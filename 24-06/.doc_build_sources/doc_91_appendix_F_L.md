# Appendix F — External Dependencies

- **Ollama** (local LLM runtime, model `llama3.2` by default) — powers Data Quality's business-rule discovery exclusively.
- **A Deloitte-hosted agent endpoint** (`DELOITTE_AGENT_URL`) — primary provider for Validation Stage 2/3's RAG regulatory-rule judging, falling back to Ollama if unconfigured/unreachable.
- **FRED (Federal Reserve Economic Data) API** — macro-economic series (GDP, unemployment, interest rate) for Data Upload's macro attach feature; requires a `FRED_API_KEY`.
- **scikit-learn** — the workhorse for splitting, all classification models, all standard evaluation metrics, `RandomizedSearchCV`.
- **SHAP library** (`shap.TreeExplainer`, `shap.KernelExplainer`) — Explainability's SHAP tab.
- **scipy** — KS statistic, Spearman correlation (heteroscedasticity check).
- **openpyxl** — Model Inventory's Excel export.
- **pypdf/PyPDF2, python-docx** — real MDD document text extraction (Stage 1).

# Appendix G — All Known Limitations (consolidated)

1. No real authentication/authorization/audit trail (Login).
2. No persistent training-run database — Dashboard/Landing "session" widgets reset with localStorage.
3. `/data/feature-engineering` hardcodes its own split, ignoring the reviewer's Preprocessing split choice.
4. "Regulatory insights" panel on Data Preparation is dead code — no backend field ever populates it.
5. `scale_pos_weight` on Model Training is a vestigial, non-functional parameter.
6. "Recall-first threshold" framing doesn't match the actual F1-optimizing threshold algorithm.
7. Explainability's "Prediction Reasoning" always uses a fixed 0.5 threshold, independent of the model's real tuned operating threshold.
8. SHAP sample-size slider is silently capped at 50 rows for non-tree (KernelExplainer) models regardless of the requested value.
9. Explainability "Explainability Method" tile always says "TreeExplainer" even when KernelExplainer actually ran.
10. Validation Stage 2/3's "X/Y checks passed" headline is a RAG-rule count, not the threshold-check tile count shown beneath it.
11. No SS11/13 framework checkbox exists, permanently excluding one knowledge-store rule from Stage 2.
12. Validation Stage 3's R4.7 "Split reproducibility" check always returns PASS — no real check is performed.
13. Validation Stage 4's ROC "Benchmark" overlay is a mathematical approximation from one AUC number, not a measured curve.
14. Validation Stage 5 has no "Dataset Variant" control despite being referenced conceptually — not implemented.
15. Validation Stage 6's "SHAP Feature Importance" chart is mislabeled — it's native feature importance, not SHAP.
16. Validation Stage 6's fair-lending bias check has no confidence interval/bootstrap correction, and includes groups as small as 10 rows.
17. Validation Stage 7 findings for "Stage 3" and "Stage 5" categories are structurally unreachable — required form fields are never sent by the current frontend.
18. Validation Stage 7's monitoring/revalidation guidance is a static lookup by risk tier, not computed from the model's actual drift metrics.
19. Demo A/Demo B Stage 1 is intentionally an independent validation demo, with `registered_model_id = None`, `model_inventory_registered = False`, and `independence_confirmed = False`; the demo is not a registered model and cannot support a final approval verdict.
20. Dashboard's "Compliance Score" is a hardcoded lookup table by verdict string, not a computed percentage in the common case.
21. Two Agent2 compliance rules (class imbalance, macro-variables-missing) are defined in the rules file but never actually referenced by the check function — orphaned rules.
22. Correlation matrices (Data Preparation) are capped to the first 10 numeric columns positionally and, on datasets >5,000 rows, computed on a fixed random sample — an estimate on large portfolios.

# Appendix H — Presentation Cheat Sheet (one line per screen)

1. Login — demo auth, no backend, in-memory only.
2. Workspace — live inventory/history counts; Dev-card metrics are session-local.
3. Dashboard — real KPIs; Compliance Score is a verdict-keyed lookup table; Health Radar is session-local.
4. Data Upload — real joins with scored FK confidence; macro data is point-in-time safe (no look-ahead).
5. Data Quality — six independently-computed dimensions; Consistency = LLM proposes, deterministic pandas decides.
6. Data Prep (Profiling) — same profiling engine as Data Quality, target-scoped.
7. Data Prep (Preprocessing/FE) — leakage-safe (train-only fits); zero LLM in this tab; split-config mismatch with FE endpoint.
8–9. Model Training — weighted multi-factor model recommendation; balanced weights always on; threshold optimizes F1, labeled "recall".
10–18. Model Evaluation — 9 tabs, all real sklearn/scipy metrics on true held-out predictions.
19–22. Explainability — Importance=structural, SHAP=data-grounded-averaged, Reasoning=single-row; report tab is client-only, no backend PDF.
23–24. Validation Stage 2 — "X/Y" = RAG rule count, not threshold-tile count; real LLM judging with Deloitte→Ollama fallback.
25–26. Validation Stage 3 — genuine independent re-training, 8 tolerance checks; R4.7 is a stub always-PASS.
27. Validation Stage 4 — real challenger re-fit; ROC "benchmark" line is a synthetic approximation.
28. Validation Stage 5 — real re-scoring under stress; macro shocks are fixed scenarios, not fitted elasticities.
29. Validation Stage 6a — mislabeled "SHAP" (really feature importance); real AUC-gap bias test, small-group caveat.
30. Validation Stage 1 — demo MDD metrics are hardcoded; real regex parser exists for actual uploads; no LLM in MDD parsing.
31. Validation Stage 6b — deterministic keyword checks; 2 of 10 are honest manual-review stubs.
32. Validation Stage 7 — clean hardcoded verdict rule; 2 of 5 finding categories are currently unreachable; summary text is templated, not AI-written.

# Appendix I — 5-Minute Presentation Script

"Aegis Credit takes a dataset from raw upload through to a fully validated, governed credit-risk model, with two parallel but connected workflows: **Model Development**, where a model is built, and **Model Validation**, where it's independently checked.

On the Development side, we automatically profile data quality across six dimensions, apply leakage-safe preprocessing that's fit only on the training split, engineer statistically-justified features, and let a weighted, explainable algorithm recommend the best-fit model for the dataset's actual characteristics — size, imbalance, non-linearity, and so on. Every evaluation metric you see — accuracy, ROC-AUC, KS, Gini — is a standard, real computation against genuinely held-out data, and every explainability view, from global feature importance down to a single customer's prediction reasoning, is backed by real model output, not a canned narrative.

On the Validation side — and this is the part I'd emphasize most to this audience — Stage 3 doesn't just re-read the developer's numbers. It **independently retrains the model from the raw data**, five times with different seeds to test stability, and once per feature removed to test dependency, then compares against the developer's reported metrics with defined tolerances. From there we run benchmarking against a challenger model, economic stress testing including macro scenarios and historical backtesting, and a quantitative fairness test across protected groups — all rolling up into one final, code-defined verdict: right now, more than two unresolved high-severity findings means automatic rejection, full stop, no manual override in the logic.

Everything I've just described is real and running — I've traced every one of these numbers back to the actual code that produces it. I also want to be upfront that this is a proof of concept: there's no real authentication yet, a couple of validation checks are currently stubs awaiting full automation, and I've got a short list of labeling/plumbing inconsistencies we should clean up before this goes further — but the core architecture and the independence of the validation logic are genuinely sound."

# Appendix J — 15-Minute Deep-Dive Script

Use the 5-minute script as the opening, then walk the room through, in order: (1) Data Upload's join-confidence scoring and macro point-in-time safety; (2) Data Quality's business-rule discovery pipeline end to end (LLM proposes → 5 safety gates → confidence gate → deterministic pandas evaluation), emphasizing that the LLM never decides pass/fail, only proposes candidates; (3) Preprocessing's train-only-fit discipline as the leakage control; (4) the model-recommendation weighted formula, naming LightGBM's specific affinity advantages; (5) the auto-threshold F1 sweep and why it's mislabeled "recall-first" in the current UI copy; (6) all nine Evaluation metrics with one plain-language sentence each; (7) the three-tier Explainability distinction (structural vs. data-grounded-averaged vs. single-case); (8) Validation Stage 3's genuine independent retraining as the platform's core "trust but verify" proof point; (9) the fairness AUC-gap test with its small-group caveat; (10) Stage 7's clean verdict rule, honestly flagging the two currently-unreachable finding categories. Close by walking through Appendix G's limitations list candidly — proactively raising limitations builds more credibility with a Director/Manager audience than waiting to be caught on them.

# Appendix K — 50 Likely Director/Manager Questions and Answers

1. **Is any of this connected to real production data?** No — it's a proof-of-concept platform; demo/synthetic and analyst-uploaded datasets only, no core-banking integration.
2. **Is authentication real?** No — demo login accepts any credentials; no backend auth exists; session state isn't even persisted to localStorage.
3. **Where does the model recommendation come from?** A weighted scoring formula across 9 measured dataset characteristics and per-model affinity coefficients — not a simple rule of thumb.
4. **Why LightGBM specifically?** It has the highest affinity score for large sample size and high dimensionality among the 5 candidates in this formula.
5. **Is class imbalance handled?** Yes, automatically — balanced sample weighting on every classification run, no toggle to disable it.
6. **What does `scale_pos_weight` do?** Nothing currently — it's present in the API but the frontend never sets it above its inert default.
7. **How is the decision threshold chosen?** Automatically, by sweeping 99 candidate cutoffs and picking the one that maximizes F1.
8. **Is that "recall-first" as the UI says?** No — that's a labeling inconsistency; the algorithm optimizes F1, not recall specifically.
9. **Can we override the threshold manually?** Yes, via a toggle on the Training screen.
10. **What's the difference between ROC-AUC and PR-AUC?** ROC-AUC measures overall ranking ability; PR-AUC focuses on the minority (default) class and is more informative on imbalanced portfolios.
11. **What does KS statistic tell us?** The maximum separation between the cumulative good/bad score distributions — a classic credit-scoring metric.
12. **Is the confusion matrix at a fixed 0.5 cutoff?** No — it uses the actual resolved threshold (auto F1-optimal or manual override), not a fixed 0.5.
13. **How many actual defaulters does the model miss?** Read directly off the Miss Rate on the Confusion Matrix tab for the current run.
14. **What is heteroscedasticity and why does it matter?** Uneven prediction error across the risk spectrum — flagged if a statistical correlation or variance-ratio threshold is exceeded; it signals the model may be less reliable in certain score bands.
15. **Is the temporal-stability chart based on real history?** Yes, real historical predictions vs. real observed rates by period.
16. **What's the difference between Feature Importance and SHAP?** Importance is a structural property of the fitted model; SHAP is a data-grounded average of many individual prediction explanations — they can legitimately rank differently.
17. **Does SHAP really explain every customer?** The tool can produce a per-row explanation for any selected customer in the held-out test sample, using their real feature values and the model's real prediction.
18. **Is the AI making up feature explanations?** No — SHAP and feature importance are both deterministic mathematical computations on the actual fitted model, not language-model output.
19. **Where is an LLM actually used in this platform?** Exactly two places: Data Quality's business-rule discovery, and Validation Stage 2/3's regulatory-rule judging — nowhere else.
20. **Can the LLM invalidate real dataset findings on its own?** No — every LLM-proposed business rule must pass five structural safety gates and a confidence threshold before a separate, deterministic pandas calculation (never the LLM) decides pass/fail.
21. **What happens if the LLM is unreachable?** The relevant checks fail soft to "not evaluated" — nothing else on the page is affected.
22. **Is Validation Stage 3 just re-reading Development's numbers?** No — it independently retrains the model from the raw dataset, including 5 seeds for stability and per-feature ablation.
23. **What tolerance do we use to say replication "matches"?** AUC within ±0.03 (warn to ±0.06), Gini ±0.05, KS ±0.03, other metrics within ±5% relative.
24. **Does the split-reproducibility check (R4.7) actually check anything?** Currently no — it's a hardcoded always-PASS stub; a real check would need to be implemented.
25. **Is the Stage 4 benchmarking ROC comparison a fair, real comparison?** The AUC values compared are real; the visual "benchmark" curve overlay specifically is a mathematical approximation, not the challenger's measured curve.
26. **How are macro stress scenarios calibrated?** Fixed, standard shock magnitudes coded into the platform — not portfolio-specific fitted elasticities.
27. **Is the PSI threshold industry-standard?** Yes — <0.10 stable, 0.10–0.25 moderate shift (warn), >0.25 significant shift (fail), matching common industry convention, confirmed in code.
28. **What does the backtesting check actually compare?** Real historical model predictions vs. real observed default rates, by period, with both a per-period and an overall-mean gap threshold.
29. **Is the fairness/bias test statistically robust?** It's a real AUC-gap computation against a coded threshold, but currently has no confidence interval and includes groups as small as 10 rows — a meaningful screening signal, not a final statistical verdict.
30. **Is the "SHAP" chart on Validation Stage 6 really SHAP?** No — it's mislabeled; it's native feature importance reused from Stage 3, not a SHAP computation.
31. **Are the Regulatory Compliance checks (7.1–7.10) fully automated?** Four are automated keyword checks against the MDD text; two (7.9, 7.10) are explicit manual-review stubs; the remainder are similarly stubbed.
32. **What triggers a REJECTED verdict?** More than 2 unresolved HIGH-severity findings, per a hardcoded rule in Stage 7.
33. **Can a reviewer override a REJECTED verdict?** Not within this logic as currently implemented — the rule is a hard cutoff.
34. **Are all potential findings actually being checked in Stage 7?** No — findings tied to Stage 3 (AUC-gap vs stated) and Stage 5 (large manual-shock PD change) currently can't fire due to a data-plumbing gap; this is a known limitation.
35. **Is the Executive Summary AI-generated?** No — it's a template with real numbers plugged in, editable by the reviewer before sign-off.
36. **How is monitoring frequency decided?** A fixed lookup table by risk tier, not computed from the specific model's live drift metrics.
37. **Where does the dataset come from originally?** Uploaded CSV/Excel, optionally joined with a SQLite database and/or FRED macro-economic data.
38. **Is the macro data point-in-time safe?** Yes — explicitly aligned to the most recent observation on or before each record's date, with no look-ahead.
39. **How are join relationships detected?** A scored formula combining value overlap, data-type compatibility, and column-name similarity — the reviewer confirms before any join executes.
40. **What's the leakage control in preprocessing?** Every transformer (imputer, scaler, encoder) is fit exclusively on the training split and applied unchanged to validation/test.
41. **Is there a single company-wide correlation/leakage threshold?** No — several different, independently-hardcoded thresholds exist across pages (e.g., 0.95 for leakage flagging, 0.90 for feature-engineering multicollinearity removal, 0.85/0.9 for Validation Stage 2's checks) — precision on "which 0.9" matters if pressed.
42. **Does this platform have a real model registry/MLflow equivalent?** No — trained artifacts are base64-encoded and live in browser session state unless explicitly downloaded; there's no persistent artifact store.
43. **Is there audit logging of who trained/validated what?** Two flat CSV/JSON logs exist for pipeline events and inventory changes, but there's no user-attribution layer since there's no real authentication.
44. **What's the biggest genuine strength of this platform?** The Stage 3 independent re-training discipline and the leakage-safe train-only-fit preprocessing — both are real, verifiable governance controls, not just claims.
45. **What's the biggest current gap?** The Stage 7 finding-reachability gap (Stages 3/5) and a handful of mislabeled UI elements (recall vs. F1, "SHAP" vs. feature importance) that could mislead a careful reviewer if not corrected.
46. **Can we point to exactly which file computes any given number?** Yes — every metric in this platform has been traced to a specific function and file; ask about any one and I can cite it precisely.
47. **Is any part of this making up numbers or hallucinating results?** No — every quantitative result traces to a deterministic calculation or a real model computation; the only generative-AI-touched outputs (business-rule proposals, RAG rule judgments) are explicitly gated by deterministic checks before they affect anything.
48. **How mature is this relative to a production MRM platform?** It's a functioning proof of concept with real statistical and ML rigor in its core calculations, but lacking production concerns like auth, persistent artifact storage, full audit trails, and a few validation-check automations that are currently manual stubs.
49. **What would you prioritize fixing first?** The Stage 7 finding-reachability gap (silent false completeness) and the mislabeled UI elements, since those are the two categories most likely to cause a reviewer to draw an incorrect conclusion.
50. **Is this document itself trustworthy?** Every claim in it is tied to a specific file, function, and line number in the actual codebase as of this trace date — anything that couldn't be verified is explicitly marked "SOURCE NOT VERIFIED" rather than assumed.

# Appendix L — "Never Claim" List

Do **not** say, imply, or let stand unchallenged, any of the following:
- That Login has real authentication, authorization, or session security.
- That the "SHAP Feature Importance" chart on Validation Stage 6 is SHAP.
- That the ROC "Benchmark" overlay on Validation Stage 4 is a measured curve for the challenger.
- That the auto-selected decision threshold optimizes recall (it optimizes F1).
- That `scale_pos_weight` does anything on the Model Training screen.
- That the Dashboard's Compliance Score is computed from a live count of passing checks (it's a verdict-keyed lookup table).
- That Validation Stage 2/3's "X/Y checks passed" reflects the threshold-check tile grid (it reflects the RAG rule count).
- That Validation Stage 3's R4.7 "Split reproducibility" check performs any real verification.
- That Validation Stage 7's findings comprehensively cover Stages 3 and 5 (they currently cannot fire).
- That Demo B's "Governance Status: Complete" reflects a real, verified governance review.
- That any Executive Summary or verdict-reasoning text is AI/LLM-generated (it's templated).
- That "Prediction Reasoning"'s risk label uses the model's real, tuned operating threshold (it's fixed at 0.5).
- That the platform has a persistent model registry, artifact store, or audit-attributed user actions.
- That macro stress scenarios reflect a fitted, portfolio-specific economic elasticity model (they're fixed standard shock magnitudes).
- That the fairness/bias AUC-gap test is statistically bulletproof at small group sizes (it has no confidence interval and includes groups as small as 10 rows).

---

*End of document. Every technical claim above was traced to the repository at `c:\Users\adeha\Downloads\Final UI 2_backup` as of 2026-09-28. No code was modified in the production of this document.*
