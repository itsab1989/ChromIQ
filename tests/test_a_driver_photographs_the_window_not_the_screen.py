"""A driver may not roll its own window capture, and may not give up on a lock.

Basti, 2026-09-13: *"so this will work in the future in other sessions
automatically as well?"*, after a round wrote "the screen is locked, so there
are no photographs" and stopped.

Fixing `scripts/onscreen_capture.py` makes it work for every driver that CALLS
it. It does nothing about the next driver, written from scratch, that shells
out to `screencapture` on its own and rediscovers the same two dead ends. This
file is the part that is actually automatic.

**The two dead ends, measured on macOS 15.6 with Screen Recording granted:**

* `screencapture -R <rect>` copies a RECTANGLE OF THE SCREEN. A window this
  process opened without stealing focus is not composited on the Space being
  captured, so the rectangle comes back as wallpaper. `win.raise_()` cannot fix
  it and neither can `NSRunningApplication.activateWithOptions_`, which returns
  True while `isActive` stays False.
* `screencapture -l <window id>` exits 1 with "could not create image from
  window". CLAUDE.md blamed that string on the missing permission grant; it
  survives the grant.

Only `CGWindowListCreateImage` works, and it lives in one place.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
HELPER = SCRIPTS / "onscreen_capture.py"

#: `screencapture` with no window in it is fine: a WHOLE SCREEN is a legitimate
#: thing to photograph (a driver showing a modal over the desktop, say), and it
#: is not what this guard is about. What is banned is aiming it at a window.
_WINDOW_FLAGS = re.compile(r"screencapture[^\n]*\s-(?:l|R)\b")


def _driver_files() -> list[Path]:
    return [p for p in sorted(SCRIPTS.rglob("*.py"))
            if p.name != HELPER.name and "__pycache__" not in p.parts]


def _window_captures(src: str) -> list[tuple[int, str]]:
    """Every CALL that runs `screencapture` with `-l` or `-R`.

    **SCANNING LINES DOES NOT WORK, IN BOTH DIRECTIONS, AND THIS GUARD GOT IT
    WRONG BOTH WAYS BEFORE IT WORKED.**

    * Its first version read raw lines and failed on a DOCSTRING that explains
      the rule. Prose about `screencapture -R` is the fix being written down,
      not the fault being committed.
    * Its second version skipped every line covered by a string literal, and
      then missed a real call: ``subprocess.run(['screencapture', '-R', ...])``
      IS string literals, which is what a call looks like. A deliberate mutant
      of exactly that shape went straight through.

    So this asks the syntax tree for calls, and only then reads their source.
    A plain full-screen `screencapture -x out.png` is untouched: photographing
    a whole screen is legitimate, and it is not what this guard is about.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        seg = ast.get_source_segment(src, node) or ""
        if "screencapture" not in seg:
            continue
        if re.search(r"-(?:l|R)\b", seg):
            out.append((node.lineno, " ".join(seg.split())[:120]))
    return out


def test_only_the_shared_helper_aims_screencapture_at_a_window():
    """`-l` and `-R` belong to `onscreen_capture.py` and nowhere else."""
    offenders = []
    for p in _driver_files():
        src = p.read_text(encoding="utf-8")
        for n, seg in _window_captures(src):
            offenders.append(f"{p.relative_to(ROOT)}:{n}: {seg}")
    assert not offenders, (
        "these aim `screencapture` at a window themselves. `-R` returns the "
        "desktop when the window is not composited on the captured Space, and "
        "`-l` does not work on macOS 15 at all. Call "
        "`scripts/onscreen_capture.py::capture_window`, which uses "
        "`CGWindowListCreateImage` and falls back to the rectangle with a "
        "hide/show proof:\n  " + "\n  ".join(offenders))


def test_the_guard_above_can_actually_see_a_call():
    """The negative half. A guard that cannot fire is not a guard, and this one
    silently could not: see `_window_captures` for the two ways it failed."""
    bad = "import subprocess\nsubprocess.run(['screencapture', '-R', '1,1,9,9', 'x.png'])\n"
    assert _window_captures(bad), "a real call is not detected"
    prose = '"""A note about `screencapture -R` and why it is wrong."""\n'
    assert not _window_captures(prose), "a docstring is read as a call"
    whole = "import subprocess\nsubprocess.run(['screencapture', '-x', 'x.png'])\n"
    assert not _window_captures(whole), (
        "a full-screen capture is flagged; only window captures are banned")


def test_the_helper_tries_the_windows_own_buffer_before_the_screen():
    """The order is load-bearing: buffer first, rectangle only as a fallback."""
    src = HELPER.read_text(encoding="utf-8")
    assert "CGWindowListCreateImage" in src, (
        "the helper no longer photographs the window's own buffer, which is "
        "the only route that works when the window is not frontmost")
    body = src[src.index("def capture_window("):]
    buf = body.index("_grab_window_id")
    rect = body.index("_grab_region")
    assert buf < rect, (
        "`capture_window` reaches for the screen rectangle before the window's "
        "own buffer; on macOS 15 that returns wallpaper for any window the "
        "driver did not manage to bring to the front")


def test_a_lock_is_woken_before_it_is_reported():
    """*"my screen never needs a password to be unlocked"* (Basti, 2026-09-13).

    A lock with no password on it is cleared by asserting user activity, so
    reporting one as a blocker before trying is giving up early. That cost a
    whole morning's proof once.
    """
    src = HELPER.read_text(encoding="utf-8")
    assert "def wake_the_screen(" in src
    assert "caffeinate" in src, (
        "`wake_the_screen` no longer asserts user activity, so it cannot clear "
        "a passwordless lock")
    body = src[src.index("def capture_window("):]
    stop = body.index("session_is_locked()")
    woke = body.index("wake_the_screen()")
    ret = body.index("return False")
    assert stop < woke < ret, (
        "`capture_window` reports the lock before trying to wake it; the wake "
        "has to come first, and the refusal only after it fails")


@pytest.mark.parametrize("name", ["wake_the_screen", "window_id_for",
                                  "capture_window", "session_is_locked"])
def test_the_helper_still_offers_what_the_drivers_import(name):
    """Twenty-four drivers import from this module. Renaming is a breaking
    change to all of them at once, so the names are pinned."""
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    got = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert name in got, f"{name} is gone from scripts/onscreen_capture.py"
