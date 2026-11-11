"""F-00 under Maximum accuracy's DEFAULT token state (research integration 1).

The strict xfail in tests/test_engine_accurate_mode.py
(test_accurate_cmyk_build_and_separation_smoothness) keeps F-00 recorded at
the grid it was found on: it builds with "no-b2a33s", so the -ql B2A is grid
9, and the neutral column still jumps there. With the shipped default
(b2a33s ON) the same fixture's B2A is grid 33 and the same neutral-column
check PASSES (gate-07 on edf19949: XPASS). This test pins that, so a
regression of the default turns the gate red.

What the pass does and does not mean: the check measures the step between
ADJACENT nodes, and a grid four times finer per axis makes every step
smaller; the late-GCR K locus meeting this fixture's ink-limit face
(Findings/agent5-03 item 4) is not changed by b2a33s. So this is what a
CMM reads from the shipped table (smaller node-to-node steps in the neutral
column), not a fix of the K rule."""
from __future__ import annotations

import struct

import numpy as np
import pytest

from tests.test_profile_engine import write_synth_ti3
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine.builder import accurate_candidates


def _neutral_column(icc_bytes: bytes) -> tuple[int, np.ndarray]:
    ntags = struct.unpack(">I", icc_bytes[128:132])[0]
    off = None
    for i in range(ntags):
        sig, o, _size = struct.unpack(">4sII",
                                      icc_bytes[132 + 12 * i:144 + 12 * i])
        if sig == b"B2A1":
            off = o
    assert off is not None
    n_in, n_out, grid = icc_bytes[off + 8], icc_bytes[off + 9], \
        icc_bytes[off + 10]
    assert (n_in, n_out) == (3, 4)
    n_in_entries, _ = struct.unpack(">HH", icc_bytes[off + 48:off + 52])
    clut_off = off + 52 + 2 * n_in * n_in_entries
    clut = np.frombuffer(icc_bytes, dtype=">u2", count=grid ** 3 * n_out,
                         offset=clut_off).reshape(grid, grid, grid, n_out)
    mid = grid // 2
    return grid, clut[:, mid, mid, :].astype(float) / 0xFFFF


@pytest.mark.slow
def test_the_default_token_state_passes_the_f00_neutral_column_check(tmp_path):
    assert "b2a33s" in accurate_candidates(frozenset())
    ti3 = write_synth_ti3(tmp_path / "cmyk.ti3", "CMYK",
                          [f"CMYK_{c}" for c in "CMYK"], additive=False,
                          n_per_axis=7, ink_limit=300.0)
    st = BuildSettings(quality="l", gammap_mode="accurate")
    res = build_profile(ti3, tmp_path / "cmyk.icc", st)
    assert res.icc_path.exists()
    grid, neutral_col = _neutral_column(res.icc_path.read_bytes())
    assert grid == 33
    # the same three checks as the strict xfail, unchanged thresholds
    k = neutral_col[:, 3]
    assert np.diff(k).max() < 0.10
    assert np.abs(np.diff(k)).sum() < (k[0] - k[-1]) + 0.30
    assert np.abs(np.diff(neutral_col, axis=0)).max() < 0.45
