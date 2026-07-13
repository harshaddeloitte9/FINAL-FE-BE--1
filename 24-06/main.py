"""
main.py - FastAPI backend for the Credit Risk ML POC

Thin REST wrapper that exposes the latest pipeline logic from the
Credit-Risk-Poc-main source-of-truth project.
"""

import base64
import io
import json
import importlib.util
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple, Union

BACKEND_DIR = Path(__file__).resolve().parent
SOURCE_OF_TRUTH_DIR = Path(__file__).resolve().parent.parent / "Credit-Risk-Poc-main"
for path in [BACKEND_DIR, SOURCE_OF_TRUTH_DIR]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0 if path == BACKEND_DIR else 1, path_str)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import joblib

_local_agent2_spec = importlib.util.spec_from_file_location("local_agent2", Path(__file__).resolve().parent / "agent2.py")
if _local_agent2_spec is None or _local_agent2_spec.loader is None:
    raise ImportError("Could not load local Agent2 from 24-06/agent2.py")
_local_agent2_module = importlib.util.module_from_spec(_local_agent2_spec)
_local_agent2_spec.loader.exec_module(_local_agent2_module)
Agent2 = _local_agent2_module.Agent2
from build_rules import RULES_PATH

from utils import (
    generate_synthetic_credit_dataset, detect_column_types,
    detect_target_candidates, detect_task_type, df_to_csv_download, model_to_download,
)
from preprocessing_new import (
    build_preprocessing_report, prepare_data, rebuild_preprocessor_for, finalize_xy,
    get_feature_names_from_fitted_preprocessor,
    classify_missing_treatment, select_imputation_strategy, SemanticImputer,
    REVIEW_MISSING_THRESHOLD, MISSING_VALUE_LIMITATION_NOTE,
    estimate_drop_impact,
)
from feature_engineering import (
    analyze_for_feature_engineering, apply_feature_engineering,
    compute_univariate_gini,
)
try:
    from feature_engineering import resolve_ead_configuration
except ImportError:
    _legacy_fe_path = Path(__file__).resolve().parent / "feature_engineering.py"
    _legacy_fe_spec = importlib.util.spec_from_file_location("legacy_feature_engineering", _legacy_fe_path)
    if _legacy_fe_spec is None or _legacy_fe_spec.loader is None:
        raise
    _legacy_fe = importlib.util.module_from_spec(_legacy_fe_spec)
    _legacy_fe_spec.loader.exec_module(_legacy_fe)
    resolve_ead_configuration = _legacy_fe.resolve_ead_configuration
from model_selector import recommend_models, get_model_instance, get_hyperparameter_grid
from train_new import split_data, compute_split_stats, train_model
import ecl_engine as ecl
import evaluate as eval_engine

compute_binary_metrics = eval_engine.compute_binary_metrics
compute_regression_metrics = eval_engine.compute_regression_metrics
compute_heteroscedasticity_check = eval_engine.compute_heteroscedasticity_check

_legacy_eval_path = Path(__file__).resolve().parent / "evaluate.py"
_legacy_eval_spec = importlib.util.spec_from_file_location("legacy_evaluate", _legacy_eval_path)
if _legacy_eval_spec is None or _legacy_eval_spec.loader is None:
    raise ImportError(f"Could not load evaluation helpers from {_legacy_eval_path}")
_legacy_eval = importlib.util.module_from_spec(_legacy_eval_spec)
_legacy_eval_spec.loader.exec_module(_legacy_eval)

compute_roc_curve = getattr(eval_engine, "compute_roc_curve", _legacy_eval.compute_roc_curve)
compute_pr_curve = getattr(eval_engine, "compute_pr_curve", _legacy_eval.compute_pr_curve)
compute_threshold_analysis = getattr(eval_engine, "compute_threshold_analysis", _legacy_eval.compute_threshold_analysis)
compute_score_distribution = getattr(eval_engine, "compute_score_distribution", _legacy_eval.compute_score_distribution)
compute_gain_chart = getattr(eval_engine, "compute_gain_chart", _legacy_eval.compute_gain_chart)
from explainability import (
    extract_feature_importance, compute_shap_values, generate_prediction_reasoning,
)
from val_replication_core import extract_metrics_from_mdd, parse_mdd_file, run_replication

_validation_agent2_path = SOURCE_OF_TRUTH_DIR / "validation_agent2.py"
_validation_agent2_spec = importlib.util.spec_from_file_location("source_validation_agent2", _validation_agent2_path)
if _validation_agent2_spec is None or _validation_agent2_spec.loader is None:
    raise ImportError(f"Could not load ValidationAgent2 from {_validation_agent2_path}")
_validation_agent2_module = importlib.util.module_from_spec(_validation_agent2_spec)
_validation_agent2_spec.loader.exec_module(_validation_agent2_module)
ValidationAgent2 = _validation_agent2_module.ValidationAgent2


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://final-ok9cvxfh0-harshads-projects-d63c4e68.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_validation_agent2(val_df: Optional[pd.DataFrame], intake_json: dict, mdd_text: str = "") -> dict:
    agent = ValidationAgent2()
    return agent.run_all_checks(val_df if val_df is not None else pd.DataFrame(), intake_json or {}, mdd_text or "")
    
def _build_validation_intake_snapshot(mode: str = "clean") -> Dict[str, Any]:
    demo_mode = "flawed" if mode.lower() == "flawed" else "clean"
    if demo_mode == "flawed":
        model_data = {
            "model_name": "PD_Model_Internal_v1",
            "model_owner": "Unknown",
            "owning_team": "Risk",
            "lead_validator": "Reeyaz Miglani",
            "model_type": "PD (Probability of Default)",
            "model_version": "v1.0",
            "model_tier": "Tier 1 — High Risk",
            "model_purpose": "Credit risk model.",
            "target_col": "default",
            "algorithm": "XGBoost",
            "default_definition": "Internal default indicator",
            "calibration_method": "Not specified",
            "macro_variables_mentioned": False,
            "model_inventory_registered": False,
            "independence_confirmed": False,
        }
        reported_metrics = {
            "roc_auc": 0.78,
            "gini": 0.56,
            "ks": 0.48,
            "cv_mean_auc": 0.73,
            "accuracy": 0.79,
            "precision": 0.61,
            "recall": 0.72,
            "f1": 0.65,
        }
        mdd_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_mdd.txt"
        hyperparams_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_params.json"
        demo_label = "Demo B"
    else:
        model_data = {
            "model_name": "PD_XGBoost_RetailCredit_v2",
            "model_owner": "Sarah Chen",
            "owning_team": "Retail Credit Risk",
            "lead_validator": "Reeyaz Miglani",
            "model_type": "PD (Probability of Default)",
            "model_version": "v2.1.0",
            "model_tier": "Tier 2 — Medium Risk",
            "model_purpose": (
                "This model estimates the probability of default for unsecured retail credit customers. "
                "Used for IFRS 9 ECL staging, credit decisioning, and risk appetite reporting. "
                "Scope: personal loan portfolio only. Out of scope: mortgages, business lending."
            ),
            "default_definition": "90 days past due (IFRS 9 / CRR Art.178)",
            "calibration_method": "Platt scaling (TTC)",
            "macro_variables_mentioned": True,
            "model_inventory_registered": True,
            "independence_confirmed": True,
        }
        reported_metrics = {
            "roc_auc": 0.82,
            "gini": 0.64,
            "ks": 0.58,
            "cv_mean_auc": 0.80,
            "accuracy": 0.85,
            "precision": 0.72,
            "recall": 0.71,
            "f1": 0.72,
        }
        mdd_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_mdd.txt"
        hyperparams_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_params.json"
        demo_label = "Demo A"

    try:
        mdd_text = mdd_file.read_text(encoding="utf-8")
    except Exception:
        mdd_text = ""
    try:
        hyperparams = json.loads(hyperparams_file.read_text(encoding="utf-8"))
    except Exception:
        hyperparams = {}

    return {
        "demo_mode": demo_mode,
        "demo_label": demo_label,
        "val_intake_data": {**model_data, "mdd_text": mdd_text},
        "val_mdd_text": mdd_text,
        "val_mdd_reported_metrics": reported_metrics,
        "val_hyperparams": hyperparams,
        "chk_inventory": True,
        "chk_tier": True,
        "chk_artifacts": True,
        "chk_prev_findings": True,
        "chk_reg_scope": True,
        "chk_independence": True,
        "chk_plan_approved": True,
        "chk_attestation": True,
        "display": {
            "title": "Stage 1 — Intake & Governance",
            "description": "Capture model metadata, upload all required artifacts, and complete the governance attestation checklist before proceeding to automated validation stages.",
            "modelMetadata": {
                "title": "Model metadata",
                "description": "Key registration details supplied by the development team.",
                "registeredLabel": "Registered",
                "items": [
                    ["Model ID", "CR-PD-XGB-027"],
                    ["Model name", "Retail PD — XGBoost Champion"],
                    ["Owner", "A. Khurana · Risk Validation"],
                    ["Developer", "Credit Risk Modelling, EMEA"],
                    ["Version", "v1.7.6"],
                    ["Risk tier", "Tier 2 — Material"],
                    ["Last validated", "12 Apr 2026"],
                    ["Next review", "12 Jul 2026"],
                ],
            },
            "targetDefinition": {
                "title": "Target definition",
                "expression": "default_12m ∈ {0, 1}",
                "detail": "positive class = 90+ DPD within 12m",
                "baseRateLabel": "Base rate",
                "baseRate": "4.7%",
                "sampleSizeLabel": "Sample size",
                "sampleSize": "219,486",
            },
            "riskTier": {
                "title": "Risk tier",
                "value": "Tier 2",
                "description": "Material — quarterly independent validation required.",
            },
            "artifacts": [
                {"fileName": "retail_pd_validation.csv", "status": "Uploaded", "timestamp": "Uploaded 21 Jun 2026 · 09:13", "required": True},
                {"fileName": "retail_pd_mdd.pdf", "status": "Uploaded", "timestamp": "Uploaded 21 Jun 2026 · 09:15", "required": True},
                {"fileName": "training_pipeline.zip", "status": "Uploaded", "timestamp": "Uploaded 21 Jun 2026 · 09:17", "required": True},
                {"fileName": "data_profile.xlsx", "status": "Optional", "timestamp": "Pending review", "required": False},
                {"fileName": "assumptions_limitations.pdf", "status": "Optional", "timestamp": "Pending review", "required": False},
                {"fileName": "performance_report.xlsx", "status": "Optional", "timestamp": "Pending review", "required": False},
            ],
            "artifactSummary": "3 required · 3 optional",
            "artifactTitle": "Artifact inventory",
            "artifactDescription": "Uploaded evidence to support subsequent validation stages.",
            "governance": {
                "title": "Governance attestation",
                "description": "Confirm the model and validation plan are ready to proceed.",
                "status": "Pending review",
                "checklist": [
                    "Model is registered in the model inventory",
                    "Risk tier assignment has been documented",
                    "Submitted artifacts cover dataset, MDD, and training code",
                    "Previous validation findings (if any) have been reviewed",
                    "Regulatory scope (IFRS 9 / SS1/23 / SS11/13) is identified",
                    "Independent validation team has no conflict of interest",
                    "Validation plan has been approved by the Head of Model Risk",
                ],
            },
            "nextStep": {
                "description": "Once intake is confirmed, proceed to Stage 2 data validation and automated checks.",
                "label": "Proceed to Stage 2",
                "path": "/validation/data-quality",
            },
        },
    }

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*-harshads-projects-d63c4e68\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/validation/intake")
async def validation_intake(mode: str = "clean") -> Dict[str, Any]:
    return _build_validation_intake_snapshot(mode)

@app.post("/data/feature-decision-log")
async def feature_decision_log(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    """Return the Feature Decision Log CSV (exact format as the original Streamlit app).
    This reconstructs the training-split plan and fe_summary then returns a CSV payload.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    task_type = detect_task_type(df[target_col])
    X, y, _ = finalize_xy(df, col_types, target_col)
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=0.15, val_size=0.15,
        task_type=task_type, random_state=42,
    )
    plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
    X_engineered, fe_summary = apply_feature_engineering(X_train, plan)

    # Recreate the exact log rows as in the Streamlit app
    _orig_cols = list(X.columns)
    _fe_iv = plan.get("iv_scores", {})
    _fe_vif = plan.get("multicollinearity", {}).get("vif", {})
    _transformed_src = set(
        plan.get("log_transform_cols", [])
        + plan.get("binning_cols", [])[:5]
        + plan.get("freq_encoding_cols", [])
        + plan.get("woe_cols", [])
    )
    _col_reason: dict = {}
    for _fstep in plan.get("applied_steps", []):
        for _fc in _fstep.get("columns", []):
            _col_reason[_fc] = f"{_fstep['step']}: {_fstep.get('reason','')}"
    _removed_set = set(fe_summary.get("removed", []))
    _log_rows = []
    for _fc in _orig_cols:
        if _fc in _removed_set:
            _dec, _rsn = "Removed", _col_reason.get(_fc, "Removed during feature engineering")
        elif _fc in _transformed_src:
            _dec, _rsn = "Transformed", _col_reason.get(_fc, "Transformation applied")
        else:
            _dec, _rsn = "Retained", "No transformation required"
        _log_rows.append({
            "Feature": _fc, "Decision": _dec, "Reason": _rsn,
            "IV Score": _fe_iv.get(_fc, ""), "VIF Score": _fe_vif.get(_fc, ""),
        })
    for _fc in fe_summary.get("added", []):
        _rsn = "New feature created during engineering"
        for _sfx in ("_log", "_bin", "_freq", "_woe"):
            if _fc.endswith(_sfx):
                _src = _fc[: -len(_sfx)]
                if _src in _col_reason:
                    _rsn = _col_reason[_src]
                    break
        if "_x_" in _fc and _rsn == "New feature created during engineering":
            for _part in _fc.split("_x_"):
                if _part in _col_reason:
                    _rsn = _col_reason[_part]
                    break
        _log_rows.append({
            "Feature": _fc, "Decision": "Added", "Reason": _rsn,
            "IV Score": _fe_iv.get(_fc, ""), "VIF Score": _fe_vif.get(_fc, ""),
        })

    # Create CSV bytes
    csv_bytes = pd.DataFrame(_log_rows).to_csv(index=False).encode("utf-8")
    return {"file_name": "feature_decision_log.csv", "content_base64": base64.b64encode(csv_bytes).decode("utf-8")}


class ComplianceRequest(BaseModel):
    stage: str
    payload: Dict[str, Any]


class TierRequest(BaseModel):
    training_config: Dict[str, Any]
    metrics: Dict[str, Any]
    fe_summary: Optional[Dict[str, Any]] = None


class ECLConfigRequest(BaseModel):
    lgd_method: str = "fixed"
    lgd_fixed: float = 0.45
    ltv_col: Optional[str] = None
    lgd_haircut: float = 0.20
    lgd_floor: float = 0.05
    lgd_cap: float = 0.95
    ead_undrawn_col: Optional[str] = None
    ead_ccf: float = 1.0
    pd_relative_threshold: float = 1.5
    pd_absolute_threshold: float = 0.03
    dpd_sicr_threshold: int = 30
    dpd_impaired_threshold: int = 90
    credit_impaired_pd_floor: float = 0.20
    maturity_col: Optional[str] = None
    dpd_col: Optional[str] = None
    orig_pd_col: Optional[str] = None


_agent2: Optional[Agent2] = None


def _load_agent2() -> Optional[Agent2]:
    global _agent2
    if _agent2 is not None:
        return _agent2
    try:
        _agent2 = Agent2(str(RULES_PATH))
    except Exception:
        _agent2 = None
    return _agent2


async def _read_dataframe(
    file: Optional[UploadFile] = None,
    csv_text: Optional[str] = None,
    synthetic_samples: Optional[int] = None,
) -> pd.DataFrame:
    if synthetic_samples and synthetic_samples > 0:
        return generate_synthetic_credit_dataset(n_samples=synthetic_samples)

    if file is not None:
        name = file.filename.lower()
        if name.endswith(".csv"):
            file.file.seek(0)
            return pd.read_csv(file.file, keep_default_na=True)
        if name.endswith(('.xls', '.xlsx')):
            file.file.seek(0)
            return pd.read_excel(file.file, engine="openpyxl")
        raise HTTPException(status_code=400, detail="Unsupported file type. Use CSV or XLSX.")

    if csv_text:
        return pd.read_csv(io.StringIO(csv_text), keep_default_na=True)

    raise HTTPException(status_code=400, detail="Provide a file upload, CSV text, or synthetic_samples.")


def _serialize_dataframe(df: pd.DataFrame, max_rows: int = 5) -> Dict[str, Any]:
    return {
        "shape": list(df.shape),
        "columns": df.columns.astype(str).tolist(),
        "preview": df.head(max_rows).replace({pd.NA: None}).to_dict(orient="records"),
    }


def _to_base64(obj: Any) -> str:
    buffer = io.BytesIO()
    joblib.dump(obj, buffer)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _from_base64(encoded: str) -> Any:
    try:
        raw = base64.b64decode(encoded.encode("utf-8"))
        return joblib.load(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load artifact: {exc}")


def _infer_target_column(df: pd.DataFrame, requested_target: Optional[str] = None) -> Optional[str]:
    if requested_target is not None:
        if requested_target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{requested_target}' not found")
        return requested_target

    target_candidates = detect_target_candidates(df)
    priority_names = {"default", "target", "label", "y", "loan_status"}
    for col in df.columns.astype(str):
        col_lower = col.lower()
        if col_lower in priority_names:
            return col

    if target_candidates:
        preferred = None
        for candidate in target_candidates:
            candidate_lower = candidate.lower()
            if any(keyword in candidate_lower for keyword in ("default", "target", "label", "y", "outcome", "flag", "risk")):
                preferred = candidate
                break
        if preferred is not None:
            return preferred
        return target_candidates[0]

    for col in df.columns.astype(str):
        col_lower = col.lower()
        if col_lower in {"loan_status", "default", "target", "label", "y"}:
            return col

    for col in reversed(df.columns.tolist()):
        if "id" in col.lower():
            continue
        col_vals = df[col].dropna().unique()
        if set(col_vals).issubset({0, 1, 0.0, 1.0}) and len(col_vals) == 2:
            return col

    return None


def _build_data_profile(
    df: pd.DataFrame,
    target_col: Optional[str] = None,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    col_types = detect_column_types(df)
    target_candidates = detect_target_candidates(df)
    resolved_target_col = _infer_target_column(df, target_col)
    task_type = None
    if resolved_target_col is not None:
        task_type = detect_task_type(df[resolved_target_col])

    leakage_risk_cols: List[str] = []
    if resolved_target_col is not None and task_type == "binary":
        target_numeric = pd.to_numeric(df[resolved_target_col], errors="coerce")
        if target_numeric.notna().sum() >= 2:
            for col in col_types.get("numeric", []):
                if col == target_col:
                    continue
                try:
                    corr = df[col].corr(target_numeric)
                    if pd.notna(corr) and abs(corr) > 0.95:
                        leakage_risk_cols.append(col)
                except Exception:
                    pass

    date_integrity: Dict[str, Any] = {}
    for dt_col in col_types.get("datetime", []):
        try:
            parsed = pd.to_datetime(df[dt_col], errors="coerce")
            valid = parsed.dropna()
            if valid.empty:
                continue
            today = pd.Timestamp.today().normalize()
            future_count = int((valid > today).sum())
            ancient_count = int((valid.dt.year < 1900).sum())
            date_integrity[dt_col] = {
                "min_date": str(valid.min().date()),
                "max_date": str(valid.max().date()),
                "future_count": future_count,
                "ancient_count": ancient_count,
            }
        except Exception:
            continue

    missing_cells = int(df.isna().sum().sum())
    total_cells = int(df.shape[0] * df.shape[1]) if df.shape[0] and df.shape[1] else 0
    missing_percentage = round((missing_cells / total_cells * 100) if total_cells else 0.0, 4)
    missing_by_column: Dict[str, Dict[str, Union[int, float]]] = {}
    for col in df.columns.astype(str):
        count = int(df[col].isna().sum())
        pct = round((count / df.shape[0] * 100) if df.shape[0] else 0.0, 4)
        missing_by_column[col] = {"count": count, "percentage": pct}

    duplicate_rows = int(df.duplicated().sum())
    duplicate_rate = round((duplicate_rows / len(df) * 100) if len(df) else 0.0, 4)
    numeric_feature_count = len(col_types.get("numeric", []))
    categorical_feature_count = len(col_types.get("categorical", []))

    outlier_analysis: Dict[str, Any] = {}
    for col in list(col_types.get("numeric", []))[:8]:
        try:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = ((series < lower) | (series > upper)).sum()
            outlier_frac = round(float(outliers / len(series)), 4) if len(series) else 0.0
            outlier_analysis[col] = {
                "outlier_count": int(outliers),
                "outlier_fraction": outlier_frac,
                "has_outliers": bool(outlier_frac > 0.02),
            }
        except Exception:
            continue

    class_distribution: Optional[Dict[str, int]] = None
    if resolved_target_col is not None and resolved_target_col in df.columns:
        class_distribution = {
            str(k): int(v)
            for k, v in df[resolved_target_col].value_counts(dropna=False).to_dict().items()
        }

    # For large datasets, sample data for expensive computations
    df_sample = df.sample(n=min(5000, len(df)), random_state=42) if len(df) > 5000 else df
    
    numeric_columns = list(col_types.get("numeric", []))
    numeric_columns = numeric_columns[:10]
    correlation_matrix: Dict[str, Any] = {"columns": numeric_columns, "values": []}
    if len(numeric_columns) >= 1:
        try:
            corr = df_sample[numeric_columns].corr(method="pearson")
            correlation_matrix["values"] = corr.fillna(0).round(4).values.tolist()
        except Exception:
            correlation_matrix["values"] = []

    summary_stats = []
    try:
        description = df_sample.describe(include="all").T.round(3)
        summary_stats = description.replace({np.nan: ""}).reset_index().rename(columns={"index": "Column"}).to_dict(orient="records")
    except Exception:
        summary_stats = []

    column_type_table = []
    for col in df.columns.astype(str):
        series = df[col]
        column_type_table.append({
            "Column": col,
            "Detected Type": next((t for t, cols in col_types.items() if col in cols), "unknown"),
            "Pandas Dtype": str(series.dtype),
            "Unique Values": int(series.nunique(dropna=True)),
            "Non-Null Count": int(series.notna().sum()),
        })

    distribution_histograms = []
    for col in list(col_types.get("numeric", []))[:4]:
        values = pd.to_numeric(df_sample[col], errors="coerce").dropna()
        if values.empty:
            distribution_histograms.append({"column": col, "bins": [], "counts": []})
            continue
        counts, bin_edges = np.histogram(values, bins=20)
        distribution_histograms.append({
            "column": col,
            "bins": [float(x) for x in bin_edges.tolist()],
            "counts": [int(x) for x in counts.tolist()],
        })

    data_dictionary = []
    for col in df.columns.astype(str):
        series = df[col]
        miss_n = int(series.isna().sum())
        miss_pct = round((miss_n / len(df) * 100) if len(df) else 0.0, 2)
        unique_values = int(series.nunique(dropna=True))
        is_num = pd.api.types.is_numeric_dtype(series)
        try:
            dd_min = round(float(series.min()), 4) if is_num else ""
            dd_max = round(float(series.max()), 4) if is_num else ""
            dd_mean = round(float(series.mean()), 4) if is_num else ""
        except Exception:
            dd_min = ""
            dd_max = ""
            dd_mean = ""
        sample_values = ", ".join(str(v) for v in series.dropna().unique()[:3])
        data_dictionary.append({
            "Column": col,
            "Detected Type": next((t for t, cols in col_types.items() if col in cols), "unknown"),
            "Missing Count": miss_n,
            "Missing %": miss_pct,
            "Unique Values": unique_values,
            "Min": dd_min,
            "Max": dd_max,
            "Mean": dd_mean,
            "Sample Values": sample_values,
        })

    target_summary: Dict[str, Any] = {}
    if resolved_target_col is not None and resolved_target_col in df.columns:
        target_values = df[resolved_target_col].dropna()
        task_label = "Unknown"
        if task_type == "binary":
            task_label = "Binary classification"
        elif task_type == "multiclass":
            task_label = "Multiclass classification"
        elif task_type == "regression":
            task_label = "Regression"

        imbalance_ratio: Optional[float] = None
        is_imbalanced = False
        if len(target_values) > 0:
            counts = target_values.value_counts(dropna=False)
            if len(counts) >= 2 and counts.min() > 0:
                imbalance_ratio = round(float(counts.max() / counts.min()), 2)
                is_imbalanced = imbalance_ratio > 3

        target_summary = {
            "selected_target": resolved_target_col,
            "task_type": task_type,
            "task_label": task_label,
            "target_candidates": target_candidates,
            "imbalance_ratio": imbalance_ratio,
            "is_imbalanced": is_imbalanced,
            "suggestion": (
                "Imbalanced target distribution detected; consider class weighting or resampling."
                if is_imbalanced else "Target distribution appears balanced for the current profile."
            ),
        }

    profile = {
        "shape": list(df.shape),
        "columns": df.columns.astype(str).tolist(),
        "col_types": col_types,
        "target_col": resolved_target_col,
        "target_candidates": target_candidates,
        "task_type": task_type,
        "dataset_name": dataset_name,
        "leakage_risk_cols": leakage_risk_cols,
        "date_integrity": date_integrity,
        "missing_cells": missing_cells,
        "missing_percentage": missing_percentage,
        "missing_by_column": missing_by_column,
        "duplicate_rows": duplicate_rows,
        "duplicate_rate": duplicate_rate,
        "numeric_feature_count": numeric_feature_count,
        "categorical_feature_count": categorical_feature_count,
        "class_distribution": class_distribution,
        "outlier_analysis": outlier_analysis,
        "correlation_matrix": correlation_matrix,
        "summary_stats": summary_stats,
        "column_type_table": column_type_table,
        "distribution_histograms": distribution_histograms,
        "data_dictionary": data_dictionary,
        "data_preview": _serialize_dataframe(df, max_rows=10)["preview"],
        "target_summary": target_summary,
    }

    if resolved_target_col is not None:
        agent = _load_agent2()
        if agent is not None:
            try:
                agent.check_data(df, col_types, leakage_risk_cols=leakage_risk_cols)
                agent.check_rules_from_agent1("data", {
                    "n_rows": len(df),
                    "n_cols": len(df.columns),
                    "missing_pct": round(float(df.isna().mean().mean()), 4),
                    "target_col": resolved_target_col,
                })
                profile["agent2_flags_data"] = agent.get_stage_summary("data")["flags"]
                profile["agent2_report"] = agent.get_full_report()
            except Exception as exc:
                profile["agent2_error"] = f"Agent2 data check failed: {exc}"
                profile["agent2_flags_data"] = []
                profile["agent2_report"] = {
                    "metadata": {"generated_at": None, "rules_source": "rag_store/rules.json", "stages_checked": [], "total_rules": 0, "rules_passed": 0, "rules_flagged": 0, "compliance_score": 0},
                    "summary": {"high_severity": 0, "medium_severity": 0, "low_severity": 0, "overall_status": "WARN"},
                    "flags_by_stage": {"data": []},
                    "flags_by_source": {},
                    "all_flags": [],
                    "model_tier": None,
                }

    return profile


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/data/upload")
async def upload_data(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    dataset_name = file.filename if file is not None else "Synthetic Credit Dataset"
    profile = _build_data_profile(df, dataset_name=dataset_name)
    if synthetic_samples and synthetic_samples > 0 and file is None:
        profile["csv_text"] = df.to_csv(index=False)
        profile["source_type"] = "synthetic"
        profile["synthetic_samples"] = int(synthetic_samples)
    else:
        profile["source_type"] = "file"
    return profile


@app.post("/data/profile")
async def data_profile(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: Optional[str] = Form(None),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    dataset_name = file.filename if file is not None else None
    profile = _build_data_profile(df, target_col=target_col, dataset_name=dataset_name)
    if target_col is not None:
        profile["preprocessing_report"] = build_preprocessing_report(df, profile["col_types"], target_col)
    return profile


def _json_safe(obj: Any) -> Any:
    """Recursively convert numpy scalar types to native Python so dict/list
    structures built from pandas/numpy computations serialize cleanly."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, pd.DataFrame):
        return _json_safe(obj.to_dict(orient="records"))
    return obj


@app.post("/data/preprocess")
async def preprocess_data(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    # ── Confirmed reviewer choices (all optional; sensible "accept the
    #    platform's proposal" defaults apply when omitted) ──
    treatment_overrides: Optional[str] = Form(None),  # JSON {col: treatment}
    drop_cols: Optional[str] = Form(None),             # JSON [col, ...]
    transform_choices: Optional[str] = Form(None),     # JSON {col: "none"|"log1p"|"yeo_johnson"}
    strategy_override: Optional[str] = Form(None),     # "mice" | "knn" | "median"
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")

    test_size = float(test_size)
    val_size = float(val_size)
    if not 0 < test_size < 1:
        raise HTTPException(status_code=400, detail="test_size must be between 0 and 1")
    if not 0 < val_size < 1:
        raise HTTPException(status_code=400, detail="val_size must be between 0 and 1")
    if test_size + val_size >= 1:
        raise HTTPException(status_code=400, detail="test_size + val_size must be less than 1")

    def _parse_json_form(raw: Optional[str], default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in request: {exc}")

    _treatment_overrides: Dict[str, str] = _parse_json_form(treatment_overrides, {})
    _drop_cols: List[str] = _parse_json_form(drop_cols, [])
    _transform_choices: Dict[str, str] = _parse_json_form(transform_choices, {})

    task_type = detect_task_type(df[target_col])
    X, y, clean_info = finalize_xy(df, col_types, target_col)

    # Split FIRST — every statistic learned below (missing-value treatment
    # proposal, imputation strategy, skew/transform recommendations, the
    # fitted preprocessor) comes from the TRAINING split only. This matches
    # /models/train and the Streamlit reference app's leakage-safe design;
    # the previous version of this endpoint built its report from the full
    # pre-split dataset, which this fixes.
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=random_seed,
    )

    # ── Phase 1: PROPOSE — classify_missing_treatment() on TRAIN only.
    #    Nothing is applied yet; this is purely diagnostic. ──
    missing_treatment_proposal = classify_missing_treatment(X_train, col_types)

    # ── Phase 2: resolve the CONFIRMED treatment per column ──
    # A column resolved to "review_flag" (>40% missing) that the reviewer
    # chose to KEEP (not in drop_cols) can't stay "review_flag" — that
    # treatment means "leave untouched", so it needs a real, recalibrated
    # treatment instead. See classify_missing_treatment's force_include_cols
    # docstring.
    treatment_map: Dict[str, Dict[str, Any]] = {}
    recalibrated_cols: List[Dict[str, str]] = []
    for col, info in missing_treatment_proposal.items():
        if col in _drop_cols:
            continue
        resolved_treatment = _treatment_overrides.get(col, info["treatment"])

        if resolved_treatment == "review_flag":
            recalibrated = classify_missing_treatment(
                X_train[[col]], col_types, force_include_cols=[col]
            )
            if col in recalibrated:
                treatment_map[col] = {
                    **recalibrated[col],
                    "reason": (
                        f"Recalibrated — kept despite "
                        f"{info['evidence'].get('missing_pct', 0):.1%} missing (over the "
                        f"{int(REVIEW_MISSING_THRESHOLD * 100)}% review threshold). "
                        f"{recalibrated[col]['reason']}"
                    ),
                }
                recalibrated_cols.append({"column": col, "treatment": treatment_map[col]["treatment"]})
                continue
            treatment_map[col] = {
                "treatment": "statistical", "reason": info["reason"], "evidence": info["evidence"],
            }
            continue

        if col in _treatment_overrides:
            treatment_map[col] = {
                "treatment": resolved_treatment,
                "reason": f"Manually overridden by reviewer (platform proposed: {info['treatment']}).",
                "evidence": info["evidence"],
            }
        else:
            treatment_map[col] = info

    # ── Phase 3: joint imputation strategy for the "statistical" block ──
    statistical_cols = [c for c, v in treatment_map.items() if v["treatment"] == "statistical"]
    imputation_strategy = select_imputation_strategy(X_train, statistical_cols)
    if strategy_override in ("mice", "knn", "median") and statistical_cols:
        imputation_strategy = {
            "method": strategy_override,
            "reason": (
                f"Manually overridden by reviewer "
                f"(platform proposed: {imputation_strategy['method']})."
            ),
            "diagnostics": imputation_strategy.get("diagnostics", {}),
        }

    # ── Phase 4: fit SemanticImputer on TRAIN only, apply unchanged to val/test ──
    col_types_for_fit = {k: [c for c in v if c not in _drop_cols] for k, v in col_types.items()}
    imputer = SemanticImputer(
        col_types=col_types_for_fit, treatment_map=treatment_map, strategy_choice=imputation_strategy,
    )
    imputer.fit(X_train)
    X_train = imputer.transform(X_train)
    X_val = imputer.transform(X_val)
    X_test = imputer.transform(X_test)

    _drop_cols_present = [c for c in _drop_cols if c in X_train.columns]
    if _drop_cols_present:
        X_train = X_train.drop(columns=_drop_cols_present)
        X_val = X_val.drop(columns=[c for c in _drop_cols_present if c in X_val.columns], errors="ignore")
        X_test = X_test.drop(columns=[c for c in _drop_cols_present if c in X_test.columns], errors="ignore")

    # ── Phase 5: preprocessing report (scaler/encoder strategy + skew/transform
    #    recommendations) on the now-imputed TRAIN split. transform_choices is
    #    what actually drives the fitted ColumnTransformer below — nothing
    #    here auto-applies a log/Yeo-Johnson transform on its own. ──
    prep_report = build_preprocessing_report(
        X_train.assign(**{target_col: y_train}), col_types, target_col,
        transform_choices=_transform_choices,
    )

    preprocessor = rebuild_preprocessor_for(X_train, col_types, target_col, prep_report)
    preprocessor.fit(X_train)
    processed_matrix = preprocessor.transform(X_train)
    processed_feature_names = get_feature_names_from_fitted_preprocessor(preprocessor)
    processed_df = pd.DataFrame(processed_matrix, columns=processed_feature_names)
    processed_df[target_col] = y_train.reset_index(drop=True)

    def _summary_row(column: str, feature_type: str, scaler: str, imputer_label: str, encoding: str, outlier_strategy: str, transform: str):
        return {
            "feature": column,
            "type": feature_type,
            "scaler": scaler,
            "imputer": imputer_label,
            "encoding": encoding,
            "outlier_strategy": outlier_strategy,
            "transform": transform,
        }

    strategy_summary = []
    for col, info in prep_report.get("numeric", {}).items():
        scaler = "Robust" if info.get("scaler") == "robust" else "Standard"
        imputer_label = info.get("imputer", "mean").capitalize()
        encoding = "-"
        outlier_strategy = "Robust scaling" if info.get("has_outliers") else "Standard scaling"
        confirmed_t = _transform_choices.get(col, "none")
        rec_t = (info.get("transform_recommendation") or {}).get("transform", "none")
        transform_label = (
            f"{confirmed_t.replace('_', '-').title()} (confirmed)" if confirmed_t in ("log1p", "yeo_johnson")
            else (f"Suggested: {rec_t.replace('_', '-').title()}" if rec_t in ("log1p", "yeo_johnson") else "-")
        )
        strategy_summary.append(_summary_row(col, "Numeric", scaler, imputer_label, encoding, outlier_strategy, transform_label))

    for col, info in prep_report.get("categorical", {}).items():
        scaler = "-"
        imputer_label = "Mode"
        encoding = "OneHot" if info.get("encoding") == "onehot" else "Ordinal"
        outlier_strategy = "-"
        strategy_summary.append(_summary_row(col, "Categorical", scaler, imputer_label, encoding, outlier_strategy, "-"))

    for col in prep_report.get("boolean", {}):
        strategy_summary.append(_summary_row(col, "Boolean", "-", "-", "-", "-", "-"))

    for col in prep_report.get("datetime", {}):
        strategy_summary.append(_summary_row(col, "Datetime", "-", "-", "-", "-", "-"))

    feature_names = list(X_train.columns)
    split_stats = compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test)

    class_distribution_chart = []
    for split_name in ["train", "val", "test"]:
        class_dist = split_stats.get(f"{split_name}_class_dist", {}) or {}
        for cls, prop in class_dist.items():
            class_distribution_chart.append({
                "split": split_name.capitalize(),
                "class": str(cls),
                "proportion": float(prop),
            })

    summary_metrics = {
        "features_basic": X_train.shape[1],
        "numeric_columns": len(prep_report.get("numeric", {})),
        "categorical_columns": len(prep_report.get("categorical", {})),
        "duplicates_removed": clean_info.get("duplicates_removed", 0),
        "ecl_only_cols_dropped": clean_info.get("ecl_only_cols_dropped", []),
    }

    return {
        "col_types": col_types,
        "target_col": target_col,
        "feature_names": feature_names,
        "processed_feature_names": processed_feature_names,
        "x_shape": list(X_train.shape),
        "y_shape": list(y_train.shape),
        "feature_count": X_train.shape[1],
        "numeric_feature_count": len(prep_report.get("numeric", {})),
        "categorical_feature_count": len(prep_report.get("categorical", {})),
        "duplicates_removed": clean_info.get("duplicates_removed", 0),
        "ecl_only_cols_dropped": clean_info.get("ecl_only_cols_dropped", []),
        "split_config": {"test_size": test_size, "val_size": val_size, "random_seed": int(random_seed)},
        "split_stats": split_stats,
        "class_distribution_chart": class_distribution_chart,
        "summary_metrics": summary_metrics,
        "x_preview": _serialize_dataframe(X_train, max_rows=5)["preview"],
        "processed_dataset_preview": _serialize_dataframe(processed_df, max_rows=5)["preview"],
        "target_preview": y_train.head(5).replace({pd.NA: None}).tolist(),
        "y_preview": y_train.head(5).replace({pd.NA: None}).tolist(),
        "preprocessing_report": prep_report,
        "preprocessing_strategy_summary": strategy_summary,
        "processed_dataset_csv": processed_df.to_csv(index=False),
        # ── New: the interactive missing-value + transform workflow ──
        "missing_treatment_proposal": _json_safe(missing_treatment_proposal),
        "applied_treatment_map": _json_safe(treatment_map),
        "imputation_strategy": _json_safe(imputation_strategy),
        "recalibrated_columns": recalibrated_cols,
        "dropped_columns": _drop_cols_present,
        "transform_recommendations": _json_safe(prep_report.get("transform_recommendations", {})),
        "applied_transform_choices": _transform_choices,
        "missing_value_limitation_note": MISSING_VALUE_LIMITATION_NOTE,
        "review_missing_threshold": REVIEW_MISSING_THRESHOLD,
        "original_dataset_csv": df.to_csv(index=False),
    }


@app.post("/data/drop-impact")
async def drop_impact(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    columns: str = Form(...),  # JSON list of column names to analyze
) -> Dict[str, Any]:
    """
    On-demand "impact of dropping this feature" analysis for one or more
    sparse (review_flag) columns — called lazily by the frontend when a
    reviewer expands a column's impact panel, not on every /data/preprocess
    call, since it re-derives the correlation matrix per requested column.

    Re-derives the SAME train split /data/preprocess uses (same file, target,
    split config) so the estimate is computed on training data only — no
    leakage from validation/test. Returns a lightweight, standalone estimate
    (predictive importance via a quick IV, redundancy via correlation with
    other numeric features) — NOT the authoritative IV/WOE from
    /data/feature-engineering, which runs later on cleaned/engineered data.
    See preprocessing_new.estimate_drop_impact() for the full explanation.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")

    test_size = float(test_size)
    val_size = float(val_size)
    if not 0 < test_size < 1:
        raise HTTPException(status_code=400, detail="test_size must be between 0 and 1")
    if not 0 < val_size < 1:
        raise HTTPException(status_code=400, detail="val_size must be between 0 and 1")
    if test_size + val_size >= 1:
        raise HTTPException(status_code=400, detail="test_size + val_size must be less than 1")

    try:
        requested_cols: List[str] = json.loads(columns) if columns else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in 'columns': {exc}")
    if not isinstance(requested_cols, list) or not requested_cols:
        raise HTTPException(status_code=400, detail="'columns' must be a non-empty JSON list of column names")

    task_type = detect_task_type(df[target_col])
    X, y, _clean_info = finalize_xy(df, col_types, target_col)
    X_train, _X_val, _X_test, y_train, _y_val, _y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=random_seed,
    )

    results: Dict[str, Any] = {}
    for col in requested_cols:
        if col not in X_train.columns:
            results[col] = {"error": f"Column '{col}' not found in the training features."}
            continue
        results[col] = estimate_drop_impact(col, X_train, y_train, col_types)

    return {"drop_impact": _json_safe(results)}


@app.post("/data/feature-engineering")
async def feature_engineering(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
    ead_mode: Optional[str] = Form(None),
    ead_col: Optional[str] = Form(None),
    ead_loan_col: Optional[str] = Form(None),
    ead_interest_col: Optional[str] = Form(None),
    ead_years_col: Optional[str] = Form(None),
    ead_term_col: Optional[str] = Form(None),
    ead_years_months: Optional[str] = Form(None),
    ead_term_months: Optional[str] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    task_type = detect_task_type(df[target_col])
    X, y, _ = finalize_xy(df, col_types, target_col)
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=0.15, val_size=0.15,
        task_type=task_type, random_state=42,
    )
    plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
    X_engineered, fe_summary = apply_feature_engineering(X_train, plan)
    numeric_cols = [c for c in col_types.get("numeric", []) if c in X_train.columns]
    gini_scores = compute_univariate_gini(X_train, y_train, numeric_cols) if task_type == "binary" else {}
    ead_configuration = resolve_ead_configuration(
        df,
        mode=ead_mode or "auto",
        ob_col=ead_col,
        la_col=ead_loan_col,
        ir_col=ead_interest_col,
        ye_col=ead_years_col,
        tm_col=ead_term_col,
        ye_months=str(ead_years_months).lower() in {"true", "1", "yes"},
        tm_months=str(ead_term_months).lower() in {"true", "1", "yes"},
    )
    engineered_feature_names = list(X_engineered.columns.astype(str))
    dropped_features = [col for col in fe_summary.get("removed", []) if col in X_train.columns]
    selected_features = engineered_feature_names
    encoding_summary = {
        "log_transform_columns": plan.get("log_transform_cols", []),
        "interaction_pairs": plan.get("interaction_pairs", []),
        "binning_columns": plan.get("binning_cols", [])[:5],
        "frequency_encoding_columns": plan.get("freq_encoding_cols", []),
        "woe_columns": plan.get("woe_cols", []),
        "low_variance_columns": plan.get("low_variance_cols", []),
        "low_iv_columns": plan.get("low_iv_cols", []),
    }
    feature_engineering_report = {
        "applied_steps": plan.get("applied_steps", []),
        "summary": fe_summary,
        "multicollinearity": plan.get("multicollinearity", {}),
        "gini_scores": gini_scores,
        "ead_configuration": ead_configuration,
    }
    feature_importance_summary = {
        "mi_scores": plan.get("mi_scores", {}),
        "gini_scores": gini_scores,
        "iv_scores": plan.get("iv_scores", {}),
    }

    return {
        "col_types": col_types,
        "target_col": target_col,
        "task_type": task_type,
        "feature_engineering_plan": plan,
        "feature_engineering_summary": fe_summary,
        "engineered_feature_names": engineered_feature_names,
        "selected_features": selected_features,
        "dropped_features": dropped_features,
        "encoding_summary": encoding_summary,
        "feature_engineering_report": feature_engineering_report,
        "feature_importance_summary": feature_importance_summary,
        "x_engineered_shape": list(X_engineered.shape),
        "x_engineered_preview": _serialize_dataframe(X_engineered, max_rows=5)["preview"],
        "final_engineered_dataset_preview": _serialize_dataframe(X_engineered, max_rows=5)["preview"],
        "x_engineered_csv": X_engineered.to_csv(index=False),
        "gini_scores": gini_scores,
        "ead_configuration": ead_configuration,
        "available_numeric_columns": [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])],
    }


@app.post("/models/recommend")
async def recommend_models_endpoint(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: Optional[str] = Form(None),
    n_samples: Optional[int] = Form(None),
    n_features: Optional[int] = Form(None),
    class_imbalance_ratio: Optional[float] = Form(None),
    task_type: Optional[str] = Form(None),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    if file is not None or csv_text or synthetic_samples:
        df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
        if target_col is None or target_col not in df.columns:
            raise HTTPException(status_code=400, detail="target_col is required for dataset-based recommendations")
        col_types = detect_column_types(df)
        task_type = detect_task_type(df[target_col])

        # Prepare data (drop ids, dedupe) but DO NOT fit preprocessors here
        X, y, preproc, prep_report, feature_names = prepare_data(df, col_types, target_col)

        # Split the data exactly like the original Streamlit flow so recommendations
        # are based on the TRAIN set after FE (parity requirement).
        X_train, X_val, X_test, y_train, y_val, y_test = split_data(
            X, y, test_size=0.15, val_size=0.15, task_type=task_type, random_state=42
        )

        # Learn FE plan on TRAIN and apply to TRAIN to get the actual feature set
        try:
            plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
            X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
        except Exception:
            # Fallback: no FE applied
            X_train_engineered = X_train.copy()
            fe_summary = None

        n_samples = X_train_engineered.shape[0]
        n_features = X_train_engineered.shape[1]
        if task_type == "binary":
            vc = y_train.value_counts()
            class_imbalance_ratio = float(vc.max() / vc.min()) if vc.min() > 0 else 5.0
    else:
        if n_samples is None or n_features is None or task_type is None:
            raise HTTPException(status_code=400, detail="Either dataset or numeric summary values are required")
        if class_imbalance_ratio is None:
            class_imbalance_ratio = 1.0
    recs = recommend_models(
        n_samples=n_samples,
        n_features=n_features,
        class_imbalance_ratio=class_imbalance_ratio,
        task_type=task_type,
    )
    return {
        "recommendations": recs,
        "training": {
            "train_n": int(n_samples),
            "train_features": int(n_features),
            "imbalance_ratio": float(class_imbalance_ratio),
        },
        "task_type": task_type,
        "feature_engineering_summary": fe_summary if 'fe_summary' in locals() else None,
    }

        
@app.post("/models/train")
async def train_model_endpoint(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    model_name: str = Form(...),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    use_cv: bool = Form(False),
    cv_folds: int = Form(5),
    use_hyperopt: bool = Form(False),
    use_class_weight: bool = Form(False),
    scale_pos_weight: float = Form(1.0),
    manual_params: Optional[str] = Form(None),
    use_feature_engineering: bool = Form(False),
    synthetic_samples: Optional[int] = Form(None),
    use_oot: bool = Form(False),
    date_col: Optional[str] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    col_types = detect_column_types(df)
    task_type = detect_task_type(df[target_col])
    X, y, _ = finalize_xy(df, col_types, target_col)
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=random_seed,
    )

    # ── Origination/observation date for Out-of-Time (OOT) validation ──
    # Use the reviewer-selected date column if provided and valid, otherwise
    # fall back to the first auto-detected datetime column (same detection
    # `detect_column_types` already exposes via the data-profile endpoint).
    origination_date_col = date_col if (date_col and date_col in df.columns) else None
    if origination_date_col is None:
        datetime_candidates = col_types.get("datetime", [])
        if datetime_candidates:
            origination_date_col = datetime_candidates[0]

    dates_train = None
    if origination_date_col and origination_date_col in df.columns:
        try:
            dates_train = df.loc[X_train.index, origination_date_col]
        except Exception:
            dates_train = None
    prep_report = build_preprocessing_report(X_train.assign(**{target_col: y_train}), col_types, target_col)
    fe_summary = None
    plan = None
    if use_feature_engineering:
        plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
        X_train, fe_summary = apply_feature_engineering(X_train, plan)
        X_val, _ = apply_feature_engineering(X_val, plan)
        X_test, _ = apply_feature_engineering(X_test, plan)
    if manual_params:
        try:
            manual_params_dict = json.loads(manual_params)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"manual_params must be valid JSON: {exc}")
    else:
        manual_params_dict = None
    if manual_params_dict is not None:
        model = get_model_instance(model_name, task_type)
        valid_keys = set(model.get_params().keys())
        manual_params_dict = {k: v for k, v in manual_params_dict.items() if k in valid_keys}
        model = type(model)(**manual_params_dict)
    else:
        model = get_model_instance(
            model_name,
            task_type,
            class_weight="balanced" if use_class_weight else None,
            scale_pos_weight=scale_pos_weight if model_name == "XGBoost" else None,
        )
    param_grid = None
    if use_hyperopt:
        param_grid = get_hyperparameter_grid(model_name, task_type)
    pipeline, training_info, real_feature_names = train_model(
        X_train, y_train,
        col_types=col_types,
        target_col=target_col,
        prep_report=prep_report,
        model=model,
        use_smote=False,
        use_cv=use_cv,
        cv_folds=cv_folds,
        use_hyperopt=use_hyperopt,
        param_grid=param_grid,
        task_type=task_type,
        model_name=model_name,
        dates_train=dates_train,
        use_oot=use_oot,
    )
    split_stats = compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test)

    # Evaluate on hold-out test set to mirror the original Streamlit training workflow.
    y_pred = pipeline.predict(X_test)
    y_proba = None
    if hasattr(pipeline, "predict_proba"):
        try:
            y_proba = pipeline.predict_proba(X_test)
        except Exception:
            y_proba = None

    if task_type == "binary":
        metrics = compute_binary_metrics(y_test.values, y_pred, y_proba, threshold=0.5)
        hetero_input = y_proba if y_proba is not None else y_pred
        roc_curve = compute_roc_curve(y_test.values, y_proba) if y_proba is not None else []
        pr_curve = compute_pr_curve(y_test.values, y_proba) if y_proba is not None else []
        threshold_analysis = compute_threshold_analysis(y_test.values, y_proba) if y_proba is not None else []
        score_distribution = compute_score_distribution(y_test.values, y_proba) if y_proba is not None else []
        gain_chart = compute_gain_chart(y_test.values, y_proba)
    else:
        metrics = compute_regression_metrics(y_test.values, y_pred)
        hetero_input = y_pred
        roc_curve = []
        pr_curve = []
        threshold_analysis = []
        score_distribution = []
        gain_chart = []

    hetero_check = compute_heteroscedasticity_check(y_test.values, hetero_input, task_type=task_type)
    evaluation_data = {
        "metrics": metrics,
        "heteroscedasticity_check": hetero_check,
        "threshold": 0.5,
        "task_type": task_type,
        "roc_curve": roc_curve,
        "pr_curve": pr_curve,
        "threshold_analysis": threshold_analysis,
        "score_distribution": score_distribution,
        "gain_chart": gain_chart,
    }

    return {
        "task_type": task_type,
        "model_name": model_name,
        "real_feature_names": real_feature_names,
        "training_config": {
            "model_name": model_name,
            "test_size": test_size,
            "val_size": val_size,
            "random_seed": random_seed,
            "use_cv": use_cv,
            "cv_folds": cv_folds,
            "use_hyperopt": use_hyperopt,
            "use_class_weight": use_class_weight,
            "scale_pos_weight": scale_pos_weight,
            "use_feature_engineering": use_feature_engineering,
            "manual_params": manual_params_dict or {},
            "use_oot": use_oot,
            "date_col": origination_date_col,
        },
        "training_info": training_info,
        "split_stats": split_stats,
        "feature_engineering_summary": fe_summary,
        "evaluation_metrics": metrics,
        "evaluation_data": evaluation_data,
        "model_artifact": _to_base64(pipeline),
    }


def _lighten_for_comparison(model, model_name: str, max_estimators: int = 100):
    """
    Reduce ensemble size for comparison-only runs so each candidate trains
    fast. Comparison is meant to give a directional read on which model is
    worth committing to — not a final number — so trading a bit of accuracy
    for speed here is the right call. Full-fidelity numbers come from the
    dedicated /models/train run once the user picks a model.
    """
    if hasattr(model, "n_estimators") and getattr(model, "n_estimators", None):
        try:
            if model.n_estimators > max_estimators:
                model.set_params(n_estimators=max_estimators)
        except Exception:
            pass
    return model


@app.post("/models/compare")
async def compare_models_endpoint(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    model_names: str = Form(...),  # JSON-encoded list of model names
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    use_feature_engineering: bool = Form(False),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    """
    Lightweight, fast comparison across candidate models on the SAME split.

    Deliberately skips everything that makes /models/train slow when run
    N times: no cross-validation, no hyperparameter search, no OOT, no
    ROC/PR/threshold/gain-chart curves, and no base64 model-artifact
    serialization. Just fit -> predict -> summary metrics per model, so a
    reviewer can quickly see which model is worth committing to before
    running the full, config-rich /models/train on that one model.
    """
    try:
        names = json.loads(model_names)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"model_names must be a JSON array: {exc}")
    if not isinstance(names, list) or not names:
        raise HTTPException(status_code=400, detail="model_names must be a non-empty list")

    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")

    col_types = detect_column_types(df)
    task_type = detect_task_type(df[target_col])
    X, y, _ = finalize_xy(df, col_types, target_col)
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=random_seed,
    )

    prep_report = build_preprocessing_report(X_train.assign(**{target_col: y_train}), col_types, target_col)
    fe_summary = None
    if use_feature_engineering:
        plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
        X_train, fe_summary = apply_feature_engineering(X_train, plan)
        X_test, _ = apply_feature_engineering(X_test, plan)

    results = []
    for name in names:
        try:
            model = get_model_instance(name, task_type)
            model = _lighten_for_comparison(model, name)
            pipeline, training_info, _ = train_model(
                X_train, y_train,
                col_types=col_types,
                target_col=target_col,
                prep_report=prep_report,
                model=model,
                use_cv=False,
                use_hyperopt=False,
                task_type=task_type,
                model_name=name,
                use_oot=False,
            )
            y_pred = pipeline.predict(X_test)
            y_proba = None
            if hasattr(pipeline, "predict_proba"):
                try:
                    y_proba = pipeline.predict_proba(X_test)
                except Exception:
                    y_proba = None

            if task_type == "binary":
                metrics = compute_binary_metrics(y_test.values, y_pred, y_proba, threshold=0.5)
            else:
                metrics = compute_regression_metrics(y_test.values, y_pred)

            results.append({
                "model_name": name,
                **metrics,
                "training_time_s": training_info.get("training_time_s"),
            })
        except Exception as e:
            results.append({"model_name": name, "error": str(e)})

    return {
        "task_type": task_type,
        "comparison": results,
        "feature_engineering_summary": fe_summary,
    }


@app.post("/models/evaluate")
async def evaluate_model(
    model_artifact: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    threshold: float = Form(0.5),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    pipeline = _from_base64(model_artifact)
    y_true = df[target_col].values
    X_eval = df.drop(columns=[target_col], errors='ignore')
    y_pred = pipeline.predict(X_eval)
    y_proba = None
    if hasattr(pipeline, "predict_proba"):
        try:
            y_proba = pipeline.predict_proba(X_eval)
        except Exception:
            y_proba = None
    task_type = detect_task_type(df[target_col])
    if task_type == "binary":
        metrics = compute_binary_metrics(y_true, y_pred, y_proba, threshold=threshold)
        hetero_input = y_proba if y_proba is not None else y_pred
        roc_curve = compute_roc_curve(y_true, y_proba) if y_proba is not None else []
        pr_curve = compute_pr_curve(y_true, y_proba) if y_proba is not None else []
        threshold_analysis = compute_threshold_analysis(y_true, y_proba) if y_proba is not None else []
        score_distribution = compute_score_distribution(y_true, y_proba) if y_proba is not None else []
        gain_chart = compute_gain_chart(y_true, y_proba)
    else:
        metrics = compute_regression_metrics(y_true, y_pred)
        hetero_input = y_pred
        roc_curve = []
        pr_curve = []
        threshold_analysis = []
        score_distribution = []
        gain_chart = []
    hetero_check = compute_heteroscedasticity_check(y_true, hetero_input, task_type=task_type)
    return {
        "metrics": metrics,
        "heteroscedasticity_check": hetero_check,
        "threshold": threshold,
        "task_type": task_type,
        "roc_curve": roc_curve,
        "pr_curve": pr_curve,
        "threshold_analysis": threshold_analysis,
        "score_distribution": score_distribution,
        "gain_chart": gain_chart,
    }


@app.post("/models/explain")
async def explain_model(
    model_artifact: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: Optional[str] = Form(None),
    max_shap_samples: int = Form(100),
    sample_idx: int = Form(0),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col is not None and target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    pipeline = _from_base64(model_artifact)
    if target_col is not None:
        X = df.drop(columns=[target_col], errors='ignore')
    else:
        X = df
    importance_df = extract_feature_importance(pipeline)
    importance = []
    if importance_df is not None:
        importance = importance_df.to_dict(orient="records")
    shap_info: Dict[str, Any] = {"shap_available": False}
    shap_result = compute_shap_values(pipeline, X, max_samples=max_shap_samples)
    if shap_result is not None:
        explainer, shap_values, X_df, names = shap_result
        mean_abs = list(
            pd.DataFrame({"Feature": X_df.columns, "MeanAbsSHAP": np.abs(shap_values).mean(axis=0)})
            .sort_values("MeanAbsSHAP", ascending=False)
            .head(20)
            .to_dict(orient="records")
        )
        reasoning = None
        if 0 <= sample_idx < len(X_df):
            try:
                model_proba = pipeline.predict_proba(X) if hasattr(pipeline, "predict_proba") else np.zeros((len(X_df), 2))
            except Exception:
                model_proba = np.zeros((len(X_df), 2))
            reasoning = generate_prediction_reasoning(shap_values, X_df, model_proba, sample_idx, threshold=0.5)
        shap_info = {
            "shap_available": True,
            "shap_mean_abs": mean_abs,
            "sample_idx": sample_idx,
            "sample_reasoning": reasoning,
        }
    return {
        "feature_importance": importance,
        "shap": shap_info,
    }


@app.post("/validation/compliance")
async def validation_compliance(request: ComplianceRequest) -> Dict[str, Any]:
    agent = _load_agent2()
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent2 is unavailable. Missing or invalid rules.json?")
    stage = request.stage.lower()
    payload = request.payload
    flags = []
    if stage == "data":
        df = pd.DataFrame(payload.get("data", [])) if payload.get("data") else None
        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="Data payload is required for data compliance checks.")
        col_types = payload.get("col_types") or detect_column_types(df)
        leakage_risk_cols = payload.get("leakage_risk_cols")
        agent.check_data(df, col_types, leakage_risk_cols=leakage_risk_cols)
        agent.check_rules_from_agent1("data", payload.get("context", {}))
        flags = agent.get_stage_summary("data")["flags"]
    elif stage == "feature":
        plan = payload.get("feature_engineering_plan")
        if not plan:
            raise HTTPException(status_code=400, detail="feature_engineering_plan is required for feature compliance.")
        all_columns = payload.get("all_columns")
        agent.check_features(plan, all_columns=all_columns)
        agent.check_rules_from_agent1("feature", payload.get("context", {}))
        flags = agent.get_stage_summary("feature")["flags"]
    elif stage == "training":
        training_config = payload.get("training_config", {})
        training_info = payload.get("training_info", {})
        test_auc = payload.get("test_auc")
        imbalance_ratio = payload.get("imbalance_ratio")
        task_type = payload.get("task_type", "binary")
        agent.check_training(
            training_config,
            training_info=training_info,
            test_auc=test_auc,
            imbalance_ratio=imbalance_ratio,
            task_type=task_type,
        )
        agent.check_rules_from_agent1("training", payload.get("context", {}))
        flags = agent.get_stage_summary("training")["flags"]
    elif stage == "evaluation":
        metrics = payload.get("metrics")
        if not metrics:
            raise HTTPException(status_code=400, detail="metrics are required for evaluation compliance.")
        training_info = payload.get("training_info", {})
        threshold = payload.get("threshold", 0.5)
        explainability_done = payload.get("explainability_done", False)
        hetero_check = payload.get("heteroscedasticity_check")
        agent.check_evaluation(
            metrics=metrics,
            training_info=training_info,
            threshold=threshold,
            explainability_done=explainability_done,
            heteroscedasticity_result=hetero_check,
            pd_output_present=payload.get("pd_output_present", False),
            staging_logic_present=payload.get("staging_logic_present", False),
            sicr_flagged=payload.get("sicr_flagged", False),
            ecl_estimated=payload.get("ecl_estimated", False),
            concentration_analysis=payload.get("concentration_analysis", False),
            exposure_reported=payload.get("exposure_reported", False),
            past_due_breakdown=payload.get("past_due_breakdown", False),
            shap_available=payload.get("shap_available", False),
        )
        agent.check_rules_from_agent1("evaluation", payload.get("context", {}))
        flags = agent.get_stage_summary("evaluation")["flags"]
    else:
        raise HTTPException(status_code=400, detail="Unknown compliance stage. Use data, feature, training, or evaluation.")
    return {
        "stage": stage,
        "flags": flags,
        "report": agent.get_full_report(),
    }


@app.post("/validation/tier")
async def validation_tier(request: TierRequest) -> Dict[str, Any]:
    agent = _load_agent2()
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent2 is unavailable. Missing or invalid rules.json?")
    tier = agent.tier_model(request.training_config, request.metrics, fe_summary=request.fe_summary)
    return {"tier": tier, "report": agent.get_full_report()}


@app.post("/validation/replication")
async def validation_replication(
    model_name: str = Form(...),
    target_col: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    seeds: Optional[str] = Form("42,43,44,45,46"),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    cv_folds: int = Form(5),
    mdd_file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Run backend replication checks. Returns {'flags', 'report'} to match existing shapes."""
    df = await _read_dataframe(file=file, csv_text=csv_text)
    # parse seeds
    try:
        seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    except Exception:
        seed_list = [random_seed]

    reported = {}
    if mdd_file is not None:
        try:
            mdd_text = parse_mdd_file(mdd_file)
            reported = extract_metrics_from_mdd(mdd_text)
        except Exception:
            reported = {}

    result = run_replication(
        df=df,
        target_col=target_col,
        model_name=model_name,
        test_size=test_size,
        val_size=val_size,
        random_seed=random_seed,
        cv_folds=cv_folds,
        reported=reported,
        seeds=seed_list,
    )

    checks = []
    try:
        from val_replication_core import evaluate_replication_checks
        checks = evaluate_replication_checks(result, reported, seed_list)
    except Exception:
        checks = []

    # Build flags similar to Agent2: list of failing check ids
    flags = [c["id"] for c in checks if c.get("status") in ("FAIL",)]
    return {"stage": "replication", "flags": flags, "report": {"replication": {"result": result, "checks": checks}}}


@app.post("/validation/agent2")
async def validation_agent2(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    intake_json: Optional[str] = Form(None),
    mdd_file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Run the POC ValidationAgent2 engine and return its structured report.
    If the POC module is not available, returns a minimal fallback.
    """
    df = None
    try:
        df = await _read_dataframe(file=file, csv_text=csv_text)
    except HTTPException:
        df = None

    intake = {}
    if intake_json:
        try:
            intake = json.loads(intake_json)
        except Exception:
            intake = {}

    mdd_text = ""
    if mdd_file is not None:
        try:
            mdd_text = parse_mdd_file(mdd_file)
        except Exception:
            mdd_text = ""

    report = run_validation_agent2(df, intake, mdd_text)
    # map to existing shape: flags + report
    flags = []
    try:
        flags = [f.get("check_id") for f in report.get("all_findings", []) if f.get("status") == "FAIL"]
    except Exception:
        flags = []
    return {"stage": "agent2", "flags": flags, "report": report}


@app.post("/ecl/compute")
async def compute_ecl(
    model_artifact: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: Optional[str] = Form(None),
    ead_col: Optional[str] = Form(None),
    loan_type_col: Optional[str] = Form(None),
    lgd_map: Optional[str] = Form(None),
    cfg: str = Form(None),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    pipeline = _from_base64(model_artifact)
    if target_col is not None and target_col in df.columns:
        X = df.drop(columns=[target_col], errors='ignore')
    else:
        X = df
    config_data = json.loads(cfg) if cfg else {}
    ecl_cfg = ecl.ECLConfig(**config_data)
    lgd_map_data = json.loads(lgd_map) if lgd_map else None
    result_df, summary = ecl.compute(
        pipeline=pipeline,
        X=X,
        data=df,
        ead_col=ead_col,
        cfg=ecl_cfg,
        loan_type_col=loan_type_col,
        lgd_map=lgd_map_data,
    )
    return {
        "summary": summary,
        "sample_rows": result_df.head(20).replace({pd.NA: None}).to_dict(orient="records"),
        "columns": result_df.columns.astype(str).tolist(),
    }
