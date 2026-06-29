import pandas as pd

from feature_engineering import (
    analyze_for_feature_engineering,
    apply_feature_engineering,
    resolve_ead_configuration,
)
from utils import detect_column_types


def test_apply_feature_engineering_accepts_reference_style_call():
    X = pd.DataFrame(
        {
            "loan_amount": [1000, 2000, 3000, 4000, 5000, 6000],
            "credit_score": [600, 620, 650, 680, 700, 720],
            "segment": ["A", "A", "B", "B", "C", "C"],
            "target": [0, 0, 0, 1, 1, 1],
        }
    )
    col_types = detect_column_types(X)
    col_types["numeric"] = [c for c in col_types["numeric"] if c != "target"]
    col_types["categorical"] = [c for c in col_types["categorical"] if c != "target"]

    plan = analyze_for_feature_engineering(X, X["target"], col_types, "binary")

    engineered_a, summary_a = apply_feature_engineering(X, plan)
    engineered_b, summary_b = apply_feature_engineering(X, X["target"], plan)

    assert engineered_a.columns.tolist() == engineered_b.columns.tolist()
    assert summary_a["features_added"] == summary_b["features_added"]
    assert summary_a["features_removed"] == summary_b["features_removed"]
    assert summary_a["final_shape"] == summary_b["final_shape"]


def test_resolve_ead_configuration_uses_outstanding_balance_when_available():
    df = pd.DataFrame(
        {
            "outstanding_balance": [1000, 1500, 2000],
            "loan_amount": [1000, 1500, 2000],
            "interest_rate": [5.0, 5.0, 5.0],
            "years_elapsed": [1.0, 2.0, 3.0],
            "term_years": [5.0, 5.0, 5.0],
        }
    )

    result = resolve_ead_configuration(df)

    assert result["mode"] == "outstanding_balance"
    assert result["source_col"] == "outstanding_balance"
    assert result["method"].startswith("Outstanding balance column")
    assert result["series"] is not None
