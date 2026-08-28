"""CR30 wire framing.

Transport-agnostic: this module never imports serial or bleak. It turns bytes
into frames and frames into bytes, and it is the only place the checksum rule
lives.

Every rule here is VERIFIED against real device traffic; see PROTOCOL.md.
"""
from __future__ import annotations

from dataclasses import dataclass

FRAME_SIZE = 60
MARKER = 58          # index of the marker byte
CHECKSUM = 59        # index of the checksum byte

START_IDENTITY = 0xAA
START_COMMAND = 0xBB


class FrameError(Exception):
    """Base class. A malformed frame is always an error, never a warning."""


class ShortFrameError(FrameError):
    """Fewer than FRAME_SIZE bytes were available."""


class ChecksumError(FrameError):
    """Received frame failed its checksum."""


def checksum(data: bytes) -> int:
    """Checksum over bytes 0..58 inclusive, mod 256.

    VERIFIED against every device-originated frame captured so far
    (EXP-MAC-USB-001). Note this INCLUDES the marker byte at index 58.

    Relation to itohio/color-science, stated precisely (PROTOCOL.md 2):

    * Their 0xAA branch, `sum(0..57)`, is **DISPROVEN** -- off by exactly +1 on
      every real 0xAA frame, because it omits the marker (0xFF == -1 mod 256).
    * Their 0xBB branch, `sum(0..57) - 1`, is **arithmetically identical to this
      rule on any frame whose marker byte 58 is 0xFF**, and differs by exactly 1
      when it is 0x00. On the four command classes EXP-USB-006 could reach
      (`AA 0A`, `BB 13`, `BB 17`, `BB 28`) the device sets byte 58 to 0xFF
      whatever the request contained, so those frames cannot separate the rules.

      **The measurement header can, and does.** `BB 01 09` carries marker 0x00:
      20 such frames in the vendor corpus (PRIORART-001, a second unit) satisfy
      `sum(0..58)` 20/20 and itohio's rule **0/20**. Across all 637 vendor
      frames ours holds 637/637 and theirs 617/637.

      So their 0xBB branch is **DISPROVEN too** -- and precisely on the frames a
      real implementation must parse. Corrected after `[CR30-SKEPTIC]` showed
      this docstring had over-generalised "every frame it emits" from four
      classes to all of them (PROTOCOL.md 7.1a).

    One unified rule beats a rule plus a special case. And "the published
    checksum is wrong" is now true of both branches, for two different reasons.
    """
    return sum(data[:CHECKSUM]) % 256


@dataclass(frozen=True)
class Frame:
    """One 60-byte CR30 frame.

    `payload` is bytes 4..57 -- everything structurally between the four header
    bytes and the marker. That is a statement about the FRAME, not about how
    much of it the device fills in.

    **The device does not write all of it.** VERIFIED (EXP-USB-006): a reply is
    the request buffer mutated in place. For the `AA 0A` class the device
    overwrites exactly offsets **5..54**, forces byte 58 to `0xFF` and
    recomputes byte 59; offsets **4, 55, 56 and 57 come back holding the bytes
    the caller sent**. Proof: a request with `A5 5A` at offsets 56-57 was
    answered with `A5 5A` still at 56-57, and a request whose payload was a
    ramp came back with the ramp intact at 4 and 55..57.

    This retires PROTOCOL.md 6 Q1. Session 1 saw `0x00` at 56-57 in every frame
    and could not tell whether they were payload; they were zero because the
    *requests* were zero there. Prior art's "payload = 4..55" and this class's
    "4..57" are both statements about the frame, and NEITHER describes the
    response body. Use `session.RESPONSE_BODY_START/END` for that, and
    `session.device_written_bytes()` to see what a given reply really contains.

    HYPOTHESIS: the 5..54 span is command-class specific, and a measurement
    chunk may differ. It has been measured for `AA 0A` and `BB 13` only.
    """

    start: int
    cmd: int
    subcmd: int
    param: int
    payload: bytes          # bytes 4..57 inclusive -> 54 bytes (see below)
    marker: int = 0xFF
    received_checksum: int | None = None   # set only by parse(verify=False)

    PAYLOAD_SIZE = MARKER - 4       # 54

    def __post_init__(self) -> None:
        if len(self.payload) != self.PAYLOAD_SIZE:
            raise FrameError(
                f"payload must be {self.PAYLOAD_SIZE} bytes, got {len(self.payload)}")

    # -- encode ----------------------------------------------------------
    def to_bytes(self) -> bytes:
        """Serialise, ALWAYS recomputing the checksum.

        Defect filed by `[CR30-SKEPTIC]` and fixed: `parse(verify=False)`
        followed by `to_bytes()` used to launder a corrupt frame into a
        checksum-valid one, silently. A frame parsed with `verify=False` now
        remembers that (`self.received_checksum`), `is_intact()` reports it, and
        `to_bytes_as_received()` returns the ORIGINAL bytes so a corrupt capture
        can be logged verbatim rather than repaired (CLAUDE.md 14).
        """
        d = bytearray(FRAME_SIZE)
        d[0], d[1], d[2], d[3] = self.start, self.cmd, self.subcmd, self.param
        d[4:MARKER] = self.payload
        d[MARKER] = self.marker
        d[CHECKSUM] = checksum(d)
        return bytes(d)

    def to_bytes_as_received(self) -> bytes:
        """The frame exactly as it arrived, checksum included, never repaired."""
        d = bytearray(self.to_bytes())
        if self.received_checksum is not None:
            d[CHECKSUM] = self.received_checksum
        return bytes(d)

    def is_intact(self) -> bool:
        """False when this frame was parsed with verify=False and did not match."""
        return (self.received_checksum is None
                or self.received_checksum == checksum(self.to_bytes()))

    # -- decode ----------------------------------------------------------
    @classmethod
    def parse(cls, data: bytes, *, verify: bool = True) -> "Frame":
        """Parse a received frame.

        Raises rather than repairing. A short or corrupt frame must never be
        rounded up into a usable one (CLAUDE.md §14).
        """
        if len(data) < FRAME_SIZE:
            raise ShortFrameError(
                f"need {FRAME_SIZE} bytes, got {len(data)}: {data.hex()}")
        if len(data) > FRAME_SIZE:
            raise FrameError(
                f"expected exactly {FRAME_SIZE} bytes, got {len(data)}; "
                "refusing to guess frame boundaries")
        if verify:
            want = checksum(data)
            if data[CHECKSUM] != want:
                raise ChecksumError(
                    f"checksum 0x{data[CHECKSUM]:02X}, expected 0x{want:02X} "
                    f"for frame {data.hex()}")
        return cls(start=data[0], cmd=data[1], subcmd=data[2], param=data[3],
                   payload=bytes(data[4:MARKER]), marker=data[MARKER],
                   received_checksum=data[CHECKSUM])

    @classmethod
    def build(cls, start: int, cmd: int, subcmd: int = 0, param: int = 0,
              data: bytes = b"", marker: int = 0xFF) -> "Frame":
        if len(data) > cls.PAYLOAD_SIZE:
            raise FrameError(
                f"data too long: {len(data)} > {cls.PAYLOAD_SIZE}")
        return cls(start, cmd, subcmd, param,
                   data + bytes(cls.PAYLOAD_SIZE - len(data)), marker)

    def hex(self) -> str:
        return self.to_bytes().hex(" ")
