"""The import's routing and run choice — the parts a challenge found decorative.

Three faults, all of which left the feature looking as though it worked:
  * the run picker's `currentIndexChanged` was never connected, so the choice
    on screen was ignored and EVERY import went to "a new run";
  * that new run was EMPTY, so `assess()` had no chart to compare against and
    filed anything at all, in silence;
  * the "is this file already in a project?" test looked one level up, and a
    run's own measurement lives two levels down — so ChromIQ offered to copy a
    file into another project when it was already exactly where it belonged.
"""
import pathlib
import tempfile

import pytest


@pytest.fixture()
def work():
    return pathlib.Path(tempfile.mkdtemp())


def test_project_has_all_runs_not_runs(work, qapp):
    """The selection code called `proj.runs()`, which does not exist — it
    raised into a guard and fell through to "a new run" every time."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    assert hasattr(proj, "all_runs"), "the API this depends on has moved"
    assert not hasattr(proj, "runs"), (
        "`runs` exists again — the selection code must use whichever is real")
    assert [r.id for r in proj.all_runs()] == ["run1"]


def test_a_new_run_for_an_import_carries_the_chart(work, qapp):
    """An empty run has nothing to check a measurement against, so the import
    accepted any file in silence. §I.9: the copy takes the chart, and only the
    chart."""
    from core.file_manager import Project

    proj = Project.create(work / "P", "P")
    src = proj.current_run()
    src.chart_ti2.write_text("CTI2\n\nNUMBER_OF_SETS 6\n")
    src.measurement_ti3.write_text("CTI3 someone's measurement\n")

    new = proj.duplicate_run(src, ("chart",))

    assert new.chart_ti2.is_file(), (
        "a new run with no chart cannot validate anything filed into it")
    assert not new.measurement_ti3.is_file(), "the copy carried a measurement"
    assert src.measurement_ti3.is_file(), "the source run was touched"


def test_a_runs_own_measurement_counts_as_already_in_a_project(work, qapp):
    """`<project>/runs/runN/` holds no `project.json`, so a one-level test said
    "not in a project" — and ChromIQ asked where to put a file that was already
    where it belonged, then offered to copy it into a different project."""
    from core.file_manager import Project, peek_project
    from ui.ti2_loader import _project_root_for

    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    own = run.dir / "P.ti3"
    own.write_text("CTI3\n")

    assert not peek_project(own.parent).exists, (
        "precondition: the run folder itself is not a project")
    assert _project_root_for(own, work) is not None, (
        "a run's own measurement must be recognised as inside its project")


def test_an_outside_measurement_is_still_outside(work, qapp):
    """…and the walk must not swallow the case the feature exists for."""
    from ui.ti2_loader import _project_root_for

    stray = work / "Desktop-ish" / "measured.ti3"
    stray.parent.mkdir(parents=True)
    stray.write_text("CTI3\n")
    assert _project_root_for(stray, work) is None


def test_every_format_reaches_the_same_question(qapp):
    """`.mxf` and `.txt` — the files this feature exists for — were routed by
    suffix BEFORE the question and never met it."""
    import inspect
    from ui.tabs.tab_profile import TabProfile

    src = inspect.getsource(TabProfile._on_load_ti3)
    ask = src.index("_offer_import_into_a_project")
    mxf = src.index('".mxf", ".cxf"')
    assert src.index("_convert_for_import") < ask, (
        "the conversion must happen before the question, or the question "
        "cannot read the measurement")
    assert ask < src.rindex('".mxf", ".cxf"'), (
        "the format routing still runs before the question — .mxf and .txt "
        "never reach it")


def test_the_run_picker_choice_is_connected(qapp):
    """The picker wrote into a list only if somebody wired the signal. Nobody
    did, so the selection on screen was ignored: Run 2 highlighted, Run 6
    filed."""
    import inspect
    from ui.tabs.tab_profile import TabProfile

    src = inspect.getsource(TabProfile._file_into_project)
    assert "currentIndexChanged" in src, (
        "the run picker is decorative — every import goes to a new run")
    assert "all_runs()" in src, (
        "the run is looked up with a method Project does not have")
