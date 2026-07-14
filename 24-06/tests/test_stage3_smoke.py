import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure the package path includes the parent (24-06) so `main` can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app

client = TestClient(app)

errors = []

print('Calling GET /validation/intake')
resp = client.get('/validation/intake')
if resp.status_code != 200:
    errors.append(f"GET /validation/intake returned {resp.status_code}")
else:
    print(' OK')

print('Calling POST /validation/agent2')
resp = client.post('/validation/agent2', data={'intake_json': json.dumps({})})
if resp.status_code != 200:
    errors.append(f"POST /validation/agent2 returned {resp.status_code}")
else:
    j = resp.json()
    if 'report' not in j:
        errors.append('POST /validation/agent2 missing report')
    else:
        print(' OK')

print('Calling POST /validation/stage3/run')
resp = client.post('/validation/stage3/run', data={'intake_json': json.dumps({})})
if resp.status_code != 200:
    errors.append(f"POST /validation/stage3/run returned {resp.status_code} - {resp.text}")
else:
    j = resp.json()
    required_keys = [
        'featureRelevance', 'methodologyReview', 'modelAssumptions',
        'documentationChecklist', 'regulatoryAlignment', 'raw_findings',
        'replicated_importances', 'pending_llm_ids', 'llm_ran', 'timestamp'
    ]
    missing = [k for k in required_keys if k not in j]
    if missing:
        errors.append(f"/validation/stage3/run missing keys: {missing}")
    else:
        print(' OK')

print('Calling POST /validation/stage3/llm-check')
resp = client.post('/validation/stage3/llm-check', data={'intake_json': json.dumps({})})
if resp.status_code == 200:
    print(' /validation/stage3/llm-check returned 200 OK')
    try:
        _ = resp.json()
        print(' OK')
    except Exception as e:
        errors.append('POST /validation/stage3/llm-check returned non-json')
else:
    print(f' /validation/stage3/llm-check returned {resp.status_code} — this may be expected if Agent2 is unavailable')

if errors:
    print('\nSMOKE TEST FAILED:')
    for e in errors:
        print(' -', e)
    sys.exit(1)

print('\nSMOKE TEST PASSED')
sys.exit(0)
