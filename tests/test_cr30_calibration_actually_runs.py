"""#159: the calibration flow, EXECUTED rather than read.

This exists because of a shipped blocker. `black=` was added to
`CR30.calibrate` and not to `DeviceReader.calibrate` — the wrapper the Measure
tab actually calls — so every CR30 calibration raised

    TypeError: DeviceReader.calibrate() got an unexpected keyword argument 'black'

and no CR30 measurement could start at all, on either transport, whether or not
the black step was ticked. It was the feature the branch exists for, broken by
the commit that added to it.

**Three tests covered this flow and all three passed.** Every one of them read
`inspect.getsource` and matched text. Not one called anything. A test that reads
the source can prove a line is present; only a test that RUNS it can prove the
line works — and a signature mismatch is invisible to the first kind by
construction.

So these call the real objects with the real signatures. They stub the
transport, never the code under test.
"""
from __future__ import annotations

import pytest

from workflow.cr30.device import CR30
from workflow.cr30.measure_bridge import DeviceReader


class _Transport:
    """A CR30 that answers commands and hands back a readable spectrum."""

    kind = "usb"

    def __init__(self):
        self.sent: list[bytes] = []
        self.reads = 0

    # -- what CR30.calibrate uses over USB
    def send(self, frame):
        self.sent.append(frame.to_bytes())

    def receive(self, timeout=None):
        class _R:
            @staticmethod
            def to_bytes():
                return bytes([0xBB, 0x11, 0x00]) + bytes(57)
        return _R()

    def reset_input(self):
        pass


def _reader(monkeypatch, spectrum=None):
    """A real DeviceReader whose device is a real CR30 on a stub transport."""
    dev = CR30.__new__(CR30)
    dev.kind = "usb"
    dev._t = _Transport()
    dev._previous = None
    dev.model = "CR30"

    from workflow.cr30.measurement import Measurement
    vals = spectrum if spectrum is not None else [0.0] * 31

    # The signature MIRRORS the real one, argument for argument. A stub that
    # quietly accepted **kw would have swallowed `allow_dark` and this file
    # would have gone on passing while the real read-back was still rejecting
    # the very reading it exists to take.
    def _read(self, *, enforce=True, allow_dark=False, button_header=None):
        self._t.reads += 1
        self._t.allow_dark = allow_dark
        return Measurement(wavelengths=list(range(400, 710, 10)),
                           values=list(vals), gate_flag=None, transport="usb")

    monkeypatch.setattr(CR30, "read_measurement", _read)
    monkeypatch.setattr(CR30, "trigger_unsafe", lambda self: None)

    r = DeviceReader()
    r._dev = dev
    return r, dev


def test_a_white_calibration_actually_runs(monkeypatch):
    """The blocker, in one line. This call is what the Measure tab makes."""
    r, dev = _reader(monkeypatch)
    r.calibrate(black=False)                     # must not raise
    assert dev._t.sent, "no command reached the instrument"
    assert dev._t.sent[0][:3].hex(" ") == "bb 11 00"


def test_a_black_calibration_actually_runs_and_sends_the_other_command(monkeypatch):
    r, dev = _reader(monkeypatch)
    r.calibrate(black=True)
    assert dev._t.sent[0][:3].hex(" ") == "bb 10 00"


def test_the_default_is_white(monkeypatch):
    r, dev = _reader(monkeypatch)
    r.calibrate()
    assert dev._t.sent[0][:3].hex(" ") == "bb 11 00"


def test_the_zero_check_takes_a_READING_not_the_stored_value(monkeypatch):
    """What a calibration leaves in the stored slot has never been established.
    Reading it without asking for a fresh measurement is the stale-cache
    pattern that once wrote the white-tile cache onto patch A1 at delta E 60.5.
    """
    triggered = []
    r, dev = _reader(monkeypatch, spectrum=[0.0] * 31)
    monkeypatch.setattr(CR30, "trigger_unsafe",
                        lambda self: triggered.append(True))
    zero = r.read_zero()
    assert triggered, "it read whatever was stored instead of measuring"
    assert zero == pytest.approx(0.0)


def test_the_zero_check_reports_what_it_saw(monkeypatch):
    r, _ = _reader(monkeypatch, spectrum=[2.0] * 31)
    assert r.read_zero() == pytest.approx(2.0)


def test_a_black_calibration_does_not_consume_its_own_answer(monkeypatch):
    """The white path reads back to seed the patch baseline. The black path must
    not, or read_zero's question is answered before it is asked."""
    r, dev = _reader(monkeypatch)
    r.calibrate(black=True)
    assert dev._t.reads == 0
    r.calibrate(black=False)
    assert dev._t.reads == 1


def test_the_dark_read_back_asks_for_a_reading_air_can_actually_give(monkeypatch):
    """#159, found on the owner's own Bluetooth session, 2026-08-30.

    The read-back after a black calibration failed with

        candidate at 0 has 31 zero bands (truncated reply)

    and the check silently did nothing. The guard is right about patches — a
    real dark patch reads a few percent, never exactly 0.0 — but the dark
    reference is taken against OPEN AIR, and air reads exactly 0.00000 %R on
    this instrument (EXP-022, before and after). The expected answer and the
    fault are byte-identical, so the check could never pass.

    Admitting it is safe because the check is one-sided: it warns when the dark
    reference reads too HIGH, and a truncated reply reads zero — the passing
    direction. It cannot turn a bad reference into a good report.
    """
    r, dev = _reader(monkeypatch)
    r.read_zero()
    assert getattr(dev._t, "allow_dark", False) is True, (
        "the dark read-back still asks for a reading air cannot give")
