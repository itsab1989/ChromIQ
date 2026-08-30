"""#159: the calibration-first flow, ruled by Basti on 2026-08-28.

"i'd rather have this button being a calibration button and instructions to put
the cap with the white tile on for this … the calibration button should trigger
the calibration on the instrument wthout the user pressing a button", and — once
EXP-BLE-012 disproved the belief that Bluetooth could not do it — "if it is
supported then chromiq triggers both".

The rules that must hold, and every one of them was a way to lose something:

* Cancelling costs NOTHING. The window sits before the archive step, so a user
  who cancels because the white tile is in the other room does not find the
  run's existing measurement moved to old/ for a measurement that never began.
* Guided is mandatory, Manual honours the existing Skip box — and that is read
  from the run's params, never from the widget, because the widget is hidden in
  Guided and holds whatever Manual last set (beta.148: a stored tick ran every
  guided measurement uncalibrated).
* The calibration cannot be counted as a measurement.
* ChromIQ never claims the calibration worked.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure                       # noqa: E402
from workflow import measurement_messages as M                   # noqa: E402


def _calibration_source() -> str:
    """The flow is a pair: a thin wrapper that holds Start and Stop across it,
    and the body it guards. Both are the unit under test."""
    return (inspect.getsource(TabMeasure._run_cr30_calibration)
            + inspect.getsource(TabMeasure._calibrate_and_confirm))


def test_the_window_comes_before_anything_irreversible():
    """The whole reason it sits where it does."""
    src = inspect.getsource(TabMeasure._on_start)
    cal = src.index("_run_cr30_calibration")
    archive = src.index("_archive_measurement_before_replacing")
    assert cal < archive, (
        "the calibration window opens after the run's measurement has been "
        "archived — cancelling it would cost the user that measurement")
    assert src.index("_confirm_replacing_measurement") < cal, (
        "the user is asked to calibrate before being asked whether to replace "
        "the measurement at all")


def test_cancelling_disarms_the_sound_it_armed():
    """#131: per-patch sounds must not stay live outside a read, and Start
    arms them before this point."""
    # THE WINDOW IS THE `if` BLOCK, NOT A CHARACTER COUNT. This sliced 600
    # characters after the call, so it broke the day a comment above it grew —
    # measuring the source's shape rather than the code's behaviour.
    src = inspect.getsource(TabMeasure._on_start)
    i = src.index("if not self._run_cr30_calibration():")
    block = src[i:src.index("return", i) + len("return")]
    assert "_sound.disarm()" in block, (
        "a cancelled start leaves the measurement sounds armed")


def test_the_skip_rule_is_read_from_the_run_not_the_widget():
    """beta.148: the Skip box is hidden in Guided while still holding whatever
    Manual last set, so reading the widget ran guided measurements
    uncalibrated with nothing on screen to say so."""
    # The GUARD LINE itself, not a 2000-character window before the call:
    # what matters is what the `if` tests, and a window drifts with comments.
    src = inspect.getsource(TabMeasure._on_start)
    guard = next(l for l in src.splitlines()
                 if "if params.external_values" in l
                 or "disable_initial_cal" in l)
    assert "params.disable_initial_cal" in guard, (
        f"the calibration gate is not read from the run: {guard.strip()!r}")
    assert "_nocal_cb" not in guard, (
        "the calibration gate reads the checkbox — in Guided that widget is "
        "hidden and belongs to Manual")


def test_it_calibrates_through_the_session_reader():
    """A second device handle means opening the instrument twice, and over
    Bluetooth that is a disconnect and reconnect of a peripheral that accepts
    one connection at a time."""
    src = _calibration_source()
    assert "_open_cr30_bridge" in src
    assert "_cr30_reader" in src
    assert "CR30.open" not in src, "it opens its own second handle"


def test_it_does_not_block_the_gui_thread():
    """The reader holds its lock for the whole call — the same primitive that
    froze the app for three minutes on Stop."""
    src = _calibration_source()
    assert "QThread" in src and "moveToThread" in src


def test_the_cancel_does_not_touch_the_readers_one_way_latch():
    """`DeviceReader._cancel` means 'this reader is finished' and is never
    cleared, so cancelling a calibration through it would make every patch
    read for the rest of the session fail instantly."""
    src = _calibration_source()
    assert ".cancel()" not in src, (
        "the calibration reaches for the reader's one-way cancel latch")


def test_the_message_never_claims_the_calibration_worked():
    """The device reports the firmware's nominal tile constant whatever is
    under the cap: white tile and green face come back bit-identical, so there
    is nothing to check and no threshold that could be defended."""
    body = M.M_CR30_CALIBRATE.body.lower()
    assert "cannot check" in body
    for lie in ("successful", "calibration complete", "verified", "confirmed"):
        assert lie not in body, f"the window claims {lie!r}"


def test_the_warning_is_about_the_cap_face_not_about_magnets():
    """Telling the user to keep magnets away would tell them to remove the very
    thing the operation requires — the magnet is what makes it a calibration."""
    body = M.M_CR30_CALIBRATE.body.lower()
    assert "white tile" in body and "green" in body
    assert "away from" not in body


def test_it_is_still_awaiting_approval():
    assert M.M_CR30_CALIBRATE.approved is False
