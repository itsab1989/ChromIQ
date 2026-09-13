#!/usr/bin/env python3
"""Photograph a real window, or say plainly that it could not be done.

CLAUDE.md: a `widget.grab()` render is not a screenshot, and an on-screen run
that cannot open or photograph a window is a FINDING to report, never a silent
fallback. This module exists because a driver found the opposite failure: it
called ``screencapture -R`` on the window's frame rectangle, got back 4.4 MB of
desktop wallpaper, and its own "a real screenshot was taken" check passed on the
file size. The screen was LOCKED. macOS keeps drawing into the window server
while the session is locked, so the window really was there, and every capture
came back as the desktop picture with no window, no menu bar and no dock.

Two guards, because either alone can be fooled:

* ``session_is_locked()`` asks the window server directly. A locked session
  cannot produce a photograph of anything, so the capture is refused before it
  is taken rather than judged afterwards.
* ``capture_window()`` then proves the picture actually contains the window: it
  photographs the same rectangle with the window hidden and requires the two to
  differ. A permission failure, a window on another Space and a window behind
  another application all fail that test; a real photograph passes it.

``CGPreflightScreenCaptureAccess`` is NOT one of the guards. It answered True on
the locked session that produced the wallpaper.
"""
from __future__ import annotations

import ctypes
import subprocess
import time
from pathlib import Path


def session_is_locked() -> bool:
    """Whether the login session's screen is locked, per the window server."""
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework"
                         "/CoreGraphics")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework"
                         "/CoreFoundation")
        cg.CGSessionCopyCurrentDictionary.restype = ctypes.c_void_p
        cf.CFDictionaryGetValue.restype = ctypes.c_void_p
        cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                                 ctypes.c_uint32]
        cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                        ctypes.c_void_p]
        d = cg.CGSessionCopyCurrentDictionary()
        if not d:
            return False
        key = cf.CFStringCreateWithCString(None, b"CGSSessionScreenIsLocked",
                                           0x08000100)   # kCFStringEncodingUTF8
        v = cf.CFDictionaryGetValue(d, key)
        if not v:
            return False
        out = ctypes.c_int()
        cf.CFNumberGetValue(v, 9, ctypes.byref(out))       # kCFNumberIntType
        return bool(out.value)
    except Exception:                                      # noqa: BLE001
        return False


def wake_the_screen(timeout: float = 6.0) -> tuple[bool, str]:
    """Try to clear a locked screen, and say what happened.

    **A LOCKED SCREEN IS NOT AUTOMATICALLY A BLOCKER, AND ONE ROUND REPORTED IT
    AS ONE.** Basti, 2026-09-13: *"my screen never needs a password to be
    unlocked"*. On a session with no password on the lock, asserting user
    activity dismisses it, and every capture then works. The round that spent a
    morning writing "the screen is locked, so there are no photographs" had the
    fix available the whole time and never tried it. That is also the honest
    explanation for why earlier rounds "managed to unlock the screen" and this
    one did not: nobody unlocked anything, they woke a display that happened to
    be asleep.

    So the order is: ask, WAKE, ask again, and only then give up. When a
    password IS required the wake changes nothing and the caller gets the same
    refusal it always got, with the difference that it has now been earned.

    ``caffeinate -u`` asserts user activity; it does not type anything and it
    cannot defeat a password.
    """
    if not session_is_locked():
        return True, "the screen was not locked"
    try:
        subprocess.run(["caffeinate", "-u", "-t", "1"], timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                      # noqa: BLE001
        return False, "caffeinate could not be run"
    end = time.time() + timeout
    while time.time() < end:
        if not session_is_locked():
            return True, "the screen was locked and a wake cleared it"
        time.sleep(0.25)
    return False, ("the screen is locked and a wake did NOT clear it, so this "
                   "session wants a password; unlock it by hand")


def window_id_for(win) -> "int | None":
    """The CGWindowID of *win*, found by this process's pid and the title.

    **A WINDOW DOES NOT HAVE TO BE IN FRONT TO BE PHOTOGRAPHED, and requiring
    it to be cost this round its pictures too.** `screencapture -R` copies a
    RECTANGLE of the screen, so anything stacked above the window is what comes
    out, and the guard below correctly refused it: the app's window sat behind
    the terminal that launched it, and the capture was 0 % different from the
    same rectangle with the window hidden. `win.raise_()` cannot fix that on
    macOS, because a process that was never activated cannot bring itself to
    the front.

    `screencapture -l <id>` copies the WINDOW's own buffer instead, so the
    stacking order stops mattering. Returns None when pyobjc is not installed
    or the window cannot be matched, and the caller falls back to the rectangle.
    """
    try:
        import Quartz
    except ImportError:
        return None
    import os as _os
    try:
        title = win.windowTitle()
        pid = _os.getpid()
        infos = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID) or []
        cands = [w for w in infos
                 if int(w.get("kCGWindowOwnerPID", -1)) == pid]
        if not cands:
            return None
        # The biggest window this process owns, preferring an exact title
        # match: a Qt app also owns tiny helper windows (tooltips, shadows).
        named = [w for w in cands if str(w.get("kCGWindowName") or "") == title]
        pick = max(named or cands,
                   key=lambda w: (w["kCGWindowBounds"]["Width"]
                                  * w["kCGWindowBounds"]["Height"]))
        return int(pick["kCGWindowNumber"])
    except Exception:                                      # noqa: BLE001
        return None


def _grab_window_id(wid: int, path: Path) -> bool:
    """Photograph one window by id, through Quartz rather than the CLI.

    **`screencapture -l` DOES NOT WORK ON THIS MACHINE AND THE API BEHIND IT
    DOES.** Measured 2026-09-13 on macOS 15.6 (Darwin 24.6.0), Screen Recording
    granted, screen unlocked, on a plain Qt window this process had just
    opened:

    | route | result |
    |---|---|
    | `screencapture -R <the window's rect>` | the DESKTOP PICTURE. The window is not composited on the Space being captured, so the rectangle contains wallpaper, and `capture_window`'s hide/show guard correctly called it 0 % different |
    | `screencapture -l <window id>` | exit 1, *"could not create image from window"* |
    | `CGWindowListCreateImage(..., kCGWindowListOptionIncludingWindow, wid, ...)` | **a 700x528 picture of the window, title bar and all** |

    The CLI is the one thing that fails. CLAUDE.md recorded *"could not create
    image from window"* as a symptom of the missing Screen Recording grant; it
    survives the grant, so it is not that.

    The Quartz route also does not care about stacking or Spaces, which is what
    makes it usable from a driver: the app never has to steal focus, and on
    macOS 15 it cannot anyway (`NSRunningApplication.activateWithOptions_`
    returns True and `isActive` stays False).
    """
    try:
        import Quartz
        from CoreFoundation import (CFURLCreateWithFileSystemPath,
                                    kCFURLPOSIXPathStyle)
    except ImportError:
        return False
    try:
        img = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            wid,
            Quartz.kCGWindowImageBoundsIgnoreFraming
            | Quartz.kCGWindowImageNominalResolution)
        if img is None or Quartz.CGImageGetWidth(img) < 1:
            return False
        url = CFURLCreateWithFileSystemPath(None, str(path),
                                            kCFURLPOSIXPathStyle, False)
        dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
        if dest is None:
            return False
        Quartz.CGImageDestinationAddImage(dest, img, None)
        if not Quartz.CGImageDestinationFinalize(dest):
            return False
    except Exception:                                      # noqa: BLE001
        return False
    return path.exists() and path.stat().st_size > 0


def _grab_region(rect: str, path: Path) -> bool:
    try:
        subprocess.run(["screencapture", "-x", "-R", rect, str(path)],
                       check=True, timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                      # noqa: BLE001
        return False
    return path.exists() and path.stat().st_size > 0


def _difference(a: Path, b: Path) -> float:
    """Share of sampled pixels that differ between two captures, 0..1."""
    from PyQt6.QtGui import QImage
    ia, ib = QImage(str(a)), QImage(str(b))
    if ia.isNull() or ib.isNull() or ia.size() != ib.size():
        return 1.0 if not (ia.isNull() or ib.isNull()) else 0.0
    n = diff = 0
    for y in range(0, ia.height(), 4):
        for x in range(0, ia.width(), 4):
            n += 1
            ca, cb = ia.pixel(x, y), ib.pixel(x, y)
            if ca != cb:
                diff += 1
    return diff / n if n else 0.0


def capture_window(win, path: Path, settle: float = 0.6,
                   min_difference: float = 0.25) -> tuple[bool, str]:
    """Photograph *win* into *path*. Returns (ok, why-not).

    The caller is expected to REPORT a False at the top of its result. The file
    is not left behind when the capture could not be proved, so a later reader
    cannot mistake wallpaper for evidence.
    """
    from PyQt6.QtWidgets import QApplication
    # ASK, WAKE, ASK AGAIN. See `wake_the_screen`: a lock with no password on
    # it is cleared by asserting user activity, and refusing before trying is
    # what turned one round's proof into a paragraph of excuses.
    if session_is_locked():
        woke, why = wake_the_screen()
        if not woke:
            return False, ("the login session's screen is LOCKED and a wake "
                           f"did not clear it ({why}), so the window server "
                           "hands every capture the desktop picture instead "
                           "of the window; unlock the screen and run again")
    path.parent.mkdir(parents=True, exist_ok=True)
    win.raise_()
    win.activateWindow()
    QApplication.processEvents()
    time.sleep(settle)

    # THE WINDOW'S OWN BUFFER FIRST. `-l` does not care what is stacked above
    # it, so the app does not have to steal focus from whatever launched it,
    # and the hide/show proof below is unnecessary: a window id cannot return
    # the desktop. The size is checked instead, because a minimised or
    # zero-sized window would give a picture of nothing.
    wid = window_id_for(win)
    if wid is not None and _grab_window_id(wid, path):
        from PyQt6.QtGui import QImage
        im = QImage(str(path))
        if not im.isNull() and im.width() > 200 and im.height() > 200:
            return True, ""
        path.unlink(missing_ok=True)

    g = win.frameGeometry()
    rect = f"{g.x()},{g.y()},{g.width()},{g.height()}"
    if not _grab_region(rect, path):
        return False, "screencapture refused the window's rectangle"

    # Prove the picture contains the WINDOW and not what is behind it.
    empty = path.with_name(path.stem + "__behind.png")
    win.hide()
    QApplication.processEvents()
    time.sleep(0.35)
    got_empty = _grab_region(rect, empty)
    win.show()
    win.raise_()
    QApplication.processEvents()
    time.sleep(settle)
    if not got_empty:
        empty.unlink(missing_ok=True)
        return True, ""            # cannot prove it either way; keep the file
    d = _difference(path, empty)
    empty.unlink(missing_ok=True)
    if d < min_difference:
        path.unlink(missing_ok=True)
        return False, (f"the capture is {d:.0%} different from the same "
                       "rectangle with the window HIDDEN, so it is a picture "
                       "of what is behind the window, not of the window")
    return True, ""
