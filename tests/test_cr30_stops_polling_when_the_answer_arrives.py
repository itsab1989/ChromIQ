"""#159: a second of dead waiting on every patch.

Measured on the owner's unit, one press-to-recorded cycle:

    08.135  the press event arrives
    08.577  we ask for the reading
    08.857  THE REPLY IS ALREADY HERE          (+280 ms — the device is quick)
    08.928  poll   09.280  poll   09.631  poll (+1.05 s of confirming silence)
    09.985  the measurement finally reaches the chart

The transport waited for three consecutive quiet rounds before believing the
reply was finished — over a second spent on data it already held. On a
390-patch chart that is nearly seven minutes.

The stop rule has to be the FULL validation and nothing weaker. The vendor's own
capture is a truncated, zero-filled reply followed by a complete one, and both
pass every length, header and checksum test; that is why the parser collects
every candidate and keeps the last that survives. A "looks finished, stop" rule
would take the bad one and report a corrupt reading as a measurement.
"""
from __future__ import annotations

import struct

from workflow.cr30 import ble
from workflow.cr30.device import _parse_reply


def _reply(values, at=0, total=None):
    total = total or (at + 200)
    buf = bytearray(total)
    buf[at:at + 4] = ble.MEASUREMENT_HDR
    struct.pack_into(">H", buf, at + 4, 400)
    buf[at + 6], buf[at + 7] = 10, 31
    struct.pack_into("<31f", buf, at + ble.SPECTRUM_AT, *values)
    struct.pack_into("<3f", buf, at + ble.LAB_AT, 50.0, 1.0, -1.0)
    return bytes(buf)


GOOD = [10.0 + 0.5 * i for i in range(31)]


def test_a_complete_reply_is_recognised():
    assert _parse_reply(_reply(GOOD)) is not None


def test_a_partial_reply_is_not_enough_to_stop_on():
    """Half a reply arrives first over the air; stopping there would report a
    truncated frame as a reading."""
    whole = _reply(GOOD)
    for cut in (20, 100, ble.MIN_REPLY - 1):
        assert _parse_reply(whole[:cut]) is None, f"stopped after {cut} bytes"


def test_the_truncated_half_of_a_double_reply_is_rejected():
    """The exact shape in the vendor capture, and the reason the rule cannot be
    a length or a checksum: a zero-filled reply that is otherwise perfectly
    well formed, followed by the real one."""
    zeros = _reply([0.0] * 31)
    assert _parse_reply(zeros) is None, (
        "a zero-filled reply was accepted — this is the frame that would be "
        "recorded as a patch colour")
    both = zeros + _reply(GOOD)
    assert _parse_reply(both) is not None
    assert _parse_reply(both) >= len(zeros), (
        "it took the truncated first half instead of the complete second")


def test_nothing_at_all_is_not_a_reply():
    assert _parse_reply(b"") is None
    assert _parse_reply(b"\x00" * 400) is None
