"""One fold for the two frames under the Create Chart preview (Basti,
2026-11-14): *"make measured from preview and chart layout information section
collapsible? i think one button (or triangle) should collapse both at once"*,
and *"the purpose of this is to save space"*, and his choice of three
photographed placements: a round button floated in the preview's bottom
right corner, a badge beside it while folded ("overall option b"). With it,
the page buttons became one compact centred group in every preview.

Pinned here, on a real main window:

1. open by default, and open costs no pixel: the preview, the page line and
   the two frames sit exactly where 4.3.34 put them (measured on that tree);
2. one click (or Space / Return on the button) hides BOTH frames and the
   preview gets their whole height; the badge opens them again;
3. never silent: folded, the badge repeats the verdict, "Margins: OK" or the
   frame's own warning count, live, and a new warning does not open the
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


def _show_chart(qapp, w, tif, pages=1):
    import time
    w._tab_chart._preview.load_tiff([tif] * pages)
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
#: [x, y, w, h] in the main window, at 1500 x 1000 and at 900 x 951 (the
#: smallest that build allowed). The page text is compared by its centre:
#: since the page buttons became one group (same change) it has a fixed
#: width for the page count, centred where it was.
_V4334 = {
    (1500, 1000): {"preview": [584, 177, 916, 603], "nav": [584, 765, 916, 15],
                   "page_centre_x": 1015 + 55 // 2,
                   "info_scroll": [584, 780, 916, 208]},
    (900, 951): {"preview": [584, 209, 316, 326], "nav": [584, 520, 316, 15],
                 "page_centre_x": 715 + 55 // 2,
                 "info_scroll": [584, 535, 316, 404]},
}


@pytest.mark.skipif(sys.platform != "darwin",
                    reason="the stored 4.3.34 numbers were measured on macOS")
@pytest.mark.parametrize("size", list(_V4334))
def test_open_it_costs_no_pixel_and_folded_the_preview_gets_it_all(
        qapp, settings, one_page_tif, size):
    w = _window(qapp, settings, size)
    try:
        if (w.width(), w.height()) != size:
            pytest.skip(f"this build's window cannot be {size}")
        _show_chart(qapp, w, one_page_tif)
        tab = w._tab_chart
        prev = tab._preview
        lab = prev._page_label
        got = {"preview": _geom(w, prev), "nav": _geom(w, prev._nav),
               "page_centre_x": _geom(w, lab)[0] + lab.width() // 2,
               "info_scroll": _geom(w, tab._info_scroll)}
        want = _V4334[size]
        assert got["preview"] == want["preview"], "open, the preview moved"
        assert got["nav"] == want["nav"], "open, the page line moved"
        assert got["info_scroll"] == want["info_scroll"], "the boxes moved"
        assert abs(got["page_centre_x"] - want["page_centre_x"]) <= 1
        assert tab._preview_fold.button.isVisible()
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


def test_the_page_buttons_do_not_move(qapp, settings, one_page_tif):
    """One compact group in the middle; neither button moves when the page
    number grows ("Page 9 / 10" -> "Page 10 / 10"), on the first or the last
    page (a button greyed), or when the boxes fold."""
    w = _window(qapp, settings)
    try:
        _show_chart(qapp, w, one_page_tif, pages=10)
        prev = w._tab_chart._preview
        assert prev._prev_btn.isVisible() and prev._next_btn.isVisible()

        def where():
            for _ in range(5):
                qapp.processEvents()
            return (_geom(w, prev._prev_btn), _geom(w, prev._page_label),
                    _geom(w, prev._next_btn))
        first = where()
        assert not prev._prev_btn.isEnabled()
        for _ in range(8):
            prev._go_next()
        assert prev._page_label.text().split()[-3] == "9"
        assert where() == first
        prev._go_next()                    # page 10 of 10, Next greyed
        assert not prev._next_btn.isEnabled()
        assert where() == first
        w._tab_chart._preview_fold.toggle()
        moved = where()
        assert [g[0] for g in moved] == [g[0] for g in first], (
            "folding moved the buttons sideways")
        # one group: the page text sits right between the two buttons
        p, lab, n = first
        assert p[0] + p[2] < lab[0] < lab[0] + lab[2] < n[0]
        assert n[0] - (p[0] + p[2]) < 300, "the buttons are not close"
        mid = prev._nav.width() // 2 + _geom(w, prev._nav)[0]
        assert abs((p[0] + n[0] + n[2]) // 2 - mid) <= 2, "not centred"
    finally:
        w.close()


def test_every_preview_has_the_compact_page_group(qapp):
    """Print Chart and Measure use the same preview: the same row."""
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    lay = p._nav.layout()
    order = [lay.itemAt(i).widget() for i in range(lay.count())]
    assert order[1:4] == [p._prev_btn, p._page_label, p._next_btn]
    assert order[0] is None and order[4] is None, "stretch on both sides"


def test_open_by_default_and_one_click_folds_both(qapp, settings, qtbot,
                                                 one_page_tif):
    w = _window(qapp, settings)
    try:
        _show_chart(qapp, w, one_page_tif)
        tab = w._tab_chart
        fold = tab._preview_fold
        tri = fold.button
        assert not fold.is_collapsed()
        assert not tab._info_scroll.isHidden()
        assert tri.isVisible() and tri.parentWidget() is tab._preview
        img = tab._preview._img_label
        corner = img.mapTo(tab._preview, img.rect().bottomRight())
        assert tri.geometry().right() <= corner.x()
        assert tri.geometry().bottom() <= corner.y(), "not in the corner"
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
        assert fold.badge.isVisible() and fold.badge.text() == "✓"
        qtbot.mouseClick(fold.badge, Qt.MouseButton.LeftButton)
        assert not fold.is_collapsed(), "the badge did not open them"
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
        assert fold.button.isVisible(), "folded, the button must stay"
        assert fold.status_text() == tr("Margins: OK")
        _two_warnings(panel)
        assert fold.status_text() == tr(
            "{n} warnings: click to show the details").format(n=2)
        assert fold.badge.text() == "⚠ 2"
        assert fold.badge.toolTip() == fold.status_text()
        assert fold.is_collapsed(), "a new warning opened the frames"
        assert tab._info_scroll.isHidden()
        panel.update_report(
            _report(), [], thresholds_defined=True, notify=True,
            text_warnings=["⚠ Strip length 300 mm exceeds the ruler"])
        # nothing red when opened: a neutral notice, never a red warning
        assert fold.status_text() == tr("1 notice: click to show the details")
        assert fold.badge.text() == "ⓘ 1"
        # one red line and one note on the ⓘ: the same "1 warning" the open
        # frame's own header says, never a different number
        panel.update_report(
            _report(), [Violation(edge="Top", measured_mm=4.0,
                                  threshold_mm=8.0)],
            thresholds_defined=True, notify=True,
            text_warnings=["⚠ Strip length 300 mm exceeds the ruler"])
        assert panel._warning_count == 1
        assert fold.status_text() == tr("1 warning: click to show the details")
        panel.show_placeholder()
        assert fold.status_text() == ""
        panel.update_report(_report(), [], thresholds_defined=True,
                            notify=False)
        assert fold.status_text() == "", "warnings switched off say nothing"
    finally:
        w.close()


def test_open_with_no_chart_there_is_no_button(qapp, settings):
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        assert not tab._preview._pages
        assert not tab._preview_fold.button.isVisible()
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
        assert w2._tab_chart._preview_fold.button.isVisible(), (
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


def test_the_badge_reads_on_its_own_ground():
    """White on the badge's red, green and grey: at least 4.5:1 (WCAG AA)."""
    from ui.preview_details_fold import BADGE_GREEN, BADGE_NOTE, BADGE_RED

    def lum(hexc):
        def ch(c):
            c = int(c, 16) / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (ch(hexc[i:i + 2]) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    for c in (BADGE_RED, BADGE_GREEN, BADGE_NOTE):
        assert 1.05 / (lum(c) + 0.05) >= 4.5, c


@pytest.mark.parametrize("lang", ["en", "de", "ru"])
def test_a_narrow_row_keeps_the_page_text_whole(qapp, settings, one_page_tif,
                                                lang):
    """In the smallest window the worded buttons and the page text did not
    fit (the page text ran under a button, the other left the window): the
    buttons then show their arrows only, nothing overlaps, and the words
    come back when there is room."""
    from core.i18n import set_language, tr
    set_language(lang)
    try:
        w = _window(qapp, settings, (900, 951))
        try:
            _show_chart(qapp, w, one_page_tif, pages=10)
            prev = w._tab_chart._preview
            for _ in range(10):
                qapp.processEvents()
            p, lab, n = (prev._prev_btn.geometry(),
                         prev._page_label.geometry(),
                         prev._next_btn.geometry())
            assert p.right() < lab.left() and lab.right() < n.left(), (
                "the page text and a button overlap")
            assert n.right() <= prev._nav.width(), "a button left the row"
            text = prev._page_label.text()
            assert lab.width() >= prev._page_label.fontMetrics(
                ).horizontalAdvance(text), "the page text is cut"
            w.resize(1500, 1000)
            for _ in range(10):
                qapp.processEvents()
            assert prev._prev_btn.text() == tr("‹ Prev")
            assert prev._next_btn.text() == tr("Next ›")
        finally:
            w.close()
    finally:
        set_language("en")


@pytest.mark.parametrize("case", ["ok", "notice", "warning", "both"])
def test_the_badge_counts_what_the_open_frame_shows(qapp, settings, case):
    """Red only for what is red when opened (review of 2026-11-14)."""
    from core.i18n import tr
    from ui.preview_details_fold import BADGE_GREEN, BADGE_NOTE, BADGE_RED
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        fold, panel = tab._preview_fold, tab._margin_panel
        fold.toggle()
        viol = ([Violation(edge="Top", measured_mm=4.0, threshold_mm=8.0)]
                if case in ("warning", "both") else [])
        notes = (["⚠ The sheet text runs into the patches."]
                 if case in ("notice", "both") else [])
        panel.update_report(_report(), viol, thresholds_defined=True,
                            notify=True, text_warnings=notes)
        red_lines = panel._warning_count
        sheet = fold.badge.styleSheet()
        if case == "ok":
            assert fold.badge.text() == "✓" and BADGE_GREEN in sheet
            assert fold.status_text() == tr("Margins: OK")
        elif case == "notice":
            assert red_lines == 0
            assert fold.badge.text() == "ⓘ 1" and BADGE_NOTE in sheet
            assert BADGE_RED not in sheet
        else:
            assert fold.badge.text() == f"⚠ {red_lines}" and BADGE_RED in sheet
            assert red_lines == 1
    finally:
        w.close()


def test_the_fold_button_says_what_it_does(qapp, settings):
    from core.i18n import tr
    w = _window(qapp, settings)
    try:
        assert w._tab_chart._preview_fold.button.accessibleName() == tr(
            "Hide or show the measurements and the chart layout information")
    finally:
        w.close()


def test_switching_appearance_while_compact_brings_back_a_fresh_style(
        qapp, settings, one_page_tif):
    """The worded buttons' own sheet is put back when the row widens; an
    appearance switch meanwhile must not leave a stale sheet on them."""
    from ui.theme import apply_appearance
    w = _window(qapp, settings, (900, 951))
    try:
        _show_chart(qapp, w, one_page_tif, pages=3)
        prev = w._tab_chart._preview
        prev._prev_btn.setStyleSheet("QPushButton { min-width: 200px; }")
        prev._nav_compact = False
        prev._fit_nav_to_width()
        compact = prev._nav_compact
        apply_appearance(qapp, w, "dark")
        for _ in range(10):
            qapp.processEvents()
        w.resize(1500, 1000)
        for _ in range(10):
            qapp.processEvents()
        assert prev._prev_btn.text() != "‹" or not compact
        assert prev._next_btn.isVisible()
        g1, g2 = prev._prev_btn.geometry(), prev._next_btn.geometry()
        assert g1.right() < prev._page_label.geometry().left() < g2.left()
    finally:
        apply_appearance(qapp, w, "light")
        w.close()
