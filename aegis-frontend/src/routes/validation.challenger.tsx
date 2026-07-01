import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight, Trophy } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/validation/challenger")({
  head: () => ({ meta: [{ title: "Replication & Benchmarking — Aegis Credit" }] }),
  component: Challenger,
});

const compare = [
  { metric: "AUC",        champion: 0.873, challenger: 0.869 },
  { metric: "KS",         champion: 0.612, challenger: 0.604 },
  { metric: "Gini",       champion: 0.746, challenger: 0.738 },
  { metric: "Recall",     champion: 0.812, challenger: 0.798 },
  { metric: "Precision",  champion: 0.768, challenger: 0.781 },
  { metric: "F1",         champion: 0.789, challenger: 0.789 },
];

const ranking = [
  { rank: 1, name: "XGBoost (Champion)",   auc: 0.873, ks: 0.612, gini: 0.746, status: "Selected" },
  { rank: 2, name: "LightGBM (Challenger)", auc: 0.869, ks: 0.604, gini: 0.738, status: "Approved benchmark" },
  { rank: 3, name: "Gradient Boosting",     auc: 0.864, ks: 0.599, gini: 0.728, status: "Benchmark" },
  { rank: 4, name: "Random Forest",         auc: 0.851, ks: 0.581, gini: 0.702, status: "Benchmark" },
  { rank: 5, name: "Logistic Regression",   auc: 0.812, ks: 0.541, gini: 0.624, status: "Baseline" },
];

function Challenger() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 4 — Replication & Benchmarking"
        description="Replicate developer outputs and benchmark the champion model against approved challengers."
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Champion reproduction</h3>
          <p className="mt-2 text-sm text-foreground/80">
            The developer's XGBoost champion was reproduced using submitted code and the validation dataset, then benchmarked against alternatives.
          </p>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={compare}>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                <XAxis dataKey="metric" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} domain={[0, 1]} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="champion" fill="oklch(0.76 0.18 130)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="challenger" fill="oklch(0.55 0.02 240)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-primary/30 bg-primary-soft p-6 shadow-elegant">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-primary" />
            <h3 className="text-sm font-semibold">Recommendation</h3>
          </div>
          <p className="mt-3 text-sm">
            Retain <span className="font-semibold">XGBoost</span> as champion. Differences against LightGBM
            challenger are within governance tolerance (ΔAUC = 0.004).
          </p>
          <ul className="mt-3 space-y-1.5 text-xs text-foreground/80">
            <li>· Calibrate quarterly on rolling 12-month window</li>
            <li>· Re-benchmark when ΔAUC &gt; 0.010 against any challenger</li>
            <li>· Maintain LightGBM as warm standby</li>
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card shadow-elegant">
        <div className="border-b border-border p-6">
          <h3 className="text-sm font-semibold">Model ranking</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-background text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-6 py-3 text-left">#</th>
                <th className="px-6 py-3 text-left">Model</th>
                <th className="px-6 py-3 text-right">AUC</th>
                <th className="px-6 py-3 text-right">KS</th>
                <th className="px-6 py-3 text-right">Gini</th>
                <th className="px-6 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ranking.map((r) => (
                <tr key={r.name} className={r.rank === 1 ? "bg-primary-soft/40" : ""}>
                  <td className="px-6 py-3 font-mono text-xs text-muted-foreground">{r.rank}</td>
                  <td className="px-6 py-3 font-medium">{r.name}</td>
                  <td className="px-6 py-3 text-right tabular-nums">{r.auc.toFixed(3)}</td>
                  <td className="px-6 py-3 text-right tabular-nums">{r.ks.toFixed(3)}</td>
                  <td className="px-6 py-3 text-right tabular-nums">{r.gini.toFixed(3)}</td>
                  <td className="px-6 py-3 text-xs">{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="text-right">
        <Link
          to="/validation/performance"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 5
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
