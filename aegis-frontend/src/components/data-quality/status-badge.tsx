import { CheckCircle2, AlertTriangle, MinusCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DqStatus } from "./selectors";

const STATUS_CONFIG: Record<DqStatus, { label: string; classes: string; Icon: typeof CheckCircle2 }> = {
  healthy: { label: "Healthy", classes: "bg-emerald-50 text-emerald-700 border-emerald-200", Icon: CheckCircle2 },
  review: { label: "Review", classes: "bg-amber-50 text-amber-700 border-amber-200", Icon: AlertTriangle },
  not_evaluated: { label: "Not evaluated", classes: "bg-slate-100 text-slate-500 border-slate-200", Icon: MinusCircle },
  critical: { label: "Critical", classes: "bg-rose-50 text-rose-700 border-rose-200", Icon: XCircle },
};

export function StatusBadge({ status, label, className }: { status: DqStatus; label?: string; className?: string }) {
  const cfg = STATUS_CONFIG[status];
  const Icon = cfg.Icon;
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold", cfg.classes, className)}>
      <Icon className="h-3 w-3 shrink-0" />
      {label ?? cfg.label}
    </span>
  );
}

// A small dot-only variant for dense rows (issues/column tables) where a
// full pill per cell would be too heavy.
export function StatusDot({ status }: { status: DqStatus }) {
  const dotClasses: Record<DqStatus, string> = {
    healthy: "bg-emerald-500",
    review: "bg-amber-500",
    not_evaluated: "bg-slate-300",
    critical: "bg-rose-500",
  };
  return <span className={cn("inline-block h-2 w-2 shrink-0 rounded-full", dotClasses[status])} aria-hidden="true" />;
}
