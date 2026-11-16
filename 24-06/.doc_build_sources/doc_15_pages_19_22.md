# PAGES 19–22 — Model Explainability (4 tabs)

**Shared context:** Frontend `explainability.tsx`. Backend: one endpoint, `POST /models/explain`, three different parameter combinations. Full deep dive: **§2.5**.

---

## PAGE 19 — Explainability: Feature Importance tab

**A. Visible:** "Extracted importance for 36 features with real column names," a "Show Top N Features" slider (default 15), a ranked horizontal bar chart, a "KEY INSIGHT" auto-generated sentence, an At-a-Glance tile block, a paginated Full Ranking table with Importance/Relative Weight%.

**G. Values:** `extract_feature_importance()` — tree models use native `feature_importances_`; linear models use `|coef_|`. **Not SHAP, not permutation importance.** Values are normalized to sum to 100% across all features; "Relative Weight %" is that same normalized number × 100 — the bar's visual *width*, however, is a separate cosmetic ratio relative to only the single largest feature (floored at 2% for legibility) — don't equate bar length with the percentage number when explaining the chart.

**H.** "KEY INSIGHT" text is **dynamically generated JavaScript** interpolating the real top-3 features and their real percentages — not an LLM call, not static copy.

**J.** "This ranks features by how much the fitted model's own internal structure relies on them — for tree models, that's literally how much each feature reduced prediction error across every split in every tree."

**K/L.** "Is this the same as SHAP on the next tab?" → "No — this reads a property the model already has the moment training finishes, with no extra computation. SHAP, on the next tab, re-runs the model over real sample rows to see how much each feature's *actual value* moved *actual predictions* — they can rank differently, and that's expected, not a bug."

---

## PAGE 20 — Explainability: SHAP Analysis tab

**A. Visible:** "Samples for SHAP Analysis" slider (default 150, range 50–300), "Compute SHAP Values" button, Mean |SHAP| bar chart, At-a-Glance tiles (Highest impact, Mean |SHAP|, Features covered, Samples used).

**G. Values:** `compute_shap_values()` — **tree-family models** (name contains XGB/LGBM/Forest/Boosting/Tree) use `shap.TreeExplainer` on the full requested sample; **all other models with `predict_proba`** use `shap.KernelExplainer`, with a 50-row background sample and — important — the actually-explained set **silently capped at the first 50 rows**, regardless of the slider. Mean |SHAP| = average absolute per-row SHAP value per feature.

**M.** The "Samples Used" tile shows the slider's *requested* value, not necessarily the true number of rows explained for non-tree models (capped at 50 by KernelExplainer) — a caveat to have ready, not to volunteer unprompted.

**J.** "This tab runs the model forward over real held-out rows and measures how much each feature's actual value pushed each prediction up or down, then averages the absolute effect across the sample — that's a fundamentally different, data-grounded computation from the previous tab's structural importance."

---

## PAGE 21 — Explainability: Prediction Reasoning tab

**A. Visible:** Customer Index input, Prediction (LOW RISK, 15.4% default probability, 50% decision threshold), Top Prediction Drivers (Reduces/Increases Default Risk lists), SHAP Contribution Chart, Raw Feature Values expandable section.

**G. Values:** `pipeline.predict_proba()` — the model's real probability output for the one selected row. **Decision rule uses a fixed 0.5 threshold**, hardcoded independently of whatever F1-optimized threshold (e.g. 0.62 on the Evaluation tab) is actually used for the model's real production decisions — a genuine inconsistency worth flagging proactively rather than waiting to be caught on it. Top Drivers = that single row's own SHAP vector (zero averaging), top 12 by magnitude, split by sign into two lists of up to 3 each.

**M.** "Customer Index" is a position within the re-derived test split, **not** a row number in the original uploaded CSV. "Raw Feature Values" are the **preprocessor-transformed** (scaled/encoded) values used by the model, not the untouched original spreadsheet cell values — say "raw model-input features," not "raw source data."

**J.** "This is the most granular explanation layer — no averaging at all, just this one customer's own feature values and their exact contribution to this one prediction."

**K/L.** "Why does this use 0.5 and not the 0.62 we saw on Evaluation?" → "That's a genuine inconsistency in the current build — this tab's risk-band label always compares against a fixed 0.5, while the model's actual operating threshold (chosen to maximize F1) is 0.62. It doesn't change the underlying probability shown, just the HIGH/LOW RISK label's cutoff — worth aligning in a future release."

---

## PAGE 22 — Explainability: Summary tab

**A. Visible:** Top Feature / Key Risk Driver / Features Analyzed / Explainability Method KPI tiles, a full assembled report (Model Identity, Dataset Summary, Preprocessing Decisions, Feature Engineering Summary, Preprocessing Strategy table, Model Training Configuration, Evaluation Metrics, Explainability Findings with an auto-generated narrative), a Document Download Hub, "Download Full Report" button.

**G. Values:** Every section is client-side re-formatting of data already computed by earlier pipeline steps (profiling, preprocessing, FE, training, explainability) held in React context — **nothing is recomputed here.** "Download Full Report" = the browser's native print dialog (`window.print()`) — **there is no backend PDF-generation endpoint.**

**H.** The "Model Performance Summary" and "Key Predictors" narrative text is generated by **one deterministic Python function**, `generate_model_summary()` — real numbers plugged into fixed sentence templates via hardcoded quality bands (ROC-AUC >0.85 "excellent"/>0.75 "good"; Recall >0.70 "strong") — **not an LLM call.** The "Explainability Method" tile always shows the fixed string "TreeExplainer," regardless of which explainer branch actually ran for a given model.

**J.** "This page assembles everything the pipeline has already computed into one printable view — nothing new is calculated here, and the narrative paragraphs are template-generated from real metrics, not an AI summarization."

**M.** Don't describe "Download Full Report" as producing a formal PDF report from a backend service — it's a browser print of the on-screen content.

---
