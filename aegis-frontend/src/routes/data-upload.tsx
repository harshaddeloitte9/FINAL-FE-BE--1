import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { UploadCloud, FileSpreadsheet, Sparkles, CheckCircle2, ArrowRight } from "lucide-react";
import { useRef, useState } from "react";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/data-upload")({
  head: () => ({ meta: [{ title: "Data Upload — Aegis Credit" }] }),
  component: DataUpload,
});

function DataUpload() {
  const [progress, setProgress] = useState(0);
  const [file, setFile] = useState<{ name: string; size: string; rows?: number } | null>(null);
  const { setUploadResult, profile } = useDataset();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const uploadFile = async (f: File | null) => {
    if (!f) return;
    setFile({ name: f.name, size: `${(f.size / (1024 * 1024)).toFixed(1)} MB` });
    setProgress(0);
    const t = setInterval(() => setProgress((p) => Math.min(90, p + 6)), 120);
    try {
      const form = new FormData();
      form.append("file", f);
      console.log("DataUpload: sending POST to /data/upload", { filename: f.name, size: f.size });
      const profile = await formUpload("/data/upload", form);
      console.log("DataUpload: received profile", profile);
      setProgress(100);
      setUploadResult(f, profile as any);
      if (profile && (profile as any).shape) {
        const rows = (profile as any).shape?.[0];
        setFile((prev) => (prev ? { ...prev, rows } : prev));
      }
    } catch (err) {
      setProgress(0);
      console.error("DataUpload: upload failed", err);
    } finally {
      clearInterval(t);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Data Upload"
        description="Bring in loan tape, exposure, or scoring datasets. CSV and XLSX up to 5 GB."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div
          className="lg:col-span-2 group relative cursor-pointer rounded-2xl border-2 border-dashed border-border bg-card p-10 text-center transition-colors hover:border-primary/60 hover:bg-primary/5"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) uploadFile(f);
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            className="hidden"
            onChange={(e) => uploadFile(e.target.files?.[0] ?? null)}
          />
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl gradient-primary shadow-elegant transition-transform group-hover:scale-105">
            <UploadCloud className="h-8 w-8 text-primary-foreground" />
          </div>
          <h3 className="mt-5 text-lg font-semibold">Drop CSV or XLSX here</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Or click to browse. We'll auto-detect schema and run profiling.
          </p>
          <div className="mt-4 flex justify-center gap-2 text-[11px] text-muted-foreground">
            <span className="rounded-full border border-border bg-background px-2 py-0.5">CSV</span>
            <span className="rounded-full border border-border bg-background px-2 py-0.5">XLSX</span>
            <span className="rounded-full border border-border bg-background px-2 py-0.5">Parquet (beta)</span>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Synthetic dataset</h3>
              <p className="text-xs text-muted-foreground">No data? Generate a realistic loan tape.</p>
            </div>
          </div>
          <ul className="mt-4 space-y-2 text-xs text-muted-foreground">
            <li>· 200k synthetic obligors, balanced default flag</li>
            <li>· IFRS 9 staging, macro overlay variables</li>
            <li>· Geographic + sector segmentation</li>
          </ul>
          <button
            onClick={async () => {
              setProgress(0);
              try {
                const t = setInterval(() => setProgress((p) => Math.min(90, p + 6)), 120);
                const form = new FormData();
                form.append("synthetic_samples", "200000");
                console.log("DataUpload: requesting synthetic dataset generation POST /data/upload", { synthetic_samples: 200000 });
                const profile = await formUpload("/data/upload", form);
                console.log("DataUpload: synthetic profile received", profile);
                clearInterval(t);
                setProgress(100);
                setFile({ name: "synthetic_portfolio.csv", size: "~200 MB", rows: profile?.shape?.[0] ?? undefined });
                setUploadResult(null, profile as any);
              } catch (err) {
                setProgress(0);
                console.error("DataUpload: synthetic generation failed", err);
              }
            }}
            className="mt-5 w-full rounded-lg border border-primary/30 bg-primary-soft px-3 py-2 text-sm font-medium text-foreground hover:bg-primary/20"
          >
            Generate dataset
          </button>
        </div>
      </div>

      {file && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-background">
                <FileSpreadsheet className="h-6 w-6 text-primary" />
              </div>
              <div>
                <div className="font-medium">{file.name}</div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>{file.size}</span>
                  <span>{file.rows ? file.rows.toLocaleString() + " rows · 38 columns" : "— rows · 38 columns"}</span>
                  <span>SHA-256 a4f…b921</span>
                </div>
              </div>
            </div>
            {progress >= 100 && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-foreground">
                <CheckCircle2 className="h-4 w-4 text-primary" /> Ready
              </span>
            )}
          </div>
          <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full gradient-primary transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
            <span>{progress < 100 ? "Uploading and validating schema…" : "Schema validated"}</span>
            <span>{progress}%</span>
          </div>
        </div>
      )}

      {profile && progress >= 100 && (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-elegant">
            <h3 className="text-sm font-semibold">Dataset summary</h3>
            <div className="mt-4 space-y-3 text-sm text-foreground/90">
              <div className="flex items-center justify-between border-b border-border/70 pb-3">
                <span className="text-xs text-muted-foreground">Total rows</span>
                <span className="font-semibold">{profile.shape?.[0]?.toLocaleString() ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between border-b border-border/70 pb-3">
                <span className="text-xs text-muted-foreground">Total columns</span>
                <span className="font-semibold">{profile.shape?.[1]?.toLocaleString() ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between border-b border-border/70 pb-3">
                <span className="text-xs text-muted-foreground">Missing values</span>
                <span className="font-semibold">{profile.missing_cells?.toLocaleString() ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Duplicate rows</span>
                <span className="font-semibold">{profile.duplicate_rows?.toLocaleString() ?? "—"}</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">Preview first {profile.data_preview?.length ?? 0} rows</h3>
                <p className="text-xs text-muted-foreground">Loaded directly from backend response</p>
              </div>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                    {(profile.columns ?? []).slice(0, 10).map((column) => (
                      <th key={column} className="px-2 py-2">{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(profile.data_preview ?? []).map((row, rowIndex) => (
                    <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : "bg-card"}>
                      {(profile.columns ?? []).slice(0, 10).map((column) => (
                        <td key={`${rowIndex}-${column}`} className="whitespace-nowrap px-2 py-2 text-xs text-foreground/90">
                          {row[column] ?? ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {file && progress >= 100 && (
        <div className="flex justify-end gap-3 pt-4">
          <Button onClick={() => navigate({ to: "/profiling" })} className="gap-2">
            Proceed to Profiling
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
