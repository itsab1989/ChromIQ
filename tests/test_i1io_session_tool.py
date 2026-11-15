"""THE i1iO SESSION TEST PROGRAM 0.3.0 SENDS ONLY THE SIXTEEN RECORDED LINES OF BYTES.md,
ONLY INSIDE ITS FIXED STEPS, EACH AFTER THE PERSON'S YES, WITHIN HARD CAPS, AND STOPS ON ANY
DOUBT.

`tools/i1io_session/` is a standalone program for the one tester who owns an i1iO 2 (issue
#129), built after the owner's ruling of 15 Nov 2026 (recorded commands with recorded
parameters, also from a start close to a recorded one; nothing of very high risk). These tests
hold its claims: the allow-list and BYTES.md agree byte for byte; every write on every path,
with every injected fault, stop or Ctrl-C, is in that list and in the simulator's own copy of
the steps; the caps hold per step and per session; any fault ends everything; the person is
never asked anything while the arm is out; the serial never reaches the log. No real USB is
used anywhere: the simulator and a fake pyusb device.
"""
from __future__ import annotations

import ast
import re
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_session"
sys.path.insert(0, str(PKG))

import i1io_session_table as tbl  # noqa: E402
import i1io_session_sim as sim_mod  # noqa: E402
import i1io_session as prog  # noqa: E402

RECORDED = {";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034", ";s022",
            ";f42b", ";p025", ";i12b", ";f02f", ";f32c", ";m0044e00fa012c0e",
            ";m003e805dc012c06", ";m0044e05da012c0b", ";m009cb05da012cda", ";f12e"}
FORBIDDEN_IDS = ("i0", "m1", "m2", "c3", "c4", "d1", "a3", "p1")
OPEN = sim_mod.REC_OPEN
STEP_KEYS = ("home", "near", "straight", "across", "free", "close")
PROGRAM_FILES = ("i1io_session_table.py", "i1io_session.py", "i1io_session_sim.py")


def _bytes_md_lines():
    text = (PKG / "BYTES.md").read_text(encoding="utf-8")
    section = text.split("## Lines to the table", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| (\d+) \| `([^`]+)` \| `([0-9a-f ]+)` \|", section, re.M)
    return {line: hx for _, line, hx in rows}


def _source(name):
    return (PKG / name).read_text(encoding="utf-8")


class Script(prog.AutoConsole):
    """Answers by a word in the question; records every question with the simulator's state
    at that moment (lines sent, arm position, moving or not)."""

    def __init__(self, sim, script=None, **kw):
        super().__init__(lambda k, t: None, script=script, **kw)
        self.sim, self.seen = sim, []

    def ask(self, question, choices=("yes", "no")):
        self.seen.append((question, len(self.sim.received), tuple(self.sim.pos),
                          self.sim.moving, self.sim.free_arm))
        return super().ask(question, choices)

    def text(self, question):
        self.seen.append((question, len(self.sim.received), tuple(self.sim.pos),
                          self.sim.moving, self.sim.free_arm))
        return super().text(question)


def _run(tmp_path, sim=None, script=None, **kw):
    sim = sim or sim_mod.SimTable()
    con = Script(sim, script=script, **kw)
    log = tmp_path / "log.txt"
    code = prog.main(["--auto", "--sim", "cold" if sim.cold else "warm", "--log", str(log)],
                     sim_table=sim, console=con)
    sim.finish()
    return code, sim, log.read_text(encoding="utf-8"), con


def _unused_only(*keys):
    """Answers that run only the named steps and skip every other one."""
    out = {}
    for s in tbl.STEPS:
        out[f"Step {STEP_KEYS.index(s.key) + 1}: "] = None
    return {"Run this step now?": "skip", **{f"__{k}": "yes" for k in keys}}


class Choose(Script):
    """Runs exactly the steps in *keys* (yes), skips the others."""

    def __init__(self, sim, keys, script=None, **kw):
        super().__init__(sim, script=script, **kw)
        self.keys, self.last_title = set(keys), None

    def say(self, text=""):
        m = re.match(r"Step \d+: (.*)\.$", text)
        if m:
            self.last_title = m.group(1)
        super().say(text)

    def ask(self, question, choices=("yes", "no")):
        if question.endswith("Run this step now?"):
            step = next(s for s in tbl.STEPS if s.title == self.last_title)
            self.seen.append((question, len(self.sim.received), tuple(self.sim.pos),
                              self.sim.moving, self.sim.free_arm))
            ans = "yes" if step.key in self.keys else "skip"
            self.log("ASK", f"{question} -> {ans} (automatic)")
            return ans
        return super().ask(question, choices)


def _choose(tmp_path, keys, sim=None, script=None, **kw):
    sim = sim or sim_mod.SimTable()
    con = Choose(sim, keys, script=script, **kw)
    log = tmp_path / "log.txt"
    code = prog.main(["--auto", "--log", str(log)], sim_table=sim, console=con)
    sim.finish()
    return code, sim, log.read_text(encoding="utf-8"), con


def _lines(key):
    return [tbl.WIRE[k].decode().rstrip("\r") for k in tbl.step_lines(tbl.STEPS[STEP_KEYS.index(key)])]


ALL = OPEN + [x for k in STEP_KEYS for x in _lines(k)]


# ---- the allow-list -------------------------------------------------------------------

def test_bytes_md_lists_exactly_the_programs_sixteen_lines():
    listed = _bytes_md_lines()
    assert set(listed) == RECORDED
    assert {v.decode("ascii").rstrip("\r") for v in tbl.WIRE.values()} == RECORDED
    for line, hx in listed.items():
        assert bytes.fromhex(hx.replace(" ", "")) == (line + "\r").encode("ascii"), line


def test_every_line_has_a_valid_checksum_and_names_where_it_was_recorded():
    for key, line in tbl.WIRE.items():
        assert line.endswith(b"\r") and line.count(b"\r") == 1
        assert tbl.checksum_ok(line[:-1].decode("ascii"))
        assert re.search(r"\b(S1|S2|R1|R2) \d", tbl.RECORDED_AT[key]), key
    assert set(tbl.RECORDED_AT) == set(tbl.WIRE)


def test_the_four_moves_have_their_recorded_targets_and_speed():
    want = {"to_250": (1102, 250), "to_1000": (1000, 1500), "to_1498": (1102, 1498),
            "to_2507": (2507, 1498)}
    for key, (x, y) in want.items():
        line = tbl.WIRE[key].decode()
        assert line[1:3] == "m0"
        assert (int(line[3:7], 16), int(line[7:11], 16), int(line[11:15], 16)) == (x, y, 300)


def test_the_gate_refuses_every_other_line():
    for bad in (b";i02c\r", b";m10b10055b012c42\r", b";c32f\r", b";c42e\r", b";d1016d35\r",
                b";p124\r", b";m0044e00fa00c839\r", b";m0044e00fb012c0d\r", b";a133",
                b";a133\r\r", b";A133\r", b";u8000060000200d0\r", b"", b";f12e\n"):
        with pytest.raises(tbl.ForbiddenLine):
            tbl.check_outgoing(bad)


def test_no_unrecorded_or_high_risk_command_exists_in_the_package():
    for name in PROGRAM_FILES + ("README.md",):
        src = _source(name)
        for cid in FORBIDDEN_IDS:
            assert f";{cid}" not in src, (name, cid)
            assert f'_frame("{cid}"' not in src, (name, cid)
    frames = re.findall(r'_frame\("([a-z][0-9])"(?:, "([0-9a-f]*)")?\)', _source("i1io_session_table.py"))
    assert sorted(set(f for f, _ in frames)) == sorted({"a1", "k2", "u8", "a0", "s0", "f4", "p0",
                                                        "i1", "f0", "f3", "m0", "f1"})
    assert sorted(a for f, a in frames if f == "u8") == ["000060000100", "000061000068"]
    tree = ast.parse(_source("i1io_session_table.py"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_frame"]
    assert all(all(isinstance(a, ast.Constant) for a in c.args) for c in calls)
    assert len(calls) == 16


def test_the_program_writes_only_in_one_place_and_through_the_gate():
    src = _source("i1io_session_table.py")
    assert src.count("self.t.write(") == 1
    assert src.count("self.dev.write(") == 1
    assert len(re.findall(r"ctrl_transfer\(", src)) == 1
    assert ".write(" not in _source("i1io_session.py").replace("fh.write(", "")


def test_standard_library_only():
    allowed = {"__future__", "argparse", "datetime", "platform", "signal", "subprocess", "sys",
               "tempfile", "textwrap", "pathlib", "re", "time", "dataclasses", "math", "random",
               "os", "ctypes", "termios", "fcntl", "usb", "plistlib", "i1io_session_table",
               "i1io_session_sim"}
    for name in PROGRAM_FILES:
        for node in ast.walk(ast.parse(_source(name))):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "").split(".")[0]]
            else:
                continue
            for m in mods:
                assert m in allowed, (name, m)


def test_the_simulator_carries_its_own_copy_of_every_step():
    src = _source("i1io_session_sim.py")
    assert "tbl." not in src and src.count("i1io_session_table") == 1
    assert "from i1io_session_table import TransportError, checksum, checksum_ok" in src
    assert sim_mod.REC_OPEN == [tbl.WIRE[k].decode().rstrip("\r") for k in tbl.OPEN_KEYS]
    for s in tbl.STEPS:
        assert sim_mod.REC_STEPS[s.key] == _lines(s.key), s.key


# ---- caps ----------------------------------------------------------------------------------

def test_the_caps_per_step_and_per_session_are_pinned():
    assert tbl.STEP_MAX_LINES == {"home": 4, "near": 21, "straight": 19, "across": 27,
                                  "free": 25, "close": 3}
    assert tbl.STEP_MAX_MOTIONS == {"home": 1, "near": 5, "straight": 4, "across": 6,
                                    "free": 3, "close": 0}
    assert tbl.MAX_LINES == 110 and tbl.MAX_MOTIONS == 19
    assert tbl.MAX_LINES == len(tbl.OPEN_KEYS) + sum(tbl.STEP_MAX_LINES.values())


def test_a_step_cannot_exceed_its_own_caps_nor_the_session_its_caps():
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    d.opening()
    d.current_step, d.step_lines = tbl.STEPS[0], 4
    with pytest.raises(tbl.Doubt):
        d.exchange("status")
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    d.lines_sent = tbl.MAX_LINES
    with pytest.raises(tbl.Doubt):
        d.exchange("identity")
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    d.current_step, d.motions_sent = tbl.STEPS[1], tbl.MAX_MOTIONS
    n = len(d.t.writes)
    with pytest.raises(tbl.Doubt):
        d.exchange("to_250", "to_250")
    assert len(d.t.writes) == n


def test_no_movement_outside_a_step():
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    with pytest.raises(tbl.Doubt):
        d.exchange("home", "home_rest")
    assert d.t.writes == []


def test_a_struck_step_is_removed_by_deleting_one_entry(tmp_path, monkeypatch):
    """The reviewer may strike a step: without its entry the session never offers or sends
    it, and nothing else in the program names it."""
    kept = tuple(s for s in tbl.STEPS if s.key != "across")
    monkeypatch.setattr(tbl, "STEPS", kept)
    code, sim, log, con = _run(tmp_path)
    assert code == 0 and ";m009cb05da012cda" not in sim.received
    assert sim.steps_run == ["home", "near", "straight", "free", "close"]
    for key in ("near", "straight", "across"):
        assert f'"{key}"' not in _source("i1io_session.py"), key


# ---- the clean paths ------------------------------------------------------------------------

def test_every_step_in_one_session(tmp_path):
    code, sim, log, con = _run(tmp_path)
    assert code == 0 and sim.received == ALL and len(ALL) == 110
    assert sim.motions == 19 and sim.steps_run == list(STEP_KEYS)
    assert "table closed; steps done ['home', 'near', 'straight', 'across', 'free', 'close']" in log
    assert "arm home" in log


@pytest.mark.parametrize("key", ["home", "near", "straight", "across", "free"])
def test_each_step_alone_then_the_close(tmp_path, key):
    code, sim, log, con = _choose(tmp_path, {key, "close"})
    assert code == 0 and sim.received == OPEN + _lines(key) + _lines("close")
    assert sim.steps_run == [key, "close"]


def test_skipping_everything_sends_the_opening_only_and_says_it_was_not_closed(tmp_path):
    code, sim, log, con = _choose(tmp_path, set())
    assert code == 0 and sim.received == OPEN and sim.motions == 0
    assert " ".join(prog.NOT_CLOSED.split()) in " ".join(log.split())
    assert not any("close" in q.lower() and "Run this step" in q for q, *_ in con.seen
                   if False)


def test_the_close_needs_a_homing_first(tmp_path):
    code, sim, log, con = _choose(tmp_path, {"close"})
    assert sim.received == OPEN and "table warm" in log


def test_end_stops_offering_steps(tmp_path):
    class End(Choose):
        def ask(self, question, choices=("yes", "no")):
            if question.endswith("Run this step now?") and self.last_title.startswith("Drive out about"):
                self.log("ASK", f"{question} -> end")
                return "end"
            return super().ask(question, choices)
    sim = sim_mod.SimTable()
    con = End(sim, set(STEP_KEYS))
    log = tmp_path / "l.txt"
    assert prog.main(["--auto", "--log", str(log)], sim_table=sim, console=con) == 0
    sim.finish()
    assert sim.received == OPEN + _lines("home")


def test_a_cold_table_gets_the_six_reading_lines_and_nothing_else(tmp_path):
    code, sim, log, con = _run(tmp_path, sim_mod.SimTable(cold=True))
    assert code == 1 and sim.received == OPEN[:6]
    assert "needs its start-up, which this program does not send" in " ".join(log.split())


def test_after_the_free_step_only_the_close_is_offered(tmp_path):
    code, sim, log, con = _choose(tmp_path, {"free", "close"})
    titles = re.findall(r"^SAY    Step \d+: (.*)\.$", log, re.M)
    i = titles.index(tbl.STEPS[STEP_KEYS.index("free")].title)
    assert titles[i + 1:] == [tbl.STEPS[STEP_KEYS.index("close")].title]
    assert sim.received[-3:] == [";s022", ";f02f", ";f32c"]


def test_the_free_step_touch_comes_with_the_arm_free_at_home(tmp_path):
    code, sim, log, con = _choose(tmp_path, {"free"})
    at = [s for s in con.seen if s[0] == prog.ASK_FREE_TOUCH]
    assert len(at) == 1
    q, n, pos, moving, free = at[0]
    assert free and not moving and tbl.REST_GUARD.contains((round(pos[0]), round(pos[1])))
    assert sim.received[n - 1] == ";f42b" and sim.received[n - 3] == ";f12e"
    assert "('free arm at home (step 'free')', 'free')" in log or "free arm at home" in log


# ---- the guards ------------------------------------------------------------------------------

@pytest.mark.parametrize("y,window", [(0, "home_rest"), (48, "home_rest"), (49, "home_wide"),
                                      (55, "home_wide"), (80, "home_wide")])
def test_the_homing_guard_inside(tmp_path, y, window):
    sim = sim_mod.SimTable(pos=[1102.0, float(y)], jitter=False)
    code, sim, log, con = _choose(tmp_path, {"home", "close"}, sim=sim)
    assert code == 0 and sim.received == OPEN + _lines("home") + _lines("close")
    assert f"home/{window}" in log


@pytest.mark.parametrize("x,y", [(1102, 251), (1102, 300), (1102, -2), (1089, 20), (1116, 20),
                                 (1058, 317), (1090, 251), (1102, 1202)])
def test_the_homing_guard_outside_stops_before_any_movement(tmp_path, x, y):
    sim = sim_mod.SimTable(pos=[float(x), float(y)], jitter=False)
    code, sim, log, con = _run(tmp_path, sim)
    assert code == 2 and sim.received == OPEN + [";s022", ";p025"] and sim.motions == 0
    assert "Nothing was moved." in log


def test_the_guard_box_and_its_reasons_are_pinned():
    assert tbl.REST_GUARD == tbl.Box(1101, 1103, -1, 80)
    assert tbl.START_GUARD == tbl.Box(1090, 1115, -1, 250)
    assert not tbl.START_GUARD.contains((1058, 317))    # 32 units left of X 1090, 67 beyond Y 250
    assert tbl.START_GUARD.contains((1104, 110)) and tbl.START_GUARD.contains((1101, 97))
    assert tbl.HOME_FIRST[1] == ("p0", "START_GUARD", "right before the homing")
    assert tbl.HOME_AND_CHECK[2][1] == "REST_GUARD"
    assert tbl.REST_RECORDED == tbl.Box(1101, 1103, -1, 48)
    assert tbl.OUT_START == tbl.Box(1101, 1103, -1, 48)
    xs = [x for x, _ in tbl.RECORDED_REST_STARTS]
    ys = [y for _, y in tbl.RECORDED_REST_STARTS]
    assert tbl.REST_RECORDED == tbl.Box(min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1)
    assert not tbl.REST_GUARD.contains((1058, 317))      # the one recorded drive-out case
    assert tbl.TIME_WINDOW["home_rest"] == (0.0, 0.6) and tbl.TIME_WINDOW["home_wide"][1] == 2.0


def test_a_move_out_needs_a_start_where_the_recorded_ones_started(tmp_path):
    """The p0 right before driving out (after the step's homing) must read Y -1..48."""
    sim = sim_mod.SimTable()
    sim.inject_at(len(OPEN) + 6, "drift", 60.0)       # the p0 before the move
    code, sim, log, con = _choose(tmp_path, {"near"}, sim=sim)
    assert code == 2 and sim.received == OPEN + _lines("near")[:7] and sim.motions == 1


@pytest.mark.parametrize("key,move_at", [("near", 7), ("near", 9), ("straight", 7),
                                         ("across", 7), ("across", 9), ("across", 15)])
def test_a_move_that_does_not_arrive_stops_with_the_arm_out(tmp_path, key, move_at):
    sim = sim_mod.SimTable()
    sim.inject_at(len(OPEN) + move_at, "blocked", 0.5)
    code, sim, log, con = _choose(tmp_path, {key}, sim=sim)
    sent = sim.received[len(OPEN):]
    assert code == 2 and sent[-1] == ";p025"            # stopped at the arrival check
    assert " ".join(prog.OUT_ON_TABLE.split()) in " ".join(log.split())
    assert prog.ASK_TOUCH not in [q for q, *_ in con.seen]


@pytest.mark.parametrize("kind", ["slow_motion", "fast_motion", "late"])
def test_every_movement_outside_its_time_window_stops_right_after_it(tmp_path, kind):
    """A homing from rest has no lower bound (recorded 0.047 s from Y 0..2), so a too fast
    answer is a stop only for the moves with a recorded lower bound."""
    moves = [i for i, ln in enumerate(ALL) if ln in (";i12b",) or ln.startswith(";m0")]
    for i in moves:
        sim = sim_mod.SimTable()
        sim.inject_at(i, kind, 30.0 if kind == "late" else 1.0)
        code, sim, log, con = _run(tmp_path, sim)
        if kind == "fast_motion" and code == 0:
            assert ALL[i] == ";i12b"            # a homing from rest: no lower bound
            continue
        assert code == 2, (kind, i, ALL[i])
        assert sim.received == ALL[:i + 1], (kind, i)


def test_the_free_arm_homing_refused_with_status_3_stops(tmp_path):
    lines = _lines("free")
    at = len(OPEN) + len(lines) - 6                  # the i1 from the free arm
    assert ALL[:len(OPEN)] == OPEN
    sim = sim_mod.SimTable()
    con_keys = {"free"}
    sim.inject_at(at, "status", 3.0)
    code, sim, log, con = _choose(tmp_path, con_keys, sim=sim)
    assert code == 2 and sim.received == OPEN + lines[:len(lines) - 5]
    flat = " ".join(log.split())
    assert "should still be there" in flat
    assert prog.FREE_MAYBE in flat and " ".join(prog.FREE_MODE_LEFT.split()) in flat
    assert " ".join(prog.NOT_CLOSED.split()) not in flat
    assert "the hand-alignment mode was left on" in log


def test_a_wrong_f4_in_the_free_step_stops(tmp_path):
    lines = _lines("free")
    after_f1 = len(OPEN) + lines.index(";f12e") + 1
    sim = sim_mod.SimTable()
    sim.inject_at(after_f1, "free", 0.0)              # f4 answers 00 where 01 is expected
    code, sim, log, con = _choose(tmp_path, {"free"}, sim=sim)
    assert code == 2 and len(sim.received) == after_f1 + 1


# ---- every fault, every stop -----------------------------------------------------------------

@pytest.mark.parametrize("kind", [k for k in sim_mod.FAULT_KINDS
                                  if k not in ("slow_motion", "fast_motion", "blocked", "drift")])
def test_any_fault_at_any_line_stops_with_nothing_more_sent(tmp_path, kind):
    for i in range(len(ALL)):
        line = ALL[i]
        if kind in ("identity",) and line != ";a133":
            continue
        if kind in ("k2_other",) and line != ";k228":
            continue
        if kind in ("a0_other",) and line != ";a034":
            continue
        if kind == "memory_short" and not line.startswith(";u8"):
            continue
        if kind == "memory_bad_start" and line != ";u8000060000100d1":
            continue
        if kind == "free" and line != ";f42b":
            continue
        sim = sim_mod.SimTable()
        sim.inject_at(i, kind, 1.0 if kind != "late" else 30.0)
        code, sim, log, con = _run(tmp_path, sim)
        assert code == 2, (kind, i, line)
        assert sim.received == ALL[:i + 1], (kind, i, line)
        assert sim_mod.FAKE_SERIAL not in log


def test_ctrl_c_during_any_exchange_sends_nothing_more(tmp_path):
    for i in range(len(ALL)):
        sim = sim_mod.SimTable()

        def hook(n, i=i):
            if n == i:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
        code, sim, log, con = _run(tmp_path, sim)
        assert code in (1, 0), i
        assert len(sim.received) <= i + 1 or sim.received == ALL, i
        assert sim.received == ALL[:len(sim.received)]
        if len(sim.received) < len(ALL):
            assert "stopped by you" in log or "stopped with Ctrl-C" in log, i


def test_stop_or_ctrl_c_at_every_question_sends_nothing_more(tmp_path):
    n_questions = len(_run(tmp_path)[3].seen)
    for n in range(1, n_questions + 1):
        sim = sim_mod.SimTable()
        code, sim, log, con = _run(tmp_path, sim, interrupt_at=n)
        assert sim.received == ALL[:len(sim.received)], n
        assert not sim.moving


def test_nothing_is_asked_while_the_arm_is_out_or_moving(tmp_path):
    for keys in ({"near"}, {"straight"}, {"across"}, set(STEP_KEYS)):
        code, sim, log, con = _choose(tmp_path, keys)
        for q, n, pos, moving, free in con.seen:
            assert not moving, q
            assert tbl.REST_GUARD.contains((round(pos[0]), round(pos[1]))), (q, pos)


def test_a_no_after_a_step_ends_the_session(tmp_path):
    code, sim, log, con = _run(tmp_path, script={prog.ASK_DID: "no"})
    assert code == 1 and sim.received == OPEN + _lines("home")


def test_i1profiler_started_during_the_session_stops_before_the_next_step(tmp_path, monkeypatch):
    calls = []

    def running():
        calls.append(1)
        return len(calls) >= 2
    sim = sim_mod.SimTable()
    tr = sim_mod.SimTransport(sim)
    s = prog.Session(tbl.Table(tr), Script(sim), simulated=True, other_program=running)
    assert s.go() == 1 and sim.received == OPEN + _lines("home")


# ---- texts and privacy -----------------------------------------------------------------------

def test_every_step_explains_itself_and_its_risk_before_the_yes(tmp_path):
    code, sim, log, con = _run(tmp_path)
    flat = " ".join(log.split())
    for n, s in enumerate(tbl.STEPS, 1):
        i = flat.index(f"Step {n}: {s.title}.")
        assert flat.index(" ".join(s.explain.split()), i) > i
        assert flat.index("What is not exactly as recorded: " + " ".join(s.beyond.split()), i) > i
        assert s.risk in ("low", "medium")
    assert {s.risk for s in tbl.STEPS} <= {"low", "medium"}


def test_the_memory_answers_never_reach_the_log_or_the_screen(tmp_path, capsys):
    code, sim, log, con = _run(tmp_path)
    out = capsys.readouterr().out
    for text in (log, out):
        assert sim_mod.FAKE_SERIAL not in text
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in text


def test_plan_and_dry_run_show_every_line_and_open_nothing(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tbl, "open_table", lambda: pytest.fail("opened"))
    assert prog.main(["--plan"]) == 0
    plan = capsys.readouterr().out
    assert prog.main(["--dry-run"]) == 0
    dry = capsys.readouterr().out
    for line in RECORDED:
        assert line in plan and line in dry
        assert (line + "\r").encode().hex(" ") in dry
    assert set(re.findall(r";[a-z][0-9][0-9a-f]*", plan + dry)) == RECORDED
    assert list(tmp_path.iterdir()) == []


def test_the_touch_wording_is_gentle_and_never_downwards():
    for q in (prog.ASK_TOUCH, prog.ASK_FREE_TOUCH):
        for needed in ("very gently", "from side to side", "Do not push it towards the front "
                       "of the table", "do not press down", "force it"):
            assert needed in q, needed
        assert "push it very gently towards" not in q


def test_the_readme_says_what_matters():
    readme = " ".join(_source("README.md").split())
    for line in RECORDED:
        assert line in readme, line
    for needed in ("power switch", "Ctrl-C", "--plan", "not from X-Rite", "unofficial",
                   "hands and everything else away from the arm", "empty",
                   "folder you started it from", "has just been switched on", "skip",
                   "open i1Profiler once"):
        assert needed in readme, needed
    assert "—" not in _source("README.md")
    for s in tbl.STEPS:
        assert s.title in readme, s.title


def test_f4_is_never_called_a_motor_reading():
    for name in PROGRAM_FILES + ("README.md", "BYTES.md"):
        text = " ".join(_source(name).split()).lower()
        for claim in ("asks whether the motors hold", "its motors hold the arm (f4",
                      "f4 = 00 means", "we believe: the motors hold"):
            assert claim not in text, (name, claim)


def test_the_program_runs_no_other_command_than_pgrep_and_ioreg():
    for name in PROGRAM_FILES:
        src = _source(name)
        for bad in ("os.kill", "killpg", "pkill", "killall", "launchctl", "os.system", "Popen("):
            assert bad not in src, (name, bad)
    runs = re.findall(r"subprocess\.run\(\s*(\[[^\]]*\])", _source("i1io_session.py")
                      + _source("i1io_session_table.py"))
    assert runs == ['["pgrep", *args]',
                    '["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"]']


def test_the_practice_run_never_opens_the_real_table(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl, "open_table", lambda: pytest.fail("opened"))
    for cold in (True, False):
        code, *_ = _run(tmp_path, sim_mod.SimTable(cold=cold))
        assert code == (1 if cold else 0)


# ---- the USB layer (a fake pyusb device) -----------------------------------------------------
class USBError(Exception):
    def __init__(self, strerror="", errno=None):
        super().__init__(strerror)
        self.strerror, self.errno = strerror, errno


class USBTimeoutError(USBError):
    pass


class FakeCore:
    USBError = USBError
    USBTimeoutError = USBTimeoutError


class FakeUtil:
    def __init__(self):
        self.calls = []

    def claim_interface(self, dev, n):
        self.calls.append(("claim", n))

    def release_interface(self, dev, n):
        self.calls.append(("release", n))

    def dispose_resources(self, dev):
        self.calls.append(("dispose",))


class _EP:
    def __init__(self, addr):
        self.bEndpointAddress, self.bmAttributes, self.wMaxPacketSize = addr, 2, 64


class _Intf:
    bInterfaceClass = bInterfaceSubClass = bInterfaceProtocol = 0xFF

    def endpoints(self):
        return [_EP(0x81), _EP(0x02)]


class FakeDev:
    """Speaks to a SimTable in FTDI packets (2 status bytes + up to 62 bytes),
    with status-only packets between them. Touching the serial number fails."""

    def __init__(self, cold=True, line_status=0x60):
        self.bcdDevice = 0x0400
        self.sim = sim_mod.SimTable(cold=cold)
        self.t = sim_mod.SimTransport(self.sim)
        self.ctrl, self.line_status = [], line_status
        self.pending, self.toggle = b"", False

    def __getattr__(self, name):
        if "serial" in name.lower():
            raise AssertionError("the serial number string must never be read")
        raise AttributeError(name)

    def __getitem__(self, i):
        return [_Intf()]

    def get_active_configuration(self):
        return object()

    def ctrl_transfer(self, rt, req, val, idx, data, timeout):
        self.ctrl.append((rt, req, val, idx, data))

    def write(self, ep, data, timeout):
        assert ep == 0x02
        self.t.write(bytes(data))
        return len(data)

    def read(self, ep, size, timeout_ms):
        assert ep == 0x81 and size == 64
        self.toggle = not self.toggle
        if self.toggle:
            return bytes([0x11, 0x60])
        if not self.pending:
            self.pending = self.t.read(timeout_ms / 1000.0)
        if not self.pending:
            raise USBTimeoutError("Operation timed out", 60)
        out, self.pending = self.pending[:62], self.pending[62:]
        return bytes([0x11, self.line_status]) + out


def _ftdi(dev):
    """The FTDI path on the simulator's VIRTUAL clock (so the movement windows apply)."""
    util = FakeUtil()
    t = tbl.FtdiUsb(dev, FakeCore, util)
    t.now = dev.t.now
    t.setup()
    return util, t


def test_setup_sends_exactly_the_five_recorded_ftdi_requests(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    assert dev.ctrl == [(0x40, 0x00, 0x0000, 0, None), (0x40, 0x00, 0x0001, 0, None),
                        (0x40, 0x00, 0x0002, 0, None), (0x40, 0x03, 0x0034, 0, None),
                        (0x40, 0x04, 0x0008, 0, None)]


def test_a_whole_session_over_the_ftdi_path(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(cold=False)
    util, t = _ftdi(dev)
    s = prog.Session(tbl.Table(t), Script(dev.sim), simulated=True)
    assert s.go() == 0
    assert dev.sim.received == ALL
    t.close()
    assert ("release", 0) in util.calls


def test_the_ftdi_transport_refuses_any_other_line_itself(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    with pytest.raises(tbl.ForbiddenLine):
        t.write(b";m10b10055b012c42\r")
    assert dev.sim.received == []


def test_the_real_run_needs_a_person_at_the_keyboard(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", open(__file__, encoding="utf-8"))
    log = tmp_path / "real.txt"
    assert prog.main(["--real", "--log", str(log)]) == 2
    assert "typed by a person" in log.read_text(encoding="utf-8")


class _TTY:
    def isatty(self):
        return True


def test_the_real_path_order_questions_touch_sentence_open(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(cold=False)
    events = []
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(tbl, "check_usb_available", lambda: "pyusb test; libusb test")
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog, "xrite_helpers_running", lambda: ["xrdd"])
    monkeypatch.setattr(tbl, "usb_holders", lambda: [])
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)
    monkeypatch.setattr(prog.time, "sleep", lambda s: None)

    def opener():
        events.append("open")
        return _ftdi(dev)[1]
    monkeypatch.setattr(tbl, "open_table", opener)

    class C(Script):
        def ask(self, question, choices=("yes", "no")):
            events.append(question)
            return super().ask(question, choices)
    log = tmp_path / "r.txt"
    assert prog.main(["--real", "--log", str(log)], console=C(dev.sim)) == 0
    # 0.3.1: no touch before the opening; the first touch comes after the session, at rest
    assert prog.ASK_MOVED in events and events.index(prog.ASK_MOVED) < events.index("open")
    assert prog.ASK_TOUCH in events and events.index(prog.ASK_TOUCH) > events.index("open")
    assert dev.sim.received == ALL


def test_a_busy_table_is_named_without_its_number(tmp_path, monkeypatch):
    class BusyUtil(FakeUtil):
        def claim_interface(self, dev, n):
            exc = USBError("Access denied (insufficient permissions)", 13)
            exc.backend_error_code = -3
            raise exc

    def opener():
        t = tbl.FtdiUsb(FakeDev(), FakeCore, BusyUtil())
        t.setup()
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(tbl, "check_usb_available", lambda: "pyusb test; libusb test")
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog, "xrite_helpers_running", lambda: ["xrdd"])
    monkeypatch.setattr(tbl, "usb_holders", lambda: ["exclusive owner: SomeApp (pid 654)"])
    monkeypatch.setattr(tbl, "open_table", opener)
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)
    log = tmp_path / "b.txt"
    assert prog.main(["--real", "--log", str(log)], console=prog.AutoConsole(lambda k, t: None)) == 2
    text = log.read_text(encoding="utf-8")
    said = " ".join(line[7:] for line in text.splitlines() if line.startswith("SAY"))
    assert "macOS names the program holding it: SomeApp." in said and "654" not in said
    assert "pid 654" in text


# ---- the package --------------------------------------------------------------------------

def test_the_zip_is_reproducible_and_runs_from_a_clean_folder(tmp_path):
    build = ROOT / "scripts" / "build_i1io_session_zip.py"
    a = subprocess.run([sys.executable, "-I", str(build), "--out", str(tmp_path / "a")],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    b = subprocess.run([sys.executable, "-I", str(build), "--out", str(tmp_path / "b")],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert a.returncode == 0 and b.returncode == 0, a.stderr
    za = next((tmp_path / "a").glob("*.zip"))
    zb = next((tmp_path / "b").glob("*.zip"))
    assert za.read_bytes() == zb.read_bytes()
    with zipfile.ZipFile(za) as z:
        names = sorted(n.split("/", 1)[1] for n in z.namelist())
        assert names == sorted(["README.md", "BYTES.md", "i1io_session.py",
                                "i1io_session_table.py", "i1io_session_sim.py", "LICENSE"])
        z.extractall(tmp_path / "x")
    folder = next((tmp_path / "x").iterdir())
    for sim in ("cold", "warm"):
        r = subprocess.run([sys.executable, "-I", "i1io_session.py", "--auto", "--sim", sim,
                            "--log", f"run-{sim}.txt"], cwd=folder, capture_output=True,
                           text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
        assert r.returncode == (1 if sim == "cold" else 0), r.stdout + r.stderr
        assert "Traceback" not in r.stdout + r.stderr


def test_bytes_md_and_the_readme_carry_the_programs_steps_and_caps():
    b = _source("BYTES.md")
    rows = re.findall(r"^\| (\d) \| (\w+) \| (\d+) \| (\d+) \| (\w+) \| `([a-z0-9 ]+)` \|$", b, re.M)
    assert [(k, int(n), int(m), r) for _, k, n, m, r, _ in rows] == [
        (s.key, tbl.STEP_MAX_LINES[s.key], tbl.STEP_MAX_MOTIONS[s.key], s.risk)
        for s in tbl.STEPS]
    for (_, k, *_rest, ids) in rows:
        step = tbl.STEPS[STEP_KEYS.index(k)]
        assert ids.split() == [tbl.WIRE[x].decode()[1:3] for x in tbl.step_lines(step)]
    assert f"**{tbl.MAX_LINES} lines, {tbl.MAX_MOTIONS} movements**" in b
    readme = " ".join(_source("README.md").split())
    assert f"At most **{tbl.MAX_LINES} lines and {tbl.MAX_MOTIONS} movements**" in readme
    for s in tbl.STEPS:
        assert " ".join(s.explain.split()) in readme and " ".join(s.beyond.split()) in readme



def test_a_free_arm_pushed_off_its_place_stops_without_the_homing(tmp_path):
    lines = _lines("free")
    at_p0 = len(OPEN) + lines.index(";p025", lines.index(";f12e"))
    sim = sim_mod.SimTable()
    sim.inject_at(at_p0, "drift", 150.0)
    code, sim, log, con = _choose(tmp_path, {"free"}, sim=sim)
    assert code == 2 and sim.received == OPEN + lines[:lines.index(";p025", lines.index(";f12e")) + 1]
    flat = " ".join(log.split())
    assert "not where the step needed it" in flat
    assert " ".join(prog.FREE_MODE_LEFT.split()) in flat and prog.FREE_MAYBE in flat
    assert flat.count(" ".join(prog.RECOVERY.split())) == 1          # said once, not twice
    assert prog.ASK_TOUCH not in [q for q, *_ in con.seen]


# ---- guards pinned on their own (planted faults had survived the first pass) ----------------

def test_the_arrival_boxes_are_five_units_and_six_off_stops(tmp_path):
    assert tbl.AT_1000 == tbl.Box(995, 1005, 1495, 1505)
    assert tbl.AT_250 == tbl.Box(1097, 1107, 245, 255)
    assert tbl.AT_1498 == tbl.Box(1097, 1107, 1493, 1503)
    assert tbl.AT_2507 == tbl.Box(2502, 2512, 1493, 1503)
    lines = _lines("near")
    at = len(OPEN) + lines.index(";m003e805dc012c06") + 5      # the p0 after ARRIVE
    assert (OPEN + lines)[at] == ";p025"
    for drift, ok in ((5.0, True), (6.0, False)):
        sim = sim_mod.SimTable(jitter=False)
        sim.inject_at(at, "drift", drift)
        code, sim, log, con = _choose(tmp_path, {"near"}, sim=sim)
        if ok:
            assert sim.received == OPEN + lines
        else:
            assert code == 2 and sim.received == OPEN + lines[:lines.index(";m003e805dc012c06") + 6]


def test_a_step_runs_at_most_once():
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    d.opening()
    home = tbl.STEPS[STEP_KEYS.index("home")]
    d.run_step(home)
    assert not d.can_run(home)
    n = len(d.t.writes)
    with pytest.raises(tbl.Doubt):
        d.run_step(home)
    assert len(d.t.writes) == n


def test_a_stop_noticed_inside_write_before_the_wire_writes_nothing(monkeypatch):
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    real_hold = tbl.hold_stop_signals

    def hold():
        d.request_stop()            # a Ctrl-C arriving between the checks and the write
        return real_hold()
    monkeypatch.setattr(tbl, "hold_stop_signals", hold)
    with pytest.raises(tbl.Stopped):
        d.exchange("identity")
    assert d.t.writes == []


def test_the_stop_signals_are_held_while_a_line_is_written():
    sim = sim_mod.SimTable()
    t = sim_mod.SimTransport(sim)
    seen = []
    real_write = t.write

    def write(data):
        seen.append(signal.SIGINT in signal.pthread_sigmask(signal.SIG_BLOCK, []))
        real_write(data)
    t.write = write
    d = tbl.Table(t)
    d.exchange("identity")
    assert seen == [True]
    assert signal.SIGINT not in signal.pthread_sigmask(signal.SIG_BLOCK, [])


def test_the_memory_answers_are_logged_only_as_not_written_down(tmp_path):
    code, sim, log, con = _run(tmp_path)
    mem = [ln for ln in log.splitlines() if ln.startswith("RECV") and ":$u8" in ln]
    assert len(mem) == 2 and all("not written down" in ln for ln in mem)


def test_the_session_is_closed_for_sending_before_the_first_touch(tmp_path, monkeypatch):
    seen = []
    real_touch = prog.Session.touch

    def touch(self, when):
        seen.append(self.d.closed_reason)
        n = len(self.d.t.writes)
        with pytest.raises(tbl.Doubt):
            self.d.exchange("status")
        assert len(self.d.t.writes) == n
        return real_touch(self, when)
    monkeypatch.setattr(prog.Session, "touch", touch)
    code, sim, log, con = _run(tmp_path)
    assert code == 0 and seen and seen[0] in ("the table is closed", "the session is over")


def _drive(sim, lines):
    t = sim_mod.SimTransport(sim)
    for line in lines:
        t.write((line + "\r").encode())
        while t.table.next_time() is not None or t.table.moving:
            t.read(1.0)
    return t


@pytest.mark.parametrize("y", [251, 300, 317, -2])
def test_the_simulator_refuses_a_homing_outside_its_own_guard(y):
    sim = sim_mod.SimTable(pos=[1102.0, float(y)], jitter=False)
    t = _drive(sim, OPEN + [";s022", ";p025"])
    with pytest.raises(sim_mod.SimViolation, match="not a place this copy allows"):
        t.write(b";i12b\r")


def test_the_simulator_refuses_a_move_with_the_arm_free_and_f1_away_from_rest():
    sim = sim_mod.SimTable()
    sim.free_arm = True
    with pytest.raises(sim_mod.SimViolation, match="while the arm is free"):
        sim._physics(";m0044e00fa012c0e")
    sim = sim_mod.SimTable(pos=[1102.0, 1498.0])
    with pytest.raises(sim_mod.SimViolation, match="away from the resting place"):
        sim._physics(";f12e")


def test_i1profiler_is_checked_again_right_before_the_first_touch(tmp_path, monkeypatch):
    dev = FakeDev(cold=False)
    calls, events = [], []

    def running():
        calls.append(1)
        return len(calls) == 2
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(tbl, "check_usb_available", lambda: "pyusb test; libusb test")
    monkeypatch.setattr(prog, "i1profiler_running", running)
    monkeypatch.setattr(prog, "i1profiler_matches", lambda: ["a process named i1Profiler"])
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)
    monkeypatch.setattr(tbl, "open_table", lambda: events.append("open"))

    class C(Script):
        def ask(self, question, choices=("yes", "no")):
            events.append(question)
            return super().ask(question, choices)
    log = tmp_path / "l.txt"
    assert prog.main(["--real", "--log", str(log)], console=C(dev.sim)) == 2
    assert prog.ASK_TOUCH not in events and "open" not in events
    assert "refused before the first touch" in log.read_text(encoding="utf-8")


def test_a_session_ended_without_the_close_is_closed_for_sending_before_the_touch(
        tmp_path, monkeypatch):
    seen = []
    real_touch = prog.Session.touch

    def touch(self, when):
        seen.append(self.d.closed_reason)
        n = len(self.d.t.writes)
        with pytest.raises(tbl.Doubt):
            self.d.exchange("status")
        assert len(self.d.t.writes) == n
        return real_touch(self, when)
    monkeypatch.setattr(prog.Session, "touch", touch)
    code, sim, log, con = _choose(tmp_path, {"home"})
    assert code == 0 and sim.received == OPEN + _lines("home")
    assert seen and seen[0] == "the session is over"


# ---- the safety review of eb38ba20b: texts after step 5, true sentences, guard Y 80 ----------

#: The whole warm session as eb38ba20b sent it (110 lines). The review's changes are texts and
#: the narrower guard; what goes on the wire on this path must not change by a single byte.
EB38_FULL_SESSION_SHA256 = "48b64f912e6d7ccff9d2d982d833657d7538b73026840be11769a39f2721a22f"


def test_the_full_session_on_the_wire_is_byte_identical_to_the_reviewed_eb38ba20b(tmp_path):
    import hashlib
    code, sim, log, con = _run(tmp_path)
    assert code == 0 and len(sim.received) == 110 and sim.motions == 19
    assert hashlib.sha256(" ".join(ALL).encode()).hexdigest() == EB38_FULL_SESSION_SHA256
    assert hashlib.sha256(" ".join(sim.received).encode()).hexdigest() == EB38_FULL_SESSION_SHA256


def test_the_guard_boundary_y250_homes_and_y251_stops_before_any_movement(tmp_path):
    """0.3.1: the first homing's box START_GUARD X 1090..1115, Y -1..250."""
    for (x, y), homes in (((1102, 250), True), ((1102, 251), False), ((1090, 250), True),
                          ((1115, 0), True), ((1089, 30), False), ((1116, 30), False),
                          ((1104, 110), True), ((1101, 97), True)):
        sim = sim_mod.SimTable(pos=[float(x), float(y)], jitter=False)
        code, sim, log, con = _choose(tmp_path, {"home", "close"}, sim=sim)
        if homes:
            assert code == 0 and sim.motions == 1
            assert sim.received == OPEN + _lines("home") + _lines("close")
        else:
            assert code == 2 and sim.motions == 0
            assert sim.received == OPEN + [";s022", ";p025"]
            assert "Nothing was moved." in log
    assert "2.0 s from Y 49..250" in prog.plan_text()
    assert "X 1090 to 1115, Y -1 to 250" in prog.plan_text()


class _CtrlCAtFreeTouch(Choose):
    def ask(self, question, choices=("yes", "no")):
        if question == prog.ASK_FREE_TOUCH:
            raise KeyboardInterrupt
        return super().ask(question, choices)


def _free_mode_said(log):
    flat = " ".join(log.split())
    return (" ".join(prog.FREE_MODE_LEFT.split()) in flat
            and " ".join(prog.NOT_CLOSED.split()) not in flat
            and "the hand-alignment mode was left on" in log)


def test_ctrl_c_at_the_free_touch_says_the_table_is_still_in_the_hand_alignment_mode(tmp_path):
    sim = sim_mod.SimTable()
    con = _CtrlCAtFreeTouch(sim, {"free", "close"})
    log_path = tmp_path / "l.txt"
    code = prog.main(["--auto", "--log", str(log_path)], sim_table=sim, console=con)
    sim.finish()
    log = log_path.read_text(encoding="utf-8")
    lines = _lines("free")
    assert code == 1 and sim.received == OPEN + lines[:lines.index(";f12e") + 3]
    assert _free_mode_said(log) and prog.FREE_MAYBE in log
    flat = " ".join(log.split())
    for needed in ("still in the hand-alignment mode", "open i1Profiler once",
                   "switch the table off at its power switch, wait ten seconds",
                   "not a routine step"):
        assert needed in flat, needed


def test_ending_after_step_5_without_the_close_says_the_mode_is_still_on(tmp_path):
    code, sim, log, con = _choose(tmp_path, {"free"})
    assert code == 0 and sim.received == OPEN + _lines("free")
    assert _free_mode_said(log)
    assert prog.FREE_MAYBE not in log            # the arm was taken back: it is held again
    assert "The arm is at its resting place." in log


def test_a_free_arm_homing_that_never_finishes_says_power_cycle_and_the_mode(tmp_path):
    lines = _lines("free")
    at = len(OPEN) + len(lines) - 6                  # the i1 from the free arm
    sim = sim_mod.SimTable()
    sim.inject_at(at, "no_done", 0.0)
    code, sim, log, con = _choose(tmp_path, {"free"}, sim=sim)
    flat = " ".join(log.split())
    assert code == 2 and sim.received == OPEN + lines[:len(lines) - 5]
    assert " ".join(prog.UNFINISHED.split()) in flat and prog.UNFINISHED_FREE in flat
    assert " ".join(prog.FREE_MODE_LEFT.split()) not in flat


def test_the_close_after_step_5_says_it_switches_the_mode_off_and_is_recommended(tmp_path):
    code, sim, log, con = _choose(tmp_path, {"free", "close"})
    said = re.findall(r"^SAY    (.*)$", log, re.M)
    close_title = f"Step 6: {tbl.STEPS[STEP_KEYS.index('close')].title}."
    i = said.index(close_title)
    assert prog.CLOSE_AFTER_FREE in said[i:i + 6]
    assert "switches that mode off again" in prog.CLOSE_AFTER_FREE
    assert "recommend" in prog.CLOSE_AFTER_FREE
    assert "the table is closed" in log or "table closed" in log
    assert prog.FREE_MODE_LEFT not in log
    code, sim, log, con = _choose(tmp_path, {"home", "close"})
    assert prog.CLOSE_AFTER_FREE not in log


def test_the_free_touch_says_hands_off_before_answering():
    q = " ".join(prog.ASK_FREE_TOUCH.split())
    assert "take your hand off the arm BEFORE you answer" in q
    assert "right after your answer, the program sends the arm home at once" in q
    assert q.index("BEFORE you answer") < q.index("Does it move freely")


def test_the_out_on_table_text_expects_rather_than_promises_and_names_the_recovery():
    t = " ".join(prog.OUT_ON_TABLE.split())
    assert "We expect i1Profiler to bring the arm home" in t and "from 3 cm out" in t
    assert " ".join(prog.RECOVERY.split()) in t
    assert "wait ten seconds" in prog.RECOVERY and "not a routine step" in prog.RECOVERY


def test_the_step_texts_say_what_is_true():
    by = {s.key: s for s in tbl.STEPS}
    for key in ("near", "straight"):
        assert "X 1102, Y 1202" in by[key].beyond and "X 1050, Y 1492" not in by[key].beyond
        assert "holding the arm" in by[key].beyond
    for key in ("straight", "across"):
        assert "seven measuring sessions" in by[key].explain
        assert "without a calibration" in by[key].explain
    free = " ".join(by["free"].beyond.split())
    assert "recorded three times" in free and "twice it worked" in free
    assert "two milliseconds after a button" in free and "status 3 means is not known" in free
    assert "still in the hand-alignment mode" in free
    assert "switches the hand-alignment mode off again" in by["free"].explain
    assert "X 1090 to 1115 and Y up to 250 (up to 25 mm out" in by["home"].beyond
    assert "longer than 2 s" in by["home"].beyond


#: Sentences the safety review of eb38ba20b found untrue or asked to remove. None may come back
#: in any shipped file (the zip holds exactly these files).
UNTRUE = ("same harmless state", "harmless state as after i1profiler",
          "brings the arm to its resting place by itself", "brings the arm home by itself",
          "drove it home by itself", "not now", "recorded twice",
          "start of every measuring session", "answers directly the question of the loose arm",
          "answers the loose-arm question", "loose-arm question directly",
          "y 48 to 120", "up to 12 mm", "y 49..120", "y -1..120", "up to y 120",
          "which is how you found it after i1profiler", "may stay free until")
SHIPPED = ("README.md", "BYTES.md") + PROGRAM_FILES


def test_no_untrue_sentence_from_the_review_comes_back_in_any_shipped_file():
    for name in SHIPPED:
        # Python strings split over lines ("... state "\n    "as after ...") are joined first
        text = re.sub(r'"\s*\n\s*(?:\+\s*)?f?"', "", _source(name))
        text = " ".join(text.split()).lower()
        for phrase in UNTRUE:
            assert phrase not in text, (name, phrase)
    build = (ROOT / "scripts" / "build_i1io_session_zip.py").read_text(encoding="utf-8")
    assert all(f'"{n}"' in build for n in SHIPPED)


# ---- 0.3.1: no touch before the first homing, none after a stop; the wider first-homing box --

def test_no_touch_question_is_asked_before_the_opening(tmp_path):
    src = _source("i1io_session.py")
    body = src.split("def touch_before_opening", 1)[1].split("\ndef ", 1)[0]
    assert "ASK_TOUCH" not in body and "ask(" in body
    for name in SHIPPED:
        text = " ".join(_source(name).split()).lower()
        assert "push it very gently towards the front" not in text, name
        assert "apart from the touch just now" not in text, name
        assert "touch the arm gently once before it opens anything" not in text, name


def test_the_real_run_asks_no_touch_before_the_first_homing(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(cold=False)
    events = []
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(tbl, "check_usb_available", lambda: "pyusb test; libusb test")
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog, "xrite_helpers_running", lambda: [])
    monkeypatch.setattr(tbl, "usb_holders", lambda: [])
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)
    monkeypatch.setattr(prog.time, "sleep", lambda s: None)
    monkeypatch.setattr(tbl, "open_table", lambda: _ftdi(dev)[1])

    class C(Script):
        def ask(self, question, choices=("yes", "no")):
            events.append((question, list(self.sim.received)))
            return super().ask(question, choices)
    assert prog.main(["--real", "--log", str(tmp_path / "r.txt")], console=C(dev.sim)) == 0
    touches = [rec for q, rec in events if q in (prog.ASK_TOUCH, prog.ASK_FREE_TOUCH)]
    assert touches
    first_home = ALL.index(";i12b")
    assert all(len(rec) > first_home for rec in touches)


@pytest.mark.parametrize("x,y", [(1102, 251), (1089, 30), (1058, 317)])
def test_outside_even_the_wider_box_nothing_moves_no_touch_and_the_recovery_is_offered(
        tmp_path, x, y):
    sim = sim_mod.SimTable(pos=[float(x), float(y)], jitter=False)
    code, sim, log, con = _run(tmp_path, sim)
    flat = " ".join(log.split())
    assert code == 2 and sim.motions == 0 and sim.received == OPEN + [";s022", ";p025"]
    assert f"The arm stands at X {x}, Y {y}, outside the range" in flat
    for needed in ("open i1Profiler once, let it start the table, quit i1Profiler",
                   "run this program again without touching the arm"):
        assert needed in flat, needed
    assert prog.ASK_TOUCH not in [q for q, *_ in con.seen]


@pytest.mark.parametrize("script", [{prog.ASK_DID: "no"}, {prog.ASK_DID: "stop"}])
def test_no_touch_question_after_an_early_stop(tmp_path, script):
    code, sim, log, con = _run(tmp_path, script=script)
    assert code == 1
    assert prog.ASK_TOUCH not in [q for q, *_ in con.seen]


def test_no_touch_question_after_a_fault_nor_without_a_homing(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject_at(len(OPEN) + 4, "garbled", 1.0)
    code, sim, log, con = _run(tmp_path, sim)
    assert code == 2 and prog.ASK_TOUCH not in [q for q, *_ in con.seen]
    code, sim, log, con = _choose(tmp_path, set())           # nothing run: no homing
    assert prog.ASK_TOUCH not in [q for q, *_ in con.seen]
    code, sim, log, con = _choose(tmp_path, {"home"})       # a homing at rest: touches
    assert [q for q, *_ in con.seen].count(prog.ASK_TOUCH) == 2


def test_the_tester_s_two_stopping_points_now_home_inside_the_window(tmp_path):
    for x, y in ((1104, 110), (1101, 97)):
        sim = sim_mod.SimTable(pos=[float(x), float(y)], jitter=False)
        code, sim, log, con = _choose(tmp_path, {"home", "close"}, sim=sim)
        assert code == 0 and sim.received == OPEN + _lines("home") + _lines("close")
        assert "home/home_wide" in log
    # a homing from 25 mm out that takes longer than 2 s stops right after it
    sim = sim_mod.SimTable(pos=[1102.0, 250.0], jitter=False)
    sim.inject_at(len(OPEN) + 2, "slow_motion", 1.0)
    code, sim, log, con = _choose(tmp_path, {"home", "close"}, sim=sim)
    assert code == 2 and sim.received == OPEN + _lines("home")[:3]
