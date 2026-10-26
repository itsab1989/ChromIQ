"""Research a80-greywalk / a80-colpin / a80-lincurve / a80-oraclecurve (Agent 80): the grey walk near black."""
import numpy as np

from workflow.profile_engine import b2a, builder, gamut_map


def test_tokens_registered_passed_ones_on_since_integration11():
    toks = {b2a.A80_TOKEN, b2a.A80_LINCURVE, b2a.A80_COLPIN, gamut_map.A80_ORACLECURVE}
    assert toks <= builder.ENGINE_CANDIDATE_TOKENS
    on = {b2a.A80_TOKEN, b2a.A80_LINCURVE, b2a.A80_COLPIN}
    assert on <= builder.ACCURATE_DEFAULT_TOKENS
    assert gamut_map.A80_ORACLECURVE not in builder.ACCURATE_DEFAULT_TOKENS
    assert "a80-perccol" not in builder.ACCURATE_DEFAULT_TOKENS


def _axis(jump: bool):
    ls = np.arange(100.0, -1e-9, -0.5)
    k = np.clip((60 - ls) / 40, 0, 1) ** 1.6
    c = np.clip((80 - ls) / 60, 0, 1) * 0.7
    if jump:
        c = np.where(ls < 24, 0.1, c)       # C/M/Y fall off the ink-limit face within one step
    dev = np.stack([c, c, c, k], 1)
    ok = ls >= 20.0
    return {"l": ls, "dev": dev, "ok": ok, "l_black": 20.0, "black": dev[np.flatnonzero(ok)[-1]].copy()}


def test_walk_jump_reads_the_largest_ink_step_near_the_black():
    assert b2a.a80_walk_jump(_axis(False)) < b2a.A80_JUMP
    assert b2a.a80_walk_jump(_axis(True)) >= b2a.A80_JUMP
    assert b2a.a80_walk_jump({"l_black": None}) == 0.0


def test_rewalk_needs_a_black_ink():
    ax = _axis(True)
    assert b2a.a80_rewalk(None, ax, kw={"channel_letters": list("CMYO")}) is ax


def test_oracle_output_keeps_every_node_device_value():
    from workflow.profile_engine import icc_writer as icw
    rng = np.random.default_rng(3)
    g, n = 5, 4
    curve = np.linspace(0, 1, 64) ** 1.7
    dev = rng.random((g ** 3, n))
    shaped = np.interp(dev, curve, np.linspace(0, 1, 64))
    blob = icw.make_mft2(3, n, g, icw.device_to_u16(shaped),
                         out_tables=icw.curves_to_tables(np.tile(curve, (n, 1)), 1024))
    oracle = np.tile(np.linspace(0, 1, 1024) ** 0.6, (n, 1))     # colprof's own (different) curves
    out = gamut_map.a80_oracle_output(blob, oracle)
    assert len(out) == len(blob) and out[:52] == blob[:52]
    c0 = 52 + 3 * 256 * 2
    clut = np.frombuffer(out[c0:c0 + 2 * g ** 3 * n], ">u2").reshape(-1, n) / 65535.0
    outs = np.frombuffer(out[c0 + 2 * g ** 3 * n:c0 + 2 * g ** 3 * n + 2 * n * 1024], ">u2").reshape(n, -1) / 65535.0
    got = np.stack([np.interp(clut[:, c], np.linspace(0, 1, 1024), outs[c]) for c in range(n)], 1)
    assert np.abs(got - dev).max() < 2e-3
    assert np.abs(outs - oracle).max() < 1e-4
    assert gamut_map.a80_oracle_output(blob, None) is blob
