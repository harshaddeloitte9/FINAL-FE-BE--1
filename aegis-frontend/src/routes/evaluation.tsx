import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";
import PlotlyChart from "@/components/plotly-chart";
import { ArrowLeft, ArrowRight, Download, Info } from "lucide-react";
import { useMemo, useState } from "react";

export const Route = createFileRoute("/evaluation")({
  head: () => ({ meta: [{ title: "Evaluation — Aegis Credit" }] }),
  component: Evaluation,
});

function makeCsvRows(metrics: Record<string, any>) {
  return Object.entries(metrics)
    .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
    .map(([key, value]) => [key, String(value)]);
}

function downloadCsv(metrics: Record<string, any>, fileName: string) {
  const rows = makeCsvRows(metrics);
  const csv = ["Metric,Value", ...rows.map(([key, value]) => `${JSON.stringify(key)},${JSON.stringify(value)}`)].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function downloadBase64File(base64: string, fileName: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatMetricValue(value: unknown) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  if (typeof value === "number") {
    return value.toFixed(3);
  }
  return String(value);
}

const AXIS_LINE_COLOR = "#334155"; // slate-700
const AXIS_TICK_COLOR = "#1e293b"; // slate-800
const AXIS_GRID_COLOR = "#cbd5e1"; // slate-300

function withTitleFont(title: unknown) {
  const text = typeof title === "string" ? title : (title as any)?.text;
  if (!text) return title;
  return {
    text,
    standoff: 14,
    font: { size: 15, color: AXIS_TICK_COLOR, ...((title as any)?.font ?? {}) },
  };
}

// Makes axis lines, ticks, and titles bolder and higher-contrast so charts are easier to read.
function enhanceFigureAxes(figure: any) {
  if (!figure) return figure;

  const baseAxis = {
    showline: true,
    linecolor: AXIS_LINE_COLOR,
    linewidth: 2,
    mirror: true,
    ticks: "outside",
    tickcolor: AXIS_LINE_COLOR,
    ticklen: 6,
    tickfont: { size: 13, color: AXIS_TICK_COLOR },
    showgrid: true,
    gridcolor: AXIS_GRID_COLOR,
    gridwidth: 1,
    zerolinecolor: AXIS_LINE_COLOR,
    zerolinewidth: 2,
    // Lets Plotly grow the margin as needed so the axis title never
    // overlaps long tick labels (paired with `standoff` on the title).
    automargin: true,
  };

  const layout = { ...(figure.layout ?? {}) };

  layout.xaxis = { ...baseAxis, ...(layout.xaxis ?? {}), title: withTitleFont(layout.xaxis?.title) };
  layout.yaxis = { ...baseAxis, ...(layout.yaxis ?? {}), title: withTitleFont(layout.yaxis?.title) };
  if (layout.xaxis2) {
    layout.xaxis2 = { ...baseAxis, ...layout.xaxis2, title: withTitleFont(layout.xaxis2?.title) };
  }
  if (layout.yaxis2) {
    layout.yaxis2 = { ...baseAxis, ...layout.yaxis2, title: withTitleFont(layout.yaxis2?.title) };
  }
  // Backend figures are styled for a dark card (light-gray text) — this UI
  // renders charts on a light card, so our high-contrast color must win
  // over whatever the backend sent, not the other way around.
  layout.font = { ...(layout.font ?? {}), size: 13, color: AXIS_TICK_COLOR };
  layout.margin = { t: 30, r: 20, b: 60, l: 65, ...(layout.margin ?? {}) };

  // Same light-on-dark mismatch applies to the chart title and legend,
  // neither of which inherit cleanly from layout.font since the backend
  // sets its own explicit colors on them.
  if (layout.title) {
    const titleObj = typeof layout.title === "string" ? { text: layout.title } : { ...layout.title };
    layout.title = { ...titleObj, font: { size: 16, ...(titleObj.font ?? {}), color: AXIS_TICK_COLOR } };
  }
  layout.legend = {
    ...(layout.legend ?? {}),
    font: { size: 12, color: AXIS_TICK_COLOR },
    bgcolor: "rgba(255,255,255,0.85)",
    bordercolor: AXIS_GRID_COLOR,
    borderwidth: 1,
  };

  return { ...figure, layout };
}

function toneClasses(tone: string) {
  if (tone === "warning") return "border-amber-500/40 bg-amber-500/5";
  if (tone === "destructive") return "border-destructive/40 bg-destructive/5";
  return "border-primary/40 bg-primary/5";
}

function Card({ title, sub, children, className }: { title: string; sub?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-border bg-card p-6 shadow-elegant ${className ?? ""}`.trim()}>
      <h3 className="text-sm font-semibold">{title}</h3>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      <div className="mt-4">{children}</div>
    </div>
  );
}

function Evaluation() {
  const navigate = useNavigate();
  const { trainingResult } = useDataset();
  const [activeTab, setActiveTab] = useState<"summary" | "roc" | "pr" | "confusion" | "score" | "threshold" | "lift" | "residual" | "temporal">("summary");
  const [temporalDateColumn, setTemporalDateColumn] = useState<string | null>(null);
  const [temporalFrequency, setTemporalFrequency] = useState<string>("Quarterly");

  const evaluationMetrics = trainingResult?.evaluation_metrics && typeof trainingResult.evaluation_metrics === "object"
    ? trainingResult.evaluation_metrics
    : null;
  const evaluationData = trainingResult?.evaluation_data && typeof trainingResult.evaluation_data === "object"
    ? trainingResult.evaluation_data
    : null;
  const modelArtifact = typeof trainingResult?.model_artifact === "string" ? trainingResult.model_artifact : null;
  const taskType = typeof trainingResult?.task_type === "string" ? trainingResult.task_type : "binary";
  const threshold = typeof evaluationMetrics?.threshold_used === "number"
    ? evaluationMetrics.threshold_used
    : typeof evaluationData?.threshold === "number"
      ? evaluationData.threshold
      : 0.5;
  // Present only when the backend auto-picked the threshold (i.e. no explicit
  // override was passed to /models/train) — see evaluate_new.select_best_threshold.
  const thresholdSelection = evaluationMetrics?.threshold_selection ?? evaluationData?.threshold_selection ?? null;
  const isAutoThreshold = thresholdSelection != null;

  const confusion = useMemo(() => {
    const matrix = evaluationMetrics?.confusion_matrix;
    if (Array.isArray(matrix) && matrix.length === 2 && Array.isArray(matrix[0]) && Array.isArray(matrix[1])) {
      return [
        ["True Negative", matrix[0][0], "primary"],
        ["False Positive", matrix[0][1], "warning"],
        ["False Negative", matrix[1][0], "destructive"],
        ["True Positive", matrix[1][1], "primary"],
      ] as const;
    }
    return [
      ["True Negative", 0, "primary"],
      ["False Positive", 0, "warning"],
      ["False Negative", 0, "destructive"],
      ["True Positive", 0, "primary"],
    ] as const;
  }, [evaluationMetrics?.confusion_matrix]);

  const rocFigure = useMemo(() => enhanceFigureAxes(evaluationData?.roc_curve_figure ?? null), [evaluationData?.roc_curve_figure]);
  const prFigure = useMemo(() => enhanceFigureAxes(evaluationData?.pr_curve_figure ?? null), [evaluationData?.pr_curve_figure]);
  const thresholdFigure = useMemo(() => enhanceFigureAxes(evaluationData?.threshold_analysis_figure ?? null), [evaluationData?.threshold_analysis_figure]);
  const scoreDistributionFigure = useMemo(() => enhanceFigureAxes(evaluationData?.score_distribution_figure ?? null), [evaluationData?.score_distribution_figure]);
  const liftChartFigure = useMemo(() => enhanceFigureAxes(evaluationData?.lift_chart_figure ?? null), [evaluationData?.lift_chart_figure]);
  const heteroscedasticityCheck = useMemo(() => evaluationData?.heteroscedasticity_check ?? null, [evaluationData?.heteroscedasticity_check]);
  const temporalAnalysis = useMemo(() => evaluationData?.temporal_analysis ?? null, [evaluationData?.temporal_analysis]);
  const temporalRows = useMemo(() => {
    if (!temporalAnalysis) {
      return [] as Array<{ period: string; actual_rate: number; predicted_rate: number; gap: number; flagged: boolean }>;
    }

    if (temporalFrequency === "Quarterly") {
      return temporalAnalysis.plot_data ?? [];
    }

    return temporalAnalysis.plot_data_by_freq?.[temporalFrequency] ?? [];
  }, [temporalAnalysis, temporalFrequency]);

  const temporalFigure = useMemo(() => {
    if (!temporalRows || temporalRows.length === 0) return null;

    const periods = temporalRows.map((r: any) => r.period);
    const actual = temporalRows.map((r: any) => r.actual_rate);
    const predicted = temporalRows.map((r: any) => r.predicted_rate);
    const gap = temporalRows.map((r: any) => r.gap);
    // Flagged periods (significant actual-vs-predicted drift) get a red
    // marker so they stand out against the rest of the series at a glance.
    const markerColors = temporalRows.map((r: any) => (r.flagged ? "#ef4444" : "#0ea5e9"));

    return enhanceFigureAxes({
      data: [
        {
          type: "bar",
          name: "Gap",
          x: periods,
          y: gap,
          yaxis: "y2",
          marker: { color: "rgba(100,116,139,0.25)" },
          hovertemplate: "%{x}<br>Gap: %{y:.3f}<extra></extra>",
        },
        {
          type: "scatter",
          mode: "lines+markers",
          name: "Actual Rate",
          x: periods,
          y: actual,
          line: { color: "#0ea5e9", width: 3 },
          marker: { color: markerColors, size: 8 },
          hovertemplate: "%{x}<br>Actual: %{y:.3f}<extra></extra>",
        },
        {
          type: "scatter",
          mode: "lines+markers",
          name: "Predicted Rate",
          x: periods,
          y: predicted,
          line: { color: "#6366f1", width: 3, dash: "dot" },
          marker: { size: 6 },
          hovertemplate: "%{x}<br>Predicted: %{y:.3f}<extra></extra>",
        },
      ],
      layout: {
        title: "Actual vs Predicted Default Rate",
        xaxis: { title: "Period" },
        yaxis: { title: "Rate" },
        yaxis2: { title: "Gap", overlaying: "y", side: "right", showgrid: false },
        legend: { orientation: "h", y: 1.18 },
        barmode: "overlay",
      },
    });
  }, [temporalRows]);

  const temporalSummary = useMemo(() => {
    if (!temporalAnalysis) {
      return null;
    }

    if (temporalFrequency === "Quarterly") {
      return temporalAnalysis.summary ?? null;
    }

    return temporalAnalysis.summaries_by_freq?.[temporalFrequency] ?? null;
  }, [temporalAnalysis, temporalFrequency]);

  const summaryMetricRows = useMemo(() => {
    if (taskType !== "binary") {
      return [
        { label: "R²", value: evaluationMetrics?.r2 },
        { label: "MAE", value: evaluationMetrics?.mae },
        { label: "MSE", value: evaluationMetrics?.mse },
        { label: "RMSE", value: evaluationMetrics?.rmse },
      ];
    }

    return [
      { label: "Accuracy", value: evaluationMetrics?.accuracy },
      { label: "Precision", value: evaluationMetrics?.precision },
      { label: "Recall", value: evaluationMetrics?.recall },
      { label: "F1 score", value: evaluationMetrics?.f1 },
      { label: "ROC AUC", value: evaluationMetrics?.roc_auc },
      { label: "PR AUC", value: evaluationMetrics?.pr_auc },
      { label: "KS statistic", value: evaluationMetrics?.ks_statistic },
      { label: "Brier score", value: evaluationMetrics?.brier_score },
    ];
  }, [evaluationMetrics, taskType]);

  const classificationReportRows = useMemo(() => {
    const report = evaluationMetrics?.classification_report;
    if (!report || typeof report !== "object") {
      return [] as Array<{ label: string; precision?: number; recall?: number; f1?: number; support?: number }>;
    }

    return Object.entries(report)
      .filter(([, value]) => value && typeof value === "object" && "precision" in value)
      .map(([label, value]) => {
        const row = value as Record<string, unknown>;
        return {
          label,
          precision: typeof row.precision === "number" ? row.precision : undefined,
          recall: typeof row.recall === "number" ? row.recall : undefined,
          f1: typeof row["f1-score"] === "number" ? row["f1-score"] : undefined,
          support: typeof row.support === "number" ? row.support : undefined,
        };
      });
  }, [evaluationMetrics?.classification_report]);

  useMemo(() => {
    if (!temporalAnalysis || temporalDateColumn) {
      return;
    }
    const available = temporalAnalysis.date_columns ?? [];
    if (available.length > 0) {
      setTemporalDateColumn(available[0]);
    }
  }, [temporalAnalysis, temporalDateColumn]);

  if (!trainingResult) {
    return (
      <div className="space-y-8">
        <PageHeader
          title="Evaluation"
          description="Interactive performance diagnostics on the hold-out test set."
        />
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No trained model available</h3>
          <p className="mt-2 text-sm text-muted-foreground">Run training first to populate evaluation metrics and compliance checks.</p>
          <Button onClick={() => navigate({ to: "/training" })} className="mt-4">
            Go to Training
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Evaluation"
        description="Interactive performance diagnostics on the hold-out test set."
        actions={
          <div className="flex flex-wrap gap-2">
            {evaluationMetrics && (
              <Button variant="outline" onClick={() => downloadCsv(evaluationMetrics, "evaluation_metrics.csv")} className="gap-2">
                <Download className="h-4 w-4" />
                Download metrics CSV
              </Button>
            )}
            {modelArtifact && (
              <Button variant="outline" onClick={() => downloadBase64File(modelArtifact, "trained_model.pkl")} className="gap-2">
                <Download className="h-4 w-4" />
                Download model artifact
              </Button>
            )}
          </div>
        }
      />

      <section className="grid grid-cols-1 gap-6">
          <div className="space-y-6">
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg bg-background/60 p-1">
              {(["summary","roc","pr","confusion","score","threshold","lift","residual","temporal"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`px-3 py-1 text-sm rounded ${activeTab===t?"bg-primary text-white":"text-muted-foreground"}`}>
                  {t === "summary" ? "Summary" : t === "roc" ? "ROC Curve" : t === "pr" ? "PR Curve" : t === "confusion" ? "Confusion" : t === "score" ? "Score Dist" : t === "threshold" ? "Thresholds" : t === "lift" ? "Lift" : t === "residual" ? "Residuals" : "Temporal"}
                </button>
              ))}
            </div>
          </div>

          {activeTab === "summary" ? (
            <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
              <Card
                title="Hold-out performance"
                sub={`Key evaluation metrics from the test split · decision threshold ${threshold.toFixed(2)}${isAutoThreshold ? " (auto-selected, max F1)" : ""}`}
              >
                {isAutoThreshold && (
                  <div className="mb-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-500/10 p-3">
                    <Info className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-blue-900">
                      Threshold <strong>{threshold.toFixed(2)}</strong> was chosen automatically — it's the cut-off
                      that maximizes F1 ({(thresholdSelection.f1 * 100).toFixed(1)}%) on this hold-out set, out of
                      99 candidate thresholds swept from 0.01 to 0.99. At this cut-off: precision{" "}
                      {(thresholdSelection.precision * 100).toFixed(1)}%, recall {(thresholdSelection.recall * 100).toFixed(1)}%.
                    </p>
                  </div>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  {summaryMetricRows.map((metric) => (
                    <div key={metric.label} className="rounded-lg border border-border bg-background/70 p-3">
                      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{metric.label}</div>
                      <div className="mt-1 text-lg font-semibold tabular-nums">{formatMetricValue(metric.value)}</div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card title="Classification report" sub="Per-class precision, recall, F1 and support">
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
                        <th className="py-2 pr-3">Class</th>
                        <th className="py-2 pr-3">Precision</th>
                        <th className="py-2 pr-3">Recall</th>
                        <th className="py-2 pr-3">F1</th>
                        <th className="py-2">Support</th>
                      </tr>
                    </thead>
                    <tbody>
                      {classificationReportRows.length > 0 ? (
                        classificationReportRows.map((row) => (
                          <tr key={row.label} className="border-b border-border/60 text-sm">
                            <td className="py-2 pr-3 font-medium">{row.label}</td>
                            <td className="py-2 pr-3">{formatMetricValue(row.precision)}</td>
                            <td className="py-2 pr-3">{formatMetricValue(row.recall)}</td>
                            <td className="py-2 pr-3">{formatMetricValue(row.f1)}</td>
                            <td className="py-2">{formatMetricValue(row.support)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} className="py-3 text-sm text-muted-foreground">Classification report will appear after a completed binary classification run.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          ) : (
          <div className="grid gap-6">
            {activeTab === "roc" && (
              <Card title="ROC curve" sub={evaluationMetrics?.roc_auc ? `AUC ${evaluationMetrics.roc_auc}` : "Probability output unavailable"}>
                {rocFigure ? (
                  <PlotlyChart figure={rocFigure} style={{ minHeight: 360 }} />
                ) : (
                  <p className="text-sm text-muted-foreground">ROC curve requires probability predictions from a binary classification model.</p>
                )}
              </Card>
            )}

            {activeTab === "pr" && (
              <Card title="Precision–Recall" sub={evaluationMetrics?.pr_auc ? `Average precision ${evaluationMetrics.pr_auc}` : "Probability output unavailable"}>
                {prFigure ? (
                  <PlotlyChart figure={prFigure} style={{ minHeight: 360 }} />
                ) : (
                  <p className="text-sm text-muted-foreground">Precision–Recall curve requires probability predictions from a binary classification model.</p>
                )}
              </Card>
            )}

            {activeTab === "confusion" && (
              <Card title="Confusion matrix" sub={`Threshold ${threshold.toFixed(2)}${isAutoThreshold ? " (auto-selected, max F1)" : ""}`}>
                <div className="flex justify-center overflow-auto py-2">
                  <table className="border-separate" style={{ borderSpacing: 8 }}>
                    <thead>
                      <tr>
                        <th />
                        <th />
                        <th colSpan={2} className="pb-1 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          Predicted
                        </th>
                      </tr>
                      <tr>
                        <th />
                        <th />
                        <th className="px-2 pb-2 text-center text-xs font-medium text-muted-foreground">0</th>
                        <th className="px-2 pb-2 text-center text-xs font-medium text-muted-foreground">1</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th
                          rowSpan={2}
                          className="pr-1 text-center align-middle text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                          style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
                        >
                          Actual
                        </th>
                        <th className="pr-2 text-center text-xs font-medium text-muted-foreground">0</th>
                        {[confusion[0], confusion[1]].map(([label, count, tone]) => (
                          <td key={label} className={`rounded-lg border p-4 text-center ${toneClasses(tone)}`}>
                            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
                            <div className="mt-1 text-lg font-semibold tabular-nums">{Number(count).toLocaleString()}</div>
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <th className="pr-2 text-center text-xs font-medium text-muted-foreground">1</th>
                        {[confusion[2], confusion[3]].map(([label, count, tone]) => (
                          <td key={label} className={`rounded-lg border p-4 text-center ${toneClasses(tone)}`}>
                            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
                            <div className="mt-1 text-lg font-semibold tabular-nums">{Number(count).toLocaleString()}</div>
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {activeTab === "lift" && (
              <Card title="Gain & lift" sub="Cumulative gain and lift by decile">
                {liftChartFigure ? (
                  <PlotlyChart figure={liftChartFigure} style={{ minHeight: 360 }} />
                ) : (
                  <p className="text-sm text-muted-foreground">Gain and lift charts require probability predictions from a binary classification model.</p>
                )}
              </Card>
            )}

            {activeTab === "threshold" && (
              <Card
                title="Threshold analysis"
                sub={isAutoThreshold ? `Precision · Recall · F1 across cut-offs · best F1 at ${threshold.toFixed(2)}` : "Precision · Recall · F1 across cut-offs"}
              >
                {thresholdFigure ? (
                  <PlotlyChart figure={thresholdFigure} style={{ minHeight: 360 }} />
                ) : (
                  <p className="text-sm text-muted-foreground">Threshold analysis requires probability predictions from a binary classification model.</p>
                )}
              </Card>
            )}

            {activeTab === "score" && (
              <Card title="Score distribution" sub="Hold-out set">
                {scoreDistributionFigure ? (
                  <PlotlyChart figure={scoreDistributionFigure} style={{ minHeight: 360 }} />
                ) : (
                  <p className="text-sm text-muted-foreground">Score distribution requires probability predictions from a binary classification model.</p>
                )}
              </Card>
            )}

            {activeTab === "residual" && (
              <Card title="Residual diagnostics" sub="Heteroscedasticity-style residual checks">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Signal</div>
                    <div className="mt-1 text-base font-semibold">{heteroscedasticityCheck?.risk_flag ?? "N/A"}</div>
                  </div>
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Abs residual corr</div>
                    <div className="mt-1 text-base font-semibold">{formatMetricValue(heteroscedasticityCheck?.spearman_abs_resid_vs_score)}</div>
                  </div>
                  <div className="rounded-lg border border-border bg-background/70 p-3 sm:col-span-2">
                    <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Variance ratio</div>
                    <div className="mt-1 text-base font-semibold">{formatMetricValue(heteroscedasticityCheck?.variance_ratio)}</div>
                  </div>
                </div>
                {Array.isArray(heteroscedasticityCheck?.bin_variance) && heteroscedasticityCheck.bin_variance.length > 0 && (
                  <div className="mt-4 overflow-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
                          <th className="py-2 pr-3">Bin</th>
                          <th className="py-2 pr-3">Count</th>
                          <th className="py-2">Variance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {heteroscedasticityCheck.bin_variance.map((row: Record<string, any>, index: number) => (
                          <tr key={`${row.score_bin ?? index}`} className="border-b border-border/60 text-sm">
                            <td className="py-2 pr-3">{row.score_bin ?? `Bin ${index + 1}`}</td>
                            <td className="py-2 pr-3">{row.n ?? "—"}</td>
                            <td className="py-2">{formatMetricValue(row.residual_variance)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            )}

            {activeTab === "temporal" && (
              <Card title="Actual vs Predicted" sub="Temporal stability by selected period">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <select value={temporalFrequency} onChange={(e) => setTemporalFrequency(e.target.value)} className="text-sm p-1 rounded bg-background">
                      {temporalAnalysis?.frequency_options?.map((f: string) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                  {temporalFigure ? (
                    <PlotlyChart figure={temporalFigure} style={{ minHeight: 380 }} />
                  ) : (
                    <p className="text-sm text-muted-foreground">No temporal data available for the selected period.</p>
                  )}
                </div>
              </Card>
            )}
          </div>
          )}

        </div>
      </section>

      <div className="flex gap-3 pt-4">
        <Button variant="outline" onClick={() => navigate({ to: "/training" })} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Training
        </Button>
        <Button onClick={() => navigate({ to: "/explainability" })} className="gap-2 ml-auto">
          Proceed to Explainability
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
