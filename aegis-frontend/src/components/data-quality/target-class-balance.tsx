import { AlertTriangle } from "lucide-react";
import { StatusBadge } from "./status-badge";
import { getTargetHealth } from "./selectors";

const SEGMENT_COLORS = ["#2563eb", "#059669", "#7c3aed", "#d97706", "#e11d48", "#0891b2"];

// Compact stacked-proportion visualization for the real class_distribution
// object _build_data_profile returns — same "one bar, segment per class"
// pattern already used elsewhere in Aegis (e.g. the train/val/test split
// bar in Data Preparation), reimplemented locally rather than importing
// unexported code from data-preparation.tsx.
export function TargetClassBalance({ profile }: { profile: any }) {
  const targetHealth = getTargetHealth(profile);
  const classDistribution = profile?.class_distribution;
  const targetSummary = profile?.target_summary;

  if (!targetHealth.hasTarget || !classDistribution || typeof classDistribution !== "object") {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-slate-900">Target Class Balance</h3>
          <StatusBadge status="not_evaluated" />
        </div>
        <p className="mt-2 text-sm text-slate-500">No target column resolved for this dataset — class distribution not evaluated.</p>
      </div>
    );
  }

  const entries = Object.entries(classDistribution as Record<string, number>);
  const total = entries.reduce((sum, [, v]) => sum + (typeof v === "number" ? v : 0), 0);
  const segments = entries.map(([name, value], i) => ({
    name,
    value,
    pct: total > 0 ? (value / total) * 100 : 0,
    color: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
  }));

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Target Class Balance</h3>
          <p className="mt-0.5 text-[13px] text-slate-500">
            {targetSummary?.selected_target ? <>Distribution of <code className="rounded bg-slate-100 px-1 py-0.5 font-mono">{targetSummary.selected_target}</code></> : "Target distribution"}
          </p>
        </div>
        <StatusBadge status={targetHealth.status} label={targetHealth.headline} />
      </div>

      <div className="mt-5 flex h-3.5 w-full overflow-hidden rounded-full bg-slate-100">
        {segments.map((s) => (
          <div key={s.name} style={{ width: `${s.pct}%`, background: s.color }} title={`${s.name}: ${s.pct.toFixed(1)}%`} />
        ))}
      </div>

      {/* Per-class breakdown — same label / count / share shape as the
          Class Distribution card on Data Preparation, just condensed into
          rows instead of a donut, so the card carries real visual weight
          instead of ending in empty space below a thin bar. */}
      <div className="mt-5 divide-y divide-slate-100">
        {segments.map((s) => (
          <div key={s.name} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
            <div className="flex items-center gap-2.5">
              <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: s.color }} />
              <span className="text-sm font-medium text-slate-600">
                {targetSummary?.selected_target ?? "Target"} = {s.name}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-bold tabular-nums text-slate-900">{s.value.toLocaleString()}</span>
              <span className="text-sm font-semibold tabular-nums text-slate-500">{s.pct.toFixed(1)}%</span>
            </div>
          </div>
        ))}
      </div>

      {targetHealth.status === "review" && (
        <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50/60 p-3.5 text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="text-sm font-semibold">Class imbalance detected</div>
            <p className="mt-0.5 text-[13px] leading-snug">{targetHealth.evidence}</p>
          </div>
        </div>
      )}
    </div>
  );
}
