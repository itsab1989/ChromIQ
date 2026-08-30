"""Re-check of review 43, fix 1: the OTHER half of the contract.

`request_trigger()` refusing while nothing is listening is half the fix, and
`tests/test_cr30_review43_stale_trigger.py` proves it. This proves the half
that test can no longer see: a request that WAS legitimately accepted (a read
in flight) but never consumed — the read was abandoned, failed, or ended in
the microsecond between the GUI's in-flight check and its flag write — must be
cleared by that read's `finally`, never inherited by the next one.

Without this file, deleting `self._trigger_requested = False` from
`DeviceReader.__call__`'s finally block passes the entire suite, because no
other test ever leaves a flag pending when a read exits.

The flag is planted directly, and deliberately so: `request_trigger()` itself
now refuses when no read is in flight, so the ONLY way this state arises in
production is the documented race remnant (Space landing in the instant the
read ends). The test reproduces the remnant, not the API call.
"""
from __future__ import annotations

import time

import pytest

from workflow.cr30.device import CR30
from workflow.cr30.measure_bridge import DeviceReader
from workflow.cr30.measurement import MeasurementError
from workflow.cr30.transport import TransportTimeout


class _Triggered(Exception):
    pass


class _SilentUsbPort:
    """Mirrors the surface the reader uses while waiting; nobody presses."""

    def __init__(self):
        self.triggered = False

    def bytes_waiting(self):
        return 0

    def receive(self, timeout=1.0, verify=True):
        time.sleep(min(timeout, 0.05))
        raise TransportTimeout("nothing arrived")

    def transact(self, frame, timeout=10.0, verify=True):
        self.triggered = True
        raise _Triggered()

    def close(self):
        pass


def test_a_request_pending_when_its_read_dies_is_cleared_by_that_read():
    port = _SilentUsbPort()
    dev = CR30(port, "usb")
    dev.learned_tile = [70.0] * 31          # guard armed: the flag is reachable

    reader = DeviceReader()
    reader._dev = dev
    # The race remnant: a request accepted in the instant before the read
    # ended, left unconsumed. request_trigger() cannot create it any more, so
    # plant it as the race would leave it.
    reader._trigger_requested = True
    # The read starts already abandoned — the generation moved on — so its
    # very first loop iteration raises, BEFORE the trigger flag is looked at.
    stale_generation = reader.abandon_current() - 1
    with pytest.raises(MeasurementError):
        reader(stale_generation)
    assert not port.triggered, (
        "the dying read spent the flag itself; the scenario under test is a "
        "flag that outlives its read, and the harness failed to create it")
    assert reader._trigger_requested is False, (
        "the read exited with the request still pending — the finally block "
        "no longer clears it, and the next read will fire unasked")
    # The in-flight latch must have dropped too, or an idle reader accepts
    # new requests with nothing listening.
    assert reader.request_trigger() is False, (
        "_reading_in_flight leaked True past the read's exit")
    # And the next read must wait for the operator, not fire on arrival.
    with pytest.raises(MeasurementError):
        dev.read_next_measurement(timeout=0.3,
                                  trigger_wanted=reader._take_trigger_request)
    assert not port.triggered, (
        "a request left over from an abandoned read fired the instrument at "
        "whatever it was sitting on")


def test_a_request_during_a_live_read_is_accepted_and_fires_exactly_once():
    """The accept direction, at the READER level. The tab-level mutation guard
    proves the filter forwards Space; nothing proved `request_trigger` ever
    says yes — a mutation that never sets `_reading_in_flight` would kill the
    feature and pass the whole suite. This drives a real read on a worker
    thread, requests mid-wait, and requires the trigger frame to reach the
    port."""
    import threading

    port = _SilentUsbPort()
    dev = CR30(port, "usb")
    dev.learned_tile = [70.0] * 31

    reader = DeviceReader()
    reader._dev = dev
    outcome: list = []

    def run():
        try:
            reader(None)
        except Exception as exc:        # noqa: BLE001 — recorded for the assert
            outcome.append(exc)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    accepted = False
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if reader.request_trigger():
            accepted = True
            break
        time.sleep(0.005)
    assert accepted, ("request_trigger never said yes while a read was "
                      "genuinely waiting — the keyboard feature is dead")
    t.join(5.0)
    assert not t.is_alive(), "the read never ended; harness broken"
    assert port.triggered, "the accepted request never sent the trigger frame"
    assert isinstance(outcome[0], _Triggered), (
        f"the read ended for the wrong reason: {outcome[0]!r}")
    assert reader._trigger_requested is False, "the request outlived its read"
