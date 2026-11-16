"""Phase 1 regression tests — reference (developer-reported) metrics must stay
separate from metrics computed from model predictions.

Covers AEGIS_VALIDATION_REPLICATION_AUDIT.md findings C1 (Benchmarking
overwrote computed metrics with MDD claims), H5 (replication's "Reported"
values were not returned/saved) and the /validation/parse-mdd NameError.

Every persistence write is redirected to pytest's tmp_path; the fixture
fails the test if the real validation log changes.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402
import persistence  # noqa: E402


def _file_fingerprint(path: Path):
    return (path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else None


@pytest.fixture
def client(tmp_path, monkeypatch):
    real_log = BACKEND_DIR / "app_data" / persistence.VALIDATION_PIPELINE_LOG
    real_inventory = BACKEND_DIR / "app_data" / persistence.MODEL_INVENTORY_FILENAME
    before = (_file_fingerprint(real_log), _file_fingerprint(real_inventory))

    app_data = tmp_path / "app_data"
    artifacts = app_data / "artifacts"
    artifacts.mkdir(parents=True)
    monkeypatch.setattr(persistence, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(persistence, "APP_DATA_DIR", app_data)
    monkeypatch.setattr(persistence, "ARTIFACTS_DIR", artifacts)
    # ValidationAgent2 loads rag_store/rules.json relative to the cwd.
    monkeypatch.chdir(BACKEND_DIR)

    yield TestClient(main.app)

    after = (_file_fingerprint(real_log), _file_fingerprint(real_inventory))
    assert before == after, "test wrote to the real app_data log or inventory"


def _synthetic_csv(n=800, seed=11) -> bytes:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "credit_score": rng.normal(680, 60, n).round(),
        "debt_to_income": rng.uniform(0.05, 0.8, n).round(3),
        "num_late_payments": rng.poisson(1.0, n),
    })
    logit = -2.0 - 0.015 * (df.credit_score - 680) + 2.5 * df.debt_to_income + 0.4 * df.num_late_payments
    df["default"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df.to_csv(index=False).encode()


CSV = _synthetic_csv()


def _auc_from_points(points):
    fpr = np.array([p["fpr"] for p in points])
    tpr = np.array([p["tpr"] for p in points])
    order = np.argsort(fpr, kind="stable")
    integrate = getattr(np, "trapezoid", None) or np.trapz
    return float(integrate(tpr[order], fpr[order]))


def _files(extra=None):
    files = {"file": ("provenance_test.csv", io.BytesIO(CSV), "text/csv")}
    files.update(extra or {})
    return files


# ── build_reference_metrics (unit) ──────────────────────────────────────────

def test_reference_builder_mdd_wins_and_sources_are_kept():
    ref = main.build_reference_metrics(
        json.dumps({"roc_auc": 0.70, "accuracy": 0.8}),
        json.dumps({"roc_auc": "manual_entry", "accuracy": "development_training_run"}),
        {"roc_auc": 0.75, "recall": None},
    )
    assert ref["values"] == {"roc_auc": 0.75, "accuracy": 0.8}
    assert ref["sources"] == {"roc_auc": "mdd_upload", "accuracy": "development_training_run"}
    # D3: the MDD replaced a different reviewer value, so it is warned about (never silent).
    assert len(ref["warnings"]) == 1 and "roc_auc 0.7 (Entered manually by reviewer) → 0.75" in ref["warnings"][0]


def test_reference_builder_does_not_trust_unknown_source_labels():
    ref = main.build_reference_metrics(json.dumps({"roc_auc": 0.8}), json.dumps({"roc_auc": "computed_by_model"}))
    assert ref["sources"]["roc_auc"] == "client_supplied"


def test_reference_builder_reports_bad_input_instead_of_dropping_silently():
    bad_json = main.build_reference_metrics("not json")
    assert bad_json["values"] == {} and bad_json["warnings"]
    non_numeric = main.build_reference_metrics(json.dumps({"roc_auc": "abc"}))
    assert non_numeric["values"] == {} and "roc_auc" in non_numeric["warnings"][0]
    mdd_failed = main.build_reference_metrics(None, None, None, mdd_error="corrupt pdf")
    assert any("corrupt pdf" in w for w in mdd_failed["warnings"])


def test_demo_mdd_snapshot_uses_real_extracted_reference_metrics_from_shipped_documents():
    clean = main._build_validation_intake_snapshot("clean")
    flawed = main._build_validation_intake_snapshot("flawed")

    assert clean["val_mdd_reported_metrics"] == {
        "roc_auc": 0.82,
        "gini": 0.64,
        "ks": 0.58,
        "cv_mean_auc": 0.80,
        "accuracy": 0.85,
        "precision": 0.72,
        "recall": 0.71,
        "f1": 0.72,
        "brier_score": 0.16,
    }
    assert flawed["val_mdd_reported_metrics"] == {
        "roc_auc": 0.78,
        "gini": 0.56,
        "ks": 0.48,
        "cv_mean_auc": 0.73,
        "accuracy": 0.79,
        "precision": 0.61,
        "recall": 0.72,
        "f1": 0.65,
        "brier_score": None,
    }
    assert main.extract_metrics_from_mdd((BACKEND_DIR / "demo_data" / "clean_mdd.txt").read_text(encoding="utf-8"))["brier_score"] == 0.16
    assert main.extract_metrics_from_mdd((BACKEND_DIR / "demo_data" / "flawed_mdd.txt").read_text(encoding="utf-8"))["brier_score"] is None


# ── /validation/performance (Benchmarking) — finding C1 ─────────────────────

CLAIMS = {"roc_auc": 0.99, "gini": 0.98, "recall": 0.97, "precision": 0.96}
CHECK_KEYS = {"ROC-AUC": "roc_auc", "Gini": "gini", "Recall": "recall", "Precision": "precision",
              "F1 Score": "f1", "Brier Score": "brier_score", "PR-AUC": "pr_auc", "KS Statistic": "ks"}


def test_performance_claims_never_overwrite_computed_metrics(client):
    r = client.post("/validation/performance", data={
        "model_name": "Logistic Regression", "target_col": "default", "challenger_model_name": "Random Forest",
        "reported_json": json.dumps(CLAIMS),
        "reported_sources_json": json.dumps({k: "intake_mdd" for k in CLAIMS}),
    }, files=_files())
    assert r.status_code == 200, r.text
    report = r.json()["report"]
    metrics = report["metrics"]

    computed_auc = _auc_from_points(report["roc_curve"]["points"])
    assert abs(metrics["roc_auc"] - computed_auc) < 0.01
    assert metrics["roc_auc"] != CLAIMS["roc_auc"]
    assert report["roc_curve"]["auc"] == metrics["roc_auc"]
    assert "mdd_reported" not in metrics

    for check in report["metric_checks"]:
        assert check["value"] == metrics[CHECK_KEYS[check["check"]]], check

    bench = report["benchmark"]
    assert bench["status"] == "OK"
    champion = bench["comparison"]["champion_vs_challenger"]
    assert champion["roc_auc"]["champion"] == metrics["roc_auc"]
    assert champion["recall"]["champion"] == metrics["recall"]

    assert report["reference_metrics"]["values"] == CLAIMS
    assert set(report["reference_metrics"]["sources"].values()) == {"intake_mdd"}
    assert report["metric_provenance"] == {
        "schema_version": 2, "metrics": "computed_from_model_predictions",
        "reference_metrics": "developer_reported", "reference_overrides_computed": False,
        # D2: browser-claimed "intake_mdd" labels are recorded but never presented as verified.
        "reference_source_verification": {"server_verified": [], "browser_reported": sorted(CLAIMS)},
    }


def test_performance_mdd_upload_is_reference_only(client):
    mdd = ("mdd.txt", io.BytesIO(b"Performance: ROC-AUC: 0.97, Recall: 0.95."), "text/plain")
    r = client.post("/validation/performance", data={
        "model_name": "Logistic Regression", "target_col": "default", "challenger_model_name": "Logistic Regression",
    }, files=_files({"mdd_file": mdd}))
    assert r.status_code == 200, r.text
    report = r.json()["report"]
    assert report["reference_metrics"]["values"] == {"roc_auc": 0.97, "recall": 0.95}
    assert report["reference_metrics"]["sources"] == {"roc_auc": "mdd_upload", "recall": "mdd_upload"}
    assert abs(report["metrics"]["roc_auc"] - _auc_from_points(report["roc_curve"]["points"])) < 0.01
    assert report["metrics"]["recall"] != 0.95 or report["metrics"]["roc_auc"] != 0.97


def test_performance_runs_without_any_reference(client):
    r = client.post("/validation/performance", data={
        "model_name": "Logistic Regression", "target_col": "default", "challenger_model_name": "Logistic Regression",
    }, files=_files())
    assert r.status_code == 200, r.text
    report = r.json()["report"]
    assert report["reference_metrics"]["values"] == {}
    assert report["metric_provenance"]["reference_metrics"] == "none_supplied"


# ── /validation/replication — finding H5 + saved-record provenance ─────────

def test_replication_returns_and_saves_the_reference_actually_used(client):
    mdd = ("mdd.txt", io.BytesIO(b"ROC-AUC: 0.75"), "text/plain")
    r = client.post("/validation/replication", data={
        "model_name": "Provenance Model", "algorithm": "Logistic Regression", "target_col": "default",
        "reported_json": json.dumps({"roc_auc": 0.70, "accuracy": 0.80}),
        "reported_sources_json": json.dumps({"roc_auc": "manual_entry", "accuracy": "development_training_run"}),
    }, files=_files({"mdd_file": mdd}))
    assert r.status_code == 200, r.text
    body = r.json()
    report = body["report"]

    ref = report["reference_metrics"]
    assert ref["values"] == {"roc_auc": 0.75, "accuracy": 0.80}
    assert ref["sources"] == {"roc_auc": "mdd_upload", "accuracy": "development_training_run"}

    # R4.2 compared against exactly the returned reference value.
    r42 = next(c for c in report["replication"]["checks"] if c["id"] == "R4.2")
    assert "Reported = 0.7500" in r42["observed"]

    # Replicated metrics are computed, untouched by the reference.
    rep_metrics = report["replication"]["result"]["metrics"]
    assert abs(rep_metrics["roc_auc"] - _auc_from_points(report["roc_curve"]["points"])) < 0.01
    assert report["metric_provenance"]["reference_overrides_computed"] is False

    latest = client.get("/history/latest", params={
        "log_file": persistence.VALIDATION_PIPELINE_LOG, "stage": "replication",
        "business_model_name": "Provenance Model", "dataset_name": "provenance_test.csv",
    }).json()["latest"]
    assert latest is not None
    assert latest["summary"]["reference_metrics"] == ref["values"]
    assert latest["summary"]["reference_sources"] == ref["sources"]
    assert latest["summary"]["metric_provenance_version"] == 2
    assert latest["full_payload"]["report"]["reference_metrics"] == ref


# ── /validation/parse-mdd — NameError regression ───────────────────────────

def test_parse_mdd_saves_file_and_extracts_metrics(client):
    r = client.post("/validation/parse-mdd", files={"mdd_file": ("m.txt", io.BytesIO(b"ROC-AUC: 0.81"), "text/plain")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metrics"]["roc_auc"] == 0.81
    saved = persistence.BACKEND_DIR / body["mdd_document_path"]
    assert saved.exists() and saved.read_bytes() == b"ROC-AUC: 0.81"
