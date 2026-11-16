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
    tmp_path.mkdir(parents=True, exist_ok=True)
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


ALL_STAGES = ["c1", "c2", "e1", "c3", "c4", "d1", "d2", "d3", "e2", "e3", "d4", "f"]
FIRST = ["c1", "c2", "e1", "c3", "c4", "f"]
P0 = ";p025"


REAL_FAKE_READERS = csim.FakeReaders


def readers(spot=None, scan=None, problem=None):
    return lambda s, lg: REAL_FAKE_READERS(s, lg, spot_faults=spot, scan_faults=scan,
                                           problem=problem)


def screen(con):
    return "\n".join(con.said)


def check_truthful(sim, con, log):
    """The end text says only what the table's state really is."""
    text = screen(con)
    last = sim.received[-1][1:3] if sim.received else ""
    moving = sim.m2_pending is not None or (sim.moving and last in ("m0", "m1", "m2", "i1"))
    if moving:
        assert ("SWITCH THE TABLE OFF" in text or "never reported that its last movement" in text
                or "may still be moving" in text), text[-1500:]
    if "at its resting place, held when last checked" in text.split("\n\n")[-1] or \
            text.rstrip().endswith("held when last checked."):
        pass
    tail = text[text.rfind("\n\n"):] if "\n\n" in text else text
    for para in con.said[-6:]:
        if "at its resting place, held when last checked" in para:
            assert tbl.REST_GUARD.contains((round(sim.pos[0]), round(sim.pos[1]))), para
            assert not moving
    del tail


END_QUESTIONS = ("Did you hear anything unusual", "Had the table been switched off",
                 "Which lights are on", "If you have seen it", "Did anything else surprise")


def check_no_question_while_moving(con):
    """No question of a stage or of the menu while the arm moves or a scan move waits (the
    report questions at the very end may come after a stop, when nothing more is sent)."""
    for q, n, pos, moving, free, pending in con.seen:
        if q.startswith(END_QUESTIONS):
            continue
        assert not moving and not pending, q


def check_allow_list(sim):
    for line in sim.received:
        cl.classify((line + "\r").encode("ascii"))


# ---- whole sittings -------------------------------------------------------------------------

def test_a_whole_sitting_runs_every_stage_and_keeps_every_rule(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ALL_STAGES)
    assert code == 0 and sim.violations == []
    assert verdicts(log) == [(k, "worked") for k in ALL_STAGES]
    check_allow_list(sim)
    check_no_question_while_moving(con)
    check_truthful(sim, con, log)
    assert sim.free_arm is False and tbl.REST_GUARD.contains((round(sim.pos[0]),
                                                              round(sim.pos[1])))
    assert sim.mode == "00"
    # one zip with the log and the results; nothing from the table's memory in it
    z = tmp_path / "log-results.zip"
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        assert "log.txt" in names
        assert "log-results/summary.json" in names
        assert any(n.endswith("p1_row1.cut.ti3") for n in names)
        assert "log-results/spot_readings.ti3" in names
        assert "log-results/strip_readings.ti3" in names
        blob = b"".join(zf.read(n) for n in names)
    assert sim_mod.FAKE_SERIAL.encode() not in blob
    assert str(Path.home()).encode() not in blob


def test_the_part_c_gate_asks_about_part_b_and_a_no_sends_nothing(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c1"], script={"Have you already run part B": "no"})
    assert sim.received == []
    assert prog.C_GATE_REFUSED in screen(con)
    assert not (tmp_path / "log-results").exists()


def test_the_opening_already_goes_through_part_c_s_gate(tmp_path, monkeypatch):
    seen = []
    real = cl.classify

    def spy(line):
        seen.append(bytes(line))
        return real(line)
    monkeypatch.setattr(cl, "classify", spy)
    code, sim, log, con, res = run_c(tmp_path, [])
    assert [b.decode().rstrip("\r") for b in seen] == sim.received == sim_mod.REC_OPEN


def test_every_stage_explains_itself_its_risk_and_its_dependency_before_the_yes(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ALL_STAGES)
    text = screen(con)
    for st in pc.STAGES:
        i = text.index(f"Stage {st.key.upper()}: {st.title}")
        j = text.index(f"Stage {st.key.upper()} worked")
        part = text[i:j]
        assert st.explain[:60] in part.replace("\n", " ") or st.explain[:40] in part
        assert "Risk, as we judge it" in part
        assert "It depends on" in part


def test_a_repeated_stage_has_its_own_results_folder(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c2", "c2", "c2", "c2"])
    assert verdicts(log) == [("c2", "worked")] * 3          # its cap: 3 runs
    assert sorted(p.name for p in res.iterdir() if p.is_dir()) == ["c2-1", "c2-2", "c2-3"]


# ---- the readers fail ----------------------------------------------------------------------

def test_no_instrument_found_fails_cleanly_and_the_sitting_goes_on(tmp_path):
    code, sim, log, con, res = run_c(
        tmp_path, ["c1", "d1", "f"],
        readers=readers(problem="macOS lists no i1Pro 2 (USB 0971:2000)."))
    assert verdicts(log) == [("c1", "failed cleanly (instrument)"), ("d1", "worked"),
                             ("f", "worked")]
    assert sim.violations == []
    assert "macOS lists no i1Pro 2" in screen(con)


@pytest.mark.parametrize("fault,stage", [({"empty": True}, "c2"), ({"read_fails_at": "A1"}, "c2"),
                                         ({"no_instrument": True}, "c2"),
                                         ({"cal_fails": True}, "c2"),
                                         ({"read_fails_at": "A5"}, "c4"),
                                         ({"empty": True}, "c3")])
def test_a_spot_reader_failure_is_a_clean_failure_and_the_next_stage_runs(tmp_path, fault, stage):
    code, sim, log, con, res = run_c(tmp_path, [stage, "d1", "f"], readers=readers(spot=fault))
    v = verdicts(log)
    assert v[0][0] == stage and v[0][1].startswith("failed cleanly"), v
    assert ("d1", "worked") in v or ("f", "worked") in v, v
    assert sim.violations == []
    check_truthful(sim, con, log)
    check_no_question_while_moving(con)


@pytest.mark.parametrize("fault", [{"not_ready": True}, {"dead": True}, {"lights_err": True},
                                   {"no_instrument": True}])
def test_an_instrument_not_ready_never_gets_a_scan_move(tmp_path, fault):
    code, sim, log, con, res = run_c(tmp_path, ["e1", "c2"], readers=readers(scan=fault))
    assert not any(line.startswith(";m2") for line in sim.received)
    v = verdicts(log)
    assert v[0][0] == "e1" and v[0][1].startswith("failed cleanly"), v
    assert sim.violations == []
    assert sim.m2_pending is None


@pytest.mark.parametrize("fault", [{"no_lamp": True}, {"dies_at_fire": True}])
def test_a_failure_after_the_scan_move_says_switch_the_table_off_and_leaves_a_marker(tmp_path,
                                                                                     fault):
    code, sim, log, con, res = run_c(tmp_path, ["e1", "c2"], readers=readers(scan=fault))
    assert code == 2
    assert "SWITCH THE TABLE OFF" in screen(con)
    markers = list(res.rglob(sc.PENDING_MARKER))
    assert markers and "SWITCH THE TABLE OFF" in markers[0].read_text()
    # nothing at all after the scan move's own two lines
    last_m2 = max(i for i, line in enumerate(sim.received) if line.startswith(";m2"))
    assert sim.received[last_m2 + 1:] == [cl.C_FIXED["scan_a3"].decode().rstrip("\r"),
                                          cl.C_FIXED["scan_c3"].decode().rstrip("\r")]
    assert verdicts(log)[-1] == ("e1", "stopped")
    assert (tmp_path / "log-results.zip").exists()


def test_the_lamp_ignored_by_the_table_is_also_pending(tmp_path):
    sim = csim.CSimTable(part_c=False)
    sim.c_faults["lamp_ignored"] = True
    code, sim, log, con, res = run_c(tmp_path, ["e1"], sim=sim)
    assert code == 2 and "SWITCH THE TABLE OFF" in screen(con)


# ---- every fault at every line, every Ctrl-C ----------------------------------------------

FAULTS = ("no_answer", "no_done", "late", "bad_checksum", "garbled", "status", "stray",
          "unplug", "refuse", "slow_motion")


def _clean_run(tmp_path, stages):
    code, sim, log, con, res = run_c(tmp_path / "clean", stages)
    assert code == 0 and sim.violations == []
    return sim.received, len(con.seen)


@pytest.mark.parametrize("kind", FAULTS)
def test_any_fault_at_any_line_of_the_first_stages_keeps_every_rule(tmp_path, kind):
    lines, _ = _clean_run(tmp_path, FIRST)
    for i in range(len(lines)):
        sim = csim.CSimTable(part_c=False)
        sim.inject_at(i, kind, 30.0 if kind == "late" else 1.0)
        code, sim, log, con, res = run_c(tmp_path / f"{kind}{i}", FIRST, sim=sim)
        assert sim.violations == [], (kind, i, lines[i], sim.violations)
        assert "SimViolation" not in log, (kind, i)
        check_no_question_while_moving(con)
        check_truthful(sim, con, log)
        if code == 2:
            # after the fault only position reads (what a stage reads before it decides), and
            # on the scan path the two lines that belong to a scan move already written
            after = sim.received[i + 1:]
            scan_path = [cl.C_FIXED[k].decode().rstrip("\r") for k in ("scan_a3", "scan_c3")]
            if lines[i].startswith(";m2") or lines[i] == scan_path[0]:
                rest = scan_path if lines[i].startswith(";m2") else scan_path[1:]
                while after and rest and after[0] == rest[0]:     # a dead link may cut it
                    after, rest = after[1:], rest[1:]
            assert all(x == P0 for x in after), (kind, i, sim.received[i:])
        assert sim.received[:i + 1] == lines[:i + 1]
        assert (tmp_path / f"{kind}{i}" / "log-results.zip").exists()


def test_ctrl_c_at_any_line_of_the_first_stages_sends_nothing_more(tmp_path):
    import signal
    lines, _ = _clean_run(tmp_path, FIRST)
    for i in range(len(lines)):
        sim = csim.CSimTable(part_c=False)

        def hook(n, i=i):
            if n == i:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
        code, sim, log, con, res = run_c(tmp_path / f"c{i}", FIRST, sim=sim)
        assert sim.violations == [], (i, sim.violations)
        assert code in (0, 1), i
        assert sim.received[:i + 1] == lines[:i + 1]
        extra = sim.received[i + 1:]
        if lines[i].startswith(";m2"):
            # the scan move always gets its two lines and its fire; then nothing
            assert extra == [cl.C_FIXED["scan_a3"].decode().rstrip("\r"),
                             cl.C_FIXED["scan_c3"].decode().rstrip("\r")], (i, extra)
            assert sim.m2_pending is None and sim.scan_moves
        elif lines[i] in (cl.C_FIXED["scan_a3"].decode().rstrip("\r"),):
            assert extra == [cl.C_FIXED["scan_c3"].decode().rstrip("\r")], (i, extra)
        else:
            assert extra == [], (i, lines[i], extra)
        assert not sim.moving and sim.m2_pending is None
        check_truthful(sim, con, log)


def test_ctrl_c_at_every_question_of_the_first_stages_sends_nothing_more(tmp_path):
    lines, n_questions = _clean_run(tmp_path, FIRST)
    for n in range(1, n_questions + 1):
        sim = csim.CSimTable(part_c=False)
        code, sim, log, con, res = run_c(tmp_path / f"q{n}", FIRST, sim=sim, interrupt_at=n)
        assert sim.violations == [], n
        assert sim.received == lines[:len(sim.received)], n
        assert not sim.moving and sim.m2_pending is None
        if len(sim.received) < len(lines):
            assert code == 1, n
        check_truthful(sim, con, log)
