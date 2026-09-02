"""Convert an ICC **v4** RGB profile to an equivalent **v2** profile.

ArgyllCMS (and therefore `collink`) is v2-only — it prints *"ICC V4 not
supported!"* and aborts on a v4 input. The vast majority of v4 profiles a user
would pick as a *source* for a device-link are ordinary **matrix + tone-curve
RGB** profiles (sRGB, AdobeRGB, ProPhoto/ROMM, Display P3, Rec.709/2020, …). For
that class the v2 and v4 tag *types* are identical, so we can transcode exactly:
copy the colorant (`rXYZ`/`gXYZ`/`bXYZ`), white-point (`wtpt`) and chromatic-
adaptation (`chad`) tags verbatim, re-sample any parametric tone curves (`para`)
into plain `curv` tables (v2-safe), and wrap them in a fresh v2 container.

Profiles that aren't matrix/TRC RGB (LUT-based `mAB`/`mBA`, CMYK, …) raise
:class:`NotConvertible`; the caller falls back to lcms2 or an honest message.

The output is written to a tempfile the caller is expected to delete after use —
it's a throwaway intermediate (the device-link bakes in the source colorimetry).
"""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

from core import icc_text
from core.logger import get_logger
from workflow.icc_info import read_icc

log = get_logger(__name__)

# D50 PCS illuminant as s15Fixed16 (the value every v2/v4 profile header carries
# at offset 68): X=0.9642, Y=1.0, Z=0.8249.
_D50_S15 = (0x0000F6D6, 0x00010000, 0x0000D32D)

_CURV_SAMPLES = 1024   # points used when flattening a 'para' curve to 'curv'


class NotConvertible(ValueError):
    """The profile isn't a matrix/TRC RGB profile we can transcode to v2."""


def needs_v2_conversion(path: str | Path) -> bool:
    """True if ``path`` is a v4 profile (and so unusable by Argyll as-is)."""
    return read_icc(path).is_v4


def _tag_table(data: bytes) -> dict[bytes, tuple[int, int]]:
    """Return ``{signature: (offset, size)}`` for every tag in the profile."""
    count = struct.unpack_from(">I", data, 128)[0]
    out: dict[bytes, tuple[int, int]] = {}
    for i in range(count):
        base = 132 + i * 12
        if base + 12 > len(data):
            break
        sig = data[base:base + 4]
        offset, size = struct.unpack_from(">II", data, base + 4)
        out[sig] = (offset, size)
    return out


def _eval_para(func: int, p: list[float], x: float) -> float:
    """Evaluate an ICC parametricCurveType function at ``x`` in [0,1]."""
    g = p[0]
    try:
        if func == 0:
            return x ** g
        if func == 1:  # g, a, b
            a, b = p[1], p[2]
            return (a * x + b) ** g if (a * x + b) >= 0 and x >= -b / a else 0.0
        if func == 2:  # g, a, b, c
            a, b, c = p[1], p[2], p[3]
            return ((a * x + b) ** g + c) if x >= -b / a else c
        if func == 3:  # g, a, b, c, d
            a, b, c, d = p[1], p[2], p[3], p[4]
            return (a * x + b) ** g if x >= d else c * x
        if func == 4:  # g, a, b, c, d, e, f
            a, b, c, d, e, f = p[1], p[2], p[3], p[4], p[5], p[6]
            return ((a * x + b) ** g + e) if x >= d else (c * x + f)
    except (ZeroDivisionError, ValueError):
        return 0.0
    raise NotConvertible(f"Unsupported parametric curve function type {func}")


def _curv_tag_bytes(data: bytes, offset: int, size: int) -> bytes:
    """Return a v2-safe 'curv' tag for the curve at ``offset``.

    A 'curv' tag is copied verbatim. A 'para' tag is evaluated at
    ``_CURV_SAMPLES`` points and emitted as a 'curv' LUT, which every CMM
    (including Argyll) accepts.
    """
    ttype = data[offset:offset + 4]
    if ttype == b"curv":
        return data[offset:offset + size]
    if ttype == b"para":
        func = struct.unpack_from(">H", data, offset + 8)[0]
        nparam = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}.get(func)
        if nparam is None:
            raise NotConvertible(f"Unsupported parametric curve function {func}")
        params = [
            struct.unpack_from(">i", data, offset + 12 + 4 * i)[0] / 65536.0
            for i in range(nparam)
        ]
        n = _CURV_SAMPLES
        body = struct.pack(">4sII", b"curv", 0, n)
        for i in range(n):
            y = _eval_para(func, params, i / (n - 1))
            v = max(0, min(65535, round(y * 65535)))
            body += struct.pack(">H", v)
        return body
    raise NotConvertible(f"Tone curve has unsupported type {ttype!r}")


def _text_desc_tag(text: str) -> bytes:
    """Build a v2 textDescriptionType tag for ``text``.

    THE FOURTH WRITER OF THIS TAG, and it used to be the one that still threw
    the accents away: `encode("ascii", "replace")` with an empty Unicode
    field, so converting a v4 profile called Müller-Prüfdruck down to v2
    produced M?ller-Pr?fdruck — the same blemish the build path had just been
    taught not to make, re-made by our own Convert tool.
    """
    return icc_text.text_description(text)


def _text_tag(text: str) -> bytes:
    """Build a v2 textType tag (used for 'cprt').

    A v2 `text` tag is ASCII by definition and has no Unicode field to fall
    back on, so an accent cannot be stored here at all. It is transliterated
    rather than replaced: `(c) 2026 Mueller` says what the line means and
    `? 2026 M?ller` does not.
    """
    return (struct.pack(">4sI", b"text", 0)
            + icc_text.ascii_fallback(text).encode("ascii", "replace") + b"\x00")


def to_v2(src: str | Path) -> Path:
    """Transcode a v4 matrix/TRC RGB profile to a v2 profile in a tempfile.

    Raises :class:`NotConvertible` if the profile isn't a matrix/TRC RGB profile.
    The returned path is a throwaway the caller should delete after use.
    """
    src = Path(src)
    data = src.read_bytes()
    info = read_icc(src)

    if info.color_space.strip() != "RGB":
        raise NotConvertible("Only RGB profiles can be transcoded.")

    tags = _tag_table(data)
    required = (b"rXYZ", b"gXYZ", b"bXYZ", b"rTRC", b"gTRC", b"bTRC", b"wtpt")
    if not all(sig in tags for sig in required):
        raise NotConvertible(
            "Profile is not a matrix + tone-curve RGB profile (likely LUT-based)."
        )

    # Collect output tags as {sig: tag-data-bytes}. XYZ and chad tags are
    # type-identical between v2/v4, so copy verbatim; TRC curves are normalised
    # to 'curv'; desc/cprt are synthesised as v2 text tags.
    out_tags: dict[bytes, bytes] = {}
    for sig in (b"rXYZ", b"gXYZ", b"bXYZ", b"wtpt", b"bkpt", b"chad"):
        if sig in tags:
            off, size = tags[sig]
            out_tags[sig] = data[off:off + size]
    for sig in (b"rTRC", b"gTRC", b"bTRC"):
        off, size = tags[sig]
        out_tags[sig] = _curv_tag_bytes(data, off, size)

    desc = (info.description or src.stem) + " (v2)"
    out_tags[b"desc"] = _text_desc_tag(desc)
    out_tags[b"cprt"] = _text_tag("Converted to ICC v2 by ChromIQ")

    blob = _assemble_v2(out_tags)
    fd, tmp = tempfile.mkstemp(suffix=".icc", prefix="chromiq-v2-")
    Path(tmp).write_bytes(blob)
    import os
    os.close(fd)
    log.info("Transcoded v4→v2: %s → %s (%d bytes)", src.name, tmp, len(blob))
    return Path(tmp)


def _assemble_v2(out_tags: dict[bytes, bytes]) -> bytes:
    """Assemble a v2 RGB display profile from prepared tag-data blobs."""
    # 128-byte header.
    header = bytearray(128)
    struct.pack_into(">I", header, 4, 0)                 # CMM
    struct.pack_into(">I", header, 8, 0x02400000)        # version 2.4.0
    header[12:16] = b"mntr"                               # device class
    header[16:20] = b"RGB "                               # data colour space
    header[20:24] = b"XYZ "                               # PCS
    header[36:40] = b"acsp"                               # signature
    struct.pack_into(">3I", header, 68, *_D50_S15)        # PCS illuminant = D50
    # intent (64), flags (44), platform (40) etc. left zero — valid defaults.

    # Tag table + data (each tag 4-byte aligned).
    sigs = list(out_tags.keys())
    table_size = 4 + len(sigs) * 12
    data_start = 128 + table_size
    table = bytearray(struct.pack(">I", len(sigs)))
    body = bytearray()
    offset = data_start
    for sig in sigs:
        tag = out_tags[sig]
        pad = (-len(tag)) % 4
        table += struct.pack(">4sII", sig, offset, len(tag))
        body += tag + b"\x00" * pad
        offset += len(tag) + pad

    blob = bytearray(header) + table + body
    struct.pack_into(">I", blob, 0, len(blob))            # profile size
    return bytes(blob)
