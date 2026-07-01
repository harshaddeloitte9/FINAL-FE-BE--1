import { n as PageHeader } from "./app-shell-DVyXktRn.js";
import { t as featureImportance } from "./mock-data-2vCp6sQZ.js";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { AlertTriangle, ArrowRight, CheckCircle2, XCircle } from "lucide-react";
//#region src/routes/validation.conceptual.tsx?tsr-split=component
var doc = [
	{
		label: "Model development document",
		status: "PASS"
	},
	{
		label: "Data lineage attestation",
		status: "PASS"
	},
	{
		label: "Independent code review",
		status: "PASS"
	},
	{
		label: "Sensitivity analysis report",
		status: "WARN"
	},
	{
		label: "Reproducibility package (seed, env)",
		status: "PASS"
	},
	{
		label: "Limitations & caveats statement",
		status: "WARN"
	}
];
var assumptions = [
	{
		label: "Linearity in log-odds for monotonic features",
		verdict: "Holds",
		tone: "PASS"
	},
	{
		label: "Independence of behavioural & application features",
		verdict: "Partial — DTI/Util ρ=0.42",
		tone: "WARN"
	},
	{
		label: "Stationarity of macroeconomic regime",
		verdict: "Holds within window",
		tone: "PASS"
	},
	{
		label: "Default definition consistency (90 DPD)",
		verdict: "Aligned IFRS 9 Stage 3",
		tone: "PASS"
	}
];
var StatusIcon = ({ s }) => s === "PASS" ? /* @__PURE__ */ jsx(CheckCircle2, { className: "h-4 w-4 text-primary" }) : s === "WARN" ? /* @__PURE__ */ jsx(AlertTriangle, { className: "h-4 w-4 text-warning" }) : /* @__PURE__ */ jsx(XCircle, { className: "h-4 w-4 text-destructive" });
function Conceptual() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Conceptual Soundness Review",
				description: "Are the chosen features, methodology, and assumptions appropriate for the stated business objective and regulatory context?"
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Feature relevance"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "Top SHAP-ranked drivers · economic plausibility check"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 space-y-2",
							children: featureImportance.slice(0, 8).map((f) => /* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-3 rounded-lg border border-border bg-background p-3",
								children: [
									/* @__PURE__ */ jsx("span", {
										className: "w-44 truncate text-sm font-medium",
										children: f.feature
									}),
									/* @__PURE__ */ jsx("div", {
										className: "h-2 flex-1 overflow-hidden rounded-full bg-muted",
										children: /* @__PURE__ */ jsx("div", {
											className: "h-full rounded-full bg-primary",
											style: { width: `${f.value * 400}%` }
										})
									}),
									/* @__PURE__ */ jsx("span", {
										className: "w-12 text-right text-xs font-mono text-muted-foreground",
										children: f.value.toFixed(2)
									}),
									/* @__PURE__ */ jsx(CheckCircle2, { className: "h-4 w-4 text-primary" })
								]
							}, f.feature))
						})
					]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Methodology review"
					}), /* @__PURE__ */ jsxs("ul", {
						className: "mt-4 space-y-3 text-sm",
						children: [
							/* @__PURE__ */ jsxs("li", {
								className: "flex gap-2",
								children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-4 w-4 shrink-0 text-primary" }), " XGBoost with monotonic constraints on DTI / Utilization."]
							}),
							/* @__PURE__ */ jsxs("li", {
								className: "flex gap-2",
								children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-4 w-4 shrink-0 text-primary" }), " Stratified 5-fold CV; SMOTE on training fold only."]
							}),
							/* @__PURE__ */ jsxs("li", {
								className: "flex gap-2",
								children: [/* @__PURE__ */ jsx(AlertTriangle, { className: "h-4 w-4 shrink-0 text-warning" }), " Isotonic calibration applied — recommend Platt benchmark."]
							}),
							/* @__PURE__ */ jsxs("li", {
								className: "flex gap-2",
								children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-4 w-4 shrink-0 text-primary" }), " Class weights documented and reproducible."]
							})
						]
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Model assumptions"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-3 divide-y divide-border",
						children: assumptions.map((a) => /* @__PURE__ */ jsxs("div", {
							className: "flex items-center justify-between gap-3 py-3 text-sm",
							children: [
								/* @__PURE__ */ jsx("span", {
									className: "flex-1",
									children: a.label
								}),
								/* @__PURE__ */ jsx("span", {
									className: "text-xs text-muted-foreground",
									children: a.verdict
								}),
								/* @__PURE__ */ jsx(StatusIcon, { s: a.tone })
							]
						}, a.label))
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Documentation checklist"
					}), /* @__PURE__ */ jsx("ul", {
						className: "mt-3 divide-y divide-border",
						children: doc.map((d) => /* @__PURE__ */ jsxs("li", {
							className: "flex items-center justify-between py-3 text-sm",
							children: [/* @__PURE__ */ jsx("span", { children: d.label }), /* @__PURE__ */ jsx(StatusIcon, { s: d.status })]
						}, d.label))
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-primary/30 bg-primary-soft p-6",
				children: [/* @__PURE__ */ jsx("div", {
					className: "text-xs font-semibold uppercase tracking-wider text-foreground/70",
					children: "Regulatory alignment"
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm",
					children: "Methodology is consistent with SS1/23 expectations on transparency, monotonicity, and challenger benchmarking. Two amber items (sensitivity report, limitations statement) require remediation prior to sign-off."
				})]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "text-right",
				children: /* @__PURE__ */ jsxs(Link, {
					to: "/validation/challenger",
					className: "inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90",
					children: ["Continue to Stage 4", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})
			})
		]
	});
}
//#endregion
export { Conceptual as component };
