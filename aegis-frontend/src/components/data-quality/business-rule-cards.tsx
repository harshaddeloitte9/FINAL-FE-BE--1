import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { cn } from "@/lib/utils";
import type { BusinessRule, BusinessRulesState } from "./selectors";

function MiniRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-200/70 py-1.5 text-[12.5px] last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono font-semibold text-slate-800">{value}</span>
    </div>
  );
}

function confidenceLabel(confidence: number | null): string {
  return typeof confidence === "number" ? `${Math.round(confidence * 100)}%` : "—";
}

// One applied, deterministically-evaluated rule. Every number shown here
// (violations, rows checked, violation rate) is echoed straight from the
// backend's POST /data/business-rules/discover response — nothing is
// recomputed in React.
function AppliedRuleCard({ rule }: { rule: BusinessRule }) {
  const violationCount = rule.violation_count ?? 0;
  const hasViolations = violationCount > 0;

  return (
    <AccordionItem value={rule.rule_id} className="border-slate-100 px-3">
      <AccordionTrigger className="py-2.5 text-left text-[13px] font-medium text-slate-700 hover:no-underline">
        <div className="flex flex-1 flex-wrap items-center justify-between gap-2 pr-2">
          <span className="font-mono text-[12.5px] text-slate-800">{rule.condition_display}</span>
          <span className={cn("text-[12px] font-semibold", hasViolations ? "text-amber-700" : "text-emerald-700")}>
            {hasViolations
              ? `${violationCount.toLocaleString()} violation${violationCount === 1 ? "" : "s"}`
              : "No violations"}
          </span>
        </div>
      </AccordionTrigger>
      <AccordionContent>
        <div className="rounded-lg bg-slate-50/70 px-3">
          <MiniRow
            label="Violations"
            value={`${violationCount.toLocaleString()} / ${(rule.rows_checked ?? 0).toLocaleString()} applicable rows`}
          />
          <MiniRow
            label="Violation rate"
            value={typeof rule.violation_percentage === "number" ? `${rule.violation_percentage.toFixed(2)}%` : "—"}
          />
          <MiniRow label="Source" value="LLM inferred" />
          <MiniRow label="Confidence" value={confidenceLabel(rule.confidence)} />
          <MiniRow label="Status" value="Applied" />
        </div>
        {rule.rationale && <p className="mt-2 px-1 text-[12px] leading-snug text-slate-500">{rule.rationale}</p>}
      </AccordionContent>
    </AccordionItem>
  );
}

// Suggested rules are proposals only — never executed, never affecting
// Consistency's health — so they're rendered as flat, muted, non-expandable
// rows, visually distinct from applied rule cards.
function SuggestedRuleRow({ rule }: { rule: BusinessRule }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-3 py-2 text-[12px] text-slate-500">
      <span>
        Potential business rule identified:{" "}
        <span className="font-mono text-slate-600">{rule.condition_display}</span>
      </span>
      <span className="flex items-center gap-2 whitespace-nowrap">
        <span>Confidence: {confidenceLabel(rule.confidence)}</span>
        <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-slate-400">
          Suggested
        </span>
      </span>
    </div>
  );
}

// Compact, non-impacting expandable rule cards for the Consistency dimension
// row. Applied rules (real, deterministically-evaluated) render as accordion
// items; suggested rules render as muted, non-expandable rows; invalid rules
// are summarized in a single line for auditability without cluttering the
// page with rejected LLM proposals — see business_rules.py's safety gate for
// why a rule ends up invalid.
export function BusinessRuleCards({ businessRulesState }: { businessRulesState: BusinessRulesState }) {
  const { appliedRules, suggestedRules, invalidRules } = businessRulesState;

  if (appliedRules.length === 0 && suggestedRules.length === 0 && invalidRules.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 space-y-2">
      {appliedRules.length > 0 && (
        <Accordion type="multiple" className="rounded-lg border border-slate-100">
          {appliedRules.map((rule) => (
            <AppliedRuleCard key={rule.rule_id} rule={rule} />
          ))}
        </Accordion>
      )}
      {suggestedRules.length > 0 && (
        <div className="space-y-1.5">
          {suggestedRules.map((rule) => (
            <SuggestedRuleRow key={rule.rule_id} rule={rule} />
          ))}
        </div>
      )}
      {invalidRules.length > 0 && (
        <p className="px-1 text-[11.5px] text-slate-400">
          {invalidRules.length} proposed rule{invalidRules.length === 1 ? "" : "s"} labeled <span className="font-semibold">Invalid</span>{" "}
          — could not be safely validated and {invalidRules.length === 1 ? "was" : "were"} not applied.
        </p>
      )}
    </div>
  );
}
