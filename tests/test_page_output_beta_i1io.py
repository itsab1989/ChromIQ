"""THE i1iO KEEPS THE PAGE-OUTPUT BETA'S TWO VALUES ON EVERY PATH (#215, B1).

`tests/test_i1io_every_option_persists.py` walks every i1iO option through
every place it is kept, with the page-output Beta off. Its two values need the
Beta ON (the Resolution unit row is built only then) and Paper = Custom (a
typed page), so that module lists them as walked HERE, through the same paths
with the same helpers:

  (a) "Save as Defaults" and the panel the next start builds from it;
  (b) a preset file, the preset bar's Update / Reset, a named preset;
  (c) the target's own stored Create Chart state;
  and Generate hands the build what the chart records.

A page typed in pixels on the i1iO stays pixel-exact everywhere (the review's
i1iO point): the stored sides are the typed pixels, not millimetres.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_i1io_every_option_persists import (  # noqa: E402,F401
    _base, _manual_io2, _show, chart_tab)
from workflow.page_output import support as po  # noqa: E402

#: an upright i1iO sheet typed in pixels: 211.67 x 296.33 mm at 600 ppi
PX = {"w": [5000, "px"], "h": [7000, "px"], "ppi": 600}


@pytest.fixture(autouse=True)
def betas_on():
    from workflow.i1io import support as io
    before = (io._latched, po._latched)
    io.set_enabled_for_this_process(True)
    po.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        io._latched, po._latched = before


def _page_recipe():
    w, h = po.page_mm(PX, 600)
    return replace(_base(), paper=po.paper_code(w, h), dpi=600,
                   page_size=PX, tiff_res_unit="in", margins_explicit=True,
                   label_style_explicit=True)


WANT = {"page_size": PX, "tiff_res_unit": "in", "dpi": 600}


def _lost(rec):
    w, h = po.page_mm(PX, 600)
    want = dict(WANT, paper=po.paper_code(w, h))
    return {k: (getattr(rec, k), v) for k, v in want.items()
            if getattr(rec, k) != v}


def test_the_panel_shows_and_gives_back_the_page(chart_tab):
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _page_recipe())
    assert panel.paper.currentData() == "__custom__"
    assert (panel._page_px["w"].value(), panel._page_px["h"].value()) == (
        5000, 7000)
    assert _lost(panel.get_recipe()) == {}


def test_a_preset_file_and_the_preset_bar_keep_it(chart_tab):
    from workflow.layout_engine.presets import PresetStore
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _page_recipe())
    store = PresetStore()
    store.set(panel.get_recipe())
    back = PresetStore.from_dict(json.loads(json.dumps(store.to_dict())))
    (saved,) = back._presets.values()
    _show(tab, panel, _base())
    assert _lost(panel.get_recipe()) != {}
    _show(tab, panel, saved)
    assert _lost(panel.get_recipe()) == {}
    # the preset bar: Update preset, move away, Reset to preset
    tab._update_manual_preset()
    _show(tab, panel, replace(_page_recipe(), tiff_res_unit="cm",
                              page_size=None))
    assert _lost(panel.get_recipe()) != {}
    tab._reset_manual_to_preset()
    assert _lost(panel.get_recipe()) == {}


def test_a_named_preset_keeps_it(chart_tab):
    from PyQt6.QtWidgets import QApplication
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _page_recipe())
    rec = tab._pinned_layout_recipe()
    data = {"printtarg_-i": "IO2", "printtarg_-p": rec.paper,
            "layout_recipe": replace(rec, seed=None,
                                     seed_fixed=None).to_dict()}
    data = json.loads(json.dumps(data))
    _show(tab, panel, _base())
    tab._restore_user_preset(data)
    QApplication.processEvents()
    assert _lost(tab._manual_layout_panel.get_recipe()) == {}


def test_save_as_defaults_and_the_next_start_keep_it(chart_tab):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import LayoutRecipe
    tab, s, tmp = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _page_recipe())
    tab._on_save_defaults()
    stored = s.get("manual_engine_recipe")
    assert _lost(LayoutRecipe.from_dict(json.loads(json.dumps(stored)))) == {}
    s2 = AppSettings()
    s2._qs = QSettings(str(tmp / "app.ini"), QSettings.Format.IniFormat)
    tab2 = TabChart(ArgyllRunner(s2), FileManager(s2), s2)
    try:
        tab2._switch_mode("manual")
        tab2._init_manual_layout_panel()
        QApplication.processEvents()
        assert _lost(tab2._manual_layout_panel.get_recipe()) == {}
    finally:
        tab2.deleteLater()


def test_the_targets_own_state_keeps_it(chart_tab):
    from PyQt6.QtWidgets import QApplication
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _page_recipe())
    state = json.loads(json.dumps(tab._collect_ui_state()))
    _show(tab, panel, _base())
    tab._apply_ui_state(state)
    QApplication.processEvents()
    assert _lost(panel.get_recipe()) == {}


def test_generate_builds_what_the_recipe_records(chart_tab):
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _page_recipe())
    recorded = tab._current_layout_recipe().build_kwargs()
    built = tab._creator._engine_kwargs(tab._collect_params())
    own = {"project", "chart_date", "rundescription", "side_stamp"}
    diff = {k: (recorded.get(k), built.get(k))
            for k in set(recorded) | set(built)
            if k not in own and recorded.get(k) != built.get(k)}
    assert diff == {}
    assert built["page_size"] == PX and built["tiff_res_unit"] == "in"


def test_the_i1io_sheet_is_drawn_pixel_exact(tmp_path):
    """The build itself: an i1iO sheet typed in pixels has those pixels."""
    from pathlib import Path
    import tifffile
    from workflow.layout_engine.chart import build_from_recipe
    ti1 = Path(__file__).resolve().parent / "data" / "targen350_rgb.ti1"
    r = replace(_page_recipe(), seed=3, compression="none")
    res, _ = build_from_recipe(ti1, tmp_path / "io", r)
    for p in res.tiff_paths:
        with tifffile.TiffFile(str(p)) as t:
            pg = t.pages[0]
            assert (pg.imagewidth, pg.imagelength) == (5000, 7000)
            assert tuple(pg.tags["XResolution"].value) == (600, 1)
