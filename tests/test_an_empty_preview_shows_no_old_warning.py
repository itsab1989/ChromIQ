"""An empty preview carries no warning header from the chart before it.

Found by the independent review of fix/after-4334 (2026-11-14), and already in
4.3.34: an i1iO sheet too large for the arm is refused, the preview goes empty
(`MarginInspectorPanel.show_placeholder`), and the "Measured from Preview"
frame still said "1 warning" from the PREVIOUS chart, while the fold badge
above the two frames, which reads `verdict()`, showed nothing. The two
disagreed because `show_placeholder` reset the verdict but never the count
behind the red header, nor re-applied the fold.
"""
from __future__ import annotations

import os

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.margin_inspector import MarginReport   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _panel_with_one_warning():
    from ui.margin_inspector_panel import MarginInspectorPanel
    p = MarginInspectorPanel()
    p.update_report(
        MarginReport(left_mm=10, right_mm=10, top_mm=4, bottom_mm=10,
                     strip_width_mm=8.0, strip_length_mm=200.0,
                     page_w_mm=210.0, page_h_mm=297.0),
        [], thresholds_defined=True, notify=True,
        overlap_warnings=["⚠ The strip letters are printed over the patches."])
    assert not p._warn_toggle.isHidden()
    assert "1 warning" in p._warn_toggle.text()
    assert p.verdict() == ("warnings", 1)
    return p


@pytest.mark.parametrize("expanded", [True, False])
def test_the_placeholder_hides_the_previous_charts_warning(qapp, expanded):
    p = _panel_with_one_warning()
    p.set_warnings_expanded(expanded)
    seen = []
    p.verdict_changed.connect(lambda: seen.append(p.verdict()))
    p.show_placeholder()
    assert p._warn_toggle.isHidden(), (
        "the red header of the previous chart is still shown over an empty "
        "preview: " + p._warn_toggle.text())
    assert p._status.isHidden()
    assert p._warning_count == 0
    # The header and the fold badge now say the same thing: nothing.
    assert p.verdict() == ("none", 0)
    assert seen == [("none", 0)]
    p.deleteLater()


def test_the_next_chart_after_a_placeholder_counts_from_zero(qapp):
    p = _panel_with_one_warning()
    p.show_placeholder()
    p.update_report(
        MarginReport(left_mm=10, right_mm=10, top_mm=10, bottom_mm=10,
                     strip_width_mm=8.0, strip_length_mm=200.0,
                     page_w_mm=210.0, page_h_mm=297.0),
        [], thresholds_defined=True, notify=True)
    assert p._warn_toggle.isHidden()
    assert p.verdict() == ("ok", 0)
    p.deleteLater()
