from __future__ import annotations

import numpy as np
import pytest

from titlei.needs import NAIVE_WEIGHT, WEIGHT, combined_weights, naive_weights
from titlei.optimizer import InfeasibleAllocation, allocate, build_bounds


def test_budget_is_respected(schools, config):
    scored = combined_weights(schools, config)
    result = allocate(scored, scored[WEIGHT], config)
    assert result.budget_used <= config.extra_budget + 1e-6
    assert result.budget_utilisation == pytest.approx(1.0, abs=1e-9)


def test_no_school_exceeds_its_cap(schools, config):
    scored = combined_weights(schools, config)
    result = allocate(scored, scored[WEIGHT], config)
    caps = np.where(
        scored[WEIGHT] > config.weight_floor,
        config.high_need_cap_per_pupil,
        config.low_need_cap_per_pupil,
    )
    per_pupil = result.funding / scored["K-12 Enrollment"].to_numpy()
    assert (per_pupil <= caps + 1e-6).all()


def test_low_scoring_schools_get_their_floor_award(schools, config):
    scored = combined_weights(schools, config)
    result = allocate(scored, scored[WEIGHT], config)
    below = scored["Avg Regents Score"] < config.floor_score
    assert (result.funding[below.to_numpy()] >= config.floor_award - 1e-6).all()


def test_high_need_tier_is_funded_ahead_of_the_rest(schools, config):
    """The whole point of the model: need buys priority on the same budget."""
    scored = combined_weights(schools, config)
    result = allocate(scored, scored[WEIGHT], config)
    per_pupil = result.funding / scored["K-12 Enrollment"].to_numpy()
    high_need = (scored[WEIGHT] > config.weight_floor).to_numpy()
    assert per_pupil[high_need].mean() > per_pupil[~high_need].mean()


def test_more_budget_never_reduces_the_objective(schools, config):
    scored = combined_weights(schools, config)
    small = allocate(scored, scored[WEIGHT], config, budget=100_000_000)
    large = allocate(scored, scored[WEIGHT], config, budget=300_000_000)
    assert large.objective >= small.objective


def test_infeasible_when_floors_exceed_budget(schools, config):
    scored = combined_weights(schools, config)
    with pytest.raises(InfeasibleAllocation, match="exceeds"):
        allocate(scored, scored[WEIGHT], config, budget=1_000.0)


def test_floor_award_is_clipped_to_the_cap(tiny_schools, config):
    """A tiny school's guaranteed floor can never break its own cap."""
    tiny = tiny_schools.copy()
    tiny.loc[0, "K-12 Enrollment"] = 5  # cap = 5 * 5000 = 25,000 < 50,000 floor
    scored = combined_weights(tiny, config)
    bounds = build_bounds(scored, scored[WEIGHT], config)
    assert bounds[0][0] <= bounds[0][1]


def test_empty_frame_is_rejected(schools, config):
    scored = combined_weights(schools, config).iloc[0:0]
    with pytest.raises(ValueError, match="empty"):
        allocate(scored, scored[WEIGHT], config)


def test_naive_and_combined_allocate_differently(schools, config):
    combined = combined_weights(schools, config)
    naive = naive_weights(schools, config)
    a = allocate(combined, combined[WEIGHT], config)
    b = allocate(naive, naive[NAIVE_WEIGHT], config)
    assert not np.allclose(a.funding, b.funding)
