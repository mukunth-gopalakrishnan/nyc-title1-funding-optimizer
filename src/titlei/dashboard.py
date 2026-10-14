"""Start the interactive dashboard: ``titlei dashboard``.

Streamlit is started headless and the browser is opened from here. Started the
ordinary way, Streamlit's very first run stops to ask for an email address in
the terminal -- invisible from a double-clicked launcher, where it just looks as
if nothing happened. Headless mode skips that prompt.

The server listens on 127.0.0.1 only, so the dashboard is not reachable from
other machines on the network, and Streamlit's usage statistics are turned off.
"""

from __future__ import annotations

import importlib.util
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from titlei.resources import DASHBOARD_APP
from titlei.runs import DEFAULT_RUNS_DIR

#: The dashboard reads the run registry location from this variable, so the
#: dashboard and the command line share one set of saved runs.
RUNS_DIR_ENV = "TITLEI_RUNS_DIR"

#: Keep in step with the `dashboard` extra in pyproject.toml (a test checks).
STREAMLIT_REQUIREMENT = "streamlit>=1.50"

DEFAULT_PORT = 8501
LOOPBACK = "127.0.0.1"
# A cold first start imports pandas, scipy, matplotlib and Streamlit from disk.
STARTUP_TIMEOUT = 90.0


class DashboardUnavailable(RuntimeError):
    """This installation cannot run the dashboard; the message says what to do."""


def streamlit_available() -> bool:
    return importlib.util.find_spec("streamlit") is not None


def install_hint() -> str:
    """What to do when the dashboard cannot start here."""
    if getattr(sys, "frozen", False):
        return (
            "the downloadable app runs the model, the guided demo and the HTML "
            "report, but not the live dashboard, which needs Python.\n"
            "To get it, download the project from GitHub and double-click "
            "'Run Simulation.command' (Mac) or 'Run Simulation.bat' (Windows)."
        )
    return (
        "the dashboard needs Streamlit, which is not installed in this "
        "environment. Install it with:\n\n"
        f'    "{sys.executable}" -m pip install "{STREAMLIT_REQUIREMENT}"\n\n'
        "Or, from the project folder, double-click 'Run Simulation.command' "
        "(Mac) or 'Run Simulation.bat' (Windows), which sets everything up."
    )


def free_port(start: int = DEFAULT_PORT, attempts: int = 50) -> int:
    """The first port from ``start`` that nothing is listening on."""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((LOOPBACK, port))
            except OSError:
                continue
            return port
    raise DashboardUnavailable(
        f"no free port between {start} and {start + attempts - 1}; "
        "pass one with --port"
    )


def build_command(port: int) -> list[str]:
    return [
        sys.executable, "-m", "streamlit", "run", str(DASHBOARD_APP),
        "--server.headless", "true",
        "--server.address", LOOPBACK,
        "--server.port", str(port),
        "--browser.gatherUsageStats", "false",
        # Hide Streamlit's developer menu, including its "Deploy" button.
        "--client.toolbarMode", "viewer",
    ]


def wait_until_listening(
    port: int, process: subprocess.Popen, timeout: float = STARTUP_TIMEOUT
) -> bool:
    """True once the server accepts connections; False if it died or timed out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with socket.create_connection((LOOPBACK, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _say(message: str) -> None:
    # Flushed, so the messages appear in order with Streamlit's own output even
    # when stdout is a pipe or a file rather than a terminal.
    print(message, flush=True)


def _interrupt(signum, frame):
    raise KeyboardInterrupt


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def launch(
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    port: int | None = None,
    open_browser: bool = True,
    out=_say,
) -> int:
    """Serve the dashboard until the user stops it; returns the exit code."""
    if getattr(sys, "frozen", False) or not streamlit_available():
        raise DashboardUnavailable(install_hint())

    port = port or free_port()
    url = f"http://localhost:{port}"
    env = {**os.environ, RUNS_DIR_ENV: str(Path(runs_dir).resolve())}

    out("Starting the simulation dashboard...")
    process = subprocess.Popen(build_command(port), env=env)
    # A plain `kill` should stop Streamlit too, the same way Ctrl+C does,
    # rather than leave it running without the launcher.
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, _interrupt)
    try:
        if wait_until_listening(port, process):
            out(f"\nThe dashboard is running at {url}")
            if open_browser:
                webbrowser.open(url)
            out(
                "Keep this window open while you use it. "
                "Press Ctrl+C, or close the window, to stop.\n"
            )
        elif process.poll() is None:
            out(f"\nStill starting; it will be at {url}")
        return process.wait()
    except KeyboardInterrupt:
        _stop(process)
        out("\nStopped.")
        return 0
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
