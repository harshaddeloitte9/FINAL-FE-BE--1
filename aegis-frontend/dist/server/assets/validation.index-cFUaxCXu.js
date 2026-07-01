import { n as PageHeader } from "./app-shell-DVyXktRn.js";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { Activity, ArrowRight, BarChart3, BookOpen, ClipboardCheck, Database, FileText, GitCompareArrows, ShieldCheck } from "lucide-react";
//#region src/routes/validation.index.tsx?tsr-split=component
var stages = [
	{
		stage: 1,
		to: "/validation/intake",
		icon: FileText,
		title: "Intake & Governance",
		desc: "Model metadata, artifacts, risk tier, and governance attestation."
	},
	{
		stage: 2,
		to: "/validation/data-quality",
		icon: Database,
		title: "Data Validation",
		desc: "Automated dataset checks, leakage scan, and sample representativeness."
	},
	{
		stage: 3,
		to: "/validation/conceptual",
		icon: BookOpen,
		title: "Conceptual Soundness",
		desc: "Feature relevance, methodology, assumptions, and documentation."
	},
	{
		stage: 4,
		to: "/validation/challenger",
		icon: GitCompareArrows,
		title: "Replication & Benchmarking",
		desc: "Reproduce developer outputs and compare champion vs challengers."
	},
	{
		stage: 5,
		to: "/validation/performance",
		icon: BarChart3,
		title: "Performance Testing",
		desc: "AUC, KS, calibration, threshold analysis, hold-out validation."
	},
	{
		stage: 6,
		to: "/validation/stress",
		icon: Activity,
		title: "Stress & Backtesting",
		desc: "Scenario simulations, stability, backtests, and stress results."
	},
	{
		stage: 7,
		to: "/validation/regulatory",
		icon: ShieldCheck,
		title: "Regulatory Compliance Review",
		desc: "IFRS 9 / IFRS 7 / SS1/23 review, rule coverage, and remediation."
	},
	{
		stage: 8,
		to: "/validation/findings",
		icon: ClipboardCheck,
		title: "Findings & Final Report",
		desc: "Final observations, risk grading, recommendation, and sign-off."
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
										children: ["Stage ", s.stage]
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
