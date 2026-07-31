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


def _rendered(family):
    """The text a user of *family* actually sees in the completion window."""
    import re as _re
    from ui.ti2_loader import spot_measurement_instructions_html
    return _re.sub(r"<[^>]+>", " ", spot_measurement_instructions_html(family))


def test_each_instrument_gets_its_own_instructions(qapp):
    """Knut, #130 2026-07-31: *"one window for each instrument, wired to the
    detection of each instrument type during connection."*

    Asserted on the RENDERED text, not the method source: the window composes it
    from a helper now, so checking the body would prove nothing.
    """
    munki, i1 = _rendered("colormunki"), _rendered("i1pro")
    assert "dial" in munki.lower()
    assert "base" in i1.lower()
    assert munki != i1


def test_the_colormunki_text_no_longer_mentions_a_tile(qapp):
    """His device has no calibration tile; the i1Pro does. One generic text
    could never be right for both, which is how the wrong one shipped."""
    assert "tile" not in _rendered("colormunki").lower()


def test_an_unknown_instrument_still_gets_usable_words(qapp):
    generic = _rendered(None)
    assert "aperture" in generic.lower()
    assert "(s)" not in generic


def test_the_window_pulls_that_text_rather_than_writing_its_own(qapp):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_finished)
    assert "spot_measurement_instructions_html(self._instrument_family())" in src


def test_the_required_window_is_instrument_specific_too(qapp):
    """He asked for BOTH windows; I had wired only the completion one."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_prompt)
    assert "calibration_instructions_html(self._instrument_family())" in src


def test_reading_is_re_enabled_when_the_calibration_ends(qapp):
    """The prompt disables the read button; nothing re-enabled it here before."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_finished)
    assert "_read_btn.setEnabled(True)" in src


# ---- item 2: a way out of the calibration prompt -------------------------
def test_the_calibration_prompt_offers_a_way_out(qapp):
    """Knut, #130 2026-07-31: *"the Calibration Required window is lacking a
    Cancel Measurement button … There should be a chance to change my mind and
    exit the measurement session."* Without one, the only escape was the Stop
    session button hidden behind a modal window."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_prompt)
    assert "Cancel session" in src
    assert "RejectRole" in src
    assert "rejected.connect" in src


def test_cancelling_stops_the_instrument_rather_than_hanging(qapp):
    """Rejecting must send spotread its quit key — a Cancel that only closes the
    window would leave the tool running with nothing driving it."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_prompt)
    assert '\\x1b' in src
    assert src.index("else:") < src.index('\\x1b')


# ---- item 4: the completion window must not stack ------------------------
def test_a_second_completion_window_cannot_open_over_the_first(qapp):
    """*"I press the instrument button. That results in another Calibration
    Complete window to appear on top of the previous, every time I click."*
    Each press makes spotread reprint its ready prompt."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_finished)
    assert '_cal_done_open' in src
    assert src.index("_cal_done_open") < src.index("QDialog(self)")


def test_the_guard_is_released_even_if_the_window_raises(qapp):
    """A stuck guard would silence every later completion window."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_calibration_finished)
    assert "finally:" in src
    assert src.index("finally:") < src.rindex("_cal_done_open = False")


# ---- item 5: the wrong position must be visible, not just written -------
def test_the_wrong_position_opens_a_window(qapp):
    """Knut, #130 2026-07-31 (item 5): he asked for what patch-by-patch does —
    *"a window saying 'The patch could not be read: Sensor should be in surface
    position', then Retry button."* It used to set a status line only, which is
    easy to miss when you are looking at the instrument, not the screen."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_sensor_wrong_position)
    assert "QDialog(self)" in src
    assert "Try again" in src


def test_it_says_what_to_actually_do(qapp):
    """"Wrong position" alone does not tell you which way to turn anything."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    body = _window_text(SpotReadDialog._on_sensor_wrong_position)
    assert "measuring position" in body
    assert "calibration" in body
    assert "(s)" not in body


def test_repeated_reports_do_not_stack_windows(qapp):
    """Pressing the button again while it is still wrong reports it again."""
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    src = inspect.getsource(SpotReadDialog._on_sensor_wrong_position)
    assert "_sensor_pos_open" in src
    assert "finally:" in src


def test_the_signal_reaches_that_handler(qapp):
    from ui.dialogs import spot_read_dialog
    src = inspect.getsource(spot_read_dialog.SpotReadDialog)
    assert "sensor_wrong_position.connect(self._on_sensor_wrong_position)" in src


# ---- the checkbox now explains itself ------------------------------------
def test_the_skip_checkbox_has_a_help_icon(qapp):
    """Knut, #130 2026-07-31: *"add an help icon to the right of the checkbox
    text and in that help text explain how argyllcms handles this request."*

    He reported the box as broken. It is not — and the honest answer is to say
    what it can and cannot promise, rather than to change working code.
    """
    from ui.dialogs import spot_read_dialog
    src = inspect.getsource(spot_read_dialog.SpotReadDialog)
    assert "TooltipButton(" in src
    assert src.index("_skip_cal = QCheckBox") < src.index("TooltipButton(")


def test_the_help_explains_the_three_things_he_asked_for(qapp):
    """The option passed to ArgyllCMS, that some instruments ignore it, and the
    case where it does help."""
    from ui.dialogs import spot_read_dialog
    src = inspect.getsource(spot_read_dialog.SpotReadDialog)
    start = src.index("About skipping the initial calibration")
    help_text = src[start:start + 1800]
    assert "-N" in help_text
    assert "ColorMunki" in help_text
    assert "start another one shortly after" in help_text
    assert "(s)" not in help_text


def test_the_tool_has_its_own_wording_not_the_chart_one(qapp):
    """Knut, #130 2026-07-31: *"separate the patch-by-patch window wording and
    make a window with specific wording for the Read Single Patches tool."*

    Patch-by-patch says "the highlighted patch" because a chart is on screen
    there. Here you pick any colour you like, so borrowing that text described a
    screen the user is not looking at.
    """
    from ui.ti2_loader import (patch_measurement_instructions_html,
                               spot_measurement_instructions_html)
    for fam in ("colormunki", "i1pro", None):
        spot = spot_measurement_instructions_html(fam)
        assert "highlighted patch" not in spot
        assert spot != patch_measurement_instructions_html(fam)


def test_the_chart_wording_is_left_exactly_as_it_was(qapp):
    """Splitting must not disturb text he has already accepted elsewhere."""
    from ui.ti2_loader import patch_measurement_instructions_html
    assert "highlighted patch" in patch_measurement_instructions_html("colormunki")


def test_each_instrument_still_gets_its_own_spot_wording(qapp):
    from ui.ti2_loader import spot_measurement_instructions_html
    munki = spot_measurement_instructions_html("colormunki")
    i1 = spot_measurement_instructions_html("i1pro")
    assert "dial" in munki.lower() and "tile" not in munki.lower()
    assert "base" in i1.lower()
    assert munki != i1
