// Scoping for development-page resumes (audit finding E7).
//
// A development page (preprocessing, feature engineering, training,
// evaluation, explainability) may only restore a saved run that belongs to
// the exact dataset file being worked on and, for model pages, the exact
// registered model and training run. Without that identity nothing is
// restored: an empty page is better than another model's or dataset's result.

export type DevResumeScope = {
  /** SHA-256 of the dataset bytes this page sends (dataset_file_sha256). */
  fileSha: string | null;
  registeredModelId?: string | null;
  trainingRunId?: string | null;
  /** Model pages: no resume until the model identity is known. */
  requireModel?: boolean;
};

/** Query params for /history/latest, or null when the scope is not yet known. */
export function devResumeParams(scope: DevResumeScope): Record<string, string> | null {
  if (!scope.fileSha) return null;
  if (scope.requireModel && !(scope.registeredModelId && scope.trainingRunId)) return null;
  const params: Record<string, string> = { dataset_file_sha256: scope.fileSha };
  if (scope.registeredModelId) params.registered_model_id = scope.registeredModelId;
  if (scope.trainingRunId) params.training_run_id = scope.trainingRunId;
  return params;
}

type IdentityCarrier = {
  dataset_file_sha256?: string | null;
  registered_model_id?: string | null;
  training_run_id?: string | null;
};

function payloadIdentity(payload: any): IdentityCarrier {
  const scoped: IdentityCarrier = payload?.evaluation_scope ?? payload?.explain_scope ?? {};
  return {
    dataset_file_sha256: payload?.dataset_identity?.dataset_file_sha256 ?? scoped.dataset_file_sha256 ?? null,
    registered_model_id: scoped.registered_model_id ?? payload?.model_id ?? null,
    training_run_id: scoped.training_run_id ?? payload?.training_run_id ?? null,
  };
}

/**
 * Second, client-side check on a resumed payload (the server already
 * filtered by the same fields): the payload must itself record the same
 * dataset file and, when required, the same model and training run.
 * Payloads that do not record their identity (legacy runs) never match.
 */
export function resumedPayloadMatches(payload: unknown, scope: DevResumeScope): boolean {
  if (!payload || !scope.fileSha) return false;
  const id = payloadIdentity(payload);
  if (id.dataset_file_sha256 !== scope.fileSha) return false;
  if (scope.registeredModelId && id.registered_model_id !== scope.registeredModelId) return false;
  if (scope.trainingRunId && id.training_run_id !== scope.trainingRunId) return false;
  if (scope.requireModel && !(id.registered_model_id && id.training_run_id)) return false;
  return true;
}
