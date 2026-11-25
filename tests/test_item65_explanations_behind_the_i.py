"""Item 65 (Basti, 25 Nov 2026): "the info text belongs behind the tooltip
icons / the pop up windows". The Compact note, the pieces note under the paper
(Guided and Manual) and the printing notes of the Print Chart tab are behind
an (i); in the section stays only what is to be done at that moment."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                       # noqa: E402

from tests.test_i1io_print_pieces import build, tab      # noqa: E402,F401
from workflow.i1io import sheets as S                    # noqa: E402


@pytest.fixture(autouse=True)
def _beta_on(monkeypatch):
    from workflow.i1io import support
    monkeypatch.setattr(support, "_latched", True)


@pytest.fixture
def chart_tab(qtbot, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(t)
    t.show()
    return t


def _guided(t, instrument, paper):
    t._switch_mode("guided")
    for box, value in ((t._instr_combo, instrument), (t._paper_combo, paper)):
        i = box.findData(value)
        box.setCurrentIndex(i)
        box.activated.emit(i)
    t._update_patch_count()


def test_guided_says_compact_and_pieces_only_behind_their_i(chart_tab):
    t = chart_tab
    _guided(t, "IO2", "A3")
    t._set_guided_i1io_layout("compact")
    t._guided_i1io_layout_changed()
    for label in (t._i1io_layout_note, t._i1io_pieces_note):
        assert not label.isVisibleTo(t)
    assert "simulated table only" in t._paper_tip.dialog_body()
    assert t._paper_tip.dialog_body().startswith("1 sheet, 2 pieces")
    assert t._i1io_layout_tooltip.dialog_body().startswith("Compact:")
    _guided(t, "IO2", "A4")
    t._set_guided_i1io_layout("standard")
    t._guided_i1io_layout_changed()
    assert not t._paper_tip.live_note()
    assert not t._i1io_layout_tooltip.live_note()


def test_manual_says_them_behind_its_i_too(chart_tab):
    t = chart_tab
    t._switch_mode("manual")
    t._init_manual_layout_panel()
    p = t._manual_layout_panel
    k = p.instr.findData("IO2")
    p.instr.setCurrentIndex(k)
    p.instr.activated.emit(k)
    k = p.paper.findData("A3")
    p.paper.setCurrentIndex(k)
    p._show_i1io_pieces()
    assert not p._i1io_pieces_note.isVisibleTo(p)
    assert "simulated table only" in p._paper_tip.dialog_body()


@pytest.mark.parametrize("paper,n,line", [
    ("A3", 1100, "Print this sheet at 100 %, without scaling, and cut it along "
                 "the grey lines into its pieces."),
    ("A4", 100, "Print this page as it is, then lay it on the table a quarter "
                "turn clockwise.")])
def test_print_chart_says_one_line_and_the_rest_behind_its_i(
        tab, tmp_path, paper, n, line):  # noqa: F811
    r = build(tmp_path, paper=paper, n=n)
    if paper == "A3":
        S.ensure(r.ti2_path)
    tab.show()
    tab.load_tiffs(list(r.tiff_paths))
    assert tab._i1io_load_lbl.text() == line
    assert tab._i1io_load_tip.isVisibleTo(tab)
    whole = tab._i1io_load_tip.dialog_body()
    assert len(whole) > 2 * len(line)
    assert ("cut along the grey lines" in whole) is (paper == "A3")
    assert tab._i1io_load_text() == whole
