"""K39-2 and K39-3 (Knut, #182 5831246553; register B8-1112, B8-1113; spec
§28.11 of `measurement_report_limits.md`).

K39-2. "Nothing was changed for the selected report" (approved) was followed
by an Update that turned FAIL into PASS on a report an earlier version had
worked out (B8-1093). Asked whether that case should have its own wording,
Knut answered "Yes." The window now works out what the Update would write and
compares it with the page, and asks M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW
when the two differ.

K39-3. *"Selecting "New report…" will not change whatever report is
currently visible, but loads the default settings for "New report…", and
should then also show a red text message telling user to modify settings as
desired and then press Generate Report to apply and make a new report.
Generate Report will then update the viewed report on screen. However, if a
user selects "New report…", and then goes back to selecting the previously
selected report, then that report reloads, as normal when selecting a
report."*
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_c5_a_saved_report_is_its_own_record import (  # noqa: E402
    _pdf_text, _results_words, _window)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _asked(dlg, qapp, monkeypatch, answer="Cancel"):
    """Press Generate report through the real button, answer the real box
    with *answer*; return (headline, button texts left to right, default
    button's text, escape button's text)."""
    from PyQt6.QtWidgets import QMessageBox
    seen = {}

    def _exec(box):
        seen["title"] = box.text()
        seen["body"] = box.informativeText()
        seen["buttons"] = [b.text().replace("&", "") for b in box.buttons()]
        seen["default"] = (box.defaultButton().text().replace("&", "")
                           if box.defaultButton() else None)
        seen["escape"] = (box.escapeButton().text().replace("&", "")
                          if box.escapeButton() else None)
        for b in box.buttons():
            if b.text().replace("&", "") == answer:
                b.click()
                return 0
        raise AssertionError(f"no {answer!r} button")
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    dlg._generate_btn.click()
    qapp.processEvents()
    return seen


def _report_files(run):
    """Every live report file under the run (not the archived ones)."""
    return sorted(p for p in run.dir.rglob("report_*.json")
                  if "old" not in p.relative_to(run.dir).parts)


def _pick(dlg, qapp, key):
    combo = dlg._saved_combo
    i = combo.findData(key)
    assert i >= 0, key
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    qapp.processEvents()


# ---------------------------------------------------------------------------
# K39-2
# ---------------------------------------------------------------------------
def test_an_update_that_would_change_the_report_is_asked_in_its_own_words(
        tmp_path, qapp, monkeypatch):
    """The saved words were FAIL where this version works out PASS: with
    nothing changed the box says so, Create New first and the default,
    Escape Cancel; Cancel writes nothing; and Update then writes what the
    box said it would (the words change).

    MUTATION, proved to land: `_update_would_change_the_report` answers
    False (red: the headline is "Nothing was changed for the selected
    report")."""
    from workflow import measurement_messages as M
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        assert not dlg._settings_were_modified()
        page = dlg._view.toPlainText()
        before = _results_words(page)
        assert "FAIL" in before and "PASS" not in before, before
        n = len(_report_files(run))
        seen = _asked(dlg, qapp, monkeypatch, "Cancel")
        want = M.CATALOGUE[
            "M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW"].render()
        assert seen["title"] == want[0], seen
        assert seen["body"] == want[1], seen
        assert seen["buttons"] == ["Create New", "Update", "Cancel"], seen
        assert seen["default"] == "Create New" and seen["escape"] == "Cancel"
        assert len(_report_files(run)) == n, "Cancel wrote a report"
        assert dlg._view.toPlainText() == page, "Cancel redrew the page"
        # Update: the words it said would change, change
        _asked(dlg, qapp, monkeypatch, "Update")
        after = _results_words(dlg._view.toPlainText())
        assert after != before, "the box said the Update changes the report"
    finally:
        dlg.close()


def test_an_update_that_would_change_nothing_keeps_the_approved_words(
        tmp_path, qapp, monkeypatch):
    """The same window with the saved words left as they were worked out:
    an Update would print the same results, so the approved question.

    MUTATION, proved to land: `_update_would_change_the_report` answers True
    (red: the variant is shown over a report an Update would not change)."""
    from workflow import measurement_messages as M
    dlg, run, _vs = _window(tmp_path, qapp, flip=False)
    try:
        assert not dlg._settings_were_modified()
        seen = _asked(dlg, qapp, monkeypatch, "Cancel")
        assert seen["title"] == M.CATALOGUE[
            "M-REPORT-UNCHANGED-UPDATE-OR-NEW"].render()[0], seen
    finally:
        dlg.close()


def test_a_changed_setting_still_asks_the_modified_question(
        tmp_path, qapp, monkeypatch):
    """A setting moved: his own question, whatever the working would do."""
    from workflow import measurement_messages as M
    dlg, _run, _vs = _window(tmp_path, qapp)
    try:
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        seen = _asked(dlg, qapp, monkeypatch, "Cancel")
        assert seen["title"] == M.CATALOGUE[
            "M-REPORT-UPDATE-OR-NEW"].render()[0], seen
    finally:
        dlg.close()


def test_one_press_works_each_measurement_out_once(tmp_path, qapp,
                                                    monkeypatch):
    """The question and the Update ask the same working: one build per
    measurement per press, and none left cached after it.

    MUTATION, proved to land: the cache in `_worked_out_again` is not
    consulted (red: two builds for one measurement)."""
    import workflow.measurement_report as mr
    dlg, _run, _vs = _window(tmp_path, qapp)
    try:
        calls = []
        real = mr.build_report

        def _count(ti3, *a, **k):
            calls.append(str(ti3))
            return real(ti3, *a, **k)
        monkeypatch.setattr(mr, "build_report", _count)
        _asked(dlg, qapp, monkeypatch, "Update")
        assert calls and len(calls) == len(set(calls)), calls
        assert dlg._press_cache is None
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# K39-3
# ---------------------------------------------------------------------------
def _new_report_line():
    from workflow import measurement_messages as M
    return "⚠ " + M.M_REPORT_NEW_REPORT_SETTINGS.render()[1]


def _defaults(dlg):
    return (dlg._report_type_now(), dlg._report_limits().set_id,
            dlg._detail_check.isChecked())


def test_new_report_keeps_the_page_loads_the_defaults_and_says_so(
        tmp_path, qapp, monkeypatch):
    """Chosen with the mouse: the page and its PDF stay the report shown,
    the controls hold the new report's defaults, the red line says
    M-REPORT-NEW-REPORT-SETTINGS, Delete is greyed; Generate then draws the
    new report and the line goes.

    MUTATIONS, each proved to land: `_on_saved_chosen` calls
    `_start_new_report()` without *chosen* (red: the page is redrawn);
    `_show_stale_banner` ignores `_new_report_pending` (red: no line with
    the settings unchanged)."""
    import ui.dialogs.measurement_report_dialog as mrd
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        old_key = dlg._loaded_doc_id
        page = dlg._view.toPlainText()
        words = _results_words(page)
        # a setting of the report shown, moved away from the default
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        assert dlg._view.toPlainText() == page, "New report… redrew the page"
        assert dlg._loaded_doc_id == mrd.NEW_REPORT_KEY
        want = dlg._defaults_document()
        assert dlg._detail_check.isChecked() == bool(want["detail"])
        assert dlg._stale_label.isVisible()
        assert dlg._stale_label.text() == _new_report_line()
        assert not dlg._delete_report_btn.isEnabled()
        # the line is up "whatever the settings are": with the controls
        # exactly what the page was drawn with, it still is
        dlg._doc_built_with = dlg._doc_settings()
        dlg._page_covers = dlg._coverage_now()
        assert not dlg._settings_were_modified()
        dlg._show_stale_banner()
        assert dlg._stale_label.isVisible(), (
            "after New report… the red line depends on a changed setting")
        # the PDF is the report on the page
        pdf = _results_words(_pdf_text(dlg, qapp, tmp_path, "pending"))
        assert pdf == words, {"page": words, "pdf": pdf}
        # Generate: a new report, drawn
        n = len(_report_files(run))
        dlg._generate_btn.click()
        qapp.processEvents()
        assert len(_report_files(run)) == n + 1, "no new report was written"
        assert dlg._loaded_doc_id not in (mrd.NEW_REPORT_KEY, old_key)
        assert dlg._view.toPlainText() != page, "the new report is not shown"
        assert not dlg._stale_label.isVisible()
    finally:
        dlg.close()


def test_choosing_the_previous_report_again_brings_back_its_own_settings(
        tmp_path, qapp):
    """After "New report…" and a changed setting, the previous report chosen
    again reloads as any report does: its own settings, no red line, its
    page.

    MUTATION, proved to land: `_render` does not clear the pending flag
    (red: the red line stays up over the reloaded report)."""
    import ui.dialogs.measurement_report_dialog as mrd
    dlg, _run, _vs = _window(tmp_path, qapp)
    try:
        old_key = dlg._loaded_doc_id
        page = dlg._view.toPlainText()
        settings = dlg._doc_settings()
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._stale_label.text() == _new_report_line()
        _pick(dlg, qapp, old_key)
        assert dlg._loaded_doc_id == old_key
        assert dlg._doc_settings() == settings
        assert not dlg._stale_label.isVisible()
        assert dlg._view.toPlainText() == page
    finally:
        dlg.close()


def test_new_report_chosen_from_the_keyboard_is_the_same(tmp_path, qapp):
    """Up arrow on the closed "Report shown" moves to "New report…" the way
    a reader does it: the same state as a click.

    MUTATION, proved to land: as the first test's (the page is redrawn)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    import ui.dialogs.measurement_report_dialog as mrd
    dlg, _run, _vs = _window(tmp_path, qapp)
    try:
        page = dlg._view.toPlainText()
        combo = dlg._saved_combo
        combo.setFocus()
        for _ in range(combo.count()):
            if combo.currentData() == mrd.NEW_REPORT_KEY:
                break
            QTest.keyClick(combo, Qt.Key.Key_Up)
            qapp.processEvents()
        assert combo.currentData() == mrd.NEW_REPORT_KEY
        assert dlg._loaded_doc_id == mrd.NEW_REPORT_KEY
        assert dlg._view.toPlainText() == page
        assert dlg._stale_label.text() == _new_report_line()
    finally:
        dlg.close()


def test_delete_right_after_new_report_deletes_nothing(tmp_path, qapp,
                                                       monkeypatch):
    """"New report…" is not a report: Delete is greyed, and a press that
    reaches the handler moves no file and keeps the page."""
    import ui.dialogs.measurement_report_dialog as mrd
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        page = dlg._view.toPlainText()
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        files = _report_files(run)
        assert not dlg._delete_report_btn.isEnabled()
        monkeypatch.setattr(mrd.MeasurementReportDialog, "_confirm",
                            lambda self, *a, **k: True)
        dlg._on_delete_report()
        qapp.processEvents()
        assert _report_files(run) == files
        assert dlg._view.toPlainText() == page
    finally:
        dlg.close()


def test_the_first_page_and_an_empty_list(tmp_path, qapp):
    """A run with no saved report opens on "New report…" with its page
    drawn from the defaults and no red line (nothing was chosen); choosing
    "New report…" again over that page keeps it and says so."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=2)
    for v in vs:
        for p in (v.dir / "reports").glob("report_*.json"):
            p.unlink()
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        assert dlg._saved_combo.count() == 1
        assert dlg._loaded_doc_id == mrd.NEW_REPORT_KEY
        assert not dlg._stale_label.isVisible()
        page = dlg._view.toPlainText()
        assert len(page) > 200
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        assert dlg._view.toPlainText() == page
        assert dlg._stale_label.text() == _new_report_line()
    finally:
        dlg.close()


def test_a_calibration_window_keeps_its_page_too(tmp_path, qapp):
    """The same rule in a calibration window."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_calibration_reports import (_project_with_cal, _save,
                                                _settings)
    from tests.test_calibration_reports import _window as _cal_window
    from workflow.measurement_report import REPORT_TYPE_FULL
    p, ti3 = _project_with_cal(tmp_path, "P")
    _save([p.calibration.dir], [ti3], type_id=REPORT_TYPE_FULL)
    dlg = _cal_window(_settings(), ti3, qapp)
    try:
        assert dlg._loaded_doc_id != mrd.NEW_REPORT_KEY
        page = dlg._view.toPlainText()
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        assert dlg._view.toPlainText() == page
        assert dlg._stale_label.text() == _new_report_line()
    finally:
        dlg.close()


def test_a_delete_that_lands_on_new_report_draws(tmp_path, qapp,
                                                 monkeypatch):
    """The door a delete uses must not keep the deleted report on the page:
    only a reader's CHOICE of "New report…" keeps it."""
    import ui.dialogs.measurement_report_dialog as mrd
    dlg, _run, _vs = _window(tmp_path, qapp)
    try:
        page = dlg._view.toPlainText()
        dlg._start_new_report()
        qapp.processEvents()
        assert dlg._view.toPlainText() != page or not dlg._stale_label.isVisible()
        assert not getattr(dlg, "_new_report_pending", False)
    finally:
        dlg.close()


def test_the_pdf_after_new_report_is_the_report_shown(tmp_path, qapp):
    """While "New report…" waits for Generate, Save report as PDF… is the
    report on the page, down to what it says of ITS saved report: a report
    across three profile runs, one deleted since, keeps its Report Scope
    line (M-REPORT-SCOPE-RUN-DELETED) in the PDF.

    MUTATION, proved to land: `_as_the_document_was_built` does not put the
    page's report back (`doc_as_built` ignored; red: the line is gone from
    the PDF, because the window already holds "New report…")."""
    import core.run_delete as rd
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_calibration_reports import _settings
    from tests.test_calibration_reports import _window as _cal_window
    from tests.test_k34_knuts_section_a import (_Target,
                                                _three_runs_one_report)
    from workflow import measurement_messages as M
    proj = _three_runs_one_report(tmp_path, qapp)
    rd.delete_run(proj, rd.plan_for(proj, _Target("run2")))
    ti3 = next((proj.root / "runs" / "run1").glob("verifications/*/*.ti3"))
    dlg = _cal_window(_settings(), ti3, qapp, "verification")
    try:
        title = M.M_REPORT_SCOPE_RUN_DELETED.render(count=1, runs="x")[0]
        page = dlg._view.toPlainText()
        assert title in page, "the scene does not show the line it is about"
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        assert dlg._view.toPlainText() == page
        pdf = _pdf_text(dlg, qapp, tmp_path, "pending")
        assert title in " ".join(pdf.split()), (
            "the PDF of the report shown lost what it says of its own report")
    finally:
        dlg.close()
