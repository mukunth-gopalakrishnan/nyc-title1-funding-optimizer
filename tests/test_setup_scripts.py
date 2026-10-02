"""The setup scripts are the first thing a downloader runs.

They cannot be executed here for every platform, so these check the properties
that break silently: the executable bit surviving a download, and the two
scripts agreeing on what they create.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "scripts" / "setup.sh"
PS1 = ROOT / "scripts" / "setup.ps1"


def test_both_platform_scripts_exist():
    assert SH.exists(), "macOS/Linux users need scripts/setup.sh"
    assert PS1.exists(), "Windows users need scripts/setup.ps1"


def test_the_shell_script_is_executable():
    """A downloader runs `./scripts/setup.sh`; without +x that fails."""
    assert os.access(SH, os.X_OK)


def test_git_records_the_executable_bit():
    """The mode must survive `git clone` and GitHub's Download ZIP."""
    out = subprocess.run(
        ["git", "ls-files", "-s", "scripts/setup.sh"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    assert out.stdout.startswith("100755"), f"mode is not executable: {out.stdout}"


def test_the_shell_script_is_valid_bash():
    result = subprocess.run(["bash", "-n", str(SH)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", [SH, PS1])
def test_both_scripts_target_the_same_venv_directory(script):
    assert ".venv" in script.read_text(encoding="utf-8")


@pytest.mark.parametrize("script", [SH, PS1])
def test_both_scripts_install_the_same_extras(script):
    assert "[dev,dashboard]" in script.read_text(encoding="utf-8")


@pytest.mark.parametrize("script", [SH, PS1])
def test_both_scripts_verify_before_claiming_success(script):
    """Setup must not report success without checking the install."""
    text = script.read_text(encoding="utf-8")
    assert re.search(r"titlei\W+verify", text), "setup must run `titlei verify`"


@pytest.mark.parametrize("script", [SH, PS1])
def test_both_scripts_enforce_the_same_minimum_python(script):
    text = script.read_text(encoding="utf-8")
    assert re.search(r"MIN_MINOR=9|\$MinMinor = 9", text)


def test_powershell_has_no_unbound_format_operator():
    """`Say 'x {0}' -f $y` binds -f to the function, not the string, and dies."""
    for line in PS1.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if re.match(r"^(Say|Die)\s+.*\s-f\s", stripped):
            pytest.fail(f"format operator misused in a function call: {stripped}")


def test_docs_cover_activation_on_both_platforms():
    guide = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")
    assert "source .venv/bin/activate" in guide
    assert "Activate.ps1" in guide
    assert "deactivate" in guide
    assert "-m titlei" in guide, "the no-activation fallback must be documented"


def test_documented_manual_install_upgrades_pip_first():
    """Editable installs need pip >= 21.3; macOS 3.9 ships 21.2.

    Without the upgrade, `pip install -e .` fails with a misleading
    "setup.py not found", which is a dead end for a newcomer.
    """
    guide = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")
    manual = guide[guide.index("Prefer to do it by hand") :][:600]
    assert "pip install --upgrade pip" in manual

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("install:", "dev:"):
        body = makefile[makefile.index(target) :][:300]
        assert "upgrade pip" in body, f"`make {target[:-1]}` must upgrade pip first"
