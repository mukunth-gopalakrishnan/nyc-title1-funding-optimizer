"""The allocation linear program.

Maximise total need-weighted dollars subject to a fixed discretionary budget,
a per-pupil cap that depends on the school's need tier, and a guaranteed floor
award for the lowest-scoring schools.

    maximise    sum_i w_i * x_i
    subject to  sum_i x_i <= B
                l_i <= x_i <= cap_i * enrollment_i

where ``x_i`` is the extra dollars sent to school ``i``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from titlei.config import ModelConfig
from titlei.data import ENROLLMENT, SCORE

logger = logging.getLogger(__name__)


class InfeasibleAllocation(RuntimeError):
    """Raised when no allocation satisfies the budget and floor constraints."""


@dataclass
class AllocationResult:
    """The solved allocation plus the diagnostics worth reporting."""

    funding: np.ndarray
    objective: float
    budget_used: float
    budget: float
    schools_funded: int
    schools_at_cap: int

    @property
    def budget_utilisation(self) -> float:
        return self.budget_used / self.budget if self.budget else 0.0


def build_bounds(
    frame: pd.DataFrame, weights: pd.Series, config: ModelConfig
) -> list[tuple[float, float]]:
    """Per-school (minimum, maximum) award.

    The cap tier is set by whether the school's need score cleared the floor,
    and schools averaging below ``floor_score`` on the Regents are guaranteed
    ``floor_award`` so that the optimiser cannot zero them out entirely.
    """
    is_high_need = (weights > config.weight_floor).to_numpy()
    caps = np.where(
        is_high_need, config.high_need_cap_per_pupil, config.low_need_cap_per_pupil
    )
    upper = caps * frame[ENROLLMENT].to_numpy(dtype=float)
    lower = np.where(
        frame[SCORE].to_numpy(dtype=float) < config.floor_score, config.floor_award, 0.0
    )
    lower = np.minimum(lower, upper)  # a floor can never exceed the school's cap
    return list(zip(lower, upper))


def allocate(
    frame: pd.DataFrame,
    weights: pd.Series,
    config: ModelConfig | None = None,
    budget: float | None = None,
) -> AllocationResult:
    """Solve the allocation LP for ``frame`` under ``weights``."""
    config = config or ModelConfig()
    budget = config.extra_budget if budget is None else budget

    n_schools = len(frame)
    if n_schools == 0:
        raise ValueError("cannot allocate over an empty school frame")

    bounds = build_bounds(frame, weights, config)
    required = sum(low for low, _ in bounds)
    if required > budget:
        raise InfeasibleAllocation(
            f"guaranteed floor awards total ${required:,.0f}, which exceeds the "
            f"${budget:,.0f} budget"
        )

    result = linprog(
        c=-weights.to_numpy(dtype=float),
        A_ub=np.ones((1, n_schools)),
        b_ub=np.array([budget], dtype=float),
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        raise InfeasibleAllocation(f"linprog failed: {result.message}")

    funding = np.asarray(result.x, dtype=float)
    uppers = np.array([high for _, high in bounds])
    at_cap = int(np.sum(np.isclose(funding, uppers, rtol=1e-9, atol=1e-6)))

    allocation = AllocationResult(
        funding=funding,
        objective=float(-result.fun),
        budget_used=float(funding.sum()),
        budget=float(budget),
        schools_funded=int(np.sum(funding > 0)),
        schools_at_cap=at_cap,
    )
    logger.info(
        "allocated $%s of $%s across %d schools (%d at cap)",
        f"{allocation.budget_used:,.0f}",
        f"{allocation.budget:,.0f}",
        allocation.schools_funded,
        allocation.schools_at_cap,
    )
    return allocation
