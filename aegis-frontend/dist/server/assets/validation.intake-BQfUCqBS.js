import { n as PageHeader } from "./app-shell-DVyXktRn.js";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowRight, FileCheck, FileText } from "lucide-react";
//#region src/routes/validation.intake.tsx?tsr-split=component
var meta = [
	["Model ID", "CR-PD-XGB-027"],
	["Model name", "Retail PD — XGBoost Champion"],
	["Owner", "A. Khurana · Risk Validation"],
	["Developer", "Credit Risk Modelling, EMEA"],
	["Version", "v1.7.6"],
	["Risk tier", "Tier 2 — Material"],
	["Last validated", "12 Apr 2026"],
	["Next review", "12 Jul 2026"]
];
var artifacts = [
	{
		label: "Validation dataset",
		status: "Submitted",
		detail: "Used for Stage 2 automated checks."
	},
	{
		label: "Model development document",
		status: "Submitted",
		detail: "Needed for governance and concept review."
	},
	{
		label: "Training code / scripts",
		status: "Submitted",
		detail: "Required for replication & benchmarking."
	},
	{
		label: "Data dictionary / profile",
		status: "Optional",
		detail: "Supports data validation and documentation."
	},
	{
		label: "Assumptions & limitations",
		status: "Optional",
		detail: "Supports conceptual review and risk assessment."
	},
	{
		label: "Performance report",
		status: "Optional",
		detail: "Useful for Stage 5 performance benchmarking."
	}
];
var checklist = [
	"Model is registered in the model inventory",
	"Risk tier assignment has been documented",
	"Submitted artifacts cover dataset, MDD, and training code",
	"Previous validation findings (if any) have been reviewed",
	"Regulatory scope (IFRS 9 / SS1/23 / SS11/13) is identified",
	"Independent validation team has no conflict of interest",
	"Validation plan has been approved by the Head of Model Risk"
];
function Intake() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Stage 1 — Intake & Governance",
				description: "Capture model metadata, evidence artifacts, and governance attestation before proceeding to automated validation checks."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center justify-between gap-4",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
							className: "text-sm font-semibold",
							children: "Model metadata"
						}), /* @__PURE__ */ jsx("p", {
							className: "mt-1 text-xs text-muted-foreground",
							children: "Key registration details supplied by the developer."
						})] }), /* @__PURE__ */ jsxs("div", {
							className: "inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-xs font-semibold text-primary",
							children: [/* @__PURE__ */ jsx(FileText, { className: "h-3.5 w-3.5" }), " Registered"]
						})]
					}), /* @__PURE__ */ jsx("dl", {
						className: "mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2",
						children: meta.map(([k, v]) => /* @__PURE__ */ jsxs("div", {
							className: "flex flex-col rounded-lg border border-border bg-background p-3",
							children: [/* @__PURE__ */ jsx("dt", {
								className: "text-[10px] uppercase tracking-wider text-muted-foreground",
								children: k
							}), /* @__PURE__ */ jsx("dd", {
								className: "mt-1 text-sm font-medium",
								children: v
							})]
						}, k))
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "space-y-4",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [
							/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold",
								children: "Target definition"
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-3 rounded-lg bg-primary-soft p-3 font-mono text-xs",
								children: [
									"default_12m ∈ ",
									`{0, 1}`,
									/* @__PURE__ */ jsx("br", {}),
									"positive class = 90+ DPD within 12m"
								]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-3 text-xs text-muted-foreground",
								children: [
									"Base rate: ",
									/* @__PURE__ */ jsx("span", {
										className: "font-semibold text-foreground",
										children: "4.7%"
									}),
									" · Sample size: 219,486"
								]
							})
						]
					}), /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-sidebar p-6 text-sidebar-foreground shadow-elegant",
						children: [
							/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold",
								children: "Risk tier"
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-2 text-3xl font-semibold",
								children: "Tier 2"
							}),
							/* @__PURE__ */ jsx("p", {
								className: "mt-1 text-xs text-sidebar-foreground/70",
								children: "Material — quarterly independent validation required."
							})
						]
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-center justify-between gap-4",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Artifact inventory"
					}), /* @__PURE__ */ jsx("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: "Uploaded evidence to support subsequent validation stages."
					})] }), /* @__PURE__ */ jsx("span", {
						className: "rounded-full border border-primary/20 bg-primary-soft px-3 py-1 text-xs font-semibold text-primary",
						children: "3 required, 3 optional"
					})]
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3",
					children: artifacts.map((artifact) => /* @__PURE__ */ jsx("div", {
						className: "rounded-xl border border-border bg-background p-4",
						children: /* @__PURE__ */ jsxs("div", {
							className: "flex items-center justify-between gap-3",
							children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
								className: "text-sm font-semibold",
								children: artifact.label
							}), /* @__PURE__ */ jsx("p", {
								className: "mt-1 text-xs text-muted-foreground",
								children: artifact.detail
							})] }), /* @__PURE__ */ jsxs("span", {
								className: "inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary-soft px-2 py-1 text-[11px] font-semibold text-primary",
								children: [
									/* @__PURE__ */ jsx(FileCheck, { className: "h-3.5 w-3.5" }),
									" ",
									artifact.status
								]
							})]
						})
					}, artifact.label))
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-center justify-between gap-4",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Governance attestation"
					}), /* @__PURE__ */ jsx("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: "Confirm the model and validation plan are ready to proceed."
					})] }), /* @__PURE__ */ jsx("span", {
						className: "rounded-full border border-warning/20 bg-warning/10 px-3 py-1 text-xs font-semibold text-warning-foreground",
						children: "Pending review"
					})]
				}), /* @__PURE__ */ jsx("ul", {
					className: "mt-4 grid gap-3 text-sm text-foreground/80 md:grid-cols-2",
					children: checklist.map((item) => /* @__PURE__ */ jsxs("li", {
						className: "flex gap-3 rounded-lg border border-border bg-background p-3",
						children: [/* @__PURE__ */ jsx("span", { className: "mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-primary" }), /* @__PURE__ */ jsx("span", { children: item })]
					}, item))
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 text-right shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "text-sm text-muted-foreground",
					children: "Once intake is confirmed, proceed to Stage 2 data validation and automated checks."
				}), /* @__PURE__ */ jsxs(Link, {
					to: "/validation/data-quality",
					className: "mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90",
					children: [/* @__PURE__ */ jsx("span", { children: "Proceed to Stage 2" }), /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})]
			})
		]
	});
}
//#endregion
export { Intake as component };
