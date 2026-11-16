// Display rules for saved history records (Phase 4, H1–H4).

export type RecordStatus = "current" | "legacy" | string | null | undefined;

/** H4 — the backend labels every history row; only "legacy" gets a badge. */
export function isLegacyRecord(row: { record_status?: RecordStatus } | null | undefined): boolean {
  return row?.record_status === "legacy";
}

export const LEGACY_BADGE_TEXT = "Legacy";
export const LEGACY_FALLBACK_REASON =
  "Recorded before run-identity tracking; its model, dataset and evidence cannot be verified.";

/**
 * H2 / H3 — whether a saved validation run belongs to the registered model
 * under validation AND the exact dataset bytes now loaded. Runs that do not
 * record the dataset fingerprint (older runs), runs of another model or
 * dataset, and lookups made before the current fingerprint is known never
 * match.
 */
export function runMatchesModelAndDataset(
  summary: { registered_model_id?: string | null; dataset_file_sha256?: string | null } | null | undefined,
  current: { registeredModelId: string | null; datasetFileSha: string | null },
): boolean {
  if (!summary || !current.registeredModelId || !current.datasetFileSha) return false;
  return summary.registered_model_id === current.registeredModelId
    && Boolean(summary.dataset_file_sha256)
    && summary.dataset_file_sha256 === current.datasetFileSha;
}

/** Query params for a model + dataset scoped lookup, or null until both are known. */
export function modelDatasetParams(registeredModelId: string | null, datasetFileSha: string | null): Record<string, string> | null {
  return registeredModelId && datasetFileSha ? { registered_model_id: registeredModelId, dataset_file_sha256: datasetFileSha } : null;
}
