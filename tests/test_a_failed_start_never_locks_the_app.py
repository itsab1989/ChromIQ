"""A tool that cannot start must still release the UI.

`QProcess.finished` is emitted only by a process that actually ran. A missing
or non-executable binary emits `errorOccurred(FailedToStart)` and nothing else,
so every caller's `on_finish` was simply never called.

That mattered little while a build only greyed the tabs. Since #164 Q7 a build
also greys the masthead — Open Project, Open Chart File, Tools AND Preferences —
and Preferences is the one place a wrong ArgyllCMS path can be corrected. A
mistyped path therefore locked the user out of the only fix, until restart.
"""
import pathlib
import tempfile

import pytest


@pytest.fixture
def broken_runner(qapp, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    s = AppSettings()
    s.set("argyll_bin_path", "/nonexistent/argyll/bin")
    monkeypatch.setenv("PATH", "")
    return ArgyllRunner(s), s


def _pump(qapp, ms=800):
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    qapp.processEvents()


def test_on_finish_fires_when_the_binary_cannot_start(broken_runner, qapp):
    runner, _ = broken_runner
    seen = []
    runner.run("colprof", ["-v"], pathlib.Path(tempfile.mkdtemp()),
               on_finish=seen.append)
    _pump(qapp)
    assert seen == [-1], (
        "a tool that never started did not report back, so whatever locked the "
        "UI before the call will never unlock it")
    assert runner.is_running is False


def test_the_masthead_and_tabs_come_back_after_a_failed_build(qapp, tmp_path,
                                                              monkeypatch):
    """The user-facing point: Preferences must be reachable again."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    s.set("argyll_bin_path", "/nonexistent/argyll/bin")
    monkeypatch.setenv("PATH", "")

    w = MainWindow(s)
    try:
        qapp.processEvents()
        prefs = w._masthead._btn

        # The lock as a build applies it.
        w._on_profile_active(True)
        assert prefs.isEnabled() is False, "the build did not lock Preferences"

        # …and the release the failed start now delivers.
        w._tab_profile._reset_build_ui()
        qapp.processEvents()
        assert prefs.isEnabled() is True, (
            "Preferences is still greyed after a build that never started — "
            "the user cannot reach the setting that would fix it")
        for i in range(w._tabs.count()):
            assert w._tabs.isTabEnabled(i) is True, f"tab {i} is still locked"
    finally:
        w.close()


def test_run_emits_started_when_a_tool_actually_launches(qapp, tmp_path):
    """`ArgyllRunner.run` must emit `started`.

    Without this, every test of the masthead's chart-build lock emits the
    signal itself and passes even when `run()` never emits it — which is
    exactly what happened: the lock shipped not working, guarded by green
    tests, and only a real driven build found it.
    """
    import pathlib
    import sys

    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    # A tool that certainly exists and exits immediately: this interpreter.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    tool = fake_bin / "targen"
    tool.write_text(f"#!/bin/sh\nexec {sys.executable} -c 'pass'\n")
    tool.chmod(0o755)

    s = AppSettings()
    s.set("argyll_bin_path", str(fake_bin))
    r = ArgyllRunner(s)

    started, finished = [], []
    r.started.connect(lambda: started.append(True))
    r.run("targen", ["-v"], pathlib.Path(tmp_path), on_finish=finished.append)
    _pump(qapp, 1500)

    assert started == [True], (
        "run() did not emit `started`, so nothing can react to a tool actually "
        "beginning")
    assert finished, "the run never reported finishing"


def test_started_is_not_emitted_when_the_binary_is_missing(qapp, tmp_path,
                                                          monkeypatch):
    """A tool that cannot launch has not started — only `finished(-1)`."""
    import pathlib

    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    # PATH must be cleared too: the runner falls back to a PATH lookup, and on
    # a machine with ArgyllCMS installed it finds the real colprof, which then
    # starts and exits 1 — a completely different path from the one under test.
    monkeypatch.setenv("PATH", "")
    s = AppSettings()
    s.set("argyll_bin_path", str(tmp_path / "nowhere"))
    r = ArgyllRunner(s)
    started, finished = [], []
    r.started.connect(lambda: started.append(True))
    r.run("colprof", ["-v"], pathlib.Path(tmp_path), on_finish=finished.append)
    _pump(qapp, 1200)

    assert finished == [-1], f"expected a failed-start report, got {finished}"
    assert started == [], (
        "`started` was emitted for a binary that never ran. The signal is the "
        "app's 'a tool is really going' edge — emitting it after `start()` "
        "returns is a lie, because a missing binary reports through "
        "`errorOccurred` afterwards. This test built the list and then never "
        "asserted on it, so the false contract went unnoticed.")


def test_the_user_is_told_which_tool_could_not_start(qapp, tmp_path,
                                                     monkeypatch):
    """F5 had NO test at all — the dialog could be deleted and the gate stayed
    green. This drives the real `_on_build_done` failure path."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.tooltip_button import InfoDialog

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    try:
        qapp.processEvents()
        shown = []
        monkeypatch.setattr(InfoDialog, "exec",
                            lambda self: shown.append(self.windowTitle()) or 0)

        w._runner.last_failed_to_start = "colprof"
        w._tab_profile._on_build_done(-1)
        qapp.processEvents()

        assert shown, ("a build whose tool could not start told the user "
                       "nothing — only a line in the log")
        assert "colprof" in shown[0], f"the message does not name the tool: {shown}"
        assert w._runner.last_failed_to_start is None, (
            "the flag was not cleared, so a LATER unrelated failure would show "
            "this message again")
    finally:
        w.close()


def test_an_ordinary_build_failure_does_not_claim_a_missing_tool(qapp, tmp_path,
                                                                 monkeypatch):
    """The dialog must fire only for a tool that could not START."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from ui.tooltip_button import InfoDialog

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    try:
        qapp.processEvents()
        shown = []
        monkeypatch.setattr(InfoDialog, "exec",
                            lambda self: shown.append(self.windowTitle()) or 0)

        w._runner.last_failed_to_start = None
        w._tab_profile._on_build_done(2)          # colprof ran and failed
        qapp.processEvents()

        assert not any("could not start" in t for t in shown), (
            f"an ordinary build failure blamed a missing tool: {shown}")
    finally:
        w.close()


def test_a_refused_run_does_not_leave_a_stale_missing_tool_flag(qapp, tmp_path):
    """`run()` refuses while something else is running. That is not a failed
    START, and leaving the flag set made the next build say "the program was
    not found" for a completely different cause."""
    import pathlib as _p

    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    s = AppSettings()
    s.set("argyll_bin_path", str(tmp_path / "nowhere"))
    r = ArgyllRunner(s)
    r.last_failed_to_start = "targen"          # a previous failed start

    class _Busy:
        state = lambda self: 2

    r._process = _Busy()
    assert r.is_running is True
    r.run("colprof", ["-v"], _p.Path(tmp_path), on_finish=lambda c: None)
    assert r.last_failed_to_start is None, (
        "a refused run kept a stale 'could not start' flag")
