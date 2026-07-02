"""
app.py - Credit Risk ML POC — Adaptive Machine Learning Platform
Run with: streamlit run app.py
"""

import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import warnings
import io
import time
from typing import Dict, Any

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# Page Config (must be first Streamlit call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="CreditRisk ML POC",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #1e293b !important; }
    section[data-testid="stSidebar"] .stMarkdown { color: #e2e8f0; }

    /* Cards */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .metric-card h2 { margin: 0; font-size: 2rem; color: #6366f1; }
    .metric-card p { margin: 0; color: #94a3b8; font-size: 0.85rem; }

    /* Step header */
    .step-header {
        background: linear-gradient(135deg, #1e293b, #2d3748);
        border-left: 4px solid #6366f1;
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1.2rem;
        margin-bottom: 1rem;
    }
    .step-header h3 { margin: 0; color: #e2e8f0; }
    .step-header p { margin: 0; color: #94a3b8; font-size: 0.85rem; }

    /* Info panels */
    .insight-box {
        background: #1e293b;
        border: 1px solid #6366f1;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; background: transparent; }
    .stTabs [data-baseweb="tab"] {
        background: #1e293b;
        color: #94a3b8;
        border-radius: 6px 6px 0 0;
        border: 1px solid #334155;
        padding: 0.4rem 1rem;
    }
    .stTabs [aria-selected="true"] { background: #6366f1 !important; color: white !important; }

    /* Progress */
    .stProgress .st-bo { background: #6366f1; }

    /* Buttons */
    .stButton button {
        background: #6366f1;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
    }
    .stButton button:hover { background: #4f46e5; }

    /* Expander */
    .streamlit-expanderHeader { background: #1e293b !important; color: #e2e8f0 !important; }
    .streamlit-expanderContent { background: #0f172a !important; }

    /* DataFrame */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Select boxes */
    .stSelectbox label, .stMultiSelect label, .stSlider label { color: #94a3b8 !important; }

    /* Metric */
    [data-testid="stMetricValue"] { color: #6366f1 !important; font-size: 1.8rem !important; }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Imports from modules
# ─────────────────────────────────────────────
from utils import (
    generate_synthetic_credit_dataset, detect_column_types,
    detect_target_candidates, detect_task_type,
    df_to_csv_download, model_to_download,
)
from preprocessing import (
    build_preprocessing_report, prepare_data, rebuild_preprocessor_for,
    finalize_xy,
)
from feature_engineering import (
    analyze_for_feature_engineering, apply_feature_engineering,
    compute_univariate_gini,
    detect_outstanding_balance_col, detect_loan_amount_col,
    detect_interest_rate_col, detect_years_elapsed_col, detect_term_col,
    detect_payment_frequency_col,
    compute_outstanding_balance, compute_ead_schedule, compute_ead,
    PAYMENT_FREQUENCIES, DEFAULT_PAYMENT_FREQUENCY,
)
from model_selector import (
    recommend_models, CLASSIFICATION_MODELS, REGRESSION_MODELS
)
from train import split_data, compute_split_stats, train_model
import ecl_engine as ecl
import lgd_ui
import ead_ui
from evaluate import (    compute_binary_metrics, compute_regression_metrics,
    compute_heteroscedasticity_check,
    plot_roc_curve, plot_pr_curve, plot_confusion_matrix,
    plot_score_distribution, plot_threshold_analysis, plot_lift_chart,
    plot_actual_vs_predicted_over_time, compute_temporal_stability_summary
)
from explainability import (
    extract_feature_importance, compute_shap_values,
    plot_feature_importance_bar, plot_shap_summary_plotly,
    plot_shap_waterfall_single, generate_prediction_reasoning,
    generate_model_summary
)
from val_replication import render_val_replication, parse_mdd_file, extract_metrics_from_mdd

try:
    from agent2 import Agent2 as _Agent2
    _AGENT2_AVAILABLE = True
except Exception:
    _AGENT2_AVAILABLE = False


# ─────────────────────────────────────────────
# Demo Data Constants (Validation Workspace)
# ─────────────────────────────────────────────
DEMO_INTAKE_CLEAN = {
    "model_name": "PD_XGBoost_RetailCredit_v2",
    "model_owner": "Sarah Chen",
    "owning_team": "Retail Credit Risk",
    "lead_validator": "Reeyaz Miglani",
    "model_type": "PD (Probability of Default)",
    "model_version": "v2.1.0",
    "model_tier": "Tier 2 — Medium Risk",
    "model_purpose": (
        "This model estimates the probability of default for unsecured "
        "retail credit customers. Used for IFRS 9 ECL staging, credit "
        "decisioning, and risk appetite reporting. Scope: personal loan "
        "portfolio only. Out of scope: mortgages, business lending."
    ),
    "mdd_text": """
        Purpose and Intended Use: This model estimates probability of
        default for retail unsecured loans. Scope is limited to personal
        loan portfolio.
        Methodology: XGBoost algorithm selected after comparison with
        logistic regression baseline. SMOTE oversampling applied for
        class imbalance combined with class weighting. Hyperparameter
        tuning via RandomizedSearchCV. Calibrated via Platt scaling
        through the cycle TTC calibration.
        Data: Internal dataset January 2015 to December 2023, 5000
        observations covering COVID-19 stress period. Default definition
        90 days past due per IFRS 9 B5.5.28 and CRR Article 178.
        Stratified random sample across origination vintages. Survivorship
        bias addressed by retaining closed and charged-off accounts.
        No time-period bias identified. Selection bias reviewed.
        Feature transformations: log transform of loan_amount, quantile
        binning of credit_score, WOE weight of evidence encoding,
        standard scaling. All transformations documented in Appendix B.
        Forward-looking macro scenarios: baseline 50 percent, upside
        25 percent, downside 25 percent defined over GDP growth and
        unemployment rate. Probability-weighted ECL.
        Features: credit_score, debt_to_income_ratio, loan_amount,
        employment_length, num_credit_lines, gdp_growth,
        unemployment_rate. Variable selection via information value
        IV greater than 0.02.
        Assumptions: LGD fixed at 45 percent Basel II floor. TTC
        calibration applied. No post-default information used as
        predictor. All predictors observable at origination.
        Limitations: POC dataset. Macro scenario weights are
        illustrative.
        Performance: AUC 0.82, Recall 0.71, Gini 0.64, Brier Score 0.16.
        Governance: SMF holder Jane Smith. Model inventory registered.
        Independence confirmed — validation team had no involvement in
        model development. Version history maintained from v1.0.
        Governance approved by Model Risk Committee MRC June 2026.
        Operating boundaries: score range 0 to 1. Input domain:
        retail unsecured loans UK only. Extrapolation risk documented.
        Bias and fairness evaluation performed. No material
        discriminatory bias identified across age and employment groups.
        Version v2.1.0 change log maintained.
    """,
    "stated_auc": 0.82,
    "stated_recall": 0.71,
    "stated_gini": 0.64,
    "stated_brier": 0.16,
    "target_col": "default",
    "algorithm": "XGBoost",
    "default_definition": "90 days past due (IFRS 9 / CRR Art.178)",
    "calibration_method": "Platt scaling (TTC)",
    "macro_variables_mentioned": True,
    "model_inventory_registered": True,
    "independence_confirmed": True,
}

DEMO_INTAKE_FLAWED = {
    "model_name": "PD_Model_Internal_v1",
    "model_owner": "Unknown",
    "owning_team": "Risk",
    "lead_validator": "Reeyaz Miglani",
    "model_type": "PD (Probability of Default)",
    "model_version": "v1.0",
    "model_tier": "Tier 1 — High Risk",
    "model_purpose": "Credit risk model.",
    "mdd_text": """
        Model Note: We trained an XGBoost classifier on a historical
        loan dataset of roughly 10000 accounts. The target is the
        internal default indicator. Predictors include credit score,
        income ratios, recovery amounts and other account fields.
        The model reached an AUC of about 0.78 on a hold-out sample.
        Defaults are flagged by the collections team based on internal
        judgement. Standard data cleaning was performed before training.
        Further details are available on request.
    """,
    "stated_auc": 0.78,
    "stated_recall": 0.72,
    "stated_gini": 0.56,
    "stated_brier": None,
    "target_col": "default",
    "algorithm": "XGBoost",
    "default_definition": "Internal collections judgement",
    "calibration_method": "Not specified",
    "macro_variables_mentioned": False,
    "model_inventory_registered": False,
    "independence_confirmed": True,
}

DEMO_DATA_DIR = os.path.join(os.path.dirname(__file__), "demo_data")


# ─────────────────────────────────────────────
# Session State Initializer
# ─────────────────────────────────────────────
def init_session():
    defaults = {
        "df": None,
        "col_types": None,
        "target_col": None,
        "task_type": None,
        "X": None,
        "y": None,
        "preprocessor": None,
        "prep_report": None,
        "feature_names": None,
        "X_engineered": None,
        "fe_plan": None,
        "fe_summary": None,
        "X_train": None, "X_val": None, "X_test": None,
        "y_train": None, "y_val": None, "y_test": None,
        # LEAKAGE FIX: engineered splits are stored separately; FE is learned on
        # X_train only and applied to all three.
        "X_train_engineered": None,
        "X_val_engineered": None,
        "X_test_engineered": None,
        # Split is now decided in Step 3 (before feature engineering).
        "split_test_size": 0.15,
        "split_val_size": 0.15,
        "split_seed": 42,
        "split_stats": None,
        "trained_pipeline": None,
        "model_comparison_results": None,
        "model_comparison_pipelines": None,
        "final_model_name": None,
        "training_info": None,
        "eval_metrics": None,
        "y_proba_test": None,
        "heteroscedasticity_check": None,
        "importance_df": None,
        "shap_result": None,
        "current_step": 1,
        "data_source": None,
        "agent2": None,
        "agent2_report": {},
        "model_tier": None,
        "leakage_risk_cols": [],
        "date_integrity": {},
        "gini_scores": {},
        "workspace": "landing",
        "val_df": None,
        "val_dv_results": None,
        "val_step": 1,
        "val_demo_mode": None,
        "val_intake_data": {},
        "val_mdd_text": "",
        "val_mdd_reported_metrics": {},
        "_val_mdd_parsed_name": None,
        "val_intake_json": {},
        "val_hyperparams": {},
        "val_agent2_results": None,
        "val_agent2": None,
        "val_s3_results": None,
        "val_demo_df_loaded": False,
        "val_demo_mdd_loaded": False,
        "val_demo_checks": False,
        "val_demo_attestation": False,
        "chk_inventory": False,
        "chk_tier": False,
        "chk_artifacts": False,
        "chk_prev_findings": False,
        "chk_reg_scope": False,
        "chk_independence": False,
        "chk_plan_approved": False,
        "chk_attestation": False,
        "val_benchmark_metrics": None,
        "val_benchmark_proba": None,
        "val_benchmark_name": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


def _full_engineered_X():
    """
    Reassemble the full engineered feature matrix from the train/val/test
    engineered splits (used by ECL portfolio scoring and the processed-dataset
    export). This is leakage-free: the transformations were LEARNED on train and
    merely applied to every row — exactly how a deployed model scores a book.
    """
    parts = [
        st.session_state.get("X_train_engineered"),
        st.session_state.get("X_val_engineered"),
        st.session_state.get("X_test_engineered"),
    ]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    return pd.concat(parts).sort_index()


def _full_engineered_y():
    """Full y aligned to the engineered matrix index (train+val+test)."""
    parts = [
        st.session_state.get("y_train"),
        st.session_state.get("y_val"),
        st.session_state.get("y_test"),
    ]
    parts = [p for p in parts if p is not None]
    if not parts:
        return st.session_state.get("y")
    return pd.concat(parts).sort_index()


# ─────────────────────────────────────────────
# Agent 2 helpers
# ─────────────────────────────────────────────
def _get_agent2():
    """Return the Agent2 singleton from session state, initializing it lazily."""
    if not _AGENT2_AVAILABLE:
        return None
    if st.session_state.get("agent2") is None:
        try:
            st.session_state["agent2"] = _Agent2("rag_store/val_mdd_rules.json")
        except Exception:
            return None
    return st.session_state.get("agent2")


def _get_val_agent2():
    """Return ValidationAgent2 singleton from session state, initializing it lazily."""
    if st.session_state.get("val_agent2") is None:
        try:
            from validation_agent2 import ValidationAgent2 as _VA2
            st.session_state["val_agent2"] = _VA2()
        except Exception:
            return None
    return st.session_state.get("val_agent2")


def _run_agent2_stage(stage_key: str, check_fn, *args, **kwargs) -> list:
    """Cache check_fn result in session_state so it doesn't re-run on every Streamlit rerun."""
    cache_key = f"agent2_flags_{stage_key}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = check_fn(*args, **kwargs)
    return st.session_state[cache_key]


def _render_tier_card(tier_result: dict) -> None:
    """Render the SS1/23 model risk tier card using inline HTML."""
    import html as _html

    tier = tier_result["tier"]
    _C = {
        1: {"border": "#ef4444", "text": "#ef4444", "bg": "#1a0000", "div": "#ef444440"},
        2: {"border": "#f59e0b", "text": "#f59e0b", "bg": "#1a1000", "div": "#f59e0b40"},
        3: {"border": "#10b981", "text": "#10b981", "bg": "#001a0e", "div": "#10b98140"},
    }
    c = _C.get(tier, _C[2])

    tier_label = _html.escape(tier_result["tier_label"])
    score      = tier_result["score"]
    principle  = _html.escape(tier_result["principle"])
    req_icon   = "⚠️" if tier < 3 else "ℹ️"

    reasons_li = "".join(
        f"<li style='color:#64748b;margin-bottom:0.25rem;'>{_html.escape(r)}</li>"
        for r in tier_result["reasons"]
    )
    reqs_li = "".join(
        f"<li style='color:{c['text']};margin-bottom:0.3rem;'>"
        f"{req_icon} {_html.escape(req)}</li>"
        for req in tier_result["requirements"]
    )

    st.markdown(
        f"<div style='background:{c['bg']};border-left:4px solid {c['border']};"
        f"border-radius:0 8px 8px 0;padding:1rem 1.25rem;margin:0.75rem 0;'>"
        f"<div style='color:#94a3b8;font-size:0.78rem;margin-bottom:0.3rem;"
        f"letter-spacing:0.06em;text-transform:uppercase;'>"
        f"🏷️ SS1/23 Model Risk Tier — Principle 1.3</div>"
        f"<div style='color:{c['text']};font-size:1.35rem;font-weight:700;margin-bottom:0.2rem;'>"
        f"{tier_label}</div>"
        f"<div style='color:#94a3b8;font-size:0.85rem;margin-bottom:0.75rem;'>"
        f"Risk Score: {score}</div>"
        f"<hr style='border:0;border-top:1px solid {c['div']};margin:0.5rem 0;'>"
        f"<div style='color:#94a3b8;font-size:0.82rem;margin-bottom:0.4rem;font-weight:600;'>"
        f"📊 Risk Scoring Breakdown:</div>"
        f"<ul style='margin:0 0 0.75rem 1.2rem;padding:0;'>{reasons_li}</ul>"
        f"<hr style='border:0;border-top:1px solid {c['div']};margin:0.5rem 0;'>"
        f"<div style='color:#94a3b8;font-size:0.82rem;margin-bottom:0.4rem;font-weight:600;'>"
        f"Requirements under SS1/23 Principle 1.3:</div>"
        f"<ul style='margin:0 0 0.75rem 1.2rem;padding:0;'>{reqs_li}</ul>"
        f"<div style='color:#475569;font-size:0.72rem;border-top:1px solid {c['div']};"
        f"padding-top:0.5rem;margin-top:0.25rem;'>"
        f"Based on {principle} (PRA, April 2026)</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_compliance_banner(stage_label: str, flags: list) -> None:
    """Render inline compliance flag cards. Never blocks navigation."""
    import html as _html

    if not flags:
        st.success(f"✅ Agent 2: All compliance checks passed for {stage_label}.")
        return

    _SEV_COLOR = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
    _SEV_ICON  = {"high": "🔴",      "medium": "🟡",      "low": "🟢"}
    _SEV_BG    = {"high": "#1c0808", "medium": "#1c1200", "low": "#071a0e"}

    sorted_flags = sorted(
        flags,
        key=lambda f: {"high": 0, "medium": 1, "low": 2}.get(f.get("severity", "low"), 9),
    )

    cards = []
    for flag in sorted_flags:
        sev    = flag.get("severity", "low")
        border = _SEV_COLOR.get(sev, "#6366f1")
        bg     = _SEV_BG.get(sev, "#1e293b")
        icon   = _SEV_ICON.get(sev, "⚪")

        rule_id    = _html.escape(str(flag.get("rule_id", "?")))
        flag_text  = _html.escape(str(flag.get("flag", "")))
        suggestion = _html.escape(str(flag.get("suggestion", "")))
        source     = _html.escape(str(flag.get("source", "?")))
        principle  = _html.escape(str(flag.get("principle", "")))
        ov         = flag.get("observed_value")

        observed_row = ""
        if ov is not None:
            observed_row = (
                f"<div style='color:#94a3b8;font-size:0.78rem;margin-top:0.2rem;'>"
                f"📊 Observed: <code>{_html.escape(str(ov))}</code></div>"
            )

        nv_tag = ""
        if flag.get("not_verifiable"):
            nv_tag = (
                "<span style='color:#64748b;font-size:0.75rem;"
                "font-style:italic;'> · not verifiable with current data</span>"
            )

        cards.append(
            f"<div style='border-left:3px solid {border};padding:0.55rem 1rem;"
            f"margin:0.35rem 0;background:{bg};border-radius:0 6px 6px 0;'>"
            f"<div style='color:#f1f5f9;font-size:0.9rem;font-weight:600;line-height:1.4;'>"
            f"{icon} <span style='color:#94a3b8;'>[{rule_id}]</span> {flag_text}{nv_tag}"
            f"</div>"
            f"{observed_row}"
            f"<div style='color:#94a3b8;font-size:0.82rem;margin-top:0.25rem;line-height:1.4;'>"
            f"💡 {suggestion}"
            f"</div>"
            f"<div style='color:#475569;font-size:0.75rem;margin-top:0.15rem;'>"
            f"📋 {source} — {principle}"
            f"</div>"
            f"</div>"
        )

    st.markdown("".join(cards), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Sidebar Navigation
# ─────────────────────────────────────────────
def render_sidebar():
    workspace = st.session_state.get("workspace", "landing")
    with st.sidebar:
        st.markdown("""
        <div style='text-align:center; padding: 1rem 0;'>
            <span style='font-size:2.5rem'>🏦</span>
            <h2 style='color:#6366f1; margin:0.3rem 0;'>CreditRisk ML</h2>
            <p style='color:#64748b; font-size:0.8rem; margin:0;'>Adaptive POC Platform</p>
        </div>
        """, unsafe_allow_html=True)

        if workspace == "development":
            st.divider()
            if st.button("← Back to Home", use_container_width=True, key="switch_to_landing_dev"):
                st.session_state.workspace = "landing"
                st.rerun()
            st.markdown("### 🧭 Workflow Progress")
            current = st.session_state.current_step
            pd_steps = [
                ("📂 Data Upload",         1),
                ("🔍 Data Profiling",      2),
                ("⚙️ Preprocessing",       3),
                ("🔬 Feature Engineering", 4),
                ("🤖 Model Selection",     5),
                ("🎯 Training",            6),
                ("📊 Evaluation",          7),
                ("💡 Explainability",      8),
            ]
            st.markdown(
                "<div style='color:#6366f1;font-size:0.78rem;font-weight:700;"
                "letter-spacing:0.05em;padding:0.3rem 0;'>🎯 PD MODEL</div>",
                unsafe_allow_html=True,
            )
            for label, step_id in pd_steps:
                if step_id < current:
                    _icon, _color = "✅", "#10b981"
                elif step_id == current:
                    _icon, _color = "▶️", "#6366f1"
                else:
                    _icon, _color = "⏳", "#475569"
                st.markdown(
                    f"<div style='color:{_color};padding:0.1rem 0 0.1rem 0.5rem;font-size:0.88rem;'>{_icon} {label}</div>",
                    unsafe_allow_html=True,
                )

            # LGD sub-steps
            _lgd_bundle = st.session_state.get("lgd_model_bundle")
            _lgd_feats = st.session_state.get("lgd_features")
            _lgd_pred = st.session_state.get("lgd_portfolio_pred")
            _pd_done = st.session_state.get("trained_pipeline") is not None
            _lgd_color = "#94a3b8" if not _pd_done else "#10b981" if _lgd_pred is not None else "#f59e0b"
            st.markdown(
                f"<div style='color:{_lgd_color};font-size:0.78rem;font-weight:700;"
                f"letter-spacing:0.05em;padding:0.4rem 0 0.2rem 0;'>💧 LGD MODEL</div>",
                unsafe_allow_html=True,
            )
            lgd_substeps = [
                ("🔬 Feature Engineering", _lgd_feats is not None),
                ("🎯 Training",            _lgd_bundle is not None),
                ("📊 Evaluation",          _lgd_bundle is not None),
                ("📥 Apply & Report",      _lgd_pred is not None),
            ]
            for _lbl, _done in lgd_substeps:
                if not _pd_done:
                    _li, _lc = "🔒", "#475569"
                elif _done:
                    _li, _lc = "✅", "#10b981"
                else:
                    _li, _lc = "⏳", "#94a3b8"
                st.markdown(
                    f"<div style='color:{_lc};padding:0.1rem 0 0.1rem 1rem;font-size:0.82rem;'>{_li} {_lbl}</div>",
                    unsafe_allow_html=True,
                )

            # EAD sub-steps
            _ccf_bundle = st.session_state.get("ccf_model_bundle")
            _ead_vals = st.session_state.get("ead_values")
            _lgd_done = _lgd_bundle is not None
            _ead_color = "#94a3b8" if not _lgd_done else "#10b981" if _ead_vals is not None else "#f59e0b"
            st.markdown(
                f"<div style='color:{_ead_color};font-size:0.78rem;font-weight:700;"
                f"letter-spacing:0.05em;padding:0.4rem 0 0.2rem 0;'>💳 EAD MODEL</div>",
                unsafe_allow_html=True,
            )
            ead_substeps = [
                ("📋 Product split",           _lgd_done),
                ("🚀 CCF model (revolving)",   _ccf_bundle is not None),
                ("🏦 Amortisation (term loan)", _lgd_done),
                ("💰 Portfolio EAD computed",  _ead_vals is not None),
            ]
            for _lbl, _done in ead_substeps:
                if not _lgd_done:
                    _li, _lc = "🔒", "#475569"
                elif _done:
                    _li, _lc = "✅", "#10b981"
                else:
                    _li, _lc = "⏳", "#94a3b8"
                st.markdown(
                    f"<div style='color:{_lc};padding:0.1rem 0 0.1rem 1rem;font-size:0.82rem;'>{_li} {_lbl}</div>",
                    unsafe_allow_html=True,
                )

            st.divider()
            st.markdown("### ⚙️ Global Settings")
            st.session_state.decision_threshold = st.slider("Decision Threshold (Eval Step)", 0.1, 0.9, 0.5, 0.05)

        elif workspace == "validation":
            st.divider()
            if st.button("← Back to Home", use_container_width=True,
                         key="switch_to_landing_val"):
                st.session_state.workspace = "landing"
                st.rerun()
            st.markdown("### 🔎 Validation Stages")
            val_steps = [
                (1, "📋 Intake & Governance"),
                (2, "📂 Data Validation"),
                (3, "🧠 Conceptual Soundness"),
                (4, "⚙️ Replication"),
                (5, "📊 Performance Testing"),
                (6, "📉 Stress & Backtesting"),
                (7, "⚖️ Regulatory Review"),
                (8, "📄 Findings & Report"),
            ]
            _val_current = st.session_state.get("val_step", 1)
            for _vs_num, _vs_label in val_steps:
                if _vs_num < _val_current:
                    _vs_icon, _vs_color = "✅", "#10b981"
                elif _vs_num == _val_current:
                    _vs_icon, _vs_color = "▶️", "#6366f1"
                else:
                    _vs_icon, _vs_color = "⏳", "#475569"
                st.markdown(
                    f"<div style='color:{_vs_color};padding:0.15rem 0;"
                    f"font-size:0.9rem;'>"
                    f"{_vs_icon} {_vs_label}</div>",
                    unsafe_allow_html=True,
                )

        st.divider()
        if st.button("🔄 Reset Everything", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_session()
            st.rerun()


# ─────────────────────────────────────────────
# STEP 1: Data Upload
# ─────────────────────────────────────────────
def render_upload():
    st.markdown("""
    <div class='step-header'>
        <h3>📂 Step 1 — Data Upload</h3>
        <p>Upload a CSV or Excel file, or use the built-in synthetic credit dataset</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🔌 Data Source")
    data_source_type = st.radio(
        "Select how you want to bring in data",
        [
            "📁 Upload File (CSV/XLSX)",
            "🗄️ Database Connection",
            "🌐 API Endpoint",
            "☁️ Cloud Storage (S3/Azure Blob)",
            "📂 SFTP / File Server",
        ],
        horizontal=False,
        key="data_source_type",
    )

    if data_source_type == "📁 Upload File (CSV/XLSX)":
        col1, col2 = st.columns([2, 1])

        with col1:
            uploaded_file = st.file_uploader(
                "Upload your dataset (CSV / XLSX)",
                type=["csv", "xlsx"],
                help="The system adapts automatically to any structured dataset schema.",
            )

        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            use_synthetic = st.button("🎲 Use Synthetic Dataset", use_container_width=True)
            n_samples = st.number_input("Synthetic samples", min_value=500, max_value=50000, value=2000, step=500)

        if uploaded_file is not None:
            try:
                with st.spinner("Reading file..."):
                    if uploaded_file.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file, engine="openpyxl")
                st.session_state.df = df
                st.session_state.data_source = uploaded_file.name
                st.success(f"✅ Loaded **{uploaded_file.name}** — {df.shape[0]:,} rows × {df.shape[1]} columns")
            except Exception as e:
                st.error(f"Error reading file: {e}")
                return

        elif use_synthetic:
            with st.spinner("Generating synthetic credit dataset..."):
                df = generate_synthetic_credit_dataset(n_samples=int(n_samples))
            st.session_state.df = df
            st.session_state.data_source = "Synthetic Credit Dataset"
            st.success(f"✅ Generated synthetic dataset — {df.shape[0]:,} rows × {df.shape[1]} columns")

    elif data_source_type == "🗄️ Database Connection":
        st.info("🔧 Database connection setup")
        col1, col2 = st.columns(2)
        with col1:
            db_type = st.selectbox("Database type",
                ["PostgreSQL", "SQL Server", "Oracle", "MySQL"])
            db_host = st.text_input("Host", placeholder="e.g. db.internal.deloitte.com")
            db_name = st.text_input("Database name")
        with col2:
            db_port = st.text_input("Port", placeholder="e.g. 5432")
            db_user = st.text_input("Username")
            db_query = st.text_area("SQL Query",
                placeholder="SELECT * FROM credit_portfolio WHERE ...",
                height=100)
        st.warning(
            "🚧 Database connectivity is not yet implemented in this POC. "
            "This UI demonstrates the intended workflow — connection logic "
            "will be added once the target database and credentials are confirmed."
        )
        st.button("Connect & Pull Data", disabled=True, use_container_width=True)

    elif data_source_type == "🌐 API Endpoint":
        st.info("🔧 API connection setup")
        api_url = st.text_input("API Endpoint URL",
            placeholder="https://api.internal.deloitte.com/credit-data")
        api_auth = st.selectbox("Authentication",
            ["None", "API Key", "OAuth 2.0", "Bearer Token"])
        if api_auth != "None":
            st.text_input("Credential", type="password")
        st.warning(
            "🚧 API connectivity is not yet implemented in this POC. "
            "This UI demonstrates the intended workflow."
        )
        st.button("Fetch Data", disabled=True, use_container_width=True)

    elif data_source_type == "☁️ Cloud Storage (S3/Azure Blob)":
        st.info("🔧 Cloud storage connection setup")
        cloud_provider = st.selectbox("Provider", ["AWS S3", "Azure Blob Storage", "Google Cloud Storage"])
        bucket_path = st.text_input("Bucket / Container path",
            placeholder="e.g. s3://credit-risk-data/portfolio/")
        st.warning(
            "🚧 Cloud storage connectivity is not yet implemented in this POC. "
            "This UI demonstrates the intended workflow."
        )
        st.button("Load from Cloud", disabled=True, use_container_width=True)

    elif data_source_type == "📂 SFTP / File Server":
        st.info("🔧 SFTP / File Server connection setup")
        sftp_host = st.text_input("Server host", placeholder="e.g. sftp.internal.deloitte.com")
        sftp_path = st.text_input("File path", placeholder="e.g. /exports/credit_portfolio_latest.csv")
        st.warning(
            "🚧 SFTP connectivity is not yet implemented in this POC. "
            "This UI demonstrates the intended workflow — useful for "
            "scheduled exports landing in a fixed location."
        )
        st.button("Pull from Server", disabled=True, use_container_width=True)

    if st.session_state.df is not None:
        df = st.session_state.df

        # Quick stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 Rows", f"{df.shape[0]:,}")
        c2.metric("📊 Columns", df.shape[1])
        c3.metric("⚠️ Missing Values", f"{df.isna().sum().sum():,}")
        c4.metric("🔄 Duplicates", f"{df.duplicated().sum():,}")

        st.markdown("#### 👀 Dataset Preview")
        st.dataframe(df.head(10), use_container_width=True)

        if st.button("▶️ Proceed to Data Profiling", type="primary", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()
    else:
        st.markdown("""
        <div class='insight-box'>
            <h4>👋 Welcome to CreditRisk ML POC</h4>
            <p>This platform intelligently adapts to <strong>any structured dataset</strong> — no hardcoded columns required.</p>
            <ul>
                <li>📤 Upload your own CSV/XLSX file, or</li>
                <li>🎲 Click <strong>"Use Synthetic Dataset"</strong> to explore with demo data</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# STEP 2: Data Profiling
# ─────────────────────────────────────────────
def render_profiling():
    st.markdown("""
    <div class='step-header'>
        <h3>🔍 Step 2 — Data Profiling & Target Selection</h3>
        <p>Automatic schema analysis and intelligent target detection</p>
    </div>
    """, unsafe_allow_html=True)

    df = st.session_state.df

    # Auto-detect column types
    with st.spinner("Analyzing dataset schema..."):
        col_types = detect_column_types(df)
    st.session_state.col_types = col_types

    # Display column type breakdown
    st.markdown("#### 🧬 Column Type Analysis")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("🔢 Numeric", len(col_types["numeric"]))
    col_b.metric("🏷️ Categorical", len(col_types["categorical"]))
    col_c.metric("📅 Datetime", len(col_types["datetime"]))
    col_d.metric("✅ Boolean / ID", len(col_types["boolean"]) + len(col_types["id"]))

    tabs = st.tabs(["📊 Summary Stats", "❓ Missing Values", "🏷️ Column Types", "📈 Distributions"])

    with tabs[0]:
        st.dataframe(df.describe(include="all").T.round(3), use_container_width=True)

    with tabs[1]:
        missing = df.isna().sum().reset_index()
        missing.columns = ["Column", "Missing Count"]
        missing["Missing %"] = (missing["Missing Count"] / len(df) * 100).round(2)
        missing = missing[missing["Missing Count"] > 0].sort_values("Missing %", ascending=False)
        if missing.empty:
            st.success("✅ No missing values detected!")
        else:
            st.dataframe(missing, use_container_width=True)
            fig = px.bar(missing, x="Column", y="Missing %", color="Missing %",
                          color_continuous_scale="Reds", title="Missing Value % by Column")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#e2e8f0"))
            st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        type_data = []
        for type_name, cols in col_types.items():
            for col in cols:
                type_data.append({"Column": col, "Detected Type": type_name,
                                   "Pandas Dtype": str(df[col].dtype),
                                   "Unique Values": df[col].nunique(),
                                   "Non-Null Count": df[col].notna().sum()})
        if type_data:
            st.dataframe(pd.DataFrame(type_data), use_container_width=True)

    with tabs[3]:
        num_cols = col_types["numeric"][:8]
        if num_cols:
            import plotly.figure_factory as ff
            fig = go.Figure()
            for col in num_cols[:4]:
                data = df[col].dropna()
                fig.add_trace(go.Histogram(x=data, name=col, opacity=0.6, nbinsx=30))
            fig.update_layout(barmode="overlay", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
                               title="Distribution of Numeric Features (first 4)")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Target selection
    st.markdown("#### 🎯 Target Variable Selection")
    target_candidates = detect_target_candidates(df)
    all_cols = df.columns.tolist()

    # Pre-select best candidate
    default_idx = 0
    if target_candidates:
        for i, col in enumerate(all_cols):
            if col in target_candidates:
                default_idx = i
                break
    else:
        # Fallback: find first binary 0/1 column that isn't an ID
        for i, col in enumerate(all_cols):
            if "id" in col.lower():
                continue
            col_vals = df[col].dropna().unique()
            if set(col_vals).issubset({0, 1, 0.0, 1.0}) and len(col_vals) == 2:
                default_idx = i
                break

    target_col = st.selectbox(
        "Select target variable",
        options=all_cols,
        index=default_idx,
        help="The system will detect binary/multiclass/regression task automatically.",
    )
    st.session_state.target_col = target_col

    # Detect task type
    task_type = detect_task_type(df[target_col])

    # ── Quantitative target: offer binning into risk bands ──────────────
    if task_type == "regression":
        st.markdown("#### 🎚️ Quantitative Target Detected")
        st.info(
            "This target is continuous (a regression problem). In credit risk, "
            "continuous scores are often converted into discrete risk bands "
            "(e.g. Grade A-E) instead of predicting an exact number. "
            "Choose how you'd like to proceed below."
        )

        target_mode = st.radio(
            "How should this target be modeled?",
            ["Keep as continuous (Regression)", "Convert to risk bands (Classification)"],
            key="target_mode_choice",
        )

        if target_mode == "Convert to risk bands (Classification)":
            from utils import bin_continuous_target

            bc1, bc2 = st.columns(2)
            with bc1:
                n_bins = st.slider("Number of risk bands", 2, 10, 5, key="n_bins_slider")
                bin_method = st.selectbox(
                    "Binning method",
                    ["quantile", "equal_width"],
                    format_func=lambda x: "Equal Frequency (Quantile)" if x == "quantile" else "Equal Width",
                    key="bin_method_select",
                )
            with bc2:
                default_labels = ["A (Lowest Risk)", "B", "C", "D", "E (Highest Risk)"][:n_bins] \
                    if n_bins <= 5 else [f"Band_{i+1}" for i in range(n_bins)]
                use_custom_labels = st.checkbox("Customize band labels", value=False, key="custom_labels_chk")
                if use_custom_labels:
                    label_input = st.text_input(
                        "Comma-separated labels (e.g. A,B,C,D,E)",
                        value=",".join(default_labels),
                        key="custom_labels_input",
                    )
                    band_labels = [l.strip() for l in label_input.split(",")]
                    if len(band_labels) != n_bins:
                        st.warning(f"⚠️ Provided {len(band_labels)} labels but need {n_bins}. Using defaults.")
                        band_labels = default_labels
                else:
                    band_labels = default_labels

            binned_series, bin_edges, bin_counts = bin_continuous_target(
                df[target_col], n_bins=n_bins, method=bin_method, labels=band_labels
            )

            st.markdown("**Preview — Band Distribution:**")
            bin_preview_df = pd.DataFrame(
                list(bin_counts.items()), columns=["Band", "Count"]
            )
            st.dataframe(bin_preview_df, use_container_width=True)

            fig_bins = px.bar(
                bin_preview_df, x="Band", y="Count",
                color="Band", title="Risk Band Distribution",
            )
            fig_bins.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig_bins, use_container_width=True)

            if st.button("✅ Apply Binning", type="primary", key="apply_binning_btn"):
                binned_col_name = f"{target_col}_band"
                df[binned_col_name] = binned_series
                st.session_state.df = df
                st.session_state.target_col = binned_col_name
                target_col = binned_col_name
                task_type = "multiclass"
                st.session_state["_target_was_binned"] = True
                st.session_state["_original_continuous_target"] = df[target_col].copy()
                st.success(
                    f"✅ Created '{binned_col_name}' with {n_bins} risk bands. "
                    f"Task type switched to multiclass classification."
                )
                st.rerun()

            # If already applied in a previous run, keep using the binned target
            if st.session_state.get("_target_was_binned") and target_col.endswith("_band"):
                task_type = "multiclass"

    st.session_state.task_type = task_type

    # Task type badge
    badge_color = {"binary": "#10b981", "multiclass": "#f59e0b", "regression": "#6366f1"}
    task_label = {"binary": "Binary Classification ✅", "multiclass": "Multiclass Classification ⚠️",
                  "regression": "Regression ⚠️"}
    st.markdown(
        f"<div style='display:inline-block; background:{badge_color[task_type]}; "
        f"color:white; padding:0.3rem 1rem; border-radius:20px; font-weight:bold; margin:0.5rem 0'>"
        f"Task Type: {task_label[task_type]}</div>",
        unsafe_allow_html=True
    )

    if task_type != "binary":
        st.warning("⚠️ This POC is optimized for binary classification. Other task types are partially supported.")

    # Show class distribution
    if task_type in ("binary", "multiclass"):
        col1, col2 = st.columns(2)
        with col1:
            dist = df[target_col].value_counts()
            st.markdown("**Class Distribution**")
            st.dataframe(dist.reset_index().rename(columns={"index": "Class", target_col: "Count"}),
                          use_container_width=True)
        with col2:
            fig = px.pie(values=dist.values, names=dist.index.astype(str),
                          title=f"Target Distribution: {target_col}",
                          color_discrete_sequence=["#6366f1", "#f59e0b", "#10b981", "#ef4444"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"))
            st.plotly_chart(fig, use_container_width=True)

        # Imbalance warning
        if task_type == "binary":
            counts = df[target_col].value_counts()
            ratio = counts.max() / counts.min() if counts.min() > 0 else 99
            if ratio > 3:
                st.warning(f"⚠️ Imbalanced dataset detected (ratio ≈ {ratio:.1f}:1). Enable class_weight='balanced' in the training step.")
            else:
                st.success("✅ Class distribution is reasonably balanced.")



    # ── Target leakage detection ──────────────────────────────────────────────
    _leakage_cols: list = []
    _target_num = pd.to_numeric(df[target_col], errors="coerce")
    if _target_num.notna().sum() >= 2:
        for _lc in col_types.get("numeric", []):
            if _lc == target_col:
                continue
            try:
                _corr = df[_lc].corr(_target_num)
                if pd.notna(_corr) and abs(_corr) > 0.95:
                    _leakage_cols.append(_lc)
            except Exception:
                pass
    if _leakage_cols != st.session_state.get("_leakage_cols_prev", []):
        st.session_state["_leakage_cols_prev"] = _leakage_cols
    st.session_state["leakage_risk_cols"] = _leakage_cols
    if _leakage_cols:
        st.warning(f"⚠️ Potential leakage detected: {', '.join([f'`{c}`' for c in _leakage_cols])} correlate >0.95 with target.")

    # ── Date integrity check ──────────────────────────────────────────────────
    _datetime_cols = col_types.get("datetime", [])
    if _datetime_cols:
        st.markdown("#### 📅 Date Integrity")
        _today = pd.Timestamp.today().normalize()
        _date_integrity: dict = {}
        for _dt_col in _datetime_cols:
            try:
                _parsed = pd.to_datetime(df[_dt_col], errors="coerce")
                _valid = _parsed.dropna()
                if _valid.empty:
                    continue
                _min_d, _max_d = _valid.min(), _valid.max()
                _future_n = int((_valid > _today).sum())
                _ancient_n = int((_valid.dt.year < 1900).sum())
                _date_integrity[_dt_col] = {
                    "min_date": str(_min_d.date()),
                    "max_date": str(_max_d.date()),
                    "future_count": _future_n,
                    "ancient_count": _ancient_n,
                }
                st.markdown(f"**`{_dt_col}`** — Range: `{_min_d.date()}` → `{_max_d.date()}`")
                if _future_n > 0:
                    st.warning(f"⚠️ {_future_n} future date(s) detected in `{_dt_col}` — possible data entry error")
                if _ancient_n > 0:
                    st.warning(f"⚠️ {_ancient_n} date(s) before 1900 detected in `{_dt_col}` — possible parsing error")
            except Exception:
                pass
        st.session_state["date_integrity"] = _date_integrity

    # ── Data Dictionary download ──────────────────────────────────────────────
    st.divider()
    _dd_rows = []
    for _col in df.columns:
        _col_type = next((t for t, cols in col_types.items() if _col in cols), "unknown")
        _s = df[_col]
        _miss_n = int(_s.isna().sum())
        _miss_pct = round(_miss_n / len(df) * 100, 2)
        _uniq = int(_s.nunique())
        _is_num = pd.api.types.is_numeric_dtype(_s)
        try:
            _dd_min = round(float(_s.min()), 4) if _is_num else ""
            _dd_max = round(float(_s.max()), 4) if _is_num else ""
            _dd_mean = round(float(_s.mean()), 4) if _is_num else ""
        except Exception:
            _dd_min, _dd_max, _dd_mean = "", "", ""
        _samp = ", ".join(str(v) for v in _s.dropna().unique()[:3])
        _dd_rows.append({
            "Column": _col,
            "Detected Type": _col_type,
            "Missing Count": _miss_n,
            "Missing %": _miss_pct,
            "Unique Values": _uniq,
            "Min": _dd_min,
            "Max": _dd_max,
            "Mean": _dd_mean,
            "Sample Values": _samp,
        })
    st.download_button(
        "📥 Download Data Dictionary (CSV)",
        data=pd.DataFrame(_dd_rows).to_csv(index=False).encode("utf-8"),
        file_name="data_dictionary.csv",
        mime="text/csv",
        use_container_width=True,
        key="data_dict_download",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back to Upload", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
    with col2:
        if st.button("▶️ Proceed to Preprocessing", type="primary", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()


# ─────────────────────────────────────────────
# STEP 3: Preprocessing
# ─────────────────────────────────────────────
def render_preprocessing():
    st.markdown("""
    <div class='step-header'>
        <h3>⚙️ Step 3 — Preprocessing Config & Train/Val/Test Split</h3>
        <p>Finalize X/y, then split <em>immediately</em> so every learned statistic comes from training data only</p>
    </div>
    """, unsafe_allow_html=True)

    df = st.session_state.df
    col_types = st.session_state.col_types
    target_col = st.session_state.target_col
    task_type = st.session_state.get("task_type", "binary")

    # ── Finalize X / y (drop IDs + duplicates ONLY — no statistics learned) ──
    X, y, clean_info = finalize_xy(df, col_types, target_col)
    st.session_state.X = X
    st.session_state.y = y

    st.markdown(
        "<div style='background:#071a0e;border-left:4px solid #10b981;border-radius:0 8px 8px 0;"
        "padding:0.75rem 1rem;margin:0.5rem 0;color:#94a3b8;font-size:0.85rem;'>"
        "🔒 <strong style='color:#10b981;'>Leakage control:</strong> the dataset is split <em>before</em> "
        "any feature engineering. IV/WOE, mutual information, correlation/VIF, variance, frequency maps, "
        "binning edges, imputation medians and feature-selection decisions are all learned on the "
        "<strong>training split only</strong> in the next step and applied unchanged to validation/test."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Split configuration (moved here from Training so it precedes FE) ──
    st.markdown("#### ✂️ Train / Validation / Test Split")
    sp1, sp2, sp3 = st.columns(3)
    with sp1:
        test_size = st.slider("Test set size (%)", 5, 35,
                              int(st.session_state.get("split_test_size", 0.15) * 100), 5,
                              key="prep_ts_slider") / 100
    with sp2:
        val_size = st.slider("Validation set size (%)", 5, 25,
                             int(st.session_state.get("split_val_size", 0.15) * 100), 5,
                             key="prep_vs_slider") / 100
    with sp3:
        random_seed = st.number_input("Random seed", min_value=0, max_value=9999,
                                      value=int(st.session_state.get("split_seed", 42)),
                                      key="prep_seed_inp")

    # Persist split params; if they change, invalidate downstream engineered splits
    _prev = (st.session_state.get("split_test_size"), st.session_state.get("split_val_size"),
             st.session_state.get("split_seed"))
    _now = (test_size, val_size, int(random_seed))
    if _prev != _now:
        for _k in ("X_train_engineered", "X_val_engineered", "X_test_engineered"):
            st.session_state[_k] = None
    st.session_state.split_test_size = test_size
    st.session_state.split_val_size = val_size
    st.session_state.split_seed = int(random_seed)

    # ── Perform the split on the BASIC (pre-FE) feature matrix ──
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=int(random_seed),
    )
    split_stats = compute_split_stats(X_train, X_val, X_test, y_train, y_val, y_test)
    st.session_state.X_train = X_train
    st.session_state.X_val = X_val
    st.session_state.X_test = X_test
    st.session_state.y_train = y_train
    st.session_state.y_val = y_val
    st.session_state.y_test = y_test
    st.session_state.split_stats = split_stats

    m1, m2, m3 = st.columns(3)
    m1.metric("🏋️ Train", f"{split_stats['train_n']:,}", f"{split_stats['train_pct']:.0%}")
    m2.metric("🔍 Validation", f"{split_stats['val_n']:,}", f"{split_stats['val_pct']:.0%}")
    m3.metric("🧪 Test", f"{split_stats['test_n']:,}", f"{split_stats['test_pct']:.0%}")

    if task_type == "binary" and "train_class_dist" in split_stats:
        dist_data = []
        for sn in ["train", "val", "test"]:
            for cls, pct in split_stats.get(f"{sn}_class_dist", {}).items():
                dist_data.append({"Split": sn.capitalize(), "Class": str(cls), "Proportion": pct})
        if dist_data:
            fig = px.bar(pd.DataFrame(dist_data), x="Split", y="Proportion", color="Class",
                          barmode="stack", color_discrete_map={"0": "#10b981", "1": "#ef4444"},
                          title="Class Distribution per Split (stratified)")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#e2e8f0"))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Build the preprocessing report on the TRAIN split ONLY ──
    with st.spinner("🔧 Learning preprocessing strategy on the training split..."):
        report = build_preprocessing_report(
            X_train.assign(**{target_col: y_train}), col_types, target_col
        )
        report["duplicates_removed"] = clean_info["duplicates_removed"]
        # Unfitted preprocessor scoped to train columns (re-fit later inside train_model)
        preprocessor = rebuild_preprocessor_for(X_train, col_types, target_col, report)

    st.session_state.preprocessor = preprocessor
    st.session_state.prep_report = report
    st.session_state.feature_names = list(X_train.columns)

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Features (basic)", X.shape[1])
    c2.metric("🗑️ Duplicates Removed", report.get("duplicates_removed", 0))
    c3.metric("🔢 Numeric Columns", len(report["numeric"]))
    c4.metric("🏷️ Categorical Columns", len(report["categorical"]))

    st.markdown("#### 🧠 Preprocessing Decisions")
    st.info("ℹ️ Scaler/imputer strategies were chosen from **training-split** skewness, outliers, "
            "missing %, and cardinality. Imputation values (means/medians) are fit on the training "
            "split inside the model pipeline and applied unchanged to validation/test.")

    decisions = report.get("decisions", [])
    if decisions:
        for dec in decisions:
            col_type_icon = {"numeric": "🔢", "categorical": "🏷️", "datetime": "📅", "boolean": "✅"}.get(dec["type"], "📌")
            with st.expander(f"{col_type_icon} **{dec['column']}** ({dec['type']})", expanded=False):
                for action in dec["actions"]:
                    st.markdown(f"- {action}")

    if report["numeric"] or report["categorical"]:
        st.markdown("#### 📊 Preprocessing Strategy Summary (training split)")
        summary_rows = []
        for col, info in report["numeric"].items():
            summary_rows.append({
                "Column": col, "Type": "Numeric",
                "Scaler": info["scaler"].capitalize(),
                "Imputer": info["imputer"].capitalize(),
                "Outliers": "Yes" if info["has_outliers"] else "No",
                "Log Transform": "Suggested" if info["needs_log"] else "-",
                "Missing % (train)": f"{info['missing_pct']:.1%}",
            })
        for col, info in report["categorical"].items():
            summary_rows.append({
                "Column": col, "Type": "Categorical",
                "Scaler": "-", "Imputer": "Mode", "Outliers": "-", "Log Transform": "-",
                "Missing % (train)": f"{info['missing_pct']:.1%}",
            })
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

    st.markdown("#### 🔎 Training Feature Matrix Preview (X_train)")
    st.dataframe(X_train.head(5), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()
    with col2:
        if st.button("▶️ Proceed to Feature Engineering", type="primary", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()


# ─────────────────────────────────────────────
# STEP 4: Feature Engineering
# ─────────────────────────────────────────────
def render_feature_engineering():
    st.markdown("""
    <div class='step-header'>
        <h3>🔬 Step 4 — Intelligent Feature Engineering</h3>
        <p>Automatic feature analysis, creation, and selection — no hardcoded domain logic</p>
    </div>
    """, unsafe_allow_html=True)

    col_types = st.session_state.col_types
    task_type = st.session_state.task_type

    X_train = st.session_state.get("X_train")
    y_train = st.session_state.get("y_train")
    X_val = st.session_state.get("X_val")
    X_test = st.session_state.get("X_test")
    if X_train is None or y_train is None:
        st.warning("⚠️ No train/validation/test split found. Complete Step 3 "
                   "(Preprocessing & Split) before feature engineering.")
        return

    st.markdown(
        "<div style='background:#071a0e;border-left:4px solid #10b981;border-radius:0 8px 8px 0;"
        "padding:0.7rem 1rem;margin:0.4rem 0;color:#94a3b8;font-size:0.85rem;'>"
        "🔒 <strong style='color:#10b981;'>Train-only learning:</strong> every diagnostic and "
        "transformation below (IV/WOE, MI, correlation, VIF, variance, frequency maps, binning edges, "
        "feature selection) is learned on <strong>X_train / y_train</strong> and then applied unchanged "
        "to the validation and test splits.</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("🔬 Analyzing the TRAINING split for feature engineering opportunities..."):
        plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)

    # Show analysis plan
    st.markdown("#### 📋 Feature Engineering Plan")
    if not plan["applied_steps"]:
        st.info("No significant feature engineering opportunities detected for this dataset.")
    else:
        for step in plan["applied_steps"]:
            with st.expander(f"🔧 **{step['step']}** — {len(step['columns'])} column(s)", expanded=True):
                st.markdown(f"**Why:** {step['reason']}")
                st.markdown("**Columns:** " + ", ".join([f"`{c}`" for c in step["columns"]]))

    # Mutual Information Scores
    if plan.get("mi_scores"):
        st.markdown("#### 📈 Mutual Information with Target")
        st.caption("📌 Calculated using training data only.")
        mi_df = pd.DataFrame(list(plan["mi_scores"].items()), columns=["Feature", "MI Score"])
        mi_df = mi_df.sort_values("MI Score", ascending=False).head(15)
        fig = go.Figure(go.Bar(
            x=mi_df["Feature"], y=mi_df["MI Score"],
            marker_color="#6366f1",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"), title="Top Feature MI Scores",
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)

    # Lightweight multicollinearity diagnostics
    multicol = plan.get("multicollinearity", {})
    high_corr = multicol.get("high_corr_pairs", [])
    vif_scores = multicol.get("vif", {})
    if high_corr or vif_scores:
        st.markdown("#### Multicollinearity Check")
        st.caption("📌 Correlation pairs and approximate VIF calculated using training data only.")
        mc1, mc2 = st.columns(2)
        with mc1:
            if high_corr:
                st.dataframe(pd.DataFrame(high_corr).head(20), use_container_width=True)
            else:
                st.success("No high-correlation numeric pairs detected.")
        with mc2:
            if vif_scores:
                vif_df = (
                    pd.DataFrame(list(vif_scores.items()), columns=["Feature", "Approx VIF"])
                    .sort_values("Approx VIF", ascending=False)
                    .head(15)
                )
                st.dataframe(vif_df, use_container_width=True)

    # Information Value / WOE diagnostics
    if plan.get("iv_scores"):
        st.markdown("#### Information Value and WOE")
        st.caption("📌 IV scores, WOE buckets and the IV<0.02 removal threshold are calculated using training data only.")
        iv_df = pd.DataFrame(list(plan["iv_scores"].items()), columns=["Feature", "IV"])
        iv_df = iv_df.sort_values("IV", ascending=False).head(20)
        st.dataframe(iv_df, use_container_width=True)
        st.caption("WOE copies are created for the top IV features only; very low-IV features are removed with IV < 0.02.")

    # ── Univariate Gini ───────────────────────────────────────────────────────
    if task_type == "binary" and col_types.get("numeric"):
        with st.spinner("Computing univariate Gini coefficients (training data only)..."):
            _gini = compute_univariate_gini(X_train, y_train, col_types.get("numeric", []))
        st.session_state["gini_scores"] = _gini
        if _gini:
            st.markdown("#### 📐 Univariate Gini Coefficients")
            st.caption("📌 Calculated using training data only.")
            _gini_df = pd.DataFrame(
                list(_gini.items()), columns=["Feature", "Gini Coefficient"]
            )
            st.dataframe(_gini_df, use_container_width=True)

    # ── Apply the TRAIN-learned plan to all three splits (pure transform) ──
    with st.spinner("Applying training-learned transformations to train / validation / test..."):
        X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
        X_val_engineered, _ = (
            apply_feature_engineering(X_val, plan) if X_val is not None else (None, None)
        )
        X_test_engineered, _ = (
            apply_feature_engineering(X_test, plan) if X_test is not None else (None, None)
        )

    st.session_state.fe_plan = plan
    st.session_state.fe_summary = fe_summary
    st.session_state.X_train_engineered = X_train_engineered
    st.session_state.X_val_engineered = X_val_engineered
    st.session_state.X_test_engineered = X_test_engineered
    # Back-compat alias: a few legacy views read `X_engineered`; point it at the
    # engineered TRAIN matrix. Full-portfolio consumers use _full_engineered_X().
    st.session_state.X_engineered = X_train_engineered
    X_engineered = X_train_engineered

    _excl_pd = fe_summary.get("excluded_orig_pd") or []
    if _excl_pd:
        st.info("🔒 Hidden from model development (origination PD / DPD leakage): "
                + ", ".join(f"`{c}`" for c in _excl_pd)
                + " — kept in the dataset for IFRS 9 SICR in the ECL step.")

    # Note: Exposure at Default (EAD) is now modelled in Model Development → 💳 EAD Model tab.

    # Before vs After
    st.markdown("#### 📊 Before vs After")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Original Features", fe_summary["original_shape"][1])
    c2.metric("Final Features", fe_summary["final_shape"][1])
    c3.metric("Features Added", fe_summary["features_added"], delta=f"+{fe_summary['features_added']}")
    c4.metric("Features Removed", fe_summary["features_removed"], delta=f"-{fe_summary['features_removed']}" if fe_summary["features_removed"] else "0")

    # Transformations applied
    if fe_summary.get("transformed"):
        st.markdown("#### ✅ Transformations Applied")
        for t in fe_summary["transformed"]:
            st.markdown(f"- `{t}`")

    if fe_summary.get("removed"):
        st.markdown("#### 🗑️ Features Removed")
        for r in fe_summary["removed"]:
            st.markdown(f"- `{r}` (high correlation, low variance, or low IV)")

    # Preview
    st.markdown("#### 🔎 Engineered Training Matrix Preview (X_train_engineered)")
    st.dataframe(X_engineered.head(5), use_container_width=True)
    if X_val_engineered is not None and X_test_engineered is not None:
        st.caption(
            f"✅ The identical {X_engineered.shape[1]}-column transformation was applied to all splits — "
            f"train {X_train_engineered.shape}, validation {X_val_engineered.shape}, test {X_test_engineered.shape}. "
            "Validation/test never produced their own IV, WOE, frequency or selection decisions."
        )



    # ── Feature Decision Log download ─────────────────────────────────────────
    st.divider()
    _orig_cols = list(st.session_state.X.columns)
    _fe_iv = plan.get("iv_scores", {})
    _fe_vif = plan.get("multicollinearity", {}).get("vif", {})
    _transformed_src = set(
        plan.get("log_transform_cols", [])
        + plan.get("binning_cols", [])[:5]
        + plan.get("freq_encoding_cols", [])
        + plan.get("woe_cols", [])
    )
    _col_reason: dict = {}
    for _fstep in plan.get("applied_steps", []):
        for _fc in _fstep.get("columns", []):
            _col_reason[_fc] = f"{_fstep['step']}: {_fstep['reason']}"
    _removed_set = set(fe_summary.get("removed", []))
    _log_rows = []
    for _fc in _orig_cols:
        if _fc in _removed_set:
            _dec, _rsn = "Removed", _col_reason.get(_fc, "Removed during feature engineering")
        elif _fc in _transformed_src:
            _dec, _rsn = "Transformed", _col_reason.get(_fc, "Transformation applied")
        else:
            _dec, _rsn = "Retained", "No transformation required"
        _log_rows.append({
            "Feature": _fc, "Decision": _dec, "Reason": _rsn,
            "IV Score": _fe_iv.get(_fc, ""), "VIF Score": _fe_vif.get(_fc, ""),
        })
    for _fc in fe_summary.get("added", []):
        _rsn = "New feature created during engineering"
        for _sfx in ("_log", "_bin", "_freq", "_woe"):
            if _fc.endswith(_sfx):
                _src = _fc[: -len(_sfx)]
                if _src in _col_reason:
                    _rsn = _col_reason[_src]
                    break
        if "_x_" in _fc and _rsn == "New feature created during engineering":
            for _part in _fc.split("_x_"):
                if _part in _col_reason:
                    _rsn = _col_reason[_part]
                    break
        _log_rows.append({
            "Feature": _fc, "Decision": "Added", "Reason": _rsn,
            "IV Score": _fe_iv.get(_fc, ""), "VIF Score": _fe_vif.get(_fc, ""),
        })
    st.download_button(
        "📥 Download Feature Decision Log (CSV)",
        data=pd.DataFrame(_log_rows).to_csv(index=False).encode("utf-8"),
        file_name="feature_decision_log.csv",
        mime="text/csv",
        use_container_width=True,
        key="feature_decision_log_download",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    with col2:
        if st.button("▶️ Proceed to Model Selection", type="primary", use_container_width=True):
            st.session_state.current_step = 5
            st.rerun()


# ─────────────────────────────────────────────
# STEP 5: Model Selection
# ─────────────────────────────────────────────
def render_model_selection():
    st.markdown("""
    <div class='step-header'>
        <h3>🤖 Step 5 — Smart Model Recommendation</h3>
        <p>Models ranked by suitability for your dataset — with explanations</p>
    </div>
    """, unsafe_allow_html=True)

    X = st.session_state.get("X_train_engineered")
    if X is None:
        X = st.session_state.get("X_train")
    if X is None:
        X = st.session_state.X
    y = st.session_state.get("y_train")
    if y is None:
        y = st.session_state.y
    task_type = st.session_state.task_type

    n_samples, n_features = X.shape
    imbalance_ratio = 1.0
    if task_type == "binary":
        vc = y.value_counts()
        imbalance_ratio = vc.max() / vc.min() if vc.min() > 0 else 5.0

    recommendations = recommend_models(n_samples, n_features, imbalance_ratio, task_type)

    st.markdown(f"#### 📊 Training set: {n_samples:,} samples × {n_features} features | Imbalance ratio: {imbalance_ratio:.1f}:1")

    st.markdown("#### 🏆 Recommended Models (Ranked)")
    for i, rec in enumerate(recommendations):
        rank_badge = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][min(i, 4)]
        with st.expander(
            f"{rank_badge} {rec['icon']} **{rec['name']}** — Score: {rec['score']}/10",
            expanded=(i < 2)
        ):
            st.markdown(f"**Description:** {rec['description']}")
            st.markdown(f"**Why recommended:** {rec.get('why', '-')}")
            if rec.get("best_for"):
                st.markdown("**Best for:** " + " · ".join([f"`{b}`" for b in rec["best_for"]]))

    # Model selector
    model_names = [r["name"] for r in recommendations]
    selected_model = st.selectbox(
        "Select model to train",
        options=model_names,
        index=0,
        help="The top-ranked model is pre-selected. You can change this.",
    )
    st.session_state.selected_model = selected_model

    default_compare = model_names[:min(3, len(model_names))]
    compare_models = st.multiselect(
        "Models to compare after training split",
        options=model_names,
        default=default_compare,
        help="These models will be trained with lightweight defaults on the same split for comparison.",
    )
    st.session_state.compare_models = compare_models

    # Credit risk context
    if task_type == "binary":
        st.markdown("""
        <div class='insight-box'>
            <h4>💡 Credit Risk Evaluation Strategy</h4>
            <p>In credit risk, <strong>Recall</strong> is the most critical metric because failing to identify
            a truly risky customer (false negative) is far more costly than incorrectly flagging a safe one.</p>
            <p>We optimize for: <strong>ROC-AUC → Recall → PR-AUC → F1</strong></p>
        </div>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()
    with col2:
        if st.button("▶️ Proceed to Training", type="primary", use_container_width=True):
            st.session_state.current_step = 6
            st.rerun()


# ─────────────────────────────────────────────
# STEP 6: Training  (v2 — manual params + column-safe pipeline)
# ─────────────────────────────────────────────

def _manual_params_ui(model_name: str, task_type: str) -> dict:
    """
    Render per-model manual hyperparameter sliders/selects.
    Returns a dict of param_name → value chosen by the user.
    """
    st.markdown("#### 🎛️ Manual Hyperparameter Configuration")
    st.info("Every parameter is editable. Changes take effect on the next training run.")

    params = {}

    if model_name == "Logistic Regression":
        col1, col2 = st.columns(2)
        with col1:
            params["C"] = st.select_slider(
                "C — Inverse regularisation strength (higher = less regularised)",
                options=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0],
                value=1.0,
            )
            params["max_iter"] = st.slider("max_iter — Max solver iterations", 100, 5000, 1000, 100)
        with col2:
            params["solver"] = st.selectbox("solver", ["lbfgs", "liblinear", "saga", "newton-cg"], index=0)
            params["penalty"] = st.selectbox("penalty — Regularisation type", ["l2", "l1", "elasticnet", "none"], index=0)
            if params["penalty"] == "elasticnet":
                params["l1_ratio"] = st.slider("l1_ratio (elasticnet only)", 0.0, 1.0, 0.5, 0.05)
        params["random_state"] = 42

    elif model_name == "Random Forest":
        col1, col2, col3 = st.columns(3)
        with col1:
            params["n_estimators"] = st.slider("n_estimators — Number of trees", 50, 1000, 200, 50)
            params["max_depth"] = st.select_slider(
                "max_depth — Max tree depth (None = unlimited)",
                options=["None", 3, 5, 8, 10, 15, 20, 30],
                value="None",
            )
            params["max_depth"] = None if params["max_depth"] == "None" else int(params["max_depth"])
        with col2:
            params["min_samples_split"] = st.slider("min_samples_split", 2, 20, 2, 1)
            params["min_samples_leaf"] = st.slider("min_samples_leaf", 1, 10, 1, 1)
        with col3:
            params["max_features"] = st.selectbox("max_features", ["sqrt", "log2", "None", "0.5", "0.8"], index=0)
            if params["max_features"] not in ("sqrt", "log2", "None"):
                params["max_features"] = float(params["max_features"])
            elif params["max_features"] == "None":
                params["max_features"] = None
            params["bootstrap"] = st.checkbox("bootstrap", value=True)
            params["oob_score"] = st.checkbox("oob_score (requires bootstrap=True)", value=False)
        params["n_jobs"] = -1
        params["random_state"] = 42

    elif model_name == "XGBoost":
        col1, col2, col3 = st.columns(3)
        with col1:
            params["n_estimators"] = st.slider("n_estimators — Boosting rounds", 50, 1000, 200, 50)
            params["learning_rate"] = st.select_slider(
                "learning_rate (eta) — Step size shrinkage",
                options=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3],
                value=0.05,
            )
            params["max_depth"] = st.slider("max_depth — Max tree depth", 2, 12, 6, 1)
        with col2:
            params["subsample"] = st.slider("subsample — Row sampling ratio", 0.4, 1.0, 0.8, 0.05)
            params["colsample_bytree"] = st.slider("colsample_bytree — Feature sampling per tree", 0.3, 1.0, 0.8, 0.05)
            params["min_child_weight"] = st.slider("min_child_weight — Min child leaf weight", 1, 20, 1, 1)
        with col3:
            params["gamma"] = st.slider("gamma — Min loss split threshold", 0.0, 5.0, 0.0, 0.1)
            params["reg_alpha"] = st.slider("reg_alpha — L1 regularisation", 0.0, 10.0, 0.0, 0.1)
            params["reg_lambda"] = st.slider("reg_lambda — L2 regularisation", 0.0, 10.0, 1.0, 0.1)
        params["eval_metric"] = "logloss"
        params["verbosity"] = 0
        params["random_state"] = 42

    elif model_name == "LightGBM":
        col1, col2, col3 = st.columns(3)
        with col1:
            params["n_estimators"] = st.slider("n_estimators — Boosting rounds", 50, 1000, 200, 50)
            params["learning_rate"] = st.select_slider(
                "learning_rate",
                options=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3],
                value=0.05,
            )
            params["num_leaves"] = st.slider("num_leaves — Max leaves per tree", 10, 300, 31, 5)
        with col2:
            params["max_depth"] = st.slider("max_depth (−1 = no limit)", -1, 20, -1, 1)
            params["subsample"] = st.slider("subsample — Row sampling ratio", 0.4, 1.0, 0.8, 0.05)
            params["colsample_bytree"] = st.slider("colsample_bytree", 0.3, 1.0, 0.8, 0.05)
        with col3:
            params["min_child_samples"] = st.slider("min_child_samples — Min data in leaf", 5, 100, 20, 5)
            params["reg_alpha"] = st.slider("reg_alpha — L1 regularisation", 0.0, 10.0, 0.0, 0.1)
            params["reg_lambda"] = st.slider("reg_lambda — L2 regularisation", 0.0, 10.0, 0.0, 0.1)
        params["verbose"] = -1
        params["random_state"] = 42

    elif model_name == "Gradient Boosting":
        col1, col2, col3 = st.columns(3)
        with col1:
            params["n_estimators"] = st.slider("n_estimators", 50, 500, 100, 25)
            params["learning_rate"] = st.select_slider(
                "learning_rate",
                options=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3],
                value=0.1,
            )
            params["max_depth"] = st.slider("max_depth", 1, 10, 4, 1)
        with col2:
            params["subsample"] = st.slider("subsample", 0.4, 1.0, 1.0, 0.05)
            params["min_samples_split"] = st.slider("min_samples_split", 2, 20, 2, 1)
            params["min_samples_leaf"] = st.slider("min_samples_leaf", 1, 10, 1, 1)
        with col3:
            params["max_features"] = st.selectbox("max_features", ["sqrt", "log2", "None"], index=2)
            if params["max_features"] == "None":
                params["max_features"] = None
            params["loss"] = st.selectbox("loss", ["log_loss", "exponential"], index=0)
        params["random_state"] = 42

    return params


def _make_default_model(model_name: str, task_type: str, use_class_weight: bool = False):
    """Create a fast default model instance for comparison runs."""
    registry = CLASSIFICATION_MODELS if task_type in ("binary", "multiclass") else REGRESSION_MODELS
    model_class = registry[model_name]["class"]
    params = registry[model_name].get("default_params", {}).copy()
    if "n_estimators" in params:
        params["n_estimators"] = min(int(params["n_estimators"]), 80)

    if use_class_weight and task_type == "binary":
        try:
            if "class_weight" in model_class().get_params():
                params["class_weight"] = "balanced"
        except Exception:
            pass

    try:
        valid_keys = set(model_class().get_params().keys())
        params = {k: v for k, v in params.items() if k in valid_keys}
    except Exception:
        pass
    return model_class(**params)


def _comparison_metrics(pipeline, X_val, y_val, task_type: str, threshold: float = 0.5) -> Dict[str, Any]:
    y_pred = pipeline.predict(X_val)
    if task_type == "binary":
        y_proba = None
        if hasattr(pipeline, "predict_proba"):
            try:
                y_proba = pipeline.predict_proba(X_val)
            except Exception:
                pass
        metrics = compute_binary_metrics(y_val.values, y_pred, y_proba, threshold=threshold)
        return {
            "ROC-AUC": metrics.get("roc_auc"),
            "Recall": metrics.get("recall"),
            "Precision": metrics.get("precision"),
            "F1": metrics.get("f1"),
            "PR-AUC": metrics.get("pr_auc"),
            "Accuracy": metrics.get("accuracy"),
        }

    metrics = compute_regression_metrics(y_val.values, y_pred)
    return {
        "R2": metrics.get("r2"),
        "MAE": metrics.get("mae"),
        "RMSE": metrics.get("rmse"),
    }


def render_training():
    st.markdown("""
    <div class='step-header'>
        <h3>🎯 Step 6 — Model Training</h3>
        <p>Full transparency: inspect data splits, tune every hyperparameter, monitor results live</p>
    </div>
    """, unsafe_allow_html=True)

    col_types = st.session_state.col_types
    prep_report = st.session_state.prep_report
    target_col = st.session_state.target_col
    task_type = st.session_state.task_type
    threshold = getattr(st.session_state, "decision_threshold", 0.5)
    selected_model_name = getattr(st.session_state, "selected_model", None)

    if selected_model_name is None:
        st.warning("Please complete Model Selection first.")
        return

    # ── Consume the ENGINEERED splits produced in Step 4 (learned on train only) ──
    X_train = st.session_state.get("X_train_engineered")
    X_val = st.session_state.get("X_val_engineered")
    X_test = st.session_state.get("X_test_engineered")
    y_train = st.session_state.get("y_train")
    y_val = st.session_state.get("y_val")
    y_test = st.session_state.get("y_test")

    # Fallback to basic (pre-FE) splits if feature engineering hasn't been run yet
    if X_train is None:
        X_train = st.session_state.get("X_train")
        X_val = st.session_state.get("X_val")
        X_test = st.session_state.get("X_test")
    if X_train is None or y_train is None:
        st.warning("⚠️ No split found. Complete Step 3 (Split) and Step 4 "
                   "(Feature Engineering) before training.")
        return

    # ── Read-only split summary (the split is configured in Step 3, before FE) ──
    st.markdown("#### 📊 Data Split (configured in Step 3 — before feature engineering)")
    split_stats = st.session_state.get("split_stats") or compute_split_stats(
        X_train, X_val, X_test, y_train, y_val, y_test
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("🏋️ Train", f"{split_stats['train_n']:,}", f"{split_stats['train_pct']:.0%}")
    m2.metric("🔍 Validation", f"{split_stats['val_n']:,}", f"{split_stats['val_pct']:.0%}")
    m3.metric("🧪 Test", f"{split_stats['test_n']:,}", f"{split_stats['test_pct']:.0%}")
    st.caption(
        f"Engineered feature matrix: {X_train.shape[1]} columns. To change the split ratio or seed, "
        "return to Step 3 — feature engineering will re-learn on the new training split, with no "
        "validation/test information used."
    )

    if task_type == "binary" and "train_class_dist" in split_stats:
        dist_data = []
        for sn in ["train", "val", "test"]:
            for cls, pct in split_stats.get(f"{sn}_class_dist", {}).items():
                dist_data.append({"Split": sn.capitalize(), "Class": str(cls), "Proportion": pct})
        if dist_data:
            fig = px.bar(pd.DataFrame(dist_data), x="Split", y="Proportion", color="Class",
                          barmode="stack", color_discrete_map={"0": "#10b981", "1": "#ef4444"},
                          title="Class Distribution per Split")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#e2e8f0"))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Class Balancing ──
    st.markdown("#### ⚖️ Class Balancing")
    vc = y_train.value_counts()
    imbalance = vc.max() / vc.min() if vc.min() > 0 else 1.0

    use_smote = False  # SMOTE removed — use class_weight / scale_pos_weight instead
    if imbalance > 2 and task_type == "binary":
        st.info(
            f"⚠️ **Class imbalance detected ({imbalance:.1f}:1).** "
            "We recommend keeping class_weight enabled to prevent the model from ignoring the minority class."
        )
    bal_col1, bal_col2 = st.columns(2)
    with bal_col1:
        use_class_weight = st.checkbox("Use class_weight='balanced' in model", value=(imbalance > 1.5))
    with bal_col2:
        if task_type == "binary" and len(vc) == 2:
            spw = float(vc.iloc[0] / vc.iloc[-1])
            use_scale_pos = st.checkbox(f"Use scale_pos_weight for XGBoost (auto = {spw:.2f})", value=False)
            custom_spw = st.number_input("Custom scale_pos_weight", min_value=0.1, max_value=100.0, value=spw, step=0.5) if use_scale_pos else spw
        else:
            use_scale_pos = False
            custom_spw = 1.0

    st.divider()

    # ── Cross Validation ──
    st.markdown("#### 🔁 Cross Validation")
    cv_col1, cv_col2 = st.columns(2)
    with cv_col1:
        use_cv = st.checkbox("Enable K-Fold Cross Validation", value=False)
        cv_folds = st.slider("Number of folds", 3, 10, 5, 1) if use_cv else 5
    with cv_col2:
        use_hyperopt = st.checkbox("Enable RandomizedSearchCV hyperparameter tuning", value=False)
        if use_hyperopt:
            n_iter = st.slider("Search iterations (n_iter)", 5, 30, 8, 1)
            st.caption("Hyperopt will override the manual parameters below — disable it to use manual settings.")

    st.divider()

    # ── Manual Hyperparameters ──
    manual_params = _manual_params_ui(selected_model_name, task_type)

    # Class weight injection into manual params
    class_weight_val = "balanced" if use_class_weight else None
    scale_pos_weight_val = float(custom_spw) if (use_scale_pos and selected_model_name == "XGBoost") else None

    # Show current params summary
    with st.expander("📋 Current Parameters Summary (what will be used to train)", expanded=False):
        display_params = {**manual_params}
        if class_weight_val and selected_model_name in ("Logistic Regression", "Random Forest", "Gradient Boosting", "LightGBM"):
            display_params["class_weight"] = class_weight_val
        if scale_pos_weight_val and selected_model_name == "XGBoost":
            display_params["scale_pos_weight"] = scale_pos_weight_val
        st.json(display_params)

    st.divider()

    # Quick model comparison
    st.markdown("#### Model Comparison")
    compare_models = getattr(st.session_state, "compare_models", []) or [selected_model_name]
    st.caption("Trains selected candidates with fast defaults on the same split, scores validation data, then lets you promote one as final.")

    if st.button("Run Quick Model Comparison", use_container_width=True):
        comparison_rows = []
        comparison_pipelines = {}
        comparison_features = {}
        progress = st.progress(0)

        for i, model_name in enumerate(compare_models):
            try:
                model = _make_default_model(model_name, task_type, use_class_weight=use_class_weight)
                start = time.time()
                candidate_pipeline, candidate_info, candidate_features = train_model(
                    X_train, y_train,
                    col_types=col_types,
                    target_col=target_col,
                    prep_report=prep_report,
                    model=model,
                    use_smote=(use_smote and task_type == "binary"),
                    use_cv=False,
                    use_hyperopt=False,
                    task_type=task_type,
                )
                row = {"Model": model_name, "Training Time (s)": round(time.time() - start, 2)}
                row.update(_comparison_metrics(candidate_pipeline, X_val, y_val, task_type, threshold))
                comparison_rows.append(row)
                comparison_pipelines[model_name] = candidate_pipeline
                comparison_features[model_name] = candidate_features
            except Exception as e:
                comparison_rows.append({"Model": model_name, "Error": str(e)})
            progress.progress((i + 1) / max(len(compare_models), 1))

        comparison_df = pd.DataFrame(comparison_rows)
        if task_type == "binary" and "ROC-AUC" in comparison_df.columns:
            comparison_df = comparison_df.sort_values(
                by=["ROC-AUC", "Recall", "PR-AUC"],
                ascending=False,
                na_position="last",
            )
        elif task_type != "binary" and "R2" in comparison_df.columns:
            comparison_df = comparison_df.sort_values(by="R2", ascending=False, na_position="last")

        st.session_state.model_comparison_results = comparison_df
        st.session_state.model_comparison_pipelines = comparison_pipelines
        st.session_state.model_comparison_features = comparison_features
        st.success("Model comparison complete. Select a final model below.")

    comparison_df = st.session_state.get("model_comparison_results")
    if comparison_df is not None and not comparison_df.empty:
        st.dataframe(comparison_df, use_container_width=True)
        available_models = list(st.session_state.get("model_comparison_pipelines", {}).keys())
        if available_models:
            default_final = comparison_df["Model"].iloc[0] if "Model" in comparison_df.columns else available_models[0]
            default_idx = available_models.index(default_final) if default_final in available_models else 0
            final_choice = st.selectbox("Final model to use for evaluation/explainability", available_models, index=default_idx)
            if st.button("Use Selected Comparison Model as Final", type="primary", use_container_width=True):
                st.session_state.trained_pipeline = st.session_state.model_comparison_pipelines[final_choice]
                st.session_state.feature_names = st.session_state.get("model_comparison_features", {}).get(final_choice, [])
                st.session_state.final_model_name = final_choice
                time_match = comparison_df.loc[comparison_df["Model"] == final_choice, "Training Time (s)"]
                st.session_state.training_info = {"training_time_s": float(time_match.iloc[0]) if len(time_match) else 0.0}
                st.success(f"{final_choice} is now the final model for evaluation and explainability.")

    st.divider()

    # ── Train Button ──
    if st.button("🚀 Train Model Now", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("⚙️ Instantiating model with your parameters...")
            progress_bar.progress(10)

            # Build model directly from manual params
            from model_selector import CLASSIFICATION_MODELS, REGRESSION_MODELS
            models_registry = CLASSIFICATION_MODELS if task_type in ("binary", "multiclass") else REGRESSION_MODELS

            if selected_model_name not in models_registry:
                st.error(f"Model '{selected_model_name}' not found in registry.")
                return

            model_class = models_registry[selected_model_name]["class"]

            # Inject class balancing params
            final_params = {**manual_params}
            if class_weight_val and "class_weight" in model_class().get_params():
                final_params["class_weight"] = class_weight_val
            if scale_pos_weight_val is not None and selected_model_name == "XGBoost":
                final_params["scale_pos_weight"] = scale_pos_weight_val

            # Remove invalid params for this model
            valid_keys = set(model_class().get_params().keys())
            final_params = {k: v for k, v in final_params.items() if k in valid_keys}
            model = model_class(**final_params)

            progress_bar.progress(20)

            param_grid = None
            if use_hyperopt:
                status_text.text("🔍 Preparing hyperparameter search space...")
                from model_selector import get_hyperparameter_grid
                param_grid = get_hyperparameter_grid(selected_model_name, task_type)

            progress_bar.progress(30)
            status_text.text(f"🏋️ Training {selected_model_name} on {len(X_train):,} samples...")

            trained_pipeline, training_info, real_feature_names = train_model(
                X_train, y_train,
                col_types=col_types,
                target_col=target_col,
                prep_report=prep_report,
                model=model,
                use_smote=(use_smote and task_type == "binary"),
                use_cv=use_cv,
                cv_folds=cv_folds,
                use_hyperopt=use_hyperopt,
                param_grid=param_grid,
                task_type=task_type,
            )

            progress_bar.progress(90)
            status_text.text("✅ Training complete! Extracting feature names...")

            st.session_state.trained_pipeline = trained_pipeline
            st.session_state.training_info = training_info
            st.session_state.feature_names = real_feature_names
            st.session_state.final_model_name = selected_model_name
            # Store final params for display
            st.session_state.final_model_params = final_params

            progress_bar.progress(100)
            st.success(f"✅ **{selected_model_name}** trained successfully in **{training_info['training_time_s']}s**")

            # ── Results Panel ──
            res_cols = st.columns(4)
            res_cols[0].metric("⏱️ Training Time", f"{training_info['training_time_s']}s")
            res_cols[1].metric("📐 Features Used", len(real_feature_names))
            res_cols[2].metric("🏋️ Train Samples", f"{len(X_train):,}")
            if training_info.get("smote_skipped"):
                res_cols[3].warning(f"SMOTE skipped: {training_info['smote_skipped']}")

            if training_info.get("cv_mean"):
                cv_cols = st.columns(3)
                cv_cols[0].metric("📊 CV Mean Score", f"{training_info['cv_mean']:.4f}")
                cv_cols[1].metric("📊 CV Std", f"±{training_info['cv_std']:.4f}")
                cv_cols[2].metric("📊 CV Folds", cv_folds)
                fig_cv = go.Figure(go.Bar(
                    x=[f"Fold {i+1}" for i in range(len(training_info["cv_scores"]))],
                    y=training_info["cv_scores"],
                    marker_color="#6366f1",
                    text=[f"{s:.4f}" for s in training_info["cv_scores"]],
                    textposition="outside",
                ))
                fig_cv.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"), title=f"{cv_folds}-Fold CV Scores",
                    yaxis=dict(range=[0, 1], gridcolor="#334155"),
                )
                st.plotly_chart(fig_cv, use_container_width=True)

            if training_info.get("cv_best_score"):
                st.info(f"🎯 RandomizedSearchCV best score: **{training_info['cv_best_score']:.4f}**")
                if training_info.get("best_params"):
                    st.markdown("**Best Hyperparameters Found:**")
                    st.json(training_info["best_params"])

            # Show actual model params
            with st.expander("🔎 Model Parameters Used for Training", expanded=True):
                try:
                    actual_params = trained_pipeline.named_steps["model"].get_params()
                    st.json({k: str(v) for k, v in actual_params.items()})
                except Exception:
                    st.json({k: str(v) for k, v in final_params.items()})

            # Feature names extracted
            if real_feature_names:
                with st.expander(f"📋 {len(real_feature_names)} Real Feature Names After Preprocessing", expanded=False):
                    feat_df = pd.DataFrame({"#": range(1, len(real_feature_names)+1), "Feature Name": real_feature_names})
                    st.dataframe(feat_df, use_container_width=True)

        except Exception as e:
            progress_bar.progress(0)
            st.error(f"❌ Training failed: {e}")
            import traceback
            st.code(traceback.format_exc())
            return



    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back", use_container_width=True):
            st.session_state.current_step = 5
            st.rerun()
    with col2:
        if st.session_state.trained_pipeline and st.button("▶️ Proceed to Evaluation", type="primary", use_container_width=True):
            st.session_state.current_step = 7
            st.rerun()


# ─────────────────────────────────────────────
# STEP 7: Evaluation
# ─────────────────────────────────────────────
def render_evaluation():
    st.markdown("""
    <div class='step-header'>
        <h3>📊 Step 7 — Credit Risk Evaluation</h3>
        <p>Comprehensive evaluation with credit-risk focused metrics and visualizations</p>
    </div>
    """, unsafe_allow_html=True)

    pipeline = st.session_state.trained_pipeline
    X_test = st.session_state.get("X_test_engineered")
    if X_test is None:
        X_test = st.session_state.X_test
    y_test = st.session_state.y_test
    task_type = st.session_state.task_type
    threshold = getattr(st.session_state, "decision_threshold", 0.5)

    if pipeline is None:
        st.warning("Please complete model training first.")
        return

    with st.spinner("Computing predictions and metrics..."):
        y_pred = pipeline.predict(X_test)
        y_proba = None
        if hasattr(pipeline, "predict_proba"):
            try:
                y_proba = pipeline.predict_proba(X_test)
            except Exception:
                pass

        if task_type == "binary":
            metrics = compute_binary_metrics(
                y_test.values, y_pred, y_proba, threshold=threshold
            )
            hetero_input = y_proba if y_proba is not None else y_pred
        else:
            metrics = compute_regression_metrics(y_test.values, y_pred)
            hetero_input = y_pred
        hetero_check = compute_heteroscedasticity_check(
            y_test.values, hetero_input, task_type=task_type
        )

    st.session_state.eval_metrics = metrics
    st.session_state.y_proba_test = y_proba
    st.session_state.heteroscedasticity_check = hetero_check



    if task_type == "binary":
        # Key metrics dashboard
        st.markdown("#### 🏆 Key Performance Metrics")
        st.info("💡 In credit risk, **Recall** and **ROC-AUC** are the primary metrics. A missed default is more costly than a false alarm.")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("🎯 Accuracy", f"{metrics['accuracy']:.3f}")
        m2.metric("⚡ Precision", f"{metrics['precision']:.3f}")
        m3.metric("🚨 Recall", f"{metrics['recall']:.3f}", help="Most critical for credit risk")
        m4.metric("⚖️ F1 Score", f"{metrics['f1']:.3f}")
        if "roc_auc" in metrics:
            m5.metric("📈 ROC-AUC", f"{metrics['roc_auc']:.3f}")

        if "pr_auc" in metrics:
            st.metric("📊 PR-AUC", f"{metrics['pr_auc']:.3f}", help="Precision-Recall AUC — important for imbalanced datasets")

        tabs = st.tabs(["📈 ROC Curve", "🎯 PR Curve", "🔢 Confusion Matrix",
                         "📊 Score Distribution", "📉 Threshold Analysis", "📊 Lift Chart",
                         "Residual Check", "🎯 Actual vs Predicted"])

        with tabs[0]:
            if y_proba is not None:
                st.plotly_chart(plot_roc_curve(y_test.values, y_proba), use_container_width=True)

        with tabs[1]:
            if y_proba is not None:
                st.plotly_chart(plot_pr_curve(y_test.values, y_proba), use_container_width=True)

        with tabs[2]:
            fig = plot_confusion_matrix(
                metrics["confusion_matrix"],
                labels=["Non-Default (0)", "Default (1)"]
            )
            st.plotly_chart(fig, use_container_width=True)

            # Report table
            report = metrics.get("classification_report", {})
            if report:
                report_df = pd.DataFrame(report).T.round(3)
                st.dataframe(report_df, use_container_width=True)

        with tabs[3]:
            if y_proba is not None:
                st.plotly_chart(plot_score_distribution(y_test, y_proba), use_container_width=True)

        with tabs[4]:
            if y_proba is not None:
                st.plotly_chart(plot_threshold_analysis(y_test.values, y_proba), use_container_width=True)

        with tabs[5]:
            if y_proba is not None:
                st.plotly_chart(plot_lift_chart(y_test.values, y_proba), use_container_width=True)

        with tabs[6]:
            hetero = st.session_state.get("heteroscedasticity_check", {})
            st.markdown("#### Heteroscedasticity-Style Residual Check")
            hc1, hc2, hc3 = st.columns(3)
            hc1.metric("Signal", hetero.get("risk_flag", "N/A"))
            hc2.metric("Abs Residual Corr", hetero.get("spearman_abs_resid_vs_score", "N/A"))
            hc3.metric("Variance Ratio", hetero.get("variance_ratio", "N/A"))
            if hetero.get("bin_variance"):
                st.dataframe(pd.DataFrame(hetero["bin_variance"]), use_container_width=True)

        with tabs[7]:
            st.markdown("#### 📅 Actual vs Predicted PD Over Time")
            st.caption(
                "Compares the model's average predicted PD against the actual "
                "observed default rate across time periods. Large gaps (e.g. "
                "during COVID) indicate the model underestimated or overestimated risk."
            )

            df_orig = st.session_state.df
            date_cols = [c for c in df_orig.columns if pd.api.types.is_datetime64_any_dtype(df_orig[c])]
            if not date_cols:
                for c in df_orig.select_dtypes(include="object").columns:
                    try:
                        parsed = pd.to_datetime(df_orig[c], errors="coerce")
                        if parsed.notna().mean() > 0.8:
                            date_cols.append(c)
                    except Exception:
                        pass

            if not date_cols:
                st.warning(
                    "⚠️ No date column detected in the dataset. Temporal stability "
                    "analysis requires a loan origination or observation date column."
                )
            else:
                date_col_sel = st.selectbox("Date column", date_cols, key="temporal_date_col")
                freq_sel = st.radio(
                    "Time period grouping", ["Monthly", "Quarterly", "Half-Yearly", "Yearly"],
                    horizontal=True, key="temporal_freq", index=1,
                )
                freq_map = {
                    "Monthly": "ME",
                    "Quarterly": "QE",
                    "Half-Yearly": "6ME",
                    "Yearly": "YE",
                }

                try:
                    test_idx = y_test.index
                    dates_test = pd.to_datetime(df_orig.loc[test_idx, date_col_sel], errors="coerce")

                    fig_temporal = plot_actual_vs_predicted_over_time(
                        dates_test, y_test.values, y_proba[:, 1],
                        freq=freq_map[freq_sel]
                    )
                    st.plotly_chart(fig_temporal, use_container_width=True)

                    temporal_summary = compute_temporal_stability_summary(
                        dates_test, y_test.values, y_proba[:, 1],
                        freq=freq_map[freq_sel]
                    )

                    tc1, tc2, tc3 = st.columns(3)
                    tc1.metric("Periods Flagged",
                               f"{temporal_summary['n_periods_flagged']}/{temporal_summary['n_periods_total']}")
                    tc2.metric("Mean Absolute Gap", f"{temporal_summary['mean_absolute_gap']:.2%}")
                    if temporal_summary["max_underestimation_period"]:
                        tc3.metric("Worst Underestimation",
                                   temporal_summary["max_underestimation_period"],
                                   delta=f"{temporal_summary['max_underestimation_gap']:.2%} gap")

                    if temporal_summary["n_periods_flagged"] > 0:
                        st.warning(
                            f"⚠️ {temporal_summary['n_periods_flagged']} period(s) show a gap "
                            f">5% between actual and predicted default rates. This may indicate "
                            f"the model needs recalibration for stress periods or regime changes."
                        )
                    else:
                        st.success("✅ Model PD estimates track actual default rates closely across all periods.")

                except Exception as e:
                    st.error(f"Could not compute temporal stability: {e}")

    else:
        # Regression metrics
        st.markdown("#### 📊 Regression Metrics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("R²", f"{metrics['r2']:.4f}")
        c2.metric("MAE", f"{metrics['mae']:.4f}")
        c3.metric("MSE", f"{metrics['mse']:.4f}")
        c4.metric("RMSE", f"{metrics['rmse']:.4f}")

        hetero = st.session_state.get("heteroscedasticity_check", {})
        st.markdown("#### Heteroscedasticity Check")
        hc1, hc2, hc3 = st.columns(3)
        hc1.metric("Signal", hetero.get("risk_flag", "N/A"))
        hc2.metric("Abs Residual Corr", hetero.get("spearman_abs_resid_vs_score", "N/A"))
        hc3.metric("Variance Ratio", hetero.get("variance_ratio", "N/A"))
        if hetero.get("bin_variance"):
            st.dataframe(pd.DataFrame(hetero["bin_variance"]), use_container_width=True)

    # Downloads
    st.divider()
    st.markdown("#### 💾 Export Results")
    dc1, dc2 = st.columns(2)
    with dc1:
        metrics_df = pd.DataFrame([(k, v) for k, v in metrics.items()
                                    if isinstance(v, (int, float))], columns=["Metric", "Value"])
        df_to_csv_download(metrics_df, "evaluation_metrics.csv")
    with dc2:
        model_to_download(pipeline, "trained_model.pkl")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back", use_container_width=True):
            st.session_state.current_step = 6
            st.rerun()
    with col2:
        if st.button("▶️ Proceed to Explainability", type="primary", use_container_width=True):
            st.session_state.current_step = 8
            st.rerun()


# ─────────────────────────────────────────────
# STEP 8: Explainability
# ─────────────────────────────────────────────
def render_explainability():
    st.markdown("""
    <div class='step-header'>
        <h3>💡 Step 8 — Model Explainability</h3>
        <p>Feature importance, SHAP values, and individual prediction reasoning</p>
    </div>
    """, unsafe_allow_html=True)

    pipeline = st.session_state.trained_pipeline
    X_test = st.session_state.get("X_test_engineered")
    if X_test is None:
        X_test = st.session_state.X_test
    y_test = st.session_state.y_test
    y_proba = st.session_state.y_proba_test
    metrics = st.session_state.eval_metrics or {}

    if pipeline is None:
        st.warning("Please complete model training first.")
        return

    tabs = st.tabs(["📊 Feature Importance", "🔬 SHAP Analysis", "🔍 Prediction Reasoning", "📋 Summary"])

    with tabs[0]:
        st.markdown("#### 📊 Feature Importance")
        with st.spinner("Extracting feature importance with real column names..."):
            # extract_feature_importance now resolves names from the fitted preprocessor internally
            importance_df = extract_feature_importance(pipeline)
            st.session_state.importance_df = importance_df

        if importance_df is not None and not importance_df.empty:
            st.success(f"✅ Extracted importance for **{len(importance_df)} features** with real column names.")
            top_n = st.slider("Show top N features", 5, min(50, len(importance_df)), 15, 5, key="imp_topn")
            fig = plot_feature_importance_bar(importance_df, top_n=top_n)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(importance_df.head(top_n + 5), use_container_width=True)
            df_to_csv_download(importance_df, "feature_importance.csv")
        else:
            st.info("Feature importance not available for this model type.")

    with tabs[1]:
        st.markdown("#### 🔬 SHAP Values")
        st.info("SHAP (SHapley Additive exPlanations) shows each feature's contribution to each prediction using real feature names.")

        max_shap_samples = st.slider("Samples for SHAP analysis", 50, 300, 150, 50, key="shap_samp")

        if st.button("▶ Compute SHAP Values", use_container_width=True):
            with st.spinner("Computing SHAP values... (this may take a moment)"):
                shap_result = compute_shap_values(pipeline, X_test, max_samples=max_shap_samples)
                st.session_state.shap_result = shap_result

            if shap_result is not None:
                _, shap_values, X_df, names = shap_result
                st.success(f"✅ SHAP values computed for {len(names)} features!")
                fig = plot_shap_summary_plotly(shap_values, X_df)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("SHAP computation failed or not supported for this model. Try Feature Importance tab.")

        elif st.session_state.shap_result is not None:
            _, shap_values, X_df, names = st.session_state.shap_result
            fig = plot_shap_summary_plotly(shap_values, X_df)
            st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        st.markdown("#### 🔍 Individual Prediction Reasoning")
        st.info("Inspect exactly why a specific customer was classified as risky or safe — with real feature names.")

        shap_result = st.session_state.shap_result
        if shap_result is None:
            st.warning("Please compute SHAP values first (in the SHAP Analysis tab).")
        else:
            _, shap_values, X_df, names = shap_result
            n = len(X_df)
            sample_idx = st.number_input("Customer index (row number)", min_value=0, max_value=n - 1, value=0)

            if y_proba is not None and sample_idx < len(y_proba):
                threshold = getattr(st.session_state, "decision_threshold", 0.5)
                reasoning = generate_prediction_reasoning(
                    shap_values, X_df,
                    y_proba[:n], sample_idx, threshold
                )
                st.markdown(reasoning)

                fig = plot_shap_waterfall_single(shap_values, X_df, sample_idx)
                st.plotly_chart(fig, use_container_width=True)

                # Show raw feature values
                with st.expander("🔎 Raw Feature Values for This Customer"):
                    row_data = X_df.iloc[sample_idx].reset_index()
                    row_data.columns = ["Feature", "Value"]
                    st.dataframe(row_data, use_container_width=True)

    with tabs[3]:
        st.markdown("#### 📋 Model Performance Summary")
        importance_df = st.session_state.importance_df
        summary = generate_model_summary(metrics, importance_df, st.session_state.task_type)
        st.markdown(summary)

        st.divider()
        st.markdown("### 💾 Final Exports")
        dc1, dc2, dc3 = st.columns(3)

        with dc1:
            model_to_download(pipeline, "final_credit_risk_model.pkl")
        with dc2:
            X_final = _full_engineered_X()
            if X_final is None:
                X_final = st.session_state.X_engineered if st.session_state.X_engineered is not None else st.session_state.X
            _y_final = _full_engineered_y()
            if X_final is not None and _y_final is not None:
                processed_df = X_final.copy()
                processed_df[st.session_state.target_col] = _y_final.reindex(X_final.index).values
                df_to_csv_download(processed_df, "processed_dataset.csv")
        with dc3:
            if importance_df is not None:
                df_to_csv_download(importance_df, "feature_importance.csv")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀ Back to Evaluation", use_container_width=True):
            st.session_state.current_step = 7
            st.rerun()
    with col2:
        st.success("✅ PD pipeline complete. The **💧 LGD Model** tab is now unlocked — "
                   "switch to it (above) to build the LGD model, then the **💳 EAD Model** tab.")


# ─────────────────────────────────────────────
# Model Validation Workspace — Helpers & Stages
# ─────────────────────────────────────────────

def _render_val_stage_stub(stage_num: int, icon: str, title: str, framework: str, description: str):
    import html as _html
    st.markdown(
        f"<div style='background:#1e293b;border:1px solid #334155;border-radius:10px;"
        f"padding:2rem;margin:1rem 0;'>"
        f"<div style='display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;'>"
        f"<span style='font-size:2rem;'>{icon}</span>"
        f"<div>"
        f"<div style='color:#e2e8f0;font-weight:700;font-size:1.1rem;'>Stage {stage_num}: {_html.escape(title)}</div>"
        f"<div style='color:#6366f1;font-size:0.8rem;font-weight:600;'>{_html.escape(framework)}</div>"
        f"</div>"
        f"</div>"
        f"<div style='color:#94a3b8;font-size:0.9rem;line-height:1.6;'>{_html.escape(description)}</div>"
        f"<div style='margin-top:1.5rem;padding:0.75rem 1rem;background:#0f172a;border-radius:6px;"
        f"border:1px dashed #475569;color:#475569;font-size:0.85rem;text-align:center;'>"
        f"🚧 Under Construction — available in next sprint</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if stage_num < 8:
        next_stage = stage_num + 1
        st.markdown("<br>", unsafe_allow_html=True)
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            if st.button(
                f"▶️ Proceed to Stage {next_stage}",
                type="primary",
                use_container_width=True,
                key=f"proceed_to_stage{next_stage}",
            ):
                st.session_state["val_step"] = next_stage
                st.rerun()


def render_val_intake():
    """Stage 1 — Model Intake & Governance"""
    import html as _html

    # ── Demo Data Section ──────────────────────────────────────────────────────
    st.markdown("""
    <div style='background:#1e293b;border:1px solid #6366f133;
                border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.5rem;'>
        <div style='color:#6366f1;font-weight:700;font-size:1rem;margin-bottom:0.3rem;'>
            🧪 Demo Mode — Use Pre-loaded Test Submissions
        </div>
        <div style='color:#64748b;font-size:0.82rem;'>
            Load a realistic model submission instantly — no uploads needed.
            Use Demo A for a clean well-documented submission,
            Demo B for a flawed submission with regulatory violations.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _dcol1, _dcol2, _dcol3 = st.columns([1, 1, 2])
    with _dcol1:
        if st.button(
            "✅ Demo A — Clean Submission",
            use_container_width=True,
            key="demo_clean_btn",
            help="Loads a well-documented PD model. Most checks pass.",
        ):
            try:
                _ddf = pd.read_csv(os.path.join(DEMO_DATA_DIR, "clean_portfolio.csv"))
                with open(os.path.join(DEMO_DATA_DIR, "clean_mdd.txt"), "r", encoding="utf-8") as _f:
                    _demo_mdd = _f.read()
                st.session_state["val_df"]                     = _ddf
                st.session_state["val_dv_results"]             = None
                st.session_state["val_agent2_results"]         = None
                st.session_state["val_agent2"]                 = None
                st.session_state["val_agent2_instance"]        = None
                st.session_state["val_replicated_importances"] = {}
                st.session_state["val_intake_data"]            = DEMO_INTAKE_CLEAN
                st.session_state["val_demo_mode"]      = "clean"
                st.session_state["val_mdd_text"]       = _demo_mdd
                st.session_state["val_intake_json"]    = DEMO_INTAKE_CLEAN
                st.session_state["val_mdd_reported_metrics"] = {
                    "roc_auc": 0.82, "gini": 0.64, "ks": 0.58,
                    "cv_mean_auc": 0.80, "accuracy": 0.85,
                    "precision": 0.72, "recall": 0.71, "f1": 0.72,
                }
                # Pre-set replication widget selections so they auto-populate
                st.session_state["rep_target_col"] = DEMO_INTAKE_CLEAN["target_col"]
                st.session_state["rep_model_name"] = DEMO_INTAKE_CLEAN["algorithm"]
                with open(os.path.join(DEMO_DATA_DIR, "clean_params.json"), "r", encoding="utf-8") as _pf:
                    st.session_state["val_hyperparams"] = json.load(_pf)
                st.session_state["val_independence"]   = True
                st.session_state["val_scope"]          = True
                st.session_state["val_demo_df_loaded"]  = True
                st.session_state["val_demo_mdd_loaded"] = True
                st.session_state["val_demo_checks"]     = True
                st.session_state["val_demo_attestation"] = True
                st.session_state["chk_inventory"]      = True
                st.session_state["chk_tier"]           = True
                st.session_state["chk_artifacts"]      = True
                st.session_state["chk_prev_findings"]  = True
                st.session_state["chk_reg_scope"]      = True
                st.session_state["chk_independence"]   = True
                st.session_state["chk_plan_approved"]  = True
                st.session_state["chk_attestation"]    = True
                st.session_state["vi_model_name"]      = DEMO_INTAKE_CLEAN["model_name"]
                st.session_state["vi_team"]            = DEMO_INTAKE_CLEAN["owning_team"]
                st.session_state["vi_model_owner"]     = DEMO_INTAKE_CLEAN["model_owner"]
                st.session_state["vi_reviewer"]        = DEMO_INTAKE_CLEAN["lead_validator"]
                st.session_state["vi_version"]         = DEMO_INTAKE_CLEAN["model_version"]
                st.session_state["vi_purpose"]         = DEMO_INTAKE_CLEAN["model_purpose"]
                st.session_state["vi_model_type"]      = DEMO_INTAKE_CLEAN["model_type"]
                st.session_state["vi_tier"]            = DEMO_INTAKE_CLEAN["model_tier"]
                st.success(f"✅ Demo A loaded — {_ddf.shape[0]:,} rows × {_ddf.shape[1]} columns")
                st.rerun()
            except FileNotFoundError:
                st.error("Demo files not found. Make sure demo_data/ folder exists with clean_portfolio.csv and clean_mdd.txt")

    with _dcol2:
        if st.button(
            "🔴 Demo B — Flawed Submission",
            use_container_width=True,
            key="demo_flawed_btn",
            help="Loads a poorly documented submission. Expect multiple FAILs.",
        ):
            try:
                _ddf = pd.read_csv(os.path.join(DEMO_DATA_DIR, "flawed_portfolio.csv"))
                with open(os.path.join(DEMO_DATA_DIR, "flawed_mdd.txt"), "r", encoding="utf-8") as _f:
                    _demo_mdd = _f.read()
                st.session_state["val_df"]                     = _ddf
                st.session_state["val_dv_results"]             = None
                st.session_state["val_agent2_results"]         = None
                st.session_state["val_agent2"]                 = None
                st.session_state["val_agent2_instance"]        = None
                st.session_state["val_replicated_importances"] = {}
                st.session_state["val_intake_data"]            = DEMO_INTAKE_FLAWED
                st.session_state["val_demo_mode"]      = "flawed"
                st.session_state["val_mdd_text"]       = _demo_mdd
                st.session_state["val_intake_json"]    = DEMO_INTAKE_FLAWED
                st.session_state["val_mdd_reported_metrics"] = {
                    "roc_auc": 0.78, "gini": 0.56, "ks": 0.48,
                    "cv_mean_auc": 0.73, "accuracy": 0.79,
                    "precision": 0.61, "recall": 0.72, "f1": 0.65,
                }
                # Pre-set replication widget selections so they auto-populate
                st.session_state["rep_target_col"] = DEMO_INTAKE_FLAWED["target_col"]
                st.session_state["rep_model_name"] = DEMO_INTAKE_FLAWED["algorithm"]
                with open(os.path.join(DEMO_DATA_DIR, "flawed_params.json"), "r", encoding="utf-8") as _pf:
                    st.session_state["val_hyperparams"] = json.load(_pf)
                st.session_state["val_independence"]   = True
                st.session_state["val_scope"]          = True
                st.session_state["val_demo_df_loaded"]  = True
                st.session_state["val_demo_mdd_loaded"] = True
                st.session_state["val_demo_checks"]     = True
                st.session_state["val_demo_attestation"] = True
                st.session_state["chk_inventory"]      = True
                st.session_state["chk_tier"]           = True
                st.session_state["chk_artifacts"]      = True
                st.session_state["chk_prev_findings"]  = True
                st.session_state["chk_reg_scope"]      = True
                st.session_state["chk_independence"]   = True
                st.session_state["chk_plan_approved"]  = True
                st.session_state["chk_attestation"]    = True
                st.session_state["vi_model_name"]      = DEMO_INTAKE_FLAWED["model_name"]
                st.session_state["vi_team"]            = DEMO_INTAKE_FLAWED["owning_team"]
                st.session_state["vi_model_owner"]     = DEMO_INTAKE_FLAWED["model_owner"]
                st.session_state["vi_reviewer"]        = DEMO_INTAKE_FLAWED["lead_validator"]
                st.session_state["vi_version"]         = DEMO_INTAKE_FLAWED["model_version"]
                st.session_state["vi_purpose"]         = DEMO_INTAKE_FLAWED["model_purpose"]
                st.session_state["vi_model_type"]      = DEMO_INTAKE_FLAWED["model_type"]
                st.session_state["vi_tier"]            = DEMO_INTAKE_FLAWED["model_tier"]
                st.warning(f"⚠️ Demo B loaded — {_ddf.shape[0]:,} rows × {_ddf.shape[1]} columns. Multiple violations expected.")
                st.rerun()
            except FileNotFoundError:
                st.error("Demo files not found. Make sure demo_data/ folder exists with flawed_portfolio.csv and flawed_mdd.txt")

    with _dcol3:
        _demo_mode = st.session_state.get("val_demo_mode")
        if _demo_mode == "clean":
            st.markdown("""
            <div style='background:#071a0e;border:1px solid #10b981;border-radius:8px;
                        padding:0.6rem 1rem;font-size:0.82rem;color:#10b981;'>
                ✅ <b>Demo A active</b> — Clean submission with macro variables,
                8-year history, no leakage, complete MDD. Expect mostly PASS results.
            </div>""", unsafe_allow_html=True)
        elif _demo_mode == "flawed":
            st.markdown("""
            <div style='background:#1c0808;border:1px solid #ef4444;border-radius:8px;
                        padding:0.6rem 1rem;font-size:0.82rem;color:#ef4444;'>
                🔴 <b>Demo B active</b> — Flawed submission with target leakage
                (recovery_amount, write_off_flag), duplicate rows, no macro variables,
                2-year history, vague MDD. Expect multiple FAILs.
            </div>""", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1e293b;margin:1rem 0'>", unsafe_allow_html=True)

    st.markdown("### 📋 Stage 1 — Model Intake & Governance")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.9rem;'>Capture model metadata, upload all artifacts, "
        "and complete the governance attestation checklist before proceeding to automated validation stages.</p>",
        unsafe_allow_html=True,
    )

    # Section A: Model Metadata
    _demo = st.session_state.get("val_intake_data", {})
    st.markdown("#### 🏷️ Section A — Model Metadata")
    _mc1, _mc2 = st.columns(2)
    with _mc1:
        _name = st.text_input("Model Name", value=_demo.get("model_name", ""), key="vi_model_name")
        _team = st.text_input("Owning Team / Business Unit", value=_demo.get("owning_team", ""), key="vi_team")
    with _mc2:
        _owner    = st.text_input("Model Owner (name)", value=_demo.get("model_owner", ""), key="vi_model_owner")
        _reviewer = st.text_input("Lead Validator (name)", value=_demo.get("lead_validator", ""), key="vi_reviewer")

    _mc3, _mc4 = st.columns(2)
    _type_opts = ["PD (Probability of Default)", "LGD", "EAD", "ECL / IFRS 9", "Scorecard", "Other"]
    _tier_opts = ["Tier 1 — High Risk", "Tier 2 — Medium Risk", "Tier 3 — Low Risk"]
    _type_val  = _demo.get("model_type", "")
    _tier_val  = _demo.get("model_tier", "")
    _type_idx  = _type_opts.index(_type_val) if _type_val in _type_opts else 0
    _tier_idx  = _tier_opts.index(_tier_val) if _tier_val in _tier_opts else 0
    with _mc3:
        _model_type = st.selectbox("Model Type", _type_opts, index=_type_idx, key="vi_model_type")
        _tier       = st.selectbox("Model Tier", _tier_opts, index=_tier_idx, key="vi_tier")
    with _mc4:
        _version     = st.text_input("Model Version", value=_demo.get("model_version", ""), placeholder="e.g. v2.1.0", key="vi_version")
        _review_date = st.date_input("Validation Start Date", key="vi_review_date")

    st.text_area(
        "Model Purpose & Scope",
        value=_demo.get("model_purpose", ""),
        placeholder="Describe what the model is used for, the portfolio it covers, and any constraints.",
        height=90,
        key="vi_purpose",
    )

    # Section B: Artifact Upload
    st.markdown("#### 📁 Section B — Artifact Upload")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;'>Upload all model artifacts below. "
        "The dataset uploaded here is used for automated checks in Stage 2.</p>",
        unsafe_allow_html=True,
    )

    _ub1, _ub2 = st.columns(2)
    with _ub1:
        _val_file        = st.file_uploader("📊 Validation Dataset (CSV / XLSX) *", type=["csv", "xlsx"], key="val_dataset")
        _mdd_file        = st.file_uploader("📄 Model Development Document (PDF / DOCX / TXT) — reported metrics auto-extracted for Stage 4", type=["pdf", "docx", "txt"], key="val_mdd_upload")
        _code_file       = st.file_uploader("💻 Training Code / Scripts (ZIP / PY / IPYNB)", type=["zip", "py", "ipynb"], key="val_code_upload")
        _perf_file       = st.file_uploader("📈 Performance Report (PDF / XLSX)", type=["pdf", "xlsx"], key="val_perf_upload")
    with _ub2:
        _profile_file    = st.file_uploader("🔍 Data Profile / Dictionary (CSV / XLSX / PDF)", type=["csv", "xlsx", "pdf"], key="val_profile")
        _assumptions_file = st.file_uploader("📝 Assumptions & Limitations (PDF / DOCX)", type=["pdf", "docx"], key="val_assumptions")
        uploaded_params  = st.file_uploader("⚙️ Hyperparameter Config (JSON) *", type=["json"], key="val_hyperparams_upload")

    # Load dataset into session state when uploaded (only the dataset needs parsing)
    if _val_file is not None:
        try:
            if _val_file.name.endswith(".csv"):
                _loaded = pd.read_csv(_val_file)
            else:
                _loaded = pd.read_excel(_val_file, engine="openpyxl")
            st.session_state["val_df"] = _loaded
            st.success(f"✅ Dataset loaded — {_loaded.shape[0]:,} rows × {_loaded.shape[1]} columns")
        except Exception as _e:
            st.error(f"Error reading dataset: {_e}")

    # Parse the MDD here so its text is the single source of truth shared with
    # Stage 3 (Conceptual Soundness) and Stage 4 (Model Replication). The reported
    # performance metrics are pre-extracted now so Stage 4 needs no second upload.
    # Guarded by filename so a large PDF is not re-parsed on every Streamlit rerun.
    if _mdd_file is not None and st.session_state.get("_val_mdd_parsed_name") != _mdd_file.name:
        try:
            _mdd_parsed = parse_mdd_file(_mdd_file)
            st.session_state["_val_mdd_parsed_name"] = _mdd_file.name
            if _mdd_parsed.strip():
                st.session_state["val_mdd_text"] = _mdd_parsed
                _mm = {k: v for k, v in extract_metrics_from_mdd(_mdd_parsed).items() if v is not None}
                st.session_state["val_mdd_reported_metrics"] = _mm
                if _mm:
                    st.success(
                        f"✅ MDD parsed — {len(_mdd_parsed):,} characters; "
                        f"{len(_mm)} reported metric(s) detected and ready for Stage 4: "
                        + ", ".join(sorted(_mm.keys())) + "."
                    )
                else:
                    st.success(
                        f"✅ MDD parsed — {len(_mdd_parsed):,} characters. No performance "
                        "metrics auto-detected; you can add them in Stage 4 if needed."
                    )
            else:
                st.warning(
                    "MDD uploaded but no text could be extracted (scanned PDF?). "
                    "Upload a text-based PDF/DOCX/TXT, or enter metrics manually in Stage 4."
                )
        except Exception as _e:
            st.error(f"Could not parse MDD: {_e}")
    elif (st.session_state.get("val_mdd_text", "") or "").strip():
        _mm_cached = st.session_state.get("val_mdd_reported_metrics") or {}
        st.caption(
            f"📄 MDD on file — {len(st.session_state['val_mdd_text']):,} characters"
            + (f"; {len(_mm_cached)} reported metric(s) ready for Stage 4." if _mm_cached else ".")
        )

    # Parse uploaded hyperparameter config JSON
    if uploaded_params is not None:
        try:
            uploaded_params.seek(0)
            hyperparams = json.load(uploaded_params)
            st.session_state["val_hyperparams"] = hyperparams
            st.success(f"✅ Hyperparameter config loaded — {len(hyperparams)} parameters found")
            st.json(hyperparams)
        except Exception as _e:
            st.error(f"Could not parse hyperparameter config: {_e}")
    elif st.session_state.get("val_hyperparams"):
        _hp = st.session_state["val_hyperparams"]
        st.caption(f"⚙️ Hyperparameter config on file — {len(_hp)} parameters: {', '.join(list(_hp.keys())[:5])}{'…' if len(_hp) > 5 else ''}")

    # Artifact completeness checklist
    _artifact_specs = [
        ("Submitted Dataset",
         st.session_state.get("val_df") is not None or st.session_state.get("val_demo_df_loaded", False),
         "REQUIRED", "Needed for Stages 2–5"),
        ("Data Profile Report",          _profile_file is not None,                  "OPTIONAL",  "Needed for Stage 2 — Check 2.7"),
        ("Model Dev Document (MDD)",
         _mdd_file is not None or st.session_state.get("val_demo_mdd_loaded", False),
         "REQUIRED",  "Needed for Stage 1 governance checks"),
        ("Assumptions & Limitations",    _assumptions_file is not None,              "OPTIONAL",  "Needed for Stage 3"),
        ("Training Code / Scripts",      _code_file is not None,                     "REQUIRED",  "Needed for Stage 4 — Model Replication"),
        ("Hyperparameter Config",        bool(st.session_state.get("val_hyperparams")), "REQUIRED",  "Needed for Stage 4 — Model Replication"),
        ("Performance Report",           _perf_file is not None,                     "OPTIONAL",  "Needed for Stage 5"),
    ]
    _required_ok  = all(ok for _, ok, req, _ in _artifact_specs if req == "REQUIRED")
    _ready_count  = sum(1 for _, ok, _, _ in _artifact_specs if ok)
    st.markdown(f"**Artifact Completeness: {_ready_count}/{len(_artifact_specs)}** — Required items: {'✅ All uploaded' if _required_ok else '❌ Some missing'}")
    _art_cols = st.columns(4)
    for _i, (_art_name, _art_ok, _art_req, _art_desc) in enumerate(_artifact_specs):
        _req_color = "#ef4444" if _art_req == "REQUIRED" else "#64748b"
        _art_cols[_i % 4].markdown(
            f"<div style='padding:0.35rem 0.5rem;"
            f"background:{'#071a0e' if _art_ok else '#1c0808'};"
            f"border-radius:4px;margin:0.15rem 0;font-size:0.78rem;'>"
            f"{'✅' if _art_ok else '❌'} <strong style='color:#e2e8f0;'>{_html.escape(_art_name)}</strong><br>"
            f"<span style='color:{_req_color};font-size:0.68rem;font-weight:600;'>{_art_req}</span> "
            f"<span style='color:#475569;font-size:0.68rem;'>{_html.escape(_art_desc)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Section C: Governance Checklist
    st.markdown("#### ☑️ Section C — Governance Attestation Checklist")
    chk_inventory     = st.checkbox("Model is registered in the model inventory",                        key="chk_inventory")
    chk_tier          = st.checkbox("Model risk tier has been formally assigned",                        key="chk_tier")
    chk_artifacts     = st.checkbox("Model developer has provided all required artifacts",               key="chk_artifacts")
    chk_prev_findings = st.checkbox("Previous validation findings (if any) have been reviewed",          key="chk_prev_findings")
    chk_reg_scope     = st.checkbox("Regulatory scope (IFRS 9 / SS1/23 / SS11/13) has been identified", key="chk_reg_scope")
    chk_independence  = st.checkbox("Independent validation team has no conflict of interest",           key="chk_independence")
    chk_plan_approved = st.checkbox("Validation plan has been approved by the Head of Model Risk",      key="chk_plan_approved")
    _all_checked = all([chk_inventory, chk_tier, chk_artifacts, chk_prev_findings,
                        chk_reg_scope, chk_independence, chk_plan_approved])

    # Section D: Attestation & Submit
    st.markdown("#### ✍️ Section D — Validator Attestation")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;'>By clicking 'Submit Intake', you confirm that all "
        "information provided is accurate and the validation team is ready to proceed.</p>",
        unsafe_allow_html=True,
    )
    _attest = st.checkbox("I confirm the above information is accurate and complete", key="chk_attestation")

    _demo_active = st.session_state.get("val_demo_mode") is not None
    _gate_passed = _demo_active or (_attest and _all_checked)
    if st.button(
        "📋 Submit Intake & Proceed to Stage 2",
        type="primary",
        use_container_width=True,
        disabled=not _gate_passed,
    ):
        st.session_state["val_model_name"]  = _name
        st.session_state["val_model_owner"] = _owner
        # Preserve an MDD already parsed at upload (real submissions); only fall
        # back to the demo intake_data text when no MDD has been captured yet.
        _existing_mdd = st.session_state.get("val_mdd_text", "") or ""
        _intake_mdd = st.session_state.get("val_intake_data", {}).get("mdd_text", "") or ""
        st.session_state["val_mdd_text"] = _existing_mdd if _existing_mdd.strip() else _intake_mdd
        st.session_state["val_intake_json"] = st.session_state.get("val_intake_data", {})
        st.session_state["val_step"] = 2
        st.rerun()
    elif not _gate_passed:
        st.info("Complete all checklist items and the attestation to submit the intake.")


# ─────────────────────────────────────────────
# RAG Agent helpers — Model Validation Stages 2 & 3
# ─────────────────────────────────────────────

def _load_val_rag_rules(stage_filter: str | None = None) -> list[dict]:
    """
    Load qualitative MDD validation rules from rag_store/val_mdd_rules.json.

    These rules were extracted from regulatory documents by the RAG agent
    (val_rag_rule_extractor.py + val_build_rules.py) and represent what the
    MDD must contain or demonstrate.

    Agent 2b (colleague's agent) will cross-check these against the uploaded
    MDD and produce PASS / WARN / FAIL results; this function only surfaces
    the rules for informational display until Agent 2b runs.

    Args:
        stage_filter: "data" | "conceptual" | None (returns all)

    Returns:
        List of rule dicts, filtered by stage if requested.
    """
    import json
    from pathlib import Path

    # Deloitte-agent rules now drive the model-validation RAG layer too.
    rules_path = Path(__file__).resolve().parent / "rag_store" / "rules.json"
    if not rules_path.exists():
        return []
    # Map the legacy filter values onto the model-validation stage tags.
    _stage_map = {"data": "data_validation", "conceptual": "conceptual_soundness"}
    want = _stage_map.get(stage_filter, stage_filter)
    try:
        with rules_path.open(encoding="utf-8") as f:
            rules: list[dict] = json.load(f)
        # The panel shows the qualitative (non-auto-testable) rules; the testable
        # ones are evaluated via Agent2.check_for_validation() in the results.
        out = [r for r in rules if not r.get("checkable_against_data", False)]
        if want:
            out = [r for r in out if r.get("stage") == want]
        return out
    except Exception:
        return []


def _render_rag_rules_panel(rules: list[dict], panel_key: str = "rag") -> None:
    """
    Render the RAG-retrieved qualitative MDD rules as an informational panel.

    Each rule card shows the rule text, regulatory source/principle, expected
    MDD section, and the keywords Agent 2b will search for.  Status is shown
    as "PENDING AGENT 2b" until Agent 2b runs and replaces it with findings.

    Args:
        rules:     List of rule dicts from _load_val_rag_rules()
        panel_key: Unique key suffix for Streamlit widgets
    """
    import html as _html

    if not rules:
        st.info(
            "ℹ️ No qualitative rules found in rag_store/val_mdd_rules.json. "
            "Run `python build_rules.py` to seed the knowledge store with baseline rules, "
            "or `python build_rules.py --extract` to pull rules from the RAG agent."
        )
        return

    _SEV_COLOR = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
    _SEV_BG    = {"high": "#1c0808", "medium": "#1c1200", "low": "#071a0e"}
    _SEV_ICON  = {"high": "🔴",      "medium": "🟡",       "low": "🟢"}

    # Summary metrics
    _high   = sum(1 for r in rules if r.get("severity") == "high")
    _medium = sum(1 for r in rules if r.get("severity") == "medium")
    _low    = sum(1 for r in rules if r.get("severity") == "low")
    _rm1, _rm2, _rm3, _rm4 = st.columns(4)
    _rm1.metric("Rules from Knowledge Store", len(rules))
    _rm2.metric("🔴 High", _high)
    _rm3.metric("🟡 Medium", _medium)
    _rm4.metric("🟢 Low", _low)

    st.markdown(
        "<div style='padding:0.5rem 0.75rem;background:#0f172a;border:1px solid #334155;"
        "border-radius:6px;color:#94a3b8;font-size:0.8rem;margin-bottom:0.75rem;'>"
        "⏳ <strong style='color:#6366f1;'>Status: PENDING AGENT 2b</strong> — "
        "These rules have been retrieved from the regulatory knowledge store. "
        "Agent 2b will cross-check each rule against the uploaded MDD and replace "
        "this status with PASS / WARN / FAIL findings."
        "</div>",
        unsafe_allow_html=True,
    )

    # Sort: high → medium → low
    sorted_rules = sorted(
        rules,
        key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.get("severity", "low"), 9),
    )

    # Collapsible panel to keep the UI compact
    with st.expander(
        f"📋 View all {len(rules)} qualitative rules — awaiting Agent 2b",
        expanded=False,
    ):
        for rule in sorted_rules:
            sev    = rule.get("severity", "medium")
            border = _SEV_COLOR.get(sev, "#6366f1")
            bg     = _SEV_BG.get(sev, "#1e293b")
            icon   = _SEV_ICON.get(sev, "⚪")

            rule_id    = _html.escape(str(rule.get("id", "?")))
            rule_text  = _html.escape(str(rule.get("rule", rule.get("rule_text", ""))))
            source     = _html.escape(str(rule.get("source", "?")))
            principle  = _html.escape(str(rule.get("principle", "")))
            hint       = _html.escape(str(rule.get("mdd_section_hint", "")))
            keywords   = rule.get("keywords", [])
            kw_str     = _html.escape(", ".join(str(k) for k in keywords[:6]))
            suggestion = _html.escape(str(rule.get("suggestion", "")))

            st.markdown(
                f"<div style='border-left:3px solid {border};padding:0.6rem 1rem;"
                f"margin:0.35rem 0;background:{bg};border-radius:0 6px 6px 0;'>"
                f"<div style='color:#f1f5f9;font-size:0.88rem;font-weight:600;line-height:1.4;'>"
                f"{icon} <span style='color:#94a3b8;'>[{rule_id}]</span> {rule_text}"
                f"</div>"
                f"<div style='color:#94a3b8;font-size:0.76rem;margin-top:0.25rem;'>"
                f"📋 {source} — {principle}"
                f"{'  ·  📂 ' + hint if hint else ''}"
                f"</div>"
                f"{'<div style=\"color:#64748b;font-size:0.75rem;margin-top:0.15rem;\">🔑 Keywords Agent 2b will match: ' + kw_str + '</div>' if kw_str else ''}"
                f"<div style='color:#475569;font-size:0.76rem;margin-top:0.15rem;'>"
                f"💡 {suggestion}"
                f"</div>"
                f"<div style='color:#334155;font-size:0.72rem;margin-top:0.2rem;font-style:italic;'>"
                f"⏳ Agent 2b: PENDING MDD CROSS-CHECK"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


def render_val_data_validation():
    """Stage 2 — Data Validation (10 automated regulatory checks)"""
    import html as _html

    st.markdown("### 📂 Stage 2 — Data Validation")

    # Guard: require dataset uploaded in Stage 1
    _vdf = st.session_state.get("val_df")
    if _vdf is None:
        st.warning("⚠️ No dataset found. Please upload artifacts in Stage 1: Intake & Governance first.")
        return

    _profile_loaded = st.session_state.get("val_profile") is not None
    st.success(f"✅ Dataset ready — {_vdf.shape[0]:,} rows × {_vdf.shape[1]} columns")

    if st.button("▶️ Run Data Validation Checks", type="primary", use_container_width=True):
        _df = _vdf
        _results = []

        # 2.1 Row/Column Reconciliation
        _results.append({
            "check_id": "2.1", "title": "Row/Column Reconciliation",
            "source": "SS11/13", "principle": "§10.4", "severity": "high",
            "status": "PASS",
            "observed": f"{len(_df)} rows × {_df.shape[1]} cols",
            "threshold": "Dataset must be loadable",
            "detail": "Dataset loaded successfully. Cross-reference against developer's reported row count manually.",
        })

        # 2.2 Missing Data Rate
        _miss = _df.isna().mean()
        _worst_col = str(_miss.idxmax())
        _max_miss = float(_miss.max())
        _miss_status = "FAIL" if _max_miss > 0.20 else ("WARN" if _max_miss > 0.10 else "PASS")
        _results.append({
            "check_id": "2.2", "title": "Missing Data Rate",
            "source": "SS1/23", "principle": "P3.2", "severity": "high",
            "status": _miss_status,
            "observed": f"Max missing: {_max_miss:.1%} in column '{_worst_col}'",
            "threshold": "< 20% per column",
            "detail": "High missing rates introduce bias and undermine model stability. SS1/23 P3.2 requires evidence of appropriate treatment.",
        })

        # 2.3 Default Definition Consistency
        _def_kw = ["default", "bad", "charged_off", "write_off", "target", "label", "y", "dpd_90"]
        _tgt_cands = [c for c in _df.columns if any(k in c.lower() for k in _def_kw)]
        _results.append({
            "check_id": "2.3", "title": "Default Definition Consistency",
            "source": "IFRS 9", "principle": "B5.5.28", "severity": "high",
            "status": "WARN" if _tgt_cands else "FAIL",
            "observed": "Candidates: " + ", ".join(_tgt_cands) if _tgt_cands else "No candidate target column detected",
            "threshold": "Target column identifiable; 90-DPD definition confirmed",
            "detail": "Validator must confirm default = 90 DPD or document alternative with regulatory justification.",
        })

        # 2.4 Macro Variables Present
        _macro_kw = ["gdp", "unemployment", "hpi", "inflation", "rate", "macro", "cpi", "index"]
        _macro_cols = [c for c in _df.columns if any(k in c.lower() for k in _macro_kw)]
        _results.append({
            "check_id": "2.4", "title": "Macro Variables Present",
            "source": "IFRS 9", "principle": "B5.5.49", "severity": "medium",
            "status": "PASS" if _macro_cols else "FAIL",
            "observed": ", ".join(_macro_cols) if _macro_cols else "None detected",
            "threshold": "At least one macroeconomic variable required",
            "detail": "IFRS 9 B5.5.49 requires forward-looking macroeconomic information. If absent, model developer must justify.",
        })

        # 2.5 Historical Coverage ≥ 5 Years
        _date_col_v = None
        for _c in _df.columns:
            if pd.api.types.is_datetime64_any_dtype(_df[_c]):
                _date_col_v = _c
                break
        if _date_col_v is None:
            for _c in _df.select_dtypes(include=["object"]).columns:
                try:
                    _p = pd.to_datetime(_df[_c], errors="coerce")
                    if _p.notna().sum() / max(len(_df), 1) > 0.80:
                        _date_col_v = _c
                        break
                except Exception:
                    pass
        if _date_col_v:
            _pdates = pd.to_datetime(_df[_date_col_v], errors="coerce").dropna()
            _yrs = (_pdates.max() - _pdates.min()).days / 365.25
            _hist_status = "PASS" if _yrs >= 5 else ("WARN" if _yrs >= 3 else "FAIL")
            _hist_obs = f"{_yrs:.1f} years in column '{_date_col_v}'"
        else:
            _hist_status = "WARN"
            _hist_obs = "No date column detected — coverage cannot be verified automatically."
        _results.append({
            "check_id": "2.5", "title": "Historical Coverage ≥ 5 Years",
            "source": "SS11/13", "principle": "§10.1", "severity": "high",
            "status": _hist_status, "observed": _hist_obs,
            "threshold": "≥ 5 years preferred; ≥ 3 years minimum",
            "detail": "SS11/13 §10.1 requires sufficient historical data covering at least one economic cycle.",
        })

        # 2.6 Sampling Strategy Documented
        _results.append({
            "check_id": "2.6", "title": "Sampling Strategy Documented",
            "source": "SS1/23", "principle": "P3.2", "severity": "medium",
            "status": "WARN",
            "observed": "Manual review required — cannot be automated.",
            "threshold": "Sampling methodology documented in MDD",
            "detail": "Validator must confirm sampling methodology in submitted MDD. Check for: survivorship bias, selection bias, time-period bias.",
        })

        # 2.7 Transformations Documented
        _results.append({
            "check_id": "2.7", "title": "Transformations Documented",
            "source": "SS1/23", "principle": "P3.5", "severity": "medium",
            "status": "PASS" if _profile_loaded else "WARN",
            "observed": "Profile report uploaded" if _profile_loaded else "No profile report submitted.",
            "threshold": "Data dictionary / profile report must be submitted",
            "detail": "If data dictionary/profile was not submitted, request it from the model developer.",
        })

        # 2.8 Target Leakage Detection
        _leak_kw = ["recovery", "loss_given", "write", "charged", "resolved", "post_default", "lgd", "ead"]
        _tgt_col_v = None
        for _c in _df.columns:
            if any(k in _c.lower() for k in ["default", "target", "label", "bad"]):
                if _df[_c].nunique() <= 2:
                    _tgt_col_v = _c
                    break
        if _tgt_col_v is None:
            for _c in _df.columns:
                if set(_df[_c].dropna().unique()).issubset({0, 1, 0.0, 1.0}):
                    _tgt_col_v = _c
                    break
        _kw_leak = [c for c in _df.columns if c != _tgt_col_v and any(k in c.lower() for k in _leak_kw)]
        _corr_leak = []
        if _tgt_col_v is not None:
            _tgt_num = pd.to_numeric(_df[_tgt_col_v], errors="coerce")
            if _tgt_num.notna().sum() >= 2:
                for _nc in _df.select_dtypes(include="number").columns:
                    if _nc == _tgt_col_v:
                        continue
                    try:
                        _cr = _df[_nc].corr(_tgt_num)
                        if pd.notna(_cr) and abs(_cr) > 0.95:
                            _corr_leak.append(_nc)
                    except Exception:
                        pass
        _all_leak = list(set(_kw_leak + _corr_leak))
        _results.append({
            "check_id": "2.8", "title": "Target Leakage Detection",
            "source": "SS1/23", "principle": "P3.5", "severity": "high",
            "status": "FAIL" if _all_leak else "PASS",
            "observed": ", ".join(_all_leak) if _all_leak else "No suspected leakage columns found",
            "threshold": "No post-default or high-correlation (>0.95) features",
            "detail": "Post-default features and near-perfect correlates with the target are likely leakage and must be excluded from the model.",
        })

        # 2.9 Duplicate Record Rate
        _dup_n = int(_df.duplicated().sum())
        _dup_rate = _dup_n / max(len(_df), 1)
        _dup_status = "FAIL" if _dup_rate > 0.01 else ("WARN" if _dup_rate > 0.001 else "PASS")
        _results.append({
            "check_id": "2.9", "title": "Duplicate Record Rate",
            "source": "SS1/23", "principle": "P3.2", "severity": "low",
            "status": _dup_status,
            "observed": f"{_dup_n} duplicates ({_dup_rate:.2%})",
            "threshold": "< 1%",
            "detail": "Duplicate records inflate effective sample size and may bias model estimates. Investigate and remove before training.",
        })

        # 2.10 Class Imbalance
        _bin_tgt = None
        for _c in _df.columns:
            if _df[_c].nunique() == 2 and set(_df[_c].dropna().unique()).issubset({0, 1, 0.0, 1.0}):
                _bin_tgt = _c
                break
        if _bin_tgt:
            _vc10 = _df[_bin_tgt].value_counts()
            _min_pct = float(_vc10.min() / _vc10.sum())
            _ratio_10 = float(_vc10.min() / _vc10.max())
            _imb10 = "FAIL" if _ratio_10 < 0.1 else ("WARN" if _ratio_10 < 0.33 else "PASS")
            _imb_obs = f"Minority class: {_min_pct:.1%} | Ratio: {_ratio_10:.2f}"
        else:
            _imb10 = "WARN"
            _imb_obs = "No binary target column detected automatically."
        _results.append({
            "check_id": "2.10", "title": "Class Imbalance",
            "source": "SS1/23", "principle": "P3.2", "severity": "medium",
            "status": _imb10, "observed": _imb_obs,
            "threshold": "> 0.33 (3:1 or better)",
            "detail": "Severe class imbalance requires explicit treatment (class weights, oversampling) documented in the MDD.",
        })

        # ── Agent 1 RAG rules — Stage 2 context ──────────────────────────────
        # ── RAG agent — quantitative rule checks + MDD keyword search ──
        _imbalance_ratio = (
            round(1.0 / _ratio_10, 2) if (_bin_tgt and _ratio_10 > 0) else 1.0
        )
        _del_a2 = _get_agent2()
        if _del_a2 is not None:
            # Quantitative checks from val_mdd_rules.json (checkable_against_data=True)
            _rag_findings = _del_a2.check_for_validation("data_validation", {
                "missing_rate":          _max_miss,
                "duplicate_rate":        _dup_rate,
                "n_rows":                len(_df),
                "class_imbalance_ratio": _imbalance_ratio,
            })
            _results.extend(_rag_findings)
            # Keyword-search cross-check against uploaded MDD (if available)
            _mdd_text = st.session_state.get("val_mdd_text", "")
            if _mdd_text:
                _kw_findings = _del_a2.check_mdd_keywords(_mdd_text, stage="data_validation")
                _results.extend(_kw_findings)

        st.session_state["val_dv_results"] = _results

        try:
            _va2_full = _get_val_agent2()
            if _va2_full is not None:
                st.session_state["val_agent2_results"] = _va2_full.run_all_checks(
                    val_df=_df,
                    intake_json=st.session_state.get("val_intake_json", {}),
                    mdd_text=st.session_state.get("val_mdd_text", ""),
                    hyperparams=st.session_state.get("val_hyperparams", {}),
                )
                st.session_state["val_agent2_instance"] = _va2_full
                st.session_state["val_replicated_importances"] = (
                    _va2_full.replicated_importances
                    if hasattr(_va2_full, "replicated_importances")
                    else {}
                )
        except Exception:
            st.session_state["val_agent2_results"] = None

    # Results display
    _dv_res = st.session_state.get("val_dv_results")
    if _dv_res:
        st.markdown("### 📊 Validation Results")

        _pass_n = sum(1 for r in _dv_res if r["status"] == "PASS")
        _warn_n = sum(1 for r in _dv_res if r["status"] == "WARN")
        _fail_n = sum(1 for r in _dv_res if r["status"] == "FAIL")
        _tot    = len(_dv_res)

        _sm1, _sm2, _sm3, _sm4 = st.columns(4)
        _sm1.metric("Total Checks", _tot)
        _sm2.metric("✅ PASS", _pass_n)
        _sm3.metric("🟡 WARN", _warn_n)
        _sm4.metric("🔴 FAIL", _fail_n)
        st.progress(_pass_n / _tot)

        _S_COL = {"PASS": "#10b981", "WARN": "#f59e0b", "FAIL": "#ef4444"}
        _S_BG  = {"PASS": "#071a0e", "WARN": "#1c1200", "FAIL": "#1c0808"}
        _S_ICN = {"PASS": "✅",      "WARN": "🟡",       "FAIL": "🔴"}
        _V_COL = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}

        # Split into threshold checks vs RAG agent flags.
        # Threshold checks have numeric check_ids like "2.1", "2.10".
        # RAG agent flags have IDs like "V13", "DV-001" — non-numeric prefixes.
        import re as _re
        def _is_threshold_check(r):
            cid = str(r.get("check_id", r.get("rule_id", "")))
            return bool(_re.match(r"^\d+\.\d+$", cid))
        _thresh_res = [r for r in _dv_res if _is_threshold_check(r)]
        _rag_res    = [r for r in _dv_res if not _is_threshold_check(r)]

        _col_thresh, _col_rag = st.columns(2)

        with _col_thresh:
            st.markdown(
                "<div style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
                "padding:0.6rem 1rem;margin-bottom:0.75rem;'>"
                "<div style='color:#6366f1;font-weight:700;font-size:0.9rem;'>📐 Recommended Threshold Checks</div>"
                "<div style='color:#64748b;font-size:0.75rem;'>Quantitative checks against regulatory thresholds</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            for _r in _thresh_res:
                _st  = _r["status"]
                _sev = _r.get("severity", "medium")
                _border = _S_COL.get(_st, "#6366f1")
                _bg     = _S_BG.get(_st, "#1e293b")
                _s_icn  = _S_ICN.get(_st, "⚪")
                _sev_c  = _V_COL.get(_sev, "#6366f1")
                st.markdown(
                    f"<div style='border-left:3px solid {_border};padding:0.75rem 1rem;"
                    f"margin:0.4rem 0;background:{_bg};border-radius:0 6px 6px 0;'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
                    f"<div style='color:#f1f5f9;font-size:0.92rem;font-weight:600;line-height:1.4;'>"
                    f"{_s_icn} <span style='color:#94a3b8;'>[{_html.escape(str(_r['check_id']))}]</span> "
                    f"{_html.escape(str(_r['title']))}"
                    f"<span style='background:{_sev_c};color:#0f172a;font-size:0.7rem;font-weight:700;"
                    f"padding:0.1rem 0.5rem;border-radius:10px;margin-left:0.5rem;'>"
                    f"{_html.escape(_sev.upper())}</span></div>"
                    f"<span style='background:{_border};color:#0f172a;font-size:0.78rem;font-weight:700;"
                    f"padding:0.15rem 0.6rem;border-radius:4px;white-space:nowrap;'>{_st}</span>"
                f"</div>"
                f"<div style='color:#94a3b8;font-size:0.78rem;margin-top:0.3rem;'>"
                f"📋 {_html.escape(str(_r.get('source', '')))} — {_html.escape(str(_r.get('principle', '')))}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.25rem;'>"
                f"📊 Observed: <code style='color:#e2e8f0;'>{_html.escape(str(_r.get('observed', '')))}</code></div>"
                f"<div style='color:#475569;font-size:0.78rem;margin-top:0.15rem;'>"
                f"📐 Threshold: {_html.escape(str(_r.get('threshold', '')))}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.2rem;'>"
                f"💡 {_html.escape(str(_r.get('detail', '')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with _col_rag:
            st.markdown(
                "<div style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
                "padding:0.6rem 1rem;margin-bottom:0.75rem;'>"
                "<div style='color:#a78bfa;font-weight:700;font-size:0.9rem;'>🤖 RAG Agent Rules</div>"
                "<div style='color:#64748b;font-size:0.75rem;'>Regulatory rules fetched from knowledge store (SS1/23, SS11/13, IFRS 9)</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            if not _rag_res:
                st.info("No RAG agent flags generated for this dataset.")
            for _r in _rag_res:
                _sev    = _r.get("severity", "low")
                _border = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}.get(_sev, "#6366f1")
                _bg     = {"high": "#1c0808", "medium": "#1c1200", "low": "#071a0e"}.get(_sev, "#1e293b")
                _icon   = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(_sev, "⚪")
                _rule_id    = _html.escape(str(_r.get("rule_id", _r.get("check_id", "?"))))
                _flag_text  = _html.escape(str(_r.get("flag", _r.get("title", ""))))
                _suggestion = _html.escape(str(_r.get("suggestion", _r.get("detail", ""))))
                _source     = _html.escape(str(_r.get("source", "")))
                _principle  = _html.escape(str(_r.get("principle", "")))
                _ov         = _r.get("observed_value", _r.get("observed"))
                _obs_row    = (
                    f"<div style='color:#94a3b8;font-size:0.78rem;margin-top:0.2rem;'>"
                    f"📊 Observed: <code style='color:#e2e8f0;'>{_html.escape(str(_ov))}</code></div>"
                    if _ov is not None else ""
                )
                _nv_tag = (
                    "<span style='color:#64748b;font-size:0.75rem;font-style:italic;'> · not verifiable with current data</span>"
                    if _r.get("not_verifiable") else ""
                )
                st.markdown(
                    f"<div style='border-left:3px solid {_border};padding:0.6rem 1rem;"
                    f"margin:0.35rem 0;background:{_bg};border-radius:0 6px 6px 0;'>"
                    f"<div style='color:#f1f5f9;font-size:0.88rem;font-weight:600;line-height:1.4;'>"
                    f"{_icon} <span style='color:#94a3b8;'>[{_rule_id}]</span> {_flag_text}{_nv_tag}</div>"
                    f"{_obs_row}"
                    f"<div style='color:#94a3b8;font-size:0.82rem;margin-top:0.25rem;line-height:1.4;'>"
                    f"💡 {_suggestion}</div>"
                    f"<div style='color:#475569;font-size:0.75rem;margin-top:0.15rem;'>"
                    f"📋 {_source} — {_principle}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.divider()
        _csv_rows = [{
            "Check ID": r.get("check_id", ""), "Title": r.get("title", r.get("flag", "")),
            "Regulatory Source": r.get("source", ""), "Principle": r.get("principle", ""),
            "Severity": r.get("severity", ""), "Status": r.get("status", ""),
            "Observed": r.get("observed", ""), "Threshold": r.get("threshold", ""),
            "Detail": r.get("detail", ""),
        } for r in _dv_res]
        st.download_button(
            "📥 Download Data Validation Report (CSV)",
            data=pd.DataFrame(_csv_rows).to_csv(index=False).encode("utf-8"),
            file_name="data_validation_report.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_dv_report",
        )

    st.markdown("<br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        if st.button(
            "▶️ Proceed to Stage 3: Conceptual Soundness",
            type="primary",
            use_container_width=True,
            key="proceed_to_stage3",
        ):
            st.session_state["val_step"] = 3
            st.rerun()


def render_val_conceptual_soundness():
    """Stage 3 — Conceptual Soundness Review (SS1/23 P2 · SS11/13 §9)"""
    import html as _html

    st.markdown("### 🧠 Stage 3 — Conceptual Soundness Review")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.87rem;'>"
        "SS1/23 Principle 2 · SS11/13 §9 · IFRS 9 B5.5.50"
        "</p>",
        unsafe_allow_html=True,
    )

    df = st.session_state.get("val_df")
    mdd_text = st.session_state.get("val_mdd_text", "")
    intake_json = st.session_state.get("val_intake_json", {})

    if not mdd_text and df is None:
        st.warning(
            "⚠️ No artifacts found. Please complete "
            "Stage 1 — Intake & Governance first."
        )
        if st.button("← Go to Stage 1", key="s3_back"):
            st.session_state["val_step"] = 1
            st.rerun()
        return

    if mdd_text:
        st.success("✅ MDD loaded from Stage 1 intake.")
        with st.expander("📄 MDD preview (first 500 chars)"):
            st.text(mdd_text[:500])

    # Auto-detect from submitted dataset
    auto_target = None
    auto_features = []
    auto_model_type = intake_json.get("methodology", "Not specified")
    auto_prot_cols = []

    if df is not None:
        default_kw = ["default", "bad", "target", "label", "is_bad", "def_flag"]
        auto_target = next(
            (c for c in df.columns if any(k in c.lower() for k in default_kw)),
            df.columns[-1] if len(df.columns) > 0 else None,
        )
        exclude_kw = ["id", "customer", "loan_id", "origination", "date"]
        auto_features = [
            c for c in df.select_dtypes(include=["number"]).columns
            if c != auto_target and not any(k in c.lower() for k in exclude_kw)
        ]
        _prot_kw = ["age", "gender", "sex", "ethnicity", "race", "nationality",
                    "marital", "religion", "disability"]
        auto_prot_cols = [c for c in df.columns if any(k in c.lower() for k in _prot_kw)]

        col1, col2, col3 = st.columns(3)
        col1.metric("Target Column", auto_target or "None")
        col2.metric("Feature Columns", len(auto_features))
        col3.metric("Model Type", (auto_model_type[:20] if auto_model_type else "N/A"))

        with st.expander("📊 Feature columns detected"):
            st.write(auto_features)

    if st.button(
        "▶️ Run Conceptual Soundness Checks",
        type="primary",
        use_container_width=True,
        key="run_s3_checks",
    ):
        try:
            _va2_s3 = _get_val_agent2()
            if _va2_s3 is None:
                from validation_agent2 import ValidationAgent2
                _va2_s3 = ValidationAgent2()
            _va2_s3.val_df = df
            _va2_s3.intake_json = intake_json
            _va2_s3.mdd_text = mdd_text.lower()
            _s3_results = list(_va2_s3.check_conceptual_soundness())

            # ── Agent 1 RAG rules — Stage 3 / feature context ────────────────
            _corr_max = 0.0
            if df is not None:
                try:
                    _num_s3 = df.select_dtypes(include=["number"])
                    if _num_s3.shape[1] >= 2:
                        _cm = _num_s3.corr().abs().values
                        np.fill_diagonal(_cm, 0.0)
                        _corr_max = float(_cm.max())
                except Exception:
                    pass
            _del_a2 = _get_agent2()
            if _del_a2 is not None:
                # Keyword-search cross-check against uploaded MDD
                _mdd_text_s3 = st.session_state.get("val_mdd_text", "")
                if _mdd_text_s3:
                    _kw_s3 = _del_a2.check_mdd_keywords(_mdd_text_s3, stage="conceptual_soundness")
                    _s3_results.extend(_kw_s3)
                _rag_s3 = _del_a2.check_for_validation("conceptual_soundness", {
                    "correlation_max": _corr_max,
                })
                _s3_results.extend(_rag_s3)

            st.session_state["val_s3_results"] = _s3_results
            st.rerun()
        except Exception as _e:
            st.error(f"Error running checks: {_e}")

    # ── Display results ────────────────────────────────────────────────────────────
    _cs_res = st.session_state.get("val_s3_results")
    if not _cs_res:
        return

    st.markdown("### 📊 Conceptual Soundness Results")

    _pass_n = sum(1 for r in _cs_res if r.get("status") == "PASS")
    _warn_n = sum(1 for r in _cs_res if r.get("status") == "WARN")
    _fail_n = sum(1 for r in _cs_res if r.get("status") == "FAIL")
    _tot_n  = len(_cs_res)

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Total Checks", _tot_n)
    _m2.metric("✅ PASS", _pass_n)
    _m3.metric("🟡 WARN", _warn_n)
    _m4.metric("🔴 FAIL", _fail_n)
    st.progress(_pass_n / _tot_n if _tot_n > 0 else 0)

    _S_COL = {"PASS": "#10b981", "WARN": "#f59e0b", "FAIL": "#ef4444"}
    _S_BG  = {"PASS": "#071a0e", "WARN": "#1c1200", "FAIL": "#1c0808"}
    _S_ICN = {"PASS": "✅",      "WARN": "🟡",       "FAIL": "🔴"}
    _V_COL = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}

    # Split into threshold checks vs RAG agent flags.
    # Threshold checks have numeric check_ids like "3.1". RAG flags use "V13", "CS-001" etc.
    import re as _re
    def _is_threshold_check_s3(r):
        cid = str(r.get("check_id", r.get("rule_id", "")))
        return bool(_re.match(r"^\d+\.\d+$", cid))
    _thresh_s3  = [r for r in _cs_res if _is_threshold_check_s3(r)]
    _rag_s3_res = [r for r in _cs_res if not _is_threshold_check_s3(r)]

    _col_thresh_s3, _col_rag_s3 = st.columns(2)

    with _col_thresh_s3:
        st.markdown(
            "<div style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
            "padding:0.6rem 1rem;margin-bottom:0.75rem;'>"
            "<div style='color:#6366f1;font-weight:700;font-size:0.9rem;'>📐 Recommended Threshold Checks</div>"
            "<div style='color:#64748b;font-size:0.75rem;'>Quantitative checks against regulatory thresholds</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        for _r in _thresh_s3:
            _st  = _r.get("status", "WARN")
            _sev = _r.get("severity", "medium")
            st.markdown(
                f"<div style='border-left:3px solid {_S_COL.get(_st,'#6366f1')};"
                f"padding:0.75rem 1rem;margin:0.4rem 0;"
                f"background:{_S_BG.get(_st,'#1e293b')};border-radius:0 6px 6px 0;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
                f"<div style='color:#f1f5f9;font-size:0.92rem;font-weight:600;line-height:1.4;'>"
                f"{_S_ICN.get(_st,'⚪')} "
                f"<span style='color:#94a3b8;'>[{_html.escape(str(_r.get('check_id','')))}]</span> "
                f"{_html.escape(str(_r.get('title','')))}"
                f"<span style='background:{_V_COL.get(_sev,'#6366f1')};color:#0f172a;"
                f"font-size:0.7rem;font-weight:700;padding:0.1rem 0.5rem;"
                f"border-radius:10px;margin-left:0.5rem;'>{_html.escape(_sev.upper())}</span>"
                f"</div>"
                f"<span style='background:{_S_COL.get(_st,'#6366f1')};color:#0f172a;"
                f"font-size:0.78rem;font-weight:700;padding:0.15rem 0.6rem;"
                f"border-radius:4px;white-space:nowrap;'>{_st}</span>"
                f"</div>"
                f"<div style='color:#94a3b8;font-size:0.78rem;margin-top:0.3rem;'>"
                f"📋 {_html.escape(str(_r.get('source', '')))} — {_html.escape(str(_r.get('principle', '')))}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.25rem;'>"
                f"📊 Observed: <code style='color:#e2e8f0;'>"
                f"{_html.escape(str(_r.get('observed', '')))}</code></div>"
                f"<div style='color:#475569;font-size:0.78rem;margin-top:0.15rem;'>"
                f"📐 Threshold: {_html.escape(str(_r.get('threshold', '')))}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.2rem;'>"
                f"💡 {_html.escape(str(_r.get('detail', '')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with _col_rag_s3:
        st.markdown(
            "<div style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
            "padding:0.6rem 1rem;margin-bottom:0.75rem;'>"
            "<div style='color:#a78bfa;font-weight:700;font-size:0.9rem;'>🤖 RAG Agent Rules</div>"
            "<div style='color:#64748b;font-size:0.75rem;'>Regulatory rules fetched from knowledge store (SS1/23, SS11/13, IFRS 9)</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if not _rag_s3_res:
            st.info("No RAG agent flags generated for this stage.")
        for _r in _rag_s3_res:
            _sev    = _r.get("severity", "low")
            _border = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}.get(_sev, "#6366f1")
            _bg     = {"high": "#1c0808", "medium": "#1c1200", "low": "#071a0e"}.get(_sev, "#1e293b")
            _icon   = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(_sev, "⚪")
            _rule_id    = _html.escape(str(_r.get("rule_id", _r.get("check_id", "?"))))
            _flag_text  = _html.escape(str(_r.get("flag", _r.get("title", ""))))
            _suggestion = _html.escape(str(_r.get("suggestion", _r.get("detail", ""))))
            _source     = _html.escape(str(_r.get("source", "")))
            _principle  = _html.escape(str(_r.get("principle", "")))
            _ov         = _r.get("observed_value", _r.get("observed"))
            _obs_row    = (
                f"<div style='color:#94a3b8;font-size:0.78rem;margin-top:0.2rem;'>"
                f"📊 Observed: <code style='color:#e2e8f0;'>{_html.escape(str(_ov))}</code></div>"
                if _ov is not None else ""
            )
            _nv_tag = (
                "<span style='color:#64748b;font-size:0.75rem;font-style:italic;'> · not verifiable with current data</span>"
                if _r.get("not_verifiable") else ""
            )
            st.markdown(
                f"<div style='border-left:3px solid {_border};padding:0.6rem 1rem;"
                f"margin:0.35rem 0;background:{_bg};border-radius:0 6px 6px 0;'>"
                f"<div style='color:#f1f5f9;font-size:0.88rem;font-weight:600;line-height:1.4;'>"
                f"{_icon} <span style='color:#94a3b8;'>[{_rule_id}]</span> {_flag_text}{_nv_tag}</div>"
                f"{_obs_row}"
                f"<div style='color:#94a3b8;font-size:0.82rem;margin-top:0.25rem;line-height:1.4;'>"
                f"💡 {_suggestion}</div>"
                f"<div style='color:#475569;font-size:0.75rem;margin-top:0.15rem;'>"
                f"📋 {_source} — {_principle}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()
    _csv_rows = [{
        "Check ID":  r.get("check_id", ""),
        "Title":     r.get("title", r.get("flag", "")),
        "Source":    r.get("source", ""),
        "Principle": r.get("principle", ""),
        "Severity":  r.get("severity", ""),
        "Status":    r.get("status", ""),
        "Observed":  r.get("observed", ""),
        "Threshold": r.get("threshold", ""),
        "Detail":    r.get("detail", ""),
    } for r in _cs_res]
    st.download_button(
        "📥 Download Conceptual Soundness Report (CSV)",
        data=pd.DataFrame(_csv_rows).to_csv(index=False).encode("utf-8"),
        file_name="conceptual_soundness_report.csv",
        mime="text/csv",
        use_container_width=True,
        key="download_cs_report",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        if st.button(
            "▶️ Proceed to Stage 4: Replication & Benchmarking",
            type="primary",
            use_container_width=True,
            key="proceed_to_stage4",
        ):
            st.session_state["val_step"] = 4
            st.rerun()


def render_val_performance():
    """Stage 5 — Performance Validation + Benchmarking"""
    import html as _html
    from sklearn.metrics import roc_curve as _roc_curve, confusion_matrix as _cm

    st.markdown("### 📊 Stage 5 — Performance Validation & Benchmarking")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.87rem;'>"
        "SS1/23 P4.1 · SS11/13 §10.3 · SS11/13 §10.5"
        "</p>",
        unsafe_allow_html=True,
    )

    ij         = st.session_state.get("val_intake_json") or {}
    rep_result = st.session_state.get("val_rep_result") or {}
    rep_metrics = rep_result.get("metrics") or {}
    y_proba    = rep_result.get("y_proba_test")
    y_test     = rep_result.get("y_test")

    if not ij:
        st.warning("⚠️ No model intake data found. Complete Stage 1 first.")
        return

    tab1, tab2 = st.tabs(["📊 Performance Testing", "🏆 Benchmarking"])

    # ══════════════════════════════════════════════════════════════════
    # TAB 1 — PERFORMANCE TESTING
    # ══════════════════════════════════════════════════════════════════
    with tab1:

        st.markdown("#### 📋 Metrics — Stated vs Replicated vs Threshold")
        st.caption(
            "Stated = developer MDD. Replicated = independently computed in Stage 4. "
            "Threshold = regulatory minimum."
        )

        _S_COL  = {"PASS": "#10b981", "WARN": "#f59e0b", "FAIL": "#ef4444"}
        _S_BG   = {"PASS": "#071a0e", "WARN": "#1c1200", "FAIL": "#1c0808"}
        _S_ICN  = {"PASS": "✅", "WARN": "🟡", "FAIL": "🔴"}
        _SEV_C  = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}

        perf_rows = [
            ("ROC-AUC",    ij.get("stated_auc"),    rep_metrics.get("roc_auc"),
             "≥ 0.70", lambda s,r: (r or s or 0) >= 0.70, "SS1/23 P4.1",    "HIGH"),
            ("Gini",       ij.get("stated_gini"),
             round(2*rep_metrics["roc_auc"]-1,4) if rep_metrics.get("roc_auc") else None,
             "≥ 0.40", lambda s,r: (r or s or 0) >= 0.40, "SS11/13 §10.3",  "HIGH"),
            ("Recall",     ij.get("stated_recall"),  rep_metrics.get("recall"),
             "≥ 0.60", lambda s,r: (r or s or 0) >= 0.60, "SS1/23 P4.4",    "HIGH"),
            ("Precision",  None,                     rep_metrics.get("precision"),
             "≥ 0.50", lambda s,r: (r or 0) >= 0.50,      "SS1/23 P4.4",    "MEDIUM"),
            ("F1 Score",   None,                     rep_metrics.get("f1"),
             "≥ 0.55", lambda s,r: (r or 0) >= 0.55,      "SS1/23 P4.4",    "MEDIUM"),
            ("Brier Score",ij.get("stated_brier"),   rep_metrics.get("brier_score"),
             "< 0.25", lambda s,r: (r or s or 1) < 0.25,  "SS11/13 §10.5",  "HIGH"),
            ("PR-AUC",     None,                     rep_metrics.get("pr_auc"),
             "≥ 0.30", lambda s,r: (r or 0) >= 0.30,      "SS1/23 P3.3",    "MEDIUM"),
            ("KS Statistic",None,                    rep_metrics.get("ks"),
             "≥ 0.30", lambda s,r: (r or 0) >= 0.30,      "SS11/13 §10.3",  "MEDIUM"),
        ]

        csv_rows = []
        for (check, stated, replicated, threshold, pass_fn, source, sev) in perf_rows:
            val = replicated if replicated is not None else stated
            if val is None:
                status = "WARN"
                obs    = "No stated or replicated value available"
            elif pass_fn(stated, replicated):
                status = "PASS"
                obs    = f"{'Replicated' if replicated else 'Stated'}: {val:.4f}"
            else:
                status = "FAIL"
                obs    = f"{'Replicated' if replicated else 'Stated'}: {val:.4f}"

            gap_warn = ""
            if stated is not None and replicated is not None:
                gap = abs(stated - replicated)
                if gap > 0.05:
                    gap_warn = (
                        f" ⚠️ Gap: stated={stated:.4f} vs "
                        f"replicated={replicated:.4f} (Δ={gap:.4f})"
                    )

            border = _S_COL.get(status, "#6366f1")
            bg     = _S_BG.get(status, "#1e293b")
            icon   = _S_ICN.get(status, "⚪")
            sev_c  = _SEV_C.get(sev, "#6366f1")

            st.markdown(
                f"<div style='border-left:3px solid {border};padding:0.75rem 1rem;"
                f"margin:0.4rem 0;background:{bg};border-radius:0 6px 6px 0;'>"
                f"<div style='display:flex;justify-content:space-between;'>"
                f"<div style='color:#f1f5f9;font-size:0.92rem;font-weight:600;'>"
                f"{icon} {_html.escape(check)}"
                f"<span style='background:{sev_c};color:#0f172a;font-size:0.7rem;"
                f"font-weight:700;padding:0.1rem 0.5rem;border-radius:10px;"
                f"margin-left:0.5rem;'>{sev}</span></div>"
                f"<span style='background:{border};color:#0f172a;font-size:0.78rem;"
                f"font-weight:700;padding:0.15rem 0.6rem;border-radius:4px;'>"
                f"{status}</span></div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.3rem;'>"
                f"📊 {_html.escape(obs)}{_html.escape(gap_warn)}</div>"
                f"<div style='color:#475569;font-size:0.78rem;margin-top:0.15rem;'>"
                f"📐 Threshold: {_html.escape(threshold)} — "
                f"📋 {_html.escape(source)}</div>"
                f"<div style='color:#475569;font-size:0.75rem;margin-top:0.1rem;'>"
                f"Stated: {f'{stated:.4f}' if stated else 'N/A'} | "
                f"Replicated: {f'{replicated:.4f}' if replicated else 'N/A'}"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            csv_rows.append({
                "Check": check, "Stated": stated,
                "Replicated": replicated, "Threshold": threshold,
                "Status": status, "Source": source, "Severity": sev,
            })

        st.divider()

        # ── Train/Test gap ────────────────────────────────────────────
        st.markdown("#### 🔍 Train/Test AUC Gap (Overfitting Check)")
        cv_mean  = rep_result.get("cv_mean_auc")
        test_auc = rep_metrics.get("roc_auc")
        if cv_mean and test_auc:
            gap = abs(cv_mean - test_auc)
            gs  = "PASS" if gap <= 0.10 else "FAIL"
            st.markdown(
                f"<div style='border-left:3px solid "
                f"{'#10b981' if gs=='PASS' else '#ef4444'};"
                f"padding:0.75rem 1rem;margin:0.4rem 0;"
                f"background:{'#071a0e' if gs=='PASS' else '#1c0808'};"
                f"border-radius:0 6px 6px 0;'>"
                f"<div style='color:#f1f5f9;font-weight:600;'>"
                f"{'✅' if gs=='PASS' else '🔴'} Train/Test AUC Gap</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.3rem;'>"
                f"CV Mean AUC: {cv_mean:.4f} | Test AUC: {test_auc:.4f} | "
                f"Gap: {gap:.4f}</div>"
                f"<div style='color:#475569;font-size:0.78rem;margin-top:0.15rem;'>"
                f"📐 Gap ≤ 0.10 — 📋 SS1/23 P4.4</div></div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Run Stage 4 with CV enabled to populate this check.")

        st.divider()

        # ── Charts ────────────────────────────────────────────────────
        if y_proba is not None and y_test is not None:
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("#### 📈 ROC Curve")
                fpr, tpr, _ = _roc_curve(y_test.values, y_proba)
                auc_val = rep_metrics.get("roc_auc", 0)
                fig_roc = go.Figure()
                fig_roc.add_trace(go.Scatter(
                    x=fpr, y=tpr, mode="lines",
                    name=f"AUC={auc_val:.4f}",
                    line=dict(color="#6366f1", width=3),
                    fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
                ))
                fig_roc.add_trace(go.Scatter(
                    x=[0,1], y=[0,1], mode="lines", name="Random",
                    line=dict(color="#64748b", dash="dash"),
                ))
                fig_roc.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    xaxis_title="FPR", yaxis_title="TPR",
                )
                st.plotly_chart(fig_roc, use_container_width=True)

            with c2:
                st.markdown("#### 🔢 Confusion Matrix")
                y_pred = (y_proba >= 0.5).astype(int)
                cm = _cm(y_test.values, y_pred)
                fig_cm = go.Figure(go.Heatmap(
                    z=cm, x=["Pred: 0","Pred: 1"],
                    y=["Actual: 0","Actual: 1"],
                    text=cm, texttemplate="%{text}",
                    colorscale="Blues",
                ))
                fig_cm.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                )
                st.plotly_chart(fig_cm, use_container_width=True)

            st.markdown("#### 📊 Score Distribution by Outcome")
            fig_dist = go.Figure()
            df_plot = pd.DataFrame({
                "proba": y_proba, "actual": y_test.values
            })
            fig_dist.add_trace(go.Histogram(
                x=df_plot[df_plot["actual"]==0]["proba"],
                name="Non-Default", opacity=0.6,
                marker_color="#10b981", nbinsx=40,
            ))
            fig_dist.add_trace(go.Histogram(
                x=df_plot[df_plot["actual"]==1]["proba"],
                name="Default", opacity=0.6,
                marker_color="#ef4444", nbinsx=40,
            ))
            fig_dist.update_layout(
                barmode="overlay",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                xaxis_title="Predicted PD",
                yaxis_title="Count",
            )
            st.plotly_chart(fig_dist, use_container_width=True)

            # ── Calibration chart ─────────────────────────────────────
            st.markdown("#### 🎯 Calibration Chart (Actual vs Predicted by Risk Bin)")
            st.caption(
                "Customers grouped into 10 bins by predicted PD. "
                "Bars = actual default rate. Line = avg predicted PD. "
                "A well-calibrated model has bars matching the line."
            )
            df_cal = pd.DataFrame({
                "actual": y_test.values, "predicted": y_proba
            })
            df_cal["bin"] = pd.qcut(
                df_cal["predicted"], q=10, duplicates="drop"
            )
            grouped = df_cal.groupby("bin", observed=True).agg(
                actual_rate=("actual", "mean"),
                predicted_rate=("predicted", "mean"),
                n=("actual", "count"),
            ).reset_index()
            grouped["bin_label"] = grouped["bin"].astype(str)

            fig_cal = go.Figure()
            fig_cal.add_trace(go.Bar(
                x=grouped["bin_label"],
                y=grouped["actual_rate"],
                name="Actual Default Rate",
                marker_color="#ef4444", opacity=0.85,
            ))
            fig_cal.add_trace(go.Scatter(
                x=grouped["bin_label"],
                y=grouped["predicted_rate"],
                mode="lines+markers",
                name="Avg Predicted PD",
                line=dict(color="#6366f1", width=3),
                marker=dict(size=8),
            ))
            fig_cal.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                xaxis_title="Predicted PD Bin (low → high risk)",
                yaxis=dict(tickformat=".0%", gridcolor="#334155"),
            )
            st.plotly_chart(fig_cal, use_container_width=True)

        st.divider()

        # ── Manual stubs ──────────────────────────────────────────────
        st.markdown("#### 🚧 Checks Requiring Manual Review")
        for cid, ctitle, src, prin, sev in [
            ("5.8",  "Calibration Test (Hosmer-Lemeshow)",
             "SS11/13", "§10.5", "HIGH"),
            ("5.9",  "SHAP Explainability Outputs Reviewed",
             "SS1/23",  "P4.2",  "HIGH"),
            ("5.10", "Decision Threshold Justified",
             "SS1/23",  "P5.1",  "MEDIUM"),
            ("5.11", "Sensitivity Analysis Performed",
             "SS1/23",  "P4.3",  "MEDIUM"),
        ]:
            st.markdown(
                f"<div style='border-left:3px solid #475569;"
                f"padding:0.6rem 1rem;margin:0.3rem 0;"
                f"background:#1e293b;border-radius:0 6px 6px 0;'>"
                f"<div style='color:#94a3b8;font-size:0.88rem;font-weight:600;'>"
                f"⏭️ [{cid}] {_html.escape(ctitle)}</div>"
                f"<div style='color:#475569;font-size:0.78rem;margin-top:0.2rem;'>"
                f"📋 {src} {prin} — Manual review required"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.download_button(
            "📥 Download Performance Report (CSV)",
            data=pd.DataFrame(csv_rows).to_csv(index=False).encode("utf-8"),
            file_name="performance_validation_report.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_perf_report",
        )

    # ══════════════════════════════════════════════════════════════════
    # TAB 2 — BENCHMARKING
    # ══════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("#### 🏆 Benchmarking — Champion vs Challenger")
        st.caption(
            "Compare the submitted model against a baseline/benchmark model. "
            "SS1/23 P4.2 requires performance to be assessed relative to "
            "alternatives. Industry standard for credit risk is logistic "
            "regression as the baseline challenger."
        )

        val_df = st.session_state.get("val_df")

        if val_df is None:
            st.warning("⚠️ No dataset found. Complete Stage 1 first.")
        elif y_proba is None or y_test is None:
            st.warning("⚠️ Run Stage 4 Model Replication first to enable benchmarking.")
        else:
            # ── Benchmark model selector ──────────────────────────────
            st.markdown("##### Select Benchmark Model")
            benchmark_model = st.selectbox(
                "Benchmark / Challenger model",
                [
                    "Logistic Regression (Industry Standard)",
                    "Decision Tree (Simple Interpretable)",
                    "Random Forest (Ensemble Baseline)",
                ],
                key="benchmark_model_sel",
            )

            if st.button(
                "🚀 Run Benchmark Comparison",
                type="primary",
                use_container_width=True,
                key="run_benchmark_btn",
            ):
                from sklearn.linear_model import LogisticRegression
                from sklearn.tree import DecisionTreeClassifier
                from sklearn.ensemble import RandomForestClassifier
                from sklearn.preprocessing import StandardScaler
                from sklearn.metrics import roc_auc_score
                import warnings
                warnings.filterwarnings("ignore")

                with st.spinner("Training benchmark model..."):
                    try:
                        rep_res     = st.session_state.get("val_rep_result") or {}
                        X_test_rep  = rep_res.get("X_test")
                        X_train_rep = rep_res.get("X_train")
                        y_train_rep = rep_res.get("y_train")
                        y_test_rep  = rep_res.get("y_test")

                        if X_train_rep is None:
                            st.error("Stage 4 training data not found in session. Re-run Stage 4.")
                        else:
                            if "Logistic" in benchmark_model:
                                bm = LogisticRegression(
                                    max_iter=1000, class_weight="balanced", random_state=42
                                )
                            elif "Decision Tree" in benchmark_model:
                                bm = DecisionTreeClassifier(
                                    max_depth=5, class_weight="balanced", random_state=42
                                )
                            else:
                                bm = RandomForestClassifier(
                                    n_estimators=100, class_weight="balanced", random_state=42
                                )

                            from sklearn.impute import SimpleImputer

                            # Select numeric columns only
                            X_tr_num = X_train_rep.select_dtypes(include=[np.number])
                            X_te_num = X_test_rep.select_dtypes(include=[np.number])

                            # Impute missing values with median (learned on train only)
                            imputer = SimpleImputer(strategy="median")
                            X_tr_imp = imputer.fit_transform(X_tr_num)
                            X_te_imp = imputer.transform(X_te_num)

                            # Scale
                            scaler  = StandardScaler()
                            X_tr_sc = scaler.fit_transform(X_tr_imp)
                            X_te_sc = scaler.transform(X_te_imp)

                            bm.fit(X_tr_sc, y_train_rep)
                            bm_proba  = bm.predict_proba(X_te_sc)[:, 1]
                            bm_pred   = (bm_proba >= 0.5).astype(int)
                            bm_auc    = round(roc_auc_score(y_test_rep.values, bm_proba), 4)
                            bm_gini   = round(2 * bm_auc - 1, 4)
                            bm_recall = round(
                                float((bm_pred[y_test_rep.values == 1] == 1).mean()), 4
                            )

                            st.session_state["val_benchmark_proba"]   = bm_proba
                            st.session_state["val_benchmark_metrics"] = {
                                "roc_auc": bm_auc,
                                "gini":    bm_gini,
                                "recall":  bm_recall,
                            }
                            st.session_state["val_benchmark_name"]    = benchmark_model
                            st.success(f"✅ Benchmark trained — AUC={bm_auc:.4f}")
                    except Exception as e:
                        st.error(f"Benchmark training failed: {e}")

            # ── Show comparison if benchmark exists ───────────────────
            bm_metrics      = st.session_state.get("val_benchmark_metrics")
            bm_proba_stored = st.session_state.get("val_benchmark_proba")
            bm_name         = st.session_state.get("val_benchmark_name", "Benchmark")

            if bm_metrics:
                st.markdown("##### 📊 Champion vs Challenger Comparison")

                comp_data = {
                    "Metric": ["ROC-AUC", "Gini", "Recall"],
                    "Submitted Model (Champion)": [
                        round(rep_metrics.get("roc_auc", 0), 4),
                        round(2 * rep_metrics.get("roc_auc", 0) - 1, 4),
                        round(rep_metrics.get("recall", 0), 4),
                    ],
                    f"Benchmark ({bm_name.split('(')[0].strip()})": [
                        bm_metrics["roc_auc"],
                        bm_metrics["gini"],
                        bm_metrics["recall"],
                    ],
                }
                comp_df = pd.DataFrame(comp_data)
                comp_df["Delta (Champion - Benchmark)"] = (
                    comp_df["Submitted Model (Champion)"]
                    - comp_df[f"Benchmark ({bm_name.split('(')[0].strip()})"]
                )
                comp_df["Verdict"] = comp_df["Delta (Champion - Benchmark)"].apply(
                    lambda d: "✅ Better" if d > 0.02
                    else "⚠️ Similar" if d >= -0.02
                    else "❌ Worse"
                )
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                worse  = (comp_df["Verdict"] == "❌ Worse").sum()
                better = (comp_df["Verdict"] == "✅ Better").sum()
                if worse > 0:
                    st.error(
                        f"❌ Submitted model underperforms the benchmark on "
                        f"{worse} metric(s) — requires justification per SS1/23 P4.2"
                    )
                elif better == len(comp_df):
                    st.success(
                        "✅ Submitted model outperforms benchmark on all metrics — "
                        "champion/challenger test passed"
                    )
                else:
                    st.warning(
                        "⚠️ Submitted model performance is similar to benchmark — "
                        "marginal improvement may not justify additional model complexity"
                    )

                if bm_proba_stored is not None:
                    st.markdown("##### 📈 ROC Curve Overlay")
                    from sklearn.metrics import roc_curve as _rc2
                    fpr_ch, tpr_ch, _ = _rc2(y_test.values, y_proba)
                    fpr_bm, tpr_bm, _ = _rc2(y_test.values, bm_proba_stored)

                    fig_overlay = go.Figure()
                    fig_overlay.add_trace(go.Scatter(
                        x=fpr_ch, y=tpr_ch, mode="lines",
                        name=f"Champion (AUC={rep_metrics.get('roc_auc', 0):.4f})",
                        line=dict(color="#6366f1", width=3),
                    ))
                    fig_overlay.add_trace(go.Scatter(
                        x=fpr_bm, y=tpr_bm, mode="lines",
                        name=f"Benchmark (AUC={bm_metrics['roc_auc']:.4f})",
                        line=dict(color="#f59e0b", width=2.5, dash="dash"),
                    ))
                    fig_overlay.add_trace(go.Scatter(
                        x=[0, 1], y=[0, 1], mode="lines", name="Random",
                        line=dict(color="#64748b", dash="dot"),
                    ))
                    fig_overlay.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#e2e8f0"),
                        title="ROC Curve — Champion vs Challenger",
                        xaxis_title="False Positive Rate",
                        yaxis_title="True Positive Rate",
                    )
                    st.plotly_chart(fig_overlay, use_container_width=True)

                st.download_button(
                    "📥 Download Benchmarking Report (CSV)",
                    data=comp_df.to_csv(index=False).encode("utf-8"),
                    file_name="benchmarking_report.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_benchmark_report",
                )
            else:
                st.info(
                    "ℹ️ Select a benchmark model above and click "
                    "'Run Benchmark Comparison' to start."
                )

            # ── Industry benchmarks ───────────────────────────────────
            st.divider()
            st.markdown("##### 📋 Industry Standard Benchmarks")
            st.caption(
                "Typical performance ranges for retail credit risk PD models. "
                "Source: industry practice and regulatory guidance."
            )
            industry_df = pd.DataFrame({
                "Metric":    ["ROC-AUC", "Gini", "KS", "Brier Score"],
                "Minimum":   ["0.70",    "0.40", "0.30", "< 0.25"],
                "Good":      ["0.75-0.80", "0.50-0.60", "0.40-0.50", "< 0.20"],
                "Excellent": ["> 0.85",    "> 0.70",    "> 0.60",    "< 0.15"],
                "Our Model": [
                    f"{rep_metrics.get('roc_auc'):.4f}" if rep_metrics.get("roc_auc") else "N/A",
                    f"{round(2*rep_metrics.get('roc_auc',0)-1,4):.4f}" if rep_metrics.get("roc_auc") else "N/A",
                    f"{rep_metrics.get('ks'):.4f}" if rep_metrics.get("ks") else "N/A",
                    f"{rep_metrics.get('brier_score'):.4f}" if rep_metrics.get("brier_score") else "N/A",
                ],
            })
            st.dataframe(industry_df, use_container_width=True, hide_index=True)

    # ── Proceed button ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        if st.button(
            "▶️ Proceed to Stage 6: Stress & Backtesting",
            type="primary",
            use_container_width=True,
            key="proceed_to_stage6",
        ):
            st.session_state["val_step"] = 6
            st.rerun()


def render_model_validation():
    """Top-level Model Validation workspace — routes by val_step (sidebar is the nav)."""
    st.markdown("""
    <div class='step-header'>
        <h3>🔎 Independent Model Validation Workspace</h3>
        <p>Validate externally submitted credit risk models against SS1/23, IFRS 9, IFRS 7, SS11/13</p>
    </div>
    """, unsafe_allow_html=True)

    stage = st.session_state.get("val_step", 1)

    if stage == 1:
        render_val_intake()
    elif stage == 2:
        render_val_data_validation()
    elif stage == 3:
        render_val_conceptual_soundness()
    elif stage == 4:
        render_val_replication()

        # ── Feature Importance Comparison Table ──────────────────────────────────
        st.divider()
        st.markdown("#### 📊 Feature Importance Comparison")

        _rep_imp    = st.session_state.get("val_replicated_importances") or {}
        _stated_imp = (st.session_state.get("val_hyperparams") or {}).get("feature_importances") or {}

        if not _rep_imp:
            st.info("Run Model Replication above to populate the feature importance comparison table.")
        else:
            _all_feats = list(dict.fromkeys(
                list(_rep_imp.keys())[:10] + list(_stated_imp.keys())
            ))

            _rows = []
            for _f in _all_feats:
                _r = _rep_imp.get(_f, 0.0)
                _s = _stated_imp.get(_f) if _stated_imp else None
                _d = round(abs(_r - _s), 4) if _s is not None else None
                _rows.append({
                    "Feature":          _f,
                    "Replicated":       round(_r, 4),
                    "Developer Stated": round(_s, 4) if _s is not None else "N/A",
                    "Difference":       _d if _d is not None else "N/A",
                    "Match": (
                        "✅" if _d is not None and _d < 0.05
                        else "⚠️" if _d is not None and _d < 0.15
                        else "❌" if _d is not None
                        else "—"
                    ),
                })

            _rows.sort(key=lambda x: x["Replicated"], reverse=True)

            st.dataframe(
                pd.DataFrame(_rows).head(10),
                use_container_width=True,
                hide_index=True,
            )

            if not _stated_imp:
                st.caption(
                    "💡 Add 'feature_importances' to your hyperparameter "
                    "config JSON to enable comparison against developer stated values."
                )

        st.divider()
        if st.button(
            "Proceed to Stage 5: Performance Testing →",
            type="primary",
            use_container_width=True,
            key="proceed_to_stage5",
        ):
            st.session_state["val_step"] = 5
            st.rerun()

    elif stage == 5:
        render_val_performance()
    elif stage == 6:
        _render_val_stage_stub(6, "📉", "Stress Testing & Backtesting", "SS11/13 §12 · IFRS 9 B5.5.49",
            "Test model performance under stress scenarios and economic downturns. "
            "Backtest PD estimates against observed default rates using traffic-light frameworks.")
    elif stage == 7:
        _render_val_stage_stub(7, "⚖️", "Regulatory Compliance Review", "SS1/23 · IFRS 9 · IFRS 7 · SS11/13",
            "Verify the model meets all applicable regulatory requirements including SICR criteria, "
            "ECL staging logic, forward-looking information, and IFRS 7 disclosure requirements.")
    elif stage == 8:
        _render_val_stage_stub(8, "📄", "Findings & Validation Report", "SS1/23 P5 · SS11/13 §13",
            "Compile all validation findings into the formal Independent Validation Report. "
            "Assign an overall model rating and document conditions, limitations, and remediation actions.")


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
def render_header():
    if st.session_state.get("workspace", "landing") == "landing":
        return
    st.markdown("""
    <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border: 1px solid #334155; border-radius: 12px; padding: 1.5rem 2rem;
                margin-bottom: 1.5rem;'>
        <div style='display:flex; align-items:center; gap:1rem;'>
            <span style='font-size:2.5rem'>🏦</span>
            <div>
                <h1 style='color:#e2e8f0; margin:0; font-size:1.8rem'>Credit Risk ML Platform</h1>
                <p style='color:#6366f1; margin:0; font-size:0.9rem'>
                    Adaptive Machine Learning POC · Automatically adapts to any dataset schema
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Model Development — LGD & EAD tabs
# ─────────────────────────────────────────────
def render_lgd_development():
    """LGD modelling tab (Model Development). Mirrors the PD pipeline's staged feel,
    but is fully automatic: training population, realized-LGD target and predictors
    are all derived from the same uploaded dataset and the PD target already chosen
    in the PD Model tab. Uses the SAME dataset uploaded in Step 1 — no re-upload."""
    st.markdown("""
    <div class='step-header'>
        <h3>💧 LGD Model — Loss Given Default</h3>
        <p>Train a regression model on the defaulted loans in your uploaded dataset
        (default flag = the PD target chosen in the PD Model tab), enriched with
        point-in-time macroeconomic features from FRED. Same dataset, no re-upload.</p>
    </div>
    """, unsafe_allow_html=True)

    data = st.session_state.get("df")
    if data is None:
        st.warning("Please upload or generate a dataset first (Step 1).")
        return

    X_full = _full_engineered_X()
    portfolio_index = X_full.index if X_full is not None else None

    lgd_ui.render_lgd_workflow(data, portfolio_index, y=st.session_state.get("y"))


def render_ead_development():
    """EAD modelling tab (Model Development). Revolving products (cards) use an
    ML-estimated CCF (EAD = drawn + CCF × undrawn); non-revolving term loans use
    the amortisation schedule. Same uploaded dataset — no re-upload."""
    st.markdown("""
    <div class='step-header'>
        <h3>💳 EAD Model — Exposure at Default</h3>
        <p>Revolving accounts: ML-estimated Credit Conversion Factor on the defaulted
        revolving book. Non-revolving term loans: amortising outstanding principal +
        accrued interest. Same dataset uploaded in Step 1 — no re-upload.</p>
    </div>
    """, unsafe_allow_html=True)

    data = st.session_state.get("df")
    if data is None:
        st.warning("Please upload or generate a dataset first (Step 1).")
        return

    X_full = _full_engineered_X()
    portfolio_index = X_full.index if X_full is not None else None

    ead_ui.render_ead_workflow(data, portfolio_index, y=st.session_state.get("y"))



def _render_attestation_checklist():
    """
    Option B: render descriptive (non-machine-testable) extracted rules as a
    per-stage reviewer sign-off checklist. Source: Agent2.get_attestation_checklist().
    """
    _a2 = _get_agent2()
    if _a2 is None or not hasattr(_a2, "get_attestation_checklist"):
        return
    _items = _a2.get_attestation_checklist()
    if not _items:
        return

    from collections import defaultdict
    _labels = {"data": "Data", "feature": "Feature Engineering",
               "training": "Training", "evaluation": "Evaluation", "other": "Other"}
    _by_stage = defaultdict(list)
    for _it in _items:
        _by_stage[_it.get("stage", "other")].append(_it)

    with st.expander(f"📝 Manual Attestation Checklist — {len(_items)} descriptive rule(s)", expanded=False):
        st.caption("IFRS 9 / SS1-23 rules that can't be auto-checked against data — "
                   "a reviewer confirms each during validation.")
        for _sk in ["data", "feature", "training", "evaluation", "other"]:
            _group = _by_stage.get(_sk, [])
            if not _group:
                continue
            st.markdown(f"**{_labels.get(_sk, _sk.title())}** ({len(_group)})")
            for _it in _group:
                _rid = _it.get("rule_id", "?")
                _help = " · ".join(
                    p for p in (_it.get("source", ""), _it.get("principle", ""),
                                _it.get("suggestion", "")) if p
                )
                st.checkbox(
                    f"[{_rid}] {_it.get('statement', '')}",
                    key=f"attest_{_sk}_{_rid}",
                    help=_help or None,
                )


# ─────────────────────────────────────────────
# Compliance Tab
# ─────────────────────────────────────────────
def _render_compliance_tab():
    st.markdown("""
    <div class='step-header'>
        <h3>📋 Compliance Dashboard</h3>
        <p>Consolidated SS1/23, IFRS 9, IFRS 7 compliance flags from all pipeline stages</p>
    </div>
    """, unsafe_allow_html=True)

    _render_attestation_checklist()

    _stage_map = {
        "data":       "Data Profiling",
        "feature":    "Feature Engineering",
        "training":   "Training",
        "evaluation": "Evaluation",
    }

    # Collect all flags
    _all_flags = []
    for _sk, _sl in _stage_map.items():
        for _f in st.session_state.get(f"agent2_flags_{_sk}", []):
            _all_flags.append({**_f, "_stage": _sl})

    if not _all_flags:
        st.info("ℹ️ No compliance flags yet. Complete Steps 2–7 in the **App** tab to generate flags.")
        return

    # Summary
    _high   = sum(1 for f in _all_flags if f.get("severity") == "high")
    _medium = sum(1 for f in _all_flags if f.get("severity") == "medium")
    _low    = sum(1 for f in _all_flags if f.get("severity") == "low")
    _sm1, _sm2, _sm3, _sm4 = st.columns(4)
    _sm1.metric("Total Flags",  len(_all_flags))
    _sm2.metric("🔴 High",      _high)
    _sm3.metric("🟡 Medium",    _medium)
    _sm4.metric("🟢 Low",       _low)

    st.divider()

    # Per-stage banners
    for _sk, _sl in _stage_map.items():
        _flags = st.session_state.get(f"agent2_flags_{_sk}", [])
        if _flags:
            st.markdown(f"#### {_sl}")
            _render_compliance_banner(_sl, _flags)

    # Model tier
    if st.session_state.get("model_tier"):
        st.markdown("#### SS1/23 Model Risk Tier")
        _render_tier_card(st.session_state["model_tier"])

    # Download
    st.divider()
    _dl_rows = [{
        "Stage":      f.get("_stage", ""),
        "Rule ID":    f.get("rule_id", ""),
        "Severity":   f.get("severity", ""),
        "Source":     f.get("source", ""),
        "Principle":  f.get("principle", ""),
        "Flag":       f.get("flag", ""),
        "Suggestion": f.get("suggestion", ""),
    } for f in _all_flags]
    st.download_button(
        "📥 Download Compliance Report (CSV)",
        data=pd.DataFrame(_dl_rows).to_csv(index=False).encode("utf-8"),
        file_name="compliance_report.csv",
        mime="text/csv",
        use_container_width=True,
        key="download_compliance_report",
    )


# ─────────────────────────────────────────────
# Landing Page
# ─────────────────────────────────────────────
def render_landing():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align:center;padding:2rem 0 1rem 0;'>
        <span style='font-size:4rem'>🏦</span>
        <h1 style='color:#e2e8f0;font-size:2.2rem;margin:0.5rem 0;'>Credit Risk ML Platform</h1>
        <p style='color:#64748b;font-size:1rem;margin:0;'>
            Regulation-grade credit risk modelling and independent model validation
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1, 0.08, 1])

    with col_left:
        st.markdown("""
        <div style='background:#1e293b;border:1px solid #334155;border-radius:16px;
                    padding:2rem;text-align:center;min-height:320px;'>
            <div style='font-size:3rem;margin-bottom:1rem;'>⚙️</div>
            <div style='color:#e2e8f0;font-size:1.3rem;font-weight:700;margin-bottom:0.5rem;'>
                Model Development
            </div>
            <div style='color:#94a3b8;font-size:0.88rem;line-height:1.6;margin-bottom:1.5rem;'>
                End-to-end ML pipeline for building credit risk models.<br><br>
                Data → Features → Training → Evaluation → Explainability<br><br>
                Agent 2 compliance checks at every step.<br>
                SS1/23 · IFRS 9 · IFRS 7
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        if st.button("⚙️ Open Model Development", use_container_width=True, type="primary", key="go_develop"):
            st.session_state.workspace = "development"
            st.session_state.current_step = 1
            st.rerun()

    with col_mid:
        st.markdown("""
        <div style='display:flex;align-items:center;justify-content:center;height:320px;'>
            <div style='color:#334155;font-size:1.5rem;font-weight:300;'>|</div>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown("""
        <div style='background:#1e293b;border:1px solid #334155;border-radius:16px;
                    padding:2rem;text-align:center;min-height:320px;'>
            <div style='font-size:3rem;margin-bottom:1rem;'>🔎</div>
            <div style='color:#e2e8f0;font-size:1.3rem;font-weight:700;margin-bottom:0.5rem;'>
                Model Validation
            </div>
            <div style='color:#94a3b8;font-size:0.88rem;line-height:1.6;margin-bottom:1.5rem;'>
                Independent validation of externally submitted credit risk models.<br><br>
                Intake → Data → Soundness → Replication → Performance → Stress → Compliance → Report<br><br>
                SS1/23 P4.1 independence requirement.<br>
                SS1/23 · SS11/13 · IFRS 9 · IFRS 7
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        if st.button("🔎 Open Model Validation", use_container_width=True, type="secondary", key="go_validate"):
            st.session_state.workspace = "validation"
            st.session_state.val_step = 1
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align:center;color:#334155;font-size:0.78rem;'>
        Deloitte SR&amp;T · Credit Risk POC · SS1/23 (PRA) · IFRS 9 · IFRS 7 · SS11/13
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Main Router
# ─────────────────────────────────────────────
def main():
    render_sidebar()
    render_header()

    workspace = st.session_state.get("workspace", "landing")

    if workspace == "landing":
        render_landing()
        return

    if workspace == "validation":
        render_model_validation()
        return

    # Development pipeline
    step = st.session_state.current_step

    if step == 1:
        render_upload()
    elif step in (2, 3, 4, 5, 6, 7, 8):
        tab_pd, tab_lgd, tab_ead = st.tabs(["🎯 PD Model", "💧 LGD Model", "💳 EAD Model"])
        with tab_pd:
            if step == 2:
                if st.session_state.df is None:
                    st.warning("Please upload or generate a dataset first.")
                    st.session_state.current_step = 1
                    st.rerun()
                render_profiling()
            elif step == 3:
                if st.session_state.df is None or st.session_state.target_col is None:
                    st.session_state.current_step = 2
                    st.rerun()
                render_preprocessing()
            elif step == 4:
                if st.session_state.X is None:
                    st.session_state.current_step = 3
                    st.rerun()
                render_feature_engineering()
            elif step == 5:
                if st.session_state.X is None:
                    st.session_state.current_step = 4
                    st.rerun()
                render_model_selection()
            elif step == 6:
                if st.session_state.X is None:
                    st.session_state.current_step = 5
                    st.rerun()
                render_training()
            elif step == 7:
                if st.session_state.trained_pipeline is None:
                    st.session_state.current_step = 6
                    st.rerun()
                render_evaluation()
            elif step == 8:
                if st.session_state.trained_pipeline is None:
                    st.session_state.current_step = 7
                    st.rerun()
                render_explainability()
        with tab_lgd:
            # Gated: finish the PD pipeline (train a PD model) before LGD.
            if st.session_state.get("trained_pipeline") is None:
                st.info("🔒 **Locked.** Complete the **🎯 PD Model** pipeline first "
                        "(train a PD model in Step 6) to unlock the LGD model.")
            else:
                render_lgd_development()
        with tab_ead:
            # Gated: finish the LGD pipeline (train an LGD model) before EAD.
            if st.session_state.get("trained_pipeline") is None:
                st.info("🔒 **Locked.** Complete the **🎯 PD Model** pipeline first.")
            elif st.session_state.get("lgd_model_bundle") is None:
                st.info("🔒 **Locked.** Complete the **💧 LGD Model** pipeline first "
                        "(train an LGD model) to unlock the EAD model.")
            else:
                render_ead_development()


if __name__ == "__main__":
    main()
