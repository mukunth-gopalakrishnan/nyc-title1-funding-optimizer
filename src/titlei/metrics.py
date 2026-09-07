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
    """Mean Regents gap between lower-need and high-need schools."""
    high = frame.loc[frame[NEED_GROUP] == HIGH_NEED, column].mean()
    low = frame.loc[frame[NEED_GROUP] != HIGH_NEED, column].mean()
    return float(low - high)


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
        "gini_funding_before": gini(frame[FUNDING_PER_PUPIL]),
        "gini_funding_after": gini(frame[FUNDING_AFTER]),
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
