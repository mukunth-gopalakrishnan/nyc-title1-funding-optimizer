"""`titlei dashboard`, and the Streamlit app it serves."""

from __future__ import annotations

import importlib.util
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from titlei import dashboard
from titlei.cli import main
from titlei.resources import DASHBOARD_APP, PACKAGE_DIR
from titlei.runs import RunRegistry

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "dashboard" / "app.py"


# --- the launcher ----------------------------------------------------------


def test_the_app_ships_inside_the_package():
    """A pip install or wheel has no repository around it, so the app must be here."""
    assert DASHBOARD_APP.is_file()
    assert PACKAGE_DIR in DASHBOARD_APP.parents


def test_the_app_has_a_directory_to_itself():
    """Streamlit puts the script's directory first on sys.path; nothing may shadow."""
    assert sorted(p.name for p in DASHBOARD_APP.parent.glob("*.py")) == ["app.py"]


def test_install_hint_matches_the_dashboard_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    floor = re.search(r'dashboard = \["(streamlit>=[\d.]+)"\]', pyproject).group(1)
    assert floor == dashboard.STREAMLIT_REQUIREMENT
    assert floor in dashboard.install_hint()


def test_missing_streamlit_says_how_to_install_it(monkeypatch, capsys):
    monkeypatch.setattr(dashboard, "streamlit_available", lambda: False)
    assert main(["dashboard"]) == 1
    out = capsys.readouterr().out
    assert "pip install" in out
    assert sys.executable in out, "the hint must name the interpreter to install into"


def test_the_downloadable_app_points_to_the_launchers(monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert main(["dashboard"]) == 1
    out = capsys.readouterr().out
    assert "Run Simulation.command" in out and "Run Simulation.bat" in out


def test_server_is_headless_local_only_and_sends_no_usage_stats():
    command = dashboard.build_command(8765)
    pairs = dict(zip(command[5::2], command[6::2]))
    assert command[1:5] == ["-m", "streamlit", "run", str(DASHBOARD_APP)]
    # Headless skips Streamlit's first-run email prompt, which would otherwise
    # leave a double-clicked window waiting on input nobody can see.
    assert pairs["--server.headless"] == "true"
    assert pairs["--server.address"] == "127.0.0.1"
    assert pairs["--server.port"] == "8765"
    assert pairs["--browser.gatherUsageStats"] == "false"
    assert pairs["--client.toolbarMode"] == "viewer", "no Deploy button for end users"


def test_free_port_skips_a_port_in_use():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        assert dashboard.free_port(start=taken, attempts=20) != taken


class FakeProcess:
    def __init__(self, wait_results):
        self._wait_results = list(wait_results)
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def wait(self, timeout=None):
        result = self._wait_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def terminate(self):
        self.terminated = True


@pytest.fixture
def fake_server(monkeypatch):
    """Stand in for Streamlit so the launcher logic is tested without a server."""
    calls = {"opened": []}

    def popen(command, env):
        calls["command"], calls["env"] = command, env
        return calls["process"]

    monkeypatch.setattr(dashboard, "streamlit_available", lambda: True)
    monkeypatch.setattr(dashboard.subprocess, "Popen", popen)
    monkeypatch.setattr(dashboard, "wait_until_listening", lambda port, proc: True)
    monkeypatch.setattr(dashboard.webbrowser, "open", calls["opened"].append)
    return calls


def test_launch_shares_the_run_registry_and_opens_the_browser(fake_server, tmp_path):
    fake_server["process"] = FakeProcess([0])
    code = dashboard.launch(tmp_path / "runs", port=8777, out=lambda *_: None)

    assert code == 0
    assert fake_server["env"][dashboard.RUNS_DIR_ENV] == str((tmp_path / "runs").resolve())
    assert fake_server["opened"] == ["http://localhost:8777"]


def test_no_browser_flag_keeps_the_browser_closed(fake_server, tmp_path):
    fake_server["process"] = FakeProcess([0])
    assert main(["dashboard", "--no-browser", "--port", "8778",
                 "--runs-dir", str(tmp_path)]) == 0
    assert fake_server["opened"] == []


def test_ctrl_c_stops_the_server_cleanly(fake_server, tmp_path):
    fake_server["process"] = process = FakeProcess([KeyboardInterrupt(), 0])
    assert dashboard.launch(tmp_path, port=8779, out=lambda *_: None) == 0
    assert process.terminated


# --- the app itself, driven headlessly ---------------------------------------

needs_streamlit = pytest.mark.skipif(
    importlib.util.find_spec("streamlit") is None,
    reason="the dashboard extra is not installed",
)


def _run(path: Path, runs_dir: Path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv(dashboard.RUNS_DIR_ENV, str(runs_dir))
    app = AppTest.from_file(str(path), default_timeout=180)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    return app


def _metric(app, label):
    return next(m.value for m in app.metric if m.label == label)


@needs_streamlit
@pytest.mark.parametrize("path", [DASHBOARD_APP, SHIM], ids=["packaged", "shim"])
def test_the_app_renders_and_the_budget_slider_moves_it(path, tmp_path, monkeypatch):
    app = _run(path, tmp_path, monkeypatch)
    assert _metric(app, "Budget allocated") == "$500M"

    app.sidebar.slider[0].set_value(100).run()
    assert not app.exception
    assert _metric(app, "Budget allocated") == "$100M"


@needs_streamlit
def test_every_control_changes_the_result_not_just_the_budget(tmp_path, monkeypatch):
    """Regression: results were cached on the budget alone, so the need-weight
    slider and the cap inputs silently changed nothing."""
    app = _run(DASHBOARD_APP, tmp_path, monkeypatch)
    before = _metric(app, "Mean projected gain")

    app.sidebar.slider[1].set_value(1.0).run()  # financial need only
    assert _metric(app, "Mean projected gain") != before


@needs_streamlit
def test_conflicting_caps_explain_themselves_instead_of_crashing(tmp_path, monkeypatch):
    app = _run(DASHBOARD_APP, tmp_path, monkeypatch)
    app.sidebar.number_input[0].set_value(1000).run()  # high-need cap below lower-need

    assert not app.exception
    assert any("cap" in e.value for e in app.error)


@needs_streamlit
def test_saving_a_run_writes_to_the_shared_registry(tmp_path, monkeypatch):
    app = _run(DASHBOARD_APP, tmp_path, monkeypatch)
    next(b for b in app.button if b.label == "Save run").click().run()

    assert not app.exception
    assert len(RunRegistry(tmp_path).list()) == 1


# --- a real server -----------------------------------------------------------


def _port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


@needs_streamlit
@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
@pytest.mark.parametrize("stop_signal", ["SIGINT", "SIGTERM"], ids=["ctrl-c", "kill"])
def test_titlei_dashboard_serves_the_app_and_stops_cleanly(tmp_path, stop_signal):
    port = dashboard.free_port(start=8600)
    server = subprocess.Popen(
        [sys.executable, "-m", "titlei", "dashboard", "--no-browser",
         "--port", str(port), "--runs-dir", str(tmp_path)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + dashboard.STARTUP_TIMEOUT
        health = None
        while time.monotonic() < deadline and server.poll() is None:
            try:
                url = f"http://127.0.0.1:{port}/_stcore/health"
                with urllib.request.urlopen(url, timeout=2) as response:
                    health = response.read().decode()
                break
            except OSError:
                time.sleep(0.5)
        assert health == "ok", f"server never became healthy (exit {server.poll()})"
    finally:
        server.send_signal(getattr(signal, stop_signal))
        try:
            output = server.communicate(timeout=30)[0]
        except subprocess.TimeoutExpired:
            server.kill()
            raise
    assert server.returncode == 0, output
    assert "Email" not in output, "the first-run email prompt must not appear"
    # The Streamlit process the launcher started must be gone too, not orphaned.
    deadline = time.monotonic() + 10
    while not _port_is_free(port) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _port_is_free(port), f"Streamlit kept running after {stop_signal}"
