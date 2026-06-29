"""
agent2.py
Regulatory compliance checker for the credit risk ML pipeline.
Loads rules from rag/rules.json and checks data, features, training, and
evaluation stages against SS1/23, IFRS 9, and IFRS 7 requirements.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")


class Agent2:
    def __init__(self, rules_path: str = "rag_store/rules.json"):
        path = Path(rules_path)
        with path.open(encoding="utf-8") as f:
            self.rules: list[dict] = json.load(f)
        self._rules_by_check: dict[str, dict] = {r["check"]: r for r in self.rules}
        self._flags: dict[str, list[dict]] = {
            "data": [], "feature": [], "training": [], "evaluation": []
        }
        self._stages_checked: set[str] = set()
        self._tier_result: dict | None = None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _rule(self, check_name: str) -> dict | None:
        return self._rules_by_check.get(check_name)

    def _make_flag(
        self,
        rule: dict,
        observed_value: Any = None,
        flag_override: str | None = None,
    ) -> dict:
        return {
            "rule_id": rule["id"],
            "source": rule["source"],
            "principle": rule["principle"],
            "stage": rule["stage"],
            "severity": rule["severity"],
            "flag": flag_override or rule["flag"],
            "suggestion": rule["suggestion"],
            "observed_value": observed_value,
        }

    # ── Data Stage ───────────────────────────────────────────────────────────

    def check_data(self, df, col_types: dict, leakage_risk_cols: list | None = None) -> list[dict]:
        flags: list[dict] = []
        self._stages_checked.add("data")
        self._flags["data"].clear()

        # R01 missing_threshold
        r = self._rule("missing_threshold")
        if r:
            bad = [c for c in df.columns if df[c].isna().mean() > r["threshold"]]
            if bad:
                flags.append(self._make_flag(
                    r, observed_value=bad,
                    flag_override=f"High missing data (>{r['threshold']*100:.0f}%) in: {', '.join(bad)}"
                ))

        # R03 duplicate_threshold
        r = self._rule("duplicate_threshold")
        if r:
            dup_rate = df.duplicated().sum() / max(len(df), 1)
            if dup_rate > r["threshold"]:
                flags.append(self._make_flag(r, observed_value=round(dup_rate, 4)))

        # R04 id_columns_present
        r = self._rule("id_columns_present")
        if r:
            id_cols = col_types.get("id", [])
            if id_cols:
                flags.append(self._make_flag(
                    r, observed_value=id_cols,
                    flag_override=f"ID columns detected — risk of leakage if used as features: {', '.join(id_cols)}"
                ))

        # R05 min_sample_size
        r = self._rule("min_sample_size")
        if r and len(df) < r["threshold"]:
            flags.append(self._make_flag(r, observed_value=len(df)))

        # Macro variable detection
        macro_kw = {"gdp", "unemployment", "inflation", "interest", "cpi",
                    "macro", "economic", "hpi", "house_price", "sentiment"}
        macro_found = [c for c in df.columns if any(kw in c.lower() for kw in macro_kw)]

        # MACRO_MISSING — required by both SS1/23 P1.3 and IFRS 9 B5.5.49
        if not macro_found:
            flags.append({
                "rule_id": "MACRO_MISSING",
                "source": "SS1/23 | IFRS 9",
                "principle": "Principle 1.3 | B5.5.49",
                "stage": "data",
                "severity": "high",
                "flag": (
                    "No macroeconomic variables detected in the dataset. "
                    "SS1/23 Principle 1.3 requires models used in regulatory decisions "
                    "to incorporate forward-looking economic inputs where material to model outcomes. "
                    "IFRS 9 B5.5.49 additionally requires that ECL models incorporate "
                    "probability-weighted macroeconomic scenarios (e.g. GDP growth, "
                    "unemployment rate, interest rates, HPI) in an unbiased manner."
                ),
                "suggestion": (
                    "Add macroeconomic overlays (GDP growth, unemployment rate, HPI, interest rates) "
                    "to the feature set and apply at least three scenarios (base, upside, downside) "
                    "probability-weighted per IFRS 9 B5.5.49. "
                    "If macroeconomic inputs are not material for this portfolio, "
                    "document the justification formally in the model development log per SS1/23 P1.3."
                ),
                "observed_value": None,
            })

        # SS1_P3.5_TARGET_LEAKAGE
        if leakage_risk_cols:
            flags.append({
                "rule_id": "SS1_P3.5_TARGET_LEAKAGE",
                "source": "SS1/23",
                "principle": "Principle 3.5",
                "stage": "data",
                "severity": "high",
                "flag": (
                    f"Potential target leakage detected in features: {leakage_risk_cols}. "
                    "These features have correlation > 0.95 with the target variable. "
                    "Using them would cause artificially inflated performance metrics."
                ),
                "suggestion": (
                    "Remove or investigate these features before training. "
                    "Leakage is a critical model risk issue — SS1/23 P3.5 requires "
                    "documented justification for any retained high-correlation feature."
                ),
                "observed_value": leakage_risk_cols,
            })

        self._flags["data"].extend(flags)
        return flags

    # ── Feature Stage ────────────────────────────────────────────────────────

    def check_features(self, fe_plan: dict, all_columns: list | None = None) -> list[dict]:
        flags: list[dict] = []
        self._stages_checked.add("feature")
        self._flags["feature"].clear()

        # R06 high_correlation
        r = self._rule("high_correlation")
        if r:
            pairs = fe_plan.get("multicollinearity", {}).get("high_corr_pairs", [])
            bad = [p for p in pairs if abs(p.get("correlation", 0)) > r["threshold"]]
            if bad:
                labels = [
                    f"{p['feature_1']}/{p['feature_2']} ({p['correlation']:.2f})"
                    for p in bad
                ]
                flags.append(self._make_flag(
                    r, observed_value=labels,
                    flag_override=f"Highly correlated feature pairs (>{r['threshold']}): {'; '.join(labels)}"
                ))

        # R07 low_variance_features
        r = self._rule("low_variance_features")
        if r:
            lv = fe_plan.get("low_variance_cols", [])
            if lv:
                flags.append(self._make_flag(
                    r, observed_value=lv,
                    flag_override=f"Low-variance features detected: {', '.join(lv)}"
                ))

        # R08 low_iv_features
        r = self._rule("low_iv_features")
        if r:
            li = fe_plan.get("low_iv_cols", [])
            if li:
                flags.append(self._make_flag(
                    r, observed_value=li,
                    flag_override=f"Low information-value features (<{r['threshold']} IV): {', '.join(li)}"
                ))

        # IFRS9_5.5_DPD_MISSING — days-past-due feature required for IFRS 9 staging
        if all_columns is not None:
            dpd_kw = {"dpd", "days_past", "past_due", "overdue", "delinquent", "dq_"}
            dpd_found = [c for c in all_columns if any(kw in c.lower() for kw in dpd_kw)]
            if not dpd_found:
                flags.append({
                    "rule_id": "IFRS9_5.5_DPD_MISSING",
                    "source": "IFRS 9",
                    "principle": "Section 5.5",
                    "stage": "feature",
                    "severity": "high",
                    "flag": (
                        "No days-past-due (DPD) feature detected in the dataset. "
                        "IFRS 9 Section 5.5 requires DPD information to support "
                        "Stage 1/2/3 classification and SICR assessment."
                    ),
                    "suggestion": (
                        "Add a days-past-due column or equivalent delinquency indicator. "
                        "IFRS 9 staging logic relies on DPD as a primary criterion for "
                        "significant increase in credit risk (SICR) determination."
                    ),
                    "observed_value": None,
                })

        # SS1_P3.4_NO_DECISION_LOG — fires when FE steps were applied without a logged justification
        if fe_plan.get("applied_steps"):
            flags.append({
                "rule_id": "SS1_P3.4_NO_DECISION_LOG",
                "source": "SS1/23",
                "principle": "Principle 3.4",
                "stage": "feature",
                "severity": "medium",
                "flag": (
                    "Feature transforms applied automatically with no documented expert "
                    "justification. SS1/23 P3.4 requires adjustments to inputs to be "
                    "justified and retained in the model development artefacts."
                ),
                "suggestion": (
                    "Review and confirm each automated transform in the feature decision log. "
                    "Use the 'Download Feature Decision Log' button on Step 4 to export a "
                    "structured record and retain it as part of the model development artefacts."
                ),
                "observed_value": [s["step"] for s in fe_plan["applied_steps"]],
            })

        self._flags["feature"].extend(flags)
        return flags

    # ── Training Stage ───────────────────────────────────────────────────────

    def check_training(
        self,
        t_cfg: dict,
        training_info: dict | None = None,
        test_auc: float | None = None,
        imbalance_ratio: float | None = None,
        task_type: str = "binary",
    ) -> list[dict]:
        flags: list[dict] = []
        self._stages_checked.add("training")
        self._flags["training"].clear()
        ti = training_info or {}

        # R09 model_documented
        r = self._rule("model_documented")
        if r and not t_cfg.get("model_name"):
            flags.append(self._make_flag(r, observed_value=None))

        # R10 challenger_model_used
        r = self._rule("challenger_model_used")
        if r and not t_cfg.get("multiple_models_compared", False):
            flags.append(self._make_flag(r, observed_value=False))

        # NO_CV — fires when user didn't enable CV, or CV results absent from training_info
        # Merges R11 (cross_validation_used) and the prior SS1_P3.3_NO_CV inline check
        _cv_not_done = (
            not t_cfg.get("use_cv", False)
            or ("cv_scores" not in ti and "cv_best_score" not in ti)
        )
        if _cv_not_done:
            flags.append({
                "rule_id": "NO_CV",
                "source": "SS1/23",
                "principle": "Principle 3.3",
                "stage": "training",
                "severity": "high",
                "flag": (
                    "Cross-validation was not performed. "
                    "SS1/23 Principle 3.3 requires backward-looking stability testing "
                    "across multiple data samples — stratified K-Fold CV (k≥5) must be "
                    "run and fold-level metrics reported to demonstrate model stability."
                ),
                "suggestion": (
                    "Enable K-Fold cross-validation in the training step. "
                    "Report mean and standard deviation of ROC-AUC, recall, and PR-AUC "
                    "across folds in the validation report per SS1/23 Principle 3.3."
                ),
                "observed_value": None,
            })
        else:  # CV was done and results are present
            # SS1_P3.3_CV_STABILITY — high fold-to-fold variance
            std = ti.get("cv_std", 0.0)
            if std is not None and std > 0.05:
                flags.append({
                    "rule_id": "SS1_P3.3_CV_STABILITY",
                    "source": "SS1/23",
                    "principle": "Principle 3.3",
                    "stage": "training",
                    "severity": "medium",
                    "flag": (
                        f"Cross-validation score variance is high (std={std:.3f} across folds). "
                        "SS1/23 P3.3 requires model stability testing — high fold variance "
                        "indicates the model may be unstable across different data samples."
                    ),
                    "suggestion": (
                        "Investigate feature engineering or regularization to reduce variance. "
                        "Consider ensemble methods or simplifying the model."
                    ),
                    "observed_value": round(std, 4),
                })

            # SS1_P3.3_OVERFIT_GAP — CV mean vs test AUC gap
            cv_mean = ti.get("cv_mean")
            if cv_mean is not None and test_auc is not None:
                gap = abs(cv_mean - test_auc)
                if gap > 0.05:
                    flags.append({
                        "rule_id": "SS1_P3.3_OVERFIT_GAP",
                        "source": "SS1/23",
                        "principle": "Principle 3.3",
                        "stage": "training",
                        "severity": "medium",
                        "flag": (
                            f"CV mean AUC ({cv_mean:.3f}) differs from test AUC ({test_auc:.3f}) "
                            f"by {gap:.3f}. SS1/23 P3.3 requires performance stability — "
                            "a large gap suggests overfitting to the training distribution."
                        ),
                        "suggestion": (
                            "Check for data leakage, reduce model complexity, "
                            "or apply stronger regularization."
                        ),
                        "observed_value": round(gap, 4),
                    })

        # SS1_P3.2 — class imbalance mitigation check (binary only)
        if imbalance_ratio is not None and imbalance_ratio > 10 and task_type == "binary":
            class_weight_set = "class_weight" in (ti.get("best_params") or {})
            if not class_weight_set:
                flags.append({
                    "rule_id": "SS1_P3.2_IMBALANCE_UNMITIGATED",
                    "source": "SS1/23",
                    "principle": "Principle 3.2",
                    "stage": "training",
                    "severity": "high",
                    "flag": (
                        f"Class imbalance detected (ratio {imbalance_ratio:.1f}:1) with no "
                        "mitigation applied. Class weighting was not used during training. "
                        "SS1/23 P3.2 requires imbalance to be addressed and its impact "
                        "on recall and precision to be documented."
                    ),
                    "suggestion": (
                        "Enable class_weight='balanced' in the training step, or select a model with "
                        "class_weight support (Logistic Regression, Random Forest, Gradient Boosting). "
                        "Document the chosen approach and its impact on recall and PR-AUC."
                    ),
                    "observed_value": round(imbalance_ratio, 2),
                })
            else:
                flags.append({
                    "rule_id": "SS1_P3.2_IMBALANCE_MITIGATED",
                    "source": "SS1/23",
                    "principle": "Principle 3.2",
                    "stage": "training",
                    "severity": "low",
                    "flag": (
                        f"Class imbalance ({imbalance_ratio:.1f}:1) detected and mitigation "
                        "applied. SS1/23 P3.2 requires the chosen approach and its impact to be "
                        "documented in the model development log."
                    ),
                    "suggestion": (
                        "Document the mitigation method and quantify its impact on recall and "
                        "PR-AUC in the model card."
                    ),
                    "observed_value": round(imbalance_ratio, 2),
                })

        self._flags["training"].extend(flags)
        return flags

    # ── Evaluation Stage ─────────────────────────────────────────────────────

    def check_evaluation(
        self,
        metrics: dict,
        training_info: dict,
        threshold: float = 0.5,
        explainability_done: bool = False,
        heteroscedasticity_result: dict | None = None,
        pd_output_present: bool = True,
        staging_logic_present: bool = True,
        sicr_flagged: bool = True,
        ecl_estimated: bool = True,
        concentration_analysis: bool = True,
        exposure_reported: bool = True,
        past_due_breakdown: bool = True,
        shap_available: bool = False,
    ) -> list[dict]:
        flags: list[dict] = []
        self._stages_checked.add("evaluation")
        self._flags["evaluation"].clear()

        # R13 roc_auc_minimum
        r = self._rule("roc_auc_minimum")
        if r:
            val = metrics.get("roc_auc")
            if val is not None and val < r["threshold"]:
                flags.append(self._make_flag(r, observed_value=val))

        # R14 recall_minimum
        r = self._rule("recall_minimum")
        if r:
            val = metrics.get("recall")
            if val is not None and val < r["threshold"]:
                flags.append(self._make_flag(r, observed_value=val))

        # R15 precision_minimum
        r = self._rule("precision_minimum")
        if r:
            val = metrics.get("precision")
            if val is not None and val < r["threshold"]:
                flags.append(self._make_flag(r, observed_value=val))

        # R16 train_test_gap
        r = self._rule("train_test_gap")
        if r:
            cv = training_info.get("cv_mean")
            auc = metrics.get("roc_auc")
            if cv is not None and auc is not None:
                gap = abs(cv - auc)
                if gap > r["threshold"]:
                    flags.append(self._make_flag(
                        r, observed_value=round(gap, 4),
                        flag_override=(
                            f"Train/test AUC gap ({gap:.3f}) exceeds {r['threshold']} "
                            "— possible overfitting or data leakage"
                        )
                    ))

        # R17 explainability_performed — merged into NO_SHAP below (same condition, same framework)

        # R18 threshold_documented — flag whenever a non-default threshold is used
        r = self._rule("threshold_documented")
        if r and threshold != 0.5:
            flags.append(self._make_flag(
                r, observed_value=threshold,
                flag_override=(
                    f"Non-default decision threshold ({threshold}) requires "
                    "formal documentation and governance sign-off"
                )
            ))

        # R19 heteroscedasticity_flag
        r = self._rule("heteroscedasticity_flag")
        if r and heteroscedasticity_result and heteroscedasticity_result.get("risk_flag"):
            flags.append(self._make_flag(
                r, observed_value=heteroscedasticity_result["risk_flag"]
            ))

        # R20 pr_auc_minimum
        r = self._rule("pr_auc_minimum")
        if r:
            val = metrics.get("pr_auc")
            if val is not None and val < r["threshold"]:
                flags.append(self._make_flag(r, observed_value=val))

        # R21 pd_output_present (IFRS 9)
        r = self._rule("pd_output_present")
        if r and not pd_output_present:
            flags.append(self._make_flag(r, observed_value=False))

        # R22 staging_logic_present (IFRS 9)
        r = self._rule("staging_logic_present")
        if r and not staging_logic_present:
            flags.append(self._make_flag(r, observed_value=False))

        # R24 sicr_flagged (IFRS 9)
        r = self._rule("sicr_flagged")
        if r and not sicr_flagged:
            flags.append(self._make_flag(r, observed_value=False))

        # R25 ecl_estimated (IFRS 9)
        r = self._rule("ecl_estimated")
        if r and not ecl_estimated:
            flags.append(self._make_flag(r, observed_value=False))

        # R26 concentration_analysis (IFRS 7)
        r = self._rule("concentration_analysis")
        if r and not concentration_analysis:
            flags.append(self._make_flag(r, observed_value=False))

        # R27 exposure_reported (IFRS 7)
        r = self._rule("exposure_reported")
        if r and not exposure_reported:
            flags.append(self._make_flag(r, observed_value=False))

        # R28 past_due_breakdown (IFRS 7)
        r = self._rule("past_due_breakdown")
        if r and not past_due_breakdown:
            flags.append(self._make_flag(r, observed_value=False))

        # IFRS9_B5.5_NO_PRAUC — PR-AUC must be reported for imbalanced credit models
        if metrics.get("pr_auc") is None:
            flags.append({
                "rule_id": "IFRS9_B5.5_NO_PRAUC",
                "source": "IFRS 9",
                "principle": "Appendix B5.5",
                "stage": "evaluation",
                "severity": "medium",
                "flag": (
                    "Precision-Recall AUC (PR-AUC) was not reported. "
                    "IFRS 9 Appendix B5.5 guidance on ECL measurement requires "
                    "evaluation metrics that are robust to class imbalance — "
                    "PR-AUC is the standard complement to ROC-AUC for credit models."
                ),
                "suggestion": (
                    "Add PR-AUC to the evaluation step. "
                    "For imbalanced credit portfolios, PR-AUC is more informative "
                    "than ROC-AUC and should be included in model validation reports."
                ),
                "observed_value": None,
            })

        # SS1_P3.3_NO_SENSITIVITY — sensitivity analysis always required
        flags.append({
            "rule_id": "SS1_P3.3_NO_SENSITIVITY",
            "source": "SS1/23",
            "principle": "Principle 3.3",
            "stage": "evaluation",
            "severity": "high",
            "flag": (
                "No sensitivity analysis has been performed. "
                "SS1/23 Principle 3.3 requires backward-looking and forward-looking "
                "sensitivity testing — the effect of parameter perturbations on model "
                "outputs must be documented."
            ),
            "suggestion": (
                "Run a sensitivity analysis varying key model parameters (±10%, ±25%). "
                "Document how predictions change under adverse macro scenarios and "
                "include results in the model validation report."
            ),
            "observed_value": None,
        })

        # NO_SHAP — merges R17 (P4.2) and SS1_P3.5_NO_SHAP (P3.5): same condition, both SS1/23
        if not shap_available:
            flags.append({
                "rule_id": "NO_SHAP",
                "source": "SS1/23",
                "principle": "Principle 3.5 | 4.2",
                "stage": "evaluation",
                "severity": "high",
                "flag": (
                    "Model explainability analysis (SHAP) was not performed. "
                    "SS1/23 Principle 3.5 requires model inputs and their relative "
                    "contributions to be documented and explainable to non-technical "
                    "stakeholders and regulators. "
                    "SS1/23 Principle 4.2 additionally requires that model outputs "
                    "be explainable using model-agnostic interpretability techniques "
                    "(e.g. SHAP, LIME) to support human oversight and credit decisions."
                ),
                "suggestion": (
                    "Run SHAP value analysis on Step 7 (Explainability). "
                    "Produce a SHAP summary plot and document the top contributing "
                    "features in the model card per SS1/23 Principles 3.5 and 4.2."
                ),
                "observed_value": False,
            })

        self._flags["evaluation"].extend(flags)
        return flags

    # ── Reporting ────────────────────────────────────────────────────────────

    def get_full_report(self) -> dict:
        all_flags: list[dict] = []
        for stage_flags in self._flags.values():
            all_flags.extend(stage_flags)

        _sev = {"high": 0, "medium": 1, "low": 2}
        _stg = {"data": 0, "feature": 1, "training": 2, "evaluation": 3}
        sorted_flags = sorted(
            all_flags,
            key=lambda f: (_sev.get(f["severity"], 9), _stg.get(f["stage"], 9))
        )

        high = sum(1 for f in all_flags if f["severity"] == "high")
        medium = sum(1 for f in all_flags if f["severity"] == "medium")
        low = sum(1 for f in all_flags if f["severity"] == "low")

        total_rules = len(self.rules)
        rules_flagged = len(all_flags)
        rules_passed = total_rules - rules_flagged
        compliance_score = round(max(rules_passed / total_rules * 100, 0), 1)

        if high > 0:
            overall_status = "FAIL"
        elif medium > 0:
            overall_status = "WARN"
        else:
            overall_status = "PASS"

        flags_by_source: dict[str, list] = {}
        for f in all_flags:
            flags_by_source.setdefault(f["source"], []).append(f)

        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "rules_source": "rag_store/rules.json",
                "stages_checked": sorted(self._stages_checked),
                "total_rules": total_rules,
                "rules_passed": rules_passed,
                "rules_flagged": rules_flagged,
                "compliance_score": compliance_score,
            },
            "summary": {
                "high_severity": high,
                "medium_severity": medium,
                "low_severity": low,
                "overall_status": overall_status,
            },
            "flags_by_stage": {k: list(v) for k, v in self._flags.items()},
            "flags_by_source": flags_by_source,
            "all_flags": sorted_flags,
            "model_tier": getattr(self, "_tier_result", None),
        }

    def save_report(self, path: str = "agent2_report.json") -> None:
        report = self.get_full_report()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    def print_summary(self) -> None:
        report = self.get_full_report()
        meta = report["metadata"]
        summary = report["summary"]

        _SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        _STATUS_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}

        W = 65
        print("\n" + "=" * W)
        print("  AGENT 2 — REGULATORY COMPLIANCE REPORT")
        print("=" * W)
        print(f"  Generated : {meta['generated_at']}")
        print(f"  Stages    : {', '.join(meta['stages_checked'])}")
        print(f"  Rules     : {meta['total_rules']} total  |  "
              f"{meta['rules_passed']} passed  |  {meta['rules_flagged']} flagged")
        print(f"  Score     : {meta['compliance_score']}%")
        status = summary["overall_status"]
        print(f"  Status    : {_STATUS_ICON.get(status, '')} {status}")
        print("=" * W)
        print(f"\n  🔴 High severity   : {summary['high_severity']}")
        print(f"  🟡 Medium severity : {summary['medium_severity']}")
        print(f"  🟢 Low severity    : {summary['low_severity']}")

        for stage in ("data", "feature", "training", "evaluation"):
            stage_flags = report["flags_by_stage"].get(stage, [])
            if not stage_flags:
                continue
            print(f"\n  {'─' * (W - 2)}")
            print(f"  STAGE: {stage.upper()}  ({len(stage_flags)} flag(s))")
            print(f"  {'─' * (W - 2)}")
            for flag in stage_flags:
                icon = _SEV_ICON.get(flag["severity"], "⚪")
                print(f"  {icon} [{flag['rule_id']}] {flag['flag']}")
                if flag.get("observed_value") is not None:
                    print(f"       Observed : {flag['observed_value']}")
                print(f"       Source   : {flag['source']} — Principle {flag['principle']}")
                print(f"       Suggest  : {flag['suggestion'][:120]}...")

        print("\n" + "=" * W)

    # ── Agent 1 rule format support ──────────────────────────────────────────

    def _resolve_field(self, field_hint: str, context_dict: dict) -> Any:
        """Dot-notation field resolver: 'metrics.roc_auc' → context_dict['metrics']['roc_auc']."""
        if not field_hint:
            return None
        if field_hint in context_dict:
            return context_dict[field_hint]
        parts = field_hint.split(".")
        obj: Any = context_dict
        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return None
        return obj

    def _apply_operator(self, value: Any, operator: str, threshold: Any) -> bool:
        """Return True if the check PASSES (i.e., no flag needed)."""
        try:
            if operator in (">=", "gte"):
                return float(value) >= float(threshold)
            if operator in ("<=", "lte"):
                return float(value) <= float(threshold)
            if operator in (">", "gt"):
                return float(value) > float(threshold)
            if operator in ("<", "lt"):
                return float(value) < float(threshold)
            if operator in ("==", "eq"):
                return value == threshold
            if operator in ("!=", "ne"):
                return value != threshold
            if operator == "is_true":
                return bool(value)
            if operator == "is_false":
                return not bool(value)
            if operator == "is_present":
                return value is not None
        except (TypeError, ValueError):
            pass
        return True  # unknown operator → don't flag

    def _make_flag_from_agent1_rule(self, rule: dict, observed_value: Any = None) -> dict:
        return {
            "rule_id": rule.get("rule_id", rule.get("id", "?")),
            "source": rule.get("regulation", rule.get("source", "?")),
            "principle": rule.get("section", rule.get("principle", "?")),
            "stage": rule.get("stage", "?"),
            "severity": rule.get("severity", "medium"),
            "flag": rule.get("statement", rule.get("flag", "Compliance check failed")),
            "suggestion": rule.get("action", rule.get("suggestion", "Review the relevant guidance.")),
            "observed_value": observed_value,
            "not_verifiable": False,
        }

    def check_rules_from_agent1(self, stage: str, context_dict: dict) -> list[dict]:
        """
        Dynamically evaluate rules that carry Agent 1's logic format:
          checkable_against_data=True + logic: {field_hint, operator, threshold, unit, action}
        Extends self._flags[stage]; call AFTER the corresponding check_* method so that
        check_*'s .clear() doesn't wipe these results.
        """
        self._stages_checked.add(stage)
        self._flags.setdefault(stage, [])
        new_flags: list[dict] = []
        not_verifiable_count = 0

        for rule in self.rules:
            if rule.get("stage") != stage:
                continue
            if not rule.get("checkable_against_data", False):
                continue
            logic = rule.get("logic")
            if not logic or not isinstance(logic, dict):
                continue

            field_hint = logic.get("field_hint", "")
            if not field_hint:
                continue

            operator = logic.get("operator", "")
            threshold = logic.get("threshold")
            value = self._resolve_field(field_hint, context_dict)

            if value is None:
                if not_verifiable_count >= 3:
                    continue
                not_verifiable_count += 1
                flag: dict = {
                    "rule_id": rule.get("rule_id", rule.get("id", "?")),
                    "source": rule.get("regulation", rule.get("source", "?")),
                    "principle": rule.get("section", rule.get("principle", "?")),
                    "stage": stage,
                    "severity": "medium",
                    "flag": (
                        f"Not Verifiable with Current Dataset — "
                        f"{rule.get('statement', rule.get('flag', ''))[:80]}"
                    ),
                    "suggestion": rule.get("action", rule.get("suggestion", "Verify manually.")),
                    "observed_value": None,
                    "not_verifiable": True,
                }
                new_flags.append(flag)
            elif not self._apply_operator(value, operator, threshold):
                new_flags.append(self._make_flag_from_agent1_rule(rule, value))

        self._flags[stage].extend(new_flags)
        return new_flags

    def get_stage_summary(self, stage: str) -> dict:
        """Return {total_flags, high, medium, low, status: PASS/WARN/FAIL, flags: [...]}."""
        flags = self._flags.get(stage, [])
        high = sum(1 for f in flags if f.get("severity") == "high")
        medium = sum(1 for f in flags if f.get("severity") == "medium")
        low = sum(1 for f in flags if f.get("severity") == "low")
        if high > 0:
            status = "FAIL"
        elif medium > 0:
            status = "WARN"
        else:
            status = "PASS"
        return {
            "total_flags": len(flags),
            "high": high,
            "medium": medium,
            "low": low,
            "status": status,
            "flags": flags,
        }

    @property
    def is_fully_checked(self) -> bool:
        """True once all four pipeline stages have been checked at least once."""
        return len(self._stages_checked) >= 4

    # ── SS1/23 Model Risk Tiering ────────────────────────────────────────────

    def tier_model(
        self,
        training_config: dict,
        metrics: dict,
        fe_summary: dict | None = None,
    ) -> dict:
        """
        Assigns SS1/23 model risk tier (1=High, 2=Medium, 3=Low) per Principle 1.3.

        Principle 1.3b: Model materiality considers:
          - quantitative size-based measures (number of customers/samples)
          - qualitative factors: importance to business decisions, impact on solvency

        Principle 1.3c: Model complexity considers:
          - nature and quality of input data
          - choice of methodology (including assumptions)
          - requirements and integrity of implementation
          - frequency/extensiveness of use
          - interpretability and explainability (1.3c.ii)
          - potential for designer or data bias (1.3c.ii)
        """
        score = 0
        reasons: list[str] = []

        # ── COMPLEXITY: methodology choice (SS1/23 Principle 1.3c) ──
        model_name = training_config.get("model_name", "")
        if model_name in ["XGBoost", "LightGBM", "Neural Network"]:
            score += 3
            reasons.append(
                f"{model_name} — high complexity, difficult to explain in "
                f"non-technical terms (SS1/23 §1.3c)"
            )
        elif model_name in ["Random Forest", "Gradient Boosting"]:
            score += 2
            reasons.append(f"{model_name} — moderate complexity ensemble model (SS1/23 §1.3c)")
        elif model_name in ["Logistic Regression", "Linear Regression", "Ridge"]:
            score += 1
            reasons.append(f"{model_name} — low complexity, highly interpretable (SS1/23 §1.3c)")

        # ── MATERIALITY: dataset size (SS1/23 Principle 1.3b.i) ──
        n_samples = training_config.get("n_samples", 0)
        if n_samples > 10000:
            score += 3
            reasons.append(
                f"Large portfolio: {n_samples:,} samples — high materiality (SS1/23 §1.3b.i)"
            )
        elif n_samples > 1000:
            score += 2
            reasons.append(
                f"Medium portfolio: {n_samples:,} samples — moderate materiality (SS1/23 §1.3b.i)"
            )
        elif n_samples > 0:
            score += 1
            reasons.append(
                f"Small portfolio: {n_samples:,} samples — lower materiality (SS1/23 §1.3b.i)"
            )

        # ── DATA QUALITY RISK: class imbalance (SS1/23 Principle 1.3c) ──
        imbalance = training_config.get("class_imbalance_ratio", 1.0)
        if imbalance > 5:
            score += 2
            reasons.append(
                f"Severe class imbalance ({imbalance:.1f}x) — higher data uncertainty (SS1/23 §1.3c)"
            )
        elif imbalance > 2:
            score += 1
            reasons.append(
                f"Moderate class imbalance ({imbalance:.1f}x) — elevated data risk (SS1/23 §1.3c)"
            )

        # ── PERFORMANCE RISK (SS1/23 Principle 1.3b.ii — impact on solvency) ──
        roc_auc = metrics.get("roc_auc")
        recall = metrics.get("recall")
        if roc_auc is not None:
            if roc_auc < 0.70:
                score += 3
                reasons.append(
                    f"Poor discriminative ability (ROC-AUC={roc_auc:.3f}) — "
                    f"high risk of adverse business decisions (SS1/23 §1.3b.ii)"
                )
            elif roc_auc < 0.80:
                score += 1
                reasons.append(
                    f"Moderate discriminative ability (ROC-AUC={roc_auc:.3f}) (SS1/23 §1.3b.ii)"
                )
        if recall is not None and recall < 0.60:
            score += 2
            reasons.append(
                f"Low recall ({recall:.3f}) — high rate of missed defaults, "
                f"material impact on solvency (SS1/23 §1.3b.ii)"
            )

        # ── EXPLAINABILITY (SS1/23 Principle 1.3c.ii) ──
        if not training_config.get("explainability_done", False):
            score += 2
            reasons.append(
                "No explainability analysis performed — model interpretability "
                "not demonstrated (SS1/23 §1.3c.ii)"
            )

        # ── GOVERNANCE GAPS (SS1/23 Principle 1.3c) ──
        if not training_config.get("use_cv", False):
            score += 1
            reasons.append(
                "No cross-validation — model stability not verified (SS1/23 §1.3c)"
            )
        if not training_config.get("multiple_models_compared", False):
            score += 1
            reasons.append(
                "No challenger model comparison — operating boundaries not "
                "established (SS1/23 §1.3c)"
            )

        # ── FEATURE COMPLEXITY (SS1/23 Principle 1.3c — nature and quality of input data) ──
        if fe_summary and fe_summary.get("features_added", 0) > 10:
            score += 1
            reasons.append(
                f"High feature engineering complexity "
                f"({fe_summary['features_added']} features added) — "
                f"increased data interconnectedness (SS1/23 §1.3c)"
            )

        # ── TIER ASSIGNMENT (SS1/23 Principle 1.3a) ──
        if score >= 10:
            tier = 1
            tier_label = "TIER 1 — HIGH RISK"
            color = "red"
            requirements = [
                "Full independent validation required before deployment (SS1/23 Principle 4.1)",
                "Monthly model performance monitoring mandatory (SS1/23 Principle 4.4)",
                "Board-level model risk reporting required (SS1/23 Principle 2.1d)",
                "Model inventory entry with all sub-fields mandatory (SS1/23 Principle 1.2)",
                "SMF accountability must be formally assigned (SS1/23 Principle 2.2)",
                "Post-model adjustments must be independently reviewed (SS1/23 Principle 5.1)",
                "Periodic revalidation at highest frequency (SS1/23 Principle 4.5)",
            ]
        elif score >= 6:
            tier = 2
            tier_label = "TIER 2 — MEDIUM RISK"
            color = "amber"
            requirements = [
                "Independent validation required (SS1/23 Principle 4.1)",
                "Quarterly model performance monitoring (SS1/23 Principle 4.4)",
                "Regular reporting to senior management (SS1/23 Principle 2.1d)",
                "Model inventory entry required (SS1/23 Principle 1.2)",
                "Periodic revalidation at standard frequency (SS1/23 Principle 4.5)",
            ]
        else:
            tier = 3
            tier_label = "TIER 3 — LOW RISK"
            color = "green"
            requirements = [
                "Light-touch validation acceptable (SS1/23 Principle 4.1)",
                "Annual model performance monitoring sufficient (SS1/23 Principle 4.4)",
                "Basic model inventory entry required (SS1/23 Principle 1.2)",
                "Revalidation at lower frequency (SS1/23 Principle 4.5)",
            ]

        self._tier_result = {
            "tier": tier,
            "tier_label": tier_label,
            "score": score,
            "color": color,
            "reasons": reasons,
            "requirements": requirements,
            "principle": "SS1/23 Principle 1.3 — Model Identification and Risk Classification",
            "sub_scores": {
                "complexity": "methodology choice",
                "materiality": "portfolio size",
                "data_quality": "class imbalance",
                "performance_risk": "ROC-AUC and recall",
                "explainability": "SHAP/feature importance",
                "governance": "CV and challenger model",
            },
        }
        return self._tier_result
