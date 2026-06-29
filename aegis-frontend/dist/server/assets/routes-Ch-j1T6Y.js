import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowRight, BarChart3, Boxes, FileCheck2, GitCompareArrows, ShieldCheck, Sparkles } from "lucide-react";
//#region src/routes/index.tsx?tsr-split=component
function Landing() {
	return /* @__PURE__ */ jsxs("div", {
		className: "mx-auto flex max-w-6xl flex-col",
		children: [
			/* @__PURE__ */ jsxs("div", {
				className: "mb-10 md:mb-14",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground",
						children: [/* @__PURE__ */ jsx("span", { className: "h-1.5 w-1.5 rounded-full bg-primary" }), "Enterprise AI Platform"]
					}),
					/* @__PURE__ */ jsx("h1", {
						className: "mt-4 text-3xl font-semibold tracking-tight md:text-5xl",
						children: "Choose your workspace"
					}),
					/* @__PURE__ */ jsx("p", {
						className: "mt-3 max-w-2xl text-sm text-muted-foreground md:text-base",
						children: "Aegis Credit unifies model development and independent validation in a single, regulator-grade platform. Select a workspace to begin."
					})
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsx(WorkspaceCard, {
					to: "/development",
					accent: "from-primary/15 to-transparent",
					icon: /* @__PURE__ */ jsx(Boxes, { className: "h-6 w-6 text-primary" }),
					eyebrow: "Workspace 01",
					title: "Model Development",
					description: "Build, train, evaluate, and explain credit risk models with an end-to-end ML workflow.",
					bullets: [{
						icon: /* @__PURE__ */ jsx(Sparkles, { className: "h-3.5 w-3.5" }),
						label: "Data → Features → Training → Explainability"
					}, {
						icon: /* @__PURE__ */ jsx(BarChart3, { className: "h-3.5 w-3.5" }),
						label: "Live model metrics & SHAP attribution"
					}],
					cta: "Open Model Development"
				}), /* @__PURE__ */ jsx(WorkspaceCard, {
					to: "/validation",
					accent: "from-foreground/10 to-transparent",
					icon: /* @__PURE__ */ jsx(ShieldCheck, { className: "h-6 w-6 text-primary" }),
					eyebrow: "Workspace 02",
					title: "Model Validation",
					description: "Independently validate existing models for performance, conceptual soundness, regulatory compliance, and governance.",
					bullets: [{
						icon: /* @__PURE__ */ jsx(GitCompareArrows, { className: "h-3.5 w-3.5" }),
						label: "Champion vs challenger benchmarking"
					}, {
						icon: /* @__PURE__ */ jsx(FileCheck2, { className: "h-3.5 w-3.5" }),
						label: "IFRS 9 / IFRS 7 / SS1/23 evidence pack"
					}],
					cta: "Open Model Validation"
				})]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4",
				children: [
					["47", "Models in inventory"],
					["92.4%", "Compliance score"],
					["12", "Active validations"],
					["Tier 2", "Risk classification"]
				].map(([v, l]) => /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
					children: [/* @__PURE__ */ jsx("div", {
						className: "text-2xl font-semibold tracking-tight",
						children: v
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-1 text-[11px] uppercase tracking-wider text-muted-foreground",
						children: l
					})]
				}, l))
			})
		]
	});
}
function WorkspaceCard({ to, icon, eyebrow, title, description, bullets, cta, accent }) {
	return /* @__PURE__ */ jsxs(Link, {
		to,
		className: "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card p-8 shadow-elegant transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg",
		children: [/* @__PURE__ */ jsx("div", { className: `pointer-events-none absolute inset-0 bg-gradient-to-br ${accent} opacity-60` }), /* @__PURE__ */ jsxs("div", {
			className: "relative",
			children: [
				/* @__PURE__ */ jsxs("div", {
					className: "flex items-center justify-between",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-12 w-12 items-center justify-center rounded-xl bg-primary-soft",
						children: icon
					}), /* @__PURE__ */ jsx("span", {
						className: "text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground",
						children: eyebrow
					})]
				}),
				/* @__PURE__ */ jsx("h2", {
					className: "mt-6 text-2xl font-semibold tracking-tight",
					children: title
				}),
				/* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: description
				}),
				/* @__PURE__ */ jsx("ul", {
					className: "mt-6 space-y-2",
					children: bullets.map((b) => /* @__PURE__ */ jsxs("li", {
						className: "flex items-center gap-2 text-sm text-foreground/80",
						children: [/* @__PURE__ */ jsx("span", {
							className: "flex h-5 w-5 items-center justify-center rounded-md bg-primary-soft text-primary",
							children: b.icon
						}), b.label]
					}, b.label))
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "mt-8 inline-flex items-center gap-2 rounded-lg gradient-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-elegant transition-transform group-hover:translate-x-0.5",
					children: [
						cta,
						" ",
						/* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })
					]
				})
			]
		})]
	});
}
//#endregion
export { Landing as component };
