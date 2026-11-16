"""Test isolation for the whole backend test suite (tests/ and root-level
test_*.py files alike).

* Before any test module is imported, every persistence path (validation and
  dev logs, artifacts, model inventory, saved MDDs, model artifacts) and the
  intake-drafts folder are redirected to a fresh temporary directory, which
  is deleted after the session.
* The real app_data/ and intake_drafts/ trees are fingerprinted (every file's
  size + modification time, plus the file list). Any change detected after a
  test fails that test; a change at the end fails the whole session.

Tests therefore can never write to real application data, and if anything
ever bypasses this redirection the run fails loudly instead of silently
polluting the production log (as earlier tests did).
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PROTECTED_ROOTS = (BACKEND_DIR / "app_data", BACKEND_DIR / "intake_drafts")
_STATE = {"tmp": None, "baseline": None}


def _cleanup_session_temp(tmp_dir):
    """Remove only the temp root created for this pytest session."""
    if tmp_dir is None:
        return
    tmp_dir = Path(tmp_dir)
    if not tmp_dir.exists():
        return
    if tmp_dir == BACKEND_DIR or tmp_dir == BACKEND_DIR / "app_data" or tmp_dir == BACKEND_DIR / "intake_drafts":
        raise RuntimeError(f"Refusing to remove project path {tmp_dir!s} during pytest cleanup")
    shutil.rmtree(tmp_dir, ignore_errors=True)


def protected_snapshot(roots=PROTECTED_ROOTS):
    """{path: (size, mtime_ns)} for every file under the protected roots,
    plus a marker per root so a root being created/removed is also seen."""
    snap = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            snap[f"<absent>{root}"] = None
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                    snap[path] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    snap[path] = "unreadable"
    return snap


def describe_changes(before, after, limit=10):
    added = [p for p in after if p not in before]
    removed = [p for p in before if p not in after]
    modified = [p for p in after if p in before and after[p] != before[p]]
    lines = [f"added: {p}" for p in added[:limit]] + [f"removed: {p}" for p in removed[:limit]] + \
            [f"modified: {p}" for p in modified[:limit]]
    return lines


def pytest_configure(config):
    tmp = Path(tempfile.mkdtemp(prefix="aegis_tests_"))
    (tmp / "app_data" / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp / "intake_drafts").mkdir(parents=True, exist_ok=True)
    source_demo = BACKEND_DIR / "demo_data"
    if source_demo.exists():
        shutil.copytree(source_demo, tmp / "demo_data", dirs_exist_ok=True)
    _STATE["tmp"] = tmp
    os.environ["AEGIS_TEST_STORAGE_ROOT"] = str(tmp)

    # Import application modules only after the session root is established so
    # they resolve their storage paths to the temp tree, not the real project.
    import persistence
    import main

    persistence.set_test_storage_root(tmp)
    main.INTAKE_DRAFTS_DIR = tmp / "intake_drafts"
    main.INTAKE_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    _STATE["baseline"] = protected_snapshot()


@pytest.fixture(scope="session", autouse=True)
def _isolate_main_module_paths():
    """main.py builds INTAKE_DRAFTS_DIR from its own directory at import time;
    point it at the temporary tree too."""
    import main
    main.INTAKE_DRAFTS_DIR = _STATE["tmp"] / "intake_drafts"
    main.INTAKE_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture(autouse=True)
def _restore_main_intake_dir_before_each_test():
    import main
    saved = main.INTAKE_DRAFTS_DIR
    main.INTAKE_DRAFTS_DIR = _STATE["tmp"] / "intake_drafts"
    main.INTAKE_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    main.INTAKE_DRAFTS_DIR = saved


@pytest.fixture(autouse=True)
def _guard_protected_data():
    yield
    changes = describe_changes(_STATE["baseline"], protected_snapshot())
    if changes:
        pytest.fail("Test modified protected application data:\n  " + "\n  ".join(changes), pytrace=False)


def pytest_sessionfinish(session, exitstatus):
    if _STATE["baseline"] is not None:
        changes = describe_changes(_STATE["baseline"], protected_snapshot())
        if changes:
            print("\n[conftest] PROTECTED APPLICATION DATA WAS MODIFIED DURING THE TEST RUN:\n  " + "\n  ".join(changes))
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    if _STATE["tmp"] is not None:
        _cleanup_session_temp(_STATE["tmp"])
    os.environ.pop("AEGIS_TEST_STORAGE_ROOT", None)
