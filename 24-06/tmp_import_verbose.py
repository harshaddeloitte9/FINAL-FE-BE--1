import importlib,traceback,sys
importlib.invalidate_caches()
try:
    importlib.import_module('main')
    print('IMPORT OK')
except Exception:
    traceback.print_exc()
    print('\nPYTHONPATH:')
    for p in sys.path:
        print(p)
