from __future__ import annotations

import pytest

from titlei.pipeline import run_pipeline
from titlei.report import build_report


@pytest.fixture(scope="module")
def result():
    return run_pipeline(with_sweep=True)


def test_pipeline_produces_every_table(result):
    assert len(result.combined) == len(result.naive) == len(result.comparison)
    assert len(result.group_summary) == 2
    assert not result.sweep.empty
    assert not result.borough_summary.empty
    assert result.headline["budget_allocated"] == pytest.approx(500_000_000.0)


def test_pipeline_can_skip_the_sweep():
    result = run_pipeline(with_sweep=False)
    assert result.sweep.empty


def test_write_tables_emits_csvs(result, tmp_path):
    paths = result.write_tables(tmp_path)
    assert set(paths) >= {
        "combined_allocation",
        "naive_allocation",
        "group_summary",
        "budget_sweep",
        "headline_metrics",
    }
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0


def test_report_is_self_contained(result, tmp_path):
    path = build_report(result, tmp_path)
    document = path.read_text(encoding="utf-8")

    assert document.startswith("<!doctype html>")
    assert "data:image/png;base64," in document
    assert "http://" not in document and "https://" not in document
    assert (tmp_path / "charts").is_dir()
    assert len(list((tmp_path / "charts").glob("*.png"))) == 8


def test_report_builds_from_a_run_made_without_a_sweep(tmp_path):
    """build_report used to raise KeyError on a sweep-less result."""
    result = run_pipeline(with_sweep=False)
    path = build_report(result, tmp_path)

    assert path.exists()
    charts = {p.stem for p in (tmp_path / "charts").glob("*.png")}
    assert "budget_sweep" not in charts, "an empty sweep must not produce a chart"
    assert len(charts) == 7


def test_budget_sweep_chart_degrades_instead_of_raising():
    import matplotlib.pyplot as plt
    import pandas as pd

    from titlei.viz import budget_sweep, has_sweep_data

    empty = pd.DataFrame(columns=["Budget", "Strategy"])
    assert not has_sweep_data(empty)

    figure = budget_sweep(empty)
    assert figure is not None
    plt.close(figure)
