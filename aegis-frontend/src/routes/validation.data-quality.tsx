import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { ArrowRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, AreaChart, Area } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

type ValidationResultRow = {
  id: string;
  title: string;
  source: string;
  principle: string;
  severity: "high" | "medium" | "low" | string;
  status: "PASS" | "WARN" | "FAIL";
  observed: string;
  threshold: string;
  detail: string;
};

function buildValidationCsv(rows: ValidationResultRow[]) {
  const header = [
    "Check ID",
    "Title",
    "Source",
    "Principle",
    "Severity",
    "Status",
    "Observed",
    "Threshold",
    "Detail",
  ];
  const escape = (value: string | number | null | undefined) => {
    const text = value == null ? "" : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };
  const lines = [header.map(escape).join(",")];
  for (const row of rows) {
    lines.push(
      [
        row.id,
        row.title,
        row.source,
        row.principle,
        row.severity.toUpperCase(),
        row.status,
        row.observed,
        row.threshold,
        row.detail,
      ].map(escape).join(","),
    );
  }
  return lines.join("\n");
}

function getStage2ThresholdChecks(profile: any): ValidationResultRow[] {
  if (!profile) return [];

  const rowCount = Number(profile?.shape?.[0] ?? 0);
  const colCount = Number(profile?.shape?.[1] ?? 0);
  const columns = Array.isArray(profile?.columns) ? profile.columns : [];
  const targetCandidates = Array.isArray(profile?.target_candidates) ? profile.target_candidates : [];
  const leakageRiskCols = Array.isArray(profile?.leakage_risk_cols) ? profile.leakage_risk_cols : [];
  const missingByColumn = profile?.missing_by_column ?? {};
  const duplicateRatePct = Number(profile?.duplicate_rate ?? 0);
  const dateIntegrity = profile?.date_integrity ?? {};
  const targetSummary = profile?.target_summary ?? {};
  const preprocessingLoaded = Boolean(profile?.preprocessing_report);

  const missingEntries = Object.entries(missingByColumn).map(([column, value]: any) => ({
    column,
    percentage: Number(value?.percentage ?? 0),
  }));
  const worstMissing = missingEntries.sort((a, b) => b.percentage - a.percentage)[0] ?? { percentage: 0, column: "" };
  const missingStatus = worstMissing.percentage > 20 ? "FAIL" : worstMissing.percentage > 10 ? "WARN" : "PASS";

  const macroKeywords = ["gdp", "unemployment", "hpi", "inflation", "rate", "macro", "cpi", "index"];
  const macroColumns = columns.filter((column: string) => macroKeywords.some((keyword) => column.toLowerCase().includes(keyword)));
  const macroStatus = macroColumns.length > 0 ? "PASS" : "FAIL";

  let histStatus: ValidationResultRow["status"] = "WARN";
  let histObserved = "No date column detected — coverage cannot be verified automatically.";
  let histYears = 0;
  const dateColumns = Object.keys(dateIntegrity);
  if (dateColumns.length > 0) {
    const firstDateCol = dateColumns[0];
    const firstDate = new Date(dateIntegrity[firstDateCol]?.min_date ?? "");
    const lastDate = new Date(dateIntegrity[firstDateCol]?.max_date ?? "");
    if (!Number.isNaN(firstDate.getTime()) && !Number.isNaN(lastDate.getTime())) {
      histYears = Math.max(0, (lastDate.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25));
      histStatus = histYears >= 5 ? "PASS" : histYears >= 3 ? "WARN" : "FAIL";
      histObserved = `${histYears.toFixed(1)} years in column '${firstDateCol}'`;
    }
  }

  const defaultStatus = targetCandidates.length > 0 ? "WARN" : "FAIL";
  const defaultObserved = targetCandidates.length > 0 ? `Candidates: ${targetCandidates.join(", ")}` : "No candidate target column detected";

  const duplicateRateFraction = duplicateRatePct / 100;
  const duplicateStatus = duplicateRateFraction > 0.01 ? "FAIL" : duplicateRateFraction > 0.001 ? "WARN" : "PASS";

  let imbalanceStatus: ValidationResultRow["status"] = "WARN";
  let imbalanceObserved = "No binary target column detected automatically.";
  const classDistribution = profile?.class_distribution ?? {};
  const counts = Object.values(classDistribution).map((value: any) => Number(value)).filter((count) => !Number.isNaN(count));
  if (counts.length === 2 && counts.every((count) => count >= 0)) {
    const [minCount, maxCount] = counts.sort((a, b) => a - b);
    const ratio = maxCount > 0 ? minCount / maxCount : 0;
    const total = maxCount + minCount;
    const minorityPct = total > 0 ? minCount / total : 0;
    imbalanceObserved = `Minority class: ${Math.round(minorityPct * 1000) / 10}% | Ratio: ${ratio.toFixed(2)}`;
    imbalanceStatus = ratio > 0.33 ? "PASS" : ratio > 0.1 ? "WARN" : "FAIL";
  }

  return [
    {
      id: "2.1",
      title: "Row/Column Reconciliation",
      source: "SS11/13",
      principle: "§10.4",
      severity: "high",
      status: "PASS",
      observed: `${rowCount.toLocaleString()} rows × ${colCount.toLocaleString()} columns`,
      threshold: "Dataset must be loadable",
      detail: "Dataset loaded successfully. Cross-reference against developer-reported row count manually.",
    },
    {
      id: "2.2",
      title: "Missing Data Rate",
      source: "SS1/23",
      principle: "P3.2",
      severity: "high",
      status: missingStatus,
      observed: `Max missing: ${worstMissing.percentage.toFixed(1)}% in column '${worstMissing.column}'`,
      threshold: "< 20% per column",
      detail: "High missing rates introduce bias and undermine model stability. SS1/23 P3.2 requires evidence of appropriate treatment.",
    },
    {
      id: "2.3",
      title: "Default Definition Consistency",
      source: "IFRS 9",
      principle: "B5.5.28",
      severity: "high",
      status: defaultStatus,
      observed: defaultObserved,
      threshold: "Target column identifiable; 90-DPD definition confirmed",
      detail: "Validator must confirm default = 90 DPD or document alternatives with regulatory justification.",
    },
    {
      id: "2.4",
      title: "Macro Variables Present",
      source: "IFRS 9",
      principle: "B5.5.49",
      severity: "medium",
      status: macroStatus,
      observed: macroColumns.length > 0 ? macroColumns.join(", ") : "None detected",
      threshold: "At least one macroeconomic variable required",
      detail: "IFRS 9 B5.5.49 requires forward-looking macroeconomic information or documentation for its absence.",
    },
    {
      id: "2.5",
      title: "Historical Coverage ≥ 5 Years",
      source: "SS11/13",
      principle: "§10.1",
      severity: "high",
      status: histStatus,
      observed: histObserved,
      threshold: "≥ 5 years preferred; ≥ 3 years minimum",
      detail: "SS11/13 §10.1 requires sufficient historical data covering at least one economic cycle.",
    },
    {
      id: "2.6",
      title: "Sampling Strategy Documented",
      source: "SS1/23",
      principle: "P3.2",
      severity: "medium",
      status: "WARN",
      observed: "Manual review required — cannot be automated.",
      threshold: "Sampling methodology documented in MDD",
      detail: "Validator must confirm sampling methodology in the submitted model development documentation.",
    },
    {
      id: "2.7",
      title: "Transformations Documented",
      source: "SS1/23",
      principle: "P3.5",
      severity: "medium",
      status: preprocessingLoaded ? "PASS" : "WARN",
      observed: preprocessingLoaded ? "Profile report submitted" : "No profile report submitted.",
      threshold: "Data dictionary / profile report must be submitted",
      detail: "If transformation documentation is not submitted, request it from the model developer.",
    },
    {
      id: "2.8",
      title: "Target Leakage Detection",
      source: "SS1/23",
      principle: "P3.5",
      severity: "high",
      status: leakageRiskCols.length > 0 ? "FAIL" : "PASS",
      observed: leakageRiskCols.length > 0 ? leakageRiskCols.join(", ") : "No suspected leakage columns found",
      threshold: "No post-default or high-correlation (>0.95) features",
      detail: "Post-default features and near-perfect correlates with the target are likely leakage and must be excluded.",
    },
    {
      id: "2.9",
      title: "Duplicate Record Rate",
      source: "SS1/23",
      principle: "P3.2",
      severity: "low",
      status: duplicateStatus,
      observed: `${Math.round(duplicateRateFraction * 10000) / 100}% duplicate records`,
      threshold: "< 1%",
      detail: "Duplicate records inflate effective sample size and may bias model estimates.",
    },
    {
      id: "2.10",
      title: "Class Imbalance",
      source: "SS1/23",
      principle: "P3.2",
      severity: "medium",
      status: imbalanceStatus,
      observed: imbalanceObserved,
      threshold: "> 0.33 (3:1 or better)",
      detail: "Severe class imbalance requires explicit treatment documented in the MDD.",
    },
  ];
}

export const Route = createFileRoute("/validation/data-quality")({
  head: () => ({ meta: [{ title: "Data Validation — Aegis Credit" }] }),
  component: DataQuality,
});

function DataQuality() {
  const {
    file,
    profile,
    validationIntakeData,
    validationMddText,
    validationMddMetrics,
    validationProfile: sharedValidationProfile,
    validationResults: sharedValidationResults,
    setValidationProfile,
    setValidationResults,
  } = useDataset();
  const [validationProfile, setValidationProfileState] = useState<any | null>(sharedValidationProfile ?? null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showAiDeepCheck, setShowAiDeepCheck] = useState(true);

  const datasetLoaded = Boolean(file || profile?.csv_text || profile?.dataset_name);
  const validationReport = validationProfile?.agent2_report;
  const thresholdChecks = useMemo(() => getStage2ThresholdChecks(validationProfile), [validationProfile]);
  const rawAgentFlags = (validationProfile?.agent2_flags_data ?? validationReport?.all_flags ?? []) as any[];
  const agent2Summary = (validationReport?.summary ?? {}) as Record<string, any>;
  const agent2Status = String(agent2Summary.overall_status ?? (rawAgentFlags.length > 0 ? "WARN" : "PASS")).toUpperCase();
  const agent2ComplianceScore = typeof agent2Summary.compliance_score === "number" ? agent2Summary.compliance_score : 0;
  const agent2SeverityBreakdown = {
    high: Number(agent2Summary.high_severity ?? 0),
    medium: Number(agent2Summary.medium_severity ?? 0),
    low: Number(agent2Summary.low_severity ?? 0),
  };
  const aiTone = agent2Status === "PASS" ? "pass" : agent2Status === "WARN" ? "warn" : "fail";

  const runDataValidation = async () => {
    if (!datasetLoaded) return;
    setRunError(null);
    setIsRunning(true);
    try {
      const form = new FormData();
      if (file) {
        form.append("file", file);
      } else if (profile?.csv_text) {
        form.append("csv_text", profile.csv_text);
      } else {
        throw new Error("No dataset available to validate.");
      }

      const result = await formUpload("/data/profile", form);
      const nextProfile = result as any;
      setValidationProfileState(nextProfile);
      setValidationProfile(nextProfile);
      setValidationResults({
        profile: nextProfile,
        intake: validationIntakeData ?? null,
        mddText: validationMddText ?? null,
        mddMetrics: validationMddMetrics ?? null,
      });
    } catch (error: any) {
      setRunError(error?.message ?? "Failed to run validation checks.");
    } finally {
      setIsRunning(false);
    }
  };

  useEffect(() => {
    if (!datasetLoaded || validationProfile || isRunning) return;

    void runDataValidation();
  }, [datasetLoaded, validationProfile, isRunning, file, profile?.csv_text, profile?.dataset_name]);

  useEffect(() => {
    if (sharedValidationProfile && !validationProfile) {
      setValidationProfileState(sharedValidationProfile);
    }
  }, [sharedValidationProfile, validationProfile]);

  const combinedResults = useMemo(() => {
    if (!validationProfile) return [];
    const agentFlagRows: ValidationResultRow[] = rawAgentFlags.map((flag: any) => {
      const severity = String(flag.severity ?? "medium").toLowerCase();
      const status = severity === "high" ? "FAIL" : severity === "medium" ? "WARN" : "PASS";
      return {
        id: flag.rule_id ?? String(flag.flag ?? ""),
        title: flag.flag ?? String(flag.title ?? ""),
        source: flag.source ?? "",
        principle: flag.principle ?? "",
        severity: flag.severity ?? "medium",
        status,
        observed: Array.isArray(flag.observed_value) ? flag.observed_value.join(", ") : String(flag.observed_value ?? ""),
        threshold: "",
        detail: flag.suggestion ?? "",
      };
    });
    return [...thresholdChecks, ...agentFlagRows];
  }, [thresholdChecks, rawAgentFlags]);

  const totalChecks = combinedResults.length;
  const passCount = combinedResults.filter((row) => row.status === "PASS").length;
  const warnCount = combinedResults.filter((row) => row.status === "WARN").length;
  const failCount = combinedResults.filter((row) => row.status === "FAIL").length;
  const flags = rawAgentFlags;
  const sourceSummary = Object.entries(validationReport?.flags_by_source ?? {}).map(([source, items]) => `${source}: ${(items as any[]).length}`);

  const missingChartData = useMemo(() => {
    if (!validationProfile?.missing_by_column) return [];
    return Object.entries(validationProfile.missing_by_column)
      .map(([feature, stats]: any) => ({ feature, pct: Number(stats?.percentage ?? 0) }))
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 10);
  }, [validationProfile]);

  const distributionChartData = useMemo(() => {
    const histograms = validationProfile?.distribution_histograms;
    if (!Array.isArray(histograms) || histograms.length === 0) return [];
    const first = histograms[0];
    if (!Array.isArray(first?.bins) || !Array.isArray(first?.counts)) return [];
    return first.bins.slice(0, -1).map((bin: number, idx: number) => ({
      bin: `${Number(first.bins[idx]).toFixed(2)}–${Number(first.bins[idx + 1]).toFixed(2)}`,
      count: Number(first.counts[idx] ?? 0),
    }));
  }, [validationProfile]);

  const validationCsv = useMemo(() => {
    if (!validationProfile) return "";
    const combinedRows: ValidationResultRow[] = [
      ...thresholdChecks,
      ...rawAgentFlags.map((flag: any) => {
        const severity = String(flag.severity ?? "medium").toLowerCase();
        const status: ValidationResultRow["status"] = severity === "high" ? "FAIL" : severity === "medium" ? "WARN" : "PASS";
        return {
          id: flag.rule_id ?? String(flag.flag ?? ""),
          title: flag.flag ?? String(flag.title ?? ""),
          source: flag.source ?? "",
          principle: flag.principle ?? "",
          severity: flag.severity ?? "medium",
          status,
          observed: Array.isArray(flag.observed_value) ? flag.observed_value.join(", ") : String(flag.observed_value ?? ""),
          threshold: "",
          detail: flag.suggestion ?? "",
        };
      }),
    ];
    return buildValidationCsv(combinedRows);
  }, [thresholdChecks, rawAgentFlags]);

  const downloadValidationReport = () => {
    const blob = new Blob([validationCsv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "data_validation_report.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const summaryRows: Array<{ label: string; value: string; tone?: "pass" | "warn" | "fail" }> = [
    { label: "Checks", value: totalChecks.toString() },
    { label: "PASS", value: passCount.toString(), tone: "pass" },
    { label: "WARN", value: warnCount.toString(), tone: "warn" },
    { label: "FAIL", value: failCount.toString(), tone: "fail" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 2 — Data Validation"
        description="Automated validation checks for the active dataset uploaded in the previous stage."
      />

      {datasetLoaded ? (
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-4 text-sm text-emerald-900 shadow-elegant">
          ✅ Dataset ready — {profile?.shape?.[0] ?? "?"} rows × {profile?.shape?.[1] ?? "?"} columns
        </div>
      ) : (
        <div className="rounded-xl border border-yellow-400/20 bg-yellow-500/10 p-4 text-sm text-yellow-900 shadow-elegant">
          ⚠️ No dataset is loaded from Intake. Upload the dataset in Stage 1 before running validation.
        </div>
      )}

      {validationProfile ? (
        <>
          <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Automated validation summary</h3>
              <p className="mt-2 text-sm text-foreground/80">This stage verifies the dataset submitted in Intake and flags any issues that affect model validity.</p>
              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {summaryRows.map((item) => (
                  <Stat key={item.label} label={item.label} value={item.value} tone={item.tone} />
                ))}
              </div>
              <div className="mt-3 rounded-xl border border-dashed border-border bg-background p-3 text-sm text-muted-foreground">
                Dataset ready — {profile?.shape?.[0] ?? "?"} rows × {profile?.shape?.[1] ?? "?"} columns.
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Stage outcome</h3>
              <p className="mt-2 text-sm text-foreground/80">Data Validation reports on the active dataset already loaded from Stage 1; no new upload is required here.</p>
              <div className="mt-4 flex flex-col gap-3">
                <button
                  type="button"
                  onClick={downloadValidationReport}
                  disabled={!validationProfile || (!thresholdChecks.length && !flags.length)}
                  className="inline-flex items-center justify-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-semibold text-foreground shadow-elegant hover:bg-slate-950/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Download Data Validation Report
                </button>
                <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-2 text-xs font-semibold text-primary">
                  Validation profile loaded
                </div>
                {runError ? (
                  <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                    {runError}
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-violet-400/30 bg-violet-500/10 p-6 shadow-elegant">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-violet-600 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-white">AI Deep-Check</span>
                  <h3 className="text-sm font-semibold text-foreground">Agent2 diagnostics and rule review</h3>
                </div>
                <p className="mt-2 text-sm text-foreground/80">Toggle this optional section to inspect Agent2 findings without re-uploading the dataset.</p>
              </div>
              <button
                type="button"
                onClick={() => setShowAiDeepCheck((current) => !current)}
                className="inline-flex items-center justify-center rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-elegant transition hover:bg-violet-700"
              >
                {showAiDeepCheck ? "Hide AI Deep-Check" : "Run AI Deep-Check"}
              </button>
            </div>

            {showAiDeepCheck ? (
              <div className="mt-5 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                <div className="rounded-xl border border-violet-400/20 bg-background p-4">
                  <div className="text-sm font-semibold text-foreground">Agent2 diagnostics</div>
                  <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat label="Status" value={agent2Status} tone={aiTone} />
                    <Stat label="Compliance" value={`${Math.round(agent2ComplianceScore)}%`} tone={aiTone} />
                    <Stat label="High" value={String(agent2SeverityBreakdown.high)} tone="fail" />
                    <Stat label="Medium" value={String(agent2SeverityBreakdown.medium)} tone="warn" />
                  </div>
                  {validationProfile?.agent2_error ? (
                    <div className="mt-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                      {validationProfile.agent2_error}
                    </div>
                  ) : null}
                  <div className="mt-4 rounded-xl border border-dashed border-border bg-background/60 p-3 text-sm text-muted-foreground">
                    {rawAgentFlags.length > 0
                      ? `Agent2 surfaced ${rawAgentFlags.length} findings from the active profile. Review the details below for the next remediation steps.`
                      : "The current dataset does not yet produce any Agent2 findings. The deep-check will populate once the standard validation profile is available."}
                  </div>
                </div>

                <div className="rounded-xl border border-violet-400/20 bg-background p-4">
                  <div className="text-sm font-semibold text-foreground">Diagnostic details</div>
                  <div className="mt-4 space-y-3 text-sm">
                    <div className="rounded-lg border border-border bg-background p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Rule sources</div>
                      <div className="mt-2 space-y-1">
                        {sourceSummary.length > 0 ? sourceSummary.map((summary) => <div key={summary} className="text-foreground">• {summary}</div>) : <div className="text-muted-foreground">No source summary is available.</div>}
                      </div>
                    </div>
                    <div className="rounded-lg border border-border bg-background p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Turned into findings</div>
                      <div className="mt-2 space-y-2">
                        {rawAgentFlags.length > 0 ? rawAgentFlags.slice(0, 6).map((flag: any, index: number) => (
                          <div key={`${flag.rule_id ?? index}-${flag.flag ?? index}`} className="rounded-lg border border-border/70 bg-background/80 p-3">
                            <div className="text-sm font-semibold text-foreground">{flag.flag ?? flag.rule_id ?? `Finding ${index + 1}`}</div>
                            <div className="mt-1 text-xs text-muted-foreground">{flag.source ?? "Agent2"} · {flag.principle ?? "Rule review"}</div>
                            {flag.suggestion ? <div className="mt-2 text-sm text-muted-foreground">{flag.suggestion}</div> : null}
                          </div>
                        )) : <div className="text-muted-foreground">No Agent2 findings were returned for the current validation profile.</div>}
                      </div>
                    </div>
                    {validationReport?.model_tier ? <div className="rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">Model tier: {validationReport.model_tier}</div> : null}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-5 rounded-xl border border-dashed border-violet-400/30 bg-background/70 p-4 text-sm text-muted-foreground">
                The AI deep-check is ready. Use the button above to review the existing Agent2 diagnostics for the active dataset.
              </div>
            )}
          </section>

          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="grid min-w-0 gap-4 xl:grid-cols-[0.75fr_1.25fr]">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">Validation results</p>
                    <p className="text-xs text-muted-foreground">Automated rule and threshold checks performed against the active dataset.</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Total agent rules</div>
                    <div className="mt-1 text-2xl font-semibold text-foreground">{totalChecks}</div>
                  </div>
                </div>
                <div className="mt-5 grid grid-cols-3 gap-3">
                  <SummaryCard label="PASS" value={passCount.toString()} tone="pass" />
                  <SummaryCard label="WARN" value={warnCount.toString()} tone="warn" />
                  <SummaryCard label="FAIL" value={failCount.toString()} tone="fail" />
                </div>
                <div className="mt-5 rounded-full bg-slate-950/70 p-1">
                  <div className="h-2 rounded-full bg-emerald-500" style={{ width: totalChecks ? `${Math.round((passCount / totalChecks) * 100)}%` : "0%" }} />
                </div>
              </div>
              <div className="grid min-w-0 gap-3 md:grid-cols-2">
                <div className="min-w-0 rounded-xl border border-border bg-background p-4">
                  <div className="text-sm font-semibold text-foreground">Recommended threshold checks</div>
                  <p className="mt-2 text-xs text-muted-foreground">Quantitative checks against dataset quality and validation requirements.</p>
                </div>
                <div className="min-w-0 rounded-xl border border-border bg-background p-4">
                  <div className="text-sm font-semibold text-foreground">RAG agent rules</div>
                  <p className="mt-2 text-xs text-muted-foreground">Regulatory findings from the knowledge store and dataset rule checks.</p>
                  <div className="mt-3 space-y-1 text-xs text-foreground">
                    {sourceSummary.length > 0 ? sourceSummary.map((summary) => (
                      <div key={summary} className="break-words">• {summary}</div>
                    )) : <div>No source summary available.</div>}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="min-w-0 rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Recommended threshold checks</h3>
              <div className="mt-5 space-y-4">
                {thresholdChecks.length > 0 ? (
                  thresholdChecks.map((check) => (
                    <ThresholdCheckCard key={check.id} check={check} />
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-border bg-background p-5 text-sm text-muted-foreground">
                    No threshold checks are available for the current dataset.
                  </div>
                )}
              </div>
            </div>

            <div className="min-w-0 space-y-6">
              <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
                <h3 className="text-sm font-semibold">RAG Agent validation flags</h3>
                <div className="mt-5 space-y-4">
                  {flags.length > 0 ? (
                    flags.map((flag: any) => (
                      <ValidationFlagCard key={`${flag.rule_id}-${flag.flag}`} flag={flag} />
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border bg-background p-5 text-sm text-muted-foreground">
                      No validation flags were generated for this dataset.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
                <h3 className="text-sm font-semibold">Missing values by feature</h3>
                {missingChartData.length > 0 ? (
                  <div className="mt-4 h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={missingChartData}>
                        <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                        <XAxis dataKey="feature" tickLine={false} axisLine={false} fontSize={10} />
                        <YAxis tickLine={false} axisLine={false} fontSize={11} unit="%" />
                        <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                        <Bar dataKey="pct" fill="oklch(0.76 0.18 130)" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-muted-foreground">Missing value details are not available for the current dataset.</p>
                )}
              </div>

              <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
                <h3 className="text-sm font-semibold">Feature distribution preview</h3>
                {distributionChartData.length > 0 ? (
                  <div className="mt-4 h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={distributionChartData}>
                        <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                        <XAxis dataKey="bin" tickLine={false} axisLine={false} fontSize={10} />
                        <YAxis tickLine={false} axisLine={false} fontSize={11} />
                        <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                        <Area type="monotone" dataKey="count" stroke="oklch(0.55 0.02 240)" fill="oklch(0.55 0.02 240)" fillOpacity={0.25} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-muted-foreground">Feature distribution data is not available for the current dataset.</p>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Data leakage detection</h3>
              <p className="mt-2 text-sm text-foreground/80">
                {profile?.leakage_risk_cols && profile.leakage_risk_cols.length > 0
                  ? `Potential leakage detected: ${profile.leakage_risk_cols.join(", ")}`
                  : "No potential target leakage detected in the current dataset."}
              </p>
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Stage 2 validation</h3>
          <p className="mt-2 text-sm text-foreground/80">The dataset is loaded from Intake. Click the button below to run validation checks on the active dataset.</p>
          <div className="mt-4 flex flex-col gap-3">
            {isRunning ? (
              <div className="rounded-xl border border-primary/20 bg-primary-soft p-3 text-sm text-primary">
                Running validation checks…
              </div>
            ) : null}
            {runError ? (
              <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                {runError}
              </div>
            ) : null}
          </div>
        </section>
      )}

      <div className="text-right">
        <Link
          to="/validation/conceptual"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 3
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone: "pass" | "warn" | "fail" }) {
  const classes =
    tone === "pass"
      ? "border border-emerald-400/30 bg-emerald-500/10 text-emerald-200"
      : tone === "warn"
      ? "border border-amber-500/30 bg-amber-500/10 text-amber-100"
      : "border border-red-500/30 bg-red-500/10 text-red-100";

  return (
    <div className={`rounded-xl border p-4 ${classes}`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function ThresholdCheckCard({ check }: { check: ValidationResultRow }) {
  const tone = check.status === "PASS" ? "pass" : check.status === "WARN" ? "warn" : "fail";
  const borderClasses =
    check.status === "PASS"
      ? "border-emerald-400/30 bg-emerald-500/10"
      : check.status === "WARN"
      ? "border-amber-500/30 bg-amber-500/10"
      : "border-red-500/30 bg-red-500/10";

  return (
    <div className={`min-w-0 rounded-xl border p-4 ${borderClasses}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-foreground break-words">[{check.id}] {check.title}</div>
          <div className="mt-2 text-xs text-muted-foreground break-words">{check.source} · {check.principle}</div>
        </div>
        <div className="shrink-0 space-y-1 text-right">
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{check.status}</div>
          <div className="rounded-full border border-current px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]">{check.severity}</div>
        </div>
      </div>
      <div className="mt-3 text-sm text-foreground">Observed: {check.observed}</div>
      <div className="mt-2 text-sm text-foreground">Threshold: {check.threshold}</div>
      <div className="mt-2 text-sm text-muted-foreground">{check.detail}</div>
    </div>
  );
}

function ValidationFlagCard({ flag }: { flag: any }) {
  const severityClasses =
    flag.severity === "high"
      ? "border-red-500/30 bg-red-500/10"
      : flag.severity === "medium"
      ? "border-amber-500/30 bg-amber-500/10"
      : "border-emerald-500/30 bg-emerald-500/10";
  return (
    <div className={`min-w-0 rounded-xl border p-4 ${severityClasses}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-semibold text-foreground break-words">[{flag.rule_id}] {flag.flag}</div>
          <div className="mt-2 text-xs text-muted-foreground break-words">{flag.source} · {flag.principle}</div>
        </div>
        <span className="shrink-0 rounded-full border border-current px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]">
          {flag.severity?.toString()?.toUpperCase()}
        </span>
      </div>
      {flag.observed_value ? (
        <div className="mt-3 text-sm text-foreground">Observed: {Array.isArray(flag.observed_value) ? flag.observed_value.join(", ") : flag.observed_value}</div>
      ) : null}
      <div className="mt-3 text-sm text-muted-foreground">{flag.suggestion}</div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "pass" | "warn" | "fail" }) {
  const classes =
    tone === "pass"
      ? "border border-primary/30 bg-primary-soft text-foreground"
      : tone === "warn"
      ? "border border-warning/30 bg-warning-10 text-warning-foreground"
      : "border border-border bg-background text-foreground";

  return (
    <div className={`rounded-xl p-4 ${classes}`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold">{value}</div>
    </div>
  );
}
