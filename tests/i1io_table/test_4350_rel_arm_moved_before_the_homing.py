"""4.3.50 integration, the table re-review's MUST-A, MUST-B and SHOULD-1..3 (20 Nov 2026).

MUST-A. After "Not now" the person may reach the sheet and nudge the held arm. "Bring the arm
home" then refuses (correctly: the reading right before the homing differs from where ChromIQ
left the arm, job.py ``_end_of_job``), but the page that followed said "The arm did not report
the place it was sent to" (nothing was sent), promised that i1Profiler "brings the arm home"
(no recording shows that from there) and offered to save readings that were already saved.
Now:
* the homing pages (HOME-AT-END, HOME-NOT-NOW) say plainly not to move the arm while reaching
  the sheet;
* a held arm read elsewhere right before the homing of the ending: nothing after the s0 p0, and
  its own page (M-I1IO-DRIVE-HOME-ARM-MOVED) that says what is true;
* the guard itself has a test (it had none: replacing it by ``if False`` stayed green).

MUST-B. The page for a table that answers a0 with 530000 at the opening (most likely the aiming
mode left on) says to press End measurement FIRST: until then ChromIQ holds the connection and
i1Profiler cannot find the table.

SHOULD-1: the switch-off sentence once on the homing pages, in every language. SHOULD-2: the
front-stop page promises no homing that no recording shows. SHOULD-3: CONSENT_VERSION 3.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow import measurement_messages as M

MOVES = ("m0", "m1", "m2", "i0", "i1")
BRING = "Bring the arm home, my hands are away"
DO_NOT_MOVE = "Please do not move the arm while you reach for the sheet."
I18N = Path(__file__).resolve().parents[2] / "data" / "i18n"


def _cids(sim, since=0):
    return [ln[1:3] for ln in sim.sim.received[since:]]


def _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert p.page() == "home_at_end"
    return win, sim, p


def test_both_homing_pages_say_not_to_move_the_arm_while_reaching_the_sheet(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    for msg in (M.M_I1IO_DRIVE_HOME_AT_END, M.M_I1IO_DRIVE_HOME_NOT_NOW):
        assert DO_NOT_MOVE in msg.body, msg.id
        assert "only from the place where it left it" in msg.body, msg.id
    win, sim, p = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    assert tr(DO_NOT_MOVE) in win._text.text()
    p.press("Not now")
    assert tr(DO_NOT_MOVE) in win._text.text()


@pytest.mark.parametrize("not_now", [True, False])
def test_a_held_arm_moved_before_the_homing_of_the_ending_is_not_driven_and_the_page_is_true(
        qtbot, monkeypatch, tmp_path, settings, not_now):  # noqa: F811
    win, sim, p = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    if not_now:
        p.press("Not now")
    job = sim.jobs[0]
    left = tuple(job.state().position_now)
    # the person reaches the sheet and pushes the held arm 4 mm (the re-reviewer's on-screen run)
    sim.sim.pos = [left[0], left[1] + 40.0]
    n = len(sim.sim.received)
    p.press(BRING)
    page = p.drive_until(("stopped", "done", "refused"))
    assert page == "stopped", (page, win._text.text()[:300])
    cids = _cids(sim, n)
    # the guard before the homing (job.py _end_of_job): the status and one reading, nothing else
    assert cids == ["s0", "p0"], cids
    assert not [c for c in _cids(sim) if c == "f0"]
    assert sim.sim.violations == []
    title, _b = M.M_I1IO_DRIVE_HOME_ARM_MOVED.render(what="x", log="x")
    assert win._title.text() == tr(title)
    text = win._text.text()
    assert tr("The measurement was saved into the run.") in text
    for wrong in ("did not report the place it was sent to", "it brings the arm home",
                  "you can still save them", "Your readings so far are kept"):
        assert wrong not in text, wrong
    assert "sent no movement" in text
    assert p.labels() == [tr("Close")]
    # the done page then gives the way on that is true for a table left in its aiming mode
    p.press("Close")
    assert p.page() == "done"
    assert tr(M.M_I1IO_DRIVE_LEFT_OUT.render()[1]) in win._text.text()
    assert "it brings the arm home" not in win._text.text()


def test_the_doubt_before_the_homing_has_its_own_id():
    from workflow.i1io.table import job as J
    assert J.doubt_id("before the homing the held arm reads (1, 2), not (1, 3), where ChromIQ "
                      "left it") == "arm_moved_before_homing"
    assert "was moved" in W.reason_text("arm_moved_before_homing")
    assert "sent to" not in W.reason_text("arm_moved_before_homing")


def test_the_a0_530000_page_says_end_measurement_before_i1profiler(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """2026-11-21 fix round (B-1): a0 and f4 that disagree are put right at START; the one
    refusal left is four mode answers that differ among themselves: nothing moves, End
    measurement first, then the power switch and START, never i1Profiler."""
    from workflow import measurement_messages as M
    sim = WindowSim(table_faults=[("free", "f4")])         # the first f4 answers 01, then 00
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, asking=False)
    page = p.drive_until(("stopped", "refused", "done"))
    assert page == "stopped"
    assert win._title.text() == M.M_I1IO_DRIVE_STILL_AIMING.render(log="x")[0]
    text = win._text.text()
    end = text.find("1. Press End measurement")
    start = text.find("START MEASUREMENT")
    assert end != -1 and start != -1 and end < start, text
    assert "i1Profiler" not in text
    assert tr("End measurement") in p.labels() and sim.jobs[-1].phase == "open"


def _catalogue(code):
    return json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", sorted(p.stem for p in I18N.glob("*.json")))
def test_the_switch_off_sentence_is_said_once_on_the_homing_pages(code):
    cat = _catalogue(code)
    line = cat.get("To stop the arm at once, switch the table off at its power switch.")
    assert line
    for msg in (M.M_I1IO_DRIVE_HOME_AT_END, M.M_I1IO_DRIVE_HOME_NOT_NOW):
        body = cat.get(msg.body)
        assert body, (code, msg.id)
        # the window adds the line unless its exact translation is there (MOVES_AT_ONCE_PAGES)
        assert line in body, (code, msg.id)


def test_the_front_stop_way_promises_no_homing_that_no_recording_shows():
    win = W.TableMeasureWindow.__new__(W.TableMeasureWindow)
    for rid in W.FRONT_STOP_IDS:
        for ending in (True, False):
            way = W.TableMeasureWindow._front_stop_way(win, rid, ending)
            # 2026-11-21 (the owner: "driving the table should work without involving
            # i1profiler"): the way on is the power switch and START, never i1Profiler
            assert "i1Profiler" not in way and "START MEASUREMENT" in way


def test_the_consent_is_asked_again_for_this_version():
    # 4.3.52: version 4 (the guidance, its countdown, the reader's facts, the alarm)
    assert W.CONSENT_VERSION == 4
