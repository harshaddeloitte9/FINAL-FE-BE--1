// Unit tests for src/lib/evaluation-evidence.ts (Batch 3D-F: evaluation
// identity display and stale-result protection on Stress, Bias, Benchmark).
//   node --test unit-tests/evaluation-evidence.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  MODE_REFIT,
  MODE_REGISTERED,
  cachedResultUsable,
  datasetFingerprint,
  describeEvidence,
  evaluationKey,
  evaluationReducer,
  initialEvaluationState,
  shortHash,
  type EvaluationState,
} from "../src/lib/evaluation-evidence.ts";

const REGISTERED = {
  run_id: "run-1", evaluation_mode: MODE_REGISTERED, registered_model_id: "MOD-001", training_run_id: "tr-19878811",
  dataset_sha256: "fc57aba5f093fd9a", test_index_sha256: "74709166c98f2398", bundle_sha256: "baddcb9e31d96b8d", test_rows: 450,
};
const REFIT = {
  run_id: "run-2", evaluation_mode: MODE_REFIT, registered_model_id: null, training_run_id: null,
  dataset_sha256: "aa11", test_index_sha256: "bb22", refit_algorithm: "Logistic Regression",
};
const row = (d: ReturnType<typeof describeEvidence>, label: string) => d.rows.find((r) => r.label === label);

// ── Evidence display ─────────────────────────────────────────────────────

test("registered evidence is shown as a registered scoring bundle with every identifier", () => {
  const d = describeEvidence(REGISTERED);
  assert.equal(d.kind, "registered");
  assert.equal(d.title, "Registered scoring bundle");
  assert.match(d.summary, /MOD-001/);
  assert.equal(row(d, "Registered model")?.value, "MOD-001");
  assert.equal(row(d, "Training run")?.value, "tr-19878811");
  assert.equal(row(d, "Bundle SHA-256")?.value, "baddcb9e31d96b8d");
  assert.equal(row(d, "Dataset fingerprint")?.value, "fc57aba5f093fd9a");
  assert.equal(row(d, "Test-row fingerprint")?.value, "74709166c98f2398");
});

test("an independent refit is never labelled as a registered model evaluation", () => {
  const d = describeEvidence(REFIT);
  assert.equal(d.kind, "refit");
  assert.equal(d.title, "Independent refit");
  assert.match(d.summary, /NOT an evaluation of a registered model/);
  assert.equal(row(d, "Registered model")?.value, null);
  assert.equal(row(d, "Registered model")?.note, "None — independent refit");
  assert.equal(row(d, "Bundle SHA-256"), undefined);
  assert.equal(row(d, "Refit algorithm")?.value, "Logistic Regression");
  // A refit that (wrongly) carries a model ID is still a refit.
  assert.equal(describeEvidence({ ...REFIT, registered_model_id: "MOD-001" }).kind, "refit");
});

test("missing evidence fields are shown as unavailable, never inferred", () => {
  const partial = describeEvidence({ evaluation_mode: MODE_REGISTERED, registered_model_id: "MOD-001" });
  assert.equal(partial.kind, "registered");
  for (const label of ["Training run", "Bundle SHA-256", "Dataset fingerprint", "Test-row fingerprint", "Run ID"]) {
    assert.equal(row(partial, label)?.value, null, label);
  }
  // Registered mode without the model ID cannot be presented as registered.
  assert.equal(describeEvidence({ evaluation_mode: MODE_REGISTERED }).kind, "unrecorded");
  for (const ev of [null, undefined, {}, { evaluation_mode: "something_else" }]) {
    const d = describeEvidence(ev as any);
    assert.equal(d.kind, "unrecorded");
    assert.equal(d.rows.length, 0);
  }
  assert.equal(shortHash("0123456789abcdef"), "0123456789ab…");
  assert.equal(shortHash("short"), "short");
});

// ── Result state ─────────────────────────────────────────────────────────

type Result = { status: string };
const PASS: Result = { status: "PASS" };
function run(steps: Parameters<typeof evaluationReducer<Result>>[1][]): EvaluationState<Result> {
  return steps.reduce((s, a) => evaluationReducer<Result>(s, a), initialEvaluationState<Result>());
}

test("bias PASS followed by a 409 clears the PASS result", () => {
  const passed = run([{ type: "reset", key: "A", token: 1 }, { type: "start", token: 2 }, { type: "success", token: 2, result: PASS }]);
  assert.equal(passed.result?.status, "PASS");
  const rerun = evaluationReducer(passed, { type: "start", token: 3 });
  assert.equal(rerun.result, null, "the old PASS disappears as soon as a new evaluation starts");
  assert.equal(rerun.status, "loading");
  const failed = evaluationReducer(rerun, { type: "failure", token: 3, error: "409 dataset_mismatch" });
  assert.equal(failed.status, "error");
  assert.equal(failed.result, null);
  assert.equal(failed.error, "409 dataset_mismatch");
});

test("bias PASS followed by a different dataset drops the earlier result", async () => {
  const keyA = evaluationKey({ registeredModelId: "MOD-001", trainingRunId: "tr", datasetKey: await datasetFingerprint(new Blob(["a,b\n1,2\n"])), extra: "gender" });
  const keyB = evaluationKey({ registeredModelId: "MOD-001", trainingRunId: "tr", datasetKey: await datasetFingerprint(new Blob(["a,b\n9,9\n"])), extra: "gender" });
  assert.notEqual(keyA, keyB);
  const cached = { ...PASS, evaluation_key: keyA };
  const passed = run([{ type: "reset", key: keyA, token: 1 }, { type: "start", token: 2 }, { type: "success", token: 2, result: PASS }]);
  const switched = evaluationReducer(passed, {
    type: "reset", key: keyB, token: 3, cached: cachedResultUsable(cached, keyB) ? cached : null,
  });
  assert.equal(switched.result, null);
  assert.equal(switched.status, "idle");
});

test("the cache is isolated by model, training run, dataset and analysed column", async () => {
  const ds1 = await datasetFingerprint(new Blob(["x\n1\n"]));
  const ds2 = await datasetFingerprint(new Blob(["x\n2\n"]));
  assert.equal(ds1, await datasetFingerprint(new Blob(["x\n1\n"])));                 // same bytes, same key
  const base = { registeredModelId: "MOD-001", trainingRunId: "tr-1", datasetKey: ds1, extra: "gender" };
  const key = evaluationKey(base);
  const cached = { evaluation_key: key };
  assert.equal(cachedResultUsable(cached, evaluationKey(base)), true);
  for (const change of [{ datasetKey: ds2 }, { registeredModelId: "MOD-002" }, { registeredModelId: null }, { trainingRunId: "tr-2" }, { extra: "age" }]) {
    assert.equal(cachedResultUsable(cached, evaluationKey({ ...base, ...change })), false, JSON.stringify(change));
  }
  assert.equal(evaluationKey({ ...base, datasetKey: null }), null);                    // unknown dataset → no key
  assert.equal(cachedResultUsable(cached, null), false);
  assert.equal(cachedResultUsable({}, key), false);                                    // legacy cache entry without a key
  assert.equal(cachedResultUsable(null, key), false);
});

test("a late response from an older request never overwrites the latest request", () => {
  let s = run([{ type: "reset", key: "A", token: 1 }, { type: "start", token: 2 }, { type: "start", token: 3 }]);
  s = evaluationReducer(s, { type: "success", token: 2, result: { status: "OLD PASS" } });
  assert.equal(s.status, "loading");
  assert.equal(s.result, null);
  s = evaluationReducer(s, { type: "failure", token: 3, error: "409" });
  s = evaluationReducer(s, { type: "success", token: 2, result: { status: "OLD PASS" } });
  assert.equal(s.status, "error");
  assert.equal(s.result, null);
  // A response arriving after the identity changed is ignored too.
  let t = run([{ type: "reset", key: "A", token: 1 }, { type: "start", token: 2 }, { type: "reset", key: "B", token: 3 }]);
  t = evaluationReducer(t, { type: "success", token: 2, result: PASS });
  assert.equal(t.result, null);
  assert.equal(t.key, "B");
});

test("stress and benchmark keys change with their own inputs (algorithm, challenger)", () => {
  const stressA = evaluationKey({ registeredModelId: null, trainingRunId: null, datasetKey: "d", extra: "Logistic Regression|default" });
  const stressB = evaluationKey({ registeredModelId: null, trainingRunId: null, datasetKey: "d", extra: "XGBoost|default" });
  const benchA = evaluationKey({ registeredModelId: "MOD-001", trainingRunId: "t", datasetKey: "d", extra: "LR|Random Forest|default" });
  const benchB = evaluationKey({ registeredModelId: "MOD-001", trainingRunId: "t", datasetKey: "d", extra: "LR|XGBoost|default" });
  assert.notEqual(stressA, stressB);
  assert.notEqual(benchA, benchB);
  // A cached benchmark restores only for its exact key.
  const restored = evaluationReducer(initialEvaluationState<Result>(), { type: "reset", key: benchA, token: 1,
    cached: cachedResultUsable({ evaluation_key: benchA }, benchA) ? PASS : null });
  assert.equal(restored.status, "success");
});

// ── The three pages actually use these rules ─────────────────────────────

const page = (name: string) => readFileSync(new URL(`../src/routes/${name}`, import.meta.url), "utf8");

test("stress, bias and benchmark pages use keyed state, show evidence identity and do not restore unscoped history", () => {
  for (const name of ["validation.stress.tsx", "validation.regulatory.tsx", "validation.performance.tsx"]) {
    const src = page(name);
    assert.match(src, /useEvaluationKey\(/, name);
    assert.match(src, /useEvaluationState</, name);
    assert.match(src, /<EvidenceIdentity/, name);
    assert.match(src, /\.isCurrent\(token\)/, name);
    assert.doesNotMatch(src, /useResumeState/, name);
  }
  const bias = page("validation.regulatory.tsx");
  assert.doesNotMatch(bias, /biasData/);                       // columns and result no longer share one state
  assert.match(bias, /evaluation_key: biasKey/);
  assert.match(page("validation.performance.tsx"), /evaluation_key: keyAtStart/);
});

test("manual shock: keyed result, evidence identity shown, registered raw inputs, never a refit by default", () => {
  const src = page("validation.stress.tsx");
  // The shock result is scoped to the stress identity plus the shock settings, and late responses are ignored.
  assert.match(src, /const shockKey = stressKey \? `\$\{stressKey\}\|shock\|\$\{shockFeature\}\|\$\{shockDirection\}\|\$\{shockMagnitude\}` : null;/);
  assert.match(src, /useEvaluationState<\{ result: any; evidence: EvaluationEvidence \| null \}>\(shockKey, null\)/);
  assert.match(src, /if \(!shock\.isCurrent\(token\)\) return;/);
  assert.doesNotMatch(src, /setShockResult\(/);
  // The evidence identity (registered bundle or independent refit) is shown with the result.
  assert.match(src, /<EvidenceIdentity evidence=\{shockEvidence\} title="Shock evidence identity" \/>/);
  assert.match(src, /not recorded and is not used in the validation verdict/);
  // Registered models offer only their shockable raw inputs; the algorithm is not required for them.
  assert.match(src, /stress\.state\.result\?\.shockable_features \?\? report\?\.numeric_features/);
  assert.match(src, /\(!algorithm && !registeredModelId\)/);
});
