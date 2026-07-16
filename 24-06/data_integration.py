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
class JoinCandidate:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    confidence: float
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "left_table": self.left_table, "left_column": self.left_column,
            "right_table": self.right_table, "right_column": self.right_column,
            "confidence": round(self.confidence, 3), "reasons": self.reasons,
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


def _value_overlap(a: pd.Series, b: pd.Series, sample_size: int = 2000) -> float:
    a_vals = set(a.dropna().astype(str).sample(min(len(a.dropna()), sample_size), random_state=0)) if len(a.dropna()) else set()
    b_vals = set(b.dropna().astype(str).sample(min(len(b.dropna()), sample_size), random_state=0)) if len(b.dropna()) else set()
    if not a_vals or not b_vals:
        return 0.0
    inter = len(a_vals & b_vals)
    smaller = min(len(a_vals), len(b_vals))
    return inter / smaller if smaller else 0.0


def score_join(left_col: pd.Series, right_col: pd.Series, left_name: str, right_name: str) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    name_sim = _name_similarity(left_name, right_name)
    if name_sim >= 0.5:
        score += 0.35 * name_sim
        reasons.append(f"column names are similar ('{left_name}' ~ '{right_name}')")

    if _dtype_compatible(left_col, right_col):
        score += 0.15
    else:
        score -= 0.15

    left_unique = left_col.nunique(dropna=True) / len(left_col) if len(left_col) else 0
    right_unique = right_col.nunique(dropna=True) / len(right_col) if len(right_col) else 0
    if max(left_unique, right_unique) >= 0.9:
        score += 0.2
        reasons.append("one side looks like a primary key (high uniqueness)")

    overlap = _value_overlap(left_col, right_col)
    if overlap > 0:
        score += 0.35 * overlap
        reasons.append(f"~{round(overlap * 100)}% of values overlap between the two columns")

    return max(0.0, min(1.0, score)), reasons


def discover_relationships(
    tables: dict[str, pd.DataFrame],
    min_confidence: float = 0.3,
) -> list[JoinCandidate]:
    """Scores every column pair across every pair of tables and returns
    ranked join candidates. Callers should treat candidates with
    confidence >= ~0.6 as safe defaults, and anything lower as "ask the
    user to confirm" (see the /data/integration/relationships endpoint)."""
    names = list(tables.keys())
    candidates: list[JoinCandidate] = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            left_name, right_name = names[i], names[j]
            left_df, right_df = tables[left_name], tables[right_name]
            best_for_pair: Optional[JoinCandidate] = None

            for lcol in left_df.columns:
                for rcol in right_df.columns:
                    try:
                        conf, reasons = score_join(left_df[lcol], right_df[rcol], str(lcol), str(rcol))
                    except Exception as exc:
                        logger.warning("score_join failed for %s.%s vs %s.%s: %s", left_name, lcol, right_name, rcol, exc)
                        continue
                    if conf < min_confidence:
                        continue
                    cand = JoinCandidate(left_name, str(lcol), right_name, str(rcol), conf, reasons)
                    if best_for_pair is None or cand.confidence > best_for_pair.confidence:
                        best_for_pair = cand

            if best_for_pair is not None:
                candidates.append(best_for_pair)

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates


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
