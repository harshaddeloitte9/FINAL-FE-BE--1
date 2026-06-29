# 🏦 CreditRisk ML POC — Adaptive Machine Learning Platform

A fully adaptive, production-style machine learning application for Credit Risk / Binary Classification workflows, built with Python and Streamlit.

**No hardcoded column names. Works with any structured CSV or Excel dataset.**

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Backend API
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open in Browser
- FastAPI docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

---

## 📁 Project Structure

```
credit_risk_poc/
├── app.py                  # Main Streamlit UI & workflow router
├── preprocessing.py        # Adaptive preprocessing pipeline engine
├── feature_engineering.py  # Auto feature analysis & transformation
├── model_selector.py       # Smart model recommendation registry
├── train.py                # Data splitting, SMOTE, pipeline training
├── evaluate.py             # Credit-risk metrics & Plotly charts
├── explainability.py       # SHAP values & prediction reasoning
├── utils.py                # Helpers: synthetic data, type detection, downloads
└── requirements.txt        # Python dependencies
```

---

## 🔄 Workflow (8 Steps)

| Step | Description |
|------|-------------|
| 1 | **Data Upload** — CSV/XLSX upload or synthetic dataset generation |
| 2 | **Data Profiling** — Schema detection, missing values, class distribution |
| 3 | **Preprocessing** — Adaptive imputation, scaling, encoding via sklearn Pipeline |
| 4 | **Feature Engineering** — Log transforms, interactions, binning, frequency encoding |
| 5 | **Model Selection** — Ranked recommendations with explanations |
| 6 | **Training** — SMOTE, model comparison, cross-validation, hyperparameter tuning |
| 7 | **Evaluation** — ROC-AUC, Recall, PR Curve, Lift Chart, Threshold Analysis |
| 8 | **Explainability** — SHAP values, feature importance, individual reasoning |

---

## 🧠 Key Features

### Adaptive Preprocessing
- Automatically detects column types (numeric, categorical, datetime, boolean, ID)
- Chooses `RobustScaler` when outliers are detected, `StandardScaler` otherwise
- `OneHotEncoding` for low-cardinality (≤8 unique), `OrdinalEncoding` for high
- Median imputation for skewed/missing, mean for normal distributions
- Datetime columns auto-decomposed into year/month/day/week/weekend features

### Intelligent Feature Engineering
- Log transforms for positively skewed columns
- Interaction features from top mutual-information pairs
- Quantile binning for high-cardinality numerics
- Frequency encoding for high-cardinality categoricals
- Automatic removal of highly correlated and low-variance features
- Lightweight multicollinearity diagnostics using correlation and approximate VIF
- Basic Weight of Evidence (WOE) copies for top Information Value (IV) features
- Simple IV-based feature selection for very low-signal features

### Smart Model Recommendation
- Ranks models based on dataset size, imbalance ratio, dimensionality
- Explains WHY each model is recommended
- Supports: Logistic Regression, Random Forest, XGBoost, LightGBM, Gradient Boosting
- Lets you compare multiple candidate models on the same validation split
- Lets you promote the preferred comparison winner as the final model

### Credit Risk Evaluation
- Prioritizes Recall and ROC-AUC
- Interactive charts: ROC Curve, PR Curve, Confusion Matrix, Score Distribution
- Threshold analysis to tune decision boundary
- Lift and Gain charts for deployment prioritization
- Lightweight residual variance / heteroscedasticity-style check

### SHAP Explainability
- TreeExplainer for tree-based models (fast)
- KernelExplainer fallback for other models
- Summary bar plot of mean |SHAP| values
- Waterfall chart for individual predictions
- Natural language "Why was this customer flagged?" reasoning

---

## 📊 Sample Dataset Schema (Synthetic)

The built-in synthetic dataset includes:

| Column | Type | Description |
|--------|------|-------------|
| customer_id | ID | Unique identifier |
| age | Numeric | Customer age |
| annual_income | Numeric (skewed) | Annual income |
| employment_years | Numeric | Years employed |
| loan_amount | Numeric (skewed) | Requested loan amount |
| credit_score | Numeric | Credit score (300-850) |
| debt_to_income_ratio | Numeric | DTI ratio |
| loan_to_income_ratio | Numeric | LTI ratio |
| num_late_payments | Numeric | Past late payments |
| num_credit_inquiries | Numeric | Hard inquiries |
| has_mortgage | Boolean | Mortgage flag |
| education_level | Categorical | Education level |
| loan_purpose | Categorical | Purpose of loan |
| employment_type | Categorical | Employment classification |
| application_date | Datetime | Application date |
| default | **Target** | 0 = No default, 1 = Default |

---

## ⚙️ Sidebar Controls

| Control | Description |
|---------|-------------|
| Test Set % | Proportion held out for final test |
| Validation Set % | Proportion for validation monitoring |
| Apply SMOTE | Oversample minority class for imbalanced data |
| K-Fold Cross Validation | Evaluate with cross-validation |
| Hyperparameter Tuning | RandomizedSearchCV over model grid |
| Decision Threshold | Tune precision/recall tradeoff |

---

## 💾 Exports

- **Trained Model** (.pkl via joblib)
- **Processed Dataset** (.csv)
- **Evaluation Metrics** (.csv)
- **Feature Importance** (.csv)

---

## 📦 Requirements

```
streamlit>=1.32.0
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
xgboost>=2.0.0
lightgbm>=4.0.0
shap>=0.43.0
plotly>=5.18.0
matplotlib>=3.7.0
seaborn>=0.12.0
imbalanced-learn>=0.11.0
openpyxl>=3.1.0
joblib>=1.3.0
scipy>=1.11.0
```

---

## 🔧 Customization

To use with your own dataset:
1. Ensure your CSV has a clear binary target column (0/1)
2. Upload on Step 1
3. Select your target column on Step 2
4. The system auto-adapts all preprocessing and modeling

No code changes required for new datasets.
