"""No console window for any tool ChromIQ starts on Windows.

**THE SHIPPED ChromIQ.exe HAS NO CONSOLE, SO EVERY CONSOLE TOOL IT STARTS GETS
ONE OF ITS OWN.** Forum report (jctay, ChromIQ 4.3.6, Windows 11, 2026-10-18,
with a video): "command boxes" flashed for a split second right after Run type
was set to Verification. His log has ``xicclu: 15625 rows over 20 processes``
three times at that moment, the From Profile Gamut prefetch asking the profile
which colours it can print: sixty ``xicclu.exe`` started with
``subprocess.run``, each one a Windows Terminal window on screen. Reproduced
on screen under ``pythonw.exe`` (no console, as the windowed build): nine
console windows caught on the first switch, none after this module.

``QProcess`` never had the fault: Qt starts a console child with
``CREATE_NO_WINDOW`` whenever the parent has no console of its own
(``qprocess_win.cpp``). ``subprocess`` has no such default, and ChromIQ starts
tools through it in some fifty places; one of them (``ArgyllRunner``'s pipe
path) passed the flag by hand. Fixing them one by one would fix the places that
exist and not the next one written, so :func:`install` gives ``subprocess.Popen``
Qt's rule once, at start-up (``main()``, and the drivers' ``build_app``):

* only on Windows, and only while this process has no console. Run from a
  terminal (development, the test suite) a child still shares that console and
  prints into it exactly as before;
* a caller that asked for a console of its own keeps it: ``CREATE_NEW_CONSOLE``
  (``ArgyllRunner._run_winpty``, which hides it itself) or ``DETACHED_PROCESS``
  are left alone;
* a GUI program (Explorer, a viewer) ignores the flag, so nothing that should
  open a window stops doing so.

``tests/test_no_console_window_for_a_tool.py`` holds it.
"""
from __future__ import annotations

import functools
import subprocess
import sys

#: Index of ``creationflags`` in ``Popen.__init__``'s positional parameters
#: after ``self`` (args, bufsize, executable, stdin, stdout, stderr,
#: preexec_fn, close_fds, shell, cwd, env, universal_newlines, startupinfo,
#: creationflags).
_CREATIONFLAGS_POS = 13

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010
DETACHED_PROCESS = 0x00000008

#: Set on ``subprocess.Popen`` by :func:`install`; holds the original
#: ``__init__`` so :func:`uninstall` can put it back.
_MARK = "_chromiq_original_init"


def has_console() -> bool:
    """Whether this process has a console window (Windows only)."""
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:                                      # noqa: BLE001
        return True                  # cannot tell: change nothing


def child_flags(creationflags: int, *, parent_has_console: bool) -> int:
    """The ``creationflags`` a child is started with under Qt's rule."""
    if parent_has_console:
        return creationflags
    if creationflags & (CREATE_NEW_CONSOLE | DETACHED_PROCESS):
        return creationflags
    return creationflags | CREATE_NO_WINDOW


def install(*, platform: str = sys.platform) -> bool:
    """Give every ``subprocess.Popen`` (and so ``run``, ``check_output`` …)
    Qt's console rule. Idempotent; a no-op off Windows. Returns whether it is
    installed."""
    if platform != "win32":
        return False
    if hasattr(subprocess.Popen, _MARK):
        return True
    original = subprocess.Popen.__init__

    @functools.wraps(original)
    def __init__(self, *args, **kwargs):
        # `creationflags` is Popen's 14th parameter after self; a caller may
        # pass it positionally, so rewrite it where it was given.
        parent = has_console()
        if len(args) > _CREATIONFLAGS_POS:
            args = list(args)
            args[_CREATIONFLAGS_POS] = child_flags(
                args[_CREATIONFLAGS_POS], parent_has_console=parent)
        else:
            kwargs["creationflags"] = child_flags(
                kwargs.get("creationflags", 0), parent_has_console=parent)
        original(self, *args, **kwargs)

    setattr(subprocess.Popen, _MARK, original)
    subprocess.Popen.__init__ = __init__
    return True


def uninstall() -> None:
    """Put ``subprocess.Popen`` back as it was when :func:`install` ran (for
    tests and drivers; a wrapper added after `install` is dropped too)."""
    original = getattr(subprocess.Popen, _MARK, None)
    if original is not None:
        subprocess.Popen.__init__ = original
        delattr(subprocess.Popen, _MARK)
