import importlib.util
import numpy as np
from pathlib import Path

root = Path.cwd()
source_eval_path = root / '24-06' / 'Credit-Risk-Poc-main' / 'evaluate.py'
main_path = root / '24-06' / 'main.py'

spec = importlib.util.spec_from_file_location('source_eval', source_eval_path)
source_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_eval)

spec2 = importlib.util.spec_from_file_location('backend_main', main_path)
backend_main = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(backend_main)

rng = np.random.RandomState(7)
n = 120
base_prob = np.clip(rng.beta(2, 5, size=n), 0.01, 0.99)
y_true = (rng.rand(n) < base_prob).astype(int)
y_proba = np.column_stack([1 - base_prob, base_prob])
metrics = backend_main.compute_binary_metrics(y_true, (y_proba[:, 1] >= 0.5).astype(int), y_proba, threshold=0.5)

figures = [
    ('ROC', lambda: source_eval.plot_roc_curve(y_true, y_proba), lambda: backend_main.plot_roc_curve(y_true, y_proba)),
    ('PR', lambda: source_eval.plot_pr_curve(y_true, y_proba), lambda: backend_main.plot_pr_curve(y_true, y_proba)),
    ('Confusion Matrix', lambda: source_eval.plot_confusion_matrix(metrics['confusion_matrix']), lambda: backend_main.plot_confusion_matrix(metrics['confusion_matrix'])),
    ('Threshold Analysis', lambda: source_eval.plot_threshold_analysis(y_true, y_proba), lambda: backend_main.plot_threshold_analysis(y_true, y_proba)),
    ('Score Distribution', lambda: source_eval.plot_score_distribution(y_true, y_proba), lambda: backend_main.plot_score_distribution(y_true, y_proba)),
    ('Lift Chart', lambda: source_eval.plot_lift_chart(y_true, y_proba), lambda: backend_main.plot_lift_chart(y_true, y_proba)),
]


def normalize(obj):
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items() if k not in {'uid', 'id'}}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def flatten_title(layout):
    title = layout.get('title')
    if isinstance(title, dict):
        return title.get('text')
    return title


def axis_titles(layout):
    out = {}
    for key in sorted(layout):
        if key.startswith('xaxis') or key.startswith('yaxis'):
            axis = layout[key]
            title_obj = axis.get('title') if isinstance(axis, dict) else None
            if isinstance(title_obj, dict):
                out[key] = title_obj.get('text')
            else:
                out[key] = title_obj
    return out


def annotations(layout):
    return layout.get('annotations') or []


def trace_summary(fig):
    traces = fig.get('data', [])
    names = [t.get('name') for t in traces]
    lengths = []
    for tr in traces:
        for key in ('x', 'y', 'z'):
            val = tr.get(key)
            if val is not None:
                lengths.append(len(val))
                break
        else:
            lengths.append(0)
    return names, lengths


def compare_json(a, b, path='$'):
    diffs = []
    if type(a) != type(b):
        diffs.append((path, a, b, 'type changed'))
        return diffs
    if isinstance(a, dict):
        keys = set(a) | set(b)
        for k in sorted(keys):
            if k not in a:
                diffs.append((path + '.' + k, None, b[k], 'missing in original'))
            elif k not in b:
                diffs.append((path + '.' + k, a[k], None, 'missing in serialized figure'))
            else:
                diffs.extend(compare_json(a[k], b[k], path + '.' + k))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append((path, a, b, 'list length changed'))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diffs.extend(compare_json(x, y, f'{path}[{i}]'))
    elif a != b:
        diffs.append((path, a, b, 'value changed'))
    return diffs

print('PLOTLY FIGURE COMPARISON')
print('========================')
for name, build_original, build_serialized in figures:
    original_fig = build_original().to_dict()
    serialized_fig = build_serialized().to_dict()
    original_norm = normalize(original_fig)
    serialized_norm = normalize(serialized_fig)
    names, lengths = trace_summary(original_fig)

    print(f'FIGURE: {name}')
    print('1. Figure type:', type(original_fig).__name__, '->', type(serialized_fig).__name__)
    print('2. Number of traces:', len(original_fig.get('data', [])), 'vs', len(serialized_fig.get('data', [])))
    print('3. Trace names:', names)
    print('4. Trace lengths:', lengths)
    print('5. Layout title:', flatten_title(original_fig.get('layout', {})), 'vs', flatten_title(serialized_fig.get('layout', {})))
    print('6. Axis titles:', axis_titles(original_fig.get('layout', {})), 'vs', axis_titles(serialized_fig.get('layout', {})))
    print('7. Legend entries:', [t.get('name') for t in original_fig.get('data', [])])
    print('8. Annotation count:', len(annotations(original_fig.get('layout', {}))), 'vs', len(annotations(serialized_fig.get('layout', {}))))

    if original_norm == serialized_norm:
        print('Comparison: identical')
    else:
        print('Comparison: DIFFERENT')
        for path, old, new, reason in compare_json(original_norm, serialized_norm)[:10]:
            print('  -', path)
            print('    Original value:', old)
            print('    New value:     ', new)
            print('    Reason:        ', reason)
    print()
