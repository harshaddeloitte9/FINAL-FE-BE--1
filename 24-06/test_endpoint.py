#!/usr/bin/env python3
"""Test the /models/recommend endpoint to verify HTTP 200 and valid JSON response."""

import requests
import json

def test_recommend_endpoint():
    """Test /models/recommend with CSV and parameters."""
    
    # Test 1: CSV-based
    print("=" * 60)
    print("TEST 1: CSV-based recommendation")
    print("=" * 60)
    
    csv_data = """age,income,credit_score,loan_status
25,30000,600,0
35,50000,700,1
45,75000,750,0
55,100000,800,1
30,40000,650,0"""
    
    files = {'file': ('test.csv', csv_data)}
    data = {'target_col': 'loan_status'}
    
    try:
        resp = requests.post('http://127.0.0.1:8000/models/recommend', 
                           files=files, data=data, timeout=10)
        print(f"HTTP Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"ERROR: Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        payload = resp.json()
        recommendations = payload.get("recommendations", [])
        
        print(f"✓ Received {len(recommendations)} model recommendations")
        
        # Verify fields
        for i, rec in enumerate(recommendations[:3]):
            print(f"\n  Model {i+1}: {rec.get('name')}")
            print(f"    - score: {rec.get('score')}")
            print(f"    - why: {rec.get('why')[:60]}...")
            print(f"    - best_for: {rec.get('best_for')}")
            
            # Verify no non-serializable types
            if 'class' in rec or 'param_grid' in rec or 'default_params' in rec:
                print(f"    ERROR: Found non-JSON-safe fields!")
                return False
        
        print("\n✓ All fields are JSON-serializable")
        print("✓ TEST 1 PASSED")
        
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return False
    
    # Test 2: Parameter-based
    print("\n" + "=" * 60)
    print("TEST 2: Parameter-based recommendation")
    print("=" * 60)
    
    params = {
        'n_samples': 5000,
        'n_features': 35,
        'class_imbalance_ratio': 3.5,
        'task_type': 'binary'
    }
    
    try:
        resp = requests.post('http://127.0.0.1:8000/models/recommend', 
                           data=params, timeout=10)
        print(f"HTTP Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"ERROR: Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        payload = resp.json()
        recommendations = payload.get("recommendations", [])
        
        print(f"✓ Received {len(recommendations)} model recommendations")
        
        # Check top 3
        for i, rec in enumerate(recommendations[:3]):
            print(f"  {i+1}. {rec['name']} (score: {rec['score']})")
        
        print("✓ TEST 2 PASSED")
        
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return False
    
    return True

if __name__ == '__main__':
    success = test_recommend_endpoint()
    print("\n" + "=" * 60)
    if success:
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("Endpoint /models/recommend is working correctly")
        print("No PydanticSerializationError")
        print("All responses are valid JSON")
    else:
        print("✗✗✗ TESTS FAILED ✗✗✗")
    print("=" * 60)
