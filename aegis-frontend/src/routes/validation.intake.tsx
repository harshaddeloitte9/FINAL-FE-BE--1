import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";

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

function Intake() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Model Intake & Intended Use"
        description="Authoritative metadata, intended use, target variable, and modelling assumptions registered for independent validation."
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-sm font-semibold">Model metadata</h2>
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
            <h3 className="text-sm font-semibold">Target variable</h3>
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

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Business objective</h3>
          <p className="mt-3 text-sm text-foreground/80">
            Estimate 12-month probability of default for the retail unsecured lending portfolio to support
            origination decisioning, IFRS 9 ECL Stage 2 transitions, and capital adequacy reporting.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Intended use summary</h3>
          <ul className="mt-3 space-y-2 text-sm text-foreground/80">
            <li>· Application scoring at origination (cut-off 0.50)</li>
            <li>· Behavioural rescoring monthly post-booking</li>
            <li>· Input into IFRS 9 ECL staging engine</li>
            <li>· Not approved for capital-floor or regulatory PD reporting</li>
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h3 className="text-sm font-semibold">Key assumptions</h3>
        <ul className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {assumptions.map((a) => (
            <li key={a} className="flex gap-3 rounded-lg border border-border bg-background p-3 text-sm">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              {a}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
