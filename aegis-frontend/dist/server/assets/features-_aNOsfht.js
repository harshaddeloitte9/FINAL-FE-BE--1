import { n as PageHeader } from "./app-shell-DVyXktRn.js";
import { n as useDataset } from "./app-context-DEU1RUW-.js";
import { n as formUpload } from "./api-EJXRGsO6.js";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { AlertCircle, ArrowLeft, ArrowRight, Loader } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/features.tsx?tsr-split=component
function Features() {
	const navigate = useNavigate();
	const { file, profile } = useDataset();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [engineeringResult, setEngineeringResult] = useState(null);
	const [vifSortKey, setVifSortKey] = useState("value");
	const [vifSortAsc, setVifSortAsc] = useState(false);
	const [eadMode, setEadMode] = useState("outstanding_balance");
	const [eadCol, setEadCol] = useState("");
	const [loanCol, setLoanCol] = useState("");
	const [interestCol, setInterestCol] = useState("");
	const [yearsCol, setYearsCol] = useState("");
	const [termCol, setTermCol] = useState("");
	const [yearsMonths, setYearsMonths] = useState(false);
	const [termMonths, setTermMonths] = useState(false);
	useEffect(() => {
		if (!file || !profile) {
			setError("No dataset uploaded. Please upload a dataset first.");
			return;
		}
		const runFeatureEngineering = async () => {
			try {
				setLoading(true);
				setError(null);
				let target_col = "";
				if (profile.columns && Array.isArray(profile.columns) && profile.columns.includes("loan_status")) target_col = "loan_status";
				else if (profile.target_candidates && Array.isArray(profile.target_candidates) && profile.target_candidates.length > 0) target_col = profile.target_candidates[0];
				if (!target_col || target_col === "string") throw new Error("Could not determine target column. Please check the uploaded dataset.");
				const form = new FormData();
				form.append("file", file);
				form.append("target_col", target_col);
				form.append("ead_mode", eadMode);
				form.append("ead_col", eadCol || "");
				form.append("ead_loan_col", loanCol || "");
				form.append("ead_interest_col", interestCol || "");
				form.append("ead_years_col", yearsCol || "");
				form.append("ead_term_col", termCol || "");
				form.append("ead_years_months", yearsMonths ? "true" : "false");
				form.append("ead_term_months", termMonths ? "true" : "false");
				setEngineeringResult(await formUpload("/data/feature-engineering", form));
			} catch (err) {
				setError(err instanceof Error ? err.message : "Failed to run feature engineering");
			} finally {
				setLoading(false);
			}
		};
		runFeatureEngineering();
	}, [
		file,
		profile,
		eadMode,
		eadCol,
		loanCol,
		interestCol,
		yearsCol,
		termCol,
		yearsMonths,
		termMonths
	]);
	const plan = engineeringResult?.feature_engineering_plan ?? {};
	const summary = engineeringResult?.feature_engineering_summary ?? {};
	const addedFeatures = Array.isArray(summary.added) ? summary.added : [];
	const removedFeatures = Array.isArray(summary.removed) ? summary.removed : [];
	const transformedSteps = Array.isArray(summary.transformed) ? summary.transformed : [];
	const appliedSteps = Array.isArray(plan.applied_steps) ? plan.applied_steps : [];
	const miScores = plan.mi_scores && typeof plan.mi_scores === "object" ? plan.mi_scores : {};
	const ivScores = plan.iv_scores && typeof plan.iv_scores === "object" ? plan.iv_scores : {};
	const woeCols = Array.isArray(plan.woe_cols) ? plan.woe_cols : [];
	const woeMaps = plan.woe_maps && typeof plan.woe_maps === "object" ? plan.woe_maps : {};
	const highCorrPairs = Array.isArray(plan.multicollinearity?.high_corr_pairs) ? plan.multicollinearity.high_corr_pairs : [];
	const vifMap = plan.multicollinearity?.vif && typeof plan.multicollinearity.vif === "object" ? plan.multicollinearity.vif : {};
	const regulatoryAlerts = Array.isArray(summary.regulatory_alerts) ? summary.regulatory_alerts : Array.isArray(plan.regulatory_alerts) ? plan.regulatory_alerts : [];
	const [decisionLogCsvUrl, setDecisionLogCsvUrl] = useState(null);
	const vifRows = useMemo(() => {
		return Object.entries(vifMap).map(([feature, value]) => ({
			feature,
			value: Number(value)
		}));
	}, [vifMap]);
	const sortedVifRows = useMemo(() => {
		return [...vifRows].sort((a, b) => {
			if (vifSortKey === "feature") return vifSortAsc ? a.feature.localeCompare(b.feature) : b.feature.localeCompare(a.feature);
			return vifSortAsc ? a.value - b.value : b.value - a.value;
		});
	}, [
		vifRows,
		vifSortKey,
		vifSortAsc
	]);
	const miData = useMemo(() => {
		return Object.entries(miScores).map(([feature, score]) => ({
			feature,
			score: Number(score)
		})).sort((a, b) => b.score - a.score);
	}, [miScores]);
	const ivData = useMemo(() => {
		return Object.entries(ivScores).map(([feature, iv]) => ({
			feature,
			iv: Number(iv)
		})).sort((a, b) => b.iv - a.iv);
	}, [ivScores]);
	const woeInfo = useMemo(() => {
		return woeCols.map((col) => ({
			feature: col,
			buckets: woeMaps[col] ? Object.keys(woeMaps[col]).length : 0
		}));
	}, [woeCols, woeMaps]);
	const numericColumns = useMemo(() => engineeringResult?.available_numeric_columns ?? [], [engineeringResult]);
	const giniRows = useMemo(() => Object.entries(engineeringResult?.gini_scores ?? {}).map(([feature, score]) => ({
		feature,
		score: Number(score)
	})), [engineeringResult]);
	useEffect(() => {
		const selected = engineeringResult?.ead_configuration?.selected;
		if (!selected) return;
		if (selected.outstanding_balance_col) setEadCol(selected.outstanding_balance_col);
		if (selected.loan_amount) setLoanCol(selected.loan_amount);
		if (selected.interest_rate) setInterestCol(selected.interest_rate);
		if (selected.years_elapsed) setYearsCol(selected.years_elapsed);
		if (selected.term) setTermCol(selected.term);
		if (typeof selected.years_elapsed_is_months === "boolean") setYearsMonths(selected.years_elapsed_is_months);
		if (typeof selected.term_is_months === "boolean") setTermMonths(selected.term_is_months);
		if (selected.outstanding_balance_col) setEadMode("outstanding_balance");
		else if (selected.loan_amount || selected.interest_rate || selected.years_elapsed || selected.term) setEadMode("estimate");
	}, [engineeringResult]);
	const canProceed = !!engineeringResult && !loading && !error;
	if (!file || !profile) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Feature Engineering",
			description: "Engineered features, multicollinearity diagnostics, and importance preview."
		}), /* @__PURE__ */ jsx("div", {
			className: "rounded-xl border border-amber-200 bg-amber-50 p-6",
			children: /* @__PURE__ */ jsxs("div", {
				className: "flex items-center gap-3",
				children: [/* @__PURE__ */ jsx(AlertCircle, { className: "h-5 w-5 text-amber-600" }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
					className: "font-semibold text-amber-900",
					children: "No Dataset"
				}), /* @__PURE__ */ jsx("div", {
					className: "text-sm text-amber-800",
					children: "Upload a dataset on the Data Upload page to see feature engineering results."
				})] })]
			})
		})]
	});
	if (error) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Feature Engineering",
			description: "Engineered features, multicollinearity diagnostics, and importance preview."
		}), /* @__PURE__ */ jsxs("div", {
			className: "rounded-xl border border-red-200 bg-red-50 p-6",
			children: [/* @__PURE__ */ jsxs("div", {
				className: "flex items-center gap-3",
				children: [/* @__PURE__ */ jsx(AlertCircle, { className: "h-5 w-5 text-red-600" }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
					className: "font-semibold text-red-900",
					children: "Error"
				}), /* @__PURE__ */ jsx("div", {
					className: "text-sm text-red-800",
					children: error
				})] })]
			}), /* @__PURE__ */ jsx("div", {
				className: "mt-4 flex flex-wrap gap-2",
				children: /* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:border-primary hover:bg-primary-soft",
					onClick: () => navigate("/preprocessing"),
					children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Preprocessing"]
				})
			})]
		})]
	});
	if (loading) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Feature Engineering",
			description: "Engineered features, multicollinearity diagnostics, and importance preview."
		}), /* @__PURE__ */ jsxs("div", {
			className: "flex flex-col items-center justify-center gap-4 py-12",
			children: [/* @__PURE__ */ jsx(Loader, { className: "h-8 w-8 animate-spin text-primary" }), /* @__PURE__ */ jsx("div", {
				className: "text-sm text-muted-foreground",
				children: "Running feature engineering..."
			})]
		})]
	});
	if (!engineeringResult) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Feature Engineering",
			description: "Engineered features, multicollinearity diagnostics, and importance preview."
		}), /* @__PURE__ */ jsx("div", {
			className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
			children: /* @__PURE__ */ jsx("div", {
				className: "text-center text-sm text-muted-foreground",
				children: "Feature engineering did not return a result."
			})
		})]
	});
	const originalFeatures = Array.isArray(summary.original_shape) ? summary.original_shape[1] ?? null : null;
	const finalFeatures = Array.isArray(summary.final_shape) ? summary.final_shape[1] ?? null : null;
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Feature Engineering",
				description: "Engineered features, multicollinearity diagnostics, and importance preview."
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-4 md:grid-cols-4",
				children: [
					originalFeatures !== null && /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Original features"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: originalFeatures
						})]
					}),
					finalFeatures !== null && /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Final features"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: finalFeatures
						})]
					}),
					addedFeatures.length > 0 && /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Features added"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: addedFeatures.length
						})]
					}),
					removedFeatures.length > 0 && /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-xs uppercase tracking-wider text-muted-foreground",
							children: "Features removed"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-2 text-2xl font-semibold tabular-nums",
							children: removedFeatures.length
						})]
					})
				]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "flex items-center justify-between gap-4",
					children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Feature Engineering Plan"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "The same transformations learned on the training split and applied to validation/test."
					})] })
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 space-y-3 text-sm",
					children: appliedSteps.length > 0 ? appliedSteps.map((step, idx) => /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-background p-3",
						children: [
							/* @__PURE__ */ jsx("div", {
								className: "font-medium text-xs text-foreground",
								children: step.step || `Step ${idx + 1}`
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-1 text-[11px] text-muted-foreground",
								children: step.reason || ""
							}),
							Array.isArray(step.columns) && step.columns.length > 0 && /* @__PURE__ */ jsx("div", {
								className: "mt-2 flex flex-wrap gap-1",
								children: step.columns.map((col, cidx) => /* @__PURE__ */ jsx("span", {
									className: "inline-block rounded border border-border bg-primary/10 px-2 py-0.5 font-mono text-[10px]",
									children: col
								}, cidx))
							})
						]
					}, idx)) : /* @__PURE__ */ jsx("div", {
						className: "rounded-xl border border-border bg-background p-3 text-muted-foreground",
						children: "No significant feature engineering opportunities were detected for this dataset."
					})
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "flex items-center justify-between gap-4",
					children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Exposure at Default (EAD) source for ECL"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "This mirrors the original Streamlit step and is used for downstream ECL calculations."
					})] })
				}), /* @__PURE__ */ jsxs("div", {
					className: "mt-4 space-y-4 text-sm",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-background p-3",
							children: [/* @__PURE__ */ jsx("label", {
								className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
								children: "Does your dataset contain an outstanding balance column?"
							}), /* @__PURE__ */ jsxs("div", {
								className: "mt-2 space-y-2",
								children: [/* @__PURE__ */ jsxs("label", {
									className: "flex items-center gap-2 rounded border border-border px-3 py-2",
									children: [/* @__PURE__ */ jsx("input", {
										type: "radio",
										checked: eadMode === "outstanding_balance",
										onChange: () => setEadMode("outstanding_balance")
									}), /* @__PURE__ */ jsx("span", { children: "Yes — select it" })]
								}), /* @__PURE__ */ jsxs("label", {
									className: "flex items-center gap-2 rounded border border-border px-3 py-2",
									children: [/* @__PURE__ */ jsx("input", {
										type: "radio",
										checked: eadMode === "estimate",
										onChange: () => setEadMode("estimate")
									}), /* @__PURE__ */ jsx("span", { children: "No — estimate it from loan amount, interest, elapsed time, term" })]
								})]
							})]
						}),
						eadMode === "outstanding_balance" ? /* @__PURE__ */ jsx("div", {
							className: "grid gap-3 md:grid-cols-1",
							children: /* @__PURE__ */ jsxs("label", {
								className: "space-y-2 text-sm",
								children: [/* @__PURE__ */ jsx("span", {
									className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
									children: "Outstanding balance column"
								}), /* @__PURE__ */ jsxs("select", {
									className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
									value: eadCol,
									onChange: (event) => setEadCol(event.target.value),
									children: [/* @__PURE__ */ jsx("option", {
										value: "",
										children: "Select a numeric column"
									}), numericColumns.map((col) => /* @__PURE__ */ jsx("option", {
										value: col,
										children: col
									}, col))]
								})]
							})
						}) : /* @__PURE__ */ jsxs("div", {
							className: "grid gap-3 md:grid-cols-2",
							children: [
								/* @__PURE__ */ jsxs("label", {
									className: "space-y-2 text-sm",
									children: [/* @__PURE__ */ jsx("span", {
										className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
										children: "Loan amount"
									}), /* @__PURE__ */ jsxs("select", {
										className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
										value: loanCol,
										onChange: (event) => setLoanCol(event.target.value),
										children: [/* @__PURE__ */ jsx("option", {
											value: "",
											children: "Select a column"
										}), numericColumns.map((col) => /* @__PURE__ */ jsx("option", {
											value: col,
											children: col
										}, col))]
									})]
								}),
								/* @__PURE__ */ jsxs("label", {
									className: "space-y-2 text-sm",
									children: [/* @__PURE__ */ jsx("span", {
										className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
										children: "Interest rate"
									}), /* @__PURE__ */ jsxs("select", {
										className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
										value: interestCol,
										onChange: (event) => setInterestCol(event.target.value),
										children: [/* @__PURE__ */ jsx("option", {
											value: "",
											children: "Select a column"
										}), numericColumns.map((col) => /* @__PURE__ */ jsx("option", {
											value: col,
											children: col
										}, col))]
									})]
								}),
								/* @__PURE__ */ jsxs("label", {
									className: "space-y-2 text-sm",
									children: [/* @__PURE__ */ jsx("span", {
										className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
										children: "Elapsed time"
									}), /* @__PURE__ */ jsxs("select", {
										className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
										value: yearsCol,
										onChange: (event) => setYearsCol(event.target.value),
										children: [/* @__PURE__ */ jsx("option", {
											value: "",
											children: "Select a column"
										}), numericColumns.map((col) => /* @__PURE__ */ jsx("option", {
											value: col,
											children: col
										}, col))]
									})]
								}),
								/* @__PURE__ */ jsxs("label", {
									className: "space-y-2 text-sm",
									children: [/* @__PURE__ */ jsx("span", {
										className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground",
										children: "Total loan term"
									}), /* @__PURE__ */ jsxs("select", {
										className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm",
										value: termCol,
										onChange: (event) => setTermCol(event.target.value),
										children: [/* @__PURE__ */ jsx("option", {
											value: "",
											children: "Select a column"
										}), numericColumns.map((col) => /* @__PURE__ */ jsx("option", {
											value: col,
											children: col
										}, col))]
									})]
								})
							]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "flex flex-wrap gap-3 text-sm",
							children: [/* @__PURE__ */ jsxs("label", {
								className: "flex items-center gap-2 rounded border border-border px-3 py-2",
								children: [/* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: yearsMonths,
									onChange: (event) => setYearsMonths(event.target.checked)
								}), /* @__PURE__ */ jsx("span", { children: "Elapsed time is in months" })]
							}), /* @__PURE__ */ jsxs("label", {
								className: "flex items-center gap-2 rounded border border-border px-3 py-2",
								children: [/* @__PURE__ */ jsx("input", {
									type: "checkbox",
									checked: termMonths,
									onChange: (event) => setTermMonths(event.target.checked)
								}), /* @__PURE__ */ jsx("span", { children: "Loan term is in months" })]
							})]
						}),
						engineeringResult?.ead_configuration && /* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-background p-3 text-sm",
							children: [/* @__PURE__ */ jsx("div", {
								className: "font-medium text-xs",
								children: engineeringResult.ead_configuration.method || "EAD configuration"
							}), engineeringResult.ead_configuration.available === false && engineeringResult.ead_configuration.missing_columns?.length ? /* @__PURE__ */ jsxs("div", {
								className: "mt-2 text-[11px] text-red-600",
								children: ["Missing required columns: ", engineeringResult.ead_configuration.missing_columns.join(", ")]
							}) : engineeringResult.ead_configuration.summary && Object.keys(engineeringResult.ead_configuration.summary).length > 0 ? /* @__PURE__ */ jsxs("div", {
								className: "mt-2 text-[11px] text-muted-foreground",
								children: [
									"Mean ",
									engineeringResult.ead_configuration.summary.mean ?? "n/a",
									", median ",
									engineeringResult.ead_configuration.summary.median ?? "n/a"
								]
							}) : /* @__PURE__ */ jsx("div", {
								className: "mt-2 text-[11px] text-muted-foreground",
								children: "Configuration ready for ECL downstream processing."
							})]
						})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "grid grid-cols-1 gap-6 xl:grid-cols-3",
				children: [(appliedSteps.length > 0 || transformedSteps.length > 0) && /* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant xl:col-span-2",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex items-center justify-between gap-4",
						children: /* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Transformations applied"
						})
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-4 space-y-3 text-sm",
						children: appliedSteps.length > 0 ? appliedSteps.map((step, idx) => /* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-background p-3",
							children: [
								/* @__PURE__ */ jsx("div", {
									className: "font-medium text-xs text-foreground",
									children: step.step || `Step ${idx + 1}`
								}),
								/* @__PURE__ */ jsx("div", {
									className: "mt-1 text-[11px] text-muted-foreground",
									children: step.reason || ""
								}),
								Array.isArray(step.columns) && step.columns.length > 0 && /* @__PURE__ */ jsx("div", {
									className: "mt-2 flex flex-wrap gap-1",
									children: step.columns.map((col, cidx) => /* @__PURE__ */ jsx("span", {
										className: "inline-block rounded border border-border bg-primary/10 px-2 py-0.5 font-mono text-[10px]",
										children: col
									}, cidx))
								})
							]
						}, idx)) : transformedSteps.map((item, idx) => /* @__PURE__ */ jsx("div", {
							className: "rounded-xl border border-border bg-background p-3 text-muted-foreground",
							children: item
						}, idx))
					})]
				}), addedFeatures.length > 0 && /* @__PURE__ */ jsxs("section", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Features added"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-4 space-y-2 text-sm text-muted-foreground",
						children: addedFeatures.map((feature, idx) => /* @__PURE__ */ jsx("div", {
							className: "rounded-xl border border-border bg-background px-3 py-2 font-mono text-xs",
							children: feature
						}, idx))
					})]
				})]
			}),
			removedFeatures.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("h2", {
					className: "text-base font-semibold",
					children: "Features removed"
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 space-y-3 text-sm text-muted-foreground",
					children: removedFeatures.map((feature, idx) => {
						const reasons = appliedSteps.filter((step) => Array.isArray(step.columns) && step.columns.includes(feature)).map((step) => step.reason).filter(Boolean);
						return /* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-background p-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "font-medium text-xs",
								children: feature
							}), reasons.length > 0 && /* @__PURE__ */ jsx("div", {
								className: "mt-1 text-[11px] text-muted-foreground",
								children: reasons.join(" / ")
							})]
						}, idx);
					})
				})]
			}),
			giniRows.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "flex items-center justify-between gap-4",
					children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Univariate Gini coefficients"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "Computed on the training split only."
					})] })
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 overflow-x-auto",
					children: /* @__PURE__ */ jsxs("table", {
						className: "min-w-full border-collapse text-sm",
						children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", {
							className: "text-left text-xs uppercase tracking-wider text-muted-foreground",
							children: [/* @__PURE__ */ jsx("th", {
								className: "border-b border-border px-3 py-2",
								children: "Feature"
							}), /* @__PURE__ */ jsx("th", {
								className: "border-b border-border px-3 py-2",
								children: "Gini"
							})]
						}) }), /* @__PURE__ */ jsx("tbody", { children: giniRows.map((row) => /* @__PURE__ */ jsxs("tr", {
							className: "odd:bg-background",
							children: [/* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 font-mono text-xs",
								children: row.feature
							}), /* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 text-xs",
								children: row.score.toFixed(4)
							})]
						}, row.feature)) })]
					})
				})]
			}),
			miData.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "flex items-center justify-between gap-4",
					children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Mutual information"
					}), /* @__PURE__ */ jsxs("p", {
						className: "text-xs text-muted-foreground",
						children: [
							"All numeric features ranked by mutual information with target (",
							miData.length,
							" features)."
						]
					})] })
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 overflow-y-auto",
					style: { maxHeight: "600px" },
					children: miData.length > 0 && /* @__PURE__ */ jsx("div", {
						style: { height: Math.max(400, miData.length * 25) },
						children: /* @__PURE__ */ jsx(ResponsiveContainer, {
							width: "100%",
							height: "100%",
							children: /* @__PURE__ */ jsxs(BarChart, {
								data: miData,
								layout: "vertical",
								margin: { left: 150 },
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
										fontSize: 10
									}),
									/* @__PURE__ */ jsx(YAxis, {
										type: "category",
										dataKey: "feature",
										tickLine: false,
										axisLine: false,
										fontSize: 9,
										width: 145
									}),
									/* @__PURE__ */ jsx(Tooltip, { contentStyle: {
										borderRadius: 10,
										border: "1px solid oklch(0.92 0.005 240)"
									} }),
									/* @__PURE__ */ jsx(Bar, {
										dataKey: "score",
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
					})
				})]
			}),
			highCorrPairs.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("h2", {
					className: "text-base font-semibold",
					children: "Highly correlated pairs"
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 space-y-3 text-sm text-muted-foreground",
					children: highCorrPairs.map((pair, idx) => /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-background p-3",
						children: [/* @__PURE__ */ jsxs("div", {
							className: "font-medium text-xs",
							children: [
								pair.feature_1,
								" ↔ ",
								pair.feature_2
							]
						}), /* @__PURE__ */ jsxs("div", {
							className: "mt-1 text-[11px]",
							children: ["Correlation: ", Number(pair.correlation).toFixed(4)]
						})]
					}, idx))
				})]
			}),
			vifRows.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-center justify-between gap-4",
					children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "VIF table"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "Variance inflation factor estimates for numeric features."
					})] }), /* @__PURE__ */ jsxs("div", {
						className: "flex gap-2 text-xs",
						children: [/* @__PURE__ */ jsx("button", {
							type: "button",
							className: "rounded-full border border-border bg-background px-2 py-1 text-muted-foreground hover:border-primary hover:text-foreground",
							onClick: () => {
								setVifSortKey("feature");
								setVifSortAsc((prev) => vifSortKey === "feature" ? !prev : true);
							},
							children: "Sort by feature"
						}), /* @__PURE__ */ jsx("button", {
							type: "button",
							className: "rounded-full border border-border bg-background px-2 py-1 text-muted-foreground hover:border-primary hover:text-foreground",
							onClick: () => {
								setVifSortKey("value");
								setVifSortAsc((prev) => vifSortKey === "value" ? !prev : true);
							},
							children: "Sort by VIF"
						})]
					})]
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 overflow-x-auto",
					children: /* @__PURE__ */ jsxs("table", {
						className: "min-w-full border-collapse text-sm",
						children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", {
							className: "text-left text-xs uppercase tracking-wider text-muted-foreground",
							children: [/* @__PURE__ */ jsx("th", {
								className: "border-b border-border px-3 py-2",
								children: "Feature"
							}), /* @__PURE__ */ jsx("th", {
								className: "border-b border-border px-3 py-2",
								children: "VIF"
							})]
						}) }), /* @__PURE__ */ jsx("tbody", { children: sortedVifRows.map((row) => /* @__PURE__ */ jsxs("tr", {
							className: "odd:bg-background",
							children: [/* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 font-mono text-xs",
								children: row.feature
							}), /* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 text-xs",
								children: row.value.toFixed(3)
							})]
						}, row.feature)) })]
					})
				})]
			}),
			ivData.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [
					/* @__PURE__ */ jsx("div", {
						className: "flex items-center justify-between gap-4",
						children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Information value"
						}), /* @__PURE__ */ jsxs("p", {
							className: "text-xs text-muted-foreground",
							children: [
								"All computed IV features and WOE transformation candidates (",
								ivData.length,
								" features)."
							]
						})] })
					}),
					/* @__PURE__ */ jsx("div", {
						className: "mt-4 overflow-x-auto",
						children: /* @__PURE__ */ jsxs("table", {
							className: "min-w-full border-collapse text-sm",
							children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", {
								className: "text-left text-xs uppercase tracking-wider text-muted-foreground",
								children: [
									/* @__PURE__ */ jsx("th", {
										className: "border-b border-border px-3 py-2",
										children: "Feature"
									}),
									/* @__PURE__ */ jsx("th", {
										className: "border-b border-border px-3 py-2",
										children: "IV"
									}),
									/* @__PURE__ */ jsx("th", {
										className: "border-b border-border px-3 py-2",
										children: "WOE Applied"
									})
								]
							}) }), /* @__PURE__ */ jsx("tbody", { children: ivData.map((row) => /* @__PURE__ */ jsxs("tr", {
								className: "odd:bg-background",
								children: [
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: row.feature
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 text-xs",
										children: row.iv.toFixed(5)
									}),
									/* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 text-xs",
										children: woeCols.includes(row.feature) ? "Yes" : "No"
									})
								]
							}, row.feature)) })]
						})
					}),
					woeInfo.length > 0 && /* @__PURE__ */ jsxs("div", {
						className: "mt-6",
						children: [/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "WOE Transformation Details"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3",
							children: woeInfo.map((info) => /* @__PURE__ */ jsxs("div", {
								className: "rounded-xl border border-border bg-background p-3 text-sm",
								children: [/* @__PURE__ */ jsx("div", {
									className: "font-medium text-xs",
									children: info.feature
								}), /* @__PURE__ */ jsxs("div", {
									className: "mt-1 text-[11px] text-muted-foreground",
									children: ["WOE buckets: ", info.buckets]
								})]
							}, info.feature))
						})]
					})
				]
			}),
			regulatoryAlerts.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("h2", {
					className: "text-base font-semibold",
					children: "Regulatory insights"
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 space-y-3",
					children: regulatoryAlerts.map((alert, idx) => /* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-amber-200 bg-amber-50 p-4",
						children: [
							/* @__PURE__ */ jsx("div", {
								className: "text-sm font-semibold",
								children: alert.rule_id || alert.id || alert.code || alert.rule || `Alert ${idx + 1}`
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-1 text-sm text-muted-foreground",
								children: alert.flag || alert.message || alert.detail || alert.description || JSON.stringify(alert)
							}),
							alert.observed_value && /* @__PURE__ */ jsxs("div", {
								className: "mt-2 text-xs font-mono text-muted-foreground",
								children: ["Observed: ", Array.isArray(alert.observed_value) ? alert.observed_value.join(", ") : String(alert.observed_value)]
							}),
							alert.suggestion && /* @__PURE__ */ jsxs("div", {
								className: "mt-2 text-[11px] text-muted-foreground",
								children: ["Recommendation: ", alert.suggestion]
							}),
							alert.source && /* @__PURE__ */ jsxs("div", {
								className: "mt-1 text-[11px] text-muted-foreground",
								children: [
									"Reference: ",
									alert.source,
									" — ",
									alert.principle || alert.section || ""
								]
							})
						]
					}, idx))
				})]
			}),
			engineeringResult.x_engineered_preview && Array.isArray(engineeringResult.x_engineered_preview) && engineeringResult.x_engineered_preview.length > 0 && /* @__PURE__ */ jsxs("section", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "flex items-center justify-between gap-4",
					children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
						className: "text-base font-semibold",
						children: "Engineered feature matrix preview"
					}), /* @__PURE__ */ jsx("p", {
						className: "text-xs text-muted-foreground",
						children: "A sample of the transformed dataset after feature engineering."
					})] })
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-4 overflow-x-auto",
					children: /* @__PURE__ */ jsxs("table", {
						className: "min-w-full border-collapse text-sm",
						children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", { children: Object.keys(engineeringResult.x_engineered_preview[0]).map((key) => /* @__PURE__ */ jsx("th", {
							className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
							children: key
						}, key)) }) }), /* @__PURE__ */ jsx("tbody", { children: engineeringResult.x_engineered_preview.map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
							className: rowIndex % 2 === 0 ? "bg-background" : "",
							children: Object.values(row).map((cell, cellIndex) => /* @__PURE__ */ jsx("td", {
								className: "border-b border-border px-3 py-2 font-mono text-xs",
								children: String(cell)
							}, cellIndex))
						}, rowIndex)) })]
					})
				})]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
				children: [/* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition hover:border-primary hover:bg-primary-soft",
					onClick: () => navigate("/preprocessing"),
					children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Preprocessing"]
				}), /* @__PURE__ */ jsxs("button", {
					className: "inline-flex items-center justify-center gap-2 rounded-lg border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition disabled:cursor-not-allowed disabled:opacity-50",
					onClick: () => navigate("/models"),
					disabled: !canProceed,
					children: ["Proceed to Model Selection", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})]
			})
		]
	});
}
//#endregion
export { Features as component };
