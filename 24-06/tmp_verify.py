import json
from pathlib import Path

APP = Path(__file__).parent
inv = json.loads((APP / 'app_data' / 'model_inventory.json').read_text(encoding='utf-8'))
entry = None
for d in inv.get('development', []):
    if d.get('model_name') == 'DEV_TEST_MODEL':
        entry = d
        break
if not entry:
    print('No entry found')
    raise SystemExit(1)

pdf_path = APP / entry.get('documentation_path') if entry.get('documentation_path') else None
pdf_text = ''
if pdf_path and pdf_path.exists():
    raw = pdf_path.read_bytes()
    try:
        pdf_text = raw.decode('latin-1')
    except Exception:
        pdf_text = str(raw[:200])

fields = [
    ('Model ID', 'model_id', 'persistence.next_model_id -> register_development_model (persistence.py)'),
    ('Model Type', 'model_type', 'main.train_model_endpoint (Form -> intake_payload:model_type)'),
    ('Development Date', 'development_date', 'main.train_model_endpoint (Form -> intake_payload:development_date)'),
    ('Owner', 'model_owner', 'main.train_model_endpoint (Form -> intake_payload:model_owner)'),
    ('Business Unit', 'business_unit', 'main.train_model_endpoint (Form -> intake_payload:business_unit)'),
    ('Purpose', 'business_purpose', 'main.train_model_endpoint (Form -> intake_payload:model_purpose)'),
    ('Intended Use', 'intended_use', 'intake payload field (not provided in train endpoint)'),
    ('Portfolio/Product', 'portfolio', 'intake payload field (not provided in train endpoint)'),
    ('Target Variable', 'dataset_target_variable', 'dataset_payload.target_variable (main.train_model_endpoint)'),
    ('Target Definition', 'target_definition', 'not provided by train endpoint'),
    ('Scope/Population', 'scope', 'intake payload field (not provided in train endpoint)'),
    ('Dataset', 'dataset_name', 'dataset_payload.file_name (main.train_model_endpoint)'),
    ('Record Count', 'dataset_record_count', 'dataset_payload.record_count (main.train_model_endpoint)'),
    ('Feature Count', 'real_feature_names', 'train_model.train_model -> real_feature_names returned'),
    ('Numeric Columns', 'numeric_column_count', 'dataset_payload.numeric_column_count (main.train_model_endpoint)'),
    ('Categorical Columns', 'categorical_column_count', 'dataset_payload.categorical_column_count (main.train_model_endpoint)'),
    ('Missing Values', 'missing_value_count', 'dataset_payload.missing_value_count (main.train_model_endpoint)'),
    ('Duplicate Records', 'duplicate_record_count', 'dataset_payload.duplicate_record_count (main.train_model_endpoint)'),
    ('Class Distribution', 'class_distribution', 'dataset_payload.class_distribution (main.train_model_endpoint)'),
    ('Preprocessing', 'preprocessing_summary', 'prep_report from build_preprocessing_report (main.train_model_endpoint)'),
    ('Feature Engineering', 'feature_engineering_summary', 'analyze_for_feature_engineering/apply_feature_engineering (main.train_model_endpoint)'),
    ('Feature Selection', 'training_info.feature_selection', 'feature engineering plan -> feature_selection (main.train_model_endpoint)'),
    ('Encoding', 'encoding', 'main.train_model_endpoint collects from prep_report'),
    ('Scaling', 'scaling', 'main.train_model_endpoint collects from prep_report'),
    ('Class Imbalance Treatment', 'training_info.class_weighting', 'train_new.train_model sets class_weighting (train_new.py)'),
    ('Hyperparameter Tuning', 'training_info.best_params', 'train_new or main.train_model_endpoint use_hyperopt'),
    ('Train/Validation/Test sizes', 'split_stats', 'split_data (main.train_model_endpoint)'),
    ('Random Seed', 'training_config.random_seed', 'Form random_seed in main.train_model_endpoint'),
    ('CV Folds', 'training_config.cv_folds', 'Form cv_folds in main.train_model_endpoint'),
    ('Evaluation Metrics', 'evaluation_metrics', 'evaluation in main.train_model_endpoint'),
    ('Feature Importance', 'feature_importances', 'extract_feature_importance(pipeline) in main.train_model_endpoint'),
    ('Explainability/SHAP', 'shap', 'explainability endpoint or apply_latest_explainability_to_last_registered_model (persistence.py)'),
    ('Assumptions', 'assumptions', 'intake_payload field (not provided)'),
    ('Limitations', 'limitations', 'intake_payload field (not provided)'),
]

rows = []
for display, key, source in fields:
    # support nested keys like training_info.class_weighting
    if '.' in key:
        parts = key.split('.')
        val = entry
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                val = None
                break
    else:
        val = entry.get(key)

    # For real_feature_names we want count
    if key == 'real_feature_names' and isinstance(val, (list, tuple)):
        actual_value = len(val)
    else:
        actual_value = val

    persisted = (val is not None)

    # PDF presence: check for either the display label or the stringified value
    present_in_pdf = False
    if pdf_text:
        if display in pdf_text:
            present_in_pdf = True
        else:
            try:
                sval = str(actual_value)
                if sval and sval in pdf_text:
                    present_in_pdf = True
            except Exception:
                present_in_pdf = False

    rows.append((display, source, actual_value, persisted, present_in_pdf))

# Print table
print('| Field | Source | Actual value (this run) | Persisted in inventory? | Present in PDF? |')
print('|---|---|---|---:|---:|')
for r in rows:
    disp, src, val, persisted, pdfp = r
    print(f'| {disp} | {src} | {json.dumps(val, ensure_ascii=False) if val is not None else "<missing>"} | {"Yes" if persisted else "No"} | {"Yes" if pdfp else "No"} |')

print('\nInventory entry path:', APP / 'app_data' / 'model_inventory.json')
print('PDF path:', pdf_path)