"""
build_rules.py
CLI tool to validate and rebuild rag_store/rules.json.

Usage:
    python build_rules.py               # report on existing rules
    python build_rules.py --extract     # append LLM-extracted rules from documents
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
RAG_STORE_DIR = BASE_DIR / "rag_store"
RULES_PATH = RAG_STORE_DIR / "rules.json"
DOCS_DIR = RAG_STORE_DIR / "documents"


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
    by_source: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    for r in rules:
        k = r.get("source", "?")
        by_source[k] = by_source.get(k, 0) + 1
        k = r.get("severity", "?")
        by_sev[k] = by_sev.get(k, 0) + 1
        k = r.get("stage", "?")
        by_stage[k] = by_stage.get(k, 0) + 1

    print(f"\n📋 Rules summary — {len(rules)} total")
    print(f"  By source   : {by_source}")
    print(f"  By severity : {by_sev}")
    print(f"  By stage    : {by_stage}")


def extract_and_append(rules: list[dict]) -> list[dict]:
    """Run LLM extraction over documents and append novel rules."""
    from rule_extractor import RuleExtractor

    extractor = RuleExtractor()
    existing_checks = {r.get("check", "") for r in rules}
    max_id = max(
        (int(r["id"][1:]) for r in rules if r.get("id", "").startswith("R") and r["id"][1:].isdigit()),
        default=0,
    )
    new_rules: list[dict] = []

    doc_paths = [
        p for p in sorted(DOCS_DIR.rglob("*"))
        if p.suffix.lower() in (".pdf", ".txt", ".md") and not p.is_dir()
    ]

    if not doc_paths:
        print(f"  No documents found in {DOCS_DIR}")
        return rules

    for path in doc_paths:
        print(f"  Extracting from {path.name}…")
        extracted = extractor.extract_from_file(path)
        for rule in extracted:
            check = rule.get("check", "").strip()
            if not check or check in existing_checks:
                continue
            max_id += 1
            rule.setdefault("id", f"R{max_id:02d}")
            rule.setdefault("principle", "?")
            rule.setdefault("threshold", None)
            rule.setdefault("rule", rule.get("rule_text", ""))
            rule.setdefault("flag", rule.get("rule_text", "Rule violation detected"))
            rule.setdefault("suggestion", "Review the relevant regulatory guidance.")
            new_rules.append(rule)
            existing_checks.add(check)

    print(f"  → {len(new_rules)} new rule(s) extracted")
    return rules + new_rules


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and optionally rebuild rag_store/rules.json"
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Run LLM extraction over documents in rag_store/documents/ and append new rules",
    )
    args = parser.parse_args()

    print(f"Rules file : {RULES_PATH}")
    print(f"Docs dir   : {DOCS_DIR}")

    rules = load_rules()
    report(rules)

    if args.extract:
        print("\nRunning LLM-based rule extraction…")
        rules = extract_and_append(rules)
        save_rules(rules)
        report(rules)
    else:
        print("\nTip: run with --extract to append LLM-extracted rules from documents.")


if __name__ == "__main__":
    main()
