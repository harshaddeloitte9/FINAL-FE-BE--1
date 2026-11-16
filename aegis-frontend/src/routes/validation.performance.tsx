import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, AlertCircle, Loader2, PlayCircle, Upload, BarChart3, Database, GitCompareArrows } from "lucide-react";
import { useDataset } from "@/lib/app-context";
import { describeCurveProvenance, type CurveProvenance } from "@/lib/check-provenance";
import PlotlyChart from "@/components/plotly-chart";
import { ApiError, formUpload } from "@/lib/api";
import { useEvaluationKey, useEvaluationState } from "@/hooks/use-evaluation";
import { EvidenceIdentity } from "@/components/evidence-identity";
import { StageHero, HeroChip, VCard, VEmptyState, KpiStrip, StatusPill } from "@/components/validation-ui";

export const Route = createFileRoute("/validation/performance")({
  head: () => ({ meta: [{ title: "Benchmarking — Aegis Credit" }] }),
  component: Performance,
});

// Stage 4 — Benchmarking only. The full performance report (metrics, ROC/PR
// curves, confusion matrix, calibration, score distribution) that used to
// live on this page moved to Stage 3 (/validation/challenger, "Model
// Replication & Performance Testing"), since replication and performance
// testing fit the model the same way under the hood and showing them
// together avoids re-running that fit twice. This page keeps just the
// champion-vs-industry-benchmark comparison.
// Developer-reported reference values, kept apart from computed metrics.
// `sources` says where each value came from (mdd_upload, intake_mdd,
// demo_intake, development_training_run, manual_entry, client_supplied).
export type ReferenceMetrics = {
  values: Record<string, number>;
  sources: Record<string, string>;
  source_labels?: Record<string, string>;
  warnings?: string[];
};

type PerformanceResponse = {
  stage: string;
  report: {
    // Champion metrics computed from the fitted model's predictions. Never
    // replaced by MDD values (they live in `reference_metrics`).
    metrics: Record<string, any>;
    reference_metrics?: ReferenceMetrics;
    // Absent on runs saved before provenance was recorded — those runs may
    // show developer-reported values as champion metrics.
    metric_provenance?: { schema_version: number; metrics: string; reference_metrics: string };
    roc_curve: { points: Array<Record<string, number>>; auc?: number | null; provenance?: CurveProvenance };
    benchmark?: Record<string, any>;
  };
};

// Mirrors model_selector.py's CLASSIFICATION_MODELS registry keys (also
// available from the backend at GET /models/list) — the same candidate set
// offered during the model development pipeline's Model Selection step.
const CHALLENGER_CANDIDATES = [
  "Logistic Regression",
  "Random Forest",
  "XGBoost",
  "LightGBM",
  "Gradient Boosting",
];

type ChallengerComparisonRow = {
  model_name: string;
  roc_auc?: number;
  gini?: number;
  ks?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  training_time_s?: number;
  error?: string;
};

type CompareModelsResponse = {
  task_type: string;
  comparison: ChallengerComparisonRow[];
};

function formatValue(value: unknown, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return num.toFixed(digits);
}

// Same fallback the comparison table already used: prefer the real `gini`
// field the backend returns, and only ever derive it from roc_auc (the
// standard Gini = 2*AUC-1 identity) when the backend didn't send one —
// never a different/new calculation, just reused in the one extra place
// (the selected-challenger metric strip) that now also needs it.
function resolveGini(row: { gini?: number; roc_auc?: number } | null | undefined): number | undefined {
  if (!row) return undefined;
  if (typeof row.gini === "number") return row.gini;
  return typeof row.roc_auc === "number" ? 2 * row.roc_auc - 1 : undefined;
}

// Aegis palette for this page's two charts — plain hex, not oklch(): Plotly's
// bundled color parser can't read CSS Color 4 oklch()/lab() syntax and
// silently falls back to black for anything it can't parse, which is why
// the previous version of these charts rendered with default/black styling
// despite already specifying colors. Champion = indigo (the same accent
// used elsewhere in Aegis), Challenger/Benchmark = teal, kept deliberately
// distinct from the semantic pass/fail palette since this is a side-by-side
// comparison, not a status.
const CHART_CHAMPION = "#4f46e5";
const CHART_CHAMPION_SOFT = "rgba(79,70,229,0.10)";
const CHART_CHALLENGER = "#0891b2";
const CHART_GRID = "#eef2ff";
const CHART_HOVERLABEL = { bgcolor: "#ffffff", bordercolor: "#c7d2fe", font: { size: 12, color: "#334155" } };

function Performance() {
  const ds = useDataset();
  const [targetCol, setTargetCol] = React.useState(
    () => ds.profile?.target_col || ds.trainingResult?.evaluation_data?.target_col || "default",
  );
  const [modelName, setModelName] = React.useState(
    () => ds.selectedModel?.name || ds.trainingResult?.model_name || "Logistic Regression",
  );
  const [challengerModelName, setChallengerModelName] = React.useState("Logistic Regression");
  const [selectedCandidates, setSelectedCandidates] = React.useState<string[]>([...CHALLENGER_CANDIDATES]);
  const [comparisonRows, setComparisonRows] = React.useState<ChallengerComparisonRow[] | null>(null);
  const [comparing, setComparing] = React.useState(false);
  const [comparisonError, setComparisonError] = React.useState<string | null>(null);
  // Input-validation messages; request failures live in the evaluation state.
  const [inputError, setError] = React.useState<string | null>(null);
  // Whether the reviewer has actually run "Compare Challengers" and clicked
  // "Select" on a row this session. The champion-vs-challenger benchmark
  // must not run against a guessed/default challenger — it can only run
  // once a challenger has been deliberately picked from real comparison
  // numbers.
  const [challengerPicked, setChallengerPicked] = React.useState(false);
  // Developer-reported metrics parsed from the MDD at Stage 1 (Intake &
  // Governance). These are REFERENCE values only: they are sent so the
  // backend can return them alongside the champion's computed metrics, never
  // in place of them. Null entries (metrics the MDD doesn't mention) are
  // dropped. Demo intakes are labelled as such so they are never presented
  // as a real submission's evidence.
  const mddMetricsFromIntake = React.useMemo(() => {
    const raw = (ds.validationMddMetrics ?? {}) as Record<string, any>;
    return Object.fromEntries(Object.entries(raw).filter(([, v]) => v !== null && v !== undefined && v !== ""));
  }, [ds.validationMddMetrics]);
  const hasMddMetrics = Object.keys(mddMetricsFromIntake).length > 0;
  const mddReferenceSource = ds.profile?.demo_mode ? "demo_intake" : "intake_mdd";
  // Fallback only: lets a reviewer parse an MDD directly from this page if
  // Stage 1 was skipped or didn't have one yet. Writes back into the same
  // shared context (mirrors Stage 1's own upload handler) so it becomes the
  // one shared source of truth for every stage, not a page-local copy.
  const [mddParseError, setMddParseError] = React.useState<string | null>(null);
  const [mddParsing, setMddParsing] = React.useState(false);
  // Seed from shared context so returning to this page (e.g. via Back from
  // Stage 5) shows the already-computed result instead of resetting to the
  // bare input form — but ONLY if that cached result reflects a benchmark
  // that was actually run against a deliberately-picked challenger, not
  // just whatever happened to be sitting in shared state (e.g. left over
  // from an earlier dataset or an earlier visit). Previously this seeded
  // unconditionally, which is why the champion-vs-challenger comparison
  // could appear pre-loaded the moment the tab opened, before Compare
  // Challengers had ever been run.
  // A browser-cached benchmark is reused only for the exact evaluation
  // identity it was produced for (registered model, training run, dataset
  // bytes, champion/challenger/target) — see benchKey below. Results from the
  // backend history are not restored: they cannot be tied to the dataset
  // currently loaded.
  const cachedResult = ds.validationStage5Result as (PerformanceResponse & { evaluation_key?: string | null }) | null;
  const currentRegisteredModelId =
    ((ds.validationIntakeData as Record<string, any> | null | undefined)?.registered_model_id as string | undefined) || null;

  const datasetName = ds.file?.name ?? ds.profile?.dataset_name ?? "uploaded dataset";
  const datasetReady = Boolean(ds.file || ds.profile?.csv_text || ds.profile?.dataset_name);

  // By the time a reviewer reaches Stage 4, the working dataset often only
  // exists as profile.csv_text (not a literal File object) — carried forward
  // through preprocessing/FE/macro-fetch as text, same as Stage 3's activeFile
  // pattern. Without this reconstruction, the auto-run below silently no-ops
  // whenever ds.file is null, leaving the page stuck with no data.
  const datasetFile = React.useMemo<File | null>(() => {
    if (ds.file) return ds.file;
    const csvText = typeof ds.profile?.csv_text === "string" ? ds.profile.csv_text : "";
    if (!csvText.trim()) return null;
    const resolvedName = ds.profile?.dataset_name ?? "validation_dataset.csv";
    const safeName = resolvedName.endsWith(".csv") || resolvedName.endsWith(".xlsx")
      ? resolvedName
      : `${resolvedName}.csv`;
    return new File([csvText], safeName, { type: "text/csv" });
  }, [ds.file, ds.profile?.csv_text, ds.profile?.dataset_name]);

  const benchKey = useEvaluationKey(datasetFile, currentRegisteredModelId, `${modelName}|${challengerModelName}|${targetCol}`);
  const bench = useEvaluationState<PerformanceResponse>(
    benchKey,
    cachedResult?.report?.benchmark?.status === "OK" ? cachedResult : null,
  );
  const payload = bench.state.result;
  const loading = bench.state.status === "loading";
  const error = inputError ?? bench.state.error;
  // A restored cached benchmark was run against a deliberately-picked challenger.
  React.useEffect(() => {
    if (payload && !challengerPicked) setChallengerPicked(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload]);

  const handleRun = React.useCallback(async (fileOverride?: File | null) => {
    const fileToUse = fileOverride ?? datasetFile;
    if (!fileToUse) {
      setError("Upload a dataset or use the file from Intake before running Stage 4.");
      return;
    }
    if (!targetCol.trim()) {
      setError("Target column is required.");
      return;
    }
    if (!modelName.trim()) {
      setError("Model name is required.");
      return;
    }
    if (!benchKey) return;
    setError(null);
    const token = bench.begin();                     // clears the previous result now
    const keyAtStart = benchKey;
    try {
      const form = new FormData();
      form.append("file", fileToUse);
      form.append("model_name", modelName.trim());
      form.append("target_col", targetCol.trim());
      form.append("challenger_model_name", challengerModelName.trim());
      // Recorded with the run so the final verdict can confirm this benchmark
      // belongs to the registered model under validation.
      const registeredModelId = (ds.validationIntakeData as Record<string, any> | null | undefined)?.registered_model_id;
      if (typeof registeredModelId === "string" && registeredModelId) form.append("registered_model_id", registeredModelId);
      // Optional reference values only — champion metrics are always
      // computed by the backend from the fitted model's predictions.
      if (hasMddMetrics) {
        form.append("reported_json", JSON.stringify(mddMetricsFromIntake));
        form.append(
          "reported_sources_json",
          JSON.stringify(Object.fromEntries(Object.keys(mddMetricsFromIntake).map((k) => [k, mddReferenceSource]))),
        );
      }
      const res = await formUpload<PerformanceResponse>("/validation/performance", form);
      if (!bench.isCurrent(token)) return;           // superseded by a newer request or identity
      bench.succeed(token, res);
      ds.setValidationStage5Result({ ...(res as unknown as Record<string, any>), evaluation_key: keyAtStart });
    } catch (err) {
      if (err instanceof ApiError) {
        const detail =
          err.body && typeof err.body === "object" && "detail" in (err.body as any)
            ? String((err.body as any).detail)
            : err.message;
        bench.fail(token, detail);
      } else {
        bench.fail(token, err instanceof Error ? err.message : "Benchmark analysis failed.");
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetFile, targetCol, modelName, challengerModelName, hasMddMetrics, mddMetricsFromIntake, mddReferenceSource, benchKey, bench]);

  // NOTE: Stage 4 deliberately does NOT auto-run on mount. Unlike Stage 2,
  // this page's main result is a champion-vs-challenger comparison, and a
  // challenger must be deliberately picked (via Compare Challengers ->
  // Select) before there's anything meaningful to benchmark against. An
  // earlier version auto-ran this against a hardcoded default challenger
  // ("Logistic Regression") the instant a dataset was ready, which is why
  // the comparison could appear already populated before the reviewer had
  // run Compare Challengers or picked a model — see handleRun's disabled
  // state below, which now requires challengerPicked.

  const toggleCandidate = React.useCallback((name: string) => {
    setSelectedCandidates((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  }, []);

  // Reuses /models/compare — the exact same lightweight, no-CV/no-hyperopt
  // comparison the model development pipeline's Model Selection step uses
  // — so picking a challenger here is grounded in the same fast read on
  // "which model is worth committing to" rather than a separate mechanism.
  const runComparison = React.useCallback(async () => {
    if (!datasetFile) {
      setComparisonError("Upload a dataset or use the file from Intake before comparing challengers.");
      return;
    }
    if (!targetCol.trim()) {
      setComparisonError("Target column is required.");
      return;
    }
    if (selectedCandidates.length === 0) {
      setComparisonError("Select at least one challenger candidate to compare.");
      return;
    }

    setComparing(true);
    setComparisonError(null);
    try {
      const form = new FormData();
      form.append("file", datasetFile);
      form.append("target_col", targetCol.trim());
      form.append("model_names", JSON.stringify(selectedCandidates));
      const res = await formUpload<CompareModelsResponse>("/models/compare", form);
      setComparisonRows(res.comparison ?? []);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail =
          err.body && typeof err.body === "object" && "detail" in (err.body as any)
            ? String((err.body as any).detail)
            : err.message;
        setComparisonError(detail);
      } else {
        setComparisonError(err instanceof Error ? err.message : "Challenger comparison failed.");
      }
    } finally {
      setComparing(false);
    }
  }, [datasetFile, targetCol, selectedCandidates]);

  const rocPoints = payload?.report?.roc_curve?.points ?? [];
  const benchmarkResponse = payload?.report?.benchmark;
  const benchmarkComparison = benchmarkResponse?.comparison?.champion_vs_challenger;
  // "Complete" is only ever shown when the actual benchmark response says so
  // — payload being non-null on its own isn't enough (a response could in
  // principle come back without a usable benchmark), matching the same
  // status/model_name check already used to decide whether a cached/resumed
  // result is usable above.
  const benchmarkComplete = Boolean(payload && benchmarkResponse?.model_name && benchmarkResponse?.status === "OK");

  const selectedComparisonRow = React.useMemo(
    () => comparisonRows?.find((row) => row.model_name === challengerModelName) ?? null,
    [comparisonRows, challengerModelName],
  );

  // Champion and challenger rows are both computed from model predictions.
  // The developer-reported reference row (if any) is shown separately and
  // labelled with its source — it is never substituted into the champion row.
  const referenceMetrics = payload?.report?.reference_metrics;
  const hasProvenance = Boolean(payload?.report?.metric_provenance);
  const benchmarkTableRows = React.useMemo(() => {
    const championMetrics = payload?.report?.metrics ?? {};
    const challengerMetrics = benchmarkResponse?.metrics ?? {};
    const rows: Array<{ model: string; kind: "champion" | "challenger" | "reference"; roc_auc?: number; gini?: number; recall?: number; source?: string }> = [
      { model: "Champion", kind: "champion", roc_auc: championMetrics.roc_auc, gini: championMetrics.gini, recall: championMetrics.recall },
      { model: benchmarkResponse?.model_name ?? "Benchmark", kind: "challenger", roc_auc: challengerMetrics.roc_auc, gini: challengerMetrics.gini, recall: challengerMetrics.recall },
    ];
    const refValues = referenceMetrics?.values ?? {};
    if (Object.keys(refValues).length > 0) {
      const labels = referenceMetrics?.source_labels ?? {};
      const sourceText = Array.from(new Set(["roc_auc", "gini", "recall"].map((k) => labels[k]).filter(Boolean))).join(", ");
      rows.push({
        model: "Developer-reported",
        kind: "reference",
        roc_auc: refValues.roc_auc,
        gini: refValues.gini,
        recall: refValues.recall,
        source: sourceText || undefined,
      });
    }
    return rows;
  }, [payload, benchmarkResponse, referenceMetrics]);

  // Both ROC curves are measured: the champion's from report.roc_curve and
  // the challenger's from benchmark.roc_curve, each computed by the backend
  // from that model's predicted probabilities on the same test rows. (This
  // used to draw the challenger as tpr = fpr × AUC — a formula, not data.)
  // Results saved before the challenger curve was recorded have no
  // challenger series rather than a synthesised one.
  const challengerRocPoints: Array<Record<string, number>> = benchmarkResponse?.roc_curve?.points ?? [];

  const comparisonChartData = React.useMemo(() => {
    if (!benchmarkComparison) return [];
    return [
      { metric: "ROC-AUC", champion: benchmarkComparison.roc_auc?.champion, challenger: benchmarkComparison.roc_auc?.challenger },
      { metric: "Gini", champion: benchmarkComparison.gini?.champion, challenger: benchmarkComparison.gini?.challenger },
      { metric: "Recall", champion: benchmarkComparison.recall?.champion, challenger: benchmarkComparison.recall?.challenger },
    ];
  }, [benchmarkComparison]);

  const benchmarkComparisonFigure = React.useMemo(() => {
    const metrics = comparisonChartData.map((row) => row.metric);
    const champion = comparisonChartData.map((row) => row.champion);
    const challenger = comparisonChartData.map((row) => row.challenger);
    return {
      data: [
        {
          type: "bar",
          x: metrics,
          y: champion,
          name: "Champion",
          marker: { color: CHART_CHAMPION, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>Champion: %{y:.3f}<extra></extra>",
        },
        {
          type: "bar",
          x: metrics,
          y: challenger,
          name: benchmarkResponse?.model_name ?? "Challenger",
          marker: { color: CHART_CHALLENGER, cornerradius: 3 },
          hovertemplate: "<b>%{x}</b><br>Challenger: %{y:.3f}<extra></extra>",
        },
      ],
      layout: {
        autosize: true,
        barmode: "group",
        bargap: 0.3,
        bargroupgap: 0.15,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        legend: { orientation: "h", y: -0.18, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 40, r: 16, t: 10, b: 40 },
        xaxis: { tickfont: { size: 11.5 }, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "Value" }, tickfont: { size: 11 }, gridcolor: CHART_GRID, zeroline: false, showline: false, range: [0, 1] },
      },
    };
  }, [comparisonChartData, benchmarkResponse]);

  const benchmarkOverlayFigure = React.useMemo(() => {
    const series: any[] = [
      {
        type: "scatter",
        mode: "lines",
        x: (rocPoints ?? []).map((point) => point.fpr),
        y: (rocPoints ?? []).map((point) => point.tpr),
        line: { color: CHART_CHAMPION, width: 2.5 },
        fill: "tozeroy",
        fillcolor: CHART_CHAMPION_SOFT,
        hovertemplate: "<b>Champion</b><br>TPR %{y:.3f}<br>FPR %{x:.3f}<extra></extra>",
        name: "Champion",
      },
    ];
    if (challengerRocPoints.length) {
      series.push({
        type: "scatter",
        mode: "lines",
        x: challengerRocPoints.map((point) => point.fpr),
        y: challengerRocPoints.map((point) => point.tpr),
        line: { color: CHART_CHALLENGER, width: 2.5, dash: "dash" },
        hovertemplate: `<b>${benchmarkResponse?.model_name ?? "Challenger"}</b><br>TPR %{y:.3f}<br>FPR %{x:.3f}<extra></extra>`,
        name: benchmarkResponse?.model_name ?? "Challenger",
      });
    }
    return {
      data: series,
      layout: {
        autosize: true,
        showlegend: true,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        legend: { orientation: "h", y: -0.32, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 40, r: 16, t: 10, b: 64 },
        xaxis: { title: { text: "False Positive Rate" }, tickfont: { size: 11 }, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "True Positive Rate" }, tickfont: { size: 11 }, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [rocPoints, challengerRocPoints, benchmarkResponse]);

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <StageHero
        eyebrow="STAGE 4 · MODEL VALIDATION"
        title="Benchmarking"
        description="Compare the champion model against an industry-standard challenger before stress testing and regulatory review."
        chips={
          <>
            <HeroChip tone={challengerPicked ? "success" : "neutral"}>
              {challengerPicked ? `Challenger: ${challengerModelName}` : "No challenger selected"}
            </HeroChip>
            <HeroChip tone={benchmarkComplete ? "success" : "neutral"}>
              {benchmarkComplete ? "Benchmark complete" : "Live comparison"}
            </HeroChip>
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

      {loading ? (
        <section className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500 shadow-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          Running Stage 4 benchmarking analysis on the shared dataset…
        </section>
      ) : null}

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {!payload && !loading ? (
        <VEmptyState
          icon={BarChart3}
          title={datasetReady ? "Benchmark not yet run" : "Waiting on a dataset"}
          description={
            datasetReady
              ? "Run Compare Challengers below, select a challenger model, then Run Benchmark to see the champion-vs-challenger comparison."
              : "Waiting on a dataset from Stage 1/Stage 2 to run the Stage 4 benchmark report."
          }
        />
      ) : null}

      {datasetReady ? (
        <div className="space-y-6">
          {/* ── Challenger comparison workspace ─────────────────────── */}
          <VCard
            icon={GitCompareArrows}
            title="Compare Challenger Models"
            sub="Reuses the same lightweight, no-CV comparison from the model development pipeline's Model Selection step — fit → predict → summary metrics per model — so you can see which challenger is worth benchmarking against before committing to one."
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap gap-2">
                {CHALLENGER_CANDIDATES.map((name) => (
                  <label
                    key={name}
                    className={
                      "inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors " +
                      (selectedCandidates.includes(name)
                        ? "border-blue-300 bg-blue-50 text-blue-700"
                        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300")
                    }
                  >
                    <input
                      type="checkbox"
                      className="hidden"
                      checked={selectedCandidates.includes(name)}
                      onChange={() => toggleCandidate(name)}
                    />
                    {name}
                  </label>
                ))}
              </div>
              <button
                type="button"
                onClick={() => void runComparison()}
                disabled={comparing || !datasetFile || selectedCandidates.length === 0}
                className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {comparing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                Compare Challengers
              </button>
            </div>

            {comparisonError ? (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{comparisonError}</span>
              </div>
            ) : null}

            {/* Selected challenger — headline identity + a scannable metric
                strip, before the full comparison table below. Every value
                here is read straight from the same comparisonRows the table
                renders; nothing is recalculated. */}
            <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Selected Challenger</div>
                  <div className="mt-0.5 text-base font-semibold text-slate-900">{challengerModelName}</div>
                </div>
                <StatusPill tone={challengerPicked ? "pass" : "pending"}>
                  {challengerPicked ? "Picked for benchmarking" : "Not yet picked"}
                </StatusPill>
              </div>

              {selectedComparisonRow && !selectedComparisonRow.error ? (
                <div className="mt-4">
                  <KpiStrip
                    tiles={[
                      { icon: BarChart3, label: "ROC-AUC", value: formatValue(selectedComparisonRow.roc_auc, 3), tone: "primary" },
                      { icon: BarChart3, label: "Gini", value: formatValue(resolveGini(selectedComparisonRow), 3), tone: "violet" },
                      { icon: BarChart3, label: "KS", value: formatValue(selectedComparisonRow.ks, 3), tone: "primary" },
                      { icon: BarChart3, label: "Recall", value: formatValue(selectedComparisonRow.recall, 3), tone: "emerald" },
                      { icon: BarChart3, label: "Fit Time", value: `${formatValue(selectedComparisonRow.training_time_s, 2)}s`, tone: "slate" },
                    ]}
                  />
                </div>
              ) : (
                <p className="mt-3 text-xs text-slate-500">
                  {comparisonRows ? "Run Compare Challengers to see this model's metrics, or pick a model from the comparison table below." : "Run Compare Challengers to populate real metrics for this model."}
                </p>
              )}
            </div>

            {comparisonRows && comparisonRows.length > 0 ? (
              <div className="mt-5 overflow-hidden rounded-xl border border-slate-200">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                        <th className="px-4 py-2.5 text-left">Model</th>
                        <th className="px-3 py-2.5 text-right">ROC-AUC</th>
                        <th className="px-3 py-2.5 text-right">Gini</th>
                        <th className="px-3 py-2.5 text-right">Recall</th>
                        <th className="px-3 py-2.5 text-right">KS</th>
                        <th className="px-3 py-2.5 text-right">Fit time (s)</th>
                        <th className="px-4 py-2.5 text-left">Challenger</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {comparisonRows.map((row) => {
                        const isSelected = row.model_name === challengerModelName;
                        const gini = resolveGini(row);
                        return (
                          <tr key={row.model_name} className={isSelected ? "bg-blue-50/60" : "hover:bg-slate-50/60"}>
                            <td className="px-4 py-2.5 font-medium text-slate-900">{row.model_name}</td>
                            {row.error ? (
                              <td colSpan={5} className="px-3 py-2.5 text-xs text-red-600">{row.error}</td>
                            ) : (
                              <>
                                <td className="px-3 py-2.5 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.roc_auc, 3)}</td>
                                <td className="px-3 py-2.5 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(gini, 3)}</td>
                                <td className="px-3 py-2.5 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.recall, 3)}</td>
                                <td className="px-3 py-2.5 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.ks, 3)}</td>
                                <td className="px-3 py-2.5 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.training_time_s, 2)}</td>
                              </>
                            )}
                            <td className="px-4 py-2.5">
                              <button
                                type="button"
                                onClick={() => {
                                  setChallengerModelName(row.model_name);
                                  setChallengerPicked(true);
                                  // A newly-picked challenger changes the
                                  // evaluation identity (benchKey), which
                                  // clears any earlier benchmark result.
                                }}
                                disabled={Boolean(row.error)}
                                className={
                                  "rounded-lg border px-3 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 " +
                                  (isSelected
                                    ? "border-blue-600 bg-blue-600 text-white"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-blue-300")
                                }
                              >
                                {isSelected ? "Selected" : "Select"}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </VCard>

          {/* ── Run benchmark action ─────────────────────────────────── */}
          <VCard icon={BarChart3} title="Champion vs Challenger" sub={challengerPicked ? `Benchmarks the champion model against ${challengerModelName} — pick a different row above and re-run to compare against another challenger.` : "Run Compare Challengers above and select a row before running the benchmark."}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                {hasMddMetrics ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2.5 text-xs text-slate-500">
                    <span className="font-semibold text-slate-900">
                      Developer-reported reference ({mddReferenceSource === "demo_intake" ? "demo intake" : "MDD from Stage 1"})
                    </span>
                    {" "}— shown for comparison only. Champion metrics are computed from the model&apos;s predictions:{" "}
                    {Object.entries(mddMetricsFromIntake)
                      .map(([k, v]) => `${k.replace(/_/g, " ")}=${v}`)
                      .join(", ")}
                  </div>
                ) : (
                  <div className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2.5 text-xs text-slate-600">
                    No developer-reported metrics from Stage 1 (Intake &amp; Governance). The benchmark can still run;
                    a reference row will only appear if an MDD is provided. Optionally parse one here:
                    <label className="mt-2 flex cursor-pointer items-center gap-2 text-slate-900 hover:underline">
                      <Upload className="h-3.5 w-3.5" />
                      <span>{mddParsing ? "Parsing…" : "Upload & Parse MDD"}</span>
                      <input
                        type="file"
                        accept=".pdf,.docx,.txt"
                        className="hidden"
                        disabled={mddParsing}
                        onChange={async (e) => {
                          const f = e.target.files?.[0] ?? null;
                          if (!f) return;
                          setMddParseError(null);
                          setMddParsing(true);
                          try {
                            const form = new FormData();
                            form.append("mdd_file", f);
                            const resp = await formUpload<Record<string, any>>("/validation/parse-mdd", form);
                            // Write back to the same shared context Stage 1
                            // uses, so this becomes the one source of truth
                            // for every stage rather than a page-local copy.
                            ds.setValidationMddText(resp?.mdd_text ?? null);
                            ds.setValidationMddMetrics(resp?.metrics ?? null);
                          } catch (err) {
                            setMddParseError(err instanceof Error ? err.message : "Failed to parse MDD file.");
                          } finally {
                            setMddParsing(false);
                          }
                        }}
                      />
                    </label>
                    {mddParseError ? <div className="mt-1 text-red-700">{mddParseError}</div> : null}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleRun()}
                disabled={loading || !datasetFile || !challengerPicked}
                className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                Run Benchmark
              </button>
            </div>
          </VCard>

          {payload ? (
            <>
              {/* Champion = the evaluation identity below; the challenger is
                  always a separately identified independent refit. */}
              <EvidenceIdentity
                title="Champion evidence identity"
                evidence={(payload as any).evidence}
                extra={[
                  {
                    label: "Challenger",
                    value: (payload as any).evidence?.challenger?.algorithm
                      ? `${(payload as any).evidence.challenger.algorithm} — independent refit`
                      : null,
                  },
                  {
                    label: "Same test rows as champion",
                    value:
                      typeof payload?.report?.benchmark?.evaluation?.same_test_rows_as_champion === "boolean"
                        ? (payload.report.benchmark.evaluation.same_test_rows_as_champion ? "Yes" : "No")
                        : null,
                  },
                ]}
                limitations={[
                  ...(!hasProvenance ? [
                    "This result was saved before metric sources were recorded. Its champion values may be developer-reported (MDD) figures rather than metrics computed from model predictions.",
                  ] : []),
                  ...(referenceMetrics?.warnings ?? []).filter(Boolean),
                ]}
              />
              {/* ── Industry benchmark table ─────────────────────────── */}
              <VCard title="Industry Benchmark Table" sub="Selected challenger benchmark versus champion model">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                        <th className="w-10 px-4 py-2.5 text-left">#</th>
                        <th className="px-3 py-2.5 text-left">Model</th>
                        <th className="px-3 py-2.5 text-right">ROC-AUC</th>
                        <th className="px-3 py-2.5 text-right">Gini</th>
                        <th className="px-3 py-2.5 text-right">Recall</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {benchmarkTableRows.map((row, rowIndex) => {
                        const badge =
                          row.kind === "champion"
                            ? { text: "Champion · computed", cls: "bg-indigo-50 text-indigo-700" }
                            : row.kind === "challenger"
                            ? { text: "Challenger · computed", cls: "bg-cyan-50 text-cyan-700" }
                            : { text: "Reference · not computed", cls: "bg-slate-100 text-slate-600" };
                        return (
                          <tr key={`${row.kind}-${row.model}`} className={row.kind === "reference" ? "bg-slate-50/40" : "hover:bg-slate-50/60"}>
                            <td className="px-4 py-3 text-slate-400">{rowIndex + 1}</td>
                            <td className="px-3 py-3">
                              <span className="font-medium text-slate-900">{row.model}</span>
                              <span className={"ml-2 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide " + badge.cls}>
                                {badge.text}
                              </span>
                              {row.source ? <div className="mt-0.5 text-[11px] text-slate-400">Source: {row.source}</div> : null}
                            </td>
                            <td className="px-3 py-3 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.roc_auc, 3)}</td>
                            <td className="px-3 py-3 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.gini, 3)}</td>
                            <td className="px-3 py-3 text-right font-mono text-[13px] tabular-nums text-slate-700">{formatValue(row.recall, 3)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </VCard>

              {/* Keep the two analytical charts aligned in a compact 2-column grid
                  on desktop/tablet so the page reads as a single analytics panel,
                  while still collapsing cleanly to one column on smaller screens. */}
              <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <VCard
                  title="Champion vs Challenger Comparison"
                  sub="Metric deltas from the real benchmark response"
                  className="p-4"
                  contentClassName="mt-3"
                >
                  <div className="h-[260px] min-w-0 overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                    <PlotlyChart figure={benchmarkComparisonFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                  </div>
                </VCard>

                <VCard
                  title="ROC Overlay Chart"
                  sub={
                    (challengerRocPoints.length
                      ? "Champion vs challenger — both curves computed from each model's predictions on the same test rows"
                      : "Champion only — this saved result has no measured challenger curve; re-run the benchmark to add it") +
                    ` · Champion: ${describeCurveProvenance(payload?.report?.roc_curve?.provenance)}` +
                    (challengerRocPoints.length ? ` · Challenger: ${describeCurveProvenance(benchmarkResponse?.roc_curve?.provenance)}` : "")
                  }
                  className="p-4"
                  contentClassName="mt-3"
                >
                  <div className="h-[260px] min-w-0 overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                    <PlotlyChart figure={benchmarkOverlayFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                  </div>
                </VCard>
              </section>
            </>
          ) : null}
        </div>
      ) : null}

      {/* ── Navigation — a normal end-of-page action, not floating over
          content. ────────────────────────────────────────────────────── */}
      <div className="flex justify-end pb-2">
        <Link
          to="/validation/stress"
          className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
        >
          Continue to Stage 5
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
