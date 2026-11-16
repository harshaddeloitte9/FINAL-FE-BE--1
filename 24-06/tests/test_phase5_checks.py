"""Phase 5 (G1-G4): seed-stability independence, split identity, curve
provenance and stress sensitivity labelling.

G1  R4.5 / R4.6 are never PASS on repeated evaluation of identical (or
    unrecorded) test rows; chronological splits are NOT_ASSESSED.
G4  every seed execution records its seed, split strategy, test-row
    fingerprint and count, dataset fingerprint, model / training run,
    status and metrics; the number of distinct test sets is recorded.
G2  ROC / PR curves carry their prediction source, partition, rows and
    dataset / test-row fingerprints, matching the predictions plotted.
G3  stress sensitivity reports its method (permutation vs removal + refit).
Isolated temporary app_data; synthetic data; real training and replication.
"""
import io
import json

import numpy as np
import pandas as pd
import pytest

import _aegis_test_env as env
import main
import model_lineage
import persistence
import stability_checks as stability
from evaluate_new import compute_pr_curve, compute_roc_curve
from val_replication_core import evaluate_replication_checks

_df = env.dataset_coefs(2500, [1.0, 0.6, 0.3, 0.0], seed=71)
_df["application_date"] = pd.date_range("2017-01-01", periods=len(_df), freq="D").strftime("%Y-%m-%d")
CSV = env.to_csv(_df)
DF = pd.read_csv(io.BytesIO(CSV))
MDD = ("Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions are documented. "
       "Macro overlays use GDP and unemployment.")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("phase5")) as c:
        yield c


@pytest.fixture(scope="module")
def stratified(client):
    mid = env.train(client, CSV, "P5 Stratified")["model_id"]
    return {"model_id": mid, "rep": env.replicate(client, CSV, mid)}


@pytest.fixture(scope="module")
def temporal(client):
    mid = env.train(client, CSV, "P5 Temporal", split_strategy="temporal", temporal_date_col="application_date")["model_id"]
    return {"model_id": mid, "rep": env.replicate(client, CSV, mid)}


def checks(rep):
    return {c["id"]: c for c in rep["report"]["replication"]["checks"]}


def stability_of(rep):
    return rep["report"]["replication"]["result"]["stability"]


# ── G1 / G4 units ──────────────────────────────────────────────────────────

def _run(seed, fp, status="COMPLETED"):
    return {"seed": seed, "status": status, "test_index_sha256": fp, "auc": 0.75}


def test_seed_run_independence_rules():
    ind = stability.seed_run_independence([_run(1, "a"), _run(2, "b"), _run(3, "c")], "stratified_random")
    assert ind["independent"] is True and ind["distinct_test_sets"] == 3 and ind["completed_runs"] == 3
    same = stability.seed_run_independence([_run(1, "a"), _run(2, "a"), _run(3, "a")], "stratified_random")
    assert same["independent"] is False and "1 distinct test sets across 3" in same["reason"]
    chrono = stability.seed_run_independence([_run(1, "a"), _run(2, "a")], "temporal")
    assert chrono["independent"] is False and "Chronological split" in chrono["reason"] and "Model Risk" in chrono["reason"]
    unrecorded = stability.seed_run_independence([{"seed": 1, "status": "COMPLETED"}], "stratified_random")
    assert unrecorded["independent"] is False and "did not record" in unrecorded["reason"]
    assert stability.seed_run_independence([_run(1, "a", "FAILED")], "stratified_random")["independent"] is False


def test_identical_test_sets_never_produce_pass():
    """Even with perfectly consistent runs, identical test rows give NOT_ASSESSED."""
    runs = [{**_run(s, "same"), "auc_se": 0.01, "auc_ci": [0.73, 0.77], "test_rows": 300, "test_positives": 90,
             "test_negatives": 210, "importance": {"f0": 0.1, "f1": 0.05}, "importance_sd": {"f0": 0.001, "f1": 0.001},
             "selected": ["f0", "f1"], "direction": {}, "model_inputs": ["f0", "f1"]} for s in range(5)]
    result = {"success": True, "metrics": {"roc_auc": 0.75, "gini": 0.5, "ks": 0.4}, "seed_aucs": [0.75] * 5,
              "stability": {"runs": runs, "independence": stability.seed_run_independence(runs, "stratified_random"),
                            "determinism": None, "main_evaluation": {}, "temporal": None}}
    out = {c["id"]: c for c in evaluate_replication_checks(result, {}, list(range(5)))}
    assert out["R4.5"]["status"] == "NOT_ASSESSED" and out["R4.6"]["status"] == "NOT_ASSESSED"
    # A result that does not record independence at all is not trusted either.
    result["stability"].pop("independence")
    out = {c["id"]: c for c in evaluate_replication_checks(result, {}, list(range(5)))}
    assert out["R4.5"]["status"] == "NOT_ASSESSED" and out["R4.6"]["status"] == "NOT_ASSESSED"


# ── G1 / G4 end to end ─────────────────────────────────────────────────────

def test_stratified_seed_runs_are_independent_and_fully_identified(stratified):
    stab = stability_of(stratified["rep"])
    contract = env.dev_entry(stratified["model_id"])["lineage_contract"]
    completed = [r for r in stab["runs"] if r["status"] == "COMPLETED"]
    assert len(completed) == 5
    for r in completed:
        assert r["split_strategy"] == "stratified_random"
        assert r["test_index_sha256"] and r["test_rows"] > 0 and r["auc"] is not None
        assert r["dataset_sha256"] == main.dataset_fingerprint(DF)
        assert r["registered_model_id"] == stratified["model_id"] and r["training_run_id"] == contract["training_run_id"]
    # The recorded fingerprints are the test rows each seed's split really produced.
    for r in completed[:2]:
        (_, _, Xte, _, _, _), _ = model_lineage.contract_split(DF, contract, random_seed=r["seed"])
        assert r["test_index_sha256"] == model_lineage.index_fingerprint(Xte.index)
    ind = stab["independence"]
    assert ind["independent"] is True and ind["distinct_test_sets"] == 5 == ind["completed_runs"]
    c = checks(stratified["rep"])
    assert c["R4.5"]["status"] != "NOT_ASSESSED" and c["R4.6"]["status"] != "NOT_ASSESSED"
    assert "test sets differ" in c["R4.6"]["_methodology"]


def test_chronological_split_r45_r46_are_not_assessed(temporal):
    stab = stability_of(temporal["rep"])
    assert stab["independence"]["independent"] is False and stab["independence"]["distinct_test_sets"] == 1
    assert all(r["split_strategy"] == "temporal" for r in stab["runs"])
    c = checks(temporal["rep"])
    for cid in ("R4.5", "R4.6"):
        assert c[cid]["status"] == "NOT_ASSESSED"
        assert "Chronological split" in c[cid]["observed"] and "Model Risk Management" in c[cid]["observed"]


def _verdict(client, model_id, run_id):
    client.post("/validation/independence/attest", data={"registered_model_id": model_id, "attested_by": "V", "independent": "true"})
    data = {"intake_json": json.dumps({"registered_model_id": model_id, "model_name": "x", "model_tier": "Tier 2"}),
            "mdd_text": MDD, "replication_run_id": run_id, "registered_model_id": model_id}
    r = client.post("/validation/stage8/findings", data=data, files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def test_not_assessed_stability_makes_the_verdict_inconclusive(client, temporal):
    v = _verdict(client, temporal["model_id"], temporal["rep"]["evidence"]["run_id"])
    assert v["verdict"] not in ("APPROVED", "CONDITIONALLY APPROVED")
    rep = v["verdict_basis"]["replication"]
    assert rep["status"] == "INCONCLUSIVE"
    statuses = {c["id"]: c["status"] for c in rep["mandatory_checks"]}
    assert statuses["R4.5"] == "NOT_ASSESSED" and statuses["R4.6"] == "NOT_ASSESSED"


def test_saved_pass_without_independence_evidence_is_not_trusted(client, stratified):
    """A run saved before independence was recorded (simulated by removing it
    from the saved record, in the temporary log only) cannot carry R4.5/R4.6."""
    run_id = stratified["rep"]["evidence"]["run_id"]
    row = next(r for r in persistence.read_log(env.LOG) if r["run_id"] == run_id)
    path = persistence.BACKEND_DIR / row["artifact_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["report"]["replication"]["result"]["stability"].pop("independence", None)
    for c in payload["report"]["replication"]["checks"]:
        if c["id"] in ("R4.5", "R4.6"):
            c["status"] = "PASS"
    path.write_text(json.dumps(payload), encoding="utf-8")
    ev = main.assess_replication_evidence(run_id, {"registered_model_id": stratified["model_id"],
                                                  "dataset_sha256": main.dataset_fingerprint(DF)})
    assert ev["status"] in ("INCONCLUSIVE", "FAIL")
    statuses = {c["id"]: c["status"] for c in ev["mandatory_checks"]}
    assert statuses["R4.5"] == "NOT_ASSESSED" and statuses["R4.6"] == "NOT_ASSESSED"
    assert main.VERDICT_POLICY_VERSION == 7


# ── G2: curve provenance matches the plotted predictions ──────────────────

def test_replication_curves_are_the_independent_retrains_predictions(client, temporal):
    mid = env.train(client, CSV, "P5 Curves")["model_id"]
    rep = env.replicate(client, CSV, mid)
    contract = env.dev_entry(mid)["lineage_contract"]
    roc, pr = rep["report"]["roc_curve"], rep["report"]["pr_curve"]
    for curve in (roc, pr):
        p = curve["provenance"]
        assert p["prediction_source"] == "independent_retrain" and p["evaluation_partition"] == "test"
        assert p["rows"] == contract["split"]["test_rows"] and p["test_index_sha256"] == contract["split"]["test_index_sha256"]
        assert p["dataset_sha256"] == main.dataset_fingerprint(DF)
    fit = model_lineage._fit_from_contract(DF, contract)
    proba = fit["pipeline"].predict_proba(fit["X_test"])[:, 1]
    assert roc["points"] == compute_roc_curve(np.asarray(fit["y_test"]), proba)
    assert pr["points"] == compute_pr_curve(np.asarray(fit["y_test"]), proba)


def test_benchmark_curves_are_the_registered_bundle_and_challenger(client, stratified):
    mid = stratified["model_id"]
    r = client.post("/validation/performance", data={"target_col": "default", "registered_model_id": mid, "model_name": "Logistic Regression",
                                                     "challenger_model_name": "Logistic Regression"},
                    files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")})
    assert r.status_code == 200, r.text
    report = r.json()["report"]
    ev = model_lineage.registered_evaluation(DF, mid, dataset_sha256=main.dataset_fingerprint(DF))
    p = report["roc_curve"]["provenance"]
    assert p["prediction_source"] == "registered_bundle" and p["test_index_sha256"] == ev["identity"]["test_index_sha256"]
    assert p["rows"] == len(ev["y_test"])
    assert report["roc_curve"]["points"] == compute_roc_curve(np.asarray(ev["y_test"]).astype(int), np.asarray(ev["y_proba"]).astype(float))
    cp = report["benchmark"]["roc_curve"]["provenance"]
    assert cp["prediction_source"] == "challenger_refit" and cp["test_index_sha256"] == p["test_index_sha256"]
    assert cp["dataset_sha256"] == p["dataset_sha256"] == main.dataset_fingerprint(DF) and cp["rows"] == p["rows"]


# ── G3: stress sensitivity method ──────────────────────────────────────────

def test_stress_sensitivity_reports_its_method(client, stratified):
    reg = client.post("/validation/stress/run", data={"target_col": "default", "registered_model_id": stratified["model_id"]},
                      files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")}).json()["report"]["sensitivity"]
    assert reg["method"] == "permutation"
    assert "permuting" in reg["check"]["observed"] and "no refit" in reg["check"]["observed"]
    assert "removing" not in reg["check"]["observed"]
    refit = client.post("/validation/stress/run", data={"target_col": "default", "algorithm": "Logistic Regression"},
                        files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")}).json()["report"]["sensitivity"]
    assert refit["method"] == "removal_refit" and "removing" in refit["check"]["observed"]


# ── Unchanged: R4.7 executed and ablation retrains ─────────────────────────

def test_r47_and_ablation_still_execute(stratified):
    c = checks(stratified["rep"])
    assert c["R4.7"]["status"] == "PASS"
    assert {s["id"] for s in c["R4.7"]["_subchecks"]} >= {"S1", "S2", "S3", "S4", "S5", "S6"}
    runs = stratified["rep"]["report"]["replication"]["result"]["ablation_runs"]
    assert runs and all(r["status"] == "COMPLETED" and r["feature_removed"] for r in runs)
