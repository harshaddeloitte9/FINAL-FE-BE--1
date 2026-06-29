"""
Detailed trace of what happens inside the FastAPI /models/recommend endpoint
Add logging to the actual backend code to trace step-by-step
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
from utils import detect_column_types, detect_task_type  
from preprocessing import prepare_data
from train import split_data
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering

csv_file = "C:/Users/adeha/Downloads/credit_risk_dataset_sicr_ready.csv"
target_col = "loan_status"

print("="*100)
print("FASTAPI ENDPOINT FLOW - DETAILED TRACE")
print("="*100)

df = pd.read_csv(csv_file)
print(f"\n1. LOAD CSV")
print(f"   Shape: {df.shape}")

col_types = detect_column_types(df)
task_type = detect_task_type(df[target_col])

print(f"\n2. DETECT COLUMN TYPES (same as /data/upload)")

X, y, preproc, prep_report, feature_names = prepare_data(df, col_types, target_col)
print(f"\n3. PREPARE DATA")
print(f"   X shape: {X.shape}")
print(f"   Feature names from prepare_data: {feature_names}")

X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y, test_size=0.15, val_size=0.15, task_type=task_type, random_state=42)
print(f"\n4. SPLIT DATA")
print(f"   X_train shape: {X_train.shape}")
print(f"   X_train columns: {list(X_train.columns)}")

plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
print(f"\n5. ANALYZE FOR FEATURE ENGINEERING")
print(f"   Plan drop_high_corr_pairs: {plan.get('drop_high_corr_pairs', [])}")
print(f"   Plan low_iv_cols: {len(plan.get('low_iv_cols', []))} items")
print(f"   Plan low_variance_cols: {plan.get('low_variance_cols', [])}")

X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
print(f"\n6. APPLY FEATURE ENGINEERING")
print(f"   X_train_engineered shape: {X_train_engineered.shape}")
print(f"   X_train_engineered columns ({len(X_train_engineered.columns)}):")
for i, col in enumerate(sorted(X_train_engineered.columns), 1):
    print(f"      {i:2d}. {col}")

# This is what would be passed to recommend_models
n_samples = X_train_engineered.shape[0]
n_features = X_train_engineered.shape[1]  
vc = y_train.value_counts()
imbalance_ratio = float(vc.max() / vc.min()) if vc.min() > 0 else 1.0

print(f"\n7. VALUES PASSED TO recommend_models():")
print(f"   n_samples: {n_samples}")
print(f"   n_features: {n_features}")
print(f"   imbalance_ratio: {imbalance_ratio}")
print(f"   task_type: {task_type}")

# Import and run recommend_models
from model_selector import recommend_models

recs = recommend_models(n_samples, n_features, imbalance_ratio, task_type)

print(f"\n8. RECOMMENDATIONS:")
for rec in recs:
    print(f"   - {rec['name']}: {rec['score']}")

print(f"\n9. WHAT'S SHOWN IN UI:")
print(f"   Feature Count = {n_features}")
print(f"   Sample Count = {n_samples}")
print(f"   Logistic Regression score = {[r['score'] for r in recs if r['name'] == 'Logistic Regression'][0]}")
