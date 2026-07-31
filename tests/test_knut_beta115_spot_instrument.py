"""#130 (Knut, 2026-07-31, testing beta.114): the single-patch tool must know
which instrument is attached, and must not strand the user on "Calibrating…".

Two findings, both diagnosed by Knut from a terminal rather than by me:

1. **The instrument was never detected.** I had claimed spotread was launched
   with the instrument ChromIQ chose. It is not — ``-c 1`` selects the
   *communication port*. So both calibration windows fell back to generic
   wording whatever was plugged in. His ``spotread -v`` output shows the one
   line that does say:  ``Instrument Type:   ColorMunki``.

2. **The stuck "Calibrating…".** With the dial still in measurement position he
   pressed Start Calibration and the tool sat there for ever — *"Clicking
   instrument button had no effect… Had to stop session."* His transcript shows
   spotread simply RE-PRINTS its prompt when the instrument is not in position.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

from workflow.spot_read_manager import (SpotReadManager,   # noqa: E402
                                        SpotReadParams,
                                        _INST_TYPE_RE)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- 1. the instrument is actually detected ------------------------------
def test_spotread_is_asked_to_announce_the_instrument(qapp):
    """Without -v the line we need is never printed at all."""
    m = SpotReadManager.__new__(SpotReadManager)
    assert "-v" in SpotReadManager._build_args(m, SpotReadParams())


def test_the_comport_is_not_mistaken_for_the_instrument(qapp):
    """-c is the communication port. Believing otherwise is exactly the mistake
    that made every window generic."""
    m = SpotReadManager.__new__(SpotReadManager)
    args = SpotReadManager._build_args(m, SpotReadParams(instrument="1"))
    assert args[args.index("-c") + 1] == "1"


def test_knuts_actual_terminal_line_parses(qapp):
    """Pasted from his terminal, spacing and all."""
    m = _INST_TYPE_RE.search("Instrument Type:   ColorMunki")
    assert m and m.group(1) == "ColorMunki"


@pytest.mark.parametrize("line,expected", [
    ("Instrument Type:   ColorMunki", "ColorMunki"),
    ("Instrument Type: i1Pro", "i1Pro"),
    ("Instrument Type:\ti1Pro2", "i1Pro2"),
])
def test_it_reads_the_name_whatever_the_spacing(qapp, line, expected):
    m = _INST_TYPE_RE.search(line)
    assert m and m.group(1) == expected


def test_an_unrelated_line_is_not_read_as_an_instrument(qapp):
    assert _INST_TYPE_RE.search("Serial Number:     2017464") is None


def test_the_colormunki_reaches_its_own_wording(qapp):
    """End to end: the reported name must select the ColorMunki texts."""
    from ui.ti2_loader import instrument_family
    assert instrument_family("ColorMunki") == "colormunki"


def test_the_dialog_prefers_the_detected_instrument(qapp):
    """The device in your hand beats whatever the chart was made for — that is
    the whole point of detecting it."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._instrument_family)
    assert src.index("_detected_instrument") < src.index("chart_instrument")


def test_the_manager_reports_it(qapp):
    assert hasattr(SpotReadManager, "instrument_detected")


# ---- 2. the wrong dial position is noticed -------------------------------
def test_a_repeated_prompt_means_the_instrument_is_not_ready(qapp):
    """Knut's transcript: the prompt appears a second time when the key was
    pressed but the instrument was not in position."""
    src = inspect.getsource(SpotReadManager._handle_line)
    first = src.index("calibration_prompt.emit()")
    again = src.index("calibration_position_wrong.emit()")
    assert first < again, "the repeat must be the else-branch of the first"


def test_the_first_prompt_is_still_the_normal_one(qapp):
    """The guard must not turn an ordinary calibration into a warning."""
    src = inspect.getsource(SpotReadManager._handle_line)
    assert "if not self._calib_announced:" in src


def test_the_window_offers_a_way_out_and_a_way_on(qapp):
    """Being trapped was the actual fault: Try again re-sends the key so turning
    the dial then works, and Cancel leaves spotread cleanly."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_position_wrong)
    assert "Try again" in src and "Cancel session" in src
    assert "send_key" in src


def test_that_window_is_instrument_specific_too(qapp):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_position_wrong)
    assert "calibration_instructions_html(self._instrument_family())" in src


def test_it_does_not_stack(qapp):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_position_wrong)
    assert "_cal_pos_open" in src and "finally:" in src


# ---- 3. the two text faults he reported ----------------------------------
def test_the_help_text_english_is_fixed(qapp):
    """*"'has' should here be 'is'"* — his correction, verbatim."""
    from ui.dialogs import spot_read_dialog
    src = inspect.getsource(spot_read_dialog.SpotReadDialog)
    assert "instrument has calibrated" not in src
    assert "instrument is calibrated" in src


def test_the_skip_help_icon_uses_the_window_accent(qapp):
    """It was red; every other mark in this window is green."""
    from ui.dialogs import spot_read_dialog
    src = inspect.getsource(spot_read_dialog.SpotReadDialog)
    assert "color=_ACCENT" in src
