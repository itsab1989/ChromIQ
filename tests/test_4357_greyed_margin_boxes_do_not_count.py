"""4.3.57, item 38: with "Use instrument margins" ticked, the four margin boxes
are greyed and say they are locked to the instrument's margins; a value written
into them anyway (seen on screen in part A) still went into the chart Generate
built. The recipe now takes what the tick stands for, from the same lookup that
fills the boxes (`LayoutOptionsPanel._instrument_margins_now`)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

LIMITS = {"T": 11.0, "R": 7.0, "B": 13.0, "L": 9.0}


@pytest.fixture
def panel(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    p.set_threshold_lookup(lambda inst, paper: dict(LIMITS))
    yield p
    p.deleteLater()


def test_a_value_in_a_greyed_box_does_not_reach_the_recipe(panel):
    """MUTATION: drop the `_instrument_margins_now()` override in
    `get_recipe` and the 40 mm written into the greyed box is built."""
    panel.use_instr_margins.setChecked(True)
    assert not panel.margins["t"].isEnabled()
    assert panel.margins["t"].value() == pytest.approx(11.0)
    panel.margins["t"].setValue(40.0)        # written past the lock
    panel.margins["l"].setValue(55.0)
    r = panel.get_recipe()
    assert r.use_instrument_margins
    assert (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) == \
        pytest.approx((11.0, 7.0, 13.0, 9.0))


def test_the_recipe_follows_the_instrument_entry_while_ticked(panel):
    panel.use_instr_margins.setChecked(True)
    LIMITS["T"] = 21.0
    try:
        assert panel.get_recipe().margin_top == pytest.approx(21.0)
    finally:
        LIMITS["T"] = 11.0


def test_unticked_the_typed_margins_count_again(panel):
    panel.use_instr_margins.setChecked(True)
    panel.use_instr_margins.setChecked(False)
    assert panel.margins["t"].isEnabled()
    panel.margins["t"].setValue(40.0)
    r = panel.get_recipe()
    assert not r.use_instrument_margins
    assert r.margin_top == pytest.approx(40.0)


def test_a_missing_entry_falls_back_to_the_instruments_own(panel):
    """No Instrument Limits entry: the instrument's own margins, as the boxes
    show them (the same fallback, one function)."""
    panel.set_threshold_lookup(lambda inst, paper: None)
    panel.use_instr_margins.setChecked(True)
    shown = {k: panel.margins[k].value() for k in "trbl"}
    panel.margins["b"].setValue(77.0)
    r = panel.get_recipe()
    assert r.margin_bottom == pytest.approx(shown["b"])
    assert r.margin_bottom != pytest.approx(77.0)


@pytest.mark.parametrize("inst, side, shown", [("SS", "l", 11.2),
                                                ("CR30", "l", 14.5)])
def test_the_recipe_takes_the_value_as_the_greyed_box_shows_it(
        panel, inst, side, shown):
    """Fix round, review F1: the instrument's own margin is 11.249333 mm on
    the SpectroScan and 14.466667 mm on the CR30; the one-decimal box shows
    11.2 and 14.5, and 4.3.56 built exactly that (measured: same .tif, .ti2
    and strips file to the byte, only the CREATED line differs). The recipe
    must build what the box shows, not the raw lookup.
    MUTATION: drop `_as_box_shows` in `get_recipe` and this fails."""
    panel.instr.setCurrentIndex(panel.instr.findData(inst))
    panel.set_threshold_lookup(lambda i, p: None)
    panel.use_instr_margins.setChecked(True)
    assert panel.margins[side].value() == shown
    r = panel.get_recipe()
    got = {"t": r.margin_top, "r": r.margin_right,
           "b": r.margin_bottom, "l": r.margin_left}
    assert got == {k: panel.margins[k].value() for k in "trbl"}
    assert got[side] == shown        # exact, not approx


def test_an_entry_outside_a_box_range_is_built_as_the_box_holds_it(panel):
    """An Instrument Limits entry with more decimals, or beyond the box's
    range, is built as the box rounds and clamps it."""
    hi = panel.margins["r"].maximum()
    panel.set_threshold_lookup(lambda i, p: {"T": 7.26, "R": hi + 50.0,
                                             "B": 6.0, "L": 9.04})
    panel.use_instr_margins.setChecked(True)
    r = panel.get_recipe()
    assert (r.margin_top, r.margin_right, r.margin_left) == (
        panel.margins["t"].value(), hi, panel.margins["l"].value())
    assert r.margin_top == 7.3 and r.margin_left == 9.0
