"""Chart builders.

Each function takes already-computed frames and returns a matplotlib Figure,
so the same chart can be saved to disk by the report builder or rendered live
by the Streamlit dashboard.  These recreate the Power BI report pages from the
original capstone submission.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

from titlei.config import ModelConfig
from titlei.data import ENROLLMENT, FUNDING_PER_PUPIL, SCHOOL, SCORE
from titlei.needs import HIGH_NEED, NEED_GROUP
from titlei.simulate import (
    CHANGE,
    EXTRA_PER_PUPIL,
    FUNDING_AFTER,
    PERCENT_INCREASE,
    PROJECTED,
)
from titlei.theme import (
    AFTER,
    BEFORE,
    GROUP_COLORS,
    INK_MUTED,
    INK_SECONDARY,
    STRATEGY_COLORS,
    STRATEGY_LABELS,
    SURFACE,
    apply_theme,
)

apply_theme()

_DOLLARS = FuncFormatter(lambda v, _: f"${v:,.0f}")
_MILLIONS = FuncFormatter(lambda v, _: f"${v / 1e6:,.0f}M")


def _annotate_bars(ax, bars, fmt: str, dy: int = 3) -> None:
    """Direct-label a bar series so identity never rests on colour alone."""
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            fmt.format(height),
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, dy),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK_SECONDARY,
        )


def _headline(ax, title: str, subtitle: str | None = None) -> None:
    """Set a title, and a subtitle above the axes that clears it."""
    ax.set_title(title, pad=34 if subtitle else 14)
    if subtitle:
        ax.text(
            0,
            1.015,
            subtitle,
            transform=ax.transAxes,
            fontsize=10,
            color=INK_MUTED,
            va="bottom",
        )


def _paired_bars(
    labels,
    before,
    after,
    *,
    title: str,
    ylabel: str,
    before_label: str,
    after_label: str,
    fmt: str,
    subtitle: str | None = None,
    figsize=(10, 6),
) -> Figure:
    """The grouped before/after bar chart used by several report pages."""
    x = np.arange(len(labels))
    width = 0.38
    gap = 0.01  # 2px-equivalent surface gap between adjacent fills

    fig, ax = plt.subplots(figsize=figsize)
    bars_before = ax.bar(
        x - width / 2 - gap, before, width, label=before_label, color=BEFORE
    )
    bars_after = ax.bar(
        x + width / 2 + gap, after, width, label=after_label, color=AFTER
    )

    _annotate_bars(ax, bars_before, fmt)
    _annotate_bars(ax, bars_after, fmt)

    _headline(ax, title, subtitle)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=2)
    fig.tight_layout()
    return fig


def score_by_need_group(summary: pd.DataFrame) -> Figure:
    """Average Regents score before vs after optimisation, by need tier."""
    return _paired_bars(
        summary[NEED_GROUP],
        summary["Before Score"],
        summary["After Score"],
        title="Average Regents score before vs after optimization",
        subtitle="Projected under the linear impact model; see methodology",
        ylabel="Average Regents score",
        before_label="Before",
        after_label="After optimization",
        fmt="{:.1f}",
    )


def funding_by_need_group(summary: pd.DataFrame) -> Figure:
    """Average per-pupil funding before vs after optimisation, by need tier."""
    fig = _paired_bars(
        summary[NEED_GROUP],
        summary["Funding Before"],
        summary["Funding After"],
        title="Average funding per student before vs after optimization",
        subtitle="Existing per-pupil funding plus the optimized discretionary award",
        ylabel="Funding per student",
        before_label="Before",
        after_label="After optimization",
        fmt="${:,.0f}",
    )
    fig.axes[0].yaxis.set_major_formatter(_DOLLARS)
    return fig


def funding_vs_score_scatter(frame: pd.DataFrame) -> Figure:
    """Per-pupil funding against Regents score, sized by enrollment."""
    fig, ax = plt.subplots(figsize=(10, 6.5))

    sizes = frame[ENROLLMENT] / frame[ENROLLMENT].max() * 320 + 20
    for group, color in GROUP_COLORS.items():
        subset = frame[frame[NEED_GROUP] == group]
        if subset.empty:
            continue
        ax.scatter(
            subset[FUNDING_PER_PUPIL],
            subset[SCORE],
            s=sizes.loc[subset.index],
            color=color,
            alpha=0.75,
            edgecolor=SURFACE,
            linewidth=1.5,
            label=group,
        )

    _headline(
        ax,
        "Funding per student vs average Regents score",
        "Bubble area is K-12 enrollment. Current funding, before optimization.",
    )
    ax.set_xlabel("Total school funding per pupil")
    ax.set_ylabel("Average Regents score")
    ax.xaxis.set_major_formatter(_DOLLARS)
    # Uniform legend swatches: bubble area encodes enrollment, not identity.
    handles = [
        Line2D(
            [], [], marker="o", linestyle="none", markersize=9,
            markerfacecolor=color, markeredgecolor=SURFACE, label=group,
        )
        for group, color in GROUP_COLORS.items()
        if (frame[NEED_GROUP] == group).any()
    ]
    ax.legend(handles=handles, loc="upper right")
    fig.tight_layout()
    return fig


def top_school_scores(frame: pd.DataFrame, n: int = 12) -> Figure:
    """Before/after Regents scores for the biggest high-need gainers."""
    top = frame.nlargest(n, CHANGE).sort_values(CHANGE)
    y = np.arange(len(top))
    height = 0.38

    fig, ax = plt.subplots(figsize=(10, 0.55 * len(top) + 3))
    ax.barh(y - height / 2 - 0.01, top[SCORE], height, color=BEFORE, label="Before")
    ax.barh(
        y + height / 2 + 0.01,
        top[PROJECTED],
        height,
        color=AFTER,
        label="After optimization",
    )

    for i, (before, after) in enumerate(zip(top[SCORE], top[PROJECTED])):
        ax.annotate(
            f"+{after - before:.1f}",
            xy=(after, i + height / 2 + 0.01),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK_SECONDARY,
        )

    ax.set_yticks(y)
    ax.set_yticklabels([s[:44] for s in top[SCHOOL]], fontsize=9)
    ax.set_xlabel("Average Regents score")
    _headline(ax, f"Largest projected score gains (top {len(top)} schools)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.06), ncol=2)
    fig.tight_layout()
    return fig


def top_school_funding(frame: pd.DataFrame, n: int = 12) -> Figure:
    """Per-pupil funding before/after for the biggest proportional gainers."""
    top = frame.nlargest(n, PERCENT_INCREASE).sort_values(PERCENT_INCREASE)
    y = np.arange(len(top))
    height = 0.38

    fig, ax = plt.subplots(figsize=(10, 0.55 * len(top) + 3))
    ax.barh(
        y - height / 2 - 0.01,
        top[FUNDING_PER_PUPIL],
        height,
        color=BEFORE,
        label="Before",
    )
    ax.barh(
        y + height / 2 + 0.01,
        top[FUNDING_AFTER],
        height,
        color=AFTER,
        label="After optimization",
    )

    for i, pct in enumerate(top[PERCENT_INCREASE]):
        ax.annotate(
            f"+{pct:.0f}%",
            xy=(top[FUNDING_AFTER].iloc[i], i + height / 2 + 0.01),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK_SECONDARY,
        )

    ax.set_yticks(y)
    ax.set_yticklabels([s[:44] for s in top[SCHOOL]], fontsize=9)
    ax.set_xlabel("Funding per student")
    ax.xaxis.set_major_formatter(_DOLLARS)
    _headline(
        ax, f"Largest proportional funding increases (top {len(top)} schools)"
    )
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.06), ncol=2)
    fig.tight_layout()
    return fig


def strategy_comparison(comparison: pd.DataFrame) -> Figure:
    """Mean projected score gain by need tier: baseline vs proposed model."""
    grouped = (
        comparison.groupby(NEED_GROUP)
        .agg(
            naive=("Score Change Naive", "mean"),
            combined=("Score Change Combined", "mean"),
        )
        .reset_index()
    )
    return _paired_bars(
        grouped[NEED_GROUP],
        grouped["naive"],
        grouped["combined"],
        title="Projected Regents gain by allocation strategy",
        subtitle="Same budget, two definitions of need",
        ylabel="Average score increase (points)",
        before_label=STRATEGY_LABELS["naive"],
        after_label=STRATEGY_LABELS["combined"],
        fmt="+{:.2f}",
    )


def has_sweep_data(sweep: pd.DataFrame, column: str = "Mean Score Change") -> bool:
    """Whether a sweep frame actually carries plottable results.

    A pipeline run with ``with_sweep=False`` produces an empty frame with only
    its key columns, so callers must be able to ask before charting it.
    """
    return not sweep.empty and column in sweep.columns


def budget_sweep(sweep: pd.DataFrame, column: str = "Mean Score Change") -> Figure:
    """How each strategy's projected gain scales with the budget."""
    fig, ax = plt.subplots(figsize=(10, 6))

    if not has_sweep_data(sweep, column):
        _headline(ax, "Budget sensitivity not available")
        ax.text(
            0.5,
            0.5,
            "This run was made without a budget sweep.\n"
            "Re-run without --no-sweep to populate it.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=INK_MUTED,
        )
        ax.grid(visible=False)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        return fig

    # The two curves converge at the top end, so nudge their end labels apart.
    label_offsets = {"naive": 9, "combined": -9}

    for strategy in ("naive", "combined"):
        subset = sweep[sweep["Strategy"] == strategy].sort_values("Budget")
        ax.plot(
            subset["Budget"],
            subset[column],
            marker="o",
            markersize=8,
            color=STRATEGY_COLORS[strategy],
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=STRATEGY_LABELS[strategy],
        )
        last = subset.iloc[-1]
        ax.annotate(
            f"{last[column]:+.2f}",
            xy=(last["Budget"], last[column]),
            xytext=(8, label_offsets[strategy]),
            textcoords="offset points",
            va="center",
            fontsize=10,
            color=INK_SECONDARY,
        )

    _headline(ax, f"{column} across discretionary budget scenarios")
    ax.set_xlabel("Discretionary budget")
    ax.set_ylabel(column + " (Regents points)")
    ax.xaxis.set_major_formatter(_MILLIONS)
    ax.margins(x=0.12)
    ax.legend(loc="upper left")
    fig.tight_layout()
    return fig


def award_tiers(frame: pd.DataFrame, config=None) -> Figure:
    """How many schools land at zero, partway, or at their per-pupil cap.

    The LP drives almost every school to a corner of its feasible region, so
    the awards are effectively three discrete outcomes rather than a smooth
    distribution — counts read far better here than a histogram would.
    """
    config = config or ModelConfig()
    caps = np.where(
        frame[NEED_GROUP] == HIGH_NEED,
        config.high_need_cap_per_pupil,
        config.low_need_cap_per_pupil,
    )
    per_pupil = frame[EXTRA_PER_PUPIL].to_numpy()

    at_cap = np.isclose(per_pupil, caps, rtol=1e-9, atol=1e-6)
    none = per_pupil <= 1e-9
    labels = ["No award", "Partial award", "At tier cap"]
    bucket = np.where(none, labels[0], np.where(at_cap, labels[2], labels[1]))

    counts = (
        pd.DataFrame({"bucket": bucket, "group": frame[NEED_GROUP].to_numpy()})
        .value_counts()
        .unstack(fill_value=0)
        .reindex(labels, fill_value=0)
    )
    for group in GROUP_COLORS:
        if group not in counts.columns:
            counts[group] = 0

    x = np.arange(len(labels))
    width = 0.38
    fig, ax = plt.subplots(figsize=(10, 6))
    for offset, (group, color) in zip((-1, 1), GROUP_COLORS.items()):
        bars = ax.bar(
            x + offset * (width / 2 + 0.01),
            counts[group],
            width,
            color=color,
            label=group,
        )
        _annotate_bars(ax, bars, "{:.0f}")

    _headline(
        ax,
        "Where the optimizer lands on each school",
        f"Caps: ${config.high_need_cap_per_pupil:,.0f} per pupil for high-need schools, "
        f"${config.low_need_cap_per_pupil:,.0f} for the rest",
    )
    ax.set_ylabel("Schools")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=2)
    fig.tight_layout()
    return fig


def save_all(
    *,
    combined: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    sweep: pd.DataFrame,
    outdir: str | Path,
    config=None,
) -> dict[str, Path]:
    """Render every chart to ``outdir`` and return the paths by slug."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    figures = {
        "score_by_need_group": score_by_need_group(summary),
        "funding_by_need_group": funding_by_need_group(summary),
        "funding_vs_score": funding_vs_score_scatter(combined),
        "top_school_scores": top_school_scores(combined),
        "top_school_funding": top_school_funding(combined),
        "strategy_comparison": strategy_comparison(comparison),
        "award_tiers": award_tiers(combined, config),
    }
    # A run made without a sweep has nothing to chart here; omit it rather
    # than writing an empty panel into the report.
    if has_sweep_data(sweep):
        figures["budget_sweep"] = budget_sweep(sweep)

    paths: dict[str, Path] = {}
    for slug, figure in figures.items():
        path = outdir / f"{slug}.png"
        figure.savefig(path)
        plt.close(figure)
        paths[slug] = path
    return paths
