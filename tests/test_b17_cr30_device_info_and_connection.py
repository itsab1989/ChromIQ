"""Beta 17, builder B: what a CR30 says about itself, the key its learned tile
is filed under, and the four connection faults Basti hit on beta 16.

Every test runs the real code with only the instrument replaced: the replies
are the bytes Basti's own unit sent on 2026-10-09 (docs/cr30_reports/
56_captures/), the Bluetooth radio is a stand-in for bleak, and the spot window
is the real `SpotReadDialog`. No real instrument is ever opened.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox          # noqa: E402

from core import instrument_lease                               # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from workflow.cr30 import ble, device_info, tile_learning       # noqa: E402
from workflow.cr30.device import CR30, DeviceLost               # noqa: E402
from workflow.cr30.measure_bridge import (DeviceReader,         # noqa: E402
                                          close_all_readers)
from workflow.cr30.measurement import Measurement, MeasurementError  # noqa: E402
from workflow.cr30.transport import Exchange, ReplayTransport   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAPTURES = ROOT / "docs" / "cr30_reports" / "56_captures"
WL = list(range(400, 701, 10))


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_store():
    """Every test starts with no learned tile and no remembered unit."""
    s = AppSettings()
    for key in (tile_learning.SIGNATURE_KEY, device_info.LAST_DEVICE_KEY,
                DeviceReader.REMEMBERED_ADDRESS_KEY):
        s.set(key, "")
    # The window remembers the reader chosen by hand; a later test's window
    # must start on its own default, not on this file's choice.
    s.set("spot_read_instrument", "auto")
    instrument_lease.release(instrument_lease.holder_object())
    yield
    for key in (tile_learning.SIGNATURE_KEY, device_info.LAST_DEVICE_KEY,
                DeviceReader.REMEMBERED_ADDRESS_KEY):
        s.set(key, "")
    # The window remembers the reader chosen by hand; a later test's window
    # must start on its own default, not on this file's choice.
    s.set("spot_read_instrument", "auto")
    instrument_lease.release(instrument_lease.holder_object())


def _ble_reply() -> bytes:
    doc = json.loads((CAPTURES / "devinfo_ble_20261009-215204.capture.json")
                     .read_text(encoding="utf-8"))
    return bytes.fromhex(doc["exchanges"][0]["rx"])


def _usb_identity_transport() -> ReplayTransport:
    doc = json.loads((CAPTURES / "devinfo_usb_20261009-215159.capture.json")
                     .read_text(encoding="utf-8"))
    return ReplayTransport([Exchange(bytes.fromhex(e["tx"]),
                                     bytes.fromhex(e["rx"]))
                            for e in doc["exchanges"]])


# ---------------------------------------------------------------------------
# A Bluetooth radio, simulated: bleak replaced, ChromIQ's BleTransport real
# ---------------------------------------------------------------------------
class _Radio:
    """Answers the way Basti's unit did: `BB 12 01` gets its 200-byte reply in
    20-byte notifications, and nothing else is answered."""

    def __init__(self, transport, reply=None, *, silent=False):
        self.t = transport
        self.reply = reply if reply is not None else _ble_reply()
        self.silent = silent
        self.written: list[bytes] = []
        self.disconnected = False
        self.on_disconnect = None

    async def write_gatt_char(self, _char, data, response=False):
        self.written.append(bytes(data))
        if self.silent:
            return
        if bytes(data) == ble.DEVICE_INFO:
            for i in range(0, len(self.reply), 20):
                self.t._on_notify(None, bytearray(self.reply[i:i + 20]))

    async def stop_notify(self, _char):
        pass

    async def disconnect(self):
        self.disconnected = True

    def power_off(self):
        """The CR30 switches itself off: bleak calls the disconnect callback."""
        self.t._on_disconnect(None)


def _ble_transport(**radio_kw):
    t = ble.BleTransport.__new__(ble.BleTransport)
    t.name, t.address, t.timeout = "CM454M0223", "ADDR-1", 5.0
    t._buf = bytearray()
    from collections import deque
    t._events = deque(maxlen=64)
    t._loop = None
    t._lost = False
    radio = _Radio(t, **radio_kw)
    t._client = radio
    return t, radio


# ---------------------------------------------------------------------------
# 1. Device information, logged at every connect
# ---------------------------------------------------------------------------
def test_the_bluetooth_reply_decodes_to_basti_s_unit():
    info = device_info.parse_ble_reply(_ble_reply())
    assert (info.model, info.serial, info.internal_id) == (
        "CR30", "CM454M0223", "PT694D01E7")
    assert info.software == "V11.3.0.0.20231219"
    assert info.hardware == "V10.0.0.0"
    assert info.device_code == 793
    assert info.tested_firmware


def test_usb_and_bluetooth_describe_the_same_unit_alike():
    """The two transports must agree field for field, or the key and the
    version mark would depend on the cable."""
    dev = CR30(_usb_identity_transport(), "usb")
    usb = dev.read_device_info()
    bt = device_info.parse_ble_reply(_ble_reply())
    for f in ("model", "serial", "internal_id", "software", "hardware",
              "device_code"):
        assert getattr(usb, f) == getattr(bt, f), f


def test_bluetooth_asks_only_the_vendor_question_and_its_poll():
    """Wake byte, `BB 12 01`, and `01` polls while incomplete. Nothing new."""
    t, radio = _ble_transport()
    raw = t.read_device_info(timeout=2.0)
    assert device_info.parse_ble_reply(raw).serial == "CM454M0223"
    allowed = {ble.POLL, ble.DEVICE_INFO}
    assert set(radio.written) <= allowed, radio.written
    assert radio.written[:2] == [ble.POLL, ble.DEVICE_INFO]
    assert radio.written.count(ble.DEVICE_INFO) == 1


def test_a_silent_unit_costs_at_most_the_timeout_and_never_blocks_the_open(
        caplog):
    t, radio = _ble_transport(silent=True)
    dev = CR30(t, "ble")
    dev.unit_id = "CM454M0223"
    reader = DeviceReader()
    t0 = time.monotonic()
    with caplog.at_level(logging.INFO):
        reader._note_device(dev)
    took = time.monotonic() - t0
    # The production bound is five seconds; read_device_info is called with
    # its default here, so this proves the bound is real and is honoured.
    assert took < ble.DEVICE_INFO_TIMEOUT_S + 2.0, took
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "did not describe itself" in said and "carrying on" in said
    assert dev.unit_id == "CM454M0223", "a failed question changed the key"


def test_every_connect_logs_the_unit_and_keeps_it_for_the_report(caplog):
    t, _radio = _ble_transport()
    dev = CR30(t, "ble")
    with caplog.at_level(logging.INFO):
        DeviceReader()._note_device(dev)
    said = " ".join(r.getMessage() for r in caplog.records)
    for part in ("model CR30", "serial CM454M0223", "internal id PT694D01E7",
                 "software V11.3.0.0.20231219", "hardware V10.0.0.0"):
        assert part in said, part
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], \
        "the tested firmware was marked as untested"
    lines = "\n".join(device_info.report_lines())
    assert "CM454M0223" in lines and "V11.3.0.0.20231219" in lines


def test_a_different_firmware_is_marked_in_the_log_only(caplog):
    reply = device_info.build_ble_reply(software="V11.4.0.0.20250101")
    t, _radio = _ble_transport(reply=reply)
    with caplog.at_level(logging.INFO):
        DeviceReader()._note_device(CR30(t, "ble"))
    warned = [r.getMessage() for r in caplog.records
              if r.levelno >= logging.WARNING]
    assert warned and "V11.4.0.0.20250101" in warned[0] \
        and device_info.TESTED_SOFTWARE in warned[0]
    assert "tested with" in "\n".join(device_info.report_lines())


def test_the_bluetooth_report_names_the_last_unit(monkeypatch):
    import asyncio
    import sys
    import types
    t, _radio = _ble_transport()
    DeviceReader()._note_device(CR30(t, "ble"))

    class _Scanner:
        @staticmethod
        async def discover(timeout=None, return_adv=False):
            return {}

    mod = types.ModuleType("bleak")
    mod.BleakScanner = _Scanner
    monkeypatch.setitem(sys.modules, "bleak", mod)
    from workflow.cr30.bluetooth_report import collect
    rep = asyncio.new_event_loop().run_until_complete(
        collect(scan_seconds=0.0))
    head = rep.text.split("1. What this computer")[0]
    assert "CM454M0223" in head and "PT694D01E7" in head


# ---------------------------------------------------------------------------
# 2. The learned tile is keyed by the serial the unit states itself
# ---------------------------------------------------------------------------
TILE = [70.0 + i * 0.1 for i in range(31)]


def test_a_tile_learned_under_the_advertised_name_still_arms_the_guard():
    """Every key written before beta 17 is the advertised name, which on this
    unit IS the serial: nobody has to teach the tile again."""
    tile_learning.remember_signature(TILE, "CM454M0223")
    t, _radio = _ble_transport()
    dev = CR30(t, "ble")
    dev.unit_id = "CM454M0223"
    DeviceReader()._arm_tile_guard(dev)
    assert dev.learned_tile == TILE


def test_an_address_key_moves_to_the_serial_over_bluetooth_without_a_name():
    """The fast path without a name filed under `ble:<address>`; the unit's own
    serial now arrives over that very link and the key follows it."""
    tile_learning.remember_signature(TILE, "ble:ADDR-1")
    t, _radio = _ble_transport()
    t.name = None
    dev = CR30(t, "ble")
    dev.unit_id = None
    DeviceReader()._arm_tile_guard(dev)
    store = json.loads(AppSettings().get(tile_learning.SIGNATURE_KEY))
    assert list(store) == ["CM454M0223"], store
    assert dev.learned_tile == TILE and dev.unit_id == "CM454M0223"


def test_a_name_that_is_not_the_serial_is_re_filed_under_the_serial():
    tile_learning.remember_signature(TILE, "CR30-somename")
    t, _radio = _ble_transport()
    dev = CR30(t, "ble")
    dev.unit_id = "CR30-somename"           # what the advertisement said
    DeviceReader()._arm_tile_guard(dev)
    store = json.loads(AppSettings().get(tile_learning.SIGNATURE_KEY))
    assert list(store) == ["CM454M0223"], store
    assert dev.learned_tile == TILE


def test_usb_and_bluetooth_file_the_tile_under_the_same_key():
    usb = CR30(_usb_identity_transport(), "usb")
    usb.identify()
    DeviceReader()._note_device(usb)
    t, _radio = _ble_transport()
    bt = CR30(t, "ble")
    bt.unit_id = None
    DeviceReader()._note_device(bt)
    assert usb.unit_id == bt.unit_id == "CM454M0223"


# ---------------------------------------------------------------------------
# 3a. A closed reader never opens the instrument again
# ---------------------------------------------------------------------------
class _FakeDevice:
    kind = "ble"

    def __init__(self):
        self.closed = False
        self.learned_tile = None
        self.reads = 0
        self.calibrations = 0
        self._pending = None
        self.lost_next = False
        self.block = None
        self.calibrate_delay = 0.0

    def press(self, level=40.0):
        self._pending = Measurement(WL, [float(level)] * 31)

    def read_next_measurement(self, *, timeout=180.0, cancelled=None,
                              poll=0.01, for_learning=False,
                              trigger_wanted=None,
                              drop_stale=True):
        if self.lost_next:
            self.lost_next = False
            raise DeviceLost("the Bluetooth link to the instrument dropped")
        if self.block is not None:
            # A link that ignores Stop: waits for the test, not the cancel.
            self.block.wait(6.0)
            raise MeasurementError("no button press within 1 s.")
        end = time.monotonic() + timeout
        while self._pending is None:
            if self.lost_next:
                self.lost_next = False
                raise DeviceLost("the Bluetooth link to the instrument "
                                 "dropped")
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > end:
                raise MeasurementError(f"no button press within {timeout:.0f} s.")
            time.sleep(0.002)
        m, self._pending = self._pending, None
        self.reads += 1
        return m

    def calibrate(self, black=False):
        self.calibrations += 1
        time.sleep(self.calibrate_delay)

    def read_measurement(self, *a, **kw):
        return Measurement(WL, [0.0] * 31)

    def close(self):
        self.closed = True


class _CountingReader(DeviceReader):
    """A real DeviceReader whose OPEN is the only thing replaced."""

    devices: list = []

    def _open(self):
        dev = _FakeDevice()
        dev.calibrate_delay = type(self).calibrate_delay
        type(self).devices.append(dev)
        return dev

    calibrate_delay = 0.0


def test_a_closed_reader_refuses_to_open_the_instrument_again():
    _CountingReader.devices = []
    r = _CountingReader()
    r.calibrate()
    assert len(_CountingReader.devices) == 1
    r.close()
    assert _CountingReader.devices[0].closed
    with pytest.raises(ConnectionError):
        r.learn_tile(timeout=0.1)
    with pytest.raises(ConnectionError):
        r.calibrate()
    assert len(_CountingReader.devices) == 1, (
        "a closed reader opened a new link that nobody holds")


def test_quitting_lets_go_of_every_reader():
    _CountingReader.devices = []
    r = _CountingReader()
    r.calibrate()
    assert close_all_readers() >= 1
    assert _CountingReader.devices[0].closed


class _StubBox:
    """The calibration question, answered "Calibrate now"."""

    Icon = QMessageBox.Icon
    ButtonRole = QMessageBox.ButtonRole
    StandardButton = QMessageBox.StandardButton

    def __init__(self, parent=None):
        self._buttons, self._clicked = [], None

    def __getattr__(self, name):
        return lambda *a, **k: None

    def addButton(self, text, role=None):
        from PyQt6.QtWidgets import QPushButton
        b = QPushButton(text)
        self._buttons.append(b)
        return b

    def buttons(self):
        return self._buttons

    def exec(self):
        for b in self._buttons:
            if b.text() == "Calibrate now":
                self._clicked = b

    def clickedButton(self):
        return self._clicked


def test_closing_the_window_during_the_calibration_ends_it_there(
        qapp, monkeypatch):
    """Basti's log, 20:59:12: the window let go of the instrument while the
    calibration was still running, and the teach-in then opened a NEW
    Bluetooth link on the closed reader. Nothing ever closed that one, so the
    CR30 stopped advertising and the next session could not find it."""
    import PyQt6.QtWidgets as W
    import ui.widgets as widgets
    from PyQt6.QtCore import QTimer
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    import workflow.cr30.measure_bridge as mb
    from core.argyll_runner import ArgyllRunner

    monkeypatch.setattr(W, "QMessageBox", _StubBox)
    monkeypatch.setattr(widgets, "fit_message_box_buttons", lambda box: None)
    monkeypatch.setattr(widgets, "order_message_box_buttons",
                        lambda box, order: None)
    monkeypatch.setattr(mb, "DeviceReader", _CountingReader)
    _CountingReader.devices = []
    _CountingReader.calibrate_delay = 0.4
    offered = []

    class _Dlg(SpotReadDialog):
        def _offer_cr30_tile_learning(self, reader):
            offered.append(reader)

    s = AppSettings()
    dlg = _Dlg(ArgyllRunner(s), s)
    try:
        dlg._instrument.setCurrentIndex(2)
        QTimer.singleShot(50, dlg.reject)       # the user gives up waiting
        dlg._on_start_stop()
        assert offered == [], "the teach-in was offered on a closed reader"
        assert len(_CountingReader.devices) == 1, "a second link was opened"
        assert _CountingReader.devices[0].closed, "the instrument was kept"
        assert dlg._cr30 is None
    finally:
        _CountingReader.calibrate_delay = 0.0
        dlg._release_instrument()
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 3b/3c. The link drops: noticed at once, Stop works, Reconnect finds it again
# ---------------------------------------------------------------------------
def test_a_switched_off_unit_is_noticed_at_once_not_at_the_rearm():
    t, radio = _ble_transport()
    dev = CR30(t, "ble")
    threading.Timer(0.2, radio.power_off).start()
    t0 = time.monotonic()
    with pytest.raises(DeviceLost):
        dev.read_next_measurement(timeout=30.0)
    assert time.monotonic() - t0 < 3.0, "the loss waited for the re-arm"


def test_closing_from_another_thread_really_disconnects():
    """The reader thread runs the transport's loop for the whole wait; a close
    from the window used to fail on "this event loop is already running", and
    the link stayed up."""
    t, radio = _ble_transport()
    waiting = threading.Thread(target=lambda: t.wait_for_event(1.5),
                               daemon=True)
    waiting.start()
    time.sleep(0.2)
    t.close()
    waiting.join(3.0)
    assert radio.disconnected, "close() left the Bluetooth link connected"


def _spot_dialog(qapp, device, answer=None):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    from core.argyll_runner import ArgyllRunner

    class _Dlg(SpotReadDialog):
        asked: list = []

        def _run_cr30_calibration(self, *, keep_bridge=False):
            self._open_cr30_bridge()
            if self._cr30_reader is not None:
                self._cr30_reader._dev = device
                self._cr30_reader._open = lambda: device
            return True

        def _ask(self, box):
            self.asked.append(box.text())
            for b in box.buttons():
                if b.text().replace("&", "") == answer:
                    return b
            return None

    s = AppSettings()
    dlg = _Dlg(ArgyllRunner(s), s)
    dlg.asked = []
    dlg._instrument.setCurrentIndex(2)
    return dlg


def _wait(qapp, predicate, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_stop_ends_the_session_even_when_the_link_ignores_it(qapp):
    """Basti, beta 16: the CR30 had switched itself off and Stop did nothing.
    Stop used to wait for the read loop to report its end."""
    dev = _FakeDevice()
    dev.block = threading.Event()
    dlg = _spot_dialog(qapp, dev)
    try:
        dlg._on_start_stop()
        assert dlg._cr30 is not None and dlg._cr30.is_running
        _wait(qapp, lambda: False, 0.2)
        dlg._on_start_stop()                       # Stop
        assert dlg._start_btn.text() == "Start session", \
            "the window still offers Stop after Stop was pressed"
        assert dlg._cr30 is None and dlg._cr30_reader is None
        assert dev.closed, "the instrument was not let go"
    finally:
        dev.block.set()
        dlg._release_instrument()
        dlg.deleteLater()


def test_a_lost_instrument_pauses_the_session_and_reconnect_carries_on(qapp):
    from workflow import measurement_messages as M
    dev = _FakeDevice()
    dlg = _spot_dialog(qapp, dev, answer="Reconnect")
    try:
        dlg._on_start_stop()
        dev.press(30.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 1)
        dev.lost_next = True                      # the CR30 switches off
        title = M.M_SPOT_CR30_GONE.render()[0]
        assert _wait(qapp, lambda: title in dlg.asked), \
            "nobody was told the instrument had gone"
        assert len(dlg._readings) == 1, "a reading was lost with the link"
        # Reconnect chosen: the reader opens the instrument again and the
        # session listens again -- no window close, no new Start.
        assert _wait(qapp, lambda: dlg._cr30 is not None
                     and dlg._cr30.is_running and dlg._read_btn.isEnabled())
        dev.press(50.0)
        assert _wait(qapp, lambda: len(dlg._readings) == 2), \
            "the switched-on instrument was not read again"
    finally:
        dlg._release_instrument()
        dlg.deleteLater()


def test_stop_session_in_the_lost_window_ends_cleanly(qapp):
    dev = _FakeDevice()
    dlg = _spot_dialog(qapp, dev, answer="Stop session")
    try:
        dlg._on_start_stop()
        dev.lost_next = True
        assert _wait(qapp, lambda: bool(dlg.asked))
        assert _wait(qapp, lambda: dlg._start_btn.text() == "Start session")
        assert dlg._cr30 is None and dev.closed
    finally:
        dlg._release_instrument()
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 3d. A slow reading names itself in the log
# ---------------------------------------------------------------------------
def test_a_bluetooth_reading_says_how_long_it_took(monkeypatch, caplog):
    t, _radio = _ble_transport()
    dev = CR30(t, "ble")
    t._events.append(bytes([0xBB, 0x01, 0, 0, 0, 0, 0, 0, 0xFF, 0xBC]))
    monkeypatch.setattr(t, "drop_events", lambda: 0)
    monkeypatch.setattr(CR30, "_read_when_ready",
                        lambda self, deadline, tries=6:
                        Measurement(WL, [40.0] * 31))
    with caplog.at_level(logging.INFO, logger="workflow.cr30.device"):
        dev.read_next_measurement(timeout=5.0)
    assert any("reading collected" in r.getMessage() for r in caplog.records)


def test_a_link_that_arrives_after_the_close_is_let_go():
    """Over Bluetooth an open can outlast the two seconds a close waits for the
    reader. Found on screen with the simulated radio: the window had gone, and
    the link that arrived afterwards stayed connected and was even
    calibrated."""

    class _Slow(_CountingReader):
        def _open(self):
            time.sleep(2.6)
            return super()._open()

    _CountingReader.devices = []
    r = _Slow()
    worker = threading.Thread(target=lambda: _swallow(r.calibrate),
                              daemon=True)
    worker.start()
    time.sleep(0.2)
    r.close()                                   # gives up waiting after 2 s
    worker.join(6.0)
    assert len(_CountingReader.devices) == 1
    assert _CountingReader.devices[0].closed, "the late link was kept"
    assert _CountingReader.devices[0].calibrations == 0, \
        "a closed reader calibrated the instrument"


def _swallow(fn):
    try:
        fn()
    except Exception:            # noqa: BLE001 — the refusal is the point
        pass


def test_after_reconnect_ready_waits_for_the_link(qapp):
    """A press made while the instrument is still being found cannot be
    collected, so the window must not say Ready before the link is open."""
    dev = _FakeDevice()
    dlg = _spot_dialog(qapp, dev, answer="Reconnect")
    try:
        dlg._on_start_stop()
        opened = threading.Event()

        def _slow_open():
            time.sleep(1.0)
            opened.set()
            return dev

        dlg._cr30_reader._open = _slow_open
        dev.lost_next = True
        assert _wait(qapp, lambda: bool(dlg.asked))
        _wait(qapp, lambda: False, 0.3)
        assert not opened.is_set()
        assert not dlg._read_btn.isEnabled(), \
            "Ready was shown while the instrument was still being looked for"
        assert _wait(qapp, lambda: dlg._read_btn.isEnabled(), 5.0)
        assert opened.is_set()
    finally:
        dlg._release_instrument()
        dlg.deleteLater()
