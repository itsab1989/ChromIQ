"""ARGYLL_EXCLUDE_SERIAL_SCAN handling: skip Argyll's slow phantom-serial-port
probe on macOS so a USB spectro connects fast, without ever excluding a real
serial instrument (Basti — 11 s → 0.35 s to the calibration prompt)."""
from __future__ import annotations

import sys

import pytest

from core.argyll_runner import (_phantom_serial_ports,
                                _windows_bluetooth_com_ports,
                                argyll_serial_exclusion_ports,
                                merged_serial_exclusion)


def test_phantom_filter_keeps_real_usb_serial_adapters():
    cands = [
        "/dev/cu.Bluetooth-Incoming-Port",   # phantom → exclude
        "/dev/cu.debug-console",             # phantom → exclude
        "/dev/cu.wlan-debug",                # phantom → exclude
        "/dev/cu.usbserial-1420",            # REAL adapter (e.g. SpectroScan) → keep
        "/dev/cu.usbmodem14201",             # REAL adapter → keep
        "/dev/cu.JETI-specbos",              # a JETI port Argyll talks to → keep
    ]
    excl = _phantom_serial_ports(cands)
    assert "/dev/cu.Bluetooth-Incoming-Port" in excl
    assert "/dev/cu.debug-console" in excl
    assert "/dev/cu.wlan-debug" in excl
    # A real USB-serial adapter is NEVER excluded → serial instruments still work.
    assert "/dev/cu.usbserial-1420" not in excl
    assert "/dev/cu.usbmodem14201" not in excl
    assert "/dev/cu.JETI-specbos" not in excl
    assert excl == sorted(excl)                       # stable order


def test_merged_value_adds_ours_and_keeps_user_set():
    # No existing value → just our ports.
    assert merged_serial_exclusion(None, ["/dev/cu.a", "/dev/cu.b"]) == \
        "/dev/cu.a;/dev/cu.b"
    # A user-set value is preserved and never dropped.
    assert merged_serial_exclusion("COM9;COM10", ["/dev/cu.a"]) == \
        "COM9;COM10;/dev/cu.a"
    # Commas are accepted as separators too.
    assert merged_serial_exclusion("x,y", ["z"]) == "x;y;z"
    # De-dup: a port already listed isn't repeated.
    assert merged_serial_exclusion("/dev/cu.a", ["/dev/cu.a"]) == "/dev/cu.a"
    # Nothing to exclude → None (callers then leave the environment untouched).
    assert merged_serial_exclusion(None, []) is None
    assert merged_serial_exclusion("", []) is None


def test_linux_left_unchanged(monkeypatch):
    """Linux enumerates only Bluetooth /dev/rfcomm* — none on the test host."""
    monkeypatch.setattr(sys, "platform", "linux")
    assert argyll_serial_exclusion_ports() == []


def test_windows_excludes_only_bluetooth_com_ports():
    """The Windows classifier skips Bluetooth COM ports and KEEPS every
    USB-serial adapter and native port — so a serial instrument (SpectroScan on
    a USB-serial bridge) is never excluded."""
    rows = [
        (r"\Device\BthModem0", "COM47"),   # paired Bluetooth SPP → exclude
        (r"\Device\BtPort1",   "COM48"),   # Bluetooth port       → exclude
        (r"\Device\VCP0",      "COM3"),    # FTDI/virtual USB-serial → KEEP
        (r"\Device\USBSER000", "COM4"),    # USB serial adapter      → KEEP
        (r"\Device\Serial0",   "COM1"),    # native UART             → KEEP
    ]
    excl = _windows_bluetooth_com_ports(rows)
    assert excl == ["COM47", "COM48"]                 # sorted, Bluetooth only
    for keep in ("COM3", "COM4", "COM1"):
        assert keep not in excl
    # De-dup: the same Bluetooth COM listed twice appears once.
    assert _windows_bluetooth_com_ports(
        [(r"\Device\BthModem0", "COM47"),
         (r"\Device\BthModem1", "COM47")]) == ["COM47"]
    # No serial ports at all → nothing excluded.
    assert _windows_bluetooth_com_ports([]) == []


def test_windows_enumeration_delegates_to_registry(monkeypatch):
    """On win32, argyll_serial_exclusion_ports() reads SERIALCOMM and returns
    exactly the Bluetooth COM ports found there."""
    import core.argyll_env as ar          # where the enumeration lives now
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ar, "_read_serialcomm",
                        lambda: [(r"\Device\BthModem0", "COM47"),
                                 (r"\Device\USBSER000", "COM4")])
    assert ar.argyll_serial_exclusion_ports() == ["COM47"]
    # An empty registry (the common case) excludes nothing.
    monkeypatch.setattr(ar, "_read_serialcomm", lambda: [])
    assert ar.argyll_serial_exclusion_ports() == []


class _StubSettings:
    def __init__(self, on): self._on = on
    def get(self, key, default=None):
        return self._on if key == "fast_instrument_connect" else default


def test_setting_gates_the_exclusion(qapp, monkeypatch):
    """The Beta 'Faster instrument connection' switch turns the phantom-port
    list on and off. Off ⇒ the user's value is passed on as it is, plus only
    the ports whose open can hang for ever (core/argyll_env.py: the macOS
    Bluetooth incoming port, 2026-10-03), which no preference may put back."""
    import core.argyll_env as AE
    from core.argyll_runner import ArgyllRunner
    monkeypatch.setattr(AE, "argyll_serial_exclusion_ports",
                        lambda: ["/dev/cu.debug-console"])
    off = ArgyllRunner(_StubSettings(False))
    monkeypatch.setattr(sys, "platform", "linux")
    assert off._serial_exclusion_value(None) is None
    assert off._serial_exclusion_value("COM9") == "COM9"    # user value untouched
    monkeypatch.setattr(sys, "platform", "darwin")
    assert off._serial_exclusion_value(None) == "/dev/cu.Bluetooth-Incoming-Port"
    assert off._serial_exclusion_value("COM9") == \
        "COM9;/dev/cu.Bluetooth-Incoming-Port"
    on = ArgyllRunner(_StubSettings(True))
    assert on._serial_exclusion_value(None) == \
        "/dev/cu.Bluetooth-Incoming-Port;/dev/cu.debug-console"
    # On: a user-set value is always preserved (ours is merged onto it).
    assert on._serial_exclusion_value("COM9") is not None
    assert "COM9" in on._serial_exclusion_value("COM9")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS /dev/cu.* only")
def test_macos_enumeration_returns_paths():
    # On macOS this returns whatever phantom /dev/cu.* ports exist (possibly
    # empty); every entry must be a real device path and never a USB adapter.
    for p in argyll_serial_exclusion_ports():
        assert p.startswith("/dev/cu.")
        assert "usbserial" not in p and "usbmodem" not in p
