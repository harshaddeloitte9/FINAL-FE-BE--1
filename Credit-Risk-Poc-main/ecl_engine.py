"""
ecl_engine.py — ECL calculation with full IFRS 9 staging (SICR + lifetime PD).

IFRS 9 staging pipeline:
  Stage 1 : No significant increase in credit risk since origination.
            ECL = 12-month PD × LGD × EAD
  Stage 2 : SICR detected but not yet credit-impaired.
            ECL = Lifetime PD × LGD × EAD
  Stage 3 : Credit-impaired (DPD >= 90, or absolute PD >= credit_impaired_pd_threshold).
            ECL = Lifetime PD × LGD × EAD  (same formula as Stage 2, higher PD)

SICR is assessed via two criteria (IFRS 9 §5.5.9 / §B5.5.15-22):
  Quantitative : Current PD has increased by more than pd_relative_threshold (%) OR
                 pd_absolute_threshold (absolute pp) relative to origination PD.
  Qualitative  : DPD >= dpd_30_threshold (default 30 days) but < 90 days.
  Backstop     : DPD >= 30 days triggers SICR even if PD movement is below threshold
                 (IFRS 9 rebuttable presumption at 30 DPD, hard backstop at 90 DPD).

Lifetime PD estimation:
  The model produces a point-in-time 12-month PD. We extend it to a lifetime PD
  using a configurable duration multiplier (maturity-based) or the built-in
  exponential survival curve approach:
    lifetime_PD = 1 − (1 − 12m_PD)^n_years
  where n_years defaults to remaining_maturity_years if a maturity column is present,
  otherwise falls back to a portfolio-level assumption (default 3 years).

Existing API (compute, ECLConfig, model_pd, etc.) is fully backward-compatible.
New staging fields added to the result DataFrame:
  sicr_flag, ifrs9_stage, pd_12m, pd_lifetime, ecl_12m (Stage 1 reference), ecl
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {
    "primary":   "#6366f1",
    "secondary": "#f59e0b",
    "success":   "#10b981",
    "danger":    "#ef4444",
    "warning":   "#f97316",
    "neutral":   "#64748b",
    "text":      "#e2e8f0",
    "stage1":    "#10b981",   # green
    "stage2":    "#f59e0b",   # amber
    "stage3":    "#ef4444",   # red
}

# ── Column name heuristics ─────────────────────────────────────────────────────

_EAD_CANDIDATES = [
    "exposure_at_default", "ead", "exposure", "current_balance",
    "outstanding_balance", "balance", "loan_amount",
    "original_loan_amount", "principal", "drawn_amount",
]
_LTV_CANDIDATES = ["loan_to_value", "ltv", "loan_to_value_ratio"]
_DPD_CANDIDATES = [
    "days_past_due", "dpd", "days_overdue", "overdue_days",
    "days_delinquent", "delinquency_days", "arrears_days",
]
_ORIG_PD_CANDIDATES = [
    "origination_pd", "orig_pd", "pd_at_origination", "initial_pd",
    "pd_origination", "pd_orig", "base_pd",
]
_MATURITY_CANDIDATES = [
    "remaining_maturity", "remaining_maturity_years", "maturity_years",
    "loan_term_remaining", "term_remaining", "years_to_maturity",
]


# ── Configuration dataclass ────────────────────────────────────────────────────

@dataclass
class ECLConfig:
    # LGD
    lgd_method: str = "fixed"       # "fixed" | "ltv" | "ml"
    lgd_fixed: float = 0.45
    ltv_col: Optional[str] = None
    lgd_haircut: float = 0.20
    lgd_floor: float = 0.05
    lgd_cap: float = 0.95

    # ML-based LGD (predicted by a trained lgd_engine model)
    lgd_model: Optional[Any] = None    # bundle from lgd_engine.train_lgd_model()
    lgd_macro: Optional[Any] = None    # point-in-time macro frame aligned to the portfolio

    # EAD
    ead_undrawn_col: Optional[str] = None
    ead_ccf: float = 1.0

    # SICR thresholds (IFRS 9 §B5.5.15)
    pd_relative_threshold: float = 1.5   # current PD / origination PD > this → SICR
    pd_absolute_threshold: float = 0.03  # current PD - origination PD > this (abs pp) → SICR
    dpd_sicr_threshold: int = 30          # DPD >= this → SICR backstop
    dpd_impaired_threshold: int = 90      # DPD >= this → Stage 3 (credit-impaired)

    # Stage 3 PD floor (even if model PD is low, impaired loans get this minimum)
    credit_impaired_pd_floor: float = 0.20

    # Lifetime PD estimation
    maturity_col: Optional[str] = None               # override auto-detection

    # Column overrides (optional — auto-detected if None)
    dpd_col: Optional[str] = None
    orig_pd_col: Optional[str] = None


# ── Column detection helpers ───────────────────────────────────────────────────

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

def detect_dpd_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, _DPD_CANDIDATES)

def detect_orig_pd_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, _ORIG_PD_CANDIDATES)

def detect_maturity_col(df: pd.DataFrame) -> Optional[str]:
    return _detect(df, _MATURITY_CANDIDATES)


# ── PD components ──────────────────────────────────────────────────────────────

def model_pd(pipeline, X: pd.DataFrame) -> pd.Series:
    """12-month point-in-time PD from the trained classifier."""
    if not hasattr(pipeline, "predict_proba"):
        raise ValueError(
            "The selected model has no predict_proba; PD cannot be read from it. "
            "Use a probabilistic classifier (LogReg / RF / XGBoost / LightGBM)."
        )
    proba = pipeline.predict_proba(X)
    pd_vals = proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else np.ravel(proba)
    return pd.Series(np.clip(pd_vals, 1e-6, 1.0 - 1e-6), index=X.index, name="pd_12m")


def estimate_lifetime_pd(
    pd_12m: pd.Series,
    remaining_years: pd.Series,
) -> pd.Series:
    """
    Extend 12-month PD to lifetime PD using the exponential survival curve:

        lifetime_PD = 1 − (1 − pd_12m) ^ n_years

    This is the standard actuarial extension used in IFRS 9 ECL models when
    a full through-the-cycle term structure is not available.  For n_years = 1
    it reduces exactly to pd_12m.  Clipped to [pd_12m, 1 − ε] to ensure
    lifetime PD is never lower than 12-month PD.

    Args:
        pd_12m          : Annual (12-month) PD per loan.
        remaining_years : Remaining maturity in years per loan (can be fractional).
    """
    n = remaining_years.clip(lower=1.0)          # minimum 1-year horizon
    survival_annual = (1.0 - pd_12m).clip(1e-9, 1.0)
    lifetime_pd = 1.0 - survival_annual ** n
    lifetime_pd = lifetime_pd.clip(lower=pd_12m, upper=1.0 - 1e-6)
    return lifetime_pd.rename("pd_lifetime")


# ── SICR & staging ─────────────────────────────────────────────────────────────

def assess_sicr_and_stage(
    data: pd.DataFrame,
    pd_12m: pd.Series,
    cfg: ECLConfig,
) -> pd.DataFrame:
    """
    Assess SICR and assign IFRS 9 stages (1, 2, 3) for each loan.

    IFRS 9 staging logic:
    ┌──────────────────────────────────────────────────────────────────────────┐
    │ Stage 3 (credit-impaired) — assessed FIRST as the hardest backstop       │
    │   • DPD >= dpd_impaired_threshold (default 90), OR                       │
    │   • Current PD >= credit_impaired_pd_floor (absolute floor, e.g. 20%)   │
    │                                                                           │
    │ Stage 2 (SICR, not yet impaired) — if Stage 3 not triggered:             │
    │   Quantitative SICR:                                                     │
    │     • pd_current / pd_orig > pd_relative_threshold (e.g. 1.5×), OR      │
    │     • pd_current − pd_orig > pd_absolute_threshold (e.g. 0.03 pp)       │
    │   Qualitative SICR (DPD backstop, IFRS 9 §B5.5.19):                     │
    │     • DPD >= dpd_sicr_threshold (default 30 days)                        │
    │                                                                           │
    │ Stage 1 (performing) — neither Stage 2 nor Stage 3 criteria met          │
    └──────────────────────────────────────────────────────────────────────────┘

    Returns a DataFrame with columns:
        dpd, orig_pd, pd_12m, sicr_quantitative, sicr_qualitative,
        sicr_flag, ifrs9_stage
    """
    idx = pd_12m.index
    result = pd.DataFrame(index=idx)
    result["pd_12m"] = pd_12m

    # ── DPD ────────────────────────────────────────────────────────────────────
    dpd_col = cfg.dpd_col or detect_dpd_col(data)
    if dpd_col and dpd_col in data.columns:
        result["dpd"] = pd.to_numeric(data[dpd_col].reindex(idx), errors="coerce").fillna(0.0).clip(lower=0)
    else:
        result["dpd"] = 0.0   # DPD not available — conservative: no DPD-based SICR

    # ── Origination PD ─────────────────────────────────────────────────────────
    orig_pd_col = cfg.orig_pd_col or detect_orig_pd_col(data)
    if orig_pd_col and orig_pd_col in data.columns:
        orig_pd = pd.to_numeric(data[orig_pd_col].reindex(idx), errors="coerce")
        # Origination PD must be a valid probability; invalid → use current PD (neutral)
        orig_pd = orig_pd.clip(1e-6, 1.0 - 1e-6).fillna(pd_12m)
    else:
        # No origination PD column: cannot compute quantitative SICR
        # Fall back to current PD as origination (no relative change)
        orig_pd = pd_12m.copy()

    result["orig_pd"] = orig_pd

    # ── Quantitative SICR ──────────────────────────────────────────────────────
    # Relative: current PD / origination PD exceeds threshold
    pd_ratio = pd_12m / orig_pd.replace(0, np.nan).fillna(1.0)
    sicr_relative = pd_ratio > cfg.pd_relative_threshold

    # Absolute: current PD has risen by more than X percentage points
    pd_abs_change = pd_12m - orig_pd
    sicr_absolute = pd_abs_change > cfg.pd_absolute_threshold

    result["sicr_quantitative"] = sicr_relative | sicr_absolute

    # ── Qualitative SICR (DPD backstop) ────────────────────────────────────────
    result["sicr_qualitative"] = result["dpd"] >= cfg.dpd_sicr_threshold

    result["sicr_flag"] = result["sicr_quantitative"] | result["sicr_qualitative"]

    # ── Stage assignment ────────────────────────────────────────────────────────
    # Stage 3 first (credit-impaired)
    stage3_mask = (result["dpd"] >= cfg.dpd_impaired_threshold) | (
        pd_12m >= cfg.credit_impaired_pd_floor
    )
    # Stage 2: SICR but not yet impaired
    stage2_mask = result["sicr_flag"] & ~stage3_mask
    # Stage 1: everything else
    stage1_mask = ~stage3_mask & ~stage2_mask

    result["ifrs9_stage"] = np.select(
        [stage3_mask, stage2_mask, stage1_mask],
        [3, 2, 1],
        default=1,
    ).astype(int)

    return result


# ── LGD helpers ────────────────────────────────────────────────────────────────

def estimate_ead(data: pd.DataFrame, ead_col: str, cfg: ECLConfig) -> pd.Series:
    base = pd.to_numeric(data[ead_col], errors="coerce")
    base = base.fillna(base.median() if base.notna().any() else 0.0)
    if cfg.ead_undrawn_col and cfg.ead_undrawn_col in data.columns:
        undrawn = pd.to_numeric(data[cfg.ead_undrawn_col], errors="coerce").fillna(0.0)
        base = base + cfg.ead_ccf * undrawn
    return base.clip(lower=0.0).rename("ead")


def estimate_lgd(data: pd.DataFrame, cfg: ECLConfig) -> pd.Series:
    # ML-predicted LGD from a trained lgd_engine model (with macro features).
    if cfg.lgd_method == "ml" and getattr(cfg, "lgd_model", None) is not None:
        import lgd_engine
        lgd = lgd_engine.predict_lgd(
            cfg.lgd_model, data, macro_aligned=getattr(cfg, "lgd_macro", None)
        )
        return lgd.clip(cfg.lgd_floor, cfg.lgd_cap).reindex(data.index).rename("lgd")
    if cfg.lgd_method == "ltv" and cfg.ltv_col and cfg.ltv_col in data.columns:
        ltv = pd.to_numeric(data[cfg.ltv_col], errors="coerce")
        coverage = (1.0 / ltv.replace(0, np.nan)) * (1.0 - cfg.lgd_haircut)
        recovery = coverage.clip(upper=1.0)
        lgd = (1.0 - recovery).clip(cfg.lgd_floor, cfg.lgd_cap)
        return lgd.fillna(cfg.lgd_fixed).rename("lgd")
    return pd.Series(float(cfg.lgd_fixed), index=data.index, name="lgd")


def estimate_lgd_by_type(
    data: pd.DataFrame,
    loan_type_col: str,
    lgd_map: dict,
    cfg: ECLConfig,
) -> pd.Series:
    lgd = pd.Series(float(cfg.lgd_fixed), index=data.index, name="lgd")
    if loan_type_col and loan_type_col in data.columns:
        for loan_type, lgd_val in lgd_map.items():
            mask = data[loan_type_col].astype(str) == str(loan_type)
            lgd[mask] = float(lgd_val)
    return lgd.clip(cfg.lgd_floor, cfg.lgd_cap)


# ── Main compute function ──────────────────────────────────────────────────────

def compute(
    pipeline,
    X: pd.DataFrame,
    data: pd.DataFrame,
    ead_col: str = None,
    cfg: ECLConfig = None,
    loan_type_col: str = None,
    lgd_map: dict = None,
    ead_series: pd.Series = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Compute per-loan ECL with full IFRS 9 staging.

    Returns
    -------
    result_df : pd.DataFrame
        One row per loan with columns:
        dpd, orig_pd, pd_12m, pd_lifetime, sicr_quantitative, sicr_qualitative,
        sicr_flag, ifrs9_stage, lgd, ead, ecl_12m, ecl

        ecl_12m  = 12-month ECL (Stage 1 reference, always computed)
        ecl      = IFRS 9 ECL: 12m for Stage 1, lifetime for Stage 2 & 3

    summary : dict
        Portfolio-level aggregates including stage breakdown.
    """
    cfg = cfg or ECLConfig()
    idx = X.index

    # ── 1. Get 12-month PD from model ──────────────────────────────────────────
    pd_12m = model_pd(pipeline, X)

    # ── 2. SICR assessment & staging ──────────────────────────────────────────
    staging = assess_sicr_and_stage(data.reindex(idx), pd_12m, cfg)

    # ── 3. Remaining maturity for lifetime PD ─────────────────────────────────
    mat_col = cfg.maturity_col or detect_maturity_col(data)
    if mat_col and mat_col in data.columns:
        remaining_years = (
            pd.to_numeric(data[mat_col].reindex(idx), errors="coerce")
            .fillna(1.0)   # any unparseable value → 1 year (no lifetime extension)
            .clip(lower=1.0)
        )
    else:
        # No maturity column found — lifetime PD = 12m PD (n_years=1, no extension).
        # Stage 2/3 loans will still use this PD, which is conservative for short-tenor
        # books but correct when maturity data is unavailable.
        remaining_years = pd.Series(1.0, index=idx, name="remaining_years")

    # ── 4. Lifetime PD ────────────────────────────────────────────────────────
    # For Stage 3: apply credit_impaired_pd_floor before extending to lifetime
    pd_for_lifetime = pd_12m.copy()
    stage3_mask = staging["ifrs9_stage"] == 3
    pd_for_lifetime[stage3_mask] = pd_for_lifetime[stage3_mask].clip(
        lower=cfg.credit_impaired_pd_floor
    )
    pd_lifetime = estimate_lifetime_pd(pd_for_lifetime, remaining_years)

    # ── 5. EAD & LGD ─────────────────────────────────────────────────────────
    if ead_series is not None:
        _ead = pd.to_numeric(pd.Series(ead_series), errors="coerce").reindex(idx)
        _ead = _ead.fillna(_ead.median() if _ead.notna().any() else 0.0)
        ead = _ead.clip(lower=0.0).rename("ead")
    else:
        ead = estimate_ead(data.reindex(idx), ead_col, cfg)
    if loan_type_col and lgd_map:
        lgd = estimate_lgd_by_type(data.reindex(idx), loan_type_col, lgd_map, cfg)
    else:
        lgd = estimate_lgd(data.reindex(idx), cfg)

    # ── 6. ECL calculation ────────────────────────────────────────────────────
    # 12-month ECL (Stage 1 basis — always computed for reference)
    ecl_12m = (pd_12m * lgd * ead).rename("ecl_12m")

    # IFRS 9 ECL: use 12m PD for Stage 1, lifetime PD for Stage 2 & 3
    pd_for_ecl = pd_12m.copy()
    stage2_or_3 = staging["ifrs9_stage"].isin([2, 3])
    pd_for_ecl[stage2_or_3] = pd_lifetime[stage2_or_3]

    ecl = (pd_for_ecl * lgd * ead).rename("ecl")

    # ── 7. Assemble result DataFrame ──────────────────────────────────────────
    res = pd.concat([
        staging[["dpd", "orig_pd", "pd_12m", "sicr_quantitative", "sicr_qualitative",
                  "sicr_flag", "ifrs9_stage"]],
        pd_lifetime.rename("pd_lifetime"),
        lgd.rename("lgd"),
        ead.rename("ead"),
        ecl_12m.round(2),
        ecl.round(2),
    ], axis=1)

    # Round probabilities for display
    for col in ["orig_pd", "pd_12m", "pd_lifetime", "lgd"]:
        res[col] = res[col].round(6)

    # ── 8. Portfolio summary ──────────────────────────────────────────────────
    stage_counts = res["ifrs9_stage"].value_counts().to_dict()
    total_ead = float(ead.sum())
    total_ecl = float(ecl.sum())
    total_ecl_12m = float(ecl_12m.sum())

    ecl_by_stage = (
        res.groupby("ifrs9_stage")["ecl"].sum()
        .reindex([1, 2, 3], fill_value=0.0)
        .round(2)
        .to_dict()
    )
    ead_by_stage = (
        res.groupby("ifrs9_stage")["ead"].sum()
        .reindex([1, 2, 3], fill_value=0.0)
        .round(2)
        .to_dict()
    )

    summary = {
        "loans":              int(len(res)),
        "avg_pd_12m":         round(float(pd_12m.mean()), 4),
        "avg_pd_lifetime":    round(float(pd_lifetime.mean()), 4),
        "avg_lgd":            round(float(lgd.mean()), 4),
        "total_ead":          round(total_ead, 2),
        "total_ecl":          round(total_ecl, 2),
        "total_ecl_12m":      round(total_ecl_12m, 2),
        "coverage_pct":       round(total_ecl / total_ead * 100, 3) if total_ead else 0.0,
        "coverage_pct_12m":   round(total_ecl_12m / total_ead * 100, 3) if total_ead else 0.0,
        "stage_counts":       {f"stage_{k}": int(stage_counts.get(k, 0)) for k in [1, 2, 3]},
        "ecl_by_stage":       {f"stage_{k}": float(ecl_by_stage.get(k, 0.0)) for k in [1, 2, 3]},
        "ead_by_stage":       {f"stage_{k}": float(ead_by_stage.get(k, 0.0)) for k in [1, 2, 3]},
        "sicr_count":         int(res["sicr_flag"].sum()),
        "sicr_pct":           round(float(res["sicr_flag"].mean()) * 100, 2),
        # backward-compat alias
        "avg_pd":             round(float(pd_12m.mean()), 4),
    }
    return res, summary


# ── Plotly charts ──────────────────────────────────────────────────────────────

def _layout(title: str, **kwargs) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=COLORS["text"], size=16)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"]),
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(gridcolor="#334155"),
        yaxis=dict(gridcolor="#334155"),
        **kwargs,
    )


def plot_ecl_by_pd_band(res: pd.DataFrame) -> go.Figure:
    df = res.copy()
    try:
        df["band"] = pd.qcut(df["pd_12m"], q=10, duplicates="drop")
    except Exception:
        df["band"] = pd.cut(df["pd_12m"], bins=10)
    grp = df.groupby("band", observed=False)["ecl"].sum().reset_index()
    grp["label"] = grp["band"].astype(str)
    fig = go.Figure(go.Bar(
        x=grp["label"], y=grp["ecl"],
        marker=dict(
            color=grp["ecl"],
            colorscale=[[0, COLORS["neutral"]], [1, COLORS["danger"]]],
        ),
    ))
    fig.update_layout(**_layout("ECL contribution by PD band"))
    fig.update_xaxes(title_text="PD band (low → high)", tickangle=-40)
    fig.update_yaxes(title_text="Total ECL")
    return fig


def plot_pd_distribution(res: pd.DataFrame) -> go.Figure:
    """Overlay 12-month vs lifetime PD distributions."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=res["pd_12m"], nbinsx=40, name="12-month PD",
        marker_color=COLORS["primary"], opacity=0.7, histnorm="probability density",
    ))
    if "pd_lifetime" in res.columns:
        fig.add_trace(go.Histogram(
            x=res["pd_lifetime"], nbinsx=40, name="Lifetime PD",
            marker_color=COLORS["secondary"], opacity=0.7, histnorm="probability density",
        ))
    fig.update_layout(**_layout("12-month vs Lifetime PD distribution"), barmode="overlay")
    fig.update_xaxes(title_text="Predicted default probability")
    fig.update_yaxes(title_text="Density")
    return fig


def plot_stage_loan_count(res: pd.DataFrame) -> go.Figure:
    """Bar chart: loan count by IFRS 9 stage."""
    stage_labels = {1: "Stage 1 — Performing", 2: "Stage 2 — SICR", 3: "Stage 3 — Impaired"}
    stage_colors = {1: COLORS["stage1"], 2: COLORS["stage2"], 3: COLORS["stage3"]}

    grp = res.groupby("ifrs9_stage")["ecl"].count().reindex([1, 2, 3], fill_value=0)

    fig = go.Figure()
    for stage in [1, 2, 3]:
        label = stage_labels[stage]
        fig.add_trace(go.Bar(
            name=label, x=[label], y=[int(grp.loc[stage])],
            marker_color=stage_colors[stage],
        ))
    fig.update_layout(**_layout("Loan count by IFRS 9 stage"), showlegend=False)
    fig.update_yaxes(title_text="Number of loans")
    return fig


def plot_stage_ecl(res: pd.DataFrame) -> go.Figure:
    """Bar chart: total ECL by IFRS 9 stage."""
    stage_labels = {1: "Stage 1 — Performing", 2: "Stage 2 — SICR", 3: "Stage 3 — Impaired"}
    stage_colors = {1: COLORS["stage1"], 2: COLORS["stage2"], 3: COLORS["stage3"]}

    grp = res.groupby("ifrs9_stage")["ecl"].sum().reindex([1, 2, 3], fill_value=0)

    fig = go.Figure()
    for stage in [1, 2, 3]:
        label = stage_labels[stage]
        fig.add_trace(go.Bar(
            name=label, x=[label], y=[float(grp.loc[stage])],
            marker_color=stage_colors[stage],
        ))
    fig.update_layout(**_layout("ECL by IFRS 9 stage"), showlegend=False)
    fig.update_yaxes(title_text="Total ECL")
    return fig


def plot_sicr_drivers(res: pd.DataFrame) -> go.Figure:
    """Pie chart: what drove SICR — quantitative vs qualitative vs both."""
    sicr = res[res["sicr_flag"]].copy()
    if sicr.empty:
        fig = go.Figure()
        fig.update_layout(**_layout("SICR Driver Breakdown (no SICR loans)"))
        return fig

    both  = int((sicr["sicr_quantitative"] & sicr["sicr_qualitative"]).sum())
    quant = int((sicr["sicr_quantitative"] & ~sicr["sicr_qualitative"]).sum())
    qual  = int((~sicr["sicr_quantitative"] & sicr["sicr_qualitative"]).sum())

    fig = go.Figure(go.Pie(
        labels=["Quantitative only (PD rise)", "Qualitative only (DPD ≥ 30)", "Both"],
        values=[quant, qual, both],
        marker_colors=[COLORS["primary"], COLORS["secondary"], COLORS["danger"]],
        hole=0.4,
    ))
    fig.update_layout(**_layout("SICR Driver Breakdown"))
    return fig


def plot_ecl_12m_vs_lifetime(res: pd.DataFrame) -> go.Figure:
    """Scatter: 12-month ECL vs lifetime ECL, coloured by stage."""
    stage_colors_map = {1: COLORS["stage1"], 2: COLORS["stage2"], 3: COLORS["stage3"]}
    stage_labels = {1: "Stage 1", 2: "Stage 2", 3: "Stage 3"}
    fig = go.Figure()
    for stage in [1, 2, 3]:
        sub = res[res["ifrs9_stage"] == stage]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["ecl_12m"], y=sub["ecl"],
            mode="markers",
            name=stage_labels[stage],
            marker=dict(color=stage_colors_map[stage], size=4, opacity=0.6),
        ))
    # Diagonal reference line
    max_val = float(max(res["ecl_12m"].max(), res["ecl"].max()))
    fig.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode="lines", name="12m = Lifetime",
        line=dict(color=COLORS["neutral"], dash="dash"),
    ))
    fig.update_layout(**_layout("12-month ECL vs IFRS 9 ECL (by stage)"))
    fig.update_xaxes(title_text="12-month ECL")
    fig.update_yaxes(title_text="IFRS 9 ECL (lifetime for Stage 2 & 3)")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# EAD calculation — moved here from feature_engineering.py (logic unchanged).
# The ECL engine now owns the Exposure-at-Default computation system:
#   EAD = Outstanding Principal (amortising balance after last completed payment)
#         + Accrued Interest (current period only)
# feature_engineering.py re-exports these names for backward compatibility.
# ══════════════════════════════════════════════════════════════════════════════

# ── Outstanding-balance / EAD resolution (computed here, used as EAD in ECL) ───
_OUTSTANDING_BALANCE_SYNONYMS = [
    "outstanding_balance", "outstanding_principal", "current_balance",
    "book_balance", "loan_balance", "principal_outstanding",
    "outstanding_amount", "balance_outstanding", "current_principal", "outstanding",
]
_LOAN_AMOUNT_SYNONYMS = [
    "loan_amount", "total_loan_amount", "original_loan_amount", "sanctioned_amount",
    "disbursed_amount", "loan_principal", "original_principal", "principal", "loan_amt",
]
_INTEREST_RATE_SYNONYMS = [
    "interest_rate", "int_rate", "interest", "apr", "coupon",
    "annual_rate", "nominal_rate", "rate",
]
_YEARS_ELAPSED_SYNONYMS = [
    "years_elapsed", "years_on_book", "loan_age_years", "age_years",
    "seasoning_years", "elapsed_years", "time_on_book_years",
]
_MONTHS_ELAPSED_SYNONYMS = [
    "months_on_book", "loan_age_months", "age_months", "seasoning_months",
    "months_elapsed", "mob", "time_on_book",
]
_TERM_SYNONYMS = [
    "term_years", "loan_term_years", "tenure_years", "maturity_years",
    "original_term", "loan_term", "tenure", "term",
]
_PAYMENT_FREQUENCY_SYNONYMS = [
    "payment_frequency", "repayment_frequency", "installment_frequency",
    "pay_frequency", "freq", "frequency",
]

# Number of payment periods per year, by frequency label.
PAYMENT_FREQUENCIES: Dict[str, int] = {
    "monthly": 12,
    "quarterly": 4,
    "semi-annual": 2,
    "annual": 1,
}
DEFAULT_PAYMENT_FREQUENCY = "monthly"


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _match_column(columns, synonyms):
    norm = {_norm_name(c): c for c in columns}
    for syn in synonyms:                       # exact (normalized) match first
        if _norm_name(syn) in norm:
            return norm[_norm_name(syn)]
    for syn in synonyms:                       # then substring match
        ns = _norm_name(syn)
        for nc, orig in norm.items():
            if ns and ns in nc:
                return orig
    return None


def detect_outstanding_balance_col(df):
    return _match_column(df.columns, _OUTSTANDING_BALANCE_SYNONYMS)


def detect_loan_amount_col(df):
    return _match_column(df.columns, _LOAN_AMOUNT_SYNONYMS)


def detect_interest_rate_col(df):
    return _match_column(df.columns, _INTEREST_RATE_SYNONYMS)


def detect_years_elapsed_col(df):
    """Return (column, is_in_months)."""
    col = _match_column(df.columns, _YEARS_ELAPSED_SYNONYMS)
    if col:
        return col, False
    col = _match_column(df.columns, _MONTHS_ELAPSED_SYNONYMS)
    if col:
        return col, True
    return None, False


def detect_term_col(df):
    return _match_column(df.columns, _TERM_SYNONYMS)


def detect_payment_frequency_col(df):
    return _match_column(df.columns, _PAYMENT_FREQUENCY_SYNONYMS)


def compute_outstanding_balance(loan_amount, interest_rate, years_elapsed,
                                term_years=None, rate_is_percent=None):
    """
    Outstanding balance per loan from loan amount, annual interest rate and years
    elapsed. With a loan term, an amortizing (declining) balance is used:

        B = P * ((1+r)^N - (1+r)^m) / ((1+r)^N - 1)     (m = elapsed, N = term)

    Without a term, an interest-accrual balance is used: B = P * (1+r)^m.
    The interest rate is auto-normalised from percent to a fraction when needed.
    All inputs are pandas Series sharing one index.

    NOTE: This is the legacy continuous-time balance function, retained for
    backward compatibility with any code that still calls it directly. For EAD
    estimation, use compute_ead() below, which models a real discrete payment
    schedule (monthly/quarterly/semi-annual/annual) and avoids double-counting
    between the amortizing balance and the accrued-interest add-on.
    """
    P = pd.to_numeric(loan_amount, errors="coerce").astype(float)
    r = pd.to_numeric(interest_rate, errors="coerce").astype(float)
    t = pd.to_numeric(years_elapsed, errors="coerce").astype(float)
    idx = P.index

    P = P.fillna(0.0).clip(lower=0)
    nonzero = r.replace(0, np.nan).dropna()
    auto_percent = bool(len(nonzero)) and float(nonzero.median()) > 1.0
    if rate_is_percent is True or (rate_is_percent is None and auto_percent):
        r = r / 100.0
    r = r.fillna(0.0).clip(lower=0)
    t = t.fillna(0.0).clip(lower=0)

    if term_years is not None:
        N = pd.to_numeric(term_years, errors="coerce").reindex(idx).astype(float)
        N = N.where(N > 0).fillna(t.clip(lower=1.0))
        m = np.minimum(t, N)
        one_plus_r = 1.0 + r
        factor_N = one_plus_r ** N
        factor_m = one_plus_r ** m
        denom = (factor_N - 1.0).replace(0, np.nan)
        amort = P * (factor_N - factor_m) / denom
        straight = P * (1.0 - (m / N.replace(0, np.nan)).clip(0, 1))
        bal = amort.where(r > 1e-9, straight).fillna(straight)
    else:
        bal = P * (one_plus_r if False else (1.0 + r)) ** t

    return bal.clip(lower=0).rename("outstanding_balance")


def _periods_per_year(payment_frequency: str) -> int:
    """Map a payment frequency label to the number of payment periods per year."""
    key = str(payment_frequency).strip().lower()
    if key not in PAYMENT_FREQUENCIES:
        raise ValueError(
            f"Unknown payment_frequency '{payment_frequency}'. "
            f"Must be one of {list(PAYMENT_FREQUENCIES.keys())}."
        )
    return PAYMENT_FREQUENCIES[key]


def _amortizing_balance_after_k_payments(P, i_period, n_periods, k):
    """
    Standard level-payment amortization formula (vectorised, pandas/numpy).

    P         : original principal (Series)
    i_period  : periodic interest rate, i.e. annual rate / periods-per-year (Series)
    n_periods : total number of scheduled payments over the loan term (Series)
    k         : number of COMPLETED payments as of the valuation date (Series,
                already clipped to [0, n_periods])

    Returns the outstanding principal immediately after the k-th payment, using:

        B(k) = P * [(1+i)^n - (1+i)^k] / [(1+i)^n - 1]      (i > 0)
        B(k) = P * (1 - k/n)                                 (i == 0, straight-line)
    """
    one_i = 1.0 + i_period
    factor_n = one_i ** n_periods
    factor_k = one_i ** k
    denom = (factor_n - 1.0).replace(0, np.nan)
    amort = P * (factor_n - factor_k) / denom
    n_safe = n_periods.replace(0, np.nan)
    straight = P * (1.0 - (k / n_safe).clip(0, 1))
    return amort.where(i_period > 1e-12, straight).fillna(straight)


def compute_ead_schedule(
    loan_amount,
    interest_rate,
    years_elapsed,
    term_years,
    payment_frequency="monthly",
    rate_is_percent=None,
) -> Dict[str, pd.Series]:
    """
    Payment-schedule-based EAD engine.

        EAD = Outstanding Principal (as of the last completed payment)
              + Accrued Interest (since that last payment, for the elapsed
                fraction of the CURRENT payment period only)

    This replaces the old whole-year amortization assumption with a real
    discrete payment schedule, matching how retail loans are actually
    serviced (a fixed number of payments per year, not continuous
    compounding). Key mechanics:

      1. Periods per year (`f`) are derived from `payment_frequency`:
         monthly=12, quarterly=4, semi-annual=2, annual=1.
      2. `n_periods` = term_years * f                  -> total scheduled payments
      3. `periods_elapsed` = years_elapsed * f          -> continuous period count
      4. `k` = floor(periods_elapsed)                   -> number of COMPLETED
                                                            payment periods (the
                                                            last payment date)
      5. `frac` = periods_elapsed - k                   -> fraction of the
                                                            CURRENT (not yet
                                                            completed) period
                                                            that has elapsed
      6. Outstanding Principal = amortizing balance immediately after the
         k-th payment, using the standard level-payment amortization formula
         on the PERIODIC rate (annual_rate / f), not the annual rate. This is
         the balance "as of the last completed payment period."
      7. Accrued Interest = Outstanding Principal * periodic_rate * frac
         — simple interest on the post-last-payment balance, for only the
         fraction of the current period that has elapsed. Because the
         outstanding principal is anchored to the LAST COMPLETED period and
         the accrual covers only the CURRENT, not-yet-completed period, the
         two components are strictly additive with no overlap or double
         counting.
      8. EAD = Outstanding Principal + Accrued Interest.

    Parameters
    ----------
    loan_amount, interest_rate, years_elapsed, term_years : array-like / Series
        interest_rate is the ANNUAL nominal rate (auto-detected as percent vs.
        fraction the same way as compute_outstanding_balance, unless
        rate_is_percent is set explicitly).
    payment_frequency : str or Series of str
        One of "monthly", "quarterly", "semi-annual", "annual". Can be a
        single string applied to every row, or a per-row Series of labels
        (e.g. if different loans in the portfolio are serviced on different
        schedules).
    rate_is_percent : bool or None
        Forces percent/fraction interpretation of interest_rate; None = auto.

    Returns
    -------
    dict of aligned pandas Series:
        "periods_per_year"      : payment periods per year used per row
        "n_periods"             : total scheduled payments over the full term
        "periods_elapsed"       : continuous (fractional) periods elapsed
        "completed_periods"     : k, number of completed payments (last
                                   payment date marker)
        "period_fraction_elapsed": frac, fraction of the CURRENT period elapsed
        "periodic_rate"         : annual_rate / periods_per_year (as a fraction)
        "outstanding_principal" : amortizing balance after the k-th payment
        "accrued_interest"      : interest accrued since the last payment
        "ead"                   : outstanding_principal + accrued_interest
    """
    P = pd.to_numeric(loan_amount, errors="coerce").astype(float)
    idx = P.index
    P = P.fillna(0.0).clip(lower=0)

    r_annual = pd.to_numeric(interest_rate, errors="coerce").astype(float).reindex(idx)
    nonzero = r_annual.replace(0, np.nan).dropna()
    auto_percent = bool(len(nonzero)) and float(nonzero.median()) > 1.0
    if rate_is_percent is True or (rate_is_percent is None and auto_percent):
        r_annual = r_annual / 100.0
    r_annual = r_annual.fillna(0.0).clip(lower=0)

    t = pd.to_numeric(years_elapsed, errors="coerce").astype(float).reindex(idx).fillna(0.0).clip(lower=0)
    N_years = pd.to_numeric(term_years, errors="coerce").astype(float).reindex(idx)
    N_years = N_years.where(N_years > 0).fillna(t.clip(lower=1.0))

    # ── Payment frequency: scalar string or a per-row Series of labels ──────
    if isinstance(payment_frequency, pd.Series):
        freq_labels = payment_frequency.reindex(idx).fillna(DEFAULT_PAYMENT_FREQUENCY)
        freq_labels = freq_labels.astype(str).str.strip().str.lower()
        unknown = ~freq_labels.isin(PAYMENT_FREQUENCIES.keys())
        if unknown.any():
            freq_labels = freq_labels.where(~unknown, DEFAULT_PAYMENT_FREQUENCY)
        periods_per_year = freq_labels.map(PAYMENT_FREQUENCIES).astype(float)
    else:
        f = _periods_per_year(payment_frequency)
        freq_labels = pd.Series([str(payment_frequency).strip().lower()] * len(idx), index=idx)
        periods_per_year = pd.Series(float(f), index=idx)

    n_periods = (N_years * periods_per_year).round().clip(lower=1)
    periodic_rate = r_annual / periods_per_year

    periods_elapsed = (t * periods_per_year).clip(lower=0)
    periods_elapsed = np.minimum(periods_elapsed, n_periods)  # cap at maturity
    k = np.floor(periods_elapsed)
    frac = (periods_elapsed - k).clip(0, 1)

    outstanding_principal = _amortizing_balance_after_k_payments(
        P, periodic_rate, n_periods, k
    ).clip(lower=0)
    accrued_interest = (outstanding_principal * periodic_rate * frac).clip(lower=0)
    ead = (outstanding_principal + accrued_interest).clip(lower=0)

    return {
        "payment_frequency": freq_labels.rename("payment_frequency"),
        "periods_per_year": periods_per_year.rename("periods_per_year"),
        "n_periods": n_periods.rename("n_periods"),
        "periods_elapsed": periods_elapsed.rename("periods_elapsed"),
        "completed_periods": k.rename("completed_periods"),
        "period_fraction_elapsed": frac.rename("period_fraction_elapsed"),
        "periodic_rate": periodic_rate.rename("periodic_rate"),
        "annual_rate": r_annual.rename("annual_rate"),
        "outstanding_principal": outstanding_principal.rename("outstanding_principal"),
        "accrued_interest": accrued_interest.rename("accrued_interest"),
        "ead": ead.rename("ead"),
    }


def compute_ead(
    loan_amount,
    interest_rate,
    years_elapsed,
    term_years,
    payment_frequency="monthly",
    rate_is_percent=None,
) -> Dict[str, pd.Series]:
    """
    Thin convenience wrapper around compute_ead_schedule() — kept as the
    stable public entrypoint for the rest of the app (ECL engine, UI).

        EAD = Outstanding Principal (after last completed payment)
              + Accrued Interest (since last payment, current period only)

    See compute_ead_schedule() for the full mechanics and the complete set of
    intermediate values it returns (periods, fractions, periodic rate, etc.).
    This wrapper returns the same dict — nothing is dropped — so callers that
    want the full audit trail (e.g. the EAD validation export) can use either
    function interchangeably.
    """
    return compute_ead_schedule(
        loan_amount=loan_amount,
        interest_rate=interest_rate,
        years_elapsed=years_elapsed,
        term_years=term_years,
        payment_frequency=payment_frequency,
        rate_is_percent=rate_is_percent,
    )
