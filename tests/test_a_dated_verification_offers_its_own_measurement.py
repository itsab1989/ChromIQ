"""Knut, #182 5951427228 (4.3.3-beta.2), both halves of one report.

1. Selecting a dated verification that HAS a measurement showed neither
   "Refine / resume" nor "Show overlay": every date shares the one verification
   chart, and the tab only ever looked for a ``.ti3`` beside that chart, while a
   verification's readings live in its dated folder.
2. Switching Run type from Verification to Profiling popped "This chart has not
   been measured yet" about the verification he was leaving. The tick came from
   the profiling run's stored settings, put on screen before its chart arrived,
   and the overlay handler judged the chart still loaded.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox     # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_measure import TabMeasure                # noqa: E402

TI3 = """CTI3
KEYWORD "CHROMIQ_VERIFICATION"
CHROMIQ_VERIFICATION "true"
NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y
END_DATA_FORMAT
NUMBER_OF_SETS 1
BEGIN_DATA
1 A1 100.0 100.0 100.0 90.0 93.0
END_DATA
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def popups(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: seen.append(self.text()) or 0)
    # The existing-measurement window is its own QDialog; record its offers.
    monkeypatch.setattr(TabMeasure, "_maybe_offer_existing_overlay",
                        lambda self: seen.append("OFFER")
                        if self._existing_ti3_for_chart() else None)
    return seen


def _pump(n: int = 5) -> None:
    for _ in range(n):
        QApplication.processEvents()


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("chartread_engine", "chromiq")
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    run.chart_ti2.write_text("TI2", encoding="utf-8")
    run.measurement_ti3.write_text(TI3, encoding="utf-8")   # profiling: measured
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("TI2-v", encoding="utf-8")
    measured = run.verification("2026-10-01_184318")
    measured.ensure_dir()
    measured.measurement_ti3.write_text(TI3, encoding="utf-8")
    empty = run.verification("2026-10-02_121755")
    empty.ensure_dir()                                       # no measurement
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run(run.id)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    tab.set_ti1_path(run.verify_chart_ti2)
    _pump()
    return run, ctl, tab, measured, empty


def _offered(tab) -> tuple[bool, bool]:
    return (not tab._resume_cb.isHidden(), not tab._overlay_cb.isHidden())


def test_a_measured_date_offers_resume_and_overlay(qapp, tmp_path, popups):
    run, ctl, tab, measured, empty = _env(tmp_path)
    assert _offered(tab) == (False, False), "New verification has nothing"
    ctl.set_verification_id(measured.id)
    _pump()
    assert _offered(tab) == (True, True), \
        "a dated verification with readings must offer Refine/resume and overlay"
    ctl.set_verification_id(empty.id)
    _pump()
    assert _offered(tab) == (False, False), "an unmeasured date offers neither"
    ctl.set_verification_id("")
    _pump()
    assert _offered(tab) == (False, False)


def test_a_stored_tick_never_judges_the_chart_being_left(qapp, tmp_path,
                                                         popups):
    """The profiling run's stored overlay tick arrives while the verification
    chart is still loaded. No window about the verification, and once the
    profiling chart is in place its measurement is offered and ticked."""
    run, ctl, tab, measured, empty = _env(tmp_path)
    assert tab._overlay_cb.isHidden()
    tab._loading_measure_settings = True      # what load_target_settings does
    try:
        tab._overlay_cb.setChecked(True)
    finally:
        tab._loading_measure_settings = False
    assert popups == [], "a settings load must not pop a window"
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab.set_ti1_path(run.chart_ti2)
    _pump()
    assert popups == [], f"stale overlay window after the switch: {popups}"
    assert _offered(tab) == (True, True)
    assert tab._overlay_cb.isChecked()


def test_a_hidden_box_ticked_by_code_asks_nothing(qapp, tmp_path, popups):
    run, ctl, tab, measured, empty = _env(tmp_path)
    tab._overlay_cb.setChecked(True)          # hidden: nobody clicked it
    assert popups == []


def test_the_window_still_comes_for_an_unmeasured_date_asked_to_overlay(
        qapp, tmp_path, popups):
    """M-OVERLAY-NO-MEASUREMENT keeps its job, about the RIGHT selection: a
    stored tick arriving for a dated verification that has no readings."""
    run, ctl, tab, measured, empty = _env(tmp_path)
    tab.show()
    _pump()
    ctl.set_verification_id(empty.id)
    tab._loading_measure_settings = True
    try:
        tab._overlay_cb.setChecked(True)
    finally:
        tab._loading_measure_settings = False
    _pump()
    tab.hide()
    assert popups == ["This chart has not been measured yet"]


def test_resume_stages_the_dated_readings_beside_the_chart(qapp, tmp_path,
                                                           popups):
    """chartread resumes from <chart>.ti3; the readings are in the dated folder.
    A session that writes nothing leaves the dated file alone and the copy goes."""
    run, ctl, tab, measured, empty = _env(tmp_path)
    tab.show()
    ctl.set_verification_id(measured.id)
    _pump()
    assert popups == ["OFFER"], \
        "arriving at a measured date offers its measurement (#131 scenario 4)"
    tab._resume_cb.setChecked(True)
    staged = tab._stage_verification_for_resume()
    tab.hide()
    beside = run.verify_chart_ti2.with_suffix(".ti3")
    assert staged == beside and beside.read_text(encoding="utf-8") == TI3
    tab._drop_unused_verification_stage()
    assert not beside.exists(), "an unused copy must not stay beside the chart"
    assert measured.measurement_ti3.read_text(encoding="utf-8") == TI3


def test_no_staging_for_new_verification_or_without_resume(qapp, tmp_path,
                                                           popups):
    run, ctl, tab, measured, empty = _env(tmp_path)
    tab.show()
    ctl.set_verification_id(measured.id)
    _pump()
    tab._resume_cb.setChecked(False)
    assert tab._stage_verification_for_resume() is None
    ctl.set_verification_id("")
    _pump()
    assert tab._stage_verification_for_resume() is None
    tab.hide()
    assert not run.verify_chart_ti2.with_suffix(".ti3").exists()
