"""#159: a Bluetooth calibration took seconds it did not need to.

The owner: *"calibration via blutooth is much slower than via usb where it is
near instant"* — and he pointed out the vendor's own phone app does both
calibrations quickly over the same link, so the delay was ours.

It was, and it came from the event demultiplexer added a day earlier: `ask()`
waited for three silent poll rounds over an answer already in hand.

⚠ THE FIRST FIX FOR THIS WAS A PLACEBO, AND THESE TESTS ARE WHY IT SURVIVED.
They used a fake transport that re-implemented `ask` — without the guard the
real one had, and delivering the acknowledgement to the queue the fix happened
to read. Every assertion passed against a device that behaved as the fix
assumed, while the real transport did two other things:

* a calibration is acknowledged by `bb 11 …` / `bb 10 …`, and the demux routes
  a frame to the event queue only when its command byte is 0x01 — so that
  acknowledgement lands in the reply BUFFER, and `saw_event` was asking the
  wrong queue;
* a TRIGGER's acknowledgement does go to the queue, which leaves the reply
  buffer empty — and the real loop would not even call the predicate unless the
  buffer had something in it.

So every poll still ran, and the trigger's acknowledgement was left lying in the
queue for the next armed patch to collect as a stray press.

These tests now drive the REAL `BleTransport._ask` and the REAL demux. The only
thing stubbed is the radio underneath and the passage of time.
"""
from __future__ import annotations

import asyncio

import pytest

from workflow.cr30 import ble
from workflow.cr30.device import CR30


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    """Time passes instantly. Everything else is the real code."""
    async def _instant(_seconds):
        return None
    monkeypatch.setattr(ble.asyncio, "sleep", _instant)


class _Radio:
    """The instrument's side of the link: it acknowledges a command, and the
    acknowledgement is handed to the transport's own demultiplexer — so what
    the test exercises is the routing the device really provokes, not a
    routing chosen to suit the fix.
    """

    def __init__(self, transport, reply):
        self._t = transport
        self._reply = reply
        self._pending = None
        self.polls = 0

    async def write_gatt_char(self, _char, data, response=False):
        data = bytes(data)
        if data == ble.POLL:
            self.polls += 1
            if self._pending is not None:
                self._t._on_notify(None, self._pending)   # the real demux
                self._pending = None
            return
        self._pending = self._reply       # the command; the answer follows


def _transport(reply):
    t = ble.BleTransport.__new__(ble.BleTransport)
    t._buf = bytearray()
    from collections import deque
    t._events = deque(maxlen=64)
    t._client = _Radio(t, reply)
    return t


def _device(transport):
    d = CR30.__new__(CR30)
    d.kind = "ble"
    d._t = transport
    d._previous = None
    d.model = "CR30"
    return d


def _run(transport, coro):
    return asyncio.run(coro)


# -- what the device actually sends back ---------------------------------
#
# The calibration reply is taken from the vendor's own Bluetooth trace of this
# unit (EXP-BLE-016): `bb 11 00 11 …` for white, `bb 10 00 1c …` for black.
# Byte 3 varies between runs and means nothing we have determined, so the
# fixtures below vary it too — anything that keyed on it would be reading a
# field we cannot explain.
def _cal_reply(cmd, varying):
    d = bytearray(ble.FRAME_LEN)
    d[0], d[1], d[2], d[3] = 0xBB, cmd, 0x00, varying
    d[ble.MARKER_AT] = 0xFF
    d[9] = ble.checksum(d)
    return bytes(d)


@pytest.mark.parametrize("black,cmd,varying", [(False, 0x11, 0x11),
                                               (False, 0x11, 0x0A),
                                               (True, 0x10, 0x1C),
                                               (True, 0x10, 0x0F)])
def test_a_calibration_stops_at_the_acknowledgement(black, cmd, varying):
    """One poll, not the whole budget — through the real loop."""
    t = _transport(_cal_reply(cmd, varying))
    monkey = {}

    async def _go():
        return await t._ask(ble.frame(cmd, 0x01), 6, 0.35,
                            lambda _b: t.saw_reply(cmd))
    asyncio.run(_go())
    assert t._client.polls == 1, (
        f"the calibration spent {t._client.polls} of 6 polls waiting for an "
        "answer it already had")


@pytest.mark.parametrize("black,cmd", [(False, 0x11), (True, 0x10)])
def test_the_calibration_acknowledgement_lands_in_the_buffer(black, cmd):
    """The routing the placebo fix got backwards, asserted directly.

    If this ever fails the other way — the acknowledgement arriving as an
    event — then `saw_reply` is the wrong question and the speed-up is silently
    gone again, which is exactly how this was missed the first time.
    """
    t = _transport(_cal_reply(cmd, 0x11))
    t._on_notify(None, _cal_reply(cmd, 0x11))
    assert not t._events, "a calibration reply is not a button press"
    assert t.saw_reply(cmd), "the calibration reply is not where saw_reply looks"


def test_a_calibration_runs_the_real_ask_through_the_device():
    """End to end: CR30.calibrate over BLE, with only the radio stubbed."""
    t = _transport(_cal_reply(0x11, 0x11))
    sent = []

    def _ask(req, *, polls=10, wait=0.35, done=None):
        sent.append(bytes(req))
        return asyncio.run(t._ask(req, polls, wait, done))
    t.ask = _ask
    _device(t).calibrate(black=False)
    assert sent and sent[0][1] == 0x11, "the white calibration command"
    assert t._client.polls == 1, "it waited past its own answer"


def test_the_trigger_stops_even_though_the_buffer_stays_empty():
    """The guard that made the predicate unreachable.

    A trigger IS acknowledged as an event, so the reply buffer never fills. The
    loop used to require a non-empty buffer before it would even ask, so it ran
    every poll — over a device that had answered on the first one.
    """
    t = _transport(ble.frame(0x01, 0x00))

    async def _go():
        return await t._ask(ble.TRIGGER_UNSAFE, 4, 0.35,
                            lambda _b: t.saw_event(0x01))
    asyncio.run(_go())
    assert not t._buf, "this case only means something with an empty buffer"
    assert t._client.polls == 1, (
        f"the trigger spent {t._client.polls} of 4 polls with the answer "
        "already in the event queue")


def test_the_trigger_acknowledgement_is_consumed_not_left_lying_around():
    """Otherwise the next armed patch collects it as a press that never was.

    `drop_events` counts what it discards and reports it to the operator as
    "a reading was taken before ChromIQ was ready" — a warning about their own
    conduct, provoked entirely by our own trigger.
    """
    t = _transport(ble.frame(0x01, 0x00))

    async def _go():
        return await t._ask(ble.TRIGGER_UNSAFE, 4, 0.35,
                            lambda _b: t.saw_event(0x01))
    asyncio.run(_go())
    assert not t._events, (
        "our own trigger's acknowledgement was left in the queue; the next "
        "patch would be told the operator pressed too early")


def test_a_predicate_is_safe_on_an_empty_buffer():
    """The guard was removed, so every predicate now sees b"" at least once."""
    from workflow.cr30.device import _parse_reply
    assert _parse_reply(b"") is None
