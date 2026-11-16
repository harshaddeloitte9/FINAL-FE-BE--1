import asyncio
import pandas as pd
import json
from importlib import import_module

# Use project's venv python to run this script
main = import_module('24-06.main'.replace('-', '_')) if False else None
# Instead import via path
import importlib.util, sys
from pathlib import Path
# Ensure the backend folder is importable so `from utils import ...` works
backend_path = Path(__file__).resolve().parent.parent / '24-06'
sys.path.insert(0, str(backend_path))
spec = importlib.util.spec_from_file_location('main_mod', str(backend_path / 'main.py'))
main_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_mod)

# Generate synthetic dataset
from utils import generate_synthetic_credit_dataset, detect_column_types

df = generate_synthetic_credit_dataset(n_samples=500)
csv_text = df.to_csv(index=False)

# Prepare minimal args for endpoint
kwargs = {
    'file': None,
    'csv_text': csv_text,
    'target_col': 'default',
    'model_name': 'Automated_Test_Model_For_Report_v2',
    'estimator_name': 'LightGBM',
    'synthetic_samples': None,
    'test_size': 0.15,
    'val_size': 0.15,
    'random_seed': 42,
    'use_cv': False,
    'cv_folds': 5,
    'use_hyperopt': False,
    'scale_pos_weight': 1.0,
    'manual_params': None,
    'use_feature_engineering': False,
    'synthetic_samples': None,
    'use_oot': False,
    'date_col': None,
    'threshold': None,
    # Explicit optional metadata to avoid FastAPI Form() default objects
    'model_owner': 'auto_test_user',
    'business_unit': 'Automation',
    'model_purpose': 'Automated development run for report verification',
    'model_version': '0.0.1',
    'model_type': 'Classification',
    'development_date': pd.Timestamp.now().date().isoformat(),
    'status': 'In Development',
    'documentation_path': None,
}

# Call the async endpoint
import asyncio
async def run():
    res = await main_mod.train_model_endpoint(**kwargs)
    print('Train endpoint returned keys:', list(res.keys()))
    return res

if __name__ == '__main__':
    r = asyncio.run(run())
    print('Done')
