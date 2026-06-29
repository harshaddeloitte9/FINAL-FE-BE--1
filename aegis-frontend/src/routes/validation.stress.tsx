import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, Legend } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/validation/stress")({
  head: () => ({ meta: [{ title: "Stress & Backtesting — Aegis Credit" }] }),
  component: Stress,
});

const scenarios = [
  { name: "Base",      pd: 4.7, ecl: 100, color: "oklch(0.76 0.18 130)" },
  { name: "Adverse",   pd: 7.2, ecl: 152 },
  { name: "Severe",    pd: 11.4, ecl: 241 },
  { name: "Reverse",   pd: 14.8, ecl: 312 },
];

const stability = Array.from({ length: 12 }, (_, i) => ({
  month: `M${i + 1}`,
  auc: +(0.875 - Math.abs(Math.sin(i / 3)) * 0.02).toFixed(3),
  psi: +(0.04 + Math.abs(Math.sin(i / 4)) * 0.06).toFixed(3),
}));

const backtest = Array.from({ length: 12 }, (_, i) => ({
  month: `M${i + 1}`,
  predicted: +(4.5 + Math.sin(i / 2) * 0.4).toFixed(2),
  actual:    +(4.6 + Math.sin(i / 2) * 0.5 + (i > 8 ? 0.3 : 0)).toFixed(2),
}));

function Stress() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Sensitivity, Stress Testing & Backtesting"
        description="Scenario simulations, model stability over time, and back-tested predictions vs realised outcomes."
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Stress scenarios — ECL multiplier</h3>
          <p className="text-xs text-muted-foreground">Baseline ECL indexed to 100</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scenarios}>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Bar dataKey="ecl" fill="oklch(0.6 0.18 135)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Stability over time</h3>
          <p className="text-xs text-muted-foreground">Rolling AUC and PSI</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stability}>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis yAxisId="l" tickLine={false} axisLine={false} fontSize={11} domain={[0.8, 0.9]} />
                <YAxis yAxisId="r" orientation="right" tickLine={false} axisLine={false} fontSize={11} domain={[0, 0.2]} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="l" type="monotone" dataKey="auc" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} dot={false} />
                <Line yAxisId="r" type="monotone" dataKey="psi" stroke="oklch(0.6 0.22 27)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h3 className="text-sm font-semibold">Backtesting — predicted vs actual default rate</h3>
        <p className="text-xs text-muted-foreground">Trailing 12 months · binomial test p = 0.18 (no rejection)</p>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={backtest}>
              <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
              <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={11} />
              <YAxis tickLine={false} axisLine={false} fontSize={11} unit="%" />
              <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="predicted" stroke="oklch(0.6 0.18 135)" strokeWidth={2.5} />
              <Line type="monotone" dataKey="actual" stroke="oklch(0.6 0.22 27)" strokeWidth={2.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          ["Sensitivity", "±10% feature perturbation — output drift &lt; 3%", "PASS"],
          ["Stress sims", "Severe scenario doubles ECL — within tolerance", "PASS"],
          ["Backtest", "12-month coverage; binomial test not rejected", "PASS"],
        ].map(([t, d, s]) => (
          <div key={t} className="rounded-xl border border-border bg-card p-5 shadow-elegant">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{t}</div>
            <div className="mt-2 text-sm" dangerouslySetInnerHTML={{ __html: d }} />
            <span className="mt-3 inline-flex rounded-full border border-primary/30 bg-primary-soft px-2 py-0.5 text-[10px] font-semibold">
              {s}
            </span>
          </div>
        ))}
      </section>
    </div>
  );
}
