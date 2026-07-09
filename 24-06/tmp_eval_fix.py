import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('evaluate_mod', ROOT / 'evaluate.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(hasattr(mod, 'compute_roc_curve'))
print(dir(mod)[:20])
