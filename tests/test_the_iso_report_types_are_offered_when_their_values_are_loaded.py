"""K33 (B8-994): "Validation print check" and "Contract proof check" are
offered for a verification whenever their standard's values are loaded.

Knut, #182 5816565326: *"when loading the various demo projects and showing
the Measurement Report window for all the various runs, for run type
verification, the report type options often do not allow selecting the
"Validation print check" or "Contract proof check". These should be available
now."* Measured on screen before the change (every verification run of the
demo pack): never, in any run, because the two types were declared unbuilt.

Pinned, each with the mutation that turns it red:

* with the shipped values both are enabled for a verification, a choice of
  one sticks, and the document is headed with its name (MUTATION: put the
  menu's `built` flag back to False for either);
* with no values loaded both are greyed and the tooltip names the missing
  values and the lever (MUTATION: drop `iso_type_values_missing` from
  `report_type_is_built`);
* a saved report of one is read back as that type while the values are there
  (MUTATION: the same).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.i18n import tr
from workflow import compliance_sets as cs
from workflow import measurement_report as mr


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def repo_values(monkeypatch):
    from tests.helpers.iso_files import use_repo_iso
    use_repo_iso(monkeypatch)
    yield
    cs.reset_iso_cache()


@pytest.fixture
def no_values(tmp_path, monkeypatch):
    from tests.helpers.iso_files import use_empty_shipped_iso
    use_empty_shipped_iso(tmp_path, monkeypatch)
    yield
    cs.reset_iso_cache()


def _dialog(tmp_path, qapp):
    from tests.test_the_report_type_pulldown_stores_on_the_run import _dialog
    return _dialog(tmp_path, qapp)


def _state(dlg, tid):
    c = dlg._type_combo
    i = c.findData(tid)
    return (c.model().item(i).isEnabled(),
            c.itemData(i, Qt.ItemDataRole.ToolTipRole) or "")


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_ISO_8, mr.REPORT_TYPE_ISO_7])
def test_offered_for_a_verification_with_the_shipped_values(
        tid, tmp_path, qapp, repo_values):
    assert mr.report_type_is_built(tid)
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        assert dlg._window_kind() == mr.KIND_VERIFICATION
        enabled, tip = _state(dlg, tid)
        assert enabled, f"{tid} is greyed although its values are loaded"
        blurb = next(b for t, _n, b, _x in mr.REPORT_TYPE_MENU if t == tid)
        assert tip == tr(blurb)
        # choosing it sticks, and the document says what it is
        i = dlg._type_combo.findData(tid)
        dlg._type_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert dlg._report_type_now() == tid
        # the document Generate would write (the page on screen waits for
        # Generate since K31/K32)
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        head = tr("Report type:") + " " + tr(mr.report_type_name(tid))
        import html as _html
        assert _html.escape(head) in body, body[:600]
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_ISO_8, mr.REPORT_TYPE_ISO_7])
def test_greyed_with_the_reason_when_no_values_are_loaded(
        tid, tmp_path, qapp, no_values):
    assert not mr.report_type_is_built(tid)
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        enabled, tip = _state(dlg, tid)
        assert not enabled
        assert "no values of this standard are loaded" in tip, tip
        assert "Reference values" in tip, tip
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_ISO_8, mr.REPORT_TYPE_ISO_7])
def test_a_saved_report_of_one_reads_back_as_that_type(tid, repo_values):
    assert mr.report_type({"report_type": tid}) == tid
    assert mr.recorded_report_type({"report_type": tid}) == tid


def test_each_iso_type_is_tied_to_its_own_standard():
    assert mr.REPORT_TYPE_ISO_SET == {mr.REPORT_TYPE_ISO_8: "iso_12647_8",
                                      mr.REPORT_TYPE_ISO_7: "iso_12647_7"}
