"""Issue 217 through the Measure path (4.3.54).

A run that holds a one-pass measurement; a NEW measurement with the dual scan on (Refine /
resume not continuing it). The pieces the Measure tab's START uses, in its order: the plan
(``session.plan_for``, nothing to continue), ``TabMeasure._apply_dual_scan`` (the engine's
arguments), the session guard that copies the measurement aside (``MeasurementSession.begin``,
as ``_begin_session_guard``), and then the engine: the simulated helper wrapping the REAL
helper (its replay instrument) with exactly those arguments. The dual scan RUNS (pass 2 is
asked for every strip), the old file is copied aside as before, and M0, M1 and M2 are saved.
Up to helper 2026-11-20e the helper refused this with "mixed" before the calibration.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.dual_scan import session as D           # noqa: E402
from workflow.dual_scan import storage                 # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "tests" / "helpers" / "dual_sim_helper.py"
CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY, "i1pro3_conditions"})

needs_helper = pytest.mark.skipif(not (ROOT / "native" / "chromiq-chartread").exists(),
                                  reason="engine not built")


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


@needs_helper
@pytest.mark.parametrize("mode,code", [(D.MODE_ALWAYS, None), (D.MODE_M1_M2, "5")])
def test_a_new_dual_measurement_over_a_one_pass_measurement_runs(tmp_path, monkeypatch,
                                                                  mode, code):
    import tests.helpers.replay_tools as rt
    from tests.test_i1pro2_dual_scan_engine import _chart, _done, _swipe
    from ui.tabs.tab_measure import TabMeasure
    from workflow.measurement_session import MeasurementSession
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _steps = _chart(tmp_path)
    main = base.with_suffix(".ti3")
    # 1. the run's one-pass measurement (the REAL helper, no dual scan)
    with rt.ReplaySession(base, rp, extra_args=["-S"]) as s:
        _swipe(s)
        _swipe(s, reversed=True)
        _done(s)
    assert main.is_file() and storage.read_dual_record(main).dual is False
    old_text = main.read_text(encoding="latin-1")
    # 2. START: the plan (a NEW measurement: nothing continued) and the engine's arguments
    settings = _S({"i1pro3_conditions_beta": True, D.SETTING: True, D.MODE_SETTING: mode})
    plan = D.plan_for(settings, CAPS, "i1Pro 2", code, None)
    assert plan.dual, plan
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    fake = SimpleNamespace(_settings=settings, _ti1_path=base.with_suffix(".ti2"),
                           _dual_plan_now=lambda: plan,
                           _condition_dir_for=lambda p: cdir)
    p = SimpleNamespace(extra_args="-S" + (f" -F {code}" if code else ""),
                        ti1_path=fake._ti1_path, engine_condition_dir=cdir,
                        engine_dual_args=None, resume=False)
    TabMeasure._apply_dual_scan(fake, p)
    assert p.engine_dual_args and "-F" not in p.extra_args and "-r" not in p.extra_args
    # 3. the session guard copies the measurement aside, as the tab does
    guard = MeasurementSession(main, base.with_suffix(".ti2"))
    copy = guard.begin()
    assert copy is not None and copy.read_text(encoding="latin-1") == old_text
    # 4. the engine with exactly those arguments
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_TILE_S", "0.2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_PASS_S", "0.05")
    monkeypatch.setattr(rt, "HELPER", SIM)
    args = p.extra_args.split() + ["--condition-dir", str(cdir)] + list(p.engine_dual_args)
    with rt.ReplaySession(base, rp, extra_args=args) as s:
        for rev in (False, True):
            s.wait_event("strip_ready")
            i = s.event_index()
            s.send(cmd="swipe", reversed=rev)                  # pass 1 of 2
            s.wait_event("dual_pass", after=i)                 # pass 2 is asked for
            s.send(cmd="swipe", reversed=rev)
            s.wait_event("strip_read", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", timeout=10, after=i)
        s.finish()
    cond = [e for e in s.events if e.get("event") == "conditions"]
    assert cond and cond[0]["active"] is True and cond[0]["dual"] is True, cond
    assert not any(e.get("why") == "mixed" for e in cond)
    # M0, M1 and M2 saved; the old measurement is still in its copy
    from workflow import i1pro3_conditions as C
    rec = storage.read_dual_record(main)
    assert rec.dual and rec.scale == pytest.approx(1.156)
    assert C.condition_file(main, "M1") is not None and C.condition_file(main, "M2") is not None
    assert [(x.cond, x.usable) for x in C.choices_for(main)] == [
        ("M0", True), ("M1", True), ("M2", True)]
    assert copy.read_text(encoding="latin-1") == old_text
