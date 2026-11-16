"""Phase 4 (H2, H3, H4): history scoping for Data & Model Soundness and the
stress stage-done flags, and legacy labelling of listed history.

New soundness and stress runs record the dataset bytes' fingerprint
(dataset_file_sha256); lookups scoped by registered model + that fingerprint
never return another model's run, another dataset's run, or an older run that
did not record the fingerprint. Legacy rows stay listed (labelled) and are
never rewritten. Verdict evidence linking is unchanged.

Isolated temporary app_data; synthetic data. The stress ENGINE and the
registered evaluation boundary are stubbed exactly as in
test_verdict_evidence_completeness.py (their own tests cover them); the
real endpoints persist the runs.
"""
import hashlib
import io
import json

import numpy as np
import pandas as pd
import pytest

import _aegis_test_env as env
import main
import persistence

DF = pd.DataFrame({"f0": np.arange(60, dtype=float), "f1": np.arange(60) % 7, "default": [i % 2 for i in range(60)]})
CSV = DF.to_csv(index=False).encode()
OTHER_CSV = DF.assign(f0=DF["f0"] + 1).to_csv(index=False).encode()
SHA, OTHER_SHA = hashlib.sha256(CSV).hexdigest(), hashlib.sha256(OTHER_CSV).hexdigest()
MDD = ("Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions are documented. "
       "Macro overlays use GDP and unemployment.")


def _dev(model_id, training_run_id):
    return {"model_id": model_id, "model_name": f"Model {model_id}", "algorithm": "Logistic Regression", "status": "In Development",
            "documentation_path": "docs/x.pdf", "lineage_contract": {"contract_version": 1, "training_run_id": training_run_id}}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with env.isolated_backend(tmp_path) as c:
        persistence.save_model_inventory({"development": [_dev("MOD-001", "TR-1"), _dev("MOD-002", "TR-2")],
                                          "validation": [], "models": [], "data_sources": [], "history": []})
        yield c


def _stub_stress(monkeypatch):
    def fake(df, model_id, *, dataset_sha256, expected_training_run_id=None, compute_sensitivity=False):
        y = df["default"].iloc[-20:]
        return {"identity": {"evaluation_mode": main.model_lineage.EVALUATION_MODE_REGISTERED, "registered_model_id": model_id,
                             "training_run_id": main.registered_run_identity(model_id)["training_run_id"],
                             "dataset_sha256": dataset_sha256, "test_index_sha256": "test-rows", "bundle_sha256": "bundle"},
                "y_test": y, "y_proba": np.linspace(0.1, 0.9, len(y)), "contract": {}}
    monkeypatch.setattr(main.model_lineage, "registered_evaluation", fake)
    monkeypatch.setattr(main, "run_stress_suite", lambda *a, **k: {
        "available": True, "directional": [],
        "summary": {"checks": [{"id": "6.1", "title": "Sensitivity", "status": "PASS"}], "pass": 1, "warn": 0, "fail": 0, "pending": 0, "na": 0}})


def stress(client, monkeypatch, model_id="MOD-001", csv=CSV, as_text=False):
    _stub_stress(monkeypatch)
    data = {"target_col": "default", "registered_model_id": model_id}
    if as_text:
        r = client.post("/validation/stress/run", data={**data, "csv_text": csv.decode()})
    else:
        r = client.post("/validation/stress/run", data=data, files={"file": ("d.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def soundness(client, model_id="MOD-001", csv=CSV):
    r = client.post("/validation/stage3/run", data={"intake_json": json.dumps({"registered_model_id": model_id})},
                    files={"file": ("d.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200, r.text
    return [row for row in persistence.read_log(env.LOG) if row["stage"] == "conceptual_soundness"][-1]


def latest(client, stage, **params):
    r = client.get("/history/latest", params={"log_file": env.LOG, "stage": stage, **params})
    assert r.status_code == 200, r.text
    return r.json()["latest"]


# ── H2: Data & Model Soundness ─────────────────────────────────────────────

def test_soundness_run_records_the_file_fingerprint(client):
    row = soundness(client)
    assert row["summary"]["dataset_file_sha256"] == SHA
    assert row["summary"]["registered_model_id"] == "MOD-001" and row["summary"]["dataset_sha256"]


def test_soundness_lookup_is_scoped_by_model_and_dataset(client):
    mine = soundness(client)["run_id"]
    other_dataset = soundness(client, csv=OTHER_CSV)["run_id"]
    other_model = soundness(client, model_id="MOD-002")["run_id"]
    assert latest(client, "conceptual_soundness", registered_model_id="MOD-001", dataset_file_sha256=SHA)["run_id"] == mine
    assert latest(client, "conceptual_soundness", registered_model_id="MOD-001", dataset_file_sha256=OTHER_SHA)["run_id"] == other_dataset
    assert latest(client, "conceptual_soundness", registered_model_id="MOD-002", dataset_file_sha256=SHA)["run_id"] == other_model
    assert latest(client, "conceptual_soundness", registered_model_id="MOD-003", dataset_file_sha256=SHA) is None


def test_soundness_runs_without_a_fingerprint_are_never_restored(client):
    # A current-format run written before H2 (no dataset_file_sha256), newer than anything else.
    env.append_legacy_row(env.LOG, "conceptual_soundness",
                          {"registered_model_id": "MOD-001", "training_run_id": "TR-1",
                           "record_version": persistence.RECORD_FORMAT_VERSION}, {"thresholdChecks": []})
    assert latest(client, "conceptual_soundness", registered_model_id="MOD-001", dataset_file_sha256=SHA) is None
    found = client.get("/history/latest", params={"log_file": env.LOG, "stage": "conceptual_soundness",
                                                   "registered_model_id": "MOD-001", "dataset_file_sha256": SHA}).json()
    assert any("dataset_file_sha256" in e["reason"] for e in found["excluded"])


# ── H3: stress stage-done lookups ──────────────────────────────────────────

def test_stress_run_records_the_file_fingerprint_for_file_and_text_uploads(client, monkeypatch):
    by_file = stress(client, monkeypatch)
    assert by_file["evidence"]["dataset_file_sha256"] == SHA
    by_text = stress(client, monkeypatch, as_text=True)
    assert by_text["evidence"]["dataset_file_sha256"] == hashlib.sha256(CSV.decode().encode("utf-8")).hexdigest()
    row = next(r for r in persistence.read_log(env.LOG) if r["run_id"] == by_file["evidence"]["run_id"])
    assert row["summary"]["dataset_file_sha256"] == SHA


def test_stress_stage_done_lookup_ignores_other_datasets_models_and_old_runs(client, monkeypatch):
    other_dataset = stress(client, monkeypatch, csv=OTHER_CSV)["evidence"]["run_id"]
    # Only another dataset's run exists for MOD-001: not done for this dataset.
    assert latest(client, "stress_testing", registered_model_id="MOD-001", dataset_file_sha256=SHA) is None
    assert latest(client, "stress_testing", registered_model_id="MOD-001", dataset_file_sha256=OTHER_SHA)["run_id"] == other_dataset
    stress(client, monkeypatch, model_id="MOD-002")
    assert latest(client, "stress_testing", registered_model_id="MOD-001", dataset_file_sha256=SHA) is None
    env.append_legacy_row(env.LOG, "stress_testing",
                          {"registered_model_id": "MOD-001", "training_run_id": "TR-1",
                           "record_version": persistence.RECORD_FORMAT_VERSION}, {"report": {"available": True}})
    assert latest(client, "stress_testing", registered_model_id="MOD-001", dataset_file_sha256=SHA) is None
    mine = stress(client, monkeypatch)["evidence"]["run_id"]
    assert latest(client, "stress_testing", registered_model_id="MOD-001", dataset_file_sha256=SHA)["run_id"] == mine


# ── H4 + preservation: legacy rows listed, labelled, never rewritten ──────

def test_legacy_rows_stay_listed_and_labelled_and_untouched(client, monkeypatch):
    legacy_id = env.append_legacy_row(env.LOG, "benchmarking", {"model_name": "Old"}, {"metrics": {"roc_auc": 1.0}})
    current_id = stress(client, monkeypatch)["evidence"]["run_id"]
    log_path = persistence.APP_DATA_DIR / env.LOG
    before = log_path.read_bytes()
    runs = {r["run_id"]: r for r in client.get("/history/validation").json()["runs"]}
    assert runs[legacy_id]["record_status"] == "legacy" and runs[legacy_id]["record_status_reason"]
    assert runs[current_id]["record_status"] == "current"
    # The retired stage name is still refused for lookups (history only).
    assert client.get("/history/latest", params={"log_file": env.LOG, "stage": "benchmarking"}).status_code == 400
    assert log_path.read_bytes() == before                                    # listing/lookup never rewrites the log


# ── Verdict evidence linking unchanged ─────────────────────────────────────

def test_verdict_still_links_the_stress_run_by_model_training_and_dataset(client, monkeypatch):
    monkeypatch.setattr(main, "assess_replication_evidence", lambda run_id, claimed: {
        "status": "PASS", "run_id": run_id, "reasons": [], "execution_failed": False,
        "metrics": {"roc_auc": 0.8, "gini": 0.6, "ks": 0.45, "recall": 0.7, "brier_score": 0.1}, "reference_metrics": {},
        "failed_mandatory_checks": [], "failed_other_checks": [], "mandatory_checks": [], "identity": {}, "methodology": {}})
    run_id = stress(client, monkeypatch)["evidence"]["run_id"]
    data = {"intake_json": json.dumps({"registered_model_id": "MOD-001", "model_name": "Model MOD-001"}), "mdd_text": MDD,
            "replication_run_id": "rep-1", "registered_model_id": "MOD-001"}
    v = client.post("/validation/stage8/findings", data=data, files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")}).json()
    item = v["verdict_basis"]["evidence_completeness"]["items"]["stress_testing"]
    assert item["status"] == "PASS" and item.get("run_id") == run_id
    other = client.post("/validation/stage8/findings", data=data, files={"file": ("d.csv", io.BytesIO(OTHER_CSV), "text/csv")}).json()
    other_item = other["verdict_basis"]["evidence_completeness"]["items"]["stress_testing"]
    assert other_item["status"] == "NOT_ASSESSED"                             # another dataset's stress run is not evidence
