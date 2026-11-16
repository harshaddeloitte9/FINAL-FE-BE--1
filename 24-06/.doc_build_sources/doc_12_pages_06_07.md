# PAGE 6 — Data Preparation: Data Profiling tab

**A. What is visible:** Total Rows/Columns/Missing Values/Duplicate Rows KPIs, Target Variable selector with "1 compliance flag" and quality-check badges, Class Distribution donut (25,630 vs 7,151, 3.58:1), Duplicate & Outlier Signals, Pearson Correlation Matrix heatmap.

**B. Purpose:** Profile the integrated dataset's completeness, class balance, correlations, and compliance signals before preparing it for modelling.

**C. User workflow:** Confirm/change the target column → review the compliance flag and quality-check warnings → inspect class balance and correlation → proceed to Preprocessing.

**D. Frontend implementation:** `aegis-frontend/src/routes/data-preparation.tsx` (Tab 1, `ProfilingTab`). Full deep dive: **§2.3.1**.

**E. Backend implementation:** `_build_data_profile()` via `/data/profile` (re-run only if the target column changes) — the identical function used on Data Upload and Data Quality.

**F. Data flow:** Same `profile` object already in context; a change of target triggers a fresh `/data/profile` call, since leakage detection, imbalance ratio, and task-type detection are all target-dependent.

**G. Every important displayed value:**
- **Rows/Columns/Missing/Duplicates** — pure `df.shape` / missingness / duplicate formulas, identical to Data Quality's numbers (same backend function, same dataset).
- **"1 compliance flag"** — Agent2's `check_data()`; the wired-in checks are R01 (missing>20%), R03 (duplicates>5%), **R04 (ID columns present — presence-only, most likely trigger for ID-shaped columns like Customer_ID/Loan_ID)**, R05 (sample size<500). **Two rules defined in the rules file (R02 class imbalance, R23 macro-missing) are never actually referenced by the check function — orphaned, unused rules.**
- **Class Distribution (25,630 vs 7,151, Rate 3.58:1)** — raw `value_counts()`; ratio = majority/minority. **SOURCE NOT VERIFIED against this repository's own sample data** — the formula is fully confirmed, but these specific numbers come from a dataset uploaded live in session, not a file shipped in this codebase.
- **Outlier signals (Default 21.8%, Loan_Amount 5.2%, etc.)** — 1.5×IQR fence, first 8 numeric columns positionally (same method as Data Quality). Note: **the target column itself, if numeric-typed, is not excluded from this scan** — it's scanned like any other numeric feature.
- **Pearson Correlation Matrix** — first 10 numeric columns positionally, computed on a 5,000-row random sample (seed 42) if the dataset exceeds 5,000 rows — an *estimate*, not exact, on larger portfolios.

**H. Dynamic vs static:** All figures are real computations on the actual uploaded dataset; the specific example numbers quoted in any given screenshot are dataset-dependent, not fixtures baked into the code.

**I. Business/MRM interpretation:** This is the analyst's first real look at whether the target is well-defined, whether the sample is large enough, and whether obvious ID/leakage risks exist before any modelling work begins.

**J. What to say:** "This reuses the exact same profiling engine as the Data Quality page, scoped to whichever target column is currently selected — changing the target re-runs leakage and imbalance detection specifically for that target."

**K. Likely questions:** "Why does correlation only show 10 columns?" / "Is the correlation matrix exact?"

**L. Answers:** "It's capped at the first 10 numeric columns by dataset order, for readability and performance — not by importance. On datasets over 5,000 rows, it's computed on a fixed random sample rather than the full data, so treat it as a representative estimate on large portfolios, not an exact figure."

**M. Risks/limitations:** Correlation matrix and outlier scan are both positional (first-N), not importance-ranked — a highly important column past position 10 (correlation) or 8 (outliers) simply won't be shown here.

---

# PAGE 7 — Data Preparation: Preprocessing & Feature Engineering tab

**A. What is visible:** A dense, multi-section tab: split configuration, class distribution per split, missing-value treatment cards, skew-driven transform proposals, preprocessing strategy summary table, feature engineering summary (Original/Final/Added/Removed features), feature importance bar chart, engineered dataset preview.

**B. Purpose:** Turn the profiled raw dataset into a leakage-safe, model-ready feature matrix, with every transformation decision visible and reviewer-confirmable.

**C. User workflow:** Set test/validation split → review/override per-column missing-value treatment → confirm skew transforms → review the strategy summary → move to Feature Engineering (WOE/interactions/binning) → confirm feature removals → preview the engineered dataset → proceed to Model Training.

**D. Frontend implementation:** `aegis-frontend/src/routes/data-preparation.tsx` (Tab 2, `PreprocessingFeaturesTab`). Full deep dive: **§2.3.2–2.3.4**.

**E. Backend implementation:** `/data/preprocess`, `/data/drop-impact`, `/data/feature-engineering` (`main.py`) → `24-06/preprocessing_new.py` + `24-06/feature_engineering.py`.

**F. Data flow:** `profile`+`file` → stratified split (fit on TRAIN only) → missing-value classification/imputation → outlier winsorization → scaling/encoding/transform → `preprocessingResult` written to context → feature-engineering step reads that plus the split again (⚠ using its **own hardcoded** 0.15/0.15/42 split, not necessarily matching what the reviewer set) → `featureEngineeringResult` written to context.

**G. Every important displayed value:**
- **Split sliders** default 0.15/0.15 (test/val), range 0.05–0.45; **random seed is not exposed in the UI at all** — fixed to 42 to match the backend default.
- **Missing-value treatment** — `classify_missing_treatment()` decision tree: `>40%` missing→review-flag (excluded), categorical→"Unknown" fill, binary/structural-zero numeric→zero-fill, else→statistical (MICE if strong correlator present and missing>15% or rows>100k; KNN if strong correlator present; else median).
- **Outlier handling** — automatic, not user-selected: every numeric column is Winsorized to the 1st/99th percentile; scaler choice uses a **3×IQR** rule (RobustScaler if outlier fraction >2%, else StandardScaler) — note this is a *different* IQR multiplier from the Profiling tab's 1.5×IQR outlier-flagging scan.
- **Encoding** — OneHot if cardinality ≤8, else Ordinal.
- **Transform recommendation** — skew-based (log1p / Yeo-Johnson / none), with an automatic "ineffective" downgrade if the transform doesn't reduce skew by ≥30%. **Nothing auto-applies** — only the reviewer's confirmed choices reach the real pipeline.
- **Feature Engineering summary (Original/Final/Added/Removed Features)** — real shape-before/after counts. Added features can include `_log`, `{a}_x_{b}` interactions (top 8 features, max 10 interactions, min IV 0.02), `_bin` quantile buckets, `_freq` frequency encodings, `_woe` (top 8 by Information Value). Removed features are either reviewer-confirmed or a fallback rule (correlation >0.90, near-constant >99% single value, IV<0.02).
- **Feature Importance bars** — first non-empty of Gini (`2×AUC−1` per column) → Information Value → Mutual Information, in that priority order.

**H. Dynamic vs static:** Every number here is a real, deterministic statistical computation — **confirmed zero LLM calls anywhere in this tab's backend code.**

**I. Business/MRM interpretation:** This is the leakage-control heart of the platform: fitting every transformation on TRAIN only and applying it unchanged to val/test is exactly the discipline model-risk reviewers look for, and it's genuinely implemented here, not just claimed.

**J. What to say:** "Every transformation — imputation, winsorization, scaling, encoding — is fit exclusively on the training split and applied unchanged to validation and test, which is the standard leakage-safe pattern. All of the proposed treatments are fully deterministic statistics; there's no AI or LLM involved anywhere in this screen — the reviewer confirms or overrides every choice before it's applied."

**K. Likely questions:** "How do you decide MICE vs KNN vs median?" / "Does feature engineering respect the split I chose?"

**L. Answers:** "It's rule-based on two things: whether the column correlates strongly with another predictor, and how much data is missing — MICE for larger/harder cases, KNN for moderate, median as the simple fallback, always fit on train only. One caveat worth flagging: the Feature Engineering step currently re-splits internally at a fixed 70/15/15 with seed 42, regardless of what split ratio you set on this same screen's Preprocessing step — that's a known inconsistency we should align."

**M. Risks/limitations:** The split-ratio mismatch between Preprocessing and Feature Engineering (§F above) is a genuine implementation inconsistency, not a design choice — be ready to acknowledge it plainly rather than defend it. The "Regulatory insights" panel referenced defensively in the frontend code is currently dead — no backend endpoint populates it, so it will never appear.

---
