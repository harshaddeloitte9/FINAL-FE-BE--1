"""
fred_client.py — Federal Reserve Economic Data (FRED) client.

Fetches macroeconomic series used as forward-looking / point-in-time features in
the LGD model (and available to any other engine that wants macro context):

    gdp           -> GDPC1   (Real Gross Domestic Product, quarterly)
    unemployment  -> UNRATE  (Unemployment Rate, monthly)
    interest_rate -> FEDFUNDS (Effective Federal Funds Rate, monthly)

The series IDs are configurable. The client:
  • fetches a series over a date range and returns a clean date-indexed Series
  • assembles a macro DataFrame (one column per indicator)
  • does POINT-IN-TIME alignment: for any "as-of" date it returns the observation
    for that date's CALENDAR MONTH (i.e. the most recent observation on/before
    the first day of that month) — precise to the month, not year, and with no
    look-ahead
  • caches series in-memory (and optionally on disk) so repeated lookups over
    the same range don't re-hit the API
  • fails with a clear, catchable FREDError (e.g. when the network/VPN can't
    reach api.stlouisfed.org) so the caller can degrade gracefully

NOTE: api.stlouisfed.org must be reachable from the host (VPN/allow-list). This
module does NOT disable TLS verification.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, List, Tuple

import numpy as np
import pandas as pd

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a local .env file (if present) into os.environ, e.g. FRED_API_KEY
except Exception:  # pragma: no cover
    pass


FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Indicator -> FRED series ID. Override via FREDClient(series=...).
DEFAULT_SERIES: Dict[str, str] = {
    "gdp":           "GDPC1",    # Real GDP (quarterly, level)
    "unemployment":  "UNRATE",   # Unemployment rate (monthly, %)
    "interest_rate": "FEDFUNDS", # Effective federal funds rate (monthly, %)
}


def _month_floor(dates: pd.Series) -> pd.Series:
    """
    Normalize each date down to the first day of its calendar month. Used
    before point-in-time lookups so alignment is precise to the MONTH of the
    given date (e.g. a default on 2021-06-17 pulls the same macro observation
    as one on 2021-06-01), rather than drifting to whatever the exact day
    happens to catch, or — if a coarser date is fed in upstream — resolving
    only to the year.
    """
    return dates.dt.to_period("M").dt.to_timestamp()


class FREDError(RuntimeError):
    """Raised when FRED data cannot be retrieved (network, auth, bad series)."""


class FREDClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        series: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        cache_dir: Optional[str] = None,
    ):
        # Falls back to the FRED_API_KEY environment variable (loaded from a
        # local .env via load_dotenv() above) so callers never need to pass
        # or prompt the user for a key — it's read once, automatically, for
        # anyone who clones the repo and sets their own .env.
        resolved_key = api_key or os.getenv("FRED_API_KEY")
        if not resolved_key:
            raise FREDError(
                "A FRED API key is required. Set FRED_API_KEY in a local .env file "
                "(see .env.example) or pass api_key explicitly."
            )
        self.api_key = resolved_key
        self.series = dict(series or DEFAULT_SERIES)
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: Dict[str, pd.Series] = {}

    # ── low-level fetch ───────────────────────────────────────────────────────
    def _cache_path(self, series_id: str) -> Optional[Path]:
        return (self.cache_dir / f"{series_id}.json") if self.cache_dir else None

    def fetch_series(
        self,
        series_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.Series:
        """
        Return a float Series indexed by observation date (sorted ascending) for
        one FRED series. Missing values ('.') are dropped. Results are cached by
        series_id across the widest range seen, then sliced to [start, end].
        """
        full = self._mem.get(series_id)
        if full is None and self.cache_dir:
            cp = self._cache_path(series_id)
            if cp and cp.exists():
                try:
                    raw = json.loads(cp.read_text())
                    full = pd.Series(raw["values"], index=pd.to_datetime(raw["dates"]),
                                     name=series_id).astype(float)
                except Exception:
                    full = None
        if full is None:
            full = self._download_series(series_id)
            self._mem[series_id] = full
            cp = self._cache_path(series_id)
            if cp is not None:
                try:
                    cp.write_text(json.dumps({
                        "dates": [d.strftime("%Y-%m-%d") for d in full.index],
                        "values": [float(v) for v in full.values],
                    }))
                except Exception:
                    pass

        out = full
        if start is not None:
            out = out[out.index >= pd.to_datetime(start)]
        if end is not None:
            out = out[out.index <= pd.to_datetime(end)]
        return out

    def _download_series(self, series_id: str) -> pd.Series:
        if requests is None:
            raise FREDError("The 'requests' library is not available.")
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        try:
            resp = requests.get(FRED_BASE_URL, params=params, timeout=self.timeout)
        except Exception as e:
            raise FREDError(
                f"Could not reach FRED for series '{series_id}': {e}. "
                "Check network / VPN access to api.stlouisfed.org."
            ) from e
        if resp.status_code != 200:
            raise FREDError(
                f"FRED returned HTTP {resp.status_code} for series '{series_id}'. "
                f"Check the API key and series ID. Body: {resp.text[:200]}"
            )
        try:
            obs = resp.json().get("observations", [])
        except ValueError as e:
            raise FREDError(f"FRED returned non-JSON for '{series_id}'.") from e

        dates, values = [], []
        for o in obs:
            v = o.get("value", ".")
            if v in (".", "", None):
                continue
            try:
                values.append(float(v))
                dates.append(pd.to_datetime(o["date"]))
            except (ValueError, KeyError):
                continue
        if not dates:
            raise FREDError(f"FRED series '{series_id}' returned no usable observations.")
        return pd.Series(values, index=pd.DatetimeIndex(dates), name=series_id).sort_index()

    # ── macro assembly ────────────────────────────────────────────────────────
    def fetch_macro(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch every configured indicator and return a DataFrame whose columns are
        the indicator names (gdp, unemployment, interest_rate). Each series keeps
        its native frequency; use as_of() to align to specific dates.
        """
        cols = {}
        errors = []
        for name, sid in self.series.items():
            try:
                cols[name] = self.fetch_series(sid, start=start, end=end)
            except FREDError as e:
                errors.append(f"{name} ({sid}): {e}")
        if not cols:
            raise FREDError("No FRED indicators could be fetched.\n" + "\n".join(errors))
        macro = pd.DataFrame(cols).sort_index()
        return macro

    @staticmethod
    def as_of(macro: pd.DataFrame, dates: Iterable) -> pd.DataFrame:
        """
        Point-in-time alignment with NO look-ahead, precise to the CALENDAR
        MONTH of each requested date: every date is floored to the 1st of its
        month, then matched to the most recent macro observation on/before
        that month-start. Two dates in the same month always resolve to the
        same macro row. Returns a DataFrame indexed by the requested dates,
        columns = macro indicators (prefixed 'macro_').

        macro : DataFrame from fetch_macro() (DatetimeIndex)
        dates : iterable of datetime-like values (one per loan / observation)
        """
        if macro is None or macro.empty:
            return pd.DataFrame()
        m = macro.sort_index().ffill()
        req_raw = pd.to_datetime(pd.Series(list(dates)).reset_index(drop=True))
        req = _month_floor(req_raw)
        rows = []
        idx_dates = m.index
        for d in req:
            if pd.isna(d):
                rows.append({c: np.nan for c in m.columns})
                continue
            pos = idx_dates.searchsorted(d, side="right") - 1
            if pos < 0:
                rows.append({c: np.nan for c in m.columns})  # before first obs
            else:
                rows.append(m.iloc[pos].to_dict())
        out = pd.DataFrame(rows)
        out.columns = [f"macro_{c}" for c in out.columns]
        return out

    # ── single-series point-in-time helpers (used for HPI-indexed LTV) ───────
    def series_as_of(self, series_id: str, dates: Iterable) -> pd.Series:
        """
        Value of ONE FRED series (e.g. an HPI index) as-of each requested date,
        precise to the CALENDAR MONTH of that date (floored to month-start)
        with no look-ahead: the most recent observation on/before that
        month-start. Returns a Series aligned positionally to `dates`.
        """
        s = self.fetch_series(series_id).sort_index().ffill()
        req_raw = pd.to_datetime(pd.Series(list(dates)).reset_index(drop=True))
        req = _month_floor(req_raw)
        idx = s.index
        out = []
        for d in req:
            if pd.isna(d):
                out.append(np.nan)
                continue
            pos = idx.searchsorted(d, side="right") - 1
            out.append(float(s.iloc[pos]) if pos >= 0 else np.nan)
        return pd.Series(out, name=series_id)

    def latest_value(self, series_id: str, on_or_before=None) -> float:
        """Most recent observation of a series (optionally on/before a date)."""
        s = self.fetch_series(series_id).sort_index()
        if on_or_before is not None:
            s = s[s.index <= pd.to_datetime(on_or_before)]
        if s.empty:
            raise FREDError(f"No observations available for '{series_id}'.")
        return float(s.iloc[-1])

    def macro_features_for_dates(
        self,
        dates: Iterable,
        lookback_days: int = 400,
    ) -> pd.DataFrame:
        """
        Convenience: fetch the macro frame spanning the requested dates (with a
        lookback buffer so the first dates have a prior observation) and align
        it point-in-time to the CALENDAR MONTH of each date (see as_of()).
        Returns a DataFrame with one row per input date.
        """
        ds = pd.to_datetime(pd.Series(list(dates)))
        valid = ds.dropna()
        if valid.empty:
            return pd.DataFrame()
        start = (valid.min() - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        end = valid.max().strftime("%Y-%m-%d")
        macro = self.fetch_macro(start=start, end=end)
        aligned = self.as_of(macro, ds)
        aligned.index = ds.index
        return aligned


def macro_feature_columns(series: Optional[Dict[str, str]] = None) -> list:
    """The macro feature column names produced by as_of() (for UI display)."""
    s = series or DEFAULT_SERIES
    return [f"macro_{name}" for name in s.keys()]


# ── Generic point-in-time macro attachment ────────────────────────────────────
# Lives here (rather than only in lgd_engine) so PD's feature_engineering step can
# attach FRED macro features to the dataset without importing the LGD module. LGD
# and EAD keep their own thin wrappers around this for backward compatibility.
#
# Macro features are aligned to LOAN ORIGINATION, never to default/charge-off:
# IFRS 9's point-in-time PD methodology conditions on the macro environment AT
# ORIGINATION and forecasts forward from there. Aligning to a default date
# instead would be conceptually wrong for a PD feature (it's only observed for
# already-defaulted loans) and behaves like a leakage channel. Origination-
# pattern columns are preferred; a handful of other point-in-time date columns
# are accepted as a fallback if no origination column exists — default/charge-
# off dates are deliberately excluded from BOTH lists.
_ORIGINATION_MACRO_DATE_SIGNATURES = [
    "origination_date", "orig_date", "disbursement_date", "loan_date",
    "open_date", "sanction_date", "application_date", "booking_date",
    "start_date", "funding_date", "issue_date", "account_open_date",
]
_FALLBACK_MACRO_DATE_SIGNATURES = [
    "as_of_date", "reporting_date", "observation_date", "snapshot_date",
]
# Backward-compatible combined list (origination-preferred first) for any
# caller still using the flat name.
_MACRO_DATE_SIGNATURES = _ORIGINATION_MACRO_DATE_SIGNATURES + _FALLBACK_MACRO_DATE_SIGNATURES


def _norm_date_col_name(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]", "", str(s).lower())


def list_date_columns_for_macro(df: pd.DataFrame) -> List[Tuple[str, bool]]:
    """
    Every column in `df` usable for point-in-time macro alignment — i.e. an
    actual date, not any arbitrary column. Returns (column, is_preferred)
    tuples, origination-pattern matches first (is_preferred=True), then any
    other genuine date column (is_preferred=False). Used to build the date-
    column dropdown so the UI only ever offers real dates, with the right
    ones surfaced first — default/charge-off-dated columns can still appear
    here (they ARE real dates) but only in the non-preferred tail, and are
    never auto-selected (see detect_macro_date_col).
    """
    preferred, other = [], []
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            rate = df[c].notna().mean()
        elif df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            try:
                rate = pd.to_datetime(df[c], errors="coerce").notna().mean()
            except Exception:
                continue
        else:
            continue
        if rate < 0.80:
            continue
        n = _norm_date_col_name(c)
        is_orig = any(_norm_date_col_name(sig) in n for sig in _ORIGINATION_MACRO_DATE_SIGNATURES)
        (preferred if is_orig else other).append(c)
    return [(c, True) for c in preferred] + [(c, False) for c in other]


def detect_macro_date_col(df: pd.DataFrame) -> Optional[str]:
    """
    Best-effort auto-detection of a date column suitable for point-in-time FRED
    macro alignment. Origination/disbursement/application-type columns only —
    see module docstring above for why default/charge-off dates are
    deliberately never auto-selected, even as a fallback.
    """
    norm = {c: _norm_date_col_name(c) for c in df.columns}
    for sig in _ORIGINATION_MACRO_DATE_SIGNATURES:
        sig_n = _norm_date_col_name(sig)
        for c, n in norm.items():
            if n == sig_n:
                return c
    for sig in _ORIGINATION_MACRO_DATE_SIGNATURES:
        sig_n = _norm_date_col_name(sig)
        for c, n in norm.items():
            if sig_n in n:
                return c
    for sig in _FALLBACK_MACRO_DATE_SIGNATURES:
        sig_n = _norm_date_col_name(sig)
        for c, n in norm.items():
            if sig_n in n:
                return c
    return None


def attach_macro_features(
    df: pd.DataFrame,
    fred_client: Optional["FREDClient"] = None,
    date_col: Optional[str] = None,
    macro_aligned: Optional[pd.DataFrame] = None,
):
    """
    Append point-in-time macro columns to `df`. Either pass a pre-aligned
    `macro_aligned` frame (index matching df) OR a `fred_client` + `date_col` to
    align here. Returns (df_with_macro, macro_col_names). Same semantics as
    lgd_engine.attach_macro, generalised for use by any pipeline (PD/LGD/EAD).
    """
    if macro_aligned is not None and not macro_aligned.empty:
        macro = macro_aligned.reindex(df.index)
    elif fred_client is not None and date_col and date_col in df.columns:
        macro = fred_client.macro_features_for_dates(df[date_col])
        macro.index = df.index
    else:
        return df.copy(), []
    macro_cols = list(macro.columns)
    return pd.concat([df.copy(), macro], axis=1), macro_cols
