import { n as PageHeader } from "./app-shell-fDQz9JMF.js";
import { a as scoreDistribution, i as rocCurve, n as prCurve } from "./mock-data-2vCp6sQZ.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowRight } from "lucide-react";
import { Area, AreaChart, Bar, BarChart as BarChart$1, CartesianGrid, Line, LineChart as LineChart$1, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/validation.performance.tsx?tsr-split=component
var metrics = [
	{
		label: "ROC-AUC",
		value: "0.873"
	},
	{
		label: "Gini",
		value: "0.746"
	},
	{
		label: "KS",
		value: "0.612"
	},
	{
		label: "Accuracy",
		value: "0.901"
	},
	{
		label: "Precision",
		value: "0.768"
	},
	{
		label: "Recall",
		value: "0.812"
	},
	{
		label: "F1 Score",
		value: "0.789"
	},
	{
		label: "F2 Score",
		value: "0.803"
	},
	{
		label: "Brier",
		value: "0.071"
	},
	{
		label: "Log loss",
		value: "0.214"
	}
];
var confusion = [
	[
		"True Negative",
		14812,
		"primary"
	],
	[
		"False Positive",
		1204,
		"warning"
	],
	[
		"False Negative",
		612,
		"destructive"
	],
	[
		"True Positive",
		2938,
		"primary"
	]
];
var thresholds = Array.from({ length: 21 }, (_, i) => {
	const t = i / 20;
	const p = +(.4 + .5 * t).toFixed(3);
	const r = +(.98 - .85 * t).toFixed(3);
	return {
		threshold: t,
		precision: p,
		recall: r,
		f1: +(2 * p * r / (p + r)).toFixed(3)
	};
});
var calibration = Array.from({ length: 10 }, (_, i) => {
	const pred = (i + .5) / 10;
	return {
		pred: +pred.toFixed(2),
		actual: +Math.min(1, pred + Math.sin(i) * .03).toFixed(3),
		perfect: +pred.toFixed(2)
	};
});
function Performance() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Stage 5 — Performance Testing",
				description: "Comprehensive performance evaluation on the independent validation hold-out set before stress testing and regulatory review."
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-2 gap-3 md:grid-cols-5",
				children: metrics.map((m) => /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
					children: [/* @__PURE__ */ jsx("div", {
						className: "text-[10px] uppercase tracking-wider text-muted-foreground",
						children: m.label
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-xl font-semibold tracking-tight tabular-nums",
						children: m.value
					})]
				}, m.label))
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [
					/* @__PURE__ */ jsx(Card, {
						title: "ROC curve",
						sub: "AUC 0.873",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(AreaChart, {
								data: rocCurve,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "fpr",
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(YAxis, {
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Area, {
										type: "monotone",
										dataKey: "tpr",
										stroke: "oklch(0.6 0.18 135)",
										fill: "oklch(0.76 0.18 130)",
										fillOpacity: .3
									}),
									/* @__PURE__ */ jsx(Line, {
										type: "linear",
										dataKey: "diagonal",
										stroke: "oklch(0.6 0.01 240)",
										strokeDasharray: "4 4",
										dot: false
									})
								]
							})
						})
					}),
					/* @__PURE__ */ jsx(Card, {
						title: "Precision–Recall",
						sub: "Average precision 0.81",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(AreaChart, {
								data: prCurve,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "recall",
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(YAxis, {
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Area, {
										type: "monotone",
										dataKey: "precision",
										stroke: "oklch(0.6 0.18 135)",
										fill: "oklch(0.76 0.18 130)",
										fillOpacity: .3
									})
								]
							})
						})
					}),
					/* @__PURE__ */ jsx(Card, {
						title: "Confusion matrix",
						sub: "Threshold 0.50",
						children: /* @__PURE__ */ jsx("div", {
							className: "grid h-full grid-cols-2 gap-3",
							children: confusion.map(([label, n, tone]) => /* @__PURE__ */ jsxs("div", {
								className: "flex flex-col justify-between rounded-xl border p-4 " + (tone === "primary" ? "border-primary/30 bg-primary-soft" : tone === "warning" ? "border-warning/40 bg-warning/15" : "border-destructive/30 bg-destructive/10"),
								children: [/* @__PURE__ */ jsx("span", {
									className: "text-[11px] uppercase tracking-wider text-muted-foreground",
									children: label
								}), /* @__PURE__ */ jsx("span", {
									className: "text-2xl font-semibold tabular-nums",
									children: n.toLocaleString()
								})]
							}, label))
						})
					}),
					/* @__PURE__ */ jsx(Card, {
						title: "Threshold analysis",
						sub: "Precision · Recall · F1 across cut-offs",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(LineChart$1, {
								data: thresholds,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "threshold",
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(YAxis, {
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Line, {
										type: "monotone",
										dataKey: "precision",
										stroke: "oklch(0.6 0.18 135)",
										dot: false,
										strokeWidth: 2
									}),
									/* @__PURE__ */ jsx(Line, {
										type: "monotone",
										dataKey: "recall",
										stroke: "oklch(0.6 0.22 27)",
										dot: false,
										strokeWidth: 2
									}),
									/* @__PURE__ */ jsx(Line, {
										type: "monotone",
										dataKey: "f1",
										stroke: "oklch(0.55 0.02 240)",
										dot: false,
										strokeWidth: 2
									})
								]
							})
						})
					}),
					/* @__PURE__ */ jsx(Card, {
						title: "Calibration",
						sub: "Predicted vs observed default rate",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(LineChart$1, {
								data: calibration,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "pred",
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(YAxis, {
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Line, {
										type: "monotone",
										dataKey: "actual",
										stroke: "oklch(0.6 0.18 135)",
										strokeWidth: 2.5
									}),
									/* @__PURE__ */ jsx(Line, {
										type: "linear",
										dataKey: "perfect",
										stroke: "oklch(0.6 0.01 240)",
										strokeDasharray: "4 4",
										dot: false
									})
								]
							})
						})
					}),
					/* @__PURE__ */ jsx(Card, {
						title: "Score distribution",
						sub: "Hold-out set · KS = 0.612",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(BarChart$1, {
								data: scoreDistribution,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "bin",
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(YAxis, {
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Bar, {
										dataKey: "good",
										stackId: "a",
										fill: "oklch(0.76 0.18 130)"
									}),
									/* @__PURE__ */ jsx(Bar, {
										dataKey: "bad",
										stackId: "a",
										fill: "oklch(0.6 0.22 27)"
									})
								]
							})
						})
					})
				]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "text-right",
				children: /* @__PURE__ */ jsxs(Link, {
					to: "/validation/stress",
					className: "inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90",
					children: ["Continue to Stage 6", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})
			})
		]
	});
}
function Card({ title, sub, children }) {
	return /* @__PURE__ */ jsxs("div", {
		className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
		children: [
			/* @__PURE__ */ jsx("h3", {
				className: "text-sm font-semibold",
				children: title
			}),
			sub && /* @__PURE__ */ jsx("p", {
				className: "text-xs text-muted-foreground",
				children: sub
			}),
			/* @__PURE__ */ jsx("div", {
				className: "mt-4 h-56",
				children
			})
		]
	});
}
//#endregion
export { Performance as component };
