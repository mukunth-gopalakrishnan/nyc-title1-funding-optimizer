"""End-to-end orchestration: raw data in, tables and metrics out."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from titlei import metrics
from titlei.config import ModelConfig
from titlei.data import LoadReport, load_schools
from titlei.optimizer import AllocationResult
from titlei.simulate import compare_strategies, run_scenario, sweep_budgets

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Everything one run of the model produces."""

    config: ModelConfig
    load_report: LoadReport
    combined: pd.DataFrame
    naive: pd.DataFrame
    comparison: pd.DataFrame
    group_summary: pd.DataFrame
    borough_summary: pd.DataFrame
    sweep: pd.DataFrame
    headline: dict[str, float]
    roi: dict[str, float]
    combined_allocation: AllocationResult
    naive_allocation: AllocationResult

    def write_tables(self, outdir: str | Path) -> dict[str, Path]:
        """Persist every output table as CSV — the dashboards' table view."""
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)

        tables = {
            "combined_allocation": self.combined,
            "naive_allocation": self.naive,
            "strategy_comparison": self.comparison,
            "group_summary": self.group_summary,
            "borough_summary": self.borough_summary,
            "budget_sweep": self.sweep,
            "headline_metrics": pd.DataFrame(
                sorted(self.headline.items()), columns=["metric", "value"]
            ),
            "roi_metrics": pd.DataFrame(
                sorted(self.roi.items()), columns=["metric", "value"]
            ),
        }
        paths: dict[str, Path] = {}
        for name, frame in tables.items():
            if frame is None or frame.empty:
                continue
            path = outdir / f"{name}.csv"
            frame.to_csv(path, index=False)
            paths[name] = path
        return paths


def run_pipeline(
    data_path: str | Path | None = None,
    config: ModelConfig | None = None,
    *,
    with_sweep: bool = True,
) -> PipelineResult:
    """Run both allocation strategies and assemble every reporting table."""
    config = config or ModelConfig()
    schools, load_report = load_schools(data_path, config)
    logger.info(load_report.summary())

    combined, combined_allocation = run_scenario(schools, config, strategy="combined")
    naive, naive_allocation = run_scenario(schools, config, strategy="naive")

    sweep = (
        sweep_budgets(schools, config)
        if with_sweep
        else pd.DataFrame(columns=["Budget", "Strategy"])
    )

    return PipelineResult(
        config=config,
        load_report=load_report,
        combined=combined,
        naive=naive,
        comparison=compare_strategies(combined, naive),
        group_summary=metrics.group_summary(combined),
        borough_summary=metrics.borough_summary(combined),
        sweep=sweep,
        headline=metrics.headline_metrics(combined, config.extra_budget),
        roi=metrics.roi_metrics(combined, combined_allocation.budget_used),
        combined_allocation=combined_allocation,
        naive_allocation=naive_allocation,
    )
