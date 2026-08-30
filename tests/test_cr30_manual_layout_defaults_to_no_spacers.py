"""A CR30 chart must not default to printing spacers nobody can use.

A spacer exists so a STRIP reader can find where one patch ends as it is swiped
across the row. A CR30 is lifted onto each patch by hand and never swipes, so a
spacer is ink and paper it cannot use — and on a hand-aimed instrument the extra
width costs real patches per sheet.

`default_recipe("CR30")` already answers "none", and Guided already forces it.
Manual does neither: it builds its recipe from the panel's own controls, so
whatever the Spacers combo happened to be showing won, and it shows "colored".
Basti, 2026-08-30, having found it on screen: *"create chart manual tab defaults
to use colored spacers for the cr30. should default to none for this device"*.

The FROM PROFILE GAMUT module needs no separate fix and gets one test here to
prove it: it reuses this same Manual layout panel ("The Manual layout half is on
screen too", tab_chart.py), so a fix in the panel reaches both.

These drive the REAL `LayoutOptionsPanel` and its real signal wiring — the
instrument combo is changed the way a user changes it, and the assertions read
the real `get_recipe()` the builder consumes. Nothing here re-states the rule.
"""
import pytest

from workflow.layout_engine.presets import default_recipe


@pytest.fixture
def panel(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _choose_instrument(panel, code):
    """Change it the way a person does: pick the row in the combo."""
    i = panel.instr.findData(code)
    assert i >= 0, f"{code} is not offered in the instrument combo"
    panel.instr.setCurrentIndex(i)


def test_choosing_a_cr30_leaves_the_spacers_off(panel):
    _choose_instrument(panel, "i1")
    _choose_instrument(panel, "CR30")
    assert panel.spacer_mode.currentData() == "none", (
        "the Manual panel still offers coloured spacers for an instrument that "
        "is placed on each patch by hand and can never use one")


def test_the_recipe_the_builder_reads_says_none(panel):
    """The combo is not the deliverable — `get_recipe()` is what builds the
    chart, and it is assembled from the controls, not from `default_recipe`."""
    _choose_instrument(panel, "CR30")
    r = panel.get_recipe()
    assert r.spacer_mode == "none"
    assert r.spacer_on is False, "spacer_on must follow the mode into the engine"


def test_it_is_a_default_and_not_a_rule(panel):
    """Guided forces this; Manual must not. A user who deliberately turns
    spacers on still gets them, or the control is a lie."""
    _choose_instrument(panel, "CR30")
    assert panel.spacer_mode.isEnabled(), "the control was disabled, not defaulted"
    i = panel.spacer_mode.findData("colored")
    assert i >= 0
    panel.spacer_mode.setCurrentIndex(i)
    assert panel.get_recipe().spacer_mode == "colored", (
        "a deliberate choice was overridden")


def test_switching_away_does_not_strand_the_setting(panel):
    """Going back to a strip reader must not leave it with no spacers — that
    would break the instrument this default was never about."""
    _choose_instrument(panel, "CR30")
    _choose_instrument(panel, "i1")
    assert panel.get_recipe().spacer_mode != "none", (
        "an i1 chart was left with no spacers to find its strips by"
    )


def test_a_stored_recipe_is_not_overridden(panel):
    """`was_loading` exists so a preset or a per-target recipe carries its own
    values. A user who saved a CR30 recipe WITH spacers must get it back."""
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe(instrument="CR30", paper="A4")
    r.spacer_mode = "colored"
    panel.set_recipe(r)
    assert panel.get_recipe().spacer_mode == "colored", (
        "loading a stored recipe re-applied the instrument default over it")


def test_the_other_two_paths_already_agreed_all_along():
    """Guided and `default_recipe` were never the problem — pin that, so a
    future change cannot quietly move the disagreement to the other side."""
    assert default_recipe("CR30", "A4").spacer_mode == "none"
    assert default_recipe("i1", "A4").spacer_mode != "none"
