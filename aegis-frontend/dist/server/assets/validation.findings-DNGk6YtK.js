import { n as PageHeader } from "./app-shell-DXEPQAWO.js";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { AlertTriangle, CheckCircle2, FileDown, FileText, XCircle } from "lucide-react";
//#region src/routes/validation.findings.tsx?tsr-split=component
var findings = [
	{
		id: "F-01",
		area: "Regulatory",
		title: "Challenger benchmarks missing for Q1 cycle",
		severity: "High",
		status: "FAIL"
	},
	{
		id: "F-02",
		area: "Data",
		title: "LTV missingness at 7.6% — imputation strategy undocumented",
		severity: "Medium",
		status: "WARN"
	},
	{
		id: "F-03",
		area: "Conceptual",
		title: "Calibration limitations statement not provided",
		severity: "Medium",
		status: "WARN"
	},
	{
		id: "F-04",
		area: "Performance",
		title: "Hold-out AUC 0.873 — exceeds 0.80 threshold",
		severity: "Low",
		status: "PASS"
	},
	{
		id: "F-05",
		area: "Stress",
		title: "Severe scenario well-behaved within governance limits",
		severity: "Low",
		status: "PASS"
	},
	{
		id: "F-06",
		area: "Backtesting",
		title: "Predicted vs actual default rate aligned (binomial p=0.18)",
		severity: "Low",
		status: "PASS"
	}
];
var cls = {
	PASS: "bg-primary-soft text-foreground border-primary/30",
	WARN: "bg-warning/20 text-warning-foreground border-warning/40",
	FAIL: "bg-destructive/10 text-destructive border-destructive/30"
};
var Icon = ({ s }) => s === "PASS" ? /* @__PURE__ */ jsx(CheckCircle2, { className: "h-3.5 w-3.5" }) : s === "WARN" ? /* @__PURE__ */ jsx(AlertTriangle, { className: "h-3.5 w-3.5" }) : /* @__PURE__ */ jsx(XCircle, { className: "h-3.5 w-3.5" });
function Findings() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Validation Findings & Final Report",
				description: "Consolidated findings, risks, and recommendation for management and the Model Risk Committee.",
				actions: /* @__PURE__ */ jsxs(Fragment, { children: [/* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:border-primary/40",
					children: [/* @__PURE__ */ jsx(FileText, { className: "h-4 w-4" }), " Preview report"]
				}), /* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center gap-2 rounded-lg gradient-primary px-3 py-2 text-sm font-semibold text-primary-foreground shadow-elegant",
					children: [/* @__PURE__ */ jsx(FileDown, { className: "h-4 w-4" }), " Export PDF"]
				})] })
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Executive summary"
					}), /* @__PURE__ */ jsxs("p", {
						className: "mt-3 text-sm text-foreground/80",
						children: [
							"The XGBoost retail PD model demonstrates strong discriminatory power (AUC 0.873, KS 0.612) and stable behaviour across stress scenarios and backtesting windows. Independent validation concludes the model is ",
							/* @__PURE__ */ jsx("span", {
								className: "font-semibold",
								children: "fit for intended use"
							}),
							", conditional on remediation of one high-severity governance finding (missing Q1 challenger benchmarks) and two medium-severity documentation gaps."
						]
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-warning/40 bg-warning/10 p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("div", {
							className: "text-[10px] font-semibold uppercase tracking-wider text-warning-foreground",
							children: "Final recommendation"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold",
							children: "Approve with conditions"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "mt-2 text-xs text-foreground/80",
							children: "Re-validate in 90 days post-remediation. Maintain Tier 2 quarterly oversight cadence."
						})
					]
				})]
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-1 gap-4 sm:grid-cols-3",
				children: [
					[
						"Pass",
						"8",
						"border-primary/30 bg-primary-soft"
					],
					[
						"Warning",
						"2",
						"border-warning/40 bg-warning/10"
					],
					[
						"Fail",
						"1",
						"border-destructive/30 bg-destructive/10"
					]
				].map(([l, v, c]) => /* @__PURE__ */ jsxs("div", {
					className: `rounded-xl border p-5 shadow-elegant ${c}`,
					children: [/* @__PURE__ */ jsx("div", {
						className: "text-[10px] uppercase tracking-wider text-muted-foreground",
						children: l
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-3xl font-semibold tabular-nums",
						children: v
					})]
				}, l))
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "border-b border-border p-6",
					children: /* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Key observations & risks"
					})
				}), /* @__PURE__ */ jsx("div", {
					className: "overflow-x-auto",
					children: /* @__PURE__ */ jsxs("table", {
						className: "w-full text-sm",
						children: [/* @__PURE__ */ jsx("thead", {
							className: "bg-background text-[10px] uppercase tracking-wider text-muted-foreground",
							children: /* @__PURE__ */ jsxs("tr", { children: [
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "ID"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "Area"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "Finding"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "Severity"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "Status"
								})
							] })
						}), /* @__PURE__ */ jsx("tbody", {
							className: "divide-y divide-border",
							children: findings.map((f) => /* @__PURE__ */ jsxs("tr", { children: [
								/* @__PURE__ */ jsx("td", {
									className: "px-6 py-3 font-mono text-xs text-muted-foreground",
									children: f.id
								}),
								/* @__PURE__ */ jsx("td", {
									className: "px-6 py-3 text-xs",
									children: f.area
								}),
								/* @__PURE__ */ jsx("td", {
									className: "px-6 py-3 font-medium",
									children: f.title
								}),
								/* @__PURE__ */ jsx("td", {
									className: "px-6 py-3 text-xs",
									children: f.severity
								}),
								/* @__PURE__ */ jsx("td", {
									className: "px-6 py-3",
									children: /* @__PURE__ */ jsxs("span", {
										className: `inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cls[f.status]}`,
										children: [/* @__PURE__ */ jsx(Icon, { s: f.status }), f.status]
									})
								})
							] }, f.id))
						})]
					})
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("h3", {
					className: "text-sm font-semibold",
					children: "Sign-off"
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 grid grid-cols-1 gap-4 md:grid-cols-3",
					children: [
						[
							"Validator",
							"A. Khurana",
							"Risk Validation"
						],
						[
							"Model Owner",
							"M. Petrov",
							"Credit Risk Modelling"
						],
						[
							"Committee",
							"Model Risk Committee",
							"Pending — 22 Apr 2026"
						]
					].map(([role, name, sub]) => /* @__PURE__ */ jsxs("div", {
						className: "rounded-lg border border-border bg-background p-4",
						children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-[10px] uppercase tracking-wider text-muted-foreground",
								children: role
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-1 text-sm font-semibold",
								children: name
							}),
							/* @__PURE__ */ jsx("div", {
								className: "text-xs text-muted-foreground",
								children: sub
							})
						]
					}, role))
				})]
			})
		]
	});
}
//#endregion
export { Findings as component };
