# PAGES 23–26 — Model Validation: Stages 2 & 3

**Note on page ordering:** the reference PDF presents these validation screens out of logical sequence (Stages 2→3→4→5→6 appear before Stage 1). This document covers Stage 1 in its PDF position (Page 30) but you should present the stages in logical order (1→7) regardless of screenshot order. Full deep dive: **§2.6, §2.7**.

---

## PAGE 23 — Validation Stage 2: Data Validation tab

**A. Visible:** "2/4 data validation checks passed" headline with a Pass/Warn/Fail/N-A/Pending donut, a Threshold Checks tile grid (Missing Data Rate FAIL, Forward-Looking, Default Definition, Sampling Strategy, Feature, Class Imbalance, Target Leakage PASS, Duplicate Record PASS), a detail panel, a RAG Agent Rules list, "Regulatory Alignment: CONDITIONAL."

**B. Purpose:** Independently check the dataset itself — before any model result is trusted — against both hardcoded statistical thresholds and cited regulatory requirements.

**D/E. Implementation:** `aegis-frontend/src/routes/validation.data-quality.tsx` → `POST /validation/stage2/run` + `/validation/stage2/llm-check` → `24-06/validation_agent2.py` (threshold checks) + `24-06/source_agent2.py` (RAG rules) + `24-06/llm_providers.py` (LLM call).

**G. Values — the single most important nuance on this screen:** **"2/4" is the count of RAG regulatory rules that matched the selected frameworks and were judged, not the 10 threshold-check tiles below it.** With the default framework selection (IFRS 9, SS1/23, RBI — there is no SS11/13 checkbox anywhere in the platform), exactly 4 of the 15-rule knowledge store's `data_validation`-stage rules apply (one, V03, is SS11/13-sourced and can never match under default settings). The tile grid's own numeric checks (Missing Data Rate FAIL at >20%, Duplicate Record PASS at ≤1% (WARN at >0.1%), Target Leakage PASS at ≤0.95 correlation, Class Imbalance, etc.) are separate, deterministic, and independently computed — but they do **not** drive the "2/4" headline number.

**H.** The 10 threshold checks are fully deterministic (pandas computations against hardcoded cutoffs). The RAG rules are judged by a real LLM call (Deloitte-hosted agent, falling back to local Ollama) — the initial page load shows PENDING stubs instantly (no network call), then a second, slower call fills in real PASS/WARN/FAIL verdicts once the LLM responds.

**I.** This is a genuine two-tier control: cheap deterministic checks catch obvious data problems instantly; the LLM-judged regulatory rules add qualitative, cited assessment (e.g., "does the MDD document the sampling strategy") that a pure threshold check can't capture.

**J.** "The '2/4' you see is specifically counting cited regulatory rules that matched our selected frameworks and came back judged — not the ten quantitative checks in the grid, which are a separate, always-deterministic set. Missing Data Rate failed here because more than 20% of one column's values are missing, which is a hard, code-defined cutoff."

**K/L.** "Why only 4 rules — shouldn't there be more regulatory checks?" → "There are 15 rules total in our regulatory knowledge store for this stage, but one of them is sourced from SS11/13, and we don't currently have an SS11/13 framework option selected on the Intake screen — so it's excluded by design, not a bug. Selecting SS11/13 there would bring the total to 5."

**M.** Be precise that the RAG rule count and the threshold-check count are two independent tallies that happen to share the page — conflating them is the single easiest mistake to make presenting this screen.

---

## PAGE 24 — Validation Stage 2: Conceptual Soundness tab

**A. Visible:** "7/10 conceptual soundness checks passed," a similar donut, a tile grid (Bias and Fairness FAIL, Feature Engineering, Transformation, Model Operating, Hyperparameter, Class Imbalance, Model Methodology PASS, Multicollinearity PASS, Highly Correlated PASS), RAG Agent Rules, "Regulatory Alignment: CONDITIONAL."

**G. Values:** Same mechanism as Page 23. Here, the `conceptual_soundness` stage's RAG rule set genuinely contains exactly 10 rules, **all of which match the default frameworks** — so "7/10" being a RAG-rule count is a **numerical coincidence** with the tile grid also having 10 checks, not a designed link between the two. **Bias and Fairness (check 3.5) is a pure MDD-text keyword search** ("bias","fairness","discriminat","protected","demographic","equal") — binary PASS/FAIL, no WARN state, no actual statistical bias computation on this specific check (the real statistical bias test — the AUC-gap fair-lending check — lives on Validation Stage 6, Page 29, not here). Multicollinearity uses pairwise correlation >0.85 flagged, FAIL if more than 3 columns flagged; Highly Correlated Pairs uses >0.9, FAIL if more than 2 pairs.

**J.** "Bias and Fairness on this tab is a documentation check — did the MDD address bias at all — not a statistical test. The actual quantitative fairness test, comparing model AUC across protected groups, is a separate check on Stage 6."

**K/L.** "So did we actually test for bias here?" → "Not on this specific tile — this one only checks whether the documentation discusses bias and fairness at all. The real statistical test comes later, in Stage 6's Fair Lending Bias Check."

---

## PAGE 25 — Validation Stage 3: Replication tab

**A. Visible:** Dataset & Model selection, Developer Reference Metrics inputs, "Run Replication," "2/8 checks passed" with checks R4.1–R4.8, a Reference vs Replicated Performance table, Replication Stability Across Seeds line chart, Feature Ablation Impact bar chart.

**B. Purpose:** Independently re-train the model from the raw dataset and compare against the developer's reported numbers — the platform's core "trust but verify" control.

**D/E.** `aegis-frontend/src/routes/validation.challenger.tsx` → `POST /validation/replication` → `24-06/val_replication_core.py`.

**G. Values — this is genuinely real, independent re-training, not a cached re-read:** the base fit, the 5-seed stability loop, and the per-feature ablation loop each perform **actual separate `train_model()` calls** on the reviewer's own dataset. **Exact check IDs are R4.1–R4.8** (not "RA.1–RA.8"). Tolerances, all HARDCODED: R4.2 AUC `±0.03`/`±0.06`; R4.3 Gini `±0.05` and KS `±0.03`; R4.4 Accuracy/Precision/Recall/F1 `±5%` relative; R4.5 max feature-ablation AUC drop `<0.05`; R4.6 seed-stability `Std(AUC)<0.02` across 5 default seeds (42,43,44,45,46); **R4.7 is always PASS — hardcoded, performs no actual contamination check**; R4.8 CV mean AUC `±0.02`/`±0.04`. "Reported" values come from Stage 1's MDD extraction (regex-based, not LLM), taking precedence over any separately-supplied training-run metrics per-key.

**I.** This screen is the direct evidentiary answer to "did we just trust what the model developer told us, or did we check it ourselves?" — and the answer here is genuinely "we re-trained it independently," which is a strong, real governance claim you can make confidently.

**J.** "This isn't re-reading a cached result — this literally re-trains the model from the raw data, five separate times with different random seeds to test stability, and once per feature with that feature removed to test dependency, all within this one validation run."

**K/L.** "Why does R4.7 always pass?" → "That check is currently a placeholder — it's intended to confirm no data leaked between the training and test splits during replication, but the code doesn't yet perform that verification; it returns PASS unconditionally. That's a gap worth closing before we'd rely on it as a real control."

**M.** Be upfront and proactive about R4.7 if a Director asks about split reproducibility specifically — don't let this surface as a "gotcha" later.

---

## PAGE 26 — Validation Stage 3: Performance tab

**A. Visible:** Recomputed ROC-AUC/Gini/KS/Accuracy/Precision/Recall/F1/Brier/PR-AUC, "Train/test AUC gap 0.021," ROC curve, Precision-Recall curve, Confusion matrix, Calibration curve, Score distribution.

**G. Values:** Train/test AUC gap = `|CV mean AUC − held-out test AUC|`; PASS if `≤0.10` (HARDCODED). Additional hardcoded performance gates: Recall `≥0.60`, Precision `≥0.50`, F1 `≥0.55`, Brier `<0.25`, PR-AUC `≥0.30`, KS `≥0.30`. All charts are computed from this stage's own replicated model's real predictions — not reused from Development.

**J.** "A small train/test gap like 0.021 here, well inside our 0.10 tolerance, is evidence the replicated model isn't overfit to its own training data."

---
