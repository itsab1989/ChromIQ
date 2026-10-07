"""Agent 40 (2026-10-07): research token ``a40-inklimit``.

A Maximum accuracy B2A table respected the total ink limit at every node,
but a CMM interpolates the SHAPED CLUT values and applies the output
tables afterwards; where an output table is concave, the ink between two
nodes on the limit lies above it (R-CMYK-default-i1Pro B2A1: 306.6 % for a
300 % limit). ``workflow/profile_engine/tac_guard.py`` lowers only the
corners of the cells that exceed, on the final bytes (Findings
agent40-01-inklimit.md).

No file IO here apart from the slow build, which writes binary .icc files
and reads them back as bytes (the encoding rule of
tests/test_encoding_is_named.py has nothing to check: no text is read or
written).
"""
from __future__ import annotations

import struct

import numpy as np
import pytest

from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine import tac_guard as tg
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

TOKEN = "a40-inklimit"


def test_the_token_is_known_and_opt_in():
    assert TOKEN in ENGINE_CANDIDATE_TOKENS
    assert "no-" + TOKEN in ENGINE_CANDIDATE_TOKENS
    assert TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert TOKEN in accurate_candidates({TOKEN})
    assert TOKEN not in accurate_candidates({TOKEN, "no-" + TOKEN})


def test_both_interpolations_are_partitions_of_unity_and_exact_on_planes():
    rng = np.random.default_rng(0)
    u = rng.random((500, 3))
    corners = tg._CORNERS.astype(float)
    plane = corners @ np.array([0.3, -1.2, 2.0]) + 0.7
    for w in (tg._trilinear_weights(u), tg._tetra_weights(u)):
        assert (w >= -1e-12).all()
        assert np.allclose(w.sum(1), 1.0)
        # an affine function is reproduced exactly by either scheme
        assert np.allclose(w @ plane, u @ np.array([0.3, -1.2, 2.0]) + 0.7)
    # tetrahedral: at most 4 corners, always including 0 and 7
    wt = tg._tetra_weights(u)
    assert ((wt > 1e-12).sum(1) <= 4).all()


def test_the_row_projection_is_project_tac_to_the_bit():
    from workflow.profile_engine.b2a import project_tac
    rng = np.random.default_rng(3)
    d = rng.random((400, 6)) * 1.2 - 0.05
    caps = rng.random(400) * 4.0
    got = tg._project_rows(d, caps)
    want = np.vstack([project_tac(d[i:i + 1], float(caps[i]))
                      for i in range(len(d))])
    assert np.array_equal(got, want)


def _concave_tables(n: int, entries: int = 1024) -> np.ndarray:
    """Output tables y = x ** 0.5 (concave): interpolated ink lies above
    the chord between nodes."""
    x = np.linspace(0.0, 1.0, entries)
    return np.tile(np.round(np.sqrt(x) * 0xFFFF).astype(">u2"), (n, 1))


def _table_with_limit(n: int, grid: int, limit: float, seed: int = 1):
    """A B2A-like CLUT (shaped codes) whose nodes all hold ``limit`` but
    vary strongly from node to node near it."""
    rng = np.random.default_rng(seed)
    dev = rng.random((grid ** 3, n)) ** 0.3          # ink-heavy nodes
    from workflow.profile_engine.b2a import project_tac
    dev = project_tac(dev, limit)
    # the two lightest L rows carry little ink: their cells hold any limit
    dev[: 2 * grid * grid] *= 0.3
    shaped = dev ** 2                                # inverse of sqrt
    return np.clip(np.round(shaped * 0xFFFF), 0, 0xFFFF).astype(">u2")


def _dense_max(clut, tables, grid, limit, m=12):
    u = tg._sub_points(m)
    w = np.vstack([tg._trilinear_weights(u), tg._tetra_weights(u)])
    cells = tg._cells(grid)
    code = clut.astype(float)
    pts = np.einsum("pk,ckn->cpn", w, code[cells])
    return tg._out(tables, pts).sum(2).max()


@pytest.mark.parametrize("n", [4, 6])
def test_the_guard_holds_the_limit_between_nodes(n):
    grid, limit = 5, 2.6 if n == 4 else 3.4
    tables = _concave_tables(n)
    clut = _table_with_limit(n, grid, limit)
    nodes = tg._out(tables, clut.astype(float)).sum(1)
    assert nodes.max() <= limit + 1e-4                 # every node holds it
    assert _dense_max(clut, tables, grid, limit) > limit + 0.01   # ...not between
    new, changed = tg.guard_clut(clut, tables, grid, limit)
    assert _dense_max(new, tables, grid, limit) <= limit + 1e-4
    # nodes only ever lose ink, and only the changed ones move
    assert (new.astype(int) <= clut.astype(int)).all()
    moved = np.flatnonzero((new != clut).any(1))
    assert set(moved) <= set(changed.tolist())
    # the lightest row's cells never exceed: its nodes are not touched
    assert not set(changed.tolist()) & set(range(grid * grid))


def test_a_protected_corner_stays_unless_it_is_itself_over_the_limit():
    grid, n, limit = 5, 4, 2.6
    tables = _concave_tables(n)
    clut = _table_with_limit(n, grid, limit)
    tac = tg._out(tables, clut.astype(float)).sum(1)
    exc, _ = tg.cell_excess(clut, tables, grid, limit)
    cells = tg._cells(grid)
    # a corner on the limit inside a cell that exceeds
    bad = cells[exc > 1e-4].ravel()
    bad = bad[tac[bad] <= limit - 1e-3]
    k = int(bad[np.argmax(tac[bad])])
    new, changed = tg.guard_clut(clut, tables, grid, limit, protect=[k])
    assert k not in set(changed.tolist())
    assert (new[k] == clut[k]).all()
    assert _dense_max(new, tables, grid, limit) <= limit + 1e-4
    # over the limit itself: it cannot be protected, it comes down
    over = clut.copy()
    over[k] = np.minimum(over[k].astype(int) + 3000, 0xFFFF)
    assert tg._out(tables, over[k:k + 1].astype(float)).sum() > limit + 1e-3
    new, changed = tg.guard_clut(over, tables, grid, limit, protect=[k])
    assert k in set(changed.tolist())
    assert _dense_max(new, tables, grid, limit) <= limit + 1e-4


def test_a_table_inside_the_limit_comes_back_as_the_same_bytes():
    grid, n = 5, 4
    tables = _concave_tables(n)
    clut = _table_with_limit(n, grid, 1.5)
    blob = icw.make_mft2(3, n, grid, clut, out_tables=tables)
    out, changed = tg.guard_mft2(blob, 3.9)           # nothing near 390 %
    assert out is blob and len(changed) == 0


def test_the_guarded_tag_keeps_everything_but_the_clut():
    grid, n, limit = 5, 4, 2.6
    tables = _concave_tables(n)
    clut = _table_with_limit(n, grid, limit)
    blob = icw.make_mft2(3, n, grid, clut, out_tables=tables)
    out, changed = tg.guard_mft2(blob, limit)
    assert len(out) == len(blob) and len(changed)
    e_in = struct.unpack(">HH", blob[48:52])[0]
    pos = 52 + 2 * 3 * e_in
    size = 2 * grid ** 3 * n
    assert out[:pos] == blob[:pos] and out[pos + size:] == blob[pos + size:]
    # aliases stay aliases, bytes are guarded
    luts = tg.guard_luts({"B2A1": blob, "B2A0": "B2A1", "A2B1": b"x"},
                         limit * 100.0)
    assert luts["B2A0"] == "B2A1" and luts["A2B1"] == b"x"
    assert luts["B2A1"] == out


def _b2a_max(path, limit):
    from benchmarks.iccread import IccProfile
    p = IccProfile(path)
    worst = 0.0
    for tag in ("B2A0", "B2A1", "B2A2"):
        blob = p.tags[tag]
        e_in, e_out = struct.unpack(">HH", blob[48:52])
        n, grid = blob[9], blob[10]
        pos = 52 + 2 * 3 * e_in
        clut = np.frombuffer(blob, ">u2", grid ** 3 * n, pos).reshape(-1, n)
        tables = np.frombuffer(blob, ">u2", n * e_out,
                               pos + 2 * grid ** 3 * n).reshape(n, e_out)
        exc, _ = tg.cell_excess(clut, tables, grid, limit)
        worst = max(worst, float(exc.max()))
    return worst


@pytest.mark.slow
def test_a_build_with_the_token_holds_the_limit_and_is_the_guarded_build(tmp_path):
    """Wiring: the guard is the last step before writing, so the token's
    file is the token-less file with its B2A tags guarded, byte for byte;
    A2B and everything else are untouched."""
    from benchmarks.iccread import IccProfile
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    from workflow.profile_engine.builder import BuildSettings, build_profile
    p = PRINTERS["S3"]
    chart = make_chart(p, 400)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "S3.ti3", p, chart, xyz, refl)
    out = {}
    for tokens in (frozenset(), frozenset({TOKEN})):
        (tmp_path / str(len(tokens))).mkdir()
        f = tmp_path / str(len(tokens)) / "S3.icc"   # same name: same desc
        build_profile(ti3, f, BuildSettings(quality="l", gammap_mode="accurate",
                                            ink_limit=280.0,
                                            engine_candidates=tokens))
        out[len(tokens)] = IccProfile(f)
    off, on = out[0], out[1]
    assert set(off.tags) == set(on.tags)
    from workflow.profile_engine.pcs import LabPcs
    for tag in off.tags:
        if tag.startswith("B2A"):
            grid = off.tags[tag][10]
            black = (int(np.argmin(np.linalg.norm(LabPcs.node_lab(grid), axis=1)))
                     if off.pcs == b"Lab " else 0)
            want, _ = tg.guard_mft2(off.tags[tag], 2.8, protect=[black])
            assert on.tags[tag] == want, tag
        else:
            assert on.tags[tag] == off.tags[tag], tag
    assert _b2a_max(tmp_path / "1" / "S3.icc", 2.8) <= 1e-4
