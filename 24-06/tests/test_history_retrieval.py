"""Phase 4 regression tests — historical retrieval, run identity and audit
trail integrity.

Every model is really trained and every replication / verdict really runs.
Legacy history is simulated by writing rows exactly as pre-Phase-4 code did,
into the isolated temp log only.
"""
import io
import json
import os

import pandas as pd
import pytest

import _aegis_test_env as env
import conftest
import main
import persistence

CSV_A = env.to_csv(env.dataset(2000, 6, 0.3, seed=21))
CSV_B = env.to_csv(env.dataset(2000, 6, 0.3, seed=22))
MDD_TEXT = "Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions. GDP and unemployment."


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("history_retrieval")) as c:
        yield c


@pytest.fixture(scope="module")
def models(client):
    a = env.train(client, CSV_A, "History Model A")["model_id"]
    b = env.train(client, CSV_B, "History Model B")["model_id"]
    return {"A": a, "B": b}


def _verdict(client, model_id, run_id, csv, name):
    intake = {"model_name": name, "registered_model_id": model_id,
              "model_inventory_registered": True, "independence_confirmed": True}
    r = client.post("/validation/stage8/findings",
                    data={"intake_json": json.dumps(intake), "mdd_text": MDD_TEXT, "replication_run_id": run_id},
                    files={"file": ("current.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def _log_row(run_id):
    return next(r for r in persistence.read_log(env.LOG) if r["run_id"] == run_id)


# 1 ── Latest valid replication run ──────────────────────────────────────────

def test_latest_valid_replication_run_has_correct_identity(client, models):
    env.replicate(client, CSV_A, models["A"])
    second = env.replicate(client, CSV_A, models["A"])
    found = env.latest(client, "replication", registered_model_id=models["A"])
    latest = found["latest"]
    contract = env.dev_entry(models["A"])["lineage_contract"]

    assert latest["run_id"] == second["evidence"]["run_id"]
    assert latest["stage"] == "replication" and latest["record_status"] == "current"
    assert latest["timestamp"] == _log_row(latest["run_id"])["timestamp"]
    assert latest["summary"]["registered_model_id"] == models["A"]
    assert latest["summary"]["dataset_sha256"] == contract["dataset"]["sha256"]
    # Relationship between the original training run and the replication run.
    assert latest["summary"]["training_run_id"] == contract["training_run_id"]
    assert latest["full_payload"]["evidence"]["run_id"] == latest["run_id"]
    assert found["excluded"] == []


# 2 ── Latest legacy run ─────────────────────────────────────────────────────

def test_newer_legacy_run_is_labelled_and_never_selected_by_default(client, models):
    current = env.replicate(client, CSV_A, models["A"])["evidence"]["run_id"]
    legacy_id = env.append_legacy_row(env.LOG, "replication",
                                      {"registered_model_id": models["A"], "business_model_name": "History Model A"},
                                      {"stage": "replication", "report": {"metrics": {"roc_auc": 1.0}}})
    found = env.latest(client, "replication", registered_model_id=models["A"])
    assert found["latest"]["run_id"] == current
    assert found["excluded"][0]["run_id"] == legacy_id
    assert "before run-identity tracking" in found["excluded"][0]["reason"]

    explicit = env.latest(client, "replication", registered_model_id=models["A"], include_legacy="true")
    assert explicit["latest"]["run_id"] == legacy_id and explicit["latest"]["record_status"] == "legacy"

    rows = {r["run_id"]: r for r in client.get("/history/validation").json()["runs"]}
    assert rows[legacy_id]["record_status"] == "legacy"   # preserved, labelled
    assert rows[current]["record_status"] == "current"
    art = client.get("/history/artifact", params={"log_file": env.LOG, "run_id": legacy_id}).json()
    assert art["artifact"] is not None and art["record_status"] == "legacy"


# 3 ── Multiple models with separate runs ────────────────────────────────────

def test_runs_of_one_model_never_resume_for_another(client, models):
    run_a = env.replicate(client, CSV_A, models["A"])["evidence"]["run_id"]
    run_b = env.replicate(client, CSV_B, models["B"])["evidence"]["run_id"]   # newer
    found_a = env.latest(client, "replication", registered_model_id=models["A"])
    found_b = env.latest(client, "replication", registered_model_id=models["B"])
    assert found_a["latest"]["run_id"] == run_a
    assert found_b["latest"]["run_id"] == run_b
    assert any(e["run_id"] == run_b and "registered model id" in e["reason"] for e in found_a["excluded"])


# 4 ── Multiple datasets ─────────────────────────────────────────────────────

def test_runs_on_other_datasets_are_excluded(client, models):
    good = env.replicate(client, CSV_A, models["A"])["evidence"]
    other = env.replicate(client, CSV_B, models["A"])["evidence"]   # newer, other data → lineage L5 FAIL
    assert other["dataset_sha256"] != good["dataset_sha256"]
    found = env.latest(client, "replication", registered_model_id=models["A"], dataset_sha256=good["dataset_sha256"])
    assert found["latest"]["run_id"] == good["run_id"]
    assert any(e["run_id"] == other["run_id"] and "dataset sha256" in e["reason"] for e in found["excluded"])


def test_dataset_names_match_regardless_of_extension(client):
    # Unregistered refits are still scoped by name + dataset name; "x" and
    # "x.csv" are the same dataset (previously resume never matched).
    run = env.replicate(client, CSV_A, None, filename="Demo A dataset.csv",
                        model_name="Unregistered Name Model", algorithm="Logistic Regression")
    found = env.latest(client, "replication", business_model_name="Unregistered Name Model", dataset_name="Demo A dataset")
    assert found["latest"]["run_id"] == run["evidence"]["run_id"]


# 5 ── Stale benchmark ───────────────────────────────────────────────────────

def test_stale_two_row_benchmark_is_never_current(client, models):
    # The production log's legacy "benchmarking" row: AUC 1.000 on a 2-row test set.
    env.append_legacy_row(env.LOG, "benchmarking", {"model_name": "LogisticRegression", "champion_vs_challenger": "OK"},
                          {"stage": "performance", "report": {"metrics": {"roc_auc": 1.0},
                                                              "benchmark": {"model_name": "Logistic Regression", "status": "OK"}}})
    old_name = client.get("/history/latest", params={"log_file": env.LOG, "stage": "benchmarking"})
    assert old_name.status_code == 400 and "'performance'" in old_name.json()["detail"]

    assert env.latest(client, "performance", registered_model_id=models["A"])["latest"] is None
    bench = client.post("/validation/performance", data={"model_name": "Logistic Regression", "target_col": "default",
                                                         "challenger_model_name": "Logistic Regression", "registered_model_id": models["A"]},
                        files={"file": ("dev.csv", io.BytesIO(CSV_A), "text/csv")}).json()
    found = env.latest(client, "performance", registered_model_id=models["A"])
    assert found["latest"]["run_id"] == bench["evidence"]["run_id"]
    assert found["latest"]["full_payload"]["report"]["metrics"]["roc_auc"] != 1.0
    assert found["latest"]["summary"]["training_run_id"] == env.dev_entry(models["A"])["lineage_contract"]["training_run_id"]
    # ...and it never resumes for another registered model.
    assert env.latest(client, "performance", registered_model_id=models["B"])["latest"] is None


# 6 ── New model training after old validation ──────────────────────────────

def test_retraining_makes_earlier_runs_and_verdicts_stale(client):
    model_id = env.train(client, CSV_A, "Retrained After Validation")["model_id"]
    run = env.replicate(client, CSV_A, model_id)["evidence"]["run_id"]
    _verdict(client, model_id, run, CSV_A, "Retrained After Validation")
    assert env.latest(client, "findings", registered_model_id=model_id, replication_run_id=run)["latest"] is not None

    # A new training of the model records a new lineage contract.
    env.edit_dev_entry(model_id, lambda e: e["lineage_contract"].update({"training_run_id": "newer-training-run"}))
    for stage in ("replication", "findings"):
        found = env.latest(client, stage, registered_model_id=model_id)
        assert found["latest"] is None, stage
        assert any("retrained since this run" in reason for reason in found["excluded_counts"]), found
    # History itself is preserved.
    assert any(r["run_id"] == run for r in persistence.read_log(env.LOG))


def test_failed_retrain_withdraws_contract_and_old_runs(client):
    model_id = env.train(client, CSV_B, "Withdrawn Contract Model")["model_id"]
    env.replicate(client, CSV_B, model_id)
    env.edit_dev_entry(model_id, lambda e: e.pop("lineage_contract"))
    found = env.latest(client, "replication", registered_model_id=model_id)
    assert found["latest"] is None
    assert any("no recorded training lineage" in r for r in found["excluded_counts"])


# 7 ── New replication after an earlier verdict ──────────────────────────────

def test_new_replication_never_reuses_earlier_verdict(client, models):
    r1 = env.replicate(client, CSV_A, models["A"])["evidence"]["run_id"]
    v1 = _verdict(client, models["A"], r1, CSV_A, "History Model A")
    r2 = env.replicate(client, CSV_A, models["A"])["evidence"]["run_id"]

    for_r2 = env.latest(client, "findings", registered_model_id=models["A"], replication_run_id=r2)
    assert for_r2["latest"] is None
    assert any("replication run id" in reason for reason in for_r2["excluded_counts"])

    for_r1 = env.latest(client, "findings", registered_model_id=models["A"], replication_run_id=r1)
    assert for_r1["latest"]["full_payload"]["verdict_basis"]["replication"]["run_id"] == r1
    assert for_r1["latest"]["full_payload"]["verdict"] == v1["verdict"]

    v2 = _verdict(client, models["A"], r2, CSV_A, "History Model A")
    for_r2 = env.latest(client, "findings", registered_model_id=models["A"], replication_run_id=r2)
    assert for_r2["latest"]["summary"]["replication_run_id"] == r2
    assert for_r2["latest"]["full_payload"]["verdict"] == v2["verdict"]


# 8 ── Browser refresh and historical restoration ───────────────────────────

def test_refresh_restores_the_matching_replication_and_verdict(client, models):
    """Replays the requests the frontend makes after a refresh: Replication
    resumes by registered model ID, Findings by that model + the restored
    replication run ID, and the activity log opens the same artifact."""
    run = env.replicate(client, CSV_B, models["B"])["evidence"]["run_id"]
    verdict = _verdict(client, models["B"], run, CSV_B, "History Model B")

    restored_rep = env.latest(client, "replication", registered_model_id=models["B"])["latest"]
    assert restored_rep["run_id"] == run
    restored_run_id = restored_rep["full_payload"]["evidence"]["run_id"]
    restored_verdict = env.latest(client, "findings", registered_model_id=models["B"], replication_run_id=restored_run_id)["latest"]
    assert restored_verdict["full_payload"]["verdict"] == verdict["verdict"]
    assert restored_verdict["full_payload"]["verdict_basis"]["replication"]["run_id"] == run
    art = client.get("/history/artifact", params={"log_file": env.LOG, "run_id": restored_verdict["run_id"]}).json()
    assert art["artifact"] == restored_verdict["full_payload"] and art["record_status"] == "current"


# 9 ── Missing run IDs ───────────────────────────────────────────────────────

def test_missing_and_unknown_run_ids_are_handled(client, models):
    art = client.get("/history/artifact", params={"log_file": env.LOG, "run_id": "does-not-exist"}).json()
    assert art == {"artifact": None, "record_status": None, "record_status_reason": None}
    assert persistence.get_run(env.LOG, "") is None
    assert env.latest(client, "findings", registered_model_id=models["A"], replication_run_id="does-not-exist")["latest"] is None
    # A legacy row with no run_id at all is listed, never selected.
    env.append_legacy_row(env.LOG, "findings", {"verdict": "APPROVED"}, {"verdict": "APPROVED"}, run_id="")
    found = env.latest(client, "findings")
    assert found["latest"] is None or found["latest"]["run_id"]          # the id-less row is never selected
    assert any(e["run_id"] == "" for e in found["excluded"])              # ...but it is listed as excluded
    v = _verdict(client, models["A"], "", CSV_A, "History Model A")
    assert v["verdict"] == "NOT ASSESSED"


# 10 ── Incorrect stage names / log files ───────────────────────────────────

@pytest.mark.parametrize("log_file, stage, fragment", [
    (persistence.VALIDATION_PIPELINE_LOG, "benchmarking", "legacy name"),
    (persistence.VALIDATION_PIPELINE_LOG, "replicaton", "Unknown stage"),
    (persistence.VALIDATION_PIPELINE_LOG, "training", "Unknown stage"),
    ("../demo_data/clean_portfolio.csv", "replication", "Unknown log file"),
    ("model_inventory.json", "replication", "Unknown log file"),
])
def test_incorrect_stage_or_log_names_are_rejected(client, log_file, stage, fragment):
    r = client.get("/history/latest", params={"log_file": log_file, "stage": stage})
    assert r.status_code == 400 and fragment in r.json()["detail"]


def test_artifact_lookup_rejects_unknown_log_file(client):
    r = client.get("/history/artifact", params={"log_file": "../demo_data/clean_portfolio.csv", "run_id": "x"})
    assert r.status_code == 400


# 11 ── Tests cannot modify production logs or inventory ────────────────────

def test_session_persistence_is_redirected_away_from_real_data():
    real_app_data = conftest.BACKEND_DIR / "app_data"
    # Outside the module-level isolated_backend override, conftest's temp
    # tree is in force (checked on the saved configuration state).
    assert conftest._STATE["tmp"] is not None
    assert real_app_data not in [persistence.APP_DATA_DIR, persistence.APP_DATA_DIR.parent]
    assert str(main.INTAKE_DRAFTS_DIR).startswith(str(conftest._STATE["tmp"]))


def test_writes_land_in_temp_and_real_data_is_unchanged(client):
    before = conftest.protected_snapshot()
    client.post("/validation/intake/draft", json={"model_name": "Isolation Probe", "data": {"x": 1}})
    persistence.log_event(env.LOG, "intake", {"model_name": "Isolation Probe"}, {"probe": True})
    assert (main.INTAKE_DRAFTS_DIR / "Isolation_Probe.json").exists()
    assert conftest.describe_changes(before, conftest.protected_snapshot()) == []


def test_guard_detects_modification(tmp_path):
    protected = tmp_path / "protected"
    protected.mkdir()
    (protected / "log.csv").write_text("a", encoding="utf-8")
    before = conftest.protected_snapshot([protected])
    (protected / "log.csv").write_text("ab", encoding="utf-8")
    (protected / "new.json").write_text("{}", encoding="utf-8")
    changes = conftest.describe_changes(before, conftest.protected_snapshot([protected]))
    assert any(c.startswith("modified:") for c in changes) and any(c.startswith("added:") for c in changes)
