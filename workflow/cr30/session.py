"""CR30 protocol session -- commands, on top of any Transport.

Knows the wire protocol. Knows nothing about serial ports, BLE, or ChromIQ.
Every rule carries its evidence; anything unproven says HYPOTHESIS out loud.

## The trap this module exists to prevent

**The CR30 echoes commands it does not implement.** VERIFIED, `EXP-USB-003`:
`BB 28 00 xx` (which itohio/color-science calls "query parameters" and issues on
every connect) and `BB 17 00 00` ("initialize device") both come back as an
exact copy of the request, with only byte 58 forced to `0xFF` and byte 59
recomputed. The device wrote **nothing**: a request carrying `A5 5A` at frame
offsets 53-54 got those same bytes back, where a real response would have
overwritten them.

So **a 60-byte reply is not evidence that a command exists.** Any command
discovery that counts replies will invent a command set. `is_echo()` below is
the discriminator, and `Session.transact_checked()` applies it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .frame import CHECKSUM, MARKER, Frame, START_COMMAND, START_IDENTITY
from .identity import (CMD_IDENTITY, Identity, SUB_BUILD, SUB_MODEL, SUB_SERIAL,
                       SUB_STATUS, parse_identity)
from .transport import DEFAULT_TIMEOUT_S, Transport, TransportError

# -- commands ---------------------------------------------------------------
# VERIFIED to be answered with real content:
CMD_CHECK = 0x13          # BB 13 00 00 + b"Check": writes frame offsets 5..10

# VERIFIED to be ECHOED, i.e. NOT implemented on firmware V11.3. / build
# 0.0.20231219 (EXP-USB-003). Named so nobody rediscovers them as "working".
ECHOED_COMMANDS = {0x17: "itohio 'initialize device' -- echoed, no device content",
                   0x28: "itohio 'query parameters'  -- echoed, no device content"}

# HYPOTHESIS ONLY -- prior-art claims, never sent by this project. Listed so
# that no code path can reach them by accident (PROTOCOL.md 5).
UNTESTED_CLAIMS = {0x10: "itohio: black calibration  (HYPOTHESIS, needs EXP-CAL-001)",
                   0x11: "itohio: white calibration  (HYPOTHESIS, needs EXP-CAL-001)",
                   0x01: "itohio: measure / chunk fetch (HYPOTHESIS, needs EXP-MEAS-001)"}

# VERIFIED (EXP-USB-006): for the AA 0A class the device overwrites exactly
# frame offsets 5..54, then sets byte 58 and recomputes byte 59. Offsets 4 and
# 55..57 come back holding the REQUEST's bytes.
#
# SCOPE, and it matters: this span is COMMAND-CLASS SPECIFIC. Measurement
# chunks write 6..53; the BB 01 09 header reaches byte 56 and sets marker 0x00
# (PROTOCOL.md 7.1). Do not use these constants to slice a measurement.
RESPONSE_BODY_START = 5
RESPONSE_BODY_END = 55            # exclusive; offsets 5..54, fifty bytes


def is_echo(request: Frame | bytes, reply: Frame | bytes) -> bool:
    """True when the device returned our own frame instead of a response.

    Compares everything except the two bytes the device always rewrites --
    marker 58 and checksum 59. VERIFIED discriminator, see the module docstring.
    """
    a = request.to_bytes() if isinstance(request, Frame) else bytes(request)
    b = reply.to_bytes() if isinstance(reply, Frame) else bytes(reply)
    return a[:MARKER] == b[:MARKER]


def device_written_bytes(request: Frame | bytes, reply: Frame | bytes) -> list[int]:
    """Offsets the device actually wrote. The honest measure of a response.

    Excludes 58 and 59, which the device rewrites unconditionally.
    """
    a = request.to_bytes() if isinstance(request, Frame) else bytes(request)
    b = reply.to_bytes() if isinstance(reply, Frame) else bytes(reply)
    return [i for i in range(MARKER) if a[i] != b[i]]


class EchoedCommandError(TransportError):
    """The device echoed the request: the command is not implemented."""


@dataclass
class CheckStatus:
    """Reply to `BB 13 00 00 + b"Check"`.

    VERIFIED: the device writes six bytes at frame offsets 5..10, of the shape
    `51 00 00 00 <u16 little-endian>`.

    HYPOTHESIS, all of it: what those bytes MEAN. `byte5` has been `0x51` (81)
    in every observation. `value16` was stable at one value across 20
    back-to-back reads, 50 intervening commands, a port close/reopen and 30 s of
    idle, yet was seen at three different values across a session. It is
    therefore **not** a command counter, **not** a uniform clock, and its
    meaning is NOT DETERMINED. Do not build anything on it.
    """
    byte5: int
    value16: int
    raw: bytes

    @classmethod
    def parse(cls, f: Frame) -> "CheckStatus":
        b = f.to_bytes()
        return cls(byte5=b[5], value16=int.from_bytes(b[9:11], "little"), raw=b[5:11])


class Session:
    """Protocol session. Composition, not inheritance -- swap the transport."""

    def __init__(self, transport: Transport):
        self.t = transport

    def __enter__(self) -> "Session":
        self.t.open(); return self

    def __exit__(self, *exc) -> None:
        self.t.close()

    # -- primitives ---------------------------------------------------------
    def transact(self, req: Frame, timeout: float = DEFAULT_TIMEOUT_S) -> Frame:
        return self.t.transact(req, timeout)

    def transact_checked(self, req: Frame, timeout: float = DEFAULT_TIMEOUT_S) -> Frame:
        """Transact, and refuse to treat an echo as a response."""
        reply = self.transact(req, timeout)
        if is_echo(req, reply):
            raise EchoedCommandError(
                f"device echoed 0x{req.start:02X} 0x{req.cmd:02X} 0x{req.subcmd:02X} "
                f"0x{req.param:02X} -- the command is not implemented on this "
                "firmware, the reply carries no device data (EXP-USB-003)")
        return reply

    # -- commands -----------------------------------------------------------
    def identify(self) -> Identity:
        """`AA 0A 00..03 00`. VERIFIED (EXP-MAC-USB-001).

        Confirm the instrument with `Identity.is_cr30()`; USB descriptors
        cannot (see discovery.py).
        """
        frames = {}
        for sub in (SUB_MODEL, SUB_SERIAL, SUB_BUILD, SUB_STATUS):
            req = Frame.build(START_IDENTITY, CMD_IDENTITY, sub, 0x00)
            frames[sub] = self.transact(req)
        return parse_identity(frames)

    def check(self) -> CheckStatus:
        """`BB 13 00 00 + b"Check"`. VERIFIED to be a real, implemented command.

        The only 0xBB command this project has confirmed the device acts on.
        Its response is NOT decoded -- see `CheckStatus`.
        """
        req = Frame.build(START_COMMAND, CMD_CHECK, 0x00, 0x00,
                          data=b"Check" + b"\x00" * 7)
        return CheckStatus.parse(self.transact_checked(req))
