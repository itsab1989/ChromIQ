"""#159: a magnet must STOP the session, not cost one button press.

It happened on 2026-08-30. The owner rested his chart on a MacBook while
measuring, and the laptop's magnets reached straight through the sheet. The
instrument did what it always does with a magnet at the aperture — took a WHITE
CALIBRATION from whatever it was sitting on, which was the patch he was trying
to read.

The guard fired and refused the reading, which was right. Then the bridge
RE-ARMED the patch, the tab told him to "press the button on the instrument
again", and the session carried on — every patch after that measured against a
reference that had just been overwritten. He noticed only because the numbers
looked wrong.

The refused reading is the least of it. This is the one refusal that must not
be re-armed.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                     # noqa: E402

from workflow.cr30.measurement import (MAGNET_MESSAGE, MagnetGated,   # noqa: E402
                                       Measurement, MeasurementError)
from tests.test_cr30_measure_bridge import Harness                # noqa: E402


def test_the_gate_raises_its_own_kind_not_a_generic_refusal():
    """It needs the opposite answer to every other refused reading, so it has
    to be distinguishable without matching on the message text."""
    m = Measurement(wavelengths=list(range(400, 710, 10)),
                    values=[50.0] * 31, gate_flag=True)
    with pytest.raises(MagnetGated):
        m.check_usable(None)
    assert issubclass(MagnetGated, MeasurementError)


def test_a_magnet_does_not_re_arm_the_patch():
    h = Harness()
    gated: list = []
    h.bridge.magnet_gated.connect(lambda loc, msg: gated.append(loc))
    before = len(h.read_calls)

    h.bridge._on_read_failed("A1", MAGNET_MESSAGE, "MagnetGated")

    assert gated == ["A1"], "the magnet was not reported as its own event"
    assert len(h.read_calls) == before, (
        "the patch was armed again — inviting another press under a reference "
        "the instrument has just overwritten")


def test_a_magnet_stops_the_session():
    h = Harness()
    h.bridge._on_read_failed("A1", MAGNET_MESSAGE, "MagnetGated")
    assert h.bridge._stopped is True, (
        "the session is still live, so the next reading would be written "
        "against a corrupt white reference")


def test_a_magnet_is_not_reported_as_an_ordinary_failure():
    """"Press the button again" is the advice for a refusal that costs a press.
    Here it is the worst thing the app could say."""
    h = Harness()
    ordinary: list = []
    h.bridge.read_failed.connect(lambda loc, msg: ordinary.append(loc))
    h.bridge._on_read_failed("A1", MAGNET_MESSAGE, "MagnetGated")
    assert ordinary == []


def test_the_whole_path_runs_from_the_reader_raising():
    """End to end, the way the instrument actually reports it: the reader
    raises, the worker names the type, the bridge stops. Nothing here matches
    on the message text."""
    h = Harness()
    gated: list = []
    h.bridge.magnet_gated.connect(lambda loc, msg: gated.append(loc))
    h.raise_with = MagnetGated(MAGNET_MESSAGE)

    h.ready("A1")

    assert gated == ["A1"], "the magnet did not reach the tab as its own event"
    assert h.bridge._stopped is True
    assert h.sent == [], "a value was sent for a reading taken through a magnet"


def test_there_is_a_way_back_after_recalibrating():
    """Stopping is only defensible because the remedy is offered and works —
    the window's 'Recalibrate now' has to lead somewhere."""
    h = Harness()
    h.raise_with = MagnetGated(MAGNET_MESSAGE)
    h.ready("A1")
    assert h.bridge._stopped is True
    assert h.bridge._awaiting_loc == "A1", (
        "the patch is no longer outstanding, so there is nothing to resume")

    h.raise_with = None                       # the user recalibrated
    assert h.bridge.resume_after_magnet() is True
    assert h.bridge._stopped is False
    h.settle()
    assert len(h.sent) == 1, "the resumed read never produced a value"


def test_the_message_no_longer_prescribes_the_abandoned_recovery():
    """It used to say "seat the cap and press the device button" — the
    side-effect method ChromIQ has stopped using, which mid-session produces
    another gated reading and another refusal."""
    # THE REMEDY LIVES IN THE WINDOW, NOT IN THE EXCEPTION.
    #
    # This used to assert both on MAGNET_MESSAGE, which is the exception text —
    # and that text is printed in the window's "{reason}" slot, underneath the
    # window that has just given the same advice at length. So the long version
    # moved out and this checks where it actually has to be true.
    from workflow.measurement_messages import M_CR30_MAGNET
    assert "press the device button" not in MAGNET_MESSAGE
    assert "press the device button" not in M_CR30_MAGNET.body
    assert "Recalibrate now" in M_CR30_MAGNET.body
    # And the reason line stays a reason: short, and not a second lecture.
    assert len(MAGNET_MESSAGE) < 200, MAGNET_MESSAGE
