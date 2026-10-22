"""Check & Refine in Run type Verification (Knut's report, Basti's ruling of
2026-10-22, unified_measurement_management.md §6c-1).

Knut: in Run type Verification the tab was selectable but behaved as for
profiling. Its file fields held the profiling run's .ti3/.icc; he had to pick
the dated verification .ti3 and the profile by hand (the tool expected the
.ti3 beside the .icc); the result window offered "Guide me through
refinement", "Use as pre-conditioning" and "Install profile as is"; and the
report went to the PROFILING run's reports folder.

These tests hold the tab to the ruling, and hold the profiling run to what it
did before (proved on screen as well, before and after, pixel for pixel:
agent 15's report folder, onscreen/run_profiling_*).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

STEM = "Check-Refine-Verification"
VID = "2026-10-07_153748"


def _settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(work))
    return s, work


def _project(work, *, dated=True):
    """run1 with its profiling files and, when *dated*, one dated
    verification with a measurement (and no profile beside it, as on disk)."""
    from core.file_manager import Project
    proj = Project.create(work / STEM, STEM)
    run = proj.current_run()
    for ext in (".ti1", ".ti2", ".ti3", ".icc"):
        (run.dir / f"{STEM}{ext}").write_text("x", encoding="utf-8")
    v = run.verification(VID)
    if dated:
        v.ensure_dir()
        v.measurement_ti3.write_text("x", encoding="utf-8")
    return proj, run, v


def _tab(s, run_type="verification", vid=VID):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_check_refine import TabCheckRefine
    fm = FileManager(s)
    fm.set_target_name(STEM)
    ctl = MeasurementTargetController(fm)
    tab = TabCheckRefine(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")              # as the bar selects it
    if run_type == "verification":
        ctl.set_run_type("verification")
        if vid is not None:
            ctl.set_verification_id(vid)
    return tab, ctl


# ---- the fields follow the bar ---------------------------------------------

def test_verification_prefills_the_dated_measurement_and_the_runs_profile(
        qapp, tmp_path):
    s, work = _settings(tmp_path)
    _proj, run, v = _project(work)
    tab, _ctl = _tab(s)
    assert tab.ti3_path == v.measurement_ti3, (
        "Knut had to browse for the dated verification by hand")
    assert tab.icc_path == run.built_profile_icc(), (
        "a dated verification has no profile beside it; it checks the run's")
    assert tab._run_btn.isEnabled()


def test_the_profile_is_found_without_the_ti3_beside_it(qapp, tmp_path):
    """Browsed to under any Run type, a verification gets the run's profile
    two folders up; there is no .icc beside it."""
    s, work = _settings(tmp_path)
    _proj, run, v = _project(work)
    tab, _ctl = _tab(s, run_type="profiling")
    asked = []
    import ui.tabs.tab_check_refine as mod
    original = mod.warn
    mod.warn = lambda *a, **k: asked.append(a)
    try:
        tab._adopt_ti3(v.measurement_ti3)
    finally:
        mod.warn = original
    assert tab.icc_path == run.built_profile_icc()
    assert asked == [], "'Profile Not Found' for a profile that is there"


def test_new_verification_offers_nothing_and_takes_the_profiling_files_away(
        qapp, tmp_path):
    s, work = _settings(tmp_path)
    _proj, run, _v = _project(work, dated=False)
    tab, ctl = _tab(s, run_type="profiling")
    assert tab.ti3_path == run.measurement_ti3       # profiling: as before
    ctl.set_run_type("verification")                  # no date: "New"
    assert tab.ti3_path is None and tab.icc_path is None, (
        "the profiling run's files were still offered under Verification, "
        "which is what Knut was handed")
    assert not tab._run_btn.isEnabled()


def test_moving_between_dates_moves_the_fields(qapp, tmp_path):
    s, work = _settings(tmp_path)
    _proj, run, v = _project(work)
    v2 = run.verification("2026-10-08_090000")
    v2.ensure_dir()
    v2.measurement_ti3.write_text("x", encoding="utf-8")
    tab, ctl = _tab(s)
    assert tab.ti3_path == v.measurement_ti3
    ctl.set_verification_id(v2.id)
    assert tab.ti3_path == v2.measurement_ti3


def test_calibration_is_left_as_it_is(qapp, tmp_path):
    """A calibration makes a .cal, not a profile: nothing to follow it with
    (tool_availability.md), and the tab is not greyed out either."""
    import inspect
    from ui.tabs.tab_check_refine import TabCheckRefine
    src = inspect.getsource(TabCheckRefine._follow_the_bar)
    assert "ctl.target.is_calibration()" in src


# ---- the result window -----------------------------------------------------

class _Result:
    avg_de = 1.41
    peak_de = 65.67
    raw_log = ""
    patch_errors: list = []


def _window(tab, monkeypatch, *, strips_file=None, offered=True):
    """Build the result window and read what it shows, without running it."""
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    seen = {}

    def grab(self):
        seen["title"] = self.windowTitle()
        seen["buttons"] = [b.text() for b in self.findChildren(QPushButton)]
        seen["labels"] = " ".join(lb.text() for lb in self.findChildren(QLabel))
        return 0
    monkeypatch.setattr(QDialog, "exec", grab)
    from workflow.refine_plan import build_plan, parse_patches
    log = ("[1.000000] 2A: 0.1 0.1 0.1 -> 0.2 0.2 0.2 [0.20]\n"
           if not offered else "")
    plan = build_plan(parse_patches(log, [("C8", 65.0), ("C9", 30.0),
                                          ("A1", 0.3)] if offered else
                                    [("A1", 0.3)], None),
                      2.0, "ΔE00", None)
    tab._show_result_dialog(_Result(), plan, strips_file)
    return seen


def test_the_verification_window_offers_only_what_fits(qapp, tmp_path,
                                                         monkeypatch):
    s, work = _settings(tmp_path)
    _proj, run, v = _project(work)
    tab, _ctl = _tab(s)
    sf = v.dir / "reports" / f"Refine_Strips_1_{v.stem}.txt"
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text("C\n", encoding="utf-8")
    seen = _window(tab, monkeypatch, strips_file=sf)
    assert seen["title"] == "Profile Check Against a Verification Print"
    assert "Checked against a verification print" in seen["labels"]
    assert "never seen these readings" in seen["labels"]
    joined = " | ".join(seen["buttons"])
    assert "Pre-conditioning" not in joined, joined
    assert "Install" not in joined, joined
    assert "Guide Me Through Refinement" not in joined, joined
    assert "← Guide Me Through Re-reading These Strips" in seen["buttons"]
    assert "pre-conditioning profile" not in seen["labels"]


def test_the_profiling_window_is_unchanged(qapp, tmp_path, monkeypatch):
    s, work = _settings(tmp_path)
    _proj, run, _v = _project(work)
    tab, _ctl = _tab(s, run_type="profiling")
    assert tab.ti3_path == run.measurement_ti3
    sf = run.reports_dir / f"Refine_Strips_1_{STEM}.txt"
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text("C\n", encoding="utf-8")
    seen = _window(tab, monkeypatch, strips_file=sf)
    assert seen["title"] == "Profile Quality Assessment"
    assert "Checked against a verification print" not in seen["labels"]
    assert "← Guide Me Through Refinement" in seen["buttons"]
    assert "← Use as Pre-conditioning" in seen["buttons"]
    assert any(b.startswith("Install Profile") for b in seen["buttons"])


def test_a_verification_from_outside_the_open_project_says_how_by_hand(
        qapp, tmp_path, monkeypatch):
    """The Measure tab re-reads what the bar selects, so a verification of a
    project that is not open gets no guide, and the window says how."""
    s, work = _settings(tmp_path)
    _proj, run, v = _project(work)
    tab, ctl = _tab(s, run_type="profiling")
    tab._checking_in_place = True            # checked where it lies
    tab._ti3_path, tab._icc_path = v.measurement_ti3, run.built_profile_icc()
    seen = _window(tab, monkeypatch, strips_file=v.dir / "x.txt")
    assert not any("Guide" in b for b in seen["buttons"])
    assert "To re-read the strips listed here" in seen["labels"]
    assert "Refine / resume existing measurement (-r)" in seen["labels"]


def test_guide_points_the_bar_at_the_verification(qapp, tmp_path):
    s, work = _settings(tmp_path)
    proj, run, v = _project(work)
    tab, ctl = _tab(s, run_type="profiling")
    tab._ti3_path = v.measurement_ti3
    from ui.tabs.tab_check_refine import _verification_of
    ver = _verification_of(v.measurement_ti3)
    assert tab._can_point_the_bar_at(ver)
    tab._point_the_bar_at(ver)
    t = ctl.target
    assert (t.profile_run, t.run_type, t.verification_id) == \
        (run.id, "verification", VID)


# ---- the report ------------------------------------------------------------

def test_the_report_goes_to_the_dated_verifications_reports(qapp, tmp_path):
    from workflow.run_compliance import reports_dir_for
    s, work = _settings(tmp_path)
    _proj, run, v = _project(work)
    assert reports_dir_for(v.measurement_ti3) == v.reports_dir
    assert reports_dir_for(run.measurement_ti3) == run.reports_dir


def test_the_saved_report_says_what_it_checked(qapp, tmp_path):
    from ui.tabs.tab_check_refine import TabCheckRefine, _verification_of
    from workflow.refine_plan import build_plan, parse_patches
    s, work = _settings(tmp_path)
    _proj, _run, v = _project(work)
    plan = build_plan(parse_patches("", [("A1", 0.3)], None), 2.0, "ΔE00",
                      None)
    text = TabCheckRefine._report_summary_text(
        _Result(), plan, _verification_of(v.measurement_ti3))
    assert "Checked against a verification print" in text
    plain = TabCheckRefine._report_summary_text(_Result(), plan)
    assert "verification print" not in plain


# ---- the guide's re-read, on the Measure tab --------------------------------

def test_the_measure_tab_finds_the_dates_own_refine_list():
    """The shared verification chart sits at verifications/, but a date's
    strips worth re-reading are in that date's own reports/ (driven on
    screen: strips ['C'] armed, re-read into the same date)."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._update_resume_availability)
    assert "_newest_refine(reports_dir_for(ti3))" in src


def test_the_reread_window_of_a_verification_never_offers_build_profile(
        qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._strip_list = ["C"]
    seen = {}

    def grab(self):
        seen["buttons"] = [b.text() for b in self.findChildren(QPushButton)]
        seen["labels"] = " ".join(lb.text() for lb in self.findChildren(QLabel))
        return 0
    monkeypatch.setattr(QDialog, "exec", grab)
    tab._show_verification_reread_done()
    assert seen["buttons"] == ["Continue Measuring Manually", "Finish"]
    assert "The new readings are saved when you finish" in seen["labels"]
    assert "Build the profile again" not in seen["labels"]
    # Nothing is saved while this window is open (the reviewer's finding):
    # the text must not claim the measurement is already up to date.
    assert "up to date" not in seen["labels"]
    assert "They are not saved yet" in seen["labels"]
    assert "move between strips" in seen["labels"]
    tab.deleteLater()


def test_a_reread_patch_by_patch_says_patches_not_strips(qapp, monkeypatch):
    """The opening line counts patches when the guide went patch by patch, so
    the text under it says patches too (M-REFINE-VERIFY-DONE-PATCHES), as the
    profiling window does."""
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._strip_list = ["C"]
    tab._guided_patch_list = ["C8", "C9", "D2"]
    seen = {}

    def grab(self):
        seen["buttons"] = [b.text() for b in self.findChildren(QPushButton)]
        seen["labels"] = " ".join(lb.text() for lb in self.findChildren(QLabel))
        return 0
    monkeypatch.setattr(QDialog, "exec", grab)
    tab._show_verification_reread_done()
    labels = seen["labels"]
    assert seen["buttons"] == ["Continue Measuring Manually", "Finish"]
    assert "All 3 patches have been re-measured successfully." in labels
    assert "The patches you read again" in labels
    assert "move between patches" in labels
    assert "click a patch in the preview" in labels
    assert "strip" not in labels.lower()
    tab.deleteLater()
