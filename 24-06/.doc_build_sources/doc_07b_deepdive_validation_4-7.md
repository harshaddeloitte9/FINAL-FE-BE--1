# 2.7 Model Validation — Stages 4–7

**Numbering caveat, verified from code, not speculative:** three different "stage number" systems coexist and disagree. (1) UI numbering, used throughout this document: Stage 4=Benchmarking, 5=Stress, 6=Explainability&Fairness+Compliance, 7=Findings. (2) Legacy backend endpoint paths are frozen one number higher: the Stage 6 UI calls `/validation/stage7/*`; Stage 7 UI calls `/validation/stage8/findings`. (3) `ValidationAgent2`'s own internal 8-stage taxonomy (used by the separate, **unused-by-this-UI**, `/validation/compliance` endpoint) is a third numbering again. Also: the app-context field the Stage 6 page reads for its feature-importance chart is literally named `validationStage4Result` — a leftover variable name from before Stage 3/4 were merged; it is actually populated by the **Stage 3** page.

## 2.7.1 Stage 4 — Benchmarking

**Frontend file is `validation.performance.tsx`** (despite that filename, this is the Benchmarking screen — not to be confused with Stage 3's `validation.challenger.tsx`).

**Challengers are genuinely, independently re-fit** — `POST /models/compare` runs a real `.fit()` per selected candidate on the same split, deliberately **skipping** cross-validation, hyperparameter search, and OOT for speed (docstring confirms this explicitly). Ensembles are capped at 100 trees for this comparison fit (HARDCODED).

**Champion metrics are the Stage-1 MDD numbers, per-key-overridden onto a fresh replica fit** — the backend still fits a "replica" of the champion to get real ROC points, but then overwrites its own computed metrics with the MDD-reported value wherever the MDD provided one (per-key precedence, not all-or-nothing) — confirmed at `main.py:3928-3938`. So the displayed champion numbers (ROC-AUC 0.78, Gini 0.56, KS 0.48, etc.) are traceable straight back to Stage 1's demo/MDD data, not independently computed on this screen.

**The ROC "Benchmark" overlay is a mathematical approximation, explicitly labeled as such in the code's own comment**: `TPR_approx = FPR × challenger_AUC`, evaluated at the champion's real FPR grid points — **not** the challenger's actual predicted-probability ROC curve. The champion's own trace *is* real (`compute_roc_curve` on real test-set predictions). The UI legend correctly says "Benchmark (AUC-based)" rather than implying a measured curve — the deck should say the same.

## 2.7.2 Stage 5 — Stress & Backtesting

`24-06/validation_stress_core.py` — all mechanics genuinely re-score the actual trained pipeline on perturbed data; nothing here is simulated/faked.

**PSI (Population Stability Index)** — standard formula: `Σ(Actual%−Expected%)×ln(Actual%/Expected%)`, comparing the model's predicted-probability distribution on **train** (expected) vs **test** (actual), 10 equal-width bins (HARDCODED), 0.0001 floor for empty bins. Threshold — genuinely matches the textbook convention, confirmed in code: **PSI `<0.10`→PASS, `0.10–0.25`→WARN, `≥0.25`→FAIL** (HARDCODED).

**Macro Stress Scenarios** — 3 scenarios (**HARDCODED business rules**, no fitted elasticity): Adverse (GDP −2%, unemployment +3pp, house prices −10%), Severe (GDP −5%, unemployment +6pp, house prices −25%), COVID-style (income −25%, plus a flat **×2.5 PD multiplier**, HARDCODED — the only scenario with an extra multiplicative uplift on top of re-scoring). Mechanism: auto-detect driver columns by keyword → mechanically shift those raw feature values by the scenario's fixed percentages → re-run the real trained pipeline's `predict_proba` on the perturbed data. No independently-estimated macro elasticity coefficient exists anywhere in the codebase.

**Manual Feature Shock** — genuinely perturbs a copy of the test set (`feature × (1±magnitude%)`) and re-runs real `predict_proba`; `pd_change_pct = (shock_pd − base_pd)/base_pd × 100`.

**Backtesting** — real historical predicted probabilities vs. real observed labels, resampled by period. Per-period flag: `|actual−predicted|>5pp` (HARDCODED). **Overall PASS/WARN/FAIL uses a different threshold on the mean gap**: `<3%`→PASS, `<6%`→WARN, `≥6%`→FAIL (HARDCODED) — two distinct thresholds in the same function, worth stating precisely.

**Directional Testing** (Unemployment↑10%→PD↑, GDP↓10%→PD↑, Credit score↓10%→PD↑ — all HARDCODED shock sizes): status is **"SKIP" specifically and only when the required column isn't detected in the dataset** by keyword match — not a computation that came back inconclusive.

**"6 checks" total** = 3 non-directional checks (sensitivity, backtest, PSI) + 3 directional-test outcomes. **"Dataset Variant: default" control — SOURCE NOT VERIFIED**: no such control exists anywhere in the current frontend (grep-confirmed zero matches).

## 2.7.3 Stage 6 — Explainability and Fairness / Regulatory Compliance

**"SHAP Feature Importance" is not SHAP** — confirmed by import: `val_replication_core.py` imports only `extract_feature_importance` (native `feature_importances_`/`|coef_|`), **not** `compute_shap_values`. This chart reuses Stage 3's replicated model's native importance, correctly claiming "no re-training here" but incorrectly labeled "SHAP" on screen.

**Bias check — AUC gap formula**: protected columns detected by keyword (`age, gender, sex, region, ethnicity, race, nationality, marital, education, employment, loan_purpose`). Per-group AUC computed with a **minimum-count guard of 10 rows** (HARDCODED) — groups smaller than that are silently dropped, with **no confidence interval or bootstrap correction** for how noisy a 10–20-row AUC estimate is. `auc_gap = max(group AUCs) − min(group AUCs)`; **PASS `<0.05`, WARN `<0.10`, FAIL `≥0.10`** (HARDCODED, check ID `8.2`). Note: the "AUC by Group" bar-chart coloring uses a *different*, frontend-only rule (`|AUC − mean AUC| > 0.05` per group) that can flag different specific groups than the backend's actual max−min gap check.

**Regulatory Compliance 7.1–7.10 — all deterministic, none call an LLM** (a genuinely different mechanism from Stage 2's RAG+LLM checks). 7.1–7.4 are keyword-match-against-MDD-text checks (e.g. 7.1 Calibrated PD: keywords `"calibrat"`,`"platt"`,`"isotonic"`,...). **7.9 "Governance Controls Match Risk Tier" and 7.10 "Post-Model Overlays Governed" are PENDING because they are literal hardcoded stubs** — the code's own returned text is *"Manual validation required — not yet automated... This check requires manual review by the validator."* 7.5–7.8 are stubbed the same way.

## 2.7.4 Stage 7 — Findings & Final Validation Report

**Findings aggregation, verified reachability per stage:**
- **Stage 1** — fires if `model_inventory_registered` or `independence_confirmed` is false (both default false unless the reviewer set them).
- **Stage 2** — fires on `missing_max>20%`, `duplicate_rate>1%`, or MDD keyword misses for Limitations/Assumptions/macro documentation.
- **"Stage 3" bucket — structurally unreachable via the current UI.** Requires `stated_auc`, which `validation.intake.tsx` never sends (grep-confirmed) — `ij.get("stated_auc")` is always `None`.
- **"Stage 4" bucket — reachable and real.** Fires on replicated `ROC-AUC<0.70`, `Recall<0.60`, `Gini<0.40`, `Brier>0.25`, or `replicated AUC < benchmark AUC − 0.02` (all HARDCODED); these metrics ARE sent by the frontend.
- **"Stage 5" bucket — structurally unreachable via the current UI.** Requires `shock_result_json`, which `validation.findings.tsx` never sends (grep-confirmed) — always empty, so a `|pd_change_pct|>50%` finding can never fire even if the reviewer used "Apply Shock" earlier.
- **Stage 6** — fires if `bias_auc_gap>0.10` (the bias check's own FAIL band — a WARN-level bias result is never promoted into a Stage 7 finding).

**This is a code-verified explanation for "why only Stages 1/2/6 fire in practice"** — Stages 3 and 5 are dead paths given how this frontend currently populates the request; Stage 4 is conditional on the model's real numbers.

**Verdict rule** (`main.py:5317-5330`, HARDCODED): `0 HIGH & ≤2 MEDIUM → APPROVED`; `≤2 HIGH → CONDITIONALLY APPROVED`; `>2 HIGH → REJECTED`. (A second, separate verdict engine exists in `validation_agent2.py`'s `run_all_checks()` with similar-but-not-identical logic — that engine is **not used by this UI page**; don't conflate the two.)

**Monitoring frequency & revalidation trigger** — a pure lookup table keyed on `model_tier` (**HARDCODED**, not computed from actual PSI/AUC): Tier 1/High → Monthly monitoring, "Annual (or PSI>0.25 or AUC drop>0.05)" trigger; Tier 2/Medium → Quarterly, 18-monthly trigger; else → Semi-annual, 2-year trigger.

**Executive Summary and verdict reasoning text are 100% frontend JavaScript template strings — no LLM call anywhere on this page.** `verdictReasoning()` and `execSummaryDefault()` (`validation.findings.tsx`) interpolate real numbers (`high_count`, `medium_count`, `verdict`, replicated/stated AUC, etc.) into fixed sentence templates — the pre-filled Executive Summary textarea is editable by the reviewer before sign-off/export.

---
