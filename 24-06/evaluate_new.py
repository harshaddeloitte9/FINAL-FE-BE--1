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
    brier_score_loss,
)


def _to_scores(y_proba) -> np.ndarray:
    """Return 1-D probability scores regardless of whether y_proba is 1-D or 2-D."""
    arr = np.asarray(y_proba)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            return arr[:, 0]
        if arr.shape[1] >= 2:
            return arr[:, 1]
    return arr


def compute_ks_statistic(y_true: np.ndarray, y_proba) -> Dict[str, Any]:
    """
    Kolmogorov-Smirnov statistic: the max separation between the cumulative
    distributions of predicted scores for the positive (default) and negative
    (non-default) classes. Standard credit-risk metric — higher KS means the
    model separates good/bad accounts better. Ranges 0-1.
    """
    y_true = np.asarray(y_true)
    scores = _to_scores(y_proba)

    pos_scores = scores[y_true == 1]
    neg_scores = scores[y_true == 0]

    if len(pos_scores) == 0 or len(neg_scores) == 0:
        return {"ks_statistic": None, "ks_pvalue": None}

    from scipy.stats import ks_2samp
    result = ks_2samp(pos_scores, neg_scores)

    return {
        "ks_statistic": round(float(result.statistic), 4),
        "ks_pvalue": round(float(result.pvalue), 4),
    }


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
        try:
            roc_auc_value = roc_auc_score(y_true, _scores)
            metrics["roc_auc"] = round(float(roc_auc_value), 4) if not np.isnan(roc_auc_value) else None
        except Exception:
            metrics["roc_auc"] = None
        try:
            metrics["pr_auc"] = round(average_precision_score(y_true, _scores), 4)
        except Exception:
            metrics["pr_auc"] = None
        try:
            metrics.update(compute_ks_statistic(y_true, _scores))
        except Exception:
            metrics["ks_statistic"] = None
            metrics["ks_pvalue"] = None
        try:
            metrics["brier_score"] = round(float(brier_score_loss(y_true, _scores)), 4)
        except Exception:
            metrics["brier_score"] = None

    return metrics


def compute_roc_curve(y_true: np.ndarray, y_proba: Optional[np.ndarray] = None) -> List[Dict[str, float]]:
    """Return ROC points as a list of {fpr, tpr} dicts."""
    if y_proba is None:
        return []
    scores = _to_scores(y_proba)
    fpr, tpr, _ = roc_curve(y_true, scores)
    return [{"fpr": float(x), "tpr": float(y)} for x, y in zip(fpr.tolist(), tpr.tolist())]


def compute_pr_curve(y_true: np.ndarray, y_proba: Optional[np.ndarray] = None) -> List[Dict[str, float]]:
    """Return PR points as a list of {recall, precision} dicts."""
    if y_proba is None:
        return []
    scores = _to_scores(y_proba)
    precision, recall, _ = precision_recall_curve(y_true, scores)
    return [{"recall": float(r), "precision": float(p)} for p, r in zip(precision.tolist(), recall.tolist())]


def compute_threshold_analysis(y_true: np.ndarray, y_proba: Optional[np.ndarray] = None) -> List[Dict[str, float]]:
    """Evaluate precision/recall/F1 across the same threshold grid used by the Streamlit plot."""
    if y_proba is None:
        return []
    scores = _to_scores(y_proba)
    thresholds = np.linspace(0.01, 0.99, 99)
    rows = []
    for threshold in thresholds:
        y_pred_t = (scores >= threshold).astype(int)
        rows.append({
            "threshold": float(round(threshold, 2)),
            "precision": float(precision_score(y_true, y_pred_t, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred_t, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred_t, zero_division=0)),
        })
    return rows


def compute_score_distribution(y_true: np.ndarray, y_proba: Optional[np.ndarray] = None, n_bins: int = 40) -> List[Dict[str, Any]]:
    """Summarize score distribution by score bins for the frontend chart."""
    if y_proba is None:
        return []
    scores = _to_scores(y_proba)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for i in range(len(bins) - 1):
        left, right = bins[i], bins[i + 1]
        mask = (scores >= left) & (scores < right)
        if i == len(bins) - 2:
            mask = (scores >= left) & (scores <= right)
        if not np.any(mask):
            continue
        good = int(np.sum((y_true[mask] == 0).astype(int)))
        bad = int(np.sum((y_true[mask] == 1).astype(int)))
        rows.append({
            "bin": f"{left:.2f}-{right:.2f}",
            "good": good,
            "bad": bad,
        })
    return rows


def compute_gain_chart(y_true: np.ndarray, y_proba: Optional[np.ndarray] = None, n_deciles: int = 10) -> List[Dict[str, float]]:
    """Return cumulative gain by decile in the same shape the UI expects."""
    if y_proba is None:
        return []
    scores = _to_scores(y_proba)
    actual = np.asarray(y_true).astype(int)
    order = np.argsort(scores)[::-1]
    scores = scores[order]
    actual = actual[order]
    total_actual = int(actual.sum())
    results = []
    for i in range(n_deciles + 1):
        pct = i / n_deciles
        cutoff = int(len(actual) * pct)
        cum_actual = int(actual[:cutoff].sum()) if cutoff > 0 else 0
        results.append({
            "decile": int(pct * 100),
            "model": float(round(cum_actual / total_actual * 100 if total_actual > 0 else 0.0, 2)),
            "baseline": float(round(pct * 100, 2)),
        })
    return results


def compute_lift_chart(y_true: np.ndarray, y_proba: Optional[np.ndarray] = None, n_deciles: int = 10) -> List[Dict[str, float]]:
    """Return cumulative gain/lift rows for the Streamlit lift chart."""
    if y_proba is None:
        return []
    scores = _to_scores(y_proba)
    actual = np.asarray(y_true).astype(int)
    order = np.argsort(scores)[::-1]
    scores = scores[order]
    actual = actual[order]
    total_actual = int(actual.sum())
    results = []
    for i in range(n_deciles + 1):
        pct = i / n_deciles
        cutoff = int(len(actual) * pct)
        cum_actual = int(actual[:cutoff].sum()) if cutoff > 0 else 0
        cum_gain = cum_actual / total_actual if total_actual > 0 else 0.0
        lift = cum_gain / pct if pct > 0 else 0.0
        results.append({
            "decile": int(pct * 100),
            "model": float(round(cum_gain * 100, 2)),
            "baseline": float(round(pct * 100, 2)),
            "lift": float(round(lift, 4)),
        })
    return results


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


def plot_actual_vs_predicted(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
) -> go.Figure:
    """
    Plots actual default rate vs average predicted PD, grouped into
    bins by predicted score (calibration-style chart, not time-based).
    Shows whether the model's predicted probabilities match real-world
    outcomes — e.g. customers predicted at 70% PD should actually
    default ~70% of the time.
    """
    df = pd.DataFrame({"actual": y_true, "predicted": y_proba})
    df["bin"] = pd.qcut(df["predicted"], q=n_bins, duplicates="drop")

    grouped = df.groupby("bin", observed=True).agg(
        actual_rate=("actual", "mean"),
        predicted_rate=("predicted", "mean"),
        n=("actual", "count"),
    ).reset_index()
    grouped["bin_label"] = grouped["bin"].astype(str)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=grouped["bin_label"], y=grouped["actual_rate"],
        name="Actual Default Rate",
        marker_color="#ef4444",
        opacity=0.85,
    ))

    fig.add_trace(go.Scatter(
        x=grouped["bin_label"], y=grouped["predicted_rate"],
        mode="lines+markers", name="Avg Predicted PD",
        line=dict(color="#6366f1", width=3),
        marker=dict(size=8),
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        title="Actual vs Predicted Default Rate by Risk Bin",
        xaxis_title="Predicted PD Bin (low → high risk)",
        yaxis_title="Default Rate",
        yaxis=dict(tickformat=".0%", gridcolor="#334155"),
        legend=dict(orientation="h", y=1.1),
    )

    return fig


# ─────────────────────────────────────────────
# Temporal Stability (Actual vs Predicted over time)
# ─────────────────────────────────────────────

def _temporal_grouped(dates, y_true, y_proba, freq: str = "ME") -> pd.DataFrame:
    """Group actual default rate and average predicted PD by calendar period."""
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True), errors="coerce")
    y_true_arr = np.asarray(y_true)
    y_proba_arr = _to_scores(np.asarray(y_proba))

    df = pd.DataFrame({
        "date": dates,
        "actual": y_true_arr,
        "predicted": y_proba_arr,
    }).dropna(subset=["date"])

    if df.empty:
        return df

    pandas_freq = {"Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}.get(freq, freq)
    pandas_freq = pandas_freq.replace("ME", "M").replace("QE", "Q").replace("YE", "Y")
    df["period"] = df["date"].dt.to_period(pandas_freq)
    grouped = df.groupby("period", observed=True).agg(
        actual_rate=("actual", "mean"),
        predicted_rate=("predicted", "mean"),
        n=("actual", "count"),
    ).reset_index()
    grouped["period_label"] = grouped["period"].astype(str)
    grouped["gap"] = grouped["actual_rate"] - grouped["predicted_rate"]
    grouped["abs_gap"] = grouped["gap"].abs()
    return grouped.sort_values("period").reset_index(drop=True)


def plot_actual_vs_predicted_over_time(
    dates,
    y_true: np.ndarray,
    y_proba: np.ndarray,
    freq: str = "ME",
) -> go.Figure:
    """
    Plots actual default rate vs average predicted PD over calendar time
    (monthly/quarterly/yearly), to check whether predicted PDs track real-world
    outcomes consistently across the observation window (temporal/regime stability),
    as opposed to plot_actual_vs_predicted() which bins by predicted score.
    """
    grouped = _temporal_grouped(dates, y_true, y_proba, freq=freq)

    fig = go.Figure()
    if grouped.empty:
        fig.update_layout(**_plotly_layout("Actual vs Predicted Default Rate Over Time"))
        return fig

    fig.add_trace(go.Bar(
        x=grouped["period_label"], y=grouped["actual_rate"],
        name="Actual Default Rate",
        marker_color=COLORS["danger"],
        opacity=0.85,
    ))

    fig.add_trace(go.Scatter(
        x=grouped["period_label"], y=grouped["predicted_rate"],
        mode="lines+markers", name="Avg Predicted PD",
        line=dict(color=COLORS["primary"], width=3),
        marker=dict(size=8),
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"]),
        title="Actual vs Predicted Default Rate Over Time",
        xaxis_title="Period",
        yaxis_title="Default Rate",
        yaxis=dict(tickformat=".0%", gridcolor="#334155"),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def compute_temporal_stability_summary(
    dates,
    y_true: np.ndarray,
    y_proba: np.ndarray,
    freq: str = "ME",
    gap_threshold: float = 0.05,
) -> Dict[str, Any]:
    """
    Summarize how closely predicted PD tracks actual default rate across time
    periods. A period is "flagged" if |actual - predicted| exceeds gap_threshold
    (default 5pp). Useful for spotting stress periods / regime shifts the model
    under- or over-estimates.
    """
    grouped = _temporal_grouped(dates, y_true, y_proba, freq=freq)

    if grouped.empty:
        return {
            "n_periods_total": 0,
            "n_periods_flagged": 0,
            "mean_absolute_gap": 0.0,
            "max_underestimation_period": None,
            "max_underestimation_gap": 0.0,
            "max_overestimation_period": None,
            "max_overestimation_gap": 0.0,
            "by_period": [],
        }

    flagged = grouped[grouped["abs_gap"] > gap_threshold]

    # Underestimation: actual > predicted (gap > 0) — model understates risk.
    under = grouped[grouped["gap"] > 0]
    over = grouped[grouped["gap"] < 0]

    max_under_row = under.loc[under["gap"].idxmax()] if not under.empty else None
    max_over_row = over.loc[over["gap"].idxmin()] if not over.empty else None

    return {
        "n_periods_total": int(len(grouped)),
        "n_periods_flagged": int(len(flagged)),
        "mean_absolute_gap": float(grouped["abs_gap"].mean()),
        "max_underestimation_period": str(max_under_row["period_label"]) if max_under_row is not None else None,
        "max_underestimation_gap": float(max_under_row["gap"]) if max_under_row is not None else 0.0,
        "max_overestimation_period": str(max_over_row["period_label"]) if max_over_row is not None else None,
        "max_overestimation_gap": float(abs(max_over_row["gap"])) if max_over_row is not None else 0.0,
        "by_period": [
            {
                "period": row["period_label"],
                "n": int(row["n"]),
                "actual_rate": round(float(row["actual_rate"]), 4),
                "predicted_rate": round(float(row["predicted_rate"]), 4),
                "gap": round(float(row["gap"]), 4),
                "flagged": bool(row["abs_gap"] > gap_threshold),
            }
            for _, row in grouped.iterrows()
        ],
    }


def compute_temporal_analysis_bundle(
    dates,
    y_true: np.ndarray,
    y_proba: np.ndarray,
    date_columns: Optional[List[str]] = None,
    gap_threshold: float = 0.05,
) -> Dict[str, Any]:
    """
    Bundle temporal-stability summaries across Monthly/Quarterly/Yearly
    granularity into the shape the Evaluation page's "Temporal" tab expects:
    a default (Quarterly) plot_data/summary pair plus per-frequency variants,
    so the frontend's frequency toggle needs no extra round-trip to the API.
    """
    freq_options = ["Monthly", "Quarterly", "Yearly"]
    plot_data_by_freq: Dict[str, List[Dict[str, Any]]] = {}
    summaries_by_freq: Dict[str, Dict[str, Any]] = {}

    for freq in freq_options:
        summary = compute_temporal_stability_summary(dates, y_true, y_proba, freq=freq, gap_threshold=gap_threshold)
        plot_data_by_freq[freq] = summary.pop("by_period")
        summaries_by_freq[freq] = summary

    default_freq = "Quarterly"
    return {
        "date_columns": date_columns or [],
        "frequency_options": freq_options,
        "plot_data": plot_data_by_freq.get(default_freq, []),
        "plot_data_by_freq": plot_data_by_freq,
        "summary": summaries_by_freq.get(default_freq),
        "summaries_by_freq": summaries_by_freq,
    }
