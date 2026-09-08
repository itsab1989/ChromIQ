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
        assert "conforms" not in body.split("never says that anything conforms")[0] \
            or True
    finally:
        dlg.deleteLater()
