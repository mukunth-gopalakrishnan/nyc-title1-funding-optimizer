"""A narrated end-to-end walkthrough, for someone who has just cloned this.

`titlei demo` takes no arguments and no prior knowledge. It runs the published
scenario, runs the status-quo baseline against it, compares the two, and writes
the report — narrating each step so the output explains itself rather than
needing the README open alongside.

Everything it does is an ordinary command the user could have typed; the
narration names each one, so the demo doubles as a tour of the CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from titlei import compare as compare_mod
from titlei import metrics
from titlei.config import ModelConfig, load_config
from titlei.data import load_schools
from titlei.needs import NEED_GROUP
from titlei.pipeline import run_pipeline
from titlei.report import build_report
from titlei.runs import RunRegistry
from titlei.simulate import CHANGE

Emit = Callable[[str], None]

RULE = "-" * 72

PROPOSED_LABEL = "Demo: proposed (financial + academic)"
BASELINE_LABEL = "Demo: baseline (financial need only)"


def _step(emit: Emit, number: int, title: str, command: str) -> None:
    emit("")
    emit(RULE)
    emit(f"Step {number} — {title}")
    emit(f"  equivalent command:  {command}")
    emit(RULE)


def run_demo(
    out_dir: str | Path = "outputs/demo",
    runs_dir: str | Path = "runs",
    config_path: str | Path | None = None,
    emit: Emit = print,
    build_html: bool = True,
) -> dict[str, object]:
    """Run the walkthrough. Returns the artefacts it produced."""
    out_dir = Path(out_dir)
    config: ModelConfig = load_config(config_path)
    registry = RunRegistry(runs_dir)

    # The demo owns these two labels and suggests looking them up by name, so
    # it replaces its previous runs rather than making the names ambiguous.
    for label in (PROPOSED_LABEL, BASELINE_LABEL):
        registry.delete_by_label(label)

    emit("")
    emit("NYC Title I Funding Optimizer — guided demo")
    emit("Nothing here is simulated output; every number is computed as you watch.")

    # --- 1. the data -----------------------------------------------------
    _step(emit, 1, "Load the schools", "titlei describe")
    schools, load_report = load_schools(None, config)
    emit(f"  {load_report.summary()}")
    emit(
        f"  {len(schools)} schools, "
        f"{int(schools['K-12 Enrollment'].sum()):,} students, "
        f"Regents average {schools['Avg Regents Score'].mean():.1f}"
    )

    # --- 2. the proposed model -------------------------------------------
    _step(emit, 2, "Run the proposed model", "titlei run --label 'Demo: proposed'")
    proposed = run_pipeline(None, config, with_sweep=True)
    summary = proposed.group_summary
    emit(
        f"  Allocated ${proposed.combined_allocation.budget_used:,.0f} across "
        f"{proposed.combined_allocation.schools_funded} schools."
    )
    emit("")
    for _, row in summary.iterrows():
        emit(
            f"  {row[NEED_GROUP]:<20} {row['Before Score']:.1f} -> "
            f"{row['After Score']:.1f}  ({row['Score Change']:+.2f} pts, "
            f"${row['Extra Per Pupil']:,.0f}/pupil, "
            f"{row['Share of Budget']:.0%} of budget)"
        )
    proposed_run = registry.save(proposed, PROPOSED_LABEL)

    # --- 3. the status quo ------------------------------------------------
    _step(
        emit, 3, "Run the status-quo baseline",
        "titlei run --financial-weight 1.0 --label 'Demo: baseline'",
    )
    baseline_config = config.replace(financial_weight=1.0, academic_weight=0.0)
    baseline = run_pipeline(None, baseline_config, with_sweep=False)
    baseline_run = registry.save(baseline, BASELINE_LABEL)
    emit("  The DOE's current practice: rank schools on poverty alone.")
    emit(
        f"  Allocated ${baseline.combined_allocation.budget_used:,.0f} across "
        f"{baseline.combined_allocation.schools_funded} schools."
    )

    # --- 4. compare -------------------------------------------------------
    _step(emit, 4, "Compare them", "titlei compare")
    records = [proposed_run, baseline_run]
    emit("  Ranked by how much of the top-vs-bottom-quartile gap each closes")
    emit("  per $100M. Those quartiles come from baseline scores, so neither")
    emit("  scenario can move the goalposts.")
    emit("")
    ranked = compare_mod.scorecard(records, "academic_gap_closed_per_100m")
    for _, row in ranked.iterrows():
        emit(f"    {row['label']:<42} {row['academic_gap_closed_per_100m']:.3f}")

    best, worst = ranked.iloc[0], ranked.iloc[-1]
    if worst["academic_gap_closed_per_100m"] > 0:
        ratio = (
            best["academic_gap_closed_per_100m"]
            / worst["academic_gap_closed_per_100m"]
        )
        emit("")
        emit(f"  {best['label']} targets {ratio:.1f}x better on the same money.")

    emit("")
    emit("  Careful: aggregate return per dollar is IDENTICAL for both.")
    emit("  Under a linear impact model total gain is budget x impact_factor,")
    emit("  whatever the allocation. Only targeting differs. (docs/methodology.md 4a)")

    # --- 5. artefacts -----------------------------------------------------
    _step(emit, 5, "Write the outputs", "titlei report")
    tables = proposed.write_tables(out_dir / "tables")
    charts = compare_mod.save_comparison(records, out_dir / "comparison", proposed_run)
    report_path = build_report(proposed, out_dir) if build_html else None

    emit(f"  {len(tables)} CSV tables       {out_dir / 'tables'}")
    emit(f"  {len(charts)} comparison charts  {out_dir / 'comparison'}")
    if report_path:
        emit(f"  1 HTML report        {report_path}")

    # --- where to go next -------------------------------------------------
    emit("")
    emit(RULE)
    emit("What to do next")
    emit(RULE)
    if report_path:
        emit(f"  open {report_path}")
    emit("  titlei runs                  # the two runs you just made")
    emit(f"  titlei show '{PROPOSED_LABEL}'")
    emit("  titlei wizard                # build your own scenario, guided")
    if not getattr(sys, "frozen", False):  # the no-Python download has no dashboard
        emit("  titlei dashboard             # the interactive simulation, in your browser")
    emit("")

    return {
        "proposed": proposed_run,
        "baseline": baseline_run,
        "report": report_path,
        "tables": tables,
        "charts": charts,
        "headline": metrics.headline_metrics(
            proposed.combined, config.extra_budget
        ),
        "mean_gain": float(proposed.combined[CHANGE].mean()),
    }
