# Frontend-API Integration Guide

## Overview
The enhanced feature engineering pipeline now returns detailed transformation metadata. This guide shows how to integrate the FastAPI backend with your Streamlit frontend.

---

## 1. FastAPI Endpoint (Already Updated)

**Location**: `main.py` line 407

```python
@app.post("/data/feature-engineering")
async def feature_engineering(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    df = await _read_dataframe(file=file, csv_text=csv_text, synthetic_samples=synthetic_samples)
    col_types = detect_column_types(df)
    if target_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found")
    task_type = detect_task_type(df[target_col])
    X, y, _, _, _ = prepare_data(df, col_types, target_col)
    plan = analyze_for_feature_engineering(X, y, col_types, task_type)
    X_engineered, fe_summary = apply_feature_engineering(X, plan)
    
    return {
        "col_types": col_types,
        "target_col": target_col,
        "task_type": task_type,
        "feature_engineering_plan": plan,
        "feature_engineering_summary": fe_summary,  # ✅ NOW INCLUDES transformation_details & feature_mapping
        "x_engineered_shape": list(X_engineered.shape),
        "x_engineered_preview": _serialize_dataframe(X_engineered, max_rows=5)["preview"],
    }
```

### Response Structure

The endpoint now returns `feature_engineering_summary` with these new fields:

```json
{
  "feature_engineering_summary": {
    "added": ["col_log", "col_woe", ...],
    "removed": ["low_var_col", ...],
    "transformed": ["log1p(col) -> col_log", ...],
    "original_shape": [1000, 25],
    "final_shape": [1000, 38],
    "features_added": 13,
    "features_removed": 0,
    "transformation_details": [
      {
        "original_feature": "income",
        "transformed_features": ["income_log"],
        "transformation_type": "Log Transform",
        "reason": "Feature has skewness > 1.5 and positive values",
        "method": "log1p transformation for skewed distribution"
      },
      {
        "original_feature": "age",
        "transformed_features": ["age_bin"],
        "transformation_type": "Quantile Binning",
        "reason": "High-cardinality numeric column (>20 unique values)",
        "method": "5-quantile bins with training-learned boundaries"
      }
    ],
    "feature_mapping": {
      "income": ["income_log"],
      "age": ["age_bin"],
      "credit_score": ["credit_score", "credit_score_woe"]
    }
  }
}
```

---

## 2. Streamlit Frontend Integration

### Option A: Direct Backend Call (Recommended)

**Location**: `app.py` Step 4 (Feature Engineering)

```python
import requests
import json

def fetch_feature_engineering_from_api(df, target_col, task_type):
    """
    Call the FastAPI backend for feature engineering instead of local computation.
    """
    try:
        # Prepare the request
        csv_buffer = df.to_csv(index=False)
        
        files = {'file': ('data.csv', csv_buffer, 'text/csv')}
        data = {'target_col': target_col}
        
        # Call the API
        response = requests.post(
            "http://localhost:8000/data/feature-engineering",
            files=files,
            data=data,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        
        return result
        
    except Exception as e:
        st.error(f"API call failed: {e}")
        return None
```

### Usage in Streamlit:

```python
# In render_feature_engineering() function

# Option 1: Use FastAPI backend
use_api = st.checkbox("Use FastAPI backend", value=True)

if use_api:
    with st.spinner("🔬 Calling API for feature engineering analysis..."):
        api_response = fetch_feature_engineering_from_api(
            st.session_state.X, 
            st.session_state.target_col, 
            st.session_state.task_type
        )
    
    if api_response:
        plan = api_response["feature_engineering_plan"]
        fe_summary = api_response["feature_engineering_summary"]
        # ... rest of the code uses plan and fe_summary
else:
    # Fallback to local computation
    with st.spinner("🔬 Analyzing locally for feature engineering opportunities..."):
        plan = analyze_for_feature_engineering(X_train, y_train, col_types, task_type)
        X_train_engineered, fe_summary = apply_feature_engineering(X_train, plan)
```

---

## 3. Running Both Services

### Terminal 1: Start FastAPI Backend

```bash
cd "C:\Users\adeha\Downloads\Final UI 2\24-06"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Terminal 2: Start Streamlit Frontend

```bash
cd "C:\Users\adeha\Downloads\Final UI 2\24-06"
streamlit run app.py
```

Expected output:
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

---

## 4. API Endpoints Reference

### Feature Engineering Endpoint

**POST** `/data/feature-engineering`

**Parameters:**
- `file`: (UploadFile, optional) CSV or XLSX file
- `csv_text`: (str, optional) CSV as text
- `target_col`: (str, required) Target column name
- `synthetic_samples`: (int, optional) Generate synthetic data

**Response:**
```json
{
  "col_types": {...},
  "target_col": "default",
  "task_type": "binary",
  "feature_engineering_plan": {...},
  "feature_engineering_summary": {
    "transformation_details": [...],
    "feature_mapping": {...}
  },
  "x_engineered_shape": [1000, 38],
  "x_engineered_preview": [...]
}
```

---

## 5. Integration Checklist

- [ ] **Feature Engineering Module**
  - ✅ Updated `apply_feature_engineering()` to include `transformation_details`
  - ✅ Added `feature_mapping` dict
  - ✅ Enhanced transformation metadata

- [ ] **FastAPI Backend**
  - ✅ Endpoint at `/data/feature-engineering` returns new fields
  - ✅ CORS enabled for frontend communication
  - ✅ Error handling for malformed requests

- [ ] **Streamlit Frontend**
  - [ ] Import `requests` library
  - [ ] Add API call function in Step 4
  - [ ] Update UI to display transformation details from API
  - [ ] Show Feature Lineage section
  - [ ] Export CSV/JSON with mapping

---

## 6. Key Files Modified

| File | Location | Changes |
|------|----------|---------|
| `feature_engineering.py` | 24-06/, Credit-Risk-Poc-main/ | Added `transformation_details`, `feature_mapping` to summary |
| `main.py` | 24-06/ | Endpoint already returns enhanced summary |
| `app.py` | 24-06/ | Add API call + UI rendering (optional) |

---

## 7. Example: Complete Flow

### Step-by-step:

1. **User uploads data in Streamlit**
   ```
   → app.py renders Step 4 (Feature Engineering)
   ```

2. **Frontend calls FastAPI**
   ```python
   response = requests.post(
       "http://localhost:8000/data/feature-engineering",
       files={'file': csv_file},
       data={'target_col': 'default'}
   )
   ```

3. **Backend processes**
   ```
   → main.py receives request
   → Calls analyze_for_feature_engineering()
   → Calls apply_feature_engineering()
   → Returns full response with transformation_details & feature_mapping
   ```

4. **Frontend displays results**
   ```
   → Shows Transformation Rationale table
   → Shows Feature Lineage visualization
   → Exports CSV with original→transformed mapping
   → Exports JSON with full metadata
   ```

---

## 8. Troubleshooting

### "Connection refused" error
- Ensure FastAPI is running: `http://localhost:8000`
- Check that port 8000 is not in use: `netstat -ano | findstr :8000`

### Empty transformation_details
- Verify feature_engineering.py has the enhanced apply_feature_engineering() function
- Check that the feature engineering plan has transformations: `plan["applied_steps"]`

### API returns different data format
- Ensure both frontend and backend use the same feature_engineering.py
- Verify main.py endpoint uses the updated functions

### CORS errors
- Check that CORSMiddleware is enabled in main.py (already done)
- Verify frontend URL matches allowed origins

---

## 9. Next Steps

After integration:

1. **Test API endpoint** using curl or Postman:
   ```bash
   curl -X POST "http://localhost:8000/data/feature-engineering" \
     -F "file=@data.csv" \
     -F "target_col=default"
   ```

2. **Verify transformation metadata** in response:
   - Check `transformation_details` array has entries
   - Verify `feature_mapping` shows original→transformed relationships

3. **Update Streamlit UI** to consume API response:
   - Display transformation rationale table
   - Show feature lineage
   - Provide download buttons for CSV/JSON exports

4. **Deploy** when ready:
   - Consider using production ASGI server (e.g., Gunicorn)
   - Add authentication if needed
   - Monitor API logs
