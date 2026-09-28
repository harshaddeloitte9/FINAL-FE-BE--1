"""
Focused tests for business_rules.py (Phase 1 — LLM-assisted business-rule
discovery + deterministic pandas evaluation).

These tests deliberately do NOT trust the LLM for any pass/fail decision —
every assertion about violation counts is computed independently in the test
itself (via plain pandas) and checked against what business_rules.py produced,
to prove the deterministic engine — not Ollama — is the source of the numbers.

Most tests mock the Ollama call so the suite is deterministic and does not
require a local Ollama daemon. One additional test (marked, skipped if
unreachable) calls a REAL local Ollama instance to genuinely verify it can
propose the issue_date <= expiry_date rule from schema alone.
"""

import socket
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import business_rules
from llm_providers import LLMProviderError


# ── Shared fixtures ──────────────────────────────────────────────────────────

def _issue_expiry_dataframe() -> pd.DataFrame:
    """20 rows: 15 valid (issue <= expiry), 3 deliberately invalid
    (issue > expiry), 2 with a null in one of the two date columns."""
    rows = []
    for i in range(15):
        rows.append({"issue_date": f"2021-01-{i + 1:02d}", "expiry_date": f"2023-01-{i + 1:02d}", "loan_id": f"L{i}"})
    # Deliberately invalid: issue_date AFTER expiry_date.
    rows.append({"issue_date": "2024-06-01", "expiry_date": "2023-01-01", "loan_id": "BAD1"})
    rows.append({"issue_date": "2024-07-15", "expiry_date": "2023-02-01", "loan_id": "BAD2"})
    rows.append({"issue_date": "2025-01-01", "expiry_date": "2024-01-01", "loan_id": "BAD3"})
    # Null in one of the two referenced columns — must be excluded entirely.
    rows.append({"issue_date": None, "expiry_date": "2023-05-01", "loan_id": "NULL1"})
    rows.append({"issue_date": "2021-05-01", "expiry_date": None, "loan_id": "NULL2"})
    df = pd.DataFrame(rows)
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce")
    return df


def _date_order_rule(confidence: float = 0.96, rule_id: str = "DATE_ORDER_001") -> business_rules.LLMProposedRule:
    return business_rules.LLMProposedRule.model_validate(
        {
            "rule_id": rule_id,
            "type": "cross_column_date",
            "columns": ["issue_date", "expiry_date"],
            "operator": {"op": "lte", "left": "issue_date", "right": "expiry_date"},
            "condition_display": "issue_date <= expiry_date",
            "rationale": "Issue date should occur before or on expiry date.",
            "confidence": confidence,
            "source": "llm_inferred",
        }
    )


def _col_types_for(df: pd.DataFrame) -> dict:
    from utils import detect_column_types

    return detect_column_types(df)


# ── 1. Deterministic evaluation computes the REAL violation numbers ─────────

def test_cross_column_date_rule_applied_with_real_pandas_computed_violations():
    df = _issue_expiry_dataframe()
    col_types = _col_types_for(df)
    proposal = _date_order_rule(confidence=0.96)

    result = business_rules._gate_and_evaluate(proposal, df, col_types, threshold=0.90)

    # Independently computed expectation, using plain pandas — NOT via business_rules.
    valid_mask = df["issue_date"].notna() & df["expiry_date"].notna()
    expected_rows_checked = int(valid_mask.sum())
    expected_violations = int((valid_mask & (df["issue_date"] > df["expiry_date"])).sum())

    assert result["status"] == "applied"
    assert result["applied"] is True
    assert result["rows_checked"] == expected_rows_checked == 18  # 20 rows - 2 null rows
    assert result["violation_count"] == expected_violations == 3
    assert result["violation_percentage"] == round(3 / 18 * 100, 4)
    assert result["source"] == "llm_inferred"
    assert result["evaluated_at"]  # timestamp present


# ── 2. Null exclusion ────────────────────────────────────────────────────────

def test_null_values_excluded_from_rows_checked_and_violation_count():
    df = _issue_expiry_dataframe()
    col_types = _col_types_for(df)
    result = business_rules._gate_and_evaluate(_date_order_rule(), df, col_types, threshold=0.90)

    # 20 total rows, 2 have a null in one of the two referenced columns.
    assert len(df) == 20
    assert result["rows_checked"] == 18
    # The two null rows must not appear as violations either.
    assert result["violation_count"] == 3


# ── 3. Low confidence => suggested, NOT executed ────────────────────────────

def test_low_confidence_rule_is_suggested_and_not_executed():
    df = _issue_expiry_dataframe()
    col_types = _col_types_for(df)
    proposal = _date_order_rule(confidence=0.5)

    result = business_rules._gate_and_evaluate(proposal, df, col_types, threshold=0.90)

    assert result["status"] == "suggested"
    assert result["applied"] is False
    assert result["rows_checked"] is None
    assert result["violation_count"] is None
    assert result["violation_percentage"] is None
    assert "threshold" in result["reason"].lower()


# ── 4. Unsupported operator => invalid, NOT executed ────────────────────────

def test_unsupported_operator_is_invalid_and_not_executed():
    df = _issue_expiry_dataframe()
    col_types = _col_types_for(df)
    proposal = business_rules.LLMProposedRule.model_validate(
        {
            "rule_id": "BAD_OP_001",
            "type": "cross_column_date",
            "columns": ["issue_date", "expiry_date"],
            "operator": {"op": "neq", "left": "issue_date", "right": "expiry_date"},  # not whitelisted
            "condition_display": "issue_date != expiry_date",
            "rationale": "n/a",
            "confidence": 0.99,
            "source": "llm_inferred",
        }
    )

    result = business_rules._gate_and_evaluate(proposal, df, col_types, threshold=0.90)

    assert result["status"] == "invalid"
    assert result["applied"] is False
    assert result["rows_checked"] is None
    assert "schema" in result["reason"].lower()


# ── 5. Missing referenced column => invalid, NOT executed ───────────────────

def test_missing_referenced_column_is_invalid_and_not_executed():
    df = _issue_expiry_dataframe()
    col_types = _col_types_for(df)
    proposal = business_rules.LLMProposedRule.model_validate(
        {
            "rule_id": "MISSING_COL_001",
            "type": "cross_column_date",
            "columns": ["issue_date", "maturity_date"],  # maturity_date does not exist
            "operator": {"op": "lte", "left": "issue_date", "right": "maturity_date"},
            "condition_display": "issue_date <= maturity_date",
            "rationale": "n/a",
            "confidence": 0.99,
            "source": "llm_inferred",
        }
    )

    result = business_rules._gate_and_evaluate(proposal, df, col_types, threshold=0.90)

    assert result["status"] == "invalid"
    assert result["applied"] is False
    assert result["rows_checked"] is None
    assert "maturity_date" in result["reason"]


# ── 6. Incompatible column type => invalid, NOT executed ───────────────────

def test_incompatible_column_type_is_invalid_and_not_executed():
    df = _issue_expiry_dataframe()
    col_types = _col_types_for(df)
    # loan_id is a string/id column, not numeric — numeric_range must reject it.
    proposal = business_rules.LLMProposedRule.model_validate(
        {
            "rule_id": "BAD_TYPE_001",
            "type": "numeric_range",
            "columns": ["loan_id"],
            "operator": {"op": "between", "column": "loan_id", "min": 0, "max": 100},
            "condition_display": "loan_id between 0 and 100",
            "rationale": "n/a",
            "confidence": 0.99,
            "source": "llm_inferred",
        }
    )

    result = business_rules._gate_and_evaluate(proposal, df, col_types, threshold=0.90)

    assert result["status"] == "invalid"
    assert result["applied"] is False


# ── 7. Ollama unavailable fails soft ────────────────────────────────────────

def test_ollama_unavailable_fails_soft(monkeypatch):
    df = _issue_expiry_dataframe()

    def _raise(*args, **kwargs):
        raise LLMProviderError("Ollama unreachable: [Errno 111] Connection refused")

    monkeypatch.setattr(business_rules, "_call_ollama_for_rule_discovery", _raise)

    result = business_rules.discover_and_evaluate_rules(df)

    assert result["ollama_available"] is False
    assert result["rules"] == []
    assert result["applied_count"] == 0
    assert result["error"] is not None


# ── 8. Full discovery flow, mocked but realistic Ollama response ───────────

def test_discover_and_evaluate_rules_end_to_end_with_mocked_ollama_response(monkeypatch):
    df = _issue_expiry_dataframe()

    canned_response = """[
        {
            "rule_id": "DATE_ORDER_001",
            "type": "cross_column_date",
            "columns": ["issue_date", "expiry_date"],
            "operator": {"op": "lte", "left": "issue_date", "right": "expiry_date"},
            "condition_display": "issue_date <= expiry_date",
            "rationale": "Issue date should occur before or on expiry date.",
            "confidence": 0.96,
            "source": "llm_inferred"
        }
    ]"""

    monkeypatch.setattr(business_rules, "_call_ollama_for_rule_discovery", lambda metadata: canned_response)

    result = business_rules.discover_and_evaluate_rules(df, threshold=0.90)

    assert result["ollama_available"] is True
    assert result["applied_count"] == 1
    assert result["suggested_count"] == 0
    assert result["invalid_count"] == 0
    rule = result["rules"][0]
    assert rule["condition_display"] == "issue_date <= expiry_date"
    assert rule["status"] == "applied"
    # The deterministic layer — not the LLM — produced these numbers.
    assert rule["rows_checked"] == 18
    assert rule["violation_count"] == 3
    assert rule["violation_percentage"] == round(3 / 18 * 100, 4)


# ── 9. Malformed LLM output is recorded as invalid, never silently dropped ──

def test_malformed_llm_rule_is_recorded_as_invalid_not_dropped(monkeypatch):
    df = _issue_expiry_dataframe()
    # Missing required fields (no "operator", no "confidence").
    canned_response = '[{"rule_id": "BROKEN_1", "type": "cross_column_date", "columns": ["issue_date", "expiry_date"]}]'
    monkeypatch.setattr(business_rules, "_call_ollama_for_rule_discovery", lambda metadata: canned_response)

    result = business_rules.discover_and_evaluate_rules(df, threshold=0.90)

    assert result["invalid_count"] == 1
    assert result["rules"][0]["status"] == "invalid"
    assert result["rules"][0]["rule_id"] == "BROKEN_1"


# ── 10. Real local Ollama integration (skipped if unavailable) ─────────────

def _ollama_reachable() -> bool:
    try:
        with socket.create_connection(("localhost", 11434), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_reachable(), reason="Local Ollama daemon not reachable on localhost:11434")
def test_real_ollama_proposes_issue_expiry_date_order_rule():
    df = _issue_expiry_dataframe()
    result = business_rules.discover_and_evaluate_rules(df)

    assert result["ollama_available"] is True, result.get("error")
    date_order_rules = [
        r
        for r in result["rules"]
        if r.get("type") == "cross_column_date" and set(r.get("columns", [])) >= {"issue_date", "expiry_date"}
    ]
    assert date_order_rules, f"Expected Ollama to propose an issue_date/expiry_date rule; got: {result['rules']}"
    rule = date_order_rules[0]
    print("\nReal Ollama proposal:", rule)
    # Whatever Ollama proposed, the violation numbers must still be real and
    # deterministic if the rule was applied.
    if rule["status"] == "applied":
        assert rule["rows_checked"] == 18
        assert rule["violation_count"] == 3


# ── 11. Actual FastAPI endpoint wiring (mocked Ollama call) ─────────────────

def test_endpoint_discover_rules_via_testclient(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import main

    canned_response = """[
        {
            "rule_id": "DATE_ORDER_001",
            "type": "cross_column_date",
            "columns": ["issue_date", "expiry_date"],
            "operator": {"op": "lte", "left": "issue_date", "right": "expiry_date"},
            "condition_display": "issue_date <= expiry_date",
            "rationale": "Issue date should occur before or on expiry date.",
            "confidence": 0.96,
            "source": "llm_inferred"
        }
    ]"""
    monkeypatch.setattr(business_rules, "_call_ollama_for_rule_discovery", lambda metadata: canned_response)

    csv_path = tmp_path / "issue_expiry.csv"
    _issue_expiry_dataframe().to_csv(csv_path, index=False)

    client = TestClient(main.app)
    with open(csv_path, "rb") as f:
        response = client.post(
            "/data/business-rules/discover",
            files={"file": ("issue_expiry.csv", f, "text/csv")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ollama_available"] is True
    assert payload["applied_count"] == 1
    rule = payload["rules"][0]
    assert rule["condition_display"] == "issue_date <= expiry_date"
    assert rule["status"] == "applied"
    assert rule["rows_checked"] == 18
    assert rule["violation_count"] == 3
