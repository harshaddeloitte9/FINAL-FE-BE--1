"""Batch 3D: stress, bias and the benchmark champion evaluate the REGISTERED
model (finding E2), never a default refit attributed to its ID.

Isolated temporary app_data; small synthetic models are trained through the
real /models/train so every registered model has a genuine lineage contract
and scoring bundle. No real data is touched.
"""
import hashlib
import io
import json

import numpy as np
import pytest

import _aegis_test_env as env
import main
import model_lineage
import persistence

DF = env.dataset_coefs(3000, [1.0, 0.5, 0.2, 0.0], seed=21)
DF = DF.assign(gender=np.where(np.arange(len(DF)) % 2 == 0, "F", "M"))       # protected column, present at training
CSV = env.to_csv(DF)
OTHER_CSV = env.to_csv(DF.assign(f0=DF["f0"] + 0.5))                          # not the training dataset
# The server fingerprints the table it parses from the upload, so tests that
# call the backend functions directly use the same CSV-parsed table.
import pandas as pd  # noqa: E402
DF = pd.read_csv(io.BytesIO(CSV))
MDD = ("Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions are documented. "
       "Macro overlays use GDP and unemployment.")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("registered_stage_eval")) as c:
        yield c


@pytest.fixture(scope="module")
def model(client):
    return env.train(client, CSV, "Registered Stage Model")["model_id"]


@pytest.fixture()
def no_refit(monkeypatch):
    """Any refit on the registered path is a failure of this batch."""
    def boom(*a, **k):
        raise AssertionError("a registered-model evaluation must not refit")
    monkeypatch.setattr(main, "run_replication", boom)
    monkeypatch.setattr(main, "run_bias_check", boom)


@pytest.fixture()
def loads(monkeypatch):
    seen = []
    real = model_lineage._deserialize_verified

    def spy(data):
        seen.append(hashlib.sha256(data).hexdigest())
        return real(data)
    monkeypatch.setattr(model_lineage, "_deserialize_verified", spy)
    return seen


def contract(model_id):
    return env.dev_entry(model_id)["lineage_contract"]


def files(csv=CSV):
    return {"file": ("dev.csv", io.BytesIO(csv), "text/csv")}


def post_stress(client, model_id=None, csv=CSV, **extra):
    data = {"target_col": "default", "algorithm": "Logistic Regression", **extra}
    if model_id:
        data["registered_model_id"] = model_id
    return client.post("/validation/stress/run", data=data, files=files(csv))


def post_bias(client, model_id=None, csv=CSV, **extra):
    data = {"target_col": "default", "algorithm": "Logistic Regression", "protected_col": "gender", **extra}
    if model_id:
        data["registered_model_id"] = model_id
    return client.post("/validation/stage7/bias-check", data=data, files=files(csv))


def post_benchmark(client, model_id=None, csv=CSV, **extra):
    data = {"model_name": "Logistic Regression", "target_col": "default", "challenger_model_name": "Logistic Regression", **extra}
    if model_id:
        data["registered_model_id"] = model_id
    return client.post("/validation/performance", data=data, files=files(csv))


def assert_registered_identity(evidence, model_id):
    c = contract(model_id)
    assert evidence["evaluation_mode"] == model_lineage.EVALUATION_MODE_REGISTERED
    assert evidence["registered_model_id"] == model_id
    assert evidence["training_run_id"] == c["training_run_id"]
    assert evidence["test_index_sha256"] == c["split"]["test_index_sha256"]
    assert evidence["bundle_sha256"] == c["artifact"]["sha256"]
    assert evidence["dataset_sha256"] == c["dataset"]["sha256"]


# 1-3 ── Each stage evaluates the verified registered bundle, no refit ─────

def test_stress_uses_the_registered_scoring_bundle(client, model, no_refit, loads):
    r = post_stress(client, model)
    assert r.status_code == 200, r.text
    body = r.json()
    assert_registered_identity(body["evidence"], model)
    assert loads == [contract(model)["artifact"]["sha256"]]                 # the verified bundle was loaded
    assert body["report"]["sensitivity"]["method"] == "permutation"         # 6.1 without removal-refits
    logged = persistence.get_run(env.LOG, body["evidence"]["run_id"])["summary"]
    assert logged["evaluation_mode"] == model_lineage.EVALUATION_MODE_REGISTERED and logged["training_run_id"]


def test_bias_uses_the_registered_scoring_bundle(client, model, no_refit, loads):
    r = post_bias(client, model)
    assert r.status_code == 200, r.text
    body = r.json()
    assert_registered_identity(body["evidence"], model)
    assert loads and body["success"] is True and body["check"]["check_id"] == "8.2"
    # Group AUCs are computed on the registered model's own predictions.
    ctx = model_lineage.registered_evaluation(DF, model, dataset_sha256=main.dataset_fingerprint(DF))
    expected = main.bias_from_predictions(DF, ctx["y_test"], ctx["y_proba"], "gender")
    assert body["rows"] == expected["rows"]


def test_benchmark_champion_is_the_registered_model_and_challenger_is_separate(client, model, monkeypatch, loads):
    monkeypatch.setattr(main, "run_replication", lambda *a, **k: (_ for _ in ()).throw(AssertionError("champion refit")))
    r = post_benchmark(client, model)
    assert r.status_code == 200, r.text
    ev = r.json()["evidence"]
    assert_registered_identity(ev, model)
    assert ev["champion"]["evaluation_mode"] == model_lineage.EVALUATION_MODE_REGISTERED and ev["champion"]["registered_model_id"] == model
    assert ev["challenger"] == {"evaluation_mode": model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT, "algorithm": "Logistic Regression"}
    bench = r.json()["report"]["benchmark"]
    assert bench["status"] == "OK"
    assert bench["evaluation"]["test_index_sha256"] == contract(model)["split"]["test_index_sha256"]   # 12 same rows
    assert bench["evaluation"]["test_rows"] == contract(model)["split"]["test_rows"]
    # Champion metrics are the registered bundle's scores on those rows.
    ctx = model_lineage.registered_evaluation(DF, model, dataset_sha256=main.dataset_fingerprint(DF))
    assert r.json()["report"]["metrics"]["roc_auc"] == pytest.approx(ctx["metrics"]["roc_auc"])


# 5 / 11 ── Independent refits are labelled and never count as registered ──

def test_refits_are_never_attributed_to_a_registered_model(client):
    for post in (post_stress, post_bias, post_benchmark):
        r = post(client, None)
        assert r.status_code == 200, r.text
        ev = r.json()["evidence"]
        assert ev["evaluation_mode"] == model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT
        assert ev["registered_model_id"] is None and ev["training_run_id"] is None


def test_refit_or_mislabelled_runs_cannot_satisfy_registered_evidence(client, model):
    refit = post_stress(client, None).json()["evidence"]["run_id"]
    # A run written the pre-3D way: the registered ID as a label on a refit.
    mislabelled = persistence.log_event(env.LOG, stage="stress_testing",
                                        payload={**main.registered_run_identity(model, DF), "model_name": "Logistic Regression"},
                                        full_payload={"stage": "stress", "report": {"available": True, "summary": {"pass": 1}}})
    claimed = {"registered_model_id": model, "dataset_sha256": main.dataset_fingerprint(DF)}
    for run_id in (refit, mislabelled):
        run, reason = main._linked_stage_run("stress_testing", run_id, claimed, require_dataset=True,
                                             require_registered_evaluation=True)
        assert run is None and reason
    run, reason = main._linked_stage_run("stress_testing", None, claimed, require_dataset=True, require_registered_evaluation=True)
    assert run is None or run["summary"].get("evaluation_mode") == model_lineage.EVALUATION_MODE_REGISTERED


# 6-10 ── Fail closed, without falling back to a refit ──────────────────────

@pytest.fixture()
def broken_models(client, model):
    """MOD-X1: no lineage. MOD-X2: bundle tampered (copy of the real contract
    pointing at a modified copy of the bundle)."""
    c = contract(model)
    bundle_path = persistence.BACKEND_DIR / c["artifact"]["path"]
    tampered_rel = c["artifact"]["path"].replace(".joblib", "_tampered.joblib")
    (persistence.BACKEND_DIR / tampered_rel).write_bytes(bundle_path.read_bytes() + b"tamper")
    store = persistence.load_model_inventory()
    store["development"] += [
        {"model_id": "MOD-X1", "model_name": "No lineage", "status": "In Development"},
        {"model_id": "MOD-X2", "model_name": "Tampered", "status": "In Development",
         "lineage_contract": {**c, "model_id": "MOD-X2", "artifact": {"path": tampered_rel, "sha256": c["artifact"]["sha256"]}}},
    ]
    persistence.save_model_inventory(store)
    yield
    store = persistence.load_model_inventory()
    store["development"] = [m for m in store["development"] if m["model_id"] not in ("MOD-X1", "MOD-X2")]
    persistence.save_model_inventory(store)


@pytest.mark.parametrize("post", [post_stress, post_bias, post_benchmark])
def test_unresolvable_registered_models_fail_closed(client, model, broken_models, no_refit, post):
    cases = [
        (dict(model_id="MOD-404"), 404, "not_found"),                                   # 6 unknown
        (dict(model_id="MOD-X1"), 409, "lineage_missing"),                              # 7 missing lineage
        (dict(model_id="MOD-X2"), 409, "bundle_integrity_failed"),                      # 8 hash mismatch
        (dict(model_id=model, csv=OTHER_CSV), 409, "dataset_mismatch"),                 # 9 dataset mismatch
        (dict(model_id=model, expected_training_run_id="an-older-training"), 409, "training_run_mismatch"),  # 10
    ]
    for kwargs, status, fragment in cases:
        r = post(client, **kwargs)
        assert r.status_code == status, (kwargs, r.text)
        assert fragment in r.json()["detail"]


def test_matching_expected_training_run_is_accepted(client, model, no_refit):
    r = post_stress(client, model, expected_training_run_id=contract(model)["training_run_id"])
    assert r.status_code == 200, r.text


# 10 / 12 ── Verdict-side identity: stale training, test rows, label only ──

def _benchmark_summary_override(run_id, **fields):
    rows = persistence.read_log(env.LOG)
    row = next(r for r in rows if r["run_id"] == run_id)
    summary = {**row["summary"], **fields}
    return persistence.log_event(env.LOG, stage="performance", payload={k: v for k, v in summary.items() if k != "record_version"},
                                 full_payload=persistence.get_run(env.LOG, run_id)["full_payload"])


def test_benchmark_acceptance_requires_registered_champion_and_identical_rows(client, model):
    good = post_benchmark(client, model).json()["evidence"]["run_id"]
    claimed = {"registered_model_id": model, "dataset_sha256": main.dataset_fingerprint(DF)}
    assert main.assess_benchmark_evidence(good, claimed)["status"] == "ACCEPTED"
    for fields, fragment in (({"evaluation_mode": model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT}, "was not the registered model"),
                             ({"evaluation_mode": None}, "was not the registered model"),
                             ({"test_index_sha256": "other-rows"}, "recorded test rows"),
                             ({"training_run_id": "an-older-training"}, "current training")):
        forged = _benchmark_summary_override(good, **fields)
        out = main.assess_benchmark_evidence(forged, claimed)
        assert out["status"] == "REJECTED" and fragment in " ".join(out["reasons"]), (fields, out)


def test_evidence_becomes_stale_after_a_retrain(client, model):
    run_id = post_stress(client, model).json()["evidence"]["run_id"]
    claimed = {"registered_model_id": model, "dataset_sha256": main.dataset_fingerprint(DF)}
    assert main._linked_stage_run("stress_testing", run_id, claimed, True, True)[0] is not None
    original = contract(model)["training_run_id"]
    env.edit_dev_entry(model, lambda e: e["lineage_contract"].update({"training_run_id": "a-newer-training"}))
    try:
        run, reason = main._linked_stage_run("stress_testing", run_id, claimed, True, True)
        assert run is None and "current training" in reason
    finally:
        env.edit_dev_entry(model, lambda e: e["lineage_contract"].update({"training_run_id": original}))


# 13 ── Evidence completeness end to end with registered evaluations ───────

def test_registered_stage_evidence_completes_the_verdict(client, model, monkeypatch):
    assert post_stress(client, model).status_code == 200
    assert post_bias(client, model).status_code == 200
    assert client.post("/validation/independence/attest",
                       data={"registered_model_id": model, "attested_by": "V", "independent": "true"}).status_code == 200
    monkeypatch.setattr(main, "assess_replication_evidence", lambda run_id, claimed: {
        "status": "PASS", "run_id": run_id, "reasons": [], "execution_failed": False,
        "metrics": {"roc_auc": 0.8, "gini": 0.6, "ks": 0.4, "recall": 0.7, "brier_score": 0.1}, "reference_metrics": {},
        "failed_mandatory_checks": [], "failed_other_checks": []})
    r = client.post("/validation/stage8/findings",
                    data={"intake_json": json.dumps({"registered_model_id": model}), "mdd_text": MDD,
                          "replication_run_id": "rep", "registered_model_id": model}, files=files())
    basis = r.json()["verdict_basis"]["evidence_completeness"]
    for key in ("stress_testing", "fair_lending"):
        assert basis["items"][key]["evaluation_mode"] == model_lineage.EVALUATION_MODE_REGISTERED
        assert basis["items"][key]["test_index_sha256"] == contract(model)["split"]["test_index_sha256"]
    assert "stress_testing" not in {g["evidence"] for g in basis["gaps"]}
    assert "fair_lending" not in {g["evidence"] for g in basis["gaps"]}


def test_registered_evaluation_does_not_mutate_inventory_or_bundles(client, model, no_refit):
    path = persistence.get_model_inventory_path()
    bundle = persistence.BACKEND_DIR / contract(model)["artifact"]["path"]
    before = (path.read_bytes(), bundle.read_bytes(), bundle.stat().st_mtime_ns)
    post_stress(client, model)
    post_bias(client, model)
    assert (path.read_bytes(), bundle.read_bytes(), bundle.stat().st_mtime_ns) == before
