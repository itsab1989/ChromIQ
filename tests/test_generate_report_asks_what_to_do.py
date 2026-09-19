"""Knut's two beta-25 rulings about a SELECTED report (B8-490, B8-491).

Both are his words, recorded verbatim at
`~/Desktop/ChromIQ-knut-beta25-batch/knuts-comment-verbatim.md`, and both
overrule something this window already did deliberately.

**RULING ONE — a selected report restores ALL of its settings.** Asked whether
opening a saved report should restore its two tick boxes as well as its type
and its limit set, which was registered as B8-432 and recorded in the code as a
deliberate B8-388 decision the other way:

    Yes. All settings that belong to a report shall be loaded. Included
    measurements added for report is ticked, Report type, Judged against, and
    "Show all measurement runs" and "Show detailed data for each run".

Five things, and before this round two of them followed a report and three did
not: both tick boxes came from Preferences at the OPEN door, and the
measurement list was re-ticked only when "Show all measurement runs" happened
to be ON.

**RULING TWO — Generate report asks what to do.**

    When a report from "Report shown" is selected, as we know, all settings are
    updated reflecting the selected reports settings when it was
    created/saved. If any of the settings are changed, a red text message will
    show user that he must click Generate Report to apply settings. When
    Generate Report is then clicked, the user must be shown a popup message …
    The window must then have three buttons: Update, Create New and Cancel. …
    This feature overrules a previous ruling that Generate Report always should
    create a new report.

…and, in the same breath, the half of the naming rule that moves no file:

    when a report created the first time the trailing " - saved <date> <time>"
    should not be added (created time stamp already part of the beginning of
    the name).

**WHAT IS NOT HERE, AND IS NOT BUILT.** His ruling about WHICH FOLDER a report
lives in, the `report_profiling` / `report_verification` tags, what each run
type offers in "Report type", and Delete moving a report to
`reports/old/date_ReportId` is held: it moves files a user already has and four
questions about it are unanswered. Nothing in this file half-builds it. The one
place the two touch is the NAME, and only its leading creation stamp is built
here; the run-number prefix his held section asks for is B8-492.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures and helpers
# ---------------------------------------------------------------------------
def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def _entries(dlg):
    """(label, key) for every REPORT in the pulldown — "New report…" is row 0."""
    return [(dlg._saved_combo.itemText(i), str(dlg._saved_combo.itemData(i)))
            for i in range(1, dlg._saved_combo.count())]


def _pick_key(dlg, key, qapp):
    for i in range(dlg._saved_combo.count()):
        if str(dlg._saved_combo.itemData(i)) == key:
            dlg._saved_combo.setCurrentIndex(i)
            qapp.processEvents()
            return
    raise AssertionError(f"{key!r} is not in the list: {_entries(dlg)!r}")


def _new_report(dlg, qapp):
    dlg._saved_combo.setCurrentIndex(0)
    qapp.processEvents()


def _move_the_set(dlg, qapp, set_id):
    """Choose a limit set in "Judged against", the way a user does.

    Binding a run to a set asks first, and that question is `_confirm`, which
    exists as one method so a driver can answer it. Answered yes, which is what
    a user who moved the pulldown means.
    """
    dlg._confirm = lambda title, text: True
    # **AND A REFUSAL MUST NOT BE SILENT.** This door refuses when the run has
    # moved since the window last drew itself, and pressing Generate is exactly
    # such a move, so a test that simply selects and carries on would go on
    # against the old set and prove nothing. The window is redrawn first, which
    # is what re-stamps `_run_state_at_sync`, and every refusal this door has
    # is made to raise rather than pop a box.
    dlg._refresh()
    qapp.processEvents()
    for name in ("_say_run_moved_while_asking",
                 "_say_preferences_changed_meanwhile",
                 "_say_locked_before_the_set_changed"):
        setattr(dlg, name, lambda *a, _n=name, **k: (_ for _ in ()).throw(
            AssertionError(f"the set change was refused: {_n}")))
    for i in range(dlg._set_combo.count()):
        if str(dlg._set_combo.itemData(i)) == set_id:
            dlg._set_combo.setCurrentIndex(i)
            dlg._on_set_chosen(i)
            qapp.processEvents()
            shown = (dlg._document_limits() or dlg._sticky_limits()
                     or dlg._window_limits())
            assert shown.set_id == set_id, (
                f"the window is still judging against {shown.set_id!r}")
            return
    raise AssertionError(f"{set_id} is not selectable")


def _files(run):
    """Every saved report file of the run and of its dated verifications."""
    out = [p for p in (run.dir / "reports").glob("report_*.json")]
    for v in run.verifications():
        out += list((v.dir / "reports").glob("report_*.json"))
    return sorted(out)


def _press(box_label):
    """A `QMessageBox.exec` that presses the BUTTON WITH THAT LABEL.

    **NOT `exec = lambda self: 1`.** That answers "Accepted" with no button
    chosen, so `clickedButton()` is None and the window reads Cancel whatever
    the test meant; CLAUDE.md records two whole runs lost to it. This clicks a
    real button, which is what sets `clickedButton()`.
    """
    def _exec(self):
        for b in self.buttons():
            if b.text().replace("&", "") == box_label:
                b.click()
                return 0
        raise AssertionError(
            f"no button labelled {box_label!r}: "
            f"{[b.text() for b in self.buttons()]!r}")
    return _exec


@pytest.fixture
def two_dates(tmp_path):
    """A run with two dated verifications and four pre-#182 saved reports.

    Deliberately the untidy shape `test_a_generated_report_is_one_document`
    built for B8-383: every file records a verdict and none records a document,
    which is every project on every user's disk today.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    return _messy_project(tmp_path, dates=2)


def _a_real_document(dlg, qapp, *, type_id, all_runs, detail):
    """Press Generate once, from "New report…", with those settings on screen.

    Returns the document's key. Starting from "New report…" is what a user does
    and is also what keeps the fixture honest: a window that opens on a saved
    report now brings that report's measurement ticks with it (B8-490), so a
    press made without this would cover whatever the last report covered.
    """
    _new_report(dlg, qapp)
    dlg._say_generated = lambda saved, failed: None
    dlg._all_runs_check.setChecked(all_runs)
    dlg._detail_check.setChecked(detail)
    qapp.processEvents()
    dlg._sync_type_combo_to(type_id)
    dlg._on_type_chosen(dlg._type_combo.currentIndex())
    qapp.processEvents()
    dlg._ask_update_or_create_new = lambda: "new"
    dlg._on_generate_report()
    qapp.processEvents()
    key = dlg._loaded_doc_id
    assert key.startswith("id:"), key
    return key


# ---------------------------------------------------------------------------
# RULING ONE — all five settings come back
# ---------------------------------------------------------------------------
def test_a_selected_report_restores_all_five_of_its_settings(two_dates, qapp):
    """His sentence, item by item, on a document that records every one.

    MUTATION, proved to land: delete the `_restore_the_documents_view` call
    from `_apply_document`.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        wide = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                                all_runs=True, detail=True)
        narrow = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_GREY,
                                  all_runs=False, detail=False)
        assert wide != narrow

        _pick_key(dlg, wide, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
        assert dlg._all_runs_check.isChecked() is True
        assert dlg._detail_check.isChecked() is True

        _pick_key(dlg, narrow, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_GREY, (
            "the report TYPE did not come back")
        assert dlg._all_runs_check.isChecked() is False, (
            "“Show all measurement runs” did not come back")
        assert dlg._detail_check.isChecked() is False, (
            "“Show detailed data for each run” did not come back")

        # …and back again, so this is a restore and not a one-way drift
        _pick_key(dlg, wide, qapp)
        assert (dlg._report_type_now(), dlg._all_runs_check.isChecked(),
                dlg._detail_check.isChecked()) == (REPORT_TYPE_RECORD,
                                                   True, True)
    finally:
        dlg.close()


def test_the_included_measurements_list_is_reticked_to_the_reports_own_set(
        two_dates, qapp):
    """*"Included measurements added for report is ticked"* — and it no longer
    waits for "Show all measurement runs" to be on.

    The document below covers ONE of the run's two measurements and was made
    with that box OFF, which is the case `_apply_document` used to answer by
    clearing every tick.

    MUTATION, proved to land: put `if doc.get("all_runs") and keys:` back in
    front of the `_hidden_runs` line in `_restore_the_documents_view`.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        one = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_GREY,
                               all_runs=False, detail=False)
        doc = next(d["doc"] for d in dlg._saved_documents(dlg._run_ctx.run)
                   if d["key"] == one)
        covered = {str(m.get("key") or "") for m in doc["measurements"]}
        loaded = {dlg._run_key(r) for r in dlg._history}
        assert len(loaded) == 2, f"the fixture loaded {len(loaded)} rows"
        assert len(covered) == 1, (
            "this document covers every loaded measurement, so an untick "
            "cannot be seen: %r" % (covered,))

        # something else is selected, and every row is ticked
        _new_report(dlg, qapp)
        assert dlg._hidden_runs == set()

        _pick_key(dlg, one, qapp)
        assert dlg._hidden_runs == loaded - covered, (
            "the list was not re-ticked to the report's own measurements: "
            f"hidden={dlg._hidden_runs!r} covered={covered!r}")
    finally:
        dlg.close()


def test_opening_the_window_restores_the_tick_boxes_of_a_pre_182_report(
        two_dates, qapp):
    """B8-432, which is the question he was answering.

    Every report in this fixture was written before the document record
    existed, so none records a tick box. K.5 says what such a report is: one
    dated verification, no per-run breakdown. Before this round both boxes came
    from Preferences at this door, so a window opened on a ONE-DATE report
    saying "2 verification runs".

    MUTATION, proved to land: delete the `_restore_the_documents_view` call
    from `_adopt_visible_document`.
    """
    s, _fm, _run, vs = two_dates
    s.set("report_default_show_all_runs", True)
    s.set("report_default_show_details", True)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id.startswith("file:"), (
            "the window did not open on a report that records no document, "
            f"so this proves nothing: {dlg._loaded_doc_id!r}")
        assert dlg._all_runs_check.isChecked() is False, (
            "“Show all measurement runs” came from Preferences, not from the "
            "one-date report the window is showing")
        assert dlg._detail_check.isChecked() is False, (
            "“Show detailed data for each run” came from Preferences")
    finally:
        dlg.close()


def test_a_report_that_records_no_measurements_leaves_the_rows_alone(
        two_dates, qapp):
    """THE ONE NARROWING, and it is deliberate.

    A pre-#182 report lists no measurements; `_settings_of_one_saved_report`
    INFERS that it is about the one it was filed beside. That inference decides
    two tick boxes, which are a view. It must not untick rows, which is a
    filter that survives the view: every project made before this beta would
    open with its history narrowed to one sheet and "Show all measurement runs"
    would have one run to show.

    MUTATION, proved to land: drop the `if not recorded: return` guard from
    `_restore_the_documents_view`.
    """
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id.startswith("file:"), dlg._loaded_doc_id
        assert len({dlg._run_key(r) for r in dlg._history}) == 2
        assert dlg._hidden_runs == set(), (
            "a report that records no measurement list unticked rows anyway: "
            f"{dlg._hidden_runs!r}")
        # and the whole history is still reachable from here
        dlg._all_runs_check.setChecked(True)
        qapp.processEvents()
        assert len(dlg._runs_for_report()) == 2, (
            "“Show all measurement runs” has nothing left to show")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# RULING ONE (naming) — no trailing "saved", the creation stamp leads
# ---------------------------------------------------------------------------
def test_a_report_created_the_first_time_carries_no_trailing_saved_stamp(
        two_dates, qapp):
    """*"when a report created the first time the trailing ' - saved <date>
    <time>' should not be added (created time stamp already part of the
    beginning of the name)"*.

    His parenthesis is a premise, and it was false: a document's name began
    with its report TYPE. Both halves are checked, because dropping the
    trailing stamp without moving it to the front would have left fifty reports
    of one measurement drawing the identical line.

    MUTATION, proved to land: put `bits.append(tr("saved {when}")…)` back at
    the end of `_document_label` (the stamp then appears twice, and the name
    ends with "saved"); or delete the leading `bits.append(made)` (the name
    then carries no creation stamp at all).
    """
    import re
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        label = next(lab for lab, k in _entries(dlg) if k == key)
        assert "saved" not in label, (
            f"a report created the first time still says “saved”: {label!r}")
        lead = re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", label)
        assert lead, (
            "the creation stamp is not at the beginning of the name, so "
            f"dropping the trailing one loses it: {label!r}")
        doc = next(d["doc"] for d in dlg._saved_documents(dlg._run_ctx.run)
                   if d["key"] == key)
        assert lead.group(0) == str(doc["created"]).replace("T", " ")[:19], (
            "the stamp at the front of the name is not the document's own "
            f"creation time: {label!r} vs {doc['created']!r}")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# RULING TWO — the question
# ---------------------------------------------------------------------------
def test_the_question_is_the_catalogue_message_with_his_three_buttons(
        two_dates, qapp, monkeypatch):
    """The words are M-REPORT-UPDATE-OR-NEW and the buttons are his three.

    MUTATION, proved to land: rename either button, or build the box from a
    sentence of its own instead of the catalogue.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        seen: "dict[str, object]" = {}

        def _look(self):
            seen["title"] = self.text()
            seen["body"] = self.informativeText()
            seen["buttons"] = [b.text().replace("&", "") for b in self.buttons()]
            for b in self.buttons():
                if b.text().replace("&", "") == "Cancel":
                    b.click()
                    return 0
            raise AssertionError(seen["buttons"])

        monkeypatch.setattr(QMessageBox, "exec", _look)
        assert dlg._ask_update_or_create_new() == "cancel"
        title, body = M.CATALOGUE["M-REPORT-UPDATE-OR-NEW"].render()
        assert seen["title"] == title
        assert seen["body"] == body
        assert seen["buttons"] == ["Update", "Create New", "Cancel"], seen
        assert M.CATALOGUE["M-REPORT-UPDATE-OR-NEW"].approved is False, (
            "the wording has not been approved, so it must be marked proposed")
    finally:
        dlg.close()


def test_the_question_is_asked_only_when_both_halves_of_his_sentence_hold(
        two_dates, qapp):
    """*"When a report … is selected … If any of the settings are changed"*.

    Three states, one of which asks: "New report…" never does, a selected
    report whose settings have not moved never does, and a selected report
    whose settings have moved always does.

    MUTATION, proved to land: drop the `_settings_were_modified()` test from
    `_document_being_updated`, and the second case starts asking.

    **AND ONE MUTATION THAT DOES NOT LAND, SAID OUT LOUD.** Dropping the
    `key == NEW_REPORT_KEY` test leaves this green, because "New report…" names
    no entry in `_saved_documents` either and the lookup below it already
    returns None. The line stays as the explicit statement of the rule, but it
    is not what this check can see.
    """
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        assert dlg._document_being_updated() is None, (
            "nothing has moved, so there is nothing to ask about")
        assert not dlg._stale_label.isVisible()

        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._stale_label.isVisible(), (
            "the red line is the other half of the same predicate")
        entry = dlg._document_being_updated()
        assert entry is not None and entry["key"] == key

        _new_report(dlg, qapp)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._document_being_updated() is None, (
            "“New report…” is not a report and cannot be updated")
    finally:
        dlg.close()


def test_cancel_aborts_the_generate_report_function(two_dates, qapp,
                                                    monkeypatch):
    """*"Cancel aborts the Generate Report function."* Nothing is written,
    nothing is renamed, and nothing on screen moves.

    MUTATION, proved to land: make `_on_generate_report` fall through to
    `_write_the_document` on "cancel".
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        before = {p: p.read_bytes() for p in _files(run)}
        n_entries = len(_entries(dlg))
        dlg._detail_check.setChecked(False)
        qapp.processEvents()

        del dlg._ask_update_or_create_new       # the real one, answered Cancel
        monkeypatch.setattr(QMessageBox, "exec", _press("Cancel"))
        dlg._on_generate_report()
        qapp.processEvents()

        after = {p: p.read_bytes() for p in _files(run)}
        assert set(after) == set(before), "Cancel added or removed a file"
        assert after == before, "Cancel rewrote a file"
        assert len(_entries(dlg)) == n_entries
        assert dlg._loaded_doc_id == key
    finally:
        dlg.close()


def test_create_new_writes_a_new_report_and_leaves_the_selected_one_alone(
        two_dates, qapp, monkeypatch):
    """*"'Create New' button will perform the same function as if 'New
    report…' option is selected … A new report will be created."*

    MUTATION, proved to land: make `_on_generate_report` keep `updating` when
    the answer is "new".
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        before = {p: p.read_bytes() for p in _files(run)}
        n_entries = len(_entries(dlg))
        dlg._detail_check.setChecked(False)
        qapp.processEvents()

        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Create New"))
        dlg._on_generate_report()
        qapp.processEvents()

        assert len(_entries(dlg)) == n_entries + 1, (
            "“Create New” did not create a report")
        assert dlg._loaded_doc_id != key, "the window stayed on the old report"
        for p, raw in before.items():
            assert p.read_bytes() == raw, (
                f"“Create New” rewrote the selected report's file {p.name}")
    finally:
        dlg.close()


def test_update_keeps_the_selected_report_and_recalculates_it(
        two_dates, qapp, monkeypatch):
    """*"Update button will keep the current selected report, then append on
    the ending of the report name ' - updated <date> <time>', then recalculate
    and update the report text according to the new settings."*

    Four things, all of them checked: the list does not grow, the document keeps
    its id and its creation stamp, the file it was made of is the file that is
    rewritten (no second live report of one date), and the settings on disk are
    the new ones.

    MUTATION, proved to land: make `_write_the_document` call `save_report`
    unconditionally (the list grows by one and the old file is untouched); or
    drop `updated=updated` from the `stamp_document` call (the name gains no
    stamp).
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        created = str(entry["doc"]["created"])
        mine = {(Path(str(r.get("_origin_dir"))) / "reports" / n)
                for r, n in entry["members"]}
        n_files = len(_files(run))
        n_entries = len(_entries(dlg))

        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()

        assert len(_files(run)) == n_files, (
            "Update wrote a file instead of updating the one it had")
        assert len(_entries(dlg)) == n_entries, (
            "Update added an entry to the list")
        assert dlg._loaded_doc_id == key, (
            "the window left the report it was told to update")
        for path in mine:
            doc = json.loads(path.read_text(encoding="utf-8"))["document"]
            assert doc["id"] == key.split(":", 1)[1]
            assert str(doc["created"]) == created, (
                "Update moved the report's creation time")
            assert doc["detail"] is False, (
                "the new settings were not written to the report")
            assert doc.get("updated"), "the press was not recorded"
        label = next(lab for lab, k in _entries(dlg) if k == key)
        assert "updated" in label, (
            f"the name does not say it was updated: {label!r}")
        assert label.startswith(created.replace("T", " ")[:19]), (
            f"the name no longer leads with its creation time: {label!r}")
    finally:
        dlg.close()


def test_a_second_update_replaces_the_first_stamp_in_the_name(
        two_dates, qapp, monkeypatch):
    """THE DEFAULT TAKEN WHERE HE HAS NOT RULED, and it is a default on
    purpose.

    He said Update appends *" - updated <date> <time>"* and did not say what a
    SECOND update does. The question is open with him; the answer built here is
    **replace**, so a name says when the report was created and when it was
    last updated and nothing else. Every stamp is kept on DISK, in order, so
    `NAME_SHOWS_EVERY_UPDATE = True` shows the whole history and nothing has to
    be recovered from anywhere.

    MUTATION, proved to land: flip `NAME_SHOWS_EVERY_UPDATE` to True.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        for want in (False, True):
            dlg._detail_check.setChecked(want)
            qapp.processEvents()
            dlg._on_generate_report()
            qapp.processEvents()

        label = next(lab for lab, k in _entries(dlg) if k == key)
        assert label.count("updated") == 1, (
            f"two updates put two stamps in the name: {label!r}")
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        stamps = entry["doc"]["updated"]
        assert len(stamps) == 2, (
            f"the second press was not recorded on disk: {stamps!r}")
        assert label.endswith(str(stamps[-1]).replace("T", " ")[:19]), (
            "the name shows an update that is not the latest one")
    finally:
        dlg.close()


def test_update_writes_the_same_kind_of_document_create_new_writes(
        tmp_path, qapp, monkeypatch):
    """*"The same function is used as when 'New report…' option is selected
    then Generate Report clicked, but is instead updating the selected
    report."*

    So the two answers may differ in WHERE the bytes go and in the id, created
    and updated fields, and in nothing else.

    MUTATION, proved to land: make the Update branch skip `stamp_verdict`.

    **ONE DATE, NOT TWO, AND THAT IS NOT A CONVENIENCE.** §5 locks a run's
    limit set once it has a second dated verification, so the pulldown this
    check has to move is dead on the shared fixture — and the window says so
    rather than moving quietly, which is the right behaviour and is what the
    refusal guard in `_move_the_set` measures.
    """
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_a_generated_report_is_one_document import _messy_project
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    s, _fm, run, vs = _messy_project(tmp_path, dates=1)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    moving = {"id", "created", "updated"}
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        subject = sorted(Path(str(r.get("_origin_dir"))) / "reports" / n
                         for r, n in entry["members"])[0]

        # **THE LIMIT SET MOVES TOO, AND THAT IS WHAT MAKES THIS MEAN
        # ANYTHING.** With the set unchanged, a file that was never re-judged
        # still carries the right verdict, so an Update that skipped
        # `stamp_verdict` altogether would pass — measured, and it did. The
        # yardstick is what a verdict is against, so moving it is the one
        # change that can tell "recalculated" from "left alone".
        _move_the_set(dlg, qapp, "chromiq_tight")
        dlg._sync_type_combo_to(REPORT_TYPE_GREY)
        dlg._on_type_chosen(dlg._type_combo.currentIndex())
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        updated = json.loads(subject.read_text(encoding="utf-8"))
        assert (updated.get("compliance") or {}).get("set_id") == \
            "chromiq_tight", (
                "Update did not write the limit set the window was showing: "
                f"{(updated.get('compliance') or {}).get('set_id')!r}")

        # the same settings again, as a NEW report
        fresh = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_GREY,
                                 all_runs=True, detail=False)
        entry2 = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                      if d["key"] == fresh)
        twin = next(Path(str(r.get("_origin_dir"))) / "reports" / n
                    for r, n in entry2["members"]
                    if Path(str(r.get("_origin_dir"))) == subject.parent.parent)
        created_new = json.loads(twin.read_text(encoding="utf-8"))

        a = {k: v for k, v in updated["document"].items() if k not in moving}
        b = {k: v for k, v in created_new["document"].items()
             if k not in moving}
        assert a == b, (
            "Update and Create New wrote different documents from one set of "
            f"settings:\n  update: {a}\n  create: {b}")
        assert updated.get("verdict") == created_new.get("verdict"), (
            "Update did not re-judge the sheet the way Create New does")
    finally:
        dlg.close()


def test_update_never_leaves_two_live_reports_of_one_date(two_dates, qapp,
                                                          monkeypatch):
    """The rule `rewrite_report` exists for (CH-29), applied here.

    §5 keeps one saved report per dated verification comparable across dates.
    An Update that wrote a new file would leave that date with two, and the
    older one would go on being read as a separate entry of the list.

    MUTATION, proved to land: replace `rewrite_report(here, rep)` with
    `save_report(rep, Path(origin))`.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        before = {str(p) for p in _files(run)}
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        for want in (False, True, False):
            dlg._detail_check.setChecked(want)
            qapp.processEvents()
            dlg._on_generate_report()
            qapp.processEvents()
        assert {str(p) for p in _files(run)} == before, (
            "three updates left new files on disk: "
            f"{sorted({str(p) for p in _files(run)} - before)!r}")
    finally:
        dlg.close()


def test_a_member_the_update_drops_still_agrees_with_its_document(
        two_dates, qapp, monkeypatch):
    """Untick a measurement, press Update, and ONE document still says one
    thing about itself.

    An Update may narrow what the document covers, and its file for the
    measurement that left is still on disk carrying this document's id.
    `_saved_documents` reads the block off whichever member it sees first, so a
    leftover holding the OLD block makes the entry's settings depend on which
    file the run happened to yield first. Nothing is deleted: the file keeps
    its own verdict, which is a fact about that sheet, and gains the block the
    document now has.

    MUTATION, proved to land: make `_write_the_document` skip the loop over the
    leftover members.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               all_runs=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        assert len(entry["members"]) == 2, (
            "the document covers one measurement, so nothing can be dropped "
            "from it: %r" % (entry["members"],))
        files = {dlg._run_key(r): Path(str(r.get("_origin_dir"))) / "reports" / n
                 for r, n in entry["members"]}

        dropped = dlg._run_key(dlg._history[0])
        dlg._hidden_runs.add(dropped)
        dlg._settings_touched()
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()

        blocks = {k: json.loads(p.read_text(encoding="utf-8"))["document"]
                  for k, p in files.items()}
        assert len({json.dumps(b, sort_keys=True) for b in blocks.values()}) == 1, (
            "the two files of one document disagree about what it is:\n"
            + "\n".join(f"  {k}: {b}" for k, b in blocks.items()))
        covered = {str(m.get("key") or "")
                   for m in blocks[dropped]["measurements"]}
        assert dropped not in covered, (
            "the measurement that was unticked is still in the document")
        assert len(_files(run)) == len(files) + 4, (
            "Update wrote a file where it should have rewritten one")
    finally:
        dlg.close()
