import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight, FileText, Database, BookOpen, GitCompareArrows, BarChart3, Activity, ShieldCheck, ClipboardCheck } from "lucide-react";

export const Route = createFileRoute("/validation/")({
  head: () => ({
    meta: [
      { title: "Model Validation — Aegis Credit" },
      { name: "description", content: "Independent validation: intake, data quality, conceptual soundness, challenger, performance, stress, regulatory, findings." },
    ],
  }),
  component: ValidationHome,
});

const stages = [
  { to: "/validation/intake", icon: FileText, title: "Model Intake & Intended Use", desc: "Metadata, business objective, target, assumptions." },
  { to: "/validation/data-quality", icon: Database, title: "Data Quality & Representativeness", desc: "Missing, duplicates, outliers, leakage, sample fitness." },
  { to: "/validation/conceptual", icon: BookOpen, title: "Conceptual Soundness", desc: "Feature relevance, assumptions, methodology, documentation." },
  { to: "/validation/challenger", icon: GitCompareArrows, title: "Challenger Model Analysis", desc: "Champion vs challenger, side-by-side metrics, ranking." },
  { to: "/validation/performance", icon: BarChart3, title: "Performance Validation", desc: "ROC-AUC, KS, Gini, calibration, threshold analysis." },
  { to: "/validation/stress", icon: Activity, title: "Sensitivity, Stress & Backtesting", desc: "Scenarios, stability, stress sims, backtests." },
  { to: "/validation/regulatory", icon: ShieldCheck, title: "Regulatory Compliance", desc: "IFRS 9, IFRS 7, SS1/23 — RAG status & remediation." },
  { to: "/validation/findings", icon: ClipboardCheck, title: "Findings & Final Report", desc: "Executive summary, risks, recommendation, export pack." },
] as const;

function ValidationHome() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Model Validation"
        description="Independent review of an existing credit risk model across performance, conceptual soundness, regulatory compliance, and governance."
      />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["RAG status", "AMBER", "1 high, 2 medium findings"],
          ["Compliance", "92.4%", "IFRS 9 / IFRS 7 / SS1/23"],
          ["Champion AUC", "0.873", "vs challenger 0.869"],
          ["Validation cycle", "Q2 · 2026", "Quarterly, Tier 2"],
        ].map(([l, v, s]) => (
          <div key={l} className="rounded-xl border border-border bg-card p-5 shadow-elegant">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{l}</div>
            <div className="mt-2 text-2xl font-semibold tracking-tight">{v}</div>
            <div className="mt-1 text-xs text-muted-foreground">{s}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {stages.map((s, i) => {
          const Icon = s.icon;
          return (
            <Link
              key={s.to}
              to={s.to}
              className="group flex items-start gap-4 rounded-xl border border-border bg-card p-5 shadow-elegant transition-all hover:-translate-y-0.5 hover:border-primary/40"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-muted-foreground">0{i + 1}</span>
                  <h3 className="text-sm font-semibold">{s.title}</h3>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{s.desc}</p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
            </Link>
          );
        })}
      </section>
    </div>
  );
}
