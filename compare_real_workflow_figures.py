import importlib.util
import pandas as pd
from pathlib import Path
from fastapi.testclient import TestClient

root = Path.cwd()
backend_path = root / '24-06' / 'main.py'
source_path = root / '24-06' / 'Credit-Risk-Poc-main' / 'evaluate.py'

spec = importlib.util.spec_from_file_location('backend_main', backend_path)
backend_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_main)

spec2 = importlib.util.spec_from_file_location('source_eval', source_path)
source_eval = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(source_eval)

# Use the same sample dataset uploaded through the application workflow.
df = pd.read_csv(root / 'Credit-Risk-Poc-main' / 'demo_data' / 'clean_portfolio.csv')

client = TestClient(backend_main.app)
with open(root / 'Credit-Risk-Poc-main' / 'demo_data' / 'clean_portfolio.csv', 'rb') as f:
    train_resp = client.post(
        '/models/train',
        data={
            'target_col': 'default',
            'model_name': 'XGBoost',
            'test_size': '0.25',
            'val_size': '0.15',
            'random_seed': '42',
            'use_cv': 'false',
            'cv_folds': '5',
            'use_hyperopt': 'false',
            'use_class_weight': 'false',
            'scale_pos_weight': '1.0',
            'manual_params': '{}',
            'use_feature_engineering': 'false',
        },
        files={'file': ('clean_portfolio.csv', f, 'text/csv')},
    )

print('train_status', train_resp.status_code)
print('train_body', train_resp.text)
if train_resp.status_code != 200:
    raise SystemExit('Training endpoint failed')
model_artifact = train_resp.json()['model_artifact']

with open(root / 'Credit-Risk-Poc-main' / 'demo_data' / 'clean_portfolio.csv', 'rb') as f:
    eval_resp = client.post(
        '/models/evaluate',
        data={
            'model_artifact': model_artifact,
            'target_col': 'default',
            'threshold': '0.5',
        },
        files={'file': ('clean_portfolio.csv', f, 'text/csv')},
    )

print('eval_status', eval_resp.status_code)
print('eval_body', eval_resp.text)
eval_data = eval_resp.json()['evaluation_data']

pipeline = backend_main._from_base64(model_artifact)
X_eval = df.drop(columns=['default'])
y_true = df['default'].values
y_pred = pipeline.predict(X_eval)
y_proba = pipeline.predict_proba(X_eval)
metrics = backend_main.compute_binary_metrics(y_true, y_pred, y_proba, threshold=0.5)

orig_figs = {
    'ROC': source_eval.plot_roc_curve(y_true, y_proba).to_dict(),
    'PR': source_eval.plot_pr_curve(y_true, y_proba).to_dict(),
    'Confusion Matrix': source_eval.plot_confusion_matrix(metrics['confusion_matrix']).to_dict(),
    'Threshold Analysis': source_eval.plot_threshold_analysis(y_true, y_proba).to_dict(),
    'Score Distribution': source_eval.plot_score_distribution(y_true, y_proba).to_dict(),
    'Gain/Lift': source_eval.plot_lift_chart(y_true, y_proba).to_dict(),
}
fastapi_figs = {
    'ROC': eval_data['roc_curve_figure'],
    'PR': eval_data['pr_curve_figure'],
    'Confusion Matrix': eval_data['confusion_matrix_figure'],
    'Threshold Analysis': eval_data['threshold_analysis_figure'],
    'Score Distribution': eval_data['score_distribution_figure'],
    'Gain/Lift': eval_data['lift_chart_figure'],
}


def normalize(obj):
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items() if k not in {'uid', 'id'}}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def trace_info(fig):
    traces = fig.get('data', [])
    return {
        'trace_count': len(traces),
        'trace_names': [t.get('name') for t in traces],
        'points_per_trace': [len(t.get('x') or []) for t in traces],
        'layout': fig.get('layout', {}),
        'annotations': fig.get('layout', {}).get('annotations', []),
    }


def compare(a, b, path='$'):
    diffs = []
    if type(a) != type(b):
        return [(path, a, b, 'type changed')]
    if isinstance(a, dict):
        keys = set(a) | set(b)
        for k in sorted(keys):
            if k not in a:
                diffs.append((path + '.' + k, None, b[k], 'missing in original'))
            elif k not in b:
                diffs.append((path + '.' + k, a[k], None, 'missing in FastAPI'))
            else:
                diffs.extend(compare(a[k], b[k], path + '.' + k))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append((path, a, b, 'length changed'))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diffs.extend(compare(x, y, f'{path}[{i}]'))
    elif a != b:
        diffs.append((path, a, b, 'value changed'))
    return diffs

print('REAL WORKFLOW FIGURE COMPARISON')
print('=============================')
for name in orig_figs:
    orig = orig_figs[name]
    fast = fastapi_figs[name]
    orig_info = trace_info(orig)
    fast_info = trace_info(fast)
    print(f'FIGURE: {name}')
    print('  Original trace count:', orig_info['trace_count'])
    print('  FastAPI trace count:', fast_info['trace_count'])
    print('  Original trace names:', orig_info['trace_names'])
    print('  FastAPI trace names:', fast_info['trace_names'])
    print('  Original points per trace:', orig_info['points_per_trace'])
    print('  FastAPI points per trace:', fast_info['points_per_trace'])
    print('  Original layout title:', orig.get('layout', {}).get('title'))
    print('  FastAPI layout title:', fast.get('layout', {}).get('title'))
    print('  Original axis titles:', {k: (v.get('title') if isinstance(v, dict) else v) for k, v in orig.get('layout', {}).items() if k.startswith(('xaxis', 'yaxis'))})
    print('  FastAPI axis titles:', {k: (v.get('title') if isinstance(v, dict) else v) for k, v in fast.get('layout', {}).items() if k.startswith(('xaxis', 'yaxis'))})
    print('  Original annotation count:', len(orig_info['annotations']))
    print('  FastAPI annotation count:', len(fast_info['annotations']))
    norm_orig = normalize(orig)
    norm_fast = normalize(fast)
    if norm_orig == norm_fast:
        print('  Comparison: identical')
    else:
        print('  Comparison: DIFFERENT')
        for path, old, new, reason in compare(norm_orig, norm_fast)[:20]:
            print('   ', path)
            print('      Original:', old)
            print('      FastAPI :', new)
            print('      Reason  :', reason)
    print()
