import { cn } from "@/lib/utils";
import { StatusBadge } from "./status-badge";
import { buildColumnDiagnostics } from "./selectors";

// Column-level diagnostics sourced entirely from data_dictionary /
// outlier_analysis / date_integrity / col_types (see selectors.ts). Any
// value not actually computed for a column reads "—" (not applicable) or
// "Not evaluated" (applicable but not run) — never a silent blank that
// could be mistaken for "checked and clean".
export function ColumnDiagnosticsTable({
  profile,
  selectedColumn,
  onSelectColumn,
}: {
  profile: any;
  selectedColumn: string | null;
  onSelectColumn: (column: string) => void;
}) {
  const columns = buildColumnDiagnostics(profile);

  if (columns.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
        No column-level profile is available for this dataset.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-4">
        <h3 className="text-base font-semibold text-slate-900">Column Diagnostics</h3>
        <p className="mt-0.5 text-[13px] text-slate-500">Select a column to see its full diagnostic detail.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50 text-left text-[11px] font-bold uppercase tracking-wider text-slate-400">
              <th className="px-6 py-3">Column</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Completeness</th>
              <th className="px-4 py-3">Uniqueness</th>
              <th className="px-4 py-3">Distribution</th>
              <th className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {columns.map((col) => {
              const isSelected = col.column === selectedColumn;
              const completenessLabel = col.missingPct !== null ? `${(100 - col.missingPct).toFixed(1)}%` : "—";
              const uniquenessLabel = col.uniqueValues !== null ? col.uniqueValues.toLocaleString() : "—";
              const distributionLabel = col.outlier
                ? `${(col.outlier.fraction * 100).toFixed(1)}% outliers`
                : col.outlierApplicable
                ? "Not evaluated"
                : "—";
              return (
                <tr
                  key={col.column}
                  onClick={() => onSelectColumn(col.column)}
                  className={cn(
                    "cursor-pointer transition-colors",
                    isSelected ? "bg-blue-50/70" : "hover:bg-slate-50/70",
                  )}
                >
                  <td className="whitespace-nowrap px-6 py-3.5 font-medium text-slate-900">{col.column}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-[13px] text-slate-500">{col.type}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-[13px] text-slate-600">{completenessLabel}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-[13px] text-slate-600">{uniquenessLabel}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-[13px] text-slate-500">{distributionLabel}</td>
                  <td className="whitespace-nowrap px-6 py-3.5">
                    <StatusBadge status={col.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
