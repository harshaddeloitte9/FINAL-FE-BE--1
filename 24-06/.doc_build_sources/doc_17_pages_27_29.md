# PAGES 27–29 — Model Validation: Stages 4, 5, and Stage 6 (tab 1)

Full deep dive: **§2.7.1–2.7.3**.

---

## PAGE 27 — Validation Stage 4: Benchmarking

**A. Visible:** "Challenger: Logistic Regression," a Compare Challenger Models table (ROC-AUC/Gini/Recall/KS/Fit Time per candidate), Champion vs Challenger metrics ("Champion metrics sourced from MDD — Stage 1"), Industry Benchmark Table, a grouped bar chart, an ROC Overlay Chart.

**B. Purpose:** Compare the champion model against an industry-standard challenger before stress testing and regulatory review.

**D/E.** `aegis-frontend/src/routes/validation.performance.tsx` (despite the filename, this is Stage 4) → `POST /models/compare` + `POST /validation/performance` → `main.py` + `24-06/val_replication_core.py`.

**G. Values:** Challenger candidates are **genuinely, independently re-fit** on the same split — real `.fit()` calls, deliberately skipping CV/hyperopt/OOT for speed (ensembles capped at 100 trees). **Champion metrics are the Stage-1 MDD numbers**, per-key-overridden onto a freshly-refit "replica" — so the ROC-AUC 0.78/Gini 0.56/KS 0.48/etc. you see for the champion trace back to Stage 1's intake data, not a new computation here.

**H. Critical accuracy point:** **the "Benchmark" ROC overlay line is a mathematical approximation, not a measured curve** — `TPR_approx = FPR × challenger_AUC`, plotted at the champion's own FPR points, derived from a single AUC number rather than the challenger's actual predicted-probability curve. The champion's own trace **is** real. The code's own in-line comment states this explicitly and the UI legend is correctly labeled "Benchmark (AUC-based)" rather than implying a measured curve.

**I.** Legitimate benchmarking exercise on the challenger-comparison side; the ROC overlay specifically should be presented as an illustrative approximation, not dual measured curves.

**J.** "The challenger models here are genuinely re-trained and compared on the same data split. One nuance to flag precisely: the dashed 'benchmark' line on the ROC chart isn't the challenger's actual measured curve — it's a mathematical approximation built from its single AUC number. The solid champion line is real."

**K/L.** "So is this a fair apples-to-apples ROC comparison?" → "The AUC numbers being compared are both real and independently computed. The visual overlay specifically is where I'd be careful — the challenger's curve *shape* is approximated, not measured, so I wouldn't read fine detail into where the two lines cross on the chart, only into the AUC values themselves."

**M.** This is one of the highest-risk screens to overclaim on — rehearse the ROC-overlay caveat until it's automatic.

---

## PAGE 28 — Validation Stage 5: Stress & Backtesting

**A. Visible:** Run config (Logistic Regression, default dataset, Quarterly granularity), Validation Summary (6 checks: 3 pass, 0 warn, 1 fail, 2 n/a), Sensitivity Analysis (AUC drop on feature removal + Manual Feature Shock tool), Score Stability (PSI) train vs test, Macro Stress Scenarios, Backtesting (predicted vs actual default rate), Directional Testing.

**B. Purpose:** Test the replicated model's robustness to economic stress and its historical predictive accuracy.

**D/E.** `aegis-frontend/src/routes/validation.stress.tsx` → `/validation/stress/run`, `/validation/stress/shock` → `24-06/validation_stress_core.py`.

**G. Values — all genuinely re-score the real trained pipeline, nothing here is simulated or faked:**
- **PSI**: standard formula `Σ(Actual%−Expected%)×ln(Actual%/Expected%)` on train-vs-test predicted-probability distributions, 10 bins; **thresholds genuinely match the textbook convention**: `<0.10` PASS, `0.10–0.25` WARN, `≥0.25` FAIL.
- **Macro Stress Scenarios**: 3 hardcoded scenarios (Adverse: GDP −2%/unemployment +3pp/house prices −10%; Severe: −5%/+6pp/−25%; COVID-style: income −25% plus a flat **×2.5 PD multiplier**). Mechanism: auto-detect driver columns by keyword, mechanically shift those raw values by the fixed percentage, then **re-run the model's real `predict_proba`** on the shocked data — there is no independently-estimated economic elasticity coefficient anywhere; the "sensitivity" to macro conditions is entirely whatever the model already learned from its training features.
- **Manual Feature Shock**: genuinely perturbs a copy of the test set and re-scores it — real, not a lookup.
- **Backtesting**: real historical predictions vs. real observed default rate, by period. Per-period flag `>5pp` gap; **overall PASS/WARN/FAIL uses a separate threshold on the mean gap** (`<3%` PASS, `<6%` WARN, `≥6%` FAIL) — two different hardcoded cutoffs in the same check, worth being precise about.
- **Directional Testing**: "SKIP" status means specifically that the required macro column (unemployment/GDP/credit score, by keyword) wasn't found in the dataset — not an inconclusive computation.

**I.** The macro-scenario mechanism is a legitimate re-scoring exercise but should be framed carefully: it is not the same rigor as a professionally fitted macro-sensitivity/elasticity model — it's "what does our model predict if we mechanically shift these input columns," which is a reasonable stress-test proxy but not an independently validated economic relationship.

**J.** "Every stress result here comes from actually re-running the trained model on perturbed data — nothing is a lookup table result. The macro scenarios use fixed, documented shock magnitudes rather than a separately fitted economic elasticity model, which is worth being transparent about."

**K/L.** "Where do the −2%/−5% macro shock numbers come from — are they calibrated to our portfolio?" → "They're fixed, standard stress-scenario magnitudes coded into the platform, not calibrated per-portfolio or per-model — comparable to a simplified regulatory stress-scenario template rather than a bank-specific econometric model."

**M.** Be ready to distinguish the per-period backtest flag (5pp) from the overall mean-gap verdict bands (3%/6%) if pressed for precision.

---

## PAGE 29 — Validation Stage 6: Explainability and Fairness tab

**A. Visible:** "SHAP Feature Importance (from Stage 3 Replication)" bar chart with "reuses the replicated model's feature importances — no re-training here," a protected-characteristic selector (age), "Run Bias Check," result "[8.2] HIGH — Fair Lending Bias Check — age — FAIL," AUC gap 0.9286 (max 1.0000, min 0.0714), Group-Level Comparison table, AUC by Group bar chart.

**H. Critical accuracy point:** **"SHAP Feature Importance" is not SHAP.** Confirmed by the import statement itself — this module imports `extract_feature_importance` (native tree/linear importance), **not** `compute_shap_values`. The "no re-training here" claim is accurate; the "SHAP" label is not — say "feature importance," not "SHAP," if precision is being tested.

**G. Values:** Protected columns detected by keyword (age, gender, sex, region, ethnicity, race, nationality, marital, education, employment, loan_purpose). Per-group AUC computed with a **minimum-count guard of 10 rows** — groups smaller than that are silently excluded, and **no confidence interval or bootstrap correction** is applied for how noisy a 10–20-row AUC estimate genuinely is. `auc_gap = max(group AUC) − min(group AUC)`; PASS `<0.05`, WARN `<0.10`, FAIL `≥0.10` (all HARDCODED, check ID 8.2).

**I.** This is the platform's real, quantitative fairness test (as distinct from Stage 2's documentation-only Bias-and-Fairness check). A 0.9286 gap with a minimum group AUC of 0.0714 is a genuinely alarming number worth being ready to discuss candidly — but also worth contextualizing honestly: with some groups likely near the 10-row floor, this specific gap estimate carries real statistical noise that the current implementation doesn't quantify.

**J.** "This is our real, quantitative fairness test — comparing the model's discriminative power across age groups. I'd flag one caveat upfront: some of these age groups have very few test-set rows, right at our minimum-count cutoff of 10, so an AUC gap this large partly reflects how noisy an AUC estimate is on that few data points, not necessarily a a settled finding of discriminatory model behavior — it's a strong signal to investigate further with more data, not a final verdict on its own."

**K/L.** "Is this a statistically rigorous bias test?" → "It's a real, code-computed AUC-gap test against a defined regulatory threshold, which is a legitimate first-pass control — but it currently has no confidence interval, bootstrap resampling, or multiple-testing correction, and it will compute an AUC on groups as small as 10 rows. I'd present this as a meaningful screening signal that triggered a FAIL and warrants deeper statistical review, not as the final word on fairness."

**M.** Do not call the top chart "SHAP" in front of the room — correct it to "feature importance, reused from Stage 3" if you catch yourself.

---
