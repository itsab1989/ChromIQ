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
        # "conforms" appears exactly once, inside the sentence that denies it
        import html as _html
        plain = _html.unescape(body)
        assert plain.count("conforms") == 1
        assert "never says that anything conforms" in plain
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


def test_a_locked_run_can_always_be_relocked_after_preferences_forbid_edits(qapp, tmp_path):
    """F5: with the Preferences box turned off after an unlock, the ticked box
    must stay enabled so the user can lock the run again."""
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    rc.set_run_unlocked(run, True)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])       # allow flag off
    try:
        assert dlg._unlock_check.isChecked() and dlg._unlock_check.isEnabled()
        dlg._unlock_check.setChecked(False)
        assert not run.load_meta().compliance_unlocked
        assert not dlg._unlock_check.isEnabled()          # and now it is locked for good
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
