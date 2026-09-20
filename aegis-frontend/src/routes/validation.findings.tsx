import { createFileRoute, Link } from "@tanstack/react-router";
import React from "react";
import {
  ArrowRight,
  AlertTriangle,
  RefreshCw,
  Printer,
  ChevronDown,
  ChevronRight,
  FileText,
  Gauge,
  Download,
  Users,
  CheckCircle2,
  XCircle,
  ClipboardList,
  Database,
} from "lucide-react";
import { ApiError, formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { useResumeState } from "@/hooks/use-resume-state";
import { StageHero, HeroChip, VCard, KpiStrip, StatusPill, VEmptyState } from "@/components/validation-ui";

export const Route = createFileRoute("/validation/findings")({
  head: () => ({ meta: [{ title: "Stage 7 — Findings & Final Report — Aegis Credit" }] }),
  component: Findings,
});

type Finding = {
  stage: string;
  check: string;
  severity: string;
  status: string;
  finding: string;
  recommendation: string;
  regulation: string;
};

type Stage8Response = {
  findings: Finding[];
  verdict: "APPROVED" | "CONDITIONALLY APPROVED" | "REJECTED" | string;
  verdict_desc: string;
  high_count: number;
  medium_count: number;
  low_count: number;
  total_count: number;
  monitoring_frequency: string;
  revalidation_trigger: string;
  model_tier: string;
  stated_auc: number | null;
  replicated_auc: number | null;
};

type RemediationRow = {
  finding: string;
  severity: string;
  detail: string;
  owner: string;
  targetDate: string;
  status: string;
};

const VERDICT_BADGE_TONE: Record<string, "emerald" | "amber" | "rose"> = {
  APPROVED: "emerald",
  "CONDITIONALLY APPROVED": "amber",
  REJECTED: "rose",
};

// Text-color counterpart to VERDICT_BADGE_TONE, used for the large verdict
// headline in the Overall Verdict section — same tone mapping, just a
// foreground color instead of a badge background.
const VERDICT_TEXT_TONE: Record<string, string> = {
  APPROVED: "text-emerald-600",
  "CONDITIONALLY APPROVED": "text-amber-600",
  REJECTED: "text-rose-600",
};

const VERDICT_ICON: Record<string, typeof CheckCircle2> = {
  APPROVED: CheckCircle2,
  "CONDITIONALLY APPROVED": AlertTriangle,
  REJECTED: XCircle,
};

const SEVERITY_STYLES: Record<string, { border: string; bg: string; badge: string }> = {
  HIGH: { border: "border-red-200", bg: "bg-red-50", badge: "border-red-200 bg-red-50 text-red-700" },
  MEDIUM: { border: "border-amber-200", bg: "bg-amber-50", badge: "border-amber-200 bg-amber-50 text-amber-700" },
  LOW: { border: "border-emerald-200", bg: "bg-emerald-50", badge: "border-emerald-200 bg-emerald-50 text-emerald-700" },
};

function severityStyle(sev: string) {
  return SEVERITY_STYLES[sev?.toUpperCase()] ?? { border: "border-slate-200", bg: "bg-slate-50", badge: "border-slate-200 bg-slate-100 text-slate-700" };
}

// Finding/remediation `status` values returned by /validation/stage8/findings
// are plain "FAIL"/"WARN" strings (main.py) — mapped to the same StatusPill
// tone language already used for the Performance Metrics table on this page
// and every other redesigned validation stage, so a reviewer reads FAIL/WARN
// the same way everywhere in Aegis instead of a generic bold-text label.
function statusTone(status: string | undefined): "pass" | "warn" | "fail" | "pending" {
  switch ((status ?? "").toUpperCase()) {
    case "PASS":
      return "pass";
    case "WARN":
      return "warn";
    case "FAIL":
      return "fail";
    default:
      return "pending";
  }
}

function csvEscape(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCsv(filename: string, rows: Array<Record<string, unknown>>) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(","), ...rows.map((r) => headers.map((h) => csvEscape(r[h])).join(","))];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function todayLabel() {
  return new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// Plain-English justification for the verdict — mirrors the exact thresholds
// the /validation/stage8/findings endpoint uses to decide it (main.py: verdict
// is APPROVED iff 0 HIGH findings and <=2 MEDIUM; CONDITIONALLY APPROVED iff
// <=2 HIGH findings; REJECTED otherwise). Kept in sync with that logic rather
// than re-deriving it, since the API only returns the outcome, not the "why".
function verdictReasoning(data: Stage8Response): string {
  const { verdict, high_count, medium_count } = data;
  if (verdict === "APPROVED") {
    return `Approved because there are 0 unresolved HIGH findings and ${medium_count} MEDIUM finding(s) — both within the thresholds required for full approval (max 2 MEDIUM, 0 HIGH).`;
  }
  if (verdict === "CONDITIONALLY APPROVED") {
    const mediumNote = medium_count > 2
      ? ` (and ${medium_count} MEDIUM findings, which alone would exceed the 2 allowed for full approval)`
      : "";
    return `Conditionally approved because ${high_count} HIGH finding(s) were raised${mediumNote} — this is within the maximum of 2 HIGH findings allowed for conditional approval, so deployment may proceed once they are resolved within the agreed timeframe.`;
  }
  return `Rejected because ${high_count} unresolved HIGH findings exceed the maximum of 2 allowed for conditional approval — full remediation and resubmission is required before this model can be reconsidered.`;
}

// Same Stage 5 metric/threshold table the backend evaluates (main.py, Stage
// 5 section of /validation/stage8/findings) — reproduced here because the
// API only returns FAILING metrics as findings, not the full pass/fail
// picture needed to show "why something passed" as well as "why it failed".
type MetricThresholdRow = { metric: string; value: number | null; threshold: number; op: ">=" | "<="; regulation: string; pass: boolean | null };

function metricThresholdRows(repMetrics: Record<string, any>): MetricThresholdRow[] {
  const rocAuc = typeof repMetrics.roc_auc === "number" ? repMetrics.roc_auc : null;
  const gini = rocAuc !== null ? Math.round((2 * rocAuc - 1) * 10000) / 10000 : null;
  const rows: Array<[string, number | null, number, ">=" | "<=", string]> = [
    ["ROC-AUC", rocAuc, 0.70, ">=", "SS1/23 P4.1"],
    ["Recall", typeof repMetrics.recall === "number" ? repMetrics.recall : null, 0.60, ">=", "SS1/23 P4.4"],
    ["Gini", gini, 0.40, ">=", "SS11/13 §10.3"],
    ["Brier Score", typeof repMetrics.brier_score === "number" ? repMetrics.brier_score : null, 0.25, "<=", "SS11/13 §10.5"],
  ];
  return rows.map(([metric, value, threshold, op, regulation]) => ({
    metric,
    value,
    threshold,
    op,
    regulation,
    pass: value === null ? null : op === ">=" ? value >= threshold : value <= threshold,
  }));
}

const STAGE_ORDER = ["Stage 1", "Stage 2", "Stage 3", "Stage 4", "Stage 5", "Stage 6"];

// Subtle numbered-section label — "01  Overall Verdict" — used as every major
// section's VCard title across this page, matching the report-like hierarchy
// requested for Stage 7 specifically (the other validation stages use plain
// titles; this is the one page meant to read as a final consolidated report).
function NumberedTitle({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-400">{n}</span>
      {children}
    </span>
  );
}

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
      <div className="mt-0.5 break-words text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function VerdictStat({ label, value, tone }: { label: string; value: number; tone: "rose" | "amber" | "slate" }) {
  const toneClasses: Record<string, string> = { rose: "text-rose-600", amber: "text-amber-600", slate: "text-slate-900" };
  return (
    <div className="text-center">
      <div className={`text-2xl font-extrabold tabular-nums ${toneClasses[tone]}`}>{value}</div>
      <div className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
    </div>
  );
}

function Findings() {
  const ds = useDataset();
  const {
    file,
    profile,
    validationIntakeData,
    validationMddText,
    validationProfile,
    validationStage5Result,
    validationStage7BiasResult,
    validationStage8Result,
    setValidationStage8Result,
  } = ds;

  const datasetName = profile?.dataset_name ?? file?.name ?? "the active validation dataset";
  const datasetReady = Boolean(file || profile?.csv_text || profile?.dataset_name);

  const [loading, setLoading] = React.useState(!validationStage8Result);
  const [error, setError] = React.useState<string | null>(null);
  // "network" = the request never reached the backend at all (connection
  // refused, CORS block, backend down/restarting) — the fetch() promise
  // rejects directly rather than resolving with a non-2xx status, so it
  // reads as a transient infrastructure issue rather than a broken page.
  // "server" = the backend responded but with an error (4xx/5xx/bad body).
  const [errorKind, setErrorKind] = React.useState<"network" | "server" | null>(null);
  const [data, setData] = React.useState<Stage8Response | null>((validationStage8Result as Stage8Response | null) ?? null);
  const skipInitialAutoRun = React.useRef(validationStage8Result !== null && validationStage8Result !== undefined);
  const [retryToken, setRetryToken] = React.useState(0);

  // Resume where the reviewer left off: pulls the last saved "findings"-stage
  // run from the backend's activity log. Only applied if nothing is already
  // loaded AND the saved payload actually looks like this page's own
  // Stage8Response shape (has a `findings` array) — otherwise left alone, so
  // a run saved under the same stage name by a different findings endpoint
  // never corrupts this page's state.
  const { data: resumedFindings } = useResumeState<Record<string, any>>("validation_pipeline_log.csv", "findings");
  React.useEffect(() => {
    if (!data && resumedFindings && Array.isArray((resumedFindings as any).findings)) {
      setData(resumedFindings as Stage8Response);
      setValidationStage8Result(resumedFindings);
      skipInitialAutoRun.current = true;
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumedFindings]);

  React.useEffect(() => {
    if (skipInitialAutoRun.current) {
      skipInitialAutoRun.current = false;
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);
    setErrorKind(null);

    const repMetrics = (validationStage5Result as any)?.report?.metrics ?? {};
    const benchmarkMetrics = (validationStage5Result as any)?.report?.benchmark?.metrics ?? {};
    const biasRows = ((validationStage7BiasResult as any)?.rows ?? []) as Array<{ AUC: number | null }>;
    const biasAucVals = biasRows.map((r) => r.AUC).filter((v): v is number => v !== null);
    const biasAucGap = biasAucVals.length >= 2 ? Math.max(...biasAucVals) - Math.min(...biasAucVals) : null;

    const form = new FormData();
    form.append("intake_json", JSON.stringify(validationIntakeData ?? {}));
    form.append("mdd_text", validationMddText ?? "");
    form.append(
      "validation_profile_json",
      JSON.stringify({
        missing_by_column: validationProfile?.missing_by_column ?? {},
        duplicate_rate: validationProfile?.duplicate_rate ?? 0,
      }),
    );
    form.append("rep_metrics_json", JSON.stringify(repMetrics));
    form.append("benchmark_metrics_json", JSON.stringify(benchmarkMetrics));
    if (biasAucGap !== null) form.append("bias_auc_gap", String(biasAucGap));

    void formUpload<Stage8Response>("/validation/stage8/findings", form)
      .then((resp) => {
        if (!active) return;
        setData(resp);
        setValidationStage8Result(resp as unknown as Record<string, any>);
      })
      .catch((err) => {
        console.error("Stage8 fetch error", err);
        if (!active) return;
        if (err instanceof ApiError) {
          setErrorKind("server");
          const detail =
            err.body && typeof err.body === "object" && "detail" in (err.body as any)
              ? String((err.body as any).detail)
              : err.message;
          setError(detail);
        } else {
          // Not an ApiError means fetch() itself rejected before getting a
          // response — a real network-level failure (backend unreachable,
          // CORS, DNS), not a request the server actually processed.
          setErrorKind("network");
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validationIntakeData, validationMddText, validationProfile, validationStage5Result, validationStage7BiasResult, retryToken]);

  const findings = data?.findings ?? [];

  const [remediation, setRemediation] = React.useState<RemediationRow[]>([]);
  React.useEffect(() => {
    setRemediation((prev) => {
      if (prev.length === findings.length) return prev;
      return findings.map((f) => ({
        finding: `${f.stage} — ${f.check}`,
        severity: f.severity,
        detail: f.finding,
        owner: "",
        targetDate: "",
        status: "Open",
      }));
    });
  }, [findings]);

  const updateRemediation = (idx: number, patch: Partial<RemediationRow>) => {
    setRemediation((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };

  // Grouped-by-stage, collapsed-by-default view of the findings tracker —
  // one row per finding (Stage / Finding / Severity / Status), full detail
  // only shown once a row is expanded. S.No numbers the flattened list so
  // it stays stable/unique across groups.
  const [expandedFindings, setExpandedFindings] = React.useState<Record<number, boolean>>({});
  const toggleFinding = (idx: number) => setExpandedFindings((prev) => ({ ...prev, [idx]: !prev[idx] }));

  const groupedFindings = React.useMemo(() => {
    const indexed = findings.map((f, i) => ({ ...f, _sno: i + 1 }));
    const byStage = new Map<string, typeof indexed>();
    for (const f of indexed) {
      if (!byStage.has(f.stage)) byStage.set(f.stage, []);
      byStage.get(f.stage)!.push(f);
    }
    const orderedStages = [
      ...STAGE_ORDER.filter((s) => byStage.has(s)),
      ...Array.from(byStage.keys()).filter((s) => !STAGE_ORDER.includes(s)),
    ];
    return orderedStages.map((stage) => ({ stage, items: byStage.get(stage)! }));
  }, [findings]);

  const repMetricsForReport = (validationStage5Result as any)?.report?.metrics ?? {};
  const metricRows = React.useMemo(() => metricThresholdRows(repMetricsForReport), [repMetricsForReport]);

  const executiveOverviewTiles = React.useMemo(() => {
    if (!data) return [] as Array<{ icon: typeof Gauge; label: string; value: React.ReactNode; sub?: string; tone?: "primary" | "amber" | "emerald" | "rose" | "violet" | "slate" }>;

    return [
      { icon: Gauge, label: "Verdict", value: data.verdict, sub: "Overall decision", tone: data.verdict === "APPROVED" ? "emerald" : data.verdict === "REJECTED" ? "rose" : "amber" },
      { icon: AlertTriangle, label: "High", value: data.high_count, sub: "Critical issues", tone: "rose" },
      { icon: ClipboardList, label: "Medium", value: data.medium_count, sub: "Follow-up items", tone: "amber" },
      { icon: CheckCircle2, label: "Total", value: data.total_count, sub: "Findings logged", tone: "slate" },
    ];
  }, [data]);

  const downloadFullReportPdf = () => window.print();

  const ij = validationIntakeData ?? {};

  const execSummaryDefault = React.useMemo(() => {
    if (!data) return "";
    const stated = data.stated_auc;
    const rep = data.replicated_auc;
    const gini = rep !== null && rep !== undefined ? (2 * rep - 1).toFixed(4) : "N/A";
    const bmMetrics = (validationStage5Result as any)?.report?.benchmark?.metrics ?? {};
    const benchmarkLine =
      Object.keys(bmMetrics).length && rep !== null && rep !== undefined
        ? rep >= (bmMetrics.roc_auc ?? 0) - 0.02
          ? "Champion outperforms baseline"
          : "Champion underperforms baseline — see findings"
        : "N/A";

    return `Model: ${ij.model_name ?? "N/A"} (${ij.model_type ?? "N/A"})
Validation Date: ${todayLabel()}
Risk Tier: ${data.model_tier ?? "N/A"}
Verdict: ${data.verdict}

Performance Summary:
- Replicated AUC: ${rep !== null && rep !== undefined ? rep.toFixed(4) : "N/A"} (Stated: ${stated !== null && stated !== undefined ? stated.toFixed(4) : "N/A"})
- Gini: ${gini} | Recall: ${(validationStage5Result as any)?.report?.metrics?.recall ?? "N/A"}
- Benchmark: ${benchmarkLine}

Key Findings: ${data.total_count} total (${data.high_count} HIGH, ${data.medium_count} MEDIUM)
${data.high_count === 0 ? "No HIGH findings raised." : `${data.high_count} HIGH finding(s) require remediation before deployment.`}

Recommended Actions:
${
  data.verdict === "APPROVED"
    ? "Model approved for deployment subject to ongoing monitoring."
    : data.verdict === "CONDITIONALLY APPROVED"
      ? `Complete remediation of ${data.high_count} HIGH finding(s) by agreed deadlines.`
      : "Model rejected. Full remediation and resubmission required."
}
Monitoring frequency: ${data.monitoring_frequency}
Revalidation trigger: ${data.revalidation_trigger}`.trim();
  }, [data, ij, validationStage5Result]);

  const [execSummary, setExecSummary] = React.useState("");
  React.useEffect(() => {
    if (execSummaryDefault) setExecSummary(execSummaryDefault);
  }, [execSummaryDefault]);

  const [signOff, setSignOff] = React.useState({ validator: "", modelOwner: "", committee: "" });

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <StageHero
        eyebrow="STAGE 7 · MODEL VALIDATION"
        title="Findings & Final Validation Report"
        description="SS1/23 P4.1/P5 · SS11/13 §13 — consolidated findings, verdict, and sign-off for the Model Risk Committee."
        chips={
          <>
            <HeroChip>Final verdict</HeroChip>
            <HeroChip tone={data ? (data.verdict === "APPROVED" ? "success" : data.verdict === "REJECTED" ? "warning" : "neutral") : "neutral"}>
              {data ? data.verdict : "Findings register"}
            </HeroChip>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm text-slate-600">
        <Database className="h-4 w-4 shrink-0 text-slate-400" />
        {datasetReady ? (
          <span>
            Using the shared dataset from Stage 1 / Stage 2: <span className="font-semibold text-slate-900">{datasetName}</span>
          </span>
        ) : (
          <span>No active dataset is available in shared state yet. Complete Stage 1 Intake and Stage 2 Data Validation first.</span>
        )}
      </div>

      {data && (
        <VCard icon={Gauge} title={<NumberedTitle n="00">Executive Overview</NumberedTitle>} sub="Validation outcome at a glance">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {executiveOverviewTiles.map((tile) => {
              const Icon = tile.icon;
              return (
                <div key={tile.label} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">{tile.label}</span>
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                      <Icon className="h-3.5 w-3.5" />
                    </span>
                  </div>
                  <div className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900">{tile.value}</div>
                  <div className="mt-1 text-[11px] text-slate-500">{tile.sub}</div>
                </div>
              );
            })}
          </div>
        </VCard>
      )}

      {loading ? (
        <VEmptyState icon={RefreshCw} title="Compiling Stage 7 findings…" description="Consolidating results from Stages 1–6 into the final validation report." />
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
            <div className="flex-1">
              <div className="text-sm font-semibold text-red-700">
                {errorKind === "network"
                  ? "Backend unreachable — this looks like a transient network issue"
                  : "Error loading Stage 7 findings"}
              </div>
              <p className="mt-1 text-sm text-red-700">
                {errorKind === "network"
                  ? "The findings request never reached the server (connection refused, CORS, or the backend is still starting up). It's likely temporary — try again in a moment."
                  : error}
              </p>
              {errorKind === "network" ? <p className="mt-1 text-xs text-red-600">{error}</p> : null}
              <button
                type="button"
                onClick={() => setRetryToken((t) => t + 1)}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Retry
              </button>
            </div>
          </div>
        </div>
      ) : data ? (
        <div id="full-report-content" className="space-y-6">
          {/* ── Overall verdict — the most important section after the hero,
              per the requested "final decision workspace" hierarchy. ────── */}
          <VCard
            icon={VERDICT_ICON[data.verdict] ?? AlertTriangle}
            title={<NumberedTitle n="01">Overall Verdict</NumberedTitle>}
            badge={{ text: data.verdict, tone: VERDICT_BADGE_TONE[data.verdict] ?? "slate" }}
          >
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Overall Validation Verdict</div>
                <div className={`mt-1 text-3xl font-extrabold tracking-tight ${VERDICT_TEXT_TONE[data.verdict] ?? "text-slate-900"}`}>
                  {data.verdict}
                </div>
              </div>
              <div className="flex shrink-0 items-start gap-6 rounded-xl border border-slate-100 bg-slate-50/60 px-5 py-3">
                <VerdictStat label="High" value={data.high_count} tone="rose" />
                <VerdictStat label="Medium" value={data.medium_count} tone="amber" />
                <VerdictStat label="Total" value={data.total_count} tone="slate" />
              </div>
            </div>

            <div className="mt-5 space-y-3 border-t border-slate-100 pt-4">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Decision Rationale</div>
                <p className="mt-1 text-sm text-slate-700">{data.verdict_desc}</p>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Key Evidence</div>
                <p className="mt-1 text-sm font-medium text-slate-900">{verdictReasoning(data)}</p>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Validation Context</div>
                <p className="mt-1 text-xs text-slate-500">
                  Model: {ij.model_name ?? "N/A"} · Type: {ij.model_type ?? "N/A"} · Tier: {data.model_tier} · Date: {todayLabel()}
                </p>
              </div>
            </div>
          </VCard>

          {/* ── Model identity — compact info grid instead of a tall card. ── */}
          <VCard icon={FileText} title={<NumberedTitle n="02">Model Identity</NumberedTitle>}>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <InfoField label="Model" value={ij.model_name ?? "N/A"} />
              <InfoField label="Type" value={ij.model_type ?? "N/A"} />
              <InfoField label="Risk Tier" value={data.model_tier} />
              <InfoField label="Validator" value={signOff.validator || "—"} />
              <InfoField label="Validation Date" value={todayLabel()} />
            </div>
          </VCard>

          {/* ── Findings tracker ─────────────────────────────────────────── */}
          <VCard
            icon={ClipboardList}
            title={<NumberedTitle n="03">Findings Summary</NumberedTitle>}
            sub="Auto-compiled from Stages 1–7. All HIGH findings must be resolved before model deployment."
          >
            {findings.length === 0 ? (
              <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                No findings raised across all validation stages — model is fully compliant.
              </div>
            ) : (
              <>
                <KpiStrip
                  tiles={[
                    { icon: ClipboardList, label: "Total Findings", value: data.total_count, tone: "slate" },
                    { icon: XCircle, label: "High", value: data.high_count, tone: "rose" },
                    { icon: AlertTriangle, label: "Medium", value: data.medium_count, tone: "amber" },
                    { icon: CheckCircle2, label: "Low", value: data.low_count, tone: "emerald" },
                  ]}
                />

                <div className="no-print mt-6 space-y-6">
                  {groupedFindings.map(({ stage, items }) => (
                    <div key={stage}>
                      <div className="mb-2 flex items-center gap-2">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">{stage}</h4>
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500">
                          {items.length} finding{items.length === 1 ? "" : "s"}
                        </span>
                      </div>
                      <div className="overflow-hidden rounded-xl border border-slate-200">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-y border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                              <th className="w-10 px-3 py-2 text-left">S.No</th>
                              <th className="px-3 py-2 text-left">Finding</th>
                              <th className="px-3 py-2 text-left">Severity</th>
                              <th className="px-3 py-2 text-left">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-50">
                            {items.map((f) => {
                              const s = severityStyle(f.severity);
                              const expanded = Boolean(expandedFindings[f._sno]);
                              return (
                                <React.Fragment key={f._sno}>
                                  <tr
                                    className="cursor-pointer hover:bg-slate-50/60"
                                    onClick={() => toggleFinding(f._sno)}
                                  >
                                    <td className="px-3 py-2 align-top text-slate-400">{f._sno}</td>
                                    <td className="px-3 py-2 align-top">
                                      <div className="flex items-center gap-1.5 font-medium text-slate-900">
                                        {expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-blue-600" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-blue-600" />}
                                        {f.check}
                                      </div>
                                    </td>
                                    <td className="px-3 py-2 align-top">
                                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${s.badge}`}>
                                        {f.severity}
                                      </span>
                                    </td>
                                    <td className="px-3 py-2 align-top">
                                      <StatusPill tone={statusTone(f.status)}>{f.status}</StatusPill>
                                    </td>
                                  </tr>
                                  {expanded && (
                                    <tr className={`${s.bg}`}>
                                      <td className="px-3 py-3" />
                                      <td colSpan={3} className="px-3 py-3">
                                        <div className="text-sm text-slate-800">{f.finding}</div>
                                        <div className="mt-2 text-sm text-slate-500">{f.recommendation}</div>
                                        <div className="mt-1 text-xs text-slate-500">{f.regulation}</div>
                                      </td>
                                    </tr>
                                  )}
                                </React.Fragment>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Print-only: full findings detail, always expanded, since a
                    static PDF has no click-to-expand affordance. */}
                <div className="print-only mt-6 space-y-6">
                  {groupedFindings.map(({ stage, items }) => (
                    <div key={`print-${stage}`}>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">{stage}</h4>
                      <div className="mt-2 space-y-2">
                        {items.map((f) => {
                          const s = severityStyle(f.severity);
                          return (
                            <div key={`print-${f._sno}`} className={`rounded-r-lg border-l-4 ${s.border} ${s.bg} p-3`}>
                              <div className="text-sm font-semibold text-slate-900">
                                {f._sno}. {f.check} — <span className="uppercase">{f.severity}</span> ({f.status})
                              </div>
                              <div className="mt-1 text-sm text-slate-800">{f.finding}</div>
                              <div className="mt-1 text-sm text-slate-500">{f.recommendation}</div>
                              <div className="mt-1 text-xs text-slate-500">{f.regulation}</div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </VCard>

          {/* ── Remediation action plan — its own section now (previously
              nested inside Findings Summary), scrollable so a long tracker
              never stretches the whole page. Internal working tool, not part
              of the formal PDF report (kept no-print, as before). ────────── */}
          <VCard
            icon={RefreshCw}
            title={<NumberedTitle n="04">Remediation Action Log</NumberedTitle>}
            sub="Add owners and deadlines for each finding before sign-off."
            className="no-print"
          >
            {remediation.length === 0 ? (
              <div className="text-sm text-slate-500">No findings to remediate.</div>
            ) : (
              <div className="max-h-[420px] overflow-y-auto overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 z-10">
                    <tr className="border-y border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Finding</th>
                      <th className="px-3 py-2 text-left">Severity</th>
                      <th className="px-3 py-2 text-left">Owner</th>
                      <th className="px-3 py-2 text-left">Target Date</th>
                      <th className="px-3 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {remediation.map((r, i) => (
                      <tr key={r.finding + i} className="hover:bg-slate-50/60">
                        <td className="px-3 py-2 align-top text-slate-400">{i + 1}</td>
                        <td className="px-3 py-2 align-top">
                          <div className="font-medium text-slate-900">{r.finding}</div>
                          <div className="text-xs text-slate-500">{r.detail}</div>
                        </td>
                        <td className="px-3 py-2 align-top">
                          <select
                            value={r.severity}
                            onChange={(e) => updateRemediation(i, { severity: e.target.value })}
                            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                          >
                            <option>HIGH</option>
                            <option>MEDIUM</option>
                            <option>LOW</option>
                          </select>
                        </td>
                        <td className="px-3 py-2 align-top">
                          <input
                            value={r.owner}
                            onChange={(e) => updateRemediation(i, { owner: e.target.value })}
                            placeholder="Owner"
                            className="w-32 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                          />
                        </td>
                        <td className="px-3 py-2 align-top">
                          <input
                            value={r.targetDate}
                            onChange={(e) => updateRemediation(i, { targetDate: e.target.value })}
                            placeholder="e.g. 31 Aug 2026"
                            className="w-32 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                          />
                        </td>
                        <td className="px-3 py-2 align-top">
                          <select
                            value={r.status}
                            onChange={(e) => updateRemediation(i, { status: e.target.value })}
                            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                          >
                            <option>Open</option>
                            <option>In Progress</option>
                            <option>Resolved</option>
                            <option>Risk Accepted</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </VCard>

          {/* ── Performance metrics vs regulatory thresholds ────────────── */}
          <VCard
            icon={Gauge}
            title={<NumberedTitle n="05">Performance Metrics vs Regulatory Thresholds</NumberedTitle>}
            sub="Replicated (Stage 3/4) metrics evaluated against the minimum required by regulation."
          >
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-y border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                    <th className="px-3 py-2 text-left">Metric</th>
                    <th className="px-3 py-2 text-left">Value</th>
                    <th className="px-3 py-2 text-left">Threshold</th>
                    <th className="px-3 py-2 text-left">Regulation</th>
                    <th className="px-3 py-2 text-left">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {metricRows.map((row) => (
                    <tr key={row.metric} className="hover:bg-slate-50/60">
                      <td className="px-3 py-2 align-top font-medium text-slate-900">{row.metric}</td>
                      <td className="px-3 py-2 align-top text-slate-700">{row.value !== null ? row.value.toFixed(4) : "N/A"}</td>
                      <td className="px-3 py-2 align-top text-slate-500">{row.op} {row.threshold}</td>
                      <td className="px-3 py-2 align-top text-slate-500">{row.regulation}</td>
                      <td className="px-3 py-2 align-top">
                        {row.pass === null ? (
                          <span className="text-slate-400">N/A</span>
                        ) : (
                          <StatusPill tone={row.pass ? "pass" : "fail"}>{row.pass ? "Pass" : "Fail"}</StatusPill>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </VCard>

          {/* ── Monitoring & revalidation — lightweight, two compact cards. ── */}
          <VCard icon={RefreshCw} title={<NumberedTitle n="06">Monitoring &amp; Revalidation Recommendations</NumberedTitle>}>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4">
                <div className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Monitoring Frequency</div>
                <div className="mt-1 text-xl font-bold text-slate-900">{data.monitoring_frequency}</div>
                <div className="mt-1 text-xs text-slate-500">Based on {data.model_tier}</div>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4">
                <div className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Revalidation Trigger</div>
                <div className="mt-1 text-base font-bold text-slate-900">{data.revalidation_trigger}</div>
                <div className="mt-1 text-xs text-slate-500">SS1/23 P4.4</div>
              </div>
            </div>
          </VCard>

          {/* ── Executive summary — document-styled, still fully editable. ── */}
          <VCard icon={FileText} title={<NumberedTitle n="07">Executive Summary</NumberedTitle>} sub="Auto-generated from validation findings. Edit before final sign-off.">
            <div className="no-print rounded-xl border border-slate-200 bg-slate-50/40 p-1">
              <textarea
                value={execSummary}
                onChange={(e) => setExecSummary(e.target.value)}
                rows={14}
                className="w-full rounded-lg border border-transparent bg-white px-3 py-2.5 font-mono text-xs leading-relaxed text-slate-800 focus:border-slate-200"
              />
            </div>
            <pre className="print-only whitespace-pre-wrap font-mono text-xs leading-relaxed">{execSummary}</pre>
          </VCard>

          {/* ── Evidence pack — CSV + PDF downloads together, horizontal. ── */}
          <VCard icon={Download} title="Evidence Pack" className="no-print">
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={findings.length === 0}
                onClick={() =>
                  downloadCsv(
                    `validation_findings_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}.csv`,
                    findings,
                  )
                }
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                Download Findings Report (CSV)
              </button>
              <button
                type="button"
                onClick={() =>
                  downloadCsv(`validation_report_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}.csv`, [
                    { Section: "Verdict", Value: data.verdict },
                    { Section: "Model Name", Value: ij.model_name ?? "N/A" },
                    { Section: "Model Type", Value: ij.model_type ?? "N/A" },
                    { Section: "Risk Tier", Value: data.model_tier },
                    { Section: "Validation Date", Value: todayLabel() },
                    { Section: "Replicated AUC", Value: data.replicated_auc ?? "N/A" },
                    { Section: "Stated AUC", Value: data.stated_auc ?? "N/A" },
                    {
                      Section: "AUC Gap",
                      Value:
                        data.replicated_auc !== null && data.stated_auc !== null
                          ? Math.abs((data.replicated_auc ?? 0) - (data.stated_auc ?? 0)).toFixed(4)
                          : "N/A",
                    },
                    { Section: "Total Findings", Value: data.total_count },
                    { Section: "HIGH Findings", Value: data.high_count },
                    { Section: "MEDIUM Findings", Value: data.medium_count },
                    { Section: "Monitoring Frequency", Value: data.monitoring_frequency },
                    { Section: "Revalidation Trigger", Value: data.revalidation_trigger },
                    { Section: "Executive Summary", Value: execSummary },
                  ])
                }
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <Download className="h-4 w-4" />
                Download Full Validation Report (CSV)
              </button>
              <button
                type="button"
                onClick={downloadFullReportPdf}
                className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
              >
                <Printer className="h-4 w-4" />
                Download Full Report (PDF)
              </button>
            </div>
          </VCard>

          {/* ── Sign-off ─────────────────────────────────────────────────── */}
          <VCard icon={Users} title={<NumberedTitle n="08">Sign-off</NumberedTitle>}>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {(
                [
                  ["Validator", "validator", "Risk Validation"],
                  ["Model Owner", "modelOwner", "Credit Risk Modelling"],
                  ["Committee", "committee", "Model Risk Committee"],
                ] as const
              ).map(([role, key, sub]) => (
                <div key={role} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{role}</div>
                  <input
                    value={signOff[key]}
                    onChange={(e) => setSignOff((prev) => ({ ...prev, [key]: e.target.value }))}
                    placeholder="Name / status"
                    className="no-print mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-sm font-semibold text-slate-900"
                  />
                  <div className="print-only mt-1 border-b border-slate-400 pb-1 text-sm font-semibold">
                    {signOff[key] || " "}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{sub}</div>
                </div>
              ))}
            </div>
          </VCard>
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <Link
          to="/validation/regulatory"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          ← Back to Stage 6: Explainability and Fairness
        </Link>
        <Link
          to="/validation"
          className="inline-flex items-center gap-2 rounded-lg bg-[#2f67ff] px-4 py-2 text-sm font-semibold text-white shadow-[0_4px_10px_rgba(47,103,255,0.18)] hover:bg-[#285ee6]"
        >
          Finish
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
