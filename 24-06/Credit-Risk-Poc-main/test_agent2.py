"""
test_agent2.py
Standalone test for Agent 2 — Regulatory Compliance Checker.
Runs all four check stages with mock data and prints the full report.

Usage:
    python test_agent2.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

# utils.py has a top-level 'import streamlit' — suppress the runtime warning
# that fires in non-Streamlit contexts (the functions we use don't call st.*).
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")

from utils import generate_synthetic_credit_dataset, detect_column_types
from agent2 import Agent2

# ── 1. Generate synthetic dataset ────────────────────────────────────────────
print("Generating synthetic credit dataset (n=2000)...")
df = generate_synthetic_credit_dataset(n_samples=2000)
print(f"  Shape    : {df.shape}")

# ── 2. Detect column types and set target ─────────────────────────────────────
col_types = detect_column_types(df)
target_col = "default"
print(f"  Col types: { {k: len(v) for k, v in col_types.items()} }")

# ── 3. Initialise Agent2 ──────────────────────────────────────────────────────
agent = Agent2("rag_store/rules.json")
print(f"  Rules loaded: {len(agent.rules)}\n")

# ── 4. check_data ─────────────────────────────────────────────────────────────
print("Running check_data ...")
agent.check_data(df, col_types)

# ── 5. check_features ─────────────────────────────────────────────────────────
print("Running check_features ...")
fe_plan = {
    "multicollinearity": {
        "high_corr_pairs": [
            {
                "feature_1": "loan_amount",
                "feature_2": "loan_to_income_ratio",
                "correlation": 0.93,
            }
        ]
    },
    "low_variance_cols": ["has_dependents"],
    "low_iv_cols": ["num_credit_lines", "has_mortgage"],
    "woe_maps": {},
    "woe_cols": [],
}
agent.check_features(fe_plan)

# ── 6. check_training ─────────────────────────────────────────────────────────
print("Running check_training ...")
training_config = {
    "model_name": "XGBoost",
    "use_cv": False,
    "use_smote": True,
    "use_hyperopt": False,
    "multiple_models_compared": False,
    "class_imbalance_ratio": 3.5,
}
agent.check_training(training_config)

# ── 7. check_evaluation ───────────────────────────────────────────────────────
print("Running check_evaluation ...")
metrics = {"roc_auc": 0.65, "recall": 0.55, "precision": 0.38, "pr_auc": 0.25}
training_info = {"cv_mean": 0.78}
heteroscedasticity_result = {"risk_flag": "Potential heteroscedasticity"}

agent.check_evaluation(
    metrics=metrics,
    training_info=training_info,
    threshold=0.4,
    explainability_done=False,
    heteroscedasticity_result=heteroscedasticity_result,
    pd_output_present=False,
    staging_logic_present=False,
    sicr_flagged=False,
    ecl_estimated=False,
    concentration_analysis=False,
    exposure_reported=False,
    past_due_breakdown=False,
)

# ── 8. Print summary ──────────────────────────────────────────────────────────
agent.print_summary()

# ── 9. Save report ────────────────────────────────────────────────────────────
agent.save_report("agent2_report.json")
print("\nDone. Report saved to agent2_report.json")
