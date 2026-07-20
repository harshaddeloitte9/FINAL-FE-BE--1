"""
model_selector.py - Weighted Model Recommendation Engine
Recommends a single best-fit model (plus instantiation helpers) based on
dataset characteristics measured during preprocessing / feature engineering.

Design
------
Instead of a fixed set of if/else heuristic bumps ("+2 if XGBoost and
n_samples > 1000"), every model is scored with the SAME weighted formula:

    score(model) = sum over characteristics c of:
        GLOBAL_WEIGHT[c] * MODEL_AFFINITY[model][c] * VALUE[c]

- VALUE[c] is the dataset's measurement for characteristic c, normalized to
  0-1 (e.g. "38% missing values" -> 0.38-ish after saturation).
- MODEL_AFFINITY[model][c] is how well that model tends to handle a HIGH
  value of that characteristic, in [-1, 1] (positive = model likes it,
  negative = model is hurt by it). This is the only place per-model
  "expertise" is encoded, and it's a coefficient, not a score.
- GLOBAL_WEIGHT[c] is how much that characteristic matters overall,
  independent of model (all weights sum to 1.0).

The result is a genuine per-dataset ranking: the same model can score best
on one dataset and worst on another, because VALUE[c] changes every time.
Only the single winning model (plus human-readable reasons built from its
top-contributing characteristics) is surfaced to the caller — the raw
scores and the runners-up are internal.
"""

import math
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, RandomForestRegressor
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
        "icon": "📈",
    },
    "Random Forest": {
        "class": RandomForestClassifier,
        "default_params": {"n_estimators": 200, "random_state": 42, "n_jobs": -1},
        "param_grid": {"n_estimators": [100, 200], "max_depth": [5, 10, None]},
        "description": "Ensemble of decision trees. Handles nonlinear relationships and mixed types well.",
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
        "icon": "💡",
    },
    "Gradient Boosting": {
        "class": GradientBoostingClassifier,
        "default_params": {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 4, "random_state": 42},
        "param_grid": {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1]},
        "description": "Classic gradient boosting. Interpretable with good performance on structured data.",
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
# Weighted scoring framework
# ─────────────────────────────────────────────

# Characteristics every model is scored against. Order doesn't matter for
# scoring, but it drives the order reasons are considered in.
CHARACTERISTIC_KEYS = [
    "size", "dimensionality", "missingness", "imbalance",
    "categorical", "multicollinearity", "nonlinearity",
    "explainability", "speed",
]

# How much each characteristic matters overall, independent of model. Sums to 1.0.
GLOBAL_WEIGHTS: Dict[str, float] = {
    "size": 0.14,
    "dimensionality": 0.10,
    "missingness": 0.12,
    "imbalance": 0.14,
    "categorical": 0.10,
    "multicollinearity": 0.12,
    "nonlinearity": 0.14,
    "explainability": 0.08,
    "speed": 0.06,
}

# How well each model tends to handle a HIGH value of each characteristic,
# in [-1, 1]. This is the only per-model "domain knowledge" in the engine —
# everything else (the actual ranking) falls out of the weighted formula.
MODEL_AFFINITY: Dict[str, Dict[str, float]] = {
    "Logistic Regression": {
        "size": -0.6, "dimensionality": -0.4, "missingness": -0.8, "imbalance": -0.5,
        "categorical": -0.3, "multicollinearity": -0.7, "nonlinearity": -0.9,
        "explainability": 0.9, "speed": 0.9,
    },
    "Random Forest": {
        "size": 0.2, "dimensionality": 0.2, "missingness": 0.1, "imbalance": 0.3,
        "categorical": 0.2, "multicollinearity": 0.6, "nonlinearity": 0.7,
        "explainability": 0.5, "speed": 0.1,
    },
    "XGBoost": {
        "size": 0.7, "dimensionality": 0.5, "missingness": 0.8, "imbalance": 0.7,
        "categorical": 0.1, "multicollinearity": 0.5, "nonlinearity": 0.8,
        "explainability": -0.3, "speed": -0.2,
    },
    "LightGBM": {
        "size": 0.9, "dimensionality": 0.8, "missingness": 0.7, "imbalance": 0.6,
        "categorical": 0.3, "multicollinearity": 0.5, "nonlinearity": 0.8,
        "explainability": -0.4, "speed": 0.8,
    },
    "Gradient Boosting": {
        "size": -0.1, "dimensionality": 0.0, "missingness": -0.5, "imbalance": 0.2,
        "categorical": -0.2, "multicollinearity": 0.4, "nonlinearity": 0.6,
        "explainability": 0.3, "speed": -0.6,
    },
}

# Human-readable phrasing for a characteristic that ends up being one of a
# model's top positive contributors. Only combinations with a meaningfully
# positive affinity (>= ~0.2 above) need an entry — those are the only ones
# that can plausibly explain a win. `raw` is the characteristics["_raw"] dict.
def _fmt_pct(x: float) -> str:
    return f"{x:.0f}%"


REASON_TEMPLATES = {
    "size": {
        "XGBoost": lambda raw: f"large training set ({raw['n_samples']:,} rows) plays to gradient boosting's strengths",
        "LightGBM": lambda raw: f"large training set ({raw['n_samples']:,} rows) suits LightGBM's leaf-wise growth, which scales efficiently",
        "Random Forest": lambda raw: f"dataset size ({raw['n_samples']:,} rows) is comfortably handled by a bagged tree ensemble",
    },
    "dimensionality": {
        "LightGBM": lambda raw: f"high feature count ({raw['n_features']} features) is exactly where LightGBM's histogram-based splitting excels",
        "XGBoost": lambda raw: f"{raw['n_features']} engineered features benefit from XGBoost's built-in regularization against overfitting",
        "Random Forest": lambda raw: f"{raw['n_features']} features are well handled by Random Forest's random feature subsampling per split",
    },
    "missingness": {
        "XGBoost": lambda raw: f"{_fmt_pct(raw['missing_pct'])} missing values are handled natively via XGBoost's sparsity-aware split finding, without manual imputation",
        "LightGBM": lambda raw: f"{_fmt_pct(raw['missing_pct'])} missing values are handled natively by LightGBM, avoiding imputation bias",
        "Random Forest": lambda raw: f"{_fmt_pct(raw['missing_pct'])} missing values are tolerated reasonably well by a tree ensemble",
    },
    "imbalance": {
        "XGBoost": lambda raw: f"a {raw['imbalance_ratio']:.1f}:1 class imbalance is addressed directly via XGBoost's scale_pos_weight",
        "LightGBM": lambda raw: f"a {raw['imbalance_ratio']:.1f}:1 class imbalance is addressed via LightGBM's class-weighting support",
        "Random Forest": lambda raw: f"a {raw['imbalance_ratio']:.1f}:1 class imbalance is partially offset by class_weight='balanced'",
        "Gradient Boosting": lambda raw: f"a {raw['imbalance_ratio']:.1f}:1 class imbalance is manageable with sample weighting",
    },
    "categorical": {
        "LightGBM": lambda raw: f"{_fmt_pct(raw['categorical_pct'])} categorical features are supported with lighter preprocessing than a linear model would need",
        "Random Forest": lambda raw: f"{_fmt_pct(raw['categorical_pct'])} categorical features split naturally within decision trees",
    },
    "multicollinearity": {
        "Random Forest": lambda raw: f"{_fmt_pct(raw['multicollinearity_pct'])} of numeric feature pairs are highly correlated — tree splits are far more robust to this than linear coefficients",
        "XGBoost": lambda raw: f"{_fmt_pct(raw['multicollinearity_pct'])} of numeric feature pairs are highly correlated, which boosted trees tolerate better than a linear model",
        "LightGBM": lambda raw: f"{_fmt_pct(raw['multicollinearity_pct'])} of numeric feature pairs are highly correlated — LightGBM's split-based structure isn't destabilized by this the way linear coefficients would be",
        "Gradient Boosting": lambda raw: f"{_fmt_pct(raw['multicollinearity_pct'])} of numeric feature pairs are highly correlated, which tree-based splits absorb better than linear regression",
    },
    "nonlinearity": {
        "XGBoost": lambda raw: "feature-target relationships look substantially non-linear — boosted trees capture this where a linear model would miss it",
        "LightGBM": lambda raw: "feature-target relationships look substantially non-linear, which LightGBM's tree structure captures directly",
        "Random Forest": lambda raw: "feature-target relationships look non-linear — a tree ensemble models this without manual feature transforms",
        "Gradient Boosting": lambda raw: "feature-target relationships look non-linear, which sequential boosting captures well",
    },
    "explainability": {
        "Logistic Regression": lambda raw: "interpretability is weighted heavily here, and logistic regression's coefficients are the most directly explainable to reviewers and regulators",
        "Random Forest": lambda raw: "interpretability matters here, and Random Forest's native feature importances stay reasonably transparent",
        "Gradient Boosting": lambda raw: "interpretability matters here, and this classic boosting implementation stays easier to reason about than more opaque variants",
    },
    "speed": {
        "Logistic Regression": lambda raw: "fast training/iteration is valued, and logistic regression fits in a fraction of the time of an ensemble",
        "LightGBM": lambda raw: "fast training/iteration is valued, and LightGBM is the quickest of the boosting options here",
    },
}


def _saturate(value: float, cap: float) -> float:
    """Scale value/cap into [0,1] without a hard cutoff artifact."""
    if cap <= 0:
        return 0.0
    return float(max(0.0, min(1.0, value / cap)))


def compute_dataset_characteristics(
    X: pd.DataFrame,
    y: Optional[pd.Series],
    col_types: Dict[str, List[str]],
    task_type: str = "binary",
    explainability_priority: float = 0.5,
    speed_priority: Optional[float] = None,
) -> Dict[str, Any]:
    """Measures the dataset characteristics the scoring engine below uses.
    Returns normalized 0-1 "VALUE[c]" scores under the characteristic keys,
    plus a "_raw" dict of the underlying human-readable numbers (used to
    build reasons, not for scoring)."""
    n_samples, n_features = X.shape

    # Missingness — average fraction of NaNs across all columns.
    missing_pct = float(X.isna().mean().mean() * 100) if n_features else 0.0
    missing_score = _saturate(missing_pct, 30.0)

    # Class imbalance (binary only — multiclass/regression treated as balanced).
    imbalance_ratio = 1.0
    if task_type == "binary" and y is not None:
        vc = y.value_counts()
        if len(vc) >= 2 and vc.min() > 0:
            imbalance_ratio = float(vc.max() / vc.min())
    imbalance_score = _saturate(imbalance_ratio - 1.0, 9.0)  # 10:1 -> 1.0

    # Categorical share of columns.
    cat_cols = [c for c in col_types.get("categorical", []) if c in X.columns]
    categorical_pct = 100.0 * len(cat_cols) / n_features if n_features else 0.0
    categorical_score = categorical_pct / 100.0

    # Multicollinearity — % of numeric column pairs with |corr| > 0.8.
    numeric_cols = [c for c in col_types.get("numeric", []) if c in X.columns]
    multicollinearity_pct = 0.0
    if len(numeric_cols) >= 2:
        sample_cols = numeric_cols[:50]  # cap comparisons on very wide datasets
        try:
            corr = X[sample_cols].apply(pd.to_numeric, errors="coerce").corr().abs()
            upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
            pairs = upper.stack()
            if len(pairs):
                multicollinearity_pct = 100.0 * float((pairs > 0.8).sum()) / len(pairs)
        except Exception:
            multicollinearity_pct = 0.0
    multicollinearity_score = _saturate(multicollinearity_pct, 40.0)

    # Non-linearity — gap between a non-linear signal (mutual information)
    # and a purely linear one (Pearson correlation) against the target: if
    # MI picks up much more signal than linear correlation does, the
    # relationships are likely non-linear.
    nonlinearity_score = 0.5  # neutral default when it can't be measured
    if task_type == "binary" and y is not None and numeric_cols:
        try:
            y_num = pd.to_numeric(y, errors="coerce")
            num_df = X[numeric_cols].apply(pd.to_numeric, errors="coerce")
            linear_signal = float(num_df.corrwith(y_num).abs().fillna(0).mean())

            filled = num_df.fillna(num_df.median()).fillna(0)
            y_filled = y_num.fillna(y_num.mode().iloc[0] if not y_num.mode().empty else 0)
            from sklearn.feature_selection import mutual_info_classif
            mi = mutual_info_classif(filled, y_filled, random_state=42)
            mi_signal_norm = _saturate(float(np.mean(mi)) if len(mi) else 0.0, 0.15)

            nonlinearity_score = max(0.0, min(1.0, mi_signal_norm - linear_signal))
        except Exception:
            nonlinearity_score = 0.5

    size_score = _saturate(math.log10(max(n_samples, 1) + 1), 5.0)  # ~100k rows -> 1.0
    dimensionality_score = _saturate(n_features, 100.0)

    if speed_priority is None:
        # Fast training matters more as data grows — otherwise stay moderate.
        speed_priority = 0.3 + 0.5 * size_score

    return {
        "size": size_score,
        "dimensionality": dimensionality_score,
        "missingness": missing_score,
        "imbalance": imbalance_score,
        "categorical": categorical_score,
        "multicollinearity": multicollinearity_score,
        "nonlinearity": nonlinearity_score,
        "explainability": float(max(0.0, min(1.0, explainability_priority))),
        "speed": float(max(0.0, min(1.0, speed_priority))),
        "_raw": {
            "n_samples": int(n_samples),
            "n_features": int(n_features),
            "missing_pct": missing_pct,
            "imbalance_ratio": imbalance_ratio,
            "categorical_pct": categorical_pct,
            "multicollinearity_pct": multicollinearity_pct,
            "nonlinearity_score": nonlinearity_score,
        },
    }


def characteristics_from_summary(
    n_samples: int,
    n_features: int,
    class_imbalance_ratio: float = 1.0,
    explainability_priority: float = 0.5,
    speed_priority: Optional[float] = None,
) -> Dict[str, Any]:
    """Fallback for callers that only have summary numbers (no dataset in
    hand) — e.g. the API called with raw n_samples/n_features instead of a
    file. Characteristics that need the actual data (missingness,
    multicollinearity, non-linearity, categorical share) fall back to a
    neutral 0.5 so they don't tilt the score either way."""
    size_score = _saturate(math.log10(max(n_samples, 1) + 1), 5.0)
    dimensionality_score = _saturate(n_features, 100.0)
    imbalance_score = _saturate(class_imbalance_ratio - 1.0, 9.0)
    if speed_priority is None:
        speed_priority = 0.3 + 0.5 * size_score

    return {
        "size": size_score,
        "dimensionality": dimensionality_score,
        "missingness": 0.5,
        "imbalance": imbalance_score,
        "categorical": 0.5,
        "multicollinearity": 0.5,
        "nonlinearity": 0.5,
        "explainability": float(max(0.0, min(1.0, explainability_priority))),
        "speed": float(max(0.0, min(1.0, speed_priority))),
        "_raw": {
            "n_samples": int(n_samples),
            "n_features": int(n_features),
            "missing_pct": None,
            "imbalance_ratio": float(class_imbalance_ratio),
            "categorical_pct": None,
            "multicollinearity_pct": None,
            "nonlinearity_score": None,
        },
    }


def _score_model(model_name: str, characteristics: Dict[str, Any]) -> tuple[float, List[tuple[str, float]]]:
    """score(model) = sum_c GLOBAL_WEIGHT[c] * MODEL_AFFINITY[model][c] * VALUE[c].
    Returns the total score plus each characteristic's signed contribution,
    so the caller can explain the winner without exposing raw scores."""
    affinity = MODEL_AFFINITY[model_name]
    contributions: List[tuple[str, float]] = []
    total = 0.0
    for c in CHARACTERISTIC_KEYS:
        value = characteristics.get(c, 0.0)
        contribution = GLOBAL_WEIGHTS[c] * affinity.get(c, 0.0) * value
        contributions.append((c, contribution))
        total += contribution
    return total, contributions


def _build_reasons(model_name: str, contributions: List[tuple[str, float]], raw: Dict[str, Any], max_reasons: int = 4) -> List[str]:
    ranked = sorted(contributions, key=lambda t: t[1], reverse=True)
    reasons: List[str] = []
    for characteristic, contribution in ranked:
        if contribution <= 0.01:
            continue
        template = REASON_TEMPLATES.get(characteristic, {}).get(model_name)
        if template is None:
            continue
        try:
            text = template(raw)
        except Exception:
            continue
        if text:
            reasons.append(text)
        if len(reasons) >= max_reasons:
            break
    return reasons


def recommend_model(characteristics: Dict[str, Any], task_type: str = "binary") -> Dict[str, Any]:
    """Scores every supported model against the given dataset
    characteristics using the shared weighted formula, and returns ONLY the
    winner (with reasons) plus the full model catalogue for manual
    comparison/override — the scores and runner-up ranking stay internal.
    """
    if task_type not in ("binary", "multiclass"):
        models = REGRESSION_MODELS
        best_name = "XGBoost Regressor" if "XGBoost Regressor" in models else next(iter(models))
        recommended = {
            "name": best_name,
            "description": models[best_name]["description"],
            "icon": models[best_name].get("icon", ""),
            "reasons": ["gradient boosting is a strong general-purpose default for tabular regression tasks"],
        }
        all_models = [
            {"name": n, "description": info["description"], "icon": info.get("icon", "")}
            for n, info in models.items()
        ]
        return {"recommended_model": recommended, "all_models": all_models}

    models = CLASSIFICATION_MODELS
    raw = characteristics.get("_raw", {})

    scores: Dict[str, float] = {}
    contributions_by_model: Dict[str, List[tuple[str, float]]] = {}
    for name in models:
        total, contributions = _score_model(name, characteristics)
        scores[name] = total
        contributions_by_model[name] = contributions

    best_name = max(scores, key=scores.get)
    reasons = _build_reasons(best_name, contributions_by_model[best_name], raw)
    if not reasons:
        reasons = [models[best_name]["description"]]

    recommended = {
        "name": best_name,
        "description": models[best_name]["description"],
        "icon": models[best_name].get("icon", ""),
        "reasons": reasons,
    }
    all_models = [
        {"name": n, "description": info["description"], "icon": info.get("icon", "")}
        for n, info in models.items()
    ]
    return {"recommended_model": recommended, "all_models": all_models}


# ─────────────────────────────────────────────
# Model instantiation (unchanged behaviour)
# ─────────────────────────────────────────────

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
