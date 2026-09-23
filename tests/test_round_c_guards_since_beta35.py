"""Round C on the guards added since v4.3.0-beta.35: the mutations they missed.

Every test here closes a hole a MUTATION proved: the mutant was applied, it
landed (a diff), and it left the whole everyday tier green. Each docstring
names its mutant. Expected strings and paths are typed, never read back from
the constant under test.

One test began as a FAULT: a false sentence in the app, marked
``xfail(strict=True)`` by round C. The sentence was fixed in 85bcc182, so it
is now an ordinary guard that the false advice does not return
(`test_the_tooltip_no_longer_offers_a_lever_that_does_nothing`). Production
code is not changed here.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import types
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                      # noqa: E402

from tests.test_a_driver_photographs_the_window_not_the_screen import (  # noqa: E402
    _cg, _FakeWin, _helper)
from tests.test_the_verification_preflight_fires_for_its_preconditions import (  # noqa: E402
    _corner_chart, _ready_tab, qapp)                                # noqa: F401


# ---------------------------------------------------------------------------
# the pre-flight's history check (ui/tabs/tab_measure.py)
# ---------------------------------------------------------------------------
def test_a_dated_folder_printed_but_never_read_is_not_history(qapp, tmp_path):
    """A dated verification is created when its sheet is PRINTED, before
    anything is read. A run whose only dated folder holds no `.ti3` has no
    measured history, and the pre-flight exists for exactly this moment.

    MUTATION that survived the whole everyday tier: drop `ti3.is_file() and`
    from `_run_has_a_measured_verification`. `count_sets` answers None for a
    missing file, `_cgats_has_no_readings` then says False ("unreadable is not
    empty"), and the missing file counts as a MEASURED verification, so the
    window never opened on a run's first verification.
    """
    tab, ctl, _chart = _ready_tab(tmp_path, qapp)
    run = ctl.project_or_none().run("run1")
    v = run.new_verification()
    v.dir.mkdir(parents=True, exist_ok=True)
    assert not v.measurement_ti3.exists(), "the fixture measured the sheet"
    assert [x.id for x in run.verifications()] == [v.id], (
        "the run does not list the printed-only verification, so this test "
        "would never reach the history loop")
    ctl.set_verification_id(v.id)
    assert tab._run_has_a_measured_verification() is False
    assert tab._verification_preflight_due() is True


# ---------------------------------------------------------------------------
# which window the capture helper photographs (scripts/onscreen_capture.py)
# ---------------------------------------------------------------------------
def test_among_namesakes_that_match_no_geometry_the_biggest_is_taken():
    """The size rule is kept for a TITLED window, and the only assert about it
    had ONE namesake, so min and max agree. MUTATION survived: `max(named, ...)`
    -> `min(named, ...)` in `_pick_window`."""
    pick = _helper()._pick_window
    small = _cg(600, 300, 300, 200, "Reference values", 22)
    big = _cg(100, 100, 1200, 800, "Reference values", 11)
    far_away = _FakeWin(5, 5, 10, 10)
    assert pick(far_away, [small, big], "Reference values") is big
    assert pick(far_away, [big, small], "Reference values") is big


def test_a_title_match_is_trusted_before_an_untitled_window_in_the_same_place():
    """`_pick_window`'s docstring: *"A title the window server knows is
    trusted, and among several windows carrying it the geometry decides."*
    MUTATION survived: `_by_geometry(win, named or cands)` ->
    `_by_geometry(win, cands)`, which lets an untitled helper window lying
    exactly on the rectangle beat the namesake eight points off it."""
    pick = _helper()._pick_window
    main = _cg(0, 89, 1500, 1028, "Reference values", 11)
    box = _cg(490, 128, 516, 902, "Reference values", 22)
    untitled_helper = _cg(482, 120, 516, 902, "", 33)
    win = _FakeWin(482, 120, 516, 902)
    assert pick(win, [untitled_helper, main, box], "Reference values") is box


def test_the_on_screen_list_is_asked_before_the_list_of_all_windows(
        monkeypatch):
    """`window_id_for` asks `kCGWindowListOptionOnScreenOnly` FIRST and the
    list of all windows only when that is empty. The all-windows list also
    holds windows that are not being drawn, such as a hidden box left where
    the new one now is. MUTATION survived: ask only
    `kCGWindowListOptionAll` (the fake's other test ignores the option)."""
    import time
    mod = _helper()
    monkeypatch.setattr(time, "sleep", lambda s: None)
    main = _cg(0, 89, 1500, 1028, "ChromIQ", 11)
    shown = _cg(490, 128, 516, 902, "", 22)
    hidden_at_the_same_place = _cg(482, 120, 516, 902, "", 33)
    ON, ALL = 1, 0

    def listing(option, relative):
        wins = [main, shown] if option & ON else [
            main, hidden_at_the_same_place, shown]
        return [dict(w, kCGWindowOwnerPID=os.getpid()) for w in wins]

    monkeypatch.setitem(sys.modules, "Quartz", types.SimpleNamespace(
        CGWindowListCopyWindowInfo=listing, kCGWindowListOptionOnScreenOnly=ON,
        kCGWindowListOptionAll=ALL, kCGWindowListExcludeDesktopElements=16,
        kCGNullWindowID=0))
    assert mod.window_id_for(_FakeWin(482, 120, 516, 902)) == 22


# ---------------------------------------------------------------------------
# archive_report_files / Verification.archive_reports (core/file_manager.py)
# ---------------------------------------------------------------------------
def _a_dated_report(root: Path):
    from core.file_manager import Project
    run = Project.create(root / "P", "P").current_run()
    run.ensure_dir()
    v = run.new_verification()
    v.ensure_dir()
    v.reports_dir.mkdir(parents=True)
    live = v.reports_dir / "report_2026-01-01_10-00-00.json"
    live.write_text(json.dumps({"schema": 7}), encoding="utf-8")
    return v, live


def _make_old_a_file(v) -> None:
    """A REAL failure, not a patched one: `reports/old` is a plain file, so
    the archive folder cannot be made under it."""
    (v.reports_dir / "old").write_text("not a folder", encoding="utf-8")


def test_archive_reports_still_raises_when_the_copy_fails(tmp_path):
    """The unlock recalculation relies on the RAISE: `except OSError` is what
    puts a date on its "no archive" list and skips rewriting it. Before the
    refactor the error simply propagated; now it depends on
    `raise_errors=True`. MUTATION survived: ignore `raise_errors` (always
    swallow), and the recalculation rewrites a date it never archived."""
    v, live = _a_dated_report(tmp_path)
    _make_old_a_file(v)
    with pytest.raises(OSError):
        v.archive_reports(datetime(2026, 9, 8, 12, 0, 0))
    assert json.loads(live.read_text(encoding="utf-8")) == {"schema": 7}


def test_archive_report_files_names_the_folder_it_could_not_archive(tmp_path):
    """The Update's contract, exercised on the REAL function. The only guard
    of the failure path (`test_a_file_whose_archive_fails_is_not_rewritten`)
    monkeypatches `archive_report_files` itself, so what the real function
    returns on a failure was never run. MUTATION survived: delete
    `failed.add(rdir)`; the dialog then rewrites the unarchived files."""
    from core.file_manager import archive_report_files
    v, live = _a_dated_report(tmp_path)
    _make_old_a_file(v)
    done, failed = archive_report_files([live], datetime(2026, 9, 8, 12, 0, 0))
    assert done == {}
    assert failed == {v.reports_dir.resolve()}


def test_archive_reports_answers_through_a_symlinked_project(tmp_path):
    """`/tmp` is a symlink on macOS and an output folder can be one. The
    archive is keyed on the RESOLVED folder and returned in the CALLER's
    spelling. MUTATIONS survived: `done.get(self.reports_dir)` (the archive is
    made and the method answers None), and `old_root = rdir / "old"` (the
    folder comes back in the resolved spelling, not the one it was asked in).
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    v, live = _a_dated_report(link)
    assert v.reports_dir.resolve() != v.reports_dir, "no symlink in the path"
    got = v.archive_reports(datetime(2026, 9, 8, 12, 0, 0))
    assert got == v.reports_dir / "old" / "2026-09-08_120000"
    assert (got / live.name).read_bytes() == live.read_bytes()


# ---------------------------------------------------------------------------
# Update's archive, for a member the Update no longer covers
# ---------------------------------------------------------------------------
def test_a_dropped_member_whose_archive_fails_is_not_rewritten(
        tmp_path, qapp, monkeypatch):
    """Untick a measurement and press Update: its file is a LEFTOVER, rewritten
    in the second loop of `_write_the_document`. That loop has its own
    `_archive_failed` guard and the archive-failure test never reaches it (it
    drops no member). Here the dropped member's folder cannot be archived, for
    real (`reports/old` is a file), and the kept member's can. Since round A
    (A-1) that stops the whole update, so neither file moves.

    MUTATIONS survived: delete the leftover loop's `if _archive_failed(path)`
    block (the leftover is rewritten with no copy kept), or keep it but drop its
    `failed.append` (nothing tells the user)."""
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _press, _window)
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_RECORD,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        files = {dlg._run_key(r): Path(str(r.get("_origin_dir"))) / "reports" / n
                 for r, n in entry["members"]}
        assert len(files) == 2, files
        dropped = dlg._run_key(dlg._history[0])
        kept = next(k for k in files if k != dropped)
        assert files[dropped].parent != files[kept].parent, (
            "both members share one reports folder, so one failure is both")
        (files[dropped].parent / "old").write_text("x", encoding="utf-8")
        before = {k: p.read_bytes() for k, p in files.items()}

        said = {}
        dlg._say_generated = lambda saved, failed: said.update(
            saved=[str(p) for p in saved], failed=list(failed))
        dlg._hidden_runs.add(dropped)
        dlg._settings_touched()
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()

        # ALL OR NOTHING since round A (A-1): a press that cannot archive one
        # of the document's folders writes none of them, so the KEPT member
        # is untouched as well, and the failure names the dropped one.
        assert files[kept].read_bytes() == before[kept], (
            "the kept member was rewritten by an update that could not write "
            "the whole document")
        assert files[dropped].read_bytes() == before[dropped], (
            "the dropped member was rewritten although its archive failed")
        assert str(files[dropped]) in said.get("failed", []), said
        assert not said.get("saved"), said
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# the Generate button's reason with several runs
# ---------------------------------------------------------------------------
def _remove_source_of(dlg, run, qapp):
    """Select *run*'s SOURCE row (the run rows are not selectable) and press
    Remove, as a user does."""
    si = next(i for i, src in enumerate(dlg._sources)
              if str(run.dir) in str(src.get("origin")))
    row = next(i for i, (kind, s_i, _k) in enumerate(dlg._list_rows)
               if kind == "source" and s_i == si)
    dlg._profile_list.setCurrentRow(row)
    assert dlg._profile_list.selectedItems(), "the source row did not select"
    dlg._remove_btn.click()
    qapp.processEvents()


def _only_the_other_run(dlg, run1, qapp, only=True):
    mine = {dlg._run_key(r) for r in dlg._history
            if str(r.get("_origin_dir") or "").startswith(str(run1.dir))}
    dlg._hidden_runs = set(mine) if only else set()
    dlg._sync_limit_controls()
    qapp.processEvents()


def test_the_other_run_reason_goes_when_this_run_is_ticked_again(
        tmp_path, qapp):
    """Retargeted for G7 (#182 beta 39): the several-runs reason is gone
    (Generate is live across runs); the reason that replaced it, "every ticked
    measurement belongs to another profile run", must go as soon as it stops
    being true.

    MUTATION, proven red: delete `self._generate_btn.setToolTip("")` at the
    head of the Generate block. The sentence then stays on a live button."""
    from tests.test_the_report_type_pulldown_stores_on_the_run import _two_runs
    dlg, run1, _run2 = _two_runs(tmp_path, qapp)
    try:
        _only_the_other_run(dlg, run1, qapp)
        assert "another profile run" in dlg._generate_btn.toolTip()
        _only_the_other_run(dlg, run1, qapp, only=False)
        assert dlg._generate_btn.isEnabled()
        assert "another profile run" not in dlg._generate_btn.toolTip(), (
            "the other-run reason outlived its state")
    finally:
        dlg.close()


def test_the_tooltip_no_longer_offers_a_lever_that_does_nothing(qapp, tmp_path):
    """Round C found (and round B the same hour) that the several-runs tooltip
    told the reader to untick the other run's measurements, which did not
    bring Generate back. G7 removed that sentence; the reason a greyed
    Generate gives with two runs loaded (only the other run ticked) still
    names a lever, and never "untick"."""
    from tests.test_the_report_type_pulldown_stores_on_the_run import _two_runs
    dlg, run1, _r2 = _two_runs(tmp_path, qapp)
    try:
        _only_the_other_run(dlg, run1, qapp)
        tip = dlg._generate_btn.toolTip().lower()
        assert tip, "Generate is greyed with no reason"
        assert "untick" not in tip, tip
    finally:
        dlg.close()


def test_point_lab_refuses_a_short_list_and_takes_a_tuple():
    """MUTATIONS survived: drop the `len(vals) == 3` check (a two-value `lab`
    comes back as a 2-tuple and the line's `lab[2]` raises IndexError inside
    the report), and accept only `list` (a tuple, which `point_lightness`
    reads, is refused)."""
    from workflow.measurement_report import point_lab
    assert point_lab({"lab": [100.0, -2.4]}) is None
    assert point_lab({"lab": (100.0, -2.4, -19.4)}) == (100.0, -2.4, -19.4)


def test_a_record_holding_only_l_still_prints_its_l(tmp_path, qapp):
    """A point with L* and nothing else is one `point_lightness` reads, and the
    line falls back to printing L* alone. MUTATION survived: delete the
    `elif lv is not None:` branch, and the line prints no number at all."""
    from tests.test_one_paper_white_has_one_answer import (
        _a_project_holding_both_shapes, _window as _pw_window)
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    for f in sorted((vs[0].dir / "reports").glob("report_*.json")):
        rep = json.loads(f.read_text(encoding="utf-8"))
        rep["paper_white"] = {"L": 95.4}
        f.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _pw_window(s, vs[-1].measurement_ti3, qapp)
    try:
        html = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "- L* 95.4</div>" in html, (
            "the L*-only paper white printed no number")
        assert "L* 6.2, a* 0.2, b* -1.4" in html, "the control line is gone"
    finally:
        dlg.close()
