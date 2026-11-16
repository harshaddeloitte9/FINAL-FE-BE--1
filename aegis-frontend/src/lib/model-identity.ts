// Registered-model identity for the validation flow — one set of rules used by
// Intake, Model Training and Stage 3. Pure functions only (no React, no
// fetch), so they can be unit-tested directly (aegis-frontend/unit-tests).
//
// The single source of truth for the selected model is
// `validationIntakeData.registered_model_id` in the shared app state. An ID is
// only ever an exact Model Inventory ID chosen by the user; it is never
// derived from a model name.

export type LineageStatus = "ready" | "lineage_missing" | "unsupported_task" | "bundle_missing" | "bundle_integrity_failed";

// Response of GET /model-inventory/development/{id}/lineage.
export type LineageReadiness = {
  model_id: string;
  model_name?: string | null;
  algorithm?: string | null;
  status: LineageStatus;
  replication_ready: boolean;
  contract: {
    contract_version?: number;
    training_run_id?: string | null;
    task_type?: string | null;
    dataset_name?: string | null;
    created_at?: string | null;
  } | null;
  scoring_bundle: { recorded: boolean; available: boolean; integrity: string; path?: string | null };
  reasons: string[];
};

export type ModelIdentity =
  | { kind: "none" }
  | { kind: "loading"; modelId: string }
  | { kind: "invalid"; modelId: string; reason: string }
  | { kind: "incomplete"; modelId: string; readiness: LineageReadiness }
  | { kind: "ready"; modelId: string; readiness: LineageReadiness };

type IntakeData = Record<string, any> | null | undefined;

export function selectedModelId(intake: IntakeData): string | null {
  const id = intake?.registered_model_id;
  return typeof id === "string" && id.trim() ? id.trim() : null;
}

export function sanitizeFrameworks(frameworks: unknown): string[] {
  const raw = Array.isArray(frameworks) ? frameworks : typeof frameworks === "string" ? [frameworks] : [];
  const allowed = new Set<string>();
  for (const value of raw) {
    const item = typeof value === "string" ? value.trim() : "";
    if (!item) continue;
    const normalized = item.toLowerCase();
    if (normalized === "ifrs9" || normalized === "ifrs 9" || normalized === "ifrs-9") continue;
    if (normalized === "rbi" || normalized === "rbi model risk management") {
      allowed.add("RBI Model Risk Management");
      continue;
    }
    if (normalized === "ss1/23") {
      allowed.add("SS1/23");
      continue;
    }
    if (normalized === "ss11/13") {
      allowed.add("SS11/13");
      continue;
    }
    allowed.add(item);
  }
  return [...allowed];
}

// Intake dropdown change: written to shared state immediately. The flag the
// Stage 2 / Findings checks read is true only when the exact ID is in the
// Development Inventory list just loaded from the backend.
export function withSelectedModel(intake: IntakeData, modelId: string | null, inventoryIds: readonly string[]): Record<string, any> {
  const id = modelId && modelId.trim() ? modelId.trim() : null;
  return { ...(intake ?? {}), registered_model_id: id, model_inventory_registered: Boolean(id && inventoryIds.includes(id)) };
}

// Demo intake snapshot: demonstration data is never a registered model, so
// any previously selected ID is cleared on purpose.
export function metadataPresentationForDemo(snapshot?: IntakeData): {
  owningTeam: string;
  modelOwner: string;
  leadValidator: string;
  registeredModelId: string;
  validationDate: string;
  demoCreatedAt: string | null;
} {
  const demoCreatedAt = typeof snapshot?.demo_created_at === "string" && snapshot.demo_created_at.trim() ? snapshot.demo_created_at.trim() : null;
  return {
    owningTeam: "Demo profile",
    modelOwner: "Not assigned — demo",
    leadValidator: "Not assigned — demo",
    registeredModelId: "Not registered",
    validationDate: "Not applicable — demo",
    demoCreatedAt,
  };
}

export function metadataPresentationForRegisteredModel(snapshot?: IntakeData): {
  owningTeam: string;
  modelOwner: string;
  leadValidator: string;
  registeredModelId: string;
  validationDate: string;
  demoCreatedAt: string | null;
} {
  const modelOwner = typeof snapshot?.model_owner === "string" && snapshot.model_owner.trim() ? snapshot.model_owner.trim() : "Not assigned";
  const leadValidator = typeof snapshot?.lead_validator === "string" && snapshot.lead_validator.trim() ? snapshot.lead_validator.trim() : "Not assigned";
  const registeredModelId = typeof snapshot?.registered_model_id === "string" && snapshot.registered_model_id.trim() ? snapshot.registered_model_id.trim() : "Not registered";
  return {
    owningTeam: typeof snapshot?.owning_team === "string" && snapshot.owning_team.trim() ? snapshot.owning_team.trim() : "Not assigned",
    modelOwner,
    leadValidator,
    registeredModelId,
    validationDate: typeof snapshot?.validation_date === "string" && snapshot.validation_date.trim() ? snapshot.validation_date.trim() : "Not applicable",
    demoCreatedAt: null,
  };
}

export function demoIntakeSnapshot(snapshot: IntakeData): Record<string, any> {
  const demo = metadataPresentationForDemo(snapshot);
  return {
    ...(snapshot ?? {}),
    owning_team: demo.owningTeam,
    model_owner: demo.modelOwner,
    lead_validator: demo.leadValidator,
    registered_model_id: null,
    model_inventory_registered: false,
    validation_date: demo.validationDate,
    demo_created_at: demo.demoCreatedAt,
    is_demo_data: true,
    frameworks: sanitizeFrameworks((snapshot ?? {}).frameworks ?? ["SS1/23", "RBI Model Risk Management"]),
  };
}

// Intake draft restore: an ID is restored only if it is still in the
// inventory; otherwise the selection is cleared with a message.
export function restoreDraftModelId(
  draftId: unknown,
  inventoryIds: readonly string[],
  inventoryLoaded: boolean,
): { modelId: string | null; message: string | null } {
  const id = typeof draftId === "string" && draftId.trim() ? draftId.trim() : null;
  if (!id) return { modelId: null, message: null };
  if (!inventoryLoaded) {
    return { modelId: null, message: `The draft's registered model ${id} could not be verified (the Model Inventory did not load), so it was not restored.` };
  }
  if (!inventoryIds.includes(id)) {
    return { modelId: null, message: `The draft's registered model ${id} is no longer in the Model Inventory, so the selection was cleared.` };
  }
  return { modelId: id, message: null };
}

// Identity from the lineage lookup for the selected ID. `httpStatus` is the
// error status of the lookup when it failed (404 = not in the inventory).
export function identityFromLineage(
  modelId: string | null,
  readiness: LineageReadiness | null,
  httpStatus: number | null,
  loading: boolean,
): ModelIdentity {
  if (!modelId) return { kind: "none" };
  if (loading) return { kind: "loading", modelId };
  if (httpStatus === 404) return { kind: "invalid", modelId, reason: `${modelId} is not in the Development Inventory.` };
  if (httpStatus !== null || !readiness) return { kind: "invalid", modelId, reason: `The lineage of ${modelId} could not be checked.` };
  if (readiness.model_id !== modelId) return { kind: "invalid", modelId, reason: `The lineage response is for ${readiness.model_id}, not ${modelId}.` };
  return readiness.replication_ready && readiness.status === "ready"
    ? { kind: "ready", modelId, readiness }
    : { kind: "incomplete", modelId, readiness };
}

// Registered-model replication may only run for a model whose lineage
// contract and scoring bundle were verified.
export function canRunRegisteredReplication(identity: ModelIdentity): boolean {
  return identity.kind === "ready";
}

export function identityLabel(identity: ModelIdentity): { text: string; tone: "primary" | "amber" | "rose" | "slate" } {
  switch (identity.kind) {
    case "ready":
      return { text: "Registered · replication-ready", tone: "primary" };
    case "incomplete":
      return { text: "Registered · lineage incomplete", tone: "amber" };
    case "invalid":
      return { text: "Invalid or unavailable model", tone: "rose" };
    case "loading":
      return { text: "Checking registration…", tone: "slate" };
    default:
      return { text: "No registered model selected", tone: "slate" };
  }
}

export function identityExplanation(identity: ModelIdentity): string {
  switch (identity.kind) {
    case "ready":
      return "Lineage contract and scoring bundle verified: registered-model replication can run.";
    case "incomplete":
      return `Registered-model replication cannot run: ${identity.readiness.reasons.join(" ") || "required lineage evidence is missing."}`;
    case "invalid":
      return `Registered-model replication cannot run: ${identity.reason}`;
    case "loading":
      return "Checking the selected model's registration and lineage…";
    default:
      return "No registered model is selected, so Stage 3 can only run an unregistered independent refit, which cannot support a final verdict.";
  }
}

// The exact ID Stage 3 sends to /validation/replication (never a name).
export function replicationModelId(intake: IntakeData): string | null {
  return selectedModelId(intake);
}

// /models/train response → the model it actually registered, if any.
export function trainedModelIdentity(trainResponse: Record<string, any> | null | undefined): {
  modelId: string | null;
  lineageCaptured: boolean;
  reason: string | null;
} {
  const id = typeof trainResponse?.model_id === "string" && trainResponse.model_id.trim() ? trainResponse.model_id.trim() : null;
  const lineage = trainResponse?.lineage ?? null;
  return {
    modelId: id,
    lineageCaptured: Boolean(lineage?.captured),
    reason: lineage && !lineage.captured ? String(lineage.reason ?? "Lineage was not recorded.") : null,
  };
}
