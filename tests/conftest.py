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


@pytest.fixture(autouse=True)
def _no_writes_to_the_real_registry():
    """Fail any test that saves a run into the repository's own `runs/`.

    Tests must pass `--runs-dir tmp_path`. Without this guard a forgotten flag
    silently appends to the developer's saved runs every time they run the
    suite — which happened, and only showed up as a puzzling run count days
    later.
    """
    live = ROOT / "runs"
    existed_before = live.exists()
    before = {p.name for p in live.iterdir()} if existed_before else set()

    yield

    after = {p.name for p in live.iterdir()} if live.exists() else set()
    created = after - before
    if created:
        import shutil

        for name in created:  # leave the developer's registry as we found it
            target = live / name
            shutil.rmtree(target, ignore_errors=True) if target.is_dir() else (
                target.unlink(missing_ok=True)
            )
        if not existed_before and live.exists() and not any(live.iterdir()):
            live.rmdir()
        pytest.fail(
            "this test wrote "
            f"{len(created)} run(s) into the repository's runs/ directory; "
            "pass --runs-dir tmp_path instead"
        )
