import { n as PageHeader } from "./app-shell-fDQz9JMF.js";
import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-CPpoZWeE.js";
import { t as Button } from "./button-MHHI04mG.js";
import { t as ChartContainer } from "./chart-container-DJlEkxVk.js";
import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { AlertCircle, ArrowLeft, ArrowRight, Calculator, Download, Loader2 } from "lucide-react";
import { Area, AreaChart, Bar, BarChart as BarChart$1, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
//#region src/routes/ecl-provisions.tsx?tsr-split=component
function EclProvisions() {
	const navigate = useNavigate();
	const { file, profile, trainingResult } = useDataset();
	const availableColumns = useMemo(() => profile?.columns ?? [], [profile]);
	const targetColumn = useMemo(() => {
		if (profile?.target_col) return profile.target_col;
		if (Array.isArray(profile?.target_candidates) && profile.target_candidates.length > 0) return profile.target_candidates[0];
		return availableColumns.find((column) => [
			"loan_status",
			"default",
			"target",
			"label"
		].includes(column)) ?? "loan_status";
	}, [availableColumns, profile]);
	const [eadColumn, setEadColumn] = useState("");
	const [lgdMethod, setLgdMethod] = useState("fixed");
	const [lgdValue, setLgdValue] = useState(.45);
	const [loanTypeColumn, setLoanTypeColumn] = useState("");
	const [ltvColumn, setLtvColumn] = useState("");
	const [dpdColumn, setDpdColumn] = useState("");
	const [originationPdColumn, setOriginationPdColumn] = useState("");
	const [remainingMaturityColumn, setRemainingMaturityColumn] = useState("");
	const [relativePdMultiplier, setRelativePdMultiplier] = useState(1.5);
	const [absolutePdIncrease, setAbsolutePdIncrease] = useState(.03);
	const [dpdBackstop, setDpdBackstop] = useState(30);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);
	const [summary, setSummary] = useState(null);
	const [sampleRows, setSampleRows] = useState([]);
	const [columns, setColumns] = useState([]);
	const stageExposureData = useMemo(() => {
		const stageCounts = summary?.ead_by_stage ?? {};
		return [
			{
				stage: "Stage 1",
				value: Number(stageCounts.stage_1 ?? 0)
			},
			{
				stage: "Stage 2",
				value: Number(stageCounts.stage_2 ?? 0)
			},
			{
				stage: "Stage 3",
				value: Number(stageCounts.stage_3 ?? 0)
			}
		];
	}, [summary]);
	const eclDistributionData = useMemo(() => {
		const stageEcl = summary?.ecl_by_stage ?? {};
		return [
			{
				stage: "Stage 1",
				value: Number(stageEcl.stage_1 ?? 0)
			},
			{
				stage: "Stage 2",
				value: Number(stageEcl.stage_2 ?? 0)
			},
			{
				stage: "Stage 3",
				value: Number(stageEcl.stage_3 ?? 0)
			}
		];
	}, [summary]);
	const calculateEcl = async () => {
		if (!file) {
			setError("Upload a dataset before running the ECL workflow.");
			return;
		}
		if (!trainingResult?.model_artifact) {
			setError("Train a model before calculating ECL. The backend needs the trained model artifact.");
			return;
		}
		setLoading(true);
		setError(null);
		try {
			const form = new FormData();
			form.append("model_artifact", trainingResult.model_artifact);
			form.append("file", file);
			form.append("target_col", targetColumn);
			if (eadColumn) form.append("ead_col", eadColumn);
			if (lgdMethod === "loan-type" && loanTypeColumn) form.append("loan_type_col", loanTypeColumn);
			const cfg = {
				lgd_method: lgdMethod === "ltv" ? "ltv" : "fixed",
				lgd_fixed: lgdMethod === "fixed" ? lgdValue : .45,
				ltv_col: lgdMethod === "ltv" ? ltvColumn || void 0 : void 0,
				pd_relative_threshold: relativePdMultiplier,
				pd_absolute_threshold: absolutePdIncrease,
				dpd_sicr_threshold: dpdBackstop,
				dpd_col: dpdColumn || void 0,
				orig_pd_col: originationPdColumn || void 0,
				maturity_col: remainingMaturityColumn || void 0
			};
			form.append("cfg", JSON.stringify(cfg));
			if (lgdMethod === "loan-type" && loanTypeColumn) {
				const inferLgdMap = () => {
					const previewValues = Array.isArray(profile?.data_preview) ? profile.data_preview.map((row) => row?.[loanTypeColumn]).filter((value) => value !== void 0 && value !== null && value !== "") : [];
					const uniqueValues = Array.from(new Set(previewValues.map((value) => String(value)))).slice(0, 8);
					return Object.fromEntries(uniqueValues.map((value, index) => [value, Number((.25 + index * .05).toFixed(2))]));
				};
				form.append("lgd_map", JSON.stringify(inferLgdMap()));
			}
			const response = await formUpload("/ecl/compute", form);
			setSummary(response.summary ?? null);
			setSampleRows(response.sample_rows ?? []);
			setColumns(response.columns ?? []);
		} catch (err) {
			console.error("ECL calculation failed", err);
			setError(err?.body?.detail ?? err?.message ?? "Unable to calculate ECL from the backend.");
		} finally {
			setLoading(false);
		}
	};
	const handleDownload = () => {
		if (!sampleRows.length) return;
		const exportColumns = columns.length ? columns : Object.keys(sampleRows[0] ?? {});
		const csvRows = [exportColumns.join(",")];
		for (const row of sampleRows) csvRows.push(exportColumns.map((column) => {
			const value = row?.[column];
			return `"${(value === null || value === void 0 ? "" : String(value).replace(/\n/g, " ")).replace(/"/g, "\"\"")}"`;
		}).join(","));
		const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = "ecl_results.csv";
		anchor.click();
		URL.revokeObjectURL(url);
	};
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [
			/* @__PURE__ */ jsx(PageHeader, {
				title: "ECL & Provisions",
				description: "Step 9 — IFRS 9 ECL estimation with SICR staging and portfolio-level provision output."
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-primary/30 bg-primary-soft p-4 text-sm text-foreground/90",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-center gap-2 font-semibold",
					children: [/* @__PURE__ */ jsx(Calculator, { className: "h-4 w-4" }), "Backend-driven IFRS 9 workflow for staging, ECL, and provision visibility."]
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-foreground/80",
					children: "The controls below mirror the Streamlit workflow and now call the existing FastAPI ECL endpoint with the uploaded dataset and trained model artifact."
				})]
			}),
			error ? /* @__PURE__ */ jsx("div", {
				className: "rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700",
				children: /* @__PURE__ */ jsxs("div", {
					className: "flex items-start gap-2",
					children: [/* @__PURE__ */ jsx(AlertCircle, { className: "mt-0.5 h-4 w-4" }), /* @__PURE__ */ jsx("div", { children: error })]
				})
			}) : null,
			/* @__PURE__ */ jsxs("div", {
				className: "grid grid-cols-1 gap-6 xl:grid-cols-[1.25fr_0.75fr]",
				children: [/* @__PURE__ */ jsx("div", {
					className: "space-y-6",
					children: /* @__PURE__ */ jsxs("section", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "mb-4 flex items-center justify-between",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h2", {
									className: "text-base font-semibold",
									children: "Step 9 — ECL Calculation (IFRS 9)"
								}), /* @__PURE__ */ jsx("p", {
									className: "text-xs text-muted-foreground",
									children: "SICR assessment → Stage 1/2/3 classification → ECL = PD × LGD × EAD"
								})] }), /* @__PURE__ */ jsx("span", {
									className: "rounded-full bg-primary-soft px-2.5 py-1 text-[11px] font-medium text-foreground",
									children: "Live backend"
								})]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "space-y-6",
								children: [/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("h3", {
										className: "text-sm font-semibold",
										children: "Exposure & Loss Inputs"
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-4 grid grid-cols-1 gap-4 md:grid-cols-2",
										children: [/* @__PURE__ */ jsxs("label", {
											className: "space-y-2 text-sm",
											children: [/* @__PURE__ */ jsx("span", {
												className: "font-medium",
												children: "Exposure / balance column"
											}), /* @__PURE__ */ jsxs("select", {
												value: eadColumn,
												onChange: (event) => setEadColumn(event.target.value),
												className: "w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
												children: [/* @__PURE__ */ jsx("option", {
													value: "",
													children: "Auto-detect"
												}), availableColumns.map((column) => /* @__PURE__ */ jsx("option", {
													value: column,
													children: column
												}, column))]
											})]
										}), /* @__PURE__ */ jsxs("div", {
											className: "space-y-2 text-sm",
											children: [/* @__PURE__ */ jsx("span", {
												className: "font-medium",
												children: "LGD Method"
											}), /* @__PURE__ */ jsx("div", {
												className: "grid grid-cols-1 gap-2 rounded-lg border border-border bg-background p-2",
												children: [
													{
														value: "fixed",
														label: "Fixed Assumption"
													},
													{
														value: "loan-type",
														label: "By Loan Type"
													},
													{
														value: "ltv",
														label: "From LTV Column"
													}
												].map((option) => /* @__PURE__ */ jsxs("label", {
													className: "flex items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-muted/40",
													children: [/* @__PURE__ */ jsx("input", {
														type: "radio",
														name: "lgd-method",
														value: option.value,
														checked: lgdMethod === option.value,
														onChange: () => setLgdMethod(option.value)
													}), /* @__PURE__ */ jsx("span", { children: option.label })]
												}, option.value))
											})]
										})]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-4 rounded-lg border border-border bg-background p-4",
										children: [
											/* @__PURE__ */ jsxs("div", {
												className: "flex items-center justify-between",
												children: [/* @__PURE__ */ jsx("label", {
													className: "text-sm font-medium",
													children: "LGD assumption"
												}), /* @__PURE__ */ jsxs("span", {
													className: "text-sm font-semibold",
													children: [(lgdValue * 100).toFixed(0), "%"]
												})]
											}),
											/* @__PURE__ */ jsx("input", {
												type: "range",
												min: "0.05",
												max: "0.95",
												step: "0.05",
												value: lgdValue,
												onChange: (event) => setLgdValue(Number(event.target.value)),
												className: "mt-3 w-full"
											}),
											/* @__PURE__ */ jsx("p", {
												className: "mt-2 text-xs text-muted-foreground",
												children: lgdMethod === "fixed" ? "Applies the same loss-given-default assumption to every loan." : lgdMethod === "loan-type" ? "The backend receives a loan-type LGD map derived from the selected column." : "LGD is inferred from the selected LTV column using the backend configuration."
											})
										]
									})
								] }), /* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("h3", {
										className: "text-sm font-semibold",
										children: "IFRS 9 SICR & Staging"
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-4 grid grid-cols-1 gap-4 md:grid-cols-2",
										children: [
											/* @__PURE__ */ jsxs("label", {
												className: "space-y-2 text-sm",
												children: [/* @__PURE__ */ jsx("span", {
													className: "font-medium",
													children: "DPD column"
												}), /* @__PURE__ */ jsxs("select", {
													value: dpdColumn,
													onChange: (event) => setDpdColumn(event.target.value),
													className: "w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
													children: [/* @__PURE__ */ jsx("option", {
														value: "",
														children: "Auto-detect"
													}), availableColumns.map((column) => /* @__PURE__ */ jsx("option", {
														value: column,
														children: column
													}, column))]
												})]
											}),
											/* @__PURE__ */ jsxs("label", {
												className: "space-y-2 text-sm",
												children: [/* @__PURE__ */ jsx("span", {
													className: "font-medium",
													children: "Origination PD column"
												}), /* @__PURE__ */ jsxs("select", {
													value: originationPdColumn,
													onChange: (event) => setOriginationPdColumn(event.target.value),
													className: "w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
													children: [/* @__PURE__ */ jsx("option", {
														value: "",
														children: "Auto-detect"
													}), availableColumns.map((column) => /* @__PURE__ */ jsx("option", {
														value: column,
														children: column
													}, column))]
												})]
											}),
											/* @__PURE__ */ jsxs("label", {
												className: "space-y-2 text-sm",
												children: [/* @__PURE__ */ jsx("span", {
													className: "font-medium",
													children: "Remaining maturity column"
												}), /* @__PURE__ */ jsxs("select", {
													value: remainingMaturityColumn,
													onChange: (event) => setRemainingMaturityColumn(event.target.value),
													className: "w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
													children: [/* @__PURE__ */ jsx("option", {
														value: "",
														children: "Auto-detect"
													}), availableColumns.map((column) => /* @__PURE__ */ jsx("option", {
														value: column,
														children: column
													}, column))]
												})]
											}),
											/* @__PURE__ */ jsxs("label", {
												className: "space-y-2 text-sm",
												children: [/* @__PURE__ */ jsx("span", {
													className: "font-medium",
													children: "Loan type / segmentation column"
												}), /* @__PURE__ */ jsxs("select", {
													value: loanTypeColumn,
													onChange: (event) => setLoanTypeColumn(event.target.value),
													className: "w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
													children: [/* @__PURE__ */ jsx("option", {
														value: "",
														children: "Auto-detect"
													}), availableColumns.map((column) => /* @__PURE__ */ jsx("option", {
														value: column,
														children: column
													}, column))]
												})]
											})
										]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "mt-4 grid grid-cols-1 gap-4 md:grid-cols-2",
										children: [
											/* @__PURE__ */ jsxs("div", {
												className: "rounded-lg border border-border bg-background p-4",
												children: [/* @__PURE__ */ jsxs("div", {
													className: "flex items-center justify-between",
													children: [/* @__PURE__ */ jsx("label", {
														className: "text-sm font-medium",
														children: "SICR relative PD multiplier"
													}), /* @__PURE__ */ jsxs("span", {
														className: "text-sm font-semibold",
														children: [relativePdMultiplier.toFixed(1), "x"]
													})]
												}), /* @__PURE__ */ jsx("input", {
													type: "range",
													min: "1.1",
													max: "5",
													step: "0.1",
													value: relativePdMultiplier,
													onChange: (event) => setRelativePdMultiplier(Number(event.target.value)),
													className: "mt-3 w-full"
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "rounded-lg border border-border bg-background p-4",
												children: [/* @__PURE__ */ jsxs("div", {
													className: "flex items-center justify-between",
													children: [/* @__PURE__ */ jsx("label", {
														className: "text-sm font-medium",
														children: "SICR absolute PD increase"
													}), /* @__PURE__ */ jsxs("span", {
														className: "text-sm font-semibold",
														children: [absolutePdIncrease.toFixed(2), " pp"]
													})]
												}), /* @__PURE__ */ jsx("input", {
													type: "range",
													min: "0.01",
													max: "0.2",
													step: "0.01",
													value: absolutePdIncrease,
													onChange: (event) => setAbsolutePdIncrease(Number(event.target.value)),
													className: "mt-3 w-full"
												})]
											}),
											/* @__PURE__ */ jsxs("div", {
												className: "rounded-lg border border-border bg-background p-4 md:col-span-2",
												children: [/* @__PURE__ */ jsxs("div", {
													className: "flex items-center justify-between",
													children: [/* @__PURE__ */ jsx("label", {
														className: "text-sm font-medium",
														children: "DPD backstop threshold"
													}), /* @__PURE__ */ jsxs("span", {
														className: "text-sm font-semibold",
														children: [dpdBackstop, " days"]
													})]
												}), /* @__PURE__ */ jsx("input", {
													type: "range",
													min: "15",
													max: "60",
													step: "5",
													value: dpdBackstop,
													onChange: (event) => setDpdBackstop(Number(event.target.value)),
													className: "mt-3 w-full"
												})]
											})
										]
									})
								] })]
							}),
							/* @__PURE__ */ jsxs(Button, {
								className: "mt-6 gap-2",
								onClick: calculateEcl,
								disabled: loading,
								children: [loading ? /* @__PURE__ */ jsx(Loader2, { className: "h-4 w-4 animate-spin" }) : /* @__PURE__ */ jsx(Calculator, { className: "h-4 w-4" }), loading ? "Calculating…" : "Calculate ECL"]
							})
						]
					})
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: "Results"
						}),
						/* @__PURE__ */ jsx("p", {
							className: "mt-1 text-xs text-muted-foreground",
							children: "Portfolio metrics and stage-based charts returned by the backend."
						}),
						summary ? /* @__PURE__ */ jsxs(Fragment, { children: [/* @__PURE__ */ jsxs("div", {
							className: "mt-5 grid grid-cols-1 gap-3",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-4",
								children: [/* @__PURE__ */ jsx("div", {
									className: "text-xs uppercase tracking-[0.18em] text-muted-foreground",
									children: "Total ECL"
								}), /* @__PURE__ */ jsx("div", {
									className: "mt-1 text-2xl font-semibold",
									children: Number(summary.total_ecl ?? 0).toLocaleString()
								})]
							}), /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-4",
								children: [/* @__PURE__ */ jsx("div", {
									className: "text-xs uppercase tracking-[0.18em] text-muted-foreground",
									children: "Provision summary"
								}), /* @__PURE__ */ jsxs("div", {
									className: "mt-2 text-sm text-foreground/90",
									children: [
										"Coverage ",
										Number(summary.coverage_pct ?? 0).toFixed(2),
										"% · ",
										Number(summary.sicr_count ?? 0).toLocaleString(),
										" SICR loans"
									]
								})]
							})]
						}), /* @__PURE__ */ jsxs("div", {
							className: "mt-6 grid grid-cols-1 gap-3",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-4",
								children: [/* @__PURE__ */ jsx("div", {
									className: "text-sm font-semibold",
									children: "Stage exposures"
								}), /* @__PURE__ */ jsx("div", {
									className: "mt-3 h-44",
									children: /* @__PURE__ */ jsx(ChartContainer, {
										width: "100%",
										height: "100%",
										children: /* @__PURE__ */ jsxs(BarChart$1, {
											data: stageExposureData,
											children: [
												/* @__PURE__ */ jsx(CartesianGrid, {
													stroke: "oklch(0.92 0.005 240)",
													strokeDasharray: "3 3"
												}),
												/* @__PURE__ */ jsx(XAxis, {
													dataKey: "stage",
													tickLine: false,
													axisLine: false,
													fontSize: 11
												}),
												/* @__PURE__ */ jsx(YAxis, {
													tickLine: false,
													axisLine: false,
													fontSize: 11
												}),
												/* @__PURE__ */ jsx(Tooltip, { formatter: (value) => [`${value.toLocaleString()}`, "EAD"] }),
												/* @__PURE__ */ jsx(Bar, {
													dataKey: "value",
													fill: "oklch(0.76 0.18 130)",
													radius: [
														6,
														6,
														0,
														0
													]
												})
											]
										})
									})
								})]
							}), /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background p-4",
								children: [/* @__PURE__ */ jsx("div", {
									className: "text-sm font-semibold",
									children: "ECL distribution"
								}), /* @__PURE__ */ jsx("div", {
									className: "mt-3 h-44",
									children: /* @__PURE__ */ jsx(ChartContainer, {
										width: "100%",
										height: "100%",
										children: /* @__PURE__ */ jsxs(AreaChart, {
											data: eclDistributionData,
											children: [
												/* @__PURE__ */ jsx(CartesianGrid, {
													stroke: "oklch(0.92 0.005 240)",
													strokeDasharray: "3 3"
												}),
												/* @__PURE__ */ jsx(XAxis, {
													dataKey: "stage",
													tickLine: false,
													axisLine: false,
													fontSize: 11
												}),
												/* @__PURE__ */ jsx(YAxis, {
													tickLine: false,
													axisLine: false,
													fontSize: 11
												}),
												/* @__PURE__ */ jsx(Tooltip, { formatter: (value) => [`${value.toLocaleString()}`, "ECL"] }),
												/* @__PURE__ */ jsx(Area, {
													type: "monotone",
													dataKey: "value",
													stroke: "oklch(0.6 0.22 27)",
													fill: "oklch(0.6 0.22 27)",
													fillOpacity: .24
												})
											]
										})
									})
								})]
							})]
						})] }) : /* @__PURE__ */ jsx("div", {
							className: "mt-6 rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground",
							children: "Run the calculation to populate the live ECL portfolio output."
						}),
						summary ? /* @__PURE__ */ jsxs("div", {
							className: "mt-6 grid grid-cols-2 gap-3",
							children: [
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-[0.18em] text-muted-foreground",
										children: "Total EAD"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold",
										children: Number(summary.total_ead ?? 0).toLocaleString()
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-[0.18em] text-muted-foreground",
										children: "Avg. PD"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold",
										children: Number(summary.avg_pd_12m ?? 0).toFixed(3)
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-[0.18em] text-muted-foreground",
										children: "Stage 2 / 3"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold",
										children: Number(summary.sicr_count ?? 0).toLocaleString()
									})]
								}),
								/* @__PURE__ */ jsxs("div", {
									className: "rounded-lg border border-border bg-background p-3",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-[11px] uppercase tracking-[0.18em] text-muted-foreground",
										children: "Loans"
									}), /* @__PURE__ */ jsx("div", {
										className: "mt-1 text-lg font-semibold",
										children: Number(summary.loans ?? 0).toLocaleString()
									})]
								})
							]
						}) : null,
						sampleRows.length > 0 ? /* @__PURE__ */ jsxs("div", {
							className: "mt-6 space-y-3",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center justify-between",
								children: [/* @__PURE__ */ jsx("h3", {
									className: "text-sm font-semibold",
									children: "Top loans from backend"
								}), /* @__PURE__ */ jsxs(Button, {
									variant: "outline",
									className: "gap-2",
									onClick: handleDownload,
									children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), "Download CSV"]
								})]
							}), /* @__PURE__ */ jsx("div", {
								className: "max-h-72 overflow-auto rounded-lg border border-border bg-background",
								children: /* @__PURE__ */ jsxs("table", {
									className: "min-w-full text-left text-xs",
									children: [/* @__PURE__ */ jsx("thead", {
										className: "bg-muted/40 text-muted-foreground",
										children: /* @__PURE__ */ jsx("tr", { children: (columns.length ? columns : Object.keys(sampleRows[0] ?? {})).slice(0, 8).map((column) => /* @__PURE__ */ jsx("th", {
											className: "px-2 py-2 font-medium",
											children: column
										}, column)) })
									}), /* @__PURE__ */ jsx("tbody", { children: sampleRows.slice(0, 8).map((row, index) => /* @__PURE__ */ jsx("tr", {
										className: "border-b border-border/60 last:border-b-0",
										children: (columns.length ? columns : Object.keys(sampleRows[0] ?? {})).slice(0, 8).map((column) => /* @__PURE__ */ jsx("td", {
											className: "whitespace-nowrap px-2 py-2 text-foreground/90",
											children: row?.[column] === null || row?.[column] === void 0 ? "—" : String(row[column])
										}, `${column}-${index}`))
									}, `${row?.id ?? index}`)) })]
								})
							})]
						}) : null,
						/* @__PURE__ */ jsxs("div", {
							className: "mt-6 flex gap-3",
							children: [/* @__PURE__ */ jsxs(Button, {
								variant: "outline",
								onClick: () => navigate({ to: "/explainability" }),
								className: "gap-2",
								children: [/* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }), "Back to Explainability"]
							}), /* @__PURE__ */ jsxs(Button, {
								onClick: () => navigate({ to: "/" }),
								className: "ml-auto gap-2",
								children: ["Exit to Workspace", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
							})]
						})
					]
				})]
			})
		]
	});
}
//#endregion
export { EclProvisions as component };
