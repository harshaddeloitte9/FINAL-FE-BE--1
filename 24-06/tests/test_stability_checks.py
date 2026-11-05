"""Regression tests for the redesigned R4.5 (feature stability) and R4.6
(predictive performance stability). Phase 4 isolated environment.

Integration tests train real models through the replication path; the
evaluator tests feed the decision functions explicit per-run evidence to pin
down each decision rule (they test the rules, they do not stand in for model
output anywhere in the application).
"""
import json

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

import _aegis_test_env as env
import stability_checks as stability
import val_replication_core as core

SEEDS = [42, 43, 44, 45, 46]
CRITERIA = stability.load_criteria()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("stability_checks")) as c:
        yield c


def replicate(df, algorithm="Logistic Regression", params=None, seeds=SEEDS):
    res = core.run_replication(df, "default", algorithm, 0.15, 0.15, 42, 3, {}, seeds,
                               compute_split_integrity=False, model_params=params)
    checks = {c["id"]: c for c in core.evaluate_replication_checks(res, {}, seeds)}
    return res, checks["R4.5"], checks["R4.6"]


def run(seed, importance, selected=None, direction=None, auc=0.75, se=0.015, pos=150, neg=600):
    """Explicit per-run evidence for the evaluator tests."""
    return {"seed": seed, "status": "COMPLETED", "auc": auc, "auc_se": se, "auc_ci": [auc - 2 * se, auc + 2 * se],
            "test_rows": pos + neg, "test_positives": pos, "test_negatives": neg,
            "importance": importance, "importance_sd": {k: 0.001 for k in importance},
            "selected": selected if selected is not None else [k for k, v in importance.items() if v > 0.01],
            "direction": direction or {k: {"sign": 1, "delta_pd": 0.01} for k in importance}, "model_inputs": list(importance)}


@pytest.fixture(scope="module")
def ordered():
    return replicate(env.dataset_coefs(6000, [1.2, 0.6, 0.3, 0.0, 0.0], seed=5))


# 1 ── Stable feature rankings ───────────────────────────────────────────────

def test_stable_rankings_pass(ordered):
    _, r45, _ = ordered
    assert r45["status"] == "PASS", r45["_explanation"]
    assert r45["_runs_completed"] == 5 and r45["_mean_rank_correlation"] >= CRITERIA["r45"]["min_mean_rank_correlation"]
    assert set(r45["_material_features"]) == {"f0", "f1", "f2"}
    top = {r["feature"]: r for r in r45["_feature_stability"]}
    assert top["f0"]["top1_share"] == 1.0 and top["f0"]["direction"] == "+" and top["f0"]["direction_consistency"] == 1.0
    assert top["f3"]["material"] is False                   # no-effect feature is not material


# 2 ── Unstable feature rankings ─────────────────────────────────────────────

def test_direction_flip_fails():
    flip = {"a": {"sign": -1, "delta_pd": -0.01}, "b": {"sign": 1, "delta_pd": 0.01}}
    runs = [run(s, {"a": 0.10, "b": 0.05}, direction=flip if s % 2 else None) for s in range(5)]
    r45 = stability.feature_stability(runs, CRITERIA)
    assert r45["status"] == "FAIL" and "direction is inconsistent for a" in r45["_explanation"]


def test_driver_dropout_fails():
    imp = {"a": 0.10, "b": 0.06, "c": 0.04, "d": 0.03, "e": 0.02}
    runs = [run(s, dict(imp)) for s in range(4)]
    swapped = dict(imp, a=0.0005)                           # the top driver contributes nothing in this run
    runs.append(run(4, swapped, selected=[k for k in swapped if swapped[k] > 0.01]))
    r45 = stability.feature_stability(runs, CRITERIA)
    assert r45["status"] == "FAIL" and r45["_driver_dropouts"][0]["feature"] == "a"


def test_reversal_of_significantly_different_features_fails():
    runs = [run(s, {"a": 0.20 + 0.001 * s, "b": 0.10, "c": 0.05}) for s in range(7)]
    # a is clearly ahead overall (significant difference) yet falls behind b in
    # 3/10 runs. Large reversals would make the pair statistically tied instead.
    runs += [run(s, {"a": 0.098, "b": 0.10, "c": 0.05}) for s in (7, 8, 9)]
    r45 = stability.feature_stability(runs, CRITERIA)
    assert r45["status"] == "FAIL" and r45["_reversed_pairs"][0]["higher"] == "a"


def test_tied_features_swapping_is_a_warning_not_a_failure():
    _, r45, _ = replicate(env.dataset_coefs(6000, [0.3] * 8, seed=2))
    assert r45["status"] == "WARN", r45["_explanation"]
    assert "statistically tied" in r45["_explanation"]


# 3 ── Strong but stable predictors ──────────────────────────────────────────

def test_strong_stable_predictor_passes_r45():
    res, r45, _ = replicate(env.dataset_coefs(6000, [2.0, 0.3, 0.2, 0.0, 0.0], seed=3))
    drop = {r["feature"]: r["auc_drop"] for r in res["ablation_runs"]}
    assert drop["f0"] > 0.05                                 # the old R4.5 rule would have failed here
    assert r45["status"] == "PASS", r45["_explanation"]
    assert r45["_top1_by_run"] == ["f0"] * 5


# 4 ── Features that improve AUC when removed ────────────────────────────────

def test_removal_improvement_is_a_separate_diagnostic():
    ablation = [{"feature": "noise", "status": "COMPLETED", "auc_drop": -0.05},
                {"feature": "a", "status": "COMPLETED", "auc_drop": 0.10}]
    diag = stability.removal_diagnostics(ablation, baseline_se=0.01, criteria=CRITERIA)
    assert diag["features_improving_auc_when_removed"] == [{"feature": "noise", "auc_gain_when_removed": 0.05}]
    runs = [run(s, {"a": 0.10, "b": 0.05}) for s in range(5)]
    without = stability.feature_stability(runs, CRITERIA)
    with_diag = stability.feature_stability(runs, CRITERIA, removal=diag)
    assert without["status"] == with_diag["status"] == "PASS"   # reported, not a failure
    assert with_diag["_removal_diagnostics"]["features_improving_auc_when_removed"]


def test_small_improvement_within_noise_is_not_flagged():
    diag = stability.removal_diagnostics([{"feature": "x", "status": "COMPLETED", "auc_drop": -0.005}], 0.01, CRITERIA)
    assert diag["features_improving_auc_when_removed"] == []


# 5 ── Stable model performance across runs ──────────────────────────────────

def test_stable_performance_passes(ordered):
    res, _, r46 = ordered
    assert r46["status"] == "PASS", r46["_explanation"]
    het = r46["_heterogeneity"]
    assert het["p_value"] >= CRITERIA["r46"]["alpha"] and het["df"] == 4
    main = r46["_main_evaluation"]
    assert main["ci_low"] <= main["auc"] <= main["ci_high"]
    s = r46["_summary"]
    aucs = [r["auc"] for r in res["seed_runs"]]
    assert (s["min"], s["max"]) == (min(aucs), max(aucs))


# 6 ── Unstable performance across runs ──────────────────────────────────────

def test_performance_deterioration_over_time_fails():
    _, _, r46 = replicate(env.dataset_coefs(6000, [0.8, 0.5, 0.3], seed=9, drift_after=0.6))
    assert r46["status"] == "FAIL", r46["_explanation"]
    assert r46["_temporal"]["available"] and r46["_deteriorated_periods"]
    assert all(p["start"] >= "2021" for p in r46["_deteriorated_periods"])   # the drifted (later) period


def test_excess_run_variation_fails_heterogeneity():
    runs = [run(s, {"a": 0.1}, auc=a, se=0.01) for s, a in enumerate([0.62, 0.70, 0.78, 0.66, 0.74])]
    main = stability.stratified_bootstrap_auc(np.r_[np.zeros(400), np.ones(100)], np.r_[np.linspace(0, .8, 400), np.linspace(.2, 1, 100)],
                                              500, 1)
    r46 = stability.performance_stability(runs, main, {"available": False, "reason": "none"}, CRITERIA)
    assert r46["status"] == "FAIL" and r46["_heterogeneity"]["p_value"] < 0.05 and r46["_heterogeneity"]["I2"] > 0.5


# 7 ── Different sample sizes ────────────────────────────────────────────────

def test_interval_narrows_with_sample_size():
    rng = np.random.default_rng(0)

    def ci_width(n):
        y = (rng.uniform(size=n) < 0.25).astype(int)
        p = np.clip(0.25 + 0.3 * (y - 0.25) + rng.normal(0, 0.2, n), 0, 1)
        b = stability.stratified_bootstrap_auc(y, p, 500, 7)
        return b["ci_high"] - b["ci_low"], b
    small, b_small = ci_width(400)
    large, b_large = ci_width(6400)
    assert large < small / 2.5                                # ≈ 1/sqrt(16) scaling
    assert b_small["rows"] == 400 and b_large["rows"] == 6400
    assert b_small["positives"] + b_small["negatives"] == 400


def test_runs_record_sample_size_and_class_balance(ordered):
    res, _, r46 = ordered
    for r in r46["_runs"]:
        assert r["test_rows"] == r["test_positives"] + r["test_negatives"] == 900


# 8 ── Bootstrap confidence intervals ────────────────────────────────────────

def test_bootstrap_interval_is_correct_and_reproducible():
    rng = np.random.default_rng(1)
    y = (rng.uniform(size=1500) < 0.2).astype(int)
    p = np.clip(0.2 + 0.25 * (y - 0.2) + rng.normal(0, 0.15, 1500), 0, 1)
    a = stability.stratified_bootstrap_auc(y, p, 1000, 99)
    b = stability.stratified_bootstrap_auc(y, p, 1000, 99)
    assert a == b                                                         # fixed seed → identical
    assert stability.auc_score(y, p) == pytest.approx(roc_auc_score(y, p))
    assert a["ci_low"] < a["auc"] < a["ci_high"]
    auc, n1, n0 = a["auc"], y.sum(), len(y) - y.sum()
    q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
    hanley = np.sqrt((auc * (1 - auc) + (n1 - 1) * (q1 - auc ** 2) + (n0 - 1) * (q2 - auc ** 2)) / (n1 * n0))
    assert a["se"] == pytest.approx(hanley, rel=0.3)                      # agrees with the analytic SE


def test_single_class_sample_has_no_interval():
    b = stability.stratified_bootstrap_auc(np.zeros(50), np.linspace(0, 1, 50), 100, 1)
    assert b["available"] is False


# 9 ── Insufficient sample size ──────────────────────────────────────────────

def test_insufficient_sample_is_not_assessed():
    _, r45, r46 = replicate(env.dataset_coefs(300, [0.6, 0.3, 0.1], seed=5))
    assert r45["status"] == "NOT_ASSESSED" and r46["status"] == "NOT_ASSESSED"
    assert "too imprecise" in r46["observed"] or "at least" in r46["observed"]


def test_too_few_events_is_not_assessed():
    runs = [run(s, {"a": 0.1}, pos=5, neg=200) for s in range(5)]
    main = {"available": True, "auc": 0.7, "se": 0.05, "ci_low": 0.6, "ci_high": 0.75, "rows": 205,
            "positives": 5, "negatives": 200, "confidence_level": 0.95}
    r46 = stability.performance_stability(runs, main, None, CRITERIA)
    assert r46["status"] == "NOT_ASSESSED" and "5 defaults" in r46["observed"]
    assert stability.feature_stability(runs, CRITERIA)["status"] == "NOT_ASSESSED"


# 10 ── Missing evaluation evidence ──────────────────────────────────────────

def test_missing_evidence_is_not_assessed():
    result = {"success": True, "metrics": {"roc_auc": 0.7, "gini": 0.4, "ks": 0.3}, "seed_aucs": [], "ablation": {}, "split_stats": {}}
    checks = {c["id"]: c for c in core.evaluate_replication_checks(result, {}, [])}
    assert checks["R4.5"]["status"] == checks["R4.6"]["status"] == "NOT_ASSESSED"
    assert stability.performance_stability([run(s, {"a": 0.1}) for s in range(5)], None, None, CRITERIA)["status"] == "NOT_ASSESSED"
    two_runs = [run(0, {"a": 0.1, "b": 0.05}), {"seed": 1, "status": "FAILED", "error": "x"}, run(2, {"a": 0.1, "b": 0.05})]
    assert stability.feature_stability(two_runs, CRITERIA)["status"] == "NOT_ASSESSED"


# 11 ── Non-deterministic execution ──────────────────────────────────────────

def test_nondeterministic_training_is_flagged():
    res, r45, r46 = replicate(env.dataset_coefs(3000, [0.8, 0.5, 0.3, 0.1], seed=7), algorithm="Random Forest",
                              params={"random_state": None, "n_estimators": 40})
    det = res["stability"]["determinism"]
    assert det["assessed"] and det["deterministic"] is False
    for check in (r45, r46):
        assert check["status"] != "PASS"
        assert any("not deterministic" in l for l in check["_limitations"])


def test_deterministic_training_is_confirmed(ordered):
    assert ordered[0]["stability"]["determinism"]["deterministic"] is True


# ── Registered reproduction, criteria provenance, verdict wiring ───────────

def test_registered_reproduction_produces_stability_evidence(client):
    csv = env.to_csv(env.dataset_coefs(4000, [1.0, 0.5, 0.2, 0.0], seed=11))
    model_id = env.train(client, csv, "Stability Registered Model")["model_id"]
    checks = {c["id"]: c for c in env.replicate(client, csv, model_id)["report"]["replication"]["checks"]}
    for cid in ("R4.5", "R4.6"):
        assert checks[cid]["_runs_completed"] >= CRITERIA["runs"]["min_completed_runs"]
        assert checks[cid]["_methodology"] and checks[cid]["_diagnostic_note"]
    assert checks["R4.6"]["_main_evaluation"]["available"]


def test_provisional_criteria_are_disclosed(ordered):
    raw = json.loads(stability.CRITERIA_PATH.read_text(encoding="utf-8"))
    assert raw["approved"] is False
    for check in ordered[1:]:
        assert any("PROVISIONAL" in l for l in check["_limitations"])
    assert "0.02" not in ordered[2]["threshold"]                  # no universal AUC-spread threshold
