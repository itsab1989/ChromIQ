"""A printtarg calibration chart is laid out in order, and arranged one ink
per strip, whatever the layout recipe's "Randomise" says.

calibration_run_type §4.2: the calibration knobs switch printtarg's ``-r``
(Preserve patch order) on. Unticking "Use the ChromIQ layout engine" copies
the layout recipe's "Randomise" onto printtarg's ``-r`` (68742ca1c, June), and
the recipe randomises by default, so in Calibration the knob's ``-r`` was
dropped: the printtarg calibration chart came out shuffled (``RANDOM_START``)
and the one-ramp-per-strip arrangement (Knut 5965186237) was skipped for it,
correctly, because a shuffled chart is not a ramp set in order. Found in the
review of 7386afd8 (REVIEW-NOTES, "Pre-existing").

Fixed twice over: the argument builder gives a calibration chart ``-r``
whatever the params say (``chart_creator._printtarg_keeps_order``), and the
engine-off conversion leaves Calibration's ``-r`` ticked. Profiling charts
keep the recipe's choice in both directions.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from tests.argyll_env import argyll_tool
from tests.test_calibration_ramps_start_their_own_strip import (
    _check_arrangement, _ti2_sequence)
from workflow.chart_creator import ChartCreator, ChartParams, printtarg_layout_argv


def _params(*, cal: bool, no_randomise: bool) -> ChartParams:
    return ChartParams(target_name="P", device_type="2", is_manual=True,
                       instrument="i1", paper="A4", cal_target=cal,
                       no_randomise=no_randomise)


# ---------------------------------------------------------------------------
# the argument builder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("no_randomise", [False, True])
def test_a_calibration_chart_always_gets_minus_r(no_randomise):
    """Mutation: make `_printtarg_keeps_order` return `p.no_randomise` alone
    and the False case fails, which is the shuffled chart."""
    argv = printtarg_layout_argv(_params(cal=True, no_randomise=no_randomise))
    assert "-r" in argv


@pytest.mark.parametrize("no_randomise", [False, True])
def test_a_profiling_chart_keeps_its_own_choice(no_randomise):
    argv = printtarg_layout_argv(_params(cal=False, no_randomise=no_randomise))
    assert ("-r" in argv) is no_randomise


# ---------------------------------------------------------------------------
# the engine-off conversion, on a real Create Chart tab
# ---------------------------------------------------------------------------

@pytest.fixture
def chart(cal_settings, qapp):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    fm = FileManager(cal_settings)
    fm.set_target_name("Test-Printer")
    fm.project()
    tab = TabChart(ArgyllRunner(cal_settings), fm, cal_settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    tab.set_calibration_mode(True)
    tab._switch_mode("manual")
    if not tab._manual_engine_check.isChecked():
        tab._manual_engine_check.click()
    assert tab._manual_engine_check.isChecked()
    yield tab, ctl
    tab.deleteLater()


def _engine_off_with(tab, randomize: bool) -> None:
    panel = tab._manual_layout_panel
    tab._set_engine_recipe(replace(panel.get_recipe(), randomize=randomize))
    assert panel.get_recipe().randomize is randomize
    tab._manual_engine_check.click()
    assert not tab._manual_engine_check.isChecked()


@pytest.mark.parametrize("randomize", [True, False])
def test_calibration_keeps_minus_r_when_the_engine_goes_off(chart, randomize):
    """Mutation: put back `not r.randomize` alone in
    `_convert_engine_to_printtarg` and the True case fails."""
    from core.measurement_target import RUN_TYPE_CALIBRATION
    tab, ctl = chart
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert tab._manual_get("printtarg", "-r", False) is True   # the knob
    _engine_off_with(tab, randomize)
    assert tab._manual_get("printtarg", "-r", False) is True
    params = tab._collect_manual()
    params.cal_target = tab._calibration_selected()
    assert params.cal_target
    assert "-r" in printtarg_layout_argv(params)


@pytest.mark.parametrize("randomize", [True, False])
def test_profiling_still_takes_randomise_from_the_recipe(chart, randomize):
    from core.measurement_target import RUN_TYPE_PROFILING
    tab, ctl = chart
    ctl.set_run_type(RUN_TYPE_PROFILING)
    _engine_off_with(tab, randomize)
    assert bool(tab._manual_get("printtarg", "-r", False)) is (not randomize)
    params = tab._collect_manual()
    params.cal_target = tab._calibration_selected()
    assert not params.cal_target
    assert ("-r" in printtarg_layout_argv(params)) is (not randomize)


# ---------------------------------------------------------------------------
# the real thing: targen + printtarg through ChartCreator, engine off
# ---------------------------------------------------------------------------

class _SubprocessRunner:
    """Runs the real Argyll tool to completion, then reports its exit code."""

    is_running = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        self.calls.append((tool, list(args)))
        r = subprocess.run([argyll_tool(tool), *args], cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300,
                           stdin=subprocess.DEVNULL)
        assert r.returncode == 0, (f"{tool} {args} did not finish cleanly:\n"
                                   f"{r.stdout}\n{r.stderr}")
        if on_line:
            for ln in (r.stdout + r.stderr).splitlines():
                on_line(ln)
        if on_finish:
            on_finish(r.returncode)

    def abort(self):
        pass


class _Settings:
    def __init__(self) -> None:
        self._d = {"argyll_bin_path": str(Path(argyll_tool("targen")).parent),
                   "use_chromiq_layout_engine": False}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


class _FM:
    def __init__(self, root: Path) -> None:
        from core.file_manager import Project
        self._project = Project.create(root, root.name)

    def project(self):
        return self._project

    def chart_stem(self, *, cal_target: bool) -> str:
        p = self._project
        return p.calibration.stem if cal_target else p.current_run().stem


@pytest.mark.skipif(
    not (argyll_tool("targen") and argyll_tool("printtarg")),
    reason="ArgyllCMS not installed")
@pytest.mark.parametrize("d,channels,additive", [(2, 3, True), (4, 4, False)])
def test_the_printtarg_calibration_chart_is_in_order_and_one_ink_per_strip(
        tmp_path, d, channels, additive):
    """Engine off, Preserve patch order unticked (what the recipe's default
    "Randomise" left there): the chart is still in order, and each ink's ramp
    starts its own strip."""
    fm = _FM(tmp_path / "Proj")
    runner = _SubprocessRunner()
    creator = ChartCreator(runner, fm, _Settings())
    p = ChartParams(target_name="Proj", device_type=str(d), is_manual=True,
                    instrument="i1", paper="A4", tiff_dpi=100,
                    patches=0, white_patches=0, black_patches=0,
                    good_mode=False, grey_steps=0, single_channel_steps=20,
                    cal_target=True, no_randomise=False, stamp_commands=False)
    assert not creator._should_use_engine(p)
    got: list = []
    creator.generate(p, on_line=lambda _l: None, on_finish=got.append)
    assert got and got[0], "the build did not finish"
    pt = [a for t, a in runner.calls if t == "printtarg"]
    assert len(pt) == 2, "printtarg was not asked twice (no rearrangement)"
    assert all("-r" in a for a in pt)
    work = fm.project().calibration.dir
    ti2 = work / f"{fm.chart_stem(cal_target=True)}.ti2"
    text = ti2.read_text(encoding="latin-1")
    assert not re.search(r"^RANDOM_START", text, re.M), "the chart is shuffled"
    sip, seq, _t = _ti2_sequence(ti2, additive)
    _check_arrangement(seq, channels, 20, sip)
    shutil.rmtree(tmp_path / "Proj", ignore_errors=True)
