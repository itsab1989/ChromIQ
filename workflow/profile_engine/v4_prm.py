"""ICC v4 perceptual and saturation tables referred to the perceptual
reference medium (research agent17-01 item 2, Findings/F-09).

ICC.1:2022 6.3.4.3: "In transforms for the perceptual intent, the black
point of the perceptual reference medium is defined in Table 16" (PCSXYZ
0.003357, 0.003479, 0.002869; PCSLAB L* 3.1373), and "Perceptual transforms
developed to meet ICC specifications prior to version 4.0 frequently use zero
to represent the black point, and thus do not conform to this specification.
Such transforms should be adjusted by scaling the black point as needed. The
white point should remain unchanged and all other values should be mapped
linearly in XYZ."

The engine's v2 file keeps the v2 conventions (perceptual A2B0 is the
colorimetric table; a mapped B2A0 takes the source gamut's black at L* 0),
and until this module the v4 container carried the SAME bytes. A v4 CMM
(lcms: cmsDetectBlackPoint returns the PRM black for any v4 profile in the
perceptual and saturation intents and forces black point compensation)
then hands the B2A0 an L* 3.14 black, and sRGB black printed L* 8.0-8.4
instead of the device's 5.4-5.6 (agent 13, V1).

What the v4 container gets instead (v2 file untouched, byte for byte):

* A2B0 (and A2B2): the colorimetric A2B1 with its output scaled linearly in
  XYZ so the device's own black lands on the PRM black, white fixed (the
  ISO 18619 black point scaling, device black -> PRM black).
* B2A0 / B2A2 that were MAPPED (bytes of their own, zero-black convention):
  re-sampled through the spec's equation inverted, so the PRM black reaches
  the table where it used to receive L* 0.
* B2A0 / B2A2 that alias the colorimetric B2A1: re-sampled through the
  inverse of the A2B0 scaling (PRM black -> device black), so A2B0 and
  B2A0 are inverses of each other as A2B1 and B2A1 are.

Re-sampling evaluates the original lut16 at the transformed PCS value of
every grid node: input tables, trilinear CLUT interpolation, the CLUT value
kept in the table's own output-curve space (output tables unchanged).
"""
from __future__ import annotations

import struct

import numpy as np

from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.ti3_data import lab_to_xyz, xyz_to_lab

# ICC.1:2022 Table 16 and Table 14 (PCSXYZ, Y = 1 scale).
PRM_BLACK = np.array([0.003357, 0.003479, 0.002869])
PCS_WHITE = np.array([0.9642, 1.0, 0.8249])


def scale_black(xyz: np.ndarray, src_black: np.ndarray,
                dst_black: np.ndarray) -> np.ndarray:
    """Linear per-channel XYZ map sending ``src_black`` to ``dst_black`` with
    the PCS white fixed (Y = 1 scale). With ``src_black`` = 0 and
    ``dst_black`` = the PRM black this is ICC.1:2022 6.3.4.3's equation."""
    src = np.asarray(src_black, float)
    dst = np.asarray(dst_black, float)
    return dst + (np.asarray(xyz, float) - src) * (PCS_WHITE - dst) / (
        PCS_WHITE - src)


# ---------------------------------------------------------------------------
# lut16 (mft2) parsing and PCS codes
# ---------------------------------------------------------------------------

def parse_mft2(blob: bytes) -> dict:
    if blob[:4] != b"mft2":
        raise ValueError("not an mft2 tag")
    n_in, n_out, grid = blob[8], blob[9], blob[10]
    e_in, e_out = struct.unpack(">HH", blob[48:52])
    pos = 52
    in_t = np.frombuffer(blob, ">u2", n_in * e_in, pos).reshape(n_in, e_in)
    pos += 2 * n_in * e_in
    clut = np.frombuffer(blob, ">u2", grid ** n_in * n_out, pos).reshape(
        grid ** n_in, n_out)
    pos += 2 * grid ** n_in * n_out
    out_t = np.frombuffer(blob, ">u2", n_out * e_out, pos).reshape(
        n_out, e_out)
    return {"n_in": n_in, "n_out": n_out, "grid": grid, "in": in_t,
            "clut": clut, "out": out_t}


def _pcs_to_xyz(code: np.ndarray, pcs: bytes) -> np.ndarray:
    """lut16 PCS codes (float, 0..65535) -> XYZ (Y = 1 scale)."""
    c = np.asarray(code, float)
    if pcs == b"XYZ ":
        return c / 0x8000
    lab = np.stack([c[:, 0] / 0xFF00 * 100.0,
                    c[:, 1] / 0xFF00 * 255.0 - 128.0,
                    c[:, 2] / 0xFF00 * 255.0 - 128.0], 1)
    return lab_to_xyz(lab) / 100.0


def _xyz_to_pcs(xyz: np.ndarray, pcs: bytes) -> np.ndarray:
    """XYZ (Y = 1 scale) -> lut16 PCS codes (float, clipped to 0..65535)."""
    x = np.asarray(xyz, float)
    if pcs == b"XYZ ":
        c = x * 0x8000
    else:
        lab = xyz_to_lab(x * 100.0)
        c = np.stack([lab[:, 0] / 100.0 * 0xFF00,
                      (lab[:, 1] + 128.0) / 255.0 * 0xFF00,
                      (lab[:, 2] + 128.0) / 255.0 * 0xFF00], 1)
    return np.clip(c, 0.0, 65535.0)


def _table(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    """A lut16 1-D table at codes ``x`` (0..65535), linear interpolation."""
    e = len(t)
    return np.interp(np.asarray(x, float) / 65535.0 * (e - 1),
                     np.arange(e), t.astype(float))


def _table_inverse(t: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The smallest code a monotone non-decreasing table maps to ``y``."""
    tf = t.astype(float)
    top = int(np.argmax(tf >= tf.max()))
    xs = np.arange(top + 1) / (len(t) - 1) * 65535.0
    ys = tf[:top + 1]
    keep = np.concatenate([[True], np.diff(ys) > 0])
    return np.interp(y, ys[keep], xs[keep])


def _trilinear(clut: np.ndarray, grid: int, u: np.ndarray) -> np.ndarray:
    """3-input CLUT (first input slowest) at grid coordinates ``u`` (0..1)."""
    g = np.clip(np.asarray(u, float), 0.0, 1.0) * (grid - 1)
    i0 = np.minimum(np.floor(g).astype(int), grid - 2)
    f = g - i0
    c = clut.astype(float).reshape(grid, grid, grid, -1)
    out = 0.0
    for dx in (0, 1):
        wx = f[:, 0] if dx else 1.0 - f[:, 0]
        for dy in (0, 1):
            wy = f[:, 1] if dy else 1.0 - f[:, 1]
            for dz in (0, 1):
                wz = f[:, 2] if dz else 1.0 - f[:, 2]
                out = out + (wx * wy * wz)[:, None] * c[
                    i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
    return out


# ---------------------------------------------------------------------------
# The two operations
# ---------------------------------------------------------------------------

def a2b_scaled(blob: bytes, pcs: bytes, src_black: np.ndarray,
               dst_black: np.ndarray) -> bytes:
    """An A2B lut16 whose PCS output is :func:`scale_black`-ed. Exact at the
    nodes (the engine writes identity output tables; any other output
    table is folded into the CLUT and replaced by identity)."""
    t = parse_mft2(blob)
    vals = np.stack([_table(t["out"][c], t["clut"][:, c].astype(float))
                     for c in range(t["n_out"])], 1)
    xyz = scale_black(_pcs_to_xyz(vals, pcs), src_black, dst_black)
    new = _xyz_to_pcs(xyz, pcs).round().astype(">u2")
    e_out = t["out"].shape[1]
    return icw.make_mft2(t["n_in"], t["n_out"], t["grid"], new,
                         in_tables=t["in"],
                         out_tables=np.tile(icw._identity_table(e_out),
                                            (t["n_out"], 1)))


def _remap_table(t: np.ndarray, fn) -> np.ndarray:
    """An input table composed with a code -> code map ``fn``."""
    e = len(t)
    codes = np.arange(e) / (e - 1) * 65535.0
    return np.clip(_table(t, np.clip(fn(codes), 0.0, 65535.0)), 0,
                   0xFFFF).round().astype(">u2")


def _l_code_to_y(code):
    lab = np.zeros((len(code), 3))
    lab[:, 0] = np.asarray(code, float) / 0xFF00 * 100.0
    return lab_to_xyz(lab)[:, 1] / 100.0


def _y_to_l_code(y):
    xyz = np.zeros((len(y), 3))
    xyz[:, 1] = np.asarray(y, float) * 100.0
    xyz[:, 0] = xyz[:, 1] * PCS_WHITE[0]
    xyz[:, 2] = xyz[:, 1] * PCS_WHITE[2]
    return xyz_to_lab(xyz)[:, 0] / 100.0 * 0xFF00


def b2a_resampled(blob: bytes, pcs: bytes, src_black: np.ndarray,
                  dst_black: np.ndarray) -> bytes:
    """A B2A lut16 whose input PCS is first :func:`scale_black`-ed from
    ``src_black`` to ``dst_black``.

    The map is per channel in XYZ, so on an XYZ PCS it goes entirely into
    the input tables (exact, CLUT untouched). On a Lab PCS L* depends on Y
    alone, so the L* part goes into the L input table (exact: the neutral
    axis is reproduced without interpolation, which matters because the
    PRM black falls between the first two L grid rows); what is left, the
    small change of a* and b*, is re-sampled at the nodes with L* held on
    its grid row (bilinear in a*, b*)."""
    t = parse_mft2(blob)
    grid = t["grid"]
    if t["n_in"] != 3:
        raise ValueError("B2A with other than 3 inputs")
    src = np.asarray(src_black, float)
    dst = np.asarray(dst_black, float)
    if pcs == b"XYZ ":
        ins = np.stack([_remap_table(
            t["in"][c], lambda x, c=c: scale_black(
                np.tile((x / 0x8000)[:, None], (1, 3)), src, dst)[:, c]
            * 0x8000) for c in range(3)])
        return icw.make_mft2(3, t["n_out"], grid, t["clut"], in_tables=ins,
                             out_tables=t["out"])

    def y_map(y):                                       # Y channel only
        return dst[1] + (y - src[1]) * (PCS_WHITE[1] - dst[1]) / (
            PCS_WHITE[1] - src[1])

    def y_inv(y):
        return src[1] + (y - dst[1]) * (PCS_WHITE[1] - src[1]) / (
            PCS_WHITE[1] - dst[1])

    in_l = _remap_table(t["in"][0],
                        lambda x: _y_to_l_code(y_map(_l_code_to_y(x))))
    axis = np.arange(grid) / (grid - 1) * 65535.0
    node_code = [_table_inverse(t["in"][c], axis) for c in range(3)]
    # The v4 point each node now stands for: L* from the L row's v2 value
    # mapped back, a* and b* the node's own codes.
    l4 = _y_to_l_code(y_inv(_l_code_to_y(node_code[0])))
    mesh4 = np.stack(np.meshgrid(l4, node_code[1], node_code[2],
                                 indexing="ij"), -1).reshape(-1, 3)
    code2 = _xyz_to_pcs(scale_black(_pcs_to_xyz(mesh4, pcs), src, dst), pcs)
    gl = np.repeat(np.arange(grid), grid * grid) / (grid - 1)
    u = np.stack([gl, _table(t["in"][1], code2[:, 1]) / 65535.0,
                  _table(t["in"][2], code2[:, 2]) / 65535.0], 1)
    new = np.clip(_trilinear(t["clut"], grid, u), 0,
                  0xFFFF).round().astype(">u2")
    ins = t["in"].copy()
    ins[0] = in_l
    return icw.make_mft2(3, t["n_out"], grid, new, in_tables=ins,
                         out_tables=t["out"])


def _resolve(luts: dict, name: str) -> str:
    seen = set()
    while isinstance(luts.get(name), str) and name not in seen:
        seen.add(name)
        name = luts[name]
    return name


def v4_luts(luts: dict, pcs: bytes, device_black_lab: np.ndarray) -> dict:
    """The lut set for the v4 container (see the module docstring).
    ``device_black_lab``: media-relative Lab of the device's black (what
    A2B1 gives for the black the B2A1 prints)."""
    bd = lab_to_xyz(np.asarray(device_black_lab, float)[None, :])[0] / 100.0
    out = dict(luts)
    a2b1 = luts[_resolve(luts, "A2B1")]
    out["A2B0"] = a2b_scaled(a2b1, pcs, bd, PRM_BLACK)
    out["A2B2"] = "A2B0"
    made: dict[str, str] = {}
    for tag in ("B2A0", "B2A2"):
        if tag not in luts:
            continue
        src = _resolve(luts, tag)
        if src in made:
            out[tag] = made[src]
            continue
        if src == "B2A1":
            # colorimetric alias: PRM black -> device black
            out[tag] = b2a_resampled(luts["B2A1"], pcs, PRM_BLACK, bd)
        else:
            # mapped, zero-black convention: PRM black -> 0
            out[tag] = b2a_resampled(luts[src], pcs, PRM_BLACK,
                                     np.zeros(3))
        made[src] = tag
    return out
