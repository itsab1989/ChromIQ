"""Ported from the tester program chromiq-i1io-session 0.6.0: ``tests/test_i1io_session_060.py`` (branch
tester/i1io-session-0.6.0, 84d30fa1d), the tests that need only the modules that moved into
``workflow/i1io/table/`` and the simulators in ``tests/i1io_table/``. Test bodies are verbatim;
only this header and the imports are new (test_guarantees_in_the_app.py says what stayed).
No hardware: the simulated table and fake readers only.
"""
from __future__ import annotations

import ast  # noqa: F401
import hashlib  # noqa: F401
import inspect  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import plistlib  # noqa: F401
import re  # noqa: F401
import signal  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import zipfile  # noqa: F401
from pathlib import Path  # noqa: F401

import pytest  # noqa: F401

from tests.i1io_table import part_c_sim as csim  # noqa: F401
from tests.i1io_table import session_sim as sim_mod  # noqa: F401
from tests.i1io_table._moved import PKG, ROOT  # noqa: F401
from workflow.i1io.table import geometry as geo  # noqa: F401
from workflow.i1io.table import lines as cl  # noqa: F401
from workflow.i1io.table import reader as rd  # noqa: F401
from workflow.i1io.table import scan as sc  # noqa: F401
from workflow.i1io.table import session_table as tbl  # noqa: F401


S1_OPEN6 = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"]


S1_START_UP = [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022", ";p025", ";i12b",
               ";s022"]


S1_COLD = S1_OPEN6 + S1_START_UP


I0 = ";i02c"


def cold(**kw):
    kw.setdefault("jitter", False)
    return sim_mod.SimTable(cold=True, **kw)


def test_the_start_up_step_is_exactly_s1():
    lines = [tbl.WIRE[k].decode().rstrip("\r") for k in tbl.step_lines(tbl.COLD_STEP)]
    assert lines == S1_START_UP
    assert tbl.COLD_STEP.needs == ("cold",) and tbl.COLD_STEP.leaves == "warm"
    assert (tbl.COLD_MAX_LINES, tbl.COLD_MAX_MOTIONS) == (10, 2)
    # its window: recorded once 3.167 s; 1.0 to 8.0 s, waits at most 15 s
    assert tbl.TIME_WINDOW["start_up"] == (1.0, 8.0)
    assert tbl.MOVE_TIMEOUT["start_up"] == 15.0
    assert tbl.TIME_WINDOW["start_up"][0] < 3.167 < tbl.TIME_WINDOW["start_up"][1]
    # the position read after it: the box of every first homing
    assert ("p0", "START_GUARD", "right before the homing") in tbl.COLD_STEP.ops


def test_the_start_up_line_is_in_no_step_of_any_part():
    for s in tbl.ALL_STEP_DEFS:
        assert "start_up" not in tbl.step_lines(s), s.key
    for part, lines in tbl.PART_LINES.items():
        assert tbl.START_UP_LINE not in lines, part
    from workflow.i1io.table import lines as cl
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(tbl.START_UP_LINE)
    with pytest.raises(tbl.ForbiddenLine):
        tbl.check_outgoing(tbl.START_UP_LINE)


def _table(sim):
    return tbl.Table(sim_mod.SimTransport(sim))


def test_the_start_up_only_inside_its_step_and_only_once():
    d = _table(cold())
    assert d.opening() == "cold"
    with pytest.raises(tbl.Doubt):       # not armed: outside the step
        d._write(tbl.START_UP_LINE)
    d = _table(cold())
    d.opening()
    d.run_cold_start()
    assert d.cold_done and d.state == "warm"
    assert d.t.table.received == S1_COLD
    with pytest.raises(tbl.Doubt):
        d.run_cold_start()
    d.closed_reason = None
    with pytest.raises(tbl.Doubt):
        d._start_up()
    assert d.t.table.received.count(I0) == 1


def _armed(d, state, sent=False):
    d.state, d.start_up_sent, d._start_up_armed = state, sent, True
    d.current_step = tbl.COLD_STEP
    d.closed_reason = None


def test_the_write_gate_checks_each_condition_itself():
    for state, sent, armed in (("warm", False, True), ("cold", True, True), ("cold", False, False)):
        d = _table(cold())
        d.opening()
        _armed(d, state, sent)
        d._start_up_armed = armed
        with pytest.raises(tbl.Doubt) as e:
            d._write(tbl.START_UP_LINE)
        assert "the start-up line outside the start-up step" in str(e.value), (state, sent, armed)
        assert I0 not in d.t.table.received


def test_the_start_up_and_its_runner_refuse_by_their_own_check():
    d = _table(cold())
    d.opening()
    d.run_cold_start()
    d.closed_reason = None
    with pytest.raises(tbl.Doubt) as e:
        d._start_up()
    assert "not just switched on, or a second time" in str(e.value)
    d.closed_reason = None
    with pytest.raises(tbl.Doubt) as e:
        d.run_cold_start()
    assert str(e.value) == "the start-up asked for out of order (a bug)"
    assert d.t.table.received.count(I0) == 1


def test_the_simulators_own_cold_rules_hold_in_part_c_mode():
    def feed(sim, lines):
        for ln in lines:
            sim.receive((ln + "\r").encode())
            sim.clock += 0.5
    sim = csim.CSimTable(cold=True, part_c=True)
    with pytest.raises(sim_mod.SimViolation, match="not right after a0"):
        feed(sim, S1_OPEN6[:5] + [I0])
    sim = csim.CSimTable(cold=False, part_c=True)
    with pytest.raises(sim_mod.SimViolation, match="not just switched on"):
        feed(sim, sim_mod.REC_OPEN + [I0])
    sim = csim.CSimTable(cold=True, part_c=True)
    with pytest.raises(sim_mod.SimViolation, match="before the start-up"):
        feed(sim, S1_OPEN6 + [";s022"])

