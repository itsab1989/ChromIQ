"""#130 (Knut, 2026-07-26): starting a measurement on a verification date that
already stores a chart must warn before that stored chart is replaced — and must
stay silent when the loaded chart is the very same one.

The comparison is deliberately the same content check that decides whether
"Restore Used Chart" asks for confirmation, so the two features can never
disagree about what "a different chart" means.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_VERIFICATION,          # noqa: E402
                                     chart_overwrite_message)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController    # noqa: E402
from ui.tabs.tab_measure import TabMeasure                # noqa: E402
from workflow.verify_chart_snapshot import (has_snapshot,            # noqa: E402
                                            snapshot_chart)


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
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti1.write_text("TI1-v1")
    run.verify_chart_ti2.write_text("TI2-v1")
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    tab._verify_cb.setChecked(True)
    return s, run, ctl, tab


# ---- when the question is asked at all -----------------------------------
def test_a_date_with_no_stored_chart_is_not_questioned(qapp, tmp_path):
    """Nothing would be lost, so nothing is asked."""
    _s, run, _ctl, tab = _env(tmp_path)
    v = run.verification("2026-07-20_100000"); v.ensure_dir()
    assert tab._chart_overwrite_choice(v) == "go"


def test_re_measuring_the_same_chart_is_not_questioned(qapp, tmp_path):
    """The ordinary case — reading the same chart again — must not be
    interrupted by a pop-up."""
    _s, run, _ctl, tab = _env(tmp_path)
    v = run.verification("2026-07-20_100000"); v.ensure_dir()
    snapshot_chart(v)
    assert tab._chart_overwrite_choice(v) == "go"


def test_a_different_chart_is_questioned(qapp, tmp_path, monkeypatch):
    """A changed chart reaches the dialog. The dialog itself is answered by the
    stub; what is asserted here is that it was raised at all."""
    _s, run, _ctl, tab = _env(tmp_path)
    v = run.verification("2026-07-20_100000"); v.ensure_dir()
    snapshot_chart(v)
    run.verify_chart_ti2.write_text("TI2-v2 — a different chart")

    asked = {"n": 0}
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: asked.__setitem__("n", 1))
    tab._chart_overwrite_choice(v)
    assert asked["n"] == 1, "a changed chart must raise the warning"


# ---- what each answer does ------------------------------------------------
def _arm(tmp_path):
    s, run, ctl, tab = _env(tmp_path)
    v = run.verification("2026-07-20_100000"); v.ensure_dir()
    snapshot_chart(v)
    run.verify_chart_ti2.write_text("TI2-v2 — a different chart")
    ctl.set_verification_id(v.id)
    return run, ctl, tab, v


def test_cancel_stops_the_measurement_and_changes_nothing(qapp, tmp_path,
                                                          monkeypatch):
    run, ctl, tab, v = _arm(tmp_path)
    monkeypatch.setattr(TabMeasure, "_chart_overwrite_choice",
                        lambda self, _v: "cancel")
    before = sorted(p.name for p in run.verifications_dir.iterdir())

    assert tab._snapshot_verification_chart() is False, "the start must abort"
    from workflow.verify_chart_snapshot import snapshot_files
    kept = {p.name: p.read_text() for p in snapshot_files(v)}
    assert kept[run.verify_chart_ti2.name] == "TI2-v1", \
        "the stored chart must survive a cancel untouched"
    assert sorted(p.name for p in run.verifications_dir.iterdir()) == before, \
        "cancelling must not create a dated folder"
    assert ctl.target.verification_id == v.id


def test_replace_overwrites_the_stored_chart(qapp, tmp_path, monkeypatch):
    run, ctl, tab, v = _arm(tmp_path)
    monkeypatch.setattr(TabMeasure, "_chart_overwrite_choice",
                        lambda self, _v: "go")

    assert tab._snapshot_verification_chart() is True
    from workflow.verify_chart_snapshot import snapshot_files
    kept = {p.name: p.read_text() for p in snapshot_files(v)}
    assert kept[run.verify_chart_ti2.name] == "TI2-v2 — a different chart"
    assert ctl.target.verification_id == v.id, "the date does not change"


def test_measuring_into_a_new_date_leaves_the_old_one_intact(qapp, tmp_path,
                                                             monkeypatch):
    """The answer that keeps both: the earlier check keeps its chart, and the
    reading about to be taken gets a dated entry of its own."""
    run, ctl, tab, v = _arm(tmp_path)
    monkeypatch.setattr(TabMeasure, "_chart_overwrite_choice",
                        lambda self, _v: "new")

    assert tab._snapshot_verification_chart() is True
    from workflow.verify_chart_snapshot import snapshot_files
    old = {p.name: p.read_text() for p in snapshot_files(v)}
    assert old[run.verify_chart_ti2.name] == "TI2-v1", \
        "the earlier date must keep the chart it was measured with"

    new_id = ctl.target.verification_id
    assert new_id and new_id != v.id, "the bar must move to a new date"
    fresh = run.verification(new_id)
    assert has_snapshot(fresh)
    made = {p.name: p.read_text() for p in snapshot_files(fresh)}
    assert made[run.verify_chart_ti2.name] == "TI2-v2 — a different chart"


# ---- wording --------------------------------------------------------------
def test_the_message_names_the_date_and_the_way_out():
    text = chart_overwrite_message("2026-07-20_100000")
    assert "2026-07-20 10:00" in text, "the date must be readable, not a stamp"
    assert "Restore Used Chart" in text
    assert "new verification date" in text
