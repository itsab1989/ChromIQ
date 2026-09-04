"""ICC v2 profile byte writer (``mft2`` LUTs) — the profile engine's P0 layer.

Writes the exact profile shape colprof produces for printer profiles (the
parity contract in issue #122): an Output-class v2 profile, Lab PCS, ``mft2``
A2B0/1/2 + B2A0/1/2 (aliases share tag-table offsets when tables are
identical, exactly colprof's layout), ``gamt`` (ColorSync *requires* it on
output profiles — ``sips --verify`` rejects the file otherwise), ``wtpt`` /
``bkpt``, ``targ`` (embedded CGATS), ``arts`` (chromatic-adaptation matrix)
and the text/description tags.

Everything here is bytes-in/bytes-out and numpy — no I/O besides the optional
``write_profile`` convenience, no Qt, no Argyll.

Verified consumers (issue #122 evidence table, executed against real
binaries): iccdump, icclu, xicclu (≤4 device channels — Argyll's reverse
machinery is compiled for ≤4 inputs), cctiff, ``targen -c``, macOS ColorSync
(``sips --verify``).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core import icc_text

# The v2 "legacy" 16-bit Lab PCS encoding tops out at 0xFF00 for L=100 /
# a,b=+127; the u16 range keeps going to 0xFFFF, so a LUT grid spanning the
# full input range covers L up to 100*0xFFFF/0xFF00. B2A grids must be laid
# out over THIS range, not 0..100 — a 0..100 grid misaligns every node by
# 0.39% of the axis.
LAB16_MAX_L = 100.0 * 0xFFFF / 0xFF00          # 100.390625
LAB16_MIN_AB = -128.0
LAB16_MAX_AB = -128.0 + 255.0 * 0xFFFF / 0xFF00  # 127.99609375

# Bradford cone matrix — the chromatic-adaptation transform colprof records
# in its 'arts' tag (verified against the trusted fixture: identical values).
BRADFORD = np.array([
    [0.8951, 0.2664, -0.1614],
    [-0.7502, 1.7135, 0.0367],
    [0.0389, -0.0685, 1.0296],
])

D50_XYZ = (0.9642, 1.0, 0.8249)


# ---------------------------------------------------------------------------
# Value encodings
# ---------------------------------------------------------------------------

def lab_to_u16(lab: np.ndarray) -> np.ndarray:
    """(N,3) Lab → (N,3) big-endian u16 in the v2 legacy PCS encoding."""
    L = np.clip(lab[:, 0] / 100.0 * 0xFF00, 0, 0xFFFF)
    a = np.clip((lab[:, 1] + 128.0) / 255.0 * 0xFF00, 0, 0xFFFF)
    b = np.clip((lab[:, 2] + 128.0) / 255.0 * 0xFF00, 0, 0xFFFF)
    return np.stack([L, a, b], 1).round().astype(">u2")


def u16_to_lab(u: np.ndarray) -> np.ndarray:
    """Inverse of :func:`lab_to_u16` (used by tests and the B2A round-trip)."""
    u = u.astype(float)
    return np.stack([
        u[:, 0] / 0xFF00 * 100.0,
        u[:, 1] / 0xFF00 * 255.0 - 128.0,
        u[:, 2] / 0xFF00 * 255.0 - 128.0,
    ], 1)


def device_to_u16(dev: np.ndarray) -> np.ndarray:
    """Device fractions 0..1 → big-endian u16 (full range)."""
    return np.clip(dev * 0xFFFF, 0, 0xFFFF).round().astype(">u2")


# The ICC XYZ16 PCS encoding is u1.15: 1.0 → 0x8000, so the u16 range spans
# 0 … 1.99997. XYZ PCS grids (B2A/gamt of an -a x profile) must be laid out
# over this range.
XYZ16_MAX = 0xFFFF / 0x8000            # 1.999969…


def xyz_to_u16(xyz1: np.ndarray) -> np.ndarray:
    """(N,3) XYZ on the 0..1 scale → big-endian u16 (u1.15 PCS encoding)."""
    return np.clip(xyz1 * 0x8000, 0, 0xFFFF).round().astype(">u2")


def u16_to_xyz(u: np.ndarray) -> np.ndarray:
    return u.astype(float) / 0x8000


def xyz_grid_axes(grid: int) -> np.ndarray:
    """The XYZ axis values a ``grid``-point XYZ-PCS CLUT spans (all three
    axes are identical, 0 … :data:`XYZ16_MAX`)."""
    return np.linspace(0.0, XYZ16_MAX, grid)


def lab_grid_axes(grid: int) -> tuple[np.ndarray, np.ndarray]:
    """The Lab values a ``grid``-point B2A/gamt CLUT axis actually spans.

    Returns ``(L_axis, ab_axis)`` — the L axis runs 0..100 (the B2A input
    table maps the legacy L code 0xFF00 onto the last row, see
    :func:`lab_b2a_in_tables`), the a/b axes −128..:data:`LAB16_MAX_AB`
    (legacy-encoding endpoints).
    """
    return (np.linspace(0.0, 100.0, grid),
            np.linspace(LAB16_MIN_AB, LAB16_MAX_AB, grid))


def lab_b2a_in_tables(entries: int) -> np.ndarray:
    """B2A/gamt input tables for a Lab PCS: the L* axis is scaled by
    0xFFFF/0xFF00 so the legacy code for L*=100 (0xFF00) lands on the LAST
    grid row and the codes above it clip there — exactly colprof's B2A
    input curve (measured on its profiles: ratio 1.0039 on L, identity on
    a/b). Without it L*=100 sat 3 % of a cell below the top row and the
    interpolation with the row below sent paper white to RGB ≈ 0.996 (ink
    in the paper white) even with the model's white pinned. a/b stay
    identity: with an odd grid the a=b=0 code is already a node."""
    ident = np.linspace(0.0, 1.0, entries)
    l_tab = np.clip(ident * (0xFFFF / 0xFF00), 0.0, 1.0)
    rows = np.stack([l_tab, ident, ident])
    return np.clip(rows * 0xFFFF, 0, 0xFFFF).round().astype(">u2")


def s15fixed16(v: float) -> int:
    return int(round(v * 0x10000))


# ---------------------------------------------------------------------------
# Tag builders (each returns the complete tag data block, unpadded)
# ---------------------------------------------------------------------------

def make_mft2(n_in: int, n_out: int, grid: int, clut_u16: np.ndarray, *,
              in_tables: np.ndarray | None = None,
              out_tables: np.ndarray | None = None) -> bytes:
    """Build an ``mft2`` (Lut16) tag.

    ``clut_u16``: (grid**n_in, n_out) big-endian u16, first input channel
    varying slowest (C-order of an ``indexing="ij"`` meshgrid — verified
    against icclu on both CMYK and 6CLR).
    ``in_tables``: (n_in, entries) u16 per-channel input curves (identity when
    omitted); ``out_tables`` likewise for the output side.
    """
    if clut_u16.shape != (grid ** n_in, n_out):
        raise ValueError(f"CLUT shape {clut_u16.shape} != ({grid ** n_in}, {n_out})")
    if in_tables is None:
        in_tables = np.tile(_identity_table(256), (n_in, 1))
    if out_tables is None:
        out_tables = np.tile(_identity_table(256), (n_out, 1))
    in_tables = np.ascontiguousarray(in_tables, dtype=">u2")
    out_tables = np.ascontiguousarray(out_tables, dtype=">u2")
    if in_tables.shape[0] != n_in or out_tables.shape[0] != n_out:
        raise ValueError("shaper table channel count mismatch")

    blob = b"mft2" + b"\0" * 4 + bytes([n_in, n_out, grid, 0])
    for r in range(3):                      # 3x3 matrix: identity (Lab PCS)
        for c in range(3):
            blob += struct.pack(">i", 0x10000 if r == c else 0)
    blob += struct.pack(">HH", in_tables.shape[1], out_tables.shape[1])
    blob += in_tables.tobytes()
    blob += np.ascontiguousarray(clut_u16, dtype=">u2").tobytes()
    blob += out_tables.tobytes()
    return blob


def _identity_table(entries: int) -> np.ndarray:
    return np.round(np.linspace(0, 0xFFFF, entries)).astype(">u2")


def curves_to_tables(curves: np.ndarray, entries: int = 2048) -> np.ndarray:
    """Sample monotone 0..1 → 0..1 per-channel curves into u16 shaper tables.

    ``curves``: (n_channels, K) curve samples at K evenly spaced inputs.
    """
    n, k = curves.shape
    xs = np.linspace(0.0, 1.0, entries)
    xp = np.linspace(0.0, 1.0, k)
    out = np.empty((n, entries))
    for c in range(n):
        out[c] = np.interp(xs, xp, curves[c])
    return np.clip(out * 0xFFFF, 0, 0xFFFF).round().astype(">u2")


def make_mluc(text: str) -> bytes:
    """``multiLocalizedUnicodeType`` (ICC v4 metadata) — one en/US record.

    v4 requires desc/cprt (and dmnd/dmdd) as mluc instead of the v2
    textDescription/text types; the string is UTF-16BE per the spec.
    """
    payload = text.encode("utf-16-be")
    return (b"mluc" + b"\0" * 4
            + struct.pack(">II", 1, 12)              # count, record size
            + b"enUS"
            + struct.pack(">II", len(payload), 28)   # length, offset
            + payload)


def make_desc(text: str) -> bytes:
    """``textDescriptionType`` (ICC v2 ``desc``/``dmnd``/``dmdd``).

    An ACCENT IS PART OF THE NAME. The tag carries the same string three
    times — 7-bit ASCII, UTF-16BE and Macintosh ScriptCode — and only the
    first is limited to ASCII, so ``Müller-Prüfdruck`` goes in the Unicode
    field verbatim and the ASCII field gets a transliteration
    (``Mueller-Pruefdruck``) rather than colprof's ``M?ller-Pr?fdruck``.
    See :mod:`core.icc_text` for the measurements behind that.

    Pure-ASCII text is byte-identical to what this wrote before.
    """
    return icc_text.text_description(text)


def make_text(text: str) -> bytes:
    """``textType`` (ICC v2 ``cprt``/``targ``) — 7-bit ASCII, no Unicode field.

    Nothing can carry the accent here, so the best available spelling is a
    transliteration; ASCII text is unchanged.
    """
    return (b"text" + b"\0" * 4
            + icc_text.ascii_fallback(text).encode("ascii", "replace") + b"\0")


def make_xyz(xyz: tuple[float, float, float]) -> bytes:
    return b"XYZ " + b"\0" * 4 + struct.pack(
        ">3i", *(s15fixed16(v) for v in xyz))


def make_sf32(values: np.ndarray) -> bytes:
    flat = np.asarray(values, dtype=float).reshape(-1)
    return (b"sf32" + b"\0" * 4
            + b"".join(struct.pack(">i", s15fixed16(v)) for v in flat))


def make_arts() -> bytes:
    """The chromatic-adaptation tag colprof writes (Bradford matrix)."""
    return make_sf32(BRADFORD)


# ---------------------------------------------------------------------------
# Profile assembly
# ---------------------------------------------------------------------------

_SPACE_SIGS = {1: b"GRAY", 3: b"RGB ", 4: b"CMYK"}


def device_space_sig(n_channels: int, color_rep: str = "") -> bytes:
    """ICC colour-space signature for a device channel count / COLOR_REP."""
    rep = color_rep.split("_")[0].lstrip("i")
    if rep == "CMY":
        return b"CMY "
    if n_channels in _SPACE_SIGS and (n_channels != 3 or rep in ("RGB", "")):
        return _SPACE_SIGS[n_channels]
    if 2 <= n_channels <= 15:
        return b"%X" % n_channels + b"CLR"
    raise ValueError(f"unsupported channel count {n_channels}")


@dataclass
class ProfileSpec:
    """Everything :func:`assemble_profile` needs besides the LUT tags."""

    n_channels: int
    description: str
    color_rep: str = ""
    copyright: str = "Created with ChromIQ"
    manufacturer: str = ""           # → 'dmnd' tag (colprof -A)
    model: str = ""                  # → 'dmdd' tag (colprof -M)
    wtpt: tuple[float, float, float] = D50_XYZ     # media white, abs XYZ /1.0
    bkpt: tuple[float, float, float] | None = None
    targ: str | None = None          # embedded CGATS (.ti3) text; colprof
    # writes the same text as targ + DevD + CIED — mirrored here as aliases
    device_class: bytes = b"prtr"
    pcs: bytes = b"Lab "
    rendering_intent: int = 1        # header default: relative colorimetric
    timestamp: datetime | None = None  # fixed date → byte-reproducible file
    creator: bytes = b"CIQ "
    cmm: bytes = b"none"
    version: tuple[int, int] = (2, 2)
    # (Reflective, Glossy, Positive, Colour) == all-zero attribute bits.
    attributes: int = 0


def assemble_profile(spec: ProfileSpec,
                     luts: dict[str, bytes | str],
                     extra_tags: list[tuple[bytes, bytes]] | None = None,
                     ) -> bytes:
    """Assemble the complete ICC byte stream.

    ``luts`` maps tag names (``"A2B0"``, ``"B2A1"``, ``"gamt"``, …) to either
    tag bytes or the *name of another tag* to alias — aliased tags share one
    data block via identical (offset, size) tag-table entries, exactly
    colprof's shared-table layout.
    """
    v4 = spec.version[0] >= 4
    # v4 metadata is multiLocalizedUnicodeType; v2 keeps the classic
    # textDescription/text types. Everything else in the tag set is
    # version-neutral (lut16Type stays legal in v4, with the legacy PCS
    # encoding preserved by the spec — table bytes identical).
    meta = make_mluc if v4 else make_desc
    tags: list[tuple[bytes, bytes | str]] = [
        (b"desc", meta(spec.description)),
        (b"cprt", make_mluc(spec.copyright) if v4
         else make_text(spec.copyright)),
        (b"wtpt", make_xyz(spec.wtpt)),
    ]
    if spec.manufacturer:
        tags.append((b"dmnd", meta(spec.manufacturer)))
    if spec.model:
        tags.append((b"dmdd", meta(spec.model)))
    if spec.bkpt is not None:
        tags.append((b"bkpt", make_xyz(spec.bkpt)))
    if spec.targ is not None:
        # colprof writes the .ti3 text three times (targ + DevD + CIED,
        # byte-identical — verified on the trusted fixture); aliases give
        # the same tag set without tripling the file size.
        tags.append((b"targ", make_text(spec.targ)))
        tags.append((b"DevD", "targ"))
        tags.append((b"CIED", "targ"))
    for name in ("A2B0", "A2B1", "A2B2", "B2A0", "B2A1", "B2A2", "gamt"):
        if name in luts:
            v = luts[name]
            tags.append((name.encode(), v))
    tags.append((b"arts", make_arts()))
    for sig, data in extra_tags or []:
        tags.append((sig, data))

    hdr_size = 128 + 4 + 12 * len(tags)
    off = hdr_size
    offsets: dict[bytes, tuple[int, int]] = {}
    table = b""
    body = b""
    # First pass places real data blocks; the second resolves aliases, so an
    # alias may appear before its target in the tag list.
    for sig, data in tags:
        if isinstance(data, str):
            continue
        pad = (4 - len(data) % 4) % 4
        offsets[sig] = (off, len(data))
        body += data + b"\0" * pad
        off += len(data) + pad
    for sig, data in tags:
        target = data.encode() if isinstance(data, str) else sig
        if target not in offsets:
            raise ValueError(f"alias target {target!r} not present")
        table += sig + struct.pack(">II", *offsets[target])

    ts = spec.timestamp or datetime.now(timezone.utc)
    header = struct.pack(">I4s", 0, spec.cmm)               # size patched below
    header += bytes([spec.version[0],
                     (spec.version[1] << 4) & 0xF0, 0, 0])   # e.g. 2.2.0
    header += spec.device_class
    header += device_space_sig(spec.n_channels, spec.color_rep)
    header += spec.pcs
    header += struct.pack(">6H", ts.year, ts.month, ts.day,
                          ts.hour, ts.minute, ts.second)
    header += b"acsp" + b"APPL" + b"\0" * 4                  # sig, platform, flags
    header += b"\0" * 4 + b"\0" * 4                          # manufacturer, model
    header += struct.pack(">Q", spec.attributes)
    header += struct.pack(">I", spec.rendering_intent)
    header += struct.pack(">3i", *(s15fixed16(v) for v in D50_XYZ))
    header += spec.creator + b"\0" * 44
    assert len(header) == 128, len(header)

    icc = header + struct.pack(">I", len(tags)) + table + body
    icc = struct.pack(">I", len(icc)) + icc[4:]
    if v4:
        # v4 profile ID: MD5 over the profile with the flags, rendering
        # intent and ID fields zeroed (ICC.1 clause 7.2.18).
        import hashlib
        z = bytearray(icc)
        z[44:48] = b"\0" * 4
        z[64:68] = b"\0" * 4
        z[84:100] = b"\0" * 16
        icc = icc[:84] + hashlib.md5(bytes(z)).digest() + icc[100:]
    return icc


def write_profile(path: Path | str, spec: ProfileSpec,
                  luts: dict[str, bytes | str],
                  extra_tags: list[tuple[bytes, bytes]] | None = None) -> Path:
    """Assemble and write; returns the path."""
    p = Path(path)
    p.write_bytes(assemble_profile(spec, luts, extra_tags))
    return p
