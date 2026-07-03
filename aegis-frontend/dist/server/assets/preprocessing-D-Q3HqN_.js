import { n as PageHeader } from "./app-shell-fDQz9JMF.js";
import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-CPpoZWeE.js";
import { t as Button } from "./button-MHHI04mG.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { ArrowLeft, ArrowRight, BarChart, Brain, Download, Hash, Minus, Plus, Settings, Table, Tag, Target, Trash2 } from "lucide-react";
import { Bar, BarChart as BarChart$1, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/preprocessing.tsx?tsr-split=component
function Preprocessing() {
	const { profile, file } = useDataset();
	const navigate = useNavigate();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [preprocess, setPreprocess] = useState(null);
	const [expandedDecisions, setExpandedDecisions] = useState({});
	const [testSize, setTestSize] = useState(.15);
	const [valSize, setValSize] = useState(.15);
	const [randomSeed, setRandomSeed] = useState(42);
	useEffect(() => {
		const runPreprocess = async () => {
			if (!profile) return;
			const allColumns = Array.isArray(profile.columns) ? profile.columns : [];
			let targetCol = null;
			if (allColumns.includes("loan_status")) targetCol = "loan_status";
			else if (Array.isArray(profile.target_candidates) && profile.target_candidates.length > 0) targetCol = profile.target_candidates[0];
			else if (typeof profile.target_col === "string" && profile.target_col.trim() !== "") targetCol = profile.target_col;
			if (!targetCol || targetCol === "string" || targetCol.trim() === "") {
				setError("No valid target column found. Please upload a dataset with a recognized target variable.");
				return;
			}
			setLoading(true);
			setError(null);
			try {
				const form = new FormData();
				if (file) form.append("file", file);
				form.append("target_col", targetCol);
				form.append("test_size", String(testSize));
				form.append("val_size", String(valSize));
				form.append("random_seed", String(randomSeed));
				setPreprocess(await formUpload("/data/preprocess", form));
			} catch (err) {
				setError(err?.body?.detail ?? err?.message ?? "Preprocessing failed.");
				setPreprocess(null);
			} finally {
				setLoading(false);
			}
		};
		runPreprocess();
	}, [
		profile,
		file,
		testSize,
		valSize,
		randomSeed
	]);
	useEffect(() => {
		if (!preprocess?.split_config) return;
		setTestSize(preprocess.split_config.test_size ?? .15);
		setValSize(preprocess.split_config.val_size ?? .15);
		setRandomSeed(preprocess.split_config.random_seed ?? 42);
	}, [preprocess?.split_config]);
	if (!profile) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Preprocessing",
			description: "Reproducible transformations applied to the training dataset."
		}), /* @__PURE__ */ jsxs("div", {
			className: "rounded-xl border border-border bg-card p-6 text-center",
			children: [/* @__PURE__ */ jsx("h3", {
				className: "text-lg font-semibold",
				children: "No dataset available"
			}), /* @__PURE__ */ jsx("p", {
				className: "mt-2 text-sm text-muted-foreground",
				children: "Upload a dataset on the Data Upload page before preprocessing can run."
			})]
		})]
	});
	const summary = {
		feature_count: preprocess?.feature_count ?? preprocess?.summary_metrics?.features_basic,
		duplicates_removed: preprocess?.duplicates_removed ?? preprocess?.summary_metrics?.duplicates_removed ?? 0,
		numeric_feature_count: preprocess?.numeric_feature_count ?? preprocess?.summary_metrics?.numeric_columns,
		categorical_feature_count: preprocess?.categorical_feature_count ?? preprocess?.summary_metrics?.categorical_columns
	};
	const decisions = Array.isArray(preprocess?.preprocessing_report?.decisions) ? preprocess.preprocessing_report.decisions : [];
	const strategySummary = Array.isArray(preprocess?.preprocessing_strategy_summary) ? preprocess.preprocessing_strategy_summary : [];
	const xPreview = Array.isArray(preprocess?.x_preview) ? preprocess.x_preview : [];
	const splitStats = preprocess?.split_stats ?? {};
	const classDistributionData = useMemo(() => {
		if (!Array.isArray(preprocess?.class_distribution_chart)) return [];
		const grouped = {};
		preprocess.class_distribution_chart.forEach((item) => {
			const split = item.split ?? "";
			const klass = item.class ?? "";
			const proportion = Number(item.proportion) ?? 0;
			if (!grouped[split]) grouped[split] = { split };
			grouped[split][klass] = proportion;
		});
		return Object.values(grouped);
	}, [preprocess?.class_distribution_chart]);
	const classKeys = useMemo(() => {
		if (!Array.isArray(preprocess?.class_distribution_chart)) return [];
		return Array.from(new Set(preprocess.class_distribution_chart.map((item) => String(item.class))));
	}, [preprocess?.class_distribution_chart]);
	const targetPreview = Array.isArray(preprocess?.target_preview) ? preprocess.target_preview : [];
	const processedDatasetPreview = Array.isArray(preprocess?.processed_dataset_preview) ? preprocess.processed_dataset_preview : [];
	const downloadProcessedDataset = () => {
		const csv = preprocess?.processed_dataset_csv;
		if (!csv) return;
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = "processed_dataset.csv";
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	};
	const formatStrategyValue = (value) => value ? `${value.charAt(0).toUpperCase()}${value.slice(1)}` : "-";
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Preprocessing",
				description: "Reproducible transformations applied to the training dataset."
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "text-sm font-semibold",
					children: "Step 3 — Preprocessing Config & Train/Val/Test Split"
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: "Finalize X/y, then split immediately so every learned statistic comes from training data only."
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant border-l-4 border-emerald-500/80 bg-emerald-500/10",
				children: [/* @__PURE__ */ jsx("div", {
					className: "text-sm font-semibold text-emerald-900",
					children: "Leakage control"
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-emerald-900/90",
					children: "The dataset is split before any feature engineering. IV/WOE, mutual information, correlation/VIF, variance, frequency maps, binning edges, imputation medians and feature-selection decisions are all learned on the training split only and applied unchanged to validation/test."
				})]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: /* @__PURE__ */ jsxs("div", {
					className: "grid gap-6 xl:grid-cols-[1.2fr_1fr]",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "grid gap-4",
						children: [/* @__PURE__ */ jsxs("div", { children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-sm font-medium",
								children: "Test Size (%)"
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-2 flex items-center gap-3",
								children: [/* @__PURE__ */ jsx("input", {
									type: "range",
									min: .05,
									max: .45,
									step: .05,
									value: testSize,
									onChange: (event) => {
										const value = Number(event.target.value);
										setTestSize(Math.min(value, .95 - valSize));
									},
									className: "flex-1"
								}), /* @__PURE__ */ jsxs("div", {
									className: "w-16 text-right text-sm font-mono",
									children: [Math.round(testSize * 100), "%"]
								})]
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-2 text-xs text-muted-foreground",
								children: splitStats.test_n ? `${splitStats.test_n.toLocaleString()} samples` : "Test split count"
							})
						] }), /* @__PURE__ */ jsxs("div", { children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-sm font-medium",
								children: "Validation Size (%)"
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-2 flex items-center gap-3",
								children: [/* @__PURE__ */ jsx("input", {
									type: "range",
									min: .05,
									max: .45,
									step: .05,
									value: valSize,
									onChange: (event) => {
										const value = Number(event.target.value);
										setValSize(Math.min(value, .95 - testSize));
									},
									className: "flex-1"
								}), /* @__PURE__ */ jsxs("div", {
									className: "w-16 text-right text-sm font-mono",
									children: [Math.round(valSize * 100), "%"]
								})]
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-2 text-xs text-muted-foreground",
								children: splitStats.val_n ? `${splitStats.val_n.toLocaleString()} samples` : "Validation split count"
							})
						] })]
					}), /* @__PURE__ */ jsxs("div", {
						className: "grid gap-4",
						children: [/* @__PURE__ */ jsxs("div", { children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-sm font-medium",
								children: "Random Seed"
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "mt-2 flex items-center gap-2",
								children: [
									/* @__PURE__ */ jsx(Button, {
										type: "button",
										variant: "outline",
										className: "h-9 w-9 p-0",
										onClick: () => setRandomSeed((value) => Math.max(1, value - 1)),
										children: /* @__PURE__ */ jsx(Minus, { className: "h-4 w-4" })
									}),
									/* @__PURE__ */ jsx("div", {
										className: "flex-1 rounded-xl border border-border bg-background px-3 py-2 text-center font-mono text-sm",
										children: randomSeed
									}),
									/* @__PURE__ */ jsx(Button, {
										type: "button",
										variant: "outline",
										className: "h-9 w-9 p-0",
										onClick: () => setRandomSeed((value) => value + 1),
										children: /* @__PURE__ */ jsx(Plus, { className: "h-4 w-4" })
									})
								]
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-2 text-xs text-muted-foreground",
								children: "Ensures reproducible splits and consistent training statistics."
							})
						] }), /* @__PURE__ */ jsxs("div", {
							className: "grid grid-cols-3 gap-3",
							children: [
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-xl border border-border bg-background p-4 text-center",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-xs uppercase tracking-wider text-muted-foreground",
										children: "Train"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-2 text-2xl font-semibold tabular-nums",
										children: splitStats.train_n?.toLocaleString() ?? "—"
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-xl border border-border bg-background p-4 text-center",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-xs uppercase tracking-wider text-muted-foreground",
										children: "Validation"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-2 text-2xl font-semibold tabular-nums",
										children: splitStats.val_n?.toLocaleString() ?? "—"
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-xl border border-border bg-background p-4 text-center",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-xs uppercase tracking-wider text-muted-foreground",
										children: "Test"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-2 text-2xl font-semibold tabular-nums",
										children: splitStats.test_n?.toLocaleString() ?? "—"
									})]
								})
							]
						})]
					})]
				})
			}),
			classDistributionData.length > 0 && /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-center justify-between gap-4",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
						className: "text-sm font-semibold",
						children: "Class Distribution per Split (stratified)"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-sm text-muted-foreground",
						children: "Train, validation and test split proportions by class."
					})] }), /* @__PURE__ */ jsx("div", {
						className: "grid grid-cols-2 gap-2 text-xs",
						children: classKeys.map((label) => /* @__PURE__ */ jsxs("div", {
							className: "inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-muted-foreground",
							children: [/* @__PURE__ */ jsx("span", {
								className: "h-2.5 w-2.5 rounded-full",
								style: { backgroundColor: label === "Y" ? "#65A30D" : label === "N" ? "#84CC16" : "#94a3b8" }
							}), label]
						}, label))
					})]
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-5 h-72",
					children: /* @__PURE__ */ jsx(ChartContainer, {
						width: "100%",
						height: "100%",
						children: /* @__PURE__ */ jsxs(BarChart$1, {
							data: classDistributionData,
							margin: {
								top: 10,
								right: 20,
								left: 0,
								bottom: 0
							},
							children: [
								/* @__PURE__ */ jsx(CartesianGrid, {
									stroke: "rgba(15,23,42,0.06)",
									strokeDasharray: "3 3"
								}),
								/* @__PURE__ */ jsx(XAxis, {
									dataKey: "split",
									tickLine: false,
									axisLine: false,
									fontSize: 12
								}),
								/* @__PURE__ */ jsx(YAxis, {
									tickFormatter: (value) => `${Math.round(value * 100)}%`,
									tickLine: false,
									axisLine: false,
									fontSize: 12
								}),
								/* @__PURE__ */ jsx(Tooltip, {
									contentStyle: {
										borderRadius: 8,
										border: "1px solid rgba(15,23,42,0.06)",
										backgroundColor: "#ffffff"
									},
									formatter: (value) => `${(value * 100).toFixed(1)}%`
								}),
								/* @__PURE__ */ jsx(Legend, {
									verticalAlign: "top",
									height: 36
								}),
								classKeys.map((label, idx) => {
									const palette = [
										"#65A30D",
										"#84CC16",
										"#94a3b8"
									];
									const fill = palette[idx % palette.length];
									return /* @__PURE__ */ jsx(Bar, {
										dataKey: label,
										stackId: "a",
										fill,
										radius: [
											6,
											6,
											0,
											0
										]
									}, label);
								})
							]
						})
					})
				})]
			}),
			/* @__PURE__ */ jsx("div", {
				className: "grid grid-cols-1 gap-4",
				children: /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
						className: "text-sm font-semibold",
						children: "Processed Dataset Preview"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "Preview of the dataset after preprocessing and split selection."
					})] }), /* @__PURE__ */ jsxs(Button, {
						variant: "outline",
						onClick: downloadProcessedDataset,
						className: "gap-2 self-start sm:self-auto",
						children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download Processed Dataset"]
					})]
				})
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "text-sm font-semibold flex items-center",
					children: [/* @__PURE__ */ jsx(Target, { className: "h-4 w-4 mr-2 text-emerald-700" }), "Target Preview"]
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-3 overflow-x-auto",
					children: targetPreview.length > 0 ? /* @__PURE__ */ jsxs("table", {
						className: "min-w-full border-collapse text-sm",
						children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [/* @__PURE__ */ jsx("th", {
							className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
							children: "Index"
						}), /* @__PURE__ */ jsx("th", {
							className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
							children: "Target"
						})] }) }), /* @__PURE__ */ jsx("tbody", { children: targetPreview.map((value, index) => /* @__PURE__ */ jsxs("tr", {
							className: index % 2 === 0 ? "bg-background" : "",
							children: [/* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 font-mono text-xs",
								children: index + 1
							}), /* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 font-mono text-xs",
								children: value === null || value === void 0 ? "" : String(value)
							})]
						}, index)) })]
					}) : /* @__PURE__ */ jsx("div", {
						className: "p-6 text-center text-sm text-muted-foreground",
						children: "No target preview available."
					})
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "text-sm font-semibold flex items-center",
					children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4 mr-2" }), "Processed Dataset Preview"]
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 overflow-x-auto",
					children: processedDatasetPreview.length > 0 ? /* @__PURE__ */ jsxs("table", {
						className: "min-w-full border-collapse text-sm",
						children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", { children: Object.keys(processedDatasetPreview[0]).map((key) => /* @__PURE__ */ jsx("th", {
							className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
							children: key
						}, key)) }) }), /* @__PURE__ */ jsx("tbody", { children: processedDatasetPreview.map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
							className: rowIndex % 2 === 0 ? "bg-background" : "",
							children: Object.values(row).map((cell, cellIndex) => /* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 font-mono text-xs",
								children: cell === null || cell === void 0 ? "" : String(cell)
							}, cellIndex))
						}, rowIndex)) })]
					}) : /* @__PURE__ */ jsx("div", {
						className: "p-6 text-center text-sm text-muted-foreground",
						children: "No processed dataset preview available."
					})
				})]
			}),
			loading && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "🔧 Building adaptive preprocessing pipeline..."
			}),
			error && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-destructive",
				children: error
			}),
			preprocess ? /* @__PURE__ */ jsxs(Fragment, { children: [
				/* @__PURE__ */ jsxs("div", {
					className: "grid grid-cols-1 gap-4 md:grid-cols-4",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "text-sm text-muted-foreground flex items-center",
								children: [/* @__PURE__ */ jsx(Table, { className: "h-4 w-4 mr-2" }), "Features After Prep"]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-3 text-3xl font-semibold tabular-nums",
								children: summary.feature_count ?? "—"
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "text-sm text-muted-foreground flex items-center",
								children: [/* @__PURE__ */ jsx(Trash2, { className: "h-4 w-4 mr-2" }), "Duplicates Removed"]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-3 text-3xl font-semibold tabular-nums",
								children: summary.duplicates_removed ?? 0
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "text-sm text-muted-foreground flex items-center",
								children: [/* @__PURE__ */ jsx(Hash, { className: "h-4 w-4 mr-2" }), "Numeric Columns"]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-3 text-3xl font-semibold tabular-nums",
								children: summary.numeric_feature_count ?? "—"
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "text-sm text-muted-foreground flex items-center",
								children: [/* @__PURE__ */ jsx(Tag, { className: "h-4 w-4 mr-2" }), "Categorical Columns"]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-3 text-3xl font-semibold tabular-nums",
								children: summary.categorical_feature_count ?? "—"
							})]
						})
					]
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "text-sm font-semibold flex items-center",
							children: [/* @__PURE__ */ jsx(Brain, { className: "h-4 w-4 mr-2" }), "Preprocessing Decisions"]
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-2 text-sm text-muted-foreground",
							children: "The system automatically chose preprocessing strategies based on skewness, outliers, missing %, and cardinality."
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 space-y-3",
							children: decisions.length > 0 ? decisions.map((item, index) => {
								const isExpanded = Boolean(expandedDecisions[index]);
								return /* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsxs("button", {
										type: "button",
										className: "flex w-full items-center justify-between text-left",
										onClick: () => setExpandedDecisions((current) => ({
											...current,
											[index]: !current[index]
										})),
										children: [/* @__PURE__ */ jsxs("div", {
											className: "font-medium text-sm",
											children: [
												item.column,
												" (",
												item.type,
												")"
											]
										}), /* @__PURE__ */ jsx("span", {
											className: "text-xs text-muted-foreground",
											children: isExpanded ? "Hide" : "Show"
										})]
									}), isExpanded && Array.isArray(item.actions) && item.actions.length > 0 && /* @__PURE__ */ jsx("ul", {
										className: "mt-2 space-y-1 text-sm text-muted-foreground",
										children: item.actions.map((action, actionIndex) => /* @__PURE__ */ jsxs("li", { children: ["• ", action] }, actionIndex))
									})]
								}, index);
							}) : /* @__PURE__ */ jsx("div", {
								className: "text-sm text-muted-foreground",
								children: "No preprocessing decisions available."
							})
						})
					]
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "text-sm font-semibold flex items-center",
						children: [/* @__PURE__ */ jsx(BarChart, { className: "h-4 w-4 mr-2" }), "Preprocessing Strategy Summary"]
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-4 overflow-x-auto",
						children: strategySummary.length > 0 ? /* @__PURE__ */ jsxs("table", {
							className: "min-w-full border-collapse text-sm",
							children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
								/* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: "Column"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: "Type"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: "Scaler"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: "Imputer"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: "Encoding"
								}),
								/* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: "Outlier strategy"
								})
							] }) }), /* @__PURE__ */ jsx("tbody", { children: strategySummary.map((row, index) => /* @__PURE__ */ jsxs("tr", {
								className: index % 2 === 0 ? "bg-background" : "bg-background/50",
								children: [
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.feature
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.type
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: formatStrategyValue(row.scaler)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: formatStrategyValue(row.imputer)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: formatStrategyValue(row.encoding)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.outlier_strategy ?? "-"
									})
								]
							}, index)) })]
						}) : /* @__PURE__ */ jsx("div", {
							className: "p-6 text-center text-sm text-muted-foreground",
							children: "No preprocessing strategy summary available."
						})
					})]
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "text-sm font-semibold flex items-center",
							children: [/* @__PURE__ */ jsx(Settings, { className: "h-4 w-4 mr-2" }), "Feature Matrix Preview (X)"]
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-2 text-sm text-muted-foreground",
							children: "Preview of the training feature matrix after preprocessing decisions are established."
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-4 overflow-x-auto",
							children: xPreview.length > 0 ? /* @__PURE__ */ jsxs("table", {
								className: "min-w-full border-collapse text-sm",
								children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", { children: Object.keys(xPreview[0]).map((key) => /* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: key
								}, key)) }) }), /* @__PURE__ */ jsx("tbody", { children: xPreview.map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
									className: rowIndex % 2 === 0 ? "bg-background" : "",
									children: Object.values(row).map((cell, cellIndex) => /* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: cell === null || cell === void 0 ? "" : String(cell)
									}, cellIndex))
								}, rowIndex)) })]
							}) : /* @__PURE__ */ jsx("div", {
								className: "p-6 text-center text-sm text-muted-foreground",
								children: "No feature preview available."
							})
						})
					]
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "flex gap-3 pt-4",
					children: [/* @__PURE__ */ jsxs(Button, {
						variant: "outline",
						onClick: () => navigate({ to: "/profiling" }),
						className: "gap-2",
						children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Profiling"]
					}), /* @__PURE__ */ jsxs(Button, {
						onClick: () => navigate({ to: "/features" }),
						className: "gap-2 ml-auto",
						children: ["Proceed to Feature Engineering", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
					})]
				})
			] }) : !loading && !error ? /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "Preparing preprocessing results..."
			}) : null
		]
	});
}
//#endregion
export { Preprocessing as component };
