"""B8-965 and B8-968, both decided by Basti on 2026-09-24.

B8-965. Picking ColorMunki "Extra-high density" seeds Guided's 5 mm margins
(#93, Sebastian, 2026-06-29). Driven on screen with Knut's A3+ 616p preset
(T34 R24 B18 L14) it replaced the preset's margins with 5/5/5/5, and going back
to High kept 5 mm. The decision, option (b): the seed goes ONLY into margins
that are still at their default. Margins a preset set, or a person typed, are
never overwritten by a density change; a reset to the defaults makes them
default again; leaving Extra-high keeps whatever the margins are.

"At default" in the code (`LayoutOptionsPanel._margins_at_default`): nobody
chose them (not typed, not loaded from a recipe somebody chose, which every
preset / chart / carry-back load marks with `layout_explicit`) AND they are
the instrument's own starting values (`default_recipe`, or the 5 mm the seed
itself wrote).

B8-968. "Max strip length" has no effect in "Prioritise chart area" on any
instrument (the chart area and the grid decide the strips). It is now shown
greyed out there, with a tooltip that says why and where it applies, and is
live in "Prioritise patch size".
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from workflow.layout_engine.presets import LayoutRecipe, default_recipe

PRESET_MARGINS = (34.0, 24.0, 18.0, 14.0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _panel():
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_threshold_lookup(lambda inst, paper: {"T": 33.0, "R": 6.0,
                                                "B": 10.0, "L": 6.0})
    return p


def _margins(p):
    return tuple(p.margins[k].value() for k in ("t", "r", "b", "l"))


def _pick(p, mode):
    """The Mode pulldown as a person uses it."""
    i = p.mode.findData(mode)
    assert i >= 0, mode
    p.mode.setCurrentIndex(i)
    p.mode.activated.emit(i)


def _type(spin, text):
    """Type into a margin box by keyboard, as a person does."""
    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, text)
    QTest.keyClick(spin, Qt.Key.Key_Return)


def _cm_preset(margins=PRESET_MARGINS, *, explicit=True):
    """How the tab hands a preset picked by name to the panel: the recipe with
    `layout_explicit` forced on (tab_chart, built-in and user presets)."""
    r = LayoutRecipe(instrument="CM", paper="483x329", cm_density=2,
                     layout_mode="area_first", area_method="by_grid",
                     area_cols=44, area_rows=14, layout_explicit=explicit,
                     use_instrument_margins=False)
    (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) = margins
    return r


def _fresh_cm(p):
    """A fresh panel, ColorMunki picked by hand, High density, margins of
    one's own (a fresh recipe starts with "Use instrument margins" ticked)."""
    r = default_recipe("CM", "A4")
    r.use_instrument_margins = False
    p.set_recipe(r)
    i = p.instr.findData("CM")
    p.instr.setCurrentIndex(i)
    p.instr.activated.emit(i)
    _pick(p, "high")


# ---------------------------------------------------------------- B8-965 --
def test_a_presets_margins_survive_extra_high_and_the_way_back(app):
    p = _panel()
    p.set_recipe(_cm_preset())
    assert _margins(p) == PRESET_MARGINS
    _pick(p, "extrahigh")
    assert _margins(p) == PRESET_MARGINS
    r = p.get_recipe()
    assert r.cm_density == 3
    assert (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) \
        == PRESET_MARGINS
    _pick(p, "high")
    assert _margins(p) == PRESET_MARGINS
    _pick(p, "freehand")
    _pick(p, "extrahigh")
    assert _margins(p) == PRESET_MARGINS


def test_the_real_built_in_colormunki_preset_keeps_its_margins(app):
    """Basti's own preset, loaded the way the tab loads it."""
    from dataclasses import replace
    from ui.tabs.tab_chart import KNUT_PRESETS
    pre = next(k for k in KNUT_PRESETS
               if k.slug == "cm_a3plus_616p_1page_landscape_w10_0mm_fast_reading_speed")
    rec = replace(LayoutRecipe.from_dict(pre.layout_recipe), layout_explicit=True)
    want = (rec.margin_top, rec.margin_right, rec.margin_bottom, rec.margin_left)
    assert want == PRESET_MARGINS
    p = _panel()
    p.set_recipe(rec)
    _pick(p, "extrahigh")
    assert _margins(p) == want


def test_a_preset_whose_margins_equal_the_default_is_still_a_preset(app):
    """The flag, not the numbers: a preset at 6/6/6/6 owns them too."""
    p = _panel()
    p.set_recipe(_cm_preset((6.0, 6.0, 6.0, 6.0)))
    _pick(p, "extrahigh")
    assert _margins(p) == (6.0, 6.0, 6.0, 6.0)


def test_a_recipe_that_does_not_say_who_chose_its_margins_keeps_them(app):
    """A recipe saved before the flag (Save as Defaults, an old user preset)
    with margins that are not the instrument's default: its numbers are a
    choice."""
    p = _panel()
    p.set_recipe(_cm_preset(explicit=False))
    _pick(p, "extrahigh")
    assert _margins(p) == PRESET_MARGINS


def test_typed_margins_survive_extra_high(app):
    p = _panel()
    _fresh_cm(p)
    assert _margins(p) == (6.0, 6.0, 6.0, 6.0)
    _type(p.margins["t"], "20")
    assert _margins(p) == (20.0, 6.0, 6.0, 6.0)
    _pick(p, "extrahigh")
    assert _margins(p) == (20.0, 6.0, 6.0, 6.0)
    _pick(p, "high")
    assert _margins(p) == (20.0, 6.0, 6.0, 6.0)


def test_a_margin_typed_back_to_its_default_value_is_still_typed(app):
    """Typed is typed, even when the number happens to equal the default."""
    p = _panel()
    _fresh_cm(p)
    _type(p.margins["t"], "20")
    _type(p.margins["t"], "6")
    assert _margins(p) == (6.0, 6.0, 6.0, 6.0)
    _pick(p, "extrahigh")
    assert _margins(p) == (6.0, 6.0, 6.0, 6.0)


def test_default_margins_still_get_guideds_5_mm(app):
    """#93 is kept where nobody chose the margins."""
    p = _panel()
    _fresh_cm(p)
    _pick(p, "extrahigh")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)
    assert p.get_recipe().border == 5.0
    # Leaving Extra-high keeps whatever the margins are.
    _pick(p, "high")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)
    # ...and they are still default, so a second visit is no change.
    _pick(p, "extrahigh")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)


def test_a_reset_to_the_defaults_makes_the_margins_default_again(app):
    p = _panel()
    p.set_recipe(_cm_preset())
    _pick(p, "extrahigh")
    assert _margins(p) == PRESET_MARGINS
    # Reset (the factory store hands `default_recipe` back, unflagged).
    reset = default_recipe("CM", "483x329", mode="high")
    reset.use_instrument_margins = False
    p.set_recipe(reset)
    assert _margins(p) == (6.0, 6.0, 6.0, 6.0)
    _pick(p, "extrahigh")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)


def test_margins_left_by_unticking_instrument_margins_are_default(app):
    """A fresh recipe starts ticked; unticking on a fresh panel leaves the
    instrument's own margins in the boxes, which the app wrote, not a person:
    still default, so #93 seeds them."""
    p = _panel()
    p.set_recipe(default_recipe("CM", "483x329"))
    assert p.use_instr_margins.isChecked()
    p.use_instr_margins.click()
    assert _margins(p) == (33.0, 6.0, 10.0, 6.0)
    _pick(p, "extrahigh")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)


def test_a_preset_keeps_its_base_margin_too(app):
    p = _panel()
    r = _cm_preset()
    r.border = 8.0
    p.set_recipe(r)
    _pick(p, "extrahigh")
    assert p.get_recipe().border == 8.0


# ---------------------------------------------------------------- B8-968 --
def _instruments():
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return [k for k, _lbl in LayoutOptionsPanel.INSTRUMENTS]


def _layout(p, mode):
    i = p.layout_mode.findData(mode)
    assert i >= 0
    p.layout_mode.setCurrentIndex(i)


def _set_instrument(p, inst):
    rec = default_recipe(inst, "A4")
    rec.layout_mode = "patch_first"
    p.set_recipe(rec)
    assert p.instr.currentData() == inst


@pytest.mark.parametrize("inst", _instruments())
def test_max_strip_length_is_greyed_in_area_first_for_every_instrument(app, inst):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel as P
    p = _panel()
    _set_instrument(p, inst)
    p.max_strip.setValue(150.0)
    _layout(p, "area_first")
    lbl, box = p._max_strip_row[0], p._max_strip_row[1]
    # In view, greyed, and saying why.
    assert p.max_strip.isVisibleTo(p) and lbl.isVisibleTo(p)
    assert not p.max_strip.isEnabled() and not lbl.isEnabled()
    assert p.max_strip.toolTip() == P.max_strip_tooltip(True)
    assert lbl.toolTip() == box.toolTip() == P.max_strip_tooltip(True)
    # The (i) stays clickable.
    assert p._max_strip_row[2].isEnabled()
    # The value is kept for patch-first.
    assert p.max_strip.value() == 150.0
    _layout(p, "patch_first")
    assert p.max_strip.isVisibleTo(p) and p.max_strip.isEnabled()
    assert lbl.isEnabled()
    assert p.max_strip.toolTip() == P.max_strip_tooltip(False)
    assert p.get_recipe().max_strip_mm == 150.0


def test_a_loaded_area_first_preset_greys_it_too(app):
    p = _panel()
    p.set_recipe(_cm_preset())
    assert p.layout_mode.currentData() == "area_first"
    assert p.max_strip.isVisibleTo(p) and not p.max_strip.isEnabled()


def test_the_two_tooltips_say_why_and_where_in_english(app):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel as P
    off, on = P.max_strip_tooltip(True), P.max_strip_tooltip(False)
    assert off.startswith("Greyed out")
    for t in (off, on):
        assert "“Prioritise chart area”" in t
        assert "“Prioritise patch size”" in t
        assert "chart area and the grid decide the strips" in t
        assert "—" not in t
    assert "Top or Bottom margin" in off
    assert "caps how long" in off and "Caps how long" in on


def test_the_two_tooltips_are_german_in_german(app):
    from core.i18n import set_language
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel as P
    try:
        set_language("de")
        off, on = P.max_strip_tooltip(True), P.max_strip_tooltip(False)
        assert off.startswith("Ausgegraut")
        for t in (off, on):
            assert "„Chart-Fläche priorisieren“" in t
            assert "„Messfeldgröße priorisieren“" in t
            assert "Chart-Fläche und das Raster die Streifen" in t
            assert "Greyed" not in t and "Caps how long" not in t
            assert "—" not in t
        p = _panel()
        _set_instrument(p, "CM")
        _layout(p, "area_first")
        assert p.max_strip.toolTip() == off
        _layout(p, "patch_first")
        assert p.max_strip.toolTip() == on
    finally:
        set_language("en")
