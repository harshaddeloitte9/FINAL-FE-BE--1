"""Batch 2 regression tests: model identity and registration integrity.
Phase 4 isolated environment; no model is trained or replicated (the
replication engine is stubbed where the endpoint is exercised).

Frontend selection / draft / demo rules are unit-tested separately in
aegis-frontend/unit-tests/model-identity.test.ts; the source checks at the
end make sure the pages actually use those rules.
"""
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest

import _aegis_test_env as env
import main
import model_lineage
import persistence

FRONTEND = Path(env.BACKEND_DIR).parent / "aegis-frontend" / "src"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


def _bundle(name="MOD-001.joblib", content=b"scoring-bundle-bytes"):
    path = persistence.APP_DATA_DIR / "model_artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": str(path.relative_to(persistence.BACKEND_DIR)), "sha256": hashlib.sha256(content).hexdigest()}


def _contract(artifact, task_type="binary"):
    return {"contract_version": model_lineage.LINEAGE_CONTRACT_VERSION, "task_type": task_type, "training_run_id": "TR-1",
            "target_col": "default", "estimator_name": "XGBoost", "dataset": {"name": "dev.csv"}, "artifact": artifact}


def _dev(model_id, name, **extra):
    return {"model_id": model_id, "model_name": name, "algorithm": "XGBoost", "status": "In Development",
            "documentation_path": "docs/x.pdf", **extra}


def _save(*development):
    persistence.save_model_inventory({"development": list(development), "validation": [], "models": [],
                                      "data_sources": [], "history": []})
    return persistence.get_model_inventory_path()


@pytest.fixture()
def client(tmp_path):
    with env.isolated_backend(tmp_path) as c:
        yield c


# ── Phase B: demo registration integrity ──────────────────────────────────

@pytest.mark.parametrize("mode, expected_sample_size, expected_rate", [("taiwan", "700", "22.29%"), ("flawed", "3,180", "23.58%")])
def test_demo_intake_is_not_presented_as_registered_and_uses_real_dataset_stats(client, mode, expected_sample_size, expected_rate):
    path = _save(_dev("MOD-001", "PD_XGBoost_RetailCredit_v2"))   # same name as Demo A: must not be matched
    before = _sha(path)
    body = client.get("/validation/intake", params={"mode": mode}).json()
    text = json.dumps(body)
    assert "CR-PD-XGB-027" not in text
    assert body["display"]["modelMetadata"]["registeredLabel"] != "Registered"
    assert "not registered" in body["display"]["modelMetadata"]["registeredLabel"].lower()
    assert "demonstration" in body["display"]["modelMetadata"]["description"].lower()
    assert body["chk_inventory"] is False
    assert body["chk_attestation"] is False
    assert body["chk_tier"] is False
    assert body["is_demo"] is True
    assert body["display"]["targetDefinition"]["sampleSize"] == expected_sample_size
    assert body["display"]["targetDefinition"]["baseRate"] == expected_rate
    snap = body["val_intake_data"]
    assert snap["registered_model_id"] is None and snap["model_inventory_registered"] is False and snap["is_demo_data"] is True
    assert _sha(path) == before                                     # demo never touches the inventory


def test_demo_dataset_load_does_not_create_inventory_entries(client):
    path = _save(_dev("MOD-001", "Existing"))
    before = _sha(path)
    r = client.post("/data/upload", data={"demo_mode": "flawed"})
    assert r.status_code == 200, r.text
    assert _sha(path) == before
    assert [m["model_id"] for m in persistence.load_model_inventory()["development"]] == ["MOD-001"]


def test_taiwan_demo_mode_uses_real_ucci_dataset_and_700_row_sample(client):
    body = client.get("/validation/intake", params={"mode": "taiwan"}).json()
    assert body["demo_mode"] == "taiwan"
    assert body["display"]["modelMetadata"]["description"].lower().startswith("demo a")
    assert body["display"]["targetDefinition"]["sampleSize"] == "700"
    assert body["display"]["targetDefinition"]["baseRate"] == "22.29%"
    assert body["val_intake_data"]["model_name"] == "Demo A — Taiwan benchmark"

    upload = client.post("/data/upload", data={"demo_mode": "taiwan"})
    assert upload.status_code == 200, upload.text
    profile = upload.json()
    assert profile["demo_mode"] == "taiwan"
    assert profile["rows"] == 700
    assert abs(profile["default_rate"] - 0.222857) < 1e-6


@pytest.mark.parametrize("mode", ["clean", "flawed"])
def test_demo_replication_logs_history_without_validation_inventory_registration(client, mode):
    before = persistence.load_model_inventory()
    before_validation = list(before.get("validation", []))
    demo_csv = (Path(main.BACKEND_DIR) / "demo_data" / f"{mode}_portfolio.csv").read_text(encoding="utf-8")
    r = client.post(
        "/validation/replication",
        data={
            "target_col": "default",
            "model_name": f"Demo {mode.title()}",
            "algorithm": "XGBoost",
            "csv_text": demo_csv,
            "intake_json": json.dumps({"model_name": f"Demo {mode.title()}", "demo_mode": mode, "is_demo_data": True}),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"]["persisted"] is True
    assert body["evidence"]["validation_model_id"] is None
    assert body["evidence"]["validation_run_id"] is None
    assert body["evidence"]["dataset_sha256"] == main.dataset_fingerprint(pd.read_csv(io.StringIO(demo_csv), float_precision="round_trip"))

    summary_rows = [
        row for row in persistence.list_runs(persistence.VALIDATION_PIPELINE_LOG)
        if row.get("stage") == "replication"
        and row.get("summary", {}).get("dataset_sha256") == body["evidence"]["dataset_sha256"]
    ]
    assert summary_rows, "demo replication run was not written to the validation pipeline log"
    assert summary_rows[-1]["summary"].get("demo_dataset") is True

    after = persistence.load_model_inventory()
    assert len(after.get("validation", [])) == len(before_validation)


def test_real_independent_refit_still_registers_validation_record(client):
    before = persistence.load_model_inventory()
    before_validation = list(before.get("validation", []))
    df = env.dataset(120, 8, 0.9, seed=7)
    r = client.post(
        "/validation/replication",
        data={
            "target_col": "default",
            "model_name": "Real Independent Refit",
            "algorithm": "XGBoost",
            "csv_text": env.to_csv(df).decode("utf-8"),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"]["validation_model_id"] is not None
    assert body["evidence"]["validation_run_id"] is not None
    after = persistence.load_model_inventory()
    assert len(after.get("validation", [])) == len(before_validation) + 1


def test_browser_forged_demo_flag_cannot_bypass_server_demo_detection(client):
    df = env.dataset(120, 8, 0.9, seed=11)
    csv_text = env.to_csv(df).decode("utf-8")
    r = client.post(
        "/validation/replication",
        data={
            "target_col": "default",
            "model_name": "Pretend Demo",
            "algorithm": "XGBoost",
            "csv_text": csv_text,
            "intake_json": json.dumps({"model_name": "Pretend Demo", "is_demo_data": True, "demo_mode": "clean"}),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"]["dataset_sha256"] == main.dataset_fingerprint(df)
    assert body["evidence"]["validation_model_id"] is not None
    assert body["evidence"]["validation_run_id"] is not None


def test_demo_verdict_is_never_approved(client):
    demo_df = pd.read_csv(Path(main.BACKEND_DIR) / "demo_data" / "clean_portfolio.csv", float_precision="round_trip")
    demo_sha = main.dataset_fingerprint(demo_df)
    body = client.post(
        "/validation/stage8/findings",
        data={
            "intake_json": json.dumps({
                "model_name": "Demo A",
                "chk_attestation": True,
                "model_inventory_registered": False,
                "independence_confirmed": True,
                "frameworks": ["SS1/23"],
                "is_demo_data": True,
                "demo_mode": "clean",
            }),
            "mdd_text": (Path(main.BACKEND_DIR) / "demo_data" / "clean_mdd.txt").read_text(encoding="utf-8"),
            "dataset_sha256": demo_sha,
            "registered_model_id": "",
        },
    )
    assert body.status_code == 200, body.text
    verdict = body.json()["verdict"]
    assert verdict == "INCONCLUSIVE"
    assert verdict not in {"APPROVED", "CONDITIONALLY APPROVED"}


def test_fake_browser_demo_flag_cannot_bypass_missing_evidence(client):
    body = client.post(
        "/validation/stage8/findings",
        data={
            "intake_json": json.dumps({
                "model_name": "Pretend Demo A",
                "chk_attestation": True,
                "model_inventory_registered": False,
                "independence_confirmed": True,
                "frameworks": ["SS1/23"],
                "is_demo_data": True,
                "demo_mode": "clean",
            }),
            "mdd_text": "",
            "dataset_sha256": "definitely-not-demo-sha",
            "registered_model_id": "",
        },
    )
    assert body.status_code == 200, body.text
    payload = body.json()
    assert payload["demo_dataset"] is False
    assert payload["verdict"] == "NOT ASSESSED"


def test_backend_rejects_incomplete_submission_even_if_confirmation_is_checked(client):
    body = client.post(
        "/validation/stage8/findings",
        data={
            "intake_json": json.dumps({
                "model_name": "Incomplete Submission",
                "chk_attestation": True,
                "model_inventory_registered": False,
                "independence_confirmed": True,
                "model_owner": "Owner One",
                "lead_validator": "Validator One",
                "owning_team": "Credit Risk",
                "model_version": "1.0",
                "model_purpose": "Retail credit monitoring",
                "frameworks": ["SS1/23"],
            }),
            "mdd_text": "Retail credit model with purpose and intended use documented.",
            "registered_model_id": "",
        },
    )
    assert body.status_code == 200, body.text
    verdict = body.json()["verdict"]
    assert verdict not in {"APPROVED", "CONDITIONALLY APPROVED"}
    assert "independence" in json.dumps(body.json()).lower() or verdict in {"INCONCLUSIVE", "NOT ASSESSED"}


# ── Fingerprint integrity contract ───────────────────────────────────────────


def test_dataset_fingerprint_contract_is_stable_and_sensitive_to_identity_changes():
    base = pd.DataFrame({
        "id": [1, 2, 3],
        "score": [0.1234567890123, 1.5, 2.75],
        "segment": ["A", "B", "A"],
        "default": [0, 1, 0],
    })
    round_trip = pd.read_csv(io.StringIO(base.to_csv(index=False)))
    assert main.dataset_fingerprint(base) == main.dataset_fingerprint(round_trip)

    changed_value = base.copy()
    changed_value.loc[0, "score"] = 0.1234567890124
    assert main.dataset_fingerprint(base) != main.dataset_fingerprint(changed_value)

    tiny_delta = base.copy()
    tiny_delta.loc[0, "score"] = 0.1234567890123001
    assert main.dataset_fingerprint(base) != main.dataset_fingerprint(tiny_delta)

    renamed = base.rename(columns={"score": "score_renamed"})
    assert main.dataset_fingerprint(base) != main.dataset_fingerprint(renamed)

    reordered_cols = base[["default", "id", "score", "segment"]]
    assert main.dataset_fingerprint(base) != main.dataset_fingerprint(reordered_cols)

    reordered_rows = base.iloc[::-1].reset_index(drop=True)
    assert main.dataset_fingerprint(base) != main.dataset_fingerprint(reordered_rows)

    missing = base.copy()
    missing.loc[0, "score"] = None
    assert main.dataset_fingerprint(base) != main.dataset_fingerprint(missing)
    parsed_missing = pd.read_csv(io.StringIO(missing.to_csv(index=False)))
    assert main.dataset_fingerprint(missing) == main.dataset_fingerprint(parsed_missing)

    precise_float = pd.DataFrame({"x": [1.000000000001, 1.000000000002, 1.000000000003]})
    coarse_float = pd.DataFrame({"x": [1.0, 1.0, 1.0]})
    assert main.dataset_fingerprint(precise_float) != main.dataset_fingerprint(coarse_float)

    int_like = pd.DataFrame({"value": [1, 2, 3]})
    float_like = pd.DataFrame({"value": [1.0, 2.0, 3.0]})
    assert main.dataset_fingerprint(int_like) != main.dataset_fingerprint(float_like)

    cats_a = pd.DataFrame({"segment": ["A", "B", "A"]})
    cats_b = pd.DataFrame({"segment": ["A", "C", "A"]})
    assert main.dataset_fingerprint(cats_a) != main.dataset_fingerprint(cats_b)

    missing_matrix = pd.DataFrame({"a": [1.0, None, 3.0], "b": [None, 2.0, 3.0]})
    parsed_missing_matrix = pd.read_csv(io.StringIO(missing_matrix.to_csv(index=False)))
    assert main.dataset_fingerprint(missing_matrix) == main.dataset_fingerprint(parsed_missing_matrix)


# ── Phase D: lineage visibility (read-only endpoint) ──────────────────────

def _lineage(client, model_id, status=200):
    r = client.get(f"/model-inventory/development/{model_id}/lineage")
    assert r.status_code == status, r.text
    return r.json()


def test_genuine_registered_model_is_replication_ready(client):
    _save(_dev("MOD-001", "PD_Ready", lineage_contract=_contract(_bundle())))
    body = _lineage(client, "MOD-001")
    assert body["status"] == "ready" and body["replication_ready"] is True
    assert body["scoring_bundle"] == {**body["scoring_bundle"], "recorded": True, "available": True, "integrity": "verified"}
    assert body["contract"]["training_run_id"] == "TR-1" and body["reasons"] == []


def test_missing_lineage_contract_is_incomplete_not_ready(client):
    _save(_dev("MOD-001", "PD_Legacy"),
          _dev("MOD-002", "PD_Failed_Capture", lineage_contract_error="RuntimeError: disk full"))
    legacy = _lineage(client, "MOD-001")
    assert legacy["status"] == "lineage_missing" and legacy["replication_ready"] is False
    assert legacy["contract"] is None and legacy["scoring_bundle"]["available"] is False
    assert "Retrain" in legacy["reasons"][0]
    failed = _lineage(client, "MOD-002")
    assert any("disk full" in r for r in failed["reasons"])
    # No contract is manufactured for a legacy model.
    assert "lineage_contract" not in persistence.load_model_inventory()["development"][0]


def test_missing_or_tampered_scoring_bundle_is_incomplete(client):
    good = _bundle("MOD-002.joblib")
    tampered = _bundle("MOD-003.joblib")
    (persistence.BACKEND_DIR / tampered["path"]).write_bytes(b"changed after registration")
    _save(_dev("MOD-001", "PD_No_Bundle_Recorded", lineage_contract=_contract({})),
          _dev("MOD-002", "PD_Bundle_Deleted", lineage_contract=_contract(good)),
          _dev("MOD-003", "PD_Bundle_Tampered", lineage_contract=_contract(tampered)),
          _dev("MOD-004", "PD_Outside", lineage_contract=_contract({"path": "../../outside.joblib", "sha256": "x"})),
          _dev("MOD-005", "PD_Regression", lineage_contract=_contract(_bundle("MOD-005.joblib"), task_type="regression")))
    (persistence.BACKEND_DIR / good["path"]).unlink()
    assert _lineage(client, "MOD-001")["status"] == "bundle_missing"
    deleted = _lineage(client, "MOD-002")
    assert deleted["status"] == "bundle_missing" and deleted["scoring_bundle"]["integrity"] == "missing"
    assert _lineage(client, "MOD-003")["status"] == "bundle_integrity_failed"
    assert _lineage(client, "MOD-004")["status"] == "bundle_missing"            # never reads outside the backend
    assert _lineage(client, "MOD-005")["status"] == "unsupported_task"
    for mid in ("MOD-001", "MOD-002", "MOD-003", "MOD-004", "MOD-005"):
        assert _lineage(client, mid)["replication_ready"] is False


def test_unknown_model_id_is_404_without_name_matching(client):
    _save(_dev("MOD-001", "PD_Name"))
    assert "not found" in _lineage(client, "MOD-999", status=404)["detail"]
    _lineage(client, "PD_Name", status=404)                                    # a name is not an ID


def test_lineage_endpoint_is_read_only(client):
    artifact = _bundle()
    path = _save(_dev("MOD-001", "PD_Ready", lineage_contract=_contract(artifact)), _dev("MOD-002", "PD_Legacy"))
    before, bundle_before = _sha(path), _sha(persistence.BACKEND_DIR / artifact["path"])
    files_before = sorted(str(p) for p in persistence.APP_DATA_DIR.rglob("*"))
    for mid in ("MOD-001", "MOD-002"):
        _lineage(client, mid)
    _lineage(client, "MOD-404", status=404)
    assert _sha(path) == before and _sha(persistence.BACKEND_DIR / artifact["path"]) == bundle_before
    assert sorted(str(p) for p in persistence.APP_DATA_DIR.rglob("*")) == files_before


# ── Phase E: registration → inventory refresh ─────────────────────────────

def test_registered_model_appears_in_inventory_refresh_with_its_exact_id(client):
    _save(_dev("MOD-001", "Existing"))
    # /models/train logs its training run before registering (temp log only).
    persistence.log_event(persistence.DEV_PIPELINE_LOG, stage="training", payload={"model_name": "PD_New"},
                          full_payload={"model_name": "PD_New"})
    store = persistence.load_model_inventory()
    reg = persistence.register_development_model(store=store, business_model_name="PD_New", estimator_name="XGBoost",
                                                 intake_payload={"status": "In Development"}, dataset_payload={})
    persistence.save_model_inventory(store)
    body = client.get("/model-inventory").json()
    ids = [m["model_id"] for m in body["development"]]
    assert reg["model_id"] in ids and ids.count(reg["model_id"]) == 1 and len(ids) == 2
    assert _lineage(client, reg["model_id"])["status"] == "lineage_missing"   # no contract without a real training


# ── Stage 3 sends and resolves the exact ID ───────────────────────────────

CSV = pd.DataFrame({"f0": range(40), "default": [i % 2 for i in range(40)]}).to_csv(index=False).encode()


def test_stage3_resolves_the_exact_registered_id(client, monkeypatch):
    _save(_dev("MOD-001", "PD_Shared", lineage_contract=_contract(_bundle("a.joblib"))),
          _dev("MOD-002", "PD_Shared_v2", lineage_contract=_contract(_bundle("b.joblib"))))
    seen = []

    def fake_registered(df, entry, **k):
        seen.append(entry["model_id"])
        return {"success": True, "metrics": {}, "original_metrics": {},
                "methodology": {"mode": model_lineage.REPLICATION_MODE_REGISTERED, "registered_model_id": entry["model_id"],
                                "training_run_id": "TR-1"}}
    monkeypatch.setattr(main.model_lineage, "run_registered_replication", fake_registered)
    monkeypatch.setattr(main, "_build_performance_report", lambda *a, **k: {"metrics": {}})
    monkeypatch.setattr(main, "evaluate_replication_checks", lambda *a, **k: [])

    def post(model_id, model_name):
        return client.post("/validation/replication",
                           data={"target_col": "default", "registered_model_id": model_id, "model_name": model_name},
                           files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")})

    ev = post("MOD-002", "PD_Shared").json()["evidence"]                      # name of MOD-001, ID of MOD-002
    assert seen == ["MOD-002"] and ev["registered_model_id"] == "MOD-002"
    assert post("MOD-404", "PD_Shared").status_code == 404 and seen == ["MOD-002"]   # no fallback to a name match


# ── Frontend wiring (source checks; behaviour is unit-tested in node) ─────

def _src(rel):
    path = FRONTEND / rel
    if not path.exists():
        pytest.skip("frontend sources not present next to this backend copy")
    return path.read_text(encoding="utf-8")


def test_intake_uses_shared_state_as_the_single_source_of_truth():
    src = _src("routes/validation.intake.tsx")
    assert "[registeredModelId, setRegisteredModelId] = useState" not in src     # no separate local copy
    assert "selectedModelId(validationIntakeData)" in src
    assert "withSelectedModel(validationIntakeData, id || null, inventoryIds)" in src      # immediate on change
    assert "demoIntakeSnapshot(" in src                                                    # demo clears the ID
    assert "restoreDraftModelId(draft.registeredModelId" in src and "registeredModelId: registeredModelId || null" in src
    assert "s.registeredModelId" not in src.replace("registeredModelId from older", "")    # not restored from old local snapshot
    assert 'registeredLabel === "Registered"' not in src


def test_stage3_blocks_registered_replication_unless_lineage_is_ready():
    src = _src("routes/validation.challenger.tsx")
    assert "replicationModelId(validationIntakeData)" in src
    assert "canRunRegisteredReplication(registeredIdentity)" in src
    assert 'form.append("registered_model_id", registeredModelId)' in src


def test_training_page_keeps_the_returned_model_id_and_lineage():
    src = _src("routes/model-training-evaluation.tsx")
    assert "trainedModelIdentity(trainResponse).modelId" in src
    assert "lineage: (trainResponse as Record<string, any>).lineage" in src
    assert "withSelectedModel(validationIntakeData, trained.modelId" in src
