"""#130 (Knut, 2026-07-27): "Restore Used Chart" must give back the SAME chart.

The stored copy holds no page images — the chart's layout recipe can redraw
them — so a restore is only right if redrawing reproduces the sheet that was
measured, patch for patch. Two things decide that:

* the **seed** the patches were shuffled with. The recipe records what the user
  asked for, and "draw a fresh one each time" is written there as no seed at
  all; the number actually drawn is recorded one level up, beside the recipe.
  Rebuilding from the recipe alone therefore reshuffled the chart — Knut's
  "manual Generate Chart produced a different chart".
* the **measurement**, which must not be moved aside by the rebuild: the
  restored chart is precisely the chart that measurement was taken with.

Knut asked for this to be verified by tests, so both are asserted here — on the
real restore path, not on a stand-in.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager, Project   # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


RECIPE = {
    "instrument": "CM", "paper": "A4", "dpi": 300,
    "randomize": True, "seed": None,          # "draw a fresh one each build"
    "patch_w_mm": 8.0, "patch_h_mm": 8.0,
}


def _sidecar(seed_actually_used: int) -> str:
    return json.dumps({"layout": {"engine": "chromiq", "recipe": dict(RECIPE),
                                  "seed": seed_actually_used,
                                  "patches": [{"loc": "A1", "page": 0}]}})


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


# ---- the seed --------------------------------------------------------------
def test_the_seed_the_chart_was_built_with_is_what_comes_back(qapp, tmp_path):
    """Not the recipe's "no seed" — the number the build actually drew."""
    tab = _tab(tmp_path)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 240\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    ti2.with_suffix(".channels.json").write_text(_sidecar(987654), encoding="utf-8")

    assert tab._restore_chart_settings(ti2) is True
    assert tab._manual_layout_panel.get_recipe().seed == 987654


def test_a_chart_built_from_a_fixed_seed_keeps_that_seed(qapp, tmp_path):
    """The two agree in this case, and the answer must not change."""
    tab = _tab(tmp_path)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 240\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    doc = json.loads(_sidecar(4242))
    doc["layout"]["recipe"]["seed"] = 4242
    ti2.with_suffix(".channels.json").write_text(json.dumps(doc), encoding="utf-8")

    tab._restore_chart_settings(ti2)
    assert tab._manual_layout_panel.get_recipe().seed == 4242


def test_a_chart_that_recorded_no_seed_is_left_as_it_is(qapp, tmp_path):
    """Charts older than the seed record: nothing to reproduce from, and the
    panel must not invent one."""
    tab = _tab(tmp_path)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 240\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    doc = json.loads(_sidecar(1))
    doc["layout"].pop("seed")
    ti2.with_suffix(".channels.json").write_text(json.dumps(doc), encoding="utf-8")

    tab._restore_chart_settings(ti2)
    assert tab._manual_layout_panel.get_recipe().seed is None


def test_the_same_seed_produces_the_same_patch_order(tmp_path):
    """The reason the seed matters at all, asserted on the shuffle itself."""
    from workflow.layout_engine.permutation import location_permutation
    n = 240
    assert location_permutation(n, 987654) == location_permutation(n, 987654)
    assert location_permutation(n, 987654) != location_permutation(n, 987655)


# ---- the measurement -------------------------------------------------------
def _run_with_a_measurement(tmp_path):
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    proj = Project.create(root / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    s = run.stem
    (run.dir / f"{s}.ti1").write_text("CTI1", encoding="utf-8")
    (run.dir / f"{s}.ti2").write_text("CTI2", encoding="utf-8")
    (run.dir / f"{s}.ti3").write_text("MEASUREMENT", encoding="utf-8")
    (run.dir / f"{s}.icc").write_bytes(b"PROFILE")
    return run


def test_redrawing_a_restored_chart_leaves_the_measurement_alone(tmp_path):
    """The whole point of Restore Used Chart: this measurement was taken with
    this chart. Rebuilding its pages must not archive it."""
    run = _run_with_a_measurement(tmp_path)

    run.reset_chart_artefacts(keep_results=True)

    assert (run.dir / f"{run.stem}.ti3").read_text(encoding="utf-8") == "MEASUREMENT"
    assert (run.dir / f"{run.stem}.icc").exists()
    assert not run.old_dir.exists(), "nothing should have been archived"


def test_a_normal_chart_regeneration_still_archives_the_results(tmp_path):
    """Knut's own ruling stands for every other build: a new chart no longer
    matches the old measurement, so it is set aside — never deleted."""
    run = _run_with_a_measurement(tmp_path)

    run.reset_chart_artefacts()

    assert not (run.dir / f"{run.stem}.ti3").exists()
    archived = list(run.old_dir.rglob("*.ti3"))
    assert archived and archived[0].read_text(encoding="utf-8") == "MEASUREMENT"


def test_the_chart_files_go_either_way(tmp_path):
    """They are about to be rebuilt from the same recipe, so they are not worth
    keeping — in both modes."""
    run = _run_with_a_measurement(tmp_path)
    run.reset_chart_artefacts(keep_results=True)
    assert not (run.dir / f"{run.stem}.ti2").exists()


def test_the_user_is_told_when_results_are_moved_aside(tmp_path):
    """"Silently moved the .ti3 to old/" was the complaint — the move is right,
    the silence was not."""
    run = _run_with_a_measurement(tmp_path)
    from workflow.chart_creator import ChartCreator
    lines = []

    ChartCreator._announce_result_archive(None, run, lines.append, False)

    assert lines and "old" in lines[0]
    assert "deleted" in lines[0], "say plainly that nothing is lost"


def test_a_restore_rebuild_says_nothing_because_nothing_moves(tmp_path):
    run = _run_with_a_measurement(tmp_path)
    from workflow.chart_creator import ChartCreator
    lines = []
    ChartCreator._announce_result_archive(None, run, lines.append, True)
    assert lines == []


def test_a_run_with_no_results_says_nothing(tmp_path):
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    run = Project.create(root / "Q", "Q").current_run(); run.ensure_dir()
    from workflow.chart_creator import ChartCreator
    lines = []
    ChartCreator._announce_result_archive(None, run, lines.append, False)
    assert lines == []


# ---- both run types can be rebuilt ----------------------------------------
def test_the_rebuild_is_not_limited_to_verification_runs():
    """Profiling runs kept a copy from beta.42 on, but nothing redrew their
    pages afterwards — the restore left the preview empty (Knut)."""
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart.rebuild_verification_pages)
    assert "if ctl is None:" in src, \
        "a profiling target must no longer be turned away"
    assert "run.chart_ti1" in src and "run.verify_chart_ti1" in src
    assert "keep_results=True" in src
