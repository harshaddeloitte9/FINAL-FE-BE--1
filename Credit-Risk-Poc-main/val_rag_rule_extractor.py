"""
val_rag_rule_extractor.py
Extracts structured MDD validation rules from regulatory documents using a local Ollama LLM.

Purpose
-------
This is the RAG rule-extraction engine for the **model validation pipeline** —
specifically for Stage 2 (Data Validation) and Stage 3 (Conceptual Soundness).

It is intentionally scoped to qualitative / rationale-oriented rules: things that
a validator checks by reading the Model Development Document (MDD) rather than by
running numbers against a dataset.  Hard quantitative thresholds (missing %, IV,
VIF, etc.) are already enforced by the hardcoded checks in render_val_data_validation()
and render_val_conceptual_soundness(); this extractor handles everything else.

The extracted rules are saved to rag_store/val_mdd_rules.json by val_build_rules.py.
Agent 2b (your colleague's agent) will later load that JSON, cross-check it against
the uploaded MDD, and surface PASS / WARN / FAIL findings in the Streamlit UI.

Pipeline
--------
  1. Split regulatory document into overlapping paragraph chunks
  2. Pre-filter chunks by MDD-validation keyword score — only high-scoring chunks
     go to the LLM (reduces token usage by ~70 % on typical documents)
  3. LLM extracts structured rules in JSONL format
  4. val_build_rules.py deduplicates, assigns IDs, saves to val_mdd_rules.json

Rule schema (one rule per line from LLM, normalised here)
---------------------------------------------------------
  {
    "id"          : "V01",           # assigned by val_build_rules.py
    "stage"       : "data" | "conceptual",
    "check_id"    : "2.x" | "3.x",  # aligns with existing check IDs in app.py
    "check"       : "snake_case_identifier",
    "severity"    : "high" | "medium" | "low",
    "source"      : "SS1/23",        # regulatory document filename
    "principle"   : "P2.1",
    "rule"        : "One-sentence description of what must be present in the MDD",
    "flag"        : "Text shown when rule fails",
    "suggestion"  : "Remediation action",
    "mdd_section_hint" : "Expected MDD section (e.g. 'Section 4 — Model Selection')",
    "keywords"    : ["keyword1", "keyword2"],  # words the MDD must contain to pass
    "min_keyword_hits" : 2,          # how many keywords needed for PASS vs WARN
  }
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional


# ── Relevance pre-filter ──────────────────────────────────────────────────────

# Tier-1: MDD validation obligation language
_OBLIGATION_PATTERNS = re.compile(
    r"\b(shall|must|required to|is required|are required|should|need to|"
    r"obligated|mandated|prohibited from|is prohibited|failure to|non.compliance|"
    r"documented|disclosed|evidenced|demonstrated|justified|substantiated)\b",
    re.IGNORECASE,
)

# Tier-2: MDD-validation-specific keywords
#   Grouped into the two validation stages so we can route rules correctly.
_MDD_VALIDATION_KEYWORDS: set[str] = {
    # ── Model purpose / scope (Stage 3)
    "model purpose", "intended use", "scope", "portfolio", "applicability",
    "use case", "business objective", "model objective", "credit risk model",
    "pd model", "lgd model", "ead model", "ecl model", "scorecard",
    # ── Model selection justification (Stage 3, check 3.1)
    "model selection", "model choice", "algorithm selection", "rationale",
    "justification", "chosen because", "appropriate because", "selected model",
    "logistic regression", "xgboost", "lightgbm", "gradient boosting",
    "random forest", "neural network", "linear regression",
    # ── Benchmarking (Stage 3, check 3.2)
    "benchmark", "challenger model", "baseline model", "alternative model",
    "simpler model", "comparison", "comparative", "out-of-time", "oot",
    "gini", "roc.auc", "discrimination", "discriminatory power",
    # ── Assumptions & limitations (Stage 3)
    "assumption", "limitation", "caveat", "constraint", "condition",
    "simplifying assumption", "model limitation", "known limitation",
    "out of scope", "not applicable", "boundary condition",
    # ── Data governance / provenance (Stage 2)
    "data source", "data dictionary", "data lineage", "data governance",
    "training data", "development sample", "observation window",
    "performance window", "data quality", "data integrity",
    "sampling methodology", "sampling strategy", "selection criteria",
    "representativeness", "exclusion criteria",
    # ── Forward-looking information (Stage 2 / IFRS 9)
    "forward.looking", "macroeconomic", "macro variable", "scenario",
    "economic scenario", "point in time", "through the cycle",
    "probability.weighted", "multiple scenarios",
    # ── Regulatory
    "ss1/23", "ss11/13", "ifrs 9", "ifrs9", "model risk",
    "model validation", "independent validation", "validation plan",
    "validation scope", "significant increase in credit risk", "sicr",
    "default definition", "days past due", "dpd", "90 days",
    # ── Documentation standards
    "documentation", "evidence", "audit trail", "traceability",
    "reproducible", "version control", "model inventory",
    "validation finding", "finding", "model limitation",
}

# Noise patterns — table of contents lines, bare headers, page numbers
_NOISE_PATTERNS = re.compile(
    r"^(table of contents|contents|appendix [a-z]|page \d|\.{5,}|\d+\s*$)",
    re.IGNORECASE | re.MULTILINE,
)


def _score_chunk(text: str) -> float:
    """
    Return a relevance score [0.0, 1.0] for a text chunk.

    Scoring heuristic (same structure as rule_extractor.py):
      - Obligation language present  → +0.45
      - Each keyword hit             → +0.08 (capped at 0.55 total)
      - Noise pattern present        → −0.30
    """
    score = 0.0
    tl = text.lower()

    if _OBLIGATION_PATTERNS.search(text):
        score += 0.45

    keyword_hits = sum(
        1 for kw in _MDD_VALIDATION_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", tl)
    )
    score += min(keyword_hits * 0.08, 0.55)

    if _NOISE_PATTERNS.search(text):
        score -= 0.30

    return max(0.0, min(score, 1.0))


def _split_into_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries."""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para

    if current:
        chunks.append(current)

    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            overlapped.append((tail + "\n\n" + chunks[i]).strip())
        return overlapped

    return chunks


def filter_relevant_chunks(
    text: str,
    min_score: float = 0.45,
    chunk_size: int = 800,
    overlap: int = 150,
    max_chunks: int = 40,
) -> list[tuple[str, float]]:
    """
    Split text and return only chunks above min_score, sorted by score descending.
    Returns list of (chunk_text, score) tuples.
    """
    chunks = _split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
    scored = [(chunk, _score_chunk(chunk)) for chunk in chunks]
    relevant = [(c, s) for c, s in scored if s >= min_score]
    relevant.sort(key=lambda x: x[1], reverse=True)
    return relevant[:max_chunks]


# ── LLM extraction prompt ─────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """\
You are a senior model validation analyst specialising in credit risk model documentation review.
Read the excerpt below from the regulatory document '{source}' and extract every distinct rule
or requirement that applies to what a Model Development Document (MDD) must contain, demonstrate,
or document.

Focus ONLY on qualitative / rationale-based requirements — things a validator checks by reading
the MDD, not by computing statistics on a dataset.  Do NOT extract quantitative thresholds
(e.g. "missing rate < 20%", "IV > 0.02") — those are handled separately.

Relevant topics include but are not limited to:
  - Model purpose and intended use must be clearly stated
  - Rationale for the chosen modelling technique must be documented
  - Evidence of benchmarking against simpler/alternative models
  - Assumptions and limitations must be disclosed
  - Data sources, observation window, and sampling methodology documented
  - Forward-looking macroeconomic information incorporated and justified
  - Default definition aligned with IFRS 9 (90 DPD or documented alternative)
  - Model governance, version control, and audit trail
  - SICR criteria and staging logic documented
  - Explainability, interpretability, and SHAP analysis documented

For each rule, output exactly ONE JSON object on its own line with these keys:
  "rule_text"         : one-sentence statement of what the MDD must contain/demonstrate
  "check"             : snake_case identifier (e.g. "model_purpose_documented")
  "stage"             : "data" or "conceptual" (which validation stage this belongs to)
  "check_id_hint"     : approximate check number, e.g. "2.6" or "3.1" (use "3.x" if uncertain)
  "severity"          : "high" | "medium" | "low"
  "principle"         : the specific regulatory principle or paragraph (e.g. "P2.1", "§10.1", "B5.5.49")
  "mdd_section_hint"  : expected MDD section title (e.g. "Model Selection Rationale")
  "keywords"          : JSON array of 3-6 words/phrases the MDD should contain to satisfy this rule
  "min_keyword_hits"  : integer — minimum keyword matches for a PASS (typically 2-3)
  "action"            : one-sentence remediation if the rule is not satisfied in the MDD

Output ONLY JSON lines — no markdown, no prose, no array brackets.
If the excerpt contains no qualifying requirements, output nothing.

Excerpt:
{snippet}
"""


# ── MddRuleExtractor ──────────────────────────────────────────────────────────

class MddRuleExtractor:
    """
    Extracts structured MDD validation rules from regulatory source documents.

    Analogous to RuleExtractor in rule_extractor.py but scoped to the model
    validation pipeline (Stage 2 / Stage 3) and focused on qualitative,
    rationale-based requirements that a validator checks by reading the MDD.

    Usage
    -----
    extractor = MddRuleExtractor()
    rules = extractor.extract_from_file(Path("rag_store/documents/SS1_23.pdf"))
    """

    def __init__(self, model: str = "llama3.1", min_relevance_score: float = 0.45):
        self.model = model
        self.min_relevance_score = min_relevance_score

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """Call the local Ollama LLM and return raw text content."""
        import ollama as _ollama
        try:
            response = _ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
        except Exception as e:
            print(f"[MddRuleExtractor] LLM call failed: {e}", file=sys.stderr)
            return ""

    def _parse_llm_output(self, content: str, source: str) -> list[dict]:
        """Parse LLM JSONL output into raw rule dicts. Malformed lines are skipped."""
        rules = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    rule = json.loads(line)
                    rule["source"] = source
                    rules.append(rule)
                except json.JSONDecodeError:
                    pass
        return rules

    def _normalise_rule(self, raw: dict, source: str) -> dict:
        """
        Normalise a raw LLM output dict into the canonical MDD rule format.

        The resulting dict is what val_build_rules.py saves to val_mdd_rules.json
        and what Agent 2b loads to check against the uploaded MDD.
        """
        return {
            # Identity / provenance
            "id":               None,            # filled by val_build_rules.py
            "source":           source,
            "check":            raw.get("check", "").strip(),
            "stage":            raw.get("stage", "conceptual"),
            "check_id_hint":    raw.get("check_id_hint", "3.x"),
            "severity":         raw.get("severity", "medium"),
            "principle":        raw.get("principle", "?"),

            # Human-readable
            "rule":             raw.get("rule_text", ""),
            "flag":             raw.get("rule_text", "MDD validation rule not satisfied"),
            "suggestion":       raw.get("action", "Review the relevant regulatory guidance and update the MDD."),
            "mdd_section_hint": raw.get("mdd_section_hint", ""),

            # MDD keyword-matching config used by Agent 2b
            "keywords":         raw.get("keywords", []),
            "min_keyword_hits": int(raw.get("min_keyword_hits", 2)),
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def extract_from_text(
        self,
        text: str,
        source: str,
        chunk_size: int = 800,
        overlap: int = 150,
        max_chunks: int = 40,
        verbose: bool = False,
    ) -> list[dict]:
        """
        Extract MDD validation rules from a block of text.

        Steps:
          1. Split into overlapping paragraph chunks
          2. Score each chunk for MDD-validation relevance
          3. Send only chunks scoring >= self.min_relevance_score to the LLM
          4. Parse and normalise; deduplicate by check identifier

        Args:
            text:       Full document text
            source:     Label used in rule provenance (e.g. filename)
            chunk_size: Soft character limit per chunk
            overlap:    Character overlap between adjacent chunks
            max_chunks: Hard cap on LLM calls (cost control)
            verbose:    Print per-chunk scoring if True

        Returns:
            List of normalised rule dicts ready for val_build_rules.py
        """
        relevant_chunks = filter_relevant_chunks(
            text,
            min_score=self.min_relevance_score,
            chunk_size=chunk_size,
            overlap=overlap,
            max_chunks=max_chunks,
        )

        if not relevant_chunks:
            print(
                f"[MddRuleExtractor] No relevant chunks found in '{source}' "
                f"(min_score={self.min_relevance_score}). "
                "Consider lowering min_relevance_score or checking the document.",
                file=sys.stderr,
            )
            return []

        if verbose:
            total_chunks = len(_split_into_chunks(text, chunk_size, overlap))
            print(
                f"[MddRuleExtractor] {source}: {len(relevant_chunks)} relevant chunks "
                f"(of {total_chunks} total) will be sent to LLM",
                file=sys.stderr,
            )

        all_rules: list[dict] = []
        seen_checks: set[str] = set()

        for i, (chunk, score) in enumerate(relevant_chunks):
            if verbose:
                preview = chunk[:60].replace("\n", " ")
                print(
                    f"[MddRuleExtractor]   chunk {i + 1}/{len(relevant_chunks)} "
                    f'score={score:.2f} — "{preview}..."',
                    file=sys.stderr,
                )

            prompt = _EXTRACTION_PROMPT.format(source=source, snippet=chunk)
            raw_content = self._call_llm(prompt)
            raw_rules = self._parse_llm_output(raw_content, source)

            for raw in raw_rules:
                check = raw.get("check", "").strip()
                if not check or check in seen_checks:
                    continue
                seen_checks.add(check)
                all_rules.append(self._normalise_rule(raw, source))

        return all_rules

    def extract_from_file(
        self,
        path: Path,
        source: Optional[str] = None,
        max_pages: int = 30,
        verbose: bool = False,
    ) -> list[dict]:
        """
        Extract MDD validation rules from a PDF, TXT, or MD file.

        Args:
            path:      Path to the regulatory document
            source:    Override the source label (defaults to filename)
            max_pages: Maximum pages to read from PDFs
            verbose:   Pass-through to extract_from_text

        Returns:
            List of normalised rule dicts
        """
        src_label = source or path.name
        suffix = path.suffix.lower()

        try:
            if suffix == ".pdf":
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages = reader.pages[:max_pages]
                text = "\n".join(p.extract_text() or "" for p in pages)
            elif suffix in (".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="ignore")
            else:
                print(
                    f"[MddRuleExtractor] Unsupported file type: {path.suffix}",
                    file=sys.stderr,
                )
                return []
        except Exception as e:
            print(f"[MddRuleExtractor] Could not read {path}: {e}", file=sys.stderr)
            return []

        return self.extract_from_text(text, src_label, verbose=verbose)
