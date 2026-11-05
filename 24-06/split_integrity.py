"""
split_integrity.py — evidence for check R4.7 (train/test separation).

R4.7 used to append a hard-coded PASS. It is now built from executed
sub-checks, each comparing what the run actually did with an independent
recomputation:

  S1  Split indices available and train / validation / test disjoint
  S2  No test record identical (features + outcome) to a training record
  S3  Preprocessing depends on training rows only
  S4  Model fitted on training rows only
  S5  Feature-engineering plan learned from training rows only
  S6  Split reproducible (and matches the recorded training split)

Component checks (S3/S4) compare the fitted component's output on the test
rows with the output of an identical component fitted on the training rows
only. Equal → the component used no test rows. Different → refit once more:
if the two training-only refits agree, the original differs from a
training-only fit (FAIL); if they disagree, the procedure is not
deterministic and contamination cannot be confirmed either way
(NOT_ASSESSED). Any missing evidence is NOT_ASSESSED — never PASS.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

PASS, WARN, FAIL, NOT_ASSESSED, NOT_APPLICABLE = "PASS", "WARN", "FAIL", "NOT_ASSESSED", "NOT_APPLICABLE"
COMPONENT_TOLERANCE = 1e-9


def _sub(sub_id: str, title: str, status: str, detail: str) -> Dict[str, str]:
    return {"id": sub_id, "title": title, "status": status, "detail": detail}


def index_fingerprint(index: Iterable) -> str:
    return hashlib.sha256(",".join(str(i) for i in index).encode("utf-8")).hexdigest()


def check_disjoint(train_index, val_index, test_index) -> Dict[str, str]:
    title = "Train / validation / test rows disjoint"
    if train_index is None or test_index is None:
        return _sub("S1", title, NOT_ASSESSED, "Split row indices are not available for this run.")
    tr, te = set(train_index), set(test_index)
    va = set(val_index) if val_index is not None else set()
    overlaps = {"train∩test": len(tr & te), "validation∩test": len(va & te), "train∩validation": len(tr & va)}
    sizes = f"train {len(tr)}, validation {len(va)}, test {len(te)}"
    if any(overlaps.values()):
        return _sub("S1", title, FAIL, f"Overlapping rows — {', '.join(f'{k}: {v}' for k, v in overlaps.items() if v)} ({sizes}).")
    return _sub("S1", title, PASS, f"No shared row indices ({sizes}).")


def check_duplicate_records(X_train, y_train, X_test, y_test) -> Dict[str, str]:
    title = "No test record identical to a training record"
    if X_train is None or X_test is None or y_train is None or y_test is None:
        return _sub("S2", title, NOT_ASSESSED, "Raw split data is not available for this run.")
    try:
        cols = list(X_train.columns)
        train_h = set(pd.util.hash_pandas_object(X_train[cols].assign(__y=np.asarray(y_train)), index=False).tolist())
        test_h = pd.util.hash_pandas_object(X_test[cols].assign(__y=np.asarray(y_test)), index=False).tolist()
    except Exception as exc:
        return _sub("S2", title, NOT_ASSESSED, f"Records could not be compared: {type(exc).__name__}: {exc}")
    dup = sum(1 for h in test_h if h in train_h)
    if dup:
        return _sub("S2", title, WARN, f"{dup} of {len(test_h)} test records are identical (all features and outcome) to a training record.")
    return _sub("S2", title, PASS, f"None of the {len(test_h)} test records duplicates a training record.")


def _to_array(x) -> np.ndarray:
    if hasattr(x, "toarray"):
        x = x.toarray()
    if isinstance(x, (pd.DataFrame, pd.Series)):
        x = x.to_numpy()
    return np.asarray(x)


def _same(a, b) -> bool:
    a, b = _to_array(a), _to_array(b)
    if a.shape != b.shape:
        return False
    try:
        return bool(np.allclose(a.astype(float), b.astype(float), atol=COMPONENT_TOLERANCE, rtol=0.0, equal_nan=True))
    except (TypeError, ValueError):
        return bool(np.array_equal(a.astype(str), b.astype(str)))


def check_component(sub_id: str, title: str, fitted_output: Callable[[], Any],
                    training_only_output: Callable[[], Any], what: str) -> Dict[str, str]:
    """Compare the fitted component's output on the test rows with a fresh
    training-rows-only fit of the same component (see module docstring)."""
    try:
        original = fitted_output()
        refit_1 = training_only_output()
    except Exception as exc:
        return _sub(sub_id, title, NOT_ASSESSED, f"Could not be evaluated: {type(exc).__name__}: {exc}")
    if _same(original, refit_1):
        return _sub(sub_id, title, PASS, f"{what} on the test rows is identical to a fit on the training rows only.")
    try:
        refit_2 = training_only_output()
    except Exception as exc:
        return _sub(sub_id, title, NOT_ASSESSED, f"Repeat refit failed: {type(exc).__name__}: {exc}")
    if _same(refit_1, refit_2):
        return _sub(sub_id, title, FAIL,
                    f"{what} on the test rows differs from a deterministic fit on the training rows only — "
                    "rows outside the training set influenced it.")
    return _sub(sub_id, title, NOT_ASSESSED,
                f"Training-only refits are not reproducible (non-deterministic procedure), so {what.lower()} "
                "cannot be confirmed to use training rows only.")


def _plan_signature(plan: Any) -> str:
    return json.dumps(plan, sort_keys=True, default=str)


def check_fe_plan(plan_used: Any, training_only_plan: Optional[Callable[[], Any]], enabled: bool) -> Dict[str, str]:
    title = "Feature-engineering plan learned from training rows only"
    if not enabled:
        return _sub("S5", title, NOT_APPLICABLE, "Feature engineering was not used.")
    if plan_used is None or training_only_plan is None:
        return _sub("S5", title, NOT_ASSESSED, "The feature-engineering plan used is not available.")
    try:
        same = _plan_signature(plan_used) == _plan_signature(training_only_plan())
    except Exception as exc:
        return _sub("S5", title, NOT_ASSESSED, f"Plan could not be re-derived: {type(exc).__name__}: {exc}")
    if same:
        return _sub("S5", title, PASS, "Plan re-derived from the training rows only is identical to the plan used.")
    return _sub("S5", title, FAIL, "Plan used differs from the plan learned from the training rows only.")


def check_split_reproducible(test_index, resplit_test_index: Optional[Callable[[], Iterable]],
                             recorded_fingerprint: Optional[str] = None) -> Dict[str, str]:
    title = "Split reproducible" + (" and identical to the recorded training split" if recorded_fingerprint else "")
    if test_index is None or resplit_test_index is None:
        return _sub("S6", title, NOT_ASSESSED, "Split indices or split procedure not available.")
    try:
        again = index_fingerprint(resplit_test_index())
    except Exception as exc:
        return _sub("S6", title, NOT_ASSESSED, f"Split could not be re-derived: {type(exc).__name__}: {exc}")
    used = index_fingerprint(test_index)
    if again != used:
        return _sub("S6", title, FAIL, "Re-splitting with the same seed gives a different test set.")
    if recorded_fingerprint and used != recorded_fingerprint:
        return _sub("S6", title, FAIL, "Test set differs from the test set recorded when the model was trained.")
    return _sub("S6", title, PASS, f"Test-set fingerprint {used[:12]}… reproduced"
                + (" and matches the recorded training split." if recorded_fingerprint else "."))


REQUIRED_SUBCHECKS = ("S1", "S3", "S4", "S6")


def build_r47(subchecks: List[Dict[str, str]]) -> Dict[str, Any]:
    by_id = {s["id"]: s for s in subchecks}
    statuses = [s["status"] for s in subchecks]
    missing_required = [sid for sid in REQUIRED_SUBCHECKS if by_id.get(sid, {}).get("status") in (None, NOT_ASSESSED)]
    if FAIL in statuses:
        status = FAIL
    elif missing_required:
        status = NOT_ASSESSED
    elif WARN in statuses:
        status = WARN
    else:
        status = PASS
    return {
        "id": "R4.7",
        "title": "Train/test separation — no test contamination",
        "severity": "high",
        "status": status,
        "observed": " | ".join(f"{s['id']} {s['title']}: {s['status']}" for s in subchecks),
        "threshold": "Disjoint splits; preprocessing, feature engineering and model fitted on training rows only; reproducible split",
        "executed": True,
        "_subchecks": subchecks,
    }


def r47_not_assessed(reason: str) -> Dict[str, Any]:
    return {
        "id": "R4.7",
        "title": "Train/test separation — no test contamination",
        "severity": "high",
        "status": NOT_ASSESSED,
        "observed": reason,
        "threshold": "Disjoint splits; preprocessing, feature engineering and model fitted on training rows only; reproducible split",
        "executed": False,
        "_subchecks": [],
    }
