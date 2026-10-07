"""Comparing several runs against each other and against the control.

Single-run charts live in :mod:`titlei.viz`. Everything here takes a list of
:class:`~titlei.runs.RunRecord` and overlays them, so a dozen scenarios can be
read as one picture rather than a dozen.

Each run keeps one colour across every chart in a comparison, assigned in the
palette's fixed slot order, and every line carries a direct end label — so a
run is never identified by colour alone.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from titlei.data import SCORE
from titlei.needs import HIGH_NEED, LOWER_NEED, NEED_GROUP
from titlei.runs import RunRecord
from titlei.simulate import CHANGE, PROJECTED
from titlei.theme import (
    INK_MUTED,
    INK_SECONDARY,
    MAX_SERIES,
    SURFACE,
    apply_theme,
    series_color,
)

apply_theme()

_MILLIONS = FuncFormatter(lambda v, _: f"${v / 1e6:,.0f}M")

#: Metrics worth ranking scenarios on, and whether more is better.
#:
#: Deliberately excludes ``student_points_per_million``: under the linear
#: impact model that quantity is identically ``1000 x impact_factor`` for every
#: allocation, so ranking on it would rank nothing. See
#: :func:`titlei.metrics.roi_metrics`.
SCORECARD_METRICS = {
    "academic_gap_closed_per_100m": (
        "Top-vs-bottom-quartile gap closed per $100M", True
    ),
    "academic_gap_closed": ("Top-vs-bottom-quartile gap closed (points)", True),
    "gap_closed_per_100m": ("Need-tier gap closed per $100M", True),
    "gap_closed": ("Need-tier gap closed (points)", True),
    "bottom_quartile_points_per_million": (
        "Student-points to the bottom quartile per $1M", True
    ),
    "bottom_quartile_mean_gain": ("Mean gain, bottom-quartile schools", True),
    "high_need_share_of_points": ("Share of gains reaching high-need schools", True),
    "high_need_share_of_budget": ("Share of budget to high-need schools", True),
    "students_reached_per_million": ("Students reached per $1M", True),
}

#: Shown wherever aggregate return is reported, so a flat column is never read
#: as a coding error.
INVARIANCE_NOTE = (
    "Total student-points = budget x impact_factor under this model, so "
    "aggregate return per dollar is identical for every allocation. What "
    "differs between scenarios is targeting: whose students the return reaches."
)

#: The other trap in cross-scenario comparison, surfaced wherever runs are
#: ranked.
TIER_DEFINITION_NOTE = (
    "'gap_closed' measures the gap between need tiers, and each scenario "
    "defines its own tiers from its own weights — so it is only comparable "
    "between runs that share a need index. 'academic_gap_closed' uses baseline "
    "score quartiles, which no scenario can move, and is the safe ranking metric."
)


def _check_count(records: list[RunRecord]) -> None:
    if not records:
        raise ValueError("nothing to compare: pass at least one run")
    if len(records) > MAX_SERIES:
        raise ValueError(
            f"comparing {len(records)} runs exceeds the {MAX_SERIES} validated "
            "colour slots; narrow the selection or compare them in batches"
        )


def _colors(records: list[RunRecord]) -> dict[str, str]:
    return {r.run_id: series_color(i) for i, r in enumerate(records)}


def _short(record: RunRecord, width: int = 34) -> str:
    label = record.label
    return label if len(label) <= width else label[: width - 1] + "…"


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def _declutter(values: list[float], min_gap: float) -> list[float]:
    """Push overlapping label positions apart, keeping their original order.

    Curves that converge produce end labels stacked on top of each other. This
    walks them from the top down and enforces a minimum vertical separation, so
    the labels stay next to their lines without colliding.
    """
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    adjusted = list(values)
    previous = None
    for index in order:
        y = adjusted[index]
        if previous is not None and y > previous - min_gap:
            y = previous - min_gap
        adjusted[index] = y
        previous = y
    return adjusted


def comparison_table(
    records: list[RunRecord], control: RunRecord | None = None
) -> pd.DataFrame:
    """One row per run, with deltas against the control.

    The control's own row shows zero deltas — it is the fixed point the rest
    are read against, not an omission.
    """
    _check_count(records)
    frame = pd.DataFrame([r.index_row() for r in records])

    if control is not None:
        baseline = control.index_row()
        for column, delta_name in (
            ("mean_score_change", "Δ mean gain"),
            ("academic_gap_closed", "Δ quartile gap closed"),
            ("high_need_share_of_budget", "Δ high-need budget share"),
        ):
            frame[delta_name] = frame[column] - baseline[column]
        frame.insert(
            1, "is_control", frame["run_id"] == control.run_id
        )
    return frame


def scorecard(
    records: list[RunRecord], metric: str = "student_points_per_million"
) -> pd.DataFrame:
    """Runs ranked on one metric, best first."""
    if metric not in SCORECARD_METRICS:
        raise ValueError(
            f"unknown metric {metric!r}; choose from {sorted(SCORECARD_METRICS)}"
        )
    _, higher_is_better = SCORECARD_METRICS[metric]
    frame = pd.DataFrame(
        [
            {"run_id": r.run_id, "label": r.label, metric: r.roi.get(metric, np.nan)}
            for r in records
        ]
    )
    return frame.sort_values(metric, ascending=not higher_is_better).reset_index(
        drop=True
    )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def overlay_projected_scores(
    records: list[RunRecord], control: RunRecord | None = None
) -> Figure:
    """Every school's projected score, sorted, one curve per run.

    Reading left to right is worst school to best. A curve that sits above
    another at the left has lifted the schools that were furthest behind; two
    curves that meet on the right mean the scenarios treat top schools alike.
    The dashed line is the status quo, before any allocation.
    """
    _check_count(records)
    colors = _colors(records)

    fig, ax = plt.subplots(figsize=(11, 6.5))

    reference = (control or records[0]).allocation
    if not reference.empty:
        before = np.sort(reference[SCORE].to_numpy())
        ax.plot(
            np.linspace(0, 100, len(before)),
            before,
            linestyle="--",
            linewidth=1.6,
            color=INK_MUTED,
            label="Before any allocation",
        )

    ends: list[tuple[float, str]] = []
    for record in records:
        frame = record.allocation
        if frame.empty:
            continue
        curve = np.sort(frame[PROJECTED].to_numpy())
        x = np.linspace(0, 100, len(curve))
        ax.plot(x, curve, color=colors[record.run_id], label=_short(record))
        ends.append((float(curve[-1]), f"{curve[-1]:.0f}"))

    if ends:
        low, high = ax.get_ylim()
        positions = _declutter([value for value, _ in ends], (high - low) * 0.035)
        for (value, text), y in zip(ends, positions):
            # Anchor the text at the decluttered height, and lead a short line
            # back to the curve it belongs to.
            ax.annotate(
                text,
                xy=(100, value),
                xytext=(104, y),
                textcoords="data",
                va="center",
                fontsize=9,
                color=INK_SECONDARY,
                annotation_clip=False,
                arrowprops={
                    "arrowstyle": "-",
                    "color": INK_MUTED,
                    "linewidth": 0.7,
                    "shrinkA": 1,
                    "shrinkB": 1,
                },
            )

    ax.set_title("Projected Regents scores across scenarios", pad=34)
    ax.text(
        0,
        1.015,
        "Schools sorted worst to best within each scenario",
        transform=ax.transAxes,
        fontsize=10,
        color=INK_MUTED,
        va="bottom",
    )
    ax.set_xlabel("Percentile of schools")
    ax.set_ylabel("Projected Regents score")
    ax.margins(x=0.04)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.1), ncol=2)
    fig.tight_layout()
    return fig


def overlay_budget_sweep(
    records: list[RunRecord], column: str = "Mean Score Change"
) -> Figure:
    """Each run's budget sensitivity curve, overlaid.

    Only the proposed strategy is plotted; the point of the chart is to compare
    parameter choices, not strategies.
    """
    _check_count(records)
    colors = _colors(records)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    plotted = 0
    for record in records:
        sweep = record.sweep
        if sweep.empty or column not in sweep.columns:
            continue
        subset = sweep[sweep["Strategy"] == "combined"].sort_values("Budget")
        if subset.empty:
            continue
        ax.plot(
            subset["Budget"],
            subset[column],
            marker="o",
            markersize=7,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            color=colors[record.run_id],
            label=_short(record),
        )
        last = subset.iloc[-1]
        ax.annotate(
            f"{last[column]:+.2f}",
            xy=(last["Budget"], last[column]),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK_SECONDARY,
        )
        plotted += 1

    if not plotted:
        ax.text(
            0.5,
            0.5,
            "No run in this comparison stored a budget sweep.\n"
            "Re-run without --no-sweep to populate it.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=INK_MUTED,
        )
        ax.grid(visible=False)
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        ax.set_xlabel("Discretionary budget")
        ax.set_ylabel(f"{column} (Regents points)")
        ax.xaxis.set_major_formatter(_MILLIONS)
        ax.margins(x=0.12)
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.1), ncol=2)

    ax.set_title(f"{column} vs budget, by scenario", pad=14)
    fig.tight_layout()
    return fig


def roi_comparison(
    records: list[RunRecord], metric: str = "academic_gap_closed_per_100m"
) -> Figure:
    """Rank scenarios on a targeting metric.

    Not on aggregate return per dollar: that is constant across allocations
    under this impact model, so it would rank nothing. See
    :data:`INVARIANCE_NOTE`.
    """
    _check_count(records)
    title, higher_is_better = SCORECARD_METRICS[metric]
    ranked = scorecard(records, metric)
    colors = _colors(records)

    y = np.arange(len(ranked))[::-1]
    fig, ax = plt.subplots(figsize=(11, 0.6 * len(ranked) + 3.5))
    bars = ax.barh(
        y,
        ranked[metric],
        height=0.62,
        color=[colors[rid] for rid in ranked["run_id"]],
    )
    for bar, value in zip(bars, ranked[metric]):
        ax.annotate(
            f"{value:,.3g}",
            xy=(value, bar.get_y() + bar.get_height() / 2),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=10,
            color=INK_SECONDARY,
        )

    ax.set_yticks(y)
    ax.set_yticklabels([_short(r, 44) for r in records_in_order(records, ranked)])
    ax.set_xlabel(title)
    ax.set_title(f"Scenarios ranked by {title.lower()}", pad=34)
    ax.text(
        0,
        1.015,
        f"{'Higher' if higher_is_better else 'Lower'} is better. "
        "Aggregate return per dollar is identical across scenarios; this is targeting.",
        transform=ax.transAxes,
        fontsize=10,
        color=INK_MUTED,
        va="bottom",
    )
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.12)
    fig.tight_layout()
    return fig


def records_in_order(
    records: list[RunRecord], ranked: pd.DataFrame
) -> list[RunRecord]:
    """Reorder ``records`` to match a ranked frame's run_id column."""
    by_id = {r.run_id: r for r in records}
    return [by_id[rid] for rid in ranked["run_id"]]


def tier_gain_comparison(records: list[RunRecord]) -> Figure:
    """Mean projected gain by need tier, one bar group per tier."""
    _check_count(records)
    colors = _colors(records)

    tiers = [HIGH_NEED, LOWER_NEED]
    x = np.arange(len(tiers))
    width = min(0.8 / len(records), 0.34)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    for i, record in enumerate(records):
        frame = record.allocation
        if frame.empty:
            continue
        means = [
            frame.loc[frame[NEED_GROUP] == tier, CHANGE].mean() if
            (frame[NEED_GROUP] == tier).any() else np.nan
            for tier in tiers
        ]
        offset = (i - (len(records) - 1) / 2) * (width + 0.01)
        bars = ax.bar(
            x + offset, means, width, color=colors[record.run_id], label=_short(record)
        )
        for bar, value in zip(bars, means):
            if np.isnan(value):
                continue
            ax.annotate(
                f"{value:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color=INK_SECONDARY,
            )

    ax.set_title("Mean projected gain by need tier, across scenarios", pad=14)
    ax.set_ylabel("Average score increase (points)")
    ax.set_xticks(x)
    ax.set_xticklabels(tiers)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=2)
    fig.tight_layout()
    return fig


def equity_vs_return(records: list[RunRecord]) -> Figure:
    """The trade-off chart: how well a scenario targets, against what it buys.

    Up and to the right is better on both axes. A scenario high on one and low
    on the other is the trade-off made explicit.

    Every point carries its own text label, so colour here is decoration rather
    than identity — which is what lets this chart carry more scenarios than the
    three the palette validates for side-by-side point comparison.
    """
    _check_count(records)
    colors = _colors(records)

    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    points = []
    for record in records:
        x = record.roi.get("high_need_share_of_budget", np.nan)
        y = record.roi.get("academic_gap_closed_per_100m", np.nan)
        ax.scatter(
            x, y, s=170, color=colors[record.run_id],
            edgecolor=SURFACE, linewidth=1.6, zorder=3,
        )
        points.append((x, y, _short(record, 26)))

    # Scenarios often cluster tightly, so lift the labels apart and lead a
    # line back to each point.
    if points:
        low, high = ax.get_ylim()
        left, right = ax.get_xlim()
        positions = _declutter([y for _, y, _ in points], (high - low) * 0.062)
        offset = (right - left) * 0.025
        for (x, y, text), label_y in zip(points, positions):
            ax.annotate(
                text,
                xy=(x, y),
                xytext=(x + offset, label_y),
                textcoords="data",
                va="center",
                fontsize=9,
                color=INK_SECONDARY,
                annotation_clip=False,
                arrowprops={
                    "arrowstyle": "-",
                    "color": INK_MUTED,
                    "linewidth": 0.7,
                    "shrinkA": 1,
                    "shrinkB": 5,
                },
            )

    ax.set_title("Targeting vs equity return", pad=34)
    ax.text(
        0,
        1.015,
        "Up and to the right is better on both axes",
        transform=ax.transAxes,
        fontsize=10,
        color=INK_MUTED,
        va="bottom",
    )
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("Share of budget directed to high-need schools")
    ax.set_ylabel("Top-vs-bottom-quartile gap closed per $100M")
    ax.margins(0.18)
    fig.tight_layout()
    return fig


def save_comparison(
    records: list[RunRecord],
    outdir: str | Path,
    control: RunRecord | None = None,
) -> dict[str, Path]:
    """Render every comparison chart to ``outdir``."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    figures = {
        "overlay_projected_scores": overlay_projected_scores(records, control),
        "tier_gain_comparison": tier_gain_comparison(records),
        "roi_comparison": roi_comparison(records),
        "equity_vs_return": equity_vs_return(records),
        "overlay_budget_sweep": overlay_budget_sweep(records),
    }
    paths = {}
    for slug, figure in figures.items():
        path = outdir / f"{slug}.png"
        figure.savefig(path)
        plt.close(figure)
        paths[slug] = path
    return paths
