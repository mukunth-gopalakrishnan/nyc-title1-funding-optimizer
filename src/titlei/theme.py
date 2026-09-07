"""Shared chart theme.

Colours are the validated categorical slots 1-3 of the reference data-viz
palette (blue / orange / aqua), used in fixed order and never cycled.  No chart
in this package needs more than two series, which keeps every pair well clear
of the colour-vision-deficiency separation floor.
"""

from __future__ import annotations

import matplotlib as mpl

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#84837c"
GRID = "#e6e5e1"

SERIES_1 = "#2a78d6"  # blue    - the proposed / "after" series
SERIES_2 = "#eb6834"  # orange  - the baseline / "before" series
SERIES_3 = "#1baf7a"  # aqua    - reserved for a third series

BEFORE = SERIES_2
AFTER = SERIES_1

GROUP_COLORS = {
    "High-Need Schools": SERIES_1,
    "Lower-Need Schools": SERIES_2,
}

STRATEGY_COLORS = {
    "naive": SERIES_2,
    "combined": SERIES_1,
}

STRATEGY_LABELS = {
    "naive": "Baseline (financial need only)",
    "combined": "Proposed (financial + academic need)",
}


def apply_theme() -> None:
    """Install the package's matplotlib defaults process-wide."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_SECONDARY,
            "axes.titlecolor": INK,
            "axes.titlesize": 14,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.titlepad": 14,
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": INK_SECONDARY,
            "ytick.color": INK_SECONDARY,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.frameon": False,
            "legend.fontsize": 10,
            "legend.labelcolor": INK_SECONDARY,
            "font.size": 11,
            # Every label in this package is denominated in dollars; without this
            # a pair of "$" is parsed as a mathtext expression.
            "text.parse_math": False,
            "lines.linewidth": 2.0,
            "figure.dpi": 110,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )
