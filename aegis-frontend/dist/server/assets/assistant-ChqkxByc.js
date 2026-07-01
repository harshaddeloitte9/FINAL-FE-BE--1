import { s as suggestedPrompts } from "./mock-data-2vCp6sQZ.js";
import { useEffect, useRef, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { BookOpen, Send, Sparkles, Trash2, User } from "lucide-react";
//#region src/routes/assistant.tsx?tsr-split=component
var cannedAnswer = `**IFRS 9 Expected Credit Loss (ECL)** is a forward-looking impairment model that requires institutions to estimate credit losses across three stages:

- **Stage 1** — performing assets, 12-month ECL recognized.
- **Stage 2** — significant increase in credit risk (SICR), lifetime ECL recognized.
- **Stage 3** — credit-impaired, lifetime ECL with interest on net carrying amount.

ECL is computed as a probability-weighted estimate of **PD × LGD × EAD**, discounted at the effective interest rate, and must incorporate **forward-looking macroeconomic scenarios** (GDP, unemployment, house prices).

For your portfolio, the macro overlay was last refreshed 94 days ago — refreshing it will resolve the open IFRS 9-3 warning.`;
function Assistant() {
	const [messages, setMessages] = useState([{
		role: "assistant",
		content: "Hi — I'm your validation co-pilot. Ask me about IFRS 9, SS1/23, model performance, or why a specific compliance flag was raised."
	}]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const inputRef = useRef(null);
	const scrollRef = useRef(null);
	useEffect(() => {
		inputRef.current?.focus();
	}, []);
	useEffect(() => {
		scrollRef.current?.scrollTo({
			top: scrollRef.current.scrollHeight,
			behavior: "smooth"
		});
	}, [messages, loading]);
	const send = (text) => {
		if (!text.trim()) return;
		setMessages((m) => [...m, {
			role: "user",
			content: text
		}]);
		setInput("");
		setLoading(true);
		setTimeout(() => {
			setMessages((m) => [...m, {
				role: "assistant",
				content: cannedAnswer,
				sources: [
					"IFRS 9 §5.5",
					"PRA SS1/23 Principle 3.3",
					"Internal Validation Manual v4.2"
				]
			}]);
			setLoading(false);
			inputRef.current?.focus();
		}, 900);
	};
	const renderMarkdown = (text) => text.split("\n").map((line, i) => {
		if (line.startsWith("- ")) return /* @__PURE__ */ jsx("li", {
			className: "ml-5 list-disc",
			children: boldify(line.slice(2))
		}, i);
		if (!line.trim()) return /* @__PURE__ */ jsx("div", { className: "h-2" }, i);
		return /* @__PURE__ */ jsx("p", {
			className: "leading-relaxed",
			children: boldify(line)
		}, i);
	});
	return /* @__PURE__ */ jsxs("div", {
		className: "flex h-[calc(100vh-9rem)] flex-col gap-6 lg:flex-row",
		children: [/* @__PURE__ */ jsxs("div", {
			className: "flex min-h-0 flex-1 flex-col rounded-2xl border border-border bg-card shadow-elegant",
			children: [
				/* @__PURE__ */ jsxs("div", {
					className: "flex items-center justify-between border-b border-border px-6 py-4",
					children: [/* @__PURE__ */ jsxs("div", {
						className: "flex items-center gap-3",
						children: [/* @__PURE__ */ jsx("div", {
							className: "flex h-9 w-9 items-center justify-center rounded-lg gradient-primary",
							children: /* @__PURE__ */ jsx(Sparkles, { className: "h-5 w-5 text-primary-foreground" })
						}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("div", {
							className: "text-sm font-semibold",
							children: "Aegis Assistant"
						}), /* @__PURE__ */ jsx("div", {
							className: "text-[11px] text-muted-foreground",
							children: "Ollama · ChromaDB retrieval · regulatory corpus"
						})] })]
					}), /* @__PURE__ */ jsxs("button", {
						onClick: () => setMessages(messages.slice(0, 1)),
						className: "inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:border-primary/40",
						children: [/* @__PURE__ */ jsx(Trash2, { className: "h-3.5 w-3.5" }), " Clear"]
					})]
				}),
				/* @__PURE__ */ jsxs("div", {
					ref: scrollRef,
					className: "flex-1 space-y-6 overflow-y-auto px-6 py-6",
					children: [messages.map((m, i) => /* @__PURE__ */ jsxs("div", {
						className: "flex gap-3 " + (m.role === "user" ? "flex-row-reverse" : ""),
						children: [/* @__PURE__ */ jsx("div", {
							className: "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg " + (m.role === "user" ? "bg-secondary text-foreground" : "gradient-primary text-primary-foreground"),
							children: m.role === "user" ? /* @__PURE__ */ jsx(User, { className: "h-4 w-4" }) : /* @__PURE__ */ jsx(Sparkles, { className: "h-4 w-4" })
						}), /* @__PURE__ */ jsxs("div", {
							className: "max-w-2xl space-y-2 text-sm " + (m.role === "user" ? "text-right" : ""),
							children: [/* @__PURE__ */ jsx("div", {
								className: "inline-block rounded-2xl px-4 py-3 " + (m.role === "user" ? "bg-primary text-primary-foreground" : "bg-background text-foreground"),
								children: /* @__PURE__ */ jsx("div", {
									className: "space-y-1 text-left",
									children: renderMarkdown(m.content)
								})
							}), m.sources && /* @__PURE__ */ jsxs("div", {
								className: "flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground",
								children: [/* @__PURE__ */ jsx(BookOpen, { className: "h-3 w-3" }), m.sources.map((s) => /* @__PURE__ */ jsx("span", {
									className: "rounded-full border border-border bg-background px-2 py-0.5",
									children: s
								}, s))]
							})]
						})]
					}, i)), loading && /* @__PURE__ */ jsxs("div", {
						className: "flex gap-3",
						children: [/* @__PURE__ */ jsx("div", {
							className: "flex h-8 w-8 items-center justify-center rounded-lg gradient-primary text-primary-foreground",
							children: /* @__PURE__ */ jsx(Sparkles, { className: "h-4 w-4" })
						}), /* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-1 rounded-2xl bg-background px-4 py-3",
							children: [
								/* @__PURE__ */ jsx("span", { className: "h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.2s]" }),
								/* @__PURE__ */ jsx("span", { className: "h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.1s]" }),
								/* @__PURE__ */ jsx("span", { className: "h-1.5 w-1.5 animate-bounce rounded-full bg-primary" })
							]
						})]
					})]
				}),
				/* @__PURE__ */ jsx("div", {
					className: "border-t border-border p-4",
					children: /* @__PURE__ */ jsxs("form", {
						onSubmit: (e) => {
							e.preventDefault();
							send(input);
						},
						className: "flex items-end gap-2 rounded-xl border border-input bg-background p-2 focus-within:border-primary/60",
						children: [/* @__PURE__ */ jsx("textarea", {
							ref: inputRef,
							value: input,
							onChange: (e) => setInput(e.target.value),
							onKeyDown: (e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									send(input);
								}
							},
							rows: 1,
							placeholder: "Ask about IFRS 9, model performance, compliance flags…",
							className: "max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground/70"
						}), /* @__PURE__ */ jsx("button", {
							type: "submit",
							disabled: loading || !input.trim(),
							className: "inline-flex h-9 w-9 items-center justify-center rounded-lg gradient-primary text-primary-foreground disabled:opacity-40",
							children: /* @__PURE__ */ jsx(Send, { className: "h-4 w-4" })
						})]
					})
				})
			]
		}), /* @__PURE__ */ jsxs("aside", {
			className: "w-full shrink-0 space-y-3 lg:w-80",
			children: [/* @__PURE__ */ jsxs("div", {
				className: "rounded-2xl border border-border bg-card p-5 shadow-elegant",
				children: [/* @__PURE__ */ jsx("h3", {
					className: "text-sm font-semibold",
					children: "Suggested prompts"
				}), /* @__PURE__ */ jsx("div", {
					className: "mt-3 space-y-2",
					children: suggestedPrompts.map((p) => /* @__PURE__ */ jsx("button", {
						onClick: () => send(p),
						className: "w-full rounded-lg border border-border bg-background px-3 py-2 text-left text-xs hover:border-primary/40 hover:bg-primary-soft",
						children: p
					}, p))
				})]
			}), /* @__PURE__ */ jsxs("div", {
				className: "rounded-2xl border border-border bg-card p-5 text-xs text-muted-foreground shadow-elegant",
				children: [/* @__PURE__ */ jsx("div", {
					className: "font-semibold text-foreground",
					children: "Retrieval sources"
				}), /* @__PURE__ */ jsx("p", {
					className: "mt-2",
					children: "Answers are grounded in the IFRS 9 / IFRS 7 standards, PRA SS1/23, and your internal validation manuals. Citations appear under each response."
				})]
			})]
		})]
	});
}
function boldify(text) {
	return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) => p.startsWith("**") && p.endsWith("**") ? /* @__PURE__ */ jsx("strong", { children: p.slice(2, -2) }, i) : /* @__PURE__ */ jsx("span", { children: p }, i));
}
//#endregion
export { Assistant as component };
