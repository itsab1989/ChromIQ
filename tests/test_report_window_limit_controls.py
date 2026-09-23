"""The Measurement Report window's limit-set controls (#182): the lock, the
strip, the set choice binding the run, the unlock that archives once and
recalculates once, and the multi-run guard.
"""
from __future__ import annotations

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
    rc.bind_run(run, "chromiq_default", {})
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
    from workflow.run_compliance import run_limits, set_run_limits

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


def test_a_measured_run_is_locked_and_the_pulldown_is_disabled(qapp, tmp_path):
    proj, run, ti3s = _verified_run(tmp_path)
    s = _settings(tmp_path)
    dlg = _dialog(s, ti3s[-1])
    try:
        assert dlg._run_ctx is not None and dlg._run_ctx.run.dir == run.dir
        assert not dlg._set_combo.isEnabled()
        assert not dlg._unlock_check.isEnabled()          # Preferences forbids it
        assert dlg._limits_btn.text() == "Show limits…"
        assert "run1" in dlg._judged_label.text()
    finally:
        dlg.deleteLater()


def test_preferences_allows_the_unlock_and_unlocking_recalculates_nothing(
        qapp, tmp_path, monkeypatch):
    """**KNUT OVERTURNED THE SECOND HALF OF THIS TEST, 2026-09-18 (B8-391).**

    It was `…_and_unlocking_archives_and_recalculates`, and it asserted that
    ticking "Unlock this run's limits" archived and rewrote every dated report
    of the run. Reading that very window he wrote: *"All dated reports shall
    NOT be recalculated, only the selected report will be recalculated and
    report text recreated according to new values."*

    So the unlock is now what it says it is and no more: it lets the user
    change the run's limit set and its numbers. The archive-then-recalculate
    rule (D23) is untouched and still governs the door that does rewrite files,
    the Report limits window's Save, which asks its own question at the moment
    the rewrite happens (`test_a_report_stamped_after_the_unlock_is_archived_
    before_its_first_rewrite`).

    MUTATION: put `self._recalculate_run()` back at the foot of
    `_on_unlock_toggled` and this goes red.
    """
    proj, run, ti3s = _verified_run(tmp_path)
    s = _settings(tmp_path, compliance_allow_edit_after_measurement=True)
    dlg = _dialog(s, ti3s[-1])
    try:
        assert dlg._unlock_check.isEnabled()
        # the user says Cancel: nothing changes
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: False)
        dlg._unlock_check.setChecked(True)
        assert not dlg._unlock_check.isChecked()
        assert not run.load_meta().compliance_unlocked
        # the user says OK: the run is unlocked and NOTHING on disk moves
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: True)
        before = {p: p.read_text(encoding="utf-8") for v in run.verifications() for p in mr.list_reports(v.dir)}
        dlg._unlock_check.setChecked(True)
        assert run.load_meta().compliance_unlocked
        for v in run.verifications():
            old = sorted((v.reports_dir / "old").glob("*/report_*.json"))
            assert not old, f"unlocking archived {old}"
            for p in mr.list_reports(v.dir):
                assert p.read_text(encoding="utf-8") == before[p], (
                    f"unlocking rewrote {p.name}")
        # …AND THE QUESTION NO LONGER PROMISES ONE. The clause about every
        # dated report being recalculated went with the behaviour (B8-391);
        # the replacement sentence is §M-PROPOSED and unapproved, so what is
        # left is the words that were already there and are still true.
        _asked: list = []
        monkeypatch.setattr(dlg, "_confirm",
                            lambda t, b: (_asked.append(b), True)[1])
        dlg._unlock_check.setChecked(False)
        dlg._unlock_check.setChecked(True)
        assert _asked, "the unlock stopped asking altogether"
        assert "recalculated" not in _asked[-1], _asked[-1]
        # THE PULLDOWN IS NOW LIVE, AND CHOOSING A SET RE-STAMPS NOTHING
        # (B8-384). Knut: *"Agreed. D23 stands."* — the archive-then-
        # recalculate rule is about HOW a recalculation is done, and his
        # beta-20 ruling is that this door does not start one. It still binds
        # the RUN, which is the yardstick for the dates still to come.
        assert dlg._set_combo.isEnabled()
        held = {p: p.read_text(encoding="utf-8")
                for v in run.verifications() for p in mr.list_reports(v.dir)}
        idx = dlg._set_combo.findData("chromiq_quick")
        dlg._set_combo.setCurrentIndex(idx)
        dlg._on_set_chosen(idx)
        for v in run.verifications():
            live = mr.list_reports(v.dir)
            assert len(live) == 1, "the live file keeps its name"
            assert live[0].read_text(encoding="utf-8") == held[live[0]], (
                "a saved report was rewritten by a change of limit set")
        assert run.load_meta().compliance_set_id == "chromiq_quick"
    finally:
        dlg.deleteLater()


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
        assert "the chart has no grey patches" in html
        assert "at least 20" in html
        assert "Grey balance of the grey ramp, average" in html
    finally:
        dlg.deleteLater()


def test_a_full_chart_shows_no_strip(qapp, tmp_path):
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        assert not dlg._mismatch.isVisibleTo(dlg), dlg._mismatch.text()
    finally:
        dlg.deleteLater()


def test_two_runs_loaded_disable_the_controls(qapp, tmp_path):
    proj, run, ti3s = _verified_run(tmp_path)
    proj2, run2, ti3s2 = _verified_run(tmp_path / "other")
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        dlg._add_source(ti3s2[-1], origin=ti3s2[-1])
        assert len(dlg._distinct_run_dirs()) == 2
        assert not dlg._set_combo.isEnabled()
        assert not dlg._limits_btn.isEnabled()
        assert "more than one place" in dlg._set_combo.toolTip()
    finally:
        dlg.deleteLater()


def test_an_external_file_is_judged_but_nothing_is_written(qapp, tmp_path):
    """CH-14: a measurement in Downloads has no run; the choice is session-only."""
    dl = tmp_path / "Downloads"; dl.mkdir()
    ti3 = _write_ti3(dl / "x.ti3", _ramp(16) + _colours())
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert dlg._run_ctx is None
        assert dlg._set_combo.isEnabled()
        idx = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(idx)
        dlg._on_set_chosen(idx)
        assert dlg._window_limits().set_id == "chromiq_tight"
        assert not (dl / "meta.json").exists()
        assert "not stored" in dlg._set_combo.toolTip()
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
        # …and the fact the denial protected is still stated, positively
        assert ("rather than to that standard's own chart and control strip"
                in plain)
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


def test_a_locked_run_can_always_be_relocked_after_preferences_forbid_edits(
        qapp, tmp_path, monkeypatch):
    """F5: with the Preferences box turned off after an unlock, the ticked box
    must stay enabled so the user can lock the run again.

    **RE-LOCKING NOW ASKS FIRST** (round 9). It used to be silent, and a
    challenge round showed that is the direction that takes every control away:
    one click on a box the app itself ticks when it binds a run, one more dated
    verification, and the run is locked with no route back that anything on
    that screen names. So the question is answered here rather than met by a
    real modal, which is what this test did on the first gate after that change.

    The property F5 exists for is unchanged: re-locking is allowed even with
    the Preferences box off.
    """
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    rc.set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])       # allow flag off
    try:
        assert dlg._unlock_check.isChecked() and dlg._unlock_check.isEnabled()
        # NO QUESTION AT ONE DATE: the lock needs two dated verifications, so
        # putting it back here takes nothing away. It is asked at two, which
        # `test_refusing_the_relock_leaves_the_run_unlocked` below covers.
        monkeypatch.setattr(dlg, "_confirm",
                            lambda t, x: pytest.fail(
                                "a re-lock that takes nothing away asked anyway"))
        dlg._unlock_check.setChecked(False)
        assert not run.load_meta().compliance_unlocked
        assert not dlg._unlock_check.isEnabled()          # and now it is locked for good
    finally:
        dlg.deleteLater()


def test_refusing_the_relock_leaves_the_run_unlocked(qapp, tmp_path, monkeypatch):
    """The other half, and the one that would break silently.

    TWO dated verifications, because that is where re-locking really costs
    something and therefore where the question is asked.
    """
    proj, run, ti3s = _verified_run(tmp_path, dates=2)
    rc.set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        monkeypatch.setattr(dlg, "_confirm", lambda t, x: False)
        dlg._unlock_check.setChecked(False)
        assert run.load_meta().compliance_unlocked, (
            "a refused re-lock locked the run anyway")
        assert dlg._unlock_check.isChecked(), (
            "the box kept the refused state, so it now says the run is locked")
    finally:
        dlg.deleteLater()


def test_a_run_folder_that_cannot_be_written_untick_and_tells(qapp, tmp_path, monkeypatch):
    """F3: the unlock must not claim what the disk refused."""
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    s = _settings(tmp_path, compliance_allow_edit_after_measurement=True)
    dlg = _dialog(s, ti3s[-1])
    told = []
    try:
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: True)
        monkeypatch.setattr(dlg, "_say_not_written", lambda run, exc: told.append(str(exc)))
        import workflow.run_compliance as rcmod

        def boom(run, on):
            raise PermissionError("read-only")
        monkeypatch.setattr(rcmod, "set_run_unlocked", boom)
        dlg._unlock_check.setChecked(True)
        assert not dlg._unlock_check.isChecked()
        assert told and "read-only" in told[0]
        assert not run.load_meta().compliance_unlocked
    finally:
        dlg.deleteLater()


def test_a_date_whose_archive_fails_is_not_rewritten(qapp, tmp_path, monkeypatch):
    """F2: archive first; a report that could not be copied keeps its verdict."""
    proj, run, ti3s = _verified_run(tmp_path, dates=2)
    s = _settings(tmp_path, compliance_allow_edit_after_measurement=True)
    dlg = _dialog(s, ti3s[-1])
    told = []
    try:
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: True)
        from core.file_manager import Verification
        first = run.verifications()[0]
        orig = Verification.archive_reports

        def failing(self, when=None):
            if self.id == first.id:
                raise PermissionError("reports read-only")
            return orig(self, when)
        monkeypatch.setattr(Verification, "archive_reports", failing)
        from ui import warning_sign
        monkeypatch.setattr(warning_sign, "warn", lambda *a, **k: told.append(a[2]))
        before = {p: p.read_text(encoding="utf-8") for v in run.verifications() for p in mr.list_reports(v.dir)}
        dlg._unlock_check.setChecked(True)
        # THROUGH THE LIMITS WINDOW, because the "Judged against" pulldown no
        # longer recalculates anything (B8-384). The property is the same one:
        # archive first, and a date that could not be archived keeps its
        # verdict.
        _edit_the_runs_numbers(dlg, monkeypatch, value=0.2)
        after = {p: p.read_text(encoding="utf-8") for v in run.verifications() for p in mr.list_reports(v.dir)}
        for p in before:
            if str(p).startswith(str(first.dir)):
                assert after[p] == before[p], "a report was rewritten although its archive failed"
            else:
                assert json.loads(after[p])["compliance"]["thresholds"][
                    "all_de00_avg"] == 0.2
        # ACROSS EVERY BOX THIS DOOR RAISED, not only the last one: the date
        # that could not be archived is named in its own.
        assert told and first.id in "\n".join(told), told
    finally:
        dlg.deleteLater()


def test_a_report_stamped_after_the_unlock_is_archived_before_its_first_rewrite(qapp, tmp_path, monkeypatch):
    """F11: every content gets a copy before it changes, and identical content
    is never copied twice (N2)."""
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    s = _settings(tmp_path, compliance_allow_edit_after_measurement=True)
    dlg = _dialog(s, ti3s[-1])
    try:
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: True)
        dlg._unlock_check.setChecked(True)
        v = run.verifications()[0]
        old = lambda: sorted((v.reports_dir / "old").glob("*/report_*.json"))  # noqa: E731
        # NOTHING YET: the unlock itself recalculates nothing and so archives
        # nothing (B8-391). What follows is the door that does both.
        assert not old()
        # a new measurement stamped while unlocked
        from tests.test_report_judging import _colours, _ramp, _write_ti3
        rep = mr.build_report(ti3s[-1])
        mr.stamp_verdict(rep, rc.run_limits(run, {}).limits, set_id="chromiq_default",
                         set_label="ChromIQ default (recommended)")
        rep["created"] = "2026-05-05T05:05:05"
        p2 = v.reports_dir / "report_2026-05-05_05-05-05.json"
        p2.write_text(json.dumps(rep), encoding="utf-8")
        content2 = p2.read_text(encoding="utf-8")
        # THROUGH THE LIMITS WINDOW, for the reason `_edit_the_runs_numbers`
        # gives: the pulldown recalculates nothing any more (B8-384).
        _edit_the_runs_numbers(dlg, monkeypatch, value=0.2)
        copies = old()
        assert any(c.read_text(encoding="utf-8") == content2 for c in copies), \
            "the report stamped after the unlock was rewritten without a copy"
        n_copies = len(copies)
        assert n_copies, "the Save door archived nothing"
        # changing again copies only what changed since
        _edit_the_runs_numbers(dlg, monkeypatch, value=0.3)
        assert len(old()) == n_copies + 2   # both live files changed once more
    finally:
        dlg.deleteLater()


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


def test_the_column_choice_survives_a_refused_limit_change(qapp, tmp_path, monkeypatch):
    """Even when the user DOES change a number and then says no.

    The undo puts the run's numbers back, and used to take the column ticks
    with them. A refusal answers the question that was asked; the ticks were
    never in it.
    """
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    s = _settings(tmp_path, compliance_allow_edit_after_measurement=True)
    dlg = _dialog(s, ti3s[-1])
    try:
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: True)
        dlg._unlock_check.setChecked(True)          # so the column is editable
        before = dict(run.load_meta().compliance_thresholds or {})

        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        asked: "list[str]" = []
        monkeypatch.setattr(
            dlg, "_confirm",
            lambda title, text, *a, **k: (asked.append(title), False)[1])

        def fake_exec(self):
            self._column_checks["iso_12647_7"].setChecked(False)
            self._cells[("__run__", "all_de00_avg")].setValue(7.25)
            self.accept()
            return 1
        monkeypatch.setattr(ThresholdsDialog, "exec", fake_exec)
        dlg._on_open_limits()

        assert asked, "a refused NUMBER change must still be asked about"
        m = run.load_meta()
        assert m.compliance_thresholds == before, "the refused number stayed"
        # NOT "iso_12647_7 is absent", WHICH AN EMPTY LIST ALSO SATISFIES.
        # The snapshot taken when the window opened is the empty list, meaning
        # "show every column", so restoring it passes a test that only asks
        # whether the hidden id is missing. A mutation that put the undo back
        # went straight through it. The list has to be the CHOICE.
        stored = list(m.compliance_columns or [])
        assert stored, "the refusal wiped the column choice back to empty"
        assert "iso_12647_7" not in stored, \
            "the refusal took the column choice with it"
        assert "chromiq_default" in stored
    finally:
        dlg.deleteLater()


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


def test_the_report_explains_bound_and_locked(qapp, tmp_path):
    """*"what is the difference between bound and locked? Be specific in the
    explanation"*. §5 of the design record, in his terms."""
    import html as _html
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        plain = _html.unescape(dlg._report_body_html(dlg._runs_for_report(),
                                                     for_pdf=True))
        assert "Bound, and locked." in plain
        # bound: the copy is taken at the FIRST dated verification and is the
        # run's own from then on
        assert "first dated verification" in plain
        # K18 (the final round): the Preferences clause told a ChromIQ user
        # how the app behaves; what the reader keeps is what binding MEANS.
        assert "judged against the same numbers" in plain
        # locked: it starts at the SECOND one, and it is about comparability
        assert "locked once a second dated verification has been measured" in plain
    finally:
        dlg.deleteLater()


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
        assert "not stored" in tip, (
            f"the controls no longer say the choice is unstored: {tip!r}")
        assert "not in a ChromIQ project" not in tip, (
            f"the window tells the user their calibration is outside the "
            f"project it is sitting in: {tip!r}")
        assert "does not belong to a profile run" in tip, tip
    finally:
        dlg.deleteLater()


def test_a_file_outside_any_project_is_still_told_so(qapp, tmp_path):
    """The control: the sentence is right where it was written to be right.

    A measurement in Downloads really is in no ChromIQ project, and that is
    what the tooltip says there. Without this, "fix the sentence" could mean
    "say the weaker thing everywhere", which loses what a reader needs.
    """
    dl = tmp_path / "Downloads"; dl.mkdir()
    ti3 = _write_ti3(dl / "x.ti3", _ramp(16) + _colours())
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert dlg._run_ctx is None
        tip = dlg._set_combo.toolTip()
        assert "not in a ChromIQ project" in tip, tip
    finally:
        dlg.deleteLater()


def test_the_unlock_box_is_dead_while_there_is_nothing_to_unlock(qapp, tmp_path):
    """One dated verification locks nothing, so the box must not offer to lift it.

    Knut, on beta 32: with ONE dated verification the Judged against box is
    already editable and Edit Limits already enabled, *"However, the checkbox
    'Unlock this run's limits' is still clickable"*, and pressing it asked
    whether to unlock something that is not locked.

    `is_locked` has answered `measured_dates(run) < 2 -> not locked` since his
    ruling of 2026-09-10, that *"when only one measurement is done, I should be
    allowed to choose the type of report I want to print, and which limits to
    judge against"*. The enable rule asked `has_measured_verification`, which
    is true of ONE, so the box was live in exactly the state the window's own
    tooltip describes.

    **AND BECAUSE AN ENABLED BOX RETURNS NO REASON, THAT SENTENCE HAD NEVER
    BEEN SHOWN TO ANYBODY.** It was written, translated into thirteen
    languages, and unreachable. That is why this test asserts the tooltip as
    well as the state: a dim control has to say why.

    MUTATION: put `has_measured_verification(run)` back in place of `locked` in
    `_sync_limit_controls` and both assertions go red.
    """
    _proj, _run, ti3s = _verified_run(tmp_path, dates=1)
    s = _settings(tmp_path)
    s.set("compliance_allow_edit_after_measurement", True)
    dlg = _dialog(s, ti3s[-1])
    try:
        assert dlg._set_combo.isEnabled(), (
            "with one dated verification the set is still the user's to "
            "choose, which is the ruling this test depends on"
        )
        assert not dlg._unlock_check.isEnabled(), (
            "the unlock box is live with one dated verification, where "
            "nothing is locked, so pressing it asks to lift a lock that is "
            "not there"
        )
        assert "not locked yet" in dlg._unlock_check.toolTip(), (
            f"a dim box has to say why; it says {dlg._unlock_check.toolTip()!r}"
        )
    finally:
        dlg.deleteLater()
