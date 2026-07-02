from io import BytesIO

from fastapi.testclient import TestClient

from main import app


def test_feature_engineering_endpoint_returns_engineered_dataset_csv_and_preview():
    client = TestClient(app)
    csv_bytes = BytesIO(
        b"loan_amount,interest_rate,years_elapsed,term,default\n"
        b"1000,8,1,12,0\n"
        b"2000,10,2,24,1\n"
        b"3000,12,3,36,0\n"
        b"4000,9,4,48,1\n"
    )

    response = client.post(
        "/data/feature-engineering",
        files={"file": ("sample.csv", csv_bytes, "text/csv")},
        data={"target_col": "default"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert "x_engineered_preview" in payload
    assert isinstance(payload["x_engineered_preview"], list)
    assert payload["x_engineered_preview"]
    assert "x_engineered_csv" in payload
    assert isinstance(payload["x_engineered_csv"], str)
    assert payload["x_engineered_csv"].startswith("")
