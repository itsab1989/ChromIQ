"""X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan (Preferences > Beta):
with the option OFF, no code of the feature runs in the Measure tab.

The Measure tab and the measure manager reach the feature at exactly four
points: the folder handed to the engine (`_condition_dir_for`), the
housekeeping at the end of a session (`_prune_condition_pairs`), averaging
(`_average_the_conditions`) and the engine's "conditions" event (only ever
sent when the folder was given). This test

* lists those points from the source, so a fifth one cannot be added without
  being named here;
* turns every function of ``workflow.i1pro3_conditions`` except the switch
  itself into a trap, and drives each point with the option off: nothing
  is called, nothing is written, and the helper is started with today's
  command line.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow import i1pro3_conditions as C

ROOT = Path(__file__).resolve().parent.parent


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def test_the_measure_tab_reaches_the_feature_at_four_named_points():
    tab = (ROOT / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    mm = (ROOT / "workflow/measure_manager.py").read_text(encoding="utf-8")
    users = set()
    for name, src in (("tab_measure", tab), ("measure_manager", mm)):
        defs = [(m.start(), m.group(1)) for m in
                re.finditer(r"^    def (\w+)\(", src, re.M)]
        for m in re.finditer(r"i1pro3_conditions", src):
            owner = [d for pos, d in defs if pos < m.start()]
            users.add(f"{name}.{owner[-1] if owner else '<module>'}")
    assert users == {
        "tab_measure._average_the_conditions",
        "tab_measure._prune_condition_pairs",
        "tab_measure._condition_dir_for",
        "measure_manager.start",
        # 4.3.49: strips with the main condition only (each asks the switch
        # first, through _fill_main; test_off_none_of_the_points_runs_...)
        "tab_measure._fill_main",
        "tab_measure._fill_strips",
        "tab_measure._fill_note_text",
        "tab_measure._fill_guided_strips",
        # 4.3.50 (A10): the condition files' provenance, after asking the switch
        "tab_measure._stamp_provenance_at_end",
    }, users
    # the manager uses it only where the folder was given (`engine_condition_dir`)
    for m in re.finditer(r"i1pro3_conditions", mm):
        before = mm[max(0, m.start() - 400):m.start()]
        assert "params.engine_condition_dir is not None" in before


@pytest.fixture
def traps(monkeypatch):
    called: list = []
    for name in dir(C):
        obj = getattr(C, name)
        if (callable(obj) and not isinstance(obj, type)
                and getattr(obj, "__module__", "") == C.__name__
                and name != "stored_value"):
            monkeypatch.setattr(
                C, name, lambda *a, _n=name, **k: called.append(_n))
    return called


def test_off_none_of_the_points_runs_the_feature(tmp_path, traps, qapp):
    from ui.tabs.tab_measure import TabMeasure
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    fake = SimpleNamespace(_settings=_S({C.SETTING: False}),
                           _ti1_path=run_dir / "P.ti1",
                           _is_verification_run=lambda: False,
                           _log=SimpleNamespace(appendPlainText=traps.append))
    p = SimpleNamespace(extra_args="", ti1_path=run_dir / "P.ti1")
    assert TabMeasure._condition_dir_for(fake, p) is None
    TabMeasure._prune_condition_pairs(fake)
    TabMeasure._average_the_conditions(fake, run_dir / "P.ti3", [], "mean")
    # 4.3.49: the fill note and the guide's list
    fake._engine_selected = lambda: True
    fake._fill_main = lambda: TabMeasure._fill_main(fake)
    fake._fill_strips = lambda main=None: TabMeasure._fill_strips(fake, main)
    assert TabMeasure._fill_main(fake) is None
    assert TabMeasure._fill_strips(fake) == []
    assert TabMeasure._fill_note_text(fake) == ("", "")
    assert TabMeasure._fill_guided_strips(fake, ["B"]) == ["B"]
    assert traps == []
    assert sorted(p.name for p in tmp_path.rglob("*")) == ["P", "run1", "runs"]


def test_off_the_helper_gets_todays_command_line(tmp_path, monkeypatch):
    from tests.test_i1pro3_conditions_beta_option import _args
    on = _args(tmp_path, monkeypatch, tmp_path / "conditions")
    off = _args(tmp_path, monkeypatch, None)
    assert "--condition-dir" in on and "--condition-dir" not in off
    i = on.index("--condition-dir")
    assert on[:i] + on[i + 2:] == off
