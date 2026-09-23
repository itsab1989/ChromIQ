"""A report covering measurements of two runs is shown whole (beta 37, A-F1).

Round A, F1 (HIGH): a report in `<project>/reports` covering run1's
2026-12-15 and run2's 2026-12-22, opened from run2's window, showed only
2026-12-22 ticked and "1 verification run" on the page. Generate asked
"Nothing was changed for the selected report", and Update then rewrote it
about one date and retired the file that covered two.

The fix loads the measurements a selected document records that the window
has not loaded, and the page shows all of it. Until G7 (#182 beta 39) the
several-places rule then greyed Generate so an Update could not narrow the
document; since G7 a report across runs is written as a whole (one document
file, judged against its own set), so Generate is live and an Update keeps
every date.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_a_generated_report_is_one_document import (    # noqa: E402
    _dialog, _messy_project)
from workflow.measurement_report import (                       # noqa: E402
    REPORT_TYPE_FULL, ROLE_RECORD, SCOPE_MULTIPLE_DATES, build_report,
    document_file, document_measurement_key, new_document_id,
    project_relative, rewrite_report, save_report, stamp_document)


def _two_runs_and_a_report_across_them(tmp_path):
    """run1 and run2, one dated verification each, each with its own report,
    and ONE document across both in `<project>/reports` with a verdict record
    in each date, written the way the demo pack's `seed_report_folders`
    writes it."""
    s, fm, run1, vs = _messy_project(tmp_path, dates=1)
    proj = fm.project()
    run2 = proj.new_run()
    run2.ensure_dir()
    v2 = run2.new_verification()
    v2.ensure_dir()
    shutil.copy2(vs[0].measurement_ti3, v2.measurement_ti3)
    save_report(build_report(v2.measurement_ti3), v2.dir)
    folders = [vs[0].dir, v2.dir]
    when = "2026-12-30T09:00:00"
    reps = []
    for f in folders:
        first = sorted((f / "reports").glob("report_*.json"))[0]
        reps.append(json.loads(first.read_text(encoding="utf-8")))
    members = [{"dir": str(f), "created": str(r.get("created") or ""),
                "ti3": str(r.get("ti3") or ""),
                "key": document_measurement_key(f, str(r.get("created") or ""),
                                                str(r.get("ti3") or ""))}
               for f, r in zip(folders, reps)]
    doc_id = new_document_id()
    for f, rep in zip(folders, reps):
        rep.pop("document", None)
        stamp_document(rep, doc_id=doc_id, created=when,
                       type_id=REPORT_TYPE_FULL,
                       compliance=rep.get("compliance"), detail=False,
                       measurements=members, scope=SCOPE_MULTIPLE_DATES,
                       role=ROLE_RECORD)
        rewrite_report(f / "reports" / "report_2026-12-30_09-00-00.json", rep)
    home = Path(proj.root) / "reports"
    home.mkdir(parents=True, exist_ok=True)
    doc_path = rewrite_report(
        home / "report_2026-12-30_09-00-00.json",
        document_file(doc_id=doc_id, created=when, type_id=REPORT_TYPE_FULL,
                      compliance=reps[0].get("compliance"), detail=False,
                      measurements=members, scope=SCOPE_MULTIPLE_DATES))
    return s, run1, run2, vs[0], v2, doc_path, doc_id


def _snapshot(root: Path) -> dict:
    return {str(p): p.read_bytes() for p in sorted(root.rglob("report_*.json"))}


def test_opening_run2_on_the_cross_run_report_loads_run1s_date(tmp_path, qapp):
    """MUTATION (proved red 2026-09-23): make
    `_load_the_documents_other_measurements` return 0 at its top; the window
    then has one source, one date ticked, and Generate live."""
    s, run1, run2, v1, v2, doc_path, doc_id = \
        _two_runs_and_a_report_across_them(tmp_path)
    dlg = _dialog(s, v2.measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id == f"id:{doc_id}", (
            "the window opens on the newest report, which is the cross-run one")
        dirs = {project_relative(r.get("_origin_dir") or "")
                for r in dlg._runs_for_report()}
        assert project_relative(v1.dir) in dirs, (
            "run1's date the report covers is not in the report")
        assert project_relative(v2.dir) in dirs
        assert len(dlg._sources) == 2
        # G7: live, and an Update keeps both dates (the next test).
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
    finally:
        dlg.close()


def test_picking_the_report_in_the_list_loads_it_whole_and_writes_nothing(
        tmp_path, qapp):
    """The click path: a window that opened on another report, then the
    cross-run report picked from "Report shown". Picking writes nothing, and
    Generate answered Cancel writes nothing.

    MUTATION (proved red 2026-09-23): make
    `_load_the_documents_other_measurements` return 0 at its top."""
    s, run1, run2, v1, v2, doc_path, doc_id = \
        _two_runs_and_a_report_across_them(tmp_path)
    root = Path(doc_path).parent.parent
    before = _snapshot(root)
    dlg = _dialog(s, v2.measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)           # "New report…"
        qapp.processEvents()
        i = dlg._saved_combo.findData(f"id:{doc_id}")
        assert i > 0
        dlg._saved_combo.setCurrentIndex(i)
        qapp.processEvents()
        dirs = {project_relative(r.get("_origin_dir") or "")
                for r in dlg._runs_for_report()}
        assert {project_relative(v1.dir), project_relative(v2.dir)} <= dirs
        assert _snapshot(root) == before, "picking a report wrote a file"
        dlg._ask_update_or_create_new = lambda: "cancel"
        dlg._say_generated = lambda saved, failed: None
        dlg._on_generate_report()
        qapp.processEvents()
        assert _snapshot(root) == before, "Cancel wrote a file"
    finally:
        dlg.close()


def test_update_of_the_cross_run_report_keeps_both_dates(tmp_path, qapp):
    """G7 (#182 beta 39): the Update that A-F1 had to forbid now rewrites the
    document across both runs, in place, with its old file archived first
    (D23). K31: the dates' own folders are not touched at all, records an
    earlier ChromIQ wrote included (read-only history).

    MUTATION: write a record into a date again, or leave `JUDGED_KEY` off
    the document's measurements, and this goes red."""
    from workflow.measurement_report import JUDGED_KEY, recorded_document
    s, run1, run2, v1, v2, doc_path, doc_id = \
        _two_runs_and_a_report_across_them(tmp_path)
    # THE OTHER RUN'S date (the window is on run2): nothing is written there.
    verdicts = {}
    for f in (v1.dir, v2.dir):
        for p in (f / "reports").glob("report_*.json"):
            verdicts[str(p)] = p.read_bytes()
    dlg = _dialog(s, v2.measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id == f"id:{doc_id}"
        dlg._ask_update_or_create_new = lambda: "update"
        dlg._say_generated = lambda saved, failed: None
        dlg._on_generate_report()
        qapp.processEvents()
    finally:
        dlg.close()
    body = json.loads(Path(doc_path).read_text(encoding="utf-8"))
    block = recorded_document(body)
    assert block["id"] == doc_id and block.get("updated"), block
    ms = block["measurements"]
    assert {project_relative(m["dir"]) for m in ms} == {
        project_relative(v1.dir), project_relative(v2.dir)}
    assert all(isinstance(m.get(JUDGED_KEY), dict) for m in ms), ms
    assert list((Path(doc_path).parent / "old").glob("*/report_*.json")), (
        "the document file was rewritten without a copy in reports/old")
    for p, v in verdicts.items():
        assert Path(p).read_bytes() == v, f"{p} was touched by the Update"
    for f in (v1.dir, v2.dir):
        assert not list((f / "reports" / "old").glob("*/report_*.json")), (
            f"the Update archived something in {f}, which it never wrote")
    shared = sorted(Path(doc_path).parent.glob("report_*.json"))
    assert shared == [Path(doc_path)], shared


def test_new_report_unloads_what_the_cross_run_report_loaded(tmp_path, qapp):
    """Recheck R1 (before beta 37): the measurements a selected report loads
    belong to that report and leave with it. A run whose newest report covered
    two runs opened with the other run loaded and Generate greyed, and stayed
    so through "New report…" and every other report until Clear List.

    MUTATION: make `_drop_borrowed_sources` return False at its top and the
    window keeps two sources and a greyed Generate after "New report…": red.
    """
    s, run1, run2, v1, v2, doc_path, doc_id = \
        _two_runs_and_a_report_across_them(tmp_path)
    dlg = _dialog(s, v2.measurement_ti3, qapp)
    try:
        assert len(dlg._sources) == 2, "the premise: it opened whole"
        dlg._saved_combo.setCurrentIndex(0)           # "New report…"
        qapp.processEvents()
        assert len(dlg._sources) == 1, "the other run's measurement stayed"
        dirs = {project_relative(r.get("_origin_dir") or "")
                for r in dlg._history}
        assert project_relative(v1.dir) not in dirs
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        # and picking the cross-run report again loads it whole again
        i = dlg._saved_combo.findData(f"id:{doc_id}")
        dlg._saved_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert len(dlg._sources) == 2
    finally:
        dlg.close()
