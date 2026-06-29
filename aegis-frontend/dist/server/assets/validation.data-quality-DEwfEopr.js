import { n as PageHeader } from "./app-shell-DXEPQAWO.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { jsx, jsxs } from "react/jsx-runtime";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/validation.data-quality.tsx?tsr-split=component
var missing = [
	{
		feature: "Annual Income",
		pct: 4.2
	},
	{
		feature: "DTI Ratio",
		pct: 1.1
	},
	{
		feature: "Credit Utilization",
		pct: .4
	},
	{
		feature: "LTV",
		pct: 7.6
	},
	{
		feature: "Tenure",
		pct: 2.3
	},
	{
		feature: "Region",
		pct: 0
	}
];
var drift = Array.from({ length: 12 }, (_, i) => ({
	month: `M${i + 1}`,
	dev: .5 + Math.sin(i / 2) * .05,
	oot: .5 + Math.sin(i / 2) * .05 + (i > 7 ? .04 : 0)
}));
var checks = [
	{
		label: "Duplicate rows",
		value: "0.02%",
		status: "PASS"
	},
	{
		label: "Outliers (Z>4)",
		value: "1.6%",
		status: "WARN"
	},
	{
		label: "Class imbalance",
		value: "1 : 20",
		status: "WARN"
	},
	{
		label: "Sample representativeness",
		value: "PSI 0.08",
		status: "PASS"
	},
	{
		label: "Data leakage scan",
		value: "0 leaks",
		status: "PASS"
	},
	{
		label: "Schema drift",
		value: "Stable",
		status: "PASS"
	}
];
var cls = {
	PASS: "bg-primary-soft text-foreground border-primary/30",
	WARN: "bg-warning/20 text-warning-foreground border-warning/40",
	FAIL: "bg-destructive/10 text-destructive border-destructive/30"
};
function DataQuality() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Data Quality & Representativeness",
				description: "Independent assessment of input data integrity, sample fitness, and leakage risk."
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6",
				children: checks.map((c) => /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("div", {
							className: "text-[10px] uppercase tracking-wider text-muted-foreground",
							children: c.label
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-2 text-lg font-semibold tracking-tight",
							children: c.value
						}),
						/* @__PURE__ */ jsx("span", {
							className: `mt-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${cls[c.status]}`,
							children: c.status
						})
					]
				}, c.label))
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h3", {
						className: "text-sm font-semibold",
						children: "Missing values by feature"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-4 h-64",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(BarChart, {
								data: missing,
								children: [
									/* @__PURE__ */ jsx(CartesianGrid, {
										stroke: "oklch(0.92 0.005 240)",
										strokeDasharray: "3 3"
									}),
									/* @__PURE__ */ jsx(XAxis, {
										dataKey: "feature",
										tickLine: false,
										axisLine: false,
										fontSize: 10
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
									/* @__PURE__ */ jsx(Bar, {
										dataKey: "pct",
										fill: "oklch(0.76 0.18 130)",
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
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Population stability (dev vs OOT)"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "PSI 0.08 — within tolerance"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 h-64",
							children: /* @__PURE__ */ jsx(ChartContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(AreaChart, {
									data: drift,
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
											fontSize: 11
										}),
										/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
											borderRadius: 10,
											border: "1px solid oklch(0.92 0.005 240)"
										} }),
										/* @__PURE__ */ jsx(Area, {
											type: "monotone",
											dataKey: "dev",
											stroke: "oklch(0.6 0.18 135)",
											fill: "oklch(0.76 0.18 130)",
											fillOpacity: .25
										}),
										/* @__PURE__ */ jsx(Area, {
											type: "monotone",
											dataKey: "oot",
											stroke: "oklch(0.55 0.02 240)",
											fill: "oklch(0.55 0.02 240)",
											fillOpacity: .18
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
				children: [/* @__PURE__ */ jsx("h3", {
					className: "text-sm font-semibold",
					children: "Data leakage detection"
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-foreground/80",
					children: "No future-information leakage detected across 87 candidate features. Two features were excluded during development for post-event observability and are correctly omitted from the production schema."
				})]
			})
		]
	});
}
//#endregion
export { DataQuality as component };
