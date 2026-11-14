"""One fold for the two frames under the Create Chart preview (Basti,
2026-11-14): *"make measured from preview and chart layout information section
collapsible? i think one button (or triangle) should collapse both at once"*,
and *"the purpose of this is to save space"*: the triangle and the folded
verdict live in the preview's own "Page N / M" line, no line of their own.

Pinned here, on a real main window:

1. open by default, and open costs no pixel: the preview, the page line and
   the two frames sit exactly where 4.3.34 put them (measured on that tree);
2. one click (or Space / Return on the triangle) hides BOTH frames and the
   preview gets their whole height; the verdict text opens them again;
3. never silent: folded, the page line repeats the verdict, "Margins: OK" or
   the frame's own warning count, live, and a new warning does not open the
   frames;
4. remembered in the app's settings across a rebuilt window, never in a
   target's stored state;
5. the guide and pointer boxes inside keep their state while hidden.
"""
from __future__ import annotations

import sys

import pytest
from PyQt6.QtCore import QPoint, Qt

from workflow.margin_inspector import MarginReport, Violation


@pytest.fixture
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("auto_update_preview", False)
    s.set("preview_details_collapsed", False)
    return s


def _window(qapp, settings, size=(1500, 1000)):
    from ui.main_window import MainWindow
    w = MainWindow(settings)
    w.show()
    if size is None:
        ms = w.minimumSizeHint()
        w.resize(max(ms.width(), w.minimumWidth()),
                 max(ms.height(), w.minimumHeight()))
    else:
        w.resize(*size)
    for _ in range(30):
        qapp.processEvents()
    return w


@pytest.fixture
def one_page_tif(tmp_path):
    """A one-page A4 chart image at 300 dpi, for the page line."""
    from PIL import Image
    p = tmp_path / "page.tif"
    Image.new("RGB", (2480, 3508), (230, 230, 230)).save(p, dpi=(300, 300))
    return p


def _show_chart(qapp, w, tif):
    import time
    w._tab_chart._preview.load_tiff([tif])
    t0 = time.monotonic()
    while time.monotonic() - t0 < 2:
        qapp.processEvents()


def _report():
    return MarginReport(left_mm=10, right_mm=10, top_mm=4, bottom_mm=10,
                        strip_width_mm=8.0, strip_length_mm=200.0,
                        page_w_mm=210.0, page_h_mm=297.0)


def _ok(panel):
    panel.update_report(_report(), [], thresholds_defined=True, notify=True)


def _two_warnings(panel):
    panel.update_report(
        _report(), [Violation(edge="Top", measured_mm=4.0, threshold_mm=8.0)],
        thresholds_defined=True, notify=True,
        overlap_warnings=["⚠ The strip letters are printed over the patches."])


def _geom(w, wd):
    p = wd.mapTo(w, QPoint(0, 0))
    return [p.x(), p.y(), wd.width(), wd.height()]


#: Measured on the v4.3.34 tree (90de4a275) with the same offscreen build
#: and a one-page chart, `2026-11-14_small_fixes/drivers/measure_geom.py`:
#: [x, y, w, h] in the main window.
_V4334 = {
    "default": {"preview": [584, 177, 916, 603], "nav": [584, 765, 916, 15],
                "page_label": [1015, 765, 55, 15],
                "info_scroll": [584, 780, 916, 208]},
    "minimum": {"preview": [584, 209, 316, 326], "nav": [584, 520, 316, 15],
                "page_label": [715, 520, 55, 15],
                "info_scroll": [584, 535, 316, 404]},
}


@pytest.mark.skipif(sys.platform != "darwin",
                    reason="the stored 4.3.34 numbers were measured on macOS")
@pytest.mark.parametrize("which", ["default", "minimum"])
def test_open_it_costs_no_pixel_and_folded_the_preview_gets_it_all(
        qapp, settings, one_page_tif, which):
    w = _window(qapp, settings, None if which == "minimum" else (1500, 1000))
    try:
        _show_chart(qapp, w, one_page_tif)
        tab = w._tab_chart
        prev = tab._preview
        got = {"preview": _geom(w, prev), "nav": _geom(w, prev._nav),
               "page_label": _geom(w, prev._page_label),
               "info_scroll": _geom(w, tab._info_scroll)}
        assert got == _V4334[which], "open, the pane is not 4.3.34's"
        assert tab._preview_fold.triangle.isVisible()
        boxes = tab._info_scroll.height()
        h_open = prev.height()
        nav_y = _geom(w, prev._nav)[1]
        tab._preview_fold.toggle()
        for _ in range(30):
            qapp.processEvents()
        assert tab._info_scroll.isHidden()
        # the boxes' whole height, frames and gaps included: no strip left
        assert prev.height() == h_open + boxes
        assert prev._nav.height() == 15, "the page line grew"
        assert _geom(w, prev._nav)[1] == nav_y + boxes
    finally:
        w.close()


def test_open_by_default_and_one_click_folds_both(qapp, settings, qtbot,
                                                 one_page_tif):
    w = _window(qapp, settings)
    try:
        _show_chart(qapp, w, one_page_tif)
        tab = w._tab_chart
        fold = tab._preview_fold
        tri = fold.triangle
        assert not fold.is_collapsed()
        assert not tab._info_scroll.isHidden()
        assert tri.isVisible() and tri.parentWidget() is tab._preview._nav
        h_open = tab._preview.height()
        qtbot.mouseClick(tri, Qt.MouseButton.LeftButton)
        for _ in range(10):
            qapp.processEvents()
        assert fold.is_collapsed()
        assert tab._info_scroll.isHidden(), "the two frames are still shown"
        assert tab._preview.height() > h_open, "the preview got no room"
        assert settings.get("preview_details_collapsed") is True
        qtbot.keyClick(tri, Qt.Key.Key_Space)
        assert not fold.is_collapsed() and not tab._info_scroll.isHidden()
        qtbot.keyClick(tri, Qt.Key.Key_Return)
        assert fold.is_collapsed()
        assert tri.focusPolicy() == Qt.FocusPolicy.StrongFocus
        _ok(tab._margin_panel)
        qtbot.mouseClick(fold.status, Qt.MouseButton.LeftButton)
        assert not fold.is_collapsed(), "the verdict text did not open them"
    finally:
        w.close()


def test_folded_the_line_repeats_the_verdict_live(qapp, settings):
    from core.i18n import tr
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        fold, panel = tab._preview_fold, tab._margin_panel
        _ok(panel)
        assert fold.status_text() == "", "open, the frames say it themselves"
        fold.toggle()
        assert fold.triangle.isVisible(), "folded, the triangle must stay"
        assert fold.status_text() == tr("Margins: OK")
        _two_warnings(panel)
        assert fold.status_text() == tr("{n} warnings").format(n=2)
        assert fold.is_collapsed(), "a new warning opened the frames"
        assert tab._info_scroll.isHidden()
        panel.update_report(
            _report(), [], thresholds_defined=True, notify=True,
            text_warnings=["⚠ Strip length 300 mm exceeds the ruler"])
        assert fold.status_text() == tr("1 warning")
        # one red line and one note on the ⓘ: the same "1 warning" the open
        # frame's own header says, never a different number
        panel.update_report(
            _report(), [Violation(edge="Top", measured_mm=4.0,
                                  threshold_mm=8.0)],
            thresholds_defined=True, notify=True,
            text_warnings=["⚠ Strip length 300 mm exceeds the ruler"])
        assert panel._warning_count == 1
        assert fold.status_text() == tr("1 warning")
        panel.show_placeholder()
        assert fold.status_text() == ""
        panel.update_report(_report(), [], thresholds_defined=True,
                            notify=False)
        assert fold.status_text() == "", "warnings switched off say nothing"
    finally:
        w.close()


def test_open_with_no_chart_the_triangle_takes_no_room(qapp, settings):
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        assert not tab._preview._pages
        assert not tab._preview_fold.triangle.isVisible()
        assert tab._preview._nav.height() == 0
    finally:
        w.close()


def test_remembered_across_a_rebuilt_window(qapp, settings):
    w = _window(qapp, settings)
    w._tab_chart._preview_fold.toggle()
    w.close()
    w2 = _window(qapp, settings)
    try:
        assert w2._tab_chart._preview_fold.is_collapsed()
        assert w2._tab_chart._info_scroll.isHidden()
        assert w2._tab_chart._preview_fold.triangle.isVisible(), (
            "folded with no chart, the way back is still there")
    finally:
        w2.close()


def test_the_choice_is_not_a_target_setting(qapp, settings):
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        before = repr(tab._collect_ui_state())
        tab._preview_fold.toggle()
        after = repr(tab._collect_ui_state())
        assert before == after, "the fold reached a target's stored state"
        assert "preview_details" not in after
    finally:
        w.close()


def test_the_boxes_inside_keep_their_state_while_hidden(qapp, settings):
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        tab._margin_panel.set_coords_checked(True)
        tab._preview_fold.toggle()
        assert tab._margin_panel.coords_enabled()
        tab._preview_fold.toggle()
        assert tab._margin_panel.coords_enabled()
    finally:
        w.close()


def test_other_previews_keep_their_page_line(qapp):
    """Print Chart and Measure use the same preview without the fold: their
    page line is the original row."""
    from PyQt6.QtWidgets import QHBoxLayout
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    assert isinstance(p._nav.layout(), QHBoxLayout)
