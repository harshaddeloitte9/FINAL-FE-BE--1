"""
evaluate.py - Credit Risk Focused Evaluation Engine
Computes and visualizes all metrics for binary classification and regression.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    roc_curve, precision_recall_curve, average_precision_score,
    mean_squared_error, mean_absolute_error, r2_score,
)


def _to_scores(y_proba) -> np.ndarray:
    """Return 1-D probability scores regardless of whether y_proba is 1-D or 2-D."""
    arr = np.asarray(y_proba)
    return arr[:, 1] if arr.ndim == 2 else arr


# ─────────────────────────────────────────────
# Binary Classification Metrics
# ─────────────────────────────────────────────

def compute_binary_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Compute full binary classification metric suite."""
    if y_proba is not None:
        _scores = _to_scores(y_proba) if y_proba.ndim == 2 else y_proba
        y_pred_thresh = (_scores >= threshold).astype(int)
    else:
        y_pred_thresh = y_pred
        _scores = None

    metrics = {
        "accuracy": round(accuracy_score(y_true, y_pred_thresh), 4),
        "precision": round(precision_score(y_true, y_pred_thresh, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred_thresh, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred_thresh, zero_division=0), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred_thresh).tolist(),
        "classification_report": classification_report(y_true, y_pred_thresh, output_dict=True, zero_division=0),
        "threshold_used": threshold,
    }

    if y_proba is not None and _scores is not None:
        metrics["roc_auc"] = round(roc_auc_score(y_true, _scores), 4)
        metrics["pr_auc"] = round(average_precision_score(y_true, _scores), 4)

    return metrics


def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Compute regression evaluation metrics."""
    mse = mean_squared_error(y_true, y_pred)
    return {
        "r2": round(r2_score(y_true, y_pred), 4),
        "mae": round(mean_absolute_error(y_true, y_pred), 4),
        "mse": round(mse, 4),
        "rmse": round(np.sqrt(mse), 4),
    }


def compute_heteroscedasticity_check(
    y_true: np.ndarray,
    y_pred_or_proba: np.ndarray,
    task_type: str = "binary",
    n_bins: int = 5,
) -> Dict[str, Any]:
    """
    Lightweight heteroscedasticity-style residual check.
    For regression this checks whether absolute residuals grow with prediction size.
    For binary classification this checks probability-bin residual variance.
    """
    y_true = np.asarray(y_true)
    scores = np.asarray(y_pred_or_proba)
    if scores.ndim == 2:
        scores = scores[:, 1]

    residuals = y_true - scores
    abs_resid = np.abs(residuals)
    result = {
        "spearman_abs_resid_vs_score": None,
        "variance_ratio": None,
        "risk_flag": "Not enough data",
        "bin_variance": [],
    }

    if len(scores) < max(n_bins * 5, 20):
        return result

    try:
        from scipy.stats import spearmanr
        corr, p_value = spearmanr(scores, abs_resid)
        result["spearman_abs_resid_vs_score"] = round(float(corr), 4)
        result["p_value"] = round(float(p_value), 4)
    except Exception:
        pass

    try:
        bins = pd.qcut(scores, q=n_bins, duplicates="drop")
        df = pd.DataFrame({"bin": bins, "residual": residuals})
        grouped = df.groupby("bin", observed=False)["residual"].agg(["count", "var"]).reset_index()
        grouped["var"] = grouped["var"].fillna(0)
        variances = grouped["var"].values
        positive = variances[variances > 0]
        if len(positive) > 1:
            result["variance_ratio"] = round(float(positive.max() / positive.min()), 3)
        result["bin_variance"] = [
            {
                "score_bin": str(row["bin"]),
                "n": int(row["count"]),
                "residual_variance": round(float(row["var"]), 6),
            }
            for _, row in grouped.iterrows()
        ]
    except Exception:
        pass

    corr_abs = abs(result["spearman_abs_resid_vs_score"] or 0)
    var_ratio = result["variance_ratio"] or 0
    if corr_abs > 0.35 or var_ratio > 4:
        result["risk_flag"] = "Potential heteroscedasticity"
    else:
        result["risk_flag"] = "No strong signal"

    return result


# ─────────────────────────────────────────────
# Plotly Visualizations
# ─────────────────────────────────────────────

COLORS = {
    "primary": "#6366f1",
    "secondary": "#f59e0b",
    "success": "#10b981",
    "danger": "#ef4444",
    "neutral": "#64748b",
    "bg": "#0f172a",
    "card": "#1e293b",
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


def plot_roc_curve(y_true, y_proba) -> go.Figure:
    fpr, tpr, _ = roc_curve(y_true, _to_scores(y_proba))
    auc = roc_auc_score(y_true, _to_scores(y_proba))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fpr, y=tpr, mode="lines", name=f"ROC (AUC={auc:.3f})",
        line=dict(color=COLORS["primary"], width=3),
        fill="tozeroy", fillcolor="rgba(99,102,241,0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Random Classifier",
        line=dict(color=COLORS["neutral"], dash="dash"),
    ))
    fig.update_layout(**_plotly_layout("ROC Curve"))
    fig.update_xaxes(title_text="False Positive Rate")
    fig.update_yaxes(title_text="True Positive Rate")
    return fig


def plot_pr_curve(y_true, y_proba) -> go.Figure:
    precision, recall, _ = precision_recall_curve(y_true, _to_scores(y_proba))
    pr_auc = average_precision_score(y_true, _to_scores(y_proba))
    baseline = y_true.mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=recall, y=precision, mode="lines", name=f"PR Curve (AUC={pr_auc:.3f})",
        line=dict(color=COLORS["secondary"], width=3),
        fill="tozeroy", fillcolor="rgba(245,158,11,0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[baseline, baseline], mode="lines", name=f"Baseline ({baseline:.2f})",
        line=dict(color=COLORS["neutral"], dash="dash"),
    ))
    fig.update_layout(**_plotly_layout("Precision-Recall Curve"))
    fig.update_xaxes(title_text="Recall")
    fig.update_yaxes(title_text="Precision")
    return fig


def plot_confusion_matrix(cm: List[List[int]], labels=None) -> go.Figure:
    cm_array = np.array(cm)
    if labels is None:
        labels = [f"Class {i}" for i in range(cm_array.shape[0])]

    # Normalize for color intensity
    cm_norm = cm_array / cm_array.sum(axis=1, keepdims=True)

    text = [[f"{cm_array[i][j]}<br>({cm_norm[i][j]:.1%})" for j in range(len(labels))]
            for i in range(len(labels))]

    fig = go.Figure(data=go.Heatmap(
        z=cm_norm, x=labels, y=labels,
        text=text, texttemplate="%{text}",
        colorscale="Blues", showscale=False,
    ))
    fig.update_layout(**_plotly_layout("Confusion Matrix"))
    fig.update_xaxes(title_text="Predicted")
    fig.update_yaxes(title_text="Actual", autorange="reversed")
    return fig


def plot_feature_importance(importance_df: pd.DataFrame, title: str = "Feature Importance") -> go.Figure:
    df = importance_df.sort_values("Importance", ascending=True).tail(15)
    fig = go.Figure(go.Bar(
        x=df["Importance"], y=df["Feature"],
        orientation="h",
        marker=dict(
            color=df["Importance"],
            colorscale=[[0, COLORS["neutral"]], [1, COLORS["primary"]]],
        ),
    ))
    fig.update_layout(**_plotly_layout(title))
    fig.update_xaxes(title_text="Importance Score")
    return fig


def plot_score_distribution(y_true, y_proba) -> go.Figure:
    """Plot predicted probability distribution by actual class."""
    df = pd.DataFrame({"prob": _to_scores(y_proba), "label": y_true.astype(str)})

    fig = go.Figure()
    for label, color in [("0", COLORS["success"]), ("1", COLORS["danger"])]:
        subset = df[df["label"] == label]["prob"]
        name = "Non-Default" if label == "0" else "Default"
        fig.add_trace(go.Histogram(
            x=subset, name=name, opacity=0.7,
            marker_color=color, nbinsx=40,
            histnorm="probability density",
        ))

    fig.update_layout(**_plotly_layout("Predicted Probability Distribution by Class"), barmode="overlay")
    fig.update_xaxes(title_text="Predicted Probability (Default)")
    fig.update_yaxes(title_text="Density")
    return fig


def plot_threshold_analysis(y_true, y_proba) -> go.Figure:
    """Plot precision, recall, F1 across probability thresholds."""
    thresholds = np.linspace(0.01, 0.99, 99)
    precisions, recalls, f1s = [], [], []
    for t in thresholds:
        y_pred_t = (_to_scores(y_proba) >= t).astype(int)
        precisions.append(precision_score(y_true, y_pred_t, zero_division=0))
        recalls.append(recall_score(y_true, y_pred_t, zero_division=0))
        f1s.append(f1_score(y_true, y_pred_t, zero_division=0))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=thresholds, y=precisions, name="Precision",
                              line=dict(color=COLORS["primary"], width=2)))
    fig.add_trace(go.Scatter(x=thresholds, y=recalls, name="Recall",
                              line=dict(color=COLORS["secondary"], width=2)))
    fig.add_trace(go.Scatter(x=thresholds, y=f1s, name="F1",
                              line=dict(color=COLORS["success"], width=2)))

    # Mark best F1 threshold
    best_t = thresholds[np.argmax(f1s)]
    fig.add_vline(x=best_t, line_dash="dash", line_color=COLORS["danger"],
                   annotation_text=f"Best F1 @ {best_t:.2f}")

    fig.update_layout(**_plotly_layout("Threshold Analysis"))
    fig.update_xaxes(title_text="Decision Threshold")
    fig.update_yaxes(title_text="Score", range=[0, 1])
    return fig


def plot_lift_chart(y_true, y_proba) -> go.Figure:
    """Compute and plot a cumulative gains/lift chart."""
    df = pd.DataFrame({"prob": _to_scores(y_proba), "actual": y_true})
    df = df.sort_values("prob", ascending=False).reset_index(drop=True)
    df["cum_actual"] = df["actual"].cumsum()
    df["cum_pct"] = (df.index + 1) / len(df)
    df["cum_gain"] = df["cum_actual"] / df["actual"].sum()
    df["lift"] = df["cum_gain"] / df["cum_pct"]

    fig = make_subplots(rows=1, cols=2, subplot_titles=["Cumulative Gains", "Lift Curve"])
    fig.add_trace(go.Scatter(x=df["cum_pct"], y=df["cum_gain"], mode="lines",
                              name="Model", line=dict(color=COLORS["primary"], width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random",
                              line=dict(color=COLORS["neutral"], dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["cum_pct"], y=df["lift"], mode="lines",
                              name="Lift", line=dict(color=COLORS["secondary"], width=2)), row=1, col=2)
    fig.add_trace(go.Scatter(x=[0, 1], y=[1, 1], mode="lines", name="Baseline",
                              line=dict(color=COLORS["neutral"], dash="dash")), row=1, col=2)

    fig.update_layout(
        **_plotly_layout("Gain & Lift Chart"),
        showlegend=True,
    )
    return fig
