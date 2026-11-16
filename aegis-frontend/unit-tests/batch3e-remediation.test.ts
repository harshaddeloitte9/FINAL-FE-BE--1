// Unit tests for Batch 3E frontend remediation:
//   E7  development-page resumes scoped to dataset file / model / training run
//   E3/E5/E13/E14  threshold provenance and split method labels
//   E12 previews use the locked-in split configuration
//   node --test unit-tests/batch3e-remediation.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { devResumeParams, resumedPayloadMatches } from "../src/lib/dev-resume-scope.ts";
import { describeSplit, describeThresholdProvenance } from "../src/lib/methodology-labels.ts";
import { DEFAULT_SPLIT, appendSplitConfig, resolveSplitConfig, sameSplit } from "../src/lib/split-config.ts";

const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);

// ── E7: scoped resume ────────────────────────────────────────────────────

test("no resume is requested until the dataset (and, for model pages, the model) is known", () => {
  assert.equal(devResumeParams({ fileSha: null }), null);
  assert.deepEqual(devResumeParams({ fileSha: SHA_A }), { dataset_file_sha256: SHA_A });
  assert.equal(devResumeParams({ fileSha: SHA_A, requireModel: true }), null);
  assert.equal(devResumeParams({ fileSha: SHA_A, registeredModelId: "MOD-1", requireModel: true }), null);   // run unknown
  assert.deepEqual(devResumeParams({ fileSha: SHA_A, registeredModelId: "MOD-1", trainingRunId: "tr-1", requireModel: true }), {
    dataset_file_sha256: SHA_A, registered_model_id: "MOD-1", training_run_id: "tr-1",
  });
});

test("a resumed payload from another dataset, model or training run is rejected", () => {
  const explain = { explain_scope: { dataset_file_sha256: SHA_A, registered_model_id: "MOD-1", training_run_id: "tr-1" } };
  const scope = { fileSha: SHA_A, registeredModelId: "MOD-1", trainingRunId: "tr-1", requireModel: true };
  assert.equal(resumedPayloadMatches(explain, scope), true);
  assert.equal(resumedPayloadMatches(explain, { ...scope, fileSha: SHA_B }), false);
  assert.equal(resumedPayloadMatches(explain, { ...scope, registeredModelId: "MOD-2" }), false);
  assert.equal(resumedPayloadMatches(explain, { ...scope, trainingRunId: "tr-2" }), false);
  // Preprocessing / feature payloads carry dataset_identity.
  assert.equal(resumedPayloadMatches({ dataset_identity: { dataset_file_sha256: SHA_A } }, { fileSha: SHA_A }), true);
  assert.equal(resumedPayloadMatches({ dataset_identity: { dataset_file_sha256: SHA_B } }, { fileSha: SHA_A }), false);
  // Legacy payloads without identity never match; no dataset → nothing matches.
  for (const legacy of [{}, { feature_importance: [] }, null]) {
    assert.equal(resumedPayloadMatches(legacy, { fileSha: SHA_A }), false);
  }
  assert.equal(resumedPayloadMatches({ dataset_identity: { dataset_file_sha256: SHA_A } }, { fileSha: null }), false);
  // A model page cannot accept a payload that records no model.
  assert.equal(resumedPayloadMatches({ dataset_identity: { dataset_file_sha256: SHA_A } }, { fileSha: SHA_A, requireModel: true }), false);
});

// ── E3 / E5 / E13 / E14: labels show exactly what was recorded ───────────

test("threshold provenance labels", () => {
  const v = describeThresholdProvenance({ method: "f1_max", value: 0.3125, source_partition: "validation", rows: 225 });
  assert.equal(v.warning, false);
  assert.match(v.text, /0\.313/);
  assert.match(v.text, /validation partition \(225 rows\); test rows not used/);
  assert.match(describeThresholdProvenance({ method: "manual", value: 0.4 }).text, /set manually/);
  const d = describeThresholdProvenance({ method: "default_0.5", value: 0.5, reason: "single class" });
  assert.equal(d.warning, true);
  assert.match(d.text, /nominal default: single class/);
  for (const missing of [null, undefined, {}]) assert.equal(describeThresholdProvenance(missing as any).warning, true);
  assert.equal(describeThresholdProvenance({ method: "f1_max", value: 0.3, source_partition: "evaluated_data_in_sample" }).warning, true);
});

test("split method labels flag fallbacks and show temporal boundaries", () => {
  assert.deepEqual(describeSplit({ strategy: "stratified_random", achieved: "stratified", random_seed: 42 }), { text: "Stratified random (seed 42)", warning: false });
  const fb = describeSplit({ strategy: "stratified_random", degraded: true, random_seed: 7, fallbacks: [{ partition: "test", reason: "class too small" }] });
  assert.equal(fb.warning, true);
  assert.match(fb.text, /fell back to unstratified: test: class too small/);
  const t = describeSplit({ strategy: "temporal", date_col: "application_date",
    boundaries: { train: ["2019-01-01", "2021-06-30"], validation: ["2021-07-01", "2021-12-31"], test: ["2022-01-01", "2022-06-30"] } });
  assert.equal(t.warning, false);
  assert.match(t.text, /Chronological on application_date: train 2019-01-01 to 2021-06-30, test 2022-01-01 to 2022-06-30/);
  assert.equal(describeSplit(null).warning, true);
  assert.equal(describeSplit({ strategy: "temporal", degraded: true, fallbacks: [{ partition: "test", reason: "single class" }] }).warning, true);
});

// ── E12: preview split settings ──────────────────────────────────────────

test("previews use the first complete split configuration, else the backend defaults", () => {
  assert.deepEqual(resolveSplitConfig({ test_size: 0.2, val_size: 0.1, random_seed: 7 }), { test_size: 0.2, val_size: 0.1, random_seed: 7 });
  assert.deepEqual(resolveSplitConfig({ test_size: 0.2 }, { test_size: 0.3, val_size: 0.1, random_seed: 1 }), { test_size: 0.3, val_size: 0.1, random_seed: 1 });
  assert.deepEqual(resolveSplitConfig(null, undefined), DEFAULT_SPLIT);
  const form = appendSplitConfig(new FormData(), { test_size: 0.2, val_size: 0.1, random_seed: 7 });
  assert.equal(form.get("random_seed"), "7");
  assert.equal(form.get("test_size"), "0.2");
  assert.equal(sameSplit({ test_size: 0.2, val_size: 0.1, random_seed: 7 }, { test_size: 0.2, val_size: 0.1, random_seed: 7 }), true);
  assert.equal(sameSplit({ test_size: 0.2, val_size: 0.1, random_seed: 42 }, { test_size: 0.2, val_size: 0.1, random_seed: 7 }), false);
  assert.equal(sameSplit(undefined, DEFAULT_SPLIT), false);
});

// ── The pages actually use these rules ───────────────────────────────────

const page = (name: string) => readFileSync(new URL(`../src/routes/${name}`, import.meta.url), "utf8");

test("development pages never restore an unscoped run", () => {
  const unscoped = /useResumeState<[^>]*>\(\s*"dev_pipeline_log\.csv",\s*"[a-z_]+"\s*\)/;
  for (const name of ["data-preparation.tsx", "explainability.tsx", "model-training-evaluation.tsx"]) {
    const src = page(name);
    assert.doesNotMatch(src, unscoped, name);
    assert.match(src, /useDatasetFileSha\(file\)/, name);
    assert.match(src, /devResumeParams\(/, name);
    assert.match(src, /resumedPayloadMatches\(/, name);
  }
  const mte = page("model-training-evaluation.tsx");
  assert.match(mte, /"registration"/);                         // model ID from the registration event (E9)
  assert.match(page("explainability.tsx"), /requireModel: true/);
});

test("training sends the explicit split strategy and shows threshold / split provenance", () => {
  const src = page("model-training-evaluation.tsx");
  assert.match(src, /trainForm\.append\("split_strategy", "temporal"\)/);
  assert.match(src, /trainForm\.append\("temporal_date_col", config\.temporal_date_col\)/);
  assert.match(src, /config\.split_strategy === "temporal" && config\.temporal_date_col/);   // never sent without a column
  assert.match(src, /data-testid="threshold-provenance"/);
  assert.match(src, /data-testid="split-method"/);
  assert.match(src, /data-testid="evaluation-threshold-provenance"/);
  assert.doesNotMatch(src, /Optimize threshold automatically/);
});

test("previews send the split configuration", () => {
  const prep = page("data-preparation.tsx");
  assert.equal((prep.match(/appendSplitConfig\(form, splitConfig\)/g) ?? []).length, 2);
  assert.match(page("explainability.tsx"), /appendSplitConfig\(form, resolveSplitConfig\(trainingConfig/);
  assert.match(page("model-training-evaluation.tsx"), /appendSplitConfig\(form, resolveSplitConfig\(splitConfig\)\)/);
});

test("explainability: no browser split/FE inputs, identity and unavailable reasons shown", () => {
  const src = page("explainability.tsx");
  const explainParams = src.slice(src.indexOf("const explainParams = () => {"), src.indexOf("return form;", src.indexOf("const explainParams = () => {")));
  for (const ignored of ["use_feature_engineering", "test_size", "val_size", "random_seed"]) {
    assert.equal(explainParams.includes(`form.append("${ignored}"`), false, ignored);
  }
  assert.match(src, /data-testid="explain-scope"/);
  assert.match(src, /<EvidenceIdentity\s+title="Explanation identity"/);
  assert.match(src, /test_index_sha256: data\.explain_scope\.row_index_sha256/);
  assert.match(src, /data\.explain_scope\.threshold_source/);
  assert.match(src, /feature_importance_unavailable_reason/);
  assert.match(src, /SHAP is unavailable: \$\{response\.shap\.shap_unavailable_reason/);
  assert.doesNotMatch(src, /SHAP computation failed or not supported for this model/);
});
