import os
import json
from pathlib import Path
import persistence

APP = Path(__file__).resolve().parent

def test_metadata_persistence_and_report_generation(tmp_path, monkeypatch):
    # Use a fresh in-memory store to avoid interfering with existing inventory
    store = {"development": [], "validation": [], "models": []}

    unique_name = f"TEST_MODEL_FOR_METADATA_{os.urandom(4).hex()}"

    # Build a full_payload that mimics the real training artifact
    full_payload = {
        "model_name": unique_name,
        "training_config": {
            "random_seed": 42,
            "use_cv": True,
            "cv_folds": 5,
            "use_hyperopt": False,
        },
        "training_info": {
            "preprocessing": "standard",
            "class_distribution": {"0": 0.8, "1": 0.2},
        },
        "encoding": {"cat1": "onehot"},
        "scaling": {"num1": "standard"},
        "feature_selection": {"low_iv_cols": ["a", "b"]},
        "feature_importances": [{"Feature": "f1", "Importance": 0.5}],
        "top_model_drivers": ["f1"],
        "evaluation_metrics": {"roc_auc": 0.92, "accuracy": 0.85},
        "split_stats": {"train": 80, "val": 10, "test": 10},
        "real_feature_names": ["f1", "f2", "f3"],
        "preprocessing_summary": {"imputers": ["mean"]},
        "feature_engineering_summary": {"added": ["f_new"]},
    }

    # Log a training artifact (this writes to app_data/dev_pipeline_log.csv and artifact JSON)
    run_id = persistence.log_event(persistence.DEV_PIPELINE_LOG, stage="training", payload={"model_name": unique_name}, full_payload=full_payload)
    assert run_id

    # Prepare dataset payload
    dataset_payload = {
        "file_name": "uploaded_dataset.csv",
        "record_count": 100,
        "column_count": 3,
        "numeric_column_count": 2,
        "categorical_column_count": 1,
        "missing_value_count": 0,
        "missing_value_pct": 0.0,
        "duplicate_record_count": 0,
        "target_variable": "target",
        "class_distribution": {"0": 80, "1": 20},
    }

    # Call registration which should persist metadata and update artifact
    res = persistence.register_development_model(store=store, business_model_name=unique_name, estimator_name="est", intake_payload=full_payload, dataset_payload=dataset_payload, user="tester")

    assert isinstance(res, dict)
    model_id = res.get("model_id")
    assert model_id and model_id.startswith("MOD-")

    # Ensure development inventory contains the entry with persisted fields
    entry = next((m for m in store.get("development", []) if m.get("model_id") == model_id), None)
    assert entry is not None
    # Check persisted keys
    assert entry.get("training_config") == full_payload.get("training_config")
    assert entry.get("encoding") == full_payload.get("encoding")
    assert entry.get("scaling") == full_payload.get("scaling")
    assert entry.get("feature_selection") == full_payload.get("feature_selection")
    assert entry.get("evaluation_metrics") == full_payload.get("evaluation_metrics")
    assert entry.get("split_stats") == full_payload.get("split_stats")
    # New keys: dataset/QA and FE/preprocessing
    assert entry.get("numeric_column_count") == dataset_payload.get("numeric_column_count")
    assert entry.get("categorical_column_count") == dataset_payload.get("categorical_column_count")
    assert entry.get("missing_value_count") == dataset_payload.get("missing_value_count")
    assert entry.get("missing_value_pct") == dataset_payload.get("missing_value_pct")
    assert entry.get("duplicate_record_count") == dataset_payload.get("duplicate_record_count")
    assert entry.get("class_distribution") == dataset_payload.get("class_distribution") or full_payload.get("training_info").get("class_distribution")
    assert entry.get("preprocessing_summary") == full_payload.get("preprocessing_summary")
    assert entry.get("feature_engineering_summary") == full_payload.get("feature_engineering_summary")

    # The training artifact remains immutable; registration is logged as its
    # own event and the inventory entry carries the model_id/documentation_path.
    rows = persistence.read_log(persistence.DEV_PIPELINE_LOG)
    matching = [r for r in rows if r.get("summary") and isinstance(r.get("summary"), dict) and r.get("summary").get("model_name") == unique_name]
    assert matching, "training log entry not found"
    training_row = matching[-1]
    art_path = training_row.get("artifact_path")
    assert art_path
    candidate = Path(persistence.BACKEND_DIR) / art_path
    assert candidate.exists()
    data = json.loads(candidate.read_text(encoding="utf-8"))
    assert "model_id" not in data
    assert "documentation_path" not in data

    registration_rows = [
        r for r in rows
        if r.get("stage") == "registration"
        and r.get("summary")
        and isinstance(r.get("summary"), dict)
        and r["summary"].get("training_run_id") == training_row.get("run_id")
    ]
    assert registration_rows, "registration event not found"
    reg_summary = registration_rows[-1]["summary"]
    assert reg_summary.get("registered_model_id") == model_id
    assert reg_summary.get("training_artifact_sha256") == training_row["summary"].get("artifact_sha256")

    # The inventory entry and generated PDF should reflect the registered model,
    # but the original training artifact itself should not be rewritten.
    entry = next((m for m in store.get("development", []) if m.get("model_id") == model_id), None)
    assert entry is not None
    assert entry.get("documentation_path")
    pdf_path = persistence.BACKEND_DIR / entry["documentation_path"]
    assert pdf_path.exists()
    raw = pdf_path.read_bytes()
    assert model_id.encode("utf-8") in raw
    assert b"roc_auc" in raw or b"0.92" in raw
    assert b"Split Stats" in raw or b"train" in raw
    assert b"Class Distribution" in raw or b"80" in raw
