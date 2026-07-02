import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app-shell";
import { api } from "@/lib/api";
import { ArrowRight, CheckCircle2, Clock3, FileCheck, FileText, ShieldCheck } from "lucide-react";

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
  display: IntakeDisplay;
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

  useEffect(() => {
    let active = true;
    void api<IntakeResponse>("/validation/intake")
      .then((response) => {
        if (active && response.display) {
          setIntake(response.display);
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
            {intake.modelMetadata.items.map(([k, v]) => (
              <div key={k} className="rounded-lg border border-border bg-background px-3 py-3">
                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{k}</div>
                <div className="mt-1 text-sm font-medium text-foreground">{v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="text-sm font-semibold text-foreground">{intake.targetDefinition.title}</div>
            <div className="mt-3 rounded-lg border border-border bg-background p-3 font-mono text-[12px] leading-6 text-foreground">
              {intake.targetDefinition.expression}<br />
              {intake.targetDefinition.detail}
            </div>
            <div className="mt-3 text-xs text-muted-foreground">
              {intake.targetDefinition.baseRateLabel}: <span className="font-semibold text-foreground">{intake.targetDefinition.baseRate}</span> · {intake.targetDefinition.sampleSizeLabel}: {intake.targetDefinition.sampleSize}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-[#0f172a] p-5 text-white shadow-sm">
            <div className="text-sm font-semibold">{intake.riskTier.title}</div>
            <div className="mt-2 text-3xl font-semibold">{intake.riskTier.value}</div>
            <div className="mt-1 text-xs text-slate-400">{intake.riskTier.description}</div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{intake.artifactTitle}</h3>
            <p className="mt-1 text-xs text-muted-foreground">{intake.artifactDescription}</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
            <FileCheck className="h-3.5 w-3.5" /> {intake.artifactSummary}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {intake.artifacts.map((artifact) => (
            <div key={artifact.fileName} className="rounded-lg border border-border bg-background p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-foreground">{artifact.fileName}</div>
                  <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <Clock3 className="h-3.5 w-3.5" />
                    {artifact.timestamp}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold ${artifact.status === "Uploaded" ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-600" : "border border-border bg-muted text-muted-foreground"}`}>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {artifact.status}
                  </span>
                  <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    {artifact.required ? "Required" : "Optional"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{intake.governance.title}</h3>
            <p className="mt-1 text-xs text-muted-foreground">{intake.governance.description}</p>
          </div>
          <div className="rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-700">
            {intake.governance.status}
          </div>
        </div>

        <ul className="mt-5 grid gap-3 md:grid-cols-2">
          {intake.governance.checklist.map((item) => (
            <li key={item} className="flex items-start gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm text-foreground/80">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-sm md:flex-row md:items-center md:justify-between">
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
