"""A press of the CR30's button made once the spot window says Ready is TAKEN.

THE FAULT (beta 17 review, 2026-10-09). Tools ▸ Read single patches said Ready
the moment the session started, and only then did the reader thread reach
`CR30.read_next_measurement`, whose first act over Bluetooth is to throw away
every press the instrument had announced so far (`BleTransport.drop_events`).
A press made in that gap -- measured on the simulated radio at up to about a
second -- was the first thing it threw away. The log said "discarded 1 reading
taken before this patch was armed"; the window said nothing, and the press
simply did not count. Basti's "one reading took noticeably longer" was very
likely this: the second press is the one that counted.

And the drop ran again at the start of EVERY read, so the same gap opened after
each reading, after a refused one, and every 30 s when an idle wait is re-armed.

THE FIX. The stale presses are dropped ONCE per arming, before the window says
Ready (`DeviceReader.drop_stale_presses`, called by the read loop before it
announces itself), and not again while the session stays armed. A press the
instrument announced before Ready still goes, and the window says so in its
log; a press after Ready is collected, however soon after.

The radio is simulated (bleak replaced, ChromIQ's `BleTransport`, `CR30`,
`DeviceReader`, `Cr30SpotManager` and `SpotReadDialog` are the shipped code).
Two ways of delivering a press are covered: straight into the event queue, and
the way bleak really does it, as a callback queued on the transport's asyncio
loop that only runs when somebody pumps that loop. USB is covered with a
simulated serial port. No real instrument is ever opened.
"""
from __future__ import annotations

import os
import struct
import threading
import time
from collections import deque

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from core import instrument_lease                              # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from workflow.cr30 import ble, tile_learning, usb_measure      # noqa: E402
from workflow.cr30.device import CR30                          # noqa: E402
from workflow.cr30.frame import FRAME_SIZE, Frame              # noqa: E402
from workflow.cr30.measure_bridge import DeviceReader          # noqa: E402
from workflow.cr30.transport import (Transport,                # noqa: E402
                                     TransportTimeout)

#: The delays after Ready that the review measured and Basti's report implies.
DELAYS = (0.0, 0.2, 0.5, 1.0)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean():
    s = AppSettings()
    s.set(tile_learning.SIGNATURE_KEY, "")
    s.set("spot_read_instrument", "auto")
    instrument_lease.release(instrument_lease.holder_object())
    yield
    s.set(tile_learning.SIGNATURE_KEY, "")
    s.set("spot_read_instrument", "auto")
    instrument_lease.release(instrument_lease.holder_object())


# ---------------------------------------------------------------------------
# A Bluetooth radio, simulated
# ---------------------------------------------------------------------------
def _frame10(cmd, sub=0, b3=0):
    d = bytearray(10)
    d[0], d[1], d[2], d[3] = 0xBB, cmd, sub, b3
    d[8] = 0xFF
    d[9] = sum(d[:-1]) % 256
    return bytes(d)


def _ble_reading_reply(values):
    d = bytearray(200)
    d[0:4] = ble.MEASUREMENT_HDR
    d[4:6] = struct.pack(">H", 400)
    d[6], d[7] = 10, 31
    struct.pack_into("<31f", d, ble.SPECTRUM_AT, *values)
    struct.pack_into("<3f", d, ble.LAB_AT, 50.0, 0.0, 0.0)
    d[-1] = sum(d[:-1]) % 256
    return bytes(d)


class _Radio:
    """Stands in for bleak's client. A press stores a new reading and announces
    it with the 10-byte `bb 01 00` frame, as Basti's unit does (EXP-BLE-013)."""

    def __init__(self, t, *, via_loop: bool):
        self.t = t
        self.via_loop = via_loop
        self.stored = [5.0 + i * 0.5 for i in range(31)]
        self.disconnected = False

    async def write_gatt_char(self, _c, data, response=False):
        if bytes(data) == ble.READ_MEASUREMENT:
            self.t._on_notify(None, bytearray(_ble_reading_reply(self.stored)))

    async def stop_notify(self, _c):
        pass

    async def disconnect(self):
        self.disconnected = True

    def press(self, level: float) -> None:
        self.stored = [level + i * 0.37 for i in range(31)]
        frame = bytearray(_frame10(0x01))
        loop = self.t._loop
        if self.via_loop and loop is not None:
            # What bleak does: the radio's thread queues the callback on the
            # transport's loop, and it runs when that loop is next pumped.
            loop.call_soon_threadsafe(self.t._on_notify, None, frame)
        else:
            self.t._on_notify(None, frame)


def _ble_device(via_loop=False):
    t = ble.BleTransport.__new__(ble.BleTransport)
    t.name, t.address, t.timeout = "CM454M0223", "SIM-ADDRESS", 5.0
    t._buf, t._events, t._loop, t._lost = bytearray(), deque(maxlen=64), None, False
    radio = _Radio(t, via_loop=via_loop)
    t._client = radio
    # The loop exists from the connect on, as it does after a real open.
    t._loop = __import__("asyncio").new_event_loop()
    return CR30(t, "ble"), radio


# ---------------------------------------------------------------------------
# A USB port, simulated
# ---------------------------------------------------------------------------
def _usb_frame(sub, payload=b"", *, marker=0xFF):
    body = bytearray(Frame.PAYLOAD_SIZE)
    body[:len(payload)] = payload
    return Frame(0xBB, usb_measure.CMD_MEASURE, sub, 0, bytes(body),
                 marker=marker).to_bytes()


class _UsbPort(Transport):
    """A serial port: a press puts the unsolicited `BB 01 09` header in the
    input buffer, and each chunk request is answered from the stored reading."""

    def __init__(self):
        self._in = bytearray()
        self._lock = threading.Lock()
        self.stored = [5.0 + i * 0.5 for i in range(31)]

    def open(self):
        pass

    def close(self):
        pass

    def reset_input(self):
        with self._lock:
            self._in.clear()

    def bytes_waiting(self):
        with self._lock:
            return len(self._in)

    def _write(self, data):
        sub = data[2]
        vals = self.stored + [0.0] * 5
        i = usb_measure.CHUNK_SUBS.index(sub)
        chunk = vals[i * 12:(i + 1) * 12]
        payload = bytes(2) + struct.pack("<12f", *chunk)
        with self._lock:
            self._in += _usb_frame(sub, payload)

    def _read(self, n, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                if len(self._in) >= n:
                    out = bytes(self._in[:n])
                    del self._in[:n]
                    return out
            time.sleep(0.005)
        return b""

    def press(self, level: float) -> None:
        self.stored = [level + i * 0.37 for i in range(31)]
        header = bytearray(Frame.PAYLOAD_SIZE)
        header[0], header[1], header[2] = 40, 31, 10          # 400 nm, 31, 10
        with self._lock:
            self._in += _usb_frame(usb_measure.SUB_HEADER, bytes(header),
                                   marker=0x00)


def _usb_device():
    port = _UsbPort()
    return CR30(port, "usb"), port


# ---------------------------------------------------------------------------
# The spot window, with only the calibration replaced
# ---------------------------------------------------------------------------
#: How long the reader stays busy after the calibration in the "late" cases.
#: It stands for whatever keeps the read thread from its wait on a real Mac
#: (scheduling under load, the Bluetooth stack settling after the white
#: calibration): the review measured the gap at up to about a second. Held
#: with the reader's OWN lock, the one every read takes, so nothing about the
#: code under test is stubbed to arrange it.
BUSY_S = 1.3


def _spot_dialog(device, *, busy_s=0.0):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    from core.argyll_runner import ArgyllRunner

    class _Dlg(SpotReadDialog):
        def _run_cr30_calibration(self, *, keep_bridge=False):
            self._open_cr30_bridge()
            if self._cr30_reader is not None:
                self._cr30_reader._dev = device
                self._cr30_reader._open = lambda: device
                if busy_s:
                    lock, held = self._cr30_reader._lock, threading.Event()

                    def _busy():
                        with lock:
                            held.set()
                            time.sleep(busy_s)

                    threading.Thread(target=_busy, daemon=True).start()
                    held.wait(2.0)
            return True

    s = AppSettings()
    dlg = _Dlg(ArgyllRunner(s), s)
    dlg._instrument.setCurrentIndex(2)          # CR30 (ChnSpec)
    return dlg


def _wait(qapp, predicate, seconds=8.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return False


def _pump(qapp, seconds):
    _wait(qapp, lambda: False, seconds)


def _ready(dlg):
    return (dlg._cr30 is not None and dlg._read_btn.isEnabled()
            and dlg._status.text().startswith("Ready"))


def _status_widget_exists(dlg):
    return hasattr(dlg, "_status")


def _session(qapp, make_device, busy_s=0.0):
    dev, instrument = make_device()
    dlg = _spot_dialog(dev, busy_s=busy_s)
    assert _status_widget_exists(dlg)
    dlg._on_start_stop()
    assert _wait(qapp, lambda: _ready(dlg)), "the window never said Ready"
    return dlg, instrument


def _end(dlg):
    if dlg._cr30 is not None:
        dlg._end_cr30_session()
    dlg._unsaved = False
    dlg._release_instrument()
    dlg.deleteLater()


DEVICES = {
    "bluetooth": lambda: _ble_device(via_loop=False),
    "bluetooth-as-bleak-delivers": lambda: _ble_device(via_loop=True),
    "usb": _usb_device,
}


# ---------------------------------------------------------------------------
# 1. The first press after Ready is taken
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("delay", DELAYS)
@pytest.mark.parametrize("transport", sorted(DEVICES))
def test_the_first_press_after_ready_is_taken(qapp, transport, delay):
    dlg, instrument = _session(qapp, DEVICES[transport])
    try:
        _pump(qapp, delay)
        instrument.press(30.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 1), (
            f"{transport}: a press {delay:.1f} s after Ready was thrown away")
    finally:
        _end(dlg)


@pytest.mark.parametrize("delay", DELAYS)
@pytest.mark.parametrize("transport", sorted(DEVICES))
def test_the_first_press_after_ready_is_taken_when_the_reader_starts_late(
        qapp, transport, delay):
    """The review's case: the read thread reaches its wait about a second after
    the session starts. Ready must wait for it, not run ahead of it."""
    dlg, instrument = _session(qapp, DEVICES[transport], busy_s=BUSY_S)
    try:
        _pump(qapp, delay)
        instrument.press(30.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 1), (
            f"{transport}: a press {delay:.1f} s after Ready was thrown away")
    finally:
        _end(dlg)


# ---------------------------------------------------------------------------
# 2. ...and so is the press after the Ready that follows a reading
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("delay", DELAYS)
@pytest.mark.parametrize("transport", sorted(DEVICES))
def test_the_press_after_the_next_ready_is_taken(qapp, transport, delay):
    dlg, instrument = _session(qapp, DEVICES[transport])
    try:
        _pump(qapp, 1.5)               # the first press well clear of Ready
        instrument.press(30.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 1)
        assert _wait(qapp, lambda: _ready(dlg))
        _pump(qapp, delay)
        instrument.press(45.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 2), (
            f"{transport}: the second press, {delay:.1f} s after Ready, "
            "was thrown away")
    finally:
        _end(dlg)


# ---------------------------------------------------------------------------
# 3. ...and across the idle re-arm, where a new wait starts every 30 s
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("transport", sorted(DEVICES))
def test_presses_across_the_idle_rearm_are_all_taken(qapp, transport,
                                                     monkeypatch):
    import workflow.cr30_spot_manager as sm
    monkeypatch.setattr(sm, "REARM_SECONDS", 0.15)
    dlg, instrument = _session(qapp, DEVICES[transport])
    try:
        for i in range(8):
            # Spread over several re-arms, landing anywhere relative to them.
            _pump(qapp, 0.07 * (i % 4))
            instrument.press(20.0 + 5 * i)
            assert _wait(qapp, lambda: len(dlg._readings) == i + 1), (
                f"{transport}: press {i + 1} was thrown away at a re-arm")
    finally:
        _end(dlg)


# ---------------------------------------------------------------------------
# 4. A press announced BEFORE Ready still goes, and the window says so
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("transport", ["bluetooth",
                                       "bluetooth-as-bleak-delivers"])
def test_a_press_before_ready_is_not_used_and_the_window_says_so(qapp,
                                                                 transport):
    from workflow import measurement_messages as M
    dev, radio = DEVICES[transport]()
    # Pressed while the calibration's last window was still open: the
    # instrument announced it before any session existed.
    radio.press(70.0)
    dlg = _spot_dialog(dev)
    try:
        dlg._on_start_stop()
        assert _wait(qapp, lambda: _ready(dlg))
        _pump(qapp, 0.4)
        assert not dlg._readings, \
            "a press from before the session became its first reading"
        said = M.M_SPOT_CR30_EARLY_PRESS.render(n=1)[1]
        assert said in dlg._log.toPlainText(), \
            "the press was dropped and the window said nothing"
        # And the session is listening: the next press counts.
        radio.press(40.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 1)
    finally:
        _end(dlg)


def test_the_drop_happens_once_per_arming_not_once_per_read():
    """The mechanism, pinned below the window: a session armed once drops the
    stale presses once, and a new arming (a reconnect, a new patch) drops
    them again."""
    dev, radio = _ble_device()
    r = DeviceReader()
    r._dev = dev
    r.button_timeout_s = 0.2
    token = object()
    r.arm_trigger(token)
    radio.press(70.0)
    assert r.drop_stale_presses() == 1
    radio.press(30.0)                 # after Ready: must be collected
    xyz = r()
    assert xyz[1] > 0
    radio.press(35.0)
    assert r()[1] > 0, "the second read of the same arming dropped a press"
    r.arm_trigger(object())           # a different arming
    radio.press(80.0)
    from workflow.cr30.measurement import MeasurementError
    with pytest.raises(MeasurementError, match="no button press"):
        r()                           # the stale press went with the new arm


def test_a_read_with_nothing_armed_still_drops_what_came_before():
    """The Measure tab's old rule is untouched when no token names the read."""
    dev, radio = _ble_device()
    r = DeviceReader()
    r._dev = dev
    r.button_timeout_s = 0.2
    radio.press(70.0)
    from workflow.cr30.measurement import MeasurementError
    with pytest.raises(MeasurementError, match="no button press"):
        r()
