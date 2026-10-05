"""Agent 15 (D-14 repair): the held-out folds respect the chart's
structure, and the tapers hand the table back to the stiff fit where the
design says (beyond the ink limit, near paper, in the dark)."""
import numpy as np

from workflow.profile_engine import builder, gpsel


class _Const:
    def __init__(self, v):
        self.v = np.asarray(v, float)

    def predict(self, z):
        return np.tile(self.v, (len(np.atleast_2d(z)), 1))


def test_tokens_are_known_and_off_by_default():
    for t in ("gpwarp", "gpres", "gpclip", "gpsel", "gpkeep", "gplight",
              "gplight2", "gpdark", "gpsamp"):
        assert t in builder.ENGINE_CANDIDATE_TOKENS
    assert builder.BuildSettings().engine_candidates == frozenset()


def test_folds_keep_duplicates_together_and_never_hold_out_paper_or_solids():
    rng = np.random.default_rng(1)
    dev = rng.uniform(0, 1, (200, 4))
    dev = np.vstack([dev, dev[:20],                       # duplicates
                     np.zeros((3, 4)), np.eye(4),          # paper, solids
                     np.outer(np.linspace(0.1, 0.9, 9), [1, 0, 0, 0])])
    f = gpsel.chart_folds(dev, k=5)
    assert (f[200:220] == f[:20]).all()
    assert (f[220:227] == -1).all()
    ramp = f[227:]
    assert len(set(ramp.tolist())) == 5                  # dealt across folds


def test_taper_weights():
    t = gpsel.Tapered(_Const([1.0, 0, 0]), _Const([0.0, 0, 0]), limit=3.0,
                      light=0.2, dark=(15.0, 30.0))
    z = np.array([[1.0, 1.0, 1.0, 0.5],      # beyond limit + margin
                  [0.0, 0.0, 0.0, 0.0],      # paper
                  [0.5, 0.5, 0.5, 0.0]])     # inside, light enough? no: max 0.5
    # the stiff stand-in predicts L* 0 (dark): everything stays stiff
    assert np.allclose(t.predict(z), 0.0)
    t2 = gpsel.Tapered(_Const([1.0, 0, 0]), _Const([50.0, 0, 0]), limit=3.0,
                       light=0.2)
    out = t2.predict(z)
    assert out[0, 0] == 50.0 and out[1, 0] == 50.0
    assert np.isclose(out[2, 0], 1.0)


def test_light_scale_reads_the_lightest_ramp_step():
    dev = np.vstack([np.zeros((1, 3)), np.diag([0.2, 0.1, 0.3]), np.full((5, 3), 0.5)])
    assert gpsel.light_scale(dev) == 0.3
    assert gpsel.light_scale(np.full((4, 3), 0.5)) == 0.25
