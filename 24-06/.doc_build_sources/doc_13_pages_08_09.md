# PAGE 8 — Model Training & Evaluation: Model Training tab (pre-training state)

**A. What is visible:** Total Samples/Features/Imbalance KPIs, a 5-step Model Development Pipeline stepper, "Recommended Model: LightGBM" card with reasons, a Model Selection comparison list (Logistic Regression / Random Forest / XGBoost / LightGBM selected / Gradient Boosting, all "Not evaluated"), a "Credit Risk Evaluation Strategy" panel (Primary Target: Recall, ROC-AUC/PR-AUC/F1 tiles, Risk Signals, Model Cost Tradeoff), and two proceed options ("Compare models first" / "Configure & train").

**B. Purpose:** Recommend and configure the classification model before any real training runs.

**C. User workflow:** Review the recommended model and its stated reasons → optionally compare a few candidates first → configure training options → train.

**D. Frontend implementation:** `aegis-frontend/src/routes/model-training-evaluation.tsx` (Training tab). Full deep dive: **§2.4.1–2.4.3**.

**E. Backend implementation:** `POST /models/recommend` (`main.py:2605-2678`) → `24-06/model_selector.py`.

**F. Data flow:** `profile`+`file`+FE choices → internal hardcoded 0.15/0.15/42 split (independent of the reviewer's actual Preprocessing split) → `compute_dataset_characteristics()` on the post-FE train split → weighted scoring across 5 candidates → winner + top-4 reasons returned.

**G. Every important displayed value:**
- **"LightGBM" recommendation** — winner of a **weighted linear scoring formula** across 9 dataset characteristics × 9 global weights × per-model affinity coefficients (all HARDCODED tables) — not a simple if/else. LightGBM's affinity for `size` (0.9) and `dimensionality` (0.8) is the highest of all 5 candidates, which is concretely why it tends to win on larger/wider datasets.
- **Total Samples/Features/Imbalance** — real numbers from the `/models/recommend` response's `training` block, computed on the post-feature-engineering training split.
- **"Primary Target: Recall"** and all 4 "Risk Signals" checkmarks — **HARDCODED COPY**, not derived from any live config or backend field. The one exception worth noting: the auto-threshold algorithm actually optimizes **F1**, not recall — so "Recall-first threshold" is a label mismatch versus the real algorithm (§2.4.4).
- **Model Cost Tradeoff (FN "Very High" / FP "Low")** — **HARDCODED COPY**, no relative-cost computation exists anywhere in the codebase.

**H. Dynamic vs static:** The recommendation itself and the 3 metric tiles (once available) are real computations. The entire "Credit Risk Evaluation Strategy" panel is mostly fixed narrative text layered on top of a few real numbers — verified line by line in §2.4.3.

**I. Business/MRM interpretation:** The recommendation engine is a legitimate, explainable multi-factor scoring system — a genuine strength to present. The static narrative panel, however, should not be quoted to a Director as if every checkmark reflects a live validated condition.

**J. What to say:** "The model recommendation is a real weighted scoring formula across nine dataset characteristics, not a simple rule of thumb — I can show the exact reasons it gave for this dataset. The panel below it is mostly explanatory framing for the credit-risk context; the live numbers in it are the three metric tiles, everything else is fixed guidance text."

**K. Likely questions:** "Why LightGBM and not XGBoost?" / "Are we actually optimizing for recall?"

**L. Answers:** "Both score well on this kind of large, imbalanced, moderately non-linear dataset, but LightGBM's leaf-wise growth gives it a structural edge on training speed and scalability that the scoring formula weights slightly higher. On the threshold question — the panel's language says 'recall-first,' but the actual algorithm that picks the decision threshold optimizes F1, the balance of precision and recall, across 99 candidate cutoffs; that's a labeling nuance I'd recommend we tighten up in the UI."

**M. Risks/limitations:** Do not present the "Risk Signals" checkmarks as live-validated conditions for the current run — they render unconditionally.

---

# PAGE 9 — Model Training & Evaluation: Model Training tab (post-training state)

**A. What is visible:** Same layout as Page 8, now showing "Trained" status, real evaluation metrics summary, Class balancing/CV/OOT configuration cards (with values entered), Decision Threshold slider showing "0.62 (auto)", advanced hyperparameter sliders, a training summary, and an "Excel-free QC Validation" style dataset check block.

**B. Purpose:** Show the configured, completed training run and its immediate summary before moving to full Evaluation.

**C. User workflow:** Review configuration actually used → inspect the auto-selected threshold → proceed to Evaluation.

**D. Frontend implementation:** Same file/tab as Page 8, post-`trainingResult` state.

**E. Backend implementation:** `POST /models/train` (`main.py:2681`+) → `24-06/train_new.py` (`train_model`, `split_data`, `compute_split_stats`).

**F. Data flow:** Real `.fit()` call on the training split, with `compute_sample_weight("balanced", ...)` applied unconditionally for class balancing; optional CV (`StratifiedKFold`+`cross_val_score`), optional `RandomizedSearchCV` hyperopt (`n_iter=8`, `cv=3`, both hardcoded and not user-configurable), optional OOT carve-off scored once after final fit; auto-threshold selection via the 99-point F1 sweep.

**G. Every important displayed value:**
- **"0.62 (auto)" decision threshold** — the F1-maximizing point on `np.linspace(0.01,0.99,99)` (**HARDCODED grid**, only F1 is supported as the optimization metric, not recall).
- **Class Weight: "Automatic (balanced)"** — accurate; `compute_sample_weight("balanced", y_dev)` is applied unconditionally to every classification run, with no on/off toggle in the UI.
- **`scale_pos_weight`** — present in the backend API but **effectively dead on this screen**: default 1.0, never overridden by the frontend, and its `>1` injection gate never fires as a result. Real imbalance handling is entirely the `compute_sample_weight` mechanism above.
- **Cross-Validation / Hyperparameter Tuning / OOT toggles** — real, reviewer-controlled; CV uses `StratifiedKFold`, hyperopt uses `RandomizedSearchCV(n_iter=8)`, OOT targets 15% of dated rows (clamped 10–20%, min 100 rows, requires ≥50 dated rows to attempt at all — all HARDCODED).

**H. Dynamic vs static:** The trained metrics and threshold are real. The class-balancing mechanism (`compute_sample_weight`) is always-on and correctly labeled; `scale_pos_weight`'s presence in the API is legacy/vestigial.

**I. Business/MRM interpretation:** The auto-threshold-selection transparency (showing exactly what cutoff was used and how it was chosen) is a genuine governance strength — it removes ambiguity about "what does 'the model' actually predict" that a Director/regulator would otherwise have to ask about separately.

**J. What to say:** "The 0.62 you see here isn't arbitrary — it's the threshold, out of 99 evenly-spaced candidates from 0.01 to 0.99, that maximizes F1 on this model's validation performance. Class imbalance is handled automatically on every run via balanced sample weighting — there's no toggle to turn that off, and it applies uniformly across all five candidate model types."

**K. Likely questions:** "Can we change the threshold manually?" / "Does hyperparameter tuning use a proper cross-validated search?"

**L. Answers:** "Yes — there's a manual override toggle if a reviewer wants to set a business-driven cutoff instead of the F1-optimal one. Hyperparameter tuning uses scikit-learn's RandomizedSearchCV with 8 sampled parameter combinations across a 3-fold cross-validation — it's real cross-validated search, though the iteration count and fold count are currently fixed in code rather than reviewer-configurable."

**M. Risks/limitations:** If asked specifically about `scale_pos_weight`, be accurate that it exists in the API surface but doesn't currently affect training outcomes from this screen — the real mechanism is the sample-weight balancing.

---
