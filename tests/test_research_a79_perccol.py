"""Research a79-perccol (Agent 79): the mild-fold gate of the perceptual neutral column."""
import numpy as np

from workflow.profile_engine import builder, gamut_map


class _Toy:
    """CMYK toy printer: L* = 100 - 80 K - 8 (C+M+Y) (no fold), optionally a fold near K 1 where colour
    LIGHTENS heavy black by ``fold`` L* at K 1."""
    n_channels = 4

    def __init__(self, fold=0.0):
        self.fold = fold

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        c = d[:, :3].sum(1)
        k = d[:, 3]
        lift = self.fold * np.clip((k - 0.7) / 0.3, 0, 1) * np.clip(c / 0.05, 0, 1)
        L = 100 - 80 * k - 8 * c * (1 - np.clip((k - 0.7) / 0.3, 0, 1)) + lift
        return np.stack([L, 0 * L, 0 * L], 1)


def test_token_registered_and_off_by_default():
    assert gamut_map.A79_TOKEN in builder.ENGINE_CANDIDATE_TOKENS
    assert gamut_map.A79_TOKEN not in builder.ACCURATE_DEFAULT_TOKENS


def test_gate_fires_only_on_a_mild_fold():
    letters = list("CMYK")
    assert gamut_map.a79_mild_fold(_Toy(0.0), letters) is None          # no fold
    mild = gamut_map.a79_mild_fold(_Toy(1.8), letters)                  # i1iSis-like
    assert mild is not None and mild[1] < builder.A73_FOLD_MIN
    assert gamut_map.a79_mild_fold(_Toy(5.0), letters) is None          # strong fold: a73-kfirst's
    assert gamut_map.a79_mild_fold(_Toy(1.8), list("CMYO")) is None     # K not fourth


def test_lincurve_keeps_every_node_device_value():
    from workflow.profile_engine import icc_writer as icw
    rng = np.random.default_rng(1)
    g, n = 5, 4
    curve = np.linspace(0, 1, 64) ** 1.7                 # a shaper: CLUT holds curve-space values
    dev = rng.random((g ** 3, n))
    shaped = np.interp(dev, curve, np.linspace(0, 1, 64))
    blob = icw.make_mft2(3, n, g, icw.device_to_u16(shaped),
                         out_tables=icw.curves_to_tables(np.tile(curve, (n, 1)), 1024))
    lin = gamut_map.a79_identity_output(blob)
    assert len(lin) == len(blob) and lin[:52] == blob[:52]
    c0 = 52 + 3 * 256 * 2
    got = np.frombuffer(lin[c0:c0 + 2 * g ** 3 * n], ">u2").reshape(-1, n) / 65535.0
    assert np.abs(got - dev).max() < 2e-4
    outs = np.frombuffer(lin[c0 + 2 * g ** 3 * n:], ">u2").reshape(n, -1)
    assert (outs == np.round(np.linspace(0, 65535, 1024))).all()


def test_dark_path_is_straight_below_the_handover():
    g = 9
    v = np.linspace(0, 1, g)
    nl = np.stack(np.meshgrid(v * 100, v * 256 - 128, v * 256 - 128, indexing="ij"), -1).reshape(-1, 3)
    dev = np.random.default_rng(2).random((len(nl), 4))
    out = gamut_map.a79_dark_path(dev, nl)
    col = np.flatnonzero(np.hypot(nl[:, 1], nl[:, 2]) < 1)
    assert np.array_equal(np.delete(out, col[1:2], 0), np.delete(dev, col[1:2], 0))   # node L 12.5 only moves
    assert np.allclose(out[col[1]], 0.5 * dev[col[0]] + 0.5 * dev[col[2]])
