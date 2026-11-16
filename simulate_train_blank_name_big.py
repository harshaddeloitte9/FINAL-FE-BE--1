import sys
from pathlib import Path
import asyncio
import json

sys.path.insert(0, str(Path(__file__).resolve().parent / '24-06'))

import main
import persistence

async def run():
    # generate 200 rows
    rows = ["loan_status,age,income"]
    for i in range(200):
        status = 1 if i % 2 == 0 else 0
        age = 20 + (i % 50)
        income = 20000 + (i * 300)
        rows.append(f"{status},{age},{income}")
    csv_text = "\n".join(rows) + "\n"
    try:
        result = await main.train_model_endpoint(
            file=None,
            csv_text=csv_text,
            target_col='loan_status',
            model_name='',  # simulate frontend sending empty business model name
            estimator_name='XGBoost',
            model_owner='simuser',
            business_unit='QA',
            model_purpose='Sim blank name',
            model_version='0.2',
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
