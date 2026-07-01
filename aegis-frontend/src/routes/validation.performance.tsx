import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight } from "lucide-react";
import { rocCurve, prCurve, scoreDistribution } from "@/lib/mock-data";
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar,
} from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/validation/performance")({
  head: () => ({ meta: [{ title: "Performance Validation — Aegis Credit" }] }),
  component: Performance,
});

const metrics = [
  { label: "ROC-AUC",   value: "0.873" },
  { label: "Gini",      value: "0.746" },
  { label: "KS",        value: "0.612" },
  { label: "Accuracy",  value: "0.901" },
  { label: "Precision", value: "0.768" },
  { label: "Recall",    value: "0.812" },
  { label: "F1 Score",  value: "0.789" },
  { label: "F2 Score",  value: "0.803" },
  { label: "Brier",     value: "0.071" },
  { label: "Log loss",  value: "0.214" },
];

const confusion = [
  ["True Negative", 14_812, "primary"],
  ["False Positive", 1_204, "warning"],
  ["False Negative", 612, "destructive"],
  ["True Positive", 2_938, "primary"],
] as const;

const thresholds = Array.from({ length: 21 }, (_, i) => {
  const t = i / 20;
  const p = +(0.4 + 0.5 * t).toFixed(3);
  const r = +(0.98 - 0.85 * t).toFixed(3);
  return { threshold: t, precision: p, recall: r, f1: +((2 * p * r) / (p + r)).toFixed(3) };
});

const calibration = Array.from({ length: 10 }, (_, i) => {
  const pred = (i + 0.5) / 10;
  return { pred: +pred.toFixed(2), actual: +Math.min(1, pred + (Math.sin(i) * 0.03)).toFixed(3), perfect: +pred.toFixed(2) };
});

function Performance() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 5 — Performance Testing"
        description="Comprehensive performance evaluation on the independent validation hold-out set before stress testing and regulatory review."
      />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-xl border border-border bg-card p-4 shadow-elegant">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{m.label}</div>
            <div className="mt-2 text-xl font-semibold tracking-tight tabular-nums">{m.value}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="ROC curve" sub="AUC 0.873">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rocCurve}>
              <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
              <XAxis dataKey="fpr" tickLine={false} axisLine={false} fontSize={11} />
              <YAxis tickLine={false} axisLine={false} fontSize={11} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
              <Area type="monotone" dataKey="tpr" stroke="oklch(0.6 0.18 135)" fill="oklch(0.76 0.18 130)" fillOpacity={0.3} />
              <Line type="linear" dataKey="diagonal" stroke="oklch(0.6 0.01 240)" strokeDasharray="4 4" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Precision–Recall" sub="Average precision 0.81">
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

        <Card title="Confusion matrix" sub="Threshold 0.50">
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
                <span className="text-2xl font-semibold tabular-nums">{n.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Card>

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

        <Card title="Calibration" sub="Predicted vs observed default rate">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={calibration}>
              <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
              <XAxis dataKey="pred" tickLine={false} axisLine={false} fontSize={11} />
              <YAxis tickLine={false} axisLine={false} fontSize={11} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
              <Line type="monotone" dataKey="actual" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} />
              <Line type="linear" dataKey="perfect" stroke="oklch(0.6 0.01 240)" strokeDasharray="4 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Score distribution" sub="Hold-out set · KS = 0.612">
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
      </section>

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
