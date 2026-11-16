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


def run_c(tmp_path, stages, sim=None, script=None, readers=None, sheet=None, console_cls=None,
          **kw):
    """One simulated part C sitting. Returns (code, sim, log text, console, results folder)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    sim = sim or csim.CSimTable(part_c=False)
    con = (console_cls or CScript)(sim, stages, script=script, **kw)
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
        for name, *_ in pc.Results.COMBINED:
            assert f"log-results/{name}" in names, name
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
        if st.key == "dz":
            continue                    # the demo sheet needs no front part (fix 2 tests run it)
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
    sim = csim.CSimTable(part_c=False, aims=_aims_at((1500, 700)))
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "e2", "d3", "f"], sim=sim)
    v = verdicts(log)
    # E2 refused by its plan; the free arm (the sight offset beside mark 3) stands outside
    # the area, so D3 and F refuse to start a move from there and say what to do
    assert v == [("c1", "worked"), ("d1", "worked"), ("e2", "failed cleanly"),
                 ("d3", "failed cleanly"), ("f", "failed cleanly")], v
    text = screen(con)
    assert "22 of the 22 rows" in text and "further to the left" in text
    assert pc.AREA_WHERE in _flat(text) and pc.WHY_BACK in _flat(text)
    assert "Please push the free arm gently" in text
    assert computed(sim) == []
    assert not any(x.startswith(";m2") for x in sim.received)
    e2 = [b for b in blocks(log) if b["stage"] == "e2"][0]
    assert e2["lines_after"] == e2["lines_before"]          # not one line sent in E2
    assert sim.violations == []


def test_a_mark_outside_the_area_is_refused_with_the_way_to_shift(tmp_path):
    sim = csim.CSimTable(part_c=False, aims=_aims_at((1900, 700)))
    code, sim, log, con, res = run_c(tmp_path, ["d1", "f"], sim=sim)
    assert verdicts(log) == [("d1", "failed cleanly"), ("f", "worked")]
    assert "outside the measuring area" in screen(con)
    assert "further to the right" in screen(con)


def test_a_sheet_laid_where_i1profiler_had_it_offers_back_or_go_on(tmp_path):
    """Fix 2: the demo sheet laid as far to the front as the 14 November sheets is no longer
    refused: D1 says part of it lies further forward than the opening has been read and offers
    back (the default: nothing new is tried) or go on (then its own yes, then DZ)."""
    sim = csim.CSimTable(part_c=False, aims=_aims_at((1650, 1020)))
    code, sim, log, con, res = run_c(tmp_path, ["d1", "d2", "f"], sim=sim)
    v = verdicts(log)
    assert v[0] == ("d1", "stopped by you (clean)") and [k for k, _ in v] == ["d1", "f"], v
    text = _flat(screen(con))
    assert "further forward than the instrument's measuring opening has been" in text
    assert "i1Profiler measures sheets laid like this" in text
    assert "further back and aim again (nothing new is tried)" in text
    assert "feels its way forward" in text and "our estimate" in text
    assert computed(sim) == []


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
    strip = (res / "sheet_strip_readings.ti3").read_text()
    assert "NUMBER_OF_SETS 528" in strip
    spot = (res / "sheet_spot_readings.ti3").read_text()
    assert "NUMBER_OF_SETS 528" in spot
    # the same patches read both ways agree on the simulated sheet (spectra in percent)
    from i1io_reader import read_ti3_spectra
    _wl, a = read_ti3_spectra(res / "sheet_spot_readings.ti3")
    _wl, b = read_ti3_spectra(res / "sheet_strip_readings.ti3")
    assert set(a) == set(b)
    for data in (a, b):                                      # percent, not 0..1 or 0..10000
        assert 5 < max(max(x) for _s, _x, x in data.values()) <= 110


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
    assert (R.xmin, R.xmax, R.ymin, R.ymax) == (-1434, 1766, 473, 2773)
    assert (A.xmin, A.xmax, A.ymin, A.ymax) == (-1384, 1716, 523, 2723)
    assert R.xmax - R.xmin == 3200 and R.ymax - R.ymin == 2300      # 320 x 230 mm
    # every recorded chart move lies inside the target area
    assert A.contains(sc.RECORDED_ROW["start"]) and A.contains(sc.RECORDED_ROW["end"])
    for t in tbl.SPOT_TARGETS:
        assert A.contains(t)
    for t in RECORDED_TARGETS_ALL:
        assert A.contains(t), t


#: Every position the table READ (p0: the measuring opening) at the edges of the area, in every
#: recording and every log of the tester (fix1/tools/edges.py over the decoded R1, R2, S1, S2
#: captures and the program logs; numbers only): the frontmost, the furthest right, and the
#: furthest to the front under motor.
P0_FRONTMOST = ((-1413, 2773), (-1324, 2758), (-1434, 2755))     # R1 431.410, 279.888, 272.108
P0_RIGHTMOST = (-1434, 2755)                                     # R1 272.108
P0_FRONT_AFTER_MOTOR = (1169, 2560)                              # S2, after m2 to (1171, 2559)
#: The p1 (SIGHT) readings the old front edge 3109 was taken from, and the p0 read next.
P1_FRONTMOST = (1268, 3109)                                      # R1 412.443, mark 2


def test_the_front_edge_is_the_frontmost_sensor_reading_not_a_sight_reading():
    """Safety review of 7382e56f2, required change: both edges of the PROVEN zone rest on p0
    (sensor) readings; fix 2: the front zone beyond it is capped at the frontmost recorded aim
    plus 5 mm."""
    assert geo.FRONTMOST_Y_REACHED == max(p[1] for p in P0_FRONTMOST) == R.ymax
    assert geo.SMALLEST_X_REACHED == P0_RIGHTMOST[0] == R.xmin
    assert R.ymax < P1_FRONTMOST[1] - 300           # the sight reading is ~31 mm further front
    assert A.ymax == R.ymax - 50 and A.ymax < max(p[1] for p in P0_FRONTMOST)
    with pytest.raises(geo.AreaRefused, match="DZ"):
        geo.check_target((0, A.ymax + 1), "x")
    assert A.contains(P0_FRONT_AFTER_MOTOR)
    for dx, dy in geo.SIGHT_TO_SENSOR_SEEN:
        assert -323 <= dy <= -306 and -120 <= dx <= -83
    for name, pts in geo.RECORDED_ALIGNMENTS.items():
        if name in ("R1 716.8", "R2 144.5"):
            continue
        assert pts[1][1] > A.ymax and pts[2][1] > A.ymax, name
    # the cap: the frontmost recorded aim (p1, R1 412.443) plus the 5 mm margin
    assert geo.FRONTMOST_AIM_Y == P1_FRONTMOST[1] == max(
        p[1] for pts in geo.RECORDED_ALIGNMENTS.values() for p in pts)
    assert geo.FRONT_CAP_Y == 3159 == geo.CAP_AREA.ymax == geo.CAP_RAW.ymax


CAP = geo.CAP_AREA


@pytest.mark.parametrize("x,y,ok", [(A.xmin, A.ymin, True), (A.xmax, A.ymax, True),
                                    (A.xmax, CAP.ymax, True),
                                    (A.xmin - 1, 2000, False), (A.xmax + 1, 2000, False),
                                    (0, A.ymin - 1, False), (0, CAP.ymax + 1, False),
                                    (0, 2000, True)])
def test_a_computed_line_is_built_and_passed_only_inside_the_cap(x, y, ok):
    """The builders and classify (stateless) never pass a line beyond the front zone's cap;
    what this sitting allows inside it is the gate's job (next tests)."""
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
    assert csim.C_TARGET_BOX == (CAP.xmin, CAP.xmax, CAP.ymin, CAP.ymax)
    assert csim.C_SWEEP_BOX == (R.xmin, R.xmax, R.ymin, geo.CAP_RAW.ymax)
    assert csim.C_PROVEN_Y == (A.ymax, R.ymax) and csim.C_CREEP == geo.CREEP_STEP
    assert csim.C_SPEEDS_M2 == geo.RECORDED_M2_SPEEDS
    src = (PKG / "i1io_part_c_sim.py").read_text()
    assert "i1io_geometry" not in src and "i1io_c_lines" not in src


def _aims_mm(pts):
    (p1, p2, p3) = pts
    l12 = ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5 / 10
    l23 = ((p2[0] - p3[0]) ** 2 + (p2[1] - p3[1]) ** 2) ** 0.5 / 10
    return ((0.0, 0.0), (0.0, l12), (l23, l12))


def test_the_recorded_alignments_pass_the_checks_and_reach_into_the_front_zone():
    """Fix 2: every non-degenerate recorded alignment is accepted (its marks lie inside the cap),
    and every one reaches into the front zone (its bottom marks lie in front of the proven
    part); the two degenerate ones are refused."""
    for name, pts in geo.RECORDED_ALIGNMENTS.items():
        aims = _aims_mm(pts)
        if name in ("R1 716.8", "R2 144.5"):
            with pytest.raises(geo.AlignmentRefused):
                geo.fit_alignment(aims, pts)
            continue
        al = geo.fit_alignment(aims, pts)
        assert abs(al.checks["rotation_deg"]) < 1.0
        assert max(p[1] for p in al.readings) > A.ymax
    # 5 mm beyond the frontmost recorded mark: still inside; one unit more: refused
    pts = geo.RECORDED_ALIGNMENTS["R1 401.6"]
    geo.fit_alignment(_aims_mm(pts), [(x, y + 50) for x, y in pts])
    with pytest.raises(geo.AlignmentRefused, match="further to the front than any mark"):
        geo.fit_alignment(_aims_mm(pts), [(x, y + 51) for x, y in pts])


#: i1Profiler's own moves after each recorded alignment (decoded R1, R2, S2 captures; the m0
#: and m2 targets between the third aim and the next homing; numbers only). Spot sessions: the
#: 28 patch centres of row 1, from right to left.
RECORDED_SPOT_TARGETS = {
    "S2 383.3": [(-1181, 1658), (-1094, 1659), (-1007, 1659), (-920, 1659), (-833, 1659),
                 (-745, 1659), (-658, 1660), (-571, 1660), (-484, 1660), (-396, 1660),
                 (-309, 1660), (-222, 1661), (-135, 1661), (-48, 1661), (39, 1661), (126, 1661),
                 (213, 1661), (300, 1662), (388, 1662), (475, 1662), (562, 1662), (649, 1662),
                 (736, 1663), (824, 1663), (911, 1663), (998, 1663), (1085, 1663), (1173, 1663)],
    "S2 684.0": [(-1182, 1657), (-1094, 1657), (-1007, 1657), (-919, 1657), (-832, 1658),
                 (-744, 1658), (-657, 1658), (-569, 1659), (-482, 1659), (-394, 1659),
                 (-307, 1659), (-219, 1660), (-132, 1660), (-44, 1660), (42, 1661), (130, 1661),
                 (217, 1661), (305, 1662), (392, 1662), (480, 1662), (567, 1662), (655, 1663),
                 (742, 1663), (830, 1663), (917, 1664), (1005, 1664), (1092, 1664), (1180, 1665)],
}
#: Strip and fallback sessions: EVERY m0 and m2 target i1Profiler sent after the third aim (row
#: starts and ends, the fallback spot patches; duplicates once), and the rows' spacing in v (1/18
#: for the 19-row charts of S2, 1/17 for the 18-row charts of R1, R2).
RECORDED_SCAN_TARGETS = {
    "S2 3.5": (18, [
        (-1196, 1645), (1175, 1735), (-1197, 1795), (1174, 1885), (-1198, 1945), (1174, 2035),
        (-1199, 2094), (1173, 2184), (-1200, 2244), (1172, 2334), (-1200, 2394), (1171, 2484),
        (-1201, 2543), (1175, 1661), (-1197, 1720), (1175, 1810), (-1198, 1870), (1174, 1960),
        (-1198, 2020), (1173, 2110), (-1199, 2169), (1172, 2259), (-1200, 2319), (1172, 2409),
        (-1201, 2469), (1171, 2559)
    ]),
    "S2 526.8": (18, [
        (-1191, 1653), (1180, 1748), (-1193, 1802), (1178, 1897), (-1194, 1951), (1177, 2045),
        (-1195, 2100), (1180, 1674), (-1192, 1728), (1179, 1822), (-1193, 1877), (1178, 1971),
        (-1195, 2025), (1176, 2120)
    ]),
    "S2 270.8": (18, [
        (-1095, 1636), (1192, 1658), (1188, 1658), (1103, 1657), (1019, 1656), (934, 1655),
        (850, 1654), (765, 1654), (681, 1653), (597, 1652), (512, 1651), (428, 1651), (343,
        1650), (259, 1649), (175, 1648), (90, 1647), (6, 1647), (-78, 1646), (-162, 1645),
        (-246, 1644), (-331, 1643), (-415, 1643), (-500, 1642), (-584, 1641), (-668, 1640),
        (-753, 1640), (-837, 1639), (-922, 1638), (-1006, 1637), (-1090, 1636)
    ]),
    "R1 401.6": (17, [
        (-1290, 1674), (1290, 1705), (1286, 1705), (1190, 1703), (1095, 1702), (1000, 1701),
        (904, 1700), (809, 1699), (714, 1698), (619, 1697), (523, 1696), (428, 1695), (333,
        1693), (238, 1692), (142, 1691), (47, 1690), (-47, 1689), (-142, 1688), (-238, 1687),
        (-333, 1686), (-428, 1685), (-523, 1683), (-619, 1682), (-714, 1681), (-809, 1680),
        (-904, 1679), (-1000, 1678), (-1095, 1677), (-1190, 1676), (-1285, 1675), (-1292, 1757),
        (1289, 1787), (1284, 1787), (1189, 1786), (1094, 1785), (999, 1784), (903, 1783), (808,
        1782), (713, 1780), (618, 1779), (522, 1778), (427, 1777), (332, 1776), (237, 1775),
        (141, 1774), (46, 1773), (-48, 1772), (-143, 1770), (-239, 1769), (-334, 1768), (-429,
        1767), (-524, 1766), (-620, 1765), (-715, 1764), (-810, 1763), (-906, 1762), (-1001,
        1760), (-1096, 1759), (-1191, 1758), (-1287, 1757)
    ]),
    "R2 427.5": (17, [
        (-1270, 1537), (1316, 1543), (1311, 1543), (1216, 1542), (1121, 1542), (1025, 1542),
        (930, 1542), (834, 1542), (739, 1541), (643, 1541), (548, 1541), (452, 1541), (357,
        1541), (262, 1540), (166, 1540), (71, 1540), (-24, 1540), (-119, 1540), (-215, 1540),
        (-310, 1539), (-406, 1539), (-501, 1539), (-596, 1539), (-692, 1539), (-787, 1538),
        (-883, 1538), (-978, 1538), (-1074, 1538), (-1169, 1538), (-1265, 1538), (-1270, 1620),
        (1316, 1625), (1311, 1625), (1216, 1624), (1121, 1624), (1025, 1624), (930, 1624), (834,
        1624), (739, 1624), (643, 1623), (548, 1623), (452, 1623), (357, 1623), (262, 1623),
        (166, 1622), (71, 1622), (-24, 1622), (-119, 1622), (-215, 1622), (-310, 1621), (-406,
        1621), (-501, 1621), (-596, 1621), (-692, 1621), (-787, 1621), (-883, 1620), (-978,
        1620), (-1074, 1620), (-1169, 1620), (-1265, 1620), (-1270, 1702), (1316, 1707), (1311,
        1707), (1216, 1707), (1120, 1706), (1025, 1706), (930, 1706), (834, 1706), (739, 1706),
        (643, 1705), (548, 1705), (452, 1705), (357, 1705), (261, 1705), (166, 1705), (71,
        1704), (-24, 1704), (-119, 1704), (-215, 1704), (-310, 1704), (-406, 1703), (-501,
        1703), (-597, 1703), (-692, 1703), (-787, 1703), (-883, 1702), (-978, 1702), (-1074,
        1702), (-1169, 1702), (-1265, 1702), (-1270, 1784), (1316, 1789), (1311, 1789), (1216,
        1789), (1120, 1788), (1025, 1788), (930, 1788), (834, 1788), (739, 1788), (643, 1788),
        (548, 1787), (452, 1787), (357, 1787), (261, 1787), (166, 1787), (71, 1786), (-24,
        1786), (-119, 1786), (-215, 1786), (-310, 1786), (-406, 1786), (-501, 1785), (-597,
        1785), (-692, 1785), (-787, 1785), (-883, 1785), (-978, 1784), (-1074, 1784), (-1169,
        1784), (-1265, 1784)
    ]),
}
RECORDED_TARGETS_ALL = [t for v in RECORDED_SPOT_TARGETS.values() for t in v] + \
    [t for _r, v in RECORDED_SCAN_TARGETS.values() for t in v]


def _model_grid(al, rows, cols=28):
    """Every patch centre (and the 0.5 mm run-in/run-out points i1Profiler's strips use) of a
    chart of *cols* columns and rows spaced 1/rows in v, through OUR Alignment.to_table."""
    (x0, y0), (_x1, y1), (x2, _y2) = al.aims_mm
    out = []
    for r in range(rows + 1):
        for u in [c / (cols - 1) for c in range(cols)] + [-0.002, 1.002]:
            out.append(al.to_table((x0 + u * (x2 - x0), y0 + r / rows * (y1 - y0))))
    return out


def test_aims_become_targets_exactly_as_i1profiler_moved_after_its_recorded_alignments():
    """The SIGHT-to-SENSOR question, checked against the recordings: OUR fit of each recorded
    alignment (its three p1 readings used as targets with no conversion) puts every patch of
    row 1 within 1 unit (0.1 mm, integer rounding) of where i1Profiler actually moved in that
    session (ALIGNMENT.md section 4: spot targets exactly the model), and every strip row start
    and end and every fallback spot patch within 1 unit too, once the model grid carries the
    strips' run-in points 0.5 mm beyond the end patches (ALIGNMENT.md allows 5 units there). Adding the recorded
    sight-to-opening offset to the aims would miss every one by about 31 mm."""
    worst_spot = 0
    for name, recorded in RECORDED_SPOT_TARGETS.items():
        pts = geo.RECORDED_ALIGNMENTS[name]
        al = geo.fit_model(_aims_mm(pts), pts)
        (x0, y0), _bl, (x2, _y2) = al.aims_mm
        ours = [al.to_table((x0 + (x2 - x0) * (27 - k) / 27, y0)) for k in range(28)]
        for o, r in zip(ours, recorded):
            worst_spot = max(worst_spot, abs(o[0] - r[0]), abs(o[1] - r[1]))
            assert abs(o[0] - r[0]) <= 1 and abs(o[1] - r[1]) <= 1, (name, o, r)
        # the alternative frame: aims taken as where the opening stood (p1 + offset)
        off = geo.SIGHT_TO_SENSOR_SEEN[5]
        shifted = [(x + off[0], y + off[1]) for x, y in pts]
        alt = geo.fit_model(_aims_mm(shifted), shifted)
        o = alt.to_table((x2, y0))
        assert abs(o[1] - recorded[0][1]) > 300, name
    assert worst_spot <= 1
    for name, (rows, recorded) in RECORDED_SCAN_TARGETS.items():
        pts = geo.RECORDED_ALIGNMENTS[name]
        al = geo.fit_model(_aims_mm(pts), pts)
        grid = _model_grid(al, rows)
        for r in recorded:
            d = min(max(abs(g[0] - r[0]), abs(g[1] - r[1])) for g in grid)
            assert d <= 1, (name, r, d)          # ALIGNMENT.md allows 5; measured 1


def test_the_page_fit_and_the_targets_use_the_same_frame_as_the_aims(tmp_path):
    """D1's mark check, its page check and the stages' targets all compare TARGETS (p1 values
    and what the alignment maps from them), with no sight offset anywhere: at the cap, a mark
    on it is accepted and one unit further refused; the frontmost patch on the proven edge is a
    target without DZ, one unit further needs DZ (front_y) and is allowed once confirmed."""
    sheet = _sheet()
    aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    good = pc.demo_aims()
    fit = pc.page_fit(sheet, 0, geo.fit_alignment(aims_mm, good))
    assert fit["spot_outside"] == 0 and fit["rows_outside"] == 0 and fit["front_need"] is None
    front = max(p[1] for p in good)
    geo.fit_alignment(aims_mm, [(x, y + CAP.ymax - front) for x, y in good])
    with pytest.raises(geo.AlignmentRefused, match="towards the back"):
        geo.fit_alignment(aims_mm, [(x, y + CAP.ymax - front + 1) for x, y in good])
    pts = [(q, sc.sheet_table_mm(sheet, q["centre_mm"]))
           for st in sheet["pages"][0]["strips"] for q in st["patches"]]
    al0 = geo.fit_model(aims_mm, good)
    q, u = max(pts, key=lambda t: al0.to_table(t[1])[1])
    pfront = al0.to_table(u)[1]
    for extra in (0, 1):
        moved = [(x, y + A.ymax - pfront + extra) for x, y in good]
        al = geo.fit_model(aims_mm, moved)
        if extra == 0:
            assert al.target(u, "the frontmost patch", run_out_mm=0.5)[1] == A.ymax
        else:
            with pytest.raises(geo.AreaRefused, match="DZ"):
                al.target(u, "the frontmost patch", run_out_mm=0.5)
            assert al.target(u, "p", run_out_mm=0.5, front_y=A.ymax + 1)[1] == A.ymax + 1
            assert pc.page_fit(sheet, 0, al)["front_need"] >= A.ymax + 1


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
    # ca99966f3's build 5975f18d...ecd083c with the builder's local source path (two copies of
    # one __FILE__ string) replaced in place by a neutral one of the same length, re-signed
    # ad hoc; machine code identical (work folder reader_privacy/PROOF.txt)
    assert h == "1caf32fc300bbb4488d5360d09f88d3bf4833df13428cf34b341ca31ea4e27ac"
    assert b"/Users/" not in (PKG / "bin" / "chromiq-chartread").read_bytes()


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


def test_the_real_reader_wrapper_logs_no_user_path(tmp_path):
    """A stand-in helper (a tiny Python script) that echoes a path: the log keeps names only."""
    import i1io_reader as rd
    helper = tmp_path / "fake-helper"
    helper.write_text("#!/usr/bin/env python3\nimport json, sys, os\n"
                      "print(json.dumps({'event': 'saved', 'path': os.path.expanduser('~/x.ti3')}))\n"
                      "sys.stdout.flush()\nsys.stdin.readline()\n")
    helper.chmod(0o755)
    logged = []
    p = rd._Proc([str(helper), "--json", "--i1io-table-scan", str(tmp_path / "out")],
                 lambda k, t: logged.append(t), tmp_path)
    ev = p.wait(("saved",), 10)
    p.stop({"cmd": "quit"})
    assert ev and ev["event"] == "saved"
    text = "\n".join(logged)
    assert str(Path.home()) not in text and str(tmp_path) not in text, text


def test_plan_and_dry_run_show_part_c(capsys):
    assert prog.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "PART C (choose c at the start)" in out
    for k, v in cl.C_FIXED.items():
        assert v.hex(" ") in out, k
    for st in pc.STAGES:
        assert f"{st.key.upper():3} {st.title}" in out


# ---- what the planted faults of the first pass showed was untested --------------------------

def _first_index(lines, pred, after=0):
    return next(i for i, x in enumerate(lines) if i >= after and pred(x))


def test_m0_at_any_other_speed_is_refused_by_the_builder_and_the_gate():
    for v in (150, 299, 301, 600, 3000):
        with pytest.raises(geo.AreaRefused):
            geo.m0_line(0, 2000, v)
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(geo._line("m0", 0, 2000, v))


def test_each_alignment_refusal_names_its_own_reason():
    sheet = _sheet()
    aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    good = pc.demo_aims()
    geo.fit_alignment(aims_mm, good)
    # mirrored top to bottom: only the order/mirror check sees it first
    cy = sum(p[1] for p in good) / 3
    with pytest.raises(geo.AlignmentRefused, match="mirrored"):
        geo.fit_alignment(aims_mm, [(x, round(2 * cy - y)) for x, y in good])
    # mark 3 turned 2 degrees about mark 2: lengths and rotation pass, the corner does not
    import math
    (x2, y2), (x3, y3) = good[1], good[2]
    c, s = math.cos(math.radians(2)), math.sin(math.radians(2))
    p3 = (round(x2 + c * (x3 - x2) - s * (y3 - y2)), round(y2 + s * (x3 - x2) + c * (y3 - y2)))
    with pytest.raises(geo.AlignmentRefused, match="corner at mark 2"):
        geo.fit_alignment(aims_mm, [good[0], good[1], p3])
    with pytest.raises(geo.AlignmentRefused, match="turned"):
        geo.fit_alignment(aims_mm, _rot(good, 5))
    with pytest.raises(geo.AlignmentRefused, match="apart on the table"):
        geo.fit_alignment(aims_mm, [good[0], good[1], (good[2][0] + 100, good[2][1])])


def test_a_computed_move_outside_its_time_window_but_arrived_is_a_clean_failure(tmp_path):
    lines, _ = _clean_run(tmp_path, ["d1", "d2", "f"])
    first = _first_index(lines, lambda x: x.startswith(";m0") and x not in WIRE_LINES)
    sim = csim.CSimTable(part_c=False)
    sim.inject_at(first, "late", 2.5)              # done 2.5 s late, inside the timeout
    code, sim, log, con, res = run_c(tmp_path / "f", ["d1", "d2", "f"], sim=sim)
    v = verdicts(log)
    assert v[1][0] == "d2" and v[1][1] == "failed cleanly", v
    assert "outside" in blocks(log)[1]["why"] and v[-1] == ("f", "worked")


@pytest.mark.parametrize("kind", ["status", "refuse"])
def test_a_computed_move_answered_with_a_status_ends_the_sitting(tmp_path, kind):
    lines, _ = _clean_run(tmp_path, ["d1", "d2", "f"])
    first = _first_index(lines, lambda x: x.startswith(";m0") and x not in WIRE_LINES)
    sim = csim.CSimTable(part_c=False)
    sim.inject_at(first, kind, 3.0)
    code, sim, log, con, res = run_c(tmp_path / "f", ["d1", "d2", "f"], sim=sim)
    assert code == 2 and verdicts(log)[-1] == ("d2", "stopped")
    assert sim.received[first + 1:] == []


@pytest.mark.parametrize("stages", [["e1"], ["d1", "d2"]])
def test_a_computed_move_that_arrives_elsewhere_ends_the_sitting_before_anything_else(
        tmp_path, stages):
    sim = csim.CSimTable(part_c=False)
    sim.c_faults["arrival_off"] = 20
    code, sim, log, con, res = run_c(tmp_path, stages + ["f"], sim=sim)
    assert code == 2
    assert verdicts(log)[-1][1] == "stopped"
    assert not any(x.startswith(";m2") for x in sim.received)
    last_m0 = max(i for i, x in enumerate(sim.received)
                  if x.startswith(";m0") and x not in WIRE_LINES)
    assert all(x in (P0, cl.C_FIXED["scan_d1"].decode().rstrip("\r"))
               for x in sim.received[last_m0 + 1:]), sim.received[last_m0:]


def test_c4_answered_outside_its_recorded_range_stops_before_the_row_start(tmp_path):
    sim = csim.CSimTable(part_c=False)
    sim.c_faults["c4_byte"] = 0xC0
    code, sim, log, con, res = run_c(tmp_path, ["e1", "c2"], sim=sim)
    v = verdicts(log)
    assert v[0] == ("e1", "failed cleanly") and "c4 answered C0" in blocks(log)[0]["why"]
    assert not any(x.startswith(";m2") for x in sim.received)
    assert not any(x == sc.RECORDED_ROW["m0_line"].decode().rstrip("\r") for x in sim.received)


def test_the_plan_check_refuses_an_unrecorded_speed_and_a_way_from_outside():
    plan = sc.plan_row("x", (-1000, 2000), (1000, 2000), 54)
    sc.check_plan(plan, at=(0, 2000))
    with pytest.raises(sc.PlanRefused):
        sc.check_plan(plan, at=(-1500, 2000))           # the way from outside the area
    with pytest.raises(sc.PlanRefused):
        sc.check_plan(sc.plan_row("x", (-1000, 2000), (1000, 2000), 200))


def test_the_pending_scan_move_closes_the_session_at_once(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["e1"], readers=readers(scan={"no_lamp": True}))
    assert "nothing more is sent: a scan move may be pending" in log


def test_e2_e3_are_not_offered_without_a_strip_calibration(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c2", "d1", "e2", "f"])
    assert [k for k, _ in verdicts(log)] == ["c2", "d1", "f"]
    assert "E2 (it needs a strip calibration in this sitting (C1 or E1))" in screen(con)


def test_a_recorded_patch_move_that_arrives_elsewhere_stops_the_row(tmp_path):
    lines, _ = _clean_run(tmp_path, ["c3", "c4"])
    spot5 = sim_mod.SPOTS[4]
    i = lines.index(spot5)
    sim = csim.CSimTable(part_c=False)
    sim.inject_at(i, "blocked", 1.0)
    code, sim, log, con, res = run_c(tmp_path / "b", ["c3", "c4"], sim=sim)
    assert code == 2 and verdicts(log)[-1] == ("c4", "stopped")
    assert sim.received[i + 1:] == [P0]
    assert "at patch 5" in blocks(log)[-1]["why"]


def test_part_c_s_session_caps_are_applied(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "C_MAX_LINES", 40)
    code, sim, log, con, res = run_c(tmp_path, ["c1", "c2", "e1"])
    assert code == 2 and "limit of lines for one session" in log
    assert len(sim.received) == 40


def test_the_simulator_refuses_a_scan_move_without_a_ready_instrument_and_without_c3(tmp_path):
    sim = csim.CSimTable(part_c=True, pos=[0.0, 2000.0], jitter=False)
    sim.instrument = None
    with pytest.raises(sim_mod.SimViolation):
        sim.receive(geo.m2_line(1000, 2000, 54))
    assert sim.violations
    sim2 = csim.CSimTable(part_c=True, pos=[0.0, 2000.0], jitter=False)
    inst = csim.FakeScanReader(sim2, str(tmp_path), lambda k, t: None,
                               faults={"restored": True})
    inst.lights_off()
    sim2.clock += 2.0
    assert inst.arm(100)["ready"] is True
    sim2.receive(geo.m2_line(1000, 2000, 54))
    sim2.receive(cl.C_FIXED["scan_a3"])
    sim2.lamp(sim2.clock)                    # no c3 yet: the move must not start
    assert not sim2.m2_pending["lamp"] and not sim2.scan_moves


def test_the_fake_spot_reader_refuses_to_read_while_the_arm_moves(tmp_path):
    sim = csim.CSimTable(part_c=True, pos=[0.0, 2000.0], jitter=False)
    sim._busy_until = sim.clock + 5.0
    r = csim.FakeSpotReader(sim, str(tmp_path), "x", [("1", "A1")], lambda k, t: None, False)
    with pytest.raises(sim_mod.SimViolation):
        r.read("A1")
    assert sim.violations


def test_a_confirmed_region_is_asked_about_once(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c2", "d1", "d2", "d3", "f"])
    asked = [q for q, *_ in con.seen if q.endswith("Make this move now?")]
    assert 1 <= len(asked) <= 2, len(asked)          # D2's move, D3's row: never per patch


def test_geometry_first_visit_matches_the_driven_boxes():
    assert not geo.first_visit((-1000, 1600), (1000, 2500))       # inside the chart box
    assert geo.first_visit((-1000, 1200), (1000, 1200))           # behind every recorded chart
    assert geo.first_visit((1500, 2000), (1600, 2000))            # the left 45 mm


# ---- safety review of 7382e56f2: the recommended changes ------------------------------------

@pytest.mark.parametrize("stages", [["e1"], ["c1", "d1", "e2"], ["c1", "d1", "e3"]])
def test_a_strip_row_from_a_free_arm_reads_it_twice_and_a_hand_on_it_stops_cleanly(tmp_path,
                                                                                  stages):
    """E1, E2 and E3 start the motors from a free arm only after two readings that agree within
    STILL_UNITS, as D2, D3 and part B's step B4 do."""
    lines, _ = _clean_run(tmp_path, stages + ["f"])
    c4 = cl.C_FIXED["scan_c4"].decode().rstrip("\r")
    first_c4 = _first_index(lines, lambda x: x == c4)
    # the clean run: p0, p0 (the stillness check), c4
    assert lines[first_c4 - 2:first_c4] == [P0, P0]
    sim = csim.CSimTable(part_c=False)
    sim.inject_at(first_c4 - 1, "drift", tbl.STILL_UNITS + 3)
    code, sim, log, con, res = run_c(tmp_path / "hand", stages + ["f"], sim=sim)
    v = verdicts(log)
    assert (stages[-1], "failed cleanly") in v, v
    assert "the free arm moved between two readings" in screen(con)
    assert c4 not in sim.received                 # nothing after the second reading
    assert not any(x.startswith(";m2") for x in sim.received)
    assert sim.violations == []


@pytest.mark.parametrize("stages", [["e1"], ["c1", "d1", "e2"]])
def test_a_lamp_trigger_that_could_not_be_sent_says_switch_off_at_once(tmp_path, stages):
    """The reader had stopped before the trigger could be handed to it: SWITCH THE TABLE OFF is
    shown at once, not after waiting move + 10.5 s for a done answer that cannot come."""
    calls = []

    def factory(s, lg):
        r = REAL_FAKE_READERS(s, lg)
        real_scan = r.scan

        def scan(folder):
            calls.append(folder)
            x = real_scan(folder)
            if len(calls) == len([k for k in stages if k in ("c1", "e1", "e2")]):
                x.faults["fire_unsent"] = True
            return x
        r.scan = scan
        return r
    sim = csim.CSimTable(part_c=False)
    said_at = []

    class Timed(CScript):
        def say(self, text=""):
            if "SWITCH THE TABLE OFF" in text:
                said_at.append(self.sim.clock)
            super().say(text)
    con_cls = Timed
    code, sim, log, con, res = run_c(tmp_path, stages, sim=sim, readers=factory,
                                     console_cls=con_cls)
    assert code == 2 and said_at
    t_m2 = sim.received_at[max(i for i, x in enumerate(sim.received) if x.startswith(";m2"))]
    assert said_at[0] - t_m2 < 1.5, (said_at[0], t_m2)          # not after move + 10.5 s
    assert list(res.rglob(sc.PENDING_MARKER))
    last_m2 = max(i for i, line in enumerate(sim.received) if line.startswith(";m2"))
    assert sim.received[last_m2 + 1:] == [cl.C_FIXED["scan_a3"].decode().rstrip("\r"),
                                          cl.C_FIXED["scan_c3"].decode().rstrip("\r")]
    assert "the lamp trigger could not be sent" in log


def test_the_scan_path_sets_defer_stop_only_inside_its_try_after_busy():
    """Review (2)(b): a Ctrl-C between the two lines can no longer leave defer_stop set."""
    import inspect
    src = inspect.getsource(sc.run_row)
    i_busy = src.index("table.busy += 1")
    i_try = src.index("try:", i_busy)
    i_defer = src.index("table.defer_stop = True")
    assert i_busy < i_try < i_defer
    assert src.count("table.defer_stop = True") == 1


def test_the_real_reader_reports_a_fire_it_could_not_send():
    import i1io_reader as rd

    class Dead:
        def poll(self):
            return 1

    class P:
        p = Dead()

        def send(self, obj):
            raise rd.ReaderFailed("gone")
    r = rd.ScanReader.__new__(rd.ScanReader)
    r.proc = P()
    r.log = lambda *a: None
    r.alive = lambda: True
    assert r.fire(10, 1, "x") is False
    r.alive = lambda: False
    assert r.fire(10, 1, "x") is False


def test_every_area_text_says_where_it_lies_is_our_estimate(tmp_path):
    """Review (3) correction 2, and fix 2: wherever a text speaks of the area to the person, it
    says that WHERE it lies on his table is our estimate, proven part and front part."""
    assert "our estimate" in pc.AREA_WHERE and "measuring opening" in pc.AREA_WHERE
    assert "proven part" in pc.AREA_WHERE and "front part" in pc.AREA_WHERE
    assert pc.AREA_WHERE in _flat(pc.SHEET_LAY)
    assert "our estimate" in _flat(pc.STAGE_BY_KEY["d1"].explain)
    assert "feel its way forward" in _flat(pc.STAGE_BY_KEY["d1"].explain)
    assert any("our estimate" in ln for ln in prog.plan_part_c())
    code, sim, log, con, res = run_c(tmp_path, ["d1", "d2", "f"])
    first = [ln for ln in con.said if "no recording drove it to" in ln]
    assert first and all(pc.AREA_WHERE in _flat(ln) for ln in first), first
    assert ("d2", "worked") in verdicts(log)
    with pytest.raises(geo.AlignmentRefused, match="our estimate"):
        pts = geo.RECORDED_ALIGNMENTS["S2 383.3"]
        geo.fit_alignment(_aims_mm(pts), [(x, y + 200) for x, y in pts])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_an_aim_that_is_not_a_number_is_refused_as_an_alignment(bad):
    """Planted-fault pass of fix 1: a non-finite aim or sheet mark ends as AlignmentRefused
    (a clean D1 failure), never as an OverflowError or ValueError."""
    sheet = _sheet()
    aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    good = pc.demo_aims()
    for k in range(3):
        for axis in range(2):
            pts = [list(p) for p in good]
            pts[k][axis] = bad
            with pytest.raises(geo.AlignmentRefused, match="not a finite number"):
                geo.fit_model(aims_mm, pts)
            mm = [list(p) for p in aims_mm]
            mm[k][axis] = bad
            with pytest.raises(geo.AlignmentRefused, match="not a finite number"):
                geo.fit_alignment(mm, good)


def test_d1_s_page_check_itself_says_the_area_is_our_estimate_and_why_back():
    sheet = _sheet()
    aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    good = pc.demo_aims()
    assert not any(pc.AREA_WHERE in ln for ln in
                   pc.page_fit(sheet, 0, geo.fit_alignment(aims_mm, good))["say"])
    far = geo.fit_model(aims_mm, [(x, y + 600) for x, y in good])
    say = pc.page_fit(sheet, 0, far)["say"]
    assert pc.AREA_WHERE in say[0] and pc.WHY_BACK in say[0]
    assert any("further towards the back" in ln for ln in say)


def test_the_readme_has_no_old_area_numbers_and_the_table_rule_of_part_c():
    readme = _flat((PKG / "README.md").read_text(encoding="utf-8"))
    for old in ("859", "3059", "809", "X-Rite's specified measuring area", "8122", "2841"):
        assert old not in readme, old
    assert ("keep the table empty except for the chart or sheet a stage asks for" in readme)
    assert "keep the table empty," not in readme
    assert "Where that area lies on your table is our estimate" in readme
    assert f"up to table Y {geo.FRONT_CAP_Y} at the most" in readme
    assert "If your sheet reaches into the front part, D1 lets you choose" in readme
    assert "`back`" in readme and "`go on`" in readme


# ---- fix 2: the front zone and the creep (stage DZ) -----------------------------------------

def _recorded_sheet(tmp_path, name, rows, cols=28):
    """A ChromIQ-style sheet file whose three marks are the corner patches of a chart with the
    sizes of the recorded alignment *name* (its aimed distances), *rows* + 1 rows of *cols*
    patches: the chart the person aimed at in that session, as far as the geometry goes."""
    import math
    pts = geo.RECORDED_ALIGNMENTS[name]
    W = math.dist(pts[1], pts[2]) / 10
    H = math.dist(pts[0], pts[1]) / 10
    h, x0, y0 = 297.0, 20.0, 20.0

    def page(tx, ty):                    # table mm (x right, y down) -> page mm
        return [round(ty, 3), round(h - tx, 3)]
    strips, sid = [], 1
    for r in range(rows + 1):
        ty = y0 + r * H / rows
        pats = []
        for c in range(cols):
            tx = x0 + c * W / (cols - 1)
            pats.append({"loc": f"R{r + 1}C{c + 1}", "sample_id": sid, "centre_mm": page(tx, ty)})
            sid += 1
        run = sorted((h - (x0 + W + 5), h - (x0 - 5)))
        strips.append({"x_mm": round(ty, 3), "run_mm": [round(v, 3) for v in run],
                       "patches": pats})
    aims = [{"number": 1, "corner_on_table": "top-left", "target": "patch", "patch": "R1C1",
             "page_mm": page(x0, y0)},
            {"number": 2, "corner_on_table": "bottom-left", "target": "patch",
             "patch": f"R{rows + 1}C1", "page_mm": page(x0, y0 + H)},
            {"number": 3, "corner_on_table": "bottom-right", "target": "patch",
             "patch": f"R{rows + 1}C{cols}", "page_mm": page(x0 + W, y0 + H)}]
    sheet = {"schema": 1, "paper_mm": [210.0, h], "patch_mm": [8.0, round(W / (cols - 1), 3)],
             "orientation": "as in your i1Profiler session",
             "pages": [{"strips": strips, "aim_points": aims}]}
    f = tmp_path / f"recorded-{name.replace(' ', '_')}.i1io.json"
    f.write_text(json.dumps(sheet))
    return f, pts


GO_ON = {"back (lay the sheet further back": "go on", "To go on, type yes": "yes"}


@pytest.mark.parametrize("name,rows", [("S2 684.0", 18), ("R1 401.6", 17)])
def test_a_recorded_alignment_runs_d1_dz_d2_d3(tmp_path, name, rows):
    """Fix 2: a sheet laid as in a recorded i1Profiler session (its aims exactly the recorded
    p1 readings) now runs D1 -> DZ (the creep) -> D2 -> D3 on the simulator: DZ confirms the
    front zone up to the frontmost Y the sheet needs, in steps of at most 5 mm, and only then is
    mark 3 (in the front zone) driven to."""
    f, pts = _recorded_sheet(tmp_path, name, rows)
    sim = csim.CSimTable(part_c=False, aims=pts)
    code, sim, log, con, res = run_c(tmp_path / "run", ["c1", "d1", "d2", "dz", "d2", "d3", "f"],
                                     sim=sim, sheet=f, script=GO_ON)
    v = verdicts(log)
    assert v == [("c1", "worked"), ("d1", "worked"), ("dz", "worked"), ("d2", "worked"),
                 ("d3", "worked"), ("f", "worked")], v
    assert sim.violations == []
    text = screen(con)
    assert "D2 (it needs DZ first (the front part of the table))" in text
    need = [b for b in blocks(log) if b["stage"] == "d1"][0]["data"]["front_need_y"]
    assert abs(need - max(p[1] for p in pts)) <= 2 and need <= geo.FRONT_CAP_Y
    dz = [b for b in blocks(log) if b["stage"] == "dz"][0]
    assert dz["front_zone_reached_y"] == need
    assert f"front zone reached: Y {need}" in log
    # the creep: m0 at 300, straight forward along Y, each step at most 5 mm
    creep = [geo.decode_xyv(x.encode() + b"\r") for x in computed(sim)]
    ys = [c[2] for c in creep if c[2] > A.ymax]
    first_front = next(i for i, c in enumerate(creep) if c[2] > A.ymax)
    steps = creep[first_front - 1:first_front - 1 + len([y for y in ys if y <= need])]
    for a, b in zip(steps, steps[1:]):
        if b[2] > A.ymax and b[2] > a[2]:
            assert b[1] == a[1] and 0 < b[2] - a[2] <= geo.CREEP_STEP and b[3] == 300
    assert max(ys) == need <= geo.FRONT_CAP_Y
    # D2 drove to mark 3 only after the creep
    d2 = [b for b in blocks(log) if b["stage"] == "d2"]
    assert abs(d2[-1]["position_after"][1] - pts[2][1]) <= 2


def _dz_run(tmp_path, sim=None, **kw):
    tmp_path.mkdir(parents=True, exist_ok=True)
    f, pts = _recorded_sheet(tmp_path, "S2 684.0", 18)
    sim = sim or csim.CSimTable(part_c=False, aims=pts, jitter=False)
    script = dict(GO_ON)
    script.update(kw.pop("script", {}))
    return run_c(tmp_path / "run", ["c1", "d1", "dz", "d2", "d3", "f"], sim=sim, sheet=f,
                 script=script, **kw) + (pts,)


def _creep_lines(lines):
    """Indices of the creep steps' m0 lines in a clean DZ sitting (computed m0 to Y > 2723)."""
    out = []
    for i, x in enumerate(lines):
        if x.startswith(";m0") and x not in WIRE_LINES:
            _c, mx, my, _v = geo.decode_xyv(x.encode() + b"\r")
            if my > A.ymax and mx == 1164:          # straight forward behind mark 2 (S2 684.0)
                out.append(i)
    return out


def test_dz_stops_at_a_mechanical_front_end_and_offers_only_the_homing(tmp_path):
    """The worst credible outcome: a 5 mm step meets the mechanical front end and stalls. The
    arrival check notices it, the creep stops, the front limit stays at the last clean step,
    nothing more moves but the homing, which works from the held arm."""
    f, pts = _recorded_sheet(tmp_path, "S2 684.0", 18)
    sim = csim.CSimTable(part_c=False, aims=pts, jitter=False)
    sim.c_faults["front_wall"] = 2900
    code, sim, log, con, res, _p = _dz_run(tmp_path, sim=sim)
    v = verdicts(log)
    assert v == [("c1", "worked"), ("d1", "worked"), ("dz", "failed cleanly"), ("f", "worked")], v
    dz = [b for b in blocks(log) if b["stage"] == "dz"][0]
    assert "did not arrive" in dz["why"] and dz["front_zone_reached_y"] == 2873
    assert "The arm reads X 1164, Y 2900, held" in dz["why"]
    assert "Not offered now" in screen(con) and "only the homing" in screen(con)
    ys = [geo.decode_xyv(x.encode() + b"\r")[2] for x in computed(sim)]
    assert max(ys) == 2923                     # the stalled step, never one beyond it
    assert sim.violations == []


@pytest.mark.parametrize("k", [0, 2, 5])
@pytest.mark.parametrize("kind", ["late", "slow_motion"])
def test_dz_stops_on_a_step_outside_its_time_window(tmp_path, k, kind):
    code, sim, log, con, res, pts = _dz_run(tmp_path / "clean")
    lines = sim.received
    idx = _creep_lines(lines)
    assert len(idx) == 6
    sim = csim.CSimTable(part_c=False, aims=pts, jitter=False)
    sim.inject_at(idx[k], kind, 2.5)
    code, sim, log, con, res, _p = _dz_run(tmp_path / "f", sim=sim)
    v = verdicts(log)
    assert ("dz", "failed cleanly") in v or ("dz", "stopped") in v, v
    dz = [b for b in blocks(log) if b["stage"] == "dz"][0]
    confirmed = [2773, 2823, 2873, 2923, 2973, 3009]
    assert dz["front_zone_reached_y"] == (confirmed[k - 1] if k else None)
    # nothing in front of the stopped step afterwards, and no D2
    after = [geo.decode_xyv(x.encode() + b"\r") for x in sim.received[idx[k] + 1:]
             if x.startswith(";m0") or x.startswith(";m2")]
    assert all(c[2] <= A.ymax for c in after if c[0] in ("m0", "m2")), after
    assert ("d2", "worked") not in v
    assert sim.violations == []
    check_truthful(sim, con, log)


def test_dz_enter_at_every_pause_stops_cleanly_with_the_limit_reached(tmp_path):
    confirmed = [2773, 2823, 2873, 2923, 2973, 3009]
    # count the polls before DZ in a clean sitting (C1 and D1 do not poll)
    for n in range(1, 7):
        code, sim, log, con, res, pts = _dz_run(tmp_path / f"e{n}", stop_at_poll=n)
        v = verdicts(log)
        dz = [b for b in blocks(log) if b["stage"] == "dz"][0]
        assert dz["verdict"] == "stopped by you (clean)", (n, v)
        assert dz["front_zone_reached_y"] == confirmed[n - 1], n
        assert sim.violations == [], n
        check_truthful(sim, con, log)
        if n < 6:
            assert ("d2", "worked") not in v, (n, v)     # mark 3 lies beyond what was reached


@pytest.mark.slow       # exhaustive: every line of DZ (--runslow)
def test_ctrl_c_at_any_line_of_dz_sends_nothing_more(tmp_path):
    import signal
    code, sim, log, con, res, pts = _dz_run(tmp_path / "clean")
    lines = list(sim.received)
    idx = _creep_lines(lines)
    lo, hi = idx[0] - 6, idx[-1] + 2
    for i in range(lo, hi + 1):
        sim = csim.CSimTable(part_c=False, aims=pts, jitter=False)

        def hook(n, i=i):
            if n == i:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
        code, sim, log, con, res, _p = _dz_run(tmp_path / f"c{i}", sim=sim)
        assert sim.violations == [], (i, sim.violations)
        assert code in (0, 1), i
        assert sim.received[:i + 1] == lines[:i + 1]
        assert sim.received[i + 1:] == [], (i, sim.received[i + 1:])
        assert not sim.moving
        check_truthful(sim, con, log)


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["no_answer", "status", "late", "refuse", "no_done", "garbled"])
def test_any_fault_at_any_line_of_dz_keeps_every_rule(tmp_path, kind):
    code, sim, log, con, res, pts = _dz_run(tmp_path / "clean")
    lines = list(sim.received)
    idx = _creep_lines(lines)
    for i in range(idx[0] - 6, idx[-1] + 2):
        sim = csim.CSimTable(part_c=False, aims=pts, jitter=False)
        sim.inject_at(i, kind, 30.0 if kind == "late" else 1.0)
        code, sim, log, con, res, _p = _dz_run(tmp_path / f"{kind}{i}", sim=sim)
        assert sim.violations == [], (kind, i, sim.violations)
        check_no_question_while_moving(con)
        check_truthful(sim, con, log)
        assert sim.received[:i + 1] == lines[:i + 1]
        # nothing ever beyond what was confirmed before the fault + one step
        ys = [geo.decode_xyv(x.encode() + b"\r")[2] for x in sim.received[i + 1:]
              if (x.startswith(";m0") or x.startswith(";m2")) and x not in WIRE_LINES]
        reached = max([geo.decode_xyv(x.encode() + b"\r")[2] for x in lines[:i + 1]
                       if x.startswith(";m0") and x not in WIRE_LINES] + [A.ymax])
        assert all(y <= max(reached, A.ymax) for y in ys) or code == 0, (kind, i, ys)


def test_the_gate_lets_a_front_target_through_only_up_to_the_confirmed_y():
    t = _T()
    t.front_y = None
    t.creep = False
    gate = cl.make_gate(t)
    t.position_now = (0, 2700)
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, A.ymax + 1))                    # nothing confirmed yet
    t.creep = True
    t.position_now = (0, A.ymax)
    assert gate(geo.m0_line(0, A.ymax + 50))[2] == "computed m0"     # one creep step
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, A.ymax + 51))                   # beyond one step
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(51, A.ymax + 10))                  # more than 5 mm sideways
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m2_line(0, A.ymax + 10, 54))               # a strip never creeps
    t.creep = False
    t.front_y = 2900
    t.position_now = (0, 2000)
    assert gate(geo.m0_line(0, 2900))[2] == "computed m0"
    assert gate(geo.m2_line(0, 2900, 54))[2] == "scan move"
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, 2901))
    t.front_y = geo.FRONT_CAP_Y + 500                        # never beyond the cap
    t.creep = True
    t.position_now = (0, geo.FRONT_CAP_Y - 10)
    with pytest.raises(geo.AreaRefused):
        geo.m0_line(0, geo.FRONT_CAP_Y + 1)
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo._line("m0", 0, geo.FRONT_CAP_Y + 1, 300))
    assert gate(geo.m0_line(0, geo.FRONT_CAP_Y))[2] == "computed m0"


def test_dz_s_caps_and_the_creep_step_are_pinned():
    dz = pc.STAGE_BY_KEY["dz"]
    assert geo.CREEP_STEP == 50 and pc.CREEP_STEPS_MAX == 10
    assert dz.max_moves == 11 and dz.max_runs == 3          # 33 creep-stage moves per sitting
    assert (geo.FRONT_CAP_Y - A.ymax) / geo.CREEP_STEP < pc.CREEP_STEPS_MAX
    assert dz.first_try and "5 mm" in dz.explain


def test_strip_rows_in_the_front_zone_first_reach_both_ends_by_spot_moves(tmp_path):
    f, pts = _recorded_sheet(tmp_path, "S2 684.0", 18)
    sim = csim.CSimTable(part_c=False, aims=pts)
    script = dict(GO_ON)
    code, sim, log, con, res = run_c(tmp_path / "run", ["c1", "d1", "e3", "dz", "e3", "f"],
                                     sim=sim, sheet=f, script=script)
    v = verdicts(log)
    assert v == [("c1", "worked"), ("d1", "worked"), ("dz", "worked"), ("e3", "worked"),
                 ("f", "worked")], v
    assert "E3 (it needs DZ first (the front part of the table))" in screen(con)
    e3 = [b for b in blocks(log) if b["stage"] == "e3"][0]
    front_rows = e3["data"]["front_row_ends_confirmed"]
    assert front_rows and all(r.startswith("p1_row") for r in front_rows)
    # every front row's m2 follows an m0 to its start AND an m0 to its end
    rec = sim.received
    for i, x in enumerate(rec):
        if x.startswith(";m2"):
            _c, mx, my, _v = geo.decode_xyv(x.encode() + b"\r")
            if my > A.ymax:
                before = [geo.decode_xyv(y.encode() + b"\r")[1:3] for y in rec[:i]
                          if y.startswith(";m0") and y not in WIRE_LINES][-3:]
                assert (mx, my) in before, (x, before)
    assert sim.violations == []
