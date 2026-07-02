import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { ArrowLeft, ArrowRight, Download, Minus, Plus, Target, BarChart as BarChartIcon, Table as TableIcon, Brain, Settings, Trash2, Hash, Tag, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { ChartContainer as ResponsiveContainer } from "@/components/chart-container";
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
  const [expandedDecisions, setExpandedDecisions] = useState<Record<number, boolean>>({});
  const [testSize, setTestSize] = useState(0.15);
  const [valSize, setValSize] = useState(0.15);
  const [randomSeed, setRandomSeed] = useState(42);

  useEffect(() => {
    const runPreprocess = async () => {
      if (!profile) return;

      const allColumns = Array.isArray(profile.columns) ? profile.columns : [];
      let targetCol: string | null = null;

      if (allColumns.includes("loan_status")) {
        targetCol = "loan_status";
      } else if (Array.isArray(profile.target_candidates) && profile.target_candidates.length > 0) {
        targetCol = profile.target_candidates[0];
      } else if (typeof profile.target_col === "string" && profile.target_col.trim() !== "") {
        targetCol = profile.target_col;
      }

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
        form.append("test_size", String(testSize));
        form.append("val_size", String(valSize));
        form.append("random_seed", String(randomSeed));

        const result = await formUpload("/data/preprocess", form);
        setPreprocess(result);
      } catch (err: any) {
        setError(err?.body?.detail ?? err?.message ?? "Preprocessing failed.");
        setPreprocess(null);
      } finally {
        setLoading(false);
      }
    };

    runPreprocess();
  }, [profile, file, testSize, valSize, randomSeed]);

  useEffect(() => {
    if (!preprocess?.split_config) return;
    setTestSize(preprocess.split_config.test_size ?? 0.15);
    setValSize(preprocess.split_config.val_size ?? 0.15);
    setRandomSeed(preprocess.split_config.random_seed ?? 42);
  }, [preprocess?.split_config]);

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

  const summary = {
    feature_count: preprocess?.feature_count ?? preprocess?.summary_metrics?.features_basic,
    duplicates_removed:
      preprocess?.duplicates_removed ?? preprocess?.summary_metrics?.duplicates_removed ?? 0,
    numeric_feature_count:
      preprocess?.numeric_feature_count ?? preprocess?.summary_metrics?.numeric_columns,
    categorical_feature_count:
      preprocess?.categorical_feature_count ?? preprocess?.summary_metrics?.categorical_columns,
  };

  const decisions = Array.isArray(preprocess?.preprocessing_report?.decisions)
    ? preprocess.preprocessing_report.decisions
    : [];

  const strategySummary = Array.isArray(preprocess?.preprocessing_strategy_summary)
    ? preprocess.preprocessing_strategy_summary
    : [];

  const xPreview = Array.isArray(preprocess?.x_preview) ? preprocess.x_preview : [];

  const splitStats = preprocess?.split_stats ?? {};
  const classDistributionData = useMemo(() => {
    if (!Array.isArray(preprocess?.class_distribution_chart)) return [];
    const grouped: Record<string, Record<string, number>> = {};
    preprocess.class_distribution_chart.forEach((item: any) => {
      const split = item.split ?? "";
      const klass = item.class ?? "";
      const proportion = Number(item.proportion) ?? 0;
      if (!grouped[split]) grouped[split] = { split } as Record<string, number>;
      grouped[split][klass] = proportion;
    });
    return Object.values(grouped);
  }, [preprocess?.class_distribution_chart]);

  const classKeys = useMemo(() => {
    if (!Array.isArray(preprocess?.class_distribution_chart)) return [];
    return Array.from(new Set(preprocess.class_distribution_chart.map((item: any) => String(item.class))));
  }, [preprocess?.class_distribution_chart]);

  const targetPreview = Array.isArray(preprocess?.target_preview) ? preprocess.target_preview : [];
  const processedDatasetPreview = Array.isArray(preprocess?.processed_dataset_preview) ? preprocess.processed_dataset_preview : [];

  const downloadProcessedDataset = () => {
    const csv = preprocess?.processed_dataset_csv;
    if (!csv) return;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "processed_dataset.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const formatStrategyValue = (value: string | undefined) =>
    value ? `${value.charAt(0).toUpperCase()}${value.slice(1)}` : "-";

  return (
    <div className="space-y-8">
      <PageHeader title="Preprocessing" description="Reproducible transformations applied to the training dataset." />

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="text-sm font-semibold">Step 3 — Preprocessing Config & Train/Val/Test Split</div>
        <p className="mt-2 text-sm text-muted-foreground">
          Finalize X/y, then split immediately so every learned statistic comes from training data only.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant border-l-4 border-emerald-500/80 bg-emerald-500/10">
        <div className="text-sm font-semibold text-emerald-900">Leakage control</div>
        <p className="mt-2 text-sm text-emerald-900/90">
          The dataset is split before any feature engineering. IV/WOE, mutual information, correlation/VIF, variance, frequency maps, binning edges, imputation medians and feature-selection decisions are all learned on the training split only and applied unchanged to validation/test.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
          <div className="grid gap-4">
            <div>
              <div className="text-sm font-medium">Test Size (%)</div>
              <div className="mt-2 flex items-center gap-3">
                <input
                  type="range"
                  min={0.05}
                  max={0.45}
                  step={0.05}
                  value={testSize}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    const maxVal = Math.min(value, 0.95 - valSize);
                    setTestSize(maxVal);
                  }}
                  className="flex-1"
                />
                <div className="w-16 text-right text-sm font-mono">{Math.round(testSize * 100)}%</div>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">{splitStats.test_n ? `${splitStats.test_n.toLocaleString()} samples` : "Test split count"}</div>
            </div>

            <div>
              <div className="text-sm font-medium">Validation Size (%)</div>
              <div className="mt-2 flex items-center gap-3">
                <input
                  type="range"
                  min={0.05}
                  max={0.45}
                  step={0.05}
                  value={valSize}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    const maxVal = Math.min(value, 0.95 - testSize);
                    setValSize(maxVal);
                  }}
                  className="flex-1"
                />
                <div className="w-16 text-right text-sm font-mono">{Math.round(valSize * 100)}%</div>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">{splitStats.val_n ? `${splitStats.val_n.toLocaleString()} samples` : "Validation split count"}</div>
            </div>
          </div>

          <div className="grid gap-4">
            <div>
              <div className="text-sm font-medium">Random Seed</div>
              <div className="mt-2 flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 w-9 p-0"
                  onClick={() => setRandomSeed((value) => Math.max(1, value - 1))}
                >
                  <Minus className="h-4 w-4" />
                </Button>
                <div className="flex-1 rounded-xl border border-border bg-background px-3 py-2 text-center font-mono text-sm">{randomSeed}</div>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 w-9 p-0"
                  onClick={() => setRandomSeed((value) => value + 1)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">Ensures reproducible splits and consistent training statistics.</div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-border bg-background p-4 text-center">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">Train</div>
                <div className="mt-2 text-2xl font-semibold tabular-nums">{splitStats.train_n?.toLocaleString() ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-border bg-background p-4 text-center">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">Validation</div>
                <div className="mt-2 text-2xl font-semibold tabular-nums">{splitStats.val_n?.toLocaleString() ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-border bg-background p-4 text-center">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">Test</div>
                <div className="mt-2 text-2xl font-semibold tabular-nums">{splitStats.test_n?.toLocaleString() ?? "—"}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {classDistributionData.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-semibold">Class Distribution per Split (stratified)</div>
              <div className="mt-2 text-sm text-muted-foreground">Train, validation and test split proportions by class.</div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {classKeys.map((label) => (
                <div key={label} className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-muted-foreground">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: label === "Y" ? "#65A30D" : label === "N" ? "#84CC16" : "#94a3b8" }} />
                  {label}
                </div>
              ))}
            </div>
          </div>
          <div className="mt-5 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={classDistributionData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(15,23,42,0.06)" strokeDasharray="3 3" />
                <XAxis dataKey="split" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis tickFormatter={(value) => `${Math.round(value * 100)}%`} tickLine={false} axisLine={false} fontSize={12} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid rgba(15,23,42,0.06)', backgroundColor: '#ffffff' }} formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
                <Legend verticalAlign="top" height={36} />
                {classKeys.map((label, idx) => {
                  const palette = ["#65A30D", "#84CC16", "#94a3b8"];
                  const fill = palette[idx % palette.length];
                  return <Bar key={label} dataKey={label} stackId="a" fill={fill} radius={[6, 6, 0, 0]} />;
                })}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">Processed Dataset Preview</div>
            <p className="text-xs text-muted-foreground">Preview of the dataset after preprocessing and split selection.</p>
          </div>
          <Button variant="outline" onClick={downloadProcessedDataset} className="gap-2 self-start sm:self-auto">
            <Download className="h-4 w-4" />
            Download Processed Dataset
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="text-sm font-semibold flex items-center">
          <Target className="h-4 w-4 mr-2 text-emerald-700" />
          Target Preview
        </div>
        <div className="mt-3 overflow-x-auto">
          {targetPreview.length > 0 ? (
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr>
                  <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Index</th>
                  <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Target</th>
                </tr>
              </thead>
              <tbody>
                {targetPreview.map((value: any, index: number) => (
                  <tr key={index} className={index % 2 === 0 ? "bg-background" : ""}>
                    <td className="border-b border-border px-3 py-2 font-mono text-xs">{index + 1}</td>
                    <td className="border-b border-border px-3 py-2 font-mono text-xs">{value === null || value === undefined ? "" : String(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-6 text-center text-sm text-muted-foreground">No target preview available.</div>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="text-sm font-semibold flex items-center">
          <Download className="h-4 w-4 mr-2" />
          Processed Dataset Preview
        </div>
        <div className="mt-4 overflow-x-auto">
          {processedDatasetPreview.length > 0 ? (
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr>
                  {Object.keys(processedDatasetPreview[0]).map((key: string) => (
                    <th key={key} className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {processedDatasetPreview.map((row: any, rowIndex: number) => (
                  <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : ""}>
                    {Object.values(row).map((cell: any, cellIndex: number) => (
                      <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs">{cell === null || cell === undefined ? "" : String(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-6 text-center text-sm text-muted-foreground">No processed dataset preview available.</div>
          )}
        </div>
      </div>

      {loading && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          🔧 Building adaptive preprocessing pipeline...
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-destructive">
          {error}
        </div>
      )}

          {preprocess ? (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="text-sm text-muted-foreground flex items-center"><TableIcon className="h-4 w-4 mr-2" />Features After Prep</div>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{summary.feature_count ?? "—"}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="text-sm text-muted-foreground flex items-center"><Trash2 className="h-4 w-4 mr-2" />Duplicates Removed</div>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{summary.duplicates_removed ?? 0}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="text-sm text-muted-foreground flex items-center"><Hash className="h-4 w-4 mr-2" />Numeric Columns</div>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{summary.numeric_feature_count ?? "—"}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="text-sm text-muted-foreground flex items-center"><Tag className="h-4 w-4 mr-2" />Categorical Columns</div>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{summary.categorical_feature_count ?? "—"}</div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-sm font-semibold flex items-center"><Brain className="h-4 w-4 mr-2" />Preprocessing Decisions</div>
            <div className="mt-2 text-sm text-muted-foreground">
              The system automatically chose preprocessing strategies based on skewness, outliers, missing %, and cardinality.
            </div>
            <div className="mt-4 space-y-3">
              {decisions.length > 0 ? (
                decisions.map((item: any, index: number) => {
                  const isExpanded = Boolean(expandedDecisions[index]);
                  return (
                    <div key={index} className="rounded-lg border border-border bg-background p-3">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between text-left"
                        onClick={() => setExpandedDecisions((current) => ({ ...current, [index]: !current[index] }))}
                      >
                        <div className="font-medium text-sm">{item.column} ({item.type})</div>
                        <span className="text-xs text-muted-foreground">{isExpanded ? "Hide" : "Show"}</span>
                      </button>
                      {isExpanded && Array.isArray(item.actions) && item.actions.length > 0 && (
                        <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                          {item.actions.map((action: string, actionIndex: number) => (
                            <li key={actionIndex}>• {action}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-sm text-muted-foreground">No preprocessing decisions available.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-sm font-semibold flex items-center"><BarChartIcon className="h-4 w-4 mr-2" />Preprocessing Strategy Summary</div>
            <div className="mt-4 overflow-x-auto">
              {strategySummary.length > 0 ? (
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Column</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Type</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Scaler</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Imputer</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Encoding</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Outlier strategy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strategySummary.map((row: any, index: number) => (
                      <tr key={index} className={index % 2 === 0 ? "bg-background" : "bg-background/50"}>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.feature}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.type}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{formatStrategyValue(row.scaler)}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{formatStrategyValue(row.imputer)}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{formatStrategyValue(row.encoding)}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.outlier_strategy ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-6 text-center text-sm text-muted-foreground">No preprocessing strategy summary available.</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-sm font-semibold flex items-center"><Settings className="h-4 w-4 mr-2" />Feature Matrix Preview (X)</div>
            <div className="mt-2 text-sm text-muted-foreground">Preview of the training feature matrix after preprocessing decisions are established.</div>
            <div className="mt-4 overflow-x-auto">
              {xPreview.length > 0 ? (
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      {Object.keys(xPreview[0]).map((key: string) => (
                        <th key={key} className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {xPreview.map((row: any, rowIndex: number) => (
                      <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : ""}>
                        {Object.values(row).map((cell: any, cellIndex: number) => (
                          <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs">{cell === null || cell === undefined ? "" : String(cell)}</td>
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
        </>
      ) : !loading && !error ? (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Preparing preprocessing results...
        </div>
      ) : null}
    </div>
  );
}
