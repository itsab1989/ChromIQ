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
        self._last_n = 1
        self._changes_after = changes_after

    frozen = False

    def ask(self, _cmd):
        self.reads += 1
        if self.frozen:
            n = self._last_n
        else:
            n = self.reads if self.reads > self._changes_after else 1
            self._last_n = n
        return _reply([10.0 + 0.5 * n + 0.01 * i for i in range(31)])


def _device(link) -> CR30:
    d = CR30.__new__(CR30)
    d.kind = "ble"
    d._t = link
    d._previous = None
    # The last spectrum the device was SEEN holding — distinct from the last
    # one ACCEPTED. Enumerated here because this builds the device with
    # __new__, so __init__ never runs.
    d._last_seen = None
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


def test_a_refused_reading_does_not_burn_the_next_wait():
    """A refused reading must still count as "the button was pressed".

    Measured before the fix: a refusal left the change-detection baseline
    pointing at the last ACCEPTED patch, so the device's stored value — the
    very reading that had just been refused — already differed from it. The
    next wait therefore ended INSTANTLY with nobody pressing anything, the same
    reading was refused again, and the bridge's whole retry budget went in
    0.8 ms. The user pressed once and was told ChromIQ had "tried several
    times".
    """
    import time
    link = _Link()
    d = _device(link)
    first = d.read_next_measurement(timeout=5.0, poll=0.0)   # A1 accepted
    assert first is not None

    # A2: the device now holds something the guard will refuse. Simulate the
    # refusal the way check_usable does — it raises out of the wait.
    from workflow.cr30 import measurement as meas
    calls = {"n": 0}
    real = meas.Measurement.check_usable

    def _refuse_once(self, prev):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MeasurementError("the magnet gate is set")
        return real(self, prev)

    meas.Measurement.check_usable = _refuse_once
    try:
        with pytest.raises(MeasurementError):
            d.read_next_measurement(timeout=5.0, poll=0.0)
        reads_before = link.reads
        # The device has NOT changed since — nobody pressed anything.
        link.frozen = True
        t0 = time.monotonic()
        with pytest.raises(MeasurementError) as e:
            d.read_next_measurement(timeout=0.5, poll=0.0)
        assert "no new reading" in str(e.value), (
            f"the wait ended on something other than a timeout: {e.value}")
        assert time.monotonic() - t0 > 0.3, (
            "the wait returned instantly on a reading nobody re-took — the "
            "retry budget would be gone before the user could react")
        assert link.reads > reads_before
    finally:
        meas.Measurement.check_usable = real
