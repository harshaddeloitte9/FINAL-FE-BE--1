import { n as PageHeader } from "./app-shell-DVyXktRn.js";
import { n as useDataset } from "./app-context-DEU1RUW-.js";
import { n as formUpload } from "./api-EJXRGsO6.js";
import { t as Button } from "./button-CRuuOnrV.js";
import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";
//#region src/routes/preprocessing.tsx?tsr-split=component
function Preprocessing() {
	const { profile, file } = useDataset();
	const navigate = useNavigate();
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [preprocess, setPreprocess] = useState(null);
	useEffect(() => {
		const runPreprocess = async () => {
			if (!profile) return;
			const allColumns = profile.columns ?? [];
			let targetCol = null;
			if (allColumns.includes("loan_status")) targetCol = "loan_status";
			else if (profile.target_candidates && profile.target_candidates.length > 0) targetCol = profile.target_candidates[0];
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
				console.log("Preprocessing: POST /data/preprocess", {
					targetCol,
					file: !!file
				});
				const response = await formUpload("/data/preprocess", form);
				console.log("Preprocessing: response", response);
				setPreprocess(response);
			} catch (err) {
				console.error("Preprocessing: failed", err);
				setError(err?.body?.detail ?? err?.message ?? "Preprocessing failed.");
				setPreprocess(null);
			} finally {
				setLoading(false);
			}
		};
		runPreprocess();
	}, [profile, file]);
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
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Preprocessing",
				description: "Reproducible transformations applied to the training dataset."
			}),
			loading && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground",
				children: "Running preprocessing via backend..."
			}),
			error && /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-border bg-card p-6 text-center text-sm text-destructive",
				children: error
			}),
			preprocess && /* @__PURE__ */ jsxs("div", {
				className: "grid grid-cols-1 gap-4 md:grid-cols-2",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft",
								children: /* @__PURE__ */ jsx(CheckCircle2, { className: "h-5 w-5 text-primary" })
							}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
								className: "text-sm font-semibold",
								children: "Preprocessing steps"
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-2 text-xs text-muted-foreground",
								children: "Transformations applied to the dataset."
							})] })]
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-4 space-y-3",
							children: preprocess.preprocessing_report && Array.isArray(preprocess.preprocessing_report.decisions) ? preprocess.preprocessing_report.decisions.map((item, index) => /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-3",
								children: [/* @__PURE__ */ jsxs("div", {
									className: "font-medium text-sm",
									children: [
										item.column,
										" (",
										item.type,
										")"
									]
								}), Array.isArray(item.actions) && item.actions.length > 0 && /* @__PURE__ */ jsx("ul", {
									className: "mt-2 space-y-1",
									children: item.actions.map((action, actionIndex) => /* @__PURE__ */ jsxs("li", {
										className: "text-xs text-muted-foreground",
										children: ["• ", action]
									}, actionIndex))
								})]
							}, index)) : /* @__PURE__ */ jsx("div", {
								className: "text-sm text-muted-foreground",
								children: "No preprocessing steps recorded."
							})
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-sm font-semibold",
							children: "Transformed dataset"
						}), /* @__PURE__ */ jsxs("div", {
							className: "mt-4 grid gap-3 text-sm text-muted-foreground",
							children: [
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-xl border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-wider",
										children: "Features"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold tabular-nums",
										children: Array.isArray(preprocess.feature_names) ? preprocess.feature_names.length : "—"
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-xl border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-wider",
										children: "X shape"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold tabular-nums",
										children: Array.isArray(preprocess.x_shape) ? preprocess.x_shape.join(" × ") : "—"
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-xl border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-wider",
										children: "Y shape"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold tabular-nums",
										children: Array.isArray(preprocess.y_shape) ? preprocess.y_shape.join(" × ") : "—"
									})]
								})
							]
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant md:col-span-2",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-sm font-semibold",
							children: "Feature preview"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-4 overflow-x-auto",
							children: Array.isArray(preprocess.x_preview) && preprocess.x_preview.length > 0 ? /* @__PURE__ */ jsxs("table", {
								className: "min-w-full border-collapse text-sm",
								children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", { children: Object.keys(preprocess.x_preview[0]).map((key) => /* @__PURE__ */ jsx("th", {
									className: "border-b border-border px-3 py-2 text-left font-medium text-muted-foreground",
									children: key
								}, key)) }) }), /* @__PURE__ */ jsx("tbody", { children: preprocess.x_preview.map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
									className: rowIndex % 2 === 0 ? "bg-background" : "",
									children: Object.values(row).map((cell, cellIndex) => /* @__PURE__ */ jsx("td", {
										className: "border-b border-border px-3 py-2 font-mono text-xs",
										children: String(cell)
									}, cellIndex))
								}, rowIndex)) })]
							}) : /* @__PURE__ */ jsx("div", {
								className: "p-6 text-center text-sm text-muted-foreground",
								children: "No feature preview available."
							})
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant md:col-span-2",
						children: [/* @__PURE__ */ jsx("div", {
							className: "text-sm font-semibold",
							children: "Target preview"
						}), /* @__PURE__ */ jsx("div", {
							className: "mt-4",
							children: Array.isArray(preprocess.y_preview) && preprocess.y_preview.length > 0 ? /* @__PURE__ */ jsx("div", {
								className: "grid grid-cols-1 gap-2 md:grid-cols-5",
								children: preprocess.y_preview.map((value, index) => /* @__PURE__ */ jsx("div", {
									className: "rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs text-center",
									children: String(value)
								}, index))
							}) : /* @__PURE__ */ jsx("div", {
								className: "text-sm text-muted-foreground",
								children: "No target preview available."
							})
						})]
					})
				]
			}),
			preprocess && /* @__PURE__ */ jsxs("div", {
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
		]
	});
}
//#endregion
export { Preprocessing as component };
