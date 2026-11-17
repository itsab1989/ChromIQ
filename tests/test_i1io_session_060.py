# SPDX-License-Identifier: GPL-3.0-or-later
"""chromiq-i1io-session 0.6.0: the start-up of a table that has just been switched on.

The one recording of a cold start (S1, 14 Nov 2026), read byte by byte from its raw capture
file: after a1 a1 k2 u8 u8, a0 answered `:$a00111800B6`; then `;i02c` (accepted `:!i00C`
after 0.016 s, done `:$i00D9` after 3.167 s), s0, f4 x4 (00), s0, p0 (1102, 14), i1 (0.224 s),
s0. The tests below hold their OWN copy of that sequence (not the program's).
"""
from __future__ import annotations

import re
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "tools" / "i1io_session"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1io_part_c as pc  # noqa: E402
import i1io_part_c_sim as csim  # noqa: E402
import i1io_session as prog  # noqa: E402
import i1io_session_sim as sim_mod  # noqa: E402
import i1io_session_table as tbl  # noqa: E402
import test_i1io_part_c as TC  # noqa: E402
import test_i1io_session_tool as T  # noqa: E402

#: S1 as recorded (own copy): the opening of a cold table through the start-up's homing
S1_OPEN6 = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"]
S1_START_UP = [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022", ";p025", ";i12b",
               ";s022"]
S1_COLD = S1_OPEN6 + S1_START_UP
I0 = ";i02c"
ASK_COLD = "Type yes to send the start-up"


def _flat(text):
    return " ".join(text.split())


def cold(**kw):
    kw.setdefault("jitter", False)
    return sim_mod.SimTable(cold=True, **kw)


def run(tmp_path, sim=None, script=None, **kw):
    return T._run(tmp_path, sim or cold(), script=script, **kw)


def _home_only():
    """Part A after the start-up: run step 1 only (then end)."""
    return {"Run this step now?": "end"}


# ---- the line itself ---------------------------------------------------------------------------

def test_the_start_up_line_is_the_recorded_bytes():
    assert tbl.WIRE["start_up"] == bytes.fromhex("3b 69 30 32 63 0d") == b";i02c\r"
    assert tbl.START_UP_LINE == tbl.WIRE["start_up"]
    assert tbl.checksum_ok(";i02c")
    assert "S1 1.517" in tbl.RECORDED_AT["start_up"] and "3.167" in tbl.RECORDED_AT["start_up"]
    md = T._bytes_md_lines()
    assert md[";i02c"] == "3b 69 30 32 63 0d"


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
    import i1io_c_lines as cl
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(tbl.START_UP_LINE)
    with pytest.raises(tbl.ForbiddenLine):
        tbl.check_outgoing(tbl.START_UP_LINE)


def test_the_package_names_i0_only_in_the_allowed_places():
    for name in ("i1io_session.py", "i1io_part_c.py", "i1io_scan.py", "i1io_geometry.py",
                 "i1io_reader.py", "i1io_c_lines.py"):
        assert ";i02c" not in (PKG / name).read_text(encoding="utf-8"), name
    src = (PKG / "i1io_session_table.py").read_text(encoding="utf-8")
    assert src.count('_frame("i0")') == 1
    assert src.count('"start_up"') >= 1


# ---- the gate ------------------------------------------------------------------------------------

def _table(sim):
    return tbl.Table(sim_mod.SimTransport(sim))


def test_a_started_table_never_gets_the_start_up(tmp_path):
    for keys in (set(T.STEP_KEYS),):
        code, sim, log, con = T._choose(tmp_path, keys)
        assert I0 not in sim.received
    d = _table(sim_mod.SimTable())
    assert d.opening() == "warm"
    with pytest.raises(tbl.Doubt):
        d.run_cold_start()
    assert I0 not in d.t.table.received
    d2 = _table(sim_mod.SimTable())
    d2.opening()
    with pytest.raises(tbl.Doubt):
        d2._write(tbl.START_UP_LINE)
    assert I0 not in d2.t.table.received


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


def test_the_wire_refuses_the_start_up_unless_armed(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = T.FakeDev(cold=True)
    util, t = T._ftdi(dev)
    with pytest.raises(tbl.ForbiddenLine):
        t.write(tbl.START_UP_LINE)
    t.gate = lambda data: None           # part C's gate in place: still refused unarmed
    with pytest.raises(tbl.ForbiddenLine):
        t.write(tbl.START_UP_LINE)
    assert dev.sim.received == []
    t.start_up_armed = True
    with pytest.raises(sim_mod.SimViolation):    # armed: passes the wire (the simulator then
        t.write(tbl.START_UP_LINE)                # refuses it: i0 not right after a0)
    assert t.start_up_armed is False             # one shot


def test_the_start_up_over_the_ftdi_path(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = T.FakeDev(cold=True)
    util, t = T._ftdi(dev)
    s = prog.Session(tbl.Table(t), T.Script(dev.sim, script=_home_only()), simulated=True)
    assert s.go() == 0
    assert dev.sim.received == S1_COLD
    assert t.start_up_armed is False


# ---- whole sittings --------------------------------------------------------------------------------

def test_cold_start_then_all_of_part_a(tmp_path):
    code, sim, log, con = run(tmp_path)
    assert code == 0
    assert sim.received[:16] == S1_COLD
    assert sim.received[16:] == [x for k in T.STEP_KEYS for x in T._lines(k)]
    assert sim.received.count(I0) == 1
    assert "start-up (0.6.0): sent True; i0 took 3.167 s" in log
    assert "done True" in log
    # caps: part A plus the start-up
    assert len(sim.received) <= tbl.MAX_LINES + tbl.COLD_MAX_LINES


def test_cold_start_then_part_b(tmp_path):
    code, sim, log, con = T._run(tmp_path, cold(), script={prog.ASK_PART: "b"})
    assert code == 0, log[-3000:]
    assert sim.received[:16] == S1_COLD
    assert "done: b_end" in log and "done: close_after_end" in log
    assert sim.received[-3:] == [";s022", ";f02f", ";f32c"]
    assert sim.received.count(I0) == 1
    assert len(sim.received) <= tbl.B_MAX_LINES + tbl.COLD_MAX_LINES


def test_cold_start_then_part_c(tmp_path):
    sim = csim.CSimTable(cold=True, part_c=False)
    code, sim, log, con, res = TC.run_c(tmp_path, ["c1", "e1", "f"], sim=sim)
    assert sim.received[:16] == S1_COLD, sim.received[:20]
    verdicts = TC.verdicts(log)
    assert ("c1", "worked") in verdicts and ("e1", "worked") in verdicts, verdicts
    assert sim.received.count(I0) == 1
    assert not sim.violations


def test_the_person_sees_the_explanation_before_anything_moves(tmp_path):
    code, sim, log, con = run(tmp_path, script=_home_only())
    q = next(x for x in con.seen if x[0].startswith(ASK_COLD))
    assert q[1] == 6 and not q[3]           # asked after the six reading lines, nothing moving
    text = _flat(log)
    for needed in ("recorded ONCE", "We do not know what the arm does", "end positions",
                   "about 3 seconds", "1 to 8 seconds", "hands are away", "power switch",
                   "table is empty", "type i1profiler"):
        assert needed in text, needed
    # the questions afterwards, then the chosen part
    asked = [x[0] for x in con.seen]
    i = asked.index(prog.ASK_COLD_TRAVEL)
    assert asked[i + 1] == prog.ASK_COLD_SEEN and asked[i + 2] == prog.ASK_COLD_WRONG
    for x in con.seen[i:i + 3]:
        assert not x[3] and tbl.REST_GUARD.contains((round(x[2][0]), round(x[2][1])))
    assert "goes on with part A" in text


def test_something_wrong_in_the_start_up_ends_the_sitting(tmp_path):
    code, sim, log, con = run(tmp_path, script={prog.ASK_COLD_WRONG: "yes"})
    assert code == 1 and sim.received == S1_COLD
    code, sim, log, con = run(tmp_path, script={prog.ASK_COLD_WRONG: "not sure"})
    assert code == 1 and sim.received == S1_COLD


def test_i1profiler_instead_sends_nothing_more(tmp_path):
    code, sim, log, con = run(tmp_path, script={ASK_COLD: "i1profiler"})
    assert code == 1 and sim.received == S1_OPEN6
    assert "You chose to let i1Profiler start the table" in _flat(log)
    assert "Nothing was moved." in _flat(log)


def test_a_table_answering_neither_value_stops_as_before(tmp_path):
    sim = cold()
    sim.inject("a0_other", "a0")
    code, sim, log, con = run(tmp_path, sim)
    assert code == 2 and sim.received == S1_OPEN6


def test_the_start_up_runs_at_most_once_per_sitting(tmp_path):
    for script in ({prog.ASK_PART: "a"}, {prog.ASK_PART: "b"}):
        code, sim, log, con = run(tmp_path, script=script)
        assert sim.received.count(I0) == 1


# ---- the simulator's cold variants -------------------------------------------------------------------

def _ends_with_switch_off(log):
    return "switch the table off at its power switch" in _flat(log)


def test_a_late_start_up_stops_with_the_switch_off(tmp_path):
    code, sim, log, con = run(tmp_path, cold(i0_s=9.5))
    assert code == 2 and sim.received == S1_OPEN6 + [I0]
    t = _flat(log)
    assert "reported its start-up finished after 9.50 seconds" in t
    assert "accepts 1 to 8 seconds" in t and _ends_with_switch_off(log)
    assert "failure outside" in log


def test_an_early_start_up_stops_too(tmp_path):
    code, sim, log, con = run(tmp_path, cold(i0_s=0.4))
    assert code == 2 and sim.received == S1_OPEN6 + [I0]
    assert "after 0.40 seconds" in _flat(log) and _ends_with_switch_off(log)


def test_a_start_up_that_never_reports_done(tmp_path):
    sim = cold()
    sim.inject_at(6, "no_done")
    code, sim, log, con = run(tmp_path, sim)
    assert code == 2 and sim.received == S1_OPEN6 + [I0]
    t = _flat(log)
    assert "did not report that its start-up had finished within 15 seconds" in t
    assert "may still be moving" in t and _ends_with_switch_off(log)


def test_a_refused_start_up(tmp_path):
    sim = cold()
    sim.inject_at(6, "refuse", 1)
    code, sim, log, con = run(tmp_path, sim)
    assert code == 2 and sim.received == S1_OPEN6 + [I0]
    assert "RECV   " in log and ":#i01" in log           # the recorded form of a refusal
    t = _flat(log)
    assert "refused the start-up command (code 1)" in t and _ends_with_switch_off(log)
    assert "failure refused" in log


def test_a_start_up_answered_with_another_status(tmp_path):
    sim = cold()
    sim.inject_at(6, "status", 3)
    code, sim, log, con = run(tmp_path, sim)
    assert code == 2 and sim.received == S1_OPEN6 + [I0]
    assert "differently from the recording" in _flat(log) and _ends_with_switch_off(log)


@pytest.mark.parametrize("after", [(1102, 420), (1300, 20), (1102, -40)])
def test_the_arm_away_from_rest_after_the_start_up(tmp_path, after):
    code, sim, log, con = run(tmp_path, cold(i0_after=after))
    assert code == 2 and sim.received == S1_COLD[:14]      # through the p0, no homing
    t = _flat(log)
    assert f"Then the arm read X {after[0]}, Y {after[1]}, not at its resting place" in t
    assert "a line after it did not" in t and _ends_with_switch_off(log)
    assert "failure after" in log


@pytest.mark.parametrize("kind", ["late", "no_answer", "garbled", "bad_checksum", "wrong_cid",
                                  "stray", "status", "refuse", "long_line", "extra_line"])
def test_any_fault_on_any_line_of_the_start_up_sends_nothing_more(tmp_path, kind):
    for i in range(6, 16):
        sim = cold()
        sim.inject_at(i, kind, 30.0 if kind == "late" else 1.0)
        code, sim, log, con = run(tmp_path, sim, script=_home_only())
        if kind == "extra_line" and i in (13, 15):
            # a stray line after the last answer of a step is caught by the quiet check
            pass
        assert code == 2, (kind, i)
        assert sim.received == S1_COLD[:i + 1] or (kind == "extra_line"
                                                    and sim.received == S1_COLD[:i + 2]), \
            (kind, i, sim.received)
        assert _ends_with_switch_off(log), (kind, i)
        assert sim_mod.FAKE_SERIAL not in log


def test_a_lost_link_at_every_line_of_the_start_up(tmp_path):
    for i in range(6, 16):
        sim = cold()
        sim.inject_at(i, "unplug")
        code, sim, log, con = run(tmp_path, sim, script=_home_only())
        assert code == 2, i
        assert sim.received == S1_COLD[:i + 1], i
        t = _flat(log)
        assert "connection was lost during the start-up" in t, i
        assert _ends_with_switch_off(log), i
        if i in (6, 14):     # i0 or the homing written, its end never reported
            assert "may still be moving" in t, i


def test_ctrl_c_during_every_line_of_the_start_up(tmp_path):
    for i in range(6, 16):
        sim = cold()

        def hook(n, i=i):
            if n == i:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
        code, sim, log, con = run(tmp_path, sim, script=_home_only())
        assert code == 1, i
        # the line in flight finishes; nothing after it
        assert sim.received == S1_COLD[:i + 1], (i, sim.received)
        assert not sim.moving
        t = _flat(log)
        assert "You stopped the program" in t, i
        if i < 15:
            assert _ends_with_switch_off(log), i
            assert "The start-up lines that follow it were not all sent" in t, i


def test_ctrl_c_at_every_question_up_to_the_start_up(tmp_path):
    n = next(k for k, x in enumerate(run(tmp_path)[3].seen, 1) if x[0].startswith(ASK_COLD))
    for q in range(1, n + 1):
        code, sim, log, con = run(tmp_path, interrupt_at=q)
        assert code == 1
        assert I0 not in sim.received
        assert sim.received == S1_OPEN6[:len(sim.received)]


def test_ctrl_c_at_the_questions_after_the_start_up(tmp_path):
    seen = run(tmp_path)[3].seen
    n = [k for k, x in enumerate(seen, 1) if x[0] in (prog.ASK_COLD_TRAVEL, prog.ASK_COLD_SEEN,
                                                      prog.ASK_COLD_WRONG)]
    for q in n:
        code, sim, log, con = run(tmp_path, interrupt_at=q)
        assert code == 1 and sim.received == S1_COLD


# ---- caps -----------------------------------------------------------------------------------------

def test_the_caps_grow_only_when_the_start_up_ran():
    d = _table(sim_mod.SimTable())
    d.opening()
    assert d.cold_allowance == (0, 0)
    d = _table(cold())
    d.opening()
    d.run_cold_start()
    assert d.cold_allowance == (10, 2)
    assert (tbl.MAX_LINES, tbl.MAX_MOTIONS) == (110, 19)
    assert (tbl.B_MAX_LINES, tbl.B_MAX_MOTIONS) == (114, 33)
    assert (pc.C_MAX_LINES, pc.C_MAX_MOVES) == (8680, 3060)
    b = (PKG / "BYTES.md").read_text(encoding="utf-8")
    assert "part A then at most 120 lines and 21 movements, part B 124 and 35, part C 8690 and " \
           "3062" in _flat(b)


def test_the_part_cap_still_holds_with_the_start_up(tmp_path, monkeypatch):
    monkeypatch.setitem(tbl.PART_CAPS, "A", (14, 19))   # 6 + 10 needed; 14 + 10 allowed
    code, sim, log, con = run(tmp_path)
    assert sim.received[:16] == S1_COLD
    assert len(sim.received) <= 24
    assert "limit of lines" in log


# ---- questions at the start ---------------------------------------------------------------------

class _Q(prog.AutoConsole):
    def __init__(self, answers):
        super().__init__(lambda k, t: None)
        self.answers, self.asked = answers, []

    def ask(self, question, choices=("yes", "no")):
        self.asked.append(question)
        for k, a in self.answers.items():
            if k in question:
                return a
        return choices[0]

    def text(self, question):
        self.asked.append(question)
        return ""


def test_the_started_question_is_a_choice():
    assert prog.STARTED_CHOICES == ("yes", "no", "not sure", "stop")
    t = _flat(prog.ASK_STARTED)
    assert "i1Profiler is not needed at all" in t
    assert "whether i1Profiler still works normally" in t
    for ans, ok in (("yes", True), ("no", True), ("not sure", True), ("stop", False)):
        notes = []
        assert prog.pre_questions(_Q({"has i1Profiler connected": ans}), notes) is ok
        assert notes[-1] == ("i1Profiler connected since the table was switched on", ans)


def test_after_no_the_questions_ask_about_switching_on():
    ui = _Q({})
    notes = [("i1Profiler connected since the table was switched on", "no")]
    prog.touch_before_opening(ui, notes)
    assert prog.ASK_MINUTES_ON in ui.asked and prog.ASK_MOVED_ON in ui.asked
    assert prog.ASK_MINUTES not in ui.asked
    ui = _Q({})
    prog.touch_before_opening(ui, [("i1Profiler connected since the table was switched on",
                                    "yes")])
    assert prog.ASK_MINUTES in ui.asked and prog.ASK_MINUTES_ON not in ui.asked


def test_a_yes_at_the_start_on_a_cold_table_is_mentioned():
    for ans, said in (("yes", True), ("no", False)):
        sim = cold()
        lines = []
        con = T.Script(sim, script=_home_only())
        con.log = lambda k, t: lines.append((k, t))
        s = prog.Session(tbl.Table(sim_mod.SimTransport(sim)), con, simulated=True,
                         answers=[("i1Profiler connected since the table was switched on", ans)])
        assert s.go() == 0
        assert any(prog.COLD_FOUND_SAID_YES.replace("\n", " / ") == t for k, t in lines) is said


def test_the_end_asks_about_i1profiler_afterwards(tmp_path):
    code, sim, log, con = run(tmp_path, script=_home_only())
    assert "please tell us whether it works normally" in _flat(log)
    assert prog.ASK_COLD_START not in log
    code, sim, log, con = T._run(tmp_path, sim_mod.SimTable(), script=_home_only())
    assert "please tell us whether it works normally" not in _flat(log)


# ---- texts ---------------------------------------------------------------------------------------

def test_no_em_dash_and_no_promise_in_the_new_texts():
    texts = [prog.COLD_OFFER, prog.ASK_COLD, prog.COLD_RUNNING, prog.COLD_DONE, prog.COLD_WAY_OUT,
             prog.COLD_NOT_STARTED, prog.ASK_STARTED, prog.COLD_TEXT, prog.COLD_FOUND,
             prog.ASK_COLD_TRAVEL, prog.ASK_COLD_SEEN, prog.ASK_COLD_WRONG, prog.COLD_GO_ON,
             prog.COLD_I1PROFILER_AFTER, tbl.COLD_STEP.explain, tbl.COLD_STEP.beyond]
    for t in texts:
        assert "—" not in t
        for bad in ("safe", "guarantee", "cannot harm", "harmless", "never moves"):
            assert bad not in t.lower(), (bad, t)


def test_the_plan_shows_the_start_up(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert prog.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert ";i02c" in out and "3b 69 30 32 63 0d" in out
    assert "1.00..8.00 s" in out and "recorded once 3.167 s" in out


def test_the_version_is_0_6_0():
    assert tbl.TOOL_VERSION == "0.6.0"
    assert "0.6.0" in prog.TITLE
    assert (PKG / "BYTES.md").read_text(encoding="utf-8").splitlines()[0].count("0.6.0") == 1
    assert (PKG / "README.md").read_text(encoding="utf-8").splitlines()[0].count("0.6.0") == 1
    readme = _flat((PKG / "README.md").read_text(encoding="utf-8"))
    for needed in ("What is new in 0.6.0", "Do **not** open i1Profiler", "--sim cold",
                   "recorded **once**"):
        assert needed in readme, needed
