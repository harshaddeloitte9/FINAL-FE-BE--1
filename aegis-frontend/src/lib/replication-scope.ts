// Model Replication page rules for audit findings D1 and D2.

type RecordedIdentity = {
  registered_model_id?: string | null;
  dataset_file_sha256?: string | null;
} | null | undefined;

/**
 * D1 — a saved or cached replication run may be shown as the current result
 * only when it was recorded for the selected registered model (or for no
 * registered model, when none is selected) AND for the exact dataset bytes
 * now loaded. Runs that do not record the dataset fingerprint (older runs)
 * never match, and nothing matches until the current fingerprint is known.
 */
export function replicationRestoreUsable(
  recorded: RecordedIdentity,
  current: { registeredModelId: string | null; datasetFileSha: string | null },
): boolean {
  if (!recorded || !current.datasetFileSha) return false;
  if ((recorded.registered_model_id ?? null) !== (current.registeredModelId ?? null)) return false;
  return Boolean(recorded.dataset_file_sha256) && recorded.dataset_file_sha256 === current.datasetFileSha;
}

/**
 * D2 — who established a reference value's source. Only values the server
 * extracted from the MDD uploaded with the run are verified; any other
 * source label came from the browser and is shown as unverified.
 */
export function referenceVerificationText(verification: string | null | undefined): string {
  if (verification === "server_extracted") return "verified by the server (extracted from the MDD uploaded with this run)";
  if (verification === "browser_reported") return "browser-reported, not verified by the server";
  return "verification not recorded (run saved before source verification)";
}
