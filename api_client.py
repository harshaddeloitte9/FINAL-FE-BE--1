"""
api_client.py - FastAPI Client for Streamlit Frontend

Provides convenient methods to call the Credit Risk ML backend API.
"""

import io
import json
from typing import Any, Dict, Optional
import requests
import pandas as pd
import streamlit as st


class CreditRiskAPIClient:
    """
    Client for calling the Credit Risk ML FastAPI backend.
    
    Usage:
        client = CreditRiskAPIClient(base_url="http://localhost:8000")
        result = client.feature_engineering(df, "default")
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 60):
        self.base_url = base_url
        self.timeout = timeout
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response with error checking."""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"API Error ({response.status_code}): {response.text}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to {self.base_url}. Is the server running?")
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response from server")
    
    def feature_engineering(
        self,
        df: pd.DataFrame,
        target_col: str,
        use_synthetic: bool = False,
        n_synthetic: int = 2000,
    ) -> Dict[str, Any]:
        """
        Call the feature engineering endpoint.
        
        Args:
            df: Input DataFrame
            target_col: Target column name
            use_synthetic: Generate synthetic data instead
            n_synthetic: Number of synthetic samples
            
        Returns:
            Response dict with feature_engineering_summary containing:
            - transformation_details: List of transformation metadata
            - feature_mapping: Original → transformed feature mappings
        """
        url = f"{self.base_url}/data/feature-engineering"
        
        try:
            if use_synthetic:
                # Generate synthetic data via API
                data = {
                    "target_col": target_col,
                    "synthetic_samples": n_synthetic,
                }
                response = requests.post(url, data=data, timeout=self.timeout)
            else:
                # Upload CSV file
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_text = csv_buffer.getvalue()
                
                files = {"file": ("data.csv", csv_text, "text/csv")}
                data = {"target_col": target_col}
                
                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )
            
            return self._handle_response(response)
            
        except Exception as e:
            st.error(f"Feature Engineering API Error: {e}")
            return None
    
    def recommend_models(
        self,
        df: Optional[pd.DataFrame] = None,
        target_col: Optional[str] = None,
        task_type: Optional[str] = None,
        n_samples: Optional[int] = None,
        n_features: Optional[int] = None,
        class_imbalance_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Call the model recommendation endpoint.
        
        Args:
            Either provide (df, target_col) or (task_type, n_samples, n_features)
            
        Returns:
            Response dict with recommendations list
        """
        url = f"{self.base_url}/models/recommend"
        
        try:
            if df is not None and target_col is not None:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_text = csv_buffer.getvalue()
                
                files = {"file": ("data.csv", csv_text, "text/csv")}
                data = {"target_col": target_col}
                
                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )
            else:
                # Use numeric summary
                data = {
                    "task_type": task_type or "binary",
                    "n_samples": n_samples or 1000,
                    "n_features": n_features or 20,
                    "class_imbalance_ratio": class_imbalance_ratio or 1.0,
                }
                response = requests.post(url, data=data, timeout=self.timeout)
            
            return self._handle_response(response)
            
        except Exception as e:
            st.error(f"Model Recommendation API Error: {e}")
            return None
    
    def train_model(
        self,
        df: pd.DataFrame,
        target_col: str,
        model_name: str,
        test_size: float = 0.15,
        val_size: float = 0.15,
        random_seed: int = 42,
        use_feature_engineering: bool = True,
        use_class_weight: bool = False,
        use_hyperopt: bool = False,
    ) -> Dict[str, Any]:
        """
        Call the model training endpoint.
        
        Args:
            df: Input DataFrame
            target_col: Target column name
            model_name: Model to train (e.g., "Logistic Regression", "XGBoost")
            test_size: Test split size
            val_size: Validation split size
            random_seed: Random seed for reproducibility
            use_feature_engineering: Apply feature engineering before training
            use_class_weight: Use balanced class weights
            use_hyperopt: Perform hyperparameter optimization
            
        Returns:
            Response dict with training_info and model_artifact
        """
        url = f"{self.base_url}/models/train"
        
        try:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_text = csv_buffer.getvalue()
            
            files = {"file": ("data.csv", csv_text, "text/csv")}
            data = {
                "target_col": target_col,
                "model_name": model_name,
                "test_size": test_size,
                "val_size": val_size,
                "random_seed": random_seed,
                "use_feature_engineering": str(use_feature_engineering).lower(),
                "use_class_weight": str(use_class_weight).lower(),
                "use_hyperopt": str(use_hyperopt).lower(),
            }
            
            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout,
            )
            
            return self._handle_response(response)
            
        except Exception as e:
            st.error(f"Model Training API Error: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if the API server is running."""
        try:
            response = requests.get(
                f"{self.base_url}/docs",
                timeout=5,
            )
            return response.status_code == 200
        except:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit Integration Helpers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_api_client(base_url: str = "http://localhost:8000") -> CreditRiskAPIClient:
    """Get cached API client instance."""
    return CreditRiskAPIClient(base_url=base_url)


def check_api_connection(client: CreditRiskAPIClient) -> None:
    """Display API connection status in Streamlit."""
    if client.health_check():
        st.success("✅ Connected to FastAPI backend")
    else:
        st.error(
            "❌ Cannot reach FastAPI backend. "
            "Ensure it's running at http://localhost:8000\n\n"
            "Start it with:\n"
            "`uvicorn main:app --host 0.0.0.0 --port 8000`"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Data Extraction Helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_transformation_details(
    fe_summary: Dict[str, Any],
) -> pd.DataFrame:
    """
    Extract transformation details from API response into a DataFrame.
    
    Args:
        fe_summary: feature_engineering_summary from API response
        
    Returns:
        DataFrame with columns:
        - Original Feature
        - Transformed To
        - Type
        - Reason
        - Method
    """
    details = fe_summary.get("transformation_details", [])
    
    rows = []
    for detail in details:
        rows.append({
            "Original Feature": detail.get("original_feature", ""),
            "Transformed To": ", ".join(detail.get("transformed_features", [])) or "(removed)",
            "Type": detail.get("transformation_type", ""),
            "Reason": detail.get("reason", ""),
            "Method": detail.get("method", ""),
        })
    
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def extract_feature_mapping(
    fe_summary: Dict[str, Any],
) -> pd.DataFrame:
    """
    Extract feature mapping from API response into a DataFrame.
    
    Args:
        fe_summary: feature_engineering_summary from API response
        
    Returns:
        DataFrame with columns:
        - Source Feature
        - Created Feature
    """
    mapping = fe_summary.get("feature_mapping", {})
    
    rows = []
    for source, targets in mapping.items():
        for target in targets:
            rows.append({
                "Source Feature": source,
                "Created Feature": target,
            })
    
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def export_transformation_metadata(
    fe_summary: Dict[str, Any],
    filename: str = "transformation_metadata.json",
) -> bytes:
    """
    Export transformation metadata as JSON.
    
    Args:
        fe_summary: feature_engineering_summary from API response
        filename: Export filename
        
    Returns:
        JSON bytes for download
    """
    metadata = {
        "summary": {
            "original_shape": fe_summary.get("original_shape"),
            "final_shape": fe_summary.get("final_shape"),
            "features_added": fe_summary.get("features_added"),
            "features_removed": fe_summary.get("features_removed"),
        },
        "transformation_details": fe_summary.get("transformation_details", []),
        "feature_mapping": fe_summary.get("feature_mapping", {}),
    }
    
    return json.dumps(metadata, indent=2).encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Example Usage in Streamlit
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: How to use in app.py
    
    client = get_api_client()
    check_api_connection(client)
    
    # Call feature engineering
    df = pd.read_csv("sample.csv")
    result = client.feature_engineering(df, "default")
    
    if result:
        fe_summary = result["feature_engineering_summary"]
        plan = result["feature_engineering_plan"]
        
        # Extract and display transformation details
        transform_df = extract_transformation_details(fe_summary)
        st.dataframe(transform_df)
        
        # Extract and display feature mapping
        mapping_df = extract_feature_mapping(fe_summary)
        st.dataframe(mapping_df)
        
        # Export metadata
        json_data = export_transformation_metadata(fe_summary)
        st.download_button(
            "Download Transformation Metadata (JSON)",
            data=json_data,
            file_name="transformation_metadata.json",
            mime="application/json",
        )
