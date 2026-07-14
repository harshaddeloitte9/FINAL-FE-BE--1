import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { regulatoryChecks } from "@/lib/mock-data";
import { useDataset } from "@/lib/app-context";
import { ArrowRight, CheckCircle2, AlertTriangle, XCircle, ChevronDown, Download } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/validation/regulatory")({
  head: () => ({ meta: [{ title: "Regulatory Compliance — Aegis Credit" }] }),
  component: Regulatory,
});

const badge = {
  PASS: { Icon: CheckCircle2, cls: "bg-primary-soft text-foreground border-primary/30" },
  WARNING: { Icon: AlertTriangle, cls: "bg-warning/20 text-warning-foreground border-warning/40" },
  FAIL: { Icon: XCircle, cls: "bg-destructive/10 text-destructive border-destructive/30" },
};

const sevDot: Record<string, string> = {
  High: "bg-destructive",
  Medium: "bg-warning",
  Low: "bg-primary",
};

function Regulatory() {
  const [open, setOpen] = useState<string | null>("SS123-4.1");
  const { file, profile } = useDataset();
  const datasetName = profile?.dataset_name ?? file?.name ?? "the active validation dataset";
  const datasetReady = Boolean(file || profile?.csv_text || profile?.dataset_name);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 7 — Regulatory Compliance Review"
        description="Automated review against IFRS 9, IFRS 7, and PRA SS1/23 with severity-weighted scoring and remediation."
        actions={
          <button className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:border-primary/40">
            <Download className="h-4 w-4" /> Compliance report
          </button>
        }
      />

      <section className="rounded-xl border border-border bg-background p-4 text-sm text-muted-foreground">
        {datasetReady ? (
          <>Using the shared dataset from Stage 1 / Stage 2: <span className="font-semibold text-foreground">{datasetName}</span>.</>
        ) : (
          <>No active dataset is available in shared state yet. Complete Stage 1 Intake and Stage 2 Data Validation first.</>
        )}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          {regulatoryChecks.map((group) => (
            <div key={group.framework} className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold">{group.framework}</h2>
                <span className="text-xs text-muted-foreground">{group.rules.length} rules</span>
              </div>
              <div className="space-y-2">
                {group.rules.map((r) => {
                  const B = badge[r.status as keyof typeof badge];
                  const isOpen = open === r.id;
                  const canOpen = r.status !== "PASS";
                  return (
                    <div key={r.id} className="rounded-lg border border-border bg-background">
                      <button
                        onClick={() => canOpen && setOpen(isOpen ? null : r.id)}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left"
                      >
                        <span className={cn("h-2 w-2 rounded-full", sevDot[r.severity])} />
                        <span className="text-xs font-mono text-muted-foreground">{r.id}</span>
                        <span className="flex-1 text-sm font-medium">{r.title}</span>
                        <span className="hidden text-[10px] uppercase tracking-wider text-muted-foreground sm:inline">
                          {r.severity}
                        </span>
                        <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold", B.cls)}>
                          <B.Icon className="h-3.5 w-3.5" />
                          {r.status}
                        </span>
                        {canOpen && (
                          <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")} />
                        )}
                      </button>
                      {isOpen && canOpen && "detail" in r && (
                        <div className="border-t border-border px-4 py-3 text-sm">
                          <p className="text-foreground/80">{r.detail}</p>
                          <div className="mt-3 rounded-md border border-primary/30 bg-primary-soft p-3 text-xs">
                            <div className="font-semibold uppercase tracking-wider text-foreground/70">
                              Suggested remediation
                            </div>
                            <div className="mt-1 text-foreground/90">{r.remediation}</div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h3 className="text-sm font-semibold">Compliance score</h3>
            <div className="mt-4 flex flex-col items-center">
              <div
                className="relative h-40 w-40 rounded-full"
                style={{
                  background: "conic-gradient(oklch(0.76 0.18 130) 0 332deg, oklch(0.92 0.005 240) 332deg 360deg)",
                }}
              >
                <div className="absolute inset-2 flex flex-col items-center justify-center rounded-full bg-card">
                  <span className="text-4xl font-semibold tracking-tight">92</span>
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground">out of 100</span>
                </div>
              </div>
              <div className="mt-4 text-center text-xs text-muted-foreground">
                Down 2 pts from previous cycle due to challenger benchmark gap.
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h3 className="text-sm font-semibold">RAG summary</h3>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-destructive" /> Red</span><span className="font-semibold">1</span></li>
              <li className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-warning" /> Amber</span><span className="font-semibold">2</span></li>
              <li className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-primary" /> Green</span><span className="font-semibold">8</span></li>
            </ul>
          </div>

          <div className="rounded-xl border border-border bg-sidebar p-6 text-sidebar-foreground shadow-elegant">
            <h3 className="text-sm font-semibold">Model risk tier</h3>
            <div className="mt-3 text-3xl font-semibold">Tier 2</div>
            <p className="mt-1 text-xs text-sidebar-foreground/70">Material — quarterly independent validation required.</p>
          </div>
        </aside>
      </div>

      <div className="text-right">
        <Link
          to="/validation/findings"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 8
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
