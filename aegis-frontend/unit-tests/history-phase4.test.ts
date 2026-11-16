// Phase 4 (H1–H4) — history restore scoping and legacy labelling.
//   node --test unit-tests/history-phase4.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  LEGACY_BADGE_TEXT,
  isLegacyRecord,
  modelDatasetParams,
  runMatchesModelAndDataset,
} from "../src/lib/history-record.ts";

const A = "a".repeat(64);
const B = "b".repeat(64);
const page = (name: string) => readFileSync(new URL(`../src/routes/${name}`, import.meta.url), "utf8");

test("H2/H3: a saved run matches only the same registered model and the same dataset bytes", () => {
  const run = { registered_model_id: "MOD-001", dataset_file_sha256: A };
  const cur = { registeredModelId: "MOD-001", datasetFileSha: A };
  assert.equal(runMatchesModelAndDataset(run, cur), true);
  assert.equal(runMatchesModelAndDataset(run, { ...cur, datasetFileSha: B }), false);        // other dataset
  assert.equal(runMatchesModelAndDataset(run, { ...cur, registeredModelId: "MOD-002" }), false); // other model
  assert.equal(runMatchesModelAndDataset({ registered_model_id: "MOD-001" }, cur), false);    // no fingerprint (older run)
  assert.equal(runMatchesModelAndDataset(run, { ...cur, datasetFileSha: null }), false);      // not known yet
  assert.equal(runMatchesModelAndDataset(run, { ...cur, registeredModelId: null }), false);   // no model selected
  assert.equal(runMatchesModelAndDataset(null, cur), false);
  assert.deepEqual(modelDatasetParams("MOD-001", A), { registered_model_id: "MOD-001", dataset_file_sha256: A });
  assert.equal(modelDatasetParams("MOD-001", null), null);
  assert.equal(modelDatasetParams(null, A), null);
});

test("H4: only rows the backend labels legacy get the Legacy badge", () => {
  assert.equal(isLegacyRecord({ record_status: "legacy" }), true);
  for (const r of [{ record_status: "current" }, {}, null, undefined]) assert.equal(isLegacyRecord(r as any), false);
  assert.equal(LEGACY_BADGE_TEXT, "Legacy");
});

test("H1: intake never applies the previous intake automatically; it is an explicit, labelled opt-in", () => {
  const src = page("validation.intake.tsx");
  assert.doesNotMatch(src, /setModelName\(resumedIntake\.model_name\)/);
  assert.doesNotMatch(src, /useEffect\(\(\) => \{\s*if \(!modelName\.trim\(\) && (resumedIntake|previousIntake)/);
  assert.match(src, /data-testid="previous-intake-offer"/);
  assert.match(src, /onClick=\{\(\) => setModelName\(previousIntakeName\)\}/);
  assert.match(src, /saved for any model; not linked to the selected model/);
});

test("H2: soundness restore is scoped by model + dataset and re-checked against the run's own record", () => {
  const src = page("validation.data-quality.tsx");
  assert.match(src, /modelDatasetParams\(soundnessRegisteredModelId, soundnessFileSha\)/);
  assert.match(src, /enabled: soundnessResumeParams !== null/);
  assert.match(src, /runMatchesModelAndDataset\(soundnessResumeMeta\?\.summary/);
  assert.doesNotMatch(src, /params: soundnessRegisteredModelId \? \{ registered_model_id: soundnessRegisteredModelId \}/);
});

test("H3: overview and home stage-done flags use model + dataset scoped stress runs", () => {
  for (const [name, params] of [["validation.index.tsx", "overviewStressParams"], ["index.tsx", "stressParams"]] as const) {
    const src = page(name);
    assert.match(src, /useDatasetFileSha\(/, name);
    assert.match(src, new RegExp(`enabled: ${params} !== null`), name);
    assert.match(src, /runMatchesModelAndDataset\(/, name);
    assert.doesNotMatch(src, /params: (overviewRegisteredModelId|registeredModelId) \? \{ registered_model_id: (overviewRegisteredModelId|registeredModelId) \} : undefined/, name);
  }
});

test("H4: Activity Log and Dashboard show the backend's legacy label (display only)", () => {
  for (const name of ["activity-log.tsx", "dashboard.tsx"]) {
    const src = page(name);
    assert.match(src, /record_status\?: "current" \| "legacy"/, name);
    assert.match(src, /data-testid="legacy-badge"/, name);
    assert.match(src, /isLegacyRecord\(/, name);
    assert.doesNotMatch(src, /\.filter\(\(?\w*\)? => !?isLegacyRecord/, name);   // legacy rows stay listed
  }
  assert.match(page("activity-log.tsx"), /data-testid="legacy-detail"/);
});
