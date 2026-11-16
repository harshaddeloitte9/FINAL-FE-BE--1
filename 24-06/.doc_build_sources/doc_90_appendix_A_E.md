# PART IV — Appendices

## Appendix A — Complete Architecture Diagram (text form)

```
                              ┌────────────────────┐
                              │   LOGIN (no auth)   │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  WORKSPACE SELECT   │  (index.tsx — reads
                              │  (Dev/Val/Inventory) │   /model-inventory,
                              └──┬───────┬───────┬──┘   /history/dev+validation
        ┌────────────────────────┘       │       └────────────────────────┐
        ▼                                ▼                                ▼
┌───────────────────┐          ┌───────────────────┐          ┌────────────────────┐
│ MODEL DEVELOPMENT  │          │  MODEL VALIDATION  │          │   MODEL INVENTORY   │
├───────────────────┤          ├───────────────────┤          ├────────────────────┤
│ Data Upload         │          │ Stage 1 Intake      │          │ CRUD + Excel export │
│  → join/macro       │          │  (MDD parse: regex) │          │ over model_inventory │
│ Data Quality         │          │ Stage 2 Data &      │          │        .json         │
│  → 6 dims + LLM      │          │  Model Soundness    │          └────────────────────┘
│    business rules    │          │  (10 threshold +    │
│ Data Preparation      │          │   RAG rules + LLM)  │
│  → Profiling          │          │ Stage 3 Replication  │
│  → Preprocessing      │          │  (real re-train,     │
│    (train-only fit)   │          │   R4.1-R4.8)          │
│  → Feature Eng.       │          │ Stage 4 Benchmarking  │
│    (IV/Gini/MI, WOE)  │          │  (real re-fit +       │
│ Model Training         │          │   synthetic ROC)      │
│  → weighted model      │          │ Stage 5 Stress &       │
│    recommendation      │          │  Backtesting           │
│  → real .fit(),        │          │  (real re-scoring,     │
│    balanced weights,   │          │   PSI, macro shocks)   │
│    99-pt F1 threshold  │          │ Stage 6 Explainability │
│ Model Evaluation        │          │  & Fairness            │
│  → 9 sub-tabs, all      │          │  (AUC-gap bias check,  │
│    real sklearn/scipy   │          │   reg. compliance)     │
│ Model Explainability     │          │ Stage 7 Findings &      │
│  → native importance,    │          │  Final Report           │
│    SHAP (Tree/Kernel),   │          │  (verdict rule,         │
│    per-row reasoning     │          │   template summary)     │
└───────────┬───────────┘          └───────────┬───────────┘
            │                                   │
            └────────────► shared React Context ◄────────────┘
                     (DatasetProvider, localStorage
                      key "aegis_dataset_state")
```

**Key architectural facts:**
- No database — two flat-file persistence mechanisms (`model_inventory.json`, two CSV event logs) under `24-06/app_data/`.
- No server-side pipeline session — the browser's React context/localStorage IS the session state; every backend endpoint is stateless.
- Two LLM integration points only: Data Quality's Consistency check (Ollama-only, no fallback), and Validation Stage 2/3's RAG rule judging (Deloitte-agent → Ollama fallback chain). Every other "intelligent-looking" feature in the platform (recommendations, thresholds, transforms, feature engineering, findings, executive summaries) is deterministic code — not an LLM.

## Appendix B — End-to-End Data Lineage

1. **Raw data** enters as CSV/Excel/SQLite/FRED, joined via real pandas merges with scored FK confidence.
2. **Profile** (`_build_data_profile`) computed once, reused verbatim across Data Upload, Data Quality, and Data Preparation's Profiling tab — one function, three consumers.
3. **Preprocessing** fits every transformer (imputer, winsorizer, scaler, encoder) on the TRAIN split only; val/test receive the same fitted transform, never re-fit — leakage-safe by construction.
4. **Feature Engineering** derives WOE/interaction/frequency/bin features and ranks by Gini/IV/MI — purely statistical, zero LLM involvement.
5. **Training** re-derives the split (`train_new.split_data`), applies balanced sample weights unconditionally, optionally cross-validates/tunes/OOT-validates, and auto-selects a decision threshold via a 99-point F1 sweep.
6. **Evaluation** reads the training response's already-computed metrics — no new computation happens on this tab.
7. **Explainability** re-derives the exact same test split deterministically (same seeds/config) to compute native importance and SHAP against it.
8. **Validation Stage 3** independently **re-derives everything from the raw dataset a second time** — this is the one point in the pipeline where the platform deliberately does NOT reuse Development's own artifact, specifically to prove reproducibility.
9. **Validation Stages 4–6** consume Stage 3's replicated model/metrics, plus Stage 1's MDD-reported numbers, layering benchmarking, stress, and fairness checks on top.
10. **Validation Stage 7** aggregates whatever of Stages 1/2/4/6 actually fired into one verdict — Stages 3 and 5's own findings are currently dead paths in this aggregation (see Page 32).

## Appendix C — Frontend → API → Backend Mapping Table

| Frontend file | Calls | Backend function(s) |
|---|---|---|
| `login.tsx` | none | — |
| `index.tsx` | `/model-inventory`, `/history/dev`, `/history/validation` | `persistence.ensure_model_inventory_seed`, `persistence.read_log` |
| `dashboard.tsx` | same 3 as above | same |
| `data-upload.tsx` | `/data/upload`, `/data/database/*`, `/data/integration/*`, `/data/macro/*` | `_build_data_profile`, `data_integration.DatasetIntegrator`, `fred_client.*` |
| `data-quality.tsx` | `/data/business-rules/discover` | `business_rules.discover_and_evaluate_rules` |
| `data-preparation.tsx` (Profiling) | `/data/profile` | `_build_data_profile` |
| `data-preparation.tsx` (Prep/FE) | `/data/preprocess`, `/data/drop-impact`, `/data/feature-engineering` | `preprocessing_new.*`, `feature_engineering.*` |
| `model-training-evaluation.tsx` | `/models/recommend`, `/models/train`, `/models/compare` | `model_selector.recommend_model`, `train_new.train_model`, `evaluate_new.*` |
| `explainability.tsx` | `/models/explain` (×3 param variants) | `explainability.extract_feature_importance`, `compute_shap_values`, `generate_prediction_reasoning`, `generate_model_summary` |
| `validation.intake.tsx` | `/validation/intake`, `/validation/parse-mdd`, `/validation/tier` | `_build_validation_intake_snapshot`, `val_replication_core.parse_mdd_file`/`extract_metrics_from_mdd` |
| `validation.data-quality.tsx` | `/validation/stage2/run`, `/stage2/llm-check`, `/stage3/run`, `/stage3/llm-check` | `validation_agent2.check_data_validation`/`check_conceptual_soundness`, `source_agent2.check_documents_with_llm` |
| `validation.challenger.tsx` | `/validation/replication` | `val_replication_core.run_replication`/`_fit_core`/`evaluate_replication_checks` |
| `validation.performance.tsx` | `/models/compare`, `/validation/performance` | `_run_benchmark_comparison`, `_lighten_for_comparison` |
| `validation.stress.tsx` | `/validation/stress/run`, `/validation/stress/shock` | `validation_stress_core.run_stress_suite`/`apply_manual_shock` |
| `validation.regulatory.tsx` | `/validation/stage7/bias-check`, `/validation/stage7/run` | `val_replication_core.run_bias_check`, `validation_agent2.check_regulatory_compliance` |
| `validation.findings.tsx` | `/validation/stage8/findings` | (aggregation logic in `main.py`, no dedicated module) |
| `model-inventory.tsx` | `/model-inventory`, `/model-inventory/models` (POST), `/model-inventory/export` | `persistence.*` |

## Appendix D — All Major Formulas (consolidated)

**Data quality:** Completeness=`100−missing%`; Duplicate rate=`dup_rows/n×100`; Outlier fence=`Q1−1.5×IQR` to `Q3+1.5×IQR`; Leakage=`|Pearson r|>0.95`; Imbalance ratio=`majority/minority count`.

**Preprocessing:** MICE/KNN/median routing on correlation-strength + missing%/row-count; Scaler choice on `3×IQR` outlier fraction; OneHot vs Ordinal on cardinality ≤/>8; Transform on `|skew|` bands with a ≥30% effectiveness re-check.

**Feature Engineering:** Gini=`2×AUC−1`; IV via WOE-binning; MI via `sklearn.mutual_info_classif`; removal via correlation>0.90, near-constant>99%, or IV<0.02.

**Model selection:** `score(model)=Σ GLOBAL_WEIGHT[c]×AFFINITY[model][c]×VALUE[c]` across 9 characteristics.

**Training:** Class weights=`compute_sample_weight("balanced", y)`; Threshold=`argmax_F1` over `linspace(0.01,0.99,99)`.

**Evaluation:** Standard sklearn/scipy calls for Accuracy/Precision/Recall/F1/ROC-AUC/PR-AUC/KS(`ks_2samp`)/Brier; Heteroscedasticity flag=`|Spearman(score,|resid|)|>0.35 OR variance_ratio>4`; Temporal flag=`|actual−predicted|>5pp`.

**Explainability:** Importance=`feature_importances_` or `|coef_|`, normalized to sum 1.0; SHAP via `TreeExplainer`/`KernelExplainer`; Risk decision=`prob≥0.5`.

**Validation:** PSI=`Σ(Actual%−Expected%)×ln(Actual%/Expected%)`; Bias AUC gap=`max(group AUC)−min(group AUC)`; Replication tolerances=AUC±0.03/0.06, Gini±0.05, KS±0.03, metrics±5%, ablation<0.05, seed-std<0.02, CV-AUC±0.02/0.04; Verdict=`>2 HIGH findings→REJECTED`.

## Appendix E — All Important Configuration/Default Values

See the consolidated hardcoded-value registers at the end of each Part II section (§2.1.8, §2.2.6, §2.3.5, plus the tables embedded in §2.4–2.7). The three genuinely **environment-configurable** values in the whole platform are: `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS` (business-rule discovery), `BUSINESS_RULE_CONFIDENCE_THRESHOLD` (default 0.90), `FRED_API_KEY` (macro data), and `DELOITTE_AGENT_URL` (Stage 2/3 RAG LLM primary provider). Every other threshold documented in this report is a fixed Python/TypeScript literal, not runtime-configurable without a code change.

---
