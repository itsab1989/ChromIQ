"""The crash log says which build wrote it, says when a session ended cleanly,
and is not filled by the Windows print dialog (Basti, 2026-10-23, from jctay's
Windows log of forum post 149800: 202 start-up lines with no version, and 254
"Windows fatal exception" dumps, every one a COM exception the print dialog
raised and handled itself). `core/crash_log.py` holds the reasons."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
import types
from datetime import datetime
from pathlib import Path

import pytest

from core import crash_log

REPO = Path(__file__).resolve().parent.parent


class FakeFaulthandler:
    """Stands in for the faulthandler module, so a test never touches the one
    pytest itself armed."""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.calls: list[tuple] = []

    def is_enabled(self):
        return self.enabled

    def disable(self):
        self.calls.append(("disable",))
        self.enabled = False

    def enable(self, file=None, all_threads=True):
        self.calls.append(("enable", file, all_threads))
        self.enabled = True


@pytest.fixture
def fake(monkeypatch, tmp_path):
    fh = FakeFaulthandler()
    monkeypatch.setattr(crash_log, "faulthandler", fh)
    monkeypatch.setattr(crash_log, "_depth", 0)
    monkeypatch.setattr(crash_log, "_paused", False)
    f = open(tmp_path / "chromiq-crash.log", "a", encoding="utf-8")
    monkeypatch.setattr(crash_log, "_file", f)
    monkeypatch.setattr(crash_log, "_all_threads", True)
    yield fh, f
    f.close()


def _platform(monkeypatch, name):
    monkeypatch.setattr(crash_log, "sys", types.SimpleNamespace(platform=name))


# --- the start-up line and the shutdown line ---------------------------------

def test_the_start_up_line_names_the_version_and_the_date():
    line = crash_log.armed_line("4.3.10-beta.2", datetime(2026, 10, 23, 9, 5, 7))
    assert line == "\n=== faulthandler armed 2026-10-23 09:05:07 ChromIQ 4.3.10-beta.2 ===\n"


def test_a_clean_shutdown_line():
    when = datetime(2026, 10, 23, 18, 0, 1)
    assert crash_log.closed_line(0, when) == "=== ChromIQ closed normally 2026-10-23 18:00:01 ===\n"
    assert crash_log.closed_line(3, when) == (
        "=== ChromIQ closed normally 2026-10-23 18:00:01 (exit code 3) ===\n")


def test_arm_writes_the_line_and_arms_every_thread_into_the_file(monkeypatch, tmp_path):
    fh = FakeFaulthandler(enabled=False)
    monkeypatch.setattr(crash_log, "faulthandler", fh)
    monkeypatch.setattr(crash_log, "_file", None)
    f = crash_log.arm(tmp_path / "Logs", "9.8.7")
    try:
        assert fh.calls == [("enable", f, True)]
        text = (tmp_path / "Logs" / "chromiq-crash.log").read_text(encoding="utf-8")
        assert "=== faulthandler armed " in text and text.rstrip().endswith("ChromIQ 9.8.7 ===")
        crash_log.closed_normally(0)
        text = (tmp_path / "Logs" / "chromiq-crash.log").read_text(encoding="utf-8")
        assert text.splitlines()[-1].startswith("=== ChromIQ closed normally ")
    finally:
        f.close()


def test_closed_normally_without_a_crash_log_does_nothing(monkeypatch):
    monkeypatch.setattr(crash_log, "_file", None)
    crash_log.closed_normally(0)          # no file, no error


def test_closed_normally_never_raises(monkeypatch, tmp_path):
    f = open(tmp_path / "x.log", "a", encoding="utf-8")
    f.close()
    monkeypatch.setattr(crash_log, "_file", f)
    crash_log.closed_normally(0)          # a closed file is swallowed, not raised


# --- the pause around the Windows print dialog --------------------------------

def test_windows_pauses_for_the_dialog_and_restores_exactly(fake, monkeypatch):
    fh, f = fake
    _platform(monkeypatch, "win32")
    with crash_log.quiet_for_native_dialog():
        assert fh.calls == [("disable",)]
        assert not fh.enabled
    assert fh.calls == [("disable",), ("enable", f, True)]
    assert fh.enabled


def test_a_dialog_that_raises_still_gets_crash_coverage_back(fake, monkeypatch):
    fh, f = fake
    _platform(monkeypatch, "win32")
    with pytest.raises(RuntimeError):
        with crash_log.quiet_for_native_dialog():
            raise RuntimeError("the dialog failed")
    assert fh.calls[-1] == ("enable", f, True) and fh.enabled
    assert crash_log._depth == 0


def test_nested_blocks_restore_once_at_the_outermost(fake, monkeypatch):
    fh, f = fake
    _platform(monkeypatch, "win32")
    with crash_log.quiet_for_native_dialog():
        with crash_log.quiet_for_native_dialog():
            pass
        assert not fh.enabled               # still paused: the outer block is open
    assert fh.calls == [("disable",), ("enable", f, True)]


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_macos_and_linux_are_untouched(fake, monkeypatch, platform):
    fh, _f = fake
    _platform(monkeypatch, platform)
    with crash_log.quiet_for_native_dialog():
        pass
    assert fh.calls == [] and fh.enabled


def test_nothing_is_paused_that_chromiq_did_not_arm(fake, monkeypatch):
    """Someone else's faulthandler (no crash log of ours) cannot be put back
    exactly, so it is left alone."""
    fh, _f = fake
    _platform(monkeypatch, "win32")
    monkeypatch.setattr(crash_log, "_file", None)
    with crash_log.quiet_for_native_dialog():
        pass
    assert fh.calls == []


def test_a_faulthandler_that_is_off_stays_off(fake, monkeypatch):
    fh, _f = fake
    fh.enabled = False
    _platform(monkeypatch, "win32")
    with crash_log.quiet_for_native_dialog():
        pass
    assert fh.calls == [] and not fh.enabled


# --- where it is used ----------------------------------------------------------

def _exec_calls_and_whether_paused(path: str, fn_name: str, call: str):
    """Every `<call>(...)` in function *fn_name* of *path*, and whether each
    one sits inside a `with quiet_for_native_dialog():` block. Read from the
    file, because conftest replaces the Print tab's method in every test."""
    tree = ast.parse((REPO / path).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    paused = {id(c) for w in ast.walk(fn) if isinstance(w, ast.With)
              and any(ast.unparse(i.context_expr) == "quiet_for_native_dialog()"
                      for i in w.items)
              for c in ast.walk(w)}
    return [id(n) in paused for n in ast.walk(fn)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == call]


def test_the_print_tab_dialog_is_wrapped():
    found = _exec_calls_and_whether_paused(
        "ui/tabs/tab_print.py", "_print_native_qt", "dialog.exec")
    assert found, "the Print tab no longer opens QPrintDialog here"
    assert all(found), "dialog.exec() outside the pause"


def test_the_help_card_dialog_is_wrapped():
    found = _exec_calls_and_whether_paused(
        "ui/help_card_print.py", "_exec_print_dialog", "dlg.exec")
    assert found and all(found)


def test_nothing_else_in_the_app_pauses_faulthandler():
    """The pause is for the print dialog only: every other line of ChromIQ
    keeps its crash coverage."""
    users = []
    for root in ("ui", "workflow", "core", "main.py"):
        paths = [REPO / root] if root.endswith(".py") else (REPO / root).rglob("*.py")
        for p in paths:
            text = p.read_text(encoding="utf-8", errors="replace")
            if p.name != "crash_log.py" and (
                    "quiet_for_native_dialog()" in text or "faulthandler.disable" in text):
                users.append(p.relative_to(REPO).as_posix())
    assert sorted(users) == ["ui/help_card_print.py", "ui/tabs/tab_print.py"]


# --- the real thing, in a process of its own ----------------------------------

def _run(code: str, tmp_path: Path, **env) -> subprocess.CompletedProcess:
    e = dict(os.environ, PYTHONPATH=str(REPO), QT_QPA_PLATFORM="offscreen",
             CHROMIQ_LOG_DIR=str(tmp_path / "Logs"), **env)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], env=e,
                          cwd=str(REPO), capture_output=True, text=True, timeout=240)


def test_main_writes_its_version_and_closed_normally(tmp_path):
    """`import main` arms the log the app's way; `_hard_exit` closes it."""
    proc = _run("""
        import main
        main._hard_exit(0)
    """, tmp_path, CHROMIQ_SETTINGS_FILE=str(tmp_path / "s.ini"))
    assert proc.returncode == 0, proc.stderr[-2000:]
    from core.version import APP_VERSION
    lines = (tmp_path / "Logs" / "chromiq-crash.log").read_text(encoding="utf-8").splitlines()
    lines = [l for l in lines if l.strip()]
    assert lines[0].startswith("=== faulthandler armed ")
    assert lines[0].endswith(f" ChromIQ {APP_VERSION} ===")
    assert lines[-1].startswith("=== ChromIQ closed normally ")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_crash_coverage_is_back_after_the_dialog(tmp_path):
    """The pause, forced on as if on Windows, hands faulthandler back: a fatal
    signal after the dialog lands in the log with its stack.

    NO REAL CRASH. A real fault (or a fatal signal that kills the process)
    makes macOS write a crash report and show "Python quit unexpectedly" on
    the user's screen at every suite run. So SIGSEGV is set to be IGNORED
    before faulthandler is armed, and then sent to the process itself:
    faulthandler writes its dump, hands the signal back to the handler that
    was there before (ignore), and the process goes on and leaves through
    os._exit(0). Nothing dies, nothing reaches the crash reporter."""
    proc = _run("""
        import os, signal, types
        from pathlib import Path
        signal.signal(signal.SIGSEGV, signal.SIG_IGN)
        from core import crash_log
        crash_log.arm(Path(os.environ["CHROMIQ_LOG_DIR"]), "1.2.3")
        crash_log.sys = types.SimpleNamespace(platform="win32")
        with crash_log.quiet_for_native_dialog():
            pass
        def after_the_dialog():
            os.kill(os.getpid(), signal.SIGSEGV)
        after_the_dialog()
        print("STILL ALIVE", flush=True)
        os._exit(0)
    """, tmp_path)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "STILL ALIVE" in proc.stdout
    text = (tmp_path / "Logs" / "chromiq-crash.log").read_text(encoding="utf-8")
    assert "ChromIQ 1.2.3 ===" in text
    assert "Fatal Python error" in text and "after_the_dialog" in text
    assert "closed normally" not in text


def test_no_test_here_crashes_a_process_for_real():
    """A real fault in a test puts a crash report and a "quit unexpectedly"
    window on the user's Mac (2026-10-23, 05:55). Keep them out of this file."""
    src = Path(__file__).read_text(encoding="utf-8")
    for bad in ("string_" + "at(0)", "_sig" + "segv(", "faulthandler." + "_read_null"):
        assert bad not in src
