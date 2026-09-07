"""Command line entry point: ``titlei <command>``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from titlei import __version__
from titlei.config import DEFAULT_CONFIG_PATH, ModelConfig, load_config
from titlei.data import load_schools
from titlei.pipeline import run_pipeline
from titlei.report import build_report
from titlei.simulate import sweep_budgets

logger = logging.getLogger("titlei")

OVERRIDES = {
    "budget": "extra_budget",
    "financial_weight": "financial_weight",
    "academic_weight": "academic_weight",
    "high_need_cap": "high_need_cap_per_pupil",
    "low_need_cap": "low_need_cap_per_pupil",
    "impact_factor": "impact_factor",
    "min_frpl_pct": "min_frpl_pct",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="titlei",
        description="Optimize discretionary funding across NYC Title I high schools.",
    )
    parser.add_argument("--version", action="version", version=f"titlei {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="log pipeline progress"
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", type=Path, default=None, help="path to the school CSV")
    common.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="model config YAML"
    )
    common.add_argument("--budget", type=float, help="override the discretionary budget")
    common.add_argument("--financial-weight", type=float, dest="financial_weight")
    common.add_argument("--academic-weight", type=float, dest="academic_weight")
    common.add_argument("--high-need-cap", type=float, dest="high_need_cap")
    common.add_argument("--low-need-cap", type=float, dest="low_need_cap")
    common.add_argument("--impact-factor", type=float, dest="impact_factor")
    common.add_argument("--min-frpl-pct", type=float, dest="min_frpl_pct")

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run", parents=[common], help="run the model and write CSV outputs"
    )
    run.add_argument("--out", type=Path, default=Path("outputs"))
    run.add_argument(
        "--no-sweep", action="store_true", help="skip the budget sensitivity sweep"
    )

    report = sub.add_parser(
        "report", parents=[common], help="run the model and build the HTML report"
    )
    report.add_argument("--out", type=Path, default=Path("outputs"))

    sweep = sub.add_parser(
        "sweep", parents=[common], help="compare strategies across budgets"
    )
    sweep.add_argument("--out", type=Path, default=None, help="write the sweep to CSV")
    sweep.add_argument(
        "--budgets",
        type=float,
        nargs="+",
        default=None,
        help="budgets to evaluate, in dollars",
    )

    sub.add_parser("describe", parents=[common], help="summarise the input data")

    return parser


def _config_from_args(args: argparse.Namespace) -> ModelConfig:
    config = load_config(args.config)
    changes = {
        field: getattr(args, flag)
        for flag, field in OVERRIDES.items()
        if getattr(args, flag, None) is not None
    }
    # Keep the need index normalised when only one side is overridden.
    if "financial_weight" in changes and "academic_weight" not in changes:
        changes["academic_weight"] = 1.0 - changes["financial_weight"]
    elif "academic_weight" in changes and "financial_weight" not in changes:
        changes["financial_weight"] = 1.0 - changes["academic_weight"]
    return config.replace(**changes) if changes else config


def _cmd_run(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    result = run_pipeline(args.data, config, with_sweep=not args.no_sweep)
    paths = result.write_tables(args.out / "tables")

    print(result.load_report.summary())
    print(
        f"combined: allocated ${result.combined_allocation.budget_used:,.0f} "
        f"({result.combined_allocation.budget_utilisation:.1%} of budget) across "
        f"{result.combined_allocation.schools_funded} schools"
    )
    print(
        f"baseline: allocated ${result.naive_allocation.budget_used:,.0f} across "
        f"{result.naive_allocation.schools_funded} schools"
    )
    print()
    print(result.group_summary.to_string(index=False))
    print()
    for name, path in paths.items():
        print(f"wrote {name}: {path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    result = run_pipeline(args.data, config)
    path = build_report(result, args.out)
    print(f"wrote report: {path}")
    print(f"wrote charts: {args.out / 'charts'}")
    print(f"wrote tables: {args.out / 'tables'}")
    return 0


def _cmd_sweep(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    schools, report = load_schools(args.data, config)
    budgets = tuple(args.budgets) if args.budgets else None
    frame = sweep_budgets(schools, config, budgets)

    print(report.summary())
    with pd.option_context("display.float_format", "{:,.3f}".format):
        print(frame.to_string(index=False))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.out, index=False)
        print(f"\nwrote {args.out}")
    return 0


def _cmd_describe(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    schools, report = load_schools(args.data, config)

    print(report.summary())
    print()
    described = schools.describe().T[["count", "mean", "std", "min", "50%", "max"]]
    with pd.option_context("display.float_format", "{:,.2f}".format):
        print(described.to_string())
    if "Borough" in schools.columns:
        print("\nSchools by borough:")
        print(schools["Borough"].value_counts().to_string())
    return 0


COMMANDS = {
    "run": _cmd_run,
    "report": _cmd_report,
    "sweep": _cmd_sweep,
    "describe": _cmd_describe,
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
