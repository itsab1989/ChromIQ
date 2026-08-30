"""#159: reading a patch over Bluetooth.

Two faults were fixed here, and the second replaced the mechanism entirely.

FIRST (2026-08-28): every reading was compared against itself. `read_measurement`
stored every reading in `_previous`, including the probes the wait polled with,
so `check_usable(self._previous)` compared the reading to ITSELF, `identical_to`
returned True, and the first patch of every Bluetooth session raised
"bit-identical to the previous one". A CR30 could not read one patch over BLE.

SECOND (2026-08-29): the wait itself was guesswork. With no press event known on
Bluetooth, it polled the stored value and called a change a press. That cannot
tell one press from three, cannot see two presses that produced the same colour,
and anything slow slides a reading onto whichever patch is armed by the time it
is noticed. The owner measured the result — a colour meant for A19 recorded
against A20, delta E 73.4 — and described it as "nothing for a while, then
suddenly a few measurements are recognized (and then for the wrong patches)".

EXP-BLE-013 disproved the premise: the instrument pushes a 10-byte
`bb 01 00 …` frame whenever it acts. Three presses, three frames, control phases
silent, nothing sent to the device. So the wait is now for that event, and the
readings that used to be inferred are simply collected.
"""
from __future__ import annotations

import struct

import pytest

from workflow.cr30 import ble
from workflow.cr30.device import CR30, MeasurementError

EVENT = bytes.fromhex("bb01000001900a1fff75")     # a real one, from his unit


def _reply(values) -> bytes:
    """A real BLE 'read stored measurement' reply, so the production parser and
    the production guard both run."""
    buf = bytearray(200)
    buf[0:4] = ble.MEASUREMENT_HDR
    struct.pack_into(">H", buf, 4, 400)
    buf[6], buf[7] = 10, 31
    struct.pack_into("<31f", buf, ble.SPECTRUM_AT, *values)
    struct.pack_into("<3f", buf, ble.LAB_AT, 50.0, 1.0, -1.0)
    return bytes(buf)


class _Link:
    """A transport that answers reads, and can be told the instrument acted."""

    def __init__(self):
        self.reads = 0
        self._events: list[bytes] = []      # already delivered, before arming
        self._deferred: list[bool] = []     # will arrive DURING the wait
        self._n = 1

    # the instrument's side
    def press_before_arming(self):
        """A press with nothing listening. It belongs to no patch."""
        self._n += 1
        self._events.append(EVENT)

    def press(self, changes_colour: bool = True):
        """A press while the patch is armed — the ordinary case."""
        self._deferred.append(changes_colour)

    # the transport's side
    def wait_for_event(self, timeout, cancelled=None, poll=0.01):
        """Deliver ONLY from inside a running asyncio loop, exactly as the real
        transport does.

        This is not decoration. bleak hands notifications to the loop with
        `call_soon_threadsafe`, so a wait that does not run the loop receives
        nothing at all — the first version of this rework waited with plain
        `sleep`, every press queued invisibly and every patch timed out after
        three minutes. The tests missed it because they fed the queue directly
        and never went through a transport. A stub that can be satisfied
        without a loop would miss it again.
        """
        import asyncio

        async def _wait():
            import time as _t
            deadline = _t.monotonic() + timeout
            while True:
                if self._events:
                    return self._events.pop(0)
                if self._deferred:
                    if self._deferred.pop(0):
                        self._n += 1
                    return EVENT
                if cancelled is not None and cancelled():
                    return None
                if _t.monotonic() > deadline:
                    return None
                await asyncio.sleep(poll)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_wait())
        finally:
            loop.close()

    def drop_events(self):
        """Only what has already arrived. A press still to come is not ours to
        throw away — that is the whole point of arming."""
        n = len(self._events)
        self._events.clear()
        return n

    def ask(self, _cmd, **_kw):
        self.reads += 1
        return _reply([10.0 + 0.5 * self._n + 0.01 * i for i in range(31)])


def _device(link) -> CR30:
    """Build it through the REAL constructor.

    This used to be `CR30.__new__(CR30)` with the fields set by hand, which
    silently drifts from the real object every time one is added -- it broke on
    `learned_tile` the day that field appeared, reporting the code faulty when
    only the stand-in was. `__init__` opens nothing; it just assigns.
    """
    d = CR30(link, "ble")
    d.model = "CR30"
    return d


def test_a_press_is_what_produces_a_reading():
    link = _Link()
    d = _device(link)
    link.press()
    m = d.read_next_measurement(timeout=5.0, poll=0.0)
    assert m is not None

    link.press()
    m2 = d.read_next_measurement(timeout=5.0, poll=0.0)
    assert m2.values != m.values


def test_without_a_press_nothing_is_returned():
    """The stale-cache fault, now structurally impossible: the device is
    holding a perfectly readable value and it belongs to no patch here."""
    link = _Link()
    d = _device(link)
    with pytest.raises(MeasurementError) as e:
        d.read_next_measurement(timeout=0.4, poll=0.0)
    assert "button" in str(e.value).lower()
    assert link.reads == 0, (
        "it read the device without the instrument ever acting — that is the "
        "stale value, attributed to whatever patch happens to be armed")


def test_a_press_made_before_the_patch_was_armed_is_discarded():
    """The mis-attribution, at its source. A press with nothing listening
    belongs to no patch we can name, so it must not be collected later and
    charged to the next one."""
    link = _Link()
    d = _device(link)
    link.press_before_arming()        # nothing was listening
    link.press_before_arming()
    with pytest.raises(MeasurementError):
        d.read_next_measurement(timeout=0.4, poll=0.0)
    assert link.reads == 0, "a press from before this patch was collected"


def test_two_presses_are_two_readings_even_when_the_colour_repeats():
    """What polling could never see: the operator reads two patches that happen
    to be the same colour. The change-detector saw one press; the event sees
    two, and the guard is then free to judge the repeat on its merits."""
    link = _Link()
    d = _device(link)
    link.press()
    first = d.read_next_measurement(timeout=5.0, poll=0.0)
    assert first is not None
    link.press(changes_colour=False)
    with pytest.raises(MeasurementError) as e:
        d.read_next_measurement(timeout=5.0, poll=0.0)
    # Match what the refusal MEANS, not one word of its wording. This asserted
    # on "identical", which was jargon the user-facing text has since dropped —
    # so a message improvement failed a test about the guard's behaviour.
    assert "same numbers" in str(e.value).lower(), (
        "the second press was not even looked at")


def test_a_busy_instrument_is_waited_out_not_failed():
    """Reading too soon after the instrument acts returns a zero-filled reply.
    That is the device saying 'not finished', not a bad reading — the owner's
    calibration failed on exactly this, 1.8 s after the trigger."""
    link = _Link()
    calls = {"n": 0}
    real_ask = link.ask

    def _busy_then_ready(cmd, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _reply([0.0] * 31)          # the busy, zero-filled form
        return real_ask(cmd, **kw)

    link.ask = _busy_then_ready
    d = _device(link)
    link.press()
    m = d.read_next_measurement(timeout=8.0, poll=0.0)
    assert m is not None
    assert calls["n"] >= 2, "it gave up on the first busy reply"


def test_it_waits_through_the_transport_not_by_polling_a_queue():
    """The blocker this rework shipped with, pinned.

    bleak delivers notifications through the asyncio loop, so a wait built from
    `take_event()` and `sleep` receives nothing over real Bluetooth however long
    it waits: every press queues invisibly and the patch times out after three
    minutes. The gate stayed green because the tests fed the queue directly.

    This transport offers ONLY `wait_for_event`. If the wait ever goes back to
    peeking at a queue, it will not find one.
    """
    link = _Link()
    assert not hasattr(link, "take_event")
    d = _device(link)
    link.press()
    assert d.read_next_measurement(timeout=5.0, poll=0.0) is not None
