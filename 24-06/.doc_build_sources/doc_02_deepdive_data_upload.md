# PART II — Topic Deep-Dives

# 2.1 Data Upload — "Connect a Data Source"

**Frontend:** `aegis-frontend/src/routes/data-upload.tsx` (1,380 lines, component `DataUpload`).
**Backend:** `24-06/main.py` + `24-06/data_integration.py` (621 lines) + `24-06/fred_client.py` (398 lines).

## 2.1.1 The three source cards and their status badges

`SourceOverviewCard` (data-upload.tsx:769-807), three instances (lines 519-547). Status is **FRONTEND-ONLY DISPLAY**, computed from local React state, not a backend field:

- **Customer CSV** → `"connected"` the instant a `File` object exists in `customerFile` state — **before** any backend call succeeds.
- **SQLite Database** → `"connected"` once `dbFile` state is set, again optimistic (before `/data/integration/sqlite/inspect` resolves).
- **Macroeconomic Data** → `"connected"` only after `macroColumns.length > 0`, which requires a real successful `/data/macro/fetch` call — the one card whose status is genuinely backend-gated.

## 2.1.2 CSV header detection is client-side only — no backend call on file selection

`readCsvHeader()` (data-upload.tsx:65-69) reads only the first 8,192 bytes of the file, takes the first line, splits naively on commas. **FRONTEND-ONLY DISPLAY.** No API call happens when a file is chosen — the backend only sees the file when the reviewer clicks "Integrate sources," or via the automatic macro-date-detection effect.

## 2.1.3 "Integrate sources" — end to end

Frontend handler `runIntegration()` (data-upload.tsx:343-381) → `POST /data/integration/run` (`main.py:1727-1803`). Sequence:
1. Parses uploaded customer CSV/Excel (`_read_dataframe`, `main.py:944-973`).
2. Builds `SourceMetadata` for the customer source and any selected SQLite tables (`data_integration.py:82-119`).
3. Applies confirmed joins via **`DatasetIntegrator.integrate()`** — a real **pandas `.merge()`**, not a custom algorithm (`data_integration.py:522-584`), `how="left"` by default.
4. Calls **`_build_data_profile()`** — the exact same profiling function used by `/data/upload` and `/data/database/fetch` — on the merged result.
5. Returns the full profile plus `csv_text`, `source_type="integrated"`, and `integration_report`.

`setUploadResult(file, profile)` (app-context.tsx:311-326) is the single choke point that pushes this into the whole app's shared context — this is exactly what Data Quality, Data Preparation, etc. all read.

## 2.1.4 Join engine — exact mechanics (DATA-DERIVED)

Per `TableJoinSpec`, `data_integration.py:522-584`:
```
merged = result.merge(right_df, left_on=left_key, right_on=right_key, how=join_how, suffixes=("", "_{table}"))
```
- **Fan-out warning**: if `rows_after > rows_before`, warns the right-key column isn't unique (a real 1:many join).
- **Unmatched-left**: counts nulls in the post-merge right-key column (left join) — "N row(s) had no match … kept with nulls."
- Final `rows_after`/`columns_after` = literally `df.shape` on the merged frame.

## 2.1.5 Relationship discovery — primary/foreign key confidence formula (DATA-DERIVED, HARDCODED THRESHOLDS)

`discover_relationships()` (`data_integration.py:365-445`):
- **Primary-key candidate**: a column with `missing==0` and `unique==n` (100% unique, zero nulls) within its own table.
- **Foreign-key confidence score** (`data_integration.py:361`):
  ```
  score = 0.55 × overlap + 0.20 + (±0.15 if dtype compatible/not) + 0.10 × name_similarity
  ```
  where `overlap` = `|FK values ∩ PK values| / |FK values|` (directional, sampled to 5,000 rows), `name_similarity` = `difflib.SequenceMatcher` ratio (or 0.85 for substring match, 1.0 for identical names). **Candidates below `0.2` confidence are dropped** (HARDCODED THRESHOLD, line 367). Only the single best-scoring join per FK column is kept.
- **PK confidence**: base `0.80`; if referenced by another table, `min(0.99, 0.80 + 0.19×best_overlap)`.

## 2.1.6 Dataset Preview & Pipeline Progress

- **Dataset Preview** ("10 rows shown"): `_serialize_dataframe(df, max_rows=10)` (`main.py:976-981`) = literally `df.head(10)`, no sampling. **DATA-DERIVED.**
- **"Integration Readiness Pipeline" stepper** (SOURCE → CONNECTED → INTEGRATED → PROFILED → READY FOR MODELLING): all **FRONTEND-ONLY DISPLAY**, derived from local booleans (`customerFile`, `canIntegrate`, `integrationReport`, `profile`). **"READY FOR MODELLING" never transitions to "done" anywhere in the code** — it is a permanent placeholder (SOURCE NOT VERIFIED as a real state; confirmed by code inspection that nothing ever sets it).

## 2.1.7 Macro / FRED integration

- **`detect_macro_date_col()`** (`fred_client.py:352-375`): matches column names (normalized to lowercase alphanumerics) against an origination-date signature list first (`origination_date`, `disbursement_date`, `application_date`, …), then a fallback list (`as_of_date`, `reporting_date`, …). **Default/charge-off date columns are deliberately never auto-selected**, to avoid leakage (documented design choice).
- **`POST /data/macro/fetch`** (`main.py:2507-2569`) requires a server-side `FRED_API_KEY` environment variable (**ENVIRONMENT CONFIGURATION**) — returns HTTP 500 if unset.
- **Alignment logic** (`fred_client.py:199-230`): every date is floored to its calendar month, then matched to the most recent FRED observation on/before that month — **no look-ahead**. Default series (**HARDCODED DEFAULT**, `fred_client.py:44-48`): GDP→`GDPC1` (quarterly), Unemployment→`UNRATE` (monthly), Interest rate→`FEDFUNDS` (monthly), prefixed `macro_*` and concatenated onto the dataset.
- The macro-augmented CSV is folded back into the in-browser `customerFile` **before** integration runs — the integration endpoint has no special knowledge of macro columns; they just ride along as ordinary columns.

## 2.1.8 Full hardcoded-value register for Data Upload

| Value | Meaning | Type | Citation |
|---|---|---|---|
| 0.2 | Minimum join-candidate confidence to surface | HARDCODED THRESHOLD | `data_integration.py:367` |
| 0.55 / 0.20 / ±0.15 / 0.10 | FK confidence formula weights | HARDCODED DEFAULT | `data_integration.py:361` |
| 5,000 rows | FK overlap sampling cap | HARDCODED DEFAULT | `data_integration.py` (`_fk_overlap`) |
| 10 rows | Dataset Preview cap | HARDCODED DEFAULT | `main.py:1345` |
| GDPC1 / UNRATE / FEDFUNDS | Default FRED series | HARDCODED DEFAULT | `fred_client.py:44-48` |
| month-floor, most-recent-on-or-before | Macro alignment rule | DATA-DERIVED (no look-ahead) | `fred_client.py:199-230` |
| `left` | Default join strategy | HARDCODED DEFAULT | `main.py` form field |

---
