import sys
from pathlib import Path
import asyncio
import json

# Ensure module imports resolve to the backend package in 24-06
sys.path.insert(0, str(Path(__file__).resolve().parent / '24-06'))

import main
import persistence

async def run():
    # Simple CSV with header and a few rows
    csv_text = "loan_status,age,income\n1,30,50000\n0,45,60000\n1,25,40000\n"
    try:
        result = await main.train_model_endpoint(
            file=None,
            csv_text=csv_text,
            target_col='loan_status',
            model_name='Sim_Dev_Model_Trace',
            estimator_name='XGBoost',
            model_owner='tester',
            business_unit='QA',
            model_purpose='Sim trace',
            model_version='0.1',
            model_type='Classification',
            development_date='2026-08-13',
            status='In Development',
            documentation_path=None,
            test_size=0.2,
            val_size=0.1,
            random_seed=42,
            use_cv=False,
            cv_folds=3,
            use_hyperopt=False,
            scale_pos_weight=1.0,
            manual_params=None,
            use_feature_engineering=False,
            synthetic_samples=None,
            use_oot=False,
            date_col=None,
            threshold=None,
        )
        print('train result keys:', list(result.keys()))
    except Exception as e:
        print('TRAIN RAISED:', e)
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run())
