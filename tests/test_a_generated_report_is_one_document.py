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
    return dlg


def _files(run):
    return sorted(str(p) for v in run.verifications()
                  for p in (v.dir / "reports").glob("report_*.json"))


def _count(dlg):
    return dlg._saved_combo.count()


def _key(dlg, i):
    return str(dlg._saved_combo.itemData(i) or "")


def _pick(dlg, i, qapp):
    dlg._saved_combo.setCurrentIndex(i)
    qapp.processEvents()


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
        dlg._all_runs_check.setChecked(True)
        qapp.processEvents()
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
        dlg._all_runs_check.setChecked(True)
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
        assert d["all_runs"] is True and d["detail"] is True
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
        dlg._all_runs_check.setChecked(True)
        qapp.processEvents()
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
        labels = [dlg._saved_combo.itemText(i) for i in range(4)]
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
                                             REPORT_TYPE_RECORD)
    dlg._all_runs_check.setChecked(True)
    dlg._detail_check.setChecked(False)
    qapp.processEvents()
    dlg._sync_type_combo_to(REPORT_TYPE_RECORD)
    dlg._on_type_chosen(dlg._type_combo.currentIndex())
    qapp.processEvents()
    dlg._on_generate_report()
    qapp.processEvents()
    first = dlg._loaded_doc_id
    dlg._all_runs_check.setChecked(False)
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

    MUTATION: drop the tick-box restore from `_load_document`, or the
    `_loaded_doc` branch from `_report_type_now`, and this goes red.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        first, second = _two_documents(dlg, qapp)
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        _pick(dlg, rows[first], qapp)
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
        assert dlg._all_runs_check.isChecked() is True
        assert dlg._detail_check.isChecked() is False
        _pick(dlg, rows[second], qapp)
        assert dlg._report_type_now() == REPORT_TYPE_GREY
        assert dlg._all_runs_check.isChecked() is False
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
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, _run, vs = _messy_project(tmp_path, dates=1)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        dlg._sync_type_combo_to(REPORT_TYPE_RECORD)
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
def test_the_list_sits_between_generate_report_and_report_type(tmp_path, qapp):
    """L.8. Measured before this: Generate report y=250, Report type y=292,
    Judged against y=340, **Saved reports y=388**, below both.

    MUTATION: pack the list row after `type_row` and this goes red.
    """
    s, _fm, _run, vs = _messy_project(tmp_path, dates=1)
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        gen = dlg._generate_btn.mapTo(dlg, dlg._generate_btn.rect().topLeft()).y()
        lst = dlg._saved_combo.mapTo(dlg, dlg._saved_combo.rect().topLeft()).y()
        typ = dlg._type_combo.mapTo(dlg, dlg._type_combo.rect().topLeft()).y()
        jud = dlg._set_combo.mapTo(dlg, dlg._set_combo.rect().topLeft()).y()
        assert gen <= lst < typ < jud, (
            f"Generate {gen}, list {lst}, Report type {typ}, Judged {jud}")
        # …and the two buttons are stacked to its LEFT
        assert dlg._delete_report_btn.mapTo(
            dlg, dlg._delete_report_btn.rect().topLeft()).x() \
            < dlg._saved_combo.mapTo(dlg, dlg._saved_combo.rect().topLeft()).x()
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
        dlg._all_runs_check.setChecked(True)
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        first = dlg._saved_combo.itemText(0)
        dlg._all_runs_check.setChecked(False)
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        second = dlg._saved_combo.itemText(0)
        assert "all runs" in first and "with details" in first, first
        assert "only run" in second and "without details" in second, second
        assert first != second
        # …and the date and time it was made, which is all that tells two
        # presses of the same settings apart (L.4).
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", first), first
    finally:
        dlg.close()


def test_delete_moves_every_file_of_the_document(tmp_path, qapp):
    """L.7, on a document that spans two dated verifications of one run: its
    files go to the RUN's `verifications/old/`, and nothing is destroyed.

    MUTATION: move only the file the page is drawn from, or `unlink` instead of
    moving, and this goes red.
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        dlg._all_runs_check.setChecked(True)
        qapp.processEvents()
        before = set(_files(run))
        dlg._on_generate_report()
        qapp.processEvents()
        written = sorted(set(_files(run)) - before)
        assert len(written) == 2, written
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        _pick(dlg, rows[dlg._loaded_doc_id], qapp)
        dlg._on_delete_report()
        qapp.processEvents()
        for p in written:
            assert not Path(p).exists(), f"{p} is still live"
        old = list((run.verifications_dir / "old").glob("*/report_*.json"))
        assert len(old) == 2, (
            f"a document spanning two dates left {len(old)} files in "
            f"{run.verifications_dir / 'old'}")
        assert set(_files(run)) == before, "another report went with it"
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
        dlg._all_runs_check.setChecked(False)
        qapp.processEvents()
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
    and the two tick boxes come from his sentence.

    MUTATION: drop `_settings_of_one_saved_report` from `_load_document` and
    this goes red.
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
        dlg._all_runs_check.setChecked(True)
        qapp.processEvents()
        key = f"file:{stamped}"
        rows = {d["key"]: n for n, d in enumerate(
            dlg._saved_documents(dlg._run_ctx.run))}
        assert key in rows, sorted(rows)
        _pick(dlg, rows[key], qapp)
        assert dlg._report_type_now() == REPORT_TYPE_GREY
        assert dlg._all_runs_check.isChecked() is False, (
            "a report about one dated verification loaded with the whole "
            "history switched on")
        assert dlg._detail_check.isChecked() is False
        assert dlg._set_combo.currentData() == "chromiq_default"
        assert report_type(json.loads(stamped.read_text(encoding="utf-8"))) \
            == REPORT_TYPE_GREY, "loading the report rewrote it"
    finally:
        dlg.close()


def test_a_generated_document_is_never_recalculated(tmp_path, qapp):
    """Knut, 2026-09-18: *"Agreed. D23 stands."* and *"It is better that
    existing reports are not overwritten."*

    A document records the settings it was made with and is named after them,
    so a recalculation that re-judged it against another set would make its own
    record false and its own name a lie. That is the photograph in B8-384: an
    entry reading "ChromIQ tight" over a page still reading "ChromIQ default".

    **THIS IS NOT THE WHOLE OF B8-384**, and the second half of this test says
    so: a report saved by an earlier ChromIQ carries no document block and IS
    still rewritten, exactly as it is today.

    MUTATION: drop the `recorded_document` guard from `_recalculate_run` and
    this goes red.
    """
    s, _fm, run, vs = _messy_project(tmp_path, dates=1)
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
        # the app's own door: choose another limit set in the pulldown
        i = dlg._set_combo.findData("chromiq_tight")
        assert i >= 0
        dlg._set_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert Path(written[0]).read_bytes() == was, (
            "the generated document was recalculated")
        assert any(Path(p).read_bytes() != legacy_was[p] for p in legacy), (
            "nothing was recalculated at all, so this proves nothing about "
            "the guard")
    finally:
        dlg.close()
