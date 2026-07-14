import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import {
  ArrowRight,
  Trophy,
  PlayCircle,
  Loader2,
  UploadCloud,
  FileUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  MinusCircle,
  Database,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
import { api, formUpload, ApiError } from "@/lib/api";
import { useDataset } from "@/lib/app-context";

export const Route = createFileRoute("/validation/challenger")({
  head: () => ({ meta: [{ title: "Replication & Benchmarking — Aegis Credit" }] }),
  component: Challenger,
});

// --- Existing champion vs challenger benchmarking mock data (unchanged) ---

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

// --- Model Replication (Stage 4a) — real backend-connected panel ---

type CheckStatus = "PASS" | "WARN" | "FAIL" | "SKIP";

type ReplicationCheck = {
  id: string;
  title: string;
  severity: string;
  status: CheckStatus;
  observed?: string;
  threshold?: string;
  detail?: string;
  _table?: Array<Record<string, any>>;
  _ablation?: Record<string, number>;
  _seed_aucs?: number[];
  _seeds?: number[];
};

type ReplicationResult = {
  success: boolean;
  error?: string | null;
  metrics: Record<string, number>;
  seed_aucs: number[];
  cv_mean_auc?: number | null;
  cv_std_auc?: number | null;
  split_stats: Record<string, number>;
  ablation: Record<string, number>;
  timing_s: number;
};

type ReplicationResponse = {
  stage: string;
  flags: string[];
  report: { replication: { result: ReplicationResult; checks: ReplicationCheck[] } };
};

const statusStyles: Record<CheckStatus, string> = {
  PASS: "bg-primary-soft text-foreground border-primary/30",
  WARN: "bg-warning/20 text-warning-foreground border-warning/40",
  FAIL: "bg-destructive/10 text-destructive border-destructive/30",
  SKIP: "bg-background text-muted-foreground border-border",
};

function StatusIcon({ s }: { s: CheckStatus }) {
  if (s === "PASS") return <CheckCircle2 className="h-3.5 w-3.5" />;
  if (s === "WARN") return <AlertTriangle className="h-3.5 w-3.5" />;
  if (s === "FAIL") return <XCircle className="h-3.5 w-3.5" />;
  return <MinusCircle className="h-3.5 w-3.5" />;
}

const REPORTED_METRIC_FIELDS: Array<{ key: string; label: string }> = [
  { key: "roc_auc", label: "ROC-AUC" },
  { key: "gini", label: "Gini" },
  { key: "ks", label: "KS" },
  { key: "accuracy", label: "Accuracy" },
  { key: "precision", label: "Precision" },
  { key: "recall", label: "Recall" },
  { key: "f1", label: "F1" },
  { key: "cv_mean_auc", label: "CV Mean AUC" },
];

function ModelReplicationPanel() {
  const ds = useDataset();

  const [localFile, setLocalFile] = React.useState<File | null>(null);
  const [mddFile, setMddFile] = React.useState<File | null>(null);
  const [targetCol, setTargetCol] = React.useState("");
  const [modelName, setModelName] = React.useState("");
  const [testSize, setTestSize] = React.useState(0.15);
  const [valSize, setValSize] = React.useState(0.15);
  const [randomSeed, setRandomSeed] = React.useState(42);
  const [cvFolds, setCvFolds] = React.useState(5);
  const [seedsText, setSeedsText] = React.useState("42,43,44,45,46");
  const [reported, setReported] = React.useState<Record<string, string>>({});
  const [availableModels, setAvailableModels] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [replication, setReplication] = React.useState<{ result: ReplicationResult; checks: ReplicationCheck[] } | null>(null);
  const [flags, setFlags] = React.useState<string[]>([]);

  // profile / trainingResult shapes aren't strictly typed on the context
  // (Record<string, any>), so field access below is defensive with fallbacks.
  const profile = ds.profile as Record<string, any> | null | undefined;
  const trainingResult = ds.trainingResult as Record<string, any> | null | undefined;
  const trainingConfig = ds.trainingConfig as Record<string, any> | null | undefined;
  const validationMddMetrics = ds.validationMddMetrics as Record<string, any> | null | undefined;
  const validationIntakeData = ds.validationIntakeData as Record<string, any> | null | undefined;
  const selectedModelName = ds.selectedModel?.name as string | undefined;

  const targetCandidates: string[] = React.useMemo(() => {
    const c = profile?.target_candidates ?? profile?.targetCandidates ?? profile?.candidate_targets ?? [];
    return Array.isArray(c) ? c.filter((x) => typeof x === "string") : [];
  }, [profile]);

  const allColumns: string[] = React.useMemo(() => {
    const c = profile?.columns ?? profile?.column_names ?? profile?.all_columns ?? [];
    return Array.isArray(c) ? c.filter((x) => typeof x === "string") : [];
  }, [profile]);

  const datasetName: string | null =
    profile?.dataset_name ?? profile?.name ?? ds.file?.name ?? null;

  const contextFileAvailable = Boolean(ds.file || profile?.csv_text || profile?.dataset_name || profile?.name);
  const resolvedAlgorithmName = React.useMemo(() => {
    const fromIntake = typeof validationIntakeData?.algorithm === "string" ? validationIntakeData.algorithm.trim() : "";
    if (fromIntake) return fromIntake;

    const fromSelected = typeof selectedModelName === "string" ? selectedModelName.trim() : "";
    if (fromSelected) return fromSelected;

    const fromTraining = typeof trainingResult?.model_name === "string" ? trainingResult.model_name.trim() : "";
    if (fromTraining) return fromTraining;

    return modelName.trim();
  }, [modelName, selectedModelName, trainingResult?.model_name, validationIntakeData?.algorithm]);
  const activeFile = React.useMemo<File | null>(() => {
    if (localFile) return localFile;
    if (ds.file) return ds.file;

    const csvText = typeof profile?.csv_text === "string" ? profile.csv_text : "";
    if (!csvText.trim()) return null;

    const resolvedName = datasetName ?? "validation_dataset.csv";
    const safeName = resolvedName.endsWith(".csv") || resolvedName.endsWith(".xlsx")
      ? resolvedName
      : `${resolvedName}.csv`;
    return new File([csvText], safeName, { type: "text/csv" });
  }, [datasetName, ds.file, localFile, profile?.csv_text]);

  // Fetch the classification model registry once for the datalist.
  React.useEffect(() => {
    const contextModels = [selectedModelName, trainingResult?.model_name, validationIntakeData?.model_name]
      .filter((value): value is string => Boolean(value))
      .map((value) => String(value));

    if (contextModels.length > 0) {
      setAvailableModels((prev) => Array.from(new Set([...prev, ...contextModels])));
    }
  }, [selectedModelName, trainingResult?.model_name, validationIntakeData?.model_name]);

  // Prefill from whatever the earlier stages already put in context, once.
  const prefilledRef = React.useRef(false);
  React.useEffect(() => {
    if (prefilledRef.current) return;
    const hasContextModel = Boolean(selectedModelName || trainingResult?.model_name || validationIntakeData?.model_name || profile);
    if (!hasContextModel) return;
    prefilledRef.current = true;

    if (targetCandidates[0]) setTargetCol(targetCandidates[0]);

    const contextModelName = selectedModelName ?? trainingResult?.model_name ?? validationIntakeData?.model_name;
    if (contextModelName) {
      setModelName(String(contextModelName));
    }

    if (trainingConfig) {
      if (typeof trainingConfig.test_size === "number") setTestSize(trainingConfig.test_size);
      if (typeof trainingConfig.val_size === "number") setValSize(trainingConfig.val_size);
      if (typeof trainingConfig.random_seed === "number") setRandomSeed(trainingConfig.random_seed);
      if (typeof trainingConfig.cv_folds === "number") setCvFolds(trainingConfig.cv_folds);
    }

    const sourceMetrics = validationMddMetrics ?? (trainingResult?.evaluation_metrics as Record<string, any> | undefined);
    if (sourceMetrics) {
      setReported((prev) => {
        const next = { ...prev };
        for (const { key } of REPORTED_METRIC_FIELDS) {
          const v = sourceMetrics[key] ?? (key === "cv_mean_auc" ? sourceMetrics.cv_mean : undefined);
          if (v !== undefined && v !== null) next[key] = String(v);
        }
        return next;
      });
    }
  }, [profile, trainingResult, trainingConfig, validationMddMetrics, validationIntakeData?.model_name, selectedModelName, targetCandidates]);

  const runReplication = async () => {
    setError(null);

    if (!activeFile) {
      setError("No active dataset is available in shared state. Complete Stage 1 Intake and Stage 2 Data Validation first, or upload a file below.");
      return;
    }
    if (!targetCol.trim()) {
      setError("Target column is required.");
      return;
    }
    if (!modelName.trim()) {
      setError("Model is required.");
      return;
    }

    const algorithmName = resolvedAlgorithmName.trim();
    if (!algorithmName) {
      setError("Algorithm is required.");
      return;
    }

    setLoading(true);
    setReplication(null);
    setFlags([]);
    try {
      const form = new FormData();
      if (activeFile) {
        form.append("file", activeFile);
      } else if (typeof profile?.csv_text === "string") {
        form.append("csv_text", profile.csv_text);
      }
      form.append("model_name", modelName.trim());
      form.append("algorithm", algorithmName);
      form.append("target_col", targetCol.trim());
      form.append("seeds", seedsText.trim() || "42,43,44,45,46");
      form.append("test_size", String(testSize));
      form.append("val_size", String(valSize));
      form.append("random_seed", String(randomSeed));
      form.append("cv_folds", String(cvFolds));
      if (mddFile) form.append("mdd_file", mddFile);

      const reportedPayload = Object.fromEntries(
        Object.entries(reported)
          .filter(([, v]) => v !== "" && v !== undefined && v !== null)
          .map(([k, v]) => [k, Number(v)])
          .filter(([, v]) => !Number.isNaN(v as number)),
      );
      if (Object.keys(reportedPayload).length > 0) {
        form.append("reported_json", JSON.stringify(reportedPayload));
      }

      const res = await formUpload<ReplicationResponse>("/validation/replication", form);
      setReplication(res.report.replication);
      setFlags(res.flags ?? []);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail =
          err.body && typeof err.body === "object" && "detail" in (err.body as any)
            ? String((err.body as any).detail)
            : err.message;
        setError(detail);
      } else {
        setError(err instanceof Error ? err.message : "Replication run failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const seedChartData = React.useMemo(() => {
    if (!replication?.result?.seed_aucs?.length) return [];
    const seedIds = seedsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return replication.result.seed_aucs.map((auc, i) => ({
      seed: seedIds[i] ?? `#${i + 1}`,
      auc,
    }));
  }, [replication, seedsText]);

  const ablationChartData = React.useMemo(() => {
    const abl = replication?.result?.ablation;
    if (!abl) return [];
    return Object.entries(abl)
      .filter(([, v]) => typeof v === "number" && !Number.isNaN(v))
      .sort((a, b) => (b[1] as number) - (a[1] as number))
      .slice(0, 10)
      .map(([feature, drop]) => ({ feature, drop: Number((drop as number).toFixed(4)) }));
  }, [replication]);

  const metrics = replication?.result?.metrics ?? {};

  return (
    <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold">Model Replication</h3>
          <p className="mt-1 text-sm text-foreground/80">
            Independently re-train the submitted model on the validation dataset and run checks R4.1–R4.8
            against developer-reported metrics.
          </p>
        </div>
      </div>

      {/* Dataset source */}
      <div className="mt-5 rounded-lg border border-border bg-background p-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Database className="h-3.5 w-3.5" /> Dataset
        </div>
        {contextFileAvailable && !localFile && (
          <p className="mt-2 text-sm">
            Using <span className="font-medium">{datasetName ?? ds.file?.name}</span> from Intake.{" "}
            <label className="cursor-pointer text-primary underline underline-offset-2">
              Use a different file
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => setLocalFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </p>
        )}
        {(!contextFileAvailable || localFile) && (
          <div className="mt-2">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground hover:border-primary/40">
              <UploadCloud className="h-4 w-4" />
              {localFile ? localFile.name : "Upload dataset (CSV or XLSX)"}
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => setLocalFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {contextFileAvailable && localFile && (
              <button
                className="ml-3 text-xs text-primary underline underline-offset-2"
                onClick={() => setLocalFile(null)}
              >
                Revert to Intake file ({ds.file?.name})
              </button>
            )}
          </div>
        )}
      </div>

      {/* Config form */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Target column</label>
          <input
            list="replication-target-candidates"
            value={targetCol}
            onChange={(e) => setTargetCol(e.target.value)}
            placeholder="e.g. default_flag"
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          <datalist id="replication-target-candidates">
            {[...targetCandidates, ...allColumns].map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground">Model</label>
          <input
            list="replication-model-options"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="e.g. xgboost"
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          <datalist id="replication-model-options">
            {availableModels.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground">Random seed</label>
          <input
            type="number"
            value={randomSeed}
            onChange={(e) => setRandomSeed(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground">CV folds</label>
          <input
            type="number"
            min={2}
            max={10}
            value={cvFolds}
            onChange={(e) => setCvFolds(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground">Test size</label>
          <input
            type="number"
            step={0.01}
            min={0.05}
            max={0.4}
            value={testSize}
            onChange={(e) => setTestSize(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground">Validation size</label>
          <input
            type="number"
            step={0.01}
            min={0.05}
            max={0.4}
            value={valSize}
            onChange={(e) => setValSize(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="text-xs font-medium text-muted-foreground">Seed stability seeds (comma-separated)</label>
          <input
            value={seedsText}
            onChange={(e) => setSeedsText(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* Reported metrics + MDD */}
      <div className="mt-4 rounded-lg border border-border bg-background p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Developer-reported metrics (for R4.2 / R4.3 / R4.4 / R4.8)
          </p>
          <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-primary underline underline-offset-2">
            <FileUp className="h-3.5 w-3.5" />
            {mddFile ? mddFile.name : "Upload MDD (PDF/DOCX/TXT) to auto-extract"}
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={(e) => setMddFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Auto-filled from this dataset's training run where available. Edit any value, or leave blank to skip that check.
          Values extracted from an uploaded MDD override these on run.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {REPORTED_METRIC_FIELDS.map(({ key, label }) => (
            <div key={key}>
              <label className="text-[11px] text-muted-foreground">{label}</label>
              <input
                value={reported[key] ?? ""}
                onChange={(e) => setReported((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder="—"
                className="mt-1 w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
              />
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <XCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="mt-4">
        <button
          onClick={runReplication}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg gradient-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
          {loading ? "Running replication…" : "Run replication"}
        </button>
      </div>

      {/* Results */}
      {replication && (
        <div className="mt-6 space-y-6">
          {replication.result.success ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {flags.length === 0 ? "No failing checks" : `${flags.length} failing check${flags.length === 1 ? "" : "s"}`}
                </span>
                {flags.map((f) => (
                  <span key={f} className="rounded-full border border-destructive/30 bg-destructive/10 px-2 py-0.5 text-[11px] font-semibold text-destructive">
                    {f}
                  </span>
                ))}
                <span className="ml-auto text-xs text-muted-foreground">
                  Completed in {replication.result.timing_s}s
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
                {["roc_auc", "gini", "ks", "accuracy", "precision", "recall", "f1"].map((k) => (
                  <div key={k} className="rounded-lg border border-border bg-background p-3">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{k.replace("_", " ")}</div>
                    <div className="mt-1 text-lg font-semibold tabular-nums">
                      {typeof metrics[k] === "number" ? metrics[k].toFixed(3) : "—"}
                    </div>
                  </div>
                ))}
                <div className="rounded-lg border border-border bg-background p-3">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">cv mean auc</div>
                  <div className="mt-1 text-lg font-semibold tabular-nums">
                    {typeof replication.result.cv_mean_auc === "number" ? replication.result.cv_mean_auc.toFixed(3) : "—"}
                  </div>
                </div>
              </div>

              {/* Checks table */}
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-background text-[10px] uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 text-left">ID</th>
                      <th className="px-4 py-2 text-left">Check</th>
                      <th className="px-4 py-2 text-left">Observed</th>
                      <th className="px-4 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {replication.checks.map((c) => (
                      <tr key={c.id}>
                        <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{c.id}</td>
                        <td className="px-4 py-2 font-medium">{c.title}</td>
                        <td className="px-4 py-2 text-xs text-foreground/80">{c.observed ?? "—"}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusStyles[c.status]}`}>
                            <StatusIcon s={c.status} />
                            {c.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Seed stability + ablation charts */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {seedChartData.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Seed stability (R4.6)</h4>
                    <div className="mt-2 h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={seedChartData}>
                          <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                          <XAxis dataKey="seed" tickLine={false} axisLine={false} fontSize={11} />
                          <YAxis tickLine={false} axisLine={false} fontSize={11} domain={[0, 1]} />
                          <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                          <Bar dataKey="auc" fill="oklch(0.55 0.02 240)" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {ablationChartData.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Top feature ablation — AUC drop (R4.5)
                    </h4>
                    <div className="mt-2 h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={ablationChartData} layout="vertical" margin={{ left: 24 }}>
                          <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                          <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} />
                          <YAxis type="category" dataKey="feature" tickLine={false} axisLine={false} fontSize={11} width={110} />
                          <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                          <Bar dataKey="drop" fill="oklch(0.76 0.18 130)" radius={[0, 6, 6, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <XCircle className="h-4 w-4 shrink-0" /> Training failed: {replication.result.error ?? "Unknown error"}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Challenger() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 4 — Replication & Benchmarking"
        description="Replicate developer outputs and benchmark the champion model against approved challengers."
      />

      <ModelReplicationPanel />

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
