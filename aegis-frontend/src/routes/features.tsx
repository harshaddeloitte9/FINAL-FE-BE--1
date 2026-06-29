import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Loader, ArrowLeft, ArrowRight } from "lucide-react";

export const Route = createFileRoute("/features")({
  head: () => ({ meta: [{ title: "Feature Engineering — Aegis Credit" }] }),
  component: Features,
});

interface FeatureEngineeringResponse {
  col_types?: Record<string, string>;
  target_col?: string;
  task_type?: string;
  feature_engineering_plan?: any;
  feature_engineering_summary?: any;
  x_engineered_shape?: number[];
  x_engineered_preview?: any[];
  gini_scores?: Record<string, number>;
  ead_configuration?: {
    mode?: string;
    source_col?: string;
    method?: string;
    available?: boolean;
    missing_columns?: string[];
    selected?: Record<string, any>;
    summary?: Record<string, number | null>;
  };
  available_numeric_columns?: string[];
}

function Features() {
  const navigate = useNavigate();
  const { file, profile } = useDataset();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [engineeringResult, setEngineeringResult] = useState<FeatureEngineeringResponse | null>(null);
  const [vifSortKey, setVifSortKey] = useState<"feature" | "value">("value");
  const [vifSortAsc, setVifSortAsc] = useState(false);
  const [eadMode, setEadMode] = useState<"outstanding_balance" | "estimate">("outstanding_balance");
  const [eadCol, setEadCol] = useState<string>("");
  const [loanCol, setLoanCol] = useState<string>("");
  const [interestCol, setInterestCol] = useState<string>("");
  const [yearsCol, setYearsCol] = useState<string>("");
  const [termCol, setTermCol] = useState<string>("");
  const [yearsMonths, setYearsMonths] = useState(false);
  const [termMonths, setTermMonths] = useState(false);

  useEffect(() => {
    if (!file || !profile) {
      setError("No dataset uploaded. Please upload a dataset first.");
      return;
    }

    const runFeatureEngineering = async () => {
      try {
        setLoading(true);
        setError(null);

        let target_col = "";
        if (profile.columns && Array.isArray(profile.columns) && profile.columns.includes("loan_status")) {
          target_col = "loan_status";
        } else if (profile.target_candidates && Array.isArray(profile.target_candidates) && profile.target_candidates.length > 0) {
          target_col = profile.target_candidates[0];
        }

        if (!target_col || target_col === "string") {
          throw new Error("Could not determine target column. Please check the uploaded dataset.");
        }

        const form = new FormData();
        form.append("file", file);
        form.append("target_col", target_col);
        form.append("ead_mode", eadMode);
        form.append("ead_col", eadCol || "");
        form.append("ead_loan_col", loanCol || "");
        form.append("ead_interest_col", interestCol || "");
        form.append("ead_years_col", yearsCol || "");
        form.append("ead_term_col", termCol || "");
        form.append("ead_years_months", yearsMonths ? "true" : "false");
        form.append("ead_term_months", termMonths ? "true" : "false");

        const result = await formUpload<FeatureEngineeringResponse>("/data/feature-engineering", form);
        setEngineeringResult(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to run feature engineering";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    runFeatureEngineering();
  }, [file, profile, eadMode, eadCol, loanCol, interestCol, yearsCol, termCol, yearsMonths, termMonths]);

  const plan = engineeringResult?.feature_engineering_plan ?? {};
  const summary = engineeringResult?.feature_engineering_summary ?? {};

  const addedFeatures = Array.isArray(summary.added) ? summary.added : [];
  const removedFeatures = Array.isArray(summary.removed) ? summary.removed : [];
  const transformedSteps = Array.isArray(summary.transformed) ? summary.transformed : [];
  const appliedSteps = Array.isArray(plan.applied_steps) ? plan.applied_steps : [];
  const miScores = plan.mi_scores && typeof plan.mi_scores === "object" ? plan.mi_scores : {};
  const ivScores = plan.iv_scores && typeof plan.iv_scores === "object" ? plan.iv_scores : {};
  const woeCols = Array.isArray(plan.woe_cols) ? plan.woe_cols : [];
  const woeMaps = plan.woe_maps && typeof plan.woe_maps === "object" ? plan.woe_maps : {};
  const highCorrPairs = Array.isArray(plan.multicollinearity?.high_corr_pairs) ? plan.multicollinearity.high_corr_pairs : [];
  const vifMap = plan.multicollinearity?.vif && typeof plan.multicollinearity.vif === "object" ? plan.multicollinearity.vif : {};
  const regulatoryAlerts = Array.isArray(summary.regulatory_alerts)
    ? summary.regulatory_alerts
    : Array.isArray(plan.regulatory_alerts)
    ? plan.regulatory_alerts
    : [];

  const [decisionLogCsvUrl, setDecisionLogCsvUrl] = useState<string | null>(null);

  const downloadDecisionLog = async () => {
    if (!file) return;
    try {
      setLoading(true);
      const form = new FormData();
      form.append("file", file);
      const target_col = profile.target_candidates && profile.target_candidates.length ? profile.target_candidates[0] : "";
      form.append("target_col", target_col);
      const res = await formUpload<any>("/data/feature-decision-log", form);
      if (res && res.content_base64) {
        const blob = new Blob([Uint8Array.from(atob(res.content_base64), c => c.charCodeAt(0))], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        setDecisionLogCsvUrl(url);
        const a = document.createElement('a');
        a.href = url;
        a.download = res.file_name || 'feature_decision_log.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    } catch (err) {
      console.error(err);
      setError('Failed to download decision log.');
    } finally {
      setLoading(false);
    }
  };

  const vifRows = useMemo(() => {
    return Object.entries(vifMap).map(([feature, value]) => ({ feature, value: Number(value) }));
  }, [vifMap]);

  const sortedVifRows = useMemo(() => {
    return [...vifRows].sort((a, b) => {
      if (vifSortKey === "feature") {
        return vifSortAsc ? a.feature.localeCompare(b.feature) : b.feature.localeCompare(a.feature);
      }
      return vifSortAsc ? a.value - b.value : b.value - a.value;
    });
  }, [vifRows, vifSortKey, vifSortAsc]);

  const miData = useMemo(() => {
    return Object.entries(miScores)
      .map(([feature, score]) => ({ feature, score: Number(score) }))
      .sort((a, b) => b.score - a.score);
  }, [miScores]);

  const ivData = useMemo(() => {
    return Object.entries(ivScores)
      .map(([feature, iv]) => ({ feature, iv: Number(iv) }))
      .sort((a, b) => b.iv - a.iv);
  }, [ivScores]);

  const woeInfo = useMemo(() => {
    return woeCols.map((col) => ({
      feature: col,
      buckets: woeMaps[col] ? Object.keys(woeMaps[col]).length : 0,
    }));
  }, [woeCols, woeMaps]);

  const numericColumns = useMemo(() => engineeringResult?.available_numeric_columns ?? [], [engineeringResult]);
  const giniRows = useMemo(
    () => Object.entries(engineeringResult?.gini_scores ?? {}).map(([feature, score]) => ({ feature, score: Number(score) })),
    [engineeringResult],
  );

  useEffect(() => {
    const selected = engineeringResult?.ead_configuration?.selected;
    if (!selected) {
      return;
    }
    if (selected.outstanding_balance_col) {
      setEadCol(selected.outstanding_balance_col);
    }
    if (selected.loan_amount) {
      setLoanCol(selected.loan_amount);
    }
    if (selected.interest_rate) {
      setInterestCol(selected.interest_rate);
    }
    if (selected.years_elapsed) {
      setYearsCol(selected.years_elapsed);
    }
    if (selected.term) {
      setTermCol(selected.term);
    }
    if (typeof selected.years_elapsed_is_months === "boolean") {
      setYearsMonths(selected.years_elapsed_is_months);
    }
    if (typeof selected.term_is_months === "boolean") {
      setTermMonths(selected.term_is_months);
    }
    if (selected.outstanding_balance_col) {
      setEadMode("outstanding_balance");
    } else if (selected.loan_amount || selected.interest_rate || selected.years_elapsed || selected.term) {
      setEadMode("estimate");
    }
  }, [engineeringResult]);

  const canProceed = !!engineeringResult && !loading && !error;

  if (!file || !profile) {
    return (
      <div className="space-y-8">
        <PageHeader title="Feature Engineering" description="Engineered features, multicollinearity diagnostics, and importance preview." />
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600" />
            <div>
              <div className="font-semibold text-amber-900">No Dataset</div>
              <div className="text-sm text-amber-800">Upload a dataset on the Data Upload page to see feature engineering results.</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-8">
        <PageHeader title="Feature Engineering" description="Engineered features, multicollinearity diagnostics, and importance preview." />
        <div className="rounded-xl border border-red-200 bg-red-50 p-6">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <div>
              <div className="font-semibold text-red-900">Error</div>
              <div className="text-sm text-red-800">{error}</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:border-primary hover:bg-primary-soft"
              onClick={() => navigate("/preprocessing")}
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Preprocessing
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <PageHeader title="Feature Engineering" description="Engineered features, multicollinearity diagnostics, and importance preview." />
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <Loader className="h-8 w-8 animate-spin text-primary" />
          <div className="text-sm text-muted-foreground">Running feature engineering...</div>
        </div>
      </div>
    );
  }

  if (!engineeringResult) {
    return (
      <div className="space-y-8">
        <PageHeader title="Feature Engineering" description="Engineered features, multicollinearity diagnostics, and importance preview." />
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="text-center text-sm text-muted-foreground">Feature engineering did not return a result.</div>
        </div>
      </div>
    );
  }

  const originalFeatures = Array.isArray(summary.original_shape) ? summary.original_shape[1] ?? null : null;
  const finalFeatures = Array.isArray(summary.final_shape) ? summary.final_shape[1] ?? null : null;

  return (
    <div className="space-y-8">
      <PageHeader title="Feature Engineering" description="Engineered features, multicollinearity diagnostics, and importance preview." />

      <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {originalFeatures !== null && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Original features</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{originalFeatures}</div>
          </div>
        )}
        {finalFeatures !== null && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Final features</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{finalFeatures}</div>
          </div>
        )}
        {addedFeatures.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Features added</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{addedFeatures.length}</div>
          </div>
        )}
        {removedFeatures.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Features removed</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{removedFeatures.length}</div>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Feature Engineering Plan</h2>
            <p className="text-xs text-muted-foreground">The same transformations learned on the training split and applied to validation/test.</p>
          </div>
        </div>
        <div className="mt-4 space-y-3 text-sm">
          {appliedSteps.length > 0 ? (
            appliedSteps.map((step: any, idx: number) => (
              <div key={idx} className="rounded-xl border border-border bg-background p-3">
                <div className="font-medium text-xs text-foreground">{step.step || `Step ${idx + 1}`}</div>
                <div className="mt-1 text-[11px] text-muted-foreground">{step.reason || ""}</div>
                {Array.isArray(step.columns) && step.columns.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {step.columns.map((col: string, cidx: number) => (
                      <span key={cidx} className="inline-block rounded border border-border bg-primary/10 px-2 py-0.5 font-mono text-[10px]">
                        {col}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="rounded-xl border border-border bg-background p-3 text-muted-foreground">
              No significant feature engineering opportunities were detected for this dataset.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Exposure at Default (EAD) source for ECL</h2>
            <p className="text-xs text-muted-foreground">This mirrors the original Streamlit step and is used for downstream ECL calculations.</p>
          </div>
        </div>
        <div className="mt-4 space-y-4 text-sm">
          <div className="rounded-xl border border-border bg-background p-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Does your dataset contain an outstanding balance column?</label>
            <div className="mt-2 space-y-2">
              <label className="flex items-center gap-2 rounded border border-border px-3 py-2">
                <input
                  type="radio"
                  checked={eadMode === "outstanding_balance"}
                  onChange={() => setEadMode("outstanding_balance")}
                />
                <span>Yes — select it</span>
              </label>
              <label className="flex items-center gap-2 rounded border border-border px-3 py-2">
                <input
                  type="radio"
                  checked={eadMode === "estimate"}
                  onChange={() => setEadMode("estimate")}
                />
                <span>No — estimate it from loan amount, interest, elapsed time, term</span>
              </label>
            </div>
          </div>

          {eadMode === "outstanding_balance" ? (
            <div className="grid gap-3 md:grid-cols-1">
              <label className="space-y-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Outstanding balance column</span>
                <select
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  value={eadCol}
                  onChange={(event) => setEadCol(event.target.value)}
                >
                  <option value="">Select a numeric column</option>
                  {numericColumns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Loan amount</span>
                <select className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" value={loanCol} onChange={(event) => setLoanCol(event.target.value)}>
                  <option value="">Select a column</option>
                  {numericColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                </select>
              </label>
              <label className="space-y-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Interest rate</span>
                <select className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" value={interestCol} onChange={(event) => setInterestCol(event.target.value)}>
                  <option value="">Select a column</option>
                  {numericColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                </select>
              </label>
              <label className="space-y-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Elapsed time</span>
                <select className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" value={yearsCol} onChange={(event) => setYearsCol(event.target.value)}>
                  <option value="">Select a column</option>
                  {numericColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                </select>
              </label>
              <label className="space-y-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total loan term</span>
                <select className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" value={termCol} onChange={(event) => setTermCol(event.target.value)}>
                  <option value="">Select a column</option>
                  {numericColumns.map((col) => <option key={col} value={col}>{col}</option>)}
                </select>
              </label>
            </div>
          )}

          <div className="flex flex-wrap gap-3 text-sm">
            <label className="flex items-center gap-2 rounded border border-border px-3 py-2">
              <input type="checkbox" checked={yearsMonths} onChange={(event) => setYearsMonths(event.target.checked)} />
              <span>Elapsed time is in months</span>
            </label>
            <label className="flex items-center gap-2 rounded border border-border px-3 py-2">
              <input type="checkbox" checked={termMonths} onChange={(event) => setTermMonths(event.target.checked)} />
              <span>Loan term is in months</span>
            </label>
          </div>

          {engineeringResult?.ead_configuration && (
            <div className="rounded-xl border border-border bg-background p-3 text-sm">
              <div className="font-medium text-xs">{engineeringResult.ead_configuration.method || "EAD configuration"}</div>
              {engineeringResult.ead_configuration.available === false && engineeringResult.ead_configuration.missing_columns?.length ? (
                <div className="mt-2 text-[11px] text-red-600">
                  Missing required columns: {engineeringResult.ead_configuration.missing_columns.join(", ")}
                </div>
              ) : engineeringResult.ead_configuration.summary && Object.keys(engineeringResult.ead_configuration.summary).length > 0 ? (
                <div className="mt-2 text-[11px] text-muted-foreground">
                  Mean {engineeringResult.ead_configuration.summary.mean ?? "n/a"}, median {engineeringResult.ead_configuration.summary.median ?? "n/a"}
                </div>
              ) : (
                <div className="mt-2 text-[11px] text-muted-foreground">Configuration ready for ECL downstream processing.</div>
              )}
            </div>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {(appliedSteps.length > 0 || transformedSteps.length > 0) && (
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant xl:col-span-2">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-base font-semibold">Transformations applied</h2>
            </div>
            <div className="mt-4 space-y-3 text-sm">
              {appliedSteps.length > 0 ? (
                appliedSteps.map((step: any, idx: number) => (
                  <div key={idx} className="rounded-xl border border-border bg-background p-3">
                    <div className="font-medium text-xs text-foreground">{step.step || `Step ${idx + 1}`}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">{step.reason || ""}</div>
                    {Array.isArray(step.columns) && step.columns.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {step.columns.map((col: string, cidx: number) => (
                          <span key={cidx} className="inline-block rounded border border-border bg-primary/10 px-2 py-0.5 font-mono text-[10px]">
                            {col}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                transformedSteps.map((item: string, idx: number) => (
                  <div key={idx} className="rounded-xl border border-border bg-background p-3 text-muted-foreground">
                    {item}
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        {addedFeatures.length > 0 && (
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <h2 className="text-base font-semibold">Features added</h2>
            <div className="mt-4 space-y-2 text-sm text-muted-foreground">
              {addedFeatures.map((feature: string, idx: number) => (
                <div key={idx} className="rounded-xl border border-border bg-background px-3 py-2 font-mono text-xs">
                  {feature}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      {removedFeatures.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">Features removed</h2>
          <div className="mt-4 space-y-3 text-sm text-muted-foreground">
            {removedFeatures.map((feature: string, idx: number) => {
              const reasons = appliedSteps
                .filter((step: any) => Array.isArray(step.columns) && step.columns.includes(feature))
                .map((step: any) => step.reason)
                .filter(Boolean);
              return (
                <div key={idx} className="rounded-xl border border-border bg-background p-3">
                  <div className="font-medium text-xs">{feature}</div>
                  {reasons.length > 0 && <div className="mt-1 text-[11px] text-muted-foreground">{reasons.join(" / ")}</div>}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {giniRows.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Univariate Gini coefficients</h2>
              <p className="text-xs text-muted-foreground">Computed on the training split only.</p>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="border-b border-border px-3 py-2">Feature</th>
                  <th className="border-b border-border px-3 py-2">Gini</th>
                </tr>
              </thead>
              <tbody>
                {giniRows.map((row) => (
                  <tr key={row.feature} className="odd:bg-background">
                    <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.feature}</td>
                    <td className="border-b border-border px-3 py-2 text-xs">{row.score.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {miData.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Mutual information</h2>
              <p className="text-xs text-muted-foreground">All numeric features ranked by mutual information with target ({miData.length} features).</p>
            </div>
          </div>
          <div className="mt-4 overflow-y-auto" style={{ maxHeight: "600px" }}>
            {miData.length > 0 && (
              <div style={{ height: Math.max(400, miData.length * 25) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={miData} layout="vertical" margin={{ left: 150 }}>
                    <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tickLine={false} axisLine={false} fontSize={10} />
                    <YAxis type="category" dataKey="feature" tickLine={false} axisLine={false} fontSize={9} width={145} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid oklch(0.92 0.005 240)" }} />
                    <Bar dataKey="score" fill="oklch(0.76 0.18 130)" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>
      )}

      {highCorrPairs.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">Highly correlated pairs</h2>
          <div className="mt-4 space-y-3 text-sm text-muted-foreground">
            {highCorrPairs.map((pair: any, idx: number) => (
              <div key={idx} className="rounded-xl border border-border bg-background p-3">
                <div className="font-medium text-xs">{pair.feature_1} ↔ {pair.feature_2}</div>
                <div className="mt-1 text-[11px]">Correlation: {Number(pair.correlation).toFixed(4)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {vifRows.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">VIF table</h2>
              <p className="text-xs text-muted-foreground">Variance inflation factor estimates for numeric features.</p>
            </div>
            <div className="flex gap-2 text-xs">
              <button
                type="button"
                className="rounded-full border border-border bg-background px-2 py-1 text-muted-foreground hover:border-primary hover:text-foreground"
                onClick={() => {
                  setVifSortKey("feature");
                  setVifSortAsc((prev) => (vifSortKey === "feature" ? !prev : true));
                }}
              >
                Sort by feature
              </button>
              <button
                type="button"
                className="rounded-full border border-border bg-background px-2 py-1 text-muted-foreground hover:border-primary hover:text-foreground"
                onClick={() => {
                  setVifSortKey("value");
                  setVifSortAsc((prev) => (vifSortKey === "value" ? !prev : true));
                }}
              >
                Sort by VIF
              </button>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="border-b border-border px-3 py-2">Feature</th>
                  <th className="border-b border-border px-3 py-2">VIF</th>
                </tr>
              </thead>
              <tbody>
                {sortedVifRows.map((row) => (
                  <tr key={row.feature} className="odd:bg-background">
                    <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.feature}</td>
                    <td className="border-b border-border px-3 py-2 text-xs">{row.value.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {ivData.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Information value</h2>
              <p className="text-xs text-muted-foreground">All computed IV features and WOE transformation candidates ({ivData.length} features).</p>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="border-b border-border px-3 py-2">Feature</th>
                  <th className="border-b border-border px-3 py-2">IV</th>
                  <th className="border-b border-border px-3 py-2">WOE Applied</th>
                </tr>
              </thead>
              <tbody>
                {ivData.map((row) => (
                  <tr key={row.feature} className="odd:bg-background">
                    <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.feature}</td>
                    <td className="border-b border-border px-3 py-2 text-xs">{row.iv.toFixed(5)}</td>
                    <td className="border-b border-border px-3 py-2 text-xs">{woeCols.includes(row.feature) ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {woeInfo.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold">WOE Transformation Details</h3>
              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {woeInfo.map((info) => (
                  <div key={info.feature} className="rounded-xl border border-border bg-background p-3 text-sm">
                    <div className="font-medium text-xs">{info.feature}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">WOE buckets: {info.buckets}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {regulatoryAlerts.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">Regulatory insights</h2>
          <div className="mt-4 space-y-3">
            {regulatoryAlerts.map((alert: any, idx: number) => (
              <div key={idx} className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <div className="text-sm font-semibold">{alert.rule_id || alert.id || alert.code || alert.rule || `Alert ${idx + 1}`}</div>
                <div className="mt-1 text-sm text-muted-foreground">{alert.flag || alert.message || alert.detail || alert.description || JSON.stringify(alert)}</div>
                {alert.observed_value && (
                  <div className="mt-2 text-xs font-mono text-muted-foreground">Observed: {Array.isArray(alert.observed_value) ? alert.observed_value.join(", ") : String(alert.observed_value)}</div>
                )}
                {alert.suggestion && (
                  <div className="mt-2 text-[11px] text-muted-foreground">Recommendation: {alert.suggestion}</div>
                )}
                {alert.source && (
                  <div className="mt-1 text-[11px] text-muted-foreground">Reference: {alert.source} — {alert.principle || alert.section || ''}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {engineeringResult.x_engineered_preview && Array.isArray(engineeringResult.x_engineered_preview) && engineeringResult.x_engineered_preview.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Engineered feature matrix preview</h2>
              <p className="text-xs text-muted-foreground">A sample of the transformed dataset after feature engineering.</p>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr>
                  {Object.keys(engineeringResult.x_engineered_preview[0]).map((key: string) => (
                    <th key={key} className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {engineeringResult.x_engineered_preview.map((row: any, rowIndex: number) => (
                  <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : ""}>
                    {Object.values(row).map((cell: any, cellIndex: number) => (
                      <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs">{String(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition hover:border-primary hover:bg-primary-soft"
          onClick={() => navigate("/preprocessing")}
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Preprocessing
        </button>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => navigate("/models")}
          disabled={!canProceed}
        >
          Proceed to Model Selection
          <ArrowRight className="h-4 w-4" />
        </button>
      </section>
    </div>
  );
}
