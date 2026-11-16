from llm_providers import complete_with_fallback
import traceback

try:
    res = complete_with_fallback('hello')
    completion, provider = res
    print('OK provider=', provider)
    print('completion snippet=', repr(completion[:200]))
except Exception as e:
    print('EXC', type(e).__name__, str(e))
    traceback.print_exc()
