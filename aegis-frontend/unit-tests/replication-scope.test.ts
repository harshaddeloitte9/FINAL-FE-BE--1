// Unit tests for audit findings D1 / D2 / D3 on the Model Replication page.
//   node --test unit-tests/replication-scope.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { referenceVerificationText, replicationRestoreUsable } from "../src/lib/replication-scope.ts";

const A = "a".repeat(64);
const B = "b".repeat(64);

test("D1: a saved run is shown only for the same registered model and the same dataset bytes", () => {
  const run = { registered_model_id: "MOD-001", dataset_file_sha256: A };
  assert.equal(replicationRestoreUsable(run, { registeredModelId: "MOD-001", datasetFileSha: A }), true);
  assert.equal(replicationRestoreUsable(run, { registeredModelId: "MOD-001", datasetFileSha: B }), false);   // other dataset
  assert.equal(replicationRestoreUsable(run, { registeredModelId: "MOD-002", datasetFileSha: A }), false);   // other model
  assert.equal(replicationRestoreUsable(run, { registeredModelId: null, datasetFileSha: A }), false);        // none selected
  assert.equal(replicationRestoreUsable(run, { registeredModelId: "MOD-001", datasetFileSha: null }), false); // not known yet
  assert.equal(replicationRestoreUsable({ registered_model_id: "MOD-001" }, { registeredModelId: "MOD-001", datasetFileSha: A }), false); // older run
  assert.equal(replicationRestoreUsable(null, { registeredModelId: null, datasetFileSha: A }), false);
  // An unregistered run restores only when no registered model is selected.
  assert.equal(replicationRestoreUsable({ registered_model_id: null, dataset_file_sha256: A }, { registeredModelId: null, datasetFileSha: A }), true);
});

test("D2: only server-extracted sources are described as verified", () => {
  assert.match(referenceVerificationText("server_extracted"), /^verified by the server/);
  assert.match(referenceVerificationText("browser_reported"), /browser-reported, not verified by the server/);
  for (const unknown of [undefined, null, "something"]) {
    assert.match(referenceVerificationText(unknown as any), /verification not recorded/);
    assert.doesNotMatch(referenceVerificationText(unknown as any), /^verified/);
  }
});

const src = readFileSync(new URL("../src/routes/validation.challenger.tsx", import.meta.url), "utf8");

test("D1: the page scopes restore, cache and display to model + dataset", () => {
  assert.match(src, /const datasetFileSha = useDatasetFileSha\(datasetKeyBlob\)/);
  assert.match(src, /registered_model_id: resumeRegisteredModelId, dataset_file_sha256: datasetFileSha/);
  assert.match(src, /business_model_name: resumeModelName, dataset_name: resumeDatasetName, dataset_file_sha256: datasetFileSha/);
  assert.match(src, /const resumeParams: Record<string, string> \| undefined = !datasetFileSha\s+\? undefined/);
  // Cached result and resumed row both re-checked with the same rule.
  assert.equal((src.match(/replicationRestoreUsable\(/g) ?? []).length, 2);
  // The cache is no longer applied synchronously on mount; a dataset/model change clears what is shown.
  assert.doesNotMatch(src, /cachedStage4Usable \? \(\(cachedStage4!\.replication/);
  assert.match(src, /if \(shownIdentity && shownIdentity !== currentIdentity\) \{/);
});

test("D2 / D3: verification shown per reference value; replaced reviewer values listed", () => {
  assert.match(src, /referenceVerificationText\(referenceUsed\?\.verification\?\.\[key\]\)/);
  assert.match(src, /data-testid="reference-replacements"/);
  assert.match(src, /formatValue\(r\.previous_value\)\} \(\{r\.previous_source_label \?\? r\.previous_source\}\) → \{formatValue\(r\.new_value\)\}/);
});
