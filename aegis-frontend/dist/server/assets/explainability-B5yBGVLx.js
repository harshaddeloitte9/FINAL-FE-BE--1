import { n as PageHeader } from "./app-shell-DXEPQAWO.js";
import { c as shapWaterfall, t as featureImportance } from "./mock-data-BOXuVqnR.js";
import { t as Button } from "./button-D06NJiFe.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { useNavigate } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowLeft, ArrowRight, TrendingDown, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/explainability.tsx?tsr-split=component
function Explainability() {
	const navigate = useNavigate();
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Explainability",
				description: "Global SHAP attributions and a worked example for one obligor."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "SHAP summary"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "Mean absolute attribution per feature"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 h-80",
							children: /* @__PURE__ */ jsx(ChartContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(BarChart, {
									data: featureImportance,
									layout: "vertical",
									margin: { left: 30 },
									children: [
										/* @__PURE__ */ jsx(CartesianGrid, {
											stroke: "oklch(0.92 0.005 240)",
											strokeDasharray: "3 3",
											horizontal: false
										}),
										/* @__PURE__ */ jsx(XAxis, {
											type: "number",
											tickLine: false,
											axisLine: false,
											fontSize: 11
										}),
										/* @__PURE__ */ jsx(YAxis, {
											type: "category",
											dataKey: "feature",
											tickLine: false,
											axisLine: false,
											fontSize: 11,
											width: 170
										}),
										/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
											borderRadius: 10,
											border: "1px solid oklch(0.92 0.005 240)"
										} }),
										/* @__PURE__ */ jsx(Bar, {
											dataKey: "value",
											fill: "oklch(0.76 0.18 130)",
											radius: [
												0,
												6,
												6,
												0
											]
										})
									]
								})
							})
						})
					]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Individual prediction · Obligor #44231"
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "mt-2 flex items-center gap-3 text-sm",
							children: [/* @__PURE__ */ jsx("span", {
								className: "rounded-full bg-destructive/10 px-2.5 py-1 text-xs font-semibold text-destructive",
								children: "PD 31.6%"
							}), /* @__PURE__ */ jsx("span", {
								className: "text-muted-foreground",
								children: "Score 412 · Stage 2"
							})]
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-5 space-y-2",
							children: shapWaterfall.map((s) => {
								const positive = s.impact > 0;
								return /* @__PURE__ */ jsxs("div", {
									className: "flex items-center gap-3 rounded-lg border border-border bg-background p-3",
									children: [
										/* @__PURE__ */ jsx("div", {
											className: "flex h-8 w-8 items-center justify-center rounded-md " + (positive ? "bg-destructive/10 text-destructive" : "bg-primary-soft text-primary"),
											children: positive ? /* @__PURE__ */ jsx(TrendingUp, { className: "h-4 w-4" }) : /* @__PURE__ */ jsx(TrendingDown, { className: "h-4 w-4" })
										}),
										/* @__PURE__ */ jsx("div", {
											className: "flex-1 text-sm",
											children: s.feature
										}),
										/* @__PURE__ */ jsxs("div", {
											className: "text-sm font-semibold tabular-nums " + (positive ? "text-destructive" : "text-primary"),
											children: [positive ? "+" : "", s.impact.toFixed(2)]
										})
									]
								}, s.feature);
							})
						})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-primary/30 bg-primary-soft p-6",
				children: [/* @__PURE__ */ jsx("h2", {
					className: "text-base font-semibold",
					children: "Plain-language explanation"
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2 max-w-3xl text-sm text-foreground/90",
					children: "This obligor's elevated probability of default is driven primarily by a high debt-to-income ratio (0.42) and credit utilization above 75%, partially offset by 9 years of stable employment and mid-tier income. The model would re-classify this loan as low-risk if utilization fell below 40% while DTI stayed under 0.35 — both within typical refinancing scenarios."
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "flex gap-3 pt-4",
				children: [/* @__PURE__ */ jsxs(Button, {
					variant: "outline",
					onClick: () => navigate({ to: "/evaluation" }),
					className: "gap-2",
					children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Evaluation"]
				}), /* @__PURE__ */ jsxs(Button, {
					onClick: () => navigate({ to: "/development" }),
					className: "gap-2 ml-auto",
					children: ["Exit to Workspace", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})]
			})
		]
	});
}
//#endregion
export { Explainability as component };
