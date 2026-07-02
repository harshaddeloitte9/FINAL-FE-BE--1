"""
diagnose_extract.py — isolate why build_rules.py returns 0 rules.
Run:  python diagnose_extract.py
Uses the real extractor methods, so it matches the build_rules path exactly.
"""
import json
from pathlib import Path
from rule_extractor import RuleExtractor, AGENT_PROMPT, AGENT_URL

print(f"Endpoint: {AGENT_URL}\n")
ex = RuleExtractor()

# 1) network + raw body — a traceback here = VPN/network, not a parse problem
raw = ex._call_agent(AGENT_PROMPT)
print(f"[1] raw response length : {len(raw)} chars")
print(f"[1] first 600 chars:\n{'-'*60}\n{raw[:600]}\n{'-'*60}\n")

# 2) does the rigid format parse?
parsed = ex._parse_agent_rules(raw)
print(f"[2] RULE_START/END blocks parsed : {len(parsed)}")
if parsed:
    print(f"[2] first parsed block: {json.dumps(parsed[0], ensure_ascii=False)}\n")

# 3) how many survive normalisation + in-batch dedup?
norm = ex.extract_from_agent(verbose=True)
print(f"[3] normalised unique rules : {len(norm)}")

# 4) how many are NEW vs already in the store (the dedup that build_rules does)?
store = Path("rag_store/rules.json")
existing = set()
if store.exists():
    existing = {r.get("check", "") for r in json.loads(store.read_text(encoding="utf-8"))}
new = [r for r in norm if r["check"] not in existing]
print(f"[4] already in rules.json : {len(existing)} checks")
print(f"[4] NEW rules this run    : {len(new)}")
if norm and not new:
    print("\n→ Diagnosis: rules parsed fine but ALL already exist. "
          "The store is already populated — this is expected on a re-run, not a failure.")
elif not raw:
    print("\n→ Diagnosis: empty body. The agent likely returns text under a different "
          "JSON key — print `requests.post(...).json().keys()` to find it.")
elif not parsed:
    print("\n→ Diagnosis: body received but no RULE_START/END blocks — the agent ignored "
          "the format. Check the first-600-chars dump above.")
