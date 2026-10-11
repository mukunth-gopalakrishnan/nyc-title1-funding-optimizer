"""The package must work with no repository around it.

It originally located its data by walking up from its own source file to the
repo root, so it ran from a checkout and nowhere else. These tests pin the fix:
the files ship inside the package, and the bundled copies cannot drift from the
ones people edit.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from titlei import resources

ROOT = Path(__file__).resolve().parents[1]

PAIRS = [
    ("data/raw/nyc_title1_schools.csv", "nyc_title1_schools.csv"),
    ("config/model.yaml", "model.yaml"),
    ("tests/fixtures/golden_combined_500M.csv", "golden_combined_500M.csv"),
]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("repo_relative, name", PAIRS)
def test_bundled_copies_match_the_repository(repo_relative, name):
    """Edit one copy without the other and this fails, naming both files."""
    assert _digest(ROOT / repo_relative) == _digest(resources.bundled(name)), (
        f"src/titlei/_data/{name} has drifted from {repo_relative}; "
        f"copy one over the other"
    )


def test_a_checkout_uses_the_repository_copies():
    assert resources.IN_CHECKOUT
    assert resources.DATA_FILE == ROOT / "data/raw/nyc_title1_schools.csv"
    assert resources.CONFIG_FILE == ROOT / "config/model.yaml"


def test_package_data_is_declared_for_the_build():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"_data/*.csv"' in pyproject and '"_data/*.yaml"' in pyproject


def test_nothing_else_resolves_paths_from_its_own_location():
    """Only resources.py may compute locations from __file__.

    That pattern is what made the project run on one machine only.
    """
    offenders = [
        p.name
        for p in (ROOT / "src" / "titlei").glob("*.py")
        if p.name != "resources.py" and "Path(__file__)" in p.read_text()
    ]
    assert not offenders, f"resolve locations through titlei.resources: {offenders}"


@pytest.mark.slow
def test_an_ordinary_install_works_outside_the_repository(tmp_path):
    """The stranger's path: non-editable install, run from an unrelated directory."""
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    py = bin_dir / ("python.exe" if sys.platform == "win32" else "python")

    subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "-q", str(ROOT)], check=True)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = subprocess.run(
        [str(py), "-m", "titlei", "verify", "--out", str(elsewhere / "out")],
        cwd=elsewhere, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Reproduces published results" in result.stdout
    assert "0 failed" in result.stdout
