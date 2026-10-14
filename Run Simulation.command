#!/usr/bin/env bash
# Double-click this file to open the interactive simulation in your browser.
#
# The first run builds a private Python environment in .venv: a couple of
# minutes, and it needs an internet connection that once. After that it starts
# in a few seconds. Close the window, or press Ctrl+C, to stop.
#
# From a terminal (macOS or Linux):   ./"Run Simulation.command"

set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
VENV_PY="$VENV/bin/python"
STAMP="$VENV/.titlei-dashboard-installed"

fail() {
  printf '\n\033[31m%s\033[0m\n' "$*" >&2
  # A double-clicked window would otherwise close before the message is read.
  if [ -t 0 ]; then read -r -p "Press Enter to close. " _ || true; fi
  exit 1
}

pick_python() {
  # The versions CI tests, newest first, then whatever python3 is.
  for candidate in python3.12 python3.11 python3.10 python3 python3.9; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

needs_install() {
  [ -x "$VENV_PY" ] || return 0
  [ -f "$STAMP" ] || return 0
  # Re-install when the project's dependencies change (e.g. after a git pull).
  [ pyproject.toml -nt "$STAMP" ] && return 0
  "$VENV_PY" -c 'import titlei, streamlit' >/dev/null 2>&1 || return 0
  return 1
}

if needs_install; then
  echo "Setting up the simulation. This takes a couple of minutes the first time"
  echo "and needs an internet connection; later runs start in seconds."
  echo

  # An environment whose Python has since been removed cannot be repaired.
  if [ -d "$VENV" ] && ! "$VENV_PY" -c 'pass' >/dev/null 2>&1; then
    echo "The existing $VENV no longer works; rebuilding it."
    rm -rf "$VENV"
  fi

  if [ ! -d "$VENV" ]; then
    PYTHON=$(pick_python) || fail "Python 3.9 or newer is needed. Install it from
https://www.python.org/downloads/ and then double-click this file again."
    echo "Using $("$PYTHON" --version)"
    "$PYTHON" -m venv "$VENV" || fail "Could not create the environment in $VENV."
  fi

  "$VENV_PY" -m pip install --quiet --disable-pip-version-check --upgrade pip \
    || fail "Could not update pip. Check your internet connection and try again."
  "$VENV_PY" -m pip install --disable-pip-version-check -e ".[dashboard]" \
    || fail "Installing the packages failed. Check your internet connection and try again."
  touch "$STAMP"
  echo
fi

"$VENV_PY" -m titlei dashboard "$@" \
  || fail "The simulation stopped with an error; the details are above."
