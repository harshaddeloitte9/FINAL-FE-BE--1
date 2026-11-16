# 2.4 Model Training & Evaluation

**Frontend:** `aegis-frontend/src/routes/model-training-evaluation.tsx` (3,124 lines, two tabs).
**Live backend modules (confirmed via import graph):** `24-06/model_selector.py`, `24-06/train_new.py`, `24-06/evaluate_new.py`. **`train.py`/`evaluate.py` are dead code** for this screen — only imported by the unrelated Streamlit prototype `app_new.py` and one-off comparison scripts, never by `main.py`.

## 2.4.1 Model recommendation — a weighted scoring formula, not an if/else

`model_selector.py` implements:
```
score(model) = Σ over 9 characteristics c:  GLOBAL_WEIGHT[c] × MODEL_AFFINITY[model][c] × VALUE[c]
```
- **9 characteristics**, **GLOBAL_WEIGHTS** summing to 1.0 (HARDCODED): size 0.14, dimensionality 0.10, missingness 0.12, imbalance 0.14, categorical 0.10, multicollinearity 0.12, nonlinearity 0.14, explainability 0.08, speed 0.06.
- **MODEL_AFFINITY**: per-model coefficients in [-1,1] for how well each model handles a HIGH value of each characteristic (HARDCODED table). LightGBM has the highest affinity for size (0.9) and dimensionality (0.8) of all 5 candidates — this is the concrete reason it tends to win on large/wide datasets.
- **VALUE[c]** is measured on the actual post-feature-engineering training split — e.g. `imbalance_score = saturate(majority/minority ratio − 1.0, cap=9.0)` (a 10:1 ratio saturates to 1.0); `multicollinearity_pct` = share of numeric-pair correlations `>0.8` (HARDCODED); `nonlinearity_score` compares mutual information to linear correlation.
- **No single hard cutoff** like "n>1000 → LightGBM" exists — it's a continuous weighted score; the winner is simply `argmax(score)` across the 5 candidates, and only the winner + its top-4 reason strings are returned (runner-up scores are computed but never exposed).
- `/models/recommend` measures characteristics on an **internal, hardcoded `test_size=0.15, val_size=0.15, random_state=42` split** (`main.py:2631`) — independent of whatever split the reviewer set on the Preprocessing screen.

## 2.4.2 Training configuration

- **Split**: read-only on this screen, inherited from Preprocessing (`test_size`/`val_size`/`random_seed`, default 0.15/0.15/42).
- **Class balancing — always on, no toggle exists in the UI.** `train_new.py:308-325`: `sklearn.utils.class_weight.compute_sample_weight("balanced", y_dev)` is applied unconditionally to every binary/multiclass training run (plain fit, hyperopt fit, and CV folds alike). If an estimator's `.fit()` doesn't accept `sample_weight` (e.g. KNN), it catches the `TypeError` and falls back to unweighted fit, recording that in `training_info.class_weighting.reason` — **not silent**.
- **`scale_pos_weight` is effectively dead code on this screen.** Its `Form(...)` default is `1.0`; the frontend never sends a different value (confirmed by grep); the injection condition requires `>1`, so it never fires. Real imbalance handling is the `compute_sample_weight` mechanism above, for **all 5 model types**, not just XGBoost.
- **Cross-validation**: reviewer toggle, `StratifiedKFold(n_splits=cv_folds)` + `cross_val_score` on development data only (post-OOT carve-off).
- **Hyperparameter tuning**: reviewer toggle (on/off only, no config exposed) → `RandomizedSearchCV(n_iter=8, cv=3)` (both HARDCODED, not configurable via UI).
- **Out-of-Time (OOT) validation**: reviewer toggle + date column. Window sizing targets 15% of dated rows, clamped to [10%, 20%], never below 100 absolute rows (all HARDCODED). Requires ≥50 parseable dates or OOT is skipped entirely. Scored exactly once after final fit — never re-fit/tuned against it.

## 2.4.3 "Credit Risk Evaluation Strategy" panel — mostly static narrative, verified line by line

| Element | Verdict |
|---|---|
| "Primary Target: Recall" headline | **HARDCODED COPY** — no config or backend field drives this |
| ROC-AUC / PR-AUC / F1 tiles | Real, from `trainingResult.evaluation_metrics` |
| "⚠ Class imbalance X:1" | Real ratio; but the `>1.5` warning cutoff is a **HARDCODED THRESHOLD** with no backend equivalent |
| "✓ Recall-first threshold" | **HARDCODED COPY, and inaccurate** — the actual auto-threshold algorithm optimizes F1, not recall (see §2.4.4) |
| "✓ Class weights applied" | HARDCODED COPY (happens to be true in practice, but not actually checked against the real `training_info.class_weighting.applied` flag) |
| "✓ F1 threshold optimized" / manual override | Real UI toggle state, correctly labeled |
| Cost-tradeoff badges (FN "Very High" / FP "Low") | **HARDCODED COPY** — no relative-cost computation exists anywhere |
| "We optimize for: ROC-AUC → Recall → PR-AUC → F1" | **HARDCODED COPY** — this priority ordering doesn't exist in any backend code |

## 2.4.4 Decision threshold auto-selection — exact algorithm

`select_best_threshold()` (`evaluate_new.py:68-112`):
```
_THRESHOLD_GRID = np.linspace(0.01, 0.99, 99)     # 99 candidates, HARDCODED
for each candidate t:  y_pred = (score ≥ t);  compute precision/recall/F1
pick the t with the HIGHEST F1  (only F1 is supported — NOT recall)
tie-break: first (i.e. lowest) threshold reached wins ties → slight recall bias on plateaus
```
This exact grid is reused by the Threshold Analysis chart, guaranteeing the marked "Best F1" point matches the reported `threshold_used` by construction. The frontend's "99 candidates swept from 0.01 to 0.99" copy is a **hardcoded string** that happens to match — if the backend grid ever changed, this text would go stale silently (no `n_candidates` field is returned for the frontend to read instead).

## 2.4.5 All nine Evaluation metrics/charts — formula, function, threshold

| Metric/Chart | Formula / Method | Function | Threshold |
|---|---|---|---|
| **Accuracy** | Correct predictions / total, at resolved threshold | `sklearn.accuracy_score` | — |
| **Precision** | TP/(TP+FP) | `sklearn.precision_score` | — |
| **Recall** | TP/(TP+FN) | `sklearn.recall_score` | — |
| **F1** | Harmonic mean of precision & recall | `sklearn.f1_score` | — |
| **ROC-AUC** | Area under ROC curve, on continuous scores | `sklearn.roc_auc_score` | — |
| **PR-AUC** | Area under Precision-Recall curve | `sklearn.average_precision_score` | — |
| **KS statistic** | Max separation between cumulative score distributions of the two classes | `scipy.stats.ks_2samp(pos_scores, neg_scores).statistic` | — |
| **Brier score** | Mean squared error of predicted probability vs actual outcome | `sklearn.brier_score_loss` | — |
| **Confusion Matrix** | TN/FP/FN/TP at resolved threshold | `sklearn.confusion_matrix` | Threshold = auto (F1-optimal) or manual |
| **Specificity/Sensitivity/False-Alarm/Miss Rate** | `TN/(TN+FP)`, `TP/(TP+FN)`, `FP/(FP+TN)`, `FN/(FN+TP)` | **Computed in the frontend (JavaScript)**, not a backend field | — |
| **Threshold Analysis** | Precision/Recall/F1 swept across the same 99-point grid | `compute_threshold_analysis` | — |
| **Score Distribution** | Predicted-probability histogram by actual class, real held-out predictions, **40 bins** (HARDCODED) | `compute_score_distribution` | — |
| **Gain & Lift** | 10 deciles (HARDCODED); cumulative gain = % of positives captured; lift = cum_gain / cum_pct_population | `compute_gain_chart`/`compute_lift_chart` | — |
| **Residuals / Heteroscedasticity** | Spearman corr(score, \|residual\|) + variance ratio across 5 quantile bins (HARDCODED) | `compute_heteroscedasticity_check` | Flag if `\|Spearman\|>0.35 OR variance_ratio>4` (HARDCODED); needs ≥25 rows or returns "Not enough data" |
| **Temporal Stability** | Actual vs. predicted default rate by period (Monthly/Quarterly/Yearly, default Quarterly) | `compute_temporal_analysis_bundle` | A period is "flagged" if `\|actual−predicted\|>5pp` (HARDCODED `gap_threshold=0.05`) |
| **Classification Report** | Per-class precision/recall/f1/support + macro/weighted avg | `sklearn.classification_report(output_dict=True)` | — |

The residuals-tab color thresholds (>0.85 amber, >0.4 blue) are **cosmetic frontend-only**, unrelated to the backend's 0.35/4× statistical flag.

## 2.4.6 What each metric means for a Director (plain language)

- **Accuracy** — % of all predictions correct. Misleading alone on an imbalanced portfolio (a model predicting "no default" for everyone can still score high accuracy).
- **Precision** — of everyone the model flagged as a default risk, what fraction actually defaulted. High precision = few false alarms.
- **Recall (Sensitivity)** — of everyone who actually defaulted, what fraction the model caught. In credit risk this usually matters more than precision: a missed default is typically costlier than a false alarm.
- **F1** — balances precision and recall into one number; this is what the platform's auto-threshold actually optimizes.
- **ROC-AUC** — probability the model ranks a random defaulter above a random non-defaulter; a single number for overall discriminative power, threshold-independent.
- **Gini = 2×AUC−1** — the same discriminative power expressed on a familiar credit-risk scale.
- **KS statistic** — the maximum gap between the cumulative good/bad distributions; a classic credit-scoring separation metric regulators recognize.
- **Brier score** — how well-calibrated the predicted probabilities are (lower is better); a model can rank well (high AUC) but still be poorly calibrated.
- **PR-AUC** — like ROC-AUC but more informative on imbalanced portfolios, since it focuses on the minority (default) class.

---
