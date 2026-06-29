"""
Analyze the FE plan in detail to understand feature selection
"""
import sys
sys.path.insert(0, ".")

import pandas as pd
from utils import detect_column_types, detect_task_type  
from preprocessing import prepare_data
from train import split_data
from feature_engineering import analyze_for_feature_engineering

csv_file = "C:/Users/adeha/Downloads/credit_risk_dataset_sicr_ready.csv"
target_col = "loan_status"

df = pd.read_csv(csv_file)
col_types = detect_column_types(df)
task_type = detect_task_type(df[target_col])

X, y, preproc, prep_report, feature_names = prepare_data(df, col_types, target_col)
X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y, test_size=0.15, val_size=0.15, task_type=task_type, random_state=42)

plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)

print("="*100)
print("DETAILED FE PLAN ANALYSIS")
print("="*100)

print("\n1. LOG TRANSFORM COLS:", plan.get('log_transform_cols', []))

print("\n2. INTERACTION PAIRS:", plan.get('interaction_pairs', []))

print("\n3. BINNING COLS:", plan.get('binning_cols', []))
print("   (Only first 5 will be binned):", plan.get('binning_cols', [])[:5])

print("\n4. FREQ ENCODING COLS:", plan.get('freq_encoding_cols', []))

print("\n5. WOE COLS:", plan.get('woe_cols', []))

print("\n6. IV SCORES (for context):")
for col, iv in sorted(plan.get('iv_scores', {}).items(), key=lambda x: x[1], reverse=True):
    print(f"   {col:40s}: {iv:.4f}")

print("\n7. DROP HIGH CORR PAIRS:", plan.get('drop_high_corr_pairs', []))

print("\n8. LOW VARIANCE COLS:", plan.get('low_variance_cols', []))

print("\n9. LOW IV COLS (IV < 0.02):")
low_iv = plan.get('low_iv_cols', [])
for col in low_iv:
    iv = plan.get('iv_scores', {}).get(col, 0)
    print(f"   {col:40s}: {iv:.4f}")

print("\n" + "="*100)
print("FEATURE COUNT CALCULATION")
print("="*100)
base_features = len(X_train.columns)
print(f"Base features: {base_features}")

log_features = len(plan.get('log_transform_cols', []))
print(f"Log features: {log_features}")

interaction_features = len(plan.get('interaction_pairs', []))
print(f"Interaction features: {interaction_features}")

# Note: binning is limited to first 5
binning_features = min(5, len(plan.get('binning_cols', [])))
print(f"Binning features (capped at 5): {binning_features}")

freq_features = len(plan.get('freq_encoding_cols', []))
print(f"Freq encoding features: {freq_features}")

woe_features = len(plan.get('woe_cols', []))
print(f"WOE features: {woe_features}")

total_added = log_features + interaction_features + binning_features + freq_features + woe_features
print(f"\nTotal features to add: {total_added}")

# Feature removal
corr_drop = len(set(p[1] for p in plan.get('drop_high_corr_pairs', [])))
var_drop = len(plan.get('low_variance_cols', []))
iv_drop = len(plan.get('low_iv_cols', []))
total_dropped = corr_drop + var_drop + iv_drop
print(f"Total features to drop: {total_dropped}")
print(f"  - from high correlation: {corr_drop}")
print(f"  - from low variance: {var_drop}")
print(f"  - from low IV: {iv_drop}")

# Estimate without orphaned removal
final_estimate = base_features + total_added - total_dropped
print(f"\nEstimated features (without orphaned removal): {final_estimate}")
print(f"Actual with orphaned removal: ~23 (need to verify)")
