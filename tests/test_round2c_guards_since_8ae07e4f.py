"""Round 2-C on the guards added since 8ae07e4f: the mutations they missed.

Every test here closes a hole a MUTATION proved: the mutant was applied, it
landed (a diff), and the whole everyday tier stayed green. Each docstring
names its mutant. Expected strings and types are typed, never read back from
the constant under test. Production code is not changed here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                      # noqa: E402

from workflow.measurement_report import (  # noqa: E402
    REPORT_TYPE_FULL, REPORT_TYPE_GREY, REPORT_TYPE_RECORD)


# ---------------------------------------------------------------------------
# K13: `_fit_to_kind` on the paths the new guards never walk
# ---------------------------------------------------------------------------
def test_a_saved_printing_record_of_a_verification_is_shown_as_one_and_a_new_report_from_it_is_not(
        tmp_path, qapp):
    """A beta-34 Printing record of a VERIFICATION is still on users' disks.
    K13's own comment: *"a saved report keeps the type it was written as and
    is shown as recorded; every answer from here on is what a NEW document
    would be"*. So picking it shows T4, and the moment a control moves (the
    document stops speaking and `_settings_touched` pins its type as
    `_sticky_type`) the type is fitted to the kind, and Create New writes a
    Full colour check, never a Printing record of a verification.

    MUTATIONS that left the whole everyday tier green: `_report_type_now`
    returning `sticky` unfitted (K13-09, the beta-35 line), and `_fit_to_kind`
    returning *tid* unconditionally (K13-08).
    """
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _files, _pick_key, _window)
    from tests.test_a_generated_report_is_one_document import _messy_project
    from workflow.measurement_report import recorded_document
    s, _fm, run, vs = _messy_project(tmp_path, dates=1)
    ti3 = vs[-1].measurement_ti3
    # the beta-34 document: written while the window had no kind, which is
    # exactly how a beta-34 build wrote it
    old = _window(s, ti3, qapp)
    try:
        old._window_kind = lambda: None
        key = _a_real_document(old, qapp, type_id=REPORT_TYPE_RECORD,
                               every_measurement=False, detail=True)
    finally:
        old.close()
    dlg = _window(s, ti3, qapp)
    try:
        assert dlg._window_kind() == "verification"
        # K19 (Knut, 2026-09-23): the list no longer OFFERS a type the run type
        # refuses, so a user cannot pick this document any more. The fit below is
        # still the safety net for any other door (a stored key, a document the
        # window opens on), so the entry is let through the filter here to reach
        # it; that the list itself hides it is `test_round_k19...`.
        dlg._entry_type = lambda e: REPORT_TYPE_FULL
        dlg._sync_saved_reports(dlg._run_ctx.run)
        _pick_key(dlg, key, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_RECORD, (
            "a saved Printing record is not shown as recorded")
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        assert dlg._report_type_now() == REPORT_TYPE_FULL, (
            "a new report made from a verification's saved Printing record "
            "would itself be a Printing record")
        before = set(_files(run))
        dlg._say_generated = lambda saved, failed: None
        dlg._ask_update_or_create_new = lambda: "new"
        dlg._on_generate_report()
        qapp.processEvents()
        new = sorted(set(_files(run)) - before)
        assert new, "Create New wrote nothing"
        types = {recorded_document(json.loads(
            Path(p).read_text(encoding="utf-8")))["type"] for p in new}
        assert types == {REPORT_TYPE_FULL}, types
    finally:
        dlg.close()


def _profiling_run_with_sheet(proj_run, i):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    proj_run.ensure_dir()
    ti3 = proj_run.dir / "sheet.ti3"
    ti3.write_text(_cgats("CTI3", [(r * (1 - 0.1 * i), g, b)
                                   for (r, g, b) in _PATCHES]),
                   encoding="utf-8")
    return ti3


def test_two_profiling_runs_that_disagree_still_make_a_printing_record(
        tmp_path, qapp):
    """Two profile runs loaded, each with its own stored type (legal before
    beta 35), and the window on a PROFILING sheet. The runs disagree, so the
    window falls back to the default, and the default must be fitted to the
    kind: a profiling measurement's only report is the Printing record.

    MUTATION that left the whole everyday tier green: `return
    REPORT_TYPE_DEFAULT` unfitted in `_report_type_now` (K13-10), which puts
    a greyed Full colour check on the pulldown of a profiling window.
    """
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.run_compliance import set_run_report_type
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    run2 = fm.project().new_run()
    t1 = _profiling_run_with_sheet(run1, 0)
    t2 = _profiling_run_with_sheet(run2, 1)
    set_run_report_type(run1, REPORT_TYPE_GREY)
    set_run_report_type(run2, REPORT_TYPE_FULL)
    dlg = MeasurementReportDialog(s, None, initial_ti3=t1)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._add_source(t2)
        qapp.processEvents()
        assert len(dlg._distinct_run_dirs()) == 2, "the second run did not load"
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._window_kind() == "profiling"
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
        assert dlg._type_combo.currentData() == REPORT_TYPE_RECORD
    finally:
        dlg.close()


def test_the_type_help_says_which_types_each_kind_of_measurement_may_have():
    """K13, Knut on beta 34: *"The help text for the report type needs to
    explain when which report types are available."* The paragraph was added
    and nothing read it.

    MUTATION that left the whole everyday tier green: drop
    `+ "\\n\\n" + when_available` from `_types_and_pairing_help` (K13-22).
    """
    from ui.dialogs.measurement_report_dialog import _types_and_pairing_help
    body = _types_and_pairing_help()
    assert ("A profiling measurement is the sheet a profile was built from, "
            "so its only report is the Printing record.") in body
    assert "the Printing record is not offered for it" in body
    assert ("The report ChromIQ writes by itself after a measurement follows "
            "the same rule.") in body


def _report_type_help_body(dlg) -> str:
    from ui.tooltip_button import TooltipButton
    return next(b._body for b in dlg.findChildren(TooltipButton)
                if b._title == "Report type")


def test_the_help_does_not_say_every_greyed_type_is_unbuilt(tmp_path, qapp):
    """On a PROFILING window Full colour check is greyed (K13) and ChromIQ can
    produce it; the first paragraph of the Report type help says *"A type
    shown greyed is one ChromIQ cannot produce yet."*. Round 2B reworded it
    (02e9e0e4, B8-799); this was a strict xfail and is now the guard."""
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, run1 = _verify_env(tmp_path)
    ti3 = _profiling_run_with_sheet(run1, 0)
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    try:
        i = dlg._type_combo.findData(REPORT_TYPE_FULL)
        assert not dlg._type_combo.model().item(i).isEnabled(), (
            "the fixture no longer greys a built type")
        assert ("A type shown greyed is one ChromIQ cannot produce yet."
                not in _report_type_help_body(dlg))
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# K14: the scope sentence's verification forms
# ---------------------------------------------------------------------------
def _scope_note(dlg) -> "str | None":
    import re
    from tests.test_the_report_reads_as_a_printed_document import _plain
    body = _plain(dlg._report_body_html(dlg._runs_for_report(), for_pdf=False))
    m = re.search(r"This report (covers|does not cover)[^.]*\.", body)
    return m.group(0) if m else None


def test_one_date_of_a_two_date_run_is_counted_for_this_run(tmp_path, qapp):
    """K14, and the spec's own wording: a verification document drawn from ONE
    run says "recorded for this run".

    MUTATION that left the whole everyday tier green: `len(_run_names or ())
    <= 1` -> `< 1` (K14-06), which says "these runs" about one run.
    """
    from PyQt6.QtCore import Qt
    from tests.test_the_report_reads_as_a_printed_document import (
        _three_profiled_runs)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _proj, runs = _three_profiled_runs(tmp_path, qapp)
    v = runs[0].verifications()[-1]
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        here = dlg._run_key(dlg._report)
        for i, (kind, _si, key) in enumerate(dlg._list_rows):
            if kind == "run" and key is not None and key != here:
                dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert len(dlg._runs_for_report()) == 1
        assert _scope_note(dlg) == (
            "This report covers 1 of the 2 measurements recorded for this "
            "profile run.")
    finally:
        dlg.close()


def test_a_verification_document_of_two_projects_says_the_runs_it_is_drawn_from(
        tmp_path, qapp):
    """K14 gave a verification document drawn from SEVERAL projects its own
    sentence, "recorded for the runs it is drawn from".

    AND THE GUARD THAT WAS SUPPOSED TO SEE THIS IS VACUOUS. R13-3's
    `test_a_document_drawn_from_two_projects_does_not_call_them_one` searches
    only for "this project|the projects it is drawn from" and `return`s when
    neither is there; on its verification fixture the sentence now reads "...
    for the runs it is drawn from", so it returns without asserting anything,
    under every mutant. This is its fixture with the sentence typed out.

    MUTATION that left the whole everyday tier green: take the one-project
    verification branch for several projects (K14-08), which says "these
    runs" of four runs in two projects.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from core.file_manager import Project
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        run2 = proj.new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        other = Project.create(Path(str(proj.root)).parent / "Other-Target",
                               "Other-Target")
        for scale in (0.8, 0.6):
            r = other.new_run()
            v = r.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(c * scale, g, b) for (c, g, b) in _PATCHES]),
                encoding="utf-8")
            dlg._add_source(v.measurement_ti3)
            qapp.processEvents()
        dlg._hidden_runs = {dlg._run_key(dlg._history[0])}
        qapp.processEvents()
        assert _scope_note(dlg) == (
            "This report covers 3 of the 4 measurements recorded for the "
            "profile runs of the projects it is drawn from.")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# Round A: the PDF name after more than one update
# ---------------------------------------------------------------------------
def test_the_pdf_name_carries_the_LAST_update_not_the_first(two_dates, qapp):
    """A-6 put the update in the PDF's name, and "Report shown" keeps only the
    latest (`test_a_second_update_replaces_the_first_stamp_in_the_name`). The
    PDF name must name the same one. Two updates in one second carry equal
    stamps, so the document's two stamps are written distinctly on disk.

    MUTATION that left the whole everyday tier green: `stamps[0]` for
    `stamps[-1]` in `_note_which_document_the_page_is` (A-04).
    """
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _window)
    from workflow.measurement_report import DOCUMENT_BLOCK
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        # K23: a document of two dates is its document file (`entry["file"]`,
        # in `verifications/reports/`) and its two verdict records.
        paths = [Path(str(r.get("_origin_dir"))) / "reports" / name
                 for r, name in entry["members"]]
        if entry.get("file"):
            paths.append(Path(str(entry["file"])))
        for p in paths:
            rep = json.loads(p.read_text(encoding="utf-8"))
            rep[DOCUMENT_BLOCK]["updated"] = ["2026-01-01T10:00:00",
                                              "2026-02-02T11:00:00"]
            p.write_text(json.dumps(rep), encoding="utf-8")
    finally:
        dlg.close()
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        _pick_key(dlg, key, qapp)
        name = dlg._report_filename(dlg._runs_for_document())
        assert " - updated 2026-02-02_11-00-00" in name, name
        assert "2026-01-01_10-00-00" not in name, name
    finally:
        dlg.close()


@pytest.fixture
def two_dates(tmp_path):
    from tests.test_a_generated_report_is_one_document import _messy_project
    return _messy_project(tmp_path, dates=2)


# ---------------------------------------------------------------------------
# Round A (A-1): all or nothing, the two halves no guard reached
# ---------------------------------------------------------------------------
def _update_with_one_member_stuck(dlg, qapp, monkeypatch, *, stick, drop):
    """Make a two-member document, drop one member (*drop*: "same" or
    "other" than the stuck one) and press Update; return (files, before,
    said, stuck_key, dropped_key)."""
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _press)
    key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                           every_measurement=True, detail=True)
    _pick_key(dlg, key, qapp)
    entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                 if d["key"] == key)
    files = {dlg._run_key(r): Path(str(r.get("_origin_dir"))) / "reports" / n
             for r, n in entry["members"]}
    assert len(files) == 2 and len({p.parent for p in files.values()}) == 2
    first = dlg._run_key(dlg._history[0])
    second = next(k for k in files if k != first)
    stuck = first
    stick(files[stuck])
    before = {k: p.read_bytes() for k, p in files.items()}
    said = {}
    dlg._say_generated = lambda saved, failed: said.update(
        saved=[str(p) for p in saved], failed=list(failed))
    dropped = None
    if drop is not None:
        dropped = second if drop == "other" else first
        dlg._hidden_runs.add(dropped)
        dlg._settings_touched()
    else:
        dlg._detail_check.setChecked(False)
    qapp.processEvents()
    del dlg._ask_update_or_create_new
    monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
    dlg._on_generate_report()
    qapp.processEvents()
    return files, before, said


def test_a_blocked_update_does_not_rewrite_a_dropped_member_it_could_archive(
        two_dates, qapp, monkeypatch):
    """Round C's `test_a_dropped_member_whose_archive_fails_is_not_rewritten`
    makes the DROPPED member's folder the one that cannot be archived, so the
    leftover loop's skip is reached through `_unarchived` and never through
    `_blocked`. Here it is the other way round: the KEPT member's folder
    cannot be archived (a real `reports/old` file), the dropped member's can,
    and all-or-nothing still means the dropped member is not rewritten.

    MUTATION that left the whole everyday tier green: drop `_blocked or` from
    `_archive_failed` (A-12), and the leftover is rewritten by an update that
    reported a failure.
    """
    from tests.test_generate_report_asks_what_to_do import _window
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        files, before, said = _update_with_one_member_stuck(
            dlg, qapp, monkeypatch,
            stick=lambda p: (p.parent / "old").write_text("x", encoding="utf-8"),
            drop="other")
        for k, p in files.items():
            assert p.read_bytes() == before[k], (
                f"{p.name} was rewritten by an update that could not archive "
                "the whole document")
        assert said.get("failed") and not said.get("saved"), said
    finally:
        dlg.close()


def test_a_read_only_report_FILE_stops_the_whole_update(two_dates, qapp,
                                                         monkeypatch):
    """Round A's probe covers two things: a folder that cannot be written and
    a FILE that cannot be. The only guard uses a read-only FOLDER, and that
    one already fails its archive, so the probe itself was never needed by
    any test. A read-only report file in a writable folder is archived fine
    (a copy only reads it) and is the case only the probe stops.

    MUTATION that left the whole everyday tier green: drop the `os.access`
    probe (A-09).
    """
    import stat
    from tests.test_generate_report_asks_what_to_do import _window
    s, _fm, _run, vs = two_dates
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    locked = []
    try:
        def _lock(p):
            os.chmod(p, stat.S_IRUSR)
            locked.append(p)
        files, before, said = _update_with_one_member_stuck(
            dlg, qapp, monkeypatch, stick=_lock, drop=None)
        if os.access(locked[0], os.W_OK):
            pytest.skip("this user can write a read-only file (root?)")
        for k, p in files.items():
            assert p.read_bytes() == before[k], f"{p.name} was rewritten"
        assert said.get("failed") and not said.get("saved"), said
    finally:
        for p in locked:
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
        dlg.close()


# ---------------------------------------------------------------------------
# Round A (A-7): the L*-only fallback line
# ---------------------------------------------------------------------------
def _paper_white_page(tmp_path, qapp, white):
    from tests.test_one_paper_white_has_one_answer import (
        _a_project_holding_both_shapes, _window as _pw_window)
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    for f in sorted((vs[0].dir / "reports").glob("report_*.json")):
        rep = json.loads(f.read_text(encoding="utf-8"))
        rep["paper_white"] = white
        f.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _pw_window(s, vs[-1].measurement_ti3, qapp)
    try:
        return dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
    finally:
        dlg.close()


def test_an_l_only_record_is_rounded_like_every_other_number(tmp_path, qapp):
    """MUTATION that left the whole everyday tier green: print `lv` raw in
    the L*-only fallback (A-17). 95.4 reads the same either way, which is all
    the existing guard used; 95.43 does not."""
    html = _paper_white_page(tmp_path, qapp, {"L": 95.43})
    assert "- L* 95.4</div>" in html
    assert "95.43" not in html


def test_an_l_only_record_that_is_nan_prints_no_number(tmp_path, qapp):
    """A-7 says the line is never "nan", and the NaN guard covered a* and b*
    only. MUTATION that left the whole everyday tier green: drop
    `math.isfinite(lv)` (A-16), and the page prints "L* nan"."""
    html = _paper_white_page(tmp_path, qapp, {"L": float("nan")})
    assert "L* nan" not in html and "nan</div>" not in html.lower()
