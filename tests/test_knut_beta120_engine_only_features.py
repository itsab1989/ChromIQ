"""#130 (Knut, beta.120): engine-only features were on show with stock chartread.

    *"All 'Show overlay...' related functionality is not supported for the stock
    argyllcms chartread measurement engine and must be removed and in OFF state
    when 'ChromIQ chart-reading engine' in Preferences Beta tab is OFF."*

    *"the instructions has a text 'click  Click a patch in the preview to jump
    to it'. This feature is only available in chromIQ chartread engine … thus
    must be removed."*

    *"the checkbox 'Play sounds during measurement' is only applicable for
    ChromIQ chartread engine, so must be hidden when … = OFF."*

Four places showed features that stock chartread cannot provide: the overlay
toggles in both modes, the sounds switch, the "This chart already has a
measurement" window (which offered the overlay and then described "the two
choices above"), and the Calibration Complete key list (which promised
click-to-jump).

Hidden *and* switched off, which is not the same thing: a box left ticked
off-screen would have painted an overlay nobody asked for the moment the engine
came back.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication          # noqa: E402

from core.argyll_runner import ArgyllRunner       # noqa: E402
from core.settings import AppSettings             # noqa: E402
from ui.tabs.tab_measure import TabMeasure        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp):
    s = AppSettings()
    t = TabMeasure(ArgyllRunner(s), s)
    return t, s


def _tick_quietly(box, on: bool = True) -> None:
    """Set a checkbox WITHOUT firing its handler.

    Arranging the precondition, not exercising it: ``_on_overlay_toggled``
    opens a modal window, so a plain setChecked() in a test hangs the run
    forever — which is precisely how this was found.
    """
    box.blockSignals(True)
    box.setChecked(on)
    box.blockSignals(False)


def _set_engine(tab, on: bool, qapp):
    t, s = tab
    s.set("chartread_engine", "chromiq" if on else "argyll")
    t.refresh_engine_visibility()
    qapp.processEvents()
    return t


# ---- the sounds switch ---------------------------------------------------
def test_sounds_are_hidden_for_stock_chartread(tab, qapp):
    t = _set_engine(tab, False, qapp)
    assert not t._sound_cb.isVisibleTo(t)
    assert not t._sound_tip.isVisibleTo(t), "the ⓘ goes with its checkbox"


def test_hiding_the_sounds_switch_does_not_silence_the_windows(tab, qapp):
    """Hidden, but NOT switched off — and that is a change from beta.120.

    Knut asked for the switch to be *"hidden when [the engine] = OFF"*, and it
    was also unticked, by analogy with the overlay boxes below. The analogy
    does not hold: an overlay box left ticked off-screen paints something, while
    this switch is also the master for ChromIQ's own **window** sounds — which
    do play on stock chartread, and which he asked for separately (#130,
    2026-07-28: the "No instrument Found" window arriving in silence was a bug).

    It went unnoticed because nothing called ``refresh_engine_visibility`` until
    Preferences had been opened once. Making it run at startup — his beta.128
    report, *"'Play sounds during measurements' was not hidden when starting
    up"* — would have silenced every window sound for stock-chartread users.

    The per-patch and per-strip sounds are held back for stock chartread inside
    ``Sound.play()``, which is where that rule belongs. Raised on the issue for
    Knut to overrule if he wants the switch cleared as well.
    """
    t, s = tab
    s.set("chartread_engine", "chromiq")
    s.set("sound_enabled", True)
    _tick_quietly(t._sound_cb)
    s.set("chartread_engine", "argyll")
    t.refresh_engine_visibility()
    qapp.processEvents()
    assert not t._sound_cb.isVisibleTo(t), "it must still be hidden"
    assert s.get("sound_enabled") is True, \
        "hiding the control must not turn ChromIQ's window sounds off"


def test_sounds_come_back_with_the_engine(tab, qapp):
    t = _set_engine(tab, False, qapp)
    t = _set_engine(tab, True, qapp)
    assert t._sound_cb.isVisibleTo(t) and t._sound_tip.isVisibleTo(t)


# ---- the overlay toggles -------------------------------------------------
@pytest.mark.parametrize("box", ["_overlay_cb", "_m_overlay_cb"])
def test_the_overlay_boxes_are_hidden_and_unticked(tab, qapp, box):
    t, s = tab
    s.set("chartread_engine", "chromiq")
    _tick_quietly(getattr(t, box))
    t = _set_engine(tab, False, qapp)
    assert not getattr(t, box).isVisibleTo(t)
    assert not getattr(t, box).isChecked(), \
        "a ticked box off-screen paints an overlay nobody asked for"


def test_a_measurement_alone_no_longer_shows_the_overlay_box():
    """The visibility rule itself: a .ti3 is necessary but not sufficient."""
    src = inspect.getsource(TabMeasure._update_resume_availability)
    assert "show_overlay = has_ti3 and self._engine_selected()" in src
    assert "ocb.setVisible(show_overlay)" in src


# ---- the "already has a measurement" window ------------------------------
def test_that_window_offers_one_choice_not_two_with_stock():
    src = inspect.getsource(TabMeasure._offer_existing_measurement) \
        if hasattr(TabMeasure, "_offer_existing_measurement") else None
    if src is None:
        whole = inspect.getsource(TabMeasure)
        i = whole.index('tr("This chart already has a measurement")')
        src = whole[i - 2000:i + 8000]
    assert "engine_on = self._engine_selected()" in src
    assert "applies the choice above" in src, \
        'Knut asked for "OK - applies the choice above..." when the overlay is gone'
    assert "applies the two choices above" in src, "still correct with the engine on"
    assert "show_cb.setVisible(False)" in src


# ---- the Calibration Complete key list -----------------------------------
def test_click_to_jump_is_not_promised_by_stock_chartread():
    whole = inspect.getsource(TabMeasure)
    i = whole.index("Click a patch in the preview to jump to it")
    around = whole[i - 700:i + 400]
    assert "self._engine_selected()" in around, \
        "the click row must be conditional on the engine"
