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
