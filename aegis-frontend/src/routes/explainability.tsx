import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

type FeatureImportanceRow = {
  Feature: string;
  Importance: number;
};

type ShapInfo = {
  shap_available: boolean;
  shap_mean_abs?: Array<{ Feature: string; MeanAbsSHAP: number }>;
  sample_idx?: number;
  sample_reasoning?: string;
};

type ExplainabilityResponse = {
  feature_importance: FeatureImportanceRow[];
  shap: ShapInfo;
};

export const Route = createFileRoute("/explainability")({
  head: () => ({ meta: [{ title: "Explainability — Aegis Credit" }] }),
  component: Explainability,
});

function Explainability() {
  const navigate = useNavigate();
  const { profile, file, trainingResult } = useDataset();
  const [data, setData] = useState<ExplainabilityResponse | null>(null);

  const modelArtifact = trainingResult?.model_artifact ?? null;

  const targetColumn = profile?.target_col ??
    (Array.isArray(profile?.target_candidates) && profile.target_candidates.length > 0
      ? profile.target_candidates[0]
      : "loan_status");

  const hasEngine = Boolean(modelArtifact && file);

  // Transform backend SHAP mean-abs to match Streamlit: take top 15 by mean abs,
  // then sort ascending for vertical bar chart display (small -> large).
  const shapSummaryData = (data?.shap.shap_mean_abs ?? [])
    .slice()
    .sort((a, b) => (b.MeanAbsSHAP ?? 0) - (a.MeanAbsSHAP ?? 0))
    .slice(0, 15)
    .sort((a, b) => (a.MeanAbsSHAP ?? 0) - (b.MeanAbsSHAP ?? 0));

  const topShapDrivers = Array.isArray(data?.shap.sample_shap) ? data.shap.sample_shap : [];

  const formatValue = (value: unknown) => {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") {
      if (Math.abs(value) >= 1000) return Math.round(value).toString();
      return Number.isFinite(value) ? value.toFixed(4) : String(value);
    }
    return String(value);
  };

  const parseProbability = (text?: string): number | null => {
    if (!text) return null;
    const m = text.match(/([0-9]{1,3}(?:\.[0-9]+)?)%/);
    if (!m) return null;
    const num = Number(m[1]);
    if (Number.isNaN(num)) return null;
    return num / 100;
  };

  // Return the backend-generated reasoning with only markdown removed.
  // Do NOT rewrite or summarise content; preserve line order.
  const plainReasoning = (text?: string) => {
    if (!text) return "";
    // Remove common markdown tokens but preserve the textual content and newlines
    let t = text.replace(/\*\*/g, "").replace(/`/g, "").replace(/(^|\n)#+\s*/g, "$1");
    // Remove leading list markers but keep the list text
    t = t.replace(/(^|\n)\s*-\s*/g, "$1");
    return t;
  };

  const fetchExplainability = async () => {
    if (!hasEngine) {
      return;
    }

    const form = new FormData();
    form.append("model_artifact", modelArtifact!);
    form.append("file", file!);
    form.append("target_col", targetColumn);
    form.append("max_shap_samples", String(100));
    form.append("sample_idx", String(0));

    const response = await formUpload<ExplainabilityResponse>("/models/explain", form);
    setData(response);
  };

  useEffect(() => {
    if (hasEngine) {
      void fetchExplainability();
    }
  }, [hasEngine, modelArtifact, file]);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Explainability"
        description="Global feature attribution and obligor-level reasoning for the trained credit risk model."
      />

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="mb-4">
            <h2 className="text-base font-semibold">SHAP summary</h2>
            <p className="text-xs text-muted-foreground">Mean absolute SHAP attribution per feature</p>
          </div>

          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={shapSummaryData} layout="vertical" margin={{ left: 10, right: 10 }}>
                <CartesianGrid stroke="transparent" />
                <XAxis type="number" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="Feature" tickLine={false} axisLine={false} width={220} />
                <Tooltip formatter={(value: number) => value.toFixed(5)} />
                <Bar dataKey="MeanAbsSHAP" fill="#0f766e" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">Individual prediction</h2>
          <p className="text-xs text-muted-foreground">One obligor — model-level explanation</p>

          <div className="mt-4">
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${(() => {
                      const prob = parseProbability(data?.shap.sample_reasoning);
                      if (prob !== null && prob >= 0.5) return 'bg-destructive/10 text-destructive';
                      return 'bg-emerald-50 text-emerald-700';
                    })()}`}>
                      {(() => {
                        const prob = parseProbability(data?.shap.sample_reasoning);
                        return prob === null ? 'PD —' : `PD ${Math.round((prob ?? 0) * 1000) / 10}%`;
                      })()}
                    </span>
                    <div className="text-sm text-muted-foreground">
                      {(() => {
                        const features = data?.shap.sample_features ?? {} as Record<string, any>;
                        const scoreKey = Object.keys(features).find((k) => /score|credit_score|creditscore|score_/i.test(k));
                        const stageKey = Object.keys(features).find((k) => /stage/i.test(k));
                        const scoreVal = scoreKey ? formatValue(features[scoreKey]) : '—';
                        const stageVal = stageKey ? String(features[stageKey]) : '—';
                        return `${scoreVal} · Stage ${stageVal}`;
                      })()}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {topShapDrivers.map((d) => {
                  const shp = Number(d.SHAP ?? 0);
                  const positive = shp > 0;
                  const val = d.Value;
                  return (
                    <div key={String(d.Feature)} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-3">
                      <div className="text-sm">{d.Feature} = {formatValue(val)}</div>
                      <div className={`text-sm font-semibold tabular-nums ${positive ? 'text-destructive' : 'text-success'}`}>
                        {shp >= 0 ? '+' : ''}{shp.toFixed(5)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Plain-language explanation (green info card) */}
      <div>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div className="font-medium">Plain-language explanation</div>
          <div className="mt-2 text-sm text-foreground/90 whitespace-pre-line">
            {data?.shap.shap_available ? plainReasoning(data?.shap.sample_reasoning) : (
              "The model did not return SHAP reasoning for the selected sample. Use feature importance and model metrics to interpret overall risk drivers."
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 pt-4">
        <Button variant="outline" onClick={() => navigate({ to: "/evaluation" })} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Evaluation
        </Button>
        <div className="ml-auto" />
        <Button onClick={() => navigate({ to: "/development" })} className="gap-2">
          Exit to Workspace
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
