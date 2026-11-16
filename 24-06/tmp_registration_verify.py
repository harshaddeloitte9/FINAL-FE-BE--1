from fastapi.testclient import TestClient
import json
from pathlib import Path
from main import app
import time

client = TestClient(app)

model_name = "DEV_REGISTRATION_VERIFY_001"

data = {
    "target_col": "default",
    "model_name": model_name,
    "estimator_name": "Logistic Regression",
    "model_owner": "tester",
    "business_unit": "test_unit",
    "model_purpose": "verification of registration flow",
    "model_version": "0.1",
    "model_type": "classification",
    "development_date": "2026-08-13",
    "status": "In Development",
    "random_seed": "42",
    "use_cv": "false",
    "cv_folds": "5",
    "use_hyperopt": "false",
    # Use synthetic samples to ensure both classes are present in training
    "synthetic_samples": "200",
}

print('Posting training request for', model_name)
resp = client.post("/models/train", data=data)
print('status', resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.content[:200])

# small pause for filesystem flush
time.sleep(1)

from persistence import APP_DATA_DIR, get_model_inventory_path
inv_path = get_model_inventory_path()
print('\nInventory path:', inv_path.resolve())
print('Inventory exists:', inv_path.exists())

artifact_found = False
artifact_model_id = None
artifact_path = None

# search dev pipeline log for latest matching training artifact for this model_name
log_csv = APP_DATA_DIR / 'dev_pipeline_log.csv'
if log_csv.exists():
    with open(log_csv, 'r', encoding='utf-8') as f:
        for line in f:
            if model_name in line and ',training,' in line:
                parts = line.split(',')
                run_id = parts[0]
                # artifact path reconstruct
                candidate = APP_DATA_DIR / 'artifacts' / 'dev_pipeline_log' / 'training' / f"{run_id}.json"
                if candidate.exists():
                    artifact_path = candidate
                    try:
                        art = json.loads(candidate.read_text(encoding='utf-8'))
                        artifact_found = True
                        artifact_model_id = art.get('model_id')
                        print('\nFound training artifact:', candidate)
                        print('artifact model_name:', art.get('model_name'))
                        print('artifact model_id:', artifact_model_id)
                    except Exception as _e:
                        print('failed to read artifact json', _e)
                    break

inv_record_found = False
inv_record = None
if inv_path.exists():
    inv = json.loads(inv_path.read_text(encoding='utf-8'))
    for d in inv.get('development', []):
        if d.get('model_name') == model_name:
            inv_record_found = True
            inv_record = d
            print('\nInventory record found for model:')
            print(json.dumps(d, indent=2, default=str))
            break

# Check report
report_path = APP_DATA_DIR / 'model_reports' / f"{model_name}_model_report.pdf"
print('\nReport path:', report_path.resolve())
print('Report exists:', report_path.exists())
if report_path.exists():
    raw = report_path.read_bytes()
    try:
        text = raw.decode('latin-1')
    except Exception:
        text = str(raw[:200])
    snippet = text[:2000]
    print('\nPDF snippet:')
    print(snippet)

print('\nSummary:')
print('Development model:')
print('Model ID:', artifact_model_id or (inv_record.get('model_id') if inv_record else ''))
print('Training artifact:', artifact_path if artifact_path else 'Not found')
print('Inventory path:', inv_path.resolve())
print('Inventory record found:', bool(inv_record_found))
print('Report path:', report_path.resolve())
print('PDF Model ID:', 'Check PDF snippet above')
print('PDF Model Name:', model_name)
print('Registration successful:', bool(inv_record_found and artifact_found and artifact_model_id and (inv_record and inv_record.get('model_id') == artifact_model_id)))
