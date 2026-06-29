import { n as PageHeader } from "./app-shell-DXEPQAWO.js";
import { jsx, jsxs } from "react/jsx-runtime";
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
var assumptions = [
	"Obligor population is stable across the validation window (Q1-Q2 2026).",
	"Macro-economic conditions remain within the central forward-looking scenario.",
	"Default flag definition aligns with IFRS 9 Stage 3 (90+ DPD).",
	"Behavioural features computed on a 12-month observation window."
];
function Intake() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Model Intake & Intended Use",
				description: "Authoritative metadata, intended use, target variable, and modelling assumptions registered for independent validation."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h2", {
						className: "text-sm font-semibold",
						children: "Model metadata"
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
								children: "Target variable"
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
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Business objective"
					}), /* @__PURE__ */ jsx("p", {
						className: "mt-3 text-sm text-foreground/80",
						children: "Estimate 12-month probability of default for the retail unsecured lending portfolio to support origination decisioning, IFRS 9 ECL Stage 2 transitions, and capital adequacy reporting."
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Intended use summary"
					}), /* @__PURE__ */ jsxs("ul", {
						className: "mt-3 space-y-2 text-sm text-foreground/80",
						children: [
							/* @__PURE__ */ jsx("li", { children: "· Application scoring at origination (cut-off 0.50)" }),
							/* @__PURE__ */ jsx("li", { children: "· Behavioural rescoring monthly post-booking" }),
							/* @__PURE__ */ jsx("li", { children: "· Input into IFRS 9 ECL staging engine" }),
							/* @__PURE__ */ jsx("li", { children: "· Not approved for capital-floor or regulatory PD reporting" })
						]
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("h3", {
					className: "text-sm font-semibold",
					children: "Key assumptions"
				}), /* @__PURE__ */ jsx("ul", {
					className: "mt-4 grid grid-cols-1 gap-3 md:grid-cols-2",
					children: assumptions.map((a) => /* @__PURE__ */ jsxs("li", {
						className: "flex gap-3 rounded-lg border border-border bg-background p-3 text-sm",
						children: [/* @__PURE__ */ jsx("span", { className: "mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" }), a]
					}, a))
				})]
			})
		]
	});
}
//#endregion
export { Intake as component };
