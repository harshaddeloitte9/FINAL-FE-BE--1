import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app


def test_stage3_payload_contains_structured_sections():
    client = TestClient(app)
    response = client.post(
        "/validation/stage3/run",
        data={
            "intake_json": json.dumps({
                "algorithm": "Logistic Regression",
                "methodology": "Logistic Regression",
                "calibration_method": "Platt scaling",
                "default_definition": "Default indicator",
                "independence_confirmed": True,
                "assumptions": ["linearity", "independence"],
                "limitations": ["limited sample"],
            })
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert "featureRelevance" in body
    assert "methodologyReview" in body
    assert "modelAssumptions" in body
    assert "documentationChecklist" in body
    assert "regulatoryAlignment" in body

    methodology_titles = {item["title"] for item in body["methodologyReview"]}
    assumption_titles = {item["title"] for item in body["modelAssumptions"]}
    documentation_titles = {item["title"] for item in body["documentationChecklist"]}

    assert "Model algorithm" in methodology_titles
    assert "Cross-validation strategy" in methodology_titles
    assert "Calibration method" in methodology_titles
    assert "Linearity" in assumption_titles
    assert "Independence" in assumption_titles
    assert "Default definition consistency" in assumption_titles
    assert "Model Development Document" in documentation_titles
    assert "Data Lineage" in documentation_titles
    assert "Independent Code Review" in documentation_titles
    assert "Sensitivity Analysis" in documentation_titles
    assert "Reproducibility Package" in documentation_titles
    assert "Limitations Statement" in documentation_titles

    regulatory = body["regulatoryAlignment"]
    assert "verdict" in regulatory
    assert "counts" in regulatory
    assert "remediation_summary" in regulatory
    assert "regulatory_references" in regulatory
