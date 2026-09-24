"""B8-974: "All metrics" in "Which presets can be used for verification?".

Knut, #182 5814820283: the "Metrics answered" count covered only the rows the
chosen limit set switches on, and most sets leave many at "-", so *"there is
no way to actually see if any of the reports could fulfil ALL metrics"*. He
asked for a "Judged against" entry that *"ignores the limit sets selected
thresholds"* and checks every preset and the current chart *"against ALL
metrics"*, and for it to be *"the default when opening the window"*.

Three things are pinned, each with the mutation that turns it red (all three
proved red before this file was committed):

* the entry exists and is "All metrics"
  (MUTATION: drop the `addItem(tr("All metrics"), ...)` line);
* the window opens on it, every time, and does not remember a different choice
  (MUTATION: add it after the limit sets instead of before them);
* it counts every metric a report of the type can judge, not the rows a limit
  set has switched on, and the column's "n of N" uses that N
  (MUTATION: make `rows_asked(..., ALL_METRICS)` return the rows ChromIQ
  default limits).
"""
from __future__ import annotations

import re

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication

from core.i18n import tr
from core.settings import AppSettings
from ui.dialogs import preset_verification_dialog as PVD
from ui.tabs.tab_chart import verification_preset_rows
from workflow import compliance_sets as CS
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


def _open(qapp, rows, current=None):
    dlg = PVD.PresetVerificationDialog(list(rows), None, None, current=current)
    dlg.show()
    qapp.processEvents()
    return dlg


def _close(qapp, dlg):
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def _items(dlg):
    out = []
    for i in range(dlg._tree.topLevelItemCount()):
        top = dlg._tree.topLevelItem(i)
        for it in [top] + [top.child(j) for j in range(top.childCount())]:
            row = it.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(row, PVD.PresetRow):
                out.append((it, row))
    return out


#: Every row a report can judge: ChromIQ can compute it, and it is not one of
#: the two repeatability rows the window never asks of a chart (a property of
#: a measurement history, not of a chart). Derived from the rows, never from
#: the sets, which is the whole point of the entry.
def _every_metric():
    return tuple(r.id for r in CS.ROWS
                 if r.status in ("now", "build", "ref")
                 and r.id not in CS.POPULATION_MAY_BE_ABSENT)


# ---------------------------------------------------------------------------
# 1. the entry exists
# ---------------------------------------------------------------------------
def test_judged_against_offers_all_metrics(qapp, rows):
    dlg = _open(qapp, rows)
    try:
        idx = dlg._set_combo.findData(PE.ALL_METRICS)
        assert idx >= 0, "no 'All metrics' entry under Judged against"
        assert dlg._set_combo.itemText(idx) == tr("All metrics")
        # every limit set is still offered after it
        sets = [dlg._set_combo.itemData(i)
                for i in range(dlg._set_combo.count())]
        assert sets[1:] == CS.selectable_set_ids(None)
    finally:
        _close(qapp, dlg)


# ---------------------------------------------------------------------------
# 2. it is the default, every time the window opens
# ---------------------------------------------------------------------------
def test_the_window_opens_on_all_metrics_every_time(qapp, rows):
    first = _open(qapp, rows)
    try:
        assert first.current_set() == PE.ALL_METRICS
        assert first._set_combo.currentIndex() == 0
        # the reader moves to a limit set and closes the window there
        first._set_combo.setCurrentIndex(
            first._set_combo.findData("chromiq_default"))
        qapp.processEvents()
        assert first.current_set() == "chromiq_default"
    finally:
        _close(qapp, first)
    again = _open(qapp, rows)
    try:
        assert again.current_set() == PE.ALL_METRICS, (
            "the window remembered the last Judged against choice")
    finally:
        _close(qapp, again)


# ---------------------------------------------------------------------------
# 3. it counts every metric, and the column's total is that count
# ---------------------------------------------------------------------------
def test_all_metrics_asks_every_metric_not_the_rows_a_set_switches_on():
    every = _every_metric()
    for tid in (MR.REPORT_TYPE_FULL, "t1_colour_summary"):
        assert PE.rows_asked(tid, PE.ALL_METRICS) == every
    # more than any ChromIQ set asks, and at least as much as any set at all
    for sid in CS.selectable_set_ids(None):
        asked = set(PE.rows_asked("t1_colour_summary", sid))
        assert asked <= set(every), sid
    for sid in ("chromiq_default", "chromiq_tight", "chromiq_quick"):
        assert len(PE.rows_asked("t1_colour_summary", sid)) < len(every), sid
    # rows ChromIQ's own sets leave at "-" are counted here
    default = set(PE.rows_asked("t1_colour_summary", "chromiq_default"))
    assert any(rid not in default for rid in every)


def test_all_metrics_still_follows_the_report_type():
    """The entry replaces the limit set, not the report type: "Grey and tone
    check" is about three rows, and a Printing record judges nothing."""
    only = MR.rows_for_report_type("t3_grey_and_tone")
    assert PE.rows_asked("t3_grey_and_tone", PE.ALL_METRICS) == tuple(
        r for r in _every_metric() if r in only)
    assert PE.rows_asked(MR.REPORT_TYPE_RECORD, PE.ALL_METRICS) == ()


def test_the_column_total_is_every_metric(qapp, rows):
    dlg = _open(qapp, rows)
    try:
        dlg._type_combo.setCurrentIndex(
            dlg._type_combo.findData("t1_colour_summary"))
        qapp.processEvents()
        total = len(_every_metric())
        checked = [(it, r) for it, r in _items(dlg) if r.assessment.checked]
        assert checked, "no preset could be assessed, so this proves nothing"
        for it, r in checked:
            assert len(r.assessment.asked) == total, r.label
            assert it.text(3) == tr("{n} of {total} metrics").format(
                n=len(r.assessment.answered), total=total), r.label
        # and the count line says the same number, in its own words
        assert dlg._asked_label.text() == tr(
            "All metrics: a report of this type can verify {n} metrics of a "
            "chart, whichever limit set it is judged against.").format(
                n=total)
        # the same preset reads a SMALLER total under ChromIQ default
        it0, r0 = checked[0]
        dlg._set_combo.setCurrentIndex(
            dlg._set_combo.findData("chromiq_default"))
        qapp.processEvents()
        n_default = len(PE.rows_asked("t1_colour_summary", "chromiq_default"))
        again = next(it for it, r in _items(dlg) if r.label == r0.label)
        assert int(re.findall(r"\d+", again.text(3))[-1]) == n_default
        assert n_default < total
    finally:
        _close(qapp, dlg)


def test_the_detail_pane_names_no_limit_set_under_all_metrics():
    """A chart that answers everything is told so without a limit set in the
    sentence, because none was chosen."""
    a = PE.Assessment(asked=("all_de00_avg",), answered=("all_de00_avg",),
                      missing=())
    row = PVD.PresetRow(group="g", label="x", chart=None, patches=10,
                        pages=1, builtin=True, assessment=a)
    text = [ln.text for ln in PVD.detail_lines(row, every_metric=True)]
    assert tr("This chart answers every metric a report of this type can "
              "judge.") in text
    assert not any("limit set" in t for t in text), text
