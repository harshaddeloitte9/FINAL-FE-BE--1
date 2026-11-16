# AEGIS — Validation & Replication: Functional and Data Integrity Audit

| | |
|---|---|
| **Scope** | Model Validation workflow (Stages 1–7 in the UI), with Model Replication (UI Stage 3) as the highest priority |
| **Code audited** | `24-06/main.py`, `24-06/val_replication_core.py`, `24-06/validation_agent2.py`, `24-06/validation_stress_core.py`, `24-06/persistence.py`, `24-06/source_agent2.py`, `aegis-frontend/src/routes/validation.*.tsx`, `aegis-frontend/src/lib/app-context.tsx`, `aegis-frontend/src/hooks/use-resume-state.ts` |
| **Method** | Static trace of every frontend handler → API → backend function → persistence → response → render, plus 24 executed backend tests (see §11) |
| **Source changes** | None. This is an audit-only deliverable. Tests ran against a **copy** of the backend in a temp folder, so no production log, inventory or dataset was written to. The real `app_data` log was only **read**. |
| **Date** | 2026-11-05 |

---

## 1. Executive summary

**The calculations are real, but several screens present the wrong numbers, or present real numbers under the wrong label.** Nothing in the validation workflow returns a random or static metric array. Every ROC curve, confusion matrix, seed-stability run and ablation comes from a real scikit-learn/XGBoost fit (tests T1, T3, T4). The problems are in **what is fitted**, **which numbers are displayed**, and **what feeds the final verdict**:

1. **Benchmarking (UI Stage 4) shows the developer's claimed metrics as the champion's measured metrics.** When an MDD is present, which the page requires, the backend overwrites the computed AUC, Gini, recall and precision with the MDD values *before* it runs the PASS/FAIL checks. The ROC card's "AUC" label is overwritten too, while the plotted curve is still the computed one. The real production log shows this happening: the latest run displays accuracy 0.79 / precision 0.61 / recall 0.72, but the confusion matrix stored in the same record gives 0.577 / 0.313 / 0.670.
2. **The final Findings verdict never sees the replication result.** It reads Stage 4's (claim-substituted) metrics and labels them "Replicated AUC". Its replication-gap check depends on a `stated_auc` field that no screen ever sets. A run with no replication at all can return **"APPROVED — Model meets all regulatory requirements"** (follow-up test F1).
3. **"Model Replication" does not reproduce the registered model.** It trains a fresh model from scratch on whatever file is uploaded. In most cases it uses library-default hyperparameters, no feature-engineering or preprocessing contract, and a default seed. The original model artifact, its training dataset and its stored training configuration are never loaded. 57 of the 59 historical replication runs in the production log used default or unknown configuration.
4. **Stale and unrelated results appear on page load.** Benchmarking's resume asks for a stage name (`benchmarking`) that the backend no longer writes. The production log still holds 21 legacy rows under that name, and the newest one, from 11 Aug 2026, has **AUC = 1.000 from a 2-row test set**. It passes the page's "usable" check and would load into Stage 4, Stage 7 and the overview. The Stress, Fairness and Findings pages also resume the latest run of *any* model.
5. **Some displayed values are hard-coded or fabricated.** These are: the R4.7 "no test contamination" check (always PASS); the Intake demo's target definition ("default_12m", base rate 4.7%, sample size 219,486 — the actual demo dataset has 120 rows, column `default`, 5.8% default rate); the Benchmarking ROC overlay for the challenger (synthesised as `tpr = fpr × AUC`); and pre-ticked governance attestations in demo mode.

**Bottom line for management:** Stage 3 replication output is genuine computation and can be shown, with caveats. Stage 4 champion metrics, the Stage 7 final verdict and the Intake demo target card should **not** be shown as validation evidence until the Critical items in §10 are fixed.

### Severity count

| Severity | Count |
|---|---|
| Critical | 5 |
| High | 13 |
| Medium | 11 |
| Low | 5 |

---

## 2. Stage map (UI ↔ route ↔ endpoint)

The UI renumbered stages after merges, so the stage numbers in the UI, the backend and ValidationAgent2 do not match. This table is the reference for the rest of the report.

| UI stage | Route file | Endpoint(s) called | Backend handler | Persisted `stage` key |
|---|---|---|---|---|
| 1 Intake & Governance | `validation.intake.tsx` | `GET /validation/intake?mode=`, `POST /validation/parse-mdd`, `POST/GET /validation/intake/draft`, `POST /data/upload (demo_mode)` | `_build_validation_intake_snapshot` (main.py:296), `validation_parse_mdd` (5117) | `intake` |
| 2 Data & Model Soundness | `validation.data-quality.tsx` | `/validation/stage2/run`, `/validation/stage3/run`, `…/llm-check` | `validation_stage2_run` (4880), `validation_stage3_run` (4955) | `conceptual_soundness` (Stage 2 is **not** logged) |
| 3 Model Replication & Performance | `validation.challenger.tsx` | `POST /validation/replication`, `GET /history/latest` | `validation_replication` (4075) → `run_replication` (val_replication_core:312) | `replication` |
| 4 Benchmarking | `validation.performance.tsx` | `POST /validation/performance`, `POST /models/compare`, `GET /history/latest?stage=benchmarking` | `validation_performance` (3831) | `performance` (frontend reads `benchmarking`) |
| 5 Stress & Backtesting | `validation.stress.tsx` | `/validation/stress/run`, `/validation/stress/shock` | `validation_stress_run` (4380) → `run_stress_suite` | `stress_testing` |
| 6 Explainability & Fairness | `validation.regulatory.tsx` | `/validation/stage7/run`, `/validation/stage7/bias-check` | `validation_stage7_run` (5063), `validation_stage7_bias_check` (4312) | `fair_lending_bias` |
| 7 Findings & Final Report | `validation.findings.tsx` | `POST /validation/stage8/findings` | `validation_stage8_findings` (5141) | `findings` |
| Overview | `validation.index.tsx` | `GET /history/latest?stage=stress_testing` | — | — |

---

## 3. Findings index

| ID | Sev. | Module | Title |
|---|---|---|---|
| C1 | Critical | Benchmarking | Computed champion metrics replaced by MDD claims before PASS/FAIL and display |
| C2 | Critical | Findings | Final verdict uses claim-substituted metrics labelled "Replicated AUC"; replication never feeds it; can APPROVE with no replication |
| C3 | Critical | Replication | Replication re-fits a new model; it does not load or reproduce the registered model, its data or its configuration |
| C4 | Critical | History | Stage 4 resume key mismatch loads a stale legacy run (AUC 1.000, 2-row test set) |
| C5 | Critical | Intake | Demo intake shows fabricated target/base rate/sample size and pre-ticks every governance attestation |
| H1 | High | Replication | R4.7 "no test contamination" is hard-coded PASS |
| H2 | High | Replication | Config provenance label can claim "developer hyperopt params" when every param was silently dropped |
| H3 | High | Replication | Algorithm silently defaults to XGBoost; no lookup of the registered algorithm |
| H4 | High | Replication | "Passed" summary shown when nothing was compared, or when check evaluation threw |
| H5 | High | Replication | "Reported" column shows form state, not the values the backend compared against |
| H6 | High | Intake → Findings | Proceeding from Intake drops governance flags, algorithm and target, so Findings always raises 2 HIGH FAILs |
| H7 | High | Regulatory | IFRS 9 compliance checks pass on trivial substrings ("decline" ⇒ ECL, "credit risk" ⇒ SICR) |
| H8 | High | Benchmarking | Challenger ROC overlay is synthesised (`tpr = fpr × AUC`), not measured |
| H9 | High | Stress | PSI compares train vs test of the same random split; macro scenarios mis-map drivers and report 0% silently |
| H10 | High | Inventory | Failed or unknown-model replications are registered in Model Inventory with placeholder metadata |
| H11 | High | Intake | Training code / hyperparameters / performance / profile uploads keep the filename only and are never used |
| H12 | High | Lineage | Each stage re-fits its own model with different defaults (Stage 3 ≠ Stage 4 ≠ Stress ≠ Fairness) |
| H13 | High | History | Stress, Fairness, Findings, Data-Quality and Overview resume the latest run of *any* model/dataset |
| M1 | Medium | Replication | Replication resume never matches csv_text/demo datasets (".csv" suffix mismatch) |
| M2 | Medium | Performance | "Train/Test AUC Gap" shows the test AUC itself when CV is missing |
| M3 | Medium | Performance | Stage 5 `compliance_findings` contradict the computed checks (WARN "not stated" / PENDING "not automated") |
| M4 | Medium | Replication | No minimum-sample guard: 120-row demo gives an 18-row test set with 1 default and still produces PASS/FAIL |
| M5 | Medium | MDD parsing | Metric regex extracts wrong values ("risks: 0.15" ⇒ KS; "CV mean AUC" ⇒ ROC-AUC) |
| M6 | Medium | Data Soundness | Stage 2 RAG quantitative rules are called with an empty metrics context and can never fire |
| M7 | Medium | Conceptual | "Feature relevance" falls back to an ad-hoc Logistic Regression on a *guessed* target |
| M8 | Medium | Replication | Errors silently swallowed (MDD parse, check evaluation, reported_json) |
| M9 | Medium | Agent2 Stage 4 | ValidationAgent2 4.1 always FAILs "no hyperparameter config" because hyperparams are never passed |
| M10 | Medium | Security | `/history/*` `log_file` parameter is not validated (reads arbitrary CSV paths) |
| M11 | Medium | Inventory | A replication run is recorded as stage `data_validation` in the inventory |
| L1 | Low | Replication | R4.3 "observed" text has no numbers; R4.8 SKIP message is wrong when CV ran |
| L2 | Low | Findings | Pass thresholds are global constants, not tier- or portfolio-dependent; ≤2 HIGH FAILs still "CONDITIONAL" |
| L3 | Low | Persistence | `app_data` is 5.7 GB: every run's full payload is kept forever |
| L4 | Low | Intake | Risk Tier card reads the backend demo snapshot, not the Risk Tier dropdown |
| L5 | Low | Agent2 | A second, unused replication engine in ValidationAgent2 (XGBoost-only, 80/20) |

---

## 4. Module-wise findings (detailed)

### 4.1 Critical

#### C1 — Benchmarking: computed champion metrics replaced by MDD claims

| Field | Detail |
|---|---|
| Module | Benchmarking (UI Stage 4) |
| File | `24-06/main.py`; `aegis-frontend/src/routes/validation.performance.tsx` |
| Function | `validation_performance` (main.py:3831), `_build_performance_report` (3663) |
| Issue | When `reported_json`/`mdd_file` is present, the replica's computed metrics are overwritten per key with the MDD values (main.py:3933-3938). `_build_performance_report` then runs the ROC-AUC ≥ 0.70, Gini ≥ 0.40, Recall ≥ 0.60 and Precision ≥ 0.50 checks on those **claimed** values (3753-3780) and sets `roc_curve.auc = metrics["roc_auc"]` (3813), so the ROC card's AUC label is the claim while the plotted curve is the computed fit. The frontend **refuses to run** without MDD metrics (validation.performance.tsx:207-210) and always sends them (221), so this substitution happens on every run. |
| Evidence | **T12** (synthetic data, claimed AUC 0.97): displayed `roc_auc` = 0.97, `roc_curve.auc` = 0.97, yet the computed AUC of the same fit is 0.7286 (T1/T4). Every `metric_checks` row for a claimed key shows PASS on the claimed value. Keys that were not claimed (F1 0.538, Brier, PR-AUC, KS) stay computed, so one KPI strip mixes claims and measurements. **Production log** (latest `performance` row, 2026-09-28): displayed accuracy 0.79 / precision 0.61 / recall 0.72 / F1 0.65, while the confusion matrix `[[200,165],[37,75]]` in the same record gives 0.577 / 0.313 / 0.670 / 0.426. |
| Impact | The champion is graded against regulatory thresholds using the developer's own numbers. This defeats independent validation. The champion-vs-challenger comparison compares a claim (possibly from another dataset) with a measurement. |
| Severity | **Critical** |
| Recommendation | Never overwrite computed metrics. Return `computed_metrics` and `reported_metrics` as separate objects, run every PASS/FAIL on `computed_metrics`, and show the claims in their own "Developer-reported" column. Remove the `hasMddMetrics` hard gate. |
| Test | Re-run T12: `report.metrics.roc_auc` must equal the AUC integrated from `report.roc_curve.points` (±0.01). `metric_checks` values must equal computed values. `reported_metrics.roc_auc` must equal 0.97. |

#### C2 — Final verdict is not tied to replication; can APPROVE with no evidence

| Field | Detail |
|---|---|
| Module | Findings & Final Report (UI Stage 7) |
| File | `aegis-frontend/src/routes/validation.findings.tsx`; `24-06/main.py` |
| Function | `Findings` effect (findings.tsx:258-323); `validation_stage8_findings` (main.py:5141) |
| Issue | (a) The frontend sends `rep_metrics_json = validationStage5Result.report.metrics` (findings.tsx:270, 286), i.e. Stage 4's claim-substituted metrics (C1), not Stage 3's replication result (`validationStage4Result`), which Findings never reads. The report text labels this "Replicated AUC" (findings.tsx:404). (b) The AUC replication-gap check needs `ij.stated_auc` (main.py:5264-5273), and no screen ever sets it (grep: only consumers exist). (c) Missing inputs produce no findings, so an absent replication, benchmark or bias run counts as "no issues" (5263-5315). (d) `APPROVED` is returned when there are 0 HIGH and ≤2 MEDIUM findings (5322-5324). |
| Evidence | **F1-A**: demo intake + complete MDD + no replication/benchmark/bias → `verdict: "APPROVED"`, `"Model meets all regulatory requirements and validation standards."`, `total_count: 0`, `replicated_auc: null`. **F1-B**: passing the MDD-claimed AUC 0.82 as `rep_metrics` → APPROVED, `replicated_auc: 0.82`, `stated_auc: null`. |
| Impact | The headline decision shown to management can be produced without replication ever running, and its "Replicated AUC" can be the developer's own claim. |
| Severity | **Critical** |
| Recommendation | Feed Findings from Stage 3's `report.replication.result.metrics` plus `checks`. Treat missing mandatory stages (replication, benchmarking, stress, fairness) as HIGH "Not performed" findings. Populate `stated_auc` from the parsed MDD (`validationMddMetrics.roc_auc`). Block `APPROVED` unless every mandatory stage has a persisted, scoped run_id for the same model and dataset. |
| Test | F1-A must return a verdict other than APPROVED with a "Replication not performed" HIGH finding. Supplying replication AUC 0.70 against MDD AUC 0.82 must raise "4.2 AUC Replication" FAIL. |

#### C3 — "Replication" re-fits a new model and does not reproduce the registered one

| Field | Detail |
|---|---|
| Module | Model Replication (UI Stage 3) |
| File | `24-06/main.py`; `24-06/val_replication_core.py`; `aegis-frontend/src/routes/validation.challenger.tsx` |
| Function | `validation_replication` (main.py:4075-4309), `run_replication`/`_fit_core` (core:188-309), `runReplication` (challenger.tsx:625-712) |
| Issue | 1. No model artifact is loaded. The trained pipeline exists (`model_artifact` from `/models/train`, main.py:2977) but replication never uses it, so the "original model" is never scored. 2. **Dataset identity** is the uploaded file's name only, with no hash and no check that it is the training dataset; the split is recomputed on whatever was uploaded. 3. **Hyperparameters** are sent only if `trainingResult.model_name === modelIdentity` in the *same browser session* (challenger.tsx:531-560). Otherwise library defaults are used. The Model Inventory stores `training_config` and `algorithm` (persistence.py:1137, 1164) and is never consulted. 4. **Preprocessing / feature engineering**: the endpoint has no parameter for them (T11). `prepare_data` re-derives treatment automatically, and `use_feature_engineering` is always `False` (main.py:4249-4260), whatever the developer used. 5. `random_seed`, `cv_folds` and `seeds` are never sent by the frontend (653-687), so the backend defaults 42/5/[42…46] apply even when the developer used another seed. 6. "Original" metrics are whatever is typed or extracted into the Reference fields. |
| Evidence | T11: endpoint params contain no preprocessing or FE field; `use_feature_engineering` default `False`. Production log: 59 replication runs → `replication_config_source` = None (pre-provenance) 42, `registry_defaults_unavailable_config` 15, developer config 2. |
| Impact | R4.2–R4.8 compare a *different* model against the developer's claims. A PASS does not show that the submitted model performs as documented, and a FAIL may only reflect configuration drift. |
| Severity | **Critical** |
| Recommendation | Define a **replication contract** persisted at training time: model_id, dataset SHA-256, target, feature list, preprocessing treatment map, FE plan, split config (sizes, seed, stratify), estimator class and final params. Have `/validation/replication` accept `model_id`, load the contract from the inventory, verify the dataset hash, refit with exactly that contract, and also score the stored artifact on the same test split ("artifact vs refit"). Reject the run, or mark it `UNVERIFIED_LINEAGE`, if any element is missing. |
| Test | Train a model with non-default params, FE on and seed 7. Replicate by `model_id` only: the response must echo the same params, FE on, seed 7 and dataset hash; artifact AUC must equal the development AUC (±1e-6) on the original split; a changed dataset must return HTTP 409. |

#### C4 — Stage 4 resume loads a stale legacy run

| Field | Detail |
|---|---|
| Module | History / Benchmarking |
| File | `aegis-frontend/src/routes/validation.performance.tsx`; `24-06/main.py` |
| Function | `useResumeState(..., "benchmarking")` (performance.tsx:157-172); `log_event(stage="performance")` (main.py:3978) |
| Issue | The frontend asks for stage `benchmarking`; the current backend logs `performance`. The lookup is also unscoped (no model or dataset filter). The production log still holds **21 legacy `benchmarking` rows**. |
| Evidence | T14 (clean copy): `benchmarking` → none, `performance` → found. **Production log**: newest `benchmarking` row is 2026-08-11. Its artifact has `benchmark.model_name="Logistic Regression"`, `status="OK"` (passes the page's "usable" gate) and `roc_auc = 1.0`, accuracy/precision/recall = 1.0, confusion matrix `[[1,0],[0,1]]` (a 2-row test set). On a fresh session this loads into Stage 4, is written to `validationStage5Result` (168), and so feeds the Overview "Champion ROC-AUC 1.000" (index.tsx:83-85) and the Findings verdict (C2). |
| Impact | A demo on a fresh browser can show a perfect, months-old, unrelated result as the current champion. |
| Severity | **Critical** |
| Recommendation | Use one stage-key constant shared by backend and frontend. Scope by `business_model_name` and `dataset_name` (as Stage 3 does). Version payload schemas and ignore legacy rows. |
| Test | With the production log in place, open Stage 4 in a clean browser profile: it must show the empty state. After running Stage 4 for model A, a refresh must restore exactly that run_id. |

#### C5 — Demo intake displays fabricated facts and pre-ticks governance attestations

| Field | Detail |
|---|---|
| Module | Intake & Governance (UI Stage 1) |
| File | `24-06/main.py`; `aegis-frontend/src/routes/validation.intake.tsx` |
| Function | `_build_validation_intake_snapshot` (main.py:296-465); `loadDemo` (intake.tsx:530-594); render (744-757) |
| Issue | The demo's `display.targetDefinition` is literal text: `default_12m ∈ {0,1}`, base rate **4.7%**, sample size **219,486** (main.py:420-428). It is rendered as fact in the Target Definition card. All 8 governance attestations (`chk_*`) are returned `True` (394-401) and applied to the checkboxes (intake.tsx:568-575), **including Demo B "Flawed Submission"**, whose own metadata says `independence_confirmed: False` and `model_inventory_registered: False` (313-314). The demo also says `algorithm: XGBoost` (343) while its hyperparameter file says `LightGBM`, and that file's feature importances name 4 columns that do not exist in the demo dataset. |
| Evidence | **T21**: displayed `default_12m`/4.7%/219,486 vs actual demo file 120 rows, no `default_12m` column, default rate 5.83%. `governance_checkboxes_preticked: true`. Params model `LightGBM` vs intake `XGBoost`. Missing features: `debt_to_income, num_late_payments, income, age`. |
| Impact | A reviewer sees a target definition and population that do not belong to the dataset under test, and attestations that no person made. |
| Severity | **Critical** (in a management demo) |
| Recommendation | Compute target, base rate and sample size from the loaded dataset profile. Never pre-tick attestations. Label every demo-sourced field "Demo data". Make the demo's MDD, params and dataset mutually consistent. |
| Test | Load Demo A: the card must show `default`, 5.8%, 120. All attestation boxes start unticked. |

### 4.2 High

#### H1 — R4.7 "Split reproducibility — no test contamination" always PASS

| Field | Detail |
|---|---|
| Module | Replication |
| File | `24-06/val_replication_core.py` |
| Function | `evaluate_replication_checks` (687-691) |
| Issue | The check appends `"status": "PASS"` unconditionally. Its "observed" field just prints split sizes. Nothing tests determinism, overlap or leakage. |
| Evidence | Code lines 688-691; T1, T2 and T22 all show R4.7 PASS, including a run where R4.1–R4.6 fail. |
| Impact | A fabricated control result inflates the pass count shown in the "x/y checks passed" badge. |
| Severity | High |
| Recommendation | Implement it: re-split with the same seed and assert identical indices, assert train∩test = ∅ on a row key, and assert the FE/preprocessing fit used train only. Otherwise return `SKIP — not implemented`. |
| Test | Inject a duplicated row across train and test: R4.7 must FAIL. |

#### H2 — Provenance label can be false

| Field | Detail |
|---|---|
| Module | Replication |
| File | `24-06/main.py:4143-4158`; `24-06/val_replication_core.py:254-262` |
| Function | `validation_replication`, `_fit_core` |
| Issue | `replication_config_source` is set from "a non-empty dict was received". `_fit_core` then silently drops every key the estimator doesn't accept. |
| Evidence | **T8**: `model_params_json={"totally_bogus_param":123}` + `source=developer_hyperopt_best_params` → label `developer_hyperopt_best_params`, `model_params_used` identical to the defaults, metrics identical to the defaults run. |
| Impact | The UI line "Configuration: Developer training configuration (hyperopt-selected parameters)" can be shown for a defaults fit. |
| Severity | High |
| Recommendation | Return `params_applied` and `params_rejected`. Derive the label from what was *applied*. Reject the run if any supplied param is rejected. |
| Test | Re-run T8: expect HTTP 400, or label `registry_defaults…` with `params_rejected=["totally_bogus_param"]`. |

#### H3 — Algorithm silently defaults to XGBoost

| Field | Detail |
|---|---|
| Module | Replication |
| File | `aegis-frontend/src/routes/validation.challenger.tsx` |
| Function | state init (365), prefill (593-598) |
| Issue | `algorithm` starts as `"XGBoost"` and is only changed if a context value is literally one of the five option names. A business name (e.g. "PD_Model_v1" for a Random Forest) leaves XGBoost selected. The inventory's stored `algorithm` is never queried. |
| Evidence | Code. Production log: 46 of 59 replication runs used XGBoost and 13 have no algorithm recorded. |
| Impact | The wrong estimator class can be "replicated" without any warning. |
| Severity | High |
| Recommendation | Resolve the algorithm from the inventory by model_id. Start empty and require an explicit choice. Warn on a mismatch with the registered algorithm. |
| Test | Register a Random Forest model as "PD_Model_v1" and open Stage 3: the algorithm must show Random Forest, or be empty and block Run. |

#### H4 — "Passed" summary when nothing was compared, or when checks threw

| Field | Detail |
|---|---|
| Module | Replication |
| File | `challenger.tsx:1371-1379`; `main.py:4262-4266` |
| Function | result summary pill; `validation_replication` |
| Issue | The pill shows "Passed" when there are 0 FAILs. With no reference metrics, R4.2/R4.3/R4.4 are WARN and R4.8 SKIP, so nothing was compared, yet the pill can read "Passed". If `evaluate_replication_checks` raises, `checks=[]` and `flags=[]`, and the UI shows "Passed · 0/0 checks passed". |
| Evidence | T1: no reference metrics → R4.2/4.3/4.4 WARN, R4.8 SKIP. (That run showed "Failed" only because R4.5/R4.6 happened to fail on this data.) Exception path: code. |
| Impact | Replication can appear successful without any developer-vs-replica comparison. |
| Severity | High |
| Recommendation | Three states: Passed / Failed / **Inconclusive** (any HIGH-severity WARN or SKIP, or zero checks). Return HTTP 500 or `checks_error` on evaluation exceptions. |
| Test | Run with no reference metrics → "Inconclusive". Monkeypatch `evaluate_replication_checks` to raise → error banner, not "Passed". |

#### H5 — "Reported" column ≠ values the backend compared

| Field | Detail |
|---|---|
| Module | Replication |
| File | `challenger.tsx:964-1004`; `main.py:4167-4196` |
| Function | `reportedNumeric`/`comparisonRows`; `validation_replication` |
| Issue | The Reported column and Δ are computed from the **current form state**. The backend merges `reported_json` with MDD-extracted values (MDD wins per key) and never returns the merged `reported` dict. After an MDD upload on this page, after editing a field after a run, or after resuming a historical run, the Reported/Δ columns disagree with the R4.x verdicts beside them. |
| Evidence | Code: the response has no `reported` field; `comparisonRows` reads `reported` state. |
| Impact | The displayed comparison and the PASS/FAIL beside it can be computed from different numbers. |
| Severity | High |
| Recommendation | Return `reported_used` (with source per key: form/MDD/training) in the response and in the persisted artifact. Render only from it. |
| Test | Enter AUC 0.80, upload an MDD stating 0.70, run: the Reported column must show 0.70, matching R4.2's observed text. |

#### H6 — Proceeding from Intake drops governance flags and model facts

| Field | Detail |
|---|---|
| Module | Intake → Findings |
| File | `validation.intake.tsx:376-396`; `main.py:5201-5212` |
| Function | `handleProceed`; `validation_stage8_findings` |
| Issue | "Proceed" overwrites `validationIntakeData` with a new object that has no `model_inventory_registered`, `independence_confirmed`, `algorithm`, `target_col` or `calibration_method`, even though the reviewer ticked "registered" and "no conflict" on screen. Stage 7 then always raises "1.2 Model Inventory" and "1.4 Independence" as HIGH FAILs. ValidationAgent2's algorithm and calibration checks also lose their inputs. |
| Evidence | **T17**: handleProceed-shaped intake → HIGH findings `1.2 Model Inventory`, `1.4 Independence` → REJECTED. |
| Impact | The verdict ignores the attestation the reviewer made. At least 2 HIGH FAILs are guaranteed, so a non-demo run can never be APPROVED. |
| Severity | High |
| Recommendation | Map `chkInventory → model_inventory_registered` and `chkIndependence → independence_confirmed`. Merge rather than replace, so demo/MDD fields survive. |
| Test | Tick both boxes, proceed, run Findings: no 1.2/1.4 findings. |

#### H7 — Regulatory compliance checks pass on trivial substrings

| Field | Detail |
|---|---|
| Module | Explainability & Fairness (regulatory tab), Findings |
| File | `24-06/validation_agent2.py` |
| Function | `check_regulatory_compliance` (1435-1526) |
| Issue | 7.2 "IFRS 9 Stage 1/2/3 **Implemented**" passes if the MDD contains "12 month". 7.3 "SICR criteria documented" passes on "credit risk", which almost every credit MDD contains. 7.4 "Lifetime ECL **Computed**" passes on the substring `ecl`, which appears in "decline", "declared" and "reclassified". |
| Evidence | **T19**: MDD = "Applications that decline are excluded. This model manages credit risk for 12 month horizons." → 7.2 PASS, 7.3 PASS, 7.4 PASS. |
| Impact | The compliance % on the Overview and the Stage 6 PASS badges overstate IFRS 9 compliance. The titles claim "implemented" or "computed" for what is at best a keyword presence check. |
| Severity | High |
| Recommendation | Use word-boundary regex and specific phrases. Retitle to "documented in MDD" and mark `check_type: doc`. Require evidence quotes. Move "implemented/computed" claims to checks that test data or output. |
| Test | Re-run T19: 7.2/7.3/7.4 must not PASS. |

#### H8 — Challenger ROC curve is synthesised

| Field | Detail |
|---|---|
| Module | Benchmarking |
| File | `validation.performance.tsx:334-341` |
| Function | `benchmarkOverlayData` |
| Issue | The challenger "curve" is `tpr = fpr × AUC`. That is a straight line *below* the random-classifier diagonal for any AUC < 1, plotted next to the measured champion curve. The code comment admits it is an approximation, and the label "Benchmark (AUC-based)" does not tell a viewer it is not data. |
| Evidence | Code. The backend already has the challenger's `predict_proba` in `_run_benchmark_comparison` (main.py:3596) but doesn't return ROC points. |
| Impact | A fabricated chart makes the challenger look worse than random. |
| Severity | High |
| Recommendation | Return `compute_roc_curve(y_true, challenger_proba)` from the backend and plot it, or remove the series. |
| Test | The challenger curve must end at (1,1) and its trapezoid area must equal `benchmark.metrics.roc_auc` (±0.01). |

#### H9 — Stress tests: PSI by construction, driver mis-mapping, silent no-op scenarios

| Field | Detail |
|---|---|
| Module | Stress & Backtesting |
| File | `24-06/validation_stress_core.py` |
| Function | `compute_psi_stability` (271-311), `detect_driver_columns` (106-118), `apply_macro_scenario` (214-257) |
| Issue | (a) PSI compares train vs test scores from **one random split of the same data**, so it is near 0 by construction and is not population stability (no time or population shift). (b) The `income` keyword matches `debt_to_income`. The "Income −25%" scenario therefore *lowers* DTI, which is a favourable shock. (c) When no GDP/unemployment/HPI column exists, 6.2a and 6.2b apply nothing and still report a 0.0% PD change as a scenario result. (d) 6.2c's headline is mostly a hard-coded ×2.5 multiplier, not model response. (e) For fraction-scaled unemployment (≤1.5), "+3pp" is applied as +0.0003 (`/100` at line 227 should not be there). |
| Evidence | **T20**: PSI 0.0289 → PASS. 6.2a `applied: []`, 0.0%; 6.2b `applied: []`, 0.0%; 6.2c `["debt_to_income x 0.75", "flat PD uplift x 2.5"]`, +117%. |
| Impact | Stress results look like evidence of stability or resilience when they are artefacts. |
| Severity | High |
| Recommendation | Compute PSI on development vs validation (or out-of-time) populations. Use exact or whitelisted driver mapping, confirmed by the user. Mark a scenario "Not applicable — no driver" instead of 0%. Show the multiplier and model response separately. Fix the unit conversion. |
| Test | Dataset with `debt_to_income` only → income scenario "N/A". Shifted validation sample → PSI > 0.25 FAIL. |

#### H10 — Failed replications are registered in Model Inventory

| Field | Detail |
|---|---|
| Module | Model Inventory |
| File | `main.py:4210-4247`; `persistence.py:1498-1610` |
| Function | `validation_replication` → `register_validation_run` |
| Issue | Inventory registration happens **before** training and regardless of outcome. Missing intake fields are filled with "Unknown", "Risk", "1.0", "Internal", "PD (Probability of Default)". |
| Evidence | **T6**: algorithm "NoSuchModel" → `success:false`, yet the inventory gained `VAL-002 "Ghost Model"`, status "Under Validation", owner "Unknown", version "1.0", framework "Internal", algorithm "NoSuchModel". |
| Impact | The inventory fills with phantom engagements whose metadata looks real. |
| Severity | High |
| Recommendation | Register only after `result.success`. Store missing fields as `null` and show "Not captured". |
| Test | Re-run T6: no inventory entry is created. |

#### H11 — Intake artifacts other than dataset/MDD are filename-only

| Field | Detail |
|---|---|
| Module | Intake |
| File | `validation.intake.tsx:506-514, 856-940` |
| Function | `UploadAction onFile` handlers |
| Issue | Training code, data profile, assumptions, performance report and hyperparameters JSON only call `setXFileName(f.name)`. The file is never read or sent. They count toward "Artifacts Submitted x/7", and training code is marked **Required — "Required for replication and review"**. |
| Evidence | Code: e.g. 868 `onFile={(f) => setTrainingCodeFileName(f.name)}`. |
| Impact | The UI implies the artifacts are used in validation when they are not. In particular, an uploaded hyperparameters JSON never reaches replication. |
| Severity | High |
| Recommendation | Upload and persist the files. Parse hyperparameters JSON into the replication contract (C3). Otherwise relabel as "Recorded (not analysed)". |
| Test | Upload params JSON with `C=0.01` → Stage 3 shows `model_params_used.C = 0.01`. |

#### H12 — Each stage fits a different model

| Field | Detail |
|---|---|
| Module | Lineage (Stages 3–6) |
| File | `validation.performance.tsx:102-104`; `validation.stress.tsx:144-151`; `validation.regulatory.tsx:254-255`; `main.py:3916-3926, 4419-4430, 4351-4360` |
| Function | multiple |
| Issue | Stage 3 uses the user-picked algorithm and possibly developer params. Stage 4 uses `selectedModel.name ‖ trainingResult.model_name ‖ "Logistic Regression"` with **no** params. Stress uses the **first entry of `/models/list`**. Fairness uses `… ‖ "Logistic Regression"` and target `… ‖ "default"`. None pass `model_params`, seed or FE. |
| Evidence | Code paths cited. |
| Impact | Benchmarking, stress and fairness conclusions may be about a different model from the one replicated, and from the one in production. |
| Severity | High |
| Recommendation | Persist one "model under validation" (model_id plus contract) at Intake. Have every stage load it, and echo `model_id` and a `contract_hash` in each response. |
| Test | Every stage response for one engagement carries the same `contract_hash`. |

#### H13 — Unscoped resume shows other models' results

| Field | Detail |
|---|---|
| Module | History |
| File | `validation.stress.tsx:133-142`; `validation.regulatory.tsx:275-277`; `validation.findings.tsx:247-256`; `validation.data-quality.tsx:238`; `validation.index.tsx:39-47` |
| Function | `useResumeState` callers |
| Issue | Only Stage 3 scopes by model and dataset. The others take the newest row system-wide. The Overview marks Stress "complete" if *anyone* ever ran it. |
| Evidence | T15: unscoped latest = "Model Y" while working on "Model X". Production log: latest `findings` = REJECTED, 7 HIGH (2026-09-28), which would appear for any new engagement. |
| Impact | Stale results from previous models are displayed after refresh. |
| Severity | High |
| Recommendation | Log `business_model_name`, `dataset_name` (or `engagement_id`) for every stage and scope every resume. Disable resume if identity is unknown. |
| Test | Run stress for model A, start model B: Stress shows the empty state and the Overview shows Stress "pending". |

### 4.3 Medium

| ID | Module | File / Function | Issue | Evidence | Impact | Recommendation | Test |
|---|---|---|---|---|---|---|---|
| M1 | History | `challenger.tsx:562-574` vs `422-428`; `main.py:4208` | When the dataset comes from `profile.csv_text` (demo, or after a refresh where `ds.file` is not persisted), the uploaded File is named `"<dataset_name>.csv"`, but resume filters by `"<dataset_name>"`. | **T13**: lookup "Demo A dataset" → not found; "Demo A dataset.csv" → found. | Replication results never restore after a refresh in the demo flow. | Normalise dataset identity server-side (strip extension) or send an explicit `dataset_id`. | Re-run T13: both lookups match. |
| M2 | Performance | `main.py:3743-3745` `_build_performance_report` | When `cv_mean_auc` is missing, `gap = test_auc` (the AUC itself) and the label "Train/Test AUC Gap" is kept. | Code. | A 0.73 "gap" would look alarming. | Return `gap=null` with reason. | Fit without CV → gap null. |
| M3 | Performance | `main.py:3747-3751`; `validation_agent2.py:1339-1404` | `compliance_findings` 5.1–5.4 read `stated_*` keys (never set) and say "not stated in MDD — cannot verify" even when the MDD states them. 5.5–5.7 are "PENDING – not automated" although the same response computes the AUC gap, PR-AUC and KS. These are persisted (not currently rendered in Stage 3). | **T12** `compliance_findings`. | Contradictory evidence in the stored audit trail. | Feed parsed MDD metrics and the computed values in, or drop the duplicate set. | 5.1 shows "Developer stated 0.82 / replicated 0.73". |
| M4 | Replication | `val_replication_core.py:594-703` | No minimum-sample or minimum-defaults guard (ValidationAgent2 has one, 200 rows / 10 defaults, at 1153). | **T22** Demo A: 120 rows → test 18 rows with 1 default; AUC 0.294, recall 1.0, precision 0.077; full R4 PASS/FAIL grid issued. | Statistically meaningless metrics are presented as a verdict, and this is the default demo dataset. | Add the guard and mark the run Inconclusive. Ship a realistic demo dataset. | Demo A → "Insufficient data". |
| M5 | MDD parsing | `val_replication_core.py:69-115` `extract_metrics_from_mdd` | No word boundaries; first match wins. | **T18**: "Key risks: 0.15" → `ks=0.15`; "CV mean AUC: 0.73" → `roc_auc=0.73`. "Target accuracy 0.90 (not achieved). Achieved accuracy: 0.71" → 0.71 (correct only by luck of the range filter). | Reference metrics for R4.x can be wrong. | Use `\b` boundaries, table-aware parsing, and show the extracted values with source snippets for confirmation. | T18 cases return nothing / correct values. |
| M6 | Data Soundness | `main.py:4928` | `check_for_validation("data_validation", {})`: every quantitative rule resolves `None` and is skipped (`source_agent2.py:115-117`). | Code. | Stage 2 "RAG Agent Rules" quantitative half can never produce a result. | Build the metrics dict (missing %, imbalance, correlation, IV) as Stage 3 does for `correlation_max`. | A rule with `missing_pct > 0.2` fires on a 30%-missing column. |
| M7 | Conceptual | `main.py:4591-4649` `_derive_feature_importance_payload` | Without a model file, importance comes from a new Logistic Regression on numeric columns, with the target **guessed** as the first column having ≤2 unique values. | Code 4607-4631. | "Feature relevance" may describe a surrogate model with the wrong target. | Use the Stage 3 replicated pipeline's importance or the stored artifact. Label the source. | Response includes `importance_source`. |
| M8 | Replication | `main.py:4149-4150, 4169-4175, 4180-4196, 4263-4266` | MDD save/parse failures, malformed `reported_json` and check-evaluation exceptions are swallowed with `pass` or an empty default. | Code. | An MDD that fails to parse silently produces "Reported not provided" WARNs. | Return `warnings[]` and show them. | Upload a corrupt PDF → visible warning. |
| M9 | Agent2 Stage 4 | `main.py:225-230`; `validation_agent2.py:1043-1070` | `run_validation_agent2` never passes `hyperparams`, so 4.1 "Model Replicable from Submitted Artifacts" is always FAIL even in demos that ship a params file. | **T19** `4.1 FAIL "No hyperparameter config submitted"`. | Contradicts Stage 3, which did replicate. | Pass the parsed params, or remove the duplicate check. | Demo A → 4.1 PASS. |
| M10 | Security | `main.py:536-558`; `persistence.py:77, 90` | `log_file` is joined to `APP_DATA_DIR` without validation. | **T16**: `log_file=../demo_data/clean_portfolio.csv` read 120 rows (read-only probe). | Arbitrary CSV read under the backend's permissions. | Whitelist `{dev_pipeline_log.csv, validation_pipeline_log.csv}`. | Probe returns 400. |
| M11 | Inventory | `persistence.py:1564, 1586, 1605-1608` | A replication run sets `validation_stage="data_validation"` and `data_validation_status="In Progress"`. | **T6** inventory entry. | Inventory shows the wrong stage. | Pass the actual stage. | Replication → `validation_stage="replication"`. |

### 4.4 Low

| ID | Module | File / Function | Issue | Recommendation |
|---|---|---|---|---|
| L1 | Replication | `val_replication_core.py:637, 700-701` | R4.3 "observed" = "Gini/Ks comparison" (no numbers, see T2). R4.8 SKIP always says "CV not run — enable K-fold…" even when CV ran and only the reported value is missing (T1: `cv_mean_auc 0.7021`, R4.8 SKIP). | Print both values and deltas. Fix the message. |
| L2 | Findings / Performance | `main.py:3754-3809, 5276-5289, 5322-5330`; `validation_agent2.py:138-145` | Thresholds (AUC ≥ 0.70, Recall ≥ 0.60, …) are global constants. ≤2 HIGH FAILs still yields CONDITIONAL. These are legitimate configuration, not fabrication, but they are undocumented and not tier-aware. | Move to versioned config, show the policy source in the report. |
| L3 | Persistence | `persistence.py:52-58` | Every run writes a full JSON artifact; `app_data` is **5.7 GB**. No retention or index. `read_log` re-parses the whole CSV per request. | Retention policy, plus SQLite/Parquet index. |
| L4 | Intake | `validation.intake.tsx:731-742` | The Risk Tier card reads `intake.riskTier` (demo snapshot), not the editable `tier` dropdown. | Derive from `tier`. |
| L5 | Agent2 | `validation_agent2.py:1110-1322` | A second replication engine (XGBoost-only, numeric-only, 80/20) exists. It only runs if `hyperparams` and `stated_auc` are both present, which is never true today. | Remove, or route to `run_replication`. |

---

## 5. Hard-coded and dummy value inventory

| # | Value | Location | Classification | Why it matters |
|---|---|---|---|---|
| 1 | `default_12m ∈ {0,1}`, base rate "4.7%", sample size "219,486", "positive class = 90+ DPD within 12m" | main.py:420-428 → intake.tsx:744-757 | **Fabricated display** | Rendered as facts about the dataset under test (C5) |
| 2 | Model ID "CR-PD-XGB-027", "Retail PD — XGBoost Champion", owner "A. Khurana", "Last validated 12 Apr 2026", artifact rows "Uploaded 21 Jun 2026 · 09:13" | main.py:409-441 | Fabricated, **not rendered** today (frontend ignores `modelMetadata.items` and `artifacts`) | Dead risk: would show if wired up. Delete. |
| 3 | `chk_* = True` (all 8 attestations), both demos | main.py:394-401 → intake.tsx:568-575 | **Artificial attestation** | C5 |
| 4 | `reported_metrics` (0.82/0.64/0.58… and 0.78/0.56/0.48…) | main.py:316-359 | Demo developer claims. They match the demo MDD text, so this is legitimate as "reported" input. | They become the "champion" metrics in Stage 4 (C1) |
| 5 | R4.7 `"status": "PASS"` | val_replication_core.py:691 | **Hard-coded result** | H1 |
| 6 | `tpr = fpr × AUC` challenger curve | performance.tsx:338 | **Synthesised chart data** | H8 |
| 7 | `algorithm = "XGBoost"` default | challenger.tsx:365 | Hidden default | H3 |
| 8 | `modelName ‖ "Logistic Regression"`, `targetCol ‖ "default"` | performance.tsx:100-104; regulatory.tsx:254-255 | Hidden defaults | H12 |
| 9 | Inventory placeholders "Unknown", "Risk", "1.0", "Internal", "PD (Probability of Default)" | main.py:4230-4239; persistence.py:1519-1555 | Placeholder metadata persisted as real | H10 |
| 10 | `regulatory_references` fallback `["IFRS 9","SS11/13","SS1/23"]` | main.py:4710-4714, 4841-4845 | Default label when no rule source exists | Low: cites frameworks no rule referenced |
| 11 | `pd_multiplier: 2.5` (6.2c) | validation_stress_core.py:67 | Scenario assumption | Legitimate if disclosed. Currently dominates the headline (H9). |
| 12 | Thresholds 0.70 / 0.40 / 0.60 / 0.50 / 0.55 / 0.25 / 0.30; R4 tolerances 0.03 / 0.05 / 0.02; PSI 0.10/0.25; backtest 3%/6% | main.py, val_replication_core.py, validation_stress_core.py | **Legitimate configuration** | Not fabrication, but should be versioned and documented (L2) |
| 13 | Seeds "42,43,44,45,46", `random_seed=42`, `cv_folds=5`, `test_size=val_size=0.15` | main.py:4082-4086 | Defaults | Legitimate, but they override the developer's settings because the frontend never sends them (C3) |
| 14 | `lib/mock-data.ts` | aegis-frontend/src/lib/mock-data.ts | Mock file | **Not imported anywhere** (verified by grep). No impact. Recommend deleting. |

No `Math.random`/`np.random` metric generation and no static metric arrays were found in the validation or replication paths.

---

## 6. Frontend-to-backend API trace

### 6.1 Model Replication (Stage 3), full trace

```
Run Replication button (challenger.tsx:1361)
 └─ runReplication() (625)
     ├─ guards: activeFile, targetCol, modelIdentity, algorithm
     ├─ FormData: file | (csv_text never sent, activeFile always wins), model_name, algorithm,
     │            intake_json, target_col, test_size, val_size, mdd_file?, model_params_json?,
     │            model_params_source?, reported_json?
     │   NOT sent: random_seed, cv_folds, seeds, preprocessing/FE config, model_id, dataset hash
     └─ POST /validation/replication (main.py:4075)
         ├─ _read_dataframe (944)
         ├─ resolve_replication_model_inputs (158)
         ├─ model_params → replication_config_source (4143-4158)         [H2]
         ├─ reported = reported_json ⊕ extract_metrics_from_mdd(MDD)      [H5, M5, M8]
         ├─ register_validation_run → model_inventory.json (BEFORE fit)   [H10, M11]
         ├─ run_replication (core:312)
         │   ├─ _fit_core: detect types → prepare_data → split_data(seed=42)
         │   │   → (FE off) → estimator(defaults ⊕ params) → train_model(use_cv=True)
         │   │   → predict_proba → compute_binary_metrics(threshold=F1-opt) + gini + ks
         │   ├─ seed loop: 5 re-splits + refits (no CV)                   [real]
         │   └─ ablation: one refit per feature                           [real]
         ├─ evaluate_replication_checks → R4.1–R4.8 (R4.7 hard-coded)     [H1]
         ├─ _build_performance_report → curves, CM, calibration, metric_checks,
         │   compliance_findings (ValidationAgent2 Stage 5)               [M2, M3]
         └─ persistence.log_event(stage="replication", summary{business_model_name,
             dataset_name, algorithm, config_source, metrics, flags}, full_payload)
 ← response {stage, flags, report{replication{result,checks}, metrics, roc_curve, …}}
 └─ setReplication / setFlags / setPerformanceReport / ds.setValidationStage4Result
     ├─ Reference vs Replicated table ← metrics + *form state* reported  [H5]
     ├─ R4 table ← checks (renders as-is)
     ├─ Seed chart ← result.seed_aucs; Ablation chart ← result.ablation
     └─ Performance tab ← report.metrics, roc/pr/cm/calibration/score bins
         (metric_checks and compliance_findings are NOT rendered)
```

### 6.2 Response-field parity, Stage 3

| UI element | Field | Backend source | Status |
|---|---|---|---|
| Replicated column | `report.replication.result.metrics.*` | `_fit_core` → `compute_binary_metrics` | ✅ real (T4) |
| Reported column | form `reported` state | — (not returned) | ❌ H5 |
| Status per metric | R4.2/4.3/4.4/4.8 `status` | `evaluate_replication_checks` | ✅ real (T2) |
| R4.7 status | `checks[R4.7].status` | literal "PASS" | ❌ H1 |
| "x/y checks passed", Passed/Failed pill | derived from `checks` | frontend | ⚠️ H4 |
| "Completed in Ns" | `result.timing_s` | `time.time()` delta | ✅ real |
| Configuration line | `result.replication_config_source` | request-derived | ⚠️ H2 |
| Seed chart | `result.seed_aucs` | real refits | ✅ |
| Ablation chart | `result.ablation` | real refits | ✅ |
| KPI strip | `report.metrics` | same fit as above | ✅ |
| Train/Test AUC Gap | `report.train_test_auc_gap` | CV mean vs test AUC | ⚠️ M2 |
| ROC/PR/CM/Calibration/Score dist. | `report.*` | computed from `y_test`, `y_proba` | ✅ (CM total = test_n, T4) |

### 6.3 Other stages

| UI stage | Field shown | Source | Status |
|---|---|---|---|
| 1 Intake: Target definition card | `display.targetDefinition` | literal strings | ❌ C5 |
| 1 Intake: Readiness strip | local form state | frontend | ✅ real, but counts filename-only uploads (H11) |
| 4 Benchmarking: Champion row | `report.metrics` | **MDD-overwritten** | ❌ C1 |
| 4 Benchmarking: Challenger row | `report.benchmark.metrics` | real fit | ✅ |
| 4 Benchmarking: ROC overlay, challenger | `fpr × auc` | frontend synthesis | ❌ H8 |
| 5 Stress: PSI / scenarios | `report.psi`, `macro_scenarios` | real computation, flawed design | ⚠️ H9 |
| 5 Stress: Backtest | `report.backtest` | real, index-aligned (fixed bug documented at stress_core:362-368) | ✅ (in-sample, not out-of-time) |
| 6 Regulatory checks 7.1–7.4 | `checks` | keyword presence | ⚠️ H7 |
| 7 Findings: verdict, "Replicated AUC" | `/stage8/findings` with Stage 4 metrics | claim-substituted | ❌ C2 |
| Overview: "Champion ROC-AUC" | `validationStage5Result.report.roc_curve.auc` | MDD-overwritten / stale legacy | ❌ C1, C4 |

---

## 7. Model and dataset lineage assessment

| Lineage element | Captured at development? | Used by replication? | Verified? |
|---|---|---|---|
| Model identity (model_id) | Yes, `MOD-xxx` in inventory | No. Replication uses a free-text name; inventory creates a separate `VAL-xxx` | No |
| Trained artifact | Yes, base64 in `trainingResult.model_artifact` (memory only, never persisted server-side) | No | No |
| Algorithm | Yes, inventory `algorithm` | No (H3) | No |
| Hyperparameters | Yes, `training_config`, `training_info.best_params` | Only if same browser session and same name (C3) | No (H2) |
| Training dataset | `dataset_name`, row and column counts | Filename only | No hash |
| Target | Yes | Typed / guessed | No |
| Preprocessing treatment map | Yes (Data Prep step) | No. Re-derived automatically | No |
| Feature engineering plan | Yes | No. Always off | No |
| Split config / seed | Yes (`split_config`) | test/val size only if `trainingConfig` in session; seed never | No |

**Assessment:** lineage is not enforced anywhere in the validation workflow. The only identity link between development and validation is a case-insensitive name match used for inventory cross-referencing (`persistence._find_development_inventory_entry`). Nothing proves that the model, data or configuration validated is the one that was developed.

---

## 8. Replication methodology assessment

| Question | Answer | Evidence |
|---|---|---|
| Does replication genuinely execute? | **Yes.** A real fit with 5 seed refits and one ablation refit per feature. | T1, T3 (deterministic), T4 (AUC from ROC points = reported AUC; CM total = test_n) |
| Is the original model correctly identified? | **No.** It is free text plus an algorithm dropdown defaulting to XGBoost. | C3, H3 |
| Are the original training dataset and features reused? | **No guarantee.** Whatever file is active or uploaded is used, with no hash check. | C3 |
| Are model parameters preserved? | Only in the same-session, same-name case. When supplied and valid they are applied (T9). Invalid keys are silently dropped (T8). | C3, H2 |
| Is preprocessing configuration preserved? | **No.** There is no input for it. FE is always off. | T11 |
| Is the same split/seed used? | Default seed 42 is always used. Sizes come from the form. | C3 |
| Is the replicated model actually trained? | **Yes.** | T1 |
| Are original and replicated metrics calculated independently? | There are no "original" metrics computed at all. The "original" side is user-typed or MDD-extracted claims. The replicated side is computed. | C3, H5 |
| Are differences calculated from actual results? | Yes, against whatever "reported" dict the backend received (T2). The UI's Δ column uses form state instead. | H5 |
| Does replication status reflect execution? | R4.1 does (T5, T6, T10 → FAIL + "Training failed" banner). R4.7 does not (H1). The summary pill can say "Passed" with nothing compared (H4). | |
| Can failed replication appear successful? | A **training** failure cannot: it is surfaced correctly. A **check-evaluation** failure can ("Passed 0/0", H4). A **failed run still registers in the inventory** as an active validation (H10). | |

**Conclusion:** Stage 3 is an honest *independent re-fit*. It is not a *replication* in the model-risk sense (SS1/23 P4 / SR 11-7 "reproduce developer results"), because neither the developer's artifact nor the developer's full configuration is used.

---

## 9. Persistence and historical retrieval assessment

| Question | Finding |
|---|---|
| Where are results stored? | CSV index `24-06/app_data/validation_pipeline_log.csv` (one row per run: run_id UUID4, ISO timestamp, stage, JSON summary, artifact path) plus a full JSON per run at `app_data/artifacts/validation_pipeline_log/<stage>/<run_id>.json`. Model Inventory is in `app_data/model_inventory.json`. The browser keeps a copy in `localStorage["aegis_dataset_state"]` (app-context.tsx:254-285). |
| Persisted or React-only? | Backend-persisted: replication, performance, stress, fairness, findings, conceptual soundness, intake draft. **Not** persisted: Stage 2 data validation (`/validation/stage2/run` has no `log_event`), the manual stress shock, and Stage 6 `/stage7/run` compliance checks. |
| Correct run retrieved? | Stage 3: yes when names match (T15). Broken for csv_text/demo datasets (M1). Stage 4: no (C4). Others: newest of any model (H13). |
| Latest-run endpoint correctness | `persistence.get_latest` correctly filters by stage and optional model/dataset (T15). Ties are broken by ISO string (fine). The `log_file` parameter is unvalidated (M10). |
| Stale results from previous models? | **Yes**: Stage 4 (legacy row, AUC 1.0), Stress, Fairness, Findings, Overview (H13, C4). |
| Refresh behaviour | Assessed from code, not in a browser (see §12). `ds.file` is not persisted, so after a refresh the dataset is rebuilt from `profile.csv_text` under the name `"<name>.csv"`. Stage 3 restores from localStorage (`validationStage4Result`), and if that is empty, server resume fails for demo/csv_text datasets (M1). Stage 4 restores the stale legacy row (C4). `trainingResult.model_artifact` is dropped on refresh by design (app-context.tsx:253). |
| IDs and timestamps real? | **Yes.** UUID4 run_ids are unique (T15). Timestamps come from `pd.Timestamp.now()` at log time. Artifact round-trip via `/history/artifact` equals `/history/latest` (T15). Inventory IDs (`MOD-001`, `VAL-001`) are sequential and real. |
| Growth | 5.7 GB (L3). |

---

## 10. Prioritised remediation plan

### P0 — before any management demo

1. **C1**: stop overwriting computed metrics in `/validation/performance`. Return `computed_metrics` and `reported_metrics` separately and grade on computed.
2. **C2**: feed Findings from Stage 3 replication. Add "stage not performed" HIGH findings. Populate `stated_auc`. Block APPROVED without the mandatory stages.
3. **C4 / H13**: fix the Stage 4 resume key and scope every resume by model and dataset. Archive or ignore legacy `benchmarking` rows (move the log aside before the demo).
4. **C5**: compute the Intake target card from the dataset. Untick attestations. Label demo data.
5. **H1**: make R4.7 a real check, or return SKIP.
6. **H8**: plot a real challenger ROC curve, or remove the series.
7. **H4**: add an "Inconclusive" state. Surface check-evaluation errors.
8. **H6**: map attestation checkboxes into `validationIntakeData`.

### P1 — before relying on results for model-risk sign-off

9. **C3 / H12 / H11 / H3**: build a persisted replication contract (model_id, dataset hash, params, preprocessing, FE, split, seed). Load it in every validation stage. Score the stored artifact alongside the refit.
10. **H2 / H5**: echo `params_applied`, `params_rejected` and `reported_used`, and render from the response only.
11. **H7 / H9**: rework keyword compliance checks and stress design (PSI population, driver mapping, N/A scenarios, unit fix).
12. **H10 / M11**: register in the inventory only on success, with the correct stage. No placeholder metadata.
13. **M4**: add a minimum-sample guard. Ship a realistic demo dataset (≥ 2,000 rows, ≥ 100 defaults).

### P2 — hardening

14. M1, M2, M3, M5, M6, M7, M8, M9.
15. **M10**: whitelist `log_file`.
16. L1–L5: messaging, threshold config, retention, dead code.

---

## 11. Test execution log

**Setup.** The backend folder `24-06` was copied (excluding `app_data`) to a temporary scratch folder, and the FastAPI app was driven in-process via `fastapi.testclient.TestClient`. An assertion at start-up verified that `persistence.APP_DATA_DIR` resolved inside the copy, so **no production data was written**. Data was a seeded synthetic credit dataset (2,500 rows, logistic DGP) plus the shipped demo files. Production `validation_pipeline_log.csv` and artifacts were **read only**, for historical evidence.

Scripts: `C:\Users\adeha\AppData\Local\Temp\claude\c--Users-adeha-Downloads-Final-UI-2-backup\5989599a-7af5-428f-a4d4-a71e3cdc7abe\scratchpad\audit_tests\run_audit_tests.py` and `…\audit_tests\run_followup.py`. Raw results: `…\audit_tests\audit_results.json`.

| # | Scenario (requested category) | Result | Key evidence |
|---|---|---|---|
| T1 | Successful replication, no reported metrics | Executed | HTTP 200, success true, AUC 0.7286; R4.2/4.3/4.4 WARN, R4.8 SKIP, R4.7 PASS; source `registry_defaults_unavailable_config` |
| T2 | Replication vs wrong reported metrics | **Works as designed** | R4.2/4.3/4.4/4.8 FAIL with correct deltas |
| T3 | Determinism | **PASS** | Identical metrics across runs |
| T4 | Independent metric recompute | **PASS** | AUC from returned ROC points 0.7286 = reported 0.7286; CM total 375 = test_n 375 |
| T5 | **Failed replication** (bad target) | Correctly surfaced | HTTP 200, success false, R4.1 FAIL, rest SKIP, no metrics |
| T6 | **Missing model** (unknown algorithm) | Surfaced, but inventory polluted | success false; inventory gained `VAL-002 "Ghost Model"` (H10) |
| T7 | **Missing dataset** | **PASS** | HTTP 400 "Provide a file upload…" |
| T8 | **Missing model params** / bogus params | Defect | No params → registry defaults label ✅; bogus params → label `developer_hyperopt_best_params` with defaults used (H2) |
| T9 | Valid params flow through | **PASS** | `C=0.0005` applied, AUC changed 0.7286 → 0.7208 |
| T10 | Invalid param value | Correctly surfaced | success false, sklearn `InvalidParameterError`, R4.1 flag |
| T11 | **Missing preprocessing configuration** | Defect (by design) | Endpoint has no preprocessing/FE parameter; FE default False |
| T12 | Validation performance with MDD claims (**successful validation**) | **Defect** | Displayed AUC 0.97 (claim) while computed 0.7286; checks PASS on claims (C1) |
| T13 | **Historical retrieval**: Stage 3 scoping | Defect | "Demo A dataset" not found; "Demo A dataset.csv" found (M1) |
| T14 | **Historical retrieval**: Stage 4 key | Defect | `benchmarking` none, `performance` found (C4) |
| T15 | Historical scoping and IDs | Mixed | Scoped lookup correct; unscoped returns other model; run_ids unique; artifact round-trip equal |
| T16 | `log_file` path probe (read-only) | Defect | 120 rows read from outside `app_data` (M10) |
| T17 | **Failed validation** / Findings verdicts | Executed | No inputs → REJECTED (MDD-keyword FAILs); handleProceed intake → 1.2/1.4 HIGH FAILs (H6) |
| F1 | Findings with no replication | **Defect** | APPROVED, "Model meets all regulatory requirements", 0 findings, replicated_auc null (C2) |
| T18 | MDD extraction | Defect | "risks: 0.15" → KS 0.15; "CV mean AUC 0.73" → ROC-AUC 0.73 (M5) |
| T19 | Regulatory keyword checks | Defect | "decline"/"credit risk"/"12 month" → 7.2/7.3/7.4 PASS (H7) |
| T20 | Stress suite | Defect | PSI 0.029 PASS on same split; 6.2a/b no-op 0%; income→DTI (H9) |
| T21 | Intake demo display | Defect | 4.7% / 219,486 / default_12m vs 5.83% / 120 / default (C5) |
| T22 | Demo A replication | Defect | 18-row test set, AUC 0.294; full verdict grid issued (M4) |
| — | Production log (read-only) | Evidence | 59 replication runs: 57 default/unknown config; latest `benchmarking` AUC 1.0 on 2 rows; latest `performance` displays claims contradicting its own CM |

---

## 12. Confirmed working vs unverified

### Confirmed working (with evidence)

- `/validation/replication` trains a real model and computes AUC, Gini, KS and threshold metrics from actual predictions (T1, T4).
- Results are deterministic for identical inputs (T3).
- ROC/PR curves, confusion matrix, calibration and score distribution are computed from the same `y_test`/`y_proba` as the metrics (T4).
- Seed-stability and feature-ablation are real retrains (code: core 404-473; T1 seed AUCs vary realistically).
- R4.2, R4.3, R4.4 and R4.8 compare correctly against whatever reference dict the backend received (T2).
- Training failures surface as `success:false`, R4.1 FAIL and a "Training failed" UI banner. No fallback to sample results (T5, T6, T10).
- Missing dataset is rejected with HTTP 400 (T7).
- Valid developer hyperparameters are applied when sent (T9).
- Challenger model in Benchmarking is genuinely fitted (T12 challenger AUC 0.6702).
- Persistence writes unique UUID run_ids and real timestamps, and artifacts round-trip intact (T15).
- Stage 3 resume scoping by model and dataset works when the names match (T15).
- Backtesting aligns dates by test-row index (code: stress_core 362-368).
- `lib/mock-data.ts` is not imported anywhere.

### Unverified (and why)

| Item | Reason not verified |
|---|---|
| Browser rendering, refresh and localStorage restore | No browser was driven in this audit. Behaviour was inferred from code (app-context.tsx, use-resume-state.ts). Recommend a manual refresh test per stage after fixes. |
| Stage 2/3 LLM checks (`/llm-check`) | Depend on an external LLM provider (Deloitte agent / Ollama). Not called, to avoid network side effects. |
| Fair-lending bias check results | Endpoint traced (uses `_fit_core`, real), but not executed. |
| PDF/DOCX MDD parsing | Only TXT and in-memory strings were exercised. |
| XGBoost / LightGBM / RF replication on realistic data | Only Logistic Regression on synthetic data and XGBoost on the 120-row demo were executed. |
| Model Inventory export / PDF documentation | Out of the validation/replication path. Not exercised. |
| Concurrent-user behaviour | CSV append without locking. Not load-tested. |

---

## 13. Verdict

| Question | Answer |
|---|---|
| **Is Model Validation genuinely functional?** | **Partially.** The engines compute real statistics from real fits, but the workflow does not hold together. Stage 4 grades the developer's claims as measurements (C1). The final verdict ignores replication and can approve without it (C2). Several compliance checks pass on keywords (H7). |
| **Is Model Replication genuinely functional?** | **It executes genuinely, but it does not replicate.** It is a real, deterministic, independent re-fit with honest failure reporting. It does not load the registered model, verify the dataset, or reuse the developer's preprocessing, feature engineering, seed or, usually, hyperparameters (C3). One of its eight checks is hard-coded (H1). |
| **Are displayed results backed by real calculations?** | **Mostly in Stage 3; not in Stage 4, Stage 7 or the Intake demo card.** Stage 4 champion metrics and the ROC "AUC" label are MDD claims. Stage 7 "Replicated AUC" is those claims. The challenger ROC curve and the Intake target/base-rate/sample-size are fabricated. |
| **Are any modules presenting misleading information?** | **Yes**: Benchmarking (C1, H8, C4), Findings (C2, H6), Intake demo (C5), Replication summary and provenance (H1, H2, H4, H5), Regulatory (H7), Stress (H9), Model Inventory (H10), and the Overview tiles (C4, H13). |
| **What must be fixed before demonstrating to management?** | P0 items 1–8 in §10. If they cannot be fixed in time: (a) demo only Stage 3 with a realistic dataset and explicit reference metrics; (b) move `app_data/validation_pipeline_log.csv` and its artifacts aside so no stale run resumes; (c) do not show Stage 4, the Findings verdict or the Intake demo target card; (d) describe Stage 3 as an "independent re-fit", not "replication of the registered model". |
