import { n as PageHeader } from "./app-shell-7PSh3UZt.js";
import { t as api } from "./api-B8rOZODa.js";
import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowRight, CheckCircle2, Clock3, FileCheck, FileText } from "lucide-react";
//#region src/routes/validation.intake.tsx?tsr-split=component
var fallbackIntake = {
	title: "Stage 1 — Intake & Governance",
	description: "Capture model metadata, upload all required artifacts, and complete the governance attestation checklist before proceeding to automated validation stages.",
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
			["Next review", "12 Jul 2026"]
		]
	},
	targetDefinition: {
		title: "Target definition",
		expression: "default_12m ∈ {0, 1}",
		detail: "positive class = 90+ DPD within 12m",
		baseRateLabel: "Base rate",
		baseRate: "4.7%",
		sampleSizeLabel: "Sample size",
		sampleSize: "219,486"
	},
	riskTier: {
		title: "Risk tier",
		value: "Tier 2",
		description: "Material — quarterly independent validation required."
	},
	artifactTitle: "Artifact inventory",
	artifactDescription: "Uploaded evidence to support subsequent validation stages.",
	artifactSummary: "3 required · 3 optional",
	artifacts: [
		{
			fileName: "retail_pd_validation.csv",
			status: "Uploaded",
			timestamp: "Uploaded 21 Jun 2026 · 09:13",
			required: true
		},
		{
			fileName: "retail_pd_mdd.pdf",
			status: "Uploaded",
			timestamp: "Uploaded 21 Jun 2026 · 09:15",
			required: true
		},
		{
			fileName: "training_pipeline.zip",
			status: "Uploaded",
			timestamp: "Uploaded 21 Jun 2026 · 09:17",
			required: true
		},
		{
			fileName: "data_profile.xlsx",
			status: "Optional",
			timestamp: "Pending review",
			required: false
		},
		{
			fileName: "assumptions_limitations.pdf",
			status: "Optional",
			timestamp: "Pending review",
			required: false
		},
		{
			fileName: "performance_report.xlsx",
			status: "Optional",
			timestamp: "Pending review",
			required: false
		}
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
			"Validation plan has been approved by the Head of Model Risk"
		]
	},
	nextStep: {
		description: "Once intake is confirmed, proceed to Stage 2 data validation and automated checks.",
		label: "Proceed to Stage 2",
		path: "/validation/data-quality"
	}
};
function Intake() {
	const [intake, setIntake] = useState(fallbackIntake);
	useEffect(() => {
		let active = true;
		api("/validation/intake").then((response) => {
			if (active && response.display) setIntake(response.display);
		}).catch(() => {
			if (active) setIntake(fallbackIntake);
		});
		return () => {
			active = false;
		};
	}, []);
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-6",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: intake.title,
				description: intake.description
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 xl:grid-cols-[1.55fr_0.95fr]",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-sm",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center justify-between gap-3",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold text-foreground",
							children: intake.modelMetadata.title
						}), /* @__PURE__ */ jsx("p", {
							className: "mt-1 text-xs text-muted-foreground",
							children: intake.modelMetadata.description
						})] }), /* @__PURE__ */ jsxs("div", {
							className: "inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary",
							children: [
								/* @__PURE__ */ jsx(FileText, { className: "h-3.5 w-3.5" }),
								" ",
								intake.modelMetadata.registeredLabel
							]
						})]
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-5 grid grid-cols-1 gap-3 md:grid-cols-2",
						children: intake.modelMetadata.items.map(([k, v]) => /* @__PURE__ */ jsxs("div", {
							className: "rounded-lg border border-border bg-background px-3 py-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "text-[10px] uppercase tracking-[0.2em] text-muted-foreground",
								children: k
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-1 text-sm font-medium text-foreground",
								children: v
							})]
						}, k))
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "space-y-4",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-5 shadow-sm",
						children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-sm font-semibold text-foreground",
								children: intake.targetDefinition.title
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-3 rounded-lg border border-border bg-background p-3 font-mono text-[12px] leading-6 text-foreground",
								children: [
									intake.targetDefinition.expression,
									/* @__PURE__ */ jsx("br", {}),
									intake.targetDefinition.detail
								]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-3 text-xs text-muted-foreground",
								children: [
									intake.targetDefinition.baseRateLabel,
									": ",
									/* @__PURE__ */ jsx("span", {
										className: "font-semibold text-foreground",
										children: intake.targetDefinition.baseRate
									}),
									" · ",
									intake.targetDefinition.sampleSizeLabel,
									": ",
									intake.targetDefinition.sampleSize
								]
							})
						]
					}), /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-[#0f172a] p-5 text-white shadow-sm",
						children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-sm font-semibold",
								children: intake.riskTier.title
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-2 text-3xl font-semibold",
								children: intake.riskTier.value
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-1 text-xs text-slate-400",
								children: intake.riskTier.description
							})
						]
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-sm",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex flex-col gap-2 md:flex-row md:items-center md:justify-between",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold text-foreground",
						children: intake.artifactTitle
					}), /* @__PURE__ */ jsx("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: intake.artifactDescription
					})] }), /* @__PURE__ */ jsxs("div", {
						className: "inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary",
						children: [
							/* @__PURE__ */ jsx(FileCheck, { className: "h-3.5 w-3.5" }),
							" ",
							intake.artifactSummary
						]
					})]
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3",
					children: intake.artifacts.map((artifact) => /* @__PURE__ */ jsx("div", {
						className: "rounded-lg border border-border bg-background p-4",
						children: /* @__PURE__ */ jsxs("div", {
							className: "flex items-start justify-between gap-3",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "min-w-0",
								children: [/* @__PURE__ */ jsx("div", {
									className: "text-sm font-semibold text-foreground",
									children: artifact.fileName
								}), /* @__PURE__ */ jsxs("div", {
									className: "mt-2 flex items-center gap-2 text-[11px] text-muted-foreground",
									children: [/* @__PURE__ */ jsx(Clock3, { className: "h-3.5 w-3.5" }), artifact.timestamp]
								})]
							}), /* @__PURE__ */ jsxs("div", {
								className: "flex shrink-0 flex-col items-end gap-2",
								children: [/* @__PURE__ */ jsxs("span", {
									className: `inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold ${artifact.status === "Uploaded" ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-600" : "border border-border bg-muted text-muted-foreground"}`,
									children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-3.5 w-3.5" }), artifact.status]
								}), /* @__PURE__ */ jsx("span", {
									className: "text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground",
									children: artifact.required ? "Required" : "Optional"
								})]
							})]
						})
					}, artifact.fileName))
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-sm",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex flex-col gap-2 md:flex-row md:items-center md:justify-between",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold text-foreground",
						children: intake.governance.title
					}), /* @__PURE__ */ jsx("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: intake.governance.description
					})] }), /* @__PURE__ */ jsx("div", {
						className: "rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-700",
						children: intake.governance.status
					})]
				}), /* @__PURE__ */ jsx("ul", {
					className: "mt-5 grid gap-3 md:grid-cols-2",
					children: intake.governance.checklist.map((item) => /* @__PURE__ */ jsxs("li", {
						className: "flex items-start gap-3 rounded-lg border border-border bg-background px-3 py-3 text-sm text-foreground/80",
						children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "mt-0.5 h-4 w-4 shrink-0 text-primary" }), /* @__PURE__ */ jsx("span", { children: item })]
					}, item))
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "flex flex-col gap-3 rounded-xl border border-border bg-card p-6 shadow-sm md:flex-row md:items-center md:justify-between",
				children: [/* @__PURE__ */ jsx("div", {
					className: "text-sm text-muted-foreground",
					children: intake.nextStep.description
				}), /* @__PURE__ */ jsxs(Link, {
					to: intake.nextStep.path,
					className: "inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90",
					children: [/* @__PURE__ */ jsx("span", { children: intake.nextStep.label }), /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})]
			})
		]
	});
}
//#endregion
export { Intake as component };
