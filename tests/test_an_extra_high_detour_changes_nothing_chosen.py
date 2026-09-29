"""An Extra-high detour changes nothing a preset set or a person chose.
Beta 42 challenge, items 1, 5 and 6 (2026-09-24).

Basti's ruling for B8-965: a density change seeds its defaults ONLY into what
is still at default; anything a preset set or the user chose is never
overwritten. The first fix guarded the four margins. `_apply_mode_defaults`
writes three things, and the other two were left unguarded:

1. "Patch area alignment" went to centre-left unchecked, and nothing moved it
   back. Driven on screen: typed margins T20 R6 B6 L6 at High, then Extra-high,
   then High again, and the block sat 7 mm lower (47/39 -> 54/32 mm from top
   and bottom); a Red River ColorMunki preset went from top-left to
   centre-left.
5. Under "Use instrument margins" the boxes were left alone (B8-963), but the
   base margin `_border` still went 6 -> 5 into the recipe and the build.
6. Typing a margin marked it chosen for the session only. `get_recipe` wrote
   `layout_explicit` from the four instrument-defaulted answers alone, so after
   Save as Defaults and a restart, typed margins equal to a default value
   (6/6/6/6, or the instrument's own) looked like nobody's and got 5 mm.

The detour tests compare the WHOLE recipe, not the fields the fix is about: a
chosen layout must come back from High -> Extra-high -> High identical in
every field. Mutations are listed on each test.
"""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from workflow.layout_engine.presets import LayoutRecipe, default_recipe

THR = {"T": 33.0, "R": 6.0, "B": 10.0, "L": 6.0}
REDRIVER = "redriver_colormunki_a4_2052p_8pages"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _panel():
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_threshold_lookup(lambda inst, paper: dict(THR))
    return p


def _pick(combo, data):
    """A pulldown as a person uses it."""
    i = combo.findData(data)
    assert i >= 0, data
    combo.setCurrentIndex(i)
    combo.activated.emit(i)


def _type(spin, text):
    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, text)
    QTest.keyClick(spin, Qt.Key.Key_Return)


def _margins(p):
    return tuple(p.margins[k].value() for k in ("t", "r", "b", "l"))


def _fresh_cm(p, *, locked=False):
    """A fresh panel, ColorMunki picked by hand, High. A fresh recipe starts
    with "Use instrument margins" ticked; `locked=False` unticks it the way
    the challenge did, leaving the instrument's own margins behind."""
    p.set_recipe(default_recipe("CM", "A4"))
    _pick(p.instr, "CM")
    _pick(p.mode, "high")
    if not locked and p.use_instr_margins.isChecked():
        p.use_instr_margins.click()


def _redriver(p):
    """Knut's Red River ColorMunki preset, loaded the way the tab loads a
    preset picked by name."""
    from dataclasses import replace
    from ui.tabs.tab_chart import KNUT_PRESETS
    pre = next(k for k in KNUT_PRESETS if k.slug == REDRIVER)
    rec = replace(LayoutRecipe.from_dict(pre.layout_recipe), layout_explicit=True)
    assert rec.patch_area_align == "top-left"
    p.set_recipe(rec)


def _detour(p):
    """High -> Extra-high -> High. Returns the recipe before, during, after."""
    _pick(p.mode, "high")
    before = p.get_recipe().to_dict()
    _pick(p.mode, "extrahigh")
    during = p.get_recipe().to_dict()
    _pick(p.mode, "high")
    after = p.get_recipe().to_dict()
    return before, during, after


def _diff(a, b):
    return {k: (a.get(k), b.get(k)) for k in set(a) | set(b)
            if a.get(k) != b.get(k)}


# ------------------------------------------------------------- item 1 --
def test_typed_margins_come_back_from_the_detour_identical(app):
    """The challenge's own case: T20 R6 B6 L6 typed at High.
    MUTATION: put back the beta-42 `_apply_mode_defaults` (it seeds the
    alignment unconditionally) and this goes red on `patch_area_align`
    top-left -> center-left."""
    p = _panel()
    _fresh_cm(p)
    for k, v in zip("trbl", ("20", "6", "6", "6")):
        _type(p.margins[k], v)
    assert _margins(p) == (20.0, 6.0, 6.0, 6.0)
    before, during, after = _detour(p)
    assert during["patch_area_align"] == before["patch_area_align"] == "top-left"
    assert during["border"] == before["border"]
    assert _diff(before, after) == {}, _diff(before, after)


def test_a_red_river_preset_comes_back_from_the_detour_identical(app):
    """Knut's preset owns its layout: top-left, its margins, its base margin.
    MUTATION as above; red on `patch_area_align`."""
    p = _panel()
    _redriver(p)
    _pick(p.layout_mode, "patch_first")
    before, during, after = _detour(p)
    assert during["patch_area_align"] == "top-left"
    assert (during["margin_top"], during["margin_right"], during["margin_bottom"],
            during["margin_left"]) == (before["margin_top"], before["margin_right"],
                                       before["margin_bottom"], before["margin_left"])
    assert during["border"] == before["border"]
    assert _diff(before, after) == {}, _diff(before, after)


def test_the_red_river_preset_in_its_own_area_first_layout_too(app):
    p = _panel()
    _redriver(p)
    assert p.layout_mode.currentData() == "area_first"
    before, during, after = _detour(p)
    assert during["patch_area_align"] == "top-left"
    assert _diff(before, after) == {}, _diff(before, after)


def test_a_picked_alignment_is_kept_while_default_margins_are_seeded(app):
    """Nobody chose the margins, somebody chose where the block sits: the
    margins get Guided's 5 mm (#93) and the block stays where it was put.
    MUTATION: make `_mark_align_chosen` a no-op and this goes red."""
    p = _panel()
    _fresh_cm(p)
    _pick(p.patch_align, "bottom-right")
    _pick(p.mode, "extrahigh")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)
    assert p.patch_align.currentData() == "bottom-right"


def test_a_picked_top_left_is_a_choice_too(app):
    """Re-picking the row already shown is an answer (`activated`)."""
    p = _panel()
    _fresh_cm(p)
    assert p.patch_align.currentData() == "top-left"
    _pick(p.patch_align, "top-left")
    _pick(p.mode, "extrahigh")
    assert p.patch_align.currentData() == "top-left"


def test_a_layout_nobody_chose_still_gets_guideds_page(app):
    """#93 (Sebastian) is kept where everything is at default: 5 mm margins,
    5 mm base margin, the block centred on the left."""
    p = _panel()
    _fresh_cm(p)
    assert p.patch_align.currentData() == "top-left"
    _pick(p.mode, "extrahigh")
    r = p.get_recipe()
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)
    assert r.border == 5.0
    assert r.patch_area_align == "center-left"


def test_a_non_default_base_margin_is_not_seeded(app):
    """A recipe that says nothing about who chose it, with default margins
    but its own base margin: the base margin is not the default, so it
    stays."""
    p = _panel()
    r = default_recipe("CM", "A4")
    r.use_instrument_margins = False
    r.border = 8.0
    p.set_recipe(r)
    _pick(p.mode, "extrahigh")
    assert _margins(p) == (5.0, 5.0, 5.0, 5.0)
    assert p.get_recipe().border == 8.0


# ------------------------------------------------------------- item 5 --
def test_nothing_is_seeded_under_the_instrument_margins_lock(app):
    """A fresh ColorMunki panel starts locked. Extra-high must not move the
    base margin (6 -> 5 into the recipe and the build) or the block.
    MUTATION: move the `locked` test back below the margin loop (seed
    `_border` and the alignment under the lock) and this goes red."""
    p = _panel()
    _fresh_cm(p, locked=True)
    assert p.use_instr_margins.isChecked()
    before, during, after = _detour(p)
    assert during["border"] == before["border"] == 6.0
    assert during["patch_area_align"] == before["patch_area_align"]
    assert (during["margin_top"], during["margin_right"], during["margin_bottom"],
            during["margin_left"]) == (33.0, 6.0, 10.0, 6.0)
    assert during["cm_density"] == 3
    assert _diff(before, after) == {}, _diff(before, after)


# ------------------------------------------------------------- item 6 --
def _save_and_restart(p):
    """Save as Defaults writes `get_recipe().to_dict()` into the settings
    (`manual_engine_recipe`, a JSON value); the next start builds a new panel
    and loads it with `LayoutRecipe.from_dict` (`_init_manual_layout_panel`)."""
    stored = json.loads(json.dumps(p.get_recipe().to_dict()))
    q = _panel()
    q.set_recipe(LayoutRecipe.from_dict(stored))
    return stored, q


@pytest.mark.parametrize("typed", [("6", "6", "6", "6"),       # the recipe default
                                   ("33", "6", "10", "6")])   # the instrument's own
def test_typed_default_valued_margins_are_still_typed_after_a_restart(app, typed):
    """MUTATION: write `r.margins_explicit = False` in `apply_to_recipe`, or
    stop reading it in `_set_recipe_impl`, and this goes red: 5/5/5/5."""
    p = _panel()
    _fresh_cm(p)
    for k, v in zip("trbl", typed):
        _type(p.margins[k], "7")
        _type(p.margins[k], v)
    want = tuple(float(v) for v in typed)
    assert _margins(p) == want
    stored, q = _save_and_restart(p)
    assert stored["margins_explicit"] is True
    assert stored["layout_explicit"] is False      # nothing else was answered
    assert _margins(q) == want
    _pick(q.mode, "extrahigh")
    assert _margins(q) == want
    assert q.get_recipe().patch_area_align == "top-left"


def test_a_picked_alignment_is_still_picked_after_a_restart(app):
    p = _panel()
    _fresh_cm(p)
    _pick(p.patch_align, "top-left")
    stored, q = _save_and_restart(p)
    assert stored["align_explicit"] is True
    _pick(q.mode, "extrahigh")
    assert q.get_recipe().patch_area_align == "top-left"
    assert _margins(q) == (5.0, 5.0, 5.0, 5.0)     # the margins were nobody's


def test_nothing_typed_is_nothing_chosen_after_a_restart(app):
    """The other direction: a panel nobody touched saves no choice, so the
    next start still gets #93's page."""
    p = _panel()
    _fresh_cm(p)
    stored, q = _save_and_restart(p)
    assert stored["margins_explicit"] is False
    assert stored["align_explicit"] is False
    _pick(q.mode, "extrahigh")
    assert _margins(q) == (5.0, 5.0, 5.0, 5.0)


def test_the_flags_are_not_written_twice_for_a_chosen_layout(app):
    """A recipe that owns its whole layout says so with `layout_explicit`;
    the two new flags stay False there, so a preset loaded by name and saved
    again is recorded exactly as before."""
    p = _panel()
    _redriver(p)
    r = p.get_recipe()
    assert r.layout_explicit is True
    assert r.margins_explicit is False and r.align_explicit is False


def test_old_dicts_and_build_kwargs_read_as_nobody_chose(app):
    r = LayoutRecipe.from_dict({"instrument": "CM", "paper": "A4"})
    assert r.margins_explicit is False and r.align_explicit is False
    kw = LayoutRecipe(instrument="CM", margins_explicit=True).build_kwargs()
    assert "margins_explicit" not in kw and "align_explicit" not in kw
