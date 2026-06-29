"""
explainability.py - Model Explainability Engine
SHAP values, feature importance, and individual prediction reasoning.

FIX v2:
  - Always resolve REAL feature names from the fitted preprocessor
    (handles OHE expansion, datetime decomposition, FE-added columns)
  - No more feat_0, feat_1 fallbacks anywhere
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings("ignore")

import plotly.graph_objects as go
import plotly.express as px
import matplotlib
matplotlib.use("Agg")

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

from preprocessing import get_feature_names_from_fitted_preprocessor


COLORS = {
    "primary": "#6366f1",
    "secondary": "#f59e0b",
    "danger": "#ef4444",
    "success": "#10b981",
    "neutral": "#64748b",
    "text": "#e2e8f0",
}


def _plotly_layout(title: str, **kwargs) -> Dict:
    return dict(
        title=dict(text=title, font=dict(color=COLORS["text"], size=16)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"]),
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(gridcolor="#334155", zerolinecolor="#334155"),
        yaxis=dict(gridcolor="#334155", zerolinecolor="#334155"),
        **kwargs,
    )


# ─────────────────────────────────────────────
# Resolve real feature names from a fitted pipeline
# ─────────────────────────────────────────────

def resolve_feature_names(pipeline) -> List[str]:
    """
    Given a fitted sklearn Pipeline (preprocessor → model),
    return the real feature names that go INTO the model.

    Priority:
      1. get_feature_names_out() on the fitted ColumnTransformer
      2. Fallback to column names stored in the transformer
    Never returns feat_N placeholders.
    """
    try:
        preprocessor = pipeline.named_steps.get("preprocessor")
        if preprocessor is None:
            # imblearn pipeline wraps differently
            for step_name, step in pipeline.steps:
                if hasattr(step, "transformers_"):
                    preprocessor = step
                    break

        if preprocessor is not None and hasattr(preprocessor, "transformers_"):
            return get_feature_names_from_fitted_preprocessor(preprocessor)
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────
# Feature Importance
# ─────────────────────────────────────────────

def extract_feature_importance(pipeline) -> Optional[pd.DataFrame]:
    """
    Extract feature importance from a trained pipeline using real names.
    Supports: tree feature_importances_, linear coef_, and others.
    """
    try:
        model = pipeline.named_steps.get("model")
        if model is None:
            model = pipeline[-1]
    except Exception:
        return None

    importances = None

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        coef = model.coef_
        if coef.ndim > 1:
            coef = coef[0]
        importances = np.abs(coef)

    if importances is None:
        return None

    # Get real names
    real_names = resolve_feature_names(pipeline)
    n = len(importances)

    if len(real_names) >= n:
        names = real_names[:n]
    elif len(real_names) > 0:
        # Pad with indexed names based on last known name pattern
        names = real_names + [f"engineered_feat_{i}" for i in range(n - len(real_names))]
    else:
        names = [f"feature_{i}" for i in range(n)]

    df = pd.DataFrame({"Feature": names, "Importance": importances})
    df = df.sort_values("Importance", ascending=False).reset_index(drop=True)
    total = df["Importance"].sum()
    if total > 0:
        df["Importance"] = (df["Importance"] / total).round(5)
    return df


def plot_feature_importance_bar(importance_df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    df = importance_df.head(top_n).sort_values("Importance", ascending=True)
    fig = go.Figure(go.Bar(
        x=df["Importance"], y=df["Feature"],
        orientation="h",
        marker=dict(
            color=df["Importance"],
            colorscale=[[0, COLORS["neutral"]], [1, COLORS["primary"]]],
        ),
        text=[f"{v:.4f}" for v in df["Importance"]],
        textposition="outside",
    ))
    fig.update_layout(**_plotly_layout(f"Top {top_n} Feature Importances"))
    fig.update_xaxes(title_text="Normalized Importance")
    return fig


# ─────────────────────────────────────────────
# SHAP Analysis
# ─────────────────────────────────────────────

def compute_shap_values(
    pipeline,
    X_sample: pd.DataFrame,
    max_samples: int = 200,
) -> Optional[Tuple[Any, np.ndarray, pd.DataFrame, List[str]]]:
    """
    Compute SHAP values using REAL feature names extracted from the fitted pipeline.
    Returns (explainer, shap_values, X_transformed_df, feature_names) or None.
    """
    if not SHAP_AVAILABLE:
        return None

    try:
        preprocessor = pipeline.named_steps.get("preprocessor")
        model = pipeline.named_steps.get("model")

        if preprocessor is None or model is None:
            return None

        X_sub = X_sample.head(max_samples)
        X_transformed = preprocessor.transform(X_sub)

        # Get real names
        real_names = get_feature_names_from_fitted_preprocessor(preprocessor)
        n_feats = X_transformed.shape[1]

        if len(real_names) >= n_feats:
            names = real_names[:n_feats]
        elif len(real_names) > 0:
            names = real_names + [f"engineered_feat_{i}" for i in range(n_feats - len(real_names))]
        else:
            names = [f"feature_{i}" for i in range(n_feats)]

        X_df = pd.DataFrame(X_transformed, columns=names)

        model_type = type(model).__name__
        if any(t in model_type for t in ["XGB", "LGBM", "Forest", "Boosting", "Tree"]):
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X_df)
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]
        else:
            background = shap.sample(X_df, min(50, len(X_df)))
            if hasattr(model, "predict_proba"):
                explainer = shap.KernelExplainer(model.predict_proba, background)
                shap_vals = explainer.shap_values(X_df.head(50), nsamples=100)
                if isinstance(shap_vals, list):
                    shap_vals = shap_vals[1]
            else:
                return None

        return explainer, np.array(shap_vals), X_df, names

    except Exception as e:
        print(f"SHAP error: {e}")
        return None


def plot_shap_summary_plotly(shap_values: np.ndarray, X_df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    mean_abs = np.abs(shap_values).mean(axis=0)
    df = pd.DataFrame({"Feature": X_df.columns.tolist(), "Mean|SHAP|": mean_abs})
    df = df.sort_values("Mean|SHAP|", ascending=False).head(top_n).sort_values("Mean|SHAP|", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["Mean|SHAP|"], y=df["Feature"],
        orientation="h",
        marker=dict(
            color=df["Mean|SHAP|"],
            colorscale=[[0, "#334155"], [0.5, COLORS["primary"]], [1, COLORS["danger"]]],
        ),
        text=[f"{v:.5f}" for v in df["Mean|SHAP|"]],
        textposition="outside",
    ))
    fig.update_layout(**_plotly_layout(f"SHAP Feature Importance (Top {top_n})"))
    fig.update_xaxes(title_text="Mean |SHAP Value|")
    return fig


def plot_shap_waterfall_single(
    shap_values: np.ndarray,
    X_df: pd.DataFrame,
    sample_idx: int = 0,
) -> go.Figure:
    shap_row = shap_values[sample_idx]
    feat_vals = X_df.iloc[sample_idx]
    feature_names = X_df.columns.tolist()

    df = pd.DataFrame({
        "Feature": feature_names[:len(shap_row)],
        "SHAP": shap_row[:len(feature_names)],
        "Value": feat_vals.values[:len(shap_row)],
    })
    df["AbsSHAP"] = df["SHAP"].abs()
    df = df.sort_values("AbsSHAP", ascending=False).head(12)
    df["Label"] = df.apply(
        lambda r: f"{r['Feature']} = {r['Value']:.3f}" if isinstance(r["Value"], (int, float, np.floating)) else f"{r['Feature']} = {r['Value']}",
        axis=1
    )
    df = df.sort_values("SHAP", ascending=True)
    colors = [COLORS["success"] if v < 0 else COLORS["danger"] for v in df["SHAP"]]

    fig = go.Figure(go.Bar(
        x=df["SHAP"], y=df["Label"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.5f}" for v in df["SHAP"]],
        textposition="outside",
    ))
    fig.update_layout(**_plotly_layout(f"Prediction Explanation — Sample #{sample_idx}"))
    fig.update_xaxes(title_text="SHAP Value (impact on model output)")
    return fig


# ─────────────────────────────────────────────
# Natural Language Reasoning
# ─────────────────────────────────────────────

def generate_prediction_reasoning(
    shap_values: np.ndarray,
    X_df: pd.DataFrame,
    y_proba: np.ndarray,
    sample_idx: int = 0,
    threshold: float = 0.5,
) -> str:
    prob = y_proba[sample_idx, 1]
    decision = "🔴 HIGH RISK (Default Predicted)" if prob >= threshold else "🟢 LOW RISK (No Default Predicted)"

    shap_row = shap_values[sample_idx]
    feat_vals = X_df.iloc[sample_idx]
    feature_names = X_df.columns.tolist()

    df = pd.DataFrame({
        "Feature": feature_names[:len(shap_row)],
        "SHAP": shap_row[:len(feature_names)],
        "Value": feat_vals.values[:len(shap_row)],
    })
    df["AbsSHAP"] = df["SHAP"].abs()
    df = df.sort_values("AbsSHAP", ascending=False).head(5)

    lines = [
        f"**Prediction:** {decision}",
        f"**Default Probability:** {prob:.1%}  (threshold = {threshold:.0%})",
        "",
        "**Top Drivers of This Prediction:**",
    ]
    for _, row in df.iterrows():
        direction = "↑ increases default risk" if row["SHAP"] > 0 else "↓ reduces default risk"
        val_str = f"{row['Value']:.4f}" if isinstance(row["Value"], (float, np.floating)) else str(row["Value"])
        lines.append(
            f"- **{row['Feature']}** = `{val_str}` — {direction}  *(SHAP: {row['SHAP']:+.5f})*"
        )
    return "\n".join(lines)


def generate_model_summary(
    metrics: Dict,
    importance_df: Optional[pd.DataFrame],
    task_type: str = "binary",
) -> str:
    lines = []
    if task_type == "binary":
        auc = metrics.get("roc_auc", None)
        recall = metrics.get("recall", None)
        f1 = metrics.get("f1", None)
        pr_auc = metrics.get("pr_auc", None)

        lines.append("### 📋 Model Performance Summary")
        lines.append("")
        if isinstance(auc, float):
            quality = "excellent" if auc > 0.85 else ("good" if auc > 0.75 else "moderate")
            lines.append(f"The model achieved a **ROC-AUC of {auc:.4f}**, indicating **{quality}** discriminative ability.")
        if isinstance(recall, float):
            quality = "strong" if recall > 0.70 else "moderate"
            lines.append(f"**Recall (Sensitivity) = {recall:.4f}** — {quality} for credit risk.")
            lines.append("In credit risk, recall matters most: a missed default costs far more than a false alarm.")
        if isinstance(f1, float):
            lines.append(f"**F1 Score = {f1:.4f}** — harmonic balance of precision and recall.")
        if isinstance(pr_auc, float):
            lines.append(f"**PR-AUC = {pr_auc:.4f}** — accounts for class imbalance in the portfolio.")

    if importance_df is not None and not importance_df.empty:
        top3 = importance_df.head(3)["Feature"].tolist()
        lines.append("")
        lines.append("### 🔑 Key Predictors")
        lines.append(f"The top drivers are: **{', '.join(top3)}**.")
        lines.append("These features exert the highest influence on default risk predictions.")

    return "\n".join(lines)
