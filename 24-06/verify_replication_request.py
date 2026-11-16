import pathlib
import requests
url='http://127.0.0.1:8001/validation/replication'
csv_text=pathlib.Path('sample.csv').read_text(encoding='utf-8')
data={'algorithm':'XGBoost','model_name':'PD_Model_Internal_v1','target_col':'loan_status','csv_text':csv_text,'seeds':'42,43,44,45,46','test_size':'0.15','val_size':'0.15','random_seed':'42','cv_folds':'5'}
r=requests.post(url, data=data, timeout=1800)
print('status', r.status_code)
print(r.text[:4000])
