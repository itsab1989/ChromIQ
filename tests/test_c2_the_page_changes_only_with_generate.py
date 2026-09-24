"""The report page changes only when a user makes it change (challenge 2 of
beta 42, #1; Knut, #182 5815133233 and 5816794672; register B8-1001).

Knut, 5816794672, on the paths §28.10 had left redrawing at once:

    *"Remove Profile's Measurements, Clear List, re-adding a file that
    changed on disk, these should all result in the red warning text
    appearing that settings have changed, and never automatically change a
    report."*

    *"Changing the settings while Generate Report is greyed out and it is not
    allowed or possible to generate a report, then it makes no sense to allow
    changing settings. The report text should never automatically be updated
    in any situation, as a report is a record of history and shall never we
    changed unless deliberately done by a user."*

The fault the challenge drove on screen (Report-Limits-Evenness run 4,
Verification): the project's own profiling sheet added (unticked) greyed
Generate as "mixed kinds"; "Judged against" then redrew the page at once and
re-stamped it as built with ChromIQ tight; removing the sheet left no red
line, and Generate asked "Nothing was changed for the selected report" and
Update rewrote the saved report under ChromIQ tight.

Each test is measured on the window's own page text, red line and buttons.
The same states are photographed on screen by
`scripts/drive_b42_c2_fixes.py` (scene "rewrite").
"""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _ticks(dlg):
    from PyQt6.QtCore import Qt
    return {key: dlg._profile_list.item(i).checkState() == Qt.CheckState.Checked
            for i, (kind, _si, key) in enumerate(dlg._list_rows)
            if kind == "run" and key}


def _window(tmp_path, qapp, *, sheet=True):
    """A verification window on a saved report of run 1, and (when *sheet*)
    run 1's own profiling sheet on disk beside it."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_import_measurement_module import _cgats, _PATCHES
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    if sheet:
        run.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    assert dlg._loaded_doc_id != mrd.NEW_REPORT_KEY, (
        "the window must open on a saved report for these tests")
    return dlg, run, vs


def _add(dlg, qapp, monkeypatch, path):
    import ui.dialogs.measurement_report_dialog as mrd
    monkeypatch.setattr(mrd, "open_files_dialog",
                        lambda *a, **k: [str(path)])
    dlg._on_add_project()
    qapp.processEvents()


def _choose_set(dlg, qapp, set_id):
    idx = dlg._set_combo.findData(set_id)
    assert idx >= 0, set_id
    dlg._set_combo.setCurrentIndex(idx)
    dlg._on_set_chosen(idx)
    qapp.processEvents()


def _other_set(dlg):
    now = dlg._set_combo.currentData()
    return next(dlg._set_combo.itemData(i)
                for i in range(dlg._set_combo.count())
                if dlg._set_combo.itemData(i) not in (now, None, ""))


def test_the_challenge_path_keeps_the_page_and_asks_honestly(
        tmp_path, qapp, monkeypatch):
    """The challenge's own steps, end to end.

    MUTATIONS, each proved to land: count unticked rows in
    `_kinds_are_mixed` (Generate greys on the add); let `_render` draw and
    re-stamp inside `_keeping_the_page` (red in four of this file's six
    tests). The question's own lock is `test_the_question_asks_the_saved_
    report_not_only_the_page`."""
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        page = dlg._view.toPlainText()
        assert dlg._generate_btn.isEnabled()
        before = _ticks(dlg)
        _add(dlg, qapp, monkeypatch, run.measurement_ti3)
        new = set(_ticks(dlg)) - set(before)
        assert new and not any(_ticks(dlg)[k] for k in new), (
            "the sheet must come in unticked (B8-990)")
        # (c) an UNTICKED sheet of the other kind does not grey Generate
        assert dlg._generate_btn.isEnabled(), (
            "an unticked profiling sheet counted as a mixed kind: "
            + dlg._generate_btn.toolTip())
        assert dlg._view.toPlainText() == page
        # (a) a setting change keeps the page and raises the red line
        other = _other_set(dlg)
        _choose_set(dlg, qapp, other)
        assert dlg._view.toPlainText() == page, (
            "the page was redrawn without Generate")
        assert dlg._stale_label.isVisible()
        # Remove the added sheet: still the page, still the line
        row = next(i for i, (kind, si, _k) in enumerate(dlg._list_rows)
                   if kind == "source" and si > 0)
        dlg._profile_list.setCurrentRow(row)
        dlg._on_remove_profile()
        qapp.processEvents()
        assert dlg._view.toPlainText() == page
        assert dlg._stale_label.isVisible(), (
            "the set on screen is not the saved report's, and no line says so")
        # (b) the question says the settings were modified
        seen = {}

        def _look(box):
            seen["title"] = box.text()
            for b in box.buttons():
                if b.text().replace("&", "") == "Cancel":
                    b.click()
                    return 0
            raise AssertionError("no Cancel")
        monkeypatch.setattr(QMessageBox, "exec", _look)
        assert dlg._ask_update_or_create_new() == "cancel"
        assert seen["title"] == M.CATALOGUE[
            "M-REPORT-UPDATE-OR-NEW"].render()[0], seen
    finally:
        dlg.close()


def test_the_question_asks_the_saved_report_not_only_the_page(
        tmp_path, qapp, monkeypatch):
    """The second lock: even a page that had been re-stamped with the new
    set (the old fault) may not make the question say "Nothing was changed"
    while the set differs from the SAVED report's.

    MUTATION, proved to land: drop `_differs_from_the_saved_report` from the
    question's `modified`."""
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    dlg, _run, _vs = _window(tmp_path, qapp, sheet=False)
    try:
        _choose_set(dlg, qapp, _other_set(dlg))
        # what the old `_render` did: take the controls as the page's own
        dlg._doc_built_with = dlg._doc_settings()
        dlg._page_covers = dlg._coverage_now()
        assert not dlg._settings_were_modified()
        seen = {}

        def _look(box):
            seen["title"] = box.text()
            for b in box.buttons():
                if b.text().replace("&", "") == "Cancel":
                    b.click()
                    return 0
            raise AssertionError("no Cancel")
        monkeypatch.setattr(QMessageBox, "exec", _look)
        dlg._ask_update_or_create_new()
        assert seen["title"] != M.CATALOGUE[
            "M-REPORT-UNCHANGED-UPDATE-OR-NEW"].render()[0], (
            "'Nothing was changed' over a set that is not the saved one")
    finally:
        dlg.close()


def test_with_generate_greyed_the_page_stays_and_the_settings_wait(
        tmp_path, qapp, monkeypatch):
    """The sheet TICKED beside the verifications: Generate is greyed (FC-2,
    a press would write one type into both kinds of folder). Knut: the
    settings that cannot help are greyed too, and nothing redraws the page.

    MUTATIONS, each proved to land: drop `_grey_what_cannot_help` (the
    pulldowns stay live); let `_settings_touched` redraw while Generate is
    greyed (the page changes)."""
    from PyQt6.QtCore import Qt
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        page = dlg._view.toPlainText()
        before = _ticks(dlg)
        _add(dlg, qapp, monkeypatch, run.measurement_ti3)
        for i, (kind, _si, key) in enumerate(dlg._list_rows):
            if kind == "run" and key not in before:
                dlg._profile_list.item(i).setCheckState(Qt.CheckState.Checked)
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled(), (
            "a ticked profiling sheet beside verifications must grey Generate")
        assert dlg._view.toPlainText() == page
        assert dlg._stale_label.isVisible(), "a tick is a changed setting"
        for w in (dlg._type_combo, dlg._set_combo, dlg._detail_check):
            assert not w.isEnabled(), (w, "is live with Generate greyed")
        # the list stays live: it is how Generate comes back
        assert dlg._profile_list.isEnabled() and dlg._remove_btn is not None
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._view.toPlainText() == page, (
            "the page was redrawn while Generate was greyed")
        # unticking the sheet brings Generate and the settings back
        for i, (kind, _si, key) in enumerate(dlg._list_rows):
            if kind == "run" and key not in before:
                dlg._profile_list.item(i).setCheckState(
                    Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert dlg._generate_btn.isEnabled()
        assert dlg._set_combo.isEnabled() and dlg._type_combo.isEnabled()
    finally:
        dlg.close()


def test_remove_keeps_the_page_and_raises_the_line(tmp_path, qapp,
                                                   monkeypatch):
    """Removing a measurement the page COVERS keeps the page and raises the
    line; removing one it does not cover (an added, unticked one) changes
    nothing at all.

    MUTATION, proved to land: `_on_remove_profile` rebuilds outside
    `_keeping_the_page` (the page is drawn again, without the removed one,
    and the line is taken down)."""
    from tests.test_a_generated_report_is_one_document import _messy_project
    dlg, _run, _vs = _window(tmp_path, qapp, sheet=False)
    _s2, _fm2, _run2, vs2 = _messy_project(tmp_path / "q", dates=1)
    try:
        page = dlg._view.toPlainText()
        _add(dlg, qapp, monkeypatch, vs2[-1].measurement_ti3)
        # the added, unticked one: removed, nothing moves
        row = next(i for i, (kind, si, _k) in enumerate(dlg._list_rows)
                   if kind == "source" and si > 0)
        dlg._profile_list.setCurrentRow(row)
        dlg._on_remove_profile()
        qapp.processEvents()
        assert dlg._view.toPlainText() == page
        assert not dlg._stale_label.isVisible(), (
            "nothing the page covers was removed")
        # the window's own measurement: the page stays, the line comes up
        _add(dlg, qapp, monkeypatch, vs2[-1].measurement_ti3)
        dlg._profile_list.clearSelection()
        dlg._profile_list.setCurrentRow(0)
        dlg._on_remove_profile()
        qapp.processEvents()
        assert dlg._view.toPlainText() == page, (
            "Remove Profile's Measurements redrew the report")
        assert dlg._stale_label.isVisible()
        # and the PDF is still of the page: its measurements are the page's
        with dlg._the_page_as_drawn():
            assert [str(s["origin"]) for s in dlg._sources] == [
                str(s["origin"]) for s in dlg._page_snapshot["sources"]]
    finally:
        dlg.close()


def test_clear_list_keeps_the_page_and_what_is_added_waits(
        tmp_path, qapp, monkeypatch):
    """Clear List empties the list, not the page; the line comes up and the
    PDF button stays live (the page is a report). Measurements added after
    it come in unticked, and the page still does not move.

    MUTATIONS, each proved to land: `_on_clear_list` rebuilds outside
    `_keeping_the_page` (the page empties); `_on_add_project` asks only
    `bool(self._sources)` (the add after the clear redraws the page)."""
    from tests.test_a_generated_report_is_one_document import _messy_project
    dlg, _run, _vs = _window(tmp_path, qapp, sheet=False)
    try:
        page = dlg._view.toPlainText()
        dlg._on_clear_list()
        qapp.processEvents()
        assert dlg._view.toPlainText() == page, "Clear List emptied the page"
        assert dlg._stale_label.isVisible()
        assert dlg._pdf_btn.isEnabled(), "the page on screen can be saved"
        assert not dlg._generate_btn.isEnabled()
        _s2, _fm2, _run2, vs2 = _messy_project(tmp_path / "q", dates=1)
        _add(dlg, qapp, monkeypatch, vs2[-1].measurement_ti3)
        assert _ticks(dlg) and not any(_ticks(dlg).values()), (
            "measurements added over a kept page must come in unticked")
        assert dlg._view.toPlainText() == page
        # ticked, they can be generated: the list has its subject again
        from PyQt6.QtCore import Qt
        for i, (kind, _si, key) in enumerate(dlg._list_rows):
            if kind == "run" and key:
                dlg._profile_list.item(i).setCheckState(Qt.CheckState.Checked)
        qapp.processEvents()
        assert dlg._report is not None
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        assert dlg._view.toPlainText() == page
    finally:
        dlg.close()


def test_a_file_changed_on_disk_and_added_again_keeps_the_page(
        tmp_path, qapp, monkeypatch):
    """The measurement the page covers is measured again in place and added
    again: the list reads it again, the page does not, and the line says the
    page no longer matches.

    MUTATIONS, each proved to land: the re-read rebuilds outside
    `_keeping_the_page` (the page is drawn from the new numbers); drop the
    disk stamp from `_coverage_now` (no line)."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, vs = _window(tmp_path, qapp, sheet=False)
    try:
        page = dlg._view.toPlainText()
        ti3 = vs[-1].measurement_ti3
        st = ti3.stat()
        ti3.write_text(_cgats("CTI3", [(r, max(0.0, g - 7.0), b)
                                       for (r, g, b) in _PATCHES]),
                       encoding="utf-8")
        os.utime(ti3, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        time.sleep(0.01)
        _add(dlg, qapp, monkeypatch, ti3)
        assert dlg._view.toPlainText() == page, (
            "a file re-read from disk redrew the report")
        assert dlg._stale_label.isVisible()
    finally:
        dlg.close()
