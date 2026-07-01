import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight, CheckCircle2, FileText, FileCheck } from "lucide-react";

export const Route = createFileRoute("/validation/intake")({
  head: () => ({ meta: [{ title: "Model Intake — Aegis Credit" }] }),
  component: Intake,
});

const meta = [
  ["Model ID", "CR-PD-XGB-027"],
  ["Model name", "Retail PD — XGBoost Champion"],
  ["Owner", "A. Khurana · Risk Validation"],
  ["Developer", "Credit Risk Modelling, EMEA"],
  ["Version", "v1.7.6"],
  ["Risk tier", "Tier 2 — Material"],
  ["Last validated", "12 Apr 2026"],
  ["Next review", "12 Jul 2026"],
];

const assumptions = [
  "Obligor population is stable across the validation window (Q1-Q2 2026).",
  "Macro-economic conditions remain within the central forward-looking scenario.",
  "Default flag definition aligns with IFRS 9 Stage 3 (90+ DPD).",
  "Behavioural features computed on a 12-month observation window.",
];

const artifacts = [
  { label: "Validation dataset", status: "Submitted", detail: "Used for Stage 2 automated checks." },
  { label: "Model development document", status: "Submitted", detail: "Needed for governance and concept review." },
  { label: "Training code / scripts", status: "Submitted", detail: "Required for replication & benchmarking." },
  { label: "Data dictionary / profile", status: "Optional", detail: "Supports data validation and documentation." },
  { label: "Assumptions & limitations", status: "Optional", detail: "Supports conceptual review and risk assessment." },
  { label: "Performance report", status: "Optional", detail: "Useful for Stage 5 performance benchmarking." },
];

const checklist = [
  "Model is registered in the model inventory",
  "Risk tier assignment has been documented",
  "Submitted artifacts cover dataset, MDD, and training code",
  "Previous validation findings (if any) have been reviewed",
  "Regulatory scope (IFRS 9 / SS1/23 / SS11/13) is identified",
  "Independent validation team has no conflict of interest",
  "Validation plan has been approved by the Head of Model Risk",
];

function Intake() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 1 — Intake & Governance"
        description="Capture model metadata, evidence artifacts, and governance attestation before proceeding to automated validation checks."
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold">Model metadata</h2>
              <p className="mt-1 text-xs text-muted-foreground">Key registration details supplied by the developer.</p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-xs font-semibold text-primary">
              <FileText className="h-3.5 w-3.5" /> Registered
            </div>
          </div>
          <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            {meta.map(([k, v]) => (
              <div key={k} className="flex flex-col rounded-lg border border-border bg-background p-3">
                <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{k}</dt>
                <dd className="mt-1 text-sm font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h3 className="text-sm font-semibold">Target definition</h3>
            <div className="mt-3 rounded-lg bg-primary-soft p-3 font-mono text-xs">
              default_12m ∈ {`{0, 1}`}<br />
              positive class = 90+ DPD within 12m
            </div>
            <div className="mt-3 text-xs text-muted-foreground">
              Base rate: <span className="font-semibold text-foreground">4.7%</span> · Sample size: 219,486
            </div>
          </div>

          <div className="rounded-xl border border-border bg-sidebar p-6 text-sidebar-foreground shadow-elegant">
            <h3 className="text-sm font-semibold">Risk tier</h3>
            <div className="mt-2 text-3xl font-semibold">Tier 2</div>
            <p className="mt-1 text-xs text-sidebar-foreground/70">Material — quarterly independent validation required.</p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold">Artifact inventory</h3>
            <p className="mt-1 text-xs text-muted-foreground">Uploaded evidence to support subsequent validation stages.</p>
          </div>
          <span className="rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-xs font-semibold text-primary">
            3 required, 3 optional
          </span>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {artifacts.map((artifact) => (
            <div key={artifact.label} className="rounded-xl border border-border bg-background p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{artifact.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{artifact.detail}</p>
                </div>
                <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-2 py-1 text-[11px] font-semibold text-primary">
                  <FileCheck className="h-3.5 w-3.5" /> {artifact.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold">Governance attestation</h3>
            <p className="mt-1 text-xs text-muted-foreground">Confirm the model and validation plan are ready to proceed.</p>
          </div>
          <span className="rounded-full border border-warning/20 bg-warning/10 px-3 py-1 text-xs font-semibold text-warning-foreground">
            Pending review
          </span>
        </div>

        <ul className="mt-4 grid gap-3 text-sm text-foreground/80 md:grid-cols-2">
          {checklist.map((item) => (
            <li key={item} className="flex gap-3 rounded-lg border border-border bg-background p-3">
              <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 text-right shadow-elegant">
        <div className="text-sm text-muted-foreground">Once intake is confirmed, proceed to Stage 2 data validation and automated checks.</div>
        <Link
          to="/validation/data-quality"
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          <span>Proceed to Stage 2</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
