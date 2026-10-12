"""Research Agent 57 (a57-colprofmodel-b2a): invert COLPROF'S forward model.

Question (D-30, after Agents 53 and 56): does colprof's smoother relative
colorimetric B2A come from its forward model (the rspl fit behind the xfit
shaper curves, Argyll 3.5.0 ``xicc/xfit.c`` and ``rspl/scat.c``) rather
than from its inversion? colprof builds B2A1 by inverting the A2B it has
just written, node by node, with no smoothing of its own
(``profile/profout.c:529-555`` ``out_b2a_clut`` -> ``inv_clut_aux``; the
A2B object it inverts is created from the profile being written,
``profout.c:2287-2317``). So the A2B1 tag of colprof's profile IS colprof's
forward model as its inversion sees it: per-channel input curves, an rspl
sampled on a regular grid, and per-channel output curves.

Step 1 (cheap proof, research only): the engine builds its own A2B as usual,
but the colorimetric B2A1 is inverted from colprof's A2B1, read from a
colprof profile built from the same .ti3 (env ``CHROMIQ_A57_COLPROF_ICC``).
Every clip and black rule of the engine (a29 floor, a51 metric, a56 fade,
neutral axis, pins) runs unchanged on that model. The token acts only for
RGB devices and only on B2A1; the A2B and B2A0/B2A2 keep the engine model.

The table is held as an engine ``ForwardModel``: colprof's input curves are
the model's shaper curves (device -> grid coordinate, exact), and the grid
is re-sampled at ``grid`` nodes per axis from the exact lut16 lookup
(multilinear CLUT, then the output curves), so only the output curves'
curvature inside one fine cell is approximated.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

import numpy as np

from workflow.profile_engine.forward_model import ForwardModel, _interp_weights

A57_TOKEN = "a57-colprofmodel-b2a"
A57_ENV = "CHROMIQ_A57_COLPROF_ICC"


def a57_on(candidates, *, is_additive: bool) -> bool:
    return bool(is_additive) and A57_TOKEN in frozenset(candidates or ())


def colprof_icc_from_env() -> Path | None:
    v = os.environ.get(A57_ENV, "").strip()
    return Path(v) if v else None


def read_tags(path: Path | str) -> tuple[bytes, dict[str, bytes]]:
    """(header+file bytes, {tag signature: tag bytes})."""
    b = Path(path).read_bytes()
    n = struct.unpack(">I", b[128:132])[0]
    tags = {}
    for i in range(n):
        sig, off, size = struct.unpack(">4sII", b[132 + 12 * i:144 + 12 * i])
        tags[sig.decode("latin-1")] = b[off:off + size]
    return b, tags


def lut16_lab_decode(code: np.ndarray) -> np.ndarray:
    """lut16 (mft2) Lab PCS codes 0..65535 -> Lab, the legacy encoding
    (ICC.1 10.10: mft2 keeps 0xFF00 = L* 100 / a* b* 127 in v2 and v4)."""
    c = np.asarray(code, float)
    return np.stack([c[..., 0] / 65280.0 * 100.0,
                     c[..., 1] / 65280.0 * 255.0 - 128.0,
                     c[..., 2] / 65280.0 * 255.0 - 128.0], -1)


def _table(t: np.ndarray, x01: np.ndarray) -> np.ndarray:
    e = len(t)
    return np.interp(np.asarray(x01, float) * (e - 1), np.arange(e),
                     t.astype(float) / 65535.0)


class Lut16Lab:
    """Exact multilinear lookup of an RGB->Lab mft2 tag (Argyll's icclib
    reads lut16 n-linearly)."""

    def __init__(self, blob: bytes) -> None:
        from workflow.profile_engine.v4_prm import parse_mft2
        m = parse_mft2(blob)
        if m["n_out"] != 3:
            raise ValueError("A2B with 3 outputs expected")
        self.n = int(m["n_in"])
        self.grid = int(m["grid"])
        self.in_t = np.asarray(m["in"])
        self.out_t = np.asarray(m["out"])
        self.clut = np.asarray(m["clut"], float) / 65535.0

    def curves(self) -> np.ndarray:
        """Input tables as monotone 0..1 shaper curves (n, entries)."""
        c = self.in_t.astype(float) / 65535.0
        return np.maximum.accumulate(c, axis=1)

    def lookup_shaped(self, u: np.ndarray) -> np.ndarray:
        """Grid coordinate 0..1 (after the input tables) -> Lab."""
        w, cols = _interp_weights(np.asarray(u, float), self.grid, self.n)
        v = (w[:, :, None] * self.clut[cols]).sum(1)
        out = np.stack([_table(self.out_t[c], v[:, c]) for c in range(3)], 1)
        return lut16_lab_decode(out * 65535.0)

    def lookup(self, dev: np.ndarray) -> np.ndarray:
        """Device 0..1 -> Lab, the tag's own lookup."""
        dev = np.asarray(dev, float)
        u = np.stack([_table(self.in_t[c], dev[:, c]) for c in range(self.n)], 1)
        return self.lookup_shaped(u)


def forward_model_from_icc(path: Path | str, *, tag: str = "A2B1",
                           grid: int = 33) -> ForwardModel:
    """colprof's A2B1 as an engine ForwardModel (see the module note)."""
    head, tags = read_tags(path)
    if head[20:24] != b"Lab ":
        raise ValueError(f"{path}: Lab PCS expected, got {head[20:24]!r}")
    blob = tags.get(tag) or tags.get("A2B0")
    if blob is None or blob[:4] != b"mft2":
        raise ValueError(f"{path}: no lut16 {tag}")
    lut = Lut16Lab(blob)
    g = np.linspace(0.0, 1.0, grid)
    u = np.stack(np.meshgrid(*([g] * lut.n), indexing="ij"), -1).reshape(-1, lut.n)
    return ForwardModel(grid=grid, n_channels=lut.n,
                        nodes=lut.lookup_shaped(u), curves=lut.curves())
