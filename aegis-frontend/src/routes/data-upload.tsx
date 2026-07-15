import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AlertCircle, ArrowRight, CheckCircle2, Cloud, Database, FileSpreadsheet, Folder, Globe2, HardDrive, Info, Sparkles, Table2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/data-upload")({
  head: () => ({ meta: [{ title: "Data Upload — Aegis Credit" }] }),
  component: DataUpload,
});

function DataUpload() {
  const [dataSourceType, setDataSourceType] = useState("upload");
  const [syntheticSamples, setSyntheticSamples] = useState(2000);
  const [apiUrl, setApiUrl] = useState("");
  const [apiMethod, setApiMethod] = useState("GET");
  const [isFetchingApi, setIsFetchingApi] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [uploadSummary, setUploadSummary] = useState<{
    kind: "file" | "synthetic";
    name: string;
    rows: number;
    cols: number;
  } | null>(null);
  const { setUploadResult, profile } = useDataset();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const dataSourceOptions = [
    { value: "upload", label: "Upload File (CSV / XLSX)", icon: Upload },
    { value: "database", label: "Database Connection", icon: Database },
    { value: "api", label: "API Endpoint", icon: Globe2 },
    { value: "cloud", label: "Cloud Storage (S3 / Azure Blob)", icon: Cloud },
    { value: "sftp", label: "SFTP / File Server", icon: HardDrive },
  ];

  const applyUploadResult = (uploadedFile: File | null, response: any) => {
    const datasetName = response?.dataset_name ?? uploadedFile?.name ?? "Synthetic Credit Dataset.csv";
    const resolvedFile = uploadedFile
      ?? (typeof response?.csv_text === "string"
        ? new File([response.csv_text], datasetName.endsWith(".csv") ? datasetName : `${datasetName}.csv`, { type: "text/csv" })
        : null);

    setUploadResult(resolvedFile, response as any);

    const rows = Array.isArray(response?.shape) ? Number(response.shape[0] ?? 0) : 0;
    const cols = Array.isArray(response?.shape) ? Number(response.shape[1] ?? 0) : 0;
    setUploadSummary({
      kind: response?.source_type === "synthetic" ? "synthetic" : "file",
      name: datasetName,
      rows,
      cols,
    });
  };

  const uploadFile = async (f: File | null) => {
    if (!f) return;
    try {
      const form = new FormData();
      form.append("file", f);
      console.log("DataUpload: sending POST to /data/upload", { filename: f.name, size: f.size });
      const profile = await formUpload("/data/upload", form);
      console.log("DataUpload: received profile", profile);
      applyUploadResult(f, profile);
    } catch (err) {
      console.error("DataUpload: upload failed", err);
    }
  };

  const fetchApiData = async () => {
    if (!apiUrl.trim()) {
      setApiError("API URL is required.");
      return;
    }

    setApiError(null);
    setIsFetchingApi(true);
    try {
      const form = new FormData();
      form.append("api_url", apiUrl.trim());
      form.append("http_method", apiMethod);
      console.log("DataUpload: sending POST to /data/api", { api_url: apiUrl.trim(), http_method: apiMethod });
      const profile = await formUpload("/data/api", form);
      console.log("DataUpload: received API profile", profile);
      applyUploadResult(null, profile);
    } catch (err) {
      console.error("DataUpload: API fetch failed", err);
      setApiError(err instanceof Error ? err.message : "Failed to fetch data from API.");
    } finally {
      setIsFetchingApi(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border-l-4 border-primary bg-card px-4 py-3 shadow-elegant">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
            <Folder className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-semibold tracking-tight">Step 1 — Data Upload</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload a CSV or Excel file, or use the built-in synthetic credit dataset
            </p>
          </div>
        </div>
      </div>

      <div>
        <h4 className="text-sm font-semibold text-foreground">Data Source</h4>
        <div className="mt-4 space-y-3">
          {dataSourceOptions.map((option) => {
            const Icon = option.icon;
            return (
              <label
                key={option.value}
                className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-sm shadow-elegant"
              >
                <input
                  type="radio"
                  name="data-source-type"
                  value={option.value}
                  checked={dataSourceType === option.value}
                  onChange={() => setDataSourceType(option.value)}
                  className="h-4 w-4 accent-primary"
                />
                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background/80">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                </div>
                <span className="font-medium text-foreground">{option.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {dataSourceType === "upload" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <input ref={inputRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={(e) => uploadFile(e.target.files?.[0] ?? null)} />
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
                <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-foreground">Upload your dataset (CSV / XLSX)</label>
                <p className="text-xs text-muted-foreground">The system adapts automatically to any structured dataset schema.</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="inline-flex items-center justify-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:border-primary/40 hover:bg-primary-soft"
              >
                Browse files
              </button>
              <span className="inline-flex items-center rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                CSV / XLSX
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
                <Sparkles className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-sm font-semibold">Synthetic dataset</h3>
                <p className="text-xs text-muted-foreground">No data? Generate a realistic loan tape.</p>
              </div>
            </div>
            <button
              type="button"
              onClick={async () => {
                try {
                  const form = new FormData();
                  form.append("synthetic_samples", String(syntheticSamples));
                  console.log("DataUpload: requesting synthetic dataset generation POST /data/upload", { synthetic_samples: syntheticSamples });
                  const result = await formUpload("/data/upload", form);
                  console.log("DataUpload: synthetic profile received", result);
                  applyUploadResult(null, result);
                } catch (err) {
                  console.error("DataUpload: synthetic generation failed", err);
                }
              }}
              className="mt-5 w-full rounded-lg border border-primary/30 bg-primary-soft px-3 py-2 text-sm font-medium text-foreground hover:bg-primary/20"
            >
              Use Synthetic Dataset
            </button>
            <label className="mt-4 block text-xs text-muted-foreground">
              Synthetic samples
              <input
                type="number"
                min={500}
                max={50000}
                step={500}
                value={syntheticSamples}
                onChange={(e) => setSyntheticSamples(Number(e.target.value) || 2000)}
                className="mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary/60"
              />
            </label>
          </div>
        </div>
      ) : dataSourceType === "database" ? (
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
              <Database className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <div className="font-semibold text-foreground">Database connection setup</div>
              <div className="mt-2 text-sm text-muted-foreground">Database connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow — connection logic will be added once the target database and credentials are confirmed.</div>
            </div>
          </div>
          <button type="button" disabled className="mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground">
            Connect &amp; Pull Data
          </button>
        </div>
      ) : dataSourceType === "api" ? (
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
              <Globe2 className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">API endpoint</div>
              <div className="mt-2 text-sm text-muted-foreground">Fetch a CSV dataset directly from a remote API.</div>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <label className="block text-sm font-medium text-foreground">
              API URL
              <input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://example.com/data.csv"
                className="mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary/60"
              />
            </label>

            <label className="block text-sm font-medium text-foreground">
              HTTP Method
              <select
                value={apiMethod}
                onChange={(e) => setApiMethod(e.target.value)}
                className="mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary/60"
              >
                <option value="GET">GET</option>
              </select>
            </label>

            {apiError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {apiError}
              </div>
            ) : null}

            <button
              type="button"
              onClick={fetchApiData}
              disabled={isFetchingApi}
              className="mt-2 w-full rounded-lg border border-primary/30 bg-primary-soft px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isFetchingApi ? "Fetching…" : "Fetch Data"}
            </button>
          </div>
        </div>
      ) : dataSourceType === "cloud" ? (
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
              <Cloud className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">Cloud storage connection setup</div>
              <div className="mt-2 text-sm text-muted-foreground">Cloud storage connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow.</div>
            </div>
          </div>
          <button type="button" disabled className="mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground">
            Load from Cloud
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
              <HardDrive className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">SFTP / File Server connection setup</div>
              <div className="mt-2 text-sm text-muted-foreground">SFTP connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow — useful for scheduled exports landing in a fixed location.</div>
            </div>
          </div>
          <button type="button" disabled className="mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground">
            Pull from Server
          </button>
        </div>
      )}

      {uploadSummary ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span className="inline-flex items-center gap-2 font-semibold">
            <CheckCircle2 className="h-5 w-5" />
            {uploadSummary.kind === "synthetic" ? "Generated synthetic dataset" : `Loaded ${uploadSummary.name}`}
          </span>
          <span className="ml-2">
            — {uploadSummary.rows.toLocaleString()} rows × {uploadSummary.cols.toLocaleString()} columns
          </span>
        </div>
      ) : null}

      {profile ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-border bg-card p-4 shadow-elegant">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                <Table2 className="h-4 w-4" />
                <span>Rows</span>
              </div>
              <div className="mt-2 text-2xl font-semibold tabular-nums">{profile.shape?.[0]?.toLocaleString() ?? "—"}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 shadow-elegant">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                <Table2 className="h-4 w-4" />
                <span>Columns</span>
              </div>
              <div className="mt-2 text-2xl font-semibold tabular-nums">{profile.shape?.[1]?.toLocaleString() ?? "—"}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 shadow-elegant">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                <AlertCircle className="h-4 w-4" />
                <span>Missing Values</span>
              </div>
              <div className="mt-2 text-2xl font-semibold tabular-nums">{profile.missing_cells?.toLocaleString() ?? "—"}</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 shadow-elegant">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                <Table2 className="h-4 w-4" />
                <span>Duplicates</span>
              </div>
              <div className="mt-2 text-2xl font-semibold tabular-nums">{profile.duplicate_rows?.toLocaleString() ?? "—"}</div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-2">
              <Table2 className="h-5 w-5 text-muted-foreground" />
              <h3 className="text-sm font-semibold">Dataset Preview</h3>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                    {(profile.columns ?? []).map((column) => (
                      <th key={column} className="px-2 py-2">{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(profile.data_preview ?? []).map((row: Record<string, any>, rowIndex: number) => (
                    <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : "bg-card"}>
                      {(profile.columns ?? []).map((column) => (
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

          <div className="flex justify-end gap-3 pt-4">
            <Button onClick={() => navigate({ to: "/profiling" })} className="gap-2">
              Proceed to Data Profiling
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </>
      ) : (
        <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-muted-foreground" />
            <h4 className="text-sm font-semibold">Welcome to CreditRisk ML POC</h4>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            This platform intelligently adapts to <strong>any structured dataset</strong> — no hardcoded columns required.
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Upload your own CSV/XLSX file, or</li>
            <li>Click <strong>Use Synthetic Dataset</strong> to explore with demo data</li>
          </ul>
        </div>
      )}
    </div>
  );
}
