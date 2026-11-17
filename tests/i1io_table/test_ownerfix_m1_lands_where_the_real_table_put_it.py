"""The short move m1 ends where the REAL table put the opening (owner-results fix round, M-1/M-1b).

On the volunteer's i1iO 2 on 17 Nov 2026 the tester's alignment start stopped twice, at the same
place: after m1 (0.400 s from (2507, 1498) and from (2505, 1498)) the arm read (2507, 1429), and
the program expected (2832, 1371) or a "sight frame" box around (2716, 1057). Both were our own
wrong belief, and the simulators carried the same belief, so no test could catch it. Every START
of the in-app drive runs that very step (`job._align` runs C_ALIGN), so every table measurement
would have stopped there.

Test data (nothing private), from the analysis of that night:
  m1 `;m10b10055b012c42` -> `:!m107`, `:$m10D4` after 0.400 s; `;p025` -> `:$p0009CB059511`
  = (2507, 1429); i1Profiler's own m1 from (999, 1503) took 1.759 s.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import session_sim as ss
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

ROOT = Path(__file__).resolve().parents[2]
M1_LINE = ";m10b10055b012c42"
M1_ACK, M1_DONE = ":!m107", ":$m10D4"
P0_AFTER_M1 = ":$p0009CB059511"


def test_the_recorded_answers_after_m1_decode_to_the_measured_landing():
    assert tbl.WIRE["m1"] == (M1_LINE + "\r").encode()
    tbl.parse_ack(M1_ACK, "m1")
    assert tbl.parse_done(M1_DONE, "m1").data == ""
    assert tbl.parse_done(P0_AFTER_M1, "position").xy() == (2507, 1429)


def test_the_one_expected_place_after_m1_is_the_measured_one_with_the_usual_tolerance():
    assert tbl.AT_M1 == tbl.near(2507, 1429)
    assert tbl.AT_M1.contains((2507, 1429))
    # the tolerance every recorded arrival uses (ARRIVAL_SLACK / near(): 5 units)
    assert tbl.AT_M1.contains((2502, 1434)) and not tbl.AT_M1.contains((2501, 1429))
    for gone in ("AT_M1_SENSOR", "AT_M1_SIGHT"):
        assert not hasattr(tbl, gone), gone


def test_the_simulators_land_m1_where_the_real_table_did():
    assert ss.M1_LANDS == (2507.0, 1429.0)
    assert ss.SimTable().m1_lands_at == (2507.0, 1429.0)
    assert csim.CSimTable(part_c=True).m1_lands_at == (2507.0, 1429.0)
    assert not hasattr(ss, "M1_BELIEF")
    # the recorded times: 0.400 s from the far side, 1.759 s from i1Profiler's own start
    t_far = ss.SimTable(jitter=False, pos=[2507.0, 1498.0])._execute(M1_LINE, "m1", "", None)[2]
    t_1000 = ss.SimTable(jitter=False, pos=[999.0, 1503.0])._execute(M1_LINE, "m1", "", None)[2]
    assert t_far == pytest.approx(0.400) and t_1000 == pytest.approx(1.759)


def _align_until_felt(**simkw):
    asked = []

    def on_ask(person, res):
        asked.append(res.confirm)
        if res.confirm == J.Confirm.ARM_FELT:
            return res              # stop driving here: the alignment start was accepted
        return None
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), **simkw)
    job, sim, _t = H.make_job(sim=sim)
    person = H.Person(job, sim, on_ask=on_ask)
    assert person.drive(job.open()).ok
    res = person.drive(job.align())
    return res, job, sim, asked


def test_a_start_on_a_table_that_behaves_like_the_real_one_reaches_the_aims():
    """Failed before this round: the job stopped right after m1 on every START."""
    res, job, sim, asked = _align_until_felt()
    assert J.Confirm.ARM_FELT in asked, (res.kind, res.reason)
    sent = sim.received
    i = sent.index(M1_LINE)
    # m1, then the reading, then i1Profiler's lines that let the arm go (f3 ... f1)
    assert sent[i + 1] == ";p025"
    assert ";f12e" in sent[i + 2:]
    assert any("after m1: the arm reports (2507, 142" in ln for ln in job.diag.lines)
    # the simulated table answers m1 exactly as the real one did, in the recorded time
    log = job.diag.lines
    k = next(n for n, ln in enumerate(log) if ln.endswith(M1_LINE))
    assert log[k + 1].endswith(M1_ACK) and log[k + 2].endswith(M1_DONE)
    assert "m1 (m1) took 0.400 s" in log[k + 3]


@pytest.mark.parametrize("where", [(2716.0, 1057.0), (2832.0, 1371.0), (2514.0, 1429.0),
                                   (2507.0, 1498.0)])
def test_any_other_landing_stops_the_session_truthfully(where):
    """The old belief, the target field, one unit outside the tolerance, a move that did not
    happen: nothing more is sent after the reading, nothing moves any more."""
    res, job, sim, asked = _align_until_felt(m1_lands_at=where)
    assert res.kind == J.Kind.STOPPED, (res.kind, res.reason)
    assert J.Confirm.ARM_FELT not in asked
    sent = sim.received
    i = sent.index(M1_LINE)
    assert sent[i + 1:] == [";p025"], sent[i + 1:]
    assert job._table.closed_reason is not None
    got = tuple(job._table.outside_at)
    assert abs(got[0] - where[0]) <= 1 and abs(got[1] - where[1]) <= 1      # the sim's jitter


def test_where_the_motors_drove_the_arm_no_longer_holds_the_m1_target_field():
    """DRIVEN came partly from m1's target field (2832, 1371), where the arm never was."""
    assert not any(b.xmax > 2507 for b in geo.DRIVEN)
    approach = [b for b in geo.DRIVEN if b.xmax == 2507]
    assert approach == [geo.Area(1000, 2507, 1429, 1500)]
    assert geo.first_visit((2507, 1429), (2507, 1498)) is False
    assert geo.first_visit((2507, 1498), (2600, 1450)) is True


def test_no_text_or_comment_keeps_the_wrong_m1_explanation():
    sources = [inspect.getsource(tbl), inspect.getsource(geo),
               (ROOT / "tests/i1io_table/session_sim.py").read_text(encoding="utf-8"),
               (ROOT / "tests/i1io_table/part_c_sim.py").read_text(encoding="utf-8")]
    for src in sources:
        for wrong in ("puts the alignment sight", "two explanations", "neither explanation",
                      "m1_frame", "(2716, 1057) \"", "M1_BELIEF ="):
            assert wrong not in src, wrong
