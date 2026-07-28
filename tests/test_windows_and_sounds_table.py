"""#131 (Knut, 2026-07-27): the windows-and-sounds table in the help text.

*"a full table like this one shall be added to the help text icon … showing
exactly which sounds are wired to which error/failure/event window during
measurement … Make sure the table is actually shown as a table, for example
using html table in the help icon window."*

Two things have to hold and keep holding:

* it renders **as a table** — a proportional font cannot align columns any other
  way, which is why the earlier plain-text attempt was unreadable;
* it describes **what the code actually does**. A help text that drifts from the
  wiring is worse than none, so the sound names here are checked against the
  labels in Preferences and against the cues the windows really play.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.measure_windows import (EVENT_ROWS, WINDOW_ROWS,  # noqa: E402
                                  windows_and_sounds_html)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_it_is_a_real_table():
    from core.measure_windows import FAILURE_ROWS
    html = windows_and_sounds_html()
    assert "<table" in html and "</table>" in html
    # three tables, each with a header row
    assert html.count("<tr>") == (len(WINDOW_ROWS) + len(EVENT_ROWS)
                                  + len(FAILURE_ROWS) + 3)


def test_the_help_dialog_renders_it_as_rich_text(qapp):
    """A body carrying a table switches the dialog out of plain text; anything
    else stays plain, so a stray "<" in prose is still shown literally."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel

    from ui.tooltip_button import _InfoDialog

    def _body_format(body):
        dlg = _InfoDialog("t", body, None, 420)
        # The body label is the wrapping one inside the scroll area.
        labels = [l for l in dlg.findChildren(QLabel) if l.wordWrap()]
        return labels[-1].textFormat()

    assert _body_format(windows_and_sounds_html()) == Qt.TextFormat.RichText
    assert _body_format("prose with a < in it") == Qt.TextFormat.PlainText


def test_rich_text_takes_its_colour_from_the_palette(qapp):
    """A style sheet colours a plain label; rich text does not read it, so the
    table came out black on the dark theme until the palette was set."""
    from ui.tooltip_button import _InfoDialog
    src = inspect.getsource(_InfoDialog)
    assert "setPalette(_pal)" in src
    assert "ColorRole.Text" in src


# ---- the table must match the code ----------------------------------------
def test_every_sound_name_is_one_the_user_can_find_in_preferences():
    """Knut: "Patch out of tolerance: There is no sound defined with this name."
    Only the Preferences labels may appear."""
    import pathlib
    settings_src = (pathlib.Path(__file__).resolve().parents[1]
                    / "ui" / "dialogs" / "settings_dialog.py").read_text()
    labels = {"Patch read OK", "Patch reading looks off", "Strip read OK",
              "Strip read failed", "Instrument error", "Slow down",
              "Measurement finished", "Profile build finished"}
    for label in labels:
        assert f'tr("{label}")' in settings_src, f"{label} is not a Preferences label"

    for _w, _m, sound in WINDOW_ROWS + EVENT_ROWS:
        first = sound.split(",")[0].split("—")[0].strip()
        assert first in labels, f"{first!r} is not a name from Preferences"


def test_the_windows_listed_are_the_windows_that_exist():
    """Each row names a window the Measure tab can actually raise."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure).lower()
    # These carry the instrument-error cue and are raised from shared helpers
    # rather than by a window of their own name.
    by_signal = {"instrument disconnected", "no instrument found",
                 "instrument busy", "instrument error (other)"}
    for window, _mode, _sound in WINDOW_ROWS:
        stem = window.split("/")[0].split("(")[0].strip()
        if stem.lower() in by_signal:
            continue
        assert stem.lower() in src, f"no window called {stem!r}"


def test_the_instrument_windows_all_say_instrument_error():
    """They share one cue, wired in _connect_instrument_error_cues."""
    rows = {w: s for w, _m, s in WINDOW_ROWS}
    for w in ("Instrument disconnected", "No instrument found", "Instrument busy",
              "Instrument in Wrong Position",
              "Instrument Not Accessible (claimed by a virtual machine)",
              "Instrument error (other)", "Calibration required"):
        assert rows[w] == "Instrument error", w


def test_the_notes_state_the_two_rules_that_surprise_people():
    html = windows_and_sounds_html()
    assert "half a second" in html          # the completion gap
    assert "stock ArgyllCMS chartread" in html


# ---- row 1 in full (Knut, #131 2026-07-28) --------------------------------
def test_row_one_is_broken_out_in_full():
    """"for row 1, also list all the cases previously defined with sound, so
    the table is complete"."""
    from core.measure_windows import FAILURE_ROWS
    html = windows_and_sounds_html()
    assert "Row 1 in full" in html
    assert html.count("<table") == 3
    for wording, _meaning, _sound in FAILURE_ROWS:
        assert wording in html


def test_the_failure_rows_match_how_the_code_classifies_them():
    """The table must not drift from `failure_kind`: every wording listed as
    "Slow down" has to classify as too_fast, and every other as not-too_fast."""
    from core.measure_pace import failure_kind
    from core.measure_windows import FAILURE_ROWS
    for wording, _meaning, sound in FAILURE_ROWS:
        kind = failure_kind(wording)
        if sound == "Slow down":
            assert kind == "too_fast", (wording, kind)
        else:
            assert kind != "too_fast", (wording, kind)


def test_every_wording_the_code_knows_appears_in_the_table():
    """A phrase ChromIQ classifies but never lists would be a gap in the very
    table that is meant to be complete."""
    from core.measure_pace import _NOT_PACE, _TOO_FAST, _TOO_SLOW
    from core.measure_windows import FAILURE_ROWS
    listed = " ".join(w.lower() for w, _m, _s in FAILURE_ROWS)
    for needle in _TOO_FAST + _TOO_SLOW:
        assert needle in listed, f"{needle!r} is classified but not listed"
    # The not-about-pace list includes calibration phrases that belong to the
    # instrument windows rather than to a strip failure; the strip ones must
    # still be there.
    for needle in ("swipe didn't start and end on the media",
                   "light level is too low"):
        assert needle.split(" / ")[0][:20] in listed
