import { useState } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { Activity, BarChart3, Bell, BookOpen, Boxes, ChevronsLeft, ChevronsRight, ClipboardCheck, Cpu, Database, FileText, GitCompareArrows, Home, Layers, LayoutDashboard, LineChart, MessageSquare, Search, Settings, ShieldCheck, Sparkles, UploadCloud, Wand2 } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
//#region src/lib/utils.ts
function cn(...inputs) {
	return twMerge(clsx(inputs));
}
//#endregion
//#region src/components/app-shell.tsx
var developmentNav = [
	{
		to: "/development",
		label: "Overview",
		icon: LayoutDashboard,
		exact: true
	},
	{
		to: "/data-upload",
		label: "Data Upload",
		icon: UploadCloud
	},
	{
		to: "/profiling",
		label: "Data Profiling",
		icon: Database
	},
	{
		to: "/preprocessing",
		label: "Preprocessing",
		icon: Wand2
	},
	{
		to: "/features",
		label: "Feature Engineering",
		icon: Layers
	},
	{
		to: "/models",
		label: "Model Selection",
		icon: Boxes
	},
	{
		to: "/training",
		label: "Model Training",
		icon: Cpu
	},
	{
		to: "/evaluation",
		label: "Model Evaluation",
		icon: LineChart
	},
	{
		to: "/explainability",
		label: "Explainability",
		icon: Sparkles
	},
	{
		to: "/assistant",
		label: "AI Assistant",
		icon: MessageSquare
	},
	{
		to: "/settings",
		label: "Settings",
		icon: Settings
	}
];
var validationNav = [
	{
		to: "/validation",
		label: "Overview",
		icon: LayoutDashboard,
		exact: true
	},
	{
		to: "/validation/intake",
		label: "Intake & Intended Use",
		icon: FileText
	},
	{
		to: "/validation/data-quality",
		label: "Data Quality",
		icon: Database
	},
	{
		to: "/validation/conceptual",
		label: "Conceptual Soundness",
		icon: BookOpen
	},
	{
		to: "/validation/challenger",
		label: "Challenger Analysis",
		icon: GitCompareArrows
	},
	{
		to: "/validation/performance",
		label: "Performance Validation",
		icon: BarChart3
	},
	{
		to: "/validation/stress",
		label: "Stress & Backtesting",
		icon: Activity
	},
	{
		to: "/validation/regulatory",
		label: "Regulatory Compliance",
		icon: ShieldCheck
	},
	{
		to: "/validation/findings",
		label: "Findings & Report",
		icon: ClipboardCheck
	}
];
var developmentPaths = developmentNav.map((n) => n.to);
function resolveWorkspace(pathname) {
	if (pathname === "/") return "landing";
	if (pathname.startsWith("/validation")) return "validation";
	if (developmentPaths.some((p) => pathname === p || pathname.startsWith(p + "/"))) return "development";
	return "landing";
}
function AppShell({ children }) {
	const [collapsed, setCollapsed] = useState(false);
	const pathname = useRouterState({ select: (s) => s.location.pathname });
	const workspace = resolveWorkspace(pathname);
	const isLanding = workspace === "landing";
	const nav = workspace === "validation" ? validationNav : developmentNav;
	const workspaceLabel = workspace === "validation" ? "Model Validation" : workspace === "development" ? "Model Development" : "Workspace";
	return /* @__PURE__ */ jsxs("div", {
		className: "flex min-h-screen w-full bg-background text-foreground",
		children: [!isLanding && /* @__PURE__ */ jsxs("aside", {
			className: cn("sticky top-0 z-30 hidden h-screen shrink-0 flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-300 ease-out md:flex", collapsed ? "w-[76px]" : "w-[264px]"),
			children: [
				/* @__PURE__ */ jsxs("div", {
					className: "flex h-16 items-center gap-3 border-b border-sidebar-border px-4",
					children: [/* @__PURE__ */ jsx("div", {
						className: "flex h-9 w-9 items-center justify-center rounded-lg gradient-primary shadow-elegant",
						children: /* @__PURE__ */ jsx(ShieldCheck, { className: "h-5 w-5 text-primary-foreground" })
					}), !collapsed && /* @__PURE__ */ jsxs("div", {
						className: "flex flex-col leading-tight",
						children: [/* @__PURE__ */ jsx("span", {
							className: "text-sm font-semibold tracking-tight",
							children: "Aegis Credit"
						}), /* @__PURE__ */ jsx("span", {
							className: "text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/60",
							children: workspaceLabel
						})]
					})]
				}),
				!collapsed && /* @__PURE__ */ jsxs("div", {
					className: "px-3 pt-3",
					children: [/* @__PURE__ */ jsxs(Link, {
						to: "/",
						className: "flex items-center gap-2 rounded-lg border border-sidebar-border/60 bg-sidebar-accent/30 px-3 py-2 text-xs font-medium text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
						children: [/* @__PURE__ */ jsx(Home, { className: "h-3.5 w-3.5" }), "Switch workspace"]
					}), /* @__PURE__ */ jsxs("div", {
						className: "mt-3 grid grid-cols-2 gap-1.5",
						children: [/* @__PURE__ */ jsx(Link, {
							to: "/development",
							className: cn("rounded-md px-2 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wider transition-colors", workspace === "development" ? "bg-primary text-primary-foreground" : "bg-sidebar-accent/40 text-sidebar-foreground/70 hover:bg-sidebar-accent"),
							children: "Develop"
						}), /* @__PURE__ */ jsx(Link, {
							to: "/validation",
							className: cn("rounded-md px-2 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wider transition-colors", workspace === "validation" ? "bg-primary text-primary-foreground" : "bg-sidebar-accent/40 text-sidebar-foreground/70 hover:bg-sidebar-accent"),
							children: "Validate"
						})]
					})]
				}),
				/* @__PURE__ */ jsx("nav", {
					className: "flex-1 overflow-y-auto px-3 py-4",
					children: /* @__PURE__ */ jsx("ul", {
						className: "space-y-1",
						children: nav.map((item) => {
							const Icon = item.icon;
							const active = item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(item.to + "/");
							return /* @__PURE__ */ jsx("li", { children: /* @__PURE__ */ jsxs(Link, {
								to: item.to,
								className: cn("group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors", active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"),
								children: [
									/* @__PURE__ */ jsx(Icon, { className: cn("h-[18px] w-[18px] shrink-0", active ? "text-primary" : "text-sidebar-foreground/60 group-hover:text-primary") }),
									!collapsed && /* @__PURE__ */ jsx("span", {
										className: "truncate",
										children: item.label
									}),
									!collapsed && active && /* @__PURE__ */ jsx("span", { className: "ml-auto h-1.5 w-1.5 rounded-full bg-primary" })
								]
							}) }, item.to);
						})
					})
				}),
				/* @__PURE__ */ jsx("div", {
					className: "border-t border-sidebar-border p-3",
					children: /* @__PURE__ */ jsxs("button", {
						onClick: () => setCollapsed((c) => !c),
						className: "flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
						children: [collapsed ? /* @__PURE__ */ jsx(ChevronsRight, { className: "h-4 w-4" }) : /* @__PURE__ */ jsx(ChevronsLeft, { className: "h-4 w-4" }), !collapsed && /* @__PURE__ */ jsx("span", { children: "Collapse" })]
					})
				})
			]
		}), /* @__PURE__ */ jsxs("div", {
			className: "flex min-w-0 flex-1 flex-col",
			children: [/* @__PURE__ */ jsxs("header", {
				className: "sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-border/70 bg-background/80 px-4 backdrop-blur-md md:px-8",
				children: [
					isLanding ? /* @__PURE__ */ jsxs(Link, {
						to: "/",
						className: "flex items-center gap-3",
						children: [/* @__PURE__ */ jsx("div", {
							className: "flex h-9 w-9 items-center justify-center rounded-lg gradient-primary shadow-elegant",
							children: /* @__PURE__ */ jsx(ShieldCheck, { className: "h-5 w-5 text-primary-foreground" })
						}), /* @__PURE__ */ jsxs("div", {
							className: "leading-tight",
							children: [/* @__PURE__ */ jsx("div", {
								className: "text-sm font-semibold tracking-tight",
								children: "Aegis Credit"
							}), /* @__PURE__ */ jsx("div", {
								className: "text-[10px] uppercase tracking-[0.18em] text-muted-foreground",
								children: "AI Model Platform"
							})]
						})]
					}) : /* @__PURE__ */ jsx("div", {
						className: "hidden flex-1 items-center gap-2 md:flex",
						children: /* @__PURE__ */ jsxs("div", {
							className: "relative w-full max-w-md",
							children: [/* @__PURE__ */ jsx(Search, { className: "pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" }), /* @__PURE__ */ jsx("input", {
								placeholder: "Search models, rules, datasets…",
								className: "h-10 w-full rounded-lg border border-input bg-card pl-9 pr-3 text-sm outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/60 focus:bg-card"
							})]
						})
					}),
					!isLanding && /* @__PURE__ */ jsx("div", {
						className: "md:hidden text-sm font-semibold",
						children: "Aegis Credit"
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "ml-auto flex items-center gap-2",
						children: [
							isLanding && /* @__PURE__ */ jsx(Link, {
								to: "/development",
								className: "hidden items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:border-primary/40 sm:inline-flex",
								children: "Develop"
							}),
							isLanding && /* @__PURE__ */ jsx(Link, {
								to: "/validation",
								className: "hidden items-center gap-1.5 rounded-lg gradient-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow-elegant sm:inline-flex",
								children: "Validate"
							}),
							!isLanding && /* @__PURE__ */ jsxs("div", {
								className: "hidden items-center gap-2 rounded-full bg-primary-soft px-3 py-1.5 text-xs font-medium text-foreground sm:flex",
								children: [/* @__PURE__ */ jsx("span", { className: "h-2 w-2 rounded-full bg-primary animate-pulse" }), "Production · Tier 2"]
							}),
							/* @__PURE__ */ jsxs("button", {
								className: "relative inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground",
								children: [/* @__PURE__ */ jsx(Bell, { className: "h-4 w-4" }), /* @__PURE__ */ jsx("span", { className: "absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-destructive" })]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-2 pr-3",
								children: [/* @__PURE__ */ jsx("div", {
									className: "flex h-7 w-7 items-center justify-center rounded-md gradient-primary text-[11px] font-semibold text-primary-foreground",
									children: "AK"
								}), /* @__PURE__ */ jsxs("div", {
									className: "hidden text-left leading-tight sm:block",
									children: [/* @__PURE__ */ jsx("div", {
										className: "text-xs font-semibold",
										children: "A. Khurana"
									}), /* @__PURE__ */ jsx("div", {
										className: "text-[10px] text-muted-foreground",
										children: "Risk Validator"
									})]
								})]
							})
						]
					})
				]
			}), /* @__PURE__ */ jsx("main", {
				className: "flex-1 px-4 py-6 md:px-8 md:py-8",
				children
			})]
		})]
	});
}
function PageHeader({ title, description, actions }) {
	return /* @__PURE__ */ jsxs("div", {
		className: "mb-6 flex flex-col gap-3 md:mb-8 md:flex-row md:items-end md:justify-between",
		children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h1", {
			className: "text-2xl font-semibold tracking-tight md:text-3xl",
			children: title
		}), description && /* @__PURE__ */ jsx("p", {
			className: "mt-1.5 max-w-2xl text-sm text-muted-foreground",
			children: description
		})] }), actions && /* @__PURE__ */ jsx("div", {
			className: "flex flex-wrap items-center gap-2",
			children: actions
		})]
	});
}
//#endregion
export { PageHeader as n, cn as r, AppShell as t };
