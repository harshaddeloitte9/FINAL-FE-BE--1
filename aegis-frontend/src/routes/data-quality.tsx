import * as React from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, ArrowRight, Database, UploadCloud } from "lucide-react";
import { PageHeader } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { useDataset } from "@/lib/app-context";
import { DatasetHealthStrip } from "@/components/data-quality/dataset-health-strip";
import { QualityDimensionsPanel } from "@/components/data-quality/quality-dimensions-panel";
import { TargetClassBalance } from "@/components/data-quality/target-class-balance";
import { IssuesTable } from "@/components/data-quality/issues-table";
import { ColumnDiagnosticsTable } from "@/components/data-quality/column-diagnostics-table";
import { ColumnDetailPanel } from "@/components/data-quality/column-detail-panel";
import { getRows, getCols } from "@/components/data-quality/selectors";

export const Route = createFileRoute("/data-quality")({
  head: () => ({ meta: [{ title: "Data Quality & Dataset Health — Aegis Credit" }] }),
  component: DataQuality,
});

// Stage 2 of the Development pipeline (Data Upload -> Data Quality -> Data
// Preparation & Feature Engineering -> ...). This page answers "can I trust
// this dataset?" using ONLY the profile the existing POST /data/upload
// endpoint already returns (ds.profile) — it makes no API calls of its own,
// duplicates no backend calculation, and fabricates no data. Remediation
// stays out of scope here; every actionable item links back to Data
// Preparation, which continues to answer "how should I fix it?".
function DataQuality() {
  const { profile, file } = useDataset();
  const navigate = useNavigate();
  const [selectedColumn, setSelectedColumn] = React.useState<string | null>(null);

  if (!profile) {
    return (
      <div className="space-y-8">
        <PageHeader title="Data Quality & Dataset Health" description="Assess dataset quality before preparation and modeling." />
        <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 px-6 py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-600">
            <Database className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">Upload a dataset to begin Data Quality assessment.</h3>
            <p className="mx-auto mt-1.5 max-w-md text-sm text-slate-500">
              This page reads the profile produced when a dataset is uploaded. Go to Data Upload to select or upload a dataset first.
            </p>
          </div>
          <Link
            to="/data-upload"
            className="mt-2 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          >
            <UploadCloud className="h-4 w-4" />
            Go to Data Upload
          </Link>
        </div>
      </div>
    );
  }

  const rows = getRows(profile);
  const cols = getCols(profile);
  const datasetName = profile.dataset_name ?? file?.name ?? "Uploaded dataset";
  const targetCol = profile.target_col ?? null;
  const taskType = profile.task_type ?? null;
  const taskLabel =
    taskType === "binary" ? "Binary classification" : taskType === "multiclass" ? "Multiclass classification" : taskType === "regression" ? "Regression" : "—";

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <PageHeader title="Data Quality & Dataset Health" description="Assess dataset quality before preparation and modeling." />

      {/* ── Hero — dataset identity is the headline here, the same way
          Data Preparation's own hero leads with the dataset name rather
          than repeating the page title. Rows/columns/target/task, which
          previously lived in a separate "Dataset Summary" card below,
          are consolidated into the hero badges so the page doesn't carry
          two cards saying the same thing. ─────────────────────────────── */}
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-900 via-sky-900 to-blue-800 p-6 text-white shadow-[0_16px_36px_rgba(15,23,42,0.16)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-200">Stage 2 · Data Quality</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">{datasetName}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-200">
              Independently assess whether this dataset can be trusted, using the completeness, uniqueness, target, leakage, date, and
              compliance signals Aegis already computes — before it moves into Data Preparation.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {rows !== null && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold">
                {rows.toLocaleString()} rows
              </span>
            )}
            {cols !== null && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold">
                {cols} columns
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold">
              Target: {targetCol ?? "Not resolved"}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300/40 bg-emerald-400/15 px-3 py-1 text-xs font-semibold text-emerald-100">
              {taskLabel}
            </span>
          </div>
        </div>
      </div>

      {/* ── Dataset health / quality KPI strip ───────────────────────── */}
      <DatasetHealthStrip profile={profile} />

      {/* ── Quality dimensions + target class balance — items-start so a
          shorter Target Class Balance card never gets stretched into a
          tall block of empty space to match its taller sibling. ────────── */}
      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-2">
        <QualityDimensionsPanel profile={profile} />
        <TargetClassBalance profile={profile} />
      </div>

      {/* ── Issues requiring attention ────────────────────────────────── */}
      <IssuesTable profile={profile} />

      {/* ── Column diagnostics + drill-down — stacked below xl so the
          table always gets the full content width up to that point
          (this is the section that was visibly cramped before), and only
          splits into a side-by-side layout once there's genuinely enough
          room for both. ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[2fr_1fr]">
        <ColumnDiagnosticsTable profile={profile} selectedColumn={selectedColumn} onSelectColumn={setSelectedColumn} />
        <ColumnDetailPanel profile={profile} column={selectedColumn} />
      </div>

      {/* ── Navigation — same Button component and Back/Continue pairing
          Data Preparation's own action bar uses. ────────────────────────── */}
      <div className="flex gap-3 pb-2">
        <Button variant="outline" onClick={() => navigate({ to: "/data-upload" })} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back to Data Upload
        </Button>
        <Button onClick={() => navigate({ to: "/data-preparation" })} className="ml-auto gap-2">
          Continue to Data Preparation
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
