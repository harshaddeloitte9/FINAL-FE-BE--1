"""Batch 1A regression tests: validation records separated by execution
identity, and run history written in the real order (Started, then
Completed or Failed). Phase 4 isolated environment.

The endpoint tests replace the replication engine with stubs (success,
unsuccessful result, exception). They test the lifecycle bookkeeping only;
no model is trained or replicated.
"""
import copy
import io

import pandas as pd
import pytest

import _aegis_test_env as env
import main
import model_lineage
import persistence

REG = persistence.EXECUTION_MODE_REGISTERED
UNREG = persistence.EXECUTION_MODE_UNREGISTERED
RUN_EVENTS = ("Validation Run Started", "Validation Run Completed", "Validation Run Failed")


def _store(development=(), validation=(), history=()):
    return {"development": list(development), "validation": list(validation), "models": [],
            "data_sources": [], "history": list(history)}


def _dev(model_id, name):
    return {"model_id": model_id, "model_name": name, "algorithm": "XGBoost", "status": "In Development",
            "documentation_path": "docs/existing.pdf",
            "lineage_contract": {"training_run_id": f"TR-{model_id}", "target_col": "default", "estimator_name": "XGBoost"}}


def _register(store, name, model_id=None, run_id="run-x"):
    return persistence.register_validation_run(
        store=store, business_model_name=name, estimator_name="XGBoost",
        intake_payload={"model_id": model_id, "model_owner": "Validator"},
        dataset_payload={"file_name": "validation.csv"}, target_col="default", user="Validator", run_id=run_id,
    )


def _record(store, record_id):
    return next(r for r in store["validation"] if r["model_id"] == record_id)


def _run_events(store, record_id=None):
    return [h for h in store["history"] if h.get("event") in RUN_EVENTS
            and (record_id is None or h.get("model_id") == record_id)]


def test_execution_mode_values_match_model_lineage():
    assert REG == model_lineage.REPLICATION_MODE_REGISTERED
    assert UNREG == model_lineage.REPLICATION_MODE_UNREGISTERED


# 1-3 ── Separate records per execution identity ────────────────────────────

def test_registered_then_same_name_refit_creates_separate_records():
    store = _store(development=[_dev("MOD-001", "PD_X")])
    reg = _register(store, "PD_X", model_id="MOD-001", run_id="run-reg")
    refit = _register(store, "PD_X", model_id=None, run_id="run-refit")
    assert reg["model_id"] != refit["model_id"]
    assert _record(store, reg["model_id"])["related_model_id"] == "MOD-001"
    assert _record(store, reg["model_id"])["execution_mode"] == REG
    assert _record(store, refit["model_id"])["related_model_id"] is None
    assert _record(store, refit["model_id"])["execution_mode"] == UNREG
    assert (reg["execution_mode"], refit["execution_mode"]) == (REG, UNREG)


def test_refit_then_registered_run_creates_separate_records():
    store = _store(development=[_dev("MOD-001", "PD_X")])
    refit = _register(store, "PD_X", model_id=None)
    reg = _register(store, "PD_X", model_id="MOD-001")
    assert refit["model_id"] != reg["model_id"]
    assert _record(store, refit["model_id"])["related_model_id"] is None
    assert _record(store, reg["model_id"])["related_model_id"] == "MOD-001"


def test_same_identity_reuses_its_own_record():
    store = _store(development=[_dev("MOD-001", "PD_X")])
    assert _register(store, "PD_X", "MOD-001")["model_id"] == _register(store, "PD_X", "MOD-001")["model_id"]
    assert _register(store, "PD_X")["model_id"] == _register(store, "PD_X")["model_id"]
    assert len(store["validation"]) == 2


def test_registered_record_is_found_by_id_not_name():
    store = _store(development=[_dev("MOD-001", "PD_X"), _dev("MOD-002", "PD_Y")])
    first = _register(store, "PD_X", "MOD-001")
    other = _register(store, "PD_X", "MOD-002")      # same engagement name, different registered model
    assert first["model_id"] != other["model_id"]
    assert _record(store, other["model_id"])["related_model_id"] == "MOD-002"


# 4 ── Refit history identifies the run and has no registered model ─────────

def test_refit_history_records_mode_run_id_and_no_registered_model():
    store = _store(development=[_dev("MOD-001", "PD_X")])
    refit = _register(store, "PD_X", model_id=None, run_id="run-refit-1")
    (started,) = _run_events(store, refit["model_id"])
    assert started["event"] == "Validation Run Started"
    assert "registered_model_id" in started and started["registered_model_id"] is None
    assert started["execution_mode"] == UNREG and started["run_id"] == "run-refit-1"
    assert started["validation_run_id"] == refit["validation_run_id"]


def test_registration_alone_never_writes_completed():
    store = _store(development=[_dev("MOD-001", "PD_X")])
    _register(store, "PD_X", "MOD-001")
    _register(store, "PD_X")
    assert {h["event"] for h in _run_events(store)} == {"Validation Run Started"}


# 7-8 ── Existing records and history are not rewritten ────────────────────

def test_existing_records_and_history_are_unchanged():
    legacy_linked = {"model_id": "VAL-001", "model_name": "PD_Linked", "related_model_id": "MOD-001",
                     "status": "Under Validation", "algorithm": "LightGBM"}
    legacy_unlinked = {"model_id": "VAL-002", "model_name": "PD_Other", "related_model_id": None,
                       "status": "Under Validation", "algorithm": "LightGBM"}
    old_history = [{"model_id": "VAL-001", "event": "Validation Run Completed", "description": "legacy",
                    "timestamp": "2026-01-01T00:00:00", "user": "x", "validation_run_id": "VAL-001"}]
    store = _store(development=[_dev("MOD-001", "PD_Linked"), _dev("MOD-002", "PD_Other")],
                   validation=[copy.deepcopy(legacy_linked), copy.deepcopy(legacy_unlinked)],
                   history=copy.deepcopy(old_history))

    refit = _register(store, "PD_Linked", model_id=None)          # must not reuse VAL-001 (linked)
    reg = _register(store, "PD_Other", model_id="MOD-002")        # must not reuse VAL-002 (unlinked refit record)

    assert refit["model_id"] not in ("VAL-001", "VAL-002") and reg["model_id"] not in ("VAL-001", "VAL-002")
    assert _record(store, "VAL-001") == legacy_linked
    assert _record(store, "VAL-002") == legacy_unlinked
    assert store["history"][:len(old_history)] == old_history


def test_outcome_appends_without_changing_records():
    store = _store(development=[_dev("MOD-001", "PD_X")])
    reg = _register(store, "PD_X", "MOD-001", run_id="run-1")
    record_before = copy.deepcopy(_record(store, reg["model_id"]))
    history_before = copy.deepcopy(store["history"])
    persistence.record_validation_run_outcome(store, reg["model_id"], reg["validation_run_id"], True,
                                              execution_mode=REG, run_id="run-1", registered_model_id="MOD-001")
    assert _record(store, reg["model_id"]) == record_before
    assert store["history"][:-1] == history_before
    done = store["history"][-1]
    assert (done["event"], done["outcome"], done["run_id"], done["registered_model_id"]) == \
           ("Validation Run Completed", "COMPLETED", "run-1", "MOD-001")


# 5-6 ── Lifecycle through the replication endpoint (engine stubbed) ───────

CSV = pd.DataFrame({"f0": range(40), "f1": [i % 7 for i in range(40)], "default": [i % 2 for i in range(40)]}).to_csv(index=False).encode()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with env.isolated_backend(tmp_path) as c:
        persistence.save_model_inventory(_store(development=[_dev("MOD-001", "PD_Registered")]))
        monkeypatch.setattr(main, "_build_performance_report", lambda *a, **k: {"metrics": {}})
        monkeypatch.setattr(main, "evaluate_replication_checks", lambda *a, **k: [])
        yield c


def _post(client, **data):
    files = {"file": ("validation.csv", io.BytesIO(CSV), "text/csv")}
    return client.post("/validation/replication", data={"target_col": "default", **data}, files=files)


def _history_for(record_id):
    return _run_events(persistence.load_model_inventory(), record_id)


def test_successful_refit_records_started_then_completed(client, monkeypatch):
    monkeypatch.setattr(main, "run_replication", lambda **k: {"success": True, "metrics": {}})
    body = _post(client, model_name="PD_Refit", algorithm="Logistic Regression").json()
    ev = body["evidence"]
    events = _history_for(ev["validation_model_id"])
    assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Completed"]
    for e in events:
        assert e["run_id"] == ev["run_id"] and e["validation_run_id"] == ev["validation_run_id"]
        assert e["execution_mode"] == UNREG and e["registered_model_id"] is None
    logged = persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, ev["run_id"])
    assert logged["summary"]["validation_run_id"] == ev["validation_run_id"]


def test_successful_registered_run_records_started_then_completed(client, monkeypatch):
    monkeypatch.setattr(main.model_lineage, "run_registered_replication", lambda *a, **k: {
        "success": True, "metrics": {}, "original_metrics": {},
        "methodology": {"mode": REG, "registered_model_id": "MOD-001", "training_run_id": "TR-MOD-001"}})
    ev = _post(client, registered_model_id="MOD-001").json()["evidence"]
    events = _history_for(ev["validation_model_id"])
    assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Completed"]
    assert all(e["execution_mode"] == REG and e["registered_model_id"] == "MOD-001" for e in events)
    record = _record(persistence.load_model_inventory(), ev["validation_model_id"])
    assert record["related_model_id"] == "MOD-001"


def test_unsuccessful_result_records_failed_not_completed(client, monkeypatch):
    monkeypatch.setattr(main, "run_replication", lambda **k: {"success": False, "error": "stub failure", "metrics": {}})
    ev = _post(client, model_name="PD_Refit", algorithm="Logistic Regression").json()["evidence"]
    events = _history_for(ev["validation_model_id"])
    assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Failed"]
    assert "stub failure" in events[-1]["description"] and events[-1]["outcome"] == "FAILED"


def _assert_one_outcome_per_run(store):
    # Every new-format run (events carry run_id) has exactly one Started and
    # at most one outcome, never both outcomes. Legacy events are not checked.
    by_run = {}
    for e in _run_events(store):
        if "run_id" not in e:
            continue
        by_run.setdefault(e["validation_run_id"], []).append(e["event"])
    for run, events in by_run.items():
        assert events.count("Validation Run Started") == 1, (run, events)
        assert events.count("Validation Run Completed") + events.count("Validation Run Failed") <= 1, (run, events)


def _refit_success(monkeypatch):
    monkeypatch.setattr(main, "run_replication", lambda **k: {"success": True, "metrics": {}})


def test_report_failure_after_successful_replication_records_failed(client, monkeypatch):
    _refit_success(monkeypatch)

    def report_boom(*a, **k):
        raise ValueError("report broke")
    monkeypatch.setattr(main, "_build_performance_report", report_boom)
    with pytest.raises(ValueError, match="report broke"):
        _post(client, model_name="PD_Report", algorithm="Logistic Regression")
    store = persistence.load_model_inventory()
    record = next(r for r in store["validation"] if r["model_name"] == "PD_Report")
    assert [e["event"] for e in _run_events(store, record["model_id"])] == ["Validation Run Started", "Validation Run Failed"]
    _assert_one_outcome_per_run(store)


def test_checks_failure_records_failed(client, monkeypatch):
    _refit_success(monkeypatch)

    def checks_boom(*a, **k):
        raise KeyError("missing metric")
    monkeypatch.setattr(main, "evaluate_replication_checks", checks_boom)
    r = _post(client, model_name="PD_Checks", algorithm="Logistic Regression")
    assert r.status_code == 200                                      # response contract unchanged
    ev = r.json()["evidence"]
    events = _history_for(ev["validation_model_id"])
    assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Failed"]
    assert "checks could not be evaluated" in events[-1]["description"]


def test_log_write_failure_is_not_completed(client, monkeypatch):
    _refit_success(monkeypatch)

    def log_boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(persistence, "log_event", log_boom)
    ev = _post(client, model_name="PD_Log", algorithm="Logistic Regression").json()["evidence"]
    assert ev["persisted"] is False and ev["run_id"] is None
    events = _history_for(ev["validation_model_id"])
    assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Failed"]
    assert "could not be saved" in events[-1]["description"]


def test_outcome_write_failure_does_not_mask_original_exception(client, monkeypatch):
    def boom(**k):
        raise RuntimeError("engine crashed")

    def outcome_boom(*a, **k):
        raise ValueError("inventory unwritable")
    monkeypatch.setattr(main, "run_replication", boom)
    monkeypatch.setattr(persistence, "record_validation_run_outcome", outcome_boom)
    with pytest.raises(RuntimeError, match="engine crashed"):
        _post(client, model_name="PD_Mask", algorithm="Logistic Regression")


def test_outcome_write_failure_does_not_fail_a_successful_request(client, monkeypatch):
    _refit_success(monkeypatch)
    monkeypatch.setattr(persistence, "record_validation_run_outcome",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("inventory unwritable")))
    r = _post(client, model_name="PD_Ok", algorithm="Logistic Regression")
    assert r.status_code == 200 and r.json()["evidence"]["persisted"] is True


def test_one_identity_per_execution_and_retry_gets_a_new_one(client, monkeypatch):
    _refit_success(monkeypatch)
    first = _post(client, model_name="PD_Retry", algorithm="Logistic Regression").json()["evidence"]
    first_run = persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, first["run_id"])   # includes full_payload
    assert first_run["full_payload"]["evidence"]["run_id"] == first["run_id"]

    second = _post(client, model_name="PD_Retry", algorithm="Logistic Regression").json()["evidence"]
    assert second["run_id"] != first["run_id"]
    assert second["validation_run_id"] != first["validation_run_id"]
    assert second["validation_model_id"] == first["validation_model_id"]       # same refit engagement record

    store = persistence.load_model_inventory()
    for ev in (first, second):
        events = [e for e in _run_events(store) if e["validation_run_id"] == ev["validation_run_id"]]
        assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Completed"]
        assert {e["run_id"] for e in events} == {ev["run_id"]}
        assert persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, ev["run_id"])["summary"]["validation_run_id"] == ev["validation_run_id"]
    _assert_one_outcome_per_run(store)
    # The first run's log row and saved artifact are untouched by the retry.
    assert persistence.get_run(persistence.VALIDATION_PIPELINE_LOG, first["run_id"]) == first_run


def _registered_success(monkeypatch):
    monkeypatch.setattr(main.model_lineage, "run_registered_replication", lambda *a, **k: {
        "success": True, "metrics": {}, "original_metrics": {},
        "methodology": {"mode": REG, "registered_model_id": "MOD-001", "training_run_id": "TR-MOD-001"}})


@pytest.mark.parametrize("order", ["registered_first", "refit_first"])
def test_endpoint_runs_in_both_orders_use_separate_records(client, monkeypatch, order):
    legacy = {"model_id": "VAL-050", "model_name": "PD_Registered", "related_model_id": "MOD-777",
              "status": "Under Validation", "algorithm": "LightGBM"}
    store = persistence.load_model_inventory()
    store["validation"].append(copy.deepcopy(legacy))
    store["history"].append({"model_id": "VAL-050", "event": "Validation Run Completed", "description": "legacy",
                             "timestamp": "2026-01-01T00:00:00", "user": "x", "validation_run_id": "VAL-050"})
    persistence.save_model_inventory(store)
    history_before = copy.deepcopy(persistence.load_model_inventory()["history"])

    _registered_success(monkeypatch)
    _refit_success(monkeypatch)
    calls = [dict(registered_model_id="MOD-001"), dict(model_name="PD_Registered", algorithm="Logistic Regression")]
    if order == "refit_first":
        calls.reverse()
    evs = [_post(client, **c).json()["evidence"] for c in calls]
    reg, refit = (evs[0], evs[1]) if order == "registered_first" else (evs[1], evs[0])

    store = persistence.load_model_inventory()
    reg_rec, refit_rec = _record(store, reg["validation_model_id"]), _record(store, refit["validation_model_id"])
    assert reg_rec["model_id"] != refit_rec["model_id"]
    assert (reg_rec["related_model_id"], reg_rec["execution_mode"]) == ("MOD-001", REG)
    assert (refit_rec["related_model_id"], refit_rec["execution_mode"]) == (None, UNREG)
    assert _record(store, "VAL-050") == legacy                                   # historical record untouched
    assert store["history"][:len(history_before)] == history_before             # history only appended
    _assert_one_outcome_per_run(store)


# ── Identifier format ─────────────────────────────────────────────────────

def test_new_runs_use_vrun_prefix_and_old_ids_are_kept():
    old_history = [{"model_id": "VAL-001", "event": e, "description": "legacy", "timestamp": "2026-01-01T00:00:00",
                    "user": "x", "validation_run_id": rid}
                   for rid in ("VAL-001", "VAL-002", "VAL-003") for e in ("Validation Run Started", "Validation Run Completed")]
    store = _store(development=[_dev("MOD-001", "PD_X")], history=copy.deepcopy(old_history))
    first = _register(store, "PD_X", "MOD-001")
    second = _register(store, "PD_X")
    assert (first["validation_run_id"], second["validation_run_id"]) == ("VRUN-001", "VRUN-002")
    assert first["model_id"].startswith("VAL-") and second["model_id"].startswith("VAL-")   # record ids unchanged
    assert store["history"][:len(old_history)] == old_history


def test_exception_during_execution_records_failed_not_completed(client, monkeypatch):
    def boom(**k):
        raise RuntimeError("engine crashed")
    monkeypatch.setattr(main, "run_replication", boom)
    with pytest.raises(RuntimeError, match="engine crashed"):
        _post(client, model_name="PD_Crash", algorithm="Logistic Regression")
    store = persistence.load_model_inventory()
    record = next(r for r in store["validation"] if r["model_name"] == "PD_Crash")
    events = _run_events(store, record["model_id"])
    assert [e["event"] for e in events] == ["Validation Run Started", "Validation Run Failed"]
    assert "RuntimeError: engine crashed" in events[-1]["description"]
    assert not any(e["event"] == "Validation Run Completed" for e in _run_events(store))
