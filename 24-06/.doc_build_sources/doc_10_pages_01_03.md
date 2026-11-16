# PART III — Screen-by-Screen Walkthrough

Each screen below points back to the relevant Part II deep-dive for full formula derivations; this Part focuses on what's on the specific screenshot, what to say, and what you'll be asked.

---

# PAGE 1 — Login

**A. What is visible:** Aegis Credit branding, a "Sign in" card (username/password fields, pre-filled example `harshadade33@gmail.com`), "Demo mode — enter any username and any password to sign in" caption, a "Welcome Back" panel with decorative stats (Model Registry "43 models", Validation "Active"), and a top bar reading "SYSTEMS OPERATIONAL" with a pulsing green dot.

**B. Purpose:** Gate entry to the app and assign a cosmetic identity for the session.

**C. User workflow:** Type anything in both fields → click Sign in → redirected to `/`.

**D. Frontend implementation:** `aegis-frontend/src/routes/login.tsx` + `aegis-frontend/src/lib/auth-context.tsx`. State: `AuthUser {name, username, role}` in a plain `useState`, no persistence layer.

**E. Backend implementation:** **None.** There is no `/login`, `/auth`, or `/token` endpoint anywhere in `main.py` — confirmed by full route inspection.

**F. Data flow:** Input (any username/password) → `login(username, password)` validates only "non-empty" → assigns a **random** role from `["Risk Validator","Model Risk Analyst","Credit Risk Manager","Model Governance Analyst"]` → cosmetic display-name derived by title-casing the username → sets in-memory `user` state → router navigates to `/`.

**G. Every important displayed value:**
- "Demo mode — enter any username and any password" — literal, accurate description of the code (**HARDCODED DEFAULT** — no validation exists).
- "SYSTEMS OPERATIONAL" — **DECORATIVE / ILLUSTRATIVE**. Always renders on this route; CSS `animate-pulse`, not a live health check. The backend does have a real `GET /health` endpoint, but the frontend never calls it.
- Background stats ("43 models", "0.937", "Active", "0.481") — **DECORATIVE / ILLUSTRATIVE**, explicitly documented in code as static brand texture, not live metrics.

**H. Dynamic vs static:** Everything on this page is either trivial client-side logic or decorative copy. Nothing here reads from the backend.

**I. Business/MRM interpretation:** This is a demo/POC authentication stub, not a production identity/access-control layer. In a real deployment this would need real SSO/IAM integration, role-based access control tied to actual MRM governance roles, and audit logging of who did what — none of which exists yet.

**J. What to say:** "This is a proof-of-concept — authentication here is a placeholder so we could focus engineering effort on the model risk workflow itself. Any production rollout would integrate real SSO and role-based access control before this ever handles real credit data."

**K. Likely questions:** "Is this connected to our SSO?" / "Who can see what?" / "Is this audited?"

**L. Answers:** "No — this is intentionally a demo login for the POC. There's no backend authentication, authorization, or audit trail yet; the session state doesn't even persist across a page refresh by design. This would be one of the first things built out for a production deployment."

**M. Risks/limitations:** No real security boundary exists. Do not present this screen as if any access control is enforced. The "SYSTEMS OPERATIONAL" badge should not be cited as evidence of a live monitoring/health-check system, since it's static.

---

# PAGE 2 — Workspace Selection ("Choose your workspace")

**A. What is visible:** Three workspace cards — Model Development (Workspace 01, "In Progress", 44 models / — accuracy / Data Upload stage), Model Validation (Workspace 02, "In Progress", 6 of 7 stages / 9 findings / REJECTED), Model Inventory (Workspace 03, "Active", 49 registered / 0 validated / 0 review due) — plus a connection status line "Connected to Aegis backend".

**B. Purpose:** Single entry point that reflects the live, current state of all three areas of the platform simultaneously.

**C. User workflow:** Click a workspace card → navigates into that pipeline's first screen.

**D. Frontend implementation:** **Correction from the source screenshot's apparent naming**: this is `aegis-frontend/src/routes/index.tsx` (route `/`, component `Landing`) — **not** `development.tsx`, which is a pure redirect stub to `/data-upload`.

**E. Backend implementation:** Three real calls on mount: `GET /model-inventory`, `GET /history/dev`, `GET /history/validation` (all in `main.py`).

**F. Data flow:** Input: none from the user. Processing: merges inventory JSON + two pipeline-log CSVs with in-memory/localStorage `DatasetProvider` context. Output: three summary cards.

**G. Every important displayed value:**
- **"44 models"** — `inventory.development.length`. **BACKEND RESPONSE**, verified against the live `model_inventory.json` file (44 entries).
- **ACCURACY (—)** — `trainingResult.evaluation_metrics.accuracy`, only populated after a real `/models/train` call **in this browser session**. Shows "—" if nothing has been trained yet this session, **regardless of the 44 registered models** — this widget is not backed by the inventory.
- **STAGE ("Data Upload")** — derived from 4 booleans (`profile`,`preprocessingResult`,`featureEngineeringResult`,`trainingResult`) in context; **FRONTEND-ONLY DISPLAY**.
- **"6 of 7 stages"** — 7-element boolean array over the 7 validation-stage context fields; total is hardcoded to 7 (array length), completed count is genuinely derived from context (localStorage-backed).
- **"9 findings" / "REJECTED"** — `validationStage8Result.total_count` / `.verdict`, from a real prior `POST /validation/stage8/findings` call. Verdict rule: **>2 HIGH-severity FAIL findings → REJECTED** (see §2.7.4).
- **"49 registered"** — `Math.max(models.length, development.length+validation.length)`; verified = 49 in the live data file.
- **"0 validated"** — a real string-match quirk: the live data's 5 "Under Validation" models don't match the substring `"validated"` (different word ending), so this correctly-computed count is 0 even though 5 models are actively mid-validation.
- **"0 review due"** — `next_validation_due` is null for every current row, so this is genuinely 0, not a bug.

**H. Dynamic vs static:** Inventory and history numbers are real backend data. The Model Development card's accuracy/stage indicators are session-local only (reset if localStorage is cleared or a different browser is used) and are **not** connected to the 44 registered models.

**I. Business/MRM interpretation:** This page is effectively a governance dashboard — it's the fastest way to show a Director "here's where every model in flight currently stands" without opening each workspace.

**J. What to say:** "This landing page pulls live counts from our model inventory and validation history logs every time it loads — the 44, 49, and REJECTED numbers you see are real, not mocked. The accuracy and pipeline-stage figures on the Development card reflect only what's been done in this browser session, since we don't yet have a persistent training-run database."

**K. Likely questions:** "Why does it say REJECTED?" / "Why is 'validated' showing 0 when 5 models are under validation?"

**L. Answers:** "REJECTED reflects our Stage 7 verdict rule — more than 2 unresolved HIGH-severity findings triggers automatic rejection, which is what happened on the most recent Stage 7 run. The '0 validated' count is a strict string match on the status field — 'Under Validation' doesn't count as 'Validated' by design, since validation isn't complete yet; those 5 will move into the validated count once their Stage 7 verdict is APPROVED."

**M. Risks/limitations:** The Development card's live-looking stats can mislead a viewer into thinking they reflect the whole inventory — they don't; they're purely this browser's local session state.

---

# PAGE 3 — Dashboard

**A. What is visible:** Portfolio Overview banner, four KPI cards (Total Models 49, Active Validations 1, Compliance Score 61.8%, Portfolio Risk Rating —), Validation Completion Trend chart, Model Health Radar ("Train and evaluate a model to populate this scorecard"), Model Performance Comparison ("No model metrics are available"), Recent Activity list, Model Portfolio table.

**B. Purpose:** Operational overview of model portfolio health, validation progress, and governance risk posture.

**C. User workflow:** Read-only page; no primary actions beyond navigation.

**D. Frontend implementation:** `aegis-frontend/src/routes/dashboard.tsx`.

**E. Backend implementation:** Same three calls as the Landing page (`GET /model-inventory`, `/history/dev`, `/history/validation`) — `GET /history/latest` is **not** used on this specific page.

**F. Data flow:** Backend inventory/history feed the top KPIs, trend chart, activity feed, and portfolio table. The Health Radar and Performance Comparison widgets read **only** from `trainingResult` in local session context — completely independent of the inventory data.

**G. Every important displayed value:**
- **Total Models (49)** — same formula as Page 2. **BACKEND RESPONSE.**
- **Active Validations (1)** — count of inventory rows whose status contains "in review"/"due review"/"pending"/"draft"; in the live data, the single "Draft" row matches. **BACKEND RESPONSE**, but a **different string-match rule** than Page 2's "validated" count — don't conflate the two.
- **Compliance Score (61.8%)** — **a hardcoded lookup table**, keyed on `validationStage8Result.verdict`: REJECTED→61.8%, CONDITIONALLY APPROVED→86.4%, APPROVED→94.2% (all **HARDCODED DEFAULT**). Only falls back to a genuinely computed pass-ratio if no Stage 8 verdict exists yet.
- **Portfolio Risk Rating (—)** — a real weighted-average formula over `model_risk_rating` fields (Low=1/Moderate=2/High=3/Critical=4, mapped to letter grades A/B/B+/C), showing "—" specifically because that field is blank across the live inventory data (**DATA-DERIVED**, currently empty).
- **Validation Completion Trend** — real chart from the merged history-log CSVs, bucketed by calendar month; "completed" vs "in progress" classified by a keyword match on the log-entry's stage name (a simple heuristic, not a formal taxonomy).
- **Model Health Radar / Performance Comparison** — both read `trainingResult.evaluation_metrics` from session-local context only; empty-state text shows whenever nothing has been trained this session, **regardless of how many models exist in the inventory**. Note the radar's "Compliance" axis is actually plotting **PR-AUC**, relabeled.
- **Recent Activity** — top 5 rows of the same merged history feed; color-coding is a crude keyword scan (`warn`/`fail`/`error`) over the JSON summary blob — a REJECTED verdict entry would render with the neutral/green dot unless its summary text happens to contain one of those three words, which it typically won't (a UI gap worth being aware of, not something to volunteer unprompted).
- **Model Portfolio table** — first 4 rows of the real inventory `models[]` array; "IN DEVELOPMENT" is just the stored string `"In Development"` rendered in CSS uppercase — not a different underlying value.

**H. Dynamic vs static:** Top-row KPIs and the two feed-driven widgets (trend, activity, portfolio table) are real backend data. Health Radar and Performance Comparison are session-local and can look "empty" even with a populated inventory.

**I. Business/MRM interpretation:** A genuinely useful governance rollup where it's backend-fed, but the Compliance Score's hardcoded lookup table means it should be described as "an indicative banding tied to the validation verdict," not "a live computed compliance percentage."

**J. What to say:** "The top KPIs and the activity/trend/portfolio widgets pull real data from our inventory and pipeline logs. The Compliance Score is a fixed banding we assign per verdict tier — REJECTED models show 61.8%, not because of 61.8 individual passing checks, but as a standard indicative score for that governance outcome."

**K. Likely questions:** "Where does 61.8% actually come from?" / "Why is the risk-rating radar empty when we have 49 models?"

**L. Answers:** "It's a fixed value we display for any REJECTED verdict — think of it as a categorical banding rather than a literal percentage-of-checks-passed. The radar chart is scoped to models trained in the current session, not the full registered inventory — it's a live-training scorecard, not a portfolio-wide view; that's a good enhancement opportunity if we want portfolio-wide model health here."

**M. Risks/limitations:** Do not describe the Compliance Score as computed from real check counts — it is a lookup table. Do not describe the Health Radar/Performance Comparison as reflecting the whole 49-model portfolio.

---
