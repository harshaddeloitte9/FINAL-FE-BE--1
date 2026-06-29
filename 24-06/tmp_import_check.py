import importlib,traceback
importlib.invalidate_caches()
try:
    import main
    print('OK')
except Exception:
    traceback.print_exc()
