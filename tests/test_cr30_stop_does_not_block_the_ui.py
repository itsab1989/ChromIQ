"""#159 (Basti, 2026-08-28): the beachball on Stop, twice on real hardware.

Measured in his log: patch armed 22:11:19.339, app frozen from his quit until
22:14:19.872 — 180.5 s, against a `button_timeout_s` of 180.0. A second
incident the same evening landed on 180.0 s. He had unplugged the instrument
before the second one and it made no difference: the wait ran to the ceiling
either way.

The GUI thread was waiting on `DeviceReader._lock`, held by the worker for the
whole of `read_next_measurement`. `cancel()` existed and had NO production
caller — only a test. So Stop asked politely for a lock nobody was going to
release until the operator pressed a button they had already decided not to
press.
"""
from __future__ import annotations

import threading
import time

import pytest

from workflow.cr30.measure_bridge import Cr30MeasureBridge, DeviceReader

CEILING = 4.0          # stands in for button_timeout_s, to keep the test quick


class _StubDevice:
    """A device nobody ever presses, whose wait honours `cancelled` the way
    device.py's loop does."""

    kind = "usb"

    def __init__(self):
        self.closed = False

    def read_next_measurement(self, *, timeout, cancelled=None, poll=0.25,
                              for_learning=False, trigger_wanted=None):
        # Mirrors the real signature: a stand-in that takes fewer arguments
        # fails the caller the moment the real object grows one.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancelled is not None and cancelled():
                raise RuntimeError("cancelled")
            time.sleep(0.01)
        raise RuntimeError("no button press")

    def close(self):
        self.closed = True


def _reader() -> DeviceReader:
    r = DeviceReader()
    r.button_timeout_s = CEILING
    r._dev = _StubDevice()
    return r


def _wait_until_reading(r, timeout=2.0):
    """Block until the worker really holds the lock, so we time the contended
    case and not a race we won by luck."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if r._lock.locked():
            return True
        time.sleep(0.005)
    return False


def test_close_does_not_wait_for_a_button_nobody_will_press():
    r = _reader()
    err: list = []
    t = threading.Thread(target=lambda: err.append(_safe(r)), daemon=True)
    t.start()
    assert _wait_until_reading(r), "the worker never started reading"

    t0 = time.monotonic()
    r.close()
    blocked = time.monotonic() - t0

    assert blocked < 1.0, (
        f"Stop blocked the UI for {blocked:.2f} s — the beachball is back "
        f"(the wait's ceiling is {CEILING} s)")
    t.join(timeout=CEILING + 1)


def _safe(r):
    try:
        return r()
    except Exception as exc:      # noqa: BLE001 — the point is that it ends
        return exc


def test_stopping_the_bridge_cancels_the_reader():
    """Every stop path must get this, not only the one that remembers: it is
    `stop()` that all of them go through."""
    r = _reader()
    bridge = Cr30MeasureBridge(send=lambda _msg: None, reader=r)
    assert r._cancelled() is False
    bridge.stop()
    assert r._cancelled() is True, (
        "stop() left the reader waiting for the instrument's button")


def test_a_read_ended_by_the_stop_is_not_reported_to_the_user():
    """Cancelling is what makes Stop responsive, so the cancelled read now
    fails on EVERY stop. Reporting it would tell someone who just quit to press
    the instrument's button."""
    seen: list = []
    bridge = Cr30MeasureBridge(send=lambda _msg: None, reader=_reader())
    bridge.read_failed.connect(lambda loc, msg: seen.append((loc, msg)))
    bridge.stop()
    bridge._on_read_failed("A16", "cancelled while waiting for the button")
    assert seen == [], f"told the user about a read their own Stop ended: {seen}"
