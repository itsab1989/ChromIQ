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
        assert "one saved report" in asked[0], asked[0]
        assert "1 saved reports" not in asked[0], asked[0]
        # AND THE TAIL AGREES WITH THE HEAD. The first version kept a plural
        # tail under a singular head, so "every one of them" and "the reports
        # they replace" pointed at nothing, and German had to agree as well.
        assert "them" not in asked[0], (
            f"the singular question still refers to a plural: {asked[0]!r}")
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


# ---------------------------------------------------------------------------
# Round 6: the third door into the same room, and it was the one left open
# ---------------------------------------------------------------------------
def _edit_through_the_limits_window(dlg, monkeypatch, answer=True, row="all_de00_avg",
                                    value=0.2):
    """Drive `_on_open_limits` with a dialog that edits one number and closes.

    The real `ThresholdsDialog` writes the edited column in `done()` whatever
    result it closes with, so the fake does the same thing through the same
    function. Faking the WRITE rather than stubbing it is the point: the fault
    is what happens after the write.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import run_limits, set_run_limits

    asked: list = []
    monkeypatch.setattr(type(dlg), "_confirm",
                        lambda self, t, x: asked.append(x) or answer)

    class _Fake:
        run_limits_changed = False

        def __init__(self, settings, parent, run=None, run_editable=False):
            self._run, self._editable = run, run_editable

        def exec(self):
            if self._run is not None and self._editable:
                lim = dict(run_limits(self._run, {}).limits)
                lim[row] = Limit.value(value)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
            return 0

        def deleteLater(self):
            pass

    import ui.dialogs.thresholds_dialog as td
    monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
    _Fake.run_limits_changed = False
    dlg._on_open_limits()
    return asked


def test_editing_the_numbers_asks_the_same_question(qapp, tmp_path, monkeypatch):
    """MUTATION: drop the guard from `_on_open_limits` and this goes red.

    Round 6 drove this on the same copy round 5 used. Choosing a set asked and
    unlocking asked; typing a number into the run's own column and closing the
    window rewrote all eleven saved reports and asked nothing, and the fix that
    closed round 5's finding is what made this route reachable on two more
    kinds of run.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked = _edit_through_the_limits_window(dlg, monkeypatch)
        assert asked, "the run's limits were edited and recalculated in silence"
        assert "reports/old" in asked[0]
    finally:
        dlg.deleteLater()


def test_saying_no_to_an_edit_puts_the_numbers_back(qapp, tmp_path, monkeypatch):
    """The dialog writes on its way out, including on Escape, so a refusal has
    to undo the write as well as skip the recalculation.

    MUTATION: remove the restore block and this goes red on the first
    assertion, because the edited column survives a refusal.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    before_reports = _saved_json(run)
    before_meta = run.load_meta()
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        _edit_through_the_limits_window(dlg, monkeypatch, answer=False)
        after = run.load_meta()
        assert after.compliance_thresholds == before_meta.compliance_thresholds, (
            "a refused edit stayed on disk, so the window now shows numbers "
            "the user said no to")
        assert after.compliance_set_id == before_meta.compliance_set_id
        assert _saved_json(run) == before_reports, "a refused edit rewrote the reports"
    finally:
        dlg.deleteLater()


def test_an_edit_on_an_unbound_run_is_not_saved_where_nothing_reads_it(
        qapp, tmp_path, monkeypatch):
    """`set_run_limits` writes the numbers and never the set id, and `is_bound`
    needs both, so on a run made before #182 the typed number was stored where
    `run_limits()` does not look. Measured by round 6: typed 0.2, reloaded 2.0,
    and eleven reports rewritten with numbers nobody chose.

    MUTATION: remove the set-id write and this goes red on the reload.
    """
    from workflow.run_compliance import is_bound, run_limits

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    assert not is_bound(run), "the fixture is bound, so it proves nothing"
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        _edit_through_the_limits_window(dlg, monkeypatch, value=0.2)
        assert is_bound(run), (
            "the run is still unbound after its own column was edited")
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.2) < 1e-9, (
            f"the typed number is not what the run is judged with: {got}")
    finally:
        dlg.deleteLater()


def test_a_locked_run_is_never_offered_the_edit(qapp, tmp_path, monkeypatch):
    """The one case that must stay shut. MUTATION: pass run_editable=True
    unconditionally and this goes red."""
    proj, run, ti3 = _bound_run_with_dates(tmp_path, 2)
    from workflow.run_compliance import is_locked
    assert is_locked(run)
    before = run.load_meta().compliance_thresholds
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked = _edit_through_the_limits_window(dlg, monkeypatch)
        assert not asked, "a locked run was asked to confirm an edit it cannot make"
        assert run.load_meta().compliance_thresholds == before
    finally:
        dlg.deleteLater()


def test_the_question_counts_report_files_and_not_dates(qapp, tmp_path, monkeypatch):
    """`save_report` is timestamped on purpose so a printer's reports accrue,
    so several per date is designed behaviour. The count said dates and the
    sentence said reports.

    MUTATION: count dated verifications again and this goes red.
    """
    import shutil

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    extra = 0
    for v in run.verifications():
        src = sorted(v.reports_dir.glob("report_*.json"))[0]
        for i in (1, 2):
            shutil.copy2(src, src.with_name(f"report_2027-01-0{i}_00-00-00.json"))
            extra += 1
    files = sum(len(list(v.reports_dir.glob("report_*.json")))
                for v in run.verifications())
    assert files == 9, files

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or False)
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        assert asked
        assert "9" in asked[0], (
            f"the question undercounts what it would rewrite: {asked[0]!r}")
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 7: the fix that granted control ended by taking it away
# ---------------------------------------------------------------------------
def test_binding_an_edited_run_does_not_lock_the_user_out(qapp, tmp_path,
                                                          monkeypatch):
    """Round 6 made an edit on an unbound run record its set id, so the numbers
    would mean something. `is_locked` is bound AND two dates AND not unlocked,
    so on a project made before #182 with a history that bind LOCKED the run on
    the spot: pulldown greyed, button changed to "Show limits…", and the unlock
    box came back disabled, because it consults a preference that ships off.

    The user asked for control of those numbers and the act of granting it
    removed it, with a question that said nothing about either.

    MUTATION: drop the `compliance_unlocked = True` write and this goes red on
    the lock assertion. Watched.
    """
    from workflow.run_compliance import is_bound, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    assert not is_bound(run) and not is_locked(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        _edit_through_the_limits_window(dlg, monkeypatch, value=0.2)
        assert is_bound(run), "the premise failed: the run was not bound"
        assert not is_locked(run), (
            "editing this run's own numbers bound it AND locked it, so the "
            "control the user just used is gone and the question never said so")
    finally:
        dlg.deleteLater()


def test_the_bind_writes_the_whole_record_not_a_third_of_it(qapp, tmp_path,
                                                            monkeypatch):
    """`bind_run` writes the set id, the ENGLISH label and the moment. The
    edit route wrote only the id, so a run bound that way carried a record no
    other path produces, and a later ChromIQ that no longer knew the id printed
    the raw internal id to the user where the label exists to prevent exactly
    that (D23).

    MUTATION: remove the label write and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        _edit_through_the_limits_window(dlg, monkeypatch, value=0.2)
        meta = run.load_meta()
        assert meta.compliance_set_id, "no set id"
        assert meta.compliance_set_label, (
            "the run was bound with no English label, so a later build that "
            "does not know this id can only show the id itself")
        assert meta.compliance_bound_at, "the run was bound with no date"
    finally:
        dlg.deleteLater()


def test_a_refused_edit_puts_back_the_columns_too(qapp, tmp_path, monkeypatch):
    """The window writes `compliance_columns` on the toggle, and the first
    snapshot held only the set id and the thresholds.

    MUTATION: drop `compliance_columns` from the snapshot tuple and this goes
    red.
    """
    from workflow.run_compliance import set_run_columns

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    set_run_columns(run, ["chromiq_default", "chromiq_tight"])
    before = list(run.load_meta().compliance_columns or [])
    assert before, "the fixture stored no columns, so this proves nothing"

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        def _edit_and_hide(dlg, monkeypatch):
            from workflow.compliance_sets import Limit
            from workflow.run_compliance import run_limits, set_run_limits
            asked: list = []
            monkeypatch.setattr(type(dlg), "_confirm",
                                lambda self, t, x: asked.append(x) or False)

            class _Fake:
                run_limits_changed = False

                def __init__(self, settings, parent, run=None, run_editable=False):
                    self._run, self._editable = run, run_editable

                def exec(self):
                    if self._run is not None and self._editable:
                        set_run_columns(self._run, ["chromiq_default"])
                        lim = dict(run_limits(self._run, {}).limits)
                        lim["all_de00_avg"] = Limit.value(0.3)
                        set_run_limits(self._run, lim)
                        type(self).run_limits_changed = True
                    return 0

                def deleteLater(self):
                    pass

            import ui.dialogs.thresholds_dialog as td
            monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
            _Fake.run_limits_changed = False
            dlg._on_open_limits()
            return asked

        assert _edit_and_hide(dlg, monkeypatch), "no question was asked"
        assert list(run.load_meta().compliance_columns or []) == before, (
            "a refused edit kept the columns the window hid")
    finally:
        dlg.deleteLater()


def test_a_refusal_puts_back_the_default_that_an_unbound_run_is_judged_by(
        qapp, tmp_path, monkeypatch):
    """The window's "Default for new runs" radio writes an app-wide preference,
    and on an UNBOUND run that preference IS what the run is judged against.

    Round 7 clicked it, refused the question, and watched "Judged against"
    change from ChromIQ default to ChromIQ tight anyway: the user declined to
    change this run's limit set and the limit set changed, in the pulldown they
    were looking at.

    MUTATION: drop the default-set restore and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    s = _settings(tmp_path)
    s.set("compliance_default_set", "chromiq_default")
    dlg = _dialog(s, ti3)
    try:
        from workflow.compliance_sets import Limit
        from workflow.run_compliance import run_limits, set_run_limits
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run, self._editable, self._s = run, run_editable, settings

            def exec(self):
                self._s.set("compliance_default_set", "chromiq_tight")
                if self._run is not None and self._editable:
                    lim = dict(run_limits(self._run, {}).limits)
                    lim["all_de00_avg"] = Limit.value(0.4)
                    set_run_limits(self._run, lim)
                    type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        _Fake.run_limits_changed = False
        dlg._on_open_limits()

        assert s.get("compliance_default_set", None) == "chromiq_default", (
            "the refusal left the app-wide default moved, so an unbound run is "
            "now judged by a set the user said no to")
    finally:
        dlg.deleteLater()
