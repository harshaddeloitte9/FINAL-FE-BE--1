import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-shell";
import { suggestedPrompts } from "@/lib/mock-data";
import { Send, Sparkles, Trash2, BookOpen, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export const Route = createFileRoute("/assistant")({
  head: () => ({ meta: [{ title: "AI Assistant — Aegis Credit" }] }),
  component: Assistant,
});

type Msg = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
};

const cannedAnswer = `**IFRS 9 Expected Credit Loss (ECL)** is a forward-looking impairment model that requires institutions to estimate credit losses across three stages:

- **Stage 1** — performing assets, 12-month ECL recognized.
- **Stage 2** — significant increase in credit risk (SICR), lifetime ECL recognized.
- **Stage 3** — credit-impaired, lifetime ECL with interest on net carrying amount.

ECL is computed as a probability-weighted estimate of **PD × LGD × EAD**, discounted at the effective interest rate, and must incorporate **forward-looking macroeconomic scenarios** (GDP, unemployment, house prices).

For your portfolio, the macro overlay was last refreshed 94 days ago — refreshing it will resolve the open IFRS 9-3 warning.`;

function Assistant() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Hi — I'm your validation co-pilot. Ask me about IFRS 9, SS1/23, model performance, or why a specific compliance flag was raised.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = (text: string) => {
    if (!text.trim()) return;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: cannedAnswer,
          sources: ["IFRS 9 §5.5", "PRA SS1/23 Principle 3.3", "Internal Validation Manual v4.2"],
        },
      ]);
      setLoading(false);
      inputRef.current?.focus();
    }, 900);
  };

  const renderMarkdown = (text: string) =>
    text.split("\n").map((line, i) => {
      if (line.startsWith("- ")) {
        return (
          <li key={i} className="ml-5 list-disc">
            {boldify(line.slice(2))}
          </li>
        );
      }
      if (!line.trim()) return <div key={i} className="h-2" />;
      return (
        <p key={i} className="leading-relaxed">
          {boldify(line)}
        </p>
      );
    });

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col gap-6 lg:flex-row">
      <div className="flex min-h-0 flex-1 flex-col rounded-2xl border border-border bg-card shadow-elegant">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg gradient-primary">
              <Sparkles className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <div className="text-sm font-semibold">Aegis Assistant</div>
              <div className="text-[11px] text-muted-foreground">
                Ollama · ChromaDB retrieval · regulatory corpus
              </div>
            </div>
          </div>
          <button
            onClick={() => setMessages(messages.slice(0, 1))}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:border-primary/40"
          >
            <Trash2 className="h-3.5 w-3.5" /> Clear
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
          {messages.map((m, i) => (
            <div key={i} className={"flex gap-3 " + (m.role === "user" ? "flex-row-reverse" : "")}>
              <div
                className={
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg " +
                  (m.role === "user"
                    ? "bg-secondary text-foreground"
                    : "gradient-primary text-primary-foreground")
                }
              >
                {m.role === "user" ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
              </div>
              <div className={"max-w-2xl space-y-2 text-sm " + (m.role === "user" ? "text-right" : "")}>
                <div
                  className={
                    "inline-block rounded-2xl px-4 py-3 " +
                    (m.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-background text-foreground")
                  }
                >
                  <div className="space-y-1 text-left">{renderMarkdown(m.content)}</div>
                </div>
                {m.sources && (
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    <BookOpen className="h-3 w-3" />
                    {m.sources.map((s) => (
                      <span key={s} className="rounded-full border border-border bg-background px-2 py-0.5">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary text-primary-foreground">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-1 rounded-2xl bg-background px-4 py-3">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.2s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.1s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-border p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-end gap-2 rounded-xl border border-input bg-background p-2 focus-within:border-primary/60"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              placeholder="Ask about IFRS 9, model performance, compliance flags…"
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground/70"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg gradient-primary text-primary-foreground disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>

      <aside className="w-full shrink-0 space-y-3 lg:w-80">
        <div className="rounded-2xl border border-border bg-card p-5 shadow-elegant">
          <h3 className="text-sm font-semibold">Suggested prompts</h3>
          <div className="mt-3 space-y-2">
            {suggestedPrompts.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-left text-xs hover:border-primary/40 hover:bg-primary-soft"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5 text-xs text-muted-foreground shadow-elegant">
          <div className="font-semibold text-foreground">Retrieval sources</div>
          <p className="mt-2">
            Answers are grounded in the IFRS 9 / IFRS 7 standards, PRA SS1/23, and your internal
            validation manuals. Citations appear under each response.
          </p>
        </div>
      </aside>
    </div>
  );
}

function boldify(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i}>{p.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}
