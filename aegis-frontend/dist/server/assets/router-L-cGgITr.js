import { t as AppShell } from "./app-shell-DXEPQAWO.js";
import { t as DatasetProvider } from "./app-context-DEU1RUW-.js";
import { useEffect } from "react";
import { HeadContent, Link, Outlet, Scripts, createFileRoute, createRootRouteWithContext, createRouter, lazyRouteComponent, useRouter } from "@tanstack/react-router";
import { jsx, jsxs } from "react/jsx-runtime";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
//#region src/styles.css?url
var styles_default = "/assets/styles-X14y1chw.css";
//#endregion
//#region src/lib/lovable-error-reporting.ts
function reportLovableError(error, context = {}) {
	if (typeof window === "undefined") return;
	window.__lovableEvents?.captureException?.(error, {
		source: "react_error_boundary",
		route: window.location.pathname,
		...context
	}, {
		mechanism: "react_error_boundary",
		handled: false,
		severity: "error"
	});
}
//#endregion
//#region src/routes/__root.tsx
function NotFoundComponent() {
	return /* @__PURE__ */ jsx("div", {
		className: "flex min-h-screen items-center justify-center bg-background px-4",
		children: /* @__PURE__ */ jsxs("div", {
			className: "max-w-md text-center",
			children: [
				/* @__PURE__ */ jsx("h1", {
					className: "text-7xl font-bold text-foreground",
					children: "404"
				}),
				/* @__PURE__ */ jsx("h2", {
					className: "mt-4 text-xl font-semibold text-foreground",
					children: "Page not found"
				}),
				/* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: "The page you're looking for doesn't exist or has been moved."
				}),
				/* @__PURE__ */ jsx("div", {
					className: "mt-6",
					children: /* @__PURE__ */ jsx(Link, {
						to: "/",
						className: "inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
						children: "Go home"
					})
				})
			]
		})
	});
}
function ErrorComponent({ error, reset }) {
	console.error(error);
	const router = useRouter();
	useEffect(() => {
		reportLovableError(error, { boundary: "tanstack_root_error_component" });
	}, [error]);
	return /* @__PURE__ */ jsx("div", {
		className: "flex min-h-screen items-center justify-center bg-background px-4",
		children: /* @__PURE__ */ jsxs("div", {
			className: "max-w-md text-center",
			children: [
				/* @__PURE__ */ jsx("h1", {
					className: "text-xl font-semibold tracking-tight text-foreground",
					children: "This page didn't load"
				}),
				/* @__PURE__ */ jsx("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: "Something went wrong on our end. You can try refreshing or head back home."
				}),
				/* @__PURE__ */ jsxs("div", {
					className: "mt-6 flex flex-wrap justify-center gap-2",
					children: [/* @__PURE__ */ jsx("button", {
						onClick: () => {
							router.invalidate();
							reset();
						},
						className: "inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
						children: "Try again"
					}), /* @__PURE__ */ jsx("a", {
						href: "/",
						className: "inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent",
						children: "Go home"
					})]
				})
			]
		})
	});
}
var Route$22 = createRootRouteWithContext()({
	head: () => ({
		meta: [
			{ charSet: "utf-8" },
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1"
			},
			{ title: "Aegis Credit — AI Model Validation Platform" },
			{
				name: "description",
				content: "Enterprise AI platform for credit risk model validation, regulatory compliance (IFRS 9, IFRS 7, SS1/23), and explainability."
			},
			{
				name: "author",
				content: "Aegis Credit"
			},
			{
				property: "og:title",
				content: "Aegis Credit — AI Model Validation"
			},
			{
				property: "og:description",
				content: "Validate credit risk models with built-in regulatory checks, explainability, and an AI assistant."
			},
			{
				property: "og:type",
				content: "website"
			},
			{
				name: "twitter:card",
				content: "summary"
			}
		],
		links: [{
			rel: "stylesheet",
			href: styles_default
		}]
	}),
	shellComponent: RootShell,
	component: RootComponent,
	notFoundComponent: NotFoundComponent,
	errorComponent: ErrorComponent
});
function RootShell({ children }) {
	return /* @__PURE__ */ jsxs("html", {
		lang: "en",
		children: [/* @__PURE__ */ jsx("head", { children: /* @__PURE__ */ jsx(HeadContent, {}) }), /* @__PURE__ */ jsxs("body", { children: [children, /* @__PURE__ */ jsx(Scripts, {})] })]
	});
}
function RootComponent() {
	const { queryClient } = Route$22.useRouteContext();
	return /* @__PURE__ */ jsx(QueryClientProvider, {
		client: queryClient,
		children: /* @__PURE__ */ jsx(DatasetProvider, { children: /* @__PURE__ */ jsx(AppShell, { children: /* @__PURE__ */ jsx(Outlet, {}) }) })
	});
}
//#endregion
//#region src/routes/validation.tsx
var $$splitComponentImporter$21 = () => import("./validation-B3Crd5Zy.js");
var Route$21 = createFileRoute("/validation")({ component: lazyRouteComponent($$splitComponentImporter$21, "component") });
//#endregion
//#region src/routes/training.tsx
var $$splitComponentImporter$20 = () => import("./training-DiOPQBH_.js");
var Route$20 = createFileRoute("/training")({
	head: () => ({ meta: [{ title: "Training — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$20, "component")
});
//#endregion
//#region src/routes/settings.tsx
var $$splitComponentImporter$19 = () => import("./settings-DoO-2SQu.js");
var Route$19 = createFileRoute("/settings")({
	head: () => ({ meta: [{ title: "Settings — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$19, "component")
});
//#endregion
//#region src/routes/profiling.tsx
var $$splitComponentImporter$18 = () => import("./profiling-DLbIFeab.js");
var Route$18 = createFileRoute("/profiling")({
	head: () => ({ meta: [{ title: "Data Profiling — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$18, "component")
});
//#endregion
//#region src/routes/preprocessing.tsx
var $$splitComponentImporter$17 = () => import("./preprocessing-CjYyZSsD.js");
var Route$17 = createFileRoute("/preprocessing")({
	head: () => ({ meta: [{ title: "Preprocessing — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$17, "component")
});
//#endregion
//#region src/routes/models.tsx
var $$splitComponentImporter$16 = () => import("./models-Cu1bvG3g.js");
var Route$16 = createFileRoute("/models")({
	head: () => ({ meta: [{ title: "Model Selection — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$16, "component")
});
//#endregion
//#region src/routes/features.tsx
var $$splitComponentImporter$15 = () => import("./features-DTQlNTRC.js");
var Route$15 = createFileRoute("/features")({
	head: () => ({ meta: [{ title: "Feature Engineering — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$15, "component")
});
//#endregion
//#region src/routes/explainability.tsx
var $$splitComponentImporter$14 = () => import("./explainability-B5yBGVLx.js");
var Route$14 = createFileRoute("/explainability")({
	head: () => ({ meta: [{ title: "Explainability — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$14, "component")
});
//#endregion
//#region src/routes/evaluation.tsx
var $$splitComponentImporter$13 = () => import("./evaluation-D2Pxk3dJ.js");
var Route$13 = createFileRoute("/evaluation")({
	head: () => ({ meta: [{ title: "Evaluation — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$13, "component")
});
//#endregion
//#region src/routes/development.tsx
var $$splitComponentImporter$12 = () => import("./development-DMKOLdM7.js");
var Route$12 = createFileRoute("/development")({
	head: () => ({ meta: [{ title: "Model Development — Aegis Credit" }, {
		name: "description",
		content: "Build, train, evaluate, and explain credit risk models."
	}] }),
	component: lazyRouteComponent($$splitComponentImporter$12, "component")
});
//#endregion
//#region src/routes/data-upload.tsx
var $$splitComponentImporter$11 = () => import("./data-upload-hOObprk8.js");
var Route$11 = createFileRoute("/data-upload")({
	head: () => ({ meta: [{ title: "Data Upload — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$11, "component")
});
//#endregion
//#region src/routes/assistant.tsx
var $$splitComponentImporter$10 = () => import("./assistant-DbdPNP31.js");
var Route$10 = createFileRoute("/assistant")({
	head: () => ({ meta: [{ title: "AI Assistant — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$10, "component")
});
//#endregion
//#region src/routes/index.tsx
var $$splitComponentImporter$9 = () => import("./routes-Ch-j1T6Y.js");
var Route$9 = createFileRoute("/")({
	head: () => ({ meta: [{ title: "Aegis Credit — Model Development & Validation" }, {
		name: "description",
		content: "Choose a workspace: build credit risk models or independently validate them for regulatory compliance and governance."
	}] }),
	component: lazyRouteComponent($$splitComponentImporter$9, "component")
});
//#endregion
//#region src/routes/validation.index.tsx
var $$splitComponentImporter$8 = () => import("./validation.index-F4QUG6dj.js");
var Route$8 = createFileRoute("/validation/")({
	head: () => ({ meta: [{ title: "Model Validation — Aegis Credit" }, {
		name: "description",
		content: "Independent validation: intake, data quality, conceptual soundness, challenger, performance, stress, regulatory, findings."
	}] }),
	component: lazyRouteComponent($$splitComponentImporter$8, "component")
});
//#endregion
//#region src/routes/validation.stress.tsx
var $$splitComponentImporter$7 = () => import("./validation.stress-VZ_9qDCK.js");
var Route$7 = createFileRoute("/validation/stress")({
	head: () => ({ meta: [{ title: "Stress & Backtesting — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$7, "component")
});
//#endregion
//#region src/routes/validation.regulatory.tsx
var $$splitComponentImporter$6 = () => import("./validation.regulatory-I4uiHBts.js");
var Route$6 = createFileRoute("/validation/regulatory")({
	head: () => ({ meta: [{ title: "Regulatory Compliance — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$6, "component")
});
//#endregion
//#region src/routes/validation.performance.tsx
var $$splitComponentImporter$5 = () => import("./validation.performance-B59rG_Fq.js");
var Route$5 = createFileRoute("/validation/performance")({
	head: () => ({ meta: [{ title: "Performance Validation — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$5, "component")
});
//#endregion
//#region src/routes/validation.intake.tsx
var $$splitComponentImporter$4 = () => import("./validation.intake-0Zr7x1V_.js");
var Route$4 = createFileRoute("/validation/intake")({
	head: () => ({ meta: [{ title: "Model Intake — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$4, "component")
});
//#endregion
//#region src/routes/validation.findings.tsx
var $$splitComponentImporter$3 = () => import("./validation.findings-DNGk6YtK.js");
var Route$3 = createFileRoute("/validation/findings")({
	head: () => ({ meta: [{ title: "Validation Findings & Report — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$3, "component")
});
//#endregion
//#region src/routes/validation.data-quality.tsx
var $$splitComponentImporter$2 = () => import("./validation.data-quality-DEwfEopr.js");
var Route$2 = createFileRoute("/validation/data-quality")({
	head: () => ({ meta: [{ title: "Data Quality — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$2, "component")
});
//#endregion
//#region src/routes/validation.conceptual.tsx
var $$splitComponentImporter$1 = () => import("./validation.conceptual-DYagQD-t.js");
var Route$1 = createFileRoute("/validation/conceptual")({
	head: () => ({ meta: [{ title: "Conceptual Soundness — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter$1, "component")
});
//#endregion
//#region src/routes/validation.challenger.tsx
var $$splitComponentImporter = () => import("./validation.challenger-CLajj4Zd.js");
var Route = createFileRoute("/validation/challenger")({
	head: () => ({ meta: [{ title: "Challenger Analysis — Aegis Credit" }] }),
	component: lazyRouteComponent($$splitComponentImporter, "component")
});
//#endregion
//#region src/routeTree.gen.ts
var ValidationRoute = Route$21.update({
	id: "/validation",
	path: "/validation",
	getParentRoute: () => Route$22
});
var TrainingRoute = Route$20.update({
	id: "/training",
	path: "/training",
	getParentRoute: () => Route$22
});
var SettingsRoute = Route$19.update({
	id: "/settings",
	path: "/settings",
	getParentRoute: () => Route$22
});
var ProfilingRoute = Route$18.update({
	id: "/profiling",
	path: "/profiling",
	getParentRoute: () => Route$22
});
var PreprocessingRoute = Route$17.update({
	id: "/preprocessing",
	path: "/preprocessing",
	getParentRoute: () => Route$22
});
var ModelsRoute = Route$16.update({
	id: "/models",
	path: "/models",
	getParentRoute: () => Route$22
});
var FeaturesRoute = Route$15.update({
	id: "/features",
	path: "/features",
	getParentRoute: () => Route$22
});
var ExplainabilityRoute = Route$14.update({
	id: "/explainability",
	path: "/explainability",
	getParentRoute: () => Route$22
});
var EvaluationRoute = Route$13.update({
	id: "/evaluation",
	path: "/evaluation",
	getParentRoute: () => Route$22
});
var DevelopmentRoute = Route$12.update({
	id: "/development",
	path: "/development",
	getParentRoute: () => Route$22
});
var DataUploadRoute = Route$11.update({
	id: "/data-upload",
	path: "/data-upload",
	getParentRoute: () => Route$22
});
var AssistantRoute = Route$10.update({
	id: "/assistant",
	path: "/assistant",
	getParentRoute: () => Route$22
});
var IndexRoute = Route$9.update({
	id: "/",
	path: "/",
	getParentRoute: () => Route$22
});
var ValidationIndexRoute = Route$8.update({
	id: "/",
	path: "/",
	getParentRoute: () => ValidationRoute
});
var ValidationStressRoute = Route$7.update({
	id: "/stress",
	path: "/stress",
	getParentRoute: () => ValidationRoute
});
var ValidationRegulatoryRoute = Route$6.update({
	id: "/regulatory",
	path: "/regulatory",
	getParentRoute: () => ValidationRoute
});
var ValidationPerformanceRoute = Route$5.update({
	id: "/performance",
	path: "/performance",
	getParentRoute: () => ValidationRoute
});
var ValidationIntakeRoute = Route$4.update({
	id: "/intake",
	path: "/intake",
	getParentRoute: () => ValidationRoute
});
var ValidationFindingsRoute = Route$3.update({
	id: "/findings",
	path: "/findings",
	getParentRoute: () => ValidationRoute
});
var ValidationDataQualityRoute = Route$2.update({
	id: "/data-quality",
	path: "/data-quality",
	getParentRoute: () => ValidationRoute
});
var ValidationConceptualRoute = Route$1.update({
	id: "/conceptual",
	path: "/conceptual",
	getParentRoute: () => ValidationRoute
});
var ValidationRouteChildren = {
	ValidationChallengerRoute: Route.update({
		id: "/challenger",
		path: "/challenger",
		getParentRoute: () => ValidationRoute
	}),
	ValidationConceptualRoute,
	ValidationDataQualityRoute,
	ValidationFindingsRoute,
	ValidationIntakeRoute,
	ValidationPerformanceRoute,
	ValidationRegulatoryRoute,
	ValidationStressRoute,
	ValidationIndexRoute
};
var rootRouteChildren = {
	IndexRoute,
	AssistantRoute,
	DataUploadRoute,
	DevelopmentRoute,
	EvaluationRoute,
	ExplainabilityRoute,
	FeaturesRoute,
	ModelsRoute,
	PreprocessingRoute,
	ProfilingRoute,
	SettingsRoute,
	TrainingRoute,
	ValidationRoute: ValidationRoute._addFileChildren(ValidationRouteChildren)
};
var routeTree = Route$22._addFileChildren(rootRouteChildren)._addFileTypes();
//#endregion
//#region src/router.tsx
var getRouter = () => {
	return createRouter({
		routeTree,
		context: { queryClient: new QueryClient() },
		scrollRestoration: true,
		defaultPreloadStaleTime: 0
	});
};
//#endregion
export { getRouter };
