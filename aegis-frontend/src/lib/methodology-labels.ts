// Plain-language labels for how a model's operating threshold was chosen and
// how its data was split (audit findings E3, E5, E13, E14). Only what the
// backend recorded is shown; anything unrecorded says so.

export type ThresholdProvenance = {
  method?: string | null;
  value?: number | null;
  source_partition?: string | null;
  rows?: number | null;
  degraded?: boolean | null;
  reason?: string | null;
};

export type SplitReport = {
  strategy?: string | null;
  achieved?: string | null;
  degraded?: boolean | null;
  fallbacks?: { partition?: string; reason?: string }[] | null;
  random_seed?: number | null;
  date_col?: string | null;
  boundaries?: Record<string, [string, string]> | null;
};

const fmt = (v: number | null | undefined) => (typeof v === "number" && Number.isFinite(v) ? v.toFixed(3) : "—");

export function describeThresholdProvenance(p: ThresholdProvenance | null | undefined): { text: string; warning: boolean } {
  if (!p || !p.method) return { text: "Threshold selection not recorded", warning: true };
  if (p.method === "manual") return { text: `${fmt(p.value)}, set manually by the user`, warning: false };
  if (p.method === "f1_max" && p.source_partition === "validation") {
    return {
      text: `${fmt(p.value)}, maximises F1 on the validation partition${p.rows ? ` (${p.rows} rows)` : ""}; test rows not used`,
      warning: false,
    };
  }
  if (p.method === "default_0.5") return { text: `${fmt(p.value)}, nominal default: ${p.reason ?? "no usable validation rows"}`, warning: true };
  return { text: `${fmt(p.value)}, ${p.method} on ${p.source_partition ?? "an unrecorded partition"}`, warning: true };
}

export function describeSplit(r: SplitReport | null | undefined): { text: string; warning: boolean } {
  if (!r || !r.strategy) return { text: "Split method not recorded", warning: true };
  if (r.strategy === "temporal") {
    const b = r.boundaries ?? {};
    const range = b.train && b.test ? `: train ${b.train[0]} to ${b.train[1]}, test ${b.test[0]} to ${b.test[1]}` : "";
    const text = `Chronological on ${r.date_col ?? "an unrecorded date column"}${range}`;
    return r.degraded ? { text: `${text}. Degraded: ${fallbackText(r)}`, warning: true } : { text, warning: false };
  }
  const seed = typeof r.random_seed === "number" ? ` (seed ${r.random_seed})` : "";
  if (r.degraded) return { text: `Stratified random requested${seed}, fell back to unstratified: ${fallbackText(r)}`, warning: true };
  if (r.achieved === "random_not_stratifiable") return { text: `Random${seed}; the target could not be stratified`, warning: true };
  return { text: `Stratified random${seed}`, warning: false };
}

function fallbackText(r: SplitReport): string {
  const items = (r.fallbacks ?? []).map((f) => `${f.partition ?? "?"}: ${f.reason ?? "unspecified"}`);
  return items.length ? items.join("; ") : "see split report";
}
