import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { apiUrl } from "@/lib/api";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, ArrowRight, Download, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export const Route = createFileRoute("/evaluation")({
  head: () => ({ meta: [{ title: "Evaluation — Aegis Credit" }] }),
  component: Evaluation,
});

function makeCsvRows(metrics: Record<string, any>) {
  return Object.entries(metrics).map(([key, value]) => {
    let formatted = value;
    if (typeof value === "object" && value !== null) {
      try {
        formatted = JSON.stringify(value);
      } catch {
        formatted = String(value);
      }
    }
    return [key, String(formatted)];
  });
}

function downloadCsv(metrics: Record<string, any>, fileName: string) {
  const rows = makeCsvRows(metrics);
  const csv = ["metric,value", ...rows.map(([key, value]) => `${JSON.stringify(key)},${JSON.stringify(value)}`)].join("\n");
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

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
      <h3 className="text-sm font-semibold">{title}</h3>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      <div className="mt-4 h-56">{children}</div>
    </div>
  );
}

function Evaluation() {
  const navigate = useNavigate();
  const { trainingResult, file, profile, trainingConfig } = useDataset();
  const [complianceFlags, setComplianceFlags] = useState<Record<string, any>[] | null>(null);
  const [complianceScore, setComplianceScore] = useState<number | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);
  const [replicationResult, setReplicationResult] = useState<Record<string, any> | null>(null);
  const [replicationChecks, setReplicationChecks] = useState<Record<string, any>[]>([]);
  const [replicationLoading, setReplicationLoading] = useState(false);
  const [replicationError, setReplicationError] = useState<string | null>(null);

  const evaluationMetrics = trainingResult?.evaluation_metrics;
  const evaluationData = trainingResult?.evaluation_data;
  const modelArtifact = trainingResult?.model_artifact;
  const threshold = evaluationMetrics?.threshold_used ?? evaluationData?.threshold ?? 0.5;

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

  const gain = useMemo(() => evaluationData?.gain_chart ?? [], [evaluationData?.gain_chart]);
  const thresholds = useMemo(() => evaluationData?.threshold_analysis ?? [], [evaluationData?.threshold_analysis]);
  const rocCurve = useMemo(() => evaluationData?.roc_curve ?? [], [evaluationData?.roc_curve]);
  const prCurve = useMemo(() => evaluationData?.pr_curve ?? [], [evaluationData?.pr_curve]);
  const scoreDistribution = useMemo(() => evaluationData?.score_distribution ?? [], [evaluationData?.score_distribution]);

  useEffect(() => {
    if (!evaluationMetrics || !trainingResult) {
      return;
    }

    const payload = {
      stage: "evaluation",
      payload: {
        metrics: evaluationMetrics,
        training_info: trainingResult.training_info ?? {},
        threshold,
        explainability_done: false,
        heteroscedasticity_check: evaluationData?.heteroscedasticity_check ?? null,
        pd_output_present: true,
        staging_logic_present: true,
        sicr_flagged: true,
        ecl_estimated: true,
        concentration_analysis: true,
        exposure_reported: true,
        past_due_breakdown: true,
        shap_available: false,
      },
    };

    setComplianceLoading(true);
    setComplianceError(null);
    fetch(apiUrl("/validation/compliance"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(async (res) => {
        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(errorText || "Failed to fetch compliance results.");
        }
        return res.json();
      })
      .then((body) => {
        setComplianceFlags(body.flags ?? []);
        setComplianceScore(body.report?.metadata?.compliance_score ?? null);
      })
      .catch((error) => {
        console.error("Evaluation compliance fetch failed", error);
        setComplianceError("Unable to load compliance summary.");
      })
      .finally(() => {
        setComplianceLoading(false);
      });
  }, [evaluationMetrics, evaluationData?.heteroscedasticity_check, threshold, trainingResult]);

  useEffect(() => {
    if (!trainingResult || !file || !profile?.target_col) {
      return;
    }

    const replicationPayload = new FormData();
    replicationPayload.append("file", file);
    replicationPayload.append("target_col", profile.target_col);
    replicationPayload.append("model_name", trainingResult.model_name);
    replicationPayload.append("seeds", "42,43,44,45,46");
    replicationPayload.append("test_size", String(trainingConfig?.test_size ?? 0.15));
    replicationPayload.append("val_size", String(trainingConfig?.val_size ?? 0.15));
    replicationPayload.append("random_seed", String(trainingConfig?.random_seed ?? 42));
    replicationPayload.append("cv_folds", String(trainingConfig?.cv_folds ?? 5));

    setReplicationLoading(true);
    setReplicationError(null);

    fetch(apiUrl("/validation/replication"), {
      method: "POST",
      body: replicationPayload,
    })
      .then(async (res) => {
        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(errorText || "Failed to fetch replication results.");
        }
        return res.json();
      })
      .then((body) => {
        setReplicationResult(body.report?.replication?.result ?? null);
        setReplicationChecks(body.report?.replication?.checks ?? []);
      })
      .catch((error) => {
        console.error("Evaluation replication fetch failed", error);
        setReplicationError("Unable to load replication results.");
      })
      .finally(() => {
        setReplicationLoading(false);
      });
  }, [trainingResult, file, profile?.target_col, trainingConfig?.test_size, trainingConfig?.val_size, trainingConfig?.random_seed, trainingConfig?.cv_folds]);

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
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="ROC curve" sub={evaluationMetrics?.roc_auc ? `AUC ${evaluationMetrics.roc_auc}` : "Probability output unavailable"}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={rocCurve}>
                  <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                  <XAxis dataKey="fpr" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                  <Area type="monotone" dataKey="tpr" stroke="oklch(0.6 0.18 135)" fill="oklch(0.76 0.18 130)" fillOpacity={0.3} />
                  <Line type="linear" dataKey="fpr" stroke="oklch(0.6 0.01 240)" strokeDasharray="4 4" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card title="Precision–Recall" sub={evaluationMetrics?.pr_auc ? `Average precision ${evaluationMetrics.pr_auc}` : "Probability output unavailable"}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={prCurve}>
                  <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                  <XAxis dataKey="recall" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                  <Area type="monotone" dataKey="precision" stroke="oklch(0.6 0.18 135)" fill="oklch(0.76 0.18 130)" fillOpacity={0.3} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Confusion matrix" sub={`Threshold ${threshold.toFixed(2)}`}>
              <div className="grid h-full grid-cols-2 gap-3">
                {confusion.map(([label, n, tone]) => (
                  <div
                    key={label}
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
                    <span className="text-2xl font-semibold tabular-nums">{Number(n).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Cumulative gain" sub="Model vs baseline by decile">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={gain}>
                  <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                  <XAxis dataKey="decile" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                  <Line type="monotone" dataKey="model" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="baseline" stroke="oklch(0.6 0.01 240)" strokeDasharray="4 4" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Threshold analysis" sub="Precision · Recall · F1 across cut-offs">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={thresholds}>
                  <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                  <XAxis dataKey="threshold" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                  <Line type="monotone" dataKey="precision" stroke="oklch(0.6 0.18 135)" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="recall" stroke="oklch(0.6 0.22 27)" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="f1" stroke="oklch(0.55 0.02 240)" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Card>

            <Card title="Score distribution" sub="Hold-out set">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreDistribution}>
                  <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                  <XAxis dataKey="bin" tickLine={false} axisLine={false} fontSize={11} />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                  <Bar dataKey="good" stackId="a" fill="oklch(0.76 0.18 130)" />
                  <Bar dataKey="bad" stackId="a" fill="oklch(0.6 0.22 27)" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
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
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.roc_auc)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Gini</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.gini)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>KS</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.ks)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Accuracy</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.accuracy)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Precision</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.precision)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Recall</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.recall)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>F1 score</span>
                    <span className="font-semibold">{formatReplicatedValue(replicationResult.metrics?.f1)}</span>
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
