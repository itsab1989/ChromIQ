"""A keystroke must reach the instrument promptly, not on the next poll.

The trigger cannot be sent from the GUI thread -- the reader owns the link for
the whole of its wait, and two readers of one serial stream lose the reply to
whichever gets there first. So the keystroke sets a flag and the waiting reader
acts on it. That is correct, and it was SLOW: the reader sat inside `receive`
for up to a second at a time and only looked at the flag between blocks, so
Space cost up to 1 s and half a second on average. Basti, 2026-08-30, having
just used it: *"a tiny bit of delay there compared to the button press on the
instrument"*.

The fix is NOT a shorter `receive` timeout. A partial read is discarded
(`transport.receive`), so a window that ends mid-frame loses a real button press
and leaves its remainder to be mis-parsed. The reader now enters `receive` only
once bytes are actually arriving, and polls `bytes_waiting()` in between.

The real `CR30.read_next_measurement` is driven here. Only the transport is
faked -- the outermost edge -- and it mirrors the real one: `bytes_waiting`,
`receive`, `transact`.
"""
import time

import pytest

from workflow.cr30.device import CR30

#: How long the fake would block inside `receive`, i.e. what the loop used to
#: pay before it looked at the flag again. The real code passes min(left, 1.0).
BLOCKING_RECEIVE_S = 1.0

#: When the "keystroke" happens: after the reader is already inside its wait.
KEYSTROKE_AT_S = 0.03


class _Triggered(Exception):
    """Raised by the fake the moment a trigger frame is written."""


class _Port:
    """Mirrors the real transport's surface: bytes_waiting, receive, transact."""

    def __init__(self):
        self.triggered_at = None
        self.receives = 0

    # the instrument is quiet: nobody has pressed its button
    def bytes_waiting(self):
        return 0

    def receive(self, timeout=1.0, verify=True):
        self.receives += 1
        time.sleep(timeout)              # exactly what a quiet port costs
        from workflow.cr30.transport import TransportTimeout
        raise TransportTimeout("nothing arrived")

    def transact(self, frame, timeout=10.0, verify=True):
        self.triggered_at = time.monotonic()
        raise _Triggered()

    def drop_events(self):
        return 0


def _run(port, keystroke_at=KEYSTROKE_AT_S):
    dev = CR30(port, "usb")
    began = time.monotonic()

    def trigger_wanted():
        return time.monotonic() - began >= keystroke_at

    with pytest.raises(_Triggered):
        dev.read_next_measurement(timeout=5.0, trigger_wanted=trigger_wanted)
    return began, port.triggered_at


def test_the_trigger_goes_out_promptly_after_the_keystroke():
    port = _Port()
    began, at = _run(port)
    assert at is not None, "the trigger was never sent"
    delay = at - began
    # Generous: the point is that it is nowhere near a blocking receive.
    assert delay < BLOCKING_RECEIVE_S / 2, (
        f"the keystroke took {delay*1000:.0f} ms to reach the instrument; "
        "the reader is still blocking inside receive before checking")


def test_it_did_not_get_there_by_skipping_the_wait_entirely():
    """The mutation guard: a reader that never waits would pass the test above
    vacuously, and would also spin the CPU. It must still be waiting."""
    port = _Port()
    began, at = _run(port, keystroke_at=0.25)
    assert at - began >= 0.25, "the trigger went out before the keystroke did"


def test_a_quiet_port_is_not_entered_for_a_blocking_read():
    """The whole mechanism: while nothing is arriving, `receive` is not called
    at all. If it were, the flag could only be seen a second later."""
    port = _Port()
    _run(port)
    assert port.receives == 0, (
        f"receive() was entered {port.receives} time(s) on a silent port")


class _OlderPort(_Port):
    """A transport with no `bytes_waiting` AT ALL -- the honest shape of the
    problem. A method that RAISES is a different thing: pyserial raises from
    `in_waiting` on a port that has gone, and that really is a lost instrument,
    so it must keep meaning that."""

    bytes_waiting = None                  # not merely absent: shadowed away

    def __getattribute__(self, name):
        if name == "bytes_waiting":
            raise AttributeError(name)
        return object.__getattribute__(self, name)


def test_a_transport_that_cannot_say_is_not_a_lost_instrument():
    """A missing accessor must fall back to the blocking read, never be read as
    a disconnection -- that mistake would end a session on a healthy device."""
    port = _OlderPort()
    from workflow.cr30.device import DeviceLost
    dev = CR30(port, "usb")
    began = time.monotonic()
    try:
        dev.read_next_measurement(timeout=0.2,
                                  trigger_wanted=lambda: False)
    except DeviceLost:
        pytest.fail("a transport that cannot report waiting bytes was "
                    "reported as a disconnected instrument")
    except Exception:
        pass                              # a timeout is the honest outcome
    assert port.receives >= 1, "it never fell back to the blocking read"
