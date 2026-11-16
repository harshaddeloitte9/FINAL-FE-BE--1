from fastapi.testclient import TestClient
import json
from pathlib import Path
from main import app

client = TestClient(app)

data = {
    "target_col": "default",
    "model_name": "DEV_FINAL_VERIFY_002",
    "estimator_name": "Logistic Regression",
    "model_owner": "tester",
    "business_unit": "test_unit",
    "model_purpose": "verification run",
    "model_version": "0.1",
    "model_type": "classification",
    "development_date": "2026-08-13",
    "status": "In Development",
    "random_seed": "42",
    "use_cv": "false",
    "cv_folds": "3",
    "use_hyperopt": "false",
    "synthetic_samples": "1500",
}

resp = client.post("/models/train", data=data)

print("status", resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.content[:200])

from persistence import APP_DATA_DIR, get_model_inventory_path, read_log
inv_path = APP_DATA_DIR / 'model_inventory.json'
print('\nInventory exists:', inv_path.exists())
if inv_path.exists():
    inv = json.loads(inv_path.read_text(encoding='utf-8'))
    devs = inv.get('development', [])
    print('Development entries:', len(devs))
    entry = next((d for d in devs if d.get('model_name') == 'DEV_FINAL_VERIFY_002'), None)
    if entry:
        print('\nFound entry:')
        print(json.dumps(entry, indent=2, default=str))
        doc = entry.get('documentation_path')
        print('doc:', doc)
        if doc:
            doc_path = Path(__file__).resolve().parent / doc
            print('doc_path exists:', doc_path.exists())
            if doc_path.exists():
                raw = doc_path.read_bytes()
                try:
                    text = raw.decode('latin-1')
                except Exception:
                    text = str(raw[:200])
                print('\nPDF snippet:')
                print(text[:2000])

# Find latest training artifact for this model
rows = read_log('dev_pipeline_log.csv')
train_rows = [r for r in rows if r.get('stage') == 'training']
artifact_path = None
for r in reversed(train_rows):
    try:
        summ = r.get('summary') or {}
        if isinstance(summ, dict) and summ.get('model_name') == 'DEV_FINAL_VERIFY_002':
            artifact_path = r.get('artifact_path')
            break
    except Exception:
        continue
print('\nArtifact path:', artifact_path)
if artifact_path:
    art_file = Path(__file__).resolve().parent.parent / artifact_path
    print('artifact exists:', art_file.exists())
    if art_file.exists():
        art = json.loads(art_file.read_text(encoding='utf-8'))
        print('Artifact snippet keys:', list(art.keys()))
        print(json.dumps({k: art.get(k) for k in ['numeric_column_count','categorical_column_count','missing_value_count','missing_value_pct','duplicate_record_count','class_distribution','preprocessing_summary','encoding','scaling','feature_engineering_summary']}, indent=2, default=str))

print('\nDone')
