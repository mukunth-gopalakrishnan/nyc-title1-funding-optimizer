from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from titlei.needs import (
    FRPL_PROPORTION,
    FRPL_Z,
    HIGH_NEED,
    LOWER_NEED,
    NAIVE_WEIGHT,
    NEED_GROUP,
    SCORE_Z,
    WEIGHT,
    combined_weights,
    naive_weights,
    zscore,
)


def test_zscore_is_standardised():
    scored = zscore(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert scored.mean() == pytest.approx(0.0)
    assert scored.std() == pytest.approx(1.0)


def test_zscore_of_a_constant_series_is_zero():
    assert (zscore(pd.Series([5.0, 5.0, 5.0])) == 0).all()


def test_academic_need_is_inverted(tiny_schools):
    scored = combined_weights(tiny_schools)
    lowest = scored.loc[scored["Avg Regents Score"].idxmin()]
    highest = scored.loc[scored["Avg Regents Score"].idxmax()]
    assert lowest[SCORE_Z] > 0 > highest[SCORE_Z]


def test_weight_is_the_configured_blend(tiny_schools, config):
    scored = combined_weights(tiny_schools, config)
    expected = (
        config.financial_weight * scored[FRPL_Z]
        + config.academic_weight * scored[SCORE_Z]
    ).clip(lower=config.weight_floor)
    assert np.allclose(scored[WEIGHT], expected)


def test_weight_never_falls_below_the_floor(schools, config):
    assert combined_weights(schools, config)[WEIGHT].min() >= config.weight_floor


def test_need_group_follows_the_floor(schools, config):
    scored = combined_weights(schools, config)
    above = scored[WEIGHT] > config.weight_floor
    assert set(scored.loc[above, NEED_GROUP]) == {HIGH_NEED}
    assert set(scored.loc[~above, NEED_GROUP]) == {LOWER_NEED}


def test_naive_weight_ignores_scores(tiny_schools, config):
    baseline = naive_weights(tiny_schools, config)[NAIVE_WEIGHT]
    shifted = tiny_schools.copy()
    shifted["Avg Regents Score"] = shifted["Avg Regents Score"] * 0.5
    assert np.allclose(baseline, naive_weights(shifted, config)[NAIVE_WEIGHT])


def test_frpl_proportion_matches_counts(tiny_schools):
    scored = combined_weights(tiny_schools)
    assert np.allclose(
        scored[FRPL_PROPORTION],
        tiny_schools["K-12 FRPL Count"] / tiny_schools["K-12 Enrollment"],
    )
