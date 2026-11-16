import test from "node:test";
import assert from "node:assert/strict";

import { buildEvidenceStatus, buildRequiredArtifactState, buildSubmissionBlockedReason } from "../src/lib/intake-warning.ts";

test("required evidence status marks the card complete only when every mandatory artifact is uploaded", () => {
  const complete = buildEvidenceStatus({ uploaded: 3, total: 3 });
  const incomplete = buildEvidenceStatus({ uploaded: 2, total: 3 });

  assert.equal(complete.label, "Required evidence complete");
  assert.equal(complete.detail, "3 of 3 required artifacts uploaded");
  assert.equal(incomplete.label, "Required evidence incomplete");
  assert.equal(incomplete.detail, "2 of 3 required artifacts uploaded");
});

test("demo-only intake counts only dataset and MDD as required and keeps training code marked as demo-only", () => {
  const demo = buildRequiredArtifactState({
    isDemo: true,
    datasetUploaded: true,
    mddUploaded: true,
    trainingCodeUploaded: false,
  });
  const real = buildRequiredArtifactState({
    isDemo: false,
    datasetUploaded: true,
    mddUploaded: true,
    trainingCodeUploaded: false,
  });

  assert.equal(demo.label, "Required evidence complete");
  assert.equal(demo.detail, "2 of 2 required artifacts uploaded");
  assert.deepEqual(demo.missingRequiredArtifacts, []);
  assert.equal(demo.trainingCodeStatus, "Not supplied — demo");

  assert.equal(real.label, "Required evidence incomplete");
  assert.equal(real.detail, "2 of 3 required artifacts uploaded");
  assert.deepEqual(real.missingRequiredArtifacts, ["Training Code / Scripts"]);
  assert.equal(real.trainingCodeStatus, "Pending");
});

test("single missing required artifact shows the specific remaining requirement", () => {
  const reason = buildSubmissionBlockedReason({
    metadataReady: true,
    missingRequiredArtifacts: ["Training Code / Scripts"],
    allAttested: true,
    chkAttestation: true,
  });

  assert.equal(reason, "Upload the required training code / scripts to proceed.");
});

test("all required artifacts complete but governance remains incomplete shows the governance warning", () => {
  const reason = buildSubmissionBlockedReason({
    metadataReady: true,
    missingRequiredArtifacts: [],
    allAttested: false,
    chkAttestation: true,
  });

  assert.equal(reason, "Complete all governance controls.");
});

test("artifact and governance gaps are explained together", () => {
  const reason = buildSubmissionBlockedReason({
    metadataReady: true,
    missingRequiredArtifacts: ["Training Code / Scripts"],
    allAttested: false,
    chkAttestation: true,
  });

  assert.equal(reason, "Upload the required training code / scripts to proceed. Complete all governance controls.");
});
