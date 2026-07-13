import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AlertTriangle, ArrowLeft, ArrowRight, BarChart3, Download, FileText, Info, Table2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export const Route = createFileRoute("/profiling")({
  head: () => ({ meta: [{ title: "Data Profiling — Aegis Credit" }] }),
  component: Profiling,
});

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function formatCsvRow(row: Record<string, any>) {
  return Object.values(row)
    .map((value) => {
      if (value === undefined || value === null) return "";
      const text = String(value).replace(/"/g, '""');
      return `"${text}"`;
    })
    .join(",");
}

// Diverging red/blue scale for correlation cells: blue = negative, red = positive,
// intensity scales with |value| so weak correlations read as near-neutral.
function correlationCellStyle(value: number): { backgroundColor: string; color: string } {
  const clamped = Math.max(-1, Math.min(1, value ?? 0));
  const intensity = Math.abs(clamped);
  const [r, g, b] = clamped >= 0 ? [239, 68, 68] : [59, 130, 246];
  return {
    backgroundColor: `rgba(${r}, ${g}, ${b}, ${(0.1 + intensity * 0.8).toFixed(2)})`,
    color: intensity > 0.5 ? "#ffffff" : "inherit",
  };
}

function severityRank(severity?: string): number {
  if (severity === "high") return 0;
  if (severity === "medium") return 1;
  if (severity === "low") return 2;
  return 3;
}

function severityClasses(severity?: string): string {
  if (severity === "high") return "border-red-500 bg-red-500/5 text-red-900";
  if (severity === "medium") return "border-amber-500 bg-amber-500/5 text-amber-900";
  if (severity === "low") return "border-emerald-500 bg-emerald-500/5 text-emerald-900";
  return "border-border bg-muted text-muted-foreground";
}

function Profiling() {
  const { file, profile, setProfile } = useDataset();
  const navigate = useNavigate();
  const [selectedTarget, setSelectedTarget] = useState<string | null>(profile?.target_col ?? null);
  const [activeProfile, setActiveProfile] = useState(profile);
  const [isLoadingTarget, setIsLoadingTarget] = useState(false);
  const [targetError, setTargetError] = useState<string | null>(null);

  useEffect(() => {
    setActiveProfile(profile);
  }, [profile]);

  const availableTargets = profile?.target_candidates ?? [];
  const availableColumns = profile?.columns ?? [];
  const candidateDefault = availableColumns.includes("loan_status")
    ? "loan_status"
    : availableTargets.length > 0
    ? availableTargets[0]
    : availableColumns[0] ?? null;

  useEffect(() => {
    if (!selectedTarget && candidateDefault) {
      setSelectedTarget(candidateDefault);
    }
  }, [candidateDefault, selectedTarget]);

  useEffect(() => {
    if (!file || !selectedTarget || !profile) return;
    if (profile.target_col === selectedTarget && profile.class_distribution) {
      return;
    }

    const fetchTargetProfile = async () => {
      setIsLoadingTarget(true);
      setTargetError(null);
      try {
        const form = new FormData();
        form.append("file", file);
        form.append("target_col", selectedTarget);
        const result = await formUpload("/data/profile", form);
        setActiveProfile(result as any);
        setProfile(result as any);
      } catch (err: any) {
        setTargetError(err?.message ?? "Failed to update profile for selected target.");
      } finally {
        setIsLoadingTarget(false);
      }
    };

    fetchTargetProfile();
  }, [file, profile, selectedTarget, setProfile]);

  if (!profile) {
    return (
      <div className="space-y-8">
        <PageHeader title="Data Profiling" description="Schema, quality, balance and correlation diagnostics for the active dataset." />
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No dataset available</h3>
          <p className="mt-2 text-sm text-muted-foreground">Upload a dataset on the Data Upload page to run profiling and populate these diagnostics.</p>
        </div>
      </div>
    );
  }

  const active = activeProfile ?? profile;
  const rows = active.shape?.[0] ?? null;
  const cols = active.shape?.[1] ?? null;
  const numericCount = active.numeric_feature_count ?? null;
  const categoricalCount = active.categorical_feature_count ?? null;
  const missingCells = active.missing_cells ?? null;
  const missingPct = active.missing_percentage ?? null;
  const duplicateRows = active.duplicate_rows ?? null;
  const duplicateRate = active.duplicate_rate ?? null;
  const outlierAnalysis = active.outlier_analysis ?? {};
  const outlierEntriesAll = Object.entries(outlierAnalysis as Record<string, any>);
  const outlierEntries = outlierEntriesAll.filter(([, info]) => ((info as any)?.outlier_fraction ?? 0) > 0);
  const missingByColumn = active.missing_by_column
    ? Object.entries(active.missing_by_column).map(([col, value]) => ({
        col,
        count: (value as any).count,
        percentage: (value as any).percentage,
      }))
    : [];
  const sortedMissing = [...missingByColumn].sort((a, b) => b.count - a.count).slice(0, 10);
  const classDistribution = active.class_distribution ?? null;
  const targetSummary = active.target_summary ?? null;
  const correlationColumns: string[] = active.correlation_matrix?.columns ?? [];
  const correlationValues: number[][] = active.correlation_matrix?.values ?? [];
  const dataDictionary = active.data_dictionary ?? [];
  const columnTypeTable = active.column_type_table ?? [];
  const summaryStats = active.summary_stats ?? [];
  const distributionHistograms = active.distribution_histograms ?? [];
  const leakageRiskCols = active.leakage_risk_cols ?? [];
  const dateIntegrity = active.date_integrity ?? {};
  const dateIntegrityEntries = Object.entries(dateIntegrity);
  const agent2Flags = active.agent2_flags_data ?? [];
  const agent2Error = active.agent2_error ?? null;

  const classChartData = useMemo(() => {
    if (!classDistribution) return [];
    return Object.entries(classDistribution).map(([name, value]) => ({ name, value: Number(value) }));
  }, [classDistribution]);

  const downloadDataDictionary = () => {
    const headers = dataDictionary.length > 0 ? Object.keys(dataDictionary[0]) : [];
    const csv = [headers.join(","), ...dataDictionary.map(formatCsvRow)].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "data_dictionary.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const taskTypeLabel = active.task_type === "binary"
    ? "Binary Classification"
    : active.task_type === "multiclass"
    ? "Multiclass Classification"
    : active.task_type === "regression"
    ? "Regression"
    : "Unspecified";

  const taskBadgeVariant = active.task_type === "binary" ? "default" : active.task_type === "multiclass" ? "secondary" : active.task_type === "regression" ? "outline" : "secondary";

  return (
    <div className="space-y-8">
      <PageHeader title="Data Profiling" description="Schema, quality, balance and correlation diagnostics for the active dataset." />

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Rows" value={rows !== null ? rows.toLocaleString() : "—"} sub={active.dataset_name ?? undefined} />
          <Stat
            label="Columns"
            value={cols !== null ? String(cols) : "—"}
            sub={numericCount !== null && categoricalCount !== null ? `${numericCount} numeric · ${categoricalCount} categorical` : undefined}
          />
          <Stat
            label="Missing cells"
            value={missingCells !== null ? missingCells.toLocaleString() : missingPct !== null ? `${missingPct}%` : "—"}
            sub={missingPct !== null ? `${missingPct}% of total` : undefined}
          />
          <Stat label="Duplicates" value={duplicateRows !== null ? String(duplicateRows) : "—"} sub={duplicateRate !== null ? `${duplicateRate}% of rows` : undefined} />
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Target Task</div>
              <div className="mt-1 text-lg font-semibold text-foreground">{taskTypeLabel}</div>
            </div>
            <Badge variant={taskBadgeVariant}>{taskTypeLabel}</Badge>
          </div>
          <div className="mt-4 space-y-2 text-sm text-muted-foreground">
            <div>Detected target candidates: {availableTargets.length > 0 ? availableTargets.join(", ") : "None"}</div>
            <div>Preferred target: {candidateDefault ?? "Not detected"}</div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-base font-semibold">Target variable</h2>
              <p className="text-xs text-muted-foreground">Choose the target column to compute distribution, imbalance, and task diagnostics.</p>
            </div>
            <div className="w-full lg:w-64">
              <Select value={selectedTarget ?? ""} onValueChange={(value) => setSelectedTarget(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select target" />
                </SelectTrigger>
                <SelectContent>
                  {availableColumns.map((column) => (
                    <SelectItem key={column} value={column}>{column}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {isLoadingTarget && (
            <div className="mt-4 rounded-xl border border-border bg-muted p-3 text-sm text-muted-foreground">Updating target diagnostics…</div>
          )}
          {targetError && (
            <div className="mt-4 rounded-xl border border-destructive bg-destructive/10 p-3 text-sm text-destructive">{targetError}</div>
          )}
          {agent2Error && (
            <div className="mt-4 rounded-xl border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
              <div className="font-medium">Data compliance check could not be completed.</div>
              <div className="mt-1 text-xs">{agent2Error}</div>
            </div>
          )}
          {agent2Flags.length > 0 && (
            <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4" />
                <span>{agent2Flags.length} data compliance flag{agent2Flags.length === 1 ? "" : "s"} detected for this dataset.</span>
              </div>
              <div className="mt-3 space-y-2">
                {[...agent2Flags]
                  .sort((a: any, b: any) => severityRank(a.severity) - severityRank(b.severity))
                  .map((flag: any, idx: number) => (
                    <div
                      key={`${flag.rule_id ?? "flag"}-${idx}`}
                      className={`rounded-lg border-l-4 bg-card p-2.5 text-xs text-foreground ${severityClasses(flag.severity)}`}
                    >
                      <div className="font-medium">
                        <span className="text-muted-foreground">[{flag.rule_id ?? "?"}]</span> {flag.flag}
                        {flag.not_verifiable && (
                          <span className="ml-1 italic text-muted-foreground">· not verifiable with current data</span>
                        )}
                      </div>
                      {flag.observed_value !== undefined && flag.observed_value !== null && (
                        <div className="mt-1 text-muted-foreground">Observed: <code>{String(flag.observed_value)}</code></div>
                      )}
                      {flag.suggestion && <div className="mt-1 text-muted-foreground">💡 {flag.suggestion}</div>}
                      {(flag.source || flag.principle) && (
                        <div className="mt-1 text-[11px] text-muted-foreground/70">
                          {flag.source}{flag.source && flag.principle ? " — " : ""}{flag.principle}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            </div>
          )}
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-background p-3">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                <Info className="h-4 w-4" />
                <span>Quality checks</span>
              </div>
              <div className="mt-2 text-sm text-foreground">
                {targetSummary?.is_imbalanced ? "Target class imbalance detected." : "Target distribution appears balanced for the current profile."}
              </div>
              {targetSummary?.imbalance_ratio ? (
                <div className="mt-2 text-xs text-muted-foreground">Imbalance ratio: {targetSummary.imbalance_ratio}:1</div>
              ) : null}
            </div>
            <div className="rounded-lg border border-border bg-background p-3">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                <AlertTriangle className="h-4 w-4" />
                <span>Leakage & dates</span>
              </div>
              <div className="mt-2 text-sm text-foreground">
                {leakageRiskCols.length > 0
                  ? `${leakageRiskCols.length} potential leakage column${leakageRiskCols.length === 1 ? "" : "s"}`
                  : "No strong leakage signals detected."}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                {dateIntegrityEntries.length > 0
                  ? `${dateIntegrityEntries.length} date field${dateIntegrityEntries.length === 1 ? "" : "s"} checked for future/ancient values`
                  : "No date fields detected."}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-base font-semibold">Class distribution</h2>
              </div>
              <p className="text-xs text-muted-foreground">Counts for the selected target value.</p>
            </div>
            <Button variant="outline" size="sm" onClick={downloadDataDictionary} className="gap-2">
              <Download className="h-4 w-4" />
              Download data dictionary
            </Button>
          </div>

          {classDistribution ? (
            <div className="mt-5 grid gap-3">
              {classChartData.map((entry) => (
                <div key={entry.name} className="rounded-lg border border-border bg-background p-3">
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{entry.name}</span>
                    <span className="font-semibold tabular-nums">{entry.value.toLocaleString()}</span>
                  </div>
                </div>
              ))}
              <div className="mt-3 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={classChartData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={80} paddingAngle={2}>
                      {classChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={["#6366f1", "#f59e0b", "#10b981", "#ef4444"][index % 4]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => [value.toLocaleString(), "Count"]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-border bg-muted p-4 text-sm text-muted-foreground">Class distribution is not available until a valid target is selected.</div>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-base font-semibold">Duplicate and outlier signals</h2>
          </div>
          <div className="mt-4 space-y-3 text-sm text-muted-foreground">
            <div className="rounded-lg border border-border bg-background p-3">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Duplicate rate</div>
              <div className="mt-1 text-lg font-semibold text-foreground">{duplicateRate !== null ? `${duplicateRate}%` : "—"}</div>
              <div className="mt-1 text-xs">{duplicateRows !== null ? `${duplicateRows.toLocaleString()} duplicate row${duplicateRows === 1 ? "" : "s"}` : "No duplicate count available"}</div>
            </div>
            <div className="rounded-lg border border-border bg-background p-3">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Outlier checks</div>
              <div className="mt-1 text-sm text-foreground">
                {outlierEntries.length > 0 ? (
                  <>
                    {[...outlierEntries]
                      .sort(([, a], [, b]) => ((b as any).outlier_fraction ?? 0) - ((a as any).outlier_fraction ?? 0))
                      .slice(0, 4)
                      .map(([column, info]) => (
                        <div key={column} className="mt-2 flex items-center justify-between gap-2">
                          <span>{column}</span>
                          <span className="font-medium tabular-nums">{(((info as any).outlier_fraction ?? 0) * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    {outlierEntries.length > 4 && (
                      <div className="mt-2 text-xs text-muted-foreground">+{outlierEntries.length - 4} more column{outlierEntries.length - 4 === 1 ? "" : "s"} with outliers</div>
                    )}
                  </>
                ) : outlierEntriesAll.length > 0 ? (
                  "No numeric columns have flagged outliers."
                ) : (
                  "No numeric outlier analysis available."
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-base font-semibold">Correlation snapshot</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Pearson correlation across numeric features (up to 10 columns).</p>
          <div className="mt-4">
            {correlationColumns.length > 0 && correlationValues.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <table style={{ borderCollapse: "separate", borderSpacing: "3px" }}>
                    <thead>
                      <tr>
                        <th className="p-1" />
                        {correlationColumns.map((column) => (
                          <th
                            key={column}
                            title={column}
                            className="max-w-[56px] truncate p-1 text-[10px] font-medium text-muted-foreground"
                          >
                            {column.length > 7 ? `${column.slice(0, 6)}…` : column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {correlationColumns.map((rowColumn, rowIndex) => (
                        <tr key={rowColumn}>
                          <th
                            title={rowColumn}
                            className="whitespace-nowrap p-1 pr-2 text-right text-[10px] font-medium text-muted-foreground"
                          >
                            {rowColumn.length > 10 ? `${rowColumn.slice(0, 9)}…` : rowColumn}
                          </th>
                          {(correlationValues[rowIndex] ?? []).map((value, colIndex) => (
                            <td
                              key={`${rowColumn}-${correlationColumns[colIndex]}`}
                              title={`${rowColumn} × ${correlationColumns[colIndex]}: ${value.toFixed(2)}`}
                              className="h-8 w-8 rounded-sm text-center align-middle text-[11px] font-medium tabular-nums"
                              style={correlationCellStyle(value)}
                            >
                              {value.toFixed(2)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span>-1</span>
                  <div
                    className="h-2 flex-1 rounded-full"
                    style={{ background: "linear-gradient(to right, rgba(59,130,246,0.9), rgba(148,163,184,0.15), rgba(239,68,68,0.9))" }}
                  />
                  <span>+1</span>
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">No numeric correlation matrix available for this dataset.</div>
            )}
          </div>
        </div>
      </section>

      <Tabs defaultValue="summary">
        <TabsList>
          <TabsTrigger value="summary">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              <span>Summary Stats</span>
            </div>
          </TabsTrigger>
          <TabsTrigger value="missing">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span>Missing Values</span>
            </div>
          </TabsTrigger>
          <TabsTrigger value="types">
            <div className="flex items-center gap-2">
              <Table2 className="h-4 w-4" />
              <span>Column Types</span>
            </div>
          </TabsTrigger>
          <TabsTrigger value="distributions">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span>Distributions</span>
            </div>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            {summaryStats.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      {Object.keys(summaryStats[0]).map((column) => (
                        <th key={column} className="border-b border-border px-3 py-2 text-left text-xs uppercase tracking-wide text-muted-foreground">{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {summaryStats.map((row: Record<string, any>, rowIndex: number) => (
                      <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : "bg-card"}>
                        {Object.values(row).map((value, cellIndex) => (
                          <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs text-foreground">{String(value)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Summary statistics are not available for this dataset.</div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="missing">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            {sortedMissing.length > 0 ? (
              <div className="space-y-6">
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="px-3 py-2">Column</th>
                        <th className="px-3 py-2">Missing</th>
                        <th className="px-3 py-2">Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedMissing.map((row) => (
                        <tr key={row.col} className="odd:bg-background">
                          <td className="border-b border-border px-3 py-2">{row.col}</td>
                          <td className="border-b border-border px-3 py-2 tabular-nums">{row.count.toLocaleString()}</td>
                          <td className="border-b border-border px-3 py-2">{row.percentage.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={sortedMissing} layout="vertical" margin={{ left: 30, right: 20 }}>
                      <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} unit="%" />
                      <YAxis type="category" dataKey="col" tickLine={false} axisLine={false} fontSize={11} width={170} />
                      <Tooltip formatter={(value) => [`${value}%`, "Missing"]} />
                      <Bar dataKey="percentage" fill="oklch(0.76 0.18 130)" radius={[0, 6, 6, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No missing values were detected for this dataset.</div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="types">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant overflow-x-auto">
            {columnTypeTable.length > 0 ? (
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    {Object.keys(columnTypeTable[0]).map((column) => (
                      <th key={column} className="px-3 py-2">{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {columnTypeTable.map((row: Record<string, any>, rowIndex: number) => (
                    <tr key={row.Column} className={rowIndex % 2 === 0 ? "bg-background" : "bg-card"}>
                      {Object.values(row).map((value, cellIndex) => (
                        <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs text-foreground">{String(value)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-sm text-muted-foreground">Column type details are not available for this dataset.</div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="distributions">
          <div className="grid gap-4">
            {distributionHistograms.length > 0 ? (
              distributionHistograms.map((hist) => (
                <div key={hist.column} className="rounded-xl border border-border bg-card p-4 shadow-elegant">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold">{hist.column}</div>
                      <div className="text-xs text-muted-foreground">Numeric distribution across dataset</div>
                    </div>
                  </div>
                  <div className="h-40">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={hist.bins.map((bin: number, index: number) => ({ bin: `${bin.toFixed(1)}`, count: hist.counts[index] }))}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="bin" tickLine={false} axisLine={false} fontSize={10} />
                        <YAxis tickLine={false} axisLine={false} fontSize={10} />
                        <Tooltip formatter={(value) => [value.toLocaleString(), "Count"]} />
                        <Bar dataKey="count" fill="oklch(0.76 0.18 130)" radius={4} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">Numeric distributions are not available for this dataset.</div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {active && (
        <div className="flex gap-3 pt-4">
          <Button variant="outline" onClick={() => navigate({ to: "/data-upload" })} className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Data Upload
          </Button>
          <Button onClick={() => navigate({ to: "/preprocessing" })} className="gap-2 ml-auto">
            Proceed to Preprocessing
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
