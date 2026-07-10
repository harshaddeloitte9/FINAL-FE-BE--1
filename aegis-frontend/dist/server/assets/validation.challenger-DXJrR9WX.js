import { n as PageHeader } from "./app-shell-7PSh3UZt.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { Link } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowRight, Trophy } from "lucide-react";
import { Bar, BarChart as BarChart$1, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/validation.challenger.tsx?tsr-split=component
var compare = [
	{
		metric: "AUC",
		champion: .873,
		challenger: .869
	},
	{
		metric: "KS",
		champion: .612,
		challenger: .604
	},
	{
		metric: "Gini",
		champion: .746,
		challenger: .738
	},
	{
		metric: "Recall",
		champion: .812,
		challenger: .798
	},
	{
		metric: "Precision",
		champion: .768,
		challenger: .781
	},
	{
		metric: "F1",
		champion: .789,
		challenger: .789
	}
];
var ranking = [
	{
		rank: 1,
		name: "XGBoost (Champion)",
		auc: .873,
		ks: .612,
		gini: .746,
		status: "Selected"
	},
	{
		rank: 2,
		name: "LightGBM (Challenger)",
		auc: .869,
		ks: .604,
		gini: .738,
		status: "Approved benchmark"
	},
	{
		rank: 3,
		name: "Gradient Boosting",
		auc: .864,
		ks: .599,
		gini: .728,
		status: "Benchmark"
	},
	{
		rank: 4,
		name: "Random Forest",
		auc: .851,
		ks: .581,
		gini: .702,
		status: "Benchmark"
	},
	{
		rank: 5,
		name: "Logistic Regression",
		auc: .812,
		ks: .541,
		gini: .624,
		status: "Baseline"
	}
];
function Challenger() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Stage 4 — Replication & Benchmarking",
				description: "Replicate developer outputs and benchmark the champion model against approved challengers."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Champion reproduction"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "mt-2 text-sm text-foreground/80",
							children: "The developer's XGBoost champion was reproduced using submitted code and the validation dataset, then benchmarked against alternatives."
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 h-72",
							children: /* @__PURE__ */ jsx(ChartContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(BarChart$1, {
									data: compare,
									children: [
										/* @__PURE__ */ jsx(CartesianGrid, {
											stroke: "oklch(0.92 0.005 240)",
											strokeDasharray: "3 3"
										}),
										/* @__PURE__ */ jsx(XAxis, {
											dataKey: "metric",
											tickLine: false,
											axisLine: false,
											fontSize: 11
										}),
										/* @__PURE__ */ jsx(YAxis, {
											tickLine: false,
											axisLine: false,
											fontSize: 11,
											domain: [0, 1]
										}),
										/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
											borderRadius: 10,
											border: "1px solid oklch(0.92 0.005 240)"
										} }),
										/* @__PURE__ */ jsx(Legend, { wrapperStyle: { fontSize: 11 } }),
										/* @__PURE__ */ jsx(Bar, {
											dataKey: "champion",
											fill: "oklch(0.76 0.18 130)",
											radius: [
												6,
												6,
												0,
												0
											]
										}),
										/* @__PURE__ */ jsx(Bar, {
											dataKey: "challenger",
											fill: "oklch(0.55 0.02 240)",
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
					className: "rounded-xl border border-primary/30 bg-primary-soft p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-2",
							children: [/* @__PURE__ */ jsx(Trophy, { className: "h-5 w-5 text-primary" }), /* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold",
								children: "Recommendation"
							})]
						}),
						/* @__PURE__ */ jsxs("p", {
							className: "mt-3 text-sm",
							children: [
								"Retain ",
								/* @__PURE__ */ jsx("span", {
									className: "font-semibold",
									children: "XGBoost"
								}),
								" as champion. Differences against LightGBM challenger are within governance tolerance (ΔAUC = 0.004)."
							]
						}),
						/* @__PURE__ */ jsxs("ul", {
							className: "mt-3 space-y-1.5 text-xs text-foreground/80",
							children: [
								/* @__PURE__ */ jsx("li", { children: "· Calibrate quarterly on rolling 12-month window" }),
								/* @__PURE__ */ jsx("li", { children: "· Re-benchmark when ΔAUC > 0.010 against any challenger" }),
								/* @__PURE__ */ jsx("li", { children: "· Maintain LightGBM as warm standby" })
							]
						})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "border-b border-border p-6",
					children: /* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Model ranking"
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
									children: "#"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "Model"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-right",
									children: "AUC"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-right",
									children: "KS"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-right",
									children: "Gini"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "px-6 py-3 text-left",
									children: "Status"
								})
							] })
						}), /* @__PURE__ */ jsx("tbody", {
							className: "divide-y divide-border",
							children: ranking.map((r) => /* @__PURE__ */ jsxs("tr", {
								className: r.rank === 1 ? "bg-primary-soft/40" : "",
								children: [
									/* @__PURE__ */ jsx("td", {
										className: "px-6 py-3 font-mono text-xs text-muted-foreground",
										children: r.rank
									}),
									/* @__PURE__ */ jsx("td", {
										className: "px-6 py-3 font-medium",
										children: r.name
									}),
									/* @__PURE__ */ jsx("td", {
										className: "px-6 py-3 text-right tabular-nums",
										children: r.auc.toFixed(3)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "px-6 py-3 text-right tabular-nums",
										children: r.ks.toFixed(3)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "px-6 py-3 text-right tabular-nums",
										children: r.gini.toFixed(3)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "px-6 py-3 text-xs",
										children: r.status
									})
								]
							}, r.name))
						})]
					})
				})]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "text-right",
				children: /* @__PURE__ */ jsxs(Link, {
					to: "/validation/performance",
					className: "inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-elegant hover:bg-primary/90",
					children: ["Continue to Stage 5", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})
			})
		]
	});
}
//#endregion
export { Challenger as component };
