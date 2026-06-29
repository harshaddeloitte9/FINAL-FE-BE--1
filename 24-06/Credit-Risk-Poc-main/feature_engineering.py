"""
feature_engineering.py - Adaptive Feature Engineering Engine
Analyzes the dataset and auto-applies relevant transformations.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from sklearn.feature_selection import mutual_info_classif, VarianceThreshold
from sklearn.metrics import roc_auc_score


MAX_DIAGNOSTIC_ROWS = 20000
MAX_IV_FEATURES = 40
MAX_WOE_FEATURES = 8
EPS = 0.5


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


def _bucket_feature(s: pd.Series, max_bins: int = 5) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        filled = s.fillna(s.median())
        if filled.nunique(dropna=True) > max_bins:
            try:
                return pd.qcut(filled, q=max_bins, duplicates="drop").astype(str)
            except Exception:
                return filled.round(6).astype(str)
        return filled.astype(str)
    return s.astype("object").fillna("__MISSING__").astype(str)


def _woe_map_for_series(s: pd.Series, y_bin: pd.Series) -> Tuple[Dict[str, float], float]:
    buckets = _bucket_feature(s)
    df = pd.DataFrame({"bucket": buckets, "target": y_bin}).dropna()
    if df.empty or df["target"].nunique() != 2:
        return {}, 0.0

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
    return woe.replace([np.inf, -np.inf], 0).fillna(0).to_dict(), float(max(iv, 0.0))


def compute_information_value(
    X: pd.DataFrame,
    y: pd.Series,
    candidate_cols: List[str],
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    """Compute simple IV and WOE maps with row/feature caps for speed."""
    X_s, y_s = _sample_xy(X, y)
    y_bin = _binary_target(y_s)
    iv_scores, woe_maps = {}, {}

    for col in candidate_cols[:MAX_IV_FEATURES]:
        if col not in X_s.columns:
            continue
        try:
            woe_map, iv = _woe_map_for_series(X_s[col], y_bin)
            if woe_map:
                iv_scores[col] = round(iv, 5)
                woe_maps[col] = woe_map
        except Exception:
            continue

    return iv_scores, woe_maps


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
        "applied_steps": [],
    }

    numeric_cols = [c for c in col_types.get("numeric", []) if c in X.columns]
    cat_cols = [c for c in col_types.get("categorical", []) if c in X.columns]

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
        plan["applied_steps"].append({
            "step": "Quantile Binning",
            "columns": plan["binning_cols"][:5],
            "reason": "High-cardinality numeric columns binned into 5 quantile buckets.",
        })

    for col in cat_cols:
        if X[col].nunique() > 8:
            plan["freq_encoding_cols"].append(col)
    if plan["freq_encoding_cols"]:
        plan["applied_steps"].append({
            "step": "Frequency Encoding",
            "columns": plan["freq_encoding_cols"],
            "reason": "High-cardinality categoricals encoded by frequency.",
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
            iv_scores, woe_maps = compute_information_value(X, y, iv_candidates)
            plan["iv_scores"] = dict(sorted(iv_scores.items(), key=lambda item: item[1], reverse=True))
            plan["woe_maps"] = woe_maps
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
    y: pd.Series,
    plan: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply the feature engineering plan to produce an enriched feature matrix.
    Returns (X_engineered, summary).
    """
    X = X.copy()
    summary = {"added": [], "removed": [], "transformed": []}
    original_shape = X.shape

    for col in plan.get("log_transform_cols", []):
        if col in X.columns:
            new_col = f"{col}_log"
            X[new_col] = np.log1p(pd.to_numeric(X[col], errors="coerce").clip(lower=0).fillna(0))
            summary["added"].append(new_col)
            summary["transformed"].append(f"log1p({col}) -> {new_col}")

    for col_a, col_b in plan.get("interaction_pairs", []):
        if col_a in X.columns and col_b in X.columns:
            new_col = f"{col_a}_x_{col_b}"
            a = pd.to_numeric(X[col_a], errors="coerce").fillna(0)
            b = pd.to_numeric(X[col_b], errors="coerce").fillna(0)
            X[new_col] = a * b
            summary["added"].append(new_col)
            summary["transformed"].append(f"{col_a} x {col_b} -> {new_col}")

    for col in plan.get("binning_cols", [])[:5]:
        if col in X.columns:
            new_col = f"{col}_bin"
            try:
                base = pd.to_numeric(X[col], errors="coerce")
                X[new_col] = pd.qcut(base.fillna(base.median()), q=5, labels=False, duplicates="drop")
                summary["added"].append(new_col)
                summary["transformed"].append(f"qcut({col}, 5) -> {new_col}")
            except Exception:
                pass

    for col in plan.get("freq_encoding_cols", []):
        if col in X.columns:
            new_col = f"{col}_freq"
            freq_map = X[col].value_counts(normalize=True).to_dict()
            X[new_col] = X[col].map(freq_map).fillna(0)
            summary["added"].append(new_col)
            summary["transformed"].append(f"freq_encode({col}) -> {new_col}")

    for col in plan.get("woe_cols", []):
        if col in X.columns and col in plan.get("woe_maps", {}):
            new_col = f"{col}_woe"
            buckets = _bucket_feature(X[col])
            X[new_col] = buckets.map(plan["woe_maps"][col]).fillna(0).astype(float)
            summary["added"].append(new_col)
            summary["transformed"].append(f"woe_encode({col}) -> {new_col}")

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
