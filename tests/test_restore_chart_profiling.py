"""#130 (Knut, 2026-07-27): "Restore Used Chart" works for Profiling too.

A verification picks which stored chart to restore from its date dropdown; a
profiling run has exactly one measurement and therefore exactly one stored
chart, so the button simply puts back the chart that run was measured with.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow.chart_slot import slot_for                  # noqa: E402
from workflow.verify_chart_snapshot import (slot_has_snapshot,     # noqa: E402
                                            snapshot_slot)


def _live_differs(target) -> None:
    """Edit the live chart so that restoring it would actually change something.

    #130 (Knut, 2026-07-30): "Restore Used Chart" is greyed out when the loaded
    chart is already byte-identical to the stored one — pressing it then copies
    the files over themselves, which is why it looked like a button that does
    nothing. A snapshot taken on the previous line is identical by definition,
    so these tests now state the case they are really about: a stored chart that
    differs from what is loaded.
    """
    from workflow.chart_slot import slot_for
    for f in slot_for(target).files_to_copy():
        f.write_text(f.read_text(encoding="utf-8") + "  # edited since the snapshot", encoding="utf-8")
        return


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti1.write_text("TI1", encoding="utf-8")
    run.chart_ti2.write_text("TI2", encoding="utf-8")
    run.chart_channels_json.write_text("{}", encoding="utf-8")
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
    return s, run, ctl


# ---- the button's states --------------------------------------------------
def test_it_is_offered_for_profiling_once_a_chart_is_stored(qapp, tmp_path):
    _s, run, ctl = _env(tmp_path)
    enabled, tip = ctl.restore_state()
    assert not enabled and "no stored chart yet" in tip, tip

    snapshot_slot(slot_for(run)); _live_differs(run)

    enabled, tip = ctl.restore_state()
    assert enabled and "was measured with" in tip, tip


def test_a_new_run_says_to_make_the_chart_first(qapp, tmp_path):
    _s, _run, ctl = _env(tmp_path)
    ctl.set_profile_run("")                       # "New run"
    enabled, tip = ctl.restore_state()
    assert not enabled
    assert "Create the chart for this run first" in tip, tip


def test_it_is_unavailable_while_measuring(qapp, tmp_path):
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    ctl.set_measuring(True)
    enabled, _tip = ctl.restore_state()
    assert not enabled


def test_the_button_says_when_the_stored_chart_is_out_of_step(qapp, tmp_path):
    """After "Measure without changing the stored chart" the copy describes an
    earlier measurement — the button must not pretend otherwise."""
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    meta = run.load_meta(); meta.chart_snapshot_stale = True; run.save_meta(meta)

    enabled, tip = ctl.restore_state()

    assert enabled
    assert "from an earlier measurement" in tip, tip


# ---- restoring ------------------------------------------------------------
def test_restoring_puts_the_run_chart_back(qapp, tmp_path):
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    run.chart_ti2.write_text("REPLACED", encoding="utf-8")
    run.measurement_ti3.write_text("A MEASUREMENT", encoding="utf-8")

    result = ctl.restore_used_chart()

    assert result is not None and result.ok
    assert run.chart_ti2.read_text(encoding="utf-8") == "TI2"
    assert run.measurement_ti3.read_text(encoding="utf-8") == "A MEASUREMENT"


def test_the_confirmation_is_only_needed_when_the_chart_changed(qapp, tmp_path):
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run))
    assert ctl.restore_needs_confirmation() is False
    run.chart_ti2.write_text("REPLACED", encoding="utf-8")
    assert ctl.restore_needs_confirmation() is True


def test_switching_run_type_switches_which_chart_the_button_means(qapp,
                                                                  tmp_path):
    """One button, two meanings — decided by Run type, with no crossover."""
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)                  # a profiling copy exists

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    enabled, tip = ctl.restore_state()
    assert not enabled, "no verification date is selected"
    assert "Verification run date" in tip, tip

    ctl.set_run_type(RUN_TYPE_PROFILING)
    enabled, _tip = ctl.restore_state()
    assert enabled, "the profiling copy is still what this button restores"


# ---- the three answers at measurement start -------------------------------
def _tab(s, ctl):
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    return tab


def test_the_first_measurement_stores_the_chart_without_asking(qapp, tmp_path,
                                                               monkeypatch):
    s, run, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: pytest.fail("nothing to lose, so no question"))

    assert tab._snapshot_verification_chart() is True
    assert slot_has_snapshot(slot_for(run))


def test_measuring_the_same_chart_again_asks_nothing(qapp, tmp_path,
                                                     monkeypatch):
    s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run))
    tab = _tab(s, ctl)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: pytest.fail("the chart is unchanged"))
    assert tab._snapshot_verification_chart() is True


def test_keep_leaves_the_copy_alone_and_records_it(qapp, tmp_path, monkeypatch):
    """Knut's third answer. The copy must survive AND the mismatch must be
    written down, or Restore would later put back a chart that does not
    describe the measurement."""
    s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    run.chart_ti2.write_text("A DIFFERENT CHART", encoding="utf-8")
    tab = _tab(s, ctl)
    monkeypatch.setattr(type(tab), "_profiling_overwrite_choice",
                        lambda self, _r: "keep")

    assert tab._snapshot_verification_chart() is True

    kept = (slot_for(run).snapshot_dir / f"{run.stem}.ti2").read_text(encoding="utf-8")
    assert kept == "TI2", "the stored chart must not have been touched"
    assert run.load_meta().chart_snapshot_stale is True


def test_replace_updates_the_copy_and_clears_the_mark(qapp, tmp_path,
                                                      monkeypatch):
    s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    meta = run.load_meta(); meta.chart_snapshot_stale = True; run.save_meta(meta)
    run.chart_ti2.write_text("A DIFFERENT CHART", encoding="utf-8")
    tab = _tab(s, ctl)
    monkeypatch.setattr(type(tab), "_profiling_overwrite_choice",
                        lambda self, _r: "go")

    assert tab._snapshot_verification_chart() is True

    kept = (slot_for(run).snapshot_dir / f"{run.stem}.ti2").read_text(encoding="utf-8")
    assert kept == "A DIFFERENT CHART"
    assert run.load_meta().chart_snapshot_stale is False, \
        "the copy matches again, so the warning must stop"


def test_cancel_stops_the_measurement_and_changes_nothing(qapp, tmp_path,
                                                          monkeypatch):
    s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    run.chart_ti2.write_text("A DIFFERENT CHART", encoding="utf-8")
    tab = _tab(s, ctl)
    monkeypatch.setattr(type(tab), "_profiling_overwrite_choice",
                        lambda self, _r: "cancel")

    assert tab._snapshot_verification_chart() is False

    kept = (slot_for(run).snapshot_dir / f"{run.stem}.ti2").read_text(encoding="utf-8")
    assert kept == "TI2"


# ---- the button has to be ON SCREEN, not merely enabled -------------------
def test_the_button_is_visible_for_profiling_as_well(qapp, tmp_path):
    """Knut, beta.42: the button worked for a profiling run but was never
    shown, because its visibility still followed the Verification date box.
    Being enabled is no use if it is not on screen."""
    from ui.measurement_target_bar import MeasurementTargetBar
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)
    bar = MeasurementTargetBar(ctl)
    bar.show()
    QApplication.processEvents()

    assert not bar._restore_btn.isHidden(), "Profiling must show the button"
    assert bar._restore_btn.isEnabled()
    # …and the date box, which belongs to Verification, must stay hidden
    assert bar._verify_combo.isHidden()

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents()
    assert not bar._restore_btn.isHidden(), "and still shown for Verification"
    assert not bar._verify_combo.isHidden()


def test_its_state_follows_the_run_type_while_visible(qapp, tmp_path):
    from ui.measurement_target_bar import MeasurementTargetBar
    _s, run, ctl = _env(tmp_path)
    snapshot_slot(slot_for(run)); _live_differs(run)                  # a profiling copy only
    bar = MeasurementTargetBar(ctl)
    bar.show(); QApplication.processEvents()
    assert bar._restore_btn.isEnabled(), "profiling: there is a copy"

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents()
    assert not bar._restore_btn.isEnabled(), "verification: no date selected"
