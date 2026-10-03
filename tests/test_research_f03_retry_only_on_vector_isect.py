"""Research agent9-01 4.1 (F-03): the bit-exact helper is retried with the
shell's own neutral black ONLY when Argyll aborted with "vector_isect
failed", and only when CHROMIQ_F03_RETRY is set. A call that succeeds is
never retried, so every table that built before keeps its bytes."""
import numpy as np
import pytest

from workflow.profile_engine.gammap_helper import HelperUnavailable
from workflow.profile_engine.gammap_port import wire


class _Ap:
    def lab_to_jab(self, x):
        return np.asarray(x, float)

    def jab_to_lab(self, x):
        return np.asarray(x, float)


def _mapper():
    cloud = np.array([[100.0, 0, 0], [10.0, 1.0, -2.0], [12.0, 30.0, 0],
                      [50.0, 0.5, 0.5], [60.0, -40.0, 20.0]])
    return wire.ArgyllHelperMapper(
        src_gam="src.gam", intent="p", mapres=9, ap_src=_Ap(), ap_dst=_Ap(),
        wp_jab=np.array([100.0, 0, 0]), bp_jab=np.array([5.0, -90.0, 7.0]),
        dst_gam=None, dst_cloud_jab=cloud, td=None)


def _fake(fail_first: str | None, calls: list):
    def run(q, **k):
        calls.append(np.asarray(k["bp_jab"], float).copy())
        if fail_first and len(calls) == 1:
            raise HelperUnavailable(fail_first)
        return np.asarray(q, float)
    return run


def test_success_is_never_retried(monkeypatch):
    calls = []
    monkeypatch.setenv("CHROMIQ_F03_RETRY", "1")
    monkeypatch.setattr(wire, "run_gammap", _fake(None, calls))
    _mapper().map_lab(np.array([[50.0, 10.0, 10.0]]))
    assert len(calls) == 1
    assert np.allclose(calls[0], [5.0, -90.0, 7.0])


def test_vector_isect_failure_is_retried_with_the_shell_black(monkeypatch):
    calls = []
    monkeypatch.setenv("CHROMIQ_F03_RETRY", "1")
    monkeypatch.setattr(wire, "run_gammap", _fake(
        "helper failed (1): Error - gamut: vector_isect failed!", calls))
    _mapper().map_lab(np.array([[50.0, 10.0, 10.0]]))
    assert len(calls) == 2
    assert np.allclose(calls[1], [10.0, 1.0, -2.0])   # darkest near-neutral


def test_without_the_switch_the_failure_stays(monkeypatch):
    calls = []
    monkeypatch.delenv("CHROMIQ_F03_RETRY", raising=False)
    monkeypatch.setattr(wire, "run_gammap", _fake(
        "Error - gamut: vector_isect failed!", calls))
    with pytest.raises(HelperUnavailable):
        _mapper().map_lab(np.array([[50.0, 10.0, 10.0]]))


def test_other_failures_are_not_retried(monkeypatch):
    calls = []
    monkeypatch.setenv("CHROMIQ_F03_RETRY", "1")
    monkeypatch.setattr(wire, "run_gammap", _fake("helper failed (2): usage", calls))
    with pytest.raises(HelperUnavailable):
        _mapper().map_lab(np.array([[50.0, 10.0, 10.0]]))
    assert len(calls) == 1
