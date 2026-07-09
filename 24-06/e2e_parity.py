"""e2e_parity.py
Train a quick model on the sample dataset, evaluate locally using the
source evaluate functions and via the running FastAPI /models/evaluate
endpoint, then compare key metrics.
"""
import base64
import io
import json
import sys
from pathlib import Path
import requests
import joblib
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from train import split_data, train_model
from preprocessing import prepare_data
from utils import detect_column_types
from sklearn.ensemble import RandomForestClassifier


def _resolve_target_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if c.lower() in ("default", "target", "y", "label", "loan_status"):
            return c
    for c in df.columns[::-1]:
        vals = df[c].dropna().unique()
        if set(vals).issubset({0, 1, 0.0, 1.0}):
            return c
    raise SystemExit("Could not find a target column in sample.csv")

# Load sample data
csv_path = ROOT / "sample.csv"
df = pd.read_csv(csv_path)

# Infer target
target_col = _resolve_target_col(df)

col_types = detect_column_types(df)

# Prepare data (build preprocessing report + unfitted preprocessor)
X_all, y_all, preprocessor, prep_report, feature_names = prepare_data(df, col_types, target_col)

X_train, X_val, X_test, y_train, y_val, y_test = split_data(X_all, y_all, test_size=0.2, val_size=0.1, task_type="binary")
model = RandomForestClassifier(n_estimators=50, random_state=42)
pipeline, info, real_names = train_model(X_train, y_train, col_types, target_col, prep_report, model, task_type="binary")

# Local evaluation (source evaluate functions are available via evaluate.py)
from evaluate import compute_binary_metrics
from sklearn.metrics import roc_curve, precision_recall_curve, roc_auc_score, average_precision_score

X_eval = X_test.copy()
y_true = y_test.values
try:
    y_pred = pipeline.predict(X_eval)
except Exception as e:
    y_pred = np.zeros(len(X_eval), dtype=int)
try:
    y_proba = pipeline.predict_proba(X_eval)
except Exception:
    y_proba = None

def _to_score_array(probabilities):
    if probabilities is None:
        return None
    arr = np.asarray(probabilities)
    if arr.ndim == 1:
        return arr.astype(float)
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            return arr[:, 0].astype(float)
        if arr.shape[1] >= 2:
            return arr[:, 1].astype(float)
    return arr.astype(float)

if y_proba is not None:
    y_proba = _to_score_array(y_proba)

local_metrics = compute_binary_metrics(y_true, y_pred, y_proba, threshold=0.5)
if y_proba is not None:
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    local_roc = [{"fpr": float(a), "tpr": float(b)} for a,b in zip(fpr.tolist(), tpr.tolist())]
else:
    local_roc = []

# Call running API
api_url = "http://127.0.0.1:8000/models/evaluate"
# prepare model artifact
buf = io.BytesIO()
joblib.dump(pipeline, buf)
buf.seek(0)
model_b64 = base64.b64encode(buf.read()).decode('utf-8')

eval_df = pd.concat([X_test, y_test.rename(target_col)], axis=1)
csv_text = eval_df.to_csv(index=False)

resp = requests.post(api_url, data={
    'model_artifact': model_b64,
    'csv_text': csv_text,
    'target_col': target_col,
    'threshold': 0.5,
}, timeout=120)
try:
    resp.raise_for_status()
except requests.HTTPError as exc:
    print(resp.text)
    raise exc
api_payload = resp.json()

api_metrics = api_payload.get('evaluation_metrics') or api_payload.get('metrics')

# Compare keys of interest
keys = ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "ks_statistic"]
report = []
for k in keys:
    lval = local_metrics.get(k)
    aval = api_metrics.get(k) if api_metrics else None
    passed = (lval == aval)
    report.append((k, lval, aval, passed))

print("End-to-end parity report")
print("Key | Local | API | PASSED")
for row in report:
    print(f"{row[0]:<12} | {row[1]} | {row[2]} | {row[3]}")

# Save report
with open(ROOT / "e2e_parity_report.json", 'w', encoding='utf-8') as f:
    json.dump({r[0]: {"local": r[1], "api": r[2], "pass": r[3]} for r in report}, f, indent=2)

print("Report written to e2e_parity_report.json")
