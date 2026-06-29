"""
validation_agent2_core.py — backend-only ValidationAgent2 wrapper

Extracts pure-backend ValidationAgent2 logic from the POC, removing Streamlit
references and exposing a simplified API suitable for FastAPI endpoints.
"""
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

# We'll reuse many helper functions from the POC's ValidationAgent2 but keep
# this file small: import the original if present, otherwise provide a light
# fallback.
try:
    from Credit_Risk_Poc_validation_agent2 import ValidationAgent2  # unlikely path
except Exception:
    # Attempt to import the POC module directly if present in workspace
    try:
        from ..Credit_Risk_Poc_main.validation_agent2 import ValidationAgent2  # try relative
    except Exception:
        try:
            from Credit_Risk_Poc_main.validation_agent2 import ValidationAgent2
        except Exception:
            ValidationAgent2 = None


def run_validation_agent2(val_df: Optional[pd.DataFrame], intake_json: dict, mdd_text: str = "") -> dict:
    if ValidationAgent2 is None:
        # Minimal fallback: return an informative schema compatible with agent.get_full_report()
        findings = []
        summary = {"total": 0, "pass": 0, "warn": 0, "fail": 0, "pending": 0, "verdict": "SKIP"}
        return {"summary": summary, "findings_by_stage": {}, "all_findings": findings, "high_severity_fails": []}
    agent = ValidationAgent2()
    return agent.run_all_checks(val_df if val_df is not None else pd.DataFrame(), intake_json or {}, mdd_text or "")
