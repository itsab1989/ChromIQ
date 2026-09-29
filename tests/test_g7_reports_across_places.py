"""#182 beta 39, G7: Generate report across profile runs and across projects.

Knut, 5794078008 (point 3): *"a user may need to see how a printers profile
has changed across different periods that are saved as different projects"*,
so Generate makes a report across projects. Knut, 5773668311, confirmed in
5794311113: *"the report's own limit set applies to every included
measurement, whatever each run is bound to."*

What is built (spec §13.9 "one report, one limit set, across runs", §20 G7,
and the superseded sentences of §13.11 and §18.12):

* a report across places (several profile runs, or several projects' runs or
  calibrations) is ONE document file, in `<project>/reports/` or in the
  folder across projects (`<ChromIQ folder>/reports/`, made by that write);
* every measurement in it is judged against the report's own set, and the
  file records each verdict (`JUDGED_KEY`), so it is never recalculated
  under its reader;
* a verdict record is written only into the window's own run, and only where
  it cannot contradict that run (a profiling sheet, or a date whose run has
  the same yardstick); no binding, no other place's folder, no lock moves;
* a report across projects is offered only in a window whose list it covers,
  compared by project name as well as `runs/` path (the leak).

Every test names the mutation that turns it red; each was run red with
`-n 0` before this file was committed (REPORT.md in
~/Desktop/ChromIQ-beta39-proof/g7/).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from tests.test_calibration_reports import (                   # noqa: E402
    _headings, _project_with_cal, _rows, _settings, _window)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")
    monkeypatch.setattr(MeasurementReportDialog, "_confirm",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(MeasurementReportDialog, "_say_generated",
                        lambda self, saved, failed: None)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _date(run, scale=1.0):
    """A dated verification of *run*, measured, with the report a
    measurement saves (judged against the run's own set)."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import run_limits
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(
        _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
        encoding="utf-8")
    lim = run_limits(run, None)
    rep = build_report(v.measurement_ti3)
    stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.label_en)
    save_report(rep, v.dir)
    return v


def _project(root: Path, name: str, bind: str = "chromiq_default"):
    """A project NAME in *root* whose run1 is bound to *bind* and has one
    dated verification. Returns (project, run, verification)."""
    from core.file_manager import Project
    from tests.helpers.legacy_run_meta import (bind_run)
    proj = Project.create(root / name, name)
    run = proj.current_run()
    run.ensure_dir()
    bind_run(run, bind, None)
    return proj, run, _date(run)


def _snapshot(*folders) -> dict:
    out = {}
    for f in folders:
        for p in sorted(Path(f).rglob("*")):
            if p.is_file():
                out[str(p)] = p.read_bytes()
    return out


def _new_report_of_everything(dlg, qapp, set_id: "str | None" = None):
    dlg._saved_combo.setCurrentIndex(0)                  # "New report…"
    qapp.processEvents()
    dlg._select_all_btn.click()
    qapp.processEvents()
    if set_id is not None:
        i = dlg._set_combo.findData(set_id)
        assert i >= 0, set_id
        dlg._set_combo.setCurrentIndex(i)
        qapp.processEvents()


def _press(dlg, qapp):
    dlg._on_generate_report()
    qapp.processEvents()


def _reports(folder: Path) -> list:
    return sorted(folder.glob("report_*.json")) if folder.is_dir() else []


def _read(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. across runs of one project
# --------------------------------------------------------------------------
def test_a_report_across_two_runs_is_one_document_judged_by_its_own_set(
        tmp_path, qapp):
    """Two runs of one project, bound to two different sets, and the report
    judged against a THIRD: one document file in `<project>/reports/`, every
    measurement's verdict against the report's set recorded in it, no file
    written into either date (neither run is bound to that set), and neither
    run's binding moved.

    MUTATION, proven red: drop the `_same_yardstick` check in
    `_records_across_places` (run1's date gets a record judged against Quick
    check, a set its run is not bound to)."""
    from workflow.measurement_report import JUDGED_KEY, recorded_document
    from workflow.run_compliance import run_limits
    proj, run1, v1 = _project(tmp_path, "P", "chromiq_default")
    run2 = proj.new_run()
    run2.ensure_dir()
    from tests.helpers.legacy_run_meta import (bind_run)
    bind_run(run2, "chromiq_tight", None)
    v2 = _date(run2, 0.5)
    dates = _snapshot(v1.dir, v2.dir)
    bound = (run_limits(run1, None).set_id, run_limits(run2, None).set_id)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp, "chromiq_quick")
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        _press(dlg, qapp)
    finally:
        dlg.close()
    docs = _reports(Path(proj.root) / "reports")
    assert len(docs) == 1, docs
    block = recorded_document(_read(docs[0]))
    assert block["role"] == "document"
    assert block["compliance"]["set_id"] == "chromiq_quick"
    ms = block["measurements"]
    assert len(ms) == 2
    assert {m[JUDGED_KEY]["compliance"]["set_id"] for m in ms} == {
        "chromiq_quick"}, ms
    assert _snapshot(v1.dir, v2.dir) == dates, "a date's folder was written"
    assert (run_limits(run1, None).set_id,
            run_limits(run2, None).set_id) == bound, "a run was re-bound"


def test_a_report_across_runs_writes_nothing_into_any_date(tmp_path, qapp):
    """K31 turned this test round (it was
    `test_a_date_whose_run_has_the_reports_set_keeps_its_record`). Knut,
    5801677743: *"When a report covers more than one run or project, should
    GENERATE REPORT write anything into the dates' own folders? Answer: no."*
    Neither date's folder gains a file, the window's own run's included.

    MUTATION: write a record into the window's own run's date again (the
    pre-K31 `_records_across_places`) and this goes red."""
    from workflow.measurement_report import is_verdict_record
    proj, run1, v1 = _project(tmp_path, "P", "chromiq_default")
    run2 = proj.new_run()
    run2.ensure_dir()
    from tests.helpers.legacy_run_meta import (bind_run)
    bind_run(run2, "chromiq_tight", None)
    v2 = _date(run2, 0.5)
    other = _snapshot(v2.dir)
    before = set(_reports(v1.dir / "reports"))
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        assert dlg._set_combo.currentData() == "chromiq_default"
        _press(dlg, qapp)
    finally:
        dlg.close()
    new = sorted(set(_reports(v1.dir / "reports")) - before)
    assert new == [], new
    assert not any(is_verdict_record(_read(p))
                   for p in _reports(v1.dir / "reports"))
    assert _snapshot(v2.dir) == other


def test_the_saved_report_shows_the_verdicts_it_recorded(tmp_path, qapp):
    """Reopened from the OTHER run's window, the report's page shows the
    verdicts the document recorded, never its runs' own records, and never
    a recalculation.

    MUTATION, proven red: make `recorded_judgement` return None (the page
    judges every row again, and the word written into the file is not the
    word shown)."""
    from workflow.measurement_report import JUDGED_KEY
    proj, run1, v1 = _project(tmp_path, "P", "chromiq_default")
    run2 = proj.new_run()
    run2.ensure_dir()
    from tests.helpers.legacy_run_meta import (bind_run)
    bind_run(run2, "chromiq_tight", None)
    v2 = _date(run2, 0.5)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp, "chromiq_quick")
        _press(dlg, qapp)
        doc_id = dlg._loaded_doc_id
    finally:
        dlg.close()
    path = _reports(Path(proj.root) / "reports")[0]
    body = _read(path)
    # A WORD ONLY THE FILE CAN KNOW: the recorded overall of run2's date is
    # swapped for its opposite, so a page that recalculates says the other.
    for m in body["document"]["measurements"]:
        if str(v2.dir) == m["dir"]:
            v = m[JUDGED_KEY]["verdict"]
            v["overall"] = "PASS" if v["overall"] != "PASS" else "FAIL"
            want = v["overall"]
    path.write_text(json.dumps(body), encoding="utf-8")
    dlg = _window(_settings(), v2.measurement_ti3, qapp, "verification")
    try:
        i = dlg._saved_combo.findData(doc_id)
        assert i > 0, _rows(dlg)
        dlg._saved_combo.setCurrentIndex(i)
        qapp.processEvents()
        row = next(r for r in dlg._runs_for_report()
                   if r.get("_origin_dir") == str(v2.dir))
        assert row["compliance"]["set_id"] == "chromiq_quick"
        assert dlg._column_summary(row).word == want
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 2. across projects
# --------------------------------------------------------------------------
def test_a_report_across_projects_lives_in_the_folder_across_them(
        tmp_path, qapp):
    """Two projects side by side: the report goes to `<folder>/reports/`,
    made by this write and not before, nothing goes into either project,
    it is listed under "Reports including multiple projects" and counted,
    and a third project's window is not offered it.

    MUTATION, proven red: compare a document outside every project by
    `_coverage_key` alone in `shared_documents` (R's window lists the report
    of P and Q, because every project has a `runs/run1`)."""
    p, prun, pv = _project(tmp_path, "P")
    q, qrun, qv = _project(tmp_path, "Q")
    r, rrun, rv = _project(tmp_path, "R")
    across = tmp_path / "reports"
    projects = _snapshot(p.root, q.root)
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(qv.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        assert not across.exists()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        # P's and Q's own reports of their dates, before
        assert "Full colour check: 2" in dlg._type_blurb_full, \
            dlg._type_blurb_full
        _press(dlg, qapp)
        assert len(_reports(across)) == 1
        assert "Reports including multiple projects" in _headings(dlg)
        assert "Full colour check: 3" in dlg._type_blurb_full, \
            dlg._type_blurb_full
    finally:
        dlg.close()
    # P's own date got its record (P's run has the report's set); nothing
    # else in either project changed.
    changed = {k for k, v in _snapshot(p.root, q.root).items()
               if projects.get(k) != v}
    assert all(str(pv.dir / "reports") in k for k in changed), changed
    dlg = _window(_settings(), rv.measurement_ti3, qapp, "verification")
    try:
        assert all(e.get("file") is None
                   or Path(e["file"]).parent != across
                   for e in dlg._saved_documents(dlg._run_ctx.run)), \
            "R's window is offered a report of P and Q"
    finally:
        dlg.close()


def test_projects_in_two_folders_share_the_chromiq_folder(tmp_path, qapp,
                                                         monkeypatch):
    """SUPERSEDED BY K30 (Knut, 5798461562): *"I propose that the ChromIQ
    default folder is always used, in this situation, no matter if one of
    the projects, or both, are kept is sub folders of ChromIQ default
    folder."* Two projects in two folders are no longer refused: their
    report is one document in `<ChromIQ folder>/reports/`, it is listed
    from there, and nothing is written into the folders' common ancestor.

    MUTATION, proven red: put the two-folders check (`len(parents) > 1`)
    back in `across_places_refusal` (Generate is greyed again), or return
    the common ancestor in `document_home` (the file lands in tmp_path)."""
    import workflow.measurement_report as MR
    chromiq = tmp_path / "ChromIQ"
    chromiq.mkdir()
    monkeypatch.setattr(MR, "chromiq_folder", lambda: chromiq)
    p, _prun, pv = _project(tmp_path / "one", "P")
    q, _qrun, qv = _project(tmp_path / "two", "Q")
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(qv.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        _press(dlg, qapp)
        assert len(_reports(chromiq / "reports")) == 1
        assert "Reports including multiple projects" in _headings(dlg)
    finally:
        dlg.close()
    assert not (tmp_path / "reports").exists()


def test_update_and_delete_of_a_report_across_projects(tmp_path, qapp):
    """Update rewrites the document in place, its old content copied into
    `reports/old/<stamp>/` first (D23); Delete moves it into `old/<stamp>/`
    beside the folder, and every date keeps its own files.

    MUTATION, proven red: take `keep_doc_file` as False in
    `_write_the_document` (the Update writes a second file and the first is
    removed, so the document's file name changes under it)."""
    p, _prun, pv = _project(tmp_path, "P")
    q, _qrun, qv = _project(tmp_path, "Q")
    across = tmp_path / "reports"
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(qv.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
        first = _reports(across)
        assert len(first) == 1
        doc_id = dlg._loaded_doc_id
        dlg._ask_update_or_create_new = lambda: "update"
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _press(dlg, qapp)
        assert _reports(across) == first, _reports(across)
        assert dlg._loaded_doc_id == doc_id
        assert list((across / "old").glob("*/report_*.json"))
        assert _read(first[0])["document"].get("updated")
        dates = _snapshot(qv.dir)
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(doc_id))
        qapp.processEvents()
        dlg._on_delete_report()
        qapp.processEvents()
    finally:
        dlg.close()
    assert _reports(across) == []
    assert list((tmp_path / "old").glob("*/report_*.json"))
    assert _snapshot(qv.dir) == dates


# --------------------------------------------------------------------------
# 3. Calibration across projects
# --------------------------------------------------------------------------
def test_a_calibration_report_across_projects(tmp_path, qapp):
    """Run type Calibration, two projects' calibrations: one document in the
    folder across projects, named "All cals", and nothing written into
    either `cal/` (a calibration binds no set, so no record can be known
    not to contradict it).

    MUTATION, proven red: make `_records_across_places` return *reports*
    unfiltered (P's `cal/reports/` gets a record)."""
    p, pti3 = _project_with_cal(tmp_path, "P")
    q, qti3 = _project_with_cal(tmp_path, "Q")
    cals = _snapshot(p.calibration.dir, q.calibration.dir)
    dlg = _window(_settings(), pti3, qapp)
    try:
        dlg._add_source(qti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        _press(dlg, qapp)
        rows = [t for t, _k in _rows(dlg)]
        assert any(" · All cals" in t for t in rows), rows
    finally:
        dlg.close()
    assert len(_reports(tmp_path / "reports")) == 1
    assert _snapshot(p.calibration.dir, q.calibration.dir) == cals


# --------------------------------------------------------------------------
# 4. one measurement, one row, when a second source gathers it again
# --------------------------------------------------------------------------
def test_a_sheet_another_source_gathers_again_is_one_row(tmp_path, qapp):
    """A profiling sheet gathers every run's sheet of its project for the
    trend (#40), so adding run 2's sheet to run 1's window brought run 1's
    sheet in a second time. G7 reaches that state by itself: a report across
    runs opened from run 1 loads run 2's sheet (it is shown whole), and run 1
    was listed twice.

    MUTATION, proven red: drop the `have` filter in `_append_source` (run 1's
    sheet is two rows)."""
    from tests.test_a_report_belongs_to_the_run_it_was_asked_from import (
        _two_run_project, _window_on)
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _press(dlg, qapp)                     # run 1 has a report now
    finally:
        dlg.close()
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        dlg._add_source(run2.measurement_ti3)
        qapp.processEvents()
        keys = [dlg._run_key(r) for r in dlg._history]
        assert len(keys) == len(set(keys)) == 2, keys
    finally:
        dlg.close()
