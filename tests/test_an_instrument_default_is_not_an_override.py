"""An instrument default may set a value nobody chose, and may not overwrite one
they did — whether they chose it by hand or by loading a preset.

Knut, 4.1.5-beta.5: *"Loaded a colormunki preset, 84 patches. Then changed
instrument to CR30. The Create Layout parameter then changed from 'Prioritise
patch area…' to 'Prioritise patch size...'. Generate Chart then changed
appearance (much smaller patches)..."*

He was not describing a bug in the CR30 rule — the rule is right (#159: a CR30 is
aimed by hand through a 4 mm aperture, so the patch size must not float with the
paper) — he was describing it firing over an answer somebody had already given.
Basti's ruling, 2026-09-02: keep the rule, do not apply it to a preset. *"The
default exists to help somebody BUILDING a CR30 chart from scratch… Somebody who
has just loaded a preset has already said what they want, by name, two clicks
ago."*

`_on_instr_changed` carries FOUR such defaults, all with the same blind spot, so
this is one fix and not four:

  * CR30      → layout mode `patch_first`, spacers `none`
  * SpectroScan → layout mode `patch_first`, area method `by_grid`
  * anything else → spacers back on when they read `none`
  * i1 / i1Pro3 → clip-band content `notes` when it reads `off`

Each is exercised here in both directions: it still fires for somebody building
from scratch, and it no longer fires over an answer. Everything is driven
through the REAL `LayoutOptionsPanel` and its real signal wiring — the
instrument combo is changed the way a person changes it, and the assertions read
the real `get_recipe()` the builder consumes.
"""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import instruments, papers, presets
from workflow.layout_engine.presets import LayoutRecipe, default_recipe

CM_84P = "__chromiq_knut_cm_a4_84p_1page_portrait_w26_0mm_fast_reading_speed_hand_held__"


@pytest.fixture
def panel(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _pick(panel, code):
    """Change the instrument the way a person does: pick the row in the combo."""
    i = panel.instr.findData(code)
    assert i >= 0, f"{code} is not offered in the instrument combo"
    panel.instr.setCurrentIndex(i)


def _set_combo(combo, data):
    """Turn a knob the way a person does.

    A click in a QComboBox emits `activated` and then (only when the row really
    changed) `currentIndexChanged`. Re-picking the row that is already ticked
    emits `activated` alone, which is why the panel listens to both — so the
    helper reproduces both rather than the convenient one.
    """
    i = combo.findData(data)
    assert i >= 0, f"{data!r} is not offered"
    combo.setCurrentIndex(i)
    combo.activated.emit(i)


def _patch_mm(r: LayoutRecipe, instrument: str, paper: str = "A4"):
    g = instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": instrument, "paper": paper})
    return round(g.pwid, 2), round(g.plen, 2)


# ---------------------------------------------------------------------------
# 1. From scratch — every default must survive, or the fix has broken the app
#    for the person it was written for.
# ---------------------------------------------------------------------------
def test_from_scratch_a_cr30_still_gets_patch_first_and_no_spacers(panel):
    _pick(panel, "i1")
    _pick(panel, "CR30")
    r = panel.get_recipe()
    assert r.layout_mode == "patch_first"
    assert r.spacer_mode == "none" and r.spacer_on is False


def test_from_scratch_a_spectroscan_still_gets_patch_first_by_grid(panel):
    _pick(panel, "SS")
    r = panel.get_recipe()
    assert (r.layout_mode, r.area_method) == ("patch_first", "by_grid")


def test_from_scratch_the_cr30_leftover_spacers_are_still_restored(panel):
    """The restore exists to stop a genuinely bad chart — an i1Pro finds the
    edge of each patch BY the spacer. Somebody who visited a CR30 and came back
    without a preset in sight must still get their spacers."""
    _pick(panel, "i1")
    _pick(panel, "CR30")
    assert panel.get_recipe().spacer_mode == "none"
    _pick(panel, "i1")
    assert panel.get_recipe().spacer_mode != "none", (
        "an i1 chart was left with no spacers to find its strips by")


def test_from_scratch_an_i1_still_gets_a_clip_band_with_something_in_it(panel):
    _pick(panel, "CM")            # no clip band → content "off"
    assert panel.get_recipe().clip_content_mode == "off"
    _pick(panel, "i1")
    assert panel.get_recipe().clip_content_mode == "notes"


def test_a_recipe_that_owns_nothing_is_the_apps_own_starting_point(panel):
    """`default_recipe` and the factory `PresetStore` ARE the default. Seeding
    the panel from one must NOT count as somebody's answer — that is the path
    `_init_manual_layout_panel` takes every time Create Chart opens."""
    panel.set_recipe(default_recipe("CM", "A4"))
    _pick(panel, "CR30")
    assert panel.get_recipe().layout_mode == "patch_first", (
        "seeding the panel with the app's own default silenced the instrument "
        "default that seeding is supposed to leave alone")


# ---------------------------------------------------------------------------
# 2. Knut's journey — a preset, then a change of instrument
# ---------------------------------------------------------------------------
def _preset_recipe(key: str = CM_84P) -> LayoutRecipe:
    """The REAL bundled recipe of the built-in Knut loaded, marked the way
    `_seed_knut_preset` marks it."""
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    p = KNUT_PRESETS_BY_KEY[key]
    return replace(LayoutRecipe.from_dict(p.layout_recipe),
                   label_style_explicit=True, layout_explicit=True)


def test_the_bundled_84p_preset_is_the_chart_knut_described():
    r = _preset_recipe()
    assert (r.instrument, r.paper) == ("CM", "A4")
    assert (r.layout_mode, r.area_method) == ("area_first", "by_grid")
    assert (r.area_cols, r.area_rows) == (7, 12)
    assert _patch_mm(r, "CM") == (25.71, 19.11), \
        "the preset's own patch size, measured on this branch"


def test_knuts_journey_the_preset_keeps_its_layout_across_the_instrument(panel):
    panel.set_recipe(_preset_recipe())
    _pick(panel, "CR30")
    r = panel.get_recipe()
    assert r.layout_mode == "area_first", (
        "'Prioritise patch size' was forced over a preset that asked for "
        "'Prioritise chart area' — exactly Knut's report")
    assert (r.area_cols, r.area_rows) == (7, 12)
    assert r.spacer_mode == "colored", "the preset's spacers were turned off"


def test_knuts_journey_the_built_chart_no_longer_shrinks(panel):
    """The report was about the CHART, not the combo: 84 patches at ~25.7 mm
    became 266 at 12.0 mm. Measured through the same geometry the builder uses."""
    from workflow.layout_engine import geometry
    panel.set_recipe(_preset_recipe())
    _pick(panel, "CR30")
    r = panel.get_recipe()
    w, h = papers.dimensions_mm("A4")
    g = instruments.geom_from_build_kwargs(
        {**r.build_kwargs(), "instrument": "CR30", "paper": "A4"})
    assert geometry.compute(g, w, h, 84).patches_per_page == 84, \
        "the sheet was re-laid out to 266 hand-aimed patches"
    assert _patch_mm(r, "CR30") == (24.51, 19.11), \
        "the preset's patches were shrunk to the CR30's ruled 12.0 mm"


def test_a_preset_that_asked_for_no_spacers_keeps_them_off(panel):
    """The mirror image, and the one most likely to bite: switching AWAY from a
    CR30 turned a deliberately spacer-less preset's spacers back on."""
    panel.set_recipe(replace(_preset_recipe(), spacer_mode="none",
                             spacer_on=False))
    _pick(panel, "i1")
    assert panel.get_recipe().spacer_mode == "none"


def test_a_spectroscan_preset_keeps_its_own_layout(panel):
    panel.set_recipe(LayoutRecipe(instrument="CM", paper="A4",
                                  layout_mode="area_first",
                                  area_method="by_width",
                                  layout_explicit=True))
    _pick(panel, "SS")
    r = panel.get_recipe()
    assert (r.layout_mode, r.area_method) == ("area_first", "by_width")


def test_a_preset_that_wanted_no_clip_band_keeps_it_off(panel):
    panel.set_recipe(LayoutRecipe(instrument="CM", paper="A4",
                                  clip_content_mode="off",
                                  layout_explicit=True))
    _pick(panel, "i1")
    assert panel.get_recipe().clip_content_mode == "off"


# ---------------------------------------------------------------------------
# 3. An answer given BY HAND counts too
# ---------------------------------------------------------------------------
def test_a_hand_chosen_layout_mode_is_not_overwritten(panel):
    _pick(panel, "i1")
    _set_combo(panel.layout_mode, "patch_first")
    _set_combo(panel.layout_mode, "area_first")
    _pick(panel, "CR30")
    assert panel.get_recipe().layout_mode == "area_first"


def test_re_picking_the_row_already_ticked_is_still_an_answer(panel):
    """`area_first` is what the panel already shows, so choosing it emits no
    `currentIndexChanged` at all — and it is still a person saying "this one"."""
    _pick(panel, "i1")
    assert panel.layout_mode.currentData() == "area_first"
    _set_combo(panel.layout_mode, "area_first")
    _pick(panel, "CR30")
    assert panel.get_recipe().layout_mode == "area_first"


def test_a_hand_chosen_no_spacers_survives_a_round_trip_to_a_cr30(panel):
    """The old comment CLAIMED this — *"so a deliberate 'no spacers' chosen
    while an i1 was already selected is not touched"* — and the code could not
    tell that "none" from the one a CR30 leaves behind."""
    _pick(panel, "i1")
    _set_combo(panel.spacer_mode, "none")
    _pick(panel, "CR30")
    _pick(panel, "i1")
    assert panel.get_recipe().spacer_mode == "none"


def test_a_default_writing_a_control_does_not_make_it_an_answer(panel):
    """The whole mechanism turns on this: if the CR30 default's own write
    counted as an answer, the leftover-spacer restore could never fire again."""
    _pick(panel, "CR30")
    assert panel._may_default("spacer_mode"), \
        "the app answered its own question"
    assert panel._may_default("layout_mode")


# ---------------------------------------------------------------------------
# 4. The answer travels with the recipe
# ---------------------------------------------------------------------------
def test_a_fresh_panel_owns_no_layout(panel):
    assert panel.get_recipe().layout_explicit is False


def test_a_hand_edit_makes_the_recipe_own_its_layout(panel):
    _set_combo(panel.spacer_mode, "none")
    assert panel.get_recipe().layout_explicit is True


def test_the_flag_round_trips_through_the_dict_form():
    r = LayoutRecipe(instrument="CM", paper="A4", layout_explicit=True)
    assert LayoutRecipe.from_dict(r.to_dict()).layout_explicit is True
    old = r.to_dict()
    old.pop("layout_explicit")
    assert LayoutRecipe.from_dict(old).layout_explicit is False, \
        "a recipe written before this field existed must behave as it does today"


def test_the_engine_is_never_told_who_chose_the_layout():
    """`build_kwargs` is the ENGINE's input and this is a UI question, so the
    flag is deliberately not in it — which is why a chart that stored raw kwargs
    reconstructs as "nobody chose", exactly as `label_style_explicit` does. The
    reader still exists so a dict that DOES carry it is not silently dropped."""
    kw = LayoutRecipe(instrument="CM", paper="A4",
                      layout_explicit=True).build_kwargs()
    assert "layout_explicit" not in kw
    assert LayoutRecipe.from_build_kwargs(kw).layout_explicit is False
    assert LayoutRecipe.from_build_kwargs(
        {**kw, "layout_explicit": True}).layout_explicit is True


def test_the_app_own_defaults_never_claim_to_be_an_answer():
    assert default_recipe("CR30", "A4").layout_explicit is False
    assert default_recipe("i1", "A4").layout_explicit is False
    store = presets.PresetStore.factory_defaults()
    assert not any(r.layout_explicit for r in store._presets.values()), (
        "a factory preset claiming to be somebody's answer would silence every "
        "instrument default in the app")


def test_saving_and_reloading_a_chart_keeps_it_protected(panel):
    """A chart saved after a preset was loaded must come back protected, or the
    fault returns one session later."""
    panel.set_recipe(_preset_recipe())
    saved = panel.get_recipe().to_dict()
    assert saved["layout_explicit"] is True
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p2 = LayoutOptionsPanel(with_selectors=True)
    try:
        p2.set_recipe(LayoutRecipe.from_dict(saved))
        _pick(p2, "CR30")
        assert p2.get_recipe().layout_mode == "area_first"
    finally:
        p2.deleteLater()


# ---------------------------------------------------------------------------
# 5. Through the REAL tab, not a re-implementation of it
#
# Everything above hands the panel a recipe built the way `_seed_knut_preset`
# builds one, which would validate itself if that function stopped marking the
# recipe. This drives the tab's own preset-seeding code — the half of
# `_apply_knut_preset` that was deliberately split out so it can be exercised
# without running printtarg — and then changes the instrument on the panel the
# preset just filled in.
# ---------------------------------------------------------------------------
def test_the_real_preset_seeding_marks_the_layout_as_the_presets_own(tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    QApplication.instance() or QApplication([])
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        tab._switch_mode("manual")
        tab._seed_knut_preset(CM_84P)              # Knut's two clicks
        panel = tab._manual_layout_panel
        assert panel.get_recipe().layout_explicit is True, (
            "the preset seeded the panel without saying it owns its layout")
        _pick(panel, "CR30")                       # …and the third
        r = panel.get_recipe()
        assert r.layout_mode == "area_first"
        assert (r.area_cols, r.area_rows) == (7, 12)
        assert r.spacer_mode == "colored"
    finally:
        tab.deleteLater()
