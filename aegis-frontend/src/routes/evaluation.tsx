import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import PlotlyChart from "@/components/plotly-chart";
import { ArrowLeft, ArrowRight, Download, ShieldCheck } from "lucide-react";
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

function statusToBadgeVariant(status: string) {
  switch (status) {
    case "PASS":
      return "default" as const;
    case "WARN":
      return "secondary" as const;
    case "FAIL":
      return "destructive" as const;
    default:
      return "outline" as const;
  }
}

function formatReplicatedValue(value: unknown) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  if (typeof value === "number") {
    return value.toFixed(4);
  }
  return String(value);
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
  const [activeTab, setActiveTab] = useState<"roc" | "pr" | "confusion" | "score" | "threshold" | "lift" | "residual" | "temporal">("roc");
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

  const complianceLoading = false;
  const complianceError: string | null = null;
  const complianceScore: number | string | null = null;
  const complianceFlags: Array<{ rule_id: string; flag: string }> = [];
  const replicationLoading = false;
  const replicationError: string | null = null;
  const replicationResult = null as { metrics?: Record<string, any> } | null;
  const replicationMetrics: Record<string, any> = (replicationResult?.metrics ?? {}) as Record<string, any>;
  const replicationChecks: Array<{ id: string; title: string; status: string }> = [];

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

  const rocFigure = useMemo(() => evaluationData?.roc_curve_figure ?? null, [evaluationData?.roc_curve_figure]);
  const prFigure = useMemo(() => evaluationData?.pr_curve_figure ?? null, [evaluationData?.pr_curve_figure]);
  const confusionMatrixFigure = useMemo(() => evaluationData?.confusion_matrix_figure ?? null, [evaluationData?.confusion_matrix_figure]);
  const thresholdFigure = useMemo(() => evaluationData?.threshold_analysis_figure ?? null, [evaluationData?.threshold_analysis_figure]);
  const scoreDistributionFigure = useMemo(() => evaluationData?.score_distribution_figure ?? null, [evaluationData?.score_distribution_figure]);
  const liftChartFigure = useMemo(() => evaluationData?.lift_chart_figure ?? null, [evaluationData?.lift_chart_figure]);
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
          f1: typeof row.f1 === "number" ? row.f1 : undefined,
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

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_420px]">
          <div className="space-y-6">
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg bg-background/60 p-1">
              {(["roc","pr","confusion","score","threshold","lift","residual","temporal"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`px-3 py-1 text-sm rounded ${activeTab===t?"bg-primary text-white":"text-muted-foreground"}`}>
                  {t === "roc" ? "ROC Curve" : t === "pr" ? "PR Curve" : t === "confusion" ? "Confusion" : t === "score" ? "Score Dist" : t === "threshold" ? "Thresholds" : t === "lift" ? "Lift" : t === "residual" ? "Residuals" : "Temporal"}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card title="Hold-out performance" sub="Key evaluation metrics from the test split">
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

          <div className="grid gap-6 lg:grid-cols-2">
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
              <Card title="Confusion matrix" sub={`Threshold ${threshold.toFixed(2)}`}>
                {confusionMatrixFigure ? (
                  <PlotlyChart figure={confusionMatrixFigure} style={{ minHeight: 360 }} />
                ) : (
                  <p className="text-sm text-muted-foreground">Confusion matrix requires a binary classification prediction threshold.</p>
                )}
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
              <Card title="Threshold analysis" sub="Precision · Recall · F1 across cut-offs">
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
                  <div className="overflow-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
                          <th className="py-2 pr-3">Period</th>
                          <th className="py-2 pr-3">Actual Rate</th>
                          <th className="py-2 pr-3">Predicted Rate</th>
                          <th className="py-2">Gap</th>
                        </tr>
                      </thead>
                      <tbody>
                        {temporalRows.map((r: any, i: number) => (
                          <tr key={i} className="border-b border-border/60 text-sm">
                            <td className="py-2 pr-3">{r.period}</td>
                            <td className="py-2 pr-3">{formatMetricValue(r.actual_rate)}</td>
                            <td className="py-2 pr-3">{formatMetricValue(r.predicted_rate)}</td>
                            <td className="py-2">{formatMetricValue(r.gap)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </Card>
            )}
          </div>

        </div>

        <aside className="space-y-6">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold">Evaluation summary</h2>
            </div>
            <div className="grid gap-3 text-sm">
              <div className="flex items-center justify-between">
                <span>ROC AUC</span>
                <span className="font-semibold">{evaluationMetrics?.roc_auc ?? "N/A"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>PR AUC</span>
                <span className="font-semibold">{evaluationMetrics?.pr_auc ?? "N/A"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Recall</span>
                <span className="font-semibold">{evaluationMetrics?.recall ?? "N/A"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Precision</span>
                <span className="font-semibold">{evaluationMetrics?.precision ?? "N/A"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>F1 score</span>
                <span className="font-semibold">{evaluationMetrics?.f1 ?? "N/A"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Threshold</span>
                <span className="font-semibold">{threshold.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold">Compliance snapshot</h2>
            </div>
            {complianceLoading ? (
              <p className="text-sm text-muted-foreground">Loading compliance verdict…</p>
            ) : complianceError ? (
              <p className="text-sm text-destructive">{complianceError}</p>
            ) : (
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span>Compliance score</span>
                  <span className="font-semibold">{complianceScore ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Flags raised</span>
                  <span className="font-semibold">{complianceFlags?.length ?? 0}</span>
                </div>
                {complianceFlags && complianceFlags.length > 0 && (
                  <div className="space-y-2 pt-2">
                    {complianceFlags.slice(0, 3).map((flag, index) => (
                      <div key={index} className="rounded-lg border border-border p-3 bg-background">
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">{flag.rule_id}</div>
                        <div className="mt-1 text-sm font-semibold">{flag.flag}</div>
                      </div>
                    ))}
                  </div>
                )}
                {!complianceFlags?.length && <p className="text-sm text-muted-foreground">No compliance flags were raised in this evaluation run.</p>}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold">Replication validation</h2>
            </div>
            {replicationLoading ? (
              <p className="text-sm text-muted-foreground">Running replication checks…</p>
            ) : replicationError ? (
              <p className="text-sm text-destructive">{replicationError}</p>
            ) : replicationResult ? (
              <div className="space-y-4 text-sm">
                <div className="grid gap-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span>AUC</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.roc_auc)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Gini</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.gini)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>KS</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.ks)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Accuracy</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.accuracy)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Precision</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.precision)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Recall</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.recall)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>F1 score</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationMetrics.f1)}</span>
                  </div>
                </div>
                <div className="grid gap-2">
                  {replicationChecks?.slice(0, 6).map((check, index) => (
                    <div key={index} className="flex items-center justify-between rounded-xl border border-border bg-background px-3 py-2">
                      <div>
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">{check.id}</div>
                        <div className="font-semibold">{check.title}</div>
                      </div>
                      <Badge variant={statusToBadgeVariant(check.status)}>{check.status}</Badge>
                    </div>
                  ))}
                </div>
                {replicationChecks && replicationChecks.length > 6 && (
                  <p className="text-xs text-muted-foreground">Showing first 6 replication checks; view full report on the backend payload.</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Replication results will appear after a successful evaluation training session.</p>
            )}
          </div>
        </aside>
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
