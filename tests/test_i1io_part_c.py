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


@pytest.mark.slow       # exhaustive: every line / every question (--runslow)
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


@pytest.mark.slow       # exhaustive: every line / every question (--runslow)
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


@pytest.mark.slow       # exhaustive: every line / every question (--runslow)
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


# ---- D: your sheet ------------------------------------------------------------------------

MOTION = ("m0", "m1", "m2", "i1")
WIRE_LINES = {v.decode().rstrip("\r") for v in tbl.WIRE.values()}


def computed(sim):
    return [x for x in sim.received if x[1:3] in ("m0", "m2") and x not in WIRE_LINES]
P1 = cl.C_FIXED["aim"].decode().rstrip("\r")
SPOT_CAL = ["c2"]            # a spot calibration (and a strip one through FakeReaders? no: C1)


def _sheet():
    return pc.load_sheet(PKG / "demo" / pc.DEMO_SHEET)


def _aims_at(origin):
    return pc.demo_aims(_sheet(), origin)


def _rot(points, deg):
    import math
    cx = sum(p[0] for p in points) / 3
    cy = sum(p[1] for p in points) / 3
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(round(cx + c * (x - cx) - s * (y - cy)), round(cy + s * (x - cx) + c * (y - cy)))
            for x, y in points]


GOOD = pc.demo_aims()
WRONG = {
    "swapped corners": [GOOD[1], GOOD[0], GOOD[2]],
    "swapped 2 and 3": [GOOD[0], GOOD[2], GOOD[1]],
    "mirrored": [(2 * 150 - x, y) for x, y in GOOD],
    "a corner one patch off": [GOOD[0], GOOD[1], (GOOD[2][0] + 100, GOOD[2][1])],
    "mark 2 one patch off": [GOOD[0], (GOOD[1][0], GOOD[1][1] - 90), GOOD[2]],
    "turned 180": _rot(GOOD, 180),
    "turned 90": _rot(GOOD, 90),
    "turned 5 degrees": _rot(GOOD, 5),
    "all on one spot": [GOOD[0], GOOD[0], GOOD[0]],
}


@pytest.mark.parametrize("name", list(WRONG))
def test_a_wrong_alignment_is_refused_before_any_move_and_the_sitting_goes_on(tmp_path, name):
    sim = csim.CSimTable(part_c=False, aims=WRONG[name])
    code, sim, log, con, res = run_c(tmp_path, ["d1", "d2", "d3", "e2", "f"], sim=sim)
    v = verdicts(log)
    assert v[0] == ("d1", "failed cleanly"), (name, v)
    # D2..E2 are not offered without D1; F homes, or refuses (nothing moved) when the hand
    # left the free arm outside the measuring area
    assert [k for k, _ in v] == ["d1", "f"]
    assert v[-1][1] in ("worked", "failed cleanly"), (name, v)
    assert sim.violations == []
    last_p1 = max(i for i, x in enumerate(sim.received) if x == P1)
    nxt = [x for x in sim.received[last_p1 + 1:] if x[1:3] in MOTION]
    home = tbl.WIRE["home"].decode().rstrip("\r")
    assert nxt == ([home] if v[-1][1] == "worked" else []), (name, nxt)
    assert "Nothing has moved since your aims" in screen(con)
    assert not (res / "d1-1" / "alignment.json").exists()


def test_a_good_alignment_moves_the_opening_onto_mark_3(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["d1", "d2", "f"])
    assert verdicts(log) == [("d1", "worked"), ("d2", "worked"), ("f", "worked")]
    # D2's one computed move put the (simulated) measuring opening on mark 3
    assert len(computed(sim)) == 1
    d2 = [b for b in blocks(log) if b["stage"] == "d2"][0]
    assert abs(d2["position_after"][0] - GOOD[2][0]) <= 2
    assert abs(d2["position_after"][1] - GOOD[2][1]) <= 2
    assert sim.violations == []
    al = json.loads((res / "d1-1" / "alignment.json").read_text())
    assert al["checks"]["angle_deg"] == pytest.approx(90, abs=0.2)


def test_the_spot_row_reads_every_patch_at_its_computed_place(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c2", "d1", "d3", "f"])
    assert verdicts(log) == [("c2", "worked"), ("d1", "worked"), ("d3", "worked"),
                             ("f", "worked")]
    sheet = _sheet()
    st = sheet["pages"][0]["strips"][0]
    want = sorted(pc.demo_aims_point(sheet, q["centre_mm"]) for q in st["patches"])
    got = sorted((round(x), round(y)) for x, y in sim.read_spots[1:])
    assert len(got) == len(want) == 24
    for g, w in zip(got, want):
        assert abs(g[0] - w[0]) <= 1 and abs(g[1] - w[1]) <= 1, (g, w)
    rows = (res / "d3-1" / "d3_row1.readings.csv").read_text().splitlines()
    assert len(rows) == 25


def test_d3_and_d4_need_a_spot_calibration_and_say_so(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["d1", "d3", "f"])
    assert verdicts(log) == [("d1", "worked"), ("f", "worked")]
    assert "D3 (it needs a spot calibration in this sitting (C1))" in screen(con)


def test_enter_between_two_patches_stops_cleanly_and_the_sitting_goes_on(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c2", "d1", "d3", "f"], stop_at_poll=5)
    v = verdicts(log)
    assert v == [("c2", "worked"), ("d1", "worked"), ("d3", "stopped by you (clean)"),
                 ("f", "worked")], v
    assert len(sim.read_spots) == 1 + 5


def test_declining_a_first_visit_move_moves_nothing(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["d1", "d2", "f"],
                                     script={"Make this move now?": "no"})
    v = verdicts(log)
    assert v == [("d1", "worked"), ("d2", "failed cleanly"), ("f", "worked")], v
    assert computed(sim) == []


def test_rows_beyond_the_area_are_named_in_d1_and_refused_before_any_line(tmp_path):
    """The sheet 15 mm too far to the right: its marks still inside, its rows not."""
    sim = csim.CSimTable(part_c=False, aims=_aims_at((1500, 950)))
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "e2", "d3", "f"], sim=sim)
    v = verdicts(log)
    # E2 refused by its plan; the free arm (the sight offset beside mark 3) stands outside
    # the area, so D3 and F refuse to start a move from there and say what to do
    assert v == [("c1", "worked"), ("d1", "worked"), ("e2", "failed cleanly"),
                 ("d3", "failed cleanly"), ("f", "failed cleanly")], v
    text = screen(con)
    assert "22 of the 22 rows" in text and "further to the left" in text
    assert "Please push the free arm gently" in text
    assert computed(sim) == []
    assert not any(x.startswith(";m2") for x in sim.received)
    e2 = [b for b in blocks(log) if b["stage"] == "e2"][0]
    assert e2["lines_after"] == e2["lines_before"]          # not one line sent in E2
    assert sim.violations == []


def test_a_mark_outside_the_area_is_refused_with_the_way_to_shift(tmp_path):
    sim = csim.CSimTable(part_c=False, aims=_aims_at((1900, 950)))
    code, sim, log, con, res = run_c(tmp_path, ["d1", "f"], sim=sim)
    assert verdicts(log) == [("d1", "failed cleanly"), ("f", "worked")]
    assert "outside the measuring area" in screen(con)


def test_the_whole_page_in_spot_and_strip_readings(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "e3", "d4", "f"])
    assert verdicts(log) == [("c1", "worked"), ("d1", "worked"), ("e3", "worked"),
                             ("d4", "worked"), ("f", "worked")]
    assert sim.violations == []
    # serpentine: the scan moves alternate direction, each a whole row at the chosen speed
    moves = sim.scan_moves
    assert len(moves) == 22
    for k, (a, b, v) in enumerate(moves):
        assert v == 54
        assert (b[0] > a[0]) == (k % 2 == 0), k
    assert len(sim.read_spots) == 528
    cut = sorted((res / "e3-1").glob("*.cut.ti3"))
    assert len(cut) == 22
    strip = (res / "strip_readings.ti3").read_text()
    assert "NUMBER_OF_SETS 528" in strip


def test_e3_asks_after_each_row_and_a_stop_is_clean(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "e3", "f"],
                                     script={"Go on with row 3?": "stop"})
    v = verdicts(log)
    assert v == [("c1", "worked"), ("d1", "worked"), ("e3", "stopped by you (clean)"),
                 ("f", "worked")], v
    assert len(sim.scan_moves) == 2


@pytest.mark.parametrize("speed", [str(v) for v in pc.SPEED_CHOICES])
def test_e2_runs_at_every_recorded_speed_and_no_other(tmp_path, speed):
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "e2", "f"],
                                     script={"At which recorded speed": speed})
    assert ("e2", "worked") in verdicts(log)
    assert sim.scan_moves[-1][2] == int(speed)
    assert set(pc.SPEED_CHOICES) == set(geo.RECORDED_M2_SPEEDS)


# ---- the guard at its boundaries ------------------------------------------------------------

A = geo.MEASURING_AREA
R = geo.AREA_RAW


def test_the_area_figures_are_pinned():
    assert (R.xmin, R.xmax, R.ymin, R.ymax) == (-1434, 1766, 809, 3109)
    assert (A.xmin, A.xmax, A.ymin, A.ymax) == (-1384, 1716, 859, 3059)
    assert R.xmax - R.xmin == 3200 and R.ymax - R.ymin == 2300      # 320 x 230 mm
    # every recorded aimed corner and every recorded chart move lies inside the raw area
    for name, pts in geo.RECORDED_ALIGNMENTS.items():
        for p in pts:
            assert R.contains(p), (name, p)
    assert R.contains(sc.RECORDED_ROW["start"]) and R.contains(sc.RECORDED_ROW["end"])
    for t in tbl.SPOT_TARGETS:
        assert A.contains(t)


@pytest.mark.parametrize("x,y,ok", [(A.xmin, A.ymin, True), (A.xmax, A.ymax, True),
                                    (A.xmin - 1, 2000, False), (A.xmax + 1, 2000, False),
                                    (0, A.ymin - 1, False), (0, A.ymax + 1, False),
                                    (0, 2000, True)])
def test_a_computed_line_is_built_and_passed_only_inside_the_area(x, y, ok):
    if ok:
        for line in (geo.m0_line(x, y), geo.m2_line(x, y, 54)):
            assert cl.classify(line)[1] is True
    else:
        with pytest.raises(geo.AreaRefused):
            geo.m0_line(x, y)
        with pytest.raises(geo.AreaRefused):
            geo.m2_line(x, y, 54)
        forged = geo._line("m0", x, y, 300)
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(forged)


@pytest.mark.parametrize("speed", [1, 39, 55, 100, 120, 139, 300, 1000])
def test_a_scan_move_at_an_unrecorded_speed_is_refused(speed):
    with pytest.raises(geo.AreaRefused):
        geo.m2_line(0, 2000, speed)
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(geo._line("m2", 0, 2000, speed))


@pytest.mark.parametrize("speed", [100, 150, 299, 301, 500])
def test_a_computed_move_at_an_unrecorded_speed_is_refused(speed):
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(geo._line("m0", 0, 2000, speed))


class _T:
    position_now = None


@pytest.mark.parametrize("start,ok", [((0, 2000), True), ((R.xmin, R.ymin), True),
                                      ((R.xmin - 1, 2000), False), ((0, R.ymax + 1), False),
                                      ((1102, 0), False), (None, False)])
def test_the_gate_checks_the_whole_swept_rectangle_from_a_fresh_reading(start, ok):
    t = _T()
    t.position_now = start
    gate = cl.make_gate(t)
    line = geo.m0_line(0, 2000)
    if ok:
        assert gate(line) == ("m0", True, "computed m0")
    else:
        with pytest.raises(tbl.ForbiddenLine):
            gate(line)


def test_the_gate_lets_nothing_else_through():
    allowed = {tbl.WIRE[k] for k in cl.PART_C_WIRE_KEYS} | set(cl.C_FIXED.values())
    for line in allowed:
        cl.classify(line)
    # part A's move to Y 250 is not part C's (outside the area); its move to (1102, 1000)
    # lies inside the area, so part C would pass it only as a computed move (fresh reading,
    # swept rectangle), never as a fixed line
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(tbl.WIRE["to_250"])
    assert cl.classify(tbl.WIRE["to_1000"])[2] == "computed m0"
    for bad in (b";i02e\r", b";u8000060000100d1x\r", b";d1016e34\r", b";m0\r",
                b";m00000000012c00\r", b";w8000000\r", b";m2000007d0003600\r"):
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(bad)


def test_every_fixed_part_c_line_is_byte_for_byte_its_recorded_form():
    assert {k: v.decode().rstrip("\r") for k, v in cl.C_FIXED.items()} == {
        "aim": ";p124", "scan_c4": ";c42e", "scan_d1": ";d1016d35", "scan_a3": ";a331",
        "scan_c3": ";c32f"}
    assert {csim.C_P1, csim.C_C4, csim.C_D1, csim.C_A3, csim.C_C3} == {
        v.decode().rstrip("\r") for v in cl.C_FIXED.values()}
    assert sc.recorded_row_plan().m0 == sc.RECORDED_ROW["m0_line"]
    assert sc.recorded_row_plan().m2 == sc.RECORDED_ROW["m2_line"]


def test_the_simulator_keeps_its_own_copy_of_the_area_and_speeds():
    assert csim.C_TARGET_BOX == (A.xmin, A.xmax, A.ymin, A.ymax)
    assert csim.C_SWEEP_BOX == (R.xmin, R.xmax, R.ymin, R.ymax)
    assert csim.C_SPEEDS_M2 == geo.RECORDED_M2_SPEEDS
    src = (PKG / "i1io_part_c_sim.py").read_text()
    assert "i1io_geometry" not in src and "i1io_c_lines" not in src


def test_the_recorded_alignments_pass_the_checks_or_are_the_known_degenerate_ones():
    sheet_mm = None
    for name, pts in geo.RECORDED_ALIGNMENTS.items():
        (p1, p2, p3) = pts
        l12 = ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5 / 10
        l23 = ((p2[0] - p3[0]) ** 2 + (p2[1] - p3[1]) ** 2) ** 0.5 / 10
        aims = ((0.0, 0.0), (0.0, l12), (l23, l12))
        if name in ("R1 716.8", "R2 144.5"):
            with pytest.raises(geo.AlignmentRefused):
                geo.fit_alignment(aims, pts)
            continue
        try:
            al = geo.fit_alignment(aims, pts)
        except geo.AlignmentRefused as exc:
            # the front-most recorded aims lie in the 5 mm margin: refused as outside the area
            assert "outside the measuring area" in str(exc), (name, exc)
            assert max(p[1] for p in pts) > A.ymax
            continue
        assert abs(al.checks["rotation_deg"]) < 1.0
    del sheet_mm


# ---- E2, E3: the strip reading of your sheet ----------------------------------------------

@pytest.mark.parametrize("stage", ["e2", "e3"])
@pytest.mark.parametrize("fault", [{"not_ready": True}, {"dead": True}, {"lights_err": True}])
def test_e2_e3_never_send_the_scan_move_to_an_instrument_that_is_not_ready(tmp_path, stage,
                                                                           fault):
    rd_ = readers(scan=fault)
    # C1 calibrates with a healthy reader; the fault starts with the sheet's strip reader
    calls = []

    def factory(s, lg):
        r = REAL_FAKE_READERS(s, lg)
        real_scan = r.scan

        def scan(folder):
            calls.append(folder)
            x = real_scan(folder)
            if len(calls) > 1:
                x.faults.update(fault)
            return x
        r.scan = scan
        return r
    del rd_
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", stage, "d2", "f"], readers=factory)
    v = verdicts(log)
    assert (stage, "failed cleanly") in v, v
    assert ("d2", "worked") in v and v[-1] == ("f", "worked"), v
    assert not any(x.startswith(";m2") for x in sim.received)
    assert sim.violations == []


@pytest.mark.parametrize("stage", ["e2", "e3"])
@pytest.mark.parametrize("fault", [{"no_lamp": True}, {"dies_at_fire": True}])
def test_e2_e3_after_the_scan_move_a_failure_says_switch_off_and_leaves_a_marker(tmp_path, stage,
                                                                                 fault):
    calls = []

    def factory(s, lg):
        r = REAL_FAKE_READERS(s, lg)
        real_scan = r.scan

        def scan(folder):
            calls.append(folder)
            x = real_scan(folder)
            if len(calls) > 1:
                x.faults.update(fault)
            return x
        r.scan = scan
        return r
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", stage, "f"], readers=factory)
    assert code == 2
    text = screen(con)
    assert "SWITCH THE TABLE OFF" in text
    assert text.rstrip().count("SWITCH THE TABLE OFF") >= 2     # at once, and in the end text
    markers = list((res / f"{stage}-1").rglob(sc.PENDING_MARKER))
    assert len(markers) == 1
    m2 = [i for i, x in enumerate(sim.received) if x.startswith(";m2")]
    assert len(m2) == 1 and sim.received[m2[0] + 1:] == [
        cl.C_FIXED["scan_a3"].decode().rstrip("\r"), cl.C_FIXED["scan_c3"].decode().rstrip("\r")]
    assert verdicts(log)[-1] == (stage, "stopped")
    with zipfile.ZipFile(tmp_path / "log-results.zip") as z:
        assert any(n.endswith(sc.PENDING_MARKER) for n in z.namelist())


SHEET_STAGES = ["c1", "d1", "d2", "d3", "e2", "f"]


@pytest.mark.slow       # exhaustive: every line / every question (--runslow)
@pytest.mark.parametrize("kind", ["no_answer", "status", "late", "refuse", "no_done"])
def test_any_fault_at_any_line_of_the_sheet_stages_keeps_every_rule(tmp_path, kind):
    lines, _ = _clean_run(tmp_path, SHEET_STAGES)
    start = lines.index(P1) - 25          # from the way out of D1 on
    for i in range(start, len(lines)):
        sim = csim.CSimTable(part_c=False)
        sim.inject_at(i, kind, 30.0 if kind == "late" else 1.0)
        code, sim, log, con, res = run_c(tmp_path / f"{kind}{i}", SHEET_STAGES, sim=sim)
        assert sim.violations == [], (kind, i, lines[i], sim.violations)
        check_no_question_while_moving(con)
        check_truthful(sim, con, log)
        assert sim.received[:i + 1] == lines[:i + 1]
        if code == 2:
            after = sim.received[i + 1:]
            path = [cl.C_FIXED[k].decode().rstrip("\r") for k in ("scan_a3", "scan_c3")]
            if lines[i].startswith(";m2") or lines[i] == path[0]:
                rest = path if lines[i].startswith(";m2") else path[1:]
                while after and rest and after[0] == rest[0]:
                    after, rest = after[1:], rest[1:]
            assert all(x == P0 for x in after), (kind, i, sim.received[i:])


@pytest.mark.slow       # exhaustive: every line / every question (--runslow)
def test_ctrl_c_at_every_question_of_the_sheet_stages_sends_nothing_more(tmp_path):
    stages = ["c1", "d1", "d2", "d3", "e2", "f"]
    lines, n_questions = _clean_run(tmp_path, stages)
    for n in range(1, n_questions + 1):
        sim = csim.CSimTable(part_c=False)
        code, sim, log, con, res = run_c(tmp_path / f"q{n}", stages, sim=sim, interrupt_at=n)
        assert sim.violations == [], n
        assert sim.received == lines[:len(sim.received)], n
        assert not sim.moving and sim.m2_pending is None
        check_truthful(sim, con, log)


# ---- caps, the "no" answers, calibration out on the table, the instrument check -------------

def test_part_c_caps_are_pinned_and_each_step_keeps_its_own(tmp_path):
    assert (pc.C_MAX_LINES, pc.C_MAX_MOVES) == pc.session_caps()
    assert pc.C_MAX_LINES < 20000 and pc.C_MAX_MOVES < 8000
    code, sim, log, con, res = run_c(tmp_path, ALL_STAGES)
    tab_lines = len(sim.received)
    assert tab_lines <= pc.C_MAX_LINES
    # a stage step that tries one line more than its cap is stopped by Table._write
    d = tbl.Table(sim_mod.SimTransport(csim.CSimTable()), log=lambda k, t: None)
    d.part = "C"
    d.c_gate = cl.make_gate(d)
    d.c_caps = (pc.C_MAX_LINES, pc.C_MAX_MOVES)
    d.opening()
    d.current_step = pc.CStep("x", 2, 0)
    d.step_lines = 0
    d.position()
    d.position()
    with pytest.raises(tbl.Doubt):
        d.position()
    d2 = tbl.Table(sim_mod.SimTransport(csim.CSimTable()), log=lambda k, t: None)
    d2.part = "C"
    d2.c_gate = cl.make_gate(d2)
    d2.c_caps = (len(tbl.OPEN_KEYS) + 1, 0)
    d2.opening()
    d2.position()
    with pytest.raises(tbl.Doubt):
        d2.position()


@pytest.mark.parametrize("arm,goes_on", [("no", True), ("yes", False), ("not sure", False)])
def test_after_a_no_only_a_wrong_table_restricts_the_sitting_to_the_homing(tmp_path, arm,
                                                                           goes_on):
    code, sim, log, con, res = run_c(
        tmp_path, ["c3", "c4", "f"],
        script={"Did the table and the instrument do what was described?": "no",
                "Did anything about the TABLE or the ARM": arm})
    keys = [k for k, _ in verdicts(log)]
    assert keys == (["c3", "c4"] if goes_on else ["c3", "f"]), keys


def test_a_calibration_asked_for_out_on_the_table_is_refused(tmp_path):
    rd_ = readers(spot={"needs_cal": True})
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "d3", "f"], readers=rd_)
    v = verdicts(log)
    assert ("d3", "failed cleanly (instrument)") in v, v
    assert "A calibration needs the instrument on a white tile" in screen(con)
    qs = [q for q, *_ in con.seen]
    d1 = next(i for i, q in enumerate(qs) if q.startswith("Mark 1:"))
    assert not any(q in (pc.CAL_WHERE, pc.CAL_OWN) for q in qs[d1:])


def test_after_the_homing_the_sheet_must_be_aimed_again(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["d1", "f", "d2", "f"])
    assert verdicts(log) == [("d1", "worked"), ("f", "worked")]
    assert "D2 (it needs D1 first)" in screen(con)


def test_the_instrument_check_wants_exactly_one_i1pro_and_nothing_else():
    from i1io_reader import instrument_check
    table, pro = (0x0971, 0x2004), (0x0971, 0x2000)
    assert instrument_check([table, pro, (0x05AC, 0x1234)]) is None
    assert "no i1Pro 2" in instrument_check([table])
    assert "more than one" in instrument_check([table, pro, pro])
    for other in ((0x0765, 0x5020), (0x085C, 0x0500), (0x0971, 0x2007)):
        assert "Another measuring instrument" in instrument_check([table, pro, other])


def test_the_reader_s_problems_are_named(tmp_path, monkeypatch):
    import i1io_reader as rd
    monkeypatch.setattr(rd.sys, "platform", "darwin")
    assert "missing" in " ".join(rd.helper_problems(tmp_path / "nope"))
    f = tmp_path / "chromiq-chartread"
    f.write_bytes(b"")
    f.chmod(0o644)
    assert "chmod +x" in " ".join(rd.helper_problems(f))
    monkeypatch.setattr(rd.sys, "platform", "linux")
    assert "only on a Mac" in " ".join(rd.helper_problems(f))


def test_the_bundled_reader_is_the_built_one():
    import hashlib
    h = hashlib.sha256((PKG / "bin" / "chromiq-chartread").read_bytes()).hexdigest()
    assert h == "5975f18d2d3ae4b47fc5b37da08937a19a1b0573fc78b2e5636bf57aaecd083c"


def test_the_reader_is_never_asked_for_a_beta_flag_or_a_memory_write():
    src = (PKG / "i1io_reader.py").read_text()
    for flag in ("--i1pro2-lights", "--ruler", "--condition-dir", "--lights-", "eeprom",
                 "write_eeprom"):
        assert f'"{flag}' not in src
    assert src.count("subprocess.Popen(") == 1


# ---- what the package says ------------------------------------------------------------------

def _flat(text):
    return " ".join(text.split())


def test_the_readme_describes_part_c_truly():
    readme = _flat((PKG / "README.md").read_text(encoding="utf-8"))
    assert "—" not in readme
    for st in pc.STAGES:
        assert f"{st.key.upper()}: {st.title}" in readme, st.key
        assert pc.NEEDS_TEXT[st.key] in readme, st.key
    a = geo.MEASURING_AREA
    assert f"X {a.xmin} to {a.xmax} and Y {a.ymin} to {a.ymax}" in readme
    assert f"at most **{pc.C_MAX_LINES} lines and {pc.C_MAX_MOVES} movements**" in readme
    for needed in ("What is new in 0.5.0", "0.5.0 contains everything 0.4.0 has",
                   "xattr -d com.apple.quarantine bin/chromiq-chartread",
                   "chmod +x bin/chromiq-chartread", "i1ProDeviceService",
                   "SWITCH THE TABLE OFF NOW", sc.PENDING_MARKER, "ONE results zip",
                   "i1Profiler measurement of the same sheet", "--sheet",
                   "A stage that fails cleanly does not end the sitting",
                   "320 x 230 mm"):
        assert needed in readme, needed
    for k, v in cl.C_FIXED.items():
        assert f"`{v.decode()[1:3]}`" in readme, k


def test_bytes_md_lists_part_c_s_lines_and_rules():
    b = (PKG / "BYTES.md").read_text(encoding="utf-8")
    for k, v in cl.C_FIXED.items():
        assert f"| `{v.decode().rstrip(chr(13))}` | `{v.hex(' ')}` | {k} |" in b, k
    assert ", ".join(str(v) for v in geo.RECORDED_M2_SPEEDS) in b
    assert f"at most **{pc.C_MAX_LINES} lines and {pc.C_MAX_MOVES} movements**" in b
    assert "0.5.0" in b.splitlines()[0]


def test_the_stage_texts_say_no_untrue_thing():
    text = _flat(" ".join(st.explain + " " + st.beyond for st in pc.STAGES))
    for wrong in ("towards the resting place", "never fails", "cannot fail", "guaranteed",
                  "safe in every case", "—"):
        assert wrong not in text, wrong
    # the stages that are first tries say so
    for st in pc.STAGES:
        if st.key in ("e1", "d1", "d2", "d3", "e2", "e3", "d4"):
            assert st.first_try, st.key


NEW_FILES = ("i1io_part_c.py", "i1io_part_c_sim.py", "i1io_c_lines.py", "i1io_geometry.py",
             "i1io_reader.py", "i1io_scan.py")


def test_no_em_dash_and_standard_library_only_in_part_c():
    import ast
    allowed = {"__future__", "csv", "json", "os", "time", "dataclasses", "pathlib", "math",
               "random", "re", "queue", "subprocess", "sys", "threading", "plistlib",
               "i1io_c_lines", "i1io_geometry", "i1io_reader", "i1io_scan",
               "i1io_session_table", "i1io_session_sim", "i1io_part_c"}
    for name in NEW_FILES:
        src = (PKG / name).read_text(encoding="utf-8")
        assert "—" not in src, name
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "").split(".")[0]]
            else:
                continue
            for m in mods:
                assert m in allowed, (name, m)


def test_part_c_writes_to_the_table_only_through_table_write():
    for name in NEW_FILES:
        src = (PKG / name).read_text(encoding="utf-8")
        if name == "i1io_part_c_sim.py":
            continue
        assert ".t.write(" not in src and "dev.write(" not in src, name
