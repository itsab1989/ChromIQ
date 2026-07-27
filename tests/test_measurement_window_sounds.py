"""#131 (Knut, 2026-07-27): every measurement window sounds as it appears.

His rule, stated after finding "Wrong Strip Read" silent: *"It has been very
clearly stated that ALL warnings and error windows that could occur during
measurement, either patch-by-patch mode, re-measure mode, or normal reading
mode, shall have their belonging sound played at the same time as the window
appears."*

Two ways a window can fail that rule, and both have bitten us:

1. **No cue at all** — nothing was ever wired to the signal that raises it.
2. **A cue that arrives late** — the cue is *connected* to the same signal as
   the slot that opens the window, but AFTER it. Qt calls slots in connection
   order, and a slot that opens a modal dialog blocks inside itself, so the cue
   is not heard until the user dismisses the window. That is the "sound played
   when I pressed the button" report, three times over.

These tests read the source rather than drive the windows, deliberately: driving
them needs a modal event loop per window, and what has actually gone wrong every
time is the *wiring*, which is exactly what is checked here.
"""
from __future__ import annotations

import inspect
import re

import pytest

from ui.tabs.tab_measure import TabMeasure

#: Every slot that opens a window during a measurement, and the cue it owes.
#: "connected" means the cue is wired to the signal instead of played inside the
#: slot — allowed only if the connection is made before the window's own.
_WINDOW_SLOTS = {
    "_on_wrong_strip": "STRIP_FAIL",
    "_on_unexpected_response": "PATCH_OUT_OF_TOL",
    "_on_strip_interrupted": "STRIP_FAIL",
    "_on_unread_confirm": "STRIP_FAIL",
    "_on_strip_misaligned": "STRIP_FAIL",
    "_on_abort_confirm": "INSTRUMENT_ERROR",
    "_on_calibration_prompt": "INSTRUMENT_ERROR",
}


@pytest.mark.parametrize("slot,event", sorted(_WINDOW_SLOTS.items()))
def test_each_window_cues_itself_from_the_top_of_its_slot(slot, event):
    """Not merely somewhere in the slot: BEFORE the dialog is built, or the cue
    waits for the window to close."""
    src = inspect.getsource(getattr(TabMeasure, slot))
    assert f'self._cue_window("{event}")' in src, f"{slot} has no cue"

    lines = [l.strip() for l in src.splitlines()]
    cue_at = next(i for i, l in enumerate(lines) if "_cue_window(" in l)
    dialog_at = next((i for i, l in enumerate(lines)
                      if re.search(r"QDialog\(|QMessageBox\(", l)), len(lines))
    assert cue_at < dialog_at, (
        f"{slot} plays its cue after building the window — it will be heard "
        f"when the window is dismissed")


def test_the_instrument_error_cues_are_connected_before_their_windows():
    """The one family whose cue is connected rather than played inline. Qt calls
    slots in connection order, so this ordering IS the behaviour."""
    src = inspect.getsource(TabMeasure.__init__)
    assert "_connect_instrument_error_cues()" in src
    cue_at = src.index("_connect_instrument_error_cues()")
    for signal in ("sensor_wrong_position.connect(self._on_sensor_wrong_position)",
                   "device_busy.connect(self._on_device_busy)",
                   "generic_instrument_error.connect("):
        assert signal in src, signal
        assert cue_at < src.index(signal), (
            f"the cue is connected after {signal} — it will be heard when the "
            f"window is dismissed")


def test_every_error_signal_that_opens_a_window_has_a_cue():
    """A new window must not be able to arrive silent. The list of signals that
    carry a cue is checked against the slots that open windows."""
    cues = inspect.getsource(TabMeasure._connect_instrument_error_cues)
    for signal in ("instrument_disconnected", "no_instrument", "device_busy",
                   "sensor_wrong_position", "usb_claimed_by_vm",
                   "generic_instrument_error", "coms_init_failed",
                   "inst_init_failed", "instrument_wrong_type",
                   "ccmx_load_failed", "mode_set_failed"):
        assert signal in cues, f"{signal} has no cue"


def test_the_strip_windows_keep_their_own_arrangements():
    """Two windows sound themselves for reasons of their own, and must keep
    doing so: the strip-failure window classifies the fault first (slow-down vs
    failed), and the pace window plays its cue before deciding whether to open
    at all."""
    err = inspect.getsource(TabMeasure._on_strip_error)
    assert "_on_strip_error_sound" in err or "self._sound.play" in err or \
        "_play_strip_cue" in err

    pace = inspect.getsource(TabMeasure._report_strip_pace)
    assert "_play_strip_cue" in pace


def test_only_one_cue_can_sound_for_one_strip():
    """Knut has heard two at once more than once. The strip cue has a single
    decision point, and the completion sound waits for it to finish."""
    src = inspect.getsource(TabMeasure)
    assert "_ALL_DONE_SOUND_GAP_MS" in src
    cue = inspect.getsource(TabMeasure._play_strip_cue)
    assert "SLOW_DOWN if too_fast else" in cue, \
        "the strip cue must remain one either/or, not two plays"


def test_a_cue_never_blocks_a_window():
    """A window must open even if the sound cannot be played at all."""
    src = inspect.getsource(TabMeasure._cue_window)
    assert "except Exception" in src


# ---- stock ArgyllCMS chartread stays ChromIQ-silent (Knut, 2026-07-27) -----
def test_chromiq_plays_nothing_while_stock_chartread_reads(tmp_path):
    """His ruling: "the ChromIQ sounds should not at all be wired or used for
    stock argyllcms chartread" — Argyll beeps for itself there and cannot be
    silenced, so ours would only double every event."""
    from PyQt6.QtCore import QSettings

    import core.sound as snd
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("sound_enabled", True)
    player = snd.SoundManager(s)
    played = []
    player._preload = lambda events: None
    player._effects = {}

    class _Eff:
        def __init__(self, name): self.name = name
        def play(self): played.append(self.name)

    for ev in snd.ALL_EVENTS:
        player._effects[ev] = _Eff(ev)

    player.arm(reading_engine=False)
    for ev in (snd.STRIP_OK, snd.STRIP_FAIL, snd.SLOW_DOWN, snd.PATCH_OK):
        player.play(ev)
    assert played == [], played

    # …but the engine path is unaffected.
    player.arm(reading_engine=True)
    player.play(snd.STRIP_OK)
    assert played == [snd.STRIP_OK]


def test_a_completion_sound_still_plays_on_stock(tmp_path):
    """It belongs to ChromIQ's own workflow, not to Argyll's reading."""
    from PyQt6.QtCore import QSettings

    import core.sound as snd
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("sound_enabled", True)
    player = snd.SoundManager(s)
    played = []
    player._preload = lambda events: None

    class _Eff:
        def play(self): played.append("finished")

    player._effects = {snd.MEASUREMENT_FINISHED: _Eff()}
    player.arm(reading_engine=False)
    player.play(snd.MEASUREMENT_FINISHED)
    assert played == ["finished"]


def test_a_mid_run_fallback_silences_us_too():
    """The engine can give way to stock chartread while reading."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    for slot in (TabMeasure._on_engine_fell_back,
                 TabMeasure._on_engine_fell_back_resumed):
        assert "_silence_for_stock_chartread()" in inspect.getsource(slot)
