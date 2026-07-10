import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app-shell";
import { api, formUpload } from "@/lib/api";
import { useDataset } from "@/lib/app-context";
import { ArrowRight, FileCheck, FileText, Upload } from "lucide-react";

export const Route = createFileRoute("/validation/intake")({
  head: () => ({ meta: [{ title: "Model Intake — Aegis Credit" }] }),
  component: Intake,
});

type IntakeDisplay = {
  title: string;
  description: string;
  modelMetadata: {
    title: string;
    description: string;
    registeredLabel: string;
    items: [string, string][];
  };
  targetDefinition: {
    title: string;
    expression: string;
    detail: string;
    baseRateLabel: string;
    baseRate: string;
    sampleSizeLabel: string;
    sampleSize: string;
  };
  riskTier: {
    title: string;
    value: string;
    description: string;
  };
  artifactTitle: string;
  artifactDescription: string;
  artifactSummary: string;
  artifacts: {
    fileName: string;
    status: string;
    timestamp: string;
    required: boolean;
  }[];
  governance: {
    title: string;
    description: string;
    status: string;
    checklist: string[];
  };
  nextStep: {
    description: string;
    label: string;
    path: string;
  };
};

type IntakeResponse = {
  demo_mode?: string;
  demo_label?: string;
  display: IntakeDisplay;
  val_intake_data?: {
    model_name?: string;
    owning_team?: string;
    model_owner?: string;
    lead_validator?: string;
    model_type?: string;
    model_version?: string;
    model_tier?: string;
    model_purpose?: string;
    mdd_text?: string;
  };
  val_mdd_reported_metrics?: Record<string, any>;
  chk_inventory?: boolean;
  chk_tier?: boolean;
  chk_artifacts?: boolean;
  chk_prev_findings?: boolean;
  chk_reg_scope?: boolean;
  chk_independence?: boolean;
  chk_plan_approved?: boolean;
  chk_attestation?: boolean;
};

const fallbackIntake: IntakeDisplay = {
  title: "Stage 1 — Intake & Governance",
  description:
    "Capture model metadata, upload all required artifacts, and complete the governance attestation checklist before proceeding to automated validation stages.",
  modelMetadata: {
    title: "Model metadata",
    description: "Key registration details supplied by the development team.",
    registeredLabel: "Registered",
    items: [
      ["Model ID", "CR-PD-XGB-027"],
      ["Model name", "Retail PD — XGBoost Champion"],
      ["Owner", "A. Khurana · Risk Validation"],
      ["Developer", "Credit Risk Modelling, EMEA"],
      ["Version", "v1.7.6"],
      ["Risk tier", "Tier 2 — Material"],
      ["Last validated", "12 Apr 2026"],
      ["Next review", "12 Jul 2026"],
    ],
  },
  targetDefinition: {
    title: "Target definition",
    expression: "default_12m ∈ {0, 1}",
    detail: "positive class = 90+ DPD within 12m",
    baseRateLabel: "Base rate",
    baseRate: "4.7%",
    sampleSizeLabel: "Sample size",
    sampleSize: "219,486",
  },
  riskTier: {
    title: "Risk tier",
    value: "Tier 2",
    description: "Material — quarterly independent validation required.",
  },
  artifactTitle: "Artifact inventory",
  artifactDescription: "Uploaded evidence to support subsequent validation stages.",
  artifactSummary: "3 required · 3 optional",
  artifacts: [
    {
      fileName: "retail_pd_validation.csv",
      status: "Uploaded",
      timestamp: "Uploaded 21 Jun 2026 · 09:13",
      required: true,
    },
    {
      fileName: "retail_pd_mdd.pdf",
      status: "Uploaded",
      timestamp: "Uploaded 21 Jun 2026 · 09:15",
      required: true,
    },
    {
      fileName: "training_pipeline.zip",
      status: "Uploaded",
      timestamp: "Uploaded 21 Jun 2026 · 09:17",
      required: true,
    },
    {
      fileName: "data_profile.xlsx",
      status: "Optional",
      timestamp: "Pending review",
      required: false,
    },
    {
      fileName: "assumptions_limitations.pdf",
      status: "Optional",
      timestamp: "Pending review",
      required: false,
    },
    {
      fileName: "performance_report.xlsx",
      status: "Optional",
      timestamp: "Pending review",
      required: false,
    },
  ],
  governance: {
    title: "Governance attestation",
    description: "Confirm the model and validation plan are ready to proceed.",
    status: "Pending review",
    checklist: [
      "Model is registered in the model inventory",
      "Risk tier assignment has been documented",
      "Submitted artifacts cover dataset, MDD, and training code",
      "Previous validation findings (if any) have been reviewed",
      "Regulatory scope (IFRS 9 / SS1/23 / SS11/13) is identified",
      "Independent validation team has no conflict of interest",
      "Validation plan has been approved by the Head of Model Risk",
    ],
  },
  nextStep: {
    description: "Once intake is confirmed, proceed to Stage 2 data validation and automated checks.",
    label: "Proceed to Stage 2",
    path: "/validation/data-quality",
  },
};

function Intake() {
  const [intake, setIntake] = useState<IntakeDisplay>(fallbackIntake);
  const navigate = useNavigate();
  const { setUploadResult, profile } = useDataset();

  // Form state mirroring the Streamlit intake
  const [modelName, setModelName] = useState("");
  const [owningTeam, setOwningTeam] = useState("");
  const [modelOwner, setModelOwner] = useState("");
  const [leadValidator, setLeadValidator] = useState("");
  const [modelType, setModelType] = useState("PD (Probability of Default)");
  const [tier, setTier] = useState("Tier 2 — Medium Risk");
  const [version, setVersion] = useState("");
  const [purpose, setPurpose] = useState("");
  const [demoMode, setDemoMode] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Artifacts state
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [mddFileName, setMddFileName] = useState<string | null>(null);
  const [mddText, setMddText] = useState<string | null>(null);
  const [mddMetrics, setMddMetrics] = useState<Record<string, any> | null>(null);
  const [trainingCodeFileName, setTrainingCodeFileName] = useState<string | null>(null);
  const [perfFileName, setPerfFileName] = useState<string | null>(null);
  const [profileFileName, setProfileFileName] = useState<string | null>(null);
  const [assumptionsFileName, setAssumptionsFileName] = useState<string | null>(null);
  const [hyperparamsFileName, setHyperparamsFileName] = useState<string | null>(null);

  // Checkboxes
  const [chkInventory, setChkInventory] = useState(false);
  const [chkTier, setChkTier] = useState(false);
  const [chkArtifacts, setChkArtifacts] = useState(false);
  const [chkPrevFindings, setChkPrevFindings] = useState(false);
  const [chkRegScope, setChkRegScope] = useState(false);
  const [chkIndependence, setChkIndependence] = useState(false);
  const [chkPlanApproved, setChkPlanApproved] = useState(false);
  const [chkAttestation, setChkAttestation] = useState(false);

  const datasetUploaded = Boolean(datasetFile || profile?.dataset_name);
  const mddUploaded = Boolean(mddFileName || mddText);
  const trainingCodeUploaded = Boolean(trainingCodeFileName);
  const profileUploaded = Boolean(profileFileName);
  const assumptionsUploaded = Boolean(assumptionsFileName);
  const perfUploaded = Boolean(perfFileName);
  const hyperparamsUploaded = Boolean(hyperparamsFileName);
  const readyCount = [datasetUploaded, mddUploaded, trainingCodeUploaded, profileUploaded, assumptionsUploaded, perfUploaded, hyperparamsUploaded].filter(Boolean).length;

  const demoOptions = [
    { key: "Demo A — Gold Standard", mode: "clean" },
    { key: "Demo B — Flawed Submission", mode: "flawed" },
  ];

  const loadDemo = async (mode: string) => {
    setDemoError(null);
    setDemoLoading(true);
    try {
      const response = await api<IntakeResponse>(`/validation/intake?mode=${mode}`);
      if (!response.display) {
        throw new Error("Invalid demo response from backend.");
      }
      setIntake(response.display);
      const snapshot = response.val_intake_data;
      if (snapshot) {
        setModelName(snapshot.model_name ?? "");
        setOwningTeam(snapshot.owning_team ?? "");
        setModelOwner(snapshot.model_owner ?? "");
        setLeadValidator(snapshot.lead_validator ?? "");
        setModelType(snapshot.model_type ?? "PD (Probability of Default)");
        setTier(snapshot.model_tier ?? "Tier 2 — Medium Risk");
        setVersion(snapshot.model_version ?? "");
        setPurpose(snapshot.model_purpose ?? "");
        if (snapshot.mdd_text) {
          setMddText(snapshot.mdd_text);
          setMddFileName("Parsed MDD from backend");
        }
      }
      setChkInventory(response.chk_inventory ?? false);
      setChkTier(response.chk_tier ?? false);
      setChkArtifacts(response.chk_artifacts ?? false);
      setChkPrevFindings(response.chk_prev_findings ?? false);
      setChkRegScope(response.chk_reg_scope ?? false);
      setChkIndependence(response.chk_independence ?? false);
      setChkPlanApproved(response.chk_plan_approved ?? false);
      setChkAttestation(response.chk_attestation ?? false);
      if (response.val_mdd_reported_metrics) {
        setMddMetrics(response.val_mdd_reported_metrics);
      }
      setDemoMode(response.demo_label ?? response.demo_mode ?? null);
    } catch (error) {
      setDemoError(error instanceof Error ? error.message : "Unable to load demo submission.");
    } finally {
      setDemoLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    void api<IntakeResponse>("/validation/intake")
      .then((response) => {
        if (active && response.display) {
          setIntake(response.display);
          // Prefill lightweight form fields from snapshot if present
          const snapshot = response.val_intake_data;
          if (snapshot) {
            setModelName(snapshot.model_name ?? "");
            setOwningTeam(snapshot.owning_team ?? "");
            setModelOwner(snapshot.model_owner ?? "");
            setLeadValidator(snapshot.lead_validator ?? "");
            setModelType(snapshot.model_type ?? "PD (Probability of Default)");
            setTier(snapshot.model_tier ?? "Tier 2 — Medium Risk");
            setVersion(snapshot.model_version ?? "");
            setPurpose(snapshot.model_purpose ?? "");
            if (snapshot.mdd_text) {
              setMddText(snapshot.mdd_text);
              setMddFileName("Parsed MDD from backend");
            }
          }
          setChkInventory(response.chk_inventory ?? false);
          setChkTier(response.chk_tier ?? false);
          setChkArtifacts(response.chk_artifacts ?? false);
          setChkPrevFindings(response.chk_prev_findings ?? false);
          setChkRegScope(response.chk_reg_scope ?? false);
          setChkIndependence(response.chk_independence ?? false);
          setChkPlanApproved(response.chk_plan_approved ?? false);
          setChkAttestation(response.chk_attestation ?? false);
          if (response.val_mdd_reported_metrics) {
            setMddMetrics(response.val_mdd_reported_metrics);
          }
          setDemoMode(response.demo_label ?? response.demo_mode ?? null);
        }
      })
      .catch(() => {
        if (active) {
          setIntake(fallbackIntake);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title={intake.title}
        description={intake.description}
      />

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold text-foreground">Demo mode</div>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">Load a pre-configured demo intake submission instead of uploading every artifact manually.</p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {demoOptions.map((demo) => (
              <button
                key={demo.key}
                className="group inline-flex min-h-[110px] w-full items-center justify-center rounded-3xl border border-border bg-background px-4 py-4 text-center text-sm font-semibold text-foreground transition hover:border-primary hover:text-primary"
                onClick={() => loadDemo(demo.mode)}
                disabled={demoLoading}
              >
                <span className="inline-flex flex-col items-center gap-2 text-sm font-semibold leading-tight">
                  {demo.key.split(" — ").map((line, index) => (
                    <span key={index} className={index === 1 ? "text-primary" : "text-foreground"}>
                      {line}
                    </span>
                  ))}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {demoMode ?? "No demo loaded"}
          </div>
          {demoLoading ? <div className="text-xs text-muted-foreground">Loading demo...</div> : null}
          {demoError ? <div className="text-xs text-amber-300">{demoError}</div> : null}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[1.55fr_0.95fr]">
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">{intake.modelMetadata.title}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{intake.modelMetadata.description}</p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
              <FileText className="h-3.5 w-3.5" /> {intake.modelMetadata.registeredLabel}
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Model name</div>
              <input value={modelName} onChange={(e) => setModelName(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm" />
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Owning team / business unit</div>
              <input value={owningTeam} onChange={(e) => setOwningTeam(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm" />
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Model owner (name)</div>
              <input value={modelOwner} onChange={(e) => setModelOwner(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm" />
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Lead validator (name)</div>
              <input value={leadValidator} onChange={(e) => setLeadValidator(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm" />
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Model type</div>
              <select value={modelType} onChange={(e) => setModelType(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm">
                <option>PD (Probability of Default)</option>
                <option>LGD (Loss Given Default)</option>
                <option>EAD (Exposure at Default)</option>
                <option>Scorecard / Rating</option>
              </select>
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Model version</div>
              <input value={version} onChange={(e) => setVersion(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm" />
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Risk tier</div>
              <select value={tier} onChange={(e) => setTier(e.target.value)} className="mt-1 w-full bg-background px-2 py-2 text-sm">
                <option>Tier 1 — High Risk</option>
                <option>Tier 2 — Medium Risk</option>
                <option>Tier 3 — Low Risk</option>
              </select>
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-3 md:col-span-2">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Model purpose</div>
              <textarea value={purpose} onChange={(e) => setPurpose(e.target.value)} rows={3} className="mt-1 w-full bg-background px-2 py-2 text-sm" />
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-5 shadow-elegant">
            <div className="text-sm font-semibold text-foreground">{intake.targetDefinition.title}</div>
            <div className="mt-3 rounded-lg border border-border bg-background p-3 font-mono text-[12px] leading-6 text-foreground">
              {intake.targetDefinition.expression}<br />
              {intake.targetDefinition.detail}
            </div>
            <div className="mt-3 text-xs text-muted-foreground">
              {intake.targetDefinition.baseRateLabel}: <span className="font-semibold text-foreground">{intake.targetDefinition.baseRate}</span> · {intake.targetDefinition.sampleSizeLabel}: {intake.targetDefinition.sampleSize}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-[#0f172a] p-5 text-white shadow-elegant">
            <div className="text-sm font-semibold">{intake.riskTier.title}</div>
            <div className="mt-2 text-3xl font-semibold">{intake.riskTier.value}</div>
            <div className="mt-1 text-xs text-slate-400">{intake.riskTier.description}</div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{intake.artifactTitle}</h3>
            <p className="mt-1 text-xs text-muted-foreground">{intake.artifactDescription}</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
            <FileCheck className="h-3.5 w-3.5" /> {intake.artifactSummary}
          </div>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-3">
          {intake.artifacts.map((artifact) => (
            <div key={artifact.fileName} className="rounded-lg border border-border bg-background p-4">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{artifact.fileName}</div>
              <div className="mt-3 text-sm font-semibold text-foreground">{artifact.status}</div>
              <div className="mt-2 text-[11px] text-muted-foreground">{artifact.timestamp}</div>
            </div>
          ))}
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {/* Dataset upload */}
          <div className="rounded-lg border border-border bg-background p-4">
            <div className="text-sm font-semibold text-foreground">Validation dataset (CSV / XLSX) *</div>
            <div className="mt-2 flex items-center justify-between">
              <div className="text-xs text-muted-foreground">{datasetFile ? datasetFile.name : profile?.dataset_name ?? "No file uploaded"}</div>
              <label className="inline-flex items-center gap-2 cursor-pointer rounded bg-card px-2 py-1">
                <Upload className="h-4 w-4" />
                <input type="file" accept=".csv,.xlsx" className="hidden" onChange={async (e) => {
                  const f = e.target.files?.[0] ?? null;
                  if (!f) return;
                  setDatasetFile(f);
                  try {
                    const form = new FormData();
                    form.append("file", f);
                    const resp = await formUpload("/data/upload", form);
                    // store into dataset context
                    setUploadResult(f, resp as any);
                  } catch (err) {
                    console.error("Dataset upload failed", err);
                  }
                }} />
                <span className="text-xs text-primary">Upload</span>
              </label>
            </div>
          </div>

          {/* MDD upload */}
          <div className="rounded-lg border border-border bg-background p-4">
            <div className="text-sm font-semibold text-foreground">Model Development Document (PDF / DOCX / TXT) *</div>
            <div className="mt-2 flex items-center justify-between">
              <div className="text-xs text-muted-foreground">{mddFileName ?? (mddText ? `Parsed ${mddText.length} chars` : "No MDD uploaded")}</div>
              <label className="inline-flex items-center gap-2 cursor-pointer rounded bg-card px-2 py-1">
                <Upload className="h-4 w-4" />
                <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={async (e) => {
                  const f = e.target.files?.[0] ?? null;
                  if (!f) return;
                  setMddFileName(f.name);
                  setParseError(null);
                  try {
                    const form = new FormData();
                    form.append("mdd_file", f);
                    const resp = await formUpload<Record<string, any>>("/validation/parse-mdd", form);
                    setMddText(resp?.mdd_text ?? null);
                    setMddMetrics(resp?.metrics ?? null);
                  } catch (err) {
                    console.error("MDD parse failed", err);
                    setMddText(null);
                    setMddMetrics(null);
                    setParseError(err instanceof Error ? err.message : "Failed to parse MDD file.");
                  }
                }} />
                <span className="text-xs text-primary">Upload & Parse</span>
              </label>
            </div>
            {parseError ? <div className="mt-2 text-xs text-red-500">{parseError}</div> : null}
            {mddMetrics ? (
              <div className="mt-4 rounded-lg border border-border bg-slate-950/50 p-3 text-sm text-foreground">
                <div className="font-semibold">Extracted MDD metrics</div>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {Object.entries(mddMetrics).map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-background/70 px-3 py-2">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label.replace(/_/g, " ")}</div>
                      <div className="mt-1 text-sm font-semibold text-foreground">{value ?? "—"}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : mddText ? (
              <div className="mt-4 text-xs text-muted-foreground">No reported metrics were detected in the uploaded MDD.</div>
            ) : null}
          </div>

          {/* Training code */}
          <div className="rounded-lg border border-border bg-background p-4">
            <div className="text-sm font-semibold text-foreground">Training code / scripts (ZIP / PY / IPYNB) *</div>
            <div className="mt-2 flex items-center justify-between">
              <div className="text-xs text-muted-foreground">{trainingCodeFileName ?? "No file uploaded"}</div>
              <label className="inline-flex items-center gap-2 cursor-pointer rounded bg-card px-2 py-1">
                <Upload className="h-4 w-4" />
                <input type="file" accept=".zip,.py,.ipynb" className="hidden" onChange={(e) => { const f = e.target.files?.[0] ?? null; if (f) setTrainingCodeFileName(f.name); }} />
                <span className="text-xs text-primary">Attach</span>
              </label>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold text-foreground">Artifact completeness</div>
            <p className="mt-2 text-xs text-muted-foreground">Required items must be present before intake submission. Optional artifacts provide better detail for later validation stages.</p>
          </div>
          <div className="rounded-full border border-slate-700 bg-slate-950/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground">
            {readyCount}/7 uploaded
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Submitted Dataset", datasetUploaded, "REQUIRED", "Needed for Stage 2 data checks"],
            ["Model Dev Document", mddUploaded, "REQUIRED", "Governance evidence for Stage 1"],
            ["Training Code", trainingCodeUploaded, "REQUIRED", "Required for replication and review"],
            ["Data Profile", profileUploaded, "OPTIONAL", "Helps check feature coverage"],
            ["Assumptions", assumptionsUploaded, "OPTIONAL", "Model limitations and assumptions"],
            ["Performance Report", perfUploaded, "OPTIONAL", "Model accuracy and stability"],
            ["Hyperparameters", hyperparamsUploaded, "OPTIONAL", "Training configuration details"],
          ].map(([label, ok, badge, detail]) => (
            <div key={label as string} className={`rounded-lg border ${ok ? "border-emerald-500/30 bg-emerald-500/5" : "border-slate-700 bg-slate-950/80"} p-4`}>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
              <div className="mt-3 text-sm font-semibold text-foreground">{ok ? "Uploaded" : "Pending"}</div>
              <div className="mt-2 text-[11px] text-muted-foreground">{badge} · {detail}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{intake.governance.title}</h3>
            <p className="mt-1 text-xs text-muted-foreground">{intake.governance.description}</p>
          </div>
          <div className="rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-700">
            {intake.governance.status}
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkInventory} onChange={(e) => setChkInventory(e.target.checked)} />
            <span>{intake.governance.checklist[0]}</span>
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkTier} onChange={(e) => setChkTier(e.target.checked)} />
            <span>{intake.governance.checklist[1]}</span>
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkArtifacts} onChange={(e) => setChkArtifacts(e.target.checked)} />
            <span>{intake.governance.checklist[2]}</span>
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkPrevFindings} onChange={(e) => setChkPrevFindings(e.target.checked)} />
            <span>{intake.governance.checklist[3]}</span>
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkRegScope} onChange={(e) => setChkRegScope(e.target.checked)} />
            <span>{intake.governance.checklist[4]}</span>
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkIndependence} onChange={(e) => setChkIndependence(e.target.checked)} />
            <span>{intake.governance.checklist[5]}</span>
          </label>
          <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkPlanApproved} onChange={(e) => setChkPlanApproved(e.target.checked)} />
            <span>{intake.governance.checklist[6]}</span>
          </label>
        </div>
      </section>

      {/* Attestation and Submit */}
      <section className="rounded-xl border border-border bg-card p-6 shadow-elegant">
        <div className="mb-4 text-sm text-muted-foreground">By clicking 'Submit Intake', you confirm that all information provided is accurate and the validation team is ready to proceed.</div>
        <label className="flex items-center gap-3 mb-4">
          <input type="checkbox" className="h-4 w-4 accent-primary" checked={chkAttestation} onChange={(e) => setChkAttestation(e.target.checked)} />
          <span className="text-sm">I confirm the above information is accurate and complete</span>
        </label>
        {submitError ? <div className="mb-4 text-sm text-red-500">{submitError}</div> : null}
        <div className="flex gap-3 flex-wrap">
          <button
            className={`inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm ${!(chkAttestation && chkInventory && chkTier && chkArtifacts && chkPrevFindings && chkRegScope && chkIndependence && chkPlanApproved) ? "opacity-50 cursor-not-allowed" : "hover:bg-primary/90"}`}
            onClick={async () => {
              // Gate
              const gatePassed = chkAttestation && chkInventory && chkTier && chkArtifacts && chkPrevFindings && chkRegScope && chkIndependence && chkPlanApproved;
              if (!gatePassed) return;
              // Prepare payload
              const payload = {
                model_name: modelName,
                owning_team: owningTeam,
                model_owner: modelOwner,
                lead_validator: leadValidator,
                model_type: modelType,
                model_version: version,
                model_tier: tier,
                model_purpose: purpose,
                mdd_text: mddText ?? "",
              };
              setSubmitError(null);
              try {
                const resp = await api<Record<string, any>>("/validation/submit-intake", { method: "POST", body: JSON.stringify(payload) });
                if (resp?.status === "ok") {
                  // proceed to Stage 2
                  void navigate({ to: intake.nextStep.path as string });
                } else {
                  setSubmitError(resp?.detail ?? "Unable to submit the intake form.");
                }
              } catch (err) {
                console.error("Submit intake failed", err);
                setSubmitError(err instanceof Error ? err.message : "Failed to submit intake.");
              }
            }}
            disabled={!(chkAttestation && chkInventory && chkTier && chkArtifacts && chkPrevFindings && chkRegScope && chkIndependence && chkPlanApproved)}
          >
            <span>📋 Submit Intake & Proceed to Stage 2</span>
          </button>
          <button className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-semibold" onClick={() => { /* No-op for now: allow edits */ }}>
            Save draft
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-elegant md:flex-row md:items-center md:justify-between">
        <div className="text-sm text-muted-foreground">{intake.nextStep.description}</div>
        <Link
          to={intake.nextStep.path}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90"
        >
          <span>{intake.nextStep.label}</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
