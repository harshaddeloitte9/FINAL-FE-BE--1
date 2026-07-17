"""
data_integration.py — generic multi-source data integration engine.

Builds a single integrated pandas DataFrame out of an arbitrary number of
tabular sources (CSV upload, SQLite tables, FRED macro series today; designed
to extend to Postgres/SQL Server/REST APIs later without changing the shape
of this module) so the existing preprocessing/feature-engineering pipeline
can keep consuming "one DataFrame" exactly as it does today.

Nothing in this file hardcodes a column name, table name, or dataset-specific
assumption. Every table's key columns and join relationships are discovered
at runtime from the data itself (see discover_relationships) or supplied
explicitly by the caller (the FastAPI layer, driven by what the user
confirmed in the UI).

Layers, per the brief:
  - DataSource / CSVDataSource / SQLiteDataSource / FredDataSource  (Part A/B/E)
  - discover_relationships / JoinCandidate                          (Part C)
  - DatasetIntegrator / IntegrationReport                           (Part D)
"""
from __future__ import annotations

import difflib
import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("data_integration")
if not logger.handlers:
    # Library-style logging: attach a handler only if the host app hasn't
    # already configured logging, so we never duplicate output when main.py
    # (or uvicorn) sets up its own root logger.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


class DataIntegrationError(Exception):
    """Raised for any recoverable data-integration failure (bad file, unknown
    table, no join key found, etc). The FastAPI layer catches this and turns
    it into an HTTP 400 with the message intact."""


# ─────────────────────────────────────────────────────────────────────────
# Part A — DataSource interface
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class SourceMetadata:
    name: str
    source_type: str  # "csv" | "sqlite" | "fred" | ...
    rows: int
    columns: list[str]
    extra: dict[str, Any] = field(default_factory=dict)


class DataSource(ABC):
    """Common interface every source implements. A DataSource's only job is
    to hand back a DataFrame plus metadata about itself — no joining, no
    feature engineering, no assumptions about what happens to the data next.
    """

    name: str

    @abstractmethod
    def load(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def metadata(self, df: Optional[pd.DataFrame] = None) -> SourceMetadata:
        ...


class CSVDataSource(DataSource):
    """Wraps an already-parsed DataFrame (the FastAPI layer already knows how
    to turn an uploaded file / csv_text into a DataFrame via the existing
    _read_dataframe helper — this class just tags it as a named source)."""

    def __init__(self, name: str, df: pd.DataFrame):
        self.name = name
        self._df = df

    def load(self) -> pd.DataFrame:
        return self._df

    def metadata(self, df: Optional[pd.DataFrame] = None) -> SourceMetadata:
        d = df if df is not None else self._df
        return SourceMetadata(name=self.name, source_type="csv", rows=len(d), columns=d.columns.astype(str).tolist())


class SQLiteDataSource(DataSource):
    """Loads a single table out of a SQLite database file. Table discovery
    and schema inspection are exposed as free functions below (list_tables /
    inspect_table) so the UI can show them before the user picks anything —
    nothing here assumes which table is "the" loan table or "the" collateral
    table."""

    def __init__(self, name: str, db_path: str | Path, table: str):
        self.name = name
        self._db_path = str(db_path)
        self._table = table

    def load(self) -> pd.DataFrame:
        if self._table not in list_tables(self._db_path):
            raise DataIntegrationError(f"Table '{self._table}' not found in the uploaded database.")
        conn = sqlite3.connect(self._db_path)
        try:
            logger.info("SQLiteDataSource: loading table '%s' from %s", self._table, self._db_path)
            return pd.read_sql_query(f'SELECT * FROM "{self._table}"', conn)
        finally:
            conn.close()

    def metadata(self, df: Optional[pd.DataFrame] = None) -> SourceMetadata:
        d = df if df is not None else self.load()
        return SourceMetadata(
            name=self.name, source_type="sqlite", rows=len(d), columns=d.columns.astype(str).tolist(),
            extra={"table": self._table, "db_path": self._db_path},
        )


class FredDataSource(DataSource):
    """Reuses the existing fred_client module. Unlike the entity sources
    above, FRED data isn't joined by an entity key — it's aligned by date
    (see attach_to_by_date). load() here fetches a preview/metadata frame
    only (which series came back, over what range); the authoritative merge
    into the integrated dataset happens in DatasetIntegrator.attach_macro,
    which calls fred_client.attach_macro_features directly against the real
    integrated frame for correctness (avoids a lossy merge-back)."""

    def __init__(self, name: str, fred_client_module: Any, api_key: str, reference_dates: pd.Series, date_col_label: str = "observation_date"):
        self.name = name
        self._fred = fred_client_module
        self._api_key = api_key
        self._reference_dates = reference_dates
        self._date_col_label = date_col_label

    def load(self) -> pd.DataFrame:
        client = self._fred.FREDClient(api_key=self._api_key, cache_dir=".fred_cache")
        probe = pd.DataFrame({self._date_col_label: pd.to_datetime(self._reference_dates, errors="coerce").dropna().drop_duplicates()})
        if probe.empty:
            raise DataIntegrationError("No valid dates available to fetch FRED macro series against.")
        logger.info("FredDataSource: fetching macro series for %d distinct dates", len(probe))
        augmented, macro_cols = self._fred.attach_macro_features(probe, fred_client=client, date_col=self._date_col_label)
        self._macro_cols = macro_cols
        return augmented

    def metadata(self, df: Optional[pd.DataFrame] = None) -> SourceMetadata:
        d = df if df is not None else self.load()
        macro_cols = getattr(self, "_macro_cols", [c for c in d.columns if c != self._date_col_label])
        return SourceMetadata(name=self.name, source_type="fred", rows=len(d), columns=d.columns.astype(str).tolist(), extra={"series": macro_cols})


# ─────────────────────────────────────────────────────────────────────────
# Part B — SQLite discovery helpers
# ─────────────────────────────────────────────────────────────────────────

def list_tables(db_path: str | Path) -> list[str]:
    # `with sqlite3.connect(...) as conn` only commits/rolls back the
    # transaction — it does NOT close the connection. On Windows that leaves
    # the underlying file handle open, so a caller's os.unlink() on the temp
    # db file right after this returns fails with "file is being used by
    # another process". Close explicitly instead.
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def inspect_table(db_path: str | Path, table: str, sample_rows: int = 200) -> dict[str, Any]:
    """Schema + lightweight stats for one table, used both to show the user
    what's in their database and as input to relationship discovery."""
    conn = sqlite3.connect(str(db_path))
    try:
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        sample = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT {int(sample_rows)}', conn)
    finally:
        conn.close()

    columns = []
    for col in sample.columns:
        series = sample[col]
        unique_ratio = round(float(series.nunique(dropna=True)) / len(series), 4) if len(series) else 0.0
        columns.append({
            "name": str(col),
            "dtype": str(series.dtype),
            "unique_ratio_sample": unique_ratio,
            "sample_values": series.dropna().astype(str).unique()[:5].tolist(),
        })
    return {"table": table, "row_count": int(row_count), "columns": columns}


# ─────────────────────────────────────────────────────────────────────────
# Part C — automatic relationship discovery
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class PrimaryKeyCandidate:
    """Step 1 output — a column that structurally qualifies as a primary key
    (no missing values, 100% unique) in its own table, evaluated completely
    independently of every other table. This is what makes the engine
    O(tables x columns) instead of O(columns^2 x tables^2): everything in
    Step 2 only ever looks at this shortlist, never at the full column set
    of every table pair."""
    table: str
    column: str
    row_count: int
    unique_count: int
    unique_pct: float
    missing_count: int
    missing_pct: float
    dtype: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "table": self.table, "column": self.column, "row_count": self.row_count,
            "unique_count": self.unique_count, "unique_pct": round(self.unique_pct, 4),
            "missing_count": self.missing_count, "missing_pct": round(self.missing_pct, 4),
            "dtype": self.dtype,
        }


@dataclass
class PrimaryKeyResult:
    """A primary-key candidate plus a confidence score and plain-language
    reasons — the object the UI renders as "Primary Key: X, Confidence: Y%,
    Reason: ...". Confidence starts from the structural qualification
    (unique + no missing) and is boosted by how strongly some other table's
    column actually references it (see discover_relationships)."""
    table: str
    column: str
    confidence: float
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"table": self.table, "column": self.column, "confidence": round(self.confidence, 3), "reasons": self.reasons}


@dataclass
class JoinCandidate:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    confidence: float
    cardinality: str  # "1:1" or "1:many", from the foreign-key side's own uniqueness
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "left_table": self.left_table, "left_column": self.left_column,
            "right_table": self.right_table, "right_column": self.right_column,
            "confidence": round(self.confidence, 3), "cardinality": self.cardinality, "reasons": self.reasons,
        }


def _normalize_name(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _name_similarity(a: str, b: str) -> float:
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _dtype_compatible(a: pd.Series, b: pd.Series) -> bool:
    a_num = pd.api.types.is_numeric_dtype(a)
    b_num = pd.api.types.is_numeric_dtype(b)
    return a_num == b_num


def _fk_overlap(fk_series: pd.Series, pk_series: pd.Series, sample_size: int = 5000) -> float:
    """Directional, per Step 2: % of the FOREIGN key's distinct values that
    exist in the candidate primary key — not the old symmetric "smaller side"
    overlap. A FK column that's a proper subset of its PK should score ~100%
    even if the PK table itself is much larger."""
    fk_vals = fk_series.dropna().astype(str)
    if len(fk_vals) > sample_size:
        fk_vals = fk_vals.sample(sample_size, random_state=0)
    fk_set = set(fk_vals)
    pk_set = set(pk_series.dropna().astype(str))
    if not fk_set or not pk_set:
        return 0.0
    return len(fk_set & pk_set) / len(fk_set)


# ─────────────────────────────────────────────────────────────────────────
# Step 1 — candidate primary key detection (per table, independent)
# ─────────────────────────────────────────────────────────────────────────

def detect_primary_key_candidates(tables: dict[str, pd.DataFrame]) -> list[PrimaryKeyCandidate]:
    """A column stays a candidate only if it has zero missing values AND
    every value is unique. Everything else is discarded immediately —
    this shortlist is what Step 2 compares against, instead of every column
    in every table."""
    candidates: list[PrimaryKeyCandidate] = []
    for table_name, df in tables.items():
        n = len(df)
        if n == 0:
            continue
        for col in df.columns:
            series = df[col]
            missing = int(series.isna().sum())
            unique = int(series.nunique(dropna=True))
            if missing == 0 and unique == n:
                candidates.append(PrimaryKeyCandidate(
                    table=table_name, column=str(col), row_count=n,
                    unique_count=unique, unique_pct=1.0,
                    missing_count=0, missing_pct=0.0, dtype=str(series.dtype),
                ))
        if not any(c.table == table_name for c in candidates):
            logger.info("detect_primary_key_candidates: no column in '%s' is fully unique + non-null — "
                        "that table has no primary key candidate and can only appear as a foreign-key side.", table_name)
    logger.info("detect_primary_key_candidates: %d candidate(s) found across %d table(s)", len(candidates), len(tables))
    return candidates


# ─────────────────────────────────────────────────────────────────────────
# Step 2 + 3 — foreign key detection against the PK shortlist, and scoring
# ─────────────────────────────────────────────────────────────────────────

def score_foreign_key(fk_series: pd.Series, pk_series: pd.Series, fk_name: str, pk_name: str) -> tuple[float, float, str, list[str]]:
    """Returns (confidence, overlap, cardinality, reasons). Weights, per the
    brief: overlap highest, then cardinality, then dtype, then name
    similarity lowest — 0.55 / 0.20 / 0.15 / 0.10, so a perfect match on
    every dimension caps at 1.0."""
    reasons: list[str] = []

    overlap = _fk_overlap(fk_series, pk_series)
    if overlap <= 0:
        return 0.0, 0.0, "n/a", ["no overlapping values with this primary key"]
    reasons.append(f"{round(overlap * 100, 1)}% of values exist in the primary key column")

    dtype_ok = _dtype_compatible(fk_series, pk_series)
    reasons.append("compatible data types" if dtype_ok else "data types differ")

    fk_non_null = fk_series.dropna()
    has_duplicates = bool(fk_non_null.duplicated().any()) if len(fk_non_null) else False
    cardinality = "1:many" if has_duplicates else "1:1"
    reasons.append(f"{cardinality} relationship pattern (foreign key column {'is' if cardinality == '1:1' else 'is not'} itself unique)")

    name_sim = _name_similarity(fk_name, pk_name)
    if name_sim >= 0.5:
        reasons.append(f"column names are similar ('{fk_name}' ~ '{pk_name}')")

    score = 0.55 * overlap + 0.20 + (0.15 if dtype_ok else -0.15) + 0.10 * name_sim
    return max(0.0, min(1.0, score)), overlap, cardinality, reasons


def discover_relationships(
    tables: dict[str, pd.DataFrame],
    min_confidence: float = 0.2,
) -> tuple[list[PrimaryKeyResult], list[JoinCandidate]]:
    """Two-stage discovery:

      Step 1: detect_primary_key_candidates() — independent per table.
      Step 2: for every OTHER table's columns, score against only the PK
              shortlist (not every column in every table).
      Step 3: rank by confidence (overlap-dominated).
      Step 4: also derive a confidence + reasons for each primary key
              itself, boosted by how strongly it's actually referenced.

    Cost is O(tables x columns) for Step 1, then O(pk_candidates x other
    tables' columns) for Step 2 — versus the old O(columns^2 x tables^2)
    all-pairs comparison.
    """
    pk_candidates = detect_primary_key_candidates(tables)
    if not pk_candidates:
        logger.warning("discover_relationships: no primary-key candidates found in any table — "
                        "no column has zero missing values and 100%% uniqueness. No relationships can be inferred.")
        return [], []

    join_candidates: list[JoinCandidate] = []
    # Track the strongest reference into each PK, so we can explain *why*
    # that PK is trustworthy (Step 4) instead of just "it's unique".
    best_reference: dict[tuple[str, str], tuple[float, str, str]] = {}

    for pk in pk_candidates:
        pk_series = tables[pk.table][pk.column]
        for fk_table, fk_df in tables.items():
            if fk_table == pk.table:
                continue
            for fk_col in fk_df.columns:
                try:
                    conf, overlap, cardinality, reasons = score_foreign_key(fk_df[fk_col], pk_series, str(fk_col), pk.column)
                except Exception as exc:
                    logger.warning("score_foreign_key failed for %s.%s -> %s.%s: %s", fk_table, fk_col, pk.table, pk.column, exc)
                    continue
                if conf < min_confidence:
                    continue

                join_candidates.append(JoinCandidate(
                    left_table=fk_table, left_column=str(fk_col),
                    right_table=pk.table, right_column=pk.column,
                    confidence=conf, cardinality=cardinality, reasons=reasons,
                ))

                key = (pk.table, pk.column)
                current_best = best_reference.get(key)
                if current_best is None or overlap > current_best[0]:
                    best_reference[key] = (overlap, fk_table, str(fk_col))

    # A foreign-key column should reference exactly one primary key — if a
    # column scored against multiple PK candidates, keep only its best match
    # rather than presenting the same column as "maybe this, maybe that".
    best_per_fk_column: dict[tuple[str, str], JoinCandidate] = {}
    for cand in join_candidates:
        key = (cand.left_table, cand.left_column)
        current = best_per_fk_column.get(key)
        if current is None or cand.confidence > current.confidence:
            best_per_fk_column[key] = cand
    join_candidates = sorted(best_per_fk_column.values(), key=lambda c: c.confidence, reverse=True)

    pk_results: list[PrimaryKeyResult] = []
    for pk in pk_candidates:
        reasons = ["100% unique values", "No missing values"]
        ref = best_reference.get((pk.table, pk.column))
        if ref:
            overlap, fk_table, fk_col = ref
            reasons.append(f"Referenced by the {fk_table} table")
            reasons.append(f"{round(overlap * 100, 1)}% value overlap with {fk_table}.{fk_col}")
            confidence = min(0.99, 0.80 + 0.19 * overlap)
        else:
            reasons.append("Not yet referenced by any other selected table")
            confidence = 0.80
        pk_results.append(PrimaryKeyResult(table=pk.table, column=pk.column, confidence=confidence, reasons=reasons))

    pk_results.sort(key=lambda r: r.confidence, reverse=True)
    logger.info("discover_relationships: %d primary key(s), %d join candidate(s)", len(pk_results), len(join_candidates))
    return pk_results, join_candidates


# ─────────────────────────────────────────────────────────────────────────
# Part D — merge engine
# ─────────────────────────────────────────────────────────────────────────

class JoinStrategy(str, Enum):
    LEFT = "left"
    INNER = "inner"


@dataclass
class TableJoinSpec:
    right_table: str
    left_key: str
    right_key: str
    left_table: str = ""  # informational only; the merge always joins onto the running result
    how: JoinStrategy = JoinStrategy.LEFT


@dataclass
class JoinStepReport:
    right_table: str
    left_key: str
    right_key: str
    how: str
    rows_before: int
    rows_after: int
    unmatched_left: int
    orphan_right: int
    duplicate_left_keys: int
    duplicate_right_keys: int


@dataclass
class IntegrationReport:
    sources: list[SourceMetadata] = field(default_factory=list)
    join_steps: list[JoinStepReport] = field(default_factory=list)
    macro_series: list[str] = field(default_factory=list)
    rows_before: int = 0
    rows_after: int = 0
    columns_after: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sources": [{"name": s.name, "source_type": s.source_type, "rows": s.rows, "columns": len(s.columns), "extra": s.extra} for s in self.sources],
            "join_steps": [
                {
                    "right_table": s.right_table, "left_key": s.left_key, "right_key": s.right_key, "how": s.how,
                    "rows_before": s.rows_before, "rows_after": s.rows_after,
                    "unmatched_left": s.unmatched_left, "orphan_right": s.orphan_right,
                    "duplicate_left_keys": s.duplicate_left_keys, "duplicate_right_keys": s.duplicate_right_keys,
                }
                for s in self.join_steps
            ],
            "macro_series": self.macro_series,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "columns_after": self.columns_after,
            "warnings": self.warnings,
        }


class DatasetIntegrator:
    """Merges an arbitrary set of already-loaded tables into one DataFrame,
    tracking exactly what happened at each step so the UI can show a real
    Integration Report rather than a black box."""

    def __init__(self):
        self._report = IntegrationReport()

    @property
    def report(self) -> IntegrationReport:
        return self._report

    def integrate(
        self,
        base_name: str,
        base_df: pd.DataFrame,
        tables: dict[str, pd.DataFrame],
        join_specs: list[TableJoinSpec],
        source_metadata: list[SourceMetadata],
    ) -> pd.DataFrame:
        self._report = IntegrationReport(sources=source_metadata, rows_before=len(base_df))

        result = base_df.copy()
        for spec in join_specs:
            right_df = tables.get(spec.right_table)
            if right_df is None:
                raise DataIntegrationError(f"Join references unknown table '{spec.right_table}'.")
            if spec.left_key not in result.columns:
                raise DataIntegrationError(f"Join key '{spec.left_key}' not found in the dataset built so far.")
            if spec.right_key not in right_df.columns:
                raise DataIntegrationError(f"Join key '{spec.right_key}' not found in table '{spec.right_table}'.")

            rows_before = len(result)
            left_keys = set(result[spec.left_key].dropna().astype(str))
            right_keys = set(right_df[spec.right_key].dropna().astype(str))
            duplicate_left_keys = int(result[spec.left_key].duplicated(keep=False).sum())
            duplicate_right_keys = int(right_df[spec.right_key].duplicated(keep=False).sum())
            orphan_right = len(right_keys - left_keys)

            suffix = f"_{spec.right_table}"
            logger.info("DatasetIntegrator: %s join onto '%s' via %s = %s.%s (%d rows x %d rows)",
                        spec.how.value, spec.right_table, spec.left_key, spec.right_table, spec.right_key, rows_before, len(right_df))

            merged = result.merge(
                right_df, left_on=spec.left_key, right_on=spec.right_key,
                how=spec.how.value, suffixes=("", suffix),
            )
            rows_after = len(merged)

            unmatched_left = 0
            if spec.how == JoinStrategy.LEFT:
                indicator_col = spec.right_key if spec.right_key != spec.left_key else f"{spec.right_key}{suffix}"
                if indicator_col in merged.columns:
                    unmatched_left = int(merged[indicator_col].isna().sum())

            if rows_after > rows_before:
                self._report.warnings.append(
                    f"Join onto '{spec.right_table}' expanded row count from {rows_before} to {rows_after} — "
                    f"'{spec.right_key}' is not unique in that table (fan-out join)."
                )
            if unmatched_left:
                self._report.warnings.append(
                    f"{unmatched_left} row(s) had no match in '{spec.right_table}' and were kept with nulls (left join)."
                )

            self._report.join_steps.append(JoinStepReport(
                right_table=spec.right_table, left_key=spec.left_key, right_key=spec.right_key, how=spec.how.value,
                rows_before=rows_before, rows_after=rows_after, unmatched_left=unmatched_left, orphan_right=orphan_right,
                duplicate_left_keys=duplicate_left_keys, duplicate_right_keys=duplicate_right_keys,
            ))
            result = merged

        self._report.rows_after = len(result)
        self._report.columns_after = len(result.columns)
        return result

    def attach_macro(
        self,
        df: pd.DataFrame,
        date_col: Optional[str],
        fred_client_module: Any,
        api_key: str,
        candidate_date_cols: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Part E — merge FRED macro series onto the integrated dataset by
        observation date rather than an entity key. Reuses the existing,
        already-tested fred_client.attach_macro_features directly against
        the real dataframe (see FredDataSource docstring for why)."""
        resolved_date_col = date_col or fred_client_module.detect_macro_date_col(df)
        if not resolved_date_col:
            msg = "No observation-date column could be identified for FRED alignment — macro data was not merged."
            logger.warning("DatasetIntegrator.attach_macro: %s", msg)
            self._report.warnings.append(msg)
            return df

        try:
            client = fred_client_module.FREDClient(api_key=api_key, cache_dir=".fred_cache")
            augmented, macro_cols = fred_client_module.attach_macro_features(df, fred_client=client, date_col=resolved_date_col)
        except fred_client_module.FREDError as exc:
            msg = f"FRED fetch failed: {exc}"
            logger.error("DatasetIntegrator.attach_macro: %s", msg)
            self._report.warnings.append(msg)
            return df

        if not macro_cols:
            self._report.warnings.append(f"FRED returned no macro columns to attach for date column '{resolved_date_col}'.")
            return df

        self._report.macro_series = macro_cols
        self._report.columns_after = len(augmented.columns)
        logger.info("DatasetIntegrator: attached %d macro column(s) using date column '%s'", len(macro_cols), resolved_date_col)
        return augmented
