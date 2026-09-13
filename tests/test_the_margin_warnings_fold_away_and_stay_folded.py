"""The red warnings in "Measured from Preview" fold away, and the app remembers.

Basti, 2026-09-13: *"the red warning text in the measured from preview section
can become quite a lot in some instances. can this be made collapsible and the
app remembers the state it was in so it does not always take up this much
space?"*

Measured on his own shipped CR30 A4 preset, driven on screen: three notices at
once (the row-indicator margin raise, the chart notes down the right edge, and
the strip letters over the patches) run to fourteen wrapped lines and take more
vertical room than the whole margin table above them.

**WHAT THIS IS NOT.** On 2026-09-04 he ruled out a framed collapsible box that
held standing INFO text inside a section: *"regarding the info text in create
chart tab that is directly inside the sections (even that that you made
collapsible) - i want that gone. You can fit it inside of a tooltip where it
fits but not directly inside a section"*. This is a different thing and the
difference is why it is allowed to exist:

* that was standing help; this is a WARNING about the chart in the preview;
* Knut required these notices to be visible without a hover, which is why they
  were moved back OFF the ⓘ onto the panel's surface, so a tooltip is not
  available to them;
* he asked for them to be shuttable, not moved.

So it is one clickable line, not a frame, and the paragraph behind it is what
folds. `ui/margin_inspector_panel.py` carries the same note, because the next
reader of that file will otherwise "fix" this back.

THE FOUR THINGS THAT HAVE TO HOLD, and the last two are the ones a naive
implementation gets wrong:

1. a warning gets a header saying how many there are;
2. clicking it hides the paragraph and says so, and clicking again brings it
   back;
3. a verdict that is NOT a warning ("Margins: OK") gets no header at all and is
   never hidden by a fold the user set on some earlier chart;
4. the fold SURVIVES the next chart. `update_report` runs on every preview, and
   the obvious implementation calls `self._status.setVisible(True)` in it,
   which springs the paragraph open again on every rebuild and makes the memory
   look broken while the setting is stored perfectly.
"""
from __future__ import annotations

import os

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.margin_inspector import MarginReport, Violation   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _report():
    return MarginReport(left_mm=10, right_mm=10, top_mm=4, bottom_mm=10,
                        strip_width_mm=8.0, strip_length_mm=200.0,
                        page_w_mm=210.0, page_h_mm=297.0)


def _panel():
    from ui.margin_inspector_panel import MarginInspectorPanel
    return MarginInspectorPanel()


_OVERLAPS = [
    "⚠ The strip letters are printed over the patches.",
    "⚠ The chart notes down the right edge are printed over the patches.",
]


def _warn(panel, overlaps=None):
    panel.update_report(_report(), [], thresholds_defined=True, notify=True,
                        overlap_warnings=list(overlaps or _OVERLAPS))


def test_a_warning_gets_a_header_that_counts_it(qapp):
    p = _panel()
    _warn(p)
    assert p._warn_toggle.isVisible() or not p.isVisible(), (
        "the fold header was never shown for a warning")
    assert "2 warnings" in p._warn_toggle.text(), p._warn_toggle.text()
    assert p._status.isVisibleTo(p), "the paragraph starts open"
    p.deleteLater()


def test_one_warning_says_one_warning_and_not_one_warnings(qapp):
    """Count-bearing text gets a real singular, never "(s)" (CLAUDE.md)."""
    p = _panel()
    _warn(p, [_OVERLAPS[0]])
    assert "1 warning" in p._warn_toggle.text()
    assert "1 warnings" not in p._warn_toggle.text()
    p.deleteLater()


def test_clicking_the_header_hides_the_paragraph_and_clicking_again_shows_it(qapp):
    p = _panel()
    _warn(p)
    assert p.warnings_expanded()
    p._on_warn_toggle_clicked(None)
    assert not p.warnings_expanded()
    assert not p._status.isVisibleTo(p), "folding did not hide the paragraph"
    assert "click to show" in p._warn_toggle.text(), (
        "folded, the header is all that is left and must say how to open it")
    p._on_warn_toggle_clicked(None)
    assert p.warnings_expanded()
    assert p._status.isVisibleTo(p)
    p.deleteLater()


def test_the_fold_survives_the_next_chart(qapp):
    """THE ONE THAT BREAKS. `update_report` runs on every preview and sets the
    status label visible; if nothing re-applies the fold afterwards, the
    paragraph springs open on every rebuild while the stored setting is
    perfectly correct, and the feature reads as not working."""
    p = _panel()
    _warn(p)
    p.set_warnings_expanded(False, emit=True)
    assert not p._status.isVisibleTo(p)
    _warn(p)                                  # the user generates another chart
    assert not p.warnings_expanded(), "the fold was forgotten"
    assert not p._status.isVisibleTo(p), (
        "a new preview sprang the folded paragraph open again")
    p.deleteLater()


def test_a_verdict_that_is_not_a_warning_is_never_folded(qapp):
    """"Margins: OK" is one short line. It gets no header, and a fold set on an
    earlier chart must not hide it."""
    p = _panel()
    _warn(p)
    p.set_warnings_expanded(False, emit=True)
    p.update_report(_report(), [], thresholds_defined=True, notify=True)
    assert not p._warn_toggle.isVisibleTo(p), "a header over a green verdict"
    assert p._status.text() == "Margins: OK"
    assert p._status.isVisibleTo(p), "the green verdict was hidden by the fold"
    p.deleteLater()


def test_a_margin_violation_counts_as_a_warning_too(qapp):
    p = _panel()
    p.update_report(_report(),
                    [Violation(edge="Top", measured_mm=4.0, threshold_mm=13.0)],
                    thresholds_defined=True, notify=True)
    assert "1 warning" in p._warn_toggle.text()
    p.deleteLater()


def test_restoring_the_stored_answer_does_not_write_it_back(qapp):
    """The owner calls `set_warnings_expanded` at build time with what was
    stored. That must not emit, or every start would write the setting out
    again and a future default change could never reach anybody."""
    p = _panel()
    seen = []
    p.warnings_expanded_changed.connect(seen.append)
    p.set_warnings_expanded(False)                 # the restore, no emit=
    assert seen == [], "restoring the stored state emitted a change"
    p.set_warnings_expanded(True, emit=True)       # the click
    assert seen == [True]
    p.set_warnings_expanded(True, emit=True)       # no change, no signal
    assert seen == [True]
    p.deleteLater()


def test_the_tab_remembers_the_fold_across_a_rebuild(qapp, tmp_path):
    """End to end through the real tab and the real settings store: fold it,
    throw the tab away, build another, and it comes back folded."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart

    def make():
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
        s.set("custom_output_path", str(tmp_path / "out"))
        return TabChart(ArgyllRunner(s), FileManager(s), s), s

    tab, s = make()
    assert tab._margin_panel.warnings_expanded(), "the default is open"
    tab._margin_panel.set_warnings_expanded(False, emit=True)
    assert s.get("margin_warnings_expanded", True) is False, (
        "the click did not reach the settings store")
    tab.deleteLater()

    tab2, _ = make()
    assert not tab2._margin_panel.warnings_expanded(), (
        "a new tab did not restore the remembered fold")
    tab2.deleteLater()
