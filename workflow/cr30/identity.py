"""Device identity (command 0xAA 0x0A ss 0x00).

Field offsets are VERIFIED against EXP-MAC-USB-001, but from a single unit.
Offsets that held on one device are marked PROBABLE where a second unit could
disagree; see PROTOCOL.md §4.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .frame import Frame, START_IDENTITY

# VERIFIED (EXP-USB-006): the device writes frame offsets 5..54 for this class,
# so no identity field can extend past 54.
RESPONSE_BODY_END = 55          # exclusive

CMD_IDENTITY = 0x0A
SUB_MODEL = 0x00
SUB_SERIAL = 0x01
SUB_BUILD = 0x02
SUB_STATUS = 0x03


class IdentityError(ValueError):
    """An identity reply that cannot be trusted. Never a warning."""


def _ascii(payload: bytes, start: int, length: int) -> str:
    """Read a NUL-terminated ASCII field at an absolute frame offset.

    Defect filed by `[CR30-SKEPTIC]` and fixed: `length` used to be treated as
    an exact field width, taken from the values THIS unit happens to have. A
    unit with a longer model string was silently truncated, and `is_cr30()`
    then returned True for anything merely STARTING with "CR30".

    `length` is now a **bound**, not a width: the field is read up to the first
    NUL inside a window that extends to the end of the device-written region
    (frame offset 54, VERIFIED EXP-USB-006). If the value runs to that bound
    without a NUL, `truncated` is True and the caller must not treat it as
    complete.
    """
    lo = start - 4
    hi = min(len(payload), RESPONSE_BODY_END - 4)
    window = payload[lo:hi]
    nul = window.find(b"\x00")
    raw = window if nul < 0 else window[:nul]
    return raw.decode("ascii", errors="replace").strip()


def _ascii_bounded(payload: bytes, start: int, expected_len: int) -> tuple[str, bool]:
    """(value, truncated_or_longer_than_this_unit)."""
    v = _ascii(payload, start, expected_len)
    return v, len(v) > expected_len


@dataclass
class Identity:
    model: str = ""
    device_id: str = ""
    second_id: str = ""
    version_a: str = ""
    version_b: str = ""
    build: str = ""
    status_byte: int | None = None
    raw: dict = field(default_factory=dict)
    #: fields whose value ran to the end of the device-written region without a
    #: NUL -- i.e. this unit is not the unit the offsets were derived from.
    suspect_fields: list = field(default_factory=list)

    def is_cr30(self) -> bool:
        """The ONLY trustworthy CR30 identification.

        USB descriptors identify the CH34x bridge, not the instrument, and the
        device exposes no USB serial number -- so descriptor matching cannot
        distinguish a CR30 from any other CH34x device. Asking the device is
        the only sound test. See PLATFORM_SUPPORT.md.
        """
        return self.model.upper() == "CR30" and "model" not in self.suspect_fields


def parse_identity(frames: dict[int, Frame]) -> Identity:
    """Build an Identity from {subcmd: Frame} for subcmds 0x00..0x03."""
    ident = Identity()

    def take(name, sub, off, exp):
        v, suspect = _ascii_bounded(frames[sub].payload, off, exp)
        if suspect:
            ident.suspect_fields.append(name)
        setattr(ident, name, v)

    for sub, f in frames.items():
        if f.start != START_IDENTITY or f.cmd != CMD_IDENTITY:
            raise IdentityError(
                f"not an identity frame: start=0x{f.start:02X} cmd=0x{f.cmd:02X}")
        # The device echoes the request's sub-command at byte 2 -- free
        # request/response correlation, and it was not being checked.
        # Defect filed by `[CR30-SKEPTIC]`, fixed here.
        if f.subcmd != sub:
            raise IdentityError(
                f"reply/request mismatch: asked for sub-command 0x{sub:02X}, the "
                f"frame echoes 0x{f.subcmd:02X}. Replies are out of step -- "
                "refusing to attribute fields to the wrong query")
        if not f.is_intact():
            raise IdentityError(
                f"identity frame for sub 0x{sub:02X} failed its checksum; "
                "refusing to decode a frame known to be corrupt")
        ident.raw[sub] = f.to_bytes().hex()
        if sub == SUB_MODEL:
            take("device_id", sub, 9, 10)
            take("model", sub, 39, 4)
        elif sub == SUB_SERIAL:
            take("second_id", sub, 19, 10)
            take("version_a", sub, 49, 8)
        elif sub == SUB_BUILD:
            take("build", sub, 5, 12)
            take("version_b", sub, 29, 9)
        elif sub == SUB_STATUS:
            ident.status_byte = f.payload[19 - 4]
    return ident
