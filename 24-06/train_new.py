"""
train.py - Model Training Engine

FIX v2:
  - Preprocessor is REBUILT on X_engineered so columns always match
  - Real feature names resolved after fitting

FIX v4 (Optimal Binning removed):
  - The Optimal-Binning / WOE preprocessing path for Logistic Regression has
    been removed entirely. Every model — including Logistic Regression — now
    goes through the standard rebuild_preprocessor_for() ColumnTransformer
    path, same as tree models always have.

FIX v5 (Out-of-Time validation added — ported from Credit-Risk-Poc-main):
  - Added automatic Out-of-Time (OOT) validation:
      1. If an origination/observation date series is supplied and OOT is
         requested, the most recent slice of the data (by that date) is
         carved off as an untouched OOT holdout. Rows with an unparseable
         date are treated as development data, never OOT.
      2. Stratified K-Fold CV (when enabled) runs ONLY on the remaining
         development data — the OOT rows never participate in fold
         training or fold scoring.
      3. The final model is fit on ALL development data (i.e. everything
         except the OOT holdout).
      4. The fitted model is scored exactly once against the OOT holdout —
         never re-fit, never re-tuned against it — and OOT ROC-AUC / Gini
         are reported back in `training_info["oot"]`.
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional

from sklearn.model_selection import (
    train_test_split, StratifiedKFold,
    RandomizedSearchCV, cross_val_score
)
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.metrics import roc_auc_score

from preprocessing_new import (
    rebuild_preprocessor_for,
    get_feature_names_from_fitted_preprocessor,
)


def split_data(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.15,
    val_size: float = 0.15,
    task_type: str = "binary",
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    stratify = y if task_type in ("binary", "multiclass") else None

    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=test_size, stratify=stratify, random_state=random_state
    )
    adjusted_val = val_size / (1 - test_size)
    stratify_val = y_train_val if task_type in ("binary", "multiclass") else None

    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=adjusted_val,
        stratify=stratify_val, random_state=random_state
    )
    return X_train, X_val, X_test, y_train, y_val, y_test


def compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test) -> Dict[str, Any]:
    total = len(y_train) + len(y_val) + len(y_test)
    stats = {
        "total": total,
        "train_n": len(y_train), "val_n": len(y_val), "test_n": len(y_test),
        "train_pct": len(y_train) / total,
        "val_pct": len(y_val) / total,
        "test_pct": len(y_test) / total,
    }
    for split_name, y_split in [("train", y_train), ("val", y_val), ("test", y_test)]:
        if y_split.nunique() <= 10:
            stats[f"{split_name}_class_dist"] = y_split.value_counts(normalize=True).to_dict()
    return stats


# ─────────────────────────────────────────────
# Out-of-Time (OOT) holdout
# ─────────────────────────────────────────────

def determine_oot_window_size(
    n_total: int,
    target_frac: float = 0.15,
    min_frac: float = 0.10,
    max_frac: float = 0.20,
    min_n: int = 100,
) -> int:
    """
    Decide how many of the most-recent (chronologically last) observations to
    reserve as the Out-of-Time (OOT) holdout.

    OOT is only useful if it holds enough events to give a stable Gini /
    ROC-AUC estimate, but taking too much recent history starves the
    development set that K-Fold CV and the final model train on. We target
    ~15% of dated observations, clamped to 10%-20% of the total, and never
    let it dip below `min_n` absolute rows — below that, an OOT AUC estimate
    is mostly noise. On very small datasets we cap OOT at half the sample so
    development is never starved.
    """
    if n_total <= 0:
        return 0
    target_n = int(round(n_total * target_frac))
    lo = max(int(round(n_total * min_frac)), min_n)
    hi = int(round(n_total * max_frac))
    if hi < lo:
        oot_n = min(lo, n_total // 2)
    else:
        oot_n = min(max(target_n, lo), hi)
    return max(1, min(oot_n, n_total - 1)) if n_total > 1 else 0


def split_development_oot(
    X: pd.DataFrame,
    y: pd.Series,
    dates: pd.Series,
    min_dated_rows: int = 50,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, Dict[str, Any]]:
    """
    Chronologically reserve the most recent slice of `X`/`y` (aligned via
    `dates`, indexed the same as X) as an Out-of-Time (OOT) holdout. Everything
    else is "development" data — the only data K-Fold CV and the final fit
    ever see.

    Rows whose date failed to parse are always kept in development (an OOT
    holdout needs a trustworthy date to mean anything).

    Returns (X_dev, X_oot, y_dev, y_oot, info). If there aren't enough dated
    rows to build a trustworthy OOT window, X_oot/y_oot are empty and
    info["oot_available"] is False — callers should fall back to training on
    all of X/y.
    """
    dates = pd.to_datetime(pd.Series(dates).reindex(X.index), errors="coerce")
    valid = dates.notna()

    info: Dict[str, Any] = {
        "oot_available": False,
        "oot_n": 0,
        "dev_n": int(len(X)),
        "cutoff_date": None,
        "n_dated_rows": int(valid.sum()),
    }

    if valid.sum() < min_dated_rows:
        info["oot_reason"] = (
            f"Only {int(valid.sum())} rows have a parseable date "
            f"(need at least {min_dated_rows}) — OOT holdout skipped."
        )
        return X, X.iloc[0:0], y, y.iloc[0:0], info

    oot_n = determine_oot_window_size(int(valid.sum()))
    if oot_n < 1:
        info["oot_reason"] = "Not enough dated observations to reserve an OOT window."
        return X, X.iloc[0:0], y, y.iloc[0:0], info

    ordered_dates = dates[valid].sort_values()
    cutoff = ordered_dates.iloc[-oot_n]

    oot_mask = valid & (dates >= cutoff)
    dev_mask = ~oot_mask

    X_dev, X_oot = X.loc[dev_mask], X.loc[oot_mask]
    y_dev, y_oot = y.loc[dev_mask], y.loc[oot_mask]

    info.update({
        "oot_available": True,
        "oot_n": int(oot_mask.sum()),
        "dev_n": int(dev_mask.sum()),
        "cutoff_date": str(cutoff.date()) if hasattr(cutoff, "date") else str(cutoff),
    })
    return X_dev, X_oot, y_dev, y_oot, info


def _evaluate_oot(fitted_pipeline, X_oot: pd.DataFrame, y_oot: pd.Series, task_type: str) -> Dict[str, Any]:
    """Score the already-fitted pipeline against the OOT holdout exactly once.
    Never re-fits, never re-tunes — this is a pure evaluation pass."""
    result: Dict[str, Any] = {"oot_n_eval": int(len(X_oot))}
    if X_oot is None or len(X_oot) == 0:
        return result

    try:
        if task_type == "binary" and hasattr(fitted_pipeline, "predict_proba") and y_oot.nunique() > 1:
            y_proba_oot = fitted_pipeline.predict_proba(X_oot)
            scores = np.asarray(y_proba_oot)
            scores = scores[:, 1] if scores.ndim == 2 else scores
            oot_auc = roc_auc_score(y_oot, scores)
            result["oot_roc_auc"] = round(float(oot_auc), 4)
            result["oot_gini"] = round(float(2 * oot_auc - 1), 4)
        elif task_type == "binary" and y_oot.nunique() <= 1:
            result["oot_eval_note"] = "OOT holdout contains a single class — ROC-AUC/Gini undefined."
    except Exception as e:
        result["oot_eval_error"] = str(e)
    return result


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    col_types: Dict[str, List[str]],          # ← passed so we can rebuild preprocessor
    target_col: str,
    prep_report: Dict[str, Any],
    model,
    use_smote: bool = False,
    use_cv: bool = False,
    cv_folds: int = 5,
    use_hyperopt: bool = False,
    param_grid: Dict = None,
    task_type: str = "binary",
    model_name: Optional[str] = None,
    dates_train: Optional[pd.Series] = None,
    use_oot: bool = False,
) -> Tuple[Any, Dict[str, Any], List[str]]:
    """
    1. If `use_oot` and `dates_train` is provided, carve off the most recent
       slice of X_train/y_train (chronologically) as an untouched OOT holdout.
       Everything else becomes "development" data.
    2. Rebuild a fresh preprocessor scoped to the development data's columns
       and wrap in a standard sklearn Pipeline (same ColumnTransformer path
       for every model — no per-model routing).
    3. Stratified K-Fold CV (if enabled) runs only on development data.
    4. Fit the final pipeline on ALL development data.
    5. If an OOT holdout was carved off, score the fitted pipeline against it
       exactly once (never re-fit/re-tuned) and report OOT ROC-AUC / Gini.

    `model_name` is accepted for compatibility/logging but no longer changes
    which preprocessing path is used — every model uses the same one.

    `dates_train`: a date-like Series indexed the same as X_train (e.g. the
    loan origination date). Required for OOT; ignored if `use_oot=False`.
    """
    training_info: Dict[str, Any] = {"preprocessing_method": "standard"}
    start_time = time.time()

    # ── Carve off OOT holdout (if requested) ──
    oot_info: Dict[str, Any] = {"oot_available": False}
    X_oot, y_oot = None, None
    X_dev, y_dev = X_train, y_train

    if use_oot:
        if dates_train is None:
            oot_info = {
                "oot_available": False,
                "oot_reason": "No origination/observation date column was available.",
            }
        else:
            X_dev, X_oot, y_dev, y_oot, oot_info = split_development_oot(X_train, y_train, dates_train)

    training_info["oot"] = oot_info

    # ── Preprocessing — identical path for every model ──
    preprocessor = rebuild_preprocessor_for(X_dev, col_types, target_col, prep_report)

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model", model),
    ])

    # ── Hyperparameter search (development data only) ──
    if use_hyperopt and param_grid:
        scoring = "roc_auc" if task_type == "binary" else "accuracy"
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42) if task_type == "binary" else 3
        search = RandomizedSearchCV(
            pipeline, param_distributions=param_grid,
            n_iter=8, cv=cv, scoring=scoring,
            random_state=42, n_jobs=-1, verbose=0,
        )
        search.fit(X_dev, y_dev)
        fitted_pipeline = search.best_estimator_
        training_info["best_params"] = {k.replace("model__", ""): v for k, v in search.best_params_.items()}
        training_info["cv_best_score"] = round(search.best_score_, 4)
    else:
        pipeline.fit(X_dev, y_dev)
        fitted_pipeline = pipeline
        training_info["best_params"] = {}

    training_info["training_time_s"] = round(time.time() - start_time, 2)

    # ── Optional Stratified K-Fold CV — development data only ──
    if use_cv:
        try:
            scoring = "roc_auc" if task_type == "binary" else "accuracy"
            cv_scores = cross_val_score(
                fitted_pipeline, X_dev, y_dev,
                cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42),
                scoring=scoring, n_jobs=-1,
            )
            training_info["cv_scores"] = cv_scores.tolist()
            training_info["cv_mean"] = round(cv_scores.mean(), 4)
            training_info["cv_std"] = round(cv_scores.std(), 4)
        except Exception as e:
            training_info["cv_error"] = str(e)

    # ── One-shot OOT evaluation — never re-fit, never re-tuned ──
    if oot_info.get("oot_available") and X_oot is not None and len(X_oot):
        training_info["oot"].update(_evaluate_oot(fitted_pipeline, X_oot, y_oot, task_type))

    # ── Extract real feature names ──
    # ColumnTransformer needs the dedicated name-resolution helper (handles
    # OHE expansion, datetime decomposition, etc.).
    try:
        fitted_prep = fitted_pipeline.named_steps.get("preprocessor")
        if fitted_prep is None:
            for _, step in fitted_pipeline.steps:
                if hasattr(step, "transformers_") or hasattr(step, "get_feature_names_out"):
                    fitted_prep = step
                    break
        if fitted_prep is not None and hasattr(fitted_prep, "transformers_"):
            real_names = get_feature_names_from_fitted_preprocessor(fitted_prep)
        elif fitted_prep is not None and hasattr(fitted_prep, "get_feature_names_out"):
            real_names = list(fitted_prep.get_feature_names_out())
        else:
            real_names = []
    except Exception:
        real_names = []

    return fitted_pipeline, training_info, real_names
