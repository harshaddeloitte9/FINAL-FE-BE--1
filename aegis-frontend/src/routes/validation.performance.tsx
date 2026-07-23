import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight, AlertCircle, Loader2, PlayCircle } from "lucide-react";
import { useDataset } from "@/lib/app-context";
import PlotlyChart from "@/components/plotly-chart";
import { ApiError, formUpload } from "@/lib/api";

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
type PerformanceResponse = {
  stage: string;
  report: {
    metrics: Record<string, any>;
    roc_curve: { points: Array<Record<string, number>>; auc?: number | null };
    benchmark?: Record<string, any>;
  };
};

const benchmarkOptions = [
  { value: "Logistic Regression (Industry Standard)", label: "Logistic Regression" },
  { value: "Decision Tree (Industry Standard)", label: "Decision Tree" },
  { value: "Random Forest (Industry Standard)", label: "Random Forest" },
];

function formatValue(value: unknown, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return num.toFixed(digits);
}

function Performance() {
  const ds = useDataset();
  const [targetCol, setTargetCol] = React.useState(
    () => ds.profile?.target_col || ds.trainingResult?.evaluation_data?.target_col || "default",
  );
  const [modelName, setModelName] = React.useState(
    () => ds.selectedModel?.name || ds.trainingResult?.model_name || "Logistic Regression",
  );
  const [benchmarkModel, setBenchmarkModel] = React.useState("Logistic Regression (Industry Standard)");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // Seed from shared context so returning to this page (e.g. via Back from
  // Stage 5) shows the already-computed result instead of resetting to the
  // bare input form — payload previously lived only in this local state and
  // was lost on every remount.
  const [payload, setPayload] = React.useState<PerformanceResponse | null>(
    (ds.validationStage5Result as PerformanceResponse | null) ?? null,
  );

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

    setLoading(true);
    setError(null);
    setPayload(null);
    try {
      const form = new FormData();
      form.append("file", fileToUse);
      form.append("model_name", modelName.trim());
      form.append("target_col", targetCol.trim());
      form.append("benchmark_model", benchmarkModel.trim());
      const res = await formUpload<PerformanceResponse>("/validation/performance", form);
      setPayload(res);
      ds.setValidationStage5Result(res as unknown as Record<string, any>);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail =
          err.body && typeof err.body === "object" && "detail" in (err.body as any)
            ? String((err.body as any).detail)
            : err.message;
        setError(detail);
      } else {
        setError(err instanceof Error ? err.message : "Benchmark analysis failed.");
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetFile, targetCol, modelName, benchmarkModel]);

  // Auto-run once the shared dataset from Intake/Data Upload is available,
  // same as Stage 2 — the reviewer shouldn't have to manually
  // re-upload a file that's already sitting in context just to see Stage 4
  // results. Skipped if we already restored a cached result from context
  // (Back/Forward nav) or the reviewer already ran it locally this session.
  const autoRunAttempted = React.useRef(payload !== null);
  React.useEffect(() => {
    if (autoRunAttempted.current) return;
    if (!datasetReady || !datasetFile) return;
    if (!targetCol.trim() || !modelName.trim()) return;
    autoRunAttempted.current = true;
    void handleRun(datasetFile);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetReady, datasetFile, targetCol, modelName]);

  const rocPoints = payload?.report?.roc_curve?.points ?? [];
  const benchmarkResponse = payload?.report?.benchmark;
  const benchmarkComparison = benchmarkResponse?.comparison?.champion_vs_challenger;

  const benchmarkTableRows = React.useMemo(() => {
    const championMetrics = payload?.report?.metrics ?? {};
    const challengerMetrics = benchmarkResponse?.metrics ?? {};
    return [
      { model: "Champion", roc_auc: championMetrics.roc_auc, gini: championMetrics.gini, recall: championMetrics.recall },
      { model: benchmarkResponse?.model_name ?? "Benchmark", roc_auc: challengerMetrics.roc_auc, gini: challengerMetrics.gini, recall: challengerMetrics.recall },
    ];
  }, [payload, benchmarkResponse]);

  const benchmarkOverlayData = React.useMemo(() => {
    const championPoints = rocPoints ?? [];
    const benchmarkAuc = Number(benchmarkResponse?.metrics?.roc_auc ?? 0.5);
    const points = championPoints.length
      ? championPoints.map((point) => ({ fpr: point.fpr, champion: point.tpr, benchmark: Math.min(1, Math.max(0, point.fpr * benchmarkAuc)) }))
      : [{ fpr: 0, champion: 0, benchmark: 0 }, { fpr: 1, champion: 1, benchmark: benchmarkAuc }];
    return points;
  }, [rocPoints, benchmarkResponse]);

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
          marker: { color: "oklch(0.76 0.18 130)" },
        },
        {
          type: "bar",
          x: metrics,
          y: challenger,
          name: "Challenger",
          marker: { color: "oklch(0.55 0.02 240)" },
        },
      ],
      layout: {
        barmode: "group",
        margin: { l: 40, r: 20, t: 25, b: 40 },
        xaxis: { title: "Metric", tickfont: { size: 11 }, showline: false },
        yaxis: { title: "Value", tickfont: { size: 11 }, showline: false, range: [0, 1] },
        height: 320,
      },
    };
  }, [comparisonChartData]);

  const benchmarkOverlayFigure = React.useMemo(() => {
    const fpr = benchmarkOverlayData.map((point) => point.fpr);
    const champion = benchmarkOverlayData.map((point) => point.champion);
    const benchmark = benchmarkOverlayData.map((point) => point.benchmark);
    return {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x: fpr,
          y: champion,
          line: { color: "oklch(0.6 0.18 135)", width: 2.5 },
          hovertemplate: "Champion TPR %{y:.3f}<br>FPR %{x:.3f}<extra></extra>",
          name: "Champion",
        },
        {
          type: "scatter",
          mode: "lines",
          x: fpr,
          y: benchmark,
          line: { color: "oklch(0.55 0.02 240)", width: 2.5 },
          hovertemplate: "Benchmark TPR %{y:.3f}<br>FPR %{x:.3f}<extra></extra>",
          name: "Benchmark",
        },
      ],
      layout: {
        margin: { l: 40, r: 20, t: 25, b: 40 },
        xaxis: { title: "FPR", tickfont: { size: 11 }, showline: false },
        yaxis: { title: "TPR", tickfont: { size: 11 }, showline: false },
        height: 320,
      },
    };
  }, [benchmarkOverlayData]);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 4 — Benchmarking"
        description="Compare the champion model against an industry-standard challenger before stress testing and regulatory review."
      />

      {loading ? (
        <section className="flex items-center gap-2 rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground shadow-elegant">
          <Loader2 className="h-4 w-4 animate-spin" />
          Running Stage 4 benchmarking analysis on the shared dataset…
        </section>
      ) : null}

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      <section className="rounded-xl border border-border bg-background p-4 text-sm text-muted-foreground">
        {datasetReady ? (
          <>Using the shared dataset from Stage 1 / Stage 2: <span className="font-semibold text-foreground">{datasetName}</span>.</>
        ) : (
          <>No active dataset is available in shared state yet. Complete Stage 1 Intake and Stage 2 Data Validation first.</>
        )}
      </section>

      {!payload && !loading ? (
        <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground shadow-elegant">
          Waiting on a dataset from Stage 1/Stage 2 to run the Stage 4 benchmark report.
        </div>
      ) : null}

      {payload ? (
        <div className="space-y-6">
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex flex-wrap items-end gap-4">
              <label className="space-y-2 text-sm">
                <span className="font-medium">Benchmark selector</span>
                <select
                  value={benchmarkModel}
                  onChange={(e) => setBenchmarkModel(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                >
                  {benchmarkOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => handleRun()}
                disabled={loading || !datasetFile}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                Run Benchmark
              </button>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="Industry benchmark table" sub="Selected challenger benchmark versus champion model">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-background text-[10px] uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Model</th>
                      <th className="px-3 py-2 text-right">ROC-AUC</th>
                      <th className="px-3 py-2 text-right">Gini</th>
                      <th className="px-3 py-2 text-right">Recall</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {benchmarkTableRows.map((row, rowIndex) => (
                      <tr key={row.model}>
                        <td className="px-3 py-2 text-muted-foreground">{rowIndex + 1}</td>
                        <td className="px-3 py-2 font-medium">{row.model}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatValue(row.roc_auc, 3)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatValue(row.gini, 3)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatValue(row.recall, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="Champion vs Challenger comparison" sub="Metric deltas from the benchmark response">
              <PlotlyChart figure={benchmarkComparisonFigure} style={{ height: "100%" }} />
            </Card>

            <Card title="ROC overlay chart" sub="Champion vs selected benchmark model">
              <PlotlyChart figure={benchmarkOverlayFigure} style={{ height: "100%" }} />
            </Card>
          </section>
        </div>
      ) : null}

      <div className="text-right">
        <Link
          to="/validation/stress"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 5
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
      <h3 className="text-sm font-semibold">{title}</h3>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      <div className="mt-4 h-56">{children}</div>
    </div>
  );
}
