import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent / "Credit-Risk-Poc-main"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _expected_roc_curve(y_true, y_proba):
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    return [{"fpr": float(x), "tpr": float(y)} for x, y in zip(fpr.tolist(), tpr.tolist())]


def _expected_pr_curve(y_true, y_proba):
    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    return [{"recall": float(r), "precision": float(p)} for p, r in zip(precision.tolist(), recall.tolist())]


def _expected_threshold_analysis(y_true, y_proba):
    thresholds = np.linspace(0.01, 0.99, 99)
    rows = []
    for threshold in thresholds:
        y_pred_t = (y_proba >= threshold).astype(int)
        rows.append({
            "threshold": float(round(threshold, 2)),
            "precision": float(precision_score(y_true, y_pred_t, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred_t, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred_t, zero_division=0)),
        })
    return rows


def _expected_gain_chart(y_true, y_proba, n_deciles=10):
    df = np.column_stack([y_proba, y_true.astype(int)])
    scores = df[:, 0]
    actual = df[:, 1]
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


def test_evaluate_module_matches_reference_behavior_for_binary_helpers():
    legacy = _load_module("legacy_eval", SOURCE_ROOT / "evaluate.py")
    current = _load_module("current_eval", ROOT / "evaluate.py")

    y_true = np.array([0, 1, 0, 1, 0, 1], dtype=int)
    y_proba = np.array([0.1, 0.9, 0.2, 0.8, 0.3, 0.7], dtype=float)
    dates = ["2023-01-01", "2023-01-15", "2023-02-01", "2023-02-15", "2023-03-01", "2023-03-15"]

    assert current.compute_binary_metrics(y_true, None, y_proba, threshold=0.5) == legacy.compute_binary_metrics(
        y_true, None, y_proba, threshold=0.5
    )
    assert current.compute_roc_curve(y_true, y_proba) == _expected_roc_curve(y_true, y_proba)
    assert current.compute_pr_curve(y_true, y_proba) == _expected_pr_curve(y_true, y_proba)
    assert current.compute_threshold_analysis(y_true, y_proba) == _expected_threshold_analysis(y_true, y_proba)
    assert current.compute_gain_chart(y_true, y_proba) == _expected_gain_chart(y_true, y_proba)
    assert current.compute_temporal_stability_summary(dates, y_true, y_proba, freq="Monthly") == legacy.compute_temporal_stability_summary(
        dates, y_true, y_proba, freq="Monthly"
    )


def test_evaluation_helpers_gracefully_handle_missing_probabilities():
    current = _load_module("current_eval", ROOT / "evaluate.py")

    y_true = np.array([0, 1, 0, 1], dtype=int)
    assert current.compute_roc_curve(y_true, None) == []
    assert current.compute_pr_curve(y_true, None) == []
    assert current.compute_threshold_analysis(y_true, None) == []
    assert current.compute_score_distribution(y_true, None) == []
    assert current.compute_gain_chart(y_true, None) == []


def test_streamlit_plot_data_matches_backend_artifact_contract():
    source = _load_module("source_eval", SOURCE_ROOT / "evaluate.py")
    current = _load_module("current_eval", ROOT / "evaluate.py")

    y_true = np.array([0, 1, 0, 1, 0, 1], dtype=int)
    y_proba = np.array([0.1, 0.9, 0.2, 0.8, 0.3, 0.7], dtype=float)

    roc_fig = source.plot_roc_curve(y_true, y_proba)
    pr_fig = source.plot_pr_curve(y_true, y_proba)
    threshold_fig = source.plot_threshold_analysis(y_true, y_proba)

    assert current.compute_roc_curve(y_true, y_proba) == [
        {"fpr": float(x), "tpr": float(y)} for x, y in zip(roc_fig.data[0].x, roc_fig.data[0].y)
    ]
    assert current.compute_pr_curve(y_true, y_proba) == [
        {"recall": float(x), "precision": float(y)} for x, y in zip(pr_fig.data[0].x, pr_fig.data[0].y)
    ]
    expected_threshold_rows = [
        {
            "threshold": float(round(threshold, 2)),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }
        for threshold, precision, recall, f1 in zip(
            threshold_fig.data[0].x,
            threshold_fig.data[0].y,
            threshold_fig.data[1].y,
            threshold_fig.data[2].y,
        )
    ]
    assert current.compute_threshold_analysis(y_true, y_proba) == expected_threshold_rows


def test_binary_metrics_accept_single_column_probabilities():
    current = _load_module("current_eval", ROOT / "evaluate.py")

    y_true = np.array([0, 1, 0, 1], dtype=int)
    y_proba = np.array([[0.1], [0.9], [0.2], [0.8]], dtype=float)
    metrics = current.compute_binary_metrics(y_true, None, y_proba, threshold=0.5)

    assert metrics["accuracy"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert current.compute_roc_curve(y_true, y_proba)[0]["fpr"] == 0.0


def test_detect_task_type_treats_single_class_binary_like_targets_as_binary():
    from utils import detect_task_type

    series = pd.Series([0, 0, 0], dtype=int)
    assert detect_task_type(series) == "binary"
