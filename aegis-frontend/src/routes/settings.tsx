import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Aegis Credit" }] }),
  component: Settings,
});

const sections = [
  { title: "Organization", body: "Deloitte Risk Advisory · UK & Ireland · 124 seats" },
  { title: "Default model tier", body: "Tier 2 (Material) — quarterly validation cadence" },
  { title: "Regulatory frameworks", body: "IFRS 9 · IFRS 7 · PRA SS1/23 · Basel IV (advanced)" },
  { title: "AI assistant model", body: "Ollama · llama3.1-70b · ChromaDB regulatory corpus v4.2" },
  { title: "Audit trail retention", body: "7 years · WORM storage · SOC 2 Type II" },
];

function Settings() {
  return (
    <div className="space-y-8">
      <PageHeader title="Settings" description="Workspace, governance, and integration preferences." />
      <div className="divide-y divide-border rounded-2xl border border-border bg-card shadow-elegant">
        {sections.map((s) => (
          <div key={s.title} className="flex flex-col gap-1 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-semibold">{s.title}</div>
              <div className="text-sm text-muted-foreground">{s.body}</div>
            </div>
            <button className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:border-primary/40">
              Edit
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
