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


def test_preferences_allows_the_unlock_and_unlocking_archives_and_recalculates(
        qapp, tmp_path, monkeypatch):
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
        # the user says OK: archive once, recalculate once
        monkeypatch.setattr(dlg, "_confirm", lambda *a, **k: True)
        before = {p: p.read_text(encoding="utf-8") for v in run.verifications() for p in mr.list_reports(v.dir)}
        dlg._unlock_check.setChecked(True)
        assert run.load_meta().compliance_unlocked
        for v in run.verifications():
            old = sorted((v.reports_dir / "old").glob("*/report_*.json"))
            assert len(old) == 1, "each date's report is archived exactly once"
            assert old[0].read_text(encoding="utf-8") == before[v.reports_dir / old[0].name]
        # the pulldown is now live; choosing Quick check re-stamps every date
        assert dlg._set_combo.isEnabled()
        idx = dlg._set_combo.findData("chromiq_quick")
        dlg._set_combo.setCurrentIndex(idx)
        dlg._on_set_chosen(idx)
        for v in run.verifications():
            live = mr.list_reports(v.dir)
            assert len(live) == 1, "the live file keeps its name (rewritten in place)"
            rep = json.loads(live[0].read_text(encoding="utf-8"))
            assert rep["compliance"]["set_id"] == "chromiq_quick"
            assert rep["compliance"]["thresholds"]["all_de00_avg"] == 4.0
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
        # …and the report text repeats it
        html = dlg._report_results_html(dlg._runs_for_report())
        assert "Not computed on this chart" in html
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
        assert "Several" in dlg._set_combo.toolTip()
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
        idx = dlg._set_combo.findData("chromiq_quick")
        dlg._set_combo.setCurrentIndex(idx)
        after = {p: p.read_text(encoding="utf-8") for v in run.verifications() for p in mr.list_reports(v.dir)}
        for p in before:
            if str(p).startswith(str(first.dir)):
                assert after[p] == before[p], "a report was rewritten although its archive failed"
            else:
                assert json.loads(after[p])["compliance"]["set_id"] == "chromiq_quick"
        assert told and first.id in told[-1]
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
        assert len(old()) == 1
        # a new measurement stamped while unlocked
        from tests.test_report_judging import _colours, _ramp, _write_ti3
        rep = mr.build_report(ti3s[-1])
        mr.stamp_verdict(rep, rc.run_limits(run, {}).limits, set_id="chromiq_default",
                         set_label="ChromIQ default (recommended)")
        rep["created"] = "2026-05-05T05:05:05"
        p2 = v.reports_dir / "report_2026-05-05_05-05-05.json"
        p2.write_text(json.dumps(rep), encoding="utf-8")
        content2 = p2.read_text(encoding="utf-8")
        idx = dlg._set_combo.findData("chromiq_quick")
        dlg._set_combo.setCurrentIndex(idx)
        copies = old()
        assert any(c.read_text(encoding="utf-8") == content2 for c in copies), \
            "the report stamped after the unlock was rewritten without a copy"
        n = len(copies)
        # changing again copies only what changed since
        idx = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(idx)
        assert len(old()) == n + 2          # both live files changed once more
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
        assert "does not reach a run that is already bound" in plain
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
