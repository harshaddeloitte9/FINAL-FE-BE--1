# R4.5 / R4.6 — Methodology Review

**Status:** analysis and proposal for approval. **The R4.5 and R4.6 decision rules and thresholds were NOT changed in Phase 5.** Only diagnostic fields were added, so reviewers can see what each check is actually measuring.

---

## 1. R4.5 — "Feature removal: AUC degradation < 0.05"

### Intended concept
The check maps to SS1/23 P4.3, *"Variable removal does not cause instability"* (also ValidationAgent2 stub 4.6). The model-risk question is whether the model stays **stable and sensible** when a variable is removed. Instability signs include erratic or degenerate behaviour, or performance changing far more than the variable's genuine contribution justifies.

### What it actually measures
For each feature, the model is retrained without it and the test AUC is recomputed. The rule is `max(baseline AUC − AUC without feature) < 0.05`. That quantity is the feature's **marginal contribution (importance)**, not instability.

### Why this mismatches the concept

| Situation | Current result | Model-risk reality |
|---|---|---|
| A genuine, strong driver (e.g. debt-to-income) | **FAIL**: removing it costs > 0.05 AUC | Expected and desirable. The model is using a real risk driver. |
| Many redundant, weak features | **PASS**: no single removal matters | May hide over-parameterisation; says nothing about stability. |
| A feature whose removal *improves* AUC | **PASS** (a negative drop is < 0.05) | A real warning sign (noise or over-fitting). |

Evidence from Phase 3/5 runs:
- Every credit dataset with a dominant driver fails R4.5. On a 3,000-row registered Random Forest, removing `dti` cost 0.120 AUC and `score` 0.071.
- On the same data, removing `region` *raised* AUC by 0.023, which R4.5 reports as PASS.

### Diagnostics added in Phase 5 (no rule change)
- `_ablation_runs`: one record per feature, covering status, baseline AUC, AUC without the feature, drop, features used, and confirmation the feature was removed.
- `_noise_reference_sd`: the seed-to-seed AUC standard deviation of the same run, as a noise yardstick.
- `_features_above_noise`: features whose drop exceeds 2× that noise.
- `_features_improving_when_removed`: features whose removal improves AUC by more than 2× noise.

### Proposed methodology (requires approval)
1. **Concentration (report, policy threshold to be set by Model Risk):** the share of the total ablation drop due to the top feature, and the top drop relative to baseline Gini. This flags dependence on a single variable as a *disclosure* item, not an automatic failure.
2. **Noise / over-fitting test (FAIL criterion):** any feature whose removal improves AUC by more than 2× the seed noise.
3. **Stability under removal (FAIL criterion):** performance after removing any single feature collapses toward random (e.g. Gini falls by more than an agreed proportion), or retraining fails or degenerates.

---

## 2. R4.6 — "Seed stability: Std(AUC) < 0.02"

### Intended concept
The check maps to SS1/23 P3.3, *"Random seed sensitivity assessed"*. The question is whether results depend on **training randomness**, such as the estimator's random state, bootstrap sampling or tree construction.

### What it actually measures
For each seed, the data is **re-split** with that seed and the model is retrained with its *fixed* parameters (including a fixed `random_state`). The rule is `std(test AUC across seeds) < 0.02`. The variation therefore mostly comes from **which rows land in the test set**, not from model randomness:
- For deterministic estimators such as Logistic Regression, *all* of the variation is test-set sampling.
- Test-set sampling variability depends on test-set size and default count, not on model quality.

### Evidence
The Hanley & McNeil (1982) standard error of a single AUC estimate is now reported in R4.6's observed text:

| Run | Test set | Observed std across seeds | Expected std from test-set size alone |
|---|---|---|---|
| Logistic Regression, 3,000-row dataset | 450 rows | 0.013 | ≈ 0.023 |
| Random Forest, same data | 450 rows | 0.011 | ≈ 0.025 |

At this test size, a single split's AUC is expected to vary by more than R4.6's 0.02 threshold *from sampling alone*. The observed spread is lower only because seed re-splits share most of their data. Whether R4.6 passes therefore depends largely on dataset size. It is not a reliable measure of seed sensitivity in either direction: earlier phases saw a Random Forest fail it on a 3,000-row dataset.

### Diagnostics added in Phase 5 (no rule change)
- `_seed_runs`: one record per seed — seed, status, AUC (or the error), test rows and positives. Failed seeds are shown, not dropped.
- `_seed_mean`, `_seed_std`, and the individual AUCs in the observed text.
- `_expected_sampling_sd`: the Hanley–McNeil standard error at this test-set size.
- Display fix: chart labels now come from the *completed* seeds only. Previously a failed seed shifted every later label.

### Proposed methodology (requires approval)
1. **Seed sensitivity (the P3.3 test):** keep the split fixed and vary the *estimator's* random state. For deterministic estimators, report NOT_APPLICABLE. Threshold: std of AUC < 0.02, or relative to the sampling SE.
2. **Sampling uncertainty (disclosure):** keep the current re-split procedure, but report it as a confidence interval for test AUC and compare it with the Hanley–McNeil SE rather than a fixed 0.02.

---

## 3. Decision (superseded)
The redesign was requested and is now implemented; sections 1–2 describe the previous rules. Section 4 describes what runs now.

---

## 4. Implemented methodology (R4.5 / R4.6 redesign)

Code: `24-06/stability_checks.py`. Criteria: `24-06/config/stability_criteria.json`. Every value there has a `kind` (`statistical` or `policy`) and a written rationale. `approved` is `false`, so every R4.5/R4.6 result lists the policy values as **PROVISIONAL** in its limitations until Model Risk signs them off. Both checks stay mandatory for the final verdict (verdict policy version 4).

### Shared evidence: repeated runs
- Each seed gives a fresh stratified re-split and a retrain with the model's own configuration. For a registered model, that is the registered lineage contract.
- Each run records, on its held-out rows:
  - AUC, with a stratified-bootstrap SE and CI;
  - sample size, defaults and non-defaults;
  - permutation importance of every input (AUC drop, 5 repeats, giving a within-run SE);
  - the direction of each numeric feature's effect (average change in PD for +1 training SD).
- Failed runs are kept and reported, not dropped.
- **Determinism:** the first completed seed is run twice. A different result means training is not reproducible, and both checks WARN with that limitation.
- **Adequacy:** a run with fewer than `min_class_count` defaults or non-defaults is excluded, and so is a run whose AUC interval is wider than `max_ci_width`. Fewer than `min_completed_runs` usable runs gives **NOT ASSESSED**.

### R4.5 — feature stability
- **Material feature:** importance above 2 within-run SEs in at least half of the runs. Ranks are compared only among material features, because the order of features that contribute nothing is noise.
- **Reported:**
  - selection frequency;
  - mean ± SD importance;
  - mean / min / max rank;
  - top-1 and top-k share;
  - direction and direction consistency;
  - mean and min pairwise Spearman correlation.
- **FAIL** if any of the following holds:
  - a material feature's effect direction agrees in fewer than `min_direction_consistency` of runs;
  - two features whose importances differ significantly (one-sample t-test on the per-run differences, Bonferroni over pairs) swap order in more than `1 − min_pair_order_consistency` of runs;
  - a top-k driver in one run is not significant in another (driver dropout).
- **WARN** if any of the following holds:
  - low Spearman when the swaps are only among statistically tied features;
  - material rank shifts;
  - excluded or failed runs;
  - non-determinism.
- **A strong predictor does not fail:** being consistently dominant is stability. The previous rule failed any model with a feature worth more than 0.05 AUC.
- **Removal-improves-AUC** is a separate diagnostic (`_removal_diagnostics`). It flags a feature whose removal raises AUC by more than `removal_improvement_z` × the baseline bootstrap SE. It never changes R4.5's status.

### R4.6 — predictive performance stability
- **Reported:**
  - per-run AUC with its CI;
  - mean, SD (ddof = 1), min and max;
  - the model's test AUC with a 1000-resample stratified-bootstrap CI;
  - sample size and class counts for each evaluation.
- **Sampling vs genuine instability:** Cochran's Q over the per-run AUCs (weighted by inverse variance) tests whether run-to-run variation exceeds what each run's sampling error explains. I² gives the share that is excess. This replaces the fixed `Std(AUC) < 0.02`.
- **Deterioration is reported separately:**
  - each run is tested against the pooled AUC (one-sided, Bonferroni over runs);
  - when a date column exists, each of up to 4 equal-count chronological periods of the test rows is tested against the overall test AUC (one-sided, Bonferroni over periods).
- **FAIL** on significant heterogeneity, a deteriorated run or a deteriorated period. **WARN** on failed or excluded runs, or non-determinism.
- **NOT ASSESSED** if the test evaluation is missing, has fewer than `min_class_count` of a class, has a CI wider than `max_ci_width`, or there are too few usable runs.

### Known limitations
- Repeated re-splits share most rows, so run AUCs are positively correlated and Cochran's Q is conservative. It under-detects excess variation rather than over-detecting it.
- Two near-duplicate features can share importance between runs while each stays significant. That can PASS even though the top feature changes. The `top1_share` column shows this.
- Permutation importance and the extra bootstrap make replication noticeably slower than before.
- `min_class_count`, `max_ci_width`, `min_mean_rank_correlation`, `min_pair_order_consistency`, the rank-shift values, `min_direction_consistency` and `top_k` are policy values that await approval.
- Stress, fairness and the benchmarking stage still use their own refits and do not compute R4.5/R4.6. `/validation/performance` passes `compute_seed_stability=False`.
- Results are statistical diagnostics of model behaviour, not regulatory approval.
