"""
lgd_engine.py — LGD (Loss Given Default) modelling engine.

Mirrors the PD ML pipeline (split → preprocess → fit → evaluate → predict) but
for a REGRESSION target: realized LGD on a training set of loans that have
DEFAULTED. The model is then used to predict LGD for the live portfolio, and the
predictions feed the ECL calculation in place of a fixed LGD assumption.

Design parallels to the PD pipeline:
  • model registry          -> REGRESSION_MODELS (model_selector), extended here
  • train/validation/test    -> split_data() from train.py (task_type='regression')
  • preprocessing            -> ColumnTransformer (numeric impute+scale,
                                categorical impute+one-hot), the regression
                                analogue of the PD preprocessing step
  • macro / forward-looking  -> FRED features (GDP, unemployment, interest rate)
                                aligned POINT-IN-TIME to each loan's relevant date

The LGD target is realized loss severity in [0, 1], derived from whichever of
these the user's defaulted-loan dataset provides:
  • an explicit realized-LGD column, or
  • a recovery-rate column         -> lgd = 1 - recovery_rate, or
  • recovery amount + exposure     -> lgd = (exposure - recovery) / exposure
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

from train import split_data  # reuse the PD pipeline's splitter (regression mode)

try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except Exception:  # pragma: no cover
    _HAS_XGB = False
try:
    from lightgbm import LGBMRegressor
    _HAS_LGBM = True
except Exception:  # pragma: no cover
    _HAS_LGBM = False


# ── Model registry (regression analogue of CLASSIFICATION_MODELS) ─────────────
LGD_MODELS: Dict[str, Dict[str, Any]] = {
    "Linear Regression": {
        "class": LinearRegression, "default_params": {}, "icon": "📈",
        "description": "Ordinary least squares. Fast, interpretable baseline.",
    },
    "Ridge Regression": {
        "class": Ridge, "default_params": {"alpha": 1.0}, "icon": "📉",
        "description": "L2-regularised linear regression. Stable with correlated features.",
    },
    "Random Forest": {
        "class": RandomForestRegressor,
        "default_params": {"n_estimators": 300, "random_state": 42, "n_jobs": -1},
        "icon": "🌲",
        "description": "Ensemble of regression trees. Captures non-linear recovery patterns.",
    },
    "Gradient Boosting": {
        "class": GradientBoostingRegressor,
        "default_params": {"n_estimators": 300, "learning_rate": 0.05,
                            "max_depth": 3, "random_state": 42},
        "icon": "📊",
        "description": "Sequential boosting. Strong accuracy on structured credit data.",
    },
}
if _HAS_XGB:
    LGD_MODELS["XGBoost"] = {
        "class": XGBRegressor,
        "default_params": {"n_estimators": 300, "learning_rate": 0.05, "max_depth": 4,
                           "subsample": 0.9, "random_state": 42, "verbosity": 0},
        "icon": "⚡",
        "description": "Gradient boosting framework. State-of-the-art for tabular LGD.",
    }
if _HAS_LGBM:
    LGD_MODELS["LightGBM"] = {
        "class": LGBMRegressor,
        "default_params": {"n_estimators": 300, "learning_rate": 0.05, "num_leaves": 31,
                           "random_state": 42, "verbose": -1},
        "icon": "💡",
        "description": "Leaf-wise gradient boosting. Fast on large default histories.",
    }


def available_models() -> List[str]:
    return list(LGD_MODELS.keys())


# ── Column auto-detection (mirrors the detect_* helpers in ecl_engine) ────────
_LGD_CANDIDATES = ["lgd", "loss_given_default", "loss_severity", "realized_lgd"]
_RECOVERY_RATE_CANDIDATES = ["recovery_rate", "recoveryrate", "recovery_pct", "recovery_percentage"]
_RECOVERY_AMOUNT_CANDIDATES = ["recovery_amount", "recovery_amt", "recovery", "recovered_amount"]
_EXPOSURE_CANDIDATES = ["exposure", "ead", "exposure_at_default", "outstanding_balance",
                        "outstanding_principal", "loan_amount"]
_DEFAULT_FLAG_CANDIDATES = ["default", "is_default", "defaulted", "default_flag", "in_default"]


def _detect(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    lower = {c.lower().replace(" ", "_"): c for c in df.columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    for cand in candidates:
        for key, col in lower.items():
            if cand in key:
                return col
    return None


def detect_lgd_target(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Best-effort, name-based auto-detection of the realized-LGD target inputs, in
    priority order: explicit LGD column -> recovery rate -> recovery amount +
    exposure. Returns a dict of the column names found (None where absent) so the
    caller (UI or pipeline) doesn't need to ask the user to pick them.
    """
    lgd_col = _detect(df, _LGD_CANDIDATES)
    rr_col = _detect(df, _RECOVERY_RATE_CANDIDATES) if not lgd_col else None
    rec_col = exp_col = None
    if not lgd_col and not rr_col:
        rec_col = _detect(df, _RECOVERY_AMOUNT_CANDIDATES)
        if rec_col:
            exp_col = _detect(df, [c for c in _EXPOSURE_CANDIDATES])
    return {
        "lgd_col": lgd_col, "recovery_rate_col": rr_col,
        "recovery_amount_col": rec_col, "exposure_col": exp_col,
    }


def detect_default_flag(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, _DEFAULT_FLAG_CANDIDATES)


# ── LGD target derivation ─────────────────────────────────────────────────────
def derive_lgd_target(
    df: pd.DataFrame,
    lgd_col: Optional[str] = None,
    recovery_rate_col: Optional[str] = None,
    recovery_amount_col: Optional[str] = None,
    exposure_col: Optional[str] = None,
    floor: float = 0.0,
    cap: float = 1.0,
) -> pd.Series:
    """
    Build the realized-LGD target (clipped to [floor, cap]) from whichever inputs
    are available, in priority order: explicit LGD → 1-recovery_rate →
    (exposure-recovery)/exposure.
    """
    idx = df.index
    if lgd_col and lgd_col in df.columns:
        lgd = pd.to_numeric(df[lgd_col], errors="coerce")
    elif recovery_rate_col and recovery_rate_col in df.columns:
        rr = pd.to_numeric(df[recovery_rate_col], errors="coerce")
        if rr.dropna().gt(1.0).mean() > 0.5:          # looks like a percentage
            rr = rr / 100.0
        lgd = 1.0 - rr
    elif recovery_amount_col and exposure_col and \
            recovery_amount_col in df.columns and exposure_col in df.columns:
        rec = pd.to_numeric(df[recovery_amount_col], errors="coerce")
        exp = pd.to_numeric(df[exposure_col], errors="coerce").replace(0, np.nan)
        lgd = (exp - rec) / exp
    else:
        raise ValueError(
            "Cannot derive LGD target. Provide one of: lgd_col, recovery_rate_col, "
            "or (recovery_amount_col AND exposure_col)."
        )
    return lgd.clip(lower=floor, upper=cap).reindex(idx).rename("lgd_target")


def filter_defaulted_by_target(df: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """
    Return only the rows of `df` that defaulted, using the same binary target
    (1 = default) the PD model was trained on. This is the training population
    for the LGD model — it is derived automatically from the uploaded dataset's
    PD target rather than asking the user to pick a default flag.
    """
    y_aligned = pd.to_numeric(y, errors="coerce").reindex(df.index)
    mask = y_aligned.fillna(0) > 0
    return df[mask]


def auto_feature_cols(
    df: pd.DataFrame,
    exclude: Optional[List[str]] = None,
    max_features: int = 25,
) -> List[str]:
    """
    Automatically select predictor columns for the LGD model: every column except
    the ones used to derive the target / training population / macro, plus
    obvious identifier columns. Keeps the LGD workflow free of manual column
    picking beyond the FRED date column.
    """
    exclude = set(c for c in (exclude or []) if c)
    id_like = {c for c in df.columns if c.lower() in
               ("loan_id", "customer_id", "id", "index")}
    cols = [c for c in df.columns if c not in exclude and c not in id_like]
    return cols[:max_features] if max_features else cols


def filter_defaulted(
    df: pd.DataFrame,
    default_flag_col: Optional[str] = None,
    default_values=(1, "1", "yes", "true", "default", "defaulted", "y", "t"),
) -> pd.DataFrame:
    """Return only rows that have defaulted (training population for LGD)."""
    if not default_flag_col or default_flag_col not in df.columns:
        return df  # caller already passed a defaulted-only frame
    col = df[default_flag_col]
    if pd.api.types.is_numeric_dtype(col):
        mask = pd.to_numeric(col, errors="coerce").fillna(0) > 0
    else:
        mask = col.astype(str).str.strip().str.lower().isin(
            {str(v).lower() for v in default_values}
        )
    return df[mask]


# ── Macro feature attachment (point-in-time via FRED) ─────────────────────────
def attach_macro(
    df: pd.DataFrame,
    fred_client=None,
    date_col: Optional[str] = None,
    macro_aligned: Optional[pd.DataFrame] = None,
) -> tuple[pd.DataFrame, List[str]]:
    """
    Append point-in-time macro columns. Either pass a pre-aligned `macro_aligned`
    frame (index matching df) OR a `fred_client` + `date_col` to align here.
    Returns (df_with_macro, macro_col_names).
    """
    if macro_aligned is not None and not macro_aligned.empty:
        macro = macro_aligned.reindex(df.index)
    elif fred_client is not None and date_col and date_col in df.columns:
        macro = fred_client.macro_features_for_dates(df[date_col])
        macro.index = df.index
    else:
        return df.copy(), []
    macro_cols = list(macro.columns)
    return pd.concat([df.copy(), macro], axis=1), macro_cols


# ── Preprocessor (regression analogue of the PD preprocessing step) ───────────
def _is_date_like(series: pd.Series, sample: int = 500, threshold: float = 0.7) -> bool:
    """Return True if `series` looks like a date column that should be treated as
    a numeric ordinal rather than a categorical string."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not pd.api.types.is_object_dtype(series):
        return False
    probe = series.dropna().astype(str).head(sample)
    if len(probe) == 0:
        return False
    parsed = 0
    for v in probe:
        try:
            pd.to_datetime(v, infer_datetime_format=True)
            parsed += 1
        except Exception:
            pass
    return (parsed / len(probe)) >= threshold


def _build_preprocessor(X: pd.DataFrame) -> tuple[ColumnTransformer, List[str], List[str], List[str]]:
    """
    Classify columns into four buckets:
      • numeric_cols     — already numeric → impute + scale
      • date_cols        — datetime or parseable date strings → convert to days-since-epoch, then scale
      • categorical_cols — low-cardinality strings (nunique ≤ 30) → impute + OHE
      • dropped_cols     — high-cardinality strings or anything else → dropped silently

    Returns (ColumnTransformer, numeric_cols, date_cols, categorical_cols).
    The fourth return value replaces the old categorical_cols so callers that
    unpack three values still work with a small update.
    """
    MAX_CAT_CARDINALITY = 30  # OHE only when ≤ this many distinct values

    numeric_cols, date_cols, categorical_cols = [], [], []
    for c in X.columns:
        s = X[c]
        if pd.api.types.is_numeric_dtype(s):
            numeric_cols.append(c)
        elif _is_date_like(s):
            date_cols.append(c)
        elif s.nunique() <= MAX_CAT_CARDINALITY:
            categorical_cols.append(c)
        # else: high-cardinality string → silently dropped (remainder="drop")

    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    # Dates: convert to days-since-epoch (a single numeric per row), then scale.
    date_pipe = Pipeline([
        ("to_ordinal", FunctionTransformer(
            lambda df: pd.DataFrame(
                {c: pd.to_datetime(df[c], errors="coerce").map(
                    lambda x: float(x.toordinal()) if pd.notna(x) else np.nan
                ) for c in df.columns},
                index=df.index,
            ) if hasattr(df, "columns") else df,
            validate=False,
        )),
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    transformers = []
    if numeric_cols:
        transformers.append(("num", numeric_pipe, numeric_cols))
    if date_cols:
        transformers.append(("date", date_pipe, date_cols))
    if categorical_cols:
        transformers.append(("cat", categorical_pipe, categorical_cols))

    pre = ColumnTransformer(transformers, remainder="drop")
    return pre, numeric_cols, date_cols, categorical_cols


def _feature_importances(fitted: Pipeline, numeric_cols, date_cols, categorical_cols) -> List[Dict[str, Any]]:
    """Extract feature importance / coefficients and map them back to ORIGINAL
    column names. OHE dummies are aggregated (summed) to their parent column so
    the importance chart always shows one bar per input feature."""
    try:
        pre = fitted.named_steps["preprocessor"]
        # Build a mapping: transformed_col_index → original_col_name
        importance_by_col: Dict[str, float] = {}

        for t_name, _, _ in pre.transformers_:
            if t_name not in pre.named_transformers_:
                continue
        model = fitted.named_steps["model"]
        if hasattr(model, "feature_importances_"):
            vals = np.asarray(model.feature_importances_, dtype=float)
        elif hasattr(model, "coef_"):
            vals = np.abs(np.asarray(model.coef_, dtype=float).ravel())
        else:
            return []

        # Walk the ColumnTransformer in order to map each position → source column.
        idx = 0
        for t_name, t_step, t_cols in pre.transformers_:
            if t_name == "num":
                for col in t_cols:
                    if idx < len(vals):
                        importance_by_col[col] = importance_by_col.get(col, 0.0) + float(vals[idx])
                    idx += 1
            elif t_name == "date":
                for col in t_cols:
                    if idx < len(vals):
                        importance_by_col[col] = importance_by_col.get(col, 0.0) + float(vals[idx])
                    idx += 1
            elif t_name == "cat":
                ohe = t_step.named_steps["onehot"]
                feature_names = ohe.get_feature_names_out(t_cols)
                # Map each OHE dummy back to its source column and SUM importances.
                for i, fname in enumerate(feature_names):
                    if idx + i >= len(vals):
                        break
                    # sklearn names dummies as "col_value"; find the matching source col
                    source = next(
                        (c for c in t_cols if fname == f"{c}_{fname[len(c)+1:]}" and fname.startswith(c + "_")),
                        t_cols[0],  # fallback: attribute to first col (shouldn't happen)
                    )
                    importance_by_col[source] = importance_by_col.get(source, 0.0) + float(vals[idx + i])
                idx += len(feature_names)

        pairs = sorted(importance_by_col.items(), key=lambda x: x[1], reverse=True)
        return [{"feature": f, "importance": round(float(v), 5)} for f, v in pairs[:20]]
    except Exception:
        return []


# ── Train ─────────────────────────────────────────────────────────────────────
def train_lgd_model(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    target: pd.Series,
    model_name: str,
    macro_cols: Optional[List[str]] = None,
    test_size: float = 0.20,
    val_size: float = 0.0,
    random_state: int = 42,
    lgd_floor: float = 0.0,
    lgd_cap: float = 1.0,
    model_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fit an LGD regression model on defaulted-loan data.

    train_df      : defaulted-loan frame (already filtered) with feature + macro cols
    feature_cols  : user-selected predictor columns (excluding macro)
    target        : realized LGD Series (from derive_lgd_target), aligned to train_df
    model_name    : key in LGD_MODELS
    macro_cols    : macro feature columns to include (from attach_macro)

    Returns a bundle dict consumed by predict_lgd() and the UI.
    """
    if model_name not in LGD_MODELS:
        raise ValueError(f"Unknown LGD model '{model_name}'. Options: {available_models()}")

    macro_cols = macro_cols or []
    all_features = [c for c in (feature_cols + macro_cols) if c in train_df.columns]
    X = train_df[all_features].copy()
    y = pd.to_numeric(target.reindex(train_df.index), errors="coerce")

    keep = y.notna()
    X, y = X[keep], y[keep]
    if len(X) < 10:
        raise ValueError(f"Only {len(X)} usable defaulted rows with an LGD target — need ≥ 10 to train.")

    # Split exactly like the PD pipeline, in regression mode (no stratification).
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=max(val_size, 1e-6),
        task_type="regression", random_state=random_state,
    )

    pre, numeric_cols, date_cols, categorical_cols = _build_preprocessor(X)
    spec = LGD_MODELS[model_name]
    params = dict(spec["default_params"])
    if model_params:
        params.update(model_params)
    model = spec["class"](**params)

    pipe = Pipeline([("preprocessor", pre), ("model", model)])
    pipe.fit(X_train, y_train)

    def _metrics(Xs, ys) -> Dict[str, float]:
        if len(Xs) < 2:
            return {}
        pred = np.clip(pipe.predict(Xs), lgd_floor, lgd_cap)
        return {
            "r2":   round(float(r2_score(ys, pred)), 4),
            "mae":  round(float(mean_absolute_error(ys, pred)), 4),
            "rmse": round(float(np.sqrt(mean_squared_error(ys, pred))), 4),
            "n":    int(len(ys)),
        }

    metrics = {
        "train": _metrics(X_train, y_train),
        "validation": _metrics(X_val, y_val),
        "test": _metrics(X_test, y_test),
        "target_mean": round(float(y.mean()), 4),
        "target_std": round(float(y.std()), 4),
    }

    # Capture predictions vs actuals on train/test for the Evaluation sub-tab.
    _p_train = np.clip(pipe.predict(X_train), lgd_floor, lgd_cap)
    _p_test = np.clip(pipe.predict(X_test), lgd_floor, lgd_cap)
    eval_data = {
        "y_train": [float(v) for v in y_train],
        "pred_train": [float(v) for v in _p_train],
        "y_test": [float(v) for v in y_test],
        "pred_test": [float(v) for v in _p_test],
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "test_size": round(float(len(X_test) / max(len(X), 1)), 3),
    }

    return {
        "model": pipe,
        "model_name": model_name,
        "feature_cols": [c for c in feature_cols if c in train_df.columns],
        "macro_cols": macro_cols,
        "all_features": all_features,
        "numeric_cols": numeric_cols,
        "date_cols": date_cols,
        "categorical_cols": categorical_cols,
        "lgd_floor": float(lgd_floor),
        "lgd_cap": float(lgd_cap),
        "metrics": metrics,
        "eval": eval_data,
        "importances": _feature_importances(pipe, numeric_cols, date_cols, categorical_cols),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
    }


# ── LGD feature engineering (indexed LTV via HPI + feature selection) ─────────
HPI_SERIES_DEFAULT = "CSUSHPINSA"  # S&P/Case-Shiller U.S. National Home Price Index (monthly)


def detect_ltv_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, ["ltv", "loan_to_value", "ltv_ratio", "original_ltv",
                        "ltv_origination", "ltv_at_origination"])


def detect_origination_date_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, ["origination_date", "orig_date", "disbursement_date",
                        "start_date", "loan_date", "open_date", "sanction_date"])


def detect_product_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, ["product_type", "product", "loan_type", "facility_type", "asset_class"])


def home_loan_mask(
    df: pd.DataFrame,
    product_col: Optional[str],
    home_values=("home", "mortgage", "housing", "residential", "hl", "house"),
) -> pd.Series:
    """Boolean mask of home/mortgage loans. If no product column, assume all rows
    are home loans (the user opted to index LTV, so treat the book as mortgages)."""
    if not product_col or product_col not in df.columns:
        return pd.Series(True, index=df.index)
    low = df[product_col].astype(str).str.strip().str.lower()
    return low.apply(lambda x: any(h in x for h in home_values))


def index_ltv_with_hpi(
    df: pd.DataFrame,
    ltv_col: str,
    orig_date_col: str,
    fred_client,
    hpi_series: str = HPI_SERIES_DEFAULT,
    current_date=None,
    product_col: Optional[str] = None,
) -> tuple[pd.Series, pd.Series, float]:
    """
    Indexed LTV = original LTV × HPI(origination) / HPI(current).

    Reflects collateral revaluation since origination (if house prices rose, the
    indexed LTV falls — more equity — and vice-versa). Applied to HOME loans only;
    other products keep their original LTV. Returns (indexed_ltv, is_home, hpi_now).
    """
    ltv = pd.to_numeric(df[ltv_col], errors="coerce")
    orig_dates = pd.to_datetime(df[orig_date_col], errors="coerce")
    hpi_orig = fred_client.series_as_of(hpi_series, orig_dates)
    hpi_orig.index = df.index
    if current_date is None:
        current_date = pd.Timestamp.today().normalize()
    hpi_now = fred_client.latest_value(hpi_series, on_or_before=current_date)
    indexed = ltv * (hpi_orig / hpi_now)

    is_home = home_loan_mask(df, product_col)
    result = ltv.where(~is_home, indexed)
    return result.rename("indexed_ltv"), is_home, float(hpi_now)


def lgd_correlation_report(df: pd.DataFrame, feature_cols: List[str],
                           threshold: float = 0.85) -> List[Dict[str, Any]]:
    """High-correlation numeric pairs among LGD features (candidates to drop)."""
    num = [c for c in feature_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if len(num) < 2:
        return []
    corr = df[num].corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    pairs = []
    for row in upper.index:
        for col in upper.columns:
            v = upper.loc[row, col]
            if pd.notna(v) and v >= threshold:
                pairs.append({"feature_1": row, "feature_2": col, "correlation": round(float(v), 4)})
    return sorted(pairs, key=lambda d: d["correlation"], reverse=True)


def lgd_low_variance(df: pd.DataFrame, feature_cols: List[str],
                     threshold: float = 1e-8) -> List[str]:
    """Near-constant numeric features (candidates to drop)."""
    out = []
    for c in feature_cols:
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            var = pd.to_numeric(df[c], errors="coerce").var(skipna=True)
            if pd.isna(var) or float(var) <= threshold:
                out.append(c)
    return out


# ── Predict ───────────────────────────────────────────────────────────────────
def predict_lgd(
    bundle: Dict[str, Any],
    df: pd.DataFrame,
    macro_aligned: Optional[pd.DataFrame] = None,
) -> pd.Series:
    """
    Predict LGD for a portfolio frame using a trained bundle. Missing feature
    columns are created as NaN (the pipeline's imputers handle them). Macro
    columns, if the model used them, must be supplied via `macro_aligned`
    (point-in-time aligned to df.index) or already present in df.
    """
    all_features = bundle["all_features"]
    work = df.copy()
    if macro_aligned is not None and not macro_aligned.empty:
        macro = macro_aligned.reindex(work.index)
        for c in macro.columns:
            work[c] = macro[c]
    for c in all_features:
        if c not in work.columns:
            work[c] = np.nan
    X = work[all_features]
    pred = bundle["model"].predict(X)
    pred = np.clip(pred, bundle.get("lgd_floor", 0.0), bundle.get("lgd_cap", 1.0))
    return pd.Series(pred, index=df.index, name="lgd")
