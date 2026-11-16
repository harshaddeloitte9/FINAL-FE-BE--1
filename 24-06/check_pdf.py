from pathlib import Path
p=Path('24-06/app_data/model_reports/DEV_TEST_MODEL_model_report.pdf')
if not p.exists():
    print('MISSING')
else:
    b=p.read_bytes()
    print('EXISTS')
    print('has Model ID line:', b.find(b'Model ID:')!=-1)
    print('has MOD-002:', b.find(b'MOD-002')!=-1)
