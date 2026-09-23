"""K25 (#182, Knut 2026-09-23): "Report shown" is GROUPED, the names stay.

Knut, 5789532633: *"For both run type verification and run type profiling the
report names keep their names, but are grouped according to which measurement
sets have been added, where they come from, and what a report includes."*

* measurements of ONE profile run: no headings, as before;
* several runs of one project: headings Run1, Run2, ...;
* several projects: the project name, with Run1, Run2, ... under it;
* a report including measurements of more than one project: its own group,
  "Reports including multiple projects".

The headings are the Create Chart preset pulldown's kind (*"the group-headings
are the same type of feature that the preset pulldown list has"*): bold rows
with no data whose model item is disabled.

Every test names the mutation that turns it red; each was run.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtCore import Qt                                    # noqa: E402


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _dated(run, patches=None):
    """One dated verification of *run*, with its measurement and a one-date
    report carrying a document block, as the automatic report writes it."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", patches or _PATCHES),
                                 encoding="utf-8")
    _save_doc([v.dir], [v.measurement_ti3])
    return v


def _save_doc(folders, ti3s, *, when=None):
    """A report of *folders* written the way the window writes it: one
    folder, one file that is the report; several, a verdict record in the
    FIRST folder and a document file where `document_home` says (K23)."""
    from datetime import datetime, timedelta
    from workflow.measurement_report import (
        ROLE_RECORD, SCOPE_MULTIPLE_DATES, SCOPE_ONE_DATE, build_report,
        document_file, document_home, document_measurement_key,
        new_document_id, save_report, stamp_document)
    global _CLOCK
    _CLOCK += 1
    when = when or (datetime(2026, 12, 1, 10, 0, 0)
                    + timedelta(minutes=_CLOCK))
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD,
                                             KIND_VERIFICATION,
                                             measurement_dir_kind)
    tid = (REPORT_TYPE_FULL
           if measurement_dir_kind(folders[0]) == KIND_VERIFICATION
           else REPORT_TYPE_RECORD)
    reps = [build_report(t) for t in ti3s]
    members = [{"dir": str(f), "created": str(r.get("created") or ""),
                "ti3": t.name,
                "key": document_measurement_key(f, str(r.get("created") or ""),
                                                t.name)}
               for f, t, r in zip(folders, ti3s, reps)]
    doc_id = new_document_id(when)
    several = len(folders) > 1
    rep = reps[0]
    stamp_document(rep, doc_id=doc_id, created=when.isoformat(
        timespec="seconds"), type_id=tid, compliance=None, detail=False,
        measurements=members,
        scope=SCOPE_MULTIPLE_DATES if several else SCOPE_ONE_DATE,
        role=ROLE_RECORD if several else "")
    save_report(rep, folders[0])
    if several:
        body = document_file(doc_id=doc_id, created=when.isoformat(
            timespec="seconds"), type_id=tid, compliance=None, detail=False,
            measurements=members, scope=SCOPE_MULTIPLE_DATES)
        home = document_home(folders)
        save_report(body, home.parent)
        return home
    return None


_CLOCK = 0


def _two_runs(tmp_path):
    """Project P: run1 and run2, two dated verifications each."""
    from tests.test_import_measurement_module import _verify_env, _cgats, \
        _PATCHES
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    v1 = [_dated(run1), _dated(run1)]
    run2 = fm.project().new_run()
    run2.ensure_dir()
    run2.profile_icc.write_bytes(b"icc")
    run2.verifications_dir.mkdir(parents=True, exist_ok=True)
    run2.verify_chart_ti2.write_text(_cgats("CTI2", _PATCHES),
                                     encoding="utf-8")
    v2 = [_dated(run2), _dated(run2)]
    return s, fm, run1, run2, v1, v2


def _second_project(tmp_path):
    """Project Q beside P, one run, one dated verification."""
    from core.file_manager import Project
    from tests.test_import_measurement_module import _cgats, _PATCHES
    q = Project.create(tmp_path / "Q", "Q")
    run = q.current_run()
    run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text(_cgats("CTI2", _PATCHES), encoding="utf-8")
    return run, _dated(run)


def _dialog(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def _add(dlg, ti3, qapp):
    dlg._add_source(Path(ti3))
    qapp.processEvents()


def _rows(dlg):
    """``[(text, key or None, enabled)]`` below "New report…", separators
    left out."""
    combo = dlg._saved_combo
    out = []
    for i in range(1, combo.count()):
        text = combo.itemText(i)
        if not text and combo.itemData(i) is None:
            continue                                        # a separator
        item = combo.model().item(i)
        out.append((text, combo.itemData(i),
                    bool(item.isEnabled()) if item is not None else True))
    return out


def _headings(dlg):
    return [t.strip() for t, k, _e in _rows(dlg) if k is None]


def _group_of(dlg):
    """{entry key: [the headings above it, outermost first]}"""
    out, stack = {}, []
    for text, key, _e in _rows(dlg):
        if key is None:
            level = (len(text) - len(text.lstrip(" "))) // 4
            stack = stack[:level] + [text.strip()]
            continue
        out[str(key)] = list(stack)
    return out


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")


# --------------------------------------------------------------------------
# one run: no headings
# --------------------------------------------------------------------------
def test_one_run_is_not_grouped(tmp_path, qapp):
    """Knut: *"only measurements added for ONE verification run, tags
    become 'One date', then 'Multiple dates' and 'All dates' (as before)"*.

    MUTATION: `if len(listed) <= 1 or not docs:` in `_grouped_documents`
    changed to `if not docs:` puts a "Run1" heading over a one-run list, red.
    """
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    dlg = _dialog(s, v1[-1].measurement_ti3, qapp)
    try:
        assert len([k for _t, k, _e in _rows(dlg) if k]) == 2
        assert _headings(dlg) == [], _headings(dlg)
        assert dlg._saved_label.text() == "Report shown (run1):"
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# several runs of one project
# --------------------------------------------------------------------------
def test_several_runs_are_grouped_under_run_headings(tmp_path, qapp):
    """A run2 date added to a run1 window: Run1 and Run2, each report under
    the run it covers, and a report across the two runs in its own group.

    MUTATION: place every entry by the window's own run (`key = own` in
    `_grouped_documents`) and run2's report sits under Run1, red.
    """
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    _save_doc([v1[-1].dir, v2[0].dir],
              [v1[-1].measurement_ti3, v2[0].measurement_ti3])
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)             # New report…
        qapp.processEvents()
        _add(dlg, v2[1].measurement_ti3, qapp)
        heads = _headings(dlg)
        assert heads[:2] == ["Run1", "Run2"], heads
        assert "Reports including multiple runs" in heads, heads
        groups = _group_of(dlg)
        for key, above in groups.items():
            if key.startswith("id:"):
                continue
            want = "Run2" if str(run2.dir) in key else "Run1"
            assert above == [want], (key, above)
        multi = [k for k, a in groups.items()
                 if a == ["Reports including multiple runs"]]
        assert len(multi) == 1, groups
        assert dlg._saved_label.text() == "Report shown:"
    finally:
        dlg.close()


def test_a_heading_can_be_seen_and_not_chosen(tmp_path, qapp):
    """The Create Chart mechanism: bold, no data, disabled model item. And
    the row the list lands on is always a REPORT or "New report…".

    MUTATION: drop `item.setEnabled(False)` from `_add_report_group_heading`,
    red. MUTATION: land by position (`combo.setCurrentIndex(i + 1)` with `i`
    the entry's place in `docs`) and the landed row is a heading, red.
    """
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        _add(dlg, v2[1].measurement_ti3, qapp)
        combo = dlg._saved_combo
        heads = [i for i in range(combo.count())
                 if combo.itemData(i) is None and combo.itemText(i)]
        assert heads, "no heading, so this proves nothing"
        for i in heads:
            item = combo.model().item(i)
            assert not item.isEnabled(), combo.itemText(i)
            assert combo.itemData(i, Qt.ItemDataRole.FontRole).bold()
        # the landing: every document the list could land on
        for i in range(1, combo.count()):
            key = combo.itemData(i)
            if not key:
                continue
            dlg._loaded_doc_id = str(key)
            dlg._sync_saved_reports(dlg._run_ctx.run)
            assert combo.currentData() == key, (
                combo.currentIndex(), combo.currentText(), key)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# several projects
# --------------------------------------------------------------------------
def test_several_projects_are_grouped_by_project_then_run(tmp_path, qapp):
    """Project heading, run sub-heading, and a report across the two projects
    under "Reports including multiple projects", found where `document_home`
    files it (the projects' common folder).

    MUTATION: remove the `across` folders from `shared_report_folders` and
    the report across projects is written and never listed, red.
    """
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    qrun, qv = _second_project(tmp_path)
    home = _save_doc([v1[0].dir, qv.dir],
                     [v1[0].measurement_ti3, qv.measurement_ti3])
    assert home == tmp_path / "reports", home
    dlg = _dialog(s, v1[-1].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        _add(dlg, qv.measurement_ti3, qapp)
        rows = _rows(dlg)
        texts = [t for t, _k, _e in rows]
        assert texts[0] == "P", texts            # the window's own first
        assert "    Run1" in texts, texts
        assert "Q" in texts, texts
        assert "Reports including multiple projects" in texts, texts
        groups = _group_of(dlg)
        across = [k for k, a in groups.items()
                  if a == ["Reports including multiple projects"]]
        assert len(across) == 1, groups
        assert sum(a == ["Q", "Run1"] for a in groups.values()) == 1, groups
        assert sum(a == ["P", "Run1"] for a in groups.values()) == 2, groups
    finally:
        dlg.close()


def test_a_report_across_projects_is_counted(tmp_path):
    """The counter reads the same folders (K23), so it counts it too.

    MUTATION: as above, remove the `across` folders: 1 becomes 0, red.
    """
    from workflow.measurement_report import (generated_report_types,
                                             shared_report_folders)
    from tests.test_import_measurement_module import _verify_env
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    v = _dated(run1)
    _qrun, qv = _second_project(tmp_path)
    before = sum(generated_report_types(
        None, "verification", measurement_dirs=[v.dir, qv.dir]).values())
    _save_doc([v.dir, qv.dir], [v.measurement_ti3, qv.measurement_ti3])
    after = sum(generated_report_types(
        None, "verification", measurement_dirs=[v.dir, qv.dir]).values())
    assert after == before + 1, (before, after)
    assert tmp_path / "reports" in shared_report_folders([v.dir, qv.dir])


# --------------------------------------------------------------------------
# Profiling: every run's Printing records, and the window stays on its own
# --------------------------------------------------------------------------
def _profiling_project(tmp_path):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from tests.test_import_measurement_module import _verify_env
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    run1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                    encoding="utf-8")
    run2 = fm.project().new_run()
    run2.ensure_dir()
    run2.measurement_ti3.write_text(
        _cgats("CTI3", [(min(100.0, r + 3), g, b) for r, g, b in _PATCHES]),
        encoding="utf-8")
    return s, run1, run2


def test_profiling_lists_and_counts_every_run_s_printing_record(tmp_path,
                                                                 qapp):
    """Knut, 5789263863: *"'Already generated for this run' and 'Report
    shown' shall list and count every run's Printing records"* that the
    included measurements point to.

    MUTATION: put back the skip of the window's own source in
    `_measurement_dirs_of_the_list`, and run 2's record is neither listed
    nor counted, red.
    """
    from datetime import datetime
    s, run1, run2 = _profiling_project(tmp_path)
    _save_doc([run1.dir], [run1.measurement_ti3],
              when=datetime(2026, 12, 1, 9, 0, 0))
    _save_doc([run2.dir], [run2.measurement_ti3],
              when=datetime(2026, 12, 2, 9, 0, 0))
    dlg = _dialog(s, run1.measurement_ti3, qapp)
    try:
        keys = [str(k) for _t, k, _e in _rows(dlg) if k]
        assert len(keys) == 2, keys
        assert _headings(dlg) == ["Run1", "Run2"], _headings(dlg)
        assert "(2)" in dlg._type_blurb_full or ": 2" in dlg._type_blurb_full, \
            dlg._type_blurb_full
    finally:
        dlg.close()


def test_a_profiling_window_opens_on_its_own_run_s_report(tmp_path, qapp):
    """Run 2's record is NEWER; a window opened on run 1 still opens on run
    1's, and one opened on a run with no report of its own opens on "New
    report…", never on another run's.

    MUTATION: drop the `own in self._entry_places(d)` filter from
    `_open_on_the_latest_report` and the run-1 window opens on run 2's
    report, red.
    """
    from datetime import datetime
    s, run1, run2 = _profiling_project(tmp_path)
    _save_doc([run1.dir], [run1.measurement_ti3],
              when=datetime(2026, 12, 1, 9, 0, 0))
    _save_doc([run2.dir], [run2.measurement_ti3],
              when=datetime(2026, 12, 2, 9, 0, 0))
    dlg = _dialog(s, run1.measurement_ti3, qapp)
    try:
        entry = dlg._chosen_document(dlg._saved_documents(dlg._run_ctx.run))
        assert entry is not None
        assert all(str(r.get("_origin_dir")) == str(run1.dir)
                   for r, _n in entry["members"]), entry["members"]
        ticked = {str(r.get("_origin_dir")) for r in dlg._runs_for_report()}
        assert ticked == {str(run1.dir)}, ticked
    finally:
        dlg.close()


def test_the_automatic_record_of_one_measurement_ticks_one(tmp_path, qapp):
    """The report made at the end of a measurement covers that one
    measurement, so the window opened on it ticks one row and the trend has
    one point: the graphs show their "at least two measurements" text.
    (Already built; this pins it.)

    MUTATION: make `_restore_the_documents_view` return before it narrows
    `_hidden_runs` and both runs are ticked, red.
    """
    from datetime import datetime
    s, run1, run2 = _profiling_project(tmp_path)
    _save_doc([run1.dir], [run1.measurement_ti3],
              when=datetime(2026, 12, 1, 9, 0, 0))
    _save_doc([run2.dir], [run2.measurement_ti3],
              when=datetime(2026, 12, 2, 9, 0, 0))
    dlg = _dialog(s, run2.measurement_ti3, qapp)
    try:
        assert len(dlg._history) == 2, "both sheets are in the list"
        assert len(dlg._runs_for_report()) == 1
        assert len(dlg._trend_series) == 1, dlg._trend_series
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# the delete message and the guide
# --------------------------------------------------------------------------
def test_the_delete_message_says_measurement_s(tmp_path):
    """Knut, 5789263863 Q5: *"You could say 'the measurement(s) it
    describes'"*. Both bodies, since the file count does not say how many
    measurements a report describes.

    MUTATION: restore "the measurement it describes is not touched" in
    `M_REPORT_DELETE.body_one`, red.
    """
    from workflow import measurement_messages as M
    msg = M.CATALOGUE["M-REPORT-DELETE"]
    for n in (1, 3):
        _t, body = msg.render(what="x", n=n, where="y")
        assert "the measurement(s) it describes" in body, body


def test_the_file_guide_names_the_shared_report_folders():
    """Knut, Q6: *"Yes"* to rows for `verifications/reports/` and
    `<project>/reports/`.

    MUTATION: delete either row from `_files` in `ui/file_guide.py`, red.
    """
    import ui.file_guide as fg
    rows = [(f, where, text) for _g, items in fg._rows()
            for (f, where, text, _o) in items]
    wheres = {where for _f, where, _t in rows if _f == "report_*.json"}
    assert "runs/runN/verifications/reports" in wheres, wheres
    assert "reports (project folder)" in wheres, wheres
