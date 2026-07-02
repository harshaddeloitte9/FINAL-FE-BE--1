"""
agent2.py
Model-validation compliance checker.

Loads MDD documentation rules from rag_store/val_mdd_rules.json and provides:
  - check_for_validation()  : quantitative rules cross-checked against dataset metrics
  - check_mdd_keywords()    : keyword-search cross-check of rules against uploaded MDD text
  - get_attestation_checklist() : descriptive rules for manual reviewer sign-off

The model-development pipeline (data/feature/training/evaluation stages) no
longer uses this class — it has been removed. All compliance logic is now
focused on model validation only.
"""

import json
import re
from pathlib import Path
from typing import Any


class Agent2:
    def __init__(self, rules_path: str = "rag_store/val_mdd_rules.json"):
        path = Path(rules_path)
        if not path.exists():
            # Graceful degradation — validation UI still renders without rules
            self.rules: list[dict] = []
        else:
            with path.open(encoding="utf-8") as f:
                self.rules = json.load(f)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve_field(self, field_hint: str, context_dict: dict) -> Any:
        """Dot-notation field resolver: 'missing_rate' → context_dict['missing_rate']."""
        if not field_hint:
            return None
        if field_hint in context_dict:
            return context_dict[field_hint]
        parts = field_hint.split(".")
        obj: Any = context_dict
        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return None
        return obj

    def _apply_operator(self, value: Any, operator: str, threshold: Any) -> bool:
        """Return True if the check PASSES (no flag needed)."""
        try:
            if operator == ">=":   return float(value) >= float(threshold)
            if operator == "<=":   return float(value) <= float(threshold)
            if operator == ">":    return float(value) >  float(threshold)
            if operator == "<":    return float(value) <  float(threshold)
            if operator == "==":   return value == threshold
            if operator == "!=":   return value != threshold
            if operator == "is_true":    return bool(value)
            if operator == "is_false":   return not bool(value)
            if operator == "is_present": return value is not None
        except (TypeError, ValueError):
            pass
        return True  # unknown operator → don't flag

    # ── Quantitative validation checks ───────────────────────────────────────

    def check_for_validation(self, stage: str, context_dict: dict) -> list[dict]:
        """
        Evaluate machine-testable rules (checkable_against_data=True) for a
        model-validation stage against supplied dataset metrics.

        Returns findings shaped for the app.py render loop:
          {check_id, title, severity, status, source, principle, observed, threshold, detail}
        """
        findings: list[dict] = []
        for rule in self.rules:
            if rule.get("stage") not in (stage, self._map_stage(stage)):
                continue
            if not rule.get("checkable_against_data", False):
                continue
            logic = rule.get("logic")
            if not logic or not isinstance(logic, dict):
                continue
            field_hint = logic.get("field_hint", "")
            if not field_hint:
                continue
            value = self._resolve_field(field_hint, context_dict)
            if value is None:
                continue
            passed = self._apply_operator(value, logic.get("operator", ""), logic.get("threshold"))
            findings.append({
                "check_id":  rule.get("id", rule.get("check", "?")),
                "title":     rule.get("rule", rule.get("flag", "")),
                "severity":  rule.get("severity", "medium"),
                "status":    "PASS" if passed else "FAIL",
                "source":    rule.get("source", ""),
                "principle": rule.get("principle", ""),
                "observed":  str(value),
                "threshold": str(logic.get("threshold", "")),
                "detail":    rule.get("suggestion", ""),
            })
        return findings

    @staticmethod
    def _map_stage(stage: str) -> str:
        """Map legacy stage names to current ones."""
        return {"data": "data_validation", "conceptual": "conceptual_soundness"}.get(stage, stage)

    # ── MDD keyword-search cross-check ────────────────────────────────────────

    def check_mdd_keywords(
        self,
        mdd_text: str,
        stage: str | None = None,
    ) -> list[dict]:
        """
        Keyword-search the uploaded MDD text against each rule's `keywords` list.

        For each rule, counts how many of its keywords appear in the MDD.
        Returns a result dict per rule shaped for the app.py render loop:
          {check_id, title, severity, status, source, principle, observed, threshold, detail}

        status = PASS  if keyword hits >= min_keyword_hits
               = WARN  if some keywords hit but below threshold, or no keywords defined
               = FAIL  if zero keyword hits for a rule with keywords
        """
        if not mdd_text:
            return []

        mdd_lower = mdd_text.lower()
        results: list[dict] = []

        for rule in self.rules:
            if stage is not None:
                rule_stage = rule.get("stage", "")
                if rule_stage not in (stage, self._map_stage(stage)):
                    continue

            # Skip machine-testable rules — those go through check_for_validation
            if rule.get("checkable_against_data", False):
                continue

            keywords: list[str] = rule.get("keywords", [])
            min_hits: int = rule.get("min_keyword_hits", 2)

            if not keywords:
                status   = "WARN"
                observed = "No keywords defined — manual review required"
            else:
                hits = [kw for kw in keywords if kw.lower() in mdd_lower]
                n_hits = len(hits)
                if n_hits >= min_hits:
                    status = "PASS"
                elif n_hits > 0:
                    status = "WARN"
                else:
                    status = "FAIL"
                observed = (
                    f"{n_hits}/{len(keywords)} keywords found: {', '.join(hits)}"
                    if hits else f"0/{len(keywords)} keywords found"
                )

            results.append({
                "check_id":  rule.get("id", rule.get("check", "?")),
                "title":     rule.get("rule", rule.get("flag", "")),
                "severity":  rule.get("severity", "medium"),
                "status":    status,
                "source":    rule.get("source", ""),
                "principle": rule.get("principle", ""),
                "observed":  observed,
                "threshold": f"≥ {min_hits} keyword(s)" if keywords else "N/A",
                "detail":    rule.get("suggestion", ""),
            })

        return results

    # ── Attestation checklist (manual reviewer sign-off) ─────────────────────

    def get_attestation_checklist(self, stage: str | None = None) -> list[dict]:
        """
        Return all descriptive (non-machine-testable) rules for reviewer sign-off,
        optionally filtered by stage.
        """
        items: list[dict] = []
        for r in self.rules:
            if r.get("checkable_against_data", False):
                continue
            if stage is not None and r.get("stage") not in (stage, self._map_stage(stage)):
                continue
            items.append({
                "rule_id":     r.get("id", "?"),
                "source":      r.get("source", ""),
                "principle":   r.get("principle", ""),
                "stage":       r.get("stage", ""),
                "severity":    r.get("severity", "medium"),
                "statement":   r.get("rule", r.get("flag", "")),
                "mdd_section": r.get("mdd_section_hint", ""),
                "keywords":    r.get("keywords", []),
                "suggestion":  r.get("suggestion", ""),
            })
        return items

    # ── Summary helpers ───────────────────────────────────────────────────────

    def rules_for_stage(self, stage: str) -> list[dict]:
        """Return all rules for a given validation stage."""
        return [r for r in self.rules if r.get("stage") in (stage, self._map_stage(stage))]

    @property
    def total_rules(self) -> int:
        return len(self.rules)
