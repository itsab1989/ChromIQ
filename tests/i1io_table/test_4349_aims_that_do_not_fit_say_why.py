"""4.3.49: a real table run of 19 Nov 2026 on ChromIQ's own A4 chart with crosses (the chart of
``data/demo-sheet.i1io.json``: 528 patches, crosses 11 mm in from the paper's edges).

What the run showed, reproduced here on the simulated table with the real aims (p1 readings):

* aims at the CROSSES that had the right shape but lay 13-14 mm further to the front than any
  target ChromIQ allows were refused with "The three marks you aimed at do not fit this sheet",
  which named no reason and no remedy; the person aimed again five times, then stopped;
* aims at the coloured CORNER PATCHES beside the crosses (i1Profiler's habit) were refused with
  the same sentence;
* "Bring the arm home" from the free arm at the front was refused with "ChromIQ could not do this
  step" and offered again;
* the table's status answer a0 = 530000 (after the arm was moved by hand) stopped the opening
  with no sentence of its own.

Each page now says which check did not fit, by how much, and what to do; the refusal page always
carries End measurement, and from the second refusal in a row says so. Nothing that is SENT
changes here, except the length tolerance of the three-mark check (for the safety review).
"""
from __future__ import annotations

import math

import pytest

from core.i18n import tr
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc

#: the real aims (p1), 19 Nov 2026
CROSSES_1 = [(1394, 1369), (1402, 3253), (-1362, 3253)]        # d1-1, by the button
CROSSES_2 = [(1394, 1379), (1399, 3240), (-1362, 3252)]        # d1-2, by the button
PATCHES_4 = [(1245, 1466), (1246, 3151), (-1293, 3155)]        # d1-4, the corner patches
MOTION = ("m0", "m1", "m2", "i1", "i0")


def _moves_after_aims(received):
    last_p1 = max(i for i, x in enumerate(received) if x == ";p124")
    return [x for x in received[last_p1:] if x[1:3] in MOTION]


def _shift(aims, dx, dy):
    return [(x + dx, y + dy) for x, y in aims]


def _sheet_mm(sheet):
    return [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]


# ---- the job: the numbers the page needs, nothing moved ----------------------------------------

def test_his_aims_at_the_crosses_are_accepted_as_he_aimed_them():
    """4.3.49 (Basti's ruling): the front follows what he aimed at, so his aims are accepted
    (they were refused for the front in 4.3.48)."""
    sheet = H.demo_sheet()
    al = geo.fit_model(_sheet_mm(sheet), CROSSES_1)           # the shape fits
    assert abs(al.checks["angle_deg"] - 90) < 0.3
    res, job, sim, _p = H.run_steps(["open", "align"], aims=CROSSES_1,
                                    script={J.Confirm.FRONT_CHOICE: "go on"})
    assert res[1].ok, (res[1].reason, res[1].detail)


#: his aims, the sheet 10 mm further to the right: mark 3 lies beyond the right side (X -1384,
#: 5 mm inside the right stop the evidence shows), which is still refused
OFF_THE_RIGHT = _shift(CROSSES_1, -100, 0)


def test_aims_beyond_the_right_side_say_by_how_much():
    res, job, sim, _p = H.run_steps(["open", "align"], aims=OFF_THE_RIGHT)
    r = res[1]
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "aims_outside_area")
    assert r.detail["outside_mark"] == 3
    # 7.8 mm beyond the side: 9 mm to the left, with 1 mm to spare
    assert r.detail["sheet_move"] == {"back_mm": 0, "front_mm": 0, "left_mm": 9,
                                      "right_mm": 0}
    assert r.detail["refusals_in_a_row"] == 1
    assert _moves_after_aims(sim.received) == []


def test_his_aims_at_the_corner_patches_are_named_as_such():
    res, job, sim, _p = H.run_steps(["open", "align"], aims=PATCHES_4)
    r = res[1]
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "aims_distance_1_2")
    assert r.detail["aimed_at"] == "corner_patches"
    assert r.detail["lengths"]["table_mm"] == 168.5 and r.detail["lengths"]["sheet_mm"] == 188.0
    assert _moves_after_aims(sim.received) == []


def test_refusals_in_a_row_are_counted_and_a_fit_resets_them():
    job, sim, _t = H.make_job(aims=OFF_THE_RIGHT)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    assert p.drive(job.align()).detail["refusals_in_a_row"] == 1
    assert p.drive(job.align()).detail["refusals_in_a_row"] == 2
    sim.aims = list(H.demo_aims())
    assert p.drive(job.align()).ok and job.align_refusals_in_a_row == 0
    job.close()


def test_laid_where_the_page_says_his_aims_fit_and_the_first_move_starts():
    """The advice of the refusal page, followed: the sheet 16 mm back. The marks are then
    accepted, and the free arm after mark 3 (at the right end of the arm's travel, beside
    AREA_RAW) is moved from where it stands."""
    aims = _shift(CROSSES_1, 0, -160)
    res, job, sim, _p = H.run_steps(["open", "align", "creep", "home"],
                                    aims=aims, script={J.Confirm.FRONT_CHOICE: "go on"})
    assert res[1].ok, (res[1].reason, res[1].detail)
    assert all(r.reason != "free_arm_outside_area" for r in res), [r.reason for r in res]
    assert res[2].ok and res[3].ok, [(r.step, r.reason) for r in res]
    assert sim.violations == []


def test_laid_only_back_the_free_arm_beside_the_area_is_moved_from_where_it_stands():
    """Laid only back, not to the left: the free arm after mark 3 stands about 3 mm to the
    right of AREA_RAW. 4.3.48 refused the first move there (free_arm_outside_area, a box from
    where recordings happened to read the arm); since Basti's ruling of 19 Nov 2026 the arm is
    moved from where the hand left it, judged by the target alone."""
    aims = _shift(CROSSES_1, 0, -190)
    res, job, sim, _p = H.run_steps(["open", "align", "creep"], aims=aims,
                                    script={J.Confirm.FRONT_CHOICE: "go on"})
    assert res[1].ok
    assert all(r.reason != "free_arm_outside_area" for r in res), [r.reason for r in res]
    assert res[2].ok, [(r.step, r.reason) for r in res]
    assert sim.violations == []


def test_the_homing_of_a_free_arm_at_the_front_says_how_far_to_push_it():
    res, job, sim, _p = H.run_steps(["open", "align", "home"], aims=CROSSES_1)
    r = res[2]
    assert r.reason == "homing_only_from_inside_the_area"
    assert r.detail["arm_free"] is True and r.detail["push"]["back_mm"] > 0
    assert _moves_after_aims(sim.received) == []
    # pushed back by hand as the page says (simulated hand), the homing then runs
    job, sim, _t = H.make_job(aims=OFF_THE_RIGHT)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    p.drive(job.align())
    r = p.drive(job.home())
    push = r.detail["push"]
    sim.hand_to(sim.pos[0] + 10 * push["left_mm"], sim.pos[1] - 10 * push["back_mm"])
    assert p.drive(job.home()).ok
    assert sim.violations == []
    job.close()


def test_the_table_state_after_a_hand_move_names_its_answer_and_sends_nothing_more():
    from tests.i1io_table import part_c_sim as csim
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.inject("a0_after_hand", "a0")
    res, job, sim, _p = H.run_steps(["open"], sim=sim)
    r = res[0]
    assert (r.kind, r.reason) == (J.Kind.STOPPED, "table_state_unknown")
    assert r.detail["a0"] == "530000"
    assert sim.received[-1] == ";a034" and len(sim.received) == 6


# ---- the length tolerance (FOR THE SAFETY REVIEW) ----------------------------------------------

def test_the_length_tolerance_grows_with_the_side_and_still_refuses_a_wrong_point():
    assert geo.length_tolerance(1880) == pytest.approx(27.52)
    assert geo.length_tolerance(2750) == pytest.approx(31.0)
    sheet = H.demo_sheet()
    mm = _sheet_mm(sheet)
    base = H.demo_aims(sheet)
    # mark 3 placed so that side 2-3 is 2.6 mm long (refused by 4.3.48's flat 2 mm)
    ux = (base[2][0] - base[1][0]) / math.dist(base[1], base[2])
    long_ = [base[0], base[1], (round(base[2][0] + 26 * ux), base[2][1])]
    geo.fit_model(mm, long_)
    with pytest.raises(geo.AlignmentRefused):
        geo.fit_model(mm, [base[0], base[1], (round(base[2][0] + 36 * ux), base[2][1])])
    # the corner patch for a cross (his round 4) and a patch one row off stay refused
    with pytest.raises(geo.AlignmentRefused):
        geo.fit_model(mm, PATCHES_4)
    with pytest.raises(geo.AlignmentRefused):
        geo.fit_model(mm, [base[0], (base[1][0], base[1][1] - 90), base[2]])
    # every real alignment fits, and with more room than before
    for name in ("R1 200.3", "R1 401.6", "R2 427.5", "S2 3.5", "S2 270.8", "S2 383.3",
                 "S2 526.8", "S2 684.0"):
        sh, pts = H.recorded_sheet(name, 17)
        geo.fit_model([tuple(sc.sheet_table_mm(sh, a["page_mm"])) for a in sc.aims_of(sh, 0)],
                      pts)
    for aims in (CROSSES_1, CROSSES_2):
        geo.fit_model(mm, aims)


# ---- the window: the words ---------------------------------------------------------------------

def _to_first_refusal(qtbot, monkeypatch, tmp_path, settings, aims):
    sim = WindowSim(aims=aims)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sheet=H.demo_sheet(), sim=sim)
    assert p.drive_until("refused") == "refused", win.pages_shown[-4:]
    return win, sim, p


def test_the_page_says_the_aims_fit_and_how_far_to_lay_the_sheet(qtbot, monkeypatch, tmp_path,
                                                                 settings):
    win, sim, p = _to_first_refusal(qtbot, monkeypatch, tmp_path, settings, OFF_THE_RIGHT)
    text = win._text.text()
    assert tr("The three marks you aimed at do not fit this sheet.") not in text
    assert "so you aimed at the right points" in text and "mark 3 lies further out" in text
    assert "about 9 mm to the left" in text
    assert "towards the back" not in text
    assert set(p.labels()) >= {"Carry on", "End measurement"}
    # aimed again at the same place: the second refusal says so
    p.press("Carry on")
    assert p.drive_until("refused") == "refused"
    assert "The aims have not fitted 2 times in a row now." in win._text.text()
    assert "End measurement" in p.labels()
    assert sim.sim.violations == []


def test_the_page_names_the_corner_patches(qtbot, monkeypatch, tmp_path, settings):
    win, sim, p = _to_first_refusal(qtbot, monkeypatch, tmp_path, settings, PATCHES_4)
    text = win._text.text()
    assert "Marks 1 and 2 are 168.5 mm apart on the table, but 188.0 mm apart" in text
    assert "fit the coloured corner patches beside the crosses exactly" in text
    assert "aim again at the centre of each cross" in text


def test_the_aim_page_names_the_cross_and_not_the_patch(qtbot, monkeypatch, tmp_path, settings):
    sim = WindowSim()
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sheet=H.demo_sheet(), sim=sim)
    assert p.drive_until("aimed") == "aimed"
    text = win._text.text()
    assert "Mark 1 is the thin printed cross in a small square" in text
    assert "not on the coloured patch next to it" in text


def test_the_homing_refusal_says_where_to_push_the_free_arm(qtbot, monkeypatch, tmp_path,
                                                             settings):
    win, sim, p = _to_first_refusal(qtbot, monkeypatch, tmp_path, settings, CROSSES_1)
    p.press("Bring the arm home")
    if p.page() == "go":
        p.press("Go")
    assert p.page() == "refused", win.pages_shown[-3:]
    text = win._text.text()
    assert "ChromIQ could not do this step" not in text
    assert "please push it gently by hand about" in text
    assert "towards the back of the table (away from you)" in text


def test_the_table_state_page_says_what_the_table_answered(qtbot, monkeypatch, tmp_path,
                                                           settings):
    sim = WindowSim(table_faults=[("a0_after_hand", "a0")])
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim)
    p.drive_until(("stopped", "refused", "done"))
    text = win._text.text()
    assert "ChromIQ could not do this step" not in text
    assert "with 530000" in text and "111800 (just switched on)" in text
    assert "after its arm was moved by hand" in text
    assert "switch the table off at its power switch, wait a few seconds" in text
