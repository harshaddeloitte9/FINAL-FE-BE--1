"""
main.py - FastAPI backend for the Credit Risk ML POC

Thin REST wrapper that exposes the latest pipeline logic from the
Credit-Risk-Poc-main source-of-truth project.
"""

import base64
import hashlib
import io
import json
import os
import tempfile
import random
import re
import urllib.request
import urllib.error
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List, Tuple, Union

BACKEND_DIR = Path(__file__).resolve().parent
SOURCE_OF_TRUTH_DIR = BACKEND_DIR


def set_test_storage_root(root: Path):
    """Point the backend and intake-draft storage at the pytest temp root."""
    global BACKEND_DIR, INTAKE_DRAFTS_DIR
    root = Path(root)
    BACKEND_DIR = root
    INTAKE_DRAFTS_DIR = root / "intake_drafts"
    INTAKE_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["AEGIS_TEST_STORAGE_ROOT"] = str(root)


def _assert_write_allowed(path: Optional[Path | str] = None):
    """Reject writes to the real backend tree while pytest is active."""
    if os.environ.get("AEGIS_TEST_STORAGE_ROOT") is None:
        return
    target = Path(path) if path is not None else INTAKE_DRAFTS_DIR
    resolved = target.resolve(strict=False)
    real_root = Path(__file__).resolve().parent
    if resolved == real_root / "app_data" or (real_root / "app_data") in resolved.parents:
        raise RuntimeError(f"pytest attempted to write to the real app_data directory: {resolved}")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix

try:
    from openpyxl import Workbook
except Exception:  # pragma: no cover - environment fallback
    Workbook = None
import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix

from agent2 import Agent2
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


def _parse_json_field(raw: Optional[str], default):
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in request: {exc}")


def _resolve_treatment_map(raw_treatment_map: Any) -> Dict[str, str]:
    if not isinstance(raw_treatment_map, dict):
        return {}
    resolved: Dict[str, str] = {}
    for column, value in raw_treatment_map.items():
        if isinstance(value, dict):
            treatment = value.get("treatment") or value.get("resolved_treatment")
        else:
            treatment = value
        if treatment:
            resolved[str(column)] = str(treatment)
    return resolved


def _coalesce_contract_value(payload: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None

from feature_engineering import (
    analyze_for_feature_engineering, apply_feature_engineering,
    compute_univariate_gini, resolve_ead_configuration,
)
from model_selector import (
    recommend_model, compute_dataset_characteristics, characteristics_from_summary,
    get_model_instance, get_hyperparameter_grid, CLASSIFICATION_MODELS,
)
from train_new import (
    SPLIT_STRATEGIES,
    SPLIT_STRATEGY_STRATIFIED,
    SPLIT_STRATEGY_TEMPORAL,
    compute_split_stats,
    split_data,
    train_model,
)
import evaluate_new as eval_engine
import fred_client
import data_integration as di
import persistence
import business_rules
import model_lineage

compute_binary_metrics = eval_engine.compute_binary_metrics
select_operating_threshold = eval_engine.select_operating_threshold
compute_regression_metrics = eval_engine.compute_regression_metrics
compute_heteroscedasticity_check = eval_engine.compute_heteroscedasticity_check
compute_roc_curve = eval_engine.compute_roc_curve
compute_pr_curve = eval_engine.compute_pr_curve
compute_threshold_analysis = eval_engine.compute_threshold_analysis
compute_score_distribution = eval_engine.compute_score_distribution
compute_gain_chart = eval_engine.compute_gain_chart
compute_lift_chart = eval_engine.compute_lift_chart
compute_temporal_analysis_bundle = eval_engine.compute_temporal_analysis_bundle
compute_temporal_stability_summary = eval_engine.compute_temporal_stability_summary
plot_roc_curve = eval_engine.plot_roc_curve
plot_pr_curve = eval_engine.plot_pr_curve
plot_confusion_matrix = eval_engine.plot_confusion_matrix
plot_threshold_analysis = eval_engine.plot_threshold_analysis
plot_score_distribution = eval_engine.plot_score_distribution
plot_lift_chart = eval_engine.plot_lift_chart
from explainability import (
    extract_feature_importance, generate_prediction_reasoning,
    compute_shap_values_with_reason, feature_importance_with_reason,
    generate_model_summary,
)
from val_replication_core import (
    extract_metrics_from_mdd, parse_mdd_file, run_replication, evaluate_replication_checks,
    run_bias_check, detect_protected_columns, _gini, _ks, PROTECTED_KEYWORDS, bias_from_predictions,
)
from validation_stress_core import apply_manual_shock_through, run_stress_suite, run_manual_shock

from validation_agent2 import ValidationAgent2
_validation_agent2_path = BACKEND_DIR / "validation_agent2.py"
# ValidationAgent2.check_regulatory_compliance() (SOURCE_OF_TRUTH_DIR's
# validation_agent2.py) inlines these keyword lists as literal _mdd_contains()
# args rather than module constants — mirrored here verbatim (lines ~1442,
# ~1462 of that file) so Stage 8's findings compilation checks the MDD with
# the exact same keyword sets Stage 7's 7.1/7.2 checks use.
CALIBRATION_KEYWORDS = ["calibrat", "platt", "isotonic", "through the cycle", "ttc"]
STAGING_KEYWORDS = ["stage 1", "stage 2", "stage 3", "staging", "sicr", "lifetime ecl"]  # mirrors 7.2 ("12 month" removed in Phase 5)

# Source-of-truth Agent2: the RAG rule-matching agent (rag_store/val_mdd_rules.json,
# check_for_validation / check_mdd_keywords / check_documents_with_llm). This is a
# different class from the local `Agent2` above (24-06/agent2.py, rag_store/rules.json)
# which only handles Stage 1/2/4/5 compliance flags and has no RAG rule methods.
from source_agent2 import Agent2 as SourceAgent2, _rule_matches_frameworks


app = FastAPI()


def resolve_replication_model_inputs(model_name: Optional[str], algorithm: Optional[str]) -> Tuple[str, str]:
    """Separate the business model identity from the estimator used for training.

    Demo intake pages intentionally send human-readable placeholder algorithm
    labels such as "Demo workflow (illustrative)"; those are not estimator names
    the backend validates against. Map the known demo aliases back to the real
    model family used by the demo dataset while keeping the business model name
    intact and leaving non-demo models unchanged.
    """
    business_model_name = (model_name or "").strip()
    estimator_name = (algorithm or business_model_name or "").strip()
    if not estimator_name:
        raise ValueError("Model or algorithm is required.")

    normalized_name = business_model_name.lower()
    demo_aliases = {
        "Demo workflow (illustrative)": {
            "demo a — demonstration dataset": "LightGBM",
            "demo b — demonstration dataset": "XGBoost",
            "demo a — taiwan benchmark": "LightGBM",
        },
        "LightGBM workflow (illustrative)": "LightGBM",
        "XGBoost workflow (illustrative)": "XGBoost",
        "Logistic Regression workflow (illustrative)": "Logistic Regression",
        "Random Forest workflow (illustrative)": "Random Forest",
        "Gradient Boosting workflow (illustrative)": "Gradient Boosting",
    }
    if estimator_name in demo_aliases:
        alias_target = demo_aliases[estimator_name]
        if isinstance(alias_target, dict):
            for key, value in alias_target.items():
                if key in normalized_name:
                    estimator_name = value
                    break
            else:
                estimator_name = next(iter(alias_target.values()))
        else:
            estimator_name = alias_target

    # Original Demo A and the Taiwan benchmark are LightGBM-based demo
    # presets; stale XGBoost defaults or older placeholder text must not
    # override the audited business model identity.
    if normalized_name.startswith("demo a"):
        estimator_name = "LightGBM"
    elif normalized_name.startswith("demo b"):
        estimator_name = "XGBoost"
    elif "taiwan" in normalized_name and "workflow" in estimator_name.lower():
        estimator_name = "LightGBM"

    return business_model_name, estimator_name


# ── Reference (developer-reported) vs actual (computed) metrics ─────────────
# Reference metrics are what the developer claims (MDD, development training
# run, or values a reviewer typed in). They are only ever compared against —
# they must never replace metrics computed from model predictions. Every
# reference value carries the source it came from so a saved run can show
# exactly what each comparison was made against.
METRIC_PROVENANCE_SCHEMA_VERSION = 2
REFERENCE_SOURCE_LABELS = {
    "mdd_upload": "MDD uploaded with this run",
    "intake_mdd": "MDD parsed at Intake",
    "demo_intake": "Demo intake snapshot",
    "development_training_run": "Development training run (evaluation metrics)",
    "manual_entry": "Entered manually by reviewer",
    "client_supplied": "Supplied by client (source not stated)",
}
_CLIENT_REFERENCE_SOURCES = {"intake_mdd", "demo_intake", "development_training_run", "manual_entry"}
# Who established a reference value's source (D2). Only values the server
# itself extracted from a document uploaded with the run are server-verified;
# every source label sent by the browser is recorded as browser-reported.
REFERENCE_VERIFIED_SERVER = "server_extracted"
REFERENCE_BROWSER_REPORTED = "browser_reported"
REFERENCE_VERIFICATION_LABELS = {
    REFERENCE_VERIFIED_SERVER: "verified: extracted by the server from the document uploaded with this run",
    REFERENCE_BROWSER_REPORTED: "browser-reported: source label supplied by the client, not verified by the server",
}


def build_reference_metrics(
    reported_json: Optional[str],
    reported_sources_json: Optional[str] = None,
    mdd_metrics: Optional[Dict[str, Any]] = None,
    mdd_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge client-supplied and MDD-extracted reference metrics, keeping a
    per-key source. MDD values win per key (the MDD is the developer's
    authoritative document). Unparseable input is reported in `warnings`
    instead of being silently dropped.

    D2: `verification[key]` says who established the source — the server
    (values it extracted from the MDD uploaded with this run) or the browser
    (any client-supplied label, which is recorded but never presented as
    verified).
    D3: when an uploaded MDD value replaces a DIFFERENT client value, the
    replacement is listed in `replacements` (metric, previous value and
    source, new value) and stated in `warnings`; nothing is replaced
    silently."""
    values: Dict[str, float] = {}
    sources: Dict[str, str] = {}
    warnings: List[str] = []
    replacements: List[Dict[str, Any]] = []

    client_sources: Dict[str, Any] = {}
    if reported_sources_json:
        try:
            parsed_sources = json.loads(reported_sources_json)
            if isinstance(parsed_sources, dict):
                client_sources = parsed_sources
            else:
                warnings.append("reported_sources_json was not an object and was ignored.")
        except Exception as exc:
            warnings.append(f"reported_sources_json could not be parsed and was ignored: {exc}")

    def _add(key: str, raw: Any, source: str) -> None:
        if raw is None:
            return
        try:
            num = float(raw)
        except (TypeError, ValueError):
            warnings.append(f"Reference metric '{key}' is not numeric ({raw!r}) and was ignored.")
            return
        if not np.isfinite(num):
            warnings.append(f"Reference metric '{key}' is not finite and was ignored.")
            return
        values[key] = num
        sources[key] = source

    if reported_json:
        try:
            parsed = json.loads(reported_json)
        except Exception as exc:
            parsed = None
            warnings.append(f"reported_json could not be parsed and was ignored: {exc}")
        if isinstance(parsed, dict):
            for key, raw in parsed.items():
                claimed = client_sources.get(key)
                source = claimed if claimed in _CLIENT_REFERENCE_SOURCES else "client_supplied"
                _add(str(key), raw, source)
        elif parsed is not None:
            warnings.append("reported_json was not an object and was ignored.")

    for key, raw in (mdd_metrics or {}).items():
        key = str(key)
        previous = (values.get(key), sources.get(key)) if key in values else None
        _add(key, raw, "mdd_upload")
        if previous is not None and sources.get(key) == "mdd_upload" and previous[1] != "mdd_upload" \
                and abs(values[key] - previous[0]) > 1e-12:
            replacements.append({
                "metric": key,
                "previous_value": previous[0],
                "previous_source": previous[1],
                "previous_source_label": REFERENCE_SOURCE_LABELS.get(previous[1], previous[1]),
                "new_value": values[key],
                "new_source": "mdd_upload",
            })
    if replacements:
        warnings.append("The MDD uploaded with this run replaced reviewer-supplied reference values: " + "; ".join(
            f"{r['metric']} {r['previous_value']:g} ({r['previous_source_label']}) → {r['new_value']:g}"
            for r in replacements) + ".")

    if mdd_error:
        warnings.append(f"MDD could not be read; no metrics were taken from it: {mdd_error}")

    verification = {k: (REFERENCE_VERIFIED_SERVER if v == "mdd_upload" else REFERENCE_BROWSER_REPORTED)
                    for k, v in sources.items()}
    return {
        "values": values,
        "sources": sources,
        "source_labels": {k: REFERENCE_SOURCE_LABELS.get(v, v) for k, v in sources.items()},
        "verification": verification,
        "verification_labels": {k: REFERENCE_VERIFICATION_LABELS[v] for k, v in verification.items()},
        "replacements": replacements,
        "warnings": warnings,
    }


def _canonical_fingerprint_value(value: Any) -> str:
    """Deterministic, type-aware string for a scalar used in the dataset hash.

    The value is serialized without aggressive rounding so materially different
    floats remain distinct while CSV round-trips remain stable. Missing values
    are normalized to a single sentinel and integer/float semantics are kept
    distinct for the identity contract.
    """
    if value is None:
        return "n:null"
    if isinstance(value, (pd._libs.missing.NAType, type(pd.NaT))):
        return "n:null"
    if pd.isna(value):
        return "n:null"
    if isinstance(value, (bool, np.bool_)):
        return f"b:{int(bool(value))}"
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return f"i:{int(value)}"
    if isinstance(value, (float, np.floating)):
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return "n:null"
        if f == 0.0:
            return "f:0"
        return f"f:{format(f, '.17g')}"
    if isinstance(value, str):
        return f"s:{value}"
    return f"o:{str(value)}"


def dataset_fingerprint(df: pd.DataFrame) -> str:
    """SHA-256 of the dataset's logical identity.

    Use one CSV round-trip with pandas' round-trip float parsing so the same
    logical dataset hashes identically whether it started as an in-memory
    DataFrame or a CSV-parsed DataFrame, without arbitrary decimal rounding.
    This keeps the contract sensitive to genuine value changes while matching
    the API's real CSV parse boundary. The original uploaded file bytes remain
    tracked separately by source_fingerprint().
    """
    if df is None:
        return hashlib.sha256(b"").hexdigest()

    # Normalize to the exact CSV representation the backend consumes, but parse
    # floats with round-trip precision so we do not destroy tiny but meaningful
    # differences. Doing this once avoids the large temporary allocations from
    # repeated round-trips while remaining faithful to the identity contract.
    canonical = df.reset_index(drop=True).copy()
    canonical = pd.read_csv(
        io.StringIO(canonical.to_csv(index=False)),
        keep_default_na=True,
        float_precision="round_trip",
    ).reset_index(drop=True)

    payload = ["\x1f".join(str(c) for c in canonical.columns)]
    for row in canonical.itertuples(index=False, name=None):
        payload.append("\x1f".join(_canonical_fingerprint_value(v) for v in row))
    return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()


def source_fingerprint(file: Optional[UploadFile] = None, csv_text: Optional[str] = None) -> Optional[str]:
    """SHA-256 of the dataset exactly as received (original file bytes, or
    the UTF-8 csv_text), as opposed to dataset_fingerprint, which identifies
    the parsed table. Two different files can parse to the same table (line
    endings, quoting); this records which file was actually supplied."""
    if csv_text:
        return hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    if file is not None:
        try:
            file.file.seek(0)
            digest = hashlib.sha256(file.file.read()).hexdigest()
            file.file.seek(0)
            return digest
        except Exception:
            return None
    return None


def dataset_identity(df: pd.DataFrame, file: Optional[UploadFile] = None, csv_text: Optional[str] = None) -> Dict[str, Any]:
    """Both dataset identities, recorded with every development-stage run."""
    return {
        "dataset_sha256": dataset_fingerprint(df),
        "dataset_file_sha256": source_fingerprint(file, csv_text),
        "dataset_source": "csv_text" if csv_text else ("file" if file is not None else "synthetic"),
        "dataset_shape": [int(df.shape[0]), int(df.shape[1])],
    }


def registered_run_identity(registered_model_id: Optional[str], df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Identity recorded with every validation-stage run so history lookups
    can match it to the registered model, its CURRENT training, and the exact
    data used. Unknown/absent model IDs are recorded as given with no
    training run (such runs are never treated as current for that model)."""
    model_id = (registered_model_id or "").strip() or None
    training_run_id = None
    if model_id:
        entry = next(
            (m for m in persistence.load_model_inventory().get("development", [])
             if isinstance(m, dict) and str(m.get("model_id") or "").strip() == model_id),
            None,
        )
        training_run_id = ((entry or {}).get("lineage_contract") or {}).get("training_run_id")
    return {
        "registered_model_id": model_id,
        "training_run_id": training_run_id,
        "dataset_sha256": dataset_fingerprint(df) if df is not None else None,
    }


def _registered_evaluation_or_http(df: pd.DataFrame, registered_model_id: str,
                                   expected_training_run_id: Optional[str] = None,
                                   compute_sensitivity: bool = False) -> Dict[str, Any]:
    """The registered model scored from its verified bundle on its recorded
    split (model_lineage.registered_evaluation), or an HTTP error. Never
    falls back to a refit."""
    try:
        return model_lineage.registered_evaluation(
            df, registered_model_id, dataset_sha256=dataset_fingerprint(df),
            expected_training_run_id=(expected_training_run_id or "").strip() or None,
            compute_sensitivity=compute_sensitivity,
        )
    except model_lineage.ArtifactVerificationError as exc:
        raise HTTPException(status_code=exc.http_status,
                            detail=f"Registered model cannot be evaluated ({exc.status}): {' '.join(exc.reasons)}")


def registered_shockable_features(ctx: Dict[str, Any]) -> List[str]:
    """Raw input features of a registered model that a manual shock may
    change: numeric columns the model was trained on (recorded
    raw_feature_columns) that its preprocessing did not drop. Derived
    (feature-engineered) columns are excluded: they move when their source
    feature is shocked through the scoring chain."""
    contract = ctx.get("contract") or {}
    X_raw = ctx.get("X_test_raw")
    if X_raw is None:
        return []
    dropped = set((contract.get("preprocessing") or {}).get("drop_cols") or [])
    return [c for c in (contract.get("features") or {}).get("raw_feature_columns") or []
            if c not in dropped and c in X_raw.columns and pd.api.types.is_numeric_dtype(X_raw[c])]


def independent_refit_identity(df: pd.DataFrame, algorithm: str) -> Dict[str, Any]:
    """Evidence identity of a run that fitted a NEW model from an algorithm
    name. It is never attributed to a registered model, so it cannot satisfy
    registered-model evidence requirements."""
    return {
        "evaluation_mode": model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT,
        "registered_model_id": None,
        "training_run_id": None,
        "dataset_sha256": dataset_fingerprint(df),
        "refit_algorithm": algorithm,
    }


def attest_inventory_registration(intake: Optional[Dict[str, Any]], registered_model_id: Optional[str] = None) -> Dict[str, Any]:
    """Server-side registration status: registered only if the exact
    registered model ID (explicit argument, else intake's
    registered_model_id) is in the Development Inventory. The client's
    model_inventory_registered boolean is never used; names are never
    matched. Read-only — loads the inventory and writes nothing."""
    intake = intake if isinstance(intake, dict) else {}
    claimed = intake.get("model_inventory_registered")
    model_id = str(registered_model_id or intake.get("registered_model_id") or "").strip() or None
    entry = None
    if model_id:
        entry = next((m for m in persistence.load_model_inventory().get("development", [])
                      if isinstance(m, dict) and str(m.get("model_id") or "").strip() == model_id), None)
    verified = entry is not None
    if not model_id:
        detail = "No registered model ID was supplied, so registration in the Model Inventory is not confirmed."
    elif not verified:
        detail = (f"Registered model ID '{model_id}' was not found in the Development Inventory (unknown, deleted or "
                  "unavailable), so registration is not confirmed.")
    else:
        detail = f"Registered model {model_id} ({entry.get('model_name') or 'unnamed'}) is in the Development Inventory."
    return {
        "source": "development_inventory",
        "registered_model_id": model_id,
        "verified": verified,
        "model_name": entry.get("model_name") if verified else None,
        "detail": detail,
        "client_claim": claimed if isinstance(claimed, bool) else None,
        "client_claim_ignored": isinstance(claimed, bool) and claimed != verified,
    }


def with_attested_registration(intake: Optional[Dict[str, Any]], registered_model_id: Optional[str] = None) -> Dict[str, Any]:
    """Copy of intake whose registration fields are the server's own: any
    client-supplied model_inventory_registered or registration_attestation
    is replaced."""
    out = dict(intake) if isinstance(intake, dict) else {}
    attestation = attest_inventory_registration(out, registered_model_id)
    out["registered_model_id"] = attestation["registered_model_id"]
    out["model_inventory_registered"] = attestation["verified"]
    out["registration_attestation"] = attestation
    return out


def _demo_dataset_fingerprints() -> Dict[str, str]:
    """Exact fingerprints of the shipped demo portfolios. Server-only.
    Browser flags or dataset names are never consulted."""
    out: Dict[str, str] = {}
    for mode in ("clean", "taiwan", "flawed"):
        demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / ("taiwan_portfolio.csv" if mode == "taiwan" else f"{mode}_portfolio.csv")
        if demo_file.exists():
            try:
                out[mode] = dataset_fingerprint(pd.read_csv(demo_file, keep_default_na=True, float_precision="round_trip"))
            except Exception:
                continue
    return out


def _server_demo_dataset_flag(dataset_sha256: Optional[str] = None, df: Optional[pd.DataFrame] = None) -> bool:
    """True only when the exact shipped demo dataset fingerprint matches."""
    if dataset_sha256:
        return _is_demo_dataset_fingerprint(dataset_sha256)
    if df is not None:
        return _is_demo_dataset_fingerprint(dataset_fingerprint(df))
    return False


def with_attested_independence(intake: Optional[Dict[str, Any]], registered_model_id: Optional[str] = None) -> Dict[str, Any]:
    """Server-side independence status only: browser flags are removed and the
    logged attestation is used if present, otherwise the field is forced false."""
    out = dict(intake) if isinstance(intake, dict) else {}
    attestation = out.get("independence_attestation") if isinstance(out.get("independence_attestation"), dict) else {}
    independence = bool(attestation.get("independent") is True)
    out["independence_confirmed"] = False
    out["independence_attestation"] = {
        **attestation,
        "source": "server_recorded",
        "verified": bool(attestation),
        "independent": independence,
        "detail": attestation.get("detail") if attestation else "No recorded independence attestation found for this model and current training.",
        "identity_status": "unauthenticated/self-declared",
    }
    return out


def build_metric_provenance(reference: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": METRIC_PROVENANCE_SCHEMA_VERSION,
        "metrics": "computed_from_model_predictions",
        "reference_metrics": "developer_reported" if reference.get("values") else "none_supplied",
        "reference_overrides_computed": False,
        # D2: which reference values the server verified (extracted from the
        # uploaded MDD) and which carry browser-reported source labels only.
        "reference_source_verification": {
            "server_verified": sorted(k for k, v in (reference.get("verification") or {}).items() if v == REFERENCE_VERIFIED_SERVER),
            "browser_reported": sorted(k for k, v in (reference.get("verification") or {}).items() if v == REFERENCE_BROWSER_REPORTED),
        },
    }


_ALLOWED_ORIGINS = [
    "http://192.168.1.19:3000",
    "http://192.168.1.19:5173",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8081",
    "http://localhost:3001",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:3001",

]

_ALLOWED_ORIGIN_REGEX = re.compile(
    r"^https?://(localhost|127\.0\.0\.1|192\.168\.1\.19)(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=_ALLOWED_ORIGIN_REGEX.pattern,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn unhandled exceptions into a normal JSON response with CORS headers,
    instead of letting them fall through to Starlette's default 500 handling.

    Handlers registered for the bare `Exception` class run inside Starlette's
    ServerErrorMiddleware (see Starlette's own docs on this) — which sits
    OUTSIDE CORSMiddleware in the stack no matter what handler is registered
    here, so CORSMiddleware never gets a chance to add
    Access-Control-Allow-Origin to this response. Confirmed by testing: the
    plain-JSONResponse version of this handler (no manual headers) still came
    back with no CORS header on a genuine crash. The browser then reports
    "Failed to fetch"/a CORS error for what's actually a server-side 500,
    indistinguishable from a real network failure. Fix is to set the header
    ourselves, directly on the response this handler returns.
    """
    response = JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )
    origin = request.headers.get("origin")
    if origin and (origin in _ALLOWED_ORIGINS or _ALLOWED_ORIGIN_REGEX.match(origin)):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


def run_validation_agent2(val_df: Optional[pd.DataFrame], intake_json: dict, mdd_text: str = "") -> dict:
    agent = ValidationAgent2()
    # If no dataframe was provided (or it's empty), pass None so the
    # ValidationAgent2 checks that expect `None` will short-circuit safely.
    df_arg = val_df if (val_df is not None and getattr(val_df, "empty", False) is False) else None
    # Registration and independence are both attested by the server; any
    # browser-supplied boolean flags are stripped before the checks run.
    processed = with_attested_registration(with_attested_independence(intake_json or {}))
    return agent.run_all_checks(df_arg, processed, mdd_text or "")


def _detect_temporal_date_columns(df: pd.DataFrame) -> List[str]:
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if date_cols:
        return date_cols
    for c in df.select_dtypes(include="object").columns:
        try:
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() > 0.8:
                date_cols.append(c)
        except Exception:
            continue
    return date_cols


def _build_temporal_analysis(df: pd.DataFrame, y_true: np.ndarray, y_proba: np.ndarray) -> Dict[str, Any]:
    date_columns = _detect_temporal_date_columns(df)
    if not date_columns:
        return {
            "date_columns": [],
            "default_date_column": None,
            "default_frequency": "Quarterly",
            "frequency_options": ["Monthly", "Quarterly", "Half-Yearly", "Yearly"],
            "summary": None,
            "plot_data": [],
        }

    default_date_column = date_columns[0]
    frequency_options = ["Monthly", "Quarterly", "Half-Yearly", "Yearly"]
    freq_map = {
        "Monthly": "ME",
        "Quarterly": "QE",
        "Half-Yearly": "6ME",
        "Yearly": "YE",
    }
    plot_data_by_freq: Dict[str, Any] = {}
    summaries: Dict[str, Any] = {}
    for freq_name in frequency_options:
        freq_key = freq_map[freq_name]
        dates = df[default_date_column]
        summary = compute_temporal_stability_summary(dates, y_true, y_proba, freq=freq_key)
        plot_data = []
        for row in summary.get("by_period", []):
            plot_data.append({
                "period": row["period"],
                "actual_rate": row["actual_rate"],
                "predicted_rate": row["predicted_rate"],
                "gap": row["gap"],
                "flagged": row["flagged"],
            })
        plot_data_by_freq[freq_name] = plot_data
        summaries[freq_name] = summary
    return {
        "date_columns": date_columns,
        "default_date_column": default_date_column,
        "default_frequency": "Quarterly",
        "frequency_options": frequency_options,
        "summary": summaries.get("Quarterly"),
        "plot_data": plot_data_by_freq.get("Quarterly", []),
        "plot_data_by_freq": plot_data_by_freq,
        "summaries_by_freq": summaries,
    }


def _normalize_demo_mode(mode: Optional[str]) -> str:
    if mode is None:
        return "clean"
    value = str(mode).strip().lower().replace("-", "_")
    aliases = {
        "clean": "clean",
        "gold": "clean",
        "gold_standard": "clean",
        "demo_a": "clean",
        "demo": "clean",
        "original_demo": "clean",
        "taiwan": "taiwan",
        "taiwan_benchmark": "taiwan",
        "flawed": "flawed",
        "demo_b": "flawed",
    }
    return aliases.get(value, "clean")


def _demo_dataset_summary(mode: str = "clean") -> Dict[str, Any]:
    demo_mode = _normalize_demo_mode(mode)
    if demo_mode == "flawed":
        demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_portfolio.csv"
    elif demo_mode == "taiwan":
        demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "taiwan_portfolio.csv"
    else:
        demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_portfolio.csv"
    if not demo_file.exists():
        return {"mode": demo_mode, "rows": 0, "default_rate": 0.0, "default_col": "default", "dataset_sha256": None}
    df = pd.read_csv(demo_file, keep_default_na=True, float_precision="round_trip")
    default_col = next((c for c in df.columns if "default" in str(c).lower()), "default")
    default_rate = float(df[default_col].mean()) if default_col in df.columns else 0.0
    return {
        "mode": demo_mode,
        "rows": int(df.shape[0]),
        "default_rate": default_rate,
        "default_col": default_col,
        "dataset_sha256": dataset_fingerprint(df),
    }


def _is_demo_dataset_fingerprint(dataset_sha256: Optional[str]) -> bool:
    if not dataset_sha256:
        return False
    demo_hashes = {
        _demo_dataset_summary("taiwan").get("dataset_sha256"),
        _demo_dataset_summary("flawed").get("dataset_sha256"),
    }
    legacy_clean = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_portfolio.csv"
    if legacy_clean.exists():
        try:
            demo_hashes.add(dataset_fingerprint(pd.read_csv(legacy_clean, keep_default_na=True, float_precision="round_trip")))
        except Exception:
            pass
    return dataset_sha256 in demo_hashes


def _build_validation_intake_snapshot(mode: str = "clean") -> Dict[str, Any]:
    demo_mode = _normalize_demo_mode(mode)
    demo_stats = _demo_dataset_summary(demo_mode)
    demo_created_at = pd.Timestamp.now().isoformat()
    if demo_mode == "flawed":
        model_data = {
            "model_name": "Demo B — demonstration dataset",
            "model_owner": "Not assigned — demo",
            "owning_team": "Demo profile",
            "lead_validator": "Not assigned — demo",
            "model_type": "PD (Probability of Default)",
            "model_version": "demo",
            "model_tier": "Tier 2 — Medium Risk",
            "model_purpose": "Demonstration dataset only — not a registered development model.",
            "target_col": demo_stats["default_col"],
            "algorithm": "Demo workflow (illustrative)",
            "default_definition": "Demo default flag",
            "calibration_method": "Not applicable for demonstration data",
            "macro_variables_mentioned": False,
            "model_inventory_registered": False,
            "independence_confirmed": False,
        }
        mdd_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_mdd.txt"
        hyperparams_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_params.json"
        demo_label = "Demo B"
    elif demo_mode == "taiwan":
        model_data = {
            "model_name": "Demo A — Taiwan benchmark",
            "model_owner": "Not assigned — demo",
            "owning_team": "Demo profile",
            "lead_validator": "Not assigned — demo",
            "model_type": "PD (Probability of Default)",
            "model_version": "demo",
            "model_tier": "Tier 2 — Medium Risk",
            "model_purpose": "Independent validation benchmark sourced from the UCI Taiwan credit-card default study; not a registered development model.",
            "target_col": demo_stats["default_col"],
            "algorithm": "LightGBM workflow (illustrative)",
            "default_definition": "1 = default payment next month, 0 = non-default",
            "calibration_method": "Not applicable for demonstration data",
            "macro_variables_mentioned": False,
            "model_inventory_registered": False,
            "independence_confirmed": False,
        }
        mdd_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "taiwan_mdd.txt"
        hyperparams_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "taiwan_params.json"
        demo_label = "Demo A — Taiwan Benchmark"
    else:
        model_data = {
            "model_name": "Demo A — demonstration dataset",
            "model_owner": "Not assigned — demo",
            "owning_team": "Demo profile",
            "lead_validator": "Not assigned — demo",
            "model_type": "PD (Probability of Default)",
            "model_version": "demo",
            "model_tier": "Tier 2 — Medium Risk",
            "model_purpose": "Demonstration dataset only — not a registered development model.",
            "target_col": demo_stats["default_col"],
            "algorithm": "Demo workflow (illustrative)",
            "default_definition": "Demo default flag",
            "calibration_method": "Not applicable for demonstration data",
            "macro_variables_mentioned": False,
            "model_inventory_registered": False,
            "independence_confirmed": False,
        }
        mdd_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_mdd.txt"
        hyperparams_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_params.json"
        demo_label = "Demo A"

    # Derive the Risk Tier banner from the same model_tier used above (and
    # edited via the Model Metadata dropdown) so the two never disagree.
    # Cadence wording mirrors Stage 8's monitoring-frequency-by-tier logic
    # (see _build_stage8_findings's "driven by model tier" block) rather than
    # inventing new phrasing.
    tier_value = model_data["model_tier"].split("—")[0].strip()
    if "1" in tier_value or "High" in model_data["model_tier"]:
        tier_description = "High risk — monthly independent validation required."
    elif "2" in tier_value or "Medium" in model_data["model_tier"]:
        tier_description = "Material — quarterly independent validation required."
    else:
        tier_description = "Standard — semi-annual independent validation required."

    try:
        mdd_text = mdd_file.read_text(encoding="utf-8")
    except Exception:
        mdd_text = ""
    try:
        hyperparams = json.loads(hyperparams_file.read_text(encoding="utf-8"))
    except Exception:
        hyperparams = {}

    reported_metrics = {
        "roc_auc": None,
        "gini": None,
        "ks": None,
        "cv_mean_auc": None,
        "accuracy": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "brier_score": None,
    }
    try:
        extracted = extract_metrics_from_mdd(mdd_text)
    except Exception:
        extracted = {}
    for key, value in extracted.items():
        if key in reported_metrics:
            reported_metrics[key] = value

    mdd_document_path = f"demo_data/{demo_mode}_mdd.txt"
    # Demo submissions are demonstration data. They are not development models
    # in the Model Inventory, so: no registered model ID, not registered, and
    # the inventory attestation is left for the reviewer (never pre-ticked).
    # Reads demo files only; never creates or changes inventory entries.
    base_rate_pct = demo_stats["default_rate"] * 100.0
    return {
        "demo_mode": demo_mode,
        "demo_label": demo_label,
        "demo_created_at": demo_created_at,
        "is_demo": True,
        "val_intake_data": {**model_data, "mdd_text": mdd_text, "mdd_document_path": mdd_document_path,
                            "registered_model_id": None, "demo_mode": demo_mode, "is_demo_data": True,
                            "demo_created_at": demo_created_at},
        "val_mdd_text": mdd_text,
        "val_mdd_reported_metrics": reported_metrics,
        "val_hyperparams": hyperparams,
        "chk_inventory": False,
        "chk_tier": False,
        "chk_artifacts": False,
        "chk_prev_findings": False,
        "chk_reg_scope": False,
        "chk_independence": False,
        "chk_plan_approved": False,
        "chk_attestation": False,
        "display": {
            "title": "Stage 1 — Intake & Governance",
            "description": "Capture model metadata, upload all required artifacts, and complete the governance attestation checklist before proceeding to automated validation stages. This demonstration submission is illustrative only and is not a registered Model Inventory model.",
            "modelMetadata": {
                "title": "Model metadata",
                "description": f"{demo_label} demonstration profile — illustrative only; this is not a registered Model Inventory model.",
                "registeredLabel": "Not registered",
                "items": [
                    ["Model name", model_data["model_name"]],
                    ["Owner", "Demo profile"],
                    ["Developer", "Demo profile"],
                    ["Validation date", "Not applicable — demo"],
                    ["Registered model ID", "Not registered"],
                    ["Demo created", demo_created_at],
                    ["Version", model_data["model_version"]],
                    ["Risk tier", model_data["model_tier"]],
                    ["Algorithm", model_data["algorithm"]],
                    ["Sample rows", f"{demo_stats['rows']:,}"],
                    ["Target rate", f"{base_rate_pct:.2f}%"],
                ],
            },
            "targetDefinition": {
                "title": "Target definition",
                "expression": f"{demo_stats['default_col']} ∈ {{0, 1}}",
                "detail": "Demonstration target flag from the shipped demo CSV.",
                "baseRateLabel": "Base rate",
                "baseRate": f"{base_rate_pct:.2f}%",
                "sampleSizeLabel": "Sample size",
                "sampleSize": f"{demo_stats['rows']:,}",
            },
            "riskTier": {
                "title": "Risk tier",
                "value": tier_value,
                "description": tier_description,
            },
            "artifacts": [],
            "artifactSummary": "0 required · 0 optional",
            "artifactTitle": "Artifact inventory",
            "artifactDescription": "No uploaded artifacts for this demo submission.",
            "governance": {
                "title": "Governance attestation",
                "description": "Confirm the model and validation plan are ready to proceed.",
                "status": "Not started",
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



@app.get("/validation/intake")
async def validation_intake(mode: str = "clean") -> Dict[str, Any]:
    return _build_validation_intake_snapshot(mode)


# Intake draft persistence — file-based, keyed by model_name since there's no
# real user/session/auth system in this app yet. Deliberately simple: no
# uniqueness enforcement (two submissions named identically will overwrite
# each other's draft) — an accepted known limitation, not solved here.
INTAKE_DRAFTS_DIR = BACKEND_DIR / "intake_drafts"


def _intake_draft_slug(model_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", model_name.strip()).strip("_")
    if not slug:
        raise HTTPException(status_code=400, detail="model_name is required to save/load a draft.")
    return slug


class IntakeDraftRequest(BaseModel):
    model_name: str
    data: Dict[str, Any]


@app.post("/validation/intake/draft")
async def save_intake_draft(payload: IntakeDraftRequest) -> Dict[str, Any]:
    slug = _intake_draft_slug(payload.model_name)
    path = INTAKE_DRAFTS_DIR / f"{slug}.json"
    _assert_write_allowed(path)
    INTAKE_DRAFTS_DIR.mkdir(exist_ok=True)
    saved_at = pd.Timestamp.now().isoformat()
    record = {"model_name": payload.model_name, "data": payload.data, "saved_at": saved_at}
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    result = {"saved": True, "model_name": payload.model_name, "saved_at": saved_at}

    try:
        persistence.log_event(
            persistence.VALIDATION_PIPELINE_LOG,
            stage="intake",
            payload={"model_name": payload.model_name},
            full_payload={**result, "data": payload.data},
        )
    except Exception as e:
        print(f"[persistence] failed to log intake: {e}")

    return result


@app.get("/validation/intake/draft")
async def get_intake_draft(model_name: str) -> Dict[str, Any]:
    slug = _intake_draft_slug(model_name)
    path = INTAKE_DRAFTS_DIR / f"{slug}.json"
    if not path.exists():
        return {"found": False}
    record = json.loads(path.read_text(encoding="utf-8"))
    return {"found": True, **record}


@app.get("/history/dev")
async def history_dev() -> Dict[str, Any]:
    # Each row is labelled record_status = current | legacy (nothing removed).
    return {"runs": persistence.list_runs(persistence.DEV_PIPELINE_LOG)}


@app.get("/history/validation")
async def history_validation() -> Dict[str, Any]:
    return {"runs": persistence.list_runs(persistence.VALIDATION_PIPELINE_LOG)}


def _validate_history_request(log_file: str, stage: Optional[str] = None) -> None:
    try:
        persistence.validate_history_request(log_file, stage)
    except persistence.HistoryRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/history/artifact")
async def history_artifact(log_file: str, run_id: str) -> Dict[str, Any]:
    _validate_history_request(log_file)
    run = persistence.get_run(log_file, run_id)
    return {
        "artifact": persistence.get_artifact(log_file, run_id),
        "record_status": run.get("record_status") if run else None,
        "record_status_reason": run.get("record_status_reason") if run else None,
    }


def _registered_lineage_validator() -> Callable[[Dict[str, Any]], Optional[str]]:
    """History-row validator for validation-stage runs that name a registered
    model: the run must belong to the model's CURRENT training (a retrained
    model has a new lineage contract, which makes earlier runs stale)."""
    current: Dict[str, Optional[str]] = {}
    loaded = False

    def _check(row: Dict[str, Any]) -> Optional[str]:
        nonlocal loaded
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        model_id = summary.get("registered_model_id")
        if not model_id:
            return None
        if not loaded:
            for entry in persistence.load_model_inventory().get("development", []):
                if isinstance(entry, dict) and entry.get("model_id"):
                    current[str(entry["model_id"])] = (entry.get("lineage_contract") or {}).get("training_run_id")
            loaded = True
        if str(model_id) not in current:
            return f"Registered model {model_id} is no longer in the Model Inventory."
        current_training = current[str(model_id)]
        if current_training is None:
            return f"Registered model {model_id} has no recorded training lineage."
        if summary.get("training_run_id") != current_training:
            return (f"Registered model {model_id} has been retrained since this run "
                    f"(run used training {summary.get('training_run_id') or 'unrecorded'}, current is {current_training}).")
        return None

    return _check


@app.get("/history/latest")
async def history_latest(
    log_file: str,
    stage: str,
    business_model_name: Optional[str] = None,
    dataset_name: Optional[str] = None,
    registered_model_id: Optional[str] = None,
    dataset_sha256: Optional[str] = None,
    replication_run_id: Optional[str] = None,
    include_legacy: Optional[bool] = None,
    dataset_file_sha256: Optional[str] = None,
    training_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Newest VALID run of a stage for the given identity.

    Unknown log files / stage names (including the retired 'benchmarking'
    name) return 400. On the validation log, legacy rows (written before run
    identity was recorded) are skipped unless include_legacy=true, and runs
    for a registered model that has since been retrained are skipped. Every
    passed-over newer row is reported in `excluded` with its reason. The dev
    log keeps its previous behaviour (legacy rows allowed, but labelled).
    """
    _validate_history_request(log_file, stage)
    is_validation_log = log_file == persistence.VALIDATION_PIPELINE_LOG
    if include_legacy is None:
        include_legacy = not is_validation_log
    validator = _registered_lineage_validator() if is_validation_log else None
    if is_validation_log and stage == "findings":
        # A saved verdict issued under an older verdict policy (e.g. before
        # evidence completeness) is never restored as the current verdict.
        lineage_check = validator

        def validator(row: Dict[str, Any]) -> Optional[str]:  # type: ignore[no-redef]
            summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
            try:
                version = int(summary.get("verdict_policy_version") or 0)
            except (TypeError, ValueError):
                version = 0
            if version != VERDICT_POLICY_VERSION:
                return (f"Verdict issued under verdict policy {version or 'unrecorded'}; the current policy is "
                        f"{VERDICT_POLICY_VERSION}, so it must be recomputed.")
            return lineage_check(row)
    return persistence.find_latest_run(
        log_file,
        stage,
        filters={
            "business_model_name": business_model_name,
            "dataset_name": dataset_name,
            "registered_model_id": registered_model_id,
            "dataset_sha256": dataset_sha256,
            "replication_run_id": replication_run_id,
            # Development pages scope their resume to the exact file bytes
            # being worked on and, where relevant, the model's training run (E7).
            "dataset_file_sha256": dataset_file_sha256,
            "training_run_id": training_run_id,
        },
        include_legacy=include_legacy,
        validator=validator,
    )


class InventoryModelRequest(BaseModel):
    model_name: str
    model_type: Optional[str] = None
    business_purpose: Optional[str] = None
    model_owner: Optional[str] = None
    business_unit: Optional[str] = None
    model_version: Optional[str] = None
    regulatory_framework: Optional[str] = None
    status: Optional[str] = None
    development_date: Optional[str] = None
    implementation_date: Optional[str] = None
    last_validation_date: Optional[str] = None
    next_validation_due: Optional[str] = None
    model_risk_rating: Optional[str] = None
    approval_status: Optional[str] = None
    reviewer: Optional[str] = None
    documentation_url: Optional[str] = None
    documentation_path: Optional[str] = None
    document_url: Optional[str] = None
    document_path: Optional[str] = None


class InventoryDataSourceRequest(BaseModel):
    model_id: str
    file_name: str
    source_type: Optional[str] = "file"
    purpose: Optional[str] = "Validation dataset"
    uploaded_by: Optional[str] = "user"
    uploaded_at: Optional[str] = None
    record_count: Optional[int] = None
    column_count: Optional[int] = None
    target_variable: Optional[str] = None
    storage_reference: Optional[str] = None


class InventoryValidationRequest(BaseModel):
    model_id: str
    stage: str
    status: str
    findings_count: Optional[int] = None
    last_run: Optional[str] = None
    description: Optional[str] = None
    user: Optional[str] = None


@app.get("/model-inventory")
async def get_model_inventory() -> Dict[str, Any]:
    # Read-only: loading a page must never modify the inventory. Missing model
    # reports are generated by the registration / write endpoints instead.
    return persistence.load_model_inventory()


@app.get("/model-inventory/development/{model_id}/lineage")
async def get_development_model_lineage(model_id: str) -> Dict[str, Any]:
    """Read-only: whether a registered development model can be reproduced
    (lineage contract + scoring bundle). Writes nothing. Unknown ID → 404."""
    wanted = (model_id or "").strip()
    entry = next((m for m in persistence.load_model_inventory().get("development", [])
                  if isinstance(m, dict) and str(m.get("model_id") or "").strip() == wanted), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Registered model '{wanted}' was not found in the Development Inventory.")
    return model_lineage.lineage_readiness(entry)


@app.get("/model-inventory/legacy-readiness")
async def get_legacy_readiness() -> Dict[str, Any]:
    """Read-only: what lineage evidence exists for every registered
    development model, and what each needs (E10). Writes nothing."""
    return model_lineage.legacy_readiness_report(persistence.load_model_inventory())


@app.get("/lineage/dataset/{sha256}")
async def get_dataset_lineage(sha256: str) -> Dict[str, Any]:
    """Read-only provenance of a dataset fingerprint (E11): every development
    run that recorded it, as the parsed-table fingerprint (dataset_sha256) or
    the original-file fingerprint (dataset_file_sha256), and the registered
    models trained on it."""
    wanted = (sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", wanted):
        raise HTTPException(status_code=400, detail="sha256 must be a 64-character hexadecimal fingerprint.")
    runs = []
    for row in persistence.read_log(persistence.DEV_PIPELINE_LOG):
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        matched = [f for f in ("dataset_sha256", "dataset_file_sha256") if str(summary.get(f) or "").lower() == wanted]
        if matched:
            runs.append({"run_id": row.get("run_id"), "timestamp": row.get("timestamp"), "stage": row.get("stage"),
                         "matched_as": matched, "dataset_sha256": summary.get("dataset_sha256"),
                         "dataset_file_sha256": summary.get("dataset_file_sha256"),
                         "registered_model_id": summary.get("registered_model_id"),
                         "artifact_sha256": summary.get("artifact_sha256")})
    models = []
    for m in persistence.load_model_inventory().get("development", []):
        ds = ((m.get("lineage_contract") or {}).get("dataset") or {}) if isinstance(m, dict) else {}
        if wanted in (str(ds.get("sha256") or "").lower(), str(ds.get("file_sha256") or "").lower()):
            models.append({"model_id": m.get("model_id"), "training_run_id": (m.get("lineage_contract") or {}).get("training_run_id"),
                           "dataset_name": ds.get("name")})
    # The same parsed table reached from different files (or vice versa) is
    # reported, not hidden: it means the file changed but the table did not.
    tables = sorted({r["dataset_sha256"] for r in runs if r.get("dataset_sha256")})
    files = sorted({r["dataset_file_sha256"] for r in runs if r.get("dataset_file_sha256")})
    return {"sha256": wanted, "runs": sorted(runs, key=lambda r: r.get("timestamp") or ""), "models": models,
            "distinct_table_fingerprints": tables, "distinct_file_fingerprints": files}


@app.get("/model-inventory/documentation")
async def get_model_documentation(path: str) -> FileResponse:
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = BACKEND_DIR / candidate
    normalized = candidate.resolve()
    try:
        normalized.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid documentation path")
    if not normalized.exists() or not normalized.is_file():
        raise HTTPException(status_code=404, detail="Documentation not found")
    return FileResponse(normalized, filename=normalized.name)


@app.post("/model-inventory/models")
async def create_inventory_model(payload: InventoryModelRequest) -> Dict[str, Any]:
    store = persistence.ensure_model_inventory_seed()
    model_id = persistence.next_model_id(store)
    now = pd.Timestamp.now().isoformat()
    entry = {
        "model_id": model_id,
        "model_name": payload.model_name,
        "model_type": payload.model_type or "Custom",
        "business_purpose": payload.business_purpose or "Consultant demo model",
        "model_owner": payload.model_owner or "TBD",
        "business_unit": payload.business_unit or "Risk",
        "model_version": payload.model_version or "1.0",
        "regulatory_framework": payload.regulatory_framework or "Internal",
        "status": payload.status or "Draft",
        "development_date": payload.development_date or now.split("T", 1)[0],
        "implementation_date": payload.implementation_date,
        "last_validation_date": payload.last_validation_date,
        "next_validation_due": payload.next_validation_due,
        "model_risk_rating": payload.model_risk_rating or "Medium",
        "approval_status": payload.approval_status or "Draft",
        "reviewer": payload.reviewer or "TBD",
        "documentation_url": payload.documentation_url,
        "documentation_path": payload.documentation_path,
        "document_url": payload.document_url,
        "document_path": payload.document_path,
        "created_at": now,
        "updated_at": now,
    }
    store.setdefault("models", []).append(entry)
    persistence.append_history_event(store, model_id, "Model Registered", f"Model {payload.model_name} was added to the inventory.", user=payload.model_owner or "user")
    persistence.save_model_inventory(store)
    return entry


@app.put("/model-inventory/models/{model_id}")
async def update_inventory_model(model_id: str, payload: InventoryModelRequest) -> Dict[str, Any]:
    store = persistence.ensure_model_inventory_seed()
    model_entry = next((item for item in store.setdefault("models", []) if item.get("model_id") == model_id), None)
    if model_entry is None:
        raise HTTPException(status_code=404, detail="Model not found")

    for field, value in payload.dict().items():
        if value is not None:
            model_entry[field] = value
    model_entry["updated_at"] = pd.Timestamp.now().isoformat()
    persistence.save_model_inventory(store)
    return model_entry


@app.post("/model-inventory/data-sources")
async def create_inventory_data_source(payload: InventoryDataSourceRequest) -> Dict[str, Any]:
    store = persistence.ensure_model_inventory_seed()
    entry = persistence.create_data_source(store, payload.model_id, payload.dict())
    persistence.save_model_inventory(store)
    return entry


@app.post("/model-inventory/validation")
async def update_inventory_validation(payload: InventoryValidationRequest) -> Dict[str, Any]:
    store = persistence.ensure_model_inventory_seed()
    entry = persistence.update_model_validation_status(
        store,
        payload.model_id,
        payload.stage,
        payload.status,
        findings_count=payload.findings_count,
        last_run=payload.last_run,
        description=payload.description,
        user=payload.user,
    )
    persistence.save_model_inventory(store)
    return entry


@app.get("/model-inventory/export")
async def export_model_inventory() -> StreamingResponse:
    if Workbook is None:
        raise HTTPException(status_code=500, detail="openpyxl is not available for Excel export")

    store = persistence.load_model_inventory()  # read-only, like GET /model-inventory
    output = io.BytesIO()
    wb = Workbook()
    ws_models = wb.active
    ws_models.title = "Models"
    ws_models.append([
        "model_id",
        "model_name",
        "model_type",
        "status",
        "business_purpose",
        "model_owner",
        "business_unit",
        "model_version",
        "regulatory_framework",
        "model_risk_rating",
        "approval_status",
        "reviewer",
        "last_validation_date",
        "next_validation_due",
        "created_at",
        "updated_at",
    ])
    for model in store.get("models", []):
        ws_models.append([
            model.get("model_id"),
            model.get("model_name"),
            model.get("model_type"),
            model.get("status"),
            model.get("business_purpose"),
            model.get("model_owner"),
            model.get("business_unit"),
            model.get("model_version"),
            model.get("regulatory_framework"),
            model.get("model_risk_rating"),
            model.get("approval_status"),
            model.get("reviewer"),
            model.get("last_validation_date"),
            model.get("next_validation_due"),
            model.get("created_at"),
            model.get("updated_at"),
        ])

    ws_sources = wb.create_sheet("Data Sources")
    ws_sources.append(["data_source_id", "model_id", "file_name", "source_type", "purpose", "uploaded_by", "uploaded_at", "record_count", "column_count", "target_variable", "storage_reference"])
    for source in store.get("data_sources", []):
        ws_sources.append([
            source.get("data_source_id"),
            source.get("model_id"),
            source.get("file_name"),
            source.get("source_type"),
            source.get("purpose"),
            source.get("uploaded_by"),
            source.get("uploaded_at"),
            source.get("record_count"),
            source.get("column_count"),
            source.get("target_variable"),
            source.get("storage_reference"),
        ])

    ws_validation = wb.create_sheet("Validation")
    ws_validation.append(["model_id", "data_validation_status", "conceptual_soundness_status", "backtesting_status", "overall_status", "findings_count", "last_validation"])
    for item in store.get("validation", []):
        ws_validation.append([
            item.get("model_id"),
            item.get("data_validation_status"),
            item.get("conceptual_soundness_status"),
            item.get("backtesting_status"),
            item.get("overall_status"),
            item.get("findings_count"),
            item.get("last_validation"),
        ])

    ws_history = wb.create_sheet("History")
    ws_history.append(["model_id", "event", "description", "timestamp", "user"])
    for item in store.get("history", []):
        ws_history.append([item.get("model_id"), item.get("event"), item.get("description"), item.get("timestamp"), item.get("user")])

    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=model_inventory.xlsx"},
    )


def _preview_split(X: pd.DataFrame, y: pd.Series, task_type: str, test_size: float, val_size: float, random_seed: int):
    """Split used by the data-preparation previews (feature decision log,
    feature engineering, model recommendation). Uses the SAME split settings
    as the training configuration the caller passes (defaults match
    /models/train), never fixed values, and returns the split configuration
    actually applied (sizes, seed, rows, training-row fingerprint) so the
    preview can be reproduced and matched to a training run (E12)."""
    if not (0.0 < float(test_size) < 1.0 and 0.0 < float(val_size) < 1.0 and float(test_size) + float(val_size) < 1.0):
        raise HTTPException(status_code=400, detail="test_size and val_size must be in (0, 1) and sum to less than 1.")
    report: Dict[str, Any] = {}
    splits = split_data(X, y, test_size=test_size, val_size=val_size, task_type=task_type,
                        random_state=random_seed, report=report)
    X_train, X_val, X_test = splits[0], splits[1], splits[2]
    split_config = {
        "strategy": SPLIT_STRATEGY_STRATIFIED,
        "test_size": test_size, "val_size": val_size, "random_seed": random_seed,
        "train_rows": int(len(X_train)), "val_rows": int(len(X_val)), "test_rows": int(len(X_test)),
        "train_index_sha256": model_lineage.index_fingerprint(X_train.index),
        "achieved": report.get("achieved"), "degraded": bool(report.get("degraded")),
        "fallbacks": report.get("fallbacks") or [],
        "class_counts": report.get("class_counts"),
    }
    return splits, split_config


@app.post("/data/feature-decision-log")
async def feature_decision_log(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
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
    (X_train, X_val, X_test, y_train, y_val, y_test), split_config = _preview_split(
        X, y, task_type, test_size, val_size, random_seed)
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
    return {"file_name": "feature_decision_log.csv", "content_base64": base64.b64encode(csv_bytes).decode("utf-8"),
            "split_config": split_config}


class ComplianceRequest(BaseModel):
    stage: str
    payload: Dict[str, Any]


class TierRequest(BaseModel):
    training_config: Dict[str, Any]
    metrics: Dict[str, Any]
    fe_summary: Optional[Dict[str, Any]] = None


_agent2: Optional[Agent2] = None
_source_agent2: Optional["SourceAgent2"] = None
# Use the local runtime rule store for the 24-06 backend so the validation
# workflow resolves the same ruleset regardless of the source-of-truth tree.
VAL_MDD_RULES_PATH = BACKEND_DIR / "rag_store" / "val_mdd_rules.json"


def _load_agent2() -> Optional[Agent2]:
    global _agent2
    if _agent2 is not None:
        return _agent2
    try:
        _agent2 = Agent2(str(RULES_PATH))
    except Exception:
        _agent2 = None
    return _agent2


class _SyncFileLike:
    """Wraps a FastAPI UploadFile's underlying SpooledTemporaryFile with the
    sync .name/.seek()/.read() interface parse_mdd_file() expects (ported from
    Streamlit's UploadedFile). SpooledTemporaryFile.name is a read-only property
    in this Python version, so it can't just be assigned onto the file object
    directly (that raises AttributeError, and call sites that swallow it end up
    silently parsing "" instead of the document — every keyword-search RAG rule
    then reports 0 keyword hits against an MDD that was never actually read).
    """

    def __init__(self, upload_file: UploadFile):
        self._file = upload_file.file
        self.name = upload_file.filename or ""

    def seek(self, *args, **kwargs):
        return self._file.seek(*args, **kwargs)

    def read(self, *args, **kwargs):
        return self._file.read(*args, **kwargs)


def _sync_file_like(upload_file: UploadFile) -> _SyncFileLike:
    upload_file.file.seek(0)
    return _SyncFileLike(upload_file)


def _load_source_agent2() -> Optional["SourceAgent2"]:
    """Cached loader for the RAG rule-matching Agent2 (val_mdd_rules.json)."""
    global _source_agent2
    print("[LOAD-1] Entering _load_source_agent2")
    if _source_agent2 is not None:
        print("[LOAD-4] Returning SourceAgent2")
        return _source_agent2
    try:
        print("[LOAD-2] About to import Agent2")
        _source_agent2 = SourceAgent2(str(VAL_MDD_RULES_PATH))
        print("[LOAD-3] Import succeeded")
        print("[LOAD-4] Returning SourceAgent2")
    except Exception:
        print("[LOAD-ERROR]")
        import traceback
        traceback.print_exc()
        _source_agent2 = None
    return _source_agent2


async def _read_dataframe(
    file: Optional[UploadFile] = None,
    csv_text: Optional[str] = None,
    synthetic_samples: Optional[int] = None,
) -> pd.DataFrame:
    if synthetic_samples and synthetic_samples > 0:
        return generate_synthetic_credit_dataset(n_samples=synthetic_samples)

    # csv_text represents the CURRENT state of the pipeline (e.g. after FRED
    # macro features, feature engineering, etc. have been attached and carried
    # forward from an earlier step) and must win whenever present. `file` is
    # only used as a fallback for the very first upload, before any csv_text
    # exists yet — if both happen to be sent together (e.g. the frontend still
    # holds onto the originally uploaded file in state), silently preferring
    # `file` would discard every transformation applied since the initial
    # upload with no error or signal that it happened.
    if csv_text:
        return pd.read_csv(io.StringIO(csv_text), keep_default_na=True, float_precision="round_trip")

    if file is not None:
        name = file.filename.lower()
        if name.endswith(".csv"):
            file.file.seek(0)
            return pd.read_csv(file.file, keep_default_na=True, float_precision="round_trip")
        if name.endswith(('.xls', '.xlsx')):
            file.file.seek(0)
            return pd.read_excel(file.file, engine="openpyxl")
        raise HTTPException(status_code=400, detail="Unsupported file type. Use CSV or XLSX.")

    raise HTTPException(status_code=400, detail="Provide a file upload, CSV text, or synthetic_samples.")


def _serialize_dataframe(df: pd.DataFrame, max_rows: int = 5) -> Dict[str, Any]:
    return {
        "shape": list(df.shape),
        "columns": df.columns.astype(str).tolist(),
        "preview": df.head(max_rows).replace({pd.NA: None}).to_dict(orient="records"),
    }


def _json_safe_scalar(v: Any) -> Any:
    """Convert a single numpy/pandas scalar to a plain JSON-safe Python value —
    numpy int/float types aren't natively JSON-serializable, and non-finite
    floats (inf/-inf/nan) become the non-standard `Infinity`/`NaN` tokens that
    Python's json encoder tolerates but JavaScript's JSON.parse rejects."""
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        f = float(v)
        return f if np.isfinite(f) else None
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, float) and not np.isfinite(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _serialize_stage5_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    out = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            out[key] = _serialize_stage5_payload(value)
        elif isinstance(value, (list, tuple)):
            out[key] = [_serialize_stage5_payload(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, (np.integer, np.floating, np.bool_)):
            out[key] = _json_safe_scalar(value)
        elif isinstance(value, (pd.DataFrame, pd.Series)):
            out[key] = None
        elif isinstance(value, (np.ndarray,)):
            out[key] = value.tolist()
        else:
            out[key] = _json_safe_scalar(value)
    return out


def _to_base64(obj: Any) -> str:
    buffer = io.BytesIO()
    joblib.dump(obj, buffer)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


# Browser-uploaded model artifacts (pickles) are NEVER deserialized: unpickling
# runs code. Endpoints that score a model resolve it from an exact registered
# model ID to the server's own scoring bundle, verified against the lineage
# contract (model_lineage.load_registered_scoring_bundle). The old
# _from_base64 / _load_model_artifact upload loaders were removed for this.
UPLOADED_ARTIFACT_REJECTED = (
    "Uploaded model artifacts are not accepted (deserializing them could execute code). "
    "Supply registered_model_id: the server loads that registered model's verified scoring bundle."
)


def _resolve_registered_pipeline(registered_model_id: Optional[str], uploaded_artifact_sent: bool) -> Dict[str, Any]:
    """Verified scoring bundle for an exact registered model ID, or an HTTP
    error. An uploaded artifact is never read — its presence only changes the
    error message when no ID is given."""
    if not (registered_model_id or "").strip():
        raise HTTPException(status_code=400, detail=UPLOADED_ARTIFACT_REJECTED if uploaded_artifact_sent
                            else "registered_model_id is required: the model is loaded from its verified registered scoring bundle.")
    try:
        return model_lineage.load_registered_scoring_bundle(registered_model_id)
    except model_lineage.ArtifactVerificationError as exc:
        raise HTTPException(status_code=exc.http_status,
                            detail=f"Registered model cannot be loaded ({exc.status}): {' '.join(exc.reasons)}")


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
    if resolved_target_col is not None and not target_candidates:
        # Ensure the chosen target is also available as a candidate so the
        # frontend can reliably select it for downstream pages like feature
        # engineering when the heuristic finds it by name rather than by binary
        # target scoring.
        target_candidates = [resolved_target_col]
    task_type = None
    if resolved_target_col is not None:
        task_type = detect_task_type(df[resolved_target_col])

    leakage_risk_cols: List[str] = []
    if resolved_target_col is not None and task_type == "binary":
        target_numeric = pd.to_numeric(df[resolved_target_col], errors="coerce")
        if target_numeric.notna().sum() >= 2:
            for col in col_types.get("numeric", []):
                if col == resolved_target_col:
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
            raw_non_null = int(df[dt_col].notna().sum())
            parsed = pd.to_datetime(df[dt_col], errors="coerce")
            valid = parsed.dropna()
            if valid.empty:
                continue
            today = pd.Timestamp.today().normalize()
            future_count = int((valid > today).sum())
            ancient_count = int((valid.dt.year < 1900).sum())
            # Values that are non-null in the raw column but failed to parse as
            # a date at all (distinct from future/ancient, which are valid
            # dates with an implausible value). Objective/derivable from the
            # data itself — no business rule involved.
            unparseable_count = int(raw_non_null - len(valid))
            unparseable_percentage = round((unparseable_count / raw_non_null * 100) if raw_non_null else 0.0, 4)
            date_integrity[dt_col] = {
                "min_date": str(valid.min().date()),
                "max_date": str(valid.max().date()),
                "future_count": future_count,
                "ancient_count": ancient_count,
                "unparseable_count": unparseable_count,
                "unparseable_percentage": unparseable_percentage,
            }
        except Exception:
            continue

    # Validity — numeric format check: non-null values in columns detected as
    # numeric that fail pd.to_numeric coercion. Objective/derivable from the
    # data itself (a value either parses as a number or it doesn't) — no
    # invented range or threshold involved. Checked across every numeric
    # column (not sampled/capped) since the operation is cheap.
    numeric_format_errors: Dict[str, Any] = {}
    for col in col_types.get("numeric", []):
        try:
            non_null = df[col].dropna()
            if non_null.empty:
                continue
            parsed_numeric = pd.to_numeric(non_null, errors="coerce")
            fail_count = int(parsed_numeric.isna().sum())
            fail_pct = round((fail_count / len(non_null) * 100) if len(non_null) else 0.0, 4)
            numeric_format_errors[col] = {"count": fail_count, "percentage": fail_pct}
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
        "numeric_format_errors": numeric_format_errors,
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
    demo_mode: Optional[str] = Form(None),
) -> Dict[str, Any]:
    if demo_mode and file is None and csv_text is None and not synthetic_samples:
        demo_mode = _normalize_demo_mode(demo_mode)
        if demo_mode == "flawed":
            demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_portfolio.csv"
            dataset_name = "Demo B dataset"
        elif demo_mode == "taiwan":
            demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "taiwan_portfolio.csv"
            dataset_name = "Demo A Taiwan dataset"
        else:
            demo_file = SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_portfolio.csv"
            dataset_name = "Demo A dataset"
        if not demo_file.exists():
            raise HTTPException(status_code=400, detail=f"Demo dataset not found for mode '{demo_mode}'.")
        df = pd.read_csv(demo_file, keep_default_na=True, float_precision="round_trip")
        profile = _build_data_profile(df, dataset_name=dataset_name)
        default_col = next((c for c in df.columns if "default" in str(c).lower()), "default")
        profile["rows"] = int(df.shape[0])
        profile["default_rate"] = float(df[default_col].mean()) if default_col in df.columns else 0.0
        profile["csv_text"] = df.to_csv(index=False)
        profile["source_type"] = "demo"
        profile["demo_mode"] = demo_mode
        profile["demo_dataset"] = True
        profile["dataset_identity"] = {**dataset_identity(df, None, profile["csv_text"]), "demo_dataset": True}
        try:
            persistence.log_event(
                persistence.DEV_PIPELINE_LOG,
                stage="data_upload",
                payload={
                    "filename": dataset_name,
                    "row_count": int(df.shape[0]),
                    "column_count": int(df.shape[1]),
                    "demo_dataset": True,
                    **profile["dataset_identity"],
                },
                full_payload=profile,
            )
        except Exception as e:
            print(f"[persistence] failed to log data_upload: {e}")
        return profile

    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    dataset_name = file.filename if file is not None else "Synthetic Credit Dataset"
    profile = _build_data_profile(df, dataset_name=dataset_name)
    if synthetic_samples and synthetic_samples > 0 and file is None:
        profile["csv_text"] = df.to_csv(index=False)
        profile["source_type"] = "synthetic"
        profile["synthetic_samples"] = int(synthetic_samples)
    else:
        profile["source_type"] = "file"
    # Original-file identity (bytes as received) and parsed-table identity,
    # recorded separately so a later mutation of either is detectable (E11).
    profile["dataset_identity"] = dataset_identity(df, file, csv_text if not synthetic_samples else None)
    try:
        persistence.log_event(
            persistence.DEV_PIPELINE_LOG,
            stage="data_upload",
            payload={
                "filename": dataset_name,
                "row_count": int(df.shape[0]),
                "column_count": int(df.shape[1]),
                **profile["dataset_identity"],
            },
            full_payload=profile,
        )
    except Exception as e:
        print(f"[persistence] failed to log data_upload: {e}")
    return profile


def _fetch_remote_csv(api_url: str, http_method: str = "GET") -> str:
    method = http_method.upper().strip()
    if method != "GET":
        raise HTTPException(status_code=400, detail="Only GET is supported for API data sources.")
    try:
        parsed = urllib.parse.urlparse(api_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("API URL must use http or https")
        request = urllib.request.Request(api_url, method="GET", headers={"User-Agent": "AegisCreditDataUploader/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            if "csv" not in content_type.lower() and "text" not in content_type.lower():
                raise HTTPException(status_code=400, detail="Only CSV API responses are currently supported.")
            return text
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail=f"API request failed: {exc.reason}")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=400, detail=f"API request failed: {exc.reason}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _normalize_db_type(db_type: str) -> str:
    if db_type is None:
        return ""
    return db_type.strip().lower()


def _build_database_url(
    db_type: str,
    host: Optional[str],
    port: Optional[str],
    database: Optional[str],
    username: Optional[str],
    password: Optional[str],
) -> str:
    db_type = _normalize_db_type(db_type)
    database = (database or "").strip()
    if not database:
        raise HTTPException(status_code=400, detail="Database name/path is required.")

    if db_type == "sqlite":
        if database == ":memory:":
            return "sqlite:///:memory:"
        path = Path(database)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        return f"sqlite:///{path.as_posix()}"

    username = (username or "").strip()
    password = (password or "").strip()
    host = (host or "localhost").strip() or "localhost"
    port = (port or "").strip()

    if db_type == "postgresql":
        driver = "psycopg2"
        default_port = "5432"
    elif db_type == "mysql":
        driver = "pymysql"
        default_port = "3306"
    elif db_type in ("sqlserver", "mssql"):
        driver = "pyodbc"
        default_port = "1433"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported database type '{db_type}'.")

    port = port or default_port
    if db_type in ("sqlserver", "mssql"):
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required for SQL Server.")
        driver_query = "?driver=ODBC+Driver+17+for+SQL+Server"
        return f"mssql+{driver}://{username}:{password}@{host}:{port}/{database}{driver_query}"

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required for database connections.")

    return f"{db_type}+{driver}://{username}:{password}@{host}:{port}/{database}"


def _create_database_engine(
    db_type: str,
    host: Optional[str],
    port: Optional[str],
    database: Optional[str],
    username: Optional[str],
    password: Optional[str],
):
    url = _build_database_url(db_type, host, port, database, username, password)
    try:
        engine = create_engine(url, future=True, connect_args={"connect_timeout": 10} if _normalize_db_type(db_type) != "sqlite" else {})
        return engine
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=400, detail=f"Database URL error: {exc}")


def _inspect_database_tables(engine) -> List[str]:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    views = inspector.get_view_names()
    return sorted(set(tables + views))


@app.post("/data/database/test")
async def test_database_connection(
    db_type: str = Form(...),
    host: Optional[str] = Form(None),
    port: Optional[str] = Form(None),
    database: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
) -> Dict[str, Any]:
    engine = _create_database_engine(db_type, host, port, database, username, password)
    try:
        with engine.connect() as connection:
            # SQLAlchemy 2.0 requires an executable SQL expression; use text()
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=400, detail=f"Database connection failed: {exc}")
    finally:
        engine.dispose()
    return {"status": "ok"}


@app.post("/data/database/tables")
async def list_database_tables(
    db_type: str = Form(...),
    host: Optional[str] = Form(None),
    port: Optional[str] = Form(None),
    database: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
) -> Dict[str, Any]:
    engine = _create_database_engine(db_type, host, port, database, username, password)
    try:
        tables = _inspect_database_tables(engine)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to list tables: {exc}")
    finally:
        engine.dispose()
    return {"tables": tables}


@app.post("/data/database/fetch")
async def fetch_database_table(
    db_type: str = Form(...),
    host: Optional[str] = Form(None),
    port: Optional[str] = Form(None),
    database: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    selected_table: str = Form(...),
) -> Dict[str, Any]:
    engine = _create_database_engine(db_type, host, port, database, username, password)
    try:
        if "." in selected_table:
            schema, table_name = selected_table.split(".", 1)
        else:
            schema = None
            table_name = selected_table

        try:
            df = pd.read_sql_table(table_name, con=engine, schema=schema)
        except Exception:
            query = f"SELECT * FROM {selected_table}"
            df = pd.read_sql_query(query, con=engine)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch table '{selected_table}': {exc}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch table '{selected_table}': {exc}")
    finally:
        engine.dispose()

    profile = _build_data_profile(df, dataset_name=selected_table)
    profile["csv_text"] = df.to_csv(index=False)
    profile["source_type"] = "database"
    profile["database_type"] = db_type
    profile["database_host"] = host
    profile["database_name"] = database
    profile["database_table"] = selected_table
    return profile


def _save_upload_to_temp(file: UploadFile, suffix: str = ".db") -> str:
    """SQLite needs a real file path, not an in-memory stream — write the
    upload to a temp file. Caller is responsible for deleting it (see
    try/finally at each call site below)."""
    file.file.seek(0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        return tmp.name


def _save_uploaded_mdd(file: UploadFile) -> str:
    """Persist an uploaded MDD file to a backend-visible path for inventory docs."""
    # APP_DATA_DIR is defined in persistence, not in this module — referencing
    # it bare raised NameError, which made POST /validation/parse-mdd always
    # return 500 (and silently skipped saving the MDD in /validation/replication).
    target_dir = persistence.APP_DATA_DIR / "validation_mdds"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = Path(file.filename or "validation_mdd.txt").name
    if not file_name:
        file_name = "validation_mdd.txt"
    unique_name = f"{pd.Timestamp.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex[:8]}_{file_name}"
    target_path = target_dir / unique_name
    file.file.seek(0)
    with open(target_path, "wb") as out:
        out.write(file.file.read())
    return str(target_path.relative_to(persistence.BACKEND_DIR))


def _unlink_quietly(path: str) -> None:
    """Best-effort temp-file cleanup. On Windows a sqlite3 connection can
    still hold the file open for a moment after its Python object goes out
    of scope, so os.unlink() can raise PermissionError here even though the
    actual request already completed successfully — that shouldn't turn a
    good response into a 500."""
    try:
        os.unlink(path)
    except OSError:
        pass


@app.post("/data/integration/sqlite/inspect")
async def integration_sqlite_inspect(db_file: UploadFile = File(...)) -> Dict[str, Any]:
    """Part B — upload a SQLite database and discover every table plus its
    schema, so the frontend can populate the Loan / Collateral table
    dropdowns. Nothing here assumes specific table names."""
    tmp_path = _save_upload_to_temp(db_file)
    try:
        tables = di.list_tables(tmp_path)
        if not tables:
            raise HTTPException(status_code=400, detail="No tables found in the uploaded database.")
        return {"tables": [di.inspect_table(tmp_path, t) for t in tables]}
    except di.DataIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        _unlink_quietly(tmp_path)


@app.post("/data/integration/relationships")
async def integration_relationships(
    db_file: Optional[UploadFile] = File(None),
    customer_file: Optional[UploadFile] = File(None),
    customer_csv_text: Optional[str] = Form(None),
    selected_tables: str = Form(...),  # comma-separated table names from the db
) -> Dict[str, Any]:
    """Part C — automatic relationship discovery across the customer dataset
    and whichever SQLite tables the user selected. Returns ranked join
    candidates with confidence + human-readable reasons; the frontend
    pre-fills the suggested (highest-confidence) join per table pair but
    always lets the user override it before running the integration."""
    table_names = [t.strip() for t in selected_tables.split(",") if t.strip()]
    if not table_names:
        raise HTTPException(status_code=400, detail="No tables selected.")

    tables: Dict[str, pd.DataFrame] = {}
    tmp_path = None
    try:
        if db_file is not None:
            tmp_path = _save_upload_to_temp(db_file)
            available = set(di.list_tables(tmp_path))
            for t in table_names:
                if t not in available:
                    raise HTTPException(status_code=400, detail=f"Table '{t}' not found in the uploaded database.")
                tables[t] = di.SQLiteDataSource(t, tmp_path, t).load()

        if customer_file is not None or customer_csv_text:
            customer_df = await _read_dataframe(file=customer_file, csv_text=customer_csv_text)
            tables["customer"] = customer_df

        if len(tables) < 2:
            raise HTTPException(status_code=400, detail="At least two sources are required to discover relationships.")

        primary_keys, candidates = di.discover_relationships(tables)
        return {
            "primary_keys": [pk.as_dict() for pk in primary_keys],
            "candidates": [c.as_dict() for c in candidates],
        }
    except di.DataIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        if tmp_path:
            _unlink_quietly(tmp_path)


@app.post("/data/integration/run")
async def integration_run(
    customer_file: Optional[UploadFile] = File(None),
    customer_csv_text: Optional[str] = Form(None),
    db_file: Optional[UploadFile] = File(None),
    loan_table: Optional[str] = Form(None),
    collateral_table: Optional[str] = Form(None),
    join_specs_json: Optional[str] = Form(None),
    fetch_macro: bool = Form(False),
    macro_date_col: Optional[str] = Form(None),
    join_how: str = Form("left"),
) -> Dict[str, Any]:
    """Parts D/E/F/G/I — run the full integration: merge the customer CSV
    with whichever SQLite tables were selected using the user-confirmed join
    keys (join_specs_json — a JSON list of {right_table, left_key,
    right_key} the frontend built from discover_relationships' suggestions,
    possibly overridden), then optionally attach FRED macro series by date.

    Returns the SAME shape /data/upload already returns (via
    _build_data_profile + csv_text) so nothing downstream — preprocessing,
    feature engineering, model training — needs to change. See Part I.
    """
    if customer_file is None and not customer_csv_text:
        raise HTTPException(status_code=400, detail="Customer data (file or csv_text) is required as the base of the integration.")

    customer_df = await _read_dataframe(file=customer_file, csv_text=customer_csv_text)
    source_metadata: List[di.SourceMetadata] = [di.CSVDataSource("customer", customer_df).metadata(customer_df)]

    tmp_path = None
    try:
        tables: Dict[str, pd.DataFrame] = {}
        selected_sqlite_tables = [t for t in (loan_table, collateral_table) if t]
        if selected_sqlite_tables:
            if db_file is None:
                raise HTTPException(status_code=400, detail="A SQLite database file is required when a loan/collateral table is selected.")
            tmp_path = _save_upload_to_temp(db_file)
            for t in selected_sqlite_tables:
                source = di.SQLiteDataSource(t, tmp_path, t)
                tdf = source.load()
                tables[t] = tdf
                source_metadata.append(source.metadata(tdf))

        try:
            join_specs_raw = json.loads(join_specs_json) if join_specs_json else []
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="join_specs_json must be valid JSON.")

        join_specs = [
            di.TableJoinSpec(
                right_table=spec["right_table"], left_key=spec["left_key"], right_key=spec["right_key"],
                how=di.JoinStrategy(spec.get("how", join_how)),
            )
            for spec in join_specs_raw
        ]

        integrator = di.DatasetIntegrator()
        try:
            integrated = integrator.integrate("customer", customer_df, tables, join_specs, source_metadata)
        except di.DataIntegrationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if fetch_macro:
            api_key = os.environ.get("FRED_API_KEY", "").strip()
            if not api_key:
                integrator.report.warnings.append("No FRED API key is configured on the server — macro data was not fetched.")
            else:
                integrated = integrator.attach_macro(integrated, macro_date_col, fred_client, api_key)

        dataset_name = "Integrated dataset"
        profile = _build_data_profile(integrated, dataset_name=dataset_name)
        profile["csv_text"] = integrated.to_csv(index=False)
        profile["source_type"] = "integrated"
        profile["integration_report"] = integrator.report.as_dict()
        # Provenance (E11): the integrated table's identity, plus the identity
        # of each supplied source file exactly as received. Sources are never
        # rewritten; the integrated dataset is a new, separately identified table.
        profile["dataset_identity"] = dataset_identity(integrated, None, profile["csv_text"])
        profile["source_identities"] = {
            "customer": source_fingerprint(customer_file, customer_csv_text),
            "database": source_fingerprint(db_file) if db_file is not None else None,
        }
        try:
            persistence.log_event(
                persistence.DEV_PIPELINE_LOG,
                stage="data_upload",
                payload={"filename": dataset_name, "row_count": int(integrated.shape[0]),
                         "column_count": int(integrated.shape[1]), **profile["dataset_identity"],
                         "source_identities": profile["source_identities"]},
            )
        except Exception as e:
            print(f"[persistence] failed to log integration: {e}")
        return profile
    finally:
        if tmp_path:
            _unlink_quietly(tmp_path)



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


def _expand_plotly_bdata(obj):
    """
    Recursively expand Plotly's compact typed-array JSON encoding back into
    plain number lists.

    Since plotly.py ~5.24+, fig.to_json() encodes numeric trace arrays as
    {"dtype": "f8", "bdata": "<base64>"} instead of a plain JSON array, to
    shrink payload size. This requires a fairly recent plotly.js on the
    frontend to decode — older/most bundled versions just silently fail to
    plot that trace, so a chart's tab looks like nothing happened when
    clicked even though real figure JSON is present. Expanding it back to
    plain arrays here keeps this working regardless of the frontend's
    plotly.js version.
    """
    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj and isinstance(obj["bdata"], str):
            try:
                raw = base64.b64decode(obj["bdata"])
                flat = np.frombuffer(raw, dtype=obj["dtype"])
                # Multi-dimensional arrays (e.g. heatmap z) are flattened into
                # a single bdata blob with a companion "shape" field like
                # "2, 2" — without reshaping here we'd hand the frontend a
                # flat list where it expects nested rows, which breaks any
                # code that does z.map(row => row.map(...)).
                shape = obj.get("shape")
                if shape:
                    dims = [int(d) for d in str(shape).split(",") if d.strip()]
                    if len(dims) > 1:
                        flat = flat.reshape(dims)
                return flat.tolist()
            except Exception:
                return obj
        return {k: _expand_plotly_bdata(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_plotly_bdata(v) for v in obj]
    return obj


def _figure_json(fig) -> Optional[Dict[str, Any]]:
    """
    Convert a Plotly go.Figure into a plain JSON-safe dict for the
    PlotlyChart React component. Goes through fig.to_json() (Plotly's own
    encoder) rather than fig.to_dict(), since traces built directly from
    numpy arrays (as the eval_engine plot_* functions do) aren't otherwise
    serializable by FastAPI's default JSON encoder — then expands any
    compact typed-array encoding back to plain arrays (see
    _expand_plotly_bdata) so the frontend can actually render it.
    """
    if fig is None:
        return None
    try:
        return _expand_plotly_bdata(json.loads(fig.to_json()))
    except Exception:
        return None


def _build_evaluation_data(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray],
    task_type: str,
    threshold: Optional[float] = None,
    dates: Optional[pd.Series] = None,
    date_columns: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Shared by /models/train and /models/evaluate: computes the metric suite
    (with KS statistic + Brier score for binary tasks) and builds the full
    evaluation_data payload the Evaluation page's charts read from — Plotly
    figure JSON per tab (ROC/PR/confusion/threshold/score-distribution/lift),
    the heteroscedasticity residual check, and the temporal-stability bundle
    (Monthly/Quarterly/Yearly actual-vs-predicted) when an origination date
    is available. Returns (metrics, evaluation_data).

    `threshold=None` (the default) auto-selects the F1-maximizing threshold
    via compute_binary_metrics()/select_best_threshold() instead of a fixed
    0.5 cut-off — every downstream chart (confusion matrix, threshold curve,
    etc.) is built against that same resolved threshold so nothing drifts
    out of sync. Pass an explicit float to pin a specific operating point
    instead (e.g. a reviewer-chosen threshold on the /models/evaluate page).
    """
    if task_type == "binary":
        metrics = compute_binary_metrics(y_true, y_pred, y_proba, threshold=threshold)
        # Resolve to the threshold actually used (auto-selected or explicit)
        # so every chart/payload field below is consistent with `metrics`.
        threshold = metrics.get("threshold_used", threshold if threshold is not None else 0.5)
        hetero_input = y_proba if y_proba is not None else y_pred
        roc_curve_pts = compute_roc_curve(y_true, y_proba) if y_proba is not None else []
        pr_curve_pts = compute_pr_curve(y_true, y_proba) if y_proba is not None else []
        threshold_pts = compute_threshold_analysis(y_true, y_proba) if y_proba is not None else []
        score_dist_pts = compute_score_distribution(y_true, y_proba) if y_proba is not None else []
        gain_chart_pts = compute_gain_chart(y_true, y_proba) if y_proba is not None else []
        lift_chart_pts = compute_lift_chart(y_true, y_proba) if y_proba is not None else []
    else:
        metrics = compute_regression_metrics(y_true, y_pred)
        hetero_input = y_pred
        roc_curve_pts = pr_curve_pts = threshold_pts = score_dist_pts = gain_chart_pts = lift_chart_pts = []

    hetero_check = compute_heteroscedasticity_check(y_true, hetero_input, task_type=task_type)

    roc_fig = pr_fig = threshold_fig = score_dist_fig = lift_fig = confusion_fig = None
    if task_type == "binary" and y_proba is not None:
        try:
            roc_fig = _figure_json(plot_roc_curve(y_true, y_proba))
            pr_fig = _figure_json(plot_pr_curve(y_true, y_proba))
            threshold_fig = _figure_json(plot_threshold_analysis(y_true, y_proba))
            score_dist_fig = _figure_json(plot_score_distribution(np.asarray(y_true).astype(int), y_proba))
            lift_fig = _figure_json(plot_lift_chart(y_true, y_proba))
        except Exception:
            pass
    if task_type == "binary" and metrics.get("confusion_matrix"):
        try:
            confusion_fig = _figure_json(
                plot_confusion_matrix(metrics["confusion_matrix"], labels=["Non-Default (0)", "Default (1)"])
            )
        except Exception:
            confusion_fig = None

    temporal_analysis = None
    if task_type == "binary" and y_proba is not None and dates is not None:
        try:
            temporal_analysis = compute_temporal_analysis_bundle(
                dates, y_true, y_proba, date_columns=date_columns or [],
            )
        except Exception:
            temporal_analysis = None

    evaluation_data = {
        "metrics": metrics,
        "heteroscedasticity_check": hetero_check,
        "threshold": threshold,
        "threshold_selection": metrics.get("threshold_selection") if task_type == "binary" else None,
        "task_type": task_type,
        "roc_curve": roc_curve_pts,
        "pr_curve": pr_curve_pts,
        "threshold_analysis": threshold_pts,
        "score_distribution": score_dist_pts,
        "gain_chart": gain_chart_pts,
        "lift_chart": lift_chart_pts,
        "roc_curve_figure": roc_fig,
        "pr_curve_figure": pr_fig,
        "confusion_matrix_figure": confusion_fig,
        "threshold_analysis_figure": threshold_fig,
        "score_distribution_figure": score_dist_fig,
        "lift_chart_figure": lift_fig,
        "temporal_analysis": temporal_analysis,
    }
    return metrics, evaluation_data


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
    X_train_before_treatment = X_train.copy()
    imputer = SemanticImputer(
        col_types=col_types_for_fit, treatment_map=treatment_map, strategy_choice=imputation_strategy,
    )
    imputer.fit(X_train)
    X_train = imputer.transform(X_train)
    X_val = imputer.transform(X_val)
    X_test = imputer.transform(X_test)

    missing_before_after: Dict[str, Dict[str, Any]] = {}
    for col in X_train_before_treatment.columns:
        before_count = int(X_train_before_treatment[col].isna().sum())
        if before_count == 0:
            continue
        after_count = int(X_train[col].isna().sum()) if col in X_train.columns else 0
        missing_before_after[col] = {
            "before_missing_count": before_count,
            "before_missing_pct": round(float(X_train_before_treatment[col].isna().mean()), 6),
            "after_missing_count": after_count,
            "after_missing_pct": round(float(X_train[col].isna().mean()), 6) if col in X_train.columns else 0.0,
        }

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

    basic_feature_count = len([
        c for c in feature_names
        if c != target_col and c not in col_types.get("id", []) and str(c).lower() != "id"
    ])
    numeric_feature_count = len([
        c for c in feature_names
        if c != target_col and c not in col_types.get("id", []) and str(c).lower() != "id"
        and c in prep_report.get("numeric", {})
    ])
    categorical_feature_count = len([
        c for c in feature_names
        if c != target_col and c not in col_types.get("id", []) and str(c).lower() != "id"
        and c in prep_report.get("categorical", {})
    ])
    summary_metrics = {
        "features_basic": basic_feature_count,
        "numeric_columns": numeric_feature_count,
        "categorical_columns": categorical_feature_count,
        "boolean_columns": len(prep_report.get("boolean", {})),
        "datetime_columns": len(prep_report.get("datetime", {})),
        "duplicates_removed": clean_info.get("duplicates_removed", 0),
        "ecl_only_cols_dropped": clean_info.get("ecl_only_cols_dropped", []),
    }

    result = {
        "dataset_identity": dataset_identity(df, file, csv_text),
        "col_types": col_types,
        "target_col": target_col,
        "feature_names": feature_names,
        "processed_feature_names": processed_feature_names,
        "x_shape": list(X_train.shape),
        "y_shape": list(y_train.shape),
        "feature_count": X_train.shape[1],
        "numeric_feature_count": len(prep_report.get("numeric", {})),
        "categorical_feature_count": len(prep_report.get("categorical", {})),
        "boolean_feature_count": len(prep_report.get("boolean", {})),
        "datetime_feature_count": len(prep_report.get("datetime", {})),
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
        "missing_before_after": _json_safe(missing_before_after),
        "transform_recommendations": _json_safe(prep_report.get("transform_recommendations", {})),
        "applied_transform_choices": _transform_choices,
        "missing_value_limitation_note": MISSING_VALUE_LIMITATION_NOTE,
        "review_missing_threshold": REVIEW_MISSING_THRESHOLD,
        "original_dataset_csv": df.to_csv(index=False),
    }

    try:
        applied_steps = [t.get("treatment") for t in treatment_map.values()]
        persistence.log_event(
            persistence.DEV_PIPELINE_LOG,
            stage="preprocessing",
            payload={
                "target_col": target_col,
                "steps_applied": sorted(set(applied_steps)),
                "dropped_columns": _drop_cols_present,
                "resulting_x_shape": list(X_train.shape),
                **result.get("dataset_identity", {}),
                "split_config": {"test_size": test_size, "val_size": val_size, "random_seed": random_seed},
            },
            full_payload=result,
        )
    except Exception as e:
        print(f"[persistence] failed to log preprocessing: {e}")

    return result


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
    model_family: str = Form("linear"),
    transform_choices: Optional[str] = Form(None),
    confirmed_remove_cols: Optional[str] = Form(None),
    woe_pending_drop: Optional[str] = Form(None),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
) -> Dict[str, Any]:
    try:
        transform_choices_dict = json.loads(transform_choices) if transform_choices else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"transform_choices must be valid JSON: {exc}")
    try:
        confirmed_remove_cols_list = json.loads(confirmed_remove_cols) if confirmed_remove_cols else None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"confirmed_remove_cols must be valid JSON: {exc}")
    try:
        woe_pending_drop_list = json.loads(woe_pending_drop) if woe_pending_drop else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"woe_pending_drop must be valid JSON: {exc}")

    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    task_type = detect_task_type(df[target_col])
    X, y, _ = finalize_xy(df, col_types, target_col)
    (X_train, X_val, X_test, y_train, y_val, y_test), split_config = _preview_split(
        X, y, task_type, test_size, val_size, random_seed)
    plan = analyze_for_feature_engineering(
        X_train, y_train, col_types, task_type, model_family, transform_choices_dict,
    )
    if confirmed_remove_cols_list is not None:
        plan["confirmed_remove_cols"] = confirmed_remove_cols_list
    plan["woe_pending_drop"] = woe_pending_drop_list
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
    # resolve_ead_configuration() includes a raw pandas Series under "series"
    # for callers that do further pandas math with it (e.g. the Streamlit
    # app's ECL workflow). This API only ever returns "summary" (mean/median/
    # min/max) to the frontend — features.tsx's ead_configuration type doesn't
    # even declare a "series" field — so drop it here rather than at the
    # source, to avoid changing resolve_ead_configuration's contract for other
    # callers. Left in, it makes FastAPI/Pydantic response serialization
    # crash with "Unable to serialize unknown type: <class 'pandas.Series'>".
    ead_configuration = {k: v for k, v in ead_configuration.items() if k != "series"}
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

    result = {
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
        "interaction_features": plan.get("interaction_features", []),
        "interaction_scores": plan.get("interaction_scores", {}),
        "feature_scores": plan.get("feature_scores", {}),
        "transform_recommendations": plan.get("transform_recommendations", {}),
        "split_config": split_config,
        "dataset_identity": dataset_identity(df, file, csv_text),
    }

    try:
        persistence.log_event(
            persistence.DEV_PIPELINE_LOG,
            stage="feature_engineering",
            payload={
                "target_col": target_col,
                "features_added": plan.get("applied_steps", []),
                "features_removed": dropped_features,
                "final_feature_count": len(engineered_feature_names),
                **result["dataset_identity"],
                "split_config": {k: split_config[k] for k in ("test_size", "val_size", "random_seed", "train_index_sha256")},
            },
            full_payload=result,
        )
    except Exception as e:
        print(f"[persistence] failed to log feature_engineering: {e}")

    return result


@app.post("/data/macro/date-columns")
async def macro_date_columns(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    """
    List the columns in the dataset usable for point-in-time FRED macro
    alignment (real dates only, origination-pattern matches first), plus the
    best-effort auto-detected default. Mirrors the old Streamlit app's date
    dropdown (see fred_client.list_date_columns_for_macro/detect_macro_date_col) —
    default/charge-off-dated columns are never auto-selected, even as a fallback.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    candidates = fred_client.list_date_columns_for_macro(df)
    return {
        "candidates": [{"column": c, "is_preferred": pref} for c, pref in candidates],
        "default_date_col": fred_client.detect_macro_date_col(df),
    }


@app.post("/data/macro/fetch")
async def macro_fetch(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    synthetic_samples: Optional[int] = Form(None),
    date_col: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """
    Fetch FRED macro features (GDP, unemployment, Fed funds rate) aligned to
    the calendar month of `date_col` and attach them to the dataset — same
    semantics as the old app's "Fetch FRED macro features" button. Returns the
    augmented dataset as CSV text so the frontend can carry it forward as
    `csv_text` into /data/preprocess and /data/feature-engineering, plus the
    new macro column names for display.

    The FRED API key is configured on the server and read from the
    FRED_API_KEY environment variable. The frontend does not send the API key
    on each request.

    `date_col` is optional: when omitted, the loan-origination date column is
    auto-detected via fred_client.detect_macro_date_col (same heuristic used
    to populate /data/macro/date-columns's default_date_col), so the caller
    doesn't need to resolve it up front.
    """
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "FRED macroeconomic integration is not configured on the server. "
                "Please set the FRED_API_KEY environment variable."
            ),
        )

    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)

    resolved_date_col = date_col or fred_client.detect_macro_date_col(df)
    if not resolved_date_col:
        raise HTTPException(
            status_code=400,
            detail="No origination/observation date column could be auto-detected in this dataset.",
        )
    if resolved_date_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Date column '{resolved_date_col}' not found")

    try:
        client = fred_client.FREDClient(api_key=api_key, cache_dir=".fred_cache")
        df_with_macro, macro_cols = fred_client.attach_macro_features(
            df, fred_client=client, date_col=resolved_date_col,
        )
    except fred_client.FREDError as exc:
        raise HTTPException(status_code=502, detail=f"FRED fetch failed: {exc}")

    if not macro_cols:
        raise HTTPException(status_code=400, detail="No macro columns were attached — check the date column.")

    return {
        "macro_columns": macro_cols,
        "date_col_used": resolved_date_col,
        "csv_with_macro": df_with_macro.to_csv(index=False),
        "preview": _serialize_dataframe(df_with_macro, max_rows=5)["preview"],
        "shape": list(df_with_macro.shape),
    }


@app.post("/data/business-rules/discover")
async def business_rules_discover(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Phase 1 of LLM-assisted business-rule validation (Data Quality).

    Ollama (local only — see business_rules._call_ollama_for_rule_discovery,
    which deliberately does not use llm_providers.complete_with_fallback)
    proposes candidate rules from this dataset's schema/summary metadata only.
    Every proposal is Pydantic-validated and safety-gated before a
    deterministic pandas engine (business_rules._evaluate_rule) — never the
    LLM — computes real rows_checked/violation_count/violation_percentage.
    High-confidence, executable rules are applied automatically; everything
    else is returned as "suggested" or "invalid" for auditability, never
    silently dropped. Fails soft (empty rule set, ollama_available=False) if
    Ollama is unreachable, so this never breaks /data/upload or the Data
    Quality page.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text)
    try:
        return business_rules.discover_and_evaluate_rules(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Business rule discovery failed: {e}")


@app.get("/models/list")
async def list_classification_models() -> Dict[str, Any]:
    """Returns the available classification model keys (e.g. for the Replication
    stage's model selector), independent of any dataset-based recommendation."""
    return {"models": list(CLASSIFICATION_MODELS.keys())}


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
    explainability_priority: float = Form(0.5),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
) -> Dict[str, Any]:
    fe_summary = None
    split_config = None
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
        (X_train, X_val, X_test, y_train, y_val, y_test), split_config = _preview_split(
            X, y, task_type, test_size, val_size, random_seed)

        # Learn FE plan on TRAIN and apply to TRAIN to get the actual feature set
        try:
            plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
            X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
        except Exception:
            # Fallback: no FE applied
            X_train_engineered = X_train.copy()
            fe_summary = None

        # Dataset characteristics feed the weighted recommendation engine —
        # measured on the actual (post-FE) training data, not just its shape.
        characteristics = compute_dataset_characteristics(
            X_train_engineered, y_train, col_types, task_type,
            explainability_priority=explainability_priority,
        )
        n_samples = characteristics["_raw"]["n_samples"]
        n_features = characteristics["_raw"]["n_features"]
        class_imbalance_ratio = characteristics["_raw"]["imbalance_ratio"]
    else:
        if n_samples is None or n_features is None or task_type is None:
            raise HTTPException(status_code=400, detail="Either dataset or numeric summary values are required")
        if class_imbalance_ratio is None:
            class_imbalance_ratio = 1.0
        # No dataset in hand — fall back to a summary-only characteristic set
        # (missingness/categorical share/multicollinearity/non-linearity default
        # to neutral since we can't measure them without the data).
        characteristics = characteristics_from_summary(
            n_samples=n_samples, n_features=n_features, class_imbalance_ratio=class_imbalance_ratio,
            explainability_priority=explainability_priority,
        )

    result = recommend_model(characteristics, task_type=task_type)

    return {
        "recommended_model": result["recommended_model"],
        "all_models": result["all_models"],
        "characteristics": {k: v for k, v in characteristics.items() if k != "_raw"} | {"raw": characteristics.get("_raw", {})},
        "training": {
            "train_n": int(n_samples),
            "train_features": int(n_features),
            "imbalance_ratio": float(class_imbalance_ratio),
        },
        "task_type": task_type,
        "feature_engineering_summary": fe_summary,
        "split_config": split_config,
    }

        
@app.post("/models/train")
async def train_model_endpoint(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    model_name: str = Form(...),
    estimator_name: Optional[str] = Form(None),
    model_owner: Optional[str] = Form(None),
    business_unit: Optional[str] = Form(None),
    model_purpose: Optional[str] = Form(None),
    model_version: Optional[str] = Form(None),
    model_type: Optional[str] = Form(None),
    development_date: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    documentation_path: Optional[str] = Form(None),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    use_cv: bool = Form(False),
    cv_folds: int = Form(5),
    use_hyperopt: bool = Form(False),
    scale_pos_weight: float = Form(1.0),
    manual_params: Optional[str] = Form(None),
    use_feature_engineering: bool = Form(False),
    synthetic_samples: Optional[int] = Form(None),
    use_oot: bool = Form(False),
    date_col: Optional[str] = Form(None),
    threshold: Optional[float] = Form(None),
    treatment_overrides: Optional[str] = Form(None),
    drop_cols: Optional[str] = Form(None),
    transform_choices: Optional[str] = Form(None),
    strategy_override: Optional[str] = Form(None),
    preprocessing_contract: Optional[str] = Form(None),
    split_strategy: str = Form(SPLIT_STRATEGY_STRATIFIED),
    temporal_date_col: Optional[str] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    split_strategy = (split_strategy or SPLIT_STRATEGY_STRATIFIED).strip()
    if split_strategy not in SPLIT_STRATEGIES:
        raise HTTPException(status_code=400, detail=f"split_strategy must be one of {list(SPLIT_STRATEGIES)}.")
    temporal_date_col = (temporal_date_col or "").strip() or None
    if split_strategy == SPLIT_STRATEGY_TEMPORAL:
        if not temporal_date_col:
            raise HTTPException(status_code=400, detail="A temporal split needs temporal_date_col (an explicit date column).")
        if temporal_date_col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Date column '{temporal_date_col}' not found.")
        if temporal_date_col == target_col:
            raise HTTPException(status_code=400, detail="The date column cannot be the target column.")
    elif temporal_date_col:
        raise HTTPException(status_code=400, detail="temporal_date_col is only used with split_strategy='temporal'.")
    if threshold is not None and not (0.0 < float(threshold) < 1.0):
        raise HTTPException(status_code=400, detail="threshold must be between 0 and 1 (exclusive).")
    data_identity = dataset_identity(df, file, csv_text)

    contract_payload = _parse_json_field(preprocessing_contract, {}) if preprocessing_contract else {}
    if not isinstance(contract_payload, dict):
        raise HTTPException(status_code=400, detail="preprocessing_contract must be a JSON object.")

    direct_treatment_overrides = _parse_json_field(treatment_overrides, {}) if treatment_overrides else {}
    direct_drop_cols = _parse_json_field(drop_cols, []) if drop_cols else []
    direct_transform_choices = _parse_json_field(transform_choices, {}) if transform_choices else {}

    contract_treatment_map = _resolve_treatment_map(_coalesce_contract_value(contract_payload, "applied_treatment_map", "treatment_map"))
    contract_drop_cols = _coalesce_contract_value(contract_payload, "dropped_columns", "drop_cols") or []
    contract_transform_choices = _coalesce_contract_value(contract_payload, "applied_transform_choices", "transform_choices") or {}
    contract_strategy_override = _coalesce_contract_value(contract_payload, "strategy_override")

    combined_treatment_overrides = {
        **_resolve_treatment_map(direct_treatment_overrides),
        **contract_treatment_map,
    }
    combined_drop_cols = list(dict.fromkeys([
        *([c for c in direct_drop_cols if isinstance(c, str)]),
        *([c for c in contract_drop_cols if isinstance(c, str)]),
    ]))
    combined_transform_choices = {**(direct_transform_choices if isinstance(direct_transform_choices, dict) else {}), **(contract_transform_choices if isinstance(contract_transform_choices, dict) else {})}
    combined_strategy_override = contract_strategy_override or strategy_override

    if manual_params:
        try:
            manual_params_dict = json.loads(manual_params)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"manual_params must be valid JSON: {exc}")
    else:
        manual_params_dict = None

    business_model_name = model_name.strip()
    estimator_name = (estimator_name or model_name).strip() or model_name

    # The training path itself lives in model_lineage.fit_training_pipeline
    # (moved verbatim) so registered-model reproduction re-runs exactly the
    # same code. Everything below consumes the same variables as before.
    try:
        fit = model_lineage.fit_training_pipeline(
            df,
            target_col=target_col,
            model_name=model_name,
            estimator_name=estimator_name,
            test_size=test_size,
            val_size=val_size,
            random_seed=random_seed,
            use_cv=use_cv,
            cv_folds=cv_folds,
            use_hyperopt=use_hyperopt,
            scale_pos_weight=scale_pos_weight,
            manual_params_dict=manual_params_dict,
            use_feature_engineering=use_feature_engineering,
            use_oot=use_oot,
            date_col=date_col,
            contract_payload=contract_payload,
            combined_treatment_overrides=combined_treatment_overrides,
            combined_drop_cols=combined_drop_cols,
            combined_transform_choices=combined_transform_choices,
            combined_strategy_override=combined_strategy_override,
            split_strategy=split_strategy,
            temporal_date_col=temporal_date_col,
        )
    except ValueError as exc:
        # Temporal split preconditions (unparseable dates, too few rows).
        if split_strategy == SPLIT_STRATEGY_TEMPORAL and ("emporal" in str(exc) or "date" in str(exc)):
            raise HTTPException(status_code=400, detail=str(exc))
        raise
    col_types = fit["col_types"]
    task_type = fit["task_type"]
    X_train, X_val, X_test = fit["X_train"], fit["X_val"], fit["X_test"]
    y_train, y_val, y_test = fit["y_train"], fit["y_val"], fit["y_test"]
    effective_preprocessing_contract = fit["effective_preprocessing_contract"]
    origination_date_col = fit["origination_date_col"]
    dates_test = fit["dates_test"]
    prep_report = fit["prep_report"]
    plan = fit["plan"]
    fe_summary = fit["fe_summary"]
    manual_params_dict = fit["manual_params_dict"]
    model = fit["model"]
    pipeline = fit["pipeline"]
    training_info = fit["training_info"]
    real_feature_names = fit["real_feature_names"]
    split_stats = compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test)

    # Evaluate on hold-out test set to mirror the original Streamlit training workflow.
    y_pred = pipeline.predict(X_test)
    y_proba = None
    if hasattr(pipeline, "predict_proba"):
        try:
            y_proba = pipeline.predict_proba(X_test)
        except Exception:
            y_proba = None

    # Operating threshold: the user's value, or chosen on the VALIDATION
    # partition; the test rows are only scored with it (E3).
    threshold_provenance = None
    if task_type == "binary":
        proba_val = None
        if hasattr(pipeline, "predict_proba"):
            try:
                proba_val = pipeline.predict_proba(X_val)
            except Exception:
                proba_val = None
        threshold_provenance = select_operating_threshold(y_val.values, proba_val, manual=threshold)
    operating_threshold_value = threshold_provenance["value"] if threshold_provenance else threshold

    metrics, evaluation_data = _build_evaluation_data(
        y_test.values, y_pred, y_proba, task_type, threshold=operating_threshold_value,
        dates=dates_test, date_columns=[origination_date_col] if origination_date_col else [],
    )
    metrics["evaluation_partition"] = "test"
    evaluation_data["evaluation_partition"] = "test"
    if threshold_provenance:
        metrics["threshold_provenance"] = threshold_provenance
        evaluation_data["threshold_provenance"] = threshold_provenance

    # Additional dataset / preprocessing metadata computed by the pipeline
    numeric_count = len(col_types.get("numeric", [])) if isinstance(col_types, dict) else None
    categorical_count = len(col_types.get("categorical", [])) if isinstance(col_types, dict) else None
    missing_value_count = int(df.isna().sum().sum()) if df is not None else None
    missing_value_pct = float(df.isna().mean().mean() * 100) if df is not None else None
    duplicate_count = int(df.duplicated().sum()) if df is not None else None
    class_distribution = None
    try:
        class_distribution = (df[target_col].value_counts(normalize=True).to_dict() if (df is not None and target_col in df.columns) else None)
    except Exception:
        class_distribution = None

    preprocessing_summary = prep_report if isinstance(prep_report, dict) else None
    training_contract = {
        **effective_preprocessing_contract,
        "contract_applied": effective_preprocessing_contract["source"] == "data_preparation",
    }

    encoding = {}
    scaling = {}
    try:
        if isinstance(prep_report, dict):
            for c, info in (prep_report.get("categorical", {}) or {}).items():
                encoding[c] = info.get("encoding")
            scaling = prep_report.get("transform_recommendations") or {}
    except Exception:
        encoding = {}
        scaling = {}

    feature_selection = {
        "low_iv_cols": plan.get("low_iv_cols", []) if plan else [],
        "low_variance_cols": plan.get("low_variance_cols", []) if plan else [],
        "dropped_high_corr_pairs": plan.get("drop_high_corr_pairs", []) if plan else [],
    }

    result = {
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
            "scale_pos_weight": scale_pos_weight,
            "use_feature_engineering": use_feature_engineering,
            "manual_params": manual_params_dict or {},
            "use_oot": use_oot,
            "date_col": origination_date_col,
            "split_strategy": split_strategy,
            "temporal_date_col": temporal_date_col,
            "threshold": operating_threshold_value,
            "threshold_mode": "manual" if threshold is not None else "auto_validation",
        },
        "split_report": fit["split_report"],
        "threshold_provenance": threshold_provenance,
        "dataset_identity": data_identity,
        "training_info": {
            **training_info,
            "preprocessing_contract_used": training_contract,
        },
        "split_stats": split_stats,
        "feature_engineering_summary": fe_summary,
        "feature_selection": feature_selection,
        "preprocessing_summary": preprocessing_summary,
        "preprocessing_contract": training_contract,
        "encoding": encoding,
        "scaling": scaling,
        "low_iv_columns": plan.get("low_iv_cols", []) if plan else [],
        "low_variance_columns": plan.get("low_variance_cols", []) if plan else [],
        "dropped_high_corr_pairs": plan.get("drop_high_corr_pairs", []) if plan else [],
        "applied_steps": plan.get("applied_steps", []) if plan else [],
        "evaluation_metrics": metrics,
        "evaluation_data": evaluation_data,
        "numeric_column_count": numeric_count,
        "categorical_column_count": categorical_count,
        "missing_value_count": missing_value_count,
        "missing_value_pct": missing_value_pct,
        "duplicate_record_count": duplicate_count,
        "class_distribution": class_distribution,
        "model_artifact": _to_base64(pipeline),
    }

    try:
        print(f"[registration-flow] entered registration try block for model: {business_model_name}")
        # Record training artifact and capture run id so we can update
        # the artifact with the assigned development `model_id` after
        # registration.
        run_id = persistence.log_event(
            persistence.DEV_PIPELINE_LOG,
            stage="training",
            payload={
                "model_name": model_name,
                "business_model_name": business_model_name,
                "hyperparameters": manual_params_dict or {},
                "metrics": metrics,
                **data_identity,
                "split_strategy": split_strategy,
                "split_degraded": bool((fit["split_report"] or {}).get("degraded")),
                "operating_threshold": operating_threshold_value,
                "threshold_method": (threshold_provenance or {}).get("method"),
            },
            full_payload=result,
        )
        result["training_run_id"] = run_id
        # Immediate -- ensure registration is attempted right after artifact creation.
        try:
            early_store = persistence.load_model_inventory()
            early_reg = persistence.register_development_model(
                store=early_store,
                business_model_name=business_model_name,
                estimator_name=estimator_name,
                intake_payload={
                    "model_owner": model_owner,
                    "business_unit": business_unit,
                    "model_purpose": model_purpose,
                    "model_version": model_version,
                    "development_date": development_date,
                    "status": status,
                    "training_info": training_info,
                    "split_stats": split_stats,
                    "evaluation_metrics": metrics,
                },
                dataset_payload={
                    "file_name": getattr(file, "filename", None) or "uploaded_dataset",
                    "storage_reference": getattr(file, "filename", None) or "",
                    "record_count": int(df.shape[0]) if df is not None else None,
                    "column_count": int(df.shape[1]) if df is not None else None,
                    "numeric_column_count": numeric_count,
                    "categorical_column_count": categorical_count,
                    "missing_value_count": missing_value_count,
                    "missing_value_pct": missing_value_pct,
                    "duplicate_record_count": duplicate_count,
                    "class_distribution": class_distribution,
                    "target_variable": target_col,
                    "uploaded_by": model_owner or "user",
                    "uploaded_at": pd.Timestamp.now().isoformat(),
                },
                user=model_owner or "user",
            )
            try:
                # Persist inventory and update artifact immediately
                persistence.save_model_inventory(early_store)
            except Exception:
                pass
            if isinstance(early_reg, dict) and early_reg.get("model_id"):
                # Returned to the caller only; the training artifact is immutable.
                result["model_id"] = early_reg.get("model_id")
        except Exception as _e:
            try:
                import traceback
                print(f"[registration] immediate registration attempt failed: {_e}")
                traceback.print_exc()
            except Exception:
                print(f"[registration] immediate registration failed: {_e}")
    except Exception as e:
        print(f"[persistence] failed to log training: {e}")

    try:
        print(f"[registration-flow] entering post-artifact registration flow for model: {business_model_name}")
        store = persistence.load_model_inventory()
        # Collect additional dataset and preprocessing metadata from the
        # existing pipeline outputs so the Development Inventory captures
        # the real values already computed during training.
        numeric_count = len(col_types.get("numeric", [])) if isinstance(col_types, dict) else None
        categorical_count = len(col_types.get("categorical", [])) if isinstance(col_types, dict) else None
        missing_value_count = int(df.isna().sum().sum()) if df is not None else None
        missing_value_pct = float(df.isna().mean().mean() * 100) if df is not None else None
        duplicate_count = int(df.duplicated().sum()) if df is not None else None
        class_distribution = None
        try:
            class_distribution = (df[target_col].value_counts(normalize=True).to_dict() if (df is not None and target_col in df.columns) else None)
        except Exception:
            class_distribution = None

        date_min = date_max = None
        if origination_date_col and origination_date_col in df.columns:
            try:
                s = pd.to_datetime(df[origination_date_col], errors="coerce")
                date_min = str(s.min()) if not s.min() is pd.NaT else None
                date_max = str(s.max()) if not s.max() is pd.NaT else None
            except Exception:
                date_min = date_max = None

        # Preprocessing summary is available from `prep_report` passed to train_model
        preprocessing_summary = prep_report if isinstance(prep_report, dict) else None

        # Encoding / scaling summaries
        encoding = {}
        scaling = {}
        try:
            if isinstance(prep_report, dict):
                for c, info in (prep_report.get("categorical", {}) or {}).items():
                    encoding[c] = info.get("encoding")
                # transform recommendations indicate scaling/transform choices
                scaling = prep_report.get("transform_recommendations") or {}
        except Exception:
            encoding = {}
            scaling = {}

        # Feature selection / FE artifacts
        feature_selection = {
            "low_iv_cols": plan.get("low_iv_cols", []) if plan else [],
            "low_variance_cols": plan.get("low_variance_cols", []) if plan else [],
            "dropped_high_corr_pairs": plan.get("drop_high_corr_pairs", []) if plan else [],
        }

        # Feature importance (cheap) — extract real names + normalized importances
        try:
            importance_df = extract_feature_importance(pipeline)
            feature_importances = importance_df.to_dict(orient="records") if importance_df is not None else None
            top_model_drivers = [r.get("Feature") for r in (feature_importances or [])[:10]] if feature_importances else None
        except Exception:
            feature_importances = None
            top_model_drivers = None

        # Register the development model and capture the returned id/name
        try:
            print(f"[registration] attempting to register development model: {business_model_name}")
            reg_result = persistence.register_development_model(
                store=store,
                business_model_name=business_model_name,
                estimator_name=estimator_name,
                intake_payload={
                    "model_owner": model_owner,
                    "business_unit": business_unit,
                    "model_purpose": model_purpose,
                    "model_version": model_version,
                    "model_type": model_type,
                    "development_date": development_date,
                    "status": status,
                    "documentation_path": documentation_path,
                    "training_info": training_info,
                    "split_stats": split_stats,
                    "feature_engineering_summary": fe_summary,
                    "evaluation_metrics": metrics,
                    "real_feature_names": real_feature_names,
                    "preprocessing_summary": preprocessing_summary,
                    "encoding": encoding,
                    "scaling": scaling,
                    "feature_selection": feature_selection,
                    "feature_importances": feature_importances,
                    "top_model_drivers": top_model_drivers,
                    "training_config": result.get("training_config", {}),
                },
                dataset_payload={
                    "file_name": getattr(file, "filename", None) or "uploaded_dataset",
                    "storage_reference": getattr(file, "filename", None) or "",
                    "source_type": "file",
                    "purpose": "Development dataset",
                    "record_count": int(df.shape[0]) if df is not None else None,
                    "column_count": int(df.shape[1]) if df is not None else None,
                    "numeric_column_count": numeric_count,
                    "categorical_column_count": categorical_count,
                    "missing_value_count": missing_value_count,
                    "missing_value_pct": missing_value_pct,
                    "duplicate_record_count": duplicate_count,
                    "class_distribution": class_distribution,
                    "date_min": date_min,
                    "date_max": date_max,
                    "target_variable": target_col,
                    "uploaded_by": model_owner or "user",
                    "uploaded_at": pd.Timestamp.now().isoformat(),
                },
                user=model_owner or "user",
            )
        except Exception as reg_exc:
            # Do NOT silently swallow registration failures — log full traceback
            try:
                import traceback
                print(f"[registration] registration FAILED for model {business_model_name}: {reg_exc}")
                traceback.print_exc()
                # also persist a short diagnostic so tests / CI can inspect it
                try:
                    (persistence.APP_DATA_DIR / "last_development_registration_error.json").write_text(
                        json.dumps({"model_name": business_model_name, "error": str(reg_exc)}, default=str, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
            except Exception:
                # best-effort logging; never mask the original exception output
                print(f"[registration] registration error: {reg_exc}")
            # allow flow to continue; reg_result will be undefined or None
            reg_result = None

        # Find the created/updated entry in the in-memory store
        created_entry = None
        try:
            mid = reg_result.get("model_id") if isinstance(reg_result, dict) else None
            created_entry = next((m for m in store.get("development", []) if m.get("model_id") == mid), None) if mid else None
        except Exception:
            created_entry = None

        # Lineage capture for registered-model reproduction: save the fitted
        # scoring chain (with SHA-256) and record the full training contract
        # on the registered inventory entry. On failure the entry carries the
        # error and NO contract, so a stale contract from an earlier training
        # of the same model can never be reused for this one.
        lineage_status: Dict[str, Any] = {"captured": False, "reason": None}
        try:
            lineage_model_id = reg_result.get("model_id") if isinstance(reg_result, dict) else None
            if created_entry is not None and lineage_model_id and run_id:
                lineage_artifact = model_lineage.save_scoring_bundle(fit, model_id=lineage_model_id, training_run_id=run_id)
                created_entry["lineage_contract"] = model_lineage.build_lineage_contract(
                    fit,
                    model_id=lineage_model_id,
                    training_run_id=run_id,
                    business_model_name=business_model_name,
                    estimator_name=estimator_name,
                    target_col=target_col,
                    dataset_name=getattr(file, "filename", None),
                    dataset_sha256=dataset_fingerprint(df),
                    dataset_shape=[int(df.shape[0]), int(df.shape[1])],
                    training_config=result.get("training_config", {}),
                    threshold=operating_threshold_value,
                    threshold_provenance=threshold_provenance,
                    development_metrics=metrics,
                    artifact=lineage_artifact,
                )
                created_entry["lineage_contract"]["dataset"]["file_sha256"] = data_identity["dataset_file_sha256"]
                created_entry.pop("lineage_contract_error", None)
                lineage_status = {
                    "captured": True,
                    "contract_version": model_lineage.LINEAGE_CONTRACT_VERSION,
                    "training_run_id": run_id,
                    "artifact_sha256": lineage_artifact["sha256"],
                }
            else:
                lineage_status["reason"] = "Model was not registered, so its lineage could not be recorded."
                # A same-named entry may still carry the contract of an EARLIER
                # training. This retrain was not registered, so that contract no
                # longer describes the current model — withdraw it rather than
                # let a later reproduction validate the wrong training.
                for stale_entry in store.get("development", []):
                    if isinstance(stale_entry, dict) and str(stale_entry.get("model_name") or "").strip().casefold() == business_model_name.casefold():
                        if stale_entry.pop("lineage_contract", None) is not None:
                            stale_entry["lineage_contract_error"] = (
                                "Model was retrained but the new training could not be registered; the previous "
                                "lineage contract was withdrawn because it no longer describes the current model."
                            )
        except Exception as lineage_exc:
            if created_entry is not None:
                created_entry.pop("lineage_contract", None)
                created_entry["lineage_contract_error"] = f"{type(lineage_exc).__name__}: {lineage_exc}"
            lineage_status["reason"] = f"Lineage capture failed: {type(lineage_exc).__name__}: {lineage_exc}"
            print(f"[lineage] capture failed for {business_model_name}: {lineage_exc}")
        result["lineage"] = lineage_status

        # Log inventory path and counts immediately before saving
        try:
            inv_path = persistence.get_model_inventory_path()
            before_count = len(store.get("development", []))
            print(f"[registration] inventory_path: {inv_path.resolve()}")
            print(f"[registration] before_development_count: {before_count}")
            print(f"[registration] generated_model_id: {reg_result.get('model_id') if isinstance(reg_result, dict) else None}")
            print(f"[registration] generated_model_name: {reg_result.get('model_name') if isinstance(reg_result, dict) else business_model_name}")
        except Exception as _e:
            print(f"[registration] pre-save logging failed: {_e}")

        # Persist inventory (may raise) and log afterwards
        try:
            persistence.save_model_inventory(store)
            after_count = len(store.get("development", []))
            print(f"[registration] after_development_count: {after_count}")
            print(f"[registration] save_model_inventory succeeded: {inv_path.resolve()}")
        except Exception as e:
            print(f"[registration] save_model_inventory FAILED: {e}")
            raise

        # Registration is recorded as its OWN event linking the model ID to
        # the training run. The training artifact is never rewritten, so the
        # SHA-256 recorded when it was created stays verifiable (E9).
        try:
            if isinstance(reg_result, dict) and run_id and reg_result.get("model_id"):
                assigned_id = reg_result.get("model_id")
                result["model_id"] = assigned_id
                if created_entry and created_entry.get("documentation_path"):
                    result["documentation_path"] = created_entry.get("documentation_path")
                training_row = persistence.get_run(persistence.DEV_PIPELINE_LOG, run_id) or {}
                registration_record = {
                    "registered_model_id": assigned_id,
                    "training_run_id": run_id,
                    "business_model_name": business_model_name,
                    "training_artifact_sha256": (training_row.get("summary") or {}).get("artifact_sha256"),
                    "lineage_captured": bool(lineage_status.get("captured")),
                    "bundle_sha256": lineage_status.get("artifact_sha256"),
                    "documentation_path": result.get("documentation_path"),
                    **data_identity,
                }
                result["registration_run_id"] = persistence.log_event(
                    persistence.DEV_PIPELINE_LOG,
                    stage="registration",
                    payload=registration_record,
                    full_payload=registration_record,
                )
        except Exception as _e:
            print(f"[registration] failed to log registration event: {_e}")
    except Exception as e:
        import traceback
        print(f"[persistence] failed to update inventory from development: {e}")
        traceback.print_exc()

    return result


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
        X_val, _ = apply_feature_engineering(X_val, plan)
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
                # Each candidate's threshold is chosen on the validation rows,
                # then applied unchanged to the test rows (E3).
                proba_val = None
                try:
                    proba_val = pipeline.predict_proba(X_val) if y_proba is not None else None
                except Exception:
                    proba_val = None
                provenance = select_operating_threshold(y_val.values, proba_val)
                metrics = compute_binary_metrics(y_test.values, y_pred, y_proba, threshold=provenance["value"])
                metrics["threshold_provenance"] = provenance
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
        "split_config": {"test_size": test_size, "val_size": val_size, "random_seed": random_seed,
                         "strategy": SPLIT_STRATEGY_STRATIFIED},
        "evaluation_partition": "test",
    }


EVAL_PARTITION_TEST = "test"
EVAL_PARTITION_VALIDATION = "validation"
EVAL_PARTITION_INDEPENDENT = "independent"
EVAL_PARTITIONS = (EVAL_PARTITION_TEST, EVAL_PARTITION_VALIDATION, EVAL_PARTITION_INDEPENDENT)


def _evaluation_rows(resolved: Dict[str, Any], df: pd.DataFrame, target_col: str, partition: Optional[str],
                     independent_reason: Optional[str], *, file=None, csv_text=None) -> Dict[str, Any]:
    """The rows a registered model may be evaluated on, scored through its
    verified bundle, and the identity of that evaluation. Never the training
    rows: in-sample requests fail with 409."""
    partition = (partition or EVAL_PARTITION_TEST).strip().lower()
    if partition not in EVAL_PARTITIONS:
        raise HTTPException(status_code=400, detail=f"evaluation_partition must be one of {list(EVAL_PARTITIONS)}.")
    contract = resolved["contract"]
    model_id = resolved["model_id"]
    identity = dataset_identity(df, file, csv_text)
    training_sha = (contract.get("dataset") or {}).get("sha256")
    if contract.get("target_col") and contract["target_col"] != target_col:
        raise HTTPException(status_code=409, detail=(
            f"target_mismatch: {model_id} was trained on target '{contract['target_col']}', not '{target_col}'."))
    reason = (independent_reason or "").strip() or None
    if partition == EVAL_PARTITION_INDEPENDENT:
        if not reason:
            raise HTTPException(status_code=400, detail=(
                "independent_dataset_reason is required: document why this dataset is independent of the training data."))
        if not training_sha:
            raise HTTPException(status_code=409, detail=(
                f"independence_unverifiable: {model_id}'s training dataset fingerprint is not recorded, so this "
                "dataset cannot be shown to differ from the training data."))
        if identity["dataset_sha256"] == training_sha:
            raise HTTPException(status_code=409, detail=(
                f"in_sample: the supplied dataset is {model_id}'s training dataset. Evaluate its recorded "
                "'test' or 'validation' partition instead."))
        index = df.index
        raw = df.drop(columns=[target_col], errors="ignore")
    else:
        if not training_sha or identity["dataset_sha256"] != training_sha:
            raise HTTPException(status_code=409, detail=(
                f"dataset_mismatch: the '{partition}' partition exists only in {model_id}'s training dataset "
                f"({(contract.get('dataset') or {}).get('name')}). For another dataset use "
                "evaluation_partition='independent' with a documented reason."))
        try:
            (Xtr, Xv, Xte, _ytr, _yv, _yte), _rep = model_lineage.contract_split(df, contract)
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"split_unavailable: the recorded split could not be re-derived ({exc}).")
        if model_lineage.index_fingerprint(Xte.index) != (contract.get("split") or {}).get("test_index_sha256"):
            raise HTTPException(status_code=409, detail="split_mismatch: the recorded test rows could not be reproduced.")
        raw = Xte if partition == EVAL_PARTITION_TEST else Xv
        index = raw.index
    try:
        X = model_lineage._transform_for_bundle(resolved["bundle"], raw)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=f"feature_mismatch: the dataset lacks the model's input columns ({exc}).")
    scope = {
        "partition": partition,
        "in_sample": False,
        "registered_model_id": model_id,
        "training_run_id": contract.get("training_run_id"),
        "bundle_sha256": (contract.get("artifact") or {}).get("sha256"),
        "dataset_sha256": identity["dataset_sha256"],
        "dataset_file_sha256": identity["dataset_file_sha256"],
        "training_dataset_sha256": training_sha,
        "rows": int(len(index)),
        "row_index_sha256": model_lineage.index_fingerprint(index),
        "independent_dataset_reason": reason if partition == EVAL_PARTITION_INDEPENDENT else None,
        "limitations": ([
            "Row-level overlap with the training data cannot be checked (training rows are not stored); "
            "independence rests on the documented reason and a different dataset fingerprint."]
            if partition == EVAL_PARTITION_INDEPENDENT else []),
    }
    return {"index": index, "X": X, "scope": scope}


@app.post("/models/evaluate")
async def evaluate_model(
    # Kept in the signature for compatibility only — never read or deserialized.
    model_artifact: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    threshold: Optional[float] = Form(None),
    synthetic_samples: Optional[int] = Form(None),
    date_col: Optional[str] = Form(None),
    registered_model_id: Optional[str] = Form(None),
    evaluation_partition: str = Form(EVAL_PARTITION_TEST),
    independent_dataset_reason: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Score the registered model identified by `registered_model_id`, loaded
    from its verified scoring bundle. Uploaded model artifacts are rejected.

    Out-of-sample only (E8): `evaluation_partition` is
      - "test" (default) / "validation": the registered model's own recorded
        partition, re-derived from its lineage contract; the supplied data
        must be its training dataset;
      - "independent": a different dataset, with a documented reason. The
        training dataset itself is refused (in-sample).
    The operating threshold is the registered one unless `threshold` is given
    (recorded as a manual override)."""
    resolved = _resolve_registered_pipeline(registered_model_id, model_artifact is not None)
    pipeline = resolved["bundle"]["pipeline"]
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    scope_rows = _evaluation_rows(resolved, df, target_col, evaluation_partition, independent_dataset_reason,
                                  file=file, csv_text=csv_text)
    eval_index = scope_rows["index"]
    y_true = df.loc[eval_index, target_col].values
    X_eval = scope_rows["X"]
    if threshold is not None:
        if not (0.0 < float(threshold) < 1.0):
            raise HTTPException(status_code=400, detail="threshold must be between 0 and 1 (exclusive).")
        threshold_info = {"value": float(threshold), "status": "MANUAL_OVERRIDE",
                          "provenance": select_operating_threshold(None, None, manual=float(threshold)),
                          "detail": "Reviewer-specified threshold; not the registered model's operating threshold."}
    else:
        threshold_info = model_lineage.operating_threshold(resolved["contract"])
    threshold = threshold_info["value"]
    y_pred = pipeline.predict(X_eval)
    y_proba = None
    if hasattr(pipeline, "predict_proba"):
        try:
            y_proba = pipeline.predict_proba(X_eval)
        except Exception:
            y_proba = None
    task_type = detect_task_type(df[target_col])
    # Same origination-date resolution as /models/train: reviewer-selected
    # column if valid, else the first auto-detected datetime column — used
    # to power the Temporal tab's actual-vs-predicted-over-time analysis.
    col_types = detect_column_types(df)
    origination_date_col = date_col if (date_col and date_col in df.columns) else None
    if origination_date_col is None:
        datetime_candidates = col_types.get("datetime", [])
        if datetime_candidates:
            origination_date_col = datetime_candidates[0]
    dates_eval = df.loc[eval_index, origination_date_col] if origination_date_col else None

    metrics, evaluation_data = _build_evaluation_data(
        y_true, y_pred, y_proba, task_type, threshold=threshold,
        dates=dates_eval, date_columns=[origination_date_col] if origination_date_col else [],
    )
    evaluation_scope = {
        **scope_rows["scope"],
        "operating_threshold": threshold,
        "threshold_status": threshold_info["status"],
        "threshold_detail": threshold_info["detail"],
        "threshold_provenance": threshold_info.get("provenance"),
    }
    metrics["evaluation_partition"] = evaluation_scope["partition"]
    evaluation_data["evaluation_scope"] = evaluation_scope

    # Same response shape as /models/train so callers can treat both
    # endpoints' evaluation payload identically.
    result = {
        "evaluation_metrics": metrics,
        "evaluation_data": evaluation_data,
        "evaluation_scope": evaluation_scope,
    }

    try:
        persistence.log_event(
            persistence.DEV_PIPELINE_LOG,
            stage="evaluation",
            payload={
                "evaluation_metrics": metrics,
                "registered_model_id": evaluation_scope["registered_model_id"],
                "training_run_id": evaluation_scope["training_run_id"],
                "evaluation_partition": evaluation_scope["partition"],
                "dataset_sha256": evaluation_scope["dataset_sha256"],
                "dataset_file_sha256": evaluation_scope["dataset_file_sha256"],
                "row_index_sha256": evaluation_scope["row_index_sha256"],
                "operating_threshold": threshold,
                "threshold_status": threshold_info["status"],
            },
            full_payload=result,
        )
    except Exception as e:
        print(f"[persistence] failed to log evaluation: {e}")

    return result


@app.post("/models/explain")
async def explain_model(
    # Kept in the signature for compatibility only — never read or deserialized.
    model_artifact: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: Optional[str] = Form(None),
    max_shap_samples: int = Form(100),
    sample_idx: int = Form(0),
    synthetic_samples: Optional[int] = Form(None),
    # ── Same fields /models/train already returns in training_config — needed
    #    to deterministically re-derive the EXACT engineered test split the
    #    model was fitted on. Without this, X came straight from the raw
    #    upload, whose columns don't match what the fitted preprocessor
    #    expects whenever use_feature_engineering was True at train time
    #    (bin/WOE/interaction columns are missing) — this is what caused
    #    "SHAP computation failed" for every model type, not just non-tree
    #    ones. Mirrors the old Streamlit app's use of X_test_engineered. ──
    use_feature_engineering: bool = Form(False),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    # ── Summary tab: same inputs generate_model_summary() takes in the old app ──
    metrics: Optional[str] = Form(None),
    task_type: Optional[str] = Form(None),
    # Feature importance is cheap and shown immediately in the old UI; SHAP
    # (especially KernelExplainer, nsamples=100) is not, and is only computed
    # on an explicit "Compute SHAP Values" click there. Default True keeps
    # existing callers working; the frontend passes False for the initial
    # Feature-Importance-only load.
    compute_shap: bool = Form(True),
    # The model to explain: an exact registered model ID. The server loads its
    # verified scoring bundle; uploaded artifacts are rejected.
    registered_model_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    resolved = _resolve_registered_pipeline(registered_model_id, model_artifact is not None)
    pipeline = resolved["bundle"]["pipeline"]
    contract = resolved["contract"]
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    if target_col is not None and target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")

    # E6 — explain exactly the registered model (its verified bundle) on
    # exactly identified rows, through exactly the registered scoring chain:
    #   training dataset → its recorded test rows (same rows as the registered
    #                      test evaluation; a split that does not reproduce is
    #                      refused, never replaced by other rows);
    #   other dataset    → the supplied rows, reduced to the raw feature
    #                      columns recorded at training, in recorded order.
    #                      Missing columns are refused; nothing is imputed or
    #                      reconstructed to stand in for them.
    # Then the bundle's dropped columns → imputer → feature engineering →
    # model-input column order, and the pipeline (encoding/scaling → model).
    identity = dataset_identity(df, file, csv_text)
    training_sha = (contract.get("dataset") or {}).get("sha256")
    split = contract.get("split") or {}
    if training_sha and identity["dataset_sha256"] == training_sha and split.get("test_index_sha256"):
        try:
            (_xtr, _xv, raw, _ytr, _yv, _yte), _rep = model_lineage.contract_split(df, contract)
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"split_unavailable: the recorded split could not be re-derived ({exc}).")
        if model_lineage.index_fingerprint(raw.index) != split["test_index_sha256"]:
            raise HTTPException(status_code=409, detail="split_mismatch: the recorded test rows could not be reproduced.")
        explain_rows = "registered_test_partition"
    else:
        raw_columns = list((contract.get("features") or {}).get("raw_feature_columns") or [])
        if not raw_columns:
            raise HTTPException(status_code=409, detail=(
                "explain_inputs_unverifiable: the lineage contract does not record the model's raw feature columns, "
                "so the supplied rows cannot be matched to the registered model's inputs."))
        missing = [c for c in raw_columns if c not in df.columns]
        if missing:
            raise HTTPException(status_code=409, detail=(
                f"feature_mismatch: the dataset lacks the registered model's raw input columns {missing}."))
        raw = df[raw_columns]
        explain_rows = "supplied_dataset"
    try:
        X_explain = model_lineage._transform_for_bundle(resolved["bundle"], raw)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=f"feature_mismatch: the dataset lacks the model's input columns ({exc}).")

    # The probabilities every per-row output uses: the registered pipeline on
    # exactly these rows. Their hash is recorded so parity can be checked.
    proba_2d = np.asarray(pipeline.predict_proba(X_explain))
    proba = np.ascontiguousarray(proba_2d[:, 1], dtype=np.float64)
    op = model_lineage.operating_threshold(contract)
    threshold_source = (
        f"{(op.get('provenance') or {}).get('method')} on {(op.get('provenance') or {}).get('source_partition')}"
        if op["status"] == "PASS" else
        "nominal 0.5, not the model's recorded threshold" if op["status"] == "FAIL" else
        "recorded without its selection method")

    importance_df, importance_reason = feature_importance_with_reason(pipeline)
    importance = importance_df.to_dict(orient="records") if importance_df is not None else []

    shap_info: Dict[str, Any] = {"shap_available": False, "shap_unavailable_reason": None if compute_shap else "Not requested."}
    shap_result = None
    if compute_shap:
        shap_result, shap_reason = compute_shap_values_with_reason(pipeline, X_explain, max_samples=max_shap_samples)
        shap_info["shap_unavailable_reason"] = shap_reason
    if shap_result is not None:
        explainer, shap_values, X_df, names = shap_result
        # SHAP explains the first len(X_df) rows of X_explain, in order.
        explained_index = list(X_explain.index[:len(X_df)])
        if not (0 <= sample_idx < len(X_df)):
            raise HTTPException(status_code=400, detail=f"sample_idx must be between 0 and {len(X_df) - 1} (rows explained).")
        mean_abs = list(
            pd.DataFrame({"Feature": X_df.columns, "MeanAbsSHAP": np.abs(shap_values).mean(axis=0)})
            .sort_values("MeanAbsSHAP", ascending=False)
            .head(20)
            .to_dict(orient="records")
        )
        reasoning = generate_prediction_reasoning(shap_values, X_df, proba_2d[:len(X_df)], sample_idx,
                                                  threshold=op["value"], threshold_source=threshold_source)
        shap_row = shap_values[sample_idx]
        feat_row = X_df.iloc[sample_idx]
        # Top 12 by |SHAP| magnitude, then re-sorted ascending by signed
        # value — the explainability chart renders this list top-to-bottom
        # as-is (no further sort/slice on the frontend), so ordering here
        # is what determines the bar chart's reading order.
        sample_shap = sorted(
            sorted(
                (
                    {
                        "Feature": feat,
                        "SHAP": _json_safe_scalar(shap_row[i]),
                        "Value": _json_safe_scalar(feat_row.iloc[i]),
                    }
                    for i, feat in enumerate(X_df.columns)
                ),
                key=lambda r: abs(r["SHAP"]) if r["SHAP"] is not None else 0.0,
                reverse=True,
            )[:12],
            key=lambda r: r["SHAP"] if r["SHAP"] is not None else 0.0,
        )
        shap_info = {
            "shap_available": True,
            "shap_unavailable_reason": None,
            "shap_mean_abs": mean_abs,
            "sample_idx": sample_idx,
            "sample_row_index": _json_safe_scalar(explained_index[sample_idx]),
            "sample_predicted_pd": float(proba[sample_idx]),
            "explained_rows": int(len(X_df)),
            "explained_row_index": [_json_safe_scalar(i) for i in explained_index],
            "sample_reasoning": reasoning,
            "sample_shap": sample_shap,
            "sample_features": {feat: _json_safe_scalar(feat_row.iloc[i]) for i, feat in enumerate(X_df.columns)},
        }

    explain_scope = {
        "registered_model_id": resolved["model_id"],
        "training_run_id": contract.get("training_run_id"),
        "bundle_sha256": (contract.get("artifact") or {}).get("sha256"),
        "rows": explain_rows,
        "row_count": int(len(X_explain)),
        "row_index_sha256": model_lineage.index_fingerprint(X_explain.index),
        "predictions_sha256": hashlib.sha256(proba.tobytes()).hexdigest(),
        "model_input_columns": [str(c) for c in X_explain.columns],
        "dataset_sha256": identity["dataset_sha256"],
        "dataset_file_sha256": identity["dataset_file_sha256"],
        "operating_threshold": op["value"],
        "threshold_status": op["status"],
        "threshold_source": threshold_source,
        "feature_importance_unavailable_reason": importance_reason,
        "shap_unavailable_reason": shap_info.get("shap_unavailable_reason"),
    }

    summary_text = None
    if metrics:
        try:
            metrics_dict = json.loads(metrics)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"metrics must be valid JSON: {exc}")
        summary_text = generate_model_summary(metrics_dict, importance_df, task_type or "binary")

    result = {
        "feature_importance": importance,
        "shap": shap_info,
        "summary": summary_text,
        "explain_scope": explain_scope,
    }

    try:
        persistence.log_event(
            persistence.DEV_PIPELINE_LOG,
            stage="explainability",
            payload={
                "method": "shap" if shap_info.get("shap_available") else "feature_importance",
                "compute_shap": compute_shap,
                "registered_model_id": explain_scope["registered_model_id"],
                "training_run_id": explain_scope["training_run_id"],
                "dataset_sha256": explain_scope["dataset_sha256"],
                "dataset_file_sha256": explain_scope["dataset_file_sha256"],
                "explain_rows": explain_rows,
                "row_index_sha256": explain_scope["row_index_sha256"],
                "predictions_sha256": explain_scope["predictions_sha256"],
            },
            full_payload=result,
        )
    except Exception as e:
        print(f"[persistence] failed to log explainability: {e}")

    return result


def _run_benchmark_comparison(
    replication_result: Dict[str, Any],
    challenger_model_name: str,
    target_col: str,
    y_true: Optional[np.ndarray],
    y_proba: Optional[np.ndarray],
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Fits the selected challenger model and compares it against the
    already-fitted champion.

    Reuses the exact same lightweight fit path as /models/compare —
    get_model_instance() + _lighten_for_comparison() + train_model() with
    no CV/hyperopt/OOT, through the same rebuild_preprocessor_for()
    pipeline the champion itself was fit with — rather than a separate,
    cruder hand-rolled imputer+scaler path limited to three hardcoded
    "industry standard" models. This makes champion-vs-challenger an
    apples-to-apples comparison, and lets any model the reviewer picked
    from the challenger comparison step serve as the benchmark.
    """
    X_train = replication_result.get("X_train")
    X_test = replication_result.get("X_test")
    y_train = replication_result.get("y_train")
    col_types = replication_result.get("col_types")
    prep_report = replication_result.get("prep_report_fe") or replication_result.get("prep_report")
    task_type = replication_result.get("task_type", "binary")

    if (
        X_train is None or X_test is None or y_train is None
        or y_true is None or y_proba is None
        or col_types is None or prep_report is None
    ):
        return {
            "model_name": challenger_model_name,
            "status": "SKIP",
            "metrics": {},
            "comparison": {},
        }

    try:
        model = get_model_instance(challenger_model_name, task_type)
        model = _lighten_for_comparison(model, challenger_model_name)
        pipeline, _training_info, _ = train_model(
            X_train, y_train,
            col_types=col_types,
            target_col=target_col,
            prep_report=prep_report,
            model=model,
            use_cv=False,
            use_hyperopt=False,
            task_type=task_type,
            model_name=challenger_model_name,
            use_oot=False,
        )
        if not hasattr(pipeline, "predict_proba"):
            return {
                "model_name": challenger_model_name,
                "status": "SKIP",
                "metrics": {},
                "comparison": {},
            }
        bm_proba_2d = pipeline.predict_proba(X_test)
        bm_pred = pipeline.predict(X_test)
        # The challenger's threshold is chosen on the champion's validation
        # rows (never on the shared test rows it is compared on) (E3).
        X_val, y_val = replication_result.get("X_val"), replication_result.get("y_val")
        bm_proba_val = None
        if X_val is not None and y_val is not None:
            try:
                bm_proba_val = pipeline.predict_proba(X_val)
            except Exception:
                bm_proba_val = None
        bm_threshold = select_operating_threshold(None if y_val is None else np.asarray(y_val).astype(int), bm_proba_val)
        bm_metrics = compute_binary_metrics(np.asarray(y_true).astype(int), bm_pred, bm_proba_2d, threshold=bm_threshold["value"])
        # compute_binary_metrics() never returns "gini" — it's not one of the
        # keys it computes. The champion side (val_replication_core._fit_core)
        # adds it separately via _gini()/_ks() after calling the same
        # function; do the same here so the challenger isn't silently missing
        # it in the champion-vs-challenger comparison.
        bm_scores = eval_engine._to_scores(bm_proba_2d)
        bm_metrics["gini"] = _gini(np.asarray(y_true).astype(int), bm_scores)
        bm_metrics["ks"] = _ks(np.asarray(y_true).astype(int), bm_scores)
        # The challenger's own ROC / PR curves from its actual predicted
        # probabilities on the SAME test rows as the champion (the frontend
        # used to draw a formula line, tpr = fpr × AUC, instead).
        y_true_int = np.asarray(y_true).astype(int)
        bm_roc_curve = compute_roc_curve(y_true_int, np.asarray(bm_scores, dtype=float))
        bm_pr_curve = compute_pr_curve(y_true_int, np.asarray(bm_scores, dtype=float))
    except Exception as e:
        return {
            "model_name": challenger_model_name,
            "status": "ERROR",
            "error": str(e),
            "metrics": {},
            "comparison": {},
        }

    bm_auc = bm_metrics.get("roc_auc")
    bm_gini = bm_metrics.get("gini")
    bm_recall = bm_metrics.get("recall")

    champion_metrics = replication_result.get("metrics", {})
    champion_auc = champion_metrics.get("roc_auc")
    champion_recall = champion_metrics.get("recall")
    champion_gini = champion_metrics.get("gini")

    return {
        "model_name": challenger_model_name,
        "status": "OK",
        "roc_curve": {"points": bm_roc_curve, "auc": bm_auc,
                      "provenance": curve_provenance(CURVE_SOURCE_CHALLENGER_REFIT, replication_result.get("y_test"), df)},
        "pr_curve": {"points": bm_pr_curve, "average_precision": bm_metrics.get("pr_auc"),
                     "provenance": curve_provenance(CURVE_SOURCE_CHALLENGER_REFIT, replication_result.get("y_test"), df)},
        "evaluation": {"test_rows": int(len(y_true_int)), "same_test_rows_as_champion": True,
                       "threshold_provenance": bm_threshold,
                       "champion_threshold_provenance": (replication_result.get("metrics") or {}).get("threshold_provenance")
                       or (replication_result.get("operating_threshold") or {}).get("provenance")},
        "metrics": {
            "roc_auc": bm_auc,
            "gini": bm_gini,
            "recall": bm_recall,
            # Exposed so a low recall is explainable rather than a black box:
            # the threshold is the F1-maximising one on the validation rows
            # (see evaluation.threshold_provenance), applied to the test rows.
            "precision": bm_metrics.get("precision"),
            "f1": bm_metrics.get("f1"),
            "accuracy": bm_metrics.get("accuracy"),
            "ks": bm_metrics.get("ks"),
            "threshold_used": bm_metrics.get("threshold_used"),
        },
        "comparison": {
            "champion_vs_challenger": {
                "roc_auc": {
                    "champion": champion_auc,
                    "challenger": bm_auc,
                },
                "gini": {
                    "champion": champion_gini,
                    "challenger": bm_gini,
                },
                "recall": {
                    "champion": champion_recall,
                    "challenger": bm_recall,
                },
            }
        },
    }


CURVE_SOURCE_REGISTERED_BUNDLE = "registered_bundle"
CURVE_SOURCE_INDEPENDENT_RETRAIN = "independent_retrain"
CURVE_SOURCE_UNREGISTERED_REFIT = "unregistered_refit"
CURVE_SOURCE_CHALLENGER_REFIT = "challenger_refit"


def curve_provenance(source: Optional[str], y_true: Any, df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Where a ROC / PR curve's points come from (G2): whose predictions, on
    which partition, how many rows, and the identity of the dataset and of
    the exact test rows scored. Nothing is inferred: unknown parts are None."""
    index = getattr(y_true, "index", None)
    return {
        "prediction_source": source,
        "evaluation_partition": "test",
        "rows": int(len(y_true)) if y_true is not None else None,
        "dataset_sha256": dataset_fingerprint(df) if df is not None else None,
        "test_index_sha256": model_lineage.index_fingerprint(index) if index is not None else None,
    }


def _build_performance_report(
    df: Optional[pd.DataFrame],
    replication_result: Dict[str, Any],
    intake_payload: Dict[str, Any],
    mdd_text: str,
    prediction_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Full performance report (metrics, ROC/PR curves, confusion matrix,
    calibration, score distribution, train/test AUC gap, metric checks,
    compliance findings) built from an already-fitted replication result.

    This used to live only in /validation/performance. Stage 3 (Model
    Replication, /validation/replication) and the old Stage 4 "Performance"
    tab are now one combined page, so both endpoints call this — replication
    for the combined page's charts, performance for the champion metrics +
    ROC curve its benchmarking view still needs. Factored out rather than
    duplicated so the two stay in sync.
    """
    y_true = replication_result.get("y_test")
    y_proba = replication_result.get("y_proba")
    y_true_arr = np.asarray(y_true).astype(int) if y_true is not None else None
    y_proba_arr = np.asarray(y_proba).astype(float) if y_proba is not None else None

    metrics = dict(replication_result.get("metrics") or {})
    metrics = {k: _json_safe_scalar(v) for k, v in metrics.items()}

    roc_curve = []
    if y_true_arr is not None and y_proba_arr is not None:
        roc_curve = compute_roc_curve(y_true_arr, y_proba_arr)

    pr_curve = []
    if y_true_arr is not None and y_proba_arr is not None:
        pr_curve = compute_pr_curve(y_true_arr, y_proba_arr)

    threshold_analysis = []
    if y_true_arr is not None and y_proba_arr is not None:
        threshold_analysis = compute_threshold_analysis(y_true_arr, y_proba_arr)

    score_distribution = []
    if y_true_arr is not None and y_proba_arr is not None:
        score_distribution = compute_score_distribution(y_true_arr, y_proba_arr, n_bins=40)

    # Auto-calibrate the operating threshold the same way /models/evaluate
    # does (select_best_threshold, maximizes F1) instead of a fixed 0.5
    # cut-off, so the confusion matrix and its displayed threshold always
    # line up with the threshold actually used to build it.
    #
    # When the metrics were computed at a known threshold (threshold_used,
    # e.g. a registered model's recorded threshold), the confusion matrix is
    # built at exactly that threshold so the matrix and the displayed
    # accuracy / precision / recall describe the same predictions.
    threshold_selection = None
    cm = []
    evaluation_consistency: Dict[str, Any] = {
        "status": "NOT_ASSESSED",
        "detail": "No predicted probabilities for the test rows — curves, confusion matrix and threshold metrics were not produced.",
    }
    if y_true_arr is not None and y_proba_arr is not None:
        # The threshold the metrics were computed at (validation-selected,
        # user-specified or the registered operating threshold). It is never
        # re-optimised here on the test rows (E3); if none is known the
        # nominal 0.5 is used and labelled as such.
        metrics_threshold = metrics.get("threshold_used")
        provenance = (replication_result.get("metrics") or {}).get("threshold_provenance")
        if isinstance(metrics_threshold, (int, float)) and np.isfinite(float(metrics_threshold)):
            threshold_selection = {"threshold": float(metrics_threshold), "source": "metrics_threshold_used",
                                   "provenance": provenance}
        else:
            threshold_selection = {"threshold": 0.5, "source": "nominal_no_recorded_threshold", "provenance": None,
                                   "degraded": True}
        resolved_threshold = threshold_selection["threshold"]
        y_pred = (y_proba_arr >= resolved_threshold).astype(int)
        cm_matrix = confusion_matrix(y_true_arr, y_pred, labels=[0, 1]).tolist()
        cm = {"labels": [0, 1], "matrix": cm_matrix}
        evaluation_consistency = _evaluation_consistency(y_true_arr, cm_matrix, metrics)

    calibration_points = []
    if y_true_arr is not None and y_proba_arr is not None:
        cal_df = pd.DataFrame({"actual": y_true_arr, "predicted": y_proba_arr})
        cal_df["bin"] = pd.qcut(cal_df["predicted"], q=10, duplicates="drop")
        grouped = (
            cal_df.groupby("bin", observed=True)
            .agg(actual_rate=("actual", "mean"), predicted_rate=("predicted", "mean"), n=("actual", "count"))
            .reset_index()
        )
        calibration_points = [
            {
                "bin": str(row["bin"]),
                "actual_rate": float(row["actual_rate"]),
                "predicted_rate": float(row["predicted_rate"]),
                "n": int(row["n"]),
            }
            for _, row in grouped.iterrows()
        ]

    cv_mean_auc = replication_result.get("cv_mean_auc")
    test_auc = metrics.get("roc_auc")
    train_test_gap = None
    train_test_gap_status = "WARN"
    if cv_mean_auc is not None and test_auc is not None:
        train_test_gap = round(abs(float(cv_mean_auc) - float(test_auc)), 4)
        train_test_gap_status = "PASS" if train_test_gap <= 0.10 else "FAIL"
    elif test_auc is not None:
        train_test_gap = round(float(test_auc) if np.isfinite(float(test_auc)) else 0.0, 4)
        train_test_gap_status = "WARN"

    validation_report = run_validation_agent2(df, intake_payload or {}, mdd_text)
    stage5_findings = [
        finding for finding in validation_report.get("all_findings", [])
        if finding.get("stage") == "Stage 5: Performance Validation"
    ]

    performance_checks = []
    if metrics.get("roc_auc") is not None:
        performance_checks.append({
            "check": "ROC-AUC",
            "threshold": ">= 0.70",
            "status": "PASS" if float(metrics["roc_auc"]) >= 0.70 else "FAIL",
            "value": metrics["roc_auc"],
        })
    if metrics.get("gini") is not None:
        performance_checks.append({
            "check": "Gini",
            "threshold": ">= 0.40",
            "status": "PASS" if float(metrics["gini"]) >= 0.40 else "FAIL",
            "value": metrics["gini"],
        })
    if metrics.get("recall") is not None:
        performance_checks.append({
            "check": "Recall",
            "threshold": ">= 0.60",
            "status": "PASS" if float(metrics["recall"]) >= 0.60 else "FAIL",
            "value": metrics["recall"],
        })
    if metrics.get("precision") is not None:
        performance_checks.append({
            "check": "Precision",
            "threshold": ">= 0.50",
            "status": "PASS" if float(metrics["precision"]) >= 0.50 else "FAIL",
            "value": metrics["precision"],
        })
    if metrics.get("f1") is not None:
        performance_checks.append({
            "check": "F1 Score",
            "threshold": ">= 0.55",
            "status": "PASS" if float(metrics["f1"]) >= 0.55 else "FAIL",
            "value": metrics["f1"],
        })
    if metrics.get("brier_score") is not None:
        performance_checks.append({
            "check": "Brier Score",
            "threshold": "< 0.25",
            "status": "PASS" if float(metrics["brier_score"]) < 0.25 else "FAIL",
            "value": metrics["brier_score"],
        })
    if metrics.get("pr_auc") is not None:
        performance_checks.append({
            "check": "PR-AUC",
            "threshold": ">= 0.30",
            "status": "PASS" if float(metrics["pr_auc"]) >= 0.30 else "FAIL",
            "value": metrics["pr_auc"],
        })
    if metrics.get("ks") is not None:
        performance_checks.append({
            "check": "KS Statistic",
            "threshold": ">= 0.30",
            "status": "PASS" if float(metrics["ks"]) >= 0.30 else "FAIL",
            "value": metrics["ks"],
        })

    provenance = curve_provenance(prediction_source, y_true, df)
    return {
        "metrics": metrics,
        "roc_curve": {"points": roc_curve, "auc": metrics.get("roc_auc"), "provenance": provenance},
        "pr_curve": {"points": pr_curve, "average_precision": metrics.get("pr_auc"), "provenance": provenance},
        "confusion_matrix": cm,
        "threshold_selection": threshold_selection,
        "score_distribution": {"bins": score_distribution},
        "calibration_chart": {"points": calibration_points},
        "train_test_auc_gap": {
            "cv_mean_auc": cv_mean_auc,
            "test_auc": test_auc,
            "gap": train_test_gap,
            "status": train_test_gap_status,
        },
        "metric_checks": performance_checks,
        "compliance_findings": stage5_findings,
        "threshold_analysis": threshold_analysis,
        # Cross-check that the confusion matrix, the threshold metrics and the
        # test set they describe agree with each other.
        "evaluation_consistency": evaluation_consistency,
    }


def _evaluation_consistency(y_true: np.ndarray, cm_matrix: List[List[int]], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute accuracy / precision / recall from the confusion matrix and
    compare with the reported metrics (which are rounded to 4 decimals), and
    check the matrix covers exactly the evaluated test rows."""
    (tn, fp), (fn, tp) = cm_matrix
    total = tn + fp + fn + tp
    derived = {
        "accuracy": (tp + tn) / total if total else None,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
    }
    problems: List[str] = []
    if total != len(y_true):
        problems.append(f"confusion matrix covers {total} rows but the test set has {len(y_true)}")
    if int(tp + fn) != int(np.sum(y_true)):
        problems.append("confusion-matrix positives do not match the test-set positives")
    for key, value in derived.items():
        reported = metrics.get(key)
        if value is None or reported is None:
            continue
        if abs(float(reported) - value) > 5e-4:
            problems.append(f"{key}: reported {float(reported):.4f} vs {value:.4f} from the confusion matrix")
    return {
        "status": "PASS" if not problems else "FAIL",
        "test_rows": int(len(y_true)),
        "test_positives": int(np.sum(y_true)),
        "confusion_matrix_total": int(total),
        "derived_from_confusion_matrix": {k: (round(v, 4) if v is not None else None) for k, v in derived.items()},
        "threshold_used": metrics.get("threshold_used"),
        "detail": "Confusion matrix, threshold metrics and test set agree." if not problems else "; ".join(problems),
    }


@app.post("/validation/performance")
async def validation_performance(
    model_name: str = Form(...),
    target_col: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    challenger_model_name: str = Form("Logistic Regression"),
    seeds: Optional[str] = Form("42,43,44,45,46"),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    cv_folds: int = Form(5),
    mdd_file: Optional[UploadFile] = File(None),
    reported_json: Optional[str] = Form(None),
    intake_json: Optional[str] = Form(None),
    reported_sources_json: Optional[str] = Form(None),
    registered_model_id: Optional[str] = Form(None),
    expected_training_run_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Stage 4 — Benchmarking only.

    With `registered_model_id`: the CHAMPION is the registered model — its
    verified scoring bundle on its recorded test rows (training dataset
    only; `model_name` is ignored for the champion). The challenger is a new
    fit of `challenger_model_name` on the same recorded training rows
    (minus the columns the registered preprocessing dropped), scored on the
    SAME test rows; both are identified separately in the evidence.
    Unresolvable models fail closed. Without it: champion and challenger
    are both independent refits, recorded as such.

    The full performance report (ROC/PR curves, confusion matrix,
    calibration, score distribution, metric checks, compliance findings)
    moved to /validation/replication, since Stage 3 (Model Replication) and
    the old Stage 4 "Performance" tab are now a single combined page. This
    endpoint still fits the champion model (same replication core) because
    the champion-vs-challenger comparison needs a freshly-fit champion to
    compare against the selected challenger model, and the ROC overlay
    chart needs the champion's ROC points.

    `mdd_file` / `reported_json` (optional, combinable — MDD-extracted
    values win per key) are REFERENCE values only. They are returned
    separately as `report.reference_metrics` (with a per-key source) and
    never replace the champion metrics, which are always computed from the
    fitted model's predictions. Every PASS/FAIL in `metric_checks` and the
    champion side of the champion-vs-challenger comparison use the computed
    values. (Previously the MDD values overwrote the computed ones before
    grading — see AEGIS_VALIDATION_REPLICATION_AUDIT.md, finding C1.)

    `challenger_model_name` is a real registry model name (see
    GET /models/list) — typically whichever model the reviewer picked
    after comparing several candidates via POST /models/compare, the same
    lightweight comparison used in the model development pipeline's Model
    Selection step. It's fit here via the same path (get_model_instance +
    train_model, no CV/hyperopt/OOT) so the comparison is apples-to-apples
    with the champion.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")

    try:
        seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    except Exception:
        seed_list = [random_seed]

    intake_payload: Dict[str, Any] = {}
    if intake_json:
        try:
            intake_payload = json.loads(intake_json)
        except Exception:
            intake_payload = {}

    mdd_text = ""
    mdd_extracted: Dict[str, Any] = {}
    mdd_error: Optional[str] = None
    if mdd_file is not None:
        try:
            # _sync_file_like gives parse_mdd_file the sync .name/.seek()/
            # .read() object it expects. (Assigning .name directly on the
            # SpooledTemporaryFile raises on current Python versions, which
            # used to be swallowed silently, so MDD metrics were never read.)
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
            mdd_extracted = extract_metrics_from_mdd(mdd_text)
        except Exception as exc:
            mdd_error = str(exc)

    reference = build_reference_metrics(reported_json, reported_sources_json, mdd_extracted, mdd_error)

    if (registered_model_id or "").strip():
        ctx = _registered_evaluation_or_http(df, registered_model_id, expected_training_run_id)
        identity = ctx["identity"]
        target_col = ctx["contract"]["target_col"]
        # Challenger inputs: the registered split's raw training / test rows,
        # without the columns the registered preprocessing dropped.
        drop = [c for c in ((ctx["contract"].get("preprocessing") or {}).get("drop_cols") or [])]
        Xtr_c = ctx["X_train_raw"].drop(columns=[c for c in drop if c in ctx["X_train_raw"].columns])
        Xte_c = ctx["X_test_raw"].drop(columns=[c for c in drop if c in ctx["X_test_raw"].columns])
        Xv_c = ctx["X_val_raw"].drop(columns=[c for c in drop if c in ctx["X_val_raw"].columns])
        replication_result = {
            **ctx,
            "X_train": Xtr_c, "X_test": Xte_c, "X_val": Xv_c,
            "prep_report": build_preprocessing_report(Xtr_c.assign(**{target_col: ctx["y_train"]}), ctx["col_types"], target_col),
        }
    else:
        identity = independent_refit_identity(df, model_name)
        replication_result = run_replication(
            df=df,
            target_col=target_col,
            model_name=model_name,
            test_size=test_size,
            val_size=val_size,
            random_seed=random_seed,
            cv_folds=cv_folds,
            reported={},
            seeds=seed_list,
            compute_split_integrity=False,  # Benchmarking does not report R4.7
            compute_seed_stability=False,   # ...nor R4.5 / R4.6
        )
        if replication_result.get("X_test") is not None:
            identity["test_index_sha256"] = model_lineage.index_fingerprint(replication_result["X_test"].index)

    # Champion metrics stay exactly as computed from the fitted model's
    # predictions. Reference (developer-reported) values are kept apart in
    # `reference` and never written into replication_result["metrics"].
    y_true = replication_result.get("y_test")
    y_proba = replication_result.get("y_proba")
    y_true_arr = np.asarray(y_true).astype(int) if y_true is not None else None
    y_proba_arr = np.asarray(y_proba).astype(float) if y_proba is not None else None

    metrics = dict(replication_result.get("metrics") or {})
    metrics = {k: _json_safe_scalar(v) for k, v in metrics.items()}

    roc_curve = []
    if y_true_arr is not None and y_proba_arr is not None:
        roc_curve = compute_roc_curve(y_true_arr, y_proba_arr)

    benchmark_payload = _run_benchmark_comparison(
        replication_result=replication_result,
        challenger_model_name=challenger_model_name,
        target_col=target_col,
        y_true=y_true_arr,
        y_proba=y_proba_arr,
        df=df,
    )

    performance_report = _build_performance_report(
        df=df,
        replication_result=replication_result,
        intake_payload=intake_payload,
        mdd_text=mdd_text,
        # Champion: the registered model's verified bundle, or a refit.
        prediction_source=CURVE_SOURCE_REGISTERED_BUNDLE if (registered_model_id or "").strip() else CURVE_SOURCE_UNREGISTERED_REFIT,
    )
    # Champion and challenger are identified separately; both were scored on
    # the test rows identified by test_index_sha256.
    if isinstance(benchmark_payload, dict):
        benchmark_payload.setdefault("evaluation", {})
        benchmark_payload["evaluation"].update({
            "test_index_sha256": identity.get("test_index_sha256"),
            "champion_evaluation_mode": identity["evaluation_mode"],
            "challenger_evaluation_mode": model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT,
        })
    performance_report["benchmark"] = benchmark_payload
    performance_report["reference_metrics"] = reference
    performance_report["metric_provenance"] = build_metric_provenance(reference)

    run_id = str(uuid.uuid4())
    dataset_name_for_log = getattr(file, "filename", None) or intake_payload.get("dataset_name") or None
    dataset_sha256 = identity["dataset_sha256"]
    champion = {k: identity.get(k) for k in ("evaluation_mode", "registered_model_id", "training_run_id",
                                              "bundle_sha256", "refit_algorithm")}
    challenger = {"evaluation_mode": model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT, "algorithm": challenger_model_name}
    result = {
        "stage": "performance",
        "evidence": {
            "run_id": run_id,
            "persisted": True,
            **identity,
            "algorithm": model_name,
            "challenger_model_name": challenger_model_name,
            "champion": champion,
            "challenger": challenger,
            "dataset_name": dataset_name_for_log,
            "dataset_sha256": dataset_sha256,
            "executed_at": pd.Timestamp.now().isoformat(),
        },
        "report": performance_report,
    }

    try:
        persistence.log_event(
            persistence.VALIDATION_PIPELINE_LOG,
            stage="performance",
            run_id=run_id,
            payload={
                "dataset_name": dataset_name_for_log,
                **identity,
                "champion": champion,
                "challenger": challenger,
                "model_name": model_name,
                "metrics": metrics,
                "reference_metrics": reference["values"],
                "reference_sources": reference["sources"],
                "metric_provenance_version": METRIC_PROVENANCE_SCHEMA_VERSION,
                "champion_vs_challenger": benchmark_payload.get("status") if isinstance(benchmark_payload, dict) else None,
            },
            full_payload=result,
        )
    except Exception as e:
        print(f"[persistence] failed to log benchmarking: {e}")
        result["evidence"] = {**result["evidence"], "run_id": None, "persisted": False}

    return result


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
    algorithm: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    target_col: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    seeds: Optional[str] = Form("42,43,44,45,46"),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    cv_folds: int = Form(5),
    mdd_file: Optional[UploadFile] = File(None),
    reported_json: Optional[str] = Form(None),
    intake_json: Optional[str] = Form(None),
    model_params_json: Optional[str] = Form(None),
    model_params_source: Optional[str] = Form(None),
    reported_sources_json: Optional[str] = Form(None),
    registered_model_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Run backend replication checks. Returns {'flags', 'report'} to match existing shapes.

    Two methodologies (recorded in `report.replication.result.methodology`):

    * `registered_model_id` given → registered-model reproduction. The
      model's recorded lineage contract (Model Inventory) drives everything:
      algorithm, fitted hyperparameters, features, preprocessing, split and
      seed. Form fields describing configuration (algorithm, model_params_*,
      test_size, val_size, random_seed, target_col) are ignored and listed in
      `ignored_inputs`. It performs A) exact artifact reproduction and
      B) independent training reproduction (see model_lineage.py), and R4.x
      compare the reproduction against the ORIGINAL model's performance;
      developer-reported values stay reference-only. If the lineage,
      artifact, or original data is unavailable, the run reports that and
      does not substitute anything. An unknown model ID returns 404.

    * no `registered_model_id` → the previous behaviour, kept for API
      compatibility: an independent refit from the configuration supplied in
      the request. It is labelled `unregistered_independent_refit` and is
      not a reproduction of a registered model (the final verdict will not
      accept it as replication evidence).

    `reported` (the developer-reported metrics R4.2/R4.3/R4.4/R4.8 compare against)
    can come from two places, combinable: `reported_json` (e.g. pulled from an
    already-completed training run's evaluation_metrics) and/or an uploaded MDD
    file. When both are present, values extracted from the MDD take precedence
    per-key, since the MDD is the authoritative developer documentation.
    `reported_sources_json` optionally labels where each `reported_json`
    value came from (intake_mdd / development_training_run / manual_entry /
    demo_intake). The exact reference values used for the checks, with a
    per-key source, are returned as `report.reference_metrics` and saved
    with the run, so the UI shows what was actually compared.

    This now also returns the full performance report (`report.metrics`,
    `report.roc_curve`, `report.pr_curve`, `report.confusion_matrix`,
    `report.calibration_chart`, `report.score_distribution`,
    `report.train_test_auc_gap`, `report.metric_checks`,
    `report.compliance_findings`, `report.threshold_analysis`) alongside the
    existing `report.replication.{result,checks}` — Stage 3 (Model
    Replication) and the old Stage 4 "Performance" tab are now a single
    combined page, so this one call produces everything it needs.
    `intake_json` is optional and only feeds `compliance_findings`.

    `model_params_json`, per the Model Replication Methodology Audit: the
    developer's actual recoverable training configuration (hyperopt
    best_params, or explicit manual_params/scale_pos_weight), when the
    frontend found one that belongs to this same model. Passed straight
    through to `run_replication(model_params=...)`, which already supports
    it — replication itself, its thresholds, and R4.1-R4.8 are unchanged.
    `model_params_source` is a hint the frontend sends alongside it
    ("developer_hyperopt_best_params" or "developer_training_config"); it is
    only trusted when a real, non-empty `model_params_json` backs it up — a
    label with no real params behind it is never recorded as if it were.
    When neither is supplied (or parsing fails), replication falls back to
    the registry defaults exactly as before, and the result explicitly
    records that via `replication_config_source =
    "registry_defaults_unavailable_config"` rather than staying silent
    about it.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text)
    # parse seeds
    try:
        seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    except Exception:
        seed_list = [random_seed]

    registered_entry: Optional[Dict[str, Any]] = None
    ignored_inputs: List[str] = []
    if registered_model_id and registered_model_id.strip():
        registered_model_id = registered_model_id.strip()
        registered_entry = next(
            (m for m in persistence.load_model_inventory().get("development", [])
             if isinstance(m, dict) and str(m.get("model_id") or "").strip() == registered_model_id),
            None,
        )
        if registered_entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Registered model '{registered_model_id}' was not found in the Model Inventory. Replication was not run.",
            )
        contract = registered_entry.get("lineage_contract") or {}
        business_model_name = str(registered_entry.get("model_name") or "").strip()
        estimator_name = str(contract.get("estimator_name") or registered_entry.get("algorithm") or "").strip()
        if contract.get("target_col"):
            if target_col != contract["target_col"]:
                ignored_inputs.append(f"target_col ('{target_col}' — the registered model's target '{contract['target_col']}' is used)")
            target_col = contract["target_col"]
        for name, value in (("algorithm", algorithm), ("model_params_json", model_params_json),
                            ("model_params_source", model_params_source)):
            if value:
                ignored_inputs.append(name)
        if (model_name or "").strip() and (model_name or "").strip() != business_model_name:
            ignored_inputs.append(f"model_name ('{model_name}' — the registered name '{business_model_name}' is used)")
        model_params_json = None
        model_params_source = None
    else:
        registered_model_id = None
        try:
            business_model_name, estimator_name = resolve_replication_model_inputs(model_name, algorithm)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Developer configuration for the model being replicated — see the
    # docstring above. `replication_config_source` is derived entirely from
    # whether a real, non-empty dict was actually received, never from the
    # client's claimed label alone.
    model_params: Optional[Dict[str, Any]] = None
    if model_params_json:
        try:
            parsed_model_params = json.loads(model_params_json)
            if isinstance(parsed_model_params, dict) and parsed_model_params:
                model_params = parsed_model_params
        except Exception:
            model_params = None
    if registered_entry is not None:
        replication_config_source = "registered_lineage_contract"
    elif model_params:
        replication_config_source = (
            model_params_source
            if model_params_source in ("developer_hyperopt_best_params", "developer_training_config")
            else "developer_training_config"
        )
    else:
        replication_config_source = "registry_defaults_unavailable_config"

    intake_payload: Dict[str, Any] = {}
    if intake_json:
        try:
            intake_payload = json.loads(intake_json)
        except Exception:
            intake_payload = {}

    mdd_text = ""
    mdd_extracted: Dict[str, Any] = {}
    mdd_error: Optional[str] = None
    if mdd_file is not None:
        try:
            if not intake_payload.get("mdd_document_path"):
                intake_payload["mdd_document_path"] = _save_uploaded_mdd(mdd_file)
        except Exception:
            pass
        try:
            # parse_mdd_file was ported from Streamlit and expects a sync
            # file-like object with .name/.seek()/.read(). _sync_file_like
            # provides that (and seeks to 0, since _save_uploaded_mdd above
            # already read the stream). Assigning .name directly on the
            # SpooledTemporaryFile raises on current Python versions — that
            # used to be swallowed silently, so MDD metrics were never read.
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
            mdd_extracted = extract_metrics_from_mdd(mdd_text)
        except Exception as exc:
            mdd_error = str(exc)

    # Reference (developer-reported) metrics for R4.2/R4.3/R4.4/R4.8, with a
    # per-key source. Only ever compared against — never merged into the
    # computed replication metrics.
    reference = build_reference_metrics(reported_json, reported_sources_json, mdd_extracted, mdd_error)
    reported: Dict[str, Any] = dict(reference["values"])

    # The dataset identity used to scope replication resume (see the
    # /history/latest call below) — the same filename/intake fallback the
    # Model Inventory registration below already uses for its own
    # `dataset_payload["file_name"]`, computed here independently (rather
    # than reading it back off `dataset_payload` after the fact) so it stays
    # correct even if that registration's own try/except below fails before
    # `dataset_payload` is ever assigned. Left as None — never a placeholder
    # string like "uploaded_dataset" — when no real filename/intake dataset
    # name is known, so two different nameless uploads can never be
    # mistaken for the same dataset by the resume filter.
    dataset_name_for_log = getattr(file, "filename", None) or intake_payload.get("dataset_name") or None
    # Content fingerprint of the exact data this run used — part of the
    # evidence Stage 7 (final verdict) verifies before trusting this run.
    dataset_sha256 = dataset_fingerprint(df)
    demo_dataset = _server_demo_dataset_flag(dataset_sha256=dataset_sha256)
    # Fingerprint of the bytes as received (D1): what the browser can compute
    # itself, so a resumed run is only shown for the dataset now loaded.
    dataset_file_sha256 = source_fingerprint(file, csv_text)
    validation_model_id: Optional[str] = None
    validation_run_id: Optional[str] = None
    # Identity of this execution, assigned before it starts so the
    # "Validation Run Started" history event, the outcome event and the
    # replication log row all carry the same run_id.
    run_id = str(uuid.uuid4())
    execution_mode = (model_lineage.REPLICATION_MODE_REGISTERED if registered_entry is not None
                      else model_lineage.REPLICATION_MODE_UNREGISTERED)

    # Server-verified demo datasets never create a validation inventory
    # record. This preserves the approved demo-only history path while
    # keeping real independent-refit and registered-model workflows intact.
    if not demo_dataset:
        try:
            store = persistence.load_model_inventory()
            inventory_model_name = business_model_name or estimator_name
            dataset_payload = {
                "file_name": dataset_name_for_log or "uploaded_dataset",
                "storage_reference": dataset_name_for_log or "",
                "source_type": "file",
                "purpose": "Validation dataset",
                "record_count": int(df.shape[0]) if df is not None else None,
                "column_count": int(df.shape[1]) if df is not None else None,
                "target_variable": intake_payload.get("target_col") or intake_payload.get("target") or target_col,
                "uploaded_by": intake_payload.get("model_owner") or "user",
                "uploaded_at": pd.Timestamp.now().isoformat(),
            }
            registration = persistence.register_validation_run(
                store=store,
                business_model_name=inventory_model_name,
                estimator_name=estimator_name,
                intake_payload={
                    # Links the validation engagement to the registered
                    # development model (related_model_id) when reproducing one.
                    "model_id": registered_model_id,
                    "model_type": intake_payload.get("model_type") or "PD (Probability of Default)",
                    "model_purpose": intake_payload.get("model_purpose") or intake_payload.get("business_purpose"),
                    "model_owner": intake_payload.get("model_owner") or intake_payload.get("owner") or "Unknown",
                    "owning_team": intake_payload.get("owning_team") or intake_payload.get("business_unit") or "Risk",
                    "model_version": intake_payload.get("model_version") or "1.0",
                    "regulatory_framework": intake_payload.get("regulatory_framework") or "Internal",
                    "mdd_document_path": intake_payload.get("mdd_document_path")
                        or intake_payload.get("documentation_path")
                        or intake_payload.get("document_path")
                        or ("demo_data/flawed_mdd.txt" if _normalize_demo_mode(intake_payload.get("demo_mode")) == "flawed"
                            else "demo_data/taiwan_mdd.txt" if _normalize_demo_mode(intake_payload.get("demo_mode")) == "taiwan"
                            else "demo_data/clean_mdd.txt" if _normalize_demo_mode(intake_payload.get("demo_mode")) == "clean"
                            else None),
                },
                dataset_payload=dataset_payload,
                target_col=target_col,
                user=intake_payload.get("model_owner") or "user",
                run_id=run_id,
            )
            persistence.save_model_inventory(store)
            validation_model_id = (registration or {}).get("model_id")
            validation_run_id = (registration or {}).get("validation_run_id")
        except Exception as e:
            print(f"[persistence] failed to update inventory from replication: {e}")

    def _record_outcome(succeeded: bool, detail: Optional[str]) -> None:
        # Outcome event for the run started above; never fails the request.
        if not validation_model_id or not validation_run_id:
            return
        try:
            outcome_store = persistence.load_model_inventory()
            persistence.record_validation_run_outcome(
                outcome_store, validation_model_id, validation_run_id, succeeded,
                execution_mode=execution_mode, run_id=run_id, registered_model_id=registered_model_id,
                detail=detail, user=intake_payload.get("model_owner") or "user",
            )
            persistence.save_model_inventory(outcome_store)
        except Exception as outcome_exc:
            print(f"[persistence] failed to record validation run outcome: {outcome_exc}")

    checks_error: Optional[str] = None  # set if the R4.x checks could not be evaluated
    try:
        if registered_entry is not None:
            # Registered-model reproduction: configuration from the lineage
            # contract; R4.x compare against the ORIGINAL model's performance
            # (the re-scored artifact, or the metrics recorded at training if the
            # artifact is unavailable — the methodology says which).
            result = model_lineage.run_registered_replication(
                df, registered_entry, dataset_sha256=dataset_sha256, seeds=seed_list,
            )
            comparator = result.get("original_metrics") or {}
            checks = []
            try:
                checks = evaluate_replication_checks(result, comparator, seed_list, comparator_label="Original model")
            except Exception as checks_exc:
                checks = []
                checks_error = f"{type(checks_exc).__name__}: {checks_exc}"
            # R4.7 comes from result["split_integrity"] (built by
            # model_lineage.registered_split_integrity), like every other mode.
        else:
            result = run_replication(
                df=df,
                target_col=target_col,
                model_name=estimator_name,
                test_size=test_size,
                val_size=val_size,
                random_seed=random_seed,
                cv_folds=cv_folds,
                reported=reported,
                seeds=seed_list,
                model_params=model_params,
                dataset_sha256=dataset_sha256,
            )
            result["methodology"] = {
                "mode": model_lineage.REPLICATION_MODE_UNREGISTERED,
                "registered_model_id": None,
                "detail": "Independent refit from the configuration supplied in this request (algorithm, split sizes, "
                          "optional parameters). It is NOT a reproduction of a registered model: no registered "
                          "artifact, recorded hyperparameters, preprocessing or dataset lineage were used.",
                "limitations": ["Not linked to a registered model — cannot serve as replication evidence for a final verdict."],
            }
            checks = []
            try:
                checks = evaluate_replication_checks(result, reported, seed_list)
            except Exception as checks_exc:
                checks = []
                checks_error = f"{type(checks_exc).__name__}: {checks_exc}"
        result.setdefault("methodology", {})["ignored_inputs"] = ignored_inputs

        # Build flags similar to Agent2: list of failing check ids
        flags = [c["id"] for c in checks if c.get("status") in ("FAIL",)]

        safe_result = dict(result)
        for key in ["pipeline", "X_train", "X_test", "y_train", "y_test", "y_proba", "y_pred"]:
            safe_result.pop(key, None)
        safe_result = _serialize_stage5_payload(safe_result)
        # Explicit provenance — never silent about whether this run actually
        # used the developer's real configuration or fell back to registry
        # defaults. Derived above purely from what was actually received.
        safe_result["replication_config_source"] = replication_config_source

        # A registered reproduction's report shows the independent retrain's
        # predictions (the reproduction); otherwise the unregistered refit's.
        performance_report = _build_performance_report(
            df, result, intake_payload, mdd_text,
            prediction_source=CURVE_SOURCE_INDEPENDENT_RETRAIN if registered_entry is not None else CURVE_SOURCE_UNREGISTERED_REFIT)

        # Identity of this exact execution. Stage 7 (final verdict) reloads the
        # run from the log by run_id and checks every field below, so a verdict
        # can only rest on a replication that really ran, for this model, on
        # this data. (run_id was assigned before execution started.)
        methodology = result.get("methodology") or {}
        evidence = {
            "run_id": run_id,
            "validation_run_id": validation_run_id,
            "persisted": True,
            "replication_mode": methodology.get("mode"),
            "registered_model_id": registered_model_id,
            "training_run_id": methodology.get("training_run_id"),
            "execution_status": "COMPLETED" if result.get("success") else "FAILED",
            "validation_model_id": validation_model_id,
            "business_model_name": business_model_name,
            "algorithm": estimator_name,
            "dataset_name": dataset_name_for_log,
            "dataset_sha256": dataset_sha256,
            "dataset_file_sha256": dataset_file_sha256,
            "dataset_rows": int(df.shape[0]),
            "target_col": target_col,
            "demo_dataset": demo_dataset,
            "executed_at": pd.Timestamp.now().isoformat(),
        }

        response_payload = {
            "stage": "replication",
            "flags": flags,
            "evidence": evidence,
            "report": {
                "replication": {"result": safe_result, "checks": checks},
                **performance_report,
                "reference_metrics": reference,
                "metric_provenance": build_metric_provenance(reference),
            },
        }

        try:
            persistence.log_event(
                persistence.VALIDATION_PIPELINE_LOG,
                stage="replication",
                payload={
                    "business_model_name": business_model_name,
                    "algorithm": estimator_name,
                    "model_name": estimator_name,
                    "dataset_name": dataset_name_for_log,
                    "dataset_sha256": dataset_sha256,
                    "dataset_file_sha256": dataset_file_sha256,
                    "validation_model_id": validation_model_id,
                    "validation_run_id": validation_run_id,
                    "registered_model_id": registered_model_id,
                    "training_run_id": methodology.get("training_run_id"),
                    "replication_mode": methodology.get("mode"),
                    "execution_status": "COMPLETED" if result.get("success") else "FAILED",
                    "demo_dataset": demo_dataset,
                    "exact_artifact_reproduction": (methodology.get("exact_artifact_reproduction") or {}).get("status"),
                    "independent_training_reproduction": (methodology.get("independent_training_reproduction") or {}).get("status"),
                    "replication_config_source": replication_config_source,
                    "metrics": performance_report.get("metrics"),
                    "reference_metrics": reference["values"],
                    "reference_sources": reference["sources"],
                    "metric_provenance_version": METRIC_PROVENANCE_SCHEMA_VERSION,
                    "flags": flags,
                },
                full_payload=response_payload,
                run_id=run_id,
            )
        except Exception as e:
            print(f"[persistence] failed to log replication: {e}")
            # Not saved, so it cannot serve as verifiable evidence later.
            response_payload["evidence"] = {**evidence, "run_id": None, "persisted": False}

    except Exception as exec_exc:
        # Execution did not finish: record Failed (never Completed) and re-raise.
        _record_outcome(False, f"Execution error: {type(exec_exc).__name__}: {exec_exc}")
        raise

    # Exactly one outcome per execution. Completed only for a successful run
    # whose checks were evaluated and whose evidence was saved.
    if result.get("success") is not True:
        _record_outcome(False, f"Replication did not succeed: {result.get('error') or 'unknown error'}")
    elif checks_error:
        _record_outcome(False, f"Replication checks could not be evaluated: {checks_error}")
    elif not response_payload["evidence"].get("persisted"):
        _record_outcome(False, "Replication ran but its evidence could not be saved to the validation log.")
    else:
        _record_outcome(True, None)
    return response_payload


@app.post("/validation/stage7/bias-check")
async def validation_stage7_bias_check(
    algorithm: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    target_col: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    protected_col: Optional[str] = Form(None),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    cv_folds: int = Form(5),
    registered_model_id: Optional[str] = Form(None),
    expected_training_run_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Stage 7 Fair Lending Bias Check (Explainability & Fairness tab).

    With `registered_model_id`: the REGISTERED model is evaluated — its
    verified scoring bundle scores its recorded test rows (training dataset
    only); nothing is refitted and `algorithm` is ignored. Unresolvable
    models fail closed. Without it: an independent refit from `algorithm`,
    recorded as such and never attributed to a registered model.

    If `protected_col` is omitted, only detects candidate protected columns
    (age/gender/region/etc.) so the frontend can populate its selector.
    """
    df = await _read_dataframe(file=file, csv_text=csv_text)
    resolved_model_name = (algorithm or model_name or "").strip()
    registered = bool((registered_model_id or "").strip())
    if not registered and not resolved_model_name:
        raise HTTPException(status_code=400, detail="Model or algorithm is required.")

    if not protected_col:
        return {
            "success": True,
            "error": None,
            "protected_columns": detect_protected_columns(df),
            "bias_col": None,
            "rows": [],
            "check": None,
        }

    if registered:
        ctx = _registered_evaluation_or_http(df, registered_model_id, expected_training_run_id)
        identity = ctx["identity"]
        result = bias_from_predictions(df, ctx["y_test"], ctx["y_proba"], protected_col)
    else:
        identity = independent_refit_identity(df, resolved_model_name)
        result = run_bias_check(
            df=df,
            target_col=target_col,
            model_name=resolved_model_name,
            protected_col=protected_col,
            test_size=test_size,
            val_size=val_size,
            random_seed=random_seed,
            cv_folds=cv_folds,
        )

    run_id = str(uuid.uuid4())
    result = {**result, "evidence": {"run_id": run_id, **identity}}
    try:
        persistence.log_event(
            persistence.VALIDATION_PIPELINE_LOG,
            stage="fair_lending_bias",
            payload={
                **identity,
                "model_name": resolved_model_name or None,
                "protected_col": protected_col,
                "success": result.get("success"),
                "check": result.get("check"),
            },
            full_payload=result,
            run_id=run_id,
        )
    except Exception as e:
        print(f"[persistence] failed to log fair_lending_bias: {e}")
        result["evidence"] = {**result["evidence"], "run_id": None, "persisted": False}

    return result


@app.post("/validation/stress/run")
async def validation_stress_run(
    algorithm: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    target_col: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    seeds: Optional[str] = Form("42,43,44,45,46"),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    cv_folds: int = Form(5),
    freq: Optional[str] = Form("quarterly"),
    date_col: Optional[str] = Form(None),
    registered_model_id: Optional[str] = Form(None),
    expected_training_run_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Stage 6 — Stress Testing & Backtesting.

    With `registered_model_id`: the REGISTERED model is stressed — its
    verified scoring bundle on its recorded train/test rows (training
    dataset only). Nothing is refitted (6.1 sensitivity permutes the
    registered model's inputs instead of removing-and-refitting) and
    `algorithm` is ignored. Unresolvable models fail closed. Without it: an
    independent refit from `algorithm`, recorded as such and never
    attributed to a registered model.

    Runs everything from validation_stress_core.run_stress_suite() in one call:
    ablation-based sensitivity (6.1), macro stress scenarios (6.2), PSI score
    stability (6.4), backtesting vs realised default rate (6.8), and
    directional testing (6.9a-c). Ported from the Streamlit app's Stage 6
    tabs — see validation_stress_core.py for what was intentionally dropped
    (the LGD-dependent directional check).

    Takes the same training params as /validation/replication and retrains
    within this request (no pipeline is cached between requests in this
    backend — same tradeoff /validation/replication already makes).
    """
    df = await _read_dataframe(file=file, csv_text=csv_text)

    try:
        seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    except Exception:
        seed_list = [random_seed]

    resolved_model_name = (algorithm or model_name or "").strip()
    registered = bool((registered_model_id or "").strip())
    if not registered and not resolved_model_name:
        raise HTTPException(status_code=400, detail="Model or algorithm is required.")

    if registered:
        rep_result = _registered_evaluation_or_http(df, registered_model_id, expected_training_run_id, compute_sensitivity=True)
        identity = rep_result["identity"]
    else:
        identity = independent_refit_identity(df, resolved_model_name)
        rep_result = run_replication(
            df=df,
            target_col=target_col,
            model_name=resolved_model_name,
            test_size=test_size,
            val_size=val_size,
            random_seed=random_seed,
            cv_folds=cv_folds,
            reported={},
            seeds=seed_list,
            compute_seed_stability=False,
            compute_split_integrity=False,
        )

    # H3: the dataset bytes as received, recorded with the run (evidence and
    # log) so stage-done lookups can be scoped to the exact file loaded.
    identity = {**identity, "dataset_file_sha256": source_fingerprint(file, csv_text)}
    suite = run_stress_suite(rep_result, val_df=df, freq_key=freq or "quarterly", date_col=date_col)
    run_id = str(uuid.uuid4())
    result = {"stage": "stress", "report": suite, "evidence": {"run_id": run_id, **identity}}
    if registered:
        result["shockable_features"] = registered_shockable_features(rep_result)

    try:
        persistence.log_event(
            persistence.VALIDATION_PIPELINE_LOG,
            stage="stress_testing",
            payload={
                **identity,
                "model_name": resolved_model_name or None,
                "scenarios": list(suite.keys()) if isinstance(suite, dict) else None,
            },
            full_payload=result,
            run_id=run_id,
        )
    except Exception as e:
        print(f"[persistence] failed to log stress_testing: {e}")
        result["evidence"] = {**result["evidence"], "run_id": None, "persisted": False}

    return result


@app.post("/validation/stress/shock")
async def validation_stress_shock(
    algorithm: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    target_col: str = Form(...),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    seeds: Optional[str] = Form("42,43,44,45,46"),
    test_size: float = Form(0.15),
    val_size: float = Form(0.15),
    random_seed: int = Form(42),
    cv_folds: int = Form(5),
    shock_feature: str = Form(...),
    shock_direction: str = Form(...),
    shock_magnitude_pct: float = Form(20),
    registered_model_id: Optional[str] = Form(None),
    expected_training_run_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Stage 6 — manual single-feature shock (the interactive "Apply Shock"
    control), re-run on demand with a different feature/direction/magnitude.

    With `registered_model_id`: the REGISTERED model is shocked — its verified
    scoring bundle on its recorded test rows (training dataset only), the raw
    feature shocked and re-scored through the bundle's full scoring chain.
    Unresolvable models fail closed; there is never a refit fallback and
    `algorithm` is ignored. Without it: an independent refit from `algorithm`,
    labelled as such.

    A shock is an interactive what-if, not validation evidence: it is never
    logged and never read by the findings / verdict (which ignore any
    `shock_result_json` the browser posts).
    """
    df = await _read_dataframe(file=file, csv_text=csv_text)

    try:
        seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    except Exception:
        seed_list = [random_seed]

    if shock_direction not in ("increase", "decrease"):
        raise HTTPException(status_code=400, detail="shock_direction must be 'increase' or 'decrease'.")
    if not (0 < float(shock_magnitude_pct) <= 100):
        raise HTTPException(status_code=400, detail="shock_magnitude_pct must be greater than 0 and at most 100.")
    not_evidence = {"persisted": False, "verdict_evidence": False}

    if (registered_model_id or "").strip():
        ctx = _registered_evaluation_or_http(df, registered_model_id, expected_training_run_id)
        allowed = registered_shockable_features(ctx)
        if shock_feature not in allowed:
            raise HTTPException(status_code=400, detail=(
                f"'{shock_feature}' is not a numeric raw input of registered model {ctx['identity']['registered_model_id']}. "
                f"Shockable features: {allowed}."))
        pipeline, transform = ctx["pipeline"], ctx["transform"]

        def score(X_raw: pd.DataFrame) -> np.ndarray:
            return np.asarray(pipeline.predict_proba(transform(X_raw)))[:, 1]

        shock_result = apply_manual_shock_through(score, ctx["X_test_raw"], shock_feature, shock_direction, shock_magnitude_pct)
        return {"stage": "stress_shock", "result": shock_result, "evidence": {**ctx["identity"], **not_evidence}}

    resolved_model_name = (algorithm or model_name or "").strip()
    if not resolved_model_name:
        raise HTTPException(status_code=400, detail="Model or algorithm is required.")
    identity = independent_refit_identity(df, resolved_model_name)

    rep_result = run_replication(
        df=df,
        target_col=target_col,
        model_name=resolved_model_name,
        test_size=test_size,
        val_size=val_size,
        random_seed=random_seed,
        cv_folds=cv_folds,
        reported={},
        seeds=seed_list,
        compute_seed_stability=False,
        compute_split_integrity=False,
    )

    try:
        shock_result = run_manual_shock(rep_result, shock_feature, shock_direction, shock_magnitude_pct)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if rep_result.get("X_test") is not None:
        identity["test_index_sha256"] = model_lineage.index_fingerprint(rep_result["X_test"].index)

    return {"stage": "stress_shock", "result": shock_result, "evidence": {**identity, **not_evidence}}


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

    result = {"stage": "agent2", "flags": flags, "report": report}

    # No persistence logging here: the frontend never calls this endpoint
    # (it uses /validation/stage8/findings instead, which is where
    # stage="findings" is now logged). Left uninstrumented rather than
    # removed since it's still a working endpoint.

    return result


_FRAMEWORK_DISPLAY = {
    "IFRS9": "IFRS 9",
    "IFRS 9": "IFRS 9",
    "SS1/23": "SS1/23",
    "SS11/13": "SS11/13",
    "RBI": "RBI Model Risk Management",
    "RBI Model Risk Management": "RBI Model Risk Management",
}


def _sanitize_frameworks(frameworks: Any) -> List[str]:
    """Remove IFRS 9 from submitted intake selections while normalising RBI/SS1/23 values."""
    if frameworks is None:
        return []
    items = frameworks if isinstance(frameworks, list) else [frameworks]
    clean: List[str] = []
    seen = set()
    for raw in items:
        if raw is None:
            continue
        item = str(raw).strip()
        if not item:
            continue
        lowered = item.lower()
        if lowered in {"ifrs9", "ifrs 9", "ifrs-9"}:
            continue
        if lowered == "rbi":
            item = "RBI Model Risk Management"
        elif lowered == "rbi model risk management":
            item = "RBI Model Risk Management"
        elif lowered == "ss1/23":
            item = "SS1/23"
        elif lowered == "ss11/13":
            item = "SS11/13"
        if item not in seen:
            clean.append(item)
            seen.add(item)
    return clean


def _display_framework_name(value: Optional[str]) -> str:
    """Return a user-facing label for a regulatory framework source."""
    if not value:
        return ""
    if isinstance(value, str):
        return _FRAMEWORK_DISPLAY.get(value.strip(), value.strip())
    return str(value)


def _normalize_finding(f: dict) -> dict:
    """Return a frontend-friendly normalized finding dict."""
    return {
        "id": f.get("check_id"),
        "stage": f.get("stage"),
        "title": f.get("title"),
        "status": f.get("status"),
        "severity": f.get("severity"),
        "observed": f.get("observed"),
        "detail": f.get("detail"),
        "mdd_reference": f.get("mdd_reference"),
        "check_type": f.get("check_type"),
        "source": _display_framework_name(f.get("source")),
        "principle": f.get("principle"),
    }


def _derive_feature_importance_payload(report: dict, df=None, model_file: Optional[UploadFile] = None, intake: Optional[dict] = None) -> dict:
    """Feature importance of the actual model, with its source stated.

    Only two sources are used: an uploaded model artifact, or the
    importances ValidationAgent2's own replication produced. The previous
    fallback — a Logistic Regression fitted on whatever column looked like a
    binary target, using raw coefficient size on unscaled features — is
    removed: the target could be guessed wrongly, and unscaled coefficients
    reflect units rather than relevance, so it was not the model's feature
    relevance. When neither source is available, nothing is returned and
    `importance_source` says why."""
    replicated = report.get("replicated_importances", {}) or {}
    importance_df = None
    importance_source = "unavailable"
    importance_note = "No verified registered model and no replication importances were available, so feature relevance was not assessed."

    # An uploaded `model_file` is never read or deserialized (it could execute
    # code). The model's own importances come from the registered model chosen
    # at Intake, loaded from its verified scoring bundle.
    registered_id = (intake or {}).get("registered_model_id") if isinstance(intake, dict) else None
    if registered_id:
        try:
            resolved = model_lineage.load_registered_scoring_bundle(registered_id)
            df_imp = extract_feature_importance(resolved["bundle"]["pipeline"])
            if df_imp is not None:
                importance_df = df_imp.to_dict(orient="records")
                importance_source = "registered_scoring_bundle"
                importance_note = f"Importances of registered model {registered_id} (verified scoring bundle)."
        except model_lineage.ArtifactVerificationError as exc:
            importance_note = f"Registered model {registered_id} could not be loaded ({exc.status}): {' '.join(exc.reasons)}"
    elif model_file is not None:
        importance_note = "An uploaded model file was ignored: uploaded artifacts are not deserialized. " + importance_note

    if importance_df is None and replicated:
        try:
            importance_df = [
                {"Feature": feature, "Importance": float(score)}
                for feature, score in sorted(replicated.items(), key=lambda item: item[1], reverse=True)
            ]
            importance_source, importance_note = "validation_agent2_replication", "Importances of ValidationAgent2's replicated model."
        except Exception:
            importance_df = None

    top_drivers = importance_df[:8] if importance_df else []
    return {
        "replicated_importances": replicated,
        "importance_df": importance_df,
        "top_drivers": top_drivers,
        "importance_source": importance_source,
        "importance_note": importance_note,
    }


def _group_stage2(report: dict, rag_results: Optional[List[dict]] = None, selected_frameworks: Optional[List[str]] = None) -> dict:
    """Map ValidationAgent2 + Agent2 RAG results into the Stage 2 UI payload.

    Mirrors _group_stage3 exactly, but for "Stage 2: Data Validation":
    `thresholdChecks` are the quantitative ValidationAgent2 findings tagged
    for that stage; `ragRules` are the qualitative MDD rules retrieved from
    the regulatory knowledge store (rag_store/val_mdd_rules.json, stage ==
    "data_validation") and cross-checked against the MDD text via
    check_mdd_keywords / check_for_validation — same RAG pipeline Stage 3
    uses, just a different stage key. No featureRelevance section here;
    that's conceptual-soundness-specific (feature importance charts).
    """
    findings = []
    try:
        findings = report.get("findings_by_stage", {}).get("Stage 2: Data Validation", [])
    except Exception:
        findings = []

    raw_findings = [f for f in findings]
    rag_results = rag_results or []

    filtered_findings = raw_findings
    if selected_frameworks:
        filtered_findings = [f for f in raw_findings if _rule_matches_frameworks(f, selected_frameworks)]

    threshold_checks = [_normalize_threshold_check(f) for f in filtered_findings]
    rag_rules = [_normalize_rag_rule(r) for r in rag_results]

    combined = filtered_findings + rag_results
    stage2_counts = {
        "pass": sum(1 for f in combined if f.get("status") == "PASS"),
        "warn": sum(1 for f in combined if f.get("status") == "WARN"),
        "fail": sum(1 for f in combined if f.get("status") == "FAIL"),
        "pending": sum(1 for f in combined if f.get("status") == "PENDING"),
        # Anything outside PASS/WARN/FAIL/PENDING (e.g. an unrecognized or
        # missing status) is bucketed here so summary.total always equals
        # the sum of every exposed bucket instead of silently over-counting.
        "na": sum(1 for f in combined if f.get("status") not in ("PASS", "WARN", "FAIL", "PENDING")),
    }
    stage2_high_fails = [f for f in combined if f.get("status") == "FAIL" and str(f.get("severity", "")).upper() == "HIGH"]
    if len(stage2_high_fails) == 0 and stage2_counts["fail"] == 0 and stage2_counts["pending"] == 0:
        stage2_verdict = "PASS"
    elif len(stage2_high_fails) == 0 and stage2_counts["fail"] == 0:
        stage2_verdict = "CONDITIONAL"
    elif len(stage2_high_fails) <= 2:
        stage2_verdict = "CONDITIONAL"
    else:
        stage2_verdict = "FAIL"

    remediation_items = []
    if stage2_high_fails:
        remediation_items.append(f"Address {len(stage2_high_fails)} high-severity finding(s) before approval.")
    if stage2_counts["warn"]:
        remediation_items.append(f"Document and remediate {stage2_counts['warn']} warning(s) in the MDD or model controls.")
    if not remediation_items:
        remediation_items.append("No material remediation required at this stage.")

    regulatory_references = sorted({_display_framework_name(f.get("source")) for f in combined if f.get("source")})
    if not regulatory_references:
        if selected_frameworks:
            regulatory_references = [_display_framework_name(fw) for fw in selected_frameworks]
        else:
            regulatory_references = ["IFRS 9", "SS11/13", "SS1/23"]

    regulatory = {
        "verdict": stage2_verdict,
        "counts": stage2_counts,
        "remediation_summary": " ".join(remediation_items),
        "regulatory_references": regulatory_references,
        "high_severity_fails": [_normalize_finding(f) for f in stage2_high_fails],
    }

    pending_llm_ids = [
        r.get("check_id", r.get("rule_id"))
        for r in rag_results
        if r.get("check_source") == "keyword_search" and r.get("status") != "PASS"
    ]

    return {
        "thresholdChecks": threshold_checks,
        "ragRules": rag_rules,
        "summary": {
            "total": len(combined),
            "pass": stage2_counts["pass"],
            "warn": stage2_counts["warn"],
            "fail": stage2_counts["fail"],
            "pending": stage2_counts["pending"],
            "na": stage2_counts["na"],
        },
        "regulatoryAlignment": regulatory,
        "raw_findings": raw_findings,
        "pending_llm_ids": list(dict.fromkeys(pending_llm_ids)),
    }


def _normalize_threshold_check(f: dict) -> dict:
    """Normalize a check_conceptual_soundness() finding into the
    'Recommended Threshold Checks' card schema (mirrors app.py's left column).

    check_type is passed through so the frontend can tell a quantitative
    check (check_type "data"/"cross_reference" — e.g. VIF > 10, missing data
    < 20%) from a documentation check (check_type "doc" — e.g. methodology
    justification, bias documentation). Only the former's numeric threshold
    is an industry-statistical convention rather than regulatory text, so
    only those get the "Regulatory basis" / "Threshold" split label.
    """
    return {
        "check_id": f.get("check_id", ""),
        "title": f.get("title", ""),
        "severity": str(f.get("severity", "medium")).upper(),
        "status": f.get("status", "WARN"),
        "source": _display_framework_name(f.get("source", "")),
        "principle": f.get("principle", ""),
        "observed": f.get("observed", ""),
        "threshold": f.get("threshold", ""),
        "detail": f.get("detail", ""),
        "check_type": f.get("check_type", ""),
    }


def _normalize_rag_rule(r: dict) -> dict:
    """Normalize an Agent2 RAG rule result (check_for_validation / check_mdd_keywords /
    check_documents_with_llm) into the 'RAG Agent Rules' card schema (mirrors app.py's
    right column)."""
    return {
        "rule_id": r.get("rule_id", r.get("check_id", "?")),
        "flag": r.get("flag", r.get("title", "")),
        "suggestion": r.get("suggestion", r.get("detail", "")),
        "severity": str(r.get("severity", "medium")).upper(),
        "status": r.get("status", "WARN"),
        "source": _display_framework_name(r.get("source", "")),
        "principle": r.get("principle", ""),
        "observed_value": r.get("observed_value", r.get("observed")),
        "not_verifiable": bool(r.get("not_verifiable", False)),
        "check_source": r.get("check_source", ""),
        "reasoning": r.get("reasoning", ""),
    }


def _group_stage3(report: dict, rag_results: Optional[List[dict]] = None, df=None, model_file: Optional[UploadFile] = None, intake: Optional[dict] = None, mdd_text: str = "", selected_frameworks: Optional[List[str]] = None) -> dict:
    """Map ValidationAgent2 + Agent2 RAG results into the Stage 3 UI payload.

    Returns a dict with keys: thresholdChecks, ragRules, summary, regulatoryAlignment,
    featureRelevance, raw_findings, replicated_importances, pending_llm_ids.
    """
    findings = []
    try:
        findings = report.get("findings_by_stage", {}).get("Stage 3: Conceptual Soundness", [])
    except Exception:
        findings = []

    raw_findings = [f for f in findings]
    rag_results = rag_results or []

    feature_relevance = _derive_feature_importance_payload(report, df=df, model_file=model_file, intake=intake)
    replicated = feature_relevance.get("replicated_importances", {}) or {}

    threshold_checks = [_normalize_threshold_check(f) for f in raw_findings]
    rag_rules = [_normalize_rag_rule(r) for r in rag_results]

    # Regulatory Alignment: summarize combined threshold + RAG outcomes for Stage 3.
    combined = raw_findings + rag_results
    stage3_counts = {
        "pass": sum(1 for f in combined if f.get("status") == "PASS"),
        "warn": sum(1 for f in combined if f.get("status") == "WARN"),
        "fail": sum(1 for f in combined if f.get("status") == "FAIL"),
        "pending": sum(1 for f in combined if f.get("status") == "PENDING"),
        # See _group_stage2's identical "na" bucket for the reasoning.
        "na": sum(1 for f in combined if f.get("status") not in ("PASS", "WARN", "FAIL", "PENDING")),
    }
    stage3_high_fails = [f for f in combined if f.get("status") == "FAIL" and str(f.get("severity", "")).upper() == "HIGH"]
    if len(stage3_high_fails) == 0 and stage3_counts["fail"] == 0 and stage3_counts["pending"] == 0:
        stage3_verdict = "PASS"
    elif len(stage3_high_fails) == 0 and stage3_counts["fail"] == 0:
        stage3_verdict = "CONDITIONAL"
    elif len(stage3_high_fails) <= 2:
        stage3_verdict = "CONDITIONAL"
    else:
        stage3_verdict = "FAIL"

    remediation_items = []
    if stage3_high_fails:
        remediation_items.append(f"Address {len(stage3_high_fails)} high-severity finding(s) before approval.")
    if stage3_counts["warn"]:
        remediation_items.append(f"Document and remediate {stage3_counts['warn']} warning(s) in the MDD or model controls.")
    if not remediation_items:
        remediation_items.append("No material remediation required at this stage.")

    regulatory_references = sorted({_display_framework_name(f.get("source")) for f in combined if f.get("source")})
    if not regulatory_references:
        if selected_frameworks:
            regulatory_references = [_display_framework_name(fw) for fw in selected_frameworks]
        else:
            regulatory_references = ["SS1/23", "SS11/13"]

    regulatory = {
        "verdict": stage3_verdict,
        "counts": stage3_counts,
        "remediation_summary": " ".join(remediation_items),
        "regulatory_references": regulatory_references,
        "high_severity_fails": [_normalize_finding(f) for f in stage3_high_fails],
    }

    pending_llm_ids = [
        r.get("check_id", r.get("rule_id"))
        for r in rag_results
        if r.get("check_source") == "keyword_search" and r.get("status") != "PASS"
    ]

    return {
        "thresholdChecks": threshold_checks,
        "ragRules": rag_rules,
        "summary": {
            "total": len(combined),
            "pass": stage3_counts["pass"],
            "warn": stage3_counts["warn"],
            "fail": stage3_counts["fail"],
            "pending": stage3_counts["pending"],
            "na": stage3_counts["na"],
        },
        "regulatoryAlignment": regulatory,
        "featureRelevance": feature_relevance,
        "raw_findings": raw_findings,
        "replicated_importances": replicated,
        "pending_llm_ids": list(dict.fromkeys(pending_llm_ids)),
    }


# Placeholder text for LLM-reviewed rules when the MDD is present but the
# (slow) LLM call is deferred to the follow-up /llm-check request.
_LLM_QUEUED_REASON = "LLM review not run yet — queued as a follow-up request for the uploaded MDD."


@app.post("/validation/stage2/run")
async def validation_stage2_run(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    intake_json: Optional[str] = Form(None),
    mdd_file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Run Stage 2 Data Validation checks and return mapped JSON.

    Mirrors /validation/stage3/run exactly, one stage over: quantitative
    ValidationAgent2 findings tagged "Stage 2: Data Validation", plus the
    RAG rule-matching pipeline (rag_store/val_mdd_rules.json, stage ==
    "data_validation") — quantitative dataset-metric rules via
    check_for_validation, and a keyword-search cross-check of the MDD text
    via check_mdd_keywords. Same SourceAgent2 instance and same call
    pattern Stage 3 already uses successfully, just a different stage key.
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

    selected_frameworks = intake.get("frameworks") if isinstance(intake, dict) else None

    mdd_text = ""
    if mdd_file is not None:
        try:
            # See /validation/stage3/run — parse_mdd_file needs the sync
            # file-like wrapper or every keyword-search RAG rule silently
            # sees empty MDD content and reports 0 keyword hits.
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
        except Exception:
            mdd_text = ""

    report = run_validation_agent2(df, intake, mdd_text)

    rag_results: List[dict] = []
    source_agent = _load_source_agent2()
    if source_agent is not None:
        try:
            rag_results.extend(source_agent.check_for_validation("data_validation", {}, frameworks=selected_frameworks))
        except Exception:
            pass

        # Conceptual/qualitative rules are judged by the LLM-based agent, but
        # that call (Deloitte Agent / Ollama fallback) can take several
        # seconds to tens of seconds — too slow to block this endpoint's
        # response. So this endpoint always asks check_documents_with_llm
        # for the fast, no-network PENDING stub (pass {} regardless of
        # mdd_text) so quantitative results render immediately; the actual
        # LLM verdicts are fetched afterward by the frontend via
        # /validation/stage2/llm-check (see mapped["llm_pending"] below).
        try:
            rag_results.extend(source_agent.check_documents_with_llm(
                {}, stage="data_validation", frameworks=selected_frameworks,
                skip_reason=_LLM_QUEUED_REASON if mdd_text else "No document uploaded yet.",
            ))
        except Exception:
            pass

    mapped = _group_stage2(report, rag_results=rag_results, selected_frameworks=selected_frameworks)
    mapped["llm_ran"] = False
    # True when there's MDD text for the frontend to send to
    # /validation/stage2/llm-check as a fast follow-up call.
    mapped["llm_pending"] = bool(mdd_text)
    mapped["timestamp"] = pd.Timestamp.now().isoformat()

    return mapped


@app.post("/validation/stage3/run")
async def validation_stage3_run(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    intake_json: Optional[str] = Form(None),
    mdd_file: Optional[UploadFile] = File(None),
    model_file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Run Stage 3 Conceptual Soundness checks and return mapped JSON.

    Accepts the same upload pattern as other endpoints. Keeps calculations server-side.
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

    selected_frameworks = intake.get("frameworks") if isinstance(intake, dict) else None

    mdd_text = ""
    if mdd_file is not None:
        try:
            # parse_mdd_file expects a sync file-like object with .name/.seek()/
            # .read() (ported from Streamlit's UploadedFile). FastAPI's UploadFile
            # is async, so calling parse_mdd_file(mdd_file) directly silently
            # "succeeds" but reads the repr of an unawaited coroutine instead of
            # the document text — every keyword-search RAG rule then sees empty/
            # garbage MDD content and reports 0 keyword hits. Reach through to
            # the underlying SpooledTemporaryFile, same fix already applied in
            # /validation/replication.
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
        except Exception:
            mdd_text = ""

    # Run the full ValidationAgent2 to reuse replicated_importances if available,
    # but prefer to extract Stage 3 findings only for response.
    report = run_validation_agent2(df, intake, mdd_text)

    # RAG rule-matching pipeline (mirrors app.py:5202-5231): quantitative rules
    # checked against dataset metrics, plus a keyword-search cross-check of the
    # MDD text for qualitative rules. Without this, only the 11 threshold checks
    # (3.1-3.11) are returned and the "RAG Agent Rules" column has nothing to show.
    rag_results: List[dict] = []
    source_agent = _load_source_agent2()
    if source_agent is not None:
        corr_max = 0.0
        if df is not None:
            try:
                numeric_df = df.select_dtypes(include=["number"])
                if numeric_df.shape[1] >= 2:
                    corr_matrix = numeric_df.corr().abs().values
                    np.fill_diagonal(corr_matrix, 0.0)
                    corr_max = float(corr_matrix.max())
            except Exception:
                corr_max = 0.0

        try:
            rag_results.extend(source_agent.check_for_validation("conceptual_soundness", {
                "correlation_max": corr_max,
            }, frameworks=selected_frameworks))
        except Exception:
            pass

        # Conceptual/qualitative rules are judged by the LLM-based agent, but
        # that call can take several seconds to tens of seconds — too slow
        # to block this endpoint's response. So this endpoint always asks
        # check_documents_with_llm for the fast, no-network PENDING stub
        # (pass {} regardless of mdd_text) so quantitative results render
        # immediately; the actual LLM verdicts are fetched afterward by the
        # frontend via /validation/stage3/llm-check (see
        # mapped["llm_pending"] below).
        try:
            rag_results.extend(source_agent.check_documents_with_llm(
                {}, stage="conceptual_soundness", frameworks=selected_frameworks,
                skip_reason=_LLM_QUEUED_REASON if mdd_text else "No document uploaded yet.",
            ))
        except Exception:
            pass

    mapped = _group_stage3(report, rag_results=rag_results, df=df, model_file=model_file, intake=intake, mdd_text=mdd_text, selected_frameworks=selected_frameworks)
    # add top-level metadata
    mapped["llm_ran"] = False
    # True when there's MDD text for the frontend to send to
    # /validation/stage3/llm-check as a fast follow-up call.
    mapped["llm_pending"] = bool(mdd_text)
    mapped["timestamp"] = pd.Timestamp.now().isoformat()

    try:
        persistence.log_event(
            persistence.VALIDATION_PIPELINE_LOG,
            stage="conceptual_soundness",
            payload={
                # Registered model chosen at Intake (intake_json), so the
                # Data & Model Soundness resume can be scoped to it.
                **registered_run_identity((intake or {}).get("registered_model_id") if isinstance(intake, dict) else None, df),
                # H2: the dataset bytes as received, so a restore can be scoped
                # to the exact file the browser has loaded.
                "dataset_file_sha256": source_fingerprint(file, csv_text) if df is not None else None,
                "summary": mapped.get("summary"),
                "verdict": mapped.get("regulatoryAlignment", {}).get("verdict"),
            },
            full_payload=mapped,
        )
    except Exception as e:
        print(f"[persistence] failed to log conceptual_soundness: {e}")

    return mapped


@app.post("/validation/stage7/run")
async def validation_stage7_run(
    intake_json: Optional[str] = Form(None),
    mdd_file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Run Stage 7 Regulatory Compliance checks (7.1-7.10).

    Mirrors app.py's render_val_regulatory() Tab 1: hardcoded keyword/threshold
    checks against the MDD text and intake_json (not RAG-based, unlike Stage 3).
    Reuses ValidationAgent2.check_regulatory_compliance() via run_all_checks(),
    same pattern as /validation/stage3/run.

    If the user selected specific regulatory frameworks on Stage 1, findings
    are filtered post-hoc by their `source`/`principle` fields before being
    normalized for the frontend.
    """
    intake = {}
    if intake_json:
        try:
            intake = json.loads(intake_json)
        except Exception:
            intake = {}

    selected_frameworks = intake.get("frameworks") if isinstance(intake, dict) else None

    mdd_text = ""
    if mdd_file is not None:
        try:
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
        except Exception:
            mdd_text = ""

    report = run_validation_agent2(None, intake, mdd_text)
    findings = report.get("findings_by_stage", {}).get("Stage 7: Regulatory Compliance", [])

    if selected_frameworks:
        findings = [f for f in findings if _rule_matches_frameworks(f, selected_frameworks)]

    checks = [_normalize_threshold_check(f) for f in findings]

    summary = {
        "total": len(checks),
        "pass": sum(1 for c in checks if c.get("status") == "PASS"),
        "warn": sum(1 for c in checks if c.get("status") == "WARN"),
        "fail": sum(1 for c in checks if c.get("status") == "FAIL"),
        "pending": sum(1 for c in checks if c.get("status") == "PENDING"),
        # If a check is explicitly pending it must be counted in Pending, not
        # in N/A. N/A is for checks intentionally excluded from this stage.
        "na": sum(1 for c in checks if c.get("status") not in ("PASS", "WARN", "FAIL", "PENDING")),
    }

    return {"checks": checks, "summary": summary}


@app.post("/validation/parse-mdd")
async def validation_parse_mdd(
    mdd_file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Parse an uploaded Model Development Document (PDF/DOCX/TXT) and extract
    any reported metrics it contains. Backs the "Upload & Parse" control on
    the Model Intake screen — was previously called by the frontend with no
    matching route registered here, which is what produced the 404.
    """
    try:
        mdd_document_path = _save_uploaded_mdd(mdd_file)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save MDD: {exc}")

    try:
        mdd_file.file.seek(0)
        mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse MDD: {exc}")

    metrics = extract_metrics_from_mdd(mdd_text)
    return {"mdd_text": mdd_text, "metrics": metrics, "mdd_document_path": mdd_document_path}


# ── Final-verdict evidence gate ──────────────────────────────────────────────
# The final verdict may only rest on a Model Replication run that the server
# itself reloads from the validation log and verifies: it really ran, for
# this model, on this exact dataset, with every mandatory check executed.
# Metrics posted by the browser are never trusted for the verdict, and
# developer-reported values are only ever the comparator inside R4.2/R4.3.
# 4: R4.5 / R4.6 redesigned (stability_checks.py)
# 5: evidence completeness — stress, fairness, data quality, independence and
#    MDD evidence resolved server-side; missing mandatory evidence blocks any
#    approval (assess_evidence_completeness).
# 6: operating-threshold provenance (L10) and split methodology (L11) are
#    blocking lineage checks; thresholds are never optimised on test rows.
# 7: R4.5 / R4.6 count only with proof of independent seed executions
#    (distinct test-row fingerprints); chronological splits are NOT_ASSESSED.
VERDICT_POLICY_VERSION = 7
MANDATORY_REPLICATION_CHECKS: Dict[str, str] = {
    "R4.1": "End-to-end training",
    "R4.2": "Reproduced AUC vs original model",
    "R4.3": "Reproduced Gini / KS vs original model",
    "R4.5": "Feature stability across repeated runs",
    "R4.6": "Predictive performance stability across repeated runs",
    "R4.7": "Train/test separation (no contamination)",
}
# Registered-model reproduction requirements (Phase 3): both reproductions
# must succeed, and every lineage check except library versions must pass.
REQUIRED_REPRODUCTION_STATUS = {
    "exact_artifact_reproduction": "REPRODUCED",
    "independent_training_reproduction": "REPRODUCED",
}
NON_BLOCKING_LINEAGE_CHECKS = {"L8"}  # library versions: WARN is disclosed, not blocking
# R4.7 used to be a hard-coded PASS (audit finding H1) and was excluded here.
# It is now built from executed evidence (split_integrity.py) and is
# mandatory, so nothing is excluded. Kept (empty) for API compatibility.
EXCLUDED_REPLICATION_CHECKS: Dict[str, str] = {}
REQUIRED_REPLICATION_METRICS = ("roc_auc", "gini", "ks")
# Must match exactly. The registered Model Inventory ID is the primary model
# identity (names are informational); dataset_name is recorded for the report
# only — the content fingerprint (dataset_sha256) is the dataset identity.
_IDENTITY_FIELDS = ("registered_model_id", "dataset_sha256")


def _is_finite_number(value: Any) -> bool:
    try:
        return value is not None and not isinstance(value, bool) and bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


# ── Evidence completeness (verdict policy 5) ────────────────────────────────
# Which evidence the final verdict needs, besides Model Replication (assessed
# separately by assess_replication_evidence). Mandatory and applicable
# conditional evidence that is missing, unverified or incomplete is an
# evidence GAP: it blocks APPROVED / CONDITIONALLY APPROVED and is reported as
# NOT ASSESSED — never counted as a model failure. Browser-posted results and
# flags are never evidence.
EVIDENCE_POLICY: Dict[str, Dict[str, str]] = {
    "replication": {"requirement": "mandatory", "title": "Model Replication",
                    "source": "verified replication run (assess_replication_evidence)"},
    "data_quality": {"requirement": "mandatory", "title": "Data quality profile",
                     "source": "computed by the server from the validation dataset fingerprinted for this verdict"},
    "independence": {"requirement": "mandatory", "title": "Validation independence attestation",
                     "source": "attestation recorded server-side (POST /validation/independence/attest) for this registered model and training"},
    "mdd": {"requirement": "mandatory", "title": "Model Development Document",
            "source": "MDD text submitted for review (document content, not a result)"},
    "stress_testing": {"requirement": "mandatory", "title": "Stress testing & backtesting",
                       "source": "persisted stress_testing run for this registered model, training and dataset"},
    "fair_lending": {"requirement": "conditional", "title": "Fair lending bias check",
                     "source": "persisted fair_lending_bias run for this registered model, training and dataset; "
                               "applicable when the dataset has protected-characteristic columns"},
    "benchmark": {"requirement": "optional", "title": "Benchmarking",
                  "source": "verified Benchmarking run (assess_benchmark_evidence)"},
}
EVIDENCE_STATUSES = ("PASS", "FAIL", "WARN", "PENDING", "NOT_ASSESSED", "N/A")
BLOCKING_EVIDENCE_STATUSES = {"PENDING", "NOT_ASSESSED"}


def _evidence_item(key: str, status: str, detail: str, **extra) -> Dict[str, Any]:
    assert status in EVIDENCE_STATUSES, status
    policy = EVIDENCE_POLICY[key]
    return {"evidence": key, "title": policy["title"], "requirement": policy["requirement"], "status": status,
            "detail": detail, "source": policy["source"], **extra}


_NOT_REGISTERED_EVALUATION = (
    "it did not evaluate the registered model's scoring bundle (evaluation mode: {mode}); an independent refit "
    "cannot serve as evidence for the registered model"
)


def _linked_stage_run(stage: str, explicit_run_id: Optional[str], claimed: Dict[str, Any],
                      require_dataset: bool, require_registered_evaluation: bool = False
                      ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """A persisted run of `stage` that belongs to this validation: the same
    registered model, the model's CURRENT training run and (when required)
    the same dataset fingerprint. An explicit run ID is verified, never
    trusted; without one, the newest matching current-format run is used.
    Returns (run, None) or (None, reason)."""
    reg_id = claimed.get("registered_model_id")
    if not reg_id:
        return None, "No registered model ID, so no run can be linked to the model under validation."
    current_training = registered_run_identity(reg_id)["training_run_id"]
    if not current_training:
        return None, f"Registered model {reg_id} has no recorded training lineage, so no run can be linked to its current training."
    sha = claimed.get("dataset_sha256")
    if require_dataset and not sha:
        return None, "The validation dataset was not identified, so no run can be linked to it."
    if explicit_run_id:
        run = persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, explicit_run_id)
        if run is None:
            return None, f"Run {explicit_run_id} was not found in the validation log."
        summary = run.get("summary") or {}
        if run.get("stage") != stage:
            return None, f"Run {explicit_run_id} is a '{run.get('stage')}' run, not a '{stage}' run."
        if run.get("record_status") != "current":
            return None, f"Run {explicit_run_id} is a legacy record: {run.get('record_status_reason')}"
        if summary.get("registered_model_id") != reg_id:
            return None, f"Run {explicit_run_id} was recorded for registered model '{summary.get('registered_model_id') or 'none'}', not '{reg_id}'."
        if summary.get("training_run_id") != current_training:
            return None, f"Run {explicit_run_id} used training {summary.get('training_run_id') or 'unrecorded'}, not the current training {current_training}."
        if require_dataset and summary.get("dataset_sha256") != sha:
            return None, f"Run {explicit_run_id} used a different dataset from this validation."
        if require_registered_evaluation and summary.get("evaluation_mode") != model_lineage.EVALUATION_MODE_REGISTERED:
            return None, f"Run {explicit_run_id} " + _NOT_REGISTERED_EVALUATION.format(mode=summary.get("evaluation_mode") or "unrecorded — refit")
        return run, None
    lineage_check = _registered_lineage_validator()

    def _validator(row: Dict[str, Any]) -> Optional[str]:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        if require_registered_evaluation and summary.get("evaluation_mode") != model_lineage.EVALUATION_MODE_REGISTERED:
            return "Run " + _NOT_REGISTERED_EVALUATION.format(mode=summary.get("evaluation_mode") or "unrecorded — refit")
        return lineage_check(row)

    found = persistence.find_latest_run(
        persistence.VALIDATION_PIPELINE_LOG, stage,
        filters={"registered_model_id": reg_id, "dataset_sha256": sha if require_dataset else None},
        include_legacy=False, validator=_validator,
    )["latest"]
    if found is None:
        scope = " on this dataset" if require_dataset else ""
        return None, f"No '{stage}' run is recorded for registered model {reg_id} (current training){scope}."
    return found, None


def _server_data_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """Missing-value and duplicate profile, same formulas as _build_data_profile."""
    rows = int(df.shape[0])
    missing_by_column = {str(c): {"count": int(df[c].isna().sum()),
                                  "percentage": round((int(df[c].isna().sum()) / rows * 100) if rows else 0.0, 4)}
                         for c in df.columns}
    duplicate_rows = int(df.duplicated().sum())
    return {"missing_by_column": missing_by_column, "duplicate_rows": duplicate_rows,
            "duplicate_rate": round((duplicate_rows / rows * 100) if rows else 0.0, 4)}


def assess_evidence_completeness(
    *,
    claimed: Dict[str, Any],
    current_df: Optional[pd.DataFrame],
    dataset_identity_source: str,
    mdd_text: Optional[str],
    stress_run_id: Optional[str] = None,
    bias_run_id: Optional[str] = None,
    independence_attestation_id: Optional[str] = None,
    governance_attestation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Server-side status of every non-replication evidence item. Returns the
    items plus the server-derived values the findings rules use."""
    items: Dict[str, Dict[str, Any]] = {}
    derived: Dict[str, Any] = {}

    # Data quality — computed here from the dataset this verdict fingerprinted.
    if current_df is not None and dataset_identity_source == "server_fingerprint":
        derived["profile"] = _server_data_profile(current_df)
        items["data_quality"] = _evidence_item("data_quality", "PASS", "Profile computed from the fingerprinted validation dataset.",
                                               dataset_sha256=claimed.get("dataset_sha256"))
    else:
        items["data_quality"] = _evidence_item("data_quality", "NOT_ASSESSED",
                                               "The validation dataset was not supplied to the verdict, so its data quality could not be assessed.")

    # Independence — a server-recorded attestation for this model's current training.
    run, reason = _linked_stage_run("independence_attestation", independence_attestation_id, claimed, require_dataset=False)
    if run is None:
        items["independence"] = _evidence_item("independence", "NOT_ASSESSED", reason)
    else:
        s = run.get("summary") or {}
        independent = s.get("independent") is True
        derived["independent"] = independent
        items["independence"] = _evidence_item(
            "independence", "PASS" if independent else "FAIL",
            f"Attested by {s.get('attested_by')} on {run.get('timestamp')}: "
            + ("validation team is independent." if independent else "independence NOT confirmed (conflict declared)."),
            run_id=run.get("run_id"))

    # MDD — the document under review must be present.
    if (mdd_text or "").strip():
        items["mdd"] = _evidence_item("mdd", "PASS", "MDD text supplied; its required sections are checked by the documentation findings.")
    else:
        items["mdd"] = _evidence_item("mdd", "NOT_ASSESSED", "No Model Development Document text was supplied, so documentation could not be reviewed.")

    # Stress testing — a persisted stress suite run.
    run, reason = _linked_stage_run("stress_testing", stress_run_id, claimed, require_dataset=True,
                                    require_registered_evaluation=True)
    if run is None:
        items["stress_testing"] = _evidence_item("stress_testing", "NOT_ASSESSED", reason)
    else:
        suite = ((run.get("full_payload") or {}).get("report") or {})
        summary = suite.get("summary") or {}
        checks = [c for c in (summary.get("checks") or []) if isinstance(c, dict)]
        directional = [d for d in (suite.get("directional") or []) if isinstance(d, dict)]
        failed = [str(c.get("id")) for c in checks if c.get("status") == "FAIL"] + [str(d.get("id")) for d in directional if d.get("status") == "FAIL"]
        if not suite.get("available"):
            status, detail = "NOT_ASSESSED", f"Stress run {run.get('run_id')} did not produce results: {suite.get('reason') or 'unavailable'}."
        elif summary.get("fail"):
            status, detail = "FAIL", f"Stress run {run.get('run_id')}: failed check(s) {', '.join(failed) or summary.get('fail')}."
        elif summary.get("pending"):
            status, detail = "PENDING", f"Stress run {run.get('run_id')}: {summary.get('pending')} check(s) could not be completed."
        elif summary.get("warn"):
            status, detail = "WARN", f"Stress run {run.get('run_id')}: {summary.get('warn')} warning(s), no failures."
        elif summary.get("pass"):
            status, detail = "PASS", f"Stress run {run.get('run_id')}: {summary.get('pass')} check(s) passed."
        else:
            status, detail = "NOT_ASSESSED", f"Stress run {run.get('run_id')} produced no assessable check."
        derived["stress_failed_checks"] = failed if status == "FAIL" else []
        items["stress_testing"] = _evidence_item(
            "stress_testing", status, detail, run_id=run.get("run_id"),
            evaluation_mode=(run.get("summary") or {}).get("evaluation_mode"),
            test_index_sha256=(run.get("summary") or {}).get("test_index_sha256"))

    # Fair lending — applicable only when protected-characteristic columns exist.
    if current_df is None or dataset_identity_source != "server_fingerprint":
        items["fair_lending"] = _evidence_item("fair_lending", "NOT_ASSESSED",
                                               "Applicability unknown: the validation dataset was not supplied to the verdict.")
    else:
        protected = detect_protected_columns(current_df)
        if not protected:
            items["fair_lending"] = _evidence_item(
                "fair_lending", "N/A",
                "Not applicable: no protected-characteristic columns were detected in the validation dataset.",
                na_reason=f"No column name contains a protected-characteristic keyword ({', '.join(sorted(PROTECTED_KEYWORDS))}).")
        else:
            run, reason = _linked_stage_run("fair_lending_bias", bias_run_id, claimed, require_dataset=True,
                                            require_registered_evaluation=True)
            if run is None:
                items["fair_lending"] = _evidence_item("fair_lending", "NOT_ASSESSED",
                                                       f"Protected columns present ({', '.join(protected)}). {reason}")
            else:
                payload = run.get("full_payload") or {}
                check = payload.get("check") if isinstance(payload.get("check"), dict) else None
                aucs = [r.get("AUC") for r in (payload.get("rows") or []) if isinstance(r, dict) and _is_finite_number(r.get("AUC"))]
                if not payload.get("success") or check is None:
                    items["fair_lending"] = _evidence_item("fair_lending", "NOT_ASSESSED",
                                                           f"Bias run {run.get('run_id')} did not complete: {payload.get('error') or 'no result'}.",
                                                           run_id=run.get("run_id"))
                else:
                    gap = round(float(max(aucs) - min(aucs)), 4) if len(aucs) >= 2 else None
                    derived["bias_auc_gap"] = gap
                    items["fair_lending"] = _evidence_item(
                        "fair_lending", str(check.get("status")) if check.get("status") in EVIDENCE_STATUSES else "WARN",
                        f"Bias run {run.get('run_id')} on '{payload.get('bias_col')}': {check.get('observed')}",
                        run_id=run.get("run_id"), protected_columns=protected,
                        evaluation_mode=(run.get("summary") or {}).get("evaluation_mode"),
                        test_index_sha256=(run.get("summary") or {}).get("test_index_sha256"))

    gaps = [i for i in items.values()
            if i["requirement"] in ("mandatory", "conditional") and i["status"] in BLOCKING_EVIDENCE_STATUSES]
    return {"policy_version": VERDICT_POLICY_VERSION, "items": items, "gaps": gaps, "complete": not gaps, "derived": derived}


def assess_replication_evidence(run_id: Optional[str], claimed: Dict[str, Any]) -> Dict[str, Any]:
    """Status is one of:
    PASS          — verified run, all mandatory checks executed and passed
    FAIL          — verified run, at least one mandatory check FAILED
    INCONCLUSIVE  — a run was supplied but cannot be trusted or is incomplete
    NOT_ASSESSED  — no replication run was supplied at all
    """
    out: Dict[str, Any] = {
        "status": None, "run_id": run_id or None, "reasons": [], "execution_failed": False,
        "identity": {}, "metrics": {}, "reference_metrics": {}, "mandatory_checks": [],
        "failed_mandatory_checks": [], "failed_other_checks": [], "executed_at": None,
    }

    def _done(status: str, *reasons: str) -> Dict[str, Any]:
        out["status"] = status
        out["reasons"].extend(r for r in reasons if r)
        return out

    if not run_id:
        return _done("NOT_ASSESSED", "No Model Replication run was supplied — replication has not been executed for this validation.")

    run = persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, run_id)
    if run is None:
        return _done("INCONCLUSIVE", f"Replication run {run_id} was not found in the validation log.")
    if run.get("stage") != "replication":
        return _done("INCONCLUSIVE", f"Run {run_id} is a '{run.get('stage')}' run, not a Model Replication run, so it cannot serve as replication evidence.")
    out["executed_at"] = run.get("timestamp")
    if run.get("record_status") == "legacy":
        return _done("INCONCLUSIVE", f"Replication run {run_id} is a legacy record: {run.get('record_status_reason')} Re-run Model Replication.")

    payload = run.get("full_payload") or {}
    report = payload.get("report") or {}
    if not payload or not report:
        return _done("INCONCLUSIVE", f"The saved record for replication run {run_id} is missing.")
    if int((report.get("metric_provenance") or {}).get("schema_version") or 0) < METRIC_PROVENANCE_SCHEMA_VERSION:
        return _done("INCONCLUSIVE", f"Replication run {run_id} predates metric provenance recording (legacy run) and cannot be verified. Re-run Model Replication.")
    if (payload.get("evidence") or {}).get("run_id") != run_id:
        return _done("INCONCLUSIVE", f"The saved record for run {run_id} does not carry a matching run identity.")

    # Identity: what the run logged must equal what this validation claims.
    summary = run.get("summary") or {}
    identity_problems: List[str] = []
    out["identity"]["dataset_name"] = {"replication_run": summary.get("dataset_name"), "current_validation": claimed.get("dataset_name")}
    out["identity"]["business_model_name"] = {"replication_run": summary.get("business_model_name"), "current_validation": claimed.get("business_model_name")}
    out["identity"]["dataset_identity_source"] = claimed.get("dataset_identity_source")
    for field in _IDENTITY_FIELDS:
        logged = summary.get(field)
        current = claimed.get(field)
        out["identity"][field] = {"replication_run": logged, "current_validation": current}
        if current in (None, ""):
            identity_problems.append(f"Current validation did not supply {field}, so the run cannot be matched to it.")
        elif logged in (None, ""):
            identity_problems.append(f"Replication run {run_id} did not record {field}.")
        elif str(logged).strip() != str(current).strip():
            identity_problems.append(f"{field} mismatch: replication ran on '{logged}', current validation is '{current}'.")

    # Optional secondary identity: the validation engagement record.
    if claimed.get("validation_model_id") and summary.get("validation_model_id") \
            and str(claimed["validation_model_id"]).strip() != str(summary["validation_model_id"]).strip():
        identity_problems.append(
            f"validation_model_id mismatch: replication recorded '{summary['validation_model_id']}', "
            f"current validation is '{claimed['validation_model_id']}'."
        )

    result = (report.get("replication") or {}).get("result") or {}
    methodology = result.get("methodology") or {}
    out["methodology"] = {
        "mode": methodology.get("mode"),
        "registered_model_id": methodology.get("registered_model_id"),
        "training_run_id": methodology.get("training_run_id"),
        "exact_artifact_reproduction": (methodology.get("exact_artifact_reproduction") or {}).get("status"),
        "independent_training_reproduction": (methodology.get("independent_training_reproduction") or {}).get("status"),
        "original_metrics_source": methodology.get("original_metrics_source"),
        "lineage_checks": methodology.get("lineage_checks") or [],
        "limitations": methodology.get("limitations") or [],
    }
    if methodology.get("mode") != model_lineage.REPLICATION_MODE_REGISTERED:
        identity_problems.append(
            "This run was an independent refit from configuration supplied on screen, not a reproduction of a "
            "registered model, so it cannot serve as replication evidence. Re-run replication for the registered model."
        )

    # The registered model must still exist and still be the same training
    # (a retrained model has a new contract; earlier reproductions are stale).
    reg_id = summary.get("registered_model_id")
    if methodology.get("mode") == model_lineage.REPLICATION_MODE_REGISTERED and not methodology.get("training_run_id"):
        # D5: without the training run it reproduced, the run cannot be
        # matched to the model's current training, so it is never trusted.
        identity_problems.append(
            f"Replication run {run_id} did not record the training run it reproduced, so it cannot be verified "
            "against the registered model's current training. Re-run replication.")
    if reg_id and methodology.get("mode") == model_lineage.REPLICATION_MODE_REGISTERED:
        reg_entry = next(
            (m for m in persistence.load_model_inventory().get("development", [])
             if isinstance(m, dict) and str(m.get("model_id") or "").strip() == str(reg_id).strip()),
            None,
        )
        current_training_run = ((reg_entry or {}).get("lineage_contract") or {}).get("training_run_id")
        if reg_entry is None:
            identity_problems.append(f"Registered model {reg_id} is no longer in the Model Inventory.")
        elif methodology.get("training_run_id") and current_training_run != methodology["training_run_id"]:
            identity_problems.append(
                f"Registered model {reg_id} has been retrained since this replication "
                f"(replicated training run {methodology.get('training_run_id')}, current {current_training_run}). Re-run replication."
            )
    if identity_problems:
        return _done("INCONCLUSIVE", *identity_problems)

    if result.get("success") is not True:
        out["execution_failed"] = True
        return _done("INCONCLUSIVE", f"Model replication did not complete: {result.get('error') or 'unknown error'}.")

    # Reproduction outcomes. A reproduction that ran and disagreed is a
    # failure of the model's reproducibility (FAIL); one that could not run
    # (artifact or configuration unavailable) leaves the question open.
    reproduction_failures: List[str] = []
    reproduction_gaps: List[str] = []
    for key, required in REQUIRED_REPRODUCTION_STATUS.items():
        step = methodology.get(key) or {}
        status = step.get("status")
        label = key.replace("_", " ").capitalize()
        if status == required:
            continue
        if status in ("MISMATCH", "DIVERGED"):
            reproduction_failures.append(f"{label}: {status} — {step.get('detail')}")
        else:
            reproduction_gaps.append(f"{label}: {status or 'NOT RUN'} — {step.get('detail') or 'not performed'}")
    for check in methodology.get("lineage_checks") or []:
        if check.get("id") not in NON_BLOCKING_LINEAGE_CHECKS and check.get("status") != "PASS":
            reproduction_gaps.append(f"Lineage check {check.get('id')} ({check.get('title')}): {check.get('status')} — {check.get('detail')}")

    metrics = result.get("metrics") or {}
    missing_metrics = [k for k in REQUIRED_REPLICATION_METRICS if not _is_finite_number(metrics.get(k))]
    out["metrics"] = {k: v for k, v in metrics.items() if _is_finite_number(v)}
    out["reference_metrics"] = dict((report.get("reference_metrics") or {}).get("values") or {})
    if missing_metrics:
        return _done("INCONCLUSIVE", f"Replication produced no valid value for: {', '.join(missing_metrics)}.")

    checks = {c.get("id"): c for c in (report.get("replication") or {}).get("checks") or [] if isinstance(c, dict)}
    not_executed: List[str] = []
    # G1: R4.5 / R4.6 rest on repeated runs; a PASS only counts when the
    # saved run proves those runs were independent (distinct test sets).
    # Runs saved before that evidence was recorded are not executed evidence.
    seed_independence = (result.get("stability") or {}).get("independence") or {}
    for check_id, title in MANDATORY_REPLICATION_CHECKS.items():
        check = checks.get(check_id)
        status = (check or {}).get("status") or "MISSING"
        if check_id in ("R4.5", "R4.6") and status == "PASS" and not seed_independence.get("independent"):
            check = {**check, "status": "NOT_ASSESSED", "observed": seed_independence.get("reason") or (
                "The run does not prove its seed executions were independent (test-row fingerprints not recorded). "
                "Re-run Model Replication.")}
            status = "NOT_ASSESSED"
        out["mandatory_checks"].append({"id": check_id, "title": title, "status": status, "observed": (check or {}).get("observed")})
        if status == "FAIL":
            out["failed_mandatory_checks"].append({"id": check_id, "title": title, "observed": check.get("observed")})
        elif status != "PASS":
            reason = "not present in the run" if check is None else f"{status}: {check.get('observed') or 'not executed'}"
            not_executed.append(f"Mandatory check {check_id} ({title}) was not completed — {reason}.")
    for check_id, check in checks.items():
        if check_id not in MANDATORY_REPLICATION_CHECKS and check_id not in EXCLUDED_REPLICATION_CHECKS and check.get("status") == "FAIL":
            out["failed_other_checks"].append({"id": check_id, "title": check.get("title"), "observed": check.get("observed")})

    if out["failed_mandatory_checks"] or reproduction_failures:
        return _done(
            "FAIL",
            *reproduction_failures,
            *[f"Mandatory check {c['id']} ({c['title']}) failed: {c['observed']}" for c in out["failed_mandatory_checks"]],
            *reproduction_gaps, *not_executed,
        )
    if reproduction_gaps or not_executed:
        return _done("INCONCLUSIVE", *reproduction_gaps, *not_executed)
    return _done("PASS", "Registered model reproduced exactly from its artifact and independently retrained from its recorded "
                         "configuration; all mandatory replication checks executed and passed on the verified run.")


def _current_lineage_contract(registered_model_id: Optional[str]) -> Optional[Dict[str, Any]]:
    model_id = (registered_model_id or "").strip()
    entry = next((m for m in persistence.load_model_inventory().get("development", [])
                  if isinstance(m, dict) and str(m.get("model_id") or "").strip() == model_id), None) if model_id else None
    contract = (entry or {}).get("lineage_contract")
    return contract if isinstance(contract, dict) else None


def assess_benchmark_evidence(run_id: Optional[str], claimed: Dict[str, Any]) -> Dict[str, Any]:
    """Benchmarking is optional for the verdict, but a supplied benchmark is
    only used if it is a current-format Benchmarking run on the same data."""
    if not run_id:
        return {"status": "NOT_SUPPLIED", "run_id": None, "reasons": [], "metrics": {}}
    out: Dict[str, Any] = {"status": "REJECTED", "run_id": run_id, "reasons": [], "metrics": {}}
    run = persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, run_id)
    if run is None:
        out["reasons"].append(f"Benchmark run {run_id} was not found in the validation log.")
        return out
    if run.get("stage") != "performance":
        out["reasons"].append(f"Run {run_id} is a '{run.get('stage')}' run, not a current Benchmarking run (legacy or wrong stage).")
        return out
    if run.get("record_status") == "legacy":
        out["reasons"].append(f"Benchmark run {run_id} is a legacy record: {run.get('record_status_reason')}")
        return out
    payload = run.get("full_payload") or {}
    report = payload.get("report") or {}
    if int((report.get("metric_provenance") or {}).get("schema_version") or 0) < METRIC_PROVENANCE_SCHEMA_VERSION:
        out["reasons"].append(f"Benchmark run {run_id} predates metric provenance recording (legacy run).")
        return out
    logged_sha = (run.get("summary") or {}).get("dataset_sha256")
    if not logged_sha or logged_sha != claimed.get("dataset_sha256"):
        out["reasons"].append("Benchmark run used a different dataset from the verified replication run.")
        return out
    summary = run.get("summary") or {}
    logged_model = summary.get("registered_model_id")
    if claimed.get("registered_model_id") and logged_model != claimed.get("registered_model_id"):
        out["reasons"].append(
            f"Benchmark run was recorded for registered model '{logged_model or 'none'}', not '{claimed.get('registered_model_id')}'."
        )
        return out
    # A matching ID label is not enough: the champion must have BEEN the
    # registered model (its verified bundle), for its current training, on
    # the registered test rows.
    if claimed.get("registered_model_id"):
        if summary.get("evaluation_mode") != model_lineage.EVALUATION_MODE_REGISTERED:
            out["reasons"].append("Benchmark champion was not the registered model's scoring bundle "
                                  f"(evaluation mode: {summary.get('evaluation_mode') or 'unrecorded — refit'}).")
            return out
        contract = _current_lineage_contract(claimed["registered_model_id"])
        if not contract or summary.get("training_run_id") != contract.get("training_run_id"):
            out["reasons"].append(f"Benchmark run used training {summary.get('training_run_id') or 'unrecorded'}, "
                                  f"not the registered model's current training.")
            return out
        if summary.get("test_index_sha256") != (contract.get("split") or {}).get("test_index_sha256"):
            out["reasons"].append("Benchmark was not evaluated on the registered model's recorded test rows.")
            return out
    bench = report.get("benchmark") or {}
    if bench.get("status") != "OK":
        out["reasons"].append(f"Benchmark run did not complete (status {bench.get('status')}).")
        return out
    out["status"] = "ACCEPTED"
    out["metrics"] = {k: v for k, v in (bench.get("metrics") or {}).items() if _is_finite_number(v)}
    out["model_name"] = bench.get("model_name")
    return out


@app.post("/validation/independence/attest")
async def record_independence_attestation(
    registered_model_id: str = Form(...),
    attested_by: str = Form(...),
    independent: bool = Form(...),
    statement: Optional[str] = Form(None),
    dataset_sha256: Optional[str] = Form(None),
    session_username: Optional[str] = Form(None),
    declared_name: Optional[str] = Form(None),
    control_state: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Record the validator's independence attestation for a registered model
    (SS1/23 P4.1). Recorded server-side — attributable, timestamped, scoped to
    the model's current training — and appended to the validation log; this,
    not a flag in the intake payload, is what the final verdict accepts.
    Unknown models are rejected. There is no user authentication in this
    backend, so `attested_by` is the name the validator supplies."""
    model_id = (registered_model_id or "").strip()
    who = (attested_by or "").strip()
    if not who:
        raise HTTPException(status_code=400, detail="attested_by is required.")
    if not attest_inventory_registration({}, model_id)["verified"]:
        raise HTTPException(status_code=404, detail=f"Registered model '{model_id}' was not found in the Development Inventory.")
    identity = registered_run_identity(model_id)
    if not identity["training_run_id"]:
        raise HTTPException(status_code=409, detail=f"Registered model '{model_id}' has no recorded training lineage to attest against.")
    sha = (dataset_sha256 or "").strip() or identity.get("dataset_sha256")
    record = {
        **identity,
        "registered_model_id": model_id,
        "training_run_id": identity.get("training_run_id"),
        "dataset_sha256": sha or None,
        "attested_by": who,
        "declared_name": (declared_name or who).strip() or who,
        "session_username": (session_username or "self-declared").strip() or "self-declared",
        "control_state": (control_state or "unknown").strip() or "unknown",
        "identity_status": "unauthenticated/self-declared",
        "independent": bool(independent),
        "statement": (statement or "").strip() or None,
        "demo_dataset": _server_demo_dataset_flag(dataset_sha256=sha),
    }
    run_id = persistence.log_event(persistence.VALIDATION_PIPELINE_LOG, stage="independence_attestation",
                                   payload=record, full_payload=record)
    return {"attestation_id": run_id, **record}


@app.post("/validation/governance/attest")
async def record_governance_attestation(
    registered_model_id: Optional[str] = Form(None),
    declared_name: Optional[str] = Form(None),
    control_state: Optional[str] = Form(None),
    session_username: Optional[str] = Form(None),
    dataset_sha256: Optional[str] = Form(None),
    training_run_id: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    statement: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Append-only governance audit event. It is logged for monitoring only and
    is never treated as verdict evidence."""
    if registered_model_id:
        model_id = (registered_model_id or "").strip()
    else:
        model_id = None
    sha = (dataset_sha256 or "").strip() or None
    record = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "control_state": (control_state or "unknown").strip() or "unknown",
        "declared_name": (declared_name or model_name or session_username or "self-declared").strip() or "self-declared",
        "session_username": (session_username or "self-declared").strip() or "self-declared",
        "identity_status": "unauthenticated/self-declared",
        "registered_model_id": model_id,
        "training_run_id": (training_run_id or "").strip() or None,
        "dataset_sha256": sha,
        "demo_dataset": _server_demo_dataset_flag(dataset_sha256=sha),
        "statement": (statement or "").strip() or None,
    }
    run_id = persistence.log_event(persistence.VALIDATION_PIPELINE_LOG, stage="governance_attestation",
                                   payload=record, full_payload=record)
    return {"governance_attestation_id": run_id, **record}


@app.post("/validation/stage8/findings")
async def validation_stage8_findings(
    intake_json: Optional[str] = Form(None),
    mdd_text: Optional[str] = Form(None),
    validation_profile_json: Optional[str] = Form(None),
    rep_metrics_json: Optional[str] = Form(None),
    benchmark_metrics_json: Optional[str] = Form(None),
    shock_result_json: Optional[str] = Form(None),
    bias_auc_gap: Optional[float] = Form(None),
    replication_run_id: Optional[str] = Form(None),
    business_model_name: Optional[str] = Form(None),
    validation_model_id: Optional[str] = Form(None),
    dataset_name: Optional[str] = Form(None),
    dataset_sha256: Optional[str] = Form(None),
    benchmark_run_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    registered_model_id: Optional[str] = Form(None),
    # Optional explicit evidence references (verified, never trusted). When
    # omitted, the newest matching run for this model/training/dataset is used.
    stress_run_id: Optional[str] = Form(None),
    bias_run_id: Optional[str] = Form(None),
    independence_attestation_id: Optional[str] = Form(None),
    governance_attestation_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Compile the Stage 8 Findings Tracker + overall verdict.

    Evidence completeness (verdict policy 5): stress testing, fair lending,
    data quality, independence and the MDD are resolved server-side (see
    EVIDENCE_POLICY / assess_evidence_completeness). Browser-posted
    `validation_profile_json`, `shock_result_json`, `bias_auc_gap` and the
    intake's `independence_confirmed` are accepted for compatibility but
    ignored. Missing mandatory evidence is reported as a NOT ASSESSED gap
    and blocks any approval; it is not counted as a model failure.

    Direct port of app.py's render_val_findings() all_findings compilation
    (app.py:7484-7617). The backend is stateless, so every piece that would
    have been st.session_state on the Streamlit side is passed in from the
    frontend's app-context instead — each already computed by an earlier
    stage's own endpoint/response. CALIBRATION_KEYWORDS/STAGING_KEYWORDS are
    imported from the same source-of-truth validation_agent2.py Stage 3 uses,
    so the keyword lists can't drift between stages.

    Evidence-based verdict (audit finding C2): replication metrics are no
    longer taken from the browser. The verdict reloads the Model Replication
    run named by `replication_run_id` from the validation log and verifies
    it (see assess_replication_evidence). If the current dataset is sent
    (`file`/`csv_text`) its fingerprint is computed here and must equal the
    replication run's; otherwise the client-supplied `dataset_sha256` is
    used. `rep_metrics_json` and `benchmark_metrics_json` are still accepted
    for API compatibility but ignored; a benchmark is only used when
    `benchmark_run_id` points to a verified current-format run.

    Verdicts: APPROVED / CONDITIONALLY APPROVED (only on verified, passing
    replication), REJECTED (a mandatory replication check failed, or the
    findings themselves warrant rejection), INCONCLUSIVE (replication
    evidence supplied but unverifiable, failed to execute, or incomplete),
    NOT ASSESSED (no replication evidence supplied).
    """
    ij: Dict[str, Any] = {}
    if intake_json:
        try:
            ij = json.loads(intake_json) or {}
        except Exception:
            ij = {}
    if isinstance(ij, dict):
        ij["frameworks"] = _sanitize_frameworks(ij.get("frameworks"))

    mdd_lower = (mdd_text or "").lower()

    # Browser-posted results and flags are never evidence. Recorded so the
    # response is explicit that they were received and not used.
    ignored_client_inputs = [
        name for name, value in (("rep_metrics_json", rep_metrics_json), ("benchmark_metrics_json", benchmark_metrics_json),
                                 ("validation_profile_json", validation_profile_json), ("shock_result_json", shock_result_json),
                                 ("bias_auc_gap", bias_auc_gap))
        if value not in (None, "")
    ]
    if "independence_confirmed" in ij:
        ignored_client_inputs.append("intake independence_confirmed (only a recorded attestation counts)")
    if governance_attestation_id:
        ignored_client_inputs.append("governance_attestation_id (audit events are not verdict evidence)")

    # Current dataset identity: fingerprinted here when the data is supplied,
    # otherwise the client's claim (weaker; recorded as such).
    dataset_identity_source = "client_claim"
    current_sha = (dataset_sha256 or "").strip() or None
    current_df: Optional[pd.DataFrame] = None
    if file is not None or csv_text:
        current_df = await _read_dataframe(file=file, csv_text=csv_text)
        server_sha = dataset_fingerprint(current_df)
        if current_sha and current_sha != server_sha:
            # Keep the server value; the mismatch with the run is reported below.
            ignored_client_inputs.append("dataset_sha256 (differs from server fingerprint of the supplied dataset)")
        current_sha = server_sha
        dataset_identity_source = "server_fingerprint"

    # The registered Model Inventory ID selected at Intake is the identity the
    # whole validation refers to; the name is informational only.
    demo_dataset = _server_demo_dataset_flag(dataset_sha256=current_sha, df=current_df)
    claimed_identity = {
        "registered_model_id": (registered_model_id or ij.get("registered_model_id") or "").strip() or None,
        "business_model_name": (business_model_name or ij.get("model_name") or "").strip() or None,
        "validation_model_id": (validation_model_id or "").strip() or None,
        "dataset_name": dataset_name,
        "dataset_sha256": current_sha,
        "dataset_identity_source": dataset_identity_source,
        "demo_dataset": demo_dataset,
    }
    rep_evidence = assess_replication_evidence((replication_run_id or "").strip() or None, claimed_identity)
    evidence_trusted = rep_evidence["status"] in ("PASS", "FAIL")
    rep_metrics: Dict[str, Any] = rep_evidence["metrics"] if evidence_trusted else {}
    bm_evidence = assess_benchmark_evidence(
        (benchmark_run_id or "").strip() or None,
        {"dataset_sha256": current_sha if evidence_trusted else None,
         "registered_model_id": claimed_identity["registered_model_id"]},
    )
    bm_metrics: Dict[str, Any] = bm_evidence["metrics"] if bm_evidence["status"] == "ACCEPTED" else {}

    completeness = assess_evidence_completeness(
        claimed=claimed_identity, current_df=current_df, dataset_identity_source=dataset_identity_source,
        mdd_text=mdd_text, stress_run_id=(stress_run_id or "").strip() or None,
        bias_run_id=(bias_run_id or "").strip() or None,
        independence_attestation_id=(independence_attestation_id or "").strip() or None,
    )
    ev = completeness["items"]
    derived = completeness["derived"]
    profile: Dict[str, Any] = derived.get("profile") or {}

    all_findings: List[Dict[str, Any]] = []

    def _gap_finding(stage: str, check: str, item: Dict[str, Any], recommendation: str, regulation: str) -> None:
        # Missing / unverified evidence: blocks approval, is not a model failure.
        all_findings.append({"stage": stage, "check": check, "severity": "HIGH",
                             "status": "PENDING" if item["status"] == "PENDING" else "NOT ASSESSED",
                             "finding": f"{item['title']} evidence {'incomplete' if item['status'] == 'PENDING' else 'missing or unverified'}: {item['detail']}",
                             "recommendation": recommendation, "regulation": regulation, "evidence_gap": True})

    # Stage 1 findings. Registration is the server's own attestation from the
    # Development Inventory (same function as Stage 2 check 1.2); the client's
    # model_inventory_registered flag is ignored.
    registration = attest_inventory_registration(ij, claimed_identity["registered_model_id"])
    if not registration["verified"]:
        all_findings.append({"stage": "Stage 1", "check": "1.2 Model Inventory",
            "severity": "HIGH", "status": "FAIL",
            "finding": "Model not registered in model inventory",
            "observed": registration["detail"],
            "recommendation": "Register model with unique ID before deployment",
            "regulation": "SS1/23 P1.2"})
    # Independence: a recorded attestation only (the intake flag is ignored).
    # Declared conflict = the existing HIGH FAIL; no attestation = evidence gap.
    if ev["independence"]["status"] == "FAIL":
        all_findings.append({"stage": "Stage 1", "check": "1.4 Independence",
            "severity": "HIGH", "status": "FAIL",
            "finding": "Validation independence not confirmed",
            "observed": ev["independence"]["detail"],
            "recommendation": "Confirm validation team has no conflict of interest",
            "regulation": "SS1/23 P4.1"})
    elif ev["independence"]["status"] in BLOCKING_EVIDENCE_STATUSES:
        _gap_finding("Stage 1", "1.4 Independence", ev["independence"],
                     "Record the validator's independence attestation for this registered model.", "SS1/23 P4.1")

    # Stage 2 findings — computed by the server from the fingerprinted
    # dataset (never the browser's profile). missing_by_column is
    # {col: {"count": int, "percentage": float 0-100}} and duplicate_rate is
    # a 0-100 percentage, so divide by 100 to match the 0-1 fractions the
    # legacy Streamlit thresholds use.
    if ev["data_quality"]["status"] in BLOCKING_EVIDENCE_STATUSES:
        _gap_finding("Stage 2", "2.0 Data Quality", ev["data_quality"],
                     "Supply the validation dataset so its data quality can be profiled.", "SS1/23 P3.2")
    missing_by_column = profile.get("missing_by_column") or {}
    if missing_by_column:
        def _pct(entry: Any) -> float:
            return float(entry.get("percentage", 0)) if isinstance(entry, dict) else float(entry or 0)
        worst_col = max(missing_by_column, key=lambda c: _pct(missing_by_column[c]))
        missing_max = _pct(missing_by_column[worst_col]) / 100.0
        if missing_max > 0.20:
            all_findings.append({"stage": "Stage 2", "check": "2.2 Missing Data",
                "severity": "HIGH", "status": "FAIL",
                "finding": f"Column '{worst_col}' has {missing_max:.1%} missing values",
                "recommendation": "Investigate data pipeline — impute or remove high-missing columns",
                "regulation": "SS1/23 P3.2"})
    dupes = float(profile.get("duplicate_rate") or 0) / 100.0
    if dupes > 0.01:
        all_findings.append({"stage": "Stage 2", "check": "2.9 Duplicates",
            "severity": "MEDIUM", "status": "WARN",
            "finding": f"Duplicate row rate: {dupes:.2%}",
            "recommendation": "Remove duplicate records before training",
            "regulation": "SS1/23 P3.2"})

    # MDD findings — Calibration/IFRS 9 Staging are Regulatory Compliance
    # checks (now under Stage 6: Explainability and Fairness); Limitations/
    # Assumptions are Conceptual Soundness checks and Forward-Looking
    # Documentation is a Data Validation check (both now under Stage 2:
    # Data & Model Soundness). These used to be lumped into one "Stage 3/7"
    # bucket before Conceptual Soundness (old Stage 3) and Regulatory
    # Compliance (old Stage 7) were merged into different current stages —
    # they no longer belong together at all, let alone under one heading.
    for kw, check, finding, rec, reg, sev, stage in [
        (CALIBRATION_KEYWORDS, "7.1 Calibration",
         "MDD has no calibration section", "Document PD calibration methodology", "IFRS 9 §5.5", "HIGH", "Stage 6"),
        (STAGING_KEYWORDS, "7.2 IFRS 9 Staging",
         "MDD does not describe IFRS 9 staging logic", "Add Stage 1/2/3 classification and SICR triggers", "IFRS 9 §5.5.3", "HIGH", "Stage 6"),
        (["limitation", "weakness"], "3.4 Limitations",
         "MDD has no limitations section", "Add model limitations per SS1/23 P3.4", "SS1/23 P3.4", "HIGH", "Stage 2"),
        (["assumption"], "3.3 Assumptions",
         "MDD does not document model assumptions", "Document all modelling assumptions with rationale", "SS1/23 P3.3", "MEDIUM", "Stage 2"),
        (["macro", "gdp", "unemployment"], "2.4b Forward-Looking Documentation (MDD)",
         "MDD does not reference macro/forward-looking variables", "Add macro overlay per IFRS 9 B5.5.49", "IFRS 9 B5.5.49", "MEDIUM", "Stage 2"),
    ]:
        # No MDD at all is missing evidence (one gap below), not five
        # documentation failures; section checks run only on a supplied MDD.
        if ev["mdd"]["status"] in BLOCKING_EVIDENCE_STATUSES:
            break
        # Same word-start matching as ValidationAgent2 (no fragments inside words).
        if not any(ValidationAgent2._keyword_in(k, mdd_lower) for k in kw):
            all_findings.append({"stage": stage, "check": check,
                "severity": sev, "status": "FAIL",
                "finding": finding, "recommendation": rec, "regulation": reg})
    if ev["mdd"]["status"] in BLOCKING_EVIDENCE_STATUSES:
        _gap_finding("Stage 2", "3.0 Model Documentation", ev["mdd"],
                     "Supply the Model Development Document so its required sections can be reviewed.", "SS1/23 P3.1")

    # Stage 3 (Model Replication) — from the server-verified replication run
    # only. Evidence-gap findings carry status NOT ASSESSED / INCONCLUSIVE
    # (not FAIL) so a missing run blocks approval without being miscounted
    # as a model defect.
    rep_status = rep_evidence["status"]
    stated_auc = rep_evidence["reference_metrics"].get("roc_auc") if evidence_trusted else None
    rep_auc = rep_metrics.get("roc_auc")
    if rep_status == "NOT_ASSESSED":
        all_findings.append({"stage": "Stage 3", "check": "3.0 Replication Evidence",
            "severity": "HIGH", "status": "NOT ASSESSED",
            "finding": "Model Replication has not been executed for this validation.",
            "recommendation": "Run Model Replication (Stage 3) for this model and dataset before a verdict can be issued.",
            "regulation": "SS1/23 P4.1"})
    elif rep_status == "INCONCLUSIVE":
        all_findings.append({"stage": "Stage 3", "check": "3.0 Replication Evidence",
            "severity": "HIGH", "status": "INCONCLUSIVE",
            "finding": ("Model could not be replicated. " if rep_evidence["execution_failed"] else "Replication evidence could not be verified or is incomplete. ")
                + " ".join(rep_evidence["reasons"]),
            "recommendation": "Re-run Model Replication for this model and dataset, with developer-reported reference metrics, and resolve the issues listed.",
            "regulation": "SS1/23 P4.1"})
    else:
        for check in rep_evidence["failed_mandatory_checks"]:
            all_findings.append({"stage": "Stage 3", "check": f"{check['id']} {check['title']}",
                "severity": "HIGH", "status": "FAIL",
                "finding": str(check.get("observed") or "Mandatory replication check failed."),
                "recommendation": "Developer must reconcile the submitted model with the independent replication before resubmission.",
                "regulation": "SS1/23 P4.1"})
        for check in rep_evidence["failed_other_checks"]:
            all_findings.append({"stage": "Stage 3", "check": f"{check['id']} {check.get('title') or ''}".strip(),
                "severity": "MEDIUM", "status": "FAIL",
                "finding": str(check.get("observed") or "Replication check failed."),
                "recommendation": "Review and document the difference against the developer-reported results.",
                "regulation": "SS1/23 P4.1"})

    # Stage 4 (Performance Testing, was old Stage 5) — metric thresholds,
    # evaluated only on the verified replication run's computed metrics.
    for metric, val, threshold, op, check, reg, sev in [
        ("ROC-AUC", rep_auc, 0.70, ">=", "5.1 ROC-AUC", "SS1/23 P4.1", "HIGH"),
        ("Recall", rep_metrics.get("recall"), 0.60, ">=", "5.2 Recall", "SS1/23 P4.4", "HIGH"),
        ("Gini", rep_metrics.get("gini"), 0.40, ">=", "5.3 Gini", "SS11/13 §10.3", "HIGH"),
        ("Brier Score", rep_metrics.get("brier_score"), 0.25, "<=", "5.4 Brier", "SS11/13 §10.5", "MEDIUM"),
    ]:
        if val is not None:
            failed = (op == ">=" and val < threshold) or (op == "<=" and val > threshold)
            if failed:
                all_findings.append({"stage": "Stage 4", "check": check,
                    "severity": sev, "status": "FAIL",
                    "finding": f"{metric} = {val:.4f} — below regulatory minimum {op} {threshold}",
                    "recommendation": f"Model does not meet minimum {metric} threshold — consider retraining or additional data",
                    "regulation": reg})

    # Stage 4 (Performance Testing) — benchmarking
    if bm_metrics and rep_auc:
        bm_auc = bm_metrics.get("roc_auc", 0)
        if rep_auc < bm_auc - 0.02:
            all_findings.append({"stage": "Stage 4", "check": "5.B Benchmarking",
                "severity": "MEDIUM", "status": "WARN",
                "finding": f"Submitted model AUC ({rep_auc:.4f}) underperforms benchmark ({bm_auc:.4f})",
                "recommendation": "Marginal improvement over baseline may not justify model complexity — review feature set",
                "regulation": "SS1/23 P4.2"})
    if bm_evidence["status"] == "REJECTED":
        all_findings.append({"stage": "Stage 4", "check": "5.B Benchmark Evidence",
            "severity": "LOW", "status": "WARN",
            "finding": "Benchmark result not used: " + " ".join(bm_evidence["reasons"]),
            "recommendation": "Re-run Benchmarking on the same dataset as the replication run.",
            "regulation": "SS1/23 P4.2"})

    # Stage 5 (Stress & Backtesting) — from the persisted stress suite run.
    # (The former 6.1 rule read a browser-posted manual shock result, which is
    # not persisted and is no longer evidence; the suite's own 6.1 sensitivity
    # check is part of the stress run.) Failures keep the MEDIUM/WARN level the
    # stress finding always had.
    if ev["stress_testing"]["status"] == "FAIL":
        all_findings.append({"stage": "Stage 5", "check": "6.0 Stress & Backtesting",
            "severity": "MEDIUM", "status": "WARN",
            "finding": ev["stress_testing"]["detail"],
            "recommendation": "Review the failed stress / backtesting checks and document their impact.",
            "regulation": "SS1/23 P4.3"})
    elif ev["stress_testing"]["status"] in BLOCKING_EVIDENCE_STATUSES:
        _gap_finding("Stage 5", "6.0 Stress & Backtesting", ev["stress_testing"],
                     "Run Stress Testing (Stage 5) for this registered model on this dataset.", "SS1/23 P4.3")

    # Stage 6 (Explainability and Fairness) — bias, from the persisted bias run
    # (the browser's bias_auc_gap is ignored). Same HIGH rule as before.
    bias_gap = derived.get("bias_auc_gap")
    if bias_gap is not None and bias_gap > 0.10:
        all_findings.append({"stage": "Stage 6", "check": "8.2 Fair Lending",
            "severity": "HIGH", "status": "FAIL",
            "finding": f"AUC gap of {bias_gap:.4f} across protected groups",
            "recommendation": "Investigate discriminatory bias — model may treat protected groups unfairly",
            "regulation": "SS1/23 P1.3"})
    elif ev["fair_lending"]["status"] in BLOCKING_EVIDENCE_STATUSES:
        _gap_finding("Stage 6", "8.2 Fair Lending", ev["fair_lending"],
                     "Run the Fair Lending Bias Check for this registered model on this dataset.", "SS1/23 P1.3")

    # ── Overall verdict ──────────────────────────────────────────────
    high_count = sum(1 for f in all_findings if f["severity"] == "HIGH" and f["status"] == "FAIL")
    medium_count = sum(1 for f in all_findings if f["severity"] == "MEDIUM")
    total_count = len(all_findings)

    # Findings-based outcome (unchanged rule), then gated by the replication
    # evidence: approval of any kind requires a verified, passing replication.
    if high_count == 0 and medium_count <= 2:
        findings_verdict = "APPROVED"
        findings_desc = "No HIGH findings and at most 2 MEDIUM findings, with independent replication verified and passed."
    elif high_count <= 2:
        findings_verdict = "CONDITIONALLY APPROVED"
        findings_desc = f"Model may proceed subject to resolution of {high_count} HIGH finding(s) within agreed timeframe."
    else:
        findings_verdict = "REJECTED"
        findings_desc = f"Model has {high_count} unresolved HIGH findings. Resubmission required after remediation."

    # Demo validation is only recognized from server-side evidence.
    # Browser-supplied demo markers are never authority and are ignored here;
    # a real Demo A/B run must match the verified demo dataset fingerprint.
    is_demo = bool(demo_dataset or _is_demo_dataset_fingerprint(claimed_identity.get("dataset_sha256")))
    if is_demo:
        verdict = "INCONCLUSIVE"
        verdict_desc = "Demo data is not a registered model and cannot support a final approval or conditional approval verdict."
    elif rep_status == "FAIL":
        verdict = "REJECTED"
        verdict_desc = "Independent replication failed one or more mandatory checks: " + " ".join(rep_evidence["reasons"])
    elif findings_verdict == "REJECTED":
        verdict, verdict_desc = findings_verdict, findings_desc
    elif rep_status == "NOT_ASSESSED":
        verdict = "NOT ASSESSED"
        verdict_desc = "No verdict can be issued: Model Replication has not been executed for this validation."
    elif rep_status == "INCONCLUSIVE":
        verdict = "INCONCLUSIVE"
        verdict_desc = "No approval can be issued: " + " ".join(rep_evidence["reasons"])
    elif completeness["gaps"]:
        # A passing replication alone is not enough: approval of any kind
        # needs every mandatory (and applicable conditional) evidence item.
        verdict = "INCONCLUSIVE"
        verdict_desc = "No approval can be issued: mandatory evidence is missing or unverified — " + "; ".join(
            f"{g['title']}: {g['detail']}" for g in completeness["gaps"])
    else:
        verdict, verdict_desc = findings_verdict, findings_desc

    # ── Monitoring & revalidation recommendations, driven by model tier ──
    tier = ij.get("model_tier", "Tier 2")
    if "1" in str(tier) or "High" in str(tier):
        monitoring_frequency = "Monthly"
        revalidation_trigger = "Annual (or triggered by PSI > 0.25 or AUC drop > 0.05)"
    elif "2" in str(tier) or "Medium" in str(tier):
        monitoring_frequency = "Quarterly"
        revalidation_trigger = "18-monthly (or triggered by significant portfolio change)"
    else:
        monitoring_frequency = "Semi-annually"
        revalidation_trigger = "Every 2 years (or triggered by model change)"

    result = {
        "findings": all_findings,
        "verdict": verdict,
        "verdict_desc": verdict_desc,
        "demo_dataset": demo_dataset,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": max(total_count - high_count - medium_count, 0),
        "total_count": total_count,
        "monitoring_frequency": monitoring_frequency,
        "revalidation_trigger": revalidation_trigger,
        "model_tier": tier,
        # Developer-reported AUC (reference) and the verified replication's
        # computed AUC — both taken from the verified replication run.
        "stated_auc": stated_auc,
        "replicated_auc": rep_auc,
        "verdict_basis": {
            "policy_version": VERDICT_POLICY_VERSION,
            "findings_verdict": findings_verdict,
            "replication": rep_evidence,
            "benchmark": {k: bm_evidence.get(k) for k in ("status", "run_id", "reasons", "metrics", "model_name")},
            "mandatory_replication_checks": MANDATORY_REPLICATION_CHECKS,
            "excluded_replication_checks": EXCLUDED_REPLICATION_CHECKS,
            "dataset_identity_source": dataset_identity_source,
            "ignored_client_inputs": ignored_client_inputs,
            "evidence_completeness": {k: v for k, v in completeness.items() if k != "derived"},
            "evidence_policy": EVIDENCE_POLICY,
        },
    }

    try:
        persistence.log_event(
            persistence.VALIDATION_PIPELINE_LOG,
            stage="findings",
            payload={
                "verdict": verdict,
                "high_count": high_count,
                "medium_count": medium_count,
                "total_count": total_count,
                "verdict_policy_version": VERDICT_POLICY_VERSION,
                "replication_run_id": rep_evidence.get("run_id"),
                "replication_evidence_status": rep_status,
                "registered_model_id": claimed_identity.get("registered_model_id"),
                # The registered model's training this verdict was issued
                # against; a retrain makes the verdict stale in history.
                "training_run_id": registered_run_identity(claimed_identity.get("registered_model_id"))["training_run_id"],
                "business_model_name": claimed_identity.get("business_model_name"),
                "dataset_sha256": claimed_identity.get("dataset_sha256"),
                "demo_dataset": demo_dataset,
                # The exact evidence runs this verdict rests on.
                "evidence_run_ids": {k: v.get("run_id") for k, v in completeness["items"].items() if v.get("run_id")},
                "evidence_complete": completeness["complete"],
            },
            full_payload=result,
        )
    except Exception as e:
        print(f"[persistence] failed to log findings: {e}")

    return result


@app.post("/validation/stage2/llm-check")
async def validation_stage2_llm(
    intake_json: Optional[str] = Form(None),
    mdd_file: Optional[UploadFile] = File(None),
    only_rule_ids: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Run the LLM-based conceptual check for Stage 2 documentation items.

    Mirrors /validation/stage3/llm-check exactly, one stage over. Called by
    the frontend as a fast follow-up to /validation/stage2/run (which
    returns PENDING stubs for these rules so the page isn't blocked on the
    LLM call — see that endpoint's mapped["llm_pending"] flag).
    """
    print("========== ENTERED validation_stage2_llm ==========")
    agent = _load_source_agent2()

    intake = {}
    if intake_json:
        try:
            intake = json.loads(intake_json)
        except Exception:
            intake = {}

    selected_frameworks = intake.get("frameworks") if isinstance(intake, dict) else None

    mdd_text = ""
    if mdd_file is not None:
        try:
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
        except Exception:
            mdd_text = ""

    if agent is None:
        raise HTTPException(status_code=500, detail="Agent2 RAG component unavailable")

    docs = {"MDD": mdd_text} if mdd_text else {}

    only_ids = None
    if only_rule_ids:
        only_ids = [s.strip() for s in only_rule_ids.split(",") if s.strip()]

    try:
        llm_results = agent.check_documents_with_llm(
            docs,
            stage="data_validation",
            only_rule_ids=only_ids,
            frameworks=selected_frameworks,
        )
    except Exception as e:
        import traceback

        print("\n========== FULL EXCEPTION ==========")
        traceback.print_exc()
        print("====================================\n")
        raise HTTPException(status_code=500, detail=f"LLM deep-check failed: {e}")

    return {"llm_results": [_normalize_rag_rule(r) for r in llm_results]}


@app.post("/validation/stage3/llm-check")
async def validation_stage3_llm(
    intake_json: Optional[str] = Form(None),
    mdd_file: Optional[UploadFile] = File(None),
    only_rule_ids: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Run optional LLM deep-checks for Stage 3 documentation items.

    Mirrors app.py's "Run AI Deep-Check" button (app.py:5257-5293): sends the MDD
    text plus the RAG rule set to the LLM checker agent for rules keyword search
    could not confidently resolve. Uses the source-of-truth Agent2 (val_mdd_rules.json),
    not the local 24-06 Agent2, which has no LLM/RAG rule methods.
    """
    print("========== ENTERED validation_stage3_llm ==========")
    agent = _load_source_agent2()

    intake = {}
    if intake_json:
        try:
            intake = json.loads(intake_json)
        except Exception:
            intake = {}

    selected_frameworks = intake.get("frameworks") if isinstance(intake, dict) else None

    mdd_text = ""
    if mdd_file is not None:
        try:
            # See /validation/stage3/run — parse_mdd_file needs the sync
            # underlying file, not the async UploadFile directly.
            mdd_text = parse_mdd_file(_sync_file_like(mdd_file))
        except Exception:
            mdd_text = ""

    if agent is None:
        raise HTTPException(status_code=500, detail="Agent2 RAG component unavailable")

    docs = {"MDD": mdd_text} if mdd_text else {}

    only_ids = None
    if only_rule_ids:
        only_ids = [s.strip() for s in only_rule_ids.split(",") if s.strip()]

    try:
        print("BEFORE check_documents_with_llm")
        llm_results = agent.check_documents_with_llm(
            docs,
            stage="conceptual_soundness",
            only_rule_ids=only_ids,
            frameworks=selected_frameworks,
        )
        print("========== LLM RESULTS DEBUG ==========")
        print("LLM_RESULTS_COUNT:", len(llm_results))
        print("LLM_RESULTS:", llm_results)
        print("======================================")
    except Exception as e:
        import traceback

        print("\n========== FULL EXCEPTION ==========")
        traceback.print_exc()
        print("====================================\n")
        raise HTTPException(status_code=500, detail=f"LLM deep-check failed: {e}")

    return {"llm_results": [_normalize_rag_rule(r) for r in llm_results]}
