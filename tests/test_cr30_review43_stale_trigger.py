"""Review 43 (v4.1.5-beta.2): the keyboard-trigger request can go stale.

Three findings, each proven against the REAL objects — `CR30`,
`DeviceReader`, `Cr30MeasureBridge` — with only the transport faked, mirroring
the surface the real one has (`bytes_waiting`, `receive`, `transact`,
`wait_for_event`, `drop_events`, `ask`).

1. `DeviceReader._trigger_requested` is a session-wide flag with no owner.
   A Space press accepted while nothing is consuming it (the give-up state, or
   the instant around a click-to-jump) survives until the NEXT read starts —
   which then fires the instrument at whatever it is sitting on, unasked,
   while the operator may still be moving it to the new patch. A reading of
   the wrong surface that passes `check_usable` is recorded silently.

2. The tab's key-routing predicate (`bridge.awaiting_loc is not None`) is
   true in the give-up state, where no reader is listening — so Space is
   accepted, "Taking the reading — keep the instrument still." flashes, and
   nothing happens except the flag of finding 1 being set.

3. Over Bluetooth, `read_next_measurement(for_learning=True)` starts by
   dropping every queued event — including the very press the learning window
   asked for ("press the button on the instrument once" … "I have pressed
   it"). The press made before the click is discarded, and the learn waits in
   silence for presses nobody told the user to make.

ALL THREE ARE FIXED. The xfail(strict=True) markers they were written under did
their job -- each started failing the moment its fault was repaired -- and are
gone. What is left is a regression test for each.

Finding 1's fix went further than the review proposed: rather than clearing the
flag when a read ends, a request now needs a read to BELONG to, so one made
while nothing is listening is refused outright.

Finding 2's test was rewritten to drive the real `TabMeasure.eventFilter`. The
review's version asserted that `awaiting_loc` alone must mean "someone is
listening", which is a demand on the BRIDGE -- and the magnet remedy and the
read-failed window read that field after a failure on purpose. The tab asks
`armed_for` instead, and this proves the tab.
"""
from __future__ import annotations

import struct
import threading
import time
from collections import deque

import pytest

from workflow.cr30 import ble
from workflow.cr30.device import CR30
from workflow.cr30.measure_bridge import Cr30MeasureBridge, DeviceReader
from workflow.cr30.measurement import MeasurementError
from workflow.cr30.transport import TransportTimeout


class _Triggered(Exception):
    """Raised by the fake port the moment a trigger frame is written."""


class _SilentUsbPort:
    """A quiet instrument: nobody presses its button. Mirrors the real
    transport's surface the reader uses while waiting."""

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


# --- finding 1: a stale request fires on a patch nobody asked for ----------

def test_a_stale_trigger_request_does_not_fire_on_the_next_patch():
    """Space was accepted while no read was listening (or the read it was
    meant for was abandoned). The NEXT patch's read must wait for the
    operator, not fire the instrument the instant it starts.

    The review proposed clearing the flag whenever a read ends. The fix went
    further: a request now needs a read to BELONG to, so one made while nothing
    is listening is refused outright rather than kept and later spent. Hence
    the precondition below asserts False where the review's version asserted
    True — the behavioural assertion at the end is unchanged, and it is the one
    that matters.
    """
    port = _SilentUsbPort()
    dev = CR30(port, "usb")
    dev.learned_tile = [70.0] * 31        # the guard is armed: Space is legal

    reader = DeviceReader()
    reader._dev = dev                     # an opened session, as __call__ leaves it
    assert reader.request_trigger() is False, (
        "a trigger was accepted with no read waiting to collect it")

    # A new patch is armed. The operator has NOT pressed anything for it.
    with pytest.raises(MeasurementError):
        # the honest outcome is the button-press timeout
        dev.read_next_measurement(timeout=0.3,
                                  trigger_wanted=reader._take_trigger_request)
    assert not port.triggered, (
        "the stale Space press fired the instrument at whatever it was "
        "sitting on, without the operator asking")


# --- finding 2: the give-up state still invites Space ----------------------

def test_after_giving_up_the_key_routing_predicate_stops_inviting_space(qapp):
    """After the bridge gives up on a patch, nothing is listening — and the
    REAL key filter must not accept Space, or it flashes "Taking the reading"
    into a stalled session and plants a request nobody will collect.

    This drives `TabMeasure.eventFilter` itself, unbound over a stand-in, which
    is how the other CR30 tab tests reach it. The stand-in supplies only what
    the filter reads; the decision under test is made by the shipped method
    against the REAL `Cr30MeasureBridge` state, not by a re-stated predicate.

    Rewritten from the review's version, which asserted that `awaiting_loc`
    alone must equal "someone is listening". That is a demand on the BRIDGE
    (clear awaiting_loc on give-up), and other code — the magnet remedy, the
    read-failed window — reads that field after a failure on purpose. The tab
    was taught to ask `armed_for` instead, and this proves the tab.
    """
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent
    from ui.tabs.tab_measure import TabMeasure

    sent: list = []

    def reader():
        raise MeasurementError("refused")

    bridge = Cr30MeasureBridge(sent.append, reader)
    gave_up: list = []
    bridge.read_gave_up.connect(lambda loc, msg: gave_up.append(loc))
    bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    deadline = time.monotonic() + 10.0
    while not gave_up and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert gave_up == ["A1"], "the bridge never gave up; harness broken"
    qapp.processEvents()
    assert bridge.awaiting_loc is not None, (
        "harness broken: this test exists because awaiting_loc SURVIVES the "
        "give-up — if it did not, there would be nothing to guard against")

    took: list = []

    forwarded: list = []

    class _Manager:
        def send_key(self, k):
            forwarded.append(k)

    class _Tab:
        _session_live = True
        _cr30_bridge = bridge
        _cr30_reader = object()
        _manager = _Manager()

        def _cr30_reading_from_the_keyboard(self):
            took.append(True)

        def _arm_key_watchdog(self):
            pass

    tab = _Tab()
    space = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space,
                      Qt.KeyboardModifier.NoModifier, " ")
    TabMeasure.eventFilter(tab, qapp, space)
    assert not took, (
        "Space was accepted after the bridge gave up on the patch: nothing is "
        "listening, so the reading it promises can never arrive")
    assert forwarded == [" "], (
        "the key was claimed and then dropped; it must be left to the normal "
        f"path instead, but the manager saw {forwarded!r}")


def test_the_same_filter_DOES_take_space_while_a_patch_is_armed(qapp):
    """The mutation guard for the test above: a filter that never accepts Space
    would pass it vacuously and break the feature."""
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent
    from ui.tabs.tab_measure import TabMeasure

    waiting, release = threading.Event(), threading.Event()

    def reader(generation=None):
        waiting.set()
        # Wait like the real one does, but end ON DEMAND. A reader still
        # sleeping at teardown is destroyed with its QThread running, which is
        # the leak that produced intermittent xdist segfaults before.
        release.wait(5.0)
        raise MeasurementError("never")

    bridge = Cr30MeasureBridge(lambda *_: None, reader)
    bridge.on_patch_ready({"loc": "A1", "read": False, "all_done": False})
    assert waiting.wait(5.0), "harness broken: the reader never started"
    assert bridge.armed_for("A1"), "harness broken: the patch is not armed"

    took: list = []

    class _Manager:
        def send_key(self, k):
            pass

    class _Tab:
        _session_live = True
        _cr30_bridge = bridge
        _cr30_reader = object()
        _manager = _Manager()

        def _cr30_reading_from_the_keyboard(self):
            took.append(True)

        def _arm_key_watchdog(self):
            pass

    space = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space,
                      Qt.KeyboardModifier.NoModifier, " ")
    TabMeasure.eventFilter(_Tab(), qapp, space)
    assert took, "Space was refused while the patch was genuinely armed"
    release.set()
    bridge.stop()
    # `_threads` holds (QThread, worker) pairs, kept referenced until finished.
    # The thread ends through Qt's own quit/finished signalling, so the event
    # loop has to run for it -- `wait()` alone deadlocks against a queued quit.
    threads = [t for t, _w in list(getattr(bridge, "_threads", []))]
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and any(t.isRunning() for t in threads):
        qapp.processEvents()
        time.sleep(0.01)
    assert not any(t.isRunning() for t in threads), (
        "a reader thread outlived the test — destroyed while running, which "
        "is what produced the intermittent xdist segfaults")


# --- finding 3: BLE learning drops the press it asked for ------------------

def _ble_reply(values):
    raw = bytearray(ble.MEASUREMENT_HDR)
    raw += struct.pack(">H", 400) + bytes([10, 31])
    assert len(raw) == ble.SPECTRUM_AT
    raw += struct.pack("<31f", *values)
    raw += bytes(ble.LAB_AT - len(raw))
    raw += struct.pack("<3f", 90.0, 0.0, 0.0)
    raw += bytes(ble.MIN_REPLY - len(raw))
    return bytes(raw)


class _BlePort:
    """Mirrors the real BleTransport's event surface: a queue of unsolicited
    `bb 01 00` frames, `drop_events` clearing it, `wait_for_event` popping it,
    and `ask` returning the stored reply."""

    def __init__(self, queued_presses=1):
        self._events = deque(bytes(10) for _ in range(queued_presses))
        self.reply = _ble_reply([70.0 + i * 0.3 for i in range(31)])

    def drop_events(self):
        n = len(self._events)
        self._events.clear()
        return n

    def wait_for_event(self, timeout, cancelled=None, poll=0.05):
        if self._events:
            return self._events.popleft()
        time.sleep(min(timeout, 0.05))
        return None

    def ask(self, payload, polls=3, wait=0.35, done=None):
        return self.reply

    def close(self):
        pass


def test_ble_learning_collects_the_press_made_before_the_dialog_was_answered():
    """The window says: press the instrument's button once, then click
    "I have pressed it". Over Bluetooth that press is queued as an event while
    the dialog is up — and `read_next_measurement(for_learning=True)` begins
    by discarding every queued event, so the press the user was told to make
    is thrown away and the learn stalls in silence."""
    port = _BlePort(queued_presses=1)
    dev = CR30(port, "ble")
    m = dev.read_next_measurement(timeout=0.5, for_learning=True)
    assert m.values, "the press the dialog asked for was discarded"
