"""A recalculation refreshes the run it was asked about, and no other.

`MeasurementReportDialog._recalculate_run` rewrites the run's dated reports on
disk and then refreshes the same records in the window's in-memory history, so
the columns on screen agree with the files. It decided which records were the
run's by asking whether their origin path STARTS WITH the run's folder.

``.../runs/run10`` starts with ``.../runs/run1``.

Driven on screen (adversarial round four, 2026-09-12) on a project holding
run1 bound to ChromIQ default, run2 to ChromIQ tight and run10 to Quick check,
with "Show all measurement runs" ticked so all six columns were drawn:

* choosing "ChromIQ tight" for run1 left run2's column reading "ChromIQ tight",
  which is its own set, so run2 is the control and it was never in danger;
* run10's column went from "Quick check" to "ChromIQ tight" in the rendered
  document, and run10's file on disk still said ``chromiq_quick``.

Nothing was written. The window simply told the user a column had been judged
by a set it is not bound to, which is the fault §182 exists to prevent, reached
through a string comparison.

**AND IT REACHED WIDER THAN THE WRITE IN A SECOND WAY.** The disk pass walks
``ctx.run.verifications()``, which is what §5 of
`docs/design/measurement_report_limits.md` specifies ("each dated report"); the
in-memory pass reached the run's own ``reports/`` as well. On the same drive
run1's run-level report read "ChromIQ tight" on screen and ``chromiq_default``
on disk, and no question was asked at all, because `_saved_report_count` counts
dated folders and had counted none. A baseline refreshed wider than the write
that earned it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402
from workflow import run_compliance as rc                 # noqa: E402
from workflow.ti3_analysis import mark_verification_ti3   # noqa: E402

from tests.test_report_judging import _colours, _ramp, _write_ti3   # noqa: E402

QUICK = "chromiq_quick"
TIGHT = "chromiq_tight"
DEFAULT = "chromiq_default"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _dated_report(run, when, set_id):
    """One dated verification of *run* with one saved report, judged by
    *set_id*."""
    v = run.new_verification(when)
    v.ensure_dir()
    raw = v.dir / f"{run.stem}.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
    target = v.dir / f"{run.verify_stem}.ti3"
    rep = mr.build_report(target)
    lim = rc.run_limits(run, {})
    mr.stamp_verdict(rep, lim.limits, set_id=set_id, set_label=lim.label_en)
    mr.save_report(rep, v.dir)
    return target


def _project_with_run1_and_run10(tmp_path):
    """run1, run2 and run10, each bound to a DIFFERENT shipped set.

    run2 is the control: its folder name is not a prefix of run1's and never
    was, so anything that happens to it happens to run10 for a real reason.
    """
    proj = Project.create(tmp_path / "P", "P")
    firsts: dict = {}
    for i, (rid, sid) in enumerate(
            (("run1", DEFAULT), ("run2", TIGHT), ("run10", QUICK))):
        run = proj.run(rid)
        run.ensure_dir()
        rc.bind_run(run, sid, {})
        rc.set_run_unlocked(run, True)     # so the pulldown stays live
        firsts[rid] = _dated_report(run, datetime(2026, 3, 1 + i, 10, 0, 0),
                                    sid)
    assert (proj.runs_root / "run10").is_dir(), "the fixture has no run10"
    assert str(proj.run("run10").dir).startswith(str(proj.run("run1").dir)), \
        "run10's path no longer starts with run1's, so this proves nothing"
    return proj, firsts


def _open(s, ti3, also=()):
    """The window on *ti3*, with each of *also* added as the user adds one."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    for extra in also:
        assert dlg._append_source(extra), f"{extra} was not added"
    if also:
        dlg._rebuild_from_sources()
    return dlg


def _labels_by_run(dlg) -> dict:
    out: dict = {}
    for r in dlg._history:
        origin = str(r.get("_origin_dir", ""))
        # .../runs/<run>/verifications/<date>
        parts = origin.split(os.sep)
        rid = parts[-3] if len(parts) >= 3 else origin
        out.setdefault(rid, []).append(
            ((r.get("compliance") or {}).get("set_label")))
    return out


def _disk_label(run) -> str:
    for v in run.verifications():
        for f in sorted(v.reports_dir.glob("report_*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            return (doc.get("compliance") or {}).get("set_id")
    return ""


def test_recalculating_run1_leaves_run10_alone(qapp, tmp_path):
    """MUTATION: put `origin.startswith(str(ctx.run.dir))` back in
    `_recalculate_run` and this goes red on run10 while run2 stays green.
    Watched, 2026-09-12."""
    proj, firsts = _project_with_run1_and_run10(tmp_path)
    s = _settings(tmp_path)
    dlg = _open(s, firsts["run1"], also=(firsts["run2"], firsts["run10"]))
    try:
        # all three runs are loaded, which is what a user comparing them does
        before = _labels_by_run(dlg)
        assert {"run1", "run2", "run10"} <= set(before), before
        assert before["run10"] == ["Quick check"], before

        rc.bind_run(proj.run("run1"), TIGHT, {})
        dlg._forget_limits()
        dlg._recalculate_run()

        after = _labels_by_run(dlg)
        assert after["run10"] == ["Quick check"], (
            "run10's column was re-judged by run1's limit set: "
            f"{after['run10']}")
        assert after["run2"] == ["ChromIQ tight"], after["run2"]
        assert after["run1"] == ["ChromIQ tight"], (
            "run1's own dated column did not follow its set, so the "
            "recalculation is now doing nothing at all: " + str(after["run1"]))
    finally:
        dlg.deleteLater()


def test_run10s_file_is_not_touched_either(qapp, tmp_path):
    """The disk half of the same question. It was already right, and it is the
    half that says the memory half was wrong rather than the file."""
    proj, firsts = _project_with_run1_and_run10(tmp_path)
    s = _settings(tmp_path)
    dlg = _open(s, firsts["run1"], also=(firsts["run2"], firsts["run10"]))
    try:
        rc.bind_run(proj.run("run1"), TIGHT, {})
        dlg._forget_limits()
        dlg._recalculate_run()
        assert _disk_label(proj.run("run10")) == QUICK
        assert _disk_label(proj.run("run2")) == TIGHT
        assert _disk_label(proj.run("run1")) == TIGHT
    finally:
        dlg.deleteLater()


def test_the_memory_refresh_never_reaches_wider_than_the_write(qapp, tmp_path):
    """A run's own ``reports/`` is not a dated verification, so the disk pass
    does not rewrite it and the window must not re-judge it either.

    MUTATION: widen the loop back to the whole run subtree and this goes red:
    the column reads the new set while the file keeps the old one.
    """
    proj = Project.create(tmp_path / "R", "R")
    run = proj.run("run1")
    run.ensure_dir()
    rc.bind_run(run, DEFAULT, {})
    rc.set_run_unlocked(run, True)
    raw = run.dir / f"{run.stem}.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    rep = mr.build_report(raw)
    lim = rc.run_limits(run, {})
    mr.stamp_verdict(rep, lim.limits, set_id=DEFAULT, set_label=lim.label_en)
    mr.save_report(rep, run.dir)
    assert not list(run.verifications()), "the fixture has dated folders"

    s = _settings(tmp_path)
    dlg = _open(s, raw)
    try:
        rc.bind_run(run, TIGHT, {})
        dlg._forget_limits()
        dlg._recalculate_run()
        on_disk = {(json.loads(f.read_text(encoding="utf-8"))
                    .get("compliance") or {}).get("set_id")
                   for f in sorted(run.reports_dir.glob("report_*.json"))}
        in_window = {(r.get("compliance") or {}).get("set_id")
                     for r in dlg._history}
        assert on_disk == {DEFAULT}, on_disk
        assert in_window == on_disk, (
            "the window says this report was judged by a set its own file "
            f"does not record: window={in_window} disk={on_disk}")
    finally:
        dlg.deleteLater()


def test_the_window_asks_the_run_and_does_not_match_a_string(qapp):
    """THE SOURCE, because the two tests above need a ten-run project to reach
    it and a reader deleting the guard would want to know why it is there."""
    import inspect

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._recalculate_run)
    # the CODE, not the note above it, which names the fault on purpose
    src = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    assert "startswith" not in src, (
        "the recalculation decides whose report a record is by string prefix "
        "again; .../runs/run10 starts with .../runs/run1")
    assert "origin in mine" in src, \
        "the loop no longer asks the run which folders are its own"
