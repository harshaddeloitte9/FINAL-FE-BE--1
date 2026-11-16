import json
import re
from pathlib import Path

APP = Path(__file__).parent
ARTIFACT_DIR = APP / 'app_data' / 'artifacts' / 'dev_pipeline_log' / 'training'
PDF_PATH = APP / 'app_data' / 'model_reports' / 'DEV_TEST_MODEL_model_report.pdf'
INV_PATH = APP / 'app_data' / 'model_inventory.json'

def find_artifact():
    if not ARTIFACT_DIR.exists():
        return None
    for p in sorted(ARTIFACT_DIR.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        if j.get('model_name') == 'DEV_TEST_MODEL':
            return j
    return None

def load_pdf_text():
    if not PDF_PATH.exists():
        return ''
    b = PDF_PATH.read_bytes()
    return b.decode('latin-1', errors='ignore')

def load_inventory():
    if not INV_PATH.exists():
        return None
    j = json.loads(INV_PATH.read_text(encoding='utf-8'))
    for d in j.get('development', []):
        if d.get('model_name') == 'DEV_TEST_MODEL':
            return d
    return None

artifact = find_artifact()
pdf_text = load_pdf_text()
inv = load_inventory()

def pdf_present(label, val=None):
    if not pdf_text:
        return False
    if label and label in pdf_text:
        return True
    if val is not None:
        try:
            sval = str(val)
            return sval in pdf_text
        except Exception:
            return False
    return False

def extract_pdf_field(regex):
    if not pdf_text:
        return None
    m = re.search(regex, pdf_text)
    if m:
        return m.group(1).strip()
    return None

rows = []

def val_or_none(x):
    return x if x is not None else '<missing>'

# gather values
art = artifact or {}

fields = [
    ('Model ID', "inventory.model_id", inv.get('model_id') if inv else None),
    ('Model Type', 'artifact.task_type', art.get('task_type')),
    ('Model Name', 'artifact.model_name', art.get('model_name')),
    ('Algorithm', 'pdf/metadata', extract_pdf_field(r'Algorithm:\s*([^\)\n]+)') or art.get('algorithm')),
    ('Version', 'pdf/metadata', extract_pdf_field(r'Version:\s*([^\)\n]+)')),
    ('Development Date', 'pdf/metadata', extract_pdf_field(r'Development Date:\s*([^\)\n]+)')),
    ('Status', 'pdf/metadata', extract_pdf_field(r'Development Status:\s*([^\)\n]+)')),
    ('Owner', 'pdf/metadata', extract_pdf_field(r'Owner:\s*([^\)\n]+)')),
    ('Business Unit', 'pdf/metadata', extract_pdf_field(r'Business Unit:\s*([^\)\n]+)')),
    ('Business Purpose', 'pdf/metadata', extract_pdf_field(r'Business Purpose:\s*([^\)\n]+)')),
    ('Intended Use', 'pdf/metadata', extract_pdf_field(r'Intended Use:\s*([^\)\n]+)')),
    ('Portfolio/Product', 'pdf/metadata', extract_pdf_field(r'Portfolio/Product:\s*([^\)\n]+)')),
    ('Target Variable', 'pdf/metadata', extract_pdf_field(r'Target Variable:\s*([^\)\n]+)')),
    ('Target Definition', 'pdf/metadata', extract_pdf_field(r'Target Definition:\s*([^\)\n]+)')),
    ('Scope/Population', 'pdf/metadata', extract_pdf_field(r'Scope / Population:\s*([^\)\n]+)')),
    ('Dataset Name', 'pdf/metadata', extract_pdf_field(r'Dataset:\s*([^\)\n]+)')),
    ('Record Count', 'artifact.split_stats.total', art.get('split_stats',{}).get('total')),
    ('Feature Count', 'len(artifact.real_feature_names)', len(art.get('real_feature_names',[])) if art.get('real_feature_names') else None),
    ('Numeric Columns', 'pdf/metadata', extract_pdf_field(r'Numeric Columns:\s*([^\)\n]+)')),
    ('Categorical Columns', 'pdf/metadata', extract_pdf_field(r'Categorical Columns:\s*([^\)\n]+)')),
    ('Missing Values', 'pdf/metadata', extract_pdf_field(r'Missing Values:\s*([^\)\n]+)')),
    ('Duplicate Records', 'pdf/metadata', extract_pdf_field(r'Duplicate Records:\s*([^\)\n]+)')),
    ('Class Distribution', 'artifact.split_stats.train_class_dist', art.get('split_stats',{}).get('train_class_dist')),
    ('Preprocessing', 'artifact.preprocessing_summary', art.get('preprocessing_summary')),
    ('Feature Engineering', 'artifact.feature_engineering_summary', art.get('feature_engineering_summary')),
    ('Feature Selection', 'artifact.training_info.feature_selection', art.get('training_info',{}).get('feature_selection')),
    ('Encoding', 'artifact.preprocessing_summary.encoding' , None),
    ('Scaling', 'artifact.preprocessing_summary.scaling' , None),
    ('Class Imbalance Treatment', 'artifact.training_info.class_weighting', art.get('training_info',{}).get('class_weighting')),
    ('Hyperparameter Tuning', 'artifact.training_info.best_params', art.get('training_info',{}).get('best_params')),
    ('Train Size', 'artifact.split_stats.train_n', art.get('split_stats',{}).get('train_n')),
    ('Validation Size', 'artifact.split_stats.val_n', art.get('split_stats',{}).get('val_n')),
    ('Test Size', 'artifact.split_stats.test_n', art.get('split_stats',{}).get('test_n')),
    ('Random Seed', 'artifact.training_config.random_seed', art.get('training_config',{}).get('random_seed')),
    ('CV Folds', 'artifact.training_config.cv_folds', art.get('training_config',{}).get('cv_folds')),
    ('ROC-AUC', "artifact.evaluation_metrics.roc_auc", art.get('evaluation_metrics',{}).get('roc_auc')),
    ('PR-AUC', 'artifact.evaluation_metrics.pr_auc', art.get('evaluation_metrics',{}).get('pr_auc')),
    ('Accuracy', 'artifact.evaluation_metrics.accuracy', art.get('evaluation_metrics',{}).get('accuracy')),
    ('Precision', 'artifact.evaluation_metrics.precision', art.get('evaluation_metrics',{}).get('precision')),
    ('Recall', 'artifact.evaluation_metrics.recall', art.get('evaluation_metrics',{}).get('recall')),
    ('F1', 'artifact.evaluation_metrics.f1', art.get('evaluation_metrics',{}).get('f1')),
    ('Gini', 'computed from roc_auc', None),
    ('KS', 'artifact.evaluation_metrics.ks_statistic', art.get('evaluation_metrics',{}).get('ks_statistic')),
    ('Brier Score', 'artifact.evaluation_metrics.brier_score', art.get('evaluation_metrics',{}).get('brier_score')),
    ('Feature Importance', 'artifact.feature_importances', art.get('feature_importances')),
    ('Top Model Drivers', 'artifact.top_model_drivers', art.get('top_model_drivers')),
    ('SHAP/Explainability', 'artifact.shap or explainability artifacts', art.get('shap') or art.get('explainability')),
    ('Assumptions', 'intake payload (not provided)', None),
    ('Limitations', 'intake payload (not provided)', None),
    ('Documentation path', 'pdf path', str(PDF_PATH) if PDF_PATH.exists() else None),
]

print('| Field | Source file/function | Actual value from fresh run | In Inventory? | In PDF? | Status |')
print('|---|---|---|---:|---:|---|')
for name, source, val in fields:
    in_inv = False
    if inv and (name in inv or (isinstance(inv, dict) and inv.get(name.lower().replace(' ','_')) is not None)):
        in_inv = True
    # PDF presence
    in_pdf = False
    # check label or value
    label = name
    if pdf_present(label, val):
        in_pdf = True
    status = 'OK' if val not in (None, [], {}) else 'MISSING'
    print(f'| {name} | {source} | {json.dumps(val, ensure_ascii=False) if val is not None else "<missing>"} | {"Yes" if in_inv else "No"} | {"Yes" if in_pdf else "No"} | {status} |')

print('\nInventory file:', INV_PATH)
print('Training artifact dir:', ARTIFACT_DIR)
print('PDF path:', PDF_PATH)
