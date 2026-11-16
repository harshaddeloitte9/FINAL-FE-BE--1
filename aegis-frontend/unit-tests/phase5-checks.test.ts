// Phase 5 (G2, G3) — curve provenance and stress sensitivity labels.
//   node --test unit-tests/phase5-checks.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { describeCurveProvenance, describeSensitivityMethod } from "../src/lib/check-provenance.ts";

const page = (name: string) => readFileSync(new URL(`../src/routes/${name}`, import.meta.url), "utf8");

test("G2: curve provenance names the predictions, partition, rows and fingerprints", () => {
  const text = describeCurveProvenance({
    prediction_source: "registered_bundle", evaluation_partition: "test", rows: 450,
    dataset_sha256: "d".repeat(64), test_index_sha256: "a".repeat(64),
  });
  assert.equal(text, `Test partition · 450 rows · registered model (verified scoring bundle) · test rows ${"a".repeat(12)}… · dataset ${"d".repeat(12)}…`);
  assert.match(describeCurveProvenance({ prediction_source: "independent_retrain", evaluation_partition: "test", rows: 1 }), /independent retrain from the recorded configuration/);
  assert.match(describeCurveProvenance({ prediction_source: "unregistered_refit" }), /unregistered refit/);
  assert.match(describeCurveProvenance({ prediction_source: "challenger_refit" }), /challenger refit/);
  for (const missing of [null, undefined, {}]) {
    assert.match(describeCurveProvenance(missing as any), /not recorded/);                 // older results: honest, no guess
  }
});

test("G3: permutation is never described as removal, ablation or retraining", () => {
  const perm = describeSensitivityMethod("permutation");
  assert.match(perm.title, /permuted/);
  assert.match(perm.sub, /no refit/);
  assert.doesNotMatch(`${perm.title} ${perm.sub}`, /retrain|ablation|feature removal and/i);
  const refit = describeSensitivityMethod("removal_refit");
  assert.match(refit.title, /removal and retraining/);
  assert.match(refit.sub, /retrained/);
  assert.match(describeSensitivityMethod(undefined).sub, /not recorded/);
});

test("pages use the provenance and method labels; verdict policy 7", () => {
  const stress = page("validation.stress.tsx");
  assert.match(stress, /describeSensitivityMethod\(report\?\.sensitivity\?\.method\)\.title/);
  assert.doesNotMatch(stress, /From Stage 3 ablation/);
  assert.doesNotMatch(stress, /title="Sensitivity — AUC drop on feature removal"/);
  const rep = page("validation.challenger.tsx");
  assert.match(rep, /describeCurveProvenance\(performanceReport\?\.roc_curve\?\.provenance\)/);
  assert.match(rep, /describeCurveProvenance\(performanceReport\?\.pr_curve\?\.provenance\)/);
  const perf = page("validation.performance.tsx");
  assert.match(perf, /Champion: \$\{describeCurveProvenance\(payload\?\.report\?\.roc_curve\?\.provenance\)\}/);
  assert.match(perf, /Challenger: \$\{describeCurveProvenance\(benchmarkResponse\?\.roc_curve\?\.provenance\)\}/);
  assert.match(page("validation.findings.tsx"), /const MIN_VERDICT_POLICY_VERSION = 7;/);
});
