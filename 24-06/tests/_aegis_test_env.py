"""Shared helpers for the validation regression tests: an isolated backend
(every persistence path redirected to a temp folder, real log + inventory
asserted unchanged) and real model training through /models/train."""
import io
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402
import persistence  # noqa: E402

LOG = persistence.VALIDATION_PIPELINE_LOG


def _fingerprint(path: Path):
    return (path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else None


@contextmanager
def isolated_backend(tmp_dir: Path):
    real = [BACKEND_DIR / "app_data" / name for name in
            (persistence.VALIDATION_PIPELINE_LOG, persistence.DEV_PIPELINE_LOG, persistence.MODEL_INVENTORY_FILENAME)]
    before = [_fingerprint(p) for p in real]
    (tmp_dir / "app_data" / "artifacts").mkdir(parents=True, exist_ok=True)
    mp = pytest.MonkeyPatch()
    mp.setattr(persistence, "BACKEND_DIR", tmp_dir)
    mp.setattr(persistence, "APP_DATA_DIR", tmp_dir / "app_data")
    mp.setattr(persistence, "ARTIFACTS_DIR", tmp_dir / "app_data" / "artifacts")
    mp.chdir(BACKEND_DIR)  # ValidationAgent2 reads rag_store/ relative to cwd
    try:
        yield TestClient(main.app)
    finally:
        mp.undo()
        assert [_fingerprint(p) for p in real] == before, "test wrote to the real app_data logs or inventory"


def dataset(n, k, coef, seed) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, k))
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(k)])
    df["default"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-(-1.2 + coef * x.sum(axis=1))))).astype(int)
    return df


def dataset_coefs(n, coefs, seed, drift_after=None) -> pd.DataFrame:
    """Logistic data with the given per-feature effects. With drift_after,
    rows after that fraction carry no signal (a genuine performance
    deterioration over time) and an application_date column is added."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, len(coefs)))
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(len(coefs))])
    logit = -1.2 + x @ np.asarray(coefs, dtype=float)
    if drift_after is not None:
        logit[int(n * drift_after):] = -1.2
        df["application_date"] = pd.date_range("2018-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    df["default"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


def train(client, csv: bytes, name: str, estimator="Logistic Regression", filename="dev.csv", **extra) -> dict:
    data = {"target_col": "default", "model_name": name, "estimator_name": estimator, "use_cv": "true"}
    data.update({k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v).lower() if isinstance(v, bool) else v) for k, v in extra.items()})
    r = client.post("/models/train", data=data, files={"file": (filename, io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lineage"]["captured"] is True, body["lineage"]
    return body


def replicate(client, csv: bytes, registered_model_id=None, filename="dev.csv", status=200, **extra) -> dict:
    data = {"target_col": "default"}
    if registered_model_id:
        data["registered_model_id"] = registered_model_id
    data.update(extra)
    r = client.post("/validation/replication", data=data, files={"file": (filename, io.BytesIO(csv), "text/csv")})
    assert r.status_code == status, r.text
    return r.json()


def dev_entry(model_id: str) -> dict:
    return next(m for m in persistence.load_model_inventory()["development"] if m["model_id"] == model_id)


def edit_dev_entry(model_id: str, mutate) -> None:
    store = persistence.load_model_inventory()
    entry = next(m for m in store["development"] if m["model_id"] == model_id)
    mutate(entry)
    persistence.save_model_inventory(store)


def append_legacy_row(log_file: str, stage: str, summary: dict, payload: dict, timestamp=None, run_id=None) -> str:
    """Write a row exactly as code before run-identity tracking did (no
    record_version) — into the isolated temp log only."""
    import csv
    import uuid
    import pandas as pd

    run_id = run_id if run_id is not None else str(uuid.uuid4())
    artifact_dir = persistence.ARTIFACTS_DIR / Path(log_file).stem / stage
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"{run_id or 'no-id'}.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    log_path = persistence.APP_DATA_DIR / log_file
    new_file = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["run_id", "timestamp", "stage", "summary", "artifact_path"])
        if new_file:
            writer.writeheader()
        writer.writerow({
            "run_id": run_id,
            "timestamp": timestamp or (pd.Timestamp.now() + pd.Timedelta(days=1)).isoformat(),
            "stage": stage,
            "summary": json.dumps(summary),
            "artifact_path": str(artifact.relative_to(persistence.BACKEND_DIR)),
        })
    return run_id


def latest(client, stage: str, status=200, **params) -> dict:
    r = client.get("/history/latest", params={"log_file": LOG, "stage": stage, **params})
    assert r.status_code == status, r.text
    return r.json()


def methodology(rep: dict) -> dict:
    return rep["report"]["replication"]["result"]["methodology"]


def lineage_status(rep: dict) -> dict:
    return {c["id"]: c["status"] for c in methodology(rep)["lineage_checks"]}
