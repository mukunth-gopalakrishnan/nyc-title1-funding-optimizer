"""Cross-run comparison, including the two ways it can quietly mislead."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pytest

from titlei import compare
from titlei.config import ModelConfig
from titlei.metrics import academic_gap, roi_metrics
from titlei.pipeline import run_pipeline
from titlei.runs import RunRegistry
from titlei.simulate import CHANGE
from titlei.theme import MAX_SERIES


@pytest.fixture(scope="module")
def records(tmp_path_factory):
    root = tmp_path_factory.mktemp("runs")
    registry = RunRegistry(root)
    base = ModelConfig()
    registry.save(run_pipeline(config=base), "Control", make_control=True)
    registry.save(
        run_pipeline(config=base.replace(extra_budget=250e6)), "Half budget"
    )
    registry.save(
        run_pipeline(config=base.replace(financial_weight=1.0, academic_weight=0.0)),
        "Financial only",
    )
    return registry.list(), registry


def test_aggregate_return_is_invariant_to_allocation(records):
    """The identity the ROI metrics are built around, asserted directly.

    Total student-points = budget x impact_factor, whatever the allocation. If
    this ever fails, the impact model stopped being linear and the ROI
    docstrings need rewriting.
    """
    for record in records[0]:
        frame = record.allocation
        student_points = (frame["K-12 Enrollment"] * frame[CHANGE]).sum()
        expected = record.roi["budget_used"] * record.config.impact_factor
        assert student_points == pytest.approx(expected, rel=1e-9)


def test_the_scorecard_never_ranks_on_the_invariant_metric():
    assert "student_points_per_million" not in compare.SCORECARD_METRICS
    assert "cost_per_student_point" not in compare.SCORECARD_METRICS


def test_academic_gap_uses_groups_no_scenario_can_move(records):
    """Fixed quartiles, unlike need tiers, mean the goalposts stay put."""
    control, *_ = records[0]
    frame = control.allocation
    assert academic_gap(frame, "Avg Regents Score") == pytest.approx(
        academic_gap(frame.sample(frac=1, random_state=0), "Avg Regents Score")
    )


def test_targeting_metrics_discriminate_between_scenarios(records):
    values = {
        r.label: r.roi["academic_gap_closed_per_100m"] for r in records[0]
    }
    assert len(set(np.round(list(values.values()), 6))) == len(values)


def test_financial_only_closes_the_academic_gap_least(records):
    """The capstone's central claim, on a scenario-independent yardstick."""
    by_label = {r.label: r.roi for r in records[0]}
    assert (
        by_label["Financial only"]["academic_gap_closed"]
        < by_label["Control"]["academic_gap_closed"]
    )


def test_comparison_table_reports_deltas_against_the_control(records):
    all_records, registry = records
    table = compare.comparison_table(all_records, registry.control)

    control_row = table[table["is_control"]]
    assert len(control_row) == 1
    assert control_row["mean gain vs control"].iloc[0] == pytest.approx(0.0)
    assert control_row["quartile gap closed vs control"].iloc[0] == pytest.approx(0.0)


def test_comparison_table_works_without_a_control(records):
    table = compare.comparison_table(records[0], None)
    assert "mean gain vs control" not in table.columns
    assert len(table) == 3


def test_scorecard_orders_by_the_metrics_direction(records):
    ranked = compare.scorecard(records[0], "academic_gap_closed_per_100m")
    assert ranked["academic_gap_closed_per_100m"].is_monotonic_decreasing


def test_unknown_metric_is_rejected(records):
    with pytest.raises(ValueError, match="unknown metric"):
        compare.scorecard(records[0], "vibes")


def test_comparing_nothing_is_an_error():
    with pytest.raises(ValueError, match="at least one run"):
        compare.comparison_table([])


def test_too_many_runs_is_refused_rather_than_recycling_colours(records):
    with pytest.raises(ValueError, match="colour slots"):
        compare.comparison_table(records[0] * (MAX_SERIES + 1))


def test_every_comparison_chart_renders(records, tmp_path):
    paths = compare.save_comparison(records[0], tmp_path, records[1].control)
    assert set(paths) == {
        "overlay_projected_scores",
        "tier_gain_comparison",
        "roi_comparison",
        "equity_vs_return",
        "overlay_budget_sweep",
    }
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0


def test_sweep_overlay_degrades_gracefully_without_sweep_data(tmp_path):
    registry = RunRegistry(tmp_path / "runs")
    registry.save(run_pipeline(with_sweep=False), "No sweep")
    figure = compare.overlay_budget_sweep(registry.list())
    assert figure is not None
    plt.close(figure)


def test_declutter_separates_collisions_and_keeps_order():
    values = [10.0, 10.0, 10.0]
    spread = compare._declutter(values, 1.0)
    assert spread == sorted(spread, reverse=True)
    assert min(np.diff(sorted(spread))) >= 1.0 - 1e-9


def test_declutter_leaves_separated_values_alone():
    values = [10.0, 5.0, 1.0]
    assert compare._declutter(values, 1.0) == values


def test_roi_metrics_survive_a_zero_budget(records):
    frame = records[0][0].allocation.copy()
    frame["Score Change"] = 0.0
    frame["Optimized_Funding"] = 0.0
    roi = roi_metrics(frame, 0.0)
    assert roi["student_points_per_million"] == 0.0
    assert roi["gap_closed_per_100m"] == 0.0
