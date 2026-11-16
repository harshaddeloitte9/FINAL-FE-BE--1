# PAGES 30–32 — Model Validation: Stage 1, Stage 6 (tab 2), Stage 7

Full deep dive: **§2.6.1, §2.7.3, §2.7.4**.

---

## PAGE 30 — Validation Stage 1: Intake & Governance

**A. Visible:** Artifacts Submitted 2/7, Governance Status "Pending"/demo-only status, Model Metadata "Complete" for demo metadata, Submission Readiness "Not Ready" for a demo without registry evidence, a Demo mode selector (Demo A/Demo B), Model Profile form, Risk Tier "Tier 2 — Medium Risk" in the current live demo snapshot, Target definition (demo default flag and sample size derived from the shipped CSV), Artifact Inventory (2 demo artifacts loaded), Extracted MDD Metrics, Regulatory Frameworks checkboxes (IFRS 9, SS1/23, RBI), Governance attestation checklist.

**B. Purpose:** Stage 1 in Model Validation captures the model-under-review metadata and the developer-reported metrics, but the demo submission is intentionally separate from the Model Development registry and not a production governance approval.

**D/E.** `aegis-frontend/src/routes/validation.intake.tsx` → `GET /validation/intake`, `POST /validation/intake/draft`, `POST /validation/parse-mdd`, `POST /validation/tier`.

**G. Values — the correct demo-mode behavior is intentionally independent validation-only:**
- **Demo A and Demo B each load a shipped demo CSV plus its accompanying MDD text** from `demo_data/*.csv` and `demo_data/*_mdd.txt` rather than a registered Development model. The demo run is explicitly `registered_model_id = None`, `model_inventory_registered = False`, and `independence_confirmed = False` in the live implementation.
- **Developer-reported metrics are kept separate from server-computed metrics by design.** The Stage 1 MDD values are metadata/reference values. The validation replication checks compare those reference figures against the actual replications computed from the raw demo data; they are not replacing the calculation engine with a static demo result.
- **"Artifacts Submitted 2/7"** is a local frontend counter over 7 upload booleans; demo mode only ever populates 2 of them (dataset + MDD) — this is why demo mode always shows 2/7 regardless of which demo is selected.
- **The live demo status is intentionally unregistered and not final-approval evidence.** Any older wording that described Demo B as "Governance Status: Complete" or "Tier 1 — High Risk" was stale documentation and does not reflect the current code.
- **Risk Tier** on this screen is read from the live intake snapshot (`Tier 2 — Medium Risk` in the current implementation), not treated as a registered-model inventory classification. A separate `/validation/tier` endpoint exists for a real tiering computation via Agent2, but it does not create a registered-model status in demo mode.
- **Regulatory Frameworks**: exactly 3 checkboxes exist (IFRS 9, SS1/23, RBI); **there is no SS11/13 option anywhere** — this single fact is the root cause of Stage 2's "2/4" RAG-rule count.

**I.** This screen's honest framing matters a lot for a governance audience: the demo flow exists to let a reviewer see what a full validation submission looks like without requiring a registered Development model first. The live state is intentionally independent-validation-only and not a real governance approval.

**J.** "For a real submission, the MDD parsing is a genuine deterministic text extractor — not an LLM, a straightforward regex-based reader of the document. The demo mode you're seeing here is a deliberately standalone validation example: it uses the shipped demo data and the demo MDD text, never a registered Development model, and never a final-approval claim."

**K/L.** "Is the demo governance status actually verified?" → "No — the demo route is intentionally unregistered and not a final-approval evidence path. In a real submission, the reviewer would need to complete valid governance and model-inventory evidence before any status can be claimed as complete."

**M.** Do not present the demo submission as a registered, approved model or as final evidence. It is a standalone Model Validation demonstration, clearly marked as unregistered and not eligible for final approval.

---

## PAGE 31 — Validation Stage 6: Regulatory Compliance tab

**A. Visible:** Checks 7.1–7.10: Calibrated PD Output Produced FAIL, IFRS 9 Stage 1/2/3 Classification Implemented FAIL, SICR Detection Criteria Documented FAIL, Lifetime ECL for Stage 2/3 Computed FAIL, Governance Controls Match Risk Tier PENDING, Post-Model Overlays Governed PENDING.

**G. Values — genuinely different mechanism from Stage 2's RAG+LLM checks: all of 7.1–7.10 here are deterministic; none call an LLM.** 7.1–7.4 are pure keyword-match-against-MDD-text checks (e.g., 7.1 looks for `"calibrat"`, `"platt"`, `"isotonic"`, `"through the cycle"`, `"ttc"` anywhere in the MDD text). **7.9 and 7.10 are PENDING because they are literal, hardcoded stubs** — the code's own returned text states plainly: *"Manual validation required — not yet automated... This check requires manual review by the validator."* This is not a computation that came back inconclusive; the platform explicitly does not attempt to automate these two (and 4 others, 7.5–7.8, all similarly stubbed).

**I.** This screen should be presented as "automated documentation screening for IFRS 9-specific technical requirements," clearly distinct from a full regulatory sign-off — six of the ten checks (7.5–7.10) are honestly marked as requiring manual validator review rather than falsely claiming automation.

**J.** "These four FAILs are genuinely automated keyword checks against the uploaded MDD text — the model documentation doesn't currently use the specific language these IFRS 9 requirements look for. The two PENDING items further down aren't a computation gap — the platform explicitly flags those as requiring a human validator, by design."

**K/L.** "Why do PD calibration and IFRS 9 staging all fail?" → "These are checking whether the MDD text explicitly documents calibration methodology, staging criteria, SICR triggers, and lifetime ECL methodology in the specific language these checks look for — a FAIL here typically means the documentation needs to be more explicit about these IFRS 9 mechanics, not necessarily that the underlying model doesn't do any of this. It's a documentation-completeness signal."

**M.** Be careful not to claim these checks assess whether the *model* actually does calibration/staging correctly — they only assess whether the *documentation* mentions it, via keyword search.

---

## PAGE 32 — Validation Stage 7: Findings & Final Validation Report

**A. Visible:** Executive Overview (Verdict: REJECTED, 7 MDD findings, 2 Warnings, 9 total Findings), verdict reasoning text, Model Identity, Findings Summary grouped by stage, Remediation Action Log, Performance Metrics vs Regulatory Threshold, Monitoring & Revalidation Recommendations, Executive Summary text block, Evidence Pack downloads, Sign-off section.

**B. Purpose:** Aggregate every prior stage's findings into one governance verdict and a presentable final report.

**D/E.** `aegis-frontend/src/routes/validation.findings.tsx` → `POST /validation/stage8/findings`.

**G. Values — the aggregation logic has two structurally dead branches you should know about, not just the live rule:**
- Findings are aggregated from **Stages 1, 2, and 6** in the current build. **Stage 3's finding (stated-vs-replicated AUC gap >0.05) and Stage 5's finding (manual shock causing >50% PD change) are both structurally unreachable** given how the current frontend populates this request — they require form fields (`stated_auc`, `shock_result_json`) that the relevant pages never actually send (confirmed by grep — zero matches). **Stage 4's finding is reachable and real**, conditional on the model's actual replicated numbers (ROC-AUC<0.70, Recall<0.60, Gini<0.40, Brier>0.25, or replicated AUC underperforming the benchmark by >0.02).
- **Verdict rule** (HARDCODED, this is the authoritative one for this UI page — a *separate*, similar-but-not-identical verdict engine exists elsewhere in the codebase and is unused by this screen, so don't conflate the two if asked to be precise): `0 HIGH findings & ≤2 MEDIUM → APPROVED`; `≤2 HIGH findings → CONDITIONALLY APPROVED`; `>2 HIGH findings → REJECTED`.
- **Monitoring frequency and revalidation trigger are a hardcoded lookup table keyed on `model_tier`** (Tier 1/High → Monthly monitoring, "Annual or PSI>0.25 or AUC drop>0.05" trigger; Tier 2/Medium → Quarterly, 18-monthly; else → Semi-annual, 2-year) — **not computed from this specific model's actual PSI/AUC drift.**
- **The Executive Summary and verdict-reasoning text are 100% frontend JavaScript template strings, plugging real numbers into fixed sentence templates — there is no LLM call anywhere on this page.** The Executive Summary textarea is pre-filled but reviewer-editable before sign-off/export.

**I.** The verdict-threshold logic (>2 HIGH findings → REJECTED) is a clean, auditable, code-defined governance rule — a genuine strength to highlight. The two structurally-unreachable finding categories (Stages 3 and 5) are worth disclosing proactively as a known gap, since a careful reviewer could otherwise assume those checks are silently passing when they in fact never run.

**J.** "This screen pulls a single, code-defined verdict rule — more than two unresolved HIGH findings automatically means REJECTED — from a real aggregation of Stage 1, 2, and 6 findings. I want to flag one honest gap: two of the potential finding categories, tied to Stages 3 and 5, currently can't fire at all due to a data-plumbing gap between those pages and this one — that's on our near-term fix list, not a silent false pass being presented as clean."

**K/L.** "Does a REJECTED verdict here mean the model definitely can't be used?" → "Per our own coded rule, yes — more than 2 unresolved HIGH-severity findings is a hard rejection requiring remediation and resubmission, not something that can be conditionally waived past that threshold in the current logic." / "Is the executive summary written by AI?" → "No — it's assembled from a fixed template using the real numbers from this run; a human validator reviews and can edit it before it's finalized and signed off."

**M.** Proactively disclose the Stage 3/5 finding-reachability gap rather than waiting to be asked — it's the kind of thing that looks much worse discovered later than raised upfront.

---
