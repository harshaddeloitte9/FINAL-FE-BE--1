import importlib.util
spec = importlib.util.spec_from_file_location('persistence','24-06/persistence.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
print('Calling ensure_model_inventory_seed...')
store = p.ensure_model_inventory_seed()
print('Done. Generated/updated reports for', len(store.get('development', [])), 'development models')
