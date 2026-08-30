"""#159: `BleTransport.open()` had no test, and a NameError reached the owner.

On 2026-08-30 timing instrumentation was added to the Bluetooth open path using
a module-level `log` that `ble.py` did not define. Nothing in the suite executes
that function — it needs a radio — so 8,170 tests passed and the fault surfaced
on his machine as:

    Over Bluetooth: name 'log' is not defined

This is the same shape as the two blockers found the same night: **code no test
executes**. A `NameError` in a branch that only runs against hardware is
invisible to every kind of test except one that runs the branch.

So: run it, with only the radio replaced. Everything above bleak is the real
code — the real `open()`, the real `_run`, the real event loop, the real
notification wiring.
"""
from __future__ import annotations

import sys
import types

import pytest

from workflow.cr30 import ble


class _FakeClient:
    """A bleak client that connects instantly and remembers what it was told."""

    def __init__(self, target, timeout=None):
        self.target = target
        self.notify_char = None
        self.connected = False
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def start_notify(self, char, callback):
        self.notify_char = char
        self._cb = callback

    async def stop_notify(self, char):
        pass

    async def disconnect(self):
        self.disconnected = True


@pytest.fixture
def fake_bleak(monkeypatch):
    """Stand in for the radio, and nothing else."""
    made: list[_FakeClient] = []

    def _client(target, timeout=None):
        c = _FakeClient(target, timeout)
        made.append(c)
        return c

    class _Scanner:
        @staticmethod
        async def find_device_by_name(name, timeout=None):
            return f"address-of-{name}"

    mod = types.ModuleType("bleak")
    mod.BleakClient = _client
    mod.BleakScanner = _Scanner
    monkeypatch.setitem(sys.modules, "bleak", mod)
    return made


def test_open_runs_without_raising(fake_bleak):
    """The whole point. A NameError here is invisible to every other test."""
    t = ble.BleTransport(name="CR30")
    t.open()
    assert t._client is not None, "open() returned without a client"


def test_it_connects_and_subscribes_to_the_right_characteristic(fake_bleak):
    t = ble.BleTransport(name="CR30")
    t.open()
    client = fake_bleak[0]
    assert client.connected, "it never connected"
    assert client.notify_char == ble.FFE1, (
        "notifications are not wired to the CR30's characteristic, so no "
        "button press and no reply could ever arrive")


def test_it_finds_the_device_by_name_when_given_no_address(fake_bleak):
    t = ble.BleTransport(name="CR30")
    t.open()
    assert fake_bleak[0].target == "address-of-CR30"


def test_an_address_is_used_directly_without_scanning(fake_bleak):
    """Scanning is the slow part; an address must skip it."""
    t = ble.BleTransport(address="11:22:33:44:55:66")
    t.open()
    assert fake_bleak[0].target == "11:22:33:44:55:66"


def test_it_says_how_long_each_phase_took(fake_bleak, caplog):
    """The instrumentation itself, which is what broke.

    The owner's two Bluetooth complaints are about WHERE the time goes, and
    find/connect have different cures — a slow find wants the address
    remembered, a slow connect wants the link opened before the window rather
    than inside it. So they are reported separately, and this pins that.
    """
    import logging
    with caplog.at_level(logging.INFO, logger="workflow.cr30.ble"):
        ble.BleTransport(name="CR30").open()
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "found in" in said and "connected in" in said, (
        f"the phase timings are not reported: {said!r}")


def test_close_runs_too(fake_bleak):
    """The other half of the same blind spot."""
    t = ble.BleTransport(name="CR30")
    t.open()
    client = fake_bleak[0]
    t.close()
    assert client.disconnected, "close() never disconnected the radio"
    assert t._client is None
