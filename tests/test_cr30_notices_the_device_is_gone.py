"""#159 (Basti, 2026-08-28): "i unplugged the device and forgot to stop
measurement - no warning".

The spot workflow spends nearly all its time with nothing arriving, because it
is waiting for a human to press a button. So "no frame yet" is the normal
state. `except Exception: continue` treated a GONE transport as that same
normal state: the read failed instantly, the loop swallowed it and went round
again, and his session sat silent for 71 seconds while he pressed the button on
an instrument that was not plugged in.

The two states are separable and always were -- `receive()` raises
TransportTimeout when nothing came, while pyserial raises from `in_waiting` on
a port that has gone.
"""
from __future__ import annotations

import pytest

from workflow.cr30.device import CR30, DeviceLost
from workflow.cr30.frame import ShortFrameError
from workflow.cr30.transport import TransportTimeout


def _usb_device(receive):
    d = CR30.__new__(CR30)
    d.kind = "usb"
    d._previous = None
    d.model = "CR30"
    d._t = type("T", (), {"receive": staticmethod(receive)})()
    return d


def test_an_unplugged_instrument_is_reported_not_swallowed():
    """pyserial's failure on a vanished port must reach the user."""
    def _gone(_timeout):
        raise OSError(6, "Device not configured")

    d = _usb_device(_gone)
    with pytest.raises(DeviceLost):
        d.read_next_measurement(timeout=5.0)


def test_a_quiet_instrument_is_still_just_waiting():
    """The other half, and the one that must NOT change: a button nobody has
    pressed yet is not a fault, and must never be reported as one."""
    def _quiet(_timeout):
        raise TransportTimeout("nothing yet")

    d = _usb_device(_quiet)
    with pytest.raises(Exception) as e:
        d.read_next_measurement(timeout=0.3)
    assert not isinstance(e.value, DeviceLost), (
        "an instrument waiting for its button was reported as disconnected")
    assert "button" in str(e.value).lower()


def test_a_partial_frame_is_not_a_disconnection():
    """A truncated frame means the reply is still arriving, not that the
    instrument has gone."""
    def _partial(_timeout):
        raise ShortFrameError("partial frame, 12/60 bytes")

    d = _usb_device(_partial)
    with pytest.raises(Exception) as e:
        d.read_next_measurement(timeout=0.3)
    assert not isinstance(e.value, DeviceLost)


def test_a_dropped_bluetooth_link_is_reported():
    d = CR30.__new__(CR30)
    d.kind = "ble"
    d._previous = None
    d.model = "CR30"

    class _Dead:
        def ask(self, _cmd):
            raise ConnectionError("peripheral disconnected")

    d._t = _Dead()
    with pytest.raises(DeviceLost):
        d.read_next_measurement(timeout=5.0)
