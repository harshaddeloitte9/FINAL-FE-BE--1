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
    default = (rng.uniform(0, 1, n_samples) < prob_default).astype(int)

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
        "default": default,
    })

    # Inject missing values — keep as float so NaN doesn't collapse numeric columns to {0,1}
    for col, frac in [("credit_score", 0.03), ("debt_to_income_ratio", 0.05),
                       ("employment_years", 0.04), ("education_level", 0.06)]:
        mask = rng.choice([True, False], size=n_samples, p=[frac, 1 - frac])
        df[col] = df[col].astype(object)          # allow NaN in int cols
        df.loc[mask, col] = np.nan

    return df


# ─────────────────────────────────────────────
# Column Type Detector  (FIX: stricter boolean detection)
# ─────────────────────────────────────────────

def detect_column_types(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Intelligently detect column types from a dataframe."""
    numeric_cols, categorical_cols, datetime_cols, boolean_cols, id_cols = [], [], [], [], []

    BOOL_KEYWORDS = {"flag", "is_", "has_", "bool", "indicator"}

    for col in df.columns:
        series = df[col].dropna()
        dtype = df[col].dtype

        # ── Strict boolean detection ──
        # Only treat as boolean if:
        #   (a) actual bool dtype, OR
        #   (b) column name contains a bool keyword AND has exactly {0,1} unique values, OR
        #   (c) string-only yes/no/true/false column
        col_lower = col.lower()
        is_bool_name = any(kw in col_lower for kw in BOOL_KEYWORDS)
        unique_vals = set(series.unique())

        if dtype == bool:
            boolean_cols.append(col)
            continue

        if dtype == object and unique_vals.issubset({"yes", "no", "Yes", "No", "true", "false", "True", "False"}):
            boolean_cols.append(col)
            continue

        if (pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_float_dtype(dtype)):
            # Only call it boolean if name screams "flag/indicator" AND has only 0/1
            if is_bool_name and unique_vals.issubset({0, 1, 0.0, 1.0}):
                boolean_cols.append(col)
                continue
            # Otherwise fall through to numeric

        # ── Datetime ──
        if pd.api.types.is_datetime64_any_dtype(dtype):
            datetime_cols.append(col)
            continue

        if dtype == object and series.shape[0] > 0:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    parsed = pd.to_datetime(series.head(50), errors="coerce")
                if parsed.notna().mean() > 0.8:
                    datetime_cols.append(col)
                    continue
            except Exception:
                pass

        # ── Numeric ──
        if pd.api.types.is_numeric_dtype(dtype):
            col_is_id = col.lower() in {"id", "customer_id", "loan_id", "index", "row_id"}
            if col_is_id and series.nunique() > 0.9 * len(series):
                id_cols.append(col)
            else:
                numeric_cols.append(col)
            continue

        # ── Object dtype that is secretly numeric (int col with NaN -> cast to object) ──
        if dtype == object and len(series) > 0:
            numeric_attempt = pd.to_numeric(series, errors="coerce")
            if numeric_attempt.notna().mean() > 0.85:
                col_is_id = col.lower() in {"id", "customer_id", "loan_id", "index", "row_id"}
                if col_is_id and series.nunique() > 0.9 * len(series):
                    id_cols.append(col)
                else:
                    numeric_cols.append(col)
                continue

        # ── Categorical / object ──
        if dtype == object:
            if series.nunique() > 0.9 * len(series) and series.nunique() > 50:
                id_cols.append(col)
            else:
                categorical_cols.append(col)
            continue

    return {
        "numeric": numeric_cols,
        "categorical": categorical_cols,
        "datetime": datetime_cols,
        "boolean": boolean_cols,
        "id": id_cols,
    }


def detect_target_candidates(df: pd.DataFrame) -> List[str]:
    keywords = [
        # Default/credit risk
        "default", "defaulted", "is_default", "def_flag",
        "bad", "is_bad", "bad_flag",
        "target", "label", "y",
        # Mortgage/secured
        "arrears", "in_arrears", "npl", "non_performing",
        "mortgage_default", "charge_off", "charged_off",
        "write_off", "written_off", "forbearance",
        # Generic ML
        "outcome", "event", "flag", "indicator",
        "churn", "fraud", "risk",
        # DPD-based
        "dpd_flag", "dpd90", "dpd_90", "ever_90",
    ]

    candidates = []
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in keywords):
            candidates.append(col)

    # Fallback: if no keyword match, look for binary (0/1) columns that aren't IDs
    if not candidates:
        for col in reversed(df.columns.tolist()):
            if "id" in col.lower():
                continue
            col_vals = df[col].dropna().unique()
            if set(col_vals).issubset({0, 1, 0.0, 1.0}) and len(col_vals) == 2:
                candidates.append(col)

    return candidates


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

    # 2 unique values → always binary, regardless of dtype (covers int64 0/1 and float 0.0/1.0)
    if nunique == 2:
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
