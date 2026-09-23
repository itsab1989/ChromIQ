"""Changing "Judged against" rewrites nothing, asks nothing and binds nothing.

**K31 (Knut, #182 5801677743, beta 40)** retired most of this file: the run
lock, "Unlock this run's limits", the binding of a run to a set, the
recalculation the Report limits window's Save still did, and the undo and
collision guards around those doors are gone, because *"the limit set belongs
to the report"* and *"changing the reports settings does not change the
report, and its binding to a limit set, unless you click Generate Report"*.
Seventy-four guards of those doors went with them (§25 of
`docs/design/measurement_report_limits.md` lists what was removed and why);
what the door itself must still never do is pinned below, and the new model is
pinned in `tests/test_k31_report_model.py`.

The history of the file, kept because it is why the guards below exist:

Challenge round 5 drove this and it is the worst thing found in the round. On a
copy of a project made before #182, eleven dated verifications, the "Judged
against" pulldown is live, because a run that was never bound has nothing to
lock and the lock now correctly declines to grey a control over a value stored
nowhere. One selection in that pulldown:

* rewrote **all eleven** saved reports,
* flipped **six** verdicts from PASS to FAIL,
* bound the run and locked it, so the control was gone afterwards,
* and asked **nothing**.

The other route to that identical consequence, ticking "Unlock this run's
limits", has been guarded by a confirmation naming the count and promising the
old reports are kept. The two routes had the same effect and opposite manners.

This path became reachable this morning, by two rulings that were both right:
that an unbound run has nothing to lock, and that one measurement is not a
history. The lock rule moved and the guard did not move with it, which is the
shape of the whole round.
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


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _run_with_saved_reports(tmp_path, n_dates: int):
    """A run shaped like a project made before #182: dated verifications with
    saved reports, and NO limit set copied onto it."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    first = None
    for i in range(n_dates):
        v = run.new_verification(datetime(2026, 1, 1 + i, 10, 0, 0))
        v.ensure_dir()
        raw = v.dir / "P.ti3"
        _write_ti3(raw, _ramp(16) + _colours(), verification=False)
        mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
        target = v.dir / f"{run.verify_stem}.ti3"
        rep = mr.build_report(target)
        mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                         set_id="chromiq_default",
                         set_label="ChromIQ default (recommended)")
        mr.save_report(rep, v.dir)
        first = first or target
    # Unbind it, which is what a pre-#182 project looks like on disk.
    meta = run.load_meta()
    meta.compliance_set_id = ""
    meta.compliance_thresholds = None
    run.save_meta(meta)
    assert not rc.is_bound(run), "the fixture is bound, so it proves nothing"
    return proj, run, first


def _dialog(s, ti3):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(s, None, initial_ti3=ti3)


def _saved_json(run) -> list:
    out = []
    for v in run.verifications():
        for f in sorted(v.reports_dir.glob("report_*.json")):
            out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def test_changing_the_set_neither_asks_nor_rewrites(qapp, tmp_path, monkeypatch):
    """**KNUT OVERTURNED THIS TEST, AND IT IS KEPT AS THE OPPOSITE OF ITSELF.**

    It used to assert that the pulldown ASKS before rewriting every saved
    report, because it did rewrite them. Knut, beta 20: *"If a report has been
    generated, those reports shall not be recalculated if I want to create a
    new report with a different Judged Against threshold set."*, and beta 21,
    watching the same act relabel every entry in the list: *"This is not the
    behaviour I specified."* Asked directly whether that supersedes D23, the
    archive-then-recalculate rule stated twice in his own name, he answered
    *"Agreed. D23 stands."* — D23 says how a recalculation is done, never that
    one must happen, so the two live together: nothing is rewritten here, so
    there is nothing to keep first and nothing to ask about (B8-384).

    The whole rule, on disk and on screen, is in
    `tests/test_a_saved_report_is_not_rewritten_by_a_set_change.py`; this is
    the door that used to do it.

    MUTATION: rewrite the run's saved reports from `_on_set_chosen` (the old
    `_recalculate_run`), or ask `self._confirm` there, and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    before = _saved_json(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, title, text: asked.append((title, text)) or True)
        i = dlg._set_combo.findData("chromiq_tight")
        assert i >= 0
        dlg._set_combo.setCurrentIndex(i)
        assert not asked, (
            f"the pulldown asked about a rewrite it no longer does: {asked!r}")
        assert _saved_json(run) == before, (
            "a set change rewrote a saved report of the run")
    finally:
        dlg.deleteLater()


def test_the_set_change_binds_nothing(qapp, tmp_path, monkeypatch):
    """What the pulldown does now (K31): it changes the REPORT's set, on
    screen, and nothing else. It used to bind the run, which Knut ruled out:
    *"changing the reports settings does not change the report, and its
    binding to a limit set, unless you click Generate Report"*.

    MUTATION: write the chosen set onto the run in `_on_set_chosen` (for
    example `rc.set_run_default_set(ctx.run, set_id, "")`) and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    meta_before = run.meta_path.read_bytes()
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        assert not rc.is_bound(run), "the run was bound to the chosen set"
        assert run.meta_path.read_bytes() == meta_before, (
            "choosing a set wrote the run's meta.json")
        assert dlg._set_combo.currentData() == "chromiq_tight", (
            "the pulldown does not show the set that was chosen")
        assert dlg._report_limits().set_id == "chromiq_tight"
    finally:
        dlg.deleteLater()


def test_a_run_with_nothing_saved_is_not_interrogated(qapp, tmp_path, monkeypatch):
    """The question is about losing something. With no saved report there is
    nothing to lose, and a confirmation there is a habit-forming click.

    MUTATION: ask unconditionally and this goes red.
    """
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    v = run.new_verification(datetime(2026, 3, 1, 9, 0, 0))
    v.ensure_dir()
    raw = v.dir / "P.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
    ti3 = v.dir / f"{run.verify_stem}.ti3"

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(t) or True)
        i = dlg._set_combo.findData("chromiq_tight")
        if i < 0:
            pytest.skip("the tight set is not offered in this window")
        dlg._set_combo.setCurrentIndex(i)
        assert not asked, (
            "a run with no saved report was asked to confirm a rewrite of "
            "nothing")
    finally:
        dlg.deleteLater()
