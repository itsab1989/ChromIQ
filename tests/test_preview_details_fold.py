"""One fold for the two frames under the Create Chart preview (Basti,
2026-11-14): *"make measured from preview and chart layout information section
collapsible? i think one button (or triangle) should collapse both at once"*.

Pinned here, on a real main window:

1. open by default, so nothing changes for anyone who never clicks it;
2. one click (or Space / Return with the keyboard) hides BOTH frames and the
   preview gets the room; a second click brings them back;
3. never silent: folded, the line repeats the verdict, "Margins: OK" or the
   number of warnings, live as the report changes, and a new warning does not
   open the frames again;
4. remembered in the app's settings, across a rebuilt window, and nowhere in
   a target's store;
5. the guide and pointer boxes inside keep their state while hidden.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

from workflow.margin_inspector import MarginReport, Violation


def _window(qapp, settings):
    from ui.main_window import MainWindow
    w = MainWindow(settings)
    w.resize(1400, 900)
    w.show()
    w._tabs.setCurrentWidget(w._tab_chart) if hasattr(w, "_tabs") else None
    for _ in range(10):
        qapp.processEvents()
    return w


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


def test_open_by_default_and_one_click_folds_both(qapp, settings, qtbot):
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        fold = tab._preview_fold
        assert not fold.is_collapsed()
        assert not tab._info_scroll.isHidden()
        h_open = tab._preview.height()
        qtbot.mouseClick(fold, Qt.MouseButton.LeftButton)
        for _ in range(10):
            qapp.processEvents()
        assert fold.is_collapsed()
        assert tab._info_scroll.isHidden(), "the two frames are still shown"
        assert tab._margin_panel.isVisibleTo(tab._info_scroll.widget())
        assert tab._layout_info_panel.isVisibleTo(tab._info_scroll.widget())
        assert tab._preview.height() > h_open, "the preview got no room"
        assert settings.get("preview_details_collapsed") is True
        qtbot.keyClick(fold, Qt.Key.Key_Space)
        assert not fold.is_collapsed() and not tab._info_scroll.isHidden()
        qtbot.keyClick(fold, Qt.Key.Key_Return)
        assert fold.is_collapsed()
        assert fold.focusPolicy() == Qt.FocusPolicy.StrongFocus
    finally:
        w.close()


def test_folded_the_line_repeats_the_verdict_live(qapp, settings, qtbot):
    from core.i18n import tr
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        fold, panel = tab._preview_fold, tab._margin_panel
        _ok(panel)
        assert fold.status_text() == "", "open, the frames say it themselves"
        fold.toggle()
        assert fold.status_text() == tr("Margins: OK")
        _two_warnings(panel)
        assert fold.status_text().startswith(
            tr("{n} warnings").format(n=2)), fold.status_text()
        assert fold.is_collapsed(), "a new warning opened the frames"
        assert tab._info_scroll.isHidden()
        panel.update_report(
            _report(), [], thresholds_defined=True, notify=True,
            text_warnings=["⚠ Strip length 300 mm exceeds the ruler"])
        assert fold.status_text().startswith(tr("1 warning"))
        # one red line and one note on the ⓘ: the same "1 warning" the open
        # frame's own header says, never a different number
        panel.update_report(
            _report(), [Violation(edge="Top", measured_mm=4.0,
                                  threshold_mm=8.0)],
            thresholds_defined=True, notify=True,
            text_warnings=["⚠ Strip length 300 mm exceeds the ruler"])
        assert panel._warning_count == 1
        assert fold.status_text().startswith(tr("1 warning"))
        panel.show_placeholder()
        assert fold.status_text() == ""
        _two_warnings(panel)
        settings.set("margin_violation_notify", False)
        _two_warnings(panel)
        panel.update_report(_report(), [], thresholds_defined=True,
                            notify=False)
        assert fold.status_text() == "", "warnings switched off say nothing"
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
    finally:
        w2.close()


def test_the_choice_is_not_a_target_setting(qapp, settings):
    w = _window(qapp, settings)
    try:
        tab = w._tab_chart
        tab._preview_fold.toggle()
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
