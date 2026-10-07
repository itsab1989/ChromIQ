"""The total ink limit, held by the interpolated B2A table (Agent 40).

An ink-device B2A table stores *shaped* device values in its CLUT and maps
them to device values through per-channel output tables (the inverse of the
A2B input curves). Every node respects the limit (the inversion projects
onto it), but a CMM interpolates the shaped values and only then applies the
output tables. Where an output table is concave, the device value at a point
between nodes lies ABOVE the chord between the node values, so the sum of
the inks can exceed the limit inside a cell whose corners sit on it.
Measured on research-integration-5: up to 306.7 % between nodes for a 300 %
limit (R-CMYK-default-i1Pro B2A1; 1.2 % of the battery's samples above
301 %).

colprof's contract (xicc/xlut.c ``icxLimitD``/``icxLuLut_inv_clut``) is that
the inverse never returns a NODE over the limit; nothing guards the
interpolation, and colprof's own tables overshoot between nodes too
(int-5 battery: X3m B2A1 268.7 % for 260 %). This guard is stricter: the
nodes AND every point a CMM can interpolate hold the limit.

:func:`guard_mft2` works on the finished lut16 bytes (after every pin, the
gamut clip and the v4 PRM resampling, so nothing later can undo it), with
the exact quantised CLUT and output tables a CMM reads. It finds every cell
in which some trilinear or tetrahedral interpolation point exceeds the
limit and lowers only the corners of those cells that are above the
cell's safe cap (Euclidean projection onto the TAC face, as the inversion
itself does), iterating until no cell exceeds (re-checking only the cells
whose corners moved). Nodes in every other cell are returned byte for
byte; the black corner is protected unless it is itself over the limit.
"""
from __future__ import annotations

import struct

import numpy as np

# offsets of a cell's 8 corners, bit 2 = first input (slowest), bit 0 = last
_CORNERS = np.array([[(b >> 2) & 1, (b >> 1) & 1, b & 1] for b in range(8)])


def _sub_points(m: int) -> np.ndarray:
    a = np.linspace(0.0, 1.0, m + 1)
    return np.stack(np.meshgrid(a, a, a, indexing="ij"), -1).reshape(-1, 3)


def _trilinear_weights(u: np.ndarray) -> np.ndarray:
    w = np.ones((len(u), 8))
    for b in range(8):
        for ax in range(3):
            w[:, b] *= u[:, ax] if _CORNERS[b, ax] else 1.0 - u[:, ax]
    return w


def _tetra_weights(u: np.ndarray) -> np.ndarray:
    """Kuhn (main-diagonal) tetrahedral interpolation, as lcms2 and Argyll's
    simplex lookup do: walk from corner 0 to corner 7 along the axes in
    descending order of the fractional coordinate."""
    w = np.zeros((len(u), 8))
    order = np.argsort(-u, axis=1, kind="stable")
    us = np.take_along_axis(u, order, 1)
    idx = np.zeros(len(u), int)
    w[np.arange(len(u)), 0] += 1.0 - us[:, 0]
    for s in range(3):
        idx = idx | (1 << (2 - order[:, s]))
        nxt = us[:, s + 1] if s < 2 else np.zeros(len(u))
        w[np.arange(len(u)), idx] += us[:, s] - nxt
    return w


_M = 8          # coarse pass: 9^3 points per cell, both interpolations
_U = _sub_points(_M)
_P = len(_U)
_W = np.vstack([_trilinear_weights(_U), _tetra_weights(_U)])
_LOCAL = _sub_points(4) * 2.0 - 1.0     # 5^3 offsets in [-1, 1]^3
# refinement: around the 2 best coarse points of each interpolation, boxes
# of half-width 1/8, then 1/32, then 1/128 of the cell. The output tables
# are piecewise linear with kinks (slopes up to 5 on the K channel), so the
# worst point can sit between coarse samples (i1Pro B2A1: 306.6 % found at
# 33^3, missed by 0.4 % at 9^3 alone).
_STEPS = (1.0 / 8, 1.0 / 32, 1.0 / 128)


def _weights(u: np.ndarray, tetra: bool) -> np.ndarray:
    return _tetra_weights(u) if tetra else _trilinear_weights(u)


def _out(tables: np.ndarray, code: np.ndarray) -> np.ndarray:
    """Output tables (n, E) u16 at CLUT codes (..., n) 0..65535 -> device
    fractions, linear interpolation as a CMM does."""
    e = tables.shape[1]
    x = np.asarray(code, float) / 65535.0 * (e - 1)
    res = np.empty(x.shape)
    grid = np.arange(e)
    for c in range(tables.shape[0]):
        res[..., c] = np.interp(x[..., c], grid, tables[c].astype(float))
    return res / 65535.0


def _code_values(table: np.ndarray) -> np.ndarray:
    """The output (fraction) of every one of the 65536 CLUT codes."""
    e = len(table)
    tf = table.astype(float) / 65535.0
    codes = np.arange(65536)
    return np.interp(codes / 65535.0 * (e - 1), np.arange(e), tf)


def _out_inverse_floor(table: np.ndarray, y: np.ndarray,
                       vals: np.ndarray | None = None) -> np.ndarray:
    """The largest integer CLUT code whose output is <= ``y`` (fractions);
    the table is monotone non-decreasing."""
    vals = _code_values(table) if vals is None else vals
    k = np.searchsorted(vals, np.asarray(y, float) + 1e-12, side="right") - 1
    return np.clip(k, 0, 65535)


def _project_rows(d: np.ndarray, caps: np.ndarray) -> np.ndarray:
    """``b2a.project_tac`` with one limit per row (same arithmetic, row by
    row, so the result is the same to the bit)."""
    d = d.copy()
    caps = np.asarray(caps, float)
    over = d.sum(1) > caps
    if not over.any():
        return d
    sub = np.clip(d[over], 0.0, None)
    u = np.sort(sub, axis=1)[:, ::-1]
    css = np.cumsum(u, axis=1) - caps[over][:, None]
    ks = np.arange(1, sub.shape[1] + 1)[None, :]
    rho = (u - css / ks > 0).sum(1)
    theta = css[np.arange(len(sub)), rho - 1] / rho
    d[over] = np.maximum(sub - theta[:, None], 0.0)
    return d


def _cells(grid: int) -> np.ndarray:
    """(cells, 8) node indices of every cell's corners."""
    g = np.arange(grid - 1)
    base = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    pos = base[:, None, :] + _CORNERS[None]
    return (pos[..., 0] * grid + pos[..., 1]) * grid + pos[..., 2]


def _tac_at(code_cells: np.ndarray, out_tables: np.ndarray,
            w: np.ndarray) -> np.ndarray:
    """(c, p, 8) weights on (c, 8, n) corner codes -> (c, p) total ink."""
    pts = np.einsum("cpk,ckn->cpn", w, code_cells)
    return _out(out_tables, pts).sum(2)


def cell_excess(clut: np.ndarray, out_tables: np.ndarray, grid: int,
                limit: float, cells: np.ndarray | None = None):
    """Per cell: the largest interpolated total ink (trilinear or
    tetrahedral, whichever is worse) minus ``limit``, and the corner weights
    of the point where it occurs. Only cells whose upper bound can exceed
    the limit are searched; the others get -inf and zero weights."""
    cells = _cells(grid) if cells is None else cells
    code = clut.astype(float)
    top = _out(out_tables, code[cells].max(1)).sum(1)       # upper bound
    exc = np.full(len(cells), -np.inf)
    wmax = np.zeros((len(cells), 8))
    cand = np.flatnonzero(top > limit)
    for lo in range(0, len(cand), 64):
        sel = cand[lo:lo + 64]
        cc = code[cells[sel]]
        c = len(sel)
        coarse = np.einsum("pk,ckn->cpn", _W, cc)
        tac = _out(out_tables, coarse).sum(2)
        best_v = np.full(c, -np.inf)
        best_w = np.zeros((c, 8))
        for scheme, tetra in ((0, False), (1, True)):
            part = tac[:, scheme * _P:(scheme + 1) * _P]
            top2 = np.argsort(-part, axis=1)[:, :2]
            centre = _U[top2]                               # (c, 2, 3)
            for h in _STEPS:
                u = np.clip(centre[:, :, None, :] + h * _LOCAL[None, None],
                            0.0, 1.0)                       # (c, 2, q, 3)
                q = u.shape[2]
                w = _weights(u.reshape(-1, 3), tetra).reshape(c, 2 * q, 8)
                v = _tac_at(cc, out_tables, w).reshape(c, 2, q)
                arg = v.argmax(2)                           # (c, 2)
                centre = np.take_along_axis(
                    u, arg[:, :, None, None], 2)[:, :, 0, :]
                vbest = np.take_along_axis(v, arg[:, :, None], 2)[:, :, 0]
            k = vbest.argmax(1)
            v1 = vbest[np.arange(c), k]
            u1 = centre[np.arange(c), k]
            # the coarse samples themselves (a refinement never loses them)
            pc = part.argmax(1)
            vc = part[np.arange(c), pc]
            use_c = vc > v1
            v1 = np.where(use_c, vc, v1)
            u1 = np.where(use_c[:, None], _U[pc], u1)
            better = v1 > best_v
            best_v = np.where(better, v1, best_v)
            best_w = np.where(better[:, None], _weights(u1, tetra), best_w)
        exc[sel] = best_v - limit
        wmax[sel] = best_w
    return exc, wmax


def guard_clut(clut: np.ndarray, out_tables: np.ndarray, grid: int,
               limit: float, *, tol: float = 1e-4, margin: float = 2e-4,
               max_iter: int = 400, relax_at: int = 40, protect=()):
    """Return (new u16 CLUT, changed node indices). ``limit`` is a fraction
    (3.0 = 300 %). In every cell whose interpolated ink exceeds
    ``limit + tol`` by ``e``, the corners that carry the worst point
    (weight > 2 %) and hold more than ``limit - e - margin`` are brought
    down to it; when none does (the excess is the output tables' concavity
    alone), those corners lose ``e + margin``. Ink is taken off by the
    Euclidean projection onto the lower TAC face, as the inversion does.
    Repeated until no cell exceeds. Nodes are never raised, nodes outside
    such cells never move, and ``protect`` (the black corner) moves only if
    the cell cannot be held without it."""
    clut = np.array(clut, dtype=np.int64)
    n = clut.shape[1]
    cells = _cells(grid)
    keep = np.zeros(len(clut), bool)
    keep[list(protect)] = True
    # a protected node that is itself over the limit is not protectable
    keep &= _out(out_tables, clut).sum(1) <= limit + tol
    vals = [_code_values(out_tables[c]) for c in range(n)]
    # node -> the cells it is a corner of (to re-check only those)
    owner = np.repeat(np.arange(len(cells)), 8)
    order = np.argsort(cells.ravel(), kind="stable")
    starts = np.searchsorted(cells.ravel()[order], np.arange(len(clut) + 1))
    exc, wmax = cell_excess(clut, out_tables, grid, limit, cells)
    changed: set[int] = set()
    for it in range(max_iter):
        bad = np.flatnonzero(exc > tol)
        if not len(bad):
            break
        tac_now = _out(out_tables, clut).sum(1)
        cap = np.full(len(clut), np.inf)
        for b in bad:
            corners = cells[b]
            hit = corners[(wmax[b] > 0.02) & ~keep[corners]]
            if not len(hit):
                hit = corners[~keep[corners]]
                if not len(hit) or it >= relax_at:
                    hit = corners           # last resort: the black moves
            target = limit - exc[b] - margin
            above = hit[tac_now[hit] > target]
            if len(above):
                np.minimum.at(cap, above, target)
            else:
                np.minimum.at(cap, hit, tac_now[hit] - exc[b] - margin)
        nodes = np.flatnonzero(np.isfinite(cap))
        dev = _out(out_tables, clut[nodes])
        new = _project_rows(dev, np.maximum(cap[nodes], 0.0))
        before = clut[nodes].copy()
        for c in range(n):
            code = _out_inverse_floor(out_tables[c], new[:, c], vals[c])
            clut[nodes, c] = np.minimum(clut[nodes, c], code)
        changed.update(int(x) for x in nodes)
        moved = nodes[(clut[nodes] != before).any(1)]
        # only cells with a moved corner can have changed
        touched = np.unique(np.concatenate(
            [owner[order[starts[k]:starts[k + 1]]] for k in moved]
            or [np.zeros(0, int)]))
        if len(touched):
            e2, w2 = cell_excess(clut, out_tables, grid, limit, cells[touched])
            exc[touched], wmax[touched] = e2, w2
    else:
        # Not reached on the battery (the slowest table, the 7-ink FOGRA55
        # B2A0, needs 81-200 rounds): a build must not fail here, so any
        # remaining cell is held by its upper bound (the sum of each
        # channel's largest corner ink), which no interpolation can exceed.
        for _ in range(2000):
            bad = np.flatnonzero(exc > tol)
            if not len(bad):
                break
            code = clut.astype(float)
            top = _out(out_tables, code[cells[bad]].max(1)).sum(1)
            tac_now = _out(out_tables, clut).sum(1)
            cap = np.full(len(clut), np.inf)
            np.minimum.at(cap, cells[bad].ravel(),
                          np.repeat(top - limit + margin, 8) * -1.0
                          + tac_now[cells[bad].ravel()])
            nodes = np.flatnonzero(np.isfinite(cap))
            new = _project_rows(_out(out_tables, clut[nodes]),
                                np.maximum(cap[nodes], 0.0))
            for c in range(n):
                code_c = _out_inverse_floor(out_tables[c], new[:, c], vals[c])
                clut[nodes, c] = np.minimum(clut[nodes, c], code_c)
            changed.update(int(x) for x in nodes)
            exc[bad], wmax[bad] = cell_excess(clut, out_tables, grid, limit,
                                              cells[bad])
    return clut.astype(">u2"), np.array(sorted(changed), int)


def guard_mft2(blob: bytes, limit: float, *,
               protect=()) -> tuple[bytes, np.ndarray]:
    """A B2A lut16 tag whose interpolated total ink stays within ``limit``
    (fraction). Returns (new tag bytes, changed node indices); unchanged
    tables come back as the very same bytes."""
    if blob[:4] != b"mft2":
        raise ValueError("not an mft2 tag")
    n_in, n_out, grid = blob[8], blob[9], blob[10]
    if n_in != 3:
        raise ValueError("B2A with other than 3 inputs")
    e_in, e_out = struct.unpack(">HH", blob[48:52])
    pos = 52 + 2 * n_in * e_in
    size = grid ** 3 * n_out
    clut = np.frombuffer(blob, ">u2", size, pos).reshape(grid ** 3, n_out)
    out_t = np.frombuffer(blob, ">u2", n_out * e_out,
                          pos + 2 * size).reshape(n_out, e_out)
    new, changed = guard_clut(clut, out_t, grid, limit, protect=protect)
    if not len(changed):
        return blob, changed
    return (blob[:pos] + np.ascontiguousarray(new, ">u2").tobytes()
            + blob[pos + 2 * size:]), changed


def guard_luts(luts: dict, limit_pct: float, *, log=None,
               protect=()) -> dict:
    """Every B2A tag of a lut dict (bytes or an alias name) guarded; the
    aliases stay aliases. ``limit_pct`` in percent; ``protect``: CLUT node
    indices (the black corner) that move only as a last resort."""
    out = dict(luts)
    for tag in ("B2A0", "B2A1", "B2A2"):
        v = luts.get(tag)
        if isinstance(v, (bytes, bytearray)):
            out[tag], changed = guard_mft2(bytes(v), limit_pct / 100.0,
                                           protect=protect)
            if log is not None and len(changed):
                log(f"{tag}: {len(changed)} nodes lowered to hold the "
                    f"{limit_pct:.0f}% ink limit between nodes")
    return out
