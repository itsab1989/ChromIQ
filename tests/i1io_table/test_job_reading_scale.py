"""Build step 7: the layout's densest page (37 rows of 49 patches, 1813, on the largest piece; and
30 rows of 33, 990, on the largest whole sheet, 230 x 320 mm) and a chart of several such pages, read patch by patch in simulation, TIMED on the simulator's clock: the reader's own
time (reader.SpotReader measures each reading with ``time.monotonic``) runs on that clock too,
so the pace between patches is what it would be with a 0.9 s reading.

The derived caps hold the whole chart, a new white is due between rows (never inside one) when
the hour of the first runs out, and the session goes on after it: home, calibrate, aim again."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_safety import shaped_sheet
from workflow.i1io.table import job as J
from workflow.i1io.table import reader as rd
from workflow.i1io.table import spot as sp

DENSEST = [49] * 37
PATCHES = sum(DENSEST)
ORIGIN = (1600, 500)          # where the Letter-wide piece lies inside the measuring area
INSIDE = (0, 1500)            # where the person pushes the free arm after the aims


class SimTime:
    """The reader module's clock, on the simulator's."""

    def __init__(self, sim):
        self.sim = sim

    def monotonic(self):
        return self.sim.clock

    def sleep(self, s):
        self.sim.clock += s


#: 4.3.65's densest page on the LARGEST sheet inside the reach, still built today
LARGEST = [33] * 30
LARGEST_ORIGIN = (1700, 450)  # where the 230 x 320 mm sheet lies inside the measuring area


def chart_of(pages: int, rows=DENSEST) -> dict:
    """*pages* densest pages, each patch with its own sample id and location (as a chart's)."""
    sheet = (shaped_sheet(LARGEST, pages=pages) if rows is LARGEST else
             shaped_sheet(rows, pages=pages, along=5.5, across=5.5, w=215.9, h=297.0))
    sid = 1
    for k, pg in enumerate(sheet["pages"]):
        for st in pg["strips"]:
            for q in st["patches"]:
                q["sample_id"] = sid
                q["loc"] = f"P{k + 1}-{q['loc']}"
                sid += 1
    return sheet


def _job(tmp_path, monkeypatch, pages=1, real_table=False, script=None, rows=DENSEST):
    """*real_table* False: the ideal simulated table, so every count below is exact (the less
    ideal table of 4.3.47 fix2 has its own test at the end)."""
    sheet = chart_of(pages, rows)
    origin = LARGEST_ORIGIN if rows is LARGEST else ORIGIN
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet, origin=origin),
                                                ask_after_each_step=False,
                                                real_table=real_table)
    monkeypatch.setattr(rd, "time", SimTime(sim))
    return job, sim, helper, run, H.Person(job, sim, script)


def _align(job, sim, p):
    assert p.drive(job.align()).ok
    sim.hand_to(*INSIDE)              # the person moves the free arm in over the sheet


def _read_chart(job, sim, p, pages):
    log = {"whites": 1, "rows": 0, "calibration_due": 0}
    for pg in range(pages):
        if pg:
            assert p.drive(job.home()).ok and job.next_page().ok
            _align(job, sim, p)
        while job.rows_left():
            r = p.drive(job.read_row())
            if r.reason == "calibration_due":
                # never inside a row: the job says so between rows; the arm goes home, a new
                # white, the sheet aimed at again, and the page goes on
                log["calibration_due"] += 1
                assert r.state.position_now is not None and not r.state.movement_may_be_unfinished
                for s in ("home", "calibrate"):
                    assert p.drive(getattr(job, s)()).ok, s
                log["whites"] += 1
                _align(job, sim, p)
                continue
            assert r.ok and r.detail["status"] == "read", (r.reason, r.detail)
            log["rows"] += 1
    assert p.drive(job.home()).ok
    return log


@pytest.mark.parametrize("rows", (DENSEST, LARGEST), ids=("1813", "990"))
def test_the_densest_page_is_read_whole_within_its_caps_and_timed(tmp_path, monkeypatch, rows):
    patches = sum(rows)
    job, sim, helper, run, p = _job(tmp_path, monkeypatch, rows=rows)
    for s in ("open", "calibrate"):
        assert p.drive(getattr(job, s)()).ok
    _align(job, sim, p)
    t0, lines0 = sim.clock, len(sim.received)
    log = _read_chart(job, sim, p, 1)
    took = sim.clock - t0
    assert log == {"whites": 1, "rows": len(rows), "calibration_due": 0}
    assert helper.reads == patches and sim.violations == []
    d = job._table
    assert d.lines_sent <= job.caps.lines and d.motions_sent <= job.caps.moves
    m = job.save().detail["measurement"]
    assert (m["state"], m["read"], m["expected"]) == ("complete", patches, patches)
    # timed on the simulator: about 1.5 s a patch (move, 0.9 s reading, the pace), so a
    # densest page takes about 45 minutes; and inside one white's hour
    assert patches * 1.2 < took < patches * 2.0, took
    print(f"\ndensest page ({patches} patches) in simulation: {took:.0f} s = {took / 60:.1f} min, "
          f"{len(sim.received) - lines0} lines, {d.motions_sent} movements in the session "
          f"(caps {job.caps.lines} / {job.caps.moves})")


@pytest.mark.parametrize("pages", [3])
def test_a_chart_of_several_densest_pages_needs_new_whites_and_reads_whole(tmp_path,
                                                                         monkeypatch, pages):
    job, sim, helper, run, p = _job(tmp_path, monkeypatch, pages)
    for s in ("open", "calibrate"):
        assert p.drive(getattr(job, s)()).ok
    _align(job, sim, p)
    t0 = sim.clock
    log = _read_chart(job, sim, p, pages)
    took = sim.clock - t0
    assert log["rows"] == len(DENSEST) * pages and helper.reads == PATCHES * pages
    # hours of reading cannot be one white's hour: at least one more, each between rows
    assert log["calibration_due"] >= 1 and log["whites"] == 1 + log["calibration_due"]
    assert helper.calibrations == log["whites"]
    d = job._table
    assert d.lines_sent <= job.caps.lines and d.motions_sent <= job.caps.moves
    m = job.save().detail["measurement"]
    assert (m["state"], m["read"], m["expected"]) == ("complete", PATCHES * pages, PATCHES * pages)
    assert sim.violations == []
    # no row ever began with less than its own time and the margin left on its white
    assert job.calibration_left_s() > 0
    print(f"\n{pages} densest pages in simulation: {took / 60:.1f} min, "
          f"{log['whites']} whites, {d.lines_sent} lines / {d.motions_sent} movements "
          f"(caps {job.caps.lines} / {job.caps.moves})")


def test_a_row_is_never_started_without_its_time_left_on_the_white(tmp_path, monkeypatch):
    job, sim, helper, run, p = _job(tmp_path, monkeypatch)
    for s in ("open", "calibrate"):
        assert p.drive(getattr(job, s)()).ok
    _align(job, sim, p)
    starts = []
    real = job._row_attempt

    def spy(plan, attempt):
        starts.append(job.calibration_left_s())
        return (yield from real(plan, attempt))
    job._row_attempt = spy
    sim.clock = job.calibration["t"] + 3000.0
    _read_chart(job, sim, p, 1)
    assert all(left >= sp.row_seconds(49) + sp.CAL_MARGIN_S for left in starts)


@pytest.mark.parametrize("rows", (DENSEST, LARGEST), ids=("1813", "990"))
def test_the_densest_page_on_a_less_ideal_table_is_read_whole(tmp_path, monkeypatch, rows):
    """4.3.47 fix2: the same page on the simulated table that lands as the volunteer's real one
    did (i1Profiler's 48 arrivals: dx -2..+3, dy -5..+1) and reads with the simulator's +-1 unit
    jitter. An arrival read twice 6 units off happens about once a page; under the old rule it
    ended the measurement ("arm_not_where_expected", measured on this test before the change),
    now the row fails cleanly and is read again ("again"), and the page completes within its
    caps."""
    patches = sum(rows)
    job, sim, helper, run, p = _job(tmp_path, monkeypatch, real_table=True,
                                    script={J.Confirm.ROW_FAILED: "again"}, rows=rows)
    for s in ("open", "calibrate"):
        assert p.drive(getattr(job, s)()).ok
    _align(job, sim, p)
    log = _read_chart(job, sim, p, 1)
    assert log["rows"] == len(rows)
    assert sim.violations == [] and job._table.closed_reason is None
    assert len(sim.arrivals_off) >= patches and min(dy for _dx, dy in sim.arrivals_off) >= -5
    again = [q for q in p.asked if q[1] == J.Confirm.ROW_FAILED]
    # 4.3.48: under 4.3.47's rule this page needed rows read again (measured: 2, each
    # "arrived_beside_the_target"); now every such arrival is moved to once more automatically
    # and no row fails
    assert again == [], again
    assert job.beside_retries, "the less ideal table should land beside at least once a page"
    print(f"\nless ideal table: {len(job.beside_retries)} automatic second move(s), "
          f"{len(again)} row(s) read again, {helper.reads} readings")
    assert helper.reads >= patches
    d = job._table
    assert d.lines_sent <= job.caps.lines and d.motions_sent <= job.caps.moves
    m = job.save().detail["measurement"]
    assert (m["state"], m["read"], m["expected"]) == ("complete", patches, patches)
