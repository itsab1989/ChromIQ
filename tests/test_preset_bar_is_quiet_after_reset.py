"""The Manual layout preset bar says "modified" only when the layout differs
(2026-11-14).

Driven on screen before the fix (small-fixes `runs/d45`): for the i1Pro, the
i1Pro 3, the ColorMunki, the SpectroScan and the CR30 the bar's "Reset to
preset" stayed lit right after pressing it, because the panel and the stored
preset write the same layout in two spellings: `area_ratio` 0 ("square") as
1.0, `clip_content_when_on` "" ("the notes box") as "notes", a stale
`spacer_on` beside spacer mode "none", and the four margins with "Use
instrument margins" ticked (the panel shows the instrument's minimums; the
factory preset holds 6 mm it never uses).
"""
from __future__ import annotations

import pytest


@pytest.fixture
def tab(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "w"))
    s.set("restore_last_session", False)
    s.set("session_project", "")
    s.set("auto_update_preview", False)
    s.set("use_chromiq_layout_engine", True)
    w = MainWindow(s)
    w.show()
    for _ in range(10):
        qapp.processEvents()
    t = w._tab_chart
    t._user_switch_mode("manual")
    for _ in range(10):
        qapp.processEvents()
    yield t
    w.close()


def _choose(qapp, tab, code):
    p = tab._manual_layout_panel
    i = p.instr.findData(code)
    assert i >= 0, code
    p.instr.setCurrentIndex(i)
    p.instr.activated.emit(i)
    for _ in range(10):
        qapp.processEvents()


@pytest.mark.parametrize("code", ["i1", "p3", "CM", "SS", "CR30"])
def test_after_reset_the_bar_is_not_modified(qapp, tab, code):
    _choose(qapp, tab, code)
    tab._reset_manual_to_preset()
    for _ in range(10):
        qapp.processEvents()
    summary, modified = tab._layout_preset_status()
    assert not modified, (code, summary)


def test_a_real_change_still_lights_it(qapp, tab):
    _choose(qapp, tab, "i1")
    tab._reset_manual_to_preset()
    p = tab._manual_layout_panel
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.click()
    for _ in range(5):
        qapp.processEvents()
    p.margins["t"].setValue(p.margins["t"].value() + 3)
    for _ in range(5):
        qapp.processEvents()
    assert tab._layout_preset_status()[1]


def test_the_spellings_compare_equal_and_real_values_do_not(tab):
    from dataclasses import replace
    from workflow.layout_engine.presets import LayoutRecipe
    a = LayoutRecipe(instrument="i1", paper="A4")
    b = replace(a, area_ratio=1.0, clip_content_when_on="notes",
                margin_top=a.margin_top + 20)
    assert a.use_instrument_margins is True
    assert tab._layout_recipe_values(a) == tab._layout_recipe_values(b)
    c = replace(a, use_instrument_margins=False)
    d = replace(c, margin_top=c.margin_top + 20)
    assert tab._layout_recipe_values(c) != tab._layout_recipe_values(d)
    assert (tab._layout_recipe_values(replace(a, area_ratio=1.5))
            != tab._layout_recipe_values(a))
