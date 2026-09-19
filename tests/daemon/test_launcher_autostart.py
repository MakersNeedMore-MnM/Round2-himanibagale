"""Regression tests for autostart + auto-open (backend.daemon.launcher).

Covers the autostart contract:
- a daemon already serving the dashboard port is *adopted*, never duplicated
  (port-based check, per spec — a stale pid file must not spawn a rival);
- the browser opens only after readiness is confirmed, and never on a
  failed start;
- plain ``codelith`` (no subcommand) opens the dashboard after the daemon
  is up.
"""

from __future__ import annotations

import sys
import types

import pytest

from backend.cli import main as cli_main
from backend.daemon import launcher
from backend.daemon import state


@pytest.fixture()
def no_state(monkeypatch):
    """Neutralize real state files and process spawning for isolation."""
    monkeypatch.setattr(state, "is_running", lambda: None)
    monkeypatch.setattr(state, "clear_state", lambda: None)
    monkeypatch.setattr(state, "write_state", lambda pid, port: None)
    monkeypatch.setattr(launcher.state, "is_running", lambda: None)
    monkeypatch.setattr(launcher.state, "clear_state", lambda: None)
    monkeypatch.setattr(launcher.state, "write_state", lambda pid, port: None)
    monkeypatch.setattr(launcher, "_print_log_tail", lambda: None)


def test_start_adopts_daemon_already_on_default_port(no_state, monkeypatch, capsys):
    """Port 8765 answering + no usable pid state → adopt, never spawn."""
    opened_ports: list[int] = []

    def _fail_spawn(port):
        raise AssertionError("a second daemon must not be started")

    monkeypatch.setattr(launcher.state, "port_open", lambda port, host=...: port == launcher.DEFAULT_PORT)
    monkeypatch.setattr(launcher, "_start_detached", _fail_spawn)

    pid, port, started = launcher.start()

    assert pid is None
    assert port == launcher.DEFAULT_PORT
    assert started is False
    assert "reusing it" in capsys.readouterr().out


def test_start_starts_detached_and_waits_until_ready(no_state, monkeypatch):
    """Nothing running → detached start, pid state written, readiness polled."""
    spawned: dict = {}

    class FakeProc:
        pid = 4242

    def fake_wait(port, timeout=None):
        spawned["waited_port"] = port
        return True

    monkeypatch.setattr(launcher.state, "port_open", lambda port, host=...: False)
    monkeypatch.setattr(launcher, "_find_free_port", lambda host=..., preferred=...: launcher.DEFAULT_PORT)
    monkeypatch.setattr(launcher, "_start_detached", lambda port: spawned.setdefault("proc", FakeProc()))
    monkeypatch.setattr(launcher, "_wait_until_ready", fake_wait)

    pid, port, started = launcher.start()

    assert (pid, port, started) == (4242, launcher.DEFAULT_PORT, True)
    assert spawned["waited_port"] == launcher.DEFAULT_PORT


def test_start_fails_loudly_when_never_ready(no_state, monkeypatch):
    """Daemon not ready within timeout → clear error, no browser, exit != 0."""
    monkeypatch.setattr(launcher.state, "port_open", lambda port, host=...: False)
    monkeypatch.setattr(launcher, "_find_free_port", lambda host=..., preferred=...: launcher.DEFAULT_PORT)

    class FakeProc:
        pid = 7

    monkeypatch.setattr(launcher, "_start_detached", lambda port: FakeProc())
    monkeypatch.setattr(launcher, "_wait_until_ready", lambda port, timeout=None: False)
    opened = monkeypatch.setattr(
        launcher, "open_dashboard", lambda port: opened_ports.append(port) or True
    )
    opened_ports: list[int] = []

    with pytest.raises(SystemExit, match="failed to become ready"):
        launcher.start()

    assert opened_ports == []  # never open a broken URL


def test_open_dashboard_uses_webbrowser_with_dashboard_url(monkeypatch):
    """open_dashboard goes through webbrowser.open with the localhost URL."""
    calls: list[tuple[str, int, bool]] = []

    fake = types.ModuleType("webbrowser")
    fake.open = lambda url, new=0, autoraise=False: calls.append((url, new, autoraise)) or True
    monkeypatch.setitem(sys.modules, "webbrowser", fake)

    assert launcher.open_dashboard(8765) is True
    assert calls == [("http://localhost:8765/", 2, True)]


def test_open_dashboard_swallows_browser_errors(monkeypatch):
    """A browser failure must not take the CLI down."""
    fake = types.ModuleType("webbrowser")
    fake.open = lambda url, new=0, autoraise=False: (_ for _ in ()).throw(RuntimeError("no gui"))
    monkeypatch.setitem(sys.modules, "webbrowser", fake)

    assert launcher.open_dashboard(8765) is False


def test_cli_plain_invocation_opens_dashboard_after_start(monkeypatch, capsys):
    """`codelith` (no subcommand) → daemon start → dashboard opened with its port."""
    started: list[int] = []
    opened: list[int] = []

    monkeypatch.setattr(
        "backend.llm.key_setup.ensure_keys_at_startup", lambda: None
    )
    monkeypatch.setattr(cli_main, "print_banner", lambda: None)
    monkeypatch.setattr(
        launcher, "start", lambda: started.append(4242) or (4242, 8765, True)
    )
    monkeypatch.setattr(launcher, "open_dashboard", lambda port: opened.append(port))
    monkeypatch.setattr(cli_main, "run_session", lambda port: None)

    rc = cli_main.main([])

    assert rc == 0
    assert started == [4242]  # launcher.start ran first
    assert opened == [8765]  # then the browser, with the daemon's port
