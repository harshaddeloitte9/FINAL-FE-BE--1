"""
ead_engine.py — Exposure at Default (EAD) engine.

Two regimes, split by product type:

  • REVOLVING products (credit cards, overdrafts, lines of credit) — EAD depends
    on how much of the *undrawn* limit the borrower draws down before default.
    That draw-down fraction is the Credit Conversion Factor (CCF), estimated with
    an ML regression model trained on defaulted revolving accounts:

        EAD = drawn balance + CCF × (credit limit − drawn balance)

    Realized CCF (training target) = (EAD_at_default − drawn) / (limit − drawn).

  • NON-REVOLVING products (term loans) — EAD is the amortising outstanding
    balance plus accrued interest, via the existing payment-schedule model
    (ecl_engine.compute_ead_schedule). No ML needed.

The CCF model reuses the regression training/prediction infrastructure from
lgd_engine (same split → preprocess → fit → predict), so the two ML parameters
(LGD and CCF) share a consistent, tested pipeline. FRED macro features can be
attached to the CCF model exactly as for LGD.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import lgd_engine as L                       # reuse regression trainer/predictor + macro
from ecl_engine import compute_ead_schedule  # amortisation EAD for non-revolving loans

# CCF uses the same regression model choices as LGD.
CCF_MODELS = L.LGD_MODELS


def available_models() -> List[str]:
    return L.available_models()


# ── Column detection ──────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _detect(df: pd.DataFrame, keywords) -> Optional[str]:
    norm = {c: _norm(c) for c in df.columns}
    for kw in keywords:
        k = _norm(kw)
        for c, n in norm.items():
            if n == k:
                return c
    for kw in keywords:
        k = _norm(kw)
        for c, n in norm.items():
            if k in n:
                return c
    return None


def detect_product_type_col(df):
    return _detect(df, ["product_type", "product", "loan_type", "facility_type", "account_type"])


def detect_drawn_balance_col(df):
    return _detect(df, ["drawn_balance", "drawn", "current_balance", "utilised_amount",
                        "utilized_amount", "outstanding_balance", "balance", "utilisation_amount"])


def detect_credit_limit_col(df):
    return _detect(df, ["credit_limit", "limit", "sanctioned_limit", "approved_limit",
                        "facility_limit", "credit_line"])


def detect_ead_at_default_col(df):
    return _detect(df, ["ead_at_default", "balance_at_default", "exposure_at_default",
                        "ead", "ead_default", "default_balance"])


def is_revolving(
    df: pd.DataFrame,
    product_col: Optional[str],
    revolving_values=("revolving", "card", "credit card", "cc", "overdraft", "od",
                      "line of credit", "loc", "revolver"),
) -> pd.Series:
    """Boolean mask: which accounts are revolving. If no product column, treats all
    accounts as non-revolving (amortising)."""
    if not product_col or product_col not in df.columns:
        return pd.Series(False, index=df.index)
    vals = {str(v).lower() for v in revolving_values}
    col = df[product_col].astype(str).str.strip().str.lower()
    return col.apply(lambda x: any(v in x for v in vals))


# ── CCF target ────────────────────────────────────────────────────────────────
def derive_ccf_target(
    df: pd.DataFrame,
    drawn_col: str,
    limit_col: str,
    ead_at_default_col: str,
    floor: float = 0.0,
    cap: float = 1.0,
) -> pd.Series:
    """
    Realized CCF = (EAD_at_default − drawn) / (limit − drawn), clipped to
    [floor, cap]. Rows with no undrawn headroom (limit ≤ drawn) are NaN (they
    carry no CCF information and are dropped from training).
    """
    drawn = pd.to_numeric(df[drawn_col], errors="coerce")
    limit = pd.to_numeric(df[limit_col], errors="coerce")
    ead_d = pd.to_numeric(df[ead_at_default_col], errors="coerce")
    undrawn = limit - drawn
    ccf = (ead_d - drawn) / undrawn.where(undrawn > 0, np.nan)
    return ccf.clip(lower=floor, upper=cap).rename("ccf_target")


def detect_ccf_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        "product_col": detect_product_type_col(df),
        "drawn_col": detect_drawn_balance_col(df),
        "limit_col": detect_credit_limit_col(df),
        "ead_at_default_col": detect_ead_at_default_col(df),
    }


# ── CCF model (reuses lgd_engine's regression pipeline) ───────────────────────
def train_ccf_model(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    target: pd.Series,
    model_name: str,
    macro_cols: Optional[List[str]] = None,
    test_size: float = 0.20,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Train the CCF regression model on defaulted REVOLVING accounts. Returns a
    bundle compatible with predict_ccf()."""
    bundle = L.train_lgd_model(
        train_df, feature_cols, target, model_name,
        macro_cols=macro_cols, test_size=test_size, random_state=random_state,
        lgd_floor=0.0, lgd_cap=1.0,
    )
    bundle["parameter"] = "CCF"
    return bundle


def predict_ccf(bundle: Dict[str, Any], df: pd.DataFrame,
                macro_aligned: Optional[pd.DataFrame] = None) -> pd.Series:
    """Predict CCF (clipped to [0,1]) for revolving accounts."""
    return L.predict_lgd(bundle, df, macro_aligned=macro_aligned).rename("ccf")


# ── EAD computation ───────────────────────────────────────────────────────────
def compute_ead_revolving(
    df: pd.DataFrame,
    drawn_col: str,
    limit_col: str,
    ccf: pd.Series,
) -> pd.Series:
    """EAD = drawn + CCF × (limit − drawn), for revolving accounts."""
    drawn = pd.to_numeric(df[drawn_col], errors="coerce")
    limit = pd.to_numeric(df[limit_col], errors="coerce")
    undrawn = (limit - drawn).clip(lower=0)
    ccf = pd.to_numeric(ccf.reindex(df.index), errors="coerce").clip(0.0, 1.0)
    return (drawn + ccf * undrawn).rename("ead")


def compute_portfolio_ead(
    df: pd.DataFrame,
    revolving_mask: pd.Series,
    *,
    # revolving inputs
    drawn_col: Optional[str] = None,
    limit_col: Optional[str] = None,
    ccf_series: Optional[pd.Series] = None,
    # non-revolving (amortisation) inputs
    loan_amount_col: Optional[str] = None,
    interest_rate_col: Optional[str] = None,
    years_elapsed_col: Optional[str] = None,
    term_col: Optional[str] = None,
    years_in_months: bool = False,
    term_in_months: bool = False,
    payment_frequency="monthly",
) -> pd.Series:
    """
    Portfolio EAD: revolving accounts use CCF (EAD = drawn + CCF·undrawn),
    non-revolving accounts use the amortisation schedule. Returns one EAD Series
    aligned to df.index.
    """
    ead = pd.Series(np.nan, index=df.index, dtype=float)
    rev = revolving_mask.reindex(df.index).fillna(False).astype(bool)

    # revolving → CCF
    if rev.any() and drawn_col and limit_col and ccf_series is not None:
        ead.loc[rev] = compute_ead_revolving(
            df.loc[rev], drawn_col, limit_col, ccf_series.reindex(df.index).loc[rev]
        ).values

    # non-revolving → amortisation
    nonrev = ~rev
    if nonrev.any() and loan_amount_col and interest_rate_col and years_elapsed_col and term_col:
        sub = df.loc[nonrev]
        ye = pd.to_numeric(sub[years_elapsed_col], errors="coerce")
        if years_in_months:
            ye = ye / 12.0
        tm = pd.to_numeric(sub[term_col], errors="coerce")
        if term_in_months:
            tm = tm / 12.0
        sched = compute_ead_schedule(
            pd.to_numeric(sub[loan_amount_col], errors="coerce"),
            pd.to_numeric(sub[interest_rate_col], errors="coerce"),
            ye, tm, payment_frequency=payment_frequency,
        )
        ead.loc[nonrev] = sched["ead"].values

    return ead.rename("ead")


def auto_feature_cols(df: pd.DataFrame, exclude=None) -> List[str]:
    """Auto-select predictor columns for the CCF model (numeric + low-card categoricals)."""
    return L.auto_feature_cols(df, exclude=exclude)
