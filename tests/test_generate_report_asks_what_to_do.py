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

**AND THEN FIVE BECAME FOUR (B8-590, and this file is retargeted to it).**
Knut, 2026-09-20, on the same window:

    I realise now this checkbox is not a reasonable feature to have (and has
    evolved to something that it was not originally used) and should be
    removed … The feature that actually is desired here is a button "Select
    All" … and a button "Deselect All" … These two buttons then ONLY select or
    clear the selection of the listed measurements … Remove the feature "Show
    all measurement runs" totally from the design, and any feature that
    belongs to that button … only the selected/ticked measurements shall be
    part of the report when created/updated (always).

So the fifth item of his beta-25 list, and the preference behind it, are gone.
Nothing else in either ruling moved: a selected report still restores every
setting that belongs to it, and the four that are left are the report type,
the limit set, "Show detailed data for each run", and the measurement TICKS —
which are now the whole of what a report covers, and so carry the meaning the
removed box used to carry. Every check below that used to set or read that box
says the same thing about the list instead; the one whose subject was the box
itself is `test_the_box_that_was_the_fifth_setting_is_gone`.

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

    K31: the choice is the REPORT's and nothing asks or refuses any more (it
    bound the run, behind a question and three refusals, until then).
    """
    dlg._refresh()
    qapp.processEvents()
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


def _tick_every_measurement(dlg, qapp):
    """Press "Select all", which is what "the whole history" means now."""
    dlg._select_all_btn.click()
    qapp.processEvents()


def _tick_only_this_measurement(dlg, qapp):
    """Untick every row but the measurement the window was opened on.

    This is what `dlg._all_runs_check.setChecked(False)` used to mean, said in
    the vocabulary that is left: the box is gone (B8-590) and the report covers
    the ticked rows, so "one measurement" is a LIST state now, not a box state.
    Pressed through the list items, the way a user reaches it.

    **THE OTHER ROWS ARE UNTICKED ONE BY ONE, AND NOT THROUGH "Deselect
    all".** Both reach the same ticks, but the button passes through a state
    where NOTHING is ticked, and a repaint taken there re-stamps
    `_doc_built_with` from it: putting the last tick back then leaves the
    window saying the settings have moved when they are exactly where the
    document was built, and Generate asks "Update or Create New?" about a
    document nobody changed. That is a fault in its own right and is reported
    separately; it is not what these checks are about, and unticking the rows
    you do not want is what a reader does anyway.
    """
    from PyQt6.QtCore import Qt
    here = dlg._run_key(dlg._report)
    found = False
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind != "run" or key is None:
            continue
        if key == here:
            found = True
            continue
        dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    qapp.processEvents()
    assert found, f"the window's measurement has no row: {here!r}"
    assert [dlg._run_key(r) for r in dlg._runs_for_report()] == [here]


def _a_real_document(dlg, qapp, *, type_id, every_measurement, detail,
                     set_id=""):
    """Press Generate once, from "New report…", with those settings on screen.

    Returns the document's key. Starting from "New report…" is what a user does
    and is also what keeps the fixture honest: a window that opens on a saved
    report now brings that report's measurement ticks with it (B8-490), so a
    press made without this would cover whatever the last report covered.

    **`every_measurement` REPLACED `all_runs` (B8-590, Knut 2026-09-20.)** It
    used to set "Show all measurement runs", which is gone with the feature
    behind it; what it names now is the state of the LIST, which is the only
    thing that decides what a report covers: True presses "Select all", False
    leaves the window's own measurement ticked and nothing else.
    """
    _new_report(dlg, qapp)
    dlg._say_generated = lambda saved, failed: None
    if every_measurement:
        _tick_every_measurement(dlg, qapp)
    else:
        _tick_only_this_measurement(dlg, qapp)
    dlg._detail_check.setChecked(detail)
    qapp.processEvents()
    dlg._sync_type_combo_to(type_id)
    dlg._on_type_chosen(dlg._type_combo.currentIndex())
    qapp.processEvents()
    if set_id:
        # K31: "New report…" starts on the Preferences set, so a report
        # judged against another is chosen here, for this report.
        _move_the_set(dlg, qapp, set_id)
    dlg._ask_update_or_create_new = lambda: "new"
    dlg._on_generate_report()
    qapp.processEvents()
    key = dlg._loaded_doc_id
    assert key.startswith("id:"), key
    return key


# ---------------------------------------------------------------------------
# RULING ONE — all five settings come back
# ---------------------------------------------------------------------------
def test_a_selected_report_restores_all_four_of_its_settings(two_dates, qapp):
    """His sentence, item by item, on a document that records every one.

    **IT WAS FIVE AND IT IS FOUR (B8-590).** Knut, 2026-09-20, removed one of
    the five he had listed here: *"Remove the feature 'Show all measurement
    runs' totally from the design, and any feature that belongs to that
    button"*. So the box that used to be checked on both documents below is
    gone, and what is left is the type, the limit set, the detail box, and the
    measurement ticks. The ticks are the item that now carries the meaning the
    removed box used to carry, and they are asserted here in its place: the
    wide document covers both of the run's measurements, the narrow one covers
    the single sheet the window is on.

    MUTATION, proved to land: delete the `_restore_the_documents_view` call
    from `_apply_document`.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_FULL)
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        wide = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                                every_measurement=True, detail=True)
        narrow = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_GREY,
                                  every_measurement=False, detail=False)
        assert wide != narrow
        loaded = {dlg._run_key(r) for r in dlg._history}
        assert len(loaded) == 2, f"the fixture loaded {len(loaded)} rows"
        here = dlg._run_key(dlg._report)

        _pick_key(dlg, wide, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_FULL
        assert dlg._hidden_runs == set(), (
            "the document covering every measurement came back narrowed")
        assert dlg._detail_check.isChecked() is True

        _pick_key(dlg, narrow, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_GREY, (
            "the report TYPE did not come back")
        assert dlg._hidden_runs == loaded - {here}, (
            "the measurements the report was built from did not come back: "
            f"hidden={dlg._hidden_runs!r}")
        assert dlg._detail_check.isChecked() is False, (
            "“Show detailed data for each run” did not come back")

        # …and back again, so this is a restore and not a one-way drift
        _pick_key(dlg, wide, qapp)
        assert (dlg._report_type_now(), set(dlg._hidden_runs),
                dlg._detail_check.isChecked()) == (REPORT_TYPE_FULL,
                                                   set(), True)
    finally:
        dlg.close()


def test_the_box_that_was_the_fifth_setting_is_gone(two_dates, qapp):
    """**B8-590.** *"Remove the feature 'Show all measurement runs' totally
    from the design, and any feature that belongs to that button … The feature
    that actually is desired here is a button 'Select All' … and a button
    'Deselect All' … These two buttons then ONLY select or clear the selection
    of the listed measurements."* (Knut, 2026-09-20.)

    The premise of the fifth item in the ruling above is genuinely gone, so
    what is guarded here is the removal itself and the two buttons that
    replaced it. They ONLY move ticks: the report type, the limit set and the
    detail box are read before and after each press and must not have moved.

    MUTATION, proved to land: build `_all_runs_check` again, or make either
    button touch anything besides the ticks.
    """
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert getattr(dlg, "_all_runs_check", None) is None, (
            "“Show all measurement runs” is still built")
        assert dlg._select_all_btn is not None
        assert dlg._deselect_all_btn is not None
        loaded = {dlg._run_key(r) for r in dlg._history}
        assert len(loaded) == 2, f"the fixture loaded {len(loaded)} rows"

        def _everything_else():
            return (dlg._report_type_now(),
                    str(dlg._set_combo.currentData() or ""),
                    dlg._detail_check.isChecked())

        dlg._deselect_all_btn.click()
        qapp.processEvents()
        before = _everything_else()
        assert dlg._hidden_runs == loaded, (
            f"“Deselect all” left rows ticked: {dlg._hidden_runs!r}")

        dlg._select_all_btn.click()
        qapp.processEvents()
        assert dlg._hidden_runs == set(), (
            f"“Select all” left rows unticked: {dlg._hidden_runs!r}")
        assert {dlg._run_key(r) for r in dlg._runs_for_report()} == loaded, (
            "the report does not cover every measurement the list shows "
            "ticked")
        assert _everything_else() == before, (
            "a tick button moved a setting that is not a tick: "
            f"{before!r} -> {_everything_else()!r}")
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
                               every_measurement=False, detail=False)
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


def test_opening_the_window_restores_the_tick_box_of_a_pre_182_report(
        two_dates, qapp):
    """B8-432, which is the question he was answering.

    Every report in this fixture was written before the document record
    existed, so none records a tick box. K.5 says what such a report is: one
    dated verification, no per-run breakdown. Before this round both boxes came
    from Preferences at this door, so a window opened on a ONE-DATE report
    saying "2 verification runs".

    **ONE BOX, NOT TWO, SINCE B8-590.** "Show all measurement runs" and the
    preference behind it (`report_default_show_all_runs`) were removed on
    Knut's 2026-09-20 ruling, so the half of this that watched Preferences
    reach past a one-date report into that box has nothing to watch. The other
    half is unchanged and is what is left here; the list's own answer for such
    a report is the subject of
    `test_a_report_that_records_no_measurements_ticks_its_own_measurement`.

    MUTATION, proved to land: delete the `_restore_the_documents_view` call
    from `_adopt_visible_document`.
    """
    s, _fm, _run, vs = two_dates
    s.set("report_default_show_details", True)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id.startswith("file:"), (
            "the window did not open on a report that records no document, "
            f"so this proves nothing: {dlg._loaded_doc_id!r}")
        assert dlg._detail_check.isChecked() is False, (
            "“Show detailed data for each run” came from Preferences")
    finally:
        dlg.close()


def test_a_report_that_records_no_measurements_ticks_its_own_measurement(
        two_dates, qapp):
    """THE NARROWING THAT USED TO BE REFUSED, AND NOW HAPPENS (B8-596).

    A pre-#182 report lists no measurements; `_settings_of_one_saved_report`
    INFERS that it is about the one it was filed beside. This test used to pin
    the opposite of what it pins now, and the reason it did is recorded so a
    reader does not read the old rule as current: the inference was judged
    sound enough to decide two tick boxes, which are a view, and not sound
    enough to UNTICK rows, because unticking would have left "Show all
    measurement runs" with a single run to show on every project made before
    beta 22.

    That argument died with the box. Knut, 2026-09-20, on what he saw instead
    (B8-590/B8-596): *"when ever I select any of the reports in the drop down,
    the 'included measurements in report' always have all measurements ticked.
    This is wrong. … One the measurement used in the selected report shall be
    ticked."* A report now covers exactly what is ticked, so ticks that say
    something else are the report lying about itself.

    And it is not the inference that decides it: `entry["members"]` is which
    measurements the pulldown entry was gathered from on disk.

    MUTATION, proved to land: drop the `covers` branch from the `if not
    recorded:` arm of `_restore_the_documents_view`, and the window opens with
    both rows ticked again.
    """
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id.startswith("file:"), dlg._loaded_doc_id
        loaded = {dlg._run_key(r) for r in dlg._history}
        assert len(loaded) == 2
        here = dlg._run_key(dlg._report)
        assert dlg._hidden_runs == loaded - {here}, (
            "a report that records no measurement list came back covering "
            f"measurements it was not built from: hidden={dlg._hidden_runs!r}")
        assert [dlg._run_key(r) for r in dlg._runs_for_report()] == [here]
        # and the whole history is still one press away
        dlg._select_all_btn.click()
        qapp.processEvents()
        assert len(dlg._runs_for_report()) == 2, (
            "“Select all” has nothing left to show")
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
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
        # HIS message is the MODIFIED case (K4 gave the unchanged case its own
        # headline), so a setting is moved first, as his sentence requires.
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
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
    """*"When a report … is selected … If any of the settings are changed"*,
    and K4 (Knut on beta 34), which extends it: a selected report is asked
    about whether or not anything moved, because pressing Generate on it with
    nothing changed created reports in silence (four presses, 44 files).

    Three states: "New report…" never asks; a selected report asks with
    nothing moved; a selected report asks with a setting moved. Which
    HEADLINE it asks under is guarded by
    `test_the_unchanged_question_says_nothing_was_changed`.

    MUTATION, proved to land: put back the `_settings_were_modified()` early
    return in `_document_being_updated`, and the first case stops asking.

    **AND ONE MUTATION THAT DOES NOT LAND, SAID OUT LOUD.** Dropping the
    `key == NEW_REPORT_KEY` test leaves this green, because "New report…" names
    no entry in `_saved_documents` either and the lookup below it already
    returns None. The line stays as the explicit statement of the rule, but it
    is not what this check can see.
    """
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = dlg._document_being_updated()
        assert entry is not None and entry["key"] == key, (
            "K4: a selected report with nothing changed must still be asked "
            "about, or Generate creates a new report in silence")
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
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
                                             REPORT_TYPE_FULL)
    s, _fm, run, vs = _messy_project(tmp_path, dates=1)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    moving = {"id", "created", "updated"}
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
                                 every_measurement=True, detail=False,
                                 set_id="chromiq_tight")
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
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
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
    """Untick a measurement, press Update, and ONE report still says one
    thing about itself.

    K31 (no verdict records) changed what is on disk and kept the rule: the
    report of two dates is one file in `verifications/reports/`; updated to
    one date it becomes that date's own file (same id, no role), the file of
    two dates is archived into `old/` and leaves the live folder, and the
    date taken out holds nothing of this report.

    MUTATION: skip the retirement of the files the new shape no longer has
    (`retire` in `_write_the_document`), and a report of one date keeps a
    document file listed beside it: red.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL, recorded_document
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        home = sorted((run.verifications_dir / "reports").glob("report_*.json"))
        assert len(home) == 1, home
        before = set(_files(run))
        dropped = dlg._run_key(dlg._history[0])
        dlg._hidden_runs.add(dropped)
        dlg._settings_touched()
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        assert not list((run.verifications_dir / "reports").glob(
            "report_*.json")), "a report of one date kept a document file"
        assert list((run.verifications_dir / "reports" / "old").glob(
            "*/" + home[0].name)), "the file of two dates was not archived"
        mine = []
        for p in set(_files(run)) - before:
            block = recorded_document(json.loads(Path(p).read_text(encoding="utf-8")))
            if block and "id:" + block["id"] == key:
                mine.append((p, block))
        assert len(mine) == 1, mine
        p, block = mine[0]
        assert "role" not in block, block
        covered = {str(m.get("key") or "") for m in block["measurements"]}
        assert dropped not in covered, (
            "the measurement that was unticked is still in the report")
        drop_dir = next(str(r["_origin_dir"]) for r in dlg._history
                        if dlg._run_key(r) == dropped)
        assert Path(p).parent.parent != Path(drop_dir), (
            "the report went into the dropped date")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# ADVERSARY ROUND 29 — a press that writes nothing
# ---------------------------------------------------------------------------
def test_a_press_that_wrote_nothing_leaves_the_red_line_up(two_dates, qapp,
                                                           monkeypatch):
    """R29-F2. Update, every write refused, and the window says it was applied.

    Measured on screen with the run's report folders set read-only (round 29,
    `scripts/adv29_two_doors.py`, `shots/B-after-1.png`): a report selected, a
    setting moved, the red line up, Generate pressed, **Update** chosen in the
    real popup, and *"Nothing could be written. The log says why."* shown. The
    saved report on disk was untouched — and the red line went DOWN.

    That line reads *"Settings changed. Click 'Generate report' to build the
    report with them, or put the setting back."* After a press that saved no
    file both halves still stand, so taking it away tells the reader the
    opposite of what just happened, in the same second they were told the
    write failed. `_render` re-stamps `_doc_built_with` from the controls every
    time it draws, which is right for a repaint and wrong here.

    The guard asks the three things a reader depends on: the line is still up,
    the one predicate behind it still says the settings moved, and Generate
    would still offer to apply them.
    """
    from PyQt6.QtWidgets import QMessageBox
    import workflow.measurement_report as MR

    from workflow.measurement_report import REPORT_TYPE_SUMMARY
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_SUMMARY,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        before = {p: p.read_bytes() for p in _files(run)}
        chosen_before = dict(dlg._chosen_reports)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._stale_label.isVisible(), "the fixture never raised the line"
        assert dlg._document_being_updated() is not None

        def _refuse(*a, **k):
            raise OSError("read-only file system")

        monkeypatch.setattr(MR, "save_report", _refuse)
        monkeypatch.setattr(MR, "rewrite_report", _refuse)
        said: list = []
        dlg._say_generated = lambda saved, failed: said.append(
            (len(saved), len(failed)))
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()

        assert said and said[0][0] == 0 and said[0][1] >= 1, (
            f"the fixture did not actually refuse the write: {said!r}")
        after = {p: p.read_bytes() for p in _files(run)}
        assert after == before, (
            "a refused press still changed what is on disk: "
            f"{sorted(set(after) ^ set(before))!r}")
        assert dlg._settings_were_modified(), (
            "the window says the moved setting has been applied, and no file "
            "was written")
        assert dlg._stale_label.isVisible(), (
            "the red line went down after a press that wrote nothing")
        assert dlg._document_being_updated() is not None, (
            "pressing Generate again would no longer offer to update the "
            "report the reader still has selected")
        assert dict(dlg._chosen_reports) == chosen_before, (
            "the refused press walked the page off the file it was drawn "
            f"from: {chosen_before!r} -> {dict(dlg._chosen_reports)!r}")
    finally:
        dlg.close()


def test_a_report_whose_measurements_are_all_absent_leaves_the_rows_alone(
        two_dates, qapp, tmp_path):
    """R29-F3. A project that has MOVED, and a saved report that blanks it.

    A measurement's identity inside a document is
    `document_measurement_key`, and it begins with the measurement's ABSOLUTE
    folder. So every key a document records stops matching the moment the
    project is somewhere else: copied to another machine, restored from a
    backup, opened under a different output folder, or shipped in a demo pack
    a user downloads.

    Measured before the fix, the same project and the same document:

        in place  history 2, hidden 1, 1 row on the page, Generate ENABLED
        moved     history 2, hidden 2, 0 rows on the page, Generate DISABLED

    Selecting the saved report emptied the window and greyed the one button
    that writes anything, with no sentence anywhere saying why. B8-490 is what
    reaches it: before tonight the ticks were restored only with "Show all
    measurement runs" ON, and now every door restores them.

    The remedy is the rule the line above it already states, applied to the
    case it does not cover: a document that names no row that is HERE cannot
    say which rows were ticked. One that names some of them still narrows to
    those, and that half is checked too.

    MUTATION, proved to land: put `self._hidden_runs = (here - keys) if keys
    else set()` back.
    """
    import shutil
    from core.file_manager import Project
    from workflow.measurement_report import REPORT_TYPE_SUMMARY

    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        # ONE MEASUREMENT TICKED, because that is what a one-page summary
        # covers and, since B8-591, a press with more than one ticked is
        # refused rather than narrowed behind the user's back. The document
        # this writes covers 1 of the run's 2 rows either way, which is what
        # the moved copy below needs.
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_SUMMARY,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        in_place = (len(dlg._history), len(dlg._hidden_runs),
                    len(dlg._runs_for_report()))
        assert in_place[0] >= 2 and in_place[1] >= 1, (
            "the fixture never narrowed anything, so the moved copy would "
            f"prove nothing: {in_place!r}")
        project_dir = run.dir.parent.parent
    finally:
        dlg.close()

    moved_root = tmp_path / "moved"
    moved_root.mkdir()
    shutil.copytree(project_dir, moved_root / project_dir.name)
    s.set("custom_output_path", str(moved_root))
    moved = Project.load(moved_root / project_dir.name)
    r2 = moved.all_runs()[0]
    dlg2 = _window(s, r2.verifications()[-1].measurement_ti3, qapp)
    try:
        picked = None
        for i in range(dlg2._saved_combo.count()):
            if str(dlg2._saved_combo.itemData(i)).startswith("id:"):
                dlg2._saved_combo.setCurrentIndex(i)
                qapp.processEvents()
                picked = str(dlg2._saved_combo.itemData(i))
                break
        assert picked, "the moved copy lists no document, so nothing was tested"
        assert len(dlg2._hidden_runs) < len(dlg2._history), (
            "every measurement is unticked because the document's recorded "
            "keys name the project's OLD folder")
        assert dlg2._runs_for_report(), (
            "the page has nothing on it after selecting a saved report")
        assert dlg2._generate_btn.isEnabled(), (
            "'Generate report' is disabled because the window emptied itself")
    finally:
        dlg2.close()


def test_a_moved_report_still_ticks_exactly_the_measurements_it_covers(
        two_dates, qapp, tmp_path):
    """K15. The half R29-F3 left: a MOVED document ticks its own rows again.

    R29-F3 stopped a moved project emptying the window, and did it by ticking
    EVERY row: a "One date" report then said, in its own list, that it covered
    the whole history. That is the fault B8-596 fixed for a report with no
    block, back again for every report WITH one, and every project a user
    downloads has moved: the whole demo pack opened that way.

    The document's own files are on disk wherever the project is, and each
    sits in the folder of a measurement it covers, so the window knows the
    answer without the recorded keys.

    MUTATION, proved to land: delete the `covers` fallback in
    `_restore_the_documents_view` and the moved copy ticks 2 of 2.
    """
    import shutil
    from core.file_manager import Project
    from workflow.measurement_report import REPORT_TYPE_SUMMARY

    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_SUMMARY,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        in_place = sorted(r.get("created") for r in dlg._runs_for_report())
        project_dir = run.dir.parent.parent
    finally:
        dlg.close()
    assert len(in_place) == 1, in_place

    moved_root = tmp_path / "moved-again"
    moved_root.mkdir()
    shutil.copytree(project_dir, moved_root / project_dir.name)
    s.set("custom_output_path", str(moved_root))
    moved = Project.load(moved_root / project_dir.name)
    r2 = moved.all_runs()[0]
    dlg2 = _window(s, r2.verifications()[-1].measurement_ti3, qapp)
    try:
        _pick_key(dlg2, key, qapp)
        ticked = sorted(r.get("created") for r in dlg2._runs_for_report())
        assert ticked == in_place, (
            f"the moved copy ticks {ticked!r}; the report covers {in_place!r}")
        assert dlg2._generate_btn.isEnabled()
    finally:
        dlg2.close()


def test_update_copies_every_file_it_rewrites_into_old_first(
        two_dates, qapp, monkeypatch):
    """**D23: NOTHING IS DELETED, and Update deleted the previous content.**

    Critic round, 2026-09-22, driven on Report-Limits-Threshold-Series: a
    changed tick and Update rewrote all 11 member files in place, with 0 copies
    in ``reports/old/``. The previous bytes of a dated verification's record,
    the record the series is compared on, were gone. Now each file the press
    rewrites has its PREVIOUS bytes under ``reports/old/<stamp>/`` under its own
    name, and the live file is still the one updated in place.

    MUTATION, proved to land: delete the `archive_report_files(...)` call in
    `_write_the_document` and the first assert goes red.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        # K31: the report of two dates is ONE file, where it lives.
        mine = [Path(str(entry["file"]))] if entry.get("file") else []
        assert mine, "the fixture no longer makes a report of two dates"
        before = {p: p.read_bytes() for p in mine}

        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()

        for p, old_bytes in before.items():
            copies = [c for c in (p.parent / "old").glob(f"*/{p.name}")
                      if c.read_bytes() == old_bytes]
            assert copies, f"the previous content of {p} was not kept in old/"
            assert p.read_bytes() != old_bytes, (
                f"{p} was not updated, so this proves nothing about it")
    finally:
        dlg.close()


def test_a_file_whose_archive_fails_is_not_rewritten(two_dates, qapp,
                                                     monkeypatch):
    """…and the other half: no archive, no rewrite. A folder that could not be
    copied keeps its files exactly as they were, and the press says it failed
    (`_say_generated` is the window's existing failure message)."""
    from PyQt6.QtWidgets import QMessageBox
    import core.file_manager as FM
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        mine = [Path(str(entry["file"]))] if entry.get("file") else []
        assert mine, "the fixture no longer makes a report of two dates"
        before = {p: p.read_bytes() for p in mine}
        monkeypatch.setattr(
            FM, "archive_report_files",
            lambda paths, when=None, **k: (
                {}, {Path(p).parent.resolve() for p in paths}))
        said = {}
        dlg._say_generated = lambda saved, failed: said.update(
            saved=list(saved), failed=list(failed))
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        for p, old_bytes in before.items():
            assert p.read_bytes() == old_bytes, (
                f"{p} was rewritten although its archive failed")
        assert said.get("failed"), "the failure was not reported"
        assert not said.get("saved"), "a file was reported as saved"
    finally:
        dlg.close()


def test_the_unchanged_question_says_nothing_was_changed(two_dates, qapp,
                                                         monkeypatch):
    """K4 (Knut on beta 34): *"I clicked Generate Report button (without any
    settings having been changed.). This resulted in a new report being
    created, without user being asked"*. Now the real box comes up, under a
    headline that is TRUE of that state, and Cancel writes nothing; with a
    setting moved it is his own headline.

    MUTATION: always render M-REPORT-UPDATE-OR-NEW, and the first headline
    reads "Settings were modified": red.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        del dlg._ask_update_or_create_new
        seen = []
        cancel = _press("Cancel")

        def _exec(box):
            seen.append(box.text())
            return cancel(box)
        monkeypatch.setattr(QMessageBox, "exec", _exec)
        n = len(_files(run))
        dlg._on_generate_report()
        qapp.processEvents()
        assert seen == ["Nothing was changed for the selected report"], seen
        assert len(_files(run)) == n, "Cancel wrote a report"
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        assert seen[-1] == "Settings were modified for the selected report", seen
    finally:
        dlg.close()


def test_after_an_update_the_pdf_is_not_offered_the_earlier_pdfs_name(
        two_dates, qapp, monkeypatch):
    """ROUND A (A-6), 2026-09-22: after Update the suggested PDF name did not
    move, so saving the updated content would overwrite the PDF of what it
    said before. The name now carries the last update, as "Report shown"
    does.

    MUTATION: drop the "updated" suffix in `_report_filename` and this goes
    red.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        before = dlg._report_filename(dlg._runs_for_document())
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        after = dlg._report_filename(dlg._runs_for_document())
        assert after != before, (before, after)
        assert " - updated " in after, after
    finally:
        dlg.close()


def test_a_page_that_is_no_longer_the_saved_document_takes_neither_its_time_nor_its_name(
        two_dates, qapp):
    """ROUND A (A-3), 2026-09-22: with two runs loaded a type change repaints
    at once, so the page stopped being the saved document and still printed
    its "Created:" time, and Save as PDF offered its exact file name. When the
    document no longer speaks for the controls, the page is the window's own.

    MUTATION: make `_note_which_document_the_page_is` ignore
    `_doc_settings_moved` and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        doc_time = dlg._doc_created
        # the window's clock, made distinguishable from a document written in
        # the same second the window opened
        dlg._created = "2020-01-01T00:00:00"
        assert doc_time and doc_time != dlg._created
        dlg._doc_settings_moved = True       # what a live repaint follows
        dlg._render()
        name = dlg._report_filename(dlg._runs_for_document())
        stamp = doc_time.replace("T", "_").replace(":", "-")
        assert stamp not in name, name
        assert "2020-01-01_00-00-00" in name, name
        assert doc_time.replace("T", " ") not in dlg._view.toPlainText()
    finally:
        dlg.close()


def test_an_update_that_cannot_write_one_date_writes_none_of_them(
        two_dates, qapp, monkeypatch):
    """ROUND A (A-1), 2026-09-22, driven on screen: one date's reports folder
    read-only, a setting changed, Update, and 10 of 11 files carried the new
    settings while the locked one kept the old, so one document said two
    things about itself. Now nothing is written unless everything can be.
    Since K31 the report of two dates is one file, so the folder locked here
    is the one it lives in, `verifications/reports/`.

    A REAL read-only folder, not a patched function (round C's point about
    the archive-failure guard above).

    NOT A MUTATION GUARD (round 2C): dropping `_blocked` from the loop's
    skip changes nothing, because `_archive_failed` already returns
    `_blocked or ...`, and this folder fails the archive step itself, so the
    write-access probe is never needed here. Those two mutants (A-09, A-12)
    are pinned in `test_round2c_guards_since_8ae07e4f.py`.
    """
    import os
    import stat
    from PyQt6.QtWidgets import QMessageBox
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    locked = None
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        mine = [Path(str(entry["file"]))] if entry.get("file") else []
        assert mine, "needs a report of two dates"
        before = {p: p.read_bytes() for p in mine}
        locked = mine[0].parent
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        if os.access(locked, os.W_OK):
            pytest.skip("this user can write a read-only folder (root?)")
        said = {}
        dlg._say_generated = lambda saved, failed: said.update(
            saved=list(saved), failed=list(failed))
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        for p, b in before.items():
            assert p.read_bytes() == b, f"{p} was rewritten by a blocked update"
        assert not said.get("saved") and said.get("failed"), said
    finally:
        if locked is not None:
            os.chmod(locked, stat.S_IRWXU)
        dlg.close()
