import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, useMemo } from "react";
import { PageHeader } from "@/components/app-shell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowRight } from "lucide-react";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/validation/regulatory")({
  head: () => ({ meta: [{ title: "Stage 7 — Regulatory Review — Aegis Credit" }] }),
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
};

type Stage7Response = {
  checks: ThresholdCheck[];
  summary: { total: number; pass: number; warn: number; fail: number };
};

const STATUS_STYLES: Record<string, { border: string; bg: string; badge: string; icon: string }> = {
  PASS: { border: "border-emerald-500/40", bg: "bg-emerald-500/10", badge: "bg-emerald-500 text-emerald-950", icon: "✅" },
  WARN: { border: "border-amber-500/40", bg: "bg-amber-500/10", badge: "bg-amber-500 text-amber-950", icon: "🟡" },
  FAIL: { border: "border-red-500/40", bg: "bg-red-500/10", badge: "bg-red-500 text-red-950", icon: "🔴" },
  PENDING: { border: "border-border", bg: "bg-muted/30", badge: "bg-muted text-foreground", icon: "⏭️" },
};

const SEVERITY_STYLES: Record<string, string> = {
  HIGH: "bg-red-500 text-red-950",
  MEDIUM: "bg-amber-500 text-amber-950",
  LOW: "bg-emerald-500 text-emerald-950",
};

function statusStyle(status: string | undefined) {
  return STATUS_STYLES[status ?? ""] ?? { border: "border-border", bg: "bg-card", badge: "bg-muted text-foreground", icon: "⚪" };
}

function SummaryTile({ label, value, tone }: { label: string; value: number; tone: "neutral" | "pass" | "warn" | "fail" }) {
  const classes =
    tone === "pass"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
      : tone === "warn"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-300"
      : tone === "fail"
      ? "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-300"
      : "border-border bg-background text-foreground";

  return (
    <div className={`rounded-xl border p-4 ${classes}`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function ThresholdCheckCard({ check }: { check: ThresholdCheck }) {
  const s = statusStyle(check.status);
  const sevClasses = SEVERITY_STYLES[check.severity?.toUpperCase()] ?? "bg-muted text-foreground";
  return (
    <div className={`min-w-0 rounded-r-lg border-l-4 ${s.border} ${s.bg} p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 break-words text-sm font-semibold text-foreground">
          {s.icon} <span className="text-muted-foreground">[{check.check_id}]</span> {check.title}{" "}
          <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${sevClasses}`}>
            {check.severity}
          </span>
        </div>
        <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold ${s.badge}`}>{check.status}</span>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        📋 {check.source} — {check.principle}
      </div>
      <div className="mt-2 text-sm text-foreground">
        📊 Observed: <code className="text-foreground/90">{check.observed}</code>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">📐 Threshold: {check.threshold}</div>
      {check.detail ? <div className="mt-2 text-sm text-muted-foreground">💡 {check.detail}</div> : null}
    </div>
  );
}

function Regulatory() {
  const { validationIntakeData, validationMddText, validationStage4Result, validationStage7Result, setValidationStage7Result } =
    useDataset();

  const [loading, setLoading] = useState(!validationStage7Result);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<Stage7Response | null>((validationStage7Result as Stage7Response | null) ?? null);

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

  const summary = data?.summary ?? { total: 0, pass: 0, warn: 0, fail: 0 };
  const progress = summary.total > 0 ? Math.round((summary.pass / summary.total) * 100) : 0;

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

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 7 — Regulatory Review"
        description="SS1/23 · SS11/13 · IFRS 9 · IFRS 7 — automated regulatory compliance checks and model explainability review."
      />

      {loading ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">Loading Stage 7 checks...</div>
      ) : error ? (
        <div className="rounded-xl border border-border bg-card p-6 text-destructive">Error loading Stage 7: {error}</div>
      ) : (
        <Tabs defaultValue="compliance" className="w-full">
          <TabsList>
            <TabsTrigger value="compliance">Regulatory Compliance</TabsTrigger>
            <TabsTrigger value="explainability">Explainability &amp; Fairness</TabsTrigger>
          </TabsList>

          <TabsContent value="compliance" className="space-y-6 pt-4">
            <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Regulatory Compliance Results (7.1–7.10)</h3>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <SummaryTile label="Total Checks" value={summary.total} tone="neutral" />
                <SummaryTile label="PASS" value={summary.pass} tone="pass" />
                <SummaryTile label="WARN" value={summary.warn} tone="warn" />
                <SummaryTile label="FAIL" value={summary.fail} tone="fail" />
              </div>
              <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
              </div>
            </section>

            <div className="mx-auto max-w-2xl space-y-3">
              {data?.checks && data.checks.length > 0 ? (
                data.checks.map((c) => <ThresholdCheckCard key={c.check_id} check={c} />)
              ) : (
                <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                  No regulatory compliance checks generated for this stage.
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="explainability" className="space-y-6 pt-4">
            <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">🔬 SHAP Feature Importance (from Stage 4 Replication)</h3>
              <p className="text-xs text-muted-foreground">
                Reuses the replicated model's feature importances computed in Stage 4 — no re-training here.
              </p>

              {stage4Available ? (
                <div className="mt-4 h-[420px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={featureImportance} layout="vertical" margin={{ left: 24 }}>
                      <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                      <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} />
                      <YAxis
                        type="category"
                        dataKey="Feature"
                        tickLine={false}
                        axisLine={false}
                        fontSize={11}
                        width={160}
                      />
                      <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                      <Bar dataKey="Importance" fill="oklch(0.6 0.18 280)" radius={[0, 6, 6, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-dashed border-border bg-background p-8 text-center text-sm text-muted-foreground">
                  Feature importances not available. Run Stage 4 Model Replication first to populate this chart.
                </div>
              )}
              <p className="mt-2 text-xs text-muted-foreground">Top 15 Feature Importances (Replicated Model)</p>
            </section>
          </TabsContent>
        </Tabs>
      )}

      <div className="text-right">
        <Link
          to="/validation/findings"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 8
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
