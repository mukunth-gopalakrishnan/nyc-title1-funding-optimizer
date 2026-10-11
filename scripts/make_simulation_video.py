"""Render the annotated simulation video of the allocation model.

    pip install -e ".[video]"
    python scripts/make_simulation_video.py simulation.mp4

One input changes -- the budget -- while everything else is held fixed. Every
frame is a live LP solve. Callouts mark the input and the outputs, a caption
explains each phase, and the video holds at the start, at the published $500M
scenario and at the end so there is time to read. About 47 seconds, 1920x1080.
"""

from __future__ import annotations

import sys

import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter, FuncAnimation
from matplotlib.patches import FancyBboxPatch

from titlei.config import ModelConfig
from titlei.data import SCORE, load_schools
from titlei.metrics import academic_gap
from titlei.simulate import FUNDING, PROJECTED, run_scenario
from titlei.theme import (
    INK,
    INK_MUTED,
    INK_SECONDARY,
    SERIES_1,
    SERIES_2,
    SERIES_3,
    apply_theme,
)

FPS = 8
INPUT = SERIES_3  # aqua marks the one thing the viewer controls
INPUT_TINT = "#e3f5ee"
OUTPUT_TINT = "#eef1f6"

CAPTIONS = {
    "intro": "You control one number: the budget to hand out.  "
    "Everything else is held fixed.  Watch what changes.",
    "early": "Small budgets go to the neediest schools first, so the left end "
    "of the blue line lifts before anything else.",
    "mid": "The proposed model (blue) keeps lifting the lowest-scoring schools.  "
    "The status quo (orange) spreads the money wider.",
    "late": "Past about $510M every school has hit its per-pupil cap.  "
    "Extra money has nowhere to go, so nothing moves.",
    "outro": "Takeaway: where the money goes matters more than how much.  "
    "At every budget, the proposed model closes the gap further.",
}


def ramp(start: float, stop: float, seconds: float) -> list[float]:
    return list(np.linspace(start, stop, int(seconds * FPS)))


def hold(value: float, seconds: float) -> list[float]:
    return [value] * int(seconds * FPS)


def build_schedule() -> list[tuple[float, str]]:
    """One (budget, caption key) pair per frame, holds included."""
    phases = [
        (hold(10e6, 5.5), "intro"),
        (ramp(10e6, 300e6, 11), "early"),
        (ramp(300e6, 500e6, 8), "mid"),
        (hold(500e6, 6.5), "pub"),
        (ramp(500e6, 1_000e6, 10), "late"),
        (hold(1_000e6, 6), "outro"),
    ]
    return [(budget, key) for budgets, key in phases for budget in budgets]


class Simulation:
    """Solves each distinct budget once, for both strategies."""

    def __init__(self) -> None:
        self.config = ModelConfig()
        self.baseline_config = self.config.replace(
            financial_weight=1.0, academic_weight=0.0
        )
        self.schools, _ = load_schools(None, self.config)
        self.before = np.sort(self.schools[SCORE].to_numpy())
        self.x = np.linspace(0, 100, len(self.before))
        self.gap_before = academic_gap(
            self.schools.assign(**{PROJECTED: self.schools[SCORE]}), SCORE
        )
        self.cut = self.schools[SCORE].quantile(0.25)
        self.cache: dict[float, dict] = {}

    def solve(self, budget: float) -> dict:
        key = round(budget, -4)
        if key not in self.cache:
            row = {}
            for name, cfg in (("proposed", self.config), ("baseline", self.baseline_config)):
                frame, alloc = run_scenario(
                    self.schools, cfg, strategy="combined", budget=float(budget)
                )
                bottom = frame.loc[frame[SCORE] <= self.cut, FUNDING].sum()
                row[name] = {
                    "curve": np.sort(frame[PROJECTED].to_numpy()),
                    "gap": self.gap_before - academic_gap(frame, PROJECTED),
                    "bottom": bottom / max(alloc.budget_used, 1.0),
                }
            self.cache[key] = row
        return self.cache[key]


def tag(fig, x: float, y: float, text: str, tint: str):
    """A rounded label; tint carries the input/output distinction, text stays ink."""
    label = fig.text(
        x, y, text, fontsize=12.5, fontweight="bold", color=INK, va="center",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": tint, "edgecolor": "none"},
    )
    label.dynamic = True
    return label


def arrow(ax, xy, xytext, color=INK_SECONDARY, rad=0.2, width=1.8) -> None:
    ax.annotate(
        "", xy=xy, xycoords="data", xytext=xytext, textcoords="figure fraction",
        annotation_clip=False,
        arrowprops={
            "arrowstyle": "-|>", "color": color, "lw": width,
            "shrinkA": 2, "shrinkB": 2, "connectionstyle": f"arc3,rad={rad}",
        },
    )


def bar_pair(ax, values, fmt: str, ylim: float, ylabel: str) -> None:
    bars = ax.bar(["Status quo", "Proposed"], values, width=0.55,
                  color=[SERIES_2, SERIES_1])
    for bar, value in zip(bars, values):
        ax.annotate(
            fmt.format(value), (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 3), textcoords="offset points", ha="center",
            fontsize=12, color=INK_SECONDARY,
        )
    ax.set_ylim(0, ylim)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(axis="x", visible=False)
    ax.tick_params(labelsize=10.5)


def main(out: str) -> None:
    apply_theme()
    plt.rcParams["text.parse_math"] = False

    sim = Simulation()
    schedule = build_schedule()
    print(f"{len(schedule)} frames ({len(schedule) / FPS:.0f}s); solving...", flush=True)
    for budget, _ in schedule:
        sim.solve(budget)

    # The closing caption makes a claim about every budget; check it, don't assume it.
    assert all(r["proposed"]["gap"] >= r["baseline"]["gap"] - 1e-9 for r in sim.cache.values())

    published = sim.solve(500e6)
    captions = dict(CAPTIONS)
    captions["pub"] = (
        "$500M is the published scenario.  The proposed model closes the gap "
        f"{published['proposed']['gap']:.2f} points; the status quo "
        f"{published['baseline']['gap']:.2f}."
    )

    fig = plt.figure(figsize=(16, 9))
    fig.patch.set_facecolor("#fcfcfb")
    ax_in = fig.add_axes([0.065, 0.765, 0.555, 0.055])
    ax_main = fig.add_axes([0.065, 0.165, 0.555, 0.465])
    ax_gap = fig.add_axes([0.715, 0.455, 0.255, 0.175])
    ax_bot = fig.add_axes([0.715, 0.165, 0.255, 0.175])

    fig.text(0.065, 0.955, "What changes when the budget changes?", fontsize=25,
             fontweight="bold", color=INK, va="top")
    fig.text(0.065, 0.905,
             "349 NYC Title I high schools  ·  every frame is a live optimization",
             fontsize=13, color=INK_MUTED, va="top")
    fig.text(0.715, 0.835, "HELD FIXED", fontsize=11, fontweight="bold",
             color=INK_MUTED, va="top")
    fig.text(0.715, 0.805,
             "Need score: 30% financial / 70% academic\n"
             "Per-pupil cap: $5,000 high-need, $1,500 others\n"
             "Guaranteed $50,000 for schools scoring below 60",
             fontsize=11.5, color=INK_SECONDARY, va="top", linespacing=1.6)
    caption = fig.text(
        0.065, 0.055, "", fontsize=15, color=INK, va="center",
        bbox={"boxstyle": "round,pad=0.6", "facecolor": "#f4f6fa", "edgecolor": "none"},
    )
    budget_text = fig.text(0.62, 0.858, "", fontsize=22, fontweight="bold",
                           color=INK, va="center", ha="right")

    def draw(i: int):
        budget, phase = schedule[i]
        row = sim.solve(budget)
        for ax in (ax_in, ax_main, ax_gap, ax_bot):
            ax.clear()
        for text in [t for t in fig.texts if getattr(t, "dynamic", False)]:
            text.remove()

        # 1  INPUT: the budget slider
        ax_in.set_xlim(-35e6, 1_035e6)
        ax_in.set_ylim(0, 1)
        ax_in.axis("off")
        for width, color in ((1_000e6, "#e6e5e1"), (budget, INPUT)):
            ax_in.add_patch(FancyBboxPatch(
                (0, 0.35), width, 0.3, boxstyle="round,pad=0,rounding_size=0.15",
                facecolor=color, edgecolor="none", mutation_aspect=1e-8,
            ))
        ax_in.plot([budget], [0.5], "o", ms=20, color="white", mec=INPUT, mew=4, zorder=5)
        for tick in (0, 250e6, 500e6, 750e6, 1_000e6):
            ax_in.text(tick, -0.25, f"${tick / 1e6:,.0f}M", ha="center", va="top",
                       fontsize=10, color=INK_MUTED)
        budget_text.set_text(f"${budget / 1e6:,.0f}M")
        tag(fig, 0.065, 0.858, "1   YOUR INPUT — the budget", INPUT_TINT)
        arrow(ax_in, (budget, 0.86), (0.165, 0.838), color=INPUT, rad=0, width=2.4)

        # 2  OUTPUT: every school's projected score
        x = sim.x
        ax_main.plot(x, sim.before, ls="--", lw=2, color=INK_MUTED, label="Before any money")
        ax_main.plot(x, row["baseline"]["curve"], lw=3, color=SERIES_2,
                     label="Status quo (financial need only)")
        ax_main.plot(x, row["proposed"]["curve"], lw=3, color=SERIES_1,
                     label="Proposed (financial + academic need)")
        ax_main.fill_between(
            x, row["baseline"]["curve"], row["proposed"]["curve"],
            where=row["proposed"]["curve"] >= row["baseline"]["curve"],
            color=SERIES_1, alpha=0.14, interpolate=True,
        )
        ax_main.axvspan(0, 25, color=SERIES_1, alpha=0.05)
        ax_main.text(12.5, 46.5, "lowest-scoring quarter", ha="center",
                     fontsize=10.5, color=INK_MUTED)
        ax_main.set_xlim(0, 100)
        ax_main.set_ylim(45, 97)
        ax_main.set_xlabel("Schools, ranked from lowest to highest score", fontsize=12)
        ax_main.set_ylabel("Projected Regents score", fontsize=12)
        ax_main.legend(loc="lower right", fontsize=11.5)
        tag(fig, 0.065, 0.668, "2   CHANGES — each school's projected score", OUTPUT_TINT)
        arrow(ax_main, (14, row["proposed"]["curve"][int(len(x) * 0.14)]), (0.15, 0.652))

        # 3  OUTPUT: achievement gap closed
        gaps = [row["baseline"]["gap"], row["proposed"]["gap"]]
        bar_pair(ax_gap, gaps, "{:.2f}", 4.7, "Points")
        tag(fig, 0.715, 0.668, "3   CHANGES — gap closed", OUTPUT_TINT)
        arrow(ax_gap, (1, gaps[1] + 0.62), (0.875, 0.652), rad=-0.2)

        # 4  OUTPUT: money reaching the lowest-scoring quarter
        shares = [row["baseline"]["bottom"] * 100, row["proposed"]["bottom"] * 100]
        bar_pair(ax_bot, shares, "{:.0f}%", 112, "Share of budget (%)")
        tag(fig, 0.715, 0.378, "4   CHANGES — money to bottom quarter", OUTPUT_TINT)
        arrow(ax_bot, (1, shares[1] + 15), (0.905, 0.362), rad=-0.2)

        caption.set_text(captions[phase])
        return []

    print("encoding...", flush=True)
    anim = FuncAnimation(fig, draw, frames=len(schedule), blit=False)
    anim.save(out, writer=FFMpegWriter(
        fps=FPS, bitrate=4500, metadata={"title": "NYC Title I Funding Optimizer"},
    ), dpi=120)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "simulation.mp4")
