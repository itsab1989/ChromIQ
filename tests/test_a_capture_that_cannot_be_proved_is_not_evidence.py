"""A picture of the wallpaper must never be accepted as a picture of a window.

A driver photographed the Measurement Report with ``screencapture -R`` on the
window's frame rectangle, got back 4.4 MB of desktop wallpaper, and its own
check — "the file is bigger than 20 KB" — passed. The login session's screen was
LOCKED: macOS keeps drawing into the window server, so the app and its window
were genuinely there, but every capture came back as the desktop picture with no
window, no menu bar and no dock. ``CGPreflightScreenCaptureAccess`` answered
True throughout, which is why it is not one of the guards.

``scripts/onscreen_capture.capture_window`` refuses in two ways, and both are
tested here: it asks the window server whether the screen is locked before it
takes anything, and it proves the picture it did take contains the window by
photographing the same rectangle with the window hidden and requiring the two to
differ.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import onscreen_capture as oc          # noqa: E402


class _Win:
    """The little a capture needs from a window."""

    def __init__(self) -> None:
        self.hidden = 0
        self.shown = 0

    def raise_(self) -> None:
        pass

    def activateWindow(self) -> None:
        pass

    def hide(self) -> None:
        self.hidden += 1

    def show(self) -> None:
        self.shown += 1

    def frameGeometry(self):
        from PyQt6.QtCore import QRect
        return QRect(10, 20, 300, 200)


def _png(path: Path, colour: int, window_rows: int = 0) -> None:
    """A stand-in capture: a flat desktop, optionally with a "window" drawn
    over the top *window_rows* of it."""
    from PyQt6.QtGui import QImage, qRgb
    im = QImage(120, 90, QImage.Format.Format_RGB32)
    im.fill(qRgb(colour, colour, colour))
    for y in range(window_rows):
        for x in range(120):
            im.setPixel(x, y, qRgb(240, 240, 250))
    im.save(str(path))


def test_a_locked_screen_is_refused_before_anything_is_captured(tmp_path, monkeypatch):
    took: list = []
    monkeypatch.setattr(oc, "session_is_locked", lambda: True)
    monkeypatch.setattr(oc, "_grab_region",
                        lambda rect, p: took.append(p) or True)
    ok, why = oc.capture_window(_Win(), tmp_path / "shot.png")
    assert ok is False
    assert "LOCKED" in why
    assert took == [], "a locked session must not even try to capture"


def test_a_capture_that_matches_the_desktop_behind_it_is_thrown_away(
        tmp_path, monkeypatch, qapp):
    """The wallpaper case: hiding the window changes nothing, so the file goes."""
    monkeypatch.setattr(oc, "session_is_locked", lambda: False)

    def grab(rect, p):
        _png(p, 130)              # the same desktop, window shown or hidden
        return True

    monkeypatch.setattr(oc, "_grab_region", grab)
    shot = tmp_path / "shot.png"
    ok, why = oc.capture_window(_Win(), shot, settle=0.0)
    assert ok is False
    assert "behind the window" in why
    assert not shot.exists(), "a capture that proved nothing must not be left behind"


def test_a_capture_that_shows_the_window_is_kept(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(oc, "session_is_locked", lambda: False)
    state = {"n": 0}

    def grab(rect, p):
        state["n"] += 1
        # First call: the window is up. Second: it is hidden, so the picture
        # is the desktop and the two differ over most of the rectangle.
        _png(p, 130, window_rows=0 if state["n"] > 1 else 70)
        return True

    monkeypatch.setattr(oc, "_grab_region", grab)
    shot = tmp_path / "shot.png"
    ok, why = oc.capture_window(_Win(), shot, settle=0.0)
    assert (ok, why) == (True, "")
    assert shot.exists()
    assert not (tmp_path / "shot__behind.png").exists(), \
        "the comparison capture is working material, not evidence"


def test_the_window_is_put_back_after_the_comparison(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(oc, "session_is_locked", lambda: False)
    monkeypatch.setattr(oc, "_grab_region", lambda rect, p: _png(p, 130) or True)
    win = _Win()
    oc.capture_window(win, tmp_path / "shot.png", settle=0.0)
    assert (win.hidden, win.shown) == (1, 1), \
        "a driver's window must be on screen again when the capture returns"


def test_the_difference_rule_counts_pixels_not_file_size(tmp_path, qapp):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _png(a, 130)
    _png(b, 130)
    assert oc._difference(a, b) == 0.0
    _png(b, 200)
    assert oc._difference(a, b) == 1.0


@pytest.mark.parametrize("locked", [True, False])
def test_the_window_server_is_asked_and_an_answer_comes_back(locked, monkeypatch):
    """`session_is_locked` must return a real bool on this machine, whichever
    state it is in — a helper that raises would be silently ignored by the
    ``except`` in the driver and the refusal would never happen."""
    assert isinstance(oc.session_is_locked(), bool)
