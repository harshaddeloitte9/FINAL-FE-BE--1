import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { CheckCircle2, Loader2, Pause, ArrowLeft, ArrowRight, Zap, BarChart3, AlertCircle, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { useEffect, useState, useMemo } from "react";

export const Route = createFileRoute("/training")({
  head: () => ({ meta: [{ title: "Training — Aegis Credit" }] }),
  component: Training,
});

interface TrainingConfig {
  test_size: number;
  val_size: number;
  random_seed: number;
  use_cv: boolean;
  cv_folds: number;
  use_hyperopt: boolean;
  use_class_weight: boolean;
  scale_pos_weight: number;
  use_feature_engineering: boolean;
  manual_params: Record<string, any>;
}

interface ClassDistribution {
  [key: string]: number;
}

interface ComparisonResult {
  model_name: string;
  roc_auc?: number;
  recall?: number;
  precision?: number;
  f1?: number;
  pr_auc?: number;
  accuracy?: number;
  training_time_s?: number;
}

function Training() {
  const navigate = useNavigate();
  const {
    profile,
    file,
    selectedModel,
    recommendations,
    trainingConfig,
    trainingResult,
    comparisonResults,
    selectedComparisonModel,
    setSelectedModel,
    setTrainingConfig,
    setTrainingResult,
    setComparisonResults,
    setSelectedComparisonModel,
  } = useDataset();
  
  // Training configuration state
  const [config, setConfig] = useState<TrainingConfig>(trainingConfig ?? {
    test_size: 0.15,
    val_size: 0.15,
    random_seed: 42,
    use_cv: false,
    cv_folds: 5,
    use_hyperopt: false,
    use_class_weight: false,
    scale_pos_weight: 1.0,
    use_feature_engineering: false,
    manual_params: {},
  });

  const [trainingInfo, setTrainingInfo] = useState<Record<string, any> | null>(trainingResult?.training_info ?? null);
  const [splitStats, setSplitStats] = useState<Record<string, any> | null>(trainingResult?.split_stats ?? null);
  const [evaluationMetrics, setEvaluationMetrics] = useState<Record<string, any> | null>(trainingResult?.evaluation_metrics ?? null);
  const [modelArtifact, setModelArtifact] = useState<string | null>(trainingResult?.model_artifact ?? null);
  const [taskType, setTaskType] = useState<string | null>(trainingResult?.task_type ?? null);
  const [trainingModelName, setTrainingModelName] = useState<string | null>(trainingResult?.model_name ?? selectedModel?.name ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelComparison, setModelComparison] = useState<boolean>(false);
  const [modelsToCompare, setModelsToCompare] = useState<string[]>([]);

  // Hyperparameter preset controls
  const [hyperparams, setHyperparams] = useState<Record<string, any>>({
    learning_rate: 0.05,
    max_depth: 6,
    n_estimators: 200,
    subsample: 0.8,
    colsample_bytree: 0.8,
    reg_lambda: 1.0,
    reg_alpha: 0.0,
  });

  // Calculate live split statistics
  const totalSamples = profile?.shape?.[0] ?? 0;
  const splitStats_live = useMemo(() => {
    if (!totalSamples) return null;
    const testN = Math.floor(totalSamples * config.test_size);
    const trainValN = totalSamples - testN;
    const valN = Math.floor(trainValN * config.val_size / (1 - config.test_size));
    const trainN = trainValN - valN;
    return {
      total: totalSamples,
      train_n: trainN,
      val_n: valN,
      test_n: testN,
      train_pct: trainN / totalSamples,
      val_pct: valN / totalSamples,
      test_pct: testN / totalSamples,
    };
  }, [totalSamples, config.test_size, config.val_size]);

  // Handle training execution
  const trainModel = async (modelName: string) => {
    if (!profile || !file) {
      throw new Error("Missing profile or file");
    }

    const trainForm = new FormData();
    trainForm.append("file", file);
    trainForm.append("target_col", profile.target_col || "loan_status");
    trainForm.append("model_name", modelName);
    trainForm.append("test_size", String(config.test_size));
    trainForm.append("val_size", String(config.val_size));
    trainForm.append("random_seed", String(config.random_seed));
    trainForm.append("use_cv", String(config.use_cv));
    trainForm.append("cv_folds", String(config.cv_folds));
    trainForm.append("use_hyperopt", String(config.use_hyperopt));
    trainForm.append("use_class_weight", String(config.use_class_weight));
    trainForm.append("scale_pos_weight", String(config.scale_pos_weight));
    trainForm.append("use_feature_engineering", String(config.use_feature_engineering));
    if (Object.keys(config.manual_params).length > 0) {
      trainForm.append("manual_params", JSON.stringify(config.manual_params));
    }

    const trainResponse = await formUpload("/models/train", trainForm);
    if (!trainResponse?.training_info || !trainResponse?.split_stats || !trainResponse?.model_artifact) {
      throw new Error("Training response missing required fields.");
    }

    const evalForm = new FormData();
    evalForm.append("model_artifact", trainResponse.model_artifact);
    evalForm.append("file", file);
    evalForm.append("target_col", profile.target_col || "loan_status");

    const evalResponse = await formUpload("/models/evaluate", evalForm);

    return {
      model_name: modelName,
      task_type: trainResponse.task_type ?? "binary",
      training_info: trainResponse.training_info,
      split_stats: trainResponse.split_stats,
      feature_engineering_summary: trainResponse.feature_engineering_summary ?? null,
      model_artifact: trainResponse.model_artifact,
      evaluation_metrics: evalResponse?.metrics ?? null,
      evaluation_data: evalResponse ?? null,
    };
  };

  const handleTrain = async () => {
    if (!profile || !file || !selectedModel) {
      setError("Missing profile, file, or model selection");
      return;
    }

    setLoading(true);
    setError(null);
    setModelComparison(false);

    try {
      const result = await trainModel(selectedModel.name);
      setTrainingInfo(result.training_info);
      setSplitStats(result.split_stats);
      setEvaluationMetrics(result.evaluation_metrics);
      setModelArtifact(result.model_artifact);
      setTaskType(result.task_type);
      setTrainingModelName(result.model_name);
      setComparisonResults([{ model_name: result.model_name, ...result.evaluation_metrics, training_time_s: result.training_info.training_time_s }]);
      setTrainingResult({
        task_type: result.task_type,
        model_name: result.model_name,
        real_feature_names: [],
        training_info: result.training_info,
        split_stats: result.split_stats,
        feature_engineering_summary: result.feature_engineering_summary,
        evaluation_metrics: result.evaluation_metrics,
        evaluation_data: result.evaluation_data,
        model_artifact: result.model_artifact,
      });
    } catch (err: any) {
      console.error("Training: failed", err);
      setError(err?.body?.detail ?? err?.message ?? "Failed to train model.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickComparison = async () => {
    if (!profile || !file || !selectedModel) {
      setError("Missing profile, file, or model selection");
      return;
    }

    if (modelsToCompare.length === 0) {
      setError("Select at least one model to compare");
      return;
    }

    setLoading(true);
    setError(null);
    setModelComparison(true);

    try {
      const candidateModelNames = [selectedModel.name, ...modelsToCompare.filter((name) => name !== selectedModel.name)];
      const rows = [] as Array<ComparisonResult>;

      for (const modelName of candidateModelNames) {
        const result = await trainModel(modelName);
        rows.push({
          model_name: modelName,
          roc_auc: result.evaluation_metrics?.roc_auc,
          recall: result.evaluation_metrics?.recall,
          precision: result.evaluation_metrics?.precision,
          f1: result.evaluation_metrics?.f1,
          pr_auc: result.evaluation_metrics?.pr_auc,
          accuracy: result.evaluation_metrics?.accuracy,
          training_time_s: result.training_info.training_time_s,
        });

        if (modelName === selectedModel.name) {
          setTrainingInfo(result.training_info);
          setSplitStats(result.split_stats);
          setEvaluationMetrics(result.evaluation_metrics);
          setModelArtifact(result.model_artifact);
          setTaskType(result.task_type);
          setTrainingModelName(result.model_name);
          setTrainingResult({
            task_type: result.task_type,
            model_name: result.model_name,
            real_feature_names: [],
            training_info: result.training_info,
            split_stats: result.split_stats,
            feature_engineering_summary: result.feature_engineering_summary,
            evaluation_metrics: result.evaluation_metrics,
            evaluation_data: result.evaluation_data,
            model_artifact: result.model_artifact,
          });
        }
      }

      setComparisonResults(rows);
      setSelectedComparisonModel(candidateModelNames[0]);
    } catch (err: any) {
      console.error("Comparison: failed", err);
      setError(err?.body?.detail ?? err?.message ?? "Failed to run comparison.");
    } finally {
      setLoading(false);
    }
  };

  // Calculate class imbalance for recommendations
  const classImbalance = useMemo(() => {
    if (!profile?.class_distribution) return 1.0;
    const values = Object.values(profile.class_distribution) as number[];
    if (values.length < 2) return 1.0;
    const sorted = values.sort((a, b) => b - a);
    return sorted[0] / (sorted[1] || 1);
  }, [profile?.class_distribution]);

  useEffect(() => {
    setTrainingConfig(config);
  }, [config, setTrainingConfig]);

  if (!selectedModel) {
    return (
      <div className="space-y-8">
        <PageHeader
          title="Training"
          description="Configure and run model training"
        />
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No model selected</h3>
          <p className="mt-2 text-sm text-muted-foreground">Select a model before proceeding to training.</p>
          <Button onClick={() => navigate({ to: "/models" })} className="mt-4">
            Go back to Model Selection
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Training"
        description={`Configure and train the ${selectedModel.name} model with optimized parameters.`}
      />

      {error && (
        <div className="rounded-xl border border-destructive bg-destructive/5 p-4 text-sm text-destructive flex gap-3">
          <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div>{error}</div>
        </div>
      )}

      {/* Data Split Configuration */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="h-5 w-5 text-primary" />
          <h2 className="text-base font-semibold">Data Split Configuration</h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Train Size */}
          <div>
            <label className="text-sm font-medium">Train Size</label>
            <div className="mt-2 flex items-baseline gap-2">
              <input
                type="range"
                min="0.3"
                max="0.85"
                step="0.05"
                value={config.test_size + config.val_size > 0.95 ? 0.7 : 1 - config.test_size - config.val_size}
                onChange={(e) => {
                  const trainPct = parseFloat(e.target.value);
                  const remaining = 1 - trainPct;
                  setConfig(prev => ({
                    ...prev,
                    test_size: remaining * 0.5,
                    val_size: remaining * 0.5,
                  }));
                }}
                className="flex-1"
              />
              <span className="text-sm font-mono w-12 text-right">{(splitStats_live?.train_pct ?? 0).toFixed(0)}%</span>
            </div>
            {splitStats_live && <p className="text-xs text-muted-foreground mt-1">{splitStats_live.train_n.toLocaleString()} samples</p>}
          </div>

          {/* Val Size */}
          <div>
            <label className="text-sm font-medium">Validation Size</label>
            <div className="mt-2 flex items-baseline gap-2">
              <input
                type="range"
                min="0.05"
                max="0.4"
                step="0.05"
                value={config.val_size}
                onChange={(e) => setConfig(prev => ({ ...prev, val_size: parseFloat(e.target.value) }))}
                className="flex-1"
              />
              <span className="text-sm font-mono w-12 text-right">{(splitStats_live?.val_pct ?? 0).toFixed(0)}%</span>
            </div>
            {splitStats_live && <p className="text-xs text-muted-foreground mt-1">{splitStats_live.val_n.toLocaleString()} samples</p>}
          </div>

          {/* Test Size */}
          <div>
            <label className="text-sm font-medium">Test Size</label>
            <div className="mt-2 flex items-baseline gap-2">
              <input
                type="range"
                min="0.1"
                max="0.4"
                step="0.05"
                value={config.test_size}
                onChange={(e) => setConfig(prev => ({ ...prev, test_size: parseFloat(e.target.value) }))}
                className="flex-1"
              />
              <span className="text-sm font-mono w-12 text-right">{(splitStats_live?.test_pct ?? 0).toFixed(0)}%</span>
            </div>
            {splitStats_live && <p className="text-xs text-muted-foreground mt-1">{splitStats_live.test_n.toLocaleString()} samples</p>}
          </div>
        </div>

        {/* Random Seed */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-sm font-medium">Random Seed</label>
            <input
              type="number"
              value={config.random_seed}
              onChange={(e) => setConfig(prev => ({ ...prev, random_seed: parseInt(e.target.value) || 42 }))}
              className="mt-2 w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
            />
            <p className="text-xs text-muted-foreground mt-1">Ensures reproducible splits</p>
          </div>
        </div>
      </section>

      {/* Class Distribution Visualization */}
      {splitStats_live && profile?.class_distribution && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold mb-4">Class Distribution</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(profile.class_distribution).map(([label, count]) => (
              <div key={label} className="bg-muted rounded-lg p-4">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">Class {label}</div>
                <div className="mt-2 text-2xl font-semibold">{(count as number).toLocaleString()}</div>
                <div className="mt-2 h-2 bg-primary/20 rounded-full overflow-hidden">
                  <div className="h-full bg-primary" style={{ width: `${Math.min((count as number) / (Math.max(...Object.values(profile.class_distribution) as number[]) || 1) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
          {classImbalance > 1.5 && (
            <div className="mt-4 p-3 bg-orange-500/10 border border-orange-200 rounded-lg flex gap-2">
              <Info className="h-4 w-4 text-orange-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-orange-900">
                <strong>Class Imbalance Detected:</strong> {classImbalance.toFixed(2)}x ratio. Consider enabling class balancing below.
              </div>
            </div>
          )}
        </section>
      )}

      {/* Class Balancing */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h2 className="text-base font-semibold mb-4">Class Balancing</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Use Balanced Class Weights</label>
              <p className="text-xs text-muted-foreground mt-1">Automatically weight classes inversely proportional to frequencies</p>
            </div>
            <input
              type="checkbox"
              checked={config.use_class_weight}
              onChange={(e) => setConfig(prev => ({ ...prev, use_class_weight: e.target.checked }))}
              className="w-5 h-5"
            />
          </div>

          {selectedModel.name === "XGBoost" && (
            <div>
              <label className="text-sm font-medium block mb-2">Scale Positive Weight (XGBoost)</label>
              <div className="flex items-baseline gap-3">
                <input
                  type="range"
                  min="1"
                  max="10"
                  step="0.5"
                  value={config.scale_pos_weight}
                  onChange={(e) => setConfig(prev => ({ ...prev, scale_pos_weight: parseFloat(e.target.value) }))}
                  disabled={!config.use_class_weight}
                  className="flex-1"
                />
                <span className="text-sm font-mono w-12 text-right">{config.scale_pos_weight.toFixed(1)}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">Weights positive class; recommended when imbalance {">"} 2x</p>
            </div>
          )}

          {classImbalance > 2 && (
            <div className="p-3 bg-blue-500/10 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-900">
                <strong>Recommendation:</strong> Your dataset shows {classImbalance.toFixed(1)}x class imbalance. Using <code className="bg-blue-200 px-1 rounded">class_weight="balanced"</code> is strongly recommended.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Cross Validation & Hyperparameter Tuning */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h2 className="text-base font-semibold mb-4">Cross Validation & Hyperparameter Tuning</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Enable Cross Validation</label>
              <p className="text-xs text-muted-foreground mt-1">Assess model stability across data splits</p>
            </div>
            <input
              type="checkbox"
              checked={config.use_cv}
              onChange={(e) => setConfig(prev => ({ ...prev, use_cv: e.target.checked }))}
              className="w-5 h-5"
            />
          </div>

          {config.use_cv && (
            <div>
              <label className="text-sm font-medium block mb-2">CV Folds</label>
              <input
                type="number"
                min="2"
                max="10"
                value={config.cv_folds}
                onChange={(e) => setConfig(prev => ({ ...prev, cv_folds: parseInt(e.target.value) || 5 }))}
                className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
              />
            </div>
          )}

          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Enable Hyperparameter Tuning</label>
              <p className="text-xs text-muted-foreground mt-1">Randomized search for optimal parameters</p>
            </div>
            <input
              type="checkbox"
              checked={config.use_hyperopt}
              onChange={(e) => setConfig(prev => ({ ...prev, use_hyperopt: e.target.checked }))}
              className="w-5 h-5"
            />
          </div>
        </div>
      </section>

      {/* Manual Hyperparameter Controls */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h2 className="text-base font-semibold mb-4">Manual Hyperparameter Controls</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {selectedModel.name !== "Logistic Regression" && (
            <>
              <div>
                <label className="text-sm font-medium block mb-2">Learning Rate</label>
                <input
                  type="number"
                  min="0.001"
                  max="1"
                  step="0.01"
                  value={hyperparams.learning_rate}
                  onChange={(e) => setHyperparams(prev => ({ ...prev, learning_rate: parseFloat(e.target.value) }))}
                  className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-2">Max Depth</label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={hyperparams.max_depth}
                  onChange={(e) => setHyperparams(prev => ({ ...prev, max_depth: parseInt(e.target.value) || 6 }))}
                  className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-2">N Estimators</label>
                <input
                  type="number"
                  min="10"
                  max="1000"
                  step="10"
                  value={hyperparams.n_estimators}
                  onChange={(e) => setHyperparams(prev => ({ ...prev, n_estimators: parseInt(e.target.value) || 200 }))}
                  className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                />
              </div>

              {selectedModel.name === "XGBoost" && (
                <>
                  <div>
                    <label className="text-sm font-medium block mb-2">Subsample</label>
                    <input
                      type="number"
                      min="0.1"
                      max="1"
                      step="0.1"
                      value={hyperparams.subsample}
                      onChange={(e) => setHyperparams(prev => ({ ...prev, subsample: parseFloat(e.target.value) }))}
                      className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium block mb-2">Colsample Bytree</label>
                    <input
                      type="number"
                      min="0.1"
                      max="1"
                      step="0.1"
                      value={hyperparams.colsample_bytree}
                      onChange={(e) => setHyperparams(prev => ({ ...prev, colsample_bytree: parseFloat(e.target.value) }))}
                      className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium block mb-2">Reg Lambda</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      step="0.1"
                      value={hyperparams.reg_lambda}
                      onChange={(e) => setHyperparams(prev => ({ ...prev, reg_lambda: parseFloat(e.target.value) }))}
                      className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium block mb-2">Reg Alpha</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      step="0.1"
                      value={hyperparams.reg_alpha}
                      onChange={(e) => setHyperparams(prev => ({ ...prev, reg_alpha: parseFloat(e.target.value) }))}
                      className="w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
                    />
                  </div>
                </>
              )}
            </>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => {
            setConfig(prev => ({
              ...prev,
              manual_params: hyperparams,
            }));
          }}
        >
          Apply Manual Parameters
        </Button>
      </section>

      {/* Current Parameters Summary */}
      <Accordion type="single" collapsible className="rounded-xl border border-border bg-card shadow-elegant">
        <AccordionItem value="current-params">
          <AccordionTrigger className="px-6 py-4">
            Current Parameters Summary
          </AccordionTrigger>
          <AccordionContent className="px-6 pt-0 pb-6">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
              <div><strong>Model:</strong> {selectedModel.name}</div>
              <div><strong>Random Seed:</strong> {config.random_seed}</div>
              <div><strong>Train / Val / Test:</strong> {((1 - config.test_size - config.val_size) * 100).toFixed(0)}% / {(config.val_size * 100).toFixed(0)}% / {(config.test_size * 100).toFixed(0)}%</div>
              <div><strong>CV:</strong> {config.use_cv ? `Yes (${config.cv_folds} folds)` : "No"}</div>
              <div><strong>Hyperopt:</strong> {config.use_hyperopt ? "Yes" : "No"}</div>
              <div><strong>Feature engineering:</strong> {config.use_feature_engineering ? "Enabled" : "Disabled"}</div>
              <div><strong>Class Weight:</strong> {config.use_class_weight ? `Yes${selectedModel.name === "XGBoost" ? ` (scale: ${config.scale_pos_weight.toFixed(1)})` : ""}` : "No"}</div>
              {Object.keys(config.manual_params).length > 0 && (
                <div className="md:col-span-2"><strong>Manual Params:</strong> <code className="rounded bg-background px-2 py-1 text-xs">{JSON.stringify(config.manual_params)}</code></div>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {/* Model Comparison Section */}
      {recommendations && recommendations.length > 1 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold">Model Comparison</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-4">Select additional models to train and compare against the champion.</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {recommendations.map((rec) => (
              <label
                key={rec.name}
                className={`p-3 border rounded-lg cursor-pointer transition ${
                  modelsToCompare.includes(rec.name)
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={modelsToCompare.includes(rec.name)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setModelsToCompare(prev => [...prev, rec.name]);
                    } else {
                      setModelsToCompare(prev => prev.filter(m => m !== rec.name));
                    }
                  }}
                  className="w-4 h-4"
                />
                <div className="text-sm font-medium mt-2">{rec.name}</div>
                <div className="text-xs text-muted-foreground">{rec.name === selectedModel.name ? "(Champion)" : ""}</div>
              </label>
            ))}
          </div>
        </section>
      )}

      {/* Training Results */}
      {trainingInfo && (
        <>
          {evaluationMetrics && (
            <section className="rounded-xl border border-warning/40 bg-warning/10 p-6 shadow-elegant">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-warning-foreground flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-warning-foreground">Regulatory risk warning</p>
                  <p className="text-sm text-warning-foreground">
                    {evaluationMetrics.roc_auc !== undefined && evaluationMetrics.roc_auc < 0.70 && (
                      <>ROC-AUC is below 0.70, which may signal weak discrimination for credit risk. </>
                    )}
                    {evaluationMetrics.recall !== undefined && evaluationMetrics.recall < 0.60 && (
                      <>Recall is below 0.60, which may indicate an elevated missed-default risk. </>
                    )}
                    Review model performance before promotion to production.
                  </p>
                </div>
              </div>
            </section>
          )}

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h2 className="text-base font-semibold">Hyperparameters</h2>
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                {Object.entries(trainingInfo.best_params || {}).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="text-right font-mono text-xs">{String(v)}</dd>
                  </div>
                ))}
                {trainingInfo.training_time_s && (
                  <>
                    <dt className="text-muted-foreground">training_time_s</dt>
                    <dd className="text-right font-mono text-xs">{trainingInfo.training_time_s.toFixed(2)}</dd>
                  </>
                )}
              </dl>
            </div>

            <div className="lg:col-span-2 rounded-xl border border-border bg-sidebar p-6 font-mono text-xs text-sidebar-foreground shadow-elegant">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-sans text-sm font-semibold text-sidebar-foreground">Model Summary</span>
              </div>
              <div className="space-y-1.5">
                <div><strong>Model:</strong> {trainingModelName ?? selectedModel.name}</div>
                <div><strong>Training Time:</strong> {trainingInfo.training_time_s?.toFixed(2)}s</div>
                {trainingInfo.cv_mean && <div><strong>CV Mean Score:</strong> {trainingInfo.cv_mean.toFixed(4)}</div>}
                {trainingInfo.cv_std && <div><strong>CV Std Dev:</strong> {trainingInfo.cv_std.toFixed(4)}</div>}
              </div>
            </div>
          </section>

          {splitStats && (
            <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h2 className="text-base font-semibold">Data Split Statistics</h2>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Total Samples</dt>
                  <dd className="mt-1 text-lg font-semibold">{splitStats.total?.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Train / Val / Test</dt>
                  <dd className="mt-1 text-sm">{splitStats.train_n} / {splitStats.val_n} / {splitStats.test_n}</dd>
                </div>
              </div>
            </section>
          )}

          {evaluationMetrics && (
            <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h2 className="text-base font-semibold">Evaluation Metrics</h2>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                {[
                  ["ROC-AUC", evaluationMetrics.roc_auc],
                  ["Recall", evaluationMetrics.recall],
                  ["Precision", evaluationMetrics.precision],
                  ["F1", evaluationMetrics.f1],
                  ["PR-AUC", evaluationMetrics.pr_auc],
                  ["Accuracy", evaluationMetrics.accuracy],
                ].map(([label, value]) => (
                  value !== undefined && (
                    <div key={label} className="rounded-lg border border-border p-4">
                      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
                      <div className="mt-2 text-2xl font-semibold">{(typeof value === "number" ? value.toFixed(3) : String(value))}</div>
                    </div>
                  )
                ))}
              </div>
            </section>
          )}

          {comparisonResults && comparisonResults.length > 0 && (
            <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-base font-semibold">Comparison Table</h2>
                  <p className="text-sm text-muted-foreground">Review model-level metrics for selected candidates and choose a final champion.</p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="px-3 py-2">Model</th>
                      <th className="px-3 py-2">ROC-AUC</th>
                      <th className="px-3 py-2">Recall</th>
                      <th className="px-3 py-2">Precision</th>
                      <th className="px-3 py-2">F1</th>
                      <th className="px-3 py-2">PR-AUC</th>
                      <th className="px-3 py-2">Accuracy</th>
                      <th className="px-3 py-2">Train Time</th>
                      <th className="px-3 py-2">Final</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {comparisonResults.map((row) => (
                      <tr key={row.model_name} className={row.model_name === selectedComparisonModel ? "bg-primary/5" : undefined}>
                        <td className="px-3 py-3 font-medium">{row.model_name}</td>
                        <td className="px-3 py-3">{row.roc_auc?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-3">{row.recall?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-3">{row.precision?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-3">{row.f1?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-3">{row.pr_auc?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-3">{row.accuracy?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-3">{row.training_time_s ? `${row.training_time_s.toFixed(2)}s` : "—"}</td>
                        <td className="px-3 py-3">
                          <Button
                            variant={row.model_name === selectedComparisonModel ? "secondary" : "outline"}
                            size="sm"
                            onClick={() => {
                              setSelectedComparisonModel(row.model_name);
                              const chosen = recommendations?.find((rec) => rec.name === row.model_name);
                              if (chosen) {
                                setSelectedModel(chosen);
                              }
                            }}
                          >
                            {row.model_name === selectedComparisonModel ? "Selected" : "Select"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}

      {/* Action Buttons */}
      <div className="flex gap-3 pt-4">
        <Button variant="outline" onClick={() => navigate({ to: "/models" })} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <Button
          onClick={handleTrain}
          disabled={loading}
          className="gap-2"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {loading ? "Training..." : "Train Model Now"}
        </Button>
        {modelsToCompare.length > 0 && (
          <Button
            onClick={handleQuickComparison}
            disabled={loading}
            variant="outline"
            className="gap-2"
          >
            <Zap className="h-4 w-4" />
            Run Quick Comparison
          </Button>
        )}
        <Button
          onClick={() => navigate({ to: "/evaluation" })}
          disabled={loading || !trainingInfo}
          className="gap-2 ml-auto"
        >
          Proceed to Evaluation
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
