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

from preprocessing import (
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
) -> Tuple[Any, Dict[str, Any], List[str]]:
    """
    1. Rebuild a fresh preprocessor scoped to X_train's columns.
    2. Wrap in a standard sklearn Pipeline.
    3. Fit and return (pipeline, info, real_feature_names).
    """
    training_info = {}
    start_time = time.time()

    training_info["preprocessing_method"] = "standard"

    preprocessor = rebuild_preprocessor_for(X_train, col_types, target_col, prep_report)

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model", model),
    ])

    # ── Hyperparameter search ──
    if use_hyperopt and param_grid:
        scoring = "roc_auc" if task_type == "binary" else "accuracy"
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42) if task_type == "binary" else 3
        search = RandomizedSearchCV(
            pipeline, param_distributions=param_grid,
            n_iter=8, cv=cv, scoring=scoring,
            random_state=42, n_jobs=-1, verbose=0,
        )
        search.fit(X_train, y_train)
        fitted_pipeline = search.best_estimator_
        training_info["best_params"] = {k.replace("model__", ""): v for k, v in search.best_params_.items()}
        training_info["cv_best_score"] = round(search.best_score_, 4)
    else:
        pipeline.fit(X_train, y_train)
        fitted_pipeline = pipeline
        training_info["best_params"] = {}

    training_info["training_time_s"] = round(time.time() - start_time, 2)

    # ── Optional CV ──
    if use_cv:
        try:
            scoring = "roc_auc" if task_type == "binary" else "accuracy"
            cv_scores = cross_val_score(
                fitted_pipeline, X_train, y_train,
                cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42),
                scoring=scoring, n_jobs=-1,
            )
            training_info["cv_scores"] = cv_scores.tolist()
            training_info["cv_mean"] = round(cv_scores.mean(), 4)
            training_info["cv_std"] = round(cv_scores.std(), 4)
        except Exception as e:
            training_info["cv_error"] = str(e)

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
