"""Two owner decisions on the Create Chart presets list (Basti, 2026-11-14,
agreed to the questions of the small-fixes round):

Q5. Picking the SAVED preset that is already showing loads it again when the
    screen differs from it: its margins, paper and the rest come back.
    Picking it when nothing differs, and picking "none" again, change
    nothing (#175 round 8 kept those no-ops; built-in presets re-apply on
    every pick, as that ruling has it, and are not touched here).
Q6. Choosing "none" takes the preset away and leaves the chosen instrument
    alone: Guided, the hidden printtarg instrument row and the layout panel
    agree afterwards.
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


def _pump(qapp, n=10):
    for _ in range(n):
        qapp.processEvents()


def _choose_instr(qapp, tab, code):
    p = tab._manual_layout_panel
    i = p.instr.findData(code)
    p.instr.setCurrentIndex(i)
    p.instr.activated.emit(i)
    _pump(qapp)


def _save(qapp, tab, name):
    presets = tab._load_presets_from_settings()
    presets[name] = tab._preset_capture()
    tab._save_presets_to_settings(presets)
    tab._populate_preset_combo(presets, select_name=name)
    _pump(qapp)
    return tab._preset_combo.findData(name)


def _pick(qapp, tab, index):
    tab._preset_combo.setCurrentIndex(index)
    tab._preset_combo.activated.emit(index)
    _pump(qapp, 20)


def _margins(p):
    return {k: p.margins[k].value() for k in ("t", "r", "b", "l")}


@pytest.mark.parametrize("code", ["i1", "p3", "CM", "SS", "CR30"])
def test_q5_the_saved_preset_picked_again_loads_again_when_the_screen_differs(
        qapp, tab, code):
    _choose_instr(qapp, tab, code)
    p = tab._manual_layout_panel
    if p.use_instr_margins.isChecked() and p.use_instr_margins.isEnabled():
        p.use_instr_margins.click()
    p.paper.setCurrentIndex(p.paper.findData("Letter"))
    for k, v in (("t", 12.0), ("r", 10.0), ("b", 14.0), ("l", 30.0)):
        p.margins[k].setValue(v)
    _pump(qapp)
    saved = (_margins(p), p.selection()[1])
    idx = _save(qapp, tab, f"keep-{code}")
    _pick(qapp, tab, idx)                 # it is the one showing now
    p.paper.setCurrentIndex(p.paper.findData("A4"))
    for k, v in (("t", 17.0), ("r", 20.0), ("b", 21.0), ("l", 35.0)):
        p.margins[k].setValue(v)
    _pump(qapp)
    assert tab._screen_differs_from_saved_preset(idx)
    _pick(qapp, tab, idx)                 # the same entry again
    assert (_margins(p), p.selection()[1]) == saved, "not loaded again"
    assert not tab._screen_differs_from_saved_preset(idx)


def test_q5_no_reload_when_nothing_differs_and_none_stays_a_no_op(
        qapp, tab, monkeypatch):
    _choose_instr(qapp, tab, "i1")
    idx = _save(qapp, tab, "same")
    _pick(qapp, tab, idx)
    calls = []
    real = tab._on_preset_selected
    monkeypatch.setattr(tab, "_on_preset_selected",
                        lambda i: calls.append(i) or real(i))
    tab._preset_combo.activated.emit(idx)
    _pump(qapp)
    assert calls == [], "a preset that matches the screen was loaded again"
    _pick(qapp, tab, 0)                    # "none"
    calls.clear()
    tab._manual_layout_panel.margins["t"].setValue(33.0)
    tab._preset_combo.activated.emit(0)     # "none" again
    _pump(qapp)
    assert calls == [], '"none" picked again did something'


@pytest.mark.parametrize("code", ["i1", "p3", "CM", "SS", "CR30"])
def test_q6_none_leaves_the_instrument_alone(qapp, tab, code):
    _choose_instr(qapp, tab, code)
    idx = _save(qapp, tab, f"six-{code}")
    _pick(qapp, tab, idx)
    _pick(qapp, tab, 0)                    # "none"
    assert tab._preset_combo.currentIndex() == 0
    assert tab._manual_layout_panel.instr.currentData() == code
    assert tab._manual_instr_pw.get_raw_value() == code
    assert tab._instr_combo.currentData() == code, "Guided disagrees"
