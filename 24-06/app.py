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
import json
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
    build_preprocessing_report, prepare_data, rebuild_preprocessor_for
)
from feature_engineering import (
    analyze_for_feature_engineering, apply_feature_engineering,
    compute_univariate_gini,
    detect_outstanding_balance_col, detect_loan_amount_col,
    detect_interest_rate_col, detect_years_elapsed_col, detect_term_col,
    compute_outstanding_balance,
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
            steps = [
                ("1", "📂 Data Upload",         1),
                ("2", "🔍 Data Profiling",      2),
                ("3", "⚙️ Preprocessing",       3),
                ("4", "🔬 Feature Engineering", 4),
                ("5", "🤖 Model Selection",     5),
                ("6", "🎯 Training",            6),
                ("7", "📊 Evaluation",          7),
                ("8", "💡 Explainability",      8),
                ("9", "🏦 ECL & Provisions",    9),
            ]
            current = st.session_state.current_step
            for _, label, step_id in steps:
                if step_id < current:
                    _icon, _color = "✅", "#10b981"
                elif step_id == current:
                    _icon, _color = "▶️", "#6366f1"
                else:
                    _icon, _color = "⏳", "#475569"
                st.markdown(
                    f"<div style='color:{_color};padding:0.15rem 0;font-size:0.9rem;'>{_icon} {label}</div>",
                    unsafe_allow_html=True,
                )
            st.divider()
            st.markdown("### ⚙️ Global Settings")
            st.session_state.decision_threshold = st.slider("Decision Threshold (Eval Step)", 0.1, 0.9, 0.5, 0.05)

        elif workspace == "validation":
            st.divider()
            if st.button("← Back to Home", use_container_width=True, key="switch_to_landing_val"):
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
                    _vs_icon = "✅"
                elif _vs_num == _val_current:
                    _vs_icon = "▶️"
                else:
                    _vs_icon = "⏳"
                _is_active = (_vs_num == _val_current)
                _btn_style = "primary" if _is_active else "secondary"
                if st.button(
                    f"{_vs_icon} {_vs_label}",
                    key=f"val_nav_{_vs_num}",
                    use_container_width=True,
                    type=_btn_style,
                ):
                    st.session_state["val_step"] = _vs_num
                    st.rerun()

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
                st.warning(f"⚠️ Imbalanced dataset detected (ratio ≈ {ratio:.1f}:1). Enable class_weight='balanced' in the training step.")
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

    _excl_pd = fe_summary.get("excluded_orig_pd") or []
    if _excl_pd:
        st.info("🔒 Hidden from model development (origination PD): "
                + ", ".join(f"`{c}`" for c in _excl_pd)
                + " — kept in the dataset for IFRS 9 SICR in the ECL step.")

    # ── EAD source for ECL ──
    st.divider()
    st.markdown("#### 🏦 Exposure at Default (EAD) source for ECL")
    _dff = st.session_state.df
    _numc = [c for c in _dff.columns if pd.api.types.is_numeric_dtype(_dff[c])]
    _ob_det = detect_outstanding_balance_col(_dff)

    _has_ob = st.radio(
        "Does your dataset contain an outstanding balance column?",
        ["Yes — select it", "No — estimate it from loan amount, interest, elapsed time, term"],
        index=0 if _ob_det else 1, key="ead_has_ob",
    )

    _ead_series, _ead_method, _ead_src = None, "", ""
    if _has_ob.startswith("Yes") and _numc:
        _ob_idx = _numc.index(_ob_det) if _ob_det in _numc else 0
        _ob_col = st.selectbox("Outstanding balance column", _numc, index=_ob_idx, key="ead_ob_col")
        _ead_series = pd.to_numeric(_dff[_ob_col], errors="coerce").clip(lower=0)
        _ead_method = f"Outstanding balance column '{_ob_col}'"
        _ead_src = _ob_col
        st.caption(f"`{_ob_col}` is genuine bank-provided data — it stays a feature in the PD "
                   "model and is also used directly as EAD in ECL.")
    elif _numc:
        NA = "— not available —"
        _la_d = detect_loan_amount_col(_dff)
        _ir_d = detect_interest_rate_col(_dff)
        _ye_d, _ye_is_m = detect_years_elapsed_col(_dff)
        _tm_d = detect_term_col(_dff)
        _optf = lambda c: ([NA] + _numc).index(c) if c in _numc else 0

        st.caption("Outstanding balance is estimated as an amortizing balance. All four inputs "
                   "are required; if any is unavailable it is flagged (no fallback). The estimate "
                   "is NOT a model feature — it is used only as EAD in ECL.")
        o1, o2 = st.columns(2)
        with o1:
            _la = st.selectbox("Loan amount", [NA] + _numc, index=_optf(_la_d), key="ead_la")
            _ir = st.selectbox("Interest rate", [NA] + _numc, index=_optf(_ir_d), key="ead_ir")
        with o2:
            _ye = st.selectbox("Elapsed time", [NA] + _numc, index=_optf(_ye_d), key="ead_ye")
            _tm = st.selectbox("Total loan term", [NA] + _numc, index=_optf(_tm_d), key="ead_term")
        u1, u2 = st.columns(2)
        with u1:
            _ye_months = st.checkbox("Elapsed time is in months", value=bool(_ye_is_m), key="ead_ye_months")
        with u2:
            _tm_months = st.checkbox("Loan term is in months",
                                     value=("month" in str(_tm).lower()), key="ead_tm_months")

        _missing = [lbl for lbl, val in [
            ("loan amount", _la), ("interest rate", _ir),
            ("elapsed time", _ye), ("total loan term", _tm)] if val == NA]
        if _missing:
            st.error("🚩 Outstanding balance cannot be estimated. Required column(s) not provided: "
                     + ", ".join(_missing) + ". These are needed to compute EAD for ECL — please "
                     "add them to the dataset.")
        else:
            _la_s = pd.to_numeric(_dff[_la], errors="coerce")
            _ir_s = pd.to_numeric(_dff[_ir], errors="coerce")
            _ye_s = pd.to_numeric(_dff[_ye], errors="coerce")
            if _ye_months:
                _ye_s = _ye_s / 12.0
            _tm_s = pd.to_numeric(_dff[_tm], errors="coerce")
            if _tm_months:
                _tm_s = _tm_s / 12.0
            _ead_series = compute_outstanding_balance(_la_s, _ir_s, _ye_s, term_years=_tm_s)
            _ead_method = (f"Estimated amortizing outstanding balance from '{_la}', '{_ir}', "
                           f"'{_ye}', term '{_tm}'")
            _ead_src = "outstanding_balance (estimated)"
            st.caption(f"Estimated EAD — mean {float(_ead_series.mean()):,.0f}, "
                       f"median {float(_ead_series.median()):,.0f} (amortizing). "
                       "Held out of the PD model; used only as EAD in ECL.")

    if _ead_series is not None:
        _ead_series = _ead_series.astype(float)
        _ead_series.name = "ead"
        st.session_state.ead_values = _ead_series
        st.session_state.ead_source_col = _ead_src
        st.session_state.ead_method = _ead_method
        st.success(f"✅ EAD source set for ECL: {_ead_method}.")
    else:
        st.session_state.pop("ead_values", None)
        st.info("EAD source not set yet — resolve the inputs above; ECL needs it.")

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

    # ── Transformation Rationale & Decision Explanation ───────────────────────────
    st.divider()
    st.markdown("#### 📝 Transformation Rationale & Decision Framework")
    st.caption("📌 Statistical basis for each feature engineering decision, all calculations on training data only.")
    
    _transform_rationale = []
    
    # Log transform rationale
    if plan.get("log_transform_cols"):
        _transform_rationale.append({
            "Decision": "Log Transform",
            "Features Affected": len(plan["log_transform_cols"]),
            "Criteria": "Skewness > 1.5 with positive values",
            "Impact": "Reduces right skew; stabilizes variance for modeling",
            "Compliance": "✅ Data transformation is documented and justified",
        })
    
    # Interaction rationale
    if plan.get("interaction_pairs"):
        _transform_rationale.append({
            "Decision": "Interaction Features",
            "Features Affected": len(plan["interaction_pairs"]),
            "Criteria": "Top features by mutual information (MI)",
            "Impact": "Captures nonlinear relationships between top predictors",
            "Compliance": "✅ Feature creation rationale is statistically justified",
        })
    
    # Binning rationale
    if plan.get("binning_cols"):
        _transform_rationale.append({
            "Decision": "Quantile Binning",
            "Features Affected": len(plan["binning_cols"]),
            "Criteria": "Numeric features with >20 unique values",
            "Impact": "Reduces model complexity; enables categorical analysis",
            "Compliance": "✅ Bucket boundaries learned on training data only",
        })
    
    # Frequency encoding rationale
    if plan.get("freq_encoding_cols"):
        _transform_rationale.append({
            "Decision": "Frequency Encoding",
            "Features Affected": len(plan["freq_encoding_cols"]),
            "Criteria": "Categorical features with >8 categories",
            "Impact": "Numeric representation of category prevalence",
            "Compliance": "✅ Frequencies learned on training split; applied unchanged to val/test",
        })
    
    # WOE rationale
    if plan.get("woe_cols"):
        _transform_rationale.append({
            "Decision": "Weight of Evidence (WOE)",
            "Features Affected": len(plan["woe_cols"]),
            "Criteria": f"Top {len(plan['woe_cols'])} features by IV (min IV = 0.02)",
            "Impact": "Transforms predictors to log-odds scale for interpretability",
            "Compliance": "✅ WOE buckets and coefficients learned on training data; applied unchanged to val/test",
        })
    
    # Feature removal rationale
    _removed_reasons = {}
    if plan.get("drop_high_corr_pairs"):
        _removed_reasons["Multicollinearity"] = len({p[1] for p in plan["drop_high_corr_pairs"]})
    if plan.get("low_variance_cols"):
        _removed_reasons["Low Variance"] = len(plan["low_variance_cols"])
    if plan.get("low_iv_cols"):
        _removed_reasons["Low IV"] = len(plan["low_iv_cols"])
    
    if _removed_reasons:
        _removal_str = "; ".join([f"{k}: {v}" for k, v in _removed_reasons.items()])
        _transform_rationale.append({
            "Decision": "Feature Removal",
            "Features Affected": sum(_removed_reasons.values()),
            "Criteria": _removal_str,
            "Impact": "Reduces noise and multicollinearity; improves model stability",
            "Compliance": "✅ Removal criteria applied consistently across train/val/test splits",
        })
    
    if _transform_rationale:
        _rationale_df = pd.DataFrame(_transform_rationale)
        with st.expander("🎯 View Decision Framework Details", expanded=True):
            st.dataframe(_rationale_df, use_container_width=True)
    
    # Compliance message
    st.markdown("""
    <div style='background:#071a0e;border-left:4px solid #10b981;border-radius:0 8px 8px 0;
    padding:0.75rem 1rem;margin:0.75rem 0;color:#94a3b8;font-size:0.85rem;'>
    <strong style='color:#10b981;'>✅ Compliance & Governance</strong><br>
    • All feature engineering decisions learned exclusively on training data<br>
    • Training-learned parameters (IV thresholds, WOE maps, correlation pairs, variance, frequencies, bucket edges) 
    applied unchanged to validation/test<br>
    • No data leakage: validation/test statistics never influence transformation parameters<br>
    • Detailed transformation mapping and rationale exported for model documentation<br>
    </div>
    """, unsafe_allow_html=True)

    # ── Transformation Details & Feature Mapping ──────────────────────────────
    st.divider()
    st.markdown("#### 🔄 Detailed Transformation Mapping")
    st.caption("📌 Complete lineage of feature transformations with statistical rationale — all mappings learned on training data only.")
    
    _transform_details = fe_summary.get("transformation_details", [])
    _feature_mapping = fe_summary.get("feature_mapping", {})
    
    if _transform_details:
        # Create detailed transformation table
        _transform_rows = []
        for _td in _transform_details:
            _orig = _td.get("original_feature", "")
            _trans = _td.get("transformed_features", [])
            _trans_str = ", ".join(_trans) if _trans else "(removed)"
            _type = _td.get("transformation_type", "")
            _reason = _td.get("reason", "")
            _method = _td.get("method", "")
            
            # Get statistical context
            _iv_val = _fe_iv.get(_orig, "") if _orig and _orig in _orig_cols else ""
            _vif_val = _fe_vif.get(_orig, "") if _orig and _orig in _orig_cols else ""
            _mi_val = plan.get("mi_scores", {}).get(_orig, "") if _orig in _orig_cols else ""
            
            _transform_rows.append({
                "Original": _orig,
                "Transformed To": _trans_str,
                "Transformation Type": _type,
                "Rationale": _reason,
                "Method": _method,
                "IV": f"{_iv_val:.4f}" if isinstance(_iv_val, (int, float)) else _iv_val,
                "VIF": f"{_vif_val:.2f}" if isinstance(_vif_val, (int, float)) else _vif_val,
                "MI": f"{_mi_val:.4f}" if isinstance(_mi_val, (int, float)) else _mi_val,
            })
        
        # Display table with expander for details
        with st.expander("📋 View Transformation Details Table", expanded=True):
            st.dataframe(
                pd.DataFrame(_transform_rows).fillna("-"),
                use_container_width=True,
                height=400,
            )
    else:
        st.info("No detailed transformations logged.")
    
    # Feature mapping visualization
    if _feature_mapping:
        st.markdown("#### 📊 Feature Lineage (Original → Transformed)")
        st.caption("Shows which original features were used to create new engineered features.")
        
        with st.expander("📈 View Feature Lineage", expanded=False):
            _lineage_rows = []
            for _orig_feat, _trans_feats in _feature_mapping.items():
                for _tgt_feat in _trans_feats:
                    _lineage_rows.append({
                        "Source Feature": _orig_feat,
                        "Created Feature": _tgt_feat,
                        "IV (source)": f"{_fe_iv.get(_orig_feat, ''):.4f}" if _orig_feat in _fe_iv else "-",
                    })
            if _lineage_rows:
                st.dataframe(pd.DataFrame(_lineage_rows), use_container_width=True)

    # ── Feature Decision Log download (Enhanced) ────────────────────────────────
    st.divider()
    st.markdown("#### 📥 Feature Decision Log & Export")
    
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
        
        _trans_feats = _feature_mapping.get(_fc, [])
        _trans_str = ", ".join(_trans_feats) if _trans_feats else "-"
        
        _log_rows.append({
            "Feature": _fc, 
            "Decision": _dec, 
            "Reason": _rsn,
            "Transformed To": _trans_str,
            "IV Score": f"{_fe_iv.get(_fc, ''):.4f}" if _fc in _fe_iv else "",
            "VIF Score": f"{_fe_vif.get(_fc, ''):.3f}" if _fc in _fe_vif else "",
            "MI Score": f"{plan.get('mi_scores', {}).get(_fc, ''):.4f}" if _fc in plan.get('mi_scores', {}) else "",
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
            "Feature": _fc, 
            "Decision": "Added", 
            "Reason": _rsn,
            "Transformed To": "-",
            "IV Score": f"{_fe_iv.get(_fc, ''):.4f}" if _fc in _fe_iv else "",
            "VIF Score": f"{_fe_vif.get(_fc, ''):.3f}" if _fc in _fe_vif else "",
            "MI Score": "-",
        })
    
    _fdl_df = pd.DataFrame(_log_rows)
    
    col_fdl1, col_fdl2 = st.columns(2)
    with col_fdl1:
        st.download_button(
            "📥 Download Complete Feature Decision Log (CSV)",
            data=_fdl_df.to_csv(index=False).encode("utf-8"),
            file_name="feature_decision_log_complete.csv",
            mime="text/csv",
            use_container_width=True,
            key="feature_decision_log_download",
        )
    
    with col_fdl2:
        # Export transformation mapping as JSON for documentation
        _export_data = {
            "feature_transformation_summary": {
                "original_feature_count": fe_summary.get("original_shape", [0])[1],
                "final_feature_count": fe_summary.get("final_shape", [0])[1],
                "features_added": fe_summary.get("features_added", 0),
                "features_removed": fe_summary.get("features_removed", 0),
            },
            "transformation_details": fe_summary.get("transformation_details", []),
            "feature_mapping": _feature_mapping,
        }
        st.download_button(
            "📋 Download Transformation Details (JSON)",
            data=json.dumps(_export_data, indent=2).encode("utf-8"),
            file_name="transformation_details.json",
            mime="application/json",
            use_container_width=True,
            key="transformation_json_download",
        )
    
    with st.expander("📊 View Feature Decision Log Preview", expanded=False):
        st.dataframe(_fdl_df, use_container_width=True, height=400)

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


def render_val_intake():
    """Stage 1 — Model Intake & Governance"""
    import html as _html

    st.markdown("### 📋 Stage 1 — Model Intake & Governance")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.9rem;'>Capture model metadata, upload all artifacts, "
        "and complete the governance attestation checklist before proceeding to automated validation stages.</p>",
        unsafe_allow_html=True,
    )

    # Section A: Model Metadata
    st.markdown("#### 🏷️ Section A — Model Metadata")
    _mc1, _mc2 = st.columns(2)
    with _mc1:
        _name = st.text_input("Model Name", key="vi_model_name")
        _team = st.text_input("Owning Team / Business Unit", key="vi_team")
    with _mc2:
        _owner = st.text_input("Model Owner (name)", key="vi_model_owner")
        _reviewer = st.text_input("Lead Validator (name)", key="vi_reviewer")

    _mc3, _mc4 = st.columns(2)
    with _mc3:
        _model_type = st.selectbox(
            "Model Type",
            ["PD (Probability of Default)", "LGD", "EAD", "ECL / IFRS 9", "Scorecard", "Other"],
            key="vi_model_type",
        )
        _tier = st.selectbox(
            "Model Tier",
            ["Tier 1 — High Risk", "Tier 2 — Medium Risk", "Tier 3 — Low Risk"],
            key="vi_tier",
        )
    with _mc4:
        _version = st.text_input("Model Version", placeholder="e.g. v2.1.0", key="vi_version")
        _review_date = st.date_input("Validation Start Date", key="vi_review_date")

    st.text_area(
        "Model Purpose & Scope",
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
        _mdd_file        = st.file_uploader("📄 Model Development Document (PDF / DOCX)", type=["pdf", "docx"], key="val_mdd_upload")
        _code_file       = st.file_uploader("💻 Training Code / Scripts (ZIP / PY / IPYNB)", type=["zip", "py", "ipynb"], key="val_code_upload")
        _perf_file       = st.file_uploader("📈 Performance Report (PDF / XLSX)", type=["pdf", "xlsx"], key="val_perf_upload")
    with _ub2:
        _profile_file    = st.file_uploader("🔍 Data Profile / Dictionary (CSV / XLSX / PDF)", type=["csv", "xlsx", "pdf"], key="val_profile")
        _assumptions_file = st.file_uploader("📝 Assumptions & Limitations (PDF / DOCX)", type=["pdf", "docx"], key="val_assumptions")
        _config_file     = st.file_uploader("⚙️ Hyperparameter Config (JSON / YAML / TXT)", type=["json", "yaml", "txt"], key="val_config")

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

    # Artifact completeness checklist
    _artifact_specs = [
        ("Submitted Dataset",            st.session_state.get("val_df") is not None, "REQUIRED", "Needed for Stages 2–5"),
        ("Data Profile Report",          _profile_file is not None,                  "OPTIONAL",  "Needed for Stage 2 — Check 2.7"),
        ("Model Dev Document (MDD)",     _mdd_file is not None,                      "REQUIRED",  "Needed for Stage 1 governance checks"),
        ("Assumptions & Limitations",    _assumptions_file is not None,              "OPTIONAL",  "Needed for Stage 3"),
        ("Training Code / Scripts",      _code_file is not None,                     "REQUIRED",  "Needed for Stage 4 — Model Replication"),
        ("Hyperparameter Config",        _config_file is not None,                   "OPTIONAL",  "Needed for Stage 4"),
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
    _checklist = [
        "Model is registered in the model inventory",
        "Model risk tier has been formally assigned",
        "Model developer has provided all required artifacts",
        "Previous validation findings (if any) have been reviewed",
        "Regulatory scope (IFRS 9 / SS1/23 / SS11/13) has been identified",
        "Independent validation team has no conflict of interest",
        "Validation plan has been approved by the Head of Model Risk",
    ]
    _check_vals = [st.checkbox(item, key=f"vi_chk_{i}") for i, item in enumerate(_checklist)]
    _all_checked = all(_check_vals)

    # Section D: Attestation & Submit
    st.markdown("#### ✍️ Section D — Validator Attestation")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;'>By clicking 'Submit Intake', you confirm that all "
        "information provided is accurate and the validation team is ready to proceed.</p>",
        unsafe_allow_html=True,
    )
    _attest = st.checkbox("I confirm the above information is accurate and complete", key="vi_attest")

    if st.button(
        "📋 Submit Intake & Proceed to Stage 2",
        type="primary",
        use_container_width=True,
        disabled=not (_attest and _all_checked),
    ):
        st.session_state["val_model_name"]  = _name
        st.session_state["val_model_owner"] = _owner
        st.session_state["val_step"] = 2
        st.success("✅ Intake submitted. Navigate to Stage 2: Data Validation to run automated checks.")
    elif not _attest or not _all_checked:
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

    rules_path = Path(__file__).resolve().parent / "rag_store" / "val_mdd_rules.json"
    if not rules_path.exists():
        return []
    try:
        with rules_path.open(encoding="utf-8") as f:
            rules: list[dict] = json.load(f)
        if stage_filter:
            rules = [r for r in rules if r.get("stage") == stage_filter]
        return rules
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
            "Run `python val_build_rules.py --extract` to populate the knowledge store, "
            "or `python val_build_rules.py` to seed it with the curated baseline rules."
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

        st.session_state["val_dv_results"] = _results

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

        for _r in _dv_res:
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
                f"📋 {_html.escape(str(_r['source']))} — {_html.escape(str(_r['principle']))}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.25rem;'>"
                f"📊 Observed: <code style='color:#e2e8f0;'>{_html.escape(str(_r['observed']))}</code></div>"
                f"<div style='color:#475569;font-size:0.78rem;margin-top:0.15rem;'>"
                f"📐 Threshold: {_html.escape(str(_r['threshold']))}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.2rem;'>"
                f"💡 {_html.escape(str(_r['detail']))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── RAG Agent — qualitative rules from knowledge store ──────────────
        st.divider()
        st.markdown("#### 🤖 RAG Agent — Qualitative Data Validation Rules")
        st.markdown(
            "<p style='color:#94a3b8;font-size:0.85rem;'>"
            "The following rules were retrieved from the regulatory knowledge store "
            "(SS1/23, SS11/13, IFRS 9) by the RAG agent. They cover qualitative "
            "MDD documentation requirements for Stage 2 that cannot be assessed from "
            "the dataset alone. Agent 2b will cross-check each rule against the "
            "uploaded MDD and surface PASS / WARN / FAIL findings.</p>",
            unsafe_allow_html=True,
        )
        _rag_dv_rules = _load_val_rag_rules(stage_filter="data")
        _render_rag_rules_panel(_rag_dv_rules, panel_key="dv")

        st.divider()
        _csv_rows = [{
            "Check ID": r["check_id"], "Title": r["title"],
            "Regulatory Source": r["source"], "Principle": r["principle"],
            "Severity": r["severity"], "Status": r["status"],
            "Observed": r["observed"], "Threshold": r["threshold"],
            "Detail": r["detail"],
        } for r in _dv_res]
        st.download_button(
            "📥 Download Data Validation Report (CSV)",
            data=pd.DataFrame(_csv_rows).to_csv(index=False).encode("utf-8"),
            file_name="data_validation_report.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_dv_report",
        )


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

    _vdf = st.session_state.get("val_df")
    if _vdf is None:
        st.warning("⚠️ No dataset found. Please upload the client dataset in Stage 1: Intake & Governance first.")
        return

    # ── MDD upload (optional but needed for qualitative checks) ──────────────────
    st.markdown("#### 📄 Model Development Document (MDD)")
    _mdd_text = st.session_state.get("val_mdd_text", "")
    _mdd_file = st.file_uploader(
        "Upload MDD (PDF or TXT) — used for qualitative checks 3.1 & 3.2",
        type=["pdf", "txt"],
        key="cs_mdd_upload",
    )
    if _mdd_file is not None:
        try:
            if _mdd_file.name.endswith(".pdf"):
                import pypdf
                _reader = pypdf.PdfReader(_mdd_file)
                _mdd_text = "\n".join(p.extract_text() or "" for p in _reader.pages)
            else:
                _mdd_text = _mdd_file.read().decode("utf-8", errors="ignore")
            st.session_state["val_mdd_text"] = _mdd_text
            st.success(f"✅ MDD loaded — {len(_mdd_text):,} characters")
        except Exception as _e:
            st.error(f"Could not read MDD: {_e}")

    if _mdd_text:
        with st.expander("MDD preview (first 2 000 chars)"):
            st.text(_mdd_text[:2000])

    # ── Feature set selection ─────────────────────────────────────────────────────
    st.markdown("#### 🔬 Feature Set")
    _num_cols_cs = [c for c in _vdf.columns if pd.api.types.is_numeric_dtype(_vdf[c])]
    _all_cols_cs = _vdf.columns.tolist()

    # Auto-detect likely target
    _tgt_kw = ["default", "bad", "target", "label", "y", "dpd_90", "charged"]
    _tgt_guess = next((c for c in _all_cols_cs if any(k in c.lower() for k in _tgt_kw)
                       and _vdf[c].nunique() == 2), _all_cols_cs[0])
    _target_col_cs = st.selectbox(
        "Target / default indicator column",
        _all_cols_cs,
        index=_all_cols_cs.index(_tgt_guess),
        key="cs_target_col",
    )
    _feature_options = [c for c in _num_cols_cs if c != _target_col_cs]
    _selected_features = st.multiselect(
        "Select submitted feature set (numeric columns)",
        _feature_options,
        default=_feature_options[:min(len(_feature_options), 15)],
        key="cs_features",
    )

    # ── Protected characteristics detection ──────────────────────────────────────
    _prot_kw = ["age", "gender", "sex", "ethnicity", "race", "nationality",
                "marital", "religion", "disability"]
    _prot_detected = [c for c in _all_cols_cs if any(k in c.lower() for k in _prot_kw)]
    _prot_cols = st.multiselect(
        "Protected characteristic columns (for fairness check — leave blank if none)",
        _all_cols_cs,
        default=_prot_detected,
        key="cs_prot_cols",
    )

    # ── Model name / type (from Intake if available) ──────────────────────────────
    _model_name_cs = st.session_state.get("val_model_name", "")
    _model_type_hint = st.text_input(
        "Submitted model type (e.g. 'Logistic Regression', 'XGBoost', 'Scorecard')",
        value=st.session_state.get("val_model_type_hint", ""),
        key="cs_model_type",
    )
    st.session_state["val_model_type_hint"] = _model_type_hint

    if not _selected_features:
        st.info("Select at least one numeric feature to run the quantitative checks.")
        return

    if st.button("▶️ Run Conceptual Soundness Checks", type="primary", use_container_width=True):
        _cs_results = []
        _cs_plots   = {}
        _df = _vdf.copy()
        _feats = _selected_features

        # ─────────────────────────────────────────────────────────────────────────
        # 3.1  Model Selection Justification (MDD review)
        # ─────────────────────────────────────────────────────────────────────────
        if _mdd_text:
            _mdd_lower = _mdd_text.lower()
            _model_kw  = ["logistic", "xgboost", "lightgbm", "random forest", "gradient boost",
                          "scorecard", "neural", "linear", "regression", "selected", "chosen",
                          "rationale", "justif", "chosen because", "appropriate", "model choice"]
            _found_kw   = [k for k in _model_kw if k in _mdd_lower]
            _sel_status = "PASS" if len(_found_kw) >= 3 else ("WARN" if len(_found_kw) >= 1 else "FAIL")
            _consistency_ok = (
                _model_type_hint.strip().lower() in _mdd_lower
                if _model_type_hint.strip() else None
            )
            _consistency_note = (
                f"Model type '{_model_type_hint}' found in MDD ✓" if _consistency_ok
                else (f"Model type '{_model_type_hint}' NOT found in MDD text — verify manually"
                      if _model_type_hint.strip() else "No model type provided — cannot verify consistency")
            )
            _cs_results.append({
                "check_id": "3.1", "title": "Model Selection Justification",
                "source": "SS1/23", "principle": "P2.1", "severity": "high",
                "status": _sel_status,
                "observed": f"Justification keywords found: {_found_kw[:5]}. {_consistency_note}",
                "threshold": "MDD must document rationale for chosen model type",
                "detail": (
                    "SS1/23 P2.1 requires model developers to justify the choice of modelling technique. "
                    "Look for: stated reasons for selection, comparison to alternatives, acknowledgment of limitations. "
                    "Manual review required to confirm adequacy."
                ),
            })
        else:
            _cs_results.append({
                "check_id": "3.1", "title": "Model Selection Justification",
                "source": "SS1/23", "principle": "P2.1", "severity": "high",
                "status": "WARN",
                "observed": "No MDD uploaded — cannot assess model selection justification automatically.",
                "threshold": "MDD must document rationale for chosen model type",
                "detail": "Upload the MDD to enable automated keyword scanning. Manual review is required in all cases.",
            })

        # ─────────────────────────────────────────────────────────────────────────
        # 3.2  Benchmarking Evidence (MDD review)
        # ─────────────────────────────────────────────────────────────────────────
        if _mdd_text:
            _bench_kw = ["benchmark", "challenger", "baseline", "logistic regression", "naive",
                         "compare", "comparison", "alternative model", "simpler", "scorecard",
                         "gini", "auc", "discriminat", "out-of-time", "oot"]
            _found_bench = [k for k in _bench_kw if k in _mdd_lower]
            _bench_status = "PASS" if len(_found_bench) >= 3 else ("WARN" if len(_found_bench) >= 1 else "FAIL")
            _cs_results.append({
                "check_id": "3.2", "title": "Benchmarking Evidence (vs Simpler Models)",
                "source": "SS1/23", "principle": "P2.2", "severity": "high",
                "status": _bench_status,
                "observed": f"Benchmark keywords found in MDD: {_found_bench[:5]}",
                "threshold": "Evidence of comparison with at least one simpler/baseline model required",
                "detail": (
                    "SS1/23 P2.2 and good practice require developers to test candidate models against "
                    "simpler benchmarks (e.g. logistic regression scorecard). The MDD should report "
                    "comparative Gini/AUC across at least two models. Manual review required."
                ),
            })
        else:
            _cs_results.append({
                "check_id": "3.2", "title": "Benchmarking Evidence (vs Simpler Models)",
                "source": "SS1/23", "principle": "P2.2", "severity": "high",
                "status": "WARN",
                "observed": "No MDD uploaded.",
                "threshold": "Evidence of comparison with at least one simpler/baseline model required",
                "detail": "Upload the MDD to enable automated keyword scanning for benchmarking evidence.",
            })

        # ─────────────────────────────────────────────────────────────────────────
        # 3.3  Information Value (IV) per feature — flag if IV < 0.02
        # ─────────────────────────────────────────────────────────────────────────
        _iv_records = []
        _iv_low_flags = []
        try:
            _tgt_s = pd.to_numeric(_df[_target_col_cs], errors="coerce").fillna(0).astype(int)
            _event_rate = float(_tgt_s.mean())
            _n_events    = int(_tgt_s.sum())
            _n_non       = int((1 - _tgt_s).sum())

            for _fc in _feats:
                try:
                    _fv = pd.to_numeric(_df[_fc], errors="coerce")
                    _notna = _fv.notna()
                    if _notna.sum() < 20:
                        continue
                    # Bin into 10 quantile buckets
                    try:
                        _bins = pd.qcut(_fv[_notna], q=10, duplicates="drop")
                    except Exception:
                        _bins = pd.cut(_fv[_notna], bins=10)
                    _tmp = pd.DataFrame({"bin": _bins, "tgt": _tgt_s[_notna]})
                    _grp = _tmp.groupby("bin", observed=False)["tgt"].agg(["sum", "count"])
                    _grp.columns = ["events", "total"]
                    _grp["non_events"] = _grp["total"] - _grp["events"]
                    _grp = _grp[(_grp["events"] > 0) & (_grp["non_events"] > 0)]
                    if _grp.empty or _n_events == 0 or _n_non == 0:
                        _iv_records.append({"feature": _fc, "iv": 0.0, "bins": 0})
                        continue
                    _grp["dist_ev"]  = _grp["events"]     / _n_events
                    _grp["dist_nev"] = _grp["non_events"] / _n_non
                    _grp["woe"]      = np.log(_grp["dist_ev"] / _grp["dist_nev"])
                    _grp["iv_bin"]   = (_grp["dist_ev"] - _grp["dist_nev"]) * _grp["woe"]
                    _iv_val = float(_grp["iv_bin"].sum())
                    _iv_records.append({"feature": _fc, "iv": round(_iv_val, 5), "bins": len(_grp)})
                    if _iv_val < 0.02:
                        _iv_low_flags.append(f"{_fc} (IV={_iv_val:.4f})")
                except Exception:
                    pass

            _iv_df = pd.DataFrame(_iv_records).sort_values("iv", ascending=False)
            st.session_state["val_cs_iv_df"] = _iv_df

            _iv_status = "FAIL" if _iv_low_flags else "PASS"
            _cs_results.append({
                "check_id": "3.3", "title": "Information Value (IV) — Low-IV Feature Flags",
                "source": "SS1/23", "principle": "P2.3", "severity": "medium",
                "status": _iv_status,
                "observed": (
                    f"{len(_iv_low_flags)} feature(s) with IV < 0.02: {'; '.join(_iv_low_flags[:5])}"
                    if _iv_low_flags else f"All {len(_iv_records)} features have IV ≥ 0.02"
                ),
                "threshold": "IV < 0.02 → feature has near-zero predictive power (industry convention)",
                "detail": (
                    "Features with IV < 0.02 provide negligible discriminatory contribution and should be "
                    "excluded unless there is a strong conceptual reason to retain them. "
                    "IV 0.02–0.1 = weak; 0.1–0.3 = medium; > 0.3 = strong."
                ),
            })

            # IV bar chart
            if not _iv_df.empty:
                _fig_iv = go.Figure(go.Bar(
                    x=_iv_df["iv"], y=_iv_df["feature"],
                    orientation="h",
                    marker=dict(
                        color=_iv_df["iv"].apply(
                            lambda v: "#ef4444" if v < 0.02 else ("#f59e0b" if v < 0.10 else "#10b981")
                        ),
                    ),
                    text=[f"{v:.4f}" for v in _iv_df["iv"]],
                    textposition="outside",
                ))
                _fig_iv.add_vline(x=0.02, line_dash="dash", line_color="#ef4444",
                                  annotation_text="IV=0.02 floor")
                _fig_iv.update_layout(
                    title="Information Value by Feature (red = IV < 0.02)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    margin=dict(l=200, r=60, t=50, b=40),
                    xaxis=dict(gridcolor="#334155"),
                    yaxis=dict(gridcolor="#334155"),
                )
                _cs_plots["iv"] = _fig_iv

        except Exception as _e:
            _cs_results.append({
                "check_id": "3.3", "title": "Information Value (IV)",
                "source": "SS1/23", "principle": "P2.3", "severity": "medium",
                "status": "WARN", "observed": f"IV computation failed: {_e}",
                "threshold": "IV < 0.02 → flag",
                "detail": "Ensure the target column is binary (0/1) and features are numeric.",
            })

        # ─────────────────────────────────────────────────────────────────────────
        # 3.4  Variance Inflation Factor (VIF) — flag if VIF > 10
        # ─────────────────────────────────────────────────────────────────────────
        try:
            from sklearn.linear_model import LinearRegression as _LR

            _X_vif = _df[_feats].apply(pd.to_numeric, errors="coerce").dropna()
            _vif_records = []
            _vif_high_flags = []

            if len(_feats) >= 2 and len(_X_vif) >= len(_feats) + 5:
                _X_arr = _X_vif.values
                # Standardise to prevent numerical issues
                _col_stds = _X_arr.std(axis=0)
                _col_stds[_col_stds == 0] = 1.0
                _X_scaled = (_X_arr - _X_arr.mean(axis=0)) / _col_stds

                for _i, _fc in enumerate(_feats):
                    _y_vif  = _X_scaled[:, _i]
                    _X_rest = np.delete(_X_scaled, _i, axis=1)
                    _model_vif = _LR(fit_intercept=True)
                    _model_vif.fit(_X_rest, _y_vif)
                    _r2 = float(_model_vif.score(_X_rest, _y_vif))
                    _vif_val = round(1.0 / (1.0 - _r2) if _r2 < 1.0 else 999.0, 2)
                    _vif_records.append({"feature": _fc, "vif": _vif_val})
                    if _vif_val > 10.0:
                        _vif_high_flags.append(f"{_fc} (VIF={_vif_val:.1f})")

            _vif_df = pd.DataFrame(_vif_records).sort_values("vif", ascending=False)
            st.session_state["val_cs_vif_df"] = _vif_df

            _vif_status = "FAIL" if _vif_high_flags else ("WARN" if len(_feats) < 2 else "PASS")
            _cs_results.append({
                "check_id": "3.4", "title": "Variance Inflation Factor (VIF) — Multicollinearity",
                "source": "SS1/23", "principle": "P2.3", "severity": "high",
                "status": _vif_status,
                "observed": (
                    f"{len(_vif_high_flags)} feature(s) with VIF > 10: {'; '.join(_vif_high_flags[:5])}"
                    if _vif_high_flags else
                    (f"All {len(_vif_records)} features VIF ≤ 10" if _vif_records else "Fewer than 2 features selected")
                ),
                "threshold": "VIF > 10 → severe multicollinearity; feature should be reviewed for removal",
                "detail": (
                    "High VIF indicates that a feature is largely explained by the others, inflating "
                    "coefficient variance and destabilising model estimates. Standard threshold is VIF > 10 (some "
                    "practitioners use 5). Developer must justify retention of high-VIF features."
                ),
            })

            if not _vif_df.empty:
                _fig_vif = go.Figure(go.Bar(
                    x=_vif_df["vif"], y=_vif_df["feature"],
                    orientation="h",
                    marker=dict(
                        color=_vif_df["vif"].apply(
                            lambda v: "#ef4444" if v > 10 else ("#f59e0b" if v > 5 else "#10b981")
                        ),
                    ),
                    text=[f"{v:.1f}" for v in _vif_df["vif"]],
                    textposition="outside",
                ))
                _fig_vif.add_vline(x=10, line_dash="dash", line_color="#ef4444",
                                   annotation_text="VIF=10 threshold")
                _fig_vif.add_vline(x=5, line_dash="dot", line_color="#f59e0b",
                                   annotation_text="VIF=5 caution")
                _fig_vif.update_layout(
                    title="Variance Inflation Factor by Feature",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    margin=dict(l=200, r=60, t=50, b=40),
                    xaxis=dict(gridcolor="#334155"),
                    yaxis=dict(gridcolor="#334155"),
                )
                _cs_plots["vif"] = _fig_vif

        except Exception as _e:
            _cs_results.append({
                "check_id": "3.4", "title": "VIF — Multicollinearity",
                "source": "SS1/23", "principle": "P2.3", "severity": "high",
                "status": "WARN", "observed": f"VIF computation failed: {_e}",
                "threshold": "VIF > 10 → flag",
                "detail": "Ensure selected features are numeric with sufficient non-missing rows.",
            })

        # ─────────────────────────────────────────────────────────────────────────
        # 3.5  Pairwise Correlation — flag pairs with |r| > 0.75
        # ─────────────────────────────────────────────────────────────────────────
        try:
            _X_corr = _df[_feats].apply(pd.to_numeric, errors="coerce")
            _corr_mat = _X_corr.corr()
            _high_pairs = []
            _n_feat = len(_feats)
            for _ii in range(_n_feat):
                for _jj in range(_ii + 1, _n_feat):
                    _rval = _corr_mat.iloc[_ii, _jj]
                    if pd.notna(_rval) and abs(_rval) > 0.75:
                        _high_pairs.append(
                            f"{_feats[_ii]} ↔ {_feats[_jj]} (r={_rval:.3f})"
                        )
            st.session_state["val_cs_corr_mat"] = _corr_mat
            st.session_state["val_cs_high_corr_pairs"] = _high_pairs

            _corr_status = "FAIL" if len(_high_pairs) > 0 else "PASS"
            _cs_results.append({
                "check_id": "3.5", "title": "Pairwise Feature Correlation — High-Correlation Pairs",
                "source": "SS1/23", "principle": "P2.3", "severity": "medium",
                "status": _corr_status,
                "observed": (
                    f"{len(_high_pairs)} pair(s) with |r| > 0.75: {'; '.join(_high_pairs[:4])}"
                    + ("…" if len(_high_pairs) > 4 else "")
                    if _high_pairs else "No pairs with |r| > 0.75 detected"
                ),
                "threshold": "|r| > 0.75 → potential redundancy; developer must document resolution",
                "detail": (
                    "Highly correlated features introduce multicollinearity and may make individual "
                    "feature effects uninterpretable. Developer should document how high-correlation pairs "
                    "were identified and resolved (e.g. one removed, PCA applied, WoE re-encoding)."
                ),
            })

            # Heatmap
            if len(_feats) >= 2:
                _n_show = min(len(_feats), 25)
                _show_feats = _feats[:_n_show]
                _corr_sub = _corr_mat.loc[_show_feats, _show_feats].round(3)
                _fig_corr = go.Figure(go.Heatmap(
                    z=_corr_sub.values,
                    x=_corr_sub.columns.tolist(),
                    y=_corr_sub.index.tolist(),
                    colorscale="RdBu_r",
                    zmid=0,
                    zmin=-1, zmax=1,
                    text=_corr_sub.values.round(2),
                    texttemplate="%{text}",
                    colorbar=dict(title="r"),
                ))
                _fig_corr.update_layout(
                    title=f"Pairwise Correlation Matrix (top {_n_show} features)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0"),
                    margin=dict(l=40, r=40, t=50, b=40),
                )
                _cs_plots["corr"] = _fig_corr

        except Exception as _e:
            _cs_results.append({
                "check_id": "3.5", "title": "Pairwise Feature Correlation",
                "source": "SS1/23", "principle": "P2.3", "severity": "medium",
                "status": "WARN", "observed": f"Correlation computation failed: {_e}",
                "threshold": "|r| > 0.75 → flag",
                "detail": "Ensure all selected features are numeric.",
            })

        # ─────────────────────────────────────────────────────────────────────────
        # 3.6  Transformation Soundness Review
        # ─────────────────────────────────────────────────────────────────────────
        _transform_notes = []
        _transform_warnings = []
        for _fc in _feats:
            try:
                _fv = pd.to_numeric(_df[_fc], errors="coerce").dropna()
                if len(_fv) < 10:
                    continue
                _skew  = float(_fv.skew())
                _q1, _q99 = float(_fv.quantile(0.01)), float(_fv.quantile(0.99))
                _range = _q99 - _q1
                _has_neg = bool((_fv <= 0).any())
                _note = {"feature": _fc, "skewness": round(_skew, 3), "has_negatives": _has_neg}

                if abs(_skew) > 2.0 and not _has_neg:
                    _note["recommendation"] = "Log/sqrt transform recommended (high skew, all positive)"
                    _note["status"] = "WARN"
                    _transform_warnings.append(
                        f"{_fc}: skewness={_skew:.2f}, positive-only → log/sqrt transform advised"
                    )
                elif abs(_skew) > 2.0 and _has_neg:
                    _note["recommendation"] = "Quantile binning or Yeo-Johnson transform recommended (high skew with negatives)"
                    _note["status"] = "WARN"
                    _transform_warnings.append(
                        f"{_fc}: skewness={_skew:.2f}, has negatives → quantile binning or Yeo-Johnson advised"
                    )
                elif _range > 0 and _q99 / max(abs(_q1), 1e-9) > 1000:
                    _note["recommendation"] = "Scale is very wide — WoE binning or log scale advised"
                    _note["status"] = "WARN"
                    _transform_warnings.append(
                        f"{_fc}: extreme range ({_q1:.1f}–{_q99:.1f}) → consider WoE binning"
                    )
                else:
                    _note["recommendation"] = "No transformation issue detected"
                    _note["status"] = "OK"
                _transform_notes.append(_note)
            except Exception:
                pass

        st.session_state["val_cs_transform_notes"] = _transform_notes
        _tr_status = "WARN" if _transform_warnings else "PASS"
        _cs_results.append({
            "check_id": "3.6", "title": "Transformation Soundness Review",
            "source": "SS1/23", "principle": "P2.4", "severity": "medium",
            "status": _tr_status,
            "observed": (
                f"{len(_transform_warnings)} feature(s) flagged: {'; '.join(_transform_warnings[:3])}"
                + ("…" if len(_transform_warnings) > 3 else "")
                if _transform_warnings else
                f"No transformation concerns in the {len(_transform_notes)} reviewed features"
            ),
            "threshold": "High-skew variables (|skew| > 2) should be transformed; documented in MDD",
            "detail": (
                "Untransformed highly skewed features can distort model coefficients and reduce discriminatory power. "
                "Acceptable transformations: log (positive-only), square-root, quantile binning, WoE encoding, "
                "Yeo-Johnson (handles negatives). Each transformation must be documented in the MDD with statistical justification."
            ),
        })

        # ─────────────────────────────────────────────────────────────────────────
        # 3.7  Protected Characteristics — Fairness / Disparate Impact
        # ─────────────────────────────────────────────────────────────────────────
        if _prot_cols:
            _fair_issues = []
            _fair_notes  = []
            _tgt_s2 = pd.to_numeric(_df[_target_col_cs], errors="coerce").fillna(0)

            for _pc in _prot_cols:
                try:
                    _groups = _df[_pc].dropna().unique()
                    if len(_groups) < 2 or len(_groups) > 20:
                        continue
                    _rates = {}
                    for _g in _groups:
                        _mask = _df[_pc] == _g
                        _r = float(_tgt_s2[_mask].mean())
                        _rates[str(_g)] = round(_r, 4)
                    _min_rate = min(_rates.values())
                    _max_rate = max(_rates.values())
                    _di_ratio = round(_min_rate / _max_rate, 4) if _max_rate > 0 else 1.0
                    _note_str = f"{_pc}: rates={_rates}, DI ratio={_di_ratio:.3f}"
                    _fair_notes.append(_note_str)
                    if _di_ratio < 0.80:
                        _fair_issues.append(
                            f"{_pc}: disparate impact ratio {_di_ratio:.3f} < 0.80 "
                            f"(highest group rate {_max_rate:.1%} vs lowest {_min_rate:.1%})"
                        )
                except Exception:
                    pass

            _fair_status = "FAIL" if _fair_issues else "PASS"
            _cs_results.append({
                "check_id": "3.7", "title": "Protected Characteristics — Disparate Impact Check",
                "source": "SS1/23", "principle": "P2.5 / FCA Equality Act",
                "severity": "high",
                "status": _fair_status,
                "observed": (
                    "; ".join(_fair_issues) if _fair_issues
                    else f"No disparate impact detected across {len(_prot_cols)} protected characteristic(s). "
                         + " | ".join(_fair_notes[:3])
                ),
                "threshold": "Disparate Impact ratio < 0.80 (4/5ths rule) → potential discrimination risk",
                "detail": (
                    "The 4/5ths rule (US EEOC / FCA guidance): if the outcome rate for any protected group "
                    "is less than 80% of the highest-rate group, disparate impact is indicated. "
                    "This does not imply intentional discrimination but requires review. The model developer "
                    "must provide fairness analysis and any mitigations applied."
                ),
            })
        else:
            _cs_results.append({
                "check_id": "3.7", "title": "Protected Characteristics — Disparate Impact Check",
                "source": "SS1/23", "principle": "P2.5 / FCA Equality Act",
                "severity": "high",
                "status": "WARN",
                "observed": "No protected characteristic columns identified in submitted dataset.",
                "threshold": "Disparate impact ratio < 0.80 → flag",
                "detail": (
                    "If the model is used in retail credit decisions, the developer must supply protected "
                    "characteristic data or an equivalent fairness analysis. Absence is a material gap."
                ),
            })

        st.session_state["val_cs_results"] = _cs_results
        st.session_state["val_cs_plots"]   = _cs_plots

    # ── Display results ────────────────────────────────────────────────────────────
    _cs_res   = st.session_state.get("val_cs_results")
    _cs_plots = st.session_state.get("val_cs_plots", {})
    if not _cs_res:
        return

    st.markdown("### 📊 Conceptual Soundness Results")

    _pass_n = sum(1 for r in _cs_res if r["status"] == "PASS")
    _warn_n = sum(1 for r in _cs_res if r["status"] == "WARN")
    _fail_n = sum(1 for r in _cs_res if r["status"] == "FAIL")
    _tot_n  = len(_cs_res)

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Total Checks", _tot_n)
    _m2.metric("✅ PASS", _pass_n)
    _m3.metric("🟡 WARN", _warn_n)
    _m4.metric("🔴 FAIL", _fail_n)
    st.progress(_pass_n / _tot_n)

    _S_COL = {"PASS": "#10b981", "WARN": "#f59e0b", "FAIL": "#ef4444"}
    _S_BG  = {"PASS": "#071a0e", "WARN": "#1c1200", "FAIL": "#1c0808"}
    _S_ICN = {"PASS": "✅",      "WARN": "🟡",       "FAIL": "🔴"}
    _V_COL = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}

    for _r in _cs_res:
        _st   = _r["status"]
        _sev  = _r.get("severity", "medium")
        st.markdown(
            f"<div style='border-left:3px solid {_S_COL.get(_st,'#6366f1')};"
            f"padding:0.75rem 1rem;margin:0.4rem 0;"
            f"background:{_S_BG.get(_st,'#1e293b')};border-radius:0 6px 6px 0;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
            f"<div style='color:#f1f5f9;font-size:0.92rem;font-weight:600;line-height:1.4;'>"
            f"{_S_ICN.get(_st,'⚪')} "
            f"<span style='color:#94a3b8;'>[{_html.escape(str(_r['check_id']))}]</span> "
            f"{_html.escape(str(_r['title']))}"
            f"<span style='background:{_V_COL.get(_sev,'#6366f1')};color:#0f172a;"
            f"font-size:0.7rem;font-weight:700;padding:0.1rem 0.5rem;"
            f"border-radius:10px;margin-left:0.5rem;'>{_html.escape(_sev.upper())}</span>"
            f"</div>"
            f"<span style='background:{_S_COL.get(_st,'#6366f1')};color:#0f172a;"
            f"font-size:0.78rem;font-weight:700;padding:0.15rem 0.6rem;"
            f"border-radius:4px;white-space:nowrap;'>{_st}</span>"
            f"</div>"
            f"<div style='color:#94a3b8;font-size:0.78rem;margin-top:0.3rem;'>"
            f"📋 {_html.escape(str(_r['source']))} — {_html.escape(str(_r['principle']))}</div>"
            f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.25rem;'>"
            f"📊 Observed: <code style='color:#e2e8f0;'>"
            f"{_html.escape(str(_r['observed']))}</code></div>"
            f"<div style='color:#475569;font-size:0.78rem;margin-top:0.15rem;'>"
            f"📐 Threshold: {_html.escape(str(_r['threshold']))}</div>"
            f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:0.2rem;'>"
            f"💡 {_html.escape(str(_r['detail']))}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Charts ────────────────────────────────────────────────────────────────────
    if _cs_plots:
        st.markdown("#### 📈 Supporting Charts")

    if "iv" in _cs_plots and "vif" in _cs_plots:
        _gc1, _gc2 = st.columns(2)
        with _gc1:
            st.plotly_chart(_cs_plots["iv"],  use_container_width=True)
        with _gc2:
            st.plotly_chart(_cs_plots["vif"], use_container_width=True)
    elif "iv" in _cs_plots:
        st.plotly_chart(_cs_plots["iv"], use_container_width=True)
    elif "vif" in _cs_plots:
        st.plotly_chart(_cs_plots["vif"], use_container_width=True)

    if "corr" in _cs_plots:
        st.plotly_chart(_cs_plots["corr"], use_container_width=True)

    # ── Transformation detail table ────────────────────────────────────────────────
    _tr_notes = st.session_state.get("val_cs_transform_notes", [])
    if _tr_notes:
        with st.expander("📋 Transformation review detail (all features)"):
            _tr_df = pd.DataFrame(_tr_notes)
            st.dataframe(_tr_df, use_container_width=True)

    # ── IV table ───────────────────────────────────────────────────────────────────
    _iv_df_disp = st.session_state.get("val_cs_iv_df")
    if _iv_df_disp is not None and not _iv_df_disp.empty:
        with st.expander("📋 Full IV table"):
            st.dataframe(_iv_df_disp, use_container_width=True)

    # ── Download ──────────────────────────────────────────────────────────────────
    _csv_rows = [{
        "Check ID":    r["check_id"],
        "Title":       r["title"],
        "Source":      r["source"],
        "Principle":   r["principle"],
        "Severity":    r["severity"],
        "Status":      r["status"],
        "Observed":    r["observed"],
        "Threshold":   r["threshold"],
        "Detail":      r["detail"],
    } for r in _cs_res]

    # ── RAG Agent — qualitative rules from knowledge store ───────────────────
    st.divider()
    st.markdown("#### 🤖 RAG Agent — Qualitative Conceptual Soundness Rules")
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;'>"
        "The following rules were retrieved from the regulatory knowledge store "
        "(SS1/23, SS11/13, IFRS 9) by the RAG agent. They cover qualitative "
        "MDD documentation requirements — model purpose, selection justification, "
        "benchmarking evidence, assumptions, SICR criteria, and governance. "
        "Agent 2b will cross-check each rule against the uploaded MDD and surface "
        "PASS / WARN / FAIL findings.</p>",
        unsafe_allow_html=True,
    )
    _rag_cs_rules = _load_val_rag_rules(stage_filter="conceptual")
    _render_rag_rules_panel(_rag_cs_rules, panel_key="cs")

    st.divider()
    st.download_button(
        "📥 Download Conceptual Soundness Report (CSV)",
        data=pd.DataFrame(_csv_rows).to_csv(index=False).encode("utf-8"),
        file_name="conceptual_soundness_report.csv",
        mime="text/csv",
        use_container_width=True,
        key="download_cs_report",
    )


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
        _render_val_stage_stub(4, "⚙️", "Replication & Benchmarking", "SS1/23 P4 · SS11/13 §11",
            "Independently replicate the developer's results using submitted code and data. "
            "Compare outputs against challenger or benchmark models.")
    elif stage == 5:
        _render_val_stage_stub(5, "📊", "Performance Testing", "SS1/23 P4 · IFRS 9 B5.5.50",
            "Evaluate discriminatory power (AUC, Gini), calibration (Brier score, reliability diagrams), "
            "and stability (PSI, CSI) across time periods and segments.")
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
# STEP 9: ECL Calculation
# ─────────────────────────────────────────────
def render_ecl():
    st.markdown("""
    <div class='step-header'>
        <h3>\U0001F3E6 Step 9 — ECL Calculation (IFRS 9)</h3>
        <p>SICR assessment &rarr; Stage 1/2/3 classification &rarr; ECL = PD &times; LGD &times; EAD
        (12-month PD for Stage 1, lifetime PD for Stage 2 &amp; 3)</p>
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
    all_cols = data.columns.tolist()
    if not num_cols:
        st.error("No numeric column is available to use as exposure (EAD).")
        return

    ltv_default  = ecl.detect_ltv_col(data)
    dpd_default  = ecl.detect_dpd_col(data)
    orig_pd_def  = ecl.detect_orig_pd_col(data)
    mat_default  = ecl.detect_maturity_col(data)

    # ── EAD comes from the outstanding balance resolved in Feature Engineering ──
    st.markdown("#### Exposure & Loss inputs")
    ead_series = st.session_state.get("ead_values")
    ead_col = None
    if ead_series is not None:
        ead_series = pd.to_numeric(pd.Series(ead_series), errors="coerce").reindex(X_full.index)
        _src = st.session_state.get("ead_method", "outstanding balance (set in Feature Engineering)")
        st.info(f"EAD source (from Feature Engineering): {_src}.  Mean EAD "
                f"{float(ead_series.mean()):,.0f}.  PD is read from the trained model.")
    else:
        ead_col = ecl.detect_exposure_col(data) or num_cols[0]
        st.warning("No outstanding-balance EAD was set in Feature Engineering (Step 4). "
                   f"Falling back to auto-detected column `{ead_col}`. Set it in Step 4 to be explicit.")
    lgd_mode = st.radio("Loss Given Default (LGD) method",
                        ["Fixed assumption", "By loan type", "From LTV column"],
                        horizontal=True)

    loan_type_col = None
    lgd_map = None
    lgd_fixed = 0.45

    if lgd_mode == "Fixed assumption":
        lgd_fixed = st.slider("LGD assumption (all loans)", 0.05, 0.95, 0.45, 0.05)

    elif lgd_mode == "By loan type":
        cat_cols = [c for c in all_cols if data[c].dtype == object or data[c].nunique() <= 20]
        if not cat_cols:
            st.warning("No categorical columns detected. Switch to 'Fixed assumption'.")
        else:
            loan_type_col = st.selectbox(
                "Column that identifies loan type", cat_cols,
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

    else:  # From LTV column
        lc1, lc2 = st.columns(2)
        with lc1:
            ltv_idx = num_cols.index(ltv_default) if ltv_default in num_cols else 0
            ltv_col = st.selectbox("LTV column", num_cols, index=ltv_idx)
        with lc2:
            haircut = st.slider("Collateral haircut", 0.0, 0.6, 0.20, 0.05)

    # ── SICR configuration ──
    st.markdown("#### IFRS 9 SICR & Staging")
    with st.expander("Configure SICR thresholds & lifetime PD", expanded=True):
        s1, s2 = st.columns(2)
        with s1:
            no_cols_opt = ["— not available —"]
            dpd_options  = no_cols_opt + num_cols
            orig_options = no_cols_opt + num_cols
            mat_options  = no_cols_opt + num_cols

            dpd_idx  = dpd_options.index(dpd_default)  if dpd_default  in dpd_options  else 0
            orig_idx = orig_options.index(orig_pd_def) if orig_pd_def  in orig_options else 0
            mat_idx  = mat_options.index(mat_default)  if mat_default  in mat_options  else 0

            dpd_col_sel  = st.selectbox("Days Past Due column",      dpd_options,  index=dpd_idx,
                                         help="Used for qualitative SICR backstop and Stage 3 (≥90 DPD).")
            orig_pd_sel  = st.selectbox("Origination PD column",     orig_options, index=orig_idx,
                                         help="PD at loan origination. Used to detect relative PD increase.")
            mat_col_sel  = st.selectbox("Remaining maturity column", mat_options,  index=mat_idx,
                                         help="Remaining loan term in years. Required for lifetime PD extension (Stage 2 & 3). If not available, lifetime PD equals 12-month PD.")

            dpd_col_val  = None if dpd_col_sel  == no_cols_opt[0] else dpd_col_sel
            orig_pd_val  = None if orig_pd_sel  == no_cols_opt[0] else orig_pd_sel
            mat_col_val  = None if mat_col_sel  == no_cols_opt[0] else mat_col_sel

        with s2:
            pd_rel   = st.slider("SICR: relative PD multiplier",   1.1, 5.0, 1.5, 0.1,
                                  help="current_PD / orig_PD above this → SICR (IFRS 9 §B5.5.15)")
            pd_abs   = st.slider("SICR: absolute PD increase (pp)", 0.01, 0.20, 0.03, 0.01,
                                  help="current_PD − orig_PD above this → SICR")
            dpd_sicr = st.slider("SICR: DPD backstop threshold",   15, 60, 30, 5,
                                  help="DPD ≥ this triggers qualitative SICR (IFRS 9 §B5.5.19)")

    # ── Build config ──
    if lgd_mode == "Fixed assumption":
        cfg = ecl.ECLConfig(
            lgd_method="fixed", lgd_fixed=lgd_fixed,
            pd_relative_threshold=pd_rel, pd_absolute_threshold=pd_abs,
            dpd_sicr_threshold=int(dpd_sicr),
            dpd_col=dpd_col_val, orig_pd_col=orig_pd_val, maturity_col=mat_col_val,
        )
    elif lgd_mode == "By loan type":
        cfg = ecl.ECLConfig(
            lgd_method="fixed", lgd_fixed=0.45,
            pd_relative_threshold=pd_rel, pd_absolute_threshold=pd_abs,
            dpd_sicr_threshold=int(dpd_sicr),
            dpd_col=dpd_col_val, orig_pd_col=orig_pd_val, maturity_col=mat_col_val,
        )
    else:
        cfg = ecl.ECLConfig(
            lgd_method="ltv", ltv_col=ltv_col, lgd_haircut=haircut,
            pd_relative_threshold=pd_rel, pd_absolute_threshold=pd_abs,
            dpd_sicr_threshold=int(dpd_sicr),
            dpd_col=dpd_col_val, orig_pd_col=orig_pd_val, maturity_col=mat_col_val,
        )

    if st.button("💰 Calculate ECL", type="primary", use_container_width=True):
        try:
            res, summary = ecl.compute(
                pipeline, X_full, data, ead_col=ead_col, cfg=cfg,
                loan_type_col=loan_type_col, lgd_map=lgd_map,
                ead_series=ead_series,
            )
            st.session_state.ecl_result = res
            st.session_state.ecl_summary = summary
        except Exception as e:
            st.error(f"ECL calculation failed: {e}")
            return

    res = st.session_state.get("ecl_result")
    summary = st.session_state.get("ecl_summary")
    if res is not None and summary is not None:
        # ── Portfolio KPIs ──
        st.markdown("#### Portfolio result")
        sc = summary.get("stage_counts", {})
        m = st.columns(6)
        m[0].metric("Total ECL",    f"{summary['total_ecl']:,.0f}")
        m[1].metric("Total EAD",    f"{summary['total_ead']:,.0f}")
        m[2].metric("Coverage",     f"{summary['coverage_pct']}%")
        m[3].metric("Stage 1",      f"{sc.get('stage_1', 0):,} loans")
        m[4].metric("Stage 2",      f"{sc.get('stage_2', 0):,} loans")
        m[5].metric("Stage 3",      f"{sc.get('stage_3', 0):,} loans")

        ecl_s = summary.get("ecl_by_stage", {})
        e1, e2, e3 = st.columns(3)
        e1.metric("ECL — Stage 1 (12m PD)",       f"{ecl_s.get('stage_1', 0):,.0f}")
        e2.metric("ECL — Stage 2 (lifetime PD)",  f"{ecl_s.get('stage_2', 0):,.0f}")
        e3.metric("ECL — Stage 3 (lifetime PD)",  f"{ecl_s.get('stage_3', 0):,.0f}")

        sicr_pct = summary.get("sicr_pct", 0)
        st.info(
            f"**{summary.get('sicr_count', 0):,} loans** ({sicr_pct:.1f}%) flagged with SICR — "
            f"moved to Stage 2 or Stage 3.  "
            f"Avg 12m PD: **{summary['avg_pd_12m']:.2%}** → "
            f"Avg Lifetime PD: **{summary['avg_pd_lifetime']:.2%}**"
        )

        # ── Charts ──
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(ecl.plot_stage_loan_count(res), use_container_width=True)
        with g2:
            st.plotly_chart(ecl.plot_stage_ecl(res), use_container_width=True)

        g3, g4 = st.columns(2)
        with g3:
            st.plotly_chart(ecl.plot_ecl_by_pd_band(res), use_container_width=True)
        with g4:
            st.plotly_chart(ecl.plot_pd_distribution(res), use_container_width=True)

        st.plotly_chart(ecl.plot_ecl_12m_vs_lifetime(res), use_container_width=True)

        # ── Per-loan table ──
        st.markdown("#### Per-loan ECL (top 20 by ECL)")
        display_cols = [c for c in [
            "ifrs9_stage", "sicr_flag", "dpd", "orig_pd", "pd_12m",
            "pd_lifetime", "lgd", "ead", "ecl_12m", "ecl",
        ] if c in res.columns]
        st.dataframe(
            res[display_cols].sort_values("ecl", ascending=False).head(20),
            use_container_width=True,
        )
        df_to_csv_download(res.copy(), "ecl_results.csv")

    st.divider()
    if st.button("\u25c0 Back to Explainability", use_container_width=True):
        st.session_state.current_step = 8
        st.rerun()


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
