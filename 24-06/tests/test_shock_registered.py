"""Residual E2: the manual "Apply Shock" control.

With a registered model ID the shock scores the REGISTERED model's verified
scoring bundle on its recorded test rows (never a refit); without one it is
an independent refit labelled as such. A shock is never logged and never
influences the verdict. Isolated temporary app_data, synthetic data.
"""
import hashlib
import io
import json

import numpy as np
import pandas as pd
import pytest

import _aegis_test_env as env
import main
import model_lineage
import persistence

DF = env.dataset_coefs(1500, [1.0, 0.6, 0.3, 0.2], seed=44)
DF = DF.assign(gender=np.where(np.arange(len(DF)) % 2 == 0, "F", "M"))
CSV = env.to_csv(DF)
DF = pd.read_csv(io.BytesIO(CSV))
OTHER_CSV = env.to_csv(DF.assign(f0=DF["f0"] + 0.5))
MDD = ("Calibrated via Platt scaling. IFRS 9 staging with SICR. Limitations and assumptions are documented. "
       "Macro overlays use GDP and unemployment.")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("shock")) as c:
        yield c


@pytest.fixture(scope="module")
def model(client):
    # Feature engineering on and a dropped column, so the full scoring chain matters.
    return env.train(client, CSV, "Shock Model", use_feature_engineering=True, drop_cols=["f3"])["model_id"]


@pytest.fixture()
def no_refit(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a registered-model shock must not refit")
    monkeypatch.setattr(main, "run_replication", boom)


@pytest.fixture()
def loads(monkeypatch):
    seen = []
    real = model_lineage._deserialize_verified

    def spy(data):
        seen.append(hashlib.sha256(data).hexdigest())
        return real(data)
    monkeypatch.setattr(model_lineage, "_deserialize_verified", spy)
    return seen


def shock(client, model_id=None, csv=CSV, feature="f0", direction="increase", magnitude=20, **extra):
    data = {"target_col": "default", "algorithm": "Logistic Regression", "shock_feature": feature,
            "shock_direction": direction, "shock_magnitude_pct": str(magnitude), **extra}
    if model_id:
        data["registered_model_id"] = model_id
    return client.post("/validation/stress/shock", data=data, files={"file": ("dev.csv", io.BytesIO(csv), "text/csv")})


def ctx(model_id):
    return model_lineage.registered_evaluation(DF, model_id, dataset_sha256=main.dataset_fingerprint(DF))


# ── Transformation order: verified against the training code, not assumed ──

def test_bundle_scoring_chain_reproduces_the_training_transformations(client, model):
    """The bundle's chain (drop → imputer → feature engineering → column
    order) applied to the recorded raw test rows yields exactly the matrix
    training fed the model (re-derived with the training code itself)."""
    contract = env.dev_entry(model)["lineage_contract"]
    fit = model_lineage._fit_from_contract(DF, contract)          # the training code path, same split and plan
    c = ctx(model)
    pd.testing.assert_frame_equal(c["X_test"], fit["X_test"], check_exact=True)
    assert list(c["X_test"].columns) == contract["features"]["model_input_columns"]
    assert "f3" not in c["X_test"].columns                        # dropped before scoring
    # Same predictions as the registered test evaluation.
    np.testing.assert_array_equal(c["pipeline"].predict_proba(c["X_test"])[:, 1], c["y_proba"])


# ── Registered model: verified bundle, recorded rows, no refit ─────────────

def test_registered_shock_uses_the_verified_bundle_and_never_refits(client, model, no_refit, loads):
    r = shock(client, model)
    assert r.status_code == 200, r.text
    body = r.json()
    ev = body["evidence"]
    c = env.dev_entry(model)["lineage_contract"]
    assert ev["evaluation_mode"] == model_lineage.EVALUATION_MODE_REGISTERED
    assert ev["registered_model_id"] == model and ev["training_run_id"] == c["training_run_id"]
    assert ev["bundle_sha256"] == c["artifact"]["sha256"] and ev["test_index_sha256"] == c["split"]["test_index_sha256"]
    assert ev["persisted"] is False and ev["verdict_evidence"] is False
    assert loads and all(sha == c["artifact"]["sha256"] for sha in loads)
    res = body["result"]
    base = ctx(model)
    assert res["rows"] == c["split"]["test_rows"]
    assert res["base_pd"] == pytest.approx(float(np.mean(base["y_proba"])), abs=1e-12)
    # Shocked PD = the raw feature shocked and re-scored through the full chain.
    X_raw = base["X_test_raw"].copy()
    X_raw["f0"] = X_raw["f0"] * 1.2
    expected = float(base["pipeline"].predict_proba(base["transform"](X_raw))[:, 1].mean())
    assert res["shock_pd"] == pytest.approx(expected, abs=1e-12)
    assert res["shock_pd"] != res["base_pd"]
    assert shock(client, model).json()["result"] == res                     # reproducible


def test_algorithm_is_ignored_for_a_registered_shock(client, model, no_refit):
    a = shock(client, model, algorithm="XGBoost").json()["result"]
    b = shock(client, model, algorithm="Random Forest").json()["result"]
    assert a == b


@pytest.mark.parametrize("feature, fragment", [("f3", "not a numeric raw input"),       # dropped by preprocessing
                                               ("gender", "not a numeric raw input"),   # categorical
                                               ("nope", "not a numeric raw input")])
def test_only_numeric_raw_inputs_can_be_shocked(client, model, no_refit, feature, fragment):
    r = shock(client, model, feature=feature)
    assert r.status_code == 400 and fragment in r.json()["detail"]


def test_shockable_features_are_listed_by_the_registered_stress_run(client, model, monkeypatch):
    monkeypatch.setattr(main, "run_stress_suite", lambda *a, **k: {"available": True})
    body = client.post("/validation/stress/run", data={"target_col": "default", "registered_model_id": model},
                       files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")}).json()
    assert body["shockable_features"] == ["f0", "f1", "f2"]


# ── Fail closed: never a refit fallback ────────────────────────────────────

def test_unresolvable_registered_models_fail_closed(client, model, no_refit):
    assert shock(client, "MOD-999").status_code == 404
    r = shock(client, model, csv=OTHER_CSV)
    assert r.status_code == 409 and "dataset_mismatch" in r.json()["detail"]
    r = shock(client, model, expected_training_run_id="not-the-current-run")
    assert r.status_code == 409 and "training_run_mismatch" in r.json()["detail"]
    store = persistence.load_model_inventory()
    store["development"].append({"model_id": "MOD-LEGACY", "model_name": "Legacy", "algorithm": "LR", "status": "In Development"})
    persistence.save_model_inventory(store)
    r = shock(client, "MOD-LEGACY")
    assert r.status_code == 409 and "lineage_missing" in r.json()["detail"]


def test_tampered_bundle_is_never_loaded(client, monkeypatch, no_refit, loads):
    body = env.train(client, CSV, "Shock Tamper Model")
    path = persistence.BACKEND_DIR / env.dev_entry(body["model_id"])["lineage_contract"]["artifact"]["path"]
    path.write_bytes(path.read_bytes() + b"tampered")
    r = shock(client, body["model_id"])
    assert r.status_code == 409 and "bundle_integrity_failed" in r.json()["detail"]
    assert loads == []


# ── No ID: an independent refit, labelled as such ──────────────────────────

def test_no_id_is_an_independent_refit(client):
    r = shock(client)
    assert r.status_code == 200, r.text
    ev = r.json()["evidence"]
    assert ev["evaluation_mode"] == model_lineage.EVALUATION_MODE_INDEPENDENT_REFIT
    assert ev["registered_model_id"] is None and ev["training_run_id"] is None
    assert ev["refit_algorithm"] == "Logistic Regression" and ev["verdict_evidence"] is False
    assert shock(client, algorithm="").status_code == 400                     # no ID and no algorithm
    assert shock(client, magnitude=0).status_code == 400
    assert shock(client, direction="sideways").status_code == 400


# ── A shock is never evidence ──────────────────────────────────────────────

def test_shock_is_not_logged_and_cannot_influence_the_verdict(client, model, monkeypatch):
    log = persistence.APP_DATA_DIR / persistence.VALIDATION_PIPELINE_LOG

    def rows():
        return persistence.read_log(persistence.VALIDATION_PIPELINE_LOG) if log.exists() else []
    before = len(rows())
    for kwargs in ({"model_id": model}, {}):
        assert shock(client, **kwargs).status_code == 200
    assert len(rows()) == before                                              # nothing persisted

    # Real registered stress run + attestation; replication stubbed as passing
    # (its own tests cover it), so the verdict depends on the evidence items.
    monkeypatch.setattr(main, "assess_replication_evidence", lambda run_id, claimed: {
        "status": "PASS", "run_id": run_id, "reasons": [], "execution_failed": False,
        "metrics": {"roc_auc": 0.8, "gini": 0.6, "ks": 0.45, "recall": 0.7, "brier_score": 0.1}, "reference_metrics": {},
        "failed_mandatory_checks": [], "failed_other_checks": [], "mandatory_checks": [], "identity": {}, "methodology": {}})
    assert client.post("/validation/stress/run", data={"target_col": "default", "registered_model_id": model},
                       files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")}).status_code == 200
    client.post("/validation/independence/attest", data={"registered_model_id": model, "attested_by": "V", "independent": "true"})

    def verdict(**extra):
        data = {"intake_json": json.dumps({"registered_model_id": model, "model_name": "Shock Model", "model_tier": "Tier 2"}),
                "mdd_text": MDD, "replication_run_id": "rep-1", "registered_model_id": model, **extra}
        r = client.post("/validation/stage8/findings", data=data, files={"file": ("dev.csv", io.BytesIO(CSV), "text/csv")})
        assert r.status_code == 200, r.text
        return r.json()

    clean = verdict()
    extreme = json.dumps({"feature": "f0", "base_pd": 0.1, "shock_pd": 0.99, "pd_change": 0.89, "pd_change_pct": 890.0})
    shocked = verdict(shock_result_json=extreme)
    assert shocked["verdict_basis"]["ignored_client_inputs"] == ["shock_result_json"]
    for key in ("verdict", "findings"):
        assert shocked.get(key) == clean.get(key), key
    assert shocked["verdict_basis"]["evidence_completeness"] == clean["verdict_basis"]["evidence_completeness"]
