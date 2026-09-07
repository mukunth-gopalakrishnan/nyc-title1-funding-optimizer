from __future__ import annotations

import numpy as np
import pytest

from titlei.needs import NEED_GROUP
from titlei.simulate import (
    CHANGE,
    EXTRA_PER_PUPIL,
    FUNDING,
    FUNDING_AFTER,
    PERCENT_INCREASE,
    PROJECTED,
    compare_strategies,
    project_scores,
    run_scenario,
    sweep_budgets,
)


def test_projection_applies_the_impact_factor(schools, config):
    frame, _ = run_scenario(schools, config)
    assert np.allclose(frame[CHANGE], frame[EXTRA_PER_PUPIL] * config.impact_factor)
    assert np.allclose(frame[PROJECTED], frame["Avg Regents Score"] + frame[CHANGE])


def test_projected_scores_are_capped(tiny_schools, config):
    capped = config.replace(impact_factor=1.0, max_score=80.0)
    frame = project_scores(tiny_schools, np.full(len(tiny_schools), 1e6), capped)
    assert (frame[PROJECTED] <= 80.0 + 1e-9).all()


def test_no_school_loses_ground(schools, config):
    frame, _ = run_scenario(schools, config)
    assert (frame[CHANGE] >= -1e-9).all()


def test_funding_after_adds_the_award(schools, config):
    frame, _ = run_scenario(schools, config)
    assert np.allclose(
        frame[FUNDING_AFTER],
        frame["Total School Funding per Pupil"] + frame[EXTRA_PER_PUPIL],
    )
    funded = frame[frame[EXTRA_PER_PUPIL] > 0]
    assert (funded[PERCENT_INCREASE] > 0).all()


def test_unknown_strategy_is_rejected(schools, config):
    with pytest.raises(ValueError, match="unknown strategy"):
        run_scenario(schools, config, strategy="vibes")


def test_combined_beats_the_baseline_for_high_need_schools(schools, config):
    """The claim the capstone rests on, asserted as a test."""
    combined, _ = run_scenario(schools, config, strategy="combined")
    naive, _ = run_scenario(schools, config, strategy="naive")
    comparison = compare_strategies(combined, naive)

    high_need = comparison[comparison[NEED_GROUP] == "High-Need Schools"]
    assert high_need["Score Change Combined"].mean() > high_need[
        "Score Change Naive"
    ].mean()


def test_sweep_covers_every_budget_and_strategy(schools, config):
    budgets = (100_000_000.0, 250_000_000.0)
    sweep = sweep_budgets(schools, config, budgets)
    assert len(sweep) == len(budgets) * 2
    assert set(sweep["Strategy"]) == {"naive", "combined"}
    for strategy in ("naive", "combined"):
        subset = sweep[sweep["Strategy"] == strategy].sort_values("Budget")
        assert subset["Mean Score Change"].is_monotonic_increasing


def test_comparison_keeps_every_school(schools, config):
    combined, _ = run_scenario(schools, config, strategy="combined")
    naive, _ = run_scenario(schools, config, strategy="naive")
    assert len(compare_strategies(combined, naive)) == len(schools)


def test_total_allocated_matches_the_budget(schools, config):
    frame, allocation = run_scenario(schools, config)
    assert frame[FUNDING].sum() == pytest.approx(allocation.budget_used)
