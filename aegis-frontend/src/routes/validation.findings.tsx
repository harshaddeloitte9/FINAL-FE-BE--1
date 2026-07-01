import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { CheckCircle2, AlertTriangle, XCircle, FileDown, FileText } from "lucide-react";

export const Route = createFileRoute("/validation/findings")({
  head: () => ({ meta: [{ title: "Validation Findings & Report — Aegis Credit" }] }),
  component: Findings,
});

const findings = [
  { id: "F-01", area: "Regulatory", title: "Challenger benchmarks missing for Q1 cycle", severity: "High", status: "FAIL" },
  { id: "F-02", area: "Data", title: "LTV missingness at 7.6% — imputation strategy undocumented", severity: "Medium", status: "WARN" },
  { id: "F-03", area: "Conceptual", title: "Calibration limitations statement not provided", severity: "Medium", status: "WARN" },
  { id: "F-04", area: "Performance", title: "Hold-out AUC 0.873 — exceeds 0.80 threshold", severity: "Low", status: "PASS" },
  { id: "F-05", area: "Stress", title: "Severe scenario well-behaved within governance limits", severity: "Low", status: "PASS" },
  { id: "F-06", area: "Backtesting", title: "Predicted vs actual default rate aligned (binomial p=0.18)", severity: "Low", status: "PASS" },
] as const;

const cls = {
  PASS: "bg-primary-soft text-foreground border-primary/30",
  WARN: "bg-warning/20 text-warning-foreground border-warning/40",
  FAIL: "bg-destructive/10 text-destructive border-destructive/30",
} as const;

const Icon = ({ s }: { s: "PASS" | "WARN" | "FAIL" }) =>
  s === "PASS" ? <CheckCircle2 className="h-3.5 w-3.5" /> :
  s === "WARN" ? <AlertTriangle className="h-3.5 w-3.5" /> :
  <XCircle className="h-3.5 w-3.5" />;

function Findings() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 8 — Findings & Final Report"
        description="Consolidated findings, risks, and recommendation for management and the Model Risk Committee."
        actions={
          <>
            <button className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:border-primary/40">
              <FileText className="h-4 w-4" /> Preview report
            </button>
            <button className="inline-flex items-center gap-2 rounded-lg gradient-primary px-3 py-2 text-sm font-semibold text-primary-foreground shadow-elegant">
              <FileDown className="h-4 w-4" /> Export PDF
            </button>
          </>
        }
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Executive summary</h3>
          <p className="mt-3 text-sm text-foreground/80">
            The XGBoost retail PD model demonstrates strong discriminatory power (AUC 0.873, KS 0.612) and
            stable behaviour across stress scenarios and backtesting windows. Independent validation
            concludes the model is <span className="font-semibold">fit for intended use</span>, conditional on
            remediation of one high-severity governance finding (missing Q1 challenger benchmarks) and two
            medium-severity documentation gaps.
          </p>
        </div>

        <div className="rounded-xl border border-warning/40 bg-warning/10 p-6 shadow-elegant">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-warning-foreground">Final recommendation</div>
          <div className="mt-2 text-2xl font-semibold">Approve with conditions</div>
          <p className="mt-2 text-xs text-foreground/80">
            Re-validate in 90 days post-remediation. Maintain Tier 2 quarterly oversight cadence.
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          ["Pass",    "8", "border-primary/30 bg-primary-soft"],
          ["Warning", "2", "border-warning/40 bg-warning/10"],
          ["Fail",    "1", "border-destructive/30 bg-destructive/10"],
        ].map(([l, v, c]) => (
          <div key={l} className={`rounded-xl border p-5 shadow-elegant ${c}`}>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{l}</div>
            <div className="mt-2 text-3xl font-semibold tabular-nums">{v}</div>
          </div>
        ))}
      </section>

      <section className="rounded-xl border border-border bg-card shadow-elegant">
        <div className="border-b border-border p-6">
          <h3 className="text-sm font-semibold">Key observations & risks</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-background text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-6 py-3 text-left">ID</th>
                <th className="px-6 py-3 text-left">Area</th>
                <th className="px-6 py-3 text-left">Finding</th>
                <th className="px-6 py-3 text-left">Severity</th>
                <th className="px-6 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {findings.map((f) => (
                <tr key={f.id}>
                  <td className="px-6 py-3 font-mono text-xs text-muted-foreground">{f.id}</td>
                  <td className="px-6 py-3 text-xs">{f.area}</td>
                  <td className="px-6 py-3 font-medium">{f.title}</td>
                  <td className="px-6 py-3 text-xs">{f.severity}</td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cls[f.status]}`}>
                      <Icon s={f.status} />
                      {f.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h3 className="text-sm font-semibold">Sign-off</h3>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            ["Validator", "A. Khurana", "Risk Validation"],
            ["Model Owner", "M. Petrov", "Credit Risk Modelling"],
            ["Committee", "Model Risk Committee", "Pending — 22 Apr 2026"],
          ].map(([role, name, sub]) => (
            <div key={role} className="rounded-lg border border-border bg-background p-4">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{role}</div>
              <div className="mt-1 text-sm font-semibold">{name}</div>
              <div className="text-xs text-muted-foreground">{sub}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
