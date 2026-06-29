import { n as PageHeader, r as cn } from "./app-shell-DXEPQAWO.js";
import { n as useDataset } from "./app-context-DEU1RUW-.js";
import { n as formUpload } from "./api-EJXRGsO6.js";
import { t as Button } from "./button-D06NJiFe.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { ArrowLeft, ArrowRight, BarChart3, CheckCircle2, Shield, Sparkles } from "lucide-react";
//#region src/routes/models.tsx?tsr-split=component
function ModelSelection() {
	const { profile, file, recommendations, setRecommendations, setSelectedModel, selectedModel } = useDataset();
	const navigate = useNavigate();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [modelsToCompare, setModelsToCompare] = useState([]);
	const fetchRef = useRef(false);
	const datasetSummary = useMemo(() => {
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
	}, [profile]);
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
					if (!selectedModel && transformed.length > 0) setSelectedModel(transformed[0]);
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
		setRecommendations,
		setSelectedModel
	]);
	const handleSelectModel = useCallback((model) => {
		setSelectedModel(model);
	}, [setSelectedModel]);
	const toggleModelToCompare = useCallback((modelName) => {
		setModelsToCompare((prev) => {
			if (prev.includes(modelName)) return prev.filter((m) => m !== modelName);
			else return [...prev, modelName];
		});
	}, []);
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
				description: "Recommendation cards ranked by score, with regulator-friendly trade-offs."
			}),
			datasetSummary && /* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-4 md:grid-cols-3",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Sample count"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: datasetSummary.sampleCount.toLocaleString()
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Feature count"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: datasetSummary.featureCount
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Class imbalance"
						}), /* @__PURE__ */ jsxs("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: [datasetSummary.imbalanceRatio.toFixed(2), "x"]
						})]
					})
				]
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
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-3 mb-4",
							children: [/* @__PURE__ */ jsx(BarChart3, { className: "h-5 w-5 text-primary" }), /* @__PURE__ */ jsx("h2", {
								className: "text-base font-semibold",
								children: "Models to Compare"
							})]
						}),
						/* @__PURE__ */ jsx("p", {
							className: "text-sm text-muted-foreground mb-4",
							children: "Select additional models to include in comparative evaluation. The champion (selected above) is always included."
						}),
						/* @__PURE__ */ jsx("div", {
							className: "grid grid-cols-2 gap-3 md:grid-cols-4",
							children: transformedModels.map((model) => /* @__PURE__ */ jsxs("label", {
								className: "flex items-center gap-2 rounded-lg border border-border bg-background p-3 cursor-pointer hover:border-primary/40 transition-colors",
								children: [/* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: modelsToCompare.includes(model.name),
									onChange: () => toggleModelToCompare(model.name),
									className: "rounded border-border"
								}), /* @__PURE__ */ jsx("span", {
									className: "text-sm font-medium",
									children: model.name
								})]
							}, model.name))
						})
					]
				}),
				/* @__PURE__ */ jsxs("section", { children: [/* @__PURE__ */ jsx("h2", {
					className: "text-base font-semibold mb-4",
					children: "Recommended Models"
				}), /* @__PURE__ */ jsx("div", {
					className: "grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3",
					children: transformedModels.map((m) => /* @__PURE__ */ jsxs("div", {
						className: cn("relative rounded-2xl border bg-card p-6 shadow-elegant transition-all hover:-translate-y-1 cursor-pointer", m.selected ? "border-primary/60 ring-2 ring-primary/20" : "border-border hover:border-primary/40"),
						onClick: () => handleSelectModel(m),
						children: [
							m.selected && /* @__PURE__ */ jsxs("span", {
								className: "absolute -top-2.5 right-4 inline-flex items-center gap-1 rounded-full gradient-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground shadow-elegant",
								children: [/* @__PURE__ */ jsx(Sparkles, { className: "h-3 w-3" }), " Selected"]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "flex items-baseline justify-between gap-4",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
									className: "text-base font-semibold",
									children: m.name
								}), m.icon && /* @__PURE__ */ jsx("div", {
									className: "text-sm text-muted-foreground",
									children: m.icon
								})] }), /* @__PURE__ */ jsx("span", {
									className: "text-2xl font-semibold tabular-nums",
									children: m.score.toFixed(1)
								})]
							}),
							/* @__PURE__ */ jsx("div", {
								className: "text-[11px] uppercase tracking-wider text-muted-foreground",
								children: "Recommendation score"
							}),
							/* @__PURE__ */ jsxs("dl", {
								className: "mt-4 space-y-2.5 text-sm",
								children: [
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
										className: "text-[11px] uppercase tracking-wider text-muted-foreground",
										children: "Best for"
									}), /* @__PURE__ */ jsx("dd", {
										className: "mt-0.5 text-foreground/90",
										children: m.best_for?.length ? m.best_for.join(", ") : m.description
									})] }),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
										className: "text-[11px] uppercase tracking-wider text-muted-foreground",
										children: "Why recommended"
									}), /* @__PURE__ */ jsx("dd", {
										className: "mt-0.5 text-foreground/90 text-xs",
										children: m.why
									})] }),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", {
										className: "text-[11px] uppercase tracking-wider text-muted-foreground",
										children: "Recommendation"
									}), /* @__PURE__ */ jsxs("dd", {
										className: "mt-0.5 flex items-center gap-1.5 text-foreground/90",
										children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-3.5 w-3.5 text-primary" }), m.selected ? "Champion (selected)" : "Challenger"]
									})] })
								]
							}),
							/* @__PURE__ */ jsx("button", {
								onClick: (e) => {
									e.stopPropagation();
									handleSelectModel(m);
								},
								className: cn("mt-5 w-full rounded-lg border px-3 py-2 text-sm font-medium transition-colors", m.selected ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:border-primary/40 hover:bg-primary-soft"),
								children: m.selected ? "Selected" : "Select model"
							})
						]
					}, m.name))
				})] }),
				/* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-3 mb-4",
						children: [/* @__PURE__ */ jsx(Shield, { className: "h-5 w-5 text-primary" }), /* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Credit Risk Evaluation Strategy"
						})]
					}), /* @__PURE__ */ jsxs("div", {
						className: "space-y-4",
						children: [
							/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold mb-2",
								children: "Champion Model"
							}), /* @__PURE__ */ jsx("p", {
								className: "text-sm text-muted-foreground",
								children: selectedModel ? /* @__PURE__ */ jsxs(Fragment, { children: [/* @__PURE__ */ jsx("strong", { children: selectedModel.name }), " has been selected as the primary model for risk assessment. This model will be trained on your dataset and used for generating predictions and risk scores."] }) : "Select a champion model above to proceed with training and evaluation."
							})] }),
							/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold mb-2",
								children: "Comparative Evaluation"
							}), /* @__PURE__ */ jsx("p", {
								className: "text-sm text-muted-foreground",
								children: modelsToCompare.length > 0 ? /* @__PURE__ */ jsxs(Fragment, { children: [
									"You have selected ",
									/* @__PURE__ */ jsxs("strong", { children: [modelsToCompare.length, " challenger model(s)"] }),
									" for comparison: ",
									modelsToCompare.join(", "),
									". These will be evaluated alongside the champion model to validate robustness."
								] }) : "Optionally select challenger models above for comparative evaluation against the champion."
							})] }),
							/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold mb-2",
								children: "Next Steps"
							}), /* @__PURE__ */ jsxs("p", {
								className: "text-sm text-muted-foreground",
								children: [
									"Proceed to training to fit the champion model on your ",
									datasetSummary?.sampleCount.toLocaleString(),
									" samples. Model evaluation will follow, including performance metrics, feature importance, and SHAP-based explainability."
								]
							})] })
						]
					})]
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
