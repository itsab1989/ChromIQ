"""Check & Refine shows the run the bar is on, and nothing from the last one.

Three things a tester reported on 2026-09-17, all of them about this tab
showing the wrong project or none at all.

1. *"after having run Check & Refine and clicked Run Gamut Analysis, then
   opening a new ti2 file and choosing to create a new project with selected
   files as basis, then a new project was made (a new name defined), but the
   Check & Refine tab was showing the Gamut 3D plot made on a previously loaded
   project."* -- `_reset_results` cleared every stored field and left the web
   view displaying the scene it had already loaded.

2. *"even though the profile run is set to run1 and its folder has all files,
   ti1, ti2, ti3 and icc ... The ti3 and the icc file is not automatically
   loaded as default when entering Check & Refine tab. Measure and Build
   Profile tabs both loads the ti3 file for the run, if it exists, as
   default."* -- this tab took the shared controller and never subscribed to it.

3. *"When selecting Check & Refine tab, the profile bar is greyed out. When
   hovering profile run a tool-tip explains that it is not used on the Build
   Profile and Check & Refine tabs. This is not true for the Build Profile tab,
   which has the profile bar enabled. Update the tool-tip."* -- Build Profile
   was unlocked at Knut's request in beta.157 and the sentence stayed behind.
"""
import inspect

import pytest

STEM = "Check-Refine-Follows-The-Bar"


def _settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(work))
    return s, work


def _project_with_a_finished_run(work):
    """A run holding the four files the tester named."""
    from core.file_manager import Project
    proj = Project.create(work / STEM, STEM)
    run = proj.current_run()
    for ext in (".ti1", ".ti2", ".ti3", ".icc"):
        (run.dir / f"{STEM}{ext}").write_text("x", encoding="utf-8")
    return proj, run


# ------------------------------------------------ 2: it follows the bar

def test_check_and_refine_loads_the_run_it_is_pointed_at(qapp, tmp_path):
    """The ti3 and the icc of the selected run, with no browsing."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_check_refine import TabCheckRefine

    s, work = _settings(tmp_path)
    _proj, run = _project_with_a_finished_run(work)

    fm = FileManager(s)
    fm.set_target_name(STEM)
    tab = TabCheckRefine(ArgyllRunner(s), s)
    assert tab.ti3_path is None, "precondition: the tab starts empty"

    tab.set_target_controller(MeasurementTargetController(fm))

    assert tab.ti3_path == run.measurement_ti3, (
        "the run's measurement was not loaded; the tester had to browse for a "
        "file that was already sitting in the run the bar names")
    assert tab.icc_path == run.profile_icc, "the run's profile was not loaded"


def test_it_does_not_empty_itself_on_a_run_with_no_measurement(qapp, tmp_path):
    """Following the bar only ever OFFERS; it never takes something away."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_check_refine import TabCheckRefine

    s, work = _settings(tmp_path)
    proj, run = _project_with_a_finished_run(work)
    fm = FileManager(s)
    fm.set_target_name(STEM)
    tab = TabCheckRefine(ArgyllRunner(s), s)
    tab.set_target_controller(MeasurementTargetController(fm))
    assert tab.ti3_path == run.measurement_ti3

    empty = proj.new_run()           # a fresh run holds nothing
    tab._target_ctl.changed.emit()
    assert tab.ti3_path == run.measurement_ti3, (
        "moving to an empty run cleared the tab instead of leaving it be")
    assert not empty.measurement_ti3.exists()


def test_following_the_bar_never_asks_about_a_missing_profile(qapp, tmp_path):
    """`_auto_fill_icc` pops a modal when it finds nothing. Opening a project
    is not a question, so it must not be answered with a window."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_check_refine import TabCheckRefine

    s, work = _settings(tmp_path)
    proj = Project.create(work / STEM, STEM)
    run = proj.current_run()
    (run.dir / f"{STEM}.ti3").write_text("x", encoding="utf-8")   # no .icc

    asked = []
    import ui.tabs.tab_check_refine as mod
    original = mod.warn
    mod.warn = lambda *a, **k: asked.append(a)
    try:
        fm = FileManager(s)
        fm.set_target_name(STEM)
        tab = TabCheckRefine(ArgyllRunner(s), s)
        tab.set_target_controller(MeasurementTargetController(fm))
    finally:
        mod.warn = original

    assert asked == [], (
        "a modal 'Profile Not Found' was thrown at somebody who only opened a "
        "project")
    assert tab.ti3_path == run.measurement_ti3, "the measurement still loads"


def test_following_the_bar_tells_no_other_tab(qapp, tmp_path):
    """`ti3_selected` reaches Build Profile and can raise an import window.
    The bar moving is not a choice about files."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_check_refine import TabCheckRefine

    s, work = _settings(tmp_path)
    _project_with_a_finished_run(work)
    fm = FileManager(s)
    fm.set_target_name(STEM)
    tab = TabCheckRefine(ArgyllRunner(s), s)
    heard = []
    tab.ti3_selected.connect(heard.append)
    tab.set_target_controller(MeasurementTargetController(fm))
    assert heard == [], "following the bar broadcast the file to the other tabs"


def test_it_offers_nothing_for_a_calibration_or_verification_target(qapp, tmp_path):
    """Found by a challenge round on this change, not by the report.

    A calibration's measurement lives in `cal/` and a verification's in a dated
    folder, but `resolve_run(...).measurement_ti3` answers with the RUN's
    profiling measurement either way. That is a real file belonging to
    something the bar is not pointing at, and showing it would be worse than
    showing nothing.
    """
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import (RUN_TYPE_CALIBRATION,
                                           RUN_TYPE_VERIFICATION,
                                           MeasurementTargetController)
    from ui.tabs.tab_check_refine import TabCheckRefine

    for run_type in (RUN_TYPE_CALIBRATION, RUN_TYPE_VERIFICATION):
        s, work = _settings(tmp_path / str(run_type))
        _project_with_a_finished_run(work)
        fm = FileManager(s)
        fm.set_target_name(STEM)
        ctl = MeasurementTargetController(fm)
        ctl.target.run_type = run_type
        tab = TabCheckRefine(ArgyllRunner(s), s)
        tab.set_target_controller(ctl)
        assert tab.ti3_path is None, (
            f"run type {run_type!r} was offered the run's profiling "
            f"measurement {tab.ti3_path}")


# ------------------------------------------- 1: the stale 3D plot

def test_clearing_the_gamut_panel_blanks_the_shape_on_screen(qapp, tmp_path):
    """Every result field went to None while the picture stayed up.

    Asserted on the CALL rather than on pixels, because the suite has no
    WebEngine: `_show_placeholder` returns early with no view, so a pixel test
    would pass with the bug present.
    """
    from core.argyll_runner import ArgyllRunner
    from ui.gamut_panel import GamutPanel

    s, _work = _settings(tmp_path)
    panel = GamutPanel(ArgyllRunner(s), s)

    blanked = []
    panel._show_placeholder = lambda: blanked.append(True)
    panel._reset_results()
    assert blanked, (
        "the panel forgot every result except the only one the user can see: "
        "the previous project's 3D plot stayed on screen")


def test_clearing_the_panel_also_drops_the_comparison_profile(qapp, tmp_path):
    """B belongs to the project A came from."""
    from pathlib import Path

    from core.argyll_runner import ArgyllRunner
    from ui.gamut_panel import GamutPanel

    s, work = _settings(tmp_path)
    panel = GamutPanel(ArgyllRunner(s), s)
    panel._compare_path = Path(work / "old-project.icc")
    panel._compare_edit.setText(str(panel._compare_path))

    panel.set_icc_path(None)
    assert panel._compare_path is None, (
        "a new project opened with the previous project's profile still in B")
    assert panel._compare_edit.text() == ""


def test_showing_a_profile_keeps_the_comparison_the_user_chose(qapp, tmp_path):
    """Only a CLEAR drops B. While a profile is shown, B is a deliberate choice."""
    from pathlib import Path

    from core.argyll_runner import ArgyllRunner
    from ui.gamut_panel import GamutPanel

    s, work = _settings(tmp_path)
    panel = GamutPanel(ArgyllRunner(s), s)
    chosen = Path(work / "reference.icc")
    panel._compare_path = chosen
    panel.set_icc_path(Path(work / "a.icc"))
    assert panel._compare_path == chosen


# ------------------------------------------------------- 3: the tooltip

def _lock_note(tmp_path):
    """The tooltip a real bar shows when Check & Refine locks it."""
    from core.file_manager import FileManager
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)
    s, _work = _settings(tmp_path)
    bar = MeasurementTargetBar(MeasurementTargetController(FileManager(s)))
    return bar._lock_note()


def test_the_locked_bar_tooltip_does_not_claim_build_profile_is_locked(qapp, tmp_path):
    """It said so while the tester was looking at a live bar on that tab."""
    note = _lock_note(tmp_path)
    assert "Check & Refine" in note, "the tooltip stopped naming the locked tab"
    assert "Build Profile and Check & Refine" not in note, (
        "the tooltip still says the selection is unused on Build Profile, "
        "whose bar is enabled")


def test_the_tooltip_says_build_profile_is_where_you_can_change_it(qapp, tmp_path):
    """Naming it only as 'not here' would still be half the sentence."""
    note = _lock_note(tmp_path)
    changeable = note.split("changed on", 1)[1]
    assert "Build Profile" in changeable, (
        "Build Profile is missing from the list of tabs the selection can be "
        "changed on, and it is one of them")


def test_the_tooltip_says_build_profile_is_profiling_only(qapp, tmp_path):
    """The design authority's rule, and the app really does enforce it.

    Measured across all five tabs with `scripts/drive_the_bar_on_every_tab.py`:
    Build Profile is the ONLY tab where the Verification run type is disabled,
    and the only tab that leaves the profile run editable while doing so. A
    tooltip that lists Build Profile as a place the run can be changed and
    stops there would be true and still misleading.
    """
    note = _lock_note(tmp_path)
    tail = note.split("Build Profile tabs.", 1)[1]
    assert "Profiling" in tail and "verification" in tail.lower(), (
        "the tooltip does not say that Build Profile narrows the run type to "
        "Profiling, which is the rule the app enforces there")


def test_build_profile_is_the_one_tab_that_forbids_a_verification_run(qapp, tmp_path):
    """The behaviour the sentence above promises, read from the real bar."""
    from core.file_manager import FileManager
    from ui.measurement_target_bar import (RUN_TYPE_VERIFICATION,
                                           MeasurementTargetBar,
                                           MeasurementTargetController)

    s, _work = _settings(tmp_path)
    bar = MeasurementTargetBar(MeasurementTargetController(FileManager(s)))

    def verification_enabled() -> bool:
        model = bar._type_combo.model()
        for j in range(bar._type_combo.count()):
            if bar._type_combo.itemData(j) == RUN_TYPE_VERIFICATION:
                return bool(model.item(j).isEnabled())
        raise AssertionError("no Verification entry in the Run type box")

    bar.set_verification_selectable(True)       # tabs 1-3 and 5
    assert verification_enabled()
    bar.set_verification_selectable(False)      # what tab 4 asks for
    assert not verification_enabled(), (
        "Build Profile no longer forbids a verification run, so the tooltip "
        "now promises a rule the app does not keep")


def test_only_check_and_refine_locks_the_bar():
    """The behaviour the sentence has to describe, read from the one caller."""
    from ui.main_window import MainWindow

    src = inspect.getsource(MainWindow)
    i = src.index("set_locked(")
    call = src[i:i + 40]
    assert "index == 4" in call, (
        f"the bar is locked by {call!r}; tab 4 is Check & Refine and the "
        "tooltip is written for that one tab alone")
