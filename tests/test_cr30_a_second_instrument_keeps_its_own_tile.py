"""Two CR30s must never share one learned tile constant — on any platform.

The magnet guard recognises the value the instrument returns when something
magnetic is at the aperture. That value differs per unit: the only two CR30s
anyone has measured sit 4.69 %R apart. So a signature learned from one is
useless on the other — and worse, the keyboard trigger is permitted whenever the
guard reports itself armed, so a second instrument wearing the first one's
signature would allow Space while the magnet check was blind.

Over USB the key is the unit's own serial, read by `identify()`. Over Bluetooth
there is no id in the reply and the remembered-address fast path never scans, so
the ADDRESS stands in. That is platform-dependent in FORM but not in the
property that matters:

    macOS            a host-local CoreBluetooth UUID
    Windows, Linux   the device's MAC

Both are distinct per instrument on a given machine. These drive the real
`DeviceReader._signature_key` and the real `tile_learning` store; only the
settings backend is faked, which is the outermost edge.
"""
import pytest

from workflow.cr30 import tile_learning as tl
from workflow.cr30.measure_bridge import DeviceReader

#: The real shapes, taken from the project's own platform findings.
MACOS_UUID_A = "1B2C3D4E-5F60-4A7B-8C9D-0E1F2A3B4C5D"
MACOS_UUID_B = "9A8B7C6D-5E4F-4321-8765-4321FEDCBA98"
WINDOWS_MAC_A = "C4:BE:84:1A:2B:3C"
LINUX_MAC_B = "C4:BE:84:9F:8E:7D"


class _Link:
    def __init__(self, address=None):
        self.address = address


class _Dev:
    """Mirrors what the real CR30 exposes to the keying code."""

    def __init__(self, unit_id=None, address=None):
        self.unit_id = unit_id
        self._t = _Link(address)


@pytest.fixture
def store(monkeypatch):
    kept: dict = {}

    class _Settings:
        def get(self, key, default=None):
            return kept.get(key, default)

        def set(self, key, value):
            kept[key] = value

    monkeypatch.setattr(tl, "_settings", lambda: _Settings())
    return kept


def test_usb_keys_on_the_units_own_serial():
    assert DeviceReader._signature_key(_Dev(unit_id="CM454M0223")) == "CM454M0223"


@pytest.mark.parametrize("a,b", [
    pytest.param(MACOS_UUID_A, MACOS_UUID_B, id="macos-corebluetooth-uuid"),
    pytest.param(WINDOWS_MAC_A, LINUX_MAC_B, id="windows-linux-mac"),
])
def test_two_instruments_over_bluetooth_get_different_keys(a, b):
    ka = DeviceReader._signature_key(_Dev(address=a))
    kb = DeviceReader._signature_key(_Dev(address=b))
    assert ka and kb and ka != kb, (
        "two instruments would share one signature slot, and the second would "
        "be armed with the first one's constant")


@pytest.mark.parametrize("address", [MACOS_UUID_A, WINDOWS_MAC_A])
def test_the_second_instrument_is_left_unarmed_not_given_the_firsts(store, address):
    """The whole point. Unit A learns; unit B must get NOTHING, on every
    platform — never A's constant, which would allow Space while blind."""
    first = _Dev(address=address)
    tl.remember_signature([70.0] * 31, DeviceReader._signature_key(first))

    second = _Dev(address=MACOS_UUID_B if ":" not in address else LINUX_MAC_B)
    assert tl.learned_signature(DeviceReader._signature_key(second)) is None
    # and the first one still works
    assert tl.learned_signature(DeviceReader._signature_key(first)) == [70.0] * 31


def test_the_serial_wins_when_both_are_known():
    """USB gives both. The serial is the real identity and must be preferred,
    or the same instrument would file itself twice."""
    dev = _Dev(unit_id="CM454M0223", address=WINDOWS_MAC_A)
    assert DeviceReader._signature_key(dev) == "CM454M0223"


def test_an_instrument_with_neither_is_not_invented_a_key():
    """No id and no address: return None, so `learned_signature` applies its
    'exactly one signature' rule rather than keying on a made-up string."""
    assert DeviceReader._signature_key(_Dev()) is None
