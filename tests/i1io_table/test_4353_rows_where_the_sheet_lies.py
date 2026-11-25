"""4.3.53: rows are read as rows wherever the aimed chart puts them (FOR THE SAFETY REVIEW).

The project owner, 2026-11-20 (binding):

* "so you tell me he can't do rows / strips now - only patch by patch? ... there is no physical
  reason he should not be able to do it but you block him and make it take another turn of
  fixes."
* "for patch by patch you allowed this position because we considered the position where he
  aimed the device as safe. so why not rows? and probably even a little wider than where he
  aimed is safe as well. so if there are no crosshairs for aiming but patches only will be safe
  as well. for both patch by patch and rows"
* "and really make sure that enough area outside the aiming points becomes usable without an
  artificial limitation. the device needs enough space on both ends of the patches. before and
  after them without getting an error"
* "i hope you made or will make everything in a way that chromiq learns which movements are
  save at least so that after the first carefull attempt everything runs as fast as it is
  supposed to. like in i1profiler"

What 4.3.52 did on the table owner's sheet (his first page, 19 Nov 2026): every strip row was
read patch by patch, said "too long", because its run-out needed X -1443 and a fixed right edge
(X -1384, the recorded extent of an old chart) refused it. What these tests pin:

* his sheet where he laid it, his three aims, his free arm at (-1546, 3102): read IN ROWS, every
  row, no fallback, no refusal, and the wire of each row is the recorded row form (c4, m0 to the
  start, d1 016D, p0, m2 to the end, a3, c3) with no other move between;
* the run-up and run-out of every row are the chart's own (15 mm beyond the end patches'
  centres on ChromIQ's chart), at least i1Profiler's recorded 10.1-10.6 mm (18 Nov 2026, its
  dual rows on the owner's table; 0.2-0.5 mm on its single-scan rows of 12, 14 and 17 Nov), in
  both directions, never shortened;
* first-time care: a row whose run-up or run-out lies beyond the ground this table is known to
  reach is driven to by its two row ends once; the arrivals are stored; the second sitting on
  the same table sends exactly the recorded row form, nothing more;
* a matrix of sheet places (the corner-patch chart, crosses, his position, near the right, the
  left, the front, the back) in rows and patch by patch: everything read, nothing refused;
* the fallback, when one remains, says the true reason.
"""
from __future__ import annotations

import copy

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from workflow import measurement_messages as M
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp

STRIP = ["-v", "-c", "1", "chart"]
SPOT = ["-v", "-c", "1", "-p", "chart"]
GO_ON = {J.Confirm.FRONT_CHOICE: "go on"}
#: the owner's three aims of 19 Nov 2026 (p1, by the instrument's button) and where his free arm
#: was read after them, (-1546, 3102): the simulated sight sits that far from the opening
HIS_AIMS = [(1403, 1488), (1409, 3368), (-1352, 3370)]
HIS_FREE_ARM = (-1546, 3102)
HIS_SIGHT = (HIS_FREE_ARM[0] - HIS_AIMS[2][0], HIS_FREE_ARM[1] - HIS_AIMS[2][1])
#: i1Profiler's own run-up / run-out beyond the aimed end points on the owner's table (18 Nov,
#: decode_full_124449: aims X 1158 / -1331, row 1 m0 to -1432, m2 to 1264), in table units
VENDOR_RUN_UNITS = 106
#: the recorded row form, in order (scan.run_row; R14, A, B)
ROW_FORM = ("c4", "p0", "m0", "d1", "p0", "m2", "a3", "c3")


def _job(tmp_path, aims, args=STRIP, sheet=None, store=None, script=None, guided=False,
         **simkw):
    sheet = sheet or H.demo_sheet()
    simkw.setdefault("front_end", 3700)
    job, sim, helper, run = RS.make_reading_job(
        tmp_path, sheet=sheet, aims=aims, ask_after_each_step=guided,
        reach_store=store if store is not None else rc.MemoryReachStore(), **simkw)
    # "Guided, step by step measurement": on (every question and the report after each step)
    # or off (the job's own answers and the countdown), as the window passes it
    job.guided = bool(guided)
    rep = job.set_options(args)
    assert rep.ok, rep.detail
    return job, sim, helper, H.Person(job, sim, dict(GO_ON, **(script or {})))


def _spy_care(job):
    calls = []
    orig = job._row_ends_beyond

    def spy(*pts):
        out = orig(*pts)
        calls.append(out)
        return out
    job._row_ends_beyond = spy
    return calls


def _read_all(job, p):
    out = []
    for step in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, step)())
        out.append((step, r))
        assert r.ok, (step, r.reason, r.detail)
    if job.front_need and job.front_reached() < job.front_need:
        r = p.drive(job.creep())
        out.append(("creep", r))
        assert r.ok, ("creep", r.reason, r.detail)
    rows = []
    while job.rows_left():
        r = p.drive(job.read_row())
        rows.append(r)
        assert r.ok, (r.reason, r.detail)
    return out, rows


def _cid(line: str) -> str:
    return line[1:3]


def _row_slices(received):
    """The table lines of each strip row: from its c4 to its c3."""
    out, cur = [], None
    for ln in received:
        c = _cid(ln)
        if c == "c4":
            cur = []
        if cur is not None:
            cur.append(ln)
            if c == "c3":
                out.append(cur)
                cur = None
    return out


def _plan_ends(sheet, al, k):
    st = sheet["pages"][0]["strips"][k]
    return [al.to_table(sc.sheet_table_mm(sheet, (st["x_mm"], r))) for r in st["run_mm"]]


# ---- the tester's sheet, where he laid it ------------------------------------------------------

def test_the_testers_sheet_where_he_laid_it_is_read_in_rows(tmp_path):
    job, sim, helper, p = _job(tmp_path, HIS_AIMS, sight_offset=HIS_SIGHT)
    _steps, rows = _read_all(job, p)
    assert len(rows) == 22
    assert all(r.detail["row_kind"] == "strip" for r in rows), [r.detail for r in rows]
    assert all("read_patch_by_patch_because" not in r.detail for r in rows)
    assert job.strip_fallbacks == {} or not any(job.strip_fallbacks.values())
    assert sim.violations == [] and sim.end_targets == []
    assert sum(1 for ln in sim.received if _cid(ln) == "m2") == 22
    # his free arm was read where it was, and widened what this table is known to reach
    assert job.reach.right_end_x <= HIS_FREE_ARM[0] + 2
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete"


def test_on_his_sheet_every_row_is_the_recorded_row_form_with_nothing_between(tmp_path):
    job, sim, helper, p = _job(tmp_path, HIS_AIMS, sight_offset=HIS_SIGHT)
    care = _spy_care(job)
    _read_all(job, p)
    assert care and all(c == [] for c in care), care          # no careful row-end moves
    slices = _row_slices(sim.received)
    assert len(slices) == 22
    for sl in slices:
        assert tuple(_cid(ln) for ln in sl) == ROW_FORM, sl


def test_his_rows_start_and_end_where_the_chart_says_beyond_the_vendors_run(tmp_path):
    job, sim, helper, p = _job(tmp_path, HIS_AIMS, sight_offset=HIS_SIGHT)
    _read_all(job, p)
    sheet, al = H.demo_sheet(), job.alignment
    for k, sl in enumerate(_row_slices(sim.received)):
        m0 = geo.decode_xyv(sl[2].encode())
        m2 = geo.decode_xyv(sl[5].encode())
        ends = _plan_ends(sheet, al, k)
        assert sorted([(m0[1], m0[2]), (m2[1], m2[2])]) == sorted(ends), k
        st = sheet["pages"][0]["strips"][k]
        pts = [al.to_table(sc.sheet_table_mm(sheet, q["centre_mm"])) for q in st["patches"]]
        right, left = min(pts, key=lambda q: q[0]), max(pts, key=lambda q: q[0])
        run_right = min(ends, key=lambda q: q[0])
        run_left = max(ends, key=lambda q: q[0])
        # before the first patch and after the last, in both directions of the serpentine
        assert right[0] - run_right[0] >= VENDOR_RUN_UNITS, (k, right, run_right)
        assert run_left[0] - left[0] >= VENDOR_RUN_UNITS, (k, left, run_left)
    # the run-out on his sheet reaches beyond the old fixed right edge, which refused it
    assert min(geo.decode_xyv(sl[2].encode())[1] for sl in _row_slices(sim.received)) < -1384


def test_unguided_his_sheet_has_the_same_wire_as_guided(tmp_path):
    job, sim, helper, p = _job(tmp_path / "u", HIS_AIMS, sight_offset=HIS_SIGHT)
    _read_all(job, p)
    # the sheet laid and the aims (hands were on the table): two, as before; none elsewhere
    assert [c["seconds"] for c in job.countdowns if c["seconds"] > 0] == \
        [J.UNGUIDED_COUNTDOWN_S] * 2
    job2, sim2, helper2, p2 = _job(tmp_path / "g", HIS_AIMS, sight_offset=HIS_SIGHT,
                                   guided=True)
    _read_all(job2, p2)
    assert _row_slices(sim2.received) == _row_slices(sim.received)


# ---- first-time care, once, then remembered per table --------------------------------------

#: a sight 5 mm from the opening: after mark 3 the free arm stands at X -1402, so the run-out
#: of his rows (X -1443) lies beyond what this table is known to reach (the vendor's -1439)
CLOSE_SIGHT = (-50, -318)


def test_new_ground_gets_the_two_row_end_moves_once_and_the_next_sitting_none(tmp_path):
    store = rc.MemoryReachStore()
    job, sim, helper, p = _job(tmp_path / "1", HIS_AIMS, store=store, sight_offset=CLOSE_SIGHT)
    care = _spy_care(job)
    _read_all(job, p)
    careful = [c for c in care if c]
    assert careful and careful[0] == ["right side"]
    # once: the first row that reached the new ground; the arrivals are learned at once
    assert len(careful) == 1, care
    assert job.reach.right_end_x <= -1443 and job.reach.right_how == "motor"
    assert sim.violations == [] and sim.end_targets == []
    first_wire = _row_slices(sim.received)
    job.close()
    # the second sitting on the same table: no careful steps, the recorded row form only
    job2, sim2, helper2, p2 = _job(tmp_path / "2", HIS_AIMS, store=store,
                                   sight_offset=CLOSE_SIGHT,
                                   motors_have_been_to=job.reach.motor_front_y)
    care2 = _spy_care(job2)
    _read_all(job2, p2)
    assert care2 and all(c == [] for c in care2), care2
    slices = _row_slices(sim2.received)
    assert all(tuple(_cid(ln) for ln in sl) == ROW_FORM for sl in slices)
    assert [sl[2:] for sl in slices] == [sl[2:] for sl in first_wire]
    # no creep either: the front was remembered
    assert J.Confirm.FRONT_CHOICE not in {c for _s, c, _d, _n, _m in p2.asked}
    # another table (another serial) gets the careful moves once again
    job3, sim3, helper3, p3 = _job(tmp_path / "3", HIS_AIMS, store=store,
                                   sight_offset=CLOSE_SIGHT, serial="SIM0000OTHR")
    care3 = _spy_care(job3)
    _read_all(job3, p3)
    assert [c for c in care3 if c] == [["right side"]]


def test_the_careful_moves_are_ordinary_arrival_checked_moves_to_the_row_ends(tmp_path):
    job, sim, helper, p = _job(tmp_path, HIS_AIMS, sight_offset=CLOSE_SIGHT)
    care = _spy_care(job)
    n0 = None
    for step in ("open", "calibrate", "align", "creep"):
        assert p.drive(getattr(job, step)()).ok, step
    while job.rows_left():
        before = len(sim.received)
        r = p.drive(job.read_row())
        assert r.ok
        if care[-1]:
            n0 = (before, len(sim.received))
            break
    assert n0 is not None
    lines = sim.received[n0[0]:n0[1]]
    plan = sp.plan_row(H.demo_sheet(), 0, r.detail["row"] - 1, job.alignment,
                       job._table.front_y, cap_y=job._cap(), kind="strip")
    first_c4 = [i for i, ln in enumerate(lines) if _cid(ln) == "c4"][0]
    moves = [geo.decode_xyv(ln.encode())[1:3] for ln in lines[:first_c4] if _cid(ln) == "m0"]
    assert moves[-2:] == [plan.scan.start, plan.scan.end]
    # each followed by its arrival reading
    pre = [_cid(ln) for ln in lines[:first_c4]]
    for i, c in enumerate(pre):
        if c == "m0":
            assert pre[i + 1] == "p0"


# ---- the matrix: where the sheet lies, how it is aimed, rows and patch by patch -------------

def _patch_chart():
    """ChromIQ's A4 chart aimed at its corner PATCHES (no crosses): every row's run-up and
    run-out, and half of every edge patch, lie outside the three aimed points."""
    sheet = copy.deepcopy(H.demo_sheet())
    strips = sheet["pages"][0]["strips"]
    first, last = strips[0], strips[-1]
    tl = first["patches"][0]
    bl = last["patches"][0]
    br = last["patches"][-1]
    sheet["pages"][0]["aim_points"] = [
        {"number": 1, "corner_on_table": "top-left", "target": "patch", "patch": tl["loc"],
         "page_mm": list(tl["centre_mm"])},
        {"number": 2, "corner_on_table": "bottom-left", "target": "patch", "patch": bl["loc"],
         "page_mm": list(bl["centre_mm"])},
        {"number": 3, "corner_on_table": "bottom-right", "target": "patch", "patch": br["loc"],
         "page_mm": list(br["centre_mm"])}]
    return sheet


def _aims_at(sheet, mark3):
    """The three p1 readings of *sheet* laid square with its mark 3 at *mark3*."""
    base = H.demo_aims(sheet, origin=(0, 0))
    dx, dy = mark3[0] - base[2][0], mark3[1] - base[2][1]
    return [(x + dx, y + dy) for x, y in base]


#: (name, sheet maker, mark 3 at): his position, near the right, the left, the front and the
#: back of the bed (the back strip beside the white tile's holder excepted)
PLACES = [
    ("crosses, his position", H.demo_sheet, HIS_AIMS[2]),
    ("corner patches, his position", _patch_chart, (-1288, 3305)),
    ("crosses, near the right", H.demo_sheet, (-1700, 2900)),
    ("corner patches, near the right", _patch_chart, (-1650, 2900)),
    ("crosses, near the left", H.demo_sheet, (-300, 2900)),
    ("crosses, near the front", H.demo_sheet, (-1352, 3600)),
    ("corner patches, near the back", _patch_chart, (-1300, 2470)),
]


@pytest.mark.parametrize("kind", ["strip", "spot"])
@pytest.mark.parametrize("name, make, mark3", PLACES, ids=[p[0] for p in PLACES])
def test_the_matrix_reads_every_row_where_the_chart_lies(tmp_path, name, make, mark3, kind):
    sheet = make()
    aims = _aims_at(sheet, mark3)
    job, sim, helper, p = _job(tmp_path, aims, args=STRIP if kind == "strip" else SPOT,
                               sheet=sheet)
    steps, rows = _read_all(job, p)
    assert all(r.ok for _s, r in steps)
    assert len(rows) == len(sheet["pages"][0]["strips"])
    assert all(r.detail["row_kind"] == kind for r in rows), name
    assert all("read_patch_by_patch_because" not in r.detail for r in rows)
    assert not any(job.strip_fallbacks.values())
    assert sim.violations == [] and sim.end_targets == []
    al = job.alignment
    if kind == "strip":
        for k, sl in enumerate(_row_slices(sim.received)):
            m0 = geo.decode_xyv(sl[2].encode())
            m2 = geo.decode_xyv(sl[5].encode())
            assert sorted([(m0[1], m0[2]), (m2[1], m2[2])]) == sorted(_plan_ends(sheet, al, k))
    else:
        got = {geo.decode_xyv(ln.encode())[1:3] for ln in sim.received if _cid(ln) == "m0"}
        for st in sheet["pages"][0]["strips"]:
            for q in st["patches"]:
                assert al.to_table(sc.sheet_table_mm(sheet, q["centre_mm"])) in got
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete"


def test_on_the_corner_patch_chart_the_runs_lie_outside_the_aimed_points():
    """What the matrix's corner-patch rows prove: their run-up and run-out lie well outside
    the rectangle of the three aimed points (4.3.52 refused them: on_sheet, 10 mm)."""
    sheet = _patch_chart()
    aims = _aims_at(sheet, (-1288, 3305))
    mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    al = geo.fit_alignment(mm, aims)
    st = sheet["pages"][0]["strips"][0]
    for r in st["run_mm"]:
        u = sc.sheet_table_mm(sheet, (st["x_mm"], r))
        assert not al.on_sheet(u)                       # outside the aims by more than 10 mm
        al.target(u, "a run end")                        # and still a target


# ---- what still makes a row patch by patch, said truly ------------------------------------------

def _spy_events(job):
    events = []
    orig = job._progress

    def spy(**ev):
        events.append(ev)
        return orig(**ev)
    job._progress = spy
    return events


def test_a_sheet_laid_beyond_the_former_right_backstop_is_read_in_rows(tmp_path):
    """4.3.53 fix round (rows review SHOULD-4): the right backstop X -1800 is gone. A sheet laid
    so far right that its run-out passes it is read IN ROWS (until the fix round: patch by
    patch, "outside the part of the table ChromIQ may send it to now"), with the careful
    row-end moves once on that new ground."""
    aims = _aims_at(H.demo_sheet(), (-1790, 2900))
    job, sim, helper, p = _job(tmp_path, aims)
    for step in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, step)()).ok, step
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", r.detail
    assert "read_patch_by_patch_because" not in r.detail
    xs = [geo.decode_xyv(ln.encode())[1] for ln in sim.received
          if _cid(ln) in ("m0", "m2") and len(ln.rstrip()) == 17]
    assert min(xs) < -1800
    assert sim.violations == []


def test_a_run_beyond_the_left_side_is_read_patch_by_patch_and_says_why(tmp_path):
    """The left side (X 2507, where the table's own m1 stops the arm: physical) is the one side
    left: a sheet laid so far left that its run-up would pass it is read patch by patch, and the
    words say so (until 4.3.52 they said "too long")."""
    sheet = _patch_chart()                      # aimed on its corner patches: the run-up of
    aims = _aims_at(sheet, (-30, 2900))         # row 1 lies 15 mm beyond the aimed patch
    assert max(a[0] for a in aims) <= geo.TARGET_X_LEFT < max(a[0] for a in aims) + 150
    job, sim, helper, p = _job(tmp_path, aims, sheet=sheet)
    events = _spy_events(job)
    for step in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, step)()).ok, step
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot"
    assert r.detail["read_patch_by_patch_because"] == "strip_row_outside_area"
    fb = [e for e in events if e.get("event") == "strip_fallback"]
    assert fb and fb[0]["why"] == "strip_row_outside_area"
    text = M.strip_fallback_text(fb[0]["why"], fb[0]["row"])
    assert "outside the part of the table ChromIQ may send it to now" in text
    assert "too long" not in text
    assert sim.violations == []
    assert all(geo.decode_xyv(ln.encode())[1] <= geo.TARGET_X_LEFT
               for ln in sim.received if _cid(ln) in ("m0", "m2") and len(ln.rstrip()) == 17)


@pytest.mark.parametrize("why, words", [
    ("strip_row_too_long", "too long"),
    ("strip_row_patches_too_short", "too short"),
    ("strip_row_outside_area", "outside the part of the table"),
    ("strip_row_too_short", "not one straight run of at least 10 mm"),
    ("strip_row_not_on_a_line", "not one straight run of at least 10 mm"),
    ("dual_row_patches_too_short", "too short to be read twice")])
def test_every_fallback_reason_has_its_own_true_words(why, words):
    assert words in M.strip_fallback_text(why, 3)
    assert why in sp.STRIP_FALLBACK_REASONS


def test_the_refusal_ids_name_the_true_reason():
    assert sp.strip_refusal_id(sc.PlanRefused("a row shorter than 10 mm"))[0] == \
        "strip_row_too_short"
    assert sp.strip_refusal_id(sc.PlanRefused("patch A3 does not lie on the row"))[0] == \
        "strip_row_not_on_a_line"
    assert sp.strip_refusal_id(geo.AreaRefused("x: table position X -1900, Y 2000 lies "
                                               "outside the measuring area"))[0] == \
        "strip_row_outside_area"


def test_the_known_ground_is_the_vendors_targets_widened_by_this_tables_readings():
    assert geo.known_x() == (geo.VENDOR_ROW_START_X, geo.VENDOR_APPROACH_X) == (-1439, 2507)
    assert geo.known_x(-1546, 1254) == (-1546, 2507)
    assert geo.known_x(-1300, None)[0] == -1439
    assert geo.known_x(-5000, 9999) == (-5000, geo.TARGET_X_LEFT)
    assert geo.known_x(-40000, 9999) == (geo.TARGET_X_RIGHT, geo.TARGET_X_LEFT)
    # a stored right side is believed anywhere in the protocol's range (4.3.53 fix round:
    # -1801 was voided until then); beyond what a table can report at all, never
    r = rc.Reach.from_dict("0" * 16, {"right_end_x": -1546, "right_how": "free"})
    assert r.right_end_x == -1546
    r = rc.Reach.from_dict("0" * 16, {"right_end_x": -1801, "right_how": "free"})
    assert r.right_end_x == -1801
    r = rc.Reach.from_dict("0" * 16, {"right_end_x": -40000, "right_how": "free"})
    assert r.right_end_x == rc.DEFAULT_RIGHT_END_X


# ---- group I: the countdown only where hands were on the table (guidance off) ----------------

def test_the_countdown_runs_where_hands_were_on_the_table_and_not_before_the_end_homing(
        tmp_path):
    """4.3.53 (the owner on the guidance option: "without interruptions"): until 4.3.52 a 3 s
    countdown ran at every hands-off point of an unguided page: after the sheet was laid, after
    the aims, before the homing at the end (and before the start-up of a cold table). The one
    before the homing at the end had no reason: the rows ran with nobody touching anything. The
    other two have a STATE reason (a sheet was just laid by hand; the hand was on the free arm
    at every aim) and stay. Nothing is sent during any of them."""
    job, sim, helper, p = _job(tmp_path, HIS_AIMS, sight_offset=HIS_SIGHT)
    _read_all(job, p)
    secs = [(c["for"], c["seconds"]) for c in job.countdowns]
    assert secs[:2] == [("align", J.UNGUIDED_COUNTDOWN_S), ("creep", J.UNGUIDED_COUNTDOWN_S)]
    ask = J.Ask(J.Confirm.GO, {"step": "home"})
    n = len(sim.received)
    job._countdown("home", ask)                        # the homing at the end of the page
    assert job.countdowns[-1]["seconds"] == 0.0 and sim.received[n:] == []
    assert job._hands_off_due is False
    job._countdown_owed = True                          # a new sheet laid by hand
    job._countdown("align", J.Ask(J.Confirm.GO, {"step": "align"}))
    assert job.countdowns[-1]["seconds"] == J.UNGUIDED_COUNTDOWN_S


# ---- group I: the calibration and the tile check in ONE reader --------------------------------

def _calibrated(tmp_path, monkeypatch, level=0.88):
    from tests.i1io_table.test_job_reading import job_for
    monkeypatch.setattr(RS, "REST_TILE", level)
    job, sim, helper, run, p = job_for(tmp_path)
    job.stored_tile_white = True
    sim.stored_tile = tuple([0.88] * 36)
    assert p.drive(job.open()).ok
    n = len(sim.received)
    before = job.readers_started
    r = p.drive(job.calibrate())
    return job, sim, helper, r, sim.received[n:], job.readers_started - before


def test_the_tile_is_read_with_the_calibrations_own_reader(tmp_path, monkeypatch):
    """4.3.53 (audit D4; the owner: the calibration itself stays at every new measurement):
    until 4.3.52 the white on the table's tile was made by one reader and the tile read for the
    white-level check / the stored white by a second one started for it (about 6 s). Now the
    calibration's reader reads the tile right after the white; the check and its refusal are
    unchanged, and the table lines are those of before (position readings only)."""
    job, sim, helper, r, lines, readers = _calibrated(tmp_path, monkeypatch)
    assert r.ok, (r.reason, r.detail)
    assert readers == 1
    assert [a[a.index("-p") + 1] for a in helper.started] == ["c1_spot"]
    assert abs(r.detail["white_level_y"] - 88.0) < 0.5
    assert r.detail["stored_white"]["used"] is True
    assert {_cid(ln) for ln in lines} <= {"p0", "s0", "f4"}, lines     # nothing moves


def test_a_white_level_off_is_still_refused_with_one_reader(tmp_path, monkeypatch):
    job, sim, helper, r, lines, readers = _calibrated(tmp_path, monkeypatch, level=0.60)
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "white_level_implausible")
    assert job.calibration is None and readers == 1


# ---- "Skip initial calibration (-N)": the table follows it as a hand measurement does ---------

def _minus_n_job(tmp_path, args, valid):
    from tests.i1io_table.test_job_reading import job_for
    job, sim, helper, run, p = job_for(tmp_path)
    assert job.set_options(args).ok
    helper.calibrated = bool(valid)          # an earlier calibration still valid (ArgyllCMS)
    return job, sim, helper, p


def _names(helper):
    return [(a[a.index("-p") + 1], "-N" in a) for a in helper.started]


def test_minus_n_off_calibrates_at_every_start(tmp_path):
    job, sim, helper, p = _minus_n_job(tmp_path, ["-p"], valid=True)
    assert p.drive(job.open()).ok
    assert p.drive(job.calibrate()).ok and job.calibration is not None
    assert _names(helper)[0] == ("c1_spot", False)       # a calibration, even with one valid


def test_minus_n_on_with_a_valid_calibration_makes_none_and_reads(tmp_path):
    job, sim, helper, p = _minus_n_job(tmp_path, ["-p", "-N"], valid=True)
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate(if_needed=True))
    assert r.ok and r.detail["skipped"] == "still_valid", (r.reason, r.detail)
    assert job.calibration is None and job.minus_n_checked
    assert _names(helper) == [("c1_check", True)]
    for s in ("align",):
        assert p.drive(getattr(job, s)()).ok
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read"


def test_minus_n_on_without_a_valid_calibration_calibrates_before_the_aims(tmp_path):
    """Until 4.3.52 the table learnt it only at the first row, after the aims: the row ended,
    the arm went home, the calibration was made, and the sheet had to be aimed at again."""
    job, sim, helper, p = _minus_n_job(tmp_path, ["-p", "-N"], valid=False)
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.calibrate(if_needed=True))
    assert r.ok and job.calibration is not None, (r.reason, r.detail)
    assert [nm for nm, _n in _names(helper)] == ["c1_check", "c1_spot"]
    assert {_cid(ln) for ln in sim.received[n:]} <= {"p0", "s0", "f4"}   # nothing moved
    assert p.drive(job.align()).ok
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read"
    aims = [c for _s, c, _d, _n, _m in p.asked if c == J.Confirm.AIMED]
    assert len(aims) == 3                                     # aimed once, not twice


def test_the_window_asks_the_instrument_first_with_minus_n(qtbot, monkeypatch, tmp_path):
    from ui import i1io_table_window as W

    class _Opts:
        skip_initial_calibration = True

    class _Rep:
        options = _Opts()

    class _Job:
        ended = None
        calibration_due = False
        calibration = None
        minus_n_checked = False
        options_report = _Rep()

        def out_known(self):
            return False

        def state(self):
            return J.TableState(None, None, None, None, False, False, False, False, False,
                                False, False, 0, 0, None, False)

        def calibrate(self, if_needed=False):
            return if_needed

    win = W.TableMeasureWindow.__new__(W.TableMeasureWindow)
    win.job = _Job()
    fn, status, moves = win._next_action()
    assert fn() is True and "calibration" in status and moves is None
    win.job.minus_n_checked = True
    win.job.alignment = None
    win.job.rows_left = lambda: [1]
    win.job.page_has_something_to_read = lambda: True
    win.job.align = lambda: "align"
    win._again_rows = []
    win.job.front_need = None
    fn, status, moves = win._next_action()
    assert fn() == "align"
