// Shared visual primitives for the Model Validation pipeline (Stage 1-7 +
// dashboard) — ports the exact card/hero/KPI/pipeline patterns already
// established in the Model Development pipeline (see EvalCard, KpiTile/
// KpiStrip, and TrainingPipeline in model-training-evaluation.tsx) so the
// Validation workspace reads as the same product instead of a fork. Purely
// presentational: nothing here touches data, calculations, or API calls.
import { type ComponentType, type ReactNode } from "react";
import { CheckCircle2, Circle, Loader2, AlertTriangle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Executive hero header — same gradient used at the top of Model
// Training/Evaluation's stage panels. `eyebrow` is the "STEP N · ..." label. ──
export function StageHero({
  eyebrow,
  title,
  description,
  chips,
}: {
  eyebrow: string;
  title: string;
  description: string;
  chips?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-900 via-indigo-900 to-blue-800 p-6 text-white shadow-[0_16px_36px_rgba(15,23,42,0.16)]">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.2em] text-indigo-200">{eyebrow}</div>
          <h2 className="mt-2 text-2xl font-semibold">{title}</h2>
          <p className="mt-2 max-w-2xl text-sm text-slate-200">{description}</p>
        </div>
        {chips && <div className="flex flex-wrap items-center gap-2">{chips}</div>}
      </div>
    </div>
  );
}

// Small pill used inside a StageHero's chip row for a real status/count.
export function HeroChip({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" }) {
  const toneClasses = {
    neutral: "border-sky-300/50 bg-sky-400/15 text-sky-100",
    success: "border-emerald-300/50 bg-emerald-400/15 text-emerald-200",
    warning: "border-amber-300/50 bg-amber-400/15 text-amber-200",
  }[tone];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold", toneClasses)}>
      {children}
    </span>
  );
}

// ─── Card — icon-badge header + body, exact rounded-2xl/shadow-sm treatment
// EvalCard uses, extended with an optional icon badge (lucide, tinted box —
// matches the icon-badge convention already used across Data Upload /
// Model Training). ──
export function VCard({
  icon: Icon,
  title,
  sub,
  actions,
  badge,
  children,
  className,
  contentClassName,
}: {
  icon?: ComponentType<{ className?: string }>;
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  badge?: { text: string; tone?: "primary" | "amber" | "emerald" | "rose" | "violet" | "slate" };
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <section className={cn("rounded-2xl border border-slate-200 bg-white p-6 shadow-sm", className)}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {Icon && (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Icon className="h-4 w-4" />
            </div>
          )}
          <div>
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
          </div>
        </div>
        {(actions || badge) && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {actions}
            {badge && (
              <span className={cn("whitespace-nowrap rounded-full px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide", BADGE_TONE[badge.tone ?? "primary"])}>
                {badge.text}
              </span>
            )}
          </div>
        )}
      </div>
      <div className={cn("mt-4", contentClassName)}>{children}</div>
    </section>
  );
}

export const BADGE_TONE: Record<string, string> = {
  primary: "bg-blue-50 text-blue-700",
  amber: "bg-amber-50 text-amber-700",
  emerald: "bg-emerald-50 text-emerald-700",
  rose: "bg-rose-50 text-rose-700",
  violet: "bg-violet-50 text-violet-700",
  slate: "bg-slate-100 text-slate-600",
};

// ─── KPI strip — exact port of KpiTile/KpiStrip from Model Training &
// Evaluation. ──
export type KpiTone = "primary" | "amber" | "emerald" | "rose" | "violet" | "slate";

export function KpiTile({
  icon: Icon,
  label,
  value,
  sub,
  tone = "primary",
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: KpiTone;
}) {
  const toneClasses: Record<KpiTone, string> = {
    primary: "bg-blue-500/10 text-blue-600",
    amber: "bg-amber-500/10 text-amber-600",
    emerald: "bg-emerald-500/10 text-emerald-600",
    rose: "bg-rose-500/10 text-rose-600",
    violet: "bg-violet-500/10 text-violet-600",
    slate: "bg-slate-500/10 text-slate-600",
  };
  return (
    <div className="bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-500">{label}</span>
        <span className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-md", toneClasses[tone])}>
          <Icon className="h-3.5 w-3.5" />
        </span>
      </div>
      <div className="mt-2 text-2xl font-bold tabular-nums text-slate-900">{value}</div>
      {sub && <div className="mt-0.5 truncate text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

export function KpiStrip({ tiles }: { tiles: Array<{ icon: ComponentType<{ className?: string }>; label: string; value: ReactNode; sub?: string; tone?: KpiTone }> }) {
  return (
    <div className="grid grid-cols-2 divide-x divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0">
      {tiles.map((tile) => (
        <KpiTile key={tile.label} {...tile} />
      ))}
    </div>
  );
}

// ─── Validation pipeline — the 7-stage progress stepper, exact visual port
// of TrainingPipeline (Model Development Pipeline). Every node's status must
// be derived from real state by the caller — this component only renders
// whatever status it's given. "warn"/"fail" extend the original 3-state
// model for stages (e.g. Stage 3 Replication) that can complete with a
// review-worthy or failing outcome rather than a plain checkmark. ──
export type PipelineNodeStatus = "complete" | "active" | "warn" | "fail" | "pending";

export function ValidationPipeline({
  nodes,
  onSelect,
  title = "Validation Pipeline",
  compact = false,
}: {
  nodes: Array<{ label: string; status: PipelineNodeStatus; sub?: string; to?: string }>;
  onSelect?: (index: number) => void;
  title?: string;
  compact?: boolean;
}) {
  const activeIndex = nodes.findIndex((n) => n.status === "active");
  const settledCount = nodes.filter((n) => n.status === "complete" || n.status === "warn" || n.status === "fail").length;
  const stepNumber = (activeIndex >= 0 ? activeIndex : settledCount) + 1;
  return (
    <div className={cn("rounded-2xl border border-slate-200 bg-white shadow-sm", compact ? "p-4" : "p-5")}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide text-blue-700">
          Stage {Math.min(stepNumber, nodes.length)} of {nodes.length}
        </span>
      </div>
      <div className={cn("flex items-center gap-1 overflow-x-auto pb-1", compact ? "mt-4" : "mt-5")}>
        {nodes.map((n, i) => (
          <div key={n.label} className="flex items-center">
            <button
              type="button"
              disabled={!onSelect}
              onClick={() => onSelect?.(i)}
              className={cn("flex flex-col items-center gap-1.5", onSelect && "cursor-pointer")}
            >
              <div
                className={cn(
                  "flex shrink-0 items-center justify-center rounded-xl border text-sm font-bold transition-all duration-500",
                  compact ? "h-9 w-9" : "h-11 w-11",
                  n.status === "complete" && "border-emerald-600 bg-emerald-600 text-white",
                  n.status === "active" && "border-blue-600 bg-blue-600 text-white shadow-[0_0_0_4px_rgba(37,99,235,0.15)]",
                  n.status === "warn" && "border-amber-500 bg-amber-500 text-white",
                  n.status === "fail" && "border-rose-600 bg-rose-600 text-white",
                  n.status === "pending" && "border-slate-200 bg-slate-50 text-slate-400",
                )}
              >
                {n.status === "complete" ? <CheckCircle2 className={compact ? "h-4 w-4" : "h-5 w-5"} />
                  : n.status === "active" ? <Loader2 className="h-4 w-4 animate-spin" />
                  : n.status === "warn" ? <AlertTriangle className="h-4 w-4" />
                  : n.status === "fail" ? <XCircle className="h-4 w-4" />
                  : i + 1}
              </div>
              <div className="text-center">
                <div className="whitespace-nowrap text-[10.5px] font-semibold text-slate-700">{n.label}</div>
                {n.sub && <div className="whitespace-nowrap text-[9.5px] text-slate-400">{n.sub}</div>}
              </div>
            </button>
            {i < nodes.length - 1 && (
              <div
                className={cn(
                  "mx-2 mb-5 h-px w-6 shrink-0",
                  n.status === "complete" ? "bg-emerald-300"
                    : n.status === "warn" ? "bg-amber-300"
                    : n.status === "fail" ? "bg-rose-300"
                    : "bg-slate-200",
                )}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Small inline status pill for PASS/WARN/FAIL/PENDING/N-A style verdicts —
// same tone language as CheckSummaryTiles (@/components/check-summary) so a
// finding's badge and its tile-row total always agree visually.
const STATUS_PILL_TONE: Record<string, string> = {
  pass: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warn: "border-amber-200 bg-amber-50 text-amber-700",
  fail: "border-red-200 bg-red-50 text-red-700",
  na: "border-indigo-200 bg-indigo-50 text-indigo-700",
  pending: "border-slate-200 bg-slate-50 text-slate-500",
};

export function StatusPill({ tone, children }: { tone: keyof typeof STATUS_PILL_TONE; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold", STATUS_PILL_TONE[tone] ?? STATUS_PILL_TONE.pending)}>
      {children}
    </span>
  );
}

// Purposeful empty state — matches the dashed-box pattern used across the
// app for "not run yet" / "no data" states instead of a blank card.
export function VEmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-300 bg-slate-50/70 px-6 py-10 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-50 text-blue-600">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-500">{description}</p>
      </div>
      {action}
    </div>
  );
}

export function DefRow({ label, value, mono, highlight }: { label: string; value: ReactNode; mono?: boolean; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span
        className={cn(
          "rounded-md border px-2 py-0.5 text-right font-semibold",
          mono && "font-mono",
          highlight ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-100 bg-slate-50 text-slate-900",
        )}
      >
        {value}
      </span>
    </div>
  );
}

export { Circle as PendingDot };
