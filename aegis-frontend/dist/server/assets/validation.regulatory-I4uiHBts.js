import { n as PageHeader, r as cn } from "./app-shell-DXEPQAWO.js";
import { a as regulatoryChecks } from "./mock-data-BOXuVqnR.js";
import { useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { AlertTriangle, CheckCircle2, ChevronDown, Download, XCircle } from "lucide-react";
//#region src/routes/validation.regulatory.tsx?tsr-split=component
var badge = {
	PASS: {
		Icon: CheckCircle2,
		cls: "bg-primary-soft text-foreground border-primary/30"
	},
	WARNING: {
		Icon: AlertTriangle,
		cls: "bg-warning/20 text-warning-foreground border-warning/40"
	},
	FAIL: {
		Icon: XCircle,
		cls: "bg-destructive/10 text-destructive border-destructive/30"
	}
};
var sevDot = {
	High: "bg-destructive",
	Medium: "bg-warning",
	Low: "bg-primary"
};
function Regulatory() {
	const [open, setOpen] = useState("SS123-4.1");
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Regulatory Compliance",
			description: "Automated review against IFRS 9, IFRS 7, and PRA SS1/23 with severity-weighted scoring and remediation.",
			actions: /* @__PURE__ */ jsxs("button", {
				className: "inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:border-primary/40",
				children: [/* @__PURE__ */ jsx(Download, { className: "h-4 w-4" }), " Compliance report"]
			})
		}), /* @__PURE__ */ jsxs("div", {
			className: "grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]",
			children: [/* @__PURE__ */ jsx("div", {
				className: "space-y-6",
				children: regulatoryChecks.map((group) => /* @__PURE__ */ jsxs("div", {
					className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "mb-4 flex items-center justify-between",
						children: [/* @__PURE__ */ jsx("h2", {
							className: "text-base font-semibold",
							children: group.framework
						}), /* @__PURE__ */ jsxs("span", {
							className: "text-xs text-muted-foreground",
							children: [group.rules.length, " rules"]
						})]
					}), /* @__PURE__ */ jsx("div", {
						className: "space-y-2",
						children: group.rules.map((r) => {
							const B = badge[r.status];
							const isOpen = open === r.id;
							const canOpen = r.status !== "PASS";
							return /* @__PURE__ */ jsxs("div", {
								className: "rounded-lg border border-border bg-background",
								children: [/* @__PURE__ */ jsxs("button", {
									onClick: () => canOpen && setOpen(isOpen ? null : r.id),
									className: "flex w-full items-center gap-3 px-4 py-3 text-left",
									children: [
										/* @__PURE__ */ jsx("span", { className: cn("h-2 w-2 rounded-full", sevDot[r.severity]) }),
										/* @__PURE__ */ jsx("span", {
											className: "text-xs font-mono text-muted-foreground",
											children: r.id
										}),
										/* @__PURE__ */ jsx("span", {
											className: "flex-1 text-sm font-medium",
											children: r.title
										}),
										/* @__PURE__ */ jsx("span", {
											className: "hidden text-[10px] uppercase tracking-wider text-muted-foreground sm:inline",
											children: r.severity
										}),
										/* @__PURE__ */ jsxs("span", {
											className: cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold", B.cls),
											children: [/* @__PURE__ */ jsx(B.Icon, { className: "h-3.5 w-3.5" }), r.status]
										}),
										canOpen && /* @__PURE__ */ jsx(ChevronDown, { className: cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180") })
									]
								}), isOpen && canOpen && "detail" in r && /* @__PURE__ */ jsxs("div", {
									className: "border-t border-border px-4 py-3 text-sm",
									children: [/* @__PURE__ */ jsx("p", {
										className: "text-foreground/80",
										children: r.detail
									}), /* @__PURE__ */ jsxs("div", {
										className: "mt-3 rounded-md border border-primary/30 bg-primary-soft p-3 text-xs",
										children: [/* @__PURE__ */ jsx("div", {
											className: "font-semibold uppercase tracking-wider text-foreground/70",
											children: "Suggested remediation"
										}), /* @__PURE__ */ jsx("div", {
											className: "mt-1 text-foreground/90",
											children: r.remediation
										})]
									})]
								})]
							}, r.id);
						})
					})]
				}, group.framework))
			}), /* @__PURE__ */ jsxs("aside", {
				className: "space-y-4",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "Compliance score"
						}), /* @__PURE__ */ jsxs("div", {
							className: "mt-4 flex flex-col items-center",
							children: [/* @__PURE__ */ jsx("div", {
								className: "relative h-40 w-40 rounded-full",
								style: { background: "conic-gradient(oklch(0.76 0.18 130) 0 332deg, oklch(0.92 0.005 240) 332deg 360deg)" },
								children: /* @__PURE__ */ jsxs("div", {
									className: "absolute inset-2 flex flex-col items-center justify-center rounded-full bg-card",
									children: [/* @__PURE__ */ jsx("span", {
										className: "text-4xl font-semibold tracking-tight",
										children: "92"
									}), /* @__PURE__ */ jsx("span", {
										className: "text-[10px] uppercase tracking-wider text-muted-foreground",
										children: "out of 100"
									})]
								})
							}), /* @__PURE__ */ jsx("div", {
								className: "mt-4 text-center text-xs text-muted-foreground",
								children: "Down 2 pts from previous cycle due to challenger benchmark gap."
							})]
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-card p-6 shadow-elegant",
						children: [/* @__PURE__ */ jsx("h3", {
							className: "text-sm font-semibold",
							children: "RAG summary"
						}), /* @__PURE__ */ jsxs("ul", {
							className: "mt-4 space-y-2 text-sm",
							children: [
								/* @__PURE__ */ jsxs("li", {
									className: "flex items-center justify-between",
									children: [/* @__PURE__ */ jsxs("span", {
										className: "flex items-center gap-2",
										children: [/* @__PURE__ */ jsx("span", { className: "h-2 w-2 rounded-full bg-destructive" }), " Red"]
									}), /* @__PURE__ */ jsx("span", {
										className: "font-semibold",
										children: "1"
									})]
								}),
								/* @__PURE__ */ jsxs("li", {
									className: "flex items-center justify-between",
									children: [/* @__PURE__ */ jsxs("span", {
										className: "flex items-center gap-2",
										children: [/* @__PURE__ */ jsx("span", { className: "h-2 w-2 rounded-full bg-warning" }), " Amber"]
									}), /* @__PURE__ */ jsx("span", {
										className: "font-semibold",
										children: "2"
									})]
								}),
								/* @__PURE__ */ jsxs("li", {
									className: "flex items-center justify-between",
									children: [/* @__PURE__ */ jsxs("span", {
										className: "flex items-center gap-2",
										children: [/* @__PURE__ */ jsx("span", { className: "h-2 w-2 rounded-full bg-primary" }), " Green"]
									}), /* @__PURE__ */ jsx("span", {
										className: "font-semibold",
										children: "8"
									})]
								})
							]
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "rounded-xl border border-border bg-sidebar p-6 text-sidebar-foreground shadow-elegant",
						children: [
							/* @__PURE__ */ jsx("h3", {
								className: "text-sm font-semibold",
								children: "Model risk tier"
							}),
							/* @__PURE__ */ jsx("div", {
								className: "mt-3 text-3xl font-semibold",
								children: "Tier 2"
							}),
							/* @__PURE__ */ jsx("p", {
								className: "mt-1 text-xs text-sidebar-foreground/70",
								children: "Material — quarterly independent validation required."
							})
						]
					})
				]
			})]
		})]
	});
}
//#endregion
export { Regulatory as component };
