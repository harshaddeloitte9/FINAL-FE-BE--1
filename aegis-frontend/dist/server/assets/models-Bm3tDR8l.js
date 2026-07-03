import { n as PageHeader } from "./app-shell-fDQz9JMF.js";
import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-CPpoZWeE.js";
import { t as Button } from "./button-MHHI04mG.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { ArrowLeft, ArrowRight } from "lucide-react";
//#region src/routes/models.tsx?tsr-split=component
function ModelSelection() {
	const { profile, file, recommendations, setRecommendations, setSelectedModel, selectedModel, compareModels, setCompareModels } = useDataset();
	const [trainingStats, setTrainingStats] = useState(null);
	const [recommendationTaskType, setRecommendationTaskType] = useState(null);
	const navigate = useNavigate();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
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
			setLoading(true);
			setError(null);
			try {
				const form = new FormData();
				form.append("file", file);
				form.append("target_col", profile.target_col || "loan_status");
				console.log("Models: POST /models/recommend", { target_col: profile.target_col });
				const response = await formUpload("/models/recommend", form);
				console.log("Models: response", response);
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
				} else setError("No recommendations returned by backend.");
			} catch (err) {
				console.error("Models: failed to load recommendations", err);
				if (!isMounted) return;
				setError(err?.body?.detail ?? err?.message ?? "Failed to load model recommendations.");
			} finally {
				if (isMounted) setLoading(false);
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
	useCallback((model) => {
		setSelectedModel(model);
	}, [setSelectedModel]);
	const toggleModelToCompare = useCallback((modelName) => {
		const current = compareModels ?? [];
		setCompareModels(current.includes(modelName) ? current.filter((m) => m !== modelName) : [...current, modelName]);
	}, [compareModels, setCompareModels]);
	if (!profile) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Model Selection",
			description: "Recommendation cards ranked by score, with regulator-friendly trade-offs."
		}), /* @__PURE__ */ jsxs("div", {
			className: "rounded-xl border border-border bg-card p-6 text-center",
			children: [/* @__PURE__ */ jsx("h3", {
				className: "text-lg font-semibold",
				children: "No dataset available"
			}), /* @__PURE__ */ jsx("p", {
				className: "mt-2 text-sm text-muted-foreground",
				children: "Upload and preprocess a dataset before model selection."
			})]
		})]
	});
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Model Selection",
				description: "Models ranked by suitability for your dataset — with explanations."
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
			loading && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "Loading model recommendations..."
			}),
			error && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-destructive",
				children: error
			}),
			transformedModels.length === 0 && !loading && !error && /* @__PURE__ */ jsx("div", {
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
							return /* @__PURE__ */ jsxs("div", {
								className: "relative flex flex-col rounded-2xl border border-border bg-card p-6 shadow-elegant",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-start justify-between gap-3",
										children: [/* @__PURE__ */ jsx("div", {
											className: "space-y-2",
											children: /* @__PURE__ */ jsxs("div", {
												className: "flex items-center gap-2",
												children: [/* @__PURE__ */ jsx("span", {
													className: "text-sm uppercase tracking-wider text-muted-foreground",
													children: `Rank ${index + 1}`
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
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "mb-4 text-base font-semibold",
							children: "Models to compare after training split"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "mb-4 text-sm text-muted-foreground",
							children: "These models will be trained with lightweight defaults on the same split for comparison."
						}),
						/* @__PURE__ */ jsx("div", {
							className: "space-y-3",
							children: transformedModels.map((model) => /* @__PURE__ */ jsxs("label", {
								className: "flex items-center gap-3 rounded-xl border border-border bg-background px-4 py-3",
								children: [/* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: (compareModels ?? []).includes(model.name),
									onChange: () => toggleModelToCompare(model.name),
									className: "h-4 w-4 rounded border-border accent-primary"
								}), /* @__PURE__ */ jsx("span", {
									className: "text-sm",
									children: model.name
								})]
							}, model.name))
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
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "flex gap-3 pt-4",
					children: [/* @__PURE__ */ jsxs(Button, {
						variant: "outline",
						onClick: () => navigate({ to: "/preprocessing" }),
						className: "gap-2",
						children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Preprocessing"]
					}), /* @__PURE__ */ jsxs(Button, {
						onClick: () => navigate({ to: "/training" }),
						className: "gap-2 ml-auto",
						disabled: !selectedModel,
						children: ["Proceed to Training", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
					})]
				})
			] })
		]
	});
}
//#endregion
export { ModelSelection as component };
