"""Golden regression against the original capstone workbook.

The fixtures in ``tests/fixtures/`` are the exact per-school outputs published
in ``ORIE4820_Capstone.xlsx``.  These tests are the contract that this
refactor reproduces the submitted analysis rather than merely resembling it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from titlei.needs import FRPL_Z, NAIVE_WEIGHT, NEED_GROUP, SCORE_Z, WEIGHT
from titlei.simulate import CHANGE, EXTRA_PER_PUPIL, FUNDING, PROJECTED, run_scenario

SCHOOL = "School Name"


def _aligned(actual: pd.DataFrame, golden: pd.DataFrame) -> pd.DataFrame:
    merged = actual.merge(golden, on=SCHOOL, suffixes=("", "_golden"))
    assert len(merged) == len(golden), "school names do not line up with the workbook"
    return merged


def test_combined_need_scores_match_the_workbook(schools, config, golden_combined):
    frame, _ = run_scenario(schools, config, strategy="combined")
    merged = _aligned(frame, golden_combined)

    assert np.allclose(merged[FRPL_Z], merged["FRPL_Z_golden"], atol=1e-9)
    assert np.allclose(merged[SCORE_Z], merged["Score_Z_golden"], atol=1e-9)
    assert np.allclose(merged[WEIGHT], merged["Weight_golden"], atol=1e-9)
    assert (merged[NEED_GROUP] == merged["Need Group_golden"]).all()


def test_combined_allocation_matches_the_workbook(schools, config, golden_combined):
    frame, allocation = run_scenario(schools, config, strategy="combined")
    merged = _aligned(frame, golden_combined)

    assert np.allclose(merged[FUNDING], merged["Optimized_Funding_500M"], atol=1e-6)
    assert np.allclose(
        merged[EXTRA_PER_PUPIL], merged["Optimized_Extra_Per_Pupil_500M"], atol=1e-9
    )
    assert np.allclose(merged[PROJECTED], merged["Projected Score 500M"], atol=1e-9)
    assert np.allclose(merged[CHANGE], merged["Score Change 500M"], atol=1e-9)
    assert allocation.budget_used == pytest.approx(500_000_000.0)


def test_naive_allocation_matches_the_workbook(schools, config, golden_naive):
    frame, _ = run_scenario(schools, config, strategy="naive")
    merged = _aligned(frame, golden_naive)

    assert np.allclose(merged[NAIVE_WEIGHT], merged["Naive_Weight_golden"], atol=1e-9)
    assert np.allclose(
        merged[FUNDING], merged["Optimized_Funding_Naive_500M"], atol=1e-6
    )
    assert np.allclose(
        merged[CHANGE], merged["Score Change Naive 500M"], atol=1e-9
    )


def test_group_summary_matches_the_workbook(schools, config, golden_groups):
    from titlei.metrics import group_summary

    frame, _ = run_scenario(schools, config, strategy="combined")
    summary = group_summary(frame).set_index(NEED_GROUP)
    expected = golden_groups.set_index("Need Group")

    for group in expected.index:
        assert summary.loc[group, "Before Score"] == pytest.approx(
            expected.loc[group, "Before Score"], abs=1e-6
        )
        assert summary.loc[group, "After Score"] == pytest.approx(
            expected.loc[group, "After Score"], abs=1e-6
        )
        assert summary.loc[group, "Score Change"] == pytest.approx(
            expected.loc[group, "Score Change 500M"], abs=1e-6
        )
        assert summary.loc[group, "Extra Per Pupil"] == pytest.approx(
            expected.loc[group, "Optimized_Extra_Per_Pupil_500M"], abs=1e-6
        )


def test_headline_finding_holds(schools, config, golden_combined):
    """High-need schools gain the full 5-point improvement; the tiers converge."""
    frame, _ = run_scenario(schools, config, strategy="combined")
    high_need = frame[frame[NEED_GROUP] == "High-Need Schools"]

    assert len(high_need) == 171
    assert high_need[EXTRA_PER_PUPIL].min() == pytest.approx(5000.0)
    assert high_need[CHANGE].mean() == pytest.approx(5.0)
