"""4.3.54 fix round of the row placement check (independent review, work folder
2026-11-21_place454_review/review_place454.txt).

| the review                                                              | here                     |
|-------------------------------------------------------------------------|--------------------------|
| M1: the dual row's veto had no behavioural test (dual_rows._placement    | test_the_dual_cut_*      |
|     ignored: every focused test green)                                   |                          |
| M1: the job keeps no M0-only lamp pass after a placement refusal         | test_a_dual_row_refused_* |
| S2: six guards no test protected (each now refuses a row on its own:    | test_guard_*             |
|     the value condition, the timing bound, uniqueness, the run           |                          |
|     tolerance, 3 clean readings, every centre on a stable reading)       |                          |

Every test here was RED with its guard planted out (work folder fix_round/plants_out.txt).
Rows: tests/i1io_table/placement_synth.py (shaped like the recorded ones; the recordings stay
private). The guard tests give the check windows on each patch's TRUE clean middle, so that the
window rule cannot be what refuses; three of them (uniqueness, the timing bound, every centre on
a stable reading) make the fit's own result say what a real row would (a rival place, the best
place on the bound, a patch centre off the stable readings): those rules are backstops of each
other on real rows (the review's guards.py: removing any one alone accepted no wrong patch), so
a row refused by ONE of them alone is not something the generator produces on its own.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import placement_synth as S
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import job as J
from workflow.i1io.table import placement as pl
from workflow.i1io.table import spot as sp
from workflow.i1io.table import strip as stp
from tests.i1io_table.test_window import settings  # noqa: E402,F401 (fixture)


def _mid3(row, i):
    c = row.clean[i]
    m = len(c) // 2
    return (int(c[m - 1]), int(c[m + 2]))


def _true_windows(row, p):
    return [_mid3(row, i) for i in range(len(p.patches))]


# ---- M1: the dual row ------------------------------------------------------------------------------

def test_the_dual_cut_refuses_a_lamp_pass_whose_window_takes_in_an_edge_reading(monkeypatch):
    """The lamp pass of a dual row at 132 mm/s, the sheet 2 mm off: the dual row's own checks
    (1.5 mm edge, one colour) accept it with a patch more than 3 dE00 off; the check refuses
    the dual cut AND the M0-only cut of the same pass, with the strip row's reason."""
    lamp = S.plan(10.0, 132)
    uv = sp.uv_pass_of(lamp)
    urows = [[0.01] * 36] * uv.N
    row = S.Row(lamp, dx_mm=2.0, seed=0)
    rows = row.readings.tolist()
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    off = dl.cut_dual(lamp, uv, rows, urows)
    assert off.ok
    got = np.array(off.lamp)
    assert float(np.max(S.de00_spectra(got, row.truth))) > 3.0
    assert dl.cut_lamp_only(lamp, rows).ok
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", True)
    on = dl.cut_dual(lamp, uv, rows, urows)
    assert (on.ok, on.reason) == (False, stp.PLACEMENT_REASON)
    assert on.info["placement"]["confirmed"] is False and on.info["loc"]
    only = dl.cut_lamp_only(lamp, rows)
    assert (only.ok, only.reason) == (False, stp.PLACEMENT_REASON)
    # and a dual row lying where it should is cut as before
    good = S.Row(lamp, seed=0).readings.tolist()
    a = dl.cut_dual(lamp, uv, good, urows)
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    b = dl.cut_dual(lamp, uv, good, urows)
    assert a.ok and b.ok and a.lamp == b.lamp and a.uv == b.uv


def test_a_dual_row_refused_for_placement_keeps_no_m0_only_lamp_pass(tmp_path, monkeypatch):
    """The job (simulated table, dual scan on): row 1's sheet 2.5 mm off, read through the
    4.5 mm opening. The row fails with the placement reason, and the job does NOT try to keep
    its lamp pass as M0 only (job.py's exclusion beside lamp_pass_timing_off): the question
    says nothing of M0, and no M0-only row file exists."""
    from tests.i1io_table.test_4350_dual_m1_m2_per_row import _job, _ready
    kept = []
    real = J.TableJob._keep_lamp_pass

    def spy(self, *a, **k):
        kept.append(a[-1])
        return real(self, *a, **k)
    monkeypatch.setattr(J.TableJob, "_keep_lamp_pass", spy)
    job, sim, helper, run, p, _rep = _job(
        tmp_path, faults={"scan": {"sheet_offset_mm": 2.5, "aperture_mm": 4.5}, "scan_at": 2},
        script={J.Confirm.ROW_FAILED_STRIP: "skip"})
    asked = []
    p.on_ask = lambda person, res: (asked.append(dict(res.detail))
                                    if res.confirm == J.Confirm.ROW_FAILED_STRIP else None)
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped"
    assert [a["why"] for a in asked] == [stp.PLACEMENT_REASON]
    assert asked[0]["m0_kept"] is False and asked[0]["read"] == 0
    assert kept == []
    assert not list(job.diag.folder.rglob("*.strip.ti3"))
    job.close()


# ---- S2: each guard refuses a row on its own --------------------------------------------------------

def test_guard_the_value_condition():
    """A dark patch whose readings drift by up to 1.1 dE00 across it (within the dark run limit of
    1.2): its window lies inside its stable run, but on one end of it; the window's value is
    0.64 dE00 from the run's own. Refused by the value condition alone."""
    p = S.plan(10.0, 61)
    cols = S.PALETTE[np.arange(24) % len(S.PALETTE)].copy()
    cols[5] = np.full(36, 0.03)
    row = S.Row(p, seed=3, colours=cols, print_sd=0.0)
    c = row.clean[5]
    row.readings[c] *= (1 + 0.1 * np.linspace(-1, 1, len(c)))[:, None]
    w = _true_windows(row, p)
    w[5] = (int(c[1]), int(c[4]))
    r = pl.check_row(p, row.readings.tolist(), w)
    assert (r["reason"], r["patch"]) == ("value_disagrees_with_the_stable_run", "A6"), r
    assert r["value_de00"] > pl.VALUE_AGREE_DE00
    w[5] = _mid3(row, 5)                             # its middle: confirmed
    assert pl.check_row(p, row.readings.tolist(), w)["confirmed"]


def test_guard_the_run_tolerance():
    """One patch printed 3 mm further along than the others (3 mm spacers, so it overlaps
    nothing): the row fits the other 23; that patch's run lies 2.4 mm from its place. Its
    window (on its true middle) lies inside its run, with 10 clean readings: refused by the
    2 mm run tolerance alone."""
    p = S.plan(10.0, 61, spacer_mm=4.0)
    row = S.Row(p, seed=5, patch_shift={7: 3.0}, print_sd=0.0, spacer_mm=4.0)
    r = pl.check_row(p, row.readings.tolist(), _true_windows(row, p))
    assert (r["reason"], r["patch"]) == ("patch_run_away_from_its_place", "A8"), r
    assert r["off_mm"] > pl.PATCH_TOL_MM
    rec = [x for x in r["per_patch"] if x["loc"] == "A8"][0]
    assert rec["clean"] >= pl.MIN_READINGS and not rec["merged"]


def test_guard_three_clean_readings():
    """A plan whose patch A7 is only 5 mm long (half 2.5 mm) while the print is 10 mm: its run
    is long and its window inside it, but the readings within +-(half - 2.25 mm) of its centre
    are fewer than 3: refused by the clean-readings rule alone."""
    p = S.plan(10.0, 88)
    p.patches[6].half_mm = 2.5
    row = S.Row(p, seed=6, print_sd=0.0)
    r = pl.check_row(p, row.readings.tolist(), _true_windows(row, p))
    assert (r["reason"], r["patch"]) == ("patch_too_few_clean_readings", "A7"), r


def _good():
    p = S.plan(10.0, 88)
    row = S.Row(p, seed=6, print_sd=0.0)
    w = _true_windows(row, p)
    assert pl.check_row(p, row.readings.tolist(), w)["confirmed"]
    return p, row, w


def _fit_says(monkeypatch, change):
    real = pl._fit

    def fit(plan, n, depth, first_s, motion_s):
        D, E, Hh, deep, b = real(plan, n, depth, first_s, motion_s)
        return change(plan, D.copy(), E.copy(), Hh.copy(), deep.copy(), b)
    monkeypatch.setattr(pl, "_fit", fit)


def test_guard_every_centre_on_a_stable_reading(monkeypatch):
    """The fit finds one patch centre off the stable readings at its best place: not confirmed
    ("the readings do not show every patch where the timing puts it")."""
    p, row, w = _good()

    def change(plan, D, E, Hh, deep, b):
        Hh[0] = len(plan.patches) - 1
        return D, E, Hh, deep, b
    _fit_says(monkeypatch, change)
    r = pl.check_row(p, row.readings.tolist(), w)
    assert r["reason"] == "edges_do_not_place_every_patch" and r["off_patches"] == 1
    assert "1 patch" in pl.summary(r)


def test_guard_uniqueness(monkeypatch):
    """A place half a pitch away fits as well as the best one: not confirmed."""
    p, row, w = _good()

    def change(plan, D, E, Hh, deep, b):
        k = 1
        D[k] = D[0] + 0.6 * 11.0 / plan.speed            # 6.6 mm away (half a pitch: 5.5)
        Hh[k] = Hh[0]
        return D, E, Hh, deep, b
    _fit_says(monkeypatch, change)
    r = pl.check_row(p, row.readings.tolist(), w)
    assert r["reason"] == "edges_not_unique", r


@pytest.mark.parametrize("which", ["dt", "scale"])
def test_guard_the_timing_bound(monkeypatch, which):
    """The best place lies on the timing's own bound (the readings and the timing disagree):
    not confirmed, with the largest shift a patch would make, in mm."""
    p, row, w = _good()

    def change(plan, D, E, Hh, deep, b):
        if which == "dt":
            D[0] = b
        else:
            E[0] = pl.FIT_SCALE
        Hh[1:] = 0                     # no rival place: uniqueness is not what refuses it
        return D, E, Hh, deep, b
    _fit_says(monkeypatch, change)
    r = pl.check_row(p, row.readings.tolist(), w)
    assert r["reason"] == "edges_disagree_with_timing" and r["off_mm"] > 0, r


# ---- the relaxed window rule (adopted in the fix round, the review's S1) ---------------------------

def test_a_window_may_reach_two_readings_beyond_its_run_when_its_value_agrees():
    """placement.WINDOW_OUTSIDE_MAX_READINGS = 2 with WINDOW_OUTSIDE_VALUE_DE00 = 0.3: one or two
    readings beyond the stable run with the window's value within 0.3 dE00 of the run's are
    tolerated (and said in the record); three, or a value further off, are not."""
    assert (pl.WINDOW_OUTSIDE_MAX_READINGS, pl.WINDOW_OUTSIDE_VALUE_DE00) == (2, 0.3)
    p, row, w = _good()
    rec = pl.check_row(p, row.readings.tolist(), w)["per_patch"][5]
    ra, rb1 = rec["run"]
    for extra, ok in ((1, True), (2, True), (3, False)):
        ww = list(w)
        ww[5] = (ra - extra, rb1)
        r = pl.check_row(p, row.readings.tolist(), ww)
        if ok and r["confirmed"]:
            got = r["per_patch"][5]
            assert got["outside_readings"] == extra and got["outside_tolerated"]
            assert got["value_de00"] <= pl.WINDOW_OUTSIDE_VALUE_DE00
        else:
            assert not ok and r["reason"] == "window_outside_the_stable_run", (extra, r)
    # two readings outside that carry the edge (a short window): its value is off, refused
    ww = list(w)
    ww[5] = (ra - 2, ra + 1)
    r = pl.check_row(p, row.readings.tolist(), ww)
    assert r["reason"] == "window_outside_the_stable_run" and r["patch"] == "A6", r


# ---- no edges in the readings (the review's S3) -------------------------------------------------------

def _windows(p, n, edge):
    from workflow.i1io.table import scan as sc
    return sc.windows(p, sc.MOTION_START_AFTER_LAMP_S, n, edge_mm=edge)


@pytest.mark.parametrize("what", ["constant", "bare paper"])
def test_a_stream_without_patch_edges_is_not_confirmed(what):
    """A constant stream (an arm that did not move, a stuck reading) and bare paper with noise:
    the readings say nothing about where the patches are, so the check cannot confirm the row
    (it was "confirmed" before the fix round, review S3)."""
    p = S.plan(10.0, 88)
    if what == "constant":
        rows = [list(S.PALETTE[7])] * p.N
    else:
        paper = np.array([S.PAPER] * 24)
        rows = S.Row(p, seed=2, colours=paper, spacer=S.PAPER).readings.tolist()
    r = pl.check_row(p, rows, _windows(p, p.N, 1.58))
    assert (r["confirmed"], r["reason"]) == (False, "no_patch_edges"), r
    assert "no patch edges" in pl.summary(r)


def test_a_row_of_identical_patches_is_used_by_timing_alone_and_says_so():
    """THE DECISION: a row the CHART says is made of identical patches (and printed without
    spacers) has no edges either; refusing it would make it unreadable in rows for ever, so it
    is used as 4.3.53 used it, by timing alone, and the record and the logs say "cannot
    confirm". Any row whose chart patches differ stays refused (above)."""
    p = S.plan(10.0, 88, spacer_mm=0.0)
    same = np.array([S.PALETTE[3]] * 24)
    rows = S.Row(p, seed=2, colours=same, spacer_mm=0.0).readings.tolist()
    w = _windows(p, p.N, 1.58)
    assert pl.check_row(p, rows, w)["reason"] == "no_patch_edges"
    r = pl.check_row(p, rows, w, uniform_reference=True)
    assert r["confirmed"] is True and r["timing_only"] is True
    assert r["reason"] == "uniform_row_timing_only"
    assert pl.summary(r).startswith("row placement check: cannot confirm: a row of identical "
                                    "patches cannot be placed from its readings")


def test_the_job_knows_a_uniform_row_from_the_chart(tmp_path):
    from workflow.i1io.table import measurement as ms
    ti2 = tmp_path / "c.ti2"
    ti2.write_text('CTI2\n\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R '
                   'RGB_G RGB_B\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 3\nBEGIN_DATA\n'
                   '1 "A1" 50 50 50\n2 "A2" 50 50 50\n3 "A3" 10 50 50\nEND_DATA\n',
                   encoding="ascii")
    dev = ms.device_values_by_loc(ti2)
    assert dev == {"A1": ("50", "50", "50"), "A2": ("50", "50", "50"),
                   "A3": ("10", "50", "50")}
    assert ms.device_values_by_loc(tmp_path / "missing.ti2") == {}

    class Q:
        def __init__(self, loc):
            self.loc = loc

    class Plan:
        def __init__(self, *locs):
            self.patches = [Q(x) for x in locs]
    job = type("Job", (), {"_chart_ti2": ti2, "_uniform_row": J.TableJob._uniform_row})()
    assert job._uniform_row(Plan("A1", "A2")) is True
    assert job._uniform_row(Plan("A1", "A3")) is False
    assert job._uniform_row(Plan("A1", "A9")) is False        # unknown: not uniform


# ---- the rest of a page patch by patch (the review's S4) ----------------------------------------------

def test_after_the_second_refused_row_the_rest_of_the_page_is_offered_once(tmp_path):
    """A page whose sheet lies 2 mm off (every row refused by the check): the first refused row
    is asked as before; the SECOND offers, once, to read the rest of the page patch by patch;
    chosen, that row and every row after it on the page are read patch by patch (GO first),
    nobody is asked again, and every finished row is on disk."""
    from tests.i1io_table import reader_sim as RS
    from tests.i1io_table.test_job_reading import ready_to_read, small_sheet
    sheet = small_sheet([4, 4, 4, 4])
    job, sim, helper, run = RS.make_reading_job(
        tmp_path, sheet=sheet, aims=H.demo_aims(sheet), ask_after_each_step=False,
        faults={"scan": {"sheet_offset_mm": 2.0, "aperture_mm": 4.5}})
    assert job.set_options(["-v", "-c", "1", "chart"]).ok
    p = H.Person(job, sim)
    asked, answers = [], iter(["skip", "rest patch by patch"])

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED_STRIP:
            asked.append(dict(res.detail))
            person.script[J.Confirm.ROW_FAILED_STRIP] = next(answers)
        return None
    p.on_ask = on_ask
    ready_to_read(job, p)
    res = []
    while job.rows_left():
        res.append(p.drive(job.read_row()))
    assert [(a["row"], a["why"], a["offer_rest"]) for a in asked] == [
        (1, stp.PLACEMENT_REASON, False), (2, stp.PLACEMENT_REASON, True)]
    assert [r.detail["status"] for r in res] == ["skipped", "read", "read", "read"]
    assert [r.detail["row_kind"] for r in res[1:]] == ["spot", "spot", "spot"]
    assert all(r.detail["read_patch_by_patch_because"] == "chosen_by_you" for r in res[1:])
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == 2   # rows 1 and 2 only
    assert job.rest_by_patch == {0} and job.rest_offered == {0}
    recs = [json.loads(x.read_text(encoding="utf-8"))
            for x in sorted(job.diag.folder.rglob("*.row.json"))]
    assert sorted((r["row"], r["status"]) for r in recs if r["status"] == "read") == \
        [(2, "read"), (3, "read"), (4, "read")]
    log = "\n".join(x.read_text(encoding="utf-8") for x in job.diag.folder.rglob("*.log"))
    assert "the rest of the page is offered patch by patch" in log
    assert "the person chose to read the rest of this page patch by patch" in log
    job.close()


def test_the_panel_shows_the_rest_of_the_page_only_when_offered(qtbot, monkeypatch, tmp_path,
                                                                settings):  # noqa: F811
    from tests.i1io_table.test_window import open_window
    real = stp.cut_row
    monkeypatch.setattr(stp, "cut_row", lambda plan, outdir, fired, **kw: stp.Cut(
        False, stp.PLACEMENT_REASON, info=real(plan, outdir, fired, **kw).info))
    win, sim, run, person, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, args=["-v", "-c", "1", "chart"])
    person.drive_until("row_failed_strip")
    assert "Rest patch by patch" not in person.labels()
    assert "the readings did not confirm where the patches are" in win._text.text()
    person.press("Skip it")
    person.drive_until("row_failed_strip")
    labels = person.labels()
    assert "Rest patch by patch" in labels and "Read it patch by patch" not in labels, labels
    assert len(labels) == 4 + labels.count("End measurement") + labels.count("Report a problem")
    assert "This is the second row of this page where that happened" in win._text.text()
    person.press("Rest patch by patch")
    assert person.page() == "go"                      # hands off first, nothing moved
