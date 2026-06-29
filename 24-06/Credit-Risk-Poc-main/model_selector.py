"""
model_selector.py - Smart Model Recommendation Engine
Recommends and instantiates models based on dataset characteristics.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple

from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, RandomForestRegressor
from sklearn.svm import SVC
from xgboost import XGBClassifier, XGBRegressor
from lightgbm import LGBMClassifier, LGBMRegressor


# ─────────────────────────────────────────────
# Model Registry
# ─────────────────────────────────────────────

CLASSIFICATION_MODELS = {
    "Logistic Regression": {
        "class": LogisticRegression,
        "default_params": {"max_iter": 1000, "C": 1.0, "solver": "lbfgs", "random_state": 42},
        "param_grid": {"C": [0.01, 0.1, 1.0, 10.0]},
        "description": "Fast, interpretable linear model. Good baseline for binary classification.",
        "best_for": ["small datasets", "linear relationships", "fast training"],
        "icon": "📈",
    },
    "Random Forest": {
        "class": RandomForestClassifier,
        "default_params": {"n_estimators": 200, "random_state": 42, "n_jobs": -1},
        "param_grid": {"n_estimators": [100, 200], "max_depth": [5, 10, None]},
        "description": "Ensemble of decision trees. Handles nonlinear relationships and mixed types well.",
        "best_for": ["mixed features", "nonlinear", "feature importance", "robust to outliers"],
        "icon": "🌲",
    },
    "XGBoost": {
        "class": XGBClassifier,
        "default_params": {
            "n_estimators": 200, "learning_rate": 0.05, "max_depth": 6,
            "use_label_encoder": False, "eval_metric": "logloss", "random_state": 42,
            "verbosity": 0,
        },
        "param_grid": {"n_estimators": [100, 200], "max_depth": [4, 6], "learning_rate": [0.05, 0.1]},
        "description": "Gradient boosting framework. State-of-the-art for tabular data with regularization.",
        "best_for": ["large datasets", "imbalanced data", "missing value handling", "high accuracy"],
        "icon": "⚡",
    },
    "LightGBM": {
        "class": LGBMClassifier,
        "default_params": {
            "n_estimators": 200, "learning_rate": 0.05, "num_leaves": 31,
            "random_state": 42, "verbose": -1,
        },
        "param_grid": {"n_estimators": [100, 200], "num_leaves": [20, 31, 50]},
        "description": "Faster gradient boosting using leaf-wise tree growth. Excellent for large datasets.",
        "best_for": ["very large datasets", "high dimensionality", "fast training"],
        "icon": "💡",
    },
    "Gradient Boosting": {
        "class": GradientBoostingClassifier,
        "default_params": {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 4, "random_state": 42},
        "param_grid": {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1]},
        "description": "Classic gradient boosting. Interpretable with good performance on structured data.",
        "best_for": ["medium datasets", "stability", "moderate dimensionality"],
        "icon": "📊",
    },
}

REGRESSION_MODELS = {
    "Linear Regression": {
        "class": Ridge,
        "default_params": {"alpha": 1.0},
        "description": "Regularized linear regression (Ridge). Fast and interpretable.",
        "icon": "📈",
    },
    "Random Forest Regressor": {
        "class": RandomForestRegressor,
        "default_params": {"n_estimators": 200, "random_state": 42, "n_jobs": -1},
        "description": "Ensemble regressor for nonlinear relationships.",
        "icon": "🌲",
    },
    "XGBoost Regressor": {
        "class": XGBRegressor,
        "default_params": {"n_estimators": 200, "learning_rate": 0.05, "random_state": 42, "verbosity": 0},
        "description": "Gradient boosting for regression. High accuracy on tabular data.",
        "icon": "⚡",
    },
}


# ─────────────────────────────────────────────
# Recommendation Engine
# ─────────────────────────────────────────────

def recommend_models(
    n_samples: int,
    n_features: int,
    class_imbalance_ratio: float,
    task_type: str = "binary",
) -> List[Dict[str, Any]]:
    """
    Recommend the top models and explain WHY each is recommended.
    Returns a list of recommendation dicts sorted by score.
    """
    recommendations = []

    if task_type in ("binary", "multiclass"):
        models = CLASSIFICATION_MODELS
    else:
        models = REGRESSION_MODELS
        # For regression, return all with equal priority
        return [
            {**info, "name": name, "score": 5, "why": info["description"]}
            for name, info in models.items()
        ]

    for name, info in models.items():
        score = 5
        reasons = []

        if name == "XGBoost":
            score += 2
            reasons.append("excellent default choice for tabular credit risk data")
            if class_imbalance_ratio > 3:
                score += 1
                reasons.append("handles class imbalance natively via scale_pos_weight")
            if n_samples > 1000:
                score += 1
                reasons.append("scales well to large sample sizes")

        elif name == "LightGBM":
            score += 1
            reasons.append("fast gradient boosting")
            if n_samples > 5000:
                score += 2
                reasons.append("highly efficient for large datasets")
            if n_features > 30:
                score += 1
                reasons.append("excels in high-dimensional feature spaces")

        elif name == "Random Forest":
            score += 1
            reasons.append("robust ensemble with natural feature importance")
            if class_imbalance_ratio > 3:
                score += 1
                reasons.append("class_weight='balanced' handles imbalance well")

        elif name == "Logistic Regression":
            if n_samples < 500:
                score += 2
                reasons.append("ideal for small datasets, avoids overfitting")
            if n_features < 20:
                score += 1
                reasons.append("good performance in low-dimensional spaces")
            reasons.append("highly interpretable — easy to explain to stakeholders")

        elif name == "Gradient Boosting":
            reasons.append("solid sequential boosting baseline")
            if 500 < n_samples < 10000:
                score += 1

        rec = {**info, "name": name, "score": score, "why": "; ".join(reasons) if reasons else info["description"]}
        recommendations.append(rec)

    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations


def get_model_instance(
    model_name: str,
    task_type: str,
    class_weight: str = None,
    scale_pos_weight: float = None,
) -> Any:
    """Instantiate and return a model object with appropriate parameters."""
    models = CLASSIFICATION_MODELS if task_type in ("binary", "multiclass") else REGRESSION_MODELS

    if model_name not in models:
        raise ValueError(f"Model '{model_name}' not found in registry.")

    info = models[model_name]
    params = info["default_params"].copy()

    # Inject class balancing if applicable
    if task_type == "binary":
        if model_name in ("Logistic Regression", "Random Forest", "Gradient Boosting") and class_weight:
            params["class_weight"] = class_weight
        if model_name == "XGBoost" and scale_pos_weight and scale_pos_weight > 1:
            params["scale_pos_weight"] = scale_pos_weight
        if model_name == "LightGBM" and class_weight:
            params["class_weight"] = class_weight

    return info["class"](**params)


def get_hyperparameter_grid(model_name: str, task_type: str) -> Dict[str, List]:
    """Return the hyperparameter grid for RandomizedSearchCV."""
    models = CLASSIFICATION_MODELS if task_type in ("binary", "multiclass") else {}
    info = models.get(model_name, {})
    grid = info.get("param_grid", {})
    return {f"model__{k}": v for k, v in grid.items()}
