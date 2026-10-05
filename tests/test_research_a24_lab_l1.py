"""Research C-L1 (Agent 24, token "a24-l1"): the lut16 A2B L* output encoding.

Same meaning under the ICC specification (littleCMS, Argyll, iccDEV), and ColorSync then reads
paper white as L* 100 instead of 99.6 (Validation/d01-challenge.md; Findings/agent24-01 s3)."""
import inspect
import struct
import sys

import numpy as np
import pytest

from workflow.profile_engine import builder
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.lab_l1 import apply_l1, encode_a2b_l1


def _rgb_a2b(grid=5, top_l=100.0, out_entries=256):
    g = np.linspace(0, 1, grid)
    r, gg, b = np.meshgrid(g, g, g, indexing="ij")
    lab = np.stack([top_l * (0.2 * r + 0.7 * gg + 0.1 * b).ravel(),
                    (40 * (r - gg)).ravel(), (30 * (gg - b)).ravel()], 1)
    return icw.make_mft2(3, 3, grid, icw.lab_to_u16(lab),
                         out_tables=np.tile(icw._identity_table(out_entries), (3, 1))), lab


def _decode_nodes(blob):
    """Spec decoding of every CLUT node of one mft2 Lab A2B (output tables applied)."""
    n_in, n_out, grid = blob[8], blob[9], blob[10]
    n_it, n_ot = struct.unpack(">HH", blob[48:52])
    o = 52 + 2 * n_in * n_it
    clut = np.frombuffer(blob, ">u2", grid ** n_in * 3, o).reshape(-1, 3).astype(float)
    out = np.frombuffer(blob, ">u2", 3 * n_ot, o + 2 * clut.size).reshape(3, n_ot).astype(float)
    x = np.linspace(0, 65535, n_ot)
    v = np.stack([np.interp(clut[:, c], x, out[c]) for c in range(3)], 1)
    return icw.u16_to_lab(v)


def test_the_spec_meaning_is_unchanged():
    blob, _ = _rgb_a2b()
    l1 = encode_a2b_l1(blob)
    assert l1 != blob and len(l1) == len(blob)
    d = np.abs(_decode_nodes(l1) - _decode_nodes(blob))
    assert d[:, 0].max() < 0.003          # one CLUT code of rounding
    assert d[:, 1:].max() == 0.0          # a*, b* untouched


def test_the_clut_uses_the_full_scale_and_the_l_table_ends_at_ff00():
    blob, _ = _rgb_a2b()
    l1 = encode_a2b_l1(blob)
    n_it, n_ot = struct.unpack(">HH", l1[48:52])
    o = 52 + 2 * 3 * n_it
    clut = np.frombuffer(l1, ">u2", 125 * 3, o).reshape(-1, 3)
    out = np.frombuffer(l1, ">u2", 3 * n_ot, o + 2 * clut.size).reshape(3, n_ot)
    assert clut[:, 0].max() == 0xFFFF
    assert out[0, 0] == 0 and out[0, -1] == 0xFF00
    assert np.array_equal(out[1:], np.frombuffer(blob, ">u2", 3 * n_ot,
                                                 o + 2 * clut.size).reshape(3, n_ot)[1:])


def test_a_tag_with_l_above_100_is_left_alone():
    blob, _ = _rgb_a2b(top_l=100.3)
    assert encode_a2b_l1(blob) == blob


def test_only_a2b_tags_with_own_bytes_change():
    blob, _ = _rgb_a2b()
    luts = {"A2B1": blob, "A2B0": "A2B1", "B2A1": b"mft2-b2a", "gamt": b"g"}
    out = apply_l1(luts)
    assert out["A2B0"] == "A2B1" and out["B2A1"] == luts["B2A1"] and out["gamt"] == b"g"
    assert out["A2B1"] == encode_a2b_l1(blob)


def test_the_builder_applies_it_only_for_maximum_accuracy_with_the_token():
    src = inspect.getsource(builder._build_profile_impl)
    i = src.index("apply_l1(")
    gate = src.rfind("\n    if ", 0, i)
    assert 'accurate and "a24-l1" in candidates' in src[gate:i]
    assert "a24-l1" in builder.ENGINE_CANDIDATE_TOKENS


@pytest.mark.skipif(sys.platform != "darwin", reason="ColorSync is macOS only")
def test_colorsync_reads_paper_white_as_100(tmp_path):
    from benchmarks.research import cmm
    blob, _ = _rgb_a2b()
    res = {}
    for name, tag in (("L0", blob), ("L1", encode_a2b_l1(blob))):
        p = tmp_path / f"{name}.icc"
        spec = icw.ProfileSpec(n_channels=3, color_rep="RGB_LAB", description=name,
                               wtpt=tuple(np.array(icw.D50_XYZ, float)))
        icw.write_profile(p, spec, {"A2B0": tag, "A2B1": "A2B0", "A2B2": "A2B0",
                                    "B2A0": tag, "B2A1": "B2A0", "B2A2": "B2A0"})
        res[name] = cmm.a2b(p, np.ones((1, 3)), "colorsync")[0]
    assert res["L0"][0] < 99.8           # the misreading this candidate removes
    assert abs(res["L1"][0] - 100.0) < 0.05
