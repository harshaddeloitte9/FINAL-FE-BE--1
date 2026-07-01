"""
main.py - FastAPI backend for the Credit Risk ML POC

Exposes the existing pipeline logic as REST endpoints while preserving
business logic from the original Streamlit app.
"""

import base64
import io
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple, Union

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import joblib

from agent2 import Agent2
from build_rules import RULES_PATH

from utils import (
    generate_synthetic_credit_dataset, detect_column_types,
    detect_target_candidates, detect_task_type, df_to_csv_download, model_to_download,
)
from preprocessing import (
    build_preprocessing_report, prepare_data, rebuild_preprocessor_for, finalize_xy,
)
from feature_engineering import (
    analyze_for_feature_engineering, apply_feature_engineering,
    compute_univariate_gini, resolve_ead_configuration,
)
from model_selector import recommend_models, get_model_instance, get_hyperparameter_grid
from train import split_data, compute_split_stats, train_model
import ecl_engine as ecl
from evaluate import (
    compute_binary_metrics, compute_regression_metrics,
    compute_heteroscedasticity_check, compute_roc_curve, compute_pr_curve,
    compute_threshold_analysis, compute_score_distribution, compute_gain_chart,
)
from explainability import (
    extract_feature_importance, compute_shap_values, generate_prediction_reasoning,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8081",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def _build_data_profile(
    df: pd.DataFrame,
    target_col: Optional[str] = None,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    col_types = detect_column_types(df)
    target_candidates = detect_target_candidates(df)
    task_type = None
    if target_col is not None:
        if target_col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
        task_type = detect_task_type(df[target_col])

    leakage_risk_cols: List[str] = []
    if target_col is not None and task_type == "binary":
        target_numeric = pd.to_numeric(df[target_col], errors="coerce")
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
    numeric_feature_count = len(col_types.get("numeric", []))
    categorical_feature_count = len(col_types.get("categorical", []))

    class_distribution: Optional[Dict[str, int]] = None
    if target_col is not None and target_col in df.columns:
        class_distribution = {
            str(k): int(v)
            for k, v in df[target_col].value_counts(dropna=False).to_dict().items()
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

    profile = {
        "shape": list(df.shape),
        "columns": df.columns.astype(str).tolist(),
        "col_types": col_types,
        "target_candidates": target_candidates,
        "task_type": task_type,
        "dataset_name": dataset_name,
        "leakage_risk_cols": leakage_risk_cols,
        "date_integrity": date_integrity,
        "missing_cells": missing_cells,
        "missing_percentage": missing_percentage,
        "missing_by_column": missing_by_column,
        "duplicate_rows": duplicate_rows,
        "numeric_feature_count": numeric_feature_count,
        "categorical_feature_count": categorical_feature_count,
        "class_distribution": class_distribution,
        "correlation_matrix": correlation_matrix,
        "summary_stats": summary_stats,
        "column_type_table": column_type_table,
        "distribution_histograms": distribution_histograms,
        "data_dictionary": data_dictionary,
        "data_preview": _serialize_dataframe(df, max_rows=10)["preview"],
    }

    if target_col is not None:
        agent = _load_agent2()
        if agent is not None:
            try:
                agent.check_data(df, col_types, leakage_risk_cols=leakage_risk_cols)
                agent.check_rules_from_agent1("data", {
                    "n_rows": len(df),
                    "n_cols": len(df.columns),
                    "missing_pct": round(float(df.isna().mean().mean()), 4),
                    "target_col": target_col,
                })
                profile["agent2_flags_data"] = agent.get_stage_summary("data")["flags"]
                profile["agent2_report"] = agent.get_full_report()
            except Exception:
                profile["agent2_error"] = "Agent2 data check failed"

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
    dataset_name = file.filename if file is not None else None
    return _build_data_profile(df, dataset_name=dataset_name)


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


@app.post("/data/preprocess")
async def preprocess_data(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    task_type = detect_task_type(df[target_col])
    X, y, clean_info = finalize_xy(df, col_types, target_col)
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=0.15, val_size=0.15,
        task_type=task_type, random_state=42,
    )
    prep_report = build_preprocessing_report(X_train.assign(**{target_col: y_train}), col_types, target_col)
    preprocessor = rebuild_preprocessor_for(X_train, col_types, target_col, prep_report)
    feature_names = list(X_train.columns)
    split_stats = compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test)
    return {
        "col_types": col_types,
        "target_col": target_col,
        "feature_names": feature_names,
        "x_shape": list(X_train.shape),
        "y_shape": list(y_train.shape),
        "feature_count": X_train.shape[1],
        "duplicates_removed": clean_info.get("duplicates_removed", 0),
        "numeric_feature_count": len(prep_report.get("numeric", {})),
        "categorical_feature_count": len(prep_report.get("categorical", {})),
        "split_stats": split_stats,
        "x_preview": _serialize_dataframe(X_train, max_rows=5)["preview"],
        "y_preview": y_train.head(5).replace({pd.NA: None}).tolist(),
        "preprocessing_report": prep_report,
        "preprocessor_artifact": _to_base64(preprocessor),
    }


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
    return {
        "col_types": col_types,
        "target_col": target_col,
        "task_type": task_type,
        "feature_engineering_plan": plan,
        "feature_engineering_summary": fe_summary,
        "x_engineered_shape": list(X_engineered.shape),
        "x_engineered_preview": _serialize_dataframe(X_engineered, max_rows=5)["preview"],
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
            class_imbalance_ratio = float(vc.max() / vc.min()) if vc.min() > 0 else 1.0
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
    prep_report = build_preprocessing_report(X_train.assign(**{target_col: y_train}), col_types, target_col)
    fe_summary = None
    if use_feature_engineering:
        plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
        X_train, fe_summary = apply_feature_engineering(X_train, plan)
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
    )
    split_stats = compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test)
    return {
        "task_type": task_type,
        "model_name": model_name,
        "real_feature_names": real_feature_names,
        "training_info": training_info,
        "split_stats": split_stats,
        "feature_engineering_summary": fe_summary,
        "model_artifact": _to_base64(pipeline),
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
