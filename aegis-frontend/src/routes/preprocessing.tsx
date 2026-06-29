import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { CheckCircle2, ArrowLeft, ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/preprocessing")({
  head: () => ({ meta: [{ title: "Preprocessing — Aegis Credit" }] }),
  component: Preprocessing,
});

function Preprocessing() {
  const { profile, file } = useDataset();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preprocess, setPreprocess] = useState<any>(null);

  useEffect(() => {
    const runPreprocess = async () => {
      if (!profile) return;

      // Select target column: prefer 'loan_status', fallback to first target_candidate
      const allColumns = profile.columns ?? [];
      let targetCol: string | null = null;

      if (allColumns.includes("loan_status")) {
        targetCol = "loan_status";
      } else if (profile.target_candidates && profile.target_candidates.length > 0) {
        targetCol = profile.target_candidates[0];
      }

      // Validate target column is not a placeholder string like "string"
      if (!targetCol || targetCol === "string" || targetCol.trim() === "") {
        setError("No valid target column found. Please upload a dataset with a recognized target variable.");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const form = new FormData();
        if (file) {
          form.append("file", file);
        }
        form.append("target_col", targetCol);

        console.log("Preprocessing: POST /data/preprocess", { targetCol, file: !!file });
        const response = await formUpload("/data/preprocess", form);
        console.log("Preprocessing: response", response);
        setPreprocess(response);
      } catch (err: any) {
        console.error("Preprocessing: failed", err);
        setError(err?.body?.detail ?? err?.message ?? "Preprocessing failed.");
        setPreprocess(null);
      } finally {
        setLoading(false);
      }
    };

    runPreprocess();
  }, [profile, file]);

  if (!profile) {
    return (
      <div className="space-y-8">
        <PageHeader title="Preprocessing" description="Reproducible transformations applied to the training dataset." />
        <div className="rounded-xl border border-border bg-card p-6 text-center">
          <h3 className="text-lg font-semibold">No dataset available</h3>
          <p className="mt-2 text-sm text-muted-foreground">Upload a dataset on the Data Upload page before preprocessing can run.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Preprocessing" description="Reproducible transformations applied to the training dataset." />

      {loading && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Running preprocessing via backend...
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-destructive">
          {error}
        </div>
      )}

      {preprocess && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft">
                <CheckCircle2 className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="text-sm font-semibold">Preprocessing steps</div>
                <div className="mt-2 text-xs text-muted-foreground">Transformations applied to the dataset.</div>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {preprocess.preprocessing_report && Array.isArray(preprocess.preprocessing_report.decisions) ? (
                preprocess.preprocessing_report.decisions.map((item: any, index: number) => (
                  <div key={index} className="rounded-lg border border-border bg-background p-3">
                    <div className="font-medium text-sm">{item.column} ({item.type})</div>
                    {Array.isArray(item.actions) && item.actions.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {item.actions.map((action: string, actionIndex: number) => (
                          <li key={actionIndex} className="text-xs text-muted-foreground">• {action}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground">No preprocessing steps recorded.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-sm font-semibold">Transformed dataset</div>
            <div className="mt-4 grid gap-3 text-sm text-muted-foreground">
              <div className="rounded-xl border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-wider">Features</div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{Array.isArray(preprocess.feature_names) ? preprocess.feature_names.length : "—"}</div>
              </div>
              <div className="rounded-xl border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-wider">X shape</div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{Array.isArray(preprocess.x_shape) ? preprocess.x_shape.join(" × ") : "—"}</div>
              </div>
              <div className="rounded-xl border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-wider">Y shape</div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{Array.isArray(preprocess.y_shape) ? preprocess.y_shape.join(" × ") : "—"}</div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant md:col-span-2">
            <div className="text-sm font-semibold">Feature preview</div>
            <div className="mt-4 overflow-x-auto">
              {Array.isArray(preprocess.x_preview) && preprocess.x_preview.length > 0 ? (
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      {Object.keys(preprocess.x_preview[0]).map((key: string) => (
                        <th key={key} className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preprocess.x_preview.map((row: any, rowIndex: number) => (
                      <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : ""}>
                        {Object.values(row).map((cell: any, cellIndex: number) => (
                          <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs">{String(cell)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-6 text-center text-sm text-muted-foreground">No feature preview available.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant md:col-span-2">
            <div className="text-sm font-semibold">Target preview</div>
            <div className="mt-4">
              {Array.isArray(preprocess.y_preview) && preprocess.y_preview.length > 0 ? (
                <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
                  {preprocess.y_preview.map((value: any, index: number) => (
                    <div key={index} className="rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs text-center">{String(value)}</div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">No target preview available.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {preprocess && (
        <div className="flex gap-3 pt-4">
          <Button variant="outline" onClick={() => navigate({ to: "/profiling" })} className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Profiling
          </Button>
          <Button onClick={() => navigate({ to: "/features" })} className="gap-2 ml-auto">
            Proceed to Feature Engineering
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
