"""
ead_ui.py — Streamlit UI for the EAD modelling pipeline (Model Development).

Two regimes, handled automatically:
  • Revolving products (cards / overdrafts): an ML model estimates the Credit
    Conversion Factor (CCF) from the defaulted revolving accounts, then
    EAD = drawn + CCF × (limit − drawn).
  • Non-revolving products (term loans): EAD from the amortisation schedule
    (outstanding principal + accrued interest).

Columns are auto-detected; the only choices are the model and (optional) FRED
macro date column. The resulting portfolio EAD is stored in
st.session_state.ead_values.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

import ead_engine as E
import fred_client
import ecl_engine as ecl   # amortisation column detectors reused for non-revolving

S_BUNDLE = "ccf_model_bundle"
S_EAD = "ead_values"


def _render_fred_key_input() -> None:
    """Render the FRED API key widget ONCE per EAD workflow render.
    Stores the entered key in st.session_state['_ead_fred_api_key'] so
    _get_fred_client() can be called multiple times without re-rendering."""
    env_key = os.environ.get("FRED_API_KEY", "")
    current = st.session_state.get("_ead_fred_api_key", env_key)
    entered = st.text_input(
        "FRED API key (optional — adds macro features to CCF)",
        value=current,
        type="password",
        key="ead_fred_key",
        help="Stored for this session only. Prefer the FRED_API_KEY environment variable.",
    )
    st.session_state["_ead_fred_api_key"] = entered


def _get_fred_client() -> Optional[fred_client.FREDClient]:
    """Return a FREDClient from the already-stored session-state key.
    Never renders a widget — always call _render_fred_key_input() first."""
    key = st.session_state.get("_ead_fred_api_key", os.environ.get("FRED_API_KEY", ""))
    return fred_client.FREDClient(api_key=key, cache_dir=".fred_cache") if key else None


def render_ead_workflow(data: pd.DataFrame, portfolio_index=None, y: Optional[pd.Series] = None) -> None:
    st.markdown("### 💳 EAD Model — Exposure at Default")
    # ── FRED API key — rendered ONCE here; _get_fred_client() reads from session state ──
    _render_fred_key_input()
    st.caption(
        "Revolving products (cards, overdrafts) use an ML-estimated Credit Conversion "
        "Factor: EAD = drawn + CCF × (limit − drawn), with CCF trained on defaulted "
        "revolving accounts. Non-revolving term loans use the amortisation schedule "
        "(outstanding principal + accrued interest). Everything is auto-detected."
    )

    all_cols = list(data.columns)
    det = E.detect_ccf_columns(data)
    product_col = det["product_col"]

    # ── 1. Split the book ─────────────────────────────────────────────────────
    st.markdown("#### 1 · Product split")
    p_opt = ["— all non-revolving (amortising) —"] + all_cols
    p_idx = p_opt.index(product_col) if product_col in p_opt else 0
    product_sel = st.selectbox("Product-type column (identifies revolving vs term)", p_opt, index=p_idx)
    product_col = None if product_sel == p_opt[0] else product_sel
    rev_mask = E.is_revolving(data, product_col)
    n_rev, n_non = int(rev_mask.sum()), int((~rev_mask).sum())
    c1, c2 = st.columns(2)
    c1.metric("Revolving (CCF)", f"{n_rev:,}")
    c2.metric("Non-revolving (amortised)", f"{n_non:,}")

    bundle = st.session_state.get(S_BUNDLE)

    # ── 2. CCF model for revolving accounts ───────────────────────────────────
    if n_rev > 0:
        st.markdown("#### 2 · CCF model (revolving accounts)")
        drawn_opt = ["— auto —"] + all_cols
        limit_opt = ["— auto —"] + all_cols
        eadd_opt = ["— auto —"] + all_cols
        cc1, cc2, cc3 = st.columns(3)
        drawn_col = cc1.selectbox("Drawn balance", drawn_opt,
                                  index=drawn_opt.index(det["drawn_col"]) if det["drawn_col"] in drawn_opt else 0)
        limit_col = cc2.selectbox("Credit limit", limit_opt,
                                  index=limit_opt.index(det["limit_col"]) if det["limit_col"] in limit_opt else 0)
        eadd_col = cc3.selectbox("EAD at default (for CCF target)", eadd_opt,
                                 index=eadd_opt.index(det["ead_at_default_col"]) if det["ead_at_default_col"] in eadd_opt else 0)
        drawn_col = None if drawn_col == "— auto —" else drawn_col
        limit_col = None if limit_col == "— auto —" else limit_col
        eadd_col = None if eadd_col == "— auto —" else eadd_col

        if not (drawn_col and limit_col):
            st.error("Need a drawn-balance and a credit-limit column to model revolving EAD.")
            return

        # Training population: DEFAULTED revolving accounts only. Realized CCF is
        # only observable once an account has defaulted, so — like the LGD model —
        # the CCF model must be trained on the defaulted book, never on current loans.
        if y is None:
            st.error("No PD target available — the CCF model must be trained on the "
                     "DEFAULTED revolving accounts (using the same default flag as the "
                     "PD model). Train the PD model first (Steps 1-6).")
            return
        yb = pd.Series(y).reindex(data.index).fillna(0).astype(float) > 0
        train_mask = rev_mask & yb          # revolving AND defaulted
        train_df = data[train_mask]
        st.caption(f"Defaulted revolving accounts (PD target = 1): **{int(train_mask.sum()):,}** rows.")
        if not eadd_col:
            st.error("Need an 'EAD at default' column to derive the realized CCF training target.")
            return
        ccf_target = E.derive_ccf_target(train_df, drawn_col, limit_col, eadd_col)
        n_ccf = int(ccf_target.notna().sum())
        st.caption(f"CCF training population — defaulted revolving accounts with headroom: "
                   f"**{n_ccf:,}** rows, mean realized CCF **{ccf_target.mean():.3f}**.")

        # optional FRED macro — use the key already entered at the top (no new widget)
        st.markdown("**Macro features (optional)**")
        date_opt = ["— none —"] + all_cols
        date_sel = st.selectbox("Loan date column for FRED macro alignment", date_opt, key="ead_date")
        date_col = None if date_sel == date_opt[0] else date_sel
        macro_cols: list = []
        train_with_macro = train_df
        if date_col:
            fc = _get_fred_client()   # reads from session state — no widget rendered
            if fc is not None:
                try:
                    train_with_macro, macro_cols = E.L.attach_macro(train_df, fred_client=fc, date_col=date_col)
                    if macro_cols:
                        st.success(f"Macro features attached: {', '.join(macro_cols)}")
                except fred_client.FREDError as e:
                    st.error(f"FRED fetch failed: {e}")
            else:
                st.info("Enter a FRED API key above to enable macro features.")

        exclude = {drawn_col, limit_col, eadd_col, date_col, product_col, *macro_cols}
        feature_cols = E.auto_feature_cols(train_df, exclude=exclude)

        # ── Feature transparency panel ──
        st.markdown("**📋 Features used to train the CCF model**")
        if feature_cols:
            _feat_rows = []
            for _fc in feature_cols:
                _fc_type = "macro" if _fc in macro_cols else "numeric" if pd.api.types.is_numeric_dtype(train_df.get(_fc, pd.Series(dtype=float))) else "categorical"
                _feat_rows.append({"Feature": _fc, "Type": _fc_type, "Role": "Predictor (CCF)"})
            st.dataframe(pd.DataFrame(_feat_rows), use_container_width=True, hide_index=True)
        else:
            st.warning("No predictor columns auto-selected — check that drawn/limit/EAD columns are excluded correctly.")

        model_name = st.selectbox("CCF model", E.available_models(), key="ead_model")
        if st.button("🚀 Train CCF model", type="primary", use_container_width=True, key="ead_train"):
            if n_ccf < 10:
                st.error(f"Only {n_ccf} usable CCF rows — need ≥ 10 defaulted revolving accounts with headroom.")
            elif not feature_cols:
                st.error("No predictor columns available.")
            else:
                try:
                    with st.spinner(f"Training {model_name} CCF model on {n_ccf:,} accounts…"):
                        bundle = E.train_ccf_model(train_with_macro, feature_cols, ccf_target,
                                                   model_name, macro_cols=macro_cols)
                    bundle["_cols"] = {"drawn": drawn_col, "limit": limit_col, "date": date_col}
                    st.session_state[S_BUNDLE] = bundle
                    st.success(f"✅ Trained {model_name} CCF model.")
                except Exception as e:
                    st.error(f"Training failed: {e}")

        bundle = st.session_state.get(S_BUNDLE)
        if bundle:
            tm = bundle["metrics"].get("test", {})
            m1, m2, m3 = st.columns(3)
            m1.metric("CCF Test R²", tm.get("r2", "—"))
            m2.metric("CCF Test MAE", tm.get("mae", "—"))
            m3.metric("CCF Test RMSE", tm.get("rmse", "—"))
            if bundle.get("importances"):
                st.markdown("**CCF Feature Importance (by model weight)**")
                imp_df = pd.DataFrame(bundle["importances"][:15])
                st.bar_chart(imp_df.set_index("feature")["importance"])
                st.dataframe(imp_df.rename(columns={"feature": "Feature", "importance": "Importance"}),
                             use_container_width=True, hide_index=True)

    # ── 3. Non-revolving inputs (amortisation) ────────────────────────────────
    st.markdown("#### 3 · Non-revolving (amortisation) inputs")
    la_d = ecl.detect_loan_amount_col(data)
    ir_d = ecl.detect_interest_rate_col(data)
    ye_d, ye_is_m = ecl.detect_years_elapsed_col(data)
    tm_d = ecl.detect_term_col(data)
    a1, a2 = st.columns(2)
    NA = "— not available —"
    la = a1.selectbox("Loan amount", [NA] + all_cols, index=([NA]+all_cols).index(la_d) if la_d in all_cols else 0)
    ir = a1.selectbox("Interest rate", [NA] + all_cols, index=([NA]+all_cols).index(ir_d) if ir_d in all_cols else 0)
    ye = a2.selectbox("Elapsed time", [NA] + all_cols, index=([NA]+all_cols).index(ye_d) if ye_d in all_cols else 0)
    tmc = a2.selectbox("Loan term", [NA] + all_cols, index=([NA]+all_cols).index(tm_d) if tm_d in all_cols else 0)
    ye_months = st.checkbox("Elapsed time is in months", value=bool(ye_is_m), key="ead_ye_m")
    tm_months = st.checkbox("Loan term is in months", value=False, key="ead_tm_m")

    # ── 4. Compute portfolio EAD ──────────────────────────────────────────────
    st.markdown("#### 4 · Compute portfolio EAD")
    port = data if portfolio_index is None else data.reindex(portfolio_index)
    port_rev = E.is_revolving(port, product_col)

    if st.button("Compute EAD for the whole portfolio", type="primary",
                 use_container_width=True, key="ead_compute"):
        ccf_series = None
        if port_rev.any():
            if not bundle:
                st.error("Train the CCF model first (step 2) to price revolving EAD.")
                return
            cols = bundle.get("_cols", {})
            port_macro = None
            if bundle.get("macro_cols") and cols.get("date"):
                fc2 = _get_fred_client()   # reads session state — no widget rendered
                if fc2 is not None:
                    try:
                        port_macro = fc2.macro_features_for_dates(port[cols["date"]])
                        port_macro.index = port.index
                    except fred_client.FREDError as e:
                        st.warning(f"Macro fetch for portfolio failed ({e}); predicting without macro.")
            ccf_series = pd.Series(np.nan, index=port.index)
            ccf_series.loc[port_rev] = E.predict_ccf(bundle, port[port_rev], macro_aligned=port_macro).values

        try:
            ead = E.compute_portfolio_ead(
                port, port_rev,
                drawn_col=det["drawn_col"], limit_col=det["limit_col"], ccf_series=ccf_series,
                loan_amount_col=None if la == NA else la,
                interest_rate_col=None if ir == NA else ir,
                years_elapsed_col=None if ye == NA else ye,
                term_col=None if tmc == NA else tmc,
                years_in_months=ye_months, term_in_months=tm_months,
            )
        except Exception as e:
            st.error(f"EAD computation failed: {e}")
            return

        ead = ead.astype(float)
        ead.name = "ead"
        st.session_state[S_EAD] = ead
        st.session_state["ead_method"] = "EAD model (CCF for revolving + amortisation for term loans)"
        n_ok = int(ead.notna().sum())
        st.success(f"✅ Portfolio EAD computed for {n_ok:,}/{len(ead):,} loans.")
        r1, r2, r3 = st.columns(3)
        r1.metric("Revolving EAD (mean)", f"{ead[port_rev].mean():,.0f}" if port_rev.any() else "—")
        r2.metric("Non-revolving EAD (mean)", f"{ead[~port_rev].mean():,.0f}" if (~port_rev).any() else "—")
        r3.metric("Total EAD", f"{ead.sum():,.0f}")
