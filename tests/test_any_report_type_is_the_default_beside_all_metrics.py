"""K33 (B8-996, B8-997): "Any" in the Report type pulldown of "Which presets
can be used for verification?", and the window's intro sentence.

Knut, #182 5816565326, asked whether "All metrics" should ignore the report
type too: *"No, the Report type should instead also have an option called
"Any", which is the default, set together with "All metrics" as default for
judged against. Report type and judged against shall still be able to
individually change if desired."* And of the intro sentence: *"the intro
sentence shall say what the fields to, even if the default is set to show any
and all metrics. However, the sentence is hard to read and understand, so the
wording should be rephrased for easier understanding."*

Pinned, each with the mutation that turns it red:

* "Any" is the first Report type entry and the window opens on it together
  with "All metrics" (MUTATION: add "Any" after the report types);
* "Any" asks the union of what the verification report types ask, under
  "All metrics" and under a limit set (MUTATION: make `rows_asked(ANY, ...)`
  return only the first type's rows, or nothing);
* the two pulldowns change independently (MUTATION: reset one when the other
  changes);
* the intro names both fields' "Any" and "All metrics" and no longer runs the
  old noun phrase (MUTATION: restore the old sentence).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel

from core.i18n import tr
from core.settings import AppSettings
from ui.dialogs import preset_verification_dialog as PVD
from ui.tabs.tab_chart import verification_preset_rows
from workflow import measurement_report as MR
from workflow import preset_eligibility as PE


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def rows(qapp, tmp_path_factory):
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path_factory.mktemp("s") / "s.ini"),
                             QSettings.Format.IniFormat)
    return verification_preset_rows(settings)


def _open(qapp, rows):
    dlg = PVD.PresetVerificationDialog(list(rows), None, None)
    dlg.show()
    qapp.processEvents()
    return dlg


def _close(qapp, dlg):
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def _verification_types():
    return [t for t in MR.report_types_for_kind(MR.KIND_VERIFICATION)
            if MR.report_type_is_built(t)]


def test_any_is_the_first_report_type_and_the_window_opens_on_any_and_all_metrics(
        qapp, rows):
    dlg = _open(qapp, rows)
    try:
        assert dlg._type_combo.itemData(0) == PE.ANY_REPORT_TYPE
        assert dlg._type_combo.itemText(0) == tr("Any")
        assert dlg.current_type() == PE.ANY_REPORT_TYPE
        assert dlg.current_set() == PE.ALL_METRICS
        # the count line names "any type", and why 18 is not 20 (B8-995)
        n = len(PE.rows_asked(PE.ANY_REPORT_TYPE, PE.ALL_METRICS))
        assert dlg._asked_label.text() == tr(
            "All metrics: a report of any type can verify {n} metrics of a "
            "chart, whichever limit set it is judged against.").format(n=n) \
            + " " + tr("ChromIQ's two repeatability metrics are not counted "
                       "here: they depend on measuring the chart again, not "
                       "on the chart.")
        # every report type the window offered before is still offered
        types = [dlg._type_combo.itemData(i)
                 for i in range(1, dlg._type_combo.count())]
        assert types == [t for t, _n, _b, _x in MR.REPORT_TYPE_MENU
                         if MR.report_type_is_built(t)]
    finally:
        _close(qapp, dlg)


def test_any_asks_the_union_of_the_verification_types():
    for sid in (PE.ALL_METRICS, "chromiq_default", "custom_iso_12647_7",
                "iso_12647_8"):
        union = set()
        for t in _verification_types():
            union.update(PE.rows_asked(t, sid))
        got = PE.rows_asked(PE.ANY_REPORT_TYPE, sid)
        assert set(got) == union, sid
        assert len(got) == len(set(got)), sid
        # never fewer than the widest single type
        assert len(got) == max(len(PE.rows_asked(t, sid))
                               for t in _verification_types()), sid
    # under All metrics "Any" is every metric a chart can decide: 18 today
    assert len(PE.rows_asked(PE.ANY_REPORT_TYPE, PE.ALL_METRICS)) == \
        len(PE.rows_every_metric(MR.REPORT_TYPE_FULL))
    # and it is more than the narrow type asks
    assert len(PE.rows_asked(PE.ANY_REPORT_TYPE, PE.ALL_METRICS)) > \
        len(PE.rows_asked(MR.REPORT_TYPE_GREY, PE.ALL_METRICS))


def test_the_two_pulldowns_change_independently(qapp, rows):
    dlg = _open(qapp, rows)
    try:
        dlg._type_combo.setCurrentIndex(
            dlg._type_combo.findData(MR.REPORT_TYPE_GREY))
        qapp.processEvents()
        assert dlg.current_set() == PE.ALL_METRICS
        dlg._set_combo.setCurrentIndex(
            dlg._set_combo.findData("chromiq_default"))
        qapp.processEvents()
        assert dlg.current_type() == MR.REPORT_TYPE_GREY
        dlg._type_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert dlg.current_set() == "chromiq_default"
        n = len(PE.rows_asked(PE.ANY_REPORT_TYPE, "chromiq_default"))
        assert dlg._asked_label.text() == tr(
            "A report of any type, judged against this limit set, asks to "
            "verify {n} metrics of a chart during verification.").format(n=n)
    finally:
        _close(qapp, dlg)


def test_the_intro_says_what_the_two_fields_do_in_plain_words(qapp, rows):
    dlg = _open(qapp, rows)
    try:
        intro = next(lab.text() for lab in dlg.findChildren(QLabel)
                     if lab.objectName() == "info")
        assert "“Any”" in intro and "“All metrics”" in intro, intro
        assert "judged against this limit set asks to verify" not in intro
        assert "—" not in intro
    finally:
        _close(qapp, dlg)
