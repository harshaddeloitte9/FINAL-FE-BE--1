import { n as PageHeader } from "./app-shell-DXEPQAWO.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { jsx, jsxs } from "react/jsx-runtime";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/validation.stress.tsx?tsr-split=component
var scenarios = [
	{
		name: "Base",
		pd: 4.7,
		ecl: 100,
		color: "oklch(0.76 0.18 130)"
	},
	{
		name: "Adverse",
		pd: 7.2,
		ecl: 152
	},
	{
		name: "Severe",
		pd: 11.4,
		ecl: 241
	},
	{
		name: "Reverse",
		pd: 14.8,
		ecl: 312
	}
];
var stability = Array.from({ length: 12 }, (_, i) => ({
	month: `M${i + 1}`,
	auc: +(.875 - Math.abs(Math.sin(i / 3)) * .02).toFixed(3),
	psi: +(.04 + Math.abs(Math.sin(i / 4)) * .06).toFixed(3)
}));
var backtest = Array.from({ length: 12 }, (_, i) => ({
	month: `M${i + 1}`,
	predicted: +(4.5 + Math.sin(i / 2) * .4).toFixed(2),
	actual: +(4.6 + Math.sin(i / 2) * .5 + (i > 8 ? .3 : 0)).toFixed(2)
}));
function Stress() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Sensitivity, Stress Testing & Backtesting",
				description: "Scenario simulations, model stability over time, and back-tested predictions vs realised outcomes."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Stress scenarios — ECL multiplier"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "Baseline ECL indexed to 100"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 h-64",
							children: /* @__PURE__ */ jsx(ChartContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(BarChart, {
									data: scenarios,
									children: [
										/* @__PURE__ */ jsx(CartesianGrid, {
											stroke: "oklch(0.92 0.005 240)",
											strokeDasharray: "3 3"
										}),
										/* @__PURE__ */ jsx(XAxis, {
											dataKey: "name",
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
											dataKey: "ecl",
											fill: "oklch(0.6 0.18 135)",
											radius: [
												6,
												6,
												0,
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
						/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Stability over time"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "Rolling AUC and PSI"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 h-64",
							children: /* @__PURE__ */ jsx(ChartContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(LineChart, {
									data: stability,
									children: [
										/* @__PURE__ */ jsx(CartesianGrid, {
											stroke: "oklch(0.92 0.005 240)",
											strokeDasharray: "3 3"
										}),
										/* @__PURE__ */ jsx(XAxis, {
											dataKey: "month",
											tickLine: false,
											axisLine: false,
											fontSize: 11
										}),
										/* @__PURE__ */ jsx(YAxis, {
											yAxisId: "l",
											tickLine: false,
											axisLine: false,
											fontSize: 11,
											domain: [.8, .9]
										}),
										/* @__PURE__ */ jsx(YAxis, {
											yAxisId: "r",
											orientation: "right",
											tickLine: false,
											axisLine: false,
											fontSize: 11,
											domain: [0, .2]
										}),
										/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
											borderRadius: 10,
											border: "1px solid oklch(0.92 0.005 240)"
										} }),
										/* @__PURE__ */ jsx(Legend, { wrapperStyle: { fontSize: 11 } }),
										/* @__PURE__ */ jsx(Line, {
											yAxisId: "l",
											type: "monotone",
											dataKey: "auc",
											stroke: "oklch(0.6 0.18 135)",
											strokeWidth: 2.5,
											dot: false
										}),
										/* @__PURE__ */ jsx(Line, {
											yAxisId: "r",
											type: "monotone",
											dataKey: "psi",
											stroke: "oklch(0.6 0.22 27)",
											strokeWidth: 2.5,
											dot: false
										})
									]
								})
							})
						})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [
					/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Backtesting — predicted vs actual default rate"
					}),
					/* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "Trailing 12 months · binomial test p = 0.18 (no rejection)"
					}),
					/* @__PURE__ */ jsx("div", {
						className: "mt-4 h-72",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(LineChart, {
								data: backtest,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "month",
										tickLine: false,
										axisLine: false,
										fontSize: 11
									}),
									/* @__PURE__ */ jsx(YAxis, {
										tickLine: false,
										axisLine: false,
										fontSize: 11,
										unit: "%"
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Legend, { wrapperStyle: { fontSize: 11 } }),
									/* @__PURE__ */ jsx(Line, {
										type: "monotone",
										dataKey: "predicted",
										stroke: "oklch(0.6 0.18 135)",
										strokeWidth: 2.5
									}),
									/* @__PURE__ */ jsx(Line, {
										type: "monotone",
										dataKey: "actual",
										stroke: "oklch(0.6 0.22 27)",
										strokeWidth: 2.5
									})
								]
							})
						})
					})
				]
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-1 gap-4 md:grid-cols-3",
				children: [
					[
						"Sensitivity",
						"±10% feature perturbation — output drift &lt; 3%",
						"PASS"
					],
					[
						"Stress sims",
						"Severe scenario doubles ECL — within tolerance",
						"PASS"
					],
					[
						"Backtest",
						"12-month coverage; binomial test not rejected",
						"PASS"
					]
				].map(([t, d, s]) => /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-5 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("div", {
							className: "text-[10px] uppercase tracking-wider text-muted-foreground",
							children: t
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-2 text-sm",
							dangerouslySetInnerHTML: { __html: d }
						}),
						/* @__PURE__ */ jsx("span", {
							className: "mt-3 inline-flex rounded-full border border-primary/30 bg-primary-soft px-2 py-0.5 text-[10px] font-semibold",
							children: s
						})
					]
				}, t))
			})
		]
	});
}
//#endregion
export { Stress as component };
