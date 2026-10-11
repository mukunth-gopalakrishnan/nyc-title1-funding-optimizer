"""Build a single-file ``titlei`` executable for the current platform.

    python packaging/build_binary.py

Run it in an environment where the package is installed (``pip install .
pyinstaller``). The result is ``dist/titlei`` (``dist/titlei.exe`` on Windows):
one file, no Python required on the machine that runs it.

It is the same script on macOS, Linux and Windows, so CI and a developer build
identically. PyInstaller cannot cross-compile, so each platform's binary has to
be built on that platform -- which is what .github/workflows/release.yml does.
"""

from __future__ import annotations

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]

PyInstaller.__main__.run(
    [
        str(ROOT / "packaging" / "entry.py"),
        "--onefile",
        "--name", "titlei",
        # the school data, default config and published results
        "--collect-data", "titlei",
        # the binary is the CLI; leave out what it never uses
        "--exclude-module", "streamlit",
        "--exclude-module", "tkinter",
        "--exclude-module", "pytest",
        "--exclude-module", "IPython",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--noconfirm",
        "--clean",
    ]
)
