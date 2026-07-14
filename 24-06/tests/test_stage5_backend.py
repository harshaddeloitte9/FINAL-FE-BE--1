import json

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_validation_performance_endpoint_returns_stage5_payload():
    csv_content = """default,score,feature
1,0.85,1
0,0.15,0
1,0.8,1
0,0.1,0
1,0.75,1
0,0.2,0
1,0.9,1
0,0.12,0
"""

    intake_json = json.dumps({
        "stated_auc": 0.82,
        "stated_recall": 0.70,
        "stated_gini": 0.60,
        "stated_brier": 0.12,
    })

    response = client.post(
        "/validation/performance",
        data={
            "model_name": "LogisticRegression",
            "target_col": "default",
            "benchmark_model": "Logistic Regression (Industry Standard)",
            "intake_json": intake_json,
        },
        files={"file": ("stage5.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["stage"] == "performance"
    assert payload["report"]["metrics"]["roc_auc"] >= 0
    assert payload["report"]["roc_curve"]["points"]
    assert payload["report"]["pr_curve"]["points"]
    assert payload["report"]["confusion_matrix"]["matrix"]
    assert payload["report"]["score_distribution"]["bins"]
    assert payload["report"]["calibration_chart"]["points"]
    assert payload["report"]["train_test_auc_gap"]["gap"] is not None
    assert payload["report"]["compliance_findings"]
    assert payload["report"]["benchmark"]["model_name"]
