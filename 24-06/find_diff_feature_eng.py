"""
Find all meaningful differences between the two feature_engineering.py files
"""
import difflib

with open("../Credit-Risk-Poc-main/feature_engineering.py", "r") as f:
    original_lines = f.readlines()

with open("./feature_engineering.py", "r") as f:
    current_lines = f.readlines()

# Use unified_diff to find differences
diff = list(difflib.unified_diff(original_lines, current_lines, fromfile='original', tofile='current', n=3))

if not diff:
    print("✓ Files are identical")
else:
    print(f"Files differ ({len(diff)} lines of diff)\n")
    
    # Filter to meaningful changes (not just whitespace)
    significant = []
    for line in diff:
        if line.startswith('+') or line.startswith('-'):
            if line.strip() not in ['+++', '---', '+', '-']:
                # Skip import lines and pure whitespace changes
                if 'import' not in line and line.strip():
                    significant.append(line)
    
    print(f"Significant changes ({len(significant)} lines):\n")
    print("".join(diff[:100]))  # Print first 100 lines of diff
