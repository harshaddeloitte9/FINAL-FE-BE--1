// Data-shaping helpers for the Explainability > Summary full report.
// Every function here reads from data already computed elsewhere in the
// pipeline (profile, preprocessingResult, featureEngineeringResult,
// trainingResult) — nothing is recomputed or re-derived beyond simple
// formatting/aggregation, so the report can never drift from what each
// pipeline step actually produced.

import { computeFeatureRemovalProposal } from "@/lib/feature-removal";

export function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return "";
  return `"${String(value).replace(/"/g, '""')}"`;
}

export function rowsToCsv(headers: string[], rows: Array<Array<unknown>>): string {
  return [headers.map(csvEscape).join(","), ...rows.map((row) => row.map(csvEscape).join(","))].join("\n");
}

const TREATMENT_LABELS: Record<string, string> = {
  statistical: "Statistical (MICE/KNN/median)",
  unknown_category: "Unknown category",
  zero_fill: "Zero-fill",
  review_flag: "Review — sparse (>40% missing)",
};

export function missingTreatmentCounts(appliedTreatmentMap: Record<string, { treatment?: string }> | undefined) {
  const counts: Record<string, number> = {
    statistical: 0,
    unknown_category: 0,
    zero_fill: 0,
    review_flag: 0,
  };
  for (const info of Object.values(appliedTreatmentMap ?? {})) {
    const t = info?.treatment;
    if (t && t in counts) counts[t] += 1;
  }
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([treatment, n]) => ({ treatment, label: TREATMENT_LABELS[treatment] ?? treatment, count: n }));
}

export function preprocessingColumnRows(preprocessingResult: Record<string, any> | null | undefined) {
  return Array.isArray(preprocessingResult?.preprocessing_strategy_summary)
    ? preprocessingResult.preprocessing_strategy_summary
    : [];
}

export function computeGini(rocAuc: number | null | undefined): number | null {
  if (rocAuc === null || rocAuc === undefined || Number.isNaN(rocAuc)) return null;
  return Math.round((2 * rocAuc - 1) * 10000) / 10000;
}

export function hyperparameterSummary(trainingResult: Record<string, any> | null | undefined) {
  const trainingConfig = trainingResult?.training_config ?? {};
  const trainingInfo = trainingResult?.training_info ?? {};
  const manualParams = trainingConfig.manual_params ?? {};
  const bestParams = trainingInfo.best_params ?? {};

  if (Object.keys(bestParams).length > 0) {
    return { source: "Hyperparameter search (RandomizedSearchCV)", params: bestParams };
  }
  if (Object.keys(manualParams).length > 0) {
    return { source: "Manually set by reviewer", params: manualParams };
  }
  return { source: "Library defaults (not customized)", params: {} as Record<string, any> };
}

export function featureRemovalSummary(featureEngineeringResult: Record<string, any> | null | undefined) {
  const plan = featureEngineeringResult?.feature_engineering_plan ?? {};
  return computeFeatureRemovalProposal(plan);
}

export function topInteractionTerms(featureEngineeringResult: Record<string, any> | null | undefined, limit = 10) {
  const features = Array.isArray(featureEngineeringResult?.interaction_features)
    ? featureEngineeringResult.interaction_features
    : [];
  return [...features]
    .sort((a, b) => (b?.score ?? b?.gini ?? 0) - (a?.score ?? a?.gini ?? 0))
    .slice(0, limit);
}

export function woeFeatureSummary(featureEngineeringResult: Record<string, any> | null | undefined) {
  const plan = featureEngineeringResult?.feature_engineering_plan ?? {};
  const woeCols: string[] = Array.isArray(plan.woe_cols) ? plan.woe_cols : [];
  const woeMaps = plan.woe_maps && typeof plan.woe_maps === "object" ? plan.woe_maps : {};
  const ivScores = plan.iv_scores && typeof plan.iv_scores === "object" ? plan.iv_scores : {};
  return woeCols.map((col) => ({
    feature: col,
    buckets: woeMaps[col] ? Object.keys(woeMaps[col]).length : 0,
    iv: ivScores[col] !== undefined ? Number(ivScores[col]) : null,
  }));
}
