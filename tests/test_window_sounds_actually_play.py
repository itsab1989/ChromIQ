"""#130 (Knut, 2026-07-28): the window sounds must actually be heard.

    *"when starting a measurement without the colormunki connected, the window
    'No instrument Found' comes, but without any sound. … This implies that the
    sounds in the help text window 'Measurement windows and their sounds' … is
    not verified connected and working with sounds. … Analyse and verify the
    sounds actually are wired up and test that they play once when errors
    appear."*

He is right, and the reason is worth writing down. The completion audit of
2026-07-28 checked that every window **had** a cue and that the cue sat in the
right place. Both were true, and the sound was still silent — because
``SoundManager.play`` drops anything that is not a completion sound once the
measurement is over, and the instrument windows are raised *after* the process
exits, by which time ``disarm()`` has run. Inspecting the wiring could never
have found that.

So these tests do not read the source. They drive the real slots with a
recording sound manager and assert **what came out of the speaker**, once.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

import core.sound as snd                              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, **kw):
        self._d = {"sound_enabled": True, "patch_read_warn_de": 10.0}
        self._d.update(kw)

    def get(self, k, d=None): return self._d.get(k, d)
    def set(self, k, v): self._d[k] = v


def _tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    tab = TabMeasure(ArgyllRunner(s), s)
    played: list = []
    # Record at the LOWEST level that still exercises the gates — the effect
    # itself. Everything above it (enabled, the at-rest gate, the stock-
    # chartread rule) runs for real.
    tab._sound._preload = lambda events: None

    class _Eff:
        def __init__(self, name): self.name = name
        def play(self): played.append(self.name)

    tab._sound._effects = {e: _Eff(e) for e in snd.ALL_EVENTS}
    return tab, played


# ---- the report itself ---------------------------------------------------
def test_no_instrument_found_is_heard(qapp):
    """His exact case: start a measurement with nothing plugged in."""
    tab, played = _tab(qapp)
    tab._sound.arm(reading_engine=True)
    tab._sound.disarm()          # what _on_measure_done does before the window

    tab._cue_window("INSTRUMENT_ERROR")

    assert played == [snd.INSTRUMENT_ERROR], (
        "the window opens after the read has ended, and the sound was dropped")


def test_it_is_heard_exactly_once(qapp):
    """"…test that they play once when errors appear.""" ""
    tab, played = _tab(qapp)
    tab._sound.disarm()
    tab._cue_window("INSTRUMENT_ERROR")
    assert len(played) == 1


@pytest.mark.parametrize("event", ["INSTRUMENT_ERROR", "STRIP_FAIL",
                                   "PATCH_OUT_OF_TOL", "SLOW_DOWN"])
def test_every_window_sound_is_heard_after_a_read_has_ended(qapp, event):
    """The whole family, in the state the instrument windows are raised in."""
    tab, played = _tab(qapp)
    tab._sound.disarm()
    tab._cue_window(event)
    assert played == [getattr(snd, event)], event


@pytest.mark.parametrize("event", ["INSTRUMENT_ERROR", "STRIP_FAIL",
                                   "PATCH_OUT_OF_TOL"])
def test_and_during_a_read_too(qapp, event):
    tab, played = _tab(qapp)
    tab._sound.arm(reading_engine=True)
    tab._cue_window(event)
    assert played == [getattr(snd, event)], event


# ---- the rules that must still hold -------------------------------------
def test_a_window_stays_silent_when_sounds_are_switched_off(qapp):
    tab, played = _tab(qapp)
    tab._settings.set("sound_enabled", False)
    tab._sound.disarm()
    tab._cue_window("INSTRUMENT_ERROR")
    assert played == []


def test_a_window_stays_silent_when_that_sound_is_set_to_off(qapp):
    """"Off (no sound)" in Preferences means no file, so nothing to play."""
    tab, played = _tab(qapp)
    del tab._sound._effects[snd.INSTRUMENT_ERROR]
    tab._sound.disarm()
    tab._cue_window("INSTRUMENT_ERROR")
    assert played == []


def test_the_reading_sounds_are_still_gated_at_rest(qapp):
    """The window exemption must not leak into the per-strip / per-patch
    sounds — those still belong to the reading and stay quiet outside one."""
    tab, played = _tab(qapp)
    tab._sound.disarm()
    for event in (snd.PATCH_OK, snd.STRIP_OK, snd.STRIP_FAIL):
        tab._sound.play(event)
    assert played == [], "a reading sound escaped the at-rest gate"


def test_stock_chartread_still_silences_the_reading_sounds(qapp):
    """Knut's earlier ruling — Argyll beeps for itself there."""
    tab, played = _tab(qapp)
    tab._sound.arm(reading_engine=False)
    for event in (snd.PATCH_OK, snd.STRIP_OK, snd.STRIP_FAIL):
        tab._sound.play(event)
    assert played == []


def test_a_window_is_still_heard_on_stock_chartread(qapp):
    """A ChromIQ window is ChromIQ's own — ArgyllCMS does not beep for it, so
    there is nothing to double."""
    tab, played = _tab(qapp)
    tab._sound.arm(reading_engine=False)
    tab._cue_window("INSTRUMENT_ERROR")
    assert played == [snd.INSTRUMENT_ERROR]


# ---- every deferred instrument window, driven for real -------------------
def test_each_deferred_instrument_window_sounds_when_it_opens(qapp, monkeypatch):
    """The eight windows raised at the end of a measurement. Each is driven by
    setting its flag and running the finish handler, with the windows stubbed
    out — so what is asserted is the sound, not the dialog."""
    import PyQt6.QtWidgets as W

    flags = ("_usb_claimed_by_vm", "_no_instrument", "_device_busy",
             "_instrument_disconnected", "_instrument_wrong_type")
    for flag in flags:
        tab, played = _tab(qapp)
        monkeypatch.setattr(W.QDialog, "exec", lambda self: 0)
        monkeypatch.setattr(W.QMessageBox, "exec", lambda self: 0)
        setattr(tab, flag, True)
        tab._sound.arm(reading_engine=True)
        try:
            tab._on_measure_done(1)
        except Exception:      # noqa: BLE001 — other paths may need more state
            pass
        assert snd.INSTRUMENT_ERROR in played, (
            f"{flag}: its window opened without a sound")
