"""Beta 2: ChromIQ must not treat every CH340 device as an instrument.

`1a86:7523` is the generic CH340 USB-serial bridge. It is not a CR30 — it is
inside millions of unrelated devices: Arduinos, 3D printers, CNC controllers,
laser cutters, GPS modules, cheap adapters. ChromIQ's users are people who print
and make things, so a good number of them will have one plugged in AT THE SAME
TIME as their instrument.

Two faults, found by review after the owner asked "we just have to make sure
that chromiq does not greenlight any and every device that is connected via usb
this way":

1. **`open_usb()` took `candidates()[0]` and trusted it.** With any other CH340
   enumerating first, ChromIQ would treat a stranger's board as the instrument
   and go on to write a calibration frame to it.

2. **Opening the port asserted DTR and RTS.** `dsrdtr=False` only disables flow
   control; pyserial still raises both lines on open, because `_dtr_state` and
   `_rts_state` default to True. Most maker boards AUTO-RESET on DTR — that is
   how their bootloaders are entered — so merely LOOKING for an instrument
   restarted them. On a printer mid-job that is a ruined print.

Measured on the owner's Mac, 2026-08-30: ChromIQ's own open reported
`dtr True, rts True`; held low, his CR30 identified normally (`CR30`, V11.3).
So the safe form costs the instrument nothing.
"""
from __future__ import annotations

import inspect

import pytest

from workflow.cr30.device import CR30
from workflow.cr30.transport import SerialTransport


# ---- the control lines --------------------------------------------------

def test_the_port_is_opened_with_dtr_and_rts_held_low():
    src = inspect.getsource(SerialTransport.open)
    assert "ser.dtr = False" in src and "ser.rts = False" in src, (
        "opening the port still asserts the lines that reset a maker board")


def test_they_are_set_before_the_port_is_opened():
    """After `open()` is too late — the reset has already happened."""
    src = inspect.getsource(SerialTransport.open)
    assert src.index("ser.dtr = False") < src.index("ser.open()"), (
        "DTR is lowered after the port is opened, which is after the board "
        "has already been reset")


def test_dsrdtr_alone_is_not_mistaken_for_the_fix():
    """It was, for the whole of this instrument's life. `dsrdtr=False` is flow
    control; it says nothing about the line states."""
    src = inspect.getsource(SerialTransport.open)
    assert "dsrdtr" in src and "ser.dtr" in src, (
        "the only protection is dsrdtr again")


# ---- choosing a port ----------------------------------------------------

class _Cand:
    def __init__(self, device):
        self.device, self.vid, self.pid, self.product = device, 6790, 29987, None


@pytest.fixture
def fake_ports(monkeypatch):
    """Two CH340 devices: one that is not a CR30, and the instrument."""
    opened, identified = [], []

    class _T:
        def __init__(self, port):
            self.port = port
        def open(self):
            opened.append(self.port)
        def close(self):
            pass

    def _identify(self):
        identified.append(self._t.port)
        if self._t.port != "/dev/the-real-one":
            raise RuntimeError("no reply to AA 0A")
        self.model = "CR30"
        return {"model": "CR30"}

    import workflow.cr30.device as dev
    import workflow.cr30.discovery as disc
    import workflow.cr30.transport as tp
    monkeypatch.setattr(tp, "SerialTransport", _T)
    monkeypatch.setattr(disc, "candidates",
                        lambda: [_Cand("/dev/an-arduino"),
                                 _Cand("/dev/the-real-one")])
    monkeypatch.setattr(dev.CR30, "identify", _identify)
    return opened, identified


def test_a_ch340_that_is_not_a_cr30_is_not_accepted(fake_ports):
    opened, identified = fake_ports
    d = CR30.open_usb()
    assert d._t.port == "/dev/the-real-one", (
        "ChromIQ accepted the first CH340 it found as an instrument")


def test_every_candidate_is_asked_what_it_is(fake_ports):
    opened, identified = fake_ports
    CR30.open_usb()
    assert identified == ["/dev/an-arduino", "/dev/the-real-one"], (
        "a port was used without being identified")


def test_when_none_answer_the_error_says_why(monkeypatch):
    """"No instrument found" while a cable is plainly plugged in is the least
    helpful thing we could say, and the likeliest cause is that the CH340 the
    user can see is something else entirely."""
    class _T:
        def __init__(self, port): self.port = port
        def open(self): pass
        def close(self): pass

    import workflow.cr30.device as dev
    import workflow.cr30.discovery as disc
    import workflow.cr30.transport as tp
    monkeypatch.setattr(tp, "SerialTransport", _T)
    monkeypatch.setattr(disc, "candidates", lambda: [_Cand("/dev/an-arduino")])
    monkeypatch.setattr(dev.CR30, "identify",
                        lambda self: (_ for _ in ()).throw(RuntimeError("silence")))

    with pytest.raises(ConnectionError) as e:
        CR30.open_usb()
    msg = str(e.value).lower()
    assert "arduino" in msg or "3d printer" in msg or "cnc" in msg, (
        "the error does not tell the user their CH340 may not be an instrument")
    assert "/dev/an-arduino" in str(e.value), "it does not name what it tried"


def test_an_explicit_port_is_still_honoured(monkeypatch):
    """When the caller has already chosen, do not second-guess them."""
    asked = []
    class _T:
        def __init__(self, port): self.port = port
        def open(self): pass
        def close(self): pass
    import workflow.cr30.device as dev
    import workflow.cr30.transport as tp
    monkeypatch.setattr(tp, "SerialTransport", _T)
    monkeypatch.setattr(dev.CR30, "identify", lambda self: asked.append(1))
    d = CR30.open_usb("/dev/chosen-by-hand")
    assert d._t.port == "/dev/chosen-by-hand"
    assert asked == [], "an explicitly chosen port was interrogated anyway"
