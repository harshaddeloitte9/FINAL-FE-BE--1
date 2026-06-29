"""
Compare the original and current feature_engineering.py files line by line
"""
import difflib

with open("../Credit-Risk-Poc-main/feature_engineering.py", "r") as f:
    original = f.readlines()

with open("feature_engineering.py", "r") as f:
    current = f.readlines()

# Find differences
diff = difflib.unified_diff(original, current, fromfile="original", tofile="current", lineterm='')

print("DIFFERENCES BETWEEN ORIGINAL AND CURRENT FEATURE_ENGINEERING.PY:")
print("="*100)

count = 0
for line in diff:
    print(line)
    count += 1
    if count > 200:  # Limit output
        print(f"\n[... {count} more lines ...]")
        break

if count == 0:
    print("\n✓ Files are IDENTICAL")
