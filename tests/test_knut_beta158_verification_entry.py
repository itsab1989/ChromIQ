"""Tab 4's bar is live, but "Verification" cannot be picked from there.

Knut, beta.157: *"Unlock the bar on tab 4; leave it locked on Check & Refine.
==> OK do it."* and, for the question of what should happen if the user picks
Verification while standing there: *"Can you grey out and disable the option
'Verification' in the dropdown list of Run type? and show a tool tip if hovering
over that option in the list … This method would tell user more than being
thrown out of a tab."*

These assert what the widget is, not what the source says — a greyed item is a
property of the combo's model, and that is what is read here.
"""
import pytest

from core.file_manager import FileManager
from core.settings import AppSettings
from ui.measurement_target_bar import (MeasurementTargetBar,
                                       MeasurementTargetController,
                                       RUN_TYPE_VERIFICATION)

TAB_BUILD_PROFILE = 3
TAB_CHECK_REFINE = 4


def _bar(qapp):
    return MeasurementTargetBar(MeasurementTargetController(
        FileManager(AppSettings())))


def _verification_item(bar):
    model = bar._type_combo.model()
    for i in range(bar._type_combo.count()):
        if bar._type_combo.itemData(i) == RUN_TYPE_VERIFICATION:
            return model.item(i)
    pytest.fail("the Run type list has no Verification entry")


def test_verification_is_pickable_by_default(qapp):
    assert _verification_item(_bar(qapp)).isEnabled()


def test_it_greys_with_a_tooltip_that_names_the_way_out(qapp):
    bar = _bar(qapp)
    bar.set_verification_selectable(False)
    item = _verification_item(bar)
    assert not item.isEnabled()
    # The tooltip has to say WHY and WHAT TO DO — that is the whole point of
    # greying the entry instead of moving the user off the tab.
    tip = item.toolTip()
    assert "Build Profile" in tip and "Change tab" in tip


def test_the_grey_survives_the_list_being_rebuilt(qapp):
    """Turning calibration options on rebuilds the items from scratch.

    The old items are thrown away, so the disabled state has to be re-applied
    or it is silently lost — and the user could then pick Verification on
    tab 4 after touching Preferences.
    """
    bar = _bar(qapp)
    bar.set_verification_selectable(False)
    bar.set_calibration_allowed(True)
    assert not _verification_item(bar).isEnabled()


def test_it_comes_back_when_the_user_leaves_the_tab(qapp):
    bar = _bar(qapp)
    bar.set_verification_selectable(False)
    bar.set_verification_selectable(True)
    item = _verification_item(bar)
    assert item.isEnabled()
    assert item.toolTip() == ""


def test_main_window_locks_only_check_and_refine_and_greys_only_on_tab_4():
    """Read from the source, because building a MainWindow segfaults offscreen.

    The behaviour itself is driven on screen; this holds the two indices in
    place so a later edit cannot quietly re-lock tab 4.
    """
    import inspect

    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow._on_tab_changed)
    assert "set_locked(index == 4)" in src
    assert "set_verification_selectable(index != 3)" in src
