import sys
import inspect

# Test what's being imported
sys.path.insert(0, "../Credit-Risk-Poc-main")
import feature_engineering as fe_orig

print("Original apply_feature_engineering signature:")
print(inspect.signature(fe_orig.apply_feature_engineering))

sys.path = [p for p in sys.path if "Credit-Risk-Poc-main" not in p]
sys.path.insert(0, ".")

# Force reload
if 'feature_engineering' in sys.modules:
    del sys.modules['feature_engineering']

import feature_engineering as fe_curr

print("\nCurrent apply_feature_engineering signature:")
print(inspect.signature(fe_curr.apply_feature_engineering))
