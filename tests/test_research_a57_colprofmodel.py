"""Agent 57 (2026-10-13, D-30): research token "a57-colprofmodel-b2a".

Step 1 of the question "does colprof's smoother relative colorimetric come
from its forward model?": the colorimetric B2A1 is inverted from colprof's
own A2B1 (read from a colprof profile of the same .ti3, env
CHROMIQ_A57_COLPROF_ICC), with every clip and black rule of the engine
unchanged; the A2B and the other B2A tables keep the engine's model. RGB
only, off by default.
"""
import struct
from pathlib import Path

import numpy as np

from workflow.profile_engine import colprofmodel as cm
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS)

TOK = cm.A57_TOKEN


def _lab_code(lab):
    lab = np.asarray(lab, float)
    return np.stack([lab[:, 0] / 100 * 0xFF00, (lab[:, 1] + 128) / 255 * 0xFF00,
                     (lab[:, 2] + 128) / 255 * 0xFF00], 1)


def _profile(tmp_path: Path, *, grid=5, in_curve=lambda x: x ** 0.8,
             pcs=b"Lab ") -> tuple[Path, callable]:
    """A minimal RGB->Lab lut16 profile whose truth is known: Lab is linear
    in the shaped coordinate (so the multilinear CLUT is exact)."""
    def truth_shaped(u):
        u = np.asarray(u, float)
        return np.stack([20 + 80 * u.mean(1), 60 * (u[:, 0] - u[:, 1]),
                         50 * (u[:, 1] - u[:, 2])], 1)
    g = np.linspace(0, 1, grid)
    u = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    clut = np.round(_lab_code(truth_shaped(u))).astype(">u2")
    x = np.linspace(0, 1, 256)
    in_t = np.tile(np.round(in_curve(x) * 0xFFFF).astype(">u2"), (3, 1))
    tag = icw.make_mft2(3, 3, grid, clut, in_tables=in_t)
    head = bytearray(128)
    head[16:20] = b"RGB "
    head[20:24] = pcs
    off = 128 + 4 + 12
    body = bytes(head) + struct.pack(">I", 1) + struct.pack(
        ">4sII", b"A2B1", off, len(tag)) + tag
    p = tmp_path / "toy-colprof.icc"
    p.write_bytes(body)
    return p, (lambda d: truth_shaped(in_curve(np.asarray(d, float))))


def test_the_token_is_known_and_not_a_default():
    assert TOK in ENGINE_CANDIDATE_TOKENS
    assert TOK not in ACCURATE_DEFAULT_TOKENS


def test_the_token_acts_on_rgb_only():
    assert cm.a57_on({TOK}, is_additive=True)
    assert not cm.a57_on({TOK}, is_additive=False)
    assert not cm.a57_on(set(), is_additive=True)
    assert not cm.a57_on(None, is_additive=True)


def test_the_colprof_profile_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv(cm.A57_ENV, raising=False)
    assert cm.colprof_icc_from_env() is None
    monkeypatch.setenv(cm.A57_ENV, "  ")
    assert cm.colprof_icc_from_env() is None
    monkeypatch.setenv(cm.A57_ENV, "/x/colprof.icc")
    assert cm.colprof_icc_from_env() == Path("/x/colprof.icc")


def test_legacy_lut16_lab_decoding():
    lab = cm.lut16_lab_decode(np.array([[0xFF00, 0x8000, 0x8000], [0, 0, 0]]))
    assert np.allclose(lab[0], [100.0, 0.0, 0.0], atol=1e-9)
    assert np.allclose(lab[1], [0.0, -128.0, -128.0])


def test_the_tag_lookup_reproduces_the_profile(tmp_path):
    p, truth = _profile(tmp_path)
    lut = cm.Lut16Lab(cm.read_tags(p)[1]["A2B1"])
    d = np.random.default_rng(57).random((300, 3))
    assert np.abs(lut.lookup(d) - truth(d)).max() < 0.1   # 256-entry input table


def test_the_forward_model_is_the_profile_as_the_engine_reads_it(tmp_path):
    p, truth = _profile(tmp_path)
    m = cm.forward_model_from_icc(p, grid=9)
    assert m.grid == 9 and m.n_channels == 3 and m.nodes.shape == (729, 3)
    d = np.random.default_rng(7).random((300, 3))
    assert np.abs(m.predict(d) - truth(d)).max() < 0.1
    # the input curves are the profile's own (device -> grid coordinate)
    assert np.allclose(m.shape_device(np.array([[0.5, 0.5, 0.5]])),
                       0.5 ** 0.8, atol=2e-3)
    assert np.all(np.diff(m.curves, axis=1) >= 0)


def test_a_non_lab_profile_is_refused(tmp_path):
    p, _ = _profile(tmp_path, pcs=b"XYZ ")
    try:
        cm.forward_model_from_icc(p)
    except ValueError as exc:
        assert "Lab PCS" in str(exc)
    else:
        raise AssertionError("an XYZ-PCS profile must be refused")


def test_the_module_reads_profiles_as_bytes_only():
    src = Path(cm.__file__).read_text(encoding="utf-8")
    assert "read_bytes()" in src
    assert "open(" not in src and "read_text(" not in src
