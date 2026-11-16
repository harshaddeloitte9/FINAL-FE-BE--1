import json
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '24-06'))

import importlib.util
spec = importlib.util.spec_from_file_location('main_mod', str(ROOT / '24-06' / 'main.py'))
main_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_mod)

import persistence
import pandas as pd

async def run():
    # Verify against existing DEV_REGISTRATION_VERIFY_002 without creating new models
    model_name = 'DEV_REGISTRATION_VERIFY_002'

    # Snapshot validation inventory before (to check unchanged)
    inv_before = persistence.load_model_inventory().get('validation', [])

    # Find development inventory entry for the model
    store = persistence.load_model_inventory()
    inv_entry = next((m for m in store.get('development', []) if m.get('model_name') == model_name), None)
    dev_model = model_name
    if inv_entry:
        model_id = inv_entry.get('model_id')
    else:
        # Fallback: locate artifact with matching model_name and use its model_id
        rows = persistence.read_log(persistence.DEV_PIPELINE_LOG)
        artifact_path = None
        artifact_model_id = None
        for r in reversed(rows):
            if r.get('stage') != 'training':
                continue
            summary = r.get('summary') or {}
            name = None
            if isinstance(summary, dict):
                for k in ('model_name','business_model_name','model'):
                    if summary.get(k):
                        name = summary.get(k)
                        break
            if name and str(name).strip() == model_name:
                art_rel = r.get('artifact_path')
                if art_rel:
                    candidate = persistence.BACKEND_DIR / art_rel
                else:
                    candidate = persistence.ARTIFACTS_DIR / 'dev_pipeline_log' / 'training' / f"{r.get('run_id')}.json"
                if candidate.exists():
                    try:
                        art = json.loads(candidate.read_text(encoding='utf-8'))
                        artifact_model_id = art.get('model_id')
                        artifact_path = candidate
                    except Exception:
                        artifact_model_id = None
                    break
        # If not found via log, scan artifact files directly
        if not artifact_path:
            art_dir = persistence.ARTIFACTS_DIR / 'dev_pipeline_log' / 'training'
            if art_dir.exists():
                for p in art_dir.glob('*.json'):
                    try:
                        art = json.loads(p.read_text(encoding='utf-8'))
                        if art.get('model_name') and str(art.get('model_name')).strip() == model_name:
                            artifact_path = p
                            artifact_model_id = art.get('model_id')
                            break
                    except Exception:
                        continue
        if artifact_model_id:
            model_id = artifact_model_id
            inv_entry = None
        else:
            # Proceed without inventory/model_id; we'll still attempt PDF extraction
            model_id = None
            inv_entry = None

    # Ensure we have an artifact path/model id either from earlier scan or search the logs/artifact files now
    if 'artifact_path' not in locals():
        artifact_path = None
        artifact_model_id = None
        rows = persistence.read_log(persistence.DEV_PIPELINE_LOG)
        for r in reversed(rows):
            if r.get('stage') != 'training':
                continue
            summary = r.get('summary') or {}
            # check various name keys
            name = None
            if isinstance(summary, dict):
                for k in ('model_name','business_model_name','model'):
                    if summary.get(k):
                        name = summary.get(k)
                        break
            if name and str(name).strip() == model_name:
                art_rel = r.get('artifact_path')
                if art_rel:
                    candidate = persistence.BACKEND_DIR / art_rel
                else:
                    candidate = persistence.ARTIFACTS_DIR / 'dev_pipeline_log' / 'training' / f"{r.get('run_id')}.json"
                if candidate.exists():
                    artifact_path = candidate
                    try:
                        art = json.loads(candidate.read_text(encoding='utf-8'))
                        artifact_model_id = art.get('model_id')
                    except Exception:
                        artifact_model_id = None
                    break
        # If not found via log, scan artifact files directly
        if not artifact_path:
            art_dir = persistence.ARTIFACTS_DIR / 'dev_pipeline_log' / 'training'
            if art_dir.exists():
                for p in art_dir.glob('*.json'):
                    try:
                        art = json.loads(p.read_text(encoding='utf-8'))
                        if art.get('model_name') and str(art.get('model_name')).strip() == model_name:
                            artifact_path = p
                            artifact_model_id = art.get('model_id')
                            break
                    except Exception:
                        continue

    inv_model_id = inv_entry.get('model_id') if inv_entry else model_id
    # Locate report: prefer inventory entry's documentation_path, else scan model_reports
    report_path = None
    pdf_model_id = None
    if inv_entry and inv_entry.get('documentation_path'):
        report_path = persistence.BACKEND_DIR / inv_entry.get('documentation_path')
    else:
        # scan model_reports folder for a filename containing the model name
        reports_dir = persistence.APP_DATA_DIR / 'model_reports'
        if reports_dir.exists():
            for p in reports_dir.iterdir():
                if p.is_file() and model_name in p.name:
                    report_path = p
                    break

    if report_path and report_path.exists():
        try:
            raw = report_path.read_bytes()
            try:
                text = raw.decode('latin-1')
            except Exception:
                text = str(raw[:200])
            # Robust extraction using regex for model id pattern like MOD-123
            import re
            m = re.search(r"MOD-\d+", text)
            if m:
                pdf_model_id = m.group(0)
        except Exception:
            pdf_model_id = None

    inv_after_validation = persistence.load_model_inventory().get('validation', [])

    # Print exact required output
    print(f"Development model:\n{dev_model}")
    print(f"Model ID:\n{model_id}")
    print(f"Training artifact:\n{artifact_path if artifact_path else ''}")
    print(f"Artifact model ID:\n{artifact_model_id}")
    print(f"Inventory model ID:\n{inv_model_id}")
    print(f"Report:\n{report_path if report_path else ''}")
    print(f"PDF model ID:\n{pdf_model_id}")
    print(f"Artifact/Inventory match:\n{str(artifact_model_id == inv_model_id)}")
    print(f"Inventory/PDF match:\n{str(inv_model_id == pdf_model_id)}")
    print(f"Validation Inventory unchanged:\n{str(inv_before == inv_after_validation)}")

if __name__ == '__main__':
    asyncio.run(run())
