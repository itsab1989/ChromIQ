"""Device discovery -- the ONLY OS-aware module in the package.

Kept separate so that `frame`, `identity`, `session` and the replay tests never
touch platform code. Importing this module is optional; the decoder does not.

Why identification is not a descriptor match -- **VERIFIED**, TRANSPORT_USB.md:
the USB descriptors belong to the **CH554 serial bridge**, not to the
instrument. VID:PID is `0x1A86:0x7523`, the product string is `CH554_CDC`, and
`iSerialNumber` is **0**. Every CH34x-class adapter on the machine looks
identical, and two CR30s cannot be told apart at all. So descriptor matching can
only ever produce *candidates*.

**The only trustworthy CR30 identification is asking the device**: `AA 0A 00 00`
returns the ASCII model string `CR30` (VERIFIED, EXP-MAC-USB-001). `identify()`
in `session.py` is the real test; this module just narrows the search.
"""
from __future__ import annotations

from dataclasses import dataclass

CH34X_VID = 0x1A86
CH34X_PID = 0x7523


@dataclass(frozen=True)
class Candidate:
    """A serial port that MIGHT be a CR30. Confirmed only by asking the device."""
    device: str
    vid: int | None
    pid: int | None
    product: str | None

    @property
    def is_ch34x(self) -> bool:
        return self.vid == CH34X_VID and self.pid == CH34X_PID


def candidates(*, only_ch34x: bool = True) -> list[Candidate]:
    """Serial ports that could carry a CR30. Never claims one IS a CR30.

    Deliberately does not hard-code `COM3` (every published prior-art capture
    does) or `/dev/cu.usbserial-10` (the node number is not stable across
    replugs on macOS -- observed).
    """
    from serial.tools import list_ports  # noqa: PLC0415 -- lazy: keeps pyserial optional
    found = [Candidate(p.device, p.vid, p.pid, p.product) for p in list_ports.comports()]
    return [c for c in found if c.is_ch34x] if only_ch34x else found
