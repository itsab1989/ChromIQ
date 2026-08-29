"""#159: a Bluetooth calibration took seconds it did not need to.

The owner: *"calibration via blutooth is much slower than via usb where it is
near instant"* — and he pointed out the vendor's own phone app does both
calibrations quickly over the same link, so the delay was ours.

It was, and it came from the event demultiplexer added a day earlier. A
calibration is acknowledged by a 10-byte `bb 11 …` / `bb 10 …` frame, and that
demux routes every well-formed 10-byte command frame to the EVENT queue — where
button presses live — instead of the reply buffer. So `ask()` sat waiting for
`_buf` to fill with something that could never arrive, and spent its entire poll
budget before giving up. Measured: 2.16 s for a calibration whose device-side
share is 0.31 s.

The same applies to the trigger, whose acknowledgement is a `bb 01 …` frame.
"""
from __future__ import annotations

import pytest

from workflow.cr30 import ble
from workflow.cr30.device import CR30


class _Link:
    """A transport that answers the way the real one does: the acknowledgement
    goes to the event queue, never to the reply buffer."""

    def __init__(self):
        self.polls = 0
        self._events: list[bytes] = []

    def ask(self, req, *, polls=10, wait=0.35, done=None):
        # The instrument acknowledges immediately, into the EVENT queue.
        self._events.append(ble.frame(req[1], 0x00))
        for _ in range(polls):
            self.polls += 1
            if done is not None and done(b""):
                break
        return b""

    def saw_event(self, cmd):
        for i, f in enumerate(self._events):
            if len(f) >= 2 and f[1] == cmd:
                del self._events[i]
                return True
        return False


def _dev(link):
    d = CR30.__new__(CR30)
    d.kind = "ble"
    d._t = link
    d._previous = None
    d.model = "CR30"
    return d


@pytest.mark.parametrize("black,cmd", [(False, 0x11), (True, 0x10)])
def test_a_calibration_stops_at_the_acknowledgement(black, cmd):
    link = _Link()
    _dev(link).calibrate(black=black)
    assert link.polls == 1, (
        f"{link.polls} poll cycles for one calibration — it is waiting for a "
        "reply that the demux sends somewhere else, and will wait out its "
        "whole budget")


def test_the_trigger_stops_at_its_acknowledgement_too():
    link = _Link()
    _dev(link).trigger_unsafe()
    assert link.polls == 1


def test_the_acknowledgement_is_consumed_not_left_lying_around():
    """An acknowledgement is not a button press. Left in the queue, the next
    armed patch would collect it as one and record a reading nobody took."""
    link = _Link()
    d = _dev(link)
    d.calibrate(black=False)
    assert link._events == [], (
        "the calibration's own acknowledgement is still in the event queue, "
        "where the next patch would mistake it for the operator's press")
