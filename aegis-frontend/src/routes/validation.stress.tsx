import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Activity,
  TrendingUp,
  Gauge,
  LineChart,
  Compass,
  Zap,
  PlayCircle,
  Loader2,
  AlertCircle,
  Database,
  ListChecks,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  MinusCircle,
  Clock,
} from "lucide-react";
import PlotlyChart from "@/components/plotly-chart";
import { deriveCheckTotal } from "@/components/check-summary";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { useResumeState } from "@/hooks/use-resume-state";
import { StageHero, HeroChip, VCard, VEmptyState, StatusPill, KpiStrip } from "@/components/validation-ui";

export const Route = createFileRoute("/validation/stress")({
  head: () => ({ meta: [{ title: "Stress & Backtesting — Aegis Credit" }] }),
  component: Stress,
});

const FREQ_OPTIONS: { key: string; label: string }[] = [
  { key: "monthly", label: "Monthly" },
  { key: "quarterly", label: "Quarterly" },
  { key: "half_yearly", label: "Half-Yearly" },
  { key: "yearly", label: "Yearly" },
];

// Same hex palette convention established on the redesigned Benchmarking
// page (/validation/performance) — Plotly's bundled color parser can't read
// CSS Color 4 oklch()/lab() syntax and silently falls back to black, which
// is why this page's charts previously rendered with default/black styling
// despite already specifying oklch() colors. Kept distinct per pair: a
// baseline/primary series in indigo, and a "shocked"/"actual"/"challenger"
// counterpart in teal or amber depending on what it represents.
const CHART_INDIGO = "#4f46e5";
const CHART_TEAL = "#0891b2";
const CHART_AMBER = "#ea580c";
const CHART_GRID = "#eef2ff";
const CHART_HOVERLABEL = { bgcolor: "#ffffff", bordercolor: "#c7d2fe", font: { size: 12, color: "#334155" } };
const NO_TOOLBAR_CONFIG = { displayModeBar: false, scrollZoom: false };

function statusTone(status: string | undefined): "pass" | "warn" | "fail" | "pending" {
  switch (status) {
    case "PASS":
      return "pass";
    case "WARN":
      return "warn";
    case "FAIL":
      return "fail";
    default:
      return "pending";
  }
}

// Lightweight grouping header used to separate the page's analytical
// sections (Sensitivity / Score Stability / Macro Stress / Backtesting /
// Directional Testing) without wrapping each one in yet another large card —
// purely presentational, same idea as a table-of-contents rule.
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

// Every check rendered through this card (sensitivity AUC drop, PSI, backtest
// gap) is a quantitative statistical check — the cited regulation requires
// this kind of check to be performed, not the specific numeric cutoff, which
// is an industry-standard convention. Split the two so the citation isn't
// misread as the source of the number itself.
function CheckCard({ check }: { check: { id: string; title: string; status: string; observed: string; threshold: string; source: string } }) {
  const tone = statusTone(check.status);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Finding [{check.id}]</div>
          <div className="mt-0.5 text-sm font-semibold text-slate-900">{check.title}</div>
        </div>
        <StatusPill tone={tone}>{check.status}</StatusPill>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-700">{check.observed}</p>
      <div className="mt-3 grid grid-cols-1 gap-1 border-t border-slate-100 pt-2 text-[11px] text-slate-500 sm:grid-cols-2">
        <div>Regulatory basis: <span className="text-slate-600">{check.source}</span> — requires this to be assessed/documented</div>
        <div>Threshold: <span className="text-slate-600">{check.threshold}</span> — industry-standard convention</div>
      </div>
    </div>
  );
}

function Stress() {
  const { file, profile } = useDataset();
  const datasetName = profile?.dataset_name ?? file?.name ?? "the active validation dataset";
  const datasetReady = Boolean(file || profile?.csv_text || profile?.dataset_name);
  const columns: string[] = useMemo(() => (profile?.columns ?? profile?.col_types?.all ?? []) as string[], [profile]);

  const [algorithms, setAlgorithms] = useState<string[]>([]);
  const [targetCol, setTargetCol] = useState<string>("");
  const [algorithm, setAlgorithm] = useState<string>("");
  const [freq, setFreq] = useState<string>("quarterly");

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [report, setReport] = useState<any | null>(null);

  const [shockFeature, setShockFeature] = useState<string>("");
  const [shockDirection, setShockDirection] = useState<"increase" | "decrease">("increase");
  const [shockMagnitude, setShockMagnitude] = useState<number>(20);
  const [shockRunning, setShockRunning] = useState(false);
  const [shockError, setShockError] = useState<string | null>(null);
  const [shockResult, setShockResult] = useState<any | null>(null);

  // Resume where the reviewer left off: if this session has no stress-test
  // report yet, pull the last saved /validation/stress/run from the backend.
  const { data: resumedStress } = useResumeState<{ stage: string; report: any }>(
    "validation_pipeline_log.csv",
    "stress_testing",
  );
  useEffect(() => {
    if (!report && resumedStress?.report) {
      setReport(resumedStress.report);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumedStress]);

  useEffect(() => {
    void api<{ models: string[] }>("/models/list")
      .then((res) => {
        setAlgorithms(res.models ?? []);
        setAlgorithm((prev) => prev || res.models?.[0] || "");
      })
      .catch(() => setAlgorithms([]));
  }, []);

  useEffect(() => {
    if (!targetCol && columns.length > 0) {
      // Best-effort default: prefer an obvious target-sounding column, else the last column.
      const guess = columns.find((c) => /default|target|label|bad_flag/i.test(c)) ?? columns[columns.length - 1];
      setTargetCol(guess);
    }
  }, [columns, targetCol]);

  useEffect(() => {
    if (!shockFeature && report?.available && report.numeric_features?.length) {
      setShockFeature(report.numeric_features[0]);
    }
  }, [report, shockFeature]);

  const buildForm = () => {
    const form = new FormData();
    if (file) {
      form.append("file", file);
    } else if (profile?.csv_text) {
      form.append("csv_text", profile.csv_text);
    }
    form.append("target_col", targetCol);
    form.append("algorithm", algorithm);
    return form;
  };

  const runStressSuite = async () => {
    if (!datasetReady || !targetCol || !algorithm) return;
    setRunError(null);
    setRunning(true);
    setShockResult(null);
    try {
      const form = buildForm();
      form.append("freq", freq);
      const resp = await formUpload<{ stage: string; report: any }>("/validation/stress/run", form);
      setReport(resp.report ?? null);
      if (!resp.report?.available) {
        setRunError(resp.report?.reason ?? "Stress suite did not return a usable result.");
      }
    } catch (error: any) {
      setReport(null);
      setRunError(error?.message ?? "Failed to run stress & backtesting checks.");
    } finally {
      setRunning(false);
    }
  };

  const hasAutoRun = useRef(false);
  useEffect(() => {
    if (hasAutoRun.current) return;
    if (!datasetReady || !targetCol || !algorithm || running) return;
    hasAutoRun.current = true;
    void runStressSuite();
  }, [datasetReady, targetCol, algorithm]);

  // Backtesting only re-buckets already-computed predictions by calendar
  // period — it needs no retraining — so the backend now returns every
  // frequency's periods up front in backtest_by_freq. Switching the
  // dropdown reads from that instantly instead of re-running the whole
  // (expensive: retrains the model + full ablation sweep from scratch)
  // stress suite just to re-bucket the same numbers.
  const activeBacktest = useMemo(() => {
    return report?.backtest_by_freq?.[freq] ?? report?.backtest ?? null;
  }, [report, freq]);


  const applyShock = async () => {
    if (!shockFeature || !targetCol || !algorithm) return;
    setShockError(null);
    setShockRunning(true);
    try {
      const form = buildForm();
      form.append("shock_feature", shockFeature);
      form.append("shock_direction", shockDirection);
      form.append("shock_magnitude_pct", String(shockMagnitude));
      const resp = await formUpload<{ stage: string; result: any }>("/validation/stress/shock", form);
      setShockResult(resp.result ?? null);
    } catch (error: any) {
      setShockResult(null);
      setShockError(error?.message ?? "Shock failed.");
    } finally {
      setShockRunning(false);
    }
  };

  const psiChartData = useMemo(() => {
    const bins = report?.psi?.bins ?? [];
    return bins.map((b: any) => ({ bin: b.bin, "Train %": b.train_pct, "Test %": b.test_pct }));
  }, [report]);

  const psiFigure = useMemo(() => {
    if (!psiChartData.length) return null;
    return {
      data: [
        {
          type: "bar",
          x: psiChartData.map((row) => row.bin),
          y: psiChartData.map((row) => row["Train %"]),
          name: "Train %",
          marker: { color: CHART_INDIGO, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>Train: %{y:.2f}%<extra></extra>",
        },
        {
          type: "bar",
          x: psiChartData.map((row) => row.bin),
          y: psiChartData.map((row) => row["Test %"]),
          name: "Test %",
          marker: { color: CHART_TEAL, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>Test: %{y:.2f}%<extra></extra>",
        },
      ],
      layout: {
        autosize: true,
        barmode: "group",
        bargap: 0.3,
        bargroupgap: 0.15,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        legend: { orientation: "h", y: -0.3, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 44, r: 16, t: 10, b: 64 },
        xaxis: { tickfont: { size: 9.5 }, automargin: true, tickangle: -30, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "%" }, tickfont: { size: 11 }, automargin: true, gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [psiChartData]);

  const sensitivityChartData = useMemo(() => {
    const rows = report?.sensitivity?.rows ?? [];
    return rows.map((r: any) => ({ feature: r.feature, "AUC drop": r.auc_drop }));
  }, [report]);

  const sensitivityFigure = useMemo(() => {
    if (!sensitivityChartData.length) return null;
    return {
      data: [
        {
          type: "bar",
          x: sensitivityChartData.map((row) => row.feature),
          y: sensitivityChartData.map((row) => row["AUC drop"]),
          name: "AUC drop",
          marker: { color: CHART_INDIGO, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>AUC drop: %{y:.4f}<extra></extra>",
        },
      ],
      layout: {
        autosize: true,
        showlegend: false,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        margin: { l: 44, r: 16, t: 10, b: 64 },
        xaxis: { tickfont: { size: 9.5 }, automargin: true, tickangle: -30, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "AUC drop" }, tickfont: { size: 11 }, automargin: true, gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [sensitivityChartData]);

  const macroChartData = useMemo(() => {
    const scenarios = report?.macro_scenarios?.scenarios ?? [];
    return scenarios.map((s: any) => ({
      name: s.name,
      "Base PD": +(s.base_pd * 100).toFixed(2),
      "Scenario PD": +(s.scn_pd * 100).toFixed(2),
    }));
  }, [report]);

  const macroFigure = useMemo(() => {
    if (!macroChartData.length) return null;
    return {
      data: [
        {
          type: "bar",
          x: macroChartData.map((row) => row.name),
          y: macroChartData.map((row) => row["Base PD"]),
          name: "Base PD",
          marker: { color: CHART_INDIGO, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>Base PD: %{y:.2f}%<extra></extra>",
        },
        {
          type: "bar",
          x: macroChartData.map((row) => row.name),
          y: macroChartData.map((row) => row["Scenario PD"]),
          name: "Scenario PD",
          marker: { color: CHART_AMBER, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>Scenario PD: %{y:.2f}%<extra></extra>",
        },
      ],
      layout: {
        autosize: true,
        barmode: "group",
        bargap: 0.35,
        bargroupgap: 0.15,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        // Explicit tickangle (rather than leaving rotation to automargin's
        // width-dependent guess) plus a fixed, generous bottom margin keeps
        // the legend row from colliding with the scenario-name tick labels
        // at narrow widths — the same category of legend/label overlap
        // already found and fixed on the Benchmarking page's ROC chart.
        legend: { orientation: "h", y: -0.42, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 44, r: 16, t: 10, b: 84 },
        xaxis: { tickfont: { size: 10.5 }, automargin: true, tickangle: -20, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "%" }, tickfont: { size: 11 }, automargin: true, gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [macroChartData]);

  const backtestChartData = useMemo(() => {
    const periods = activeBacktest?.periods ?? [];
    return periods.map((p: any) => ({
      period: p.period,
      "Actual default rate": +(p.actual_dr * 100).toFixed(2),
      "Avg predicted PD": +(p.avg_pred_pd * 100).toFixed(2),
    }));
  }, [activeBacktest]);

  const backtestFigure = useMemo(() => {
    if (!backtestChartData.length) return null;
    return {
      data: [
        {
          type: "scatter",
          mode: "lines+markers",
          x: backtestChartData.map((row) => row.period),
          y: backtestChartData.map((row) => row["Avg predicted PD"]),
          name: "Avg predicted PD",
          line: { color: CHART_INDIGO, width: 2.5 },
          marker: { color: CHART_INDIGO, size: 5 },
          hovertemplate: "<b>%{x}</b><br>Avg predicted PD: %{y:.2f}%<extra></extra>",
        },
        {
          type: "scatter",
          mode: "lines+markers",
          x: backtestChartData.map((row) => row.period),
          y: backtestChartData.map((row) => row["Actual default rate"]),
          name: "Actual default rate",
          line: { color: CHART_AMBER, width: 2.5 },
          marker: { color: CHART_AMBER, size: 5 },
          hovertemplate: "<b>%{x}</b><br>Actual default rate: %{y:.2f}%<extra></extra>",
        },
      ],
      layout: {
        autosize: true,
        hovermode: "x unified",
        hoverlabel: CHART_HOVERLABEL,
        legend: { orientation: "h", y: -0.2, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 44, r: 16, t: 10, b: 44 },
        xaxis: { tickfont: { size: 11 }, automargin: true, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "%" }, tickfont: { size: 11 }, automargin: true, gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [backtestChartData]);

  // report.summary's pass/warn/fail counts were computed server-side using
  // whichever freq was active at run time. Since the freq dropdown now
  // swaps activeBacktest client-side without re-running the suite, the
  // backtest check within the summary is recomputed here too so switching
  // "Backtest period grouping" doesn't leave stale counts/tiles behind.
  const summary = useMemo(() => {
    if (!report?.summary) return report?.summary;
    const otherChecks = (report.summary.checks ?? []).filter((c: any) => c.id !== activeBacktest?.check?.id);
    const checks = activeBacktest?.check ? [...otherChecks, activeBacktest.check] : otherChecks;
    const directionalCount = (status: string) => report.summary[status] - (report.summary.checks ?? []).filter((c: any) => c.status === status.toUpperCase()).length;
    return {
      ...report.summary,
      checks,
      pass: checks.filter((c: any) => c.status === "PASS").length + directionalCount("pass"),
      warn: checks.filter((c: any) => c.status === "WARN").length + directionalCount("warn"),
      fail: checks.filter((c: any) => c.status === "FAIL").length + directionalCount("fail"),
      pending: checks.filter((c: any) => c.status === "PENDING").length,
    };
  }, [report, activeBacktest]);

  // Purely presentational derivations for the hero/status chips below — both
  // read fields the backend already returns (report.available, summary.fail)
  // rather than introducing a new calculation. Gating on `available` (not
  // just "report is truthy") mirrors the same honesty fix already applied to
  // the redesigned Benchmarking page's "Benchmark complete" chip: a response
  // can come back without a usable result, and that must not read as done.
  const suiteComplete = Boolean(report?.available);
  const totalChecks = summary ? deriveCheckTotal(summary) : 0;
  const freqLabel = FREQ_OPTIONS.find((f) => f.key === freq)?.label ?? freq;

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <StageHero
        eyebrow="STAGE 5 · MODEL VALIDATION"
        title="Stress & Backtesting"
        description="Scenario simulations, model stability over time, and back-tested predictions vs realised outcomes."
        chips={
          <>
            <HeroChip tone={suiteComplete ? "success" : "neutral"}>
              {running ? "Running…" : suiteComplete ? "Suite complete" : "Not yet run"}
            </HeroChip>
            {suiteComplete && summary ? (
              <HeroChip tone={summary.fail > 0 ? "warning" : "success"}>
                {summary.fail > 0 ? `${summary.fail} check${summary.fail === 1 ? "" : "s"} failing` : "All checks passing"}
              </HeroChip>
            ) : null}
          </>
        }
      />

      {/* ── Dataset context ──────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm text-slate-600">
        <Database className="h-4 w-4 shrink-0 text-slate-400" />
        {datasetReady ? (
          <span>
            Using the shared dataset from Stage 1 / Stage 2: <span className="font-semibold text-slate-900">{datasetName}</span>
          </span>
        ) : (
          <span>No active dataset is available in shared state yet. Complete Stage 1 Intake and Stage 2 Data Validation first.</span>
        )}
      </div>

      {/* ── Run configuration ────────────────────────────────────────── */}
      <VCard
        icon={Activity}
        title="Run configuration"
        sub="Stress testing retrains the replicated model within this run (same approach as Stage 3 Model Replication — nothing is cached between requests), then applies sensitivity, macro-scenario, stability, backtesting, and directional checks against it."
      >
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Model / Algorithm</div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">{algorithm || "—"}</div>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Target Column</div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">{targetCol || "—"}</div>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Backtest Grouping</div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">{freqLabel}</div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {running ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
                Running stress suite…
              </>
            ) : suiteComplete ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                Stress suite complete.
              </>
            ) : !datasetReady ? (
              "Waiting for an active dataset…"
            ) : (
              "Not yet run."
            )}
          </div>
          <button
            type="button"
            onClick={() => void runStressSuite()}
            disabled={!datasetReady || !targetCol || !algorithm || running}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            {report ? "Re-run Stress Suite" : "Run Stress Suite"}
          </button>
        </div>

        {runError ? (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{runError}</span>
          </div>
        ) : null}
      </VCard>

      {/* ── Validation summary strip ─────────────────────────────────── */}
      {summary ? (
        <div>
          <SectionHeading
            eyebrow="Validation Summary"
            description="Aggregated result of every Stage 5 check — sensitivity, stability, backtesting, and directional tests."
          />
          <div className="mt-3">
            <KpiStrip
              tiles={[
                { icon: ListChecks, label: "Checks", value: totalChecks, tone: "slate" },
                { icon: CheckCircle2, label: "Pass", value: summary.pass ?? 0, tone: "emerald" },
                { icon: AlertTriangle, label: "Warn", value: summary.warn ?? 0, tone: "amber" },
                { icon: XCircle, label: "Fail", value: summary.fail ?? 0, tone: "rose" },
                { icon: MinusCircle, label: "N/A", value: summary.na ?? 0, tone: "slate" },
                { icon: Clock, label: "Pending", value: summary.pending ?? 0, tone: "primary" },
              ]}
            />
          </div>
        </div>
      ) : null}

      {/* ── Two-column analytical dashboard ──────────────────────────────
          A plain 2-col grid (lg:grid-cols-2, i.e. >=1024px) with the four
          sections listed in row-major order below — CSS grid auto-placement
          alone produces exactly Sensitivity|Stability on row 1 and
          Macro|Backtesting on row 2, no explicit grid-column/row needed.
          Below 1024px this collapses to a single column. ──────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* ── Sensitivity analysis ─────────────────────────────────────── */}
      <div>
        <SectionHeading eyebrow="Sensitivity Analysis" />
        <div className="mt-3">
          <VCard icon={TrendingUp} title="Sensitivity — AUC drop on feature removal" sub="From Stage 3 ablation. SS1/23 P4.3.">
            {sensitivityFigure ? (
              <div className="h-[260px] overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                <PlotlyChart figure={sensitivityFigure} style={{ height: "100%" }} config={NO_TOOLBAR_CONFIG} />
              </div>
            ) : (
              <VEmptyState icon={TrendingUp} title="No sensitivity results yet" description="Run the stress suite to see ablation results." />
            )}
            {report?.sensitivity?.check ? <div className="mt-4"><CheckCard check={report.sensitivity.check} /></div> : null}

            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-blue-600" />
                <h4 className="text-sm font-semibold text-slate-900">Manual Feature Shock</h4>
              </div>
              <p className="mt-1 text-xs text-slate-500">Apply a one-off ±% shock to a single feature and see the resulting shift in average predicted PD.</p>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Feature</label>
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm"
                    value={shockFeature}
                    onChange={(e) => setShockFeature(e.target.value)}
                  >
                    {(report?.numeric_features ?? []).map((f: string) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Direction</label>
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm"
                    value={shockDirection}
                    onChange={(e) => setShockDirection(e.target.value as "increase" | "decrease")}
                  >
                    <option value="increase">Increase (+)</option>
                    <option value="decrease">Decrease (-)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Change %</label>
                  <input
                    type="number"
                    min={5}
                    max={100}
                    step={5}
                    value={shockMagnitude}
                    onChange={(e) => setShockMagnitude(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm"
                  />
                </div>
              </div>

              <button
                type="button"
                disabled={!shockFeature || shockRunning}
                onClick={() => void applyShock()}
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Zap className="h-4 w-4" />
                {shockRunning ? "Applying…" : "Apply Shock"}
              </button>
              {shockError ? <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{shockError}</div> : null}

              {shockResult ? (
                <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                  <div className="text-xs text-slate-500">
                    <span className="font-semibold text-slate-900">{shockResult.feature}</span> shocked {shockResult.direction} {shockResult.magnitude_pct}%
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-3 text-center">
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-400">Base avg PD</div>
                      <div className="mt-0.5 text-base font-bold tabular-nums text-slate-900">{shockResult.base_pd.toFixed(4)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-400">Shocked avg PD</div>
                      <div className="mt-0.5 text-base font-bold tabular-nums text-slate-900">{shockResult.shock_pd.toFixed(4)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-400">Change</div>
                      <div className={"mt-0.5 text-base font-bold tabular-nums " + (shockResult.pd_change >= 0 ? "text-rose-600" : "text-emerald-600")}>
                        {shockResult.pd_change >= 0 ? "+" : ""}{shockResult.pd_change.toFixed(4)} ({shockResult.pd_change_pct.toFixed(1)}%)
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </VCard>
        </div>
      </div>

      {/* ── Score stability (PSI) ────────────────────────────────────── */}
      <div>
        <SectionHeading eyebrow="Score Stability" />
        <div className="mt-3">
          <VCard
            icon={Gauge}
            title="Score stability (PSI) — train vs test"
            sub="SS11/13 §10.6. PSI < 0.10 stable, 0.10–0.25 minor shift, > 0.25 major shift."
          >
            {psiFigure ? (
              <div className="h-[260px] overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                <PlotlyChart figure={psiFigure} style={{ height: "100%" }} config={NO_TOOLBAR_CONFIG} />
              </div>
            ) : (
              <VEmptyState icon={Gauge} title="No stability data yet" description="Run the stress suite to see the score distribution." />
            )}
            {report?.psi?.check ? <div className="mt-4"><CheckCard check={report.psi.check} /></div> : null}
          </VCard>
        </div>
      </div>

      {/* ── Macro stress scenarios ───────────────────────────────────── */}
      <div>
        <SectionHeading eyebrow="Macro Stress Scenarios" />
        <div className="mt-3">
          <VCard
            icon={LineChart}
            title="Macro stress scenarios — average predicted PD"
            sub={
              <>
                SS3/18 §2.1.{" "}
                {report?.macro_scenarios?.detected_drivers
                  ? Object.entries(report.macro_scenarios.detected_drivers).map(([k, v]) => `${k} → ${v}`).join(", ")
                  : ""}
              </>
            }
          >
            {macroFigure ? (
              <div className="h-[260px] overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                <PlotlyChart figure={macroFigure} style={{ height: "100%" }} config={NO_TOOLBAR_CONFIG} />
              </div>
            ) : (
              <VEmptyState icon={LineChart} title="No scenario results yet" description="Run the stress suite to see macro-scenario results." />
            )}
            {report?.macro_scenarios?.scenarios?.length ? (
              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                {report.macro_scenarios.scenarios.map((s: any) => (
                  <div key={s.id} className="rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-sm">
                    <div className="font-semibold text-slate-900">{s.name}</div>
                    <div className="mt-1 text-slate-500">{s.desc}</div>
                    <div className="mt-2 text-slate-500">
                      Base <b className="text-slate-900">{s.base_pd.toFixed(4)}</b> → Scenario <b className="text-slate-900">{s.scn_pd.toFixed(4)}</b>{" "}
                      <span className={s.pd_change_pct >= 0 ? "font-semibold text-amber-600" : "font-semibold text-emerald-600"}>
                        ({s.pd_change_pct >= 0 ? "+" : ""}{s.pd_change_pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] text-slate-400">
                      {s.applied?.length ? `Applied: ${s.applied.join("; ")}` : "No matching driver columns found"}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </VCard>
        </div>
      </div>

      {/* ── Backtesting ───────────────────────────────────────────────── */}
      <div>
        <SectionHeading eyebrow="Backtesting" />
        <div className="mt-3">
          <VCard
            icon={Compass}
            title="Backtesting — predicted vs actual default rate"
            sub={
              activeBacktest?.available
                ? `Grouped by ${activeBacktest.freq} · date column: ${activeBacktest.date_col}`
                : activeBacktest?.reason ?? "Run the stress suite to see backtesting results."
            }
            actions={
              <div>
                <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Grouping</label>
                <select
                  className="mt-1 rounded-lg border border-slate-200 bg-white p-1.5 text-xs"
                  value={freq}
                  onChange={(e) => setFreq(e.target.value)}
                >
                  {FREQ_OPTIONS.map((f) => (
                    <option key={f.key} value={f.key}>{f.label}</option>
                  ))}
                </select>
              </div>
            }
          >
            {backtestFigure ? (
              <div className="h-[280px] overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                <PlotlyChart figure={backtestFigure} style={{ height: "100%" }} config={NO_TOOLBAR_CONFIG} />
              </div>
            ) : (
              <VEmptyState icon={Compass} title="No backtesting data yet" description="Run the stress suite to see predicted vs actual default rate over time." />
            )}
            {activeBacktest?.check ? <div className="mt-4"><CheckCard check={activeBacktest.check} /></div> : null}
          </VCard>
        </div>
      </div>
      </div>

      {/* ── Directional testing ───────────────────────────────────────── */}
      <div>
        <SectionHeading eyebrow="Directional Testing" />
        <div className="mt-3">
          <VCard
            icon={Zap}
            title="Directional testing — economic intuition check"
            sub="SS1/23 P4.3 · SS3/18 §2.1. Each driver is shocked ±10% in the adverse direction; average predicted PD should move as basic credit-risk intuition expects."
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {(report?.directional ?? []).map((r: any) => {
                if (r.status === "SKIP") {
                  return (
                    <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-sm">
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold text-slate-900">[{r.id}] {r.driver} → {r.expected}</div>
                        <StatusPill tone="pending">Skipped</StatusPill>
                      </div>
                      <div className="mt-1 text-slate-500">{r.note}</div>
                    </div>
                  );
                }
                const tone = statusTone(r.status);
                return (
                  <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold text-slate-900">[{r.id}] {r.driver} → {r.expected}</div>
                      <StatusPill tone={tone}>{r.status}</StatusPill>
                    </div>
                    {r.status === "ERROR" ? (
                      <div className="mt-1 text-slate-500">{r.error}</div>
                    ) : (
                      <div className="mt-1 text-slate-500">
                        {r.column} shocked {r.shock_desc}: avg PD {r.base_pd.toFixed(4)} → {r.new_pd.toFixed(4)} ({r.delta >= 0 ? "+" : ""}{r.delta.toFixed(4)})
                      </div>
                    )}
                  </div>
                );
              })}
              {!report?.directional?.length ? (
                <div className="text-xs text-slate-500">Run the stress suite to see directional test results.</div>
              ) : null}
            </div>
          </VCard>
        </div>
      </div>

      {/* ── Navigation — a normal end-of-page action, not floating over
          content. ────────────────────────────────────────────────────── */}
      <div className="flex justify-end pb-2">
        <Link
          to="/validation/regulatory"
          className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
        >
          Continue to Stage 6
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
