// Unit tests for src/lib/model-identity.ts (Batch 2: model identity and
// registration). Run with Node's built-in runner, no extra packages:
//   node --test unit-tests/model-identity.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  canRunRegisteredReplication,
  demoIntakeSnapshot,
  identityExplanation,
  identityFromLineage,
  identityLabel,
  metadataPresentationForDemo,
  metadataPresentationForRegisteredModel,
  replicationModelId,
  restoreDraftModelId,
  sanitizeFrameworks,
  selectedModelId,
  trainedModelIdentity,
  withSelectedModel,
  type LineageReadiness,
} from "../src/lib/model-identity.ts";

const INVENTORY = ["MOD-001", "MOD-002", "MOD-003"];

function readiness(model_id: string, status: LineageReadiness["status"], reasons: string[] = []): LineageReadiness {
  return {
    model_id,
    status,
    replication_ready: status === "ready",
    contract: status === "lineage_missing" ? null : { contract_version: 1, training_run_id: "TR-1" },
    scoring_bundle: { recorded: status !== "lineage_missing", available: status === "ready", integrity: status === "ready" ? "verified" : "missing" },
    reasons,
  };
}

test("intake frameworks strip IFRS 9 and preserve only the approved governance options", () => {
  assert.deepEqual(sanitizeFrameworks(["IFRS9", "SS1/23", "RBI", "RBI Model Risk Management"]), ["SS1/23", "RBI Model Risk Management"]);
  assert.deepEqual(sanitizeFrameworks(["IFRS 9", "RBI"]), ["RBI Model Risk Management"]);
  assert.deepEqual(sanitizeFrameworks(["SS1/23", "SS1/23"]), ["SS1/23"]);
  assert.deepEqual(sanitizeFrameworks([]), []);
});

test("demo metadata is clearly labelled as illustrative and not verified inventory data", () => {
  const demo = metadataPresentationForDemo({ demo_mode: "clean", demo_created_at: "2026-01-02T03:04:05.000Z" });
  assert.equal(demo.owningTeam, "Demo profile");
  assert.equal(demo.modelOwner, "Not assigned — demo");
  assert.equal(demo.leadValidator, "Not assigned — demo");
  assert.equal(demo.registeredModelId, "Not registered");
  assert.equal(demo.validationDate, "Not applicable — demo");
  assert.equal(demo.demoCreatedAt, "2026-01-02T03:04:05.000Z");

  const registered = metadataPresentationForRegisteredModel({
    owning_team: "Retail Credit Risk",
    model_owner: "A. Owner",
    lead_validator: "B. Reviewer",
    registered_model_id: "MOD-001",
    validation_date: "2026-01-03",
  });
  assert.equal(registered.owningTeam, "Retail Credit Risk");
  assert.equal(registered.modelOwner, "A. Owner");
  assert.equal(registered.leadValidator, "B. Reviewer");
  assert.equal(registered.registeredModelId, "MOD-001");
  assert.equal(registered.validationDate, "2026-01-03");
  assert.equal(registered.demoCreatedAt, null);
});

// 1. Genuine registered model selected
test("verified lineage gives a replication-ready identity", () => {
  const id = identityFromLineage("MOD-001", readiness("MOD-001", "ready"), null, false);
  assert.equal(id.kind, "ready");
  assert.equal(canRunRegisteredReplication(id), true);
  assert.equal(identityLabel(id).text, "Registered · replication-ready");
});

// 2. Registered model missing lineage contract
test("missing lineage contract is incomplete and cannot run, with the reason shown", () => {
  const id = identityFromLineage("MOD-002", readiness("MOD-002", "lineage_missing", ["No lineage contract is recorded."]), null, false);
  assert.equal(id.kind, "incomplete");
  assert.equal(canRunRegisteredReplication(id), false);
  assert.match(identityExplanation(id), /cannot run: No lineage contract is recorded\./);
  assert.notEqual(identityLabel(id).text, "Registered · replication-ready");
});

// 3. Registered model missing scoring bundle
test("missing or tampered scoring bundle is incomplete and cannot run", () => {
  for (const status of ["bundle_missing", "bundle_integrity_failed", "unsupported_task"] as const) {
    const id = identityFromLineage("MOD-003", readiness("MOD-003", status), null, false);
    assert.equal(id.kind, "incomplete", status);
    assert.equal(canRunRegisteredReplication(id), false, status);
  }
  // A response claiming ready without the ready status is not trusted.
  const odd = { ...readiness("MOD-003", "bundle_missing"), replication_ready: true };
  assert.equal(identityFromLineage("MOD-003", odd, null, false).kind, "incomplete");
});

// 4. No model selected
test("no selection gives the 'none' identity (unregistered refit only)", () => {
  const id = identityFromLineage(null, null, null, false);
  assert.equal(id.kind, "none");
  assert.equal(canRunRegisteredReplication(id), false);
  assert.match(identityExplanation(id), /unregistered independent refit/);
  assert.equal(selectedModelId({}), null);
  assert.equal(selectedModelId({ registered_model_id: "  " }), null);
});

// 5. Invalid model ID
test("unknown, unreachable or mismatched IDs are invalid", () => {
  assert.equal(identityFromLineage("MOD-404", null, 404, false).kind, "invalid");
  assert.equal(identityFromLineage("MOD-001", null, 500, false).kind, "invalid");
  assert.equal(identityFromLineage("MOD-001", readiness("MOD-002", "ready"), null, false).kind, "invalid");
  assert.equal(identityFromLineage("MOD-001", null, null, true).kind, "loading");
  assert.equal(canRunRegisteredReplication(identityFromLineage("MOD-001", null, null, true)), false);
});

// 6. Demo loaded after registered selection
test("loading a demo clears an earlier registered selection", () => {
  const selected = withSelectedModel({ model_name: "Real" }, "MOD-001", INVENTORY);
  const demo = demoIntakeSnapshot({
    ...selected,
    model_name: "PD_Model_Internal_v1",
    registered_model_id: "MOD-001",
    mdd_document_path: "demo_data/clean_mdd.txt",
    demo_mode: "clean",
  });
  assert.equal(demo.registered_model_id, null);
  assert.equal(demo.model_inventory_registered, false);
  assert.equal(demo.is_demo_data, true);
  assert.equal(demo.mdd_document_path, "demo_data/clean_mdd.txt");
  assert.equal(demo.demo_mode, "clean");
  assert.equal(replicationModelId(demo), null);
});

// 7. Registered selection changed without clicking Proceed
test("a dropdown change is written to shared state immediately and exactly", () => {
  let shared: Record<string, any> | null = { model_name: "PD", registered_model_id: "MOD-001", model_inventory_registered: true };
  shared = withSelectedModel(shared, "MOD-002", INVENTORY);
  assert.equal(replicationModelId(shared), "MOD-002");                 // Stage 3 sees it without Proceed
  assert.equal(shared.model_inventory_registered, true);
  assert.equal(shared.model_name, "PD");                               // other intake fields kept
  shared = withSelectedModel(shared, "MOD-999", INVENTORY);            // not in inventory
  assert.equal(shared.registered_model_id, "MOD-999");                 // kept as chosen (shown as invalid), not replaced
  assert.equal(shared.model_inventory_registered, false);
  shared = withSelectedModel(shared, "", INVENTORY);
  assert.equal(shared.registered_model_id, null);
});

// 8. Navigation away and back
test("identity is read from persisted shared state, so remounting keeps the same ID", () => {
  const shared = withSelectedModel({ model_name: "PD" }, "MOD-003", INVENTORY);
  const persisted = JSON.parse(JSON.stringify({ validationIntakeData: shared }));  // what app-context saves/restores
  assert.equal(selectedModelId(persisted.validationIntakeData), "MOD-003");
  assert.equal(replicationModelId(persisted.validationIntakeData), "MOD-003");
});

// 9. Intake draft save and restoration
test("a draft's registered model is restored when it is still in the inventory", () => {
  const draft = { registeredModelId: "MOD-002" };
  const restored = restoreDraftModelId(draft.registeredModelId, INVENTORY, true);
  assert.deepEqual(restored, { modelId: "MOD-002", message: null });
  assert.deepEqual(restoreDraftModelId(undefined, INVENTORY, true), { modelId: null, message: null });
});

// 10. Deleted or unavailable model during draft restoration
test("a draft model that no longer exists, or cannot be verified, is cleared with a message", () => {
  const gone = restoreDraftModelId("MOD-777", INVENTORY, true);
  assert.equal(gone.modelId, null);
  assert.match(gone.message ?? "", /no longer in the Model Inventory/);
  const unverified = restoreDraftModelId("MOD-001", [], false);
  assert.equal(unverified.modelId, null);
  assert.match(unverified.message ?? "", /could not be verified/);
  const fabricated = restoreDraftModelId("CR-PD-XGB-027", INVENTORY, true);   // old demo text is never restored
  assert.equal(fabricated.modelId, null);
});

// 11. Training response → inventory refresh → Intake selection
test("the trained model's returned ID is used as-is and verified against the refreshed inventory", () => {
  const response = { model_name: "PD_New", model_id: "MOD-004", lineage: { captured: true, training_run_id: "run-1" } };
  const trained = trainedModelIdentity(response);
  assert.deepEqual(trained, { modelId: "MOD-004", lineageCaptured: true, reason: null });
  const fromTraining = withSelectedModel({}, trained.modelId, []);           // set before Intake reloads the inventory
  assert.equal(fromTraining.model_inventory_registered, false);
  const afterRefresh = withSelectedModel(fromTraining, selectedModelId(fromTraining), [...INVENTORY, "MOD-004"]);
  assert.equal(afterRefresh.registered_model_id, "MOD-004");
  assert.equal(afterRefresh.model_inventory_registered, true);
  assert.deepEqual(trainedModelIdentity({ model_name: "PD_New" }), { modelId: null, lineageCaptured: false, reason: null });
  assert.equal(trainedModelIdentity({ model_id: "MOD-5", lineage: { captured: false, reason: "not registered" } }).reason, "not registered");
});

// 12. Stage 3 receives the exact model ID (never a name)
test("Stage 3 uses the exact selected ID and never falls back to the model name", () => {
  assert.equal(replicationModelId({ registered_model_id: " MOD-002 " }), "MOD-002");
  assert.equal(replicationModelId({ model_name: "PD_XGBoost_RetailCredit_v2" }), null);
  assert.equal(replicationModelId(null), null);
});
