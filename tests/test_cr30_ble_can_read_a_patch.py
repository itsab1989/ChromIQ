"""#159 (Basti, 2026-08-28): over Bluetooth the CR30 could never read a patch.

He connected over BLE, started a measurement, pressed the instrument's button
twice — and the app recorded nothing. His log shows the device answering
(three notifications on ffe1 at 22:32:57, 22:33:15, 22:33:17) with the app no
longer listening.

The cause was one line of bookkeeping. `read_measurement()` stored every
reading in `self._previous`, including the `enforce=False` probes the BLE wait
polls with. The wait then called `m.check_usable(self._previous)` — and by
then `self._previous` WAS `m`. `identical_to` compared the reading to itself,
returned True, and raised "reading is bit-identical to the previous one" on
the very first patch. USB was unaffected: it waits on a button header and never
takes that branch, which is why the same session read 15 patches over USB.

Behind it sat a second fault the first one masked: with no accepted reading
yet, `prev` was None and the loop accepted whatever the device already held —
the stale-cache bug the method's own docstring exists to prevent (patch A1
took the white-tile cache at delta E 60.5).
"""
from __future__ import annotations

import struct

import pytest

from workflow.cr30 import ble
from workflow.cr30.device import CR30, MeasurementError


def _reply(values) -> bytes:
    """A real BLE 'read stored measurement' reply, so the production parser
    and the production guard both run — stubbing read_measurement itself would
    stub out the very line the bug lived on."""
    buf = bytearray(200)
    buf[0:4] = ble.MEASUREMENT_HDR
    struct.pack_into(">H", buf, 4, 400)          # start nm
    buf[6] = 10                                   # step nm
    buf[7] = 31                                   # bands
    struct.pack_into("<31f", buf, ble.SPECTRUM_AT, *values)
    struct.pack_into("<3f", buf, ble.LAB_AT, 50.0, 1.0, -1.0)
    return bytes(buf)


class _Link:
    """A device answering with a genuinely different spectrum every read,
    after `changes_after` identical ones."""

    def __init__(self, changes_after: int = 0):
        self.reads = 0
        self._changes_after = changes_after

    def ask(self, _cmd):
        self.reads += 1
        n = self.reads if self.reads > self._changes_after else 1
        return _reply([10.0 + 0.5 * n + 0.01 * i for i in range(31)])


def _device(link) -> CR30:
    d = CR30.__new__(CR30)
    d.kind = "ble"
    d._t = link
    d._previous = None
    d.model = "CR30"
    return d


def test_a_changing_instrument_can_be_read_over_ble():
    """The bug: this raised on the FIRST patch, every time, over Bluetooth."""
    link = _Link()
    d = _device(link)
    m = d.read_next_measurement(timeout=5.0, poll=0.0)
    assert m is not None
    # A second patch must work too — the first must have left the reading it
    # ACCEPTED as the baseline, not the probe it polled with.
    m2 = d.read_next_measurement(timeout=5.0, poll=0.0)
    assert m2.values != m.values


def test_it_waits_instead_of_taking_what_the_device_already_holds():
    """With nothing accepted yet there is no baseline, and the reading sitting
    in the device belongs to whatever was measured last — not to this patch."""
    link = _Link(changes_after=4)
    d = _device(link)
    d.read_next_measurement(timeout=5.0, poll=0.0)
    assert link.reads > 4, (
        "returned the value the device was already holding instead of waiting "
        "for a new one")


def test_the_guard_still_catches_a_genuinely_repeated_reading():
    """The fix must not disarm the check it was breaking: a device that never
    changes must still be refused, not accepted."""
    link = _Link(changes_after=10_000)
    d = _device(link)
    with pytest.raises(MeasurementError):
        d.read_next_measurement(timeout=0.4, poll=0.0)
