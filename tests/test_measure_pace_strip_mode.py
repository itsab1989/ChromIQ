"""#131 (Knut, 2026-07-26): reading pace in STRIP mode, and the on-screen
readout that shows it.

Knut measured a 45-patch chart with a ColorMunki and saw no per-patch sounds and
no pace feedback at all. The cause was structural, not a wiring slip: the engine
emits a per-patch event only in patch-by-patch (spot) reading. A strip-scanning
instrument hands the whole strip back when the swipe ends, so during a strip
there is nothing to time per patch.

What *is* real is the scan's own duration — from the instrument firing
(``scan_started``) to the strip arriving — and the number of patches in that
strip. That is the pair Knut derived every threshold from.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("pace_hint_enabled", True)
    # A ColorMunki's figures: 50 readings per second, 30 per patch → 600 ms.
    s.set("pace_sample_hz_colormunki", 50.0)
    s.set("pace_min_samples_colormunki", 30)
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t._on_instrument_detected("X-Rite ColorMunki")
    return t


# isHidden() rather than isVisible(): the tab itself is never shown in a test,
# and isVisible() is False for every child of a hidden parent. isHidden() is the
# widget's own shown/hidden flag, which is what the code sets.
def _strip(n_patches: int, name="A"):
    return {"strip": name, "patches": [{"id": f"{name}{i}"} for i in range(n_patches)]}


def test_a_hurried_strip_is_reported_as_too_fast(tab, monkeypatch):
    """11 patches in 3 seconds is 273 ms each — well under the ColorMunki's
    600 ms, and exactly the case Argyll would reject or read badly."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started()
    clock[0] += 3.0
    tab._report_strip_pace(_strip(11))

    assert not tab._pace_readout.isHidden()
    text = tab._pace_readout.text()
    assert "Too fast" in text, text
    assert "ff6b6b" in tab._pace_readout.styleSheet(), "the verdict must be red"


def test_an_unhurried_strip_is_reported_as_good(tab, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started()
    clock[0] += 9.0                      # 818 ms per patch
    tab._report_strip_pace(_strip(11))

    assert "Good reading speed" in tab._pace_readout.text()
    assert "5cb85c" in tab._pace_readout.styleSheet(), "the verdict must be green"


def test_the_scan_time_is_measured_from_the_instrument_firing(tab, monkeypatch):
    """Not from when the strip was offered: the time spent lining the head up
    is not part of the swipe, and counting it would make every strip look slow
    enough to pass."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    clock[0] += 30.0                     # a long pause: reading the manual
    tab._on_scan_started()               # NOW the swipe starts
    clock[0] += 3.0
    tab._report_strip_pace(_strip(11))

    assert "Too fast" in tab._pace_readout.text(), \
        "the pause before the swipe must not count as reading time"


def test_each_strip_is_listed_with_the_time_it_took(tab, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    for name, secs in (("A", 9.0), ("B", 8.0)):
        tab._on_scan_started()
        clock[0] += secs
        tab._report_strip_pace(_strip(11, name))

    listed = tab._pace_strips.text()
    assert "Strip A" in listed and "Strip B" in listed
    assert "9.0" in listed and "8.0" in listed
    assert not tab._pace_strips.isHidden()


def test_the_readout_is_cleared_for_a_fresh_read(tab, monkeypatch):
    """Knut: it must be cleared when a strip is re-read, a chart is re-read, or
    measuring is stopped — an old verdict must never be read as this one's."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started()
    clock[0] += 3.0
    tab._report_strip_pace(_strip(11))
    assert not tab._pace_readout.isHidden()

    tab._clear_pace_readout()

    assert tab._pace_readout.isHidden()
    assert tab._pace_strips.isHidden()
    assert tab._pace_readout.text() == "" and tab._pace_strips.text() == ""


def test_no_verdict_without_a_scan_start(tab):
    """A strip that arrives with no start time (stock chartread, which reports
    no such event) says nothing rather than inventing a number."""
    tab._clear_pace_readout()
    tab._report_strip_pace(_strip(11))
    assert tab._pace_readout.isHidden()


def test_the_pace_panel_respects_the_preference(tab, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._settings.set("pace_hint_enabled", False)
    tab._on_scan_started()
    clock[0] += 3.0
    tab._report_strip_pace(_strip(11))
    assert tab._pace_readout.isHidden()


# ---- the completion sound belongs to the measurement, not the next step ----
def test_the_finished_sound_plays_once_per_read(tab):
    played = []
    tab._sound.play = lambda ev: played.append(ev)
    tab._finish_sound_played = False

    tab._play_measurement_finished_once()
    tab._play_measurement_finished_once()      # e.g. measure_finished as well
    assert played == ["measurement_finished"], played

    tab._finish_sound_played = False           # a new read may sound again
    tab._play_measurement_finished_once()
    assert len(played) == 2


# ---- a FAILED strip: the case from Knut's log ----------------------------
def test_a_failed_strip_is_told_it_was_read_too_fast(tab, monkeypatch):
    """Knut's log: three "Not enough patches" failures in a row, with nothing
    said about speed — so he tried again just as fast. A failed scan returns no
    patches, so the count comes from the strip that succeeded first."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started()                       # a good strip first
    clock[0] += 9.0
    tab._report_strip_pace(_strip(15, "B"))
    assert tab._last_strip_patches == 15

    tab._on_scan_started()                       # then a hurried one that fails
    clock[0] += 2.1                              # 140 ms per patch
    tab._report_failed_strip_pace("Not enough patches")

    assert "Too fast" in tab._pace_readout.text()
    assert "ff6b6b" in tab._pace_readout.styleSheet()


def test_a_failure_that_is_not_about_speed_is_not_blamed_on_speed(tab,
                                                                  monkeypatch):
    """Argyll's own wording decides. "Swipe didn't start and end on the media"
    is a positioning fault — telling the user to slow down would send them the
    wrong way (Knut, #131)."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started(); clock[0] += 9.0
    tab._report_strip_pace(_strip(15, "B"))
    tab._clear_pace_readout()

    tab._on_scan_started()
    clock[0] += 12.0
    tab._report_failed_strip_pace("Swipe didn't start and end on the media")

    assert "does not look like speed" in tab._pace_readout.text()
    assert "Too fast" not in tab._pace_readout.text()


def test_too_many_patches_is_called_uneven_not_too_fast(tab, monkeypatch):
    """"Too many patches" means hesitation — the opposite advice."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started(); clock[0] += 9.0
    tab._report_strip_pace(_strip(15, "B"))
    tab._clear_pace_readout()

    tab._on_scan_started(); clock[0] += 20.0
    tab._report_failed_strip_pace("Too many patches")

    assert "Uneven swipe" in tab._pace_readout.text()


def test_a_failure_is_listed_even_when_the_patch_count_is_unknown(tab,
                                                                  monkeypatch):
    """Knut: the timing shows for every strip, "even if OK or failed". With no
    successful strip yet the seconds are still shown — but no per-patch figure
    is invented from a count nobody knows."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._clear_pace_readout()
    tab._last_strip_patches = 0
    tab._on_scan_started(); clock[0] += 1.0
    tab._report_failed_strip_pace("Not enough patches")

    assert "Strip failed after 1.0 s" in tab._pace_strips.text()
    assert not tab._pace_readout.isHidden()
    assert "ms per patch" not in tab._pace_readout.text()


# ---- accepted, but under the threshold (Knut, #131 2026-07-26) ------------
def _engine(tab, monkeypatch, accepted=True):
    """Pretend the ChromIQ engine is running — the offer needs its go-to."""
    monkeypatch.setattr(type(tab._manager), "engine_active",
                        property(lambda self: True))
    jumped = []
    monkeypatch.setattr(tab._manager, "goto_strip", lambda s: jumped.append(s))
    return jumped


def test_a_fast_but_accepted_strip_offers_a_re_read(tab, monkeypatch):
    """Argyll only refuses a strip once it is unusable. Between "fine" and
    "refused" the readings are accepted but thin, and nothing used to say so."""
    jumped = _engine(tab, monkeypatch)
    shown = {}
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, "exec",
                        lambda self: shown.setdefault("title", self.windowTitle()))
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started()
    clock[0] += 3.0                              # 273 ms per patch vs 600 ms
    tab._report_strip_pace(_strip(11, "A"))

    assert shown.get("title") == "Strip Read Quickly"
    assert jumped == [], "nothing is re-read unless the user asks"


def test_continuing_keeps_the_reading(tab, monkeypatch):
    jumped = _engine(tab, monkeypatch)
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)   # default = continue
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started(); clock[0] += 3.0
    tab._report_strip_pace(_strip(11, "A"))

    assert jumped == [], "Continue Anyway must not jump back"


def test_a_comfortable_strip_is_never_interrupted(tab, monkeypatch):
    _engine(tab, monkeypatch)
    from PyQt6.QtWidgets import QDialog
    seen = {"n": 0}
    monkeypatch.setattr(QDialog, "exec",
                        lambda self: seen.__setitem__("n", seen["n"] + 1))
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started(); clock[0] += 9.0      # 818 ms per patch
    tab._report_strip_pace(_strip(11, "A"))

    assert seen["n"] == 0, "a strip read at a good pace must not raise a dialog"


def test_the_offer_quotes_the_current_preference(tab, monkeypatch):
    """The good speed suggested has to follow the settings, not be fixed text."""
    _engine(tab, monkeypatch)
    texts = []
    from PyQt6.QtWidgets import QDialog, QLabel
    monkeypatch.setattr(QDialog, "exec", lambda self: texts.append(
        " ".join(w.text() for w in self.findChildren(QLabel))))
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started(); clock[0] += 3.0
    tab._report_strip_pace(_strip(11, "A"))
    assert "600 ms" in texts[0], texts[0][:200]

    tab._settings.set("pace_min_samples_colormunki", 60)   # 1200 ms
    tab._on_scan_started(); clock[0] += 3.0
    tab._report_strip_pace(_strip(11, "B"))
    assert "1200 ms" in texts[1], texts[1][:200]


def test_no_offer_without_the_engine(tab, monkeypatch):
    """Going back to an accepted strip needs the engine's go-to, so with stock
    chartread the warning is shown but no re-read is offered."""
    monkeypatch.setattr(type(tab._manager), "engine_active",
                        property(lambda self: False))
    from PyQt6.QtWidgets import QDialog
    seen = {"n": 0}
    monkeypatch.setattr(QDialog, "exec",
                        lambda self: seen.__setitem__("n", seen["n"] + 1))
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    tab._on_scan_started(); clock[0] += 3.0
    tab._report_strip_pace(_strip(11, "A"))

    assert seen["n"] == 0
    assert "Too fast" in tab._pace_readout.text(), "the verdict still shows"


def test_choosing_re_read_jumps_back_to_that_strip(tab, monkeypatch):
    """The half that matters: the engine is told to go back, so the next swipe
    replaces the hurried reading."""
    jumped = _engine(tab, monkeypatch)
    from PyQt6.QtWidgets import QDialog, QPushButton

    def press_re_read(dlg):
        for b in dlg.findChildren(QPushButton):
            if "Re-read" in b.text():
                b.click()
                return 1
        raise AssertionError("no Re-read button in the dialog")
    monkeypatch.setattr(QDialog, "exec", press_re_read)

    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started(); clock[0] += 3.0
    tab._report_strip_pace(_strip(11, "A"))

    assert jumped == ["A"], "the engine must be sent back to that strip"
