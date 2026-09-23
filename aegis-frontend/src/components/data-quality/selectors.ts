// Pure, presentation-layer derivations over the SAME profile object Data
// Preparation already reads (ds.profile, populated by the existing
// POST /data/upload -> _build_data_profile()). Nothing here recomputes a
// backend metric — every function only re-labels or re-groups fields that
// already exist on `profile`, and is explicit ("not_evaluated") whenever the
// underlying Aegis check simply never ran for this dataset, rather than
// defaulting to "healthy". See 24-06/main.py::_build_data_profile for the
// authoritative computation of every field read below.

export type DqStatus = "healthy" | "review" | "not_evaluated" | "critical";

export interface DimensionResult {
  status: DqStatus;
  headline: string;
  evidence: string;
}

function pct(n: number | null | undefined, digits = 1): string {
  return typeof n === "number" && Number.isFinite(n) ? `${n.toFixed(digits)}%` : "—";
}

export function getRows(profile: any): number | null {
  return typeof profile?.shape?.[0] === "number" ? profile.shape[0] : null;
}

export function getCols(profile: any): number | null {
  return typeof profile?.shape?.[1] === "number" ? profile.shape[1] : null;
}

export function getCompleteness(profile: any): DimensionResult {
  const missingPct = typeof profile?.missing_percentage === "number" ? profile.missing_percentage : null;
  if (missingPct === null) {
    return { status: "not_evaluated", headline: "Not evaluated", evidence: "Missing-value scan not available for this dataset." };
  }
  const completenessPct = Math.max(0, 100 - missingPct);
  const status: DqStatus = missingPct > 3 ? "review" : "healthy";
  const cells = typeof profile?.missing_cells === "number" ? profile.missing_cells : null;
  return {
    status,
    headline: pct(completenessPct),
    evidence:
      cells !== null
        ? `${cells.toLocaleString()} missing cells (${pct(missingPct)} of all cells)`
        : `${pct(missingPct)} of all cells are empty`,
  };
}

export function getUniqueness(profile: any): DimensionResult {
  const duplicateRows = typeof profile?.duplicate_rows === "number" ? profile.duplicate_rows : null;
  const duplicateRate = typeof profile?.duplicate_rate === "number" ? profile.duplicate_rate : null;
  if (duplicateRows === null) {
    return { status: "not_evaluated", headline: "Not evaluated", evidence: "Duplicate-row scan not available for this dataset." };
  }
  const status: DqStatus = duplicateRate !== null && duplicateRate > 1 ? "review" : "healthy";
  return {
    status,
    headline: duplicateRows.toLocaleString(),
    evidence:
      duplicateRate !== null
        ? `${duplicateRows.toLocaleString()} duplicate row${duplicateRows === 1 ? "" : "s"} (${pct(duplicateRate)} of rows)`
        : `${duplicateRows.toLocaleString()} duplicate row${duplicateRows === 1 ? "" : "s"}`,
  };
}

// Validity — implemented checks only: numeric-format parsing and date
// parsing, both objective/derivable straight from the data (a value either
// parses as a number/date or it doesn't). Range validity ("is this value
// within a valid range") and allowed-value validity ("is this category
// permitted") are business rules that require an authoritative schema this
// dataset does not carry — they are never inferred here and must stay
// "not_evaluated" until such configuration exists.
export function getValidity(profile: any): DimensionResult {
  const numericFormatErrors =
    profile?.numeric_format_errors && typeof profile.numeric_format_errors === "object" ? profile.numeric_format_errors : {};
  const dateIntegrity = profile?.date_integrity && typeof profile.date_integrity === "object" ? profile.date_integrity : {};

  const numericEntries = Object.entries(numericFormatErrors as Record<string, any>);
  const dateEntries = Object.entries(dateIntegrity as Record<string, any>).filter(
    ([, info]) => typeof info?.unparseable_count === "number"
  );

  const checkedCount = numericEntries.length + dateEntries.length;
  if (checkedCount === 0) {
    return {
      status: "not_evaluated",
      headline: "Not evaluated",
      evidence: "No numeric or date columns available for format validity checks in this dataset.",
    };
  }

  const flaggedNumeric = numericEntries.filter(([, info]) => (info?.count ?? 0) > 0);
  const flaggedDate = dateEntries.filter(([, info]) => (info?.unparseable_count ?? 0) > 0);
  const flaggedCount = flaggedNumeric.length + flaggedDate.length;
  const status: DqStatus = flaggedCount > 0 ? "review" : "healthy";

  const parts: string[] = [];
  flaggedNumeric.forEach(([col, info]) => {
    parts.push(`${col}: ${info.count.toLocaleString()} non-numeric value${info.count === 1 ? "" : "s"} (${pct(info.percentage)})`);
  });
  flaggedDate.forEach(([col, info]) => {
    parts.push(
      `${col}: ${info.unparseable_count.toLocaleString()} unparseable date${info.unparseable_count === 1 ? "" : "s"} (${pct(
        info.unparseable_percentage
      )})`
    );
  });

  const headline = flaggedCount > 0 ? `${flaggedCount} column${flaggedCount === 1 ? "" : "s"} flagged` : "No format issues flagged";
  const evidence =
    flaggedCount > 0
      ? `Format validity checked on ${checkedCount} column${checkedCount === 1 ? "" : "s"} — ${parts.join("; ")}.`
      : `Format validity checked on ${checkedCount} column${checkedCount === 1 ? "" : "s"} (numeric parsing, date parsing) — none flagged.`;

  return { status, headline, evidence };
}

export function getConsistency(): DimensionResult {
  return {
    status: "not_evaluated",
    headline: "Not evaluated",
    evidence: "Cross-column consistency checks are not yet implemented in Aegis (Phase 2 of the Data Quality proposal).",
  };
}

export function getTimeliness(profile: any): DimensionResult {
  const dateIntegrity = profile?.date_integrity && typeof profile.date_integrity === "object" ? profile.date_integrity : {};
  const entries = Object.entries(dateIntegrity as Record<string, any>);
  if (entries.length === 0) {
    return { status: "not_evaluated", headline: "Not evaluated", evidence: "No date fields detected in this dataset." };
  }
  const anomalous = entries.filter(([, info]) => (info?.future_count ?? 0) > 0 || (info?.ancient_count ?? 0) > 0);
  const status: DqStatus = anomalous.length > 0 ? "review" : "healthy";
  return {
    status,
    headline: `${entries.length} field${entries.length === 1 ? "" : "s"} checked`,
    evidence:
      anomalous.length > 0
        ? `${anomalous.length} of ${entries.length} date field${entries.length === 1 ? "" : "s"} contain future or pre-1900 values`
        : `${entries.length} date field${entries.length === 1 ? "" : "s"} checked for future/ancient values — none found`,
  };
}

export function getStatistical(profile: any): DimensionResult {
  const numericCount = typeof profile?.numeric_feature_count === "number" ? profile.numeric_feature_count : 0;
  const outlierAnalysis = profile?.outlier_analysis && typeof profile.outlier_analysis === "object" ? profile.outlier_analysis : {};
  const checkedCols = Object.keys(outlierAnalysis);
  if (numericCount === 0) {
    return { status: "not_evaluated", headline: "Not evaluated", evidence: "No numeric columns available for outlier or correlation analysis." };
  }
  if (checkedCols.length === 0) {
    return {
      status: "not_evaluated",
      headline: "Not evaluated",
      evidence: `${numericCount} numeric column${numericCount === 1 ? "" : "s"} detected, but outlier analysis did not run for this dataset.`,
    };
  }
  const flagged = checkedCols.filter((c) => outlierAnalysis[c]?.has_outliers);
  const status: DqStatus = flagged.length > 0 ? "review" : "healthy";
  const coverage = `Outliers checked on ${checkedCols.length} of ${numericCount} numeric column${numericCount === 1 ? "" : "s"}`;
  return {
    status,
    headline: flagged.length > 0 ? `${flagged.length} column${flagged.length === 1 ? "" : "s"} flagged` : "No outliers flagged",
    evidence: flagged.length > 0 ? `${coverage} — ${flagged.join(", ")} show elevated outlier rates.` : `${coverage} — none flagged.`,
  };
}

export function getTargetHealth(profile: any): DimensionResult & { hasTarget: boolean } {
  const targetSummary = profile?.target_summary;
  const hasTarget = Boolean(targetSummary && targetSummary.selected_target);
  if (!hasTarget) {
    return { status: "not_evaluated", headline: "Not evaluated", evidence: "No target column resolved for this dataset.", hasTarget: false };
  }
  const isImbalanced = Boolean(targetSummary.is_imbalanced);
  const ratio = typeof targetSummary.imbalance_ratio === "number" ? targetSummary.imbalance_ratio : null;
  return {
    status: isImbalanced ? "review" : "healthy",
    headline: ratio !== null ? `${ratio}:1` : isImbalanced ? "Imbalanced" : "Balanced",
    evidence: targetSummary.suggestion || (isImbalanced ? "Class imbalance detected." : "Target distribution appears balanced."),
    hasTarget: true,
  };
}

export function getSchemaHealth(profile: any): DimensionResult {
  const rows = getRows(profile);
  const cols = getCols(profile);
  if (rows === null || cols === null) {
    return { status: "not_evaluated", headline: "Not evaluated", evidence: "Dataset shape not available." };
  }
  const numeric = profile?.numeric_feature_count;
  const categorical = profile?.categorical_feature_count;
  return {
    status: "healthy",
    headline: `${cols} column${cols === 1 ? "" : "s"}`,
    evidence:
      typeof numeric === "number" && typeof categorical === "number"
        ? `${numeric} numeric · ${categorical} categorical column${categorical === 1 ? "" : "s"} detected across ${rows.toLocaleString()} rows`
        : `${rows.toLocaleString()} rows detected`,
  };
}

// Leakage (numeric col vs. binary target correlation > 0.95) only ever runs
// for a resolved binary target — see _build_data_profile. Distinguishing
// "checked, none found" from "not evaluated for this task type" matters:
// leakage_risk_cols is an empty array in BOTH cases from the API's own shape.
export function getLeakageEvaluation(profile: any): { evaluated: boolean; cols: string[] } {
  const evaluated = Boolean(profile?.target_col) && profile?.task_type === "binary";
  const cols = Array.isArray(profile?.leakage_risk_cols) ? profile.leakage_risk_cols : [];
  return { evaluated, cols };
}

export function getIdColumns(profile: any): string[] {
  const idCols = profile?.col_types?.id;
  return Array.isArray(idCols) ? idCols : [];
}

// agent2_flags_data is only populated when a target column resolved; on
// error the backend sets agent2_error instead. Both distinct from "target
// resolved, zero flags" (a real, checked, clean result).
export function getComplianceState(profile: any): { evaluated: boolean; flags: any[]; error: string | null } {
  const hasTarget = Boolean(profile?.target_col);
  const error = typeof profile?.agent2_error === "string" ? profile.agent2_error : null;
  const flags = Array.isArray(profile?.agent2_flags_data) ? profile.agent2_flags_data : [];
  return { evaluated: hasTarget && !error, flags, error };
}

export interface IssueRow {
  id: string;
  severity: "CRITICAL" | "HIGH" | "WARNING" | "INFO";
  dimension: string;
  issue: string;
  column: string;
  recordsAffected: string;
  action: string;
}

const SEVERITY_ORDER: Record<IssueRow["severity"], number> = { CRITICAL: 0, HIGH: 1, WARNING: 2, INFO: 3 };

// Builds real issue rows only from signals the profile actually contains —
// no example/placeholder rows, no invented record counts.
export function buildIssues(profile: any): IssueRow[] {
  const issues: IssueRow[] = [];
  const rows = getRows(profile);
  const rowsLabel = rows !== null ? rows.toLocaleString() : "—";

  const missingByColumn = profile?.missing_by_column && typeof profile.missing_by_column === "object" ? profile.missing_by_column : {};
  Object.entries(missingByColumn as Record<string, any>)
    .filter(([, info]) => (info?.percentage ?? 0) > 0)
    .sort((a, b) => (b[1]?.percentage ?? 0) - (a[1]?.percentage ?? 0))
    .forEach(([col, info]) => {
      const p = info?.percentage ?? 0;
      issues.push({
        id: `missing-${col}`,
        severity: p > 20 ? "HIGH" : p > 5 ? "WARNING" : "INFO",
        dimension: "Completeness",
        issue: `${pct(p)} missing`,
        column: col,
        recordsAffected: typeof info?.count === "number" ? info.count.toLocaleString() : "—",
        action: "Review Treatment",
      });
    });

  const targetSummary = profile?.target_summary;
  if (targetSummary?.is_imbalanced) {
    issues.push({
      id: "target-imbalance",
      severity: "WARNING",
      dimension: "Target Quality",
      issue: typeof targetSummary.imbalance_ratio === "number" ? `${targetSummary.imbalance_ratio}:1 class imbalance` : "Class imbalance detected",
      column: targetSummary.selected_target ?? "—",
      recordsAffected: rowsLabel,
      action: "Review imbalance",
    });
  }

  getIdColumns(profile).forEach((col) => {
    issues.push({
      id: `id-${col}`,
      severity: "INFO",
      dimension: "Leakage Risk",
      issue: "ID-like column detected",
      column: col,
      recordsAffected: rowsLabel,
      action: "Exclude from modelling",
    });
  });

  const { evaluated: leakageEvaluated, cols: leakageCols } = getLeakageEvaluation(profile);
  if (leakageEvaluated) {
    leakageCols.forEach((col: string) => {
      issues.push({
        id: `leakage-${col}`,
        severity: "HIGH",
        dimension: "Leakage Risk",
        issue: "Correlation with target exceeds 0.95",
        column: col,
        recordsAffected: rowsLabel,
        action: "Review for leakage",
      });
    });
  }

  const duplicateRows = profile?.duplicate_rows;
  if (typeof duplicateRows === "number" && duplicateRows > 0) {
    issues.push({
      id: "duplicate-rows",
      severity: (profile?.duplicate_rate ?? 0) > 1 ? "WARNING" : "INFO",
      dimension: "Uniqueness",
      issue: `${duplicateRows.toLocaleString()} duplicate row${duplicateRows === 1 ? "" : "s"}`,
      column: "—",
      recordsAffected: duplicateRows.toLocaleString(),
      action: "Review in Data Preparation",
    });
  }

  const dateIntegrity = profile?.date_integrity && typeof profile.date_integrity === "object" ? profile.date_integrity : {};
  Object.entries(dateIntegrity as Record<string, any>).forEach(([col, info]) => {
    const future = (info as any)?.future_count ?? 0;
    const ancient = (info as any)?.ancient_count ?? 0;
    if (future > 0 || ancient > 0) {
      const parts: string[] = [];
      if (future > 0) parts.push(`${future} future date${future === 1 ? "" : "s"}`);
      if (ancient > 0) parts.push(`${ancient} pre-1900 date${ancient === 1 ? "" : "s"}`);
      issues.push({
        id: `date-${col}`,
        severity: "WARNING",
        dimension: "Timeliness",
        issue: parts.join(", "),
        column: col,
        recordsAffected: (future + ancient).toLocaleString(),
        action: "Review date values",
      });
    }
  });

  // Validity — numeric format errors. Separate id/dimension from the
  // Timeliness date-integrity issues above; this block never touches
  // future_count/ancient_count.
  const numericFormatErrors =
    profile?.numeric_format_errors && typeof profile.numeric_format_errors === "object" ? profile.numeric_format_errors : {};
  Object.entries(numericFormatErrors as Record<string, any>)
    .filter(([, info]) => (info?.count ?? 0) > 0)
    .sort((a, b) => (b[1]?.count ?? 0) - (a[1]?.count ?? 0))
    .forEach(([col, info]) => {
      issues.push({
        id: `numeric-format-${col}`,
        severity: (info?.percentage ?? 0) > 5 ? "WARNING" : "INFO",
        dimension: "Validity",
        issue: `${info.count.toLocaleString()} non-numeric value${info.count === 1 ? "" : "s"}`,
        column: col,
        recordsAffected: info.count.toLocaleString(),
        action: "Review numeric values",
      });
    });

  // Validity — date parse failures (raw values that never parsed as a date
  // at all), distinct from the future/ancient Timeliness issue above.
  Object.entries(dateIntegrity as Record<string, any>)
    .filter(([, info]) => ((info as any)?.unparseable_count ?? 0) > 0)
    .forEach(([col, info]) => {
      const unparseable = (info as any).unparseable_count;
      issues.push({
        id: `date-format-${col}`,
        severity: ((info as any)?.unparseable_percentage ?? 0) > 5 ? "WARNING" : "INFO",
        dimension: "Validity",
        issue: `${unparseable.toLocaleString()} unparseable date${unparseable === 1 ? "" : "s"}`,
        column: col,
        recordsAffected: unparseable.toLocaleString(),
        action: "Review date values",
      });
    });

  const { flags } = getComplianceState(profile);
  flags.forEach((flag: any, i: number) => {
    const sev: IssueRow["severity"] = flag?.severity === "high" ? "CRITICAL" : flag?.severity === "medium" ? "WARNING" : "INFO";
    const observed = flag?.observed_value;
    const column = Array.isArray(observed) ? observed.join(", ") : typeof observed === "string" ? observed : "—";
    issues.push({
      id: `compliance-${i}`,
      severity: sev,
      dimension: "Compliance",
      issue: flag?.flag ?? "Compliance flag",
      column,
      recordsAffected: "—",
      action: flag?.suggestion ?? "Review",
    });
  });

  return issues.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
}

export interface ColumnDiagnostic {
  column: string;
  type: string;
  missingPct: number | null;
  missingCount: number | null;
  uniqueValues: number | null;
  min: string | number | null;
  max: string | number | null;
  mean: string | number | null;
  sampleValues: string;
  outlier: { count: number; fraction: number; hasOutliers: boolean } | null;
  outlierApplicable: boolean;
  dateInfo: { minDate: string; maxDate: string; futureCount: number; ancientCount: number; unparseableCount: number } | null;
  numericFormatError: { count: number; percentage: number } | null;
  isIdColumn: boolean;
  isLeakageRisk: boolean;
  complianceNote: string | null;
  status: DqStatus;
}

// Column-level rows sourced from data_dictionary (the richest per-column
// record _build_data_profile already returns), cross-referenced against
// outlier_analysis / date_integrity / col_types / leakage_risk_cols /
// agent2_flags_data for the same column name — never a second calculation.
export function buildColumnDiagnostics(profile: any): ColumnDiagnostic[] {
  const dataDictionary: any[] = Array.isArray(profile?.data_dictionary) ? profile.data_dictionary : [];
  const outlierAnalysis = profile?.outlier_analysis && typeof profile.outlier_analysis === "object" ? profile.outlier_analysis : {};
  const dateIntegrity = profile?.date_integrity && typeof profile.date_integrity === "object" ? profile.date_integrity : {};
  const numericFormatErrors =
    profile?.numeric_format_errors && typeof profile.numeric_format_errors === "object" ? profile.numeric_format_errors : {};
  const numericCols: string[] = Array.isArray(profile?.col_types?.numeric) ? profile.col_types.numeric : [];
  const idCols = new Set(getIdColumns(profile));
  const { cols: leakageCols } = getLeakageEvaluation(profile);
  const leakageSet = new Set(leakageCols);
  const { flags } = getComplianceState(profile);

  return dataDictionary.map((row) => {
    const col = row.Column as string;
    const isNumeric = numericCols.includes(col);
    const outlierInfo = outlierAnalysis[col];
    const dInfo = dateIntegrity[col];
    const numericFormatInfo = numericFormatErrors[col];
    const missingPct = typeof row["Missing %"] === "number" ? row["Missing %"] : null;
    const isId = idCols.has(col);
    const isLeakage = leakageSet.has(col);
    const hasOutlierIssue = Boolean(outlierInfo?.has_outliers);
    const hasNumericFormatIssue = Boolean(numericFormatInfo && numericFormatInfo.count > 0);
    const hasDateParseIssue = Boolean(dInfo && (dInfo.unparseable_count ?? 0) > 0);
    const matchingFlag = flags.find((f: any) => {
      const observed = f?.observed_value;
      return Array.isArray(observed) ? observed.includes(col) : observed === col;
    });
    const status: DqStatus =
      (missingPct !== null && missingPct > 5) ||
      hasOutlierIssue ||
      hasNumericFormatIssue ||
      hasDateParseIssue ||
      isLeakage ||
      Boolean(matchingFlag)
        ? "review"
        : "healthy";

    return {
      column: col,
      type: row["Detected Type"] ?? "—",
      missingPct,
      missingCount: typeof row["Missing Count"] === "number" ? row["Missing Count"] : null,
      uniqueValues: typeof row["Unique Values"] === "number" ? row["Unique Values"] : null,
      min: row.Min ?? null,
      max: row.Max ?? null,
      mean: row.Mean ?? null,
      sampleValues: row["Sample Values"] ?? "",
      outlier: outlierInfo
        ? { count: outlierInfo.outlier_count, fraction: outlierInfo.outlier_fraction, hasOutliers: outlierInfo.has_outliers }
        : null,
      outlierApplicable: isNumeric,
      dateInfo: dInfo
        ? {
            minDate: dInfo.min_date,
            maxDate: dInfo.max_date,
            futureCount: dInfo.future_count ?? 0,
            ancientCount: dInfo.ancient_count ?? 0,
            unparseableCount: dInfo.unparseable_count ?? 0,
          }
        : null,
      numericFormatError: numericFormatInfo ? { count: numericFormatInfo.count, percentage: numericFormatInfo.percentage } : null,
      isIdColumn: isId,
      isLeakageRisk: isLeakage,
      complianceNote: matchingFlag?.suggestion ?? null,
      status,
    };
  });
}
