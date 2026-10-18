"""No console window for a tool ChromIQ starts on Windows (forum report,
ChromIQ 4.3.6): switching Run type to Verification flashed sixty
``xicclu.exe`` console windows, because the windowed ChromIQ.exe has no console
and ``subprocess`` gives a console child one of its own. See
``core/console_windows.py``.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from core import console_windows as CW


@pytest.fixture
def _installed(monkeypatch):
    """The rule installed as the windowed build has it: no console here."""
    CW.uninstall()
    monkeypatch.setattr(CW, "has_console", lambda: False)
    assert CW.install(platform="win32")
    yield
    CW.uninstall()


# ---- the rule ------------------------------------------------------------
def test_a_windowed_parent_starts_a_tool_without_a_window():
    assert CW.child_flags(0, parent_has_console=False) == CW.CREATE_NO_WINDOW


def test_a_parent_with_a_console_changes_nothing():
    """Run from a terminal (development, the suite) a child shares it."""
    assert CW.child_flags(0, parent_has_console=True) == 0


@pytest.mark.parametrize("asked", [CW.CREATE_NEW_CONSOLE, CW.DETACHED_PROCESS])
def test_a_caller_that_asked_for_its_own_console_keeps_it(asked):
    """`ArgyllRunner._run_winpty` starts chartread with CREATE_NEW_CONSOLE
    and hides that console itself; adding CREATE_NO_WINDOW would break it."""
    assert CW.child_flags(asked, parent_has_console=False) == asked


def test_other_flags_are_kept():
    high = 0x00000080            # HIGH_PRIORITY_CLASS
    assert CW.child_flags(high, parent_has_console=False) \
        == high | CW.CREATE_NO_WINDOW


# ---- install --------------------------------------------------------------
def test_install_is_a_no_op_off_windows():
    original = subprocess.Popen.__init__
    assert CW.install(platform="darwin") is False
    assert subprocess.Popen.__init__ is original


def test_install_is_idempotent_and_uninstall_restores():
    CW.uninstall()
    original = subprocess.Popen.__init__
    try:
        assert CW.install(platform="win32")
        wrapped = subprocess.Popen.__init__
        assert wrapped is not original
        assert CW.install(platform="win32")
        assert subprocess.Popen.__init__ is wrapped
    finally:
        CW.uninstall()
    assert subprocess.Popen.__init__ is original


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process creation")
def test_the_flag_reaches_create_process_and_a_piped_tool_still_works(
        _installed, monkeypatch):
    """What `xicclu_runner` does: stdin piped in, stdout read back."""
    import _winapi
    seen = []
    real = _winapi.CreateProcess

    def spy(*args):
        seen.append(args[5])                     # creationflags
        return real(*args)
    monkeypatch.setattr(_winapi, "CreateProcess", spy)
    r = subprocess.run([sys.executable, "-c",
                        "import sys; print(sys.stdin.read().upper())"],
                       input=b"ok", capture_output=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip() == b"OK"
    assert seen and all(f & CW.CREATE_NO_WINDOW for f in seen)


def test_the_wrapper_keeps_popens_signature(_installed):
    import inspect
    assert "creationflags" in inspect.signature(subprocess.Popen).parameters
    assert list(inspect.signature(subprocess.Popen.__init__).parameters)[:3] \
        == ["self", "args", "bufsize"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process creation")
def test_creationflags_given_positionally_is_rewritten_not_duplicated(
        _installed, monkeypatch):
    import _winapi
    seen = []
    real = _winapi.CreateProcess

    def spy(*args):
        seen.append(args[5])
        return real(*args)
    monkeypatch.setattr(_winapi, "CreateProcess", spy)
    #           args                       bufsize exe  in    out   err
    p = subprocess.Popen([sys.executable, "-c", "pass"], -1, None, None, None, None,
                         None, True, False, None, None, None, None, 0)
    #           preexec close shell cwd env  univ  startupinfo creationflags
    assert p.wait(timeout=120) == 0
    assert seen[0] & CW.CREATE_NO_WINDOW


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process creation")
def test_a_new_console_request_reaches_create_process_unchanged(
        _installed, monkeypatch):
    import _winapi
    seen = []
    real = _winapi.CreateProcess

    def spy(*args):
        seen.append(args[5])
        return real(*args)
    monkeypatch.setattr(_winapi, "CreateProcess", spy)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0                           # SW_HIDE, as _run_winpty does
    p = subprocess.Popen([sys.executable, "-c", "pass"],
                         creationflags=CW.CREATE_NEW_CONSOLE, startupinfo=si)
    assert p.wait(timeout=120) == 0
    assert not seen[0] & CW.CREATE_NO_WINDOW


# ---- the app and the drivers install it ----------------------------------
REPO = Path(__file__).resolve().parents[1]


def _calls(path: str, func: str) -> list[str]:
    """``name.attr`` calls inside *func* of *path*, read from the source:
    importing `main` or `capture_screens` here would build Qt state the
    suite does not want."""
    tree = ast.parse((REPO / path).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == func)
    return [f"{n.func.value.id}.{n.func.attr}" for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)]


@pytest.mark.parametrize("path,func", [("main.py", "main"),
                                       ("scripts/capture_screens.py", "build_app")])
def test_the_app_and_its_drivers_install_it(path, func):
    """A driver that does not install it would show consoles the shipped app
    does not, or hide them when the app does not (CLAUDE.md: a driver builds
    its QApplication like the app does)."""
    assert "console_windows.install" in _calls(path, func)
