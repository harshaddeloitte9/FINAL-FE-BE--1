import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Info } from "lucide-react";
import { PageHeader } from "@/components/app-shell";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useDataset } from "@/lib/app-context";
import { getPreferredTheme, setStoredTheme, type Theme } from "@/lib/theme";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Aegis Credit" }] }),
  component: Settings,
});

const REGULATORY_FRAMEWORKS = ["SS1/23", "SS11/13", "IFRS 9", "IFRS 7"];

function Settings() {
  const { decisionThreshold, setDecisionThreshold, resetSession } = useDataset();
  const [theme, setTheme] = useState<Theme>(() => getPreferredTheme());
  const [resetConfirming, setResetConfirming] = useState(false);
  const [resetDone, setResetDone] = useState(false);

  const toggleTheme = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setStoredTheme(next);
  };

  const handleReset = () => {
    if (!resetConfirming) {
      setResetConfirming(true);
      return;
    }
    resetSession();
    setResetConfirming(false);
    setResetDone(true);
    setTimeout(() => setResetDone(false), 3000);
  };

  return (
    <div className="space-y-8">
      <PageHeader title="Settings" description="Workspace preferences for this browser." />

      <div className="divide-y divide-border rounded-2xl border border-border bg-card shadow-elegant">
        {/* Decision threshold */}
        <div className="flex flex-col gap-3 px-6 py-5">
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold">Decision threshold</span>
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    aria-label="What is the decision threshold?"
                    className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
                  >
                    <Info className="h-4 w-4" />
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-80 text-sm leading-relaxed">
                  The model outputs a probability (e.g. 0.37, 0.82), not a direct yes/no. This threshold is the
                  cutoff used to turn that probability into a default / non-default classification. Example: at
                  0.50, any prediction ≥ 0.50 is classified as "will default." Lowering it flags more borrowers as
                  risky (catches more real defaults, but more false alarms); raising it is stricter (fewer false
                  alarms, but may miss some real defaults). This affects precision, recall, and other metrics shown
                  in Model Evaluation. Scoped to Model Development only — Model Validation stages calibrate their
                  own threshold independently and ignore this setting.
                </PopoverContent>
              </Popover>
            </div>
            <div className="text-sm text-muted-foreground">
              PD cut-off used to classify a prediction as default vs non-default when training or evaluating a
              model in Model Development. Model Validation stages (Replication, Performance Testing, Stress
              Testing) calibrate their own threshold independently and are not affected by this setting.
            </div>
          </div>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={0.1}
              max={0.9}
              step={0.05}
              value={decisionThreshold}
              onChange={(e) => setDecisionThreshold(Number(e.target.value))}
              className="h-2 w-full max-w-md accent-primary"
            />
            <span className="w-14 shrink-0 rounded-lg border border-border bg-background px-2 py-1 text-center text-sm font-semibold tabular-nums">
              {decisionThreshold.toFixed(2)}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Applied the next time a model is trained or evaluated in Model Development. Saved to this browser.
          </p>
        </div>

        {/* Dark mode */}
        <div className="flex flex-col gap-1 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">Dark mode</div>
            <div className="text-sm text-muted-foreground">Switches the interface color scheme. Saved to this browser.</div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={theme === "dark"}
            onClick={toggleTheme}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${theme === "dark" ? "bg-primary" : "bg-muted"}`}
          >
            <span
              className={`absolute top-0.5 h-5 w-5 rounded-full bg-background shadow transition-transform ${theme === "dark" ? "translate-x-5" : "translate-x-0.5"}`}
            />
          </button>
        </div>

        {/* Regulatory frameworks in scope */}
        <div className="flex flex-col gap-2 px-6 py-5">
          <div>
            <div className="text-sm font-semibold">Regulatory frameworks in scope</div>
            <div className="text-sm text-muted-foreground">What this platform validates models against.</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {REGULATORY_FRAMEWORKS.map((fw) => (
              <span key={fw} className="rounded-full border border-border bg-background px-3 py-1 text-xs font-medium">
                {fw}
              </span>
            ))}
          </div>
        </div>

        {/* Session / data reset */}
        <div className="flex flex-col gap-1 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">Reset session</div>
            <div className="text-sm text-muted-foreground">
              Clears the uploaded dataset, trained model, and all pipeline/validation results from this browser.
            </div>
          </div>
          <button
            type="button"
            onClick={handleReset}
            className={`shrink-0 rounded-lg border px-3 py-1.5 text-xs font-medium ${
              resetConfirming
                ? "border-destructive bg-destructive/10 text-destructive"
                : "border-border bg-background hover:border-destructive/40 hover:text-destructive"
            }`}
          >
            {resetDone ? "Cleared" : resetConfirming ? "Click again to confirm" : "Clear uploaded data"}
          </button>
        </div>
      </div>
    </div>
  );
}
