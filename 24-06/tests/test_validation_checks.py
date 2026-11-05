"""Phase 5 regression tests — genuine validation checks and data-driven
visualisations. Runs inside the Phase 4 isolated environment (conftest.py +
_aegis_test_env.isolated_backend). Models are really trained; contamination
is created by really fitting components on train + test rows.
"""
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import _aegis_test_env as env
import main
import split_integrity as si
import val_replication_core as core
import validation_stress_core as stress
from train_new import train_model
from validation_agent2 import ValidationAgent2

CSV = env.to_csv(env.dataset(2000, 6, 0.3, seed=31))
DF = env.dataset(2000, 6, 0.3, seed=31)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("validation_checks")) as c:
        yield c


def _fit():
    return core._fit_core(DF, "default", "Logistic Regression", 0.15, 0.15, 42, 5)


def _sub(check, sub_id):
    return next(s for s in check["_subchecks"] if s["id"] == sub_id)


def _trapezoid(points, x="fpr", y="tpr"):
    xs, ys = np.array([p[x] for p in points]), np.array([p[y] for p in points])
    order = np.argsort(xs, kind="stable")
    integrate = getattr(np, "trapezoid", None) or np.trapz
    return float(integrate(ys[order], xs[order]))


# 1 ── Contaminated train/test splits ────────────────────────────────────────

def test_overlapping_split_indices_fail():
    check = si.build_r47([si.check_disjoint([1, 2, 3, 4], [5], [4, 6])])
    assert check["status"] == "FAIL"
    assert "train∩test: 1" in check["_subchecks"][0]["detail"]


def test_model_and_preprocessing_fitted_on_test_rows_fail():
    fit = _fit()
    X_all = pd.concat([fit["X_train"], fit["X_test"]])
    y_all = pd.concat([fit["y_train"], fit["y_test"]])
    # A pipeline that genuinely saw the test rows during fitting.
    contaminated, _, _ = train_model(X_all, y_all, col_types=fit["col_types"], target_col="default",
                                     prep_report=fit["prep_report_fe"], model=fit["model_cls"](**fit["model_params_used"]),
                                     use_cv=False, task_type="binary")
    r47 = core.unregistered_split_integrity({**fit, "pipeline": contaminated}, "default", 0.15, 0.15, 42)
    assert r47["status"] == "FAIL"
    assert _sub(r47, "S3")["status"] == "FAIL"
    assert _sub(r47, "S4")["status"] == "FAIL"


def test_component_fitted_on_all_rows_is_detected():
    rng = np.random.default_rng(0)
    train, test = rng.normal(0, 1, (200, 3)), rng.normal(3, 1, (50, 3))
    leaky = StandardScaler().fit(np.vstack([train, test]))
    res = si.check_component("S3", "scaler", lambda: leaky.transform(test),
                             lambda: StandardScaler().fit(train).transform(test), "Scaling")
    assert res["status"] == "FAIL"


def test_duplicate_records_across_split_warn():
    X_tr = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    X_te = pd.DataFrame({"a": [2, 9], "b": [5, 9]})
    res = si.check_duplicate_records(X_tr, pd.Series([0, 1, 0]), X_te, pd.Series([1, 0]))
    assert res["status"] == "WARN" and res["detail"].startswith("1 of 2")


# 2 ── Correctly isolated splits ─────────────────────────────────────────────

def test_isolated_unregistered_split_passes(client):
    rep = env.replicate(client, CSV, None, model_name="Isolated", algorithm="Logistic Regression")
    r47 = next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.7")
    assert r47["status"] == "PASS" and r47["executed"] is True
    assert {s["id"]: s["status"] for s in r47["_subchecks"]} == {
        "S1": "PASS", "S2": "PASS", "S3": "PASS", "S4": "PASS", "S5": "NOT_APPLICABLE", "S6": "PASS"}


def test_isolated_registered_split_passes_including_imputer(client):
    df = DF.copy()
    df.loc[df.sample(150, random_state=1).index, "f0"] = np.nan
    csv = env.to_csv(df)
    model_id = env.train(client, csv, "Imputed Split Model",
                         preprocessing_contract={"applied_treatment_map": {"f0": {"treatment": "statistical"}}})["model_id"]
    r47 = next(c for c in env.replicate(client, csv, model_id)["report"]["replication"]["checks"] if c["id"] == "R4.7")
    statuses = {s["id"]: s["status"] for s in r47["_subchecks"]}
    assert r47["status"] == "PASS", r47["_subchecks"]
    assert statuses["S3b"] == "PASS"            # imputer fitted on training rows only
    assert "recorded training split" in _sub(r47, "S6")["detail"]


# 3 ── Actual ROC curve calculations ─────────────────────────────────────────

def test_roc_and_pr_curves_come_from_predictions(client):
    r = client.post("/validation/performance", data={"model_name": "Logistic Regression", "target_col": "default",
                                                     "challenger_model_name": "Random Forest"},
                    files={"file": ("d.csv", io.BytesIO(CSV), "text/csv")})
    report = r.json()["report"]
    bench = report["benchmark"]
    pts = bench["roc_curve"]["points"]
    assert pts, "challenger ROC curve must be returned"
    area = _trapezoid(pts)
    assert abs(area - bench["metrics"]["roc_auc"]) < 0.01
    # The old synthesized line tpr = fpr × AUC has area AUC / 2 — not this.
    assert abs(area - bench["metrics"]["roc_auc"] / 2) > 0.1
    assert min(p["fpr"] for p in pts) == 0 and max(p["tpr"] for p in pts) == 1
    assert bench["pr_curve"]["points"] and bench["evaluation"]["same_test_rows_as_champion"] is True
    assert abs(_trapezoid(report["roc_curve"]["points"]) - report["metrics"]["roc_auc"]) < 0.01


def test_frontend_no_longer_synthesizes_challenger_curve():
    path = Path(env.BACKEND_DIR).parent / "aegis-frontend" / "src" / "routes" / "validation.performance.tsx"
    if not path.exists():
        pytest.skip("frontend sources not present next to this backend copy")
    src = path.read_text(encoding="utf-8")
    assert "point.fpr * benchmarkAuc" not in src
    assert "benchmarkResponse?.roc_curve?.points" in src


# 4 ── Confusion matrix consistency ──────────────────────────────────────────

def test_confusion_matrix_matches_metrics_and_test_rows(client):
    rep = env.replicate(client, CSV, None, model_name="CM", algorithm="Logistic Regression")
    report = rep["report"]
    ec = report["evaluation_consistency"]
    cm = np.array(report["confusion_matrix"]["matrix"])
    assert ec["status"] == "PASS", ec
    assert cm.sum() == ec["test_rows"] == rep["report"]["replication"]["result"]["split_stats"]["test_n"]
    assert report["threshold_selection"]["threshold"] == report["metrics"]["threshold_used"]
    tn, fp, fn, tp = cm.ravel()
    assert abs(report["metrics"]["recall"] - tp / (tp + fn)) < 5e-4


def test_confusion_matrix_uses_registered_threshold(client):
    model_id = env.train(client, CSV, "Threshold Model", threshold="0.3")["model_id"]
    report = env.replicate(client, CSV, model_id)["report"]
    assert report["metrics"]["threshold_used"] == pytest.approx(0.3)
    assert report["threshold_selection"]["threshold"] == pytest.approx(0.3)
    assert report["evaluation_consistency"]["status"] == "PASS"


def test_inconsistent_metrics_are_detected():
    res = main._evaluation_consistency(np.array([0, 0, 1, 1]), [[2, 0], [1, 1]], {"accuracy": 0.99, "recall": 0.5})
    assert res["status"] == "FAIL" and "accuracy" in res["detail"]


# 5 ── Multiple random seeds ─────────────────────────────────────────────────

def test_each_seed_is_an_independent_recorded_execution(client):
    rep = env.replicate(client, CSV, None, model_name="Seeds", algorithm="Logistic Regression", seeds="11,12,13,14")
    result = rep["report"]["replication"]["result"]
    runs = result["seed_runs"]
    assert [r["seed"] for r in runs] == [11, 12, 13, 14]
    assert all(r["status"] == "COMPLETED" and 0 < r["auc"] < 1 and r["test_rows"] > 0 for r in runs)
    aucs = [r["auc"] for r in runs]
    assert len(set(aucs)) > 1                     # different splits → different results
    r46 = next(c for c in rep["report"]["replication"]["checks"] if c["id"] == "R4.6")
    assert r46["_seeds"] == [11, 12, 13, 14] and r46["_seed_aucs"] == aucs
    assert [r["seed"] for r in r46["_runs"]] == [11, 12, 13, 14]
    assert r46["_summary"]["mean"] == round(float(np.mean(aucs)), 4)
    assert r46["_summary"]["sd"] == round(float(np.std(aucs, ddof=1)), 4)
    assert all(r["auc_se"] > 0 and r["auc_ci"][0] <= r["auc"] <= r["auc_ci"][1] for r in r46["_runs"])


# 6 ── Failed seed executions ────────────────────────────────────────────────

def test_failed_seed_is_reported_not_dropped(monkeypatch):
    real_split = core.split_data

    def flaky_split(*args, **kwargs):
        if kwargs.get("random_state") == 44:
            raise RuntimeError("simulated failure for seed 44")
        return real_split(*args, **kwargs)

    monkeypatch.setattr(core, "split_data", flaky_split)
    result = core.run_replication(DF, "default", "Logistic Regression", 0.15, 0.15, 42, 3, {}, [42, 43, 44, 45],
                                  compute_split_integrity=False)
    failed = [r for r in result["seed_runs"] if r["status"] == "FAILED"]
    assert [r["seed"] for r in failed] == [44] and "seed 44" in failed[0]["error"]
    r46 = next(c for c in core.evaluate_replication_checks(result, {}, [42, 43, 44, 45]) if c["id"] == "R4.6")
    assert r46["status"] != "PASS"
    assert any(r["seed"] == 44 and r["status"] == "FAILED" for r in r46["_runs"])
    assert any("seed 44" in l for l in r46["_limitations"])
    assert r46["_seeds"] == [42, 43, 45]          # labels aligned with the completed AUCs


# 7 ── Genuine feature ablation ──────────────────────────────────────────────

def test_ablation_retrains_without_each_feature():
    rng = np.random.default_rng(4)
    n = 3000
    df = pd.DataFrame({"signal": rng.normal(size=n), "noise": rng.normal(size=n), "weak": rng.normal(size=n)})
    df["default"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-(-1 + 2.0 * df.signal + 0.2 * df.weak)))).astype(int)
    result = core.run_replication(df, "default", "Logistic Regression", 0.15, 0.15, 42, 3, {}, [42, 43],
                                  compute_split_integrity=False)
    runs = {r["feature"]: r for r in result["ablation_runs"]}
    assert set(runs) == {"signal", "noise", "weak"}
    for r in runs.values():
        assert r["status"] == "COMPLETED" and r["feature_removed"] is True and r["features_used"] == 2
        assert r["auc_drop"] == round(r["baseline_auc"] - r["auc_without_feature"], 4)
    assert runs["signal"]["auc_drop"] > 0.15         # removing the real driver hurts…
    assert abs(runs["noise"]["auc_drop"]) < 0.02     # …removing noise does not


def test_failed_ablation_is_reported():
    # Feature removal is a diagnostic reported with R4.5 (it no longer
    # decides R4.5); failed removal retrains are listed, not dropped.
    import stability_checks as stability
    diag = stability.removal_diagnostics([{"feature": "x", "status": "FAILED", "error": "boom"}], 0.01, stability.load_criteria())
    assert diag["available"] is False and diag["failed"][0]["error"] == "boom"


# 8 ── Missing prediction probabilities ──────────────────────────────────────

def test_no_probabilities_means_no_curves_and_not_assessed():
    report = main._build_performance_report(None, {"metrics": {}, "y_test": None, "y_proba": None}, {}, "")
    assert report["roc_curve"]["points"] == [] and report["pr_curve"]["points"] == []
    assert report["confusion_matrix"] == []
    assert report["evaluation_consistency"]["status"] == "NOT_ASSESSED"


def test_model_without_predict_proba_is_not_assessed_for_s4():
    class NoProba:
        def predict(self, X):
            return np.zeros(len(X))
    res = si.check_component("S4", "model", lambda: NoProba().predict_proba([[0]]), lambda: [0], "Predictions")
    assert res["status"] == "NOT_ASSESSED"


# 9 ── Unavailable validation evidence ───────────────────────────────────────

def test_missing_split_evidence_is_not_assessed():
    result = {"success": True, "metrics": {"roc_auc": 0.7, "gini": 0.4, "ks": 0.3}, "seed_aucs": [], "ablation": {}, "split_stats": {}}
    r47 = next(c for c in core.evaluate_replication_checks(result, {}, []) if c["id"] == "R4.7")
    assert r47["status"] == "NOT_ASSESSED" and r47["executed"] is False
    assert si.check_disjoint(None, None, None)["status"] == "NOT_ASSESSED"
    assert si.build_r47([si._sub("S1", "x", "PASS", ""), si._sub("S4", "y", "NOT_ASSESSED", "")])["status"] == "NOT_ASSESSED"


def test_not_assessed_r47_blocks_the_verdict(client):
    csv = env.to_csv(env.dataset_coefs(6000, [1.2, 0.6, 0.3, 0.0, 0.0], seed=5))
    model_id = env.train(client, csv, "R47 Gate Model")["model_id"]
    run = env.replicate(client, csv, model_id)
    assert "R4.7" in main.MANDATORY_REPLICATION_CHECKS and main.EXCLUDED_REPLICATION_CHECKS == {}
    row = next(r for r in main.persistence.read_log(env.LOG) if r["run_id"] == run["evidence"]["run_id"])
    path = main.persistence.BACKEND_DIR / row["artifact_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    for c in payload["report"]["replication"]["checks"]:
        if c["id"] == "R4.7":
            c.update(si.r47_not_assessed("evidence withheld for test"))
    path.write_text(json.dumps(payload), encoding="utf-8")
    intake = {"model_name": "R47 Gate Model", "registered_model_id": model_id,
              "model_inventory_registered": True, "independence_confirmed": True}
    v = client.post("/validation/stage8/findings",
                    data={"intake_json": json.dumps(intake), "replication_run_id": run["evidence"]["run_id"],
                          "mdd_text": "Platt calibration. IFRS 9 staging. Limitations. Assumptions. GDP."},
                    files={"file": ("c.csv", io.BytesIO(csv), "text/csv")}).json()
    assert v["verdict"] == "INCONCLUSIVE"
    assert any("R4.7" in r for r in v["verdict_basis"]["replication"]["reasons"])


# 10 ── Hardcoded PASS prevention ────────────────────────────────────────────

def test_no_hardcoded_r47_pass_in_source():
    src = Path(core.__file__).read_text(encoding="utf-8")
    assert not re.search(r'"id":\s*"R4\.7"[^}]*"status":\s*"PASS"', src)


def test_same_population_psi_is_not_reported_as_pass():
    fit = _fit()
    psi = stress.compute_psi_stability(fit["pipeline"], fit["X_train"], fit["y_proba"], X_test=fit["X_test"], val_df=DF)
    assert psi["check"]["status"] == "NOT_ASSESSED" and psi["psi_total"] is None
    assert psi["same_population_psi"] is not None


def test_psi_is_assessed_over_time_when_dates_exist():
    df = DF.copy()
    df["application_date"] = pd.date_range("2020-01-01", periods=len(df), freq="D")
    fit = core._fit_core(df, "default", "Logistic Regression", 0.15, 0.15, 42, 3)
    psi = stress.compute_psi_stability(fit["pipeline"], fit["X_train"], fit["y_proba"], X_test=fit["X_test"], val_df=df)
    assert psi["check"]["status"] in ("PASS", "WARN", "FAIL") and "earlier" in psi["comparison"]


def test_stress_scenarios_never_fake_a_result():
    fit = _fit()
    scen = stress.run_all_macro_scenarios(fit["pipeline"], fit["X_test"], fit["y_proba"])["scenarios"]
    by_id = {s["id"]: s for s in scen}
    assert by_id["6.2a"]["status"] == "NOT_APPLICABLE" and by_id["6.2a"]["scn_pd"] is None
    assert by_id["6.2c"]["status"] == "OVERLAY_ONLY"
    assert by_id["6.2c"]["model_response_pd"] == pytest.approx(by_id["6.2c"]["base_pd"])


def test_stress_driver_mapping_and_units():
    drivers = stress.detect_driver_columns(pd.DataFrame({"debt_to_income": [0.1], "annual_income": [1.0], "unemployment_rate": [0.05]}))
    assert drivers["income"] == "annual_income"
    pipe = LogisticRegression().fit(np.array([[0.0], [1.0]]), [0, 1])
    X = pd.DataFrame({"unemployment_rate": [0.05, 0.06]})

    class Recorder:
        def predict_proba(self, frame):
            Recorder.seen = frame.copy()
            return pipe.predict_proba(frame[["unemployment_rate"]].to_numpy())
    stress.apply_macro_scenario(Recorder(), X, [0.5, 0.5], stress.MACRO_SCENARIOS[0])
    assert Recorder.seen["unemployment_rate"].tolist() == pytest.approx([0.08, 0.09])   # +3pp on a fraction scale


def test_regulatory_keywords_need_real_evidence():
    mdd = "Applications that decline are excluded. This model manages credit risk for 12 month horizons."
    rep = ValidationAgent2().run_all_checks(None, {}, mdd)
    s7 = {f["check_id"]: f for f in rep["findings_by_stage"]["Stage 7: Regulatory Compliance"]}
    assert s7["7.2"]["status"] == "FAIL" and s7["7.3"]["status"] == "FAIL" and s7["7.4"]["status"] == "FAIL"
    assert "Documented in MDD" in s7["7.2"]["title"] and "Documented in MDD" in s7["7.4"]["title"]
    good = ValidationAgent2().run_all_checks(None, {}, "IFRS 9 staging with SICR backstop at 30 dpd. Lifetime ECL by stage.")
    good7 = {f["check_id"]: f["status"] for f in good["findings_by_stage"]["Stage 7: Regulatory Compliance"]}
    assert good7["7.2"] == good7["7.3"] == good7["7.4"] == "PASS"


def test_feature_relevance_has_no_surrogate_model():
    payload = main._derive_feature_importance_payload({}, df=DF, model_file=None, intake={})
    assert payload["importance_df"] is None and payload["importance_source"] == "unavailable"


def test_llm_failure_and_skip_are_not_findings(monkeypatch):
    import source_agent2
    agent = main._load_source_agent2()
    assert agent is not None
    skipped = agent.check_documents_with_llm({}, stage="conceptual_soundness", skip_reason="queued")
    assert skipped and all(f["status"] == "PENDING" and f["execution_status"] == "skipped" and f["observed"] == "queued" for f in skipped)

    def boom(prompt):
        raise source_agent2.LLMProviderError("both providers down")
    monkeypatch.setattr(source_agent2, "complete_with_fallback", boom)
    failed = agent.check_documents_with_llm({"MDD": "some text"}, stage="conceptual_soundness")
    assert failed and all(f["status"] == "NOT_ASSESSED" and f["execution_status"] == "failed" for f in failed)
