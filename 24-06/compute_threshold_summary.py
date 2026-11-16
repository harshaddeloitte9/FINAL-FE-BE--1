import json
with open('tmp_stage3_run.json','r',encoding='utf-8') as f:
    data = json.load(f)
checks = data.get('thresholdChecks', [])
summary = {'total': len(checks), 'pass':0,'warn':0,'fail':0,'pending':0,'na':0}
for c in checks:
    st=(c.get('status') or '').upper()
    if st=='PASS': summary['pass']+=1
    elif st=='WARN': summary['warn']+=1
    elif st=='FAIL': summary['fail']+=1
    elif st in ('N/A','NA'): summary['na']+=1
    else: summary['pending']+=1
print(summary)
