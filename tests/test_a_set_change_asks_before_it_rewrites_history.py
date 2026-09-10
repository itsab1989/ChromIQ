"""Changing a run's limit set rewrites every saved report, so it must ASK.

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
    assert not rc.is_locked(run)
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


def test_changing_the_set_asks_first(qapp, tmp_path, monkeypatch):
    """MUTATION: drop the `_recalculating_would_rewrite_history` guard from
    `_on_set_chosen` and this goes red. Watched."""
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, title, text: asked.append((title, text)) or True)
        i = dlg._set_combo.findData("chromiq_tight")
        assert i >= 0
        dlg._set_combo.setCurrentIndex(i)
        assert asked, "the set was changed with no confirmation at all"
        title, text = asked[0]
        assert "3" in text, f"the question does not say how much is at stake: {text!r}"
        assert "reports/old" in text, (
            "the question does not say the old reports are kept, which is the "
            f"fact that makes it answerable: {text!r}")
    finally:
        dlg.deleteLater()


def test_saying_no_changes_nothing_at_all(qapp, tmp_path, monkeypatch):
    """A confirmation that is asked and ignored is worse than none.

    MUTATION: make `_on_set_chosen` fall through on a refusal and this goes red
    on the first assertion.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    before = _saved_json(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)

        assert _saved_json(run) == before, "a refused change rewrote the reports"
        assert not rc.is_bound(run), "a refused change bound the run"
        assert dlg._set_combo.currentData() != "chromiq_tight", (
            "the pulldown kept the refused choice, so the window now says the "
            "run is judged by a set it is not judged by")
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


def test_the_question_counts_one_report_in_the_singular(qapp, tmp_path, monkeypatch):
    """CLAUDE.md asks for explicit singular and plural, never "(s)", and the
    sister confirmation was corrected for exactly this a day earlier."""
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 1)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or True)
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        assert asked
        assert "one dated report" in asked[0], asked[0]
        assert "1 dated reports" not in asked[0], asked[0]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# The other half of the same drift: what "editable" was asking
# ---------------------------------------------------------------------------
def _bound_run_with_dates(tmp_path, n_dates: int, unlocked: bool = False):
    proj = Project.create(tmp_path / "Q", "Q")
    run = proj.current_run()
    run.ensure_dir()
    first = None
    for i in range(n_dates):
        v = run.new_verification(datetime(2026, 5, 1 + i, 10, 0, 0))
        v.ensure_dir()
        raw = v.dir / "Q.ti3"
        _write_ti3(raw, _ramp(16) + _colours(), verification=False)
        mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
        first = first or (v.dir / f"{run.verify_stem}.ti3")
    rc.bind_run(run, "chromiq_default", {})
    if unlocked:
        rc.set_run_unlocked(run, True)
    return proj, run, first


@pytest.mark.parametrize("n_dates, unlocked, locked, why", [
    (1, False, False, "one date is not a history, so the set is still offered"),
    (2, True, False, "the lock was lifted by hand"),
    (2, False, True, "two dates and never lifted"),
])
def test_the_limits_window_is_editable_exactly_when_the_run_is_not_locked(
        qapp, tmp_path, monkeypatch, n_dates, unlocked, locked, why):
    """Three controls used to give three different answers about one run.

    Round 5 drove `Threshold-Series/run3`, one dated verification, bound, NOT
    locked, which is the state Knut asked for by name so that the settings can
    still be changed. The report window offered the pulldown and an "Edit
    limits..." button; that button opened the limits window with the run's own
    column read-only under the note "locked: tick 'Unlock this run's limits' in
    the report window to change these"; and that tick box was greyed out in the
    window behind it. An instruction that cannot be followed, over an edit that
    is refused, on a run the app says is not locked.

    The cause was one expression, `run_editable=bool(ctx and lim.unlocked)`,
    which keys on the hand-lift flag alone. Editable means NOT LOCKED, and the
    lock rule had gained a second condition that morning.

    MUTATION: put `lim.unlocked` back and the first case goes red, which is
    exactly the state that was reported. Watched.
    """
    proj, run, ti3 = _bound_run_with_dates(tmp_path, n_dates, unlocked)
    assert rc.is_locked(run) is locked, f"the fixture is not the state it names ({why})"

    seen: list = []

    class _Fake:
        run_limits_changed = False

        def __init__(self, *a, **kw):
            seen.append(bool(kw.get("run_editable")))

        def exec(self):
            return 0

        def deleteLater(self):
            pass

    # It is imported inside the method, so patch it where it is LOOKED UP.
    import ui.dialogs.thresholds_dialog as td
    monkeypatch.setattr(td, "ThresholdsDialog", _Fake)

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        dlg._on_open_limits()
        assert seen == [not locked], (
            f"the limits window was opened with run_editable={seen}, but this "
            f"run is {'locked' if locked else 'not locked'} ({why})")
    finally:
        dlg.deleteLater()
