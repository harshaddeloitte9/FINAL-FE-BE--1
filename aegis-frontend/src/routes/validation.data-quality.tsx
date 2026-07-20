import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { ArrowRight, AlertTriangle, AlertCircle, Clock, Check } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export const Route = createFileRoute("/validation/data-quality")({
  head: () => ({ meta: [{ title: "Data Validation — Aegis Credit" }] }),
  component: DataQuality,
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

type Stage2Response = {
  thresholdChecks: ThresholdCheck[];
  ragRules: RagRule[];
  summary: { total: number; pass: number; warn: number; fail: number; pending?: number; na?: number };
  regulatoryAlignment: {
    verdict: "PASS" | "CONDITIONAL" | "FAIL" | string;
    counts: { pass: number; warn: number; fail: number; pending: number };
    remediation_summary: string;
    regulatory_references: string[];
    high_severity_fails: unknown[];
  };
};

function buildValidationCsv(thresholdChecks: ThresholdCheck[], ragRules: RagRule[]) {
  const header = ["Check ID", "Title", "Source", "Principle", "Severity", "Status", "Observed", "Threshold/Suggestion"];
  const escape = (value: string | number | null | undefined) => {
    const text = value == null ? "" : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };
  const lines = [header.map(escape).join(",")];
  for (const c of thresholdChecks) {
    lines.push([c.check_id, c.title, c.source, c.principle, c.severity, c.status, c.observed, c.threshold].map(escape).join(","));
  }
  for (const r of ragRules) {
    const observed = Array.isArray(r.observed_value) ? r.observed_value.join(", ") : r.observed_value ?? "";
    lines.push([r.rule_id, r.flag, r.source, r.principle, r.severity, r.status, observed, r.suggestion].map(escape).join(","));
  }
  return lines.join("\n");
}

function DataQuality() {
  const {
    file,
    profile,
    validationIntakeData,
    validationMddText,
    validationMddMetrics,
    validationProfile: sharedValidationProfile,
    validationResults: sharedValidationResults,
    setValidationProfile,
    setValidationResults,
  } = useDataset();

  const datasetLoaded = Boolean(file || profile?.csv_text || profile?.dataset_name);

  // ── Profile (charts: missing values, distribution, leakage) — unrelated to
  // the RAG check pipeline, kept as its own call against /data/profile. ──
  const [validationProfile, setValidationProfileState] = useState<any | null>(sharedValidationProfile ?? null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const runDataProfile = async () => {
    if (!datasetLoaded) return;
    setRunError(null);
    setIsRunning(true);
    try {
      const form = new FormData();
      if (file) {
        form.append("file", file);
      } else if (profile?.csv_text) {
        form.append("csv_text", profile.csv_text);
      } else {
        throw new Error("No dataset available to validate.");
      }

      const result = await formUpload("/data/profile", form);
      const nextProfile = result as any;
      setValidationProfileState(nextProfile);
      setValidationProfile(nextProfile);
      setValidationResults({
        profile: nextProfile,
        intake: validationIntakeData ?? null,
        mddText: validationMddText ?? null,
        mddMetrics: validationMddMetrics ?? null,
      });
    } catch (error: any) {
      setRunError(error?.message ?? "Failed to profile the dataset.");
    } finally {
      setIsRunning(false);
    }
  };

  useEffect(() => {
    if (!datasetLoaded || validationProfile || isRunning) return;
    void runDataProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetLoaded, validationProfile, isRunning, file, profile?.csv_text, profile?.dataset_name]);

  useEffect(() => {
    if (sharedValidationProfile && !validationProfile) {
      setValidationProfileState(sharedValidationProfile);
    }
  }, [sharedValidationProfile, validationProfile]);

  // ── RAG threshold checks + rules — real backend pipeline, same pattern as
  // Stage 3 Conceptual Soundness (/validation/stage3/run). ──
  const [checksLoading, setChecksLoading] = useState(true);
  const [checksError, setChecksError] = useState<string | null>(null);
  const [data, setData] = useState<Stage2Response | null>(null);

  useEffect(() => {
    if (!datasetLoaded) {
      setChecksLoading(false);
      return;
    }

    let active = true;
    setChecksLoading(true);
    setChecksError(null);

    const form = new FormData();
    if (file) {
      form.append("file", file);
    } else if (profile?.csv_text) {
      form.append("csv_text", profile.csv_text);
    }
    form.append("intake_json", JSON.stringify(validationIntakeData ?? {}));
    if (validationMddText) {
      const mddBlob = new Blob([validationMddText], { type: "text/plain" });
      form.append("mdd_file", new File([mddBlob], "mdd.txt", { type: "text/plain" }));
    }

    void formUpload<Stage2Response>("/validation/stage2/run", form)
      .then((resp) => {
        if (!active) return;
        setData(resp);
      })
      .catch((err) => {
        console.error("Stage2 fetch error", err);
        if (!active) return;
        setChecksError(err?.message ?? String(err));
      })
      .finally(() => {
        if (!active) return;
        setChecksLoading(false);
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetLoaded, file, profile?.csv_text]);

  const summary = data?.summary ?? { total: 0, pass: 0, warn: 0, fail: 0 };

  const validationCsv = useMemo(() => buildValidationCsv(data?.thresholdChecks ?? [], data?.ragRules ?? []), [data]);
  const downloadValidationReport = () => {
    const blob = new Blob([validationCsv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "data_validation_report.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 2 — Data Validation"
        description="Is the dataset complete, representative, and free of quality issues that would undermine model development?"
      />

      {!datasetLoaded ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No dataset available</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Upload a dataset and complete Intake before data validation checks can run.
          </p>
        </div>
      ) : checksLoading ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">Loading Data Validation...</div>
      ) : checksError ? (
        <div className="rounded-xl border border-border bg-card p-6 text-destructive">Error loading Stage 2: {checksError}</div>
      ) : (
        <>
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Data Validation Results</h3>
              <button
                type="button"
                onClick={downloadValidationReport}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted"
              >
                Download CSV
              </button>
            </div>
            <ComplianceSummaryRow summary={summary} />
          </section>

          <section className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="min-w-0">
              <div className="mb-3 rounded-lg border border-border bg-muted/40 px-4 py-3">
                <div className="text-sm font-bold text-primary">📐 Threshold checks</div>
                <div className="text-xs text-muted-foreground">Quantitative checks against regulatory thresholds</div>
              </div>
              {data?.thresholdChecks && data.thresholdChecks.length > 0 ? (
                <ThresholdPanel checks={data.thresholdChecks} profileSource={validationProfile ?? profile} />
              ) : (
                <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                  No threshold checks were returned for this stage.
                </div>
              )}
            </div>

            <div className="min-w-0">
              <div className="mb-3 rounded-lg border border-border bg-muted/40 px-4 py-3">
                <div className="text-sm font-bold text-violet-500">🤖 RAG agent rules</div>
                <div className="text-xs text-muted-foreground">
                  Regulatory rules fetched from knowledge store (IFRS 9, SS11/13, SS1/23)
                </div>
              </div>
              {data?.ragRules && data.ragRules.length > 0 ? (
                <RagRulesPanel rules={data.ragRules} />
              ) : (
                <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
                  No RAG agent flags generated for this stage.
                </div>
              )}
            </div>
          </section>

          <section className={`rounded-xl border p-6 ${regulatoryVerdictStyle(data?.regulatoryAlignment?.verdict).border} ${regulatoryVerdictStyle(data?.regulatoryAlignment?.verdict).bg}`}>
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-foreground/70">Regulatory alignment</div>
              <span className={`text-xs font-bold uppercase tracking-wide ${regulatoryVerdictStyle(data?.regulatoryAlignment?.verdict).text}`}>
                {regulatoryVerdictStyle(data?.regulatoryAlignment?.verdict).icon} {data?.regulatoryAlignment?.verdict ?? "—"}
              </span>
            </div>
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

          {runError ? (
            <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">{runError}</div>
          ) : null}

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h3 className="text-sm font-semibold">Data leakage detection</h3>
            <p className="mt-2 text-sm text-foreground/80">
              {validationProfile?.leakage_risk_cols && validationProfile.leakage_risk_cols.length > 0
                ? `Potential leakage detected: ${validationProfile.leakage_risk_cols.join(", ")}`
                : "No potential target leakage detected in the current dataset."}
            </p>
          </div>
        </>
      )}

      <div className="text-right">
        <Link
          to="/validation/conceptual"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 3
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
  PENDING: { border: "border-slate-400/40", bg: "bg-slate-400/10", badge: "bg-slate-400 text-slate-950", icon: "⏱️" },
};

// Mirrors Stage 8's VERDICT_STYLES convention — the regulatory alignment
// card should reflect the actual verdict, not always render as a green
// "all good" card regardless of whether it's PASS/CONDITIONAL/FAIL.
const REGULATORY_VERDICT_STYLES: Record<string, { border: string; bg: string; text: string; icon: string }> = {
  PASS: { border: "border-emerald-500/40", bg: "bg-emerald-500/10", text: "text-emerald-700 dark:text-emerald-300", icon: "✅" },
  CONDITIONAL: { border: "border-amber-500/40", bg: "bg-amber-500/10", text: "text-amber-700 dark:text-amber-300", icon: "⚠️" },
  FAIL: { border: "border-red-500/40", bg: "bg-red-500/10", text: "text-red-700 dark:text-red-300", icon: "❌" },
};

function regulatoryVerdictStyle(verdict: string | undefined) {
  return REGULATORY_VERDICT_STYLES[verdict ?? ""] ?? { border: "border-border", bg: "bg-card", text: "text-foreground", icon: "⚪" };
}

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

function statusIcon(status: string | undefined, className = "h-4 w-4") {
  switch (status) {
    case "FAIL":
      return <AlertTriangle className={`${className} text-red-600 dark:text-red-400`} />;
    case "WARN":
      return <AlertCircle className={`${className} text-amber-600 dark:text-amber-400`} />;
    case "PENDING":
      return <Clock className={`${className} text-slate-500 dark:text-slate-400`} />;
    default:
      return <Check className={`${className} text-emerald-600 dark:text-emerald-400`} />;
  }
}

// ── Checks-passed donut + pass/warn/fail count cards ─────────────────────

function ComplianceDonut({ pass, warn, fail, size = 88 }: { pass: number; warn: number; fail: number; size?: number }) {
  const total = pass + warn + fail;
  const failPct = total > 0 ? (fail / total) * 100 : 0;
  const warnPct = total > 0 ? (warn / total) * 100 : 0;
  const score = total > 0 ? Math.round((pass / total) * 100) : 0;
  const gradient =
    total > 0
      ? `conic-gradient(#dc2626 0% ${failPct}%, #d97706 ${failPct}% ${failPct + warnPct}%, #16a34a ${failPct + warnPct}% 100%)`
      : "#e5e7eb";

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <div className="h-full w-full rounded-full" style={{ background: gradient }} />
      <div
        className="absolute flex items-center justify-center rounded-full bg-card"
        style={{ inset: Math.round(size * 0.16) }}
      >
        <span className="text-lg font-bold text-foreground">{score}%</span>
      </div>
    </div>
  );
}

function CountCard({ label, value, tone }: { label: string; value: number; tone: "pass" | "warn" | "fail" | "na" }) {
  const color =
    tone === "pass"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "warn"
      ? "text-amber-600 dark:text-amber-400"
      : tone === "na"
      ? "text-indigo-600 dark:text-indigo-400"
      : "text-red-600 dark:text-red-400";
  const title = tone === "pass" ? "Pass" : tone === "warn" ? "Warn" : tone === "na" ? "N/A" : "Fail";
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className={`mt-1 text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function ComplianceSummaryRow({
  summary,
}: {
  summary: { total: number; pass: number; warn: number; fail: number; pending?: number; na?: number };
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <div className="flex items-center gap-4 rounded-xl border border-border bg-background p-4">
        <ComplianceDonut pass={summary.pass} warn={summary.warn} fail={summary.fail} />
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">Checks passed</div>
          <div className="text-base font-bold leading-tight text-foreground">
            {summary.pass}/{summary.total} passed
          </div>
        </div>
      </div>
      <CountCard label="Pass" value={summary.pass} tone="pass" />
      <CountCard label="Warn" value={summary.warn} tone="warn" />
      <CountCard label="Fail" value={summary.fail} tone="fail" />
      <CountCard label="N/A" value={summary.na ?? 0} tone="na" />
    </div>
  );
}

// ── Dataset insight (e.g. missing values by column) shown inside a threshold
// check's detail panel when the check text suggests it's relevant. Purely
// additive UI — falls back to nothing if the profile doesn't have usable
// fields, so it never breaks rendering of the underlying backend data. ──

function extractMissingness(profileSource: any): { column: string; pct: number }[] | null {
  if (!profileSource || typeof profileSource !== "object") return null;

  const mapCandidates = [
    profileSource.missing_by_column,
    profileSource.missing_pct_by_column,
    profileSource.column_missing_pct,
    profileSource.missingness,
    profileSource.null_pct_by_column,
  ];
  for (const candidate of mapCandidates) {
    if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
      const entries = Object.entries(candidate)
        .map(([column, raw]) => {
          const num = Number(raw);
          if (Number.isNaN(num)) return null;
          return { column, pct: num <= 1 ? num * 100 : num };
        })
        .filter((e): e is { column: string; pct: number } => e !== null);
      if (entries.length) return entries.sort((a, b) => b.pct - a.pct);
    }
  }

  const arrayCandidates = [
    profileSource.columns,
    profileSource.column_stats,
    profileSource.column_summary,
    profileSource.column_profiles,
  ];
  for (const arr of arrayCandidates) {
    if (Array.isArray(arr) && arr.length) {
      const entries = arr
        .map((c: any) => {
          const column = c?.name ?? c?.column ?? c?.column_name;
          const raw = c?.missing_pct ?? c?.missing_percentage ?? c?.null_pct ?? c?.pct_missing ?? c?.missing_rate;
          if (column == null || raw == null) return null;
          const num = Number(raw);
          if (Number.isNaN(num)) return null;
          return { column: String(column), pct: num <= 1 ? num * 100 : num };
        })
        .filter((e: any): e is { column: string; pct: number } => e !== null);
      if (entries.length) return entries.sort((a, b) => b.pct - a.pct);
    }
  }

  return null;
}

function MissingnessChart({ rows }: { rows: { column: string; pct: number }[] }) {
  const top = rows.filter((r) => r.pct > 0).slice(0, 8);
  if (!top.length) return null;
  const max = Math.max(...top.map((r) => r.pct), 1);

  return (
    <div className="mt-4 rounded-lg border border-border/60 bg-background/60 p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Missing values by column
      </div>
      <div className="space-y-1.5">
        {top.map((r) => (
          <div key={r.column} className="flex items-center gap-2 text-xs">
            <span className="w-28 shrink-0 truncate text-foreground/80" title={r.column}>
              {r.column}
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-amber-500"
                style={{ width: `${Math.min(100, (r.pct / max) * 100)}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right text-muted-foreground">{r.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DatasetInsight({ check, profileSource }: { check: ThresholdCheck; profileSource: any }) {
  const text = `${check.title} ${check.detail} ${check.observed}`.toLowerCase();
  const looksLikeMissingness = /missing|null value|completeness/.test(text);
  if (!looksLikeMissingness) return null;

  const rows = extractMissingness(profileSource);
  if (!rows) return null;

  return <MissingnessChart rows={rows} />;
}

// ── Threshold checks: compact tile grid, tap a tile for detail ──────────────

function shortLabel(title: string, maxLen = 20): string {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return title.slice(0, maxLen);

  let label = "";
  for (const word of words) {
    const candidate = label ? `${label} ${word}` : word;
    if (candidate.length > maxLen && label) break;
    label = candidate;
    if (label.length >= maxLen) break;
  }
  return label.length > maxLen ? `${label.slice(0, maxLen - 1)}…` : label;
}

function ThresholdTile({
  check,
  active,
  onClick,
}: {
  check: ThresholdCheck;
  active: boolean;
  onClick: () => void;
}) {
  const palette =
    check.status === "FAIL"
      ? "border-red-300 bg-red-50 text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300"
      : check.status === "WARN"
      ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300"
      : "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-[64px] flex-col items-center justify-center gap-1 rounded-lg border p-2.5 text-center transition-colors ${palette} ${
        active ? "ring-2 ring-primary ring-offset-1 ring-offset-background" : ""
      }`}
    >
      {statusIcon(check.status)}
      <span className="text-[11px] font-semibold leading-tight">{shortLabel(check.title)}</span>
    </button>
  );
}

function ThresholdDetailPanel({ check, profileSource }: { check: ThresholdCheck; profileSource: any }) {
  const s = statusStyle(check.status);
  return (
    <div className={`mt-4 rounded-xl border ${s.border} ${s.bg} p-5`}>
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-base font-bold text-foreground">
          [{check.check_id}] {check.title}
        </h4>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold ${s.badge}`}>{check.status}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {check.source} — {check.principle}
      </p>
      <dl className="mt-3 space-y-1.5 text-sm">
        <div>
          <dt className="inline font-semibold text-foreground">Observed </dt>
          <dd className="inline text-foreground/90">{check.observed}</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-foreground">Threshold </dt>
          <dd className="inline text-foreground/90">{check.threshold}</dd>
        </div>
      </dl>
      <p className="mt-3 text-sm text-muted-foreground">{check.detail}</p>
      <DatasetInsight check={check} profileSource={profileSource} />
    </div>
  );
}

function ThresholdPanel({ checks, profileSource }: { checks: ThresholdCheck[]; profileSource: any }) {
  const statusRank: Record<string, number> = { FAIL: 0, WARN: 1, PASS: 2 };
  const sorted = [...checks].sort((a, b) => (statusRank[a.status] ?? 3) - (statusRank[b.status] ?? 3));
  const [selectedId, setSelectedId] = useState<string | null>(sorted[0]?.check_id ?? null);
  const selected = checks.find((c) => c.check_id === selectedId) ?? null;

  return (
    <div>
      <div className="mb-2 text-xs text-muted-foreground">Tap a tile for detail</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {sorted.map((c) => (
          <ThresholdTile key={c.check_id} check={c} active={selectedId === c.check_id} onClick={() => setSelectedId(c.check_id)} />
        ))}
      </div>
      {selected ? <ThresholdDetailPanel check={selected} profileSource={profileSource} /> : null}
    </div>
  );
}

// ── RAG agent rules: filterable list, tap a row for detail ──────────────────

type StatusFilter = "ALL" | "FAIL" | "WARN" | "PENDING" | "PASS";

function ruleEffectiveStatus(rule: RagRule): string {
  if (rule.not_verifiable) return "PENDING";
  return (rule.status || "").toUpperCase();
}

function RagRuleRow({ rule, active, onClick }: { rule: RagRule; active: boolean; onClick: () => void }) {
  const eff = ruleEffectiveStatus(rule);
  const s = statusStyle(eff);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full min-w-0 items-center gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors ${
        active ? `${s.border} ${s.bg}` : "border-border bg-card hover:bg-muted/50"
      }`}
    >
      <span className="shrink-0">{statusIcon(eff)}</span>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{rule.flag}</span>
    </button>
  );
}

function RagRuleDetailPanel({ rule }: { rule: RagRule }) {
  const eff = ruleEffectiveStatus(rule);
  const s = statusStyle(eff);
  const observed = Array.isArray(rule.observed_value) ? rule.observed_value.join(", ") : rule.observed_value;
  const csrc = CHECK_SOURCE_LABELS[rule.check_source ?? ""];

  return (
    <div className={`mt-4 rounded-xl border ${s.border} ${s.bg} p-5`}>
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-base font-bold text-foreground">{rule.flag}</h4>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold ${s.badge}`}>{eff}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {rule.source} — {rule.principle}
        {csrc ? ` · ${csrc.label.replace(/^\S+\s/, "")}` : ""}
        {rule.not_verifiable ? " · not verifiable with current data" : ""}
      </p>
      {observed != null && observed !== "" ? (
        <p className="mt-3 text-sm text-foreground">
          Observed: <span className="text-foreground/90">{observed}</span>
        </p>
      ) : null}
      {rule.reasoning ? <p className="mt-2 text-xs italic text-violet-600 dark:text-violet-300">{rule.reasoning}</p> : null}
      <p className="mt-3 text-sm text-muted-foreground">{rule.suggestion}</p>
    </div>
  );
}

function RagRulesPanel({ rules }: { rules: RagRule[] }) {
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(rules[0]?.rule_id ?? null);

  const filtered = filter === "ALL" ? rules : rules.filter((r) => ruleEffectiveStatus(r) === filter);
  const selected = filtered.find((r) => r.rule_id === selectedId) ?? filtered[0] ?? null;

  const tabs: { key: StatusFilter; label: string }[] = [
    { key: "ALL", label: "All" },
    { key: "FAIL", label: "Fail" },
    { key: "WARN", label: "Warn" },
    { key: "PENDING", label: "Pending" },
    { key: "PASS", label: "Pass" },
  ];

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setFilter(t.key)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
              filter === t.key
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="space-y-1.5">
        {filtered.length ? (
          filtered.map((r) => (
            <RagRuleRow key={r.rule_id} rule={r} active={selected?.rule_id === r.rule_id} onClick={() => setSelectedId(r.rule_id)} />
          ))
        ) : (
          <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
            No rules match this filter.
          </div>
        )}
      </div>

      {selected ? <RagRuleDetailPanel rule={selected} /> : null}
    </div>
  );
}
