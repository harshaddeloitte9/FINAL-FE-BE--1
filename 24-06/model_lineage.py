"""
model_lineage.py — registered-model lineage capture and reproduction.

Two halves:

1. Capture (called from /models/train): the training pipeline is fitted by
   `fit_training_pipeline` (the exact code /models/train has always run, moved
   here so reproduction re-runs the same path), then `build_lineage_contract`
   records everything needed to reproduce it and `save_scoring_bundle` writes
   the fitted scoring chain (imputer → feature engineering → pipeline) to disk
   with a SHA-256.

2. Reproduction (called from /validation/replication with a registered model
   ID): `run_registered_replication` verifies lineage, then performs
     A. exact artifact reproduction — re-scores the stored artifact on the
        re-derived original test split and checks it matches the metrics
        recorded at training, and
     B. independent training reproduction — retrains from the recorded
        configuration (never registry defaults) and compares to A.
   Anything missing is reported as a limitation; nothing is substituted.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import platform
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import persistence
import split_integrity as si
import stability_checks as stability
from evaluate_new import compute_binary_metrics
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering
from model_selector import get_hyperparameter_grid, get_model_instance
from preprocessing_new import (
    SemanticImputer,
    build_preprocessing_report,
    finalize_xy,
    select_imputation_strategy,
)
from train_new import compute_split_stats, split_data, train_model
from utils import detect_column_types, detect_task_type

LINEAGE_CONTRACT_VERSION = 1
REPLICATION_MODE_REGISTERED = "registered_model_reproduction"
REPLICATION_MODE_UNREGISTERED = "unregistered_independent_refit"

# Exact artifact reproduction re-scores the same fitted object on the same
# rows: any difference beyond float noise means it is not the same model.
EXACT_TOLERANCE = 1e-9
# Independent retraining from the recorded configuration. Deterministic
# estimators reproduce exactly; the tolerance only absorbs numerical noise
# from different BLAS/library builds.
INDEPENDENT_TOLERANCE = {"roc_auc": 0.005, "gini": 0.01, "ks": 0.01,
                         "accuracy": 0.01, "precision": 0.02, "recall": 0.02, "f1": 0.02}
COMPARED_METRICS = ("roc_auc", "gini", "ks", "accuracy", "precision", "recall", "f1")


# ── Shared training path (moved verbatim from /models/train) ───────────────

def fit_training_pipeline(
    df: pd.DataFrame,
    *,
    target_col: str,
    model_name: str,
    estimator_name: str,
    test_size: float,
    val_size: float,
    random_seed: int,
    use_cv: bool,
    cv_folds: int,
    use_hyperopt: bool,
    scale_pos_weight: float,
    manual_params_dict: Optional[Dict[str, Any]],
    use_feature_engineering: bool,
    use_oot: bool,
    date_col: Optional[str],
    contract_payload: Dict[str, Any],
    combined_treatment_overrides: Dict[str, str],
    combined_drop_cols: List[str],
    combined_transform_choices: Dict[str, Any],
    combined_strategy_override: Optional[str],
    estimator: Any = None,
) -> Dict[str, Any]:
    """Fit the development pipeline exactly as /models/train does.

    `estimator`, when given, is used as the (unfitted) model instead of
    building one from estimator_name/manual_params — reproduction passes an
    estimator constructed from the recorded fitted parameters. Hyperparameter
    search is not allowed together with it: the recorded parameters already
    are the search's winner."""
    if estimator is not None and use_hyperopt:
        raise ValueError("Hyperparameter search cannot be combined with a fixed recorded estimator.")

    col_types = detect_column_types(df)
    task_type = detect_task_type(df[target_col])
    X, y, _ = finalize_xy(df, col_types, target_col)
    raw_feature_columns = [str(c) for c in X.columns]
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=random_seed,
    )

    effective_preprocessing_contract = {
        "source": "data_preparation" if combined_treatment_overrides or combined_drop_cols or combined_transform_choices or combined_strategy_override else "fallback",
        "applied_treatment_map": {
            **(contract_payload.get("applied_treatment_map") or {}),
            **(contract_payload.get("treatment_map") or {}),
        },
        "treatment_overrides": combined_treatment_overrides,
        "drop_cols": combined_drop_cols,
        "dropped_columns": combined_drop_cols,
        "transform_choices": combined_transform_choices,
        "applied_transform_choices": combined_transform_choices,
        "strategy_override": combined_strategy_override,
        "imputation_strategy": None,
    }

    if combined_drop_cols:
        X_train = X_train.drop(columns=[c for c in combined_drop_cols if c in X_train.columns], errors="ignore")
        X_val = X_val.drop(columns=[c for c in combined_drop_cols if c in X_val.columns], errors="ignore")
        X_test = X_test.drop(columns=[c for c in combined_drop_cols if c in X_test.columns], errors="ignore")
    # Kept only as evidence for the R4.7 split-integrity checks; the
    # training path below is unchanged.
    X_train_pre_impute, X_test_pre_impute = X_train, X_test

    semantic_imputer = None
    if combined_treatment_overrides or combined_transform_choices or combined_strategy_override:
        treatment_map: Dict[str, Dict[str, Any]] = {}
        for col, treatment in combined_treatment_overrides.items():
            if not isinstance(treatment, str):
                continue
            treatment_map[col] = {
                "treatment": treatment,
                "reason": "Applied from Data Preparation preprocessing contract.",
                "evidence": {},
            }
        if not treatment_map and isinstance(contract_payload.get("applied_treatment_map"), dict):
            for col, value in contract_payload["applied_treatment_map"].items():
                if isinstance(value, dict):
                    treatment_map[col] = {
                        "treatment": value.get("treatment") or "statistical",
                        "reason": value.get("reason") or "Applied from Data Preparation preprocessing contract.",
                        "evidence": value.get("evidence") or {},
                    }
        if treatment_map:
            statistical_cols = [c for c, v in treatment_map.items() if v.get("treatment") == "statistical"]
            imputation_strategy = select_imputation_strategy(X_train, statistical_cols)
            if combined_strategy_override in ("mice", "knn", "median") and statistical_cols:
                imputation_strategy = {
                    "method": combined_strategy_override,
                    "reason": "Manually overridden by Data Preparation contract.",
                    "diagnostics": imputation_strategy.get("diagnostics", {}),
                }
            effective_preprocessing_contract["imputation_strategy"] = imputation_strategy
            col_types_for_fit = {k: [c for c in v if c not in combined_drop_cols] for k, v in col_types.items()}
            semantic_imputer = SemanticImputer(
                col_types=col_types_for_fit,
                treatment_map=treatment_map,
                strategy_choice=imputation_strategy,
            )
            semantic_imputer.fit(X_train)
            X_train = semantic_imputer.transform(X_train)
            X_val = semantic_imputer.transform(X_val)
            X_test = semantic_imputer.transform(X_test)

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
    dates_test = None
    if origination_date_col and origination_date_col in df.columns:
        try:
            dates_test = df.loc[X_test.index, origination_date_col]
        except Exception:
            dates_test = None
    prep_report = build_preprocessing_report(
        X_train.assign(**{target_col: y_train}),
        col_types,
        target_col,
        transform_choices=combined_transform_choices if isinstance(combined_transform_choices, dict) else {},
    )
    fe_summary = None
    plan = None
    X_train_pre_fe = X_train
    if use_feature_engineering:
        plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
        X_train, fe_summary = apply_feature_engineering(X_train, plan)
        X_val, _ = apply_feature_engineering(X_val, plan)
        X_test, _ = apply_feature_engineering(X_test, plan)

    if estimator is not None:
        model = estimator
    elif manual_params_dict is not None:
        model = get_model_instance(estimator_name, task_type)
        valid_keys = set(model.get_params().keys())
        manual_params_dict = {k: v for k, v in manual_params_dict.items() if k in valid_keys}
        model = type(model)(**manual_params_dict)
    else:
        model = get_model_instance(
            estimator_name,
            task_type,
            scale_pos_weight=scale_pos_weight if estimator_name == "XGBoost" else None,
        )
    param_grid = None
    if use_hyperopt:
        param_grid = get_hyperparameter_grid(estimator_name, task_type)
    pipeline, training_info, real_feature_names = train_model(
        X_train, y_train,
        col_types=col_types,
        target_col=target_col,
        prep_report=prep_report,
        model=model,
        use_cv=use_cv,
        cv_folds=cv_folds,
        use_hyperopt=use_hyperopt,
        param_grid=param_grid,
        task_type=task_type,
        model_name=model_name,
        dates_train=dates_train,
        use_oot=use_oot,
    )

    return {
        "col_types": col_types, "task_type": task_type,
        "X_train": X_train, "X_val": X_val, "X_test": X_test,
        "y_train": y_train, "y_val": y_val, "y_test": y_test,
        "effective_preprocessing_contract": effective_preprocessing_contract,
        "semantic_imputer": semantic_imputer,
        "origination_date_col": origination_date_col, "dates_test": dates_test,
        "prep_report": prep_report, "plan": plan, "fe_summary": fe_summary,
        "manual_params_dict": manual_params_dict, "model": model,
        "pipeline": pipeline, "training_info": training_info, "real_feature_names": real_feature_names,
        "dataset_columns": [str(c) for c in df.columns],
        "raw_feature_columns": raw_feature_columns,
        "model_input_columns": [str(c) for c in X_train.columns],
        # R4.7 evidence (see split_integrity.py).
        "X_train_pre_impute": X_train_pre_impute, "X_test_pre_impute": X_test_pre_impute,
        "X_train_pre_fe": X_train_pre_fe, "dates_train": dates_train,
        "use_oot": use_oot, "target_col": target_col,
    }


# ── Small helpers ───────────────────────────────────────────────────────────

def library_versions() -> Dict[str, Optional[str]]:
    versions: Dict[str, Optional[str]] = {"python": platform.python_version()}
    for name in ("numpy", "pandas", "sklearn", "xgboost", "lightgbm", "joblib"):
        try:
            versions[name] = getattr(importlib.import_module(name), "__version__", None)
        except Exception:
            versions[name] = None
    return versions


def index_fingerprint(index) -> str:
    return hashlib.sha256(",".join(str(i) for i in index).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe_value(value: Any):
    """Return (ok, value): ok is False for values that cannot round-trip
    through JSON exactly (objects, callables)."""
    if value is None or isinstance(value, (bool, str)):
        return True, value
    if isinstance(value, (int, np.integer)):
        return True, int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        # Non-finite floats (e.g. XGBoost's missing=nan) are encoded so the
        # contract stays strict-JSON (API responses reject NaN) and decodes
        # back to the exact same value in build_estimator.
        return True, f if np.isfinite(f) else {"__float__": repr(f)}
    if isinstance(value, (list, tuple)):
        items = [_json_safe_value(v) for v in value]
        return all(ok for ok, _ in items), [v for _, v in items]
    if isinstance(value, dict):
        items = {str(k): _json_safe_value(v) for k, v in value.items()}
        return all(ok for ok, _ in items.values()), {k: v for k, (_, v) in items.items()}
    return False, repr(value)


def estimator_spec(pipeline) -> Dict[str, Any]:
    model = pipeline.named_steps["model"]
    params: Dict[str, Any] = {}
    unserializable: List[str] = []
    for key, value in model.get_params(deep=False).items():
        ok, safe = _json_safe_value(value)
        params[key] = safe
        if not ok:
            unserializable.append(key)
    return {
        "module": type(model).__module__,
        "class": type(model).__name__,
        "params": params,
        "unserializable_params": unserializable,
    }


def _decode_param(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__float__"}:
        return float(value["__float__"])
    if isinstance(value, list):
        return [_decode_param(v) for v in value]
    if isinstance(value, dict):
        return {k: _decode_param(v) for k, v in value.items()}
    return value


def build_estimator(spec: Dict[str, Any]):
    cls = getattr(importlib.import_module(spec["module"]), spec["class"])
    return cls(**{k: _decode_param(v) for k, v in spec["params"].items()})


def with_gini_ks(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Add Gini and KS derived from compute_binary_metrics' own (rounded)
    outputs, so recorded and re-scored metrics are derived identically."""
    out = dict(metrics or {})
    if out.get("roc_auc") is not None and out.get("gini") is None:
        out["gini"] = round(2.0 * float(out["roc_auc"]) - 1.0, 4)
    if out.get("ks") is None and out.get("ks_statistic") is not None:
        out["ks"] = out["ks_statistic"]
    return out


def binary_metrics(pipeline, X: pd.DataFrame, y_true: pd.Series, threshold: Optional[float]) -> Dict[str, Any]:
    """Exactly the metric function /models/train uses (compute_binary_metrics
    with the recorded threshold), plus Gini/KS derived from its outputs."""
    proba_2d = pipeline.predict_proba(X)
    y_pred = pipeline.predict(X)
    return with_gini_ks(compute_binary_metrics(np.asarray(y_true), y_pred, proba_2d, threshold=threshold))


def compare_metrics(original: Dict[str, Any], other: Dict[str, Any], tolerance) -> Dict[str, Any]:
    rows = []
    for key in COMPARED_METRICS:
        a, b = original.get(key), other.get(key)
        if a is None or b is None:
            rows.append({"metric": key, "original": a, "reproduced": b, "abs_diff": None, "tolerance": None, "within": None})
            continue
        diff = abs(float(a) - float(b))
        tol = tolerance if isinstance(tolerance, float) else tolerance.get(key, 0.0)
        rows.append({"metric": key, "original": float(a), "reproduced": float(b), "abs_diff": diff, "tolerance": tol, "within": diff <= tol})
    compared = [r for r in rows if r["within"] is not None]
    return {"rows": rows, "all_within": bool(compared) and all(r["within"] for r in compared)}


# ── Capture at training time ────────────────────────────────────────────────

def save_scoring_bundle(fit: Dict[str, Any], *, model_id: str, training_run_id: str) -> Dict[str, str]:
    """Persist the full scoring chain the trained pipeline needs, so the
    registered artifact can be re-scored exactly later."""
    target_dir = persistence.APP_DATA_DIR / "model_artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{model_id}_{training_run_id}.joblib"
    joblib.dump({
        "lineage_contract_version": LINEAGE_CONTRACT_VERSION,
        "pipeline": fit["pipeline"],
        "semantic_imputer": fit["semantic_imputer"],
        "fe_plan": fit["plan"],
        "drop_cols": list(fit["effective_preprocessing_contract"].get("drop_cols") or []),
        "model_input_columns": fit["model_input_columns"],
    }, path)
    return {"path": str(path.relative_to(persistence.BACKEND_DIR)), "sha256": _file_sha256(path)}


def build_lineage_contract(
    fit: Dict[str, Any],
    *,
    model_id: str,
    training_run_id: str,
    business_model_name: str,
    estimator_name: str,
    target_col: str,
    dataset_name: Optional[str],
    dataset_sha256: str,
    dataset_shape: List[int],
    training_config: Dict[str, Any],
    threshold: Optional[float],
    development_metrics: Dict[str, Any],
    artifact: Dict[str, str],
) -> Dict[str, Any]:
    pre = fit["effective_preprocessing_contract"]
    ti = fit["training_info"] or {}
    return {
        "contract_version": LINEAGE_CONTRACT_VERSION,
        "model_id": model_id,
        "training_run_id": training_run_id,
        "business_model_name": business_model_name,
        "estimator_name": estimator_name,
        "task_type": fit["task_type"],
        "target_col": target_col,
        "dataset": {"name": dataset_name, "sha256": dataset_sha256, "shape": dataset_shape},
        "features": {
            # Columns of the dataset as supplied to training (order matters),
            # then the features after finalize_xy, then the model's inputs.
            "dataset_columns": fit["dataset_columns"],
            "raw_feature_columns": fit["raw_feature_columns"],
            "model_input_columns": fit["model_input_columns"],
            "final_feature_names": [str(c) for c in (fit["real_feature_names"] or [])],
        },
        "preprocessing": {
            "treatment_overrides": pre.get("treatment_overrides") or {},
            "applied_treatment_map": pre.get("applied_treatment_map") or {},
            "drop_cols": list(pre.get("drop_cols") or []),
            "transform_choices": pre.get("transform_choices") or {},
            "strategy_override": pre.get("strategy_override"),
            "imputation_strategy_method": (pre.get("imputation_strategy") or {}).get("method"),
            "semantic_imputer_fitted": fit["semantic_imputer"] is not None,
            "encoding": {c: (info or {}).get("encoding") for c, info in ((fit["prep_report"] or {}).get("categorical") or {}).items()},
            "scaling": (fit["prep_report"] or {}).get("transform_recommendations") or {},
            "feature_engineering_enabled": bool(training_config.get("use_feature_engineering")),
        },
        "split": {
            "method": "train_new.split_data (stratified when possible) after preprocessing_new.finalize_xy",
            "test_size": training_config.get("test_size"),
            "val_size": training_config.get("val_size"),
            "random_seed": training_config.get("random_seed"),
            "test_index_sha256": index_fingerprint(fit["X_test"].index),
            "train_rows": int(len(fit["X_train"])), "val_rows": int(len(fit["X_val"])), "test_rows": int(len(fit["X_test"])),
        },
        "training": {
            "use_cv": bool(training_config.get("use_cv")),
            "cv_folds": training_config.get("cv_folds"),
            "use_hyperopt": bool(training_config.get("use_hyperopt")),
            "use_oot": bool(training_config.get("use_oot")),
            "date_col": training_config.get("date_col"),
            "threshold": threshold,
            "best_params": {k: _json_safe_value(v)[1] for k, v in (ti.get("best_params") or {}).items()},
            "cv_mean": ti.get("cv_mean"),
        },
        "estimator": estimator_spec(fit["pipeline"]),
        "development_metrics": {k: v for k, v in with_gini_ks(development_metrics).items() if k in COMPARED_METRICS + ("brier_score", "pr_auc", "threshold_used")},
        "libraries": library_versions(),
        "artifact": artifact,
        "created_at": pd.Timestamp.now().isoformat(),
    }


# ── Reproduction ────────────────────────────────────────────────────────────

def _check(checks: List[Dict[str, Any]], check_id: str, title: str, status: str, detail: str) -> bool:
    checks.append({"id": check_id, "title": title, "status": status, "detail": detail})
    return status == "PASS"


def _fit_from_contract(df: pd.DataFrame, contract: Dict[str, Any], *, random_seed=None, extra_drop=None, use_cv=None):
    pre = contract["preprocessing"]
    tr = contract["training"]
    sp = contract["split"]
    drop = list(pre.get("drop_cols") or []) + list(extra_drop or [])
    return fit_training_pipeline(
        df,
        target_col=contract["target_col"],
        model_name=contract["business_model_name"],
        estimator_name=contract["estimator_name"],
        test_size=sp["test_size"], val_size=sp["val_size"],
        random_seed=sp["random_seed"] if random_seed is None else random_seed,
        use_cv=tr["use_cv"] if use_cv is None else use_cv,
        cv_folds=tr.get("cv_folds") or 5,
        use_hyperopt=False,
        scale_pos_weight=1.0,
        manual_params_dict=None,
        use_feature_engineering=bool(pre.get("feature_engineering_enabled")),
        use_oot=tr["use_oot"],
        date_col=tr.get("date_col"),
        contract_payload={"applied_treatment_map": pre.get("applied_treatment_map") or {}},
        combined_treatment_overrides=pre.get("treatment_overrides") or {},
        combined_drop_cols=drop,
        combined_transform_choices=pre.get("transform_choices") or {},
        combined_strategy_override=pre.get("strategy_override"),
        estimator=build_estimator(contract["estimator"]),
    )


def _transform_for_bundle(bundle: Dict[str, Any], X_raw: pd.DataFrame) -> pd.DataFrame:
    X = X_raw.drop(columns=[c for c in bundle.get("drop_cols") or [] if c in X_raw.columns], errors="ignore")
    if bundle.get("semantic_imputer") is not None:
        X = bundle["semantic_imputer"].transform(X)
    if bundle.get("fe_plan") is not None:
        X, _ = apply_feature_engineering(X, bundle["fe_plan"])
    return X[bundle["model_input_columns"]]


def registered_split_integrity(fit: Dict[str, Any], df: pd.DataFrame, contract: Dict[str, Any]) -> Dict[str, Any]:
    """R4.7 evidence for a registered reproduction (see split_integrity.py).
    Training-only refits are built once and shared by the preprocessing and
    model checks; a second refit is only made if outputs differ (to tell
    contamination from non-determinism)."""
    X_train, X_test, y_train, y_test = fit["X_train"], fit["X_test"], fit["y_train"], fit["y_test"]
    sp = contract["split"]
    refits: List[Any] = []

    def _refit(n: int):
        while len(refits) <= n:
            pipe, _, _ = train_model(
                X_train, y_train, col_types=fit["col_types"], target_col=fit["target_col"], prep_report=fit["prep_report"],
                model=build_estimator(contract["estimator"]), use_cv=False, task_type=fit["task_type"],
                dates_train=fit["dates_train"], use_oot=fit["use_oot"],
            )
            refits.append(pipe)
        return refits[n]

    def _sequence(extract):
        calls = {"n": 0}

        def _next():
            out = extract(_refit(calls["n"]))
            calls["n"] += 1
            return out
        return _next

    subchecks = [
        si.check_disjoint(X_train.index, fit["X_val"].index, X_test.index),
        si.check_duplicate_records(fit["X_train_pre_impute"], y_train, fit["X_test_pre_impute"], y_test),
        si.check_component("S3", "Preprocessing depends on training rows only",
                           lambda: fit["pipeline"].named_steps["preprocessor"].transform(X_test),
                           _sequence(lambda p: p.named_steps["preprocessor"].transform(X_test)),
                           "The fitted preprocessing"),
        si.check_component("S4", "Model fitted on training rows only",
                           lambda: fit["pipeline"].predict_proba(X_test)[:, 1],
                           _sequence(lambda p: p.predict_proba(X_test)[:, 1]),
                           "The model's predicted probabilities"),
    ]
    if fit["semantic_imputer"] is not None:
        from sklearn.base import clone
        subchecks.append(si.check_component(
            "S3b", "Missing-value imputation fitted on training rows only",
            lambda: fit["semantic_imputer"].transform(fit["X_test_pre_impute"]),
            lambda: clone(fit["semantic_imputer"]).fit(fit["X_train_pre_impute"]).transform(fit["X_test_pre_impute"]),
            "The imputed test data",
        ))
    subchecks.append(si.check_fe_plan(
        fit["plan"],
        (lambda: analyze_for_feature_engineering(fit["X_train_pre_fe"], y_train, fit["col_types"], fit["task_type"]))
        if fit["plan"] is not None else None,
        bool(contract["preprocessing"].get("feature_engineering_enabled")),
    ))

    def _resplit_test_index():
        X_all, y_all, _ = finalize_xy(df, detect_column_types(df), contract["target_col"])
        return split_data(X_all, y_all, test_size=sp["test_size"], val_size=sp["val_size"],
                          task_type="binary", random_state=sp["random_seed"])[2].index

    subchecks.append(si.check_split_reproducible(X_test.index, _resplit_test_index, sp.get("test_index_sha256")))
    return si.build_r47(subchecks)


def run_registered_replication(
    df: pd.DataFrame,
    entry: Dict[str, Any],
    *,
    dataset_sha256: str,
    seeds: List[int],
    compute_stability: bool = True,
) -> Dict[str, Any]:
    """Reproduce a registered development model. Returns a result dict in the
    same shape run_replication() returns (success/metrics/seed_aucs/ablation/
    split_stats/cv_mean_auc/pipeline/X_test/y_test/y_proba...) plus
    `methodology` (what was verified, what was reproduced, what could not be)
    and `original_metrics` (the comparator for R4.x)."""
    t0 = time.time()
    contract = entry.get("lineage_contract") if isinstance(entry, dict) else None
    lineage_checks: List[Dict[str, Any]] = []
    limitations: List[str] = []
    methodology: Dict[str, Any] = {
        "mode": REPLICATION_MODE_REGISTERED,
        "registered_model_id": entry.get("model_id"),
        "registered_model_name": entry.get("model_name"),
        "training_run_id": (contract or {}).get("training_run_id"),
        "contract_version": (contract or {}).get("contract_version"),
        "estimator": (contract or {}).get("estimator"),
        "preprocessing": (contract or {}).get("preprocessing"),
        "features": (contract or {}).get("features"),
        "split": (contract or {}).get("split"),
        "lineage_checks": lineage_checks,
        "exact_artifact_reproduction": {"status": "NOT_RUN", "detail": None},
        "independent_training_reproduction": {"status": "NOT_RUN", "detail": None},
        "original_metrics_source": None,
        "limitations": limitations,
        "libraries": {"recorded": (contract or {}).get("libraries"), "current": library_versions()},
    }
    out: Dict[str, Any] = {
        "success": False, "error": None, "metrics": {}, "seed_aucs": [], "seed_runs": [], "ablation_runs": [],
        "split_integrity": None, "stability": None, "cv_mean_auc": None,
        "split_stats": {}, "timing_s": 0.0, "ablation": {}, "pipeline": None, "X_train": None, "X_test": None,
        "y_train": None, "y_test": None, "y_proba": None, "y_pred": None, "feature_importance": [],
        "use_feature_engineering": None, "model_params_used": None,
        "methodology": methodology, "original_metrics": {},
    }

    def _stop(message: str) -> Dict[str, Any]:
        out["error"] = message
        out["timing_s"] = round(time.time() - t0, 1)
        return out

    _check(lineage_checks, "L1", "Registered model found", "PASS", f"{entry.get('model_id')} — {entry.get('model_name')}")
    if not isinstance(contract, dict) or contract.get("contract_version") != LINEAGE_CONTRACT_VERSION:
        _check(lineage_checks, "L2", "Training lineage recorded", "FAIL",
               "No lineage contract is recorded for this model (it was registered before lineage capture, or "
               "training did not complete registration). Retrain the model to record its configuration.")
        limitations.append("Reproduction cannot be performed: the original training configuration was never recorded.")
        methodology["exact_artifact_reproduction"] = {"status": "UNAVAILABLE", "detail": "No lineage contract."}
        methodology["independent_training_reproduction"] = {"status": "CANNOT_RUN", "detail": "No lineage contract."}
        return _stop("Registered model has no recorded training lineage; reproduction cannot be performed.")
    _check(lineage_checks, "L2", "Training lineage recorded", "PASS",
           f"Contract v{contract['contract_version']} from training run {contract.get('training_run_id')}")

    if contract.get("task_type") != "binary":
        limitations.append(f"Reproduction is implemented for binary classification only (model task: {contract.get('task_type')}).")
        _check(lineage_checks, "L3", "Supported task type", "FAIL", str(contract.get("task_type")))
        return _stop("Unsupported task type for registered reproduction.")

    target = contract["target_col"]
    target_ok = _check(lineage_checks, "L3", "Target column", "PASS" if target in df.columns else "FAIL",
                       f"'{target}' {'present' if target in df.columns else 'missing from supplied dataset'}")

    recorded_columns = list(contract["features"].get("dataset_columns") or [])
    present = [str(c) for c in df.columns]
    missing = [c for c in recorded_columns if c not in present]
    extra = [c for c in present if c not in recorded_columns]
    order_ok = not missing and not extra and present == recorded_columns
    if not recorded_columns:
        feature_detail = "Training dataset columns were not recorded."
    elif missing or extra:
        feature_detail = f"Missing: {missing or 'none'}; not in training: {extra or 'none'}"
    elif not order_ok:
        feature_detail = "Same columns as training but in a different order."
    else:
        feature_detail = f"All {len(recorded_columns)} training columns present in the original order; no additional columns."
    features_ok = _check(lineage_checks, "L4", "Feature columns match training", "PASS" if order_ok else "FAIL", feature_detail)
    required = list(contract["features"]["raw_feature_columns"])

    recorded_sha = contract["dataset"]["sha256"]
    dataset_ok = _check(
        lineage_checks, "L5", "Dataset identical to training dataset", "PASS" if dataset_sha256 == recorded_sha else "FAIL",
        f"Fingerprint {dataset_sha256[:12]}… " + ("matches" if dataset_sha256 == recorded_sha
                                                  else f"differs from training dataset {recorded_sha[:12]}… ({contract['dataset'].get('name')})"),
    )

    est = contract.get("estimator") or {}
    params_ok = _check(
        lineage_checks, "L6", "Original hyperparameters recorded",
        "PASS" if est.get("params") and est.get("class") and not est.get("unserializable_params") else "FAIL",
        f"{est.get('class')} with {len(est.get('params') or {})} parameters" if est.get("params") and not est.get("unserializable_params")
        else ("Parameters not recorded." if not est.get("params") else f"Parameters not exactly recordable: {est.get('unserializable_params')}"),
    )
    pre = contract.get("preprocessing")
    preprocessing_ok = _check(
        lineage_checks, "L7", "Preprocessing configuration recorded",
        "PASS" if isinstance(pre, dict) and "drop_cols" in pre and "treatment_overrides" in pre else "FAIL",
        "Treatment map, dropped columns, transforms, imputation and feature-engineering settings recorded."
        if isinstance(pre, dict) and "drop_cols" in pre else "Preprocessing configuration not recorded.",
    )
    recorded_libs = contract.get("libraries") or {}
    current_libs = library_versions()
    lib_diffs = {k: (recorded_libs.get(k), current_libs.get(k)) for k in recorded_libs if recorded_libs.get(k) != current_libs.get(k)}
    _check(lineage_checks, "L8", "Library versions match training", "PASS" if not lib_diffs else "WARN",
           "Identical." if not lib_diffs else "Differences (recorded → current): " + ", ".join(f"{k} {a} → {b}" for k, (a, b) in lib_diffs.items()))
    if lib_diffs:
        limitations.append("Library versions differ from training; small numerical differences are possible.")

    if not (target_ok and features_ok and dataset_ok):
        methodology["exact_artifact_reproduction"] = {"status": "NOT_RUN", "detail": "Dataset does not match the training dataset."}
        methodology["independent_training_reproduction"] = {"status": "CANNOT_RUN", "detail": "Dataset does not match the training dataset."}
        limitations.append("Reproduction requires the original training dataset; the supplied data differs.")
        return _stop("Supplied dataset does not match the registered model's training dataset.")

    # Re-derive the original split exactly as training did.
    col_types = detect_column_types(df)
    X_all, y_all, _ = finalize_xy(df, col_types, target)
    sp = contract["split"]
    Xtr, Xv, Xte_raw, ytr, yv, yte = split_data(
        X_all, y_all, test_size=sp["test_size"], val_size=sp["val_size"], task_type="binary", random_state=sp["random_seed"],
    )
    same_test_rows = index_fingerprint(Xte_raw.index) == sp["test_index_sha256"]
    no_overlap = not (set(Xtr.index) | set(Xv.index)) & set(Xte_raw.index)
    split_detail = (
        f"Test rows {len(Xte_raw)} (recorded {sp.get('test_rows')}); test-set fingerprint "
        + ("identical to training" if same_test_rows else "differs from training")
        + ("; no train/test overlap." if no_overlap else "; train and test rows overlap.")
    )
    split_ok = _check(lineage_checks, "L9", "Original train/test split reproduced",
                      "PASS" if same_test_rows and no_overlap else "FAIL", split_detail)
    threshold = contract["training"].get("threshold")
    recorded_metrics = contract.get("development_metrics") or {}

    # A. Exact artifact reproduction.
    original_metrics: Dict[str, Any] = {}
    artifact = contract.get("artifact") or {}
    artifact_path = persistence.BACKEND_DIR / artifact["path"] if artifact.get("path") else None
    exact: Dict[str, Any] = {"status": "UNAVAILABLE", "detail": None, "artifact_sha256": artifact.get("sha256")}
    if artifact_path is None or not artifact_path.exists():
        exact["detail"] = "The registered model artifact file is missing."
    elif _file_sha256(artifact_path) != artifact.get("sha256"):
        exact["detail"] = "Artifact integrity check failed: file SHA-256 differs from the one recorded at registration."
    elif not split_ok:
        exact["status"] = "NOT_RUN"
        exact["detail"] = "Original test split could not be reproduced."
    else:
        try:
            bundle = joblib.load(artifact_path)
            X_scoring = _transform_for_bundle(bundle, Xte_raw)
            original_metrics = binary_metrics(bundle["pipeline"], X_scoring, yte, threshold)
            cmp = compare_metrics(recorded_metrics, original_metrics, EXACT_TOLERANCE)
            exact.update({
                "status": "REPRODUCED" if cmp["all_within"] else "MISMATCH",
                "detail": "Stored artifact re-scored on the original test split reproduces the metrics recorded at training."
                if cmp["all_within"] else "Stored artifact does not reproduce the metrics recorded at training.",
                "comparison_with_recorded": cmp,
                "metrics": {k: original_metrics.get(k) for k in COMPARED_METRICS},
            })
            methodology["original_metrics_source"] = "artifact_rescored"
        except Exception as exc:
            exact.update({"status": "FAILED", "detail": f"Artifact could not be loaded or scored: {type(exc).__name__}: {exc}"})
    if exact["status"] != "REPRODUCED":
        limitations.append(f"Exact artifact reproduction {exact['status'].lower()}: {exact['detail']}")
    methodology["exact_artifact_reproduction"] = exact
    if not original_metrics and recorded_metrics:
        original_metrics = dict(recorded_metrics)
        methodology["original_metrics_source"] = "recorded_at_training"
    if contract["training"].get("cv_mean") is not None:
        original_metrics["cv_mean_auc"] = contract["training"]["cv_mean"]
    out["original_metrics"] = {k: v for k, v in original_metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}

    # B. Independent training reproduction.
    independent: Dict[str, Any] = {"status": "CANNOT_RUN", "detail": None}
    if not (params_ok and preprocessing_ok):
        independent["detail"] = "Original " + " and ".join(
            n for n, ok in (("hyperparameters", params_ok), ("preprocessing configuration", preprocessing_ok)) if not ok
        ) + " not recorded; defaults will not be substituted."
        limitations.append("Independent training reproduction cannot run: " + independent["detail"])
        methodology["independent_training_reproduction"] = independent
        return _stop(independent["detail"])
    try:
        fit = _fit_from_contract(df, contract)
        if fit["model_input_columns"] != contract["features"]["model_input_columns"]:
            raise RuntimeError("Retrained model input features differ from the registered model's feature set/order.")
        X_test = fit["X_test"]
        y_test = fit["y_test"]
        metrics = binary_metrics(fit["pipeline"], X_test, y_test, threshold)
    except Exception as exc:
        independent.update({"status": "FAILED", "detail": f"{type(exc).__name__}: {exc}"})
        methodology["independent_training_reproduction"] = independent
        limitations.append("Independent training reproduction failed to execute.")
        return _stop(f"Independent training reproduction failed: {type(exc).__name__}: {exc}")

    cmp = compare_metrics(out["original_metrics"], metrics, INDEPENDENT_TOLERANCE)
    independent.update({
        "status": "REPRODUCED" if cmp["all_within"] else "DIVERGED",
        "detail": "Retrained from the recorded configuration; performance matches the original model within tolerance."
        if cmp["all_within"] else "Retrained from the recorded configuration; performance differs from the original model beyond tolerance.",
        "comparison_with_original": cmp,
        "original_metrics_source": methodology["original_metrics_source"],
    })
    methodology["independent_training_reproduction"] = independent

    proba = fit["pipeline"].predict_proba(X_test)[:, 1]
    out.update({
        "success": True,
        "metrics": {k: v for k, v in metrics.items()},
        "cv_mean_auc": fit["training_info"].get("cv_mean"),
        "cv_std_auc": fit["training_info"].get("cv_std"),
        "split_stats": compute_split_stats(fit["X_train"], fit["X_val"], X_test, fit["y_train"], fit["y_val"], y_test),
        "pipeline": fit["pipeline"], "X_train": fit["X_train"], "X_test": X_test,
        "y_train": fit["y_train"], "y_test": y_test, "y_proba": proba, "y_pred": fit["pipeline"].predict(X_test),
        "col_types": fit["col_types"], "task_type": "binary", "prep_report": fit["prep_report"], "prep_report_fe": fit["prep_report"],
        "use_feature_engineering": bool(contract["preprocessing"].get("feature_engineering_enabled")),
        "model_params_used": contract["estimator"]["params"],
        "split_check": {"status": "PASS" if split_ok else "FAIL", "detail": split_detail},
    })
    try:
        out["split_integrity"] = registered_split_integrity(fit, df, contract)
    except Exception as exc:
        out["split_integrity"] = si.r47_not_assessed(f"Split evidence could not be evaluated: {type(exc).__name__}: {exc}")

    if compute_stability:
        base_auc = float(metrics["roc_auc"])
        # Seed stability: one independent execution per seed (fresh split,
        # fresh estimator from the recorded configuration, fresh fit), every
        # attempt recorded — failures included.
        # Each run also yields the R4.5 / R4.6 evidence (stability_checks).
        criteria = stability.load_criteria()

        def _seed_execution(s: int) -> Dict[str, Any]:
            f_s = _fit_from_contract(df, contract, random_seed=s, use_cv=False)
            return stability.evaluate_run(s, f_s["pipeline"], f_s["X_train"], f_s["X_test"], f_s["y_test"], criteria)

        out["seed_runs"] = []
        for s in seeds:
            try:
                out["seed_runs"].append(_seed_execution(s))
            except Exception as exc:
                out["seed_runs"].append(stability.failed_run(s, exc))
        out["seed_aucs"] = [r["auc"] for r in out["seed_runs"] if r["status"] == "COMPLETED"]
        first_ok = next((r for r in out["seed_runs"] if r["status"] == "COMPLETED"), None)
        repeat = None
        if first_ok is not None:
            try:
                repeat = _seed_execution(first_ok["seed"])
            except Exception as exc:
                repeat = stability.failed_run(first_ok["seed"], exc)
        r46c = criteria["r46"]
        from val_replication_core import _temporal_evidence
        out["stability"] = {
            "runs": out["seed_runs"],
            "determinism": stability.determinism_check(first_ok, repeat),
            "main_evaluation": stability.stratified_bootstrap_auc(
                np.asarray(y_test), proba, r46c["bootstrap_iterations"], int(r46c["bootstrap_seed"]), float(r46c["confidence_level"])),
            "temporal": _temporal_evidence(df, y_test, proba, criteria, date_col=contract["training"].get("date_col")),
        }

        # Feature ablation: drop the raw feature, rebuild preprocessing,
        # imputation and feature engineering for the remaining columns,
        # retrain from the recorded configuration, re-score the same test rows.
        out["ablation_runs"] = []
        dropped = set(contract["preprocessing"].get("drop_cols") or [])
        for col in [c for c in required if c not in dropped]:
            try:
                f_a = _fit_from_contract(df, contract, extra_drop=[col], use_cv=False)
                auc_a = float(roc_auc_score(f_a["y_test"], f_a["pipeline"].predict_proba(f_a["X_test"])[:, 1]))
                out["ablation"][col] = round(base_auc - auc_a, 4)
                out["ablation_runs"].append({
                    "feature": col, "status": "COMPLETED", "baseline_auc": round(base_auc, 4),
                    "auc_without_feature": round(auc_a, 4), "auc_drop": out["ablation"][col],
                    "features_used": len(f_a["model_input_columns"]),
                    "feature_removed": col not in f_a["model_input_columns"],
                })
            except Exception as exc:
                out["ablation_runs"].append({"feature": col, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})

    out["timing_s"] = round(time.time() - t0, 1)
    return out
