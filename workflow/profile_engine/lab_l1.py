"""C-L1 (research token ``a24-l1``, Agent 24): the A2B L* output encoding ColorSync reads right.

ICC v2 legacy Lab in a lut16 (``mft2``) stores L* 100 as 0xFF00. littleCMS, Argyll and the ICC
reference implementation (iccDEV) read it that way; macOS ColorSync reads a lut16 A2B's L* about
0.39 % low (soft proof and display: paper white 0.22 dE00, Validation/d01-challenge.md). The
same meaning can be written so that ColorSync reads it right too: the CLUT keeps L* on the full
0..0xFFFF scale (x 65535/65280) and the L output table maps 0..0xFFFF back onto 0..0xFF00. Under
the specification the table means exactly what it meant before (to the rounding of one CLUT code,
0.0015 L*); a* and b*, the input tables and every B2A table are untouched.

A tag whose CLUT holds any L* above 100 (code above 0xFF00) is left as it is: the rescaled CLUT
could not hold it, and a spec CMM must never read a different colour.
"""
from __future__ import annotations

import struct

import numpy as np

_K = 65535.0 / 65280.0


def encode_a2b_l1(blob: bytes) -> bytes:
    """Return the C-L1 form of one Lab-output ``mft2`` A2B tag (or the tag unchanged)."""
    if blob[:4] != b"mft2":
        return blob
    n_in, n_out, grid = blob[8], blob[9], blob[10]
    if n_out != 3:
        return blob
    n_it, n_ot = struct.unpack(">HH", blob[48:52])
    o_clut = 52 + 2 * n_in * n_it
    n_clut = grid ** n_in * n_out
    o_out = o_clut + 2 * n_clut
    clut = np.frombuffer(blob, ">u2", n_clut, o_clut).reshape(-1, n_out)
    if int(clut[:, 0].max()) > 0xFF00:
        return blob
    out = np.frombuffer(blob, ">u2", n_out * n_ot, o_out).reshape(n_out, n_ot)
    clut = clut.astype(np.int64)
    clut[:, 0] = np.minimum(np.round(clut[:, 0] * _K), 0xFFFF)
    x = np.linspace(0.0, 65535.0, n_ot)
    out_l = np.interp(x / _K, x, out[0].astype(float))
    new_out = out.astype(np.int64)
    new_out[0] = np.clip(np.round(out_l), 0, 0xFFFF)
    return (blob[:o_clut] + clut.astype(">u2").tobytes()
            + new_out.astype(">u2").tobytes() + blob[o_out + 2 * n_out * n_ot:])


def apply_l1(luts: dict) -> dict:
    """C-L1 on every A2B tag that holds its own bytes (aliases follow their target)."""
    return {k: (encode_a2b_l1(v) if k.startswith("A2B") and isinstance(v, bytes) else v)
            for k, v in luts.items()}
