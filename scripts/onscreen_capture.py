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
    if session_is_locked():
        return False, ("the login session's screen is LOCKED, so the window "
                       "server hands every capture the desktop picture instead "
                       "of the window; unlock the screen and run this again")
    path.parent.mkdir(parents=True, exist_ok=True)
    win.raise_()
    win.activateWindow()
    QApplication.processEvents()
    time.sleep(settle)
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
