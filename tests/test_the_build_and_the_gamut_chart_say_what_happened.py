"""Two reports from a user driving the from-profile-gamut path, 2026-09-11.

**V1 — "the colprof output area doesn't seem to show anything while the profile
is building".** It was not the box. MEASURED against ArgyllCMS 3.5.0 on her own
4,000-patch measurement, output timestamped byte by byte: without ``-v``,
colprof prints **nothing at all** for the whole build (18.71 s at ``-qm``, zero
bytes, exit 0), and neither `_collect_guided_profile` nor
`_collect_manual_profile` ever set `verbose`. Driven on screen afterwards: 0
characters in the box across all 44 s of a real build, sampled every 0.25 s.
With ``-v`` the tool names each phase and ticks a percentage for it -- a
percentage that RESTARTS at zero every phase, so that is exactly what the bar
shows and no whole-build figure is invented.

**V2 — she asked the FROM PROFILE GAMUT module for 542 colours and got a chart
of 25.** Two separate failures to speak, both reproduced on screen with her
project:

* The one notice that existed was written into the chart log and then wiped:
  `_on_generate_gamut` appended it, and the very next statement called
  `_generate_from_ti1`, which calls `self._log.clear()` before the build
  starts. It was erased every time.
* The layout panel's "estimate" column is never recomputed while the module is
  the active mode, so it kept describing the Manual targen chart from before.
  Her screen read *Total patches 25 on screen / 4032 estimate*, *Pages 1 / 6*;
  reproduced here as 25 against 4025 and one page against eight.

And the grey line under the count told her the in-gamut count "runs the first
time a profile is available" -- in a label that is only ever drawn when a
profile IS there.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                                # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

from core.argyll_runner import ArgyllRunner                       # noqa: E402
from core.file_manager import FileManager, Project                # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION         # noqa: E402
from core.settings import AppSettings                             # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_profile import TabProfile                        # noqa: E402
from workflow import gamut_target as gt                           # noqa: E402
from workflow.profile_builder import (ProfileBuilder,             # noqa: E402
                                      colprof_percent, colprof_phase)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# V1 — colprof is asked to speak, and what it says drives the bar
# ---------------------------------------------------------------------------

#: Verbatim from a timestamped `colprof -v -al -qm` run on a real 4,000-patch
#: measurement (ArgyllCMS 3.5.0). The `\r` terminators are what the reader
#: splits on, so these are the strings the tab actually receives.
_MEASURED_PHASE_LINES = [
    "Estimating white point",
    "Creating optimised per channel curves",
    "About to optimise temporary matrix",
    "About to optimise input, matrix and output together",
    "About to adjust a and b output curves for white point",
    "Create final clut from scattered data",
    "Doing White point fine tune:",
    "Find black point",
    "Setting up B to A table lookup",
    "Creating B to A tables",
    "Creating gamut boundary table",
]
_MEASURED_PCT_LINES = ["  0%", " 17%", " 45%", "100%", "10%", "99%"]
_MEASURED_PLAIN_LINES = [
    "No of test patches = 4000",
    "Done B to A tables",
    "Rev cache RAM = 27380 Mbytes",
    "calc_ocent failed to return in-gamut focal point!",
    "Profile check complete, peak err = 0.652318, avg err = 0.090577",
]


@pytest.fixture
def tab(qapp):
    s = AppSettings()
    return TabProfile(ArgyllRunner(s), s)


def test_chromiq_asks_colprof_to_say_what_it_is_doing(tab, tmp_path):
    """The whole of V1 in one line of arguments: without `-v` there is no
    output to show, measured at zero bytes over a complete build."""
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    tab._ti3_path = ti3
    for mode in ("manual", "guided"):
        params = (tab._collect_manual_profile() if mode == "manual"
                  else tab._collect_guided_profile())
        assert params.verbose, f"the {mode} panel does not ask colprof to speak"
        assert "-v" in ProfileBuilder(tab._runner)._build_args(params), (
            f"colprof is run without -v from the {mode} panel, so it prints "
            f"nothing at all and the output box stays empty for the whole "
            f"build")


@pytest.mark.parametrize("line", _MEASURED_PCT_LINES)
def test_a_percentage_drives_the_bar_and_stays_out_of_the_log(tab, line):
    tab._building_with = "colprof"
    tab._log.clear()
    tab._on_log_line(line)
    want = int(line.strip().rstrip("%")) / 100.0
    assert tab._progress_bar._value == pytest.approx(want), (
        "the percentage colprof reports is not reaching the progress bar")
    assert tab._log.toPlainText() == "", (
        "a bare percentage was written into the output box; a -qu build ticks "
        "231 of them and they would bury the phase names they belong to")


@pytest.mark.parametrize("line", _MEASURED_PHASE_LINES)
def test_a_phase_names_the_bar_and_is_still_written_down(tab, line):
    tab._building_with = "colprof"
    tab._log.clear()
    tab._on_log_line(line)
    assert line in tab._log.toPlainText(), (
        "the phase name must stay in the output box: it is the only thing "
        "that says which phase a restarting percentage belongs to")
    assert tab._progress_bar._sub == line.rstrip(":"), (
        f"the bar does not name the phase it is showing: "
        f"{tab._progress_bar._sub!r}")
    assert tab._progress_bar._value is None, (
        "a new phase must put the bar back to indeterminate: its percentage "
        "restarts at zero, and colprof can be silent for 107 s of a 457 s "
        "build before the first one arrives")


@pytest.mark.parametrize("line", _MEASURED_PLAIN_LINES)
def test_ordinary_output_is_written_down_untouched(tab, line):
    tab._building_with = "colprof"
    tab._log.clear()
    tab._on_log_line(line)
    assert line in tab._log.toPlainText()


def test_the_chromiq_engines_output_is_never_read_as_colprof_progress(tab):
    """The two builders share `_on_log_line`. The engine has its own
    vocabulary, so a line of its output that happens to look like a colprof
    percentage must still reach the box."""
    tab._building_with = "engine"
    tab._log.clear()
    tab._on_log_line(" 42%")
    assert " 42%" in tab._log.toPlainText()


def test_the_parser_reads_what_colprof_really_writes():
    for line in _MEASURED_PHASE_LINES:
        assert colprof_phase(line) == line.rstrip(":")
        assert colprof_percent(line) is None
    for line in _MEASURED_PCT_LINES:
        assert colprof_phase(line) is None
        assert colprof_percent(line) == pytest.approx(
            int(line.strip().rstrip("%")) / 100.0)
    for line in _MEASURED_PLAIN_LINES:
        assert colprof_phase(line) is None
        assert colprof_percent(line) is None
    # A number that cannot be a percentage is a misread, not progress.
    assert colprof_percent("101%") is None
    assert colprof_percent("400%") is None
    assert colprof_percent("") is None


# ---------------------------------------------------------------------------
# V2 — the module says how few colours it found, and the panel stops
#      describing a different chart
# ---------------------------------------------------------------------------

def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def _gamut_tab(qapp, tmp_path, monkeypatch, *, reachable: int):
    from ui.tabs.tab_chart import TabChart
    s, fm, ctl = _env(tmp_path)
    fm.project().run("run1").profile_icc.write_bytes(b"icc")
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)

    def fake_select(profile, count, margin, intent, **kw):
        sel = gt.GamutSelection(
            master_version="TEST-r0", master_total=5960,
            in_gamut_total=reachable, requested=count,
            intent=intent, margin=margin)
        sel.targets = [(i, (50.0, 0.0, 0.0), (10.0, 20.0, 30.0))
                       for i in range(min(count, reachable))]
        sel.corners = list(zip(gt.CORNER_DEVICES, gt.CORNER_DEVICES))
        return sel
    monkeypatch.setattr("workflow.gamut_target.select_gamut_targets",
                        fake_select)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: reachable)
    tab._gamut_master_total = 5960
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    return tab


def test_the_shortfall_notice_survives_the_build_clearing_the_log(
        qapp, tmp_path, monkeypatch):
    """Her exact case: 542 asked for, 13 reachable.

    The double clears the log the way the real `_generate_from_ti1` does --
    without that, this test passes with the bug in place, which is how the
    notice went unnoticed for so long.
    """
    tab = _gamut_tab(qapp, tmp_path, monkeypatch, reachable=13)

    def fake_build(ti1, **kw):
        tab._log.clear()          # exactly what the real one does, first
        return True
    monkeypatch.setattr(tab, "_generate_from_ti1", fake_build)
    tab._gamut_count_spin.setValue(542)

    tab._on_generate()
    said = tab._log.toPlainText()
    assert "Only 13 of the requested 542" in said, (
        "a chart that collapsed from 542 colours to 13 said nothing: the "
        f"notice was cleared by the build that followed it. Log: {said!r}")


def test_a_build_that_never_started_does_not_announce_a_chart(
        qapp, tmp_path, monkeypatch):
    tab = _gamut_tab(qapp, tmp_path, monkeypatch, reachable=13)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda ti1, **kw: False)
    tab._gamut_count_spin.setValue(542)
    tab._on_generate()
    assert "Only 13" not in tab._log.toPlainText(), (
        "a refused build must not report a chart it did not make")


def test_the_estimate_column_answers_for_the_gamut_chart(
        qapp, tmp_path, monkeypatch):
    """Her panel read 25 on screen against 4032 estimate, because the estimate
    was the Manual module's last answer and nothing recomputed it."""
    tab = _gamut_tab(qapp, tmp_path, monkeypatch, reachable=13)
    tab._gamut_count_spin.setValue(542)

    seen: list = []
    monkeypatch.setattr(tab, "_predict_layout_info",
                        lambda geom, paper, pages, npat=None:
                        seen.append(npat))
    monkeypatch.setattr(tab, "_manual_engine_check_is_on", lambda: True,
                        raising=False)
    tab._refresh_layout_estimate(use_engine=True)
    assert seen, ("the estimate column is not recomputed at all while the "
                  "gamut module is the active mode, so it keeps describing "
                  "the Manual chart from before")
    assert seen[-1] == 13 + 8, (
        f"the estimate lays out {seen[-1]} patches where this module's "
        f"Generate would lay out 13 reachable colours plus the 8 cube "
        f"corners")


def test_the_estimate_stays_silent_when_the_module_has_no_profile(
        qapp, tmp_path, monkeypatch):
    tab = _gamut_tab(qapp, tmp_path, monkeypatch, reachable=13)
    monkeypatch.setattr(tab, "_gamut_profile", lambda: None)
    cleared: list = []
    monkeypatch.setattr(tab._layout_info_panel, "clear_estimate",
                        lambda: cleared.append(True))
    monkeypatch.setattr(tab, "_predict_layout_info",
                        lambda *a, **k: pytest.fail(
                            "an estimate was published for a chart the module "
                            "cannot describe"))
    tab._refresh_layout_estimate(use_engine=True)
    assert cleared


def test_the_count_line_never_blames_a_missing_profile(
        qapp, tmp_path, monkeypatch):
    """The label is only drawn when a profile IS there, so "it runs the first
    time a profile is available" named a cause that cannot be the one. It is
    what she read straight after building hers."""
    tab = _gamut_tab(qapp, tmp_path, monkeypatch, reachable=13)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: None)
    tab._update_gamut_count_line()
    text = tab._gamut_count_lbl.text()
    assert text, "the line went blank instead of saying anything"
    assert "first time a profile is available" not in text, (
        f"the line still blames the absence of a profile it can see: {text!r}")
    assert "could not ask this profile" in text, (
        f"the line does not say what actually happened: {text!r}")
