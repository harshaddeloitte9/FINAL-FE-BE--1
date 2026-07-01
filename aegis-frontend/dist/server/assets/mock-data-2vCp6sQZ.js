//#region src/lib/mock-data.ts
var rocCurve = Array.from({ length: 21 }, (_, i) => {
	const fpr = i / 20;
	const tpr = Math.min(1, Math.pow(fpr, .35) + .02);
	return {
		fpr: +fpr.toFixed(2),
		tpr: +tpr.toFixed(3),
		diagonal: +fpr.toFixed(2)
	};
});
var prCurve = Array.from({ length: 21 }, (_, i) => {
	const r = i / 20;
	const p = Math.max(.4, .98 - Math.pow(r, 1.6));
	return {
		recall: +r.toFixed(2),
		precision: +p.toFixed(3)
	};
});
var scoreDistribution = Array.from({ length: 20 }, (_, i) => ({
	bin: `${(i * 5).toString().padStart(2, "0")}`,
	good: Math.round(80 * Math.exp(-Math.pow((i - 4) / 4, 2))) + 5,
	bad: Math.round(60 * Math.exp(-Math.pow((i - 14) / 4, 2))) + 3
}));
var featureImportance = [
	{
		feature: "DTI Ratio",
		value: .21
	},
	{
		feature: "Credit Utilization",
		value: .17
	},
	{
		feature: "Months Since Delinquency",
		value: .14
	},
	{
		feature: "Annual Income (log)",
		value: .11
	},
	{
		feature: "Loan-to-Value",
		value: .09
	},
	{
		feature: "Employment Tenure",
		value: .07
	},
	{
		feature: "Number of Open Trades",
		value: .06
	},
	{
		feature: "Revolving Balance",
		value: .05
	},
	{
		feature: "Mortgage Status",
		value: .04
	},
	{
		feature: "Region Risk Index",
		value: .03
	}
];
var correlationFeatures = [
	"DTI",
	"Util.",
	"Income",
	"LTV",
	"Tenure",
	"Trades",
	"Bal.",
	"Region"
];
correlationFeatures.map((_, i) => correlationFeatures.map((_, j) => {
	if (i === j) return 1;
	return +(Math.sin(i * 13 + j * 7) * .5 + Math.sin(i + j) * .2).toFixed(2);
}));
var regulatoryChecks = [
	{
		framework: "IFRS 9",
		rules: [
			{
				id: "IFRS9-1",
				title: "ECL staging definitions",
				status: "PASS",
				severity: "Low"
			},
			{
				id: "IFRS9-2",
				title: "12-month vs lifetime ECL transition",
				status: "PASS",
				severity: "Low"
			},
			{
				id: "IFRS9-3",
				title: "Forward-looking macroeconomic overlay",
				status: "WARNING",
				severity: "Medium",
				detail: "Macroeconomic scenario weights have not been refreshed in the last 90 days.",
				remediation: "Refresh GDP/Unemployment scenario weights and re-run ECL stage 2 cohort."
			},
			{
				id: "IFRS9-4",
				title: "SICR threshold calibration",
				status: "PASS",
				severity: "Low"
			}
		]
	},
	{
		framework: "IFRS 7",
		rules: [{
			id: "IFRS7-1",
			title: "Credit risk disclosure granularity",
			status: "PASS",
			severity: "Low"
		}, {
			id: "IFRS7-2",
			title: "Concentration risk reporting",
			status: "WARNING",
			severity: "Medium",
			detail: "Top-10 obligor exposure exceeds 18% — disclosure narrative required.",
			remediation: "Append concentration commentary to Pillar 3 appendix."
		}]
	},
	{
		framework: "SS1/23 (PRA)",
		rules: [
			{
				id: "SS123-3.3",
				title: "Model tiering & governance ownership",
				status: "PASS",
				severity: "Low"
			},
			{
				id: "SS123-4.1",
				title: "Independent validation evidence",
				status: "FAIL",
				severity: "High",
				detail: "Challenger model benchmarks missing for the last quarterly cycle.",
				remediation: "Run Ridge + LightGBM challenger benchmarks and attach evidence pack."
			},
			{
				id: "SS123-5.2",
				title: "Ongoing monitoring frequency",
				status: "PASS",
				severity: "Low"
			}
		]
	}
];
var shapWaterfall = [
	{
		feature: "DTI Ratio = 0.42",
		impact: .18
	},
	{
		feature: "Credit Utilization = 78%",
		impact: .12
	},
	{
		feature: "Months Since Delinquency = 4",
		impact: .09
	},
	{
		feature: "Annual Income = $58k",
		impact: -.07
	},
	{
		feature: "Employment Tenure = 9y",
		impact: -.11
	},
	{
		feature: "LTV = 0.62",
		impact: .04
	}
];
var suggestedPrompts = [
	"Explain IFRS 9 Expected Credit Loss.",
	"Why did this model receive a compliance warning?",
	"Explain PD, LGD, and EAD.",
	"Summarize SS1/23 Principle 3.3."
];
//#endregion
export { scoreDistribution as a, rocCurve as i, prCurve as n, shapWaterfall as o, regulatoryChecks as r, suggestedPrompts as s, featureImportance as t };
