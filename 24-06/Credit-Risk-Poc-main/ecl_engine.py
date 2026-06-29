"""
ecl_engine.py — ECL calculation from the trained default model.

This is part of the ML pipeline: it reuses the SELECTED model's output as PD,
derives the other components, and computes ECL = PD x LGD x EAD.

  PD   : the model's predicted default probability (pipeline.predict_proba) — the
         model already produces this, so no extra modelling is needed.
  EAD  : taken from an exposure / balance / loan-amount column in the input data
         (the user provides exposure; if a column isn't named, it is selectable).
  LGD  : not supplied by the user, so it is derived — from collateral/LTV when a
         loan-to-value column exists, otherwise from a configurable assumption.

Staging is intentionally OUT OF SCOPE here: this produces a single point-in-time
ECL per loan from the model's PD (effectively a 12-month ECL, matching the
model's default horizon). Discounting is configurable (1.0 = undiscounted).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

COLORS = {
    "primary": "#6366f1", "secondary": "#f59e0b", "success": "#10b981",
    "danger": "#ef4444", "neutral": "#64748b", "text": "#e2e8f0",
}

_EAD_CANDIDATES = ["exposure_at_default", "ead", "exposure", "current_balance",
                   "outstanding_balance", "balance", "loan_amount",
                   "original_loan_amount", "principal", "drawn_amount"]
_LTV_CANDIDATES = ["loan_to_value", "ltv", "loan_to_value_ratio"]


@dataclass
class ECLConfig:
    lgd_method: str = "fixed"        # "fixed" | "ltv"
    lgd_fixed: float = 0.45          # senior-unsecured style assumption
    ltv_col: Optional[str] = None
    lgd_haircut: float = 0.20        # collateral haircut when using LTV
    lgd_floor: float = 0.05
    lgd_cap: float = 0.95
    ead_undrawn_col: Optional[str] = None
    ead_ccf: float = 1.0             # credit-conversion factor on undrawn


# ───────────────────────── column helpers ─────────────────────────

def numeric_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _detect(df: pd.DataFrame, candidates: list) -> Optional[str]:
    lower = {c.lower().replace(" ", "_"): c for c in df.columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    for cand in candidates:
        for key, col in lower.items():
            if cand in key:
                return col
    return None


def detect_exposure_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, _EAD_CANDIDATES)


def detect_ltv_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, _LTV_CANDIDATES)


# ───────────────────────── components ─────────────────────────

def model_pd(pipeline, X: pd.DataFrame) -> pd.Series:
    """PD straight from the trained classifier's probability output."""
    if not hasattr(pipeline, "predict_proba"):
        raise ValueError("The selected model has no predict_proba; PD cannot be read from it. "
                         "Use a probabilistic classifier (LogReg / RF / XGBoost / LightGBM).")
    proba = pipeline.predict_proba(X)
    pd_vals = proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else np.ravel(proba)
    return pd.Series(np.clip(pd_vals, 1e-6, 1.0), index=X.index, name="pd")


def estimate_ead(data: pd.DataFrame, ead_col: str, cfg: ECLConfig) -> pd.Series:
    base = pd.to_numeric(data[ead_col], errors="coerce")
    base = base.fillna(base.median() if base.notna().any() else 0.0)
    if cfg.ead_undrawn_col and cfg.ead_undrawn_col in data.columns:
        undrawn = pd.to_numeric(data[cfg.ead_undrawn_col], errors="coerce").fillna(0.0)
        base = base + cfg.ead_ccf * undrawn
    return base.clip(lower=0.0).rename("ead")


def estimate_lgd(data: pd.DataFrame, cfg: ECLConfig) -> pd.Series:
    if cfg.lgd_method == "ltv" and cfg.ltv_col and cfg.ltv_col in data.columns:
        ltv = pd.to_numeric(data[cfg.ltv_col], errors="coerce")
        coverage = (1.0 / ltv.replace(0, np.nan)) * (1.0 - cfg.lgd_haircut)
        recovery = coverage.clip(upper=1.0)
        lgd = (1.0 - recovery).clip(cfg.lgd_floor, cfg.lgd_cap)
        return lgd.fillna(cfg.lgd_fixed).rename("lgd")
    return pd.Series(float(cfg.lgd_fixed), index=data.index, name="lgd")


def estimate_lgd_by_type(data: pd.DataFrame, loan_type_col: str,
                         lgd_map: dict, cfg: ECLConfig) -> pd.Series:
    """Per-row LGD using a per-loan-type fixed LGD map, falling back to cfg.lgd_fixed."""
    lgd = pd.Series(float(cfg.lgd_fixed), index=data.index, name="lgd")
    if loan_type_col and loan_type_col in data.columns:
        for loan_type, lgd_val in lgd_map.items():
            mask = data[loan_type_col].astype(str) == str(loan_type)
            lgd[mask] = float(lgd_val)
    return lgd.clip(cfg.lgd_floor, cfg.lgd_cap)


def compute(pipeline, X: pd.DataFrame, data: pd.DataFrame, ead_col: str,
            cfg: ECLConfig = None, loan_type_col: str = None,
            lgd_map: dict = None) -> tuple[pd.DataFrame, dict]:
    """Return (per-loan result_df, summary). data is aligned to X by index."""
    cfg = cfg or ECLConfig()
    idx = X.index
    pd_s = model_pd(pipeline, X)
    ead = estimate_ead(data, ead_col, cfg).reindex(idx)

    if loan_type_col and lgd_map:
        lgd = estimate_lgd_by_type(data, loan_type_col, lgd_map, cfg).reindex(idx)
    else:
        lgd = estimate_lgd(data, cfg).reindex(idx)

    ecl = (pd_s * lgd * ead).rename("ecl")

    res = pd.DataFrame({"pd": pd_s.round(6), "lgd": lgd.round(4),
                        "ead": ead.round(2), "ecl": ecl.round(2)})

    total_ead = float(ead.sum())
    total_ecl = float(ecl.sum())
    summary = {
        "loans": int(len(res)),
        "avg_pd": round(float(pd_s.mean()), 4),
        "avg_lgd": round(float(lgd.mean()), 4),
        "total_ead": round(total_ead, 2),
        "total_ecl": round(total_ecl, 2),
        "coverage_pct": round(total_ecl / total_ead * 100, 3) if total_ead else 0.0,
    }
    return res, summary


# ───────────────────────── plots (match app theme) ─────────────────────────

def _layout(title):
    return dict(
        title=dict(text=title, font=dict(color=COLORS["text"], size=16)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"]), margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(gridcolor="#334155"), yaxis=dict(gridcolor="#334155"),
    )


def plot_ecl_by_pd_band(res: pd.DataFrame) -> go.Figure:
    df = res.copy()
    try:
        df["band"] = pd.qcut(df["pd"], q=10, duplicates="drop")
    except Exception:
        df["band"] = pd.cut(df["pd"], bins=10)
    grp = df.groupby("band", observed=False)["ecl"].sum().reset_index()
    grp["label"] = grp["band"].astype(str)
    fig = go.Figure(go.Bar(
        x=grp["label"], y=grp["ecl"],
        marker=dict(color=grp["ecl"], colorscale=[[0, COLORS["neutral"]], [1, COLORS["danger"]]]),
    ))
    fig.update_layout(**_layout("ECL contribution by PD band"))
    fig.update_xaxes(title_text="PD band (low → high)", tickangle=-40)
    fig.update_yaxes(title_text="Total ECL")
    return fig


def plot_pd_distribution(res: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Histogram(
        x=res["pd"], nbinsx=40, marker_color=COLORS["primary"], opacity=0.85,
    ))
    fig.update_layout(**_layout("Distribution of model PD"))
    fig.update_xaxes(title_text="Predicted default probability (PD)")
    fig.update_yaxes(title_text="Loans")
    return fig
