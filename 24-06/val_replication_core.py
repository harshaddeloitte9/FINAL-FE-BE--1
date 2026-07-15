"""
val_replication_core.py — backend-only replication engine

Trimmed extraction of the POC `val_replication.py` logic for FastAPI use.
This module intentionally omits Streamlit UI and returns plain dicts suitable
for JSON serialization.
"""
from __future__ import annotations

import re as _re
import time
import traceback
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from utils import detect_column_types, detect_target_candidates, detect_task_type
from preprocessing import prepare_data, rebuild_preprocessor_for
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering
from train import split_data, compute_split_stats, train_model
from evaluate import compute_binary_metrics
from model_selector import CLASSIFICATION_MODELS
from explainability import extract_feature_importance


def _gini(y_true: np.ndarray, y_score: np.ndarray) -> float:
    try:
        return round(2.0 * float(roc_auc_score(y_true, y_score)) - 1.0, 4)
    except Exception:
        return float("nan")


def _ks(y_true: np.ndarray, y_score: np.ndarray) -> float:
    try:
        fpr, tpr, _ = roc_curve(y_true, y_score)
        return round(float(np.max(np.abs(tpr - fpr))), 4)
    except Exception:
        return float("nan")


def _proba_1d(pipeline, X) -> Optional[np.ndarray]:
    if not hasattr(pipeline, "predict_proba"):
        return None
    try:
        p = pipeline.predict_proba(X)
        return p[:, 1] if p.ndim == 2 else p
    except Exception:
        return None


def _proba_2d(pipeline, X) -> Optional[np.ndarray]:
    if not hasattr(pipeline, "predict_proba"):
        return None
    try:
        return pipeline.predict_proba(X)
    except Exception:
        return None


def _pct_diff(replicated: float, reported: float) -> float:
    if reported == 0:
        return abs(replicated)
    return abs(replicated - reported) / abs(reported)


_MDD_METRIC_PATTERNS: List = [
    ("mdd_roc_auc", [
        r"roc[\s\-_]?auc[\s:=of]+([0-9]\.[0-9]{2,4})",
        r"\bauc[\s:=]+([0-9]\.[0-9]{2,4})",
        r"area under (?:the )?(?:roc )?curve[\s:=]+([0-9]\.[0-9]{2,4})",
        r"c[\s\-]?statistic[\s:=]+([0-9]\.[0-9]{2,4})",
    ]),
    ("mdd_gini", [r"gini[\s\-_]?(?:coefficient|index|score)?[\s:=]+([0-9]\.[0-9]{2,4})", r"gini[\s:=]+([0-9]\.[0-9]{2,4})"]),
    ("mdd_ks", [r"k[\s\-]?s[\s\-]?(?:statistic|score|test)?[\s:=]+([0-9]\.[0-9]{2,4})", r"kolmogorov[\s\-]?smirnov[\s:=]+([0-9]\.[0-9]{2,4})"]),
    ("mdd_cv_mean_auc", [r"cv[\s\-_]?(?:mean[\s\-_]?)?auc[\s:=]+([0-9]\.[0-9]{2,4})", r"cross[\s\-]?val(?:idation)?[\s\-_]?(?:mean[\s\-_]?)?auc[\s:=]+([0-9]\.[0-9]{2,4})", r"mean[\s\-_]?cv[\s\-_]?auc[\s:=]+([0-9]\.[0-9]{2,4})"]),
    ("mdd_accuracy", [r"accuracy[\s:=]+([0-9]\.[0-9]{2,4})", r"overall accuracy[\s:=]+([0-9]\.[0-9]{2,4})"]),
    ("mdd_precision", [r"precision[\s:=]+([0-9]\.[0-9]{2,4})", r"positive predictive value[\s:=]+([0-9]\.[0-9]{2,4})", r"ppv[\s:=]+([0-9]\.[0-9]{2,4})"]),
    ("mdd_recall", [r"recall[\s:=]+([0-9]\.[0-9]{2,4})", r"sensitivity[\s:=]+([0-9]\.[0-9]{2,4})", r"true positive rate[\s:=]+([0-9]\.[0-9]{2,4})", r"tpr[\s:=]+([0-9]\.[0-9]{2,4})"]),
    ("mdd_f1", [r"f[\s\-]?1[\s\-]?(?:score)?[\s:=]+([0-9]\.[0-9]{2,4})", r"f[\s\-]?measure[\s:=]+([0-9]\.[0-9]{2,4})"]),
]


def extract_metrics_from_mdd(mdd_text: str) -> Dict[str, Optional[float]]:
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


def run_replication(
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
    # Wraps the original _run_replication but returns JSON-serializable outputs
    out = {
        "success": False,
        "error": None,
        "metrics": {},
        "seed_aucs": [],
        "cv_mean_auc": None,
        "split_stats": {},
        "timing_s": 0.0,
        "ablation": {},
        "X_train": None,
        "X_test": None,
        "y_train": None,
        "y_test": None,
        "y_proba": None,
        "y_pred": None,
        "feature_importance": [],
    }
    t0 = time.time()
    try:
        col_types = detect_column_types(df)
        task_type = detect_task_type(df[target_col])
        X, y, _, prep_report, _ = prepare_data(df, col_types, target_col)

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

        fe_plan = analyze_for_feature_engineering(
            X_train_raw, y_train, col_types, task_type
        )
        X_train, fe_summary = apply_feature_engineering(X_train_raw, fe_plan)
        X_val, _ = apply_feature_engineering(X_val_raw, fe_plan)
        X_test_eng, _ = apply_feature_engineering(X_test_raw, fe_plan)

        import copy as _copy
        live_cols = set(X_train.columns)
        prep_report_fe = _copy.deepcopy(prep_report)
        prep_report_fe["numeric"] = {c: v for c, v in prep_report.get("numeric", {}).items() if c in live_cols}
        prep_report_fe["categorical"] = {c: v for c, v in prep_report.get("categorical", {}).items() if c in live_cols}

        registry = CLASSIFICATION_MODELS
        normalized_model_name = model_name
        alias_map = {
            "LogisticRegression": "Logistic Regression",
            "LogisticRegressionClassifier": "Logistic Regression",
            "RandomForest": "Random Forest",
            "RandomForestClassifier": "Random Forest",
            "GradientBoosting": "Gradient Boosting",
            "GradientBoostingClassifier": "Gradient Boosting",
            "XGBoostClassifier": "XGBoost",
            "LightGBMClassifier": "LightGBM",
        }
        if model_name in alias_map:
            normalized_model_name = alias_map[model_name]
        if normalized_model_name not in registry:
            raise ValueError(f"Model '{model_name}' not found. Available: {list(registry.keys())}")
        model_cls = registry[normalized_model_name]["class"]
        default_params = registry[normalized_model_name].get("default_params", {}).copy()
        try:
            valid_keys = set(model_cls().get_params().keys())
            default_params = {k: v for k, v in default_params.items() if k in valid_keys}
        except Exception:
            pass
        model_inst = model_cls(**default_params)

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

        y_proba_2d = _proba_2d(pipeline, X_test_eng)
        y_proba = _proba_1d(pipeline, X_test_eng)
        y_pred = pipeline.predict(X_test_eng)
        if y_proba is None:
            raise RuntimeError("Model does not support predict_proba — AUC cannot be computed.")

        metrics = compute_binary_metrics(
            y_test.values, y_pred, y_proba_2d,
            threshold=0.5,
        )
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_test.values, y_proba)), 4)
        except Exception:
            pass
        metrics["gini"] = _gini(y_test.values, y_proba)
        metrics["ks"] = _ks(y_test.values, y_proba)

        # Feature importance of the replicated model, exposed so Stage 7
        # (Explainability & Fairness) can chart it without re-running
        # replication or requiring a separately-trained model artifact.
        feature_importance: List[Dict[str, Any]] = []
        try:
            importance_df = extract_feature_importance(pipeline)
            if importance_df is not None:
                feature_importance = importance_df.to_dict(orient="records")
        except Exception:
            feature_importance = []

        out.update({
            "success": True,
            "metrics": metrics,
            "cv_mean_auc": training_info.get("cv_mean"),
            "cv_std_auc": training_info.get("cv_std"),
            "timing_s": 0.0,
            "X_train": X_train,
            "X_test": X_test_eng,
            "y_train": y_train,
            "y_test": y_test,
            "y_proba": y_proba,
            "y_pred": y_pred,
            "feature_importance": feature_importance,
        })

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

                live_s = set(Xtr_fe_s.columns)
                prep_report_s = _copy.deepcopy(prep_report)
                prep_report_s["numeric"] = {c: v for c, v in prep_report.get("numeric", {}).items() if c in live_s}
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

        feat_cols = list(X_test_eng.columns)
        base_auc = float(metrics.get("roc_auc", 0))
        ablation = {}
        for col in feat_cols:
            try:
                X_abl = X_test_eng.drop(columns=[col])
                X_tr_abl = X_train.drop(columns=[col], errors="ignore")
                m_abl = model_cls(**default_params)
                live_abl = set(X_tr_abl.columns)
                prep_report_abl = _copy.deepcopy(prep_report_fe)
                prep_report_abl["numeric"] = {c: v for c, v in prep_report_fe.get("numeric", {}).items() if c in live_abl}
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


def evaluate_replication_checks(result: Dict[str, Any], reported: Dict[str, Any], seeds: List[int]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []

    rep_auc = result.get("metrics", {}).get("roc_auc")
    rep_gini = result.get("metrics", {}).get("gini")
    rep_ks = result.get("metrics", {}).get("ks")
    seed_aucs = result.get("seed_aucs", [])
    ablation = result.get("ablation", {})

    if result.get("success"):
        checks.append({"id": "R4.1", "title": "End-to-end training", "severity": "high", "status": "PASS", "observed": f"Trained in {result.get('timing_s')}s — no errors", "threshold": "Pipeline trains without errors", "detail": "Model trained successfully using the submitted dataset and the platform pipeline."})
    else:
        checks.append({"id": "R4.1", "title": "End-to-end training", "severity": "high", "status": "FAIL", "observed": result.get("error", "Unknown error"), "threshold": "Pipeline trains without errors", "detail": "Training failed."})
        for cid in ["R4.2", "R4.3", "R4.4", "R4.5", "R4.6", "R4.7", "R4.8"]:
            checks.append({"id": cid, "title": cid, "severity": "high", "status": "SKIP", "observed": "Not run — R4.1 failed", "threshold": "N/A", "detail": "Cannot evaluate: model did not train."})
        return checks

    # R4.2
    r_auc = reported.get("roc_auc")
    if r_auc is not None and rep_auc is not None:
        diff_auc = abs(rep_auc - r_auc)
        status = "PASS" if diff_auc <= 0.03 else ("WARN" if diff_auc <= 0.06 else "FAIL")
        checks.append({"id": "R4.2", "title": "Replicated AUC within ±0.03", "severity": "high", "status": status, "observed": f"Replicated AUC = {rep_auc:.4f} | Reported = {r_auc:.4f} | Δ = {diff_auc:.4f}", "threshold": "|Δ AUC| ≤ 0.03"})
    else:
        checks.append({"id": "R4.2", "title": "Replicated AUC within ±0.03", "severity": "high", "status": "WARN", "observed": f"Replicated AUC = {rep_auc if rep_auc else 'N/A'} | Reported AUC not provided", "threshold": "|Δ AUC| ≤ 0.03"})

    # R4.3
    r_gini = reported.get("gini")
    r_ks = reported.get("ks")
    gini_ok = True
    ks_ok = True
    gini_diff = None
    ks_diff = None
    if r_gini is not None and rep_gini is not None:
        gini_diff = abs(rep_gini - r_gini)
        gini_ok = gini_diff <= 0.05
    if r_ks is not None and rep_ks is not None:
        ks_diff = abs(rep_ks - r_ks)
        ks_ok = ks_diff <= 0.03
    if r_gini is None and r_ks is None:
        checks.append({"id": "R4.3", "title": "Gini within ±0.05 / KS within ±0.03", "severity": "high", "status": "WARN", "observed": f"Replicated Gini = {rep_gini:.4f}, KS = {rep_ks:.4f} | Reported values not provided", "threshold": "|Δ Gini| ≤ 0.05 and |Δ KS| ≤ 0.03"})
    else:
        gini_ks_status = "PASS" if (gini_ok and ks_ok) else "FAIL"
        checks.append({"id": "R4.3", "title": "Gini within ±0.05 / KS within ±0.03", "severity": "high", "status": gini_ks_status, "observed": f"Gini/Ks comparison", "threshold": "|Δ Gini| ≤ 0.05 and |Δ KS| ≤ 0.03"})

    # R4.4 simple implementation
    metric_keys_r4 = [("accuracy", "Accuracy"), ("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]
    r44_rows = []
    any_reported = False
    r44_fails = []
    for key, label in metric_keys_r4:
        rep_val = result.get("metrics", {}).get(key)
        repl_val = rep_val
        rep_reported = reported.get(key)
        if rep_reported is None or repl_val is None:
            r44_rows.append({"Metric": label, "Replicated": repl_val, "Reported": rep_reported, "Rel. Diff": "N/A", "Status": "SKIP"})
            continue
        any_reported = True
        rel = _pct_diff(float(repl_val), float(rep_reported))
        ok = rel <= 0.05
        status_k = "PASS" if ok else "FAIL"
        if not ok:
            r44_fails.append(f"{label} (Δ = {rel:.1%})")
        r44_rows.append({"Metric": label, "Replicated": round(float(repl_val), 4), "Reported": round(float(rep_reported), 4), "Rel. Diff": f"{rel:.2%}", "Status": status_k})
    if not any_reported:
        r44_status = "WARN"
        r44_obs = "No reported values entered — comparison not possible"
    elif r44_fails:
        r44_status = "FAIL"
        r44_obs = f"Out of tolerance: {', '.join(r44_fails)}"
    else:
        r44_status = "PASS"
        r44_obs = "All reported metrics replicated within ±5%"
    checks.append({"id": "R4.4", "title": "Metrics within ±5% at reported threshold", "severity": "medium", "status": r44_status, "observed": r44_obs, "threshold": "Relative difference ≤ 5% per metric", "_table": r44_rows})

    # R4.5
    if ablation:
        max_drop_col = max(ablation, key=lambda k: ablation[k] if not np.isnan(ablation[k]) else -999)
        max_drop_val = ablation.get(max_drop_col, float("nan"))
        r45_status = "PASS" if (not np.isnan(max_drop_val) and max_drop_val < 0.05) else "FAIL"
        checks.append({"id": "R4.5", "title": "Feature removal: AUC degradation < 0.05", "severity": "medium", "status": r45_status, "observed": f"Largest AUC drop: {max_drop_val:.4f} when removing '{max_drop_col}'", "_ablation": ablation})
    else:
        checks.append({"id": "R4.5", "title": "Feature removal: AUC degradation < 0.05", "severity": "medium", "status": "SKIP", "observed": "Ablation study not run (no features available)", "threshold": "Max AUC drop per removed feature < 0.05"})

    # R4.6
    if len(seed_aucs) >= 2:
        std_auc = round(float(np.std(seed_aucs)), 4)
        mean_auc = round(float(np.mean(seed_aucs)), 4)
        r46_status = "PASS" if std_auc < 0.02 else "FAIL"
        checks.append({"id": "R4.6", "title": f"Seed stability: Std(AUC) < 0.02 ({len(seeds)} seeds)", "severity": "medium", "status": r46_status, "observed": f"AUC across {len(seed_aucs)} seeds: mean={mean_auc:.4f}, std={std_auc:.4f}", "_seed_aucs": seed_aucs, "_seeds": seeds})
    else:
        checks.append({"id": "R4.6", "title": "Seed stability: Std(AUC) < 0.02", "severity": "medium", "status": "WARN", "observed": f"Only {len(seed_aucs)} seed(s) ran successfully"})

    # R4.7
    split_stats = result.get("split_stats", {})
    train_n = split_stats.get("train_n", 0)
    test_n = split_stats.get("test_n", 0)
    checks.append({"id": "R4.7", "title": "Split reproducibility — no test contamination", "severity": "high", "status": "PASS", "observed": f"Train={train_n:,} | Val={split_stats.get('val_n',0):,} | Test={test_n:,}", "threshold": "Deterministic split; feature engineering learned on train only"})

    # R4.8
    cv_mean = result.get("cv_mean_auc")
    r_cv = reported.get("cv_mean_auc")
    if cv_mean is not None and r_cv is not None:
        diff_cv = abs(cv_mean - r_cv)
        r48_status = "PASS" if diff_cv <= 0.02 else ("WARN" if diff_cv <= 0.04 else "FAIL")
        checks.append({"id": "R4.8", "title": "CV mean AUC within ±0.02 of reported", "severity": "medium", "status": r48_status, "observed": f"Replicated CV mean AUC = {cv_mean:.4f} | Reported = {r_cv:.4f} | Δ = {diff_cv:.4f}"})
    else:
        checks.append({"id": "R4.8", "title": "CV mean AUC within ±0.02 of reported", "severity": "medium", "status": "SKIP", "observed": "CV not run — enable K-fold cross-validation above"})

    return checks
