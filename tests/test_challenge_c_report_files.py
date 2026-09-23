"""Challenge C of beta 39: reports, renames, renumbering and read-only folders.

Tester C drove the Measurement Report window on the demo pack and found
(`~/Desktop/ChromIQ-beta39-proof/challenge-C-files/REPORT.md`):

1. an Update of a report across projects, from the side that could not find
   one of its measurements (the other project renamed), narrowed the report
   to what it found, archived the whole one and rewrote that date's record;
2. after a rename, the reports in ``<ChromIQ folder>/reports/`` kept the old
   folder name and `resolve_recorded_folder` never found the renamed project
   ("1 of the 3");
3. the renamed side's Report Scope named the chart by its old name;
4. the bar's Delete of a profile run renumbered the later runs, and the
   reports that name runs by number were not rewritten ("Multiple runs",
   "1 of the 5");
7. Delete Selected Report in a read-only folder copied the report into old/
   and left the original, under a raw "[Errno 13] …";
8. Update in a read-only folder said only "The log says why.";
11. a date whose .ti3 was deleted still counted, and an Update made it the
   only measurement.

Every test names the mutation that turns it red; each was run red with
``-n 0`` (REPORT.md in ~/Desktop/ChromIQ-beta39-proof/challenge-C-fixes/).
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from tests.test_calibration_reports import _settings, _window  # noqa: E402
from tests.test_g7_reports_across_places import (              # noqa: E402
    _new_report_of_everything, _press, _project, _read, _reports, _snapshot)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def said(monkeypatch):
    """Every box the window shows, as ``(kind, title, text)``, answered OK."""
    import ui.warning_sign as ws
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    out: list = []
    monkeypatch.setattr(ws, "inform",
                        lambda _p, t, x, *a, **k: out.append(("inform", t, x)))
    monkeypatch.setattr(ws, "warn",
                        lambda _p, t, x, *a, **k: out.append(("warn", t, x)))
    monkeypatch.setattr(MeasurementReportDialog, "_confirm",
                        lambda self, *a, **k: True)
    return out


def _across(tmp_path, qapp):
    """P and Q beside each other, each with one dated verification, and ONE
    report across them written by the window (in ``<tmp>/reports``)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    p, _pr, pv = _project(tmp_path, "P")
    q, _qr, qv = _project(tmp_path, "Q")
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        dlg._add_source(qv.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    doc = _reports(tmp_path / "reports")
    assert len(doc) == 1
    assert MeasurementReportDialog
    return p, pv, q, qv, doc[0]


def _update_from(ti3, qapp, *, leave_out_answer=None):
    """Open a window on *ti3*, which opens on the latest report, and press
    Update on it (a setting changed). Returns the window, closed."""
    dlg = _window(_settings(), ti3, qapp, "verification")
    try:
        assert dlg._loaded_doc_id, "the window did not open on a report"
        dlg._ask_update_or_create_new = lambda: "update"
        if leave_out_answer is not None:
            dlg._ask_leave_out = lambda title, body: (
                dlg.__dict__.setdefault("_asked", []).append((title, body))
                or leave_out_answer)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _press(dlg, qapp)
        return dlg
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# #1: an Update never narrows a report to what one side can find
# --------------------------------------------------------------------------
def test_an_update_that_cannot_find_a_covered_project_is_refused(
        tmp_path, qapp, said):
    """Q moved away (the tester's renamed project, from the side that could
    not find it): Update from P's side writes NOTHING, archives nothing, and
    says which measurement cannot be found and why.

    MUTATION, proven red: make `update_losses` return ``[]`` (the Update
    archives the report and rewrites it about P's date alone)."""
    from workflow import measurement_messages as M
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    shutil.move(str(q.root), str(tmp_path.parent / f"{tmp_path.name}-away"))
    before = _snapshot(tmp_path)
    _update_from(pv.measurement_ti3, qapp)
    assert _snapshot(tmp_path) == before, "the refused Update wrote something"
    title = M.CATALOGUE["M-REPORT-UPDATE-NOT-FOUND"].render(missing="")[0]
    hits = [x for k, t, x in said if t == title]
    assert hits, said
    assert "Q, run 1" in hits[0] and "ChromIQ cannot find this project" \
        in hits[0], hits[0]


def test_a_measurement_gone_from_disk_is_left_out_only_when_the_user_agrees(
        tmp_path, qapp, said):
    """#11: Q's measurement file deleted, Q still there. Update ASKS; Cancel
    writes nothing; "Update without them" writes the report without it.

    MUTATION, proven red: make `_update_leaves_out` return ``set()`` without
    asking (the first press rewrites the report and asks nothing)."""
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    qv.measurement_ti3.unlink()
    before = _snapshot(tmp_path)
    dlg = _update_from(pv.measurement_ti3, qapp, leave_out_answer=False)
    asked = dlg.__dict__.get("_asked") or []
    assert asked and "no longer on disk" in asked[0][0], asked
    assert "Q, run 1" in asked[0][1] and \
        "its measurement file is no longer in its folder" in asked[0][1]
    assert _snapshot(tmp_path) == before, "a cancelled Update wrote something"
    _update_from(pv.measurement_ti3, qapp, leave_out_answer=True)
    # the document now covers P's date alone, and the previous one is kept
    docs = [json.loads(f.read_text(encoding="utf-8"))
            for f in tmp_path.rglob("report_*.json") if "old" not in f.parts]
    mine = [d for d in docs if (d.get("document") or {}).get("updated")]
    assert mine, "the agreed Update wrote nothing"
    dirs = [m["dir"] for m in mine[0]["document"]["measurements"]]
    assert all("/Q/" not in d for d in dirs), dirs
    assert list(tmp_path.rglob("old/*/report_*.json")), "nothing archived"


# --------------------------------------------------------------------------
# #2: a rename rewrites the reports that name the project, and resolution
# finds a renamed project by its former name
# --------------------------------------------------------------------------
def test_a_rename_rewrites_every_report_that_names_the_project(tmp_path, qapp):
    """Q renamed to "Q New" the way ChromIQ renames (the name field and the
    folder-renamed window both end in `Project.rename`): the report in the
    folder across projects, and Q's own reports, name "Q-New"; P's reports
    name P as before; nothing is archived; no file of P changes except the
    document's list entry for Q.

    MUTATION, proven red: drop the `_rename_report_references` call at the
    end of `Project.rename` (the report across projects still names "Q")."""
    from core.file_manager import FileManager
    from tests.test_beta38_challenge_fixes import _Settings
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    p_before = _snapshot(p.root)
    FileManager(_Settings(tmp_path)).rename_existing_project(q.root, "Q New")
    new = tmp_path / "Q-New"
    assert new.is_dir()
    dirs = [m["dir"] for m in _read(doc)["document"]["measurements"]]
    assert any("/Q-New/runs/run1/verifications/" in d for d in dirs), dirs
    assert not any("/Q/" in d for d in dirs), dirs
    keys = [m["key"] for m in _read(doc)["document"]["measurements"]]
    assert all(k.startswith(m) for k, m in zip(keys, dirs)), keys
    for f in new.rglob("report_*.json"):
        text = f.read_text(encoding="utf-8")
        assert '"/Q/' not in text.replace(str(tmp_path), ""), f
        rep = json.loads(text)
        if rep.get("ti3"):
            assert rep["ti3"].startswith("Q-New"), rep["ti3"]
    assert not list(tmp_path.rglob("old")), "a rename archived something"
    assert _snapshot(p.root) == p_before or all(
        "/Q-New/" in v.decode() for k, v in _snapshot(p.root).items()
        if p_before.get(k) != v)


def test_a_duplicates_original_is_not_rewritten(tmp_path, qapp):
    """A Finder duplicate "Q copy" renamed to "Q-copy": its own reports now
    name "Q-copy", while the ORIGINAL Q beside it, and the report across P
    and Q, still name Q, because they are Q's.

    MUTATION, proven red: drop the ``_free`` test in
    `core.report_refs.rename_references_plan` (the report across P and Q is
    rewritten to name the copy)."""
    from core.file_manager import FileManager
    from tests.test_beta38_challenge_fixes import _Settings
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    shutil.copytree(q.root, tmp_path / "Q copy")
    before = _snapshot(q.root, tmp_path / "reports", p.root)
    FileManager(_Settings(tmp_path)).rename_existing_project(
        tmp_path / "Q copy", "Q copy")
    assert _snapshot(q.root, tmp_path / "reports", p.root) == before
    copy_reports = list((tmp_path / "Q-copy").rglob("report_*.json"))
    assert copy_reports
    for f in copy_reports:
        assert '/Q/runs' not in f.read_text(encoding="utf-8"), f


def test_a_renamed_project_is_found_by_its_former_name(tmp_path, qapp):
    """A project renamed before this fix (or whose reports could not be
    rewritten): the report still names "Q", the folder is "R", and R's
    project.json has Q in ``former_names``. P's window loads R's date.

    MUTATION, proven red: remove step 3b (`_projects_answering_to`) from
    `resolve_recorded_folder` (P's window holds P's date alone)."""
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    r = tmp_path / "R"
    q.root.rename(r)
    man = json.loads((r / "project.json").read_text(encoding="utf-8"))
    man["target_name"], man["former_names"] = "R", ["Q"]
    (r / "project.json").write_text(json.dumps(man), encoding="utf-8")
    for f in r.rglob("*"):
        if f.is_file() and f.name.startswith("Q"):
            f.rename(f.with_name("R" + f.name[1:]))
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        origins = {str(x.get("_origin_dir") or "") for x in dlg._history}
    finally:
        dlg.close()
    assert any(o.startswith(str(r)) for o in origins), origins


def test_the_scope_names_the_chart_by_the_projects_current_name(tmp_path):
    """#3: a report saved before a rename names its chart "Q-verify"; under
    the renamed project R (former name Q) the Scope prints "R-verify".

    MUTATION, proven red: take ``name = r.get("chart") or "?"`` in
    `report_scope` again."""
    from core.file_manager import Project
    from workflow.measurement_report import report_scope
    proj = Project.create(tmp_path / "R", "R")
    man = json.loads((proj.root / "project.json").read_text(encoding="utf-8"))
    man["former_names"] = ["Q"]
    (proj.root / "project.json").write_text(json.dumps(man), encoding="utf-8")
    d = proj.root / "runs" / "run1" / "verifications" / "2026-01-01_100000"
    d.mkdir(parents=True)
    sc = report_scope([{"chart": "Q-verify", "_origin_dir": str(d),
                        "created": "2026-01-01T10:00:00"}])
    assert [x["name"] for x in sc["profiles"]] == ["R-verify"], sc["profiles"]
    # a name that is not the project's is left alone
    sc = report_scope([{"chart": "Quality-chart", "_origin_dir": str(d),
                        "created": "2026-01-01T10:00:00"}])
    assert [x["name"] for x in sc["profiles"]] == ["Quality-chart"]


# --------------------------------------------------------------------------
# #4: the bar's Delete of a run renumbers the reports that name runs
# --------------------------------------------------------------------------
def _three_runs(tmp_path):
    """A project with three runs, each with a measured sheet and its own
    report, and one report across all three in ``<project>/reports``."""
    from core.file_manager import Project, RunMeta
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import (build_report, document_file,
                                             document_measurement_key,
                                             new_document_id, save_report,
                                             stamp_document)
    proj = Project.create(tmp_path / "P", "P")
    proj.new_run()
    proj.new_run()
    members = []
    for i, run in enumerate(proj.all_runs(), start=1):
        run.ensure_dir()
        if not run.meta_path.exists():
            run.save_meta(RunMeta.fresh(run.id))
        ti3 = run.dir / f"{run.stem}.ti3"
        ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        rep = build_report(ti3)
        rep["created"] = f"2026-0{i}-01T10:00:00"
        m = {"dir": str(run.dir), "created": rep["created"], "ti3": ti3.name,
             "key": document_measurement_key(run.dir, rep["created"],
                                             ti3.name)}
        stamp_document(rep, doc_id=new_document_id(), created=rep["created"],
                       type_id="t0_printing_record", compliance=None,
                       detail=False, measurements=[m], scope="one_date")
        save_report(rep, run.dir)
        members.append(m)
    body = document_file(doc_id=new_document_id(), created="2026-05-01T10:00:00",
                         type_id="t0_printing_record", compliance=None,
                         detail=False, measurements=members,
                         scope="all_dates")
    save_report(body, proj.root)
    return proj


def _run_dirs(f) -> "list[str]":
    return [Path(m["dir"]).name
            for m in _read(f)["document"]["measurements"]]


def test_deleting_a_run_renumbers_the_reports_that_name_runs(tmp_path):
    """Run 2 deleted: run 3's own report (now in runs/run2) names runs/run2,
    and the report across the runs names run1, run2.deleted (the deleted
    one, which can never point at the run that took its number) and run2.

    MUTATION, proven red: drop the `_apply_report_references` call in
    `delete_run` (run 3's report still names runs/run3, the "Multiple runs"
    the tester saw)."""
    import core.run_delete as rd
    proj = _three_runs(tmp_path)
    plan = rd.plan_for(proj, _Target("run2"))
    assert plan.kind == rd.KIND_RUN, plan
    rd.delete_run(proj, plan)
    own = sorted((proj.root / "runs" / "run2" / "reports").glob("report_*"))
    assert own and _run_dirs(own[0]) == ["run2"], _run_dirs(own[0])
    across = sorted((proj.root / "reports").glob("report_*.json"))
    assert _run_dirs(across[0]) == ["run1", "run2.deleted", "run2"], \
        _run_dirs(across[0])
    keys = [m["key"] for m in _read(across[0])["document"]["measurements"]]
    assert "/runs/run2.deleted|" in keys[1], keys


def test_a_run_delete_whose_reports_cannot_follow_deletes_nothing(tmp_path):
    """A report that must be renumbered is read-only: the delete is refused
    BEFORE anything moves, and says why.

    MUTATION, proven red: drop the `_unwritable(refs)` refusal in
    `delete_run` (run 2 goes to the Trash and run 3's report keeps naming
    run 3)."""
    import core.run_delete as rd
    proj = _three_runs(tmp_path)
    locked = proj.root / "reports"
    before = _snapshot(proj.root)
    os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
    try:
        plan = rd.plan_for(proj, _Target("run2"))
        with pytest.raises(rd.DeleteFailed) as err:
            rd.delete_run(proj, plan)
    finally:
        os.chmod(locked, stat.S_IRWXU)
    assert "Nothing was deleted" in err.value.reason
    assert _snapshot(proj.root) == before


class _Target:
    def __init__(self, profile_run):
        self.profile_run = profile_run
        self.run_type = "profiling"
        self.verification_id = ""

    def is_verification(self):
        return False


# --------------------------------------------------------------------------
# #7 and #8: read-only folders
# --------------------------------------------------------------------------
def test_moving_report_files_is_all_or_nothing(tmp_path):
    """Two files, the second in a read-only folder: NEITHER moves, no old/
    folder is left behind, and the folder that stopped it is named.

    MUTATION, proven red: remove the source-folder pre-check AND the
    put-back loop in `move_report_files`, which is what `shutil.move` one
    file at a time did (the first file is in old/, the second is not)."""
    from core.file_manager import move_report_files
    a, b = tmp_path / "A" / "reports", tmp_path / "B" / "reports"
    for d in (a, b):
        d.mkdir(parents=True)
        (d / "report_x.json").write_text(d.parent.name, encoding="utf-8")
    dest = tmp_path / "old" / "stamp"
    os.chmod(b, stat.S_IRUSR | stat.S_IXUSR)
    try:
        moved, stuck = move_report_files(
            [a / "report_x.json", b / "report_x.json"], dest)
    finally:
        os.chmod(b, stat.S_IRWXU)
    assert moved == [] and stuck == b, (moved, stuck)
    assert (a / "report_x.json").is_file() and (b / "report_x.json").is_file()
    assert not (tmp_path / "old").exists()
    moved, stuck = move_report_files([a / "report_x.json",
                                      b / "report_x.json"], dest)
    assert stuck is None
    assert moved == [dest / "report_x.json", dest / "report_x_1.json"], moved
    assert not (a / "report_x.json").exists()


def test_delete_in_a_read_only_folder_moves_nothing_and_says_why(
        tmp_path, qapp, said):
    """#7, the tester's steps: a report across dates in a read-only
    ``verifications/reports``; Delete Selected Report leaves it where it
    was, makes no copy in old/, and shows M-REPORT-DELETE-FAILED naming the
    folder, never "[Errno 13]".

    MUTATION, proven red: put back ``shutil.move`` in `_on_delete_report`
    (the report is copied into old/ and stays, and the box says
    "[Errno 13] Permission denied")."""
    from workflow import measurement_messages as M
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    ro = doc.parent
    before = _snapshot(tmp_path)
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
    try:
        assert dlg._loaded_doc_id
        dlg._on_delete_report()
        qapp.processEvents()
    finally:
        os.chmod(ro, stat.S_IRWXU)
        dlg.close()
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "old").exists()
    title = M.CATALOGUE["M-REPORT-DELETE-FAILED"].render(folder="")[0]
    hits = [x for k, t, x in said if t == title]
    assert hits and str(ro) in hits[0], said
    assert not any("Errno" in x for _k, _t, x in said), said


def test_an_update_in_a_read_only_folder_names_the_folder(tmp_path, qapp,
                                                          said):
    """#8: Update in a read-only folder writes nothing (as before) and the
    box names the folder and the remedy (M-REPORT-NOT-WRITABLE).

    MUTATION, proven red: drop the M-REPORT-NOT-WRITABLE branch of
    `_say_generated` (the box says only "The log says why.")."""
    import ui.dialogs.measurement_report_dialog as mrd
    from workflow import measurement_messages as M
    p, pv, q, qv, doc = _across(tmp_path, qapp)
    ro = doc.parent
    # the real `_say_generated`, which the g7 helper file does not stub here
    assert mrd.MeasurementReportDialog._say_generated
    before = _snapshot(tmp_path)
    os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
    try:
        _update_from(pv.measurement_ti3, qapp)
    finally:
        os.chmod(ro, stat.S_IRWXU)
    assert _snapshot(tmp_path) == before
    title = M.CATALOGUE["M-REPORT-NOT-WRITABLE"].render(folders="")[0]
    hits = [x for k, t, x in said if t == title]
    assert hits and str(ro.resolve()) in hits[0], said
