import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowRight, CheckCircle2, Database, Download, FileSpreadsheet, Info, Landmark, Link2, ShieldCheck, Table2, TrendingUp, Upload,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/data-upload")({
  head: () => ({ meta: [{ title: "Data Upload — Aegis Credit" }] }),
  component: DataUpload,
});

type TableInfo = {
  table: string;
  row_count: number;
  columns: { name: string; dtype: string; unique_ratio_sample: number; sample_values: string[] }[];
};

type JoinCandidate = {
  left_table: string;
  left_column: string;
  right_table: string;
  right_column: string;
  confidence: number;
  cardinality: string;
  reasons: string[];
};

type PrimaryKeyInfo = {
  table: string;
  column: string;
  confidence: number;
  reasons: string[];
};

type ConfirmedJoin = { right_table: string; left_key: string; right_key: string };

async function readCsvHeader(file: File): Promise<string[]> {
  const text = await file.slice(0, 8192).text();
  const firstLine = text.split(/\r?\n/)[0] ?? "";
  return firstLine.split(",").map((c) => c.trim().replace(/^"|"$/g, "")).filter(Boolean);
}

function bestCandidate(candidates: JoinCandidate[], tableA: string, tableB: string): JoinCandidate | null {
  const found = candidates.find(
    (c) => (c.left_table === tableA && c.right_table === tableB) || (c.left_table === tableB && c.right_table === tableA),
  );
  if (!found) return null;
  // Normalize so left = tableA, right = tableB regardless of which order discovery found it in.
  return found.left_table === tableA
    ? found
    : {
        left_table: tableA, left_column: found.right_column, right_table: tableB, right_column: found.left_column,
        confidence: found.confidence, cardinality: found.cardinality, reasons: found.reasons,
      };
}

function DataUpload() {
  const { setUploadResult, profile } = useDataset();
  const navigate = useNavigate();

  const customerInputRef = useRef<HTMLInputElement>(null);
  const dbInputRef = useRef<HTMLInputElement>(null);

  const [customerFile, setCustomerFile] = useState<File | null>(null);
  const [customerColumns, setCustomerColumns] = useState<string[]>([]);

  const [dbFile, setDbFile] = useState<File | null>(null);
  const [dbTables, setDbTables] = useState<TableInfo[] | null>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState<string | null>(null);

  const [loanTable, setLoanTable] = useState<string>("");
  const [collateralTable, setCollateralTable] = useState<string>("");
  const [fetchMacro, setFetchMacro] = useState(true);
  const [fredApiKey, setFredApiKey] = useState("");

  const [candidates, setCandidates] = useState<JoinCandidate[]>([]);
  const [primaryKeys, setPrimaryKeys] = useState<PrimaryKeyInfo[]>([]);
  const [relLoading, setRelLoading] = useState(false);
  const [relError, setRelError] = useState<string | null>(null);

  const [customerLoanJoin, setCustomerLoanJoin] = useState<{ left: string; right: string } | null>(null);
  const [loanCollateralJoin, setLoanCollateralJoin] = useState<{ left: string; right: string } | null>(null);

  const [integrating, setIntegrating] = useState(false);
  const [integrateError, setIntegrateError] = useState<string | null>(null);
  const [report, setReport] = useState<any | null>(null);

  const loanColumns = useMemo(() => dbTables?.find((t) => t.table === loanTable)?.columns.map((c) => c.name) ?? [], [dbTables, loanTable]);
  const collateralColumns = useMemo(() => dbTables?.find((t) => t.table === collateralTable)?.columns.map((c) => c.name) ?? [], [dbTables, collateralTable]);

  const onCustomerFileChosen = async (f: File | null) => {
    if (!f) return;
    setCustomerFile(f);
    setReport(null);
    try {
      setCustomerColumns(await readCsvHeader(f));
    } catch {
      setCustomerColumns([]);
    }
    if (dbTables) void discoverRelationships(f, dbFile, loanTable, collateralTable);
  };

  const onDbFileChosen = async (f: File | null) => {
    if (!f) return;
    setDbFile(f);
    setDbError(null);
    setDbLoading(true);
    setReport(null);
    try {
      const form = new FormData();
      form.append("db_file", f);
      const resp = await formUpload<{ tables: TableInfo[] }>("/data/integration/sqlite/inspect", form);
      setDbTables(resp.tables);
      const guessLoan = resp.tables.find((t) => /loan/i.test(t.table))?.table ?? resp.tables[0]?.table ?? "";
      const guessCollateral = resp.tables.find((t) => /collateral/i.test(t.table))?.table ?? "";
      setLoanTable(guessLoan);
      setCollateralTable(guessCollateral);
      if (customerFile) void discoverRelationships(customerFile, f, guessLoan, guessCollateral);
    } catch (error: any) {
      setDbTables(null);
      setDbError(error?.message ?? "Failed to read the SQLite database.");
    } finally {
      setDbLoading(false);
    }
  };

  const discoverRelationships = async (custFile: File | null, database: File | null, loan: string, collateral: string) => {
    const selected = [loan, collateral].filter(Boolean);
    if (!custFile || !database || selected.length === 0) return;
    setRelLoading(true);
    setRelError(null);
    try {
      const form = new FormData();
      form.append("customer_file", custFile);
      form.append("db_file", database);
      form.append("selected_tables", selected.join(","));
      const resp = await formUpload<{ primary_keys: PrimaryKeyInfo[]; candidates: JoinCandidate[] }>("/data/integration/relationships", form);
      setCandidates(resp.candidates);
      setPrimaryKeys(resp.primary_keys ?? []);

      const cl = loan ? bestCandidate(resp.candidates, "customer", loan) : null;
      setCustomerLoanJoin(cl ? { left: cl.left_column, right: cl.right_column } : null);

      const lc = loan && collateral ? bestCandidate(resp.candidates, loan, collateral) : null;
      setLoanCollateralJoin(lc ? { left: lc.left_column, right: lc.right_column } : null);
    } catch (error: any) {
      setRelError(error?.message ?? "Failed to discover relationships between sources.");
      setCandidates([]);
      setPrimaryKeys([]);
    } finally {
      setRelLoading(false);
    }
  };

  const onLoanTableChange = (t: string) => {
    setLoanTable(t);
    if (customerFile && dbFile) void discoverRelationships(customerFile, dbFile, t, collateralTable);
  };
  const onCollateralTableChange = (t: string) => {
    setCollateralTable(t);
    if (customerFile && dbFile) void discoverRelationships(customerFile, dbFile, loanTable, t);
  };

  const canIntegrate = Boolean(customerFile) && (!loanTable || Boolean(customerLoanJoin)) && (!collateralTable || Boolean(loanCollateralJoin));

  const runIntegration = async () => {
    if (!customerFile) return;
    setIntegrating(true);
    setIntegrateError(null);
    try {
      const joinSpecs: ConfirmedJoin[] = [];
      if (loanTable && customerLoanJoin) {
        joinSpecs.push({ right_table: loanTable, left_key: customerLoanJoin.left, right_key: customerLoanJoin.right });
      }
      if (collateralTable && loanCollateralJoin) {
        joinSpecs.push({ right_table: collateralTable, left_key: loanCollateralJoin.left, right_key: loanCollateralJoin.right });
      }

      const form = new FormData();
      form.append("customer_file", customerFile);
      if (dbFile) form.append("db_file", dbFile);
      if (loanTable) form.append("loan_table", loanTable);
      if (collateralTable) form.append("collateral_table", collateralTable);
      form.append("join_specs_json", JSON.stringify(joinSpecs));
      form.append("fetch_macro", String(fetchMacro));
      if (fetchMacro && fredApiKey.trim()) form.append("fred_api_key", fredApiKey.trim());

      const resp = await formUpload<any>("/data/integration/run", form);
      setReport(resp);

      const datasetName = resp?.dataset_name ?? "integrated_dataset.csv";
      const resolvedFile = typeof resp?.csv_text === "string"
        ? new File([resp.csv_text], datasetName.endsWith(".csv") ? datasetName : `${datasetName}.csv`, { type: "text/csv" })
        : null;
      setUploadResult(resolvedFile, resp as any);
    } catch (error: any) {
      setIntegrateError(error?.message ?? "Integration failed.");
    } finally {
      setIntegrating(false);
    }
  };

  const downloadReport = () => {
    if (!report?.integration_report) return;
    const blob = new Blob([JSON.stringify(report.integration_report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "integration_report.json";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const integrationReport = report?.integration_report;

  return (
    <div className="space-y-6">
      <div className="rounded-xl border-l-4 border-primary bg-card px-4 py-3 shadow-elegant">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80">
            <Link2 className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-semibold tracking-tight">Step 1 — Data Integration</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Combine customer, loan, collateral, and macroeconomic data into a single modelling dataset.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Customer data */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-elegant">
          <input ref={customerInputRef} type="file" accept=".csv" className="hidden" onChange={(e) => void onCustomerFileChosen(e.target.files?.[0] ?? null)} />
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
            <h4 className="text-sm font-semibold">CSV file</h4>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">The base table every other source joins onto.</p>
          <button
            type="button"
            onClick={() => customerInputRef.current?.click()}
            className="mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:border-primary/40 hover:bg-primary-soft"
          >
            {customerFile ? customerFile.name : "Upload CSV"}
          </button>
          {customerFile ? (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-600">
              <CheckCircle2 className="h-3.5 w-3.5" /> {customerColumns.length} columns detected
            </div>
          ) : null}
        </div>

        {/* SQLite database */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-elegant">
          <input ref={dbInputRef} type="file" accept=".db,.sqlite,.sqlite3" className="hidden" onChange={(e) => void onDbFileChosen(e.target.files?.[0] ?? null)} />
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-muted-foreground" />
            <h4 className="text-sm font-semibold">Database</h4>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">SQLite database — tables are discovered automatically.</p>
          <button
            type="button"
            onClick={() => dbInputRef.current?.click()}
            className="mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:border-primary/40 hover:bg-primary-soft"
          >
            {dbLoading ? "Reading database…" : dbFile ? dbFile.name : "Upload SQLite database (.db)"}
          </button>
          {dbError ? <div className="mt-2 text-xs text-red-500">{dbError}</div> : null}

          {dbTables ? (
            <div className="mt-4 space-y-3">
              <label className="block text-xs font-medium text-foreground">
                Loan table
                <select value={loanTable} onChange={(e) => onLoanTableChange(e.target.value)} className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm">
                  <option value="">— none —</option>
                  {dbTables.map((t) => <option key={t.table} value={t.table}>{t.table} ({t.row_count} rows)</option>)}
                </select>
              </label>
              <label className="block text-xs font-medium text-foreground">
                Collateral table <span className="text-muted-foreground">(optional)</span>
                <select value={collateralTable} onChange={(e) => onCollateralTableChange(e.target.value)} className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm">
                  <option value="">— none —</option>
                  {dbTables.map((t) => <option key={t.table} value={t.table}>{t.table} ({t.row_count} rows)</option>)}
                </select>
              </label>
            </div>
          ) : null}
        </div>

        {/* Macro data */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-elegant md:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-muted-foreground" />
              <div>
                <h4 className="text-sm font-semibold">Macroeconomic data</h4>
                <p className="text-xs text-muted-foreground">Fetched automatically from FRED and aligned by observation date — no entity key needed.</p>
              </div>
            </div>
            <label className="flex shrink-0 cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={fetchMacro} onChange={(e) => setFetchMacro(e.target.checked)} className="h-4 w-4 accent-primary" />
              Fetch from FRED
            </label>
          </div>
          {fetchMacro ? (
            <div className="mt-3">
              <label className="block text-xs font-medium text-foreground">
                FRED API key
                <input
                  type="password"
                  value={fredApiKey}
                  onChange={(e) => setFredApiKey(e.target.value)}
                  placeholder="Enter your FRED API key"
                  autoComplete="off"
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                Series are aligned to each record's origination date automatically. Get a free key at{" "}
                <a href="https://fred.stlouisfed.org/docs/api/api_key.html" target="_blank" rel="noreferrer" className="underline">
                  fred.stlouisfed.org
                </a>.
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {/* Relationships */}
      {(loanTable || collateralTable) && customerFile && dbFile ? (
        <div className="rounded-xl border border-border bg-card p-5 shadow-elegant">
          {relError ? <p className="mb-3 text-xs text-red-500">{relError}</p> : null}

          <div className="space-y-3">
            {loanTable ? (
              <JoinRow
                leftLabel="customer"
                rightLabel={loanTable}
                leftColumns={customerColumns}
                rightColumns={loanColumns}
                value={customerLoanJoin}
                onChange={setCustomerLoanJoin}
                candidate={bestCandidate(candidates, "customer", loanTable)}
              />
            ) : null}
            {loanTable && collateralTable ? (
              <JoinRow
                leftLabel={loanTable}
                rightLabel={collateralTable}
                leftColumns={loanColumns}
                rightColumns={collateralColumns}
                value={loanCollateralJoin}
                onChange={setLoanCollateralJoin}
                candidate={bestCandidate(candidates, loanTable, collateralTable)}
              />
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button onClick={runIntegration} disabled={!canIntegrate || integrating} className="gap-2">
          {integrating ? "Integrating…" : "Integrate sources"}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
      {integrateError ? <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{integrateError}</div> : null}

      {/* Loaded sources + integration preview */}
      {integrationReport ? (
        <>
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-muted-foreground" />
              <h3 className="text-sm font-semibold">Loaded sources</h3>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
              {integrationReport.sources.map((s: any) => (
                <div key={s.name} className="rounded-lg border border-border bg-background px-3 py-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {s.name}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{s.rows.toLocaleString()} rows · {s.columns} cols</div>
                </div>
              ))}
              {integrationReport.macro_series?.length ? (
                <div className="rounded-lg border border-border bg-background px-3 py-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
                    <CheckCircle2 className="h-3.5 w-3.5" /> FRED
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{integrationReport.macro_series.join(", ")}</div>
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Landmark className="h-5 w-5 text-muted-foreground" />
                <h3 className="text-sm font-semibold">Integrated dataset</h3>
              </div>
              <button type="button" onClick={downloadReport} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted">
                <Download className="h-3.5 w-3.5" /> Integration report
              </button>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <Stat label="Rows" value={integrationReport.rows_after.toLocaleString()} />
              <Stat label="Columns" value={integrationReport.columns_after.toLocaleString()} />
              <Stat label="Sources" value={String(integrationReport.sources.length + (integrationReport.macro_series?.length ? 1 : 0))} />
            </div>
            {integrationReport.warnings?.length ? (
              <div className="mt-4 space-y-1.5">
                {integrationReport.warnings.map((w: string, i: number) => (
                  <div key={i} className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">{w}</div>
                ))}
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      {profile ? (
        <>
          <div className="rounded-xl border border-border bg-card p-6 shadow-elegant">
            <div className="flex items-center gap-2">
              <Table2 className="h-5 w-5 text-muted-foreground" />
              <h3 className="text-sm font-semibold">Dataset preview</h3>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-2 py-2">#</th>
                    {(profile.columns ?? []).map((column) => (
                      <th key={column} className="px-2 py-2">{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(profile.data_preview ?? []).map((row: Record<string, any>, rowIndex: number) => (
                    <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : "bg-card"}>
                      <td className="whitespace-nowrap px-2 py-2 text-xs text-muted-foreground">{rowIndex + 1}</td>
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
            <h4 className="text-sm font-semibold">Welcome to Aegis Credit</h4>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Upload customer data, connect a loan/collateral database, and optionally attach FRED macro data — the
            platform discovers how they relate and builds one integrated dataset for modelling.
          </p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/50 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
    </div>
  );
}

function JoinRow({
  leftLabel, rightLabel, leftColumns, rightColumns, value, onChange, candidate,
}: {
  leftLabel: string;
  rightLabel: string;
  leftColumns: string[];
  rightColumns: string[];
  value: { left: string; right: string } | null;
  onChange: (v: { left: string; right: string }) => void;
  candidate?: JoinCandidate | null;
}) {
  return (
    <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-foreground">{leftLabel}</span>
        <select
          value={value?.left ?? ""}
          onChange={(e) => onChange({ left: e.target.value, right: value?.right ?? "" })}
          className="rounded-md border border-input bg-background px-2 py-1 text-xs"
        >
          <option value="">select column</option>
          {leftColumns.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-medium text-foreground">{rightLabel}</span>
        <select
          value={value?.right ?? ""}
          onChange={(e) => onChange({ left: value?.left ?? "", right: e.target.value })}
          className="rounded-md border border-input bg-background px-2 py-1 text-xs"
        >
          <option value="">select column</option>
          {rightColumns.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {candidate ? (
          <span className="ml-auto flex shrink-0 items-center gap-1.5">
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              {candidate.cardinality}
            </span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              {Math.round(candidate.confidence * 100)}% confidence
            </span>
          </span>
        ) : (
          <span className="ml-auto shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
            no suggestion — select manually
          </span>
        )}
      </div>
      {candidate?.reasons?.length ? (
        <ul className="mt-1.5 space-y-0.5 pl-1 text-[11px] text-muted-foreground">
          {candidate.reasons.map((r, i) => (
            <li key={i}>— {r}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
