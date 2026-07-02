"""
build_rules.py
CLI tool to rebuild rag_store/val_mdd_rules.json from the hosted RAG agent.

This replaces the old development-pipeline build_rules.py. Rules are now
exclusively MDD documentation requirements for model validation (SS1/23,
IFRS 9) — not quantitative data checks.

Usage:
    python build_rules.py               # report on existing rules
    python build_rules.py --extract     # pull rules from the agent and append
    python build_rules.py --reset       # wipe and reseed from curated baseline
    python build_rules.py --extract --reset   # full rebuild from scratch

The JSON is consumed by the model-validation pipeline in app.py for
keyword-search cross-checking against an uploaded MDD.
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR      = Path(__file__).resolve().parent
RAG_STORE_DIR = BASE_DIR / "rag_store"
RULES_PATH    = RAG_STORE_DIR / "val_mdd_rules.json"


def load_rules() -> list[dict]:
    if not RULES_PATH.exists():
        print(f"[build_rules] {RULES_PATH} not found — starting from empty list.")
        return []
    with RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_rules(rules: list[dict]) -> None:
    RAG_STORE_DIR.mkdir(parents=True, exist_ok=True)
    with RULES_PATH.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(rules)} rules → {RULES_PATH}")


def report(rules: list[dict]) -> None:
    by_source:   dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_stage:    dict[str, int] = {}
    for r in rules:
        for key, d in (("source", by_source), ("severity", by_severity), ("stage", by_stage)):
            k = r.get(key, "?")
            d[k] = d.get(k, 0) + 1

    print(f"\n📋 MDD Validation Rules — {len(rules)} total")
    print(f"  By source   : {by_source}")
    print(f"  By severity : {by_severity}")
    print(f"  By stage    : {by_stage}")

    no_kw = [r.get("id", "?") for r in rules if not r.get("keywords")]
    if no_kw:
        print(f"\n⚠️  {len(no_kw)} rule(s) have no keywords (keyword search will mark them WARN): {no_kw[:10]}")


def extract_and_append(rules: list[dict], verbose: bool = False) -> list[dict]:
    """Query the RAG agent and append novel MDD documentation rules."""
    from rule_extractor import RuleExtractor

    extractor = RuleExtractor()
    existing_checks = {r.get("check", "") for r in rules}
    max_id = max(
        (int(r["id"][1:]) for r in rules if r.get("id", "").startswith("V") and r["id"][1:].isdigit()),
        default=0,
    )

    print("  Querying agent for MDD documentation requirements…")
    extracted = extractor.extract_from_agent(verbose=verbose)

    new_rules: list[dict] = []
    for rule in extracted:
        check = rule.get("check", "").strip()
        if not check or check in existing_checks:
            continue
        max_id += 1
        rule["id"] = f"V{max_id:02d}"
        rule.setdefault("min_keyword_hits", 2)
        new_rules.append(rule)
        existing_checks.add(check)

    print(f"  → {len(new_rules)} new rule(s) extracted")
    return rules + new_rules


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild rag_store/val_mdd_rules.json from the RAG agent"
    )
    parser.add_argument("--extract", action="store_true",
                        help="Query the agent and append new rules")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe existing rules and reseed from val_build_rules.py baseline before extracting")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-stage extraction details")
    args = parser.parse_args()

    print(f"Rules file : {RULES_PATH}")

    if args.reset:
        from val_build_rules import seed_rules
        print("\n⚠️  --reset: rebuilding from curated seed rules.")
        rules = seed_rules()
        save_rules(rules)
    else:
        rules = load_rules()
        if not rules:
            from val_build_rules import seed_rules
            print("\nNo existing rules — seeding with curated baseline.")
            rules = seed_rules()
            save_rules(rules)

    report(rules)

    if args.extract:
        print("\nRunning agent-based rule extraction…")
        rules = extract_and_append(rules, verbose=args.verbose)
        save_rules(rules)
        report(rules)
    else:
        print("\nTip: run with --extract to append rules from the RAG agent.")


if __name__ == "__main__":
    main()
