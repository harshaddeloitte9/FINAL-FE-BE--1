import { StatusBadge } from "./status-badge";
import { BusinessRuleCards } from "./business-rule-cards";
import {
  getCompleteness,
  getUniqueness,
  getValidity,
  getConsistency,
  getTimeliness,
  getStatistical,
  getBusinessRulesState,
} from "./selectors";

// The six industry-standard dimensions from the Data Quality proposal
// (slide 6). Completeness/Uniqueness/Timeliness/Statistical/Validity are
// derived from real profile fields. Consistency is derived from the LLM-
// discovered, deterministically-evaluated business rules on
// businessRulesResult (see selectors.ts::getConsistency) — it stays
// "not_evaluated" (never a fabricated healthy/review) whenever discovery
// hasn't run, is unavailable, or found no applicable rules.
export function QualityDimensionsPanel({
  profile,
  businessRulesResult,
  isDiscoveringRules,
}: {
  profile: any;
  businessRulesResult?: any;
  isDiscoveringRules?: boolean;
}) {
  const validity = getValidity(profile);
  const consistency = getConsistency(businessRulesResult, isDiscoveringRules);
  const businessRulesState = getBusinessRulesState(businessRulesResult);
  const dimensions = [
    { name: "Completeness", ...getCompleteness(profile) },
    { name: "Uniqueness", ...getUniqueness(profile) },
    // Real numeric-format/date-parse checks come straight from getValidity().
    // Range and allowed-value validation are business rules with no
    // authoritative source in this dataset, so that limitation is appended
    // as a fixed trailing note rather than replacing the real evidence.
    {
      name: "Validity",
      ...validity,
      evidence: `${validity.evidence} Range and allowed-value validation not evaluated — no business-defined ranges or category lists are configured for this dataset.`,
    },
    { name: "Consistency", ...consistency },
    { name: "Timeliness", ...getTimeliness(profile) },
    { name: "Statistical", ...getStatistical(profile) },
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-4">
        <h3 className="text-base font-semibold text-slate-900">Quality Dimensions</h3>
        <p className="mt-0.5 text-[13px] text-slate-500">Six industry-standard dimensions, evaluated against this dataset's real profile.</p>
      </div>
      <div className="divide-y divide-slate-100">
        {dimensions.map((dim) => (
          <div key={dim.name} className="px-6 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[15px] font-semibold text-slate-900">{dim.name}</div>
                <div className="mt-0.5 text-[13px] leading-snug text-slate-500">{dim.evidence}</div>
              </div>
              <StatusBadge status={dim.status} />
            </div>
            {dim.name === "Consistency" && <BusinessRuleCards businessRulesState={businessRulesState} />}
          </div>
        ))}
      </div>
    </div>
  );
}
