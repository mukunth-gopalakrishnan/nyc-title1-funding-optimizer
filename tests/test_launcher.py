"""The downloadable binary's entry point: a double-click must do something useful."""

from __future__ import annotations

import pytest
import yaml

from titlei import launcher

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_arguments_are_passed_straight_to_the_cli(capsys):
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(["--version"])
    assert excinfo.value.code == 0
    assert "titlei" in capsys.readouterr().out


def test_no_arguments_runs_the_guided_demo_and_opens_the_report(
    tmp_path, monkeypatch, capsys
):
    """What a double-click does: demo, report, browser — then exit cleanly."""
    opened = []
    monkeypatch.setattr(launcher, "OUTPUT_DIR", tmp_path / "titlei-output")
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

    assert launcher.main([]) == 0

    report = tmp_path / "titlei-output" / "demo" / "report.html"
    assert report.is_file()
    assert opened and opened[0].endswith("report.html")
    assert "titlei verify" in capsys.readouterr().out


def test_a_missing_browser_does_not_crash_the_launcher(tmp_path, monkeypatch):
    def no_browser(_url):
        raise RuntimeError("no display")

    monkeypatch.setattr(launcher, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(launcher.webbrowser, "open", no_browser)
    assert launcher.main([]) == 0


def test_build_script_bundles_the_package_data():
    script = (ROOT / "packaging" / "build_binary.py").read_text(encoding="utf-8")
    assert '"--collect-data", "titlei"' in script
    assert '"--onefile"' in script


def test_release_workflow_builds_and_smoke_tests_every_platform():
    wf = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    matrix = wf["jobs"]["build"]["strategy"]["matrix"]["include"]
    assert {m["os"] for m in matrix} == {"ubuntu-latest", "windows-latest", "macos-latest"}

    steps = wf["jobs"]["build"]["steps"]
    smoke = next(s for s in steps if s.get("name") == "Smoke-test the binary")
    # It must run outside the checkout, or it could pass on the repo's data.
    assert 'cd "$RUNNER_TEMP"' in smoke["run"]
    assert "verify" in smoke["run"]
