"""
Test the /models/recommend endpoint with a CSV file to debug feature engineering
"""
import requests
import pandas as pd
import json

# Try to find your CSV - check common locations
import os
from pathlib import Path

possible_locations = [
    "credit_risk_dataset_sicr_ready.csv",
    "../credit_risk_dataset_sicr_ready.csv",
    "C:/Users/adeha/Downloads/credit_risk_dataset_sicr_ready.csv",
]

csv_file = None
for loc in possible_locations:
    if os.path.exists(loc):
        csv_file = loc
        break

if csv_file is None:
    print("Your large CSV file not found. Please provide the path or upload it first.")
    print("Checked locations:")
    for loc in possible_locations:
        print(f"  - {loc}")
    exit(1)

print(f"Using CSV: {csv_file}")
df = pd.read_csv(csv_file)
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}\n")

# Guess target column (usually 'default', 'target', 'label', etc.)
target_col = None
for col in ['loan_status', 'default', 'target', 'label', 'default_flag', 'defaulted', 'is_default']:
    if col in df.columns:
        target_col = col
        break

if target_col is None:
    print("Could not auto-detect target column. Available columns:")
    for i, col in enumerate(df.columns):
        print(f"  {i}: {col}")
    print("\nPlease specify target_col in the script")
    exit(1)

print(f"Target column: {target_col}\n")

# Upload to the endpoint
print("Sending to /models/recommend endpoint...")
try:
    # Use file upload instead of csv_text for large files
    with open(csv_file, 'rb') as f:
        files = {'file': f}
        data = {'target_col': target_col}
        response = requests.post(
            "http://127.0.0.1:8000/models/recommend",
            files=files,
            data=data,
            timeout=120,
        )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Success!")
        print(f"Status: {response.status_code}")
        
        print(f"\nTraining set stats:")
        if 'training' in data:
            print(f"  - Train samples: {data['training'].get('train_n', 'N/A')}")
            print(f"  - Train features: {data['training'].get('train_features', 'N/A')}")
            print(f"  - Imbalance ratio: {data['training'].get('imbalance_ratio', 'N/A')}")
        
        print(f"\nFeature Engineering Summary:")
        if 'feature_engineering_summary' in data:
            fe_summary = data['feature_engineering_summary']
            print(f"  - Original shape: {fe_summary.get('original_shape', 'N/A')}")
            print(f"  - Final shape: {fe_summary.get('final_shape', 'N/A')}")
            print(f"  - Features added: {fe_summary.get('features_added', 'N/A')}")
            print(f"  - Features removed: {fe_summary.get('features_removed', 'N/A')}")
            
            if 'removed' in fe_summary and fe_summary['removed']:
                print(f"\n  Removed features ({len(fe_summary['removed'])}):")
                for col in fe_summary['removed'][:20]:  # Show first 20
                    print(f"    - {col}")
        
        print(f"\nModel Recommendations:")
        if 'recommendations' in data:
            for rec in data['recommendations']:
                print(f"  - {rec.get('model', 'N/A')}: {rec.get('score', 'N/A')}")
                
    else:
        print(f"✗ Error {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"✗ Request failed: {e}")
