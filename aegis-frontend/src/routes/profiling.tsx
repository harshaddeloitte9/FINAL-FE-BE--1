import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import PlotlyChart from "@/components/plotly-chart";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { AlertCircle, AlertTriangle, ArrowLeft, ArrowRight, BarChart3, CheckCircle2, ChevronDown, Download, Info } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export const Route = createFileRoute("/profiling")({
  head: () => ({ meta: [{ title: "Data Profiling — Aegis Credit" }] }),
  component: Profiling,
});

const CLASS_DISTRIBUTION_COLORS = ["#065f46", "#10b981", "#6ee7b7", "#a7f3d0"];

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

// Diverging green-family scale for correlation cells: teal = negative, emerald = positive,
// intensity scales with |value| so weak correlations read as near-neutral. Both hues stay
// within the app's green palette while remaining distinguishable by their blue undertone.
function correlationCellStyle(value: number): { backgroundColor: string; color: string } {
  const clamped = Math.max(-1, Math.min(1, value ?? 0));
  const intensity = Math.abs(clamped);
  const [r, g, b] = clamped >= 0 ? [5, 150, 105] : [13, 148, 136];
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

function severityBadgeClasses(severity?: string): string {
  if (severity === "high") return "bg-red-100 text-red-700";
  if (severity === "medium") return "bg-amber-100 text-amber-700";
  if (severity === "low") return "bg-emerald-100 text-emerald-700";
  return "bg-muted text-muted-foreground";
}

function SeverityIcon({ severity }: { severity?: string }) {
  if (severity === "high") return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-600" />;
  if (severity === "medium") return <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-600" />;
  if (severity === "low") return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />;
  return <Info className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
}

// Compliance rule text can run to full regulatory paragraphs (e.g. macro
// variable / leakage rules cite chapter and verse). Show only the first
// sentence as a summary; the full text is available on expand.
function summarizeFlag(text: string, maxLength = 110): string {
  if (!text) return "";
  const firstSentenceMatch = text.match(/^.*?[.!?](?=\s|$)/);
  const firstSentence = firstSentenceMatch ? firstSentenceMatch[0].trim() : text;
  if (firstSentence.length <= maxLength) return firstSentence;
  return `${firstSentence.slice(0, maxLength).trim()}…`;
}

function isFlagSummarized(text: string): boolean {
  return summarizeFlag(text) !== text.trim();
}

function Profiling() {
  const { file, profile, setProfile } = useDataset();
  const navigate = useNavigate();
  const [selectedTarget, setSelectedTarget] = useState<string | null>(profile?.target_col ?? null);
  const [activeProfile, setActiveProfile] = useState(profile);
  const [isLoadingTarget, setIsLoadingTarget] = useState(false);
  const [targetError, setTargetError] = useState<string | null>(null);
  const [expandedFlags, setExpandedFlags] = useState<Set<number>>(new Set());

  const toggleFlagExpanded = (idx: number) => {
    setExpandedFlags((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

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
  const classDistribution = active.class_distribution ?? null;
  const targetSummary = active.target_summary ?? null;
  const correlationColumns: string[] = active.correlation_matrix?.columns ?? [];
  const correlationValues: number[][] = active.correlation_matrix?.values ?? [];
  const dataDictionary = active.data_dictionary ?? [];
  const leakageRiskCols = active.leakage_risk_cols ?? [];
  const dateIntegrity = active.date_integrity ?? {};
  const dateIntegrityEntries = Object.entries(dateIntegrity);
  const agent2Flags = active.agent2_flags_data ?? [];
  const agent2Error = active.agent2_error ?? null;

  const classChartData = useMemo(() => {
    if (!classDistribution) return [];
    return Object.entries(classDistribution).map(([name, value]) => ({ name, value: Number(value) }));
  }, [classDistribution]);

  const classDistributionFigure = useMemo(() => {
    if (!classChartData || classChartData.length === 0) return null;
    return {
      data: [
        {
          type: "pie",
          labels: classChartData.map((entry) => entry.name),
          values: classChartData.map((entry) => entry.value),
          hole: 0.45,
          marker: {
            colors: classChartData.map((_, index) => CLASS_DISTRIBUTION_COLORS[index % CLASS_DISTRIBUTION_COLORS.length]),
          },
          textinfo: "percent",
          hovertemplate: "%{label}: %{value:,}<br>%{percent}<extra></extra>",
        },
      ],
      layout: {
        margin: { t: 10, r: 10, b: 10, l: 10 },
        legend: { orientation: "h", y: -0.15 },
      },
    };
  }, [classChartData]);

  const sortedFlags = useMemo(
    () => [...agent2Flags].sort((a: any, b: any) => severityRank(a.severity) - severityRank(b.severity)),
    [agent2Flags]
  );
  const flagSeverityCounts = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 };
    for (const flag of agent2Flags as any[]) {
      if (flag.severity === "high") counts.high += 1;
      else if (flag.severity === "medium") counts.medium += 1;
      else if (flag.severity === "low") counts.low += 1;
    }
    return counts;
  }, [agent2Flags]);

  const downloadDataSummary = () => {
    const headers = dataDictionary.length > 0 ? Object.keys(dataDictionary[0]) : [];
    const csv = [headers.join(","), ...dataDictionary.map(formatCsvRow)].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "data_summary.csv";
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
          <Stat
            label="Total Rows"
            value={rows !== null ? rows.toLocaleString() : "—"}
            sub={active.dataset_name ?? "Number of records in the dataset"}
          />
          <Stat
            label="Total Columns"
            value={cols !== null ? String(cols) : "—"}
            sub={numericCount !== null && categoricalCount !== null ? `${numericCount} numeric · ${categoricalCount} categorical` : "Number of fields in the dataset"}
          />
          <Stat
            label="Missing Values"
            value={missingCells !== null ? missingCells.toLocaleString() : missingPct !== null ? `${missingPct}%` : "—"}
            sub={missingPct !== null ? `${missingPct}% of all data cells are empty` : undefined}
          />
          <Stat
            label="Duplicate Rows"
            value={duplicateRows !== null ? String(duplicateRows) : "—"}
            sub={duplicateRate !== null ? `${duplicateRate}% of rows are exact copies of another row` : "Rows that are exact copies of another row"}
          />
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

      <section className="grid grid-cols-1 gap-4">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-base font-semibold">Target variable</h2>
              <p className="text-xs text-muted-foreground">Choose the target column to compute distribution, imbalance, and task diagnostics.</p>
            </div>
            <div className="flex items-center gap-3">
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
              <Button variant="outline" size="sm" onClick={downloadDataSummary} className="shrink-0 gap-2">
                <Download className="h-4 w-4" />
                Download data summary
              </Button>
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
            <div className="mt-4 rounded-xl border border-border bg-card">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <span>{agent2Flags.length} compliance flag{agent2Flags.length === 1 ? "" : "s"}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {flagSeverityCounts.high > 0 && (
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${severityBadgeClasses("high")}`}>
                      {flagSeverityCounts.high} high
                    </span>
                  )}
                  {flagSeverityCounts.medium > 0 && (
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${severityBadgeClasses("medium")}`}>
                      {flagSeverityCounts.medium} medium
                    </span>
                  )}
                  {flagSeverityCounts.low > 0 && (
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${severityBadgeClasses("low")}`}>
                      {flagSeverityCounts.low} low
                    </span>
                  )}
                </div>
              </div>
              <div className="divide-y divide-border">
                {sortedFlags.map((flag: any, idx: number) => {
                  const isOpen = expandedFlags.has(idx);
                  const summary = summarizeFlag(flag.flag ?? "");
                  const hasMore = isFlagSummarized(flag.flag ?? "") || flag.observed_value != null || flag.suggestion || flag.source || flag.principle;
                  return (
                    <div key={`${flag.rule_id ?? "flag"}-${idx}`} className={`border-l-4 px-4 py-2.5 ${severityClasses(flag.severity)}`}>
                      <button
                        type="button"
                        onClick={() => hasMore && toggleFlagExpanded(idx)}
                        className={`flex w-full items-start gap-2 text-left ${hasMore ? "cursor-pointer" : "cursor-default"}`}
                      >
                        <SeverityIcon severity={flag.severity} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                            <span>{flag.rule_id ?? "?"}</span>
                            {flag.not_verifiable && <span className="italic normal-case">· not verifiable</span>}
                          </div>
                          <div className="mt-0.5 text-xs text-foreground">{summary}</div>
                        </div>
                        {hasMore && (
                          <ChevronDown className={`mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
                        )}
                      </button>
                      {isOpen && hasMore && (
                        <div className="mt-2 space-y-1.5 pl-5 text-xs text-muted-foreground">
                          {isFlagSummarized(flag.flag ?? "") && <div>{flag.flag}</div>}
                          {flag.observed_value !== undefined && flag.observed_value !== null && (
                            <div>Observed: <code className="text-foreground">{String(flag.observed_value)}</code></div>
                          )}
                          {flag.suggestion && <div>💡 {flag.suggestion}</div>}
                          {(flag.source || flag.principle) && (
                            <div className="text-[11px] text-muted-foreground/70">
                              {flag.source}{flag.source && flag.principle ? " — " : ""}{flag.principle}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
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

          <div className="mt-4 border-t border-border pt-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">Class Distribution</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedTarget ? (
                <>How the selected target column (<code className="text-foreground">{selectedTarget}</code>) is split across the dataset</>
              ) : (
                "Select a target column above to see its value breakdown."
              )}
            </p>

            {classDistribution ? (
              <div className="mt-4 grid items-center gap-6 lg:grid-cols-[1fr_1.2fr]">
                <div className="grid gap-3">
                  {classChartData.map((entry, index) => {
                    const total = classChartData.reduce((sum, e) => sum + e.value, 0);
                    const pct = total > 0 ? (entry.value / total) * 100 : 0;
                    return (
                      <div key={entry.name} className="rounded-lg border border-border bg-background p-4">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span
                              className="h-2.5 w-2.5 shrink-0 rounded-full"
                              style={{ backgroundColor: CLASS_DISTRIBUTION_COLORS[index % CLASS_DISTRIBUTION_COLORS.length] }}
                            />
                            {selectedTarget} = {entry.name}
                          </span>
                          <span className="text-xl font-semibold tabular-nums text-foreground">{entry.value.toLocaleString()}</span>
                        </div>
                        <div className="mt-1 pl-[18px] text-xs text-muted-foreground">{pct.toFixed(1)}% of records</div>
                      </div>
                    );
                  })}
                </div>
                <div className="h-72">
                  <PlotlyChart figure={classDistributionFigure} style={{ height: "100%", minHeight: "100%" }} />
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-border bg-muted p-4 text-sm text-muted-foreground">Class distribution is not available until a valid target is selected.</div>
            )}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[0.55fr_1.45fr]">
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
                          <span className="truncate">{column}</span>
                          <span className="shrink-0 font-medium tabular-nums">{(((info as any).outlier_fraction ?? 0) * 100).toFixed(1)}%</span>
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
                <div className="flex justify-center overflow-x-auto">
                  <table style={{ borderCollapse: "separate", borderSpacing: "4px", width: "100%", maxWidth: "480px" }}>
                    <thead>
                      <tr>
                        <th className="p-0.5" />
                        {correlationColumns.map((column) => (
                          <th
                            key={column}
                            title={column}
                            className="max-w-[56px] truncate p-0.5 text-[10px] font-medium text-muted-foreground"
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
                            className="whitespace-nowrap p-0.5 pr-2 text-right text-[10px] font-medium text-muted-foreground"
                          >
                            {rowColumn.length > 10 ? `${rowColumn.slice(0, 9)}…` : rowColumn}
                          </th>
                          {(correlationValues[rowIndex] ?? []).map((value, colIndex) => (
                            <td
                              key={`${rowColumn}-${correlationColumns[colIndex]}`}
                              title={`${rowColumn} × ${correlationColumns[colIndex]}: ${value.toFixed(2)}`}
                              className="h-9 w-9 rounded-md text-center align-middle text-xs font-medium tabular-nums"
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
                <div className="mx-auto mt-3 flex max-w-[480px] items-center gap-2 text-xs text-muted-foreground">
                  <span>-1</span>
                  <div
                    className="h-2 flex-1 rounded-full"
                    style={{ background: "linear-gradient(to right, rgba(13,148,136,0.9), rgba(148,163,184,0.15), rgba(5,150,105,0.9))" }}
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
