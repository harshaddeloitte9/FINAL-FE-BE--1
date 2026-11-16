import json
with open('tmp_stage3_run.json','r',encoding='utf-8') as f:
    data = json.load(f)
combined = data.get('thresholdChecks',[]) + data.get('ragRules',[])
combined_counts = {'total':len(combined),'pass':0,'warn':0,'fail':0,'pending':0,'na':0}
for f in combined:
    st=(f.get('status') or '').upper()
    if st=='PASS': combined_counts['pass']+=1
    elif st=='WARN': combined_counts['warn']+=1
    elif st=='FAIL': combined_counts['fail']+=1
    elif st in ('N/A','NA'): combined_counts['na']+=1
    else: combined_counts['pending']+=1
print('backend combined =>', combined_counts)
# simulate LLM completed: set all ragRules to PASS
for r in data.get('ragRules',[]):
    r['status']='PASS'
combined2 = data.get('thresholdChecks',[]) + data.get('ragRules',[])
combined_counts2 = {'total':len(combined2),'pass':0,'warn':0,'fail':0,'pending':0,'na':0}
for f in combined2:
    st=(f.get('status') or '').upper()
    if st=='PASS': combined_counts2['pass']+=1
    elif st=='WARN': combined_counts2['warn']+=1
    elif st=='FAIL': combined_counts2['fail']+=1
    elif st in ('N/A','NA'): combined_counts2['na']+=1
    else: combined_counts2['pending']+=1
print('backend combined after LLM finishes =>', combined_counts2)
print('frontend threshold-only remains =>', {'total':len(data.get('thresholdChecks',[])),'pass':sum(1 for c in data.get('thresholdChecks',[]) if (c.get('status') or '').upper()=='PASS'),'warn':sum(1 for c in data.get('thresholdChecks',[]) if (c.get('status') or '').upper()=='WARN'),'fail':sum(1 for c in data.get('thresholdChecks',[]) if (c.get('status') or '').upper()=='FAIL')})
