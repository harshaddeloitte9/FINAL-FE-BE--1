# 🚀 Quick Start: Backend-Frontend Integration

Complete integration in 5 minutes.

---

## ✅ Prerequisites Check

- [ ] Python 3.8+ installed
- [ ] FastAPI and uvicorn installed (`pip install fastapi uvicorn`)
- [ ] Streamlit installed (`pip install streamlit`)
- [ ] All required ML packages installed (see requirements.txt)

---

## 📋 Step 1: Verify Enhanced Feature Engineering (2 min)

### 1.1 Check feature_engineering.py has new fields

```bash
# Search for transformation_details in feature_engineering.py
cd "c:\Users\adeha\Downloads\Final UI 2\24-06"
findstr /N "transformation_details" feature_engineering.py
```

**Expected output:** Multiple matches (should see `transformation_details` in apply_feature_engineering)

### 1.2 Verify both versions are updated

- [ ] `c:\Users\adeha\Downloads\Final UI 2\24-06\feature_engineering.py` has transformation_details
- [ ] `c:\Users\adeha\Downloads\Final UI 2\Credit-Risk-Poc-main\feature_engineering.py` has transformation_details

---

## 🔧 Step 2: Copy Integration Files (1 min)

Copy these files to your main project directory:

```bash
cd "c:\Users\adeha\Downloads\Final UI 2"

# Copy the API client (NEW)
# Should already exist at: c:\Users\adeha\Downloads\Final UI 2\api_client.py

# Copy documentation
# Files already exist:
# - FRONTEND_API_INTEGRATION.md
# - APP_INTEGRATION_EXAMPLE.md
```

Verify files exist:
```bash
dir api_client.py FRONTEND_API_INTEGRATION.md APP_INTEGRATION_EXAMPLE.md
```

---

## 🚀 Step 3: Start FastAPI Backend (1 min)

**Terminal 1:**
```bash
cd "c:\Users\adeha\Downloads\Final UI 2\24-06"

# Install uvicorn if needed
pip install uvicorn

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Verify the API is running:**
```bash
# In another terminal:
curl http://localhost:8000/docs
# Should return HTML documentation page
```

---

## 🎨 Step 4: Update Streamlit App (1 min)

### 4.1 Add imports to app.py

```python
# Add these lines after existing imports in app.py
from api_client import (
    get_api_client,
    check_api_connection,
    extract_transformation_details,
    extract_feature_mapping,
    export_transformation_metadata,
)
```

### 4.2 Initialize API client

```python
# Add after st.set_page_config() in app.py
api_client = get_api_client(base_url="http://localhost:8000")

if "api_connected" not in st.session_state:
    st.session_state.api_connected = api_client.health_check()
```

### 4.3 Update Step 4 (Feature Engineering)

Replace the feature engineering section with code from `APP_INTEGRATION_EXAMPLE.md` → "Update Step 4: Feature Engineering section"

**Key changes:**
- Add "Use FastAPI Backend" checkbox
- Call `api_client.feature_engineering()` instead of local computation
- Display transformation details from API response
- Show exports (CSV, JSON)

---

## ▶️ Step 5: Test the Integration (0.5 min)

**Terminal 2:**
```bash
cd "c:\Users\adeha\Downloads\Final UI 2"

# Start Streamlit
streamlit run app.py
```

**Expected output:**
```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

### 5.1 Test in browser

1. Open http://localhost:8501
2. Go to **Step 1: Data Upload**
3. Upload `sample.csv` or use synthetic data
4. Go to **Step 4: Feature Engineering**
5. You should see:
   - ✅ Backend status: "Connected"
   - Checkbox: "Use FastAPI Backend" (checked)
6. Click **"Analyze & Engineer Features"**
7. Wait for analysis (~10-30 seconds)
8. View results:
   - 📋 Transformation Rationale table
   - 🔗 Detailed Transformation Mapping
   - 🌳 Feature Lineage
   - 📤 Export buttons (CSV, JSON)

---

## 🔍 Verification Checklist

After completing all steps, verify:

- [ ] FastAPI backend running on http://localhost:8000
- [ ] Streamlit app running on http://localhost:8501
- [ ] API status shows "✅ Connected" in Streamlit
- [ ] Feature Engineering returns transformation_details
- [ ] Transformation Rationale table shows multiple rows
- [ ] Feature Mapping table shows original → transformed relationships
- [ ] CSV export is downloadable and contains data
- [ ] JSON export is downloadable and valid JSON
- [ ] All 5 sections in Step 4 display correctly:
  - ✅ Transformation Rationale
  - ✅ Detailed Transformation Mapping
  - ✅ Feature Lineage
  - ✅ Decision Log & Export
  - ✅ Compliance & Governance

---

## 🆘 Troubleshooting

### Issue: "Cannot connect to API"

**Solution:**
1. Check FastAPI is running: `http://localhost:8000/docs` in browser
2. Verify port 8000 is not in use:
   ```bash
   netstat -ano | findstr :8000
   ```
3. If port in use, kill process or use different port:
   ```bash
   # Use port 8001 instead
   uvicorn main:app --port 8001 --reload
   # Update api_client call: get_api_client("http://localhost:8001")
   ```

### Issue: "No module named 'api_client'"

**Solution:**
1. Ensure `api_client.py` is in same directory as `app.py`
2. Check path:
   ```bash
   cd "c:\Users\adeha\Downloads\Final UI 2"
   dir api_client.py
   ```

### Issue: Empty transformation_details

**Solution:**
1. Verify feature_engineering.py has transformation tracking code
2. Check the feature engineering analysis created valid plan:
   ```python
   # In FastAPI logs, should see plan with transformation info
   ```
3. Use fallback (uncheck "Use FastAPI Backend"):
   - Tests if it's backend vs. local computation issue

### Issue: CORS Error

**Solution:**
Already configured in main.py, but verify:
```python
# Check main.py has CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Slow requests (>30 seconds)

**Solution:**
1. Check data size (feature engineering slower on large datasets)
2. Reduce sample size for testing:
   - Use `sample.csv` instead of full dataset
3. Monitor FastAPI logs:
   - Check for bottlenecks in feature engineering analysis

---

## 📊 Testing Data

Use the included `sample.csv` for quick testing:

```bash
# Copy sample data
cd "c:\Users\adeha\Downloads\Final UI 2\24-06"
ls sample.csv
```

Or generate synthetic data in Streamlit:
1. Go to Step 1
2. Select "Generate Synthetic Data"
3. Choose 500-1000 samples
4. Proceed to Step 4

---

## 📝 Configuration Files

### main.py (FastAPI backend)

Key endpoint: `/data/feature-engineering` (line ~407)

```python
@app.post("/data/feature-engineering")
async def feature_engineering(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    target_col: str = Form(...),
    synthetic_samples: Optional[int] = Form(None),
) -> Dict[str, Any]:
    """
    Returns:
    - feature_engineering_summary (now includes transformation_details & feature_mapping)
    - feature_engineering_plan
    - x_engineered_shape
    - x_engineered_preview
    """
```

### api_client.py (Streamlit utility)

Key class: `CreditRiskAPIClient`

```python
client = CreditRiskAPIClient(base_url="http://localhost:8000")
result = client.feature_engineering(df, target_col="default")
```

### app.py (Streamlit frontend)

Key update: Step 4 render function

```python
def render_feature_engineering():
    """Uses api_client to call backend instead of local computation"""
    client = get_api_client()
    result = client.feature_engineering(df, target_col)
    # Display results from API response
```

---

## 🎯 Next Steps

After verification:

1. **Add more API endpoints** (optional):
   - `/models/recommend` (already works)
   - `/models/train` (already works)
   - `/models/evaluate` (optional)

2. **Enhance frontend** (optional):
   - Add caching for API responses
   - Add real-time progress indicators
   - Add error recovery strategies

3. **Deploy** (optional):
   - Use production ASGI server (Gunicorn)
   - Add authentication
   - Add monitoring/logging
   - Deploy to cloud (AWS, GCP, Azure)

---

## 📞 Support Files

- **FRONTEND_API_INTEGRATION.md** - Detailed integration guide
- **APP_INTEGRATION_EXAMPLE.md** - Example code for all Step updates
- **api_client.py** - Reusable API client library
- **feature_engineering.py** - Enhanced with transformation tracking

---

## 🎓 Learning Resources

- FastAPI docs: https://fastapi.tiangolo.com/
- Streamlit docs: https://docs.streamlit.io/
- Request library: https://requests.readthedocs.io/

---

**Status**: ✅ All integration files created and ready to use!

**Time to full integration**: ~5 minutes
**Time to verification**: ~2 minutes
**Total**: ~7 minutes to working backend-frontend pipeline
