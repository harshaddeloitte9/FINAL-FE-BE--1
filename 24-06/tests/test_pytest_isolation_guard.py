from pathlib import Path

import pytest

import conftest
import main
import persistence


def test_session_temp_storage_is_active():
    assert conftest._STATE["tmp"] is not None
    assert persistence.BACKEND_DIR == conftest._STATE["tmp"]
    assert persistence.APP_DATA_DIR == conftest._STATE["tmp"] / "app_data"
    assert persistence.ARTIFACTS_DIR == conftest._STATE["tmp"] / "app_data" / "artifacts"
    assert main.INTAKE_DRAFTS_DIR == conftest._STATE["tmp"] / "intake_drafts"


def test_guard_rejects_real_app_data_writes():
    real_target = Path(__file__).resolve().parents[1] / "app_data" / "guard_probe.json"
    with pytest.raises(RuntimeError, match="real app_data|protected app_data"):
        persistence._assert_write_allowed(real_target)


def test_guard_rejects_real_json_write_from_main():
    real_target = Path(__file__).resolve().parents[1] / "app_data" / "main_guard_probe.json"
    with pytest.raises(RuntimeError, match="real app_data|protected app_data"):
        main._assert_write_allowed(real_target)


def test_prefix_cleanup_only_removes_session_temp_dir(tmp_path):
    protected_root = tmp_path / "protected_root"
    protected_root.mkdir()
    (protected_root / "keep.txt").write_text("protected", encoding="utf-8")
    session_root = tmp_path / "session"
    session_root.mkdir()
    (session_root / "probe.txt").write_text("temp", encoding="utf-8")

    conftest._cleanup_session_temp(session_root)

    assert not session_root.exists()
    assert (protected_root / "keep.txt").exists()
