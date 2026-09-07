from __future__ import annotations

import pytest

from titlei.cli import main


def test_run_writes_outputs(tmp_path, capsys):
    assert main(["run", "--no-sweep", "--out", str(tmp_path)]) == 0
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
    main(["run", "--no-sweep", "--budget", "100000000", "--out", str(tmp_path)])
    assert "$100,000,000" in capsys.readouterr().out


def test_a_single_weight_override_renormalises(tmp_path):
    """Setting only one side of the need index must not raise."""
    assert main(
        ["run", "--no-sweep", "--financial-weight", "0.6", "--out", str(tmp_path)]
    ) == 0


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
