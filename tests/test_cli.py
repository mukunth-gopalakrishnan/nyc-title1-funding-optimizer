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
