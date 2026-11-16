# PAGES 10–18 — Model Training & Evaluation: Model Evaluation tab (9 sub-tabs)

**Shared context for all 9 pages:** Frontend `model-training-evaluation.tsx` (Evaluation tab, `EvaluationTab`). Backend: all numbers come from the **same** `/models/train` response's `evaluation_metrics`/`evaluation_data` fields — computed once, server-side, by `24-06/evaluate_new.py`, on the model's real predictions over the actual held-out test split. **The frontend performs zero recomputation of any metric formula** (the one exception: the 4 confusion-matrix-derived ratios — specificity/sensitivity/false-alarm/miss-rate — are computed client-side in JavaScript from the real TN/FP/FN/TP cells). Full formula deep-dive: **§2.4.5–2.4.6**.

---

## PAGE 10 — Evaluation: Summary sub-tab

**A. Visible:** Accuracy 0.934, Precision 0.942, Recall 0.746, F1 0.833, ROC AUC 0.946, PR AUC 0.900, KS Statistic 0.749, Brier Score 0.069, a Threshold Insight card (0.62 threshold, Max F1 83.3%, Precision 94.2%, Recall 74.6%), Model Status block, Classification Report table.

**G. Values:** All 8 top metrics computed by `compute_binary_metrics()` via direct sklearn/scipy calls (`accuracy_score`, `precision_score`, `recall_score`, `f1_score`, `roc_auc_score`, `average_precision_score`, `scipy.stats.ks_2samp`, `brier_score_loss`) at the auto-selected threshold. Classification Report = real `sklearn.classification_report(output_dict=True)`.

**J. What to say:** "Every number on this tab is a direct, standard scikit-learn/scipy metric call against the model's real predictions on data it never saw during training — none of this is estimated or simulated."

**K/L.** "Why is Recall lower than Precision?" → "The auto-selected threshold optimizes F1 specifically, which balances the two — at this cutoff we're being somewhat conservative about flagging defaults, catching about 75% of actual defaulters while keeping false alarms low. A lower threshold would raise recall at the cost of more false positives; that's exactly what the Thresholds tab lets you explore."

---

## PAGE 11 — Evaluation: ROC Curve sub-tab

**A. Visible:** ROC curve (AUC=0.946) vs. a diagonal random-classifier reference line.

**G. Values:** Real curve from `sklearn`-equivalent ROC point computation over actual test-set scores — **not** an approximation (contrast with the *synthetic* "Benchmark" ROC overlay on Validation Stage 4, Page 27, which is a mathematical approximation from one AUC number — these two charts look similar but are fundamentally different in provenance; do not conflate them if asked).

**J.** "This is a genuine, point-by-point ROC curve computed from this model's actual test-set predictions."

---

## PAGE 12 — Evaluation: PR Curve sub-tab

**A. Visible:** Precision-Recall curve (PR-AUC=0.900) vs. a baseline reference (the dataset's positive-class rate).

**G. Values:** `average_precision_score` plus the real precision/recall pairs swept across thresholds. More informative than ROC-AUC on an imbalanced portfolio since it focuses on the minority (default) class.

**J.** "PR-AUC is usually the more honest metric on an imbalanced book like ours — it doesn't get inflated just because most loans don't default."

---

## PAGE 13 — Evaluation: Confusion Matrix sub-tab

**A. Visible:** TN 3,795 / FP 49 / FN 273 / TP 800, at threshold T=0.62, plus Specificity 98.7%, Sensitivity 74.6%, False Alarm 1.3%, Miss Rate 25.4%.

**G. Values:** `sklearn.confusion_matrix` at the resolved (auto or manual) threshold. **The 4 derived ratios are computed in the frontend, not the backend**: Specificity=TN/(TN+FP), Sensitivity=TP/(TP+FN), False Alarm=FP/(FP+TN), Miss Rate=FN/(FN+TP) — simple, correct textbook formulas, just computed client-side.

**I.** Miss Rate (25.4%) is the credit-risk-critical number here: roughly 1 in 4 actual defaulters are not flagged by the model at this threshold — worth having ready as the honest cost/limitation framing.

**K/L.** "What does a missed default cost us?" → "That's exactly the Miss Rate figure — 273 of the 1,073 actual defaulters in the test set weren't flagged at this threshold. Lowering the threshold would catch more of them at the cost of more false alarms on good loans; the Thresholds tab shows that full tradeoff curve."

---

## PAGE 14 — Evaluation: Score Distribution sub-tab

**A. Visible:** Overlaid histogram of predicted default probability, split Non-Default (green) vs Default (red), at T=0.62.

**G. Values:** `compute_score_distribution()`, **40 equal-width bins** (HARDCODED), built from the model's real `predict_proba` output on the held-out test set. **Confirmed real held-out predictions, not synthetic data.**

**I.** A well-separated distribution (defaults clustered high, non-defaults clustered low) is visual evidence of discriminative power complementary to the ROC-AUC number.

---

## PAGE 15 — Evaluation: Thresholds sub-tab

**A. Visible:** Precision/Recall/F1 curves swept across decision thresholds, with a "Best F1 @ 0.62" marker.

**G. Values:** `compute_threshold_analysis()` sweeps the **identical** 99-point grid (`np.linspace(0.01,0.99,99)`) used by `select_best_threshold()` — the marked point and the reported `threshold_used` are guaranteed to agree, by shared-code construction.

**J.** "This chart and the auto-selected threshold on the Training tab are generated from the exact same 99-point sweep, so they can never disagree with each other."

---

## PAGE 16 — Evaluation: Lift sub-tab

**A. Visible:** Cumulative Gains chart and Lift Curve, model vs. random selection, by decile.

**G. Values:** `compute_gain_chart`/`compute_lift_chart`, **10 deciles** (HARDCODED). Cumulative gain = % of all actual positives captured by that decile of highest-scored applicants; lift = cumulative gain ÷ cumulative % of population reviewed.

**I.** Business framing: "If we only manually reviewed the top decile of highest-risk-scored applications, how many actual defaulters would we catch?" — this chart answers that directly.

---

## PAGE 17 — Evaluation: Residuals sub-tab

**A. Visible:** "Potential heteroscedasticity" risk flag, Residual Correlation 0.371, Variance Ratio 40.9×, Residual Variance by Score Bin bar chart (5 bins).

**G. Values:** `compute_heteroscedasticity_check()` — Residual Correlation = Spearman correlation between predicted score and `|residual|`; bins are **quantile** (equal-count, not equal-width) via `pd.qcut`, **5 bins** (HARDCODED); Variance Ratio = max/min positive bin variance. **Flag trigger: `|Spearman|>0.35 OR variance_ratio>4`** (both HARDCODED) — either alone is sufficient. Requires ≥25 rows or returns "Not enough data" (HARDCODED minimum).

**I.** Heteroscedasticity here means the model's prediction error size isn't constant across the risk spectrum — typically the model is less precise in one score range (often the highest-risk band) than another. This is a genuine model-diagnostic signal, not decorative.

**M.** The bar-chart's color thresholds (amber >85% of max variance, blue >40%) are cosmetic frontend-only and unrelated to the actual 0.35/4× statistical flag — don't describe the colors as reflecting the statistical threshold.

---

## PAGE 18 — Evaluation: Temporal sub-tab

**A. Visible:** Actual vs Predicted Default Rate by period (Quarterly default), "Largest overestimation" callout, "Stability Signal: 16 of 16 periods flagged (>5pp gap)".

**G. Values:** `compute_temporal_analysis_bundle()`, bucketed by the detected origination-date column into Monthly/Quarterly/Yearly (all three precomputed together server-side; the UI toggle just re-indexes, no extra API call). A period is individually "flagged" if `|actual−predicted|>5 percentage points` (**HARDCODED `gap_threshold=0.05`**) — the frontend's literal "(>5pp gap)" copy is a hardcoded string matching this default; if the backend threshold ever changed, this text would go stale silently since no threshold value is returned in the API payload.

**I.** "16 of 16 periods flagged" is a strong, specific, code-verified signal that the model's calibration has drifted across the portfolio's history — exactly the kind of finding a real independent validator would want raised and monitored, which is precisely what Validation Stage 5's Backtesting check does independently (see Page 28).

**K/L.** "Is this the same check as the Backtesting stage in Validation?" → "Related but distinct — this is the Development team's own temporal-stability view, computed on this training run's test split. Validation Stage 5 independently re-derives a backtesting comparison using the replicated model, as a separate, independently-computed check — they should broadly agree, but they are two separate computations, not one number shown twice."

---
