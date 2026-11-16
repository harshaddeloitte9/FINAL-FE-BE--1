"""Phase 3 regression tests — genuine reproduction of a registered model.

Every model here is really trained through /models/train and every
replication really executes. Missing/damaged lineage is simulated by editing
the temp-folder inventory or artifact, exactly as a damaged registry would
look. All persistence is isolated (see _aegis_test_env.isolated_backend).
"""
import json

import joblib
import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

import _aegis_test_env as env
import main
import model_lineage
import persistence
from preprocessing_new import finalize_xy
from train_new import split_data
from utils import detect_column_types

GOOD_DF = env.dataset(8000, 12, 0.30, seed=5)
GOOD_CSV = env.to_csv(GOOD_DF)
SMALL_DF = env.dataset(2000, 6, 0.30, seed=8)
SMALL_CSV = env.to_csv(SMALL_DF)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("registered_replication")) as c:
        yield c


@pytest.fixture(scope="module")
def registered(client):
    """A registered model and one genuine reproduction of it."""
    trained = env.train(client, GOOD_CSV, "Registered PD Model")
    rep = env.replicate(client, GOOD_CSV, trained["model_id"])
    return {"model_id": trained["model_id"], "trained": trained, "rep": rep}


def _small_model(client, name, **extra):
    return env.train(client, SMALL_CSV, name, **extra)["model_id"]


# 1 ── Correct registered model reproduction ─────────────────────────────────

def test_correct_registered_model_reproduction(registered):
    rep, mid = registered["rep"], registered["model_id"]
    result = rep["report"]["replication"]["result"]
    m = env.methodology(rep)
    assert result["success"] is True
    assert m["mode"] == model_lineage.REPLICATION_MODE_REGISTERED
    assert m["registered_model_id"] == mid
    assert m["training_run_id"] == registered["trained"]["lineage"]["training_run_id"]
    assert all(s == "PASS" for s in env.lineage_status(rep).values()), m["lineage_checks"]
    assert m["exact_artifact_reproduction"]["status"] == "REPRODUCED"
    assert m["independent_training_reproduction"]["status"] == "REPRODUCED"
    assert m["original_metrics_source"] == "artifact_rescored"
    # Lineage retained on the run itself.
    ev = rep["evidence"]
    assert ev["registered_model_id"] == mid and ev["replication_mode"] == model_lineage.REPLICATION_MODE_REGISTERED
    assert ev["training_run_id"] == m["training_run_id"] and ev["execution_status"] == "COMPLETED"
    assert ev["dataset_sha256"] == env.dev_entry(mid)["lineage_contract"]["dataset"]["sha256"]
    assert result["replication_config_source"] == "registered_lineage_contract"
    r42 = next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.2")
    assert "Original model" in r42["observed"]
    r47 = next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.7")
    s6 = next(s for s in r47["_subchecks"] if s["id"] == "S6")
    assert r47.get("executed") is True and r47["status"] == "PASS"
    assert s6["status"] == "PASS" and "matches the recorded training split" in s6["detail"]


def test_screen_configuration_is_ignored_in_registered_mode(client, registered):
    rep = env.replicate(client, GOOD_CSV, registered["model_id"], algorithm="XGBoost",
                        model_params_json=json.dumps({"C": 0.001}), model_name="Something Else")
    m = env.methodology(rep)
    assert m["estimator"]["class"] == "LogisticRegression"
    assert any(i.startswith("algorithm") for i in m["ignored_inputs"])
    assert any(i.startswith("model_params_json") for i in m["ignored_inputs"])
    assert rep["report"]["replication"]["result"]["model_params_used"]["C"] == m["estimator"]["params"]["C"]


# 2 ── Incorrect model ID ────────────────────────────────────────────────────

def test_incorrect_model_id_is_rejected_without_running(client):
    before_runs = len(persistence.read_log(env.LOG))
    before_validation = len(persistence.load_model_inventory()["validation"])
    r = client.post("/validation/replication", data={"registered_model_id": "MOD-999", "target_col": "default"},
                    files={"file": ("dev.csv", GOOD_CSV, "text/csv")})
    assert r.status_code == 404
    assert "MOD-999" in r.json()["detail"] and "not run" in r.json()["detail"]
    assert len(persistence.read_log(env.LOG)) == before_runs
    assert len(persistence.load_model_inventory()["validation"]) == before_validation


# 3 ── Missing model artifact ────────────────────────────────────────────────

def test_missing_artifact_blocks_exact_reproduction_only(client):
    mid = _small_model(client, "Missing Artifact Model")
    (persistence.BACKEND_DIR / env.dev_entry(mid)["lineage_contract"]["artifact"]["path"]).unlink()
    rep = env.replicate(client, SMALL_CSV, mid)
    m = env.methodology(rep)
    assert m["exact_artifact_reproduction"]["status"] == "UNAVAILABLE"
    assert "missing" in m["exact_artifact_reproduction"]["detail"]
    # Independent retraining needs configuration + data, not the artifact.
    assert m["independent_training_reproduction"]["status"] == "REPRODUCED"
    assert m["original_metrics_source"] == "recorded_at_training"
    assert any("Exact artifact reproduction unavailable" in l for l in m["limitations"])


def test_tampered_artifact_fails_integrity_check(client):
    mid = _small_model(client, "Tampered Artifact Model")
    path = persistence.BACKEND_DIR / env.dev_entry(mid)["lineage_contract"]["artifact"]["path"]
    path.write_bytes(path.read_bytes() + b"tampered")
    m = env.methodology(env.replicate(client, SMALL_CSV, mid))
    assert m["exact_artifact_reproduction"]["status"] == "UNAVAILABLE"
    assert "integrity" in m["exact_artifact_reproduction"]["detail"]


# 4 ── Missing hyperparameters ───────────────────────────────────────────────

def test_missing_hyperparameters_are_not_substituted(client):
    mid = _small_model(client, "Missing Params Model")
    env.edit_dev_entry(mid, lambda e: e["lineage_contract"]["estimator"].update({"params": {}}))
    rep = env.replicate(client, SMALL_CSV, mid)
    result = rep["report"]["replication"]["result"]
    m = env.methodology(rep)
    assert env.lineage_status(rep)["L6"] == "FAIL"
    assert m["independent_training_reproduction"]["status"] == "CANNOT_RUN"
    assert "defaults will not be substituted" in m["independent_training_reproduction"]["detail"]
    assert result["success"] is False and result["model_params_used"] is None
    assert next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.1")["status"] == "FAIL"


def test_model_registered_without_lineage_cannot_be_reproduced(client):
    mid = _small_model(client, "Legacy Registered Model")
    env.edit_dev_entry(mid, lambda e: e.pop("lineage_contract"))
    rep = env.replicate(client, SMALL_CSV, mid)
    assert env.lineage_status(rep)["L2"] == "FAIL"
    assert rep["report"]["replication"]["result"]["success"] is False
    assert "no recorded training lineage" in rep["report"]["replication"]["result"]["error"]


# 5 ── Missing preprocessing configuration ───────────────────────────────────

def test_missing_preprocessing_configuration_blocks_reproduction(client):
    mid = _small_model(client, "Missing Preprocessing Model")
    env.edit_dev_entry(mid, lambda e: e["lineage_contract"].update({"preprocessing": None}))
    rep = env.replicate(client, SMALL_CSV, mid)
    assert env.lineage_status(rep)["L7"] == "FAIL"
    assert env.methodology(rep)["independent_training_reproduction"]["status"] == "CANNOT_RUN"
    assert rep["report"]["replication"]["result"]["success"] is False


# 6 ── Dataset mismatch ──────────────────────────────────────────────────────

def test_dataset_mismatch_blocks_reproduction(client, registered):
    other = env.to_csv(env.dataset(8000, 12, 0.30, seed=6))  # same schema, different rows
    rep = env.replicate(client, other, registered["model_id"])
    m = env.methodology(rep)
    assert env.lineage_status(rep)["L5"] == "FAIL"
    assert m["exact_artifact_reproduction"]["status"] == "NOT_RUN"
    assert m["independent_training_reproduction"]["status"] == "CANNOT_RUN"
    assert rep["report"]["replication"]["result"]["success"] is False
    assert rep["evidence"]["execution_status"] == "FAILED"


# 7 ── Feature mismatch ──────────────────────────────────────────────────────

def test_missing_feature_column_is_detected(client, registered):
    rep = env.replicate(client, env.to_csv(GOOD_DF.drop(columns=["f3"])), registered["model_id"])
    check = next(c for c in env.methodology(rep)["lineage_checks"] if c["id"] == "L4")
    assert check["status"] == "FAIL" and "f3" in check["detail"]
    assert rep["report"]["replication"]["result"]["success"] is False


def test_feature_order_change_is_detected(client, registered):
    cols = list(GOOD_DF.columns)
    reordered = GOOD_DF[[cols[1], cols[0], *cols[2:]]]
    check = next(c for c in env.methodology(env.replicate(client, env.to_csv(reordered), registered["model_id"]))["lineage_checks"] if c["id"] == "L4")
    assert check["status"] == "FAIL" and "different order" in check["detail"]


# 8 ── Successful independent reproduction (incl. hyperparameter search) ─────

def test_independent_reproduction_uses_recorded_configuration(registered):
    m = env.methodology(registered["rep"])
    contract = env.dev_entry(registered["model_id"])["lineage_contract"]
    cmp = m["independent_training_reproduction"]["comparison_with_original"]
    assert cmp["all_within"] is True
    assert all(row["within"] for row in cmp["rows"] if row["within"] is not None)
    assert registered["rep"]["report"]["replication"]["result"]["model_params_used"] == contract["estimator"]["params"]


def test_independent_reproduction_of_hyperparameter_searched_model(client):
    trained = env.train(client, SMALL_CSV, "Hyperopt XGB Model", estimator="XGBoost", use_hyperopt=True,
                        use_feature_engineering=True)
    contract = env.dev_entry(trained["model_id"])["lineage_contract"]
    assert contract["training"]["use_hyperopt"] is True and contract["training"]["best_params"]
    m = env.methodology(env.replicate(client, SMALL_CSV, trained["model_id"]))
    assert m["exact_artifact_reproduction"]["status"] == "REPRODUCED"
    assert m["independent_training_reproduction"]["status"] == "REPRODUCED"
    # The search winner is reused as fixed parameters; no new search is run.
    for key, value in contract["training"]["best_params"].items():
        assert m["estimator"]["params"][key] == value


# 9 ── Replication failure ───────────────────────────────────────────────────

def test_replication_execution_failure_is_reported(client):
    mid = _small_model(client, "Broken Params Model")
    env.edit_dev_entry(mid, lambda e: e["lineage_contract"]["estimator"]["params"].update({"C": -5.0}))
    rep = env.replicate(client, SMALL_CSV, mid)
    m = env.methodology(rep)
    assert m["independent_training_reproduction"]["status"] == "FAILED"
    assert rep["report"]["replication"]["result"]["success"] is False
    assert rep["evidence"]["execution_status"] == "FAILED"
    assert rep["flags"] == ["R4.1"]


# 10 ── Metric comparison accuracy ───────────────────────────────────────────

def test_original_metrics_are_independently_recomputed_and_compared_correctly(registered):
    rep, mid = registered["rep"], registered["model_id"]
    contract = env.dev_entry(mid)["lineage_contract"]
    result = rep["report"]["replication"]["result"]

    # Recompute the original model's AUC here, outside the application, from
    # the stored artifact on the re-derived original test split.
    bundle = joblib.load(persistence.BACKEND_DIR / contract["artifact"]["path"])
    X, y, _ = finalize_xy(GOOD_DF, detect_column_types(GOOD_DF), "default")
    _, _, X_test, _, _, y_test = split_data(X, y, test_size=contract["split"]["test_size"], val_size=contract["split"]["val_size"],
                                            task_type="binary", random_state=contract["split"]["random_seed"])
    proba = bundle["pipeline"].predict_proba(X_test[bundle["model_input_columns"]])[:, 1]
    own_auc = round(float(roc_auc_score(y_test, proba)), 4)
    assert result["original_metrics"]["roc_auc"] == own_auc
    # ... equals what training recorded, and what /models/train returned.
    assert contract["development_metrics"]["roc_auc"] == own_auc == registered["trained"]["evaluation_metrics"]["roc_auc"]
    assert result["original_metrics"]["gini"] == round(2 * own_auc - 1, 4)
    assert result["original_metrics"]["cv_mean_auc"] == registered["trained"]["training_info"]["cv_mean"]

    # R4.2 delta is exactly |reproduced − original|.
    r42 = next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.2")
    delta = abs(result["metrics"]["roc_auc"] - result["original_metrics"]["roc_auc"])
    assert f"Δ = {delta:.4f}" in r42["observed"]
    # CV performance compared against the original training's CV.
    r48 = next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.8")
    assert r48["status"] == "PASS" and "Original model" in r48["observed"]
    # Developer-reported values are not involved in the comparison.
    assert rep["report"]["reference_metrics"]["values"] == {}


# ── Lineage safety on retraining ───────────────────────────────────────────

def test_retraining_withdraws_or_replaces_the_previous_contract(client):
    first = env.train(client, SMALL_CSV, "Retrained Model")
    first_run = first["lineage"]["training_run_id"]
    # Retraining under the same name (see completion report: registration of
    # a same-named retrain currently fails in persistence). Either way the old
    # contract must not survive as if it described the new training.
    r = client.post("/models/train", data={"target_col": "default", "model_name": "Retrained Model",
                                           "estimator_name": "Random Forest", "use_cv": "true"},
                    files={"file": ("dev.csv", SMALL_CSV, "text/csv")})
    assert r.status_code == 200
    entry = env.dev_entry(first["model_id"])
    contract = entry.get("lineage_contract")
    assert contract is None or contract["training_run_id"] != first_run
    if contract is None:
        assert "withdrawn" in entry["lineage_contract_error"]
