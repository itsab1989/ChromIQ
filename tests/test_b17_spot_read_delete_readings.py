"""Beta 17, builder B: Tools ▸ Read single patches can delete single readings.

Backspace and Delete remove the selected readings while the list has the focus,
there is a visible Delete button and a right-click entry, and Undo delete
(or Cmd+Z in the list) puts them back where they were. Names stay as they are
and are never re-used, the saved files hold exactly what the list holds, and
closing still asks while something unsaved is left.

The real window, driven through its own controls; only the modal loop is
answered (`_ask`, the window's one seam), never `QMessageBox.exec`.
"""
from __future__ import annotations

import csv
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtTest import QTest                                 # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox          # noqa: E402

from core.argyll_runner import ArgyllRunner                    # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from ui.dialogs.spot_read_dialog import SpotReadDialog         # noqa: E402
from workflow.spot_read_io import write_csv                    # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Dlg(SpotReadDialog):
    answer = "Cancel"

    def _ask(self, box: QMessageBox):
        self.asked.append(box.text())
        for b in box.buttons():
            if b.text().replace("&", "") == self.answer:
                return b
        return None


@pytest.fixture
def dlg(qapp):
    s = AppSettings()
    d = _Dlg(ArgyllRunner(s), s)
    d.asked = []
    d.show()
    QTest.qWaitForWindowExposed(d, 2000)
    for i in range(4):
        d._on_reading((10.0 + i, 10.0 + i, 10.0 + i),
                      (40.0 + i, 1.0 * i, -1.0 * i))
    yield d
    d._closing = True
    d.hide()
    d.deleteLater()


def _names(d):
    return [r.name for r in d._readings]


def _table_names(d):
    return [d._table.item(r, 0).text() for r in range(d._table.rowCount())]


def _select(d, *rows):
    d._table.clearSelection()
    for r in rows:
        d._table.selectRow(r) if len(rows) == 1 else \
            d._table.selectionModel().select(
                d._table.model().index(r, 0),
                d._table.selectionModel().SelectionFlag.Select
                | d._table.selectionModel().SelectionFlag.Rows)


def test_there_is_a_visible_delete_button_that_follows_the_selection(dlg):
    btn = dlg._del_btn
    assert btn.isVisible() and btn.text() == "Delete"
    assert not btn.isEnabled(), "Delete is live with nothing selected"
    _select(dlg, 1)
    assert btn.isEnabled()
    btn.click()
    assert _names(dlg) == ["Patch 1", "Patch 3", "Patch 4"]
    assert _table_names(dlg) == _names(dlg)


def test_backspace_and_delete_in_the_list_remove_the_selection(dlg, qapp):
    dlg._table.setFocus()
    _select(dlg, 0)
    QTest.keyClick(dlg._table, Qt.Key.Key_Backspace)
    assert _names(dlg) == ["Patch 2", "Patch 3", "Patch 4"]
    _select(dlg, 1, 2)
    QTest.keyClick(dlg._table, Qt.Key.Key_Delete)
    assert _names(dlg) == ["Patch 2"]
    assert _table_names(dlg) == _names(dlg)


def test_the_keys_do_nothing_outside_the_list(dlg):
    _select(dlg, 0)
    dlg._save_btn.setFocus()
    QTest.keyClick(dlg._save_btn, Qt.Key.Key_Backspace)
    assert len(dlg._readings) == 4


def test_backspace_while_renaming_edits_the_name_not_the_list(dlg, qapp):
    dlg._table.setFocus()
    _select(dlg, 0)
    dlg._table.editItem(dlg._table.item(0, 0))
    qapp.processEvents()
    editor = QApplication.focusWidget()
    assert editor is not dlg._table
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert len(dlg._readings) == 4


def test_the_right_click_menu_offers_delete(dlg):
    _select(dlg, 2)
    menu = dlg._table_menu()
    acts = {a.text(): a for a in menu.actions()}
    assert "Delete" in acts and acts["Delete"].isEnabled()
    acts["Delete"].trigger()
    assert _names(dlg) == ["Patch 1", "Patch 2", "Patch 4"]
    menu = dlg._table_menu()
    assert "Undo delete" in [a.text() for a in menu.actions()]


def test_undo_puts_them_back_in_their_places(dlg):
    _select(dlg, 0, 2)
    dlg._del_btn.click()
    assert _names(dlg) == ["Patch 2", "Patch 4"]
    assert dlg._del_btn.text() == "Undo delete"
    dlg._del_btn.click()
    assert _names(dlg) == ["Patch 1", "Patch 2", "Patch 3", "Patch 4"]
    assert _table_names(dlg) == _names(dlg)


def test_cmd_z_in_the_list_undoes_too(dlg):
    dlg._table.setFocus()
    _select(dlg, 3)
    QTest.keyClick(dlg._table, Qt.Key.Key_Delete)
    assert len(dlg._readings) == 3
    QTest.keySequence(dlg._table, "Ctrl+Z")
    assert _names(dlg)[-1] == "Patch 4"


def test_a_deleted_number_is_never_given_out_again(dlg):
    _select(dlg, 3)
    dlg._del_btn.click()                          # Patch 4 goes
    dlg._on_reading((1, 1, 1), (50, 0, 0))
    _select(dlg, 1)
    dlg._del_btn.click()                          # Patch 2 goes
    dlg._on_reading((1, 1, 1), (50, 0, 0))
    assert _names(dlg) == ["Patch 1", "Patch 3", "Patch 5", "Patch 6"]
    assert len(set(_names(dlg))) == len(dlg._readings)


def test_a_new_reading_forgets_the_undo(dlg):
    _select(dlg, 0)
    dlg._del_btn.click()
    dlg._on_reading((1, 1, 1), (50, 0, 0))
    assert dlg._deleted == []
    assert dlg._del_btn.text() == "Delete" and not dlg._del_btn.isEnabled()


def test_the_export_holds_exactly_what_the_list_holds(dlg, tmp_path):
    _select(dlg, 1)
    dlg._del_btn.click()
    out = write_csv(tmp_path / "spot.csv", dlg._readings)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    body = [r for r in rows[1:] if r]
    assert [r[0] for r in body] == ["Patch 1", "Patch 3", "Patch 4"]


def test_a_delete_after_saving_makes_closing_ask_again(dlg):
    dlg._unsaved = False                          # as after a Save
    _select(dlg, 0)
    dlg._del_btn.click()
    assert dlg._unsaved, "the list no longer matches the file, yet it is 'saved'"
    dlg.answer = "Cancel"
    assert dlg._may_close() is False and dlg.asked


def test_deleting_everything_leaves_nothing_to_ask_about(dlg):
    _select(dlg, 0, 1, 2, 3)
    dlg._del_btn.click()
    assert dlg._readings == [] and dlg._table.rowCount() == 0
    assert not dlg._save_btn.isEnabled()
    assert dlg._may_close() is True and not dlg.asked
