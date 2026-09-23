import type { ComponentType } from "react";
import { Percent, Copy, ShieldQuestion, Layers, CalendarClock, Target } from "lucide-react";
import AnimatedNumber from "@/components/animated-number";
import { StatusDot } from "./status-badge";
import {
  getCompleteness,
  getUniqueness,
  getValidity,
  getSchemaHealth,
  getTimeliness,
  getTargetHealth,
} from "./selectors";

function HealthTile({
  icon: Icon,
  label,
  headline,
  evidence,
  status,
  animate,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  headline: string;
  evidence: string;
  status: "healthy" | "review" | "not_evaluated" | "critical";
  animate?: { value: number; formatter?: (n: number) => string };
}) {
  return (
    <div className="flex flex-col gap-2 bg-white p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</span>
        <Icon className="h-4 w-4 shrink-0 text-slate-300" />
      </div>
      <div className="text-[27px] font-bold leading-none tabular-nums text-slate-900">
        {animate ? <AnimatedNumber value={animate.value} formatter={animate.formatter} /> : headline}
      </div>
      <div className="flex items-start gap-1.5">
        <StatusDot status={status} />
        <span className="text-[12px] leading-snug text-slate-500">{evidence}</span>
      </div>
    </div>
  );
}

// The Dataset Health / Quality KPI strip — six tiles, each derived from a
// real profile field via selectors.ts. "Not evaluated" tiles render the
// same way as "Healthy"/"Review" ones (never silently blank), so a reviewer
// can see at a glance which checks Aegis actually ran for this dataset.
export function DatasetHealthStrip({ profile }: { profile: any }) {
  const completeness = getCompleteness(profile);
  const uniqueness = getUniqueness(profile);
  const validity = getValidity(profile);
  const schema = getSchemaHealth(profile);
  const timeliness = getTimeliness(profile);
  const targetHealth = getTargetHealth(profile);

  const missingPct = typeof profile?.missing_percentage === "number" ? profile.missing_percentage : null;
  const duplicateRows = typeof profile?.duplicate_rows === "number" ? profile.duplicate_rows : null;

  return (
    <div className="grid grid-cols-2 divide-x divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm sm:grid-cols-3 xl:grid-cols-6 xl:divide-y-0">
      <HealthTile
        icon={Percent}
        label="Completeness"
        headline={completeness.headline}
        evidence={completeness.evidence}
        status={completeness.status}
        animate={missingPct !== null ? { value: Math.max(0, 100 - missingPct), formatter: (n) => `${n.toFixed(1)}%` } : undefined}
      />
      <HealthTile
        icon={Copy}
        label="Duplicates"
        headline={uniqueness.headline}
        evidence={uniqueness.evidence}
        status={uniqueness.status}
        animate={duplicateRows !== null ? { value: duplicateRows } : undefined}
      />
      {/* Real numeric-format/date-parse evidence from getValidity(), with a
          fixed trailing note (same wording as the Quality Dimensions panel)
          for the range/allowed-value checks that remain not evaluated. */}
      <HealthTile
        icon={ShieldQuestion}
        label="Validity"
        headline={validity.headline}
        evidence={`${validity.evidence} Range/allowed-value not evaluated — no business rules configured.`}
        status={validity.status}
      />
      <HealthTile icon={Layers} label="Schema" headline={schema.headline} evidence={schema.evidence} status={schema.status} />
      <HealthTile
        icon={CalendarClock}
        label="Timeliness"
        headline={timeliness.headline}
        evidence={timeliness.evidence}
        status={timeliness.status}
      />
      <HealthTile
        icon={Target}
        label="Target Health"
        headline={targetHealth.headline}
        evidence={targetHealth.evidence}
        status={targetHealth.status}
      />
    </div>
  );
}
