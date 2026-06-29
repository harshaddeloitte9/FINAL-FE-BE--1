import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { featureImportance } from "@/lib/mock-data";

export const Route = createFileRoute("/validation/conceptual")({
  head: () => ({ meta: [{ title: "Conceptual Soundness — Aegis Credit" }] }),
  component: Conceptual,
});

const doc = [
  { label: "Model development document", status: "PASS" },
  { label: "Data lineage attestation", status: "PASS" },
  { label: "Independent code review", status: "PASS" },
  { label: "Sensitivity analysis report", status: "WARN" },
  { label: "Reproducibility package (seed, env)", status: "PASS" },
  { label: "Limitations & caveats statement", status: "WARN" },
] as const;

const assumptions = [
  { label: "Linearity in log-odds for monotonic features", verdict: "Holds", tone: "PASS" },
  { label: "Independence of behavioural & application features", verdict: "Partial — DTI/Util ρ=0.42", tone: "WARN" },
  { label: "Stationarity of macroeconomic regime", verdict: "Holds within window", tone: "PASS" },
  { label: "Default definition consistency (90 DPD)", verdict: "Aligned IFRS 9 Stage 3", tone: "PASS" },
] as const;

const StatusIcon = ({ s }: { s: "PASS" | "WARN" | "FAIL" }) =>
  s === "PASS" ? <CheckCircle2 className="h-4 w-4 text-primary" /> :
  s === "WARN" ? <AlertTriangle className="h-4 w-4 text-warning" /> :
  <XCircle className="h-4 w-4 text-destructive" />;

function Conceptual() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Conceptual Soundness Review"
        description="Are the chosen features, methodology, and assumptions appropriate for the stated business objective and regulatory context?"
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Feature relevance</h3>
          <p className="text-xs text-muted-foreground">Top SHAP-ranked drivers · economic plausibility check</p>
          <div className="mt-4 space-y-2">
            {featureImportance.slice(0, 8).map((f) => (
              <div key={f.feature} className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
                <span className="w-44 truncate text-sm font-medium">{f.feature}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${f.value * 400}%` }} />
                </div>
                <span className="w-12 text-right text-xs font-mono text-muted-foreground">{f.value.toFixed(2)}</span>
                <CheckCircle2 className="h-4 w-4 text-primary" />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Methodology review</h3>
          <ul className="mt-4 space-y-3 text-sm">
            <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 shrink-0 text-primary" /> XGBoost with monotonic constraints on DTI / Utilization.</li>
            <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 shrink-0 text-primary" /> Stratified 5-fold CV; SMOTE on training fold only.</li>
            <li className="flex gap-2"><AlertTriangle className="h-4 w-4 shrink-0 text-warning" /> Isotonic calibration applied — recommend Platt benchmark.</li>
            <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 shrink-0 text-primary" /> Class weights documented and reproducible.</li>
          </ul>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Model assumptions</h3>
          <div className="mt-3 divide-y divide-border">
            {assumptions.map((a) => (
              <div key={a.label} className="flex items-center justify-between gap-3 py-3 text-sm">
                <span className="flex-1">{a.label}</span>
                <span className="text-xs text-muted-foreground">{a.verdict}</span>
                <StatusIcon s={a.tone} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Documentation checklist</h3>
          <ul className="mt-3 divide-y divide-border">
            {doc.map((d) => (
              <li key={d.label} className="flex items-center justify-between py-3 text-sm">
                <span>{d.label}</span>
                <StatusIcon s={d.status} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-primary/30 bg-primary-soft p-6">
        <div className="text-xs font-semibold uppercase tracking-wider text-foreground/70">Regulatory alignment</div>
        <p className="mt-2 text-sm">
          Methodology is consistent with SS1/23 expectations on transparency, monotonicity, and challenger
          benchmarking. Two amber items (sensitivity report, limitations statement) require remediation
          prior to sign-off.
        </p>
      </section>
    </div>
  );
}
