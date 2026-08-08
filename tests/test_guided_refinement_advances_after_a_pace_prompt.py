"""Guided refinement must move to the next strip even after the pace prompt.

Basti, 2026-08-08: in guided refinement with a refinement-strips file he read
strip A, answered the "read a little fast" prompt with *use it anyway* and
*don't show this again*, and it never moved to the next strip he had to read.
His log:

    13:05:35  chromiq-chartread … -S -r -T 0.7          (refinement active)
    13:05:59  strip_read A
    13:05:59  Ready to read strip pass A (!! ALL ROWS READ !!)
    13:05:59  {"strip":"A","read":true,"all_done":true}   ← still on A

**It is an ordering fault, provable from the source.** `strip_read` handling is:

    self.strip_measured.emit(ev)            # the tab raises the modal pace prompt
    ...
    if self._guided_state == "waiting":
        self._advance_guided_strip(on_line) # only AFTER the modal closes

`strip_measured` is a direct signal, so the prompt's nested event loop delivers
`strip_ready A` first. `_guided_step` sees state `waiting` with `letter ==
target`, its `waiting` branch only acted when `letter != target`, and the event
was consumed doing nothing. `_advance_guided_strip` then set `navigating` and —
by its own comment — waited for "the next stripe_changed event", which had
already been and gone. chartread sat at its menu; nothing ever pressed a key.

With `-r` the `.ti3` is already complete, so chartread has no "next unread" to
offer by itself: ChromIQ has to drive it. That is why nothing recovered.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager        # noqa: E402


class _M:
    """The guided state machine alone — no process, no Qt."""
    _guided_step = MeasureManager._guided_step
    _advance_guided_strip = MeasureManager._advance_guided_strip

    def __init__(self, strips, idx=0, state="waiting"):
        self._guided_strips = list(strips)
        self._guided_idx = idx
        self._guided_state = state
        self._guided_menu_pending = False
        self._engine_active = True
        self.moves: list = []
        self.lines: list = []

    # what _navigate_toward would do in engine mode
    def _navigate_toward(self, current, target):
        self.moves.append((current, target))

    def goto_strip(self, target):            # not reached; engine path is stubbed
        self.moves.append((None, target))

    class _Sig:
        def __init__(self): self.count = 0
        def emit(self): self.count += 1
    all_stripes_done = property(lambda self: self._done)

    def line(self, s):
        self.lines.append(s)


def _mk(strips, idx=0):
    m = _M(strips, idx)
    m._done = _M._Sig()
    return m


def test_it_advances_when_the_menu_arrived_first(qapp):
    """Basti's case: the pace prompt let strip_ready in before the advance."""
    m = _mk(["A", "C", "E"])
    # inside the modal: chartread re-announces the strip we are waiting on
    m._guided_step("A", m.line)
    assert m._guided_menu_pending is True, "the early announcement was not noticed"
    assert m.moves == [], "nothing should move while still waiting"

    # the modal closes and the advance finally runs
    m._advance_guided_strip(m.line)
    assert m._guided_state == "navigating"
    assert m.moves == [("A", "C")], (
        "guided refinement did not move on to the next strip — it is waiting "
        "for a stripe_changed event that has already been and gone"
    )
    assert m._guided_menu_pending is False, "the flag must not stay set"


def test_the_ordinary_order_still_works_and_does_not_move_twice(qapp):
    """No pace prompt: the advance arms, and the later announcement navigates."""
    m = _mk(["A", "C", "E"])
    m._advance_guided_strip(m.line)          # advance runs first, as usual
    assert m._guided_state == "navigating"
    assert m.moves == [], "nothing to drive yet — the menu has not been announced"

    m._guided_step("A", m.line)              # chartread re-announces A
    assert m.moves == [("A", "C")], "the normal path stopped navigating"


def test_the_last_strip_finishes_instead_of_navigating(qapp):
    m = _mk(["A"], idx=0)
    m._guided_step("A", m.line)
    m._advance_guided_strip(m.line)
    assert m._guided_state == "idle_done"
    assert m.moves == [], "there is no next strip to move to"
    assert m._done.count == 1, "the completion signal was not emitted"


def test_a_different_strip_still_takes_the_original_path(qapp):
    """chartread moving on by itself must behave exactly as before.

    The pre-existing rule: while waiting on a target, an announcement for a
    DIFFERENT strip means chartread accepted the previous one and moved, so the
    index advances and navigation continues. Only the `letter == target` case is
    new, so this pins the untouched half.
    """
    m = _mk(["A", "C"])
    m._guided_step("C", m.line)              # chartread moved on by itself
    assert m._guided_state == "navigating"
    assert m.moves == [("C", "C")], "the original advance-on-a-new-strip path changed"
    assert m._guided_menu_pending is False, "the new flag must not be set here"


def test_the_measurement_log_reaches_the_file(caplog):
    """Everything the panel narrates must also be written to the app log.

    Basti, 2026-08-08, with a measurement running and the panel hidden: *"can
    you make it write your info to the real log for next time"*. It also removes
    a real diagnostic trap — the file held the raw `[argyll]` events but not one
    line of what ChromIQ itself decided, so the absence of "[Guided Refinement]"
    lines looked like evidence that navigation never started, when in fact no
    panel line reached the file at all.
    """
    import inspect
    import logging

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._on_log_line)
    assert "log.info(" in src, (
        "the measurement's own narration is not written to the application log, "
        "so a hidden log panel means the file cannot explain what happened"
    )
    # …and it must not be able to break a read.
    assert "except Exception" in src, "a logging failure could abort a measurement"
