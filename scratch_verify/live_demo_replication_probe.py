import json
import pathlib
import requests

csv_path = pathlib.Path(r"C:\Users\adeha\Downloads\Final UI 2_backup\24-06\demo_data\clean_portfolio.csv")
csv_text = csv_path.read_text(encoding="utf-8")
payload = {
    "model_name": "Demo A — demonstration dataset",
    "algorithm": "Demo workflow (illustrative)",
    "target_col": "default",
    "csv_text": csv_text,
    "seeds": "42,43,44,45,46",
    "test_size": "0.15",
    "val_size": "0.15",
    "random_seed": "42",
    "cv_folds": "5",
}
response = requests.post("http://127.0.0.1:8001/validation/replication", data=payload, timeout=120)
print(response.status_code)
print(response.text[:4000])
