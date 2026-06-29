import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { KpiCard } from "@/components/kpi-card";
import { kpis, pipeline, rocCurve, scoreDistribution } from "@/lib/mock-data";
import { Check, Loader2, Circle, Download, Play } from "lucide-react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/development")({
  head: () => ({
    meta: [
      { title: "Model Development — Aegis Credit" },
      { name: "description", content: "Build, train, evaluate, and explain credit risk models." },
    ],
  }),
  component: DevelopmentDashboard,
});

function DevelopmentDashboard() {
  const devPipeline = pipeline.filter((p) => p.key !== "regulatory");
  return (
    <div className="space-y-8">
      <PageHeader
        title="Model Development"
        description="End-to-end workflow for building, training, evaluating, and explaining credit risk models."
        actions={
          <>
            <button className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:border-primary/40">
              <Download className="h-4 w-4" /> Export report
            </button>
            <button className="inline-flex items-center gap-2 rounded-lg gradient-primary px-3 py-2 text-sm font-semibold text-primary-foreground shadow-elegant">
              <Play className="h-4 w-4" /> Run pipeline
            </button>
          </>
        }
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.slice(0, 4).map((k) => (
          <KpiCard key={k.label} {...k} />
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold">ROC curve · XGBoost champion</h2>
              <p className="text-xs text-muted-foreground">AUC 0.873 · validated on hold-out set</p>
            </div>
            <span className="rounded-full bg-primary-soft px-2.5 py-1 text-[11px] font-medium text-foreground">
              +0.012 vs prior
            </span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={rocCurve} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="rocFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="oklch(0.76 0.18 130)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="oklch(0.76 0.18 130)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                <XAxis dataKey="fpr" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Area type="monotone" dataKey="tpr" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} fill="url(#rocFill)" />
                <Line type="linear" dataKey="diagonal" stroke="oklch(0.6 0.015 240)" strokeDasharray="4 4" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="mb-4">
            <h2 className="text-base font-semibold">Development pipeline</h2>
            <p className="text-xs text-muted-foreground">{devPipeline.filter(s => s.status === "done").length} of {devPipeline.length} stages complete</p>
          </div>
          <ol className="relative space-y-3 border-l border-border pl-5">
            {devPipeline.map((s) => (
              <li key={s.key} className="relative">
                <span
                  className={
                    "absolute -left-[26px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 " +
                    (s.status === "done"
                      ? "border-primary bg-primary text-primary-foreground"
                      : s.status === "active"
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-border bg-background text-muted-foreground")
                  }
                >
                  {s.status === "done" ? <Check className="h-3 w-3" /> : s.status === "active" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Circle className="h-2 w-2" />}
                </span>
                <div className="flex items-center justify-between">
                  <span className={"text-sm " + (s.status === "pending" ? "text-muted-foreground" : "font-medium")}>
                    {s.label}
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {s.status === "done" ? "Done" : s.status === "active" ? "In progress" : "Pending"}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Score distribution</h2>
            <p className="text-xs text-muted-foreground">Good vs Bad obligor separation</p>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-primary" /> Good</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-destructive/80" /> Bad</span>
          </div>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={scoreDistribution} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
              <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
              <XAxis dataKey="bin" tickLine={false} axisLine={false} fontSize={11} />
              <YAxis tickLine={false} axisLine={false} fontSize={11} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
              <Area type="monotone" dataKey="good" stroke="oklch(0.6 0.18 135)" fill="oklch(0.76 0.18 130)" fillOpacity={0.35} />
              <Area type="monotone" dataKey="bad" stroke="oklch(0.6 0.22 27)" fill="oklch(0.6 0.22 27)" fillOpacity={0.25} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
