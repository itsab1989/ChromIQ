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


def display_is_asleep() -> bool:
    """Whether the main display is asleep, per CoreGraphics.

    Basti, 2026-10-02: *"from now on i will make it so my display goes to sleep
    automatically after a while"*. A sleeping display is not a locked session
    (no password here), but the window server may hand back an empty buffer
    for a window on it, which `capture_window` would then refuse as flat."""
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework"
                         "/CoreGraphics")
        cg.CGMainDisplayID.restype = ctypes.c_uint32
        cg.CGDisplayIsAsleep.argtypes = [ctypes.c_uint32]
        cg.CGDisplayIsAsleep.restype = ctypes.c_bool
        return bool(cg.CGDisplayIsAsleep(cg.CGMainDisplayID()))
    except Exception:                                      # noqa: BLE001
        return False


def wake_the_display(timeout: float = 6.0) -> tuple[bool, str]:
    """Wake a sleeping display (``caffeinate -u``: asserts user activity, types
    nothing, moves no focus) and wait until CoreGraphics says it is awake."""
    if not display_is_asleep():
        return True, "the display was awake"
    try:
        subprocess.run(["caffeinate", "-u", "-t", "1"], timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                      # noqa: BLE001
        return False, "caffeinate could not be run"
    end = time.time() + timeout
    while time.time() < end:
        if not display_is_asleep():
            time.sleep(0.5)            # let it draw a frame before we look
            return True, "the display was asleep and a wake cleared it"
        time.sleep(0.25)
    return False, "the display is asleep and a wake did not wake it"


_KEEP_AWAKE = None


def keep_display_awake():
    """Hold macOS's keep-the-display-awake assertion for as long as THIS process
    lives (``caffeinate -d -w <pid>`` ends by itself when the driver exits), so
    Basti's display-sleep setting cannot blank the screen in the middle of a
    driver run, and works as he set it the rest of the time. Idempotent."""
    global _KEEP_AWAKE
    import os as _os
    import sys as _sys
    if _sys.platform != "darwin":
        return None
    if _KEEP_AWAKE is not None and _KEEP_AWAKE.poll() is None:
        return _KEEP_AWAKE
    try:
        _KEEP_AWAKE = subprocess.Popen(["caffeinate", "-d", "-w", str(_os.getpid())],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
    except Exception:                                      # noqa: BLE001
        _KEEP_AWAKE = None
    return _KEEP_AWAKE


def _by_geometry(win, cands: list, slack: float = 24.0):
    """The candidate whose bounds are where *win* says it is, or None.

    Separate from :func:`window_id_for` so a test can drive it with plain
    dictionaries and no window server at all: the fault it fixes is a CHOICE
    between two windows, and a choice can be proved without photographing
    anything.

    ``slack`` is in points and covers the frame shadow and a window the server
    has just finished moving. A match must be the closest candidate AND within
    the slack, so two windows genuinely stacked on the same rectangle still
    fall through to the caller's size rule rather than being guessed at.
    """
    try:
        g = win.frameGeometry()
        want = (float(g.x()), float(g.y()), float(g.width()), float(g.height()))
    except Exception:                                      # noqa: BLE001
        return None
    if want[2] <= 0 or want[3] <= 0:
        return None

    def _off(w) -> float:
        b = w.get("kCGWindowBounds") or {}
        try:
            got = (float(b["X"]), float(b["Y"]),
                   float(b["Width"]), float(b["Height"]))
        except (KeyError, TypeError, ValueError):
            return float("inf")
        return max(abs(a - c) for a, c in zip(want, got))

    best = min(cands, key=_off, default=None)
    return best if best is not None and _off(best) <= slack else None


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

        def _own(option) -> list:
            infos = Quartz.CGWindowListCopyWindowInfo(
                option | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID) or []
            return [w for w in infos
                    if int(w.get("kCGWindowOwnerPID", -1)) == pid]

        # ON SCREEN FIRST, THEN ALL, AND THE SECOND HALF IS NOT OPTIONAL.
        # `kCGWindowListOptionOnScreenOnly` lists what the window server is
        # currently compositing, so a window on another Space, or one the
        # display dropped while it slept, is simply absent and this returned
        # None. The caller then fell through to the rectangle route, which
        # cannot photograph an unfocused window and correctly refused: measured
        # 2026-09-13, two of five captures in one run were lost that way, the
        # same two on a re-run. `CGWindowListCreateImage` does not need the
        # window to be composited, so the id is worth having either way.
        import time as _time
        # **A WINDOW JUST SHOWN IS NOT YET WHERE QT SAYS IT IS.** Measured on
        # K2's driver, 2026-09-22: a message box `show()`n 900 ms earlier had
        # no title the window server knew and bounds that did not yet match
        # its `frameGeometry`, so the old fallback took the biggest window this
        # process owns and filed a photograph of the MAIN WINDOW under the
        # popup's name, 3 of 4 times on one run and 0 of 4 on the next. So ask
        # again for up to a second, and then give up rather than guess.
        pick = None
        for _attempt in range(10):
            cands = _own(Quartz.kCGWindowListOptionOnScreenOnly) \
                or _own(Quartz.kCGWindowListOptionAll)
            pick = _pick_window(win, cands, title)
            if pick is not None:
                break
            _time.sleep(0.1)
        return None if pick is None else int(pick["kCGWindowNumber"])
    except Exception:                                      # noqa: BLE001
        return None


def _pick_window(win, cands: list, title: str):
    """Which of this process's windows is *win*, or None when it cannot tell.

    A title the window server knows is trusted, and among several windows
    carrying it the geometry decides, then the size. **With no title match,
    only the geometry may answer.** The old rule fell back to the biggest
    window, which is right for a main window and wrong for every popup whose
    title the server has not been told (macOS gives a `QMessageBox` none), and
    a wrong id photographs a real window, so nothing downstream can see it.
    """
    if not cands:
        return None
    # A Qt app also owns tiny helper windows (tooltips, shadows), so a title
    # match is preferred over the whole list.
    # **AN EMPTY TITLE MATCHES NOTHING (adversary round on 528b7cfc).** On
    # macOS Qt compiles `QMessageBox::setWindowTitle` out, so every message
    # box asks for title "", and "every window whose name is empty" is then
    # every untitled window of the process: a message box behind the one
    # asked for, a sheet, a helper. The size rule then answered for the wrong
    # box, measured on screen. With no title only the geometry may answer.
    named = [w for w in cands
             if title and str(w.get("kCGWindowName") or "") == title]
    # THE GEOMETRY DECIDES BEFORE THE SIZE DOES, AND "biggest" ALONE
    # PHOTOGRAPHED THE WRONG WINDOW FOR AS LONG AS THIS HELPER HAS EXISTED.
    #
    # `ui.tooltip_button.InfoDialog` takes its PARENT's title, so a message
    # box over the Reference values window is also called "Reference
    # values". Both then land in `named`, `max(..., area)` picks the parent
    # because a message box is smaller than the window it covers, and the
    # capture comes back as the window BEHIND the thing it is filed as.
    # Measured on challenge round 31 against the pictures of round 30:
    # `C-said-en-1.png`, `E-stop-said-en-1.png` and `G-zip-said-en-1.png`
    # are all photographs of the parent, greyed out, with the sentence they
    # are named for nowhere in them. Nothing was faked; the helper simply
    # answered a different question.
    #
    # A widget knows where it is, so ask. `frameGeometry` is in logical
    # points and `kCGWindowBounds` is too (both are in the display's
    # points, not device pixels), so they compare directly, with a few
    # points of slack for the shadow and for a window the server has just
    # moved. Only a TITLE match may fall back to the size rule; see the
    # docstring for why no title and no geometry is None.
    exact = _by_geometry(win, named or cands)
    if exact is not None or not named:
        return exact
    return max(named, key=lambda w: (w["kCGWindowBounds"]["Width"]
                                     * w["kCGWindowBounds"]["Height"]))


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
            # BEST, NOT NOMINAL. `kCGWindowImageNominalResolution` hands back a
            # 1x picture of a 2x window, so every device pixel in the window is
            # averaged with its neighbour before anyone can look at it. A
            # tester found a one-device-pixel gap along the bottom of a split
            # patch (2026-09-17) that this helper physically could not show:
            # measured on the same window, nominal 560x1028, best 1120x2056,
            # and the offending row is only in the second. Proof of a pixel
            # must be taken at the resolution the pixel exists at.
            | Quartz.kCGWindowImageBestResolution)
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


def _is_one_flat_colour(path: Path) -> bool:
    """True when every sampled pixel of *path* is the same colour.

    **A WINDOW IS NEVER ONE COLOUR, AND A FAILED BUFFER OFTEN IS.** Measured
    2026-09-13: `CGWindowListCreateImage` returned a 960x717 image of pure
    black (mean 0.0) for a real, visible, correctly sized dialog, and the size
    check below waved it through because 960x717 is a plausible window. The
    round that produced it then compared that black rectangle against a good
    capture, got "34.75 % of pixels differ", and filed the pair as proof that
    two scans behaved differently. They did, but not one pixel of that picture
    showed it.

    The same shape as the wallpaper trap the region route already guards, and
    it needs its own guard because the window-id route skips that one: a window
    id cannot return the desktop, so nothing was checking what it DID return.
    """
    from PyQt6.QtGui import QImage
    im = QImage(str(path))
    if im.isNull():
        return True
    first = im.pixel(0, 0)
    for y in range(0, im.height(), 7):
        for x in range(0, im.width(), 7):
            if im.pixel(x, y) != first:
                return False
    return True


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


def _is_in_a_modal_loop(win) -> bool:
    """True when hiding ``win`` could end a modal ``exec()``: the window is a
    modal dialog itself, or any modal window is running right now (hiding
    its parent or a sibling is no safer)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    try:
        if win.isModal() or win.windowModality() != Qt.WindowModality.NonModal:
            return True
    except Exception:            # noqa: BLE001 - not a QWidget: be careful
        return True
    return QApplication.activeModalWidget() is not None


def capture_window(win, path: Path, settle: float = 0.6,
                   min_difference: float = 0.25,
                   allow_hide: bool = True) -> tuple[bool, str]:
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
    # …AND A SLEEPING DISPLAY IS WOKEN TOO (Basti lets it sleep after a while),
    # and kept awake for the rest of this driver run.
    keep_display_awake()
    if display_is_asleep():
        woke, why = wake_the_display()
        if not woke:
            return False, f"the display is asleep and could not be woken ({why})"
    path.parent.mkdir(parents=True, exist_ok=True)
    # NO raise_() / activateWindow() HERE ANY MORE. Basti, 2026-10-02: *"when
    # i am typing here and you bring the chromiq windows to the front i am
    # sometimes still typing while you make another window get focus"*. The
    # window-id capture below reads the window's own buffer and does not care
    # what is in front of it; only the rectangle fallback needs the window on
    # top, so only that path raises it.
    QApplication.processEvents()
    time.sleep(settle)

    # THE WINDOW'S OWN BUFFER FIRST. `-l` does not care what is stacked above
    # it, so the app does not have to steal focus from whatever launched it,
    # and the hide/show proof below is unnecessary: a window id cannot return
    # the desktop. The size is checked instead, because a minimised or
    # zero-sized window would give a picture of nothing.
    wid = window_id_for(win)
    if wid is not None:
        # THREE TRIES, BECAUSE AN EMPTY BUFFER IS OFTEN JUST AN EARLY ONE.
        # Measured 2026-09-13: on a run that began with the screen locked, two
        # of five captures came back as one flat colour and both succeeded on
        # the next attempt a moment later. The window server has the window;
        # it has not finished painting into the buffer this call reads. So the
        # flat-colour refusal below is a LAST word, not a first one.
        from PyQt6.QtGui import QImage
        for attempt in range(3):
            if attempt:
                QApplication.processEvents()
                time.sleep(0.5)
                # ASK AGAIN WHICH WINDOW IT IS. A native window can be
                # recreated under the same QWidget, and an id that was right
                # a second ago photographs nothing.
                wid = window_id_for(win) or wid
            if not _grab_window_id(wid, path):
                continue
            im = QImage(str(path))
            big = not im.isNull() and im.width() > 200 and im.height() > 200
            # ...AND IT HAS TO HAVE SOMETHING IN IT. See `_is_one_flat_colour`:
            # a plausible size is not a picture, and an empty buffer of the
            # right size was filed as evidence once.
            if big and not _is_one_flat_colour(path):
                return True, ""
            path.unlink(missing_ok=True)

    if allow_hide and _is_in_a_modal_loop(win):
        # F-11 (agent 18, 2026-10-05): the fallback below hides the window and
        # raises it. A driver photographed the modal "New patch set" window
        # with the default allow_hide=True: hiding it ended its exec() as
        # Rejected, the window came back as a stray non-modal window on
        # Basti's screen, and the driver waited for ever. A modal dialog, or
        # any window while a modal loop runs, is never hidden here.
        allow_hide = False
    if not allow_hide:
        # The rectangle fallback proves itself by HIDING the window, and hiding
        # a dialog that is inside exec() ends that exec() as Rejected: the
        # photograph would answer the question. A caller photographing a
        # pop-up (PopupWatchdog) says no.
        return False, ("the window could not be captured by its id, and the "
                       "rectangle fallback would have to hide it")
    win.raise_()                    # the rectangle needs the window on top
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


class FocusGiveBack:
    """Hand the keyboard back to whoever had it before the driver started.

    Basti, 2026-10-02: while he typed in the terminal, a driver brought a
    ChromIQ window to the front and his keystrokes went into the app. Measured
    the same night on macOS 27.0.1 (J_focus/ in that session's reports):

    * a Qt app started from a terminal becomes the active application as soon
      as its first window shows, whatever the flags: WA_ShowWithoutActivating,
      AA_PluginApplication and the Accessory policy all still took focus;
    * the Prohibited policy keeps focus but the window is then never put on
      screen at all, which breaks the on-screen rule;
    * re-activating the previous app from a background THREAD is refused, and
      macOS handed focus to Finder instead;
    * what works is the cooperative hand-over on the MAIN thread while this
      process is the active one: ``yieldActivationToApplication_`` and then
      ``activateWithOptions_`` on the previous app, back within about 0.3 s.

    Call :meth:`remember` BEFORE the QApplication exists (afterwards the
    frontmost app may already be the driver itself), :meth:`install` once it
    does, and :meth:`give_back` right after showing a window. Every later
    activation (application state goes Active) is handed back too, so a click
    by the user INTO a driven window is bounced as well, which is the point:
    nobody should type into a window a driver is using. Does nothing off
    macOS or without pyobjc.
    """

    def __init__(self):
        self.previous = None
        self.handed_back = 0

    def remember(self) -> "FocusGiveBack":
        try:
            import AppKit
            import os as _os
            front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
            if front is not None and int(front.processIdentifier()) != _os.getpid():
                self.previous = front
        except Exception:          # noqa: BLE001 - no pyobjc / not macOS
            self.previous = None
        return self

    def install(self, app) -> "FocusGiveBack":
        if self.previous is not None:
            from PyQt6.QtCore import QTimer
            app.applicationStateChanged.connect(self._state_changed)
            # …AND A POLL, because Qt does not always say so: macOS can make
            # the app active a second or two after its window shows, while
            # Qt's own state already reads Active, so no signal comes. Measured:
            # focus stayed with ChromIQ for 2 s with only the signal. The poll
            # runs on the main thread (the hand-over only works there) and does
            # nothing while another app is in front.
            self._poll = QTimer(app)
            self._poll.setInterval(50)
            self._poll.timeout.connect(self.give_back)
            self._poll.start()
        return self

    def _state_changed(self, state) -> None:
        from PyQt6.QtCore import Qt
        if state == Qt.ApplicationState.ApplicationActive:
            self.give_back()

    def give_back(self) -> bool:
        if self.previous is None:
            return False
        try:
            import AppKit
            import os as _os
            front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
            if front is None or int(front.processIdentifier()) != _os.getpid():
                return False             # not ours to hand over
            try:
                AppKit.NSApp.yieldActivationToApplication_(self.previous)
            except Exception:      # noqa: BLE001 - before macOS 14
                pass
            ok = bool(self.previous.activateWithOptions_(0))
            self.handed_back += ok
            return ok
        except Exception:          # noqa: BLE001
            return False


def in_modal_loop(w) -> bool:
    """True only once *w* is really inside its modal loop: visible, opaque and
    modal. A driver must wait for THIS before it answers a dialog.

    Agent 18's second hang (2026-10-05 02:04, reproduced 02:13): the patch
    editor's "New patch set" window (``_NewChartDialog.exec``) first shows
    itself NON-modally at opacity 0 and pumps events to realise its 3D view,
    and only then enters ``QDialog.exec()``. The driver looked for "a visible
    top-level _NewChartDialog", found it in that first phase and pressed
    Create; ``accept()`` outside the modal loop only hid it, and the override
    then entered ``exec()`` and showed the window again, modal, with nobody
    left to answer it. A working window is never dismissed by
    :class:`PopupWatchdog`, so it stayed on Basti's screen."""
    from PyQt6.QtCore import Qt
    try:
        if not w.isVisible() or w.windowOpacity() < 0.99:
            return False
        return bool(w.isModal()
                    or w.windowModality() != Qt.WindowModality.NonModal)
    except RuntimeError:              # deleted under us
        return False


class StepGuard:
    """A driver that ends ITSELF, whatever it is waiting for.

    A watcher THREAD (not a Qt timer: a Qt timer cannot fire while the main
    thread is blocked outside the event loop) holds a deadline per scripted
    step and one for the whole run. When either passes, it writes every
    thread's stack to ``hang-<step>.txt`` in ``report_dir`` (so the hang names
    its own line), calls ``on_timeout`` if given (no Qt calls there: it runs
    on the watcher thread), and ends the process with ``os._exit(code)``. A
    dead process leaves no window on screen and holds no keyboard; the
    display assertion of :func:`keep_display_awake` ends with it (``-w pid``).

    Usage::

        guard = StepGuard(report_dir, step_s=300, total_s=3 * 3600).start()
        guard.step("2 new patch set")            # default budget
        guard.step("5 engine build", 2 * 3600)   # a long step says so
        guard.stop()
    """

    def __init__(self, report_dir, *, step_s: float = 300.0,
                 total_s: float = 3 * 3600.0, code: int = 3,
                 on_timeout=None, log=print):
        self.report_dir = Path(report_dir)
        self.step_s, self.total_s, self.code = float(step_s), float(total_s), int(code)
        self.on_timeout, self._log = on_timeout, log
        self.name = "start"
        self._t0 = time.monotonic()
        self._deadline = self._t0 + self.step_s
        self._stopped = False
        self._thread = None
        self.fired: "str | None" = None

    def start(self) -> "StepGuard":
        import threading
        self._thread = threading.Thread(target=self._watch, name="StepGuard",
                                        daemon=True)
        self._thread.start()
        return self

    def step(self, name: str, seconds: "float | None" = None) -> None:
        self.name = str(name)
        self._deadline = time.monotonic() + float(seconds or self.step_s)
        self._log(f"[guard] step {self.name!r}: "
                  f"{float(seconds or self.step_s):.0f} s")

    def stop(self) -> None:
        self._stopped = True

    def _watch(self) -> None:
        while not self._stopped:
            now = time.monotonic()
            why = None
            if now > self._deadline:
                why = f"step {self.name!r} ran past its budget"
            elif now - self._t0 > self.total_s:
                why = f"the run ran past its total budget ({self.total_s:.0f} s)"
            if why is not None:
                self._fire(why)
                return
            time.sleep(0.5)

    def _fire(self, why: str) -> None:
        import faulthandler
        import os
        self.fired = why
        try:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in self.name)[:60]
            out = self.report_dir / f"hang-{safe}.txt"
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} HANG: {why}\n\n")
                fh.flush()
                faulthandler.dump_traceback(fh, all_threads=True)
            self._log(f"[guard] HANG: {why}; stacks in {out}")
            if self.on_timeout is not None:
                self.on_timeout(why)
        finally:
            os._exit(self.code)


class PopupWatchdog:
    """Notice every pop-up a driver runs into, record it, and keep the run moving.

    Basti, 2026-10-02: *"the drivers that either you or your agents are
    creating get stuck at some pop ups. would be nice if they could recognize
    this"*. A driver clicks something, the app answers with a question nobody
    scripted (a confirmation, a warning, a file dialog), and ``exec()`` sits
    there for ever with the driver's own code waiting behind it.

    A timer in the driver's process looks every ``interval_ms`` for a MODAL
    window: ``QApplication.activeModalWidget()`` plus any visible top-level
    ``QMessageBox``. Qt keeps delivering timer events inside a dialog's
    ``exec()``, so this runs even while the driver is blocked.

    **ONLY QUESTIONS ARE ANSWERED BY DEFAULT.** A message box, an input box
    and a file dialog are questions; any other modal window (the Measurement
    Report window, Preferences, the patch-set editor) is a working window the
    driver opened on purpose. Those are logged once as ``window`` events and
    never closed unless ``dismiss_windows=True``. The first version closed the
    Measurement Report window two seconds after a driver opened it (challenge
    of 2026-10-02, F_challenge_182).

    For each pop-up it writes title, text and buttons to ``popups.log`` in
    ``report_dir`` and, with ``photograph=True``, a picture of it. Then:

    * a matching ``expect(pattern, button)`` rule answers it at once, which is
      how a driver says "this question is part of the scenario";
    * otherwise, after ``grace_s`` seconds, the policy decides: ``"dismiss"``
      (the default) presses the dialog's own Escape/Cancel answer, ``"report"``
      leaves it open and logs ``STUCK`` every 10 s, ``"fail"`` dismisses it
      and sets :attr:`unexpected`, so the driver can refuse to call its run a
      pass.

    Dismissing is never the same as passing: every unscripted pop-up is in
    :attr:`events` with ``"unexpected": True`` and belongs in the round's
    report. A native file dialog on macOS is a ``QFileDialog`` to Qt, so it is
    caught and rejected the same way.

    Usage::

        dog = PopupWatchdog(report_dir, photograph=True)
        dog.expect(r"Create a new report or update", "Create new")
        dog.start()
        ... drive the app ...
        dog.stop()
        if dog.unexpected_events(): report them at the top of REPORT.md
    """

    def __init__(self, report_dir: "Path | None" = None, *,
                 policy: str = "dismiss", grace_s: float = 1.5,
                 interval_ms: int = 400, photograph: bool = False,
                 dismiss_windows: bool = False, log=print):
        if policy not in ("dismiss", "report", "fail"):
            raise ValueError(f"unknown policy {policy!r}")
        self.report_dir = Path(report_dir) if report_dir else None
        self.policy, self.grace_s = policy, grace_s
        self.interval_ms, self.photograph, self._log = interval_ms, photograph, log
        self.dismiss_windows = dismiss_windows
        self.rules: list[tuple] = []
        self.events: list[dict] = []
        self.unexpected = False
        #: id(widget) -> (widget, first seen). Holding the widget keeps its id
        #: from being reused by a NEW box while this one is remembered.
        self._first_seen: dict[int, tuple] = {}
        self._last_stuck_note: dict[int, float] = {}
        self._event_for: dict[int, dict] = {}
        self._rule_for: dict[int, tuple] = {}
        self._answered: set[int] = set()
        #: Pop-ups a dismissal is already scheduled for. Once is enough: while
        #: the dismissal's own handler runs (it may ask a second question) the
        #: first pop-up is still visible, and dismissing it again every tick
        #: pressed Cancel over and over, each press asking again.
        self._dismissed: set[int] = set()
        self._timer = None

    # -- the driver's side ----------------------------------------------------
    def expect(self, pattern: str, button: str) -> "PopupWatchdog":
        """Answer a pop-up whose title or text matches *pattern* (a regular
        expression, case-insensitive) by pressing the button labelled
        *button* (ampersands ignored, case-insensitive)."""
        import re
        self.rules.append((re.compile(pattern, re.I | re.S), button))
        return self

    def start(self) -> "PopupWatchdog":
        from PyQt6.QtCore import QTimer
        self._timer = QTimer()
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._tick)       # a bound method, never a lambda
        self._timer.start()
        return self

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False

    def unexpected_events(self) -> list[dict]:
        return [e for e in self.events if e["unexpected"]]

    # -- what it looks at -----------------------------------------------------
    @staticmethod
    def _popups() -> list:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        found = []
        modal = QApplication.activeModalWidget()
        if modal is not None and modal.isVisible():
            found.append(modal)
        for w in QApplication.topLevelWidgets():
            if not w.isVisible() or w in found:
                continue
            # A WINDOW-modal box (a sheet on its parent, `open()` rather than
            # `exec()`) is not always `activeModalWidget()`, so a sweep of the
            # top-level windows finds it too (agent 18b, 2026-10-05, F-11).
            if (isinstance(w, (QMessageBox, QInputDialog, QFileDialog))
                    or w.windowModality() == Qt.WindowModality.WindowModal):
                found.append(w)
        return found

    @staticmethod
    def _buttons(w) -> list:
        from PyQt6.QtWidgets import QAbstractButton
        return [b for b in w.findChildren(QAbstractButton)
                if b.isVisible() and b.text().strip()]

    @classmethod
    def describe(cls, w) -> dict:
        from PyQt6.QtWidgets import QLabel, QMessageBox
        if isinstance(w, QMessageBox):
            text = "\n".join(t for t in (w.text(), w.informativeText()) if t)
        else:
            text = "\n".join(l.text() for l in w.findChildren(QLabel)
                             if l.isVisible() and l.text().strip())
        return {"class": type(w).__name__, "title": w.windowTitle(),
                "text": text[:1200],
                "buttons": [b.text().replace("&", "") for b in cls._buttons(w)]}

    #: Widgets that make a dialog a WORKING window rather than a question.
    _WORKING_WIDGETS = ("QTabWidget", "QAbstractItemView", "QComboBox",
                        "QLineEdit", "QAbstractSpinBox", "QTextEdit",
                        "QPlainTextEdit", "QWebEngineView", "QGraphicsView")

    @classmethod
    def is_question(cls, w) -> bool:
        """A pop-up that asks something, as opposed to a working window.

        Message, input and file dialogs always are. A plain modal QDialog is
        one too when it holds nothing to work with (no tabs, lists, tables,
        combo boxes, input fields, editors or web views) and at most four
        buttons: ChromIQ's own "Strip Read Quickly" is a QDialog, and the first
        watchdog left it hanging (review K_review_beta1). The Measurement Report
        window, Preferences and the patch-set editor all hold working widgets."""
        from PyQt6.QtWidgets import (QDialog, QFileDialog, QInputDialog,
                                     QMessageBox, QPushButton, QWidget)
        if isinstance(w, (QMessageBox, QInputDialog, QFileDialog)):
            return True
        if not isinstance(w, QDialog):
            return False
        for child in w.findChildren(QWidget):
            if not child.isVisible():
                continue
            names = {k.__name__ for k in type(child).__mro__}
            if names & set(cls._WORKING_WIDGETS):
                return False
        buttons = [b for b in w.findChildren(QPushButton) if b.isVisible()]
        return 0 < len(buttons) <= 4

    # -- what it does ---------------------------------------------------------
    def _find_button(self, w, label: str):
        want = label.replace("&", "").strip().lower()
        for b in self._buttons(w):
            if b.text().replace("&", "").strip().lower() == want:
                return b
        return None

    @staticmethod
    def _dismiss(w) -> str:
        """Dismiss *w* from a ZERO-DELAY timer, never inside this tick: a
        dismissal that opens another question would otherwise run that
        question's exec() inside the watchdog's own timer slot, and nothing
        could look at it until it closed (review K_review_beta1)."""
        from PyQt6.QtCore import QEvent, Qt, QTimer
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
        if isinstance(w, QMessageBox) and w.escapeButton() is not None:
            label = w.escapeButton().text().replace("&", "")
            QTimer.singleShot(0, w.escapeButton().click)
            return f"pressed its Escape answer '{label}'"
        if isinstance(w, QDialog):
            # A REAL Escape key, never reject(): a QMessageBox finds its own
            # Escape answer (Cancel, Stop) only when the key arrives, and
            # reject() from code leaves it with no answer at all, which
            # "Stuck Print Jobs" once read as "print" (review P_review2_beta1
            # W-1). A plain QDialog's Escape is its reject(), as for a user.
            #
            # A QMessageBox with NO Escape answer (only Accept/Destructive
            # buttons, say "Save" + "Discard") ignores the key and stays open,
            # and the watchdog dismisses a pop-up only once, so the driver
            # hung behind it (review T_review_beta2). Such a box is closed
            # with reject() after a grace period: no answer, which every
            # question in the app reads as "do nothing".
            def _fallback(w=w):
                from PyQt6 import sip
                if not sip.isdeleted(w) and w.isVisible():
                    w.reject()

            def _press(w=w):
                for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                    QApplication.sendEvent(w, QKeyEvent(
                        kind, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
                if isinstance(w, QMessageBox):
                    QTimer.singleShot(1000, _fallback)
            QTimer.singleShot(0, _press)
            return "pressed Escape"
        QTimer.singleShot(0, w.close)
        return "closed it"

    def _note(self, line: str) -> None:
        self._log(f"[popup] {line}")
        if self.report_dir is not None:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            with open(self.report_dir / "popups.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S ") + line + "\n")

    def _tick(self) -> None:
        self._ticking = True
        try:
            self._tick_body()
        finally:
            self._ticking = False

    def _tick_body(self) -> None:
        now = time.monotonic()
        live = self._popups()
        alive_ids = {id(w) for w in live}
        for gone in [k for k, (held, _t) in self._first_seen.items()
                     if k not in alive_ids or not any(w is held for w in live)]:
            self._first_seen.pop(gone, None)
            self._last_stuck_note.pop(gone, None)
            self._event_for.pop(gone, None)
            self._rule_for.pop(gone, None)
            self._answered.discard(gone)
            self._dismissed.discard(gone)
        for w in live:
            try:
                self._look_at(w, now)
            except RuntimeError as exc:     # deleted under us between ticks
                self._note(f"  a pop-up went away while being looked at ({exc})")

    def _look_at(self, w, now: float) -> None:
        from PyQt6.QtCore import QTimer
        key = id(w)
        if key not in self._first_seen:
            self._first_sight(w, key, now)
        event = self._event_for[key]
        age = now - self._first_seen[key][1]
        rule = self._rule_for.get(key)
        if rule is not None and key not in self._answered:
            button = self._find_button(w, rule[1])
            if button is not None:
                # DEFERRED, not clicked inside this tick: an answer that opens
                # a second question would otherwise run that question's exec()
                # inside this timer slot, and the watchdog could not look at
                # it until it closed (challenge G, 2026-10-02).
                self._answered.add(key)
                QTimer.singleShot(0, button.click)
                event["action"] = f"answered '{rule[1]}'"
                self._note(f"  {event['action']}")
                return
            if age < self.grace_s:
                return            # a button may still be added; look again
            self._answered.add(key)
            event["action"] = f"EXPECTED BUTTON '{rule[1]}' NOT FOUND"
            event["unexpected"] = True
            self._note(f"  {event['action']}")
        if key in self._answered and rule is not None and event["action"].startswith("answered"):
            return
        if age < self.grace_s:
            return
        if not self.is_question(w) and not self.dismiss_windows:
            return                              # a working window: leave it be
        if self.policy == "report":
            if now - self._last_stuck_note.get(key, 0) >= 10:
                self._last_stuck_note[key] = now
                self._note(f"STUCK on '{w.windowTitle()}' for {age:.0f} s")
            return
        if key in self._dismissed:
            return
        self._dismissed.add(key)
        action = self._dismiss(w)
        event["action"] = "; ".join(a for a in (event["action"], action) if a)
        if self.policy == "fail":
            self.unexpected = True
        self._note(f"  unscripted, {action}")

    def _first_sight(self, w, key: int, now: float) -> None:
        info = self.describe(w)
        haystack = f"{info['title']}\n{info['text']}"
        self._first_seen[key] = (w, now)
        rule = next(((p, b) for p, b in self.rules if p.search(haystack)), None)
        if rule is not None:
            self._rule_for[key] = rule
        question = self.is_question(w)
        event = dict(info, kind="question" if question else "window",
                     unexpected=rule is None and question, action="")
        self.events.append(event)
        self._event_for[key] = event
        self._note(f"SEEN {info['class']} '{info['title']}' "
                   f"buttons={info['buttons']} text={info['text'][:300]!r}")
        if self.photograph and self.report_dir is not None:
            # DEFERRED, never inside this tick (agent 18b, 2026-10-05, third
            # hang): capture_window pumps events, so the driver's own code ran
            # INSIDE the watchdog's tick, and Qt does not fire a timer again
            # while its slot is still on the stack. The watchdog went blind
            # for the rest of the run and never answered the next question.
            from PyQt6.QtCore import QTimer
            shot = self.report_dir / f"popup_{len(self.events):03d}.png"
            QTimer.singleShot(0, lambda w=w, shot=shot: self._photograph(w, shot))

    def _photograph(self, w, shot) -> None:
        from PyQt6 import sip
        if sip.isdeleted(w) or not w.isVisible():
            self._note(f"  NO PHOTO: {shot.name}, the pop-up was gone")
            return
        ok, why = capture_window(w, shot, allow_hide=False)
        self._note(f"  photo {shot.name}" if ok else f"  NO PHOTO: {why}")
