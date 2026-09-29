"""Preferences told every CR30 owner their instrument reads at 100 Hz.

Basti, 2026-09-08: *"in preferences under the measurement tab the cr30 is said
to have 100Hz. I think you measured more like 3Hz and it is patch by patch only
anyway"*. He was right on both counts, and the second one decides the fix.

100.0 was the i1Pro's number, copied. `368087e7` committed it the day BEFORE the
CR30's own rate was measured, "purely so the Preferences spinbox shows the
shipped default instead of silently clamping it" -- and the column it landed in
is headed "Readings per second" with a tooltip saying "from its specification".

The honest number is not simply 3.18 either. That figure is a HOST-DRIVEN USB
cycle (trigger, read, repeat) from a probe on a path `cr30/device.py` marks
"NOT for a ChromIQ backend"; ChromIQ waits for the operator's button press, so
nobody using it ever sees 3.18. It is also USB-only: no Bluetooth rate has ever
been measured. So the cell states no rate at all, and the row's information
button carries the account. Basti chose that shape, 2026-09-08.

WHAT THESE TESTS GUARD, in order of how badly each would bite:

* the cell must not go back to asserting a rate;
* the row must not go back to WRITING one on every Preferences save, which is
  what a merely-greyed spin box would still do (a disabled QDoubleSpinBox
  answers `.value()` perfectly happily);
* the other six rows must keep their editable boxes and their own values --
  this fix must not have been paid for by them;
* the shared range and decimals must not move, because widening them to express
  a sub-10 figure would let somebody set an i1Pro to 1 Hz (20 s per patch) and,
  on a de_DE machine, print "100,00 Hz" on six rows that never needed changing;
* the information button must not repeat the two claims that were false for
  this instrument.
"""
from __future__ import annotations

import os

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.measure_pace import (MODEL_DEFAULTS, SAMPLE_HZ_RANGE,  # noqa: E402
                               defaults_for, explanation_for)
from core.settings import AppSettings                            # noqa: E402

RATE_ROWS = ("i1pro", "i1pro2", "i1pro3", "i1pro3plus", "colormunki",
             "spectroscan")


@pytest.fixture
def dlg(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    # A store written by an older build, carrying the value being complained
    # about. It must be left alone, not migrated: see the save test below.
    s.set("pace_sample_hz_cr30", 100.0)
    from ui.dialogs.settings_dialog import SettingsDialog
    d = SettingsDialog(s, None)
    d._settings = s
    return d


# ---------------------------------------------------------------------------
# the number itself
# ---------------------------------------------------------------------------
def test_the_cr30_no_longer_carries_the_i1pros_rate():
    hz, min_samples = defaults_for("cr30")
    assert hz != MODEL_DEFAULTS["i1pro"][0], \
        "the CR30 is back on the i1Pro's rate, which is where this began"
    assert hz != 100.0
    assert min_samples is None, "a CR30 has no swipe to be too quick"


def test_the_row_still_exists_so_the_fallback_stays_shut():
    """`_pace_config`'s unknown-instrument fallback is the i1Pro's (100.0, 20).
    Deleting the CR30 entry would let that be applied to a CR30 chart."""
    assert "cr30" in MODEL_DEFAULTS


# ---------------------------------------------------------------------------
# what the dialog shows
# ---------------------------------------------------------------------------
def test_the_cr30_has_no_rate_box_at_all(dlg):
    assert "cr30" not in dlg._pace_hz, (
        "the CR30 has a rate spin box again. Greying one is not enough: a "
        "disabled QDoubleSpinBox still answers .value(), so the save loop "
        "would go on writing pace_sample_hz_cr30 on every Save."
    )


def test_every_other_instrument_kept_its_editable_box(dlg):
    for key in RATE_ROWS:
        assert key in dlg._pace_hz, f"{key} lost its rate box"
        box = dlg._pace_hz[key]
        assert box.isEnabled(), f"{key}'s rate box was disabled as collateral"
        assert box.value() == pytest.approx(MODEL_DEFAULTS[key][0])


def test_the_cell_says_not_applicable_in_the_words_already_used(dlg):
    """`tr("N/A")` is the string the Patches cell beside it uses, so this costs
    no new catalogue key and reads the same in every language."""
    from core.i18n import tr
    texts = [w.text() for w in dlg.findChildren(QLabel)]
    assert tr("N/A") in texts


def test_the_shared_range_and_decimals_did_not_move(dlg):
    assert SAMPLE_HZ_RANGE == (10.0, 500.0), (
        "widening this to express a sub-10 rate lets an i1Pro be set to 1 Hz, "
        "i.e. 20 s per patch, on every other row"
    )
    for key in RATE_ROWS:
        box = dlg._pace_hz[key]
        assert box.decimals() == 0, (
            f"{key} grew decimals; on a de_DE machine that prints '100,0 Hz'"
        )
        assert box.minimum() == SAMPLE_HZ_RANGE[0]


# ---------------------------------------------------------------------------
# what a Save writes
# ---------------------------------------------------------------------------
def test_a_save_stops_rewriting_the_cr30s_rate_and_still_writes_the_others(dlg):
    """The control matters: a save that wrote nothing would pass the first
    assertion for the wrong reason, so a real row is poisoned first."""
    s = dlg._settings
    s.set("pace_sample_hz_i1pro", 7.0)          # nothing's default: a canary

    # 3.18 IS THE POINT, NOT AN ARBITRARY MARKER. It is below
    # SAMPLE_HZ_RANGE[0], so no spin box in this dialog can hold it: a box
    # seeded from it would clamp to 10.0 and write 10.0 back. Storing 100.0
    # here instead would let a re-introduced box pass, because it would seed
    # from 100.0 and write the identical value -- which is exactly how an
    # earlier draft of this test passed under a mutation that gave the CR30
    # its box back.
    s.set("pace_sample_hz_cr30", 3.18)

    dlg._save_and_close()

    assert s.get("pace_sample_hz_i1pro", None) != 7.0, (
        "the save loop did not run, so this test proves nothing about the CR30"
    )
    assert float(s.get("pace_sample_hz_cr30", 0)) == pytest.approx(3.18), \
        "the CR30's rate went through a spin box again and was clamped on save"


def test_a_stale_stored_value_is_left_where_it_is(dlg):
    """Deliberately NOT migrated. It is inert (a CR30's minimum is Off, and
    `_pace_config` throws the rate away on that branch), and dropping it would
    mean bumping SETTINGS_SCHEMA -- one counter that re-runs every migration,
    which on measurement resets five unrelated settings a user had chosen,
    `chartread_engine` among them."""
    assert dlg._settings.get("pace_sample_hz_cr30", None) == 100.0


# ---------------------------------------------------------------------------
# what the information button says
# ---------------------------------------------------------------------------
def test_the_help_no_longer_calls_it_a_rate_from_a_specification():
    _title, body = explanation_for("cr30")
    assert "from its specification" not in body, (
        "the CR30's figure is a measured per-reading time; the research repo "
        "records that no sensor-parameter command exists at all"
    )


def test_the_help_no_longer_invites_a_setting_that_does_nothing():
    _title, body = explanation_for("cr30")
    assert "judged like any other" not in body, (
        "following that instruction changes nothing: the pace model subscribes "
        "to strip_measured and a CR30 never emits a strip"
    )


def test_the_help_says_why_the_cell_is_empty_and_what_the_real_figure_is():
    _title, body = explanation_for("cr30")
    assert "one reading each time you press its button" in body
    assert "3.2 readings a second" in body
    assert "never drives it that way" in body


@pytest.mark.parametrize("key", RATE_ROWS)
def test_the_other_instruments_help_is_untouched(key):
    """The CR30 leaves the shared explanation early rather than having it
    corrected underneath, which is the difference between one new catalogue
    key and seven."""
    _title, body = explanation_for(key)
    assert "HOW THE THREE NUMBERS ON THIS ROW ARE USED" in body
    assert "from its specification" in body
