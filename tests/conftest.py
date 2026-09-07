from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from titlei.config import ModelConfig
from titlei.data import load_schools

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def config() -> ModelConfig:
    return ModelConfig()


@pytest.fixture(scope="session")
def schools(config) -> pd.DataFrame:
    frame, _ = load_schools(None, config)
    return frame


@pytest.fixture(scope="session")
def golden_combined() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "golden_combined_500M.csv")


@pytest.fixture(scope="session")
def golden_naive() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "golden_naive_500M.csv")


@pytest.fixture(scope="session")
def golden_groups() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "golden_group_summary.csv")


@pytest.fixture
def tiny_schools() -> pd.DataFrame:
    """A four-school table small enough to reason about by hand."""
    return pd.DataFrame(
        {
            "School Name": ["Alpha", "Bravo", "Charlie", "Delta"],
            "Avg Regents Score": [55.0, 62.0, 70.0, 78.0],
            "K-12 Enrollment": [100, 200, 300, 400],
            "K-12 FRPL Count": [95, 170, 210, 240],
            "FRPL %": [95.0, 85.0, 70.0, 60.0],
            "Total School Funding per Pupil": [20000.0, 22000.0, 24000.0, 26000.0],
        }
    )
