import { t as cn } from "./utils-C_uf36nf.js";
import { n as PageHeader } from "./app-shell-7PSh3UZt.js";
import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-B8rOZODa.js";
import { t as Button } from "./button-MHHI04mG.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { t as Badge } from "./badge-D1Dupn2y.js";
import { a as SelectValue, i as SelectTrigger, n as SelectContent, r as SelectItem, t as Select } from "./select-BHv1JhlL.js";
import * as React$1 from "react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { AlertTriangle, ArrowLeft, ArrowRight, BarChart3, Download, FileText, Info, Table2, Target } from "lucide-react";
import { Bar, BarChart as BarChart$1, CartesianGrid, Cell, Pie, PieChart, Tooltip, XAxis, YAxis } from "recharts";
import * as TabsPrimitive from "@radix-ui/react-tabs";
//#region src/components/ui/tabs.tsx
var Tabs = TabsPrimitive.Root;
var TabsList = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx(TabsPrimitive.List, {
	ref,
	className: cn("inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground", className),
	...props
}));
TabsList.displayName = TabsPrimitive.List.displayName;
var TabsTrigger = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx(TabsPrimitive.Trigger, {
	ref,
	className: cn("inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background cursor-pointer transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow", className),
	...props
}));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;
var TabsContent = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx(TabsPrimitive.Content, {
	ref,
	className: cn("mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className),
	...props
}));
TabsContent.displayName = TabsPrimitive.Content.displayName;
//#endregion
//#region src/routes/profiling.tsx?tsr-split=component
function Stat({ label, value, sub }) {
	return /* @__PURE__ */ jsxs("div", {
		className: "rounded-xl border border-border bg-card p-4",
		children: [
			/* @__PURE__ */ jsx("div", {
				className: "text-[11px] uppercase tracking-wider text-muted-foreground",
				children: label
			}),
			/* @__PURE__ */ jsx("div", {
				className: "mt-1 text-2xl font-semibold tabular-nums",
				children: value
			}),
			sub && /* @__PURE__ */ jsx("div", {
				className: "text-[11px] text-muted-foreground",
				children: sub
			})
		]
	});
}
function formatCsvRow(row) {
	return Object.values(row).map((value) => {
		if (value === void 0 || value === null) return "";
		return `"${String(value).replace(/"/g, "\"\"")}"`;
	}).join(",");
}
function Profiling() {
	const { file, profile, setProfile } = useDataset();
	const navigate = useNavigate();
	const [selectedTarget, setSelectedTarget] = useState(profile?.target_col ?? null);
	const [activeProfile, setActiveProfile] = useState(profile);
	const [isLoadingTarget, setIsLoadingTarget] = useState(false);
	const [targetError, setTargetError] = useState(null);
	useEffect(() => {
		setActiveProfile(profile);
	}, [profile]);
	const availableTargets = profile?.target_candidates ?? [];
	const availableColumns = profile?.columns ?? [];
	const candidateDefault = availableColumns.includes("loan_status") ? "loan_status" : availableTargets.length > 0 ? availableTargets[0] : availableColumns[0] ?? null;
	useEffect(() => {
		if (!selectedTarget && candidateDefault) setSelectedTarget(candidateDefault);
	}, [candidateDefault, selectedTarget]);
	useEffect(() => {
		if (!file || !selectedTarget || !profile) return;
		if (profile.target_col === selectedTarget && profile.class_distribution) return;
		const fetchTargetProfile = async () => {
			setIsLoadingTarget(true);
			setTargetError(null);
			try {
				const form = new FormData();
				form.append("file", file);
				form.append("target_col", selectedTarget);
				const result = await formUpload("/data/profile", form);
				setActiveProfile(result);
				setProfile(result);
			} catch (err) {
				setTargetError(err?.message ?? "Failed to update profile for selected target.");
			} finally {
				setIsLoadingTarget(false);
			}
		};
		fetchTargetProfile();
	}, [
		file,
		profile,
		selectedTarget,
		setProfile
	]);
	if (!profile) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Data Profiling",
			description: "Schema, quality, balance and correlation diagnostics for the active dataset."
		}), /* @__PURE__ */ jsxs("div", {
			className: "rounded-xl border border-border bg-card p-6 text-center",
			children: [/* @__PURE__ */ jsx("h3", {
				className: "text-lg font-semibold",
				children: "No dataset available"
			}), /* @__PURE__ */ jsx("p", {
				className: "mt-2 text-sm text-muted-foreground",
				children: "Upload a dataset on the Data Upload page to run profiling and populate these diagnostics."
			})]
		})]
	});
	const active = activeProfile ?? profile;
	const rows = active.shape?.[0] ?? null;
	const cols = active.shape?.[1] ?? null;
	const numericCount = active.numeric_feature_count ?? null;
	const categoricalCount = active.categorical_feature_count ?? null;
	const missingCells = active.missing_cells ?? null;
	const missingPct = active.missing_percentage ?? null;
	const duplicateRows = active.duplicate_rows ?? null;
	const duplicateRate = active.duplicate_rate ?? null;
	const outlierAnalysis = active.outlier_analysis ?? {};
	const outlierEntries = Object.entries(outlierAnalysis);
	const sortedMissing = [...active.missing_by_column ? Object.entries(active.missing_by_column).map(([col, value]) => ({
		col,
		count: value.count,
		percentage: value.percentage
	})) : []].sort((a, b) => b.count - a.count).slice(0, 10);
	const classDistribution = active.class_distribution ?? null;
	const targetSummary = active.target_summary ?? null;
	const correlationColumns = active.correlation_matrix?.columns ?? [];
	active.correlation_matrix?.values;
	const dataDictionary = active.data_dictionary ?? [];
	const columnTypeTable = active.column_type_table ?? [];
	const summaryStats = active.summary_stats ?? [];
	const distributionHistograms = active.distribution_histograms ?? [];
	const leakageRiskCols = active.leakage_risk_cols ?? [];
	const dateIntegrity = active.date_integrity ?? {};
	const dateIntegrityEntries = Object.entries(dateIntegrity);
	const agent2Flags = active.agent2_flags_data ?? [];
	const agent2Error = active.agent2_error ?? null;
	const classChartData = useMemo(() => {
		if (!classDistribution) return [];
		return Object.entries(classDistribution).map(([name, value]) => ({
			name,
			value: Number(value)
		}));
	}, [classDistribution]);
	const downloadDataDictionary = () => {
		const csv = [(dataDictionary.length > 0 ? Object.keys(dataDictionary[0]) : []).join(","), ...dataDictionary.map(formatCsvRow)].join("\n");
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = "data_dictionary.csv";
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	};
	const taskTypeLabel = active.task_type === "binary" ? "Binary Classification" : active.task_type === "multiclass" ? "Multiclass Classification" : active.task_type === "regression" ? "Regression" : "Unspecified";
	const taskBadgeVariant = active.task_type === "binary" ? "default" : active.task_type === "multiclass" ? "secondary" : active.task_type === "regression" ? "outline" : "secondary";
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Data Profiling",
				description: "Schema, quality, balance and correlation diagnostics for the active dataset."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "grid grid-cols-2 gap-4 lg:grid-cols-4",
					children: [
						/* @__PURE__ */ jsx(Stat, {
							label: "Rows",
							value: rows !== null ? rows.toLocaleString() : "—",
							sub: active.dataset_name ?? void 0
						}),
						/* @__PURE__ */ jsx(Stat, {
							label: "Columns",
							value: cols !== null ? String(cols) : "—",
							sub: numericCount !== null && categoricalCount !== null ? `${numericCount} numeric · ${categoricalCount} categorical` : void 0
						}),
						/* @__PURE__ */ jsx(Stat, {
							label: "Missing cells",
							value: missingCells !== null ? missingCells.toLocaleString() : missingPct !== null ? `${missingPct}%` : "—",
							sub: missingPct !== null ? `${missingPct}% of total` : void 0
						}),
						/* @__PURE__ */ jsx(Stat, {
							label: "Duplicates",
							value: duplicateRows !== null ? String(duplicateRows) : "—",
							sub: duplicateRate !== null ? `${duplicateRate}% of rows` : void 0
						})
					]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-4",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex flex-wrap items-center justify-between gap-3",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
							className: "text-[11px] uppercase tracking-wider text-muted-foreground",
							children: "Target Task"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-1 text-lg font-semibold text-foreground",
							children: taskTypeLabel
						})] }), /* @__PURE__ */ jsx(Badge, {
							variant: taskBadgeVariant,
							children: taskTypeLabel
						})]
					}), /* @__PURE__ */ jsxs("div", {
						className: "mt-4 space-y-2 text-sm text-muted-foreground",
						children: [/* @__PURE__ */ jsxs("div", { children: ["Detected target candidates: ", availableTargets.length > 0 ? availableTargets.join(", ") : "None"] }), /* @__PURE__ */ jsxs("div", { children: ["Preferred target: ", candidateDefault ?? "Not detected"] })]
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-4 lg:grid-cols-[0.85fr_1.15fr]",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between",
							children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
								className: "text-base font-semibold",
								children: "Target variable"
							}), /* @__PURE__ */ jsx("p", {
								className: "text-xs text-muted-foreground",
								children: "Choose the target column to compute distribution, imbalance, and task diagnostics."
							})] }), /* @__PURE__ */ jsx("div", {
								className: "w-full lg:w-64",
								children: /* @__PURE__ */ jsxs(Select, {
									value: selectedTarget ?? "",
									onValueChange: (value) => setSelectedTarget(value),
									children: [/* @__PURE__ */ jsx(SelectTrigger, { children: /* @__PURE__ */ jsx(SelectValue, { placeholder: "Select target" }) }), /* @__PURE__ */ jsx(SelectContent, { children: availableColumns.map((column) => /* @__PURE__ */ jsx(SelectItem, {
										value: column,
										children: column
									}, column)) })]
								})
							})]
						}),
						isLoadingTarget && /* @__PURE__ */ jsx("div", {
							className: "mt-4 rounded-xl border border-border bg-muted p-3 text-sm text-muted-foreground",
							children: "Updating target diagnostics…"
						}),
						targetError && /* @__PURE__ */ jsx("div", {
							className: "mt-4 rounded-xl border border-destructive bg-destructive/10 p-3 text-sm text-destructive",
							children: targetError
						}),
						agent2Error && /* @__PURE__ */ jsxs("div", {
							className: "mt-4 rounded-xl border border-destructive bg-destructive/10 p-3 text-sm text-destructive",
							children: [/* @__PURE__ */ jsx("div", {
								className: "font-medium",
								children: "Data compliance check could not be completed."
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-1 text-xs",
								children: agent2Error
							})]
						}),
						agent2Flags.length > 0 && /* @__PURE__ */ jsx("div", {
							className: "mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900",
							children: /* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 font-medium",
								children: [/* @__PURE__ */ jsx(AlertTriangle, { className: "h-4 w-4" }), /* @__PURE__ */ jsxs("span", { children: [
									agent2Flags.length,
									" data compliance flag",
									agent2Flags.length === 1 ? "" : "s",
									" detected for this dataset."
								] })]
							})
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "mt-4 grid gap-3 md:grid-cols-3",
							children: [
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [
										/* @__PURE__ */ jsxs("div", {
											className: "flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground",
											children: [/* @__PURE__ */ jsx(Target, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Target summary" })]
										}),
										/* @__PURE__ */ jsx("div", {
											className: "mt-2 text-sm text-foreground",
											children: targetSummary?.task_label ?? "Target diagnostics will appear after selection."
										}),
										/* @__PURE__ */ jsxs("div", {
											className: "mt-2 text-xs text-muted-foreground",
											children: ["Selected target: ", selectedTarget ?? "—"]
										})
									]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [
										/* @__PURE__ */ jsxs("div", {
											className: "flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground",
											children: [/* @__PURE__ */ jsx(Info, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Quality checks" })]
										}),
										/* @__PURE__ */ jsx("div", {
											className: "mt-2 text-sm text-foreground",
											children: targetSummary?.is_imbalanced ? "Target class imbalance detected." : "Target distribution appears balanced for the current profile."
										}),
										targetSummary?.imbalance_ratio ? /* @__PURE__ */ jsxs("div", {
											className: "mt-2 text-xs text-muted-foreground",
											children: [
												"Imbalance ratio: ",
												targetSummary.imbalance_ratio,
												":1"
											]
										}) : null
									]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [
										/* @__PURE__ */ jsxs("div", {
											className: "flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground",
											children: [/* @__PURE__ */ jsx(AlertTriangle, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Leakage & dates" })]
										}),
										/* @__PURE__ */ jsx("div", {
											className: "mt-2 text-sm text-foreground",
											children: leakageRiskCols.length > 0 ? `${leakageRiskCols.length} potential leakage column${leakageRiskCols.length === 1 ? "" : "s"}` : "No strong leakage signals detected."
										}),
										/* @__PURE__ */ jsx("div", {
											className: "mt-2 text-xs text-muted-foreground",
											children: dateIntegrityEntries.length > 0 ? `${dateIntegrityEntries.length} date field${dateIntegrityEntries.length === 1 ? "" : "s"} checked for future/ancient values` : "No date fields detected."
										})
									]
								})
							]
						})
					]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center justify-between gap-4",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-2",
							children: [/* @__PURE__ */ jsx(BarChart3, { className: "h-4 w-4 text-muted-foreground" }), /* @__PURE__ */ jsx("h2", {
								className: "text-base font-semibold",
								children: "Class distribution"
							})]
						}), /* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "Counts for the selected target value."
						})] }), /* @__PURE__ */ jsxs(Button, {
							variant: "outline",
							size: "sm",
							onClick: downloadDataDictionary,
							className: "gap-2",
							children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download data dictionary"]
						})]
					}), classDistribution ? /* @__PURE__ */ jsxs("div", {
						className: "mt-5 grid gap-3",
						children: [classChartData.map((entry) => /* @__PURE__ */ jsx("div", {
							className: "rounded-lg border border-border bg-background p-3",
							children: /* @__PURE__ */ jsxs("div", {
								className: "flex items-center justify-between text-sm text-muted-foreground",
								children: [/* @__PURE__ */ jsx("span", { children: entry.name }), /* @__PURE__ */ jsx("span", {
									className: "font-semibold tabular-nums",
									children: entry.value.toLocaleString()
								})]
							})
						}, entry.name)), /* @__PURE__ */ jsx("div", {
							className: "mt-3 h-64",
							children: /* @__PURE__ */ jsx(ChartContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(PieChart, { children: [/* @__PURE__ */ jsx(Pie, {
									data: classChartData,
									dataKey: "value",
									nameKey: "name",
									innerRadius: 48,
									outerRadius: 80,
									paddingAngle: 2,
									children: classChartData.map((entry, index) => /* @__PURE__ */ jsx(Cell, { fill: [
										"#6366f1",
										"#f59e0b",
										"#10b981",
										"#ef4444"
									][index % 4] }, `cell-${index}`))
								}), /* @__PURE__ */ jsx(Tooltip, { formatter: (value) => [value.toLocaleString(), "Count"] })] })
							})
						})]
					}) : /* @__PURE__ */ jsx("div", {
						className: "mt-4 rounded-xl border border-border bg-muted p-4 text-sm text-muted-foreground",
						children: "Class distribution is not available until a valid target is selected."
					})]
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-4 lg:grid-cols-2",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-2",
						children: [/* @__PURE__ */ jsx(AlertTriangle, { className: "h-4 w-4 text-muted-foreground" }), /* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Duplicate and outlier signals"
						})]
					}), /* @__PURE__ */ jsxs("div", {
						className: "mt-4 space-y-3 text-sm text-muted-foreground",
						children: [/* @__PURE__ */ jsxs("div", {
							className: "rounded-lg border border-border bg-background p-3",
							children: [
								/* @__PURE__ */ jsx("div", {
									className: "text-xs font-medium uppercase tracking-wider text-muted-foreground",
									children: "Duplicate rate"
								}),
								/* @__PURE__ */ jsx("div", {
									className: "mt-1 text-lg font-semibold text-foreground",
									children: duplicateRate !== null ? `${duplicateRate}%` : "—"
								}),
								/* @__PURE__ */ jsx("div", {
									className: "mt-1 text-xs",
									children: duplicateRows !== null ? `${duplicateRows.toLocaleString()} duplicate row${duplicateRows === 1 ? "" : "s"}` : "No duplicate count available"
								})
							]
						}), /* @__PURE__ */ jsxs("div", {
							className: "rounded-lg border border-border bg-background p-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "text-xs font-medium uppercase tracking-wider text-muted-foreground",
								children: "Outlier checks"
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-1 text-sm text-foreground",
								children: outlierEntries.length > 0 ? outlierEntries.slice(0, 4).map(([column, info]) => /* @__PURE__ */ jsxs("div", {
									className: "mt-2 flex items-center justify-between gap-2",
									children: [/* @__PURE__ */ jsx("span", { children: column }), /* @__PURE__ */ jsx("span", {
										className: "font-medium tabular-nums",
										children: info.outlier_fraction ? `${(info.outlier_fraction * 100).toFixed(1)}%` : "0.0%"
									})]
								}, column)) : "No numeric outlier analysis available."
							})]
						})]
					})]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-2",
						children: [/* @__PURE__ */ jsx(Info, { className: "h-4 w-4 text-muted-foreground" }), /* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Correlation snapshot"
						})]
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-4 text-sm text-muted-foreground",
						children: correlationColumns.length > 0 ? /* @__PURE__ */ jsxs("div", {
							className: "rounded-lg border border-border bg-background p-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "text-xs font-medium uppercase tracking-wider text-muted-foreground",
								children: "Numeric correlation matrix"
							}), /* @__PURE__ */ jsxs("div", {
								className: "mt-2 text-sm text-foreground",
								children: [correlationColumns.slice(0, 6).join(", "), correlationColumns.length > 6 ? " …" : ""]
							})]
						}) : /* @__PURE__ */ jsx("div", {
							className: "rounded-lg border border-border bg-background p-3",
							children: "No numeric correlation matrix available for this dataset."
						})
					})]
				})]
			}),
			/* @__PURE__ */ jsxs(Tabs, {
				defaultValue: "summary",
				children: [
					/* @__PURE__ */ jsxs(TabsList, { children: [
						/* @__PURE__ */ jsx(TabsTrigger, {
							value: "summary",
							children: /* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2",
								children: [/* @__PURE__ */ jsx(BarChart3, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Summary Stats" })]
							})
						}),
						/* @__PURE__ */ jsx(TabsTrigger, {
							value: "missing",
							children: /* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2",
								children: [/* @__PURE__ */ jsx(AlertTriangle, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Missing Values" })]
							})
						}),
						/* @__PURE__ */ jsx(TabsTrigger, {
							value: "types",
							children: /* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2",
								children: [/* @__PURE__ */ jsx(Table2, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Column Types" })]
							})
						}),
						/* @__PURE__ */ jsx(TabsTrigger, {
							value: "distributions",
							children: /* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2",
								children: [/* @__PURE__ */ jsx(FileText, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Distributions" })]
							})
						})
					] }),
					/* @__PURE__ */ jsx(TabsContent, {
						value: "summary",
						children: /* @__PURE__ */ jsx("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: summaryStats.length > 0 ? /* @__PURE__ */ jsx("div", {
								className: "overflow-x-auto",
								children: /* @__PURE__ */ jsxs("table", {
									className: "min-w-full border-collapse text-sm",
									children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", { children: Object.keys(summaryStats[0]).map((column) => /* @__PURE__ */ jsx("th", {
										className: "border-b border-border px-3 py-2 text-left text-xs uppercase tracking-wide text-muted-foreground",
										children: column
									}, column)) }) }), /* @__PURE__ */ jsx("tbody", { children: summaryStats.map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
										className: rowIndex % 2 === 0 ? "bg-background" : "bg-card",
										children: Object.values(row).map((value, cellIndex) => /* @__PURE__ */ jsx("td", {
											className: "border-b border-border px-3 py-2 font-mono text-xs text-foreground",
											children: String(value)
										}, cellIndex))
									}, rowIndex)) })]
								})
							}) : /* @__PURE__ */ jsx("div", {
								className: "text-sm text-muted-foreground",
								children: "Summary statistics are not available for this dataset."
							})
						})
					}),
					/* @__PURE__ */ jsx(TabsContent, {
						value: "missing",
						children: /* @__PURE__ */ jsx("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: sortedMissing.length > 0 ? /* @__PURE__ */ jsxs("div", {
								className: "space-y-6",
								children: [/* @__PURE__ */ jsx("div", {
									className: "overflow-x-auto",
									children: /* @__PURE__ */ jsxs("table", {
										className: "min-w-full border-collapse text-sm",
										children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", {
											className: "border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground",
											children: [
												/* @__PURE__ */ jsx("th", {
													className: "px-3 py-2",
													children: "Column"
												}),
												/* @__PURE__ */ jsx("th", {
													className: "px-3 py-2",
													children: "Missing"
												}),
												/* @__PURE__ */ jsx("th", {
													className: "px-3 py-2",
													children: "Share"
												})
											]
										}) }), /* @__PURE__ */ jsx("tbody", { children: sortedMissing.map((row) => /* @__PURE__ */ jsxs("tr", {
											className: "odd:bg-background",
											children: [
												/* @__PURE__ */ jsx("td", {
													className: "border-b border-border px-3 py-2",
													children: row.col
												}),
												/* @__PURE__ */ jsx("td", {
													className: "border-b border-border px-3 py-2 tabular-nums",
													children: row.count.toLocaleString()
												}),
												/* @__PURE__ */ jsxs("td", {
													className: "border-b border-border px-3 py-2",
													children: [row.percentage.toFixed(2), "%"]
												})
											]
										}, row.col)) })]
									})
								}), /* @__PURE__ */ jsx("div", {
									className: "h-80",
									children: /* @__PURE__ */ jsx(ChartContainer, {
										width: "100%",
										height: "100%",
										children: /* @__PURE__ */ jsxs(BarChart$1, {
											data: sortedMissing,
											layout: "vertical",
											margin: {
												left: 30,
												right: 20
											},
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
													fontSize: 11,
													unit: "%"
												}),
												/* @__PURE__ */ jsx(YAxis, {
													type: "category",
													dataKey: "col",
													tickLine: false,
													axisLine: false,
													fontSize: 11,
													width: 170
												}),
												/* @__PURE__ */ jsx(Tooltip, { formatter: (value) => [`${value}%`, "Missing"] }),
												/* @__PURE__ */ jsx(Bar, {
													dataKey: "percentage",
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
								})]
							}) : /* @__PURE__ */ jsx("div", {
								className: "text-sm text-muted-foreground",
								children: "No missing values were detected for this dataset."
							})
						})
					}),
					/* @__PURE__ */ jsx(TabsContent, {
						value: "types",
						children: /* @__PURE__ */ jsx("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant overflow-x-auto",
							children: columnTypeTable.length > 0 ? /* @__PURE__ */ jsxs("table", {
								className: "min-w-full border-collapse text-sm",
								children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", {
									className: "border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground",
									children: Object.keys(columnTypeTable[0]).map((column) => /* @__PURE__ */ jsx("th", {
										className: "px-3 py-2",
										children: column
									}, column))
								}) }), /* @__PURE__ */ jsx("tbody", { children: columnTypeTable.map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
									className: rowIndex % 2 === 0 ? "bg-background" : "bg-card",
									children: Object.values(row).map((value, cellIndex) => /* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs text-foreground",
										children: String(value)
									}, cellIndex))
								}, row.Column)) })]
							}) : /* @__PURE__ */ jsx("div", {
								className: "text-sm text-muted-foreground",
								children: "Column type details are not available for this dataset."
							})
						})
					}),
					/* @__PURE__ */ jsx(TabsContent, {
						value: "distributions",
						children: /* @__PURE__ */ jsx("div", {
							className: "grid gap-4",
							children: distributionHistograms.length > 0 ? distributionHistograms.map((hist) => /* @__PURE__ */ jsxs("div", {
								className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
								children: [/* @__PURE__ */ jsx("div", {
									className: "mb-3 flex items-center justify-between gap-2",
									children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
										className: "text-sm font-semibold",
										children: hist.column
									}), /* @__PURE__ */ jsx("div", {
										className: "text-xs text-muted-foreground",
										children: "Numeric distribution across dataset"
									})] })
								}), /* @__PURE__ */ jsx("div", {
									className: "h-40",
									children: /* @__PURE__ */ jsx(ChartContainer, {
										width: "100%",
										height: "100%",
										children: /* @__PURE__ */ jsxs(BarChart$1, {
											data: hist.bins.map((bin, index) => ({
												bin: `${bin.toFixed(1)}`,
												count: hist.counts[index]
											})),
											children: [
												/* @__PURE__ */ jsx(CartesianGrid, {
													strokeDasharray: "3 3",
													vertical: false
												}),
												/* @__PURE__ */ jsx(XAxis, {
													dataKey: "bin",
													tickLine: false,
													axisLine: false,
													fontSize: 10
												}),
												/* @__PURE__ */ jsx(YAxis, {
													tickLine: false,
													axisLine: false,
													fontSize: 10
												}),
												/* @__PURE__ */ jsx(Tooltip, { formatter: (value) => [value.toLocaleString(), "Count"] }),
												/* @__PURE__ */ jsx(Bar, {
													dataKey: "count",
													fill: "oklch(0.76 0.18 130)",
													radius: 4
												})
											]
										})
									})
								})]
							}, hist.column)) : /* @__PURE__ */ jsx("div", {
								className: "rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground",
								children: "Numeric distributions are not available for this dataset."
							})
						})
					})
				]
			}),
			active && /* @__PURE__ */ jsxs("div", {
				className: "flex gap-3 pt-4",
				children: [/* @__PURE__ */ jsxs(Button, {
					variant: "outline",
					onClick: () => navigate({ to: "/data-upload" }),
					className: "gap-2",
					children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Data Upload"]
				}), /* @__PURE__ */ jsxs(Button, {
					onClick: () => navigate({ to: "/preprocessing" }),
					className: "gap-2 ml-auto",
					children: ["Proceed to Preprocessing", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})]
			})
		]
	});
}
//#endregion
export { Profiling as component };
