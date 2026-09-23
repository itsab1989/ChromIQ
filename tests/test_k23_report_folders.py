"""K23, Knut on #182, 2026-09-23 (comments 5787117741, 5787131342,
5787380408): WHERE a report lives, and what "Already generated" and "Report
shown" count and list.

* one measurement: its own folder's ``reports/`` (a dated verification's, or
  the run's own for a profiling sheet);
* several dates of ONE profile run: ``runN/verifications/reports/``;
* measurements of several profile runs: ``<project>/reports/``.

Accepted in the same exchange: every dated verification keeps its own small
verdict record in its own folder, because the lock and the comparability of
the dates are built on it, and that record "is not a report, it is never
listed or counted". Reports already on users' disks stay where they are and
are shown and counted by what they cover.

**K31 (Knut, 5801677743, beta 40) RETIRED THE RECORDS.** *"Should a report of
several measurements stop writing verdict records altogether?"* *"Agreed."*
The folder rule above is unchanged; a report of several measurements is now
ONE file in its home whose list of measurements carries each one's verdict,
and nothing is written into the dates. Records already on disk are read-only
history of their report. The guards below were retargeted to that.

Every test names the mutation that turns it red; each was applied and seen
red before this file was committed (see the K23 REPORT.md on the Desktop).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from tests.test_a_generated_report_is_one_document import (    # noqa: E402
    _dialog, _every_measurement, _files, _messy_project, _only_this_measurement,
    _start_fresh)
from workflow.measurement_report import (                       # noqa: E402
    KIND_VERIFICATION, REPORT_TYPE_FULL, ROLE_DOCUMENT, ROLE_RECORD,
    document_file, document_home, document_measurement_key, document_role,
    generated_report_types, is_verdict_record, new_document_id,
    project_relative, save_report, stamp_document)


def _home_files(run):
    return sorted((run.verifications_dir / "reports").glob("report_*.json"))


def _read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _press(dlg, qapp):
    dlg._say_generated = lambda saved, failed: None
    dlg._on_generate_report()
    qapp.processEvents()


def _counts(dlg):
    run = dlg._run_ctx.run
    kind = dlg._window_kind()
    return generated_report_types(
        run, kind, "",
        measurement_dirs=dlg._measurement_dirs_of_the_list(run, kind))


def _listed(dlg):
    return dlg._saved_documents(dlg._run_ctx.run)


# ---------------------------------------------------------------------------
# the rule itself
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dirs,where", [
    (["P/runs/run1/verifications/2026-01-01_000000"],
     "P/runs/run1/verifications/2026-01-01_000000/reports"),
    (["P/runs/run1/verifications/2026-01-01_000000",
      "P/runs/run1/verifications/2026-01-02_000000"],
     "P/runs/run1/verifications/reports"),
    (["P/runs/run1/verifications/2026-01-01_000000",
      "P/runs/run2/verifications/2026-01-02_000000"], "P/reports"),
    (["P/runs/run1"], "P/runs/run1/reports"),
    (["P/runs/run1", "P/runs/run2"], "P/reports"),
])
def test_where_a_document_lives(tmp_path, dirs, where):
    """Knut's table, row by row.

    MUTATION: answer `<run>/verifications/reports` for several runs' dates,
    or the date's own folder for several dates, and a row goes red."""
    got = document_home([tmp_path / d for d in dirs])
    assert got == tmp_path / where, got


def test_a_verdict_record_is_told_apart_on_disk():
    """MUTATION: let `document_role` read a top-level key instead of the
    block's, and the record is not a record: red."""
    rec = stamp_document({}, doc_id="doc_x", created="c", type_id="t",
                         compliance=None, detail=False, measurements=[],
                         role=ROLE_RECORD)
    one = stamp_document({}, doc_id="doc_y", created="c", type_id="t",
                         compliance=None, detail=False, measurements=[])
    doc = document_file(doc_id="doc_x", created="c", type_id="t",
                        compliance=None, detail=False, measurements=[])
    assert is_verdict_record(rec) and not is_verdict_record(one)
    assert document_role(doc) == ROLE_DOCUMENT and not is_verdict_record(doc)
    assert "role" not in one["document"], "a one-date file must stay as before"


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
def test_several_dates_write_one_document_file_and_no_record(
        tmp_path, qapp):
    """K31: one file in `runN/verifications/reports/`, carrying each date's
    verdict, and NOTHING in the dates' own folders (it was
    `..._and_a_record_per_date`).

    MUTATION: write a record into each date again, or leave `JUDGED_KEY`
    off the document's measurements, or skip the document file, and this
    goes red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        before = set(_files(run))
        _press(dlg, qapp)
        written = sorted(set(_files(run)) - before)
        assert written == [], written
        homes = _home_files(run)
        assert len(homes) == 1, homes
        body = _read(homes[0])
        assert document_role(body) == ROLE_DOCUMENT
        assert len(body["document"]["measurements"]) == 2
        assert all(m.get("judged") for m in body["document"]["measurements"])
        assert "verdict" not in body, "the document file carries no measurement"
    finally:
        dlg.close()


def test_one_date_is_written_in_that_dates_folder_as_before(tmp_path, qapp):
    """MUTATION: give a one-measurement document a document file (take
    `several` as True), and this goes red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _only_this_measurement(dlg, qapp)
        before = set(_files(run))
        _press(dlg, qapp)
        written = sorted(set(_files(run)) - before)
        assert len(written) == 1 and str(vs[-1].dir) in written[0], written
        assert document_role(_read(written[0])) == ""
        assert not _home_files(run)
    finally:
        dlg.close()


def test_the_pulldown_and_the_line_count_a_document_of_several_dates_once(
        tmp_path, qapp):
    """One entry, one count, and (K31) the entry is its own file, with no
    records as members: the page is drawn from the dates' own rows and the
    document's recorded verdicts.

    MUTATION: list the document file twice (drop the `docs.get(key)` merge
    in `_saved_documents`), or count it in the counter's per-date walk as
    well, and this goes red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        before = dict(_counts(dlg))
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        n_before = len(_listed(dlg))
        _press(dlg, qapp)
        after = _counts(dlg)
        added = {k: after.get(k, 0) - before.get(k, 0) for k in after}
        assert sum(added.values()) == 1, (before, after)
        assert len(_listed(dlg)) == n_before + 1
        entry = next(e for e in _listed(dlg) if e["key"] == dlg._loaded_doc_id)
        assert entry.get("file") and entry["members"] == [], entry
        assert len(entry["doc"]["measurements"]) == 2
    finally:
        dlg.close()


def test_a_deleted_document_leaves_nothing_behind_in_the_dates(
        tmp_path, qapp):
    """K31: a report of several dates wrote nothing into the dates, so its
    Delete leaves the dates exactly as they were and the count goes back
    (it was `..._leaves_its_records_unlisted_and_uncounted`).

    MUTATION: write a record into each date again and this goes red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    dlg._confirm = lambda t, b: True
    try:
        base = sum(_counts(dlg).values())
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        _press(dlg, qapp)
        key = dlg._loaded_doc_id
        docs = _listed(dlg)
        dlg._saved_combo.setCurrentIndex(
            1 + next(i for i, d in enumerate(docs) if d["key"] == key))
        qapp.processEvents()
        dlg._on_delete_report()
        qapp.processEvents()
        assert all(d["key"] != key for d in _listed(dlg))
        assert sum(_counts(dlg).values()) == base
        recs = [p for p in _files(run) if is_verdict_record(_read(p))]
        assert recs == [], recs
    finally:
        dlg.close()


def test_a_read_only_home_writes_nothing(tmp_path, qapp):
    """All or nothing reaches the document file's folder.

    MUTATION: drop the home check from the pre-flight, and the press tries
    the document file and says it saved something: red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    run.verifications_dir.chmod(0o555)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        before = set(_files(run))
        _press(dlg, qapp)
        assert set(_files(run)) == before
    finally:
        run.verifications_dir.chmod(0o755)
        dlg.close()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def _update(dlg, qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_generate_report_asks_what_to_do import _press as _button
    dlg._settings_touched()
    qapp.processEvents()
    dlg._ask_update_or_create_new = lambda: "update"
    monkeypatch.setattr(QMessageBox, "exec", _button("Update"))
    _press(dlg, qapp)


def test_update_rewrites_the_document_file_in_place_and_archives_it(
        tmp_path, qapp, monkeypatch):
    """D23 for the new file: copied into old/ first, then rewritten under
    its own name.

    MUTATION: leave `old_doc_file` out of the archive list: red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=3)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        _press(dlg, qapp)
        home = _home_files(run)
        assert len(home) == 1
        dlg._hidden_runs.add(dlg._run_key(dlg._history[0]))
        _update(dlg, qapp, monkeypatch)
        assert _home_files(run) == home, "the document file was not kept"
        assert len(_read(home[0])["document"]["measurements"]) == 2
        old = list((run.verifications_dir / "reports" / "old").glob(
            "*/report_*.json"))
        assert [p.name for p in old] == [home[0].name], old
    finally:
        dlg.close()


def test_update_to_one_date_retires_the_document_file_and_back(
        tmp_path, qapp, monkeypatch):
    """Narrowed to one date the document IS that date's file; widened again
    it has a document file again, and (K31) the date's file of it is retired
    into that date's `reports/old/` (a report of one date updated to cover
    more dates becomes a report of those dates).

    MUTATION: skip the retirement of the files the new shape no longer has
    (`retire` in `_write_the_document`), and this goes red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        _press(dlg, qapp)
        key = dlg._loaded_doc_id
        dlg._hidden_runs.add(dlg._run_key(dlg._history[0]))
        _update(dlg, qapp, monkeypatch)
        assert not _home_files(run), _home_files(run)
        entry = next(e for e in _listed(dlg) if e["key"] == key)
        assert not entry.get("file") and len(entry["members"]) == 1, entry
        r, name = entry["members"][0]
        assert document_role(_read(Path(r["_origin_dir"]) / "reports" / name)) \
            == ""
        one_date_file = Path(r["_origin_dir"]) / "reports" / name
        dlg._hidden_runs = set()
        _update(dlg, qapp, monkeypatch)
        assert len(_home_files(run)) == 1
        entry = next(e for e in _listed(dlg) if e["key"] == key)
        assert entry.get("file") and entry["members"] == [], entry
        assert sum(1 for e in _listed(dlg) if e["key"] == key) == 1
        assert not one_date_file.exists(), "the widened report kept its one-date file"
        assert list((one_date_file.parent / "old").glob("*/" + name))
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# legacy, shared folders, a moved project
# ---------------------------------------------------------------------------
def _legacy_two_date_document(run, vs):
    """What beta 36 wrote: one file per date, one id, no role, no document
    file."""
    from workflow.measurement_report import build_report
    doc_id = new_document_id()
    members = []
    for v in vs:
        rep = build_report(v.measurement_ti3)
        members.append({"dir": str(v.dir), "created": rep["created"],
                        "ti3": rep["ti3"],
                        "key": document_measurement_key(v.dir, rep["created"],
                                                        rep["ti3"])})
    paths = []
    for v in vs:
        rep = build_report(v.measurement_ti3)
        rep["report_type"] = REPORT_TYPE_FULL
        stamp_document(rep, doc_id=doc_id, created="2026-09-01T10:00:00",
                       type_id=REPORT_TYPE_FULL, compliance=None, detail=False,
                       measurements=members)
        paths.append(save_report(rep, v.dir))
    return doc_id, paths


def test_a_legacy_document_of_several_dates_counts_once_and_stays(
        tmp_path, qapp):
    """MUTATION: count a file with a block and no role as its own report
    (drop the id dedup), and it counts twice: red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        base = sum(_counts(dlg).values())
        n = len(_listed(dlg))
    finally:
        dlg.close()
    doc_id, paths = _legacy_two_date_document(run, vs)
    snap = {p: p.read_bytes() for p in paths}
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        assert sum(_counts(dlg).values()) == base + 1
        assert len(_listed(dlg)) == n + 1
        assert not _home_files(run)
        assert {p: p.read_bytes() for p in paths} == snap, "a legacy file moved"
    finally:
        dlg.close()


def _shared_document(where: Path, dirs, type_id=REPORT_TYPE_FULL):
    members = [{"dir": str(d), "created": "x", "ti3": "y.ti3",
                "key": document_measurement_key(d, "x", "y.ti3")} for d in dirs]
    body = document_file(doc_id=new_document_id(), created="2026-09-02T10:00:00",
                         type_id=type_id, compliance=None, detail=False,
                         measurements=members)
    return save_report(body, where)


def test_a_cross_run_document_is_listed_where_it_covers_and_nowhere_else(
        tmp_path, qapp):
    """`<project>/reports/` is read for the list's measurements, and a
    document there is shown only on a window whose list it covers.

    MUTATION: drop `covers & here` in `shared_documents`, and a run the
    document does not cover counts it: red."""
    from workflow.measurement_report import report_types_for_kind
    s, fm, run, vs = _messy_project(tmp_path, dates=1)
    proj = fm.project()
    run2 = proj.new_run()
    v2 = run2.new_verification()
    v2.ensure_dir()
    shutil.copy2(vs[0].measurement_ti3, v2.measurement_ti3)
    run3 = proj.new_run()
    v3 = run3.new_verification()
    v3.ensure_dir()
    shutil.copy2(vs[0].measurement_ti3, v3.measurement_ti3)
    assert REPORT_TYPE_FULL in report_types_for_kind(KIND_VERIFICATION)
    base1 = generated_report_types(run, KIND_VERIFICATION)
    base3 = generated_report_types(run3, KIND_VERIFICATION)
    path = _shared_document(Path(proj.root), [vs[0].dir, v2.dir])
    assert path.parent == Path(proj.root) / "reports"
    got1 = generated_report_types(run, KIND_VERIFICATION)
    got3 = generated_report_types(run3, KIND_VERIFICATION)
    assert got1.get(REPORT_TYPE_FULL, 0) == base1.get(REPORT_TYPE_FULL, 0) + 1
    assert got3 == base3, got3
    dlg = _dialog(s, vs[0].measurement_ti3, qapp)
    try:
        assert any(e.get("file") == path for e in _listed(dlg))
    finally:
        dlg.close()


def test_a_moved_project_still_finds_its_documents(tmp_path, qapp):
    """MUTATION: compare recorded folders by absolute path in
    `shared_documents` (drop `project_relative`), and the moved copy lists
    nothing: red."""
    s, fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        _press(dlg, qapp)
        key = dlg._loaded_doc_id
    finally:
        dlg.close()
    from core.file_manager import Project
    root = Path(fm.project().root)
    moved_root = tmp_path / "moved"
    moved_root.mkdir()
    shutil.copytree(root, moved_root / root.name)
    s.set("custom_output_path", str(moved_root))
    moved = Project.load(moved_root / root.name)
    r2 = moved.all_runs()[0]
    dlg = _dialog(s, r2.verifications()[-1].measurement_ti3, qapp)
    try:
        entry = next((e for e in _listed(dlg) if e["key"] == key), None)
        assert entry is not None and entry.get("file"), _listed(dlg)
        assert str(entry["file"]).startswith(str(moved_root))
    finally:
        dlg.close()


def test_a_moved_narrowed_document_ticks_what_it_covers(
        tmp_path, qapp, monkeypatch):
    """B8-810 R3A-2 in its several-dates form: three dates, Update to two,
    project moved. The document says two, and the moved copy ticks two.
    (Until K31 the date taken out kept a verdict record carrying the id.)

    MUTATION: drop the project-relative match in
    `_restore_the_documents_view`, and the moved copy ticks all three: red."""
    s, fm, run, vs = _messy_project(tmp_path, dates=3)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        _press(dlg, qapp)
        key = dlg._loaded_doc_id
        dlg._hidden_runs.add(dlg._run_key(dlg._history[0]))
        _update(dlg, qapp, monkeypatch)
        entry = next(e for e in _listed(dlg) if e["key"] == key)
        assert entry.get("file") and len(entry["doc"]["measurements"]) == 2
    finally:
        dlg.close()
    from core.file_manager import Project
    root = Path(fm.project().root)
    moved_root = tmp_path / "moved"
    moved_root.mkdir()
    shutil.copytree(root, moved_root / root.name)
    s.set("custom_output_path", str(moved_root))
    r2 = Project.load(moved_root / root.name).all_runs()[0]
    dlg = _dialog(s, r2.verifications()[-1].measurement_ti3, qapp)
    try:
        docs = _listed(dlg)
        dlg._saved_combo.setCurrentIndex(
            1 + next(i for i, d in enumerate(docs) if d["key"] == key))
        qapp.processEvents()
        assert len(dlg._runs_for_report()) == 2, [
            r.get("created") for r in dlg._runs_for_report()]
    finally:
        dlg.close()


def test_project_relative_names_a_folder_from_runs_down(tmp_path):
    assert project_relative(tmp_path / "A" / "runs" / "run1" / "verifications"
                            / "d") == "runs/run1/verifications/d"


def test_no_history_row_is_ever_made_from_a_shared_folder(tmp_path, qapp):
    """The trend, the lock and the recorded-verdict rows read per-folder
    files. A document file has no measurement and must never be a row.

    MUTATION: let `_gather_runs`' fall-back loop take `verifications/reports`
    as a date (drop the "reports" skip) AND put a .ti3 there: red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    home = run.verifications_dir / "reports"
    shutil.copy2(vs[0].measurement_ti3, home / vs[0].measurement_ti3.name)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        origins = {str(r.get("_origin_dir")) for r in dlg._history}
        assert str(home) not in origins and str(run.verifications_dir) \
            not in origins, origins
        assert len(dlg._history) == 2, len(dlg._history)
    finally:
        dlg.close()


def test_the_pdf_folder_agrees_with_where_the_document_lives(tmp_path, qapp):
    """MUTATION: change `document_home`'s several-dates answer, and the PDF's
    default folder and the document part company: red."""
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _dialog(s, vs[-1].measurement_ti3, qapp)
    try:
        _start_fresh(dlg, qapp)
        _every_measurement(dlg, qapp)
        dirs = [r["_origin_dir"] for r in dlg._runs_for_document()]
        assert dlg._report_dir() == document_home(dirs)
        _only_this_measurement(dlg, qapp)
        dirs = [r["_origin_dir"] for r in dlg._runs_for_document()]
        assert dlg._report_dir() == document_home(dirs)
    finally:
        dlg.close()


def test_the_cross_run_path_a_profiling_window_has(tmp_path, qapp):
    """The one real path that writes a document of several profile runs: a
    Profiling window gathers every run's profiling reports for the trend
    (#40), and with both runs ticked Generate is live. K23 puts that
    document in `<project>/reports/`, and since K31 nothing is written into
    either run.

    MUTATION: write a record into a member folder again, or put the
    document file in the run's own folder, and this goes red."""
    from tests.test_a_report_belongs_to_the_run_it_was_asked_from import (
        _two_run_project, _window_on)
    s, proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _press(dlg, qapp)
    finally:
        dlg.close()
    before1 = sorted((run1.dir / "reports").glob("report_*.json"))
    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        assert len(dlg._runs_for_document()) == 2
        assert dlg._generate_btn.isEnabled(), "the path is not live"
        _press(dlg, qapp)
    finally:
        dlg.close()
    assert sorted((run1.dir / "reports").glob("report_*.json")) == before1
    shared = sorted((Path(proj.root) / "reports").glob("report_*.json"))
    assert len(shared) == 1, shared
    recs = [p for p in (run2.dir / "reports").glob("report_*.json")
            if is_verdict_record(_read(p))]
    assert recs == [], recs
