# 2.2 Data Quality & Dataset Health

**Frontend:** `aegis-frontend/src/routes/data-quality.tsx` + `aegis-frontend/src/components/data-quality/*.tsx` (`dataset-health-strip`, `quality-dimensions-panel`, `issues-table`, `column-diagnostics-table`, `column-detail-panel`, `target-class-balance`, `business-rule-cards`, `selectors.ts`).
**Backend:** `_build_data_profile()` (`main.py:1096-1374`) — the single source of truth for every metric except Consistency; `24-06/business_rules.py` (578 lines) for Consistency.

**Architectural fact:** this page makes **no data-shaping API call of its own** except business-rule discovery. Everything else is read straight from `profile` (populated by whichever of `/data/upload`, `/data/database/fetch`, or `/data/integration/run` ran last — all three call the identical `_build_data_profile()`).

## 2.2.1 The six Quality Dimensions — exact formulas

| Dimension | Formula | Threshold | Type |
|---|---|---|---|
| **Completeness** | `100 − missing_percentage`, where `missing_percentage = missing_cells/total_cells×100` | Flag ("review") if `missing_percentage > 3%` | DATA-DERIVED / HARDCODED THRESHOLD (`selectors.ts:36`) |
| **Uniqueness (Duplicates)** | `duplicate_rows = df.duplicated().sum()` (exact full-row match, all columns) | Flag if `duplicate_rate > 1%` | DATA-DERIVED / HARDCODED THRESHOLD (`selectors.ts:54`) |
| **Validity** | Numeric parse-failure count + date parse-failure count, both DATA-DERIVED | Flag if any column has `count>0`; **Range/allowed-value validity is explicitly hardcoded to "not evaluated"** — a fixed sentence, not a computed result | HARDCODED (fixed disclaimer text) |
| **Consistency** | Business-rule discovery result — see §2.2.3 | See §2.2.3 | BACKEND RESPONSE (LLM + deterministic gate) |
| **Timeliness** | Count of datetime columns with `future_count>0` or `ancient_count>0` | "ancient" = year `<1900`; "future" = `>today` | DATA-DERIVED / HARDCODED THRESHOLD (`main.py:1137-1138`) |
| **Statistical (outliers)** | IQR fence per numeric column (first 8 only) | `k=1.5`; column flagged if outlier fraction `>2%` | DATA-DERIVED / HARDCODED THRESHOLD (`main.py:1197-1204`) |

Schema/Target Health are shown alongside these six on the health strip:
- **Schema** = `profile.shape[1]` (column count) — always "healthy," never fails.
- **Target Health** = `imbalance_ratio = majority_count/minority_count`, rounded to 2dp; flagged "imbalanced" if `ratio > 3.0` (**HARDCODED THRESHOLD**, `main.py:1305`).

## 2.2.2 Leakage detection (DATA-DERIVED, HARDCODED THRESHOLD)

For binary-target datasets: `df[col].corr(target_numeric)` (Pearson) for every numeric column; `|corr| > 0.95` → flagged as leakage risk (`main.py:1114-1126`). Numeric columns only — categorical/boolean are not scanned by this specific check.

## 2.2.3 Consistency — the LLM Business-Rule Discovery pipeline, full trace

This is the most architecturally distinctive feature on the platform. Endpoint: `POST /data/business-rules/discover` (`main.py:2572-2596`) → `business_rules.discover_and_evaluate_rules(df)` (`business_rules.py:517-578`).

**The pipeline, exactly:**

```
LLM PROPOSAL  →  STRUCTURED RULE (Pydantic)  →  SAFETY GATES (5)  →  CONFIDENCE GATE  →  DETERMINISTIC PANDAS EVALUATION  →  UI
```

1. **Metadata only, never raw rows** — `summarize_dataframe_for_llm()` (`business_rules.py:202-244`) sends Ollama only column names, detected types, missing/unique counts, min/max or sample categories, and up to 5 sample values per column. The module docstring is explicit: *"it never sees row-level data and never judges whether any individual row passes or fails."*
2. **Local-only LLM call** — `_call_ollama_for_rule_discovery()` (`business_rules.py:311-341`) talks directly to `OllamaProvider`'s config (`OLLAMA_URL` env, default `http://localhost:11434`; `OLLAMA_MODEL` env, default `llama3.2`; `OLLAMA_TIMEOUT_SECONDS` env, default `180s` — all **ENVIRONMENT CONFIGURATION**) — this deliberately bypasses the Deloitte-agent fallback chain used elsewhere. Requests up to **8** proposed rules (**HARDCODED DEFAULT**), structured JSON output, `temperature=0`.
3. **Pydantic structural validation** — `LLMProposedRule` model, 4 supported rule types (`numeric_range`, `allowed_values`, `cross_column_date`, `cross_column_numeric`), each with its own strict operator schema (`BetweenOperator`, `ComparisonValueOperator`, `InSetOperator`, `CrossColumnOperator`).
4. **The 5 safety gates** (`_gate_and_evaluate`, `business_rules.py:471-512`) — a proposal is marked `"invalid"` if it fails any of: (1) declared columns don't exist, (2) operator doesn't validate against the type's schema, (3) operator's own referenced columns don't exist, (4) type/column-type mismatch (e.g. `numeric_range` on a non-numeric column).
5. **Confidence gate** (Gate 5): `confidence < threshold` → `"suggested"`, **never executed** (no pandas evaluation runs at all). Threshold = **`BUSINESS_RULE_CONFIDENCE_THRESHOLD` environment variable, default `0.90`** (**ENVIRONMENT CONFIGURATION**, `business_rules.py:68-79`).
6. **Deterministic pandas evaluation** — only for gated-through, confident proposals. `_evaluate_rule()` (`business_rules.py:402-451`) computes `rows_checked`, `violation_count`, `violation_percentage` via plain pandas boolean masks (`.between()`, `.isin()`, comparison operators) — nulls excluded from both checked and violation counts. **The module docstring states explicitly: "No eval(), no exec(), no LLM-generated code path."** This is the *only* code path that ever produces a violation count — never the LLM.
7. **Fail-soft on Ollama unreachable**: returns `{rules:[], applied_count:0, ollama_available:false, error:...}` — this is exactly what drives the Consistency dimension to "not evaluated" with the message "Business-rule discovery unavailable."

**Consistency dimension status logic** (`selectors.ts:199-247`, `getConsistency`):
- `not_evaluated` if: still discovering, `ollama_available=false`, or zero *applied* rules (suggested/invalid rules don't count).
- `healthy` if all applied rules have `violation_count=0`.
- `review` if any applied rule has violations — evidence shows total violation count across all applied rules.

## 2.2.4 "Issues Requiring Attention" — full issue taxonomy (DATA-DERIVED, HARDCODED SEVERITY THRESHOLDS)

Built by `buildIssues()` (`selectors.ts:367-535`), sorted CRITICAL→HIGH→WARNING→INFO:

| Source | Row text | Severity rule |
|---|---|---|
| Missing % per column | "{pct}% missing" | HIGH if `>20%`, WARNING if `>5%`, else INFO |
| Target imbalance | "{ratio}:1 class imbalance" | WARNING (fixed) |
| ID-detected columns | "ID-like column detected" | INFO (fixed) |
| Leakage-risk columns | "Correlation with target exceeds 0.95" | HIGH (fixed) |
| Duplicate rows | "{n} duplicate row(s)" | WARNING if `rate>1%`, else INFO |
| Date anomalies | "{n} future/pre-1900 date(s)" | WARNING (fixed) |
| Numeric format errors | "{n} non-numeric value(s)" | WARNING if `>5%`, else INFO |
| Unparseable dates | "{n} unparseable date(s)" | WARNING if `>5%`, else INFO |
| Applied business rules with violations | "{n} record(s) violate: {condition}" | WARNING if `violation% >5%`, else INFO |
| Agent2 compliance flags | flag text | CRITICAL (high sev.) / WARNING (medium) / INFO |

## 2.2.5 Column Diagnostics — per-column status rule

`buildColumnDiagnostics()` (`selectors.ts:564-637`) flags a column "review" if **any** of: `missingPct>5%` (note: a *different*, independent 5% threshold from the dataset-wide 3% Completeness threshold), has outliers, numeric-format errors present, date unparseable, an applied business rule with violations references it, it's a leakage-risk column, or an Agent2 flag names it.

## 2.2.6 Full hardcoded-value register for Data Quality

| Value | Meaning | Type | Citation |
|---|---|---|---|
| >0.95 corr. | Leakage-risk threshold | HARDCODED THRESHOLD | `main.py:1123` |
| year<1900 / >today | Date "ancient"/"future" | HARDCODED THRESHOLD | `main.py:1137-1138` |
| >3% missing | Completeness "review" | HARDCODED THRESHOLD | `selectors.ts:36` |
| >1% duplicate rate | Uniqueness "review" | HARDCODED THRESHOLD | `selectors.ts:54` |
| k=1.5 (IQR) | Outlier fence multiplier | HARDCODED DEFAULT | `main.py:1197-1199` |
| >2% outlier fraction | Column "has_outliers" flag | HARDCODED THRESHOLD | `main.py:1204` |
| first 8 numeric cols | Outlier scan cap | HARDCODED DEFAULT | `main.py:1189` |
| >3.0 ratio | Target imbalance flag | HARDCODED THRESHOLD | `main.py:1305` |
| >5% missing (per column) | Column Diagnostics "review" | HARDCODED THRESHOLD | `selectors.ts:596` |
| 0.90 (default) | Business-rule confidence gate | ENVIRONMENT CONFIGURATION | `business_rules.py:72` |
| 8 rules | Max LLM proposals per call | HARDCODED DEFAULT | `business_rules.py:289` |
| 50 | Max sample violation row indices returned | HARDCODED DEFAULT | `business_rules.py:91` |
| 10 rows | Dataset Preview cap (shared with Data Upload) | HARDCODED DEFAULT | `main.py:1345` |

`critical` is a defined status value in the UI's type system but **no traced selector on this page ever returns it** — SOURCE NOT VERIFIED that "Critical" ever actually renders as a dimension status on this screen.

---
