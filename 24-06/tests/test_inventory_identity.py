"""Batch 1 (model identity audit B3 + B2) regression tests. Phase 4 isolated
environment: every inventory/app_data path points at a temporary folder.

B3: reading the inventory (GET /model-inventory, GET /model-inventory/export)
    never writes model_inventory.json.
B2: a validation record is linked to a development model (related_model_id)
    only through an explicit registered model ID that exists in the
    Development Inventory — never by matching names.
"""
import copy
import hashlib

import pytest

import _aegis_test_env as env
import main
import persistence

INVENTORY_KEYS = {"development", "validation", "models", "data_sources", "history"}


def _dev_entry(model_id, name, **extra):
    # "In Development" with no report PDF: exactly the case the old GET
    # handler "repaired" by generating a report and saving the inventory.
    return {"model_id": model_id, "model_name": name, "algorithm": "XGBoost", "status": "In Development",
            "model_owner": "Owner", "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00", **extra}


def _seed(store):
    persistence.save_model_inventory(store)
    return persistence.get_model_inventory_path()


def _fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


def _register_validation(store, name, model_id=None):
    return persistence.register_validation_run(
        store=store, business_model_name=name, estimator_name="XGBoost",
        intake_payload={"model_id": model_id, "model_owner": "Validator"},
        dataset_payload={"file_name": "validation.csv", "record_count": 100, "column_count": 5},
        target_col="default", user="Validator",
    )


@pytest.fixture()
def client(tmp_path):
    with env.isolated_backend(tmp_path) as c:
        yield c


# ── B3: read-only inventory GET ────────────────────────────────────────────

def test_inventory_get_does_not_modify_inventory_file(client):
    path = _seed({"development": [_dev_entry("MOD-001", "PD_Read_Only")], "validation": [], "models": [],
                  "data_sources": [], "history": []})
    before = _fingerprint(path)
    reports_before = sorted(p.name for p in persistence.APP_DATA_DIR.rglob("*.pdf"))

    for _ in range(3):
        r = client.get("/model-inventory")
        assert r.status_code == 200, r.text

    assert _fingerprint(path) == before, "GET /model-inventory wrote model_inventory.json"
    assert sorted(p.name for p in persistence.APP_DATA_DIR.rglob("*.pdf")) == reports_before
    assert r.json()["development"][0].get("documentation_path") is None   # entry not altered by a read


def test_inventory_export_does_not_modify_inventory_file(client):
    if main.Workbook is None:
        pytest.skip("openpyxl not installed")
    path = _seed({"development": [_dev_entry("MOD-001", "PD_Export")], "validation": [], "models": [],
                  "data_sources": [], "history": []})
    before = _fingerprint(path)
    r = client.get("/model-inventory/export")
    assert r.status_code == 200
    assert _fingerprint(path) == before


def test_write_path_still_generates_missing_reports(client):
    # The report generation moved off the read path still runs on writes, so
    # the read-only test above is not passing merely because nothing ever writes.
    path = _seed({"development": [_dev_entry("MOD-001", "PD_Write_Path")], "validation": [], "models": [],
                  "data_sources": [], "history": []})
    before = _fingerprint(path)
    store = persistence.ensure_model_inventory_seed()
    assert _fingerprint(path) != before
    assert str(store["development"][0]["documentation_path"]).endswith(".pdf")


def test_inventory_get_response_contract_is_unchanged(client):
    store = {"development": [_dev_entry("MOD-001", "PD_Contract", documentation_path="docs/existing.pdf")],
             "validation": [{"model_id": "VAL-001", "model_name": "PD_Contract", "related_model_id": "MOD-001",
                             "status": "Under Validation", "validation_status": "Under Validation"}],
             "models": [], "data_sources": [], "history": []}
    _seed(copy.deepcopy(store))
    body = client.get("/model-inventory").json()
    assert set(body) == INVENTORY_KEYS
    assert body == persistence.load_model_inventory()
    assert {m["model_id"] for m in body["models"]} == {"MOD-001", "VAL-001"}   # merged view as before
    assert body["development"][0]["documentation_path"] == "docs/existing.pdf"
    assert body["validation"][0]["related_model_id"] == "MOD-001"


# ── B2: validation-run model linking ───────────────────────────────────────

def test_refit_with_matching_name_is_not_linked():
    store = {"development": [_dev_entry("MOD-001", "PD_Same_Name")], "validation": [], "models": [],
             "data_sources": [], "history": []}
    result = _register_validation(store, "PD_Same_Name", model_id=None)
    entry = next(v for v in store["validation"] if v["model_id"] == result["model_id"])
    assert entry["related_model_id"] is None
    assert entry["model_name"] == "PD_Same_Name"                 # engagement record still created


def test_unknown_model_id_is_not_linked():
    store = {"development": [_dev_entry("MOD-001", "PD_Known")], "validation": [], "models": [],
             "data_sources": [], "history": []}
    result = _register_validation(store, "PD_Known", model_id="MOD-999")
    entry = next(v for v in store["validation"] if v["model_id"] == result["model_id"])
    assert entry["related_model_id"] is None                      # MOD- prefix alone is not verification


def test_verified_registered_id_is_linked():
    store = {"development": [_dev_entry("MOD-001", "PD_Other_Name"), _dev_entry("MOD-002", "PD_Registered")],
             "validation": [], "models": [], "data_sources": [], "history": []}
    result = _register_validation(store, "PD_Registered", model_id="MOD-002")
    entry = next(v for v in store["validation"] if v["model_id"] == result["model_id"])
    assert entry["related_model_id"] == "MOD-002"


def test_verified_id_wins_over_name():
    # Engagement named like MOD-001 but explicitly validating MOD-002.
    store = {"development": [_dev_entry("MOD-001", "PD_Shared"), _dev_entry("MOD-002", "PD_Retrained")],
             "validation": [], "models": [], "data_sources": [], "history": []}
    result = _register_validation(store, "PD_Shared", model_id="MOD-002")
    entry = next(v for v in store["validation"] if v["model_id"] == result["model_id"])
    assert entry["related_model_id"] == "MOD-002"


def test_existing_link_is_preserved_by_later_unregistered_run():
    store = {"development": [_dev_entry("MOD-001", "PD_History")],
             "validation": [{"model_id": "VAL-001", "model_name": "PD_History", "related_model_id": "MOD-001",
                             "status": "Under Validation"}],
             "models": [], "data_sources": [], "history": []}
    _register_validation(store, "PD_History", model_id=None)
    assert store["validation"][0]["related_model_id"] == "MOD-001"   # not cleared, not rewritten


def test_replication_endpoint_passes_only_a_verified_id():
    # Static check of the caller: the unregistered branch clears the ID before
    # register_validation_run, and the registered branch 404s on an unknown ID.
    import inspect
    src = inspect.getsource(main.validation_replication)
    assert 'registered_model_id = None' in src
    assert 'status_code=404' in src
    assert '"model_id": registered_model_id' in src
