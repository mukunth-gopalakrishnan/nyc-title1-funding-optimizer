"""Summary and equity metrics computed from a solved scenario."""

from __future__ import annotations

import numpy as np
import pandas as pd

from titlei.data import ENROLLMENT, FUNDING_PER_PUPIL, SCHOOL, SCORE
from titlei.needs import HIGH_NEED, NEED_GROUP
from titlei.simulate import (
    CHANGE,
    EXTRA_PER_PUPIL,
    FUNDING,
    FUNDING_AFTER,
    PROJECTED,
)


def group_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Before/after averages by need tier — the headline comparison table."""
    grouped = (
        frame.groupby(NEED_GROUP)
        .agg(
            Schools=(SCHOOL, "count"),
            Students=(ENROLLMENT, "sum"),
            **{
                "Before Score": (SCORE, "mean"),
                "After Score": (PROJECTED, "mean"),
                "Score Change": (CHANGE, "mean"),
                "Funding Before": (FUNDING_PER_PUPIL, "mean"),
                "Funding After": (FUNDING_AFTER, "mean"),
                "Extra Per Pupil": (EXTRA_PER_PUPIL, "mean"),
                "Total Allocated": (FUNDING, "sum"),
            },
        )
        .reset_index()
    )
    grouped["Share of Budget"] = (
        grouped["Total Allocated"] / grouped["Total Allocated"].sum()
    )
    return grouped.sort_values(NEED_GROUP).reset_index(drop=True)


def borough_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Allocation rolled up by borough, when the source data carries one."""
    if "Borough" not in frame.columns:
        return pd.DataFrame()
    return (
        frame.groupby("Borough")
        .agg(
            Schools=(SCHOOL, "count"),
            Students=(ENROLLMENT, "sum"),
            **{
                "Before Score": (SCORE, "mean"),
                "After Score": (PROJECTED, "mean"),
                "Score Change": (CHANGE, "mean"),
                "Extra Per Pupil": (EXTRA_PER_PUPIL, "mean"),
                "Total Allocated": (FUNDING, "sum"),
            },
        )
        .reset_index()
        .sort_values("Total Allocated", ascending=False)
        .reset_index(drop=True)
    )


def gini(values: np.ndarray | pd.Series) -> float:
    """Gini coefficient of a non-negative distribution.

    0 is perfect equality, 1 is total concentration.  Used here on per-pupil
    funding to show how much the optimiser redistributes.
    """
    array = np.asarray(values, dtype=float)
    array = array[~np.isnan(array)]
    if array.size == 0 or np.all(array == 0):
        return 0.0
    if np.any(array < 0):
        raise ValueError("gini is undefined for negative values")
    array = np.sort(array)
    n = array.size
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * array)) / (n * np.sum(array)) - (n + 1) / n)


def score_gap(frame: pd.DataFrame, column: str) -> float:
    """Mean Regents gap between lower-need and high-need schools.

    Note that the need tiers are defined by the scenario's own weights, so this
    gap is **not comparable across scenarios that weight need differently** —
    the groups themselves have moved. Use :func:`academic_gap` for a yardstick
    that is fixed independently of any scenario.
    """
    high = frame.loc[frame[NEED_GROUP] == HIGH_NEED, column].mean()
    low = frame.loc[frame[NEED_GROUP] != HIGH_NEED, column].mean()
    return float(low - high)


def academic_gap(frame: pd.DataFrame, column: str, quantile: float = 0.25) -> float:
    """Gap between the top and bottom quartile of *baseline* Regents scores.

    The reference groups come from the schools' starting scores, which no
    scenario can change. That makes this the metric to rank scenarios on:
    unlike :func:`score_gap`, the goalposts do not move when the need weights
    do.
    """
    low_cut = frame[SCORE].quantile(quantile)
    high_cut = frame[SCORE].quantile(1 - quantile)
    bottom = frame.loc[frame[SCORE] <= low_cut, column].mean()
    top = frame.loc[frame[SCORE] >= high_cut, column].mean()
    return float(top - bottom)


def headline_metrics(frame: pd.DataFrame, budget: float) -> dict[str, float]:
    """The numbers that belong at the top of a dashboard."""
    funded = frame[frame[FUNDING] > 0]
    return {
        "schools_modelled": float(len(frame)),
        "schools_funded": float(len(funded)),
        "students_reached": float(funded[ENROLLMENT].sum()),
        "budget": float(budget),
        "budget_allocated": float(frame[FUNDING].sum()),
        "mean_score_before": float(frame[SCORE].mean()),
        "mean_score_after": float(frame[PROJECTED].mean()),
        "mean_score_change": float(frame[CHANGE].mean()),
        "max_extra_per_pupil": float(frame[EXTRA_PER_PUPIL].max()),
        "gap_before": score_gap(frame, SCORE),
        "gap_after": score_gap(frame, PROJECTED),
        "academic_gap_before": academic_gap(frame, SCORE),
        "academic_gap_after": academic_gap(frame, PROJECTED),
        "gini_funding_before": gini(frame[FUNDING_PER_PUPIL]),
        "gini_funding_after": gini(frame[FUNDING_AFTER]),
    }


def roi_metrics(frame: pd.DataFrame, budget_used: float) -> dict[str, float]:
    """Return-on-investment view of an allocation.

    The unit of return is the **student-point**: one Regents point delivered to
    one student.

    A warning that shapes how every metric here should be read. Under the
    linear impact model, a school's gain is ``funding / enrollment * k``, so
    the student-points it receives are ``enrollment * funding / enrollment * k
    = funding * k``. Summed over schools that is ``budget_used * k`` — **total
    student-points depend only on how much is spent, never on where**. So
    ``student_points_per_million`` is identically ``1000 * impact_factor`` for
    every allocation, and is kept only to make that invariance visible.

    The consequence is that "which scenario has the better ROI" is not an
    aggregate question in this model — it is a **targeting** question. The
    metrics that discriminate are the ones below it: whose students the return
    lands on, and how much of the need-tier gap it closes per dollar.
    """
    student_points = float((frame[ENROLLMENT] * frame[CHANGE]).sum())
    millions = budget_used / 1e6
    funded = frame[frame[FUNDING] > 0]

    high_need = frame[frame[NEED_GROUP] == HIGH_NEED]
    high_need_points = float((high_need[ENROLLMENT] * high_need[CHANGE]).sum())

    # Schools in the bottom quartile of baseline Regents performance — the
    # ones the whole exercise is nominally about.
    cutoff = frame[SCORE].quantile(0.25)
    bottom = frame[frame[SCORE] <= cutoff]
    bottom_points = float((bottom[ENROLLMENT] * bottom[CHANGE]).sum())

    gap_closed = score_gap(frame, SCORE) - score_gap(frame, PROJECTED)
    academic_gap_closed = academic_gap(frame, SCORE) - academic_gap(frame, PROJECTED)

    def per_million(value: float) -> float:
        return value / millions if millions else 0.0

    return {
        "budget_used": float(budget_used),
        # --- invariant under this impact model; see the docstring ----------
        "student_points": student_points,
        "student_points_per_million": per_million(student_points),
        "cost_per_student_point": (
            budget_used / student_points if student_points else float("nan")
        ),
        # --- targeting: these are the metrics that actually discriminate ---
        "high_need_share_of_points": (
            high_need_points / student_points if student_points else 0.0
        ),
        "high_need_share_of_budget": (
            float(high_need[FUNDING].sum()) / budget_used if budget_used else 0.0
        ),
        "bottom_quartile_points_per_million": per_million(bottom_points),
        "bottom_quartile_mean_gain": float(bottom[CHANGE].mean()) if len(bottom) else 0.0,
        "students_reached_per_million": per_million(float(funded[ENROLLMENT].sum())),
        # Scenario-defined tiers: only comparable between runs that share
        # the same need weights.
        "gap_closed": float(gap_closed),
        "gap_closed_per_100m": (
            float(gap_closed) / (budget_used / 1e8) if budget_used else 0.0
        ),
        # Fixed reference groups (baseline score quartiles): comparable across
        # every scenario, whatever its weights.
        "academic_gap_closed": float(academic_gap_closed),
        "academic_gap_closed_per_100m": (
            float(academic_gap_closed) / (budget_used / 1e8) if budget_used else 0.0
        ),
    }


def top_movers(frame: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """The schools whose projected outcomes improve the most."""
    columns = [SCHOOL, NEED_GROUP, SCORE, PROJECTED, CHANGE, EXTRA_PER_PUPIL]
    if "Borough" in frame.columns:
        columns.insert(1, "Borough")
    return (
        frame.nlargest(n, CHANGE)[columns]
        .reset_index(drop=True)
    )
