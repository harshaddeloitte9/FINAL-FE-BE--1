# 2.5 Model Explainability

**Frontend:** `aegis-frontend/src/routes/explainability.tsx` (1,678 lines, 4 tabs).
**Backend:** one endpoint, `POST /models/explain` (`main.py:3400-3533`), backed by `24-06/explainability.py` (377 lines). All four tabs call this **same** endpoint with different parameters — there is no per-tab route.

Every tab's numbers are computed against the **re-derived held-out test split** (`X_test`), reconstructed deterministically using the same `test_size`/`val_size`/`random_seed`/`use_feature_engineering` the model was actually trained with — not a fresh random sample.

## 2.5.1 Feature Importance — global, structural, computed once from the fitted model

`extract_feature_importance()` (`explainability.py:94-136`): tree/ensemble models → `model.feature_importances_` (impurity/gain-based, native to the library); linear models → `|coef_|`. **Not permutation importance, not SHAP.** Real column names come from `get_feature_names_from_fitted_preprocessor()`, correctly handling OHE-expanded and datetime-decomposed columns.

Normalization: `Importance = raw_importance / sum(raw_importance)`, rounded to 5dp — **this already sums to 100% across all features**; the "Relative Weight %" column is the same number ×100. The bar-chart width is a *separate*, purely cosmetic ratio relative to the single largest feature (floored at 2% width for legibility) — don't conflate bar length with the percentage number.

"Show Top N Features" slider: default **15**, min **5** (HARDCODED). The "KEY INSIGHT" text (e.g. "Annual_Income is the most influential factor at 24.20%...") is **dynamically generated JavaScript string interpolation** over the real ranked array — not an LLM call, not static copy.

## 2.5.2 SHAP Analysis — data-grounded, sample-based, model-type-dependent explainer

`compute_shap_values()` (`explainability.py:186-245`):
- **Tree-family models** (name contains XGB/LGBM/Forest/Boosting/Tree) → `shap.TreeExplainer`, computed on the **full requested sample** (up to the slider's value, default **150**, range **50–300** step **50**, all HARDCODED).
- **Everything else with `predict_proba`** → `shap.KernelExplainer(model.predict_proba, background)` where `background` is a 50-row sample and — **important nuance** — the actually-explained set is silently capped at the **first 50 rows only**, regardless of the slider value. Only tree models honor the full slider setting.
- Models without `predict_proba` → SHAP unsupported.

Mean |SHAP| bar chart = `mean(|SHAP value|)` per feature across the sampled rows, top 20 server-side / top 15 in the frontend chart (both HARDCODED caps). The "Samples Used" tile displays the **requested** slider value, not necessarily the true number of rows actually explained (see the KernelExplainer cap above) — a caveat worth having ready if asked.

## 2.5.3 Prediction Reasoning — local, single-row, zero averaging

- **Customer Index** is a positional index into the re-derived `X_test` split (first `max_shap_samples` rows, further capped to 0–49 for non-tree/KernelExplainer models) — **not** a row number in the original uploaded CSV.
- **Prediction / Default Probability**: `pipeline.predict_proba(X_explain)` — the model's real, actual `predict_proba` call, not simulated. Decision rule: `prob ≥ 0.5 → HIGH RISK` (**HARDCODED threshold of exactly 0.5**, hardcoded independently of whatever F1-optimized threshold the Evaluation tab actually uses for real decisions — this inconsistency is worth flagging proactively).
- **Top Prediction Drivers**: the single selected row's own SHAP vector (not an average), paired with that row's own transformed feature values; top 12 by `|SHAP|` magnitude, then split into "Reduces"/"Increases Default Risk" (top 3 each) by sign. Since both lists are subsets of the *same* top-12, one can legitimately come back empty if all 12 happen to share the same sign.
- **"Raw Feature Values for This Customer"** are the **preprocessor-transformed** (scaled/encoded) model-input values, **not** the untouched original CSV cell values — the tab's label means "raw model-input feature vector," not "raw source data." Worth stating precisely to avoid overclaiming.

## 2.5.4 Summary tab — client-side only, no backend PDF generation

"Download Full Report" = `window.print()` (the browser's native print-to-PDF), over already-rendered DOM content. **There is no backend report-assembly endpoint.** Every section (Model Identity, Dataset Summary, Preprocessing Decisions, Feature Engineering Summary, Model Training Configuration, Evaluation Metrics, Explainability Findings) is client-side formatting of data already fetched by earlier pipeline steps and held in React context — nothing is recomputed here.

The two auto-generated narrative blocks ("Model Performance Summary" and "Key Predictors") come from **one Python function**, `generate_model_summary()` (`explainability.py:344-377`) — **deterministic string templating with real numbers plugged in, not an LLM call** (no LLM imports anywhere in this file). Hardcoded quality-band thresholds: ROC-AUC `>0.85`→"excellent", `>0.75`→"good", else "moderate"; Recall `>0.70`→"strong", else "moderate" (both HARDCODED). The "Explainability Method" KPI tile always displays the fixed string **"TreeExplainer"**, regardless of which explainer branch actually ran — a cosmetic inaccuracy for non-tree models.

## 2.5.5 Feature Importance vs. SHAP vs. Prediction Reasoning — the plain-language distinction to use in the room

- **Feature Importance = "what the model is built on."** A structural property read directly off the fitted model object — no data pass required at explanation time. Answers: *"Structurally, which inputs did this model learn to lean on most?"*
- **SHAP Analysis = "what actually moved predictions, on average, across real customers."** Built bottom-up from many individual per-row attributions, averaged. Captures interaction effects Feature Importance can't see, and is sensitive to which rows were sampled — this is *why the two rankings can legitimately differ*.
- **Prediction Reasoning = "why this one customer, specifically, got this score."** Zero averaging — the single row's own SHAP vector, paired with the model's real probability output for that row. The most granular of the three, and it reuses the exact same SHAP computation Tab 2 produces (no second SHAP run).

## 2.5.6 Full hardcoded-value register for Explainability

| Value | Meaning | Citation |
|---|---|---|
| 15 / min 5 | Feature Importance "Top N" default/min | `explainability.tsx:433,981` |
| 150 / 50–300 step 50 | SHAP samples slider default/range | `explainability.tsx:434,1093` |
| 0.5 | HIGH/LOW RISK decision threshold | `main.py:3474`, `explainability.py:312` |
| 50 | KernelExplainer background + explained-row cap | `explainability.py:226,234` |
| 100 | KernelExplainer perturbation samples per row | `explainability.py:236` |
| 20 / 15 | Backend/frontend SHAP summary truncation | `main.py:3463`; `explainability.tsx:545` |
| 12 | Per-row top-driver truncation | `main.py:3493` |
| 0.85 / 0.75 | ROC-AUC "excellent"/"good" quality bands | `explainability.py:359` |
| 0.70 | Recall "strong" quality band | `explainability.py:362` |

---
