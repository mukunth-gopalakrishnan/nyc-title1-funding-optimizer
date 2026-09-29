from __future__ import annotations

import pytest

from titlei.cli import _build_parser, main


def test_run_writes_outputs(tmp_path, capsys):
    assert main([
        "run", "--no-sweep", "--out", str(tmp_path),
        "--runs-dir", str(tmp_path / "runs"),
    ]) == 0
    out = capsys.readouterr().out
    assert "schools retained" in out
    assert (tmp_path / "tables" / "combined_allocation.csv").exists()


def test_report_builds_html(tmp_path, capsys):
    assert main(["report", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "report.html").exists()
    assert "wrote report" in capsys.readouterr().out


def test_sweep_accepts_explicit_budgets(tmp_path, capsys):
    path = tmp_path / "sweep.csv"
    assert main(["sweep", "--budgets", "1e8", "2e8", "--out", str(path)]) == 0
    assert path.exists()
    assert "combined" in capsys.readouterr().out


def test_describe_summarises_inputs(capsys):
    assert main(["describe"]) == 0
    out = capsys.readouterr().out
    assert "Schools by borough" in out


def test_budget_override_changes_the_allocation(tmp_path, capsys):
    main([
        "run", "--no-sweep", "--budget", "100000000", "--out", str(tmp_path),
        "--runs-dir", str(tmp_path / "runs"),
    ])
    assert "$100,000,000" in capsys.readouterr().out


def test_a_single_weight_override_renormalises(tmp_path):
    """Setting only one side of the need index must not raise."""
    assert main([
        "run", "--no-sweep", "--financial-weight", "0.6", "--out", str(tmp_path),
        "--runs-dir", str(tmp_path / "runs"),
    ]) == 0


def test_version_flag_exits_cleanly():
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0


# --- run registry, comparison and the questionnaire ------------------------


def test_run_registers_and_show_reports_the_parameters(tmp_path, capsys):
    runs = tmp_path / "runs"
    main([
        "run", "--no-sweep", "--budget", "250000000",
        "--label", "Quarter billion", "--out", str(tmp_path), "--runs-dir", str(runs),
    ])
    assert "registered run" in capsys.readouterr().out

    assert main(["show", "Quarter billion", "--runs-dir", str(runs)]) == 0
    out = capsys.readouterr().out
    assert "extra_budget" in out
    assert "250000000" in out.replace(",", "")


def test_no_register_leaves_the_registry_untouched(tmp_path):
    runs = tmp_path / "runs"
    main([
        "run", "--no-sweep", "--no-register",
        "--out", str(tmp_path), "--runs-dir", str(runs),
    ])
    assert not runs.exists()


def test_runs_listing_distinguishes_scenarios(tmp_path, capsys):
    runs = tmp_path / "runs"
    for budget, label in (("250000000", "Half"), ("500000000", "Full")):
        main([
            "run", "--no-sweep", "--budget", budget, "--label", label,
            "--out", str(tmp_path), "--runs-dir", str(runs),
        ])
    capsys.readouterr()

    assert main(["runs", "--runs-dir", str(runs)]) == 0
    out = capsys.readouterr().out
    assert "Half" in out and "Full" in out
    assert "2 run(s)" in out


def test_compare_ranks_and_warns_about_the_invariance(tmp_path, capsys):
    runs = tmp_path / "runs"
    main([
        "run", "--no-sweep", "--label", "Control",
        "--out", str(tmp_path), "--runs-dir", str(runs), "--control",
    ])
    main([
        "run", "--no-sweep", "--financial-weight", "1.0", "--label", "Financial",
        "--out", str(tmp_path), "--runs-dir", str(runs),
    ])
    capsys.readouterr()

    assert main([
        "compare", "--runs-dir", str(runs), "--out", str(tmp_path / "cmp"),
    ]) == 0
    out = capsys.readouterr().out
    assert "aggregate return per dollar is identical" in out
    assert "only comparable between runs that share a need index" in out
    assert "best:" in out
    assert (tmp_path / "cmp" / "overlay_projected_scores.png").exists()


def test_compare_without_charts_writes_nothing(tmp_path, capsys):
    runs = tmp_path / "runs"
    main(["run", "--no-sweep", "--out", str(tmp_path), "--runs-dir", str(runs)])
    capsys.readouterr()
    main([
        "compare", "--no-charts", "--runs-dir", str(runs),
        "--out", str(tmp_path / "cmp"),
    ])
    assert not (tmp_path / "cmp").exists()


def test_unknown_run_reference_fails_cleanly(tmp_path, capsys):
    runs = tmp_path / "runs"
    main(["run", "--no-sweep", "--out", str(tmp_path), "--runs-dir", str(runs)])
    capsys.readouterr()
    assert main(["show", "nope", "--runs-dir", str(runs)]) == 1
    assert "error:" in capsys.readouterr().out


def test_set_control_moves_the_reference(tmp_path, capsys):
    runs = tmp_path / "runs"
    main([
        "run", "--no-sweep", "--label", "A",
        "--out", str(tmp_path), "--runs-dir", str(runs),
    ])
    main([
        "run", "--no-sweep", "--budget", "3e8", "--label", "B",
        "--out", str(tmp_path), "--runs-dir", str(runs),
    ])
    capsys.readouterr()
    assert main(["runs", "--set-control", "B", "--runs-dir", str(runs)]) == 0
    assert "control is now" in capsys.readouterr().out


def test_wizard_with_defaults_runs_without_prompting(tmp_path, capsys):
    runs = tmp_path / "runs"
    saved = tmp_path / "scenario.yaml"
    assert main([
        "wizard", "--defaults", "--save", str(saved),
        "--runs-dir", str(runs), "--out", str(tmp_path),
    ]) == 0
    out = capsys.readouterr().out
    assert "registered run" in out
    assert saved.exists()


def test_wizard_can_build_a_scenario_without_running_it(tmp_path, capsys):
    runs = tmp_path / "runs"
    saved = tmp_path / "scenario.yaml"
    assert main([
        "wizard", "--defaults", "--no-run", "--save", str(saved),
        "--runs-dir", str(runs),
    ]) == 0
    assert saved.exists()
    assert not runs.exists()


def test_wizard_answers_file_is_honoured(tmp_path, capsys):
    import yaml as _yaml

    answers = tmp_path / "answers.yaml"
    answers.write_text(_yaml.safe_dump({"budget_millions": 800, "label": "Eight"}))
    saved = tmp_path / "scenario.yaml"

    assert main([
        "wizard", "--defaults", "--answers", str(answers), "--no-run",
        "--save", str(saved), "--runs-dir", str(tmp_path / "runs"),
    ]) == 0
    assert _yaml.safe_load(saved.read_text())["extra_budget"] == 800e6


# --- flag placement --------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["-v", "describe"],
        ["describe", "-v"],
        ["-v", "describe", "-v"],
    ],
    ids=["before", "after", "both"],
)
def test_verbose_is_accepted_on_either_side_of_the_subcommand(argv, capsys):
    """CI runs `titlei report --out outputs -v`; both placements must work."""
    assert main(argv) == 0


def test_verbose_after_the_subcommand_actually_enables_logging(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="titlei.data"):
        main(["run", "--no-sweep", "--no-register", "--out", str(tmp_path), "-v"])
    assert any("schools retained" in r.message for r in caplog.records)


def test_verbose_before_the_subcommand_is_not_reset_by_the_subparser(
    tmp_path, caplog
):
    """The argparse trap: a subparser default must not clobber the outer flag."""
    import logging

    with caplog.at_level(logging.INFO, logger="titlei.data"):
        main(["-v", "run", "--no-sweep", "--no-register", "--out", str(tmp_path)])
    assert any("schools retained" in r.message for r in caplog.records)


def test_omitting_verbose_leaves_logging_quiet(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="titlei.data"):
        main(["runs", "--runs-dir", str(tmp_path / "none")])
    assert not caplog.records


@pytest.mark.parametrize(
    "command",
    ["run", "report", "sweep", "describe", "wizard", "runs", "show", "compare"],
)
def test_every_subcommand_accepts_a_trailing_verbose(command):
    """Guards against a new subcommand forgetting the shared verbosity parent."""
    parser = _build_parser()
    argv = [command, "-v"]
    if command == "show":
        argv = [command, "some-ref", "-v"]
    args = parser.parse_args(argv)
    assert args.verbose is True


# --- onboarding: verify and demo -------------------------------------------


def test_verify_passes_on_a_healthy_install(tmp_path, capsys):
    assert main(["verify", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Reproduces published results" in out
    assert "0 failed" in out
    assert "titlei demo" in out


def test_verify_exits_nonzero_and_advises_on_failure(tmp_path, capsys):
    assert main(["verify", "--data", str(tmp_path / "gone.csv"), "--out", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "What to do:" in out


def test_demo_runs_with_no_arguments_beyond_paths(tmp_path, capsys):
    assert main([
        "demo", "--no-report",
        "--out", str(tmp_path / "out"), "--runs-dir", str(tmp_path / "runs"),
    ]) == 0
    out = capsys.readouterr().out
    assert "Step 1" in out and "Step 5" in out
    assert "What to do next" in out


# --- compare must never traceback on a full registry ------------------------


def _register(count, runs_dir, out_dir):
    for i in range(count):
        main([
            "run", "--no-sweep", "--budget", str(1e8 + i * 1e7),
            "--label", f"Scenario {i}", "--out", str(out_dir),
            "--runs-dir", str(runs_dir),
        ])


def test_bare_compare_works_with_more_runs_than_colour_slots(tmp_path, capsys):
    """`make scenarios` hit a raw traceback here when runs already existed."""
    from titlei.compare import MAX_SERIES

    runs = tmp_path / "runs"
    _register(MAX_SERIES + 3, runs, tmp_path)
    capsys.readouterr()

    assert main([
        "compare", "--no-charts", "--runs-dir", str(runs),
        "--out", str(tmp_path / "cmp"),
    ]) == 0
    out = capsys.readouterr().out
    assert "most recent" in out
    assert "Traceback" not in out
    assert "best:" in out


def test_bare_compare_keeps_the_control_when_it_narrows(tmp_path, capsys):
    from titlei.compare import MAX_SERIES
    from titlei.runs import RunRegistry

    runs = tmp_path / "runs"
    _register(MAX_SERIES + 3, runs, tmp_path)
    control = RunRegistry(runs).set_control("Scenario 0")  # the oldest
    capsys.readouterr()

    main(["compare", "--no-charts", "--runs-dir", str(runs), "--out", str(tmp_path)])
    assert control.label in capsys.readouterr().out


def test_naming_too_many_runs_is_a_clean_error_not_a_traceback(tmp_path, capsys):
    from titlei.compare import MAX_SERIES

    runs = tmp_path / "runs"
    _register(MAX_SERIES + 1, runs, tmp_path)
    capsys.readouterr()

    refs = [f"Scenario {i}" for i in range(MAX_SERIES + 1)]
    assert main(["compare", *refs, "--no-charts", "--runs-dir", str(runs)]) == 1
    out = capsys.readouterr().out
    assert "error:" in out
    assert "in batches" in out
    assert "Traceback" not in out


def test_run_replace_keeps_one_run_per_label(tmp_path, capsys):
    runs = tmp_path / "runs"
    for budget in ("1e8", "2e8"):
        main([
            "run", "--no-sweep", "--budget", budget, "--label", "Nightly",
            "--replace", "--out", str(tmp_path), "--runs-dir", str(runs),
        ])
    capsys.readouterr()

    assert main(["show", "Nightly", "--runs-dir", str(runs)]) == 0
    out = capsys.readouterr().out
    assert "200000000" in out.replace(",", "")


def test_run_replace_requires_a_label(tmp_path, capsys):
    assert main([
        "run", "--no-sweep", "--replace",
        "--out", str(tmp_path), "--runs-dir", str(tmp_path / "runs"),
    ]) == 1
    assert "needs --label" in capsys.readouterr().out


# --- the no-activation entry point ------------------------------------------


def test_module_entry_point_exists():
    """`python -m titlei` is the documented way to run without activating."""
    import importlib.util

    assert importlib.util.find_spec("titlei.__main__") is not None


def test_module_entry_point_runs_the_cli(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "titlei", "verify", "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Reproduces published results" in result.stdout
