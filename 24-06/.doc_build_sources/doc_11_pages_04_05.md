# PAGE 4 — Connect a Data Source (Data Upload)

**A. What is visible:** Three source cards (Customer CSV, SQLite Database, Macroeconomic Data), a tabbed uploader, a Dataset Preview table (10 rows × 21 columns), an Integration Readiness Pipeline stepper, and an "Integrate sources" call to action.

**B. Purpose:** Bring one or more raw data sources into a single, joined modelling dataset.

**C. User workflow:** Drop/select a customer CSV → optionally attach a SQLite DB and confirm join keys → optionally fetch macro data → click "Integrate sources" → preview the integrated dataset → "Proceed to Data Quality."

**D. Frontend implementation:** `aegis-frontend/src/routes/data-upload.tsx`. Full deep dive: **§2.1**.

**E. Backend implementation:** `/data/upload`, `/data/database/*`, `/data/integration/*`, `/data/macro/*` (`main.py`) + `24-06/data_integration.py` + `24-06/fred_client.py`.

**F. Data flow:** File(s) → `_read_dataframe` → optional real `pandas.merge()` joins → optional FRED macro attach (point-in-time aligned, no look-ahead) → `_build_data_profile()` → `profile` written to shared context via `setUploadResult()`.

**G. Every important displayed value:**
- **Card status badges** — **FRONTEND-ONLY DISPLAY**, optimistic (Customer CSV/SQLite "connect" the instant a file is *chosen*, before any backend call; Macro is the one card gated on a real successful fetch).
- **Row/column counts per card** — Customer: columns from **client-side** header parsing (first 8KB, naive comma split — an approximation, not authoritative schema detection); SQLite: real `/data/integration/sqlite/inspect` response; Macro: real `/data/macro/fetch` response.
- **Join relationship suggestions** — real confidence score: `0.55×overlap + 0.20 + (±0.15 dtype) + 0.10×name_similarity`, floor of 0.2 to surface at all (§2.1.5).
- **Dataset Preview (10 rows)** — literally `df.head(10)` on the final integrated frame. **DATA-DERIVED.**
- **Integration Readiness Pipeline** — all 5 steps **FRONTEND-ONLY DISPLAY**; "READY FOR MODELLING" never turns "done" anywhere in the code (a permanent placeholder).

**H. Dynamic vs static:** Card badges and the pipeline stepper are cosmetic/local; row counts, join suggestions, and the preview table are real.

**I. Business/MRM interpretation:** This is the data-lineage entry point — everything downstream (profiling, preprocessing, training, and later, independent Stage-3 replication) traces back to exactly what was joined here. The join-confidence scoring and fan-out/unmatched-row warnings are the closest thing to an automated data-lineage-integrity control at this stage.

**J. What to say:** "Every join here is a real pandas merge with automated confidence scoring and fan-out detection — nothing is faked. The pipeline stepper's last step, 'Ready for Modelling,' is currently just a visual placeholder; it never actually flips to complete in the code today."

**K. Likely questions:** "How does it know which columns to join on?" / "Where does the macro data come from and is it point-in-time safe?"

**L. Answers:** "It scores every candidate primary/foreign key pair using a weighted formula combining value overlap, data-type compatibility, and name similarity, then only proposes matches above a minimum confidence floor — the reviewer still confirms before it joins. Macro data comes from FRED via a real API call, and it's explicitly point-in-time aligned: every date is matched to the most recent macro observation on or before that month, with no look-ahead, to avoid leaking future economic conditions into the training data."

**M. Risks/limitations:** The client-side CSV column count (before integration) is an approximation only — trust the post-integration profile's column count instead. Macro fetch requires a server-side FRED API key configured via environment variable; without it, the fetch fails outright.

---

# PAGE 5 — Data Quality & Dataset Health

**A. What is visible:** A KPI strip (Completeness 99.4%, Duplicates 0, Validity "No format issues flagged", Columns 21, Timeliness "1 field checked", Target Health 3.58:1), a Quality Dimensions panel (six rows: Completeness, Uniqueness, Validity, Consistency, Timeliness, Statistical), Target Class Balance, Issues Requiring Attention table, Column Diagnostics table.

**B. Purpose:** Independently assess whether the integrated dataset can be trusted before it moves into Data Preparation.

**C. User workflow:** Read the health strip and dimension panel → drill into flagged issues → click into individual columns for detail → "Continue to Data Preparation."

**D. Frontend implementation:** `aegis-frontend/src/routes/data-quality.tsx` + `components/data-quality/*`. Full deep dive: **§2.2**.

**E. Backend implementation:** `_build_data_profile()` (shared with Data Upload/Preparation) for everything except Consistency; `POST /data/business-rules/discover` (`24-06/business_rules.py`) for Consistency — the **only** API call this page makes itself.

**F. Data flow:** Reads `profile` from context (no new call) for five dimensions; dispatches one business-rule-discovery request (deduplicated per dataset identity) for the sixth.

**G. Every important displayed value:**
- **Completeness (99.4%)** = `100 − missing_percentage`; flagged if `missing_percentage>3%` (HARDCODED THRESHOLD).
- **Duplicates (0)** = exact full-row duplicate count; flagged if rate `>1%` (HARDCODED THRESHOLD).
- **Validity ("No format issues flagged")** = zero numeric-parse or date-parse failures across checked columns; **range/allowed-value validity is explicitly hardcoded as "not evaluated"** — a fixed disclaimer sentence, not a computed result.
- **Columns (21)** = `profile.shape[1]`; always "healthy," never fails.
- **Timeliness ("1 field checked")** = count of datetime columns scanned for future (`>today`) or ancient (`<1900`) values (both HARDCODED).
- **Target Health (3.58:1)** = majority/minority class ratio; flagged "imbalanced" if `>3.0` (HARDCODED THRESHOLD).
- **Consistency** = business-rule discovery outcome (see full pipeline trace, §2.2.3): LLM proposal → Pydantic structural validation → 5 safety gates → confidence gate (`≥0.90` default, environment-configurable) → deterministic pandas evaluation. Only *applied* rules affect this dimension's status.
- **Issues table rows** — each has a specific, code-verified severity rule (§2.2.4); e.g. missing% HIGH above 20%, WARNING above 5%.

**H. Dynamic vs static:** Five of six dimensions are pure data computation with hardcoded thresholds. Consistency is the one dimension with a live LLM call in the loop, gated by deterministic safety checks before any result is trusted.

**I. Business/MRM interpretation:** This screen operationalizes "can I trust this dataset" as six independently-computed signals rather than one opaque score — which maps well to how a Director would want data quality evidenced. The business-rule discovery feature is the platform's most distinctive capability: an LLM *proposes* candidate rules from metadata only (never row-level data), but a human-auditable deterministic pandas engine — never the LLM — decides whether any row actually violates them.

**J. What to say:** "Every one of these six dimensions is independently computed from the actual dataset, with documented thresholds — nothing here is a black-box score. The Consistency dimension is worth pausing on: an LLM proposes candidate business rules purely from column metadata, but every rule goes through five structural safety gates and a confidence threshold before a deterministic pandas calculation — not the LLM — decides pass or fail. If the LLM is unreachable, this dimension simply reports 'not evaluated' rather than guessing."

**K. Likely questions:** "Can the AI make up a bad rule that fails the data unfairly?" / "What happens if Ollama is down?"

**L. Answers:** "It can propose one, but it can't apply one carelessly — every proposal is checked for column existence, correct operator schema, and type compatibility before it's even considered, and anything below the confidence threshold is shown only as a 'suggestion,' never enforced. If the LLM is unreachable, the platform fails soft: Consistency shows 'not evaluated,' and everything else on this page — which doesn't depend on the LLM at all — is completely unaffected."

**M. Risks/limitations:** The "3% missing" (dimension-level) and "5% missing" (column-diagnostics-level) thresholds are two different hardcoded cutoffs — don't conflate them if asked to be precise. The Consistency dimension can silently sit at "not evaluated" for reasons other than Ollama being down (e.g., zero applied rules), so "not evaluated" doesn't always mean "the LLM failed."

---
