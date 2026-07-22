// Shared PASS/WARN/FAIL/N/A/PENDING summary tile row, used by every
// validation stage that runs a list of checks (Stage 2/3 Data Validation &
// Conceptual Soundness, Stage 6 Stress & Backtesting, Stage 7 Regulatory
// Compliance). Each stage previously computed and rendered this row with its
// own copy-pasted logic, and at least two of those copies (Stage 2/3, Stage
// 6) counted a "pending"/"cannot run yet" bucket into the displayed total
// without ever rendering a tile for it — so the total shown never matched
// the sum of the visible PASS/WARN/FAIL/N/A tiles. Centralizing here means
// the total is always derived from literally the same buckets rendered
// below, so it can't drift from what's on screen again.
export type CheckSummaryCounts = {
  pass?: number;
  warn?: number;
  fail?: number;
  na?: number;
  pending?: number;
};

const TONE_BORDER: Record<string, string> = {
  pass: "border-emerald-500/40 bg-emerald-500/10",
  warn: "border-amber-500/40 bg-amber-500/10",
  fail: "border-red-500/40 bg-red-500/10",
  na: "border-indigo-500/30 bg-indigo-500/5",
  pending: "border-slate-400/40 bg-slate-400/10",
  neutral: "border-border bg-background",
};

const TONE_TEXT: Record<string, string> = {
  pass: "text-emerald-600 dark:text-emerald-400",
  warn: "text-amber-600 dark:text-amber-400",
  fail: "text-red-600 dark:text-red-400",
  na: "text-indigo-600 dark:text-indigo-400",
  pending: "text-slate-500 dark:text-slate-400",
  neutral: "text-foreground",
};

// Never trust a separately-computed backend "total" field — derive it here,
// as the literal sum of every bucket this component renders, so the number
// shown as "Checks"/"Total Checks" can never disagree with PASS+WARN+FAIL+
// N/A+PENDING below it.
export function deriveCheckTotal(summary: CheckSummaryCounts): number {
  return (summary.pass ?? 0) + (summary.warn ?? 0) + (summary.fail ?? 0) + (summary.na ?? 0) + (summary.pending ?? 0);
}

export function CheckSummaryTiles({
  summary,
  checksLabel = "Checks",
  className = "",
}: {
  summary: CheckSummaryCounts;
  checksLabel?: string;
  className?: string;
}) {
  const total = deriveCheckTotal(summary);
  const tiles: { label: string; value: number; tone: string }[] = [
    { label: checksLabel, value: total, tone: "neutral" },
    { label: "PASS", value: summary.pass ?? 0, tone: "pass" },
    { label: "WARN", value: summary.warn ?? 0, tone: "warn" },
    { label: "FAIL", value: summary.fail ?? 0, tone: "fail" },
    { label: "N/A", value: summary.na ?? 0, tone: "na" },
    { label: "PENDING", value: summary.pending ?? 0, tone: "pending" },
  ];

  return (
    <div className={`grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 ${className}`}>
      {tiles.map((t) => (
        <div key={t.label} className={`rounded-xl border p-4 ${TONE_BORDER[t.tone] ?? TONE_BORDER.neutral}`}>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{t.label}</div>
          <div className={`mt-1 text-2xl font-bold ${TONE_TEXT[t.tone] ?? TONE_TEXT.neutral}`}>{t.value}</div>
        </div>
      ))}
    </div>
  );
}
