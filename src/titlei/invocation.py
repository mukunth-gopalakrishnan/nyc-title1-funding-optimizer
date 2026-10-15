"""How to tell the user to run this program again.

A suggestion such as "next, run `titlei runs`" only works when `titlei` on the
user's PATH is this installation. That is true inside an activated virtual
environment, and false when the program was started without activating one --
as `./.venv/bin/titlei demo` or `.venv/bin/python -m titlei demo`, the forms the
setup script itself offers -- or as the downloaded single-file program. In those
cases the bare `titlei ...` it printed failed with "command not found".

``command("runs")`` returns the form that works from the current directory:

    titlei runs                     the environment is active, or titlei is on PATH
    ./.venv/bin/titlei runs         it is not, but the venv's own titlei exists
    ./titlei-macos-arm64 runs       the downloaded program
    /path/to/python -m titlei runs  no titlei script at all
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
import sysconfig
from pathlib import Path

PROGRAM = "titlei"


def _script_name() -> str:
    return f"{PROGRAM}.exe" if os.name == "nt" else PROGRAM


def _script_dirs() -> list[Path]:
    """Where this installation's console script can be, most specific first."""
    dirs = [Path(sys.executable).parent]  # a venv's bin/ (Scripts\\ on Windows)
    try:
        dirs.append(Path(sysconfig.get_path("scripts")))
    except KeyError:
        pass
    return dirs


def _own_script() -> Path | None:
    """This installation's `titlei` executable, if it has one."""
    for directory in _script_dirs():
        candidate = directory / _script_name()
        if candidate.is_file():
            return candidate
    return None


def _is_on_path(script: Path) -> bool:
    """True if typing `titlei` would run ``script`` rather than something else."""
    found = shutil.which(PROGRAM)
    if not found:
        return False
    try:
        return os.path.samefile(found, script)
    except OSError:
        return False


def _shown(path: Path) -> str:
    """``path`` as the user should type it: relative when under the current
    directory (``./.venv/bin/titlei``), absolute otherwise, quoted if needed."""
    path = Path(os.path.abspath(path))  # not resolve(): a venv's python is a symlink
    try:
        text = os.curdir + os.sep + str(path.relative_to(Path.cwd()))
    except (ValueError, OSError):  # outside the cwd, or the cwd no longer exists
        text = str(path)
    if os.name == "nt":
        return f'"{text}"' if " " in text else text
    return shlex.quote(text)


def python() -> str:
    """This interpreter, as the user should type it (for `-m pip install ...`)."""
    return _shown(Path(sys.executable))


def program() -> str:
    """What to type to run this program from the current directory."""
    if getattr(sys, "frozen", False):
        return _shown(Path(sys.executable))
    script = _own_script()
    if script is None:
        return f"{python()} -m {PROGRAM}"
    if _is_on_path(script):
        return PROGRAM
    return _shown(script)


def command(args: str = "") -> str:
    """A full command line to suggest, e.g. ``command("runs")``."""
    prefix = program()
    return f"{prefix} {args}" if args else prefix
