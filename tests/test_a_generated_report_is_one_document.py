"""B8-383, B8-382, B8-381, B8-380 — one press of Generate is ONE document.

Knut, 2026-09-18, on issue #182::

    The enabling "Show all measurement runs" then Generate Report seems to add
    more saved reports, instead of just rebuilding the report selected showing
    the data for all the included measurements selected.

    Clicking "Show all measurement runs" ON, and then generate report, creates
    2 new reports under the saved reports, which is wrong behaviour.

Measured before any of this was built, on a project with one profile run and
two dated verifications (`~/Desktop/ChromIQ-beta22-proof/knut-report-and-
warnings/D-five-defects/`): **one press of Generate report took the project
from two saved report files to four**, one per dated verification, and a second
press took it from four to six. Nothing was rebuilt, nothing named a document,
and picking an entry changed neither the page nor a single setting.

The root is that a saved report was a per-measurement VERDICT RECORD and never
a document. §13.4 of `docs/design/measurement_report_limits.md` says what has
to exist first, and this file is its guard:

* the files stay one per measurement, because a dated verification's verdict
  lives in that date's own folder (§5), and they now share a document id and
  the settings of the press that wrote them;
* `REPORT_SCHEMA` stays 7 and the block is additive;
* **every report already on a user's disk still opens, is still listed and is
  still named as it was** — it simply has no block, and is its own document.

THE FIXTURE IS DELIBERATELY UNTIDY. It holds two dated verifications, several
saved reports of different shapes, and TWO reports that record no limit set at
all, which is the state the previous round found on the real project it drove.
A fixture too tidy to contain the fault agrees with the code.

**THE BOX IN HIS SENTENCE ABOVE NO LONGER EXISTS (B8-590).** Knut, 2026-09-20,
on the same control he had reported this defect through: *"I realise now this
checkbox is not a reasonable feature to have … Remove the feature 'Show all
measurement runs' totally from the design, and any feature that belongs to that
button … only the selected/ticked measurements shall be part of the report when
created/updated (always)."* Two buttons, "Select all" and "Deselect all", tick
and untick the list and do nothing else.

None of the rules below changed: one press is still one document, the document
still records what it was made with, nothing on a user's disk is rewritten, and
picking an entry still brings its settings back. What changed is how a check
reaches "every measurement" or "one measurement" — the list, through those two
buttons, instead of the box. `all_runs` is still WRITTEN into a document block,
defaulting False, so `document_scope_of` can read a file written before this;
nothing sets it and nothing reads it back into a control.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtCore import Qt                                    # noqa: E402


# --------------------------------------------------------------------------
# the fixture
# --------------------------------------------------------------------------
def _messy_project(tmp_path, dates=2):
    """A run with *dates* dated verifications, each holding

    * one report with NO limit-set block at all (a 4.2.0-era file), and
    * one report stamped with the run's set,

    none of them carrying a document block, because none of them could.
    """
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import bind_run, run_limits
    import os as _os
    import time as _time
    s, fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, "chromiq_default", None)
    lim = run_limits(run, None)
    vs = []
    for _d in range(dates):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        # DATES THAT ARE REALLY DIFFERENT DATES. Two verifications created in
        # one second carry one `created` stamp, and a fixture where two rows
        # are indistinguishable cannot show whether the window tells them
        # apart.
        _t = _time.time() - 86400 * (dates - _d)
        _os.utime(v.measurement_ti3, (_t, _t))
        bare = build_report(v.measurement_ti3)
        bare.pop("compliance", None)          # the two files with no set
        save_report(bare, v.dir)
        rep = build_report(v.measurement_ti3)
        stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                      set_label=lim.label_en, edited=lim.edited)
        save_report(rep, v.dir)
        vs.append(v)
    return s, fm, run, vs


def _dialog(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    # **KNUT'S BETA-25 QUESTION, ANSWERED "Create New" (B8-491).** Generate
    # report now asks what to do when a report from "Report shown" is selected
    # and one of its five settings has moved, and the answer decides whether a
    # new report is written or the selected one is updated. Every test in this
    # file was written for the behaviour his "Create New" button keeps, so that
    # is what these windows answer. The QUESTION itself, and the Update button,
    # are guarded in `tests/test_generate_report_asks_what_to_do.py`.
    dlg._questions_asked = []

    def _answer_create_new():
        dlg._questions_asked.append("asked")
        return "new"

    dlg._ask_update_or_create_new = _answer_create_new
    return dlg


def _files(run):
    return sorted(str(p) for v in run.verifications()
                  for p in (v.dir / "reports").glob("report_*.json"))


# **THE FIRST ROW OF THE PULLDOWN IS "New report…", NOT A REPORT** (B8-388,
# Knut: *"'New report...' should be at the top of the list in the pulldown"*).
# These helpers count and address the REPORTS, so every test below goes on
# meaning what it meant before that row existed.
def _count(dlg):
    return dlg._saved_combo.count() - 1


def _key(dlg, i):
    return str(dlg._saved_combo.itemData(i + 1) or "")


def _label(dlg, i):
    return dlg._saved_combo.itemText(i + 1)


def _pick(dlg, i, qapp):
    dlg._saved_combo.setCurrentIndex(i + 1)
    qapp.processEvents()


def _start_fresh(dlg, qapp):
    """Choose "New report…", the way a user starts one.

    **NEEDED SINCE KNUT'S BETA-25 RULING (B8-490).** A window opens showing a
    saved report, and a saved report's own measurements are now what is ticked
    in the "Included Measurements" list — *"Included measurements added for
    report is ticked"*. Every report in this fixture is a per-measurement
    record of ONE date, so a window that opens on one has the other date
    UNTICKED, and the report then covers one measurement. That is the ruling
    working, not a fault; a test about what one press of Generate writes has to
    start from a state where both dates are in, and "New report…" is the
    control that means exactly that (it clears `_hidden_runs`).
    """
    dlg._saved_combo.setCurrentIndex(0)
    qapp.processEvents()


def _every_measurement(dlg, qapp):
    """Tick every measurement: what `_all_runs_check` ON used to mean (B8-590).

    Pressed through the button Knut asked for, so these checks go through the
    door a user really has.
    """
    dlg._select_all_btn.click()
    qapp.processEvents()
    assert dlg._hidden_runs == set(), dlg._hidden_runs


def _only_this_measurement(dlg, qapp):
    """Leave only the measurement the window is on ticked: what the box OFF
    used to mean, said as the list state it always really was.

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


# --------------------------------------------------------------------------
# B8-383 — one press, one document
# --------------------------------------------------------------------------
def test_one_press_of_generate_writes_one_document(tmp_path, qapp):
    """His number, exactly: two files became four and the list grew by two.

    It still writes a file per measurement, and the list grows by ONE.

    MUTATION, to be proved to land: drop the `stamp_document` call from
    `_on_generate_report` and this goes red (the list grows by two).
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        before_files = _files(run)
        before_entries = _count(dlg)
        assert len(before_files) == 4, before_files
        assert before_entries == 4, "the four pre-existing files are four entries"
        dlg._on_generate_report()
        qapp.processEvents()
        after_files = _files(run)
        assert len(after_files) == 6, (
            "one press should still file a verdict per measurement")
        assert _count(dlg) == before_entries + 1, (
            f"one press of Generate added {_count(dlg) - before_entries} "
            f"entries to the list")
    finally:
        dlg.close()


def test_the_document_records_what_it_was_made_with(tmp_path, qapp):
    """§13.4's fields: type, set id and label, the thresholds copy, both tick
    boxes and the list of measurements included.

    MUTATION: drop `measurements` (or either tick box) from `stamp_document`
    and this goes red.
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        before = set(_files(run))
        dlg._on_generate_report()
        qapp.processEvents()
        written = sorted(set(_files(run)) - before)
        assert len(written) == 2, written
        docs = [json.loads(Path(p).read_text(encoding="utf-8"))["document"]
                for p in written]
        assert len({d["id"] for d in docs}) == 1, (
            "the two files of one press are not one document")
        d = docs[0]
        assert d["type"]
        assert d["compliance"]["set_id"] == "chromiq_default"
        assert d["compliance"]["thresholds"]
        assert d["detail"] is True
        # **`all_runs` IS DEAD AND STILL WRITTEN (B8-590).** It used to be
        # asserted True here, from the box; nothing sets it now, so the field
        # is checked for its type alone — it exists, for `document_scope_of`
        # to read on a file written before the removal, and says nothing about
        # what this document covers. `measurements` is what says that.
        assert d["all_runs"] is False, (
            "something is still feeding the removed box's value into a "
            "document block")
        assert len(d["measurements"]) == 2, d["measurements"]
        assert all(m["dir"] and m["created"] for m in d["measurements"])
    finally:
        dlg.close()


def test_the_schema_is_not_bumped_and_nothing_on_disk_is_rewritten(tmp_path,
                                                                   qapp):
    """**THE ABSOLUTE CONSTRAINT.** Every report a user already has must still
    open, and this change may not delete, rename or rewrite one.

    MUTATION: raise `REPORT_SCHEMA`, or rewrite an existing file in
    `_on_generate_report`, and this goes red.
    """
    from workflow.measurement_report import REPORT_SCHEMA
    assert REPORT_SCHEMA == 7
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    before = {p: (Path(p).read_bytes(), Path(p).stat().st_mtime_ns)
              for p in _files(run)}
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _every_measurement(dlg, qapp)
        dlg._on_generate_report()
        qapp.processEvents()
        for path, (raw, mtime) in before.items():
            assert Path(path).is_file(), f"{path} was deleted or renamed"
            assert Path(path).read_bytes() == raw, f"{path} was rewritten"
            assert Path(path).stat().st_mtime_ns == mtime
            assert "document" not in json.loads(raw.decode("utf-8")), (
                "this fixture is meant to hold files with no document block")
    finally:
        dlg.close()


def test_a_report_with_no_document_block_is_still_listed_and_named(tmp_path,
                                                                   qapp):
    """Four files a 4.2.0 wrote, four entries, each named as it is today.

    MUTATION: drop the `file:` branch from `document_key` (or from
    `_saved_documents`) and this goes red: the four collapse into one entry.
    """
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        assert _count(dlg) == 4
        keys = [_key(dlg, i) for i in range(4)]
        assert all(k.startswith("file:") for k in keys), keys
        labels = [_label(dlg, i) for i in range(4)]
        assert len(set(labels)) == 4, labels
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B8-381 / B8-382 — picking one brings it back, with its settings
# --------------------------------------------------------------------------
def _two_documents(dlg, qapp):
    """Generate two documents that differ in TYPE and in both tick boxes.

    The previous round's caveat, recorded in B8-382: on a project whose saved
    reports share a type and a set, "the settings did not move" is consistent
    with the defect rather than decisive. So the two here are made to differ.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_FULL)
    # The two differ in TYPE, in the detail box, and in WHICH MEASUREMENTS
    # they cover. That third one used to be the "Show all measurement runs"
    # box; it is the measurement ticks since B8-590, which is the setting a
    # document has always really recorded (`measurements`).
    _every_measurement(dlg, qapp)
    dlg._detail_check.setChecked(False)
    qapp.processEvents()
    dlg._sync_type_combo_to(REPORT_TYPE_FULL)
    dlg._on_type_chosen(dlg._type_combo.currentIndex())
    qapp.processEvents()
    dlg._on_generate_report()
    qapp.processEvents()
    first = dlg._loaded_doc_id
    _only_this_measurement(dlg, qapp)
    dlg._detail_check.setChecked(True)
    qapp.processEvents()
    dlg._sync_type_combo_to(REPORT_TYPE_GREY)
    dlg._on_type_chosen(dlg._type_combo.currentIndex())
    qapp.processEvents()
    dlg._on_generate_report()
    qapp.processEvents()
    return first, dlg._loaded_doc_id


def test_picking_a_report_redraws_the_window_with_it(tmp_path, qapp):
    """B8-381. Measured before this, with every entry picked in turn: the
    selection stuck and the rendered document's SHA-256 did not move.

    MUTATION: make `_load_document` return before it sets `_chosen_reports`
    and `_loaded_doc`, and this goes red.
    """
    import hashlib
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        first, second = _two_documents(dlg, qapp)
        assert first and second and first != second
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}

        def _show(key):
            _pick(dlg, rows[key], qapp)
            return hashlib.sha256(
                dlg._view.toHtml().encode("utf-8")).hexdigest()

        a = _show(first)
        b = _show(second)
        assert a != b, (
            "the page is byte-identical for two documents of different types "
            "over different measurements")
        assert _show(first) == a, "going back does not bring the first back"
    finally:
        dlg.close()


def test_picking_a_report_restores_the_settings_it_was_made_with(tmp_path,
                                                                 qapp):
    """B8-382, on documents that differ in type AND in both tick boxes.

    The third setting used to be "Show all measurement runs"; since B8-590 it
    is the measurement ticks, which is what a document records and what Knut
    named first: *"Included measurements added for report is ticked"*.

    MUTATION: drop the tick restore from `_restore_the_documents_view`, or the
    `_loaded_doc` branch from `_report_type_now`, and this goes red.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_FULL)
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        first, second = _two_documents(dlg, qapp)
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        _pick(dlg, rows[first], qapp)
        assert dlg._report_type_now() == REPORT_TYPE_FULL
        assert dlg._hidden_runs == set(), (
            "the document made over every measurement came back narrowed")
        assert len(dlg._runs_for_report()) == 2
        assert dlg._detail_check.isChecked() is False
        _pick(dlg, rows[second], qapp)
        assert dlg._report_type_now() == REPORT_TYPE_GREY
        assert len(dlg._runs_for_report()) == 1, (
            "the one-measurement document came back covering the history")
        assert dlg._detail_check.isChecked() is True
    finally:
        dlg.close()


def test_the_restored_set_is_the_documents_own_and_the_run_is_not_touched(
        tmp_path, qapp):
    """A document judged against another set brings that set back into the
    pulldown, and the RUN keeps the set it is bound to.

    This is the half of B8-382 that B8-384 must not be allowed to eat: the
    window shows the document's set, and nothing on disk moves.

    MUTATION: drop the `_document_limits()` term from `_sync_limit_controls`
    and this goes red.
    """
    from workflow.run_compliance import run_limits
    s, _fm, run, vs = _messy_project(tmp_path, dates=1)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        dlg._on_generate_report()
        qapp.processEvents()
        key = dlg._loaded_doc_id
        # forge a document that was judged against another set, exactly as a
        # user who changed "Judged against" between two presses would have
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        for r, name in entry["members"]:
            path = Path(str(r["_origin_dir"])) / "reports" / name
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["document"]["compliance"]["set_id"] = "chromiq_tight"
            doc["document"]["compliance"]["set_label"] = "ChromIQ tight"
            path.write_text(json.dumps(doc), encoding="utf-8")
        dlg._doc_cache = {}
        dlg._loaded_doc_id = ""
        dlg._reload_sources()
        qapp.processEvents()
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        _pick(dlg, rows[key], qapp)
        assert dlg._set_combo.currentData() == "chromiq_tight", (
            f"the pulldown says {dlg._set_combo.currentData()} over a document "
            f"judged against ChromIQ tight")
        assert run_limits(run, None).set_id == "chromiq_default", (
            "loading a report rebound the run")
    finally:
        dlg.close()


def test_moving_a_control_stops_the_document_speaking_for_it(tmp_path, qapp):
    """The other direction, and it is Knut's fifth defect in reverse: an entry
    that disagrees with the window naming it.

    MUTATION: drop `self._loaded_doc = None` from `_settings_touched` and this
    goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = _messy_project(tmp_path, dates=1)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        dlg._sync_type_combo_to(REPORT_TYPE_FULL)
        dlg._on_type_chosen(dlg._type_combo.currentIndex())
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        assert dlg._loaded_doc is not None
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._document_settings() is None, (
            "the loaded document still claims the settings the user moved")
        assert dlg._loaded_doc_id, (
            "the document itself was dropped; only its claim on the controls "
            "should go")
        assert dlg._stale_label.isVisible(), (
            "the red line does not say the settings and the document differ")
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B8-380 — where the list is, what it looks like, and Delete
# --------------------------------------------------------------------------
def test_the_window_is_laid_out_the_way_knut_drew_it(tmp_path, qapp):
    """**HIS BETA-25 MOCKUP, AND IT SUPERSEDES L.8 (B8-460).**

    `~/Desktop/ChromIQ-knut-beta25-batch/mockup-report-window-layout.png`,
    2026-09-19: *"a frame called 'Report settings' encompass all the relevant
    buttons and input controls that are related to the settings for a report.
    The report shown is above the frame, with its help icon, and two text
    elements: the text 'Click a report to load …' to the right of the 'report
    shown' (and its help icon) and the 'Already generated…' below the 'report
    shown' input box. Below the 'Report settings' frame there are 4 buttons and
    a help icon (starting left with Generate Report, then Delete Selected
    Report, then Save Report As PDF, then Reveal Folder, then help icon)."*

    This test used to be `test_the_list_sits_between_generate_report_and_
    report_type`, which is L.8: *"The button for Generate Report and Delete
    Selected Report should probably be placed vertically over one another left
    to the new List of Generated Reports"*. That measured Generate report at
    y=250 above the pulldown; his mockup puts it below the frame instead, so
    the old assertion is the one this replaces rather than joins.

    MUTATION (run 2026-09-19, seen red, restored): put `actions_row` back above
    `self._settings_box` in `__init__`::

        E  AssertionError: 'Generate report' at 191 is not below the frame
        E  assert 191 > 372
    """
    def _y(w):
        return w.mapTo(dlg, w.rect().topLeft()).y()

    def _x(w):
        return w.mapTo(dlg, w.rect().topLeft()).x()

    s, _fm, _run, vs = _messy_project(tmp_path, dates=1)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        # 1. the pulldown is ABOVE the frame, and the frame holds the settings
        assert _y(dlg._saved_combo) < _y(dlg._settings_box), (
            f"Report shown {_y(dlg._saved_combo)}, "
            f"frame {_y(dlg._settings_box)}")
        # "Show all measurement runs" stood between the limits button and
        # the detail box until B8-590; the two buttons Knut asked for in its
        # place live inside the same frame, beside the list.
        assert getattr(dlg, "_all_runs_check", None) is None
        for w in (dlg._add_btn, dlg._profile_list, dlg._list_label,
                  dlg._type_combo, dlg._set_combo, dlg._limits_btn,
                  dlg._select_all_btn, dlg._deselect_all_btn,
                  dlg._detail_check, dlg._unlock_check):
            assert dlg._settings_box.isAncestorOf(w), (
                f"{w.objectName() or w.__class__.__name__} is outside the "
                f"Report settings frame")
        # 2. and the four buttons are BELOW it, in his order, left to right
        for w in (dlg._generate_btn, dlg._delete_report_btn, dlg._pdf_btn,
                  dlg._reveal_btn):
            assert not dlg._settings_box.isAncestorOf(w)
            assert _y(w) > _y(dlg._set_combo), (
                f"{w.text()!r} at {_y(w)} is not below the frame")
        xs = [_x(dlg._generate_btn), _x(dlg._delete_report_btn),
              _x(dlg._pdf_btn), _x(dlg._reveal_btn)]
        assert xs == sorted(xs) and len(set(xs)) == 4, xs
        ys = {_y(w) for w in (dlg._generate_btn, dlg._delete_report_btn,
                              dlg._pdf_btn, dlg._reveal_btn)}
        assert len(ys) == 1, f"the four buttons are not on one line: {ys}"
        # 3. "Already generated…" sits under the pulldown, at its left edge
        assert _y(dlg._type_blurb) > _y(dlg._saved_combo)
        assert _y(dlg._type_blurb) < _y(dlg._settings_box)
        assert abs(_x(dlg._type_blurb) - _x(dlg._saved_combo)) <= 2, (
            f"blurb x={_x(dlg._type_blurb)}, box x={_x(dlg._saved_combo)}")
        # 4. the hint rides to the RIGHT of the pulldown and its help button
        assert _x(dlg._saved_help) > _x(dlg._saved_combo)
        assert _x(dlg._saved_hint) > _x(dlg._saved_help)
        # 5. the two pulldowns inside the frame share one left edge
        assert _x(dlg._type_combo) == _x(dlg._set_combo), (
            f"type {_x(dlg._type_combo)}, judged {_x(dlg._set_combo)}")
    finally:
        dlg.close()


def test_every_entry_carries_its_own_settings_in_its_name(tmp_path, qapp):
    """L.3, and it is what a PULLDOWN needs most: one row is visible at a time.

    Knut asked for a 3-to-4-row scrolling box and then ruled *"It is ok that
    'Current Report Showing' is a pulldown list if that saves space in the
    window."* What survives that is the naming rule: *"The list of reports need
    to have names generated, with date and time, that reflect their selections
    … F.ex. 'Run type, Judged agains, All runs, with details, <date_time>', or
    'Run type, Judged agains, only run <date>, without details, <date_time>'."*

    MUTATION: drop the tick-box clauses from `_document_label` and this goes
    red, because the two entries below differ in nothing else a name shows.
    """
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        first = _label(dlg, 0)
        _only_this_measurement(dlg, qapp)
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        second = _label(dlg, 0)
        # KNUT'S FLAG WORDS (B8-392, 2026-09-18): *"If 'Show all measurement
        # runs' is ON and all measurement dates are marked to be included, then
        # the name should include the flag 'All dates'. … 'One date'. …
        # 'Multiple dates'. … If 'Show detailed data for each run' in ON, the
        # name should include the flag 'Detailed'."* The box in that sentence
        # was removed (B8-590) and the flag reads the document's own member
        # list (B8-522), so the words are unchanged and the state that earns
        # them is the ticks.
        assert "All dates" in first and "Detailed" in first, first
        assert "One date" in second, second
        assert "Detailed" not in second, second
        assert first != second
        # …and the date and time it was made, which is all that tells two
        # presses of the same settings apart (L.4).
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", first), first
    finally:
        dlg.close()


def test_delete_moves_every_file_of_the_document(tmp_path, qapp):
    """L.7, on a document that spans two dated verifications of one run: it
    goes to the RUN's `verifications/old/`, and nothing is destroyed.

    **K23 (Knut, 2026-09-23): what moves is the DOCUMENT FILE.** A document of
    several dates lives in `runN/verifications/reports/`, and each date keeps
    its own verdict record, which "is not a report": it stays in the date's
    folder, so the date keeps its verdict after the report is deleted.

    MUTATION: `unlink` instead of moving, move the records with it, or move
    nothing, and this goes red.
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        before = set(_files(run))
        home = run.verifications_dir / "reports"
        dlg._on_generate_report()
        qapp.processEvents()
        written = sorted(set(_files(run)) - before)
        assert len(written) == 2, written
        doc_files = sorted(home.glob("report_*.json"))
        assert len(doc_files) == 1, doc_files
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        _pick(dlg, rows[dlg._loaded_doc_id], qapp)
        dlg._on_delete_report()
        qapp.processEvents()
        assert not doc_files[0].exists(), f"{doc_files[0]} is still live"
        for p in written:
            assert Path(p).exists(), f"the date's verdict record {p} went too"
        old = list((run.verifications_dir / "old").glob("*/report_*.json"))
        assert [o.name for o in old] == [doc_files[0].name], (
            f"a document spanning two dates left {old} in "
            f"{run.verifications_dir / 'old'}")
    finally:
        dlg.close()


def test_delete_of_a_one_date_document_lands_in_that_dates_own_old_folder(
        tmp_path, qapp):
    """The other half of L.7's first rule.

    MUTATION: return the run's `verifications/old/` for a single-folder
    document and this goes red.
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        _only_this_measurement(dlg, qapp)
        before = set(_files(run))
        dlg._on_generate_report()
        qapp.processEvents()
        written = sorted(set(_files(run)) - before)
        assert len(written) == 1, written
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        _pick(dlg, rows[dlg._loaded_doc_id], qapp)
        dlg._on_delete_report()
        qapp.processEvents()
        here = list((vs[-1].dir / "reports" / "old").glob("*/report_*.json"))
        assert len(here) == 1, here
        assert not (run.verifications_dir / "old").exists(), (
            "a one-date document reached the run's old/ folder")
    finally:
        dlg.close()


@pytest.mark.parametrize("span,where", [
    ("one", "reports/old"),
    ("dates", "verifications/old"),
    ("runs", "project/old"),
])
def test_the_old_folder_is_decided_by_what_the_document_spans(tmp_path, span,
                                                              where):
    """L.7's three destinations, asked of the rule itself.

    MUTATION: swap any two branches of `document_old_dir` and this goes red.
    """
    from workflow.measurement_report import document_old_dir
    proj = tmp_path / "P"
    r1 = proj / "runs" / "run1"
    r2 = proj / "runs" / "run2"
    d1 = r1 / "verifications" / "2026-01-01_100000"
    d2 = r1 / "verifications" / "2026-02-02_100000"
    d3 = r2 / "verifications" / "2026-03-03_100000"
    dirs = {"one": [d1], "dates": [d1, d2], "runs": [d1, d3]}[span]
    got = document_old_dir(dirs)
    assert got is not None
    text = str(got)
    if where == "reports/old":
        assert text.startswith(str(d1 / "reports" / "old")), text
    elif where == "verifications/old":
        assert text.startswith(str(r1 / "verifications" / "old")), text
    else:
        assert text.startswith(str(proj / "old")), text


def test_the_empty_list_and_the_instruction(tmp_path, qapp):
    """L.9, both sentences, on a run with no report at all and on one with
    reports.

    MUTATION: drop either `_set_saved_hint` call from `_sync_saved_reports`
    and this goes red.
    """
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        assert _count(dlg) == 0
        assert "Generate report" in dlg._saved_hint.toolTip()
    finally:
        dlg.close()
    s2, _fm2, _run2, vs = _messy_project(tmp_path / "b", dates=1)
    dlg = _dialog(s2, vs[0].measurement_ti3, qapp)
    try:
        assert _count(dlg) == 2
        assert "Click a report" in dlg._saved_hint.toolTip()
    finally:
        dlg.close()


def test_a_report_that_records_no_document_still_restores_what_it_records(
        tmp_path, qapp):
    """Knut, 2026-09-18, on the per-dated-verification records ChromIQ writes
    by itself at measurement time::

        If the list of reports in "Current Report Showing" have one report per
        dated verification (by default created during measurement), then each
        of those reports, when selecting one, should load and show with its
        report text in the window. And each of those will automatically have
        the settings updated to what was used when generating those reports
        (Correct report type, correct Judge Against used, "Show all measurement
        runs" OFF (since it is only one date), etc.)

    Nothing is written for this: the type and the set are read off the file,
    and the settings come from his sentence.

    **HIS PARENTHESIS OUTLIVED THE BOX IT NAMED (B8-590, B8-596).** *"'Show
    all measurement runs' OFF (since it is only one date)"* was a statement
    about the report, made through the control that existed then. The control
    is gone; what is left is the list, and a legacy report now ticks the one
    measurement it was filed beside instead of leaving the ticks alone. That
    is Knut again, 2026-09-20: *"One the measurement used in the selected
    report shall be ticked."*

    MUTATION: drop `_settings_of_one_saved_report` from `_load_document`, or
    the `covers` branch from `_restore_the_documents_view`, and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY, report_type
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    # give the older date's stamped report a type of its own, the way a
    # measurement taken while the run was on another type would have
    stamped = sorted((vs[0].dir / "reports").glob("report_*.json"))[-1]
    doc = json.loads(stamped.read_text(encoding="utf-8"))
    doc["report_type"] = REPORT_TYPE_GREY
    stamped.write_text(json.dumps(doc), encoding="utf-8")
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _every_measurement(dlg, qapp)
        key = f"file:{stamped}"
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        assert key in rows, sorted(rows)
        # THE WINDOW OPENS ON THE NEWEST DOCUMENT (B8-388), which may be this
        # one, and a pulldown emits nothing when the index does not change. So
        # move off it first: what is being tested is the LOADING, not the
        # state the window happened to open in.
        _pick(dlg, (rows[key] + 1) % len(rows), qapp)
        _pick(dlg, rows[key], qapp)
        assert dlg._report_type_now() == REPORT_TYPE_GREY
        assert [dlg._run_key(r) for r in dlg._runs_for_report()] == [
            dlg._run_key(dlg._report)], (
            "a report about one dated verification loaded covering the whole "
            "history")
        assert len(dlg._history) == 2, "the other date really is loaded"
        assert dlg._detail_check.isChecked() is False
        assert dlg._set_combo.currentData() == "chromiq_default"
        assert report_type(json.loads(stamped.read_text(encoding="utf-8"))) \
            == REPORT_TYPE_GREY, "loading the report rewrote it"
    finally:
        dlg.close()


def test_a_generated_document_is_never_recalculated(tmp_path, qapp, monkeypatch):
    """Knut, 2026-09-18: *"Agreed. D23 stands."* and *"It is better that
    existing reports are not overwritten."*

    A document records the settings it was made with and is named after them,
    so a recalculation that re-judged it against another set would make its own
    record false and its own name a lie. That is the photograph in B8-384: an
    entry reading "ChromIQ tight" over a page still reading "ChromIQ default".

    **THROUGH THE REPORT LIMITS WINDOW'S SAVE, WHICH IS WHERE A RECALCULATION
    STILL HAPPENS.** This test has now been re-aimed twice, and each time
    because Knut closed the door it was driving. It drove the "Judged against"
    pulldown until B8-384, then the unlock tick box until B8-391 (*"All dated
    reports shall NOT be recalculated"*). One door is left, the Save in the
    Report limits window, and it is B8-310: whether Knut's N.3 reaches it too
    is still an open question for him and nothing here assumes an answer.

    The second half is what stops it passing by accident: the legacy report,
    which carries no document block, IS rewritten on this door, so the run
    really was recalculated.

    MUTATION: drop the `recorded_document` guard from `_recalculate_run` and
    this goes red.
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=1)
    s.set("compliance_allow_edit_after_measurement", True)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        before = set(_files(run))
        dlg._on_generate_report()
        qapp.processEvents()
        written = sorted(set(_files(run)) - before)
        assert len(written) == 1, written
        was = Path(written[0]).read_bytes()
        legacy = sorted(before)
        legacy_was = {p: Path(p).read_bytes() for p in legacy}
        # the app's own door: unlock the run (which recalculates nothing,
        # B8-391), then edit one of its numbers in the Report limits window and
        # close it, which is the recalculation §5 and D23 describe.
        dlg._unlock_check.setChecked(True)
        qapp.processEvents()
        from tests.test_report_window_limit_controls import \
            _edit_the_runs_numbers
        _edit_the_runs_numbers(dlg, monkeypatch, value=0.2)
        qapp.processEvents()
        assert Path(written[0]).read_bytes() == was, (
            "the generated document was recalculated")
        assert any(Path(p).read_bytes() != legacy_was[p] for p in legacy), (
            "nothing was recalculated at all, so this proves nothing about "
            "the guard")
    finally:
        dlg.close()
