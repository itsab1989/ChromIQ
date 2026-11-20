"""4.3.50: the simulator the table tests run on behaves like the REAL i1iO 2 where real data now
exists (the first complete page ChromIQ read on a volunteer's table, 19 Nov 2026), so no test can
pass on a simulated table that the real one would contradict, or fail on what the real one did.

* THE REPLAY: every computed move of that page (545 m0 at speed 300, in the order sent, from
  ``data/real_table_moves.json``: where the arm was read before, the target, the time, numbers
  only) is sent to the simulator from the same place. The simulator must accept every one (no
  violation, no target booked as "at the front end"), answer it inside the job's own time window
  for that move, and within 0.03 s of the real time.
* Move time on the straight-line distance (the real diagonal to the first row took 0.25 s longer
  than the simulator's larger-axis model).
* A move of 0 to 3 units is answered at once, in 0.016 s, as on the real table.
* The front end: the real arm went to Y 3370 under motor in 5 mm steps without meeting an end, so
  the simulated end (an ASSUMPTION, still: where the real end is, nobody knows) lies beyond that
  and its 5 mm margin.
* The resting place after a homing reads Y 28-32 (the real table, 19 Nov), not 0-2.
* A freed arm settles as measured: (-5, +12) on 18 Nov, (-1, +4) on 19 Nov; both are simulated
  and a page is read with either.
"""
from __future__ import annotations

import json

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import session_sim as ss
from tests.i1io_table.job_harness import HERE
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J

DATA = json.loads((HERE / "data" / "real_table_moves.json").read_text(encoding="utf-8"))
REAL = DATA["real_run_2026_11_19"]


def _send(sim, line: str) -> float:
    """One line to the simulator, the time of its done answer after it (s)."""
    t0 = sim.clock
    sim.receive((line + "\r").encode("ascii"))
    dones = [t for t, b in sim._out if b.startswith(f":${line[1:3]}".encode())]
    assert dones, f"no done answer to {line}"
    took = max(dones) - t0
    sim._out = []
    sim.clock = max(sim.clock, sim._busy_until) + 0.05
    return took


def test_the_real_page_replays_on_the_simulator():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.started = True
    off = []
    for k, (fx, fy, tx, ty, speed, took, _ax, _ay, free) in enumerate(REAL):
        sim.pos = [float(fx), float(fy)]
        sim.free_arm = bool(free)
        sim.mode = "01" if free else "00"
        # (the two recorded way-out lines of the alignment are among them: built as sent, not
        # through the job's area check)
        line = geo._line("m0", tx, ty, speed).decode("ascii").rstrip("\r")
        got = _send(sim, line)
        lo, hi = geo.move_window((fx, fy), (tx, ty), speed)
        if not (lo <= got <= hi and abs(got - took) <= 0.03):
            off.append((k, (fx, fy), (tx, ty), took, round(got, 3), (round(lo, 3), round(hi, 3))))
    assert sim.violations == []
    assert sim.end_targets == []
    assert off == [], off[:10]


def test_the_move_time_is_the_straight_line():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.started = True
    sim.pos = [1248.0, 1593.0]
    sim.front_seen = 3371.0
    # the real page's move to its first row: (2598, 1778) units diagonal, 2.528 s
    got = _send(sim, geo.m0_line(-1350, 3371).decode("ascii").rstrip("\r"))
    assert abs(got - 2.528) <= 0.03, got


@pytest.mark.parametrize("d", [0, 1, 2, 3])
def test_a_tiny_move_is_answered_at_once(d):
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.started = True
    sim.pos = [-1350.0, 3367.0]
    sim.front_seen = 3370.0
    got = _send(sim, geo.m0_line(-1350, 3367 + d).decode("ascii").rstrip("\r"))
    assert abs(got - 0.016) <= 0.002, got


def test_the_front_end_lies_beyond_where_the_real_arm_went():
    reached = max(r[3] for r in REAL)         # the frontmost target the real arm arrived at
    assert reached == 3370 and max(r[7] for r in REAL) == 3369
    assert csim.FRONT_END_Y - csim.FRONT_END_MARGIN > reached
    # still an assumption, and said so
    assert "ASSUMED" in csim.FRONT_END_WHY


def test_the_arm_rests_where_the_real_one_rests_after_a_homing():
    rests = set()
    for seed in range(1, 30):
        sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), seed=seed)
        sim.started = True
        sim.pos = [1102.0, 30.0]
        _send(sim, ss.I1)
        rests.add(sim.pos[1])
    assert rests and min(rests) >= 28 and max(rests) <= 32


def test_both_measured_settles_are_simulated():
    assert ss.RELEASE_SETTLES_MEASURED == ((-5.0, 12.0), (-1.0, 4.0))
    assert ss.RELEASE_SETTLE_REAL == ss.RELEASE_SETTLES_MEASURED[0]


@pytest.mark.parametrize("settle", [(-5.0, 12.0), (-1.0, 4.0)], ids=["18 Nov", "19 Nov"])
def test_a_page_is_read_with_either_settle(tmp_path, settle):
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), release_settle=settle)
    results, job, sim, person = H.run_steps(
        ["open", "align", "home"], sim=sim, folder=tmp_path)
    assert [r.kind for r in results] == [J.Kind.OK] * 4, [(r.step, r.reason) for r in results]
    assert sim.violations == []
