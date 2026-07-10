"""
utils.py - Shared utility functions for the Credit Risk ML POC
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import List, Dict, Tuple, Any
import io
import joblib
import itertools


_download_key_counter = itertools.count()


# ─────────────────────────────────────────────
# Synthetic Dataset Generator
# ─────────────────────────────────────────────

def generate_synthetic_credit_dataset(n_samples: int = 2000, random_state: int = 42) -> pd.DataFrame:
    """Generate a realistic synthetic credit risk dataset."""
    rng = np.random.RandomState(random_state)

    ages = rng.randint(20, 70, n_samples)
    incomes = np.round(rng.lognormal(mean=10.5, sigma=0.6, size=n_samples), 2)
    employment_years = np.clip(rng.normal(loc=8, scale=5, size=n_samples), 0, 40).astype(int)
    loan_amounts = np.round(rng.lognormal(mean=9.5, sigma=0.7, size=n_samples), 2)
    credit_scores = np.clip(rng.normal(loc=650, scale=80, size=n_samples), 300, 850).astype(int)
    num_credit_lines = rng.randint(1, 15, n_samples)
    debt_to_income = np.round(np.clip(rng.normal(loc=0.35, scale=0.15, size=n_samples), 0.01, 1.2), 4)
    loan_to_income = np.round(loan_amounts / incomes, 4)
    num_late_payments = rng.poisson(lam=1.2, size=n_samples)
    num_inquiries = rng.poisson(lam=2.0, size=n_samples)
    months_employed = employment_years * 12 + rng.randint(0, 12, n_samples)
    has_mortgage = rng.choice([0, 1], size=n_samples, p=[0.4, 0.6])
    has_dependents = rng.choice([0, 1], size=n_samples, p=[0.5, 0.5])

    education_levels = rng.choice(
        ["High School", "Bachelor's", "Master's", "PhD", "None"],
        size=n_samples, p=[0.3, 0.4, 0.2, 0.05, 0.05]
    )
    loan_purposes = rng.choice(
        ["Home Improvement", "Debt Consolidation", "Auto", "Medical", "Education", "Business"],
        size=n_samples, p=[0.2, 0.3, 0.15, 0.1, 0.15, 0.1]
    )
    employment_types = rng.choice(
        ["Salaried", "Self-Employed", "Freelancer", "Unemployed"],
        size=n_samples, p=[0.55, 0.25, 0.15, 0.05]
    )

    start_date = pd.Timestamp("2020-01-01")
    application_dates = pd.to_datetime(
        rng.randint(0, (pd.Timestamp("2024-01-01") - start_date).days, n_samples),
        unit="D", origin=start_date
    )

    log_odds = (
        -4.0
        + 0.01 * (750 - credit_scores)
        + 0.8 * debt_to_income
        + 0.5 * loan_to_income
        + 0.15 * num_late_payments
        + 0.08 * num_inquiries
        - 0.003 * incomes / 1000
        - 0.02 * employment_years
        + 0.3 * (employment_types == "Unemployed").astype(int)
    )
    prob_default = 1 / (1 + np.exp(-log_odds))
    # NOTE: "default" is the PD/LGD/EAD/CCF target column. It must never contain
    # NaN/empty values — every downstream engine (PD, LGD filter_defaulted_by_target,
    # CCF training mask) relies on a clean 0/1 flag for every row. It is generated
    # as a plain int array and is deliberately excluded from the missing-value
    # injection loop below.
    default = (rng.uniform(0, 1, n_samples) < prob_default).astype(int)
    is_default = default.astype(bool)

    # ── Product mix (drives which EAD regime — revolving CCF vs amortising — applies) ──
    PRODUCT_TYPES = ["Credit Card", "Overdraft", "Line of Credit",
                      "Mortgage", "Auto Loan", "Personal Loan", "Term Loan"]
    PRODUCT_PROBS = [0.15, 0.08, 0.07, 0.25, 0.20, 0.15, 0.10]
    REVOLVING_TYPES = {"Credit Card", "Overdraft", "Line of Credit"}
    product_types = rng.choice(PRODUCT_TYPES, size=n_samples, p=PRODUCT_PROBS)
    is_revolving = np.isin(product_types, list(REVOLVING_TYPES))

    # ── Revolving-account fields (ead_engine: product_type / drawn_balance / credit_limit / ead_at_default) ──
    credit_limit = np.full(n_samples, np.nan)
    drawn_balance = np.full(n_samples, np.nan)
    limit_factor = rng.uniform(1.5, 4.0, n_samples)
    utilisation = np.clip(rng.normal(0.5, 0.22, n_samples), 0.05, 0.98)
    credit_limit[is_revolving] = (loan_amounts * limit_factor)[is_revolving]
    drawn_balance[is_revolving] = (credit_limit * utilisation)[is_revolving]

    # ── Term / amortisation fields (ead_engine non-revolving regime, via ecl_engine schedule) ──
    TERM_YEARS = {"Mortgage": (15, 30), "Auto Loan": (3, 7),
                  "Personal Loan": (1, 5), "Term Loan": (1, 10)}
    loan_term_years = np.full(n_samples, np.nan)
    for ptype, (lo, hi) in TERM_YEARS.items():
        m = product_types == ptype
        loan_term_years[m] = rng.uniform(lo, hi, m.sum())

    interest_rate = np.clip(
        0.06 + 0.0006 * (750 - credit_scores) + rng.normal(0, 0.01, n_samples),
        0.015, 0.35,
    )

    # ── Origination / seasoning fields (shared by LGD macro alignment + EAD amortisation) ──
    origination_dates = pd.Series(application_dates)
    AS_OF = pd.Timestamp("2024-06-01")
    years_elapsed = ((AS_OF - origination_dates).dt.days / 365.25).clip(lower=0.05).to_numpy()
    # Non-revolving loans can't be "elapsed" past their own term (already matured / paid off)
    nonrev_term = np.where(np.isnan(loan_term_years), np.inf, loan_term_years)
    years_elapsed = np.minimum(years_elapsed, np.where(is_revolving, years_elapsed, nonrev_term * 0.95))

    # ── LGD fields (lgd_engine: recovery_rate / ltv / default_date), realized only
    # for actually-defaulted accounts — this is the realistic shape of the data
    # (a bank genuinely has no recovery rate, default date, or EAD-at-default for
    # a loan that hasn't defaulted). This is safe from PD target leakage because
    # preprocessing.finalize_xy/prepare_data and feature_engineering.
    # apply_feature_engineering explicitly drop these post-default-only columns
    # (by name pattern) from the PD feature matrix before any model ever sees
    # them — see _POST_DEFAULT_ONLY_SIGNATURES in preprocessing.py. LGD/EAD
    # training is unaffected: it selects these columns explicitly by name
    # (lgd_engine.detect_lgd_target, ead_engine.detect_ccf_columns) and filters
    # to the defaulted population using the real `default` flag directly
    # (filter_defaulted_by_target, `rev_mask & yb`), never via NaN-presence.
    default_date = pd.Series(pd.NaT, index=range(n_samples))
    default_offset_days = (rng.uniform(0.1, 1.0, n_samples) * (years_elapsed * 365.25)).astype(int)
    _default_dates = origination_dates + pd.to_timedelta(default_offset_days, unit="D")
    default_date[is_default] = _default_dates[is_default]

    SECURED_TYPES = {"Mortgage", "Auto Loan", "Term Loan"}
    is_secured = np.isin(product_types, list(SECURED_TYPES))
    recovery_rate = np.full(n_samples, np.nan)
    secured_rr = np.clip(rng.normal(0.60, 0.18, n_samples), 0.0, 1.0)
    unsecured_rr = np.clip(rng.normal(0.30, 0.15, n_samples), 0.0, 1.0)
    recovery_rate[is_default & is_secured] = secured_rr[is_default & is_secured]
    recovery_rate[is_default & ~is_secured] = unsecured_rr[is_default & ~is_secured]

    ltv = np.full(n_samples, np.nan)
    is_mortgage = product_types == "Mortgage"
    ltv[is_mortgage] = np.clip(rng.normal(0.75, 0.12, n_samples), 0.30, 0.98)[is_mortgage]

    # ── EAD-at-default (CCF training target), realized only for defaulted revolving accounts ──
    ead_at_default = np.full(n_samples, np.nan)
    ccf_true = np.clip(rng.beta(2, 3, n_samples), 0.0, 1.0)
    undrawn = np.clip(np.nan_to_num(credit_limit) - np.nan_to_num(drawn_balance), 0, None)
    mask_def_rev = is_default & is_revolving
    ead_at_default[mask_def_rev] = (
        np.nan_to_num(drawn_balance) + ccf_true * undrawn
    )[mask_def_rev]

    df = pd.DataFrame({
        "customer_id": [f"CUST_{i:05d}" for i in range(n_samples)],
        "age": ages,
        "annual_income": incomes,
        "employment_years": employment_years,
        "months_employed": months_employed,
        "loan_amount": loan_amounts,
        "credit_score": credit_scores,
        "num_credit_lines": num_credit_lines,
        "debt_to_income_ratio": debt_to_income,
        "loan_to_income_ratio": loan_to_income,
        "num_late_payments": num_late_payments,
        "num_credit_inquiries": num_inquiries,
        "has_mortgage": has_mortgage,
        "has_dependents": has_dependents,
        "education_level": education_levels,
        "loan_purpose": loan_purposes,
        "employment_type": employment_types,
        "application_date": application_dates,
        # ── EAD (ead_engine.py) ──
        "product_type": product_types,
        "credit_limit": credit_limit,
        "drawn_balance": drawn_balance,
        "ead_at_default": ead_at_default,
        "interest_rate": interest_rate,
        "loan_term_years": loan_term_years,
        "years_elapsed": years_elapsed,
        # ── LGD (lgd_engine.py) ──
        "origination_date": origination_dates,
        "default_date": default_date,
        "ltv": ltv,
        "recovery_rate": recovery_rate,
        # ── PD target — required, never NaN ──
        "default": default,
    })

    # Inject missing values — keep as float so NaN doesn't collapse numeric columns to {0,1}
    # "default" (the target) is intentionally NEVER included here.
    for col, frac in [("credit_score", 0.03), ("debt_to_income_ratio", 0.05),
                       ("employment_years", 0.04), ("education_level", 0.06)]:
        mask = rng.choice([True, False], size=n_samples, p=[frac, 1 - frac])
        df[col] = df[col].astype(object)          # allow NaN in int cols
        df.loc[mask, col] = np.nan

    # Safety net: guarantee the target column is fully populated, however the
    # dataset is assembled or extended above.
    assert df["default"].isna().sum() == 0, "Synthetic 'default' target must not contain NaN values."
    df["default"] = df["default"].astype(int)

    return df


# ─────────────────────────────────────────────
# Column Type Detector  (FIX: stricter boolean detection)
# ─────────────────────────────────────────────

def detect_column_types(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Intelligently detect column types from a dataframe."""
    import re as _re
    numeric_cols, categorical_cols, datetime_cols, boolean_cols, id_cols = [], [], [], [], []

    BOOL_KEYWORDS = {"flag", "is_", "has_", "bool", "indicator"}

    _ID_PATTERNS = [
        r"^id$",
        r"_id$",
        r"^id_",
        r"^customer_id",
        r"^loan_id",
        r"^account_id",
        r"^borrower_id",
        r"^facility_id",
        r"^application_id",
        r"^policy_id",
        r"^member_id",
        r"^ref_",
        r"^reference",
        r"^cust_",
        r"^acct_",
    ]

    def _is_id_name(col_name: str) -> bool:
        cl = col_name.lower()
        return any(_re.search(pat, cl) for pat in _ID_PATTERNS)

    for col in df.columns:
        series = df[col].dropna()
        dtype = df[col].dtype
        # pandas 3 uses a native 'str' StringDtype instead of object for string
        # columns — normalise so all remaining checks work on both old and new.
        _is_str = pd.api.types.is_object_dtype(dtype) or str(dtype) in ("str", "string")

        # ── Strict boolean detection ──
        col_lower = col.lower()
        is_bool_name = any(kw in col_lower for kw in BOOL_KEYWORDS)
        unique_vals = set(series.unique())

        if dtype == bool:
            boolean_cols.append(col)
            continue

        if _is_str and unique_vals.issubset({"yes", "no", "Yes", "No", "true", "false", "True", "False"}):
            boolean_cols.append(col)
            continue

        if (pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_float_dtype(dtype)):
            if is_bool_name and unique_vals.issubset({0, 1, 0.0, 1.0}):
                boolean_cols.append(col)
                continue

        # ── Datetime (native dtype) ──
        if pd.api.types.is_datetime64_any_dtype(dtype):
            datetime_cols.append(col)
            continue

        # ── String/object dtype: unified numeric-first block ──
        # Numeric MUST be tested before datetime: bare numbers (credit scores,
        # ratios, years) all parse as valid timestamps under pd.to_datetime
        # (interpreted as nanoseconds), so checking datetime first misclassifies
        # them.  We only attempt datetime after the numeric test fails, and only
        # when the raw strings actually contain date-like separators (-, /, :).
        if _is_str and len(series) > 0:
            _num = pd.to_numeric(series, errors="coerce")
            if _num.notna().mean() >= 0.95:
                if _is_id_name(col) and series.nunique() > 0.9 * len(series):
                    id_cols.append(col)
                else:
                    numeric_cols.append(col)
                continue

            # Datetime check: only when values fail numeric AND contain separators.
            # Bare integers/floats must never reach this branch.
            _sample_str = series.head(200).astype(str)
            _has_date_sep = _sample_str.str.contains(r'[\-/:]', regex=True).mean() >= 0.8
            if _has_date_sep:
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        # Try both dayfirst=False (US: MM/DD/YYYY) and dayfirst=True
                        # (EU: DD/MM/YYYY); take whichever parse rate is higher so
                        # formats like 30/01/2020 aren't rejected.
                        _p_us  = pd.to_datetime(_sample_str, errors="coerce", dayfirst=False)
                        _p_eu  = pd.to_datetime(_sample_str, errors="coerce", dayfirst=True)
                        _parsed = _p_us if _p_us.notna().mean() >= _p_eu.notna().mean() else _p_eu
                    if _parsed.notna().mean() >= 0.95:
                        datetime_cols.append(col)
                        continue
                except Exception:
                    pass

        # ── Numeric (native numeric dtype) ──
        if pd.api.types.is_numeric_dtype(dtype):
            if _is_id_name(col) and series.nunique() > 0.9 * len(series):
                id_cols.append(col)
            else:
                numeric_cols.append(col)
            continue

        # ── Categorical / string ──
        if _is_str:
            if series.nunique() > 0.9 * len(series) and series.nunique() > 50:
                id_cols.append(col)
            else:
                categorical_cols.append(col)
            continue

    # Secondary check: string/object columns with >95% unique values are likely IDs.
    # Skip anything already assigned to a definite type (datetime, numeric, boolean).
    _already_typed = set(datetime_cols) | set(numeric_cols) | set(boolean_cols)
    for c in df.columns:
        if c in id_cols or c in _already_typed:
            continue
        if pd.api.types.is_object_dtype(df[c]) or str(df[c].dtype) in ("str", "string"):
            n_total = len(df[c].dropna())
            if n_total > 0:
                n_unique = df[c].nunique()
                if n_unique / n_total > 0.95:
                    id_cols.append(c)
                    # Remove from categorical if already classified there
                    if c in categorical_cols:
                        categorical_cols.remove(c)

    return {
        "numeric": numeric_cols,
        "categorical": categorical_cols,
        "datetime": datetime_cols,
        "boolean": boolean_cols,
        "id": id_cols,
    }


# Normalized names that are unambiguous PD target identifiers.
# Exact match only — no substring — so "ead_at_default" normalises to
# "eadatdefault" which is NOT in this set, while "default" IS.
_EXACT_TARGET_NORM_NAMES = {
    "default", "defaulted", "isdefault", "defflag", "deflag",
    "bad", "isbad", "badflag",
    "target", "label", "y",
    "arrears", "npl", "chargedoff", "chargeoff",
    "writeoff", "writtenoff", "nonperforming",
    "churn", "fraud", "outcome",
    "dpdflg", "dpdflag", "dpd90", "dpd90flag", "ever90",
    "forbearance",
}


def _norm_col(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _is_binary_series(series: pd.Series) -> bool:
    """True if series has exactly 2 distinct non-null values."""
    try:
        return series.dropna().nunique() == 2
    except Exception:
        return False


def _binary_pos_rate(series: pd.Series) -> float:
    """Positive rate for a numeric 0/1 series; -1 if not 0/1."""
    try:
        vals = pd.to_numeric(series, errors="coerce").dropna()
        if set(vals.unique()).issubset({0, 1, 0.0, 1.0}):
            return float(vals.mean())
    except Exception:
        pass
    return -1.0


def detect_target_candidates(df: pd.DataFrame) -> List[str]:
    """
    Score-ranked list of candidate target columns, most likely first.

    Tier A — exact normalized name in _EXACT_TARGET_NORM_NAMES AND binary column.
              Substring / starts-with / ends-with matching deliberately avoided
              so 'ead_at_default' (normalised: 'eadatdefault') never wins over
              'default' (normalised: 'default').

    Tier B — binary 0/1 column with positive rate 1%–50% (plausible default
              rate), not in leakage lists.  Tiebreak: names containing
              'default' or 'bad' rank first.

    Tier C — empty list (no auto-selection).

    Leakage columns (post-default, ECL-only, DPD, origination-PD) are excluded
    from all tiers; ID and datetime columns are also skipped.
    """
    import re

    # Lazy import to avoid circular dependency (preprocessing imports utils).
    try:
        from preprocessing import _find_ecl_only_cols, _find_post_default_only_cols
        _leakage = set(_find_ecl_only_cols(df.columns)) | set(_find_post_default_only_cols(df.columns))
    except Exception:
        _leakage = set()

    col_types_hint = {}
    try:
        col_types_hint = detect_column_types(df)
    except Exception:
        pass
    _id_cols = set(col_types_hint.get("id", []))
    _dt_cols = set(col_types_hint.get("datetime", []))
    _excluded = _leakage | _id_cols | _dt_cols

    # Tier A: exact normalized name match + binary column
    tier_a = []
    for col in df.columns:
        if col in _excluded:
            continue
        if _norm_col(col) in _EXACT_TARGET_NORM_NAMES and _is_binary_series(df[col]):
            tier_a.append(col)
    if tier_a:
        return tier_a

    # Tier B: binary 0/1 with 1%–50% positive rate
    tier_b = []
    for col in df.columns:
        if col in _excluded:
            continue
        rate = _binary_pos_rate(df[col])
        if 0.01 <= rate <= 0.50:
            tier_b.append(col)
    if tier_b:
        def _tiebreak(col):
            n = col.lower()
            return 0 if ("default" in n or "bad" in n) else 1
        tier_b.sort(key=_tiebreak)
        return tier_b

    return []  # Tier C: no auto-selection


def bin_continuous_target(
    series: pd.Series,
    n_bins: int = 5,
    method: str = "quantile",
    custom_edges: list = None,
    labels: list = None,
) -> tuple:
    """
    Convert a continuous target into binned categories.

    Args:
        series: the continuous target column
        n_bins: number of bins (ignored if custom_edges provided)
        method: "quantile" (equal frequency) or "equal_width"
        custom_edges: optional list of bin edges, e.g. [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        labels: optional list of bin labels, e.g. ["A", "B", "C", "D", "E"]

    Returns:
        (binned_series, bin_edges_used, bin_counts_dict)
    """
    clean = series.dropna()

    if custom_edges:
        edges = custom_edges
    elif method == "quantile":
        edges = list(pd.qcut(clean, q=n_bins, retbins=True, duplicates="drop")[1])
    else:  # equal_width
        edges = list(pd.cut(clean, bins=n_bins, retbins=True)[1])

    if labels is None:
        labels = [f"Band_{i+1}" for i in range(len(edges) - 1)]

    binned = pd.cut(series, bins=edges, labels=labels, include_lowest=True)
    bin_counts = binned.value_counts().sort_index().to_dict()

    return binned, edges, bin_counts


def detect_task_type(series: pd.Series) -> str:
    clean = series.dropna()
    if clean.empty:
        return "regression"

    nunique = clean.nunique()

    # Binary classification is the default for 2-class targets. If the series
    # is binary-like but only contains one observed class in the split, preserve
    # binary semantics so evaluation can still run on the holdout slice.
    if nunique <= 2 and set(clean.astype(int).unique()).issubset({0, 1}):
        return "binary"

    # Low-cardinality columns → multiclass only when values are integer-like;
    # prevents float probability columns (e.g. 8 unique decimals) from being
    # misclassified as multiclass instead of regression.
    if nunique <= 10:
        is_int_like = pd.api.types.is_integer_dtype(clean) or (
            pd.api.types.is_float_dtype(clean)
            and bool((clean == clean.round(0)).all())
        )
        if is_int_like:
            return "multiclass"

    return "regression"


# ─────────────────────────────────────────────
# Download Helpers
# ─────────────────────────────────────────────

def df_to_csv_download(df: pd.DataFrame, filename: str = "data.csv") -> None:
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"⬇️ Download {filename}",
        data=csv,
        file_name=filename,
        mime="text/csv",
        key=f"csv_download_{filename}_{next(_download_key_counter)}",
    )


def model_to_download(model: Any, filename: str = "model.pkl") -> None:
    buf = io.BytesIO()
    joblib.dump(model, buf)
    buf.seek(0)
    st.download_button(
        label="⬇️ Download Trained Model (.pkl)",
        data=buf,
        file_name=filename,
        mime="application/octet-stream",
        key=f"model_download_{filename}_{next(_download_key_counter)}",
    )


def format_large_number(n: float) -> str:
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(round(n, 2))


def info_box(title: str, content: str, icon: str = "ℹ️") -> None:
    st.info(f"**{icon} {title}**\n\n{content}")
