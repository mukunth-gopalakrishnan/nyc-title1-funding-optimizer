"""Need scoring: turning enrollment, poverty and test scores into a weight.

Two competing definitions of need live here.  ``naive_weights`` reproduces the
DOE's current practice of ranking schools on financial need alone.
``combined_weights`` is the capstone proposal: a weighted index of financial
need and academic need, so a school that is both poor *and* behind outranks a
school that is only poor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from titlei.config import ModelConfig
from titlei.data import ENROLLMENT, FRPL_COUNT, SCORE

FRPL_PROPORTION = "FRPL Proportion"
FRPL_Z = "FRPL_Z"
SCORE_Z = "Score_Z"
WEIGHT = "Weight"
NAIVE_WEIGHT = "Naive_Weight"
NEED_GROUP = "Need Group"

HIGH_NEED = "High-Need Schools"
LOWER_NEED = "Lower-Need Schools"


def zscore(series: pd.Series) -> pd.Series:
    """Sample z-score (ddof=1), matching the spreadsheet the model came from."""
    std = series.std()
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.mean()) / std


def add_frpl_proportion(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the share of students on free or reduced-price lunch."""
    frame = frame.copy()
    frame[FRPL_PROPORTION] = frame[FRPL_COUNT] / frame[ENROLLMENT]
    return frame


def combined_weights(
    frame: pd.DataFrame, config: ModelConfig | None = None
) -> pd.DataFrame:
    """Score need as a blend of financial and academic need.

    ``Score_Z`` is *inverted* so that a low Regents average produces a high
    academic-need score.  The blended index is clipped at ``weight_floor``,
    which both keeps the objective non-negative and defines the boundary
    between the high-need and lower-need funding tiers.
    """
    config = config or ModelConfig()
    frame = add_frpl_proportion(frame)

    frame[FRPL_Z] = zscore(frame[FRPL_PROPORTION])
    frame[SCORE_Z] = -zscore(frame[SCORE])
    frame[WEIGHT] = (
        config.financial_weight * frame[FRPL_Z] + config.academic_weight * frame[SCORE_Z]
    ).clip(lower=config.weight_floor)
    frame[NEED_GROUP] = np.where(
        frame[WEIGHT] > config.weight_floor, HIGH_NEED, LOWER_NEED
    )
    return frame


def naive_weights(
    frame: pd.DataFrame, config: ModelConfig | None = None
) -> pd.DataFrame:
    """Score need on financial need alone — the status-quo baseline."""
    config = config or ModelConfig()
    frame = add_frpl_proportion(frame)

    frame[NAIVE_WEIGHT] = zscore(frame[FRPL_PROPORTION]).clip(
        lower=config.weight_floor
    )
    return frame
