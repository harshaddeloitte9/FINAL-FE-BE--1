"""
Comprehensive trace of original Streamlit pipeline - print dataframe at EVERY step
"""
import sys
sys.path.insert(0, "../Credit-Risk-Poc-main")

import pandas as pd
from utils import detect_column_types, detect_task_type
from preprocessing import prepare_data
from train import split_data
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering
import inspect

csv_file = "C:/Users/adeha/Downloads/credit_risk_dataset_sicr_ready.csv"
target_col = "loan_status"

print("="*100)
print("STEP-BY-STEP TRACE OF ORIGINAL STREAMLIT PIPELINE")
print("="*100)

df = pd.read_csv(csv_file)
print(f"\n1. LOAD CSV")
print(f"   Shape: {df.shape}")
print(f"   Columns ({len(df.columns)}): {list(df.columns)}")

col_types = detect_column_types(df)
task_type = detect_task_type(df[target_col])

print(f"\n2. DETECT COLUMN TYPES")
for ctype in ["id", "numeric", "categorical", "datetime", "boolean"]:
    cols = col_types.get(ctype, [])
    print(f"   {ctype} ({len(cols)}): {cols}")

X, y, _, _, _ = prepare_data(df, col_types, target_col)
print(f"\n3. PREPARE DATA (drop IDs, dedupe)")
print(f"   X shape: {X.shape}")
print(f"   X columns ({len(X.columns)}): {list(X.columns)}")
print(f"   y shape: {y.shape}")

X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y)
print(f"\n4. SPLIT DATA (train/val/test)")
print(f"   X_train shape: {X_train.shape}")
print(f"   X_train columns ({len(X_train.columns)}): {list(X_train.columns)}")
print(f"   y_train shape: {y_train.shape}")

plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
print(f"\n5. ANALYZE FOR FEATURE ENGINEERING")
print(f"   Plan keys: {list(plan.keys())}")
print(f"   log_transform_cols ({len(plan.get('log_transform_cols', []))}): {plan.get('log_transform_cols', [])}")
print(f"   interaction_pairs ({len(plan.get('interaction_pairs', []))}): {plan.get('interaction_pairs', [])}")
print(f"   binning_cols ({len(plan.get('binning_cols', []))}): {plan.get('binning_cols', [])}")
print(f"   freq_encoding_cols ({len(plan.get('freq_encoding_cols', []))}): {plan.get('freq_encoding_cols', [])}")
print(f"   woe_cols ({len(plan.get('woe_cols', []))}): {plan.get('woe_cols', [])}")
print(f"   drop_high_corr_pairs ({len(plan.get('drop_high_corr_pairs', []))}): {plan.get('drop_high_corr_pairs', [])}")
print(f"   low_variance_cols ({len(plan.get('low_variance_cols', []))}): {plan.get('low_variance_cols', [])}")
print(f"   low_iv_cols ({len(plan.get('low_iv_cols', []))}): {plan.get('low_iv_cols', [])[:10]}")

X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
print(f"\n6. APPLY FEATURE ENGINEERING")
print(f"   X_train_engineered shape: {X_train_engineered.shape}")
print(f"   X_train_engineered columns ({len(X_train_engineered.columns)}):")
for i, col in enumerate(sorted(X_train_engineered.columns), 1):
    print(f"      {i:2d}. {col}")

print(f"\n7. SUMMARY")
print(f"   Original features (before FE): {X_train.shape[1]}")
print(f"   Engineered features (after FE): {X_train_engineered.shape[1]}")
print(f"   Features added: {fe_summary.get('features_added', 0)}")
print(f"   Features removed: {fe_summary.get('features_removed', 0)}")
print(f"   Removed columns: {fe_summary.get('removed', [])}")

print(f"\n8. CHECK FOR ADDITIONAL PROCESSING")
print(f"   Is there any preprocessing pipeline applied after FE?")
print(f"   Let me search for rebuild_preprocessor_for usage...")

# Check if there's anything else
print(f"\n   Checking for any function calls after apply_feature_engineering in app.py...")
print(f"   Looking for calls to rebuild_preprocessor_for or other transformations...")
