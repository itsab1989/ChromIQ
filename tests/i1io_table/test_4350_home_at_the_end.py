"""4.3.50 (the first complete page on a real i1iO 2, 19 Nov 2026): THE ARM GOES HOME AS PART OF
THE ENDING, and the texts and ids a real user and the review stumbled on.

On the real page the homing OFFERED after Save ("Leave it there" / "Bring the arm home") was not
taken, and the arm stayed held out over the sheet at (-1284, 3275), in front of every recorded
homing start. Now, after an ending (saved, discarded, nothing read) whose usual homing can run,
the window starts it at once: its first page is the homing's own hands-off GO
(M-I1IO-DRIVE-HOME-AT-END, "Bring the arm home, my hands are away" / "Not now"). The job's rule
decides where it may start from (back along the way the arm came first, then the recorded
homing), unchanged. 4.3.50 fix round: "Not now" (was "Leave it there") moves nothing and keeps
the homing's question open (test_4350_not_now_keeps_the_way_home.py). A START with the arm left
out copes: it reads where the arm is, moves nothing by itself and never sends a homing from
where no recorded one starts.
"""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import CROSSES_1, HIS_TABLE
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc

MOVES = ("m0", "m1", "m2", "i0", "i1")


def _moves(sim):
    return sum(1 for ln in sim.sim.received if ln[1:3] in MOVES)


@pytest.mark.parametrize("ending", ["Save and stop", "Discard and stop"])
def test_after_the_ending_the_homing_starts_and_asks_its_hands_off_go(
        qtbot, monkeypatch, tmp_path, settings, ending):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press(ending)
    assert p.page() == "home_at_end"
    title, _b = M.M_I1IO_DRIVE_HOME_AT_END.render(what="")
    assert win._title.text() == tr(title)
    assert p.labels() == [tr("Not now"), tr("Bring the arm home, my hands are away")]
    assert "home_offered" not in win.pages_shown[-3:]
    n = _moves(sim)
    qtbot.wait(100)
    assert _moves(sim) == n                       # nothing moves before the answer
    p.press("Bring the arm home, my hands are away")
    assert p.page() == "done" and sim.jobs[0].at_rest() and _moves(sim) > n
    assert sim.sim.violations == []


def test_not_now_then_close_moves_nothing_and_the_done_page_says_how_the_arm_comes_home(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    n = _moves(sim)
    p.press("Not now")
    assert p.page() == "home_not_now" and _moves(sim) == n
    p.press("Close")
    assert p.page() == "done" and _moves(sim) == n
    assert "The arm stayed extended over the table" in win._text.text()


def test_his_page_ends_with_the_arm_brought_home_from_in_front_of_every_homing_start(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """His sheet where he laid it, his aims: the last row ends in front of Y 3114, where no
    recorded homing starts. 4.3.52 (the owner's ruling of 2026-11-20): the homing of the ending
    goes straight home from there, as i1Profiler's does (no move back first)."""
    from tests.i1io_table import job_harness as Hm
    sim = WindowSim(aims=CROSSES_1, reach_store=rc.MemoryReachStore(), **HIS_TABLE)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sheet=Hm.demo_sheet(), sim=sim, asking=False)
    p.script["front_choice"] = "Go forward carefully, my hands are away"
    p.drive_until("end_of_session")
    job = sim.jobs[0]
    here = job.state().position_now
    assert here is not None and here[1] > 3114
    p.press("Save and stop")
    assert p.page() == "home_at_end"
    n = len(sim.sim.received)
    p.press("Bring the arm home, my hands are away")
    assert p.page() == "done", (p.page(), win._text.text()[:200])
    assert job.at_rest() and job.way_back_moves == [] and sim.sim.violations == []
    assert [ln[1:3] for ln in sim.sim.received[n:]] == ["s0", "p0", "i1", "s0", "f0", "f4", "f4",
                                                        "p0"]


def test_a_start_with_the_arm_left_out_in_front_is_brought_home(tmp_path):
    """The next START with the arm held at (-1284, 3275), the real page's last place, the aiming
    mode off: the person says "The arm is out"; ChromIQ reads it once, asks the one hands-off
    question and brings it home with i1Profiler's start homing (4.3.52)."""
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.pos = [-1284.0, 3275.0]
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim, {J.Confirm.READY_TO_OPEN: "arm out"})
    assert p.drive(job.open()).ok
    r = p.drive(job.where_is_the_arm())
    assert r.ok and r.detail.get("brought_home") is True, (r.kind, r.reason)
    assert sim.received[11:] == [";p025", ";s022", ";p025", ";i12b", ";s022", ";p025"]
    assert job.at_rest() and sim.violations == []


def test_a_start_after_leave_it_there_in_the_aiming_mode_moves_nothing(tmp_path):
    """After "Leave it there" the table is still in its aiming mode (no f0 was sent): the next
    START meets f4 = 01 at the opening and sends nothing that moves (STILL-AIMING), wherever the
    arm is."""
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.pos, sim.mode, sim.free_arm = [-1284.0, 3275.0], "01", True
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim, {J.Confirm.READY_TO_OPEN: "arm out"})
    r = p.drive(job.open())
    assert r.kind == J.Kind.STOPPED and r.reason == "mode_flag_unexpected"
    assert job.home_after_stop().kind == J.Kind.REFUSED
    for step in ("park", "align", "creep", "home"):
        assert getattr(job, step)().kind != J.Kind.OK
    assert not [ln for ln in sim.received if ln[1:3] in MOVES]
    assert sim.violations == []


def test_the_end_page_says_the_arm_is_brought_home():
    body = M.M_I1IO_DRIVE_END.render()[1]
    assert "brings the arm home if it can" in body and "offers to" not in body
    end = M.M_I1IO_DRIVE_HOME_AT_END.render(what="x")[1]
    assert "Not now" in end and "Leave it there" not in end and "aiming mode" in end
    assert "—" not in body + end


# ---- the ids and texts around it --------------------------------------------------------------

def test_an_early_arrival_is_named_early(tmp_path, monkeypatch):
    """A computed move that finished sooner than its window allows (but arrived) is named so,
    never "late"; the window words both the same way."""
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts, ask_after_each_step=False)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    monkeypatch.setattr(J.geo, "move_window", lambda a, b, speed=300: (5.0, 20.0))
    r = p.drive(job.creep())
    assert r.reason == "movement_early_but_arrived", (r.reason, r.detail)
    assert W.reason_text("movement_early_but_arrived") == W.reason_text(
        "movement_late_but_arrived") == tr("A movement took longer or shorter than recorded.")


def test_i_will_move_the_sheet_says_how_far_after_the_choice():
    text = W.reason_text("sheet_to_be_laid_further_back", {"back_mm": 44})
    assert "about 44 mm further away from you" in text and "Nothing has moved" in text
    assert "about" not in W.reason_text("sheet_to_be_laid_further_back", {})


def test_the_aiming_page_of_a_chart_with_crosses_says_the_other_way():
    import inspect
    src = inspect.getsource(W.TableMeasureWindow._ask)
    assert "“Aiming crosses” switched on" in src and "corner patches, as i1Profiler does" in src
