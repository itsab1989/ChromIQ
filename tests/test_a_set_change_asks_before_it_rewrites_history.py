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
        # THE WINDOW'S CONTROLS, NOT THE FLAG ON DISK. Three rounds tried to
        # keep this true by writing `compliance_unlocked`, and that is a
        # snapshot of something that moves: dated verifications can be deleted.
        # The run really is locked; this window remembers that it bound it and
        # leaves the controls where they were for as long as it is open.
        dlg._refresh()
        assert dlg._set_combo.isEnabled(), (
            "editing this run's own numbers bound it and greyed the pulldown, "
            "so the control the user just used is gone and the question never "
            "said so")
        assert run.load_meta().compliance_unlocked is False, (
            "a lock nobody lifted was recorded on disk")
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


def test_a_refused_edit_keeps_the_columns_the_window_hid(qapp, tmp_path, monkeypatch):
    """REVERSED 2026-09-11, ON KNUT'S RULING, AND THE NAME CHANGED WITH IT.

    This test used to be `test_a_refused_edit_puts_back_the_columns_too`, and
    it asserted the opposite: that refusing the "Changing the limit set
    recalculates it…" question also undid the column ticks. The reasoning was
    that the undo puts back every key this window wrote.

    Knut reported the consequence: *"it is not remembered what I turned off
    some columns"*, with the ruling that the question itself *"should only come
    when thresholds are changed, not if table columns are hidden or shown"*. A
    refusal answers the question that was asked, and which columns are SHOWN
    was never in it.

    What this test was really protecting is still protected, one door along:
    `compliance_columns` is still in the snapshot tuple, because the LOCK path
    puts it back and `_run_columns_moved` compares it. Drop the slot and
    `test_a_run_locked_while_the_window_was_open_keeps_its_columns_too` below
    goes red.

    MUTATION: pass `keep_columns=False` in `_restore_limits_snapshot` and this
    goes red.
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
        after = list(run.load_meta().compliance_columns or [])
        assert after == ["chromiq_default"], (
            f"a refusal about the NUMBERS took the column choice with it: "
            f"{before} -> {after}")
        # …and the numbers really were refused, so this is not passing because
        # nothing was undone at all.
        from workflow.run_compliance import run_limits
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.3) > 1e-9, (
            "the refused number stayed; the undo did not run")
    finally:
        dlg.deleteLater()


def test_a_run_locked_while_the_window_was_open_keeps_its_columns_too(
        qapp, tmp_path, monkeypatch):
    """The other door, where the column choice IS put back, and why.

    A refusal is about the numbers, so the ticks stand. A LOCK is about whether
    this window may write to the run at all, and the answer covers every key it
    writes. This is also what keeps `compliance_columns` in the snapshot tuple
    once the refusal path stopped using it.

    MUTATION: pass `keep_columns=True` on the lock path and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_columns, set_run_limits)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    set_run_columns(run, ["chromiq_default", "chromiq_tight"])
    before = list(run.load_meta().compliance_columns or [])
    assert before, "the fixture stored no columns, so this proves nothing"

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(t))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                set_run_columns(self._run, ["chromiq_default"])
                bind_run(self._run, "chromiq_default", {})   # somebody locks it
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.2)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert is_locked(run), "the premise failed: the run is not locked"
        assert told, "the user was not told the run had been locked meanwhile"
        assert list(run.load_meta().compliance_columns or []) == before, (
            "a run locked while the window was open kept the window's write")
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


# ---------------------------------------------------------------------------
# Round 8: stop guarding doors, guard the room
# ---------------------------------------------------------------------------
def test_the_pulldown_route_does_not_lock_the_user_out_either(qapp, tmp_path,
                                                              monkeypatch):
    """Round 7 fixed the "Edit limits…" door and this one kept the fault.

    `_on_set_chosen` reaches the same bind through `bind_run`, which does not
    touch `compliance_unlocked`, so choosing a set on a pre-#182 run with a
    history greyed the very pulldown the user had just used. Round 8 drove both
    routes side by side and found the only differing key was that flag.

    MUTATION: remove the unlocked write from `_on_set_chosen` and this goes red.
    """
    from workflow.run_compliance import is_bound, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    assert not is_bound(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        assert is_bound(run), "the premise failed"
        # THE WINDOW'S CONTROLS, NOT THE FLAG. The pulldown route wrote
        # `compliance_unlocked` after the other door had stopped, which put the
        # snapshot-read-as-live fault straight back in through the second door.
        assert run.load_meta().compliance_unlocked is False, (
            "choosing a set recorded a lock the user never lifted")
        dlg._refresh()
        assert dlg._set_combo.isEnabled(), (
            "choosing a limit set greyed the pulldown that chose it")
    finally:
        dlg.deleteLater()


def test_moving_the_app_wide_default_on_an_unbound_run_is_questioned(
        qapp, tmp_path, monkeypatch):
    """The radio writes a preference the moment it is clicked, and on an
    unbound run that preference IS what the run is judged by. It set nothing
    that the old guard watched, so there was no question and no refusal for the
    restore to hang on: the window's header simply started naming a set none of
    the saved reports was judged with.

    The test is no longer "which control was touched" but "did what this run is
    judged by change", so this passes through the same question as the rest.

    MUTATION: drop `or self._judged_by(ctx) != snap["judged_by"]` and this goes
    red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    s = _settings(tmp_path)
    s.set("compliance_default_set", "chromiq_default")
    dlg = _dialog(s, ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._s = settings

            def exec(self):
                # ONLY the radio. No run-column edit at all.
                self._s.set("compliance_default_set", "chromiq_tight")
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert asked, (
            "the app-wide default was moved under an unbound run with eleven "
            "saved reports and nothing was asked")
        assert s.get("compliance_default_set", None) == "chromiq_default", (
            "the refusal left the default moved")
    finally:
        dlg.deleteLater()


def test_an_override_on_a_shipped_column_is_questioned_too(qapp, tmp_path,
                                                           monkeypatch):
    """The fourth door. Crushing a shipped set's cell writes an app-wide
    override the instant it is typed, and on an unbound run that is what the
    run is judged by, so eleven saved verdicts computed at one number sat under
    a window judging at another, silently.

    MUTATION: as above.
    """
    from core.settings import compliance_overrides_of, store_compliance_overrides

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._s = settings

            def exec(self):
                store_compliance_overrides(
                    self._s, {"chromiq_default": {"all_de00_max": 1.0}})
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert asked, "a shipped column was crushed and nothing was asked"
        assert compliance_overrides_of(s) == {}, (
            "the refusal left the app-wide override in place")
    finally:
        dlg.deleteLater()


def test_a_bound_run_is_not_disturbed_by_the_preference(qapp, tmp_path,
                                                        monkeypatch):
    """THE NEGATIVE HALF, and it is what keeps the new rule honest.

    On a BOUND run the preference decides nothing, so moving it is a different
    decision and reverting it would be the app second-guessing one the user
    made deliberately. No question, and the preference stays where they put it.

    MUTATION: restore the preference unconditionally and this goes red.
    """
    proj, run, ti3 = _bound_run_with_dates(tmp_path, 2, unlocked=True)
    s = _settings(tmp_path)
    s.set("compliance_default_set", "chromiq_default")
    dlg = _dialog(s, ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._s = settings

            def exec(self):
                self._s.set("compliance_default_set", "chromiq_tight")
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert not asked, (
            "a bound run asked about a preference that decides nothing for it")
        assert s.get("compliance_default_set", None) == "chromiq_tight", (
            "a deliberate preference click was reverted on a run it does not "
            "affect")
    finally:
        dlg.deleteLater()


def test_putting_the_lock_back_asks_before_it_takes_the_controls(qapp, tmp_path,
                                                                 monkeypatch):
    """Ticking the box asked; unticking it did not, and unticking is the
    direction that takes the controls away. Worse, the box the user would
    untick is one the app ticked for them when it bound the run.

    MUTATION: drop the confirmation from `_on_unlock_toggled` and this goes red.
    """
    from workflow.run_compliance import is_locked

    proj, run, ti3 = _bound_run_with_dates(tmp_path, 2, unlocked=True)
    assert not is_locked(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(t) or False)
        dlg._on_unlock_toggled(False)
        assert asked, "re-locking took the controls away with no question"
        assert not is_locked(run), "a refused re-lock locked the run anyway"

        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        dlg._on_unlock_toggled(False)
        assert is_locked(run), "an accepted re-lock did not lock the run"
    finally:
        dlg.deleteLater()


def test_a_run_one_measurement_old_is_not_shown_a_lock_it_does_not_have(
        qapp, tmp_path, monkeypatch):
    """THIS TEST HAS BEEN WRITTEN THREE WAYS AND THE THIRD IS THE RIGHT ONE.

    It first required no question below two dated verifications. A round then
    showed that WAS the worst state to be silent in, because binding a run
    ticked the unlock box for the user, so one click at one date un-ticked it in
    silence and the box then vanished. The question was added there.

    The next round found the cost: with the shipped preference off, a run one
    measurement old is bound and not unlocked, so that box sat visible, unticked
    and greyed, reading "this run is locked and you cannot change that", beside
    a live pulldown, an "Edit limits…" button and a column of live spin boxes.
    That is the state every run is in after its first verification, and it is
    the state Knut asked for by name.

    The root cause was the tick nobody made. Binding no longer sets the flag on
    a run the lock cannot reach, so at one date there is no ticked box to
    un-tick, the box is not shown at all, and there is nothing to warn about.

    MUTATION: set `compliance_unlocked = True` unconditionally on the bind and
    the companion test below goes red.
    """
    from workflow.run_compliance import is_locked

    proj, run, ti3 = _bound_run_with_dates(tmp_path, 1)
    assert not is_locked(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or False)
        dlg._on_unlock_toggled(False)
        assert not asked, (
            "a run with one dated verification was warned about a lock that "
            "does not apply to it and will not until it is measured again")
    finally:
        dlg.deleteLater()


def test_binding_a_run_with_a_history_still_keeps_its_controls(qapp, tmp_path,
                                                               monkeypatch):
    """The other half, and the reason the flag exists at all.

    At two dated verifications a bind IS a lock, so the run is marked unlocked
    and every control stays where it was.

    MUTATION: drop `measured_dates(run) >= 2` from the bind and this goes red.
    """
    from workflow.run_compliance import is_bound, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    assert not is_bound(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert _edit_a_shipped_column(dlg, monkeypatch), "no question was asked"
        assert is_bound(run)
        assert is_locked(run), (
            "a bound run with a history is locked; that is what binding means")
        assert run.load_meta().compliance_unlocked is False, (
            "the window recorded a lock the user never lifted")
        dlg._refresh()
        assert dlg._set_combo.isEnabled(), (
            "binding a run with a history took away the control that bound it")
        assert not dlg._unlock_check.isVisible(), (
            "the unlock box is offered on a run this window is treating as "
            "unlocked, which is two answers about one run")
    finally:
        dlg.deleteLater()


def test_an_unbound_run_has_nothing_to_lock_and_is_not_asked(qapp, tmp_path,
                                                             monkeypatch):
    """THE NEGATIVE HALF. A question nobody needs is a click people learn to
    dismiss, and a run with no limit set of its own can never lock.

    MUTATION: ask unconditionally and this goes red.
    """
    from workflow.run_compliance import is_bound

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    assert not is_bound(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(t) or True)
        dlg._on_unlock_toggled(False)
        assert not asked, "an unbound run was warned about a lock it cannot have"
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# The three findings round 8 left open
# ---------------------------------------------------------------------------
def _recalc_with(dlg, run, monkeypatch, broken=None, unreadable=None,
                 no_archive=False):
    """Drive `_recalculate_run` with chosen files made unwritable or unreadable."""
    import os
    from workflow.measurement_report import list_reports

    warned: list = []
    import ui.warning_sign as ws
    monkeypatch.setattr(ws, "warn",
                        lambda parent, title, text: warned.append((title, text)))
    dlg._recalculate_run()
    return warned


def test_a_date_only_partly_rewritten_is_not_called_untouched(qapp, tmp_path,
                                                              monkeypatch):
    """Round 8 drove this: three reports on one date, the middle file read-only,
    the folder writable. Two of the three were rewritten, the date was reported
    as untouched, and all three sentences of the message were false in that
    state, including the instruction.

    MUTATION: put the two lists back into one and this goes red.
    """
    import shutil

    from workflow.measurement_report import list_reports

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    v = list(run.verifications())[0]
    src = sorted(v.reports_dir.glob("report_*.json"))[0]
    extra = src.with_name("report_2027-01-01_00-00-00.json")
    shutil.copy2(src, extra)
    extra.chmod(0o444)

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        warned: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn",
                            lambda parent, t, x: warned.append((t, x)))
        dlg._run_ctx = dlg._context_run()
        dlg._recalculate_run()
        assert warned, "a file that could not be written was not reported"
        title, text = warned[0]
        assert "not touched at all" not in text, (
            f"a partly rewritten date was called untouched: {text!r}")
        assert "both old and new verdicts" in text, text
        assert "Individual files can be read-only while their folder is "\
               "writable" in text, text
    finally:
        extra.chmod(0o644)
        dlg.deleteLater()


def test_a_report_that_cannot_be_read_is_named(qapp, tmp_path, monkeypatch):
    """It was skipped by a bare `except: continue`, so a report the user can
    see in the window was never reached by any recalculation and nothing said
    so. Leaving the file alone is the safe direction; the silence was not.

    MUTATION: drop the `unreadable` list and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    v = list(run.verifications())[0]
    bad = v.reports_dir / "report_2027-02-02_00-00-00.json"
    bad.write_text("this is not json", encoding="utf-8")

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        warned: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn",
                            lambda parent, t, x: warned.append((t, x)))
        dlg._run_ctx = dlg._context_run()
        dlg._recalculate_run()
        assert warned, "an unreadable report was skipped in silence"
        assert "could not be read at all" in warned[0][1], warned[0][1]
        assert bad.name in warned[0][1], warned[0][1]
    finally:
        dlg.deleteLater()


def test_a_clean_recalculation_says_nothing(qapp, tmp_path, monkeypatch):
    """THE NEGATIVE HALF. A message that appears when everything worked is how
    people learn to dismiss the one that matters.

    MUTATION: warn unconditionally and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        warned: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn",
                            lambda parent, t, x: warned.append((t, x)))
        dlg._run_ctx = dlg._context_run()
        dlg._recalculate_run()
        assert not warned, f"a clean recalculation warned: {warned}"
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("bound, phrase", [
    (True, "This run is judged by those numbers"),
    (False, "Nothing is judged by those numbers"),
])
def test_the_undo_failure_names_the_right_disagreement(qapp, tmp_path,
                                                       monkeypatch, bound,
                                                       phrase):
    """The message said "the two no longer agree", which is true only when the
    run is bound. On a project made before #182 the run is still unbound, the
    numbers left behind govern nothing, and the sentence named a disagreement
    that did not exist while its instruction fixed nothing.

    MUTATION: use one wording for both and one of these two goes red.
    """
    if bound:
        proj, run, ti3 = _bound_run_with_dates(tmp_path, 2, unlocked=True)
    else:
        proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        seen: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn",
                            lambda parent, t, x: seen.append(x))
        dlg._say_restore_failed(run, OSError("read-only"))
        assert seen, "no message at all"
        assert phrase in seen[0], seen[0]
        assert "Your Preferences were put back" in seen[0], seen[0]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 9: the bind that did not bind, and a question about somebody else's act
# ---------------------------------------------------------------------------
def _edit_a_shipped_column(dlg, monkeypatch, answer=True, value=0.2):
    """Reach the bind WITHOUT touching the run's own column.

    This is the route round 9 used, and it is the one no test had: the dialog
    writes an app-wide override, `run_limits_changed` stays False, and
    `ThresholdsDialog.done()` never writes the run's thresholds.
    """
    from core.settings import store_compliance_overrides

    asked: list = []
    monkeypatch.setattr(type(dlg), "_confirm",
                        lambda self, t, x: asked.append(x) or answer)

    class _Fake:
        run_limits_changed = False

        def __init__(self, settings, parent, run=None, run_editable=False):
            self._s = settings

        def exec(self):
            store_compliance_overrides(
                self._s, {"chromiq_default": {"worst5_de00_avg": value}})
            return 0

        def deleteLater(self):
            pass

    import ui.dialogs.thresholds_dialog as td
    monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
    dlg._on_open_limits()
    return asked


def test_a_run_the_window_binds_is_really_bound(qapp, tmp_path, monkeypatch):
    """`_bind_without_locking_out` wrote the set id, the label, the moment and
    the unlocked flag, and NOT the thresholds, which is the half `is_bound`
    tests. So the run it bound was not bound.

    Round 9 drove what that costs: the run could never lock again, its numbers
    went on following the live app-wide overrides while eleven saved reports
    said something else, `compliance_bound_at` recorded a binding that had not
    happened, and the next verification measurement bound it a third time to
    whatever was live then.

    The route matters. Reaching the bind through the run's own column hides the
    fault, because the dialog writes the thresholds on its way out. This test
    reaches it through a SHIPPED column, where nothing does.

    MUTATION: remove the thresholds write and this goes red.
    """
    from workflow.run_compliance import is_bound, run_limits

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    assert not is_bound(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert _edit_a_shipped_column(dlg, monkeypatch), "no question was asked"
        assert is_bound(run), (
            "the window reported binding this run and `is_bound` says it did "
            "not, so the run can never lock and its numbers still follow the "
            "app-wide preference")
        meta = run.load_meta()
        assert meta.compliance_thresholds, "no numbers were copied onto the run"
        assert run_limits(run, {}).bound
    finally:
        dlg.deleteLater()


def test_a_binding_made_by_someone_else_is_not_put_to_this_user(qapp, tmp_path,
                                                                monkeypatch):
    """The window was opened and nothing in it was touched, while another
    writer bound the run: a second report window, or `ensure_bound` at a
    verification measurement, whose signal is delivered inside this modal's own
    event loop.

    The user was asked "This run has 11 saved reports. Changing the limit set
    recalculates every one of them…" about something they did not do, and the
    natural answer to a question you did not ask for reverted the other writer.

    MUTATION: trigger on a movement in `judged_by` alone and this goes red.
    """
    from workflow.run_compliance import bind_run, is_bound

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        asked: list = []
        monkeypatch.setattr(type(dlg), "_confirm",
                            lambda self, t, x: asked.append(x) or False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                # NOT this window: somebody else, while it sat open.
                bind_run(self._run, "chromiq_tight", {})
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert not asked, (
            "the user was asked about a binding another writer made")
        assert is_bound(run), (
            "answering a question they were not asked reverted the other "
            "writer's binding")
        assert run.load_meta().compliance_set_id == "chromiq_tight"
    finally:
        dlg.deleteLater()


def test_a_refusal_with_nothing_to_undo_reports_no_failure(qapp, tmp_path,
                                                           monkeypatch):
    """`_restore_limits_snapshot` called `save_meta` unconditionally, so on a
    read-only folder it reported a failure where the refusal had been honoured
    completely, and on a project made before #182 a refusal wrote six empty
    compliance keys into a meta.json that had none.

    MUTATION: drop the equality check and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    # COUNT THE WRITE, do not compare the file. The fixture's own `save_meta`
    # has already put the empty compliance keys into `meta.json`, so comparing
    # its text cannot tell a needless write from none at all: the first version
    # of this test passed with the fix removed, which is a test that proves
    # nothing.
    from core.file_manager import Run
    writes: list = []
    _real_save = Run.save_meta
    monkeypatch.setattr(Run, "save_meta",
                        lambda self, m: (writes.append(str(self.dir)),
                                         _real_save(self, m))[1])
    s = _settings(tmp_path)
    s.set("compliance_default_set", "chromiq_default")
    dlg = _dialog(s, ti3)
    try:
        seen: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: seen.append(t))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._s = settings

            def exec(self):
                self._s.set("compliance_default_set", "chromiq_tight")
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert not seen, f"a refusal that undid nothing reported a failure: {seen}"
        assert not writes, (
            "the refusal rewrote the run's meta.json although nothing of the "
            f"user's had been written into it: {writes}")
    finally:
        dlg.deleteLater()


def test_a_date_whose_only_report_cannot_be_read_is_not_called_partly_written(
        qapp, tmp_path, monkeypatch):
    """One line put the date in two lists at once, and the user read four false
    clauses: some reports were recalculated, a file could not be written, the
    date holds old and new verdicts, and the window shows what the unwritten
    file carries. The date has one file, no write was attempted, and there is no
    unwritten file.

    MUTATION: set `_failed` on the unreadable path again and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 1)
    v = list(run.verifications())[0]
    only = sorted(v.reports_dir.glob("report_*.json"))[0]
    only.write_text("this is not json", encoding="utf-8")

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        seen: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: seen.append(x))
        dlg._run_ctx = dlg._context_run()
        dlg._recalculate_run()
        assert seen, "the unreadable file was not reported at all"
        text = seen[0]
        assert "could not be read at all" in text, text
        assert "some of the reports were recalculated" not in text, text
        assert "both old and new verdicts" not in text, text
        assert "Make the files and the folders writable" not in text, (
            "the advice for a permissions problem was given for a corrupt file")
        assert "not a permissions problem" in text, text
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 10
# ---------------------------------------------------------------------------
def test_the_bind_does_not_adopt_numbers_this_window_never_wrote(
        qapp, tmp_path, monkeypatch):
    """A run can hold thresholds and still be unbound, because the limits
    dialog writes numbers without a set id, and the app itself creates that
    state: a refusal whose undo fails leaves them behind, and the message the
    user then reads says those numbers govern nothing.

    Testing "are there thresholds already" adopted exactly those leftovers, so
    a later visit that moved only the "Default for new runs" radio bound the run
    to the chosen set holding a stale number that had never been on screen, and
    rewrote every saved report with it.

    MUTATION: test `if not m.compliance_thresholds` again and this goes red.
    """
    from workflow.compliance_sets import Limit, limits_to_json
    from workflow.run_compliance import is_bound, run_limits

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    # the state the app leaves behind: numbers, no set id
    meta = run.load_meta()
    leftovers = dict(run_limits(run, {}).limits)
    leftovers["all_de00_avg"] = Limit.value(0.31)
    meta.compliance_thresholds = limits_to_json(leftovers)
    meta.compliance_set_id = ""
    run.save_meta(meta)
    assert not is_bound(run), "the fixture is bound, so it proves nothing"

    s = _settings(tmp_path)
    s.set("compliance_default_set", "chromiq_default")
    dlg = _dialog(s, ti3)
    try:
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._s = settings

            def exec(self):
                self._s.set("compliance_default_set", "chromiq_tight")
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert is_bound(run)
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.31) > 1e-9, (
            "the run was bound to a leftover number nobody chose and that was "
            "never on screen")
    finally:
        dlg.deleteLater()


def test_a_run_locked_while_the_window_was_open_keeps_its_numbers(
        qapp, tmp_path, monkeypatch):
    """`run_editable` is decided before the dialog is built and the dialog
    writes as it closes, so a run that becomes locked in between took the edit
    anyway. A challenge round drove both ways in: a verification measurement's
    own `ensure_bound`, and a second window re-locking.

    MUTATION: drop the second `is_locked` check and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_limits)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    before = _saved_json(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(t))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                # somebody else finishes a measurement and binds the run
                bind_run(self._run, "chromiq_default", {})
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.2)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert is_locked(run), "the premise failed: the run is not locked"
        assert told, "the user was not told the run had been locked meanwhile"
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.2) > 1e-9, (
            "an edit landed on a run that was locked while the window was open")
        assert _saved_json(run) == before, (
            "a locked run's saved reports were rewritten")
    finally:
        dlg.deleteLater()


def test_a_date_where_nothing_could_be_written_does_not_claim_it_was(
        qapp, tmp_path, monkeypatch):
    """"the previous reports WERE kept and some of the reports were
    recalculated … so that date now holds both old and new verdicts" assumes
    the date holds more than one file and that one of them was written. Every
    dated verification in the shared demo data ships with exactly one, which is
    the ordinary case.

    MUTATION: put every failed date back in one list and this goes red.
    """
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    v = list(run.verifications())[0]
    only = sorted(v.reports_dir.glob("report_*.json"))[0]
    only.chmod(0o444)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        seen: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: seen.append(x))
        dlg._run_ctx = dlg._context_run()
        dlg._recalculate_run()
        assert seen, "a file that could not be written was not reported"
        text = seen[0]
        assert "none of the reports could be written" in text, text
        assert "some of the reports were recalculated" not in text, (
            f"a date where nothing was written says some of it was: {text!r}")
        assert "both old and new verdicts" not in text, text
    finally:
        only.chmod(0o644)
        dlg.deleteLater()


def test_the_window_does_not_tick_a_lock_box_on_a_run_that_has_no_lock(
        qapp, tmp_path, monkeypatch):
    """The tick nobody made, reached through the window that makes it.

    The companion test above uses `bind_run` directly and therefore never
    touches `_bind_without_locking_out`, so setting the flag unconditionally
    left it green. This one binds a ONE-DATE run through the limits window,
    which is where the flag is written.

    MUTATION: `m.compliance_unlocked = True` unconditionally and this goes red.
    """
    from workflow.run_compliance import is_bound, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 1)
    assert not is_bound(run)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert _edit_a_shipped_column(dlg, monkeypatch), "no question was asked"
        assert is_bound(run), "the premise failed"
        assert not is_locked(run)
        assert run.load_meta().compliance_unlocked is False, (
            "the window ticked 'Unlock this run's limits' on a run nothing had "
            "locked, which asserts the user lifted a lock they never lifted")
        dlg._refresh()
        assert not dlg._unlock_check.isVisible(), (
            "the unlock box is shown on a run with no lock, where it can only "
            "say something untrue")
    finally:
        dlg.deleteLater()


def test_a_refusal_does_not_wipe_a_binding_made_while_the_window_was_open(
        qapp, tmp_path, monkeypatch):
    """The restore was narrowed to the two keys this window can write, and the
    companion test above never reaches it, because a window nobody touched asks
    nothing and therefore restores nothing.

    Here the user DOES edit, so the question is legitimate, and another writer
    binds the run in the same interval. Answering No must undo the user's edit
    and leave the binding alone.

    MUTATION: restore the whole six-key tuple and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, is_bound, run_limits,
                                         set_run_limits, set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                # somebody else binds it, and leaves it unlocked so the write
                # is not refused by the lock guard
                bind_run(self._run, "chromiq_tight", {})
                set_run_unlocked(self._run, True)
                # …and the user's own edit lands on top
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.15)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert is_bound(run), (
            "a refusal wiped a binding another writer made while the window "
            "was open")
        assert run.load_meta().compliance_set_id == "chromiq_tight"
        # AND THE USER IS TOLD THE REFUSAL COULD NOT REACH IT. Silently
        # leaving somebody else's numbers under the refusal is how a run ends
        # up judged by a value that is in no set and no preference.
        assert told, "the refusal could not be honoured and nothing said so"
        assert "changed" in told[0] and "were open" in told[0], told[0]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 11: a value written once as a snapshot, read later as if it were live
# ---------------------------------------------------------------------------
def test_the_window_records_no_lock_the_user_never_lifted(qapp, tmp_path,
                                                          monkeypatch):
    """THREE ROUNDS EACH MOVED THIS FLAG AND ALL THREE WERE WRONG THE SAME WAY.

    `compliance_unlocked` means "the user lifted the lock". Writing it when the
    window binds a run makes it a SNAPSHOT of `measured_dates >= 2`, and that
    number can go DOWN: "Delete a verification" is a shipped menu action. A
    challenge round drove it on a shipped demo project and reached a ticked,
    live box on a run one date old, where one click un-ticked it with no
    question and the box then vanished.

    Nothing is written now. The run really is locked, and this window remembers
    that it bound it, for as long as it is open.

    MUTATION: write the flag on the bind again and this goes red.
    """
    from workflow.run_compliance import is_bound, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert _edit_a_shipped_column(dlg, monkeypatch), "no question was asked"
        assert is_bound(run) and is_locked(run)
        assert run.load_meta().compliance_unlocked is False, (
            "the window recorded that the user had lifted a lock they never "
            "touched, and that record outlives the reason it was written")
    finally:
        dlg.deleteLater()


def test_an_edited_column_survives_a_lock_that_lands_mid_edit(qapp, tmp_path,
                                                              monkeypatch):
    """`bind_run` was used as the undo and it is not an undo.

    It is a fresh bind: its body overwrites the run's thresholds with the SET's
    effective limits. On a run carrying an edited column, that deleted the edit
    both of its saved reports had been judged against, under a message saying
    the limits were unchanged.

    MUTATION: undo with `bind_run` again and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (run_limits, set_run_limits,
                                         set_run_unlocked)

    proj, run, ti3 = _bound_run_with_dates(tmp_path, 2, unlocked=True)
    edited = dict(run_limits(run, {}).limits)
    edited["worst5_de00_avg"] = Limit.value(8.0)
    set_run_limits(run, edited)
    assert run_limits(run, {}).edited, "the fixture is not edited"

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        import ui.warning_sign as ws
        told: list = []
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                set_run_unlocked(self._run, False)      # somebody else re-locks
                lim = dict(run_limits(self._run, {}).limits)
                lim["worst5_de00_avg"] = Limit.value(0.5)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        got = run_limits(run, {}).limits.get("worst5_de00_avg")
        assert got is not None and abs(got.number - 8.0) < 1e-9, (
            f"the run's own edited column was destroyed by the undo: {got}")
        assert told and "unchanged" in told[0], told
    finally:
        dlg.deleteLater()


def test_a_set_this_build_does_not_know_survives_a_lock_mid_edit(
        qapp, tmp_path, monkeypatch):
    """`bind_run`'s first line replaces an unknown set id with the factory
    default, so using it as an undo erased the id, the English label D23 exists
    for, and every number, and told the user nothing had moved.

    MUTATION: undo with `bind_run` again and this goes red.
    """
    from workflow.compliance_sets import Limit, limits_to_json
    from workflow.run_compliance import run_limits, set_run_limits, set_run_unlocked

    proj, run, ti3 = _bound_run_with_dates(tmp_path, 2, unlocked=True)
    meta = run.load_meta()
    numbers = dict(run_limits(run, {}).limits)
    numbers["all_de00_avg"] = Limit.value(1.0)
    meta.compliance_set_id = "chromiq_house_2027"
    meta.compliance_set_label = "House standard 2027"
    meta.compliance_thresholds = limits_to_json(numbers)
    run.save_meta(meta)

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: None)
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                set_run_unlocked(self._run, False)
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.4)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        m = run.load_meta()
        assert m.compliance_set_id == "chromiq_house_2027", (
            "a set from another build was replaced by the factory default")
        assert m.compliance_set_label == "House standard 2027", (
            "the English label D23 exists for was erased")
        # AND ITS NUMBERS. `effective_limits` cannot answer for a set it does
        # not know, so re-deriving would have quietly written the factory
        # default's numbers under this run's own name. The first version of
        # this test checked only the id and the label, and that mutation stayed
        # green.
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 1.0) < 1e-9, (
            f"the unknown set's own numbers were replaced: {got}")
    finally:
        dlg.deleteLater()


def test_a_refused_override_is_never_baked_onto_the_run(qapp, tmp_path,
                                                        monkeypatch):
    """THE PUREST CASE OF TWO CORRECT RULES MEETING.

    The refusal re-derived from the set another writer chose, which is right,
    using the LIVE override table, which still held the override the user had
    just refused, because the preferences are put back later in the same
    function. The run came out permanently judged by a number that is in no set
    and in no preference.

    MUTATION: pass `self._overrides()` to the re-derive again and this goes red.
    """
    from core.settings import compliance_overrides_of, store_compliance_overrides
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: None)
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run, self._s = run, settings

            def exec(self):
                store_compliance_overrides(
                    self._s, {"chromiq_tight": {"worst5_de00_avg": 0.44}})
                bind_run(self._run, "chromiq_tight", {})
                set_run_unlocked(self._run, True)
                lim = dict(run_limits(self._run, {}).limits)
                lim["worst5_de00_avg"] = Limit.value(0.9)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert compliance_overrides_of(s) == {}, "the override was not rolled back"
        got = run_limits(run, {}).limits.get("worst5_de00_avg")
        assert got is not None and abs(got.number - 0.44) > 1e-9, (
            "the run was permanently judged by an override the user refused, "
            "which is now in no set and in no preference")
        assert abs(got.number - 0.9) > 1e-9, (
            "the run kept the very number the user said no to")
    finally:
        dlg.deleteLater()


def test_a_run_rebound_to_an_unknown_set_keeps_that_set_s_own_numbers(
        qapp, tmp_path, monkeypatch):
    """The other half of the unknown-set case, and the one that reaches the
    re-derive.

    The companion test above has the binding UNCHANGED, so it takes the plain
    undo and never reaches the branch that decides whether to re-derive; a
    mutation removing the `is_known_set` guard stayed green there. Here another
    writer rebinds the run to a set this build does not know, which is the state
    a project from a newer ChromIQ arrives in. `effective_limits` cannot answer
    for it, so re-deriving would quietly write the factory default's numbers
    under that run's own name.

    MUTATION: drop `is_known_set` from that condition and this goes red.
    """
    from workflow.compliance_sets import Limit, limits_to_json
    from workflow.run_compliance import run_limits, set_run_limits, set_run_unlocked

    from workflow.run_compliance import bind_run

    # SAVED REPORTS, or nothing is asked and the refusal path is never reached.
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                # somebody else rebinds it to a set from another build
                numbers = dict(run_limits(self._run, {}).limits)
                numbers["all_de00_avg"] = Limit.value(1.0)
                m = self._run.load_meta()
                m.compliance_set_id = "chromiq_house_2027"
                m.compliance_set_label = "House standard 2027"
                m.compliance_thresholds = limits_to_json(numbers)
                self._run.save_meta(m)
                set_run_unlocked(self._run, True)
                # …and the user's own edit lands on top
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.4)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        m = run.load_meta()
        # THE ID AND THE LABEL SURVIVE, WHICH IS THE PART THAT CAN BE SAVED.
        # The numbers cannot: nobody holds what the other writer wrote, because
        # the dialog had already written over them, and `effective_limits`
        # cannot answer for a set this build does not know. Re-deriving would
        # put the FACTORY DEFAULT's numbers under this run's own name, which is
        # the destructive answer; the honest one is to keep the record, leave
        # the numbers, and say plainly that they could not be recovered.
        assert m.compliance_set_id == "chromiq_house_2027", (
            "a set from another build was replaced by the factory default")
        assert m.compliance_set_label == "House standard 2027", (
            "the English label D23 exists for was erased")
        assert told, "the user was not told the refusal could not reach the run"
        # AND WHICH BRANCH IT WAS. This used to assert the generic "could
        # not put the numbers back", the sentence three different outcomes
        # shared. On an unknown set the run keeps the numbers the user has
        # just REFUSED and is judged by them, and only the door beside this
        # one ever said so.
        assert "you have just refused" in told[-1], told[-1]
        # AND THE RUN IS NOT LEFT JUDGING NOTHING. `effective_limits` answers
        # for an unknown set with thirty rows of "no limit", so re-deriving
        # would leave the run bound to a named set that judges not one row,
        # silently, which is worse than the number nobody could recover.
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and got.number is not None, (
            "the run was left bound to a set that judges nothing at all")
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 12
# ---------------------------------------------------------------------------
def test_a_refusal_the_disk_refuses_still_says_so(qapp, tmp_path, monkeypatch):
    """A REGRESSION, MEASURED: two windows before the change, one after.

    `_restore_limits_snapshot` set `ok = True` and never set it False, and
    `_undo_the_edit` swallowed the `OSError` into a bool the caller dropped. So
    `_say_restore_failed` became dead code and a refusal that could not be
    honoured said nothing at all, leaving the run holding the number the user
    had just refused.

    It passed the gate because the only test that touched that message called
    it directly, and nothing tested that the app ever reaches it.

    MUTATION: drop the `_pending_restore_error` check in the caller and this
    goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import run_limits, set_run_limits

    from workflow.run_compliance import bind_run, set_run_unlocked

    # SAVED REPORTS, or nothing is asked and the refusal path is never reached.
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.37)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                # …and the folder goes read-only while the question is up
                import core.file_manager as fm
                monkeypatch.setattr(
                    fm.Run, "save_meta",
                    lambda self, m: (_ for _ in ()).throw(
                        PermissionError("read-only")))
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert told, (
            "the refusal could not be written and the app said nothing, so the "
            "run keeps the number the user refused with no trace on screen")
        assert "could not put the previous numbers back" in told[0], told[0]
    finally:
        dlg.deleteLater()


def test_the_pulldown_and_the_limits_window_agree_about_one_run(
        qapp, tmp_path, monkeypatch):
    """`_sync_limit_controls` treated a run this window bound as unlocked, so
    the pulldown stayed live and the button read "Edit limits…"; the dialog was
    built from the raw predicate, so the same run opened a READ-ONLY column
    whose note pointed at an unlock box the window was hiding.

    Three controls, three answers about one run, which is the fault two earlier
    rounds each fixed once.

    MUTATION: build the dialog from `is_locked` again and this goes red.
    """
    from workflow.run_compliance import is_bound, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    seen: list = []

    class _Fake:
        run_limits_changed = False

        def __init__(self, settings, parent, run=None, run_editable=False):
            seen.append(bool(run_editable))

        def exec(self):
            return 0

        def deleteLater(self):
            pass

    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert _edit_a_shipped_column(dlg, monkeypatch), "no question was asked"
        assert is_bound(run) and is_locked(run), "the premise failed"
        dlg._refresh()
        assert dlg._set_combo.isEnabled(), "the window greyed the pulldown"

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        seen.clear()
        dlg._on_open_limits()
        assert seen == [True], (
            "the window shows a live pulldown and an 'Edit limits…' button for "
            f"this run and then opens a read-only column: run_editable={seen}")
    finally:
        dlg.deleteLater()


def test_a_rebind_to_the_same_set_is_not_mistaken_for_no_change(
        qapp, tmp_path, monkeypatch):
    """"The binding has not moved" was tested by set id alone, so a writer that
    rebound to the SAME set with different numbers looked unmoved and the undo
    wrote the snapshot back over numbers somebody else had just chosen, under a
    message saying the limits were unchanged.

    `bind_run` stamps `compliance_bound_at` every time, which is the only signal
    that distinguishes a rebind from the dialog's own write.

    MUTATION: compare set ids alone again and this goes red.
    """
    from core.settings import store_compliance_overrides
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: False)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run, self._s = run, settings

            def exec(self):
                # somebody else rebinds to the SAME set, with moved overrides
                store_compliance_overrides(
                    self._s, {"chromiq_default": {"all_de00_avg": 0.77}})
                bind_run(self._run, "chromiq_default",
                         {"chromiq_default": {"all_de00_avg": 0.77}})
                # A MEASUREMENT TAKES LONGER THAN A SECOND, and the signal that
                # says "somebody else rebound this" is stamped to the second.
                # The fixture binds twice inside one second, which nothing a
                # person can do reaches; the stamp is moved to what a real
                # rebind would leave.
                _m = self._run.load_meta()
                _m.compliance_bound_at = "2027-01-01T00:00:00"
                self._run.save_meta(_m)
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.37)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        # WHAT CAN BE PROVED IS THAT THE USER IS TOLD. Nobody holds the other
        # writer's numbers once the dialog has written over them, so this
        # cannot assert that 0.77 survives; what it can assert is that the app
        # no longer calls the result unchanged, which is what it did while the
        # test was set ids alone.
        assert told, (
            "a writer rebound this run to the same set with different numbers, "
            "the undo wrote the snapshot back over them, and nothing said so")
        assert "could not put its own numbers back" in told[-1], told[-1]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 13: the same function disagreed with itself, twelve lines apart
# ---------------------------------------------------------------------------
def test_an_edit_on_a_run_this_window_bound_is_kept(qapp, tmp_path, monkeypatch):
    """`_on_open_limits` built the dialog from `_locked_here` and guarded the
    WRITE with the raw `is_locked`, twelve lines apart in one function.

    So on a run this window had just bound, it offered an editable column, took
    the number the user typed, threw it away, and told them something else had
    locked the run while they were editing it. Nothing else had. The remedy the
    message points at is hidden in that state, so the user can repeat it for
    ever.

    THE TEST THAT COVERED THIS FUNCTION COULD NOT SEE IT. Its fake dialog
    writes nothing, so `moved` is False and the guarded line is never reached; a
    challenge round proved that with a mutation pair, one landing nowhere. This
    one WRITES, which is the whole point.

    MUTATION: put `is_locked` back on the write guard and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (is_bound, is_locked, run_limits,
                                         set_run_limits)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 3)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))

        # 1. this window binds it, which is what locks it
        assert _edit_a_shipped_column(dlg, monkeypatch), "no question was asked"
        assert is_bound(run) and is_locked(run), "the premise failed"
        told.clear()

        # 2. …and the window still offers the column, so an edit must be kept
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Writes:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run, self._editable = run, run_editable

            def exec(self):
                assert self._editable, (
                    "the window offered 'Edit limits…' and then opened a "
                    "read-only column")
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.42)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Writes)
        dlg._on_open_limits()

        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.42) < 1e-9, (
            f"the window offered the edit and then discarded it: {got}")
        assert not told, (
            "the user was told something else had locked the run, and nothing "
            f"had: {told}")
    finally:
        dlg.deleteLater()


def test_a_run_locked_by_somebody_else_still_refuses_the_edit(qapp, tmp_path,
                                                              monkeypatch):
    """THE NEGATIVE HALF, and the reason the guard exists at all.

    A run this window did NOT bind, locked while the window was open, must
    still refuse the edit and say so.

    MUTATION: use `_locked_here` where `is_locked` belongs, or drop the guard,
    and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_limits, set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        class _Fake:
            run_limits_changed = False

            def __init__(self, settings, parent, run=None, run_editable=False):
                self._run = run

            def exec(self):
                set_run_unlocked(self._run, False)      # somebody else locks it
                lim = dict(run_limits(self._run, {}).limits)
                lim["all_de00_avg"] = Limit.value(0.3)
                set_run_limits(self._run, lim)
                type(self).run_limits_changed = True
                return 0

            def deleteLater(self):
                pass

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
        dlg._on_open_limits()

        assert is_locked(run), "the premise failed"
        got = run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.3) > 1e-9, (
            "an edit landed on a run somebody else locked while the window "
            "was open")
        assert told, "the user was not told the run had been locked"
    finally:
        dlg.deleteLater()


def test_a_second_limits_window_that_moved_the_run_is_not_silent(qapp, tmp_path,
                                                                 monkeypatch):
    """R13-2: THE OTHER WRITER THAT LEAVES NO STAMP.

    "The binding has not moved" was tested with `compliance_bound_at`, and only
    `bind_run` stamps it. The other writer of a run's column is
    `set_run_limits`, which is `ThresholdsDialog.done()`, which is this same
    window opened a second time. A challenge round drove three cases side by
    side and counted the message boxes:

        another bind_run                    2 boxes, the user is told
        a real second limits window         1 box, its number erased, and
                                            indistinguishable from
        nobody else writes at all           1 box

    So the second window's number vanished under a message saying the limits
    were unchanged. It is unchanged, of the run; that is not what happened.

    MUTATION: stop the dialog setting `run_limits_collided`, or read it and
    ignore it, and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (run_limits, set_run_limits,
                                         set_run_unlocked)

    MINE, THEIRS = 0.77, 0.55
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from workflow.run_compliance import bind_run

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)              # keep the column editable
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        before = dict(run_limits(run, {}).limits)
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        # the user is ASKED and says no, which is the route into the undo
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: False)

        class _First(ThresholdsDialog):
            def exec(self):
                # somebody else writes the run while this window sits open
                other = dict(run_limits(run, {}).limits)
                other["all_de00_avg"] = Limit.value(THEIRS)
                set_run_limits(run, other)
                # …and then this window is closed, writing the user's number
                self._run_limits["all_de00_avg"] = Limit.value(MINE)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        now = run_limits(run, {}).limits.get("all_de00_avg")
        assert now is not None and abs(now.number - MINE) > 1e-9, (
            "the number the user refused was left on the run")
        assert told, ("a second limits window erased this run's limits and the "
                      "user was told nothing")
        said = "\n".join(told)
        assert "another window" in said, said
        assert abs(before["all_de00_avg"].number - now.number) < 1e-9, (
            "the refusal did not put the previous numbers back")
        assert "put this run's own numbers back to what they were" in said, (
            "the user was told the numbers could not be put back, and they "
            f"were: {said}")
    finally:
        dlg.deleteLater()


def test_a_perfect_undo_on_an_unbound_run_is_not_reported_as_a_failure(
        qapp, tmp_path, monkeypatch):
    """R14-4: THE R13-3 SHAPE, RECURRING INSIDE R13-3'S OWN FIX.

    `kept` was `_undo_the_edit`'s return, and that return was "was the run
    bound when the window opened", not "did the previous numbers come back".
    On a project made before #182 the run is unbound, so the undo puts the
    EMPTY column back, exactly as it was, perfectly, and the user was told
    ChromIQ could not put this run's own numbers back. The one accurate
    sentence available was the one withheld.

    An empty column is the previous numbers when the run had none.

    MUTATION: return `_was_bound` again from the successful branch and this
    goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (is_bound, run_limits, set_run_limits)

    THEIRS = 0.61
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    assert not is_bound(run), "the premise failed"
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: False)

        class _First(ThresholdsDialog):
            def exec(self):
                # another window writes the run's column while this one is open
                other = dict(run_limits(run, {}).limits)
                other["all_de00_avg"] = Limit.value(THEIRS)
                set_run_limits(run, other)
                self._run_limits["all_de00_avg"] = Limit.value(0.99)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert not (run.load_meta().compliance_thresholds or {}), (
            "the run kept numbers it never had before the window opened")
        said = "\n".join(told)
        assert said, "the user was told nothing"
        assert "put this run's own numbers back to what they were" in said, (
            "the undo was perfect and the user was told it had failed: " + said)
    finally:
        dlg.deleteLater()


def test_another_windows_column_choice_is_not_reverted_in_silence(
        qapp, tmp_path, monkeypatch):
    """R14-5: THE COLLISION DETECTOR WATCHED HALF OF WHAT THE UNDO PUTS BACK.

    A Report limits window can write two things about a run: its numbers and
    which columns the report shows. `_undo_the_edit` restores both. The check
    that asks whether somebody else wrote looked only at the numbers, so a
    second window's column choice was reverted with no collision reported and
    nothing said to anybody.

    MUTATION: watch `compliance_thresholds` alone again and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: False)

        class _First(ThresholdsDialog):
            def exec(self):
                # another window changes only WHICH COLUMNS the report shows
                m = run.load_meta()
                m.compliance_columns = ["chromiq_default", "chromiq_strict"]
                run.save_meta(m)
                # …and this one edits a number, so there is something to refuse
                self._run_limits["all_de00_avg"] = Limit.value(0.88)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert told, ("another window's choice of columns was reverted and "
                      "nobody was told")
        assert "another window" in "\n".join(told), told
    finally:
        dlg.deleteLater()


def test_the_pulldown_refuses_a_run_that_was_locked_while_it_sat_open(
        qapp, tmp_path, monkeypatch):
    """R14-2: THE THIRD DOOR, AND IT NEVER HAD A LOCK CHECK AT ALL.

    The limits door got one, and round 13 corrected which question it asks.
    This one was never guarded: the lock is read when the window refreshes, to
    decide whether the pulldown is ENABLED, and nothing outside the window
    triggers a refresh. So a run locked while the window sits open, by its own
    verification measurement finishing or by another window, keeps a live
    pulldown, and one selection rebinds it and rewrites every saved report.

    A challenge round drove both ways in and watched a verdict go from FAIL to
    PASS on a locked run under nothing but the ordinary recalculate question.

    MUTATION: drop the guard and this goes red.
    """
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)               # unlocked, so the combo is live
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)   # would say yes
        before = run_limits(run, {})

        # somebody else locks it while the window sits open
        set_run_unlocked(run, False)
        assert is_locked(run), "the premise failed"

        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i)
                     and dlg._set_combo.itemData(i) != before.set_id)
        idx = dlg._set_combo.findData(other)
        dlg._on_set_chosen(idx)

        after = run_limits(run, {})
        assert after.set_id == before.set_id, (
            f"a locked run was rebound from {before.set_id} to {after.set_id}")
        assert told, "the run was locked and the user was told nothing"
        assert "locked" in "\n".join(told).lower(), told
    finally:
        dlg.deleteLater()


def test_the_pulldown_still_moves_a_run_this_window_just_bound(
        qapp, tmp_path, monkeypatch):
    """THE OTHER HALF OF R14-2's GUARD, and without it the guard is R13-1.

    Binding a run that already has a history is what locks it, so a guard on
    this door that asks the raw predicate greys out the pulldown the user has
    just used, one selection after they used it. That is the fault rounds 11
    and 12 each fixed once, and round 13 found it re-introduced twelve lines
    from where it had been fixed.

    Proved necessary by mutation: swapping `_locked_here` for `is_locked` on
    the guard above broke no test in either file that owns this window.

    MUTATION: use the raw `is_locked` on that guard and this goes red.
    """
    from workflow.run_compliance import is_bound, is_locked, run_limits

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        ids = [dlg._set_combo.itemData(i) for i in range(dlg._set_combo.count())
               if dlg._set_combo.itemData(i)]
        first, second = ids[0], ids[1]
        if run_limits(run, {}).set_id == first:
            first, second = second, first

        dlg._on_set_chosen(dlg._set_combo.findData(first))
        assert is_bound(run) and is_locked(run), (
            "the premise failed: binding a run with a history must lock it")
        told.clear()

        dlg._on_set_chosen(dlg._set_combo.findData(second))
        assert run_limits(run, {}).set_id == second, (
            "the window bound the run and then refused to let it be changed "
            "again, which is the control the user had just used")
        assert not told, told
    finally:
        dlg.deleteLater()


def test_going_ahead_over_another_windows_change_is_not_silent(qapp, tmp_path,
                                                               monkeypatch):
    """R14-1: THE COLLISION WAS REPORTED ON ONE PATH OF TWO.

    `run_limits_collided` was read in exactly one place, inside the refusal.
    A user who said YES lost the other window's change in silence: one box, the
    ordinary recalculate question, indistinguishable from the case where
    nobody else wrote at all. And on a run with no saved reports there is no
    question to ask, so nothing whatever appeared.

    MUTATION: stop reading `collided` outside the refusal and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    MINE, THEIRS = 0.81, 0.44
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        # THE USER SAYS YES, which is the path that said nothing
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        class _First(ThresholdsDialog):
            def exec(self):
                other = dict(run_limits(run, {}).limits)
                other["all_de00_avg"] = Limit.value(THEIRS)
                set_run_limits(run, other)
                self._run_limits["all_de00_avg"] = Limit.value(MINE)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        now = run_limits(run, {}).limits.get("all_de00_avg")
        assert now is not None and abs(now.number - MINE) < 1e-9, (
            f"the accepted edit did not land: {now}")
        said = "\n".join(told)
        assert said, ("the other window's change was overwritten and the user "
                      "was told nothing")
        assert "another window" in said and "went ahead" in said, said
    finally:
        dlg.deleteLater()


def test_the_collision_check_cannot_tell_a_corrupt_meta_from_an_unbound_run(
        tmp_path):
    """R14-6: THE DOCSTRING CLAIMED A DISTINCTION THE CODE CANNOT MAKE.

    `_stored_column` used to say it answers None when the run "cannot be read".
    `Run.load_meta` never raises: a truncated or absent `meta.json` is answered
    with a fresh `RunMeta`, deliberately, for Knut's D2 case. So a corrupt meta
    reads here exactly like an unbound run, the `except` branch was dead, and
    the sentence describing it was decoration.

    This pins the behaviour the docstring now describes, rather than the one it
    used to claim.
    """
    from ui.dialogs.thresholds_dialog import _stored_column

    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    unbound = _stored_column(run)

    run.meta_path.write_text("{ this is not json", encoding="utf-8")
    corrupt = _stored_column(run)

    assert corrupt is not None, (
        "a corrupt meta raised or was reported as unreadable, which "
        "Run.load_meta does not do")
    assert corrupt == unbound, (
        "the two are distinguishable after all, and the docstring should say "
        f"how: {corrupt!r} vs {unbound!r}")
    assert _stored_column(None) is None


def test_the_window_does_not_report_its_own_write_as_somebody_elses(
        qapp, tmp_path, monkeypatch):
    """R15-1: ONE USER, ONE WINDOW, AND THE APP BLAMED ANOTHER WINDOW.

    The collision check compares what the run holds when the window closes
    against what it held when it opened. `_on_column_toggled` writes
    `set_run_columns` the MOMENT the box is ticked, so ticking a column and
    typing a number in the same visit, which is the ordinary use of that
    window, raised the collision against the window's own work.

    On accept the user was told another window had changed the run and their
    other change was gone, with nothing else running and the columns still on
    disk. On refusal their own column choice, made seconds earlier in that same
    window, was reverted in silence and another window was blamed for it.

    A challenge round drove it in English and German. The two tests that
    existed covered accept with numbers and refusal with columns written by a
    fake; nobody crossed them.

    MUTATION: stop refreshing the baseline after this window's own write and
    this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, set_run_unlocked

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        class _OneUser(ThresholdsDialog):
            def exec(self):
                # the user ticks a column off, which writes at once …
                self._column_checks["chromiq_quick"].setChecked(False)
                # … and types a number, which writes at close
                self._run_limits["all_de00_avg"] = Limit.value(0.66)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _OneUser)
        dlg._on_open_limits()

        said = "\n".join(told)
        assert "another window" not in said, (
            "the window reported its own write as somebody else's: " + said)
        cols = list(run.load_meta().compliance_columns or [])
        assert cols and "chromiq_quick" not in cols, (
            f"the user's own column choice did not survive: {cols}")
    finally:
        dlg.deleteLater()


def test_the_unlock_door_checks_the_run_before_it_acts(qapp, tmp_path,
                                                       monkeypatch):
    """R15-2: THE THIRD DOOR INTO A RECALCULATION, GUARDED NOWHERE.

    The other two were guarded in earlier rounds. This one imported
    `is_locked` and never called it. Its own question promises the dated
    reports will be recalculated "with the numbers you set"; a challenge round
    rebound the run while that question was on screen and watched a saved
    verdict go from PASS to FAIL, computed with somebody else's numbers, under
    that sentence.

    MUTATION: drop the check after the question and this goes red.
    """
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_limits)
    from workflow.compliance_sets import Limit

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    s = _settings(tmp_path)
    # THE OTHER HALF OF THE GUARD MUST NOT BE WHAT KILLS THIS.
    # Without this the run does not qualify to be unlocked at all, the
    # `may_unlock` half refuses first, and a mutation that removes the check
    # this test is named for leaves it green. Measured: it did.
    s.set("compliance_allow_edit_after_measurement", True)
    dlg = _dialog(s, ti3)
    try:
        assert is_locked(run), "the premise failed"
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        recalculated: list = []
        monkeypatch.setattr(type(dlg), "_recalculate_run",
                            lambda self: recalculated.append(1))

        def _asked(self, title, body):
            # somebody else rebinds the run while the question is on screen
            other = dict(run_limits(run, {}).limits)
            other["all_de00_avg"] = Limit.value(0.05)
            set_run_limits(run, other)
            return True

        monkeypatch.setattr(type(dlg), "_confirm", _asked)
        dlg._on_unlock_toggled(True)

        assert not recalculated, (
            "the reports were recalculated with numbers the user never saw, "
            "under a question saying they were the user's own")
        assert is_locked(run), "the run was unlocked anyway"
        assert told, "the user was told nothing"
        assert "no longer the run that question was about" in "\n".join(told), told
    finally:
        dlg.deleteLater()


def test_the_unlock_door_refuses_a_run_that_stopped_qualifying(qapp, tmp_path,
                                                               monkeypatch):
    """THE OTHER HALF OF R15-2. The tick box is enabled from `may_unlock` and a
    measured verification as they were when the window last refreshed, and
    nothing outside the window refreshes it. A run that stops qualifying while
    the window sits open was unlocked anyway.

    MUTATION: drop `may_unlock` from the check and this goes red.
    """
    from workflow.run_compliance import bind_run, is_locked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    s = _settings(tmp_path)
    s.set("compliance_allow_edit_after_measurement", True)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_recalculate_run", lambda self: None)

        def _asked(self, title, body):
            # the preference is withdrawn while the question is on screen
            s.set("compliance_allow_edit_after_measurement", False)
            return True

        monkeypatch.setattr(type(dlg), "_confirm", _asked)
        dlg._on_unlock_toggled(True)

        assert is_locked(run), (
            "the run was unlocked after it stopped being allowed to be")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_another_writers_default_set_is_not_reverted_in_silence(qapp, tmp_path,
                                                                monkeypatch):
    """R15-3: A LIMITS WINDOW WRITES THREE STORES AND ONE WAS WATCHED.

    `_restore_limits_snapshot` puts `compliance_default_set` and the app-wide
    overrides back to this window's snapshot unconditionally. So another
    writer's change to the default set, which is what EVERY unbound run is
    judged by, was destroyed on a refusal with no collision raised and nothing
    said to anybody.

    MUTATION: stop reading `prefs_collided`, or stop setting it, and this goes
    red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, set_run_unlocked

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: False)          # the user refuses

        class _First(ThresholdsDialog):
            def exec(self):
                # somebody else changes what every unbound run is judged by
                s.set("compliance_default_set", "chromiq_tight")
                # …and this window has an edit of its own to refuse
                self._run_limits["all_de00_avg"] = Limit.value(0.73)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        said = "\n".join(told)
        assert told, ("another window's default set was reverted and nobody "
                      "was told")
        # AND IT IS ITS OWN MESSAGE, NOT THE RUN'S. Folded into the run's, it
        # announced a change to the app-wide preferences as a change to a run
        # whose files nothing had touched. It no longer claims the reverse
        # either: this window may have just moved the run's own numbers, so
        # "no run's own limits were touched" was a promise it cannot make, and
        # a challenge round photographed it under a box saying the opposite.
        assert "Preferences" in said, said
        assert "run's own limits were touched" not in said, said
        assert "that change is gone too" in said, said
    finally:
        dlg.deleteLater()


def test_the_window_does_not_report_its_own_preference_write_as_somebody_elses(
        qapp, tmp_path, monkeypatch):
    """R15-1's SHAPE, ON THE PREFERENCES STORE.

    The collision check for the two app-wide stores compares them at close
    against what they held at open, and this window writes them the moment a
    shipped column's cell is touched. Without a refresh after its own write it
    accuses another window of its own edit, exactly as the column tick box did.

    Proved necessary by mutation: removing that refresh broke no test until
    this one existed.

    MUTATION: drop the baseline refresh after `store_compliance_overrides` and
    this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, set_run_unlocked

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        class _OneUser(ThresholdsDialog):
            def exec(self):
                # the user changes an app-wide override, which writes at once
                self._overrides.setdefault("chromiq_default", {})[
                    "worst5_de00_avg"] = 0.31
                self._write_overrides()
                # …and moves "Default for new runs", the other app-wide store,
                # which also writes the moment it is clicked. Both refreshes
                # are needed and each was proved by its own mutation.
                _other = next(c for c, rb in self._default_radios.items()
                              if not rb.isChecked() and rb.isEnabled())
                self._default_radios[_other].setChecked(True)
                # …and a number of the run's own, which writes at close
                self._run_limits["all_de00_avg"] = Limit.value(0.52)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _OneUser)
        dlg._on_open_limits()

        assert "another window" not in "\n".join(told), (
            "the window reported its own preference write as somebody "
            "else's: " + "\n".join(told))
    finally:
        dlg.deleteLater()


def test_the_unlock_door_sees_a_rebind_that_happened_BEFORE_the_click(
        qapp, tmp_path, monkeypatch):
    """R16-4: THE GUARD STAMPED "BEFORE" TOO LATE, so the interesting half of
    the window was already inside it.

    A guard that reads the run at the moment the tick is clicked has already
    swallowed everything that happened while the user was reading the screen,
    and that is the whole window a second writer has to work in. The test that
    was written for this made the other window's change inside the
    confirmation, which is the ordering the late stamp DOES catch; its
    docstring described the ordering it does not.

    A challenge round drove the real one: rebind the run, then click the tick.
    One box, the unlock written, and a saved verdict recomputed from the other
    writer's numbers.

    MUTATION: stamp `_before` at the click again and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_limits)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    s = _settings(tmp_path)
    s.set("compliance_allow_edit_after_measurement", True)
    dlg = _dialog(s, ti3)
    try:
        assert is_locked(run), "the premise failed"
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        recalculated: list = []
        monkeypatch.setattr(type(dlg), "_recalculate_run",
                            lambda self: recalculated.append(1))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        # SOMEBODY ELSE REBINDS IT WHILE THE USER IS READING THE SCREEN,
        # which is BEFORE the click, not during the question.
        other = dict(run_limits(run, {}).limits)
        other["all_de00_avg"] = Limit.value(0.05)
        set_run_limits(run, other)

        dlg._on_unlock_toggled(True)

        assert not recalculated, (
            "the dated reports were recalculated from numbers the user never "
            "saw, under a question saying they were the user's own")
        assert is_locked(run), "the run was unlocked anyway"
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_one_column_click_does_not_blind_the_window_to_a_real_collision(
        qapp, tmp_path, monkeypatch):
    """R16-1: A BASELINE REFRESHED WIDER THAN THE WRITE THAT EARNED IT.

    The column tick box writes at once, so it must tell the collision check it
    has seen its own work. The fix refreshed the WHOLE baseline, and the
    baseline holds the run's numbers as well, so one unrelated click swallowed
    a numbers change another window had made while this one sat open. The
    collision then never fired and the other window's number was destroyed in
    silence.

    That is the same fault as not refreshing at all, and worse, because it
    fails quiet: the control case, with no click, is told.

    MUTATION: refresh the whole baseline again and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    THEIRS = 9.25
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        class _First(ThresholdsDialog):
            def exec(self):
                # another window changes this run's NUMBERS
                other = dict(run_limits(run, {}).limits)
                other["all_de00_avg"] = Limit.value(THEIRS)
                set_run_limits(run, other)
                # …and this user ticks a column, which is unrelated to it
                self._column_checks["chromiq_quick"].setChecked(False)
                self._run_limits["all_de00_avg"] = Limit.value(4.75)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert told, ("one click on a column tick box made the window blind to "
                      "another window's change of this run's numbers")
        assert "another window" in "\n".join(told), told
    finally:
        dlg.deleteLater()


def test_going_ahead_does_not_claim_a_preference_change_is_gone(qapp, tmp_path,
                                                                monkeypatch):
    """R16-2: THE SENTENCE WAS FALSE ON THE PATH WHERE NOTHING IS PUT BACK.

    A collision on the app-wide preferences was reported through the run's own
    message, whose accept-path wording says the other change is gone. Nothing
    is put back on that path, so the other change is still on disk. A challenge
    round read the value off the settings to prove it.

    MUTATION: report the preferences collision through the run's message again
    and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, set_run_unlocked

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)          # the user accepts

        class _First(ThresholdsDialog):
            def exec(self):
                s.set("compliance_default_set", "chromiq_tight")
                self._run_limits["all_de00_avg"] = Limit.value(0.64)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert s.get("compliance_default_set") == "chromiq_tight", (
            "the premise failed: the other change should still be on disk")
        said = "\n".join(told)
        assert "Preferences" in said, said
        assert "whichever change was made last" in said, (
            "the user was told the other change was gone, and it is still on "
            "disk: " + said)
    finally:
        dlg.deleteLater()


def test_one_radio_click_does_not_blind_the_window_to_an_override_change(
        qapp, tmp_path, monkeypatch):
    """R16-2, THE OTHER HALF: ONE BASELINE PER STORE.

    The two app-wide stores shared a baseline, and each refresh rewrote the
    whole of it. So this window's click on "Default for new runs" swallowed
    another writer's change to the overrides, and the other way round. The
    watch never fired and the change was destroyed in silence.

    MUTATION: share one baseline between the two stores again and this goes
    red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, set_run_unlocked
    from core.settings import store_compliance_overrides

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: False)

        class _First(ThresholdsDialog):
            def exec(self):
                # another window changes the OVERRIDES
                store_compliance_overrides(
                    s, {"chromiq_default": {"all_de00_max": 7.5}})
                # …and this user moves the radio, which is the OTHER store
                _other = next(c for c, rb in self._default_radios.items()
                              if not rb.isChecked() and rb.isEnabled())
                self._default_radios[_other].setChecked(True)
                self._run_limits["all_de00_avg"] = Limit.value(0.37)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert "Preferences" in "\n".join(told), (
            "one click on the radio made the window blind to another window's "
            f"change of the overrides: {told}")
    finally:
        dlg.deleteLater()


def test_the_locked_window_does_not_talk_about_a_refusal(qapp, tmp_path,
                                                         monkeypatch):
    """R16-3: A SENTENCE ABOUT REFUSING, SHOWN WHERE NOTHING WAS REFUSED.

    `_say_locked_meanwhile` follows no question at all: the lock stopped the
    edit, and this window is the first the user sees. Round 15 gave both
    messages one sentence function, and its wording assumes a refusal. So on a
    run that is still locked the user was told "the other change is gone too",
    where the only other change was the lock and the undo never touches it.

    MUTATION: call `_restore_sentence` with the refusal wording here again and
    this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_limits, set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))

        class _Locks(ThresholdsDialog):
            def exec(self):
                # the run is locked again while this window is open, and the
                # user's edit is written on the way out
                self._run_limits["all_de00_avg"] = Limit.value(0.29)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                set_run_unlocked(run, False)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Locks)
        dlg._on_open_limits()

        assert is_locked(run), "the premise failed"
        said = "\n".join(told)
        assert said, "the user was told nothing"
        assert "locked" in said.lower(), said
        assert "refused" not in said, (
            "the user was told they refused something, and they were never "
            "asked: " + said)
        assert "the other change is gone" not in said, (
            "the only other change was the lock, which the undo never "
            "touches: " + said)
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Round 17: a question takes as long as a person takes to read it
# ---------------------------------------------------------------------------
def _relock_during(dlg, monkeypatch, run, method="_confirm_recalculate"):
    """Answer the door's question yes, and re-lock the run while it is on
    screen, which is the state four rounds kept finding in a fourth door."""
    from workflow.run_compliance import set_run_unlocked

    def _asked(self, *a, **k):
        set_run_unlocked(run, False)
        return True

    monkeypatch.setattr(type(dlg), method, _asked)


def test_the_pulldown_checks_the_lock_after_its_question_too(qapp, tmp_path,
                                                            monkeypatch):
    """R17-1: THE GUARD RAN BEFORE THE QUESTION AND NOTHING RAN AFTER IT.

    Round 16 fixed this exact shape on the unlock door. The pulldown asks the
    same question, for the same rebind and the same recalculation, and
    re-checked nothing. A challenge round re-locked the run while the question
    was on screen: the user said yes, a locked run was rebound and a saved
    verdict went from FAIL to PASS, under one box identical to the control.
    The same re-lock one moment earlier fired a full guard.

    MUTATION: ask with `_confirm_recalculate` instead of `_confirm_about_run`
    and this goes red.
    """
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        _relock_during(dlg, monkeypatch, run)
        before = run_limits(run, {}).set_id

        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i)
                     and dlg._set_combo.itemData(i) != before)
        dlg._on_set_chosen(dlg._set_combo.findData(other))

        assert is_locked(run), "the premise failed"
        assert run_limits(run, {}).set_id == before, (
            "a run locked while the question was on screen was rebound anyway")
        assert told and "no longer the run" in "\n".join(told), told
    finally:
        dlg.deleteLater()


def test_the_limits_door_checks_the_run_after_its_question_too(qapp, tmp_path,
                                                               monkeypatch):
    """R17-2: THE SAME HOLE, AND WORSE, BECAUSE THE WINDOW HAS ALREADY
    WRITTEN.

    `_on_open_limits` reads the world, decides whether anything moved, tests
    the lock, and then asks. A challenge round wrote this run's own numbers
    from another window while that question was on screen: the collision check
    had already run, so nothing was raised, and the recalculation judged every
    saved report by a number the user never typed and never saw. With a tight
    value a saved report goes from PASS to FAIL on a limit nobody chose.

    MUTATION: drop the check after the question and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    MINE, THEIRS = 0.80, 0.01
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        recalculated: list = []
        monkeypatch.setattr(type(dlg), "_recalculate_run",
                            lambda self: recalculated.append(1))

        def _asked(self, r):
            # somebody else writes the run WHILE the question is on screen
            other = dict(run_limits(run, {}).limits)
            other["all_de00_avg"] = Limit.value(THEIRS)
            set_run_limits(run, other)
            return True

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)

        class _First(ThresholdsDialog):
            def exec(self):
                self._run_limits["all_de00_avg"] = Limit.value(MINE)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert not recalculated, (
            "every saved report was recalculated against a number written by "
            "another window while the question was on screen")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_a_lock_does_not_silence_the_preferences_message(qapp, tmp_path,
                                                         monkeypatch):
    """R17-4: THE LOCKED BRANCH RETURNS ABOVE WHERE THE APP-WIDE COLLISION IS
    REPORTED.

    So a lock arriving at the same moment made the window silent about a
    change it is noisy about otherwise, and left that change standing.

    MUTATION: drop the report from the locked branch and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))

        class _Locks(ThresholdsDialog):
            def exec(self):
                s.set("compliance_default_set", "chromiq_tight")
                self._run_limits["all_de00_avg"] = Limit.value(0.41)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                set_run_unlocked(run, False)          # …and it is locked again
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _Locks)
        dlg._on_open_limits()

        said = "\n".join(told)
        assert "Preferences" in said, (
            "a lock at the same moment silenced the app-wide message: " + said)
    finally:
        dlg.deleteLater()


def test_a_second_measurement_arriving_during_the_question_is_seen(
        qapp, tmp_path, monkeypatch):
    """NEITHER BLOCKER NEEDS A SECOND PROCESS, and this is why.

    `is_locked` counts dated verifications: a run with one is unlocked by rule
    and becomes locked the moment a second measurement finishes. That crossing
    touches no field the first version of this guard watched, so the count is
    part of the run's state now. A challenge round drove it with one user, one
    window and one process, and watched a saved verdict move.

    MUTATION: drop the count from `_run_state_now` and this goes red.
    """
    from datetime import datetime as _dt

    from workflow import measurement_report as _mr
    from workflow.run_compliance import bind_run, is_locked, run_limits

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 1)
    bind_run(run, "chromiq_default", {})
    assert not is_locked(run), "the premise failed: one date does not lock"
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        before = run_limits(run, {}).set_id

        def _asked(self, r):
            # a SECOND measurement finishes while the question is on screen,
            # which is what turns the lock on
            v = run.new_verification(_dt(2026, 2, 2, 10, 0, 0))
            v.ensure_dir()
            raw = v.dir / "P.ti3"
            _write_ti3(raw, _ramp(16) + _colours(), verification=False)
            mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
            return True

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)
        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i)
                     and dlg._set_combo.itemData(i) != before)
        dlg._on_set_chosen(dlg._set_combo.findData(other))

        assert run_limits(run, {}).set_id == before, (
            "the run was rebound after its own second measurement locked it "
            "while the question was on screen")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_the_column_baseline_is_what_we_wrote_not_what_we_read_back(
        qapp, tmp_path, monkeypatch):
    """R17-5: THE RIGHT WIDTH AND THE WRONG MOMENT IS STILL THE WRONG
    BASELINE.

    The column baseline was taken by reading the run back AFTER this window's
    own write. Anything that landed between the write and the read was
    recorded as ours, so another window's column choice was marked seen and no
    collision was raised. Recording what we WROTE closes the gap, because there
    is no gap.

    MUTATION: read the run back for the baseline again and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, set_run_columns,
                                         set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        import ui.dialogs.thresholds_dialog as td
        _real = td.set_run_columns if hasattr(td, "set_run_columns") else None

        class _First(ThresholdsDialog):
            def exec(self):
                import workflow.run_compliance as rc
                _orig = rc.set_run_columns
                done = []

                def _racing(r, cols):
                    _orig(r, cols)
                    if not done:
                        done.append(1)
                        # ANOTHER WINDOW WRITES BETWEEN OUR WRITE AND OUR READ
                        _orig(r, ["chromiq_default"])

                monkeypatch.setattr(rc, "set_run_columns", _racing)
                try:
                    self._column_checks["chromiq_quick"].setChecked(False)
                finally:
                    monkeypatch.setattr(rc, "set_run_columns", _orig)
                self._run_limits["all_de00_avg"] = Limit.value(0.58)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert told and "another window" in "\n".join(told), (
            "a write that landed between this window's own write and its read "
            f"was recorded as this window's: {told}")
    finally:
        dlg.deleteLater()


def test_a_lock_is_enforced_whichever_control_the_user_moved(qapp, tmp_path,
                                                             monkeypatch):
    """R18-2: THE LOCK CHECK WAS GATED ON A CONTROL THAT HAS NOTHING TO DO
    WITH THE LOCK.

    `_run_numbers_moved` sat in that condition, so a verification measurement
    binding and locking the run while the limits window was open was refused
    when the user had typed in the run's own column, and went straight through
    when they had moved the "Default for new runs" radio instead. A challenge
    round drove both on a pre-#182 run with eleven saved reports: the second
    archived and rewrote all eleven and moved six verdicts from PASS to FAIL,
    on a run the app says is locked, judged by a set the user never picked.

    Which control was touched is not the question. The lock is.

    MUTATION: put `_run_numbers_moved` back in that condition and this goes
    red.
    """
    from workflow.run_compliance import ensure_bound, is_locked

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)
        recalculated: list = []
        monkeypatch.setattr(type(dlg), "_recalculate_run",
                            lambda self: recalculated.append(1))

        class _RadioOnly(ThresholdsDialog):
            def exec(self):
                # the user moves ONLY the app-wide default, never the run's
                # own column
                _other = next(c for c, rb in self._default_radios.items()
                              if not rb.isChecked() and rb.isEnabled())
                self._default_radios[_other].setChecked(True)
                # …and a verification measurement binds the run to that new
                # default and locks it, which is the real sequence: the
                # measurement reads the live preference.
                ensure_bound(run, {}, _other)
                from workflow.run_compliance import set_run_unlocked
                set_run_unlocked(run, False)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _RadioOnly)
        dlg._on_open_limits()

        assert is_locked(run), "the premise failed"
        assert not recalculated, (
            "every saved report of a LOCKED run was recalculated, because the "
            "user had moved the radio rather than the run's own column")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_a_preference_change_during_the_question_is_not_reverted_in_silence(
        qapp, tmp_path, monkeypatch):
    """R18-3: THE APP-WIDE STORES WERE READ ONCE, BEFORE THE QUESTION.

    `prefs_collided` is decided inside the limits dialog's `done()`, which is
    over before the recalculate question goes up. Round 17 taught this function
    to look at the RUN again afterwards and left these on the old reading, so
    another window's change to them during the question was reverted by the
    refusal with no box at all. Word for word two earlier findings, one moment
    later.

    MUTATION: drop the second reading and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import bind_run, set_run_unlocked

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        def _asked(self, r):
            # another window changes what every UNBOUND run is judged by,
            # WHILE the question is on screen
            s.set("compliance_default_set", "chromiq_tight")
            return False                      # …and the user refuses

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)

        class _First(ThresholdsDialog):
            def exec(self):
                self._run_limits["all_de00_avg"] = Limit.value(0.46)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        said = "\n".join(told)
        assert "Preferences" in said, (
            "a change made to the app-wide limits while the question was on "
            f"screen was reverted and nobody was told: {told}")
    finally:
        dlg.deleteLater()


def test_a_control_is_not_put_back_to_a_state_the_run_does_not_have(
        qapp, tmp_path, monkeypatch):
    """R18-4: THE TWO REFUSALS ARE NOT THE SAME REFUSAL.

    `_confirm_about_run` returns False when the user says no and when the run
    moved, and the callers put their control back to the value it held before
    the click. That is right in the first case. In the second the guard has
    already redrawn the window from disk, so putting the control back replaces
    the truth with a stale value: a challenge round photographed a pulldown
    naming a set the run is not bound to.

    MUTATION: put the control back on both refusals and this goes red.
    """
    from workflow.run_compliance import (bind_run, run_limits, set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: None)
        before = run_limits(run, {}).set_id
        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i)
                     and dlg._set_combo.itemData(i) != before)

        def _asked(self, r):
            # ANOTHER window binds it to a third thing while the question is up
            bind_run(run, other, {})
            return True

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)
        dlg._on_set_chosen(dlg._set_combo.findData(other))

        on_disk = run_limits(run, {}).set_id
        shown = dlg._set_combo.itemData(dlg._set_combo.currentIndex())
        assert shown == on_disk, (
            f"the pulldown names {shown} and the run is bound to {on_disk}")
    finally:
        dlg.deleteLater()


def test_the_relock_direction_also_checks_the_run_after_its_question(
        qapp, tmp_path, monkeypatch):
    """R18-5: ONE DOOR OF THREE STILL SKIPPED THE GUARD.

    Re-locking is the irreversible direction: it takes the controls away and
    getting them back needs a Preferences setting nothing on this screen names.
    A challenge round drove the gap: the user locks their run onto ANOTHER
    window's looser set, having just been told they could not change it
    afterwards.

    MUTATION: ask with `_confirm_relock` directly again and this goes red.
    """
    from workflow.run_compliance import (bind_run, is_locked, run_limits,
                                         set_run_unlocked)

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        before = run_limits(run, {}).set_id
        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i)
                     and dlg._set_combo.itemData(i) != before)

        def _asked(self, r):
            bind_run(run, other, {})       # another window moves the set
            return True

        monkeypatch.setattr(type(dlg), "_confirm_relock", _asked)
        dlg._on_unlock_toggled(False)

        assert not is_locked(run), (
            "the run was locked onto a set the user was never shown, straight "
            "after being told they could not change it afterwards")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_the_pulldown_binds_with_the_numbers_the_answer_was_given_for(
        qapp, tmp_path, monkeypatch):
    """R19-1: `bind_run` READS THE APP-WIDE OVERRIDES LIVE, AFTER THE ANSWER.

    So another window overriding the chosen set while the question was on
    screen was baked onto the run, and every saved report recalculated against
    numbers nobody in this window ever saw. A challenge round picked the
    loosest set, had another window override it to 0.20 during the question,
    and watched six verdicts go from PASS to FAIL under one box that mentioned
    none of it. The identical write through the "Edit limits…" door has been
    guarded since an earlier round; this one had nothing.

    MUTATION: drop the comparison before `bind_run` and this goes red.
    """
    from core.settings import store_compliance_overrides
    from workflow.run_compliance import bind_run, run_limits, set_run_unlocked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)          # …or the pulldown is not usable at all
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        recalculated: list = []
        monkeypatch.setattr(type(dlg), "_recalculate_run",
                            lambda self: recalculated.append(1))
        before = run_limits(run, {}).set_id
        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i)
                     and dlg._set_combo.itemData(i) != before)

        def _asked(self, r):
            # another window tightens the set the user has just chosen, WHILE
            # the question about it is on screen
            store_compliance_overrides(s, {other: {"all_de00_avg": 0.20}})
            return True

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)
        dlg._on_set_chosen(dlg._set_combo.findData(other))

        assert not recalculated, (
            "every saved report was recalculated against an override written "
            "while the question was on screen")
        assert told and "Preferences" in "\n".join(told), told
    finally:
        dlg.deleteLater()


def test_the_refusal_path_sees_a_write_to_the_run_during_its_question(
        qapp, tmp_path, monkeypatch):
    """R19-3: THE BRANCH READ THE RUN'S STATE AND NEVER COMPARED IT.

    The app-wide comparison was added to this branch and the run's own was left
    behind, four lines apart. So another window's write to the run DURING the
    question was wiped by the undo with no box at all, while the same write one
    moment earlier produced the correct two.

    MUTATION: drop the comparison from the refusal branch and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, run_limits, set_run_limits,
                                         set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    THEIRS = 0.11
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        def _asked(self, r):
            other = dict(run_limits(run, {}).limits)
            other["all_de00_avg"] = Limit.value(THEIRS)
            set_run_limits(run, other)
            return False                      # the user refuses

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)

        class _First(ThresholdsDialog):
            def exec(self):
                self._run_limits["all_de00_avg"] = Limit.value(0.93)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert told and "another window" in "\n".join(told), (
            "another window's write during the question was wiped by the undo "
            f"and nobody was told: {told}")
    finally:
        dlg.deleteLater()


def test_a_column_write_on_a_run_relocked_meanwhile_is_not_kept_in_silence(
        qapp, tmp_path, monkeypatch):
    """R19-4 and the other half of R19-3: THE COLUMN CHOICE IS A WRITE TOO.

    The tick box writes `compliance_columns` the moment it is clicked, and the
    undo puts that key back. It was in neither term of the lock branch's
    trigger and not in the state the guard compares, so a run re-locked while
    the window was open kept that write with no message, and was refused only
    if the user had ALSO typed a number.

    MUTATION: drop `_run_columns_moved` from the trigger, or drop the columns
    key from the run's state, and this goes red.
    """
    from workflow.run_compliance import (bind_run, is_locked, set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    before = list(run.load_meta().compliance_columns or [])
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)
        monkeypatch.setattr(type(dlg), "_confirm_recalculate",
                            lambda self, run: True)

        class _ColumnsOnly(ThresholdsDialog):
            def exec(self):
                # the user touches ONLY the column tick, never a number
                self._column_checks["chromiq_quick"].setChecked(False)
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                set_run_unlocked(run, False)          # …and it is locked again
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _ColumnsOnly)
        dlg._on_open_limits()

        assert is_locked(run), "the premise failed"
        after = list(run.load_meta().compliance_columns or [])
        assert after == before, (
            f"a locked run kept a column write made while it was open: "
            f"{before} -> {after}")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()


def test_another_windows_column_write_during_the_question_is_seen(
        qapp, tmp_path, monkeypatch):
    """THE COLUMNS KEY IN THE RUN'S STATE, proved separately.

    `_run_state_now` is documented as everything this window's decisions about
    the run depend on, and `compliance_columns` was missing from it even though
    it is the one key the undo writes. So another window changing ONLY the
    columns during the question was invisible to the guard.

    Proved necessary by mutation: removing that field from the state broke no
    test until this one existed.

    MUTATION: drop the columns key from `_run_state_now` and this goes red.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (bind_run, set_run_columns,
                                         set_run_unlocked)

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))
        monkeypatch.setattr(type(dlg), "_confirm", lambda self, t, x: True)

        def _asked(self, r):
            # another window changes ONLY which columns this run's report shows
            set_run_columns(run, ["chromiq_default", "chromiq_strict"])
            return False                      # the user refuses

        monkeypatch.setattr(type(dlg), "_confirm_recalculate", _asked)

        class _First(ThresholdsDialog):
            def exec(self):
                self._run_limits["all_de00_avg"] = Limit.value(0.37)
                self._run_dirty = True
                from PyQt6.QtWidgets import QDialog as _Q
                self.done(_Q.DialogCode.Accepted)
                return 0

        import ui.dialogs.thresholds_dialog as td
        monkeypatch.setattr(td, "ThresholdsDialog", _First)
        dlg._on_open_limits()

        assert told and "another window" in "\n".join(told), (
            "another window's column choice was reverted by the undo and "
            f"nobody was told: {told}")
    finally:
        dlg.deleteLater()


def test_the_relock_question_checks_what_it_promised_after_the_answer(
        qapp, tmp_path, monkeypatch):
    """R19-2: THE ANSWER DECIDES WHAT THE USER WAS TOLD, AND IT WAS READ
    BEFORE THE QUESTION.

    `_relocking_would_take_the_controls` prints the one sentence in the app
    naming the Preferences setting that gets the controls back. It was read
    once, before the question. A challenge round flipped that setting during
    the question both ways: turned on, the sentence was printed and was not
    true; turned off, the run was locked, the unlock box went dead, and the
    user was never told it would.

    MUTATION: drop the second reading and this goes red.
    """
    from workflow.run_compliance import bind_run, is_locked, set_run_unlocked

    proj, run, ti3 = _run_with_saved_reports(tmp_path, 2)
    bind_run(run, "chromiq_default", {})
    set_run_unlocked(run, True)
    s = _settings(tmp_path)
    # OFF, so re-locking really would take the controls away and the question
    # carries the sentence naming the setting that gets them back. With it ON
    # no question is asked at all, and none is warranted: the user can untick
    # again whenever they like.
    s.set("compliance_allow_edit_after_measurement", False)
    dlg = _dialog(s, ti3)
    try:
        told: list = []
        import ui.warning_sign as ws
        monkeypatch.setattr(ws, "warn", lambda parent, t, x: told.append(x))

        def _asked(self, r):
            # …and it is switched ON while that question is on screen, so the
            # sentence the user is reading stops being true as they read it
            s.set("compliance_allow_edit_after_measurement", True)
            return True

        monkeypatch.setattr(type(dlg), "_confirm_relock", _asked)
        dlg._on_unlock_toggled(False)

        assert not is_locked(run), (
            "the run was locked under a question that had stopped being true "
            "while the user was reading it")
        assert told, "the user was told nothing"
    finally:
        dlg.deleteLater()
