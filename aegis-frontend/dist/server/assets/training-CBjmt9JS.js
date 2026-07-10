import { t as cn } from "./utils-C_uf36nf.js";
import { n as PageHeader } from "./app-shell-7PSh3UZt.js";
import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-B8rOZODa.js";
import { t as Button } from "./button-MHHI04mG.js";
import * as React$1 from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { AlertCircle, ArrowLeft, ArrowRight, BarChart3, CheckCircle2, ChevronDown, Info, Loader2, Zap } from "lucide-react";
import { Bar, BarChart as BarChart$1, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
//#region src/components/ui/accordion.tsx
var Accordion = AccordionPrimitive.Root;
var AccordionItem = React$1.forwardRef(({ className, ...props }, ref) => /* @__PURE__ */ jsx(AccordionPrimitive.Item, {
	ref,
	className: cn("border-b", className),
	...props
}));
AccordionItem.displayName = "AccordionItem";
var AccordionTrigger = React$1.forwardRef(({ className, children, ...props }, ref) => /* @__PURE__ */ jsx(AccordionPrimitive.Header, {
	className: "flex",
	children: /* @__PURE__ */ jsxs(AccordionPrimitive.Trigger, {
		ref,
		className: cn("flex flex-1 items-center justify-between py-4 text-sm font-medium cursor-pointer transition-all hover:underline text-left [&[data-state=open]>svg]:rotate-180", className),
		...props,
		children: [children, /* @__PURE__ */ jsx(ChevronDown, { className: "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" })]
	})
}));
AccordionTrigger.displayName = AccordionPrimitive.Trigger.displayName;
var AccordionContent = React$1.forwardRef(({ className, children, ...props }, ref) => /* @__PURE__ */ jsx(AccordionPrimitive.Content, {
	ref,
	className: "overflow-hidden text-sm data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down",
	...props,
	children: /* @__PURE__ */ jsx("div", {
		className: cn("pb-4 pt-0", className),
		children
	})
}));
AccordionContent.displayName = AccordionPrimitive.Content.displayName;
//#endregion
//#region src/routes/training.tsx?tsr-split=component
function Training() {
	const navigate = useNavigate();
	const { profile, file, selectedModel, recommendations, setRecommendations, compareModels, setCompareModels, trainingConfig, trainingResult, comparisonResults, selectedComparisonModel, setSelectedModel, setTrainingConfig, setTrainingResult, setComparisonResults, setSelectedComparisonModel, preprocessingResult } = useDataset();
	const splitConfig = preprocessingResult?.split_config ?? {
		test_size: .15,
		val_size: .15,
		random_seed: 42
	};
	const [config, setConfig] = useState(trainingConfig ?? {
		test_size: splitConfig.test_size,
		val_size: splitConfig.val_size,
		random_seed: splitConfig.random_seed,
		use_cv: false,
		cv_folds: 5,
		use_hyperopt: false,
		use_class_weight: false,
		scale_pos_weight: 1,
		use_feature_engineering: false,
		manual_params: {}
	});
	useEffect(() => {
		setConfig((prev) => ({
			...prev,
			test_size: splitConfig.test_size,
			val_size: splitConfig.val_size,
			random_seed: splitConfig.random_seed
		}));
	}, [
		splitConfig.test_size,
		splitConfig.val_size,
		splitConfig.random_seed
	]);
	const [trainingInfo, setTrainingInfo] = useState(trainingResult?.training_info ?? null);
	const [splitStats, setSplitStats] = useState(trainingResult?.split_stats ?? preprocessingResult?.split_stats ?? null);
	const [evaluationMetrics, setEvaluationMetrics] = useState(trainingResult?.evaluation_metrics ?? null);
	const [modelArtifact, setModelArtifact] = useState(trainingResult?.model_artifact ?? null);
	const [taskType, setTaskType] = useState(trainingResult?.task_type ?? null);
	const [trainingModelName, setTrainingModelName] = useState(trainingResult?.model_name ?? selectedModel?.name ?? null);
	const [trainingConfigResult, setTrainingConfigResult] = useState(trainingResult?.training_config ?? null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [modelComparison, setModelComparison] = useState(false);
	const [modelsToCompare, setModelsToCompare] = useState(compareModels ?? []);
	const [hyperparams, setHyperparams] = useState({
		learning_rate: .05,
		max_depth: 6,
		n_estimators: 200,
		subsample: .8,
		colsample_bytree: .8,
		reg_lambda: 1,
		reg_alpha: 0
	});
	const [trainingStats, setTrainingStats] = useState(null);
	const [recommendationTaskType, setRecommendationTaskType] = useState(null);
	const [modelsLoading, setModelsLoading] = useState(false);
	const [modelsError, setModelsError] = useState(null);
	const fetchRef = useRef(false);
	const datasetSummary = useMemo(() => {
		if (trainingStats) return {
			sampleCount: trainingStats.train_n,
			featureCount: trainingStats.train_features,
			imbalanceRatio: trainingStats.imbalance_ratio
		};
		if (!profile) return null;
		const shape = profile.shape ?? [0, 0];
		const sampleCount = shape[0] ?? 0;
		const featureCount = shape[1] ?? 0;
		let imbalanceRatio = 1;
		if (profile.class_distribution && typeof profile.class_distribution === "object") {
			const values = Object.values(profile.class_distribution);
			if (values.length >= 2) {
				const sorted = values.sort((a, b) => b - a);
				imbalanceRatio = sorted[0] / (sorted[1] || 1);
			}
		}
		return {
			sampleCount,
			featureCount,
			imbalanceRatio
		};
	}, [profile, trainingStats]);
	const transformedModels = useMemo(() => {
		if (!recommendations || !Array.isArray(recommendations) || recommendations.length === 0) return [];
		return recommendations.map((rec, idx) => ({
			...rec,
			selected: rec.name === selectedModel?.name || !selectedModel && idx === 0
		}));
	}, [recommendations, selectedModel]);
	useEffect(() => {
		if (!profile || !file) return;
		fetchRef.current = false;
		if (recommendations && recommendations.length > 0) return;
		if (fetchRef.current) return;
		let isMounted = true;
		const loadRecommendations = async () => {
			setModelsLoading(true);
			setModelsError(null);
			try {
				const form = new FormData();
				form.append("file", file);
				form.append("target_col", profile.target_col || "loan_status");
				const response = await formUpload("/models/recommend", form);
				if (!isMounted) return;
				if (response?.training) setTrainingStats(response.training);
				if (response?.task_type) setRecommendationTaskType(response.task_type);
				const recs = response?.recommendations ?? response?.recommendations_list ?? response?.data ?? null;
				if (recs && Array.isArray(recs)) {
					const transformed = recs.map((rec) => ({
						name: rec.name,
						score: typeof rec.score === "number" ? rec.score : 5,
						description: rec.description ?? "",
						why: rec.why ?? rec.description ?? "",
						best_for: rec.best_for ?? [],
						icon: rec.icon
					}));
					setRecommendations(transformed);
					const currentModelName = selectedModel?.name;
					if (!(currentModelName ? transformed.some((m) => m.name === currentModelName) : false) && transformed.length > 0) setSelectedModel(transformed[0]);
					const validCompareModels = (compareModels ?? []).filter((name) => transformed.some((m) => m.name === name));
					if (validCompareModels.length === 0 && transformed.length > 0) setCompareModels(transformed.slice(0, Math.min(3, transformed.length)).map((m) => m.name));
					else if (validCompareModels.length !== (compareModels ?? []).length) setCompareModels(validCompareModels);
				} else setModelsError("No recommendations returned by backend.");
			} catch (err) {
				console.error("Training: failed to load model recommendations", err);
				if (!isMounted) return;
				setModelsError(err?.body?.detail ?? err?.message ?? "Failed to load model recommendations.");
			} finally {
				if (isMounted) setModelsLoading(false);
			}
		};
		fetchRef.current = true;
		loadRecommendations();
		return () => {
			isMounted = false;
		};
	}, [
		file,
		profile,
		recommendations,
		selectedModel,
		compareModels,
		setRecommendations,
		setSelectedModel,
		setCompareModels
	]);
	const handleSelectModel = useCallback((model) => {
		setSelectedModel(model);
	}, [setSelectedModel]);
	useCallback((modelName) => {
		const current = compareModels ?? [];
		const next = current.includes(modelName) ? current.filter((m) => m !== modelName) : [...current, modelName];
		setCompareModels(next);
	}, [compareModels, setCompareModels]);
	const displaySplitStats = splitStats ?? preprocessingResult?.split_stats ?? null;
	const trainModel = async (modelName) => {
		if (!profile || !file) throw new Error("Missing profile or file");
		const trainForm = new FormData();
		trainForm.append("file", file);
		trainForm.append("target_col", profile.target_col || "loan_status");
		trainForm.append("model_name", modelName);
		trainForm.append("test_size", String(config.test_size));
		trainForm.append("val_size", String(config.val_size));
		trainForm.append("random_seed", String(config.random_seed));
		trainForm.append("use_cv", String(config.use_cv));
		trainForm.append("cv_folds", String(config.cv_folds));
		trainForm.append("use_hyperopt", String(config.use_hyperopt));
		trainForm.append("use_class_weight", String(config.use_class_weight));
		trainForm.append("scale_pos_weight", String(config.scale_pos_weight));
		trainForm.append("use_feature_engineering", String(config.use_feature_engineering));
		if (Object.keys(config.manual_params).length > 0) trainForm.append("manual_params", JSON.stringify(config.manual_params));
		const trainResponse = await formUpload("/models/train", trainForm);
		if (!trainResponse?.training_info || !trainResponse?.split_stats || !trainResponse?.model_artifact) throw new Error("Training response missing required fields.");
		return {
			model_name: modelName,
			task_type: trainResponse.task_type ?? "binary",
			real_feature_names: trainResponse.real_feature_names ?? [],
			training_config: trainResponse.training_config ?? null,
			training_info: trainResponse.training_info,
			split_stats: trainResponse.split_stats,
			feature_engineering_summary: trainResponse.feature_engineering_summary ?? null,
			model_artifact: trainResponse.model_artifact,
			evaluation_metrics: trainResponse.evaluation_metrics ?? null,
			evaluation_data: trainResponse.evaluation_data ?? null
		};
	};
	const handleTrain = async () => {
		if (!profile || !file || !selectedModel) {
			setError("Missing profile, file, or model selection");
			return;
		}
		setLoading(true);
		setError(null);
		setModelComparison(false);
		try {
			const result = await trainModel(selectedModel.name);
			setTrainingInfo(result.training_info);
			setSplitStats(result.split_stats);
			setEvaluationMetrics(result.evaluation_metrics);
			setModelArtifact(result.model_artifact);
			setTaskType(result.task_type);
			setTrainingModelName(result.model_name);
			setTrainingConfigResult(result.training_config ?? null);
			setComparisonResults([{
				model_name: result.model_name,
				...result.evaluation_metrics,
				training_time_s: result.training_info.training_time_s
			}]);
			setTrainingResult({
				task_type: result.task_type,
				model_name: result.model_name,
				real_feature_names: result.real_feature_names ?? [],
				training_config: result.training_config ?? null,
				training_info: result.training_info,
				split_stats: result.split_stats,
				feature_engineering_summary: result.feature_engineering_summary,
				evaluation_metrics: result.evaluation_metrics,
				evaluation_data: result.evaluation_data,
				model_artifact: result.model_artifact
			});
		} catch (err) {
			console.error("Training: failed", err);
			setError(err?.body?.detail ?? err?.message ?? "Failed to train model.");
		} finally {
			setLoading(false);
		}
	};
	const handleQuickComparison = async () => {
		if (!profile || !file || !selectedModel) {
			setError("Missing profile, file, or model selection");
			return;
		}
		if (modelsToCompare.length === 0) {
			setError("Select at least one model to compare");
			return;
		}
		setLoading(true);
		setError(null);
		setModelComparison(true);
		try {
			const candidateModelNames = [selectedModel.name, ...modelsToCompare.filter((name) => name !== selectedModel.name)];
			const rows = [];
			for (const modelName of candidateModelNames) {
				const result = await trainModel(modelName);
				rows.push({
					model_name: modelName,
					roc_auc: result.evaluation_metrics?.roc_auc,
					recall: result.evaluation_metrics?.recall,
					precision: result.evaluation_metrics?.precision,
					f1: result.evaluation_metrics?.f1,
					pr_auc: result.evaluation_metrics?.pr_auc,
					accuracy: result.evaluation_metrics?.accuracy,
					training_time_s: result.training_info.training_time_s
				});
				if (modelName === selectedModel.name) {
					setTrainingInfo(result.training_info);
					setSplitStats(result.split_stats);
					setEvaluationMetrics(result.evaluation_metrics);
					setModelArtifact(result.model_artifact);
					setTaskType(result.task_type);
					setTrainingModelName(result.model_name);
					setTrainingConfigResult(result.training_config ?? null);
					setTrainingResult({
						task_type: result.task_type,
						model_name: result.model_name,
						real_feature_names: result.real_feature_names ?? [],
						training_config: result.training_config ?? null,
						training_info: result.training_info,
						split_stats: result.split_stats,
						feature_engineering_summary: result.feature_engineering_summary,
						evaluation_metrics: result.evaluation_metrics,
						evaluation_data: result.evaluation_data,
						model_artifact: result.model_artifact
					});
				}
			}
			setComparisonResults(rows);
			setSelectedComparisonModel(candidateModelNames[0]);
		} catch (err) {
			console.error("Comparison: failed", err);
			setError(err?.body?.detail ?? err?.message ?? "Failed to run comparison.");
		} finally {
			setLoading(false);
		}
	};
	const usedTrainingConfig = trainingConfigResult ?? trainingResult?.training_config ?? config;
	const classImbalance = useMemo(() => {
		const trainingDist = splitStats?.train_class_dist ?? profile?.class_distribution;
		if (!trainingDist) return 1;
		const values = Object.values(trainingDist);
		if (values.length < 2) return 1;
		const sorted = [...values].sort((a, b) => b - a);
		return sorted[0] / (sorted[1] || 1);
	}, [splitStats?.train_class_dist, profile?.class_distribution]);
	const classLabels = useMemo(() => {
		if (splitStats?.train_class_dist) return Object.keys(splitStats.train_class_dist);
		return [];
	}, [splitStats]);
	const splitClassData = useMemo(() => {
		if (!splitStats?.train_class_dist || !splitStats?.val_class_dist || !splitStats?.test_class_dist) return [];
		return [
			{
				split: "Train",
				dist: splitStats.train_class_dist
			},
			{
				split: "Val",
				dist: splitStats.val_class_dist
			},
			{
				split: "Test",
				dist: splitStats.test_class_dist
			}
		].map((item) => {
			const row = { split: item.split };
			classLabels.forEach((label) => {
				row[label] = Number(item.dist?.[label] ?? 0);
			});
			return row;
		});
	}, [splitStats, classLabels]);
	useEffect(() => {
		setTrainingConfig(config);
	}, [config, setTrainingConfig]);
	useEffect(() => {
		if (compareModels && compareModels.length > 0) setModelsToCompare(compareModels);
	}, [compareModels]);
	useEffect(() => {
		setCompareModels(modelsToCompare);
	}, [modelsToCompare, setCompareModels]);
	if (!profile) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Training",
			description: "Pick a model and configure training."
		}), /* @__PURE__ */ jsxs("div", {
			className: "rounded-xl border border-border bg-card p-6 text-center",
			children: [/* @__PURE__ */ jsx("h3", {
				className: "text-lg font-semibold",
				children: "No dataset available"
			}), /* @__PURE__ */ jsx("p", {
				className: "mt-2 text-sm text-muted-foreground",
				children: "Upload and preprocess a dataset before training."
			})]
		})]
	});
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Training",
				description: selectedModel ? `Configure and train the ${selectedModel.name} model with optimized parameters.` : "Models ranked by suitability for your dataset — pick one to train."
			}),
			error && /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-destructive bg-destructive/5 p-4 text-sm text-destructive flex gap-3",
				children: [/* @__PURE__ */ jsx(AlertCircle, { className: "h-5 w-5 flex-shrink-0 mt-0.5" }), /* @__PURE__ */ jsx("div", { children: error })]
			}),
			modelsError && /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-destructive bg-destructive/5 p-4 text-sm text-destructive flex gap-3",
				children: [/* @__PURE__ */ jsx(AlertCircle, { className: "h-5 w-5 flex-shrink-0 mt-0.5" }), /* @__PURE__ */ jsx("div", { children: modelsError })]
			}),
			datasetSummary && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "text-sm text-muted-foreground",
					children: "Dataset summary"
				}), /* @__PURE__ */ jsxs("div", {
					className: "mt-2 text-lg font-semibold",
					children: [
						"Dataset: ",
						datasetSummary.sampleCount.toLocaleString(),
						" samples × ",
						datasetSummary.featureCount,
						" features | Imbalance ratio: ",
						datasetSummary.imbalanceRatio.toFixed(1),
						":1"
					]
				})]
			}),
			modelsLoading && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "Loading model recommendations..."
			}),
			transformedModels.length === 0 && !modelsLoading && !modelsError && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "No model recommendations available."
			}),
			transformedModels.length > 0 && /* @__PURE__ */ jsxs(Fragment, { children: [
				/* @__PURE__ */ jsxs("section", { children: [
					/* @__PURE__ */ jsx("h2", {
						className: "mb-4 text-base font-semibold",
						children: "Recommended Models"
					}),
					/* @__PURE__ */ jsx("p", {
						className: "mb-4 text-sm text-muted-foreground",
						children: "These candidates are ranked by suitability and can be compared on the same split after training."
					}),
					/* @__PURE__ */ jsx("div", {
						className: "grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3",
						children: transformedModels.map((m, index) => {
							const rankBadge = `Rank ${index + 1}`;
							return /* @__PURE__ */ jsxs("button", {
								type: "button",
								onClick: () => handleSelectModel(m),
								className: `relative flex flex-col rounded-2xl border p-6 shadow-elegant text-left transition ${m.selected ? "border-primary bg-primary/5" : "border-border bg-card hover:border-primary/50"}`,
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-start justify-between gap-3",
										children: [/* @__PURE__ */ jsx("div", {
											className: "space-y-2",
											children: /* @__PURE__ */ jsxs("div", {
												className: "flex items-center gap-2",
												children: [/* @__PURE__ */ jsx("span", {
													className: "text-sm uppercase tracking-wider text-muted-foreground",
													children: rankBadge
												}), /* @__PURE__ */ jsx("h3", {
													className: "text-base font-semibold",
													children: m.name
												})]
											})
										}), /* @__PURE__ */ jsxs("div", {
											className: "text-right",
											children: [/* @__PURE__ */ jsxs("div", {
												className: "text-2xl font-semibold tabular-nums",
												children: [m.score, "/10"]
											}), /* @__PURE__ */ jsx("div", {
												className: "text-[11px] uppercase tracking-wider text-muted-foreground",
												children: "Score"
											})]
										})]
									}),
									/* @__PURE__ */ jsx("p", {
										className: "mt-4 text-sm text-muted-foreground",
										children: m.description
									}),
									/* @__PURE__ */ jsxs("dl", {
										className: "mt-4 space-y-3 text-sm",
										children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
											className: "text-[11px] uppercase tracking-wider text-muted-foreground",
											children: "Why recommended"
										}), /* @__PURE__ */ jsx("dd", {
											className: "mt-1 text-foreground/90",
											children: m.why || m.description
										})] }), m.best_for?.length ? /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
											className: "text-[11px] uppercase tracking-wider text-muted-foreground",
											children: "Best for"
										}), /* @__PURE__ */ jsx("dd", {
											className: "mt-1 text-foreground/90",
											children: m.best_for.join(" · ")
										})] }) : null]
									}),
									m.selected && /* @__PURE__ */ jsxs("div", {
										className: "mt-4 inline-flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary",
										children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-3 w-3" }), " Selected to train"]
									})
								]
							}, m.name);
						})
					})
				] }),
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "mb-4 text-base font-semibold",
							children: "Select model to train"
						}),
						/* @__PURE__ */ jsx("select", {
							value: selectedModel?.name ?? transformedModels[0]?.name,
							onChange: (e) => {
								const next = transformedModels.find((m) => m.name === e.target.value);
								if (next) setSelectedModel(next);
							},
							className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
							children: transformedModels.map((model) => /* @__PURE__ */ jsx("option", {
								value: model.name,
								children: model.name
							}, model.name))
						}),
						/* @__PURE__ */ jsx("p", {
							className: "mt-2 text-sm text-muted-foreground",
							children: "The top-ranked model is pre-selected. You can change this."
						})
					]
				}),
				recommendationTaskType === "binary" && /* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Credit Risk Evaluation Strategy"
						}),
						/* @__PURE__ */ jsxs("p", {
							className: "mt-3 text-sm text-muted-foreground",
							children: [
								"In credit risk, ",
								/* @__PURE__ */ jsx("strong", { children: "Recall" }),
								" is the most critical metric because failing to identify a truly risky customer (false negative) is far more costly than incorrectly flagging a safe one."
							]
						}),
						/* @__PURE__ */ jsxs("p", {
							className: "mt-2 text-sm text-muted-foreground",
							children: ["We optimize for: ", /* @__PURE__ */ jsx("strong", { children: "ROC-AUC → Recall → PR-AUC → F1" })]
						})
					]
				})
			] }),
			!selectedModel && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "Select a model above to configure and run training."
			}),
			selectedModel && /* @__PURE__ */ jsxs(Fragment, { children: [
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-2 mb-4",
						children: [/* @__PURE__ */ jsx(BarChart3, { className: "h-5 w-5 text-primary" }), /* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Data Split (locked in during Preprocessing)"
						})]
					}), displaySplitStats ? /* @__PURE__ */ jsxs(Fragment, { children: [/* @__PURE__ */ jsx("div", {
						className: "grid grid-cols-1 md:grid-cols-3 gap-6",
						children: (() => {
							const totalN = displaySplitStats.total ?? Number(displaySplitStats.train_n ?? 0) + Number(displaySplitStats.val_n ?? 0) + Number(displaySplitStats.test_n ?? 0);
							const pct = (n) => totalN ? n / totalN * 100 : 0;
							return /* @__PURE__ */ jsxs(Fragment, { children: [
								/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("div", {
										className: "text-xs uppercase tracking-wider text-muted-foreground",
										children: "Train"
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-1 text-2xl font-semibold tabular-nums",
										children: [pct(displaySplitStats.train_n).toFixed(0), "%"]
									}),
									/* @__PURE__ */ jsxs("p", {
										className: "text-xs text-muted-foreground mt-1",
										children: [Number(displaySplitStats.train_n ?? 0).toLocaleString(), " samples"]
									})
								] }),
								/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("div", {
										className: "text-xs uppercase tracking-wider text-muted-foreground",
										children: "Validation"
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-1 text-2xl font-semibold tabular-nums",
										children: [pct(displaySplitStats.val_n).toFixed(0), "%"]
									}),
									/* @__PURE__ */ jsxs("p", {
										className: "text-xs text-muted-foreground mt-1",
										children: [Number(displaySplitStats.val_n ?? 0).toLocaleString(), " samples"]
									})
								] }),
								/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("div", {
										className: "text-xs uppercase tracking-wider text-muted-foreground",
										children: "Test"
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-1 text-2xl font-semibold tabular-nums",
										children: [pct(displaySplitStats.test_n).toFixed(0), "%"]
									}),
									/* @__PURE__ */ jsxs("p", {
										className: "text-xs text-muted-foreground mt-1",
										children: [Number(displaySplitStats.test_n ?? 0).toLocaleString(), " samples"]
									})
								] })
							] });
						})()
					}), /* @__PURE__ */ jsxs("p", {
						className: "mt-4 text-sm text-muted-foreground",
						children: [
							"Random seed: ",
							/* @__PURE__ */ jsx("span", {
								className: "font-mono",
								children: config.random_seed
							}),
							". Feature engineering is re-learned on the training split only, then applied unchanged to validation/test. To change the split ratio or seed, go back to Preprocessing."
						]
					})] }) : /* @__PURE__ */ jsxs("p", {
						className: "text-sm text-muted-foreground",
						children: [
							"No split found yet. ",
							/* @__PURE__ */ jsx(Button, {
								variant: "link",
								className: "px-0 h-auto",
								onClick: () => navigate({ to: "/preprocessing" }),
								children: "Run Preprocessing"
							}),
							" first — the split happens there and Training reuses it."
						]
					})]
				}),
				splitStats && classLabels.length > 0 && /* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold mb-4",
							children: "Class Distribution per Split"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "h-72",
							children: /* @__PURE__ */ jsx(ResponsiveContainer, {
								width: "100%",
								height: "100%",
								children: /* @__PURE__ */ jsxs(BarChart$1, {
									data: splitClassData,
									margin: {
										top: 10,
										right: 12,
										left: -12,
										bottom: 0
									},
									children: [
										/* @__PURE__ */ jsx(CartesianGrid, {
											strokeDasharray: "3 3",
											stroke: "#374151"
										}),
										/* @__PURE__ */ jsx(XAxis, {
											dataKey: "split",
											stroke: "#9ca3af"
										}),
										/* @__PURE__ */ jsx(YAxis, { stroke: "#9ca3af" }),
										/* @__PURE__ */ jsx(Tooltip, {
											contentStyle: {
												backgroundColor: "#0f172a",
												borderColor: "#334155"
											},
											formatter: (value) => value.toLocaleString?.() ?? value
										}),
										classLabels.map((label, index) => /* @__PURE__ */ jsx(Bar, {
											dataKey: label,
											stackId: "a",
											fill: index === 0 ? "#22c55e" : index === 1 ? "#ef4444" : index === 2 ? "#3b82f6" : "#f59e0b"
										}, label))
									]
								})
							})
						}),
						/* @__PURE__ */ jsx("div", {
							className: "mt-6 grid grid-cols-1 md:grid-cols-3 gap-4",
							children: (() => {
								const distributionSource = splitStats?.train_class_counts ? Object.entries(splitStats.train_class_counts).map(([label, count]) => ({
									label,
									count: Number(count)
								})) : [];
								const maxCount = Math.max(...distributionSource.map((item) => item.count), 1);
								return distributionSource.map(({ label, count }) => /* @__PURE__ */ jsxs("div", {
									className: "bg-muted rounded-lg p-4",
									children: [
										/* @__PURE__ */ jsxs("div", {
											className: "text-xs uppercase tracking-wider text-muted-foreground",
											children: ["Class ", label]
										}),
										/* @__PURE__ */ jsx("div", {
											className: "mt-2 text-2xl font-semibold",
											children: count.toLocaleString()
										}),
										/* @__PURE__ */ jsx("div", {
											className: "mt-2 h-2 bg-primary/20 rounded-full overflow-hidden",
											children: /* @__PURE__ */ jsx("div", {
												className: "h-full bg-primary",
												style: { width: `${Math.min(count / maxCount * 100, 100)}%` }
											})
										})
									]
								}, label));
							})()
						}),
						classImbalance > 1.5 && /* @__PURE__ */ jsxs("div", {
							className: "mt-4 p-3 bg-orange-500/10 border border-orange-200 rounded-lg flex gap-2",
							children: [/* @__PURE__ */ jsx(Info, { className: "h-4 w-4 text-orange-600 flex-shrink-0 mt-0.5" }), /* @__PURE__ */ jsxs("div", {
								className: "text-xs text-orange-900",
								children: [
									/* @__PURE__ */ jsx("strong", { children: "Class Imbalance Detected:" }),
									" ",
									classImbalance.toFixed(2),
									"x ratio. Consider enabling class balancing below."
								]
							})]
						})
					]
				}),
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold mb-4",
						children: "Class Balancing"
					}), /* @__PURE__ */ jsxs("div", {
						className: "space-y-4",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "flex items-center justify-between",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium",
									children: "Use Balanced Class Weights"
								}), /* @__PURE__ */ jsx("p", {
									className: "text-xs text-muted-foreground mt-1",
									children: "Automatically weight classes inversely proportional to frequencies"
								})] }), /* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: config.use_class_weight,
									onChange: (e) => setConfig((prev) => ({
										...prev,
										use_class_weight: e.target.checked
									})),
									className: "w-5 h-5"
								})]
							}),
							selectedModel.name === "XGBoost" && /* @__PURE__ */ jsxs("div", { children: [
								/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium block mb-2",
									children: "Scale Positive Weight (XGBoost)"
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "flex items-baseline gap-3",
									children: [/* @__PURE__ */ jsx("input", {
										type: "range",
										min: "1",
										max: "10",
										step: "0.5",
										value: config.scale_pos_weight,
										onChange: (e) => setConfig((prev) => ({
											...prev,
											scale_pos_weight: parseFloat(e.target.value)
										})),
										disabled: !config.use_class_weight,
										className: "flex-1"
									}), /* @__PURE__ */ jsx("span", {
										className: "text-sm font-mono w-12 text-right",
										children: config.scale_pos_weight.toFixed(1)
									})]
								}),
								/* @__PURE__ */ jsxs("p", {
									className: "text-xs text-muted-foreground mt-1",
									children: [
										"Weights positive class; recommended when imbalance ",
										">",
										" 2x"
									]
								})
							] }),
							classImbalance > 2 && /* @__PURE__ */ jsx("div", {
								className: "p-3 bg-blue-500/10 border border-blue-200 rounded-lg",
								children: /* @__PURE__ */ jsxs("p", {
									className: "text-xs text-blue-900",
									children: [
										/* @__PURE__ */ jsx("strong", { children: "Recommendation:" }),
										" Your dataset shows ",
										classImbalance.toFixed(1),
										"x class imbalance. Using ",
										/* @__PURE__ */ jsx("code", {
											className: "bg-blue-200 px-1 rounded",
											children: "class_weight=\"balanced\""
										}),
										" is strongly recommended."
									]
								})
							})
						]
					})]
				}),
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold mb-4",
						children: "Cross Validation & Hyperparameter Tuning"
					}), /* @__PURE__ */ jsxs("div", {
						className: "grid grid-cols-1 md:grid-cols-2 gap-6",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "flex items-center justify-between",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium",
									children: "Enable Cross Validation"
								}), /* @__PURE__ */ jsx("p", {
									className: "text-xs text-muted-foreground mt-1",
									children: "Assess model stability across data splits"
								})] }), /* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: config.use_cv,
									onChange: (e) => setConfig((prev) => ({
										...prev,
										use_cv: e.target.checked
									})),
									className: "w-5 h-5"
								})]
							}),
							config.use_cv && /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
								className: "text-sm font-medium block mb-2",
								children: "CV Folds"
							}), /* @__PURE__ */ jsx("input", {
								type: "number",
								min: "2",
								max: "10",
								value: config.cv_folds,
								onChange: (e) => setConfig((prev) => ({
									...prev,
									cv_folds: parseInt(e.target.value) || 5
								})),
								className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
							})] }),
							/* @__PURE__ */ jsxs("div", {
								className: "flex items-center justify-between",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium",
									children: "Enable Hyperparameter Tuning"
								}), /* @__PURE__ */ jsx("p", {
									className: "text-xs text-muted-foreground mt-1",
									children: "Randomized search for optimal parameters"
								})] }), /* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: config.use_hyperopt,
									onChange: (e) => setConfig((prev) => ({
										...prev,
										use_hyperopt: e.target.checked
									})),
									className: "w-5 h-5"
								})]
							})
						]
					})]
				}),
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold mb-4",
							children: "Manual Hyperparameter Controls"
						}),
						/* @__PURE__ */ jsx("div", {
							className: "grid grid-cols-1 md:grid-cols-2 gap-4",
							children: selectedModel.name !== "Logistic Regression" && /* @__PURE__ */ jsxs(Fragment, { children: [
								/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium block mb-2",
									children: "Learning Rate"
								}), /* @__PURE__ */ jsx("input", {
									type: "number",
									min: "0.001",
									max: "1",
									step: "0.01",
									value: hyperparams.learning_rate,
									onChange: (e) => setHyperparams((prev) => ({
										...prev,
										learning_rate: parseFloat(e.target.value)
									})),
									className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
								})] }),
								/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium block mb-2",
									children: "Max Depth"
								}), /* @__PURE__ */ jsx("input", {
									type: "number",
									min: "1",
									max: "30",
									value: hyperparams.max_depth,
									onChange: (e) => setHyperparams((prev) => ({
										...prev,
										max_depth: parseInt(e.target.value) || 6
									})),
									className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
								})] }),
								/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
									className: "text-sm font-medium block mb-2",
									children: "N Estimators"
								}), /* @__PURE__ */ jsx("input", {
									type: "number",
									min: "10",
									max: "1000",
									step: "10",
									value: hyperparams.n_estimators,
									onChange: (e) => setHyperparams((prev) => ({
										...prev,
										n_estimators: parseInt(e.target.value) || 200
									})),
									className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
								})] }),
								selectedModel.name === "XGBoost" && /* @__PURE__ */ jsxs(Fragment, { children: [
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
										className: "text-sm font-medium block mb-2",
										children: "Subsample"
									}), /* @__PURE__ */ jsx("input", {
										type: "number",
										min: "0.1",
										max: "1",
										step: "0.1",
										value: hyperparams.subsample,
										onChange: (e) => setHyperparams((prev) => ({
											...prev,
											subsample: parseFloat(e.target.value)
										})),
										className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
									})] }),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
										className: "text-sm font-medium block mb-2",
										children: "Colsample Bytree"
									}), /* @__PURE__ */ jsx("input", {
										type: "number",
										min: "0.1",
										max: "1",
										step: "0.1",
										value: hyperparams.colsample_bytree,
										onChange: (e) => setHyperparams((prev) => ({
											...prev,
											colsample_bytree: parseFloat(e.target.value)
										})),
										className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
									})] }),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
										className: "text-sm font-medium block mb-2",
										children: "Reg Lambda"
									}), /* @__PURE__ */ jsx("input", {
										type: "number",
										min: "0",
										max: "10",
										step: "0.1",
										value: hyperparams.reg_lambda,
										onChange: (e) => setHyperparams((prev) => ({
											...prev,
											reg_lambda: parseFloat(e.target.value)
										})),
										className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
									})] }),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
										className: "text-sm font-medium block mb-2",
										children: "Reg Alpha"
									}), /* @__PURE__ */ jsx("input", {
										type: "number",
										min: "0",
										max: "10",
										step: "0.1",
										value: hyperparams.reg_alpha,
										onChange: (e) => setHyperparams((prev) => ({
											...prev,
											reg_alpha: parseFloat(e.target.value)
										})),
										className: "w-full px-3 py-2 border border-input rounded-lg text-sm bg-background"
									})] })
								] })
							] })
						}),
						/* @__PURE__ */ jsx(Button, {
							variant: "outline",
							size: "sm",
							className: "mt-4",
							onClick: () => {
								setConfig((prev) => ({
									...prev,
									manual_params: hyperparams
								}));
							},
							children: "Apply Manual Parameters"
						})
					]
				}),
				/* @__PURE__ */ jsx(Accordion, {
					type: "single",
					collapsible: true,
					className: "rounded-xl border border-border bg-card shadow-elegant",
					children: /* @__PURE__ */ jsxs(AccordionItem, {
						value: "current-params",
						children: [/* @__PURE__ */ jsx(AccordionTrigger, {
							className: "px-6 py-4",
							children: "Current Parameters Summary"
						}), /* @__PURE__ */ jsx(AccordionContent, {
							className: "px-6 pt-0 pb-6",
							children: /* @__PURE__ */ jsxs("div", {
								className: "grid grid-cols-1 gap-3 md:grid-cols-2 text-sm",
								children: [
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Model:" }),
										" ",
										selectedModel.name
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Random Seed:" }),
										" ",
										usedTrainingConfig.random_seed
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Train / Val / Test:" }),
										" ",
										((1 - usedTrainingConfig.test_size - usedTrainingConfig.val_size) * 100).toFixed(0),
										"% / ",
										(usedTrainingConfig.val_size * 100).toFixed(0),
										"% / ",
										(usedTrainingConfig.test_size * 100).toFixed(0),
										"%"
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "CV:" }),
										" ",
										usedTrainingConfig.use_cv ? `Yes (${usedTrainingConfig.cv_folds} folds)` : "No"
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Hyperopt:" }),
										" ",
										usedTrainingConfig.use_hyperopt ? "Yes" : "No"
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Feature engineering:" }),
										" ",
										usedTrainingConfig.use_feature_engineering ? "Enabled" : "Disabled"
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Class Weight:" }),
										" ",
										usedTrainingConfig.use_class_weight || selectedModel.name === "XGBoost" && usedTrainingConfig.scale_pos_weight !== 1 ? `Yes${selectedModel.name === "XGBoost" ? ` (scale: ${usedTrainingConfig.scale_pos_weight.toFixed(1)})` : ""}` : "No"
									] }),
									Object.keys(usedTrainingConfig.manual_params || {}).length > 0 && /* @__PURE__ */ jsxs("div", {
										className: "md:col-span-2",
										children: [
											/* @__PURE__ */ jsx("strong", { children: "Manual Params:" }),
											" ",
											/* @__PURE__ */ jsx("code", {
												className: "rounded bg-background px-2 py-1 text-xs",
												children: JSON.stringify(usedTrainingConfig.manual_params)
											})
										]
									})
								]
							})
						})]
					})
				}),
				recommendations && recommendations.length > 1 && /* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-2 mb-4",
							children: [/* @__PURE__ */ jsx(BarChart3, { className: "h-5 w-5 text-primary" }), /* @__PURE__ */ jsx("h2", {
								className: "text-base font-semibold",
								children: "Model Comparison"
							})]
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-sm text-muted-foreground mb-4",
							children: "Select additional models to train and compare against the champion."
						}),
						/* @__PURE__ */ jsx("div", {
							className: "grid grid-cols-2 gap-3 md:grid-cols-4",
							children: recommendations.map((rec) => /* @__PURE__ */ jsxs("label", {
								className: `p-3 border rounded-lg cursor-pointer transition ${modelsToCompare.includes(rec.name) ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}`,
								children: [
									/* @__PURE__ */ jsx("input", {
										type: "checkbox",
										checked: modelsToCompare.includes(rec.name),
										onChange: (e) => {
											if (e.target.checked) setModelsToCompare((prev) => [...prev, rec.name]);
											else setModelsToCompare((prev) => prev.filter((m) => m !== rec.name));
										},
										className: "w-4 h-4"
									}),
									/* @__PURE__ */ jsx("div", {
										className: "text-sm font-medium mt-2",
										children: rec.name
									}),
									/* @__PURE__ */ jsx("div", {
										className: "text-xs text-muted-foreground",
										children: rec.name === selectedModel.name ? "(Champion)" : ""
									})
								]
							}, rec.name))
						})
					]
				}),
				trainingInfo && /* @__PURE__ */ jsxs(Fragment, { children: [
					evaluationMetrics && /* @__PURE__ */ jsx("section", {
						className: "rounded-xl border border-warning/40 bg-warning/10 p-6 shadow-elegant",
						children: /* @__PURE__ */ jsxs("div", {
							className: "flex items-start gap-3",
							children: [/* @__PURE__ */ jsx(AlertCircle, { className: "h-5 w-5 text-warning-foreground flex-shrink-0 mt-0.5" }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
								className: "font-semibold text-warning-foreground",
								children: "Regulatory risk warning"
							}), /* @__PURE__ */ jsxs("p", {
								className: "text-sm text-warning-foreground",
								children: [
									evaluationMetrics.roc_auc !== void 0 && evaluationMetrics.roc_auc < .7 && /* @__PURE__ */ jsx(Fragment, { children: "ROC-AUC is below 0.70, which may signal weak discrimination for credit risk. " }),
									evaluationMetrics.recall !== void 0 && evaluationMetrics.recall < .6 && /* @__PURE__ */ jsx(Fragment, { children: "Recall is below 0.60, which may indicate an elevated missed-default risk. " }),
									"Review model performance before promotion to production."
								]
							})] })]
						})
					}),
					/* @__PURE__ */ jsxs("section", {
						className: "grid grid-cols-1 gap-6 lg:grid-cols-3",
						children: [/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsx("h2", {
								className: "text-base font-semibold",
								children: "Hyperparameters"
							}), /* @__PURE__ */ jsxs("dl", {
								className: "mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm",
								children: [Object.entries(trainingInfo.best_params || {}).map(([k, v]) => /* @__PURE__ */ jsxs("div", {
									className: "contents",
									children: [/* @__PURE__ */ jsx("dt", {
										className: "text-muted-foreground",
										children: k
									}), /* @__PURE__ */ jsx("dd", {
										className: "text-right font-mono text-xs",
										children: String(v)
									})]
								}, k)), trainingInfo.training_time_s && /* @__PURE__ */ jsxs(Fragment, { children: [/* @__PURE__ */ jsx("dt", {
									className: "text-muted-foreground",
									children: "training_time_s"
								}), /* @__PURE__ */ jsx("dd", {
									className: "text-right font-mono text-xs",
									children: trainingInfo.training_time_s.toFixed(2)
								})] })]
							})]
						}), /* @__PURE__ */ jsxs("div", {
							className: "lg:col-span-2 rounded-xl border border-border bg-sidebar p-6 font-mono text-xs text-sidebar-foreground shadow-elegant",
							children: [/* @__PURE__ */ jsx("div", {
								className: "mb-3 flex items-center justify-between",
								children: /* @__PURE__ */ jsx("span", {
									className: "font-sans text-sm font-semibold text-sidebar-foreground",
									children: "Model Summary"
								})
							}), /* @__PURE__ */ jsxs("div", {
								className: "space-y-1.5",
								children: [
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Model:" }),
										" ",
										trainingModelName ?? selectedModel.name
									] }),
									/* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "Training Time:" }),
										" ",
										trainingInfo.training_time_s?.toFixed(2),
										"s"
									] }),
									trainingInfo.cv_mean && /* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "CV Mean Score:" }),
										" ",
										trainingInfo.cv_mean.toFixed(4)
									] }),
									trainingInfo.cv_std && /* @__PURE__ */ jsxs("div", { children: [
										/* @__PURE__ */ jsx("strong", { children: "CV Std Dev:" }),
										" ",
										trainingInfo.cv_std.toFixed(4)
									] })
								]
							})]
						})]
					}),
					splitStats && /* @__PURE__ */ jsxs("section", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Data Split Statistics"
						}), /* @__PURE__ */ jsxs("div", {
							className: "mt-4 grid grid-cols-2 gap-4 text-sm",
							children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
								className: "text-[11px] uppercase tracking-wider text-muted-foreground",
								children: "Total Samples"
							}), /* @__PURE__ */ jsx("dd", {
								className: "mt-1 text-lg font-semibold",
								children: splitStats.total?.toLocaleString()
							})] }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
								className: "text-[11px] uppercase tracking-wider text-muted-foreground",
								children: "Train / Val / Test"
							}), /* @__PURE__ */ jsxs("dd", {
								className: "mt-1 text-sm",
								children: [
									splitStats.train_n,
									" / ",
									splitStats.val_n,
									" / ",
									splitStats.test_n
								]
							})] })]
						})]
					}),
					evaluationMetrics && /* @__PURE__ */ jsxs("section", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Evaluation Metrics"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-4 grid grid-cols-2 gap-4 text-sm md:grid-cols-4",
							children: [
								["ROC-AUC", evaluationMetrics.roc_auc],
								["Recall", evaluationMetrics.recall],
								["Precision", evaluationMetrics.precision],
								["F1", evaluationMetrics.f1],
								["PR-AUC", evaluationMetrics.pr_auc],
								["Accuracy", evaluationMetrics.accuracy]
							].map(([label, value]) => value !== void 0 && /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border p-4",
								children: [/* @__PURE__ */ jsx("div", {
									className: "text-xs uppercase tracking-wider text-muted-foreground",
									children: label
								}), /* @__PURE__ */ jsx("div", {
									className: "mt-2 text-2xl font-semibold",
									children: typeof value === "number" ? value.toFixed(3) : String(value)
								})]
							}, label))
						})]
					}),
					comparisonResults && comparisonResults.length > 0 && /* @__PURE__ */ jsxs("section", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between",
							children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
								className: "text-base font-semibold",
								children: "Comparison Table"
							}), /* @__PURE__ */ jsx("p", {
								className: "text-sm text-muted-foreground",
								children: "Review model-level metrics for selected candidates and choose a final champion."
							})] })
						}), /* @__PURE__ */ jsx("div", {
							className: "overflow-x-auto",
							children: /* @__PURE__ */ jsxs("table", {
								className: "min-w-full divide-y divide-border text-sm",
								children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", {
									className: "text-left text-xs uppercase tracking-wider text-muted-foreground",
									children: [
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "Model"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "ROC-AUC"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "Recall"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "Precision"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "F1"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "PR-AUC"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "Accuracy"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "Train Time"
										}),
										/* @__PURE__ */ jsx("th", {
											className: "px-3 py-2",
											children: "Final"
										})
									]
								}) }), /* @__PURE__ */ jsx("tbody", {
									className: "divide-y divide-border",
									children: comparisonResults.map((row) => /* @__PURE__ */ jsxs("tr", {
										className: row.model_name === selectedComparisonModel ? "bg-primary/5" : void 0,
										children: [
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3 font-medium",
												children: row.model_name
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.roc_auc?.toFixed(3) ?? "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.recall?.toFixed(3) ?? "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.precision?.toFixed(3) ?? "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.f1?.toFixed(3) ?? "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.pr_auc?.toFixed(3) ?? "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.accuracy?.toFixed(3) ?? "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: row.training_time_s ? `${row.training_time_s.toFixed(2)}s` : "—"
											}),
											/* @__PURE__ */ jsx("td", {
												className: "px-3 py-3",
												children: /* @__PURE__ */ jsx(Button, {
													variant: row.model_name === selectedComparisonModel ? "secondary" : "outline",
													size: "sm",
													onClick: () => {
														setSelectedComparisonModel(row.model_name);
														const chosen = recommendations?.find((rec) => rec.name === row.model_name);
														if (chosen) setSelectedModel(chosen);
													},
													children: row.model_name === selectedComparisonModel ? "Selected" : "Select"
												})
											})
										]
									}, row.model_name))
								})]
							})
						})]
					})
				] })
			] }),
			/* @__PURE__ */ jsxs("div", {
				className: "flex gap-3 pt-4",
				children: [
					/* @__PURE__ */ jsxs(Button, {
						variant: "outline",
						onClick: () => navigate({ to: "/features" }),
						className: "gap-2",
						children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Feature Engineering"]
					}),
					/* @__PURE__ */ jsxs(Button, {
						onClick: handleTrain,
						disabled: loading || !selectedModel,
						className: "gap-2",
						children: [loading && /* @__PURE__ */ jsx(Loader2, { className: "h-4 w-4 animate-spin" }), loading ? "Training..." : "Train Model Now"]
					}),
					selectedModel && modelsToCompare.length > 0 && /* @__PURE__ */ jsxs(Button, {
						onClick: handleQuickComparison,
						disabled: loading,
						variant: "outline",
						className: "gap-2",
						children: [/* @__PURE__ */ jsx(Zap, { className: "h-4 w-4" }), "Run Quick Comparison"]
					}),
					/* @__PURE__ */ jsxs(Button, {
						onClick: () => navigate({ to: "/evaluation" }),
						disabled: loading || !trainingInfo,
						className: "gap-2 ml-auto",
						children: ["Proceed to Evaluation", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
					})
				]
			})
		]
	});
}
//#endregion
export { Training as component };
