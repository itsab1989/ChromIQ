"""Every tab ends on the same line, with the log panel shown or hidden.

Basti, 2026-08-07, over several rounds — first *"in check refine tab in the
right panel the buttons run gamut analysis, reset view and save as defaults
should have the same distance to the main window on their bottom like those
buttons in the left panel"*, then, once that was levelled, *"in this case when
the log is on the distance of the log to the main window should also be the
same"*, and finally *"in check refine log is 1px (?) higher than in the other
tabs"* — which it was, by 2 px, because the first fix had settled on 15 while
every other log sat on 13.

**The agreed line is 13 px above the window edge.** Measured on screen with the
real styling, the tabs were: Create Chart 15, Measure 11, Print Chart 13,
Calibration & Profiling 15, Check & Refine 13 — with the log **hidden**, which
is how Basti runs it, so the jump showed every time he changed tab.

Why the gap has to be split in two, and why one tab splits it the other way, is
explained on :func:`ui.widgets.add_log_row`. The short version: the space above
a log and the space below the buttons that replace it are the same pixels doing
two different jobs, and only one of the two may survive the log being hidden.

**These tests build the real tabs** rather than reading their source. An earlier
version of this file grepped for the constants, which meant it could pass while
the wrapper was attached to nothing. The one thing that still cannot be checked
here is the resulting pixel count: that needs the whole window with its
stylesheet, and MainWindow segfaults under the offscreen platform the gate runs
on. So the assertions cover the structure that produces those pixels, and each
was verified by re-introducing the bug it guards.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QPlainTextEdit                      # noqa: E402

from ui.widgets import LOG_GAP_KEPT, LOG_GAP_TOTAL             # noqa: E402


def _tabs():
    """One instance of every tab that owns a log panel."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_check_refine import TabCheckRefine
    from ui.tabs.tab_measure import TabMeasure
    from ui.tabs.tab_profile import TabProfile

    st = AppSettings()
    runner = ArgyllRunner(st)
    fm = FileManager(st)
    return [
        ("Create Chart", TabChart(runner, fm, st, None)),
        ("Build Profile", TabProfile(runner, st, None)),
        ("Measure", TabMeasure(runner, st, None)),
        ("Check & Refine", TabCheckRefine(runner, st, None)),
    ]


def _logs(tab):
    return [w for w in tab.findChildren(QPlainTextEdit) if w.objectName() == "log"]


def test_the_gap_split_still_adds_up():
    """The two halves must reconstruct the original 5 px, or every gap moves."""
    assert LOG_GAP_TOTAL == 5
    assert LOG_GAP_KEPT == 3
    assert 0 < LOG_GAP_KEPT < LOG_GAP_TOTAL, (
        "the kept half must be a real part of the gap: at 0 the buttons drop to "
        "where the log's bottom was, and at the full amount nothing is hidden "
        "with the log and they hang below it"
    )


def test_every_log_lives_in_a_hideable_container(qapp):
    """Otherwise hiding the log leaves its margins behind as a blank strip."""
    seen = 0
    for name, tab in _tabs():
        for log in _logs(tab):
            parent = log.parentWidget()
            assert parent is not None and parent.objectName() == "log_container", (
                f"{name}: a log panel is not wrapped in a log_container "
                f"(parent is {parent.objectName() or parent.__class__.__name__!r}). "
                "MainWindow._apply_log_visibility hides the log and a parent "
                "called log_container; anything else leaves the margins on screen."
            )
            seen += 1
    assert seen >= 6, f"expected at least six log panels across the tabs, found {seen}"


def test_the_wrapper_never_takes_a_stretch(qapp):
    """With a stretch the wrapper grows and the log floats clear of the bottom.

    ``fit_log_height`` pins the log's height (``min == max``), so a stretch
    cannot be absorbed by the log itself — it inflates the wrapper instead. The
    symptom looks exactly like the bug this whole change was fixing, which is
    what makes it worth a test of its own.
    """
    for name, tab in _tabs():
        for log in _logs(tab):
            wrapper = log.parentWidget()
            outer = wrapper.parentWidget()
            layout = outer.layout() if outer is not None else None
            if layout is None:
                continue
            idx = layout.indexOf(wrapper)
            if idx < 0:
                continue
            assert layout.stretch(idx) == 0, (
                f"{name}: the log_container was added with a stretch factor. "
                "The log's height is fixed, so the slack inflates the wrapper "
                "and leaves the log short of the bottom edge."
            )


def test_the_hidden_half_of_the_gap_sits_inside_the_wrapper(qapp):
    """Above the log on most tabs; below it on Measure, which is inverted."""
    hidden = LOG_GAP_TOTAL - LOG_GAP_KEPT
    for name, tab in _tabs():
        for log in _logs(tab):
            m = log.parentWidget().layout().contentsMargins()
            if name == "Measure":
                # Measure's buttons have their own container, whose bottom
                # margin is all they get once the log is hidden — so here the
                # 2 px must move OUT of the wrapper, not into it.
                assert m.top() == 0, f"{name}: unexpected top margin {m.top()}"
                assert m.bottom() == 12 - hidden, (
                    f"{name}: wrapper bottom margin is {m.bottom()}, expected "
                    f"{12 - hidden} — the {hidden} px belongs outside the "
                    "wrapper so it survives the log being hidden"
                )
            else:
                assert m.top() == hidden, (
                    f"{name}: wrapper top margin is {m.top()}, expected {hidden}"
                )
                assert m.bottom() == 0, (
                    f"{name}: the wrapper must add nothing below the log — that "
                    f"is what puts its bottom edge on the same line as the "
                    f"buttons of a tab whose log is hidden"
                )


def test_measure_keeps_its_two_pixels_outside_the_wrapper(qapp):
    """The spacer that survives the log being hidden must actually be there."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    st = AppSettings()
    tab = TabMeasure(ArgyllRunner(st), st, None)
    log = _logs(tab)[0]
    wrapper = log.parentWidget()
    layout = wrapper.parentWidget().layout()
    idx = layout.indexOf(wrapper)
    assert idx >= 0
    after = layout.itemAt(idx + 1)
    assert after is not None and after.widget() is None and after.layout() is None, (
        "Measure needs a plain spacer immediately after its log_container: it "
        "is the 2 px that stays behind when the log is hidden and brings the "
        "buttons down to 13 px, the same line as every other tab"
    )
    assert after.sizeHint().height() == LOG_GAP_TOTAL - LOG_GAP_KEPT, (
        f"that spacer is {after.sizeHint().height()} px, expected "
        f"{LOG_GAP_TOTAL - LOG_GAP_KEPT}"
    )


def test_gamut_button_row_clears_the_window_edge_by_the_same_amount(qapp):
    """15, not 12 — the value that lands these buttons on 13 px like the rest.

    Read from the live layout rather than the source, because the number only
    means anything in combination with the buttons' real rendered height: they
    ask for ``setFixedHeight(36)`` and paint at 42, and the overflow eats into
    this margin.
    """
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.gamut_panel import GamutPanel

    st = AppSettings()
    panel = GamutPanel(ArgyllRunner(st), st, None)
    btn = panel._run_btn
    row = None
    parent_layout = btn.parentWidget().layout()
    # The button row is the sub-layout that holds Run Gamut Analysis.
    for i in range(parent_layout.count()):
        item = parent_layout.itemAt(i)
        sub = item.layout()
        if sub is not None and sub.indexOf(btn) >= 0:
            row = sub
            break
    assert row is not None, "could not find the gamut button row in the layout"
    assert row.contentsMargins().bottom() == 15, (
        f"bottom margin is {row.contentsMargins().bottom()}, expected 15. At 12 "
        "these buttons sit 10 px above the window instead of the 13 every log "
        "in the app sits on."
    )
