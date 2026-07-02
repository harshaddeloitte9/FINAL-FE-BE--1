"""
lgd_ui.py — Streamlit UI for the LGD modelling pipeline (Model Development).

Structured into sub-tabs that mirror the PD pipeline (only the steps that suit a
continuous LGD target):

  🔬 Feature Engineering — indexed LTV via FRED HPI (home loans) + multicollinearity
                           / low-variance review. WOE/IV binning is intentionally
                           excluded (it is for binary targets, not regression).
  🎯 Training           — FRED macro features, model choice, fit on the DEFAULTED book.
  📊 Evaluation         — train/test split metrics (R²/MAE/RMSE) + predicted-vs-actual
                           and residual diagnostics on the held-out test set.
  📥 Apply & Report     — predict LGD for the portfolio and download an estimated-LGD
                           report for all loans.

The trained bundle is stored in st.session_state["lgd_model_bundle"] so render_ecl /
the EAD tab gate can consume it.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

import lgd_engine as L
import fred_client

S_BUNDLE = "lgd_model_bundle"
S_PORT_LGD = "lgd_portfolio_pred"
S_PORT_MACRO = "lgd_portfolio_macro"
S_DATA_ENG = "lgd_data_eng"        # dataset augmented with indexed_ltv
S_FEATURES = "lgd_features"        # finalised predictor list
S_EXCLUDE_LTV = "lgd_original_ltv" # original LTV col replaced by indexed_ltv


def _render_fred_key_input() -> None:
    """Render the FRED API key widget ONCE at the top of the LGD workflow.
    Stores the key in st.session_state['_lgd_fred_api_key']."""
    env_key = os.environ.get("FRED_API_KEY", "")
    current = st.session_state.get("_lgd_fred_api_key", env_key)
    entered = st.text_input(
        "FRED API key",
        value=current,
        type="password",
        key="lgd_fred_key",
        help="Used for HPI (indexed LTV) and macro features. Prefer FRED_API_KEY env var.",
    )
    st.session_state["_lgd_fred_api_key"] = entered


def _get_fred_client() -> Optional[fred_client.FREDClient]:
    """Return a FREDClient from session state. Never renders a widget."""
    key = st.session_state.get("_lgd_fred_api_key", os.environ.get("FRED_API_KEY", ""))
    return fred_client.FREDClient(api_key=key, cache_dir=".fred_cache") if key else None


# ══════════════════════════════════════════════════════════════════════════════
def render_lgd_workflow(data: pd.DataFrame, portfolio_index=None, y: Optional[pd.Series] = None) -> None:
    st.markdown("### 🧮 LGD Model (trained on defaulted loans)")
    # ── FRED API key — rendered ONCE here for both HPI and macro use ──
    _render_fred_key_input()
    st.caption(
        "Regression model for Loss Given Default, trained on the loans that defaulted "
        "in your uploaded dataset (same default flag as the PD model), enriched with "
        "point-in-time FRED macro features. Same dataset — no re-upload."
    )

    if y is None:
        st.error("No PD target available yet — train the PD model first (Steps 1-6); "
                 "the LGD training population is derived from it automatically.")
        return

    train_pop = L.filter_defaulted_by_target(data, y)
    if len(train_pop) < 10:
        st.error(f"Only {len(train_pop):,} defaulted rows found — need ≥ 10 to train an LGD model.")
        return

    # realized-LGD target (auto-detected)
    det = L.detect_lgd_target(train_pop)
    lgd_col, rr_col, rec_col, exp_col = (det["lgd_col"], det["recovery_rate_col"],
                                         det["recovery_amount_col"], det["exposure_col"])
    if not (lgd_col or rr_col or (rec_col and exp_col)):
        st.error("Could not auto-detect a realized-LGD target (explicit LGD, recovery rate, "
                 "or recovery amount + exposure). Add one of these to the dataset.")
        return
    try:
        target = L.derive_lgd_target(train_pop, lgd_col=lgd_col, recovery_rate_col=rr_col,
                                     recovery_amount_col=rec_col, exposure_col=exp_col)
    except Exception as e:
        st.error(f"Could not derive the LGD target: {e}")
        return
    tgt_src = lgd_col or rr_col or f"{rec_col} ÷ {exp_col}"
    st.caption(f"Defaulted population **{len(train_pop):,}** · target from `{tgt_src}` "
               f"(mean LGD **{target.mean():.3f}**).")

    tabs = st.tabs(["🔬 Feature Engineering", "🎯 Training", "📊 Evaluation", "📥 Apply & Report"])
    with tabs[0]:
        _fe_tab(data, train_pop)
    with tabs[1]:
        _training_tab(data, train_pop, target)
    with tabs[2]:
        _eval_tab()
    with tabs[3]:
        _apply_tab(data, portfolio_index)


# ── 🔬 Feature Engineering ────────────────────────────────────────────────────
def _fe_tab(data: pd.DataFrame, train_pop: pd.DataFrame) -> None:
    st.markdown("#### Feature engineering (regression-appropriate)")
    st.caption("WOE/IV binning from the PD pipeline is intentionally excluded — it is a "
               "binary-target technique. Included: indexed LTV, multicollinearity removal, "
               "and low-variance removal.")
    all_cols = list(data.columns)
    work = st.session_state.get(S_DATA_ENG, data).copy()

    # ── Indexed LTV via FRED HPI (home loans) ──
    st.markdown("##### 🏠 Indexed LTV (home loans, via FRED HPI)")
    st.caption("Indexed LTV = origination LTV × HPI(origination) ÷ HPI(current). Reflects "
               "collateral revaluation since origination instead of the stale origination LTV. "
               "Applied to home loans only; other products keep their origination LTV.")
    ltv_d = L.detect_ltv_col(data)
    od_d = L.detect_origination_date_col(data)
    pc_d = L.detect_product_col(data)
    if not ltv_d or not od_d:
        st.info("Need an LTV column and an origination-date column to index LTV — not both "
                "auto-detected. Select them below if available.")
    c1, c2, c3 = st.columns(3)
    ltv_col = c1.selectbox("LTV column", ["— none —"] + all_cols,
                           index=(all_cols.index(ltv_d) + 1) if ltv_d in all_cols else 0)
    od_col = c2.selectbox("Origination date", ["— none —"] + all_cols,
                          index=(all_cols.index(od_d) + 1) if od_d in all_cols else 0)
    pc_col = c3.selectbox("Product type (home-loan flag)", ["— treat all as home —"] + all_cols,
                          index=(all_cols.index(pc_d) + 1) if pc_d in all_cols else 0)
    hpi_series = st.text_input("FRED HPI series ID", value=L.HPI_SERIES_DEFAULT,
                               help="Default: S&P/Case-Shiller U.S. National HPI (CSUSHPINSA).")
    fc = _get_fred_client()
    if st.button("🏠 Compute indexed LTV", key="lgd_index_ltv"):
        if ltv_col == "— none —" or od_col == "— none —":
            st.error("Select both an LTV column and an origination-date column.")
        elif fc is None:
            st.error("Enter a FRED API key to fetch the HPI series.")
        else:
            try:
                idx_ltv, is_home, hpi_now = L.index_ltv_with_hpi(
                    data, ltv_col, od_col, fc, hpi_series=hpi_series,
                    product_col=None if pc_col == "— treat all as home —" else pc_col,
                )
                work["indexed_ltv"] = idx_ltv
                st.session_state[S_DATA_ENG] = work
                st.session_state[S_EXCLUDE_LTV] = ltv_col
                n_home = int(is_home.sum())
                st.success(f"✅ Indexed LTV computed (current HPI {hpi_now:,.1f}); "
                           f"{n_home:,} home loans re-indexed. "
                           f"`indexed_ltv` will replace `{ltv_col}` in the feature set.")
                # Build full report for all home loans (not just a preview)
                _id_col = next((c for c in data.columns
                                if c.lower() in ("loan_id", "customer_id", "account_id", "id")), None)
                _ltv_report = pd.DataFrame({
                    **({_id_col: data.loc[is_home.index, _id_col].values} if _id_col else
                       {"row_index": is_home.index}),
                    "home_loan": is_home.values,
                    "origination_ltv": pd.to_numeric(data[ltv_col], errors="coerce").values,
                    "indexed_ltv": idx_ltv.round(4).values,
                    "ltv_change_pp": (idx_ltv - pd.to_numeric(data[ltv_col], errors="coerce")).round(4).values,
                })
                # show only home-loan rows (indexed_ltv was applied there)
                _ltv_report_home = _ltv_report[_ltv_report["home_loan"]]
                m1c, m2c, m3c = st.columns(3)
                m1c.metric("Home loans re-indexed", f"{n_home:,}")
                m2c.metric("Mean origination LTV", f"{_ltv_report_home['origination_ltv'].mean():.3f}")
                m3c.metric("Mean indexed LTV", f"{_ltv_report_home['indexed_ltv'].mean():.3f}")
                st.download_button(
                    "📥 Download home-loan LTV report (CSV)",
                    data=_ltv_report_home.to_csv(index=False).encode("utf-8"),
                    file_name="home_loan_ltv_report.csv",
                    mime="text/csv",
                    key="lgd_ltv_report_download",
                )
            except fred_client.FREDError as e:
                st.error(f"FRED HPI fetch failed: {e}")
            except Exception as e:
                st.error(f"Indexed LTV failed: {e}")

    work = st.session_state.get(S_DATA_ENG, data)
    train_eng = work.loc[train_pop.index]

    # ── Feature set + multicollinearity / low-variance review ──
    st.markdown("##### 🧮 Predictor set")
    excl = {L.detect_lgd_target(train_pop).get(k) for k in
            ("lgd_col", "recovery_rate_col", "recovery_amount_col", "exposure_col")}
    orig_ltv = st.session_state.get(S_EXCLUDE_LTV)
    if orig_ltv:
        excl.add(orig_ltv)  # replaced by indexed_ltv
    base_feats = L.auto_feature_cols(train_eng, exclude=excl)
    if "indexed_ltv" in train_eng.columns and "indexed_ltv" not in base_feats:
        base_feats = ["indexed_ltv"] + base_feats

    corr_pairs = L.lgd_correlation_report(train_eng, base_feats)
    low_var = L.lgd_low_variance(train_eng, base_feats)
    if corr_pairs:
        st.warning("Highly-correlated pairs (consider dropping one of each): " +
                   ", ".join(f"`{p['feature_1']}`↔`{p['feature_2']}` ({p['correlation']})"
                             for p in corr_pairs[:6]))
    if low_var:
        st.warning("Near-constant (low-variance) features: " + ", ".join(f"`{c}`" for c in low_var))

    default_sel = [f for f in base_feats if f not in low_var]
    features = st.multiselect("Final predictors for the LGD model", base_feats, default=default_sel,
                              key="lgd_feature_select")
    st.session_state[S_FEATURES] = features
    st.caption(f"{len(features)} predictor(s) selected"
               + (" · includes `indexed_ltv`" if "indexed_ltv" in features else ""))

    # ── Feature transparency: show which features will be used ────────────────
    if features:
        st.markdown("##### 📋 Features that will be used to train the LGD model")
        _feat_rows = []
        for _f in features:
            if _f == "indexed_ltv":
                _ftype, _note = "numeric (derived)", "HPI-indexed collateral value"
            elif _f in [c for c in base_feats if corr_pairs and any(_f in (p["feature_1"], p["feature_2"]) for p in corr_pairs)]:
                _ftype, _note = "numeric", "⚠️ correlated with another feature"
            elif _f in low_var:
                _ftype, _note = "numeric", "⚠️ near-constant (low variance)"
            elif pd.api.types.is_numeric_dtype(train_eng.get(_f, pd.Series(dtype=float))):
                _ftype, _note = "numeric", ""
            else:
                _ftype, _note = "categorical", ""
            _feat_rows.append({"Feature": _f, "Type": _ftype, "Notes": _note})
        st.dataframe(pd.DataFrame(_feat_rows), use_container_width=True, hide_index=True)
    else:
        st.warning("No features selected — choose at least one predictor above.")


# ── 🎯 Training ───────────────────────────────────────────────────────────────
def _training_tab(data: pd.DataFrame, train_pop: pd.DataFrame, target: pd.Series) -> None:
    st.markdown("#### Training")
    work = st.session_state.get(S_DATA_ENG, data)
    train_eng = work.loc[train_pop.index]
    features = st.session_state.get(S_FEATURES)
    if not features:
        st.info("Set the predictor list in the **🔬 Feature Engineering** tab first.")
        return
    st.caption(f"Training on **{len(train_eng):,}** defaulted loans · {len(features)} predictors.")

    # macro
    st.markdown("##### Macroeconomic features (FRED)")
    all_cols = list(data.columns)
    date_opt = ["— none —"] + all_cols
    date_sel = st.selectbox("Loan date column for point-in-time macro alignment", date_opt, key="lgd_macro_date")
    date_col = None if date_sel == date_opt[0] else date_sel
    macro_cols: list = []
    train_with_macro = train_eng
    fc = _get_fred_client() if date_col else None
    if fc is not None and date_col:
        try:
            train_with_macro, macro_cols = L.attach_macro(train_eng, fred_client=fc, date_col=date_col)
            if macro_cols:
                st.success(f"Macro features attached: {', '.join(macro_cols)}")
        except fred_client.FREDError as e:
            st.error(f"FRED fetch failed: {e}")

    # ── Training feature summary ────────────────────────────────────────────────
    all_train_feats = features + [c for c in macro_cols if c not in features]
    st.markdown("##### 📋 Final feature set for training")
    _train_feat_rows = [
        {"Feature": f, "Source": "macro (FRED)" if f in macro_cols else "dataset",
         "Type": "numeric" if pd.api.types.is_numeric_dtype(train_with_macro.get(f, pd.Series(dtype=float))) else "categorical"}
        for f in all_train_feats
    ]
    st.dataframe(pd.DataFrame(_train_feat_rows), use_container_width=True, hide_index=True)
    st.caption(f"{len(features)} dataset feature(s) + {len(macro_cols)} FRED macro feature(s) = "
               f"{len(all_train_feats)} total predictors.")

    model_name = st.selectbox("Model", L.available_models(), key="lgd_model")
    test_size = st.slider("Test-set proportion", 0.1, 0.4, 0.2, 0.05, key="lgd_test_size")

    if st.button("🚀 Train LGD model", type="primary", use_container_width=True, key="lgd_train"):
        try:
            with st.spinner(f"Training {model_name} on {len(train_with_macro):,} defaulted loans…"):
                bundle = L.train_lgd_model(train_with_macro, features, target, model_name,
                                           macro_cols=macro_cols, test_size=test_size)
            st.session_state[S_BUNDLE] = bundle
            st.session_state["lgd_date_col"] = date_col
            st.success(f"✅ Trained {model_name}. See the **📊 Evaluation** tab for test-set metrics.")
        except Exception as e:
            st.error(f"Training failed: {e}")

    bundle = st.session_state.get(S_BUNDLE)
    if bundle:
        tm = bundle["metrics"].get("test", {})
        m1, m2, m3 = st.columns(3)
        m1.metric("Test R²", tm.get("r2", "—"))
        m2.metric("Test MAE", tm.get("mae", "—"))
        m3.metric("Test RMSE", tm.get("rmse", "—"))


# ── 📊 Evaluation ─────────────────────────────────────────────────────────────
def _eval_tab() -> None:
    st.markdown("#### Evaluation (held-out test split)")
    bundle = st.session_state.get(S_BUNDLE)
    if not bundle:
        st.info("Train the LGD model in the **🎯 Training** tab first.")
        return
    ev = bundle.get("eval", {})
    tr, te = bundle["metrics"].get("train", {}), bundle["metrics"].get("test", {})
    st.caption(f"Defaulted loans split into train **{ev.get('n_train','?')}** / "
               f"test **{ev.get('n_test','?')}** (test size {ev.get('test_size','?')}). "
               "Metrics below are on the held-out test set the model never saw.")

    c = st.columns(4)
    c[0].metric("Test R²", te.get("r2", "—"), help="Train R²: " + str(tr.get("r2", "—")))
    c[1].metric("Test MAE", te.get("mae", "—"))
    c[2].metric("Test RMSE", te.get("rmse", "—"))
    c[3].metric("Train R²", tr.get("r2", "—"))
    _overfit = (tr.get("r2") or 0) - (te.get("r2") or 0)
    if _overfit > 0.2:
        st.warning(f"Train R² exceeds test R² by {_overfit:.2f} — possible overfitting; "
                   "consider a simpler model or fewer features.")

    y_test = np.array(ev.get("y_test", []))
    p_test = np.array(ev.get("pred_test", []))
    if len(y_test) >= 2:
        st.markdown("##### Predicted vs actual LGD (test set)")
        sc = pd.DataFrame({"actual_LGD": y_test, "predicted_LGD": p_test})
        st.scatter_chart(sc, x="actual_LGD", y="predicted_LGD", height=320)
        st.caption("Points on the diagonal are perfect predictions.")

        st.markdown("##### Residuals (actual − predicted)")
        resid = y_test - p_test
        counts, edges = np.histogram(resid, bins=20)
        hist = pd.DataFrame({"residual": np.round((edges[:-1] + edges[1:]) / 2, 3), "count": counts})
        st.bar_chart(hist, x="residual", y="count", height=240)
        st.caption(f"Residual mean {resid.mean():+.3f}, std {resid.std():.3f} "
                   "(centred near 0 with no skew is ideal).")

    if bundle.get("importances"):
        st.markdown("##### Feature importance (model-derived)")
        imp_df = pd.DataFrame(bundle["importances"])
        st.bar_chart(imp_df.head(15).set_index("feature")["importance"])
        with st.expander(f"📋 All {len(imp_df)} features ranked by importance", expanded=False):
            st.dataframe(
                imp_df.rename(columns={"feature": "Feature", "importance": "Importance"})
                      .reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )
        if len(imp_df) >= 2:
            top1 = imp_df.iloc[0]["feature"]
            top1_imp = imp_df.iloc[0]["importance"]
            top2 = imp_df.iloc[1]["feature"]
            st.caption(f"Top driver: `{top1}` ({top1_imp:.3f}). "
                       f"Second: `{top2}`. "
                       "If only one or two features dominate, consider whether there is data leakage.")


# ── 📥 Apply & Report ─────────────────────────────────────────────────────────
def _apply_tab(data: pd.DataFrame, portfolio_index=None) -> None:
    st.markdown("#### Apply to the portfolio & download report")
    bundle = st.session_state.get(S_BUNDLE)
    if not bundle:
        st.info("Train the LGD model in the **🎯 Training** tab first.")
        return
    work = st.session_state.get(S_DATA_ENG, data)
    port = work if portfolio_index is None else work.reindex(portfolio_index)
    all_cols = list(work.columns)

    port_macro = None
    if bundle.get("macro_cols"):
        fc = _get_fred_client()
        pdate_opt = ["— use latest available macro —"] + all_cols
        _d = st.session_state.get("lgd_date_col")
        pdate_sel = st.selectbox("Portfolio reporting-date column (for macro)", pdate_opt,
                                 index=pdate_opt.index(_d) if _d in pdate_opt else 0, key="lgd_apply_date")
        if fc is not None:
            try:
                if pdate_sel != pdate_opt[0]:
                    port_macro = fc.macro_features_for_dates(port[pdate_sel])
                else:
                    last = fc.fetch_macro().ffill().iloc[-1]
                    port_macro = pd.DataFrame({f"macro_{k}": [float(v)] * len(port) for k, v in last.items()},
                                              index=port.index)
                port_macro.index = port.index
            except fred_client.FREDError as e:
                st.error(f"FRED fetch for portfolio failed: {e}")

    if st.button("Predict LGD for the whole portfolio", type="primary",
                 use_container_width=True, key="lgd_predict"):
        try:
            lgd_pred = L.predict_lgd(bundle, port, macro_aligned=port_macro)
            st.session_state[S_PORT_LGD] = lgd_pred
            st.session_state[S_PORT_MACRO] = port_macro
            st.success(f"Predicted LGD for {len(lgd_pred):,} loans — mean {float(lgd_pred.mean()):.3f}.")
        except Exception as e:
            st.error(f"Prediction failed: {e}")

    lgd_pred = st.session_state.get(S_PORT_LGD)
    if lgd_pred is None:
        return

    lgd_pred = pd.Series(lgd_pred).reindex(port.index)
    st.markdown("##### 📥 Estimated-LGD report (all loans)")
    m1, m2, m3 = st.columns(3)
    m1.metric("Loans scored", f"{int(lgd_pred.notna().sum()):,}")
    m2.metric("Mean LGD", f"{float(lgd_pred.mean()):.3f}")
    m3.metric("Median LGD", f"{float(lgd_pred.median()):.3f}")

    id_col = next((c for c in work.columns if c.lower() in
                   ("loan_id", "customer_id", "account_id", "id")), None)
    report = pd.DataFrame({
        **({id_col: port[id_col].values} if id_col else {"row_index": port.index}),
        "estimated_lgd": lgd_pred.round(4).values,
    })
    # attach the model's key predictors for context
    for c in bundle.get("feature_cols", [])[:8]:
        if c in port.columns:
            report[c] = port[c].values
    st.dataframe(report.head(25), use_container_width=True)
    st.download_button(
        "⬇️ Download estimated LGD for all loans (CSV)",
        data=report.to_csv(index=False).encode("utf-8"),
        file_name="lgd_estimates_all_loans.csv",
        mime="text/csv",
        key="lgd_report_download",
    )
