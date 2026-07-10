import { t as cn } from "./utils-C_uf36nf.js";
import { n as PageHeader } from "./app-shell-7PSh3UZt.js";
import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-B8rOZODa.js";
import { t as Button } from "./button-MHHI04mG.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { a as SelectValue, i as SelectTrigger, n as SelectContent, r as SelectItem, t as Select } from "./select-BHv1JhlL.js";
import * as React$1 from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { AlertTriangle, ArrowLeft, ArrowRight, BarChart, Brain, Check, CheckCircle2, Download, Hash, Info, Loader2, Minus, Plus, Settings, Table, Tag, Target, Trash2 } from "lucide-react";
import { Bar, BarChart as BarChart$1, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as SeparatorPrimitive from "@radix-ui/react-separator";
//#region src/components/ui/card.tsx
var Card = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx("div", {
	ref,
	className: cn("rounded-xl border bg-card text-card-foreground shadow", className),
	...props
}));
Card.displayName = "Card";
var CardHeader = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx("div", {
	ref,
	className: cn("flex flex-col space-y-1.5 p-6", className),
	...props
}));
CardHeader.displayName = "CardHeader";
var CardTitle = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx("div", {
	ref,
	className: cn("font-semibold leading-none tracking-tight", className),
	...props
}));
CardTitle.displayName = "CardTitle";
var CardDescription = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx("div", {
	ref,
	className: cn("text-sm text-muted-foreground", className),
	...props
}));
CardDescription.displayName = "CardDescription";
var CardContent = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx("div", {
	ref,
	className: cn("p-6 pt-0", className),
	...props
}));
CardContent.displayName = "CardContent";
var CardFooter = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx("div", {
	ref,
	className: cn("flex items-center p-6 pt-0", className),
	...props
}));
CardFooter.displayName = "CardFooter";
//#endregion
//#region src/components/ui/checkbox.tsx
var Checkbox = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx(CheckboxPrimitive.Root, {
	ref,
	className: cn("grid place-content-center peer h-4 w-4 shrink-0 rounded-sm border border-primary shadow cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground", className),
	...props,
	children: /* @__PURE__ */ jsx(CheckboxPrimitive.Indicator, {
		className: cn("grid place-content-center text-current"),
		children: /* @__PURE__ */ jsx(Check, { className: "h-4 w-4" })
	})
}));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;
//#endregion
//#region src/components/ui/separator.tsx
var Separator = React$1.forwardRef(({ className, orientation = "horizontal", decorative = true, ...props }, ref) => /* @__PURE__ */ jsx(SeparatorPrimitive.Root, {
	ref,
	decorative,
	orientation,
	className: cn("shrink-0 bg-border", orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]", className),
	...props
}));
Separator.displayName = SeparatorPrimitive.Root.displayName;
//#endregion
//#region src/routes/preprocessing.tsx?tsr-split=component
var TREATMENT_LABELS = {
	unknown_category: "Unknown category",
	zero_fill: "Zero-fill",
	statistical: "Statistical",
	review_flag: "Review (sparse)"
};
var TREATMENT_OPTIONS = [
	"unknown_category",
	"zero_fill",
	"statistical",
	"review_flag"
];
var TRANSFORM_LABELS = {
	none: "None",
	log1p: "Log",
	yeo_johnson: "Yeo-Johnson"
};
var TRANSFORM_OPTIONS = [
	"none",
	"log1p",
	"yeo_johnson"
];
function Preprocessing() {
	const { profile, file, preprocessingResult, setPreprocessingResult } = useDataset();
	const navigate = useNavigate();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [preprocess, setPreprocess] = useState(preprocessingResult ?? null);
	const [testSize, setTestSize] = useState(preprocessingResult?.split_config?.test_size ?? .15);
	const [valSize, setValSize] = useState(preprocessingResult?.split_config?.val_size ?? .15);
	const [randomSeed, setRandomSeed] = useState(preprocessingResult?.split_config?.random_seed ?? 42);
	const [treatmentOverrides, setTreatmentOverrides] = useState({});
	const [dropCols, setDropCols] = useState({});
	const [transformChoices, setTransformChoices] = useState({});
	const [strategyOverride, setStrategyOverride] = useState(null);
	const initializedDefaults = useRef(false);
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
				form.append("treatment_overrides", JSON.stringify(treatmentOverrides));
				form.append("drop_cols", JSON.stringify(Object.entries(dropCols).filter(([, v]) => v).map(([k]) => k)));
				form.append("transform_choices", JSON.stringify(transformChoices));
				if (strategyOverride) form.append("strategy_override", strategyOverride);
				const result = await formUpload("/data/preprocess", form);
				setPreprocess(result);
				setPreprocessingResult(result);
				if (!initializedDefaults.current) {
					const proposal = result?.missing_treatment_proposal ?? {};
					const recommendations = result?.transform_recommendations ?? {};
					const seededDrop = {};
					Object.entries(proposal).forEach(([col, info]) => {
						if (info?.treatment === "review_flag") seededDrop[col] = true;
					});
					const seededTransforms = {};
					Object.entries(recommendations).forEach(([col, rec]) => {
						if (rec?.transform && rec.transform !== "none") seededTransforms[col] = rec.transform;
					});
					if (Object.keys(seededDrop).length > 0) setDropCols(seededDrop);
					if (Object.keys(seededTransforms).length > 0) setTransformChoices(seededTransforms);
					initializedDefaults.current = true;
				}
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
		randomSeed,
		treatmentOverrides,
		dropCols,
		transformChoices,
		strategyOverride
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
	const strategySummary = Array.isArray(preprocess?.preprocessing_strategy_summary) ? preprocess.preprocessing_strategy_summary : [];
	Array.isArray(preprocess?.x_preview) && preprocess.x_preview;
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
	const missingProposal = preprocess?.missing_treatment_proposal ?? {};
	const missingProposalEntries = Object.entries(missingProposal);
	const imputationStrategy = preprocess?.imputation_strategy;
	const recalibratedColumns = preprocess?.recalibrated_columns ?? [];
	const reviewMissingThreshold = preprocess?.review_missing_threshold ?? .4;
	const transformRecommendations = preprocess?.transform_recommendations ?? {};
	const transformDecisions = Object.entries(transformRecommendations).filter(([, rec]) => rec.transform !== "none").sort((a, b) => Math.abs(b[1].skew) - Math.abs(a[1].skew));
	const downloadCsv = (csv, filename) => {
		if (!csv) return;
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	};
	const severityBadge = (skew) => {
		const abs = Math.abs(skew);
		if (abs >= 2) return {
			label: "High skew",
			className: "bg-red-500/15 text-red-700 border-red-500/30"
		};
		if (abs >= 1.5) return {
			label: "Moderate skew",
			className: "bg-amber-500/15 text-amber-700 border-amber-500/30"
		};
		return {
			label: "Strong skew",
			className: "bg-yellow-500/15 text-yellow-700 border-yellow-500/30"
		};
	};
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
					children: "The dataset is split before any feature engineering. Missing-value treatment, imputation strategy, skew/transform recommendations, IV/WOE, correlation/VIF, and feature-selection decisions are all learned on the training split only and applied unchanged to validation/test."
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
										const maxVal = Math.min(value, .95 - valSize);
										setTestSize(maxVal);
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
										const maxVal = Math.min(value, .95 - testSize);
										setValSize(maxVal);
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
			loading && /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground flex items-center justify-center gap-2",
				children: [/* @__PURE__ */ jsx(Loader2, { className: "h-4 w-4 animate-spin" }), "🔧 Building adaptive preprocessing pipeline..."]
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
				/* @__PURE__ */ jsxs(Card, {
					className: "shadow-elegant",
					children: [/* @__PURE__ */ jsxs(CardHeader, { children: [/* @__PURE__ */ jsxs(CardTitle, {
						className: "flex items-center gap-2 text-sm",
						children: [/* @__PURE__ */ jsx(Brain, { className: "h-4 w-4" }), "Missing Value Treatment"]
					}), /* @__PURE__ */ jsx(CardDescription, { children: "Each column is classified by its data shape alone — no column-name guessing. Review the proposal and override anything before it's applied." })] }), /* @__PURE__ */ jsx(CardContent, {
						className: "space-y-4",
						children: missingProposalEntries.length === 0 ? /* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-2 text-sm text-muted-foreground",
							children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-4 w-4 text-emerald-600" }), "No missing values in the training features — imputation not required."]
						}) : /* @__PURE__ */ jsxs(Fragment, { children: [
							/* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-3 text-xs text-muted-foreground leading-relaxed",
								children: [
									/* @__PURE__ */ jsx("span", {
										className: "font-medium text-foreground",
										children: "Unknown category"
									}),
									" — categorical column, filled with an explicit 'Unknown' value.",
									" ",
									/* @__PURE__ */ jsx("span", {
										className: "font-medium text-foreground",
										children: "Zero-fill"
									}),
									" — binary or structural-zero numeric column.",
									" ",
									/* @__PURE__ */ jsx("span", {
										className: "font-medium text-foreground",
										children: "Statistical"
									}),
									" — genuinely missing numeric values, filled jointly via MICE, KNN, or median.",
									" ",
									/* @__PURE__ */ jsx("span", {
										className: "font-medium text-foreground",
										children: "Review"
									}),
									" — over ",
									Math.round(reviewMissingThreshold * 100),
									"% missing, too sparse to impute reliably."
								]
							}),
							missingProposalEntries.sort((a, b) => (b[1].evidence?.missing_pct ?? 0) - (a[1].evidence?.missing_pct ?? 0)).map(([col, info]) => {
								const isDropped = Boolean(dropCols[col]);
								const currentTreatment = treatmentOverrides[col] ?? info.treatment;
								const missingPct = info.evidence?.missing_pct ?? 0;
								const isReviewFlag = info.treatment === "review_flag";
								return /* @__PURE__ */ jsxs("div", {
									className: `rounded-lg border p-3 ${isReviewFlag ? "border-amber-500/40 bg-amber-500/5" : "border-border bg-background"}`,
									children: [
										/* @__PURE__ */ jsxs("div", {
											className: "flex flex-wrap items-center gap-2",
											children: [
												/* @__PURE__ */ jsx("span", {
													className: "font-medium text-sm",
													children: col
												}),
												/* @__PURE__ */ jsxs("span", {
													className: "rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground",
													children: [(missingPct * 100).toFixed(1), "% missing"]
												}),
												isReviewFlag && /* @__PURE__ */ jsxs("span", {
													className: "inline-flex items-center gap-1 rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-xs text-amber-700",
													children: [/* @__PURE__ */ jsx(AlertTriangle, { className: "h-3 w-3" }), "Sparse"]
												})
											]
										}),
										/* @__PURE__ */ jsx("p", {
											className: "mt-1.5 text-xs text-muted-foreground",
											children: info.reason
										}),
										/* @__PURE__ */ jsxs("div", {
											className: "mt-3 flex flex-wrap items-center gap-3",
											children: [/* @__PURE__ */ jsxs("div", {
												className: "flex items-center gap-2",
												children: [/* @__PURE__ */ jsx("span", {
													className: "text-xs text-muted-foreground",
													children: "Treatment"
												}), /* @__PURE__ */ jsxs(Select, {
													value: currentTreatment,
													disabled: isDropped,
													onValueChange: (value) => setTreatmentOverrides((prev) => ({
														...prev,
														[col]: value
													})),
													children: [/* @__PURE__ */ jsx(SelectTrigger, {
														className: "h-8 w-[180px] text-xs",
														children: /* @__PURE__ */ jsx(SelectValue, {})
													}), /* @__PURE__ */ jsx(SelectContent, { children: TREATMENT_OPTIONS.map((opt) => /* @__PURE__ */ jsx(SelectItem, {
														value: opt,
														children: TREATMENT_LABELS[opt]
													}, opt)) })]
												})]
											}), /* @__PURE__ */ jsxs("label", {
												className: "flex items-center gap-2 text-xs text-muted-foreground cursor-pointer",
												children: [/* @__PURE__ */ jsx(Checkbox, {
													checked: isDropped,
													onCheckedChange: (checked) => setDropCols((prev) => ({
														...prev,
														[col]: Boolean(checked)
													}))
												}), "Drop variable — removed entirely, not used in training or evaluation"]
											})]
										})
									]
								}, col);
							}),
							recalibratedColumns.length > 0 && /* @__PURE__ */ jsxs("div", {
								className: "flex items-start gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 text-xs text-sky-900",
								children: [/* @__PURE__ */ jsx(Info, { className: "h-4 w-4 mt-0.5 shrink-0" }), /* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("span", {
										className: "font-medium",
										children: "Recalibrated"
									}),
									" — kept despite being flagged for review, so a real imputation method was found instead of leaving it untreated:",
									" ",
									recalibratedColumns.map((r) => `${r.column} → ${TREATMENT_LABELS[r.treatment] ?? r.treatment}`).join(", ")
								] })]
							}),
							imputationStrategy && /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-3",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "text-sm font-medium",
										children: ["Statistical imputation method: ", /* @__PURE__ */ jsx("span", {
											className: "font-mono",
											children: imputationStrategy.method?.toUpperCase()
										})]
									}),
									/* @__PURE__ */ jsx("p", {
										className: "mt-1 text-xs text-muted-foreground",
										children: imputationStrategy.reason
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-2 flex items-center gap-2",
										children: [/* @__PURE__ */ jsx("span", {
											className: "text-xs text-muted-foreground",
											children: "Override"
										}), /* @__PURE__ */ jsxs(Select, {
											value: strategyOverride ?? "auto",
											onValueChange: (value) => setStrategyOverride(value === "auto" ? null : value),
											children: [/* @__PURE__ */ jsx(SelectTrigger, {
												className: "h-8 w-[160px] text-xs",
												children: /* @__PURE__ */ jsx(SelectValue, {})
											}), /* @__PURE__ */ jsxs(SelectContent, { children: [
												/* @__PURE__ */ jsx(SelectItem, {
													value: "auto",
													children: "Auto (recommended)"
												}),
												/* @__PURE__ */ jsx(SelectItem, {
													value: "mice",
													children: "MICE"
												}),
												/* @__PURE__ */ jsx(SelectItem, {
													value: "knn",
													children: "KNN"
												}),
												/* @__PURE__ */ jsx(SelectItem, {
													value: "median",
													children: "Median"
												})
											] })]
										})]
									})
								]
							})
						] })
					})]
				}),
				/* @__PURE__ */ jsxs(Card, {
					className: "shadow-elegant",
					children: [/* @__PURE__ */ jsxs(CardHeader, { children: [/* @__PURE__ */ jsxs(CardTitle, {
						className: "flex items-center gap-2 text-sm",
						children: [/* @__PURE__ */ jsx(BarChart, { className: "h-4 w-4" }), "Skew-Driven Transforms"]
					}), /* @__PURE__ */ jsx(CardDescription, { children: transformDecisions.length > 0 ? `${transformDecisions.length} of ${Object.keys(transformRecommendations).length} numeric column(s) are skewed enough to matter — everything else is left alone.` : "No numeric columns are skewed enough to need a transform." })] }), transformDecisions.length > 0 && /* @__PURE__ */ jsx(CardContent, {
						className: "space-y-3",
						children: transformDecisions.map(([col, rec]) => {
							const badge = severityBadge(rec.skew);
							const current = transformChoices[col] ?? "none";
							return /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-3",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "flex flex-wrap items-center gap-2",
										children: [
											/* @__PURE__ */ jsx("span", {
												className: "font-medium text-sm",
												children: col
											}),
											/* @__PURE__ */ jsxs("span", {
												className: `rounded-full border px-2 py-0.5 text-xs ${badge.className}`,
												children: [
													badge.label,
													" · ",
													rec.skew.toFixed(2)
												]
											}),
											/* @__PURE__ */ jsxs("span", {
												className: "text-xs text-muted-foreground",
												children: ["recommended: ", /* @__PURE__ */ jsx("span", {
													className: "font-medium text-foreground",
													children: TRANSFORM_LABELS[rec.transform]
												})]
											})
										]
									}),
									/* @__PURE__ */ jsx("p", {
										className: "mt-1.5 text-xs text-muted-foreground",
										children: rec.reason
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-3 flex items-center gap-2",
										children: [/* @__PURE__ */ jsx("span", {
											className: "text-xs text-muted-foreground",
											children: "Apply"
										}), /* @__PURE__ */ jsxs(Select, {
											value: current,
											onValueChange: (value) => setTransformChoices((prev) => ({
												...prev,
												[col]: value
											})),
											children: [/* @__PURE__ */ jsx(SelectTrigger, {
												className: "h-8 w-[160px] text-xs",
												children: /* @__PURE__ */ jsx(SelectValue, {})
											}), /* @__PURE__ */ jsx(SelectContent, { children: TRANSFORM_OPTIONS.map((opt) => /* @__PURE__ */ jsx(SelectItem, {
												value: opt,
												children: TRANSFORM_LABELS[opt]
											}, opt)) })]
										})]
									})
								]
							}, col);
						})
					})]
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
									children: "Transform"
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
										children: row.scaler
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.imputer
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.encoding
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.transform ?? "-"
									})
								]
							}, index)) })]
						}) : /* @__PURE__ */ jsx("div", {
							className: "p-6 text-center text-sm text-muted-foreground",
							children: "No preprocessing strategy summary available."
						})
					})]
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
				/* @__PURE__ */ jsxs("div", {
					className: "grid grid-cols-1 gap-4 sm:grid-cols-2",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
							className: "text-sm font-semibold",
							children: "Original Dataset"
						}), /* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "The dataset exactly as uploaded, before any processing."
						})] }), /* @__PURE__ */ jsxs(Button, {
							variant: "outline",
							onClick: () => downloadCsv(preprocess?.original_dataset_csv, "original_dataset.csv"),
							className: "gap-2 self-start sm:self-auto",
							children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download"]
						})]
					}), /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
							className: "text-sm font-semibold",
							children: "Transformed Dataset"
						}), /* @__PURE__ */ jsx("p", {
							className: "text-xs text-muted-foreground",
							children: "Training split after imputation, scaling and encoding."
						})] }), /* @__PURE__ */ jsxs(Button, {
							variant: "outline",
							onClick: () => downloadCsv(preprocess?.processed_dataset_csv, "transformed_dataset.csv"),
							className: "gap-2 self-start sm:self-auto",
							children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download"]
						})]
					})]
				}),
				/* @__PURE__ */ jsx(Separator, {}),
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
						children: [/* @__PURE__ */ jsx(Settings, { className: "h-4 w-4 mr-2" }), "Processed Dataset Preview"]
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
