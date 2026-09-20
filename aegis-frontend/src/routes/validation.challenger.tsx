import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowRight,
  PlayCircle,
  Loader2,
  UploadCloud,
  FileUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  MinusCircle,
  Database,
  GitCompareArrows,
  ListChecks,
  Settings2,
  Activity,
} from "lucide-react";
import PlotlyChart from "@/components/plotly-chart";
import { formUpload, ApiError } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { useResumeState } from "@/hooks/use-resume-state";
import { cn } from "@/lib/utils";
import {
  StageHero,
  HeroChip,
  VCard,
  VEmptyState,
  StatusPill,
} from "@/components/validation-ui";

export const Route = createFileRoute("/validation/challenger")({
  head: () => ({ meta: [{ title: "Model Replication & Performance — Aegis Credit" }] }),
  component: Challenger,
});

// --- Model Replication + Performance Testing (Stage 3) — real backend-connected panel ---
// Combines what used to be two separate pages: Stage 3 (Model Replication —
// R4.1-R4.8 checks, seed stability, feature ablation) and Stage 4's
// "Performance" tab (metrics, ROC/PR curves, confusion matrix, calibration,
// score distribution). Stage 4 (/validation/performance) is now
// benchmarking-only, since both pages already fit the model the same way
// under the hood (run_replication) — this just stops making the reviewer
// do it twice.

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
  // Provenance of the model configuration this run actually used — set by
  // the backend from real request state, never fabricated. Not surfaced in
  // the UI yet (see the Model Replication Methodology Audit).
  replication_config_source?: "developer_hyperopt_best_params" | "developer_training_config" | "registry_defaults_unavailable_config";
  model_params_used?: Record<string, unknown>;
};

type ReplicationResponse = {
  stage: string;
  flags: string[];
  report: {
    replication: { result: ReplicationResult; checks: ReplicationCheck[] };
    metrics: Record<string, any>;
    roc_curve: { points: Array<Record<string, number>>; auc?: number | null };
    pr_curve: { points: Array<Record<string, number>>; average_precision?: number | null };
    confusion_matrix: { labels: Array<number | string>; matrix: number[][] };
    score_distribution: { bins: Array<Record<string, any>> };
    calibration_chart: { points: Array<Record<string, any>> };
    train_test_auc_gap: { gap?: number | null; status?: string | null; cv_mean_auc?: number | null; test_auc?: number | null };
    threshold_selection?: { threshold: number; metric: string; f1?: number; precision?: number; recall?: number } | null;
    metric_checks?: Array<Record<string, any>>;
    compliance_findings?: Array<Record<string, any>>;
    threshold_analysis?: Array<Record<string, any>>;
  };
};

const metricDefinitions = [
  { key: "roc_auc", label: "ROC-AUC", digits: 3 },
  { key: "gini", label: "Gini", digits: 3 },
  { key: "ks", label: "KS", digits: 3 },
  { key: "accuracy", label: "Accuracy", digits: 3 },
  { key: "precision", label: "Precision", digits: 3 },
  { key: "recall", label: "Recall", digits: 3 },
  { key: "f1", label: "F1 Score", digits: 3 },
  { key: "brier_score", label: "Brier", digits: 3 },
  { key: "pr_auc", label: "PR-AUC", digits: 3 },
];

// Restrained, enterprise-toned per-metric accent for the Performance tab's
// KPI strip — colors only, purely presentational. Each accent pairs a
// Tailwind "-600" value color with its own "-50" tint for the card's top
// bar/indicator, the same value/tint pairing convention BADGE_TONE already
// uses elsewhere in this app.
const PERFORMANCE_KPI_ACCENTS: Record<string, { value: string; tint: string }> = {
  roc_auc: { value: "#4f46e5", tint: "#eef2ff" }, // indigo
  gini: { value: "#7c3aed", tint: "#f5f3ff" }, // violet
  ks: { value: "#0891b2", tint: "#ecfeff" }, // cyan
  accuracy: { value: "#059669", tint: "#ecfdf5" }, // emerald/green
  precision: { value: "#d97706", tint: "#fffbeb" }, // amber/gold
  recall: { value: "#2563eb", tint: "#eff6ff" }, // blue
  f1: { value: "#9333ea", tint: "#faf5ff" }, // purple
  brier_score: { value: "#0d9488", tint: "#f0fdfa" }, // teal
  pr_auc: { value: "#6366f1", tint: "#eef2ff" }, // blue/indigo
};
const KPI_NEUTRAL_ACCENT = { value: "#475569", tint: "#f1f5f9" };

const MODEL_OPTIONS = [
  "Logistic Regression",
  "Random Forest",
  "XGBoost",
  "LightGBM",
  "Gradient Boosting",
];

function formatValue(value: unknown, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return num.toFixed(digits);
}

// Δ with an explicit sign so "improved vs reported" and "degraded vs
// reported" are never ambiguous at a glance.
function formatDelta(value: number | null, digits = 3) {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

const STATUS_TONE: Record<CheckStatus, "pass" | "warn" | "fail" | "na"> = {
  PASS: "pass",
  WARN: "warn",
  FAIL: "fail",
  SKIP: "na",
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

// Maps a reported-metric key to the "Metric" label R4.4's own per-metric
// table (_table) uses, so the comparison below can read that check's real
// PASS/FAIL instead of re-deriving one.
const R44_TABLE_LABEL: Record<string, string> = {
  accuracy: "Accuracy",
  precision: "Precision",
  recall: "Recall",
  f1: "F1",
};

// Same input styling as Model Intake & Governance's `Field` component
// (validation.intake.tsx) — a labeled, bordered box instead of a bare input,
// so Replication Setup reads as the same form language as Intake.
function Field({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={className}>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</div>
      <div className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2.5">{children}</div>
    </div>
  );
}

// Extracts the real numeric tolerance already embedded in a check's own
// title/threshold text (e.g. "Std(AUC) < 0.02", "AUC degradation < 0.05")
// so charts can plot the application's actual threshold instead of a
// frontend-invented one. Returns null (no band/line drawn) if it can't find one.
function parseThresholdValue(text?: string | null): number | null {
  if (!text) return null;
  const match = text.match(/[<≤]\s*([0-9]*\.?[0-9]+)/);
  if (!match) return null;
  const num = Number(match[1]);
  return Number.isFinite(num) ? num : null;
}

// Human-readable label for the backend's real `replication_config_source`,
// never fabricated — only these three values are ever produced (see
// 24-06/main.py). Absent entirely when the field is missing (older runs).
function configProvenanceLabel(source?: ReplicationResult["replication_config_source"]): string | null {
  switch (source) {
    case "developer_hyperopt_best_params":
      return "Developer training configuration (hyperopt-selected parameters)";
    case "developer_training_config":
      return "Developer training configuration";
    case "registry_defaults_unavailable_config":
      return "Registry defaults · developer configuration unavailable";
    default:
      return null;
  }
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = React.useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = () => setReduced(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

// Animates a real KPI value from 0 up to itself, once, whenever `target`
// actually changes to a new real number — a Performance result loading for
// the first time, or a different one replacing it. Purely presentational:
// every intermediate frame is a plain interpolation between 0 and this same
// real `target`, never a fabricated or randomized number, and re-renders
// that don't change `target` (unrelated state elsewhere on the page) never
// replay it. Uses requestAnimationFrame only — no animation dependency.
function useCountUp(target: number | null, durationMs = 700): number | null {
  const reducedMotion = usePrefersReducedMotion();
  const [display, setDisplay] = React.useState<number | null>(target == null ? null : 0);
  const rafRef = React.useRef<number | null>(null);

  // The dependency array below is what already guarantees this only
  // (re-)animates when `target` truly changes to a new real value —
  // re-renders that leave `target` the same primitive number never re-run
  // this effect, so no separate "already animated for this value" guard is
  // needed. (An earlier version added one via a ref and it actively broke
  // this under React's development Strict Mode double-invoke: cleanup
  // cancels the first scheduled frame, and a ref set during the effect body
  // — never cleared by cleanup — then blocked the second, real invocation
  // from ever scheduling a replacement, leaving the value stuck at 0.)
  React.useEffect(() => {
    if (target === null || Number.isNaN(target)) {
      setDisplay(null);
      return;
    }

    if (reducedMotion) {
      setDisplay(target);
      return;
    }

    setDisplay(0);
    const from = 0;
    const to = target;
    const start = performance.now();

    const step = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic — no bounce/overshoot
      if (t < 1) {
        setDisplay(from + (to - from) * eased);
        rafRef.current = requestAnimationFrame(step);
      } else {
        setDisplay(to); // land exactly on the real value — no float drift
        rafRef.current = null;
      }
    };
    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [target, durationMs, reducedMotion]);

  return display;
}

// One KPI tile for the Performance tab's metric strip — label, a
// count-up-animated real value in its metric's accent color, and (only for
// the Train/Test AUC Gap tile) the real PASS/FAIL status already computed
// by the backend. The animated `<span>` is aria-hidden; a static sr-only
// twin carries the real final value so screen readers never depend on
// catching the animation mid-flight.
function KpiAccentCard({
  label,
  value,
  digits = 3,
  accent = KPI_NEUTRAL_ACCENT,
  statusText,
  statusTone,
}: {
  label: string;
  value: number | null;
  digits?: number;
  accent?: { value: string; tint: string };
  statusText?: string | null;
  statusTone?: "pass" | "fail" | "neutral";
}) {
  const display = useCountUp(value, 700);
  const displayText = display == null ? "—" : formatValue(display, digits);
  const finalText = value == null ? "—" : formatValue(value, digits);
  const statusColor = statusTone === "pass" ? "#059669" : statusTone === "fail" ? "#e11d48" : "#64748b";
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
      <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: accent.value }} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-500">{label}</span>
        <span
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
          style={{ background: accent.tint }}
          aria-hidden="true"
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: accent.value }} />
        </span>
      </div>
      <div className="mt-2 text-2xl font-bold tabular-nums" style={{ color: accent.value }}>
        <span aria-hidden="true">{displayText}</span>
        <span className="sr-only">{finalText}</span>
      </div>
      {statusText && (
        <div className="mt-1 flex items-center gap-1.5 text-[11px] font-semibold" style={{ color: statusColor }}>
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: statusColor }} />
          {statusText}
        </div>
      )}
    </div>
  );
}

function ModelReplicationPanel({
  activeSubTab,
  setActiveSubTab,
}: {
  activeSubTab: string;
  setActiveSubTab: (tab: string) => void;
}) {
  const ds = useDataset();

  const [localFile, setLocalFile] = React.useState<File | null>(null);
  const [mddFile, setMddFile] = React.useState<File | null>(null);
  const [targetCol, setTargetCol] = React.useState("");
  // `modelIdentity` is the business/model name; `algorithm` is the technical framework.
  const [modelIdentity, setModelIdentity] = React.useState("");
  const [algorithm, setAlgorithm] = React.useState("XGBoost");
  const [testSize, setTestSize] = React.useState(0.15);
  const [valSize, setValSize] = React.useState(0.15);
  const [reported, setReported] = React.useState<Record<string, string>>({});
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // Seed from shared context so returning to this page (e.g. via Back from
  // Stage 4 — Benchmarking) shows the already-computed R4.1-R4.8 checks,
  // model ranking, and performance report instead of forcing a full rerun —
  // this previously lived only in local state and was lost on every remount.
  const [replication, setReplication] = React.useState<{ result: ReplicationResult; checks: ReplicationCheck[] } | null>(
    (ds.validationStage4Result?.replication as { result: ReplicationResult; checks: ReplicationCheck[] } | null) ?? null,
  );
  const [flags, setFlags] = React.useState<string[]>((ds.validationStage4Result?.flags as string[] | null) ?? []);
  const [performanceReport, setPerformanceReport] = React.useState<ReplicationResponse["report"] | null>(
    (ds.validationStage4Result?.performanceReport as ReplicationResponse["report"] | null) ?? null,
  );

  // Explicit, traceable record of where the currently-displayed replication
  // result came from — a fresh run this session, a resumed historical run
  // (and which one), or neither yet. This is correctness/traceability only;
  // it is not surfaced in the UI yet. `ds.validationStage4Result` (seeded
  // above) was itself produced by a fresh run earlier in this same session,
  // so it counts as "fresh" here, not "resumed".
  type ReplicationProvenance =
    | { kind: "none" }
    | { kind: "fresh" }
    | { kind: "resumed"; runId: string; timestamp: string; businessModelName: string | null; datasetName: string | null };
  const [provenance, setProvenance] = React.useState<ReplicationProvenance>(
    ds.validationStage4Result?.replication ? { kind: "fresh" } : { kind: "none" },
  );

  // The model identity to scope a resumed result by, so a reviewer looking
  // at one model's Setup can never be shown another model's most recent
  // replication run just because it happened more recently system-wide
  // (the /history/latest endpoint otherwise picks the single most recent
  // row across every dataset/model). Sourced the same way the Setup form's
  // own prefill is, so "what would resume" and "what the form shows" agree.
  const resumeModelName = React.useMemo(() => {
    const candidates = [
      ds.selectedModel?.name,
      (ds.trainingResult as Record<string, any> | null | undefined)?.model_name,
      (ds.validationIntakeData as Record<string, any> | null | undefined)?.model_name,
    ];
    const found = candidates.find((v): v is string => Boolean(v && String(v).trim()));
    return found ? found.trim() : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ds.selectedModel?.name, ds.trainingResult, ds.validationIntakeData]);

  // The dataset identity to scope a resumed result by, alongside
  // `resumeModelName` — same model but a DIFFERENT dataset must not resume
  // either. This is the exact same value already shown to the reviewer as
  // "Using {datasetName} from Intake" below (the only dataset identity that
  // exists anywhere in this app — there is no dataset hash/ID to prefer over
  // it), so "what would resume" and "what the Setup screen shows" agree here
  // too, the same way `resumeModelName` already agrees with the Setup form's
  // model name.
  const resumeDatasetName = React.useMemo(() => {
    const p = ds.profile as Record<string, any> | null | undefined;
    const candidates = [p?.dataset_name, p?.name, ds.file?.name];
    const found = candidates.find((v): v is string => Boolean(v && String(v).trim()));
    return found ? found.trim() : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ds.profile, ds.file]);

  // Resume where the reviewer left off: if this session has no replication
  // result yet, pull the last saved /validation/replication run from the
  // backend (this page maps to the "replication" stage since it's the one
  // that actually calls POST /validation/replication).
  //
  // Scoped to BOTH `resumeModelName` and `resumeDatasetName` so this can
  // only ever resume a run logged under the SAME model against the SAME
  // dataset — never simply whichever replication ran most recently for
  // anyone, on any dataset. If either identity is unknown yet (a completely
  // fresh session, or no dataset in context), resuming is disabled entirely
  // rather than falling back to a less-scoped lookup: a wrong result is
  // worse than an empty one.
  const { data: resumedReplication, meta: resumeMeta } = useResumeState<ReplicationResponse>(
    "validation_pipeline_log.csv",
    "replication",
    {
      enabled: Boolean(resumeModelName && resumeDatasetName),
      params: resumeModelName && resumeDatasetName
        ? { business_model_name: resumeModelName, dataset_name: resumeDatasetName }
        : undefined,
    },
  );
  React.useEffect(() => {
    if (!replication && resumedReplication?.report?.replication && resumeMeta) {
      const summary = (resumeMeta.summary ?? {}) as Record<string, any>;
      // Defense in depth: the backend call above already scoped the lookup
      // to `resumeModelName`/`resumeDatasetName`, but re-verify the row's
      // own logged identity here too before ever applying it, so a resumed
      // result can never end up attached to the wrong model or the wrong
      // dataset even if that scoping were ever loosened upstream.
      if (resumeModelName && summary.business_model_name !== resumeModelName) {
        return;
      }
      if (resumeDatasetName && summary.dataset_name !== resumeDatasetName) {
        return;
      }
      setReplication(resumedReplication.report.replication);
      setFlags(resumedReplication.flags ?? []);
      setPerformanceReport(resumedReplication.report);
      setProvenance({
        kind: "resumed",
        runId: resumeMeta.runId,
        timestamp: resumeMeta.timestamp,
        businessModelName: summary.business_model_name ?? null,
        datasetName: summary.dataset_name ?? null,
      });
      ds.setValidationStage4Result({
        replication: resumedReplication.report.replication,
        flags: resumedReplication.flags ?? [],
        performanceReport: resumedReplication.report,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumedReplication, resumeMeta]);

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
    return algorithm.trim();
  }, [algorithm]);

  // The developer's actual recoverable training configuration for THIS
  // model, per the Model Replication Methodology Audit: replication should
  // independently refit using the developer's real config when it's
  // recoverable, not silently fall back to registry defaults. Sourced only
  // from this session's own Model Training run (Stage 5) — never fabricated
  // — and only applied when it demonstrably belongs to the SAME model
  // currently configured here (matched by name), so a different model's
  // training run can never be mistaken for this one's, the same principle
  // already applied to the resume-scoping fix.
  //
  // Priority (do not assume manual_params is final when hyperopt ran):
  //   1. training_info.best_params  — the actual hyperopt-selected params
  //   2. training_config.manual_params — explicit developer overrides
  //   3. (layered onto either 1 or 2) training_config.scale_pos_weight,
  //      only when it was ever actually applied during training (XGBoost,
  //      and > 1 — mirrors get_model_instance()'s own condition exactly)
  // If none of the above yields anything, this is null — the backend then
  // falls back to registry defaults and records that fact explicitly rather
  // than silently.
  const developerModelParams = React.useMemo(() => {
    if (!trainingResult) return null;
    const trModelName = typeof trainingResult.model_name === "string" ? trainingResult.model_name.trim() : "";
    const currentModelName = modelIdentity.trim();
    if (!trModelName || !currentModelName || trModelName !== currentModelName) return null;

    const tc = (trainingResult.training_config ?? {}) as Record<string, any>;
    const ti = (trainingResult.training_info ?? {}) as Record<string, any>;

    const bestParams = ti.best_params;
    const hasBestParams = Boolean(bestParams && typeof bestParams === "object" && Object.keys(bestParams).length > 0);

    const manualParams = tc.manual_params;
    const hasManualParams = Boolean(manualParams && typeof manualParams === "object" && Object.keys(manualParams).length > 0);

    const scalePosWeight = tc.scale_pos_weight;
    const scalePosWeightApplies =
      resolvedAlgorithmName === "XGBoost" && typeof scalePosWeight === "number" && scalePosWeight > 1;

    if (!hasBestParams && !hasManualParams && !scalePosWeightApplies) return null;

    const params: Record<string, unknown> = { ...(hasBestParams ? bestParams : hasManualParams ? manualParams : {}) };
    if (scalePosWeightApplies) params.scale_pos_weight = scalePosWeight;
    if (Object.keys(params).length === 0) return null;

    return {
      params,
      source: hasBestParams ? "developer_hyperopt_best_params" : "developer_training_config",
    } as const;
  }, [trainingResult, modelIdentity, resolvedAlgorithmName]);

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

  // Prefill from whatever the earlier stages already put in context, once.
  const prefilledRef = React.useRef(false);
  React.useEffect(() => {
    if (prefilledRef.current) return;
    const hasContextModel = Boolean(selectedModelName || trainingResult?.model_name || validationIntakeData?.model_name || profile);
    if (!hasContextModel) return;
    prefilledRef.current = true;

    if (targetCandidates[0]) setTargetCol(targetCandidates[0]);

    // Prefill the model identity (business name) if present in prior stages.
    const contextIdentity = [selectedModelName, trainingResult?.model_name, validationIntakeData?.model_name]
      .filter((value): value is string => Boolean(value))
      .map((value) => value.trim())
      .find(Boolean);
    if (contextIdentity) setModelIdentity(contextIdentity);

    // Prefill algorithm if any context value matches a known algorithm option.
    const contextAlg = [selectedModelName, trainingResult?.model_name, validationIntakeData?.model_name]
      .filter((value): value is string => Boolean(value))
      .map((value) => value.trim())
      .find((value) => MODEL_OPTIONS.includes(value));
    if (contextAlg) setAlgorithm(contextAlg);

    if (trainingConfig) {
      if (typeof trainingConfig.test_size === "number") setTestSize(trainingConfig.test_size);
      if (typeof trainingConfig.val_size === "number") setValSize(trainingConfig.val_size);
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

  // Real readiness signal for the Run Replication button — mirrors the exact
  // validation runReplication() itself performs, so "enabled" never disagrees
  // with what happens when the button is actually pressed.
  const datasetReady = Boolean(activeFile);
  const configReady = Boolean(targetCol.trim() && modelIdentity.trim() && resolvedAlgorithmName);
  const canRun = datasetReady && configReady;

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
    if (!modelIdentity.trim()) {
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
    setPerformanceReport(null);
    setProvenance({ kind: "none" });
    try {
      const form = new FormData();
      if (activeFile) {
        form.append("file", activeFile);
      } else if (typeof profile?.csv_text === "string") {
        form.append("csv_text", profile.csv_text);
      }
      form.append("model_name", modelIdentity.trim());
      form.append("algorithm", algorithmName);
      if (validationIntakeData) {
        form.append("intake_json", JSON.stringify(validationIntakeData));
      }
      form.append("target_col", targetCol.trim());
      form.append("test_size", String(testSize));
      form.append("val_size", String(valSize));
      if (mddFile) form.append("mdd_file", mddFile);
      // Developer's actual recoverable training configuration (hyperopt
      // best_params, or explicit manual_params/scale_pos_weight), only when
      // it was found to belong to this same model — see developerModelParams
      // above. When absent, these fields are simply omitted and the backend
      // falls back to registry defaults, recording that fact explicitly
      // rather than silently (replication_config_source on the result).
      if (developerModelParams) {
        form.append("model_params_json", JSON.stringify(developerModelParams.params));
        form.append("model_params_source", developerModelParams.source);
      }

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
      setPerformanceReport(res.report);
      setProvenance({ kind: "fresh" });
      ds.setValidationStage4Result({
        replication: res.report.replication,
        flags: res.flags ?? [],
        performanceReport: res.report,
      });
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
    const aucs = replication?.result?.seed_aucs;
    if (!aucs?.length) return [];
    // R4.6 carries the actual seed integers used for this run — prefer real
    // seed identities over a synthetic "#1, #2…" index when available.
    const realSeeds = replication?.checks?.find((c) => c.id === "R4.6")?._seeds;
    return aucs.map((auc, i) => ({
      seed: realSeeds && realSeeds[i] != null ? `Seed ${realSeeds[i]}` : `Seed ${i + 1}`,
      auc,
    }));
  }, [replication]);

  const ablationChartData = React.useMemo(() => {
    const abl = replication?.result?.ablation;
    if (!abl) return [];
    return Object.entries(abl)
      .filter(([, v]) => typeof v === "number" && !Number.isNaN(v))
      .sort((a, b) => (b[1] as number) - (a[1] as number))
      .slice(0, 10)
      .map(([feature, drop]) => ({ feature, drop: Number((drop as number).toFixed(4)) }));
  }, [replication]);

  // Real tolerance + real "which seed/feature" facts pulled from R4.5/R4.6's
  // own text, so the stability and ablation charts can show the application's
  // actual thresholds without the frontend inventing new ones.
  const seedStats = React.useMemo(() => {
    const aucs = replication?.result?.seed_aucs;
    if (!aucs?.length) return null;
    const mean = aucs.reduce((s, v) => s + v, 0) / aucs.length;
    const variance = aucs.length > 1 ? aucs.reduce((s, v) => s + (v - mean) ** 2, 0) / aucs.length : 0;
    const r46 = replication?.checks?.find((c) => c.id === "R4.6");
    return { mean, std: Math.sqrt(variance), threshold: parseThresholdValue(r46?.title), status: r46?.status ?? null };
  }, [replication]);

  const ablationStats = React.useMemo(() => {
    const r45 = replication?.checks?.find((c) => c.id === "R4.5");
    const maxFeatureMatch = r45?.observed?.match(/removing '([^']+)'/);
    return { threshold: parseThresholdValue(r45?.title), maxFeature: maxFeatureMatch?.[1] ?? null, status: r45?.status ?? null };
  }, [replication]);

  // Enterprise-styling constants for the two diagnostic charts below — colors
  // only, matching the app's existing blue/indigo Aegis language. Purely
  // visual: no effect on which values are plotted or how R4.5/R4.6 status is
  // computed.
  //
  // Deliberately plain hex/rgba, NOT oklch() — Plotly's bundled color parser
  // (tinycolor-based) doesn't understand CSS Color 4 oklch()/lab() syntax and
  // silently falls back to black for anything it can't parse. That's exactly
  // why the pre-existing oklch(...) tokens elsewhere in this file's Plotly
  // figures render as default/black rather than the intended color — verified
  // empirically while building this redesign. Left the other charts (ROC/PR/
  // calibration/etc., outside this task's scope) untouched.
  const CHART_INDIGO = "#4f46e5";
  const CHART_INDIGO_DEEP = "#3730a3";
  const CHART_INDIGO_SOFT = "rgba(79,70,229,0.08)";
  const CHART_GRID = "#eef2ff";
  const CHART_AXIS_LINE = "#475569";
  const CHART_CYAN = "#06b6d4";
  const CHART_ROSE = "#e11d48";
  const CHART_AMBER = "#d97706";
  const CHART_MEAN_LINE = "#64748b";
  const CHART_SPIKE = "#c7d2fe";
  const CHART_THRESHOLD_LINE = "#94a3b8";
  const CHART_EMERALD = "#059669";
  const CHART_HOVERLABEL = { bgcolor: "#ffffff", bordercolor: "#c7d2fe", font: { size: 12, color: "#334155" } };

  const seedFigure = React.useMemo(() => {
    if (!seedChartData.length) return null;
    const seedLabels = seedChartData.map((d) => d.seed);
    const seedValues = seedChartData.map((d) => d.auc);
    const lastIndex = seedValues.length - 1;

    const meanDisplay = seedStats ? seedStats.mean.toFixed(4) : "—";
    const thresholdDisplay = seedStats?.threshold != null ? `± ${seedStats.threshold}` : "n/a";
    const pointCustomData = seedValues.map(() => [meanDisplay, thresholdDisplay]);

    const shapes: any[] = [];
    if (seedStats && seedStats.threshold != null) {
      shapes.push({
        type: "rect",
        xref: "paper",
        x0: 0,
        x1: 1,
        y0: seedStats.mean - seedStats.threshold,
        y1: seedStats.mean + seedStats.threshold,
        fillcolor: CHART_INDIGO_SOFT,
        line: { width: 0 },
        layer: "below",
      });
    }

    // Real-data "latest seed" marker emphasis — the last element of the
    // actual seed_aucs array, not a synthetic/selected value.
    const markerSizes = seedValues.map((_, i) => (i === lastIndex ? 11 : 7));
    const markerLineWidths = seedValues.map((_, i) => (i === lastIndex ? 2.5 : 1.5));
    const markerLineColors = seedValues.map((_, i) => (i === lastIndex ? CHART_INDIGO_DEEP : "white"));

    return {
      data: [
        {
          type: "scatter",
          mode: "lines+markers",
          x: seedLabels,
          y: seedValues,
          line: { color: CHART_INDIGO, width: 2.5, shape: "spline", smoothing: 0.3 },
          marker: { size: markerSizes, color: CHART_INDIGO, line: { width: markerLineWidths, color: markerLineColors } },
          customdata: pointCustomData,
          hovertemplate: "<b>%{x}</b><br>AUC %{y:.4f}<br>Mean AUC %{customdata[0]}<br>Threshold %{customdata[1]}<extra></extra>",
          name: "AUC",
        },
        ...(seedStats
          ? [
              {
                type: "scatter",
                mode: "lines",
                x: seedLabels,
                y: seedLabels.map(() => seedStats.mean),
                line: { color: CHART_MEAN_LINE, width: 1.5, dash: "dash" },
                hovertemplate: "Mean AUC %{y:.4f}<extra></extra>",
                name: "Mean AUC",
              },
            ]
          : []),
      ],
      layout: {
        shapes,
        showlegend: Boolean(seedStats),
        legend: { orientation: "h", y: -0.22, font: { size: 10.5 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 45, r: 20, t: 10, b: seedStats ? 55 : 40 },
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        xaxis: {
          tickfont: { size: 10.5 },
          automargin: true,
          showgrid: false,
          showspikes: true,
          spikemode: "across",
          spikethickness: 1,
          spikedash: "dot",
          spikecolor: CHART_SPIKE,
        },
        yaxis: {
          title: { text: "AUC" },
          tickfont: { size: 11 },
          gridcolor: CHART_GRID,
          zeroline: false,
          showspikes: true,
          spikemode: "across",
          spikethickness: 1,
          spikedash: "dot",
          spikecolor: CHART_SPIKE,
        },
        height: 260,
      },
    };
  }, [seedChartData, seedStats]);

  const ablationFigure = React.useMemo(() => {
    if (!ablationChartData.length) return null;
    const thresholdDisplay = ablationStats.threshold != null ? ablationStats.threshold.toFixed(2) : "n/a";
    const colors = ablationChartData.map((d) =>
      d.feature === ablationStats.maxFeature
        ? ablationStats.status === "FAIL"
          ? CHART_ROSE
          : ablationStats.status === "WARN"
          ? CHART_AMBER
          : d.drop >= 0
          ? CHART_INDIGO
          : CHART_CYAN
        : d.drop >= 0
        ? CHART_INDIGO
        : CHART_CYAN,
    );
    const customData = ablationChartData.map((d) => [
      thresholdDisplay,
      d.feature === ablationStats.maxFeature && ablationStats.status ? ablationStats.status : "—",
    ]);
    const shapes: any[] = [];
    const annotations: any[] = [];
    if (ablationStats.threshold != null) {
      shapes.push({
        type: "line",
        yref: "paper",
        y0: 0,
        y1: 1,
        x0: ablationStats.threshold,
        x1: ablationStats.threshold,
        line: { color: CHART_THRESHOLD_LINE, dash: "dash", width: 1.5 },
      });
      annotations.push({
        x: ablationStats.threshold,
        y: 1,
        yref: "paper",
        yanchor: "bottom",
        text: "R4.5 limit",
        showarrow: false,
        font: { size: 9.5, color: CHART_THRESHOLD_LINE },
      });
    }
    return {
      data: [
        {
          type: "bar",
          orientation: "h",
          x: ablationChartData.map((d) => d.drop),
          y: ablationChartData.map((d) => d.feature),
          marker: { color: colors, cornerradius: 3 },
          customdata: customData,
          hovertemplate: "<b>%{y}</b><br>AUC change: %{x:.4f}<br>Threshold: %{customdata[0]}<br>Status: %{customdata[1]}<extra></extra>",
          name: "AUC Δ",
        },
      ],
      layout: {
        shapes,
        annotations,
        showlegend: false,
        bargap: 0.35,
        margin: { l: 150, r: 24, t: 24, b: 40 },
        hoverlabel: CHART_HOVERLABEL,
        xaxis: {
          title: { text: "AUC Δ on removal" },
          tickfont: { size: 11 },
          automargin: true,
          gridcolor: CHART_GRID,
          zeroline: true,
          zerolinecolor: CHART_AXIS_LINE,
          zerolinewidth: 1.5,
        },
        yaxis: { tickfont: { size: 11 }, automargin: true, autorange: "reversed", showgrid: false },
        height: Math.max(224, ablationChartData.length * 30 + 70),
      },
    };
  }, [ablationChartData, ablationStats]);

  // Which color categories actually appear in this run's real ablation
  // values — drives the small legend below so it never lists a category
  // that has no bars for it.
  const ablationLegend = React.useMemo(() => {
    const hasPositive = ablationChartData.some((d) => d.drop >= 0);
    const hasNegative = ablationChartData.some((d) => d.drop < 0);
    const hasCritical = Boolean(ablationStats.maxFeature) && (ablationStats.status === "FAIL" || ablationStats.status === "WARN");
    return { hasPositive, hasNegative, hasCritical };
  }, [ablationChartData, ablationStats]);

  const metrics = replication?.result?.metrics ?? {};

  // Real reported values, parsed to numbers where the reviewer actually
  // entered/extracted one — used only for the informational Reference vs
  // Replicated delta tiles, never for a derived pass/fail verdict (that
  // comes solely from the real R4.x checks below).
  const reportedNumeric = React.useMemo(() => {
    const out: Record<string, number | null> = {};
    for (const { key } of REPORTED_METRIC_FIELDS) {
      const raw = reported[key];
      const num = raw !== undefined && raw !== "" ? Number(raw) : NaN;
      out[key] = Number.isFinite(num) ? num : null;
    }
    return out;
  }, [reported]);

  const checkCounts = React.useMemo(() => {
    const checks = replication?.checks ?? [];
    return {
      total: checks.length,
      pass: checks.filter((c) => c.status === "PASS").length,
      fail: checks.filter((c) => c.status === "FAIL").length,
      warn: checks.filter((c) => c.status === "WARN").length,
    };
  }, [replication]);

  // Reference (developer-reported) vs Replicated, per metric — status comes
  // straight from the real R4.2/R4.3/R4.4/R4.8 check verdicts already
  // computed by the backend (R4.4's own _table gives a per-metric verdict
  // for accuracy/precision/recall/f1; R4.2/R4.3/R4.8 give one verdict each
  // for roc_auc, gini+ks, and cv_mean_auc respectively). No thresholds are
  // invented here — a metric with no corresponding check simply has no status.
  const comparisonRows = React.useMemo(() => {
    if (!replication?.result?.success) return [];
    const r42 = replication.checks.find((c) => c.id === "R4.2");
    const r43 = replication.checks.find((c) => c.id === "R4.3");
    const r44 = replication.checks.find((c) => c.id === "R4.4");
    const r48 = replication.checks.find((c) => c.id === "R4.8");
    return REPORTED_METRIC_FIELDS.map(({ key, label }) => {
      const replicatedValue =
        key === "cv_mean_auc"
          ? replication.result.cv_mean_auc ?? null
          : typeof metrics[key] === "number"
          ? metrics[key]
          : null;
      const reportedValue = reportedNumeric[key] ?? null;
      const delta = replicatedValue !== null && reportedValue !== null ? replicatedValue - reportedValue : null;

      let status: CheckStatus | null = null;
      if (key === "roc_auc") status = r42?.status ?? null;
      else if (key === "gini" || key === "ks") status = r43?.status ?? null;
      else if (key === "cv_mean_auc") status = r48?.status ?? null;
      else if (R44_TABLE_LABEL[key]) {
        const row = r44?._table?.find((r) => String(r.Metric) === R44_TABLE_LABEL[key]);
        status = (row?.Status as CheckStatus | undefined) ?? null;
      }
      // Gini and KS share a single joint R4.3 verdict in the backend rather
      // than two independent ones — flag that so the table doesn't imply
      // they were checked separately.
      const joint = key === "gini" || key === "ks";
      return { key, label, replicatedValue, reportedValue, delta, status, joint };
    });
  }, [replication, reportedNumeric, metrics]);


  // --- Performance tab data (ported from the old Stage 4 "Performance" tab) ---
  // Same validity gate `formatValue` itself applies (null/undefined/NaN ->
  // excluded) — kept in raw numeric form now, instead of a pre-formatted
  // string, so the KPI strip can animate each real value from 0 up to
  // itself and still finish on the exact same formatted string this used to
  // render directly.
  const metricCards = React.useMemo(() => {
    const m = performanceReport?.metrics ?? {};
    return metricDefinitions
      .map((item) => {
        const raw = m[item.key];
        const num = Number(raw);
        const valid = raw !== null && raw !== undefined && !Number.isNaN(num) && Number.isFinite(num);
        return { key: item.key, label: item.label, digits: item.digits, raw: valid ? num : null };
      })
      .filter((item) => item.raw !== null);
  }, [performanceReport]);

  const gap = performanceReport?.train_test_auc_gap;
  const rocPoints = performanceReport?.roc_curve?.points ?? [];
  const prPoints = performanceReport?.pr_curve?.points ?? [];
  const scoreBins = performanceReport?.score_distribution?.bins ?? [];
  const calibrationPoints = performanceReport?.calibration_chart?.points ?? [];
  const confusionMatrix = performanceReport?.confusion_matrix;
  const thresholdSelection = performanceReport?.threshold_selection;

  // Performance-tab figures — same fix as the Replication Stability/Feature
  // Ablation charts above: no hardcoded `layout.height` (that's what let the
  // plot draw taller than its card and overflow), hex/rgba colors instead of
  // oklch (Plotly's bundled color parser can't parse oklch() and silently
  // falls back to black), and a polished light hoverlabel. `autosize: true`
  // plus the shared config's `responsive: true` let Plotly size itself to
  // whatever the wrapping card actually measures, so the chart can never
  // disagree with its container again.
  const rocFigure = React.useMemo(() => {
    const fpr = rocPoints.map((point) => point.fpr);
    const tpr = rocPoints.map((point) => point.tpr);
    const diagonal = rocPoints.map((point) => point.fpr);
    return {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x: fpr,
          y: tpr,
          line: { color: CHART_INDIGO, width: 2.5 },
          fill: "tozeroy",
          fillcolor: CHART_INDIGO_SOFT,
          hovertemplate: "<b>TPR</b> %{y:.3f}<br><b>FPR</b> %{x:.3f}<extra></extra>",
          name: "ROC",
        },
        {
          type: "scatter",
          mode: "lines",
          x: diagonal,
          y: diagonal,
          line: { color: CHART_THRESHOLD_LINE, width: 1.5, dash: "dash" },
          hoverinfo: "skip",
          showlegend: false,
          name: "Random",
        },
      ],
      layout: {
        autosize: true,
        showlegend: false,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        margin: { l: 45, r: 16, t: 10, b: 40 },
        xaxis: { title: { text: "False Positive Rate" }, tickfont: { size: 11 }, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "True Positive Rate" }, tickfont: { size: 11 }, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [rocPoints]);

  const prFigure = React.useMemo(() => {
    const recall = prPoints.map((point) => point.recall);
    const precision = prPoints.map((point) => point.precision);
    return {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x: recall,
          y: precision,
          line: { color: CHART_INDIGO, width: 2.5 },
          fill: "tozeroy",
          fillcolor: CHART_INDIGO_SOFT,
          hovertemplate: "<b>Precision</b> %{y:.3f}<br><b>Recall</b> %{x:.3f}<extra></extra>",
          name: "PR",
        },
      ],
      layout: {
        autosize: true,
        showlegend: false,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        margin: { l: 45, r: 16, t: 10, b: 40 },
        xaxis: { title: { text: "Recall" }, tickfont: { size: 11 }, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "Precision" }, tickfont: { size: 11 }, range: [0, 1], gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [prPoints]);

  const calibrationFigure = React.useMemo(() => {
    const pred = calibrationPoints.map((point) => point.predicted_rate);
    const actual = calibrationPoints.map((point) => point.actual_rate);
    return {
      data: [
        {
          type: "scatter",
          mode: "lines",
          x: pred,
          y: actual,
          line: { color: CHART_INDIGO, width: 2.5 },
          hovertemplate: "<b>Actual</b> %{y:.3f}<br><b>Predicted</b> %{x:.3f}<extra></extra>",
          name: "Actual",
        },
        {
          type: "scatter",
          mode: "lines",
          x: pred,
          y: pred,
          line: { color: CHART_THRESHOLD_LINE, width: 1.5, dash: "dash" },
          hoverinfo: "skip",
          showlegend: false,
          name: "Perfect",
        },
      ],
      layout: {
        autosize: true,
        showlegend: false,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        margin: { l: 45, r: 16, t: 10, b: 40 },
        xaxis: { title: { text: "Predicted rate" }, tickfont: { size: 11 }, gridcolor: CHART_GRID, zeroline: false, showline: false },
        yaxis: { title: { text: "Observed rate" }, tickfont: { size: 11 }, gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [calibrationPoints]);

  const scoreDistributionFigure = React.useMemo(() => {
    const bins = scoreBins.map((bin) => bin.bin);
    const good = scoreBins.map((bin) => bin.good ?? 0);
    const bad = scoreBins.map((bin) => bin.bad ?? 0);
    return {
      data: [
        {
          type: "bar",
          x: bins,
          y: good,
          name: "Good",
          marker: { color: CHART_EMERALD },
          hovertemplate: "<b>Bin %{x}</b><br>Good: %{y}<extra></extra>",
        },
        {
          type: "bar",
          x: bins,
          y: bad,
          name: "Bad",
          marker: { color: CHART_ROSE },
          hovertemplate: "<b>Bin %{x}</b><br>Bad: %{y}<extra></extra>",
        },
      ],
      layout: {
        autosize: true,
        barmode: "stack",
        bargap: 0.25,
        hovermode: "closest",
        hoverlabel: CHART_HOVERLABEL,
        legend: { orientation: "h", y: -0.28, font: { size: 10.5 }, bgcolor: "rgba(0,0,0,0)" },
        margin: { l: 45, r: 16, t: 10, b: 55 },
        xaxis: {
          title: { text: "Score bin" },
          tickfont: { size: 10.5 },
          automargin: true,
          tickangle: bins.length > 8 ? -45 : 0,
          gridcolor: CHART_GRID,
          zeroline: false,
          showline: false,
        },
        yaxis: { title: { text: "Count" }, tickfont: { size: 11 }, gridcolor: CHART_GRID, zeroline: false, showline: false },
      },
    };
  }, [scoreBins]);

  return (
    <div className="space-y-6">
      <VCard
        icon={Settings2}
        title="Model Replication"
        sub="Independently re-train the submitted model on the validation dataset and run checks R4.1–R4.8 against developer-reported metrics."
      >
        {/* Dataset & Model */}
        <div className="text-[11px] font-bold uppercase tracking-wider text-blue-700">Dataset &amp; Model</div>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
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
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-500 hover:border-blue-400">
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

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Model Name (business identity)">
            <input
              value={modelIdentity}
              onChange={(e) => setModelIdentity(e.target.value)}
              placeholder="e.g. Credit Risk PD Model"
              className="w-full bg-transparent text-sm font-medium text-slate-800 outline-none"
            />
          </Field>
          <Field label="Algorithm / Framework">
            <select
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value)}
              className="w-full cursor-pointer bg-transparent text-sm font-semibold text-slate-800 outline-none"
            >
              {MODEL_OPTIONS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {/* Validation Configuration */}
        <div className="mt-6 text-[11px] font-bold uppercase tracking-wider text-blue-700">Validation Configuration</div>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Target Column">
            <input
              list="replication-target-candidates"
              value={targetCol}
              onChange={(e) => setTargetCol(e.target.value)}
              placeholder="e.g. default_flag"
              className="w-full bg-transparent font-mono text-sm font-semibold text-slate-900 outline-none"
            />
            <datalist id="replication-target-candidates">
              {[...targetCandidates, ...allColumns].map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </Field>
          <Field label="Test Size">
            <input
              type="number"
              step={0.01}
              min={0.05}
              max={0.4}
              value={testSize}
              onChange={(e) => setTestSize(Number(e.target.value))}
              className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none"
            />
          </Field>
          <Field label="Validation Size">
            <input
              type="number"
              step={0.01}
              min={0.05}
              max={0.4}
              value={valSize}
              onChange={(e) => setValSize(Number(e.target.value))}
              className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none"
            />
          </Field>
        </div>

        {/* Developer Reference Metrics */}
        <div className="mt-6 text-[11px] font-bold uppercase tracking-wider text-blue-700">Developer Reference Metrics</div>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              For checks R4.2 / R4.3 / R4.4 / R4.8 — auto-filled from this dataset's training run where available.
              Edit any value, or leave blank to skip that check. Values extracted from an uploaded MDD override these on run.
            </p>
            <label className="inline-flex shrink-0 cursor-pointer items-center gap-2 text-xs text-primary underline underline-offset-2">
              <FileUp className="h-3.5 w-3.5" />
              {mddFile ? mddFile.name : "Upload MDD (PDF/DOCX/TXT)"}
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => setMddFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {REPORTED_METRIC_FIELDS.map(({ key, label }) => (
              <div key={key}>
                <label className="text-[11px] text-muted-foreground">{label}</label>
                <input
                  value={reported[key] ?? ""}
                  onChange={(e) => setReported((prev) => ({ ...prev, [key]: e.target.value }))}
                  placeholder="—"
                  className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Run + result summary — stays inside the same setup card, same as
            the dataset/config/reference-metrics blocks above it. */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-5">
          <button
            onClick={runReplication}
            disabled={loading || !canRun}
            className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            {loading ? "Running replication…" : "Run Replication"}
            {!loading && <ArrowRight className="h-4 w-4" />}
          </button>

          {replication && replication.result.success && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs">
              <StatusPill tone={checkCounts.fail === 0 ? "pass" : "fail"}>
                {checkCounts.fail === 0 ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                {checkCounts.fail === 0 ? "Passed" : "Failed"}
              </StatusPill>
              <span className="font-medium text-slate-600">
                {checkCounts.pass}/{checkCounts.total} checks passed
              </span>
              {flags.length > 0 && (
                <span className="inline-flex flex-wrap items-center gap-1.5 font-bold text-red-600">
                  {flags.length} FAILING
                  {flags.map((id) => (
                    <span key={id} className="rounded border border-red-200 bg-red-100 px-1.5 py-0.5 text-[10px]">
                      {id}
                    </span>
                  ))}
                </span>
              )}
              <span className="text-slate-400">Completed in {replication.result.timing_s}s</span>
            </div>
          )}
        </div>

        {replication?.result?.success && configProvenanceLabel(replication.result.replication_config_source) && (
          <p className="mt-2 text-[11px] text-slate-400">
            Configuration: {configProvenanceLabel(replication.result.replication_config_source)}
          </p>
        )}

        {loading && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-blue-700">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> In progress
            </div>
            <ul className="mt-2 grid grid-cols-1 gap-1 text-xs text-slate-600 sm:grid-cols-2">
              <li>• Preparing the validation dataset and split</li>
              <li>• Reproducing the model end-to-end</li>
              <li>• Calculating performance metrics</li>
              <li>• Running R4.1–R4.8 replication checks</li>
              <li>• Generating stability and ablation diagnostics</li>
            </ul>
          </div>
        )}
      </VCard>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <XCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Purposeful empty state before the first run, instead of a blank gap */}
      {!replication && !loading && (
        <VEmptyState
          icon={GitCompareArrows}
          title="Replication has not been run yet"
          description="Configure the dataset, target column, and model above, then run replication to see the R4.1–R4.8 checks and performance profile."
        />
      )}

      {/* Results */}
      {replication && (
        replication.result.success ? (
          <>
            <Tabs value={activeSubTab} onValueChange={setActiveSubTab} className="w-full">
              <TabsList>
                <TabsTrigger value="replication">Replication Checks</TabsTrigger>
                <TabsTrigger value="performance">Performance</TabsTrigger>
              </TabsList>

              <TabsContent value="replication" className="space-y-6 pt-4">
                <VCard
                  icon={GitCompareArrows}
                  title="Reference vs Replicated Performance"
                  sub="Developer-reported metrics compared against this independent reproduction"
                  contentClassName="-mx-6 -mb-6"
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-y border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                          <th className="px-6 py-3 text-left">Metric</th>
                          <th className="px-4 py-3 text-right">Reported</th>
                          <th className="px-4 py-3 text-right">Replicated</th>
                          <th className="px-4 py-3 text-right">Δ</th>
                          <th className="px-6 py-3 text-left">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {comparisonRows.map((row) => (
                          <tr key={row.key} className="hover:bg-slate-50/60">
                            <td className="px-6 py-3.5 font-medium text-slate-900">
                              {row.label}
                              {row.joint && <span className="ml-2 text-[10px] font-normal uppercase tracking-wide text-slate-400">joint check</span>}
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono text-xs text-slate-600">{formatValue(row.reportedValue)}</td>
                            <td className="px-4 py-3.5 text-right font-mono text-xs text-slate-900">{formatValue(row.replicatedValue)}</td>
                            <td className={cn("px-4 py-3.5 text-right font-mono text-xs", row.delta === null ? "text-slate-400" : row.delta === 0 ? "text-slate-600" : row.delta > 0 ? "text-emerald-600" : "text-rose-600")}>
                              {formatDelta(row.delta)}
                            </td>
                            <td className="px-6 py-3.5">
                              {row.status ? (
                                <StatusPill tone={STATUS_TONE[row.status]}>
                                  <StatusIcon s={row.status} />
                                  {row.status}
                                </StatusPill>
                              ) : (
                                <span className="text-xs text-slate-400">No automated check</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </VCard>

                <VCard
                  icon={ListChecks}
                  title="Replication Check Results"
                  sub="R4.1 – R4.8 automated validation checks"
                  badge={{ text: `${checkCounts.pass}/${checkCounts.total} passed`, tone: "primary" }}
                  contentClassName="-mx-6 -mb-6"
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-y border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                          <th className="px-6 py-3 text-left">ID</th>
                          <th className="px-4 py-3 text-left">Check</th>
                          <th className="px-4 py-3 text-left">Observed</th>
                          <th className="px-4 py-3 text-left">Expected / Threshold</th>
                          <th className="px-6 py-3 text-left">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {replication.checks.map((c) => (
                          <tr
                            key={c.id}
                            className={cn(
                              "border-l-4",
                              c.status === "FAIL" ? "border-l-rose-400 bg-red-50/40"
                                : c.status === "WARN" ? "border-l-amber-400"
                                : c.status === "PASS" ? "border-l-emerald-400"
                                : "border-l-slate-200",
                              "hover:bg-slate-50/60",
                            )}
                          >
                            <td className="px-6 py-3.5 font-mono text-xs text-slate-400">{c.id}</td>
                            <td className="px-4 py-3.5 font-medium text-slate-900">{c.title}</td>
                            <td className="px-4 py-3.5 text-xs text-slate-600">{c.observed ?? "—"}</td>
                            <td className="px-4 py-3.5 text-xs text-slate-500">{c.threshold ?? "—"}</td>
                            <td className="px-6 py-3.5">
                              <StatusPill tone={STATUS_TONE[c.status]}>
                                <StatusIcon s={c.status} />
                                {c.status}
                              </StatusPill>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </VCard>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <VCard
                    title="Replication Stability Across Seeds"
                    sub="Variation in independently reproduced AUC across random seeds"
                    badge={seedStats?.status ? { text: seedStats.status, tone: seedStats.status === "PASS" ? "emerald" : seedStats.status === "FAIL" ? "rose" : "amber" } : undefined}
                  >
                    {seedFigure ? (
                      <>
                        <div className="h-[260px] rounded-xl border border-slate-100 bg-white p-1">
                          <PlotlyChart figure={seedFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                        </div>
                        {seedStats && (
                          <p className="mt-2 text-[11px] text-slate-400">
                            Mean AUC {seedStats.mean.toFixed(4)} · Std {seedStats.std.toFixed(4)}
                            {seedStats.threshold != null ? ` · threshold < ${seedStats.threshold}` : ""}
                          </p>
                        )}
                      </>
                    ) : (
                      <VEmptyState icon={Activity} title="No seed stability data yet" description="Run replication to see AUC variation across random seeds." />
                    )}
                  </VCard>

                  <VCard
                    title="Feature Ablation Impact"
                    sub="Change in AUC when individual features are removed"
                    badge={ablationStats.status ? { text: ablationStats.status, tone: ablationStats.status === "PASS" ? "emerald" : ablationStats.status === "FAIL" ? "rose" : "amber" } : undefined}
                  >
                    {ablationFigure ? (
                      <>
                        {(ablationLegend.hasPositive || ablationLegend.hasNegative || ablationLegend.hasCritical) && (
                          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10.5px] text-slate-500">
                            {ablationLegend.hasPositive && (
                              <span className="inline-flex items-center gap-1.5">
                                <span className="h-2 w-2 rounded-full" style={{ background: "#4f46e5" }} />
                                AUC decreases when removed
                              </span>
                            )}
                            {ablationLegend.hasNegative && (
                              <span className="inline-flex items-center gap-1.5">
                                <span className="h-2 w-2 rounded-full" style={{ background: "#06b6d4" }} />
                                AUC increases when removed
                              </span>
                            )}
                            {ablationLegend.hasCritical && (
                              <span className="inline-flex items-center gap-1.5">
                                <span
                                  className="h-2 w-2 rounded-full"
                                  style={{ background: ablationStats.status === "FAIL" ? "#e11d48" : "#d97706" }}
                                />
                                Exceeds R4.5 threshold
                              </span>
                            )}
                          </div>
                        )}
                        <div className="rounded-xl border border-slate-100 bg-white p-1" style={{ height: ablationFigure.layout.height }}>
                          <PlotlyChart figure={ablationFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                        </div>
                      </>
                    ) : (
                      <VEmptyState icon={ListChecks} title="No ablation data yet" description="Run replication to see the impact of removing each feature." />
                    )}
                  </VCard>
                </div>
              </TabsContent>

              <TabsContent value="performance" className="space-y-6 pt-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                  {metricCards.map((m) => (
                    <KpiAccentCard
                      key={m.key}
                      label={m.label}
                      value={m.raw}
                      digits={m.digits}
                      accent={PERFORMANCE_KPI_ACCENTS[m.key] ?? KPI_NEUTRAL_ACCENT}
                    />
                  ))}
                  <KpiAccentCard
                    label="Train/Test AUC Gap"
                    value={typeof gap?.gap === "number" && Number.isFinite(gap.gap) ? gap.gap : null}
                    digits={3}
                    accent={gap?.status === "PASS" ? { value: "#059669", tint: "#ecfdf5" } : gap?.status === "FAIL" ? { value: "#e11d48", tint: "#fff1f2" } : KPI_NEUTRAL_ACCENT}
                    statusText={gap?.status ?? null}
                    statusTone={gap?.status === "PASS" ? "pass" : gap?.status === "FAIL" ? "fail" : "neutral"}
                  />
                </div>

                <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <VCard className="min-w-0" title="ROC curve" sub={`AUC ${formatValue(performanceReport?.roc_curve?.auc, 3)}`}>
                    <div className="h-[300px] min-w-0 overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                      <PlotlyChart figure={rocFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                    </div>
                  </VCard>

                  <VCard className="min-w-0" title="Precision–Recall" sub={`Average precision ${formatValue(performanceReport?.pr_curve?.average_precision, 3)}`}>
                    <div className="h-[300px] min-w-0 overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                      <PlotlyChart figure={prFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                    </div>
                  </VCard>

                  <VCard
                    className="min-w-0"
                    title="Confusion matrix"
                    sub={
                      thresholdSelection
                        ? `Threshold ${formatValue(thresholdSelection.threshold, 2)} (auto-calibrated for max F1)`
                        : "Threshold —"
                    }
                  >
                    <div className="flex h-[300px] min-w-0 flex-col overflow-hidden rounded-xl border border-slate-100 bg-slate-50/40 p-4">
                      <div className="mb-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        Predicted
                      </div>
                      <div className="flex min-h-0 flex-1 items-stretch gap-2">
                        <div className="flex items-center">
                          <span className="w-4 origin-center -rotate-90 whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                            Actual
                          </span>
                        </div>
                        <div className="grid min-w-0 flex-1 grid-cols-2 gap-3">
                          {confusionMatrix?.matrix?.length === 2
                            ? confusionMatrix.matrix.flatMap((row, rowIndex) =>
                                row.map((value, colIndex) => {
                                  // Standard binary quadrant labels — row 0 = Actual
                                  // negative, col 0 = Predicted negative, matching
                                  // the real backend's labels/matrix ordering.
                                  const quadrant =
                                    rowIndex === 0 && colIndex === 0 ? { label: "TN", classes: "border-blue-200 bg-blue-50 text-blue-800" }
                                    : rowIndex === 0 && colIndex === 1 ? { label: "FP", classes: "border-red-200 bg-red-50 text-red-700" }
                                    : rowIndex === 1 && colIndex === 0 ? { label: "FN", classes: "border-amber-200 bg-amber-50 text-amber-700" }
                                    : { label: "TP", classes: "border-emerald-200 bg-emerald-50 text-emerald-800" };
                                  return (
                                    <div key={`${rowIndex}-${colIndex}`} className={`flex flex-col justify-between rounded-xl border p-4 shadow-sm ${quadrant.classes}`}>
                                      <span className="text-[10.5px] font-bold uppercase tracking-wider opacity-70">{quadrant.label}</span>
                                      <span className="font-mono text-3xl font-bold tabular-nums">{value.toLocaleString()}</span>
                                    </div>
                                  );
                                }),
                              )
                            : confusionMatrix?.matrix?.length
                            ? confusionMatrix.matrix.flatMap((row, rowIndex) =>
                                row.map((value, colIndex) => {
                                  const label = confusionMatrix.labels?.[colIndex] ?? colIndex;
                                  const isCorrect = rowIndex === colIndex;
                                  const classes = isCorrect ? "border-blue-200 bg-blue-50 text-blue-800" : "border-red-200 bg-red-50 text-red-700";
                                  return (
                                    <div key={`${rowIndex}-${colIndex}`} className={`flex flex-col justify-between rounded-xl border p-4 shadow-sm ${classes}`}>
                                      <span className="text-[11px] uppercase tracking-wider opacity-70">
                                        Predicted {label} · Actual {confusionMatrix.labels?.[rowIndex] ?? rowIndex}
                                      </span>
                                      <span className="font-mono text-3xl font-bold tabular-nums">{value.toLocaleString()}</span>
                                    </div>
                                  );
                                }),
                              )
                            : null}
                        </div>
                      </div>
                    </div>
                  </VCard>

                  <VCard className="min-w-0" title="Calibration" sub="Predicted vs observed default rate">
                    <div className="h-[300px] min-w-0 overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                      <PlotlyChart figure={calibrationFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                    </div>
                  </VCard>

                  <VCard className="min-w-0" title="Score distribution" sub={`Hold-out set · KS ${formatValue(performanceReport?.metrics?.ks, 3)}`}>
                    <div className="h-[300px] min-w-0 overflow-hidden rounded-xl border border-slate-100 bg-white p-1">
                      <PlotlyChart figure={scoreDistributionFigure} style={{ height: "100%" }} config={{ displayModeBar: false, scrollZoom: false }} />
                    </div>
                  </VCard>
                </section>
              </TabsContent>
            </Tabs>
          </>
        ) : (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <XCircle className="h-4 w-4 shrink-0" /> Training failed: {replication.result.error ?? "Unknown error"}
          </div>
        )
      )}

      <div className="flex justify-end pb-2">
        {activeSubTab === "replication" ? (
          <button
            type="button"
            onClick={() => setActiveSubTab("performance")}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[#2f67ff] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
          >
            Continue
            <ArrowRight className="h-4 w-4" />
          </button>
        ) : (
          <Link
            to="/validation/performance"
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[#2f67ff] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
          >
            Continue to Stage 4 — Benchmarking
            <ArrowRight className="h-4 w-4" />
          </Link>
        )}
      </div>
    </div>
  );
}

function Challenger() {
  // Tracks which sub-tab is active so the bottom button can tell whether
  // the reviewer is still on the first sub-tab (Replication Checks —
  // button just advances to Performance) or the last one (button
  // navigates to Stage 4).
  const [activeSubTab, setActiveSubTab] = React.useState<string>("replication");

  return (
    <div className="space-y-6">
      <StageHero
        eyebrow="STAGE 3 · MODEL VALIDATION"
        title="Model Replication & Performance Testing"
        description="Independently reproduce the submitted model, compare developer-reported results with independently generated results, and assess replication stability."
        chips={
          <>
            <HeroChip tone={activeSubTab === "replication" ? "success" : "neutral"}>Replication</HeroChip>
            <HeroChip tone={activeSubTab === "performance" ? "success" : "neutral"}>Performance review</HeroChip>
          </>
        }
      />

      <ModelReplicationPanel activeSubTab={activeSubTab} setActiveSubTab={setActiveSubTab} />
    </div>
  );
}
