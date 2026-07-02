"""
preprocessing.py - Adaptive Data Preprocessing Engine
Dynamically builds sklearn Pipelines and ColumnTransformers based on dataset characteristics.

FIX v2:
  - get_feature_names_out() used to extract REAL names after fit (incl. OHE expansion)
  - Boolean detection no longer grabs integer columns like employment_years
  - Preprocessor is rebuilt on X_engineered so column sets always match
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
from sklearn.impute import SimpleImputer
from sklearn.base import BaseEstimator, TransformerMixin


# ─────────────────────────────────────────────
# Analysis helpers
# ─────────────────────────────────────────────

def analyze_numeric_column(series: pd.Series) -> Dict[str, Any]:
    s = series.dropna()
    result = {
        "missing_pct": series.isna().mean(),
        "skewness": float(s.skew()) if len(s) > 3 else 0.0,
        "has_outliers": False,
        "scaler": "standard",
        "imputer": "mean",
        "needs_log": False,
        "outlier_frac": 0.0,
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
        result["imputer"] = "median"

    if abs(result["skewness"]) > 1.0 and (s > 0).all():
        result["needs_log"] = True
        result["imputer"] = "median"

    if result["missing_pct"] > 0.20:
        result["imputer"] = "median"

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


def build_preprocessing_report(
    df: pd.DataFrame,
    col_types: Dict[str, List[str]],
    target_col: str,
) -> Dict[str, Any]:
    """Analyse all columns and return a preprocessing strategy report."""
    report = {"numeric": {}, "categorical": {}, "datetime": {}, "boolean": {}, "decisions": []}
    feature_cols = [c for c in df.columns if c != target_col]

    for col in col_types.get("numeric", []):
        if col == target_col or col not in feature_cols:
            continue
        analysis = analyze_numeric_column(df[col])
        report["numeric"][col] = analysis
        reasons = []
        if analysis["has_outliers"]:
            reasons.append(f"RobustScaler (outlier_frac={analysis['outlier_frac']:.2%})")
        else:
            reasons.append("StandardScaler (no significant outliers)")
        if analysis["needs_log"]:
            reasons.append(f"Log transform suggested (skewness={analysis['skewness']:.2f})")
        if analysis["missing_pct"] > 0:
            reasons.append(f"Median imputation (missing={analysis['missing_pct']:.1%})")
        report["decisions"].append({"column": col, "type": "numeric", "actions": reasons})

    for col in col_types.get("categorical", []):
        if col == target_col or col not in feature_cols:
            continue
        analysis = analyze_categorical_column(df[col])
        report["categorical"][col] = analysis
        enc = "OneHotEncoding" if analysis["encoding"] == "onehot" else "OrdinalEncoding"
        reasons = [f"{enc} (cardinality={analysis['cardinality']})"]
        if analysis["missing_pct"] > 0:
            reasons.append(f"Mode imputation (missing={analysis['missing_pct']:.1%})")
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
        # Store original column names so get_feature_names_out works
        if hasattr(X, "columns"):
            self._col_names = list(X.columns)
        else:
            self._col_names = [f"dt_col_{i}" for i in range(X.shape[1] if hasattr(X, "shape") else 1)]
        return self

    def transform(self, X):
        # Normalise to 2-D numpy array; handle DataFrame and ndarray
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
            # Convert to pandas Series of datetime64
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
    """
    transformers = []

    # ── Numeric ──
    numeric_standard, numeric_robust = [], []
    for col, analysis in report["numeric"].items():
        if col not in X.columns:
            continue
        if analysis["scaler"] == "robust":
            numeric_robust.append(col)
        else:
            numeric_standard.append(col)

    # Keep fast engineered numeric columns, including WOE/log/bin/interactions.
    # The original report is built before feature engineering, so these columns
    # need to be picked up here when the preprocessor is rebuilt for training.
    known_cols = set(numeric_standard + numeric_robust)
    known_cols.update(report.get("categorical", {}).keys())
    known_cols.update(col_types.get("boolean", []))
    known_cols.update(col_types.get("datetime", []))
    extra_numeric = [
        c for c in X.columns
        if c not in known_cols and pd.api.types.is_numeric_dtype(X[c])
    ]
    numeric_standard.extend(extra_numeric)

    if numeric_standard:
        transformers.append(("num_standard", Pipeline([
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
        ]), numeric_standard))

    if numeric_robust:
        transformers.append(("num_robust", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]), numeric_robust))

    # ── Categorical ──
    cat_onehot, cat_ordinal = [], []
    for col, analysis in report["categorical"].items():
        if col not in X.columns:
            continue
        if analysis["encoding"] == "onehot":
            cat_onehot.append(col)
        else:
            cat_ordinal.append(col)

    if cat_onehot:
        transformers.append(("cat_onehot", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_onehot))

    if cat_ordinal:
        transformers.append(("cat_ordinal", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), cat_ordinal))

    # ── Boolean ──
    bool_cols = [c for c in col_types.get("boolean", []) if c != target_col and c in X.columns]
    if bool_cols:
        transformers.append(("bool_cols", BooleanToIntTransformer(), bool_cols))

    # ── Datetime ──
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
            # sklearn ≥1.0 — get_feature_names_out on the last step of a Pipeline
            if hasattr(transformer, "get_feature_names_out"):
                out = transformer.get_feature_names_out(cols if isinstance(cols, list) else list(cols))
                names.extend([str(n) for n in out])
            elif hasattr(transformer, "named_steps"):
                # It's a Pipeline — get names from its last step
                last_step = list(transformer.named_steps.values())[-1]
                if hasattr(last_step, "get_feature_names_out"):
                    input_for_last = cols if isinstance(cols, list) else list(cols)
                    out = last_step.get_feature_names_out(input_for_last)
                    # Clean sklearn OHE prefix like "encoder__col_val" → "col_val"
                    cleaned = []
                    for n in out:
                        n = str(n)
                        # OHE produces names like "col_value"; keep as-is, already readable
                        cleaned.append(n)
                    names.extend(cleaned)
                else:
                    # Fallback: use input column names
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
    "dpd", "dayspastdue",               # days-past-due: definitional leakage (dpd≥90 ≡ default)
    "origpd", "originationpd", "pdorig", "pdatorigination",
    "pdorigination", "initialpd", "basepd", "originalpd", "pdinitial",
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

    # Drop ECL-only columns (dpd, orig_pd) — they must never enter the feature matrix
    _ecl_cols = _find_ecl_only_cols([c for c in df.columns if c != target_col])
    df = df.drop(columns=_ecl_cols, errors="ignore")

    before = len(df)
    df = df.drop_duplicates()
    after = len(df)

    y = df[target_col].copy()
    X = df.drop(columns=[target_col])

    return X, y, {"duplicates_removed": before - after, "ecl_only_cols_dropped": _ecl_cols}


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

    # Drop ID columns
    id_cols = col_types.get("id", [])
    df = df.drop(columns=[c for c in id_cols if c in df.columns], errors="ignore")

    # Drop ECL-only columns (dpd, orig_pd) — they must never enter the feature matrix
    _ecl_cols = _find_ecl_only_cols([c for c in df.columns if c != target_col])
    df = df.drop(columns=_ecl_cols, errors="ignore")

    before = len(df)
    df = df.drop_duplicates()
    after = len(df)

    y = df[target_col].copy()
    X = df.drop(columns=[target_col])

    report = build_preprocessing_report(X.assign(**{target_col: y}), col_types, target_col)

    # Build an UNFITTED preprocessor on X (will be rebuilt later on X_engineered)
    preprocessor = build_preprocessing_pipeline(X, col_types, target_col, report)

    report["duplicates_removed"] = before - after
    # Placeholder — real names come after fitting on X_engineered
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
