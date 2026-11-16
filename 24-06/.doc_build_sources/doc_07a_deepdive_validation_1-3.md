# 2.6 Model Validation — Stages 1–3

**Routing note (important):** `validation.tsx` is a redirect/outlet shell only — there is no shared stepper on the individual stage pages (the 7-node stepper only exists on the `/validation/` overview page, `validation.index.tsx`). Each stage is its own top-level route file: Stage 1 = `validation.intake.tsx`; Stage 2 = `validation.data-quality.tsx`; Stage 3 = `validation.challenger.tsx` (titled "Model Replication & Performance" — distinct from `validation.performance.tsx`, which is actually **Stage 4** "Benchmarking"). `validation.conceptual.tsx` is a dead redirect stub (Conceptual Soundness was merged into Stage 2 as a second tab).

**Universal "X/Y checks passed" mechanic**: every stage total is computed the same way, `deriveCheckTotal() = pass+warn+fail+na+pending` — the denominator can never silently drift from the tile row below it, by construction (`components/check-summary.tsx:41`).

## 2.6.1 Stage 1 — Intake & Governance

**Demo mode is intentionally a standalone validation sample, not a live Development registration.** `_build_validation_intake_snapshot(mode)` (`main.py:736-889`) loads the shipped demo CSV and MDD files for Demo A or Demo B, returns a `val_intake_data` payload with `registered_model_id = None`, and sets `model_inventory_registered = False` and `independence_confirmed = False` for both demos. This is the intended standalone Model Validation demo mode: it exercises the independent validation workflow without depending on a registered Development model.

**Real MDD parsing does exist, as a separate code path**, used when a real file is uploaded (not demo mode): `parse_mdd_file()` (`val_replication_core.py:118-158`, real `pypdf`/`python-docx`/UTF-8 extraction — no LLM) → `extract_metrics_from_mdd()` (`val_replication_core.py:69-115`) — **a pure regex extractor** (patterns for `roc[-_]?auc`, `gini`, `ks`, `cv mean auc`, `accuracy`, `precision`, `recall`, `f1`, each requiring the matched value to fall in `[0.01, 1.0]`). **No LLM is used for MDD metric extraction, in either code path.**

**"Artifacts Submitted 2/7"** is a **FRONTEND-ONLY** local counter over 7 booleans (dataset/MDD/training-code/profile/assumptions/perf-report/hyperparameters uploaded). Demo mode only ever populates 2 of the 7 (dataset + MDD) — so demo mode always shows exactly 2/7 regardless of which demo is loaded. This is a sample/demo state, not a claim that a real submission has been fully evidenced.

**The current live demo snapshot does not mark the demo model as registered or governance-complete.** The live code sets the demo model as `registered_model_id = None`, `model_inventory_registered = False`, and `independence_confirmed = False`, and the UI displays the demo badge as "Demo data — not registered." Any older wording that described Demo B's governance as "Complete" was stale documentation and does not reflect the live implementation.

**Risk tier badge** on this page is derived from the live demo `model_tier` field in the intake snapshot (`Tier 2 — Medium Risk` in the current implementation). This is a demo-only classification and is deliberately not a production inventory attestation. It is **not** the same as the separate `POST /validation/tier` → `Agent2.tier_model()` endpoint, which exists for a real tiering computation but does not create a registered-model status in demo mode.

**Regulatory Frameworks**: exactly 3 checkboxes exist — IFRS 9, SS1/23, RBI Model Risk Management, default all three checked. **There is no SS11/13 checkbox anywhere in the UI** — this single fact is the root cause of Stage 2's "2/4" headline (see below).

## 2.6.2 Stage 2 — Data & Model Soundness (Data Validation + Conceptual Soundness tabs)

Both tabs run `ValidationAgent2().run_all_checks()` (`24-06/validation_agent2.py`): Data Validation = `check_data_validation()` (checks 2.1–2.10); Conceptual Soundness = `check_conceptual_soundness()` (checks 3.1–3.10).

**Deterministic threshold checks — exact formulas:**

| Check | Formula | Threshold |
|---|---|---|
| 2.2 Missing Data Rate | `df.isnull().mean().max()` | FAIL `>20%`, WARN `>10%` |
| 2.5 Historical Coverage | years of data span | PASS `≥5`, WARN `≥3` |
| 2.8 Target Leakage | `corr(feature, target)` | Flag if `>0.95` |
| 2.9 Duplicate Record Rate | `df.duplicated().mean()` | FAIL `>1%`, WARN `>0.1%` |
| 2.10 Class Imbalance | minority/majority ratio | FAIL `<0.1`, WARN `<0.33` |
| 3.3 Multicollinearity (VIF proxy) | pairwise corr `>0.85` | FAIL if `>3` flagged columns |
| 3.4 Highly Correlated Pairs | pairwise corr `>0.9` | FAIL if `>2` pairs |
| 3.5 Bias and Fairness | keyword search in MDD text only (`"bias"`,`"fairness"`,`"discriminat"`,...) — **not a computed statistic**, binary PASS/FAIL, no WARN state | — |

All other checks (2.1, 2.3, 2.4, 2.6, 2.7, 3.1, 3.2, 3.6–3.10) resolve via column-name keyword matching and/or MDD-text keyword search, not numeric thresholds.

**The RAG rule engine — full trace:**
```
KNOWLEDGE STORE (rag_store/val_mdd_rules.json, 15 rules)
   ↓ filtered by stage (data_validation / conceptual_soundness)
   ↓ filtered by selected frameworks (_rule_matches_frameworks)
   ↓
LLM CALL (complete_with_fallback: DeloitteAgentProvider → OllamaProvider)
   ↓ structured JSON: {index, rule_id, status: PASS|WARN|FAIL, evidence, reasoning}
   ↓
Merged back into ragRules by rule_id
```
- Knowledge store: **15 rules total**, hand-curated (`_SEED_RULES` literal in `val_build_rules.py`) — **SOURCE NOT VERIFIED as live semantic/vector retrieval**; it's a static filtered list, not an embeddings search, at runtime.
- Framework filter (`source_agent2.py:28-44`): `data_validation` stage has 5 total rules (V01,V02 IFRS9; **V03 SS11/13**; V04,V05 SS1/23). Since the default frameworks are `[IFRS9, SS1/23, RBI]` and there is no SS11/13 checkbox, **V03 can never match** → **exactly 4 rules ever apply → this is the literal source of "2/4 data validation checks passed."** `conceptual_soundness` stage has 10 total rules, all matching the default frameworks → **"7/10" is 7-of-these-10-RAG-rules**, not 7-of-the-10-threshold-checks shown in the tile grid below (a numerical coincidence, not a design link — confirmed the frontend's `summary` derivation prefers the RAG-rule-based count whenever `ragRules.length>0`, which it always is).
- **Real LLM call, confirmed**: `complete_with_fallback()` tries `DeloitteAgentProvider` first (a hosted agent URL, configured via `.env`), falls back to `OllamaProvider` (`llama3.2`, local). Structured JSON output requested. **SOURCE NOT VERIFIED**: whether either provider actually responds in a given runtime environment — the code path and fallback chain are real, not simulated.
- **Two-call design**: the initial `/validation/stage2|3/run` call runs with an empty document dict on purpose (instant PENDING stubs, no network call); a **second**, slower `/validation/stage2|3/llm-check` call with the real MDD text does the actual LLM judging and merges real verdicts back in — this is what the "🤖 AI reviewing documentation…" spinner is waiting on.
- None of the 15 rules carry a `checkable_against_data` flag — so the quantitative RAG-rule-vs-data path (`check_for_validation`) always returns empty; **every RAG rule on this stage is judged by the LLM only, never by direct data comparison.**

**"Regulatory Alignment: CONDITIONAL" verdict** (`main.py:4691-4699`, `4822-4830`): `0 high-severity FAILs & 0 pending → PASS`; `0 high FAILs (but pending exist) OR ≤2 high FAILs → CONDITIONAL`; `>2 high FAILs → FAIL` (all HARDCODED THRESHOLDS).

## 2.6.3 Stage 3 — Model Replication & Performance Testing

**Replication is real, independent re-training — not a re-read of a cached artifact.** `_fit_core()` (`val_replication_core.py:188-309`) runs the full pipeline (column typing → split → optional FE → `train_model(use_cv=True)`) from scratch on the reviewer's own dataset. The 5-seed stability loop and the per-feature ablation loop each perform **genuine additional full re-trainings** (5 separate fits for seed stability; 1 fit per dropped feature for ablation) — confirmed real, not simulated.

**Exact check identifiers: R4.1–R4.8** (not "RA.1–RA.8" — a naming correction; confirmed both in code and on-screen).

| Check | Meaning | Threshold |
|---|---|---|
| R4.1 | End-to-end training succeeded | PASS/FAIL gate for all others |
| **R4.2** | Replicated AUC vs reported | PASS `≤±0.03`, WARN `≤±0.06` |
| **R4.3** | Gini / KS vs reported | Gini `≤±0.05`, KS `≤±0.03` (joint PASS) |
| **R4.4** | Accuracy/Precision/Recall/F1 vs reported | `≤±5%` relative |
| **R4.5** | Feature-removal AUC degradation | PASS if max drop `<0.05` |
| **R4.6** | Seed stability | PASS if `Std(AUC)<0.02` across 5 seeds |
| R4.7 | Split reproducibility | **Always PASS — hardcoded, no actual contamination check performed** |
| **R4.8** | CV mean AUC vs reported | PASS `≤±0.02`, WARN `≤±0.04` |

All 8 tolerances above are **HARDCODED THRESHOLDS**. "Reported" values precedence: an earlier training run's metrics, then MDD-extracted metrics override per-key (MDD treated as authoritative). Default seeds `"42,43,44,45,46"`, `test_size=0.15`, `val_size=0.15`, `random_seed=42`, `cv_folds=5` are all **HARDCODED DEFAULTS** the frontend never overrides.

**Train/test AUC gap** (Performance tab): `|CV mean AUC − held-out test AUC|`, PASS if `≤0.10` (HARDCODED). Additional hardcoded performance gates: Recall `≥0.60`, Precision `≥0.50`, F1 `≥0.55`, Brier `<0.25`, PR-AUC `≥0.30`, KS `≥0.30`.

---
