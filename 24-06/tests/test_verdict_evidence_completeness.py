"""Batch 3C: final-verdict evidence completeness (audit finding E1).

Missing mandatory evidence (stress testing, data quality, independence, MDD,
and fair lending when applicable) blocks any approval and is reported as a
NOT ASSESSED gap — not as a model failure. Evidence is resolved server-side;
browser-posted results and flags are ignored.

Isolated temporary app_data. No model is trained: the replication verdict
input is stubbed at assess_replication_evidence (its own tests are in
test_final_verdict.py), and the stress / bias ENGINES are stubbed while their
real endpoints persist the runs, so identity and log format are production.
"""
import io
import json

import numpy as np
import pandas as pd
import pytest

import _aegis_test_env as env
import main
import persistence

MDD = ("Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions are documented. "
       "Macro overlays use GDP and unemployment.")
CLEAN = pd.DataFrame({"f0": np.arange(60, dtype=float), "f1": np.arange(60) % 7, "default": [i % 2 for i in range(60)]})
PROTECTED = CLEAN.assign(gender=["F", "M"] * 30)
MISSING = CLEAN.assign(f2=[np.nan] * 30 + list(range(30)))          # 50% missing → 2.2 HIGH FAIL


def csv(df):
    return df.to_csv(index=False).encode()


def suite(status="PASS"):
    checks = [{"id": "6.1", "title": "Sensitivity", "status": status}]
    return {"available": True, "directional": [],
            "summary": {"checks": checks, "pass": int(status == "PASS"), "warn": int(status == "WARN"),
                        "fail": int(status == "FAIL"), "pending": int(status == "PENDING"), "na": 0}}


def bias_result(gap):
    rows = [{"Group": "F", "Count": 30, "AUC": 0.80}, {"Group": "M", "Count": 30, "AUC": round(0.80 - gap, 4)}]
    status = "PASS" if gap < 0.05 else ("WARN" if gap < 0.10 else "FAIL")
    return {"success": True, "error": None, "protected_columns": ["gender"], "bias_col": "gender", "rows": rows,
            "check": {"check_id": "8.2", "status": status, "observed": f"AUC gap across groups: {gap:.4f}"}}


def passing_replication(run_id="rep-run-1"):
    return {"status": "PASS", "run_id": run_id, "reasons": [], "execution_failed": False,
            "metrics": {"roc_auc": 0.80, "gini": 0.60, "ks": 0.45, "recall": 0.70, "brier_score": 0.10},
            "reference_metrics": {}, "failed_mandatory_checks": [], "failed_other_checks": [], "mandatory_checks": [],
            "identity": {}, "methodology": {}}


def _dev(model_id, training_run_id):
    return {"model_id": model_id, "model_name": f"Model {model_id}", "algorithm": "Logistic Regression", "status": "In Development",
            "documentation_path": "docs/x.pdf", "lineage_contract": {"contract_version": 1, "training_run_id": training_run_id}}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with env.isolated_backend(tmp_path) as c:
        persistence.save_model_inventory({"development": [_dev("MOD-001", "TR-1"), _dev("MOD-002", "TR-9")],
                                          "validation": [], "models": [], "data_sources": [], "history": []})
        monkeypatch.setattr(main, "assess_replication_evidence", lambda run_id, claimed: passing_replication(run_id or "rep-run-1"))
        yield c


def _stub_registered_evaluation(monkeypatch):
    # Batch 3D: a registered stress/bias run evaluates the registered scoring
    # bundle via model_lineage.registered_evaluation. These verdict tests stub
    # that boundary (its own tests: test_registered_stage_evaluation.py),
    # returning the identity it records for the model's CURRENT training.
    def fake(df, model_id, *, dataset_sha256, expected_training_run_id=None, compute_sensitivity=False):
        y = df["default"].iloc[-20:]
        return {"identity": {"evaluation_mode": main.model_lineage.EVALUATION_MODE_REGISTERED, "registered_model_id": model_id,
                             "training_run_id": main.registered_run_identity(model_id)["training_run_id"],
                             "dataset_sha256": dataset_sha256, "test_index_sha256": "test-rows", "bundle_sha256": "bundle"},
                "y_test": y, "y_proba": np.linspace(0.1, 0.9, len(y)), "contract": {}}
    monkeypatch.setattr(main.model_lineage, "registered_evaluation", fake)


def stress(client, monkeypatch, df=CLEAN, model_id="MOD-001", status="PASS"):
    _stub_registered_evaluation(monkeypatch)
    monkeypatch.setattr(main, "run_stress_suite", lambda *a, **k: suite(status))
    r = client.post("/validation/stress/run", data={"target_col": "default", "algorithm": "Logistic Regression",
                                                    "registered_model_id": model_id},
                    files={"file": ("d.csv", io.BytesIO(csv(df)), "text/csv")})
    assert r.status_code == 200, r.text
    return _latest_run_id("stress_testing")


def bias(client, monkeypatch, df=PROTECTED, model_id="MOD-001", gap=0.01):
    _stub_registered_evaluation(monkeypatch)
    monkeypatch.setattr(main, "bias_from_predictions", lambda *a, **k: bias_result(gap))
    r = client.post("/validation/stage7/bias-check", data={"target_col": "default", "algorithm": "Logistic Regression",
                                                           "protected_col": "gender", "registered_model_id": model_id},
                    files={"file": ("d.csv", io.BytesIO(csv(df)), "text/csv")})
    assert r.status_code == 200, r.text
    return _latest_run_id("fair_lending_bias")


def attest(client, model_id="MOD-001", independent=True):
    r = client.post("/validation/independence/attest",
                    data={"registered_model_id": model_id, "attested_by": "A. Validator", "independent": str(independent).lower()})
    assert r.status_code == 200, r.text
    return r.json()["attestation_id"]


def _latest_run_id(stage):
    rows = [r for r in persistence.read_log(env.LOG) if r["stage"] == stage]
    return rows[-1]["run_id"]


def verdict(client, df=CLEAN, mdd=MDD, model_id="MOD-001", intake_extra=None, **extra):
    intake = {"registered_model_id": model_id, "model_name": f"Model {model_id}", "model_tier": "Tier 2", **(intake_extra or {})}
    data = {"intake_json": json.dumps(intake), "mdd_text": mdd, "replication_run_id": "rep-run-1",
            "registered_model_id": model_id, **{k: (v if isinstance(v, str) else json.dumps(v)) for k, v in extra.items()}}
    files = {"file": ("d.csv", io.BytesIO(csv(df)), "text/csv")} if df is not None else None
    r = client.post("/validation/stage8/findings", data=data, files=files)
    assert r.status_code == 200, r.text
    return r.json()


def items(v):
    return v["verdict_basis"]["evidence_completeness"]["items"]


def gaps(v):
    return {g["evidence"] for g in v["verdict_basis"]["evidence_completeness"]["gaps"]}


def finding(v, check):
    return [f for f in v["findings"] if f["check"] == check]


# 1 / 11 / 14 ── All mandatory evidence present → approval is possible ──────

def test_complete_evidence_can_be_approved(client, monkeypatch):
    stress(client, monkeypatch)
    attest(client)
    v = verdict(client)
    assert gaps(v) == set() and v["verdict_basis"]["evidence_completeness"]["complete"] is True
    assert v["verdict"] == "APPROVED", v["verdict_desc"]
    # 11: fairness N/A only with a recorded reason (no protected columns in the data)
    fl = items(v)["fair_lending"]
    assert fl["status"] == "N/A" and fl["na_reason"] and "no protected-characteristic columns" in fl["detail"]
    assert items(v)["stress_testing"]["run_id"] and items(v)["independence"]["run_id"]


def test_complete_evidence_with_protected_columns_needs_a_bias_run(client, monkeypatch):
    stress(client, monkeypatch, df=PROTECTED)
    attest(client)
    assert "fair_lending" in gaps(verdict(client, df=PROTECTED))
    bias(client, monkeypatch, gap=0.01)
    v = verdict(client, df=PROTECTED)
    assert items(v)["fair_lending"]["status"] == "PASS" and v["verdict"] == "APPROVED"


# 2-6 ── Missing mandatory evidence blocks approval, is not a failure ────────

@pytest.mark.parametrize("missing", ["stress", "independence", "bias", "data_quality", "mdd"])
def test_missing_evidence_blocks_approval_without_counting_as_failure(client, monkeypatch, missing):
    df = PROTECTED if missing == "bias" else CLEAN
    if missing != "stress":
        stress(client, monkeypatch, df=df)
    if missing != "independence":
        attest(client)
    if missing not in ("bias",) and df is PROTECTED:
        bias(client, monkeypatch, df=df)
    v = verdict(client, df=None if missing == "data_quality" else df, mdd="" if missing == "mdd" else MDD)
    key = {"stress": "stress_testing", "bias": "fair_lending", "data_quality": "data_quality",
           "mdd": "mdd", "independence": "independence"}[missing]
    assert key in gaps(v)
    assert v["verdict"] == "INCONCLUSIVE" and "mandatory evidence is missing" in v["verdict_desc"]
    assert v["high_count"] == 0                                             # a gap is not a model defect
    gap_findings = [f for f in v["findings"] if f.get("evidence_gap")]
    assert gap_findings and all(f["status"] in ("NOT ASSESSED", "PENDING") for f in gap_findings)
    if missing == "mdd":
        assert not finding(v, "7.1 Calibration") and finding(v, "3.0 Model Documentation")   # no fake MDD failures


def test_pending_stress_checks_block_approval(client, monkeypatch):
    stress(client, monkeypatch, status="PENDING")
    attest(client)
    v = verdict(client)
    assert items(v)["stress_testing"]["status"] == "PENDING" and v["verdict"] == "INCONCLUSIVE"


# 7-8 ── Forged browser evidence is ignored ─────────────────────────────────

def test_forged_client_evidence_is_ignored(client, monkeypatch):
    attest(client)
    forged = verdict(client, df=MISSING,
                     validation_profile_json={"missing_by_column": {}, "duplicate_rate": 0},       # claims clean data
                     shock_result_json={"feature": "f0", "magnitude_pct": 10, "pd_change_pct": 0},
                     bias_auc_gap="0.0")
    assert "stress_testing" in gaps(forged) and forged["verdict"] == "INCONCLUSIVE"          # no stress run
    assert finding(forged, "2.2 Missing Data")                                                 # server profile wins
    ignored = " ".join(forged["verdict_basis"]["ignored_client_inputs"])
    for name in ("validation_profile_json", "shock_result_json", "bias_auc_gap"):
        assert name in ignored


def test_forged_independence_confirmation_is_not_evidence(client, monkeypatch):
    stress(client, monkeypatch)
    v = verdict(client, intake_extra={"independence_confirmed": True})
    assert items(v)["independence"]["status"] == "NOT_ASSESSED" and v["verdict"] == "INCONCLUSIVE"
    assert finding(v, "1.4 Independence")[0]["status"] == "NOT ASSESSED"
    assert any("independence_confirmed" in x for x in v["verdict_basis"]["ignored_client_inputs"])


def test_independence_attestation_records_self_declared_identity_and_dataset_fingerprint(client):
    demo_fp = main.dataset_fingerprint(pd.read_csv(main.SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_portfolio.csv"))
    r = client.post("/validation/independence/attest", data={
        "registered_model_id": "MOD-001",
        "attested_by": "Independent Reviewer",
        "independent": "true",
        "session_username": "demo-user",
        "declared_name": "Demo Reviewer",
        "dataset_sha256": demo_fp,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dataset_sha256"] == demo_fp
    assert body["identity_status"] == "unauthenticated/self-declared"
    assert body["attested_by"] == "Independent Reviewer"
    assert body["session_username"] == "demo-user"


def test_governance_attestation_is_append_only_and_never_verdict_evidence(client):
    before = len(persistence.read_log(env.LOG))
    r = client.post("/validation/governance/attest", data={
        "registered_model_id": "MOD-001",
        "declared_name": "Self-declared reviewer",
        "control_state": "draft",
        "session_username": "demo-reviewer",
        "training_run_id": "TR-1",
        "dataset_sha256": main.dataset_fingerprint(pd.read_csv(main.SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_portfolio.csv")),
    })
    assert r.status_code == 200, r.text
    row = persistence.read_log(env.LOG)[-1]
    assert row["stage"] == "governance_attestation"
    assert row["summary"]["identity_status"] == "unauthenticated/self-declared"
    assert row["summary"]["control_state"] == "draft"
    assert row["summary"]["registered_model_id"] == "MOD-001"
    assert row["summary"]["training_run_id"] == "TR-1"
    assert row["summary"]["demo_dataset"] is True
    assert len(persistence.read_log(env.LOG)) == before + 1
    # Governance rows are not evidence for the verdict; they are appended audit records only.
    v = verdict(client)
    assert "governance_attestation" not in {g["evidence"] for g in v["verdict_basis"]["evidence_completeness"]["gaps"]}


def test_demo_dataset_detection_is_exact_and_server_only(client):
    clean_fp = main.dataset_fingerprint(pd.read_csv(
        main.SOURCE_OF_TRUTH_DIR / "demo_data" / "clean_portfolio.csv",
        keep_default_na=True,
        float_precision="round_trip",
    ))
    flawed_fp = main.dataset_fingerprint(pd.read_csv(
        main.SOURCE_OF_TRUTH_DIR / "demo_data" / "flawed_portfolio.csv",
        keep_default_na=True,
        float_precision="round_trip",
    ))
    unrelated = main.dataset_fingerprint(pd.DataFrame({"f0": [1, 2, 3], "default": [0, 1, 0]}))
    assert main._is_demo_dataset_fingerprint(clean_fp) is True
    assert main._is_demo_dataset_fingerprint(flawed_fp) is True
    assert main._is_demo_dataset_fingerprint(unrelated) is False
    assert main._is_demo_dataset_fingerprint("definitely-not-a-demo-sha") is False


# 9-10 ── Evidence must belong to this run, model, training and dataset ─────

def test_evidence_from_another_run_stage_or_dataset_is_rejected(client, monkeypatch):
    attest(client)
    other_data = stress(client, monkeypatch, df=CLEAN.assign(f0=CLEAN["f0"] + 1))          # different dataset
    assert "stress_testing" in gaps(verdict(client))                                         # not picked up implicitly
    bias_run = bias(client, monkeypatch)
    for run_id, fragment in ((other_data, "different dataset"), (bias_run, "not a 'stress_testing' run"),
                             ("no-such-run", "not found")):
        v = verdict(client, stress_run_id=run_id)
        assert "stress_testing" in gaps(v) and fragment in items(v)["stress_testing"]["detail"]


def test_evidence_for_another_registered_model_is_rejected(client, monkeypatch):
    attest(client)
    other_model = stress(client, monkeypatch, model_id="MOD-002")
    assert "stress_testing" in gaps(verdict(client))
    v = verdict(client, stress_run_id=other_model)
    assert "recorded for registered model 'MOD-002'" in items(v)["stress_testing"]["detail"]
    other_attestation = attest(client, model_id="MOD-002")
    v = verdict(client, independence_attestation_id=other_attestation)
    assert items(v)["independence"]["status"] == "NOT_ASSESSED"


def test_evidence_from_before_a_retrain_is_stale(client, monkeypatch):
    stress(client, monkeypatch)
    attest(client)
    assert verdict(client)["verdict"] == "APPROVED"
    env.edit_dev_entry("MOD-001", lambda e: e["lineage_contract"].update({"training_run_id": "TR-2"}))
    v = verdict(client)
    assert {"stress_testing", "independence"} <= gaps(v) and v["verdict"] == "INCONCLUSIVE"


# 12 ── Missing evidence versus failed evidence ─────────────────────────────

def test_failed_evidence_is_a_finding_not_a_gap(client, monkeypatch):
    attest(client)
    stress(client, monkeypatch, status="FAIL")
    v = verdict(client)
    assert items(v)["stress_testing"]["status"] == "FAIL" and "stress_testing" not in gaps(v)
    (f,) = finding(v, "6.0 Stress & Backtesting")
    assert (f["severity"], f["status"]) == ("MEDIUM", "WARN") and not f.get("evidence_gap")
    assert v["verdict"] == "APPROVED"                                     # 1 MEDIUM: existing rule still approves


def test_failed_bias_is_high_fail_but_missing_bias_is_a_gap(client, monkeypatch):
    stress(client, monkeypatch, df=PROTECTED)
    attest(client)
    missing = verdict(client, df=PROTECTED)
    assert missing["high_count"] == 0 and finding(missing, "8.2 Fair Lending")[0]["status"] == "NOT ASSESSED"
    bias(client, monkeypatch, gap=0.20)
    failed = verdict(client, df=PROTECTED)
    (f,) = finding(failed, "8.2 Fair Lending")
    assert (f["severity"], f["status"]) == ("HIGH", "FAIL") and failed["high_count"] == 1
    assert "fair_lending" not in gaps(failed)


def test_declared_conflict_is_a_failure(client, monkeypatch):
    stress(client, monkeypatch)
    attest(client, independent=False)
    v = verdict(client)
    (f,) = finding(v, "1.4 Independence")
    assert (f["severity"], f["status"]) == ("HIGH", "FAIL") and items(v)["independence"]["status"] == "FAIL"


# 13 ── Saved verdicts cannot hide newly missing evidence ───────────────────

def test_saved_verdict_from_older_policy_is_never_restored(client, monkeypatch):
    persistence.log_event(env.LOG, stage="findings",
                          payload={"verdict": "APPROVED", "verdict_policy_version": 4, "registered_model_id": "MOD-001",
                                   "training_run_id": "TR-1", "replication_run_id": "rep-run-1"},
                          full_payload={"verdict": "APPROVED", "findings": []})
    found = env.latest(client, "findings", registered_model_id="MOD-001", replication_run_id="rep-run-1")
    assert found["latest"] is None and any("verdict policy 4" in e["reason"] for e in found["excluded"])
    v = verdict(client)                                                    # recomputed: gaps visible
    assert v["verdict"] == "INCONCLUSIVE"
    current = env.latest(client, "findings", registered_model_id="MOD-001", replication_run_id="rep-run-1")["latest"]
    assert current["summary"]["verdict_policy_version"] == main.VERDICT_POLICY_VERSION
    assert current["summary"]["evidence_complete"] is False


def test_frontend_only_reuses_current_policy_verdicts():
    path = env.BACKEND_DIR.parent / "aegis-frontend" / "src" / "routes" / "validation.findings.tsx"
    if not path.exists():
        pytest.skip("frontend sources not present next to this backend copy")
    src = path.read_text(encoding="utf-8")
    assert "MIN_VERDICT_POLICY_VERSION = 7" in src and "evidence_completeness" in src
    assert 'form.append("bias_auc_gap"' not in src and '"validation_profile_json"' not in src


# Attestation endpoint ───────────────────────────────────────────────────────

def test_attestation_requires_a_registered_model_with_lineage_and_a_name(client):
    def post(**data):
        return client.post("/validation/independence/attest", data={"attested_by": "A", "independent": "true", **data})
    assert post(registered_model_id="MOD-999").status_code == 404
    assert post(registered_model_id="MOD-001", attested_by=" ").status_code == 400
    store = persistence.load_model_inventory()
    store["development"].append({"model_id": "MOD-003", "model_name": "No lineage"})
    persistence.save_model_inventory(store)
    assert post(registered_model_id="MOD-003").status_code == 409
    body = post(registered_model_id="MOD-001").json()
    assert body["training_run_id"] == "TR-1" and body["attested_by"] == "A" and body["independent"] is True


def test_verdict_does_not_mutate_inventory(client, monkeypatch):
    stress(client, monkeypatch)
    attest(client)
    path = persistence.get_model_inventory_path()
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    for kwargs in ({}, {"df": None}, {"mdd": ""}):
        verdict(client, **kwargs)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
