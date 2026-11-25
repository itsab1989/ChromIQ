"""A SHEET LARGER THAN THE TABLE IS KEPT LIKE ANY PAPER, AND OFF CHANGES NOTHING (step 9).

Guided and Manual, presets, Save as Defaults, the target's own state: the sheet comes back, the
division never goes along (it is worked out at Generate and stored with the chart only). With the
Beta off, or for another instrument, none of the code for pieces is even loaded.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_i1io_every_option_persists import (  # noqa: F401  (fixtures)
    _manual_io2, chart_tab)
from workflow.i1io import support
from workflow.layout_engine.presets import LayoutRecipe, default_recipe

ROOT = Path(__file__).resolve().parent.parent
A3 = "v1;sheet=297x420;piece=210x297;turn=1;at=0,0/0,210;cut_x=;cut_y=210"
PAPERS = ["A3", "A2", "11x17", "420x297", "300x500"]


@pytest.fixture(autouse=True)
def i1io_on():
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _show(tab, panel, paper):
    from PyQt6.QtWidgets import QApplication
    # (a recipe as a chart of that sheet gives it: its division must not stick)
    panel.set_recipe(replace(default_recipe("IO2", paper), i1io_pieces=A3
                             if paper == "A3" else ""))
    QApplication.processEvents()


def _kept(recipe, paper):
    assert recipe.instrument == "IO2" and recipe.paper == paper
    assert recipe.i1io_pieces == "" and recipe.i1io_limits == 2


@pytest.mark.parametrize("paper", PAPERS)
def test_manual_keeps_the_sheet_and_never_the_division(chart_tab, paper):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import PresetStore
    tab, s, tmp = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, paper)
    _kept(panel.get_recipe(), paper)
    # a preset of the layout store, through its file
    store = PresetStore()
    store.set(panel.get_recipe())
    (back,) = PresetStore.from_dict(
        json.loads(json.dumps(store.to_dict())))._presets.values()
    _kept(back, paper)
    # the target's own state
    state = json.loads(json.dumps(tab._collect_ui_state()))
    _show(tab, panel, "A4")
    tab._apply_ui_state(state)
    QApplication.processEvents()
    _kept(tab._manual_layout_panel.get_recipe(), paper)
    # a named preset
    data = json.loads(json.dumps({
        "printtarg_-i": "IO2", "printtarg_-p": paper,
        "layout_recipe": replace(tab._pinned_layout_recipe(), seed=None,
                                 seed_fixed=None).to_dict()}))
    assert "i1io_pieces" not in data["layout_recipe"]
    _show(tab, panel, "Letter")
    tab._restore_user_preset(data)
    QApplication.processEvents()
    _kept(tab._manual_layout_panel.get_recipe(), paper)
    # Save as Defaults and the next start
    tab._on_save_defaults()
    stored = json.loads(json.dumps(s.get("manual_engine_recipe")))
    assert "i1io_pieces" not in stored
    _kept(LayoutRecipe.from_dict(stored), paper)
    s2 = AppSettings()
    s2._qs = QSettings(str(tmp / "app.ini"), QSettings.Format.IniFormat)
    tab2 = TabChart(ArgyllRunner(s2), FileManager(s2), s2)
    try:
        tab2._switch_mode("manual")
        tab2._init_manual_layout_panel()
        QApplication.processEvents()
        _kept(tab2._manual_layout_panel.get_recipe(), paper)
    finally:
        tab2.deleteLater()


@pytest.mark.parametrize("paper", ["A3", "A2", "11x17", "329x483"])
def test_guided_keeps_the_sheet_and_the_number_of_sheets(chart_tab, paper):
    from PyQt6.QtWidgets import QApplication
    tab, s, _t = chart_tab
    tab._switch_mode("guided")
    tab._shared_set("guided", "instrument", "IO2")
    i = tab._instr_combo.findData("IO2")
    tab._instr_combo.activated.emit(i)
    QApplication.processEvents()
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData(paper))
    tab._pages_spin.setValue(3)
    state = json.loads(json.dumps(tab._collect_ui_state()))
    tab._on_save_defaults()
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    tab._pages_spin.setValue(1)
    tab._apply_ui_state(state)
    QApplication.processEvents()
    assert tab._instr_combo.currentData() == "IO2"
    assert tab._paper_combo.currentData() == paper
    assert tab._pages_spin.value() == 3
    assert tab._pages_row_lbl.text() == "Number of sheets:"
    assert "i1io_pieces" not in json.dumps(state.get("guided", {}))


def test_another_instrument_after_it_has_a_whole_sheet(chart_tab):
    """A3 of the i1iO, then the i1Pro: the same paper, one page, "Pages"."""
    from PyQt6.QtWidgets import QApplication
    from workflow.layout_engine import papers
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, "A3")
    assert panel._pages_lbl.text() == "Sheets:"
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    QApplication.processEvents()
    r = panel.get_recipe()
    assert r.instrument == "i1" and r.i1io_pieces == ""
    assert papers.piece_mm_of(r) == papers.dimensions_mm(r.paper)
    assert panel._pages_lbl.text() == "Pages:"
    assert not panel._i1io_pieces_note.isVisibleTo(panel)


CHILD = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1]); out = Path(sys.argv[2])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from workflow.i1io import support
support.set_enabled_for_this_process(False)
from tests.test_chart_creator_engine import (ChartParams, _EngineRunner, _EngineSettings,
                                             _MockFileManager, _real_ti1)
from workflow.chart_creator import ChartCreator
c = ChartCreator(_EngineRunner(), _MockFileManager(out / "p"), _EngineSettings())
_real_ti1(out / "in.ti1", 60)
done = []
c.load_ti1_and_generate_preview(out / "in.ti1", ChartParams(instrument="i1", paper="A3",
                                tiff_dpi=72), on_line=lambda l: None, on_finish=done.append)
pages = done[0]
from ui.tiff_preview import TiffPreview
pv = TiffPreview(); pv.load_tiff(list(pages))
from workflow import overhang as O, printer_edges as E, chart_inks as I
O.instrument_of(pages[0]); O.helper_markers(pages[0]); O.content_box(pages[0])
E.losses(pages[0], 0, E.Edges(3, 3, 3, 3), (297.0, 420.0)); E._page_key(pages[0], 0)
I.plan_for_file(pages[0])
from core.settings import AppSettings
from PyQt6.QtCore import QSettings
s = AppSettings(); s._qs = QSettings(str(out / "s.ini"), QSettings.Format.IniFormat)
from ui.tabs.tab_print import TabPrint
t = TabPrint(s); t._printers_loaded = True; t.load_tiffs(list(pages))
assert t._tiff_pages == list(pages) and t._print_all_btn.isEnabled()
print(json.dumps(sorted(m for m in sys.modules if m.startswith("workflow.i1io"))))
'''


def test_with_the_beta_off_no_code_for_pieces_is_loaded(tmp_path):
    """Another instrument's A3 chart generated, shown, judged and put into Print with the Beta off:
    of the i1iO only the switch is loaded."""
    r = subprocess.run([sys.executable, "-c", CHILD, str(ROOT), str(tmp_path)],
                       capture_output=True, text=True, encoding="utf-8", timeout=240, cwd=ROOT,
                       env={**os.environ,
                            "CHROMIQ_SETTINGS_FILE": str(tmp_path / "x.ini")})
    assert r.returncode == 0, r.stderr[-1500:]
    loaded = json.loads(r.stdout.strip().splitlines()[-1])
    assert not {m for m in loaded if m.rsplit(".", 1)[-1] in
                ("pieces", "sheets", "chart", "table_facts")}, loaded


def test_a_layout_of_an_earlier_version_on_a_large_sheet(tmp_path):
    """Without the marker nothing is divided: refused as it was, in the panel and at Generate; laid
    out again by today's panel it is divided."""
    from tests.test_i1io_chart import _ti1
    from workflow.i1io import chart as C
    from workflow.layout_engine import chart, papers
    d = default_recipe("IO2", "A3").to_dict()
    d.pop("i1io_limits")
    old = LayoutRecipe.from_dict(d)
    assert not papers.is_divided(old)
    with pytest.raises(C.I1ioSheetRefused):
        chart.build_chart(_ti1(tmp_path / "c.ti1", 60), tmp_path / "c",
                          **{**old.build_kwargs(), "dpi": 72})
    assert papers.is_divided(replace(old, i1io_limits=2))
