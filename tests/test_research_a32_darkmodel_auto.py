"""Agent 32 (2026-10-06): research token "a32-darkmodel-auto".

Agent 29a's fixed dark-corner fit weight ("a29-darkmodel") wins on clean
dark readings (real ET-8550 held-out darks 0.718 -> 0.591 dE00) and follows
the noise on pessimistic charts. This token lets the chart decide: the weight
(0 = off) is chosen on five held-out chart folds at the smoothing the plain
fit chose, and is taken only when it clearly beats "off". Off by default; a
build where the chart says "off" is the base build.
"""
from pathlib import Path

import numpy as np
import pytest

from workflow.profile_engine import darkauto
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             candidates_from_env)
from workflow.profile_engine.metrics import delta_e_2000

TOKEN = "a32-darkmodel-auto"


def test_the_token_is_known_and_off_by_default():
    assert TOKEN in ENGINE_CANDIDATE_TOKENS
    assert TOKEN + "-lamcv" in ENGINE_CANDIDATE_TOKENS
    assert TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert TOKEN + "-lamcv" not in ACCURATE_DEFAULT_TOKENS
    assert candidates_from_env(f"{TOKEN}, nonsense") == frozenset({TOKEN})


def test_the_token_names_are_read_exactly():
    assert darkauto.wanted({TOKEN}) and darkauto.wanted({TOKEN + "-lamcv"})
    assert not darkauto.wanted({"a29-darkmodel"})
    assert not darkauto.wanted({TOKEN + "x"})
    assert not darkauto.wanted(None)
    assert darkauto.lam_cv_wanted({TOKEN + "-lamcv"})
    assert not darkauto.lam_cv_wanted({TOKEN})


def test_the_weight_is_agent_29a_s_ramp():
    lab = np.array([[0.0, 0, 0], [25.0, 0, 0], [50.0, 0, 0], [90.0, 0, 0]])
    w = darkauto.dark_weights(lab, 3.0)
    assert w == pytest.approx([4.0, 2.5, 1.0, 1.0])
    assert darkauto.dark_weights(lab, 0.0) == pytest.approx(np.ones(4))


class _Stub:
    """A forward 'model' whose dark error depends on how hard the training
    rows weighed the darks: ``gain`` > 0 means weighting helps (a clean
    chart), < 0 means it hurts (a noisy one)."""

    def __init__(self, truth, gain, wdark):
        self.truth, self.gain, self.wdark = truth, gain, wdark

    def predict(self, dev):
        lab = self.truth(dev)
        dark = np.clip((50.0 - lab[:, 0]) / 50.0, 0.0, 1.0)
        err = 1.2 - self.gain * np.log(self.wdark)
        return lab + np.c_[np.zeros(len(lab)), dark * err, np.zeros(len(lab))]


def _chart(n=400, seed=1):
    rng = np.random.default_rng(seed)
    dev = rng.uniform(0, 1, (n, 3))
    dev[:3] = [[1, 1, 1], [0, 0, 0], [1, 0, 0]]

    def truth(d):
        d = np.atleast_2d(d)
        L = 5 + 90 * d.mean(1)
        return np.c_[L, 30 * (d[:, 0] - d[:, 1]), 30 * (d[:, 1] - d[:, 2])]
    return dev, truth(dev), truth


@pytest.mark.parametrize("gain,expect_on", [(0.5, True), (-0.5, False),
                                            (0.0, False)])
def test_the_chart_decides(gain, expect_on):
    dev, lab, truth = _chart()
    calls = []

    def fit_fn(d, l, w, lam):
        calls.append(lam)
        dk = l[:, 0] < 50
        return _Stub(truth, gain, float(w[dk].mean()) if dk.any() else 1.0)

    alpha, lam, rep = darkauto.choose(dev, lab, None, fit_fn, 0.04,
                                      delta_e_2000)
    assert set(calls) == {0.04} and lam == 0.04     # smoothing held fixed
    assert len(calls) == len(darkauto.ALPHAS) * darkauto.FOLDS
    assert (alpha > 0) == expect_on
    if expect_on:
        assert alpha == max(darkauto.ALPHAS)
        assert rep["alphas"][alpha]["accepted"]
    # deterministic: the same chart gives the same report
    assert darkauto.choose(dev, lab, None, fit_fn, 0.04,
                           delta_e_2000)[2] == rep


def test_the_lamcv_variant_chooses_the_smoothing_first():
    dev, lab, truth = _chart()

    def fit_fn(d, l, w, lam):
        # best smoothing at base x1 (0.04), weight neutral
        return _Stub(truth, -1.0, np.exp(abs(np.log(lam / 0.04))))

    alpha, lam, rep = darkauto.choose(
        dev, lab, None, fit_fn, 0.16, delta_e_2000,
        lam_factors=darkauto.LAM_FACTORS, base_lam=0.04)
    assert lam == pytest.approx(0.04) and alpha == 0.0
    assert set(rep["lam_cv"]) == {str(f) for f in darkauto.LAM_FACTORS}


def test_the_module_reads_and_writes_no_file_without_naming_its_encoding():
    src = Path(darkauto.__file__).read_text(encoding="utf-8")
    assert "open(" not in src and "read_text(" not in src


def _tags(path: Path) -> dict:
    """ICC tag signature -> bytes, without 'desc' (binary read, no text)."""
    data = path.read_bytes()
    count = int.from_bytes(data[128:132], "big")
    out = {}
    for i in range(count):
        e = data[132 + 12 * i:144 + 12 * i]
        sig = e[:4].decode("ascii")
        off, size = int.from_bytes(e[4:8], "big"), int.from_bytes(e[8:12], "big")
        if sig != "desc":
            out[sig] = data[off:off + size]
    return out


@pytest.mark.slow
def test_off_is_the_base_build_and_on_refits_at_the_fixed_smoothing(
        tmp_path, monkeypatch):
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    from workflow.profile_engine import accuracy
    from workflow.profile_engine.builder import BuildSettings, build_profile
    p = PRINTERS["S1"]
    chart = make_chart(p, 300)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "S1.ti3", p, chart, xyz, refl)

    def build(name, tokens):
        out = tmp_path / f"{name}.icc"
        build_profile(ti3, out, BuildSettings(quality="l",
                                              gammap_mode="accurate",
                                              engine_candidates=tokens))
        return out

    base = build("base", frozenset())
    real_choose = darkauto.choose
    monkeypatch.setattr(darkauto, "choose",
                        lambda *a, **k: (0.0, a[4], real_choose(*a, **k)[2]))
    off = build("off", frozenset({TOKEN}))
    # alpha 0: the same tags (the description and the header date aside)
    assert _tags(base) == _tags(off)

    seen = []
    real_fit = accuracy.fit_forward_model_accurate

    def spy(*a, fixed_lam=None, row_weights=None, **kw):
        seen.append((fixed_lam, None if row_weights is None
                     else np.asarray(row_weights).copy()))
        return real_fit(*a, fixed_lam=fixed_lam, row_weights=row_weights, **kw)

    monkeypatch.setattr(accuracy, "fit_forward_model_accurate", spy)
    monkeypatch.setattr(darkauto, "choose",
                        lambda *a, **k: (3.0, a[4], {"n_heldout": 1,
                                                     "alphas": {3.0: {"mean": 0.1}},
                                                     "off": {"mean": 0.2}}))
    build("on", frozenset({TOKEN}))
    final = seen[-1]
    assert seen[0][0] is None                      # the plain fit searches
    assert final[0] is not None                    # the refit holds it fixed
    assert final[1] is not None and final[1].max() > 1.5 and final[1].min() >= 1.0
