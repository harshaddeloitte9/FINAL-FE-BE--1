export const kpis = [
  { label: "Models Validated", value: "47", delta: "+6 this quarter", tone: "neutral" as const },
  { label: "Compliance Score", value: "92.4%", delta: "+1.8% vs last run", tone: "positive" as const },
  { label: "Regulatory Flags", value: "3", delta: "1 High · 2 Medium", tone: "warning" as const },
  { label: "Model Risk Tier", value: "Tier 2", delta: "Material", tone: "neutral" as const },
  { label: "ROC-AUC", value: "0.873", delta: "+0.012", tone: "positive" as const },
  { label: "Recall", value: "0.812", delta: "Target ≥ 0.80", tone: "positive" as const },
  { label: "Precision", value: "0.768", delta: "Stable", tone: "neutral" as const },
  { label: "Last Validation", value: "12 min ago", delta: "Auto-refresh on", tone: "neutral" as const },
];

export const pipeline = [
  { key: "upload", label: "Data Upload", status: "done" },
  { key: "profile", label: "Data Profiling", status: "done" },
  { key: "regulatory", label: "Regulatory Checks", status: "done" },
  { key: "preprocess", label: "Preprocessing", status: "done" },
  { key: "features", label: "Feature Engineering", status: "done" },
  { key: "models", label: "Model Selection", status: "done" },
  { key: "training", label: "Training", status: "active" },
  { key: "evaluation", label: "Evaluation", status: "pending" },
  { key: "explain", label: "Explainability", status: "pending" },
] as const;

export const rocCurve = Array.from({ length: 21 }, (_, i) => {
  const fpr = i / 20;
  const tpr = Math.min(1, Math.pow(fpr, 0.35) + 0.02);
  return { fpr: +fpr.toFixed(2), tpr: +tpr.toFixed(3), diagonal: +fpr.toFixed(2) };
});

export const prCurve = Array.from({ length: 21 }, (_, i) => {
  const r = i / 20;
  const p = Math.max(0.4, 0.98 - Math.pow(r, 1.6));
  return { recall: +r.toFixed(2), precision: +p.toFixed(3) };
});

export const scoreDistribution = Array.from({ length: 20 }, (_, i) => ({
  bin: `${(i * 5).toString().padStart(2, "0")}`,
  good: Math.round(80 * Math.exp(-Math.pow((i - 4) / 4, 2))) + 5,
  bad: Math.round(60 * Math.exp(-Math.pow((i - 14) / 4, 2))) + 3,
}));

export const featureImportance = [
  { feature: "DTI Ratio", value: 0.21 },
  { feature: "Credit Utilization", value: 0.17 },
  { feature: "Months Since Delinquency", value: 0.14 },
  { feature: "Annual Income (log)", value: 0.11 },
  { feature: "Loan-to-Value", value: 0.09 },
  { feature: "Employment Tenure", value: 0.07 },
  { feature: "Number of Open Trades", value: 0.06 },
  { feature: "Revolving Balance", value: 0.05 },
  { feature: "Mortgage Status", value: 0.04 },
  { feature: "Region Risk Index", value: 0.03 },
];

export const correlationFeatures = [
  "DTI", "Util.", "Income", "LTV", "Tenure", "Trades", "Bal.", "Region",
];

export const correlationMatrix = correlationFeatures.map((_, i) =>
  correlationFeatures.map((_, j) => {
    if (i === j) return 1;
    const seed = Math.sin(i * 13 + j * 7) * 0.5 + Math.sin(i + j) * 0.2;
    return +seed.toFixed(2);
  }),
);

export const regulatoryChecks = [
  {
    framework: "IFRS 9",
    rules: [
      { id: "IFRS9-1", title: "ECL staging definitions", status: "PASS", severity: "Low" },
      { id: "IFRS9-2", title: "12-month vs lifetime ECL transition", status: "PASS", severity: "Low" },
      { id: "IFRS9-3", title: "Forward-looking macroeconomic overlay", status: "WARNING", severity: "Medium",
        detail: "Macroeconomic scenario weights have not been refreshed in the last 90 days.",
        remediation: "Refresh GDP/Unemployment scenario weights and re-run ECL stage 2 cohort." },
      { id: "IFRS9-4", title: "SICR threshold calibration", status: "PASS", severity: "Low" },
    ],
  },
  {
    framework: "IFRS 7",
    rules: [
      { id: "IFRS7-1", title: "Credit risk disclosure granularity", status: "PASS", severity: "Low" },
      { id: "IFRS7-2", title: "Concentration risk reporting", status: "WARNING", severity: "Medium",
        detail: "Top-10 obligor exposure exceeds 18% — disclosure narrative required.",
        remediation: "Append concentration commentary to Pillar 3 appendix." },
    ],
  },
  {
    framework: "SS1/23 (PRA)",
    rules: [
      { id: "SS123-3.3", title: "Model tiering & governance ownership", status: "PASS", severity: "Low" },
      { id: "SS123-4.1", title: "Independent validation evidence", status: "FAIL", severity: "High",
        detail: "Challenger model benchmarks missing for the last quarterly cycle.",
        remediation: "Run Ridge + LightGBM challenger benchmarks and attach evidence pack." },
      { id: "SS123-5.2", title: "Ongoing monitoring frequency", status: "PASS", severity: "Low" },
    ],
  },
];

export const models = [
  { name: "Logistic Regression", strengths: "Highly interpretable, regulator-friendly", weaknesses: "Limited non-linear capture", suitability: "Baseline / scorecards", auc: 0.812 },
  { name: "Ridge Classifier", strengths: "Stable under multicollinearity", weaknesses: "No probability calibration by default", suitability: "Stress benchmarks", auc: 0.804 },
  { name: "Random Forest", strengths: "Robust to outliers, feature interactions", weaknesses: "Larger memory footprint", suitability: "Champion candidate", auc: 0.851 },
  { name: "Gradient Boosting", strengths: "Strong tabular performance", weaknesses: "Slower training, tuning sensitive", suitability: "Challenger", auc: 0.864 },
  { name: "XGBoost", strengths: "State-of-the-art tabular accuracy", weaknesses: "Higher explainability burden", suitability: "Champion (selected)", auc: 0.873, selected: true },
  { name: "LightGBM", strengths: "Fast training on large data", weaknesses: "Sensitive to leaf parameters", suitability: "Challenger", auc: 0.869 },
];

export const trainingLogs = [
  "[10:14:02] Starting champion run — XGBoost v1.7.6",
  "[10:14:03] Split: train 70% / valid 15% / test 15% — stratified on default flag",
  "[10:14:04] SMOTE applied on training fold (target ratio 1:2)",
  "[10:14:05] Cross-validation: 5-fold stratified, scoring=roc_auc",
  "[10:14:18] Fold 1 → AUC 0.871 · Recall 0.806",
  "[10:14:31] Fold 2 → AUC 0.875 · Recall 0.814",
  "[10:14:45] Fold 3 → AUC 0.870 · Recall 0.811",
  "[10:14:58] Fold 4 → AUC 0.878 · Recall 0.819",
  "[10:15:12] Fold 5 → AUC 0.872 · Recall 0.810",
  "[10:15:13] Mean AUC 0.873 (±0.003) — within governance tolerance",
];

export const shapWaterfall = [
  { feature: "DTI Ratio = 0.42", impact: +0.18 },
  { feature: "Credit Utilization = 78%", impact: +0.12 },
  { feature: "Months Since Delinquency = 4", impact: +0.09 },
  { feature: "Annual Income = $58k", impact: -0.07 },
  { feature: "Employment Tenure = 9y", impact: -0.11 },
  { feature: "LTV = 0.62", impact: +0.04 },
];

export const suggestedPrompts = [
  "Explain IFRS 9 Expected Credit Loss.",
  "Why did this model receive a compliance warning?",
  "Explain PD, LGD, and EAD.",
  "Summarize SS1/23 Principle 3.3.",
];
