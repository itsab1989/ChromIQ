"""The start-up windows must wait for macOS's fullscreen transition.

`showFullScreen()` on macOS is NATIVE fullscreen: the window is moved to a Space
of its own, animated, and the move is only over ~1.7 s in (measured on a first
launch, with `NSWindowDidEnterFullScreenNotification` as the yardstick). Two
faults follow, both measured on screen, both older than this branch — they
reproduce identically at `master` (v4.1.2-beta.7) and at `ddc117a0`:

* **The welcome dialog is stranded on the old Space.** Shown on its 100 ms
  timer, it lands on whichever Space is active at that moment, which is still
  the one the app came from. The user ends up looking at a fullscreen window on
  one Space and a dialog on another.
* **The ArgyllCMS modal aborts the transition.** macOS answers with
  `NSWindowDidFailToEnterFullScreenNotification`, the window drops back to its
  plain geometry — while `isFullScreen()` still returns True, which
  `MainWindow.closeEvent` then files, so the next launch repeats it.

No fixed delay can be right, because the transition's length is not ours to
predict. `core.macos_fullscreen` waits for AppKit to say it is over (Qt cannot:
`QWindow.windowStateChanged` and `QEvent.WindowStateChange` both arrive at the
START of the transition — 39 ms, against 1747 ms for the real end).

The decision table of that wait is tested here for real. The Space placement
itself is not assertable in a test — it needs a screen, a window server and a
second Space — so it is not faked here; it was measured, and the measurements
are in the report that came with this change.
"""
from __future__ import annotations

import inspect
import re
import sys

import pytest

from core.macos_fullscreen import (FullScreenTransition,
                                   run_after_fullscreen_transition)


class Clock:
    """A schedule that runs nothing until told, so every deadline is explicit."""

    def __init__(self) -> None:
        self.queued: list[tuple[int, object]] = []

    def schedule(self, ms, fn) -> None:
        self.queued.append((ms, fn))

    def run(self, ms) -> None:
        """Fire everything queued for exactly ``ms`` (in queue order)."""
        for queued_ms, fn in list(self.queued):
            if queued_ms == ms:
                self.queued.remove((queued_ms, fn))
                fn()


@pytest.fixture
def gate():
    clock = Clock()
    fired: list[str] = []
    g = FullScreenTransition(lambda: fired.append("windows"),
                             start_ms=400, settle_ms=120, timeout_ms=5000,
                             schedule=clock.schedule)
    g.arm()
    return g, clock, fired


def test_without_a_transition_the_windows_open_on_the_start_deadline(gate):
    """The ordinary launch: no fullscreen to restore, nothing to wait for."""
    g, clock, fired = gate
    clock.run(400)
    assert fired == [], "fired without even the settling tick"
    clock.run(120)
    assert fired == ["windows"], "the start-up windows never opened"
    assert g.reason == "no transition began"


def test_a_transition_in_flight_holds_the_windows_back(gate):
    """The fault itself: at 400 ms the window is mid-flight to its own Space,
    and anything shown now lands on the Space it is leaving."""
    g, clock, fired = gate
    g.note_will_enter()
    clock.run(400)
    clock.run(120)
    assert fired == [], "the windows opened while the transition was running"

    g.note_settled()
    clock.run(120)
    assert fired == ["windows"], "the windows never opened after the transition"


def test_a_refused_transition_still_opens_the_windows(gate):
    """macOS can refuse (NSWindowDidFailToEnterFullScreen). That ends the wait
    just as much as success does — the windows must not be lost with it."""
    g, clock, fired = gate
    g.note_will_enter()
    g.note_settled("macOS refused the transition")
    clock.run(120)
    assert fired == ["windows"]
    assert g.reason == "macOS refused the transition"


def test_a_transition_that_never_reports_an_end_times_out(gate):
    """A notification that never arrives must never mean 'no start-up dialogs'
    — the first-launch user with no ArgyllCMS would get no dialog at all."""
    g, clock, fired = gate
    g.note_will_enter()
    clock.run(400)
    clock.run(120)
    assert fired == []
    clock.run(5000)
    clock.run(120)
    assert fired == ["windows"]
    assert g.reason == "the transition never reported an end"


def test_the_windows_open_exactly_once(gate):
    """Every route is armed at the same time; a late failure still has the
    overall deadline queued behind it."""
    g, clock, fired = gate
    g.note_will_enter()
    g.note_settled()
    g.note_settled("again")
    clock.run(120)
    clock.run(400)
    clock.run(5000)
    clock.run(120)
    assert fired == ["windows"], f"opened {len(fired)} times"


def test_off_macos_the_caller_keeps_its_own_timer(monkeypatch):
    """Returning False is what makes main.py fall back to singleShot(100) —
    Windows and Linux have no Space to wait for."""
    monkeypatch.setattr(sys, "platform", "win32")
    assert run_after_fullscreen_transition(None, lambda: None) is False


# ----------------------------------------------------------------------
# …and that main() actually wires it that way.
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def main_src():
    import main
    return inspect.getsource(main.main)


def _delay(call: str, src: str) -> int:
    m = re.search(r"QTimer\.singleShot\(\s*(\d+)\s*,[^)]*" + re.escape(call), src)
    assert m, f"no singleShot scheduling {call}"
    return int(m.group(1))


def test_the_window_state_is_still_applied_before_anything_else(main_src):
    for state in ("win.showFullScreen", "win.showMaximized"):
        assert _delay(state, main_src) == 0, (
            f"{state} must stay on the immediate tick; delaying it is a "
            "visible flash of the un-restored window")


def test_the_modal_comes_after_the_welcome_dialog(main_src):
    assert _delay("win.show_startup_warnings", main_src) > 0, (
        "the not-found modal is queued at 0, in the same batch as "
        "showFullScreen — that aborts the fullscreen transition")
    assert (main_src.index("win.open_welcome_dialog()")
            < main_src.index("win.show_startup_warnings")), (
        "the modal must be queued after the welcome dialog is up, or the "
        "welcome dialog's timer fires inside the modal's event loop and takes "
        "the keyboard from it")


def test_a_fullscreen_restore_gates_both_windows_on_the_transition(main_src):
    assert "run_after_fullscreen_transition(win, _open_startup_windows)" in main_src, (
        "the start-up windows are back on a fixed delay — on macOS that puts "
        "them on the Space the main window is leaving")
    assert re.search(r'if settings\.get\("window_fullscreen", False\):\s*\n'
                     r"\s*from core\.macos_fullscreen import", main_src), (
        "the gate must be reached only when there is a fullscreen state to "
        "restore; every other launch has no transition to wait for")
    assert re.search(r"if not gated:\s*\n(\s*#[^\n]*\n)*"
                     r"\s*QTimer\.singleShot\(\s*100\s*,\s*_open_startup_windows\)",
                     main_src), (
        "nothing opens the start-up windows when the gate declines the job "
        "(every platform but macOS, and macOS without pyobjc)")
