import json
from pathlib import Path
import persistence

art = Path(__file__).resolve().parent / 'app_data' / 'artifacts' / 'dev_pipeline_log' / 'training' / '1fa86755-721e-43c3-95b0-1fecae2edfc7.json'
print('artifact exists', art.exists())
obj = json.loads(art.read_text(encoding='utf-8'))
print('artifact model_name', obj.get('model_name'))

store = persistence.load_model_inventory()
res = persistence.register_development_model(
    store=store,
    business_model_name=obj.get('model_name'),
    estimator_name=obj.get('algorithm'),
    intake_payload={
        'model_owner': obj.get('training_info', {}).get('owner') if isinstance(obj.get('training_info'), dict) else None,
        'model_version': obj.get('training_config', {}).get('model_version') if isinstance(obj.get('training_config'), dict) else None,
        'model_purpose': obj.get('model_purpose') or None,
        'development_date': obj.get('development_date') or None,
        'status': obj.get('status') or None,
        'training_info': obj.get('training_info'),
        'evaluation_metrics': obj.get('evaluation_metrics') or obj.get('evaluation_metrics') or obj.get('evaluation_metrics'),
        'preprocessing_summary': obj.get('preprocessing_summary'),
        'feature_engineering_summary': obj.get('feature_engineering_summary'),
        'feature_importances': obj.get('feature_importances'),
        'top_model_drivers': obj.get('top_model_drivers'),
        'training_config': obj.get('training_config'),
    },
    dataset_payload={
        'file_name': obj.get('dataset_name') or 'uploaded_dataset',
        'storage_reference': obj.get('dataset_name') or '',
        'record_count': obj.get('numeric_column_count'),
        'column_count': obj.get('dataset_column_count'),
        'numeric_column_count': obj.get('numeric_column_count'),
        'categorical_column_count': obj.get('categorical_column_count'),
        'missing_value_count': obj.get('missing_value_count'),
        'missing_value_pct': obj.get('missing_value_pct'),
        'duplicate_record_count': obj.get('duplicate_record_count'),
        'class_distribution': obj.get('class_distribution'),
    },
    user='debug_test'
)
print('register result', res)
persistence.save_model_inventory(store)
print('inventory saved')
