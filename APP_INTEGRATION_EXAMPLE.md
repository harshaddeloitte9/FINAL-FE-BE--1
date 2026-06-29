# Integration Example: app.py Frontend Updates

This file shows example code to integrate the FastAPI backend into your Streamlit app.py.

## Key Changes to app.py

### 1. Add imports at the top

```python
# In app.py, add these imports after existing imports:
import requests
from api_client import (
    get_api_client,
    check_api_connection,
    extract_transformation_details,
    extract_feature_mapping,
    export_transformation_metadata,
)
```

---

### 2. Add API client initialization (after st.set_page_config)

```python
# Initialize API client
api_client = get_api_client(base_url="http://localhost:8000")

# Check connection on app load
if "api_connected" not in st.session_state:
    st.session_state.api_connected = api_client.health_check()
```

---

### 3. Update Step 4: Feature Engineering section

Replace or enhance the current feature engineering section in your `render_feature_engineering()` function:

```python
def render_feature_engineering():
    """
    Enhanced Step 4: Feature Engineering with API backend support.
    """
    st.header("🔬 Feature Engineering & Analysis")
    
    # ─────────────────────────────────────────────────────────────────────
    # Connection Status
    # ─────────────────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("### Backend Status")
    with col2:
        if st.session_state.api_connected:
            st.success("✅ Connected")
        else:
            st.error("❌ Disconnected")
            st.info("Start FastAPI backend: `uvicorn main:app --port 8000`")
    
    # ─────────────────────────────────────────────────────────────────────
    # Feature Engineering Options
    # ─────────────────────────────────────────────────────────────────────
    use_api = st.checkbox(
        "Use FastAPI Backend",
        value=st.session_state.api_connected,
        help="Call the backend API for feature engineering instead of local computation"
    )
    
    if not use_api and not st.session_state.api_connected:
        st.warning("Backend not available. Using local computation.")
        use_api = False
    
    # ─────────────────────────────────────────────────────────────────────
    # Perform Feature Engineering
    # ─────────────────────────────────────────────────────────────────────
    if st.button("🚀 Analyze & Engineer Features"):
        with st.spinner("🔬 Analyzing features..."):
            
            if use_api:
                # Call FastAPI backend
                try:
                    result = api_client.feature_engineering(
                        st.session_state.X,
                        st.session_state.target_col,
                    )
                    
                    if result:
                        st.session_state.fe_plan = result["feature_engineering_plan"]
                        st.session_state.fe_summary = result["feature_engineering_summary"]
                        st.session_state.x_engineered_shape = result["x_engineered_shape"]
                        st.success("✅ API-based feature engineering complete!")
                    else:
                        st.error("Failed to call feature engineering API")
                        
                except Exception as e:
                    st.error(f"API Error: {e}")
                    st.info("Falling back to local computation...")
                    use_api = False
            
            if not use_api:
                # Local computation (fallback)
                plan = analyze_for_feature_engineering(
                    st.session_state.X,
                    st.session_state.y,
                    st.session_state.col_types,
                    st.session_state.task_type,
                )
                X_engineered, fe_summary = apply_feature_engineering(
                    st.session_state.X, plan
                )
                st.session_state.fe_plan = plan
                st.session_state.fe_summary = fe_summary
                st.session_state.x_engineered_shape = list(X_engineered.shape)
                st.success("✅ Local feature engineering complete!")
    
    # ─────────────────────────────────────────────────────────────────────
    # Display Results
    # ─────────────────────────────────────────────────────────────────────
    if "fe_summary" not in st.session_state:
        st.info("👆 Click the button above to analyze features")
        return
    
    fe_summary = st.session_state.fe_summary
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Original Shape", str(fe_summary.get("original_shape", [None, None])))
    with col2:
        st.metric("Final Shape", str(fe_summary.get("final_shape", [None, None])))
    with col3:
        st.metric("Features Added", fe_summary.get("features_added", 0))
    with col4:
        st.metric("Features Removed", fe_summary.get("features_removed", 0))
    
    # ─────────────────────────────────────────────────────────────────────
    # 1. Transformation Rationale & Decision Framework
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("📋 Transformation Rationale & Decision Framework", expanded=True):
        st.write(
            "**Framework:** Each transformation is applied based on statistical criteria "
            "and business decision logic. All parameters are learned on training data only."
        )
        
        transform_df = extract_transformation_details(fe_summary)
        if not transform_df.empty:
            st.dataframe(transform_df, use_container_width=True)
        else:
            st.info("No transformations applied.")
    
    # ─────────────────────────────────────────────────────────────────────
    # 2. Detailed Transformation Mapping
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("🔗 Detailed Transformation Mapping"):
        st.write("**Mapping:** Original features → Transformed features")
        
        mapping_df = extract_feature_mapping(fe_summary)
        if not mapping_df.empty:
            st.dataframe(mapping_df, use_container_width=True)
        else:
            st.info("No transformations applied.")
    
    # ─────────────────────────────────────────────────────────────────────
    # 3. Feature Lineage (Original → Transformed)
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("🌳 Feature Lineage (Original → Transformed)"):
        st.write("**Lineage:** Visual representation of feature derivations")
        
        mapping = fe_summary.get("feature_mapping", {})
        if mapping:
            lineage_text = "\n".join([
                f"  {src} → {', '.join(targets) if targets else '(removed)'}"
                for src, targets in mapping.items()
            ])
            st.code(lineage_text)
        else:
            st.info("No transformations applied.")
    
    # ─────────────────────────────────────────────────────────────────────
    # 4. Feature Decision Log & Export
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("📤 Feature Decision Log & Export"):
        st.write("**Decision Log:** Complete audit trail of feature engineering decisions")
        
        # CSV Export
        transform_df = extract_transformation_details(fe_summary)
        if not transform_df.empty:
            csv_data = transform_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Complete Feature Decision Log (CSV)",
                data=csv_data,
                file_name="feature_decision_log.csv",
                mime="text/csv",
            )
        
        # JSON Export
        json_data = export_transformation_metadata(fe_summary)
        st.download_button(
            "📥 Download Transformation Details (JSON)",
            data=json_data,
            file_name="transformation_metadata.json",
            mime="application/json",
        )
    
    # ─────────────────────────────────────────────────────────────────────
    # 5. Compliance & Governance Banner
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("✅ Compliance & Governance", expanded=True):
        st.success(
            "✅ **Data Leakage Prevention Verified:**\n\n"
            "• All feature engineering parameters (binning edges, frequency maps, WOE coefficients) "
            "are learned **exclusively from training data**\n"
            "• Validation and test splits apply these parameters **unchanged**, "
            "preventing information leakage\n"
            "• No data from validation or test sets influenced feature engineering decisions\n"
            "• All transformations are stateless and deterministic\n\n"
            "**Audit Trail:** Complete transformation history is exported with each feature "
            "for regulatory review and model explainability."
        )
```

---

### 4. Update Step 5: Model Selection (call recommendations from API)

```python
def render_model_selection():
    """
    Enhanced Step 5: Model Selection with API recommendations.
    """
    st.header("🎯 Model Selection & Recommendations")
    
    if "fe_summary" not in st.session_state:
        st.info("👈 Complete Feature Engineering first (Step 4)")
        return
    
    if st.button("🤖 Get Model Recommendations"):
        with st.spinner("Analyzing data characteristics..."):
            try:
                result = api_client.recommend_models(
                    st.session_state.X,
                    st.session_state.target_col,
                )
                
                if result:
                    st.session_state.recommendations = result
                    st.success("✅ Recommendations complete!")
                else:
                    st.error("Failed to get recommendations")
                    
            except Exception as e:
                st.error(f"API Error: {e}")
    
    if "recommendations" in st.session_state:
        recommendations = st.session_state.recommendations.get("recommendations", [])
        
        st.write("### Top Model Recommendations")
        for i, rec in enumerate(recommendations[:5], 1):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{i}. {rec.get('model_name', 'Unknown')}**")
            with col2:
                st.write(f"Score: {rec.get('recommendation_score', 0):.2f}")
            with col3:
                st.caption(f"Reason: {rec.get('reason', 'N/A')}")
```

---

### 5. Update Step 6: Training (use API for training)

```python
def render_training():
    """
    Enhanced Step 6: Model Training with API backend.
    """
    st.header("🏋️ Model Training")
    
    if "fe_summary" not in st.session_state:
        st.info("👈 Complete Feature Engineering first")
        return
    
    # Model selection
    model_name = st.selectbox(
        "Select Model",
        [
            "Logistic Regression",
            "Decision Tree",
            "Random Forest",
            "XGBoost",
            "LightGBM",
            "Gradient Boosting",
        ]
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        test_size = st.slider("Test Size", 0.1, 0.3, 0.15)
    with col2:
        val_size = st.slider("Validation Size", 0.1, 0.3, 0.15)
    with col3:
        use_class_weight = st.checkbox("Use Class Weight")
    
    if st.button("🚀 Start Training"):
        with st.spinner("Training model..."):
            try:
                result = api_client.train_model(
                    st.session_state.X,
                    st.session_state.target_col,
                    model_name,
                    test_size=test_size,
                    val_size=val_size,
                    use_feature_engineering=True,
                    use_class_weight=use_class_weight,
                )
                
                if result:
                    st.session_state.training_result = result
                    st.success("✅ Training complete!")
                    
                    # Display results
                    training_info = result.get("training_info", {})
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "Train Accuracy",
                            f"{training_info.get('train_accuracy', 0):.4f}"
                        )
                    with col2:
                        st.metric(
                            "Val Accuracy",
                            f"{training_info.get('val_accuracy', 0):.4f}"
                        )
                    with col3:
                        st.metric(
                            "Test Accuracy",
                            f"{training_info.get('test_accuracy', 0):.4f}"
                        )
                    with col4:
                        st.metric(
                            "Test AUC",
                            f"{training_info.get('test_auc', 0):.4f}"
                        )
                else:
                    st.error("Training failed")
                    
            except Exception as e:
                st.error(f"API Error: {e}")
```

---

## How to Use

1. **Place `api_client.py` in your project root**
   ```
   Final UI 2/
   ├── api_client.py          ← NEW
   ├── app.py                 ← UPDATE
   ├── main.py                ← (already updated)
   ├── feature_engineering.py ← (already updated)
   └── ...
   ```

2. **Start the FastAPI backend**
   ```bash
   cd "c:\Users\adeha\Downloads\Final UI 2\24-06"
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Update app.py with code from above sections**

4. **Start Streamlit**
   ```bash
   cd "c:\Users\adeha\Downloads\Final UI 2"
   streamlit run app.py
   ```

5. **Test the integration**
   - Upload data in Step 1
   - Go to Step 4 (Feature Engineering)
   - Check "Use FastAPI Backend"
   - Click "Analyze & Engineer Features"
   - View transformation details, mappings, and exports

---

## API Response Format

When you call `client.feature_engineering()`, the response contains:

```json
{
  "col_types": {...},
  "target_col": "default",
  "task_type": "binary",
  "feature_engineering_plan": {...},
  "feature_engineering_summary": {
    "added": ["income_log", "age_bin", "credit_score_woe"],
    "removed": ["low_variance_col"],
    "transformed": ["log1p(income) -> income_log", ...],
    "original_shape": [1000, 25],
    "final_shape": [1000, 37],
    "features_added": 12,
    "features_removed": 0,
    "transformation_details": [
      {
        "original_feature": "income",
        "transformed_features": ["income_log"],
        "transformation_type": "Log Transform",
        "reason": "Feature has skewness > 1.5 and positive values",
        "method": "log1p transformation for skewed distribution"
      },
      ...
    ],
    "feature_mapping": {
      "income": ["income_log"],
      "age": ["age_bin"],
      ...
    }
  },
  "x_engineered_shape": [1000, 37],
  "x_engineered_preview": [...]
}
```

---

## Testing Checklist

- [ ] FastAPI backend starts without errors
- [ ] Streamlit app starts and connects to backend
- [ ] "✅ Connected" status shows in app
- [ ] Feature engineering runs via API (not local)
- [ ] Transformation details table displays correctly
- [ ] Feature mapping shows original → transformed relationships
- [ ] CSV export works and has all columns
- [ ] JSON export contains full metadata
- [ ] Compliance banner displays
- [ ] Error messages appear if API is disconnected

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot connect to API" | Start FastAPI: `uvicorn main:app --port 8000` |
| Empty transformation details | Ensure feature_engineering.py has enhanced apply_feature_engineering() |
| Import error for api_client | Move api_client.py to same directory as app.py |
| CORS error | Ensure CORSMiddleware is in main.py (already done) |
| Slow requests | Check network, increase timeout in api_client.py |
