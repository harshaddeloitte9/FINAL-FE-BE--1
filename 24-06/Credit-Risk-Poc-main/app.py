"""
app.py - Credit Risk ML POC — Adaptive Machine Learning Platform
Run with: streamlit run app.py
"""

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
    :root { color-scheme: dark; }
    body, .stApp { font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }
    .stApp { background: #0b1222; color: #e2e8f0; }
    .main .block-container { padding: 1.75rem 2rem 2rem; max-width: 1480px; }

    section[data-testid="stSidebar"] {
        background: #111827 !important;
        color: #e2e8f0 !important;
        border-right: 1px solid #1f2937;
    }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

    .sidebar-branding { padding: 1.2rem 1rem 0.75rem; text-align: center; }
    .sidebar-branding h2 { margin: 0.3rem 0 0.1rem; color: #86bc25; font-size: 1.3rem; }
    .sidebar-branding p { margin: 0; color: #94a3b8; font-size: 0.83rem; }
    .sidebar-step {
        padding: 0.75rem 0.85rem;
        border-radius: 0.95rem;
        margin: 0.35rem 0;
        border: 1px solid #1f2937;
        transition: all 0.15s ease-in-out;
        color: #cbd5e1;
    }
    .sidebar-step:hover { background: rgba(134, 188, 37, 0.09); }
    .sidebar-step-active {
        background: rgba(134, 188, 37, 0.14);
        border-color: #86bc25;
        color: #f8fafc;
    }
    .sidebar-step span { display: inline-block; width: 1.6rem; text-align: center; margin-right: 0.65rem; color: #94a3b8; }
    .placeholder-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 1rem;
        padding: 1rem;
        margin-top: 1rem;
    }
    .placeholder-card h4 { margin: 0 0 0.5rem; color: #86bc25; }
    .placeholder-card p { margin: 0; color: #cbd5e1; font-size: 0.92rem; line-height: 1.6; }

    .panel-card {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(148, 163, 184, 0.06);
        border-radius: 1.25rem;
        padding: 1.45rem;
        box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
    }
    .step-header {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.92));
        border-left: 4px solid #86bc25;
        border-radius: 1rem;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 14px 32px rgba(0, 0, 0, 0.14);
    }
    .step-header h3 { margin: 0; color: #f8fafc; font-size: 1.5rem; font-weight:600; }
    .step-header p { margin: 0.35rem 0 0; color: #94a3b8; }

    .insight-box {
        :root { color-scheme: light; }
        body, .stApp { font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }
        .stApp { background: #fafafa; color: #0f172a; }
        border: 1px solid rgba(134, 188, 37, 0.18);
        border-radius: 1rem;
        padding: 1rem 1.1rem;
        margin: 0.9rem 0;
    }
    .insight-box h4 { margin: 0 0 0.5rem; color: #f8fafc; }
    .insight-box p, .insight-box li { color: #cbd5e1; }

    .stButton button {
        section[data-testid="stSidebar"] {
            background: #ffffff !important;
            color: #0f172a !important;
            border-right: 1px solid #e6e9ee;
        }
        section[data-testid="stSidebar"] * { color: #0f172a !important; }
        letter-spacing: 0.01em;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28) !important;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    .stButton button:hover { transform: translateY(-2px); box-shadow: 0 14px 40px rgba(0,0,0,0.36) !important; }

    .streamlit-expanderHeader { background: rgba(17, 24, 39, 0.95) !important; color: #e2e8f0 !important; border-radius: 0.95rem !important; }
    .streamlit-expanderContent { background: #0f172a !important; border-radius: 0 0 0.95rem 0.95rem !important; }

    .stDataFrame, .element-container { border-radius: 1rem !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; background: transparent; }
    .stTabs [data-baseweb="tab"] {
        background: #111827;
        color: #cbd5e1;
        border-radius: 0.75rem 0.75rem 0 0;
        border: 1px solid #1f2937;
        padding: 0.45rem 1rem;
        .sidebar-branding { padding: 1rem 1rem; text-align: left; }
        .sidebar-branding h2 { margin: 0.1rem 0 0.15rem; color: #111827; font-size: 1.05rem; }
        .sidebar-branding p { margin: 0; color: #6b7280; font-size: 0.75rem; }
    .stProgress .st-bo { background: #86bc25; }
    [data-testid="stMetricValue"] { color: #86bc25 !important; font-size: 1.85rem !important; }
    [data-testid="stMetricLabel"] { color: #cbd5e1 !important; }

    .stTextInput>div>div>input, .stSelectbox>div>div>div>div, .stSlider>div>div>div>div {
        border-radius: 0.85rem !important;
    }

    /* Landing hero */
        .placeholder-card {
            background: #ffffff;
            border: 1px solid #eef2f6;
            border-radius: 0.75rem;
            padding: 0.9rem;
            margin-top: 0.9rem;
        }
        .placeholder-card h4 { margin: 0 0 0.4rem; color: #86bc25; }
        .placeholder-card p { margin: 0; color: #374151; font-size: 0.9rem; line-height: 1.5; }
    }
    .hero-card {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(134, 188, 37, 0.18);
        border-radius: 1.25rem;
        padding: 1.6rem;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
        min-height: 320px;
    }
    .hero-card:hover { transform: translateY(-4px); box-shadow: 0 24px 58px rgba(0, 0, 0, 0.28); }
    .hero-card h2 { margin:0 0 0.75rem; color:#f8fafc; font-size:1.85rem; }
    .hero-card p { margin:0 0 1rem; color:#cbd5e1; font-size:0.96rem; line-height:1.75; }
    .hero-card ul { margin: 0; padding-left: 1.2rem; color: #cbd5e1; }
    .hero-card ul li { margin-bottom: 0.6rem; }
    .hero-card .hero-badge { display:inline-flex; align-items:center; gap:0.45rem; margin-bottom:1rem; color:#d9f99d; font-size:0.75rem; letter-spacing:0.2em; text-transform:uppercase; }
    .workspace-pill {
        display:inline-flex; align-items:center; justify-content:center; gap:0.4rem;
        border-radius:999px; padding:0.65rem 1rem; font-size:0.84rem; font-weight:700;
        letter-spacing:0.12em; text-transform:uppercase; border:1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.04); color:#f8fafc;
    }
    .workspace-pill.active { background: linear-gradient(135deg, #86bc25, #5c8c13); color:#fff; border-color: rgba(134,188,37,0.4); }
</style>""", unsafe_allow_html=True)

from utils import (
    generate_synthetic_credit_dataset, detect_column_types,
    detect_target_candidates, detect_task_type,
    df_to_csv_download, model_to_download,
)
from preprocessing import (
    build_preprocessing_report, prepare_data, rebuild_preprocessor_for
)
from feature_engineering import (
    analyze_for_feature_engineering, apply_feature_engineering,
    compute_univariate_gini,
)
from model_selector import (
    recommend_models, CLASSIFICATION_MODELS, REGRESSION_MODELS
)
from train import split_data, compute_split_stats, train_model
import ecl_engine as ecl
from evaluate import (
    compute_binary_metrics, compute_regression_metrics,
    compute_heteroscedasticity_check,
    plot_roc_curve, plot_pr_curve, plot_confusion_matrix,
    plot_score_distribution, plot_threshold_analysis, plot_lift_chart
)
from explainability import (
    extract_feature_importance, compute_shap_values,
    plot_feature_importance_bar, plot_shap_summary_plotly,
    plot_shap_waterfall_single, generate_prediction_reasoning,
    generate_model_summary
)

try:
    from agent2 import Agent2 as _Agent2
    _AGENT2_AVAILABLE = True
except Exception:
    _AGENT2_AVAILABLE = False
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
        "workspace": None,
        "data_source": None,
        "agent2": None,
        "agent2_report": {},
        "model_tier": None,
        "leakage_risk_cols": [],
        "date_integrity": {},
        "gini_scores": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ─────────────────────────────────────────────
# Agent 2 helpers
# ─────────────────────────────────────────────
def _get_agent2():
    """Return the Agent2 singleton from session state, initializing it lazily."""
    if not _AGENT2_AVAILABLE:
        return None
    if st.session_state.get("agent2") is None:
        try:
            st.session_state["agent2"] = _Agent2("rag_store/rules.json")
        except Exception:
            return None
    return st.session_state.get("agent2")


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
    with st.sidebar:
        st.markdown("""
        <div class='sidebar-branding'>
            <div style='display:flex;justify-content:center;align-items:center;gap:0.65rem;'>
                <div style='width:2.6rem;height:2.6rem;border-radius:1rem;background:linear-gradient(135deg,#86bc25,#5c8c13);display:flex;align-items:center;justify-content:center;box-shadow:0 18px 30px rgba(0,0,0,0.16);'>
                    <span style='font-size:1.3rem;font-weight:700;color:#0b1222;'>A</span>
                </div>
                <div style='text-align:left;'>
                    <h2>Aegis Credit</h2>
                    <p>Model Development</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🧭 Workflow Progress")

        steps = [
            ("1", "📂 Data Upload", 1),
            ("2", "🔍 Data Profiling", 2),
            ("3", "⚙️ Preprocessing", 3),
            ("4", "🔬 Feature Engineering", 4),
            ("5", "🤖 Model Selection", 5),
            ("6", "🎯 Training", 6),
            ("7", "📊 Evaluation", 7),
            ("8", "💡 Explainability", 8),
            ("9", "🏦 ECL & Provisions", 9),
        ]

        current = st.session_state.current_step
        for num, label, step_id in steps:
            if step_id == current:
                style = "sidebar-step-active"
            else:
                style = "sidebar-step"
            icon = "✅" if step_id < current else ("▶️" if step_id == current else "⏳")
            st.markdown(
                f"<div class='{style}'><span>{icon}</span>{label}</div>",
                unsafe_allow_html=True
            )

        st.markdown("""
        <div class='placeholder-card'>
            <h4>Lovable Insights</h4>
            <p>AI assistant workflows and regulator-grade guidance are not yet connected in this POC. This placeholder preserves the polished layout without changing backend functionality.</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown("### ⚙️ Global Settings")
        st.session_state.decision_threshold = st.slider("Decision Threshold (Eval Step)", 0.1, 0.9, 0.5, 0.05)

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

    workspace = st.session_state.get("workspace")
    if workspace is None:
        st.markdown("""
        <div style='margin-bottom:1rem;'>
            <div style='display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem;'>
                <div style='width:12px;height:12px;border-radius:999px;background:#86bc25;'></div>
                <div style='color:#d9f99d;font-size:0.78rem;letter-spacing:0.18em;text-transform:uppercase;'>Enterprise AI platform</div>
            </div>
            <h1 style='margin:0.4rem 0 0.75rem;color:#f8fafc;font-size:3rem;line-height:1.05;'>Choose your workspace</h1>
            <p style='margin:0;color:#cbd5e1;max-width:920px;font-size:1rem;line-height:1.75;'>Aegis Credit unifies model development and independent validation in a single, polished platform. Pick the workspace that matches your role.</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1,1], gap='large')
        with col1:
            st.markdown("""
            <div class='hero-card'>
                <div style='display:flex;align-items:center;gap:0.9rem;margin-bottom:1.2rem;'>
                    <div style='width:48px;height:48px;border-radius:14px;background:rgba(134,188,37,0.18);display:flex;align-items:center;justify-content:center;color:#86bc25;font-weight:700;'>📈</div>
                    <div>
                        <div class='hero-badge'>Workspace 01</div>
                        <h2>Model Development</h2>
                    </div>
                </div>
                <p>Build, train, evaluate, and explain credit risk models with a full end-to-end workflow.</p>
                <ul>
                    <li>Data upload, profiling, preprocessing, and modeling</li>
                    <li>Live metrics, SHAP explainability, and ECL output</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Model Development", key='open_dev', use_container_width=True):
                st.session_state.workspace = 'development'

        with col2:
            st.markdown("""
            <div class='hero-card'>
                <div style='display:flex;align-items:center;gap:0.9rem;margin-bottom:1.2rem;'>
                    <div style='width:48px;height:48px;border-radius:14px;background:rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:center;color:#86bc25;font-weight:700;'>🛡️</div>
                    <div>
                        <div class='hero-badge'>Workspace 02</div>
                        <h2>Model Validation</h2>
                    </div>
                </div>
                <p>Independently validate models for performance, governance, and regulatory soundness.</p>
                <ul>
                    <li>Champion / challenger benchmarking and evidence generation</li>
                    <li>IFRS 9 / IFRS 7 / SS1/23 review support</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Model Validation", key='open_val', use_container_width=True):
                st.session_state.workspace = 'validation'

        return

    df = st.session_state.df

    if df is not None:
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
        <div style='margin-bottom:1rem;'>
            <div style='display:flex;align-items:center;gap:1rem;'>
                <div style='background:rgba(134,188,37,0.12);padding:0.35rem 0.6rem;border-radius:999px;color:#86bc25;font-weight:700;'>ENTERPRISE AI PLATFORM</div>
            </div>
            <h1 style='margin:0.8rem 0 0.6rem;color:#f8fafc;font-size:2.4rem;'>Upload or generate a dataset</h1>
            <p style='margin:0;color:#cbd5e1;max-width:880px;'>Start the {st.session_state.workspace.title()} workflow by uploading your file or using the built-in synthetic credit dataset.</p>
        </div>
        """, unsafe_allow_html=True)

        st.info(f"Workspace selected: {workspace.title()}")

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

    target_col = st.selectbox(
        "Select target variable",
        options=all_cols,
        index=default_idx,
        help="The system will detect binary/multiclass/regression task automatically.",
    )
    st.session_state.target_col = target_col

    # Detect task type
    task_type = detect_task_type(df[target_col])
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
                st.warning(f"⚠️ Imbalanced dataset detected (ratio ≈ {ratio:.1f}:1). SMOTE is recommended in the sidebar.")
            else:
                st.success("✅ Class distribution is reasonably balanced.")

    # ── Agent 2 — data compliance ──
    _a2 = _get_agent2()
    if _a2 is not None:
        _first = "agent2_flags_data" not in st.session_state
        _run_agent2_stage("data", _a2.check_data, df, col_types,
                          leakage_risk_cols=st.session_state.get("leakage_risk_cols"))
        if _first:
            _a2.check_rules_from_agent1("data", {
                "n_rows": len(df),
                "n_cols": len(df.columns),
                "missing_pct": round(float(df.isna().mean().mean()), 4),
                "target_col": target_col,
            })
            st.session_state["agent2_flags_data"] = _a2.get_stage_summary("data")["flags"]
            st.session_state["agent2_report"] = _a2.get_full_report()
        _render_compliance_banner("Data Profiling", st.session_state["agent2_flags_data"])

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
        st.session_state.pop("agent2_flags_data", None)
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
        <h3>⚙️ Step 3 — Adaptive Data Preprocessing</h3>
        <p>Dynamic preprocessing pipeline built based on dataset characteristics</p>
    </div>
    """, unsafe_allow_html=True)

    df = st.session_state.df
    col_types = st.session_state.col_types
    target_col = st.session_state.target_col

    with st.spinner("🔧 Building adaptive preprocessing pipeline..."):
        X, y, preprocessor, report, feature_names = prepare_data(df, col_types, target_col)

    st.session_state.X = X
    st.session_state.y = y
    st.session_state.preprocessor = preprocessor
    st.session_state.prep_report = report
    st.session_state.feature_names = feature_names

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Features After Prep", X.shape[1])
    c2.metric("🗑️ Duplicates Removed", report.get("duplicates_removed", 0))
    c3.metric("🔢 Numeric Columns", len(report["numeric"]))
    c4.metric("🏷️ Categorical Columns", len(report["categorical"]))

    st.markdown("#### 🧠 Preprocessing Decisions")
    st.info("ℹ️ The system automatically chose preprocessing strategies based on skewness, outliers, missing %, and cardinality.")

    decisions = report.get("decisions", [])
    if decisions:
        for dec in decisions:
            col_type_icon = {"numeric": "🔢", "categorical": "🏷️", "datetime": "📅", "boolean": "✅"}.get(dec["type"], "📌")
            with st.expander(f"{col_type_icon} **{dec['column']}** ({dec['type']})", expanded=False):
                for action in dec["actions"]:
                    st.markdown(f"- {action}")

    # Missing value strategy summary
    if report["numeric"] or report["categorical"]:
        st.markdown("#### 📊 Preprocessing Strategy Summary")
        summary_rows = []
        for col, info in report["numeric"].items():
            summary_rows.append({
                "Column": col, "Type": "Numeric",
                "Scaler": info["scaler"].capitalize(),
                "Imputer": info["imputer"].capitalize(),
                "Outliers": "Yes" if info["has_outliers"] else "No",
                "Log Transform": "Suggested" if info["needs_log"] else "-",
                "Missing %": f"{info['missing_pct']:.1%}",
            })
        for col, info in report["categorical"].items():
            summary_rows.append({
                "Column": col, "Type": "Categorical",
                "Scaler": "-",
                "Imputer": "Mode",
                "Outliers": "-",
                "Log Transform": "-",
                "Missing %": f"{info['missing_pct']:.1%}",
            })
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

    # Preview features
    st.markdown("#### 🔎 Feature Matrix Preview (X)")
    st.dataframe(X.head(5), use_container_width=True)

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

    X = st.session_state.X
    y = st.session_state.y
    col_types = st.session_state.col_types
    task_type = st.session_state.task_type

    with st.spinner("🔬 Analyzing dataset for feature engineering opportunities..."):
        plan = analyze_for_feature_engineering(X, y, col_types, task_type)

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
        iv_df = pd.DataFrame(list(plan["iv_scores"].items()), columns=["Feature", "IV"])
        iv_df = iv_df.sort_values("IV", ascending=False).head(20)
        st.dataframe(iv_df, use_container_width=True)
        st.caption("WOE copies are created for the top IV features only; very low-IV features are removed with IV < 0.02.")

    # ── Univariate Gini ───────────────────────────────────────────────────────
    if task_type == "binary" and col_types.get("numeric"):
        with st.spinner("Computing univariate Gini coefficients..."):
            _gini = compute_univariate_gini(X, y, col_types.get("numeric", []))
        st.session_state["gini_scores"] = _gini
        if _gini:
            st.markdown("#### 📐 Univariate Gini Coefficients")
            _gini_df = pd.DataFrame(
                list(_gini.items()), columns=["Feature", "Gini Coefficient"]
            )
            st.dataframe(_gini_df, use_container_width=True)

    # Apply feature engineering
    with st.spinner("Applying feature transformations..."):
        X_engineered, fe_summary = apply_feature_engineering(X, y, plan)

    st.session_state.fe_plan = plan
    st.session_state.fe_summary = fe_summary
    st.session_state.X_engineered = X_engineered

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
    st.markdown("#### 🔎 Engineered Feature Matrix Preview")
    st.dataframe(X_engineered.head(5), use_container_width=True)

    # ── Agent 2 — feature compliance ──
    _a2 = _get_agent2()
    if _a2 is not None:
        _first = "agent2_flags_feature" not in st.session_state
        _run_agent2_stage("feature", _a2.check_features, plan,
                          all_columns=list(st.session_state.df.columns))
        if _first:
            _a2.check_rules_from_agent1("feature", {
                "n_features": int(X_engineered.shape[1]),
                "features_removed": fe_summary.get("features_removed", 0),
                "features_added": fe_summary.get("features_added", 0),
            })
            st.session_state["agent2_flags_feature"] = _a2.get_stage_summary("feature")["flags"]
            st.session_state["agent2_report"] = _a2.get_full_report()
        _render_compliance_banner("Feature Engineering", st.session_state["agent2_flags_feature"])

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

    X = (
    st.session_state.X_engineered
    if st.session_state.X_engineered is not None
    else st.session_state.X
    )
    y = st.session_state.y
    task_type = st.session_state.task_type

    n_samples, n_features = X.shape
    imbalance_ratio = 1.0
    if task_type == "binary":
        vc = y.value_counts()
        imbalance_ratio = vc.max() / vc.min() if vc.min() > 0 else 5.0

    recommendations = recommend_models(n_samples, n_features, imbalance_ratio, task_type)

    st.markdown(f"#### 📊 Dataset: {n_samples:,} samples × {n_features} features | Imbalance ratio: {imbalance_ratio:.1f}:1")

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

    X = (
    st.session_state.X_engineered
    if st.session_state.X_engineered is not None
    else st.session_state.X
    )
    y = st.session_state.y
    col_types = st.session_state.col_types
    prep_report = st.session_state.prep_report
    target_col = st.session_state.target_col
    task_type = st.session_state.task_type
    threshold = getattr(st.session_state, "decision_threshold", 0.5)
    selected_model_name = getattr(st.session_state, "selected_model", None)

    if selected_model_name is None:
        st.warning("Please complete Model Selection first.")
        return

    # ── Data Split ──
    st.markdown("#### 📊 Data Split")
    sp_col1, sp_col2, sp_col3 = st.columns(3)
    with sp_col1:
        test_size = st.slider("Test set size", 5, 35, 15, 5, key="ts_slider") / 100
    with sp_col2:
        val_size = st.slider("Validation set size", 5, 25, 15, 5, key="vs_slider") / 100
    with sp_col3:
        random_seed = st.number_input("Random seed", min_value=0, max_value=9999, value=42, key="seed_inp")

    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X, y, test_size=test_size, val_size=val_size,
        task_type=task_type, random_state=int(random_seed)
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
                          title="Class Distribution per Split")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#e2e8f0"))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Class Balancing ──
    st.markdown("#### ⚖️ Class Balancing")
    vc = y_train.value_counts()
    imbalance = vc.max() / vc.min() if vc.min() > 0 else 1.0

    bal_col1, bal_col2 = st.columns(2)
    with bal_col1:
        use_smote = st.checkbox(
            f"Apply SMOTE (oversample minority class — imbalance ratio {imbalance:.1f}:1)",
            value=(imbalance > 2 and task_type == "binary"),
        )
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

    # ── Agent 2 — training compliance (shown once pipeline is ready) ──
    if st.session_state.trained_pipeline is not None:
        _a2 = _get_agent2()
        if _a2 is not None:
            _t_cfg = {
                "model_name": st.session_state.get("final_model_name", selected_model_name),
                "multiple_models_compared": st.session_state.get("model_comparison_results") is not None,
                "use_cv": use_cv,
                "use_smote": use_smote and task_type == "binary",
            }
            _first = "agent2_flags_training" not in st.session_state
            _yt = st.session_state.get("y_train")
            _vc = _yt.value_counts() if _yt is not None else None
            _imb_ratio = float(_vc.max() / _vc.min()) if (_vc is not None and _vc.min() > 0) else None
            _run_agent2_stage(
                "training", _a2.check_training, _t_cfg,
                training_info=st.session_state.get("training_info"),
                test_auc=(st.session_state.get("eval_metrics") or {}).get("roc_auc"),
                imbalance_ratio=_imb_ratio,
                task_type=task_type,
            )
            if _first:
                _a2.check_rules_from_agent1("training", {
                    "model_name": st.session_state.get("final_model_name", selected_model_name),
                    "use_cv": use_cv,
                })
                st.session_state["agent2_flags_training"] = _a2.get_stage_summary("training")["flags"]
                st.session_state["agent2_report"] = _a2.get_full_report()
            _render_compliance_banner("Training", st.session_state["agent2_flags_training"])

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

    # ── Agent 2 — evaluation compliance + model risk tier ──
    _a2 = _get_agent2()
    if _a2 is not None and task_type == "binary":
        _e_cfg = dict(
            metrics=metrics,
            training_info=st.session_state.get("training_info") or {},
            threshold=threshold,
            explainability_done=bool(st.session_state.get("shap_result")),
            heteroscedasticity_result=hetero_check,
            pd_output_present=False,
            staging_logic_present=False,
            sicr_flagged=False,
            ecl_estimated=False,
            concentration_analysis=False,
            exposure_reported=False,
            past_due_breakdown=False,
            shap_available=bool(st.session_state.get("shap_result")),
        )
        _first_eval = "agent2_flags_evaluation" not in st.session_state
        _run_agent2_stage("evaluation", _a2.check_evaluation, **_e_cfg)
        if _first_eval:
            _a2.check_rules_from_agent1("evaluation", {
                "roc_auc": metrics.get("roc_auc"),
                "recall": metrics.get("recall"),
                "precision": metrics.get("precision"),
                "pr_auc": metrics.get("pr_auc"),
                "threshold": threshold,
            })
            st.session_state["agent2_flags_evaluation"] = _a2.get_stage_summary("evaluation")["flags"]
        _render_compliance_banner("Evaluation", st.session_state["agent2_flags_evaluation"])

        # Model risk tier (SS1/23 Principle 1.3) — compute once
        if not st.session_state.get("model_tier"):
            _y_train = st.session_state.get("y_train")
            _y_val   = st.session_state.get("y_val")
            _n_samp  = sum(len(s) for s in [_y_train, _y_val, y_test] if s is not None)
            _imb = 1.0
            if _y_train is not None:
                _vc = _y_train.value_counts()
                _imb = float(_vc.max() / _vc.min()) if _vc.min() > 0 else 1.0
            _tier_cfg = {
                "model_name": st.session_state.get("final_model_name", ""),
                "n_samples": _n_samp,
                "class_imbalance_ratio": _imb,
                "use_cv": bool((st.session_state.get("training_info") or {}).get("cv_mean")),
                "multiple_models_compared": st.session_state.get("model_comparison_results") is not None,
                "explainability_done": bool(st.session_state.get("shap_result")),
            }
            st.session_state["model_tier"] = _a2.tier_model(
                training_config=_tier_cfg,
                metrics=metrics,
                fe_summary=st.session_state.get("fe_summary"),
            )
        st.session_state["agent2_report"] = _a2.get_full_report()
        if st.session_state.get("model_tier"):
            _render_tier_card(st.session_state["model_tier"])

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
                         "Residual Check"])

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
            X_final = st.session_state.X_engineered if st.session_state.X_engineered is not None else st.session_state.X
            if X_final is not None and st.session_state.y is not None:
                processed_df = X_final.copy()
                processed_df[st.session_state.target_col] = st.session_state.y.values
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
        if st.button("▶️ Proceed to ECL Calculation", type="primary", use_container_width=True):
            st.session_state.current_step = 9
            st.rerun()


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
def render_header():
    workspace = st.session_state.get("workspace")
    cols = st.columns([2.6, 2, 1])
    with cols[0]:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:0.9rem;margin-bottom:0.75rem;'>
                <div style='width:44px;height:44px;border-radius:14px;background:linear-gradient(135deg,#86bc25,#5c8c13);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;box-shadow:0 12px 28px rgba(3,7,18,0.12);'>A</div>
                <div>
                    <div style='font-size:0.78rem;color:#86bc25;text-transform:uppercase;letter-spacing:0.16em;margin-bottom:0.15rem;'>Aegis Credit</div>
                    <div style='font-size:1.05rem;font-weight:700;color:#f8fafc;'>AI Model Platform</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if workspace:
            st.markdown(
                f"""
                <div style='display:inline-flex;align-items:center;gap:0.6rem;padding:0.45rem 0.95rem;border-radius:999px;background:rgba(134,188,37,0.12);color:#d9f99d;font-size:0.86rem;font-weight:600;'>
                    <span style='width:8px;height:8px;background:#86bc25;border-radius:999px;display:inline-block;'></span>
                    {workspace.title()} workspace active
                </div>
                """,
                unsafe_allow_html=True,
            )
    with cols[1]:
        button_cols = st.columns([1,1])
        with button_cols[0]:
            if st.button("Develop", key="header_dev", use_container_width=True):
                st.session_state.workspace = "development"
        with button_cols[1]:
            if st.button("Validate", key="header_val", use_container_width=True):
                st.session_state.workspace = "validation"
    with cols[2]:
        st.markdown(
            """
            <div style='display:flex;align-items:center;justify-content:flex-end;gap:0.8rem;'>
                <div style='width:40px;height:40px;border-radius:999px;background:#0f172a;border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;'>AK</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
# STEP 9: ECL Calculation
# ─────────────────────────────────────────────
def render_ecl():
    st.markdown("""
    <div class='step-header'>
        <h3>\U0001F3E6 Step 9 — ECL Calculation</h3>
        <p>Expected Credit Loss from the trained model's PD &mdash; ECL = PD \u00d7 LGD \u00d7 EAD (no staging)</p>
    </div>
    """, unsafe_allow_html=True)

    pipeline = st.session_state.trained_pipeline
    X_full = st.session_state.X_engineered if st.session_state.X_engineered is not None else st.session_state.X
    if pipeline is None or X_full is None:
        st.warning("Train a model first (Step 6).")
        return

    raw = st.session_state.df
    try:
        data = raw.loc[X_full.index]
    except Exception:
        data = raw.iloc[:len(X_full)].copy()
        data.index = X_full.index

    num_cols = ecl.numeric_columns(data)
    if not num_cols:
        st.error("No numeric column is available to use as exposure (EAD).")
        return
    default_ead = ecl.detect_exposure_col(data) or num_cols[0]
    ltv_default = ecl.detect_ltv_col(data)

    st.markdown("#### Inputs")
    c1, c2 = st.columns(2)
    with c1:
        ead_col = st.selectbox("Exposure at Default (EAD) column", num_cols,
                               index=num_cols.index(default_ead))
        st.caption("PD is read directly from the trained model's predicted default probability.")
    with c2:
        lgd_mode = st.radio("Loss Given Default (LGD) method",
                            ["Fixed assumption", "By loan type", "From LTV column"],
                            horizontal=False)

    # ── LGD configuration ──
    loan_type_col = None
    lgd_map = None

    if lgd_mode == "Fixed assumption":
        lgd_fixed = st.slider("LGD assumption (all loans)", 0.05, 0.95, 0.45, 0.05)
        cfg = ecl.ECLConfig(lgd_method="fixed", lgd_fixed=lgd_fixed)

    elif lgd_mode == "By loan type":
        all_cols = data.columns.tolist()
        cat_cols = [c for c in all_cols if data[c].dtype == object or data[c].nunique() <= 20]
        if not cat_cols:
            st.warning("No categorical columns detected. Switch to 'Fixed assumption'.")
            cfg = ecl.ECLConfig()
        else:
            loan_type_col = st.selectbox(
                "Column that identifies loan type",
                cat_cols,
                help="Each unique value in this column gets its own LGD slider."
            )
            loan_types = sorted(data[loan_type_col].dropna().astype(str).unique())
            st.markdown(f"**Set LGD for each `{loan_type_col}` value:**")

            defaults = {lt: round(0.30 + (i * 0.05) % 0.65, 2) for i, lt in enumerate(loan_types)}
            lgd_map = {}
            cols_per_row = 3
            for row_start in range(0, len(loan_types), cols_per_row):
                row_types = loan_types[row_start: row_start + cols_per_row]
                slider_cols = st.columns(len(row_types))
                for col_widget, lt in zip(slider_cols, row_types):
                    with col_widget:
                        lgd_map[lt] = st.slider(
                            f"LGD — {lt}", 0.05, 0.95,
                            float(defaults[lt]), 0.05,
                            key=f"lgd_type_{lt}"
                        )
            cfg = ecl.ECLConfig(lgd_method="fixed", lgd_fixed=0.45)

    else:  # From LTV column
        lc1, lc2 = st.columns(2)
        with lc1:
            ltv_idx = num_cols.index(ltv_default) if ltv_default in num_cols else 0
            ltv_col = st.selectbox("LTV column", num_cols, index=ltv_idx)
        with lc2:
            haircut = st.slider("Collateral haircut", 0.0, 0.6, 0.20, 0.05)
        cfg = ecl.ECLConfig(lgd_method="ltv", ltv_col=ltv_col, lgd_haircut=haircut)

    if st.button("💰 Calculate ECL", type="primary", use_container_width=True):
        try:
            res, summary = ecl.compute(
                pipeline, X_full, data, ead_col=ead_col, cfg=cfg,
                loan_type_col=loan_type_col, lgd_map=lgd_map,
            )
            st.session_state.ecl_result = res
            st.session_state.ecl_summary = summary
        except Exception as e:
            st.error(f"ECL calculation failed: {e}")
            return

    res = st.session_state.get("ecl_result")
    summary = st.session_state.get("ecl_summary")
    if res is not None and summary is not None:
        st.markdown("#### Portfolio result")
        m = st.columns(4)
        m[0].metric("Total ECL", f"{summary['total_ecl']:,.0f}")
        m[1].metric("Total EAD", f"{summary['total_ead']:,.0f}")
        m[2].metric("Coverage", f"{summary['coverage_pct']}%")
        m[3].metric("Avg PD", f"{summary['avg_pd']:.1%}")

        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(ecl.plot_ecl_by_pd_band(res), use_container_width=True)
        with g2:
            st.plotly_chart(ecl.plot_pd_distribution(res), use_container_width=True)

        st.markdown("#### Per-loan ECL (top 20 by ECL)")
        st.dataframe(res.sort_values("ecl", ascending=False).head(20), use_container_width=True)
        df_to_csv_download(res.copy(), "ecl_results.csv")

    st.divider()
    if st.button("\u25c0 Back to Explainability", use_container_width=True):
        st.session_state.current_step = 8
        st.rerun()


# ─────────────────────────────────────────────
# Main Router
# ─────────────────────────────────────────────
def main():
    render_sidebar()
    render_header()

    step = st.session_state.current_step

    if step == 1:
        render_upload()
    elif step == 2:
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
    elif step == 9:
        if st.session_state.trained_pipeline is None:
            st.session_state.current_step = 6
            st.rerun()
        render_ecl()


if __name__ == "__main__":
    main()
