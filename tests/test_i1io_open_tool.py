"""THE i1iO TESTER PROGRAM 0.2.2 SENDS ONLY THE ELEVEN RECORDED LINES OF BYTES.md,
EVERY STRETCH OF UP TO TEN NEIGHBOURING LINES ONE i1Profiler ALSO SENT, MOVES ONLY BY
ONE HOMING AT THE RESTING PLACE OF A STARTED TABLE, AND STOPS ON ANY DOUBT.

`tools/i1io_open/` is a standalone program for the one tester who owns an i1iO 2
(issue #129). It is WARM ONLY (safety review 2026-11-14): on a started table it
opens it the way i1Profiler does, sends the arm to its resting place once and closes
the table, exactly as i1Profiler ended two recorded sessions (s0 p0 i1 s0, a pause,
s0 f0 f3: S1, R2; safety review after the real run, M3); on a table that has just
been switched on (a0 = 111800) it sends the six reading lines of the opening and
nothing else. 0.2.1 follows the
tester's real run of 0.2.0 (14 Nov 2026): the position check after the homing
uses the whole recorded resting range, and no position is read before the close.
0.2.2 follows the tester's 0.2.1 runs (15 Nov 2026): the homing is sent only from the
places i1Profiler itself sent it from (X 1102, Y 0..47, one unit around them), a busy
table is named and explained, the arm is touched once before anything is opened, and
an early stop says that the table was not closed (the close is not recorded there).
These tests hold its claims:

* BYTES.md and the program's own list agree byte for byte; every write on every
  path, with every injected fault, is in that list; i0 exists nowhere;
* the simulated table, which carries its own copy of the recorded sequences,
  never sees a line out of place (it raises on the spot);
* any fault in a reply stops the run and NOTHING more is written;
* a stop noticed at any moment before a write means that line is never written
  (the stop signals are held around the last check and the write);
* the table's memory answers (its serial number) never reach the log or screen;
* the timeouts are pinned; it is standard-library only.

No real USB is used anywhere: the simulator and a fake pyusb device.
"""
from __future__ import annotations

import ast
import os
import re
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_open"
sys.path.insert(0, str(PKG))

import i1io_open_table as tbl  # noqa: E402
import i1io_open_sim as sim_mod  # noqa: E402
import i1io_open as prog  # noqa: E402

#: The eleven lines, written out here as they appear in the decoded recordings.
RECORDED = {
    ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034",
    ";s022", ";f42b", ";p025", ";i12b", ";f02f", ";f32c",
}
OPEN = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"]
FOLLOW = [";s022", ";f42b", ";f42b", ";f42b", ";f42b"]
HOMING = [";s022", ";p025", ";i12b", ";s022"]
CLOSING = [";s022", ";f02f", ";f32c"]
COLD = list(OPEN)
WARM = OPEN + FOLLOW + HOMING + CLOSING
FORBIDDEN_IDS = ("i0", "m0", "m1", "m2", "c3", "c4", "d1", "a3", "f1", "p1")
#: The recorded stretches the whole run is made of, (seconds, line) as decoded from the
#: recordings (the same lines also at R1 83.666 and R2 378.147 for the opening). Every
#: window of 2 to 10 neighbouring lines of the run must occur in one of them; the work
#: folder's fix_round/tools/ngram_pause_audit.py checks the same against the whole of R1,
#: R2, S1 and S2.
RECORDED_STRETCHES = {
    "R2 34.546-35.385 (a warm opening and its homing)": [
        (34.546, ";a133"), (34.715, ";a133"), (34.731, ";k228"),
        (34.747, ";u8000060000100d1"), (34.853, ";u8000061000068c3"), (34.906, ";a034"),
        (34.932, ";s022"), (34.940, ";f42b"), (34.953, ";f42b"), (34.976, ";f42b"),
        (34.985, ";f42b"), (35.003, ";s022"), (35.017, ";p025"), (35.033, ";i12b"),
        (35.385, ";s022")],
    "S1 4.693-22.951 (after the start-up: homing, pause, close)": [
        (4.693, ";s022"), (4.706, ";f42b"), (4.716, ";f42b"), (4.738, ";f42b"),
        (4.748, ";f42b"), (4.766, ";s022"), (4.780, ";p025"), (4.796, ";i12b"),
        (5.020, ";s022"), (22.919, ";s022"), (22.935, ";f02f"), (22.951, ";f32c")],
    "R2 268.621-361.611 (homing at rest, pause, close)": [
        (268.621, ";s022"), (268.637, ";p025"), (268.653, ";i12b"), (268.909, ";s022"),
        (361.579, ";s022"), (361.594, ";f02f"), (361.611, ";f32c")],
}


def _recorded_window(window):
    """Where the window occurs in a recorded stretch, or None."""
    n = len(window)
    for name, stretch in RECORDED_STRETCHES.items():
        lines = [line for _, line in stretch]
        for j in range(len(lines) - n + 1):
            if lines[j:j + n] == list(window):
                return name, j
    return None


def _windows_ok(seq, longest=10):
    return all(_recorded_window(seq[i:i + n]) for n in range(2, longest + 1)
               for i in range(len(seq) - n + 1))


#: Where the program may wait for the person: only between lines i1Profiler also paused
#: between for long (f4 then s0: up to 162.6 s, R1 550.730-713.337).
LONG_PAUSE_PAIRS = {(";f42b", ";s022"), (";s022", ";s022")}
#: Every position read at rest in R1, R2, S1, S2 and the tester's two real runs
#: (after_real_run/rest_reads.txt plus the logs of 0.1.0 and 0.2.0).
REST_READS = [(1102, 32), (1102, 2), (1102, 5), (1102, 29), (1102, 29), (1102, 47),
              (1102, 36), (1102, 0), (1102, 6), (1102, 24), (1102, 24), (1102, 22),
              (1102, 2), (1102, 4), (1102, 14), (1101, 41), (1102, 37), (1102, 31),
              (1102, 32), (1102, 34), (1102, 25), (1102, 5), (1101, 46), (1101, 46),
              (1102, 19)]


def _bytes_md_lines():
    text = (PKG / "BYTES.md").read_text(encoding="utf-8")
    section = text.split("## Lines to the table", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| (\d+) \| `([^`]+)` \| `([0-9a-f ]+)` \|", section, re.M)
    return {line: hx for _, line, hx in rows}


ALLOWED = {(line + "\r").encode("ascii") for line in _bytes_md_lines()}


def _argv(cold):
    return ("--auto", "--sim", "cold" if cold else "warm")


def _run(tmp_path, sim=None, console=None, argv=None):
    sim = sim or sim_mod.SimTable(cold=False)
    log = tmp_path / "log.txt"
    code = prog.main([*(argv or _argv(sim.cold)), "--log", str(log)], sim_table=sim,
                     console=console or prog.AutoConsole(lambda k, t: None))
    return code, sim, log.read_text(encoding="utf-8")


def _source(name):
    return (PKG / name).read_text(encoding="utf-8")


PROGRAM_FILES = ("i1io_open_table.py", "i1io_open.py", "i1io_open_sim.py")


# ---- the allow-list -------------------------------------------------------------------

def test_bytes_md_lists_exactly_the_programs_eleven_lines():
    listed = _bytes_md_lines()
    assert set(listed) == RECORDED
    assert {v.decode("ascii").rstrip("\r") for v in tbl.WIRE.values()} == RECORDED
    assert tbl.ALLOWED_LINES == ALLOWED
    for line, hx in listed.items():
        assert bytes.fromhex(hx.replace(" ", "")) == (line + "\r").encode("ascii"), line


def test_every_line_has_a_valid_checksum_and_one_cr():
    for line in tbl.WIRE.values():
        assert line.endswith(b"\r") and line.count(b"\r") == 1
        assert tbl.checksum_ok(line[:-1].decode("ascii"))


def test_every_line_names_where_it_was_recorded():
    assert set(tbl.RECORDED_AT) == set(tbl.WIRE)
    for key, where in tbl.RECORDED_AT.items():
        assert re.search(r"\b(S1|R1|R2)\b", where), key


def test_the_gate_refuses_every_other_line():
    for bad in (b";i02c\r", b";m0044e00fa012c0e\r", b";c32f\r", b";c42e\r", b";d1016d35\r",
                b";f12e\r", b";a133", b";a133\r\r", b";A133\r", b";i12b\n", b"", b";p124\r",
                b";u8000060000200d0\r"):
        with pytest.raises(tbl.ForbiddenLine):
            tbl.check_outgoing(bad)


def test_i0_and_every_move_or_unknown_command_are_absent_from_the_package():
    for name in PROGRAM_FILES + ("README.md",):
        src = _source(name)
        for cid in FORBIDDEN_IDS:
            assert f";{cid}" not in src, (name, cid)
            assert f'_frame("{cid}"' not in src, (name, cid)
    assert ";i02c" not in _source("BYTES.md").split("## Never sent")[0]
    frames = re.findall(r'_frame\("([a-z][0-9])"', _source("i1io_open_table.py"))
    assert sorted(set(frames)) == sorted({"a1", "k2", "u8", "a0", "s0", "f4", "p0", "i1",
                                          "f0", "f3"})
    tree = ast.parse(_source("i1io_open_table.py"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_frame"]
    assert all(all(isinstance(a, ast.Constant) for a in c.args) for c in calls)
    assert len(calls) == 11
    assert tbl.MOTION_KEYS == {"home"} and tbl.MAX_MOTIONS == 1 and tbl.MAX_LINES == len(WARM)


def test_the_program_writes_only_in_one_place_and_through_the_gate():
    src = _source("i1io_open_table.py")
    assert src.count("self.t.write(") == 1
    assert src.count("self.dev.write(") == 1
    assert len(re.findall(r"ctrl_transfer\(", src)) == 1
    assert "ctrl_transfer" not in _source("i1io_open.py")
    assert ".write(" not in _source("i1io_open.py").replace("fh.write(", "")


def test_standard_library_only_and_nothing_from_chromiq():
    allowed = {"__future__", "argparse", "datetime", "platform", "signal", "subprocess", "sys",
               "tempfile", "textwrap", "pathlib", "re", "time", "dataclasses", "math", "random",
               "os", "ctypes", "termios", "fcntl", "usb", "i1io_open_table", "i1io_open_sim",
               "plistlib"}
    for name in PROGRAM_FILES:
        tree = ast.parse(_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "").split(".")[0]]
            else:
                continue
            for m in mods:
                assert m in allowed, (name, m)


def test_the_simulator_does_not_import_the_programs_sequences():
    src = _source("i1io_open_sim.py")
    assert "WIRE" not in src
    assert "from i1io_open_table import TransportError, checksum, checksum_ok" in src
    assert sim_mod.REC_COLD == COLD and sim_mod.REC_WARM == WARM
    assert "A BELIEF, not a recording" in src


def test_the_timeouts_and_slow_limits_are_pinned():
    assert tbl.QUICK_TIMEOUT == 1.0
    assert tbl.HOME_TIMEOUT == 12.0
    assert tbl.SLOW_AFTER == {"home": 0.6}
    assert not hasattr(tbl, "START_TIMEOUT")
    assert prog.RELEASE_WAIT_S == 10.0


#: Where i1Profiler itself sent i1 from at rest (work folder homings.txt): first homings
#: and the second homings of the double homings, all X 1102.
DIRECT_STARTS = [(1102, 14), (1102, 22), (1102, 24), (1102, 24), (1102, 32), (1102, 36),
                 (1102, 47), (1102, 0), (1102, 2), (1102, 2)]


def test_the_homing_box_is_the_recorded_starts_of_i1profilers_homings_plus_one_unit():
    """0.2.2: not a range of rest reads (they drift: 0.2.0's Y -3..8 failed at 19, 0.2.1's
    Y -5..50 at 55) but the places i1Profiler sent i1 from at rest, one unit around them."""
    assert tbl.HOME_CLUSTER == tbl.Box(1101, 1103, -1, 48)
    assert sorted(tbl.RECORDED_DIRECT_STARTS) == sorted(DIRECT_STARTS)
    xs = [x for x, _ in DIRECT_STARTS]
    ys = [y for _, y in DIRECT_STARTS]
    assert tbl.HOME_CLUSTER == tbl.Box(min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1)
    assert not hasattr(tbl, "HOMED")          # 0.2.0's Y -3..8 after the homing is withdrawn
    # our own homings on his table started inside; the read that stopped 0.2.1 is outside
    assert tbl.HOME_CLUSTER.contains((1102, 25)) and tbl.HOME_CLUSTER.contains((1101, 46))
    assert not tbl.HOME_CLUSTER.contains((1101, 55))
    # 0.2.1's wider margins are gone
    for p in ((1097, 19), (1107, 19), (1102, 50), (1102, -5)):
        assert not tbl.HOME_CLUSTER.contains(p), p
    # the text shown before the go-ahead names the same box
    assert "X 1101 to 1103, Y -1 to 48" in prog.HOMING_PLACES
    assert "X 1101 to 1103, Y -1 to 48" in tbl.OUTSIDE_TEXT


def test_every_window_of_up_to_ten_lines_of_the_run_was_sent_by_i1profiler(tmp_path):
    """The n-gram audit, n = 2..10, on the lines a simulated run really sends (safety review
    after the real run, M3)."""
    code, sim, _ = _run(tmp_path, sim_mod.SimTable())
    assert code == 0 and sim.received == WARM and len(WARM) == 18
    for n in range(2, 11):
        for i in range(len(WARM) - n + 1):
            assert _recorded_window(WARM[i:i + n]), (n, i, WARM[i:i + n])
    assert _windows_ok(COLD)
    assert WARM[-7:] == [";s022", ";p025", ";i12b", ";s022", ";s022", ";f02f", ";f32c"]
    assert WARM.count(";i12b") == 1
    for a, b in zip(WARM, WARM[1:]):
        if a == ";p025":
            assert b == ";i12b"


def test_the_old_double_homing_would_fail_the_audit():
    """The audit has teeth: 0.2.1's first ending (s0 p0 i1 p0 i1 s0) is not recorded at five
    lines (the reviewer's finding)."""
    old = OPEN + FOLLOW + [";s022", ";p025", ";i12b", ";p025", ";i12b", ";s022"] + CLOSING
    assert not _windows_ok(old, longest=5)


def test_the_person_is_only_asked_where_i1profiler_also_paused(tmp_path):
    sim = sim_mod.SimTable()
    at = []

    class C(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            at.append(len(sim.received))
            return super().ask(question, choices)
    code, sim, _ = _run(tmp_path, sim, console=C(lambda k, t: None))
    assert code == 0 and at
    for n in at:
        if n < len(WARM):
            assert (WARM[n - 1], WARM[n]) in LONG_PAUSE_PAIRS, (n, WARM[n - 1], WARM[n])
    # the look sits between the homing's s0 and the closing s0, where i1Profiler paused
    # 17.9 s (S1) and 92.7 s (R2) in the very stretches the ending is made of
    look = len(OPEN + FOLLOW + HOMING)
    assert look in at
    for name in ("S1", "R2 268"):
        stretch = next(v for k, v in RECORDED_STRETCHES.items() if k.startswith(name))
        j = [line for _, line in stretch].index(";i12b") + 1
        assert stretch[j + 1][0] - stretch[j][0] > 15.0


@pytest.mark.parametrize("key,good,bad", [
    ("identity", "005D010702", "005D010800"), ("k2", "0B600000000013", "0B600000000014"),
    ("arm_mode", "00", "01"), ("f0", "00", "01"), ("f3", "00", "01"),
    ("a0", "130000", "120000")])
def test_every_constant_answer_the_program_relies_on_is_checked_exactly(key, good, bad):
    body = f":${tbl.WIRE[key][1:3].decode()}0{good}"
    assert tbl.parse_done(body + tbl.checksum(body).upper(), key).data == good
    body = f":${tbl.WIRE[key][1:3].decode()}0{bad}"
    with pytest.raises(tbl.ProtocolError):
        tbl.parse_done(body + tbl.checksum(body).upper(), key)


def test_a_homing_answer_later_than_the_timeout_is_a_missing_answer(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject("late", "i1", 12.5)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received[-1] == ";i12b"
    assert "no answer to i1 within the expected time" in log


# ---- the clean paths ------------------------------------------------------------------------

def test_a_started_table_gets_the_recorded_open_homing_and_close(tmp_path):
    code, sim, log = _run(tmp_path, sim_mod.SimTable(cold=False))
    assert code == 0
    assert sim.received == WARM and len(WARM) == 18
    assert sim.motions == 1
    assert "result 0; table warm; 18 lines sent, 1 movements; closed yes" in log


def test_the_homing_follows_s0_and_p0_back_to_back_after_the_yes(tmp_path):
    events = []
    sim = sim_mod.SimTable()

    class C(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            events.append((question, len(sim.received)))
            return super().ask(question, choices)
    code, sim, _ = _run(tmp_path, sim, console=C(lambda k, t: None))
    assert code == 0
    n = next(count for q, count in events if "Send it now" in q)
    assert sim.received[n:n + 4] == [";s022", ";p025", ";i12b", ";s022"]
    assert sim.received[n - 1] == ";f42b"     # the yes comes right after the f4 block (nit 1)


def test_a_cold_table_gets_the_six_reading_lines_and_nothing_else(tmp_path):
    code, sim, log = _run(tmp_path, sim_mod.SimTable(cold=True))
    assert code == 1 and sim.received == OPEN
    assert "result 1; table cold; 6 lines sent, 0 movements; closed no" in log
    assert "needs its start-up, which this version does not send" in log
    assert "open i1Profiler" in log and "Nothing was moved" in log


@pytest.mark.parametrize("pos", [(1101.0, 55.0), (1102.0, 49.0), (1100.0, 20.0),
                                 (1104.0, 20.0), (1102.0, -2.0)])
def test_the_simulator_refuses_a_homing_from_outside_the_recorded_starts(pos):
    """The simulator's own copy of the box (a second, independent line): an i1 from a place
    i1Profiler never sent it from raises at once, whatever the program believes."""
    sim = sim_mod.SimTable(pos=list(pos), jitter=False)
    t = sim_mod.SimTransport(sim)
    for line in OPEN + FOLLOW + [";s022", ";p025"]:
        t.write((line + "\r").encode())
        t.read(1.0)
    with pytest.raises(sim_mod.SimViolation, match="only from the resting place"):
        t.write(b";i12b\r")


def test_the_simulator_refuses_i0_outright():
    sim = sim_mod.SimTable(cold=True)
    t = sim_mod.SimTransport(sim)
    for line in OPEN:
        t.write((line + "\r").encode())
    with pytest.raises(sim_mod.SimViolation):
        t.write(b";i02c\r")


def test_the_homing_waits_for_the_persons_yes(tmp_path):
    for answer in ("no", "stop"):
        con = prog.AutoConsole(lambda k, t: None, script={"Send it now": answer})
        code, sim, _ = _run(tmp_path, sim_mod.SimTable(), console=con)
        assert code == 1 and sim.received == OPEN + FOLLOW


def test_the_arm_moved_away_while_the_person_read_stops_before_i1(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject_at(len(OPEN + FOLLOW) + 1, "drift", 200.0)     # the p0 right before i1
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received == OPEN + FOLLOW + [";s022", ";p025"]
    assert "right before the homing" in log


@pytest.mark.parametrize("x,y,ok", [
    (1101, 46, True), (1102, 19, True), (1102, 48, True), (1102, -1, True), (1101, 47, True),
    (1103, 0, True), (1101, -1, True), (1103, 48, True), (1102, 49, False), (1102, -2, False),
    (1100, 19, False), (1104, 19, False), (1101, 55, False), (1102, 50, False),
    (1097, 19, False), (1102, 300, False)])
def test_the_check_before_the_homing_at_its_edges(tmp_path, x, y, ok):
    """The box on the p0 right before the one homing: every recorded i1Profiler start passes;
    one unit beyond the box, his (1101, 55), or an arm 3 cm out, stops with no homing sent."""
    sim = sim_mod.SimTable(pos=[float(x), float(y)], jitter=False)
    code, sim, log = _run(tmp_path, sim)
    if ok:
        assert code == 0 and sim.received == WARM
    else:
        assert code == 2 and sim.received == OPEN + FOLLOW + HOMING[:2] and sim.motions == 0


def test_tonights_real_replies_now_end_with_the_recorded_close(tmp_path):
    """The tester's table as it answered 0.2.0 on 14 Nov 2026 ((1101, 46) before, homing
    0.352 s from the line, 0.336 s from its acceptance): 0.2.1 reads no position after the
    homing and finishes with s0 f0 f3."""
    code, sim, log = _run(tmp_path, sim_mod.tonights_table())
    assert code == 0 and sim.received == WARM
    assert "right before the homing the arm reports (1101, 46)" in log
    assert "the homing took 0.352 s" in log
    assert "result 0; table warm; 18 lines sent, 1 movements; closed yes" in log


def test_tonights_lines_up_to_the_homing_are_the_ones_his_table_already_answered(tmp_path):
    """Every reply 0.2.0 got from his table, in its form, is what the replay gives; the
    only lines 0.2.1 sends that 0.2.0 did not are the closing s0 f0 f3, and the first s0 p0
    pair before the yes is gone (nit 1)."""
    seen_by_020 = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3",
                   ";a034", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022", ";p025",
                   ";s022", ";p025", ";i12b", ";s022", ";p025"]
    replies_020 = {";a034": ":$a00130000BD", ";f42b": ":$f400078", ";s022": ":$s00CF",
                   ";i12b": ":$i10D8"}
    code, sim, log = _run(tmp_path, sim_mod.tonights_table())
    assert set(WARM[:16]) <= set(seen_by_020)
    recv = re.findall(r"^RECV\s+\S+\s+(:\$\S+)", log, re.M)
    for want in replies_020.values():
        assert want in recv
    assert ":$p00044D002E1F" in recv          # (1101, 46), byte for byte as his table said it
    assert ":$p00044E001331" not in recv      # (1102, 19) after the homing: no longer read


def test_the_arm_check_itself_refuses_anything_but_00():
    """The M3 lesson: parse_done demands 00 too, so this check is tested on its own."""
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    d.opening()
    d.exchange = lambda key, timeout=1.0: tbl.Reply("f4", 0, "01")
    with pytest.raises(tbl.Doubt):
        d._arm()
    assert d.closed_reason


def test_no_line_after_the_homing_but_the_recorded_close(tmp_path):
    """No p0 and no f4 after the homing: the close follows i1, s0 as recorded."""
    code, sim, _ = _run(tmp_path, sim_mod.SimTable())
    last_i1 = len(sim.received) - 1 - sim.received[::-1].index(";i12b")
    assert sim.received[last_i1:] == [";i12b", ";s022", ";s022", ";f02f", ";f32c"]


def test_the_arm_not_seen_at_rest_means_no_closing(tmp_path):
    con = prog.AutoConsole(lambda k, t: None, script={"Is the arm at": "no"})
    code, sim, _ = _run(tmp_path, sim_mod.SimTable(), console=con)
    assert code == 1 and sim.received == WARM[:-3]


# ---- every fault stops everything ------------------------------------------------------------

ONLY_FOR = {"identity": "a1", "k2_other": "k2", "a0_other": "a0", "memory_short": "u8",
            "memory_bad_start": "u8", "free": "f4", "drift": "p0", "blocked": "i1",
            "slow_motion": "i1"}
VALUES = {"drift": 200.0, "blocked": 0.5, "late": 30.0, "status": 3.0, "refuse": 1.0}


def _applies(kind, line, seq=None, index=None):
    if kind == "blocked" and seq is not None and ";p025" not in seq[index:]:
        return False        # after the homing nothing reads the position: the look does
    want = ONLY_FOR.get(kind)
    if want is None:
        return True
    if kind == "memory_bad_start":
        return line == ";u8000060000100d1"
    return line[1:3] == want


@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
@pytest.mark.parametrize("kind", sim_mod.FAULT_KINDS)
def test_any_fault_at_any_line_stops_with_nothing_more_sent(tmp_path, cold, kind):
    seq = COLD if cold else WARM
    for index, line in enumerate(seq):
        sim = sim_mod.SimTable(cold=cold, seed=index)
        sim.inject_at(index, kind, VALUES.get(kind, 0.0))
        code, sim, log = _run(tmp_path, sim)
        assert all((r + "\r").encode() in ALLOWED for r in sim.received)
        assert sim.received == seq[:len(sim.received)]
        assert _windows_ok(sim.received)
        if _applies(kind, line, seq, index):
            assert code == 2, (kind, index, line)
            stop_at = seq.index(";p025", index) if kind == "blocked" else index
            assert len(sim.received) == stop_at + 1, (kind, index, line, sim.received)
            if index < len(seq) - 1:
                assert "closed yes" not in log
        else:
            assert code == (1 if cold else 0), (kind, index, line)
            assert sim.received == seq
        assert sim_mod.FAKE_SERIAL not in log
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in log


def test_a_reply_that_comes_slowly_but_in_time_is_fine(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject("late", "s0", 0.5)
    code, sim, _ = _run(tmp_path, sim)
    assert code == 0 and sim.received == WARM


HOME_AT = len(OPEN + FOLLOW) + 2          # the index of the one i1 in the run


@pytest.mark.parametrize("took,ok", [(0.047, True), (0.336, True), (0.352, True), (0.595, True),
                                     (0.605, False), (0.8, False), (1.55, False), (11.0, False)])
def test_the_homing_window_at_its_edges(tmp_path, took, ok):
    """Safety review M1: every recorded homing from rest took 0.047-0.352 s, so 0.6 s is the
    limit. A homing outside it stops the run with NOTHING further sent (no close)."""
    sim = sim_mod.SimTable(pos=[1102.0, 30.0], home_y=0.0, home_s=took, jitter=False)
    code, sim, log = _run(tmp_path, sim)
    flat = " ".join(log.split())
    if ok:
        assert code == 0 and sim.received == WARM and "closed yes" in log
    else:
        assert code == 2 and sim.received == WARM[:HOME_AT + 1], sim.received
        assert sim.received[-1] == ";i12b" and "closed no" in log
        assert f"i1 took {took:.3f} s, more than the 0.6 s allowed" in log
        assert f"it took {took:.2f} seconds" in flat and "does not close the table" in flat
        assert "the homing has finished" not in flat
        assert "opened and closed the way i1Profiler does it" not in flat


def test_the_reviewers_slow_homing_no_longer_reports_success(tmp_path):
    """The reviewer's case (second_slow.py): a homing 1.55 s late was accepted, the table
    closed and the run reported success. It must stop, unclosed, after the i1."""
    sim = sim_mod.SimTable()
    sim.inject_at(HOME_AT, "late", 1.55)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received[-1] == ";i12b" and len(sim.received) == HOME_AT + 1
    assert "result 2;" in log and "closed no" in log and "1 movements" in log
    assert "the homing has finished" not in " ".join(log.split())


def test_there_is_no_lower_limit_on_the_homing_time():
    """The recordings show a homing from Y 0..2 answered in 0.047 s and no faster time a real
    homing could not beat, so no lower bound is set (decision in the source)."""
    assert set(tbl.SLOW_AFTER) == {"home"}
    assert not any(n.startswith(("FAST", "MIN_HOME")) for n in dir(tbl))
    assert "There is NO lower bound" in _source("i1io_open_table.py")


def test_a_homing_that_takes_far_longer_than_recorded_stops_right_after_it(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject("slow_motion", "i1")
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received[-1] == ";i12b"
    assert "i1 took" in log


def test_an_unknown_a0_answer_stops_right_after_a0(tmp_path):
    for cold in (True, False):
        sim = sim_mod.SimTable(cold=cold)
        sim.inject("a0_other", "a0")
        code, sim, log = _run(tmp_path, sim)
        assert code == 2 and sim.received == OPEN
        assert "120000" in log


def test_the_refusal_seen_on_the_tester_table_stops_with_a_plain_message(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject("refuse", "s0", 1)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received == OPEN + [";s022"]
    assert "refused the line ;s022 (code 1)" in log


def test_the_cable_pulled_after_every_line(tmp_path):
    for cold, seq in ((True, COLD), (False, WARM)):
        for index in range(len(seq)):
            sim = sim_mod.SimTable(cold=cold)
            sim.inject_at(index, "unplug")
            code, sim, _ = _run(tmp_path, sim)
            assert code == 2 and len(sim.received) == index + 1


# ---- stopping --------------------------------------------------------------------------------

@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
def test_ctrl_c_during_any_exchange_sends_nothing_more(tmp_path, cold):
    seq = COLD if cold else WARM
    for index in range(len(seq)):
        sim = sim_mod.SimTable(cold=cold)

        def hook(i, index=index):
            if i == index:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
        code, sim, log = _run(tmp_path, sim)
        assert len(sim.received) == index + 1, (index, sim.received)
        if index < len(seq) - 1:
            assert code == 1, index
            assert "stopped by you" in log
        else:
            assert code in (0, 1)


@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
def test_stop_or_ctrl_c_at_every_question_sends_nothing_more(tmp_path, cold):
    for n in range(1, 10):
        sim = sim_mod.SimTable(cold=cold)
        con = prog.AutoConsole(lambda k, t: None, interrupt_at=n)
        code, sim, _ = _run(tmp_path, sim, console=con)
        sent = len(sim.received)
        seq = COLD if cold else WARM
        assert sim.received == seq[:sent]
        if cold:
            assert sent == 6 and code == 1
            continue
        if code == 0:
            assert sim.received == WARM
            continue
        assert code == 1
        assert sent in (11, 15)       # before the homing's s0, or before the closing


def _opened_warm():
    sim = sim_mod.SimTable()
    tr = sim_mod.SimTransport(sim)
    d = tbl.Table(tr)
    d.opening()
    d.follow_up()
    return sim, tr, d


def test_a_stop_during_the_listening_before_a_line_means_exchange_never_writes(monkeypatch):
    """The stop check right after the 50 ms listening (planted fault: remove it)."""
    sim, tr, d = _opened_warm()
    real_read = tr.read

    def read(timeout):
        d.request_stop()
        return real_read(timeout)
    tr.read = read
    monkeypatch.setattr(tbl.Table, "_write",
                        lambda self, line: pytest.fail(f"_write reached after a stop: {line!r}"))
    with pytest.raises(tbl.Stopped):
        d.exchange("status")


def test_a_stop_noticed_inside_write_before_the_wire_writes_nothing(monkeypatch):
    """Safety review M1 (the reviewer's test, on the homing's lines)."""
    sim, tr, d = _opened_warm()
    n = len(tr.writes)
    real_check = tbl.check_outgoing

    def check(line):
        d.request_stop()
        return real_check(line)
    monkeypatch.setattr(tbl, "check_outgoing", check)
    with pytest.raises((tbl.Stopped, tbl.Doubt)):
        d.home()
    assert len(tr.writes) == n, tr.writes[n:]


def test_the_stop_signals_are_held_while_a_line_is_written():
    sim, tr, d = _opened_warm()
    seen = []
    real_write = tr.write

    def write(data):
        seen.append(signal.SIGINT in signal.pthread_sigmask(signal.SIG_BLOCK, []))
        return real_write(data)
    tr.write = write
    d.exchange("status")
    assert seen == [True]
    assert signal.SIGINT not in signal.pthread_sigmask(signal.SIG_BLOCK, [])


def test_a_real_sigint_while_waiting_for_the_homing_sends_nothing_more(tmp_path):
    """The reviewer's test, moved from i0 to i1: a real SIGINT through the handler."""
    sim = sim_mod.SimTable()
    fired = {"done": False}
    real_pending = sim.pending

    def pending(until):
        if sim.received and sim.received[-1] == ";i12b" and not fired["done"]:
            fired["done"] = True
            os.kill(os.getpid(), signal.SIGINT)
        return real_pending(until)
    sim.pending = pending
    code, sim, _ = _run(tmp_path, sim)
    assert fired["done"] and sim.received[-1] == ";i12b" and code == 1


def test_reviewer_ctrl_c_at_every_question(tmp_path):
    for cold in (True, False):
        for k in range(1, 12):
            sim = sim_mod.SimTable(cold=cold)
            before = {}

            class C(prog.AutoConsole):
                def _maybe_interrupt(self):
                    self.asked += 1
                    if self.asked == k:
                        before["n"] = len(sim.received)
                        raise KeyboardInterrupt
            _run(tmp_path, sim, console=C(lambda a, b: None))
            if "n" in before:
                assert len(sim.received) == before["n"], (cold, k)


def test_a_blocked_homing_is_not_seen_by_the_program_but_by_the_persons_look(tmp_path):
    """The weakest point, pinned: no position is read after the homing, so a homing that
    reports done in time but ended elsewhere is caught only by the person's look."""
    sim = sim_mod.SimTable()
    sim.inject_at(len(OPEN + FOLLOW) + 2, "blocked", 0.5)
    con = prog.AutoConsole(lambda k, t: None, script={"Is the arm at": "no"})
    code, sim, log = _run(tmp_path, sim, console=con)
    assert code == 1 and sim.received == WARM[:-3] and "closed no" in log


# ---- the touch questions: before and after the USB connection is let go --------------------

def test_the_touch_questions_come_after_the_close_once_before_and_once_after_the_release(tmp_path):
    seen = []
    sim = sim_mod.SimTable()

    class C(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            if question == prog.ASK_TOUCH:
                seen.append((len(sim.received), self.transport.closed))
            return super().ask(question, choices)
    con = C(lambda k, t: None)
    real_init = sim_mod.SimTransport.__init__

    def init(self, table=None):
        real_init(self, table)
        con.transport = self
    sim_mod.SimTransport.__init__ = init
    try:
        code, sim, log = _run(tmp_path, sim, console=con)
    finally:
        sim_mod.SimTransport.__init__ = real_init
    assert code == 0 and seen == [(len(WARM), False), (len(WARM), True)]
    first = log.index("ASK    " + prog.ASK_TOUCH)
    let_go = log.index("INFO   the program has let go of the table's USB connection")
    assert first < let_go < log.index("ASK    " + prog.ASK_TOUCH, first + 1)
    assert "('arm held? (while the program still held the USB connection)', 'holds')" in log


def test_no_touch_question_while_a_movement_may_still_run_or_the_arm_was_not_at_rest(tmp_path):
    for script, inject in (({}, ("no_done", "i1")), ({"Is the arm at": "no"}, None)):
        sim = sim_mod.SimTable()
        if inject:
            sim.inject(*inject)
        asked = []

        class C(prog.AutoConsole):
            def ask(self, question, choices=("yes", "no")):
                asked.append(question)
                return super().ask(question, choices)
        code, sim, log = _run(tmp_path, sim, console=C(lambda k, t: None, script=script))
        assert prog.ASK_TOUCH not in asked and "arm held?" not in log
        assert prog.LOOSE_ADVICE not in log.replace("\n", " ")


class _Asked(prog.AutoConsole):
    """Records every question (and free-text question) with the lines sent so far."""

    def __init__(self, sim, **kw):
        super().__init__(lambda k, t: None, **kw)
        self.sim, self.seen = sim, []

    def ask(self, question, choices=("yes", "no")):
        self.seen.append((question, len(self.sim.received)))
        return super().ask(question, choices)

    def text(self, question):
        self.seen.append((question, len(self.sim.received)))
        return super().text(question)


def _touches(con):
    return [q for q, _ in con.seen if q == prog.ASK_TOUCH]


def test_ctrl_c_at_the_first_touch_ends_cleanly_without_the_wait_or_another_question(
        tmp_path, monkeypatch):
    """Safety review S2: a Ctrl-C at the first touch question means no 10 s wait, no second
    touch, no report questions; only the closing text. Nothing is sent either way."""
    monkeypatch.setattr(prog.time, "sleep", lambda s: pytest.fail("waited after a Ctrl-C"))
    sim = sim_mod.SimTable()
    con = _Asked(sim, interrupt_at=3)            # 1 go ahead, 2 look, 3 first touch
    code, sim, log = _run(tmp_path, sim, console=con)
    assert code == 0 and sim.received == WARM
    assert len(con.seen) == 3 and len(_touches(con)) == 1     # go ahead, look, first touch
    assert "('arm held? (while the program still held the USB connection)', " \
           "'stopped with Ctrl-C')" in log
    assert "about ten seconds after" not in log.split("INFO   result")[1].split("answers")[0]
    assert "stopped by you: no more questions" in log
    assert "Did you hear anything unusual" not in log
    assert " ".join(prog.LOOSE_ADVICE.split()) in " ".join(log.split())   # the closing text


def test_ctrl_c_at_the_first_touch_on_the_real_path_skips_the_ten_second_wait(tmp_path):
    """The same through after_the_run with real=True: the wait would be a 10 s sleep."""
    sim = sim_mod.SimTable()
    tr = sim_mod.SimTransport(sim)
    table = tbl.Table(tr)
    con = _Asked(sim, interrupt_at=3)
    r = prog.Run(table, con, simulated=False)
    assert r.go() == 0
    slept = []
    real_sleep = prog.time.sleep
    prog.time.sleep = lambda s: slept.append(s)
    try:
        r.after_the_run(tr, real=True)
    finally:
        prog.time.sleep = real_sleep
    assert slept == [] and len(_touches(con)) == 1 and tr.closed and r.stopped_by_person


def test_ctrl_c_during_the_ten_second_wait_asks_nothing_more(tmp_path):
    sim = sim_mod.SimTable()
    tr = sim_mod.SimTransport(sim)
    con = _Asked(sim)
    r = prog.Run(tbl.Table(tr), con, simulated=False)
    assert r.go() == 0

    def sleep(s):
        raise KeyboardInterrupt
    real_sleep = prog.time.sleep
    prog.time.sleep = sleep
    try:
        r.after_the_run(tr, real=True)
    finally:
        prog.time.sleep = real_sleep
    assert len(_touches(con)) == 1 and r.stopped_by_person
    assert not any("Did you hear" in q for q, _ in con.seen)


def test_ctrl_c_at_the_second_touch_asks_nothing_more(tmp_path):
    sim = sim_mod.SimTable()
    con = _Asked(sim, interrupt_at=4)
    code, sim, log = _run(tmp_path, sim, console=con)
    assert code == 0 and sim.received == WARM and len(_touches(con)) == 2
    assert len(con.seen) == 4 and "Did you hear anything unusual" not in log


@pytest.mark.parametrize("how", ["ctrl-c at the look", "stop at the look", "stop at the go-ahead",
                                 "ctrl-c during an exchange", "slow homing", "refused homing"])
def test_no_touch_question_after_a_stop_or_without_a_yes_at_rest(tmp_path, how):
    """Safety review S2: the touches only when nothing moved or the person's last word was
    "yes, at its resting place"; never after Ctrl-C or "stop"."""
    sim = sim_mod.SimTable()
    kw = {}
    if how == "ctrl-c at the look":
        kw["interrupt_at"] = 2
    elif how == "stop at the look":
        kw["script"] = {"Is the arm at": "stop"}
    elif how == "stop at the go-ahead":
        kw["script"] = {"Send it now": "stop"}
    elif how == "slow homing":
        sim.inject_at(HOME_AT, "late", 1.0)
    elif how == "refused homing":
        sim.inject_at(HOME_AT, "refuse", 1.0)
    else:
        def hook(i):
            if i == HOME_AT + 1:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
    con = _Asked(sim, **kw)
    code, sim, log = _run(tmp_path, sim, console=con)
    assert code in (1, 2) and not _touches(con), how
    assert "arm held?" not in log
    if how.startswith(("ctrl-c", "stop")):
        assert "Did you hear anything unusual" not in log, how


def test_may_touch_itself_refuses_while_a_movement_is_unconfirmed():
    """The guard on its own (a planted fault removing it survived the fix round's first
    mutation pass: since S2 an unconfirmed movement never reaches the look, so the yes-at-rest
    rule hides it). Even with a yes at rest, an unreported movement end means no touch."""
    sim = sim_mod.SimTable()
    r = prog.Run(tbl.Table(sim_mod.SimTransport(sim)), prog.AutoConsole(lambda k, t: None),
                 simulated=True)
    r.d.lines_sent, r.d.motions_sent, r.seen_at_rest = 18, 1, True
    assert r.may_touch() is True
    r.d.motion_unconfirmed = True
    assert r.may_touch() is False
    r.d.motion_unconfirmed, r.stopped_by_person = False, True
    assert r.may_touch() is False
    r.stopped_by_person, r.seen_at_rest = False, None
    assert r.may_touch() is False
    r.d.motions_sent = 0
    assert r.may_touch() is True


def test_the_touches_are_still_asked_when_nothing_moved(tmp_path):
    for sim, script in ((sim_mod.SimTable(cold=True), {}),
                        (sim_mod.SimTable(), {"Send it now": "no"})):
        con = _Asked(sim, script=script)
        code, sim, log = _run(tmp_path, sim, console=con)
        assert code == 1 and sim.motions == 0 and len(_touches(con)) == 2


def test_the_run_is_closed_for_sending_before_the_first_touch_question(tmp_path, monkeypatch):
    """Review N1 (a planted fault survived): the final lock at the end of go() is pinned.
    Before the first touch the table refuses every line without writing it."""
    seen = []
    real_touch = prog.Run.touch

    def touch(self, when):
        seen.append(self.d.closed_reason)
        n = len(self.d.t.writes)
        with pytest.raises(tbl.Doubt):
            self.d.exchange("status")
        assert len(self.d.t.writes) == n
        return real_touch(self, when)
    monkeypatch.setattr(prog.Run, "touch", touch)
    code, sim, _ = _run(tmp_path, sim_mod.SimTable())
    assert code == 0 and sim.received == WARM
    assert seen and seen[0] == "the run is over"


def test_the_touch_question_is_gentle_and_names_the_direction_and_the_feel():
    """Safety review S3 and N2 (a planted fault removing "Do not force it" survived): the
    gentle wording, the direction (towards the front, the way the arm travels) and what
    holds and free feel like are pinned, in the program and in the README."""
    q = prog.ASK_TOUCH
    readme = " ".join(_source("README.md").split())
    for text in (q, readme):
        for needed in ("very gently", "towards the front of the table",
                       "the way the arm travels over the table", "about a millimetre",
                       "let go at once", "Do not force it.", "resists your finger",
                       "springs back when you let go", "almost no effort"):
            assert needed in text, needed
    assert "sideways" not in q and "sideways" not in readme
    assert prog.TOUCH_CHOICES == ("holds", "free", "not sure", "skip")
    assert '"holds"' in q and '"free"' in q


def test_the_wait_before_the_second_touch_is_only_for_the_real_table(tmp_path, monkeypatch):
    monkeypatch.setattr(prog.time, "sleep", lambda s: pytest.fail("waited in a practice run"))
    code, sim, _ = _run(tmp_path, sim_mod.SimTable())
    assert code == 0


def test_the_i1profiler_check_names_what_it_found(monkeypatch):
    monkeypatch.setattr(prog, "_pgrep", lambda *a: ["123"] if a[0] == "-f" else [])
    assert prog.i1profiler_matches() == [
        "a process inside i1Profiler.app (i1Profiler itself or one of its helpers)"]
    assert prog.i1profiler_running() is True


def test_no_stale_count_word_anywhere():
    for name in PROGRAM_FILES + ("README.md", "BYTES.md"):
        assert "twelve" not in _source(name).lower(), name


# ---- privacy ---------------------------------------------------------------------------------

def test_the_memory_answers_never_reach_the_log_or_the_screen(tmp_path, capsys):
    code, sim, log = _run(tmp_path, sim_mod.SimTable())
    out = capsys.readouterr().out
    for text in (log, out):
        assert sim_mod.FAKE_SERIAL not in text
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in text
        assert "not written down" in text
    assert "6801000056312E31" not in log


def test_a_damaged_memory_answer_is_described_never_echoed(tmp_path):
    for kind in ("bad_checksum_memory", "memory_short", "memory_bad_start"):
        sim = sim_mod.SimTable()
        sim.inject(kind, "u8")
        code, sim, log = _run(tmp_path, sim)
        assert code == 2
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in log
        assert sim_mod.FAKE_SERIAL not in log


def test_show_never_echoes_long_or_memory_lines():
    assert tbl.show(":$s00CF") == "':$s00CF'"
    assert "bytes" in tbl.show(":$u80" + "AB" * 30)
    assert "bytes" in tbl.show(":$u80AB")
    assert "bytes" in tbl.show("X" * 40)


# ---- plan, dry run, practice: nothing is sent -----------------------------------------------

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


def test_the_practice_run_never_opens_the_real_table(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl, "open_table", lambda: pytest.fail("opened"))
    for cold in (True, False):
        code, _, _ = _run(tmp_path, sim_mod.SimTable(cold=cold))
        assert code == (1 if cold else 0)


def test_i1profiler_is_looked_for_by_name_and_by_app_path(monkeypatch):
    calls = []
    monkeypatch.setattr(prog, "_pgrep", lambda *a: calls.append(a) or [])
    assert prog.i1profiler_running() is False
    assert ("-x", "-i", "i1Profiler") in calls
    assert ("-f", "i1Profiler.app/Contents/MacOS") in calls


# ---- the USB layer (a fake pyusb device; no real USB) ---------------------------------------

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
    util = FakeUtil()
    t = tbl.FtdiUsb(dev, FakeCore, util)
    t.setup()
    return util, t


def test_setup_sends_exactly_the_five_recorded_ftdi_requests(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    assert dev.ctrl == [(0x40, 0x00, 0x0000, 0, None), (0x40, 0x00, 0x0001, 0, None),
                        (0x40, 0x00, 0x0002, 0, None), (0x40, 0x03, 0x0034, 0, None),
                        (0x40, 0x04, 0x0008, 0, None)]
    assert util.calls == [("claim", 0)]


@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
def test_a_whole_run_over_the_ftdi_path_with_the_long_memory_answer_in_packets(monkeypatch, cold):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(cold=cold)
    util, t = _ftdi(dev)
    table = tbl.Table(t)
    run = prog.Run(table, prog.AutoConsole(lambda k, tx: None), simulated=True)
    assert run.go() == (1 if cold else 0)
    assert dev.sim.received == (COLD if cold else WARM)
    t.close()
    assert ("release", 0) in util.calls and ("dispose",) in util.calls


def test_the_ftdi_transport_refuses_any_other_line_itself(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    with pytest.raises(tbl.ForbiddenLine):
        t.write(b";m0044e00fa012c0e\r")
    assert dev.sim.received == []


def test_a_line_error_from_the_chip_stops_everything(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(line_status=0x68)
    util, t = _ftdi(dev)
    table = tbl.Table(t)
    with pytest.raises(tbl.Doubt):
        table.opening()
    assert table.closed_reason and len(dev.sim.received) <= 1


def test_the_real_run_needs_a_person_at_the_keyboard(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", open(__file__, encoding="utf-8"))
    log = tmp_path / "real.txt"
    assert prog.main(["--real", "--log", str(log)]) == 2
    assert "typed by a person" in log.read_text(encoding="utf-8")


# ---- the package --------------------------------------------------------------------------

def test_the_zip_is_reproducible_and_runs_from_a_clean_folder(tmp_path):
    build = ROOT / "scripts" / "build_i1io_open_zip.py"
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
        assert names == sorted(["README.md", "BYTES.md", "i1io_open.py", "i1io_open_table.py",
                                "i1io_open_sim.py", "LICENSE"])
        z.extractall(tmp_path / "x")
    folder = next((tmp_path / "x").iterdir())
    for sim in ("cold", "warm"):
        r = subprocess.run([sys.executable, "-I", "i1io_open.py", "--auto", "--sim", sim,
                            "--log", f"run-{sim}.txt"], cwd=folder, capture_output=True,
                           text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
        assert r.returncode == (1 if sim == "cold" else 0), r.stdout + r.stderr
        assert "Traceback" not in r.stdout + r.stderr


def test_the_timing_text_is_his_tables_and_the_light_is_explained(tmp_path):
    """Safety review S1: no 'twentieth of a second' (there is one homing, and on his table it
    took 0.352 s), and the missing light of the i1Pro 2 is said before the movement."""
    for name in PROGRAM_FILES + ("README.md", "BYTES.md"):
        text = " ".join(_source(name).split()).lower()
        assert "twentieth" not in text and "quarter of a second" not in text, name
    code, sim, log = _run(tmp_path, sim_mod.SimTable())
    flat = " ".join(log.split())
    go = flat.index("Send it now?")
    assert flat.index("about a third of a second") < go
    assert flat.index(" ".join(prog.NO_LIGHT.split())) < go
    assert "never talks to the i1Pro 2" in prog.NO_LIGHT
    assert "light will not come on" in " ".join(_source("README.md").split())


def test_the_loose_arm_advice_has_no_power_cycle(tmp_path):
    """Safety review M2: he described the start after a power cycle as a hard movement, so the
    loose-arm advice (screen, log, README) is only: leave it, open i1Profiler once, let it
    start the table, quit it. The power switch stays the emergency stop during a movement,
    and the power cycle stays only for a movement that never reported its end."""
    advice = " ".join(prog.LOOSE_ADVICE.split())
    assert advice.endswith("Leave the arm where it is, at its resting place. Then open "
                           "i1Profiler once, let it start the table as usual, and quit it.")
    readme = " ".join(_source("README.md").split())
    loose = readme.split("### If the arm is loose afterwards", 1)[1].split("###", 1)[0]
    for text in (advice, loose):
        for power in ("switch the table off", "switch it on", "switched off and on",
                      "wait about ten seconds"):
            assert power not in text, power
    code, sim, log = _run(tmp_path, sim_mod.SimTable())
    said = " ".join(line[7:] for line in log.splitlines() if line.startswith("SAY"))
    assert advice in " ".join(said.split())
    assert "switch the table off at its power switch" in prog.PLUG
    assert "switch the table off, wait ten seconds" in prog.RECOVERY_UNFINISHED
    assert "switch the table off" not in prog.RECOVERY
    assert "Switch the table off or pull its power plug" in readme


def test_the_readme_names_every_line_and_says_what_matters():
    readme = _source("README.md")
    for line in RECORDED:
        assert line in readme, line
    for needed in ("power switch", "Ctrl-C", "--plan", "not from X-Rite", "unofficial",
                   "hands and everything else away from the arm",
                   "folder you started it from", "has just been switched on",
                   "loose", "Leave the arm where it is, at its resting place. Then open "
                   "i1Profiler once, let it start the table as usual, and quit it."):
        assert needed in " ".join(readme.split()), needed
    assert "—" not in readme
    assert not re.search(r"macOS 2\d|Python 3\.1\d", readme)


# ---- 0.2.2: after the tester's 0.2.1 runs of 15 Nov 2026 -------------------------------------

def test_todays_real_replies_stop_before_the_homing_as_planned(tmp_path):
    """His table on 15 Nov 2026 (run 5): a0 130000, f4 00 x4, the arm at (1101, 55). 0.2.2
    stops there as 0.2.1 did (13 lines, nothing moved, no close), but now says why it is a
    planned ending, how to try again, that the table was not closed and why, and still asks
    the two touch questions (nothing moved)."""
    con = _Asked(sim_mod.todays_table())
    code, sim, log = _run(tmp_path, con.sim, console=con)
    assert code == 2 and sim.received == OPEN + FOLLOW + [";s022", ";p025"] and sim.motions == 0
    flat = " ".join(log.split())
    assert "right before the homing the arm reports (1101, 55)" in log
    assert "X 1101, Y 55" in flat and "planned endings" in flat
    for text in (prog.AGAIN_TEXT, prog.NOT_CLOSED):
        assert " ".join(text.split()) in flat
    assert "result 2; table warm; 13 lines sent, 0 movements; closed no" in log
    assert len(_touches(con)) == 2


@pytest.mark.parametrize("how", ["outside", "slow homing", "look no", "go-ahead no"])
def test_a_warm_stop_says_the_table_was_not_closed_and_sends_no_close(tmp_path, how):
    sim = sim_mod.SimTable()
    script = {}
    if how == "outside":
        sim = sim_mod.SimTable(pos=[1102.0, 49.0], jitter=False)
    elif how == "slow homing":
        sim.inject_at(HOME_AT, "late", 1.0)
    elif how == "look no":
        script = {"Is the arm at": "no"}
    else:
        script = {"Send it now": "no"}
    code, sim, log = _run(tmp_path, sim, console=prog.AutoConsole(lambda k, t: None,
                                                                  script=script))
    assert code in (1, 2) and ";f02f" not in sim.received and ";f32c" not in sim.received
    assert " ".join(prog.NOT_CLOSED.split()) in " ".join(log.split()), how
    assert (" ".join(prog.AGAIN_TEXT.split()) in " ".join(log.split())) == (how == "outside")


def test_no_not_closed_text_after_a_complete_run_or_on_a_cold_table(tmp_path):
    for sim in (sim_mod.SimTable(), sim_mod.SimTable(cold=True)):
        code, sim, log = _run(tmp_path, sim)
        assert " ".join(prog.NOT_CLOSED.split()) not in " ".join(log.split())


def test_the_go_ahead_says_the_position_check_may_stop_the_run(tmp_path):
    code, sim, log = _run(tmp_path, sim_mod.SimTable())
    flat = " ".join(log.split())
    go = flat.index("Send it now?")
    assert flat.index(prog.HOMING_PLACES) < go
    assert flat.index("may well stop the run") < go


def test_f4_is_no_longer_called_a_motor_reading():
    for name in PROGRAM_FILES + ("README.md", "BYTES.md"):
        text = " ".join(_source(name).split())
        assert "its motors hold the arm (f4 = 00)" not in text, name
        assert "do the motors hold the arm? (must be 00)" not in text, name
    assert not hasattr(tbl, "ARM_HELD") and tbl.F4_RECORDED == "00"
    assert "does not tell whether the motors hold the arm" in prog.MEANING["arm_mode"]


# -- the touch before anything is opened, and the real path with a fake table --------------

class _TTY:
    def isatty(self):
        return True

    def fileno(self):
        raise OSError


def _real(tmp_path, monkeypatch, open_table, con=None, events=None):
    """main(--real) with every outside thing replaced: no USB, no pgrep, no ioreg, no sleep."""
    events = [] if events is None else events
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(tbl, "check_usb_available", lambda: "pyusb test; libusb test")
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog, "xrite_helpers_running", lambda: ["xrdd"])
    monkeypatch.setattr(tbl, "usb_holders", lambda: events.append("ioreg") or
                        ["connected: xrdd (pid 321)", "exclusive owner: SomeApp (pid 654)"])
    monkeypatch.setattr(tbl, "open_table", lambda: events.append("open") or open_table())
    monkeypatch.setattr(prog.time, "sleep", lambda s: None)
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)

    class C(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            events.append(("ask", question))
            return super().ask(question, choices)

        def text(self, question):
            events.append(("text", question))
            return super().text(question)
    con = con or C(lambda k, t: None)
    log = tmp_path / "real.txt"
    code = prog.main(["--real", "--log", str(log)], console=con)
    return code, log.read_text(encoding="utf-8"), events


def _fake_ftdi(monkeypatch, cold=False, pos=None):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(cold=cold)
    if pos is not None:
        dev.sim.pos = list(pos)
        dev.sim.jitter = False
    holder = {}

    def opener():
        util, t = _ftdi(dev)
        holder["util"] = util
        return t
    return dev, opener, holder


def test_the_first_touch_comes_before_anything_is_opened(tmp_path, monkeypatch):
    dev, opener, holder = _fake_ftdi(monkeypatch)
    code, log, events = _real(tmp_path, monkeypatch, opener)
    assert code == 0 and dev.sim.received == WARM
    touches = [i for i, e in enumerate(events) if e == ("ask", prog.ASK_TOUCH)]
    assert len(touches) == 3
    opened = events.index("open")
    assert touches[0] < opened < touches[1] < touches[2]
    assert events[touches[0] + 1] == ("text", prog.ASK_MINUTES)
    # nothing at all reached the table before the open: the fake device saw nothing earlier
    assert "('arm held? (before the program opened anything)', 'holds')" in log
    assert "('minutes since i1Profiler was quit', '')" in log
    assert "macOS lists for the table before opening" in log
    assert ("release", 0) in holder["util"].calls


def test_a_stop_at_the_first_touch_opens_nothing(tmp_path, monkeypatch):
    dev, opener, _ = _fake_ftdi(monkeypatch)
    con = prog.AutoConsole(lambda k, t: None, interrupt_at=6)    # 5 questions, then the touch
    code, log, events = _real(tmp_path, monkeypatch, opener, con=con)
    assert code == 1 and "open" not in events and dev.sim.received == []
    assert "stopped with Ctrl-C (or the Terminal window was closed) before the table was " \
           "opened; nothing was sent" in log


def test_ctrl_c_at_a_start_question_is_written_to_the_log(tmp_path, monkeypatch):
    """The tester's first run of 0.2.1 ended at a start question with nothing in its log."""
    dev, opener, _ = _fake_ftdi(monkeypatch)
    for at in (1, 5):
        con = prog.AutoConsole(lambda k, t: None, interrupt_at=at)
        code, log, events = _real(tmp_path, monkeypatch, opener, con=con)
        assert code == 1 and "open" not in events
        assert "stopped with Ctrl-C" in log and "nothing was sent" in log


def test_a_closed_window_before_the_table_is_opened_is_logged(tmp_path, monkeypatch):
    dev, opener, _ = _fake_ftdi(monkeypatch)

    class Hup(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            if "power switch" in question:
                signal.raise_signal(signal.SIGHUP)
            return super().ask(question, choices)
    unhandled = []

    def guard(signum, frame):              # only reached if the program installed nothing
        unhandled.append(signum)
    before = signal.signal(signal.SIGHUP, guard)
    try:
        code, log, events = _real(tmp_path, monkeypatch, opener, con=Hup(lambda k, t: None))
        assert signal.getsignal(signal.SIGHUP) is guard       # put back as it was found
    finally:
        signal.signal(signal.SIGHUP, before)
    assert not unhandled, "the program did not handle the closed window itself"
    assert code == 1 and "open" not in events and "stopped with Ctrl-C" in log


def test_todays_table_on_the_real_path_with_all_three_touches(tmp_path, monkeypatch):
    dev, opener, holder = _fake_ftdi(monkeypatch, pos=(1101.0, 55.0))
    code, log, events = _real(tmp_path, monkeypatch, opener)
    assert code == 2 and dev.sim.received == OPEN + FOLLOW + [";s022", ";p025"]
    assert len([e for e in events if e == ("ask", prog.ASK_TOUCH)]) == 3
    assert "13 lines sent, 0 movements; closed no" in log
    assert ("release", 0) in holder["util"].calls


# -- a busy or missing table ----------------------------------------------------------------

class BusyUtil(FakeUtil):
    def __init__(self, code=-3, errno=13):
        super().__init__()
        self.code, self.errno = code, errno

    def claim_interface(self, dev, n):
        exc = USBError("Access denied (insufficient permissions)", self.errno)
        exc.backend_error_code = self.code
        raise exc


@pytest.mark.parametrize("code,errno,kind", [(-3, 13, "busy"), (-6, 16, "busy"),
                                             (None, 13, "busy"), (-4, 19, "gone"),
                                             (-1, 5, "other"), (None, None, "other")])
def test_an_open_that_macos_refuses_is_classified(monkeypatch, code, errno, kind):
    dev = FakeDev()
    t = tbl.FtdiUsb(dev, FakeCore, BusyUtil(code, errno))
    with pytest.raises(tbl.TransportError) as info:
        t.setup()
    exc = info.value
    assert isinstance(exc, tbl.TableBusy) == (kind == "busy")
    assert "claim_interface failed" in str(exc)
    if kind == "busy":
        assert exc.step == "claim_interface" and str(exc).startswith(tbl.BUSY_TEXT)
    elif kind == "gone":
        assert str(exc).startswith(tbl.GONE_TEXT)
    assert "Nothing was sent" in str(exc)
    assert dev.ctrl == [] and dev.sim.received == []      # not even the FTDI set-up


def test_a_busy_table_is_named_and_explained_without_touching_any_process(tmp_path, monkeypatch):
    def opener():
        t = tbl.FtdiUsb(FakeDev(), FakeCore, BusyUtil())
        t.setup()
    code, log, events = _real(tmp_path, monkeypatch, opener)
    assert code == 2
    assert events.count("ioreg") == 2          # before opening, and after the refusal
    flat = " ".join(log.split())
    assert tbl.BUSY_TEXT in flat and " ".join(tbl.BUSY_STEPS.split()) in flat
    assert "macOS names: exclusive owner: SomeApp (pid 654)." in flat
    assert "opening refused by macOS at claim_interface (libusb -3)" in log
    assert "lines sent" not in log.split("INFO   opening refused")[1]
    for text in (tbl.BUSY_TEXT, tbl.BUSY_STEPS, prog.I1PROFILER_RUNNING):
        for bad in ("kill", "pkill", "killall", "launchctl", "Activity Monitor", "Force Quit",
                    "sudo"):
            assert bad.lower() not in text.lower(), bad
    assert "never touches them" in tbl.BUSY_STEPS


def test_the_program_runs_no_other_command_than_pgrep_and_ioreg():
    """The only outside programs: pgrep (looking for i1Profiler by name) and ioreg (macOS's
    list of who holds the table), both read only. Nothing that signals or ends a process."""
    for name in PROGRAM_FILES:
        src = _source(name)
        for bad in ("os.kill", "signal.pthread_kill", "killpg", "pkill", "killall",
                    "launchctl", "os.system", "Popen("):
            assert bad not in src, (name, bad)
    runs = re.findall(r"subprocess\.run\(\s*(\[[^\]]*\])", _source("i1io_open.py")
                      + _source("i1io_open_table.py"))
    assert runs == ['["pgrep", *args]',
                    '["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"]']


def test_usb_holders_runs_ioreg_read_only_with_a_time_limit(monkeypatch):
    seen = {}

    class R:
        stdout = b""

    def fake_run(args, **kw):
        seen["args"], seen["kw"] = args, kw
        return R()
    monkeypatch.setattr(tbl.sys, "platform", "darwin")
    import subprocess as sp
    monkeypatch.setattr(sp, "run", fake_run)
    assert tbl.usb_holders() == []
    assert seen["args"] == ["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"]
    assert seen["kw"]["timeout"] == 5

    def boom(args, **kw):
        raise sp.TimeoutExpired(args, 5)
    monkeypatch.setattr(sp, "run", boom)
    assert tbl.usb_holders() == ["(macOS's list could not be read)"]


def _plist(table_extra=None):
    import plistlib
    uc_ours = {"IOObjectClass": "IOUSBHostDeviceUserClient", "IOUserClientCreator": "pid 77, Python"}
    uc_xrdd = {"IOObjectClass": "IOUSBHostInterfaceUserClient",
               "IOUserClientCreator": "pid 321, xrdd"}
    intf = {"IOObjectClass": "IOUSBHostInterface", "UsbExclusiveOwner": "pid 654, SomeApp",
            "IORegistryEntryChildren": [uc_xrdd]}
    table = {"IOObjectClass": "IOUSBHostDevice", "idVendor": 0x0971, "idProduct": 0x2004,
             "USB Serial Number": sim_mod.FAKE_SERIAL, "kUSBSerialNumberString":
             sim_mod.FAKE_SERIAL, "IORegistryEntryChildren": [intf, uc_ours]}
    table.update(table_extra or {})
    i1pro = {"IOObjectClass": "IOUSBHostDevice", "idVendor": 0x0971, "idProduct": 0x2000,
             "USB Serial Number": "OTHERSERIAL", "UsbExclusiveOwner": "pid 999, NotTheTable"}
    hub = {"IOObjectClass": "IOUSBHostDevice", "idVendor": 0x0451, "idProduct": 0x2046,
           "UsbExclusiveOwner": "pid 998, HubThing", "IORegistryEntryChildren": [table, i1pro]}
    other = {"IOObjectClass": "IOUSBHostDevice", "idVendor": 0x05AC, "idProduct": 0x1234,
             "IOUserClientCreator": "pid 1, launchd"}
    return plistlib.dumps([hub, other])


def test_holders_are_read_from_the_tables_own_entry_only_and_never_its_serial():
    got = tbl.holders_from_plist(_plist(), own_pid=77)
    assert got == ["exclusive owner: SomeApp (pid 654)", "connected: xrdd (pid 321)",
                   "connected: this program (pid 77)"]
    text = " ".join(got)
    for secret in (sim_mod.FAKE_SERIAL, "OTHERSERIAL", "NotTheTable", "HubThing", "launchd"):
        assert secret not in text
    # a value not of the form "pid N, name" is never copied
    odd = tbl.holders_from_plist(_plist({"UsbExclusiveOwner": "serial " + sim_mod.FAKE_SERIAL}))
    assert sim_mod.FAKE_SERIAL not in " ".join(odd)
    assert "UsbExclusiveOwner: (not in the expected form)" in odd
    assert tbl.holders_from_plist(b"") == []
    assert tbl.holders_from_plist(b"not a plist") == ["(macOS's list could not be read)"]


def test_the_holders_reach_the_log_without_the_serial(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl, "usb_holders", lambda: tbl.holders_from_plist(_plist()))

    def opener():
        t = tbl.FtdiUsb(FakeDev(), FakeCore, BusyUtil())
        t.setup()
    events = []
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(tbl, "check_usb_available", lambda: "pyusb test; libusb test")
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog, "xrite_helpers_running", lambda: ["xrdd"])
    monkeypatch.setattr(tbl, "open_table", opener)
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)
    log = tmp_path / "busy.txt"
    assert prog.main(["--real", "--log", str(log)],
                     console=prog.AutoConsole(lambda k, t: None)) == 2
    text = log.read_text(encoding="utf-8")
    assert "exclusive owner: SomeApp (pid 654)" in text
    assert sim_mod.FAKE_SERIAL not in text and "OTHERSERIAL" not in text


def test_missing_pyusb_names_the_exact_command():
    assert "venv/bin/python3 i1io_open.py --real" in tbl.NO_PYUSB
