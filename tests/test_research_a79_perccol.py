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
