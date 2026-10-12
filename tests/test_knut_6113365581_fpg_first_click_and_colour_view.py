"""Knut, #182 6108217111 / 6113365581, 4.3.5-beta.2.

Two things:

1. **The first click on FROM PROFILE GAMUT froze the window.** It asked the
   profile, on the window's thread, which of the 16,608 reference colours it
   can print: measured on his CLJ5550 profile, a 5.14 s stall the first time
   and nothing after (the tab's memo). It is now asked in the background
   (`gamut_target.gamut_coverage_async`), the count line says it is asking,
   and the answer refreshes everything that reads it when it lands.

2. **The 3D tool can show the chart as COLOURS.** A From Profile Gamut chart
   is spread evenly as colours (k82, ΔE in L*a*b*); the tool drew only ink
   amounts (device RGB), where a printer's uneven response makes the same
   chart look crowded and holey (his CLJ5550: 56 % of the device cube makes
   5 % of the colours). "Show:" offers the colour view, drawn to scale, inside
   the outline of the profile's gamut (the device cube's edges and faces
   mapped through the profile).
"""
from __future__ import annotations

import inspect
import os
import threading
import time
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION  # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import gamut_target as gt                   # noqa: E402
from workflow import patch_cube                           # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


# --- 1. the reach is asked in the background --------------------------------

def test_the_reach_is_asked_off_the_calling_thread_and_shared(monkeypatch, tmp_path):
    gate = threading.Event()
    seen = []

    def slow(profile, margin, intent, **kw):
        seen.append(threading.current_thread().name)
        gate.wait(5)
        return 123, 456

    monkeypatch.setattr(gt, "gamut_coverage", slow)
    p = tmp_path / "x.icc"
    one = gt.gamut_coverage_async(p, "safe", "absolute", bin_dir=tmp_path)
    two = gt.gamut_coverage_async(p, "safe", "absolute", bin_dir=tmp_path)
    assert one is two, "a second ask while the first runs must share it"
    assert not one.done()
    gate.set()
    assert one.result(5) == (123, 456)
    assert seen and seen[0] != threading.current_thread().name


def test_one_real_question_to_xicclu_at_a_time():
    """The background reach and a Generate share the memo; the lock makes the
    second wait for the first instead of asking the same thing again."""
    for fn in (gt._round_trip, gt._gamut_density):
        src = inspect.getsource(fn)
        assert "_CACHE_LOCK" in src and "subprocess.run" in src


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def test_the_first_click_does_not_wait_and_the_line_says_so(qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    fm.project().run("run1").profile_icc.write_bytes(b"icc")
    gate = threading.Event()

    def slow(profile, margin, intent, **kw):
        gate.wait(10)
        return 3272, 16608

    monkeypatch.setattr(gt, "gamut_coverage", slow)
    gt._COVERAGE_JOBS.clear()
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    t = time.monotonic()
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    tab._update_gamut_count_line()
    assert time.monotonic() - t < 3.0, "the window waited for the profile"
    assert "Asking your profile" in tab._gamut_count_lbl.text()
    assert tab._gamut_in_gamut_total() is None      # uncapped while unknown
    gate.set()
    end = time.monotonic() + 10
    while "3272 of the 16608" not in tab._gamut_count_lbl.text() \
            and time.monotonic() < end:
        _pump(qapp, 0.05)
    assert "3272 of the 16608" in tab._gamut_count_lbl.text()
    assert tab._gamut_in_gamut_total() == 3272
    assert not tab._gamut_coverage_timer.isActive()


def test_a_failed_reach_is_remembered_and_says_so(qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    fm.project().run("run1").profile_icc.write_bytes(b"icc")

    def broken(*a, **k):
        raise gt.GamutTargetError("xicclu said no")

    monkeypatch.setattr(gt, "gamut_coverage", broken)
    gt._COVERAGE_JOBS.clear()
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    end = time.monotonic() + 10
    while "could not ask" not in tab._gamut_count_lbl.text() \
            and time.monotonic() < end:
        _pump(qapp, 0.05)
    assert "could not ask this profile" in tab._gamut_count_lbl.text()
    assert None in tab._gamut_coverage_cache.values()


def test_a_verification_run_with_a_profile_starts_asking_before_the_click(
        qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    fm.project().run("run1").profile_icc.write_bytes(b"icc")
    asked = []
    monkeypatch.setattr(gt, "gamut_coverage",
                        lambda *a, **k: (asked.append(a) or (10, 20)))
    gt._COVERAGE_JOBS.clear()
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    tab._user_switch_mode("manual")
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    _pump(qapp, 0.5)
    assert tab._mode_name() == "manual"
    assert asked, "nothing was asked before the module was opened"


# --- 2. the colour view ------------------------------------------------------

def _fake_forward(rows, profile, bin_dir, *, intent="r", runner=None):
    """A stand-in printer: L* from the sum, a*/b* from the differences."""
    out = []
    for r, g, b in rows:
        out.append((0.3 * r + 0.6 * g + 0.1 * b, 0.8 * (r - g), 0.8 * (g - b)))
    return out


def test_the_gamut_outline_is_the_device_cube_mapped_through_the_profile(monkeypatch):
    import workflow.xicclu_runner as X
    monkeypatch.setattr(X, "forward_lab", _fake_forward)
    o = patch_cube.gamut_outline(Path("p.icc"), "/bin", intent="a")
    assert len(o.edges) == 12
    assert all(len(e) == patch_cube.OUTLINE_EDGE_STEPS for e in o.edges)
    n = patch_cube.OUTLINE_FACE_STEPS
    assert len(o.vertices) == 6 * n * n
    assert len(o.faces) == 6 * (n - 1) * (n - 1) * 2
    # every edge runs between two cube corners as the profile prints them
    corners = {tuple(np.round(c, 6)) for c in _fake_forward(
        [tuple(c) for c in patch_cube._CUBE_CORNERS], None, None)}
    for e in o.edges:
        assert tuple(np.round(e[0], 6)) in corners
        assert tuple(np.round(e[-1], 6)) in corners


def test_the_colour_view_is_drawn_to_scale_inside_its_outline(monkeypatch):
    import workflow.xicclu_runner as X
    monkeypatch.setattr(X, "forward_lab", _fake_forward)
    o = patch_cube.gamut_outline(Path("p.icc"), "/bin")
    labs = _fake_forward([(10, 20, 30), (90, 10, 50), (50, 50, 50)], None, None)
    pay = patch_cube.lab_payload(labs, [(1, 2, 3)] * 3, outline=o,
                                 stats=patch_cube.lab_spacing_summary(labs))
    kinds = [t["type"] for t in pay["data"]]
    assert "mesh3d" in kinds and kinds[-1] == "scatter3d"
    scene = pay["layout"]["scene"]
    assert scene["aspectmode"] == "manual"
    spans = {ax: scene[ax]["range"][1] - scene[ax]["range"][0]
             for ax in ("xaxis", "yaxis", "zaxis")}
    ratio = scene["aspectratio"]
    # one ΔE*ab is the same length along every axis
    per = [ratio[k] / spans[a] for k, a in (("x", "xaxis"), ("y", "yaxis"),
                                             ("z", "zaxis"))]
    assert max(per) == pytest.approx(min(per))
    # and the old multi-ink view keeps its fixed box
    old = patch_cube.lab_payload(labs, [(1, 2, 3)] * 3)
    assert old["layout"]["scene"]["aspectmode"] == "cube"
    assert all(t["type"] != "mesh3d" for t in old["data"])


def test_the_colour_view_footer_reports_spacing_in_two_decimals():
    text = patch_cube.lab_spacing_summary([(50, 0, 0), (50, 3, 4), (60, 0, 0)])
    assert "3 patches" in text and "median 5.00" in text
    assert "closest 5.00" in text and "ΔE*ab" in text


def test_the_dialog_offers_the_colour_view_beside_the_rgb_cube(qapp, monkeypatch):
    import workflow.xicclu_runner as X
    monkeypatch.setattr(X, "forward_lab", _fake_forward)
    from ui.dialogs.patch_cube_dialog import PatchCubeDialog
    program = [(10.0, 20.0, 30.0), (90.0, 10.0, 50.0), (50.0, 50.0, 50.0)]
    plain = PatchCubeDialog(program)
    assert plain._view_combo is None
    plain.done(0)

    o = patch_cube.gamut_outline(Path("p.icc"), "/bin")
    labs = _fake_forward(program, None, None)
    dlg = PatchCubeDialog(program, colour_view=(labs, [(0, 0, 0)] * 3, o),
                          compare_presets=[("", [("X", Path("x.ti1"))])])
    combo = dlg._view_combo
    assert [combo.itemData(i) for i in range(combo.count())] == ["rgb", "lab"]
    assert combo.currentData() == "rgb", "the RGB cube stays the default"
    assert "From Profile Gamut" in combo.toolTip()
    combo.setCurrentIndex(1)
    assert "Lab" in dlg.windowTitle()
    assert not dlg._compare_combo.isEnabled()
    assert "spacing median" in dlg._panel._pending_payload["stats"]
    combo.setCurrentIndex(0)
    assert dlg._compare_combo.isEnabled()
    assert "RGB" in dlg.windowTitle()
    dlg.done(0)
