from fastapi.testclient import TestClient
import json
from pathlib import Path
from main import app

client = TestClient(app)

data = {
    "target_col": "default",
    "model_name": "DEV_TEST_MODEL",
    "estimator_name": "Logistic Regression",
    "model_owner": "tester",
    "business_unit": "test_unit",
    "model_purpose": "testing end-to-end",
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

resp = client.post("/models/train", data=data)

print("status", resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.content[:200])

# After train, read inventory and report
from persistence import APP_DATA_DIR, get_model_inventory_path
inv_path = APP_DATA_DIR / 'model_inventory.json'
print('\nInventory exists:', inv_path.exists())
if inv_path.exists():
    inv = json.loads(inv_path.read_text(encoding='utf-8'))
    print('Development entries:', len(inv.get('development', [])))
    for d in inv.get('development', []):
        if d.get('model_name') == 'DEV_TEST_MODEL':
            print('\nFound entry:')
            print(json.dumps(d, indent=2, default=str))
            doc = d.get('documentation_path')
            print('doc:', doc)
            if doc:
                doc_path = Path(__file__).resolve().parent.parent / doc
                print('doc_path exists:', doc_path.exists())
                if doc_path.exists():
                    raw = doc_path.read_bytes()
                    try:
                        text = raw.decode('latin-1')
                    except Exception:
                        text = str(raw[:200])
                    print('\nPDF snippet:')
                    print(text[:2000])

print('\nDone')
