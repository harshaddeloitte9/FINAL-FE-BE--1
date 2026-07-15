import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight } from "lucide-react";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";

export const Route = createFileRoute("/validation/conceptual")({
  head: () => ({ meta: [{ title: "Stage 3 — Conceptual Soundness — Aegis Credit" }] }),
  component: Conceptual,
});

type Status = "PASS" | "WARN" | "FAIL" | string;

type ThresholdCheck = {
  check_id: string;
  title: string;
  severity: string;
  status: Status;
  source: string;
  principle: string;
  observed: string;
  threshold: string;
  detail: string;
};

type RagRule = {
  rule_id: string;
  flag: string;
  suggestion: string;
  severity: string;
  status: Status;
  source: string;
  principle: string;
  observed_value?: string | string[] | null;
  not_verifiable?: boolean;
  check_source?: "llm" | "llm_error" | "quantitative" | "keyword_search" | "" | string;
  reasoning?: string;
};

type Stage3Response = {
  thresholdChecks: ThresholdCheck[];
  ragRules: RagRule[];
  summary: { total: number; pass: number; warn: number; fail: number };
  regulatoryAlignment: {
    verdict: "PASS" | "CONDITIONAL" | "FAIL" | string;
    counts: { pass: number; warn: number; fail: number; pending: number };
    remediation_summary: string;
    regulatory_references: string[];
    high_severity_fails: unknown[];
  };
  featureRelevance?: { importance_df?: unknown[]; top_drivers?: unknown[] };
};

// Component renders entirely from backend response; no local mock data kept.

function Conceptual() {
  const {
    file,
    profile,
    trainingResult,
    validationIntakeData,
    validationMddText,
    validationStage3Result,
    setValidationStage3Result,
  } = useDataset();

  // Seed from shared context so returning to this page (e.g. via Back from
  // Stage 4) shows the already-computed result instead of forcing a re-run.
  const [loading, setLoading] = useState(!validationStage3Result);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<Stage3Response | null>((validationStage3Result as Stage3Response | null) ?? null);

  const datasetLoaded = Boolean(file || profile?.csv_text || profile?.dataset_name);
  const skipInitialAutoRun = useRef(validationStage3Result !== null && validationStage3Result !== undefined);

  useEffect(() => {
    if (!datasetLoaded) {
      setLoading(false);
      return;
    }
    if (skipInitialAutoRun.current) {
      skipInitialAutoRun.current = false;
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    const form = new FormData();
    // Mirrors Stage 2 (validation.data-quality.tsx): use the real working
    // dataset from context rather than posting an empty intake, which is why
    // the RAG Agent Rules column previously came back empty — check_for_validation
    // needs dataset metrics and check_mdd_keywords needs the MDD text to match
    // against, neither of which were ever being sent.
    if (file) {
      form.append("file", file);
    } else if (profile?.csv_text) {
      form.append("csv_text", profile.csv_text);
    }
    // check_conceptual_soundness() reads intake_json.methodology (check 3.1),
    // but the Intake form has no dedicated methodology field — the actual
    // algorithm choice lives on Training's trainingResult. Fill it in here
    // when the Intake form didn't already provide one.
    const intakePayload: Record<string, any> = { ...(validationIntakeData ?? {}) };
    if (!intakePayload.methodology && trainingResult?.model_name) {
      intakePayload.methodology = trainingResult.model_name;
    }
    form.append("intake_json", JSON.stringify(intakePayload));
    if (validationMddText) {
      const mddBlob = new Blob([validationMddText], { type: "text/plain" });
      form.append("mdd_file", new File([mddBlob], "mdd.txt", { type: "text/plain" }));
    }

    void formUpload<Stage3Response>("/validation/stage3/run", form)
      .then((resp) => {
        if (!active) return;
        setData(resp);
        setValidationStage3Result(resp as unknown as Record<string, any>);
      })
      .catch((err) => {
        console.error("Stage3 fetch error", err);
        if (!active) return;
        setError(err?.message ?? String(err));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetLoaded, file, profile?.csv_text]);

  const summary = data?.summary ?? { total: 0, pass: 0, warn: 0, fail: 0 };
  const progress = summary.total > 0 ? Math.round((summary.pass / summary.total) * 100) : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Conceptual Soundness Review"
        description="Are the chosen features, methodology, and assumptions appropriate for the stated business objective and regulatory context?"
      />

      {!datasetLoaded ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No dataset available</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Upload a dataset and complete Intake before conceptual soundness checks can run.
          </p>
        </div>
      ) : loading ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">Loading Conceptual Soundness...</div>
      ) : error ? (
        <div className="rounded-xl border border-border bg-card p-6 text-destructive">Error loading Stage 3: {error}</div>
      ) : (
        <>
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h3 className="text-sm font-semibold">Conceptual Soundness Results</h3>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryTile label="Total Checks" value={summary.total} tone="neutral" />
              <SummaryTile label="PASS" value={summary.pass} tone="pass" />
              <SummaryTile label="WARN" value={summary.warn} tone="warn" />
              <SummaryTile label="FAIL" value={summary.fail} tone="fail" />
            </div>
            <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </section>

          <section className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="min-w-0">
              <div className="mb-3 rounded-lg border border-border bg-muted/40 px-4 py-3">
                <div className="text-sm font-bold text-primary">📐 Recommended Threshold Checks</div>
                <div className="text-xs text-muted-foreground">Quantitative checks against regulatory thresholds</div>
              </div>
              <div className="space-y-3">
                {data?.thresholdChecks && data.thresholdChecks.length > 0 ? (
                  data.thresholdChecks.map((c) => <ThresholdCheckCard key={c.check_id} check={c} />)
                ) : (
                  <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                    No threshold checks generated for this stage.
                  </div>
                )}
              </div>
            </div>

            <div className="min-w-0">
              <div className="mb-3 rounded-lg border border-border bg-muted/40 px-4 py-3">
                <div className="text-sm font-bold text-violet-500">🤖 RAG Agent Rules</div>
                <div className="text-xs text-muted-foreground">
                  Regulatory rules fetched from knowledge store (SS1/23, SS11/13, IFRS 9)
                </div>
              </div>
              <div className="space-y-3">
                {data?.ragRules && data.ragRules.length > 0 ? (
                  data.ragRules.map((r) => <RagRuleCard key={r.rule_id} rule={r} />)
                ) : (
                  <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                    No RAG agent flags generated for this stage.
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-primary/30 bg-primary-soft p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-foreground/70">Regulatory alignment</div>
            <p className="mt-2 text-sm">
              Verdict: <VerdictBadge verdict={data?.regulatoryAlignment?.verdict} />
            </p>
            <p className="mt-2 text-sm">
              Pass/Warn/Fail: {data?.regulatoryAlignment?.counts?.pass ?? 0}/{data?.regulatoryAlignment?.counts?.warn ?? 0}/
              {data?.regulatoryAlignment?.counts?.fail ?? 0}
            </p>
            {data?.regulatoryAlignment?.remediation_summary && (
              <p className="mt-3 text-sm text-muted-foreground">{data.regulatoryAlignment.remediation_summary}</p>
            )}
            {data?.regulatoryAlignment?.regulatory_references?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {data.regulatoryAlignment.regulatory_references.map((ref: string) => (
                  <span
                    key={ref}
                    className="rounded-full border border-primary/20 bg-background px-3 py-1 text-xs font-medium text-foreground/80"
                  >
                    {ref}
                  </span>
                ))}
              </div>
            ) : null}
            {data?.regulatoryAlignment?.high_severity_fails?.length ? (
              <div className="mt-3 text-sm text-destructive">
                High severity fails: {data.regulatoryAlignment.high_severity_fails.length}
              </div>
            ) : null}
          </section>
        </>
      )}

      <div className="text-right">
        <Link
          to="/validation/challenger"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 4
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

const STATUS_STYLES: Record<string, { border: string; bg: string; badge: string; icon: string }> = {
  PASS: { border: "border-emerald-500/40", bg: "bg-emerald-500/10", badge: "bg-emerald-500 text-emerald-950", icon: "✅" },
  WARN: { border: "border-amber-500/40", bg: "bg-amber-500/10", badge: "bg-amber-500 text-amber-950", icon: "🟡" },
  FAIL: { border: "border-red-500/40", bg: "bg-red-500/10", badge: "bg-red-500 text-red-950", icon: "🔴" },
};

const SEVERITY_STYLES: Record<string, string> = {
  HIGH: "bg-red-500 text-red-950",
  MEDIUM: "bg-amber-500 text-amber-950",
  LOW: "bg-emerald-500 text-emerald-950",
};

const CHECK_SOURCE_LABELS: Record<string, { label: string; classes: string }> = {
  llm: { label: "🤖 LLM", classes: "bg-violet-500 text-violet-950" },
  llm_error: { label: "⚠️ LLM (call failed)", classes: "bg-amber-500 text-amber-950" },
  quantitative: { label: "📐 Rule-based", classes: "bg-sky-500 text-sky-950" },
  keyword_search: { label: "🔤 Keyword search", classes: "bg-slate-400 text-slate-950" },
};

function statusStyle(status: string | undefined) {
  return STATUS_STYLES[status ?? ""] ?? { border: "border-border", bg: "bg-card", badge: "bg-muted text-foreground", icon: "⚪" };
}

function SummaryTile({ label, value, tone }: { label: string; value: number; tone: "neutral" | "pass" | "warn" | "fail" }) {
  const classes =
    tone === "pass"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
      : tone === "warn"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-300"
      : tone === "fail"
      ? "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-300"
      : "border-border bg-background text-foreground";

  return (
    <div className={`rounded-xl border p-4 ${classes}`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict?: string }) {
  const classes =
    verdict === "PASS"
      ? "bg-emerald-500 text-emerald-950"
      : verdict === "CONDITIONAL"
      ? "bg-amber-500 text-amber-950"
      : verdict === "FAIL"
      ? "bg-red-500 text-red-950"
      : "bg-muted text-foreground";
  return (
    <span className={`ml-1 rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide ${classes}`}>
      {verdict ?? "—"}
    </span>
  );
}

function ThresholdCheckCard({ check }: { check: ThresholdCheck }) {
  const s = statusStyle(check.status);
  const sevClasses = SEVERITY_STYLES[check.severity?.toUpperCase()] ?? "bg-muted text-foreground";
  return (
    <div className={`min-w-0 rounded-r-lg border-l-4 ${s.border} ${s.bg} p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 break-words text-sm font-semibold text-foreground">
          {s.icon} <span className="text-muted-foreground">[{check.check_id}]</span> {check.title}{" "}
          <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${sevClasses}`}>
            {check.severity}
          </span>
        </div>
        <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold ${s.badge}`}>{check.status}</span>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        📋 {check.source} — {check.principle}
      </div>
      <div className="mt-2 text-sm text-foreground">
        📊 Observed: <code className="text-foreground/90">{check.observed}</code>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">📐 Threshold: {check.threshold}</div>
      <div className="mt-2 text-sm text-muted-foreground">💡 {check.detail}</div>
    </div>
  );
}

function RagRuleCard({ rule }: { rule: RagRule }) {
  const s = statusStyle(rule.status);
  const sevClasses = SEVERITY_STYLES[rule.severity?.toUpperCase()] ?? "bg-muted text-foreground";
  const csrc = CHECK_SOURCE_LABELS[rule.check_source ?? ""];
  const observed = Array.isArray(rule.observed_value) ? rule.observed_value.join(", ") : rule.observed_value;

  return (
    <div className={`min-w-0 rounded-r-lg border-l-4 ${s.border} ${s.bg} p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 break-words text-sm font-semibold text-foreground">
          {s.icon} <span className="text-muted-foreground">[{rule.rule_id}]</span> {rule.flag}
          {rule.not_verifiable ? (
            <span className="ml-1 text-xs italic text-muted-foreground"> · not verifiable with current data</span>
          ) : null}
          {csrc ? (
            <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${csrc.classes}`}>{csrc.label}</span>
          ) : null}
          <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${sevClasses}`}>
            {rule.severity}
          </span>
        </div>
        <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold ${s.badge}`}>{rule.status}</span>
      </div>
      {observed != null && observed !== "" ? (
        <div className="mt-2 text-sm text-foreground">
          📊 Observed: <code className="text-foreground/90">{observed}</code>
        </div>
      ) : null}
      {rule.reasoning ? (
        <div className="mt-2 text-xs italic text-violet-600 dark:text-violet-300">🧠 {rule.reasoning}</div>
      ) : null}
      <div className="mt-2 text-sm text-muted-foreground">💡 {rule.suggestion}</div>
      <div className="mt-1 text-xs text-muted-foreground">
        📋 {rule.source} — {rule.principle}
      </div>
    </div>
  );
}
