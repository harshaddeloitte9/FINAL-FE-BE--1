import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";

export const Route = createFileRoute("/ead")({
  head: () => ({ meta: [{ title: "EAD Model — Aegis Credit" }] }),
  component: EadModelPage,
});

function EadModelPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="EAD Model" description="This workflow is under development." />
      <div className="rounded-xl border border-border bg-card p-8 text-sm text-muted-foreground">
        EAD Model
        <br />
        This workflow is under development.
      </div>
    </div>
  );
}
