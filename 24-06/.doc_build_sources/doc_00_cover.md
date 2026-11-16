# Aegis Credit — Model Risk Management Platform
## Complete Code-Traced Director/Manager Reference

This document is a comprehensive, code-verified reference for presenting the Aegis Credit platform to a Director or Manager. Every claim in this document is traced to the actual repository at `c:\Users\adeha\Downloads\Final UI 2_backup` — backend `24-06/` (FastAPI + Python), frontend `aegis-frontend/src/` (React + TanStack Router) — as it exists on 2026-09-28. Where a value or behavior could not be verified in code, this document says so explicitly with the phrase **SOURCE NOT VERIFIED** rather than guessing.

### How to use this document

1. **Part I — Architecture** gives the end-to-end flow of the whole platform: how a dataset becomes a validated, governed model.
2. **Part II — Topic Deep-Dives** are the authoritative technical reference for each functional area (Data Upload, Data Quality, Data Preparation, Model Training & Evaluation, Explainability, Model Validation Stages 1–7). Every formula, threshold, and hardcoded default is documented here once, in full.
3. **Part III — Screen-by-Screen Walkthrough** covers all 32 screenshots individually, in the order they appear in the reference PDF. Each screen section is intentionally concise on formulas (it points back to Part II for the full derivation) but complete on what's visible, what to say, and what you'll be asked.
4. **Part IV — Appendices** contains the consolidated formula reference, hardcoded-value register, a presentation cheat sheet, 5-minute and 15-minute scripts, 50 anticipated Director/Manager questions with answers, and a "never claim" list of things this codebase does **not** actually do — memorize this last one especially.

### Legend used throughout this document

Every displayed value is tagged with exactly one of the following:

- **HARDCODED DEFAULT** — a fixed number/string in the code with no live computation behind it (e.g., a form field default, a slider's starting value).
- **HARDCODED THRESHOLD** — a fixed cutoff that a real, computed value is compared against to decide PASS/WARN/FAIL/flag.
- **ENVIRONMENT CONFIGURATION** — read from an environment variable at runtime (e.g., `OLLAMA_MODEL`, `BUSINESS_RULE_CONFIDENCE_THRESHOLD`).
- **USER CONFIGURATION** — a value the reviewer actively sets in the UI (a slider, a dropdown, a checkbox).
- **DATA-DERIVED** — computed directly from the uploaded dataset (e.g., missing %, correlation).
- **MODEL-DERIVED** — computed from a fitted model's predictions or internal attributes (e.g., ROC-AUC, feature_importances_).
- **BACKEND RESPONSE** — passed through from an API call verbatim, not recomputed by the frontend.
- **FRONTEND-ONLY DISPLAY** — computed or formatted entirely in the browser, no backend round-trip.
- **DECORATIVE / ILLUSTRATIVE** — cosmetic content with no data backing (e.g., login-page background numbers).
- **DEMO DATA** — a hardcoded value that exists specifically to populate the "Demo A / Demo B" sample flows.

### Critical accuracy corrections found during this trace

These are the highest-value corrections to internalize before presenting — each one is a place where the UI's label or apparent behavior does **not** match what the code actually does. Full detail is in the relevant Part II/III sections.

1. **The "SHAP Feature Importance" chart on Validation Stage 6 is not SHAP.** It reuses `extract_feature_importance()` (native tree `feature_importances_` / linear `|coef_|`), the same function behind the Explainability module's "Feature Importance" tab — not `compute_shap_values()`. The "no re-training" claim in its subtitle is accurate; the "SHAP" label is not.
2. **The ROC "Benchmark" overlay curve on Stage 4 Benchmarking is a mathematical approximation, not a measured curve.** It is `TPR ≈ FPR × challenger_AUC`, plotted at the champion's own FPR points — derived from a single AUC number, not the challenger's real predicted probabilities. The code's own comment says so.
3. **The "Recall-first threshold" and "Primary Target: Recall" framing on Model Training does not match the actual auto-threshold algorithm**, which maximizes **F1**, not recall, across a 99-point grid sweep (`np.linspace(0.01, 0.99, 99)`).
4. **`scale_pos_weight` is effectively dead code** on the Model Training screen — the frontend never sends it, so it stays at its default of `1.0` and the `>1` gate that would apply it to XGBoost never fires. Real class-imbalance handling is `sklearn.utils.class_weight.compute_sample_weight("balanced", ...)`, applied unconditionally to every classification run.
5. **The Stage 2/3 "X/Y checks passed" headline numbers come from the RAG regulatory-rule count, not from the 10 quantitative threshold checks shown in the tile grid below them.** With the default framework selection (IFRS 9, SS1/23, RBI — there is no SS11/13 checkbox anywhere in the UI), Data Validation has exactly 4 matching RAG rules and Conceptual Soundness has exactly 10 — the "7/10" is 7-of-10-RAG-rules, not 7-of-10-threshold-checks (which is a coincidence of both totaling 10).
6. **Two Stage-7 finding categories are structurally unreachable given how the current frontend populates the request** — the "Stage 3" (stated-vs-replicated AUC gap) and "Stage 5" (manual shock >50% PD change) findings require form fields (`stated_auc`, `shock_result_json`) that the frontend never sends.
7. **The live Demo A/Demo B validation flow is intentionally unregistered and demo-only** — the current implementation sets `registered_model_id = None`, `model_inventory_registered = False`, and `independence_confirmed = False` for both demo snapshots, and the UI explicitly labels the demo as "Demo data — not registered." Older documentation that described Demo B as "Governance Status: Complete" or "Tier 1 — High Risk" is stale and should not be presented as the live behavior.
8. **The Dashboard's "Compliance Score" is a hardcoded lookup table** keyed on the verdict string (REJECTED→61.8%, CONDITIONALLY APPROVED→86.4%, APPROVED→94.2%), not a computed percentage — confirmed only as a fallback path computes a real ratio when no verdict exists yet.
9. **There is no real backend authentication.** Login accepts any non-empty username/password, assigns a random cosmetic role, and the "signed in" state lives in memory only (not even localStorage) — by explicit design, documented in the code's own comments.
10. **"Prediction Reasoning" always compares against a fixed 0.5 decision threshold**, independent of whatever F1-optimized threshold the Evaluation tab is actually using for the model's real decisions.

---
