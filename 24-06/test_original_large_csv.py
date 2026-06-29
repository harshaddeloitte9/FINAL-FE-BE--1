"""
Test the original Streamlit pipeline with your large CSV to see feature count
"""
import sys
sys.path.insert(0, "../Credit-Risk-Poc-main")

import pandas as pd
from utils import detect_column_types, detect_task_type
from preprocessing import prepare_data
from train import split_data
from feature_engineering import analyze_for_feature_engineering, apply_feature_engineering

csv_file = "C:/Users/adeha/Downloads/credit_risk_dataset_sicr_ready.csv"
target_col = "loan_status"

print(f"Loading {csv_file}...")
df = pd.read_csv(csv_file)
print(f"Shape: {df.shape}\n")

print("="*80)
print("ORIGINAL STREAMLIT PIPELINE")
print("="*80)

# Original flow
col_types = detect_column_types(df)
task_type = detect_task_type(df[target_col])

print(f"Column types detected:")
for ctype, cols in col_types.items():
    print(f"  {ctype}: {len(cols)} columns")
    if len(cols) <= 10:
        print(f"    {cols}")

X, y, _, _, _ = prepare_data(df, col_types, target_col)
print(f"\nAfter prepare_data: X={X.shape}, y={y.shape}")
print(f"X columns: {list(X.columns)}")

X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y)
print(f"After split: X_train={X_train.shape}")

plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)

print(f"\nFE Plan:")
print(f"  log_transform_cols: {len(plan.get('log_transform_cols', []))} - {plan.get('log_transform_cols', [])}")
print(f"  interaction_pairs: {len(plan.get('interaction_pairs', []))} - {plan.get('interaction_pairs', [])}")
print(f"  binning_cols: {len(plan.get('binning_cols', []))} - {plan.get('binning_cols', [])}")
print(f"  freq_encoding_cols: {len(plan.get('freq_encoding_cols', []))} - {plan.get('freq_encoding_cols', [])}")
print(f"  woe_cols: {len(plan.get('woe_cols', []))} - {plan.get('woe_cols', [])}")
print(f"  drop_high_corr_pairs: {len(plan.get('drop_high_corr_pairs', []))} - {plan.get('drop_high_corr_pairs', [])}")
print(f"  low_variance_cols: {len(plan.get('low_variance_cols', []))} - {plan.get('low_variance_cols', [])}")
print(f"  low_iv_cols: {len(plan.get('low_iv_cols', []))} - First 10: {plan.get('low_iv_cols', [])[:10]}")

X_train_fe, summary = apply_feature_engineering(X_train, plan)

print(f"\nAfter FE:")
print(f"  Original shape: {summary.get('original_shape', 'N/A')}")
print(f"  Final shape: {summary.get('final_shape', 'N/A')}")
print(f"  Features added: {summary.get('features_added', 'N/A')}")
print(f"  Features removed: {summary.get('features_removed', 'N/A')}")

print(f"\nRemoved features:")
for col in summary.get('removed', []):
    print(f"  - {col}")

print(f"\nFinal engineered features ({X_train_fe.shape[1]}):")
for col in sorted(X_train_fe.columns):
    print(f"  - {col}")
