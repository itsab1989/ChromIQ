"""B8-1591: no setting of the report window changes the page before Generate.

Knut, #182 5858874320, 2026-09-27:

    Any change in settings will give a red text to click generate report, no
    matter if the loaded report is an old or new report. Clicking Generate
    Report will either create a new report, update the selected report (unless
    canceled.). new or update will always regenerate according to the version
    of ChromIQ that is running. No regenerating or change of the report text
    happens before Generate Report is pressed. This is the rule, mentioned
    several times.

Each setting is moved on a window showing a SAVED report, and the page (its
text, the trend graphs, the key under them) is compared with the page before:
unchanged, and the red line up. Putting the setting back takes the line down.
Cancel at Generate's question keeps the page and the line; Update rebuilds it.

MUTATIONS: call `_refresh()` from `_settings_touched` (every move redraws);
keep the red line down with nothing ticked again (Deselect all goes red);
drop the `_refresh` after an Update (the last test goes red).
"""
from __future__ import annotations

import hashlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402

from tests.test_the_report_waits_for_the_generate_button import (  # noqa: E402
    _asks_for_no_press, _dialog)


def _trend(dlg) -> str:
    parts = []
    tabs = dlg._trend_tabs
    for i in range(tabs.count()):
        w = tabs.widget(i)
        parts.append(tabs.tabText(i))
        for name in ("_series", "_thresholds", "_limit_lines", "_line_notes",
                     "_no_limit_text", "_info_note"):
            parts.append(repr(getattr(w, name, None)))
    parts.append(dlg._trend_key.text())
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()


def _page(dlg) -> tuple:
    return dlg._view.toHtml(), _trend(dlg)


def _saved(tmp_path, qapp):
    """A window on two dates, with a report generated and SHOWN (the saved
    report the settings are then moved on)."""
    dlg, run, fm = _dialog(tmp_path, qapp, dates=2)
    dlg._ask_update_or_create_new = lambda: "new"
    dlg._on_generate_report()
    qapp.processEvents()
    assert dlg._saved_combo.currentIndex() > 0 or dlg._loaded_doc_id, (
        "Generate saved no report, so there is no saved report to move a "
        "setting on")
    assert not dlg._stale_label.isVisible()
    return dlg


def _run_item(dlg):
    from PyQt6.QtCore import Qt
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        item = dlg._profile_list.item(i)
        if kind == "run" and key and item.checkState() == Qt.CheckState.Checked:
            return item
    raise AssertionError("no ticked measurement row")


def _other(combo):
    m = combo.model()
    cur = combo.currentData()
    for i in range(combo.count()):
        item = m.item(i) if hasattr(m, "item") else None
        if item is not None and not item.isEnabled():
            continue
        if combo.itemData(i) not in (None, cur):
            return i
    return -1


def _moves(dlg):
    """(name, move, put back) for every setting of the window."""
    from PyQt6.QtCore import Qt

    def combo(c):
        i0 = c.currentIndex()
        i1 = _other(c)

        def move():
            assert i1 >= 0, f"{c.objectName() or c} offers nothing else"
            c.setCurrentIndex(i1)
            c.activated.emit(i1)

        def back():
            c.setCurrentIndex(i0)
            c.activated.emit(i0)
        return move, back

    t_move, t_back = combo(dlg._type_combo)
    s_move, s_back = combo(dlg._set_combo)
    det = dlg._detail_check.isChecked()
    item = _run_item(dlg)
    return [
        ("Report type", t_move, t_back),
        ("Judged against", s_move, s_back),
        ("Show detailed data", lambda: dlg._detail_check.setChecked(not det),
         lambda: dlg._detail_check.setChecked(det)),
        ("a measurement's tick",
         lambda: item.setCheckState(Qt.CheckState.Unchecked),
         lambda: item.setCheckState(Qt.CheckState.Checked)),
        ("Deselect all", dlg._deselect_all_btn.click,
         dlg._select_all_btn.click),
    ]


@pytest.mark.parametrize("which", range(5))
def test_a_setting_moved_on_a_saved_report_changes_nothing_on_the_page(
        tmp_path, qapp, which):
    dlg = _saved(tmp_path, qapp)
    try:
        name, move, back = _moves(dlg)[which]
        before = _page(dlg)
        move()
        qapp.processEvents()
        assert _page(dlg) == before, f"{name} changed the page before Generate"
        assert dlg._stale_label.isVisible(), (
            f"{name} moved and no red line says so")
        if not dlg._generate_btn.isEnabled():
            # Deselect all: Generate is greyed, and the line asks for no press
            assert _asks_for_no_press(dlg), (
                "the red line asks for a press of a greyed Generate")
        back()
        qapp.processEvents()
        assert _page(dlg) == before, f"putting {name} back changed the page"
        assert not dlg._stale_label.isVisible(), (
            f"{name} is back as the report was built and the line is still up")
    finally:
        dlg.close()


def test_a_number_changed_in_edit_limits_changes_nothing_on_the_page(
        tmp_path, qapp, monkeypatch):
    from ui.dialogs.thresholds_dialog import RUN_COLUMN, ThresholdsDialog
    from ui.widgets import NoScrollDoubleSpinBox
    dlg = _saved(tmp_path, qapp)
    try:
        changed = []

        def _exec(td):
            for (col, rid), w in td._cells.items():
                if col == RUN_COLUMN and isinstance(w, NoScrollDoubleSpinBox) \
                        and w.isEnabled():
                    w.setValue(round(w.value() + 0.3, 2))
                    changed.append(rid)
                    break
            td.done(1)              # what Close does: the column is written
            return 1
        monkeypatch.setattr(ThresholdsDialog, "exec", _exec)
        before = _page(dlg)
        dlg._limits_btn.click()
        qapp.processEvents()
        assert changed, "the report's own column offered no number to change"
        assert _page(dlg) == before, "Edit limits… changed the page"
        assert dlg._stale_label.isVisible(), (
            "the report's own limit changed and no red line says so")
    finally:
        dlg.close()


def test_cancel_at_generate_keeps_the_page_and_the_red_line(tmp_path, qapp):
    dlg = _saved(tmp_path, qapp)
    try:
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        before = _page(dlg)
        dlg._ask_update_or_create_new = lambda: "cancel"
        dlg._on_generate_report()
        qapp.processEvents()
        assert _page(dlg) == before, "a cancelled Generate changed the page"
        assert dlg._stale_label.isVisible(), (
            "a cancelled Generate took the red line down")
    finally:
        dlg.close()


def test_update_rebuilds_the_page_and_takes_the_line_down(tmp_path, qapp):
    dlg = _saved(tmp_path, qapp)
    try:
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        before = _page(dlg)
        dlg._ask_update_or_create_new = lambda: "update"
        dlg._on_generate_report()
        qapp.processEvents()
        assert _page(dlg) != before, (
            "Update did not build the report with the moved setting")
        assert not dlg._stale_label.isVisible()
    finally:
        dlg.close()


def test_with_nothing_ticked_the_line_says_a_measurement_is_needed(
        tmp_path, qapp):
    """B8-1592 (Knut, #182 5859248797): with every measurement unticked,
    Generate is greyed and the red line names the reason, "at least one
    measurement must be ticked", instead of pointing at a reason elsewhere."""
    from core.i18n import tr
    dlg = _saved(tmp_path, qapp)
    try:
        dlg._deselect_all_btn.click()
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled()
        assert dlg._stale_label.isVisible()
        assert dlg._stale_label.text() == tr(
            "⚠ Settings changed. At least one measurement must be ticked "
            "to generate a report.")
    finally:
        dlg.close()
