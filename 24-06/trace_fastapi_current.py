"""
COMPLETE TRACE: FastAPI implementation
Same flow as original but using current 24-06 code with orphaned feature removal
"""
import sys
sys.path.insert(0, "c:/Users/adeha/Downloads/Final UI 2/24-06")

import pandas as pd

print("=" * 120)
print("TRACING FASTAPI IMPLEMENTATION (24-06 with orphaned removal)")
print("=" * 120)

from utils import detect_column_types, detect_task_type
from preprocessing import prepare_data
from train import split_data
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering
from model_selector import recommend_models

csv_file = "C:/Users/adeha/Downloads/credit_risk_dataset_sicr_ready.csv"
target_col = "loan_status"

df = pd.read_csv(csv_file)
print(f"\n1. LOAD: {df.shape}")

col_types = detect_column_types(df)
task_type = detect_task_type(df[target_col])

X, y, preproc, prep_report, feature_names = prepare_data(df, col_types, target_col)
print(f"2. PREPARE: {X.shape}")

X_train, X_val, X_test, y_train, y_val, y_test = split_data(
    X, y, test_size=0.15, val_size=0.15, task_type=task_type, random_state=42
)
print(f"3. SPLIT X_train: {X_train.shape}")

plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
print(f"4. ANALYZE_FE (plan created)")

X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
print(f"\n5. APPLY_FE on X_train:")
print(f"   Before FE:  {X_train.shape}")
print(f"   After FE:   {X_train_engineered.shape}")
print(f"   Removed:    {fe_summary['features_removed']} features")
print(f"   Added:      {fe_summary['features_added']} features")
print(f"   FE Summary (removed list): {fe_summary.get('removed', [])}")

# FastAPI /models/recommend endpoint uses X_train_engineered directly
X_engineered = X_train_engineered
print(f"\n6. /models/recommend uses X_train_engineered")
print(f"   Shape: {X_engineered.shape}")
print(f"   Columns ({len(X_engineered.columns)}):")
for i, col in enumerate(sorted(X_engineered.columns), 1):
    print(f"      {i:2d}. {col}")

# FastAPI passes this directly to recommend_models (line ~565 in main.py)
X_for_recommendation = X_engineered
print(f"\n7. recommend_models gets X_for_recommendation:")
print(f"   Shape: {X_for_recommendation.shape}")

# Line 565: n_features = X_train_engineered.shape[1]
n_samples, n_features = X_for_recommendation.shape
imbalance_ratio = float(y_train.value_counts().max() / y_train.value_counts().min())

print(f"\n8. RECOMMENDATION INPUTS:")
print(f"   n_samples: {n_samples}")
print(f"   n_features: {n_features}")
print(f"   imbalance_ratio: {imbalance_ratio:.4f}")
print(f"   task_type: {task_type}")

# Call recommend_models
recommendations = recommend_models(n_samples, n_features, imbalance_ratio, task_type)

print(f"\n9. RECOMMENDATIONS:")
for rec in recommendations:
    print(f"   {rec['name']:20s}: {rec['score']}")

print("\n" + "=" * 120)
print("FASTAPI RESULT")
print("=" * 120)
print(f"Display: Training set: {n_samples:,} samples × {n_features} features")
print(f"Features after FE applied: {n_features}")
print(f"Logistic Regression score: {[r['score'] for r in recommendations if r['name'] == 'Logistic Regression'][0]}")
