import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";

export const Route = createFileRoute("/lgd")({
  head: () => ({ meta: [{ title: "LGD Model — Aegis Credit" }] }),
  component: LgdModelPage,
});

function LgdModelPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="LGD Model" description="This workflow is under development." />
      <div className="rounded-xl border border-border bg-card p-8 text-sm text-muted-foreground">
        LGD Model
        <br />
        This workflow is under development.
      </div>
    </div>
  );
}
