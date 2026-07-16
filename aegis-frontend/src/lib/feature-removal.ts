// Feature removal proposal — shared between the Feature Engineering screen
// (features.tsx) and the Explainability > Summary full report, so both
// render the exact same cascade-rescue decisions instead of two independent
// implementations drifting apart.
//
// Mirrors the old Streamlit app's cascade-rescue logic exactly (same inputs:
// drop_high_corr_pairs, low_variance_cols, low_iv_cols, iv_scores — all
// already returned wholesale in feature_engineering_plan): if BOTH members
// of a correlated pair are proposed for removal, pre-retain the higher-IV
// one so the information family doesn't vanish entirely.

export type FeatureRemovalRow = {
  feature: string;
  iv: number | null;
  reason: string;
  rescued: boolean;
  defaultRemove: boolean;
};

export type FeatureRemovalProposal = {
  rows: FeatureRemovalRow[];
  rescueSet: Set<string>;
};

export function computeFeatureRemovalProposal(plan: Record<string, any>): FeatureRemovalProposal {
  const dropHighCorrPairs: Array<[string, string, number]> = Array.isArray(plan?.drop_high_corr_pairs)
    ? plan.drop_high_corr_pairs
    : [];
  const lowVarianceCols: string[] = Array.isArray(plan?.low_variance_cols) ? plan.low_variance_cols : [];
  const lowIvCols: string[] = Array.isArray(plan?.low_iv_cols) ? plan.low_iv_cols : [];
  const ivScoresMap: Record<string, number> = plan?.iv_scores && typeof plan.iv_scores === "object" ? plan.iv_scores : {};

  const corrDropSet = new Set(dropHighCorrPairs.map(([, dropped]) => dropped));
  const lowVarSet = new Set(lowVarianceCols);
  const lowIvSet = new Set(lowIvCols);
  const corrReason = new Map<string, string>();
  for (const [kept, dropped, corr] of dropHighCorrPairs) {
    corrReason.set(dropped, `Corr ${Number(corr).toFixed(2)} with \`${kept}\``);
  }

  const allProposed = new Set<string>([...corrDropSet, ...lowVarSet, ...lowIvSet]);
  const rescueSet = new Set<string>();
  const rescueNote = new Map<string, string>();
  for (const [kept, dropped] of dropHighCorrPairs) {
    if (allProposed.has(kept)) {
      const ivKept = ivScoresMap[kept] ?? 0;
      const ivDrop = ivScoresMap[dropped] ?? 0;
      const [rescued, victim] = ivKept >= ivDrop ? [kept, dropped] : [dropped, kept];
      rescueSet.add(rescued);
      rescueNote.set(
        rescued,
        `Retained — sole survivor of correlated pair (partner \`${victim}\` also removed by another filter)`,
      );
    }
  }

  const reasonFor = (feat: string): string => {
    if (rescueNote.has(feat)) return rescueNote.get(feat)!;
    if (corrReason.has(feat)) return corrReason.get(feat)!;
    if (lowVarSet.has(feat)) return "Near-constant — top value covers > 99% of rows";
    if (lowIvSet.has(feat)) {
      const ivVal = ivScoresMap[feat];
      return ivVal !== undefined ? `Low IV (${ivVal.toFixed(4)} < 0.02)` : "Low IV (< 0.02)";
    }
    return "Proposed for removal";
  };

  const proposalCols = Array.from(new Set<string>([...corrDropSet, ...lowVarSet, ...lowIvSet]));
  const rows = proposalCols.map((feature) => ({
    feature,
    iv: ivScoresMap[feature] !== undefined ? Number(ivScoresMap[feature]) : null,
    reason: reasonFor(feature),
    rescued: rescueSet.has(feature),
    defaultRemove: !rescueSet.has(feature),
  }));

  return { rows, rescueSet };
}
