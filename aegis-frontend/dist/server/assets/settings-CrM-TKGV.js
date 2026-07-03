import { n as PageHeader } from "./app-shell-fDQz9JMF.js";
import { jsx, jsxs } from "react/jsx-runtime";
//#region src/routes/settings.tsx?tsr-split=component
var sections = [
	{
		title: "Organization",
		body: "Deloitte Risk Advisory · UK & Ireland · 124 seats"
	},
	{
		title: "Default model tier",
		body: "Tier 2 (Material) — quarterly validation cadence"
	},
	{
		title: "Regulatory frameworks",
		body: "IFRS 9 · IFRS 7 · PRA SS1/23 · Basel IV (advanced)"
	},
	{
		title: "AI assistant model",
		body: "Ollama · llama3.1-70b · ChromaDB regulatory corpus v4.2"
	},
	{
		title: "Audit trail retention",
		body: "7 years · WORM storage · SOC 2 Type II"
	}
];
function Settings() {
	return /* @__PURE__ */ jsxs("div", {
		className: "space-y-8",
		children: [/* @__PURE__ */ jsx(PageHeader, {
			title: "Settings",
			description: "Workspace, governance, and integration preferences."
		}), /* @__PURE__ */ jsx("div", {
			className: "divide-y divide-border rounded-2xl border border-border bg-card shadow-elegant",
			children: sections.map((s) => /* @__PURE__ */ jsxs("div", {
				className: "flex flex-col gap-1 px-6 py-4 sm:flex-row sm:items-center sm:justify-between",
				children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
					className: "text-sm font-semibold",
					children: s.title
				}), /* @__PURE__ */ jsx("div", {
					className: "text-sm text-muted-foreground",
					children: s.body
				})] }), /* @__PURE__ */ jsx("button", {
					className: "rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:border-primary/40",
					children: "Edit"
				})]
			}, s.title))
		})]
	});
}
//#endregion
export { Settings as component };
