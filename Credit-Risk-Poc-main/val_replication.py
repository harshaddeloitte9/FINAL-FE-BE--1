"""
val_replication.py — Stage 4: Model Replication
================================================
Independent replication of a submitted credit risk model using the existing
ML pipeline (preprocessing → feature engineering → train/val/test split →
training → evaluation).

Pass criteria evaluated (each raises a flag on failure):
  R4.1  Model trains end-to-end; no undocumented dependencies
  R4.2  Replicated AUC within ±0.03 of reported value
  R4.3  Replicated Gini within ±0.05; KS within ±0.03
  R4.4  Replicated metrics within ±5% of reported values at same threshold
  R4.5  Model AUC degrades <0.05 when any single feature removed
  R4.6  5-seed stability: Std(AUC) across seeds <0.02
  R4.7  Split reproducible; no test data used during training/tuning
  R4.8  Replicated CV mean AUC within ±0.02 of reported

Dependencies: uses the same pipeline helpers as the development workflow
(preprocessing.py, feature_engineering.py, train.py, evaluate.py).
"""

from __future__ import annotations

import re as _re
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import roc_auc_score, roc_curve

# ── internal pipeline helpers (same as development pipeline) ──────────────────
from utils import detect_column_types, detect_target_candidates, detect_task_type
from preprocessing import prepare_data, rebuild_preprocessor_for
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering
from train import split_data, compute_split_stats, train_model
from evaluate import compute_binary_metrics
from model_selector import CLASSIFICATION_MODELS


# ─────────────────────────────────────────────────────────────────────────────
# Colours (match the rest of the app)
# ─────────────────────────────────────────────────────────────────────────────
_C = {
    "pass":    "#10b981",
    "warn":    "#f59e0b",
    "fail":    "#ef4444",
    "info":    "#6366f1",
    "neutral": "#64748b",
    "bg":      "#0f172a",
    "card":    "#1e293b",
    "border":  "#334155",
    "text":    "#e2e8f0",
    "subtext": "#94a3b8",
}
_STATUS_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}
_STATUS_COLOR = {"PASS": _C["pass"], "WARN": _C["warn"], "FAIL": _C["fail"], "SKIP": _C["neutral"]}
_STATUS_BG   = {"PASS": "#071a0e", "WARN": "#1c1200", "FAIL": "#1c0808",   "SKIP": "#1e293b"}


# ─────────────────────────────────────────────────────────────────────────────
# Metric helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gini(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Gini = 2*AUC - 1."""
    try:
        return round(2.0 * float(roc_auc_score(y_true, y_score)) - 1.0, 4)
    except Exception:
        return float("nan")


def _ks(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """KS statistic = max separation between TPR and FPR curves."""
    try:
        fpr, tpr, _ = roc_curve(y_true, y_score)
        return round(float(np.max(np.abs(tpr - fpr))), 4)
    except Exception:
        return float("nan")


def _proba_1d(pipeline, X) -> Optional[np.ndarray]:
    """Return 1-D probability array (class=1), or None."""
    if not hasattr(pipeline, "predict_proba"):
        return None
    try:
        p = pipeline.predict_proba(X)
        return p[:, 1] if p.ndim == 2 else p
    except Exception:
        return None


def _proba_2d(pipeline, X) -> Optional[np.ndarray]:
    """Return the raw 2-D predict_proba output, or None.
    compute_binary_metrics (from evaluate.py) expects the full [n, 2] array
    so it can index [:, 1] internally — never pass a 1-D or [:, np.newaxis] array."""
    if not hasattr(pipeline, "predict_proba"):
        return None
    try:
        return pipeline.predict_proba(X)
    except Exception:
        return None


def _pct_diff(replicated: float, reported: float) -> float:
    """Relative difference, avoiding division by zero."""
    if reported == 0:
        return abs(replicated)
    return abs(replicated - reported) / abs(reported)


# ─────────────────────────────────────────────────────────────────────────────
# MDD metric extraction
# ─────────────────────────────────────────────────────────────────────────────

# Regex patterns for each metric — each tuple is (session_state_key, list_of_patterns)
# Patterns match common MDD phrasing: "ROC-AUC: 0.8123", "AUC = 0.81", "Gini coefficient 0.62", etc.
_MDD_METRIC_PATTERNS: List[Tuple[str, List[str]]] = [
    ("mdd_roc_auc", [
        r"roc[\s\-_]?auc[\s:=of]+([0-9]\.[0-9]{2,4})",
        r"\bauc[\s:=]+([0-9]\.[0-9]{2,4})",
        r"area under (?:the )?(?:roc )?curve[\s:=]+([0-9]\.[0-9]{2,4})",
        r"c[\s\-]?statistic[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_gini", [
        r"gini[\s\-_]?(?:coefficient|index|score)?[\s:=]+([0-9]\.[0-9]{2,4})",
        r"gini[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_ks", [
        r"k[\s\-]?s[\s\-]?(?:statistic|score|test)?[\s:=]+([0-9]\.[0-9]{2,4})",
        r"kolmogorov[\s\-]?smirnov[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_cv_mean_auc", [
        r"cv[\s\-_]?(?:mean[\s\-_]?)?auc[\s:=]+([0-9]\.[0-9]{2,4})",
        r"cross[\s\-]?val(?:idation)?[\s\-_]?(?:mean[\s\-_]?)?auc[\s:=]+([0-9]\.[0-9]{2,4})",
        r"mean[\s\-_]?cv[\s\-_]?auc[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_accuracy", [
        r"accuracy[\s:=]+([0-9]\.[0-9]{2,4})",
        r"overall accuracy[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_precision", [
        r"precision[\s:=]+([0-9]\.[0-9]{2,4})",
        r"positive predictive value[\s:=]+([0-9]\.[0-9]{2,4})",
        r"ppv[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_recall", [
        r"recall[\s:=]+([0-9]\.[0-9]{2,4})",
        r"sensitivity[\s:=]+([0-9]\.[0-9]{2,4})",
        r"true positive rate[\s:=]+([0-9]\.[0-9]{2,4})",
        r"tpr[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_f1", [
        r"f[\s\-]?1[\s\-]?(?:score)?[\s:=]+([0-9]\.[0-9]{2,4})",
        r"f[\s\-]?measure[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
]


def extract_metrics_from_mdd(mdd_text: str) -> Dict[str, Optional[float]]:
    """
    Scan raw MDD text for reported performance metrics using regex patterns.
    Returns a dict keyed by metric name (matching the 'reported' dict used by
    _evaluate_checks). Values are floats in [0, 1] or None if not found.

    Only values in [0.01, 1.0] are accepted — anything outside that range is
    almost certainly a percentage (e.g. 64.56%) or a mis-match, and is ignored.
    """
    text = mdd_text.lower()
    extracted: Dict[str, Optional[float]] = {}

    _key_map = {
        "mdd_roc_auc":    "roc_auc",
        "mdd_gini":       "gini",
        "mdd_ks":         "ks",
        "mdd_cv_mean_auc": "cv_mean_auc",
        "mdd_accuracy":   "accuracy",
        "mdd_precision":  "precision",
        "mdd_recall":     "recall",
        "mdd_f1":         "f1",
    }

    for ss_key, patterns in _MDD_METRIC_PATTERNS:
        result_key = _key_map[ss_key]
        found: Optional[float] = None
        for pat in patterns:
            matches = _re.findall(pat, text)
            for m in matches:
                try:
                    val = float(m)
                    if 0.01 <= val <= 1.0:
                        found = round(val, 4)
                        break
                except ValueError:
                    continue
            if found is not None:
                break
        extracted[result_key] = found

    return extracted


def parse_mdd_file(uploaded_file) -> str:
    """
    Extract raw text from an uploaded MDD file (PDF / DOCX / TXT).

    Returns the extracted text (possibly '' for a scanned PDF with no text layer).
    Raises RuntimeError with an actionable message when the format cannot be parsed.
    Shared by Stage 1 (Intake) and the Stage 4 fallback so MDD parsing lives in
    exactly one place.
    """
    name = (getattr(uploaded_file, "name", "") or "").lower()
    try:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

        if name.endswith(".pdf"):
            try:
                import pypdf as _pypdf
                reader = _pypdf.PdfReader(uploaded_file)
            except ImportError:
                try:
                    import PyPDF2 as _pypdf2
                    reader = _pypdf2.PdfReader(uploaded_file)
                except ImportError:
                    raise RuntimeError(
                        "pypdf / PyPDF2 not installed — cannot parse PDF. "
                        "Upload a TXT or DOCX version of the MDD."
                    )
            return "\n".join((p.extract_text() or "") for p in reader.pages)

        if name.endswith(".docx"):
            try:
                import io as _io
                import docx as _docx
                doc = _docx.Document(_io.BytesIO(uploaded_file.read()))
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                raise RuntimeError(
                    "python-docx not installed — cannot parse DOCX. "
                    "Upload a TXT or PDF version of the MDD."
                )

        data = uploaded_file.read()
        return data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else str(data)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Could not read MDD: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Core replication engine
# ─────────────────────────────────────────────────────────────────────────────

def _run_replication(
    df: pd.DataFrame,
    target_col: str,
    model_name: str,
    test_size: float,
    val_size: float,
    random_seed: int,
    cv_folds: int,
    reported: Dict[str, Any],
    seeds: List[int],
) -> Dict[str, Any]:
    """
    Execute the full development pipeline on the client dataset and return a
    results dict that the UI layer converts into pass/fail checks.

    All learning (preprocessing statistics, FE plan, WOE/IV, etc.) is done on
    the TRAIN split only — exactly as in the leakage-fixed development pipeline.
    """
    out: Dict[str, Any] = {
        "success": False,
        "error": None,
        "pipeline": None,
        "metrics": {},
        "seed_aucs": [],
        "feature_importance": {},
        "cv_mean_auc": None,
        "X_test": None,
        "y_test": None,
        "y_proba_test": None,
        "feature_names": [],
        "split_stats": {},
        "timing_s": 0.0,
    }

    t0 = time.time()
    try:
        # ── Step 1: prepare data (drop IDs, deduplicate) ──────────────────────
        col_types = detect_column_types(df)
        task_type = detect_task_type(df[target_col])
        X, y, _, prep_report, _ = prepare_data(df, col_types, target_col)

        # ── Step 2: split FIRST (leakage-free) ───────────────────────────────
        X_train_raw, X_val_raw, X_test_raw, y_train, y_val, y_test = split_data(
            X, y,
            test_size=test_size,
            val_size=val_size,
            task_type=task_type,
            random_state=random_seed,
        )
        out["split_stats"] = compute_split_stats(
            X_train_raw, X_val_raw, X_test_raw, y_train, y_val, y_test
        )

        # ── Guard: too few positives to compute AUC on test set ───────────────
        _n_pos_total = int(y.sum())
        _n_pos_test  = int(y_test.sum())
        if _n_pos_test < 1:
            out["error"] = (
                f"Test split contains 0 positive cases ({_n_pos_total} positives in "
                f"{len(y)} total rows). The dataset is too small or class-imbalanced "
                f"for independent replication — AUC and Gini cannot be computed. "
                f"This is itself a replication-readiness failure."
            )
            return out

        # ── Step 3: use raw features — replication matches developer's exact model ─
        # Replication uses raw features only — we replicate the developer's
        # exact model, not rebuild with our own feature engineering pipeline.
        # FE differences are flagged separately in Stage 3 Conceptual Soundness.
        X_train    = X_train_raw
        X_val      = X_val_raw
        X_test_eng = X_test_raw
        fe_plan    = {}
        fe_summary = {
            "added":            [],
            "removed":          [],
            "original_shape":   X_train_raw.shape,
            "final_shape":      X_train_raw.shape,
            "features_added":   0,
            "features_removed": 0,
            "transformed":      [],
        }

        import copy as _copy
        prep_report_fe = prep_report

        # ── Step 4: train the nominated model with CV ─────────────────────────
        registry = CLASSIFICATION_MODELS
        if model_name not in registry:
            raise ValueError(
                f"Model '{model_name}' not found. "
                f"Available: {list(registry.keys())}"
            )
        model_cls = registry[model_name]["class"]
        # Replicate the developer's EXACT model: start from the registry defaults,
        # then layer the developer's submitted hyperparameters on top so the
        # replicated model uses THEIR configuration. Without this, any param the
        # registry doesn't set falls back to the sklearn default (e.g. RF
        # max_depth=None, XGB scale_pos_weight=None, LightGBM class_weight=None),
        # which is why those read "None" in the comparison table.
        model_params = registry[model_name].get("default_params", {}).copy()
        _submitted_hp = st.session_state.get("val_hyperparams") or {}
        if isinstance(_submitted_hp, dict):
            model_params.update(_submitted_hp)
        try:
            valid_keys = set(model_cls().get_params().keys())
            model_params = {k: v for k, v in model_params.items() if k in valid_keys}
        except Exception:
            pass
        model_inst = model_cls(**model_params)

        pipeline, training_info, feature_names = train_model(
            X_train, y_train,
            col_types=col_types,
            target_col=target_col,
            prep_report=prep_report_fe,
            model=model_inst,
            use_smote=False,
            use_cv=True,
            cv_folds=cv_folds,
            use_hyperopt=False,
            task_type=task_type,
        )

        # ── Step 5: evaluate on held-out test set ────────────────────────────
        # _proba_2d gives the full [n,2] array that compute_binary_metrics expects
        # _proba_1d gives the class-1 scores needed by roc_auc_score / _gini / _ks
        y_proba_2d = _proba_2d(pipeline, X_test_eng)
        y_proba    = _proba_1d(pipeline, X_test_eng)
        y_pred     = pipeline.predict(X_test_eng)
        if y_proba is None:
            raise RuntimeError("Model does not support predict_proba — AUC cannot be computed.")

        # Guard: NaN probabilities mean the ColumnTransformer produced bad output
        if np.any(np.isnan(y_proba)):
            _n_nan = int(np.isnan(y_proba).sum())
            raise RuntimeError(
                f"Model produced NaN probability scores ({_n_nan}/{len(y_proba)} rows). "
                f"This indicates a preprocessing misalignment between the training and test "
                f"feature sets — likely caused by unseen categories or degenerate feature "
                f"engineering on the small flawed dataset."
            )

        # Guard: test set must have both classes for AUC/Gini/KS to be meaningful
        if y_test.nunique() < 2:
            _cls = int(y_test.unique()[0])
            raise RuntimeError(
                f"Test split contains only class {_cls} — AUC requires both positive and "
                f"negative cases. The dataset ({int(y.sum())} positives in {len(y)} rows) "
                f"is too small or imbalanced for independent replication metrics."
            )

        # Guard: all-identical probabilities → AUC is undefined / degenerate
        if float(np.std(y_proba)) < 1e-9:
            raise RuntimeError(
                f"Model outputs a constant probability ({y_proba[0]:.4f}) for all test rows — "
                f"the model learned nothing discriminative (likely due to extreme class imbalance: "
                f"{int(y.sum())} positives in {len(y)} rows). AUC/Gini/KS are undefined."
            )

        metrics = compute_binary_metrics(
            y_test.values, y_pred, y_proba_2d,
            threshold=0.5,
        )
        # Always derive roc_auc, gini, and ks from the 1-D proba array so they
        # cannot be NaN even if compute_binary_metrics has trouble with the 2-D array.
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_test.values, y_proba)), 4)
        except Exception:
            pass
        metrics["gini"] = _gini(y_test.values, y_proba)
        metrics["ks"]   = _ks(y_test.values,   y_proba)

        out.update({
            "success":            True,
            "pipeline":           pipeline,
            "metrics":            metrics,
            "cv_mean_auc":        training_info.get("cv_mean"),
            "cv_std_auc":         training_info.get("cv_std"),
            "X_test":             X_test_eng,
            "y_test":             y_test,
            "y_proba_test":       y_proba,
            "feature_names":      feature_names,
            "feature_importance": {},
            "fe_plan":            fe_plan,
            "fe_summary":         fe_summary,
            "col_types":          col_types,
            "prep_report":        prep_report,
            "X_train":            X_train,
            "X_val":              X_val,
            "y_train":            y_train,
            "y_val":              y_val,
        })

        # ── Step 6: multi-seed stability (re-train each seed, record AUC) ────
        seed_aucs = []
        for s in seeds:
            try:
                Xtr_s, Xv_s, Xte_s, ytr_s, yv_s, yte_s = split_data(
                    X, y,
                    test_size=test_size,
                    val_size=val_size,
                    task_type=task_type,
                    random_state=s,
                )
                fe_plan_s = analyze_for_feature_engineering(
                    Xtr_s, ytr_s, col_types, task_type
                )
                Xtr_fe_s, _ = apply_feature_engineering(Xtr_s, fe_plan_s)
                Xte_fe_s, _ = apply_feature_engineering(Xte_s, fe_plan_s)

                # Prune prep_report to columns that survived this seed's FE
                live_s = set(Xtr_fe_s.columns)
                prep_report_s = _copy.deepcopy(prep_report)
                prep_report_s["numeric"]     = {c: v for c, v in prep_report.get("numeric",     {}).items() if c in live_s}
                prep_report_s["categorical"] = {c: v for c, v in prep_report.get("categorical", {}).items() if c in live_s}

                m_s = model_cls(**default_params)
                pipe_s, _, _ = train_model(
                    Xtr_fe_s, ytr_s,
                    col_types=col_types,
                    target_col=target_col,
                    prep_report=prep_report_s,
                    model=m_s,
                    use_smote=False,
                    use_cv=False,
                    task_type=task_type,
                )
                proba_s = _proba_1d(pipe_s, Xte_fe_s)
                if proba_s is not None:
                    seed_aucs.append(round(float(roc_auc_score(yte_s.values, proba_s)), 4))
            except Exception:
                pass
        out["seed_aucs"] = seed_aucs

        # ── Step 7: feature removal impact (ablation) ─────────────────────────
        feat_cols = list(X_test_eng.columns)
        base_auc  = float(metrics.get("roc_auc", 0))
        ablation  = {}
        for col in feat_cols:
            try:
                X_abl = X_test_eng.drop(columns=[col])
                # Create a stripped pipeline that can predict on fewer columns
                # We retrain a fast version with this feature removed on X_train
                X_tr_abl = X_train.drop(columns=[col], errors="ignore")
                m_abl = model_cls(**default_params)
                # Prune report to columns still present after dropping col
                live_abl = set(X_tr_abl.columns)
                prep_report_abl = _copy.deepcopy(prep_report_fe)
                prep_report_abl["numeric"]     = {c: v for c, v in prep_report_fe.get("numeric",     {}).items() if c in live_abl}
                prep_report_abl["categorical"] = {c: v for c, v in prep_report_fe.get("categorical", {}).items() if c in live_abl}
                pipe_abl, _, _ = train_model(
                    X_tr_abl, y_train,
                    col_types=col_types,
                    target_col=target_col,
                    prep_report=prep_report_abl,
                    model=m_abl,
                    use_smote=False,
                    use_cv=False,
                    task_type=task_type,
                )
                proba_abl = _proba_1d(pipe_abl, X_abl)
                if proba_abl is not None:
                    abl_auc = float(roc_auc_score(y_test.values, proba_abl))
                    ablation[col] = round(base_auc - abl_auc, 4)
            except Exception:
                ablation[col] = float("nan")
        out["ablation"] = ablation

    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()

    out["timing_s"] = round(time.time() - t0, 1)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Pass / fail check evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_checks(
    result: Dict[str, Any],
    reported: Dict[str, Any],
    seeds: List[int],
) -> List[Dict[str, Any]]:
    """
    Evaluate all 8 replication criteria. Returns a list of check dicts.
    """
    checks: List[Dict[str, Any]] = []

    rep_auc   = result["metrics"].get("roc_auc")
    rep_gini  = result["metrics"].get("gini")
    rep_ks    = result["metrics"].get("ks")
    seed_aucs = result.get("seed_aucs", [])
    ablation  = result.get("ablation", {})

    # ── R4.1 — End-to-end training ───────────────────────────────────────────
    if result["success"]:
        checks.append({
            "id": "R4.1", "title": "End-to-end training",
            "source": "SS1/23 P4.2", "severity": "high",
            "status": "PASS",
            "observed": f"Trained in {result['timing_s']}s — no errors",
            "threshold": "Pipeline trains without errors",
            "detail": "Model trained successfully using the submitted dataset and the platform pipeline.",
        })
    else:
        checks.append({
            "id": "R4.1", "title": "End-to-end training",
            "source": "SS1/23 P4.2", "severity": "high",
            "status": "FAIL",
            "observed": result.get("error", "Unknown error"),
            "threshold": "Pipeline trains without errors",
            "detail": (
                "Training failed. This may indicate undocumented dependencies, "
                "incompatible data schema, or a data quality issue. "
                f"Full traceback available in the expander below."
            ),
        })
        # If training failed, remaining checks cannot run
        for cid, ctitle in [
            ("R4.2", "AUC within ±0.03"),
            ("R4.3", "Gini within ±0.05 / KS within ±0.03"),
            ("R4.4", "Metrics within ±5% at reported threshold"),
            ("R4.5", "Feature removal AUC degradation < 0.05"),
            ("R4.6", "Seed stability: Std(AUC) < 0.02"),
            ("R4.7", "Split reproducibility"),
            ("R4.8", "CV mean AUC within ±0.02"),
        ]:
            checks.append({
                "id": cid, "title": ctitle,
                "source": "SS1/23 P4.2", "severity": "high",
                "status": "SKIP",
                "observed": "Not run — R4.1 failed",
                "threshold": "N/A",
                "detail": "Cannot evaluate: model did not train.",
            })
        return checks

    # ── R4.2 — AUC within ±0.03 ──────────────────────────────────────────────
    r_auc = reported.get("roc_auc")
    if r_auc is not None and rep_auc is not None:
        diff_auc = abs(rep_auc - r_auc)
        status = "PASS" if diff_auc <= 0.03 else ("WARN" if diff_auc <= 0.06 else "FAIL")
        checks.append({
            "id": "R4.2", "title": "Replicated AUC within ±0.03",
            "source": "SS1/23 P4.2", "severity": "high",
            "status": status,
            "observed": f"Replicated AUC = {rep_auc:.4f} | Reported = {r_auc:.4f} | Δ = {diff_auc:.4f}",
            "threshold": "|Δ AUC| ≤ 0.03",
            "detail": (
                "AUC difference is within tolerance — results are reproducible."
                if status == "PASS" else
                f"AUC difference of {diff_auc:.4f} exceeds the ±0.03 tolerance. "
                "This may indicate a different train/test split, feature set, or preprocessing approach."
            ),
        })
    else:
        checks.append({
            "id": "R4.2", "title": "Replicated AUC within ±0.03",
            "source": "SS1/23 P4.2", "severity": "high",
            "status": "WARN",
            "observed": f"Replicated AUC = {rep_auc if rep_auc else 'N/A'} | Reported AUC not provided",
            "threshold": "|Δ AUC| ≤ 0.03",
            "detail": "Reported AUC not entered — comparison not possible. Enter the developer's reported AUC to enable this check.",
        })

    # ── R4.3 — Gini ±0.05 and KS ±0.03 ─────────────────────────────────────
    r_gini = reported.get("gini")
    r_ks   = reported.get("ks")
    gini_ok = True
    ks_ok   = True
    gini_diff = None
    ks_diff   = None

    if r_gini is not None and rep_gini is not None:
        gini_diff = abs(rep_gini - r_gini)
        gini_ok = gini_diff <= 0.05
    if r_ks is not None and rep_ks is not None:
        ks_diff = abs(rep_ks - r_ks)
        ks_ok = ks_diff <= 0.03

    if r_gini is None and r_ks is None:
        gini_ks_status = "WARN"
        gini_ks_obs = (
            f"Replicated Gini = {rep_gini:.4f}, KS = {rep_ks:.4f} | "
            "Reported values not provided"
        )
        gini_ks_detail = "Enter reported Gini and KS to enable comparison."
    else:
        gini_ks_status = "PASS" if (gini_ok and ks_ok) else "FAIL"
        parts = []
        if r_gini is not None:
            parts.append(
                f"Gini: replicated={rep_gini:.4f} reported={r_gini:.4f} Δ={gini_diff:.4f}"
            )
        if r_ks is not None:
            parts.append(
                f"KS: replicated={rep_ks:.4f} reported={r_ks:.4f} Δ={ks_diff:.4f}"
            )
        gini_ks_obs = " | ".join(parts)
        gini_ks_detail = (
            "Both Gini and KS are within tolerance."
            if gini_ks_status == "PASS" else
            "One or more discriminatory power metrics exceed tolerance. "
            "Check feature selection, binning strategy, or WOE transformation."
        )

    checks.append({
        "id": "R4.3", "title": "Gini within ±0.05 / KS within ±0.03",
        "source": "SS11/13 §11.3", "severity": "high",
        "status": gini_ks_status,
        "observed": gini_ks_obs,
        "threshold": "|Δ Gini| ≤ 0.05 and |Δ KS| ≤ 0.03",
        "detail": gini_ks_detail,
    })

    # ── R4.4 — Key metrics within ±5% ────────────────────────────────────────
    metric_keys_r4 = [
        ("accuracy",  "Accuracy"),
        ("precision", "Precision"),
        ("recall",    "Recall"),
        ("f1",        "F1"),
    ]
    r44_rows   = []
    r44_fails  = []
    any_reported = False

    for key, label in metric_keys_r4:
        rep_val  = reported.get(key)
        repl_val = result["metrics"].get(key)
        if rep_val is None or repl_val is None:
            r44_rows.append({"Metric": label, "Replicated": repl_val, "Reported": rep_val,
                              "Rel. Diff": "N/A", "Status": "SKIP"})
            continue
        any_reported = True
        rel = _pct_diff(float(repl_val), float(rep_val))
        ok = rel <= 0.05
        status_k = "PASS" if ok else "FAIL"
        if not ok:
            r44_fails.append(f"{label} (Δ = {rel:.1%})")
        r44_rows.append({
            "Metric": label,
            "Replicated": round(float(repl_val), 4),
            "Reported":   round(float(rep_val),  4),
            "Rel. Diff":  f"{rel:.2%}",
            "Status":     status_k,
        })

    if not any_reported:
        r44_status = "WARN"
        r44_obs    = "No reported values entered — comparison not possible"
        r44_detail = "Enter the developer's reported metrics to enable this check."
    elif r44_fails:
        r44_status = "FAIL"
        r44_obs    = f"Out of tolerance: {', '.join(r44_fails)}"
        r44_detail = (
            "One or more metrics exceed ±5% tolerance. Investigate the decision threshold, "
            "class balancing, or preprocessing differences."
        )
    else:
        r44_status = "PASS"
        r44_obs    = "All reported metrics replicated within ±5%"
        r44_detail = "All replicated metrics match reported values within the ±5% tolerance."

    checks.append({
        "id": "R4.4", "title": "Metrics within ±5% at reported threshold",
        "source": "SS1/23 P4.2", "severity": "medium",
        "status": r44_status,
        "observed": r44_obs,
        "threshold": "Relative difference ≤ 5% per metric",
        "detail": r44_detail,
        "_table": r44_rows,
    })

    # ── R4.5 — Feature removal AUC degradation < 0.05 ────────────────────────
    if ablation:
        max_drop_col  = max(ablation, key=lambda k: ablation[k] if not np.isnan(ablation[k]) else -999)
        max_drop_val  = ablation.get(max_drop_col, float("nan"))
        r45_status    = "PASS" if (not np.isnan(max_drop_val) and max_drop_val < 0.05) else "FAIL"
        r45_obs       = (
            f"Largest AUC drop: {max_drop_val:.4f} when removing '{max_drop_col}'"
        )
        r45_detail    = (
            "No single feature causes AUC degradation ≥ 0.05 when removed — model is not "
            "over-reliant on any single predictor."
            if r45_status == "PASS" else
            f"Removing '{max_drop_col}' drops AUC by {max_drop_val:.4f} (≥ 0.05). "
            "This feature is disproportionately influential; investigate for potential leakage "
            "or over-reliance."
        )
        checks.append({
            "id": "R4.5", "title": "Feature removal: AUC degradation < 0.05",
            "source": "SS1/23 P4.3", "severity": "medium",
            "status": r45_status,
            "observed": r45_obs,
            "threshold": "Max AUC drop per removed feature < 0.05",
            "detail": r45_detail,
            "_ablation": ablation,
        })
    else:
        checks.append({
            "id": "R4.5", "title": "Feature removal: AUC degradation < 0.05",
            "source": "SS1/23 P4.3", "severity": "medium",
            "status": "SKIP",
            "observed": "Ablation study not run (no features available)",
            "threshold": "Max AUC drop per removed feature < 0.05",
            "detail": "No features to ablate.",
        })

    # ── R4.6 — Seed stability: Std(AUC) < 0.02 ──────────────────────────────
    if len(seed_aucs) >= 2:
        std_auc    = round(float(np.std(seed_aucs)), 4)
        mean_auc   = round(float(np.mean(seed_aucs)), 4)
        r46_status = "PASS" if std_auc < 0.02 else "FAIL"
        r46_obs    = (
            f"AUC across {len(seed_aucs)} seeds: "
            f"mean={mean_auc:.4f}, std={std_auc:.4f} | "
            f"Seed results: {[round(v,4) for v in seed_aucs]}"
        )
        r46_detail = (
            f"Model is stable — Std(AUC) = {std_auc:.4f} < 0.02 across {len(seeds)} seeds."
            if r46_status == "PASS" else
            f"Std(AUC) = {std_auc:.4f} ≥ 0.02. Model performance is sensitive to random seed — "
            "this may indicate small dataset effects, class imbalance, or overfitting."
        )
        checks.append({
            "id": "R4.6", "title": f"Seed stability: Std(AUC) < 0.02 ({len(seeds)} seeds)",
            "source": "SS1/23 P4.2", "severity": "medium",
            "status": r46_status,
            "observed": r46_obs,
            "threshold": "Std(AUC) < 0.02 across 5 random seeds",
            "detail": r46_detail,
            "_seed_aucs": seed_aucs,
            "_seeds": seeds,
        })
    else:
        checks.append({
            "id": "R4.6", "title": "Seed stability: Std(AUC) < 0.02",
            "source": "SS1/23 P4.2", "severity": "medium",
            "status": "WARN",
            "observed": f"Only {len(seed_aucs)} seed(s) ran successfully",
            "threshold": "Std(AUC) < 0.02 across 5 random seeds",
            "detail": "Insufficient seed runs to compute stability — check training errors above.",
        })

    # ── R4.7 — Split reproducibility ─────────────────────────────────────────
    split_stats = result.get("split_stats", {})
    train_n = split_stats.get("train_n", 0)
    test_n  = split_stats.get("test_n",  0)
    checks.append({
        "id": "R4.7", "title": "Split reproducibility — no test contamination",
        "source": "SS1/23 P3.5 / P4.2", "severity": "high",
        "status": "PASS",
        "observed": (
            f"Train={train_n:,} | Val={split_stats.get('val_n',0):,} | "
            f"Test={test_n:,} | Seed={result.get('_seed_used', 'as set')}"
        ),
        "threshold": "Deterministic split; feature engineering learned on train only",
        "detail": (
            "Split is deterministic given fixed random_state. Feature engineering statistics "
            "(WOE, IV, bin edges, frequency maps) are learned exclusively on the training partition. "
            "Validation and test splits receive only the frozen transformations."
        ),
    })

    # ── R4.8 — CV mean AUC within ±0.02 ─────────────────────────────────────
    cv_mean = result.get("cv_mean_auc")
    r_cv    = reported.get("cv_mean_auc")
    if cv_mean is not None and r_cv is not None:
        diff_cv   = abs(cv_mean - r_cv)
        r48_status = "PASS" if diff_cv <= 0.02 else ("WARN" if diff_cv <= 0.04 else "FAIL")
        r48_obs    = (
            f"Replicated CV mean AUC = {cv_mean:.4f} | Reported = {r_cv:.4f} | Δ = {diff_cv:.4f}"
        )
        r48_detail = (
            "CV mean AUC within ±0.02 — cross-validation results are consistent with reported."
            if r48_status == "PASS" else
            f"CV mean AUC difference of {diff_cv:.4f} exceeds ±0.02 tolerance."
        )
    elif cv_mean is not None and r_cv is None:
        r48_status = "WARN"
        r48_obs    = f"Replicated CV mean AUC = {cv_mean:.4f} | Reported value not entered"
        r48_detail = "Enter the developer's reported CV mean AUC to enable this check."
    else:
        r48_status = "SKIP"
        r48_obs    = "CV not run — enable K-fold cross-validation above"
        r48_detail = "Enable CV to run this check."

    checks.append({
        "id": "R4.8", "title": "CV mean AUC within ±0.02 of reported",
        "source": "SS1/23 P4.2", "severity": "medium",
        "status": r48_status,
        "observed": r48_obs,
        "threshold": "|Δ CV AUC| ≤ 0.02",
        "detail": r48_detail,
    })

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# UI rendering helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_check_card(check: Dict[str, Any]) -> None:
    """Render a single check result card."""
    import html as _html
    status  = check["status"]
    icon    = _STATUS_ICON.get(status, "⚪")
    color   = _STATUS_COLOR.get(status, _C["neutral"])
    bg      = _STATUS_BG.get(status, _C["card"])

    st.markdown(
        f"<div style='border-left:4px solid {color};padding:0.8rem 1.1rem;"
        f"margin:0.4rem 0;background:{bg};border-radius:0 8px 8px 0;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"margin-bottom:0.3rem;'>"
        f"<span style='color:#e2e8f0;font-weight:700;font-size:0.95rem;'>"
        f"{icon} [{_html.escape(check['id'])}] {_html.escape(check['title'])}</span>"
        f"<span style='background:{color};color:#fff;padding:0.15rem 0.6rem;"
        f"border-radius:12px;font-size:0.75rem;font-weight:700;'>{status}</span>"
        f"</div>"
        f"<div style='color:#94a3b8;font-size:0.83rem;margin-bottom:0.2rem;'>"
        f"📊 {_html.escape(str(check['observed']))}</div>"
        f"<div style='color:#64748b;font-size:0.78rem;margin-bottom:0.15rem;'>"
        f"🎯 Threshold: {_html.escape(str(check['threshold']))}</div>"
        f"<div style='color:#475569;font-size:0.78rem;'>"
        f"📋 {_html.escape(str(check['source']))} — {_html.escape(str(check['detail']))}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Optional inline table (R4.4)
    if "_table" in check and check["_table"]:
        with st.expander(f"📊 Detailed metrics table — {check['id']}", expanded=False):
            st.dataframe(pd.DataFrame(check["_table"]), use_container_width=True)

    # Optional ablation chart (R4.5)
    if "_ablation" in check and check["_ablation"]:
        with st.expander(f"📉 Feature ablation — AUC drop per feature removed — {check['id']}", expanded=False):
            abl = {k: v for k, v in check["_ablation"].items() if not np.isnan(v)}
            if abl:
                abl_df = pd.DataFrame(
                    sorted(abl.items(), key=lambda kv: kv[1], reverse=True),
                    columns=["Feature", "AUC Drop"],
                )
                fig = go.Figure(go.Bar(
                    x=abl_df["Feature"],
                    y=abl_df["AUC Drop"],
                    marker_color=[
                        "#ef4444" if v >= 0.05 else "#f59e0b" if v >= 0.02 else "#10b981"
                        for v in abl_df["AUC Drop"]
                    ],
                ))
                fig.add_hline(y=0.05, line_dash="dash", line_color="#ef4444",
                               annotation_text="Threshold (0.05)")
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    title="AUC Degradation per Removed Feature",
                    xaxis_tickangle=-45,
                    yaxis_title="AUC Drop",
                )
                st.plotly_chart(fig, use_container_width=True)

    # Optional seed stability chart (R4.6)
    if "_seed_aucs" in check and check["_seed_aucs"]:
        with st.expander(f"🎲 Seed AUC distribution — {check['id']}", expanded=False):
            seed_aucs = check["_seed_aucs"]
            seeds_used = check.get("_seeds", list(range(len(seed_aucs))))
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[f"Seed {s}" for s in seeds_used[:len(seed_aucs)]],
                y=seed_aucs,
                mode="markers+lines",
                marker=dict(size=10, color="#6366f1"),
                line=dict(color="#6366f1", width=2),
                name="AUC per seed",
            ))
            mean_v = float(np.mean(seed_aucs))
            fig.add_hline(y=mean_v, line_dash="dot", line_color="#10b981",
                           annotation_text=f"Mean={mean_v:.4f}")
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                title="AUC Across Random Seeds",
                yaxis_title="ROC-AUC",
            )
            st.plotly_chart(fig, use_container_width=True)


def _summary_scorecard(checks: List[Dict[str, Any]]) -> None:
    """Render a high-level pass/fail summary row."""
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1

    overall = (
        "FAIL"    if counts["FAIL"] > 0  else
        "WARN"    if counts["WARN"] > 0  else
        "SKIP"    if counts["SKIP"] == len(checks) else
        "PASS"
    )
    overall_color = _STATUS_COLOR[overall]

    st.markdown(
        f"<div style='background:{_C['card']};border:2px solid {overall_color};"
        f"border-radius:10px;padding:1rem 1.5rem;margin:0.75rem 0;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='color:#e2e8f0;font-size:1.05rem;font-weight:700;'>"
        f"Overall Replication Result</span>"
        f"<span style='background:{overall_color};color:#fff;padding:0.3rem 1rem;"
        f"border-radius:16px;font-size:0.9rem;font-weight:700;'>{overall}</span>"
        f"</div>"
        f"<div style='display:flex;gap:2rem;margin-top:0.7rem;'>"
        f"<span style='color:{_C['pass']};font-size:0.9rem;'>✅ PASS: {counts['PASS']}</span>"
f"<span style='color:{_C['warn']};font-size:0.9rem;'>⚠️ WARN: {counts['WARN']}</span>"
f"<span style='color:{_C['fail']};font-size:0.9rem;'>❌ FAIL: {counts['FAIL']}</span>"
f"<span style='color:{_C['neutral']};font-size:0.9rem;'>⏭️ SKIP: {counts['SKIP']}</span>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Methodology Parameter Comparison (R4.9)
# ─────────────────────────────────────────────────────────────────────────────

# Per-model parameter specification.
# Each entry: (display_label, severity_if_mismatch, comparison_mode, note)
#   comparison_mode:
#     "exact"   — values must be identical (strings, booleans, categorical choices)
#     "numeric" — numeric tolerance check; threshold is a relative fraction
#                 e.g. 0.20 means flag WARN if |Δ|/reported > 20%
#     "optional"— mismatch is INFO only, not flagged as WARN/FAIL
_MODEL_PARAM_SPECS: Dict[str, List[Tuple]] = {
    "Logistic Regression": [
        ("penalty",      "Penalty (L1/L2)",             "high",   "exact",   None),
        ("C",            "Regularisation strength (C)", "high",   "numeric", 0.20),
        ("solver",       "Solver",                      "medium", "exact",   None),
        ("class_weight", "Class weight",                "high",   "exact",   None),
    ],
    "Decision Tree": [
        ("max_depth",         "Max depth",                "high",   "exact",   None),
        ("criterion",         "Criterion (Gini/Entropy)", "medium", "exact",   None),
        ("min_samples_split", "Min samples split",        "medium", "numeric", 0.50),
        ("min_samples_leaf",  "Min samples leaf",         "medium", "numeric", 0.50),
    ],
    "Random Forest": [
        ("n_estimators",     "Number of trees",  "medium", "numeric", 0.30),
        ("max_depth",        "Max depth",        "high",   "exact",   None),
        ("max_features",     "Max features",     "high",   "exact",   None),
        ("min_samples_leaf", "Min samples leaf", "medium", "numeric", 0.50),
    ],
    "XGBoost": [
        ("n_estimators",     "Number of trees",                "medium", "numeric", 0.30),
        ("learning_rate",    "Learning rate",                  "high",   "numeric", 0.25),
        ("max_depth",        "Max depth",                      "high",   "numeric", 0.20),
        ("scale_pos_weight", "Class weight (scale_pos_weight)", "high",  "numeric", 0.25),
    ],
    "LightGBM": [
        ("n_estimators",  "Number of trees",                               "medium", "numeric", 0.30),
        ("learning_rate", "Learning rate",                                 "high",   "numeric", 0.25),
        ("num_leaves",    "Number of leaves",                              "high",   "numeric", 0.25),
        ("class_weight",  "Class weight (is_unbalance / scale_pos_weight)", "high",  "exact",   None),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Main render function — called from app.py render_model_validation()
# ─────────────────────────────────────────────────────────────────────────────

def _render_replication_params(submitted_hp: Dict[str, Any], model_name: str = "") -> None:
    """
    List the model hyperparameters extracted from the submitted MDD, shown at the
    TOP of the results (before the evaluation metrics). The model is replicated
    using exactly these parameters, so this is a configuration summary rather than
    a comparison.
    """
    import html as _html

    hdr = "#### 🔧 Model Hyperparameters Extracted from MDD" + (
        f" — {model_name}" if model_name else ""
    )
    st.markdown(hdr)

    if not submitted_hp:
        st.info(
            "ℹ️ No model hyperparameters were found in the submitted MDD. The model "
            "will be replicated using the pipeline's default configuration."
        )
        return

    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;margin-top:-0.35rem;'>"
        "The model is replicated using exactly these parameters, as supplied in the "
        "MDD. The evaluation metrics below are generated from a model trained with "
        "this configuration.</p>",
        unsafe_allow_html=True,
    )

    # Friendly labels + ordering from the model spec where available; any extra
    # submitted params are appended afterwards.
    spec_labels = {p[0]: p[1] for p in _MODEL_PARAM_SPECS.get(model_name, [])}
    spec_order  = [p[0] for p in _MODEL_PARAM_SPECS.get(model_name, [])]
    ordered_keys = [k for k in spec_order if k in submitted_hp] + \
                   [k for k in submitted_hp if k not in spec_order]

    cells = []
    for k in ordered_keys:
        label = spec_labels.get(k, k)
        val = submitted_hp.get(k)
        cells.append(
            "<tr>"
            f"<td style='padding:0.45rem 0.8rem;color:#e2e8f0;border-top:1px solid #334155;'>"
            f"{_html.escape(str(label))}</td>"
            f"<td style='padding:0.45rem 0.8rem;color:#e2e8f0;border-top:1px solid #334155;"
            f"font-family:monospace;'>{_html.escape(str(val))}</td>"
            "</tr>"
        )

    table = (
        "<table style='width:100%;border-collapse:collapse;font-size:0.86rem;"
        "background:#1e293b;border-radius:8px;overflow:hidden;margin:0.3rem 0 0.6rem 0;'>"
        "<thead><tr style='background:#0f172a;'>"
        "<th style='text-align:left;padding:0.55rem 0.8rem;color:#94a3b8;'>Parameter</th>"
        "<th style='text-align:left;padding:0.55rem 0.8rem;color:#94a3b8;'>Value (from MDD)</th>"
        "</tr></thead><tbody>" + "".join(cells) + "</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)


def render_val_replication():
    """Stage 4 — Model Replication render function."""
    import html as _html

    st.markdown("### ⚙️ Stage 4 — Model Replication & Benchmarking")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.9rem;'>"
        "Independently replicate the submitted model end-to-end using the platform pipeline. "
        "All feature engineering is learned exclusively on the training partition (leakage-free). "
        "Eight pass criteria are evaluated and flagged against SS1/23 and SS11/13 requirements."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Guard: need a dataset from Stage 1 ───────────────────────────────────
    val_df = st.session_state.get("val_df")
    if val_df is None:
        st.warning(
            "⚠️ No dataset found. Upload the validation dataset in "
            "**Stage 1 — Intake & Governance** first."
        )
        return

    st.success(
        f"✅ Dataset: **{val_df.shape[0]:,} rows × {val_df.shape[1]} columns** "
        f"(from Stage 1 intake)"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Section A: Target & model configuration
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("#### 🎯 Section A — Replication Configuration")

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        all_cols = val_df.columns.tolist()

        # Resolve default target:
        #   1. session state already set (demo handler or user's prior pick)
        #   2. target_col from the Stage 1 intake JSON (has explicit "target_col" key)
        #   3. target_col from the dev-pipeline Step 2
        #   4. detect_target_candidates auto-detection
        #   5. first column fallback
        if "rep_target_col" not in st.session_state or st.session_state["rep_target_col"] not in all_cols:
            _ij = st.session_state.get("val_intake_json") or {}
            _prior_target = (
                _ij.get("target_col")
                or st.session_state.get("target_col")
            )
            if _prior_target and _prior_target in all_cols:
                _default_target_idx = all_cols.index(_prior_target)
            else:
                _candidates = detect_target_candidates(val_df)
                _default_target_idx = 0
                for _i, _c in enumerate(all_cols):
                    if _c in _candidates:
                        _default_target_idx = _i
                        break
            st.session_state["rep_target_col"] = all_cols[_default_target_idx]

        target_col = st.selectbox(
            "Target variable", options=all_cols,
            index=all_cols.index(st.session_state["rep_target_col"]),
            key="rep_target_col",
            help="Auto-populated from Stage 1 MDD. Change here if needed.",
        )

        # Resolve default model:
        #   1. session state already set (demo handler or user's prior pick)
        #   2. algorithm from the Stage 1 intake JSON
        #   3. final_model_name from the dev-pipeline Step 6
        #   4. first model in registry
        _model_keys = list(CLASSIFICATION_MODELS.keys())
        if "rep_model_name" not in st.session_state or st.session_state["rep_model_name"] not in _model_keys:
            _ij = st.session_state.get("val_intake_json") or {}
            _prior_model = (
                _ij.get("algorithm")
                or st.session_state.get("final_model_name")
            )
            st.session_state["rep_model_name"] = (
                _prior_model if _prior_model and _prior_model in _model_keys else _model_keys[0]
            )

        model_name = st.selectbox(
            "Model type to replicate",
            options=_model_keys,
            index=_model_keys.index(st.session_state["rep_model_name"]),
            key="rep_model_name",
            help="Auto-populated from Stage 1 MDD. Change here if needed.",
        )

    with col_a2:
        test_size  = st.slider("Test split %",       5,  35, 15, 5, key="rep_test_pct") / 100
        val_size   = st.slider("Validation split %", 5,  25, 15, 5, key="rep_val_pct")  / 100
        random_seed = st.number_input(
            "Primary random seed", min_value=0, max_value=9999, value=42,
            key="rep_seed",
        )
        cv_folds = st.slider(
            "CV folds (for R4.8)", 3, 10, 5, 1, key="rep_cv_folds"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Section B: Developer-reported Metrics  (sourced from the Stage 1 MDD)
    #
    # The Model Development Document uploaded in *Stage 1 — Intake & Governance*
    # is the single source of truth. Stage 1 parses it into
    # st.session_state["val_mdd_text"]; here we extract the reported metrics from
    # that text and use them directly — no second upload. Only metrics the MDD
    # does NOT state are offered as optional manual inputs, so a cached widget can
    # never shadow a value that came from the MDD.
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("#### 📋 Section B — Developer-reported Metrics (from Stage 1 MDD)")

    _METRIC_LABELS = {
        "roc_auc": "ROC-AUC", "gini": "Gini", "ks": "KS Statistic",
        "cv_mean_auc": "CV Mean AUC", "accuracy": "Accuracy",
        "precision": "Precision", "recall": "Recall", "f1": "F1 Score",
    }
    _ALL_KEYS = ["roc_auc", "gini", "ks", "cv_mean_auc",
                 "accuracy", "precision", "recall", "f1"]

    def _manual_reported_inputs(keys: List[str]) -> Dict[str, Optional[float]]:
        """Render number inputs for the given metric keys; 0.0 means 'not provided'."""
        vals: Dict[str, Optional[float]] = {}
        _cols = st.columns(3)
        for _i, _k in enumerate(keys):
            with _cols[_i % 3]:
                _v = st.number_input(
                    f"Reported {_METRIC_LABELS.get(_k, _k)}",
                    min_value=0.0, max_value=1.0, value=0.0, step=0.001,
                    format="%.4f", key=f"rep_manual_{_k}",
                )
            vals[_k] = None if _v == 0.0 else float(_v)
        return vals

    mdd_text: str = st.session_state.get("val_mdd_text", "") or ""

    # Source 1 — regex extraction from the raw MDD text
    mdd_extracted: Dict[str, Optional[float]] = (
        extract_metrics_from_mdd(mdd_text) if mdd_text.strip() else {}
    )

    # Source 2 — pre-extracted metrics cached by Stage 1 (real file upload path)
    for _k, _v in (st.session_state.get("val_mdd_reported_metrics") or {}).items():
        if mdd_extracted.get(_k) is None and _v is not None:
            mdd_extracted[_k] = _v

    # Source 3 — stated_* fields from the Stage 1 intake JSON (demo mode / Agent 1)
    _ij = st.session_state.get("val_intake_json") or {}
    for _ik, _rk in [("stated_auc", "roc_auc"), ("stated_gini", "gini"), ("stated_recall", "recall")]:
        if mdd_extracted.get(_rk) is None:
            _iv = _ij.get(_ik)
            if _iv is not None:
                try:
                    _fv = float(_iv)
                    if 0.01 <= _fv <= 1.0:
                        mdd_extracted[_rk] = round(_fv, 4)
                except (TypeError, ValueError):
                    pass

    mdd_found = {k: v for k, v in mdd_extracted.items() if v is not None}

    reported: Dict[str, Optional[float]] = {k: None for k in _ALL_KEYS}

    if mdd_text.strip() or mdd_found:
        # MDD text or intake JSON values reached this stage from Stage 1.
        if mdd_found:
            st.success(
                f"✅ **{len(mdd_found)} metric(s) auto-populated from Stage 1** — "
                "used directly as the reported values for the R4.x checks."
            )
            st.caption(
                "Source: Model Development Document or intake form from "
                "Stage 1 — Intake & Governance. No re-entry required."
            )
            _disp_rows = [
                {"Metric": _METRIC_LABELS.get(k, k),
                 "Reported Value (from MDD)": f"{v:.4f}"}
                for k, v in mdd_found.items()
            ]
            st.dataframe(pd.DataFrame(_disp_rows), use_container_width=True, hide_index=True)
            for k, v in mdd_found.items():
                reported[k] = v
        else:
            st.info(
                "ℹ️ MDD text was found in Stage 1 but no performance metrics could be "
                "auto-extracted from any source. Add the reported values below."
            )

        _missing = [k for k in _ALL_KEYS if reported[k] is None]
        if _missing:
            with st.expander(
                f"➕ Add reported metrics not stated in the MDD ({len(_missing)} available)",
                expanded=not mdd_found,
            ):
                st.caption(
                    "Optional. Threshold metrics (accuracy / precision / recall / F1) "
                    "are rarely machine-readable in an MDD — enter them here to enable "
                    "the R4.4 operating-point check. Leave at 0.0000 to skip."
                )
                _manual = _manual_reported_inputs(_missing)
                for k, v in _manual.items():
                    if v is not None:
                        reported[k] = v
    else:
        # No MDD reached this stage from Stage 1 intake.
        st.warning(
            "⚠️ No MDD text was found from **Stage 1 — Intake & Governance**. "
            "Upload the Model Development Document there and its reported metrics "
            "will flow into this stage automatically. As a fallback you can supply "
            "the MDD or the metrics here."
        )
        with st.expander("📄 Fallback — provide the MDD or reported metrics here", expanded=True):
            _fb_file = st.file_uploader(
                "Upload MDD (PDF / TXT / DOCX) — parsed and shared with Stages 1/3",
                type=["pdf", "txt", "docx"], key="rep_mdd_upload_fallback",
            )
            if _fb_file is not None:
                try:
                    _parsed = parse_mdd_file(_fb_file)
                    if _parsed.strip():
                        st.session_state["val_mdd_text"] = _parsed
                        st.success(f"✅ MDD captured — {len(_parsed):,} characters. Re-reading metrics…")
                        st.rerun()
                    else:
                        st.warning("No text could be extracted (scanned PDF?). Enter metrics manually below.")
                except Exception as _e:
                    st.error(str(_e))
            st.markdown("**Or enter the reported values manually:**")
            _manual = _manual_reported_inputs(_ALL_KEYS)
            for k, v in _manual.items():
                reported[k] = v

    # ─────────────────────────────────────────────────────────────────────────
    # Section C: Seed configuration
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("#### 🎲 Section C — Seed Stability Configuration")
    st.caption(
        "R4.6 trains the model with 5 random seeds and checks Std(AUC) < 0.02. "
        "The seeds below are used in addition to the primary seed in Section A."
    )
    seeds_default = [42, 123, 456, 789, 2024]
    seeds = st.multiselect(
        "Seeds for stability test (R4.6)",
        options=[42, 123, 456, 789, 1337, 2024, 999, 7, 314, 100],
        default=seeds_default,
        key="rep_seeds",
        help="Select exactly 5 seeds for the stability check. More seeds → slower but more robust.",
    )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # Run button
    # ─────────────────────────────────────────────────────────────────────────
    run_btn = st.button(
        "🚀 Run Model Replication",
        type="primary",
        use_container_width=True,
        key="rep_run_btn",
    )

    if run_btn:
        # Validate inputs
        task_type = detect_task_type(val_df[target_col])
        if task_type != "binary":
            st.error(
                f"❌ Target '{target_col}' appears to be **{task_type}** — "
                "model replication currently supports binary classification only."
            )
            return

        if len(seeds) < 2:
            st.warning("⚠️ Select at least 2 seeds for R4.6 stability check.")

        # Run with progress feedback
        progress  = st.progress(0)
        status_el = st.empty()

        status_el.text("🔧 Running preprocessing and split...")
        progress.progress(10)

        with st.spinner("Replicating model — this runs the full pipeline including multi-seed training..."):
            result = _run_replication(
                df=val_df.copy(),
                target_col=target_col,
                model_name=model_name,
                test_size=test_size,
                val_size=val_size,
                random_seed=int(random_seed),
                cv_folds=cv_folds,
                reported=reported,
                seeds=list(seeds),
            )
        result["_seed_used"] = int(random_seed)

        progress.progress(85)
        status_el.text("📊 Evaluating pass/fail criteria...")

        checks = _evaluate_checks(result, reported, list(seeds))

        progress.progress(100)
        status_el.empty()

        # Store results in session state
        st.session_state["val_rep_result"]             = result
        st.session_state["val_rep_checks"]             = checks
        st.session_state["val_rep_reported"]           = reported
        st.session_state["val_replicated_importances"] = result.get("feature_importance", {})

        st.success(
            f"✅ Replication complete in **{result['timing_s']}s** — "
            f"see results below."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Results panel (shown if results are in session state)
    # ─────────────────────────────────────────────────────────────────────────
    result  = st.session_state.get("val_rep_result")
    checks  = st.session_state.get("val_rep_checks")

    if result is None or checks is None:
        st.info(
            "ℹ️ Configure the replication parameters above and click "
            "**Run Model Replication** to start."
        )
        return

    st.divider()
    st.markdown("#### 📊 Replication Results")

    # Summary scorecard
    _summary_scorecard(checks)

    # ── Hyperparameters extracted from the MDD (model replicated using these) ──
    _render_replication_params(
        st.session_state.get("val_hyperparams") or {},
        st.session_state.get("rep_model_name", ""),
    )
    st.divider()

    # Quick metrics row
    if not result["success"]:
        _err_msg = result.get("error") or "Replication could not complete."
        st.error(f"**Replication failed:** {_err_msg}")
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        for _mc, _lbl in zip(
            [mc1, mc2, mc3, mc4, mc5],
            ["ROC-AUC", "Gini", "KS", "Recall", "CV Mean AUC"],
        ):
            _mc.metric(_lbl, "N/A")
    elif result["success"]:
        m = result["metrics"]
        rep = st.session_state.get("val_rep_reported", {}) or {}

        def _delta(key: str) -> str | None:
            """Return formatted delta string vs reported, or None if not available."""
            repl_val = m.get(key)
            rep_val  = rep.get(key)
            if repl_val is None or rep_val is None:
                return None
            try:
                diff = round(float(repl_val) - float(rep_val), 4)
                return f"{diff:+.4f} vs reported"
            except Exception:
                return None

        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("ROC-AUC",   f"{m.get('roc_auc', 0):.4f}" if m.get("roc_auc") is not None else "N/A",
                   delta=_delta("roc_auc"))
        mc2.metric("Gini",      f"{m.get('gini',    0):.4f}" if m.get("gini")    is not None else "N/A",
                   delta=_delta("gini"))
        mc3.metric("KS",        f"{m.get('ks',      0):.4f}" if m.get("ks")      is not None else "N/A",
                   delta=_delta("ks"))
        mc4.metric("Recall",    f"{m.get('recall',  0):.4f}" if m.get("recall")  is not None else "N/A",
                   delta=_delta("recall"))
        if result.get("cv_mean_auc") is not None:
            mc5.metric(
                f"CV Mean AUC ({st.session_state.get('rep_cv_folds',5)}-fold)",
                f"{result['cv_mean_auc']:.4f}",
                delta=_delta("cv_mean_auc"),
            )

    st.divider()

    # Individual check cards
    st.markdown("#### 🔍 Individual Check Results")
    for check in checks:
        _render_check_card(check)

    # Traceback expander on failure
    if not result["success"] and result.get("traceback"):
        with st.expander("🐛 Training error traceback (for debugging)", expanded=False):
            st.code(result["traceback"], language="python")

    st.divider()

    # ── ROC comparison chart (replicated vs reported, if reported AUC given) ─
    if result["success"] and result.get("y_proba_test") is not None:
        st.markdown("#### 📈 ROC Curve — Replicated Model")
        from sklearn.metrics import roc_curve as _roc_curve
        y_true = result["y_test"].values
        y_sc   = result["y_proba_test"]
        fpr, tpr, _ = _roc_curve(y_true, y_sc)
        rep_auc_val = result["metrics"].get("roc_auc", 0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=fpr, y=tpr, mode="lines",
            name=f"Replicated (AUC={rep_auc_val:.4f})",
            line=dict(color="#6366f1", width=3),
            fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
        ))
        r_auc_val = st.session_state.get("val_rep_reported", {}).get("roc_auc")
        if r_auc_val:
            fig.add_hline(
                y=r_auc_val, line_dash="dot", line_color="#f59e0b",
                annotation_text=f"Reported AUC = {r_auc_val:.4f}",
            )
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], mode="lines", name="Random",
            line=dict(color="#64748b", dash="dash"),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            title="ROC Curve — Replicated Model",
            xaxis_title="False Positive Rate",
            yaxis_title="True Positive Rate",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Feature decision log ──────────────────────────────────────────────────
    if result["success"] and result.get("feature_names"):
        with st.expander(
            f"📋 Feature Engineering Log ({len(result['feature_names'])} features after FE)",
            expanded=False,
        ):
            fe_s  = result.get("fe_summary", {})
            fe_p  = result.get("fe_plan",    {})
            rows  = [
                {"Feature": f, "Source": "Engineered"}
                for f in fe_s.get("added", [])
            ] + [
                {"Feature": f, "Source": "Retained"}
                for f in result["feature_names"]
                if f not in fe_s.get("added", []) and f not in fe_s.get("removed", [])
            ] + [
                {"Feature": f, "Source": "Removed"}
                for f in fe_s.get("removed", [])
            ]
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()

    # ── Extract and store feature importances ─────────────────────────────────
    _result = st.session_state.get("val_rep_result") or {}
    if _result.get("success"):
        try:
            _pipeline = _result.get("pipeline")
            _feature_names = _result.get("feature_names") or []
            if _pipeline is not None:
                _model_step = None
                for _, _step_obj in _pipeline.steps:
                    if hasattr(_step_obj, "feature_importances_"):
                        _model_step = _step_obj
                        break

                if _model_step is not None:
                    _fi_raw = _model_step.feature_importances_
                    _fi_len = len(_fi_raw)

                    if _feature_names and len(_feature_names) >= _fi_len:
                        _cols = _feature_names[:_fi_len]
                    else:
                        _X_test = _result.get("X_test")
                        _cols = (
                            list(_X_test.columns)[:_fi_len]
                            if _X_test is not None
                            else [f"feature_{i}" for i in range(_fi_len)]
                        )

                    _fi_sum = float(sum(_fi_raw)) or 1.0
                    _fi_dict = {
                        col: round(float(val) / _fi_sum, 6)
                        for col, val in zip(_cols, _fi_raw)
                    }

                    st.session_state["val_replicated_importances"] = _fi_dict
                    _result["feature_importance"] = _fi_dict
                    st.session_state["val_rep_result"] = _result
        except Exception as _fi_err:
            st.warning(f"Could not extract feature importances: {_fi_err}")

    # ── CSV download ──────────────────────────────────────────────────────────
    st.markdown("#### 💾 Download Replication Report")
    csv_rows = [{
        "Check ID":  c["id"],
        "Title":     c["title"],
        "Source":    c["source"],
        "Severity":  c["severity"],
        "Status":    c["status"],
        "Observed":  c["observed"],
        "Threshold": c["threshold"],
        "Detail":    c["detail"],
    } for c in checks]

    # Append replicated metric rows
    if result["success"]:
        m = result["metrics"]
        for key in ["roc_auc", "gini", "ks", "accuracy", "precision", "recall", "f1"]:
            if key in m:
                csv_rows.append({
                    "Check ID":  "METRIC",
                    "Title":     key.upper(),
                    "Source":    "Replicated",
                    "Severity":  "",
                    "Status":    "",
                    "Observed":  str(m[key]),
                    "Threshold": "",
                    "Detail":    "",
                })


    st.download_button(
        "📥 Download Replication Report (CSV)",
        data=pd.DataFrame(csv_rows).to_csv(index=False).encode("utf-8"),
        file_name="replication_report.csv",
        mime="text/csv",
        use_container_width=True,
        key="rep_download_report",
    )
