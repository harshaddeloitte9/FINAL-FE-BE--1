import { cn } from "@/lib/utils";
import { ArrowUpRight } from "lucide-react";

export function KpiCard({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: "positive" | "warning" | "negative" | "neutral";
}) {
  const toneColor: Record<string, string> = {
    positive: "text-primary",
    warning: "text-warning-foreground bg-warning/20",
    negative: "text-destructive",
    neutral: "text-muted-foreground",
  };
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-elegant transition-all hover:-translate-y-0.5 hover:border-primary/40">
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <ArrowUpRight className="h-4 w-4 text-muted-foreground/40 transition-colors group-hover:text-primary" />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight tabular-nums">{value}</div>
      {delta && (
        <div
          className={cn(
            "mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
            tone === "warning" ? toneColor.warning : "bg-transparent",
            tone !== "warning" && toneColor[tone],
          )}
        >
          {delta}
        </div>
      )}
      <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-primary/5 blur-2xl transition-opacity group-hover:opacity-100" />
    </div>
  );
}
