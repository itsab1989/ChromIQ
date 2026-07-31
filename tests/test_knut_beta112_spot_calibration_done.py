"""#130 item 3 (Knut, 2026-07-30): "Read single patches" must say when the
calibration has finished.

    *"Read single patches tool, when enabling 'skip initial calibration', still
    calls the Calibration Required window. When I complete the calibration,
    there is no infomation window that calibration is done and to turn the unit
    back to measure mode. This window and the handling of the Calibration should
    be same as patch-by-patch mode … However, parts of the calibration complete
    window is not relevant for read single patches tool."*

Two findings, and only one of them is a bug.

The skip checkbox already works: it becomes spotread's ``-N``, which ArgyllCMS
documents as "disable initial calibration **if possible**". A ColorMunki cannot
skip it, so spotread asks anyway. Nothing to fix there — a test below pins the
flag so it cannot be "fixed" away by someone reading the report literally.

The missing completion window is the real gap. spotread returning to its ready
prompt after a calibration is the only evidence the calibration finished, so
that is what the window is driven from.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from workflow.spot_read_manager import (SpotReadManager,    # noqa: E402
                                        SpotReadParams)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- the skip flag is already correct; keep it that way -------------------
def test_skip_initial_calibration_reaches_spotread(qapp):
    """It becomes -N. The prompt Knut still sees is the instrument's rule, not
    a missing flag."""
    m = SpotReadManager.__new__(SpotReadManager)
    args = SpotReadManager._build_args(m, SpotReadParams(disable_initial_cal=True))
    assert "-N" in args


def test_not_skipping_leaves_the_flag_off(qapp):
    m = SpotReadManager.__new__(SpotReadManager)
    args = SpotReadManager._build_args(m, SpotReadParams(disable_initial_cal=False))
    assert "-N" not in args


# ---- the completion window ------------------------------------------------
def _window_text(fn) -> str:
    """Only what the user reads: no docstring, no comments.

    Twice now an assertion has tripped on my own prose quoting Knut rather than
    on the window text — first the docstring, then a comment repeating his
    words. Quoting "calibration tile" is not the same as showing it.
    """
    src = inspect.getsource(fn).split('"""')[2]
    return "\n".join(ln for ln in src.splitlines()
                      if not ln.lstrip().startswith("#"))


def test_returning_to_the_ready_prompt_ends_the_calibration(qapp):
    """The only evidence spotread gives that a calibration finished."""
    src = inspect.getsource(SpotReadManager._handle_line)
    ready = src.index("_READY_RE.search(line)")
    fired = src.index("calibration_finished.emit()")
    assert ready < fired < src.index("ready_to_read.emit()")


def test_it_only_fires_after_a_calibration_was_announced(qapp):
    """Every ordinary reading passes the ready prompt too; without the guard the
    window would open after each one."""
    src = inspect.getsource(SpotReadManager._handle_line)
    guard = src.index("if self._calib_announced:")
    assert guard < src.index("calibration_finished.emit()")


def test_the_signal_exists_for_the_dialog_to_use(qapp):
    assert hasattr(SpotReadManager, "calibration_finished")


def test_the_dialog_listens_for_it(qapp):
    from ui.dialogs import spot_read_dialog
    src = inspect.getsource(spot_read_dialog.SpotReadDialog)
    assert "calibration_finished.connect(self._on_calibration_finished)" in src


def test_the_window_says_to_move_the_instrument_back(qapp):
    """The whole point of it, in Knut's words: *"calibration is done and to turn
    the unit back to measure mode"*."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_finished)
    assert "calibrated and ready" in src
    assert "measuring position" in src


def test_the_window_names_the_button_that_is_really_there(qapp):
    """Knut, #130 2026-07-31: the text said "Read patch"; the button is "Take
    reading". Naming a button that does not exist is worse than naming none."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    body = _window_text(SpotReadDialog._on_calibration_finished)
    assert "Take reading" in body
    assert "Read patch" not in body


def test_it_does_not_describe_hardware_this_instrument_lacks(qapp):
    """*"'Take it off the calibration tile', which does not exist for this
    instrument"* — a ColorMunki is turned by a dial."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    body = _window_text(SpotReadDialog._on_calibration_finished)
    assert "calibration tile" not in body


def test_the_window_leaves_out_what_does_not_apply(qapp):
    """*"parts of the calibration complete window is not relevant for read
    single patches tool"* — strips and charts are those parts."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    body = _window_text(SpotReadDialog._on_calibration_finished)
    assert "strip" not in body.lower()
    assert "chart" not in body.lower()
    assert "(s)" not in body


def test_reading_is_re_enabled_when_the_calibration_ends(qapp):
    """The prompt disables the read button; nothing re-enabled it here before."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_finished)
    assert "_read_btn.setEnabled(True)" in src
