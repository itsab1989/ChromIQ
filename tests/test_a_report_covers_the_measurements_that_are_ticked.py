"""Knut's beta-29 reversal: the ticks decide, and nothing else.

**Knut, 2026-09-20, on issue #182**, having watched "Show all measurement runs"
mean two different things in one window:

> *"I realise now this checkbox is not a reasonable feature to have (and has
> evolved to something that it was not originally used) and should be removed
> … The feature that actually is desired here is a button 'Select All' … and a
> button 'Deselect All' … These two buttons then ONLY select or clear the
> selection of the listed measurements … Remove the feature 'Show all
> measurement runs' totally from the design, and any feature that belongs to
> that button … only the selected/ticked measurements shall be part of the
> report when created/updated (always)."*

Five things have to hold, and each was a separate fault he reported:

* **B8-590** the box is gone, the two buttons are there, and they tick and
  untick and do nothing else.
* **B8-591** the measurement list is never disabled. A "Colour summary" used
  to disable it, which is what he met as *"it froze, so I cannot scroll or
  select"* — and it stayed frozen when he moved on to "New report...".
  A one-page summary still covers one measurement; it now SAYS so at Generate
  instead of narrowing the list behind him.
* **B8-593** the "Already generated for this run" count is a count of
  REPORTS. One press of Generate writes one file per ticked measurement, all
  of one document, so counting files made it disagree with the pulldown
  beside it: *"Full colour check (11), while the pulldown for Run shown only
  has one report"*.
* **B8-594/595** a report that has never been updated carries ONE date, and
  carries its date flag like every other report.
* **B8-596** selecting a report ticks the measurements THAT report was built
  from: *"the 'included measurements in report' always have all measurements
  ticked. This is wrong."*

Everything here operates the real controls of a real window on a real project:
a mouse click on a list row's tick, a mouse click on the buttons, the pulldown
through its own activation path. Nothing reads a slot's source and nothing
asserts on a widget the window never drew.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402
from PyQt6.QtCore import QPoint, Qt                             # noqa: E402
from PyQt6.QtTest import QTest                                  # noqa: E402

import workflow.measurement_report as mr                        # noqa: E402


# --------------------------------------------------------------------------
# a run with several dated verifications, each with a saved report
# --------------------------------------------------------------------------
def _project(tmp_path, dates=3):
    import os as _os
    import time as _time

    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import (run_limits)
    from tests.helpers.legacy_run_meta import (bind_run)

    s, fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, "chromiq_default", None)
    lim = run_limits(run, None)
    vs = []
    for d in range(dates):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        # Real, distinct dates: two verifications made in one second share a
        # `created` stamp, and a fixture whose rows cannot be told apart
        # cannot show whether the window tells them apart.
        t = _time.time() - 86400 * (dates - d)
        _os.utime(v.measurement_ti3, (t, t))
        rep = build_report(v.measurement_ti3)
        stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                      set_label=lim.label_en, edited=lim.edited)
        save_report(rep, v.dir)
        vs.append(v)
    return s, run, vs


@pytest.fixture
def window(tmp_path, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, run, vs = _project(tmp_path)
    dlg = MeasurementReportDialog(s, None, initial_ti3=vs[0].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    for v in vs[1:]:
        dlg._append_source(v.measurement_ti3, origin=v.measurement_ti3)
    dlg._rebuild_from_sources()
    qapp.processEvents()
    yield dlg, run, vs
    dlg.close()


def _rows(dlg) -> "list[int]":
    """The indices of the MEASUREMENT rows. Row 0 is the profile header and
    carries no tick, so a probe that clicks it measures nothing."""
    return [i for i, (kind, _si, key) in enumerate(dlg._list_rows)
            if kind == "run" and key is not None]


def _ticked(dlg) -> int:
    return sum(1 for i in range(dlg._profile_list.count())
               if dlg._profile_list.item(i).checkState()
               == Qt.CheckState.Checked)


def _click_tick(dlg, row: int) -> None:
    """A real mouse press on the row's tick indicator."""
    lst = dlg._profile_list
    r = lst.visualItemRect(lst.item(row))
    QTest.mouseClick(lst.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier,
                     QPoint(r.left() + 10, r.center().y()))


def _pick(combo, part: str) -> bool:
    for i in range(combo.count()):
        if part.lower() in combo.itemText(i).lower():
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            return True
    return False


# --------------------------------------------------------------------------
# B8-590 — the box is gone, the buttons are there
# --------------------------------------------------------------------------
def test_the_show_all_box_is_gone_from_the_window(window, qapp):
    dlg, _run, _vs = window
    assert getattr(dlg, "_all_runs_check", None) is None


def test_the_show_all_default_is_gone_from_preferences(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(st, None)
    try:
        assert getattr(dlg, "_report_all_runs_default_check", None) is None
    finally:
        dlg.close()


def test_the_two_buttons_tick_and_untick_every_measurement(window, qapp):
    dlg, _run, _vs = window
    n = len(_rows(dlg))
    assert n >= 3, "the fixture must have several measurements to tick"

    QTest.mouseClick(dlg._deselect_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert _ticked(dlg) == 0

    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert _ticked(dlg) == n


def test_the_two_buttons_change_nothing_but_the_ticks(window, qapp):
    """*"These two buttons then ONLY select or clear the selection."*"""
    dlg, _run, _vs = window
    before = (dlg._type_combo.currentData(), dlg._set_combo.currentData(),
              dlg._detail_check.isChecked())
    QTest.mouseClick(dlg._deselect_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    after = (dlg._type_combo.currentData(), dlg._set_combo.currentData(),
             dlg._detail_check.isChecked())
    assert before == after


def test_the_report_covers_exactly_what_is_ticked(window, qapp):
    """*"only the selected/ticked measurements shall be part of the report
    when created/updated (always)"*."""
    dlg, _run, _vs = window
    rows = _rows(dlg)
    # THE WINDOW OPENS ON THE LATEST REPORT, and since B8-596 that report
    # ticks the measurement it was built from and nothing else. So the "every
    # row ticked" starting point this test needs is asked for rather than
    # assumed: an earlier draft of this file assumed it and failed 1 == 3
    # about behaviour that is now correct.
    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert len(dlg._runs_for_report()) == len(rows)
    _click_tick(dlg, rows[0])
    qapp.processEvents()
    assert len(dlg._runs_for_report()) == len(rows) - 1
    _click_tick(dlg, rows[1])
    qapp.processEvents()
    assert len(dlg._runs_for_report()) == len(rows) - 2


# --------------------------------------------------------------------------
# B8-591 — the list never freezes
# --------------------------------------------------------------------------
@pytest.mark.parametrize("part", ["colour summary", "full colour check",
                                  "grey and tone"])
def test_the_measurement_list_is_never_disabled(window, qapp, part):
    dlg, _run, _vs = window
    assert _pick(dlg._type_combo, part)
    qapp.processEvents()
    lst = dlg._profile_list
    assert lst.isEnabled(), f"the list is dead under {part!r}"
    assert lst.viewport().isEnabled()


def test_a_click_still_toggles_a_row_under_the_one_page_type(window, qapp):
    """The freeze Knut met was `setEnabled(False)`, and `isEnabled()` alone
    would pass on a list whose viewport swallowed every click. So the guard
    clicks."""
    dlg, _run, _vs = window
    assert _pick(dlg._type_combo, "colour summary")
    qapp.processEvents()
    row = _rows(dlg)[0]
    was = dlg._profile_list.item(row).checkState()
    _click_tick(dlg, row)
    qapp.processEvents()
    assert dlg._profile_list.item(row).checkState() != was


def test_the_list_still_works_after_moving_to_new_report(window, qapp):
    """*"when selecting 'New report...' … the 'included measurements in
    report' input box is frozen again"*."""
    dlg, _run, _vs = window
    assert _pick(dlg._type_combo, "colour summary")
    qapp.processEvents()
    _pick(dlg._saved_combo, "new report")
    qapp.processEvents()
    row = _rows(dlg)[0]
    was = dlg._profile_list.item(row).checkState()
    _click_tick(dlg, row)
    qapp.processEvents()
    assert dlg._profile_list.item(row).checkState() != was


def test_generate_refuses_a_one_page_summary_of_several(window, qapp,
                                                        monkeypatch):
    """It TELLS, and it moves no tick. *"the user should be informed … Then
    the user can close that message and do the changes."*"""
    said = []
    import ui.warning_sign as ws
    monkeypatch.setattr(ws, "inform",
                        lambda *a, **k: said.append(a[1:3]) or None)
    dlg, _run, _vs = window
    assert _pick(dlg._type_combo, "colour summary")
    qapp.processEvents()
    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    before = _ticked(dlg)
    dlg._generate_btn.click()
    qapp.processEvents()
    assert said, "Generate wrote a one-page summary of several measurements " \
                 "without saying anything"
    assert str(before) in said[0][1], "the message does not name the count"
    assert _ticked(dlg) == before, "a tick was moved behind the user's back"


# --------------------------------------------------------------------------
# B8-593 — the count is a count of REPORTS
# --------------------------------------------------------------------------
def test_one_document_of_many_files_counts_once(tmp_path, qapp):
    from workflow.measurement_report import (generated_report_types,
                                             list_reports, new_document_id,
                                             rewrite_report, stamp_document)
    import json
    _s, run, vs = _project(tmp_path, dates=3)
    files = [p for v in vs for p in list_reports(v.dir)]
    assert len(files) == 3, "the fixture must have one file per date"
    assert sum(generated_report_types(run).values()) == 3

    # One press of Generate: one document, one file per ticked measurement.
    doc_id = new_document_id()
    for p in files:
        rep = json.loads(p.read_text(encoding="utf-8"))
        stamp_document(rep, doc_id=doc_id, created="2026-09-20T10:00:00",
                       type_id=mr.REPORT_TYPE_FULL, compliance=None,
                       detail=False, measurements=[], scope=mr.SCOPE_ALL_DATES)
        rewrite_report(p, rep)
    counts = generated_report_types(run)
    assert sum(counts.values()) == 1, (
        f"three files of ONE document counted as {counts}")
    assert counts.get(mr.REPORT_TYPE_FULL) == 1


def test_a_leftover_file_cannot_split_one_document_in_two(tmp_path, qapp):
    """*"Full colour check (11), Printing Record (not graded)(1)"* for a single
    document: a press that narrows re-types the files it writes and leaves the
    rest with their old top-level type. The document block's type is what
    decides."""
    from workflow.measurement_report import (generated_report_types,
                                             list_reports, new_document_id,
                                             rewrite_report, set_report_type,
                                             stamp_document)
    import json
    _s, run, vs = _project(tmp_path, dates=3)
    files = [p for v in vs for p in list_reports(v.dir)]
    doc_id = new_document_id()
    for i, p in enumerate(files):
        rep = json.loads(p.read_text(encoding="utf-8"))
        # the leftovers keep an older top-level type on disk
        set_report_type(rep, mr.REPORT_TYPE_FULL if i == 0
                        else mr.REPORT_TYPE_RECORD)
        stamp_document(rep, doc_id=doc_id, created="2026-09-20T10:00:00",
                       type_id=mr.REPORT_TYPE_FULL, compliance=None,
                       detail=False, measurements=[], scope=mr.SCOPE_ALL_DATES)
        rewrite_report(p, rep)
    counts = generated_report_types(run)
    assert counts == {mr.REPORT_TYPE_FULL: 1}, (
        f"one document was counted as {counts}")


# --------------------------------------------------------------------------
# B8-594/595 — one date on the line, and a date flag
# --------------------------------------------------------------------------
def test_a_report_never_updated_shows_one_date_and_no_saved_stamp(window, qapp):
    dlg, _run, _vs = window
    labels = [dlg._saved_combo.itemText(i)
              for i in range(dlg._saved_combo.count())]
    real = [t for t in labels if "new report" not in t.lower()]
    assert real, "the fixture saved no report"
    for t in real:
        assert "saved " not in t, (
            f"a report that was never updated still shows a second date: {t!r}")
        assert "One date" in t, f"a report carries no date flag: {t!r}"


# --------------------------------------------------------------------------
# B8-600/601 — the empty list is not a document
# --------------------------------------------------------------------------
def test_nothing_ticked_leaves_nothing_to_generate(window, qapp):
    """A press must never write a measurement the user explicitly unticked.

    `_runs_for_report` falls back to the loaded measurement so the PAGE does
    not go blank, and that fallback used to reach `_reports_to_generate`, so
    the button stayed live over an empty list.
    """
    dlg, _run, _vs = window
    QTest.mouseClick(dlg._deselect_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert _ticked(dlg) == 0
    assert dlg._reports_to_generate() == [], (
        "Generate would write a report of a measurement that is unticked")
    assert not dlg._generate_btn.isEnabled()


def test_undoing_deselect_all_puts_the_red_line_back_down(window, qapp):
    """The banner is a COMPARISON, and the empty list must not become the
    thing it compares against.

    Press "Deselect all", change your mind, tick the row back: the ticks are
    exactly where the document was built, so nothing has been changed and the
    window must not say it has. It did, because a repaint taken while
    everything was unticked re-stamped the baseline from that state, and
    Generate then asked "Update or Create New?" about a document nobody
    touched.
    """
    dlg, _run, _vs = window
    before = set(dlg._hidden_runs)
    assert not dlg._settings_were_modified(), "the fixture starts settled"

    QTest.mouseClick(dlg._deselect_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert dlg._settings_were_modified(), (
        "unticking everything IS a change and must be reported as one")

    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key in before:
            _click_tick(dlg, i)
            qapp.processEvents()
    assert set(dlg._hidden_runs) == before, "the fixture did not get back"
    assert not dlg._settings_were_modified(), (
        "the ticks are back where the document was built, so nothing changed")


# --------------------------------------------------------------------------
# B8-596 — selecting a report ticks ITS measurements
# --------------------------------------------------------------------------
def test_selecting_a_report_ticks_only_its_own_measurement(window, qapp):
    dlg, _run, _vs = window
    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert _ticked(dlg) == len(_rows(dlg)) >= 3

    picked = None
    for i in range(dlg._saved_combo.count()):
        t = dlg._saved_combo.itemText(i)
        if "new report" in t.lower():
            continue
        dlg._saved_combo.setCurrentIndex(i)
        dlg._saved_combo.activated.emit(i)
        qapp.processEvents()
        picked = t
        break
    assert picked is not None, "no saved report to select"
    assert _ticked(dlg) == 1, (
        f"selecting {picked!r} left {_ticked(dlg)} measurements ticked; "
        "only the one it was built from should be")
