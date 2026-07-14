import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient

root = Path('c:/Users/adeha/Downloads/Final UI 2')
backend_path = root / '24-06' / 'main.py'
spec = importlib.util.spec_from_file_location('backend_main', backend_path)
backend_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_main)

client = TestClient(backend_main.app)
with open(root / '24-06/sample.csv', 'rb') as f:
    resp = client.post(
        '/models/train',
        data={
            'target_col': 'loan_status',
            'test_size': '0.25',
            'val_size': '0.0',
            'random_seed': '42',
            'use_cv': 'false',
            'use_hyperopt': 'false',
            'manual_params': '{}',
            'task_type': 'binary',
            'use_feature_engineering': 'false',
        },
        files={'file': ('sample.csv', f, 'text/csv')},
    )
print('status', resp.status_code)
print(resp.headers)
print(resp.text)
