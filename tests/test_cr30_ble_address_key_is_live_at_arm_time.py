"""Re-check of f1ea856e: the address key must EXIST when the guard is armed.

`tests/test_cr30_a_second_instrument_keeps_its_own_tile.py` proves the keying
FUNCTION with a thin `_Dev` stand-in. What it cannot prove is the integration
condition the whole fix rests on: that a real Bluetooth session arrives at
`_arm_tile_guard` with `transport.address` already populated — on the
remembered-address fast path AND on discovery — and that `learn_tile` would
file under the very key `_arm_tile_guard` looks up. If the address were None
at that moment, `_signature_key` returns None, the lookup silently falls back
to the "exactly one signature" rule, and the hole f1ea856e closes reopens
without any test noticing.

So these drive the REAL `DeviceReader._open()` -> `CR30.open_ble` ->
`BleTransport` stack, faking only `bleak` (the radio) and the settings store —
the same harness discipline as `test_ble_remembered_address_is_identified.py`,
whose fixtures are reused.
"""
from __future__ import annotations

import json

from workflow.cr30 import tile_learning as tl
from workflow.cr30.measure_bridge import DeviceReader

from tests.test_ble_remembered_address_is_identified import (  # noqa: F401
    REAL_CR30, _FakeBleakScanner, fake_bleak, store)

SIGNATURE = [70.0 + i * 0.25 for i in range(31)]


def _seed(store, key):
    store[tl.SIGNATURE_KEY] = json.dumps({key: SIGNATURE})


def test_fast_path_arms_from_the_address_key_with_no_scan(fake_bleak, store):
    """Remembered address, scan forbidden: the guard must arm from
    `ble:<address>` — proving the address is populated at arm time."""
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = REAL_CR30
    _seed(store, f"ble:{REAL_CR30}")
    _FakeBleakScanner.forbid = True
    reader = DeviceReader(transport="ble")
    dev = reader._open()
    assert dev.learned_tile == SIGNATURE, (
        "the guard did not arm from the address key on the fast path — "
        "the address was not available when _arm_tile_guard ran")
    assert reader.unit_id == f"ble:{REAL_CR30}"


def test_discovery_path_arms_from_the_address_key(fake_bleak, store):
    """No remembered address: discovery chooses the unit, and the address it
    stored must be live by the time the guard arms."""
    _seed(store, f"ble:{REAL_CR30}")
    reader = DeviceReader(transport="ble")
    dev = reader._open()
    assert dev._t.address == REAL_CR30
    assert dev.learned_tile == SIGNATURE, (
        "the guard did not arm from the address key after discovery")


def test_learn_and_arm_agree_on_the_key(fake_bleak, store):
    """A signature filed by `learn_tile`'s key must be findable by
    `_arm_tile_guard`'s. Both call `_signature_key(dev)`; this pins the
    integration so a future asymmetry cannot file signatures nobody finds."""
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = REAL_CR30
    reader = DeviceReader(transport="ble")
    dev = reader._open()
    key_at_learn_time = DeviceReader._signature_key(reader._dev or dev)
    assert key_at_learn_time == reader.unit_id == f"ble:{REAL_CR30}", (
        "learn_tile and _arm_tile_guard would use different keys — a learned "
        "signature would be filed where arming never looks")
    # and a signature stored under that key is what a fresh session arms with
    tl.remember_signature(SIGNATURE, key_at_learn_time)
    dev2 = DeviceReader(transport="ble")._open()
    assert dev2.learned_tile == SIGNATURE


def test_a_stranger_address_key_arms_nothing(fake_bleak, store):
    """Failure direction: a signature stored for a DIFFERENT address must
    leave this unit unarmed — never armed with the foreign constant, and never
    refused as anything."""
    store[DeviceReader.REMEMBERED_ADDRESS_KEY] = REAL_CR30
    _seed(store, "ble:AA:AA:AA:AA:AA:99")     # some other unit's key
    dev = DeviceReader(transport="ble")._open()
    assert dev.learned_tile is None, (
        "a foreign unit's signature was inherited — the keyboard trigger "
        "would be allowed while the magnet check is blind")
