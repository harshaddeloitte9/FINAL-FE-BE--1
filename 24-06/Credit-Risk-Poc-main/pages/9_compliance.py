"""
pages/9_compliance.py
Agent 2 Regulatory Compliance Dashboard — reads from st.session_state["agent2_report"].
"""

import json
import streamlit as st

st.set_page_config(
    page_title="Compliance Dashboard",
    page_icon="🛡️",
    layout="wide",
)

_SEV_COLOR = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
_SEV_ICON  = {"high": "🔴",      "medium": "🟡",      "low": "🟢"}
_STATUS_BG = {"PASS": "#064e3b", "WARN": "#78350f",   "FAIL": "#450a0a"}
_STATUS_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}


def _badge(text: str, color: str, text_color: str = "white") -> str:
    return (
        f"<span style='background:{color}; color:{text_color}; "
        f"padding:0.15rem 0.55rem; border-radius:12px; "
        f"font-size:0.75rem; font-weight:700;'>{text}</span>"
    )


def _render_tier_card_compliance(tier_result: dict) -> None:
    """Render the SS1/23 model risk tier card (standalone copy for the compliance page)."""
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


def _flag_card(flag: dict) -> None:
    sev = flag.get("severity", "low")
    border = _SEV_COLOR.get(sev, "#6366f1")
    icon = _SEV_ICON.get(sev, "⚪")
    not_verifiable = flag.get("not_verifiable", False)

    card_bg = "#1e293b" if not not_verifiable else "#0f172a"
    border_left = f"3px solid {border}" if not not_verifiable else "3px solid #475569"

    ov = flag.get("observed_value")
    observed_html = (
        f"<small style='color:#94a3b8;'>📊 Observed: <code>{ov}</code></small><br>"
        if ov is not None else ""
    )
    nv_label = " <em style='color:#64748b; font-size:0.8rem;'>(not verifiable with current data)</em>" if not_verifiable else ""

    st.markdown(
        f"""
        <div style='border-left:{border_left}; padding:0.6rem 1rem;
                    margin:0.4rem 0; background:{card_bg}; border-radius:0 6px 6px 0;'>
            <strong>{icon} [{flag.get('rule_id','?')}]{nv_label}</strong><br>
            <span style='color:#e2e8f0;'>{flag.get('flag','')}</span><br>
            <small style='color:#64748b;'>
                📋 {flag.get('source','?')} — {flag.get('principle','?')}
            </small><br>
            {observed_html}
            <small style='color:#94a3b8;'>💡 {flag.get('suggestion','')}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_compliance_dashboard() -> None:
    st.markdown("""
    <div style='background:#1e293b; border-left:4px solid #6366f1;
                border-radius:0 8px 8px 0; padding:0.8rem 1.2rem; margin-bottom:1rem;'>
        <h2 style='margin:0; color:#e2e8f0;'>🛡️ Agent 2 — Regulatory Compliance Dashboard</h2>
        <p style='margin:0; color:#94a3b8; font-size:0.85rem;'>
            SS1/23 Model Risk · IFRS 9 ECL &amp; Staging · IFRS 7 Disclosure
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Re-run button ─────────────────────────────────────────────────────────
    if st.button("🔄 Re-run Compliance Checks", help="Clears cached results and re-runs all Agent 2 checks on the next pipeline visit"):
        for _k in list(st.session_state.keys()):
            if _k.startswith("agent2_"):
                del st.session_state[_k]
        st.session_state.pop("model_tier", None)
        st.rerun()

    # ── Model risk tier ───────────────────────────────────────────────────────
    _tier = st.session_state.get("model_tier")
    if _tier:
        _render_tier_card_compliance(_tier)
    else:
        st.info(
            "ℹ️ Complete training and evaluation (Steps 6–7) to see the SS1/23 model risk tier."
        )

    st.divider()

    report: dict = st.session_state.get("agent2_report", {})

    if not report:
        st.info(
            "No compliance data yet. Run the pipeline through at least the Data Profiling step "
            "to generate compliance flags."
        )
        return

    meta    = report.get("metadata", {})
    summary = report.get("summary", {})
    status  = summary.get("overall_status", "PASS")

    # ── Overall status banner ─────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style='background:{_STATUS_BG.get(status,"#1e293b")};
                    border:1px solid {_SEV_COLOR.get("high","#6366f1") if status=="FAIL"
                                      else (_SEV_COLOR.get("medium","#6366f1") if status=="WARN"
                                            else "#10b981")};
                    border-radius:8px; padding:1rem 1.5rem; margin-bottom:1rem;'>
            <h3 style='margin:0; color:#f8fafc;'>
                {_STATUS_ICON.get(status,'')} Overall Status: {status}
            </h3>
            <p style='margin:0.3rem 0 0; color:#cbd5e1; font-size:0.9rem;'>
                Compliance score: <strong>{meta.get('compliance_score',0):.1f}%</strong>
                &nbsp;·&nbsp;
                {meta.get('rules_passed',0)} / {meta.get('total_rules',0)} rules passed
                &nbsp;·&nbsp;
                Generated: {meta.get('generated_at','—')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Severity breakdown ────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 High",   summary.get("high_severity", 0))
    c2.metric("🟡 Medium", summary.get("medium_severity", 0))
    c3.metric("🟢 Low",    summary.get("low_severity", 0))
    c4.metric("📋 Total Flags", meta.get("rules_flagged", 0))

    st.divider()

    # ── Per-stage expanders ───────────────────────────────────────────────────
    flags_by_stage: dict = report.get("flags_by_stage", {})
    stage_labels = {
        "data": "📥 Data Quality",
        "feature": "🔬 Feature Engineering",
        "training": "🎯 Model Training",
        "evaluation": "📊 Evaluation & Compliance",
    }

    for stage_key in ("data", "feature", "training", "evaluation"):
        stage_flags = flags_by_stage.get(stage_key, [])
        label = stage_labels.get(stage_key, stage_key.capitalize())

        high_n   = sum(1 for f in stage_flags if f.get("severity") == "high")
        medium_n = sum(1 for f in stage_flags if f.get("severity") == "medium")
        low_n    = sum(1 for f in stage_flags if f.get("severity") == "low")
        nv_n     = sum(1 for f in stage_flags if f.get("not_verifiable"))

        if not stage_flags:
            st.success(f"✅ {label} — No compliance flags")
            continue

        badge_parts = []
        if high_n:   badge_parts.append(_badge(f"🔴 {high_n} High", "#7f1d1d"))
        if medium_n: badge_parts.append(_badge(f"🟡 {medium_n} Medium", "#78350f"))
        if low_n:    badge_parts.append(_badge(f"🟢 {low_n} Low", "#064e3b"))
        if nv_n:     badge_parts.append(_badge(f"⚪ {nv_n} Not Verifiable", "#1e293b", "#94a3b8"))

        with st.expander(
            f"🛡️ {label} — {len(stage_flags)} flag(s)   " + "  ".join(badge_parts),
            expanded=(high_n > 0),
        ):
            verifiable   = [f for f in stage_flags if not f.get("not_verifiable")]
            unverifiable = [f for f in stage_flags if f.get("not_verifiable")]

            if verifiable:
                st.markdown("##### Compliance Flags")
                for flag in sorted(verifiable, key=lambda f: {"high": 0, "medium": 1, "low": 2}.get(f.get("severity","low"), 9)):
                    _flag_card(flag)

            if unverifiable:
                st.markdown("##### Not Verifiable with Current Dataset")
                st.caption(
                    "These rules require fields not present in the uploaded data. "
                    "Verify them manually against your regulatory documentation."
                )
                for flag in unverifiable:
                    _flag_card(flag)

    # ── Source breakdown ──────────────────────────────────────────────────────
    flags_by_source: dict = report.get("flags_by_source", {})
    if flags_by_source:
        st.divider()
        st.markdown("#### 📋 Flags by Regulatory Source")
        src_cols = st.columns(min(len(flags_by_source), 3))
        for i, (src, src_flags) in enumerate(flags_by_source.items()):
            with src_cols[i % len(src_cols)]:
                h = sum(1 for f in src_flags if f.get("severity") == "high")
                m = sum(1 for f in src_flags if f.get("severity") == "medium")
                l = sum(1 for f in src_flags if f.get("severity") == "low")
                st.markdown(
                    f"**{src}** — {len(src_flags)} flag(s)<br>"
                    f"{_badge(f'🔴 {h}', '#7f1d1d')} "
                    f"{_badge(f'🟡 {m}', '#78350f')} "
                    f"{_badge(f'🟢 {l}', '#064e3b')}",
                    unsafe_allow_html=True,
                )

    # ── JSON download ─────────────────────────────────────────────────────────
    st.divider()
    report_json = json.dumps(report, indent=2, default=str)
    st.download_button(
        "⬇️ Download Full Compliance Report (JSON)",
        data=report_json,
        file_name="agent2_compliance_report.json",
        mime="application/json",
        use_container_width=True,
    )


render_compliance_dashboard()
