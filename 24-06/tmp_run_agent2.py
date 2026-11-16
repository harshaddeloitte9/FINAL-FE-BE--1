from source_agent2 import Agent2
import traceback

agent = Agent2(rules_path='24-06/rag_store/val_mdd_rules.json')
print('Loaded rules:', len(agent.rules))
try:
    docs = {'MDD': 'This is a short sample MDD describing model purpose and selection rationale.'}
    res = agent.check_documents_with_llm(docs, stage='conceptual_soundness')
    print('Result count:', len(res))
    for r in res[:5]:
        print(r)
except Exception as e:
    print('EXC', e)
    traceback.print_exc()
