#!/usr/bin/env python3
import json
import base64
import io
from pathlib import Path
import numpy as np
import pandas as pd
import importlib.util
import requests
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier

ROOT = Path(__file__).resolve().parent
SAMPLE_CSV = ROOT / "sample.csv"
# Use the migrated FastAPI at localhost:8000
API_URL = "http://127.0.0.1:8000/models/evaluate"

# Helper: base64 serialize pipeline using existing main._to_base64 when available
def pipeline_to_base64(pipeline):
    try:
        spec = importlib.util.spec_from_file_location("main_module", ROOT / "main.py")
        main_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_mod)
        if hasattr(main_mod, "_to_base64"):
            return main_mod._to_base64(pipeline)
    except Exception:
        pass
    # fallback: joblib dump to bytes then base64
    import joblib
    buf = io.BytesIO()
    joblib.dump(pipeline, buf)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

# Load local evaluation helpers (the migrated functions used by the FastAPI backend)
spec = importlib.util.spec_from_file_location("local_eval", ROOT / "evaluate.py")
streamlit_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(streamlit_eval)

# Read dataset and train a pipeline
print("Loading sample and training model...")
df = pd.read_csv(SAMPLE_CSV)
# determine target column - use loan_status if present, else try common names
if "loan_status" in df.columns:
    target_col = "loan_status"
elif "default" in df.columns:
    target_col = "default"
else:
    raise SystemExit("No known target column in sample.csv")

X = df.drop(columns=[target_col])
y = df[target_col]

num_cols = X.select_dtypes(include=["number"]).columns.tolist()
cat_cols = X.select_dtypes(exclude=["number"]).columns.tolist()
pre = ColumnTransformer([
    ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), num_cols),
    ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cat_cols),
])
# Build pipeline
pipeline = Pipeline([("preprocess", pre), ("model", RandomForestClassifier(n_estimators=80, random_state=42))])
pipeline.fit(X, y)

# Predictions and probabilities
preds = pipeline.predict(X)
proba = pipeline.predict_proba(X)
# Ensure proba is 2-D or 1-D handled by streamlit helpers

# Streamlit reference metrics and artifacts
print("Computing Streamlit reference metrics and artifacts...")
compute = streamlit_eval
metrics_streamlit = compute.compute_binary_metrics(y.values, preds, proba, threshold=0.5)
# some functions may not exist in older reference; guard with hasattr
roc_pts = compute.compute_roc_curve(y.values, proba) if hasattr(compute, "compute_roc_curve") else []
pr_pts = compute.compute_pr_curve(y.values, proba) if hasattr(compute, "compute_pr_curve") else []
thresh_rows = compute.compute_threshold_analysis(y.values, proba) if hasattr(compute, "compute_threshold_analysis") else []
gain_rows = compute.compute_gain_chart(y.values, proba) if hasattr(compute, "compute_gain_chart") else []
lift_rows = compute.compute_lift_chart(y.values, proba) if hasattr(compute, "compute_lift_chart") else []
score_rows = compute.compute_score_distribution(y.values, proba) if hasattr(compute, "compute_score_distribution") else []

# Send same trained model artifact and csv to FastAPI evaluate endpoint
print("Calling FastAPI evaluate endpoint...")
artifact_b64 = pipeline_to_base64(pipeline)
files = {"file": (SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "text/csv")}
data = {"model_artifact": artifact_b64, "target_col": target_col, "threshold": "0.5"}
resp = requests.post(API_URL, files=files, data=data, timeout=120)
resp.raise_for_status()
api_payload = resp.json()
metrics_api = api_payload = api_payload = resp.json().get("evaluation_metrics") or resp.json().get("metrics") or {}
eval_data_api = resp.json().get("evaluation_data") or {}

# Build React-exported CSV content using current frontend logic: header Metric,Value and numeric-only metrics
numeric_metrics = {k: v for k, v in (metrics_api or {}).items() if isinstance(v, (int, float)) and np.isfinite(v)}
react_csv_lines = ["Metric,Value"]
for k, v in numeric_metrics.items():
    react_csv_lines.append(f'{json.dumps(k)},{json.dumps(str(v))}')
react_csv = "\n".join(react_csv_lines)

# Prepare comparison entries
entries = []
# numeric metrics
for key in ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"]:
    s = metrics_streamlit.get(key)
    f = metrics_api.get(key)
    entries.append((key, s, f))
# confusion matrix and classification report
entries.append(("confusion_matrix", metrics_streamlit.get("confusion_matrix"), metrics_api.get("confusion_matrix")))
entries.append(("classification_report", metrics_streamlit.get("classification_report"), metrics_api.get("classification_report")))
# counts
entries.append(("roc_point_count", len(roc_pts), len(eval_data_api.get("roc_curve", []))))
entries.append(("pr_point_count", len(pr_pts), len(eval_data_api.get("pr_curve", []))))
entries.append(("threshold_analysis_row_count", len(thresh_rows), len(eval_data_api.get("threshold_analysis", []))))
entries.append(("gain_chart_row_count", len(gain_rows), len(eval_data_api.get("gain_chart", []))))
entries.append(("lift_chart_row_count", len(lift_rows), len(eval_data_api.get("lift_chart", []))))
entries.append(("score_distribution_row_count", len(score_rows), len(eval_data_api.get("score_distribution", []))))
# exported csv: Streamlit builds a dataframe of numeric metrics and writes Metric,Value rows; React uses numeric metrics from API.
# We'll construct the Streamlit exported CSV (from metrics_streamlit numeric) and React's CSV (from API numeric)
streamlit_numeric = {k: v for k, v in metrics_streamlit.items() if isinstance(v, (int, float))}
streamlit_csv_lines = ["Metric,Value"]
for k, v in streamlit_numeric.items():
    streamlit_csv_lines.append(f'{json.dumps(k)},{json.dumps(str(v))}')
streamlit_csv = "\n".join(streamlit_csv_lines)

# Now build markdown table
md = []
md.append("| Metric | Streamlit | FastAPI | React | PASS/FAIL |")
md.append("|---|---|---|---|---|")
all_pass = True
mismatches = []
for name, s_val, f_val in entries:
    # format values for display
    def fmt(v):
        try:
            return json.dumps(v)
        except Exception:
            return str(v)
    s_disp = fmt(s_val)
    f_disp = fmt(f_val)
    # React column: if this metric is one of numeric ones, React will show value from numeric_metrics
    if name in ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"]:
        r_val = numeric_metrics.get(name)
        r_disp = fmt(r_val)
        # compare numeric with tolerance
        passed = False
        try:
            if s_val == f_val:
                passed = True
            elif isinstance(s_val, (int, float)) and isinstance(f_val, (int, float)):
                if np.isfinite(s_val) and np.isfinite(f_val) and abs(float(s_val) - float(f_val)) < 1e-6:
                    passed = True
        except Exception:
            passed = False
        if not passed:
            all_pass = False
            mismatches.append((name, s_disp, f_disp))
        md.append(f"| {name} | {s_disp} | {f_disp} | {r_disp} | {'PASS' if passed else 'FAIL'} |")
    elif name in ("confusion_matrix", "classification_report"):
        r_disp = "(n/a)"
        # React export will not include nested structures; show Streamlit and FastAPI
        passed = False
        try:
            if s_val == f_val:
                passed = True
        except Exception:
            passed = False
        if not passed:
            all_pass = False
            mismatches.append((name, s_disp, f_disp))
        md.append(f"| {name} | {s_disp} | {f_disp} | {r_disp} | {'PASS' if passed else 'FAIL'} |")
    else:
        # counts
        r_disp = f_disp
        passed = (s_val == f_val)
        if not passed:
            all_pass = False
            mismatches.append((name, s_disp, f_disp))
        md.append(f"| {name} | {s_disp} | {f_disp} | {r_disp} | {'PASS' if passed else 'FAIL'} |")

# Add exported CSV contents as final row
# React exported CSV is react_csv; Streamlit exported CSV is streamlit_csv; FastAPI doesn't directly export CSV but metrics_api is source for React
csv_pass = (streamlit_csv == react_csv)
if not csv_pass:
    all_pass = False
    mismatches.append(("Exported metrics CSV contents", streamlit_csv, react_csv))
md.append(f"| Exported metrics CSV contents | {streamlit_csv.replace(chr(10),'\\n')} | {json.dumps(metrics_api)} | {react_csv.replace(chr(10),'\\n')} | {'PASS' if csv_pass else 'FAIL'} |")

# Print table and summary
print('\n'.join(md))
print('\n')
if all_pass:
    print('100% parity achieved.')
else:
    print('Mismatches detected:')
    for m in mismatches:
        print('- ', m[0], ':')
        print('   Streamlit ->', m[1])
        print('   FastAPI  ->', m[2])

# Exit status
if all_pass:
    raise SystemExit(0)
else:
    raise SystemExit(2)
