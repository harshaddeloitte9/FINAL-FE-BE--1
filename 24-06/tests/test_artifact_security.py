"""Batch 3B: model artifact security (audit finding E4).

Only server-written scoring bundles, resolved from an exact registered model
ID, located in the approved artifact folder and matching the SHA-256 in the
lineage contract, are ever deserialized. Browser-uploaded artifacts are
never deserialized.

No malicious pickle is executed: "malicious" inputs are sentinel bytes, and
spies on joblib.load / pickle.loads / the verified-load boundary prove what
reaches (or does not reach) the deserializer. Isolated temporary app_data.
"""
import hashlib
import io
import json
import pickle

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

import _aegis_test_env as env
import main
import model_lineage
import persistence

SENTINEL = b"MALICIOUS-ARTIFACT-SENTINEL-must-never-be-deserialized"
CSV = pd.DataFrame({"f0": np.arange(40, dtype=float), "f1": np.arange(40, dtype=float) % 5,
                    "default": [i % 2 for i in range(40)]}).to_csv(index=False).encode()


def _harmless_bundle_bytes():
    # A trivial stand-in model (not a trained credit model) in the bundle format.
    stub = DummyClassifier(strategy="prior").fit(np.zeros((4, 2)), [0, 1, 0, 1])
    buf = io.BytesIO()
    joblib.dump({"lineage_contract_version": model_lineage.LINEAGE_CONTRACT_VERSION, "pipeline": stub,
                 "semantic_imputer": None, "fe_plan": None, "drop_cols": [], "model_input_columns": ["f0", "f1"]}, buf)
    return buf.getvalue()


def _write(rel, data):
    path = persistence.BACKEND_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel.replace("\\", "/")


def _contract(path, sha):
    return {"contract_version": model_lineage.LINEAGE_CONTRACT_VERSION, "task_type": "binary", "training_run_id": "TR-1",
            "target_col": "default", "estimator_name": "Dummy",
            # Trained on a different dataset than the CSV posted below, so the
            # posted CSV is a legitimately independent evaluation dataset (E8).
            "dataset": {"name": "training.csv", "sha256": "0" * 64},
            # Raw inputs recorded at training (E6: explanation inputs are matched to them).
            "features": {"raw_feature_columns": ["f0", "f1"], "model_input_columns": ["f0", "f1"]},
            "artifact": {"path": path, "sha256": sha}}


def _dev(model_id, name, contract=None):
    entry = {"model_id": model_id, "model_name": name, "algorithm": "Dummy", "status": "In Development",
             "documentation_path": "docs/x.pdf"}
    if contract is not None:
        entry["lineage_contract"] = contract
    return entry


@pytest.fixture()
def client(tmp_path):
    with env.isolated_backend(tmp_path) as c:
        yield c


@pytest.fixture()
def spies(monkeypatch):
    """Record every deserialization attempt without ever executing input."""
    calls = {"verified": [], "joblib": [], "pickle": []}
    real_verified = model_lineage._deserialize_verified

    def verified(data):
        calls["verified"].append(hashlib.sha256(data).hexdigest())
        assert SENTINEL not in data, "sentinel bytes reached the deserializer"
        return real_verified(data)

    real_joblib_load = joblib.load

    def joblib_spy(source, *a, **k):
        data = source.getvalue() if isinstance(source, io.BytesIO) else None
        calls["joblib"].append(data)
        assert data is None or SENTINEL not in data, "sentinel bytes reached joblib.load"
        return real_joblib_load(source, *a, **k)

    def pickle_spy(data, *a, **k):
        calls["pickle"].append(data)
        raise AssertionError("pickle.loads must not be called")

    monkeypatch.setattr(model_lineage, "_deserialize_verified", verified)
    monkeypatch.setattr(joblib, "load", joblib_spy)
    monkeypatch.setattr(pickle, "loads", pickle_spy)
    return calls


@pytest.fixture()
def inventory(client):
    """MOD-001: valid. MOD-002: no contract. MOD-003: bundle file deleted.
    MOD-004: bundle modified after registration. MOD-005: traversal path.
    MOD-006: inside the backend but outside approved storage. MOD-007: absolute path."""
    good = _harmless_bundle_bytes()
    good_sha = hashlib.sha256(good).hexdigest()
    p1 = _write("app_data/model_artifacts/MOD-001_TR-1.joblib", good)
    p3 = "app_data/model_artifacts/MOD-003_TR-1.joblib"
    p4 = _write("app_data/model_artifacts/MOD-004_TR-1.joblib", SENTINEL)            # tampered: sentinel replaced the bundle
    secret = _write("app_data/secret.joblib", good)                                      # real bytes, wrong place
    other = _write("app_data/other_store/MOD-006.joblib", good)
    entries = [
        _dev("MOD-001", "PD_Ready", _contract(p1, good_sha)),
        _dev("MOD-002", "PD_Legacy"),
        _dev("MOD-003", "PD_Deleted", _contract(p3, good_sha)),
        _dev("MOD-004", "PD_Tampered", _contract(p4, good_sha)),
        _dev("MOD-005", "PD_Traversal", _contract("app_data/model_artifacts/../secret.joblib", good_sha)),
        _dev("MOD-006", "PD_Outside", _contract(other, good_sha)),
        _dev("MOD-007", "PD_Absolute", _contract(str(persistence.BACKEND_DIR / secret), good_sha)),
    ]
    persistence.save_model_inventory({"development": entries, "validation": [], "models": [], "data_sources": [], "history": []})
    return {"good_sha": good_sha}


def _fp():
    p = persistence.get_model_inventory_path()
    return hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns


def _evaluate(client, model_id=None, upload=None, **extra):
    # Out-of-sample evaluation (E8): an independent dataset with a documented reason.
    data = {"target_col": "default", "evaluation_partition": "independent",
            "independent_dataset_reason": "Synthetic hold-out file, not used in training.", **extra}
    if model_id is not None:
        data["registered_model_id"] = model_id
    files = {"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    if upload is not None:
        files["model_artifact"] = ("model_artifact.b64", io.BytesIO(upload), "text/plain")
    return client.post("/models/evaluate", data=data, files=files)


def _explain(client, model_id=None, upload=None):
    data = {"target_col": "default", "compute_shap": "false"}
    if model_id is not None:
        data["registered_model_id"] = model_id
    files = {"file": ("d.csv", io.BytesIO(CSV), "text/csv")}
    if upload is not None:
        files["model_artifact"] = ("model_artifact.b64", io.BytesIO(upload), "text/plain")
    return client.post("/models/explain", data=data, files=files)


# 1 ── Valid registered model, matching hash ─────────────────────────────────

def test_valid_registered_bundle_is_loaded_after_verification(client, inventory, spies):
    resolved = model_lineage.load_registered_scoring_bundle("MOD-001")
    assert resolved["model_id"] == "MOD-001" and hasattr(resolved["bundle"]["pipeline"], "predict_proba")
    assert spies["verified"] == [inventory["good_sha"]]                  # deserialized bytes are the verified ones
    r = _evaluate(client, "MOD-001")
    assert r.status_code == 200, r.text
    assert "roc_auc" in r.json()["evaluation_metrics"]
    r = _explain(client, "MOD-001")
    assert r.status_code == 200, r.text
    assert spies["pickle"] == []


# 2-7 ── Fail closed, before any deserialization ────────────────────────────

@pytest.mark.parametrize("model_id, http, status_fragment", [
    ("MOD-999", 404, "not_found"),                           # 2 unknown ID
    ("MOD-002", 409, "lineage_missing"),                     # 3 missing lineage contract
    ("MOD-003", 409, "bundle_missing"),                      # 4 missing scoring bundle
    ("MOD-004", 409, "bundle_integrity_failed"),             # 5 modified bundle (hash mismatch)
    ("MOD-005", 409, "bundle_missing"),                      # 6 path traversal
    ("MOD-006", 409, "bundle_missing"),                      # 7 outside approved storage
    ("MOD-007", 409, "bundle_missing"),                      # 7 absolute path elsewhere
])
def test_unverifiable_models_fail_closed_without_deserializing(client, inventory, spies, model_id, http, status_fragment):
    for call in (_evaluate, _explain):
        r = call(client, model_id)
        assert r.status_code == http, r.text
        assert status_fragment in r.json()["detail"]
    with pytest.raises(model_lineage.ArtifactVerificationError) as exc:
        model_lineage.load_registered_scoring_bundle(model_id)
    assert exc.value.http_status == http
    assert spies["verified"] == [] and spies["joblib"] == [] and spies["pickle"] == []


def test_readiness_never_reports_out_of_storage_bundles_as_ready(client, inventory):
    for model_id in ("MOD-005", "MOD-006", "MOD-007"):
        body = client.get(f"/model-inventory/development/{model_id}/lineage").json()
        assert body["replication_ready"] is False
        assert body["scoring_bundle"]["integrity"] == "outside_approved_storage"
    assert client.get("/model-inventory/development/MOD-001/lineage").json()["replication_ready"] is True


# 8 ── Browser-uploaded artifacts never reach the deserializer ─────────────

def test_uploaded_artifact_without_id_is_rejected_unread(client, inventory, spies):
    for call in (_evaluate, _explain):
        r = call(client, None, upload=SENTINEL)
        assert r.status_code == 400 and "not accepted" in r.json()["detail"]
    assert spies["verified"] == [] and spies["joblib"] == [] and spies["pickle"] == []


def test_uploaded_artifact_alongside_a_valid_id_is_ignored(client, inventory, spies):
    with_upload = _evaluate(client, "MOD-001", upload=SENTINEL)
    without = _evaluate(client, "MOD-001")
    assert with_upload.status_code == 200 and with_upload.json() == without.json()   # result is the registered model's
    assert all(sha == inventory["good_sha"] for sha in spies["verified"])
    assert all(data is None or SENTINEL not in data for data in spies["joblib"])


def test_stage3_model_file_upload_is_never_deserialized(client, inventory, spies):
    files = {"model_file": ("model.pkl", io.BytesIO(SENTINEL), "application/octet-stream")}
    r = client.post("/validation/stage3/run", data={"intake_json": json.dumps({})}, files=files)
    assert r.status_code == 200, r.text
    assert spies["verified"] == [] and spies["pickle"] == []
    assert all(data is None or SENTINEL not in data for data in spies["joblib"])
    assert "not deserialized" in json.dumps(r.json())


def test_stage3_feature_importance_uses_the_verified_registered_bundle(client, inventory, spies):
    payload = main._derive_feature_importance_payload({}, intake={"registered_model_id": "MOD-004"})
    assert payload["importance_source"] != "registered_scoring_bundle" and "bundle_integrity_failed" in payload["importance_note"]
    assert spies["verified"] == []                                               # tampered bundle never loaded
    main._derive_feature_importance_payload({}, intake={"registered_model_id": "MOD-001"})
    assert spies["verified"] == [inventory["good_sha"]]


# 9 ── A model name cannot select another artifact ──────────────────────────

def test_model_name_cannot_select_an_artifact(client, inventory, spies):
    assert _evaluate(client, "PD_Ready").status_code == 404                     # a name is not an ID
    assert _evaluate(client, "MOD-002", model_name="PD_Ready").status_code == 409  # extra name field ignored
    assert _evaluate(client, " MOD-001 ").status_code == 200                    # exact ID (whitespace trimmed)
    assert spies["verified"] == [inventory["good_sha"]]


def test_removed_upload_loaders_no_longer_exist():
    assert not hasattr(main, "_from_base64") and not hasattr(main, "_load_model_artifact")


# 11 ── No inventory mutation ───────────────────────────────────────────────

def test_resolution_and_scoring_do_not_mutate_inventory_or_bundles(client, inventory):
    before = _fp()
    files_before = {p: p.stat().st_mtime_ns for p in persistence.APP_DATA_DIR.rglob("*.joblib")}
    for model_id in ("MOD-001", "MOD-002", "MOD-004", "MOD-005", "MOD-999"):
        _evaluate(client, model_id)
        _explain(client, model_id)
        client.get(f"/model-inventory/development/{model_id}/lineage")
    client.get("/model-inventory")
    assert _fp() == before
    assert {p: p.stat().st_mtime_ns for p in persistence.APP_DATA_DIR.rglob("*.joblib")} == files_before
