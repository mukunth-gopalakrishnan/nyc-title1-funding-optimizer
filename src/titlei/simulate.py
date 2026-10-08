"""Projecting Regents outcomes from an allocation, and sweeping budgets.

The outcome model is deliberately simple and linear: every extra dollar of
per-pupil funding buys ``impact_factor`` Regents points, capped at
``max_score``.  It is an assumption of the capstone, not an estimated
elasticity — see docs/methodology.md for why that matters when reading these
numbers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from titlei.config import ModelConfig
from titlei.data import ENROLLMENT, FUNDING_PER_PUPIL, SCHOOL, SCORE
from titlei.needs import (
    HIGH_NEED,
    NAIVE_WEIGHT,
    NEED_GROUP,
    WEIGHT,
    combined_weights,
    naive_weights,
)
from titlei.optimizer import AllocationResult, allocate

EXTRA_PER_PUPIL = "Optimized_Extra_Per_Pupil"
FUNDING = "Optimized_Funding"
PROJECTED = "Projected Score"
CHANGE = "Score Change"
FUNDING_AFTER = "Funding After Optimization"
PERCENT_INCREASE = "Funding Percent Increase"
SCORE_PERCENT_INCREASE = "Score Percent Increase"


def project_scores(
    frame: pd.DataFrame, funding: np.ndarray, config: ModelConfig | None = None
) -> pd.DataFrame:
    """Attach per-pupil awards and projected Regents scores to ``frame``."""
    config = config or ModelConfig()
    frame = frame.copy()

    frame[FUNDING] = funding
    frame[EXTRA_PER_PUPIL] = frame[FUNDING] / frame[ENROLLMENT]
    frame[PROJECTED] = (
        frame[SCORE] + frame[EXTRA_PER_PUPIL] * config.impact_factor
    ).clip(upper=config.max_score)
    frame[CHANGE] = frame[PROJECTED] - frame[SCORE]
    return frame


def add_funding_deltas(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the before/after per-pupil funding fields the dashboards chart."""
    frame = frame.copy()
    frame[FUNDING_AFTER] = frame[FUNDING_PER_PUPIL] + frame[EXTRA_PER_PUPIL]
    frame[PERCENT_INCREASE] = np.where(
        frame[FUNDING_PER_PUPIL] > 0,
        frame[EXTRA_PER_PUPIL] / frame[FUNDING_PER_PUPIL] * 100.0,
        np.nan,
    )
    frame[SCORE_PERCENT_INCREASE] = np.where(
        frame[SCORE] > 0, frame[CHANGE] / frame[SCORE] * 100.0, np.nan
    )
    return frame


def run_scenario(
    schools: pd.DataFrame,
    config: ModelConfig | None = None,
    *,
    strategy: str = "combined",
    budget: float | None = None,
) -> tuple[pd.DataFrame, AllocationResult]:
    """Score need, solve the LP, and project outcomes for one scenario.

    ``strategy`` is either ``"combined"`` (financial + academic need) or
    ``"naive"`` (financial need only, the status quo baseline).
    """
    config = config or ModelConfig()

    if strategy == "combined":
        scored = combined_weights(schools, config)
        weight_column = WEIGHT
    elif strategy == "naive":
        scored = naive_weights(schools, config)
        weight_column = NAIVE_WEIGHT
    else:
        raise ValueError(f"unknown strategy {strategy!r}; use 'combined' or 'naive'")

    allocation = allocate(scored, scored[weight_column], config, budget=budget)
    projected = project_scores(scored, allocation.funding, config)
    return add_funding_deltas(projected), allocation


def sweep_budgets(
    schools: pd.DataFrame,
    config: ModelConfig | None = None,
    budgets: tuple[float, ...] | None = None,
) -> pd.DataFrame:
    """Compare both strategies across a range of discretionary budgets."""
    config = config or ModelConfig()
    budgets = budgets if budgets is not None else config.sweep_budgets

    rows = []
    for budget in budgets:
        for strategy in ("naive", "combined"):
            frame, allocation = run_scenario(
                schools, config, strategy=strategy, budget=budget
            )
            # The naive strategy never assigns need tiers, so reuse the combined
            # model's tiering to keep the comparison on the same schools.
            if NEED_GROUP in frame.columns:
                tiers = frame[NEED_GROUP]
            else:
                tiers = combined_weights(schools, config)[NEED_GROUP]
            high_need = frame[tiers.to_numpy() == HIGH_NEED]

            rows.append(
                {
                    "Budget": budget,
                    "Strategy": strategy,
                    "Mean Score Change": frame[CHANGE].mean(),
                    "High-Need Mean Score Change": (
                        high_need[CHANGE].mean() if len(high_need) else np.nan
                    ),
                    "Students Reached": int(
                        frame.loc[frame[FUNDING] > 0, ENROLLMENT].sum()
                    ),
                    "Schools Funded": allocation.schools_funded,
                    "Budget Used": allocation.budget_used,
                }
            )
    return pd.DataFrame(rows)


def compare_strategies(
    combined: pd.DataFrame, naive: pd.DataFrame
) -> pd.DataFrame:
    """Join the two strategies school-by-school for head-to-head charting."""
    left = combined[[SCHOOL, NEED_GROUP, SCORE, CHANGE, EXTRA_PER_PUPIL]].rename(
        columns={
            CHANGE: "Score Change Combined",
            EXTRA_PER_PUPIL: "Extra Per Pupil Combined",
        }
    )
    right = naive[[SCHOOL, CHANGE, EXTRA_PER_PUPIL]].rename(
        columns={
            CHANGE: "Score Change Naive",
            EXTRA_PER_PUPIL: "Extra Per Pupil Naive",
        }
    )
    return left.merge(right, on=SCHOOL, how="inner")
