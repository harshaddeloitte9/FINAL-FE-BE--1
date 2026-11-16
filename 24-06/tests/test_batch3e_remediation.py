"""Batch 3E: remaining audit remediation (E3, E5, E7-E14).

Unit, endpoint and adversarial tests. Isolated temporary app_data; small
synthetic models are trained through the real /models/train. No real data
is read or written.
"""
import hashlib
import io
import json

import numpy as np
import pandas as pd
import pytest

import _aegis_test_env as env
import evaluate_new
import main
import model_lineage
import persistence
import train_new

DF = env.dataset_coefs(1500, [1.0, 0.6, 0.3, 0.0], seed=33)
DF["application_date"] = pd.date_range("2019-01-01", periods=len(DF), freq="D").strftime("%Y-%m-%d")
CSV = env.to_csv(DF)
DF = pd.read_csv(io.BytesIO(CSV))                                   # the table the server parses
OTHER_CSV = env.to_csv(DF.assign(f0=DF["f0"] + 0.25))                # a different dataset
SAME_TABLE_OTHER_FILE = CSV.replace(b"\n", b"\r\n")                  # same table, different file bytes


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("batch3e")) as c:
        yield c


@pytest.fixture(scope="module")
def trained(client):
    return env.train(client, CSV, "Batch3E Model")


@pytest.fixture(scope="module")
def temporal(client):
    return env.train(client, CSV, "Batch3E Temporal", split_strategy="temporal", temporal_date_col="application_date")


def contract(model_id):
    return env.dev_entry(model_id)["lineage_contract"]


def files(csv=CSV, name="dev.csv"):
    return {"file": (name, io.BytesIO(csv), "text/csv")}


def evaluate(client, model_id, csv=CSV, **extra):
    return client.post("/models/evaluate", data={"target_col": "default", "registered_model_id": model_id, **extra}, files=files(csv))


# ── E3 / E5: threshold selection never uses the test rows ──────────────────

def test_operating_threshold_selector_units():
    y = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    p = np.array([0.1, 0.2, 0.8, 0.7, 0.3, 0.9, 0.6, 0.4])
    manual = evaluate_new.select_operating_threshold(y, p, manual=0.37)
    assert manual["method"] == "manual" and manual["value"] == 0.37 and manual["source_partition"] == "user_specified"
    auto = evaluate_new.select_operating_threshold(y, p)
    assert auto["method"] == "f1_max" and auto["source_partition"] == "validation" and auto["rows"] == 8
    assert auto["value"] == evaluate_new.select_best_threshold(y, p)["threshold"]
    for bad_y, bad_p in ((None, None), (np.array([1, 1, 1]), np.array([0.2, 0.5, 0.9])), (np.array([]), np.array([]))):
        d = evaluate_new.select_operating_threshold(bad_y, bad_p)
        assert d["method"] == "default_0.5" and d["degraded"] is True and d["source_partition"] is None and d["value"] == 0.5
    # Remaining auto-selection inside compute_binary_metrics is flagged in-sample.
    m = evaluate_new.compute_binary_metrics(y, (p > 0.5).astype(int), p, threshold=None)
    assert m["threshold_selection"]["source_partition"] == "evaluated_data_in_sample"


def _recompute_partitions(c):
    (Xtr, Xv, Xte, ytr, yv, yte), _ = model_lineage.contract_split(DF, c)
    return Xv, yv, Xte, yte


def test_training_threshold_is_selected_on_validation_and_recorded(client, trained):
    prov = trained["threshold_provenance"]
    assert prov["method"] == "f1_max" and prov["source_partition"] == "validation" and prov["degraded"] is False
    assert trained["evaluation_metrics"]["threshold_used"] == prov["value"]
    assert trained["evaluation_metrics"]["evaluation_partition"] == "test"
    assert trained["training_config"]["threshold_mode"] == "auto_validation"
    c = contract(trained["model_id"])
    assert c["training"]["threshold"] == prov["value"] and c["training"]["threshold_provenance"]["source_partition"] == "validation"
    # Adversarial: the recorded threshold equals the F1-max on the VALIDATION
    # rows scored by the registered bundle (and the validation row count matches).
    bundle = model_lineage.load_registered_scoring_bundle(trained["model_id"])["bundle"]
    Xv, yv, _, _ = _recompute_partitions(c)
    proba_v = bundle["pipeline"].predict_proba(model_lineage._transform_for_bundle(bundle, Xv))[:, 1]
    assert evaluate_new.select_best_threshold(yv.values, proba_v)["threshold"] == prov["value"]
    assert prov["rows"] == len(yv) == c["split"]["val_rows"]


def test_threshold_is_not_reoptimised_on_test_rows(client, trained, monkeypatch):
    """If the test rows were used, changing only the TEST labels would move
    the threshold. Selection sees validation rows only, so it cannot."""
    seen = []
    real = evaluate_new.select_operating_threshold

    def spy(y_val, proba_val, manual=None):
        seen.append(None if y_val is None else len(y_val))
        return real(y_val, proba_val, manual=manual)
    monkeypatch.setattr(main, "select_operating_threshold", spy)
    body = env.train(client, CSV, "Batch3E Spy")
    c = contract(body["model_id"])
    assert seen == [c["split"]["val_rows"]]                       # only the validation partition was offered


def test_manual_threshold_is_labelled_and_used_everywhere(client):
    body = env.train(client, CSV, "Batch3E Manual", threshold=0.42)
    assert body["threshold_provenance"]["method"] == "manual"
    assert body["evaluation_metrics"]["threshold_used"] == 0.42
    assert body["training_config"]["threshold_mode"] == "manual"
    c = contract(body["model_id"])
    assert c["training"]["threshold"] == 0.42
    op = model_lineage.operating_threshold(c)
    assert op["status"] == "PASS" and op["value"] == 0.42
    r = client.post("/models/train", data={"target_col": "default", "model_name": "bad", "threshold": "1.5"}, files=files())
    assert r.status_code == 400


def test_operating_threshold_contract_statuses():
    prov = {"method": "f1_max", "source_partition": "validation", "degraded": False}
    assert model_lineage.operating_threshold({"training": {"threshold": 0.3, "threshold_provenance": prov}})["status"] == "PASS"
    warn = model_lineage.operating_threshold({"training": {"threshold": 0.3}})
    assert warn["status"] == "WARN" and warn["value"] == 0.3
    legacy = model_lineage.operating_threshold({"training": {"threshold": None}, "development_metrics": {"threshold_used": 0.21}})
    assert legacy["status"] == "WARN" and legacy["value"] == 0.21 and "unknown" in legacy["detail"]
    none = model_lineage.operating_threshold({"training": {}, "development_metrics": {}})
    assert none["status"] == "FAIL" and none["value"] == 0.5
    # An in-sample provenance is never accepted as PASS.
    assert model_lineage.operating_threshold({"training": {"threshold": 0.3, "threshold_provenance": {
        "method": "f1_max", "source_partition": "evaluated_data_in_sample"}}})["status"] == "WARN"


def test_reproduction_uses_the_recorded_threshold_and_reports_L10_L11(client, trained):
    rep = env.replicate(client, CSV, registered_model_id=trained["model_id"])
    status = env.lineage_status(rep)
    assert status["L10"] == "PASS" and status["L11"] == "PASS"
    m = env.methodology(rep)
    assert m["operating_threshold"]["value"] == trained["threshold_provenance"]["value"]
    assert m["exact_artifact_reproduction"]["status"] == "REPRODUCED"


def test_missing_threshold_provenance_blocks_instead_of_passing(client, trained):
    body = env.train(client, CSV, "Batch3E Legacy Threshold")
    mid = body["model_id"]

    def strip(entry):
        entry["lineage_contract"]["training"]["threshold_provenance"] = None
        entry["lineage_contract"]["split"].pop("report", None)
    env.edit_dev_entry(mid, strip)
    rep = env.replicate(client, CSV, registered_model_id=mid)
    status = env.lineage_status(rep)
    assert status["L10"] == "WARN" and status["L11"] == "WARN"
    lim = " ".join(env.methodology(rep)["limitations"])
    assert "Operating threshold provenance" in lim and "Split methodology" in lim
    # The verdict treats every non-PASS lineage check outside this set as a
    # reproduction gap, so L10 / L11 warnings block approval.
    assert not {"L10", "L11"} & set(main.NON_BLOCKING_LINEAGE_CHECKS)
    assert main.VERDICT_POLICY_VERSION >= 6


# ── E13: stratification fallback is never silent ───────────────────────────

def test_split_report_records_stratification_and_fallback():
    X = pd.DataFrame({"a": np.arange(100.0)})
    y = pd.Series([1] * 30 + [0] * 70)
    rep = {}
    train_new.split_data(X, y, test_size=0.2, val_size=0.2, random_state=1, report=rep)
    assert rep["achieved"] == "stratified" and rep["degraded"] is False and rep["fallbacks"] == []
    assert sum(rep["class_counts"]["test"].values()) == 20
    # A class with a single member cannot be stratified: recorded, degraded.
    y2 = pd.Series([1] + [0] * 99)
    rep2 = {}
    train_new.split_data(X, y2, test_size=0.2, val_size=0.2, random_state=1, report=rep2)
    assert rep2["degraded"] is True and rep2["achieved"] == "random_fallback"
    assert rep2["fallbacks"] and "stratif" in rep2["fallbacks"][0]["reason"].lower()


def test_degraded_split_is_a_blocking_lineage_warning():
    c = {"split": {"strategy": "stratified_random", "report": {"degraded": True, "achieved": "random_fallback",
                                                             "fallbacks": [{"partition": "test", "reason": "x"}]}}}
    assert model_lineage.split_methodology_check(c)["status"] == "WARN"
    assert model_lineage.split_methodology_check({"split": {}})["status"] == "WARN"
    ok = {"split": {"strategy": "stratified_random", "report": {"degraded": False, "achieved": "stratified"}}}
    assert model_lineage.split_methodology_check(ok)["status"] == "PASS"


def test_training_records_the_split_report(trained):
    c = contract(trained["model_id"])
    assert c["split"]["strategy"] == "stratified_random"
    assert c["split"]["report"]["achieved"] == "stratified" and c["split"]["report"]["degraded"] is False
    assert set(c["split"]["report"]["class_counts"]) == {"train", "validation", "test"}
    assert trained["split_report"]["achieved"] == "stratified"


# ── E14: explicit chronological validation ─────────────────────────────────

def test_temporal_split_unit():
    X = pd.DataFrame({"a": np.arange(50.0)}, index=np.arange(50)[::-1])
    y = pd.Series(np.arange(50) % 2, index=X.index)
    dates = pd.Series(pd.date_range("2020-01-01", periods=50, freq="D"), index=np.arange(50))
    rep = {}
    Xtr, Xv, Xte, *_ = train_new.temporal_split(X, y, dates, test_size=0.2, val_size=0.2, report=rep)
    assert dates.loc[Xtr.index].max() < dates.loc[Xv.index].min() and dates.loc[Xv.index].max() < dates.loc[Xte.index].min()
    assert rep["strategy"] == "temporal" and rep["boundaries"]["test"][1] == "2020-02-19"
    with pytest.raises(ValueError):
        train_new.temporal_split(X, y, dates.where(dates.index != 3), report={})
    with pytest.raises(ValueError):
        train_new.make_split(X, y, strategy="random_guess")
    with pytest.raises(ValueError):
        train_new.make_split(X, y, strategy="temporal")                   # no dates
    one_class = {}
    train_new.temporal_split(X, pd.Series([0] * 40 + [1] * 10, index=np.arange(50)), dates, 0.2, 0.2, report=one_class)
    assert one_class["degraded"] is True                                   # the test period has one class


def test_temporal_training_is_chronological_and_reproducible(client, temporal):
    c = contract(temporal["model_id"])
    assert c["split"]["strategy"] == "temporal" and c["split"]["date_col"] == "application_date"
    b = c["split"]["report"]["boundaries"]
    assert b["train"][1] <= b["validation"][0] <= b["validation"][1] <= b["test"][0]
    (Xtr, Xv, Xte, *_), _ = model_lineage.contract_split(DF, c)
    dates = pd.to_datetime(DF["application_date"])
    assert dates.loc[Xtr.index].max() <= dates.loc[Xte.index].min()
    assert model_lineage.index_fingerprint(Xte.index) == c["split"]["test_index_sha256"]
    rep = env.replicate(client, CSV, registered_model_id=temporal["model_id"])
    status = env.lineage_status(rep)
    assert status["L9"] == "PASS" and status["L11"] == "PASS"


def test_temporal_is_never_inferred_and_bad_requests_are_rejected(client, trained):
    # A date column exists, but the default training split stays stratified random.
    assert contract(trained["model_id"])["split"]["strategy"] == "stratified_random"
    base = {"target_col": "default", "model_name": "bad"}
    for extra, fragment in (({"split_strategy": "temporal"}, "temporal_date_col"),
                            ({"split_strategy": "temporal", "temporal_date_col": "nope"}, "not found"),
                            ({"split_strategy": "shuffle"}, "split_strategy"),
                            ({"temporal_date_col": "application_date"}, "only used")):
        r = client.post("/models/train", data={**base, **extra}, files=files())
        assert r.status_code == 400 and fragment in r.json()["detail"], (extra, r.text)


# ── E8: /models/evaluate is out-of-sample only ─────────────────────────────

def test_evaluate_defaults_to_the_registered_test_partition(client, trained):
    c = contract(trained["model_id"])
    r = evaluate(client, trained["model_id"])
    assert r.status_code == 200, r.text
    scope = r.json()["evaluation_scope"]
    assert scope["partition"] == "test" and scope["in_sample"] is False and scope["rows"] == c["split"]["test_rows"]
    assert scope["row_index_sha256"] == c["split"]["test_index_sha256"]
    assert scope["training_run_id"] == c["training_run_id"] and scope["registered_model_id"] == trained["model_id"]
    assert scope["operating_threshold"] == c["training"]["threshold"] and scope["threshold_status"] == "PASS"
    # Same metrics as recorded at training (same rows, same threshold).
    assert r.json()["evaluation_metrics"]["roc_auc"] == c["development_metrics"]["roc_auc"]
    v = evaluate(client, trained["model_id"], evaluation_partition="validation").json()["evaluation_scope"]
    assert v["partition"] == "validation" and v["rows"] == c["split"]["val_rows"]


def test_evaluate_refuses_in_sample_and_undocumented_requests(client, trained):
    mid = trained["model_id"]
    r = evaluate(client, mid, evaluation_partition="independent", independent_dataset_reason="trust me")
    assert r.status_code == 409 and "in_sample" in r.json()["detail"]
    r = evaluate(client, mid, csv=OTHER_CSV, evaluation_partition="independent")
    assert r.status_code == 400 and "independent_dataset_reason" in r.json()["detail"]
    r = evaluate(client, mid, csv=OTHER_CSV)
    assert r.status_code == 409 and "dataset_mismatch" in r.json()["detail"]
    r = evaluate(client, mid, evaluation_partition="all_rows")
    assert r.status_code == 400
    ok = evaluate(client, mid, csv=OTHER_CSV, evaluation_partition="independent", independent_dataset_reason="Later vintage")
    assert ok.status_code == 200
    s = ok.json()["evaluation_scope"]
    assert s["partition"] == "independent" and s["rows"] == len(DF) and s["independent_dataset_reason"] == "Later vintage"
    assert s["dataset_sha256"] != s["training_dataset_sha256"] and s["limitations"]


def test_evaluate_manual_threshold_is_labelled(client, trained):
    s = evaluate(client, trained["model_id"], threshold="0.33").json()["evaluation_scope"]
    assert s["threshold_status"] == "MANUAL_OVERRIDE" and s["operating_threshold"] == 0.33


def test_evaluation_log_records_identity(client, trained):
    evaluate(client, trained["model_id"])
    row = [r for r in persistence.read_log(persistence.DEV_PIPELINE_LOG) if r["stage"] == "evaluation"][-1]
    s = row["summary"]
    assert s["registered_model_id"] == trained["model_id"] and s["evaluation_partition"] == "test"
    assert s["training_run_id"] == contract(trained["model_id"])["training_run_id"] and s["dataset_sha256"]


# ── E9: training artifacts are immutable; registration is its own event ───

def test_training_artifact_is_never_rewritten(client, trained):
    run = persistence.get_run(persistence.DEV_PIPELINE_LOG, trained["training_run_id"])
    path = persistence.BACKEND_DIR / [r for r in persistence.read_log(persistence.DEV_PIPELINE_LOG)
                                      if r["run_id"] == trained["training_run_id"]][0]["artifact_path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == run["summary"]["artifact_sha256"]
    assert "model_id" not in run["full_payload"]                      # registration did not rewrite it
    reg = [r for r in persistence.read_log(persistence.DEV_PIPELINE_LOG) if r["stage"] == "registration"
           and r["summary"].get("training_run_id") == trained["training_run_id"]]
    assert len(reg) == 1
    s = reg[0]["summary"]
    assert s["registered_model_id"] == trained["model_id"] and s["training_artifact_sha256"] == run["summary"]["artifact_sha256"]
    assert s["bundle_sha256"] == contract(trained["model_id"])["artifact"]["sha256"]
    assert trained["registration_run_id"] == reg[0]["run_id"]


def test_retraining_the_same_name_keeps_earlier_artifacts_intact(client):
    first = env.train(client, CSV, "Batch3E Retrain")
    p1 = persistence.BACKEND_DIR / [r for r in persistence.read_log(persistence.DEV_PIPELINE_LOG)
                                    if r["run_id"] == first["training_run_id"]][0]["artifact_path"]
    before = hashlib.sha256(p1.read_bytes()).hexdigest()
    second = env.train(client, CSV, "Batch3E Retrain")
    assert second["model_id"] == first["model_id"] and second["training_run_id"] != first["training_run_id"]
    assert hashlib.sha256(p1.read_bytes()).hexdigest() == before


def test_save_artifact_refuses_to_overwrite(client):
    rel = persistence.save_artifact(persistence.DEV_PIPELINE_LOG, "training", "immutable-test", {"a": 1})
    with pytest.raises(persistence.ImmutableArtifactError):
        persistence.save_artifact(persistence.DEV_PIPELINE_LOG, "training", "immutable-test", {"a": 2})
    assert json.loads((persistence.BACKEND_DIR / rel).read_text())["a"] == 1
    with pytest.raises(persistence.ImmutableArtifactError):
        persistence._update_latest_training_artifact_with_model_id("x", "MOD-1")
    assert "registration" in persistence.LOG_STAGES[persistence.DEV_PIPELINE_LOG]


# ── E11: file identity vs parsed-table identity; provenance lookup ─────────

def test_file_and_table_identities_are_distinct(client):
    a = client.post("/data/upload", files=files(CSV)).json()["dataset_identity"]
    b = client.post("/data/upload", files=files(SAME_TABLE_OTHER_FILE)).json()["dataset_identity"]
    assert a["dataset_sha256"] == b["dataset_sha256"]                  # same parsed table
    assert a["dataset_file_sha256"] != b["dataset_file_sha256"]        # different original files
    assert a["dataset_file_sha256"] == hashlib.sha256(CSV).hexdigest()
    c = client.post("/data/upload", files=files(OTHER_CSV)).json()["dataset_identity"]
    assert c["dataset_sha256"] != a["dataset_sha256"]                  # mutation detected


def test_dataset_lineage_endpoint(client, trained):
    sha = contract(trained["model_id"])["dataset"]["sha256"]
    body = client.get(f"/lineage/dataset/{sha}").json()
    stages = {r["stage"] for r in body["runs"]}
    assert {"training", "registration"} <= stages
    assert any(m["model_id"] == trained["model_id"] for m in body["models"])
    file_sha = hashlib.sha256(CSV).hexdigest()
    assert contract(trained["model_id"])["dataset"]["file_sha256"] == file_sha
    assert any("dataset_file_sha256" in r["matched_as"] for r in client.get(f"/lineage/dataset/{file_sha}").json()["runs"])
    assert client.get("/lineage/dataset/not-a-hash").status_code == 400


# ── E7: explanation scoped to the exact registered model and rows ─────────

def test_explain_uses_the_registered_test_rows_and_records_identity(client, trained):
    data = {"target_col": "default", "compute_shap": "false", "registered_model_id": trained["model_id"]}
    body = client.post("/models/explain", data=data, files=files()).json()
    s = body["explain_scope"]
    c = contract(trained["model_id"])
    assert s["rows"] == "registered_test_partition" and s["row_index_sha256"] == c["split"]["test_index_sha256"]
    assert s["training_run_id"] == c["training_run_id"]
    other = client.post("/models/explain", data=data, files=files(OTHER_CSV)).json()["explain_scope"]
    assert other["rows"] == "supplied_dataset"
    row = [r for r in persistence.read_log(persistence.DEV_PIPELINE_LOG) if r["stage"] == "explainability"][-1]
    assert row["summary"]["registered_model_id"] == trained["model_id"] and row["summary"]["dataset_sha256"]


# ── E12: previews use the training split configuration ─────────────────────

def test_previews_use_the_requested_split_and_are_reproducible(client):
    def fe(**extra):
        r = client.post("/data/feature-engineering", data={"target_col": "default", **extra}, files=files())
        assert r.status_code == 200, r.text
        return r.json()["split_config"]
    default = fe()
    assert (default["test_size"], default["val_size"], default["random_seed"]) == (0.15, 0.15, 42)
    seven = fe(random_seed="7", test_size="0.2", val_size="0.1")
    assert seven["random_seed"] == 7 and seven["test_rows"] == 300 and seven["train_index_sha256"] != default["train_index_sha256"]
    assert fe(random_seed="7", test_size="0.2", val_size="0.1")["train_index_sha256"] == seven["train_index_sha256"]
    # Same split as training with the same settings.
    X, y, _ = main.finalize_xy(DF, main.detect_column_types(DF), "default")
    Xtr = train_new.split_data(X, y, test_size=0.2, val_size=0.1, random_state=7)[0]
    assert model_lineage.index_fingerprint(Xtr.index) == seven["train_index_sha256"]
    log = client.post("/data/feature-decision-log", data={"target_col": "default", "random_seed": "7",
                                                          "test_size": "0.2", "val_size": "0.1"}, files=files()).json()
    assert log["split_config"]["train_index_sha256"] == seven["train_index_sha256"]
    rec = client.post("/models/recommend", data={"target_col": "default", "random_seed": "7", "test_size": "0.2",
                                                 "val_size": "0.1"}, files=files()).json()
    assert rec["split_config"]["random_seed"] == 7
    assert client.post("/data/feature-engineering", data={"target_col": "default", "test_size": "0.9", "val_size": "0.2"},
                       files=files()).status_code == 400


# ── E3: model comparison and benchmark challenger ─────────────────────────

def test_compare_selects_each_threshold_on_validation(client):
    r = client.post("/models/compare", data={"target_col": "default", "model_names": json.dumps(["Logistic Regression"])},
                    files=files()).json()
    row = r["comparison"][0]
    assert row["threshold_provenance"]["source_partition"] == "validation" and row["threshold_used"] == row["threshold_provenance"]["value"]
    assert r["split_config"]["random_seed"] == 42


# ── E10: legacy readiness (read-only) ──────────────────────────────────────

def test_legacy_readiness_is_read_only_and_never_fabricates(client, trained):
    store = persistence.load_model_inventory()
    store["development"].append({"model_id": "MOD-LEGACY-9", "model_name": "Old PD", "algorithm": "LR",
                                 "status": "In Development", "training_config": {"test_size": 0.2}})
    persistence.save_model_inventory(store)
    inv = persistence.get_model_inventory_path()
    before = (hashlib.sha256(inv.read_bytes()).hexdigest(), inv.stat().st_mtime_ns)
    body = client.get("/model-inventory/legacy-readiness").json()
    assert (hashlib.sha256(inv.read_bytes()).hexdigest(), inv.stat().st_mtime_ns) == before
    by_id = {m["model_id"]: m for m in body["models"]}
    legacy = by_id["MOD-LEGACY-9"]
    assert legacy["category"] == "retrain_required" and legacy["safe_migration"] is None
    assert legacy["recorded_on_inventory_entry"]["training_config"] is True        # noted, not converted
    assert "lineage_contract" not in env.dev_entry("MOD-LEGACY-9")
    assert by_id[trained["model_id"]]["category"] == "ready"
    assert body["total"] == len(body["models"]) and sum(body["counts"].values()) == body["total"]
