"""
preprocessing.py - Adaptive Data Preprocessing Engine
Dynamically builds sklearn Pipelines and ColumnTransformers based on dataset characteristics.

FIX v2:
  - get_feature_names_out() used to extract REAL names after fit (incl. OHE expansion)
  - Boolean detection no longer grabs integer columns like employment_years
  - Preprocessor is rebuilt on X_engineered so column sets always match

FIX v3:
  - Winsorizer clips to [q_low, q_high] percentiles before scaling
  - Log-transform pipeline for right-skewed all-positive columns

FIX v4 (manager review - "platform PROPOSES with evidence, USER decides"):
  - REMOVED: keyword-based critical/medium priority tiers (_IMPUTE_KEYWORDS),
    keyword-based count detection (_COUNT_KEYWORDS), MissingFlagTransformer /
    missing-flag features, and the old learn_imputation/apply_imputation
    segment-mean/median model. All of these were model/dataset-dependent
    heuristics baked into column names rather than derived from the data.
  - ADDED: classify_missing_treatment() - a data-shape-only classifier that
    proposes one of {unknown_category, zero_fill, statistical, review_flag}
    per column, with a human-readable reason and supporting evidence.
  - ADDED: select_imputation_strategy() - chooses ONE joint strategy
    (mice | knn | median) for the whole "statistical" numeric block based on
    inter-column correlation, missingness and row count, so a caller can show
    the evidence and let the user confirm before anything is fit.
  - ADDED: SemanticImputer - a standalone transformer (meant to run BEFORE the
    ColumnTransformer built here) that applies the confirmed treatment plan:
    zero-fill for structural zeros/binaries, "Unknown" for categoricals, and
    the selected MICE/KNN/median strategy - fit jointly across the numeric
    block - for genuinely missing values. review_flag columns are left alone;
    the user decides whether to keep (and how) or drop them upstream.
  - Because SemanticImputer now handles real imputation upstream, the
    SimpleImputer steps inside the num_* pipelines below are pass-through
    safety nets only (they should see no missing values in normal operation).
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import (
    StandardScaler, RobustScaler,
    OneHotEncoder, OrdinalEncoder
)
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.base import BaseEstimator, TransformerMixin


# ─────────────────────────────────────────────
# Analysis helpers
# ─────────────────────────────────────────────

def recommend_transform(series: pd.Series, model_family: str = "linear") -> Dict[str, Any]:
    """
    Single source of truth for skew-driven transform recommendations —
    replaces the two previously-inconsistent thresholds that used to live
    separately in analyze_numeric_column() (|skew| > 1.0) and
    analyze_for_feature_engineering() (|skew| > 1.5).

    Decision rule:
      |skew| < 0.5              -> "none"  ("approximately symmetric")
      0.5 <= |skew| < 1         -> "none"  (noted "optional — mild skew")
      |skew| >= 1, all values > 0 -> "log1p"
      |skew| >= 1, zeros/negatives present -> "yeo_johnson"
        (sklearn PowerTransformer(method="yeo-johnson"), fit on the values
        passed in — the CALLER is responsible for only ever passing train data)

    Then VERIFIES the recommendation actually helps: if |post_transform_skew|
    isn't reduced by at least 30% versus the original |skew|, the
    recommendation is downgraded to "none" with reason "transform ineffective
    (likely bimodal distribution)" — a transform that doesn't meaningfully
    reduce skew is usually a sign the distribution is multi-modal rather than
    single-tailed, and log/Yeo-Johnson won't fix that.

    This function only RECOMMENDS — nothing here fits or mutates anything
    used at inference time, and nothing calling this should auto-apply the
    result. build_preprocessing_pipeline()'s log/Yeo-Johnson routing and
    analyze_for_feature_engineering()'s log_transform_cols are both driven by
    a separate, USER-CONFIRMED choices dict — never by this function's output
    directly (see their docstrings).

    model_family: "tree" (LightGBM/XGBoost/RandomForest) or "linear"
    (logistic regression / scorecard). Tree models are invariant to monotonic
    transforms, so a "tree" recommendation is annotated as not required and
    comes back with default_on=False; "linear" defaults to default_on=True.

    Returns:
      {
        "transform": "none" | "log1p" | "yeo_johnson",
        "skew": float,
        "post_transform_skew": float | None,
        "reason": str,
        "default_on": bool,   # whether the UI's selectbox should default to
                               # applying this recommendation, given model_family
      }
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 10:
        return {
            "transform": "none", "skew": 0.0, "post_transform_skew": None,
            "reason": "Too few non-missing values to assess skew reliably (< 10).",
            "default_on": False,
        }

    skew = float(s.skew())
    abs_skew = abs(skew)

    if abs_skew < 0.5:
        return {
            "transform": "none", "skew": round(skew, 4), "post_transform_skew": None,
            "reason": "Approximately symmetric (|skew| < 0.5).",
            "default_on": False,
        }

    if abs_skew < 1.0:
        return {
            "transform": "none", "skew": round(skew, 4), "post_transform_skew": None,
            "reason": "Optional — mild skew (0.5 ≤ |skew| < 1); a transform is not required.",
            "default_on": False,
        }

    all_positive = bool((s > 0).all())
    if all_positive:
        transform = "log1p"
        transformed = np.log1p(s)
    else:
        transform = "yeo_johnson"
        try:
            from sklearn.preprocessing import PowerTransformer
            pt = PowerTransformer(method="yeo-johnson")
            transformed = pd.Series(
                pt.fit_transform(s.values.reshape(-1, 1)).ravel(), index=s.index
            )
        except Exception as e:
            return {
                "transform": "none", "skew": round(skew, 4), "post_transform_skew": None,
                "reason": f"Yeo-Johnson fit failed ({e}) — recommending no transform.",
                "default_on": False,
            }

    post_skew = float(transformed.skew())
    reduction = (1.0 - abs(post_skew) / abs_skew) if abs_skew > 0 else 0.0

    if reduction < 0.30:
        return {
            "transform": "none", "skew": round(skew, 4), "post_transform_skew": round(post_skew, 4),
            "reason": (
                f"Transform ineffective (likely bimodal distribution) — |skew| only reduced by "
                f"{reduction:.0%} (needs ≥ 30%). Recommending no transform."
            ),
            "default_on": False,
        }

    method_label = "log1p" if transform == "log1p" else "Yeo-Johnson"
    positivity_note = "all values are positive" if all_positive else "zeros/negatives are present"
    reason = (
        f"|skew| = {abs_skew:.2f} ≥ 1 and {positivity_note} — {method_label} reduces skew by "
        f"{reduction:.0%} ({skew:.2f} → {post_skew:.2f})."
    )
    default_on = True
    if model_family == "tree":
        reason += (" Not required — tree models are invariant to monotonic transforms; "
                   "defaulting OFF (you can still opt in).")
        default_on = False

    return {
        "transform": transform,
        "skew": round(skew, 4),
        "post_transform_skew": round(post_skew, 4),
        "reason": reason,
        "default_on": default_on,
    }


def analyze_numeric_column(series: pd.Series, model_family: str = "linear") -> Dict[str, Any]:
    s = series.dropna()
    result = {
        "missing_pct": series.isna().mean(),
        "skewness": float(s.skew()) if len(s) > 3 else 0.0,
        "has_outliers": False,
        "scaler": "standard",
        "safety_net_imputer": "mean",
        "needs_log": False,
        "outlier_frac": 0.0,
        "is_count": False,  # set by caller via column name detection
        "transform_recommendation": None,  # populated below via recommend_transform()
    }
    if len(s) < 4:
        return result

    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    outlier_frac = ((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).mean() if iqr > 0 else 0.0
    result["outlier_frac"] = float(outlier_frac)

    if outlier_frac > 0.02:
        result["has_outliers"] = True
        result["scaler"] = "robust"
        result["safety_net_imputer"] = "median"

    # Skew/transform decision now goes through the single unified
    # recommend_transform() — see its docstring for why the two previously
    # separate thresholds (1.0 here, 1.5 in feature_engineering.py) were
    # inconsistent and have been replaced. `needs_log` is kept as a legacy
    # boolean for any caller still reading it, but is a PROPOSAL only —
    # nothing here applies it; see build_preprocessing_pipeline()'s
    # transform_choices-driven routing.
    recommendation = recommend_transform(s, model_family=model_family)
    result["transform_recommendation"] = recommendation
    result["needs_log"] = recommendation["transform"] == "log1p"
    if recommendation["transform"] in ("log1p", "yeo_johnson"):
        result["safety_net_imputer"] = "median"

    if result["missing_pct"] > 0.20:
        result["safety_net_imputer"] = "median"

    return result


def analyze_categorical_column(series: pd.Series) -> Dict[str, Any]:
    s = series.dropna()
    cardinality = s.nunique()
    freq_dist = s.value_counts(normalize=True)
    return {
        "missing_pct": series.isna().mean(),
        "cardinality": cardinality,
        "is_binary": cardinality == 2,
        "encoding": "onehot" if cardinality <= 8 else "ordinal",
        "top_freq": float(freq_dist.iloc[0]) if len(freq_dist) > 0 else 1.0,
        "freq_imbalance": float(freq_dist.iloc[0] - freq_dist.iloc[-1]) if len(freq_dist) > 1 else 0.0,
    }


# ─────────────────────────────────────────────
# Semantic-aware missing value treatment
# The platform PROPOSES a treatment + strategy with evidence; the USER decides
# whether to accept, edit, or override before anything is fit. Nothing here
# uses column-name keywords — every decision is derived from the data itself.
# ─────────────────────────────────────────────

REVIEW_MISSING_THRESHOLD = 0.40


def classify_missing_treatment(
    X_train: pd.DataFrame,
    col_types: Dict[str, List[str]],
    force_include_cols: List[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Propose a missing-value TREATMENT for every column in X_train that actually
    has missing values, using data shape only (no column-name keywords):

      - categorical / object                         -> "unknown_category"
      - 2 unique non-null numeric values              -> "zero_fill"   (binary)
      - non-negative integer-valued, mode==0, skew>1  -> "zero_fill"   (structural
        zero, e.g. counts / missed payments — replaces the old keyword-based
        count detection)
      - any remaining numeric column with missing     -> "statistical"
      - ANY column with >40% missing                  -> "review_flag" (checked
        first, overrides the above — excluded from imputation entirely; the
        user decides whether to keep it (and how) or drop it)

    `force_include_cols`: columns to classify NORMALLY even if they're above
    the review threshold — i.e. skip straight to the categorical/zero-fill/
    statistical checks below instead of stopping at "review_flag". This is
    for the case where a reviewer explicitly chooses to KEEP a column the
    platform recommended dropping: since it's staying in the dataset, it
    needs a REAL treatment recalibrated for it, not the placeholder
    "review_flag" (which SemanticImputer leaves untouched, so the column
    would silently fall through to the pipeline's generic safety-net
    imputer instead of a treatment actually chosen for its data shape).

    Returns {col: {"treatment": str, "reason": str, "evidence": dict}}.
    Columns with no missing values are omitted.
    """
    numeric_cols = set(col_types.get("numeric", []))
    categorical_cols = set(col_types.get("categorical", []))
    force_include_cols = set(force_include_cols or [])
    results: Dict[str, Dict[str, Any]] = {}

    for col in X_train.columns:
        if col not in numeric_cols and col not in categorical_cols:
            continue  # boolean / datetime / id — handled by their own pipelines

        s = X_train[col]
        missing_pct = float(s.isna().mean())
        if missing_pct <= 0:
            continue

        # >40% missing overrides everything else — too sparse to impute reliably.
        # Skipped for force_include_cols: the reviewer already decided to keep
        # this column despite that, so it needs a real, recalibrated treatment.
        if missing_pct > REVIEW_MISSING_THRESHOLD and col not in force_include_cols:
            results[col] = {
                "treatment": "review_flag",
                "reason": (
                    f"{missing_pct:.1%} missing exceeds the {REVIEW_MISSING_THRESHOLD:.0%} "
                    "review threshold — too sparse to impute reliably. Excluded from "
                    "imputation; keep or drop this column explicitly."
                ),
                "evidence": {"missing_pct": round(missing_pct, 4)},
            }
            continue

        if col in categorical_cols:
            results[col] = {
                "treatment": "unknown_category",
                "reason": "Categorical column — missing values filled with an explicit 'Unknown' category.",
                "evidence": {"missing_pct": round(missing_pct, 4)},
            }
            continue

        # Numeric from here on.
        nonnull = pd.to_numeric(s, errors="coerce").dropna()
        if len(nonnull) == 0:
            # All-NaN column: imputers drop these from their output, misaligning
            # the imputed array. Treat as review_flag so SemanticImputer leaves
            # it alone and build_preprocessing_pipeline excludes it entirely.
            results[col] = {
                "treatment": "review_flag",
                "reason": (
                    "All values are missing (0 non-null rows) — imputation is "
                    "impossible. Exclude or drop this column."
                ),
                "evidence": {"missing_pct": round(missing_pct, 4)},
            }
            continue

        n_unique = int(nonnull.nunique())
        if n_unique == 2:
            unique_vals = sorted(nonnull.unique().tolist())
            results[col] = {
                "treatment": "zero_fill",
                "reason": f"Binary numeric column (observed values={unique_vals}) — missing treated as the absent/zero state.",
                "evidence": {"missing_pct": round(missing_pct, 4), "unique_values": unique_vals},
            }
            continue

        is_nonneg = bool((nonnull >= 0).all())
        is_integer_valued = bool(np.all(np.isclose(nonnull.values % 1, 0)))
        modes = nonnull.mode()
        mode_is_zero = bool(len(modes) and (modes == 0).any())
        skew = float(nonnull.skew()) if len(nonnull) > 3 else 0.0

        if is_nonneg and is_integer_valued and mode_is_zero and skew > 1.0:
            results[col] = {
                "treatment": "zero_fill",
                "reason": (
                    f"Non-negative, integer-valued column with mode=0 and skewness={skew:.2f} > 1 "
                    "— a structural-zero pattern typical of counts or missed-payment fields."
                ),
                "evidence": {"missing_pct": round(missing_pct, 4), "mode": 0, "skewness": round(skew, 3)},
            }
            continue

        results[col] = {
            "treatment": "statistical",
            "reason": (
                "Numeric column with missing values that is neither binary nor a structural-zero "
                "pattern — routed to joint statistical imputation (MICE/KNN/median)."
            ),
            "evidence": {"missing_pct": round(missing_pct, 4), "skewness": round(skew, 3)},
        }

    return results


# ─────────────────────────────────────────────
# "Impact of dropping this feature" — reviewer decision support for sparse
# (review_flag) columns. This is a lightweight, standalone estimate computed
# at THIS stage (before the split's features are engineered) so a reviewer
# can weigh "keep vs drop" now — it is NOT the authoritative IV/WOE computed
# later in feature engineering (which bins on cleaned/engineered data with
# optimal binning). It exists purely to surface three things a human needs to
# make the call: predictive power (a quick IV estimate), redundancy (is
# another feature already carrying this signal), and how much real data would
# be discarded if the column is dropped.
# ─────────────────────────────────────────────

IV_REDUNDANCY_CORR_THRESHOLD = 0.60


def _quick_iv_estimate(
    s_valid: pd.Series,
    y_bin: pd.Series,
    is_numeric: bool,
    n_bins: int = 5,
) -> Any:
    """Fast IV estimate via quantile (numeric) or top-category (categorical)
    binning against a binarized target. Returns a float IV or None if it
    can't be estimated (degenerate bins, single-class target, etc.)."""
    try:
        if is_numeric and pd.api.types.is_numeric_dtype(s_valid):
            nunique = s_valid.nunique()
            if nunique < 2:
                return None
            buckets = pd.qcut(s_valid, q=min(n_bins, nunique), duplicates="drop")
        else:
            cats = s_valid.astype(str)
            top = cats.value_counts().nlargest(n_bins).index
            buckets = cats.where(cats.isin(top), "Other")

        tab = pd.crosstab(buckets, y_bin)
        if tab.shape[0] < 2 or 0 not in tab.columns or 1 not in tab.columns:
            return None

        # Laplace smoothing (+0.5) so zero-count bins don't blow up WOE.
        goods = tab[0].astype(float) + 0.5
        bads = tab[1].astype(float) + 0.5
        good_dist = goods / goods.sum()
        bad_dist = bads / bads.sum()
        woe = np.log(bad_dist / good_dist)
        return float(((bad_dist - good_dist) * woe).sum())
    except Exception:
        return None


def _iv_strength_label(iv: float) -> str:
    if iv < 0.02:
        return "Not useful"
    if iv < 0.10:
        return "Weak"
    if iv < 0.30:
        return "Medium"
    if iv < 0.50:
        return "Strong"
    return "Suspiciously high (check for leakage)"


def estimate_drop_impact(
    col: str,
    X_train: pd.DataFrame,
    y_train: Any,
    col_types: Dict[str, List[str]],
    min_rows_for_iv: int = 30,
) -> Dict[str, Any]:
    """
    Estimate the impact of DROPPING a single sparse column, combining three
    factors a reviewer needs to weigh a keep-vs-drop call:

      1. Predictive importance — a quick IV estimate against the training
         target (binary only), computed on the column's non-missing rows.
      2. Redundancy — the other numeric column (if any) most correlated with
         this one; a strong partner means another feature may already be
         capturing the same signal.
      3. Rows with real data — how many training rows actually have a value
         for this column (i.e. how much information is discarded if it's
         dropped, versus how much is already missing either way).

    Returns a dict: {iv, iv_label, redundant_col, redundant_corr,
    rows_available, rows_available_pct, verdict, verdict_tone}. `verdict_tone`
    is one of "safe" / "caution" / "risk" / "neutral" for UI coloring.
    """
    numeric_cols = set(col_types.get("numeric", []))
    result: Dict[str, Any] = {
        "iv": None,
        "iv_label": None,
        "redundant_col": None,
        "redundant_corr": None,
        "rows_available": 0,
        "rows_available_pct": 0.0,
    }

    if col not in X_train.columns:
        result["verdict"] = f"Column '{col}' not found in the training data."
        result["verdict_tone"] = "neutral"
        return result

    s = X_train[col]
    nonnull_mask = s.notna()
    result["rows_available"] = int(nonnull_mask.sum())
    result["rows_available_pct"] = float(nonnull_mask.mean()) if len(s) else 0.0

    # ---- 1. Predictive importance (IV) ----
    if y_train is not None:
        try:
            y_aligned = pd.Series(y_train).reindex(X_train.index)
        except Exception:
            y_aligned = None
        if y_aligned is not None:
            valid = nonnull_mask & y_aligned.notna()
            y_valid = y_aligned[valid]
            uniq_y = sorted(pd.unique(y_valid))
            if int(valid.sum()) >= min_rows_for_iv and len(uniq_y) == 2:
                pos_label = uniq_y[-1]
                y_bin = (y_valid == pos_label).astype(int)
                iv = _quick_iv_estimate(s[valid], y_bin, is_numeric=col in numeric_cols)
                if iv is not None:
                    result["iv"] = round(iv, 4)
                    result["iv_label"] = _iv_strength_label(iv)

    # ---- 2. Redundancy — strongest correlated numeric partner ----
    if col in numeric_cols:
        s_num = pd.to_numeric(s, errors="coerce")
        best_col, best_corr = None, 0.0
        for other in numeric_cols:
            if other == col or other not in X_train.columns:
                continue
            o_num = pd.to_numeric(X_train[other], errors="coerce")
            pair = pd.concat([s_num, o_num], axis=1).dropna()
            if len(pair) < min_rows_for_iv:
                continue
            corr = pair.iloc[:, 0].corr(pair.iloc[:, 1])
            if corr is not None and not np.isnan(corr) and abs(corr) > abs(best_corr):
                best_col, best_corr = other, float(corr)
        if best_col is not None and abs(best_corr) >= IV_REDUNDANCY_CORR_THRESHOLD:
            result["redundant_col"] = best_col
            result["redundant_corr"] = round(best_corr, 3)

    # ---- 3. Verdict — combine predictive power + redundancy ----
    result["verdict"], result["verdict_tone"] = _build_drop_verdict(result)
    return result


def _build_drop_verdict(r: Dict[str, Any]) -> Tuple[str, str]:
    iv, redundant_col, redundant_corr = r.get("iv"), r.get("redundant_col"), r.get("redundant_corr")

    redund_note = (
        f" {redundant_col} captures similar information (|corr|={abs(redundant_corr):.2f})."
        if redundant_col else ""
    )

    if iv is None:
        return (
            "Predictive power could not be estimated (too few overlapping "
            "non-missing rows with a two-class target, or target not yet set)."
            + (f" {redund_note.strip()}" if redund_note else ""),
            "neutral",
        )

    if iv < 0.10:
        base = f"Low-to-weak predictive power (IV={iv:.3f})."
        if redundant_col:
            return (
                f"{base}{redund_note} Dropping is likely to have minimal impact — "
                f"the signal is weak and largely redundant with {redundant_col}.",
                "safe",
            )
        return (f"{base} Dropping is likely to have minimal impact on model performance.", "safe")

    if iv < 0.30:
        base = f"Moderate predictive power (IV={iv:.3f})."
        if redundant_col:
            return (
                f"{base}{redund_note} Some signal, but largely covered by {redundant_col} — "
                "dropping is a reasonable trade-off for a sparse column.",
                "caution",
            )
        return (
            f"{base} No strongly redundant feature found — dropping may cost a modest "
            "amount of signal.",
            "caution",
        )

    base = f"Strong predictive power (IV={iv:.3f})."
    if redundant_col:
        return (
            f"{base}{redund_note} Dropping is likely to reduce model performance, though "
            f"{redundant_col} may partially offset the loss.",
            "risk",
        )
    return (f"{base} Dropping is likely to reduce model performance.", "risk")

def select_imputation_strategy(
    X_train: pd.DataFrame,
    statistical_cols: List[str],
    all_numeric_cols: List[str] = None,
) -> Dict[str, Any]:
    """
    Choose ONE joint imputation strategy for the whole "statistical" numeric
    block (never mix imputers per column — MICE is chained jointly across
    columns, so column-level mixing would break that).

    Decision rule, based on per-column max absolute correlation with predictor
    columns, overall missing % across the statistical block, and n_rows:
      - n_strong > 0 AND (missing% > 15% OR n_rows > 100,000) -> "mice"
      - n_strong > 0 AND n_rows <= 100,000                    -> "knn"
      - n_strong == 0                                         -> "median"

    Where n_strong = number of statistical columns whose max|corr| with any
    predictor column is >= 0.3. When >= 50% of statistical columns are strongly
    connected the reason says so; when < 50% the reason notes the split
    ("N of M columns have strong predictors").

    Correlation is per-column maximum absolute cross-correlation against all
    predictor columns in `all_numeric_cols` (all numerics NOT in the
    statistical block). Falls back to within-statistical pairwise max if no
    predictor columns are available.

    Returns {"method": "mice"|"knn"|"median", "reason": str, "diagnostics": dict}.
    """
    cols = [c for c in statistical_cols if c in X_train.columns]
    n_rows = int(len(X_train))
    diagnostics: Dict[str, Any] = {"n_rows": n_rows, "n_cols": len(cols)}

    if not cols:
        return {
            "method": "median",
            "reason": "No columns were routed to statistical imputation.",
            "diagnostics": diagnostics,
        }

    numeric_block = X_train[cols].apply(pd.to_numeric, errors="coerce")
    missing_pct = float(numeric_block.isna().values.mean()) if numeric_block.size else 0.0
    diagnostics["missing_pct"] = round(missing_pct, 4)

    # Determine which predictor columns to correlate against.
    predictor_cols: List[str] = []
    if all_numeric_cols is not None:
        predictor_cols = [c for c in all_numeric_cols
                         if c not in cols and c in X_train.columns]

    per_col_max_corr: Dict[str, float] = {}
    mean_abs_corr = 0.0

    if predictor_cols:
        # Cross-correlation: per statistical col, max |corr| across all predictor cols.
        cross_df = X_train[cols + predictor_cols].apply(pd.to_numeric, errors="coerce")
        full_corr = cross_df.corr().abs()
        cross_block = full_corr.loc[cols, predictor_cols]
        for c in cols:
            row = cross_block.loc[c].replace([np.inf, -np.inf], np.nan).dropna()
            per_col_max_corr[c] = round(float(row.max()), 4) if len(row) else 0.0
        # Mean kept for backward-compat diagnostics only (not used for routing).
        vals = cross_block.values[np.isfinite(cross_block.values)]
        mean_abs_corr = float(vals.mean()) if len(vals) else 0.0
        diagnostics["n_predictor_cols"] = len(predictor_cols)
        diagnostics["correlation_basis"] = "statistical_vs_predictors"
    elif len(cols) >= 2:
        # Fallback: within-statistical-block pairwise max (excluding self).
        corr = numeric_block.corr().abs()
        for c in cols:
            row = corr.loc[c].drop(labels=[c], errors="ignore").replace([np.inf, -np.inf], np.nan).dropna()
            per_col_max_corr[c] = round(float(row.max()), 4) if len(row) else 0.0
        n = len(cols)
        off_diag_sum = float(np.nansum(corr.values)) - float(np.nansum(np.diag(corr.values)))
        denom = n * (n - 1)
        mean_abs_corr = float(off_diag_sum / denom) if denom > 0 else 0.0
        mean_abs_corr = 0.0 if np.isnan(mean_abs_corr) else mean_abs_corr
        diagnostics["correlation_basis"] = "within_statistical_block"
    else:
        for c in cols:
            per_col_max_corr[c] = 0.0
        diagnostics["correlation_basis"] = "none_computable"

    diagnostics["per_col_max_corr"] = per_col_max_corr
    diagnostics["mean_abs_correlation"] = round(mean_abs_corr, 4)  # kept for backward compat

    n_total = len(cols)
    n_strong = sum(1 for v in per_col_max_corr.values() if v >= 0.3)
    majority_strong = (n_strong / n_total) >= 0.5 if n_total > 0 else False
    diagnostics["n_strongly_connected"] = n_strong

    corr_ctx = (
        f"between {n_total} statistical and {len(predictor_cols)} predictor column(s)"
        if predictor_cols
        else "among statistical columns"
    )
    high_volume_or_missing = missing_pct > 0.15 or n_rows > 100_000

    if n_strong > 0:
        coverage_note = ""
        if not majority_strong:
            coverage_note = (
                f" ({n_strong} of {n_total} columns have strong predictors — "
                "weakly-connected columns degrade gracefully to ~mean, no worse than median)"
            )
        else:
            coverage_note = f" ({n_strong} of {n_total} columns have strong predictors)"

        if high_volume_or_missing:
            trigger = (f"missing%={missing_pct:.1%} > 15%" if missing_pct > 0.15
                       else f"n_rows={n_rows:,} > 100,000")
            return {
                "method": "mice",
                "reason": (
                    f"{n_strong}/{n_total} statistical columns have max|corr| >= 0.3 "
                    f"{corr_ctx}{coverage_note} and {trigger} — inter-column structure "
                    "and volume/missingness support chained MICE imputation."
                ),
                "diagnostics": diagnostics,
            }

        return {
            "method": "knn",
            "reason": (
                f"{n_strong}/{n_total} statistical columns have max|corr| >= 0.3 "
                f"{corr_ctx}{coverage_note}, but n_rows={n_rows:,} <= 100,000 — "
                "KNN captures the correlation structure without the added cost/complexity "
                "of chained MICE on a smaller dataset."
            ),
            "diagnostics": diagnostics,
        }

    return {
        "method": "median",
        "reason": (
            f"No statistical column has max|corr| >= 0.3 {corr_ctx} — MICE/KNN "
            "degenerate toward mean prediction without inter-column correlation, so median "
            "imputation is used instead."
        ),
        "diagnostics": diagnostics,
    }


class SemanticImputer(BaseEstimator, TransformerMixin):
    """
    Semantic-aware missing-value treatment, meant to run as a standalone step
    BEFORE the ColumnTransformer built by build_preprocessing_pipeline(). It
    applies the treatment plan from classify_missing_treatment() (or a plan the
    user has reviewed/edited) plus the strategy from select_imputation_strategy():

      - "unknown_category" columns -> filled with "Unknown"
      - "zero_fill" columns        -> filled with 0
      - "statistical" columns      -> filled jointly via the selected strategy,
        fit on the FULL numeric matrix (including already zero-filled columns,
        so they can act as predictors) — never refit at transform time
      - "review_flag" columns      -> left untouched (excluded from imputation;
        the caller/user decides whether to keep or drop them)

    fit() learns everything from X_train only. transform() only applies the
    fitted state, so it is safe to call on validation/test/inference data.
    """

    def __init__(self, col_types: Dict[str, List[str]] = None,
                 treatment_map: Dict[str, Dict[str, Any]] = None,
                 strategy_choice: Dict[str, Any] = None):
        self.col_types = col_types
        self.treatment_map = treatment_map
        self.strategy_choice = strategy_choice

    def fit(self, X, y=None):
        X = pd.DataFrame(X).copy()
        col_types = self.col_types or {}

        self.treatment_map_ = self.treatment_map or classify_missing_treatment(X, col_types)

        self.zero_fill_cols_ = [c for c, v in self.treatment_map_.items()
                                 if v["treatment"] == "zero_fill" and c in X.columns]
        self.unknown_cols_ = [c for c, v in self.treatment_map_.items()
                               if v["treatment"] == "unknown_category" and c in X.columns]
        self.statistical_cols_ = [c for c, v in self.treatment_map_.items()
                                   if v["treatment"] == "statistical" and c in X.columns]
        self.review_flag_cols_ = [c for c, v in self.treatment_map_.items()
                                   if v["treatment"] in ("review_flag", "woe_pending") and c in X.columns]

        numeric_all = [c for c in col_types.get("numeric", []) if c in X.columns]
        self.numeric_matrix_cols_ = [c for c in numeric_all if c not in self.review_flag_cols_]

        if not self.statistical_cols_:
            self.strategy_ = self.strategy_choice or {
                "method": "median", "reason": "No columns routed to statistical imputation.",
                "diagnostics": {},
            }
            self.effective_method_  = "median"
            self.n_predictor_cols_  = 0
            self.imputer_ = None
            self.scaler_  = None
            return self

        # Apply zero-fill on a working copy BEFORE strategy selection so the
        # cross-correlation measurement sees predictor columns already filled.
        X_zero_filled = X.copy()
        for c in self.zero_fill_cols_:
            X_zero_filled[c] = pd.to_numeric(X_zero_filled[c], errors="coerce").fillna(0.0)

        numeric_matrix = X_zero_filled[self.numeric_matrix_cols_].apply(pd.to_numeric, errors="coerce")

        # Predictor columns = full matrix minus the columns being imputed.
        # They provide signal to KNN / MICE and are left untouched after imputation.
        predictor_only = [c for c in self.numeric_matrix_cols_ if c not in self.statistical_cols_]
        self.n_predictor_cols_ = len(predictor_only)

        # Pass the full predictor matrix so correlation is measured against all
        # available numerics, not just within the (possibly 1-column) statistical block.
        self.strategy_ = self.strategy_choice or select_imputation_strategy(
            X_zero_filled, self.statistical_cols_,
            all_numeric_cols=self.numeric_matrix_cols_,
        )
        method = self.strategy_.get("method", "median")

        # Edge case: no predictor columns → KNN/MICE degenerate to single-column
        # fill (equivalent to mean).  Auto-downgrade to median and surface the
        # reason so the user can see it in the strategy card.
        if method in ("mice", "knn") and self.n_predictor_cols_ == 0:
            requested = method
            method = "median"
            self.strategy_ = {
                **self.strategy_,
                "method": "median",
                "reason": (
                    f"Auto-downgraded from {requested.upper()} to MEDIAN — "
                    "the statistical block is the only numeric feature in the matrix "
                    "so there are no predictor columns. KNN/MICE would degenerate to "
                    "mean fill with no useful signal."
                ),
            }

        self.effective_method_ = method

        if method == "mice":
            from sklearn.experimental import enable_iterative_imputer  # noqa: F401
            from sklearn.impute import IterativeImputer
            from sklearn.linear_model import BayesianRidge
            self.imputer_ = IterativeImputer(estimator=BayesianRidge(), max_iter=10, random_state=42)
            self.imputer_.fit(numeric_matrix)
            self.scaler_  = None
        elif method == "knn":
            # Scale full matrix → KNN fit → inverse-scale at transform time.
            self.scaler_  = StandardScaler()
            scaled = self.scaler_.fit_transform(numeric_matrix)
            self.imputer_ = KNNImputer(n_neighbors=5)
            self.imputer_.fit(scaled)
        else:
            self.imputer_ = SimpleImputer(strategy="median")
            self.imputer_.fit(numeric_matrix)
            self.scaler_  = None

        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()

        for c in self.unknown_cols_:
            if c in X.columns:
                X[c] = X[c].astype("object").where(X[c].notna(), "Unknown")

        for c in self.zero_fill_cols_:
            if c in X.columns:
                X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0.0)

        if self.statistical_cols_ and self.imputer_ is not None:
            numeric_matrix = X[self.numeric_matrix_cols_].apply(pd.to_numeric, errors="coerce")
            if self.scaler_ is not None:
                scaled = self.scaler_.transform(numeric_matrix)
                imputed = self.scaler_.inverse_transform(self.imputer_.transform(scaled))
            else:
                imputed = self.imputer_.transform(numeric_matrix)
            assert imputed.shape[1] == len(self.numeric_matrix_cols_), (
                f"Imputed array has {imputed.shape[1]} columns but expected "
                f"{len(self.numeric_matrix_cols_)}. An all-NaN column was likely "
                "dropped by the imputer — classify it as review_flag instead."
            )
            imputed_df = pd.DataFrame(imputed, columns=self.numeric_matrix_cols_, index=X.index)
            for c in self.statistical_cols_:
                X[c] = imputed_df[c]

        return X

    def get_feature_names_out(self, input_features=None):
        return np.array(input_features) if input_features is not None else np.array([])


MISSING_VALUE_LIMITATION_NOTE = (
    "MICE/KNN assume Missing At Random; informative missingness (MNAR) is a "
    "known limitation in credit data."
)


def build_preprocessing_report(
    df: pd.DataFrame,
    col_types: Dict[str, List[str]],
    target_col: str,
    model_family: str = "linear",
    transform_choices: Dict[str, str] = None,
) -> Dict[str, Any]:
    """Analyse all columns and return a preprocessing strategy report.

    Missing-value handling is PROPOSED, not silently applied: classify_missing_
    treatment() and select_imputation_strategy() populate report["missing_
    treatment"] / report["imputation_strategy"] with the treatment, reason and
    evidence per column so the user can review and confirm before a
    SemanticImputer is ever fit.

    Skew-driven transforms work the same way: every numeric column's
    recommend_transform() output is stored in report["numeric"][col]
    ["transform_recommendation"] (and mirrored in report["transform_
    recommendations"] for convenience), but NOTHING is applied from that
    alone. `transform_choices` — a {column: "none"|"log1p"|"yeo_johnson"}
    dict of the reviewer's actual, confirmed selections (defaulting to each
    column's recommendation only once the reviewer has seen and accepted it
    in the UI) — is what build_preprocessing_pipeline() actually routes on.
    Pass None / omit it and every column gets "none": no transform, ever,
    until a human confirms one.

    model_family: "tree" (LightGBM/XGBoost/RandomForest) or "linear"
    (logistic regression/scorecard) — passed through to recommend_transform()
    so tree-model recommendations come back annotated as not required and
    defaulted off.
    """
    report = {"numeric": {}, "categorical": {}, "datetime": {}, "boolean": {}, "decisions": []}
    feature_cols = [c for c in df.columns if c != target_col]
    X_features = df[feature_cols]

    missing_treatment = classify_missing_treatment(X_features, col_types)
    statistical_cols = [c for c, v in missing_treatment.items() if v["treatment"] == "statistical"]
    # Mirror SemanticImputer.fit exactly: apply zero-fill on a working copy
    # before calling select_imputation_strategy so the cross-correlation matrix
    # sees predictor columns already filled — same as the imputer sees at fit time.
    _zero_fill_cols_report = [c for c, v in missing_treatment.items()
                               if v["treatment"] == "zero_fill" and c in X_features.columns]
    X_for_strategy = X_features.copy()
    for _c in _zero_fill_cols_report:
        X_for_strategy[_c] = pd.to_numeric(X_for_strategy[_c], errors="coerce").fillna(0.0)
    review_flag_cols = [
        c for c, v in missing_treatment.items()
        if v["treatment"] in ("review_flag", "woe_pending")
    ]
    all_numeric_cols = [
        c for c in col_types.get("numeric", [])
        if c not in review_flag_cols
    ]
    imputation_strategy = select_imputation_strategy(
        X_for_strategy, statistical_cols,
        all_numeric_cols=all_numeric_cols,
    )

    report["missing_treatment"] = missing_treatment
    report["imputation_strategy"] = imputation_strategy
    report["review_flag_cols"] = [c for c, v in missing_treatment.items() if v["treatment"] == "review_flag"]
    report["missing_value_limitation_note"] = MISSING_VALUE_LIMITATION_NOTE

    transform_choices = transform_choices or {}
    report["transform_choices"] = transform_choices
    report["transform_recommendations"] = {}

    for col in col_types.get("numeric", []):
        if col == target_col or col not in feature_cols:
            continue
        analysis = analyze_numeric_column(df[col], model_family=model_family)
        report["numeric"][col] = analysis
        report["transform_recommendations"][col] = analysis["transform_recommendation"]
        reasons = []
        if analysis["has_outliers"]:
            reasons.append(f"RobustScaler (outlier_frac={analysis['outlier_frac']:.2%})")
        else:
            reasons.append("StandardScaler (no significant outliers)")
        rec = analysis.get("transform_recommendation") or {}
        if rec.get("transform") in ("log1p", "yeo_johnson"):
            confirmed = transform_choices.get(col)
            status = f"confirmed: {confirmed}" if confirmed else "not yet confirmed — no transform applied"
            reasons.append(
                f"{rec['transform']} suggested (skew={rec['skew']:.2f} → {rec.get('post_transform_skew')}) "
                f"— {status}"
            )
        treat = missing_treatment.get(col)
        if treat:
            reasons.append(f"Proposed: {treat['treatment']} — {treat['reason']}")
        report["decisions"].append({"column": col, "type": "numeric", "actions": reasons})

    for col in col_types.get("categorical", []):
        if col == target_col or col not in feature_cols:
            continue
        analysis = analyze_categorical_column(df[col])
        report["categorical"][col] = analysis
        enc = "OneHotEncoding" if analysis["encoding"] == "onehot" else "OrdinalEncoding"
        reasons = [f"{enc} (cardinality={analysis['cardinality']})"]
        treat = missing_treatment.get(col)
        if treat:
            reasons.append(f"Proposed: {treat['treatment']} — {treat['reason']}")
        report["decisions"].append({"column": col, "type": "categorical", "actions": reasons})

    for col in col_types.get("boolean", []):
        if col == target_col or col not in feature_cols:
            continue
        report["decisions"].append({"column": col, "type": "boolean", "actions": ["Cast to int (0/1)"]})

    for col in col_types.get("datetime", []):
        if col not in feature_cols:
            continue
        report["decisions"].append({
            "column": col, "type": "datetime",
            "actions": ["Extract year, month, day, dayofweek, is_weekend, quarter"]
        })

    return report


# ─────────────────────────────────────────────
# Custom Transformers
# ─────────────────────────────────────────────

class BooleanToIntTransformer(BaseEstimator, TransformerMixin):
    """Cast boolean / 0-1 flag columns to float."""
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return pd.DataFrame(X).astype(float).values

    def get_feature_names_out(self, input_features=None):
        return np.array(input_features) if input_features is not None else np.array([])


class DatetimeFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extract 6 time-components from each datetime column."""
    SUFFIXES = ["year", "month", "day", "dayofweek", "is_weekend", "quarter"]

    def __init__(self):
        self._col_names = []

    def fit(self, X, y=None):
        if hasattr(X, "columns"):
            self._col_names = list(X.columns)
        else:
            self._col_names = [f"dt_col_{i}" for i in range(X.shape[1] if hasattr(X, "shape") else 1)]
        return self

    def transform(self, X):
        if hasattr(X, "values"):
            arr = X.values
        else:
            arr = np.asarray(X)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        n_rows = arr.shape[0]
        results = []
        for col_idx in range(arr.shape[1]):
            col_vals = arr[:, col_idx]
            series = pd.to_datetime(pd.Series(col_vals), errors="coerce")
            feats = np.column_stack([
                series.dt.year.fillna(0).astype(int).values,
                series.dt.month.fillna(0).astype(int).values,
                series.dt.day.fillna(0).astype(int).values,
                series.dt.dayofweek.fillna(0).astype(int).values,
                series.dt.dayofweek.isin([5, 6]).astype(int).values,
                series.dt.quarter.fillna(0).astype(int).values,
            ])
            results.append(feats)
        return np.hstack(results) if results else np.zeros((n_rows, 0))

    def get_feature_names_out(self, input_features=None):
        cols = input_features if input_features is not None else self._col_names
        return np.array([f"{c}_{s}" for c in cols for s in self.SUFFIXES])


class Winsorizer(BaseEstimator, TransformerMixin):
    """Clips values to [q_low, q_high] percentiles learned on training data.
    Prevents extreme values from distorting the model — critical for financial variables."""

    def __init__(self, q_low=0.01, q_high=0.99):
        self.q_low  = q_low
        self.q_high = q_high
        self.lower_ = None
        self.upper_ = None

    def fit(self, X, y=None):
        arr = pd.DataFrame(X).apply(pd.to_numeric, errors="coerce")
        self.lower_ = arr.quantile(self.q_low).values
        self.upper_ = arr.quantile(self.q_high).values
        return self

    def transform(self, X):
        arr = pd.DataFrame(X).apply(
            pd.to_numeric, errors="coerce"
        ).values.astype(float)
        return np.clip(arr, self.lower_, self.upper_)

    def get_feature_names_out(self, input_features=None):
        return np.array(input_features) if input_features is not None else np.array([])


class LogTransformer(BaseEstimator, TransformerMixin):
    """Applies log1p to all columns. Only call this on columns confirmed to be
    all-positive on training data."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        arr = pd.DataFrame(X).apply(
            pd.to_numeric, errors="coerce"
        ).clip(lower=0).fillna(0).values
        return np.log1p(arr)

    def get_feature_names_out(self, input_features=None):
        return np.array(input_features) if input_features is not None else np.array([])


class YeoJohnsonTransformer(BaseEstimator, TransformerMixin):
    """Applies a Yeo-Johnson power transform (sklearn PowerTransformer), fit on
    TRAINING data only, then reused unchanged on validation/test. Unlike log1p,
    Yeo-Johnson handles zero and negative values, so it's the recommended
    transform (see recommend_transform() in this module) for skewed columns
    that aren't all-positive."""

    def __init__(self):
        self._pt = None

    def fit(self, X, y=None):
        from sklearn.preprocessing import PowerTransformer
        arr = pd.DataFrame(X).apply(pd.to_numeric, errors="coerce").fillna(0).values
        self._pt = PowerTransformer(method="yeo-johnson")
        self._pt.fit(arr)
        return self

    def transform(self, X):
        arr = pd.DataFrame(X).apply(pd.to_numeric, errors="coerce").fillna(0).values
        return self._pt.transform(arr)

    def get_feature_names_out(self, input_features=None):
        return np.array(input_features) if input_features is not None else np.array([])



# ─────────────────────────────────────────────
# Pipeline Builder
# ─────────────────────────────────────────────

def build_preprocessing_pipeline(
    X: pd.DataFrame,
    col_types: Dict[str, List[str]],
    target_col: str,
    report: Dict[str, Any],
) -> ColumnTransformer:
    """
    Build a ColumnTransformer that operates on the ACTUAL columns present in X.
    Only includes columns that exist in X — so it is safe to call after FE.

    This ColumnTransformer assumes a SemanticImputer has already run upstream
    (see report["missing_treatment"] / report["imputation_strategy"]), so the
    SimpleImputer step inside each num_* pipeline below is a pass-through
    safety net only — it should see no missing values in normal operation.

    For a column proposed as "zero_fill" (binary or structural-zero, e.g.
    counts / missed payments):
      num_counts        — zero impute (safety net) → winsorize(0,99) → StandardScaler
    For a column with a CONFIRMED "log1p" choice in report["transform_choices"]
    (see recommend_transform() and build_preprocessing_report() — the
    recommendation alone is never enough, a human has to have picked it):
      num_log            — median impute (safety net) → winsorize → log1p → StandardScaler
    For a column with a CONFIRMED "yeo_johnson" choice:
      num_yeojohnson     — median impute (safety net) → Yeo-Johnson → StandardScaler
        (no winsorize step — Yeo-Johnson already compresses extreme values as
        part of the power transform, so winsorizing first would just distort
        the lambda it fits)
    For a standard numeric column:
      num_standard      — median impute (safety net) → winsorize → StandardScaler
    For a high-outlier numeric column:
      num_robust        — median impute (safety net) → winsorize → RobustScaler

    Columns proposed as "review_flag" (>40% missing) are EXCLUDED here — they
    are not imputed or scored until the user explicitly decides to keep them.
    """
    transformers = []
    missing_treatment = report.get("missing_treatment", {})
    # Columns explicitly kept unimputed by the reviewer (tree-model path).
    # These are NOT excluded entirely — they go to the num_passthrough_nan
    # pipeline (Winsorizer + StandardScaler, no imputer). Every other
    # review_flag / woe_pending column is still excluded via remainder="drop".
    kept_unimputed_cols = set(report.get("kept_unimputed_cols", []))
    review_flag_cols = {
        c for c, v in missing_treatment.items()
        if v.get("treatment") in ("review_flag", "woe_pending")
        and c not in kept_unimputed_cols
    }
    zero_fill_cols_proposed = {c for c, v in missing_treatment.items() if v.get("treatment") == "zero_fill"}
    transform_choices = report.get("transform_choices", {}) or {}

    # ── Numeric — initial split from report ──────────────────────────
    numeric_standard, numeric_robust = [], []
    for col, analysis in report["numeric"].items():
        if (
            col not in X.columns
            or col in review_flag_cols
            or col in kept_unimputed_cols
        ):
            continue
        if analysis["scaler"] == "robust":
            numeric_robust.append(col)
        else:
            numeric_standard.append(col)

    # Pick up engineered columns not in the original report
    known_cols = set(numeric_standard + numeric_robust)
    known_cols.update(report.get("categorical", {}).keys())
    known_cols.update(col_types.get("boolean", []))
    known_cols.update(col_types.get("datetime", []))
    extra_numeric = [
        c for c in X.columns
        if c not in known_cols
        and c not in review_flag_cols
        and c not in kept_unimputed_cols
        and pd.api.types.is_numeric_dtype(X[c])
    ]
    numeric_standard.extend(extra_numeric)

    # Structural-zero / binary columns proposed by classify_missing_treatment()
    # — zero imputation, no log. Replaces the old keyword-based count detection.
    count_cols = [
        c for c in (numeric_standard + numeric_robust)
        if (
            c in zero_fill_cols_proposed
            and c in X.columns
            and c not in kept_unimputed_cols
        )
    ]
    numeric_standard = [c for c in numeric_standard if c not in count_cols]
    numeric_robust   = [c for c in numeric_robust   if c not in count_cols]

    # Transform-routed columns — driven ONLY by the reviewer's CONFIRMED choice
    # in report["transform_choices"] ({col: "none"|"log1p"|"yeo_johnson"}),
    # never by the raw recommendation. An empty/missing transform_choices dict
    # (the default) means every column here falls through to num_standard/
    # num_robust untransformed — nothing auto-applies.
    log_cols = [
        c for c in (numeric_standard + numeric_robust)
        if (
            transform_choices.get(c) == "log1p"
            and c in X.columns
            and c not in review_flag_cols
            and c not in kept_unimputed_cols
        )
    ]
    yeojohnson_cols = [
        c for c in (numeric_standard + numeric_robust)
        if (
            transform_choices.get(c) == "yeo_johnson"
            and c in X.columns
            and c not in review_flag_cols
            and c not in kept_unimputed_cols
        )
    ]
    numeric_standard = [c for c in numeric_standard if c not in log_cols and c not in yeojohnson_cols]
    numeric_robust   = [c for c in numeric_robust   if c not in log_cols and c not in yeojohnson_cols]

    # Count / zero-fill columns pipeline
    if count_cols:
        transformers.append(("num_counts", Pipeline([
            ("imputer",   SimpleImputer(strategy="constant", fill_value=0)),
            ("winsorize", Winsorizer(q_low=0.0, q_high=0.99)),
            ("scaler",    StandardScaler()),
        ]), count_cols))

    # Log-transform columns pipeline — user-confirmed only (see above)
    if log_cols:
        transformers.append(("num_log", Pipeline([
            ("imputer",   SimpleImputer(strategy="median")),
            ("winsorize", Winsorizer(q_low=0.01, q_high=0.99)),
            ("log",       LogTransformer()),
            ("scaler",    StandardScaler()),
        ]), log_cols))

    # Yeo-Johnson columns pipeline — user-confirmed only; for skewed columns
    # with zeros/negatives, where log1p doesn't apply
    if yeojohnson_cols:
        transformers.append(("num_yeojohnson", Pipeline([
            ("imputer",      SimpleImputer(strategy="median")),
            ("yeo_johnson",  YeoJohnsonTransformer()),
            ("scaler",       StandardScaler()),
        ]), yeojohnson_cols))

    # Standard numeric pipeline (FIX 2 + FIX 4)
    if numeric_standard:
        transformers.append(("num_standard", Pipeline([
            ("imputer",   SimpleImputer(strategy="median")),
            ("winsorize", Winsorizer(q_low=0.01, q_high=0.99)),
            ("scaler",    StandardScaler()),
        ]), numeric_standard))

    # Robust numeric pipeline (FIX 4)
    if numeric_robust:
        transformers.append(("num_robust", Pipeline([
            ("imputer",   SimpleImputer(strategy="median")),
            ("winsorize", Winsorizer(q_low=0.01, q_high=0.99)),
            ("scaler",    RobustScaler()),
        ]), numeric_robust))

    # ── Kept-unimputed numeric (reviewer chose "keep unimputed") ─────
    # Winsorize + scale only — deliberately NO imputer. sklearn StandardScaler
    # propagates NaN since 0.20, so NaN rows pass through as NaN and tree
    # models (XGBoost/LightGBM) handle them natively.
    passthrough_nan_cols = [
        c for c in kept_unimputed_cols
        if c in X.columns and pd.api.types.is_numeric_dtype(X[c])
    ]
    if passthrough_nan_cols:
        transformers.append(("num_passthrough_nan", Pipeline([
            ("winsorize", Winsorizer(q_low=0.01, q_high=0.99)),
            ("scaler",    StandardScaler()),
        ]), passthrough_nan_cols))

    # ── Categorical (FIX 3) ───────────────────────────────────────────
    cat_onehot, cat_ordinal = [], []
    for col, analysis in report["categorical"].items():
        if (
            col not in X.columns
            or col in review_flag_cols
            or col in kept_unimputed_cols
        ):
            continue
        if analysis["encoding"] == "onehot":
            cat_onehot.append(col)
        else:
            cat_ordinal.append(col)

    if cat_onehot:
        transformers.append(("cat_onehot", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_onehot))

    if cat_ordinal:
        transformers.append(("cat_ordinal", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), cat_ordinal))

    # ── Boolean ───────────────────────────────────────────────────────
    bool_cols = [c for c in col_types.get("boolean", []) if c != target_col and c in X.columns]
    if bool_cols:
        # SimpleImputer fills any NaN (e.g. has_mortgage 5.7% missing) with 0 —
        # the natural "absent" value for a binary flag — before BooleanToIntTransformer
        # casts to float. sklearn scalers ignore NaN but OHE/ordinal do not, so
        # filling here is safer than relying on the safety-net imputers above.
        transformers.append(("bool_cols", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
            ("cast",    BooleanToIntTransformer()),
        ]), bool_cols))

    # ── Datetime ──────────────────────────────────────────────────────
    dt_cols = [c for c in col_types.get("datetime", []) if c in X.columns]
    if dt_cols:
        transformers.append(("datetime_cols", DatetimeFeatureExtractor(), dt_cols))

    return ColumnTransformer(transformers=transformers, remainder="drop")


def get_feature_names_from_fitted_preprocessor(preprocessor: ColumnTransformer) -> List[str]:
    """
    Extract REAL feature names from a FITTED ColumnTransformer.
    This handles OHE expansion (e.g. loan_purpose → loan_purpose_Auto, _Business, …)
    and datetime decomposition (application_date → application_date_year, …).
    Returns a flat list of human-readable strings.
    """
    names = []
    for name, transformer, cols in preprocessor.transformers_:
        if name == "remainder":
            continue
        if transformer == "drop" or transformer == "passthrough":
            if isinstance(cols, list):
                names.extend(cols)
            continue

        try:
            if hasattr(transformer, "get_feature_names_out"):
                out = transformer.get_feature_names_out(cols if isinstance(cols, list) else list(cols))
                names.extend([str(n) for n in out])
            elif hasattr(transformer, "named_steps"):
                last_step = list(transformer.named_steps.values())[-1]
                if hasattr(last_step, "get_feature_names_out"):
                    input_for_last = cols if isinstance(cols, list) else list(cols)
                    out = last_step.get_feature_names_out(input_for_last)
                    cleaned = []
                    for n in out:
                        n = str(n)
                        cleaned.append(n)
                    names.extend(cleaned)
                else:
                    names.extend(cols if isinstance(cols, list) else list(cols))
            else:
                names.extend(cols if isinstance(cols, list) else list(cols))
        except Exception:
            names.extend(cols if isinstance(cols, list) else list(cols))

    return names


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

_ECL_ONLY_SIGNATURES = [
    "dpd", "dayspastdue",
    "origpd", "originationpd", "pdorig", "pdatorigination",
    "pdorigination", "initialpd", "basepd", "originalpd", "pdinitial",
]

_POST_DEFAULT_ONLY_SIGNATURES = [
    "recoveryrate", "recoveryamount", "recoveryamt", "recoveredamount", "recovery",
    "lgd", "lossgivendefault", "lossseverity", "realizedlgd",
    "eadatdefault", "exposureatdefault", "balanceatdefault", "defaultbalance",
    "ccf", "creditconversionfactor", "realizedccf",
    "defaultdate", "dateofdefault", "defaultdt", "chargeoffdate", "writeoffdate",
    "delinquencydate",
]


def _find_ecl_only_cols(columns):
    """Return columns that are ECL/SICR inputs only — never PD model features."""
    import re
    def _norm(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())
    found = []
    for c in columns:
        nc = _norm(c)
        if any(sig in nc for sig in _ECL_ONLY_SIGNATURES):
            found.append(c)
    return found


def _find_post_default_only_cols(columns):
    """Return columns realized only at/after default (recovery, LGD, EAD-at-default,
    CCF, default date) — never PD model features."""
    import re
    def _norm(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())
    found = []
    for c in columns:
        nc = _norm(c)
        if any(sig in nc for sig in _POST_DEFAULT_ONLY_SIGNATURES):
            found.append(c)
    return found


def finalize_xy(
    df: pd.DataFrame,
    col_types: Dict[str, List[str]],
    target_col: str,
) -> Tuple[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """
    LEAKAGE FIX — Step toward train-only learning.

    Produce the final (X, y) by dropping ID columns and duplicate rows ONLY.
    No statistics are learned here, so this is safe to run on the full dataset
    *before* the train/val/test split. The preprocessing report and the
    preprocessor are intentionally NOT built here — they are built/fitted on the
    TRAIN split afterwards (see app.render_preprocessing -> build_preprocessing_report
    on X_train, and train_model -> rebuild_preprocessor_for on X_train).

    Returns (X, y, info) where info carries duplicates_removed.
    """
    df = df.copy()

    id_cols = col_types.get("id", [])
    df = df.drop(columns=[c for c in id_cols if c in df.columns], errors="ignore")

    _ecl_cols = _find_ecl_only_cols([c for c in df.columns if c != target_col])
    df = df.drop(columns=_ecl_cols, errors="ignore")

    _post_default_cols = _find_post_default_only_cols([c for c in df.columns if c != target_col])
    df = df.drop(columns=_post_default_cols, errors="ignore")

    before = len(df)
    df = df.drop_duplicates()
    after = len(df)

    y = df[target_col].copy()
    X = df.drop(columns=[target_col])

    return X, y, {
        "duplicates_removed": before - after,
        "ecl_only_cols_dropped": _ecl_cols,
        "post_default_cols_dropped": _post_default_cols,
    }


def prepare_data(
    df: pd.DataFrame,
    col_types: Dict[str, List[str]],
    target_col: str,
) -> Tuple[pd.DataFrame, pd.Series, ColumnTransformer, Dict[str, Any], List[str]]:
    """
    Prepare data: drop IDs, remove duplicates, build report + unfitted preprocessor.
    The preprocessor is NOT fitted here — it will be fitted inside train_model()
    so it always sees the exact columns in X_engineered.
    """
    df = df.copy()

    id_cols = col_types.get("id", [])
    df = df.drop(columns=[c for c in id_cols if c in df.columns], errors="ignore")

    _ecl_cols = _find_ecl_only_cols([c for c in df.columns if c != target_col])
    df = df.drop(columns=_ecl_cols, errors="ignore")

    _post_default_cols = _find_post_default_only_cols([c for c in df.columns if c != target_col])
    df = df.drop(columns=_post_default_cols, errors="ignore")

    before = len(df)
    df = df.drop_duplicates()
    after = len(df)

    y = df[target_col].copy()
    X = df.drop(columns=[target_col])

    report = build_preprocessing_report(X.assign(**{target_col: y}), col_types, target_col)

    preprocessor = build_preprocessing_pipeline(X, col_types, target_col, report)

    report["duplicates_removed"] = before - after
    report["post_default_cols_dropped"] = _post_default_cols
    feature_names = list(X.columns)
    return X, y, preprocessor, report, feature_names


def rebuild_preprocessor_for(
    X_engineered: pd.DataFrame,
    col_types: Dict[str, List[str]],
    target_col: str,
    report: Dict[str, Any],
) -> ColumnTransformer:
    """
    Build a fresh ColumnTransformer scoped to the columns in X_engineered.
    Called after feature engineering so the column list is up to date.
    """
    return build_preprocessing_pipeline(X_engineered, col_types, target_col, report)
