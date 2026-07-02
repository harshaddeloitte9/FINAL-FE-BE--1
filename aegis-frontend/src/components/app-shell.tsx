import { Link, useRouterState } from "@tanstack/react-router";
import {
  UploadCloud,
  Database,
  ShieldCheck,
  Wand2,
  Layers,
  Boxes,
  Cpu,
  LineChart,
  Sparkles,
  MessageSquare,
  Settings,
  Bell,
  Search,
  ChevronsLeft,
  ChevronsRight,
  Home,
  FileText,
  BookOpen,
  GitCompareArrows,
  BarChart3,
  Activity,
  ClipboardCheck,
  Calculator,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type NavItem = { to: string; label: string; icon: typeof Home; exact?: boolean };
type ModelTab = { to: string; label: string; key: "pd" | "lgd" | "ead" };

const modelTabs: ModelTab[] = [
  { to: "/pd", label: "PD Model", key: "pd" },
  { to: "/lgd", label: "LGD Model", key: "lgd" },
  { to: "/ead", label: "EAD Model", key: "ead" },
];

const developmentNav: NavItem[] = [
  { to: "/data-upload", label: "Data Upload", icon: UploadCloud },
  { to: "/profiling", label: "Data Profiling", icon: Database },
  { to: "/preprocessing", label: "Preprocessing", icon: Wand2 },
  { to: "/features", label: "Feature Engineering", icon: Layers },
  { to: "/models", label: "Model Selection", icon: Boxes },
  { to: "/training", label: "Model Training", icon: Cpu },
  { to: "/evaluation", label: "Model Evaluation", icon: LineChart },
  { to: "/explainability", label: "Explainability", icon: Sparkles },
  { to: "/ecl-provisions", label: "ECL & Provisions", icon: Calculator },
  { to: "/assistant", label: "AI Assistant", icon: MessageSquare },
  { to: "/settings", label: "Settings", icon: Settings },
];

const validationNav: NavItem[] = [
  { to: "/validation/intake", label: "Intake & Governance", icon: FileText, exact: true },
  { to: "/validation/data-quality", label: "Data Validation", icon: Database },
  { to: "/validation/conceptual", label: "Conceptual Soundness", icon: BookOpen },
  { to: "/validation/challenger", label: "Replication & Benchmarking", icon: GitCompareArrows },
  { to: "/validation/performance", label: "Performance Testing", icon: BarChart3 },
  { to: "/validation/stress", label: "Stress & Backtesting", icon: Activity },
  { to: "/validation/regulatory", label: "Regulatory Compliance Review", icon: ShieldCheck },
  { to: "/validation/findings", label: "Findings & Final Report", icon: ClipboardCheck },
];

const developmentPaths = [
  ...developmentNav.map((n) => n.to),
  "/pd",
  "/lgd",
  "/ead",
];

function resolveWorkspace(pathname: string): "landing" | "development" | "validation" {
  if (pathname === "/") return "landing";
  if (pathname.startsWith("/validation")) return "validation";
  if (developmentPaths.some((p) => pathname === p || pathname.startsWith(p + "/"))) return "development";
  return "landing";
}

function resolveActiveModelTab(pathname: string): ModelTab["key"] {
  if (pathname.startsWith("/lgd")) return "lgd";
  if (pathname.startsWith("/ead")) return "ead";
  if (pathname.startsWith("/pd") || [
    "/data-upload",
    "/profiling",
    "/preprocessing",
    "/features",
    "/models",
    "/training",
    "/evaluation",
    "/explainability",
    "/ecl-provisions",
    "/assistant",
    "/settings",
    "/development",
  ].includes(pathname)) {
    return "pd";
  }
  return "pd";
}

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const workspace = resolveWorkspace(pathname);

  const isLanding = workspace === "landing";
  // Hide the shared model tabs on the Data Upload page per UX request
  const showModelTabs = workspace === "development" && pathname !== "/data-upload";
  const nav = workspace === "validation" ? validationNav : developmentNav;
  const activeModelTab = resolveActiveModelTab(pathname);
  const workspaceLabel = workspace === "validation" ? "Model Validation" : workspace === "development" ? "Model Development" : "Workspace";

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {!isLanding && (
        <aside
          className={cn(
            "sticky top-0 z-30 hidden h-screen shrink-0 flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-300 ease-out md:flex",
            collapsed ? "w-[76px]" : "w-[264px]",
          )}
        >
          <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg gradient-primary shadow-elegant">
              <ShieldCheck className="h-5 w-5 text-primary-foreground" />
            </div>
            {!collapsed && (
              <div className="flex flex-col leading-tight">
                <span className="text-sm font-semibold tracking-tight">Aegis Credit</span>
                <span className="text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/60">
                  {workspaceLabel}
                </span>
              </div>
            )}
          </div>

          {!collapsed && (
            <div className="px-3 pt-3">
              <Link
                to="/"
                className="flex items-center gap-2 rounded-lg border border-sidebar-border/60 bg-sidebar-accent/30 px-3 py-2 text-xs font-medium text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              >
                <Home className="h-3.5 w-3.5" />
                Switch workspace
              </Link>
              <div className="mt-3 grid grid-cols-2 gap-1.5">
                <Link
                  to="/data-upload"
                  className={cn(
                    "rounded-md px-2 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wider transition-colors",
                    workspace === "development"
                      ? "bg-primary text-primary-foreground"
                      : "bg-sidebar-accent/40 text-sidebar-foreground/70 hover:bg-sidebar-accent",
                  )}
                >
                  Develop
                </Link>
                <Link
                  to="/validation"
                  className={cn(
                    "rounded-md px-2 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wider transition-colors",
                    workspace === "validation"
                      ? "bg-primary text-primary-foreground"
                      : "bg-sidebar-accent/40 text-sidebar-foreground/70 hover:bg-sidebar-accent",
                  )}
                >
                  Validate
                </Link>
              </div>
            </div>
          )}

          <nav className="flex-1 overflow-y-auto px-3 py-4">
            <ul className="space-y-1">
              {nav.map((item) => {
                const Icon = item.icon;
                const active = item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(item.to + "/");
                return (
                  <li key={item.to}>
                    <Link
                      to={item.to}
                      className={cn(
                        "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-[18px] w-[18px] shrink-0",
                          active ? "text-primary" : "text-sidebar-foreground/60 group-hover:text-primary",
                        )}
                      />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                      {!collapsed && active && (
                        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="border-t border-sidebar-border p-3">
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            >
              {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
              {!collapsed && <span>Collapse</span>}
            </button>
          </div>
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-border/70 bg-background/80 px-4 backdrop-blur-md md:px-8">
          {isLanding ? (
            <Link to="/" className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg gradient-primary shadow-elegant">
                <ShieldCheck className="h-5 w-5 text-primary-foreground" />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold tracking-tight">Aegis Credit</div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">AI Model Platform</div>
              </div>
            </Link>
          ) : (
            <div className="hidden flex-1 items-center gap-2 md:flex">
              <div className="relative w-full max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  placeholder="Search models, rules, datasets…"
                  className="h-10 w-full rounded-lg border border-input bg-card pl-9 pr-3 text-sm outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/60 focus:bg-card"
                />
              </div>
            </div>
          )}
          {!isLanding && <div className="md:hidden text-sm font-semibold">Aegis Credit</div>}
          <div className="ml-auto flex items-center gap-2">
            {isLanding && (
              <Link
                to="/data-upload"
                className="hidden items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:border-primary/40 sm:inline-flex"
              >
                Develop
              </Link>
            )}
            {isLanding && (
              <Link
                to="/validation"
                className="hidden items-center gap-1.5 rounded-lg gradient-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow-elegant sm:inline-flex"
              >
                Validate
              </Link>
            )}
            {!isLanding && (
              <div className="hidden items-center gap-2 rounded-full bg-primary-soft px-3 py-1.5 text-xs font-medium text-foreground sm:flex">
                <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                Production · Tier 2
              </div>
            )}
            <button className="relative inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground">
              <Bell className="h-4 w-4" />
              <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-destructive" />
            </button>
            <div className="flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-2 pr-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-md gradient-primary text-[11px] font-semibold text-primary-foreground">
                AK
              </div>
              <div className="hidden text-left leading-tight sm:block">
                <div className="text-xs font-semibold">A. Khurana</div>
                <div className="text-[10px] text-muted-foreground">Risk Validator</div>
              </div>
            </div>
          </div>
        </header>

        {showModelTabs && (
          <div className="border-b border-border/70 bg-background/80 px-4 md:px-8">
            <div className="mx-auto flex max-w-7xl flex-wrap gap-2 py-3">
              {modelTabs.map((tab) => {
                const active = activeModelTab === tab.key;
                return (
                  <Link
                    key={tab.to}
                    to={tab.to}
                    className={cn(
                      "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                      active
                        ? "border-primary bg-primary text-primary-foreground shadow-sm"
                        : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
                    )}
                  >
                    {tab.label}
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 md:mb-8 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
