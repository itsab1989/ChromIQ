"""Agent 58 (research token a58-purecolprof): the RGB colorimetric B2A1 built
as colprof builds it, with the engine's additions given back one at a time
(workflow/profile_engine/purecolprof.py)."""
from __future__ import annotations

import inspect
import json

import numpy as np
import pytest

from workflow.profile_engine import purecolprof as P


def test_the_tokens_are_known_and_v_noclip_is_the_default():
    # Integration 8 (Agent 62): a58-purecolprof with every keep token except
    # the engine's own clip metric (ourclip) and the all-fine grid (grid33)
    from workflow.profile_engine import builder
    off = {"a58-keep-ourclip", "a58-keep-grid33"}
    for t in (P.TOKEN,) + P.KEEP_TOKENS:
        assert t in builder.ENGINE_CANDIDATE_TOKENS
        assert (t in builder.ACCURATE_DEFAULT_TOKENS) == (t not in off)
        if t not in off:
            assert "no-" + t in builder.ENGINE_CANDIDATE_TOKENS


def test_applies_to_rgb_maximum_accuracy_only():
    on = {P.TOKEN}
    assert P.applies(on, accurate=True, is_additive=True, n=3)
    assert not P.applies(on, accurate=True, is_additive=False, n=4)
    assert not P.applies(on, accurate=False, is_additive=True, n=3)
    assert not P.applies(set(), accurate=True, is_additive=True, n=3)


def test_keep_is_int7_when_inactive_and_opt_in_when_active():
    for s in P.KEEP_STEPS:
        assert P.keep(set(), s, active=False)
        assert not P.keep({P.TOKEN}, s, active=True)
        assert P.keep({P.TOKEN, f"a58-keep-{s}"}, s, active=True)
    with pytest.raises(ValueError):
        P.keep(set(), "nonsense", active=True)


def test_residual_is_the_rev_c_distance():
    rng = np.random.default_rng(58)
    y = rng.normal(0, 40, (500, 3))
    t = rng.normal(0, 40, (500, 3))
    r = P.lchw_residual(y, t)
    assert np.allclose((r * r).sum(1), P.lchw_sq(y, t), rtol=1e-9, atol=1e-8)


def test_rev_c_weights_are_colprofs():
    # xlut.c JCCWEIGHT 2, CCCWEIGHT 1, HCCWEIGHT 2.2; CAMCLIPTRANS 1
    assert P.LCH_WEIGHTS == (2.0, 1.0, 2.2)
    assert P.CAMCLIPTRANS == 1.0
    t = np.array([[50.0, 30.0, 0.0]])
    assert P.lchw_sq(np.array([[51.0, 30.0, 0.0]]), t)[0] == pytest.approx(4.0)
    assert P.lchw_sq(np.array([[50.0, 31.0, 0.0]]), t)[0] == pytest.approx(1.0)
    # pure hue move at equal chroma: dH^2 = dab^2, weighted 4.84
    y = np.array([[50.0, 30.0 * np.cos(0.1), 30.0 * np.sin(0.1)]])
    dab2 = ((y - t)[0, 1:] ** 2).sum()
    assert P.lchw_sq(y, t)[0] == pytest.approx(4.84 * dab2)


class _Box:
    """Toy RGB 'printer': Lab = 20 + 60 * mean, a/b from R-G, G-B (smooth)."""
    n_channels = 3

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        return np.stack([20.0 + 60.0 * d.mean(1), 40.0 * (d[:, 0] - d[:, 1]),
                         40.0 * (d[:, 1] - d[:, 2])], 1)


def test_cam_clip_leaves_in_gamut_nodes_and_blends_continuously():
    m = _Box()
    d = np.array([[0.5, 0.5, 0.5], [0.2, 0.3, 0.4]])
    t = m.predict(d)
    out = P.cam_clip(m, t, d, np.zeros(2))
    assert np.array_equal(out, d)
    # an out-of-gamut target far away takes the CAM answer (bf = 1): the
    # result is printable and no farther (rev.c metric, in Jab) than the
    # Lab-nearest answer it started from
    from workflow.profile_engine.oog_clip import lab_to_argyll_jab
    tgt = np.array([[45.0, 90.0, 10.0]])
    d0 = np.array([[1.0, 0.0, 0.2]])
    res = np.linalg.norm(m.predict(d0) - tgt, axis=1)
    out = P.cam_clip(m, tgt, d0, res)
    assert ((out >= 0) & (out <= 1)).all()
    tj = lab_to_argyll_jab(tgt)
    assert (P.lchw_sq(lab_to_argyll_jab(m.predict(out)), tj)[0]
            <= P.lchw_sq(lab_to_argyll_jab(m.predict(d0)), tj)[0] + 1e-9)


def test_floor_lifts_targets_below_it_only():
    m = _Box()
    tgt = np.array([[5.0, 0.0, 0.0]])
    d0 = np.zeros((1, 3))
    res = np.linalg.norm(m.predict(d0) - tgt, axis=1)
    out = P.cam_clip(m, tgt, d0, res, floor=20.0)
    assert m.predict(out)[0, 0] == pytest.approx(20.0, abs=0.5)


def test_active_flag_is_per_thread_and_cleared():
    import threading
    P.set_active(True, floor=4.0, fade=False)
    assert P.active() and P.floor() == 4.0
    seen = []
    th = threading.Thread(target=lambda: seen.append((P.active(), P.floor())))
    th.start(); th.join()
    assert seen == [(False, None)]
    P.set_active(False)
    assert not P.active() and P.floor() is None


def test_builder_wires_every_keep_step():
    from workflow.profile_engine import builder
    src = inspect.getsource(builder._build_profile_impl)
    for s in P.KEEP_STEPS:
        assert f'_a58k("{s}")' in src
    assert "_a58m.set_active(False)" in src


def test_job_file_round_trip_is_utf8(tmp_path):
    # research jobs carry tokens in JSON files: written and read as UTF-8
    f = tmp_path / "jobs.json"
    jobs = [{"candidates": ",".join((P.TOKEN,) + P.KEEP_TOKENS),
             "note": "colprof Jab, L 2 / C 1 / h 2,2 °"}]
    f.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    back = json.loads(f.read_text(encoding="utf-8"))
    assert back == jobs
    assert set(back[0]["candidates"].split(",")) == {P.TOKEN, *P.KEEP_TOKENS}


def test_coarse_outside_keeps_fine_in_gamut_and_coarse_far_out():
    g, gc = 9, 5
    rng = np.random.default_rng(1)
    fine = rng.random((g ** 3, 3))
    coarse = fine.reshape(g, g, g, 3)[::2, ::2, ::2].reshape(-1, 3)
    res = np.zeros(g ** 3)
    assert np.array_equal(P.coarse_outside(fine, coarse, res, g, gc), fine)
    out = P.coarse_outside(fine, coarse, np.full(g ** 3, 10.0), g, gc)
    # shared nodes are exact; the others lie on the coarse trilinear field
    assert np.allclose(out.reshape(g, g, g, 3)[::2, ::2, ::2].reshape(-1, 3), coarse)
    mid = out.reshape(g, g, g, 3)[1, 0, 0]
    c4 = coarse.reshape(gc, gc, gc, 3)
    assert np.allclose(mid, 0.5 * (c4[0, 0, 0] + c4[1, 0, 0]))
