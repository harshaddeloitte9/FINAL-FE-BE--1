import json
from pathlib import Path

import pytest

import persistence


def write_log_row(log_path: Path, run_id: str, timestamp: str, stage: str, summary: dict, artifact_rel: str):
    # Use csv.writer to correctly quote the JSON summary field
    import csv as _csv
    with open(log_path, 'a', newline='', encoding='utf-8') as f:
        writer = _csv.writer(f)
        writer.writerow([run_id, timestamp, stage, json.dumps(summary), artifact_rel])


def test_update_matches_correct_artifact(tmp_path, monkeypatch):
    # Use real APP_DATA_DIR inside repo to exercise actual function
    app_dir = persistence.APP_DATA_DIR
    artifacts_dir = persistence.ARTIFACTS_DIR / 'dev_pipeline_log' / 'training'
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Prepare two artifacts: one older matching model_name, one newer unrelated
    old_run = 'old-run-1111'
    new_run = 'new-run-2222'
    old_art = artifacts_dir / f"{old_run}.json"
    new_art = artifacts_dir / f"{new_run}.json"

    old_content = {"model_name": "Target Model", "some_field": 1}
    new_content = {"model_name": "Other Model", "some_field": 2}
    old_art.write_text(json.dumps(old_content, indent=2), encoding='utf-8')
    new_art.write_text(json.dumps(new_content, indent=2), encoding='utf-8')

    # Recreate dev_pipeline_log.csv with header and two rows (old then new)
    log_path = persistence.APP_DATA_DIR / persistence.DEV_PIPELINE_LOG
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(','.join(persistence._FIELDNAMES) + '\n')

    # timestamps chosen so old is earlier
    write_log_row(log_path, old_run, '2026-01-01T10:00:00', 'training', {'model_name': 'Target Model'}, str((persistence.BACKEND_DIR / old_art).relative_to(persistence.BACKEND_DIR)))
    write_log_row(log_path, new_run, '2026-01-02T10:00:00', 'training', {'model_name': 'Other Model'}, str((persistence.BACKEND_DIR / new_art).relative_to(persistence.BACKEND_DIR)))

    # Ensure no model_id present initially
    assert 'model_id' not in json.loads(old_art.read_text(encoding='utf-8'))
    assert 'model_id' not in json.loads(new_art.read_text(encoding='utf-8'))

    # Prepare last_development_registered.json to simulate registration timestamp
    last_reg = persistence.APP_DATA_DIR / 'last_development_registered.json'
    last_reg.write_text(json.dumps({'timestamp': '2026-01-01T10:01:00', 'model_id': 'DUMMY', 'model_name': 'Target Model'}), encoding='utf-8')

    # The immutable-artifact contract forbids rewriting training artifacts.
    # Registration must be logged as a separate event instead.
    with pytest.raises(persistence.ImmutableArtifactError):
        persistence._update_latest_training_artifact_with_model_id('Target Model', 'MOD-999', documentation_path='docs/target.pdf')

    # The older matching artifact remains unchanged.
    old_after = json.loads(old_art.read_text(encoding='utf-8'))
    assert 'model_id' not in old_after
    assert 'documentation_path' not in old_after

    # The newer unrelated artifact remains untouched.
    newer = json.loads(new_art.read_text(encoding='utf-8'))
    assert 'model_id' not in newer
    assert 'documentation_path' not in newer
