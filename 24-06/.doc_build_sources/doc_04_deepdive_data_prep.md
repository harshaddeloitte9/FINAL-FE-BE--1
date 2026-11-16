# 2.3 Data Preparation & Feature Engineering

**Frontend:** `aegis-frontend/src/routes/data-preparation.tsx` (3,051 lines, two tabs).
**Backend:** `24-06/preprocessing_new.py` (the live implementation — `preprocessing.py` is an 8-line compatibility shim that just re-exports it), `24-06/feature_engineering.py`, `24-06/train_new.py` (for `split_data`).

## 2.3.1 Tab 1 — Data Profiling

Reuses `_build_data_profile()` (same function as Data Quality). New elements specific to this tab:

- **Target detection chain**: `detect_column_types()` → `detect_target_candidates()` → `detect_task_type()` → `_infer_target_column()` (`utils.py`). Tier A candidates are exact-name matches (`default`, `bad`, `target`, `churn`, `npl`, …) that are binary; Tier B (only if Tier A is empty) is any binary 0/1 column with positive rate **1%–50%** (HARDCODED DEFAULT), tie-broken toward names containing "default"/"bad".
- **"1 compliance flag"** = Agent2 (`24-06/agent2.py`, rules from `24-06/rag_store/rules.json`). Confirmed rule set actually wired into `check_data()`: **R01** missing>20% (HARDCODED THRESHOLD), **R03** duplicates>5% (HARDCODED THRESHOLD), **R04** ID columns present (presence-only, no threshold), **R05** sample size<500 rows (HARDCODED THRESHOLD), plus an inline macro-keyword-missing check and an inline target-leakage check. **R02 (class imbalance) and R23 (macro variables missing) are defined in `rules.json` but never referenced by `check_data()` — orphaned/unused rules.**
- **Class imbalance ratio**: identical formula and threshold (`>3.0`) as the Data Quality page — same backend field, same number, shown on both screens.
- **Outlier scan**: identical to Data Quality (first 8 numeric columns, 1.5×IQR, 2% flag threshold) — same numbers appear on both pages.
- **Correlation matrix**: `df.sample(n=min(5000,len(df)), random_state=42).corr(method="pearson")` on the **first 10 numeric columns positionally** (not selected by variance/importance) — for datasets over 5,000 rows this is an *estimate*, not an exact matrix (HARDCODED DEFAULTS: 5,000-row cap, seed 42, 10-column cap).

## 2.3.2 Tab 2 — Preprocessing

**Split**: `test_size=0.15, val_size=0.15, random_seed=42` (HARDCODED DEFAULT, both UI initial state and backend `Form(...)` defaults) — reviewer-adjustable via sliders on this screen (range 0.05–0.45, step 0.05). **Random seed is not exposed in the UI at all** — hardcoded to 42 client-side to match the backend default. Split function `split_data()` (`train_new.py:78-113`): stratified `sklearn.train_test_split`, two-stage (test carved off first, then val carved from the remainder, re-normalized: `adjusted_val = val_size/(1-test_size)`), falls back to unstratified on a `ValueError`.

**⚠ Important inconsistency to flag**: `/data/feature-engineering` **hardcodes its own internal split at `test_size=0.15, val_size=0.15, random_state=42`**, ignoring whatever the reviewer set on the Preprocessing sliders — the two steps can silently diverge on split composition (`main.py:2385-2388`).

**Missing-value treatment** — `classify_missing_treatment()` (`preprocessing_new.py:247-368`), decision order:
1. `missing_pct > 0.40` (HARDCODED DEFAULT `REVIEW_MISSING_THRESHOLD`) → `"review_flag"` (excluded from imputation).
2. Categorical → `"unknown_category"` (literal `"Unknown"` fill).
3. Numeric, exactly 2 unique values → `"zero_fill"` (binary pattern).
4. Numeric, non-negative integer, mode=0, skew>1.0 (HARDCODED) → `"zero_fill"` (structural-zero pattern).
5. Else → `"statistical"`.

**Statistical imputation method choice** — `select_imputation_strategy()` (`preprocessing_new.py:567-706`):
```
n_strong = count of columns with max|corr with any predictor| ≥ 0.3   (HARDCODED)
if n_strong>0 and (missing_pct>0.15 or n_rows>100,000):  →  MICE       (HARDCODED)
elif n_strong>0:                                          →  KNN
else:                                                     →  Median
```
Applied by `SemanticImputer`, fit on TRAIN only, transformed unchanged onto val/test — **leakage-safe by construction**.

**Outlier treatment is automatic, not a separate UI selector.** Every numeric column is **always Winsorized** (clipped to 1st/99th percentile, HARDCODED, learned on TRAIN) before scaling. Scaler choice (`analyze_numeric_column()`, `preprocessing_new.py:178-220`) uses a **3×IQR** rule (note: different multiplier from the Data Quality/Profiling 1.5×IQR outlier scan): `outlier_frac>2%` → RobustScaler, else StandardScaler.

**Encoding**: `cardinality ≤ 8` (HARDCODED) → OneHot; `>8` → Ordinal.

**Numeric transform recommendation** — `recommend_transform()` (`preprocessing_new.py:56-175`), single source of truth:
```
|skew|<0.5        → none
0.5≤|skew|<1.0    → none (optional)
|skew|≥1.0, all>0 → log1p
|skew|≥1.0, has 0/neg → yeo_johnson
then: if post-transform skew isn't reduced by ≥30% (HARDCODED), downgrade back to "none"
```
**Nothing auto-applies this** — it's a proposal; the reviewer confirms via the "Skew-Driven Transforms" card, and only confirmed choices (`transform_choices`) reach the actual pipeline.

## 2.3.3 Tab 2 — Feature Engineering

- **Gini** = `2×AUC−1` per numeric column (own `roc_auc_score` vs target, flipped if `<0.5`), binary task only, capped at 40 columns (HARDCODED `MAX_IV_FEATURES`).
- **IV (Information Value)** — WOE/quantile-binned, binary task only.
- **MI (Mutual Information)** — `sklearn.mutual_info_classif`, `random_state=42`.
- Feature-importance bar chart picks the **first non-empty** of Gini → IV → MI, in that priority order — not a blend.
- **Added features**: `_log` (confirmed log1p only), interaction terms (`{a}_x_{b}`, top **8** features considered, max **10** interactions, min IV **0.02** — all HARDCODED), `_bin` quantile buckets (numeric `nunique>20` → 5 buckets, HARDCODED), `_freq` frequency encoding (categorical `nunique>8`, HARDCODED), `_woe` (top **8** by IV, HARDCODED `MAX_WOE_FEATURES`).
- **Removed features**: reviewer's explicit `confirmed_remove_cols`, OR fallback = one of each highly-correlated pair (`|corr|>0.90`, HARDCODED), near-constant columns (`nunique≤1` or top-value share `>99%`, HARDCODED), low-IV columns (`IV<0.02`, HARDCODED).
- **No LLM anywhere in this module** — confirmed via exhaustive grep for `llm|ollama|openai|gpt|anthropic` across `preprocessing_new.py` and `feature_engineering.py`: zero matches. All proposals are deterministic statistics.
- **"Regulatory insights" panel is dead code** — the frontend defensively reads `summary.regulatory_alerts`, but **no backend endpoint ever populates this field** (confirmed by full-repo grep) — this panel can never render in the current build.

## 2.3.4 Drop-Impact analysis (on-demand, per sparse column)

`estimate_drop_impact()` (`preprocessing_new.py:433-565`): quick quantile-binned IV estimate (5 bins, HARDCODED), redundancy flagged if `|corr|≥0.60` with another feature (HARDCODED), verdict — `IV<0.10`→"safe to drop", `IV<0.30`→"caution", else→"risk" (all HARDCODED).

## 2.3.5 Full hardcoded-value register for Data Preparation

| Value | Meaning | Citation |
|---|---|---|
| 0.15/0.15/42 | Default split (Preprocessing screen, reviewer-adjustable) | `main.py:1995-1997` |
| 0.15/0.15/42 | **Non-overridable** split for Feature Engineering endpoint | `main.py:2386-2388` |
| 0.40 | Missing% forcing "review_flag" | `preprocessing_new.py:244` |
| 0.3 | "Strong predictor" correlation for MICE/KNN routing | `preprocessing_new.py:653` |
| 0.15 / 100,000 | Missing%/row-count triggers choosing MICE over KNN | `preprocessing_new.py:662` |
| 0.5 / 1.0 / 30% | Skew thresholds + min reduction for transform choice | `preprocessing_new.py:111,118,147` |
| 8 | Cardinality cutoff: OneHot (≤8) vs Ordinal (>8) | `preprocessing_new.py:231` |
| 3.0× IQR | Scaler-choice outlier rule (different from 1.5× profiling rule) | `preprocessing_new.py:196` |
| 0.01/0.99 | Winsorizer clip percentiles | `preprocessing_new.py:1290,1308,1316` |
| 0.90 | Multicollinearity removal threshold | `feature_engineering.py:41,517` |
| 0.99 | Near-constant "top value share" threshold | `feature_engineering.py:1105` |
| 0.02 (IV) | Low-IV removal threshold | `feature_engineering.py:991` |
| 8 / 5 | `nunique` cutoffs for `_freq` / `_bin` features | `feature_engineering.py:1053-1067` |
| 8 | `MAX_WOE_FEATURES`, `TOP_FEATURES_FOR_INTERACTIONS` | `feature_engineering.py:21,36` |
| 40 | `MAX_IV_FEATURES` | `feature_engineering.py:20` |
| 0.60 | Drop-impact redundancy correlation threshold | `preprocessing_new.py:383` |

**SOURCE NOT VERIFIED**: the specific example figures often quoted for this screen (e.g. 25,630 vs 7,151 records, 3.58:1 ratio, named columns like `Collateral_ID`/`Linked_Loan_Ref`) are not reproducible from any dataset shipped in this repo — the *formulas* above are fully verified; the *specific numbers* depend on whatever dataset is loaded live in a session.

---
