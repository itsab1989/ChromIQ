"""Final fix round, S-8 (review 13): the calibration place's help is reachable without hovering
(an (i) button, as every row around it), and the table's completion window says "saved" once:
Close saves nothing more after the table's own Save, so its sentence only says it stays."""
from __future__ import annotations

import pytest

#: 4.3.54 release: a completion-window test that does not end fails within 3 minutes (the
#: thread method dumps every stack and ends the worker, which fails the run at once) instead of
#: spinning for 50 minutes as on the 2026-11-21 gate; faulthandler_timeout only dumps
pytestmark = pytest.mark.timeout(180, method="thread")

from tests.i1io_table.test_fix10_open_points import _finish_complete
from tests.i1io_table.test_window_in_the_measure_tab import beta, tab, table_run  # noqa: F401


def test_the_calibration_place_row_has_its_i_button(qapp, tmp_path):
    import workflow.i1io.support as sup
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog, i1io_cal_place_help
    from ui.tooltip_button import TooltipButton
    sup.set_enabled_for_this_process(True)
    try:
        dlg = SettingsDialog(AppSettings())
        found = [b for b in dlg.findChildren(TooltipButton)
                 if b._body == i1io_cal_place_help().strip()]
        assert found, "no (i) button carries the calibration place's help"
        dlg.deleteLater()
    finally:
        sup.set_enabled_for_this_process(None)
    assert "resting place over the table's tile" in i1io_cal_place_help()


def test_the_table_completion_window_says_saved_once(tab, beta, tmp_path, monkeypatch, qtbot):
    from PyQt6.QtWidgets import QDialog, QLabel
    tab._settings.set("averaging_enabled", False)
    run, sheet = table_run(tmp_path)
    texts = []

    def exec_(dlg):
        texts.extend(lb.text() for lb in dlg.findChildren(QLabel))
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", exec_)
    _finish_complete(tab, run, monkeypatch, qtbot)
    body = " ".join(t for t in texts if "every patch" in t)
    assert body, texts
    assert body.count("saved") == 1 and "the measurement is saved" in body
    assert "<b>Close</b> saves" not in body
    assert "<b>Close</b> stays on this tab" in body
