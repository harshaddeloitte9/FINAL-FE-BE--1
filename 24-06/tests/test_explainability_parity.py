"""E6: explainability parity with the registered model.

Explanations must use the exact registered scoring bundle, on exactly
identified rows, through exactly the registered scoring chain; predictions
used by explanations must equal the registered test evaluation's
predictions for the same rows; feature names are never invented, padded or
truncated; anything unavailable says why. Isolated temporary app_data,
synthetic data, real /models/train.
"""
import hashlib
import io

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

import _aegis_test_env as env
import explainability
import main
import model_lineage

_base = env.dataset_coefs(1200, [1.0, 0.6, 0.3, 0.2], seed=55)
_base.insert(0, "loan_id", np.arange(100000, 100000 + len(_base)))          # an ID column finalize_xy drops
_base["gender"] = np.where(np.arange(len(_base)) % 2 == 0, "F", "M")
_base.loc[_base.index % 9 == 0, "f1"] = np.nan                               # missing values for the imputer
CSV = env.to_csv(_base)
DF = pd.read_csv(io.BytesIO(CSV))
OTHER_CSV = env.to_csv(DF.assign(f0=DF["f0"] + 0.3))
OTHER = pd.read_csv(io.BytesIO(OTHER_CSV))                                    # the table the server parses
TRAIN_OPTS = dict(use_feature_engineering=True, drop_cols=["f3"], treatment_overrides={"f1": "statistical"})


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with env.isolated_backend(tmp_path_factory.mktemp("explain_parity")) as c:
        yield c


@pytest.fixture(scope="module")
def models(client):
    return {
        "lr": env.train(client, CSV, "Parity LR", estimator="Logistic Regression", **TRAIN_OPTS)["model_id"],
        "rf": env.train(client, CSV, "Parity RF", estimator="Random Forest", **TRAIN_OPTS)["model_id"],
    }


def explain(client, model_id, csv=CSV, status=200, **extra):
    data = {"target_col": "default", "registered_model_id": model_id, "compute_shap": "false", **extra}
    r = client.post("/models/explain", data=data, files={"file": ("dev.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == status, r.text
    return r.json()


def sha(proba) -> str:
    return hashlib.sha256(np.ascontiguousarray(proba, dtype=np.float64).tobytes()).hexdigest()


def registered_test(model_id):
    return model_lineage.registered_evaluation(DF, model_id, dataset_sha256=main.dataset_fingerprint(DF))


def contract(model_id):
    return env.dev_entry(model_id)["lineage_contract"]


def test_the_training_exercised_every_transformation(models):
    for mid in models.values():
        c = contract(mid)
        assert c["preprocessing"]["semantic_imputer_fitted"] is True
        assert c["preprocessing"]["drop_cols"] == ["f3"] and c["preprocessing"]["feature_engineering_enabled"] is True
        assert "loan_id" not in c["features"]["raw_feature_columns"]          # removed by finalize_xy at training


# ── Criteria 1-3: same model, same rows, same predictions ──────────────────

@pytest.mark.parametrize("kind", ["lr", "rf"])
def test_test_partition_predictions_equal_the_registered_test_evaluation(client, models, kind):
    mid = models[kind]
    c = contract(mid)
    scope = explain(client, mid)["explain_scope"]
    reg = registered_test(mid)
    assert scope["registered_model_id"] == mid and scope["training_run_id"] == c["training_run_id"]
    assert scope["bundle_sha256"] == c["artifact"]["sha256"]
    assert scope["rows"] == "registered_test_partition"
    assert scope["row_index_sha256"] == c["split"]["test_index_sha256"] == reg["identity"]["test_index_sha256"]
    assert scope["row_count"] == c["split"]["test_rows"]
    assert scope["model_input_columns"] == c["features"]["model_input_columns"]
    # Identical rows, identical registered model version, identical scoring chain.
    assert scope["predictions_sha256"] == sha(reg["y_proba"])
    # ...and they are the TEST-partition predictions behind the metrics recorded at training.
    assert round(float(roc_auc_score(reg["y_test"], reg["y_proba"])), 4) == c["development_metrics"]["roc_auc"]


def test_other_dataset_uses_recorded_raw_columns_in_recorded_order(client, models):
    mid = models["lr"]
    c = contract(mid)
    scope = explain(client, mid, csv=OTHER_CSV)["explain_scope"]
    assert scope["rows"] == "supplied_dataset" and scope["row_count"] == len(OTHER)
    bundle = model_lineage.load_registered_scoring_bundle(mid)["bundle"]
    expected = bundle["pipeline"].predict_proba(model_lineage._transform_for_bundle(bundle, OTHER[c["features"]["raw_feature_columns"]]))[:, 1]
    assert scope["predictions_sha256"] == sha(expected)
    # Adversarial: extra columns (ID, junk) and a shuffled column order change nothing.
    shuffled = OTHER.assign(junk=7.0)[list(reversed(list(OTHER.columns))) + ["junk"]]
    again = explain(client, mid, csv=env.to_csv(shuffled))["explain_scope"]
    assert again["predictions_sha256"] == scope["predictions_sha256"]


def test_missing_raw_inputs_are_refused_not_reconstructed(client, models):
    body = explain(client, models["lr"], csv=env.to_csv(OTHER.drop(columns=["f2"])), status=409)
    assert "feature_mismatch" in body["detail"] and "f2" in body["detail"]


def test_unrecorded_raw_inputs_are_refused_for_other_datasets(client):
    mid = env.train(client, CSV, "Parity Unrecorded")["model_id"]
    env.edit_dev_entry(mid, lambda e: e["lineage_contract"]["features"].pop("raw_feature_columns"))
    body = explain(client, mid, csv=OTHER_CSV, status=409)
    assert "explain_inputs_unverifiable" in body["detail"]


def test_a_split_that_does_not_reproduce_is_refused(client):
    mid = env.train(client, CSV, "Parity Split")["model_id"]
    env.edit_dev_entry(mid, lambda e: e["lineage_contract"]["split"].update(test_index_sha256="0" * 64))
    assert "split_mismatch" in explain(client, mid, status=409)["detail"]


# ── Criteria 4-6: SHAP input parity, row alignment, threshold ─────────────

@pytest.mark.parametrize("kind", ["rf", "lr"])
def test_shap_inputs_rows_and_predictions_align_with_the_registered_model(client, models, kind):
    mid = models[kind]
    body = explain(client, mid, compute_shap="true", max_shap_samples="40", sample_idx="3")
    shap, scope = body["shap"], body["explain_scope"]
    assert shap["shap_available"] is True, shap
    reg = registered_test(mid)
    pipeline = reg["pipeline"]
    # The explained rows are the first rows of the recorded test partition, in order.
    assert shap["explained_row_index"] == list(reg["X_test"].index[: shap["explained_rows"]])
    assert shap["sample_row_index"] == reg["X_test"].index[3]
    assert shap["sample_predicted_pd"] == float(reg["y_proba"][3])
    # The SHAP feature values are exactly the preprocessor's output for that row.
    transformed = pipeline.named_steps["preprocessor"].transform(reg["X_test"].iloc[[3]])
    names, reason = explainability.resolve_model_input_names(pipeline, transformed.shape[1])
    assert reason is None and list(shap["sample_features"]) == names
    np.testing.assert_allclose([shap["sample_features"][n] for n in names], np.asarray(transformed)[0], rtol=0, atol=1e-12)
    # Never invented names.
    assert {r["Feature"] for r in shap["shap_mean_abs"]} <= set(names)
    # Threshold: the registered operating threshold, exact, with its source.
    c = contract(mid)
    assert scope["operating_threshold"] == c["training"]["threshold"] and scope["threshold_status"] == "PASS"
    assert f"threshold = {c['training']['threshold']:.4f}; f1_max on validation" in shap["sample_reasoning"]


def test_sample_idx_out_of_range_is_rejected(client, models):
    body = explain(client, models["rf"], compute_shap="true", max_shap_samples="20", sample_idx="20", status=400)
    assert "sample_idx" in body["detail"]


def test_missing_threshold_is_labelled_nominal(client):
    mid = env.train(client, CSV, "Parity No Threshold", estimator="Random Forest")["model_id"]

    def strip(entry):
        entry["lineage_contract"]["training"]["threshold"] = None
        entry["lineage_contract"]["training"]["threshold_provenance"] = None
        entry["lineage_contract"]["development_metrics"].pop("threshold_used", None)
    env.edit_dev_entry(mid, strip)
    body = explain(client, mid, compute_shap="true", max_shap_samples="10")
    assert body["explain_scope"]["threshold_status"] == "FAIL" and body["explain_scope"]["operating_threshold"] == 0.5
    assert "nominal 0.5, not the model's recorded threshold" in body["shap"]["sample_reasoning"]


# ── Criteria 4 & 7: strict names, explicit reasons ─────────────────────────

def test_unresolvable_names_make_outputs_unavailable_with_a_reason(client, models, monkeypatch):
    real = explainability.resolve_feature_names
    monkeypatch.setattr(explainability, "resolve_feature_names", lambda p: real(p)[:-1])     # one name short
    body = explain(client, models["rf"], compute_shap="true", max_shap_samples="10")
    assert body["feature_importance"] == []
    assert "not shown rather than padded or truncated" in body["explain_scope"]["feature_importance_unavailable_reason"]
    assert body["shap"]["shap_available"] is False
    assert "not shown rather than padded or truncated" in body["shap"]["shap_unavailable_reason"]
    assert "padded" in body["explain_scope"]["shap_unavailable_reason"]


def test_name_resolution_units_and_backward_compatibility(models):
    pipeline = model_lineage.load_registered_scoring_bundle(models["rf"])["bundle"]["pipeline"]
    names = explainability.resolve_feature_names(pipeline)
    assert explainability.resolve_model_input_names(pipeline, len(names)) == (names, None)
    assert explainability.resolve_model_input_names(pipeline, len(names) + 1)[0] is None
    df = explainability.extract_feature_importance(pipeline)                     # old entry point: DataFrame or None
    assert isinstance(df, pd.DataFrame) and set(df["Feature"]) == set(names)
    assert not any(n.startswith(("engineered_feat_", "feature_")) for n in df["Feature"])
    assert explainability.compute_shap_values(pipeline, registered_test(models["rf"])["X_test"], max_samples=5) is not None


def test_shap_refuses_an_input_path_that_does_not_reproduce_the_pipeline(models):
    real = model_lineage.load_registered_scoring_bundle(models["rf"])["bundle"]["pipeline"]
    X = registered_test(models["rf"])["X_test"].head(5)

    class Drifted:                                          # the "model" step disagrees with the pipeline
        def __init__(self, model):
            self.model = model

        def predict_proba(self, X):
            p = self.model.predict_proba(X).copy()
            p[:, 1] = np.clip(p[:, 1] + 0.01, 0, 1)
            p[:, 0] = 1 - p[:, 1]
            return p

    class FakePipeline:
        def __init__(self, inner):
            self.inner = inner
            self.named_steps = {"preprocessor": inner.named_steps["preprocessor"], "model": Drifted(inner.named_steps["model"])}
            self.steps = list(self.named_steps.items())

        def predict_proba(self, X):
            return self.inner.predict_proba(X)

    result, reason = explainability.compute_shap_values_with_reason(FakePipeline(real), X, max_samples=5)
    assert result is None and "does not reproduce the pipeline's predictions" in reason
