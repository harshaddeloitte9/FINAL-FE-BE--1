import { n as PageHeader, r as cn } from "./app-shell-DXEPQAWO.js";
import { n as kpis, o as rocCurve, r as pipeline, s as scoreDistribution } from "./mock-data-BOXuVqnR.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { ArrowUpRight, Check, Circle, Download, Loader2, Play } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, Tooltip, XAxis, YAxis } from "recharts";
//#region src/components/kpi-card.tsx
function KpiCard({ label, value, delta, tone = "neutral" }) {
	const toneColor = {
		positive: "text-primary",
		warning: "text-warning-foreground bg-warning/20",
		negative: "text-destructive",
		neutral: "text-muted-foreground"
	};
	return /* @__PURE__ */ jsxs("div", {
		className: "group relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-elegant transition-all hover:-translate-y-0.5 hover:border-primary/40",
		children: [
			/* @__PURE__ */ jsxs("div", {
				className: "flex items-start justify-between",
				children: [/* @__PURE__ */ jsx("span", {
					className: "text-xs font-medium uppercase tracking-wider text-muted-foreground",
					children: label
				}), /* @__PURE__ */ jsx(ArrowUpRight, { className: "h-4 w-4 text-muted-foreground/40 transition-colors group-hover:text-primary" })]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "mt-3 text-3xl font-semibold tracking-tight tabular-nums",
				children: value
			}),
			delta && /* @__PURE__ */ jsx("div", {
				className: cn("mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium", tone === "warning" ? toneColor.warning : "bg-transparent", tone !== "warning" && toneColor[tone]),
				children: delta
			}),
			/* @__PURE__ */ jsx("div", { className: "pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-primary/5 blur-2xl transition-opacity group-hover:opacity-100" })
		]
	});
}
//#endregion
//#region src/routes/development.tsx?tsr-split=component
function DevelopmentDashboard() {
	const devPipeline = pipeline.filter((p) => p.key !== "regulatory");
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Model Development",
				description: "End-to-end workflow for building, training, evaluating, and explaining credit risk models.",
				actions: /* @__PURE__ */ jsxs(Fragment, { children: [/* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:border-primary/40",
					children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), " Export report"]
				}), /* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center gap-2 rounded-lg gradient-primary px-3 py-2 text-sm font-semibold text-primary-foreground shadow-elegant",
					children: [/* @__PURE__ */ jsx(Play, { className: "h-4 w-4" }), " Run pipeline"]
				})] })
			}),
			/* @__PURE__ */ jsx("section", {
				className: "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4",
				children: kpis.slice(0, 4).map((k) => /* @__PURE__ */ jsx(KpiCard, { ...k }, k.label))
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "lg:col-span-2 rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "mb-4 flex items-center justify-between",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "ROC curve · XGBoost champion"
						}), /* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "AUC 0.873 · validated on hold-out set"
						})] }), /* @__PURE__ */ jsx("span", {
							className: "rounded-full bg-primary-soft px-2.5 py-1 text-[11px] font-medium text-foreground",
							children: "+0.012 vs prior"
						})]
					}), /* @__PURE__ */ jsx("div", {
						className: "h-72",
						children: /* @__PURE__ */ jsx(ChartContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(AreaChart, {
								data: rocCurve,
								margin: {
									left: -10,
									right: 10,
									top: 10,
									bottom: 0
								},
								children: [
									/* @__PURE__ */ jsx("defs", { children: /* @__PURE__ */ jsxs("linearGradient", {
										id: "rocFill",
										x1: "0",
										y1: "0",
										x2: "0",
										y2: "1",
										children: [/* @__PURE__ */ jsx("stop", {
											offset: "0%",
											stopColor: "oklch(0.76 0.18 130)",
											stopOpacity: .35
										}), /* @__PURE__ */ jsx("stop", {
											offset: "100%",
											stopColor: "oklch(0.76 0.18 130)",
											stopOpacity: 0
										})]
									}) }),
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
										strokeWidth: 2.5,
										fill: "url(#rocFill)"
									}),
									/* @__PURE__ */ jsx(Line, {
										type: "linear",
										dataKey: "diagonal",
										stroke: "oklch(0.6 0.015 240)",
										strokeDasharray: "4 4",
										dot: false
									})
								]
							})
						})
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "mb-4",
						children: [/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Development pipeline"
						}), /* @__PURE__ */ jsxs("p", {
							className: "text-xs text-muted-foreground",
							children: [
								devPipeline.filter((s) => s.status === "done").length,
								" of ",
								devPipeline.length,
								" stages complete"
							]
						})]
					}), /* @__PURE__ */ jsx("ol", {
						className: "relative space-y-3 border-l border-border pl-5",
						children: devPipeline.map((s) => /* @__PURE__ */ jsxs("li", {
							className: "relative",
							children: [/* @__PURE__ */ jsx("span", {
								className: "absolute -left-[26px] top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 " + (s.status === "done" ? "border-primary bg-primary text-primary-foreground" : s.status === "active" ? "border-primary bg-primary/15 text-primary" : "border-border bg-background text-muted-foreground"),
								children: s.status === "done" ? /* @__PURE__ */ jsx(Check, { className: "h-3 w-3" }) : s.status === "active" ? /* @__PURE__ */ jsx(Loader2, { className: "h-3 w-3 animate-spin" }) : /* @__PURE__ */ jsx(Circle, { className: "h-2 w-2" })
							}), /* @__PURE__ */ jsxs("div", {
								className: "flex items-center justify-between",
								children: [/* @__PURE__ */ jsx("span", {
									className: "text-sm " + (s.status === "pending" ? "text-muted-foreground" : "font-medium"),
									children: s.label
								}), /* @__PURE__ */ jsx("span", {
									className: "text-[10px] uppercase tracking-wider text-muted-foreground",
									children: s.status === "done" ? "Done" : s.status === "active" ? "In progress" : "Pending"
								})]
							})]
						}, s.key))
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "mb-4 flex items-center justify-between",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Score distribution"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "Good vs Bad obligor separation"
					})] }), /* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-3 text-xs text-muted-foreground",
						children: [/* @__PURE__ */ jsxs("span", {
							className: "flex items-center gap-1.5",
							children: [/* @__PURE__ */ jsx("span", { className: "h-2 w-2 rounded-full bg-primary" }), " Good"]
						}), /* @__PURE__ */ jsxs("span", {
							className: "flex items-center gap-1.5",
							children: [/* @__PURE__ */ jsx("span", { className: "h-2 w-2 rounded-full bg-destructive/80" }), " Bad"]
						})]
					})]
				}), /* @__PURE__ */ jsx("div", {
					className: "h-64",
					children: /* @__PURE__ */ jsx(ChartContainer, {
						width: "100%",
						height: "100%",
						children: /* @__PURE__ */ jsxs(AreaChart, {
							data: scoreDistribution,
							margin: {
								left: -10,
								right: 10,
								top: 10,
								bottom: 0
							},
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
								/* @__PURE__ */ jsx(Area, {
									type: "monotone",
									dataKey: "good",
									stroke: "oklch(0.6 0.18 135)",
									fill: "oklch(0.76 0.18 130)",
									fillOpacity: .35
								}),
								/* @__PURE__ */ jsx(Area, {
									type: "monotone",
									dataKey: "bad",
									stroke: "oklch(0.6 0.22 27)",
									fill: "oklch(0.6 0.22 27)",
									fillOpacity: .25
								})
							]
						})
					})
				})]
			})
		]
	});
}
//#endregion
export { DevelopmentDashboard as component };
