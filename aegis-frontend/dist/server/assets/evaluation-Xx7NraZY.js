import { n as PageHeader } from "./app-shell-DVyXktRn.js";
import { n as useDataset } from "./app-context-DEU1RUW-.js";
import { t as apiUrl } from "./api-EJXRGsO6.js";
import { t as Button } from "./button-CRuuOnrV.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { t as Badge } from "./badge-BQ9cV5rG.js";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { ArrowLeft, ArrowRight, Download, ShieldCheck } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart as LineChart$1, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/evaluation.tsx?tsr-split=component
function makeCsvRows(metrics) {
	return Object.entries(metrics).map(([key, value]) => {
		let formatted = value;
		if (typeof value === "object" && value !== null) try {
			formatted = JSON.stringify(value);
		} catch {
			formatted = String(value);
		}
		return [key, String(formatted)];
	});
}
function downloadCsv(metrics, fileName) {
	const csv = ["metric,value", ...makeCsvRows(metrics).map(([key, value]) => `${JSON.stringify(key)},${JSON.stringify(value)}`)].join("\n");
	const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = fileName;
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(url);
}
function downloadBase64File(base64, fileName) {
	const binary = atob(base64);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
	const blob = new Blob([bytes], { type: "application/octet-stream" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = fileName;
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(url);
}
function statusToBadgeVariant(status) {
	switch (status) {
		case "PASS": return "default";
		case "WARN": return "secondary";
		case "FAIL": return "destructive";
		default: return "outline";
	}
}
function formatReplicatedValue(value) {
	if (value === null || value === void 0 || Number.isNaN(value)) return "N/A";
	if (typeof value === "number") return value.toFixed(4);
	return String(value);
}
function Card({ title, sub, children }) {
	return /* @__PURE__ */ jsxs("div", {
		className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
		children: [
			/* @__PURE__ */ jsx("h3", {
				className: "text-sm font-semibold",
				children: title
			}),
			sub && /* @__PURE__ */ jsx("p", {
				className: "text-xs text-muted-foreground",
				children: sub
			}),
			/* @__PURE__ */ jsx("div", {
				className: "mt-4 h-56",
				children
			})
		]
	});
}
function Evaluation() {
	const navigate = useNavigate();
	const { trainingResult, file, profile, trainingConfig } = useDataset();
	const [complianceFlags, setComplianceFlags] = useState(null);
	const [complianceScore, setComplianceScore] = useState(null);
	const [complianceLoading, setComplianceLoading] = useState(false);
	const [complianceError, setComplianceError] = useState(null);
	const [replicationResult, setReplicationResult] = useState(null);
	const [replicationChecks, setReplicationChecks] = useState([]);
	const [replicationLoading, setReplicationLoading] = useState(false);
	const [replicationError, setReplicationError] = useState(null);
	const evaluationMetrics = trainingResult?.evaluation_metrics;
	const evaluationData = trainingResult?.evaluation_data;
	const modelArtifact = trainingResult?.model_artifact;
	const threshold = evaluationMetrics?.threshold_used ?? evaluationData?.threshold ?? .5;
	const confusion = useMemo(() => {
		const matrix = evaluationMetrics?.confusion_matrix;
		if (Array.isArray(matrix) && matrix.length === 2 && Array.isArray(matrix[0]) && Array.isArray(matrix[1])) return [
			[
				"True Negative",
				matrix[0][0],
				"primary"
			],
			[
				"False Positive",
				matrix[0][1],
				"warning"
			],
			[
				"False Negative",
				matrix[1][0],
				"destructive"
			],
			[
				"True Positive",
				matrix[1][1],
				"primary"
			]
		];
		return [
			[
				"True Negative",
				0,
				"primary"
			],
			[
				"False Positive",
				0,
				"warning"
			],
			[
				"False Negative",
				0,
				"destructive"
			],
			[
				"True Positive",
				0,
				"primary"
			]
		];
	}, [evaluationMetrics?.confusion_matrix]);
	const gain = useMemo(() => evaluationData?.gain_chart ?? [], [evaluationData?.gain_chart]);
	const thresholds = useMemo(() => evaluationData?.threshold_analysis ?? [], [evaluationData?.threshold_analysis]);
	const rocCurve = useMemo(() => evaluationData?.roc_curve ?? [], [evaluationData?.roc_curve]);
	const prCurve = useMemo(() => evaluationData?.pr_curve ?? [], [evaluationData?.pr_curve]);
	const scoreDistribution = useMemo(() => evaluationData?.score_distribution ?? [], [evaluationData?.score_distribution]);
	useEffect(() => {
		if (!evaluationMetrics || !trainingResult) return;
		const payload = {
			stage: "evaluation",
			payload: {
				metrics: evaluationMetrics,
				training_info: trainingResult.training_info ?? {},
				threshold,
				explainability_done: false,
				heteroscedasticity_check: evaluationData?.heteroscedasticity_check ?? null,
				pd_output_present: true,
				staging_logic_present: true,
				sicr_flagged: true,
				ecl_estimated: true,
				concentration_analysis: true,
				exposure_reported: true,
				past_due_breakdown: true,
				shap_available: false
			}
		};
		setComplianceLoading(true);
		setComplianceError(null);
		fetch(apiUrl("/validation/compliance"), {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload)
		}).then(async (res) => {
			if (!res.ok) {
				const errorText = await res.text();
				throw new Error(errorText || "Failed to fetch compliance results.");
			}
			return res.json();
		}).then((body) => {
			setComplianceFlags(body.flags ?? []);
			setComplianceScore(body.report?.metadata?.compliance_score ?? null);
		}).catch((error) => {
			console.error("Evaluation compliance fetch failed", error);
			setComplianceError("Unable to load compliance summary.");
		}).finally(() => {
			setComplianceLoading(false);
		});
	}, [
		evaluationMetrics,
		evaluationData?.heteroscedasticity_check,
		threshold,
		trainingResult
	]);
	useEffect(() => {
		if (!trainingResult || !file || !profile?.target_col) return;
		const replicationPayload = new FormData();
		replicationPayload.append("file", file);
		replicationPayload.append("target_col", profile.target_col);
		replicationPayload.append("model_name", trainingResult.model_name);
		replicationPayload.append("seeds", "42,43,44,45,46");
		replicationPayload.append("test_size", String(trainingConfig?.test_size ?? .15));
		replicationPayload.append("val_size", String(trainingConfig?.val_size ?? .15));
		replicationPayload.append("random_seed", String(trainingConfig?.random_seed ?? 42));
		replicationPayload.append("cv_folds", String(trainingConfig?.cv_folds ?? 5));
		setReplicationLoading(true);
		setReplicationError(null);
		fetch(apiUrl("/validation/replication"), {
			method: "POST",
			body: replicationPayload
		}).then(async (res) => {
			if (!res.ok) {
				const errorText = await res.text();
				throw new Error(errorText || "Failed to fetch replication results.");
			}
			return res.json();
		}).then((body) => {
			setReplicationResult(body.report?.replication?.result ?? null);
			setReplicationChecks(body.report?.replication?.checks ?? []);
		}).catch((error) => {
			console.error("Evaluation replication fetch failed", error);
			setReplicationError("Unable to load replication results.");
		}).finally(() => {
			setReplicationLoading(false);
		});
	}, [
		trainingResult,
		file,
		profile?.target_col,
		trainingConfig?.test_size,
		trainingConfig?.val_size,
		trainingConfig?.random_seed,
		trainingConfig?.cv_folds
	]);
	if (!trainingResult) return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Evaluation",
			description: "Interactive performance diagnostics on the hold-out test set."
		}), /* @__PURE__ */ jsxs("div", {
			className: "rounded-xl border border-border bg-card p-6 text-center",
			children: [
				/* @__PURE__ */ jsx("h3", {
					className: "text-lg font-semibold",
					children: "No trained model available"
				}),
				/* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: "Run training first to populate evaluation metrics and compliance checks."
				}),
				/* @__PURE__ */ jsx(Button, {
					onClick: () => navigate({ to: "/training" }),
					className: "mt-4",
					children: "Go to Training"
				})
			]
		})]
	});
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "Evaluation",
				description: "Interactive performance diagnostics on the hold-out test set.",
				actions: /* @__PURE__ */ jsxs("div", {
					className: "flex flex-wrap gap-2",
					children: [evaluationMetrics && /* @__PURE__ */ jsxs(Button, {
						variant: "outline",
						onClick: () => downloadCsv(evaluationMetrics, "evaluation_metrics.csv"),
						className: "gap-2",
						children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download metrics CSV"]
					}), modelArtifact && /* @__PURE__ */ jsxs(Button, {
						variant: "outline",
						onClick: () => downloadBase64File(modelArtifact, "trained_model.pkl"),
						className: "gap-2",
						children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download model artifact"]
					})]
				})
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_420px]",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "space-y-6",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "grid gap-6 lg:grid-cols-2",
							children: [/* @__PURE__ */ jsx(Card, {
								title: "ROC curve",
								sub: evaluationMetrics?.roc_auc ? `AUC ${evaluationMetrics.roc_auc}` : "Probability output unavailable",
								children: /* @__PURE__ */ jsx(ChartContainer, {
									width: "100%",
									height: "100%",
									children: /* @__PURE__ */ jsxs(AreaChart, {
										data: rocCurve,
										children: [
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
												fill: "oklch(0.76 0.18 130)",
												fillOpacity: .3
											}),
											/* @__PURE__ */ jsx(Line, {
												type: "linear",
												dataKey: "fpr",
												stroke: "oklch(0.6 0.01 240)",
												strokeDasharray: "4 4",
												dot: false
											})
										]
									})
								})
							}), /* @__PURE__ */ jsx(Card, {
								title: "Precision–Recall",
								sub: evaluationMetrics?.pr_auc ? `Average precision ${evaluationMetrics.pr_auc}` : "Probability output unavailable",
								children: /* @__PURE__ */ jsx(ChartContainer, {
									width: "100%",
									height: "100%",
									children: /* @__PURE__ */ jsxs(AreaChart, {
										data: prCurve,
										children: [
											/* @__PURE__ */ jsx(CartesianGrid, {
												stroke: "oklch(0.92 0.005 240)",
												strokeDasharray: "3 3"
											}),
											/* @__PURE__ */ jsx(XAxis, {
												dataKey: "recall",
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
												dataKey: "precision",
												stroke: "oklch(0.6 0.18 135)",
												fill: "oklch(0.76 0.18 130)",
												fillOpacity: .3
											})
										]
									})
								})
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "grid gap-6 lg:grid-cols-2",
							children: [/* @__PURE__ */ jsx(Card, {
								title: "Confusion matrix",
								sub: `Threshold ${threshold.toFixed(2)}`,
								children: /* @__PURE__ */ jsx("div", {
									className: "grid h-full grid-cols-2 gap-3",
									children: confusion.map(([label, n, tone]) => /* @__PURE__ */ jsxs("div", {
										className: "flex flex-col justify-between rounded-xl border p-4 " + (tone === "primary" ? "border-primary/30 bg-primary-soft" : tone === "warning" ? "border-warning/40 bg-warning/15" : "border-destructive/30 bg-destructive/10"),
										children: [/* @__PURE__ */ jsx("span", {
											className: "text-[11px] uppercase tracking-wider text-muted-foreground",
											children: label
										}), /* @__PURE__ */ jsx("span", {
											className: "text-2xl font-semibold tabular-nums",
											children: Number(n).toLocaleString()
										})]
									}, label))
								})
							}), /* @__PURE__ */ jsx(Card, {
								title: "Cumulative gain",
								sub: "Model vs baseline by decile",
								children: /* @__PURE__ */ jsx(ChartContainer, {
									width: "100%",
									height: "100%",
									children: /* @__PURE__ */ jsxs(LineChart$1, {
										data: gain,
										children: [
											/* @__PURE__ */ jsx(CartesianGrid, {
												stroke: "oklch(0.92 0.005 240)",
												strokeDasharray: "3 3"
											}),
											/* @__PURE__ */ jsx(XAxis, {
												dataKey: "decile",
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
											/* @__PURE__ */ jsx(Line, {
												type: "monotone",
												dataKey: "model",
												stroke: "oklch(0.6 0.18 135)",
												strokeWidth: 2.5,
												dot: false
											}),
											/* @__PURE__ */ jsx(Line, {
												type: "monotone",
												dataKey: "baseline",
												stroke: "oklch(0.6 0.01 240)",
												strokeDasharray: "4 4",
												dot: false
											})
										]
									})
								})
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "grid gap-6 lg:grid-cols-2",
							children: [/* @__PURE__ */ jsx(Card, {
								title: "Threshold analysis",
								sub: "Precision · Recall · F1 across cut-offs",
								children: /* @__PURE__ */ jsx(ChartContainer, {
									width: "100%",
									height: "100%",
									children: /* @__PURE__ */ jsxs(LineChart$1, {
										data: thresholds,
										children: [
											/* @__PURE__ */ jsx(CartesianGrid, {
												stroke: "oklch(0.92 0.005 240)",
												strokeDasharray: "3 3"
											}),
											/* @__PURE__ */ jsx(XAxis, {
												dataKey: "threshold",
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
											/* @__PURE__ */ jsx(Line, {
												type: "monotone",
												dataKey: "precision",
												stroke: "oklch(0.6 0.18 135)",
												dot: false,
												strokeWidth: 2
											}),
											/* @__PURE__ */ jsx(Line, {
												type: "monotone",
												dataKey: "recall",
												stroke: "oklch(0.6 0.22 27)",
												dot: false,
												strokeWidth: 2
											}),
											/* @__PURE__ */ jsx(Line, {
												type: "monotone",
												dataKey: "f1",
												stroke: "oklch(0.55 0.02 240)",
												dot: false,
												strokeWidth: 2
											})
										]
									})
								})
							}), /* @__PURE__ */ jsx(Card, {
								title: "Score distribution",
								sub: "Hold-out set",
								children: /* @__PURE__ */ jsx(ChartContainer, {
									width: "100%",
									height: "100%",
									children: /* @__PURE__ */ jsxs(BarChart, {
										data: scoreDistribution,
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
											/* @__PURE__ */ jsx(Bar, {
												dataKey: "good",
												stackId: "a",
												fill: "oklch(0.76 0.18 130)"
											}),
											/* @__PURE__ */ jsx(Bar, {
												dataKey: "bad",
												stackId: "a",
												fill: "oklch(0.6 0.22 27)"
											})
										]
									})
								})
							})]
						})
					]
				}), /* @__PURE__ */ jsxs("aside", {
					className: "space-y-6",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 mb-4",
								children: [/* @__PURE__ */ jsx(ShieldCheck, { className: "h-4 w-4 text-primary" }), /* @__PURE__ */ jsx("h2", {
									className: "text-base font-semibold",
									children: "Evaluation summary"
								})]
							}), /* @__PURE__ */ jsxs("div", {
								className: "grid gap-3 text-sm",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "ROC AUC" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: evaluationMetrics?.roc_auc ?? "N/A"
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "PR AUC" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: evaluationMetrics?.pr_auc ?? "N/A"
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "Recall" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: evaluationMetrics?.recall ?? "N/A"
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "Precision" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: evaluationMetrics?.precision ?? "N/A"
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "F1 score" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: evaluationMetrics?.f1 ?? "N/A"
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "Threshold" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: threshold.toFixed(2)
										})]
									})
								]
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 mb-4",
								children: [/* @__PURE__ */ jsx(ShieldCheck, { className: "h-4 w-4 text-primary" }), /* @__PURE__ */ jsx("h2", {
									className: "text-base font-semibold",
									children: "Compliance snapshot"
								})]
							}), complianceLoading ? /* @__PURE__ */ jsx("p", {
								className: "text-sm text-muted-foreground",
								children: "Loading compliance verdict…"
							}) : complianceError ? /* @__PURE__ */ jsx("p", {
								className: "text-sm text-destructive",
								children: complianceError
							}) : /* @__PURE__ */ jsxs("div", {
								className: "space-y-3 text-sm",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "Compliance score" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: complianceScore ?? "—"
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "flex items-center justify-between",
										children: [/* @__PURE__ */ jsx("span", { children: "Flags raised" }), /* @__PURE__ */ jsx("span", {
											className: "font-semibold",
											children: complianceFlags?.length ?? 0
										})]
									}),
									complianceFlags && complianceFlags.length > 0 && /* @__PURE__ */ jsx("div", {
										className: "space-y-2 pt-2",
										children: complianceFlags.slice(0, 3).map((flag, index) => /* @__PURE__ */ jsxs("div", {
											className: "rounded-lg border border-border p-3 bg-background",
											children: [/* @__PURE__ */ jsx("div", {
												className: "text-xs uppercase tracking-wider text-muted-foreground",
												children: flag.rule_id
											}), /* @__PURE__ */ jsx("div", {
												className: "mt-1 text-sm font-semibold",
												children: flag.flag
											})]
										}, index))
									}),
									!complianceFlags?.length && /* @__PURE__ */ jsx("p", {
										className: "text-sm text-muted-foreground",
										children: "No compliance flags were raised in this evaluation run."
									})
								]
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 mb-4",
								children: [/* @__PURE__ */ jsx(ShieldCheck, { className: "h-4 w-4 text-primary" }), /* @__PURE__ */ jsx("h2", {
									className: "text-base font-semibold",
									children: "Replication validation"
								})]
							}), replicationLoading ? /* @__PURE__ */ jsx("p", {
								className: "text-sm text-muted-foreground",
								children: "Running replication checks…"
							}) : replicationError ? /* @__PURE__ */ jsx("p", {
								className: "text-sm text-destructive",
								children: replicationError
							}) : replicationResult ? /* @__PURE__ */ jsxs("div", {
								className: "space-y-4 text-sm",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "grid gap-3 text-sm",
										children: [
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "AUC" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.roc_auc)
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "Gini" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.gini)
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "KS" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.ks)
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "Accuracy" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.accuracy)
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "Precision" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.precision)
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "Recall" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.recall)
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("span", { children: "F1 score" }), /* @__PURE__ */ jsx("span", {
													className: "font-semibold",
													children: formatReplicatedValue(replicationResult.metrics?.f1)
												})]
											})
										]
									}),
									/* @__PURE__ */ jsx("div", {
										className: "grid gap-2",
										children: replicationChecks?.slice(0, 6).map((check, index) => /* @__PURE__ */ jsxs("div", {
											className: "flex items-center justify-between rounded-xl border border-border bg-background px-3 py-2",
											children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
												className: "text-xs uppercase tracking-wider text-muted-foreground",
												children: check.id
											}), /* @__PURE__ */ jsx("div", {
												className: "font-semibold",
												children: check.title
											})] }), /* @__PURE__ */ jsx(Badge, {
												variant: statusToBadgeVariant(check.status),
												children: check.status
											})]
										}, index))
									}),
									replicationChecks && replicationChecks.length > 6 && /* @__PURE__ */ jsx("p", {
										className: "text-xs text-muted-foreground",
										children: "Showing first 6 replication checks; view full report on the backend payload."
									})
								]
							}) : /* @__PURE__ */ jsx("p", {
								className: "text-sm text-muted-foreground",
								children: "Replication results will appear after a successful evaluation training session."
							})]
						})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "flex gap-3 pt-4",
				children: [/* @__PURE__ */ jsxs(Button, {
					variant: "outline",
					onClick: () => navigate({ to: "/training" }),
					className: "gap-2",
					children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Training"]
				}), /* @__PURE__ */ jsxs(Button, {
					onClick: () => navigate({ to: "/explainability" }),
					className: "gap-2 ml-auto",
					children: ["Proceed to Explainability", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
				})]
			})
		]
	});
}
//#endregion
export { Evaluation as component };
