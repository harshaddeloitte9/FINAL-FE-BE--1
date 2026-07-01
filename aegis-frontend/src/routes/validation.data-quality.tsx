import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, AreaChart, Area } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/validation/data-quality")({
  head: () => ({ meta: [{ title: "Data Validation — Aegis Credit" }] }),
  component: DataQuality,
});

const missing = [
  { feature: "Annual Income", pct: 4.2 },
  { feature: "DTI Ratio", pct: 1.1 },
  { feature: "Credit Utilization", pct: 0.4 },
  { feature: "LTV", pct: 7.6 },
  { feature: "Tenure", pct: 2.3 },
  { feature: "Region", pct: 0.0 },
];

const drift = Array.from({ length: 12 }, (_, i) => ({
  month: `M${i + 1}`,
  dev: 0.5 + Math.sin(i / 2) * 0.05,
  oot: 0.5 + Math.sin(i / 2) * 0.05 + (i > 7 ? 0.04 : 0),
}));

const checks = [
  { label: "Duplicate rows", value: "0.02%", status: "PASS" },
  { label: "Outliers (Z>4)", value: "1.6%", status: "WARN" },
  { label: "Class imbalance", value: "1 : 20", status: "WARN" },
  { label: "Sample representativeness", value: "PSI 0.08", status: "PASS" },
  { label: "Data leakage scan", value: "0 leaks", status: "PASS" },
  { label: "Schema drift", value: "Stable", status: "PASS" },
];

const cls = {
  PASS: "bg-primary-soft text-foreground border-primary/30",
  WARN: "bg-warning/20 text-warning-foreground border-warning/40",
  FAIL: "bg-destructive/10 text-destructive border-destructive/30",
} as const;

function DataQuality() {
  const passCount = checks.filter((item) => item.status === "PASS").length;
  const warnCount = checks.filter((item) => item.status === "WARN").length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Stage 2 — Data Validation"
        description="Run automated validation checks on the submitted dataset and verify sample fitness, leakage, and data quality."
      />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Automated validation summary</h3>
          <p className="mt-2 text-sm text-foreground/80">
            This stage verifies the dataset submitted in Intake and flags any issues that affect model validity.
          </p>
          <div className="mt-5 grid grid-cols-3 gap-3">
            <Stat label="Checks" value={checks.length.toString()} />
            <Stat label="PASS" value={passCount.toString()} tone="pass" />
            <Stat label="WARN" value={warnCount.toString()} tone="warn" />
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Stage outcome</h3>
          <p className="mt-2 text-sm text-foreground/80">
            Data Validation is intended to confirm the dataset is fit for independent model assessment and that no obvious data integrity issues exist.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-2 text-xs font-semibold text-primary">
            <span>Ready to proceed</span>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {checks.map((c) => (
          <div key={c.label} className="rounded-xl border border-border bg-card p-4 shadow-elegant">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{c.label}</div>
            <div className="mt-2 text-lg font-semibold tracking-tight">{c.value}</div>
            <span className={`mt-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${cls[c.status as keyof typeof cls]}`}>
              {c.status}
            </span>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Missing values by feature</h3>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={missing}>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                <XAxis dataKey="feature" tickLine={false} axisLine={false} fontSize={10} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} unit="%" />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Bar dataKey="pct" fill="oklch(0.76 0.18 130)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h3 className="text-sm font-semibold">Population stability (dev vs OOT)</h3>
          <p className="text-xs text-muted-foreground">PSI 0.08 — within tolerance</p>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={drift}>
                <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                <Area type="monotone" dataKey="dev" stroke="oklch(0.6 0.18 135)" fill="oklch(0.76 0.18 130)" fillOpacity={0.25} />
                <Area type="monotone" dataKey="oot" stroke="oklch(0.55 0.02 240)" fill="oklch(0.55 0.02 240)" fillOpacity={0.18} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h3 className="text-sm font-semibold">Data leakage detection</h3>
        <p className="mt-2 text-sm text-foreground/80">
          No future-information leakage detected across 87 candidate features. Two features were excluded
          during development for post-event observability and are correctly omitted from the production schema.
        </p>
      </section>

      <div className="text-right">
        <Link
          to="/validation/conceptual"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 3
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "pass" | "warn" }) {
  const classes =
    tone === "pass"
      ? "border border-primary/30 bg-primary-soft text-foreground"
      : tone === "warn"
      ? "border border-warning/30 bg-warning/10 text-warning-foreground"
      : "border border-border bg-background text-foreground";

  return (
    <div className={`rounded-xl p-4 ${classes}`}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold">{value}</div>
    </div>
  );
}
