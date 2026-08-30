"""Q7 proving test for F4: the remembered BLE address must be identified.

Drives the REAL DeviceReader -> CR30 -> BleTransport stack. The only fake is
the `bleak` module itself -- the outermost transport edge. The fake CR30's
reply bytes are a HEX LITERAL taken from the research repo's captures
(EXP-BLE-013 carries the axis field 01 90 0a 1f = 400 nm BE / 10 nm / 31
bands), never built with ble.frame() -- a stub that reuses the code's own
builder validates itself.

The condition that distinguishes the real system from the harness: the
identity decision is made by the REAL `CR30.identify()` parsing those literal
bytes, and the tests assert on which ADDRESS the returned transport holds and
which BYTES each fake peripheral received -- facts the stub cannot fake
without the production code actually taking the right path.
"""
from __future__ import annotations

import asyncio
import sys
import types

import pytest

# --- the two peripherals ---------------------------------------------------

STRANGER = "AA:AA:AA:AA:AA:01"     # an HM-10 UART gadget: echoes every write
REAL_CR30 = "CC:30:CC:30:CC:30"

# Captured axis field (EXP-BLE-013: bb 01 00 00 01 90 0a 1f ff 75) spliced
# behind the stored-measurement header as the device returns it. 8 bytes is
# exactly what identify() needs (header + axis).
CR30_IDENT_REPLY = bytes.fromhex("bb 02 10 00 01 90 0a 1f".replace(" ", ""))


class _FakePeripheral:
    def __init__(self, address):
        self.address = address
        self.writes: list[bytes] = []
        self.notify_cb = None
        self.connected = False
        self.disconnects = 0

    def deliver(self, data: bytes):
        if self.notify_cb is not None:
            self.notify_cb("ffe1", bytearray(data))

    def on_write(self, data: bytes):
        self.writes.append(bytes(data))
        if self.address == STRANGER:
            # HM-10 loopback firmware: whatever arrives goes straight back.
            self.deliver(bytes(data))
        elif self.address == REAL_CR30 and bytes(data) == b"\x01":
            # A CR30 answers a POLL with its stored-slot reply.
            self.deliver(CR30_IDENT_REPLY)


PERIPHERALS: dict[str, _FakePeripheral] = {}


def _peripheral(address) -> _FakePeripheral:
    return PERIPHERALS.setdefault(address, _FakePeripheral(address))


class _FakeBleakClient:
    def __init__(self, address, timeout=None, **kw):
        addr = getattr(address, "address", address)
        self._p = _peripheral(addr)

    async def connect(self):
        self._p.connected = True

    async def disconnect(self):
        self._p.connected = False
        self._p.disconnects += 1

    async def start_notify(self, _char, cb):
        self._p.notify_cb = cb

    async def stop_notify(self, _char):
        self._p.notify_cb = None

    async def write_gatt_char(self, _char, data, response=False):
        self._p.on_write(data)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.disconnect()


class _Adv:
    def __init__(self, name):
        self.local_name = name
        self.service_uuids = ["0000ffe0-0000-1000-8000-00805f9b34fb"]
        self.rssi = -50


class _Dev:
    def __init__(self, address, name):
        self.address, self.name = address, name


class _FakeBleakScanner:
    #: Set by a test to forbid scanning outright.
    forbid = False

    @staticmethod
    async def discover(timeout=None, return_adv=True):
        if _FakeBleakScanner.forbid:
            raise AssertionError(
                "the scan ran -- the remembered fast path was not taken")
        await asyncio.sleep(0)
        return {REAL_CR30: (_Dev(REAL_CR30, "CR30-unit"), _Adv("CR30-unit"))}

    @staticmethod
    async def find_device_by_name(name, timeout=None):
        return _Dev(REAL_CR30, name)


@pytest.fixture
def fake_bleak(monkeypatch):
    PERIPHERALS.clear()
    _FakeBleakScanner.forbid = False
    mod = types.ModuleType("bleak")
    mod.BleakClient = _FakeBleakClient
    mod.BleakScanner = _FakeBleakScanner
    monkeypatch.setitem(sys.modules, "bleak", mod)
    return mod


@pytest.fixture
def store(monkeypatch):
    kept: dict = {}

    class _Settings:
        def get(self, key, default=None):
            return kept.get(key, default)

        def set(self, key, value):
            kept[key] = value

    import core.settings
    monkeypatch.setattr(core.settings, "AppSettings", _Settings)
    return kept


def _reader():
    from workflow.cr30.measure_bridge import DeviceReader
    return DeviceReader(transport="ble")


def test_a_stranger_at_the_remembered_address_is_refused(fake_bleak, store):
    """THE FAULT DETECTOR. Under the unfixed code this returns the echoing
    gadget itself, and the next frames it would receive are bb 11 / bb 10."""
    from workflow.cr30.measure_bridge import DeviceReader
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = STRANGER
    dev = _reader()._open()
    assert dev._t.address == REAL_CR30, (
        "the device at the remembered address was accepted without "
        "identification -- calibration frames would go to a stranger")
    stranger = _peripheral(STRANGER)
    for w in stranger.writes:
        assert not (w[:2] in (b"\xbb\x11", b"\xbb\x10")), (
            "a calibration frame reached an unidentified device")
    assert stranger.disconnects >= 1, (
        "the refused device was left connected; it stops advertising while "
        "held, so a transiently-failing real CR30 could never be rediscovered")
    assert store[DeviceReader.REMEMBERED_ADDRESS_KEY] == REAL_CR30, (
        "the poisoned address survived a session where the real "
        "instrument was found -- no self-heal")


def test_a_genuine_cr30_at_the_remembered_address_skips_the_scan(fake_bleak, store):
    """THE DICT-TRAP DETECTOR. identify()'s BLE branch returns a dict; a fix
    that copies the USB `is_cr30()` test refuses every real CR30 and lands in
    the scan, which this test forbids."""
    from workflow.cr30.measure_bridge import DeviceReader
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = REAL_CR30
    _FakeBleakScanner.forbid = True
    dev = _reader()._open()
    assert dev._t.address == REAL_CR30
    assert store[DeviceReader.REMEMBERED_ADDRESS_KEY] == REAL_CR30


def test_the_stranger_only_ever_receives_the_identity_probe(fake_bleak, store):
    """What DOES reach an unidentified device must be the minimal question:
    the READ_MEASUREMENT frame and 1-byte polls, nothing else."""
    from workflow.cr30 import ble
    from workflow.cr30.measure_bridge import DeviceReader
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = STRANGER
    _reader()._open()
    allowed = {bytes(ble.READ_MEASUREMENT), b"\x01"}
    got = set(_peripheral(STRANGER).writes)
    assert got <= allowed, f"unexpected bytes to an unidentified device: {got - allowed}"
