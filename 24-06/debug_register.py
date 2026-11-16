import json
from persistence import load_model_inventory, register_development_model, APP_DATA_DIR
from pathlib import Path

artifact_path = Path(__file__).resolve().parent / "app_data" / "artifacts" / "dev_pipeline_log" / "training" / "dd875450-325f-4d26-ad1c-c2a72fc432d8.json"
art = json.loads(artifact_path.read_text(encoding='utf-8'))
store = load_model_inventory()
intake = {
    'training_info': art.get('training_info'),
    'evaluation_metrics': art.get('evaluation_metrics'),
    'split_stats': art.get('split_stats'),
    'feature_engineering_summary': art.get('feature_engineering_summary'),
    'real_feature_names': art.get('real_feature_names'),
    'preprocessing_summary': art.get('preprocessing_summary'),
    'encoding': art.get('encoding'),
    'scaling': art.get('scaling'),
    'feature_selection': art.get('feature_selection'),
    'feature_importances': art.get('feature_importances'),
}
dataset = {
    'file_name': 'synthetic',
    'record_count': art.get('split_stats', {}).get('total'),
    'column_count': len(art.get('real_feature_names', [])),
    'numeric_column_count': art.get('numeric_column_count'),
    'categorical_column_count': art.get('categorical_column_count'),
    'missing_value_count': art.get('missing_value_count'),
    'missing_value_pct': art.get('missing_value_pct'),
    'duplicate_record_count': art.get('duplicate_record_count'),
    'class_distribution': art.get('class_distribution'),
}
res = register_development_model(store, art.get('model_name'), art.get('model_name'), intake_payload=intake, dataset_payload=dataset, user='debug')
print('res', res)
import json
p = APP_DATA_DIR / 'model_inventory.json'
print('inv exists', p.exists())
print(json.dumps(json.loads(p.read_text(encoding='utf-8')), indent=2)[:2000])
