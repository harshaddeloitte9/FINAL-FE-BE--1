import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { featureImportance, shapWaterfall } from "@/lib/mock-data";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
import { TrendingUp, TrendingDown, ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/explainability")({
  head: () => ({ meta: [{ title: "Explainability — Aegis Credit" }] }),
  component: Explainability,
});

function Explainability() {
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      <PageHeader
        title="Explainability"
        description="Global SHAP attributions and a worked example for one obligor."
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">SHAP summary</h2>
          <p className="text-xs text-muted-foreground">Mean absolute attribution per feature</p>
          <div className="mt-4 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={featureImportance} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis type="category" dataKey="feature" tickLine={false} axisLine={false} fontSize={11} width={170} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Bar dataKey="value" fill="oklch(0.76 0.18 130)" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">Individual prediction · Obligor #44231</h2>
          <div className="mt-2 flex items-center gap-3 text-sm">
            <span className="rounded-full bg-destructive/10 px-2.5 py-1 text-xs font-semibold text-destructive">
              PD 31.6%
            </span>
            <span className="text-muted-foreground">Score 412 · Stage 2</span>
          </div>

          <div className="mt-5 space-y-2">
            {shapWaterfall.map((s) => {
              const positive = s.impact > 0;
              return (
                <div
                  key={s.feature}
                  className="flex items-center gap-3 rounded-lg border border-border bg-background p-3"
                >
                  <div
                    className={
                      "flex h-8 w-8 items-center justify-center rounded-md " +
                      (positive ? "bg-destructive/10 text-destructive" : "bg-primary-soft text-primary")
                    }
                  >
                    {positive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                  </div>
                  <div className="flex-1 text-sm">{s.feature}</div>
                  <div
                    className={
                      "text-sm font-semibold tabular-nums " +
                      (positive ? "text-destructive" : "text-primary")
                    }
                  >
                    {positive ? "+" : ""}
                    {s.impact.toFixed(2)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-primary/30 bg-primary-soft p-6">
        <h2 className="text-base font-semibold">Plain-language explanation</h2>
        <p className="mt-2 max-w-3xl text-sm text-foreground/90">
          This obligor's elevated probability of default is driven primarily by a high debt-to-income ratio
          (0.42) and credit utilization above 75%, partially offset by 9 years of stable employment and
          mid-tier income. The model would re-classify this loan as low-risk if utilization fell below 40%
          while DTI stayed under 0.35 — both within typical refinancing scenarios.
        </p>
      </section>

      <div className="flex gap-3 pt-4">
        <Button variant="outline" onClick={() => navigate({ to: "/evaluation" })} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Evaluation
        </Button>
        <Button onClick={() => navigate({ to: "/development" })} className="gap-2 ml-auto">
          Exit to Workspace
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
