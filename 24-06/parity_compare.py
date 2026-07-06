import importlib.util
from pathlib import Path
import numpy as np
import json

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'Credit-Risk-Poc-main' / 'evaluate.py'
CURRENT = ROOT / 'evaluate.py'

def load_module(path):
    spec = importlib.util.spec_from_file_location('mod', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

legacy = load_module(SOURCE)
current = load_module(CURRENT)

print('Loaded legacy from', SOURCE)
print('Loaded current from', CURRENT)

# deterministic test data
np.random.seed(0)
y_true = np.concatenate([np.zeros(500), np.ones(500)]).astype(int)
# make scores correlated
scores = np.concatenate([np.random.beta(2,5,500), np.random.beta(5,2,500)])

# small balanced sample too
y_true_small = np.array([0,1,0,1,0,1], dtype=int)
y_proba_small = np.array([0.1,0.9,0.2,0.8,0.3,0.7], dtype=float)

def cmp(name, legacy_res, current_res):
    ok = legacy_res == current_res
    # for lists of dicts/numbers, try to compare via json dumping with rounding
    if not ok:
        try:
            lhs = json.dumps(legacy_res, sort_keys=True)
            rhs = json.dumps(current_res, sort_keys=True)
            ok = lhs == rhs
        except Exception:
            ok = False
    print(f"{name}: {'PASS' if ok else 'MISMATCH'}")
    if not ok:
        print('--- legacy:')
        print(legacy_res)
        print('--- current:')
        print(current_res)

# functions to compare
pairs = [
    ('compute_binary_metrics_small', lambda: legacy.compute_binary_metrics(y_true_small, None, y_proba_small, threshold=0.5), lambda: current.compute_binary_metrics(y_true_small, None, y_proba_small, threshold=0.5)),
    ('compute_roc_curve_small', lambda: legacy.compute_roc_curve(y_true_small, y_proba_small), lambda: current.compute_roc_curve(y_true_small, y_proba_small)),
    ('compute_pr_curve_small', lambda: legacy.compute_pr_curve(y_true_small, y_proba_small), lambda: current.compute_pr_curve(y_true_small, y_proba_small)),
    ('compute_threshold_analysis_small', lambda: legacy.compute_threshold_analysis(y_true_small, y_proba_small), lambda: current.compute_threshold_analysis(y_true_small, y_proba_small)),
    ('compute_gain_chart_small', lambda: legacy.compute_gain_chart(y_true_small, y_proba_small), lambda: current.compute_gain_chart(y_true_small, y_proba_small)),
    ('compute_score_distribution_small', lambda: legacy.compute_score_distribution(y_true_small, y_proba_small), lambda: current.compute_score_distribution(y_true_small, y_proba_small)),
    ('compute_hetero_small', lambda: legacy.compute_heteroscedasticity_check(y_true_small, y_proba_small), lambda: current.compute_heteroscedasticity_check(y_true_small, y_proba_small)),
    ('compute_temporal_small', lambda: legacy.compute_temporal_stability_summary(['2023-01-01','2023-01-15','2023-02-01','2023-02-15','2023-03-01','2023-03-15'], y_true_small, y_proba_small, freq='Monthly'), lambda: current.compute_temporal_stability_summary(['2023-01-01','2023-01-15','2023-02-01','2023-02-15','2023-03-01','2023-03-15'], y_true_small, y_proba_small, freq='Monthly')),
]

for name, lfun, cfun in pairs:
    try:
        l = lfun()
    except Exception as e:
        l = f'ERROR: {e}'
    try:
        c = cfun()
    except Exception as e:
        c = f'ERROR: {e}'
    cmp(name, l, c)

# large sample comparisons (only numeric summaries)
print('\nLarge-sample summaries')
try:
    l_metrics = legacy.compute_binary_metrics(y_true, None, scores, threshold=0.5)
except Exception as e:
    l_metrics = f'ERROR: {e}'
try:
    c_metrics = current.compute_binary_metrics(y_true, None, scores, threshold=0.5)
except Exception as e:
    c_metrics = f'ERROR: {e}'
cmp('binary_metrics_large', l_metrics, c_metrics)

try:
    l_gain = legacy.compute_gain_chart(y_true, scores)
except Exception as e:
    l_gain = f'ERROR: {e}'
try:
    c_gain = current.compute_gain_chart(y_true, scores)
except Exception as e:
    c_gain = f'ERROR: {e}'
cmp('gain_large', l_gain, c_gain)

print('\nDone')
