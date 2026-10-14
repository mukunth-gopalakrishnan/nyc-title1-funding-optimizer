"""Locate the files the model ships with, wherever it is running.

From a source checkout the repository copies are used, so edits to
``config/model.yaml`` or ``data/raw/`` take effect immediately. Anywhere else --
a normal ``pip install``, a wheel, a frozen binary -- there is no repository
around the code, so the copies bundled inside the package are used instead.

The bundled copies in ``titlei/_data/`` must stay byte-identical to the
repository ones; ``tests/test_resources.py`` enforces that.

This exists because the package originally found its data by walking up from
its own source file to the repository root. That works only when the code runs
from inside the checkout, which is why it ran on the author's machine and
nowhere else.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_DIR = PACKAGE_DIR / "_data"
REPO_ROOT = PACKAGE_DIR.parents[1]

#: True only when running from a source checkout of this project, not merely
#: when some unrelated directory two levels up happens to contain a data/ folder.
IN_CHECKOUT = (REPO_ROOT / "pyproject.toml").is_file() and (
    REPO_ROOT / "src" / "titlei"
).is_dir()


def bundled(name: str) -> Path:
    """The copy of ``name`` shipped inside the package."""
    return BUNDLED_DIR / name


def locate(repo_relative: str, name: str) -> Path:
    """The repository copy when running from a checkout, else the bundled one."""
    if IN_CHECKOUT:
        candidate = REPO_ROOT / repo_relative
        if candidate.exists():
            return candidate
    return bundled(name)


DATA_FILE = locate("data/raw/nyc_title1_schools.csv", "nyc_title1_schools.csv")
CONFIG_FILE = locate("config/model.yaml", "model.yaml")
GOLDEN_FILE = locate(
    "tests/fixtures/golden_combined_500M.csv", "golden_combined_500M.csv"
)

#: The Streamlit app behind `titlei dashboard`. It ships inside the package
#: (there is no repository copy), so it exists in every kind of install.
DASHBOARD_APP = PACKAGE_DIR / "_dashboard" / "app.py"
