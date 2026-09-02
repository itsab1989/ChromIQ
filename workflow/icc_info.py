"""Read an ICC profile's header (and a few key tags) without ArgyllCMS.

ArgyllCMS only understands ICC **v2** profiles — its gamut tools (``iccgamut``,
``tiffgamut``, ``viewgam``) and our soft-proof pipeline all refuse a **v4**
profile with a bare "ICC V4 not supported!" error. i1Profiler / X-Rite (creator
``'XRCM'``) and modern ColorSync exports are v4, so users hit this regularly.

This module parses the 128-byte ICC header (big-endian, per ICC.1:2010) plus a
best-effort profile description, so ChromIQ can:

  * show a friendly "Profile info" panel, and
  * detect v4 up front (:func:`is_v4`) and explain *why* a profile can't be
    visualised, instead of surfacing Argyll's cryptic error.

No third-party dependency and no Argyll call — just ``struct`` on the bytes.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

# ICC PCS reference white (D50), used to turn the absolute wtpt/bkpt XYZ tags
# into L*a*b*. These match the values ArgyllCMS reports for media-absolute Lab.
_D50 = (0.96422, 1.0, 0.82521)


def _f_lab(t: float) -> float:
    """CIE L*a*b* nonlinearity."""
    return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0


def xyz_to_lab(xyz: tuple[float, float, float],
               ref: tuple[float, float, float] = _D50) -> tuple[float, float, float]:
    """Convert an XYZ triple to L*a*b* against reference white ``ref`` (D50)."""
    fx, fy, fz = (_f_lab(c / r) for c, r in zip(xyz, ref))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))

# --- signature → friendly label maps (ICC.1:2010 tables) --------------------

_DEVICE_CLASS = {
    "scnr": "Input (scanner)",
    "mntr": "Display (monitor)",
    "prtr": "Output (printer)",
    "link": "Device link",
    "spac": "Colour space",
    "abst": "Abstract",
    "nmcl": "Named colour",
}

_COLOR_SPACE = {
    "XYZ ": "XYZ", "Lab ": "Lab", "Luv ": "Luv", "YCbr": "YCbCr",
    "Yxy ": "Yxy", "RGB ": "RGB", "GRAY": "Gray", "HSV ": "HSV",
    "HLS ": "HLS", "CMYK": "CMYK", "CMY ": "CMY",
    "2CLR": "2 colour", "3CLR": "3 colour", "4CLR": "4 colour",
    "5CLR": "5 colour", "6CLR": "6 colour", "7CLR": "7 colour",
    "8CLR": "8 colour", "9CLR": "9 colour", "ACLR": "10 colour",
    "BCLR": "11 colour", "CCLR": "12 colour", "DCLR": "13 colour",
    "ECLR": "14 colour", "FCLR": "15 colour",
}

_RENDER_INTENT = {
    0: "Perceptual",
    1: "Media-relative colorimetric",
    2: "Saturation",
    3: "ICC-absolute colorimetric",
}

# A few well-known creator / CMM signatures, for the "made by" hint.
_CREATORS = {
    "XRCM": "X-Rite (i1Profiler / ColorSync)",
    "appl": "Apple",
    "APPL": "Apple",
    "ADBE": "Adobe",
    "argl": "ArgyllCMS",
    "ARGL": "ArgyllCMS",
    "lcms": "Little CMS",
    "KCMS": "Kodak",
    "MSFT": "Microsoft",
    "HDM ": "Heidelberg",
    "GMG ": "GMG",
    "EFI ": "EFI",
}


@dataclass
class IccInfo:
    """Decoded ICC header fields plus a best-effort description."""
    path: Path
    size: int
    version_major: int
    version_minor: int
    device_class: str          # raw 4-char signature
    color_space: str           # raw 4-char signature
    pcs: str                   # raw 4-char signature
    rendering_intent: int
    creator: str               # raw 4-char signature
    platform: str              # raw 4-char signature
    is_embedded: bool
    white_point: tuple[float, float, float]   # header PCS illuminant (always D50)
    created: str               # "YYYY-MM-DD HH:MM:SS" or ""
    description: str           # from 'desc' tag, best-effort
    # Media white / black point tags (absolute XYZ). 'wtpt' is required by the
    # spec; 'bkpt' is optional and deprecated in v4, so it may be None.
    media_white: tuple[float, float, float] | None = None
    media_black: tuple[float, float, float] | None = None

    # -- friendly accessors -------------------------------------------------
    @property
    def version(self) -> str:
        return f"{self.version_major}.{self.version_minor}"

    # -- paper-white / max-black contrast ----------------------------------
    @property
    def white_lab(self) -> tuple[float, float, float] | None:
        return xyz_to_lab(self.media_white) if self.media_white else None

    @property
    def black_lab(self) -> tuple[float, float, float] | None:
        return xyz_to_lab(self.media_black) if self.media_black else None

    @property
    def contrast_ratio(self) -> float | None:
        """Luminance contrast ratio Y_white : Y_black (e.g. 193.0 → "193:1")."""
        if not (self.media_white and self.media_black):
            return None
        yw, yb = self.media_white[1], self.media_black[1]
        return yw / yb if yb > 0 else None

    @property
    def dynamic_range(self) -> float | None:
        """Dynamic range as an optical-density span, log10(Y_white / Y_black)."""
        r = self.contrast_ratio
        return math.log10(r) if r and r > 0 else None

    @property
    def delta_lstar(self) -> float | None:
        """Lightness spread between paper white and max black, L*_w − L*_b."""
        w, b = self.white_lab, self.black_lab
        return (w[0] - b[0]) if (w and b) else None

    @property
    def is_v4(self) -> bool:
        return self.version_major >= 4

    @property
    def device_class_label(self) -> str:
        return _DEVICE_CLASS.get(self.device_class, self.device_class.strip() or "—")

    @property
    def color_space_label(self) -> str:
        return _COLOR_SPACE.get(self.color_space, self.color_space.strip() or "—")

    @property
    def pcs_label(self) -> str:
        return _COLOR_SPACE.get(self.pcs, self.pcs.strip() or "—")

    @property
    def rendering_intent_label(self) -> str:
        return _RENDER_INTENT.get(self.rendering_intent, str(self.rendering_intent))

    @property
    def creator_label(self) -> str:
        sig = self.creator.strip()
        nice = _CREATORS.get(self.creator) or _CREATORS.get(sig)
        if nice:
            return f"{nice}  ({sig})" if sig else nice
        return sig or "—"


class IccParseError(ValueError):
    """Raised when the file is not a parseable ICC profile."""


def _sig(raw: bytes) -> str:
    """Decode a 4-byte signature to a string, preserving trailing spaces."""
    return raw.decode("latin-1", errors="replace")


def _read_desc(data: bytes, header_size: int) -> str:
    """Best-effort profile description from the 'desc' tag (v2 textDescription
    or v4 mluc). Returns '' if not found / unparseable."""
    try:
        count = struct.unpack_from(">I", data, 128)[0]
        table = 132
        for i in range(count):
            base = table + i * 12
            if base + 12 > len(data):
                break
            sig = data[base:base + 4]
            offset, size = struct.unpack_from(">II", data, base + 4)
            if sig != b"desc":
                continue
            if offset + 8 > len(data):
                return ""
            ttype = data[offset:offset + 4]
            if ttype == b"desc":
                # v2 textDescriptionType. THE UNICODE FIELD FIRST, and this is
                # the whole point of the tag having one: the ASCII field
                # cannot hold an accent, so Argyll fills it with `?` — a
                # profile called Müller-Prüfdruck reads back as
                # `M?ller-Pr?fdruck`, and a Russian or Japanese name reads
                # back as nothing but question marks. ChromIQ repairs the
                # Unicode field when it writes a profile, and then showed the
                # broken ASCII one in its own windows, so the user saw a name
                # they never typed in the one place we control.
                #
                # Falls back to the ASCII field when there is no Unicode one:
                # a profile from another application, or one of ours from
                # before the repair existed.
                from core.icc_text import parse_text_description
                try:
                    end = offset + size if offset + size <= len(data) else len(data)
                    ascii_field, uni = parse_text_description(data[offset:end])
                except Exception:              # noqa: BLE001 — display only
                    n = struct.unpack_from(">I", data, offset + 8)[0]
                    start = offset + 12
                    raw = data[start:start + max(0, n - 1)]
                    return raw.decode("latin-1", errors="replace").strip()
                return (uni or ascii_field).strip()
            if ttype == b"mluc":
                # v4 multiLocalizedUnicode: type(4) reserved(4) num(4) recsize(4)
                num, recsize = struct.unpack_from(">II", data, offset + 8)
                if num >= 1 and recsize >= 12:
                    rec = offset + 16
                    length, str_off = struct.unpack_from(">II", data, rec + 4)
                    s = offset + str_off
                    raw = data[s:s + length]
                    return raw.decode("utf-16-be", errors="replace").strip()
            return ""
    except (struct.error, IndexError):
        return ""
    return ""


def _read_xyz_tag(data: bytes, want: bytes) -> tuple[float, float, float] | None:
    """Best-effort read of an XYZType tag (e.g. ``b'wtpt'``, ``b'bkpt'``).

    Returns the first XYZNumber as a float triple, or ``None`` if the tag is
    absent or unparseable. XYZType layout: type(4) 'XYZ ' · reserved(4) · then
    one or more XYZNumber, each three s15Fixed16 (big-endian /65536)."""
    try:
        count = struct.unpack_from(">I", data, 128)[0]
        for i in range(count):
            base = 132 + i * 12
            if base + 12 > len(data):
                break
            if data[base:base + 4] != want:
                continue
            offset, _size = struct.unpack_from(">II", data, base + 4)
            if offset + 20 > len(data) or data[offset:offset + 4] != b"XYZ ":
                return None
            x, y, z = struct.unpack_from(">3i", data, offset + 8)
            return (x / 65536.0, y / 65536.0, z / 65536.0)
    except (struct.error, IndexError):
        return None
    return None


def read_icc(path: str | Path) -> IccInfo:
    """Parse the ICC header (and 'desc' tag) of ``path``.

    Raises :class:`IccParseError` if the file is too small or lacks the ``acsp``
    profile signature at offset 36.
    """
    p = Path(path)
    data = p.read_bytes()
    if len(data) < 132:
        raise IccParseError("File is too small to be an ICC profile.")
    if data[36:40] != b"acsp":
        raise IccParseError("Missing ICC 'acsp' signature — not an ICC profile.")

    size = struct.unpack_from(">I", data, 0)[0]
    version_major = data[8]
    version_minor = data[9] >> 4   # high nibble = minor version (BCD)
    device_class = _sig(data[12:16])
    color_space = _sig(data[16:20])
    pcs = _sig(data[20:24])

    yr, mo, dy, hh, mm, ss = struct.unpack_from(">6H", data, 24)
    created = ""
    if yr:
        created = f"{yr:04d}-{mo:02d}-{dy:02d} {hh:02d}:{mm:02d}:{ss:02d}"

    platform = _sig(data[40:44])
    flags = struct.unpack_from(">I", data, 44)[0]
    is_embedded = bool(flags & 0x1)
    rendering_intent = struct.unpack_from(">I", data, 64)[0]

    wx, wy, wz = struct.unpack_from(">3i", data, 68)
    white_point = (wx / 65536.0, wy / 65536.0, wz / 65536.0)

    creator = _sig(data[80:84])
    description = _read_desc(data, size)
    media_white = _read_xyz_tag(data, b"wtpt")
    media_black = _read_xyz_tag(data, b"bkpt")

    return IccInfo(
        path=p,
        size=size if size else len(data),
        version_major=version_major,
        version_minor=version_minor,
        device_class=device_class,
        color_space=color_space,
        pcs=pcs,
        rendering_intent=rendering_intent,
        creator=creator,
        platform=platform,
        is_embedded=is_embedded,
        white_point=white_point,
        created=created,
        description=description,
        media_white=media_white,
        media_black=media_black,
    )


def is_v4(path: str | Path) -> bool:
    """True if ``path`` is an ICC v4 (or later) profile — which ArgyllCMS
    cannot read. Returns False on any parse error (let the tool surface the
    real error rather than mislabel an unreadable file as v4)."""
    try:
        return read_icc(path).is_v4
    except (OSError, IccParseError):
        return False
