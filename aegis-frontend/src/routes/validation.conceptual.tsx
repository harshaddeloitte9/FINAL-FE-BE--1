import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app-shell";
import { ArrowRight, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { formUpload } from "@/lib/api";

export const Route = createFileRoute("/validation/conceptual")({
  head: () => ({ meta: [{ title: "Stage 3 — Conceptual Soundness — Aegis Credit" }] }),
  component: Conceptual,
});

// Component renders entirely from backend response; no local mock data kept.

function Conceptual() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    const form = new FormData();
    // No files by default; empty intake will be accepted by backend.
    form.append("intake_json", JSON.stringify({}));

    void formUpload<any>("/validation/stage3/run", form)
      .then((resp) => {
        if (!active) return;
        setData(resp);
      })
      .catch((err) => {
        console.error("Stage3 fetch error", err);
        if (!active) return;
        setError(err?.message ?? String(err));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const renderStatusIcon = (s: string | undefined) =>
    s === "PASS" ? <CheckCircle2 className="h-4 w-4 text-primary" /> :
    s === "WARN" ? <AlertTriangle className="h-4 w-4 text-warning" /> :
    <XCircle className="h-4 w-4 text-destructive" />;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Conceptual Soundness Review"
        description="Are the chosen features, methodology, and assumptions appropriate for the stated business objective and regulatory context?"
      />

      {loading ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center">Loading Conceptual Soundness...</div>
      ) : error ? (
        <div className="rounded-xl border border-border bg-card p-6 text-destructive">Error loading Stage 3: {error}</div>
      ) : (
        <>
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Feature relevance</h3>
              <p className="text-xs text-muted-foreground">Top SHAP-ranked drivers · economic plausibility check</p>
              <div className="mt-4 space-y-2">
                {data?.featureRelevance?.importance_df && data.featureRelevance.importance_df.length > 0 ? (
                  data.featureRelevance.importance_df.slice(0, 8).map((f: any) => (
                    <div key={f.Feature} className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
                      <span className="w-44 truncate text-sm font-medium">{f.Feature}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${(f.Importance ?? 0) * 400}%` }} />
                      </div>
                      <span className="w-12 text-right text-xs font-mono text-muted-foreground">{((f.Importance ?? 0) * 1).toFixed(2)}</span>
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-muted-foreground">No feature importance available.</div>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Methodology review</h3>
              <ul className="mt-4 space-y-3 text-sm">
                {data?.methodologyReview && data.methodologyReview.length > 0 ? (
                  data.methodologyReview.map((m: any) => (
                    <li key={m.id} className="flex gap-2 items-start">
                      {renderStatusIcon(m.status)}
                      <div className="flex-1">{m.title} <div className="text-xs text-muted-foreground">{m.observed}</div></div>
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-muted-foreground">No methodology items returned.</li>
                )}
              </ul>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Model assumptions</h3>
              <div className="mt-3 divide-y divide-border">
                {data?.modelAssumptions && data.modelAssumptions.length > 0 ? (
                  data.modelAssumptions.map((a: any) => (
                    <div key={a.id} className="flex items-center justify-between gap-3 py-3 text-sm">
                      <span className="flex-1">{a.title}</span>
                      <span className="text-xs text-muted-foreground">{a.observed}</span>
                      {renderStatusIcon(a.status)}
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-muted-foreground">No model assumptions returned.</div>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <h3 className="text-sm font-semibold">Documentation checklist</h3>
              <ul className="mt-3 divide-y divide-border">
                {data?.documentationChecklist && data.documentationChecklist.length > 0 ? (
                  data.documentationChecklist.map((d: any) => (
                    <li key={d.id || d.title} className="flex items-center justify-between py-3 text-sm">
                      <span>{d.title ?? d.title}</span>
                      {renderStatusIcon(d.status)}
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-muted-foreground">No documentation items returned.</li>
                )}
              </ul>
            </div>
          </section>

          <section className="rounded-xl border border-primary/30 bg-primary-soft p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-foreground/70">Regulatory alignment</div>
            <p className="mt-2 text-sm">
              Verdict: <span className="font-semibold">{data?.regulatoryAlignment?.verdict ?? "—"}</span>. 
              Pass/Warn/Fail: {data?.regulatoryAlignment?.counts?.pass ?? 0}/{data?.regulatoryAlignment?.counts?.warn ?? 0}/{data?.regulatoryAlignment?.counts?.fail ?? 0}.
            </p>
            {data?.regulatoryAlignment?.high_severity_fails?.length > 0 && (
              <div className="mt-3 text-sm text-destructive">High severity fails: {data.regulatoryAlignment.high_severity_fails.length}</div>
            )}
          </section>
        </>
      )}

      <div className="text-right">
        <Link
          to="/validation/challenger"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90"
        >
          Continue to Stage 4
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
