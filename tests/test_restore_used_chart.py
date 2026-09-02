"""#130 (Knut, 2026-07-25): the "Restore Used Chart" button — its availability
rules and the exact reason it gives when it is unavailable."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,       # noqa: E402
                                       MeasurementTargetController)
from workflow.verify_chart_snapshot import snapshot_chart  # noqa: E402


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


def _env(tmp_path, *, with_chart=True):
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    if with_chart:
        run.verify_chart_ti1.write_text("TI1", encoding="utf-8")
        run.verify_chart_ti2.write_text("TI2", encoding="utf-8")
        (run.verifications_dir / f"{run.verify_stem}.channels.json").write_text("{}", encoding="utf-8")
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return ctl, run


def test_disabled_on_new_verification_with_the_specified_reason(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    enabled, tip = ctl.restore_state()
    assert enabled is False
    assert tip == ("Select an existing Verification run date to restore its "
                   "used chart")


def test_disabled_when_the_date_has_no_stored_chart(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    ctl.set_verification_id(v.id)

    enabled, tip = ctl.restore_state()
    assert enabled is False
    assert tip == "Selected Verification run date has no available chart to restore"


def test_disabled_when_the_stored_chart_folder_is_empty(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    (v.dir / "chart").mkdir()                       # present but empty
    ctl.set_verification_id(v.id)

    enabled, _ = ctl.restore_state()
    assert enabled is False


def test_enabled_for_a_date_that_has_a_stored_chart(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); _live_differs(v)
    ctl.set_verification_id(v.id)

    enabled, tip = ctl.restore_state()
    assert enabled is True
    assert tip == "Restore chart used for selected verification run date"


def test_disabled_while_a_measurement_is_running(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); _live_differs(v); ctl.set_verification_id(v.id)
    assert ctl.restore_state()[0] is True

    ctl.set_measuring(True)
    enabled, tip = ctl.restore_state()
    assert enabled is False and "measurement" in tip.lower()

    ctl.set_measuring(False)
    assert ctl.restore_state()[0] is True


def test_button_hidden_unless_run_type_is_verification(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    bar = MeasurementTargetBar(ctl)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert bar._restore_btn.isVisible() is False

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    # offscreen never truly shows widgets; the enable/tooltip state is the check.
    # The tooltip now opens with the action's NAME, because the button carries
    # only its drawn mark and has no label to read (#130, Knut 2026-07-29).
    assert bar._restore_btn.toolTip() == (
        "Restore Used Chart\n\nSelect an existing Verification run date to "
        "restore its used chart")


def test_confirmation_only_when_the_live_chart_differs(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); ctl.set_verification_id(v.id)
    assert ctl.restore_needs_confirmation() is False

    run.verify_chart_ti2.write_text("SOMETHING ELSE", encoding="utf-8")
    assert ctl.restore_needs_confirmation() is True


def test_restore_emits_chart_restored_and_puts_the_chart_back(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); _live_differs(v); ctl.set_verification_id(v.id)
    run.verify_chart_ti2.write_text("REPLACED", encoding="utf-8")
    seen = {"n": 0}
    ctl.chart_restored.connect(lambda: seen.__setitem__("n", seen["n"] + 1))

    result = ctl.restore_used_chart()

    assert result is not None and result.ok
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "TI2"
    assert seen["n"] == 1, "the tabs must be told to refresh"


def test_restore_is_a_no_op_when_nothing_is_selected(qapp, tmp_path):
    ctl, run = _env(tmp_path)
    assert ctl.restore_used_chart() is None


def test_dropdown_marks_a_verification_with_no_measurement(qapp, tmp_path):
    """#130 decision 1: a folder created by a measurement that was cancelled or
    failed is kept, and marked, so an empty date is never mistaken for a result —
    while staying selectable, because its chart can still be restored."""
    ctl, run = _env(tmp_path)
    started = run.verification("2026-07-25_120000"); started.ensure_dir()
    snapshot_chart(started); _live_differs(started)                       # chart kept, no .ti3 written
    finished = run.verification("2026-07-25_130000"); finished.ensure_dir()
    finished.measurement_ti3.write_text("MEASURED", encoding="utf-8")

    assert ctl.verification_has_measurement("run1", started.id) is False
    assert ctl.verification_has_measurement("run1", finished.id) is True

    bar = MeasurementTargetBar(ctl)
    labels = [bar._verify_combo.itemText(i)
              for i in range(bar._verify_combo.count())]
    assert any("no measurement yet" in t for t in labels), labels
    assert sum("no measurement yet" in t for t in labels) == 1
    # still selectable, and its chart is restorable
    ctl.set_verification_id(started.id)
    assert ctl.restore_state()[0] is True


def test_outcome_says_the_pages_can_be_redrawn(qapp, tmp_path):
    """With a recipe present the snapshot holds no images, so the restore asks
    the caller to redraw them rather than leaving the user to do it."""
    ctl, run = _env(tmp_path)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); _live_differs(v); ctl.set_verification_id(v.id)

    result = ctl.restore_used_chart()

    assert result.ok
    assert result.should_rebuild is True
    assert result.images_restored is False
    assert result.needs_regeneration is False


def test_outcome_needs_no_rebuild_when_the_images_came_back(qapp, tmp_path):
    """Without a recipe the images travel with the snapshot, so there is
    nothing to redraw."""
    ctl, run = _env(tmp_path, with_chart=False)
    run.verify_chart_ti2.write_text("TI2", encoding="utf-8")
    (run.verifications_dir / f"{run.verify_stem}_01.tif").write_text("PAGE", encoding="utf-8")
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); _live_differs(v); ctl.set_verification_id(v.id)
    for p in run.verify_chart_tiffs():
        p.unlink()

    result = ctl.restore_used_chart()

    assert result.ok and result.images_restored is True
    assert result.should_rebuild is False
    assert len(run.verify_chart_tiffs()) == 1


def test_rebuild_is_started_for_the_restored_chart(qapp, tmp_path, monkeypatch):
    """The Create Chart tab redraws the pages from the restored chart files,
    applying that chart's own saved settings first."""
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_chart import TabChart
    ctl, run = _env(tmp_path)
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s2.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "ChromIQ"))
    tab = TabChart(ArgyllRunner(s), ctl._fm, s)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    tab.set_target_controller(ctl)
    v = run.verification("2026-07-25_120000"); v.ensure_dir()
    snapshot_chart(v); _live_differs(v); ctl.set_verification_id(v.id)
    started = {}
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda ti1, params, **k: started.update(ti1=ti1))

    assert tab.rebuild_verification_pages() is True
    assert started.get("ti1") == run.verify_chart_ti1


def test_no_rebuild_without_a_chart_to_rebuild_from(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_chart import TabChart
    ctl, run = _env(tmp_path, with_chart=False)
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s3.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "ChromIQ"))
    tab = TabChart(ArgyllRunner(s), ctl._fm, s)
    tab.set_target_controller(ctl)

    assert tab.rebuild_verification_pages() is False
