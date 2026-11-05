"""
stability_checks.py — R4.5 (feature stability) and R4.6 (predictive
performance stability), redesigned after the methodology review
(R4_5_R4_6_METHODOLOGY_REVIEW.md).

Evidence comes from repeated runs: each run is a fresh stratified re-split
and a retrain with the model's own configuration (the registered model's
recorded configuration for a registered reproduction). For every run this
module measures, on that run's held-out rows:
  * ROC-AUC and its stratified-bootstrap standard error,
  * permutation importance of every model input (AUC drop when the column is
    shuffled; repeated, giving a within-run standard error) — model-agnostic,
    so it means the same thing for every algorithm,
  * the direction of each numeric feature's effect: the average change in
    predicted PD when the feature is raised by one training-set SD.

R4.5 judges whether importance RANKINGS and DIRECTIONS agree across runs,
among material features only (a strong predictor that is consistently
strong is stable; shuffling among features that contribute nothing is noise,
not instability). R4.6 separates ordinary sampling variation from genuine
instability with a heterogeneity test (Cochran's Q / I²) and tests runs and
time periods for significant deterioration. All acceptance criteria come from
config/stability_criteria.json. Insufficient evidence → NOT_ASSESSED.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm, rankdata, spearmanr, ttest_1samp

CRITERIA_PATH = Path(__file__).resolve().parent / "config" / "stability_criteria.json"
DETERMINISM_TOLERANCE = 1e-9

R45_METHODOLOGY = (
    "Repeated stratified re-split + retrain with the model's configuration. Per run: permutation importance "
    "of every input on held-out rows (AUC drop when shuffled) and the direction of each numeric feature's "
    "effect on predicted PD. Stability = agreement of importance ranks (Spearman) and directions across runs, "
    "judged among material features (selected in at least half of the runs)."
)
R46_METHODOLOGY = (
    "Repeated stratified re-split + retrain with the model's configuration. Per run: held-out ROC-AUC with a "
    "stratified-bootstrap standard error. Run-to-run variation is compared with sampling error (Cochran's Q "
    "heterogeneity test, I²); each run is tested for significant deterioration against the pooled AUC and each "
    "chronological period against the overall test AUC (one-sided, Bonferroni-corrected); the model's test AUC "
    "gets a stratified-bootstrap confidence interval."
)
DIAGNOSTIC_NOTE = "Statistical diagnostic of model behaviour — not a regulatory approval."


# ── Criteria ────────────────────────────────────────────────────────────────

def load_criteria(path: Optional[Path] = None) -> Dict[str, Any]:
    raw = json.loads(Path(path or CRITERIA_PATH).read_text(encoding="utf-8"))

    def values(section: str) -> Dict[str, Any]:
        return {k: v["value"] for k, v in raw.get(section, {}).items() if isinstance(v, dict) and "value" in v}

    policy_keys = [f"{s}.{k}" for s in ("repeated_runs", "r4_5_feature_stability", "r4_6_performance_stability")
                   for k, v in raw.get(s, {}).items() if isinstance(v, dict) and v.get("kind") == "policy"]
    return {
        "runs": values("repeated_runs"),
        "r45": values("r4_5_feature_stability"),
        "r46": values("r4_6_performance_stability"),
        "approved": bool(raw.get("approved")),
        "approved_by": raw.get("approved_by"),
        "policy_keys": policy_keys,
        "source": str(Path(path or CRITERIA_PATH).name),
    }


def _criteria_note(criteria: Dict[str, Any]) -> str:
    if criteria.get("approved"):
        return f"Acceptance criteria approved by {criteria.get('approved_by') or 'Model Risk'} ({criteria['source']})."
    return (f"Acceptance criteria are PROVISIONAL defaults ({criteria['source']}); the policy values "
            f"({', '.join(k.split('.')[-1] for k in criteria['policy_keys'])}) await Model Risk approval.")


# ── Primitive measurements ─────────────────────────────────────────────────

def auc_score(y: np.ndarray, p: np.ndarray) -> float:
    """Mann-Whitney ROC-AUC (ties count half) — identical to roc_auc_score."""
    y = np.asarray(y).astype(int)
    ranks = rankdata(np.asarray(p, dtype=float))
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def stratified_bootstrap_auc(y, p, iterations: int, seed: int, level: float = 0.95) -> Dict[str, Any]:
    """Resample defaults and non-defaults separately (so every resample keeps
    the sample's class balance) and recompute AUC; percentile interval."""
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    base = {"rows": int(len(y)), "positives": int(len(pos)), "negatives": int(len(neg)), "iterations": int(iterations)}
    if len(pos) == 0 or len(neg) == 0:
        return {**base, "available": False, "reason": "Evaluation sample contains only one class."}
    rng = np.random.default_rng(seed)
    samples = np.empty(int(iterations))
    for i in range(int(iterations)):
        idx = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
        samples[i] = auc_score(y[idx], p[idx])
    tail = (1 - level) / 2
    return {
        **base, "available": True, "auc": auc_score(y, p), "se": float(np.std(samples, ddof=1)),
        "ci_low": float(np.quantile(samples, tail)), "ci_high": float(np.quantile(samples, 1 - tail)),
        "confidence_level": level,
    }


def permutation_importance(pipeline, X: pd.DataFrame, y, repeats: int, seed: int):
    y = np.asarray(y).astype(int)
    base = auc_score(y, pipeline.predict_proba(X)[:, 1])
    rng = np.random.default_rng(seed)
    mean, sd = {}, {}
    for col in X.columns:
        drops = []
        for _ in range(int(repeats)):
            shuffled = X.copy()
            shuffled[col] = rng.permutation(shuffled[col].to_numpy())
            drops.append(base - auc_score(y, pipeline.predict_proba(shuffled)[:, 1]))
        mean[str(col)] = float(np.mean(drops))
        sd[str(col)] = float(np.std(drops, ddof=1)) if len(drops) > 1 else 0.0
    return mean, sd


def direction_effects(pipeline, X_eval: pd.DataFrame, X_reference: pd.DataFrame) -> Dict[str, Optional[Dict[str, float]]]:
    """Average change in predicted PD when a numeric feature is raised by one
    training-set SD. Not meaningful for categorical / binary inputs → None."""
    p0 = pipeline.predict_proba(X_eval)[:, 1]
    out: Dict[str, Optional[Dict[str, float]]] = {}
    for col in X_eval.columns:
        series = X_reference[col] if col in X_reference.columns else X_eval[col]
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series) or series.nunique(dropna=True) <= 2:
            out[str(col)] = None
            continue
        sd = float(series.std())
        if not np.isfinite(sd) or sd == 0:
            out[str(col)] = None
            continue
        shifted = X_eval.copy()
        shifted[col] = shifted[col] + sd
        delta = float(np.nanmean(pipeline.predict_proba(shifted)[:, 1] - p0))
        out[str(col)] = {"delta_pd": delta, "sign": 0 if abs(delta) < 1e-6 else int(np.sign(delta))}
    return out


# ── One repeated run ───────────────────────────────────────────────────────

def evaluate_run(seed: int, pipeline, X_train: pd.DataFrame, X_test: pd.DataFrame, y_test, criteria: Dict[str, Any]) -> Dict[str, Any]:
    r45, r46 = criteria["r45"], criteria["r46"]
    y = np.asarray(y_test).astype(int)
    p = pipeline.predict_proba(X_test)[:, 1]
    boot = stratified_bootstrap_auc(y, p, r46["per_run_bootstrap_iterations"], int(r46["bootstrap_seed"]) + int(seed),
                                    float(r46["confidence_level"]))
    if not boot["available"]:
        raise ValueError(boot["reason"])
    imp, imp_sd = permutation_importance(pipeline, X_test, y, r45["permutation_repeats"], int(r46["bootstrap_seed"]) + int(seed))
    z = float(r45["importance_significance_z"])
    se_factor = 1 / math.sqrt(max(int(r45["permutation_repeats"]), 1))
    selected = [f for f, m in imp.items() if m > 0 and m > z * imp_sd[f] * se_factor]
    return {
        "seed": seed, "status": "COMPLETED",
        "auc": round(boot["auc"], 4), "auc_se": round(boot["se"], 5),
        "auc_ci": [round(boot["ci_low"], 4), round(boot["ci_high"], 4)],
        "test_rows": boot["rows"], "test_positives": boot["positives"], "test_negatives": boot["negatives"],
        "importance": {k: round(v, 6) for k, v in imp.items()},
        "importance_sd": {k: round(v, 6) for k, v in imp_sd.items()},
        "selected": selected,
        "direction": direction_effects(pipeline, X_test, X_train),
        "model_inputs": [str(c) for c in X_test.columns],
    }


def failed_run(seed: int, exc: BaseException) -> Dict[str, Any]:
    return {"seed": seed, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}


def determinism_check(first: Optional[Dict[str, Any]], repeat: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Repeat one run with the same seed: identical AUC and importances →
    deterministic. Different → the training procedure is not reproducible, so
    run-to-run variation also contains training randomness."""
    if not first or not repeat or first.get("status") != "COMPLETED" or repeat.get("status") != "COMPLETED":
        return {"assessed": False, "deterministic": None, "detail": "Repeat execution unavailable — determinism not assessed."}
    keys = set(first["importance"]) | set(repeat["importance"])
    max_diff = max([abs(first["auc"] - repeat["auc"])] +
                   [abs(first["importance"].get(k, 0.0) - repeat["importance"].get(k, 0.0)) for k in keys])
    same = max_diff <= DETERMINISM_TOLERANCE
    return {
        "assessed": True, "deterministic": same, "seed": first["seed"], "max_abs_difference": max_diff,
        "detail": (f"Repeating seed {first['seed']} reproduced the run exactly."
                   if same else f"Repeating seed {first['seed']} gave different results (max difference {max_diff:.6f}): "
                                "training is not deterministic, so run-to-run variation includes training randomness."),
    }


def temporal_performance(y, p, dates, criteria: Dict[str, Any]) -> Dict[str, Any]:
    """AUC per chronological, equal-count period of the model's test rows,
    each tested for significant deterioration against the overall test AUC."""
    r46 = criteria["r46"]
    if dates is None:
        return {"available": False, "reason": "No date information in the evaluation data."}
    frame = pd.DataFrame({"date": pd.to_datetime(pd.Series(np.asarray(dates)), errors="coerce"),
                          "y": np.asarray(y).astype(int), "p": np.asarray(p, dtype=float)}).dropna(subset=["date"]).sort_values("date")
    if frame["date"].nunique() < 2:
        return {"available": False, "reason": "Fewer than two distinct dates in the evaluation data."}
    min_cc = int(r46["min_class_count"])
    chunks = None
    for n in range(int(r46["temporal_max_periods"]), 1, -1):
        parts = [frame.iloc[pos] for pos in np.array_split(np.arange(len(frame)), n)]
        if all(int(c["y"].sum()) >= min_cc and int((1 - c["y"]).sum()) >= min_cc for c in parts):
            chunks = parts
            break
    if chunks is None:
        return {"available": False, "reason": f"Too few defaults to form two periods with at least {min_cc} of each class."}
    seed = int(r46["bootstrap_seed"])
    overall = stratified_bootstrap_auc(frame["y"], frame["p"], r46["per_run_bootstrap_iterations"], seed, float(r46["confidence_level"]))
    # Bonferroni: one test per period, so the family-wise false-alarm rate
    # stays at alpha rather than growing with the number of periods.
    z_crit = float(norm.ppf(1 - float(r46["alpha"]) / len(chunks)))
    periods = []
    for i, c in enumerate(chunks):
        b = stratified_bootstrap_auc(c["y"], c["p"], r46["per_run_bootstrap_iterations"], seed + 100 + i, float(r46["confidence_level"]))
        z = (overall["auc"] - b["auc"]) / math.sqrt(overall["se"] ** 2 + b["se"] ** 2) if (overall["se"] or b["se"]) else 0.0
        periods.append({
            "start": str(c["date"].iloc[0].date()), "end": str(c["date"].iloc[-1].date()),
            "rows": b["rows"], "positives": b["positives"], "negatives": b["negatives"],
            "auc": round(b["auc"], 4), "se": round(b["se"], 5), "ci": [round(b["ci_low"], 4), round(b["ci_high"], 4)],
            "z_vs_overall": round(z, 3), "deteriorated": bool(z > z_crit),
        })
    return {"available": True, "overall_auc": round(overall["auc"], 4), "periods": periods,
            "test": f"one-sided z-test of each period vs the overall test AUC, alpha={r46['alpha']} Bonferroni-corrected over {len(chunks)} periods"}


# ── R4.5 — feature stability ───────────────────────────────────────────────

def _check(cid: str, title: str, status: str, observed: str, threshold: str, **extra) -> Dict[str, Any]:
    return {"id": cid, "title": title, "severity": "medium", "status": status, "observed": observed,
            "threshold": threshold, "executed": status != "NOT_ASSESSED", "_diagnostic_note": DIAGNOSTIC_NOTE, **extra}


def removal_diagnostics(ablation_runs: List[Dict[str, Any]], baseline_se: Optional[float], criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Features whose removal raises AUC beyond sampling error. Reported
    separately; does NOT change R4.5's status."""
    completed = [r for r in ablation_runs or [] if r.get("status") == "COMPLETED"]
    failed = [r for r in ablation_runs or [] if r.get("status") != "COMPLETED"]
    if not completed:
        return {"available": False, "reason": "No feature-removal retrains completed.", "failed": failed}
    z = float(criteria["r45"]["removal_improvement_z"])
    margin = z * baseline_se if baseline_se else None
    improving = []
    for r in completed:
        gain = -float(r["auc_drop"])
        if gain > 0 and (margin is None or gain > margin):
            improving.append({"feature": r["feature"], "auc_gain_when_removed": round(gain, 4)})
    return {
        "available": True, "features_improving_auc_when_removed": improving,
        "margin_used": round(margin, 5) if margin else None,
        "rule": (f"AUC gain on removal > {z} × bootstrap SE of the baseline AUC" if margin else "AUC gain on removal > 0 (no SE available)"),
        "failed": failed,
        "note": "Diagnostic only: removing a feature and seeing AUC rise suggests noise or over-fitting; it is not by itself evidence of feature instability.",
    }


def feature_stability(runs: List[Dict[str, Any]], criteria: Dict[str, Any], determinism: Optional[Dict[str, Any]] = None,
                      removal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r45 = criteria["r45"]
    alpha = float(criteria["r46"]["alpha"])
    title = "Feature stability across repeated runs"
    threshold = (f"FAIL if a material numeric feature's effect direction agrees in < {r45['min_direction_consistency']} of runs; "
                 f"if two material features whose importances differ significantly (Bonferroni-corrected t-test) swap order in > "
                 f"{1 - float(r45['min_pair_order_consistency']):.0%} of runs; or if a top-{r45['top_k']} driver of one run makes no "
                 f"significant contribution in another (driver dropout). Mean Spearman of material-feature ranks < "
                 f"{r45['min_mean_rank_correlation']} without those conditions (swaps among statistically tied features) is a WARN.")
    min_cc = int(criteria["r46"]["min_class_count"])
    max_ci_width = float(criteria["r46"]["max_ci_width"])
    all_completed = [r for r in runs if r.get("status") == "COMPLETED"]
    # Same evidence-adequacy rules as R4.6: enough of each class, and a run
    # AUC precise enough that its importances are not dominated by noise.
    completed = [r for r in all_completed
                 if r["test_positives"] >= min_cc and r["test_negatives"] >= min_cc
                 and (not r.get("auc_ci") or (r["auc_ci"][1] - r["auc_ci"][0]) <= max_ci_width)]
    too_small = [r for r in all_completed if r not in completed]
    failed = [r for r in runs if r.get("status") != "COMPLETED"]
    limitations = [_criteria_note(criteria)]
    if failed:
        limitations.append(f"{len(failed)} run(s) failed: " + "; ".join(f"seed {r.get('seed')}: {r.get('error')}" for r in failed))
    if too_small:
        limitations.append(f"{len(too_small)} run(s) excluded: evaluation sample too small (fewer than {min_cc} of a class, "
                           f"or AUC interval wider than {max_ci_width}), so importances are too noisy to compare.")
    limitations.append("Permutation importances are estimated on each run's held-out rows; smaller samples give noisier "
                       "importances, which shows up as larger dispersion across runs.")
    base_extra = {"_methodology": R45_METHODOLOGY, "_runs_completed": len(completed), "_runs_failed": len(failed),
                  "_limitations": limitations, "_removal_diagnostics": removal}
    min_runs = int(criteria["runs"]["min_completed_runs"])
    if len(completed) < min_runs:
        return _check("R4.5", title, "NOT_ASSESSED",
                      f"Only {len(completed)} of {len(runs)} repeated run(s) completed with an adequate evaluation sample; "
                      f"at least {min_runs} are needed.", threshold, **base_extra)

    features = sorted({f for r in completed for f in r["importance"]})
    matrix = np.array([[r["importance"].get(f, 0.0) for f in features] for r in completed])
    selection_share = {f: float(np.mean([f in r["selected"] for r in completed])) for f in features}
    material = [f for f in features if selection_share[f] >= float(r45["material_feature_min_selection_share"])]
    if not material:
        return _check("R4.5", title, "NOT_ASSESSED",
                      "No feature made a material contribution (significant permutation importance) in a majority of runs.",
                      threshold, **base_extra)

    idx = [features.index(f) for f in material]
    ranks = np.array([rankdata(-row[idx], method="average") for row in matrix])   # 1 = most important
    pair_rho = []
    if len(material) >= 2:
        for i in range(len(completed)):
            for j in range(i + 1, len(completed)):
                rho = spearmanr(ranks[i], ranks[j]).statistic if len(material) > 2 else (1.0 if np.array_equal(ranks[i], ranks[j]) else -1.0)
                pair_rho.append(float(rho) if np.isfinite(rho) else 1.0)
    mean_rho = float(np.mean(pair_rho)) if pair_rho else None
    min_rho = float(np.min(pair_rho)) if pair_rho else None

    shift_thr = max(int(r45["material_rank_shift_min"]), math.ceil(float(r45["material_rank_shift_fraction"]) * len(material)))
    k = int(r45["top_k"])
    top1 = [features[int(np.argmax(row))] for row in matrix]
    table = []
    direction_flips = []
    material_shifts = []
    for f in features:
        col = matrix[:, features.index(f)]
        row = {
            "feature": f, "material": f in material, "selection_share": round(selection_share[f], 3),
            "importance_mean": round(float(col.mean()), 5), "importance_sd": round(float(col.std(ddof=1)), 5),
            "top1_share": round(top1.count(f) / len(completed), 3),
            "top_k_share": round(float(np.mean([f in [features[t] for t in np.argsort(-r)[:k]] for r in matrix])), 3),
        }
        if f in material:
            fr = ranks[:, material.index(f)]
            row.update({"rank_mean": round(float(fr.mean()), 2), "rank_min": float(fr.min()), "rank_max": float(fr.max()),
                        "rank_range": float(fr.max() - fr.min())})
            if row["rank_range"] >= shift_thr:
                material_shifts.append(f)
            signs = [r["direction"].get(f, {}).get("sign") for r in completed if isinstance(r["direction"].get(f), dict)]
            signs = [s for s in signs if s]
            if signs:
                modal_share = max(signs.count(1), signs.count(-1)) / len(signs)
                row["direction"] = "+" if signs.count(1) >= signs.count(-1) else "-"
                row["direction_consistency"] = round(modal_share, 3)
                if modal_share < float(r45["min_direction_consistency"]):
                    direction_flips.append(f)
            else:
                row["direction"] = None
                row["direction_consistency"] = None
        if f in material and row["importance_mean"] > 0:
            row["importance_cv"] = round(row["importance_sd"] / row["importance_mean"], 3)
        table.append(row)
    table.sort(key=lambda r: -r["importance_mean"])

    # Genuine instability vs statistically tied features. A pair of material
    # features has a definite order when their importance difference across
    # runs is significantly non-zero (one-sample t-test, alpha). Reversals of
    # a definite order are instability; reversals between tied features are
    # expected and only lower the descriptive Spearman correlation.
    # Bonferroni over all material-feature pairs keeps the chance of calling
    # tied features "different" at alpha overall, however many pairs exist.
    definite_pairs, reversed_pairs = [], []
    n_pairs = len(material) * (len(material) - 1) // 2
    pair_alpha = alpha / n_pairs if n_pairs else alpha
    allowed_reversal = 1 - float(r45["min_pair_order_consistency"]) + 1e-9   # tolerance for float rounding
    if len(completed) >= 3:
        for i, a in enumerate(material):
            for b in material[i + 1:]:
                diff = matrix[:, features.index(a)] - matrix[:, features.index(b)]
                if np.allclose(diff, diff[0]):
                    p_val = 0.0 if diff[0] != 0 else 1.0
                else:
                    p_val = float(ttest_1samp(diff, 0.0).pvalue)
                if p_val < pair_alpha:
                    order_sign = np.sign(diff.mean())
                    reversal_share = float(np.mean(np.sign(diff) != order_sign))
                    pair = {"higher": a if order_sign > 0 else b, "lower": b if order_sign > 0 else a,
                            "p_value": round(p_val, 6), "reversal_share": round(reversal_share, 3)}
                    definite_pairs.append(pair)
                    if reversal_share > allowed_reversal:
                        reversed_pairs.append(pair)

    # Driver dropout: a feature that is a top-k driver in one run but makes no
    # significant contribution in another — the signature of a model
    # substituting one driver for another between runs. Only meaningful when
    # there are more material features than k.
    dropouts = []
    if len(material) > k:
        for f in material:
            top_in = [r["seed"] for r, row in zip(completed, matrix) if f in [features[t] for t in np.argsort(-row)[:k]]]
            absent_in = [r["seed"] for r in completed if f not in r["selected"]]
            if top_in and absent_in:
                dropouts.append({"feature": f, "top_driver_in_runs": top_in, "not_significant_in_runs": absent_in})

    reasons_fail, reasons_warn = [], []
    if direction_flips:
        reasons_fail.append("effect direction is inconsistent for " + ", ".join(direction_flips))
    if reversed_pairs:
        reasons_fail.append("significantly different features swap order: "
                            + ", ".join(f"{p['higher']} > {p['lower']} reversed in {p['reversal_share']:.0%} of runs" for p in reversed_pairs))
    if dropouts:
        reasons_fail.append("driver dropout: " + ", ".join(
            f"{d['feature']} is a top-{k} driver in run(s) {d['top_driver_in_runs']} but not significant in {d['not_significant_in_runs']}"
            for d in dropouts))
    if mean_rho is not None and mean_rho < float(r45["min_mean_rank_correlation"]) and not reversed_pairs:
        reasons_warn.append(f"rank agreement is low (mean Spearman {mean_rho:.3f}) but only among features whose importances "
                            "are statistically tied — expected, not instability")
    if material_shifts:
        reasons_warn.append(f"material rank changes (range ≥ {shift_thr} places) for " + ", ".join(material_shifts))
    if failed:
        reasons_warn.append(f"{len(failed)} run(s) failed")
    if too_small:
        reasons_warn.append(f"{len(too_small)} run(s) excluded for sample size")
    if determinism and determinism.get("deterministic") is False:
        reasons_warn.append("training is not deterministic")
        limitations.append(determinism["detail"])

    status = "FAIL" if reasons_fail else "WARN" if reasons_warn else "PASS"
    leader = max(set(top1), key=top1.count)
    observed = (f"{len(completed)} runs; {len(material)} material feature(s); mean pairwise Spearman "
                + (f"{mean_rho:.3f} (min {min_rho:.3f})" if mean_rho is not None else "n/a (one material feature)")
                + f"; top feature '{leader}' in {top1.count(leader)}/{len(completed)} runs.")
    explanation = (
        "Rankings and directions of the material features are consistent across runs."
        if status == "PASS" else
        ("Instability: " + "; ".join(reasons_fail) + (". Also: " + "; ".join(reasons_warn) if reasons_warn else "") + ".")
        if status == "FAIL" else "Consistent overall, but: " + "; ".join(reasons_warn) + "."
    )
    return _check("R4.5", title, status, observed, threshold, **base_extra,
                  _explanation=explanation, _mean_rank_correlation=mean_rho, _min_rank_correlation=min_rho,
                  _material_features=material, _material_rank_shift_threshold=shift_thr,
                  _feature_stability=table, _top1_by_run=top1,
                  _definite_order_pairs=definite_pairs, _reversed_pairs=reversed_pairs, _driver_dropouts=dropouts)


# ── R4.6 — predictive performance stability ────────────────────────────────

def performance_stability(runs: List[Dict[str, Any]], main_eval: Optional[Dict[str, Any]], temporal: Optional[Dict[str, Any]],
                          criteria: Dict[str, Any], determinism: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r46 = criteria["r46"]
    title = "Predictive performance stability across repeated runs"
    threshold = (f"Run-to-run AUC variation not significantly larger than sampling error (Cochran's Q, alpha={r46['alpha']}); "
                 f"no run significantly below the pooled AUC and no period significantly below the overall AUC "
                 f"(one-sided, Bonferroni-corrected)")
    completed = [r for r in runs if r.get("status") == "COMPLETED"]
    failed = [r for r in runs if r.get("status") != "COMPLETED"]
    min_cc = int(r46["min_class_count"])
    eligible = [r for r in completed if r["test_positives"] >= min_cc and r["test_negatives"] >= min_cc and r.get("auc_se", 0) > 0]
    too_small = [r for r in completed if r not in eligible]
    limitations = [_criteria_note(criteria)]
    if failed:
        limitations.append(f"{len(failed)} run(s) failed: " + "; ".join(f"seed {r.get('seed')}: {r.get('error')}" for r in failed))
    if too_small:
        limitations.append(f"{len(too_small)} run(s) excluded: fewer than {min_cc} of a class in the evaluation sample.")
    if temporal and not temporal.get("available"):
        limitations.append(f"Time-based comparison not performed: {temporal.get('reason')}")
    run_table = [{k: r.get(k) for k in ("seed", "status", "auc", "auc_se", "auc_ci", "test_rows", "test_positives", "test_negatives", "error")}
                 for r in runs]
    base_extra = {"_methodology": R46_METHODOLOGY, "_runs": run_table, "_runs_completed": len(eligible),
                  "_runs_failed": len(failed), "_limitations": limitations, "_main_evaluation": main_eval, "_temporal": temporal,
                  # Aligned per-run series for the chart (completed runs only).
                  "_seeds": [r["seed"] for r in completed], "_seed_aucs": [r["auc"] for r in completed]}

    if not main_eval or not main_eval.get("available"):
        return _check("R4.6", title, "NOT_ASSESSED", "The model's own test-set evaluation is unavailable.", threshold, **base_extra)
    if main_eval["positives"] < min_cc or main_eval["negatives"] < min_cc:
        return _check("R4.6", title, "NOT_ASSESSED",
                      f"Test set has {main_eval['positives']} defaults and {main_eval['negatives']} non-defaults; at least {min_cc} of each are needed.",
                      threshold, **base_extra)
    ci_width = main_eval["ci_high"] - main_eval["ci_low"]
    if ci_width > float(r46["max_ci_width"]):
        return _check("R4.6", title, "NOT_ASSESSED",
                      f"AUC {main_eval['auc']:.4f} with {int(main_eval['confidence_level'] * 100)}% CI [{main_eval['ci_low']:.4f}, {main_eval['ci_high']:.4f}] "
                      f"is too imprecise (width {ci_width:.3f} > {r46['max_ci_width']}) to judge stability.", threshold, **base_extra)
    min_runs = int(criteria["runs"]["min_completed_runs"])
    if len(eligible) < min_runs:
        return _check("R4.6", title, "NOT_ASSESSED",
                      f"Only {len(eligible)} usable run(s) of {len(runs)}; at least {min_runs} are needed.", threshold, **base_extra)

    aucs = np.array([r["auc"] for r in eligible], dtype=float)
    ses = np.array([r["auc_se"] for r in eligible], dtype=float)
    w = 1 / ses ** 2
    pooled = float((w * aucs).sum() / w.sum())
    q = float((w * (aucs - pooled) ** 2).sum())
    dof = len(eligible) - 1
    p_value = float(chi2.sf(q, dof))
    i2 = max(0.0, (q - dof) / q) if q > 0 else 0.0
    alpha = float(r46["alpha"])
    # Each run is compared with the pooled (inverse-variance weighted) AUC of
    # all runs — not with any single split, which is itself just one random
    # draw — one-sided, Bonferroni-corrected over the number of runs.
    pooled_se = math.sqrt(1 / w.sum())
    z_crit = float(norm.ppf(1 - alpha / len(eligible)))
    deteriorated_runs = []
    for r in eligible:
        z = (pooled - r["auc"]) / math.sqrt(pooled_se ** 2 + r["auc_se"] ** 2)
        if z > z_crit:
            deteriorated_runs.append({"seed": r["seed"], "auc": r["auc"], "z": round(z, 3)})
    deteriorated_periods = [p for p in (temporal or {}).get("periods", []) if p.get("deteriorated")]

    reasons_fail, reasons_warn = [], []
    if p_value < alpha:
        reasons_fail.append(f"run-to-run AUC variation exceeds sampling error (Q={q:.2f}, df={dof}, p={p_value:.4f}, I²={i2:.0%})")
    if deteriorated_runs:
        reasons_fail.append("significant deterioration in run(s) " + ", ".join(str(d["seed"]) for d in deteriorated_runs))
    if deteriorated_periods:
        reasons_fail.append("significant deterioration in period(s) " + ", ".join(f"{p['start']}–{p['end']} (AUC {p['auc']})" for p in deteriorated_periods))
    if failed:
        reasons_warn.append(f"{len(failed)} run(s) failed")
    if too_small:
        reasons_warn.append(f"{len(too_small)} run(s) too small to use")
    if determinism and determinism.get("deterministic") is False:
        reasons_warn.append("training is not deterministic")
        limitations.append(determinism["detail"])

    status = "FAIL" if reasons_fail else "WARN" if reasons_warn else "PASS"
    observed = (f"{len(eligible)} runs: AUC mean {aucs.mean():.4f}, SD {aucs.std(ddof=1):.4f}, min {aucs.min():.4f}, max {aucs.max():.4f}. "
                f"Model test AUC {main_eval['auc']:.4f}, {int(main_eval['confidence_level'] * 100)}% bootstrap CI "
                f"[{main_eval['ci_low']:.4f}, {main_eval['ci_high']:.4f}] (n={main_eval['rows']}, defaults={main_eval['positives']}). "
                f"Heterogeneity Q={q:.2f} (df={dof}), p={p_value:.4f}, I²={i2:.0%}.")
    explanation = (
        "Run-to-run differences are consistent with ordinary sampling variation and no run or period deteriorates significantly."
        if status == "PASS" else
        ("Instability: " + "; ".join(reasons_fail) + (". Also: " + "; ".join(reasons_warn) if reasons_warn else "") + ".")
        if status == "FAIL" else "Consistent with sampling variation, but: " + "; ".join(reasons_warn) + "."
    )
    return _check("R4.6", title, status, observed, threshold, **base_extra,
                  _explanation=explanation,
                  _summary={"mean": round(float(aucs.mean()), 4), "sd": round(float(aucs.std(ddof=1)), 4),
                            "min": round(float(aucs.min()), 4), "max": round(float(aucs.max()), 4)},
                  _heterogeneity={"Q": round(q, 3), "df": dof, "p_value": round(p_value, 5), "I2": round(i2, 4),
                                  "pooled_auc": round(pooled, 4), "alpha": alpha},
                  _deteriorated_runs=deteriorated_runs, _deteriorated_periods=deteriorated_periods)


def not_assessed(check_id: str, reason: str) -> Dict[str, Any]:
    title = {"R4.5": "Feature stability across repeated runs", "R4.6": "Predictive performance stability across repeated runs"}[check_id]
    return _check(check_id, title, "NOT_ASSESSED", reason, "See stability_criteria.json",
                  _methodology=R45_METHODOLOGY if check_id == "R4.5" else R46_METHODOLOGY, _runs_completed=0, _limitations=[])
