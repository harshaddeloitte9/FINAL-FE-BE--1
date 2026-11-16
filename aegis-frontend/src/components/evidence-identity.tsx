import { describeEvidence, shortHash, type EvaluationEvidence, type EvidenceRow } from "@/lib/evaluation-evidence";
import { cn } from "@/lib/utils";

const KIND_STYLES = {
  registered: "border-blue-200 bg-blue-50/60 text-blue-900",
  refit: "border-amber-200 bg-amber-50 text-amber-900",
  unrecorded: "border-slate-200 bg-slate-50 text-slate-700",
} as const;

const BADGE_STYLES = {
  registered: "bg-blue-600 text-white",
  refit: "bg-amber-500 text-white",
  unrecorded: "bg-slate-400 text-white",
} as const;

// Compact evidence identity of a stress / bias / benchmark result, exactly as
// the backend recorded it. Missing values read "Not recorded" — never filled.
export function EvidenceIdentity({
  evidence,
  title = "Evidence identity",
  extra,
  limitations,
}: {
  evidence: EvaluationEvidence | null | undefined;
  title?: string;
  extra?: Array<{ label: string; value: string | null }>;
  limitations?: string[];
}) {
  const d = describeEvidence(evidence);
  if (d.kind === "unrecorded") return null;

  const rows: EvidenceRow[] = [...d.rows, ...(extra ?? [])];
  const statusLabel = d.kind === "registered" ? "Registered model" : d.kind === "refit" ? "Independent refit" : "Evidence recorded";
  const details = limitations?.filter(Boolean) ?? [];

  return (
    <div className={cn("rounded-xl border px-4 py-3 text-xs", KIND_STYLES[d.kind])} data-testid="evidence-identity" data-evidence-kind={d.kind}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10.5px] font-bold uppercase tracking-wider opacity-70">{title}</span>
        <span className={cn("rounded-full px-2 py-0.5 text-[10.5px] font-semibold", BADGE_STYLES[d.kind])}>{statusLabel}</span>
      </div>
      <p className="mt-1.5 leading-relaxed">{d.summary}</p>
      {details.length ? (
        <details className="mt-2 rounded-lg border border-current/15 bg-white/30">
          <summary className="cursor-pointer list-none px-2 py-1.5 text-[10.5px] font-bold uppercase tracking-wider opacity-80">
            Evidence limitations
          </summary>
          <ul className="list-disc space-y-1 px-6 py-2 text-[11px] leading-relaxed opacity-90">
            {details.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
        </details>
      ) : null}
      {rows.length ? (
        <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
          {rows.map((row) => (
            <div key={row.label} className="flex min-w-0 items-baseline gap-2">
              <dt className="shrink-0 text-slate-500">{row.label}:</dt>
              <dd className="min-w-0 truncate">
                {row.value ? (
                  <span className="font-mono text-slate-800" title={row.value}>
                    {row.hash ? shortHash(row.value) : row.value}
                  </span>
                ) : (
                  <span className="italic text-slate-400">{row.note ?? "Not recorded"}</span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
