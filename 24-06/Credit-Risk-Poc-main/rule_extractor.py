"""
rule_extractor.py
Extracts structured compliance rules from regulatory document text using a local Ollama LLM.
Used by build_rules.py to auto-generate candidate rule entries from new documents.
"""

import json
import sys
from pathlib import Path
from typing import Optional


class RuleExtractor:
    """
    Extracts compliance rules from regulatory text chunks using a local LLM.
    The LLM is prompted to output one JSON object per line; malformed lines are skipped.
    """

    def __init__(self, model: str = "llama3.1"):
        self.model = model

    def extract_from_text(
        self,
        text: str,
        source: str,
        max_chars: int = 3000,
    ) -> list[dict]:
        """
        Send a regulatory text snippet to the LLM and parse extracted rules.
        Returns a list of raw rule dicts (may be incomplete — caller fills in ids etc.).
        """
        import ollama as _ollama

        snippet = text[:max_chars].strip()
        if not snippet:
            return []

        prompt = (
            f"You are a regulatory analyst reading an excerpt from '{source}'.\n"
            "Extract every distinct compliance rule or requirement you find.\n"
            "For each rule, output exactly ONE JSON object on a single line with these keys:\n"
            '  "rule_text": one-sentence rule description,\n'
            '  "check": snake_case identifier for the check (e.g. "missing_threshold"),\n'
            '  "severity": one of high / medium / low,\n'
            '  "stage": one of data / feature / training / evaluation\n\n'
            "Output only JSON lines — no markdown, no prose, no array brackets.\n"
            "If the excerpt contains no clear compliance rules, output nothing.\n\n"
            f"Excerpt:\n{snippet}"
        )

        try:
            response = _ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
        except Exception as e:
            print(f"[RuleExtractor] LLM call failed: {e}", file=sys.stderr)
            return []

        rules = []
        for line in content.splitlines():
            line = line.strip()
            # Accept lines that look like JSON objects
            if line.startswith("{") and line.endswith("}"):
                try:
                    rule = json.loads(line)
                    rule["source"] = source
                    rules.append(rule)
                except json.JSONDecodeError:
                    pass
        return rules

    def extract_from_file(
        self,
        path: Path,
        source: Optional[str] = None,
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Extract rules from a PDF or plain-text file.
        For PDFs only the first max_pages pages are processed to keep prompt size manageable.
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
                print(f"[RuleExtractor] Unsupported file type: {path.suffix}", file=sys.stderr)
                return []
        except Exception as e:
            print(f"[RuleExtractor] Could not read {path}: {e}", file=sys.stderr)
            return []

        return self.extract_from_text(text, src_label)
