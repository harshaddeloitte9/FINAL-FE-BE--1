import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/models")({
  head: () => ({ meta: [{ title: "Model Selection — Aegis Credit" }] }),
  component: ModelSelection,
});

interface ModelRecommendation {
  name: string;
  score: number;
  description: string;
  why: string;
  best_for?: string[];
  icon?: string;
}

interface ModelCard extends ModelRecommendation {
  selected?: boolean;
}

function ModelSelection() {
  const { profile, file, recommendations, setRecommendations, setSelectedModel, selectedModel, compareModels, setCompareModels } = useDataset();
  const [trainingStats, setTrainingStats] = useState<{train_n: number; train_features: number; imbalance_ratio: number} | null>(null);
  const [recommendationTaskType, setRecommendationTaskType] = useState<string | null>(null);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchRef = useRef(false);

  // Compute dataset summary metrics
  const datasetSummary = useMemo(() => {
    // Prefer training stats returned by the backend (train split after FE)
    if (trainingStats) {
      return { sampleCount: trainingStats.train_n, featureCount: trainingStats.train_features, imbalanceRatio: trainingStats.imbalance_ratio };
    }
    if (!profile) return null;
    const shape = profile.shape ?? [0, 0];
    const sampleCount = shape[0] ?? 0;
    const featureCount = shape[1] ?? 0;
    let imbalanceRatio = 1.0;
    
    if (profile.class_distribution && typeof profile.class_distribution === "object") {
      const values = Object.values(profile.class_distribution) as number[];
      if (values.length >= 2) {
        const sorted = values.sort((a, b) => b - a);
        imbalanceRatio = sorted[0] / (sorted[1] || 1);
      }
    }
    
    return { sampleCount, featureCount, imbalanceRatio };
  }, [profile, trainingStats]);

  const transformedModels = useMemo(() => {
    if (!recommendations || !Array.isArray(recommendations) || recommendations.length === 0) return [];
    return recommendations.map((rec, idx) => ({
      ...rec,
      selected: rec.name === selectedModel?.name || (!selectedModel && idx === 0),
    }));
  }, [recommendations, selectedModel]);

  useEffect(() => {
    if (!profile || !file) return;
    // Reset guard when dataset changes so we fetch for new dataset
    fetchRef.current = false;
    if (recommendations && recommendations.length > 0) return; // already loaded
    if (fetchRef.current) return; // already in-flight or fetched

    let isMounted = true;
    const loadRecommendations = async () => {
      setLoading(true);
      setError(null);

      try {
        const form = new FormData();
        form.append("file", file);
        form.append("target_col", profile.target_col || "loan_status");

        console.log("Models: POST /models/recommend", { target_col: profile.target_col });
        const response = await formUpload("/models/recommend", form);
        console.log("Models: response", response);
        if (!isMounted) return;
        // Use backend-provided training stats when available
        if (response?.training) {
          setTrainingStats(response.training as any);
        }
            if (response?.task_type) {
          setRecommendationTaskType(response.task_type);
        }

        const recs = response?.recommendations ?? response?.recommendations_list ?? response?.data ?? null;
        if (recs && Array.isArray(recs)) {
          const transformed = recs.map((rec: any) => ({
            name: rec.name,
            score: typeof rec.score === "number" ? rec.score : 5,
            description: rec.description ?? "",
            why: rec.why ?? rec.description ?? "",
            best_for: rec.best_for ?? [],
            icon: rec.icon,
          }));

          setRecommendations(transformed);

          const currentModelName = selectedModel?.name;
          const hasCurrentSelection = currentModelName
            ? transformed.some((m) => m.name === currentModelName)
            : false;

          if (!hasCurrentSelection && transformed.length > 0) {
            setSelectedModel(transformed[0]);
          }

          const validCompareModels = (compareModels ?? []).filter((name) =>
            transformed.some((m) => m.name === name),
          );

          if (validCompareModels.length === 0 && transformed.length > 0) {
            setCompareModels(transformed.slice(0, Math.min(3, transformed.length)).map((m) => m.name));
          } else if (validCompareModels.length !== (compareModels ?? []).length) {
            setCompareModels(validCompareModels);
          }
        } else {
          setError("No recommendations returned by backend.");
        }
      } catch (err: any) {
        console.error("Models: failed to load recommendations", err);
        if (!isMounted) return;
        setError(err?.body?.detail ?? err?.message ?? "Failed to load model recommendations.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchRef.current = true;
    loadRecommendations();
    return () => {
      isMounted = false;
    };
  }, [file, profile, recommendations, selectedModel, compareModels, setRecommendations, setSelectedModel, setCompareModels]);

  const handleSelectModel = useCallback((model: ModelCard) => {
    setSelectedModel(model);
  }, [setSelectedModel]);

  const toggleModelToCompare = useCallback((modelName: string) => {
    const current = compareModels ?? [];
    const next = current.includes(modelName)
      ? current.filter((m) => m !== modelName)
      : [...current, modelName];
    setCompareModels(next);
  }, [compareModels, setCompareModels]);

  if (!profile) {
    return (
      <div className="space-y-8">
        <PageHeader title="Model Selection" description="Recommendation cards ranked by score, with regulator-friendly trade-offs." />
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No dataset available</h3>
          <p className="mt-2 text-sm text-muted-foreground">Upload and preprocess a dataset before model selection.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Model Selection"
        description="Models ranked by suitability for your dataset — with explanations."
      />

      {datasetSummary && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="text-sm text-muted-foreground">Dataset summary</div>
          <div className="mt-2 text-lg font-semibold">
            Dataset: {datasetSummary.sampleCount.toLocaleString()} samples × {datasetSummary.featureCount} features | Imbalance ratio: {datasetSummary.imbalanceRatio.toFixed(1)}:1
          </div>
        </section>
      )}

      {loading && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Loading model recommendations...
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-destructive">
          {error}
        </div>
      )}

      {transformedModels.length === 0 && !loading && !error && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          No model recommendations available.
        </div>
      )}

      {transformedModels.length > 0 && (
        <>
          <section>
            <h2 className="mb-4 text-base font-semibold">Recommended Models</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              These candidates are ranked by suitability and can be compared on the same split after training.
            </p>
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
              {transformedModels.map((m, index) => {
                const rankBadge = `Rank ${index + 1}`;
                return (
                  <div
                    key={m.name}
                    className="relative flex flex-col rounded-2xl border border-border bg-card p-6 shadow-elegant"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm uppercase tracking-wider text-muted-foreground">{rankBadge}</span>
                          <h3 className="text-base font-semibold">{m.name}</h3>
                        </div>
                        {/* model icon omitted to remove emoji from UI */}
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-semibold tabular-nums">{m.score}/10</div>
                        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Score</div>
                      </div>
                    </div>

                    <p className="mt-4 text-sm text-muted-foreground">{m.description}</p>

                    <dl className="mt-4 space-y-3 text-sm">
                      <div>
                        <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Why recommended</dt>
                        <dd className="mt-1 text-foreground/90">{m.why || m.description}</dd>
                      </div>
                      {m.best_for?.length ? (
                        <div>
                          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Best for</dt>
                          <dd className="mt-1 text-foreground/90">{m.best_for.join(" · ")}</dd>
                        </div>
                      ) : null}
                    </dl>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h2 className="mb-4 text-base font-semibold">Select model to train</h2>
            <select
              value={selectedModel?.name ?? transformedModels[0]?.name}
              onChange={(e) => {
                const next = transformedModels.find((m) => m.name === e.target.value);
                if (next) setSelectedModel(next);
              }}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            >
              {transformedModels.map((model) => (
                <option key={model.name} value={model.name}>
                  {model.name}
                </option>
              ))}
            </select>
            <p className="mt-2 text-sm text-muted-foreground">
              The top-ranked model is pre-selected. You can change this.
            </p>
          </section>

          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h2 className="mb-4 text-base font-semibold">Models to compare after training split</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              These models will be trained with lightweight defaults on the same split for comparison.
            </p>
            <div className="space-y-3">
              {transformedModels.map((model) => (
                <label key={model.name} className="flex items-center gap-3 rounded-xl border border-border bg-background px-4 py-3">
                  <input
                    type="checkbox"
                    checked={(compareModels ?? []).includes(model.name)}
                    onChange={() => toggleModelToCompare(model.name)}
                    className="h-4 w-4 rounded border-border accent-primary"
                  />
                  <span className="text-sm">{model.name}</span>
                </label>
              ))}
            </div>
          </section>

          {recommendationTaskType === "binary" && (
            <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h2 className="text-base font-semibold">Credit Risk Evaluation Strategy</h2>
              <p className="mt-3 text-sm text-muted-foreground">
                In credit risk, <strong>Recall</strong> is the most critical metric because failing to identify a truly risky customer (false negative) is far more costly than incorrectly flagging a safe one.
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                We optimize for: <strong>ROC-AUC → Recall → PR-AUC → F1</strong>
              </p>
            </section>
          )}

          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={() => navigate({ to: "/preprocessing" })} className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back to Preprocessing
            </Button>
            <Button onClick={() => navigate({ to: "/training" })} className="gap-2 ml-auto" disabled={!selectedModel}>
              Proceed to Training
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
