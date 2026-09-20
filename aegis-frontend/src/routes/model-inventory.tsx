import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PageHeader } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { VCard, VEmptyState } from "@/components/validation-ui";
import {
  ArrowRight,
  Database,
  Download,
  FileText,
  History,
  Plus,
  Search,
  ShieldCheck,
  ListChecks,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";

type InventoryModel = {
  model_id: string;
  model_name: string;
  model_type: string;
  algorithm?: string;
  business_purpose: string;
  model_owner: string;
  business_unit: string;
  model_version: string;
  regulatory_framework: string;
  status: string;
  development_date: string;
  implementation_date?: string;
  last_validation_date?: string;
  next_validation_due?: string;
  model_risk_rating: string;
  approval_status: string;
  reviewer: string;
  created_at: string;
  updated_at: string;
  documentation_url?: string;
  documentation_path?: string;
  document_url?: string;
  document_path?: string;
};

type InventoryDataSource = {
  data_source_id: string;
  model_id: string;
  file_name: string;
  source_type: string;
  purpose: string;
  uploaded_by: string;
  uploaded_at: string;
  record_count?: number;
  column_count?: number;
  target_variable?: string;
  storage_reference?: string;
};

type InventoryValidation = {
  model_id: string;
  data_validation_status: string;
  conceptual_soundness_status: string;
  backtesting_status: string;
  overall_status: string;
  findings_count: number;
  last_validation?: string | null;
};

type InventoryHistoryEntry = {
  model_id: string;
  event: string;
  description: string;
  timestamp: string;
  user: string;
  validation_run_id?: string;
};

type InventoryTab = "development" | "validation";

type InventoryPayload = {
  development: InventoryModel[];
  validation: InventoryModel[];
  models: InventoryModel[];
  data_sources: InventoryDataSource[];
  history: InventoryHistoryEntry[];
};

export const Route = createFileRoute("/model-inventory")({
  head: () => ({ meta: [{ title: "Model Inventory — Aegis Credit" }] }),
  component: ModelInventory,
});

function normalizeInventoryPayload(payload: InventoryPayload): InventoryPayload {
  return {
    ...payload,
    models: payload.models.map((model) => ({
      ...model,
      algorithm: typeof model.algorithm === "string" && model.algorithm.trim() ? model.algorithm.trim() : undefined,
    })),
  };
}

function displayAlgorithm(model: InventoryModel): string {
  return typeof model.algorithm === "string" && model.algorithm.trim() ? model.algorithm.trim() : "—";
}

// Same "blank string -> em dash" treatment displayAlgorithm already used,
// applied to the other free-text inventory fields that are frequently blank
// in real records (business_unit/model_type/model_version/regulatory_framework
// /model_owner) — purely a display fallback, never a fabricated value.
function dash(value: string | null | undefined): string {
  return typeof value === "string" && value.trim() ? value.trim() : "—";
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function getDocumentationReference(model: InventoryModel): string | null {
  const candidates = [
    model.documentation_url,
    model.documentation_path,
    model.document_url,
    model.document_path,
  ];

  for (const candidate of candidates) {
    const value = typeof candidate === "string" ? candidate.trim() : "";
    if (value) {
      return value;
    }
  }

  return null;
}

function resolveDocumentationHref(reference: string | null): string | null {
  if (!reference) return null;
  if (/^https?:\/\//i.test(reference) || reference.startsWith("data:")) {
    return reference;
  }
  const apiBase = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");
  return `${apiBase}/model-inventory/documentation?path=${encodeURIComponent(reference)}`;
}

// Case-insensitive keyword match rather than an exact-value lookup table —
// real inventory records currently carry status values like "In Development"
// and "Under Validation" (and blank strings), but the field is a free-text
// string, not a fixed enum, so this stays honest ("—" for blank, a neutral
// badge for anything unrecognized) without hardcoding an exhaustive list.
function statusTone(status: string): { label: string; classes: string; dot: string } | null {
  const s = status.trim();
  if (!s) return null;
  const lower = s.toLowerCase();
  if (lower.includes("valid") && !lower.includes("under") && !lower.includes("not")) {
    return { label: s, classes: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200", dot: "bg-emerald-500" };
  }
  if (lower.includes("under validation") || lower.includes("in review") || lower.includes("review")) {
    return { label: s, classes: "bg-sky-50 text-sky-700 ring-1 ring-sky-200", dot: "bg-sky-500" };
  }
  if (lower.includes("development")) {
    return { label: s, classes: "bg-violet-50 text-violet-700 ring-1 ring-violet-200", dot: "bg-violet-500" };
  }
  if (lower.includes("fail")) {
    return { label: s, classes: "bg-red-50 text-red-700 ring-1 ring-red-200", dot: "bg-red-500" };
  }
  if (lower.includes("retire") || lower.includes("inactive")) {
    return { label: s, classes: "bg-slate-100 text-slate-600 ring-1 ring-slate-200", dot: "bg-slate-400" };
  }
  return { label: s, classes: "bg-slate-100 text-slate-600 ring-1 ring-slate-200", dot: "bg-slate-400" };
}

function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  if (!tone) return <span className="text-sm text-slate-400">—</span>;
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${tone.classes}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
      {tone.label}
    </span>
  );
}

// model_risk_rating is a free-text field too (real data currently leaves it
// unset for every record) — same tolerant keyword mapping as StatusBadge, so
// "High"/"Critical"/"Medium"/"Low" (the values the create-model flow and the
// existing KPI calc already assume) render with semantic color, and an unset
// or unrecognized value renders as a plain dash rather than a fabricated tier.
function RiskBadge({ tier }: { tier: string | null | undefined }) {
  const s = (tier ?? "").trim();
  if (!s) return <span className="text-sm text-slate-400">—</span>;
  const lower = s.toLowerCase();
  const classes = lower.includes("critical") || lower.includes("high")
    ? "text-red-700 bg-red-50 ring-1 ring-red-200"
    : lower.includes("medium")
      ? "text-amber-700 bg-amber-50 ring-1 ring-amber-200"
      : lower.includes("low")
        ? "text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200"
        : "text-slate-600 bg-slate-100 ring-1 ring-slate-200";
  return <span className={`inline-flex whitespace-nowrap rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${classes}`}>{s}</span>;
}

function ModelInventory() {
  const [inventory, setInventory] = useState<InventoryPayload | null>(null);
  const [activeTab, setActiveTab] = useState<InventoryTab>("development");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [buFilter, setBuFilter] = useState<string | null>(null);
  const [form, setForm] = useState({ model_name: "", model_owner: "", business_unit: "Retail Credit", model_version: "1.0", regulatory_framework: "Internal", model_type: "Probability of Default" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Presentation-only: opens the (unchanged) "Register a model" form in a
  // dialog instead of it always taking up page space, matching the "Create
  // Model" entry point pattern — no new create logic, same handleCreate.
  const [createOpen, setCreateOpen] = useState(false);

  const loadInventory = async () => {
    setError(null);
    try {
      const payload = await api<InventoryPayload>("/model-inventory");
      setInventory(normalizeInventoryPayload(payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load inventory");
    }
  };

  useEffect(() => { void loadInventory(); }, []);

  const loading = inventory === null && error === null;

  const currentRecords = useMemo(() => {
    if (!inventory) return [] as InventoryModel[];
    return activeTab === "development" ? (inventory.development ?? []) : (inventory.validation ?? []);
  }, [inventory, activeTab]);

  const selectedModel = useMemo(() => currentRecords[0] ?? null, [currentRecords]);

  const filteredModels = useMemo(() => {
    if (!currentRecords) return [] as InventoryModel[];
    return currentRecords.filter((m) => {
      const q = search.trim().toLowerCase();
      if (q) {
        const inText = [m.model_name, m.model_type, displayAlgorithm(m), m.model_owner, m.regulatory_framework].join(" ").toLowerCase();
        if (!inText.includes(q)) return false;
      }
      if (statusFilter && m.status !== statusFilter) return false;
      if (buFilter && m.business_unit !== buFilter) return false;
      return true;
    });
  }, [currentRecords, search, statusFilter, buFilter]);

  const summary = useMemo(() => {
    const totals = { total: 0, validated: 0, inReview: 0, highPriority: 0 };
    if (!inventory) return totals;
    const source = activeTab === "development" ? (inventory.development ?? []) : (inventory.validation ?? []);
    totals.total = source.length;
    for (const m of source) {
      if (m.status === "Validated") totals.validated += 1;
      if (m.status === "In Review") totals.inReview += 1;
      if (m.model_risk_rating === "High" || m.model_risk_rating === "Critical") totals.highPriority += 1;
    }
    return totals;
  }, [inventory, activeTab]);

  const hasActiveFilters = Boolean(search.trim() || statusFilter || buFilter);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await api<InventoryModel>("/model-inventory/models", {
        method: "POST",
        body: JSON.stringify({
          model_name: form.model_name,
          model_owner: form.model_owner,
          business_unit: form.business_unit,
          model_version: form.model_version,
          regulatory_framework: form.regulatory_framework,
          model_type: form.model_type,
          status: "Draft",
        }),
      });
      setForm({ model_name: "", model_owner: "", business_unit: "Retail Credit", model_version: "1.0", regulatory_framework: "Internal", model_type: "Probability of Default" });
      await loadInventory();
      if (created.model_id) {
        const next = inventory?.models ?? [];
        const modelEntry = [created, ...next].find((item) => item.model_id === created.model_id);
        if (modelEntry) {
          setInventory((current) => current ? { ...current, models: [modelEntry, ...current.models] } : current);
        }
      }
      setCreateOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create model");
    } finally {
      setSubmitting(false);
    }
  };

  const exportInventory = async () => {
    const res = await fetch(`${import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8001"}/model-inventory/export`);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Export failed");
    }
    const blob = await res.blob();
    if (!blob.size) {
      throw new Error("Export returned an empty file");
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "model_inventory.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const registerModelForm = (
    <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-2">
      <label className="text-sm font-medium text-slate-700">
        Model name
        <input required value={form.model_name} onChange={(e) => setForm((f) => ({ ...f, model_name: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Model owner
        <input value={form.model_owner} onChange={(e) => setForm((f) => ({ ...f, model_owner: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Business unit
        <input value={form.business_unit} onChange={(e) => setForm((f) => ({ ...f, business_unit: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Model version
        <input value={form.model_version} onChange={(e) => setForm((f) => ({ ...f, model_version: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Regulatory framework
        <input value={form.regulatory_framework} onChange={(e) => setForm((f) => ({ ...f, regulatory_framework: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Model type
        <input value={form.model_type} onChange={(e) => setForm((f) => ({ ...f, model_type: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
      </label>
      <DialogFooter className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving…" : (<><Plus className="h-4 w-4" />Save model</>)}
        </Button>
      </DialogFooter>
    </form>
  );

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <PageHeader
        title="Model Inventory"
        description="Centralised register of models, ownership, lifecycle status, validation state and risk classification."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void exportInventory().catch(() => setError("Excel export failed"))}>
              <Download className="h-4 w-4" /> Export Excel
            </Button>
            <Button variant="outline" onClick={() => window.location.assign("/validation/intake")}>
              Open intake <ArrowRight className="h-4 w-4" />
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Create Model
            </Button>
          </div>
        }
      />

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">
            <div className="font-semibold">Unable to load model inventory</div>
            <p className="mt-0.5">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => void loadInventory()}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Retry
          </button>
        </div>
      ) : null}

      {loading ? (
        <VEmptyState icon={RefreshCw} title="Loading model inventory…" description="Fetching the model registry, ownership, lifecycle and validation state." />
      ) : (
        <>
          {/* ── Inventory overview — navy hero band with the real KPI counts,
              matching the gradient hero language used across the redesigned
              validation pages. ─────────────────────────────────────────── */}
          <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-900 via-indigo-900 to-blue-800 p-6 text-white shadow-[0_16px_36px_rgba(15,23,42,0.16)]">
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-indigo-200">Model Risk Management · Aegis</div>
            <h2 className="mt-2 text-lg font-semibold">Inventory Overview</h2>
            <p className="mt-1 text-sm text-slate-300">
              {summary.total} model{summary.total === 1 ? "" : "s"} tracked in the {activeTab === "development" ? "Development" : "Validation"} register.
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { icon: Database, label: "Total Models", value: summary.total, sub: "in registry" },
                { icon: CheckCircle2, label: "Validated", value: summary.validated, sub: "confirmed" },
                { icon: Clock, label: "In Review", value: summary.inReview, sub: "validation in progress" },
                { icon: AlertTriangle, label: "High Priority", value: summary.highPriority, sub: "high risk models" },
              ].map((kpi) => (
                <div key={kpi.label} className="rounded-xl border border-white/10 bg-white/10 px-4 py-3 backdrop-blur-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-300">{kpi.label}</span>
                    <kpi.icon className="h-3.5 w-3.5 shrink-0 text-slate-300" />
                  </div>
                  <div className="mt-1 text-2xl font-bold text-white">{kpi.value}</div>
                  <div className="mt-0.5 text-[11px] text-slate-400">{kpi.sub}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="min-w-0 space-y-6">
            <div className="min-w-0 space-y-6">
              {/* ── Tabs ─────────────────────────────────────────────────── */}
              <div className="flex w-fit items-center gap-1 rounded-lg border border-slate-200 bg-white p-1">
                {([
                  ["development", "Development"],
                  ["validation", "Validation"],
                ] as const).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key)}
                    className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                      activeTab === key ? "bg-[#2f67ff] text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* ── Model registry table ────────────────────────────────── */}
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-3.5">
                  <div className="relative min-w-[200px] max-w-xs flex-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search models, type, owner"
                      className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-sm text-slate-900 placeholder-slate-400 transition focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                    />
                  </div>
                  <select
                    value={statusFilter ?? ""}
                    onChange={(e) => setStatusFilter(e.target.value || null)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 transition focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                  >
                    <option value="">All statuses</option>
                    {inventory && Array.from(new Set(inventory.models.map((m) => m.status).filter(Boolean))).map((s) => (<option key={s} value={s}>{s}</option>))}
                  </select>
                  <select
                    value={buFilter ?? ""}
                    onChange={(e) => setBuFilter(e.target.value || null)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 transition focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                  >
                    <option value="">All business units</option>
                    {inventory && Array.from(new Set(inventory.models.map((m) => m.business_unit).filter(Boolean))).map((b) => (<option key={b} value={b}>{b}</option>))}
                  </select>
                  <div className="ml-auto text-xs font-medium text-slate-400">
                    {filteredModels.length} model{filteredModels.length === 1 ? "" : "s"}
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1080px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50 text-left text-[10.5px] font-bold uppercase tracking-wider text-slate-400">
                        <th className="px-4 py-2.5">Model</th>
                        <th className="px-3 py-2.5">Type</th>
                        <th className="px-3 py-2.5">Version</th>
                        <th className="px-3 py-2.5">Algorithm</th>
                        <th className="px-3 py-2.5">Framework</th>
                        <th className="px-3 py-2.5">Owner</th>
                        <th className="px-3 py-2.5">Business Unit</th>
                        <th className="px-3 py-2.5">Status</th>
                        <th className="px-3 py-2.5">Last Updated</th>
                        <th className="px-3 py-2.5">Documentation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {filteredModels.length === 0 ? (
                        <tr>
                          <td colSpan={10} className="px-6 py-14">
                            <VEmptyState
                              icon={Database}
                              title={hasActiveFilters ? "No models match your filters" : "No models in inventory"}
                              description={
                                hasActiveFilters
                                  ? "Try adjusting your search or filter criteria."
                                  : "No model records are currently available in this inventory."
                              }
                            />
                          </td>
                        </tr>
                      ) : (
                        filteredModels.map((m) => {
                          const documentationReference = getDocumentationReference(m);
                          const documentationHref = resolveDocumentationHref(documentationReference);
                          return (
                            <tr key={m.model_id} className="hover:bg-blue-50/40">
                              <td className="px-4 py-3">
                                <div className="font-semibold leading-tight text-slate-900">{m.model_name}</div>
                                <div className="mt-0.5 text-xs text-slate-400">{m.model_id}</div>
                              </td>
                              <td className="px-3 py-3 text-slate-600">{dash(m.model_type)}</td>
                              <td className="px-3 py-3 tabular-nums text-slate-600">{dash(m.model_version)}</td>
                              <td className="px-3 py-3 text-slate-600">{displayAlgorithm(m)}</td>
                              <td className="px-3 py-3 text-slate-600">{dash(m.regulatory_framework)}</td>
                              <td className="px-3 py-3 text-slate-600">{dash(m.model_owner)}</td>
                              <td className="px-3 py-3 text-slate-600">{dash(m.business_unit)}</td>
                              <td className="px-3 py-3"><StatusBadge status={m.status} /></td>
                              <td className="px-3 py-3 whitespace-nowrap tabular-nums text-slate-500">{formatDate(m.updated_at)}</td>
                              <td className="px-3 py-3">
                                {documentationHref ? (
                                  <a className="font-medium text-blue-600 hover:underline" href={documentationHref} target="_blank" rel="noreferrer">Open</a>
                                ) : (
                                  <span className="text-slate-400">Not available</span>
                                )}
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {filteredModels.length > 0 ? (
                  <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
                    <span className="text-xs text-slate-400">Showing {filteredModels.length} of {currentRecords.length} {activeTab} models</span>
                  </div>
                ) : null}
              </div>
            </div>

            {/* ── Secondary registry context — data sources, activity, focus
                model — a compact row below the (now full-width) table rather
                than a side rail that would otherwise squeeze the table's
                available width. ─────────────────────────────────────────── */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <VCard icon={Database} title="Data sources">
                {inventory?.data_sources.length ? (
                  <div className="max-h-[360px] space-y-3 overflow-y-auto pr-1">
                    {inventory.data_sources.map((source) => (
                      <div key={source.data_source_id} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3 text-sm">
                        <div className="font-medium text-slate-900">{source.file_name}</div>
                        <div className="mt-1 text-xs text-slate-500">{source.purpose} · {source.source_type}</div>
                        <div className="mt-1 text-xs text-slate-400">Uploaded by {source.uploaded_by} on {source.uploaded_at}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-slate-500">No data sources have been linked yet.</div>
                )}
              </VCard>

              <VCard icon={History} title="Activity">
                {inventory?.history.length ? (
                  <div className="max-h-[360px] space-y-3 overflow-y-auto pr-1">
                    {inventory.history.slice(0, 8).map((entry, index) => (
                      <div key={`${entry.timestamp}-${index}`} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3 text-sm">
                        <div className="font-medium text-slate-900">{entry.event}</div>
                        <div className="mt-1 text-xs text-slate-500">{entry.description}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wider text-slate-400">
                          <span>{entry.timestamp}</span>
                          {entry.validation_run_id ? <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-700">{entry.validation_run_id}</span> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-slate-500">No activity recorded yet.</div>
                )}
              </VCard>

              {selectedModel ? (
                <VCard icon={ListChecks} title="Selected focus model">
                  <div className="text-base font-semibold text-slate-900">{selectedModel.model_name}</div>
                  {selectedModel.business_purpose ? (
                    <p className="mt-1 text-sm text-slate-500">{selectedModel.business_purpose}</p>
                  ) : null}
                  <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-slate-500">{activeTab === "development" ? "Development status" : "Validation status"}</span>
                      <StatusBadge status={selectedModel.status} />
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-slate-500">Algorithm</span>
                      <span className="font-medium text-slate-900">{displayAlgorithm(selectedModel)}</span>
                    </div>
                  </div>
                </VCard>
              ) : null}
            </div>
          </div>
        </>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              <DialogTitle>Register a model</DialogTitle>
            </div>
            <DialogDescription>Add a new model to the inventory register.</DialogDescription>
          </DialogHeader>
          {registerModelForm}
        </DialogContent>
      </Dialog>
    </div>
  );
}
