"""The spot workflow must WAIT for the instrument's button, never read the cache.

A CR30 holds its last reading indefinitely. Reading without waiting returns it
instantly and with every appearance of success — measured on a real chart, patch
A1 (a lavender) received the stale white-tile cache at **delta E 76 = 60.5**,
written to the .ti3 in silence, after which every patch failed the
bit-identical guard with nothing to retry. The session was dead at patch two
while the message still said "press the button again".

No hardware: a fake device stands in for the instrument, which is the point —
this is a behavioural rule, not a protocol one.
"""
import pathlib
import sys
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow.cr30.measure_bridge import DeviceReader  # noqa: E402
from workflow.cr30.measurement import Measurement, MeasurementError  # noqa: E402

WL = list(range(400, 701, 10))


class FakeDevice:
    """A CR30 that only produces a new reading when `press()` is called."""

    kind = "usb"

    def __init__(self):
        self._pending = None
        self.reads = 0

    def press(self, level):
        self._pending = Measurement(WL, [float(level)] * 31)

    def read_next_measurement(self, *, timeout=180.0, cancelled=None, poll=0.01,
                              for_learning=False, trigger_wanted=None):
        # MIRROR THE REAL SIGNATURE. A stub that accepts fewer arguments than
        # the object it stands in for reports the caller broken the moment the
        # real one grows a parameter -- which is what happened when the
        # keyboard trigger added `trigger_wanted`.
        end = time.monotonic() + timeout
        if trigger_wanted is not None and trigger_wanted():
            self.press(50)              # the host asked; the device answers
        while self._pending is None:
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled")
            if time.monotonic() > end:
                raise MeasurementError("no button press")
            time.sleep(0.005)
        m, self._pending = self._pending, None
        self.reads += 1
        return m

    def close(self):
        pass


def _reader(dev):
    r = DeviceReader()
    r._dev = dev
    r.button_timeout_s = 2.0
    return r


def test_a_reading_is_not_returned_until_the_button_is_pressed():
    dev = FakeDevice()
    r = _reader(dev)
    out = []
    t = threading.Thread(target=lambda: out.append(r()), daemon=True)
    t.start()
    time.sleep(0.25)
    assert not out, "a value was produced before any button press — this is the bug"
    dev.press(42.0)
    t.join(timeout=3)
    assert out, "the reading never arrived after the press"
    x, y, z = out[0]
    assert y > 0


def test_each_patch_needs_its_own_press():
    """One press must not satisfy two patches — that is how a stale value gets
    written under the next patch's id."""
    dev = FakeDevice()
    r = _reader(dev)
    dev.press(40.0)
    first = r()
    out = []
    t = threading.Thread(target=lambda: out.append(r()), daemon=True)
    t.start()
    time.sleep(0.25)
    assert not out, "the second patch was answered without a second press"
    dev.press(60.0)
    t.join(timeout=3)
    assert out and out[0] != first


def test_waiting_gives_up_with_an_actionable_message():
    dev = FakeDevice()
    r = _reader(dev)
    with pytest.raises(MeasurementError, match="button"):
        r()


def test_cancel_ends_the_wait_promptly():
    """Stop must not block for the whole timeout."""
    dev = FakeDevice()
    r = _reader(dev)
    r.button_timeout_s = 30.0
    err = []
    t = threading.Thread(target=lambda: err.append(pytest.raises(
        MeasurementError, lambda: r()) if False else _swallow(r)), daemon=True)
    t.start()
    time.sleep(0.2)
    began = time.monotonic()
    r.cancel()
    t.join(timeout=3)
    assert not t.is_alive(), "cancel did not end the wait"
    assert time.monotonic() - began < 2.0, "cancel took too long"


def _swallow(r):
    try:
        return r()
    except MeasurementError as e:
        return e


def test_the_bridge_does_not_call_the_non_waiting_read():
    """Pin the regression directly: the old code called read_measurement()."""
    import inspect
    src = inspect.getsource(DeviceReader.__call__)
    assert "read_next_measurement" in src
    assert "self._dev.read_measurement()" not in src, (
        "the bridge is reading the device's CACHE again")


def test_the_mutation_lands():
    """A fake that always has a reading would pass the first test vacuously."""
    dev = FakeDevice()
    assert dev._pending is None
    with pytest.raises(MeasurementError):
        dev.read_next_measurement(timeout=0.05)
