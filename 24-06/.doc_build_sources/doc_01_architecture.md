# PART I — End-to-End Architecture

## 1.1 The two workspaces

The platform has two independent pipelines sharing one dataset/model context, plus a shared inventory:

```
LOGIN  →  WORKSPACE SELECTION
              ├── MODEL DEVELOPMENT workspace
              │      Data Upload → Data Quality → Data Preparation (Profiling → Preprocessing → Feature Engineering)
              │      → Model Training → Model Evaluation → Model Explainability
              │
              ├── MODEL VALIDATION workspace (independent reviewer path)
              │      Stage 1 Intake & Governance → Stage 2 Data & Model Soundness →
              │      Stage 3 Model Replication & Performance → Stage 4 Benchmarking →
              │      Stage 5 Stress & Backtesting → Stage 6 Explainability & Fairness →
              │      Stage 7 Findings & Final Report
              │
              └── MODEL INVENTORY workspace (registry/governance record)
```

Both the Development and Validation workspaces read/write the **same** in-memory + localStorage React context (`DatasetProvider`, `aegis-frontend/src/lib/app-context.tsx`, persisted under the `localStorage` key `aegis_dataset_state`). This is the single most important architectural fact for explaining "how does data flow between screens": **there is no server-side session state for the pipeline** — every stage's result (profile, preprocessing result, feature engineering result, training result, and each validation stage's result) is held in the browser's React context and localStorage, and each screen's effect/handler reads whatever the previous screen already wrote there. Backend endpoints are stateless — every POST includes whatever inputs it needs (the file, or `csv_text`, or a previous stage's JSON result as a form field) each time.

## 1.2 Backend shape

- **Framework:** FastAPI, single app in `24-06/main.py` (5,499 lines), started via `24-06/start_backend.py` → `uvicorn.run(app, ...)`.
- **No database.** Two persistence mechanisms exist, both flat files under `24-06/app_data/`:
  - `model_inventory.json` — a single JSON document with `development[]`, `validation[]`, `models[]`, `data_sources[]`, `history[]` arrays, read/written by `24-06/persistence.py`.
  - `dev_pipeline_log.csv` / `validation_pipeline_log.csv` — append-only event logs written by `persistence.log_event()`, read back by `/history/dev`, `/history/validation`, `/history/latest`, `/history/artifact`.
- **No real model registry / MLflow-style artifact store.** A trained model's serialized pipeline is base64-encoded and passed back to the frontend in the `/models/train` response; it lives in browser context only unless the reviewer explicitly downloads it.
- **LLM integration:** `24-06/llm_providers.py` defines a provider-fallback chain — `DeloitteAgentProvider` (a hosted agent endpoint, tried first if configured) falling back to `OllamaProvider` (local `llama3.2` by default). Used in exactly two places: (1) the Data Quality "Consistency" business-rule discovery (`24-06/business_rules.py`, Ollama only, does **not** use the fallback chain — deliberately local-only), and (2) the Model Validation Stage 2/3 RAG regulatory-rule checks (`24-06/source_agent2.py`, uses the full Deloitte→Ollama fallback chain).
- **No authentication, no authorization, no multi-tenancy.** Confirmed by exhaustive route inspection — zero auth-related endpoints exist.

## 1.3 Frontend shape

- **Framework:** React 19.2 + TanStack Router (file-based routing) + TanStack Query (installed, present in the dependency tree, but not actually used by any route in this codebase — every data-fetch is a raw `fetch()` wrapper (`aegis-frontend/src/lib/api.ts`'s `api()`/`formUpload()`), not a `useQuery` hook).
- **State:** one large `DatasetProvider` React Context (`app-context.tsx`) holds the entire pipeline's state — `profile`, `file`, `preprocessingResult`, `featureEngineeringResult`, `trainingResult`, `businessRulesResult`, and one field per Validation stage (`validationIntakeData`, `validationStage3Result` … `validationStage8Result`). This context is persisted to `localStorage` on every change (except the raw `File` object and the trained model's base64 artifact, both deliberately excluded — see Part III, Screen 8/9 for why).
- **Routing quirk to know for the deck:** several route files (`development.tsx`, `profiling.tsx`, `preprocessing.tsx`, `training.tsx`, `evaluation.tsx`, `pd.tsx`, `validation.conceptual.tsx`) are **pure redirect stubs** with no real content — they exist only so an old/bookmarked URL still lands somewhere sensible. The actual screens live in `data-upload.tsx`, `data-quality.tsx`, `data-preparation.tsx` (2 tabs), `model-training-evaluation.tsx` (2 tabs, 9 evaluation sub-tabs), `explainability.tsx` (4 tabs), and the seven `validation.*.tsx` files.

## 1.4 Data lineage, stage by stage

| Stage | Input | Processing | Output written to context | Backend endpoint(s) |
|---|---|---|---|---|
| Data Upload | CSV file(s), optional SQLite DB, optional FRED macro fetch | Column-type detection, join, macro alignment | `profile`, `file` | `/data/upload`, `/data/database/*`, `/data/integration/*`, `/data/macro/*` |
| Data Quality | `profile` (read-only) | Six quality-dimension checks + LLM business-rule discovery | `businessRulesResult` | `/data/business-rules/discover` (only call this page makes) |
| Data Preparation — Profiling | `profile` | Re-profile if target changed | `profile` (updated) | `/data/profile` |
| Data Preparation — Preprocessing | `profile`, `file` | Missing-value treatment, outlier winsorization, scaling, encoding, transforms — fit on TRAIN split only | `preprocessingResult` | `/data/preprocess`, `/data/drop-impact` |
| Data Preparation — Feature Engineering | `profile`, `file`, preprocessing choices | WOE/interaction/frequency/bin features, IV/Gini/MI ranking, correlation-driven removal | `featureEngineeringResult` | `/data/feature-engineering` |
| Model Training | `profile`, `file`, FE choices | Model recommendation, real `.fit()`, optional CV/hyperopt/OOT, auto threshold selection | `trainingResult` (includes `evaluation_metrics`, base64 model artifact) | `/models/recommend`, `/models/train` |
| Model Evaluation | `trainingResult` | Pure display — all 9 sub-tabs read fields already computed by `/models/train` | (no new context written) | (reads `trainingResult`; `/models/evaluate` exists for re-scoring a separate artifact but this screen doesn't call it) |
| Model Explainability | `trainingResult`'s model artifact + re-derived `X_test` | Native feature importance, SHAP (TreeExplainer/KernelExplainer), per-row reasoning | (no context written back — read-only view) | `/models/explain` (one endpoint, 3 different parameter combinations for the 3 data-producing tabs) |
| Validation Stage 1 | Uploaded MDD or Demo A/B | Regex MDD metric extraction, or hardcoded demo dict | `validationIntakeData`, `validationMddText`, `validationMddMetrics` | `/validation/intake`, `/validation/parse-mdd`, `/validation/tier` |
| Validation Stage 2 | Dataset + MDD text + selected frameworks | 10 deterministic threshold checks + N framework-filtered RAG rules judged by LLM | `validationStage3Result` (yes — Stage 2's Conceptual-Soundness tab writes to a context field literally named for "stage3", a legacy naming artifact) | `/validation/stage2/run`, `/validation/stage2/llm-check`, `/validation/stage3/run`, `/validation/stage3/llm-check` |
| Validation Stage 3 | Dataset, reported metrics (from Stage 1 MDD or a prior training run) | Real independent re-training: base fit + 5-seed stability + per-feature ablation, 8 tolerance checks (R4.1–R4.8) | `validationStage4Result` (again a legacy-named field — this is Stage 3's output) | `/validation/replication` |
| Validation Stage 4 | Champion metrics (from Stage 1 MDD, precedence-merged), challenger selection | Real lightweight re-fit per challenger (no CV/hyperopt), synthetic ROC overlay | `validationStage5Result` | `/models/compare`, `/validation/performance` |
| Validation Stage 5 | Replicated model + test data | PSI, macro scenario shocks, manual feature shock, backtesting, directional tests — all via real `predict_proba` re-scoring | (read via `useResumeState` from the persisted CSV log, not written to a dedicated context field in the same way) | `/validation/stress/run`, `/validation/stress/shock` |
| Validation Stage 6 | Stage 3's feature importances (reused, not recomputed) + dataset | Fair-lending AUC-gap bias check; 10 deterministic/stub regulatory-compliance checks (7.1–7.10) | `validationStage7BiasResult` | `/validation/stage7/bias-check`, `/validation/stage7/run` |
| Validation Stage 7 | All prior stage results, re-sent as form fields | Aggregates reachable findings from Stages 1, 2, 4, 6 into one verdict | `validationStage8Result` | `/validation/stage8/findings` |
| Model Inventory | — | CRUD over the JSON store; Excel export | `GET/POST/PUT /model-inventory*` | — |

## 1.5 What "Model Development" and "Model Validation" each actually prove

For the Director-facing framing: **Model Development** is where a model is *built* — every metric there is the model's own self-reported performance on its own held-out split, computed by the same code that trained it. **Model Validation** is an *independent* re-derivation — Stage 3 genuinely retrains the model from the raw dataset using the developer's own configuration (not just re-reading the Development-stage artifact), specifically so that Development's and Validation's numbers can be *compared* rather than assumed equal. This distinction — "self-reported vs. independently reproduced" — is the single most important governance point in the whole platform, and it's real: confirmed by code (`val_replication_core.py`'s `_fit_core()` performs a full `train_model()` call, not an artifact re-load).

---
