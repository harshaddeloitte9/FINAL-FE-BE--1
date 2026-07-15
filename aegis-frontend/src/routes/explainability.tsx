import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { AlertCircle, ArrowLeft, ArrowRight, Loader, Download, BarChart3, Microscope, Search, ClipboardList } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";

type FeatureImportanceRow = {
  Feature: string;
  Importance: number;
};

type SampleShapRow = {
  Feature: string;
  SHAP: number | null;
  Value: unknown;
};

type ShapInfo = {
  shap_available: boolean;
  shap_mean_abs?: Array<{ Feature: string; MeanAbsSHAP: number }>;
  sample_idx?: number;
  sample_reasoning?: string;
  sample_shap?: SampleShapRow[];
  sample_features?: Record<string, unknown>;
};

type ExplainabilityResponse = {
  feature_importance: FeatureImportanceRow[];
  shap: ShapInfo;
  summary?: string | null;
};

export const Route = createFileRoute("/explainability")({
  head: () => ({ meta: [{ title: "Explainability — Aegis Credit" }] }),
  component: Explainability,
});

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function base64ToBlob(base64: string, mime = "application/octet-stream"): Blob {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: mime });
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    if (Math.abs(value) >= 1000) return Math.round(value).toString();
    return Number.isFinite(value) ? value.toFixed(4) : String(value);
  }
  return String(value);
}

// Remove markdown tokens for plain-text rendering but preserve line order —
// do not rewrite or summarise the backend-generated content.
function plainMarkdown(text?: string | null) {
  if (!text) return "";
  let t = text.replace(/\*\*/g, "").replace(/`/g, "").replace(/(^|\n)#+\s*/g, "$1");
  t = t.replace(/(^|\n)\s*-\s*/g, "$1");
  return t;
}

function Explainability() {
  const navigate = useNavigate();
  const { profile, file, trainingResult, preprocessingResult, featureEngineeringResult } = useDataset();

  const modelArtifact = trainingResult?.model_artifact ?? null;
  const trainingConfig = trainingResult?.training_config ?? {};
  const hasEngine = Boolean(modelArtifact && file);

  const targetColumn = profile?.target_col ??
    (Array.isArray(profile?.target_candidates) && profile.target_candidates.length > 0
      ? profile.target_candidates[0]
      : "loan_status");

  const [data, setData] = useState<ExplainabilityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [topN, setTopN] = useState(15);
  const [shapSamples, setShapSamples] = useState(150);
  const [shapComputed, setShapComputed] = useState(false);
  const [shapLoading, setShapLoading] = useState(false);
  const [shapError, setShapError] = useState<string | null>(null);
  const [sampleIdx, setSampleIdx] = useState(0);

  const explainParams = () => {
    const form = new FormData();
    // Sent as a file part (not a plain text field): the base64-encoded
    // pipeline can be several MB, and multipart parsers cap plain form
    // fields much lower than file parts, which was causing 400s here.
    const modelArtifactBlob = new Blob([modelArtifact!], { type: "text/plain" });
    form.append("model_artifact", modelArtifactBlob, "model_artifact.b64");
    form.append("file", file!);
    form.append("target_col", targetColumn);
    form.append("use_feature_engineering", String(Boolean(trainingConfig.use_feature_engineering)));
    form.append("test_size", String(trainingConfig.test_size ?? 0.15));
    form.append("val_size", String(trainingConfig.val_size ?? 0.15));
    form.append("random_seed", String(trainingConfig.random_seed ?? 42));
    form.append("task_type", trainingResult?.task_type ?? "binary");
    if (trainingResult?.evaluation_metrics) {
      form.append("metrics", JSON.stringify(trainingResult.evaluation_metrics));
    }
    return form;
  };

  // Initial load: Feature Importance only (fast, no SHAP) — matches the old
  // app's tab behaviour where Feature Importance renders immediately and
  // SHAP is only computed on an explicit button click.
  const fetchFeatureImportance = async () => {
    if (!hasEngine) return;
    try {
      setLoading(true);
      setError(null);
      const form = explainParams();
      form.append("compute_shap", "false");
      const response = await formUpload<ExplainabilityResponse>("/models/explain", form);
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load explainability data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (hasEngine) void fetchFeatureImportance();
    setShapComputed(false);
    setSampleIdx(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasEngine, modelArtifact, file]);

  const computeShap = async () => {
    if (!hasEngine) return;
    try {
      setShapLoading(true);
      setShapError(null);
      const form = explainParams();
      form.append("compute_shap", "true");
      form.append("max_shap_samples", String(shapSamples));
      form.append("sample_idx", String(sampleIdx));
      const response = await formUpload<ExplainabilityResponse>("/models/explain", form);
      setData(response);
      if (response.shap.shap_available) {
        setShapComputed(true);
      } else {
        setShapError("SHAP computation failed or not supported for this model. Try the Feature Importance tab.");
      }
    } catch (err) {
      setShapError(err instanceof Error ? err.message : "Failed to compute SHAP values");
    } finally {
      setShapLoading(false);
    }
  };

  // Re-fetch reasoning when the reviewer picks a different sample, once SHAP
  // is already computed — cheap relative to a full SHAP recompute.
  const changeSample = async (idx: number) => {
    setSampleIdx(idx);
    if (!shapComputed || !hasEngine) return;
    try {
      const form = explainParams();
      form.append("compute_shap", "true");
      form.append("max_shap_samples", String(shapSamples));
      form.append("sample_idx", String(idx));
      const response = await formUpload<ExplainabilityResponse>("/models/explain", form);
      setData(response);
    } catch (err) {
      setShapError(err instanceof Error ? err.message : "Failed to load prediction reasoning");
    }
  };

  const importanceRows = data?.feature_importance ?? [];
  const maxTopN = Math.max(5, importanceRows.length);
  const chartRows = useMemo(
    () => [...importanceRows].slice(0, topN).sort((a, b) => a.Importance - b.Importance),
    [importanceRows, topN],
  );

  const shapSummaryRows = useMemo(
    () =>
      (data?.shap.shap_mean_abs ?? [])
        .slice()
        .sort((a, b) => (b.MeanAbsSHAP ?? 0) - (a.MeanAbsSHAP ?? 0))
        .slice(0, 15)
        .sort((a, b) => (a.MeanAbsSHAP ?? 0) - (b.MeanAbsSHAP ?? 0)),
    [data],
  );

  const sampleShapRows = data?.shap.sample_shap ?? [];
  const sampleCount = sampleShapRows.length > 0
    ? Math.max(sampleShapRows.length, sampleIdx + 1)
    : 0;

  const downloadModel = () => {
    if (!modelArtifact) return;
    downloadBlob(base64ToBlob(modelArtifact), "final_credit_risk_model.pkl");
  };

  const downloadProcessedDataset = () => {
    const csv = preprocessingResult?.processed_dataset_csv ?? featureEngineeringResult?.x_engineered_csv;
    if (!csv) return;
    downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8" }), "processed_dataset.csv");
  };

  const downloadFeatureImportanceCsv = () => {
    if (importanceRows.length === 0) return;
    const header = "Feature,Importance";
    const rows = importanceRows.map((r) => `${r.Feature},${r.Importance}`);
    downloadBlob(new Blob([[header, ...rows].join("\n")], { type: "text/csv;charset=utf-8" }), "feature_importance.csv");
  };

  if (!hasEngine) {
    return (
      <div className="space-y-8">
        <PageHeader title="Model Explainability" description="Feature importance, SHAP values, and individual prediction reasoning." />
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600" />
            <div>
              <div className="font-semibold text-amber-900">No trained model</div>
              <div className="text-sm text-amber-800">Complete model training first, then return here to explain the model.</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title="💡 Model Explainability" description="Feature importance, SHAP values, and individual prediction reasoning." />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>
      )}

      <Tabs defaultValue="importance" className="w-full">
        <TabsList>
          <TabsTrigger value="importance" className="gap-2"><BarChart3 className="h-4 w-4" />Feature Importance</TabsTrigger>
          <TabsTrigger value="shap" className="gap-2"><Microscope className="h-4 w-4" />SHAP Analysis</TabsTrigger>
          <TabsTrigger value="reasoning" className="gap-2"><Search className="h-4 w-4" />Prediction Reasoning</TabsTrigger>
          <TabsTrigger value="summary" className="gap-2"><ClipboardList className="h-4 w-4" />Summary</TabsTrigger>
        </TabsList>

        {/* ── Feature Importance ── */}
        <TabsContent value="importance" className="space-y-4 pt-4">
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h2 className="text-base font-semibold">📊 Feature Importance</h2>
            {loading ? (
              <div className="mt-6 flex items-center gap-3 text-sm text-muted-foreground">
                <Loader className="h-4 w-4 animate-spin" />
                Extracting feature importance with real column names...
              </div>
            ) : importanceRows.length > 0 ? (
              <>
                <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                  ✅ Extracted importance for {importanceRows.length} features with real column names.
                </div>
                <div className="mt-4 max-w-md">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Show top N features</span>
                    <span className="font-semibold text-foreground">{topN}</span>
                  </div>
                  <Slider
                    min={5}
                    max={maxTopN}
                    step={1}
                    value={[topN]}
                    onValueChange={(v) => setTopN(v[0])}
                    className="mt-2"
                  />
                </div>
                <div className="mt-6 h-96">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartRows} layout="vertical" margin={{ left: 160, right: 30 }}>
                      <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tickLine={false} axisLine={false} fontSize={10} />
                      <YAxis type="category" dataKey="Feature" tickLine={false} axisLine={false} fontSize={9} width={155} />
                      <Tooltip formatter={(value: number) => value.toFixed(4)} />
                      <Bar dataKey="Importance" fill="oklch(0.6 0.18 275)" radius={[0, 6, 6, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-6 overflow-x-auto">
                  <table className="min-w-full border-collapse text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                        <th className="border-b border-border px-3 py-2">Feature</th>
                        <th className="border-b border-border px-3 py-2">Importance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importanceRows.slice(0, topN + 5).map((row) => (
                        <tr key={row.Feature} className="odd:bg-background">
                          <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.Feature}</td>
                          <td className="border-b border-border px-3 py-2 text-xs">{row.Importance.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">Feature importance not available for this model type.</p>
            )}
          </section>
        </TabsContent>

        {/* ── SHAP Analysis ── */}
        <TabsContent value="shap" className="space-y-4 pt-4">
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h2 className="text-base font-semibold">🔬 SHAP Values</h2>
            <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
              SHAP (SHapley Additive exPlanations) shows each feature's contribution to each prediction using real feature names.
            </div>

            <div className="mt-4 max-w-md">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Samples for SHAP analysis</span>
                <span className="font-semibold text-foreground">{shapSamples}</span>
              </div>
              <Slider
                min={50}
                max={300}
                step={50}
                value={[shapSamples]}
                onValueChange={(v) => setShapSamples(v[0])}
                className="mt-2"
              />
            </div>

            <Button onClick={computeShap} disabled={shapLoading} className="mt-4 w-full gap-2">
              {shapLoading ? <Loader className="h-4 w-4 animate-spin" /> : null}
              ▶ Compute SHAP Values
            </Button>

            {shapError && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{shapError}</div>
            )}

            {shapComputed && shapSummaryRows.length > 0 && (
              <div className="mt-6">
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                  ✅ SHAP values computed for {shapSummaryRows.length >= 15 ? "15+" : shapSummaryRows.length} features!
                </div>
                <div className="mt-4 h-96">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapSummaryRows} layout="vertical" margin={{ left: 160, right: 30 }}>
                      <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tickLine={false} axisLine={false} fontSize={10} />
                      <YAxis type="category" dataKey="Feature" tickLine={false} axisLine={false} fontSize={9} width={155} />
                      <Tooltip formatter={(value: number) => value.toFixed(5)} />
                      <Bar dataKey="MeanAbsSHAP" fill="oklch(0.6 0.2 25)" radius={[0, 6, 6, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </section>
        </TabsContent>

        {/* ── Prediction Reasoning ── */}
        <TabsContent value="reasoning" className="space-y-4 pt-4">
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h2 className="text-base font-semibold">🔍 Individual Prediction Reasoning</h2>
            <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
              Inspect exactly why a specific customer was classified as risky or safe — with real feature names.
            </div>

            {!shapComputed ? (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Please compute SHAP values first (in the SHAP Analysis tab).
              </div>
            ) : (
              <>
                <div className="mt-4 max-w-xs">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Customer index (row number)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={Math.max(0, sampleCount - 1)}
                    value={sampleIdx}
                    onChange={(e) => void changeSample(Math.max(0, Number(e.target.value)))}
                    className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  />
                </div>

                {data?.shap.sample_reasoning && (
                  <div className="mt-4 whitespace-pre-line rounded-lg border border-border bg-background p-4 text-sm">
                    {plainMarkdown(data.shap.sample_reasoning)}
                  </div>
                )}

                {sampleShapRows.length > 0 && (
                  <div className="mt-6 h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={[...sampleShapRows].slice(0, 12).reverse().map((r) => ({
                          Label: `${r.Feature} = ${formatValue(r.Value)}`,
                          SHAP: r.SHAP ?? 0,
                        }))}
                        layout="vertical"
                        margin={{ left: 220, right: 30 }}
                      >
                        <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" tickLine={false} axisLine={false} fontSize={10} />
                        <YAxis type="category" dataKey="Label" tickLine={false} axisLine={false} fontSize={9} width={215} />
                        <Tooltip formatter={(value: number) => value.toFixed(5)} />
                        <Bar dataKey="SHAP" radius={[0, 6, 6, 0]}>
                          {[...sampleShapRows].slice(0, 12).reverse().map((r, i) => (
                            <Cell key={i} fill={(r.SHAP ?? 0) < 0 ? "oklch(0.7 0.15 150)" : "oklch(0.6 0.2 25)"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {Object.keys(data?.shap.sample_features ?? {}).length > 0 && (
                  <details className="mt-6">
                    <summary className="cursor-pointer text-sm font-semibold text-foreground">
                      🔎 Raw Feature Values for This Customer
                    </summary>
                    <div className="mt-3 overflow-x-auto">
                      <table className="min-w-full border-collapse text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                            <th className="border-b border-border px-3 py-2">Feature</th>
                            <th className="border-b border-border px-3 py-2">Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(data?.shap.sample_features ?? {}).map(([feat, val]) => (
                            <tr key={feat} className="odd:bg-background">
                              <td className="border-b border-border px-3 py-2 font-mono text-xs">{feat}</td>
                              <td className="border-b border-border px-3 py-2 text-xs">{formatValue(val)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                )}
              </>
            )}
          </section>
        </TabsContent>

        {/* ── Summary ── */}
        <TabsContent value="summary" className="space-y-4 pt-4">
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            {data?.summary ? (
              <div className="whitespace-pre-line text-sm text-foreground">{plainMarkdown(data.summary)}</div>
            ) : (
              <p className="text-sm text-muted-foreground">Model performance summary is not available yet.</p>
            )}

            <div className="mt-8 border-t border-border pt-6">
              <h3 className="text-sm font-semibold">💾 Final Exports</h3>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Button variant="outline" onClick={downloadModel} disabled={!modelArtifact} className="gap-2">
                  <Download className="h-4 w-4" />
                  Download Trained Model (.pkl)
                </Button>
                <Button
                  variant="outline"
                  onClick={downloadProcessedDataset}
                  disabled={!preprocessingResult?.processed_dataset_csv && !featureEngineeringResult?.x_engineered_csv}
                  className="gap-2"
                >
                  <Download className="h-4 w-4" />
                  Download processed_dataset.csv
                </Button>
                <Button
                  variant="outline"
                  onClick={downloadFeatureImportanceCsv}
                  disabled={importanceRows.length === 0}
                  className="gap-2"
                >
                  <Download className="h-4 w-4" />
                  Download feature_importance.csv
                </Button>
              </div>
            </div>
          </section>
        </TabsContent>
      </Tabs>

      <div className="flex flex-wrap gap-3 pt-2">
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
