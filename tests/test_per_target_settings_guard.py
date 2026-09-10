"""The shield that keeps a chart's values out of a run's own settings.

`_chart_imposed` records what the chart sidecar changed when a run is selected,
so the next write files the RUN's values rather than the chart's. Three ways it
went wrong, each measured on screen before being fixed, each pinned here.
"""
import json
import pathlib

import pytest

pytestmark = pytest.mark.usefixtures("qapp")


def _tab_source() -> str:
    return (pathlib.Path(__file__).resolve().parents[1]
            / "ui" / "tabs" / "tab_chart.py").read_text(encoding="utf-8")


def test_the_shield_records_which_target_it_was_taken_for():
    """A shield is released only by a widget MOVING, and loading the incoming
    run's stored value over a widget that already shows it moves nothing. The
    shield taken for the run just left then survived into the write for the run
    just entered, and substituted the previous run's numbers into this run's
    file. Measured with no edit and no build at all: picking run 2 then run 1
    moved run 1's stored patch count from 600 to run 2's 222.

    It hides whenever two runs agree on a value, which is common because two
    runs of one project often share a chart recipe, and the sanctioned
    acceptance driver gives every target deliberately different values, which
    is exactly the arrangement in which it cannot fire.
    """
    src = _tab_source()
    assert '"target": self._target_store_key()' in src, (
        "the shield no longer records whose it is"
    )
    assert 'if store_key and imposed.get("target") != store_key:' in src, (
        "the shield is no longer refused when it belongs to another target"
    )


def test_a_builds_own_write_is_not_shielded():
    """§4c D-4: a target records what it was actually used with.

    The shield exists to stop a chart's values being filed on a mere SELECTION.
    It must not reach the one write where those values genuinely are the user's,
    because they have just pressed Generate Chart. Measured before this: a run
    whose settings file had never been written recorded "A4, 0 columns, 0 rows,
    300 dpi" for a sheet that is 130x180 with 12 by 18 patches at 200 dpi. Not
    one field of the chart reached the store.
    """
    src = _tab_source()
    build_write = src.split("THE CHART THE USER JUST BUILT WINS OVER THE SHIELD", 1)
    assert len(build_write) == 2, "the build's own write is shielded again"
    after = build_write[1][:900]
    assert "self._chart_imposed = {}" in after and "save_target_settings()" in after, (
        "the shield is no longer dropped before the build's own write"
    )


def test_the_shield_episode_ends_with_the_write_it_was_taken_for():
    """Belt and braces with the scoping above: the outgoing target's shield is
    dropped after its write and before the incoming target's load, so its
    lifetime is one selection and readable as such."""
    src = _tab_source()
    assert "THE EPISODE ENDS WITH THE WRITE IT WAS TAKEN FOR" in src


def test_the_new_run_block_survives_a_preview_render(tmp_path):
    """§4a N-4 puts the settings typed for a run that does not exist yet in
    `cache/new_run.json`. Every live-preview render swept `cache/` away, so the
    block was destroyed by the act of watching the preview redraw."""
    from core.file_manager import Project
    from workflow.per_target_settings import NEW_RUN_FILENAME

    proj = Project.create(tmp_path / "p", "p")
    run = proj.new_run()
    run.cache_dir.mkdir(parents=True, exist_ok=True)
    block = run.cache_dir / NEW_RUN_FILENAME
    block.write_text(json.dumps({"kept": True}), encoding="utf-8")
    junk = run.cache_dir / "scanin-working-copy.tif"
    junk.write_bytes(b"derived")

    run.reset_chart_artefacts()

    assert block.exists(), (
        "the New-run block was deleted by the chart sweep; the settings a user "
        "typed for a run that does not exist yet are gone"
    )
    assert json.loads(block.read_text(encoding="utf-8")) == {"kept": True}
    assert not junk.exists(), "the sweep stopped deleting what it is for"


def test_a_closed_project_is_not_written_by_the_next_tab_change(tmp_path):
    """Closing a project must end every route back into it, not just one.

    Letting go of the settings store pushed the next write into the branch that
    handles a run with no store, and that branch resolves through the New-run
    SEED folder, which is still a folder inside the project just closed.
    Measured on a clean tree by a reviewer: after Close Project, changing tab
    wrote `runs/run2/cache/new_run.json` into it. Nothing was lost, because the
    content came out the same either way, but a closed project must not be
    written at all.
    """
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    proj = Project.create(tmp_path / "P", "P")
    proj.current_run().ensure_dir()
    fm.set_target_name("P")
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(MeasurementTargetController(fm))

    tab.forget_target_store()

    assert getattr(tab, "_settings_store", "unset") is None
    assert getattr(tab, "_new_run_seed_dir", "unset") is None, (
        "the seed folder still points into the project that was closed"
    )
