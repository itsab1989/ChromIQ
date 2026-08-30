"""Beta 2: over Bluetooth, ChromIQ connected to anything advertising `ffe0`.

`ffe0` is the HM-10 module's service UUID — it is in countless hobby gadgets,
not just in a CR30. `BleTransport.open()` did:

    ok = [c for c in cands if c["confirmed"]] or cands

so when nothing confirmed, it took the first advertiser it saw. This is the
Bluetooth twin of the USB fault where `open_usb()` trusted `candidates()[0]`,
and review established the consequences do not stop at a failed read:

* the address is **REMEMBERED** for next time, so one misfire persists;
* the next frames written to that stranger are **calibration commands**.

**And the fallback protected almost nothing.** A CR30 held by a phone app does
not advertise at all, so it never reaches the list. A freshly calibrated one
still confirms, because confirmation reads the stored slot's AXIS and a
zero-filled slot still carries its header. The one genuine case is a transient
timing miss — `discover()` allows roughly 1.6 s for a reply — which one retry
serves far better than accepting anything that answers.
"""
from __future__ import annotations

import asyncio
import inspect
import sys
import types

import pytest

from workflow.cr30 import ble


def _cand(addr, confirmed, name="", axis=None):
    e = {"name": name, "address": addr, "rssi": -50, "confirmed": confirmed}
    if axis:
        e["axis"] = axis
    return e


@pytest.fixture
def fake_ble(monkeypatch):
    """A radio and a discovery we control. Everything above them is real."""
    state = {"rounds": [], "connected": None}

    class _Client:
        def __init__(self, target, timeout=None):
            self.target = target
        async def connect(self):
            state["connected"] = self.target
        async def start_notify(self, char, cb):
            pass
        async def stop_notify(self, char):
            pass
        async def disconnect(self):
            pass

    class _Scanner:
        @staticmethod
        async def find_device_by_name(name, timeout=None):
            return None

    mod = types.ModuleType("bleak")
    mod.BleakClient = _Client
    mod.BleakScanner = _Scanner
    monkeypatch.setitem(sys.modules, "bleak", mod)

    async def _discover(timeout=None, verify=True):
        return state["rounds"].pop(0) if state["rounds"] else []
    monkeypatch.setattr(ble, "discover", _discover)
    return state


def _open(state, rounds):
    state["rounds"] = list(rounds)
    t = ble.BleTransport()
    t.open()
    return t


def test_a_confirmed_device_is_used(fake_ble):
    t = _open(fake_ble, [[_cand("aa:bb", True)]])
    assert fake_ble["connected"] == "aa:bb"


def test_an_unconfirmed_gadget_is_refused(fake_ble):
    """The whole point. An HM-10 in somebody's project must not be adopted as
    an instrument and then sent calibration commands."""
    with pytest.raises(ConnectionError) as e:
        _open(fake_ble, [[_cand("gadget", False, "HMSoft")],
                         [_cand("gadget", False, "HMSoft")]])
    assert fake_ble["connected"] is None, "it connected to the gadget anyway"
    msg = str(e.value).lower()
    assert "not identified" in msg or "has not identified" in msg
    assert "hobby" in msg, "the message does not explain why it is refusing"


def test_it_names_what_it_saw(fake_ble):
    """"No CR30 found" while a device is plainly advertising is unhelpful."""
    with pytest.raises(ConnectionError) as e:
        _open(fake_ble, [[_cand("x", False, "HMSoft", (400, 10, 16))],
                         [_cand("x", False, "HMSoft", (400, 10, 16))]])
    assert "HMSoft" in str(e.value)


def test_a_transient_miss_is_retried_once(fake_ble):
    """The one real case the old fallback covered: discover() allows about
    1.6 s for a reply, and a slow CR30 can miss it. A retry serves that; taking
    any advertiser does not."""
    t = _open(fake_ble, [[_cand("cr30", False)],       # first look: missed it
                         [_cand("cr30", True)]])       # second: confirmed
    assert fake_ble["connected"] == "cr30"


def test_nothing_at_all_keeps_the_old_advice(fake_ble):
    """A CR30 held by a phone app does not advertise, and that message is the
    one that helps."""
    with pytest.raises(ConnectionError) as e:
        _open(fake_ble, [[], []])
    assert "phone app" in str(e.value)


def test_the_or_cands_fallback_is_gone():
    src = inspect.getsource(ble.BleTransport.open)
    assert 'or cands' not in src, (
        "unconfirmed devices are accepted again when nothing confirms")


# ---- and identify() must compare the axis, not merely parse it ----------

def test_identify_refuses_an_echoing_gadget():
    """`identify()`'s BLE branch parsed the axis and then ignored it, so any
    device echoing a measurement header was pronounced a CR30 — the same shape
    as `Identity.is_cr30()` having had no callers."""
    from workflow.cr30.device import CR30
    from workflow.cr30.measurement import MeasurementError
    import struct

    raw = bytearray(64)
    raw[0:4] = ble.MEASUREMENT_HDR
    # bytes 4..7 of a reply: uint16 BE start, uint8 step, uint8 count
    struct.pack_into(">HBB", raw, 4, 400, 10, 16)      # 16 bands, not 31

    class _T:
        def ask(self, *a, **k):
            return bytes(raw)

    d = CR30.__new__(CR30)
    d.kind, d._t, d._previous, d.model = "ble", _T(), None, None
    with pytest.raises(MeasurementError) as e:
        d.identify()
    assert "not a CR30" in str(e.value)


def test_identify_accepts_the_real_axis():
    from workflow.cr30.device import CR30
    import struct
    raw = bytearray(64)
    raw[0:4] = ble.MEASUREMENT_HDR
    struct.pack_into(">HBB", raw, 4, 400, 10, 31)

    class _T:
        def ask(self, *a, **k):
            return bytes(raw)

    d = CR30.__new__(CR30)
    d.kind, d._t, d._previous, d.model = "ble", _T(), None, None
    assert d.identify()["model"] == "CR30"
