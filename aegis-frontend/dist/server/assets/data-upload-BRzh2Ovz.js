import { n as useDataset } from "./app-context-DV-UQQQM.js";
import { r as formUpload } from "./api-CPpoZWeE.js";
import { t as Button } from "./button-MHHI04mG.js";
import { useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { AlertCircle, ArrowRight, CheckCircle2, Cloud, Database, FileSpreadsheet, Folder, Globe2, HardDrive, Info, Sparkles, Table2, Upload } from "lucide-react";
//#region src/routes/data-upload.tsx?tsr-split=component
function DataUpload() {
	const [dataSourceType, setDataSourceType] = useState("upload");
	const [syntheticSamples, setSyntheticSamples] = useState(2e3);
	const [uploadSummary, setUploadSummary] = useState(null);
	const { setUploadResult, profile } = useDataset();
	const navigate = useNavigate();
	const inputRef = useRef(null);
	const dataSourceOptions = [
		{
			value: "upload",
			label: "Upload File (CSV / XLSX)",
			icon: Upload
		},
		{
			value: "database",
			label: "Database Connection",
			icon: Database
		},
		{
			value: "api",
			label: "API Endpoint",
			icon: Globe2
		},
		{
			value: "cloud",
			label: "Cloud Storage (S3 / Azure Blob)",
			icon: Cloud
		},
		{
			value: "sftp",
			label: "SFTP / File Server",
			icon: HardDrive
		}
	];
	const applyUploadResult = (uploadedFile, response) => {
		const datasetName = response?.dataset_name ?? uploadedFile?.name ?? "Synthetic Credit Dataset.csv";
		setUploadResult(uploadedFile ?? (typeof response?.csv_text === "string" ? new File([response.csv_text], datasetName.endsWith(".csv") ? datasetName : `${datasetName}.csv`, { type: "text/csv" }) : null), response);
		const rows = Array.isArray(response?.shape) ? Number(response.shape[0] ?? 0) : 0;
		const cols = Array.isArray(response?.shape) ? Number(response.shape[1] ?? 0) : 0;
		setUploadSummary({
			kind: response?.source_type === "synthetic" ? "synthetic" : "file",
			name: datasetName,
			rows,
			cols
		});
	};
	const uploadFile = async (f) => {
		if (!f) return;
		try {
			const form = new FormData();
			form.append("file", f);
			console.log("DataUpload: sending POST to /data/upload", {
				filename: f.name,
				size: f.size
			});
			const profile = await formUpload("/data/upload", form);
			console.log("DataUpload: received profile", profile);
			applyUploadResult(f, profile);
		} catch (err) {
			console.error("DataUpload: upload failed", err);
		}
	};
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-6",
		children: [
			/* @__PURE__ */ jsx("div", {
				className: "rounded-xl border-l-4 border-primary bg-card px-4 py-3 shadow-elegant",
				children: /* @__PURE__ */ jsxs("div", {
					className: "flex items-center gap-3",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
						children: /* @__PURE__ */ jsx(Folder, { className: "h-5 w-5 text-muted-foreground" })
					}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
						className: "text-lg font-semibold tracking-tight",
						children: "Step 1 — Data Upload"
					}), /* @__PURE__ */ jsx("p", {
						className: "mt-1 text-sm text-muted-foreground",
						children: "Upload a CSV or Excel file, or use the built-in synthetic credit dataset"
					})] })]
				})
			}),
			/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h4", {
				className: "text-sm font-semibold text-foreground",
				children: "Data Source"
			}), /* @__PURE__ */ jsx("div", {
				className: "mt-4 space-y-3",
				children: dataSourceOptions.map((option) => {
					const Icon = option.icon;
					return /* @__PURE__ */ jsxs("label", {
						className: "flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-sm shadow-elegant",
						children: [
							/* @__PURE__ */ jsx("input", {
								type: "radio",
								name: "data-source-type",
								value: option.value,
								checked: dataSourceType === option.value,
								onChange: () => setDataSourceType(option.value),
								className: "h-4 w-4 accent-primary"
							}),
							/* @__PURE__ */ jsx("div", {
								className: "flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background/80",
								children: /* @__PURE__ */ jsx(Icon, { className: "h-5 w-5 text-muted-foreground" })
							}),
							/* @__PURE__ */ jsx("span", {
								className: "font-medium text-foreground",
								children: option.label
							})
						]
					}, option.value);
				})
			})] }),
			dataSourceType === "upload" ? /* @__PURE__ */ jsxs("div", {
				className: "grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsx("input", {
							ref: inputRef,
							type: "file",
							accept: ".csv,.xlsx",
							className: "hidden",
							onChange: (e) => uploadFile(e.target.files?.[0] ?? null)
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "flex items-start gap-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
								children: /* @__PURE__ */ jsx(FileSpreadsheet, { className: "h-5 w-5 text-muted-foreground" })
							}), /* @__PURE__ */ jsxs("div", {
								className: "space-y-2",
								children: [/* @__PURE__ */ jsx("label", {
									className: "block text-sm font-medium text-foreground",
									children: "Upload your dataset (CSV / XLSX)"
								}), /* @__PURE__ */ jsx("p", {
									className: "text-xs text-muted-foreground",
									children: "The system adapts automatically to any structured dataset schema."
								})]
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "mt-4 flex flex-wrap gap-3",
							children: [/* @__PURE__ */ jsx("button", {
								type: "button",
								onClick: () => inputRef.current?.click(),
								className: "inline-flex items-center justify-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:border-primary/40 hover:bg-primary-soft",
								children: "Browse files"
							}), /* @__PURE__ */ jsx("span", {
								className: "inline-flex items-center rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted-foreground",
								children: "CSV / XLSX"
							})]
						})
					]
				}), /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-3",
							children: [/* @__PURE__ */ jsx("div", {
								className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
								children: /* @__PURE__ */ jsx(Sparkles, { className: "h-5 w-5 text-muted-foreground" })
							}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold",
								children: "Synthetic dataset"
							}), /* @__PURE__ */ jsx("p", {
								className: "text-xs text-muted-foreground",
								children: "No data? Generate a realistic loan tape."
							})] })]
						}),
						/* @__PURE__ */ jsx("button", {
							type: "button",
							onClick: async () => {
								try {
									const form = new FormData();
									form.append("synthetic_samples", String(syntheticSamples));
									console.log("DataUpload: requesting synthetic dataset generation POST /data/upload", { synthetic_samples: syntheticSamples });
									const result = await formUpload("/data/upload", form);
									console.log("DataUpload: synthetic profile received", result);
									applyUploadResult(null, result);
								} catch (err) {
									console.error("DataUpload: synthetic generation failed", err);
								}
							},
							className: "mt-5 w-full rounded-lg border border-primary/30 bg-primary-soft px-3 py-2 text-sm font-medium text-foreground hover:bg-primary/20",
							children: "Use Synthetic Dataset"
						}),
						/* @__PURE__ */ jsxs("label", {
							className: "mt-4 block text-xs text-muted-foreground",
							children: ["Synthetic samples", /* @__PURE__ */ jsx("input", {
								type: "number",
								min: 500,
								max: 5e4,
								step: 500,
								value: syntheticSamples,
								onChange: (e) => setSyntheticSamples(Number(e.target.value) || 2e3),
								className: "mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary/60"
							})]
						})
					]
				})]
			}) : dataSourceType === "database" ? /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-start gap-3",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
						children: /* @__PURE__ */ jsx(Database, { className: "h-5 w-5 text-muted-foreground" })
					}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
						className: "font-semibold text-foreground",
						children: "Database connection setup"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-sm text-muted-foreground",
						children: "Database connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow — connection logic will be added once the target database and credentials are confirmed."
					})] })]
				}), /* @__PURE__ */ jsx("button", {
					type: "button",
					disabled: true,
					className: "mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground",
					children: "Connect & Pull Data"
				})]
			}) : dataSourceType === "api" ? /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-start gap-3",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
						children: /* @__PURE__ */ jsx(Globe2, { className: "h-5 w-5 text-muted-foreground" })
					}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
						className: "text-sm font-semibold text-foreground",
						children: "API connection setup"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-sm text-muted-foreground",
						children: "API connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow."
					})] })]
				}), /* @__PURE__ */ jsx("button", {
					type: "button",
					disabled: true,
					className: "mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground",
					children: "Fetch Data"
				})]
			}) : dataSourceType === "cloud" ? /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-start gap-3",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
						children: /* @__PURE__ */ jsx(Cloud, { className: "h-5 w-5 text-muted-foreground" })
					}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
						className: "text-sm font-semibold text-foreground",
						children: "Cloud storage connection setup"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-sm text-muted-foreground",
						children: "Cloud storage connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow."
					})] })]
				}), /* @__PURE__ */ jsx("button", {
					type: "button",
					disabled: true,
					className: "mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground",
					children: "Load from Cloud"
				})]
			}) : /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "flex items-start gap-3",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background/80",
						children: /* @__PURE__ */ jsx(HardDrive, { className: "h-5 w-5 text-muted-foreground" })
					}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
						className: "text-sm font-semibold text-foreground",
						children: "SFTP / File Server connection setup"
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-2 text-sm text-muted-foreground",
						children: "SFTP connectivity is not yet implemented in this POC. This UI demonstrates the intended workflow — useful for scheduled exports landing in a fixed location."
					})] })]
				}), /* @__PURE__ */ jsx("button", {
					type: "button",
					disabled: true,
					className: "mt-4 w-full rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-muted-foreground",
					children: "Pull from Server"
				})]
			}),
			uploadSummary ? /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800",
				children: [/* @__PURE__ */ jsxs("span", {
					className: "inline-flex items-center gap-2 font-semibold",
					children: [/* @__PURE__ */ jsx(CheckCircle2, { className: "h-5 w-5" }), uploadSummary.kind === "synthetic" ? "Generated synthetic dataset" : `Loaded ${uploadSummary.name}`]
				}), /* @__PURE__ */ jsxs("span", {
					className: "ml-2",
					children: [
						"— ",
						uploadSummary.rows.toLocaleString(),
						" rows × ",
						uploadSummary.cols.toLocaleString(),
						" columns"
					]
				})]
			}) : null,
			profile ? /* @__PURE__ */ jsxs(Fragment, { children: [
				/* @__PURE__ */ jsxs("div", {
					className: "grid grid-cols-2 gap-3 md:grid-cols-4",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground",
								children: [/* @__PURE__ */ jsx(Table2, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Rows" })]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-2 text-2xl font-semibold tabular-nums",
								children: profile.shape?.[0]?.toLocaleString() ?? "—"
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground",
								children: [/* @__PURE__ */ jsx(Table2, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Columns" })]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-2 text-2xl font-semibold tabular-nums",
								children: profile.shape?.[1]?.toLocaleString() ?? "—"
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground",
								children: [/* @__PURE__ */ jsx(AlertCircle, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Missing Values" })]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-2 text-2xl font-semibold tabular-nums",
								children: profile.missing_cells?.toLocaleString() ?? "—"
							})]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "rounded-xl border border-border bg-card p-4 shadow-elegant",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground",
								children: [/* @__PURE__ */ jsx(Table2, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { children: "Duplicates" })]
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-2 text-2xl font-semibold tabular-nums",
								children: profile.duplicate_rows?.toLocaleString() ?? "—"
							})]
						})
					]
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-2",
						children: [/* @__PURE__ */ jsx(Table2, { className: "h-5 w-5 text-muted-foreground" }), /* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Dataset Preview"
						})]
					}), /* @__PURE__ */ jsx("div", {
						className: "mt-4 overflow-x-auto",
						children: /* @__PURE__ */ jsxs("table", {
							className: "min-w-full text-left text-sm",
							children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", {
								className: "border-b border-border text-xs uppercase tracking-wider text-muted-foreground",
								children: (profile.columns ?? []).map((column) => /* @__PURE__ */ jsx("th", {
									className: "px-2 py-2",
									children: column
								}, column))
							}) }), /* @__PURE__ */ jsx("tbody", { children: (profile.data_preview ?? []).map((row, rowIndex) => /* @__PURE__ */ jsx("tr", {
								className: rowIndex % 2 === 0 ? "bg-background" : "bg-card",
								children: (profile.columns ?? []).map((column) => /* @__PURE__ */ jsx("td", {
									className: "whitespace-nowrap px-2 py-2 text-xs text-foreground/90",
									children: row[column] ?? ""
								}, `${rowIndex}-${column}`))
							}, rowIndex)) })]
						})
					})]
				}),
				/* @__PURE__ */ jsx("div", {
					className: "flex justify-end gap-3 pt-4",
					children: /* @__PURE__ */ jsxs(Button, {
						onClick: () => navigate({ to: "/profiling" }),
						className: "gap-2",
						children: ["Proceed to Data Profiling", /* @__PURE__ */ jsx(ArrowRight, { className: "h-4 w-4" })]
					})
				})
			] }) : /* @__PURE__ */ jsxs("div", {
				className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-2",
						children: [/* @__PURE__ */ jsx(Info, { className: "h-5 w-5 text-muted-foreground" }), /* @__PURE__ */ jsx("h4", {
							className: "text-sm font-semibold",
							children: "Welcome to CreditRisk ML POC"
						})]
					}),
					/* @__PURE__ */ jsxs("p", {
						className: "mt-2 text-sm text-muted-foreground",
						children: [
							"This platform intelligently adapts to ",
							/* @__PURE__ */ jsx("strong", { children: "any structured dataset" }),
							" — no hardcoded columns required."
						]
					}),
					/* @__PURE__ */ jsxs("ul", {
						className: "mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground",
						children: [/* @__PURE__ */ jsx("li", { children: "Upload your own CSV/XLSX file, or" }), /* @__PURE__ */ jsxs("li", { children: [
							"Click ",
							/* @__PURE__ */ jsx("strong", { children: "Use Synthetic Dataset" }),
							" to explore with demo data"
						] })]
					})
				]
			})
		]
	});
}
//#endregion
export { DataUpload as component };
