"""The Measurement Report window's limit-set controls (#182): the strip, the
report's own set, and (since K31, beta 40) no lock, no binding and no unlock:
Knut, 5801677743, *"the limit set belongs to the report"*.
"""
from __future__ import annotations

from tests.helpers import legacy_run_meta
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402
from workflow import run_compliance as rc                 # noqa: E402
from workflow.ti3_analysis import mark_verification_ti3   # noqa: E402

from tests.test_report_judging import _colours, _ramp, _write_ti3  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path, **kw) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in kw.items():
        s.set(k, v)
    return s


def _verified_run(tmp_path, dates=2, patches=None):
    """A project whose run has *dates* measured verifications with saved reports."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    # BIND IT, because the app does. `ensure_bound` runs at the first
    # verification measurement (ui/tabs/tab_measure.py), and a fixture that
    # skips it produces a run with measured dates and no limit set copied onto
    # it, which is the pre-#182 shape rather than a run this build made. The
    # lock now asks whether a run is bound, so the difference matters.
    legacy_run_meta.bind_run(run, "chromiq_default", {})
    from datetime import datetime, timedelta
    ti3s = []
    for i in range(dates):
        v = run.new_verification(datetime(2026, 1, 1, 10, 0, 0) + timedelta(days=30 * i))
        v.ensure_dir()
        raw = v.dir / "P.ti3"
        # the verification file must carry the verify stem the run expects
        target = v.dir / f"{run.verify_stem}.ti3"
        _write_ti3(raw, patches or (_ramp(16) + _colours()), verification=False)
        p = mark_verification_ti3(raw)
        p.rename(target)
        ti3s.append(target)
        rep = mr.build_report(target)
        mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                         set_id="chromiq_default", set_label="ChromIQ default (recommended)")
        mr.save_report(rep, v.dir)
    return proj, run, ti3s


def _dialog(s, ti3):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(s, None, initial_ti3=ti3)


def _edit_the_runs_numbers(dlg, monkeypatch, value=0.2, row="all_de00_avg"):
    """Drive the Report limits window: edit ONE of the run's own numbers and
    close, which is a recalculation of the run (§5, D23).

    **THE DOOR MOVED, AND THAT IS B8-384.** These properties belong to
    `_recalculate_run`, and the tests below used to reach it through the
    "Judged against" pulldown because that was the shortest way in. That
    pulldown no longer recalculates anything: Knut ruled that changing it may
    not rewrite a saved report. Two doors still do, and this is the one that
    can be driven twice in a row with a different answer each time.

    The real `ThresholdsDialog` writes the edited column in `done()` whatever
    result it closes with, so the fake does the same thing through the same
    function.
    """
    from workflow.compliance_sets import Limit
    from workflow.run_compliance import (run_limits)
    from tests.helpers.legacy_run_meta import (set_run_limits)

    class _Fake:
        #: WHAT THE DOOR READS OFF THE DIALOG, spelled out rather than
        #: answered by a catch-all `__getattr__`: a lambda is truthy, so a
        #: catch-all made the window believe the Preferences had been edited
        #: too and left a warning box open on the suite.
        run_limits_changed = True

        def __init__(self, settings, parent, run=None, run_editable=False):
            self._run, self._editable = run, run_editable

        def exec(self):
            if self._run is not None and self._editable:
                lim = dict(run_limits(self._run, {}).limits)
                lim[row] = Limit.value(value)
                set_run_limits(self._run, lim)
            return 0

        def deleteLater(self):
            pass

    import ui.dialogs.thresholds_dialog as td
    monkeypatch.setattr(td, "ThresholdsDialog", _Fake)
    dlg._on_open_limits()


def test_a_measured_run_is_not_locked(qapp, tmp_path):
    """K31 turned this test round: it was
    `test_a_measured_run_is_locked_and_the_pulldown_is_disabled`. A run with
    two dated verifications, bound by an earlier ChromIQ, keeps every limit
    control live, the button reads "Edit limits…", and there is no unlock
    control at all (Knut, 5801677743: *"I agree that the 'Unlock this run's
    limits' is no longer needed"*).

    MUTATION: grey the pulldown on a bound run with two dates in
    `_sync_limit_controls` (the old lock), or build the unlock box again, and
    this goes red."""
    proj, run, ti3s = _verified_run(tmp_path)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3s[-1])
    try:
        assert dlg._run_ctx is not None and dlg._run_ctx.run.dir == run.dir
        assert dlg._set_combo.isEnabled()
        assert dlg._limits_btn.isEnabled()
        assert dlg._limits_btn.text() == "Edit limits…"
        assert not hasattr(dlg, "_unlock_check")
        from PyQt6.QtWidgets import QCheckBox
        assert not any("Unlock" in c.text()
                       for c in dlg.findChildren(QCheckBox))
        # B8-946: the set is the report's, so its label names no run.
        assert dlg._judged_label.text() == "Judged against:"
    finally:
        dlg.deleteLater()


# RETIRED BY K31 (beta 40): `test_preferences_allows_the_unlock_and_unlocking_recalculates_nothing`.
# Unlock this run's limits and the Preferences option that allowed it are
# removed (Knut, 5801677743); nothing is locked, so there is nothing to allow
# or unlock.


def test_the_strip_names_what_the_chart_cannot_supply(qapp, tmp_path):
    """CH-10/D25: a chart with 12 patches and no grey ramp."""
    proj, run, ti3s = _verified_run(tmp_path, dates=1, patches=_colours(12))
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        assert dlg._mismatch.isVisibleTo(dlg)
        # one line on screen (elided to the window), the whole message as tooltip
        assert "cannot be checked" in dlg._mismatch.text()
        assert "grey" in dlg._mismatch.text().lower()
        full = dlg._mismatch.toolTip()
        assert "grey" in full.lower() and "at least 20" in full
        assert "Neutral grey ramp" in full            # what to add to the chart
        # …AND THE REPORT TEXT REPEATS IT, which since 2026-09-21 it does
        # through the numbered notes rather than a "Not computed on this
        # chart" block: Knut ruled that an N-A cell carries a raised number
        # pointing at a note that says why. The claim is the same one, so
        # this asks for the same fact in the place the ruling put it.
        html = dlg._report_results_html(dlg._runs_for_report())
        assert "Notes on the verdicts above" in html
        # the same two facts the strip carries, each numbered and pointed at
        # by the cell it explains, and the two grey rows sharing one number
        assert "the measured chart has no grey patches" in html   # K22
        assert "at least 20" in html
        assert "Average ΔCh, grey balance of the grey ramp" in html
    finally:
        dlg.deleteLater()


def test_a_full_chart_shows_no_strip(qapp, tmp_path):
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        assert not dlg._mismatch.isVisibleTo(dlg), dlg._mismatch.text()
    finally:
        dlg.deleteLater()


def test_two_runs_loaded_the_pulldown_chooses_the_reports_set(qapp, tmp_path):
    """G7 (#182 beta 39). With two profile runs loaded, "Judged against"
    chooses the REPORT's own set (Knut, 5794311113: *"the report's own limit
    set applies to every included measurement, whatever each run is bound
    to"*) and binds no run. (K31 removed "Unlock this run's limits".)

    Before G7 this test asserted all three greyed. SINCE K30 (Knut,
    5798461562: *"all settings belong to a report, not a specific run"*)
    the limits button is LIVE and reads "Edit limits…": it edits the
    report's own limits (`tests/test_k30_rulings.py`).

    MUTATION, proven red: drop the `if self._several_runs():` early return in
    `_on_set_chosen` (the window's run is re-bound to the chosen set)."""
    from workflow.run_compliance import run_limits
    proj, run, ti3s = _verified_run(tmp_path)
    proj2, run2, ti3s2 = _verified_run(tmp_path / "other")
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        dlg._add_source(ti3s2[-1], origin=ti3s2[-1])
        assert len(dlg._distinct_run_dirs()) == 2
        assert dlg._set_combo.isEnabled()
        assert dlg._limits_btn.isEnabled()
        assert dlg._limits_btn.text() == "Edit limits…"
        assert "whichever profile run or project" in dlg._set_combo.toolTip()
        assert "This report" in dlg._limits_btn.toolTip()
        before = (run_limits(run, None).set_id, run_limits(run2, None).set_id)
        other = next(dlg._set_combo.itemData(i)
                     for i in range(dlg._set_combo.count())
                     if dlg._set_combo.itemData(i) not in before)
        idx = dlg._set_combo.findData(other)
        dlg._set_combo.setCurrentIndex(idx)
        qapp.processEvents()
        assert dlg._set_combo.currentData() == other
        after = (run_limits(run, None).set_id, run_limits(run2, None).set_id)
        assert after == before, "choosing the report's set bound a run"
    finally:
        dlg.deleteLater()


def test_an_external_file_is_judged_but_nothing_is_written(qapp, tmp_path):
    """CH-14: a measurement in Downloads has no run; the choice is the
    report's, for the session, and nothing is written (K31: nothing is written
    for any measurement until Generate report)."""
    dl = tmp_path / "Downloads"; dl.mkdir()
    ti3 = _write_ti3(dl / "x.ti3", _ramp(16) + _colours())
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert dlg._run_ctx is None
        # KNUT, #182 5816794672: with Generate greyed (a file in no project
        # has no run to save into) the settings are greyed with it; the
        # choice below is still the report's alone, and writes nothing.
        assert not dlg._generate_btn.isEnabled()
        assert not dlg._set_combo.isEnabled()
        idx = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(idx)
        dlg._on_set_chosen(idx)
        assert dlg._report_limits().set_id == "chromiq_tight"
        assert not (dl / "meta.json").exists()
    finally:
        dlg.deleteLater()


def test_the_words_reach_the_grid_and_the_pdf_body(qapp, tmp_path):
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        runs = dlg._runs_for_report()
        grid = dlg._report_results_html(runs)
        assert "PASS" in grid and "Overall" in grid and "Judged against" in grid
        assert "ChromIQ default" in grid
        body = dlg._report_body_html(runs, for_pdf=True)
        assert "The five verdict words" in body
        # THE WORD IS GONE ALTOGETHER NOW, denial included. Knut, 2026-09-11,
        # struck the sentence that carried it: *"It is not needed to say 'this
        # report never says that anything conforms to a standard', which
        # actually has the opposite effect of building confidence in the report
        # results."* The promise made to Idealliance is that the CLAIM is never
        # printed, so zero occurrences keeps it more plainly than one did.
        import html as _html
        plain = _html.unescape(body)
        assert plain.count("conforms") == 0
        # …and the fact the denial protected is stated where it applies: in
        # a report judged against a standard's set. This one is judged
        # against ChromIQ default, so it does not carry that paragraph, and
        # does not point at a note it does not have (R2 of beta 39, #2).
        assert ("rather than to that standard's own chart and control strip"
                not in plain)
        # W5: one bullet per word, not one paragraph carrying all five
        for word in ("PASS:", "FAIL:", "COND (short for conditional):",
                     "INFO:", "N-A (not applicable):"):
            assert f"<li>{_html.escape(word)}" in body or f"<li>{word}" in body, word
    finally:
        dlg.deleteLater()


def test_the_confirmation_answers_yes_when_ok_is_really_clicked(qapp, tmp_path):
    """Found on screen 2026-09-08: `QMessageBox.exec()` returns an int and a
    PyQt6 enum member never equals an int, so `exec() == StandardButton.Ok`
    was always False and nobody could unlock a run. This test clicks the real
    button from a timer instead of stubbing the method."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMessageBox
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        answers = []

        def press(which):
            box = QApplication.activeModalWidget()
            assert isinstance(box, QMessageBox), type(box)
            box.button(which).click()

        QTimer.singleShot(150, lambda: press(QMessageBox.StandardButton.Ok))
        answers.append(dlg._confirm("t", "ok?"))
        QTimer.singleShot(150, lambda: press(QMessageBox.StandardButton.Cancel))
        answers.append(dlg._confirm("t", "cancel?"))
        assert answers == [True, False]
    finally:
        dlg.deleteLater()


# RETIRED BY K31 (beta 40): `test_a_locked_run_can_always_be_relocked_after_preferences_forbid_edits`.
# The relock direction went with the lock (K31).


# RETIRED BY K31 (beta 40): `test_refusing_the_relock_leaves_the_run_unlocked`.
# The relock question went with the lock (K31).


# RETIRED BY K31 (beta 40): `test_a_run_folder_that_cannot_be_written_untick_and_tells`.
# The unlock box is gone (K31); the only run write left in the window, the
# run's own default for new reports, reports an unwritable folder through the
# same _say_not_written (tests/test_k31_report_model.py).


# RETIRED BY K31 (beta 40): `test_a_date_whose_archive_fails_is_not_rewritten`.
# The recalculation of a run's dated reports (_recalculate_run) is removed
# with the run's limits (K31): no report is ever rewritten by a limit change,
# so there is no archive-then-rewrite to guard.


# RETIRED BY K31 (beta 40): `test_a_report_stamped_after_the_unlock_is_archived_before_its_first_rewrite`.
# As above: no unlock and no recalculation since K31.


# ---------------------------------------------------------------------------
# Knut, 2026-09-11: hiding a table column is not a change to the limits
# ---------------------------------------------------------------------------
# Two reports, one mechanism. *"When unchecking the table columns that I do not
# want to show (the 'Show' row), and click close, and then open the Show limits
# window again, it is not remembered what I turned off some columns."* And, on
# a run with one dated verification: *"This should only come when thresholds are
# changed, not if table columns are hidden or shown."*
#
# Driven in a real window on 2026-09-11 before the fix: unticking the two ISO
# columns and clicking Close raised "This run (run1) has one saved report.
# Changing the limit set recalculates it with the new numbers…", and answering
# Cancel, which is the only sensible answer to a question about a limit set
# nobody touched, put `compliance_columns` back to empty. Both of his reports,
# from one term folded into `moved`.

def _hide_two_columns(dlg, run, monkeypatch, answer=True, sets=("iso_12647_7",
                                                               "iso_12647_8")):
    """Open the limits window from the report window, untick *sets*, Close.

    Returns the list of confirmation titles the route raised.
    """
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    asked: "list[str]" = []
    monkeypatch.setattr(dlg, "_confirm",
                        lambda title, text, *a, **k: (asked.append(title), answer)[1])

    def fake_exec(self):
        for sid in sets:
            self._column_checks[sid].setChecked(False)
        self.accept()
        return 1
    monkeypatch.setattr(ThresholdsDialog, "exec", fake_exec)
    dlg._on_open_limits()
    return asked


def test_hiding_a_column_asks_nothing_and_is_remembered(qapp, tmp_path, monkeypatch):
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    assert sum(1 for v in run.verifications() for _ in mr.list_reports(v.dir)) == 1
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        asked = _hide_two_columns(dlg, run, monkeypatch)
        assert asked == [], (
            "hiding a table column raised a confirmation about the limit set: "
            + "; ".join(asked))
        stored = list(run.load_meta().compliance_columns or [])
        assert "iso_12647_7" not in stored and "iso_12647_8" not in stored
        assert "chromiq_default" in stored
    finally:
        dlg.deleteLater()


# RETIRED BY K31 (beta 40): `test_the_column_choice_survives_a_refused_limit_change`.
# No limit change is refused any more (no question, no undo, K31). The column
# choice stays a view setting remembered per run: tests/test_k31_report_model
# .py::test_the_column_choice_is_remembered_and_binds_nothing.


def test_hiding_a_column_never_binds_an_unbound_run(qapp, tmp_path, monkeypatch):
    """The other half of the same fault, on the door with no question in it.

    With no saved report there is nothing to ask about, so the old code went
    straight on to bind the run and recalculate. A view setting must not decide
    which numbers a run is judged by for the rest of its life.
    """
    from core.file_manager import Project
    proj = Project.create(tmp_path / "U", "U")
    run = proj.current_run(); run.ensure_dir()
    assert not rc.is_bound(run)
    v = run.new_verification()
    v.ensure_dir()
    raw = v.dir / "U.ti3"
    target = v.dir / f"{run.verify_stem}.ti3"
    _write_ti3(raw, _ramp(16) + _colours(), verification=False)
    mark_verification_ti3(raw).rename(target)

    dlg = _dialog(_settings(tmp_path), target)
    try:
        asked = _hide_two_columns(dlg, run, monkeypatch)
        assert asked == []
        assert not rc.is_bound(run), \
            "hiding a table column bound the run to a limit set"
        assert "iso_12647_7" not in list(run.load_meta().compliance_columns or [])
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Knut, 2026-09-11, on the report's own words
# ---------------------------------------------------------------------------

def test_the_scope_section_has_air_under_the_run_description(qapp, tmp_path):
    """*"add a new line as empty space before the text 'The following profile
    verification runs are included:'"*.

    The description is a heading for the section and was four pixels above the
    sentence, so the two read as one paragraph. The gap is the report's own
    empty line, the one used under every section heading.
    """
    from ui.dialogs.measurement_report_dialog import _gap
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    m = run.load_meta()
    m.description = "A described run"
    run.save_meta(m)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        html = dlg._scope_html(dlg._runs_for_report())
        assert "A described run" in html
        head, _, tail = html.partition("A described run")
        intro = "The following profile"
        assert intro in tail
        between = tail[:tail.index(intro)]
        assert _gap() in between, (
            "no empty line between the run's description and the line naming "
            "the runs; they read as one paragraph")
    finally:
        dlg.deleteLater()


def test_the_help_says_the_report_owns_its_limits_and_nothing_locks(
        qapp, tmp_path):
    """K31 turned this test round. It was
    `test_bound_and_locked_is_explained_in_the_help_not_the_report` (K26: the
    "Bound, and locked" paragraph moved out of the report into the help).
    Since K31 nothing is bound or locked, so no help and no report may say it
    is, and the "Judged against" help and the glossary say what is true now:
    the limit set belongs to the report (Knut, 5801677743, and his
    5801750910: *"Make sure all the changes in functionality is described in
    help icons and relevant help cards"*).

    MUTATION: put `_bound_and_locked_help()` back into the "Judged against"
    help, or the glossary's "Bound (a run's limits)" or "Locked / Unlock this
    run's limits" entries back, and this goes red."""
    import html as _html
    from PyQt6.QtWidgets import QToolButton
    from ui.dialogs.welcome_dialog import GLOSSARY
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        plain = _html.unescape(dlg._report_body_html(dlg._runs_for_report(),
                                                     for_pdf=True))
        assert "Bound, and locked." not in plain
        assert "locked once a second dated verification" not in plain
        helps = []
        for b in dlg.findChildren(QToolButton):
            v = getattr(b, "_body", None)
            if isinstance(v, str):
                helps.append(v)
        assert helps, "no help button found to read"
        for h in helps:
            assert "Bound, and locked." not in h
            assert "Unlock this run's limits" not in h, h[:200]
        judged = [h for h in helps if "The limit set belongs to the report" in h]
        assert judged, "the Judged against help does not say the report owns its set"
    finally:
        dlg.deleteLater()
    words = dict(GLOSSARY)
    assert not any(k.startswith("Bound") for k in words), words.keys()
    assert not any(k.startswith("Locked") for k in words), words.keys()
    assert "A report's limit set" in words


def test_both_limits_doors_are_the_same_window():
    """Knut's custom-column ruling *"applies also to the report limits window in
    Preferences ▸ Reports tab"*, and it does, because there is only one window.

    Pinned rather than assumed: two implementations of one table is this
    project's most repeated fault shape, and the placeholder values live below
    both doors in `factory_limits`. Driven in two real windows on 2026-09-11,
    the two tables agreed cell for cell.
    """
    import inspect
    import ui.dialogs.measurement_report_dialog as report_win
    import ui.dialogs.settings_dialog as prefs
    for mod in (report_win, prefs):
        src = inspect.getsource(mod)
        assert "from ui.dialogs.thresholds_dialog import" in src \
            and "ThresholdsDialog(" in src, mod.__name__
        assert "_build_rows" not in src, (
            f"{mod.__name__} looks like it grew its own limits table; there "
            "must be exactly one, or Knut's ruling reaches only one door")
    # …and the numbers both doors draw come from one function, below both
    from workflow.compliance_sets import factory_limits
    f = factory_limits("custom_iso_12647_7")
    assert f["all_de00_avg"].is_numeric


# ---------------------------------------------------------------------------
# R24-F6 — what the controls say about a measurement that has no run
# ---------------------------------------------------------------------------
def test_a_calibration_is_not_told_it_is_outside_the_project(qapp, tmp_path):
    """R24-F6. A false sentence, in shipped text, about the user's own file.

    With Run type = Calibration the limit controls carried the tooltip *"This
    measurement is not in a ChromIQ project, so the choice is not stored
    anywhere."* The measurement is at ``<project>/cal/<name>-cal.ti3``, which
    is where `calibration_run_type.md` puts a calibration: inside the project,
    in the folder the project gives it.

    `run_context_for` answers None for anything that is not ``runs/runN/…``,
    and that None was read as "not in a project". The half that is true, and
    the reason the controls say anything at all, is the second one: there is
    no run for the choice to be stored on.

    MUTATION, proved to land: read the old sentence for both branches again.
    """
    proj = Project.create(tmp_path / "P", "P")
    cal = proj.calibration
    cal.ensure_dir()
    ti3 = _write_ti3(cal.ti3, _ramp(16) + _colours())
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert dlg._run_ctx is None, (
            "the calibration resolved to a RUN, so this is not the state the "
            "sentence is shown in")
        tip = dlg._set_combo.toolTip()
        assert "not in a ChromIQ project" not in tip, (
            f"the window tells the user their calibration is outside the "
            f"project it is sitting in: {tip!r}")
        assert tip, "the limit set pulldown says nothing about itself"
    finally:
        dlg.deleteLater()


# RETIRED BY K31 (beta 40): `test_a_file_outside_any_project_is_still_told_so`.
# The sentence it kept ('not in a ChromIQ project, so the choice is not
# stored anywhere') described the run binding; since K31 no choice of limits
# is stored anywhere until Generate report, for any measurement, so the
# sentence is gone. Generate report still says why it is greyed for such a
# file.


# RETIRED BY K31 (beta 40): `test_the_unlock_box_is_dead_while_there_is_nothing_to_unlock`.
# The unlock box is gone (K31).
