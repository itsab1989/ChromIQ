"""The limits window never said which set the run was bound to.

Knut, 2026-09-13, on `Report-Limits-Report-Types` run 5::

    The Judged against is set to "ChromIQ tight", but when opening "Edit
    Limits" window the "ChromIQ default" was enabled. Manually clicking any of
    the 5 radio-buttons to select a limit set did nothing (had no effect.) even
    though the Judge against field was open for editing (Unlock this run's
    limits was ON). The radio-buttons should be locked if "Unlock this run's
    limits" is OFF, and set to same value as in the Judge against field. The
    radio-buttons should select the correct Judge against option if any of the
    buttons are selected, and only if "Unlock this run's limits" is ON (or only
    one dated verification run).

**BOTH HALVES OF WHAT HE SAW WERE TRUE, AND NEITHER WAS A BROKEN CONTROL.**
Driven on screen before anything was changed: run 5 really is bound to
`chromiq_tight`, the only radio row on that window really is headed "Default
for new runs", and clicking one really did move `compliance_default_set` and
leave the run alone. Two different questions, one row of radios, and the window
never stated the answer to the one he was looking for.

So the row he expected was added beside the one that was there, rather than
repurposing a specified setting (CH-1 / S-13) that nobody asked to lose. It
writes nothing itself: `MeasurementReportDialog._on_set_chosen` is the single
writer and carries the lock re-check, the preferences-moved check and the
recalculate question, so the choice is recorded and applied through that.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


def _dialog(tmp_path, qapp, *, editable: bool):
    """A limits window on a real run, editable or not."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    ensure_bound(run, None, "chromiq_tight")
    dlg = ThresholdsDialog(s, None, run=run, run_editable=editable)
    dlg.show()
    qapp.processEvents()
    return dlg, run, s


def test_the_row_shows_the_set_the_run_is_bound_to(tmp_path, qapp):
    """MUTATION: build the row without `_run_set_id` and this goes red."""
    dlg, _run, _s = _dialog(tmp_path, qapp, editable=True)
    try:
        radios = dlg._run_set_radios
        assert radios, "the window has no 'Used for this run' row at all"
        checked = [c for c, rb in radios.items() if rb.isChecked()]
        assert checked == ["chromiq_tight"], (
            f"the row shows {checked}, not the set the run is bound to")
    finally:
        dlg.close()


def test_it_is_a_different_row_from_the_default_for_new_runs(tmp_path, qapp):
    """The two questions stay two questions. Repurposing the existing row
    would have deleted CH-1 / S-13 without anyone asking."""
    dlg, _run, s = _dialog(tmp_path, qapp, editable=True)
    try:
        assert dlg._default_radios, "the 'Default for new runs' row is gone"
        assert set(dlg._default_radios) == set(dlg._run_set_radios), (
            "the two rows offer different sets, which is a new way to confuse "
            "the same two questions")
        # They are genuinely different objects with genuinely different state.
        assert all(dlg._default_radios[c] is not dlg._run_set_radios[c]
                   for c in dlg._run_set_radios)
        default_checked = [c for c, rb in dlg._default_radios.items()
                           if rb.isChecked()]
        run_checked = [c for c, rb in dlg._run_set_radios.items()
                       if rb.isChecked()]
        assert default_checked != run_checked, (
            "this fixture cannot tell the two rows apart, so it proves nothing")
    finally:
        dlg.close()


def test_choosing_one_records_the_pick_and_writes_nothing(tmp_path, qapp):
    """The dialog must not rebind a run behind the report window's guards."""
    from workflow.run_compliance import run_limits
    dlg, run, _s = _dialog(tmp_path, qapp, editable=True)
    try:
        before = run_limits(run, {}).set_id
        dlg._run_set_radios["chromiq_quick"].setChecked(True)
        qapp.processEvents()
        assert dlg.run_set_chosen == "chromiq_quick"
        assert run_limits(run, {}).set_id == before, (
            "the limits window rebound the run itself, bypassing the lock "
            "re-check, the preferences check and the recalculate question")
    finally:
        dlg.close()


def test_picking_the_set_it_already_has_records_nothing(tmp_path, qapp):
    """**THIS PASSED FOR THE WRONG REASON ONCE.** It clicked the already-checked
    radio FIRST, where an auto-exclusive no-op happens to give the right
    answer. The real question is what happens after a different pick, which is
    the next test."""
    dlg, _run, _s = _dialog(tmp_path, qapp, editable=True)
    try:
        dlg._run_set_radios["chromiq_tight"].setChecked(True)
        qapp.processEvents()
        assert dlg.run_set_chosen == ""
    finally:
        dlg.close()


def test_changing_your_mind_back_records_nothing(tmp_path, qapp):
    """Pick another set, then put the original back. Nothing is chosen.

    **THE RUN WAS REBOUND TO THE SET THE USER CANCELLED.** With both rows in
    one auto-exclusive group the first click never unchecked the original, so
    clicking it again was a no-op on an already-checked button: the handler did
    not fire, `run_set_chosen` kept the abandoned pick, and the radio the user
    had just pressed went dark. Driven end to end by an adversary round, a run
    on `chromiq_tight` came out on `chromiq_quick` after the user put it back.
    """
    dlg, _run, _s = _dialog(tmp_path, qapp, editable=True)
    try:
        dlg._run_set_radios["chromiq_quick"].setChecked(True)
        qapp.processEvents()
        assert dlg.run_set_chosen == "chromiq_quick"
        dlg._run_set_radios["chromiq_tight"].setChecked(True)
        qapp.processEvents()
        assert dlg.run_set_chosen == "", (
            "putting the original set back left the abandoned pick recorded")
        checked = [c for c, rb in dlg._run_set_radios.items() if rb.isChecked()]
        assert checked == ["chromiq_tight"], (
            f"the row shows {checked}: the radio the user pressed is not the "
            f"one that is filled")
    finally:
        dlg.close()


def test_the_two_rows_are_separate_exclusive_groups(tmp_path, qapp):
    """MUTATION: drop either `QButtonGroup` and this goes red.

    Qt's auto-exclusivity is per PARENT WIDGET and both rows are laid into the
    same header grid, so without their own groups all ten radios were one
    group: picking a set for the run silently unchecked "Default for new runs",
    and one row could show TWO filled buttons at once. Photographed by an
    adversary round on the very window written to stop a radio row being read
    wrong.
    """
    dlg, _run, _s = _dialog(tmp_path, qapp, editable=True)
    try:
        before = [c for c, rb in dlg._default_radios.items() if rb.isChecked()]
        assert before, "no default is shown at all"
        dlg._run_set_radios["chromiq_quick"].setChecked(True)
        qapp.processEvents()
        after = [c for c, rb in dlg._default_radios.items() if rb.isChecked()]
        assert after == before, (
            f"picking a set for the run moved the app-wide default from "
            f"{before} to {after}")
        run_on = [c for c, rb in dlg._run_set_radios.items() if rb.isChecked()]
        assert len(run_on) == 1, f"{len(run_on)} radios filled in one row: {run_on}"
        # …and the other way round.
        dlg._default_radios["chromiq_tight"].setChecked(True)
        qapp.processEvents()
        still = [c for c, rb in dlg._run_set_radios.items() if rb.isChecked()]
        assert still == run_on, (
            f"changing the default moved the run's own row from {run_on} to "
            f"{still}")
    finally:
        dlg.close()


# ------------------------------------------------------------- and locked
def test_a_locked_run_cannot_be_changed_from_here(tmp_path, qapp):
    """*"The radio-buttons should be locked if 'Unlock this run's limits' is
    OFF."* Driven on the shipped pack's own locked run as well."""
    dlg, run, _s = _dialog(tmp_path, qapp, editable=False)
    try:
        radios = dlg._run_set_radios
        assert radios, "no row at all on a locked run"
        assert not any(rb.isEnabled() for rb in radios.values()), (
            "a locked run's set can still be picked")
        # …and it still SHOWS which set the run uses, which is the half of his
        # complaint that has nothing to do with the lock.
        assert [c for c, rb in radios.items() if rb.isChecked()] == ["chromiq_tight"]
    finally:
        dlg.close()


def test_a_click_on_a_locked_run_records_nothing(tmp_path, qapp):
    """`setChecked` from code ignores `setEnabled`, so the handler guards too."""
    dlg, _run, _s = _dialog(tmp_path, qapp, editable=False)
    try:
        dlg._run_set_radios["chromiq_quick"].setChecked(True)
        qapp.processEvents()
        assert dlg.run_set_chosen == "", (
            "a locked run recorded a set change through a disabled control")
    finally:
        dlg.close()


def test_there_is_no_row_when_there_is_no_run(tmp_path, qapp):
    """Opened from Preferences there is no run to bind, so the question does
    not arise and the row must not appear."""
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s, None, run=None, run_editable=False)
    dlg.show()
    qapp.processEvents()
    try:
        assert not dlg._run_set_radios
        assert dlg._default_radios, "the app-wide row belongs here"
    finally:
        dlg.close()


def test_the_report_window_applies_the_pick_through_its_own_door(tmp_path, qapp):
    """Read off the syntax tree: the body RECORDS the pick and the wrapper
    APPLIES it by driving `_set_combo`. Neither may call `bind_run`: every
    guard lives on `_on_set_chosen` and a second caller is a second set of
    guards to keep in step."""
    import ast
    import inspect
    import textwrap
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    body = inspect.getsource(MeasurementReportDialog._open_limits_window)
    wrap = inspect.getsource(MeasurementReportDialog._on_open_limits)
    assert "run_set_chosen" in body, "the body never reads the pick"
    assert "setCurrentIndex" in wrap, (
        "the wrapper does not apply the pick by driving the pulldown")
    for name, src in (("body", body), ("wrapper", wrap)):
        names = {n.func.id for n in ast.walk(ast.parse(textwrap.dedent(src)))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "bind_run" not in names, (
            f"{name} rebinds the run itself, bypassing its own guards")


def test_the_pick_is_applied_outside_the_body_so_it_cannot_double(tmp_path, qapp):
    """**THE FAULT THIS SHAPE EXISTS FOR.** Applying the pick inside the body
    made the body's own "did what this run is judged by change?" snapshot see
    the movement the window had just made, and report it as somebody else's:
    one pick asked the recalculate question TWICE and archived the run's saved
    reports twice. An adversary round drove it with a default-for-new-runs pick
    beside a run pick and counted two archive folders.

    The body has a dozen early returns, so the application has to sit in a
    `finally` outside it to be exactly once on all of them.
    """
    import ast
    import inspect
    import textwrap
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(MeasurementReportDialog._on_open_limits)))
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    assert tries and tries[0].finalbody, (
        "the pick is not applied in a finally, so an early return skips it")
    fin = ast.dump(ast.Module(body=tries[0].finalbody, type_ignores=[]))
    assert "setCurrentIndex" in fin, (
        "the finally does not apply the pick")
    body = inspect.getsource(MeasurementReportDialog._open_limits_window)
    assert "setCurrentIndex" not in body or "_set_combo.setCurrentIndex" not in body, (
        "the body applies the pick as well, so it can happen twice")


def test_the_body_leaves_the_pick_for_the_wrapper(tmp_path, qapp):
    """A behavioural half to go with the two source checks: after the body has
    run, the pick is parked on the window and nothing has been rebound yet."""
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from workflow.run_compliance import run_limits
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    ensure_bound(run, None, "chromiq_tight")
    win = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    win.show()
    qapp.processEvents()
    try:
        # The limits window, driven the way the button drives it.
        td = ThresholdsDialog(s, win, run=run, run_editable=True)
        td._run_set_radios["chromiq_quick"].setChecked(True)
        qapp.processEvents()
        assert td.run_set_chosen == "chromiq_quick"
        assert run_limits(run, {}).set_id == "chromiq_tight", (
            "the limits window rebound the run on its own")
        td.close()
    finally:
        win.close()
