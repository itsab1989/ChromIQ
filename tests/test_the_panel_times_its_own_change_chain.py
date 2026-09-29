"""The layout panel logs how long its own change chain took.

**WHY A LOG LINE IS THE FIX HERE.** Knut reports (#182) that a spin box in the
Create Chart layout panel lags on his machine and is comfortable on another
instrument. Driving his own chart here, field for field off his `meta.json`
(SpectroScan, 648 patches, two pages, hexagonal, 15 x 18 area-first), the whole
chain is about 11 ms a step, five filesystem calls, and 11 ms again from the
step to the preview's next repaint. Nothing reproduces it.

Every attempt to get the figure out of his logs measured **the spacing of his
clicks**: across 198 helper-marker steps in one log the median gap is 0.499 s
and the fastest is 0.003 s, so the four one-second gaps that were reported as a
one-second step were four slow clicks. A log cannot be read for a duration it
never recorded, so the chain now records it.

These tests hold the line to what it PROMISES:

* it is emitted on a change,
* its "listeners" figure really covers the slots the host connected, which is
  the only half nobody can measure from outside,
* and its total is not smaller than its parts.
"""
from __future__ import annotations

import logging
import re
import time

import pytest
from PyQt6.QtWidgets import QApplication

from ui.dialogs.layout_options_panel import LayoutOptionsPanel

_LINE = re.compile(
    r"layout panel change: ([\d.]+) ms total "
    r"\(text ([\d.]+), clip ([\d.]+), note ([\d.]+), listeners ([\d.]+)\)")


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _timings(caplog):
    """Every timing line in the capture, as floats."""
    out = []
    for rec in caplog.records:
        m = _LINE.match(rec.getMessage())
        if m:
            out.append([float(g) for g in m.groups()])
    return out


def test_a_change_logs_how_long_the_chain_took(qapp, caplog):
    p = LayoutOptionsPanel()
    with caplog.at_level(logging.DEBUG,
                         logger="ui.dialogs.layout_options_panel"):
        caplog.clear()
        p._emit()
    rows = _timings(caplog)
    assert rows, ("a change to the layout panel logged no timing line at all; "
                  "Knut's next log has to answer the question by itself")
    total, text, clip, note, listeners = rows[-1]
    assert total >= 0.0 and listeners >= 0.0
    # the parts cannot add up to more than the whole
    assert text + clip + note + listeners <= total + 1.0, (
        f"the parts ({text} + {clip} + {note} + {listeners}) exceed the "
        f"total ({total}), so at least one of them is timing the wrong span")
    p.deleteLater()


def test_the_listeners_figure_covers_what_the_host_connected(qapp, caplog):
    """**THE HALF THAT CANNOT BE MEASURED FROM OUTSIDE.**

    The panel's own three steps are visible to anyone with a profiler. What a
    reader of the log needs is the cost of everything the HOST hung on
    `changed`, because on the Create Chart tab that is a dozen handlers and one
    of them is the suspect. `changed.emit()` is synchronous, so timing the emit
    times all of them, and this proves it with a slot that is deliberately slow.

    MUTATION, proven to land: read the last clock BEFORE `changed.emit()`
    instead of after, and the sleeping slot's 40 ms is reported as 0.
    """
    p = LayoutOptionsPanel()
    p.changed.connect(lambda: time.sleep(0.040))
    with caplog.at_level(logging.DEBUG,
                         logger="ui.dialogs.layout_options_panel"):
        caplog.clear()
        p._emit()
    rows = _timings(caplog)
    assert rows, "no timing line was logged"
    total, _text, _clip, _note, listeners = rows[-1]
    assert listeners >= 35.0, (
        f"a slot that sleeps 40 ms was reported as {listeners} ms, so the "
        f"line does not measure what the host connected")
    assert total >= listeners, (
        f"the total ({total}) is less than the listeners it contains "
        f"({listeners})")
    p.deleteLater()


def test_a_loading_panel_is_silent_unless_the_load_was_slow(qapp, caplog):
    """R22-F3: **68 % of what this line wrote was `0.0 ms total (0.0, 0.0, 0.0,
    0.0)`.**

    While a recipe is being loaded all three steps early-return and nothing is
    emitted, so there is no duration to report; the line was outside that
    guard and wrote one anyway. Measured across 40 lines with `_loading` read
    on entry: 27 True and all-zero, 13 False and real, zero disagreements. Per
    gesture, an instrument change wrote eight of them and a preset apply ten.
    The file handler is DEBUG and rotates at 5 MB, so noise here costs a user
    the log they would otherwise have sent, which is the whole point of the
    line.

    A load that really was slow still says so, because that is worth knowing
    and it is not noise.

    MUTATION, proven to land: drop the `not self._loading` condition.
    """
    p = LayoutOptionsPanel()
    p._loading = True
    try:
        with caplog.at_level(logging.DEBUG,
                             logger="ui.dialogs.layout_options_panel"):
            caplog.clear()
            for _ in range(8):
                p._emit()
        assert not _timings(caplog), (
            f"a panel doing no work while it loads wrote "
            f"{len(_timings(caplog))} timing lines into the user's log")
    finally:
        p._loading = False
        p.deleteLater()


def test_a_slow_load_still_says_so(qapp, caplog):
    """The other side of the same condition: silence must not hide a load that
    genuinely took time, or the line would be blind to exactly the case a user
    would complain about."""
    p = LayoutOptionsPanel()
    p._loading = True
    real = p._refresh_clip_preview

    def slow():
        time.sleep(0.010)
        return real()

    p._refresh_clip_preview = slow
    try:
        with caplog.at_level(logging.DEBUG,
                             logger="ui.dialogs.layout_options_panel"):
            caplog.clear()
            p._emit()
        rows = _timings(caplog)
        assert rows, "a load that took 10 ms was not reported at all"
        assert rows[-1][0] >= 5.0
    finally:
        p._loading = False
        p.deleteLater()
