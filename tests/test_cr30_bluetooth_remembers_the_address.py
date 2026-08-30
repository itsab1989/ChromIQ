"""#159: eighteen seconds of a Bluetooth calibration was ChromIQ looking for the
instrument.

Basti, twice: *"when i click the button to calibrate against white i think this
is the first time my mac tries to connect to the device and thus it takes a
while"* — and after the first speed fix, *"i don't know if it is much faster"*.

He was right both times, and the second time proved the first fix was aimed at
the wrong thing. Instrumented and measured on his own Mac, 2026-08-30:

    found in 15.42 s, connected in 2.33 s, notifications in 0.06 s
    calibration white answered in 0.81 s

**The scan is the whole of it** — six times the connection, and nearly twenty
times the calibration exchange it happens before. Connecting to a known address
skips it.

The remembered address is a HINT, never an identity. A CoreBluetooth address is
stable per host but says nothing about WHICH unit answers there, so a failure
falls back to the scan instead of reporting the instrument missing — which also
covers a second CR30, a reset Bluetooth stack and a different Mac.
"""
from __future__ import annotations

import pytest

from workflow.cr30.measure_bridge import DeviceReader


class _Transport:
    def __init__(self, address):
        self.address = address


class _Device:
    """Mirrors the REAL CR30's BLE surface, or this test proves nothing.

    `identify()` returns a plain DICT over Bluetooth (device.py:214) and raises
    for a stranger; `close()` exists and the reader calls it when identification
    fails. A stub missing either one turns a legitimate call into an
    AttributeError and reports the code broken when it is not -- which is what
    happened when the remembered-address branch was finally taught to identify.
    """

    def __init__(self, address):
        self._t = _Transport(address)
        self.model = ""
        self.identified = 0
        self.closed = 0

    def identify(self):
        self.identified += 1
        self.model = "CR30"
        return {"model": "CR30", "transport": "ble"}

    def close(self):
        self.closed += 1


@pytest.fixture
def opens(monkeypatch):
    """Record every open_ble call, and control what it does."""
    calls: list = []
    outcome = {"fail_for": None}

    def _open_ble(name=None, *, address=None, **kw):
        calls.append(address)
        if outcome["fail_for"] is not None and address == outcome["fail_for"]:
            raise ConnectionError("no CR30 found over Bluetooth")
        return _Device(address or "scanned-address")

    import workflow.cr30.device as device
    monkeypatch.setattr(device.CR30, "open_ble", staticmethod(_open_ble))
    return calls, outcome


@pytest.fixture
def store(monkeypatch):
    """A settings store that lives only for the test."""
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
    return DeviceReader(transport="ble")


def test_the_first_open_scans_and_remembers_what_it_found(opens, store):
    calls, _ = opens
    _reader()._open()
    assert calls == [None], "it did not scan when it had nothing remembered"
    assert store[DeviceReader.REMEMBERED_ADDRESS_KEY] == "scanned-address", (
        "the address it connected to was not remembered, so the next session "
        "pays the fifteen-second scan again")


def test_the_next_open_uses_the_remembered_address(opens, store):
    calls, _ = opens
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = "known-address"

    _reader()._open()

    assert calls == ["known-address"], (
        "it scanned even though it knew where the instrument was")


def test_a_stale_address_falls_back_to_scanning(opens, store):
    """The address is a hint. A unit that has moved, a reset Bluetooth stack or
    a different Mac must cost one failed connection, never a dead end."""
    calls, outcome = opens
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = "gone-address"
    outcome["fail_for"] = "gone-address"

    dev = _reader()._open()

    assert calls == ["gone-address", None], (
        "a stale address was not followed by a search")
    assert dev is not None, "a stale address reported the instrument missing"


def test_the_fallback_replaces_the_stale_address(opens, store):
    calls, outcome = opens
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = "gone-address"
    outcome["fail_for"] = "gone-address"

    _reader()._open()

    assert store[DeviceReader.REMEMBERED_ADDRESS_KEY] == "scanned-address", (
        "the address that failed is still remembered, so every session would "
        "pay the failed connection AND the scan for ever")


def test_an_explicit_address_still_wins(opens, store):
    """A unit chosen deliberately must not be overridden by a remembered one."""
    calls, _ = opens
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = "remembered"
    DeviceReader(transport="ble", address="chosen-by-hand")._open()
    assert calls[0] == "chosen-by-hand"


def test_a_broken_settings_store_never_stops_a_measurement(monkeypatch, opens):
    """Remembering is a convenience. It must not be able to fail an open."""
    calls, _ = opens

    class _Broken:
        def __init__(self):
            raise RuntimeError("settings are unavailable")

    import core.settings
    monkeypatch.setattr(core.settings, "AppSettings", _Broken)

    dev = _reader()._open()
    assert dev is not None, "a settings failure prevented the instrument opening"


# ---- and the same discipline on USB -------------------------------------
#
# `CR30.open_usb()` now identifies every candidate rather than trusting the
# first — right, and it means it may write its identify frame to MORE of the
# user's devices than the old code did, because `1a86:7523` is the generic
# CH340 and the list can hold an Arduino or a 3D printer. Remembering the port
# that answered keeps the ordinary case to a single probe, of the right device.

@pytest.fixture
def usb_opens(monkeypatch):
    calls: list = []
    outcome = {"fail_for": None}

    class _T:
        def __init__(self, port):
            self.port = port

    class _Ident:
        """Mirrors the real return type: `identify()` does NOT raise for a
        stranger, it returns an identity whose `is_cr30()` is the actual test.
        A stub returning a bare dict cannot exercise that check."""
        def __init__(self, model="CR30"):
            self.model = model
        def is_cr30(self):
            return self.model == "CR30"

    class _Dev:
        def __init__(self, port):
            self._t = _T(port)
        def identify(self):
            if outcome["fail_for"] == self._t.port:
                raise ConnectionError("not a CR30")
            return _Ident()
        def close(self):
            pass

    def _open_usb(port=None):
        calls.append(port)
        if port is None:
            return _Dev("/dev/found-by-searching")
        if outcome["fail_for"] == port:
            raise ConnectionError("not a CR30")
        return _Dev(port)

    import workflow.cr30.device as device
    monkeypatch.setattr(device.CR30, "open_usb", staticmethod(_open_usb))
    return calls, outcome


def test_the_first_usb_open_searches_and_remembers(usb_opens, store):
    calls, _ = usb_opens
    DeviceReader(transport="usb")._open()
    assert calls == [None], "it did not search when it had nothing remembered"
    assert store[DeviceReader.REMEMBERED_PORT_KEY] == "/dev/found-by-searching"


def test_the_next_open_tries_the_remembered_port_first(usb_opens, store):
    calls, _ = usb_opens
    store[DeviceReader.REMEMBERED_PORT_KEY] = "/dev/known"
    DeviceReader(transport="usb")._open()
    assert calls == ["/dev/known"], (
        "it probed other people's serial devices although it knew where the "
        "instrument was")


def test_a_port_that_is_now_something_else_falls_back(usb_opens, store):
    """A `/dev/cu.usbserial-*` path is reused by whatever is plugged in next,
    so the remembered port is a hint and must be identified, not trusted."""
    calls, outcome = usb_opens
    store[DeviceReader.REMEMBERED_PORT_KEY] = "/dev/was-the-cr30"
    outcome["fail_for"] = "/dev/was-the-cr30"

    dev = DeviceReader(transport="usb")._open()

    assert calls == ["/dev/was-the-cr30", None], "a stale port did not fall back"
    assert dev is not None
    assert store[DeviceReader.REMEMBERED_PORT_KEY] == "/dev/found-by-searching", (
        "the stale port is still remembered, so every session would probe it")
