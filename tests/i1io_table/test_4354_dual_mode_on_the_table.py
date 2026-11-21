"""4.3.54: "when the dual scan runs" governs the i1iO 2 table exactly as a hand measurement.

The table has no copy of the rule: the Measure tab's START (`TabMeasure._table_dual_setup`) asks
`workflow.dual_scan.session.plan_for`, the same function the hand path asks, and hands the
window `dual=` (a DualSetup, or None) and the chart reader's arguments. The window and the job
never read the option. Proved here on the simulated table:

* "only for M1 or M2" with M0 chosen: no DualSetup, -F taken out of the arguments, and the
  whole measurement sends the table exactly the lines a measurement with the dual scan OFF
  sends (rows and patch by patch), with the same reader arguments;
* with M1 chosen, the DualSetup is the one "always" gives, and the table lines are the same;
* a continued measurement keeps the kind it was started with.
"""
from __future__ import annotations

import pytest

from tests.i1io_table.test_dual_table import long_sheet
from tests.i1io_table.test_dual_table_window import CAPS, _tab
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (fixture)
from ui import i1io_table_window as W
from workflow.dual_scan import session as D

STRIP = ["-v", "-c", "1", "-S", "chart"]
SPOT = ["-v", "-c", "1", "-S", "-p", "chart"]


def _set(settings, on, mode=D.MODE_M1_M2):
    from workflow import i1pro3_conditions as ic
    settings.set(ic.SETTING, on)
    settings.set(D.SETTING, on)
    settings.set(D.MODE_SETTING, mode)


def _row_choice_only(settings, code, main=None):
    from types import SimpleNamespace
    from ui.tabs.tab_measure import TabMeasure
    t = SimpleNamespace(_settings=settings, _dual_caps=lambda: frozenset(CAPS),
                        _measurement_to_continue=lambda: main,
                        _measure_filter_code=lambda: code, _current_mode=lambda: "manual")
    return TabMeasure._table_row_is_choice_only(t)


@pytest.mark.parametrize("code", [None, "n"])
def test_m0_chosen_gives_the_table_no_dual_setup_and_no_minus_f(settings, code):
    _set(settings, True)
    f, shown = _tab(settings, CAPS, code=code)
    assert f() is None and shown == []
    assert _row_choice_only(settings, code) is True
    _set(settings, False)


@pytest.mark.parametrize("code", ["5", "u"])
def test_m1_or_m2_chosen_gives_the_dual_setup_of_always(settings, code):
    _set(settings, True, D.MODE_M1_M2)
    b = _tab(settings, CAPS, code=code)[0]()
    _set(settings, True, D.MODE_ALWAYS)
    a = _tab(settings, CAPS, code=code)[0]()
    assert b is not None and a is not None and b == a
    assert _row_choice_only(settings, code) is False
    _set(settings, False)


def test_a_continued_table_measurement_keeps_its_kind(settings, tmp_path):
    from tests.test_4354_dual_scan_mode import _main
    _set(settings, True)
    (tmp_path / "s").mkdir()
    (tmp_path / "d").mkdir()
    single, dual = _main(tmp_path / "s", dual=False), _main(tmp_path / "d", dual=True)
    assert _tab(settings, CAPS, code="5", main=single)[0]() is None
    assert _row_choice_only(settings, "5", main=single) is True
    setup = _tab(settings, CAPS, code=None, main=dual)[0]()
    assert setup is not None and setup.chosen == "M0"
    _set(settings, False)


def _whole(qtbot, monkeypatch, tmp_path, settings, args, dual):
    orig = W.TableMeasureWindow.__init__

    def init(self, *a, **k):
        k["dual"] = dual
        orig(self, *a, **k)
    monkeypatch.setattr(W.TableMeasureWindow, "__init__", init)
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=long_sheet(), args=args)
    assert p.drive_until("end_of_session") == "end_of_session"
    p.press("Save and stop")
    assert saved
    out = (list(sim.sim.received), list(win._chart_args), sim.helper.reads,
           sim.helper.calibrations)
    assert sim.sim.violations == []
    win.close()
    monkeypatch.setattr(W.TableMeasureWindow, "__init__", orig)
    return out


@pytest.mark.parametrize("args", [STRIP, SPOT], ids=["rows", "patch_by_patch"])
def test_m0_chosen_is_line_for_line_the_table_with_the_dual_scan_off(
        qtbot, monkeypatch, tmp_path, settings, args):
    from ui.tabs.tab_measure import TabMeasure
    # the dual scan OFF: the filter row is greyed on a table chart, so no -F reaches the args
    _set(settings, False)
    off = _whole(qtbot, monkeypatch, tmp_path / "off", settings, list(args), None)
    # "only for M1 or M2" with "M0: no filter" switched on in the row
    _set(settings, True)
    setup = _tab(settings, CAPS, code="n")[0]()
    with_f = args[:-1] + ["-F", "n", args[-1]]
    assert _row_choice_only(settings, "n")
    b = _whole(qtbot, monkeypatch, tmp_path / "b", settings,
               TabMeasure._args_without_filter(with_f), setup)
    _set(settings, False)
    assert setup is None
    assert b[1] == off[1], "the same reader arguments"
    assert b[0] == off[0], "the same lines to the table, line for line"
    assert b[2:] == off[2:]
    assert len(off[0]) > 50 and off[2] > 0, "a whole measurement was driven"
    assert not any(ln.startswith(";m2") and int(ln[11:15], 16) == 132 for ln in off[0]), \
        "no dual row"
