"""
feature_engineering.py - Adaptive Feature Engineering Engine
Analyzes the dataset and auto-applies relevant transformations.
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any


MAX_DIAGNOSTIC_ROWS = 20000
MAX_IV_FEATURES = 40
MAX_WOE_FEATURES = 8
EPS = 0.5

# ── EAD calculation moved to ecl_engine (re-exported for backward compatibility) ──
# The Exposure-at-Default computation now lives in ecl_engine.py. These imports
# keep existing `from feature_engineering import compute_ead*/detect_*` callers working.
# NOTE: do NOT redefine these names below — ecl_engine.py is the single source of
# truth for EAD/outstanding-balance detection and computation (see Step 9 / ECL).
from ecl_engine import (
    PAYMENT_FREQUENCIES, DEFAULT_PAYMENT_FREQUENCY,
    detect_outstanding_balance_col, detect_loan_amount_col,
    detect_interest_rate_col, detect_years_elapsed_col, detect_term_col,
    detect_payment_frequency_col,
    compute_outstanding_balance, compute_ead_schedule, compute_ead,
)


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# ── Origination-PD columns must be hidden from model development (Change 3) ────
_ORIG_PD_SIGNATURES = [
    "originationpd", "origpd", "pdorig", "pdatorigination",
    "pdorigination", "initialpd", "basepd", "originalpd", "pdinitial",
]

# ── DPD columns are definitional leakage (dpd≥90 ≡ default=1) ───────────────
_DPD_SIGNATURES = [
    "dpd", "dayspastdue",
]


def find_origination_pd_cols(columns):
    """Columns that look like an origination PD (excluded from the PD model)."""
    out = []
    for c in columns:
        nc = _norm_name(c)
        if any(sig in nc for sig in _ORIG_PD_SIGNATURES):
            out.append(c)
    return out


def find_dpd_cols(columns):
    """Columns that look like Days-Past-Due (excluded from the PD model — DPD>=90
    is definitionally equivalent to default=1, so leaving it in is direct leakage)."""
    out = []
    for c in columns:
        nc = _norm_name(c)
        if any(sig in nc for sig in _DPD_SIGNATURES):
            out.append(c)
    return out


def _sample_xy(X: pd.DataFrame, y: pd.Series, max_rows: int = MAX_DIAGNOSTIC_ROWS):
    if len(X) <= max_rows:
        return X, y
    sample_idx = X.sample(n=max_rows, random_state=42).index
    return X.loc[sample_idx], y.loc[sample_idx]


def _binary_target(y: pd.Series) -> pd.Series:
    vals = sorted(y.dropna().unique())
    if len(vals) != 2:
        raise ValueError("WOE/IV requires a binary target")
    return y.map({vals[0]: 0, vals[1]: 1}).astype(int)


# ── LEAKAGE FIX ───────────────────────────────────────────────────────────────
# Bucketing is split into a FIT step (learns boundaries) and an APPLY step
# (uses learned boundaries). Boundaries / medians are learned on TRAIN ONLY and
# stored in the FE plan, then applied unchanged to validation and test. This
# replaces the old _bucket_feature(), which re-derived quantile edges and the
# fill median from whatever frame it was handed — leaking val/test statistics
# whenever it was used to transform val/test.

def _fit_bucketer(s: pd.Series, max_bins: int = 5) -> Dict[str, Any]:
    """
    Learn bucket boundaries on TRAIN data only. Returns a spec dict that is later
    applied (unchanged) to train, validation and test via _apply_bucketer().
    Buckets are emitted as integer codes so the WOE/bin map keys never depend on
    interval-string formatting that could differ between splits.
    """
    if pd.api.types.is_numeric_dtype(s):
        vals = pd.to_numeric(s, errors="coerce")
        median = float(vals.median()) if vals.notna().any() else 0.0
        filled = vals.fillna(median)
        edges = None
        value_categories = None
        if filled.nunique(dropna=True) > max_bins:
            try:
                _, raw_edges = pd.qcut(filled, q=max_bins, duplicates="drop", retbins=True)
                edges = [float(e) for e in raw_edges]
                if len(edges) >= 2:
                    # Open the outer edges so val/test values outside the train
                    # range still fall into the first/last train bin (no NaNs).
                    edges[0] = -np.inf
                    edges[-1] = np.inf
                else:
                    edges = None
            except Exception:
                edges = None
        if edges is None:
            # Low-cardinality numeric: each distinct TRAIN value is its own bucket.
            value_categories = [str(v) for v in sorted(filled.round(6).unique())]
        return {"kind": "numeric", "edges": edges, "median": median,
                "value_categories": value_categories}

    # Categorical: bucket = the category seen in TRAIN (missing -> __MISSING__).
    cats = s.astype("object").fillna("__MISSING__").astype(str)
    return {"kind": "categorical", "categories": list(pd.Index(cats.unique()))}


def _apply_bucketer(s: pd.Series, spec: Dict[str, Any]) -> pd.Series:
    """
    Apply a TRAIN-learned bucketer spec to ANY split. Categories/values not seen
    in training map to code -1 (a neutral bucket -> WOE 0 / frequency 0).
    """
    if spec.get("kind") == "numeric":
        vals = pd.to_numeric(s, errors="coerce").fillna(spec.get("median", 0.0))
        if spec.get("edges"):
            codes = pd.cut(vals, bins=spec["edges"], labels=False, include_lowest=True)
            return pd.Series(codes, index=s.index).fillna(-1).astype(int)
        cat_index = {c: i for i, c in enumerate(spec.get("value_categories") or [])}
        return vals.round(6).astype(str).map(cat_index).fillna(-1).astype(int)

    cat_index = {c: i for i, c in enumerate(spec.get("categories") or [])}
    cats = s.astype("object").fillna("__MISSING__").astype(str)
    return cats.map(cat_index).fillna(-1).astype(int)


def _woe_map_for_series(s: pd.Series, y_bin: pd.Series) -> Tuple[Dict[Any, float], float, Dict[str, Any]]:
    """
    Learn a WOE map on TRAIN data only. Returns (woe_map, iv, bucketer_spec).
    The bucketer spec is returned so the SAME boundaries can be re-applied to
    validation/test at transform time without re-deriving anything.
    """
    spec = _fit_bucketer(s)
    codes = _apply_bucketer(s, spec)
    df = pd.DataFrame({"bucket": codes, "target": y_bin}).dropna()
    if df.empty or df["target"].nunique() != 2:
        return {}, 0.0, spec

    grouped = df.groupby("bucket", observed=False)["target"].agg(["sum", "count"])
    grouped["bad"] = grouped["sum"]
    grouped["good"] = grouped["count"] - grouped["sum"]
    total_bad = grouped["bad"].sum()
    total_good = grouped["good"].sum()
    n_buckets = max(len(grouped), 1)

    bad_dist = (grouped["bad"] + EPS) / (total_bad + EPS * n_buckets)
    good_dist = (grouped["good"] + EPS) / (total_good + EPS * n_buckets)
    woe = np.log(good_dist / bad_dist)
    iv = ((good_dist - bad_dist) * woe).sum()
    woe_map = woe.replace([np.inf, -np.inf], 0).fillna(0).to_dict()  # keys = int bucket codes
    return woe_map, float(max(iv, 0.0)), spec


def compute_information_value(
    X: pd.DataFrame,
    y: pd.Series,
    candidate_cols: List[str],
) -> Tuple[Dict[str, float], Dict[str, Dict[Any, float]], Dict[str, Dict[str, Any]]]:
    """
    Compute IV, WOE maps AND the bucketer specs, learned on the supplied frame
    only (the caller now passes X_train / y_train). The bucketer specs are
    returned so the exact TRAIN boundaries can be re-applied to val/test.
    """
    X_s, y_s = _sample_xy(X, y)
    y_bin = _binary_target(y_s)
    iv_scores, woe_maps, woe_specs = {}, {}, {}

    for col in candidate_cols[:MAX_IV_FEATURES]:
        if col not in X_s.columns:
            continue
        try:
            woe_map, iv, spec = _woe_map_for_series(X_s[col], y_bin)
            if woe_map:
                iv_scores[col] = round(iv, 5)
                woe_maps[col] = woe_map
                woe_specs[col] = spec
        except Exception:
            continue

    return iv_scores, woe_maps, woe_specs


def compute_multicollinearity_report(
    X: pd.DataFrame,
    numeric_cols: List[str],
    corr_threshold: float = 0.90,
    max_cols: int = 30,
) -> Dict[str, Any]:
    """Fast correlation/VIF-style check on a capped numeric subset."""
    numeric_cols = [c for c in numeric_cols if c in X.columns][:max_cols]
    if len(numeric_cols) < 2:
        return {"high_corr_pairs": [], "vif": {}}

    X_s, _ = _sample_xy(X[numeric_cols], pd.Series(np.zeros(len(X)), index=X.index))
    X_num = X_s.apply(pd.to_numeric, errors="coerce").fillna(X_s.median(numeric_only=True)).fillna(0)
    corr = X_num.corr().replace([np.inf, -np.inf], 0).fillna(0)
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    high_corr_pairs = [
        {"feature_1": row, "feature_2": col, "correlation": round(float(upper.loc[row, col]), 4)}
        for col in upper.columns
        for row in upper.index
        if abs(float(upper.loc[row, col])) >= corr_threshold
    ]

    vif = {}
    try:
        corr_for_inv = corr.values + np.eye(len(corr)) * 1e-6
        inv_corr = np.linalg.pinv(corr_for_inv)
        vif = {
            col: round(float(max(inv_corr[i, i], 0)), 3)
            for i, col in enumerate(corr.columns)
        }
    except Exception:
        vif = {}

    return {"high_corr_pairs": high_corr_pairs, "vif": vif}


def analyze_for_feature_engineering(
    X: pd.DataFrame,
    y: pd.Series,
    col_types: Dict[str, List[str]],
    task_type: str = "binary",
) -> Dict[str, Any]:
    """
    Analyze dataset and decide which feature engineering steps to apply.
    Returns a plan dict explaining what will be done and why.
    """
    plan = {
        "log_transform_cols": [],
        "interaction_pairs": [],
        "binning_cols": [],
        "freq_encoding_cols": [],
        "datetime_cols": col_types.get("datetime", []),
        "drop_high_corr_pairs": [],
        "low_variance_cols": [],
        "mi_scores": {},
        "iv_scores": {},
        "woe_maps": {},
        "woe_cols": [],
        "low_iv_cols": [],
        "multicollinearity": {"high_corr_pairs": [], "vif": {}},
        "excluded_orig_pd": [],
        "applied_steps": [],
        # ── LEAKAGE FIX: learned application state (TRAIN-only), applied verbatim
        #    to val/test by apply_feature_engineering(). ──
        "freq_maps": {},   # {col: {raw_value: frequency}}      learned on X_train
        "bin_specs": {},   # {col: bucketer_spec}               learned on X_train
        "woe_specs": {},   # {col: bucketer_spec for WOE}       learned on X_train
        "learned_on": "train",
    }

    numeric_cols = [c for c in col_types.get("numeric", []) if c in X.columns]
    cat_cols = [c for c in col_types.get("categorical", []) if c in X.columns]

    # Change 3: hide origination PD and DPD from model development (leakage / definitional)
    _orig_pd_cols = find_origination_pd_cols(X.columns)
    _dpd_cols     = find_dpd_cols(X.columns)
    _hidden_cols  = list(dict.fromkeys(_orig_pd_cols + _dpd_cols))
    if _hidden_cols:
        numeric_cols = [c for c in numeric_cols if c not in _hidden_cols]
        cat_cols     = [c for c in cat_cols     if c not in _hidden_cols]
        plan["excluded_orig_pd"] = _hidden_cols

    for col in numeric_cols:
        s = X[col].dropna()
        if len(s) >= 10 and (s > 0).all() and abs(s.skew()) > 1.5:
            plan["log_transform_cols"].append(col)
    if plan["log_transform_cols"]:
        plan["applied_steps"].append({
            "step": "Log Transform",
            "columns": plan["log_transform_cols"],
            "reason": "Columns have skewness > 1.5 and positive values.",
        })

    if len(numeric_cols) >= 2 and task_type == "binary":
        try:
            X_num = X[numeric_cols].apply(pd.to_numeric, errors="coerce")
            X_num = X_num.fillna(X_num.median()).fillna(0)
            from sklearn.feature_selection import mutual_info_classif
            mi = mutual_info_classif(X_num, y.fillna(y.mode()[0]), random_state=42, discrete_features=False)
            mi_series = pd.Series(mi, index=numeric_cols).sort_values(ascending=False)
            plan["mi_scores"] = mi_series.round(5).to_dict()
            top_cols = mi_series.head(4).index.tolist()
            plan["interaction_pairs"] = [
                (top_cols[i], top_cols[j])
                for i in range(len(top_cols))
                for j in range(i + 1, len(top_cols))
            ][:4]
            if plan["interaction_pairs"]:
                plan["applied_steps"].append({
                    "step": "Interaction Features",
                    "columns": [f"{a}*{b}" for a, b in plan["interaction_pairs"]],
                    "reason": "Top mutual-information numeric features multiplied to capture simple nonlinear relationships.",
                })
        except Exception:
            pass

    for col in numeric_cols:
        if X[col].nunique() > 20:
            plan["binning_cols"].append(col)
    if plan["binning_cols"]:
        # LEAKAGE FIX: learn the quantile edges + fill median on TRAIN now and
        # store them, so val/test get binned with the SAME boundaries later.
        for col in plan["binning_cols"][:5]:
            plan["bin_specs"][col] = _fit_bucketer(X[col], max_bins=5)
        plan["applied_steps"].append({
            "step": "Quantile Binning",
            "columns": plan["binning_cols"][:5],
            "reason": "High-cardinality numeric columns binned into 5 quantile buckets (edges learned on training data only).",
        })

    for col in cat_cols:
        if X[col].nunique() > 8:
            plan["freq_encoding_cols"].append(col)
    if plan["freq_encoding_cols"]:
        # LEAKAGE FIX: learn the category->frequency map on TRAIN now and store
        # it; unseen val/test categories will map to 0 at apply time.
        for col in plan["freq_encoding_cols"]:
            plan["freq_maps"][col] = X[col].value_counts(normalize=True).to_dict()
        plan["applied_steps"].append({
            "step": "Frequency Encoding",
            "columns": plan["freq_encoding_cols"],
            "reason": "High-cardinality categoricals encoded by frequency (frequencies learned on training data only).",
        })

    plan["multicollinearity"] = compute_multicollinearity_report(X, numeric_cols)
    high_corr_pairs = [
        (p["feature_2"], p["feature_1"], p["correlation"])
        for p in plan["multicollinearity"].get("high_corr_pairs", [])
    ]
    plan["drop_high_corr_pairs"] = high_corr_pairs
    if high_corr_pairs:
        plan["applied_steps"].append({
            "step": "Multicollinearity Check",
            "columns": list({p[1] for p in high_corr_pairs}),
            "reason": f"{len(high_corr_pairs)} highly correlated pair(s) found; one feature removed from each pair.",
        })

    try:
        X_num = X[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        if X_num.shape[1] > 0:
            from sklearn.feature_selection import VarianceThreshold
            selector = VarianceThreshold(threshold=0.01)
            selector.fit(X_num)
            low_var_mask = ~selector.get_support()
            plan["low_variance_cols"] = [numeric_cols[i] for i, m in enumerate(low_var_mask) if m]
            if plan["low_variance_cols"]:
                plan["applied_steps"].append({
                    "step": "Low-Variance Removal",
                    "columns": plan["low_variance_cols"],
                    "reason": "Columns with near-zero variance carry little information.",
                })
    except Exception:
        pass

    if task_type == "binary":
        try:
            iv_candidates = numeric_cols + cat_cols
            iv_scores, woe_maps, woe_specs = compute_information_value(X, y, iv_candidates)
            plan["iv_scores"] = dict(sorted(iv_scores.items(), key=lambda item: item[1], reverse=True))
            plan["woe_maps"] = woe_maps
            plan["woe_specs"] = woe_specs   # LEAKAGE FIX: store TRAIN bucketer specs for WOE
            plan["woe_cols"] = list(plan["iv_scores"].keys())[:MAX_WOE_FEATURES]
            plan["low_iv_cols"] = [c for c, iv in plan["iv_scores"].items() if iv < 0.02]
            if plan["woe_cols"]:
                plan["applied_steps"].append({
                    "step": "WOE Transformation",
                    "columns": plan["woe_cols"],
                    "reason": "Top IV features receive lightweight Weight of Evidence encoded copies.",
                })
            if plan["low_iv_cols"]:
                plan["applied_steps"].append({
                    "step": "Information Value Selection",
                    "columns": plan["low_iv_cols"][:20],
                    "reason": "Very low-IV features are removed using a simple IV < 0.02 rule.",
                })
        except Exception:
            pass

    return plan


def apply_feature_engineering(
    X: pd.DataFrame,
    plan: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply a feature engineering plan to a feature matrix.

    LEAKAGE FIX: this is now a PURE TRANSFORM. Every data-dependent quantity
    (frequency maps, bin edges, WOE buckets + maps, fill medians, drop lists) is
    read from `plan`, which was learned on X_train only. Nothing is recomputed
    from `X`, so it produces identical, train-defined transformations whether `X`
    is the train, validation or test split. The `y` argument has been removed
    because supervised statistics must never be (re)learned at apply time.

    Returns (X_engineered, summary).
    """
    X = X.copy()
    summary = {"added": [], "removed": [], "transformed": []}
    original_shape = X.shape

    # Change 3: drop origination PD and DPD — they must never be model features
    _orig_pd_cols = find_origination_pd_cols(X.columns)
    _dpd_cols     = find_dpd_cols(X.columns)
    _hidden_cols  = list(dict.fromkeys(_orig_pd_cols + _dpd_cols))
    if _hidden_cols:
        X = X.drop(columns=_hidden_cols, errors="ignore")
    summary["excluded_orig_pd"] = _hidden_cols

    # ── Log transform (stateless) ──
    for col in plan.get("log_transform_cols", []):
        if col in X.columns:
            new_col = f"{col}_log"
            X[new_col] = np.log1p(pd.to_numeric(X[col], errors="coerce").clip(lower=0).fillna(0))
            summary["added"].append(new_col)
            summary["transformed"].append(f"log1p({col}) -> {new_col}")

    # ── Interaction features (stateless) ──
    for col_a, col_b in plan.get("interaction_pairs", []):
        if col_a in X.columns and col_b in X.columns:
            new_col = f"{col_a}_x_{col_b}"
            a = pd.to_numeric(X[col_a], errors="coerce").fillna(0)
            b = pd.to_numeric(X[col_b], errors="coerce").fillna(0)
            X[new_col] = a * b
            summary["added"].append(new_col)
            summary["transformed"].append(f"{col_a} x {col_b} -> {new_col}")

    # ── Quantile binning — apply TRAIN-learned edges (no qcut here) ──
    for col in plan.get("binning_cols", [])[:5]:
        spec = plan.get("bin_specs", {}).get(col)
        if col in X.columns and spec is not None:
            new_col = f"{col}_bin"
            X[new_col] = _apply_bucketer(X[col], spec).values
            summary["added"].append(new_col)
            summary["transformed"].append(f"bin({col}) -> {new_col} [train edges]")

    # ── Frequency encoding — apply TRAIN-learned frequency map (no value_counts) ──
    for col in plan.get("freq_encoding_cols", []):
        freq_map = plan.get("freq_maps", {}).get(col)
        if col in X.columns and freq_map is not None:
            new_col = f"{col}_freq"
            X[new_col] = X[col].map(freq_map).fillna(0.0)  # unseen categories -> 0
            summary["added"].append(new_col)
            summary["transformed"].append(f"freq_encode({col}) -> {new_col} [train freqs]")

    # ── WOE encoding — apply TRAIN-learned buckets + WOE map (no re-bucketing) ──
    for col in plan.get("woe_cols", []):
        wmap = plan.get("woe_maps", {}).get(col)
        spec = plan.get("woe_specs", {}).get(col)
        if col in X.columns and wmap and spec is not None:
            new_col = f"{col}_woe"
            codes = _apply_bucketer(X[col], spec)
            X[new_col] = codes.map(wmap).fillna(0.0).astype(float).values  # unseen bucket -> 0
            summary["added"].append(new_col)
            summary["transformed"].append(f"woe_encode({col}) -> {new_col} [train WOE]")

    # ── Feature removal — apply TRAIN-learned drop lists verbatim ──
    cols_to_drop_corr = list({p[1] for p in plan.get("drop_high_corr_pairs", [])})
    low_var_cols = plan.get("low_variance_cols", [])
    low_iv_cols = plan.get("low_iv_cols", [])
    cols_to_drop = [c for c in dict.fromkeys(cols_to_drop_corr + low_var_cols + low_iv_cols) if c in X.columns]
    if cols_to_drop:
        X = X.drop(columns=cols_to_drop)
        summary["removed"].extend(cols_to_drop)

    summary["original_shape"] = original_shape
    summary["final_shape"] = X.shape
    summary["features_added"] = len(summary["added"])
    summary["features_removed"] = len(summary["removed"])

    return X, summary


def compute_univariate_gini(
    X: pd.DataFrame,
    y: pd.Series,
    numeric_cols: List[str],
) -> Dict[str, float]:
    """
    Compute per-feature Gini coefficient (2*AUC - 1) against the binary target.
    Handles AUC < 0.5 by flipping (uses absolute discriminative power).
    Returns {col: gini} sorted descending, capped at MAX_IV_FEATURES columns.
    """
    try:
        y_bin = _binary_target(y)
        result: Dict[str, float] = {}
        for col in numeric_cols[:MAX_IV_FEATURES]:
            if col not in X.columns:
                continue
            try:
                vals = pd.to_numeric(X[col], errors="coerce")
                vals = vals.fillna(vals.median()).fillna(0)
                from sklearn.metrics import roc_auc_score
                auc = float(roc_auc_score(y_bin, vals))
                if auc < 0.5:
                    auc = 1.0 - auc
                result[col] = round(2.0 * auc - 1.0, 4)
            except Exception:
                continue
        return dict(sorted(result.items(), key=lambda kv: kv[1], reverse=True))
    except Exception:
        return {}


def get_feature_importance_summary(importance_dict: Dict[str, float], top_n: int = 15) -> pd.DataFrame:
    """Return top-N feature importances as a sorted DataFrame."""
    df = pd.DataFrame(list(importance_dict.items()), columns=["Feature", "Importance"])
    df = df.sort_values("Importance", ascending=False).head(top_n).reset_index(drop=True)
    df["Importance"] = df["Importance"].round(4)
    return df
