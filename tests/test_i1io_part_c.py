# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""chromiq-i1io-session 0.5.0, part C: READING with the instrument on the table.

Everything here runs on the SIMULATED table (its own copy of part C's rules, raising
SimViolation the moment one is broken) with FAKE spot and strip readers. No hardware.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_session"
sys.path.insert(0, str(PKG))

import i1io_c_lines as cl  # noqa: E402
import i1io_geometry as geo  # noqa: E402
import i1io_part_c as pc  # noqa: E402
import i1io_part_c_sim as csim  # noqa: E402
import i1io_scan as sc  # noqa: E402
import i1io_session as prog  # noqa: E402
import i1io_session_sim as sim_mod  # noqa: E402
import i1io_session_table as tbl  # noqa: E402


class CScript(prog.AutoConsole):
    """Part C chosen, the gate answered, stages chosen in the order of *stages* (then end).
    Every question is recorded with the simulator's state at that moment."""

    def __init__(self, sim, stages=(), script=None, **kw):
        super().__init__(lambda k, t: None, script=script, **kw)
        self.sim = sim
        self.stages = list(stages)
        self.seen = []
        self.said = []

    def say(self, text=""):
        self.said.append(text)
        super().say(text)

    def _record(self, q):
        self.seen.append((q, len(self.sim.received), tuple(self.sim.pos), self.sim.moving,
                          self.sim.free_arm, self.sim.m2_pending is not None))

    def ask(self, question, choices=("yes", "no")):
        self._record(question)
        if question == prog.ASK_PART:
            self._maybe_interrupt()
            self.log("ASK", f"{question} -> c (automatic)")
            return "c"
        if question.startswith("Which stage now?"):
            self._maybe_interrupt()
            while self.stages:
                k = self.stages.pop(0)
                if k in choices:
                    self.log("ASK", f"{question} -> {k} (automatic)")
                    return k
                self.log("ASK", f"{question}: {k} not offered ({choices})")
            return "end"
        return super().ask(question, choices)

    def text(self, question):
        self._record(question)
        return super().text(question)


def run_c(tmp_path, stages, sim=None, script=None, readers=None, sheet=None, **kw):
    """One simulated part C sitting. Returns (code, sim, log text, console, results folder)."""
    sim = sim or csim.CSimTable(part_c=False)
    con = CScript(sim, stages, script=script, **kw)
    log = tmp_path / "log.txt"
    argv = ["--auto", "--log", str(log)]
    if sheet:
        argv += ["--sheet", str(sheet)]
    orig = csim.FakeReaders
    if readers is not None:
        csim.FakeReaders = lambda s, lg: readers(s, lg)
    try:
        code = prog.main(argv, sim_table=sim, console=con)
    finally:
        csim.FakeReaders = orig
    return code, sim, log.read_text(encoding="utf-8"), con, tmp_path / "log-results"


def blocks(text):
    out = []
    for ln in text.splitlines():
        if ln.startswith("RESULT"):
            j = json.loads(ln[ln.index("{"):])
            if j and "verdict" in j:
                out.append(j)
    return out


def verdicts(text):
    return [(b["stage"], b["verdict"]) for b in blocks(text)]


# ---- a first whole sitting ---------------------------------------------------------------

def test_the_first_stages_work_end_to_end(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c1", "c2", "e1", "c3", "c4"])
    assert sim.violations == []
    assert verdicts(log) == [("c1", "worked"), ("c2", "worked"), ("e1", "worked"),
                             ("c3", "worked"), ("c4", "worked")], log[-3000:]
    assert code == 0
