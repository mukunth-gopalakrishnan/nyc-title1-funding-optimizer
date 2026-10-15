"""Commands the program suggests must work from where the user is.

Reported by a reviewer: after `./.venv/bin/titlei demo`, without activating the
environment, the demo ended with "titlei runs", "titlei wizard" and so on --
none of which work there. They should read `./.venv/bin/titlei runs`.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

import pytest

from titlei import invocation, launcher, selfcheck
from titlei.demo import run_demo
from titlei.invocation import command

BIN = "Scripts" if os.name == "nt" else "bin"
SCRIPT = invocation._script_name()
IN_VENV = os.curdir + os.sep + os.path.join(".venv", BIN, SCRIPT)  # ./.venv/bin/titlei


def _make_venv(project: Path) -> tuple[Path, Path]:
    bindir = project / ".venv" / BIN
    bindir.mkdir(parents=True)
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    python.write_text("")
    script = bindir / SCRIPT
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    return python, script


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project folder with a .venv holding this program, not activated."""
    folder = tmp_path / "project"
    python, script = _make_venv(folder)
    monkeypatch.setattr(sys, "executable", str(python))
    monkeypatch.setattr(invocation, "_script_dirs", lambda: [script.parent])
    monkeypatch.setenv("PATH", str(tmp_path / "nothing-here"))
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(folder)
    return folder


def test_outside_the_environment_the_venv_path_is_spelled_out(project):
    assert command("runs") == f"{IN_VENV} runs"


def test_inside_an_activated_environment_plain_titlei_is_enough(project, monkeypatch):
    monkeypatch.setenv("PATH", str(project / ".venv" / BIN))
    assert command("runs") == "titlei runs"


def test_a_different_titlei_on_path_is_not_trusted(project, tmp_path, monkeypatch):
    """Another installation's titlei would run other code, or a stale version."""
    other = tmp_path / "other"
    _make_venv(other)
    monkeypatch.setenv("PATH", str(other / ".venv" / BIN))
    assert command("runs") == f"{IN_VENV} runs"


def test_from_another_directory_the_path_is_absolute(project, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    script = project / ".venv" / BIN / SCRIPT
    assert command("runs").endswith(" runs")
    assert Path(command().strip('"').strip("'")) == script


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell quoting")
def test_paths_with_spaces_survive_being_pasted(tmp_path, monkeypatch):
    folder = tmp_path / "My Projects" / "title i"
    python, script = _make_venv(folder)
    monkeypatch.setattr(sys, "executable", str(python))
    monkeypatch.setattr(invocation, "_script_dirs", lambda: [script.parent])
    monkeypatch.setenv("PATH", str(tmp_path / "nothing-here"))
    monkeypatch.chdir(tmp_path)

    # Pasted into a shell, the path must stay one word despite its spaces.
    words = shlex.split(command("show 'Demo: proposed'"))
    assert words == [f"./{script.relative_to(tmp_path)}", "show", "Demo: proposed"]

    elsewhere = tmp_path / "elsewhere"  # outside the project: absolute path
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert shlex.split(command("runs")) == [str(script), "runs"]


def test_without_a_titlei_script_it_falls_back_to_python_m(project):
    (project / ".venv" / BIN / SCRIPT).unlink()
    python = os.curdir + os.sep + os.path.join(".venv", BIN, Path(sys.executable).name)
    assert command("runs") == f"{python} -m titlei runs"


def test_the_downloaded_program_names_itself(tmp_path, monkeypatch):
    """The download is called titlei-macos-arm64 and is not on PATH."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "titlei-macos-arm64"))
    monkeypatch.chdir(tmp_path)
    assert command("--help") == f"{os.curdir}{os.sep}titlei-macos-arm64 --help"


# --- where the suggestions are printed ----------------------------------------


def test_the_demo_tips_work_without_activating(project, tmp_path):
    """The reviewer's case, end to end."""
    lines: list[str] = []
    run_demo(out_dir=tmp_path / "out", runs_dir=tmp_path / "runs",
             build_html=False, emit=lines.append)
    text = "\n".join(lines)
    tips = text[text.index("What to do next"):]

    for suggestion in ("runs", "wizard", "dashboard", "show 'Demo: proposed"):
        assert f"{IN_VENV} {suggestion}" in tips
    assert f"equivalent command:  {IN_VENV} describe" in text
    bare = [line for line in lines if line.lstrip().startswith("titlei ")]
    assert not bare, f"bare `titlei` suggestions remain: {bare}"


def test_the_demo_tips_stay_aligned(project, tmp_path):
    lines: list[str] = []
    run_demo(out_dir=tmp_path / "out", runs_dir=tmp_path / "runs",
             build_html=False, emit=lines.append)
    commented = [line for line in lines if "  # " in line and IN_VENV in line]
    assert len({line.index("  # ") for line in commented}) == 1


def test_the_double_clicked_download_suggests_its_own_name(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "titlei-macos-arm64"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher, "OUTPUT_DIR", tmp_path / "titlei-output")
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: None)

    assert launcher.main([]) == 0
    out = capsys.readouterr().out
    assert f"{os.curdir}{os.sep}titlei-macos-arm64 verify" in out
    assert "    titlei " not in out


def test_missing_packages_are_installed_with_this_pythons_pip(project, monkeypatch):
    """A bare `pip` outside the environment can belong to another Python."""
    monkeypatch.setattr(selfcheck, "REQUIRED_PACKAGES", ("yaml", "not_a_real_package_xyz"))
    result = selfcheck._check_packages()
    python = os.curdir + os.sep + os.path.join(".venv", BIN, Path(sys.executable).name)
    assert result.remedy == f"Run: {python} -m pip install not_a_real_package_xyz"
