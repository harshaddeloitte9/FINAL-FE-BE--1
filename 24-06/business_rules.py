"""
business_rules.py — LLM-assisted business-rule DISCOVERY + deterministic
pandas EVALUATION for the Aegis Data Quality page (Phase 1, backend-only).

Architecture (non-negotiable):
    Ollama proposes candidate rules from dataset METADATA only (column names,
    detected types, min/max/sample values) — it never sees row-level data and
    never judges whether any individual row passes or fails.
    A deterministic, whitelisted-operator pandas engine in this module is the
    ONLY thing that ever computes rows_checked / violation_count /
    violation_percentage. No eval(), no exec(), no LLM-generated code path.

Flow:
    summarize_dataframe_for_llm(df)      -> compact metadata (sent to Ollama)
    _call_ollama_for_rule_discovery(...) -> raw LLM text (local Ollama only —
                                             this deliberately does NOT use
                                             llm_providers.complete_with_fallback,
                                             which tries a remote endpoint first)
    _parse_and_validate_llm_response(...) -> List[LLMProposedRule] (Pydantic)
    _gate_and_evaluate(...)              -> safety gate + deterministic pandas
                                             evaluation + classification
    discover_and_evaluate_rules(df)      -> the single public entry point
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Type

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from llm_providers import LLMProviderError, OllamaProvider
from utils import detect_column_types

# ── Observability (diagnostic-only, no business-rule/DQ logic here) ─────────
# Named logger, matching the existing library-style convention already used
# by data_integration.py (attach handlers only if the host app hasn't already
# configured logging, so this never duplicates output under uvicorn/main.py).
# In addition to the console StreamHandler that convention uses, a dedicated
# FileHandler is attached: this endpoint's worker process inherits stdout
# through uvicorn `--reload`'s reloader/worker process chain, which has been
# observed in practice to buffer console output for many minutes before any
# of it becomes visible — a direct file handle avoids that so this record is
# actually readable while a request is in flight, not just after the fact.
# Never logs raw dataset rows, sample values, or the prompt — only shape,
# status, counts, timing, and exception text.
logger = logging.getLogger("business_rules")
if not logger.handlers:
    _formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(_formatter)
    logger.addHandler(_stream_handler)
    _file_handler = logging.FileHandler(Path(__file__).resolve().parent / "business_rules_discovery.log")
    _file_handler.setFormatter(_formatter)
    logger.addHandler(_file_handler)
    logger.setLevel(logging.INFO)

# ── Configuration ────────────────────────────────────────────────────────────

# The consultant did not specify a numeric confidence threshold. 0.90 is a
# clearly-documented POC default only — override via the environment variable
# below. Read at call time (not cached at import) so a changed .env takes
# effect on the next request without a code change.
DEFAULT_CONFIDENCE_THRESHOLD = 0.90


def get_confidence_threshold() -> float:
    try:
        return float(os.environ.get("BUSINESS_RULE_CONFIDENCE_THRESHOLD", str(DEFAULT_CONFIDENCE_THRESHOLD)))
    except (TypeError, ValueError):
        return DEFAULT_CONFIDENCE_THRESHOLD


SUPPORTED_RULE_TYPES = ("numeric_range", "allowed_values", "cross_column_date", "cross_column_numeric")

_ALLOWED_OPERATORS_BY_TYPE: Dict[str, set] = {
    "numeric_range": {"between", "gte", "lte"},
    "allowed_values": {"in_set"},
    "cross_column_date": {"lte", "gte", "lt", "gt", "eq"},
    "cross_column_numeric": {"lte", "gte", "lt", "gt", "eq"},
}

MAX_SAMPLE_VIOLATION_INDICES = 50


# ── Pydantic schemas — nothing from the LLM is trusted until it parses here ──

class LLMProposedRule(BaseModel):
    """Top-level shape every LLM-proposed rule must match exactly."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    type: Literal["numeric_range", "allowed_values", "cross_column_date", "cross_column_numeric"]
    columns: List[str] = Field(min_length=1)
    operator: Dict[str, Any]
    condition_display: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["llm_inferred"] = "llm_inferred"


class BetweenOperator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["between"]
    column: str
    min: float
    max: float


class ComparisonValueOperator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["gte", "lte"]
    column: str
    value: float


class InSetOperator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["in_set"]
    column: str
    values: List[Any] = Field(min_length=1)


class CrossColumnOperator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["lte", "gte", "lt", "gt", "eq"]
    left: str
    right: str


# Candidate operator models tried, in order, for each rule type. The first one
# that validates wins; if none validate, the rule is "invalid" — this is the
# concrete mechanism behind safety-gate requirement "operator payload exactly
# matches the allowed schema".
_OPERATOR_MODELS: Dict[str, List[Type[BaseModel]]] = {
    "numeric_range": [BetweenOperator, ComparisonValueOperator],
    "allowed_values": [InSetOperator],
    "cross_column_date": [CrossColumnOperator],
    "cross_column_numeric": [CrossColumnOperator],
}


def _validate_operator(rule_type: str, operator: Dict[str, Any]) -> Optional[BaseModel]:
    for model_cls in _OPERATOR_MODELS.get(rule_type, []):
        try:
            return model_cls.model_validate(operator)
        except ValidationError:
            continue
    return None


def _extract_operator_columns(rule_type: str, operator_model: BaseModel) -> List[str]:
    if rule_type in ("numeric_range", "allowed_values"):
        return [operator_model.column]
    return [operator_model.left, operator_model.right]


def _check_type_compatibility(rule_type: str, operator_cols: List[str], col_types: Dict[str, List[str]]) -> Tuple[bool, Optional[str]]:
    numeric_cols = set(col_types.get("numeric", []))
    categorical_cols = set(col_types.get("categorical", []))
    boolean_cols = set(col_types.get("boolean", []))
    datetime_cols = set(col_types.get("datetime", []))

    if rule_type == "numeric_range":
        (col,) = operator_cols
        if col not in numeric_cols:
            return False, f"Column '{col}' is not a detected numeric column."
        return True, None

    if rule_type == "allowed_values":
        (col,) = operator_cols
        if col not in categorical_cols and col not in boolean_cols:
            return False, f"Column '{col}' is not a detected categorical/boolean column."
        return True, None

    if rule_type == "cross_column_date":
        left, right = operator_cols
        if left not in datetime_cols or right not in datetime_cols:
            return False, f"Both '{left}' and '{right}' must be detected datetime columns."
        return True, None

    if rule_type == "cross_column_numeric":
        left, right = operator_cols
        if left not in numeric_cols or right not in numeric_cols:
            return False, f"Both '{left}' and '{right}' must be detected numeric columns."
        return True, None

    return False, f"Unsupported rule type: {rule_type}"


# ── Dataset metadata summarization (this — and only this — goes to Ollama) ──

def summarize_dataframe_for_llm(df: pd.DataFrame, max_sample_values: int = 5, max_categories: int = 20) -> Dict[str, Any]:
    """Compact, non-row-level metadata: column names, detected types, and a
    few representative sample values/min/max per column. This is deliberately
    modeled on the same fields _build_data_profile's data_dictionary already
    carries, but computed independently here so this module never needs to
    invoke (or risk coupling to) the full profiling pipeline."""
    col_types = detect_column_types(df)
    columns_summary: List[Dict[str, Any]] = []

    for col in df.columns.astype(str):
        series = df[col]
        detected_type = next((t for t, cols in col_types.items() if col in cols), "unknown")
        non_null = series.dropna()
        entry: Dict[str, Any] = {
            "name": col,
            "type": detected_type,
            "missing_count": int(series.isna().sum()),
            "unique_count": int(non_null.nunique()),
        }
        try:
            if detected_type == "numeric":
                numeric_series = pd.to_numeric(non_null, errors="coerce").dropna()
                if not numeric_series.empty:
                    entry["min"] = float(numeric_series.min())
                    entry["max"] = float(numeric_series.max())
            elif detected_type == "categorical" or detected_type == "boolean":
                entry["sample_categories"] = [str(v) for v in non_null.unique()[:max_categories]]
            elif detected_type == "datetime":
                parsed = pd.to_datetime(non_null, errors="coerce").dropna()
                if not parsed.empty:
                    entry["min_date"] = str(parsed.min().date())
                    entry["max_date"] = str(parsed.max().date())
        except Exception:
            pass
        entry["sample_values"] = [str(v) for v in non_null.unique()[:max_sample_values]]
        columns_summary.append(entry)

    return {
        "columns": df.columns.astype(str).tolist(),
        "col_types": col_types,
        "columns_summary": columns_summary,
        "shape": list(df.shape),
    }


# ── Ollama call — local only, strict JSON schema (Phase 1 requirement) ──────

# We deliberately do NOT reuse OllamaProvider.complete() as-is: it hardcodes a
# fixed JSON schema for the Stage 2/3 PASS/WARN/FAIL rule-check feature, which
# is unrelated to (and incompatible with) rule discovery. Calling it here
# would force the model to emit that unrelated schema. Instead we reuse
# OllamaProvider purely for its existing, env-driven local configuration
# (base_url/model/timeout) and issue our own request with our own schema —
# same local-only guarantee, same config resolution, correct schema. We
# intentionally never touch llm_providers.py or complete_with_fallback(),
# which tries a remote endpoint first.
_RULE_DISCOVERY_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "rule_id": {"type": "string"},
            "type": {"type": "string", "enum": list(SUPPORTED_RULE_TYPES)},
            "columns": {"type": "array", "items": {"type": "string"}},
            "operator": {"type": "object"},
            "condition_display": {"type": "string"},
            "rationale": {"type": "string"},
            "confidence": {"type": "number"},
            "source": {"type": "string", "enum": ["llm_inferred"]},
        },
        "required": ["rule_id", "type", "columns", "operator", "condition_display", "rationale", "confidence", "source"],
        "additionalProperties": False,
    },
}


def _build_discovery_prompt(metadata: Dict[str, Any]) -> str:
    shape = metadata["shape"]
    return f"""You are a data-quality assistant. You are given ONLY the schema and \
summary statistics of a tabular dataset — no row-level data. Do not assume you \
have seen individual records.

Dataset shape: {shape[0]} rows x {shape[1]} columns.

Columns (name, detected type, and summary stats/sample values):
{json.dumps(metadata["columns_summary"], indent=2, default=str)}

Propose up to 8 high-confidence, OBJECTIVELY EXECUTABLE data-quality rules a \
deterministic program could check against this dataset. Only propose a rule \
if it is clearly justified by the column names/types/stats shown above — do \
not invent numeric thresholds or category lists that aren't supported by the \
information given.

Each rule must use exactly one of these types and matching operator shapes:
- numeric_range: {{"op": "between", "column": "<name>", "min": <number>, "max": <number>}}
                 or {{"op": "gte"|"lte", "column": "<name>", "value": <number>}}
- allowed_values: {{"op": "in_set", "column": "<name>", "values": [<value>, ...]}}
- cross_column_date: {{"op": "lte"|"gte"|"lt"|"gt"|"eq", "left": "<date column>", "right": "<date column>"}}
- cross_column_numeric: {{"op": "lte"|"gte"|"lt"|"gt"|"eq", "left": "<numeric column>", "right": "<numeric column>"}}

A classic example: if the dataset has an "issue_date" and an "expiry_date" \
column, the natural rule is issue_date <= expiry_date (type: cross_column_date, \
operator: {{"op": "lte", "left": "issue_date", "right": "expiry_date"}}).

Only reference column names that appear in the list above. Respond with a \
JSON array of rule objects only.
"""


def _call_ollama_for_rule_discovery(metadata: Dict[str, Any]) -> str:
    provider = OllamaProvider()  # reused for its local, env-driven config only
    logger.info("Ollama call started: model=%s base_url=%s timeout=%.0fs", provider.model, provider.base_url, provider.timeout)
    prompt = _build_discovery_prompt(metadata)
    payload = json.dumps(
        {
            "model": provider.model,
            "prompt": prompt,
            "stream": False,
            "format": _RULE_DISCOVERY_JSON_SCHEMA,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(f"{provider.base_url}/api/generate", data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=provider.timeout) as resp:
            if resp.status >= 400:
                raise LLMProviderError(f"Ollama returned HTTP {resp.status}")
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise LLMProviderError(f"Ollama HTTP error: {e.code} {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise LLMProviderError(f"Ollama unreachable: {e}") from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body
    return str(data.get("response", body))


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


def _parse_and_validate_llm_response(raw: str) -> List[Dict[str, Any]]:
    """Returns a list of dicts, each either a validated LLMProposedRule
    (accessible via ["_proposal"]) or an already-classified invalid record for
    malformed items — nothing here is silently dropped (auditability)."""
    try:
        parsed = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []

    results: List[Dict[str, Any]] = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            results.append(_invalid_record({"rule_id": f"unparsed_{i}"}, f"LLM produced a non-object rule entry at index {i}."))
            continue
        try:
            proposal = LLMProposedRule.model_validate(item)
            results.append({"_proposal": proposal})
        except ValidationError as e:
            results.append(_invalid_record(item, f"LLM output failed schema validation: {e}"))
    return results


def _invalid_record(raw_item: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "_invalid": True,
        "rule_id": str(raw_item.get("rule_id", "unknown")),
        "type": raw_item.get("type"),
        "columns": raw_item.get("columns", []),
        "condition_display": raw_item.get("condition_display", ""),
        "rationale": raw_item.get("rationale", ""),
        "confidence": raw_item.get("confidence"),
        "source": "llm_inferred",
        "status": "invalid",
        "reason": reason,
        "applied": False,
        "rows_checked": None,
        "violation_count": None,
        "violation_percentage": None,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Deterministic pandas evaluator — the ONLY code that decides pass/fail ───

def _evaluate_rule(df: pd.DataFrame, rule_type: str, operator_model: BaseModel) -> Dict[str, Any]:
    if rule_type == "numeric_range":
        series = pd.to_numeric(df[operator_model.column], errors="coerce")
        checked_mask = series.notna()
        if operator_model.op == "between":
            ok_mask = series.between(operator_model.min, operator_model.max)
        elif operator_model.op == "gte":
            ok_mask = series >= operator_model.value
        else:  # lte
            ok_mask = series <= operator_model.value

    elif rule_type == "allowed_values":
        series = df[operator_model.column]
        checked_mask = series.notna()
        allowed = {str(v) for v in operator_model.values}
        ok_mask = series.astype(str).isin(allowed)

    else:  # cross_column_date / cross_column_numeric
        if rule_type == "cross_column_date":
            left = pd.to_datetime(df[operator_model.left], errors="coerce")
            right = pd.to_datetime(df[operator_model.right], errors="coerce")
        else:
            left = pd.to_numeric(df[operator_model.left], errors="coerce")
            right = pd.to_numeric(df[operator_model.right], errors="coerce")
        # Requirement: null rows are excluded from rows_checked AND
        # violation_count — never automatically treated as a violation.
        checked_mask = left.notna() & right.notna()
        if operator_model.op == "lte":
            ok_mask = left <= right
        elif operator_model.op == "gte":
            ok_mask = left >= right
        elif operator_model.op == "lt":
            ok_mask = left < right
        elif operator_model.op == "gt":
            ok_mask = left > right
        else:  # eq
            ok_mask = left == right

    violating_mask = checked_mask & ~ok_mask.fillna(False)
    rows_checked = int(checked_mask.sum())
    violation_count = int(violating_mask.sum())
    violation_percentage = round((violation_count / rows_checked * 100) if rows_checked else 0.0, 4)
    sample_violation_indices = df.index[violating_mask].tolist()[:MAX_SAMPLE_VIOLATION_INDICES]

    return {
        "rows_checked": rows_checked,
        "violation_count": violation_count,
        "violation_percentage": violation_percentage,
        "sample_violation_indices": sample_violation_indices,
    }


def _not_executed_record(proposal: LLMProposedRule, status: str, reason: Optional[str]) -> Dict[str, Any]:
    record = proposal.model_dump()
    record.update(
        {
            "status": status,
            "reason": reason,
            "applied": False,
            "rows_checked": None,
            "violation_count": None,
            "violation_percentage": None,
            "sample_violation_indices": None,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return record


def _gate_and_evaluate(proposal: LLMProposedRule, df: pd.DataFrame, col_types: Dict[str, List[str]], threshold: float) -> Dict[str, Any]:
    # Gate 1 — referenced columns (as declared by the LLM) exist.
    missing_declared = [c for c in proposal.columns if c not in df.columns]
    if missing_declared:
        return _not_executed_record(proposal, "invalid", f"Declared column(s) not found in dataset: {missing_declared}")

    # Gate 2 — operator payload exactly matches the allowed schema for this type.
    operator_model = _validate_operator(proposal.type, proposal.operator)
    if operator_model is None:
        return _not_executed_record(
            proposal, "invalid", f"Operator payload does not match the allowed schema for type '{proposal.type}' (allowed ops: {sorted(_ALLOWED_OPERATORS_BY_TYPE[proposal.type])})."
        )

    # Gate 3 — columns actually referenced by the operator exist.
    operator_cols = _extract_operator_columns(proposal.type, operator_model)
    missing_operator_cols = [c for c in operator_cols if c not in df.columns]
    if missing_operator_cols:
        return _not_executed_record(proposal, "invalid", f"Operator references column(s) not found in dataset: {missing_operator_cols}")

    # Gate 4 — column dtypes are compatible with the rule type.
    compatible, reason = _check_type_compatibility(proposal.type, operator_cols, col_types)
    if not compatible:
        return _not_executed_record(proposal, "invalid", reason)

    # Gate 5 — confidence threshold. Below threshold => suggested, NOT executed.
    if proposal.confidence < threshold:
        return _not_executed_record(proposal, "suggested", f"Confidence {proposal.confidence:.2f} below configured threshold {threshold:.2f}.")

    # All gates passed and confidence is high enough — deterministic pandas
    # evaluation is the ONLY thing that produces the numbers below.
    evaluation = _evaluate_rule(df, proposal.type, operator_model)
    record = proposal.model_dump()
    record.update(
        {
            "status": "applied",
            "reason": None,
            "applied": True,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            **evaluation,
        }
    )
    return record


# ── Public entry point ───────────────────────────────────────────────────────

def discover_and_evaluate_rules(df: pd.DataFrame, threshold: Optional[float] = None) -> Dict[str, Any]:
    """Discover candidate business rules from `df`'s schema/metadata via the
    local Ollama provider, then deterministically evaluate and classify each
    one. Never raises for an unavailable/misbehaving LLM — fails soft with an
    empty rule set so callers (e.g. /data/upload's page) are never broken."""
    threshold = get_confidence_threshold() if threshold is None else threshold
    logger.info("Business-rule discovery request started: dataset shape=%d rows x %d columns", df.shape[0], df.shape[1])
    metadata = summarize_dataframe_for_llm(df)

    ollama_started_at = time.monotonic()
    try:
        raw_response = _call_ollama_for_rule_discovery(metadata)
    except LLMProviderError as e:
        elapsed = time.monotonic() - ollama_started_at
        logger.error("Ollama call failed after %.1fs: %s", elapsed, e)
        result = {
            "rules": [],
            "applied_count": 0,
            "suggested_count": 0,
            "invalid_count": 0,
            "threshold_used": threshold,
            "ollama_available": False,
            "error": str(e),
        }
        logger.info(
            "Business-rule discovery finished: ollama_available=%s applied_count=%d suggested_count=%d invalid_count=%d elapsed=%.1fs",
            result["ollama_available"], result["applied_count"], result["suggested_count"], result["invalid_count"], elapsed,
        )
        return result

    elapsed = time.monotonic() - ollama_started_at
    logger.info("Ollama call completed after %.1fs", elapsed)

    parsed_items = _parse_and_validate_llm_response(raw_response)

    results: List[Dict[str, Any]] = []
    for item in parsed_items:
        if item.get("_invalid"):
            item = {k: v for k, v in item.items() if k != "_invalid"}
            results.append(item)
            continue
        proposal: LLMProposedRule = item["_proposal"]
        results.append(_gate_and_evaluate(proposal, df, metadata["col_types"], threshold))

    applied_count = sum(1 for r in results if r["status"] == "applied")
    suggested_count = sum(1 for r in results if r["status"] == "suggested")
    invalid_count = sum(1 for r in results if r["status"] == "invalid")

    result = {
        "rules": results,
        "applied_count": applied_count,
        "suggested_count": suggested_count,
        "invalid_count": invalid_count,
        "threshold_used": threshold,
        "ollama_available": True,
        "error": None,
    }
    logger.info(
        "Business-rule discovery finished: ollama_available=%s applied_count=%d suggested_count=%d invalid_count=%d elapsed=%.1fs",
        result["ollama_available"], result["applied_count"], result["suggested_count"], result["invalid_count"], elapsed,
    )
    return result
