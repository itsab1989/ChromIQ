"""Wait for macOS's native-fullscreen transition before opening a window.

``showFullScreen()`` on macOS is **native** fullscreen: the window is moved to a
Space of its own, and the move is animated. Two things follow that no fixed
delay can paper over.

**A window shown while the transition runs lands on the wrong Space.** macOS
puts a new window on whichever Space is active *at that moment*, and until the
transition completes that is still the Space the app came from. Measured on a
first launch with the window state restored to fullscreen: the main window went
to its new Space at ~1.2 s, while the welcome dialog — shown on its 100 ms timer
— stayed behind on the old one. The user is then looking at a fullscreen window
on one Space with a dialog stranded on another.

**A modal shown while the transition runs can abort it.** macOS answers with
``NSWindowDidFailToEnterFullScreenNotification`` and the window drops back to
its plain geometry — while Qt's ``isFullScreen()`` still returns True, so
``MainWindow.closeEvent`` then files a window state that was never on screen and
the next launch repeats it.

**Qt cannot tell you when the transition is over.** ``QWindow.
windowStateChanged`` and ``QEvent.WindowStateChange`` both arrive at the *start*
of it (measured: 39 ms, against 1747 ms for the real end). The only truthful
signal is AppKit's, so this module listens for it directly. pyobjc is already a
hard macOS dependency (``requirements.txt``) and is bundled by ``ChromIQ.spec``,
but every use of it here is optional: if anything at all is missing the caller
is told so and keeps its own timer.
"""
from __future__ import annotations

import sys
from typing import Callable

from core.logger import get_logger

log = get_logger(__name__)

# By NAME, not by pyobjc constant: the failure notification is real and was
# measured arriving, but pyobjc exports no symbol for it.
_WILL_ENTER = "NSWindowWillEnterFullScreenNotification"
_DID_ENTER = "NSWindowDidEnterFullScreenNotification"
_DID_FAIL = "NSWindowDidFailToEnterFullScreenNotification"

#: Observer tokens (and the blocks they wrap) must outlive this function call or
#: the notification centre delivers to freed memory.
_live: list = []


class FullScreenTransition:
    """Fires ``callback`` exactly once: when the transition has settled, or when
    it is clear there is not going to be one.

    Timing is injected (``schedule``) so the whole decision table is testable
    without a screen. All four routes are guarded by ``_fired``, because two of
    them can easily race: a transition that fails late still has the overall
    deadline armed behind it.

    * ``note_will_enter`` — a transition has begun; the *start* deadline is now
      moot and we wait for it to end.
    * ``note_settled`` — it ended (entered, or failed to). Fire.
    * start deadline — nothing began, so there is nothing to wait for. Fire.
      This is the ordinary case for a window that is not being restored to
      fullscreen at all, and for Qt's non-native fullscreen path.
    * overall deadline — a transition began and never reported an end. Fire
      anyway: a missing notification must never mean "no start-up dialogs".
    """

    def __init__(
        self,
        callback: Callable[[], None],
        *,
        start_ms: int = 400,
        settle_ms: int = 120,
        timeout_ms: int = 5000,
        schedule: Callable[[int, Callable[[], None]], None] | None = None,
    ) -> None:
        self._callback = callback
        self._start_ms = start_ms
        self._settle_ms = settle_ms
        self._timeout_ms = timeout_ms
        self._schedule = schedule or _qt_schedule
        self._began = False
        self._fired = False
        self.reason = ""

    def arm(self) -> None:
        self._schedule(self._start_ms, self._start_deadline)
        self._schedule(self._timeout_ms, self._overall_deadline)

    # -- what AppKit tells us -------------------------------------------
    def note_will_enter(self) -> None:
        self._began = True

    def note_settled(self, reason: str = "the transition finished") -> None:
        self._fire(reason)

    # -- the two deadlines ----------------------------------------------
    def _start_deadline(self) -> None:
        if not self._began:
            self._fire("no transition began")

    def _overall_deadline(self) -> None:
        self._fire("the transition never reported an end")

    # -------------------------------------------------------------------
    def _fire(self, reason: str) -> None:
        if self._fired:
            return
        self._fired = True
        self.reason = reason
        log.debug("start-up windows released: %s", reason)
        # Never straight out of an AppKit notification: give the window server
        # the tick it needs to finish settling before another window is put on
        # top of the one it has just moved.
        self._schedule(self._settle_ms, self._callback)


def _qt_schedule(ms: int, fn: Callable[[], None]) -> None:
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(ms, fn)


def run_after_fullscreen_transition(widget, callback: Callable[[], None],
                                    **kwargs) -> bool:
    """Call ``callback`` once ``widget``'s fullscreen transition has settled.

    Returns True if it took the job on, False if the caller must fall back to
    its own timer (not macOS, no pyobjc, no native window yet). ``widget`` must
    already be shown — the ``NSWindow`` is reached through its native handle.
    """
    if sys.platform != "darwin":
        return False
    try:
        import ctypes

        # AppKit, not Foundation: it re-exports NSNotificationCenter, and it is
        # the one ChromIQ.spec collects for the frozen bundle.
        import AppKit
        import objc
    except Exception:                       # noqa: BLE001 — pyobjc is optional here
        log.debug("no pyobjc: start-up windows stay on their timers",
                  exc_info=True)
        return False

    try:
        handle = int(widget.winId())
        ns_window = objc.objc_object(
            c_void_p=ctypes.c_void_p(handle)).window()
    except Exception:                       # noqa: BLE001
        log.debug("could not reach the NSWindow", exc_info=True)
        return False
    if ns_window is None:
        return False

    centre = AppKit.NSNotificationCenter.defaultCenter()
    tokens: list = []

    def _release_then_call() -> None:
        # Whichever of the four routes fires, the observers go: the gate is
        # one-shot, so anything still delivering to it is dead weight.
        for token in tokens:
            centre.removeObserver_(token)
        tokens.clear()
        for i, held in enumerate(_live):
            if held is entry:          # by identity: two gates compare equal
                del _live[i]
                break
        callback()

    gate = FullScreenTransition(_release_then_call, **kwargs)
    entry = (gate, tokens)
    _live.append(entry)

    def _observe(name: str, fn: Callable[[], None]) -> None:
        def block(_note) -> None:
            fn()
        tokens.append(centre.addObserverForName_object_queue_usingBlock_(
            name, ns_window, None, block))

    _observe(_WILL_ENTER, gate.note_will_enter)
    _observe(_DID_ENTER, gate.note_settled)
    _observe(_DID_FAIL,
             lambda: gate.note_settled("macOS refused the transition"))
    gate.arm()
    return True
