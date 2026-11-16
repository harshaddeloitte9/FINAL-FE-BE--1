"""Audit findings D1, D2, D3, D5 (Phase 1-3 audit).

D1  replication runs record the original-file fingerprint; history can be
    scoped by registered model AND dataset, so a run on another dataset is
    never returned as the current result.
D2  reference source labels supplied by the browser are recorded as
    browser-reported; only values the server extracted from the MDD uploaded
    with the run are server-verified.
D3  an uploaded MDD value that replaces a different reviewer value is
    listed (previous / new value) and warned about, never silent.
D5  a registered replication that does not record its training run is
    INCONCLUSIVE evidence.
Isolated temporary app_data; synthetic data; real training and replication.
"""
import hashlib
import io
import json

import pytest

import _aegis_test_env as env
import main
import persistence

CSV = env.to_csv(env.dataset_coefs(1500, [1.0, 0.5, 0.2], seed=61))
OTHER_CSV = env.to_csv(env.dataset_coefs(1500, [1.0, 0.5, 0.2], seed=62))
MDD = b"Model Development Document. The model achieved ROC AUC: 0.8100 on the hold-out sample."


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("d_findings")) as c:
        yield c


@pytest.fixture(scope="module")
def model(client):
    return env.train(client, CSV, "D Findings Model")["model_id"]


@pytest.fixture(scope="module")
def runs(client, model):
    """One replication on the training dataset (with reviewer reference values
    and an uploaded MDD) and one on a different dataset."""
    data = {"target_col": "default", "registered_model_id": model,
            "reported_json": json.dumps({"roc_auc": 0.70, "gini": 0.42}),
            "reported_sources_json": json.dumps({"roc_auc": "manual_entry", "gini": "intake_mdd"})}
    r = client.post("/validation/replication", data=data,
                    files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv"), "mdd_file": ("mdd.txt", io.BytesIO(MDD), "text/plain")})
    assert r.status_code == 200, r.text
    other = env.replicate(client, OTHER_CSV, model, filename="other.csv")
    return {"training": r.json(), "other": other}


def latest(client, **params):
    r = client.get("/history/latest", params={"log_file": env.LOG, "stage": "replication", **params})
    assert r.status_code == 200, r.text
    return r.json()["latest"]


# ── D1 ─────────────────────────────────────────────────────────────────────

def test_replication_records_the_original_file_fingerprint(client, runs):
    for key, csv in (("training", CSV), ("other", OTHER_CSV)):
        ev = runs[key]["evidence"]
        assert ev["dataset_file_sha256"] == hashlib.sha256(csv).hexdigest()
        row = next(r for r in persistence.read_log(env.LOG) if r["run_id"] == ev["run_id"])
        assert row["summary"]["dataset_file_sha256"] == ev["dataset_file_sha256"]


def test_history_scoped_by_model_and_dataset_never_returns_another_datasets_run(client, model, runs):
    train_sha, other_sha = hashlib.sha256(CSV).hexdigest(), hashlib.sha256(OTHER_CSV).hexdigest()
    # The run on the other dataset is the newest for this model...
    assert latest(client, registered_model_id=model)["run_id"] == runs["other"]["evidence"]["run_id"]
    # ...but scoped to the training dataset only the training-dataset run qualifies.
    assert latest(client, registered_model_id=model, dataset_file_sha256=train_sha)["run_id"] == runs["training"]["evidence"]["run_id"]
    assert latest(client, registered_model_id=model, dataset_file_sha256=other_sha)["run_id"] == runs["other"]["evidence"]["run_id"]
    assert latest(client, registered_model_id=model, dataset_file_sha256="f" * 64) is None


def test_runs_without_a_file_fingerprint_are_never_restored_for_a_dataset(client, model):
    env.append_legacy_row(env.LOG, "replication",
                          {"registered_model_id": model, "record_version": persistence.RECORD_FORMAT_VERSION},
                          {"report": {}})
    sha = hashlib.sha256(CSV).hexdigest()
    found = latest(client, registered_model_id=model, dataset_file_sha256=sha)
    assert found is None or found["summary"].get("dataset_file_sha256") == sha


# ── D2 ─────────────────────────────────────────────────────────────────────

def test_reference_verification_distinguishes_server_from_browser_sources():
    ref = main.build_reference_metrics(
        json.dumps({"roc_auc": 0.7, "gini": 0.4, "ks": 0.3}),
        json.dumps({"roc_auc": "manual_entry", "gini": "intake_mdd", "ks": "computed_by_model"}),
        {"recall": 0.6},
    )
    assert ref["verification"] == {"roc_auc": "browser_reported", "gini": "browser_reported",
                                   "ks": "browser_reported", "recall": "server_extracted"}
    # A browser claim of "MDD parsed at Intake" is kept as a label but not verified.
    assert ref["sources"]["gini"] == "intake_mdd" and "not verified" in ref["verification_labels"]["gini"]
    assert ref["sources"]["ks"] == "client_supplied"                       # unknown label not trusted
    assert "extracted by the server" in ref["verification_labels"]["recall"]
    prov = main.build_metric_provenance(ref)
    assert prov["reference_source_verification"] == {"server_verified": ["recall"], "browser_reported": ["gini", "ks", "roc_auc"]}


def test_replication_response_and_saved_record_carry_verification(client, runs):
    ref = runs["training"]["report"]["reference_metrics"]
    assert ref["verification"]["roc_auc"] == "server_extracted"             # replaced by the uploaded MDD
    assert ref["verification"]["gini"] == "browser_reported"                # client label "intake_mdd"
    assert runs["training"]["report"]["metric_provenance"]["reference_source_verification"]["browser_reported"] == ["gini"]
    run = persistence.get_run(env.LOG, runs["training"]["evidence"]["run_id"])
    saved = run["full_payload"]["report"]["reference_metrics"]
    assert saved["verification"] == ref["verification"] and saved["replacements"] == ref["replacements"]


# ── D3 ─────────────────────────────────────────────────────────────────────

def test_mdd_replacing_a_different_reviewer_value_is_listed_and_warned():
    ref = main.build_reference_metrics(json.dumps({"roc_auc": 0.70, "accuracy": 0.8}),
                                       json.dumps({"roc_auc": "manual_entry"}), {"roc_auc": 0.75})
    assert ref["values"]["roc_auc"] == 0.75
    assert ref["replacements"] == [{"metric": "roc_auc", "previous_value": 0.70, "previous_source": "manual_entry",
                                    "previous_source_label": "Entered manually by reviewer",
                                    "new_value": 0.75, "new_source": "mdd_upload"}]
    assert any("roc_auc 0.7 (Entered manually by reviewer) → 0.75" in w for w in ref["warnings"])


def test_identical_or_new_mdd_values_are_not_reported_as_replacements():
    same = main.build_reference_metrics(json.dumps({"roc_auc": 0.75}), None, {"roc_auc": 0.75})
    only_mdd = main.build_reference_metrics(None, None, {"roc_auc": 0.75})
    assert same["replacements"] == [] and same["warnings"] == []
    assert only_mdd["replacements"] == [] and only_mdd["warnings"] == []


def test_replication_run_reports_the_replacement(client, runs):
    ref = runs["training"]["report"]["reference_metrics"]
    assert [(r["metric"], r["previous_value"], r["new_value"]) for r in ref["replacements"]] == [("roc_auc", 0.70, 0.81)]
    assert any("replaced reviewer-supplied reference values" in w for w in ref["warnings"])


# ── D5 ─────────────────────────────────────────────────────────────────────

def _set_methodology(run_id, mutate):
    row = next(r for r in persistence.read_log(env.LOG) if r["run_id"] == run_id)
    path = persistence.BACKEND_DIR / row["artifact_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload["report"]["replication"]["result"]["methodology"])
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_registered_run_without_training_run_is_inconclusive(client, model, runs):
    run_id = runs["training"]["evidence"]["run_id"]
    claimed = {"registered_model_id": model, "dataset_sha256": runs["training"]["evidence"]["dataset_sha256"]}
    before = main.assess_replication_evidence(run_id, claimed)
    assert not any("did not record the training run" in r for r in before["reasons"])
    _set_methodology(run_id, lambda m: m.pop("training_run_id", None))
    after = main.assess_replication_evidence(run_id, claimed)
    assert after["status"] == "INCONCLUSIVE"
    assert any("did not record the training run it reproduced" in r for r in after["reasons"])
