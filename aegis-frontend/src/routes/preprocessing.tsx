import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import {
  ArrowLeft, ArrowRight, Download, BarChart as BarChartIcon,
  Table as TableIcon, Brain, Loader2, AlertTriangle,
  CheckCircle2, Info,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import PlotlyChart from "@/components/plotly-chart";

import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";

export const Route = createFileRoute("/preprocessing")({
  head: () => ({ meta: [{ title: "Preprocessing — Aegis Credit" }] }),
  component: Preprocessing,
});

// ── Types for the interactive missing-value / transform workflow ───────────
type TreatmentEvidence = { missing_pct?: number; unique_values?: unknown[]; skewness?: number };
type TreatmentInfo = { treatment: string; reason: string; evidence: TreatmentEvidence };
type TransformRecommendation = {
  transform: "none" | "log1p" | "yeo_johnson";
  skew: number;
  post_transform_skew: number | null;
  reason: string;
  default_on: boolean;
};

const TREATMENT_LABELS: Record<string, string> = {
  unknown_category: "Unknown category",
  zero_fill: "Zero-fill",
  statistical: "Statistical",
  review_flag: "Review (sparse)",
};
const TREATMENT_OPTIONS = ["unknown_category", "zero_fill", "statistical", "review_flag"];

const TRANSFORM_LABELS: Record<string, string> = {
  none: "None",
  log1p: "Log",
  yeo_johnson: "Yeo-Johnson",
};
const TRANSFORM_OPTIONS = ["none", "log1p", "yeo_johnson"];

function Preprocessing() {
  const { profile, file, preprocessingResult, setPreprocessingResult } = useDataset();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Seed local preview state from context so returning to this page (e.g. via
  // Back from a later step) doesn't lose the split/preprocessing already run.
  const [preprocess, setPreprocess] = useState<any>(preprocessingResult ?? null);
  const [testSize, setTestSize] = useState(preprocessingResult?.split_config?.test_size ?? 0.15);
  const [valSize, setValSize] = useState(preprocessingResult?.split_config?.val_size ?? 0.15);
  // Not user-configurable in the UI — hardcoded to match the backend default.
  // Stage 4's seed-stability check (R4.6) varies the seed programmatically via
  // its own control on the Model Validation screen, independent of this value.
  const randomSeed = 42;

  // ── Reviewer's confirmed choices — sent back to the API on every call ──
  const [treatmentOverrides, setTreatmentOverrides] = useState<Record<string, string>>({});
  const [dropCols, setDropCols] = useState<Record<string, boolean>>({});
  const [transformChoices, setTransformChoices] = useState<Record<string, string>>({});
  const [strategyOverride, setStrategyOverride] = useState<string | null>(null);
  const initializedDefaults = useRef(false);

  // ── On-demand "impact of dropping this feature" analysis (review_flag
  //    columns only) — fetched lazily per column when the reviewer expands
  //    it, not for every column on every /data/preprocess call. ──
  const [dropImpactOpen, setDropImpactOpen] = useState<Record<string, boolean>>({});
  const [dropImpactLoading, setDropImpactLoading] = useState<Record<string, boolean>>({});
  const [dropImpactError, setDropImpactError] = useState<Record<string, string>>({});
  const [dropImpact, setDropImpact] = useState<Record<string, any>>({});

  const fetchDropImpact = async (col: string) => {
    if (!file || !preprocess?.target_col) return;
    setDropImpactLoading((prev) => ({ ...prev, [col]: true }));
    setDropImpactError((prev) => ({ ...prev, [col]: "" }));
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("target_col", preprocess.target_col);
      form.append("test_size", String(testSize));
      form.append("val_size", String(valSize));
      form.append("random_seed", String(randomSeed));
      form.append("columns", JSON.stringify([col]));
      const result = await formUpload("/data/drop-impact", form);
      const impact = (result as any)?.drop_impact?.[col];
      if (impact?.error) {
        setDropImpactError((prev) => ({ ...prev, [col]: impact.error }));
      } else {
        setDropImpact((prev) => ({ ...prev, [col]: impact }));
      }
    } catch (err: any) {
      setDropImpactError((prev) => ({
        ...prev,
        [col]: err?.body?.detail ?? err?.message ?? "Impact analysis failed.",
      }));
    } finally {
      setDropImpactLoading((prev) => ({ ...prev, [col]: false }));
    }
  };

  const toggleDropImpact = (col: string) => {
    const nextOpen = !dropImpactOpen[col];
    setDropImpactOpen((prev) => ({ ...prev, [col]: nextOpen }));
    if (nextOpen && !dropImpact[col] && !dropImpactLoading[col]) {
      fetchDropImpact(col);
    }
  };

  // Consumed once: if we mounted with a cached result already in context (e.g.
  // navigating back from Feature Engineering/Training and forward again), skip
  // the very next auto-run and reuse it instead of silently re-POSTing and
  // potentially producing a fresh (if non-deterministic) split. Any later
  // change the reviewer makes to test size, seed, or treatments still runs.
  const skipInitialAutoRun = useRef(preprocessingResult !== null);

  useEffect(() => {
    const runPreprocess = async () => {
      if (!profile) return;

      if (skipInitialAutoRun.current) {
        skipInitialAutoRun.current = false;
        return;
      }

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
        form.append("treatment_overrides", JSON.stringify(treatmentOverrides));
        form.append(
          "drop_cols",
          JSON.stringify(Object.entries(dropCols).filter(([, v]) => v).map(([k]) => k)),
        );
        form.append("transform_choices", JSON.stringify(transformChoices));
        if (strategyOverride) {
          form.append("strategy_override", strategyOverride);
        }

        const result = await formUpload("/data/preprocess", form);
        setPreprocess(result);
        // Publish to shared context so Training (which no longer re-splits)
        // can read split_stats / split_config directly.
        setPreprocessingResult(result);

        // Seed local selection state from the platform's proposal, but only
        // ONCE — after that, the reviewer's own edits are what's sent back,
        // never silently overwritten by a fresh proposal on a later call.
        if (!initializedDefaults.current) {
          const proposal = (result as any)?.missing_treatment_proposal ?? {};
          const recommendations = (result as any)?.transform_recommendations ?? {};

          const seededDrop: Record<string, boolean> = {};
          Object.entries(proposal).forEach(([col, info]: [string, any]) => {
            if (info?.treatment === "review_flag") seededDrop[col] = true;
          });

          const seededTransforms: Record<string, string> = {};
          Object.entries(recommendations).forEach(([col, rec]: [string, any]) => {
            if (rec?.transform && rec.transform !== "none") {
              seededTransforms[col] = rec.transform;
            }
          });

          if (Object.keys(seededDrop).length > 0) setDropCols(seededDrop);
          if (Object.keys(seededTransforms).length > 0) setTransformChoices(seededTransforms);
          initializedDefaults.current = true;
        }
      } catch (err: any) {
        setError(err?.body?.detail ?? err?.message ?? "Preprocessing failed.");
        setPreprocess(null);
      } finally {
        setLoading(false);
      }
    };

    runPreprocess();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    profile, file, testSize, valSize, randomSeed,
    treatmentOverrides, dropCols, transformChoices, strategyOverride,
  ]);

  useEffect(() => {
    if (!preprocess?.split_config) return;
    setTestSize(preprocess.split_config.test_size ?? 0.15);
    setValSize(preprocess.split_config.val_size ?? 0.15);
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

  const classDistributionFigure = useMemo(() => {
    if (!classDistributionData || classDistributionData.length === 0) return null;
    const x = classDistributionData.map((d: any) => d.split ?? "");

    const traces = [
      {
        type: "bar",
        name: "Class 0",
        x,
        y: classDistributionData.map((row: any) => Number(row["0"] ?? 0)),
        marker: { color: "#65A30D" },
        hovertemplate: "%{x}<br>%{y:.1%}<extra></extra>",
      },
      {
        type: "bar",
        name: "Class 1",
        x,
        y: classDistributionData.map((row: any) => Number(row["1"] ?? 0)),
        marker: { color: "#84CC16" },
        hovertemplate: "%{x}<br>%{y:.1%}<extra></extra>",
      },
    ];

    const layout: any = {
      barmode: "stack",
      margin: { t: 10, r: 20, l: 60, b: 60 },
      xaxis: { title: "", automargin: true },
      yaxis: { title: "", tickformat: ".0%", automargin: true, range: [0, 1] },
      legend: { orientation: "h", y: 1.12 },
    };

    return { data: traces, layout };
  }, [classDistributionData]);


  // ── Missing-value treatment proposal (every column classify_missing_treatment
  //    found — i.e. every column that actually has missing values) ──
  const missingProposal: Record<string, TreatmentInfo> = preprocess?.missing_treatment_proposal ?? {};
  const missingProposalEntries = Object.entries(missingProposal);
  const imputationStrategy = preprocess?.imputation_strategy;
  const recalibratedColumns: Array<{ column: string; treatment: string }> = preprocess?.recalibrated_columns ?? [];
  const reviewMissingThreshold: number = preprocess?.review_missing_threshold ?? 0.4;

  // ── Skew-driven transform recommendations — only columns that need a
  //    real decision are ever shown; symmetric/mild-skew columns are silently
  //    left alone (recommend_transform already resolved "none" for them). ──
  const transformRecommendations: Record<string, TransformRecommendation> = preprocess?.transform_recommendations ?? {};
  const transformDecisions = Object.entries(transformRecommendations)
    .filter(([, rec]) => rec.transform !== "none")
    .sort((a, b) => Math.abs(b[1].skew) - Math.abs(a[1].skew));

  const downloadCsv = (csv: string | undefined, filename: string) => {
    if (!csv) return;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const severityBadge = (skew: number) => {
    const abs = Math.abs(skew);
    if (abs >= 2.0) return { label: "High skew", className: "bg-red-500/15 text-red-700 border-red-500/30" };
    if (abs >= 1.5) return { label: "Moderate skew", className: "bg-amber-500/15 text-amber-700 border-amber-500/30" };
    return { label: "Mild skew", className: "bg-yellow-500/15 text-yellow-700 border-yellow-500/30" };
  };

  return (
    <div className="space-y-8">
      <PageHeader title="Preprocessing" description="Reproducible transformations applied to the training dataset." />

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="text-sm font-semibold">Step 3 — Preprocessing Config &amp; Train/Val/Test Split</div>
        <p className="mt-2 text-sm text-muted-foreground">
          Finalize X/y, then split immediately so every learned statistic comes from training data only.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-elegant border-l-4 border-blue-500/80 bg-blue-500/10">
        <div className="text-sm font-semibold text-blue-900">Leakage control</div>
        <p className="mt-2 text-sm text-blue-900/90">
          The dataset is split before any feature engineering. Missing-value treatment, imputation strategy,
          skew/transform recommendations, IV/WOE, correlation/VIF, and feature-selection decisions are all
          learned on the training split only and applied unchanged to validation/test.
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

      {loading && (
        <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
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
                {classDistributionFigure ? (
                  <PlotlyChart figure={classDistributionFigure} style={{ height: "100%", minHeight: "100%" }} />
                ) : null}
              </div>
            </div>
          )}

          {/* ── Missing Value Treatment ────────────────────────────────── */}
          <Card className="shadow-elegant">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Brain className="h-4 w-4" />
                Missing Value Treatment
              </CardTitle>
              <CardDescription>
                Each column is classified by its data shape alone — no column-name guessing. Review the
                proposal and override anything before it&apos;s applied.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {missingProposalEntries.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  No missing values in the training features — imputation not required.
                </div>
              ) : (
                <>
                  <div className="rounded-lg border border-border bg-background p-3 text-xs text-muted-foreground leading-relaxed">
                    <span className="font-medium text-foreground">Unknown category</span> — categorical column, filled with an explicit &apos;Unknown&apos; value.{" "}
                    <span className="font-medium text-foreground">Zero-fill</span> — binary or structural-zero numeric column.{" "}
                    <span className="font-medium text-foreground">Statistical</span> — genuinely missing numeric values, filled jointly via MICE, KNN, or median.{" "}
                    <span className="font-medium text-foreground">Review</span> — over {Math.round(reviewMissingThreshold * 100)}% missing, too sparse to impute reliably.
                  </div>

                  {missingProposalEntries
                    .sort((a, b) => (b[1].evidence?.missing_pct ?? 0) - (a[1].evidence?.missing_pct ?? 0))
                    .map(([col, info]) => {
                      const isDropped = Boolean(dropCols[col]);
                      const currentTreatment = treatmentOverrides[col] ?? info.treatment;
                      const missingPct = info.evidence?.missing_pct ?? 0;
                      const isReviewFlag = info.treatment === "review_flag";

                      return (
                        <div
                          key={col}
                          className={`rounded-lg border p-3 ${isReviewFlag ? "border-amber-500/40 bg-amber-500/5" : "border-border bg-background"}`}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-sm">{col}</span>
                            <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                              {(missingPct * 100).toFixed(1)}% missing
                            </span>
                            {isReviewFlag && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-xs text-amber-700">
                                <AlertTriangle className="h-3 w-3" />
                                Sparse
                              </span>
                            )}
                          </div>
                          <p className="mt-1.5 text-xs text-muted-foreground">{info.reason}</p>

                          {isReviewFlag && (
                            <div className="mt-2">
                              <button
                                type="button"
                                onClick={() => toggleDropImpact(col)}
                                className="text-xs font-medium text-amber-700 underline decoration-dotted underline-offset-2 hover:text-amber-800"
                              >
                                {dropImpactOpen[col] ? "Hide" : "Show"} impact of dropping this feature
                              </button>

                              {dropImpactOpen[col] && (
                                <div className="mt-2 rounded-lg border border-border bg-background p-3">
                                  {dropImpactLoading[col] ? (
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                      Analyzing impact of dropping {col}...
                                    </div>
                                  ) : dropImpactError[col] ? (
                                    <div className="text-xs text-red-600">{dropImpactError[col]}</div>
                                  ) : dropImpact[col] ? (
                                    <>
                                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                        <div>
                                          <div className="text-xs text-muted-foreground">Predictive importance (IV)</div>
                                          <div className="text-sm font-semibold tabular-nums">
                                            {dropImpact[col].iv !== null && dropImpact[col].iv !== undefined
                                              ? dropImpact[col].iv.toFixed(3)
                                              : "n/a"}
                                          </div>
                                          {dropImpact[col].iv_label && (
                                            <div className="text-xs text-muted-foreground">{dropImpact[col].iv_label}</div>
                                          )}
                                        </div>
                                        <div>
                                          <div className="text-xs text-muted-foreground">Most correlated feature</div>
                                          {dropImpact[col].redundant_col ? (
                                            <>
                                              <div className="text-sm font-semibold">{dropImpact[col].redundant_col}</div>
                                              <div className="text-xs text-muted-foreground">
                                                {"|corr|="}{Math.abs(dropImpact[col].redundant_corr).toFixed(2)}
                                              </div>
                                            </>
                                          ) : (
                                            <>
                                              <div className="text-sm font-semibold">None found</div>
                                              <div className="text-xs text-muted-foreground">no redundancy ≥ 0.60</div>
                                            </>
                                          )}
                                        </div>
                                      </div>

                                      <div
                                        className={`mt-3 rounded-md border-l-4 p-2.5 text-xs ${
                                          dropImpact[col].verdict_tone === "safe"
                                            ? "border-emerald-500 bg-emerald-500/5 text-emerald-900"
                                            : dropImpact[col].verdict_tone === "caution"
                                            ? "border-amber-500 bg-amber-500/5 text-amber-900"
                                            : dropImpact[col].verdict_tone === "risk"
                                            ? "border-red-500 bg-red-500/5 text-red-900"
                                            : "border-border bg-background text-muted-foreground"
                                        }`}
                                      >
                                        <span className="font-medium">Verdict: </span>
                                        {dropImpact[col].verdict}
                                      </div>
                                    </>
                                  ) : null}
                                </div>
                              )}
                            </div>
                          )}

                          <div className="mt-3 flex flex-wrap items-center gap-3">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">Treatment</span>
                              <Select
                                value={currentTreatment}
                                disabled={isDropped}
                                onValueChange={(value) =>
                                  setTreatmentOverrides((prev) => ({ ...prev, [col]: value }))
                                }
                              >
                                <SelectTrigger className="h-8 w-[180px] border-primary bg-primary text-xs text-primary-foreground hover:bg-primary/90 focus:ring-primary data-[placeholder]:text-primary-foreground [&>span]:text-primary-foreground [&_svg]:text-primary-foreground [&_svg]:opacity-80 disabled:border-primary/40 disabled:bg-primary/40 disabled:text-primary-foreground/70">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {TREATMENT_OPTIONS.map((opt) => (
                                    <SelectItem key={opt} value={opt}>{TREATMENT_LABELS[opt]}</SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>

                            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                              <Checkbox
                                checked={isDropped}
                                onCheckedChange={(checked) =>
                                  setDropCols((prev) => ({ ...prev, [col]: Boolean(checked) }))
                                }
                              />
                              Drop variable — removed entirely, not used in training or evaluation
                            </label>
                          </div>
                        </div>
                      );
                    })}

                  {recalibratedColumns.length > 0 && (
                    <div className="flex items-start gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 text-xs text-sky-900">
                      <Info className="h-4 w-4 mt-0.5 shrink-0" />
                      <div>
                        <span className="font-medium">Recalibrated</span> — kept despite being flagged for
                        review, so a real imputation method was found instead of leaving it untreated:{" "}
                        {recalibratedColumns.map((r) => `${r.column} → ${TREATMENT_LABELS[r.treatment] ?? r.treatment}`).join(", ")}
                      </div>
                    </div>
                  )}

                  {imputationStrategy && (
                    <div className="rounded-lg border border-border border-l-4 border-l-primary bg-background p-3">
                      <div className="text-sm font-medium">
                        Statistical imputation method: <span className="font-mono">{imputationStrategy.method?.toUpperCase()}</span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{imputationStrategy.reason}</p>
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Override</span>
                        <Select
                          value={strategyOverride ?? "auto"}
                          onValueChange={(value) => setStrategyOverride(value === "auto" ? null : value)}
                        >
                          <SelectTrigger className="h-8 w-[160px] border-primary bg-primary text-xs text-primary-foreground hover:bg-primary/90 focus:ring-primary data-[placeholder]:text-primary-foreground [&>span]:text-primary-foreground [&_svg]:text-primary-foreground [&_svg]:opacity-80">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="auto">Auto (recommended)</SelectItem>
                            <SelectItem value="mice">MICE</SelectItem>
                            <SelectItem value="knn">KNN</SelectItem>
                            <SelectItem value="median">Median</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* ── Skew-Driven Transforms ─────────────────────────────────── */}
          <Card className="shadow-elegant">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <BarChartIcon className="h-4 w-4" />
                Skew-Driven Transforms
              </CardTitle>
              <CardDescription>
                {transformDecisions.length > 0
                  ? `${transformDecisions.length} of ${Object.keys(transformRecommendations).length} numeric column(s) are skewed enough to matter — everything else is left alone.`
                  : "No numeric columns are skewed enough to need a transform."}
              </CardDescription>
            </CardHeader>
            {transformDecisions.length > 0 && (
              <CardContent className="space-y-3">
                {transformDecisions.map(([col, rec]) => {
                  const badge = severityBadge(rec.skew);
                  const current = transformChoices[col] ?? "none";
                  return (
                    <div key={col} className="rounded-lg border border-border bg-background p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-sm">{col}</span>
                        <span className={`rounded-full border px-2 py-0.5 text-xs ${badge.className}`}>
                          {badge.label} · {rec.skew.toFixed(2)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          recommended: <span className="font-medium text-foreground">{TRANSFORM_LABELS[rec.transform]}</span>
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs text-muted-foreground">{rec.reason}</p>
                      <div className="mt-3 flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Apply</span>
                        <Select
                          value={current}
                          onValueChange={(value) => setTransformChoices((prev) => ({ ...prev, [col]: value }))}
                        >
                          <SelectTrigger className="h-8 w-[160px] border-primary bg-primary text-xs text-primary-foreground hover:bg-primary/90 focus:ring-primary data-[placeholder]:text-primary-foreground [&>span]:text-primary-foreground [&_svg]:text-primary-foreground [&_svg]:opacity-80">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {TRANSFORM_OPTIONS.map((opt) => (
                              <SelectItem key={opt} value={opt}>{TRANSFORM_LABELS[opt]}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            )}
          </Card>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-sm font-semibold flex items-center"><TableIcon className="h-4 w-4 mr-2" />Preprocessing Strategy Summary</div>
            <div className="mt-4 overflow-x-auto">
              {strategySummary.length > 0 ? (
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">#</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Column</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Type</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Scaler</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Imputer</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Encoding</th>
                      <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">Transform</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strategySummary.map((row: any, index: number) => (
                      <tr key={index} className={index % 2 === 0 ? "bg-background" : "bg-background/50"}>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{index + 1}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.feature}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.type}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.scaler}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.imputer}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.encoding}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.transform ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-6 text-center text-sm text-muted-foreground">No preprocessing strategy summary available.</div>
              )}
            </div>
          </div>

          {/* ── Downloads ───────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-semibold">Original Dataset</div>
                <p className="text-xs text-muted-foreground">The dataset exactly as uploaded, before any processing.</p>
              </div>
              <Button
                variant="outline"
                onClick={() => downloadCsv(preprocess?.original_dataset_csv, "original_dataset.csv")}
                className="gap-2 self-start sm:self-auto"
              >
                <Download className="h-4 w-4" />
                Download
              </Button>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-semibold">Transformed Dataset</div>
                <p className="text-xs text-muted-foreground">Training split after imputation, scaling and encoding.</p>
              </div>
              <Button
                variant="outline"
                onClick={() => downloadCsv(preprocess?.processed_dataset_csv, "transformed_dataset.csv")}
                className="gap-2 self-start sm:self-auto"
              >
                <Download className="h-4 w-4" />
                Download
              </Button>
            </div>
          </div>

          <Separator />

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
