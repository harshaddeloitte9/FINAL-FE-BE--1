// Evaluation identity and result-state rules for the Stress, Bias and
// Benchmark pages. Pure functions only (no React), so they are unit-tested
// directly (aegis-frontend/unit-tests/evaluation-evidence.test.ts).

export const MODE_REGISTERED = "registered_scoring_bundle";
export const MODE_REFIT = "independent_refit";

// The `evidence` block the backend returns with each stress / bias /
// benchmark run (24-06/main.py). Every field is optional: older or failed
// runs may not carry it, and nothing here fills a gap.
export type EvaluationEvidence = {
  run_id?: string | null;
  persisted?: boolean;
  evaluation_mode?: string | null;
  registered_model_id?: string | null;
  training_run_id?: string | null;
  dataset_sha256?: string | null;
  test_index_sha256?: string | null;
  bundle_sha256?: string | null;
  refit_algorithm?: string | null;
  test_rows?: number | null;
  challenger?: { evaluation_mode?: string | null; algorithm?: string | null } | null;
};

export type EvidenceRow = { label: string; value: string | null; hash?: boolean; note?: string };
export type EvidenceDescription = {
  kind: "registered" | "refit" | "unrecorded";
  title: string;
  summary: string;
  rows: EvidenceRow[];
};

const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : typeof v === "number" ? String(v) : null);

// What the evidence actually says — never inferred. "Registered scoring
// bundle" is shown only when the backend recorded that mode AND the model ID.
export function describeEvidence(evidence: EvaluationEvidence | null | undefined): EvidenceDescription {
  const ev = evidence ?? {};
  const mode = text(ev.evaluation_mode);
  const modelId = text(ev.registered_model_id);
  const common: EvidenceRow[] = [
    { label: "Dataset fingerprint", value: text(ev.dataset_sha256), hash: true },
    { label: "Test-row fingerprint", value: text(ev.test_index_sha256), hash: true },
    { label: "Run ID", value: text(ev.run_id), hash: true },
  ];
  if (mode === MODE_REGISTERED && modelId) {
    return {
      kind: "registered",
      title: "Registered scoring bundle",
      summary: `Registered model ${modelId} was scored from its verified bundle on its recorded test rows — no refit.`,
      rows: [
        { label: "Registered model", value: modelId },
        { label: "Training run", value: text(ev.training_run_id), hash: true },
        { label: "Bundle SHA-256", value: text(ev.bundle_sha256), hash: true },
        ...common,
      ],
    };
  }
  if (mode === MODE_REFIT) {
    return {
      kind: "refit",
      title: "Independent refit",
      summary: "A new model was fitted from the algorithm name. This is NOT an evaluation of a registered model and cannot serve as registered-model evidence.",
      rows: [
        { label: "Refit algorithm", value: text(ev.refit_algorithm) },
        { label: "Registered model", value: null, note: "None — independent refit" },
        ...common,
      ],
    };
  }
  return {
    kind: "unrecorded",
    title: "Evaluation identity not recorded",
    summary: "This result carries no evaluation identity, so it cannot be tied to a model, training run or dataset.",
    rows: [],
  };
}

export function shortHash(value: string, length = 12): string {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

// The identity a page's result belongs to. A cached or in-flight result is
// only shown while this key is unchanged. null = not yet known (nothing shown).
export function evaluationKey(parts: {
  registeredModelId: string | null;
  datasetKey: string | null;
  trainingRunId: string | null;
  extra?: string | null;
}): string | null {
  if (!parts.datasetKey) return null;
  return [
    parts.registeredModelId ? `model:${parts.registeredModelId}` : "model:none",
    `training:${parts.trainingRunId ?? "none"}`,
    `dataset:${parts.datasetKey}`,
    `extra:${parts.extra ?? ""}`,
  ].join("|");
}

export function cachedResultUsable(cached: { evaluation_key?: string | null } | null | undefined, key: string | null): boolean {
  return Boolean(key && cached && cached.evaluation_key === key);
}

// SHA-256 of the exact bytes the page will upload (a client-side cache key,
// not the server's parsed-table fingerprint).
export async function datasetFingerprint(data: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await data.arrayBuffer());
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

// ── Result state: loading / success / error / idle, by request token ──────

export type EvaluationState<R> = {
  key: string | null;
  token: number;
  status: "idle" | "loading" | "success" | "error";
  result: R | null;
  error: string | null;
};

export type EvaluationAction<R> =
  | { type: "reset"; key: string | null; token: number; cached?: R | null }
  | { type: "start"; token: number }
  | { type: "success"; token: number; result: R }
  | { type: "failure"; token: number; error: string };

export function initialEvaluationState<R>(): EvaluationState<R> {
  return { key: null, token: 0, status: "idle", result: null, error: null };
}

// - reset (identity changed): drops whatever was shown; restores only a cache
//   entry for exactly the new key.
// - start: clears the previous result immediately.
// - success / failure: applied only if they answer the LATEST request; a late
//   response from an older request is ignored. A failure always clears the
//   result, so an earlier PASS can never sit next to a new error.
export function evaluationReducer<R>(state: EvaluationState<R>, action: EvaluationAction<R>): EvaluationState<R> {
  switch (action.type) {
    case "reset":
      return { key: action.key, token: action.token, status: action.cached ? "success" : "idle", result: action.cached ?? null, error: null };
    case "start":
      return { ...state, token: action.token, status: "loading", result: null, error: null };
    case "success":
      return action.token === state.token ? { ...state, status: "success", result: action.result, error: null } : state;
    case "failure":
      return action.token === state.token ? { ...state, status: "error", result: null, error: action.error } : state;
    default:
      return state;
  }
}
