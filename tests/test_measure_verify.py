"""Measure-tab verification option: a verify run must save a separate, tagged
'-verify.ti3' and never advance to Build Profile."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def _write_chart_ti3(p: Path) -> None:
    p.write_text(
        'CTI3\n\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "iRGB_XYZ"\nNUMBER_OF_FIELDS 7\n'
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100 86 90 75 \n"
        "END_DATA\n")


def _make_tab():
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    return TabMeasure(ArgyllRunner(s), s)


def _attach_controller(tab, tmp_path, name="P"):
    """Give the tab a Profile-run bar controller pointed at *name*.

    The three guard tests used to flip the module's Verification checkbox, which
    needed no controller. That checkbox is gone (Knut, #130 2026-07-29) and the
    bar's Run type is the only switch, so they need a bar.
    """
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    tab._settings.set("custom_output_path", str(tmp_path))
    fm = FileManager(tab._settings)
    fm.set_target_name(name)
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    tab.set_target_controller(ctl)
    return ctl


def test_verify_run_saves_tagged_verify_file(tmp_path, monkeypatch):
    # Don't let the completion dialog block or open the inspector.
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from workflow.ti3_analysis import is_verification_ti3, parse_ti3

    tab = _make_tab()
    chart = tmp_path / "chart.ti2"
    chart.touch()
    _write_chart_ti3(tmp_path / "chart.ti3")

    tab._ti1_path = chart
    tab._verify_run = True
    tab._ti3_mtime_before = None      # fresh file
    tab._all_done_shown = True
    tab._measure_failed = False

    emitted: list = []
    tab.measure_finished.connect(emitted.append)

    tab._on_measure_done(0)

    # #130: a verification is filed in a dated verifications/<date>/ folder
    # (history), not overwritten flat next to the chart.
    verifs = list(tmp_path.glob("verifications/*/*-verify.ti3"))
    assert len(verifs) == 1                        # one dated verification run
    out = verifs[0]
    assert not (tmp_path / "chart.ti3").exists()   # original renamed away
    assert not (tmp_path / "chart-verify.ti3").exists()  # not left flat at root
    assert is_verification_ti3(parse_ti3(out))     # tagged
    assert emitted == []                           # never advanced to Build Profile
    assert tab._verify_run is False                # consumed


def test_normal_run_unaffected(tmp_path, monkeypatch):
    """A non-verify read still emits measure_finished on the plain .ti3."""
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab = _make_tab()
    chart = tmp_path / "chart.ti2"
    chart.touch()
    _write_chart_ti3(tmp_path / "chart.ti3")
    tab._ti1_path = chart
    tab._verify_run = False
    tab._ti3_mtime_before = None
    tab._all_done_shown = True
    tab._measure_failed = False

    emitted: list = []
    tab.measure_finished.connect(emitted.append)
    tab._on_measure_done(0)

    assert (tmp_path / "chart.ti3").exists()       # untouched
    assert not (tmp_path / "chart-verify.ti3").exists()
    assert emitted and emitted[0].name == "chart.ti3"


def test_verification_guard_blocks_without_profile(tmp_path):
    """#130 Hole 1: 'Profile verification' on a run with no built profile is
    blocked with a guiding message; with a profile it proceeds."""
    from core.file_manager import Project
    tab = _make_tab()
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("x")
    tab._ti1_path = run.chart_ti2
    _attach_controller(tab, tmp_path)
    tab._target_ctl.set_run_type("verification")

    # No profile yet → blocked with a message.
    assert tab._verification_guard() is not None
    # Build a profile → Hole 1 satisfied, but no verify chart yet → Hole 2 blocks.
    run.profile_icc.write_text("icc")
    assert tab._verification_guard() is not None
    # Create the verification chart → allowed.
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("vc")
    assert tab._verification_guard() is None
    # Not ticked → never blocked.
    tab._target_ctl.set_run_type("profiling")
    assert tab._verification_guard() is None


def test_verification_guard_hole2_no_verify_chart(tmp_path):
    """#130 Hole 2: a run with a finished profile but no verification chart yet
    returns the 'create a verification chart first' guidance — distinct from the
    Hole 1 (no profile) message."""
    from core.file_manager import Project
    tab = _make_tab()
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("x"); run.profile_icc.write_text("icc")
    tab._ti1_path = run.chart_ti2
    _attach_controller(tab, tmp_path)
    tab._target_ctl.set_run_type("verification")
    msg = tab._verification_guard()
    # §M owns the text now (Knut, beta.128) — the guard picks the message.
    assert msg is not None and msg.id == "M-VERIFY-NO-CHART"
    assert "verification chart" in msg.body.lower()
    assert "doesn't have a built profile" not in msg.body   # not the Hole 1 text


def test_verification_guard_ignores_external_charts(tmp_path):
    tab = _make_tab()
    (tmp_path / "loose.ti2").write_text("x")
    tab._ti1_path = tmp_path / "loose.ti2"
    _attach_controller(tab, tmp_path)
    tab._target_ctl.set_run_type("verification")
    # Not inside runs/runN → the verification model doesn't apply, no block.
    assert tab._verification_guard() is None


def test_verification_guard_keys_off_bar_run(tmp_path, monkeypatch):
    """#130 (Knut): the guard must fire from the Profile-run bar even when the
    loaded chart is a verify chart under verifications/ (not the run root) — a
    run with no built profile blocks a verification Start."""
    from core.file_manager import Project, FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    tab = _make_tab()
    fm = FileManager(tab._settings)
    tab._settings.set("custom_output_path", str(tmp_path))
    proj = Project.create(tmp_path / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("chart")                 # profiling chart, but…
    # …no built profile. Bar → this run, Run type = Verification.
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    from core.measurement_target import RUN_TYPE_VERIFICATION
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab.set_target_controller(ctl)
    # A verify chart loaded from verifications/ (its parent is not the run root).
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("vc")
    tab._ti1_path = run.verify_chart_ti2
    tab._target_ctl.set_run_type("verification")

    msg = tab._verification_guard()
    assert msg is not None and msg.id == "M-VERIFY-NO-PROFILE"
    assert "doesn't have a built profile" in msg.body                  # Hole 1 fires
