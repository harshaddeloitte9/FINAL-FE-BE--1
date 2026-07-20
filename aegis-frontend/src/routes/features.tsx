import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { useDataset } from "@/lib/app-context";
import { formUpload } from "@/lib/api";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Loader, ArrowLeft, ArrowRight, Download, Globe, RefreshCw, Table as TableIcon, Trash2, Hash, Tag } from "lucide-react";
import { computeFeatureRemovalProposal } from "@/lib/feature-removal";

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
  engineered_feature_names?: string[];
  selected_features?: string[];
  dropped_features?: string[];
  encoding_summary?: Record<string, any>;
  feature_engineering_report?: Record<string, any>;
  feature_importance_summary?: Record<string, any>;
  x_engineered_shape?: number[];
  x_engineered_preview?: any[];
  final_engineered_dataset_preview?: any[];
  x_engineered_csv?: string;
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
  interaction_features?: Array<{
    name?: string;
    feature_a?: string;
    feature_b?: string;
    type?: string;
    interaction_type?: string;
    score?: number;
    gini?: number;
    source?: string;
  }>;
}

interface MacroDateCandidate {
  column: string;
  is_preferred: boolean;
}

function Features() {
  const navigate = useNavigate();
  const { file, profile, setUploadResult, featureEngineeringResult, setFeatureEngineeringResult, preprocessingResult } = useDataset();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Seed from the shared context so returning to this page (e.g. via Back from
  // Training) shows the already-computed result instead of looking reset.
  const [engineeringResult, setEngineeringResult] = useState<FeatureEngineeringResponse | null>(
    (featureEngineeringResult as FeatureEngineeringResponse | null) ?? null,
  );
  const [vifSortKey, setVifSortKey] = useState<"feature" | "value">("value");
  const [vifSortAsc, setVifSortAsc] = useState(false);

  // ── Macroeconomic Features (FRED) ──────────────────────────────────────────
  // Fetched once (per date column choice) and, once attached, carried forward
  // as csv_text (instead of the original file) into every /data/feature-
  // engineering call below, so macro columns run through the same IV/WOE, MI,
  // binning and correlation analysis as any other numeric feature.
  const [macroCandidates, setMacroCandidates] = useState<MacroDateCandidate[]>([]);
  const [macroDefaultDateCol, setMacroDefaultDateCol] = useState<string | null>(null);
  const [selectedMacroDateCol, setSelectedMacroDateCol] = useState<string>("");
  const [macroColumns, setMacroColumns] = useState<string[]>([]);
  const [macroDateColUsed, setMacroDateColUsed] = useState<string | null>(null);
  const [datasetCsvText, setDatasetCsvText] = useState<string | null>(null);
  const [macroLoading, setMacroLoading] = useState(false);
  const [macroError, setMacroError] = useState<string | null>(null);

  // Guards against out-of-order responses: runFeatureEngineering() is called
  // both on mount (no macro yet) and again right after a FRED fetch resolves
  // (datasetCsvText changes). /data/feature-engineering does non-trivial work
  // (IV/WOE, MI, VIF, interaction search) so its latency varies — without this,
  // if the mount request happens to resolve AFTER the macro-triggered one, its
  // stale (macro-less) result silently overwrites the correct one, even though
  // the "FRED features attached" banner (driven by separate state) still shows
  // success. Only the response matching the most recently issued request id
  // is ever applied.
  const feRequestIdRef = useRef(0);

  // The FRED fetch always attaches macro_* columns onto THIS pristine file,
  // never onto whatever ds.file currently is — once a fetch succeeds, ds.file
  // itself becomes the macro-augmented version (see fetchMacroFeatures), so
  // without this a second fetch (e.g. after picking a different date column)
  // would attach macro columns on top of an already-augmented file and
  // produce duplicate macro_gdp/macro_unemployment/macro_interest_rate columns.
  const originalFileRef = useRef<File | null>(null);
  useEffect(() => {
    if (file && !originalFileRef.current) {
      originalFileRef.current = file;
    }
  }, [file]);

  // ── Feature Removal — propose-confirm ──────────────────────────────────────
  const [removeChecked, setRemoveChecked] = useState<Record<string, boolean>>({});
  const [confirmedRemoveCols, setConfirmedRemoveCols] = useState<string[] | null>(null);
  const [applyingRemoval, setApplyingRemoval] = useState(false);

  const targetCol = useMemo(() => {
    if (!profile) return "";
    if (profile.columns && Array.isArray(profile.columns) && profile.columns.includes("loan_status")) {
      return "loan_status";
    }
    if (profile.target_candidates && Array.isArray(profile.target_candidates) && profile.target_candidates.length > 0) {
      return profile.target_candidates[0];
    }
    return "";
  }, [profile]);

  const runFeatureEngineering = async (overrideConfirmedRemove?: string[]) => {
    if (!file || !targetCol || targetCol === "string") {
      setError("Could not determine target column. Please check the uploaded dataset.");
      return;
    }
    const requestId = ++feRequestIdRef.current;
    try {
      setLoading(true);
      setError(null);

      const form = new FormData();
      if (datasetCsvText) {
        form.append("csv_text", datasetCsvText);
      } else {
        form.append("file", file);
      }
      form.append("target_col", targetCol);
      const remove = overrideConfirmedRemove ?? confirmedRemoveCols;
      if (remove !== null && remove !== undefined) {
        form.append("confirmed_remove_cols", JSON.stringify(remove));
      }

      const result = await formUpload<FeatureEngineeringResponse>("/data/feature-engineering", form);
      if (requestId !== feRequestIdRef.current) {
        // A newer request (e.g. triggered by a FRED macro fetch) was issued
        // while this one was in flight — drop this stale response instead of
        // overwriting the newer result.
        return;
      }
      setEngineeringResult(result);
      // Publish to shared context so navigating away and back (or forward to
      // Training) reuses this result instead of forcing a recompute.
      setFeatureEngineeringResult(result as unknown as Record<string, any>);
    } catch (err) {
      if (requestId !== feRequestIdRef.current) return;
      const message = err instanceof Error ? err.message : "Failed to run feature engineering";
      setError(message);
    } finally {
      if (requestId === feRequestIdRef.current) {
        setLoading(false);
        setApplyingRemoval(false);
      }
    }
  };

  // Fetch the date-column candidates for macro alignment once the dataset is
  // available — lightweight, doesn't block the initial analysis below.
  useEffect(() => {
    if (!file) return;
    (async () => {
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await formUpload<{ candidates: MacroDateCandidate[]; default_date_col: string | null }>(
          "/data/macro/date-columns",
          form,
        );
        setMacroCandidates(res.candidates ?? []);
        setMacroDefaultDateCol(res.default_date_col ?? null);
        setSelectedMacroDateCol(res.default_date_col ?? (res.candidates?.[0]?.column ?? ""));
      } catch {
        // Non-fatal — the macro section just won't have a default selection.
      }
    })();
  }, [file]);

  // Consumed once: if we mounted with a cached result already in context (e.g.
  // navigating back from Training and forward again), skip the very next
  // auto-run and reuse it instead of silently recomputing feature engineering
  // from scratch. Any later change to file/profile/datasetCsvText (a genuinely
  // new dataset or macro fetch) still triggers a real recompute.
  const skipInitialAutoRun = useRef(engineeringResult !== null);

  useEffect(() => {
    if (!file || !profile) {
      setError("No dataset uploaded. Please upload a dataset first.");
      return;
    }
    if (skipInitialAutoRun.current) {
      skipInitialAutoRun.current = false;
      return;
    }
    runFeatureEngineering();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, profile, datasetCsvText]);

  const fetchMacroFeatures = async () => {
    const baseFile = originalFileRef.current ?? file;
    if (!baseFile || !selectedMacroDateCol) return;
    try {
      setMacroLoading(true);
      setMacroError(null);
      const form = new FormData();
      form.append("file", baseFile);
      form.append("date_col", selectedMacroDateCol);
      const res = await formUpload<{
        macro_columns: string[];
        date_col_used: string;
        csv_with_macro: string;
      }>("/data/macro/fetch", form);
      setMacroColumns(res.macro_columns ?? []);
      setMacroDateColUsed(res.date_col_used ?? selectedMacroDateCol);
      setDatasetCsvText(res.csv_with_macro);

      // Carry the macro-augmented dataset forward as the working file so
      // every later stage (preprocessing, training, explainability) — which
      // read ds.file from context, not this page's local datasetCsvText —
      // sees the same macro columns instead of silently falling back to the
      // original upload.
      const macroBlob = new Blob([res.csv_with_macro], { type: "text/csv" });
      const macroFile = new File([macroBlob], baseFile.name, { type: "text/csv" });
      setUploadResult(macroFile, profile);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch FRED macro features";
      setMacroError(message);
    } finally {
      setMacroLoading(false);
    }
  };

  const handleReFetchMacro = () => {
    setMacroColumns([]);
    setMacroDateColUsed(null);
    setDatasetCsvText(null);
    setMacroError(null);
    // Revert ds.file to the pristine (pre-macro) dataset so the next fetch
    // attaches macro columns fresh instead of stacking onto the last result.
    if (originalFileRef.current) {
      setUploadResult(originalFileRef.current, profile);
    }
  };

  const plan = engineeringResult?.feature_engineering_plan ?? {};
  const summary = engineeringResult?.feature_engineering_summary ?? {};

  const addedFeatures = Array.isArray(summary.added) ? summary.added : [];
  const removedFeatures = Array.isArray(summary.removed) ? summary.removed : [];
  const engineeredFeatureNames = Array.isArray(engineeringResult?.engineered_feature_names) ? engineeringResult.engineered_feature_names : [];
  const selectedFeatures = Array.isArray(engineeringResult?.selected_features) && engineeringResult.selected_features.length > 0
    ? engineeringResult.selected_features
    : engineeredFeatureNames;
  const droppedFeatures = Array.isArray(engineeringResult?.dropped_features) && engineeringResult.dropped_features.length > 0
    ? engineeringResult.dropped_features
    : removedFeatures;
  const encodingSummary = engineeringResult?.encoding_summary && typeof engineeringResult.encoding_summary === "object"
    ? engineeringResult.encoding_summary
    : {};
  const featureEngineeringReport = engineeringResult?.feature_engineering_report && typeof engineeringResult.feature_engineering_report === "object"
    ? engineeringResult.feature_engineering_report
    : {};
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

  const interactionFeatures = Array.isArray(engineeringResult?.interaction_features)
    ? engineeringResult.interaction_features
    : [];

  // ── Feature Removal — propose-confirm, computed client-side ────────────────
  // Shared with the Explainability > Summary full report — see
  // lib/feature-removal.ts for the cascade-rescue logic itself.
  const removalProposal = useMemo(() => computeFeatureRemovalProposal(plan), [plan]);

  // Fill in default checkbox state for any newly-proposed feature, preserving
  // whatever the reviewer already toggled for features seen before.
  useEffect(() => {
    setRemoveChecked((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const row of removalProposal.rows) {
        if (!(row.feature in next)) {
          next[row.feature] = row.defaultRemove;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [removalProposal.rows.map((r) => r.feature).join("|")]);

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

  const downloadEngineeredDataset = () => {
    if (!engineeringResult?.x_engineered_csv) return;
    const blob = new Blob([engineeringResult.x_engineered_csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "engineered_dataset.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const applyRemovalChoices = () => {
    const confirmed = removalProposal.rows.filter((row) => removeChecked[row.feature]).map((row) => row.feature);
    setApplyingRemoval(true);
    setConfirmedRemoveCols(confirmed);
    runFeatureEngineering(confirmed);
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

  // Recap of what preprocessing produced — the starting point feature
  // engineering builds on top of. Moved here from the Preprocessing screen,
  // where it was rendering above the Missing Value Treatment section (i.e.
  // showing the post-preprocessing result before preprocessing had actually
  // been explained on that same page).
  const preprocessSummary = {
    feature_count: preprocessingResult?.feature_count ?? preprocessingResult?.summary_metrics?.features_basic,
    duplicates_removed:
      preprocessingResult?.duplicates_removed ?? preprocessingResult?.summary_metrics?.duplicates_removed ?? 0,
    numeric_feature_count:
      preprocessingResult?.numeric_feature_count ?? preprocessingResult?.summary_metrics?.numeric_columns,
    categorical_feature_count:
      preprocessingResult?.categorical_feature_count ?? preprocessingResult?.summary_metrics?.categorical_columns,
    // Boolean/datetime columns are real modeled features (present in
    // feature_count) but aren't numeric or categorical — surfaced separately
    // so the four counts always reconcile instead of silently undercounting.
    other_feature_count:
      (preprocessingResult?.boolean_feature_count ?? preprocessingResult?.summary_metrics?.boolean_columns ?? 0) +
      (preprocessingResult?.datetime_feature_count ?? preprocessingResult?.summary_metrics?.datetime_columns ?? 0),
  };

  return (
    <div className="space-y-8">
      <PageHeader title="Feature Engineering" description="Engineered features, multicollinearity diagnostics, and importance preview." />

      {preprocessingResult && (
        <div className={`grid grid-cols-1 gap-4 md:grid-cols-4${preprocessSummary.other_feature_count > 0 ? " xl:grid-cols-5" : ""}`}>
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center text-sm text-muted-foreground"><TableIcon className="h-4 w-4 mr-2" />Feature Count After Cleanup</div>
            <div className="mt-3 text-3xl font-semibold tabular-nums">{preprocessSummary.feature_count ?? "—"}</div>
            <div className="mt-1 text-xs text-muted-foreground">Columns remaining after removing sparse/ID columns</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center text-sm text-muted-foreground"><Trash2 className="h-4 w-4 mr-2" />Duplicate Rows Removed</div>
            <div className="mt-3 text-3xl font-semibold tabular-nums">{preprocessSummary.duplicates_removed ?? 0}</div>
            <div className="mt-1 text-xs text-muted-foreground">Exact-copy rows dropped before splitting</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center text-sm text-muted-foreground"><Hash className="h-4 w-4 mr-2" />Numeric Columns</div>
            <div className="mt-3 text-3xl font-semibold tabular-nums">{preprocessSummary.numeric_feature_count ?? "—"}</div>
            <div className="mt-1 text-xs text-muted-foreground">Continuous fields available for modeling</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center text-sm text-muted-foreground"><Tag className="h-4 w-4 mr-2" />Categorical Columns</div>
            <div className="mt-3 text-3xl font-semibold tabular-nums">{preprocessSummary.categorical_feature_count ?? "—"}</div>
            <div className="mt-1 text-xs text-muted-foreground">Non-numeric fields requiring encoding</div>
          </div>
          {preprocessSummary.other_feature_count > 0 && (
            <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
              <div className="flex items-center text-sm text-muted-foreground"><TableIcon className="h-4 w-4 mr-2" />Other Columns</div>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{preprocessSummary.other_feature_count}</div>
              <div className="mt-1 text-xs text-muted-foreground">Boolean/datetime fields, engineered separately</div>
            </div>
          )}
        </div>
      )}

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-primary" />
          <h2 className="text-base font-semibold">Macroeconomic Features (FRED)</h2>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Pulls in economic data (GDP, unemployment, interest rates) matched to the month each loan started —
          never a default or charge-off date, which would leak future information into the model. This reflects
          conditions at the time the loan was made, in line with IFRS 9 requirements. It's added before the
          analysis below runs, so it's treated just like any other feature.
        </p>

        {macroColumns.length > 0 ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
              ✅ Economic data attached: {macroColumns.join(", ")}
              {macroDateColUsed && <> (matched to the month of <code className="font-mono">{macroDateColUsed}</code>)</>} —
              it'll be treated just like any other feature in the analysis below.
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium transition hover:border-primary hover:bg-primary-soft"
              onClick={handleReFetchMacro}
            >
              <RefreshCw className="h-4 w-4" />
              Re-fetch / change macro features
            </button>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Loan origination date column (macro features are aligned to this, by calendar month)
              </label>
              <select
                className="mt-2 w-full max-w-md rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={selectedMacroDateCol}
                onChange={(e) => setSelectedMacroDateCol(e.target.value)}
              >
                <option value="">— none —</option>
                {macroCandidates.map(({ column, is_preferred }) => (
                  <option key={column} value={column}>
                    {is_preferred ? `⭐ ${column} (origination/loan date)` : column}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              disabled={!selectedMacroDateCol || macroLoading}
              className="inline-flex items-center gap-2 rounded-lg border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={fetchMacroFeatures}
            >
              {macroLoading ? <Loader className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
              Fetch FRED macro features
            </button>
            {!selectedMacroDateCol && (
              <p className="text-xs text-muted-foreground">
                Select the loan origination date column and click Fetch to attach FRED macro features (GDP,
                unemployment, Fed funds rate) aligned to that month.
              </p>
            )}
            {macroError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{macroError}</div>
            )}
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {originalFeatures !== null && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Original features</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{originalFeatures}</div>
            <div className="mt-1 text-xs text-muted-foreground">Columns before feature engineering</div>
          </div>
        )}
        {finalFeatures !== null && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Final features</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{finalFeatures}</div>
            <div className="mt-1 text-xs text-muted-foreground">Columns after feature engineering</div>
          </div>
        )}
        {addedFeatures.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Features added</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{addedFeatures.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">New engineered columns created</div>
          </div>
        )}
        {removedFeatures.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Features removed</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{removedFeatures.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Columns dropped during feature engineering</div>
          </div>
        )}
      </section>

      <section className="flex flex-wrap gap-3">
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition hover:border-primary hover:bg-primary-soft"
          onClick={downloadEngineeredDataset}
        >
          <Download className="h-4 w-4" />
          Download engineered dataset
        </button>
      </section>

      {/* Feature Engineering Plan section removed from UI per streamline request.
          Backend continues computing: appliedSteps, selectedFeatures, droppedFeatures.
          Full plan detail is available in downloadable CSV reports. */}

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h2 className="text-base font-semibold">🗑️ Feature Removal Proposal</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Features proposed for removal by automated analysis. Untick any row to retain that feature. Click Apply
          to re-run feature engineering with your confirmed choices.
        </p>

        {removalProposal.rescueSet.size > 0 && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            <RefreshCw className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <div>
              <strong>Cascade rescue</strong> — {Array.from(removalProposal.rescueSet).map((f) => `\`${f}\``).join(", ")}{" "}
              pre-retained: both members of a correlated pair were proposed for removal; the higher-IV member was
              kept so the information family doesn't vanish entirely.
            </div>
          </div>
        )}

        {removalProposal.rows.length > 0 ? (
          <>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="border-b border-border px-3 py-2">#</th>
                    <th className="border-b border-border px-3 py-2">Feature</th>
                    <th className="border-b border-border px-3 py-2">IV</th>
                    <th className="border-b border-border px-3 py-2">Reason</th>
                    <th className="border-b border-border px-3 py-2">Remove?</th>
                  </tr>
                </thead>
                <tbody>
                  {removalProposal.rows.map((row, rowIndex) => (
                    <tr key={row.feature} className="odd:bg-background">
                      <td className="border-b border-border px-3 py-2 font-mono text-xs text-muted-foreground">{rowIndex + 1}</td>
                      <td className="border-b border-border px-3 py-2 font-mono text-xs">{row.feature}</td>
                      <td className="border-b border-border px-3 py-2 text-xs">{row.iv !== null ? row.iv.toFixed(4) : "—"}</td>
                      <td className="border-b border-border px-3 py-2 text-xs text-muted-foreground">{row.reason}</td>
                      <td className="border-b border-border px-3 py-2 text-xs">
                        <input
                          type="checkbox"
                          checked={!!removeChecked[row.feature]}
                          onChange={(e) =>
                            setRemoveChecked((prev) => ({ ...prev, [row.feature]: e.target.checked }))
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button
              type="button"
              disabled={applyingRemoval || loading}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={applyRemovalChoices}
            >
              {applyingRemoval ? <Loader className="h-4 w-4 animate-spin" /> : null}
              Apply removal choices
            </button>
          </>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">No features proposed for removal on this dataset.</p>
        )}
      </section>

      {/* Encoding summary section removed from UI per streamline request.
          Transformations (Log transform, WOE, binning, etc.) continue backend-side.
          Full encoding report available in CSV downloads. */}

      {/* "Transformations applied" section removed from UI per streamline request.
          Applied steps continue computing server-side for CSV exports. */}

      {/* Diagnostic tables removed from UI per streamline request:
          - Univariate Gini coefficients
          - Mutual information
          - Highly correlated pairs
          - VIF table
          All metrics continue computing server-side and appear in CSV exports. */}

      {/* Information value table and WOE Transformation Details removed from UI per streamline request.
          All IV and WOE metrics continue computing server-side and appear in CSV exports. */}

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <h2 className="text-base font-semibold">🔗 Interaction Terms Generated</h2>
        {interactionFeatures.length > 0 ? (
          <>
            <p className="mt-1 text-xs text-muted-foreground">
              IV and Gini are each interaction's own predictive power — the metrics that let it pass evaluation
              (min IV, redundancy filtering) — not a lift over the source features alone.
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="border-b border-border px-3 py-2">#</th>
                    <th className="border-b border-border px-3 py-2">Feature A</th>
                    <th className="border-b border-border px-3 py-2">Feature B</th>
                    <th className="border-b border-border px-3 py-2">Type</th>
                    <th className="border-b border-border px-3 py-2">IV</th>
                    <th className="border-b border-border px-3 py-2">Gini</th>
                    <th className="border-b border-border px-3 py-2">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {[...interactionFeatures]
                    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
                    .map((f, idx) => (
                      <tr key={f.name ?? idx} className="odd:bg-background">
                        <td className="border-b border-border px-3 py-2 font-mono text-xs text-muted-foreground">{idx + 1}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{f.feature_a}</td>
                        <td className="border-b border-border px-3 py-2 font-mono text-xs">{f.feature_b}</td>
                        <td className="border-b border-border px-3 py-2 text-xs">{f.interaction_type ?? f.type ?? "—"}</td>
                        <td className="border-b border-border px-3 py-2 text-xs">{f.score !== undefined ? f.score.toFixed(4) : "—"}</td>
                        <td className="border-b border-border px-3 py-2 text-xs">{f.gini !== undefined && f.gini !== null ? f.gini.toFixed(4) : "—"}</td>
                        <td className="border-b border-border px-3 py-2 text-xs capitalize">{f.source ?? "ranked"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">No interaction terms passed evaluation for this dataset.</p>
        )}
      </section>

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

      {(engineeringResult.final_engineered_dataset_preview && Array.isArray(engineeringResult.final_engineered_dataset_preview) && engineeringResult.final_engineered_dataset_preview.length > 0) || (engineeringResult.x_engineered_preview && Array.isArray(engineeringResult.x_engineered_preview) && engineeringResult.x_engineered_preview.length > 0) ? (
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
                  <th className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">#</th>
                  {Object.keys((engineeringResult.final_engineered_dataset_preview && Array.isArray(engineeringResult.final_engineered_dataset_preview) && engineeringResult.final_engineered_dataset_preview.length > 0 ? engineeringResult.final_engineered_dataset_preview : engineeringResult.x_engineered_preview ?? [])[0] ?? {}).map((key: string) => (
                    <th key={key} className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground">{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(engineeringResult.final_engineered_dataset_preview && Array.isArray(engineeringResult.final_engineered_dataset_preview) && engineeringResult.final_engineered_dataset_preview.length > 0 ? engineeringResult.final_engineered_dataset_preview : engineeringResult.x_engineered_preview ?? []).map((row: any, rowIndex: number) => (
                  <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : ""}>
                    <td className="border-b border-border px-3 py-2 font-mono text-xs text-muted-foreground">{rowIndex + 1}</td>
                    {Object.values(row).map((cell: any, cellIndex: number) => (
                      <td key={cellIndex} className="border-b border-border px-3 py-2 font-mono text-xs">{String(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition hover:border-primary hover:bg-primary-soft"
          onClick={downloadDecisionLog}
        >
          <Download className="h-4 w-4" />
          Download feature decision log
        </button>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition hover:border-primary hover:bg-primary-soft"
          onClick={() => navigate("/preprocessing")}
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Preprocessing
        </button>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
          onClick={async () => {
            try {
              await navigate({ to: "/training" });
            } catch (err) {
              console.error("Navigation failed:", err);
            }
          }}
        >
          Proceed to Model Training
          <ArrowRight className="h-4 w-4" />
        </button>
      </section>
    </div>
  );
}
