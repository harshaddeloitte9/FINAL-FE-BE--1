import json
import os
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
APP_DATA = BASE / 'app_data'
ARTIFACTS = APP_DATA / 'artifacts'
MODEL_INVENTORY = APP_DATA / 'model_inventory.json'
PDF_PATH = APP_DATA / 'model_reports' / 'DEV_TEST_MODEL_model_report.pdf'
TARGET_ID = 'MOD-002'
TARGET_NAME = 'DEV_TEST_MODEL'

def load_inventory():
    data = json.loads(MODEL_INVENTORY.read_text(encoding='utf-8'))
    # find development entry with model_id or model_name
    dev = None
    for item in data.get('development', []):
        if not isinstance(item, dict):
            continue
        if str(item.get('model_id') or '') == TARGET_ID or str(item.get('model_name') or '') == TARGET_NAME:
            dev = item
            break
    return dev


def find_artifact():
    # look for JSON files under ARTIFACTS that contain the TARGET_NAME or TARGET_ID
    for root, dirs, files in os.walk(ARTIFACTS):
        for f in files:
            if not f.lower().endswith('.json'):
                continue
            p = Path(root) / f
            try:
                txt = p.read_text(encoding='utf-8')
            except Exception:
                continue
            if TARGET_NAME in txt or TARGET_ID in txt or 'training_info' in txt:
                # try parse
                try:
                    j = json.loads(txt)
                except Exception:
                    continue
                # Heuristic: return artifact with training_info or split_stats
                if isinstance(j, dict) and ('training_info' in j or 'split_stats' in j or 'evaluation_metrics' in j):
                    return p, j
    return None, None


def extract_pdf_text(pdf_path):
    text = ''
    # try pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        for p in reader.pages:
            try:
                text += p.extract_text() or ''
            except Exception:
                pass
        return text
    except Exception:
        pass
    # try PyPDF2
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(str(pdf_path))
        for p in reader.pages:
            try:
                text += p.extract_text() or ''
            except Exception:
                pass
        return text
    except Exception:
        pass
    # try fitz (PyMuPDF)
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        for page in doc:
            text += page.get_text()
        return text
    except Exception:
        pass
    return None


def find_label_value(text, label_patterns):
    # label_patterns: list of regex patterns (case-insensitive) that capture value in group 1
    for pat in label_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


if __name__ == '__main__':
    inv = load_inventory()
    print('--- Development Inventory Entry ---')
    if not inv:
        print('Development inventory entry not found for', TARGET_ID, TARGET_NAME)
    else:
        keys = ['model_id','model_name','algorithm','model_owner','business_unit','model_version','development_date','status','business_purpose','documentation_path']
        for k in keys:
            print(f'{k}:', json.dumps(inv.get(k), ensure_ascii=False))
        print('\n-- dataset metadata --')
        for k in ['dataset_name','dataset_target_variable','dataset_record_count','dataset_column_count','numeric_column_count','categorical_column_count','missing_value_count','missing_value_pct','duplicate_record_count','class_distribution']:
            print(f'{k}:', json.dumps(inv.get(k), ensure_ascii=False))
        print('\n-- training metadata --')
        print(json.dumps(inv.get('training_info'), ensure_ascii=False, indent=2) if inv.get('training_info') else None)
        print('\n-- evaluation metrics --')
        print(json.dumps(inv.get('evaluation_metrics'), ensure_ascii=False, indent=2) if inv.get('evaluation_metrics') else None)
        print('\n-- explainability metadata --')
        explain = {k: inv.get(k) for k in ['feature_importances','top_model_drivers','shap','preprocessing_summary']}
        print(json.dumps(explain, ensure_ascii=False, indent=2))

    art_path, art = find_artifact()
    print('\n--- Training Artifact ---')
    if art is None:
        print('No training artifact found')
    else:
        print('artifact_path:', art_path)
        # Print key fields
        print('model_name:', art.get('model_name') or art.get('business_model_name') or art.get('business_model') )
        # dataset
        print('dataset_name:', art.get('dataset_name') or art.get('dataset') or art.get('dataset_name'))
        print('dataset_record_count:', art.get('split_stats',{}).get('total') or art.get('dataset_record_count'))
        print('real_feature_names_count:', len(art.get('real_feature_names') or []))
        print('training_info:', json.dumps(art.get('training_info'), ensure_ascii=False, indent=2) if art.get('training_info') else None)
        print('evaluation_metrics:', json.dumps(art.get('evaluation_metrics'), ensure_ascii=False, indent=2) if art.get('evaluation_metrics') else None)
        print('split_stats:', json.dumps(art.get('split_stats'), ensure_ascii=False, indent=2) if art.get('split_stats') else None)

    print('\n--- Extracting PDF text ---')
    if not PDF_PATH.exists():
        print('PDF not found at', PDF_PATH)
        pdf_text = None
    else:
        pdf_text = extract_pdf_text(PDF_PATH)
        if pdf_text is None:
            print('No PDF text extractor available (pypdf/PyPDF2/PyMuPDF missing)')
        else:
            print('--- PDF text start ---')
            print(pdf_text)
            print('--- PDF text end ---')

    # Now do comparisons for table
    def get_from_inventory(field):
        if not inv:
            return None
        mapping = {
            'Model ID': inv.get('model_id'),
            'Model Name': inv.get('model_name'),
            'Algorithm': inv.get('algorithm'),
            'Owner': inv.get('model_owner'),
            'Business Unit': inv.get('business_unit'),
            'Version': inv.get('model_version'),
            'Development Date': inv.get('development_date'),
            'Status': inv.get('status'),
            'Purpose': inv.get('business_purpose'),
            'Dataset': inv.get('dataset_name'),
            'Record Count': inv.get('dataset_record_count'),
            'Feature Count': len(inv.get('real_feature_names') or []) if inv.get('real_feature_names') else inv.get('dataset_column_count'),
            'Train Size': (inv.get('training_info') or {}).get('train_size') or (inv.get('split_stats') or {}).get('train_n'),
            'Validation Size': (inv.get('training_info') or {}).get('val_size') or (inv.get('split_stats') or {}).get('val_n'),
            'Test Size': (inv.get('training_info') or {}).get('test_size') or (inv.get('split_stats') or {}).get('test_n'),
            'Random Seed': (inv.get('training_info') or {}).get('random_seed'),
            'CV Folds': (inv.get('training_info') or {}).get('cv_folds'),
            'ROC-AUC': (inv.get('evaluation_metrics') or {}).get('roc_auc'),
            'PR-AUC': (inv.get('evaluation_metrics') or {}).get('pr_auc'),
            'Accuracy': (inv.get('evaluation_metrics') or {}).get('accuracy'),
            'Precision': (inv.get('evaluation_metrics') or {}).get('precision'),
            'Recall': (inv.get('evaluation_metrics') or {}).get('recall'),
            'F1': (inv.get('evaluation_metrics') or {}).get('f1'),
            'KS': (inv.get('evaluation_metrics') or {}).get('ks_statistic'),
            'Brier Score': (inv.get('evaluation_metrics') or {}).get('brier_score'),
            'Class Distribution': inv.get('class_distribution'),
            'Preprocessing': (inv.get('preprocessing_summary') or {}).get('numeric') if inv.get('preprocessing_summary') else None,
            'Feature Engineering': inv.get('feature_engineering_summary'),
            'Feature Selection': (inv.get('training_info') or {}).get('feature_selection'),
            'Feature Importance': inv.get('feature_importances'),
            'SHAP': inv.get('shap'),
        }
        return mapping.get(field)

    def get_from_artifact(field):
        if art is None:
            return None
        mapping = {
            'Model ID': art.get('model_id'),
            'Model Name': art.get('model_name') or art.get('business_model_name'),
            'Algorithm': art.get('algorithm'),
            'Owner': art.get('model_owner') or art.get('user'),
            'Business Unit': art.get('business_unit'),
            'Version': art.get('model_version'),
            'Development Date': art.get('development_date'),
            'Status': art.get('status'),
            'Purpose': art.get('business_purpose') or art.get('model_purpose'),
            'Dataset': art.get('dataset_name') or art.get('dataset'),
            'Record Count': (art.get('split_stats') or {}).get('total') or art.get('dataset_record_count'),
            'Feature Count': len(art.get('real_feature_names') or []) if art.get('real_feature_names') else art.get('dataset_column_count'),
            'Train Size': (art.get('split_stats') or {}).get('train_n') or (art.get('training_info') or {}).get('train_size'),
            'Validation Size': (art.get('split_stats') or {}).get('val_n') or (art.get('training_info') or {}).get('val_size'),
            'Test Size': (art.get('split_stats') or {}).get('test_n') or (art.get('training_info') or {}).get('test_size'),
            'Random Seed': (art.get('training_info') or {}).get('random_seed'),
            'CV Folds': (art.get('training_info') or {}).get('cv_folds'),
            'ROC-AUC': (art.get('evaluation_metrics') or {}).get('roc_auc'),
            'PR-AUC': (art.get('evaluation_metrics') or {}).get('pr_auc'),
            'Accuracy': (art.get('evaluation_metrics') or {}).get('accuracy'),
            'Precision': (art.get('evaluation_metrics') or {}).get('precision'),
            'Recall': (art.get('evaluation_metrics') or {}).get('recall'),
            'F1': (art.get('evaluation_metrics') or {}).get('f1'),
            'KS': (art.get('evaluation_metrics') or {}).get('ks_statistic'),
            'Brier Score': (art.get('evaluation_metrics') or {}).get('brier_score'),
            'Class Distribution': art.get('class_distribution') or (art.get('split_stats') or {}).get('train_class_dist'),
            'Preprocessing': art.get('preprocessing_summary'),
            'Feature Engineering': art.get('feature_engineering_summary'),
            'Feature Selection': (art.get('training_info') or {}).get('feature_selection'),
            'Feature Importance': art.get('feature_importances') or art.get('feature_ranking'),
            'SHAP': art.get('shap'),
        }
        return mapping.get(field)

    def get_from_pdf(field, pdf_text):
        if not pdf_text:
            return None
        # mapping labels to regex
        label_map = {
            'Model ID': [r'Model ID:\s*(.+)'],
            'Model Name': [r'Model Name:\s*(.+)'],
            'Algorithm': [r'Algorithm:\s*(.+)'],
            'Owner': [r'Owner:\s*(.+)'],
            'Business Unit': [r'Business Unit:\s*(.+)'],
            'Version': [r'Version:\s*(.+)'],
            'Development Date': [r'Development Date:\s*(.+)'],
            'Status': [r'Development Status:\s*(.+)', r'Status:\s*(.+)'],
            'Purpose': [r'Business Purpose:\s*(.+)'],
            'Dataset': [r'Dataset:\s*(.+)'],
            'Record Count': [r'Dataset Record Count:\s*(.+)', r'Records:\s*(.+)'],
            'Feature Count': [r'Number of final features:\s*(.+)', r'Features:\s*(\d+)'],
            'Train Size': [r'Train Size:\s*(.+)'],
            'Validation Size': [r'Validation Size:\s*(.+)'],
            'Test Size': [r'Test Size:\s*(.+)'],
            'Random Seed': [r'Random Seed:\s*(.+)'],
            'CV Folds': [r'CV Folds:\s*(.+)'],
            'ROC-AUC': [r'Roc Auc:\s*(.+)', r'Roc Auc:\s*(.+)'],
            'PR-AUC': [r'Pr Auc:\s*(.+)', r'Pr-Auc:\s*(.+)', r'Pr Auc:\s*(.+)'],
            'Accuracy': [r'Accuracy:\s*(.+)'],
            'Precision': [r'Precision:\s*(.+)'],
            'Recall': [r'Recall:\s*(.+)'],
            'F1': [r'F1:\s*(.+)'],
            'KS': [r'Ks:\s*(.+)', r'Ks Statistic:\s*(.+)', r'Ks Statistic:\s*(.+)'],
            'Brier Score': [r'Brier Score:\s*(.+)'],
            'Class Distribution': [r'Class Distribution:\s*(.+)'],
            'Preprocessing': [r'Preprocessing:\s*(.+)'],
            'Feature Engineering': [r'Feature Engineering:\s*(.+)'],
            'Feature Selection': [r'Feature Selection:\s*(.+)'],
            'Feature Importance': [r'Top model drivers:\s*(.+)', r'Feature list.*\n(.+)'],
            'SHAP': [r'SHAP values available', r'Shap', r'SHAP'],
        }
        pats = label_map.get(field)
        if not pats:
            return None
        for pat in pats:
            v = find_label_value(pdf_text, [pat])
            if v:
                return v
        # special: for SHAP presence
        if field == 'SHAP' and ('SHAP' in pdf_text or 'Shap' in pdf_text):
            return True
        return None

    fields = ['Model ID','Model Name','Algorithm','Owner','Business Unit','Version','Development Date','Status','Purpose','Dataset','Record Count','Feature Count','Train Size','Validation Size','Test Size','Random Seed','CV Folds','ROC-AUC','PR-AUC','Accuracy','Precision','Recall','F1','KS','Brier Score','Class Distribution','Preprocessing','Feature Engineering','Feature Selection','Feature Importance','SHAP']

    # header
    print('\n| Field | Training Artifact | Development Inventory | PDF | Match? |')
    print('|---|---|---|---|---|')
    for f in fields:
        a = get_from_artifact(f)
        i = get_from_inventory(f)
        p = get_from_pdf(f, pdf_text)
        # normalize simple types to strings
        def norm(x):
            if x is None:
                return ''
            if isinstance(x, (dict, list)):
                try:
                    return json.dumps(x, ensure_ascii=False)
                except Exception:
                    return str(x)
            return str(x)
        match = 'YES' if (a is not None and i is not None and p is not None and str(a)==str(i)==str(p)) else 'NO'
        print('| %s | %s | %s | %s | %s |' % (f, norm(a), norm(i), norm(p), match))

    # Summaries A-D
    print('\nA. Fields fully end-to-end correct (exact match across artifact, inventory, PDF):')
    correct = [f for f in fields if (get_from_artifact(f) is not None and get_from_inventory(f) is not None and get_from_pdf(f, pdf_text) is not None and str(get_from_artifact(f))==str(get_from_inventory(f))==str(get_from_pdf(f, pdf_text)))]
    print(json.dumps(correct, ensure_ascii=False, indent=2))

    print('\nB. Fields present in training artifact but missing from Inventory:')
    b_list = [f for f in fields if get_from_artifact(f) is not None and get_from_inventory(f) is None]
    print(json.dumps(b_list, ensure_ascii=False, indent=2))

    print('\nC. Fields present in Inventory but missing from PDF:')
    c_list = [f for f in fields if get_from_inventory(f) is not None and get_from_pdf(f, pdf_text) is None]
    print(json.dumps(c_list, ensure_ascii=False, indent=2))

    print('\nD. Fields not generated anywhere by the Development pipeline (artifact nor inventory):')
    d_list = [f for f in fields if get_from_artifact(f) is None and get_from_inventory(f) is None]
    print(json.dumps(d_list, ensure_ascii=False, indent=2))
