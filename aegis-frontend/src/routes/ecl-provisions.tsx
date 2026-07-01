import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { AlertCircle, ArrowLeft, ArrowRight, Calculator, Download, Loader2, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { AreaChart, Area, BarChart, Bar, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";

export const Route = createFileRoute("/ecl-provisions")({
  head: () => ({ meta: [{ title: "ECL & Provisions — Aegis Credit" }] }),
  component: EclProvisions,
});

type LgdMethod = "fixed" | "loan-type" | "ltv";

type EclBackendResponse = {
  summary?: Record<string, any>;
  sample_rows?: Record<string, any>[];
  columns?: string[];
};

function EclProvisions() {
  const navigate = useNavigate();
  const { file, profile, trainingResult } = useDataset();

  const availableColumns = useMemo(() => (profile?.columns ?? []) as string[], [profile]);
  const targetColumn = useMemo(() => {
    if (profile?.target_col) return profile.target_col;
    if (Array.isArray(profile?.target_candidates) && profile.target_candidates.length > 0) {
      return profile.target_candidates[0];
    }
    return availableColumns.find((column) => ["loan_status", "default", "target", "label"].includes(column)) ?? "loan_status";
  }, [availableColumns, profile]);

  const [eadColumn, setEadColumn] = useState("");
  const [lgdMethod, setLgdMethod] = useState<LgdMethod>("fixed");
  const [lgdValue, setLgdValue] = useState(0.45);
  const [loanTypeColumn, setLoanTypeColumn] = useState("");
  const [ltvColumn, setLtvColumn] = useState("");
  const [dpdColumn, setDpdColumn] = useState("");
  const [originationPdColumn, setOriginationPdColumn] = useState("");
  const [remainingMaturityColumn, setRemainingMaturityColumn] = useState("");
  const [relativePdMultiplier, setRelativePdMultiplier] = useState(1.5);
  const [absolutePdIncrease, setAbsolutePdIncrease] = useState(0.03);
  const [dpdBackstop, setDpdBackstop] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [sampleRows, setSampleRows] = useState<Record<string, any>[]>([]);
  const [columns, setColumns] = useState<string[]>([]);

  const stageExposureData = useMemo(() => {
    const stageCounts = summary?.ead_by_stage ?? {};
    return [
      { stage: "Stage 1", value: Number(stageCounts.stage_1 ?? 0) },
      { stage: "Stage 2", value: Number(stageCounts.stage_2 ?? 0) },
      { stage: "Stage 3", value: Number(stageCounts.stage_3 ?? 0) },
    ];
  }, [summary]);

  const eclDistributionData = useMemo(() => {
    const stageEcl = summary?.ecl_by_stage ?? {};
    return [
      { stage: "Stage 1", value: Number(stageEcl.stage_1 ?? 0) },
      { stage: "Stage 2", value: Number(stageEcl.stage_2 ?? 0) },
      { stage: "Stage 3", value: Number(stageEcl.stage_3 ?? 0) },
    ];
  }, [summary]);

  const calculateEcl = async () => {
    if (!file) {
      setError("Upload a dataset before running the ECL workflow.");
      return;
    }
    if (!trainingResult?.model_artifact) {
      setError("Train a model before calculating ECL. The backend needs the trained model artifact.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("model_artifact", trainingResult.model_artifact);
      form.append("file", file);
      form.append("target_col", targetColumn);
      if (eadColumn) form.append("ead_col", eadColumn);
      if (lgdMethod === "loan-type" && loanTypeColumn) form.append("loan_type_col", loanTypeColumn);

      const cfg = {
        lgd_method: lgdMethod === "ltv" ? "ltv" : "fixed",
        lgd_fixed: lgdMethod === "fixed" ? lgdValue : 0.45,
        ltv_col: lgdMethod === "ltv" ? ltvColumn || undefined : undefined,
        pd_relative_threshold: relativePdMultiplier,
        pd_absolute_threshold: absolutePdIncrease,
        dpd_sicr_threshold: dpdBackstop,
        dpd_col: dpdColumn || undefined,
        orig_pd_col: originationPdColumn || undefined,
        maturity_col: remainingMaturityColumn || undefined,
      };
      form.append("cfg", JSON.stringify(cfg));

      if (lgdMethod === "loan-type" && loanTypeColumn) {
        const inferLgdMap = () => {
          const previewValues = Array.isArray(profile?.data_preview)
            ? profile.data_preview.map((row) => row?.[loanTypeColumn]).filter((value) => value !== undefined && value !== null && value !== "")
            : [];
          const uniqueValues = Array.from(new Set(previewValues.map((value) => String(value)))).slice(0, 8);
          return Object.fromEntries(uniqueValues.map((value, index) => [value, Number((0.25 + index * 0.05).toFixed(2))]));
        };
        form.append("lgd_map", JSON.stringify(inferLgdMap()));
      }

      const response = await formUpload<EclBackendResponse>("/ecl/compute", form);
      setSummary(response.summary ?? null);
      setSampleRows(response.sample_rows ?? []);
      setColumns(response.columns ?? []);
    } catch (err: any) {
      console.error("ECL calculation failed", err);
      setError(err?.body?.detail ?? err?.message ?? "Unable to calculate ECL from the backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!sampleRows.length) return;

    const exportColumns = columns.length ? columns : Object.keys(sampleRows[0] ?? {});
    const csvRows = [exportColumns.join(",")];
    for (const row of sampleRows) {
      csvRows.push(
        exportColumns
          .map((column) => {
            const value = row?.[column];
            const normalized = value === null || value === undefined ? "" : String(value).replace(/\n/g, " ");
            return `"${normalized.replace(/"/g, '""')}"`;
          })
          .join(","),
      );
    }

    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ecl_results.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="ECL & Provisions"
        description="Step 9 — IFRS 9 ECL estimation with SICR staging and portfolio-level provision output."
      />

      <div className="rounded-xl border border-primary/30 bg-primary-soft p-4 text-sm text-foreground/90">
        <div className="flex items-center gap-2 font-semibold">
          <Calculator className="h-4 w-4" />
          Backend-driven IFRS 9 workflow for staging, ECL, and provision visibility.
        </div>
        <p className="mt-2 text-sm text-foreground/80">
          The controls below mirror the Streamlit workflow and now call the existing FastAPI ECL endpoint with the uploaded dataset and trained model artifact.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4" />
            <div>{error}</div>
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-6">
          <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">Step 9 — ECL Calculation (IFRS 9)</h2>
                <p className="text-xs text-muted-foreground">SICR assessment → Stage 1/2/3 classification → ECL = PD × LGD × EAD</p>
              </div>
              <span className="rounded-full bg-primary-soft px-2.5 py-1 text-[11px] font-medium text-foreground">Live backend</span>
            </div>

            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-semibold">Exposure & Loss Inputs</h3>
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className="font-medium">Exposure / balance column</span>
                    <select
                      value={eadColumn}
                      onChange={(event) => setEadColumn(event.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">Auto-detect</option>
                      {availableColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="space-y-2 text-sm">
                    <span className="font-medium">LGD Method</span>
                    <div className="grid grid-cols-1 gap-2 rounded-lg border border-border bg-background p-2">
                      {[
                        { value: "fixed", label: "Fixed Assumption" },
                        { value: "loan-type", label: "By Loan Type" },
                        { value: "ltv", label: "From LTV Column" },
                      ].map((option) => (
                        <label key={option.value} className="flex items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-muted/40">
                          <input
                            type="radio"
                            name="lgd-method"
                            value={option.value}
                            checked={lgdMethod === option.value}
                            onChange={() => setLgdMethod(option.value as LgdMethod)}
                          />
                          <span>{option.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-4 rounded-lg border border-border bg-background p-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">LGD assumption</label>
                    <span className="text-sm font-semibold">{(lgdValue * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.05"
                    max="0.95"
                    step="0.05"
                    value={lgdValue}
                    onChange={(event) => setLgdValue(Number(event.target.value))}
                    className="mt-3 w-full"
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    {lgdMethod === "fixed"
                      ? "Applies the same loss-given-default assumption to every loan."
                      : lgdMethod === "loan-type"
                        ? "The backend receives a loan-type LGD map derived from the selected column."
                        : "LGD is inferred from the selected LTV column using the backend configuration."}
                  </p>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold">IFRS 9 SICR & Staging</h3>
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className="font-medium">DPD column</span>
                    <select
                      value={dpdColumn}
                      onChange={(event) => setDpdColumn(event.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">Auto-detect</option>
                      {availableColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="font-medium">Origination PD column</span>
                    <select
                      value={originationPdColumn}
                      onChange={(event) => setOriginationPdColumn(event.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">Auto-detect</option>
                      {availableColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="font-medium">Remaining maturity column</span>
                    <select
                      value={remainingMaturityColumn}
                      onChange={(event) => setRemainingMaturityColumn(event.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">Auto-detect</option>
                      {availableColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="font-medium">Loan type / segmentation column</span>
                    <select
                      value={loanTypeColumn}
                      onChange={(event) => setLoanTypeColumn(event.target.value)}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="">Auto-detect</option>
                      {availableColumns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">SICR relative PD multiplier</label>
                      <span className="text-sm font-semibold">{relativePdMultiplier.toFixed(1)}x</span>
                    </div>
                    <input
                      type="range"
                      min="1.1"
                      max="5"
                      step="0.1"
                      value={relativePdMultiplier}
                      onChange={(event) => setRelativePdMultiplier(Number(event.target.value))}
                      className="mt-3 w-full"
                    />
                  </div>
                  <div className="rounded-lg border border-border bg-background p-4">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">SICR absolute PD increase</label>
                      <span className="text-sm font-semibold">{absolutePdIncrease.toFixed(2)} pp</span>
                    </div>
                    <input
                      type="range"
                      min="0.01"
                      max="0.2"
                      step="0.01"
                      value={absolutePdIncrease}
                      onChange={(event) => setAbsolutePdIncrease(Number(event.target.value))}
                      className="mt-3 w-full"
                    />
                  </div>
                  <div className="rounded-lg border border-border bg-background p-4 md:col-span-2">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">DPD backstop threshold</label>
                      <span className="text-sm font-semibold">{dpdBackstop} days</span>
                    </div>
                    <input
                      type="range"
                      min="15"
                      max="60"
                      step="5"
                      value={dpdBackstop}
                      onChange={(event) => setDpdBackstop(Number(event.target.value))}
                      className="mt-3 w-full"
                    />
                  </div>
                </div>
              </div>
            </div>

            <Button className="mt-6 gap-2" onClick={calculateEcl} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
              {loading ? "Calculating…" : "Calculate ECL"}
            </Button>
          </section>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <h2 className="text-base font-semibold">Results</h2>
          <p className="mt-1 text-xs text-muted-foreground">Portfolio metrics and stage-based charts returned by the backend.</p>

          {summary ? (
            <>
              <div className="mt-5 grid grid-cols-1 gap-3">
                <div className="rounded-lg border border-border bg-background p-4">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Total ECL</div>
                  <div className="mt-1 text-2xl font-semibold">{Number(summary.total_ecl ?? 0).toLocaleString()}</div>
                </div>
                <div className="rounded-lg border border-border bg-background p-4">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Provision summary</div>
                  <div className="mt-2 text-sm text-foreground/90">
                    Coverage {Number(summary.coverage_pct ?? 0).toFixed(2)}% · {Number(summary.sicr_count ?? 0).toLocaleString()} SICR loans
                  </div>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-3">
                <div className="rounded-lg border border-border bg-background p-4">
                  <div className="text-sm font-semibold">Stage exposures</div>
                  <div className="mt-3 h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={stageExposureData}>
                        <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                        <XAxis dataKey="stage" tickLine={false} axisLine={false} fontSize={11} />
                        <YAxis tickLine={false} axisLine={false} fontSize={11} />
                        <Tooltip formatter={(value: number) => [`${value.toLocaleString()}`, "EAD"]} />
                        <Bar dataKey="value" fill="oklch(0.76 0.18 130)" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-background p-4">
                  <div className="text-sm font-semibold">ECL distribution</div>
                  <div className="mt-3 h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={eclDistributionData}>
                        <CartesianGrid stroke="oklch(0.92 0.005 240)" strokeDasharray="3 3" />
                        <XAxis dataKey="stage" tickLine={false} axisLine={false} fontSize={11} />
                        <YAxis tickLine={false} axisLine={false} fontSize={11} />
                        <Tooltip formatter={(value: number) => [`${value.toLocaleString()}`, "ECL"]} />
                        <Area type="monotone" dataKey="value" stroke="oklch(0.6 0.22 27)" fill="oklch(0.6 0.22 27)" fillOpacity={0.24} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="mt-6 rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
              Run the calculation to populate the live ECL portfolio output.
            </div>
          )}

          {summary ? (
            <div className="mt-6 grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Total EAD</div>
                <div className="mt-1 text-lg font-semibold">{Number(summary.total_ead ?? 0).toLocaleString()}</div>
              </div>
              <div className="rounded-lg border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Avg. PD</div>
                <div className="mt-1 text-lg font-semibold">{Number(summary.avg_pd_12m ?? 0).toFixed(3)}</div>
              </div>
              <div className="rounded-lg border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Stage 2 / 3</div>
                <div className="mt-1 text-lg font-semibold">{Number(summary.sicr_count ?? 0).toLocaleString()}</div>
              </div>
              <div className="rounded-lg border border-border bg-background p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Loans</div>
                <div className="mt-1 text-lg font-semibold">{Number(summary.loans ?? 0).toLocaleString()}</div>
              </div>
            </div>
          ) : null}

          {sampleRows.length > 0 ? (
            <div className="mt-6 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Top loans from backend</h3>
                <Button variant="outline" className="gap-2" onClick={handleDownload}>
                  <Download className="h-4 w-4" />
                  Download CSV
                </Button>
              </div>
              <div className="max-h-72 overflow-auto rounded-lg border border-border bg-background">
                <table className="min-w-full text-left text-xs">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr>
                      {(columns.length ? columns : Object.keys(sampleRows[0] ?? {})).slice(0, 8).map((column) => (
                        <th key={column} className="px-2 py-2 font-medium">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sampleRows.slice(0, 8).map((row, index) => (
                      <tr key={`${row?.id ?? index}`} className="border-b border-border/60 last:border-b-0">
                        {(columns.length ? columns : Object.keys(sampleRows[0] ?? {})).slice(0, 8).map((column) => (
                          <td key={`${column}-${index}`} className="whitespace-nowrap px-2 py-2 text-foreground/90">
                            {row?.[column] === null || row?.[column] === undefined ? "—" : String(row[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          <div className="mt-6 flex gap-3">
            <Button variant="outline" onClick={() => navigate({ to: "/explainability" })} className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back to Explainability
            </Button>
            <Button onClick={() => navigate({ to: "/" })} className="ml-auto gap-2">
              Exit to Workspace
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
