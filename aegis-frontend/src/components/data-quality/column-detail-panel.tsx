import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Columns3, Fingerprint, ShieldAlert } from "lucide-react";
import { StatusBadge } from "./status-badge";
import { buildColumnDiagnostics } from "./selectors";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2.5 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-sm font-semibold text-slate-900">{value}</span>
    </div>
  );
}

// Drill-down for one selected column — shows only information the profile
// actually contains for it. No recommendation is invented: the only
// suggestion ever shown is a real agent2 compliance-flag suggestion that
// names this column, when one exists.
export function ColumnDetailPanel({ profile, column }: { profile: any; column: string | null }) {
  const columns = buildColumnDiagnostics(profile);
  const detail = column ? columns.find((c) => c.column === column) : null;

  if (!detail) {
    return (
      <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 p-8 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-50 text-blue-500">
          <Columns3 className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-700">Select a column</div>
          <p className="mx-auto mt-1 max-w-xs text-[13px] leading-relaxed text-slate-500">
            Choose a row above to inspect column-level quality diagnostics.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Selected Column</div>
          <h3 className="mt-0.5 font-mono text-lg font-semibold text-slate-900">{detail.column}</h3>
          <div className="mt-1 text-[13px] text-slate-500">{detail.type}</div>
        </div>
        <StatusBadge status={detail.status} />
      </div>

      <div className="mt-4">
        <DetailRow label="Missing" value={detail.missingPct !== null ? `${detail.missingPct.toFixed(1)}% (${detail.missingCount?.toLocaleString() ?? "—"} rows)` : "—"} />
        <DetailRow label="Unique values" value={detail.uniqueValues !== null ? detail.uniqueValues.toLocaleString() : "—"} />
        {(detail.min !== null && detail.min !== "") || (detail.max !== null && detail.max !== "") ? (
          <>
            <DetailRow label="Min" value={detail.min !== "" ? String(detail.min) : "—"} />
            <DetailRow label="Max" value={detail.max !== "" ? String(detail.max) : "—"} />
            <DetailRow label="Mean" value={detail.mean !== "" && detail.mean !== null ? String(detail.mean) : "—"} />
          </>
        ) : null}
        <DetailRow
          label="Outliers"
          value={
            detail.outlier
              ? `${detail.outlier.count.toLocaleString()} (${(detail.outlier.fraction * 100).toFixed(1)}%)`
              : detail.outlierApplicable
              ? "Not evaluated"
              : "—"
          }
        />
        {detail.dateInfo && (
          <>
            <DetailRow label="Date range" value={`${detail.dateInfo.minDate} → ${detail.dateInfo.maxDate}`} />
            <DetailRow label="Future / pre-1900 dates" value={`${detail.dateInfo.futureCount} / ${detail.dateInfo.ancientCount}`} />
          </>
        )}
        {detail.sampleValues && <DetailRow label="Sample values" value={detail.sampleValues} />}
      </div>

      {(detail.isIdColumn || detail.isLeakageRisk) && (
        <div className="mt-4 flex flex-col gap-2">
          {detail.isIdColumn && (
            <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-[13px] leading-snug text-slate-600">
              <Fingerprint className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
              <span>ID-like column detected — typically excluded from modelling features.</span>
            </div>
          )}
          {detail.isLeakageRisk && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-[13px] leading-snug text-amber-800">
              <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>Correlation with the target exceeds 0.95 — review for potential leakage.</span>
            </div>
          )}
        </div>
      )}

      {detail.complianceNote && (
        <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50/60 p-3 text-[13px] leading-snug text-blue-800">
          <span className="font-semibold">Compliance suggestion: </span>
          {detail.complianceNote}
        </div>
      )}

      <Link
        to="/data-preparation"
        className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-700"
      >
        Open in Data Preparation
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
