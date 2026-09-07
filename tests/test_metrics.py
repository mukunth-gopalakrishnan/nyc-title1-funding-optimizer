from __future__ import annotations

import numpy as np
import pytest

from titlei.metrics import (
    borough_summary,
    gini,
    group_summary,
    headline_metrics,
    score_gap,
    top_movers,
)
from titlei.simulate import CHANGE, run_scenario


@pytest.fixture(scope="module")
def solved(request):
    from titlei.config import ModelConfig
    from titlei.data import load_schools

    config = ModelConfig()
    frame, _ = load_schools(None, config)
    solved, _ = run_scenario(frame, config)
    return solved, config


def test_group_summary_covers_both_tiers(solved):
    frame, _ = solved
    summary = group_summary(frame)
    assert set(summary["Need Group"]) == {"High-Need Schools", "Lower-Need Schools"}
    assert summary["Share of Budget"].sum() == pytest.approx(1.0)
    assert (summary["After Score"] >= summary["Before Score"]).all()


def test_borough_summary_is_present_for_this_dataset(solved):
    frame, _ = solved
    boroughs = borough_summary(frame)
    assert not boroughs.empty
    assert boroughs["Schools"].sum() == len(frame)


def test_borough_summary_is_empty_without_the_column(solved):
    frame, _ = solved
    assert borough_summary(frame.drop(columns=["Borough"])).empty


@pytest.mark.parametrize(
    "values, expected",
    [
        ([1, 1, 1, 1], 0.0),
        ([0, 0, 0, 0], 0.0),
    ],
)
def test_gini_of_a_flat_distribution_is_zero(values, expected):
    assert gini(np.array(values, dtype=float)) == pytest.approx(expected)


def test_gini_rises_with_concentration():
    even = gini(np.array([10.0, 10.0, 10.0, 10.0]))
    skewed = gini(np.array([1.0, 1.0, 1.0, 100.0]))
    assert skewed > even


def test_gini_rejects_negative_values():
    with pytest.raises(ValueError, match="undefined for negative"):
        gini(np.array([-1.0, 2.0]))


def test_the_model_narrows_the_need_tier_gap(solved):
    frame, _ = solved
    assert score_gap(frame, "Projected Score") < score_gap(frame, "Avg Regents Score")


def test_headline_metrics_are_internally_consistent(solved):
    frame, config = solved
    headline = headline_metrics(frame, config.extra_budget)
    assert headline["schools_funded"] <= headline["schools_modelled"]
    assert headline["budget_allocated"] <= headline["budget"] + 1e-6
    assert headline["mean_score_after"] >= headline["mean_score_before"]
    assert headline["gap_after"] < headline["gap_before"]


def test_top_movers_is_sorted_and_bounded(solved):
    frame, _ = solved
    movers = top_movers(frame, n=10)
    assert len(movers) == 10
    assert movers[CHANGE].is_monotonic_decreasing
