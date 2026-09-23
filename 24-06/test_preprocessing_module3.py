import json

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


def test_train_endpoint_accepts_data_preparation_preprocessing_contract():
    csv_text = """employment_length,loan_amount,default
12,25000,0
24,48000,1
,42000,0
18,30000,1
36,62000,0
,54000,1
30,51000,0
42,65000,1
"""

    with TestClient(app) as client:
        preprocess_response = client.post(
            "/data/preprocess",
            data={"target_col": "default", "csv_text": csv_text, "test_size": 0.25, "val_size": 0.25, "random_seed": 7},
        )
        assert preprocess_response.status_code == 200, preprocess_response.text
        preprocess_payload = preprocess_response.json()

        contract = {
            "source": "data_preparation",
            "applied_treatment_map": preprocess_payload.get("applied_treatment_map", {}),
            "dropped_columns": preprocess_payload.get("dropped_columns", []),
            "applied_transform_choices": preprocess_payload.get("applied_transform_choices", {}),
            "strategy_override": preprocess_payload.get("imputation_strategy", {}).get("method"),
        }

        train_response = client.post(
            "/models/train",
            data={
                "target_col": "default",
                "model_name": "Contract Test Model",
                "estimator_name": "Logistic Regression",
                "csv_text": csv_text,
                "test_size": 0.25,
                "val_size": 0.25,
                "random_seed": 7,
                "preprocessing_contract": json.dumps(contract),
            },
        )

    assert train_response.status_code == 200, train_response.text
    payload = train_response.json()
    assert payload["preprocessing_contract"]["source"] == "data_preparation"
    assert payload["preprocessing_contract"]["treatment_overrides"]
    assert payload["training_info"]["preprocessing_contract_used"]["source"] == "data_preparation"
    assert "processed_dataset_csv" not in payload


def test_train_endpoint_without_preprocessing_contract_still_works():
    csv_text = """employment_length,loan_amount,default
12,25000,0
24,48000,1
18,42000,0
36,30000,1
30,51000,0
42,65000,1
48,76000,0
22,39000,1
"""

    with TestClient(app) as client:
        response = client.post(
            "/models/train",
            data={
                "target_col": "default",
                "model_name": "Fallback Model",
                "estimator_name": "Logistic Regression",
                "csv_text": csv_text,
                "test_size": 0.25,
                "val_size": 0.25,
                "random_seed": 7,
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model_name"] == "Fallback Model"
    assert payload["training_info"]["preprocessing_contract_used"]["source"] == "fallback"
