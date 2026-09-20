import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { buildIssues, type IssueRow } from "./selectors";

const SEVERITY_STYLES: Record<IssueRow["severity"], string> = {
  CRITICAL: "bg-rose-50 text-rose-700 border-rose-200",
  HIGH: "bg-rose-50 text-rose-700 border-rose-200",
  WARNING: "bg-amber-50 text-amber-700 border-amber-200",
  INFO: "bg-slate-100 text-slate-600 border-slate-200",
};

// Every row here comes from a real signal already present on the profile
// (see selectors.ts::buildIssues) — never an example/placeholder row, and
// never a fabricated record count.
export function IssuesTable({ profile }: { profile: any }) {
  const issues = buildIssues(profile);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-6 py-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Issues Requiring Attention</h3>
          <p className="mt-0.5 text-[13px] text-slate-500">Derived from this dataset's real completeness, uniqueness, target, leakage, date, and compliance signals.</p>
        </div>
        {issues.length > 0 && (
          <span className="whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-blue-700">
            {issues.length} issue{issues.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {issues.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div className="text-sm font-semibold text-slate-900">No data quality issues detected</div>
          <p className="max-w-sm text-sm text-slate-500">
            None of the completeness, uniqueness, target, leakage, date, or compliance signals Aegis currently checks found a problem in this dataset.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] table-fixed text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50 text-left text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <th className="w-[9%] px-6 py-3">Severity</th>
                <th className="w-[11%] px-4 py-3">Dimension</th>
                <th className="w-[29%] px-4 py-3">Issue</th>
                <th className="w-[14%] px-4 py-3">Column / Area</th>
                <th className="w-[11%] px-4 py-3 text-right">Records</th>
                <th className="w-[26%] px-6 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {issues.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50/60">
                  <td className="px-6 py-4 align-top">
                    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[10.5px] font-bold tracking-wide", SEVERITY_STYLES[row.severity])}>
                      {row.severity}
                    </span>
                  </td>
                  <td className="px-4 py-4 align-top text-[13px] font-medium text-slate-500">{row.dimension}</td>
                  <td className="px-4 py-4 align-top font-medium leading-snug text-slate-900">{row.issue}</td>
                  <td className="px-4 py-4 align-top font-mono text-[13px] leading-snug text-slate-600">{row.column}</td>
                  <td className="px-4 py-4 text-right align-top font-mono text-[13px] text-slate-600">{row.recordsAffected}</td>
                  <td className="px-6 py-4 align-top text-[13px] leading-snug text-slate-600">{row.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
