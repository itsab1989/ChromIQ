"""#159: ChromIQ calibrates the CR30 with the instrument's own commands.

It used to seat a magnet at the aperture and fire an ordinary trigger. That
works — EXP-BLE-015 showed it returns the tile constant — but it is a SIDE
EFFECT of the magnet gate rather than the manufacturer's method, and it can only
ever do white. The vendor sends a dedicated command for each, neither of which
goes near the magnet, and each performs its own acquisition.

Captured from the vendor's own traffic: USB frames in PRIORART-001, Bluetooth in
EXP-BLE-016. Verified on the owner's unit in EXP-022 (2026-08-29): both accepted,
~250 ms each, and a properly seated white calibration moved his paper reading
83.95 -> 88.37 %R, back into the band every other reading that evening sat in.
"""
from __future__ import annotations

import pytest

from workflow.cr30 import ble
from workflow.cr30.device import CR30


class _Usb:
    kind = "usb"

    def __init__(self):
        self.sent = []

    def send(self, frame):
        self.sent.append(frame.to_bytes())

    def receive(self, timeout=None):
        class _R:
            @staticmethod
            def to_bytes():
                return bytes([0xBB, 0x11, 0x00]) + bytes(57)
        return _R()


class _Ble:
    kind = "ble"

    def __init__(self):
        self.asked = []

    def ask(self, req, **kw):
        self.asked.append(bytes(req))
        return b""


def _dev(transport, kind):
    d = CR30.__new__(CR30)
    d.kind = kind
    d._t = transport
    d._previous = None
    d.model = "CR30"
    return d


def test_the_usb_frames_are_the_ones_the_vendor_sends():
    t = _Usb()
    d = _dev(t, "usb")
    d.calibrate(black=False)
    d.calibrate(black=True)
    assert len(t.sent) == 2
    assert t.sent[0][:4].hex(" ") == "bb 11 00 00"
    assert t.sent[1][:4].hex(" ") == "bb 10 00 00"
    assert len(t.sent[0]) == 60, "USB framing is 60 bytes"


def test_the_bluetooth_frames_match_the_captured_trace():
    """Byte-for-byte against the vendor app on the owner's unit, EXP-BLE-016."""
    t = _Ble()
    d = _dev(t, "ble")
    d.calibrate(black=False)
    d.calibrate(black=True)
    assert t.asked[0].hex(" ") == "bb 11 01 00 00 00 00 00 ff cc"
    assert t.asked[1].hex(" ") == "bb 10 01 00 00 00 00 00 ff cb"


def test_black_and_white_are_different_commands():
    """Obvious, and worth pinning: a flag that silently did white twice would
    leave the user believing they had a dark reference they never took."""
    t = _Ble()
    d = _dev(t, "ble")
    d.calibrate(black=False)
    d.calibrate(black=True)
    assert t.asked[0] != t.asked[1]


def test_the_old_entry_point_still_does_white():
    t = _Ble()
    d = _dev(t, "ble")
    d.calibrate_white()
    assert t.asked[0][1] == ble.frame(0x11, 0x01)[1]
