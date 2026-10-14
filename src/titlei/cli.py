"""Command line entry point: ``titlei <command>``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

from titlei import __version__
from titlei import compare as compare_mod
from titlei.config import DEFAULT_CONFIG_PATH, ModelConfig, load_config
from titlei.dashboard import DEFAULT_PORT, DashboardUnavailable
from titlei.dashboard import launch as launch_dashboard
from titlei.data import load_schools
from titlei.demo import run_demo
from titlei.pipeline import run_pipeline
from titlei.report import build_report
from titlei.runs import DEFAULT_RUNS_DIR, AmbiguousRunReference, RunNotFound, RunRegistry
from titlei.selfcheck import FAIL, run_checks, summarise
from titlei.simulate import sweep_budgets
from titlei.wizard import QUESTIONS, WizardAborted, run_wizard, save_config

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

    # `-v` reads naturally on either side of the subcommand, so accept both.
    # SUPPRESS keeps the subparser from overwriting a top-level `-v` with its
    # own default when the flag was given before the subcommand.
    verbosity = argparse.ArgumentParser(add_help=False)
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="log pipeline progress",
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

    registry_args = argparse.ArgumentParser(add_help=False)
    registry_args.add_argument(
        "--runs-dir", type=Path, default=DEFAULT_RUNS_DIR, help="run registry directory"
    )

    run = sub.add_parser(
        "run",
        parents=[common, registry_args, verbosity],
        help="run the model, write CSV outputs, and register the run",
    )
    run.add_argument("--out", type=Path, default=Path("outputs"))
    run.add_argument(
        "--no-sweep", action="store_true", help="skip the budget sensitivity sweep"
    )
    run.add_argument("--label", help="name this run in the registry")
    run.add_argument("--notes", default="", help="free-text note stored with the run")
    run.add_argument(
        "--no-register", action="store_true", help="do not save this run to the registry"
    )
    run.add_argument(
        "--control", action="store_true", help="make this run the comparison control"
    )
    run.add_argument(
        "--replace",
        action="store_true",
        help="delete any existing run with this label first, so the name stays unique",
    )

    report = sub.add_parser(
        "report", parents=[common, verbosity], help="run the model and build the HTML report"
    )
    report.add_argument("--out", type=Path, default=Path("outputs"))

    sweep = sub.add_parser(
        "sweep", parents=[common, verbosity], help="compare strategies across budgets"
    )
    sweep.add_argument("--out", type=Path, default=None, help="write the sweep to CSV")
    sweep.add_argument(
        "--budgets",
        type=float,
        nargs="+",
        default=None,
        help="budgets to evaluate, in dollars",
    )

    sub.add_parser(
        "describe", parents=[common, verbosity], help="summarise the input data"
    )

    wizard = sub.add_parser(
        "wizard",
        parents=[registry_args, verbosity],
        help="answer a questionnaire to build and run a scenario",
    )
    wizard.add_argument(
        "--save", type=Path, default=None, help="write the scenario to this YAML path"
    )
    wizard.add_argument(
        "--no-run", action="store_true", help="build the scenario but do not run it"
    )
    wizard.add_argument("--data", type=Path, default=None)
    wizard.add_argument("--out", type=Path, default=Path("outputs"))
    wizard.add_argument(
        "--answers",
        type=Path,
        default=None,
        help="YAML of pre-supplied answers; unanswered questions are still asked",
    )
    wizard.add_argument(
        "--defaults",
        action="store_true",
        help="accept every default without prompting",
    )

    verify = sub.add_parser(
        "verify",
        parents=[verbosity],
        help="check that this installation works, and reproduces the published results",
    )
    verify.add_argument("--data", type=Path, default=None)
    verify.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    verify.add_argument("--out", type=Path, default=Path("outputs"))

    demo = sub.add_parser(
        "demo",
        parents=[registry_args, verbosity],
        help="guided end-to-end walkthrough; no arguments or prior knowledge needed",
    )
    demo.add_argument("--out", type=Path, default=Path("outputs/demo"))
    demo.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    demo.add_argument(
        "--no-report", action="store_true", help="skip building the HTML report"
    )

    dashboard = sub.add_parser(
        "dashboard",
        parents=[registry_args, verbosity],
        help="open the interactive simulation in your browser",
    )
    dashboard.add_argument(
        "--port", type=int, default=None,
        help=f"port to serve on (default: the first free one from {DEFAULT_PORT})",
    )
    dashboard.add_argument(
        "--no-browser", action="store_true",
        help="start the dashboard without opening a browser",
    )

    runs = sub.add_parser(
        "runs", parents=[registry_args, verbosity], help="list registered runs"
    )
    runs.add_argument("--set-control", metavar="REF", help="mark a run as the control")
    runs.add_argument("--delete", metavar="REF", help="remove a run from the registry")

    show = sub.add_parser(
        "show", parents=[registry_args, verbosity],
        help="show one run's parameters and results"
    )
    show.add_argument("ref", help="run id, id prefix, config hash, or label")

    compare = sub.add_parser(
        "compare",
        parents=[registry_args, verbosity],
        help="overlay several runs and rank them",
    )
    compare.add_argument(
        "refs", nargs="*", help="runs to compare; defaults to every registered run"
    )
    compare.add_argument("--control", metavar="REF", help="override the control run")
    compare.add_argument("--out", type=Path, default=Path("outputs/comparison"))
    compare.add_argument(
        "--metric",
        default="academic_gap_closed_per_100m",
        choices=sorted(compare_mod.SCORECARD_METRICS),
        help="metric to rank scenarios on",
    )
    compare.add_argument(
        "--no-charts", action="store_true", help="print the table only"
    )

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

    if not args.no_register:
        registry = RunRegistry(args.runs_dir)
        if args.replace:
            if not args.label:
                print("error: --replace needs --label to know what to replace")
                return 1
            removed = registry.delete_by_label(args.label)
            if removed:
                print(f"\nreplaced {len(removed)} earlier run(s) labelled {args.label!r}")
        record = registry.save(
            result,
            label=args.label,
            notes=args.notes,
            make_control=args.control,
        )
        print()
        print(f"registered run {record.run_id}")
        print(f"  label   {record.label}")
        print(f"  params  {record.config_hash} (fingerprint of this parameter set)")
        # Never the aggregate return: it is identically 1000 x impact_factor
        # for every allocation, so printing it invites exactly the misreading
        # docs/methodology.md 4a warns about.
        print(f"  targeting  {record.roi['high_need_share_of_budget']:.1%} of budget "
              f"to high-need, quartile gap closed "
              f"{record.roi['academic_gap_closed']:.2f} pts")
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


def _print_frame(frame: pd.DataFrame, floatfmt: str = "{:,.3f}") -> None:
    if frame.empty:
        print("(nothing to show)")
        return
    with pd.option_context(
        "display.float_format", floatfmt.format, "display.width", 200,
        "display.max_columns", 40,
    ):
        print(frame.to_string(index=False))


def _cmd_wizard(args: argparse.Namespace) -> int:
    answers = {}
    if args.answers:
        with args.answers.open(encoding="utf-8") as handle:
            answers = yaml.safe_load(handle) or {}
    if args.defaults:
        answers = {q.key: answers.get(q.key, q.default) for q in QUESTIONS}

    try:
        config, label = run_wizard(answers=answers)
    except WizardAborted:
        print("\naborted; nothing was run")
        return 1

    if args.save:
        print(f"\nwrote scenario: {save_config(config, args.save)}")

    if args.no_run:
        return 0

    print("\nrunning...")
    result = run_pipeline(args.data, config)
    record = RunRegistry(args.runs_dir).save(result, label=label or None)

    print()
    print(result.group_summary.to_string(index=False))
    print()
    print(f"registered run {record.run_id}")
    print(f"  label      {record.label}")
    print(f"  targeting  {record.roi['high_need_share_of_budget']:.1%} of budget "
          f"to high-need, quartile gap closed "
          f"{record.roi['academic_gap_closed']:.2f} pts")
    print("\ncompare it against the control with:  titlei compare")
    return 0


def _cmd_runs(args: argparse.Namespace) -> int:
    registry = RunRegistry(args.runs_dir)

    if args.set_control:
        record = registry.set_control(args.set_control)
        print(f"control is now {record.run_id} ({record.label})")
        return 0
    if args.delete:
        print(f"deleted {registry.delete(args.delete)}")
        return 0

    table = registry.table()
    if table.empty:
        print("no runs registered yet — try `titlei run` or `titlei wizard`")
        return 0

    view = table[[
        "run_id", "control", "label", "budget", "financial_weight",
        "high_need_cap", "low_need_cap", "impact_factor",
        "mean_score_change", "academic_gap_closed",
    ]]
    _print_frame(view)
    print(f"\n{len(table)} run(s) in {registry.root}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    record = RunRegistry(args.runs_dir).resolve(args.ref)

    print(f"run {record.run_id}")
    print(f"  label        {record.label}")
    print(f"  created      {record.created_at}")
    print(f"  param hash   {record.config_hash}")
    print(f"  data         {record.load_summary}")
    if record.notes:
        print(f"  notes        {record.notes}")
    print("\nParameters")
    for key, value in sorted(record.config.to_dict().items()):
        print(f"  {key:<26} {value}")
    print("\nResults")
    for key, value in sorted({**record.headline, **record.roi}.items()):
        print(f"  {key:<26} {value:,.4f}")
    return 0


def _narrow_to_recent(records, control, limit: int):
    """Keep the control plus the most recent runs, up to ``limit``."""
    recent = [r for r in records if control is None or r.run_id != control.run_id]
    recent.sort(key=lambda r: r.created_at, reverse=True)
    keep = recent[: limit - 1] if control is not None else recent[:limit]
    return ([control] + keep) if control is not None else keep


def _cmd_compare(args: argparse.Namespace) -> int:
    registry = RunRegistry(args.runs_dir)
    records = (
        registry.resolve_all(args.refs) if args.refs else registry.list()
    )
    if not records:
        print("no runs registered yet — try `titlei run` or `titlei wizard`")
        return 1

    control = (
        registry.resolve(args.control) if args.control else registry.control
    )
    if control is not None and control.run_id not in {r.run_id for r in records}:
        records = [control, *records]

    if len(records) > compare_mod.MAX_SERIES:
        if args.refs:
            # The user named them, so say which to drop rather than choosing.
            print(
                f"error: {len(records)} runs exceeds the "
                f"{compare_mod.MAX_SERIES} distinguishable colours. Name at most "
                f"{compare_mod.MAX_SERIES}, or compare them in batches."
            )
            return 1
        # No selection given: keep the control and the most recent runs, so the
        # bare `titlei compare` always works however full the registry is.
        records = _narrow_to_recent(records, control, compare_mod.MAX_SERIES)
        print(
            f"note: showing the control and the {len(records) - 1} most recent "
            f"runs; name runs explicitly to choose a different set.\n"
        )

    table = compare_mod.comparison_table(records, control)
    columns = [c for c in [
        "run_id", "is_control", "label", "budget", "financial_weight",
        "high_need_cap", "low_need_cap", "mean_score_change",
        "academic_gap_closed", "academic_gap_closed_per_100m",
        "high_need_share_of_budget",
        "mean gain vs control", "quartile gap closed vs control", "high-need share vs control",
    ] if c in table.columns]
    _print_frame(table[columns])
    print(f"\nnote: {compare_mod.INVARIANCE_NOTE}")
    print(f"note: {compare_mod.TIER_DEFINITION_NOTE}")

    label, higher_is_better = compare_mod.SCORECARD_METRICS[args.metric]
    ranked = compare_mod.scorecard(records, args.metric)
    print(f"\nRanked by {label} ({'higher' if higher_is_better else 'lower'} is better)")
    _print_frame(ranked[["label", args.metric]])
    best = ranked.iloc[0]
    print(f"\nbest: {best['label']}  ({best[args.metric]:,.2f})")

    if not args.no_charts:
        paths = compare_mod.save_comparison(records, args.out, control)
        print()
        for slug, path in paths.items():
            print(f"wrote {slug}: {path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    print("Verifying the installation...\n")
    results = run_checks(args.data, args.config, args.out)
    for result in results:
        print(result.line())

    passed, failed, skipped = summarise(results)
    print()
    print(f"{passed} passed, {failed} failed, {skipped} skipped")

    if failed:
        print("\nWhat to do:")
        for result in results:
            if result.status == FAIL and result.remedy:
                print(f"  - {result.name}: {result.remedy}")
        return 1

    print("\nThis installation works. Try:  titlei demo")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    run_demo(
        out_dir=args.out,
        runs_dir=args.runs_dir,
        config_path=args.config,
        build_html=not args.no_report,
    )
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    try:
        return launch_dashboard(
            args.runs_dir, port=args.port, open_browser=not args.no_browser
        )
    except DashboardUnavailable as exc:
        print(f"error: {exc}")
        return 1


COMMANDS = {
    "run": _cmd_run,
    "verify": _cmd_verify,
    "demo": _cmd_demo,
    "dashboard": _cmd_dashboard,
    "report": _cmd_report,
    "sweep": _cmd_sweep,
    "describe": _cmd_describe,
    "wizard": _cmd_wizard,
    "runs": _cmd_runs,
    "show": _cmd_show,
    "compare": _cmd_compare,
}


def _make_output_robust() -> None:
    """Never let the console's codepage crash a command.

    On Windows, redirected or piped output falls back to the ANSI codepage
    (cp1252), which cannot encode every character a scenario label or school
    name might contain. Substituting an unencodable character is better than a
    UnicodeEncodeError halfway through a run. UTF-8 terminals are unaffected.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):  # not a TextIOWrapper, or detached
            pass


def main(argv: list[str] | None = None) -> int:
    _make_output_robust()
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return COMMANDS[args.command](args)
    except (RunNotFound, AmbiguousRunReference) as exc:
        print(f"error: {exc.args[0]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
