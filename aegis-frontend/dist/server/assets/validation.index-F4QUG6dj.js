import { n as PageHeader } from "./app-shell-DXEPQAWO.js";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { Activity, ArrowRight, BarChart3, BookOpen, ClipboardCheck, Database, FileText, GitCompareArrows, ShieldCheck } from "lucide-react";
//#region src/routes/validation.index.tsx?tsr-split=component
var stages = [
	{
		to: "/validation/intake",
		icon: FileText,
		title: "Model Intake & Intended Use",
		desc: "Metadata, business objective, target, assumptions."
	},
	{
		to: "/validation/data-quality",
		icon: Database,
		title: "Data Quality & Representativeness",
		desc: "Missing, duplicates, outliers, leakage, sample fitness."
	},
	{
		to: "/validation/conceptual",
		icon: BookOpen,
		title: "Conceptual Soundness",
		desc: "Feature relevance, assumptions, methodology, documentation."
	},
	{
		to: "/validation/challenger",
		icon: GitCompareArrows,
		title: "Challenger Model Analysis",
		desc: "Champion vs challenger, side-by-side metrics, ranking."
	},
	{
		to: "/validation/performance",
		icon: BarChart3,
		title: "Performance Validation",
		desc: "ROC-AUC, KS, Gini, calibration, threshold analysis."
	},
	{
		to: "/validation/stress",
		icon: Activity,
		title: "Sensitivity, Stress & Backtesting",
		desc: "Scenarios, stability, stress sims, backtests."
	},
	{
		to: "/validation/regulatory",
		icon: ShieldCheck,
		title: "Regulatory Compliance",
		desc: "IFRS 9, IFRS 7, SS1/23 — RAG status & remediation."
	},
	{
		to: "/validation/findings",
		icon: ClipboardCheck,
		title: "Findings & Final Report",
		desc: "Executive summary, risks, recommendation, export pack."
	}
];
function ValidationHome() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Model Validation",
				description: "Independent review of an existing credit risk model across performance, conceptual soundness, regulatory compliance, and governance."
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4",
				children: [
					[
						"RAG status",
						"AMBER",
						"1 high, 2 medium findings"
					],
					[
						"Compliance",
						"92.4%",
						"IFRS 9 / IFRS 7 / SS1/23"
					],
					[
						"Champion AUC",
						"0.873",
						"vs challenger 0.869"
					],
					[
						"Validation cycle",
						"Q2 · 2026",
						"Quarterly, Tier 2"
					]
				].map(([l, v, s]) => /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-5 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("div", {
							className: "text-[10px] uppercase tracking-wider text-muted-foreground",
							children: l
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tracking-tight",
							children: v
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-1 text-xs text-muted-foreground",
							children: s
						})
					]
				}, l))
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-1 gap-4 md:grid-cols-2",
				children: stages.map((s, i) => {
					const Icon = s.icon;
					return /* @__PURE__ */ jsxs(Link, {
						to: s.to,
						className: "group flex items-start gap-4 rounded-xl border border-border bg-card p-5 shadow-elegant transition-all hover:-translate-y-0.5 hover:border-primary/40",
						children: [
							/* @__PURE__ */ jsx("div", {
								className: "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary",
								children: /* @__PURE__ */ jsx(Icon, { className: "h-5 w-5" })
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "min-w-0 flex-1",
								children: [/* @__PURE__ */ jsxs("div", {
									className: "flex items-center gap-2",
									children: [/* @__PURE__ */ jsxs("span", {
										className: "text-[10px] font-mono text-muted-foreground",
										children: ["0", i + 1]
									}), /* @__PURE__ */ jsx("h3", {
										className: "text-sm font-semibold",
										children: s.title
									})]
								}), /* @__PURE__ */ jsx("p", {
									className: "mt-1 text-xs text-muted-foreground",
									children: s.desc
								})]
							}),
							/* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" })
						]
					}, s.to);
				})
			})
		]
	});
}
//#endregion
export { ValidationHome as component };
