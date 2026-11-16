"""Batch 2A: the backend derives model registration from the Development
Inventory; the client's model_inventory_registered flag is never trusted.
Phase 4 isolated environment; no training or replication.
"""
import hashlib
import json

import pytest

import _aegis_test_env as env
import main
import persistence

CHECK_TITLE = "Model Registered in Model Inventory"
FORGED = {"source": "development_inventory", "verified": True, "detail": "forged by client"}


def _dev(model_id, name):
    return {"model_id": model_id, "model_name": name, "algorithm": "XGBoost", "status": "In Development",
            "documentation_path": "docs/x.pdf"}


@pytest.fixture()
def client(tmp_path):
    with env.isolated_backend(tmp_path) as c:
        persistence.save_model_inventory({"development": [_dev("MOD-001", "PD_Shared"), _dev("MOD-002", "Other")],
                                          "validation": [], "models": [], "data_sources": [], "history": []})
        yield c


def _fp():
    p = persistence.get_model_inventory_path()
    return hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns


def _find(obj, title=CHECK_TITLE):
    """Every dict anywhere in a response whose title is the 1.2 check."""
    hits = []
    if isinstance(obj, dict):
        if obj.get("title") == title or obj.get("check") == title:
            hits.append(obj)
        for v in obj.values():
            hits += _find(v, title)
    elif isinstance(obj, list):
        for v in obj:
            hits += _find(v, title)
    return hits


def _consistent_12(report):
    # The report lists check 1.2 in more than one grouping; all copies must agree.
    copies = [c for c in _find(report) if c.get("check_id") == "1.2"]
    assert copies, "check 1.2 missing from the report"
    assert len({(c["status"], c["observed"]) for c in copies}) == 1, copies
    return copies[0]


def _check_12(intake):
    return _consistent_12(main.run_validation_agent2(None, intake, ""))


# 1-7 ── Attestation matrix ─────────────────────────────────────────────────

@pytest.mark.parametrize("intake, expected, ignored", [
    ({"registered_model_id": "MOD-001", "model_inventory_registered": True}, True, False),    # 1 valid + true
    ({"registered_model_id": "MOD-001", "model_inventory_registered": False}, True, True),    # 2 valid + false
    ({"model_inventory_registered": True}, False, True),                                      # 3 missing + true
    ({"registered_model_id": "MOD-999", "model_inventory_registered": True}, False, True),    # 4 invalid + true
    ({"model_inventory_registered": False}, False, False),                                    # 5 missing + false
    ({"registered_model_id": "MOD-999", "model_name": "PD_Shared", "model_inventory_registered": True}, False, True),  # 6
    ({"model_name": "PD_Shared", "model_inventory_registered": True}, False, True),          # 6 name only
])
def test_attestation_matrix(client, intake, expected, ignored):
    before = _fp()
    att = main.attest_inventory_registration(intake)
    assert att["verified"] is expected and att["client_claim_ignored"] is ignored
    assert att["source"] == "development_inventory"
    assert att["registered_model_id"] == ((intake.get("registered_model_id") or None))   # exact ID kept, never a name
    if not expected:
        assert "not confirmed" in att["detail"]
    if intake.get("registered_model_id") == "MOD-999":
        assert "not found in the Development Inventory" in att["detail"]
    assert _fp() == before


def test_deleted_model_is_no_longer_registered(client):                                     # 7
    assert main.attest_inventory_registration({"registered_model_id": "MOD-002"})["verified"] is True
    store = persistence.load_model_inventory()
    store["development"] = [m for m in store["development"] if m["model_id"] != "MOD-002"]
    persistence.save_model_inventory(store)
    att = main.attest_inventory_registration({"registered_model_id": "MOD-002", "model_inventory_registered": True})
    assert att["verified"] is False and "unavailable" in att["detail"]


def test_wrapper_replaces_every_client_registration_field(client):
    out = main.with_attested_registration({"registered_model_id": None, "model_inventory_registered": True,
                                           "registration_attestation": FORGED, "model_name": "PD_Shared"})
    assert out["model_inventory_registered"] is False
    assert out["registration_attestation"]["verified"] is False
    assert out["registration_attestation"]["detail"] != "forged by client"


# 8 ── Stage 2 check 1.2 uses the server's status ──────────────────────────

def test_stage2_check_cannot_be_bypassed_by_the_payload(client):
    forged = _check_12({"model_inventory_registered": True, "registration_attestation": FORGED})
    assert forged["status"] == "WARN" and "not confirmed" in forged["observed"]
    invalid = _check_12({"registered_model_id": "MOD-999", "model_inventory_registered": True})
    assert invalid["status"] == "WARN" and "MOD-999" in invalid["observed"]
    genuine = _check_12({"registered_model_id": "MOD-001", "model_inventory_registered": False})
    assert genuine["status"] == "PASS" and "MOD-001" in genuine["observed"]
    assert forged["severity"] == genuine["severity"] == "HIGH"                             # severity rule unchanged


def test_agent2_endpoint_uses_the_server_status(client):
    # /validation/agent2 returns the full ValidationAgent2 report, check 1.2 included.
    def run(intake):
        r = client.post("/validation/agent2", data={"intake_json": json.dumps(intake)})
        assert r.status_code == 200, r.text
        return r.json()
    forged = run({"model_inventory_registered": True, "registration_attestation": FORGED})
    assert _consistent_12(forged)["status"] == "WARN" and "forged by client" not in json.dumps(forged)
    genuine = run({"registered_model_id": "MOD-001", "model_inventory_registered": False})
    assert _consistent_12(genuine)["status"] == "PASS"


def test_stage2_run_never_reports_a_forged_registration(client):
    r = client.post("/validation/stage2/run", data={"intake_json": json.dumps(
        {"model_inventory_registered": True, "registration_attestation": FORGED})})
    assert r.status_code == 200
    text = json.dumps(r.json())
    assert "Model inventory registration confirmed" not in text and "forged by client" not in text


# 9 ── Stage 7/8 Findings use the same server status ───────────────────────

def _registration_findings(client, intake, registered_model_id=None):
    data = {"intake_json": json.dumps(intake)}
    if registered_model_id is not None:
        data["registered_model_id"] = registered_model_id
    r = client.post("/validation/stage8/findings", data=data)
    assert r.status_code == 200, r.text
    return [f for f in r.json()["findings"] if f.get("check") == "1.2 Model Inventory"]


def test_findings_cannot_be_bypassed_by_the_payload(client):
    (forged,) = _registration_findings(client, {"model_inventory_registered": True, "registration_attestation": FORGED})
    assert (forged["severity"], forged["status"]) == ("HIGH", "FAIL")                      # severity rule unchanged
    assert "not confirmed" in forged["observed"]
    (invalid,) = _registration_findings(client, {"registered_model_id": "MOD-999", "model_inventory_registered": True})
    assert "MOD-999" in invalid["observed"]
    (same_name,) = _registration_findings(client, {"model_name": "PD_Shared", "model_inventory_registered": True})
    assert same_name["status"] == "FAIL"
    assert _registration_findings(client, {"registered_model_id": "MOD-001", "model_inventory_registered": False}) == []
    assert _registration_findings(client, {"model_inventory_registered": False}, registered_model_id="MOD-001") == []


def test_stage2_and_findings_agree(client):
    for intake in ({"registered_model_id": "MOD-001"}, {"registered_model_id": "MOD-999", "model_inventory_registered": True},
                   {"model_inventory_registered": True}):
        passed = _check_12(intake)["status"] == "PASS"
        has_finding = bool(_registration_findings(client, intake))
        assert passed is not has_finding, intake


# 10 ── No inventory mutation ───────────────────────────────────────────────

def test_attestation_and_checks_do_not_mutate_inventory(client):
    before = _fp()
    files_before = sorted(str(p) for p in persistence.APP_DATA_DIR.rglob("*.pdf"))
    for intake in ({"registered_model_id": "MOD-001"}, {"registered_model_id": "MOD-999"}, {"model_inventory_registered": True}):
        main.attest_inventory_registration(intake)
        _check_12(intake)
        client.post("/validation/stage2/run", data={"intake_json": json.dumps(intake)})
        _registration_findings(client, intake)
    client.get("/model-inventory")
    client.get("/model-inventory/development/MOD-001/lineage")
    assert _fp() == before
    assert sorted(str(p) for p in persistence.APP_DATA_DIR.rglob("*.pdf")) == files_before
