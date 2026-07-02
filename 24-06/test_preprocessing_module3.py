from fastapi.testclient import TestClient

from main import app


def test_preprocess_endpoint_drops_ecl_only_columns_and_returns_report():
    csv_text = """id,age,income,origpd,dpd,default
1,25,1000,0,0,0
1,25,1000,0,0,0
2,30,2000,1,60,1
3,40,3000,0,30,0
"""

    with TestClient(app) as client:
        response = client.post(
            "/data/preprocess",
            data={"target_col": "default", "csv_text": csv_text, "test_size": 0.2, "val_size": 0.2, "random_seed": 7},
        )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["target_col"] == "default"
    assert "origpd" not in payload["feature_names"]
    assert "dpd" not in payload["feature_names"]
    assert payload["duplicates_removed"] == 1
    assert payload["ecl_only_cols_dropped"] == ["origpd", "dpd"]
    assert payload["split_config"] == {"test_size": 0.2, "val_size": 0.2, "random_seed": 7}
    assert payload["summary_metrics"]["features_basic"] == 2
    assert payload["summary_metrics"]["numeric_columns"] == 2
    assert payload["summary_metrics"]["categorical_columns"] == 0
    assert payload["class_distribution_chart"]
    assert payload["target_preview"]
    assert payload["processed_dataset_csv"].startswith("")
    assert payload["preprocessing_report"].get("decisions")
