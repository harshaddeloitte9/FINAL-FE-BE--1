import json
p='tmp_stage3_run.json'
with open(p,'r',encoding='utf-8') as f:
    data=json.load(f)
print('thresholdChecks:', len(data.get('thresholdChecks',[])))
print('ragRules:', len(data.get('ragRules',[])))
print('summary from backend:', data.get('summary'))
print('llm_pending:', data.get('llm_pending'))
print('First threshold statuses:', [c.get('status') for c in data.get('thresholdChecks',[])[:10]])
print('First ragRules statuses:', [r.get('status') for r in data.get('ragRules',[])[:12]])
