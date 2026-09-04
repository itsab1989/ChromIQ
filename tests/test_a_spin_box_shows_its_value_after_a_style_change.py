"""B8-45 — a spin box must show its value after the style under it changes.

WHAT WAS REPORTED, AND WHAT IS ACTUALLY TRUE.

Agent P, measuring B8-44 in a real window: *"Size (pt)" gives its editor 7 px
for a 27 px value and shows a sliver that reads as ")"; "Line thickness" gives
1 px for 19.* Reproduced here on screen — and it is worse than filed:
**seventeen** visible spin boxes clip, not two, including all four page
margins.

It does not happen in the shipped app. Driven on screen in the app's own
launch order — `main.py` calls `apply_appearance(app, None, …)` **before** it
builds `MainWindow`, so the stylesheet is in place before any widget exists —
nothing clips, in any of the three appearances, and nothing clips after three
runtime appearance switches either. The reported numbers came from a driver
that built the window first and switched the appearance afterwards.

WHAT IS REAL IS THE FRAGILITY UNDERNEATH IT, and this file pins that.

`LayoutOptionsPanel._fit_spin_widths` sizes each box to
``widest + chrome + 4`` and asks the STYLE what the chrome is — the up/down
buttons, the frame and the text padding. That answer depends on a stylesheet
being applied: measured, the same query returns **20 px with no application
stylesheet and 51 px with one** (all three appearances write
``padding: 0 24px 0 6px`` plus a 1 px border, so they agree exactly). The fit
ran **once**, from the panel's first `showEvent`, and pinned a `maximumWidth`
from whatever the answer happened to be. Fit at 20, paint at 51, and every box
is 31 px too narrow — for ever, because nothing ever asked again.

So the panel now re-fits on `QEvent.StyleChange`, and these tests recreate the
exact condition that produced the sliver: a panel built and shown, and the
stylesheet applied to it afterwards.

WHY THIS IS NOT A TEST THAT CAN ONLY BE RUN ON A SCREEN. The trap in this
panel is that QSS geometry lands at POLISH, so an unshown widget answers 20 and
a polished one answers 51 — which is why no offscreen check has ever seen the
sliver. This file does not try to reproduce the platform's polish timing. It
CAUSES the change of chrome itself, offscreen, and asserts the invariant that
must hold across it: after the style under a built panel changes, every spin
box a user can see still has room for the longest string it can hold. The
first test proves the chrome really does move, so the other two cannot pass
vacuously.

No ``qapp.setStyleSheet()`` anywhere — an application-wide sheet re-polishes
every widget the suite has alive (CLAUDE.md: two 0.2 s tests once cost 29 s).
The sheet goes on the panel under test, which is what changes its chrome.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _chrome(sb) -> int:
    """Everything in the box that is not the editor: buttons, frame, padding."""
    from PyQt6.QtWidgets import QStyle, QStyleOptionSpinBox
    opt = QStyleOptionSpinBox()
    sb.initStyleOption(opt)
    field = sb.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox, opt,
        QStyle.SubControl.SC_SpinBoxEditField, sb).width()
    return sb.width() - field


def _longest(sb) -> int:
    """Pixels the widest string this box can ever display needs."""
    fm = sb.lineEdit().fontMetrics()
    text = sb.prefix() + sb.textFromValue(sb.maximum()) + sb.suffix()
    return max(fm.horizontalAdvance(text),
               fm.horizontalAdvance(sb.specialValueText() or ""))


def _shown_panel(qapp):
    """Built and shown with NO stylesheet — the state the fit runs in."""
    import ui.dialogs.layout_options_panel as lop
    panel = lop.LayoutOptionsPanel(with_selectors=True, with_calibration=True)
    panel._basic_frame.set_collapsed(False)
    panel._expert_frame.set_collapsed(False)
    panel.resize(514, 3000)
    panel.show()
    qapp.processEvents()
    return panel


def _apply_the_app_sheet(panel, qapp):
    from ui.styles import APP_STYLESHEET
    panel.setStyleSheet(APP_STYLESHEET)
    qapp.processEvents()      # let the repolish drain
    qapp.processEvents()      # …and the zero-timer refit run
    panel.updateGeometry()
    qapp.processEvents()


def _clipped(panel):
    """Every spin box a user can see whose editor is too small for its value."""
    from PyQt6.QtWidgets import QAbstractSpinBox
    out = []
    for sb in panel.findChildren(QAbstractSpinBox):
        le = sb.lineEdit()
        if le is None or not sb.isVisibleTo(panel):
            continue
        if _longest(sb) > le.width():
            out.append(f"{sb.objectName() or type(sb).__name__} "
                       f"{le.text()!r}: editor {le.width()} px, "
                       f"value needs {_longest(sb)} px")
    return out


def test_the_chrome_really_does_change_when_the_stylesheet_lands(qapp):
    """GUARD THE GUARD. If the chrome did not move, the two tests below would
    pass without exercising anything, and this file would be decoration.

    Measured on the running app: 20 px bare, 51 px with the sheet. Offscreen
    the numbers are the same, because they come from the QSS and not from the
    platform.
    """
    panel = _shown_panel(qapp)
    try:
        before = _chrome(panel.underline_thickness)
        _apply_the_app_sheet(panel, qapp)
        after = _chrome(panel.underline_thickness)
        assert after - before >= 20, (
            f"the chrome barely moved ({before} -> {after} px), so nothing "
            f"below is being tested — the stylesheet is not reaching the "
            f"spin boxes")
    finally:
        panel.hide(); panel.deleteLater(); qapp.processEvents()


def test_every_spin_box_still_shows_its_value_after_the_stylesheet_lands(qapp):
    """The invariant, across the change that produced the sliver."""
    panel = _shown_panel(qapp)
    try:
        _apply_the_app_sheet(panel, qapp)
        bad = _clipped(panel)
        assert not bad, (
            f"{len(bad)} spin boxes clip their own value after the style under "
            f"them changed — the widths were fitted against the old chrome and "
            f"never asked again:\n  " + "\n  ".join(bad))
    finally:
        panel.hide(); panel.deleteLater(); qapp.processEvents()


def test_the_two_boxes_that_were_reported_are_named_and_checked(qapp):
    """The specific report, by name, so a future regression says who.

    "Size (pt)" at 7 px and "Line thickness" at 1 px are the two Agent P
    measured; they are the tightest boxes in the panel and the first to go.
    """
    panel = _shown_panel(qapp)
    try:
        _apply_the_app_sheet(panel, qapp)
        for attr, label in ((("indicator_size"), "Size (pt), Strip && row labels"),
                            ("underline_thickness", "Line thickness"),
                            ("underline_gap", "Line distance"),
                            ("chart_text_size", "Size (pt), Sheet text"),
                            ("clip_text_size", "Size (pt), Clip-border content")):
            sb = getattr(panel, attr)
            have = sb.lineEdit().width()
            need = _longest(sb)
            assert have >= need, (
                f"{label}: editor {have} px for a value needing {need} px — "
                f"this is the sliver that reads as ')'")
    finally:
        panel.hide(); panel.deleteLater(); qapp.processEvents()
