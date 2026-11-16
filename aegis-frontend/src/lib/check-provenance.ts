// Phase 5 (G2, G3) — plain-language labels for where curves and sensitivity
// results come from. Only what the backend recorded is shown; older results
// without provenance say so instead of guessing.

export type CurveProvenance = {
  prediction_source?: string | null;
  evaluation_partition?: string | null;
  rows?: number | null;
  dataset_sha256?: string | null;
  test_index_sha256?: string | null;
};

const SOURCE_LABELS: Record<string, string> = {
  registered_bundle: "registered model (verified scoring bundle)",
  independent_retrain: "independent retrain from the recorded configuration",
  unregistered_refit: "unregistered refit",
  challenger_refit: "challenger refit",
};

const short = (h?: string | null) => (h ? `${h.slice(0, 12)}…` : null);

/** G2 — "Test partition · 450 rows · registered model (verified scoring bundle) · test rows 89dd8383fefa…" */
export function describeCurveProvenance(p: CurveProvenance | null | undefined): string {
  if (!p || !p.prediction_source) return "Prediction source not recorded (result saved before curve provenance)";
  const parts = [
    p.evaluation_partition ? `${p.evaluation_partition[0].toUpperCase()}${p.evaluation_partition.slice(1)} partition` : null,
    typeof p.rows === "number" ? `${p.rows} rows` : null,
    SOURCE_LABELS[p.prediction_source] ?? p.prediction_source,
    short(p.test_index_sha256) ? `test rows ${short(p.test_index_sha256)}` : null,
    short(p.dataset_sha256) ? `dataset ${short(p.dataset_sha256)}` : null,
  ];
  return parts.filter(Boolean).join(" · ");
}

/** G3 — stress sensitivity card title / subtitle from the backend method. */
export function describeSensitivityMethod(method: string | null | undefined): { title: string; sub: string } {
  if (method === "permutation") {
    return {
      title: "Sensitivity — AUC drop when each input is permuted",
      sub: "Permutation sensitivity of the registered model on its recorded test rows — no refit, no feature removal. SS1/23 P4.3.",
    };
  }
  if (method === "removal_refit") {
    return {
      title: "Sensitivity — AUC drop on feature removal and retraining",
      sub: "Each feature removed and the model retrained (independent refit), then re-scored on the same test rows. SS1/23 P4.3.",
    };
  }
  return { title: "Sensitivity", sub: "Sensitivity method not recorded for this result. SS1/23 P4.3." };
}
