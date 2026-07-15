import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowRight, AlertCircle, Loader2, PlayCircle, UploadCloud } from "lucide-react";
import { rocCurve, prCurve, scoreDistribution } from "@/lib/mock-data";
import { useDataset } from "@/lib/app-context";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar,
} from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
import { ApiError, formUpload } from "@/lib/api";

export const Route = createFileRoute("/validation/performance")({
  head: () => ({ meta: [{ title: "Performance Validation — Aegis Credit" }] }),
  component: Performance,
});

type PerformanceResponse = {
  stage: string;
  report: {
    metrics: Record<string, any>;
    roc_curve: { points: Array<Record<string, number>>; auc?: number | null };
    pr_curve: { points: Array<Record<string, number>>; average_precision?: number | null };
    confusion_matrix: { labels: Array<number | string>; matrix: number[][] };
    score_distribution: { bins: Array<Record<string, any>> };
    calibration_chart: { points: Array<Record<string, any>> };
    train_test_auc_gap: { gap?: number | null; status?: string | null; cv_mean_auc?: number | null; test_auc?: number | null };
    metric_checks?: Array<Record<string, any>>;
    compliance_findings?: Array<Record<string, any>>;
    benchmark?: Record<string, any>;
    threshold_analysis?: Array<Record<string, any>>;
  };
  replication?: Record<string, any>;
};

const metricDefinitions = [
  { key: "roc_auc", label: "ROC-AUC", digits: 3 },
  { key: "gini", label: "Gini", digits: 3 },
  { key: "ks", label: "KS", digits: 3 },
  { key: "accuracy", label: "Accuracy", digits: 3 },
  { key: "precision", label: "Precision", digits: 3 },
  { key: "recall", label: "Recall", digits: 3 },
  { key: "f1", label: "F1 Score", digits: 3 },
  { key: "brier_score", label: "Brier", digits: 3 },
  { key: "pr_auc", label: "PR-AUC", digits: 3 },
];

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
  const [localFile, setLocalFile] = React.useState<File | null>(null);
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
  // Stage 6) shows the already-computed result instead of resetting to the
  // bare input form — payload previously lived only in this local state and
  // was lost on every remount.
  const [payload, setPayload] = React.useState<PerformanceResponse | null>(
    (ds.validationStage5Result as PerformanceResponse | null) ?? null,
  );

  const datasetFile = localFile ?? ds.file ?? null;
  const datasetName = localFile?.name ?? ds.file?.name ?? ds.profile?.dataset_name ?? "uploaded dataset";
  const datasetReady = Boolean(localFile || ds.file || ds.profile?.csv_text || ds.profile?.dataset_name);

  const handleRun = React.useCallback(async (fileOverride?: File | null) => {
    const fileToUse = fileOverride ?? datasetFile;
    if (!fileToUse) {
      setError("Upload a dataset or use the file from Intake before running Stage 5.");
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
        setError(err instanceof Error ? err.message : "Performance analysis failed.");
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetFile, targetCol, modelName, benchmarkModel]);

  // Auto-run once the shared dataset from Intake/Data Upload is available,
  // same as Stage 2/Stage 3 — the reviewer shouldn't have to manually
  // re-upload a file that's already sitting in context just to see Stage 5
  // results. Skipped if we already restored a cached result from context
  // (Back/Forward nav) or the reviewer already ran it locally this session.
  const autoRunAttempted = React.useRef(payload !== null);
  React.useEffect(() => {
    if (autoRunAttempted.current) return;
    if (!datasetReady || !ds.file) return;
    if (!targetCol.trim() || !modelName.trim()) return;
    autoRunAttempted.current = true;
    void handleRun(ds.file);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetReady, ds.file, targetCol, modelName]);

  const metricCards = React.useMemo(() => {
    const metrics = payload?.report?.metrics ?? {};
    return metricDefinitions
      .map((item) => ({ label: item.label, value: formatValue(metrics[item.key], item.digits) }))
      .filter((item) => item.value !== "—");
  }, [payload]);

  const gap = payload?.report?.train_test_auc_gap;
  const rocPoints = payload?.report?.roc_curve?.points ?? [];
  const prPoints = payload?.report?.pr_curve?.points ?? [];
  const scoreBins = payload?.report?.score_distribution?.bins ?? [];
  const calibrationPoints = payload?.report?.calibration_chart?.points ?? [];
  const confusionMatrix = payload?.report?.confusion_matrix;
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

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 5 — Performance Testing"
        description="Comprehensive performance evaluation on the independent validation hold-out set before stress testing and regulatory review."
      />

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="grid gap-4 md:grid-cols-3">
          <label className="space-y-2 text-sm">
            <span className="font-medium">Dataset</span>
            <div className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-background px-3 py-2 text-sm text-muted-foreground">
              <UploadCloud className="h-4 w-4" />
              <span className="truncate">{datasetName}</span>
            </div>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              className="block w-full text-sm text-muted-foreground"
              onChange={(e) => setLocalFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <label className="space-y-2 text-sm">
            <span className="font-medium">Target column</span>
            <input
              value={targetCol}
              onChange={(e) => setTargetCol(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2"
              placeholder="e.g. default"
            />
          </label>

          <label className="space-y-2 text-sm">
            <span className="font-medium">Model name</span>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2"
              placeholder="e.g. Logistic Regression"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => handleRun()}
            disabled={!datasetFile || loading}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            Run Stage 5 analysis
          </button>
          <span className="text-sm text-muted-foreground">Uses the new backend performance endpoint for ROC, PR, calibration, and confusion outputs.</span>
        </div>

        {error ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-border bg-background p-4 text-sm text-muted-foreground">
        {datasetReady ? (
          <>Using the shared dataset from Stage 1 / Stage 2: <span className="font-semibold text-foreground">{datasetName}</span>.</>
        ) : (
          <>No active dataset is available in shared state yet. Complete Stage 1 Intake and Stage 2 Data Validation first.</>
        )}
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {metricCards.map((m) => (
          <div key={m.label} className="rounded-xl border border-border bg-card p-4 shadow-elegant">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{m.label}</div>
            <div className="mt-2 text-xl font-semibold tracking-tight tabular-nums">{m.value}</div>
          </div>
        ))}
      </section>

      {!payload && !loading ? (
        <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground shadow-elegant">
          Run the analysis to populate the Stage 5 performance report.
        </div>
      ) : null}

      {payload ? (
        <Tabs defaultValue="performance" className="w-full">
          <TabsList>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="benchmarking">Benchmarking</TabsTrigger>
          </TabsList>

          <TabsContent value="performance" className="space-y-8 pt-4">
            <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
              {metricCards.map((m) => (
                <div key={m.label} className="rounded-xl border border-border bg-card p-4 shadow-elegant">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{m.label}</div>
                  <div className="mt-2 text-xl font-semibold tracking-tight tabular-nums">{m.value}</div>
                </div>
              ))}
              <div className="rounded-xl border border-border bg-card p-4 shadow-elegant">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Train/Test AUC Gap</div>
                <div className="mt-2 text-xl font-semibold tracking-tight tabular-nums">
                  {gap ? formatValue(gap.gap, 3) : "—"}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Status: {gap?.status ?? "—"}
                </div>
              </div>
            </section>

            <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card title="ROC curve" sub={`AUC ${formatValue(payload.report.roc_curve.auc, 3)}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rocPoints.map((point) => ({ ...point, diagonal: point.fpr }))}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                    <XAxis dataKey="fpr" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis tickLine={false} axisLine={false} fontSize={11} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Line type="monotone" dataKey="tpr" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} dot={false} />
                    <Line type="linear" dataKey="diagonal" stroke="oklch(0.6 0.01 240)" strokeDasharray="4 4" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              <Card title="Precision–Recall" sub={`Average precision ${formatValue(payload.report.pr_curve.average_precision, 3)}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={prPoints}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                    <XAxis dataKey="recall" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis tickLine={false} axisLine={false} fontSize={11} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Line type="monotone" dataKey="precision" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              <Card title="Confusion matrix" sub="Threshold 0.50">
                <div className="grid h-full grid-cols-2 gap-3">
                  {confusionMatrix?.matrix?.length
                    ? confusionMatrix.matrix.flatMap((row, rowIndex) =>
                        row.map((value, colIndex) => {
                          const label = confusionMatrix.labels?.[colIndex] ?? colIndex;
                          const tone = rowIndex === 1 && colIndex === 1 ? "primary" : rowIndex === 0 && colIndex === 1 ? "warning" : "destructive";
                          return (
                            <div
                              key={`${rowIndex}-${colIndex}`}
                              className={
                                "flex flex-col justify-between rounded-xl border p-4 " +
                                (tone === "primary"
                                  ? "border-primary/30 bg-primary-soft"
                                  : tone === "warning"
                                    ? "border-warning/40 bg-warning/15"
                                    : "border-destructive/30 bg-destructive/10")
                              }
                            >
                              <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</span>
                              <span className="text-2xl font-semibold tabular-nums">{value.toLocaleString()}</span>
                            </div>
                          );
                        }),
                      )
                    : null}
                </div>
              </Card>

              <Card title="Calibration" sub="Predicted vs observed default rate">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={calibrationPoints.map((point) => ({ pred: point.predicted_rate, actual: point.actual_rate, perfect: point.predicted_rate }))}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                    <XAxis dataKey="pred" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis tickLine={false} axisLine={false} fontSize={11} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Line type="monotone" dataKey="actual" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} dot={false} />
                    <Line type="linear" dataKey="perfect" stroke="oklch(0.6 0.01 240)" strokeDasharray="4 4" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              <Card title="Score distribution" sub={`Hold-out set · KS ${formatValue(payload.report.metrics.ks, 3)}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={scoreBins.map((bin) => ({ bin: bin.bin, good: bin.good ?? 0, bad: bin.bad ?? 0 }))}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                    <XAxis dataKey="bin" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis tickLine={false} axisLine={false} fontSize={11} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Bar dataKey="good" stackId="a" fill="oklch(0.76 0.18 130)" />
                    <Bar dataKey="bad" stackId="a" fill="oklch(0.6 0.22 27)" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </section>
          </TabsContent>

          <TabsContent value="benchmarking" className="space-y-6 pt-4">
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
                        <th className="px-3 py-2 text-left">Model</th>
                        <th className="px-3 py-2 text-right">ROC-AUC</th>
                        <th className="px-3 py-2 text-right">Gini</th>
                        <th className="px-3 py-2 text-right">Recall</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {benchmarkTableRows.map((row) => (
                        <tr key={row.model}>
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
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonChartData}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                    <XAxis dataKey="metric" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis tickLine={false} axisLine={false} fontSize={11} domain={[0, 1]} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Bar dataKey="champion" fill="oklch(0.76 0.18 130)" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="challenger" fill="oklch(0.55 0.02 240)" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <Card title="ROC overlay chart" sub="Champion vs selected benchmark model">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={benchmarkOverlayData}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                    <XAxis dataKey="fpr" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis tickLine={false} axisLine={false} fontSize={11} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Line type="monotone" dataKey="champion" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="benchmark" stroke="oklch(0.55 0.02 240)" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </section>
          </TabsContent>
        </Tabs>
      ) : null}

      <div className="text-right">
        <Link
          to="/validation/stress"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 6
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
