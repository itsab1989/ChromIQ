"""Row numbers (#Knut, 2026-08-30): the tri-state must not answer for the user.

`LayoutRecipe.show_row_indicators` is None / True / False, where None means
"whatever this instrument does". The panel therefore has to distinguish a state
a PERSON chose from one it merely displayed — and the first implementation
inferred that from "the box disagrees with the instrument default", which is
not the same thing. Picking a SpectroScan with an untouched box then stored an
explicit False and silently removed the row numbers a SpectroScan has always
printed.
"""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.dialogs.layout_options_panel import LayoutOptionsPanel
from workflow.layout_engine.presets import LayoutRecipe
from workflow.layout_engine import instruments as I


def _rlwi(r: LayoutRecipe) -> float:
    return I.geom_from_build_kwargs(r.build_kwargs()).rlwi


@pytest.fixture()
def panel(qapp):
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    yield p
    p.deleteLater()


def _pick(panel, code):
    panel.instr.setCurrentIndex(panel.instr.findData(code))


def test_choosing_a_spectroscan_keeps_the_row_numbers_it_always_had(panel):
    """THE BUG: the box was never clicked, so nothing may be stored."""
    _pick(panel, "SS")
    r = panel.apply_to_recipe(LayoutRecipe(instrument="SS", paper="A4"))
    assert r.show_row_indicators is None, (
        "an untouched checkbox wrote an answer the user never gave")
    assert _rlwi(r) > 0, "the SpectroScan lost the row numbers it always prints"
    assert panel.show_row_indicators.isChecked() is True


def test_choosing_an_i1pro_does_not_add_a_band_nobody_asked_for(panel):
    """The mirror of the same fault."""
    _pick(panel, "SS")
    _pick(panel, "i1")
    r = panel.apply_to_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    assert r.show_row_indicators is None
    assert _rlwi(r) == 0.0
    assert panel.show_row_indicators.isChecked() is False


def test_a_real_click_is_kept_and_survives_an_instrument_change(panel):
    """The other half: once a person answers, the instrument stops deciding."""
    panel.show_row_indicators.click()                  # a real click, not setChecked
    r = panel.apply_to_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    assert r.show_row_indicators is True and _rlwi(r) > 0
    _pick(panel, "SS")
    assert panel.show_row_indicators.isChecked() is True
    _pick(panel, "i1")
    assert panel.show_row_indicators.isChecked() is True, (
        "a choice the user made was overwritten by the instrument")


def test_turning_off_a_spectroscans_row_numbers_is_kept(panel):
    """OFF where the instrument says ON is the state most easily lost."""
    _pick(panel, "SS")
    panel.show_row_indicators.click()                  # ticked -> clear
    r = panel.apply_to_recipe(LayoutRecipe(instrument="SS", paper="A4"))
    assert r.show_row_indicators is False
    assert _rlwi(r) == 0.0


def test_a_loaded_recipe_reports_whether_it_carries_an_answer(panel):
    """set_recipe must restore the flag, or a load-then-save loses the None."""
    panel.set_recipe(LayoutRecipe(instrument="SS", paper="A4"))
    assert panel._row_indicators_touched is False
    panel.set_recipe(LayoutRecipe(instrument="SS", paper="A4",
                                  show_row_indicators=False))
    assert panel._row_indicators_touched is True
    r = panel.apply_to_recipe(LayoutRecipe(instrument="SS", paper="A4"))
    assert r.show_row_indicators is False


def test_row_numbers_follow_the_strip_labels_they_are_drawn_with(panel):
    """raster.py draws them inside `if draw_indicators:` — so the control must
    not stay live offering a band that costs paper and prints nothing."""
    panel.show_indicators.setChecked(False)
    assert panel.show_row_indicators.isEnabled() is False
    panel.show_indicators.setChecked(True)
    assert panel.show_row_indicators.isEnabled() is True
