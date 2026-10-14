"""K7 (Knut, #182 6154440320, 4.3.5 beta 4): choosing "Validation print check
(ISO 12647-8)" selects the ISO 12647-8 limit set, and "Contract proof check
(ISO 12647-7)" the ISO 12647-7 set; the user may change it afterwards.

Before K7 any of the four ISO sets stayed, the other standard's included
(K36-1 as amended, 5822758830 answer 4). Now only the type's own standard's
sets stay: its read-only set and its Custom set.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication             # noqa: E402

from workflow import measurement_report as mr        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("type_id,own", [(mr.REPORT_TYPE_ISO_8, "iso_12647_8"),
                                         (mr.REPORT_TYPE_ISO_7, "iso_12647_7")])
@pytest.mark.parametrize("before", ["chromiq_default", "chromiq_tight",
                                    "chromiq_quick", "iso_12647_7",
                                    "iso_12647_8", "custom_iso_12647_7",
                                    "custom_iso_12647_8"])
def test_choosing_an_iso_type_selects_its_standards_set(type_id, own, before):
    got = mr.set_on_choosing_type(type_id, before)
    if before in (own, "custom_" + own):
        assert got == before          # already that standard's: kept
    else:
        assert got == own


def test_any_other_type_keeps_the_set():
    for t in (mr.REPORT_TYPE_FULL,):
        for sid in ("chromiq_tight", "iso_12647_8", "custom_iso_12647_7"):
            assert mr.set_on_choosing_type(t, sid) == sid


def test_the_report_window_selects_and_lets_the_user_change(tmp_path, qapp):
    from tests.test_the_report_type_pulldown_stores_on_the_run import _dialog
    from tests.test_challenge4_beta42_the_iso_hold_survives import _close
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        def choose_type(t):
            dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(t))
            qapp.processEvents()

        choose_type(mr.REPORT_TYPE_ISO_8)
        assert dlg._set_combo.currentData() == "iso_12647_8"
        choose_type(mr.REPORT_TYPE_ISO_7)
        assert dlg._set_combo.currentData() == "iso_12647_7"
        assert dlg._report_limits().set_id == "iso_12647_7"
        # the user changes it afterwards: it stays
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData("iso_12647_8"))
        qapp.processEvents()
        assert dlg._report_limits().set_id == "iso_12647_8"
        assert dlg._type_combo.currentData() == mr.REPORT_TYPE_ISO_7
        choose_type(mr.REPORT_TYPE_ISO_8)
        assert dlg._set_combo.currentData() == "iso_12647_8"
    finally:
        _close(dlg)
