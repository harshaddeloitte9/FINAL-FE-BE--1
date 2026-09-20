import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowRight,
  Loader2,
  Search,
  ShieldCheck,
  Microscope,
  Scale,
  ListChecks,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  MinusCircle,
  Clock,
} from "lucide-react";
import { ApiError, formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import PlotlyChart from "@/components/plotly-chart";
import { deriveCheckTotal } from "@/components/check-summary";
import { useResumeState } from "@/hooks/use-resume-state";
import { StageHero, HeroChip, VCard, VEmptyState, StatusPill, KpiStrip } from "@/components/validation-ui";

// Same hex palette / no-toolbar convention established on the redesigned
// Benchmarking and Stress & Backtesting pages — Plotly's bundled color
// parser can't read CSS Color 4 oklch() syntax and silently falls back to
// black (visible in the pre-redesign AUC chart's solid black bars), so every
// figure color below is plain hex/rgba instead.
const CHART_INDIGO = "#4f46e5";
const CHART_TEAL = "#0891b2";
const CHART_ROSE = "#e11d48";
const CHART_GRID = "#eef2ff";
const CHART_HOVERLABEL = { bgcolor: "#ffffff", bordercolor: "#c7d2fe", font: { size: 12, color: "#334155" } };
const NO_TOOLBAR_CONFIG = { displayModeBar: false, scrollZoom: false };

// Lightweight grouping header, same pattern used on the redesigned Stress &
// Backtesting page — purely presentational, duplicated locally rather than
// extracted into a shared file to keep this task's diff scoped to this page.
function SectionHeading({ eyebrow, description }: { eyebrow: string; description?: string }) {
  return (
    <div className="flex flex-col gap-1.5 pt-2">
      <div className="flex items-center gap-3">
        <span className="shrink-0 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{eyebrow}</span>
        <div className="h-px flex-1 bg-slate-200" />
      </div>
      {description ? <p className="text-xs text-slate-500">{description}</p> : null}
    </div>
  );
}

export const Route = createFileRoute("/validation/regulatory")({
  head: () => ({ meta: [{ title: "Stage 6 — Explainability and Fairness — Aegis Credit" }] }),
  component: Regulatory,
});

type Status = "PASS" | "WARN" | "FAIL" | string;

type ThresholdCheck = {
  check_id: string;
  title: string;
  severity: string;
  status: Status;
  source: string;
  principle: string;
  observed: string;
  threshold: string;
  detail: string;
  check_type?: string;
};

type Stage7Response = {
  checks: ThresholdCheck[];
  summary: { total: number; pass: number; warn: number; fail: number; pending?: number; na?: number };
};

type BiasRow = { Group: string; Count: number; "Default Rate": number; "Avg Predicted PD": number; AUC: number | null };

type BiasCheckResult = {
  check_id: string;
  title: string;
  severity: string;
  status: Status;
  source: string;
  principle: string;
  observed: string;
  threshold: string;
  detail: string;
  check_type?: string;
};

// check_type "data"/"cross_reference" checks compute a number against an
// industry-standard statistical convention (e.g. the Fair Lending bias
// check's "AUC gap < 0.05") — the cited regulation requires that kind of
// check to exist, not that specific cutoff. The 7.1-7.10 regulatory checks
// are check_type "doc" (genuinely quoting/requiring regulatory text) and
// keep their existing combined citation.
function isQuantitativeConventionCheck(checkType: string | undefined): boolean {
  return checkType === "data" || checkType === "cross_reference";
}

type BiasResponse = {
  success: boolean;
  error: string | null;
  protected_columns: string[];
  bias_col: string | null;
  rows: BiasRow[];
  check: BiasCheckResult | null;
};

const STATUS_TONE: Record<string, "pass" | "warn" | "fail" | "pending"> = {
  PASS: "pass",
  WARN: "warn",
  FAIL: "fail",
  PENDING: "pending",
};

const SEVERITY_STYLES: Record<string, string> = {
  HIGH: "border-red-200 bg-red-50 text-red-700",
  MEDIUM: "border-amber-200 bg-amber-50 text-amber-700",
  LOW: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

function ThresholdCheckCard({ check }: { check: ThresholdCheck }) {
  const tone = STATUS_TONE[check.status ?? ""] ?? "pending";
  const sevClasses = SEVERITY_STYLES[check.severity?.toUpperCase()] ?? "border-slate-200 bg-slate-100 text-slate-700";
  const isConvention = isQuantitativeConventionCheck(check.check_type);
  return (
    <div className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">[{check.check_id}]</span>
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${sevClasses}`}>
              {check.severity}
            </span>
          </div>
          <div className="mt-1 break-words text-sm font-semibold text-slate-900">{check.title}</div>
        </div>
        <StatusPill tone={tone}>{check.status}</StatusPill>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-3 text-xs leading-relaxed">
        <div className="text-slate-700">
          <span className="font-semibold uppercase tracking-wide text-slate-400">Observed </span>
          <code className="text-slate-700">{check.observed}</code>
        </div>
        <div className="text-slate-500">
          <span className="font-semibold uppercase tracking-wide text-slate-400">Threshold </span>
          {check.threshold}
          {isConvention ? " — industry-standard convention" : ""}
        </div>
        <div className="text-slate-500">
          <span className="font-semibold uppercase tracking-wide text-slate-400">Regulatory basis </span>
          {isConvention ? (
            <>
              {check.source} {check.principle} — requires this to be assessed/documented
            </>
          ) : (
            <>
              {check.source} — {check.principle}
            </>
          )}
        </div>
        {check.detail ? <div className="text-slate-500">{check.detail}</div> : null}
      </div>
    </div>
  );
}

function Regulatory() {
  const ds = useDataset();
  const {
    validationIntakeData,
    validationMddText,
    validationStage4Result,
    validationStage7Result,
    setValidationStage7Result,
    validationStage7BiasResult,
    setValidationStage7BiasResult,
  } = ds;

  const [loading, setLoading] = useState(!validationStage7Result);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<Stage7Response | null>((validationStage7Result as Stage7Response | null) ?? null);
  // Tracks which sub-tab is active so the bottom button can tell whether
  // the reviewer is still on the first sub-tab (Explainability and
  // Fairness — button just advances to Regulatory Compliance) or the last
  // one (button navigates to Stage 7).
  const [activeSubTab, setActiveSubTab] = useState<string>("explainability");

  const skipInitialAutoRun = useRef(validationStage7Result !== null && validationStage7Result !== undefined);

  useEffect(() => {
    if (skipInitialAutoRun.current) {
      skipInitialAutoRun.current = false;
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    const form = new FormData();
    form.append("intake_json", JSON.stringify(validationIntakeData ?? {}));
    if (validationMddText) {
      const mddBlob = new Blob([validationMddText], { type: "text/plain" });
      form.append("mdd_file", new File([mddBlob], "mdd.txt", { type: "text/plain" }));
    }

    void formUpload<Stage7Response>("/validation/stage7/run", form)
      .then((resp) => {
        if (!active) return;
        setData(resp);
        setValidationStage7Result(resp as unknown as Record<string, any>);
      })
      .catch((err) => {
        console.error("Stage7 fetch error", err);
        if (!active) return;
        setError(err?.message ?? String(err));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validationIntakeData, validationMddText]);

  const summary = data?.summary ?? { total: 0, pass: 0, warn: 0, fail: 0, pending: 0, na: 0 };
  const totalChecks = deriveCheckTotal(summary);
  const progress = totalChecks > 0 ? Math.round((summary.pass / totalChecks) * 100) : 0;

  const featureImportance = useMemo(() => {
    const rows = (validationStage4Result as any)?.replication?.result?.feature_importance as
      | Array<{ Feature: string; Importance: number }>
      | undefined;
    if (!rows || !rows.length) return [];
    return [...rows]
      .sort((a, b) => (b.Importance ?? 0) - (a.Importance ?? 0))
      .slice(0, 15)
      .reverse();
  }, [validationStage4Result]);

  const stage4Available = featureImportance.length > 0;

  // Dataset/target/model resolution mirrors validation.performance.tsx
  // (Stage 5) — the bias check reruns the train/split server-side since the
  // backend is stateless, so it needs the same inputs Stage 3/4 use.
  const targetCol = ds.profile?.target_col || ds.trainingResult?.evaluation_data?.target_col || "default";
  const modelName = ds.selectedModel?.name || ds.trainingResult?.model_name || "Logistic Regression";
  const datasetFile = useMemo<File | null>(() => {
    if (ds.file) return ds.file;
    const csvText = typeof ds.profile?.csv_text === "string" ? ds.profile.csv_text : "";
    if (!csvText.trim()) return null;
    const resolvedName = ds.profile?.dataset_name ?? "validation_dataset.csv";
    const safeName = resolvedName.endsWith(".csv") || resolvedName.endsWith(".xlsx") ? resolvedName : `${resolvedName}.csv`;
    return new File([csvText], safeName, { type: "text/csv" });
  }, [ds.file, ds.profile?.csv_text, ds.profile?.dataset_name]);

  const [biasData, setBiasData] = useState<BiasResponse | null>((validationStage7BiasResult as BiasResponse | null) ?? null);
  const [biasCol, setBiasCol] = useState<string>(() => (validationStage7BiasResult as BiasResponse | null)?.bias_col ?? "");
  const [biasLoading, setBiasLoading] = useState(false);
  const [biasError, setBiasError] = useState<string | null>(null);
  const columnsFetched = useRef(false);

  // Resume where the reviewer left off: this page maps to the
  // "fair_lending_bias" stage since it's the one that calls POST
  // /validation/stage7/bias-check. If nothing is loaded this session, pull
  // the last saved run from the backend rather than starting blank.
  const { data: resumedBias } = useResumeState<BiasResponse>(
    "validation_pipeline_log.csv",
    "fair_lending_bias",
  );
  useEffect(() => {
    if (!biasData && resumedBias) {
      setBiasData(resumedBias);
      setValidationStage7BiasResult(resumedBias as unknown as Record<string, any>);
      if (resumedBias.bias_col) setBiasCol(resumedBias.bias_col);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumedBias]);

  // Fetch just the detected protected-characteristic columns on first load
  // (no protected_col posted yet) so the dropdown can populate itself.
  useEffect(() => {
    if (columnsFetched.current || biasData || !datasetFile) return;
    columnsFetched.current = true;
    const form = new FormData();
    form.append("file", datasetFile);
    form.append("target_col", targetCol);
    form.append("model_name", modelName);
    void formUpload<BiasResponse>("/validation/stage7/bias-check", form)
      .then((resp) => setBiasData(resp))
      .catch(() => {
        /* silent — the "Run Bias Check" button re-attempts with a protected_col */
      });
  }, [datasetFile, targetCol, modelName, biasData]);

  // Default the dropdown to the first detected column once columns arrive,
  // rather than leaving it on the disabled "Choose a column…" placeholder.
  // Only fires when nothing is selected yet, so it never overrides a
  // selection the user (or a restored cached result) already made.
  useEffect(() => {
    if (biasCol || !biasData?.protected_columns?.length) return;
    setBiasCol(biasData.protected_columns[0]);
  }, [biasCol, biasData]);

  const runBiasCheck = useCallback(async () => {
    if (!datasetFile || !biasCol) return;
    setBiasLoading(true);
    setBiasError(null);
    try {
      const form = new FormData();
      form.append("file", datasetFile);
      form.append("target_col", targetCol);
      form.append("model_name", modelName);
      form.append("protected_col", biasCol);
      const resp = await formUpload<BiasResponse>("/validation/stage7/bias-check", form);
      setBiasData(resp);
      setValidationStage7BiasResult(resp as unknown as Record<string, any>);
    } catch (err) {
      setBiasError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Bias check failed.");
    } finally {
      setBiasLoading(false);
    }
  }, [datasetFile, targetCol, modelName, biasCol, setValidationStage7BiasResult]);

  const biasAucRows = (biasData?.rows ?? []).filter((r) => r.AUC !== null) as Array<BiasRow & { AUC: number }>;
  const biasAucMean = biasAucRows.length ? biasAucRows.reduce((s, r) => s + r.AUC, 0) / biasAucRows.length : 0;

  const featureImportanceFigure = useMemo(() => {
    if (!featureImportance.length) return null;
    return {
      data: [
        {
          type: "bar",
          orientation: "h",
          x: featureImportance.map((row) => row.Importance),
          y: featureImportance.map((row) => row.Feature),
          marker: { color: CHART_INDIGO, cornerradius: 3 },
          hovertemplate: "<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>",
          name: "Importance",
        },
      ],
      layout: {
        autosize: true,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        margin: { l: 150, r: 20, t: 10, b: 40 },
        xaxis: { title: { text: "Importance" }, tickfont: { size: 11 }, automargin: true, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { tickfont: { size: 11.5 }, automargin: true, autorange: "reversed", gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [featureImportance]);

  // Grows with the number of groups (rows can vary a lot by protected
  // characteristic — e.g. many distinct "age" values vs a handful of
  // "region" categories) so labels never get cramped, capped so a
  // high-cardinality column can't blow out the page.
  const biasAucChartHeight = Math.max(260, Math.min(520, biasAucRows.length * 26 + 60));

  const biasAucFigure = useMemo(() => {
    if (!biasAucRows.length) return null;
    return {
      data: [
        {
          type: "bar",
          x: biasAucRows.map((row) => row.AUC),
          y: biasAucRows.map((row) => row.Group),
          orientation: "h",
          marker: {
            // Same >0.05 AUC-gap flag the bar color always used — rose marks
            // a group the bias check itself would flag, teal a group within
            // the mean's normal range. No new threshold logic, just hex.
            color: biasAucRows.map((row) => (Math.abs(row.AUC - biasAucMean) > 0.05 ? CHART_ROSE : CHART_TEAL)),
            cornerradius: 3,
          },
          hovertemplate: "<b>%{y}</b><br>AUC: %{x:.4f}<extra></extra>",
          name: "AUC",
        },
        {
          type: "scatter",
          mode: "lines",
          x: Array(biasAucRows.length).fill(biasAucMean),
          y: biasAucRows.map((row) => row.Group),
          line: { color: CHART_INDIGO, dash: "dash", width: 2 },
          hovertemplate: `Mean AUC: ${biasAucMean.toFixed(4)}<extra></extra>`,
          showlegend: true,
          name: "Mean AUC",
        },
      ],
      layout: {
        autosize: true,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        // margin.b + legend.y give the legend row clear space below the
        // x-axis title instead of overlapping it — the same fix already
        // applied to the Benchmarking page's ROC chart for the identical
        // legend/axis-title collision.
        legend: { orientation: "h", y: -0.28, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 150, r: 20, t: 10, b: 68 },
        xaxis: { title: { text: "AUC" }, tickfont: { size: 11 }, automargin: true, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
        // Explicit "category" type: Group values (e.g. "0", "1", numeric-ish
        // ages) would otherwise be auto-typed as a numeric axis by Plotly's
        // own type inference, which turns readable per-group labels into a
        // sparse numeric scale — a real readability regression, not a data
        // change (the same Group strings the table already renders).
        yaxis: { type: "category", tickfont: { size: 11 }, automargin: true, autorange: "reversed", gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [biasAucRows, biasAucMean]);

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <StageHero
        eyebrow="STAGE 6 · MODEL VALIDATION"
        title="Explainability and Fairness"
        description="SS1/23 · SS11/13 · IFRS 9 · IFRS 7 — automated regulatory compliance checks and model explainability review."
        chips={
          data ? <HeroChip tone={progress === 100 ? "success" : "neutral"}>{summary.pass}/{totalChecks} compliance checks passed</HeroChip> : <HeroChip>Not yet run</HeroChip>
        }
      />

      {loading ? (
        <VEmptyState icon={Loader2} title="Loading Stage 6 checks…" description="Running explainability and regulatory compliance checks." />
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">Error loading Stage 6: {error}</div>
      ) : (
        <Tabs value={activeSubTab} onValueChange={setActiveSubTab} className="w-full">
          <TabsList>
            <TabsTrigger value="explainability">Explainability and Fairness</TabsTrigger>
            <TabsTrigger value="compliance">Regulatory Compliance</TabsTrigger>
          </TabsList>

          <TabsContent value="compliance" className="space-y-6 pt-4">
            <VCard icon={ShieldCheck} title="Regulatory Compliance Results (7.1–7.10)">
              <KpiStrip
                tiles={[
                  { icon: ListChecks, label: "Total Checks", value: totalChecks, tone: "slate" },
                  { icon: CheckCircle2, label: "Pass", value: summary.pass ?? 0, tone: "emerald" },
                  { icon: AlertTriangle, label: "Warn", value: summary.warn ?? 0, tone: "amber" },
                  { icon: XCircle, label: "Fail", value: summary.fail ?? 0, tone: "rose" },
                  { icon: MinusCircle, label: "N/A", value: summary.na ?? 0, tone: "slate" },
                  { icon: Clock, label: "Pending", value: summary.pending ?? 0, tone: "primary" },
                ]}
              />
              <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
              </div>
            </VCard>

            {data?.checks && data.checks.length > 0 ? (
              <div>
                <SectionHeading eyebrow="Compliance Findings" description="Every 7.1–7.10 check the backend evaluated for this run, most-recent result shown." />
                <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {data.checks.map((c) => (
                    <ThresholdCheckCard key={c.check_id} check={c} />
                  ))}
                </div>
              </div>
            ) : (
              <VEmptyState icon={ShieldCheck} title="No compliance checks yet" description="No regulatory compliance checks generated for this stage." />
            )}
          </TabsContent>

          <TabsContent value="explainability" className="space-y-6 pt-4">
            <VCard icon={Microscope} title="SHAP Feature Importance (from Stage 3 Replication)" sub="Reuses the replicated model's feature importances computed in Stage 3 — no re-training here.">
              {featureImportanceFigure ? (
                <div className="h-[420px] overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                  <PlotlyChart figure={featureImportanceFigure} style={{ height: "100%" }} config={NO_TOOLBAR_CONFIG} />
                </div>
              ) : (
                <VEmptyState icon={Microscope} title="Feature importances not available" description="Run Stage 3 Model Replication first to populate this chart." />
              )}
              {featureImportanceFigure && <p className="mt-2 text-xs text-slate-500">Top 15 Feature Importances (Replicated Model)</p>}
            </VCard>

            <VCard icon={Scale} title="Fair Lending Bias Check" sub="Check if model performance differs significantly across protected characteristics. Large gaps may indicate discriminatory bias.">
              {!datasetFile ? (
                <VEmptyState icon={Scale} title="No dataset available" description="Complete Stage 1 Intake and Stage 2 Data Validation first." />
              ) : biasData && biasData.protected_columns.length === 0 ? (
                <VEmptyState icon={Scale} title="No protected characteristics detected" description="Common ones: age, gender, region, employment, education." />
              ) : (
                <>
                  <div className="mt-4 flex flex-wrap items-end gap-3">
                    <label className="space-y-2 text-sm">
                      <span className="font-medium">Select characteristic to analyse for bias</span>
                      <select
                        value={biasCol}
                        onChange={(e) => setBiasCol(e.target.value)}
                        className="w-56 rounded-lg border border-slate-200 bg-white px-3 py-2"
                      >
                        <option value="" disabled>
                          Choose a column…
                        </option>
                        {(biasData?.protected_columns ?? []).map((col) => (
                          <option key={col} value={col}>
                            {col}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={() => void runBiasCheck()}
                      disabled={!biasCol || biasLoading}
                      className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {biasLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      Run Bias Check
                    </button>
                  </div>

                  {biasError ? <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{biasError}</div> : null}

                  {/* Overall bias-check finding — the backend already returns
                      this on every /validation/stage7/bias-check response
                      (BiasResponse.check), but it was fetched and never
                      rendered anywhere. Surfacing it here (reusing the same
                      ThresholdCheckCard used on the Compliance tab, since
                      BiasCheckResult has the identical shape) makes the
                      actual PASS/WARN/FAIL result visually prominent per the
                      requested hierarchy, using only data already fetched —
                      no new calculation or endpoint. */}
                  {biasData?.check ? (
                    <div className="mt-4">
                      <ThresholdCheckCard check={biasData.check} />
                    </div>
                  ) : null}

                  {biasData?.rows && biasData.rows.length > 0 ? (
                    <>
                      <div className="mt-5">
                        <SectionHeading eyebrow="Group-Level Comparison" />
                        <div className="mt-3 max-h-[420px] overflow-y-auto overflow-x-auto rounded-xl border border-slate-200">
                          <table className="w-full text-sm">
                            <thead className="sticky top-0 z-10">
                              <tr className="border-y border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                                <th className="px-3 py-2 text-left">#</th>
                                <th className="px-3 py-2 text-left">Group</th>
                                <th className="px-3 py-2 text-right">Count</th>
                                <th className="px-3 py-2 text-right">Default Rate</th>
                                <th className="px-3 py-2 text-right">Avg Predicted PD</th>
                                <th className="px-3 py-2 text-right">AUC</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                              {biasData.rows.map((r, rowIndex) => (
                                <tr key={r.Group} className="hover:bg-slate-50/60">
                                  <td className="px-3 py-2 text-slate-400">{rowIndex + 1}</td>
                                  <td className="px-3 py-2 font-medium text-slate-900">{r.Group}</td>
                                  <td className="px-3 py-2 text-right tabular-nums">{r.Count.toLocaleString()}</td>
                                  <td className="px-3 py-2 text-right tabular-nums">{(r["Default Rate"] * 100).toFixed(2)}%</td>
                                  <td className="px-3 py-2 text-right tabular-nums">{(r["Avg Predicted PD"] * 100).toFixed(2)}%</td>
                                  <td className="px-3 py-2 text-right tabular-nums">{r.AUC !== null ? r.AUC.toFixed(4) : "N/A"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {biasAucFigure ? (
                        <div className="mt-5">
                          <SectionHeading eyebrow="AUC by Group" description="Dashed line marks the mean AUC across groups; a group more than 0.05 away from it is flagged." />
                          <div
                            className="mt-3 overflow-hidden rounded-xl border border-slate-100 bg-white p-1"
                            style={{ height: `${biasAucChartHeight}px` }}
                          >
                            <PlotlyChart figure={biasAucFigure} style={{ height: "100%" }} config={NO_TOOLBAR_CONFIG} />
                          </div>
                        </div>
                      ) : null}
                    </>
                  ) : null}

                </>
              )}
            </VCard>
          </TabsContent>
        </Tabs>
      )}

      <div className="text-right">
        {activeSubTab === "explainability" ? (
          <button
            type="button"
            onClick={() => setActiveSubTab("compliance")}
            className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
          >
            Continue
            <ArrowRight className="h-4 w-4" />
          </button>
        ) : (
          <Link
            to="/validation/findings"
            className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
          >
            Continue to Stage 7
            <ArrowRight className="h-4 w-4" />
          </Link>
        )}
      </div>
    </div>
  );
}
