"""Phase 2 (updated for Phase 3) regression tests — the final validation
verdict must rest on a server-verified reproduction of the REGISTERED model.

Every model is really trained and every replication really executes (no
mocked results). Persistence is isolated; the module fails if the real logs
or model inventory change.
"""
import io
import json

import pytest

import _aegis_test_env as env
import main
import persistence

LOG = env.LOG
MODEL = "PD Verdict Test Model"
MDD_TEXT = ("Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions are documented. "
            "Macro overlays use GDP and unemployment.")

# Clearly ordered feature effects on a large sample: every mandatory check
# (including the redesigned R4.5 / R4.6) genuinely passes.
GOOD_COEFS = [1.2, 0.6, 0.3, 0.0, 0.0]
GOOD_CSV = env.to_csv(env.dataset_coefs(6000, GOOD_COEFS, seed=5))
# Outcome stops depending on the features for the later 40% of the period:
# a genuine deterioration over time, so R4.6 FAILS.
DRIFT_CSV = env.to_csv(env.dataset_coefs(6000, [0.8, 0.5, 0.3], seed=9, drift_after=0.6))
OTHER_CSV = env.to_csv(env.dataset_coefs(6000, GOOD_COEFS, seed=10))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("verdict_backend")) as c:
        yield c


def intake(model_id, name=MODEL):
    # No Stage 1/2 findings, so the verdict depends on replication evidence.
    return {"model_name": name, "registered_model_id": model_id, "model_tier": "Tier 2 — Medium Risk",
            "model_inventory_registered": True, "independence_confirmed": True}


def verdict(client, evidence, csv, model_id, extra=None, name=MODEL):
    data = {"intake_json": json.dumps(intake(model_id, name)), "mdd_text": MDD_TEXT}
    if evidence:
        data["replication_run_id"] = evidence["run_id"]
    data.update(extra or {})
    files = {"file": ("current.csv", io.BytesIO(csv), "text/csv")} if csv is not None else None
    r = client.post("/validation/stage8/findings", data=data, files=files)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def good(client):
    model_id = env.train(client, GOOD_CSV, MODEL)["model_id"]
    return {"model_id": model_id, "run": env.replicate(client, GOOD_CSV, model_id)}


def _approved(v):
    return v["verdict"] in ("APPROVED", "CONDITIONALLY APPROVED")


def _reasons(v):
    return " ".join(v["verdict_basis"]["replication"]["reasons"])


def _tamper_artifact(run_id, mutate):
    row = next(r for r in persistence.read_log(LOG) if r["run_id"] == run_id)
    path = persistence.BACKEND_DIR / row["artifact_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ── 1. Verified reproduction, all mandatory checks pass ─────────────────────

def test_verified_registered_reproduction_can_be_approved(client, good):
    statuses = {c["id"]: c["status"] for c in good["run"]["report"]["replication"]["checks"]}
    assert all(statuses[c] == "PASS" for c in main.MANDATORY_REPLICATION_CHECKS), statuses
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, good["model_id"])
    basis = v["verdict_basis"]
    assert basis["replication"]["status"] == "PASS", basis["replication"]["reasons"]
    assert basis["replication"]["methodology"]["exact_artifact_reproduction"] == "REPRODUCED"
    assert basis["replication"]["methodology"]["independent_training_reproduction"] == "REPRODUCED"
    assert basis["dataset_identity_source"] == "server_fingerprint"
    assert _approved(v) and v["verdict"] == basis["findings_verdict"]
    assert v["replicated_auc"] == good["run"]["report"]["replication"]["result"]["metrics"]["roc_auc"]


# ── 2. Reproduction ran, a mandatory check or the reproduction failed ───────

def test_failed_mandatory_check_rejects(client):
    model_id = env.train(client, DRIFT_CSV, "Drifting Model")["model_id"]
    run = env.replicate(client, DRIFT_CSV, model_id)
    r46 = next(c for c in run["report"]["replication"]["checks"] if c["id"] == "R4.6")
    assert r46["status"] == "FAIL" and r46["_deteriorated_periods"], r46["observed"]
    v = verdict(client, run["evidence"], DRIFT_CSV, model_id, name="Drifting Model")
    assert v["verdict"] == "REJECTED"
    assert v["verdict_basis"]["replication"]["status"] == "FAIL"
    assert "R4.6" in {c["id"] for c in v["verdict_basis"]["replication"]["failed_mandatory_checks"]}


def test_diverged_independent_reproduction_rejects(client):
    model_id = env.train(client, GOOD_CSV, "Diverging Model")["model_id"]
    # The recorded configuration no longer reproduces the artifact's model.
    env.edit_dev_entry(model_id, lambda e: e["lineage_contract"]["estimator"]["params"].update({"C": 1e-6}))
    run = env.replicate(client, GOOD_CSV, model_id)
    assert env.methodology(run)["independent_training_reproduction"]["status"] == "DIVERGED"
    v = verdict(client, run["evidence"], GOOD_CSV, model_id, name="Diverging Model")
    assert v["verdict"] == "REJECTED"
    assert "DIVERGED" in _reasons(v)


# ── 3. Replication failed to execute ────────────────────────────────────────

def test_failed_replication_execution_is_not_approved(client):
    model_id = env.train(client, GOOD_CSV, "Broken Model")["model_id"]
    env.edit_dev_entry(model_id, lambda e: e["lineage_contract"]["estimator"]["params"].update({"C": -5.0}))
    run = env.replicate(client, GOOD_CSV, model_id)
    assert run["report"]["replication"]["result"]["success"] is False
    v = verdict(client, run["evidence"], GOOD_CSV, model_id, name="Broken Model")
    assert v["verdict"] == "INCONCLUSIVE"
    assert v["verdict_basis"]["replication"]["execution_failed"] is True
    assert v["replicated_auc"] is None


def test_missing_artifact_is_inconclusive(client):
    model_id = env.train(client, GOOD_CSV, "No Artifact Model")["model_id"]
    (persistence.BACKEND_DIR / env.dev_entry(model_id)["lineage_contract"]["artifact"]["path"]).unlink()
    run = env.replicate(client, GOOD_CSV, model_id)
    v = verdict(client, run["evidence"], GOOD_CSV, model_id, name="No Artifact Model")
    assert v["verdict"] == "INCONCLUSIVE"
    assert "Exact artifact reproduction: UNAVAILABLE" in _reasons(v)


# ── 4. Replication never executed ───────────────────────────────────────────

def test_no_replication_is_not_assessed(client, good):
    v = verdict(client, None, GOOD_CSV, good["model_id"])
    assert v["verdict"] == "NOT ASSESSED"
    assert any(f["check"] == "3.0 Replication Evidence" and f["status"] == "NOT ASSESSED" for f in v["findings"])


def test_developer_or_browser_metrics_alone_never_approve(client, good):
    claims = json.dumps({"roc_auc": 0.99, "recall": 0.99, "gini": 0.98, "brier_score": 0.01})
    v = verdict(client, None, GOOD_CSV, good["model_id"], extra={"rep_metrics_json": claims, "benchmark_metrics_json": claims})
    assert v["verdict"] == "NOT ASSESSED" and v["replicated_auc"] is None
    assert set(v["verdict_basis"]["ignored_client_inputs"]) >= {"rep_metrics_json", "benchmark_metrics_json"}


def test_unregistered_refit_is_not_accepted_as_evidence(client, good):
    run = env.replicate(client, GOOD_CSV, None, model_name=MODEL, algorithm="Logistic Regression")
    assert env.methodology(run)["mode"] == "unregistered_independent_refit"
    v = verdict(client, run["evidence"], GOOD_CSV, good["model_id"])
    assert v["verdict"] == "INCONCLUSIVE"
    assert "not a reproduction of a registered model" in _reasons(v)


# ── 5. Model or dataset identity mismatch ───────────────────────────────────

def test_registered_model_id_mismatch_is_inconclusive(client, good):
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, "MOD-999")
    assert v["verdict"] == "INCONCLUSIVE"
    assert "registered_model_id mismatch" in _reasons(v)


def test_missing_registered_model_id_is_inconclusive(client, good):
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, None)
    assert v["verdict"] == "INCONCLUSIVE"
    assert "did not supply registered_model_id" in _reasons(v)


def test_dataset_mismatch_is_inconclusive(client, good):
    v = verdict(client, good["run"]["evidence"], OTHER_CSV, good["model_id"])
    assert v["verdict"] == "INCONCLUSIVE"
    assert "dataset_sha256 mismatch" in _reasons(v)


def test_client_supplied_fingerprint_cannot_override_server_fingerprint(client, good):
    v = verdict(client, good["run"]["evidence"], OTHER_CSV, good["model_id"],
                extra={"dataset_sha256": good["run"]["evidence"]["dataset_sha256"]})
    assert v["verdict"] == "INCONCLUSIVE"


def test_validation_engagement_id_mismatch_is_inconclusive(client, good):
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, good["model_id"], extra={"validation_model_id": "VAL-999"})
    assert v["verdict"] == "INCONCLUSIVE"
    assert "validation_model_id mismatch" in _reasons(v)


def test_unknown_run_id_is_inconclusive(client, good):
    v = verdict(client, {"run_id": "00000000-0000-0000-0000-000000000000"}, GOOD_CSV, good["model_id"])
    assert v["verdict"] == "INCONCLUSIVE" and "not found" in _reasons(v)


def test_replication_of_since_retrained_model_is_stale(client):
    model_id = env.train(client, GOOD_CSV, "Soon Retrained Model")["model_id"]
    run = env.replicate(client, GOOD_CSV, model_id)
    env.edit_dev_entry(model_id, lambda e: e["lineage_contract"].update({"training_run_id": "a-newer-training-run"}))
    v = verdict(client, run["evidence"], GOOD_CSV, model_id, name="Soon Retrained Model")
    assert v["verdict"] == "INCONCLUSIVE" and "retrained since this replication" in _reasons(v)


# ── 6. Missing validation metrics ───────────────────────────────────────────

def test_missing_replication_metrics_is_inconclusive(client):
    model_id = env.train(client, GOOD_CSV, "Metrics Gap Model")["model_id"]
    run = env.replicate(client, GOOD_CSV, model_id)
    _tamper_artifact(run["evidence"]["run_id"], lambda p: p["report"]["replication"]["result"]["metrics"].pop("gini"))
    v = verdict(client, run["evidence"], GOOD_CSV, model_id, name="Metrics Gap Model")
    assert v["verdict"] == "INCONCLUSIVE" and "gini" in _reasons(v)


# ── 7. Stale historical Benchmarking result ────────────────────────────────

def _legacy_benchmarking_run():
    legacy = {"stage": "performance", "report": {
        "metrics": {"roc_auc": 1.0, "recall": 1.0, "gini": 1.0},
        "benchmark": {"model_name": "Logistic Regression", "status": "OK", "metrics": {"roc_auc": 1.0}},
    }}
    return persistence.log_event(LOG, stage="benchmarking", payload={"model_name": "LogisticRegression"}, full_payload=legacy)


def test_stale_benchmarking_run_cannot_be_replication_evidence(client, good):
    v = verdict(client, {"run_id": _legacy_benchmarking_run()}, GOOD_CSV, good["model_id"])
    assert v["verdict"] == "INCONCLUSIVE"
    assert "'benchmarking' run, not a Model Replication run" in _reasons(v)
    assert v["replicated_auc"] is None


def test_stale_benchmarking_run_is_rejected_as_benchmark(client, good):
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, good["model_id"], extra={"benchmark_run_id": _legacy_benchmarking_run()})
    assert v["verdict_basis"]["benchmark"]["status"] == "REJECTED"
    assert v["verdict_basis"]["benchmark"]["metrics"] == {}
    assert v["verdict_basis"]["replication"]["status"] == "PASS"


def test_benchmark_for_another_registered_model_is_rejected(client, good):
    r = client.post("/validation/performance", data={"model_name": "Logistic Regression", "target_col": "default",
                                                     "challenger_model_name": "Logistic Regression", "registered_model_id": "MOD-OTHER"},
                    files={"file": ("dev.csv", io.BytesIO(GOOD_CSV), "text/csv")})
    assert r.status_code == 200
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, good["model_id"], extra={"benchmark_run_id": r.json()["evidence"]["run_id"]})
    assert v["verdict_basis"]["benchmark"]["status"] == "REJECTED"
    assert "MOD-OTHER" in " ".join(v["verdict_basis"]["benchmark"]["reasons"])


def test_legacy_replication_run_without_provenance_is_inconclusive(client, good):
    run_id = persistence.log_event(LOG, stage="replication", payload={"business_model_name": MODEL},
                                   full_payload={"stage": "replication", "report": {"replication": {"result": {"success": True}}}})
    v = verdict(client, {"run_id": run_id}, GOOD_CSV, good["model_id"])
    assert v["verdict"] == "INCONCLUSIVE" and "legacy" in _reasons(v)


# ── 8. Missing mandatory checks ─────────────────────────────────────────────

def test_mandatory_check_missing_from_record_is_inconclusive(client):
    model_id = env.train(client, GOOD_CSV, "Missing Check Model")["model_id"]
    run = env.replicate(client, GOOD_CSV, model_id)
    _tamper_artifact(run["evidence"]["run_id"], lambda p: p["report"]["replication"].__setitem__(
        "checks", [c for c in p["report"]["replication"]["checks"] if c["id"] != "R4.6"]))
    v = verdict(client, run["evidence"], GOOD_CSV, model_id, name="Missing Check Model")
    assert v["verdict"] == "INCONCLUSIVE"
    assert any("R4.6" in r and "not present" in r for r in v["verdict_basis"]["replication"]["reasons"])


def test_r47_is_executed_evidence_and_mandatory(client, good):
    # Phase 2 excluded R4.7 because it was a hard-coded PASS. Phase 5 made it
    # executed evidence (split_integrity.py), so it is now mandatory.
    assert "R4.7" in main.MANDATORY_REPLICATION_CHECKS
    r47 = next(c for c in good["run"]["report"]["replication"]["checks"] if c["id"] == "R4.7")
    assert r47["executed"] is True and r47["_subchecks"]
    v = verdict(client, good["run"]["evidence"], GOOD_CSV, good["model_id"])
    assert v["verdict_basis"]["excluded_replication_checks"] == {}
    assert any(c["id"] == "R4.7" and c["status"] == "PASS" for c in v["verdict_basis"]["replication"]["mandatory_checks"])


# ── Saved verdict record carries its evidence link ─────────────────────────

def test_saved_verdict_records_replication_run(client, good):
    verdict(client, good["run"]["evidence"], GOOD_CSV, good["model_id"])
    latest = client.get("/history/latest", params={"log_file": LOG, "stage": "findings"}).json()["latest"]
    assert latest["summary"]["replication_run_id"] == good["run"]["evidence"]["run_id"]
    assert latest["summary"]["registered_model_id"] == good["model_id"]
    assert latest["summary"]["replication_evidence_status"] == "PASS"
