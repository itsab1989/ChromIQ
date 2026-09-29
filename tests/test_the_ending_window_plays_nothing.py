"""R23-F6 (B8-389). The ending window has no sound, and that is the table's answer.

*"Keep what you have measured so far?"* (M-END) cued **Strip read failed** on
every ending: Stop, Cmd-Q, Give Up, a disconnection, a CR30 loss, the magnet
warning, No Instrument Found, Confirm Abort and *"Patches still unread"*. Two
things were wrong with that, and `measurement_window_sounds.md` §3a settles
both -- it is binding, and its table is generated from
`core.measure_windows.WINDOW_ROWS`, which is also the help card the user reads
under Preferences -> Sounds.

* **The table has no row for it.** Its own opening sentence is *"Every window a
  measurement can raise, and the sound played as it opens"*, so a window
  sounding off the table tells the user *"Strip read failed"* when no strip
  failed. On the Stop and Cmd-Q routes nothing has failed at all: the user
  pressed a button.
* **It played twice.** *"Patches still unread"* cues STRIP_FAIL from the top of
  its own slot (the table's row 8) and then reaches M-END two lines later.
  `play_window` has no de-duplication (`core/sound.py`), so the second play
  restarted the same `QSoundEffect` and truncated the first.

Both are one removal, and every route into M-END arrives either from a window
that has already sounded or from a button the user has just pressed, so nothing
is left unannounced.

**What is measured here is the cue**, at `SoundManager.play_window` /
`.play` -- the boundary `_cue_window` itself uses -- with the real manager left
in place and every call passed through to it, and with sounds really switched
on so the code takes its real path.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import Qt                               # noqa: E402
from PyQt6.QtTest import QTest                            # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

import core.sound as snd                                  # noqa: E402
from core.measure_windows import WINDOW_ROWS              # noqa: E402
from tests.helpers.live_reader import (                   # noqa: E402
    WindowDriver, measuring,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _listen(tab) -> list:
    """Record every cue, and let the real SoundManager have each one anyway.

    Wrapping rather than replacing: a recorder that stands in for the manager
    would be a second implementation of the thing under test, and would agree
    with itself whatever the app did.
    """
    heard: list = []
    real_window, real_play = tab._sound.play_window, tab._sound.play

    def play_window(event):
        heard.append(("play_window", event))
        return real_window(event)

    def play(event):
        heard.append(("play", event))
        return real_play(event)

    tab._sound.play_window = play_window
    tab._sound.play = play
    return heard


def _keep_measuring(w):
    """Answer the ending window the way a user who changed their mind does."""
    QTest.keyClick(w, Qt.Key.Key_Escape)


# ---- the table is still the specification --------------------------------
def test_the_sounds_table_has_no_row_for_the_ending_window():
    """The reason the cue was wrong. If a row is ever added, this fails and
    whoever added it has to decide what M-END should play -- which is Knut's
    to name (`measurement_window_sounds.md` §3a)."""
    labels = {row[0] for row in WINDOW_ROWS}
    assert "Keep what you have measured so far?" not in labels
    assert "Patches still unread" in labels, \
        "row 8 has gone from the table it is measured against"


# ---- M-END, through the real Stop button ---------------------------------
def test_the_ending_window_cues_nothing(qapp, tmp_path):
    with measuring(tmp_path) as (tab, reader):
        tab._settings.set("sound_enabled", True)
        heard = _listen(tab)
        driver = WindowDriver(_keep_measuring).arm()
        tab._stop_btn.click()            # the real Stop button
        driver.disarm()

        assert driver.acted_on == "Keep what you have measured so far?"
        assert heard == [], (
            f"the ending window sounded {heard!r}. The sounds table has no row "
            f"for it, so whatever it plays is a sound the user was never "
            f"promised -- and on the Stop route it says 'Strip read failed' "
            f"when nothing failed and the user pressed a button")


def test_an_empty_ending_cues_nothing_either(qapp, tmp_path):
    """M-END-EMPTY, the branch that asks nothing because nothing was read."""
    with measuring(tmp_path, readings=0) as (tab, reader):
        tab._manager._read_something = False
        tab._settings.set("sound_enabled", True)
        heard = _listen(tab)
        tab._stop_btn.click()
        assert heard == [], f"the empty ending sounded {heard!r}"


# ---- "Patches still unread", which is where the double came from ---------
def test_patches_still_unread_sounds_once_not_twice(qapp, tmp_path):
    """Row 8 cues from the top of its own slot and then reaches M-END two
    lines later. `play_window` has no de-duplication, so the second play
    restarted the same clip and truncated the first."""
    with measuring(tmp_path) as (tab, reader):
        tab._settings.set("sound_enabled", True)
        heard = _listen(tab)
        driver = WindowDriver(_keep_measuring).arm()
        tab._manager.unread_confirm.emit("21, A3")   # the real signal
        driver.disarm()

        assert driver.acted_on == "Keep what you have measured so far?", (
            f"the 'd' key did not reach the ending window; it reached "
            f"{driver.acted_on!r}")
        assert heard == [("play_window", snd.STRIP_FAIL)], (
            f"'Patches still unread' sounded {heard!r}. The table gives it one "
            f"sound; a second play_window restarts the same QSoundEffect and "
            f"truncates the first, so the user hears half of it twice")
