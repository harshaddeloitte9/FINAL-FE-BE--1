import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import _build_data_profile, Agent2
from utils import generate_synthetic_credit_dataset


def test_backend_uses_agent2_with_data_checks():
    agent = Agent2(str(Path(__file__).resolve().parent / "rag_store" / "rules.json"))

    assert hasattr(agent, "check_data")
    assert callable(getattr(agent, "check_data"))


def test_build_data_profile_infers_default_target_and_target_summary():
    df = generate_synthetic_credit_dataset(n_samples=400)
    profile = _build_data_profile(df, dataset_name="synthetic")

    assert profile["target_col"] == "default"
    assert profile["target_summary"]["selected_target"] == "default"
    assert profile["target_summary"]["task_type"] == "binary"
    assert profile["class_distribution"] is not None
    assert profile["duplicate_rate"] >= 0
    assert profile["outlier_analysis"]
