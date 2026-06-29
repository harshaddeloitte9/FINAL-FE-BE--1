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
from typing import Optional

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
    lgd_method: str = "fixed"       # "fixed" | "ltv"
    lgd_fixed: float = 0.45
    ltv_col: Optional[str] = None
    lgd_haircut: float = 0.20
    lgd_floor: float = 0.05
    lgd_cap: float = 0.95

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
    # Cast to float64 — XGBoost/LightGBM return float32 which causes pandas dtype errors downstream
    return pd.Series(np.clip(pd_vals.astype(np.float64), 1e-6, 1.0 - 1e-6), index=X.index, name="pd_12m")


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

    # Normalize float32 → float64 to prevent dtype assignment errors when XGBoost
    # or feature engineering produces float32 columns that reject float64 values.
    X = X.copy()
    for _col in X.columns:
        if str(X[_col].dtype) in ("float32", "Float32"):
            X[_col] = X[_col].astype("float64")
    data = data.copy()
    for _col in data.columns:
        if str(data[_col].dtype) in ("float32", "Float32"):
            data[_col] = data[_col].astype("float64")

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
