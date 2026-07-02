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
  • does POINT-IN-TIME alignment: for any "as-of" date it returns the most
    recent observation available on/before that date (no look-ahead)
  • caches series in-memory (and optionally on disk) so repeated lookups over
    the same range don't re-hit the API
  • fails with a clear, catchable FREDError (e.g. when the network/VPN can't
    reach api.stlouisfed.org) so the UI can degrade gracefully

NOTE: api.stlouisfed.org must be reachable from the host (VPN/allow-list). This
module does NOT disable TLS verification.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Indicator -> FRED series ID. Override via FREDClient(series=...).
DEFAULT_SERIES: Dict[str, str] = {
    "gdp":           "GDPC1",    # Real GDP (quarterly, level)
    "unemployment":  "UNRATE",   # Unemployment rate (monthly, %)
    "interest_rate": "FEDFUNDS", # Effective federal funds rate (monthly, %)
}


class FREDError(RuntimeError):
    """Raised when FRED data cannot be retrieved (network, auth, bad series)."""


class FREDClient:
    def __init__(
        self,
        api_key: str,
        series: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        cache_dir: Optional[str] = None,
    ):
        if not api_key:
            raise FREDError("A FRED API key is required.")
        self.api_key = api_key
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
        Point-in-time alignment with NO look-ahead: for each requested date,
        return the most recent macro observation on/before that date. Returns a
        DataFrame indexed by the requested dates, columns = macro indicators
        (prefixed 'macro_').

        macro : DataFrame from fetch_macro() (DatetimeIndex)
        dates : iterable of datetime-like values (one per loan / observation)
        """
        if macro is None or macro.empty:
            return pd.DataFrame()
        m = macro.sort_index().ffill()
        req = pd.to_datetime(pd.Series(list(dates)).reset_index(drop=True))
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
        with no look-ahead: the most recent observation on/before each date.
        Returns a Series aligned positionally to `dates`.
        """
        s = self.fetch_series(series_id).sort_index().ffill()
        req = pd.to_datetime(pd.Series(list(dates)).reset_index(drop=True))
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
        lookback buffer so the first dates have a prior observation) and align it
        point-in-time. Returns a DataFrame with one row per input date.
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
