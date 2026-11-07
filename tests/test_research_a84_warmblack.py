"""Research a84-warmblack (Agent 84, Findings/agent84-01): on a CMYK printer with a mild measured ink fold the
forward fit keeps clustered dark patches the robust fit had rejected as misreads."""
import numpy as np

from workflow.profile_engine import accuracy, builder, gpsel


def test_token_registered_and_off_by_default():
    assert builder.A84_WARMBLACK == "a84-warmblack"
    assert builder.A84_WARMBLACK in builder.ENGINE_CANDIDATE_TOKENS
    assert builder.A84_WARMBLACK not in builder.ACCURATE_DEFAULT_TOKENS
    assert builder.A84_WARMBLACK not in builder.accurate_candidates(())
    assert gpsel.A84_KEEP_CLUSTERS is False


def test_cluster_keep_gives_back_a_cluster_but_not_an_isolated_misread():
    rng = np.random.default_rng(84)
    # a region the model cannot follow: 20 patches close together, every one missed by ~5
    blob = np.array([0.7, 1.0, 0.3, 0.5]) + 0.02 * rng.standard_normal((20, 4))
    dev = np.vstack([rng.random((400, 4)) * np.array([1, 0.6, 1, 1]), blob])
    res = np.full(len(dev), 0.3)
    w = np.ones(len(dev))
    corner = np.arange(len(dev)) >= 400
    res[corner] = 5.0
    w[corner] = 0.0
    # one isolated misread far from it
    lone = int(np.flatnonzero(~corner)[0])
    res[lone], w[lone] = 6.0, 0.0
    out = accuracy.a84_cluster_keep(dev, res, w)
    assert corner.sum() >= 5
    assert (out[corner] == 1.0).all()
    assert out[lone] == 0.0
    assert (out[~corner & (np.arange(len(dev)) != lone)] == 1.0).all()
    assert (w[corner] == 0.0).all()          # the input is not modified


def test_fit_default_is_unchanged_without_the_flag():
    import inspect
    sig = inspect.signature(accuracy.fit_forward_model_accurate)
    assert sig.parameters["keep_clusters"].default is False
