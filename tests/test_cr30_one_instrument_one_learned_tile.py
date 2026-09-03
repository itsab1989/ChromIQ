"""A CR30 is ONE instrument, whichever cable or radio it answers on.

Knut, 2026-09-03: *"in a very short test via usb the read single patches tool
asked me to learn the white tile of the device via usb again although chromiq
should already have learned it."*

The store was already shared — one `AppSettings` key, `cr30_tile_signatures`.
The KEY was not. Over USB `identify()` reads the unit's own `second_id`; over
Bluetooth the advertised name is that same string, but the remembered-address
FAST path never scans, so it had no name and filed the signature under
`ble:<address>` instead. `learned_signature()` refuses to fall back when a unit
id is given, so the same instrument on the other transport found nothing and was
asked to learn its tile a second time.

Two halves, and this file pins both:

* the fast path can know the unit after all. Measured on his CR30, 2026-09-03,
  connecting **by address alone** with no discovery at all::

      advertised name from a scan : 'CM454M0223'
      peripheral.name() connected : 'CM454M0223'

  The portable route, the GAP Device Name characteristic 0x2A00, does NOT exist
  on this device, so the name comes from the bleak backend and every attempt is
  optional.

* the signature already filed under an address is re-filed under the unit at
  the ONE moment that is provable rather than a guess: while connected to that
  address, having just heard the device name itself.

The refusal matters as much as the migration. Adopting an `ble:` key at a USB
open would make `guard_is_armed()` answer True on an instrument whose constant
does not match — a false assurance, and worse than the honest "unarmed".
"""
import pytest

from workflow.cr30 import ble, tile_learning as tl
from workflow.cr30.measure_bridge import DeviceReader

UNIT = "CM454M0223"                                    # his unit, measured
OTHER_UNIT = "CM454M0999"
ADDRESS = "FFB32AD2-D165-6D79-A509-5EA1566707A0"       # his Mac, measured
OTHER_ADDRESS = "9A8B7C6D-5E4F-4321-8765-4321FEDCBA98"

SIG = [12.5] * 31
OTHER_SIG = [17.19] * 31


class _Link:
    def __init__(self, address=None):
        self.address = address


class _Dev:
    def __init__(self, unit_id=None, address=None):
        self.unit_id = unit_id
        self.learned_tile = None
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


def _stored(store) -> dict:
    import json
    return json.loads(store.get(tl.SIGNATURE_KEY, "{}"))


# ---- the migration -------------------------------------------------------
def test_a_tile_learned_on_the_bluetooth_fast_path_is_found_over_usb(store):
    """His report, end to end at the store."""
    tl.remember_signature(SIG, f"ble:{ADDRESS}")
    assert tl.learned_signature(UNIT) is None, "before: USB finds nothing"

    assert tl.adopt_address_key(ADDRESS, UNIT) is True
    assert tl.learned_signature(UNIT) == SIG, "after: USB finds it"
    assert f"ble:{ADDRESS}" not in _stored(store), \
        "the legacy key was left behind to drift"


def test_a_unit_never_adopts_a_key_it_did_not_answer_at(store):
    """The whole point of keying: unit B must not wear unit A's constant."""
    tl.remember_signature(SIG, f"ble:{ADDRESS}")
    assert tl.adopt_address_key(OTHER_ADDRESS, OTHER_UNIT) is False
    assert _stored(store) == {f"ble:{ADDRESS}": SIG}
    assert tl.learned_signature(OTHER_UNIT) is None


def test_a_unit_that_already_learned_keeps_its_own_signature(store):
    """A stale address key must never overwrite a real learning."""
    tl.remember_signature(SIG, UNIT)
    tl.remember_signature(OTHER_SIG, f"ble:{ADDRESS}")
    assert tl.adopt_address_key(ADDRESS, UNIT) is False
    assert tl.learned_signature(UNIT) == SIG
    assert f"ble:{ADDRESS}" not in _stored(store), "the duplicate stayed"


def test_nothing_happens_without_both_halves(store):
    tl.remember_signature(SIG, f"ble:{ADDRESS}")
    assert tl.adopt_address_key(None, UNIT) is False
    assert tl.adopt_address_key(ADDRESS, None) is False
    assert tl.adopt_address_key(ADDRESS, f"ble:{ADDRESS}") is False
    assert _stored(store) == {f"ble:{ADDRESS}": SIG}


def test_an_empty_store_is_not_disturbed(store):
    assert tl.adopt_address_key(ADDRESS, UNIT) is False
    assert _stored(store) == {}


# ---- the moment it runs --------------------------------------------------
def test_arming_migrates_when_the_unit_names_itself_over_that_address(store):
    """`_arm_tile_guard` is the one place that holds both halves at once."""
    tl.remember_signature(SIG, f"ble:{ADDRESS}")
    reader = DeviceReader.__new__(DeviceReader)
    reader.unit_id = None
    dev = reader._arm_tile_guard(_Dev(unit_id=UNIT, address=ADDRESS))
    assert dev.learned_tile == SIG, "the guard was left unarmed"
    assert reader.unit_id == UNIT
    assert list(_stored(store)) == [UNIT]


def test_a_usb_open_does_not_adopt_an_address_key(store):
    """No address, no proof, no adoption — the guard stays honestly unarmed.

    A wrong adoption would make `guard_is_armed()` answer True while the check
    matched nothing, which permits the keyboard trigger on an instrument with
    no magnet protection at all.
    """
    tl.remember_signature(SIG, f"ble:{ADDRESS}")
    reader = DeviceReader.__new__(DeviceReader)
    reader.unit_id = None
    dev = reader._arm_tile_guard(_Dev(unit_id=UNIT, address=None))
    assert dev.learned_tile is None
    assert list(_stored(store)) == [f"ble:{ADDRESS}"]


def test_the_bluetooth_fast_path_still_keys_by_address_when_nothing_names_it(store):
    """The fallback has to survive: not every backend can name a peripheral."""
    reader = DeviceReader.__new__(DeviceReader)
    reader.unit_id = None
    assert reader._signature_key(_Dev(unit_id=None, address=ADDRESS)) == f"ble:{ADDRESS}"


# ---- asking a connected peripheral what it is called ---------------------
class _Peripheral:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Client:
    def __init__(self, backend):
        self._backend = backend


class _Backend:
    pass


def test_a_connected_peripheral_is_asked_for_its_name():
    backend = _Backend()
    backend._peripheral = _Peripheral(UNIT)
    assert ble._connected_name(_Client(backend)) == UNIT


def test_a_backend_that_cannot_name_it_costs_nothing():
    assert ble._connected_name(None) is None
    assert ble._connected_name(_Client(None)) is None
    assert ble._connected_name(_Client(_Backend())) is None


def test_a_backend_that_raises_costs_nothing():
    class _Angry:
        @property
        def _peripheral(self):
            raise RuntimeError("no CoreBluetooth here")

    assert ble._connected_name(_Client(_Angry())) is None


def test_a_blank_name_is_not_an_identity():
    backend = _Backend()
    backend._peripheral = _Peripheral("   ")
    assert ble._connected_name(_Client(backend)) is None


def test_a_scan_keeps_the_name_it_just_read():
    """Even the SCANNING path threw the unit id away.

    `discover()` returns the advertised name, `open()` used only the address
    from it, and `unit_id` was set by `identify()` — which
    `DeviceReader._open_ble` calls on the remembered-address branch and NOT on
    the discovery one. So a CR30 found by scanning was keyed by its address too,
    with its own id in hand the whole time.
    """
    import inspect
    src = inspect.getsource(ble.BleTransport.open)
    assert 'self.name = self.name or (ok[0].get("name") or None)' in src
    # …and INSIDE the scan branch. It was first written one indent out, where
    # `ok` does not exist, and the fast path raised UnboundLocalError before it
    # could connect at all — caught by four existing Bluetooth tests, not by
    # this one.
    line = [l for l in src.splitlines() if "self.name = self.name or" in l][0]
    assert len(line) - len(line.lstrip()) == 16, repr(line)


def test_opening_over_bluetooth_names_the_unit_without_a_round_trip(monkeypatch):
    """`open_ble` sets `unit_id` itself, so no caller has to remember to."""
    from workflow.cr30.device import CR30

    class _T:
        name = UNIT
        address = ADDRESS

        def open(self):
            pass

    monkeypatch.setattr(ble, "BleTransport", lambda *a, **k: _T())
    dev = CR30.open_ble(address=ADDRESS)
    assert dev.unit_id == UNIT
    assert dev.kind == "ble"


def test_a_transport_with_no_name_leaves_the_unit_unknown(monkeypatch):
    from workflow.cr30.device import CR30

    class _T:
        name = None
        address = ADDRESS

        def open(self):
            pass

    monkeypatch.setattr(ble, "BleTransport", lambda *a, **k: _T())
    assert CR30.open_ble(address=ADDRESS).unit_id is None


def test_the_open_path_actually_asks(monkeypatch):
    """The helper is worth nothing unless the fast path calls it."""
    import inspect
    src = inspect.getsource(ble.BleTransport.open)
    assert "_connected_name(c)" in src
    assert src.index("await c.connect()") < src.index("_connected_name(c)"), \
        "the name is asked for before the connection exists"
