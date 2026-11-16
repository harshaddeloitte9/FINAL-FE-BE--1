from pathlib import Path
import json
from persistence import _update_latest_training_artifact_with_model_id, load_model_inventory

last=Path('app_data/last_development_registered.json')
if not last.exists():
    print('no last_development_registered.json')
    raise SystemExit(1)

j=json.loads(last.read_text(encoding='utf-8'))
model_name=j.get('model_name')
model_id=j.get('model_id')
inv=load_model_inventory()
entry=next((d for d in inv.get('development',[]) if d.get('model_id')==model_id),None)
doc=entry.get('documentation_path') if entry else None
print('Calling updater with', model_name, model_id, doc)
res=_update_latest_training_artifact_with_model_id(model_name, model_id, documentation_path=doc)
print('Updater result:', res)
