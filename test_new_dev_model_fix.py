"""
Test for NEW development model appearing in inventory.
This simulates a fresh frontend form submission with proper business model name.
"""

import json
import requests
import csv
from pathlib import Path
from datetime import datetime
import time

# Configuration
BACKEND_URL = "http://127.0.0.1:8001"
BACKEND_DIR = Path("24-06")
INVENTORY_FILE = BACKEND_DIR / "app_data" / "model_inventory.json"

# Create a unique test dataset
def create_test_dataset():
    dataset_name = f"test_new_dev_dataset_{int(datetime.now().timestamp())}.csv"
    dataset_path = BACKEND_DIR / "demo_data" / dataset_name
    
    # Create demo_data dir if needed
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write larger test data with proper header
    with open(dataset_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["loan_status", "age", "income"])  # Header
        # Add 100 rows for better training data
        for i in range(100):
            status = 1 if i % 2 == 0 else 0
            age = 20 + (i % 50)
            income = 20000 + (i * 300)
            writer.writerow([status, age, income])
    
    return dataset_name, str(dataset_path)

# Post training request
def post_training_request(dataset_name):
    # Generate unique model name (NOT algorithm name)
    unique_model_name = f"Premium_Risk_Assessment_Q4_v{int(datetime.now().timestamp()) % 1000}"
    
    dataset_path = Path("24-06") / "demo_data" / dataset_name
    
    # Prepare form data - simulating frontend form submission
    data = {
        "target_col": "loan_status",  # Required: target column for training
        "model_name": unique_model_name,  # THIS IS KEY: real business model name, not algorithm
        "model_owner": "John_Smith",  # Simulating authenticated user
        "business_unit": "Credit Risk",
        "model_purpose": "Assess credit risk for premium customers",
        "model_version": "1.0.0",
        "model_type": "Classification",
        "development_date": datetime.now().isoformat(),
        "status": "Development",
        "documentation_path": f"demo_data/clean_mdd.txt",
        "estimator_name": "XGBoost",  # Algorithm name sent separately
        "test_size": 0.1,  # Smaller splits for smaller dataset
        "val_size": 0.1,
    }
    
    print(f"\n📤 Submitting NEW development model training request:")
    print(f"   Model Name (Business ID): {unique_model_name}")
    print(f"   Model Owner: {data['model_owner']}")
    print(f"   Algorithm (Estimator): {data['estimator_name']}")
    print(f"   Dataset: {dataset_name}")
    
    # Open file and send request
    with open(dataset_path, "rb") as f:
        files = {"file": (dataset_name, f, "text/csv")}
        response = requests.post(
            f"{BACKEND_URL}/models/train",
            data=data,
            files=files,
            timeout=120
        )
    
    print(f"   Response Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ Training succeeded")
        print(f"   Backend returned model_name: {result.get('model_name')}")
        print(f"   Backend returned model_owner: {result.get('model_owner')}")
        return True, unique_model_name, result
    else:
        print(f"   ✗ Training failed")
        print(f"   Error: {response.text}")
        return False, unique_model_name, None

# Check if model appears in inventory
def verify_model_in_inventory(model_name_to_find):
    print(f"\n🔍 Verifying model appears in inventory...")
    
    # Check file exists
    if not INVENTORY_FILE.exists():
        print(f"   ✗ Inventory file not found: {INVENTORY_FILE}")
        return False
    
    # Load inventory
    with open(INVENTORY_FILE, "r") as f:
        inventory = json.load(f)
    
    print(f"   Inventory contains {len(inventory.get('models', []))} models")
    
    # Look for our model - search in model_name field (not business_model_name)
    for model_entry in inventory.get("models", []):
        model_n = model_entry.get("model_name", "")
        algorithm = model_entry.get("algorithm", "")
        owner = model_entry.get("model_owner", "")
        created = model_entry.get("created_at", "N/A")
        doc_path = model_entry.get("documentation_path", "")
        
        if model_n == model_name_to_find:
            print(f"   ✓ FOUND model in inventory!")
            print(f"      Model Name: {model_n}")
            print(f"      Algorithm: {algorithm}")
            print(f"      Model Owner: {owner}")
            print(f"      Documentation Path: {doc_path}")
            print(f"      Created: {created}")
            return True
    
    print(f"   ✗ Model '{model_name_to_find}' NOT FOUND in inventory")
    print(f"   Models in inventory:")
    for model_entry in inventory.get("models", []):
        model_n = model_entry.get("model_name", "")
        if model_n:
            print(f"      - {model_n}")
    
    return False

# Check API endpoint
def verify_via_api(model_name_to_find):
    print(f"\n🔗 Verifying via GET /model-inventory API...")
    
    response = requests.get(f"{BACKEND_URL}/model-inventory", timeout=10)
    
    if response.status_code != 200:
        print(f"   ✗ API failed with status {response.status_code}")
        return False
    
    inventory = response.json()
    
    for model_entry in inventory.get("models", []):
        model_n = model_entry.get("model_name", "")
        if model_n == model_name_to_find:
            print(f"   ✓ Model found via API")
            return True
    
    print(f"   ✗ Model not found in API response")
    return False

# Main test
if __name__ == "__main__":
    print("=" * 70)
    print("TEST: NEW Development Model Appearing in Inventory (After Fix)")
    print("=" * 70)
    
    try:
        # Step 1: Create dataset
        print("\n1️⃣  Creating test dataset...")
        dataset_name, dataset_path = create_test_dataset()
        print(f"   ✓ Created: {dataset_path}")
        
        # Step 2: Submit training request with proper business model name
        print("\n2️⃣  Submitting training request with NEW unique business model name...")
        success, model_name, response = post_training_request(dataset_name)
        
        if not success:
            print("\n❌ Training request failed - cannot verify inventory")
            exit(1)
        
        # Small delay for backend to write inventory
        time.sleep(2)
        
        # Step 3: Verify in file
        print("\n3️⃣  Checking model_inventory.json file...")
        file_found = verify_model_in_inventory(model_name)
        
        # Step 4: Verify via API
        api_found = verify_via_api(model_name)
        
        # Summary
        print("\n" + "=" * 70)
        if file_found and api_found:
            print("✅ SUCCESS: NEW development model appears in inventory!")
            print(f"   Model: {model_name}")
            print(f"   Verified in: file + API")
        elif file_found:
            print("⚠️  PARTIAL: Model in file but not in API")
        elif api_found:
            print("⚠️  PARTIAL: Model in API but not in file")
        else:
            print("❌ FAILURE: NEW development model NOT appearing in inventory")
            print("   This indicates the fix did not resolve the issue")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
