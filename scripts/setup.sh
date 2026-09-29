#!/usr/bin/env bash
# One-command setup from a fresh clone.
#
#   ./scripts/setup.sh
#
# Creates a virtual environment in .venv, installs the package with its dev and
# dashboard extras, and verifies the installation reproduces the published
# results. Safe to re-run.

set -euo pipefail

cd "$(dirname "$0")/.."

VENV="${VENV:-.venv}"
PYTHON="${PYTHON:-python3}"
MIN_MINOR=9

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }

command -v "$PYTHON" >/dev/null 2>&1 \
  || fail "$PYTHON not found. Install Python 3.$MIN_MINOR or newer, then re-run."

minor=$("$PYTHON" -c 'import sys; print(sys.version_info[1])')
major=$("$PYTHON" -c 'import sys; print(sys.version_info[0])')
if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt "$MIN_MINOR" ]; }; then
  fail "Python 3.$MIN_MINOR or newer required; found $major.$minor. Set PYTHON=/path/to/python3 and re-run."
fi

say "1/3  Creating the virtual environment in $VENV"
if [ -d "$VENV" ]; then
  echo "     already exists — reusing it"
else
  "$PYTHON" -m venv "$VENV"
  echo "     created with $("$PYTHON" --version)"
fi

say "2/3  Installing dependencies"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e ".[dev,dashboard]"
echo "     installed"

say "3/3  Verifying the installation"
# The module form, not the console script: a venv nested under a long path can
# exceed the kernel's shebang limit, which would break bin/titlei but not this.
"$VENV/bin/python" -m titlei verify

cat <<NEXT

Setup complete. Activate the environment with:

    source $VENV/bin/activate

Then take the guided tour:

    titlei demo

Activation applies to this terminal only — run it again in a new window.
To skip activation entirely, use the environment's own Python:

    $VENV/bin/python -m titlei demo

NEXT
