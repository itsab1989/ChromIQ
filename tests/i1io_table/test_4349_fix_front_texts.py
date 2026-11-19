"""4.3.49 fix round (independent safety review 449, MUST-2 and SHOULD-3, and MUST-1 in the window).

MUST-2: the front-zone question is where the new risk of 4.3.49 is consented to (the arm may now
be sent as far forward as the person aimed, and the sight sits about 3 cm in front of the
opening). It says so BEFORE the arm moves: small steps beyond where the arm has been, that the
front of the sheet may lie beyond the opening's travel, that the arm then meets the end in one
step and stops, what ChromIQ does then, the power switch, and laying the sheet back instead.

SHOULD-3: the page after such a stop does not say "ChromIQ did not do this step" (the arm moved).

MUST-1 in the window: its "Bring the arm home" on that page brings the arm home.
"""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import (CROSSES_1, HIS_TABLE,
                                                                        _through_first_row)
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow import measurement_messages as M
from workflow.i1io.table import job as J


def test_the_front_question_says_the_risk_before_the_arm_moves():
    # 4.3.50 (a real user, issue 129): first WHY it asks, in plain words, once per table; the
    # two buttons by name; the risk after the question, short; no distance on this page (it
    # is said after "I will move the sheet"); no idiom ("feel its way")
    title, body = M.M_I1IO_DRIVE_FRONT.render(back_mm=55)
    assert title == "The arm has not been this far forward on this table yet"
    first = body.split("\n\n")[0]
    for words in ("This is not an error", "has moved the arm on this table so far",
                  "slowly, 5 mm at a time", "checks every step", "does not ask again"):
        assert words in first, words
    for words in ("Go forward carefully, my hands are away", "I will move the sheet",
                  "If the arm cannot go further, it stops", "moves it no further forward",
                  "offers to bring it home", "tells you how far to move the sheet",
                  "If the table reports an error or does not answer",
                  "switch the table off at its power switch"):
        assert words in body, words
    assert "55" not in body and "mm further" not in body
    assert "feel" not in body.lower() and "recording" not in body.lower()
    assert "—" not in title + body
    for scare in ("crash", "danger", "damage", "collide", "break", "harm", "warning"):
        assert scare not in body.lower(), scare


def test_the_question_comes_before_any_step_into_the_front(tmp_path):
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1, front_end=3140)
    asked = [(c, sent) for _s, c, _d, sent, _m in p.asked]
    # 4.3.50: ONE question (front_yes is gone)
    sent_at = dict((c, sent) for c, sent in asked if c == J.Confirm.FRONT_CHOICE)
    assert set(sent_at) == {J.Confirm.FRONT_CHOICE}
    beyond = [i for i, ln in enumerate(sim.received) if ln[1:3] == "m0" and len(ln.rstrip()) == 17
              and int(ln[7:11], 16) > 2723]
    assert beyond and min(beyond) >= sent_at[J.Confirm.FRONT_CHOICE]


def test_the_page_after_the_stop_says_what_happened_and_how_home_works():
    from ui.i1io_table_window import reason_text
    why = reason_text("creep_step_did_not_arrive", {"short_mm": 9})
    title, body = M.M_I1IO_DRIVE_FRONT_END.render(why=why)
    assert title == "The arm stopped short of the front of this sheet"
    assert "did not do this step" not in title
    assert "about 9 mm short" in body and "about 9 mm further towards the back" in body
    assert "Bring the arm home" in body and "back along the way it came" in body
    assert "by hand" not in body and "pull" not in body
    assert "—" not in title + body


@pytest.mark.parametrize("front_end", [3140])
def test_in_the_window_the_stop_page_and_its_homing_bring_the_arm_home(
        qtbot, monkeypatch, tmp_path, settings, front_end):  # noqa: F811
    from workflow.i1io.table import reach as rc
    sim = WindowSim(aims=CROSSES_1, front_end=front_end, reach_store=rc.MemoryReachStore(),
                    **HIS_TABLE)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sheet=H.demo_sheet(), sim=sim)
    p.script["front_choice"] = "Go forward carefully, my hands are away"
    page = p.drive_until(("refused",))
    assert page == "refused"
    assert win._title.text() == tr("The arm stopped short of the front of this sheet")
    assert tr("Bring the arm home") in p.labels()
    p.press("Bring the arm home")
    page = p.drive_until(("after_problem", "refused", "stopped", "end_of_session",
                          "home_after_stop_done"))
    # no problem was reported: the page says the arm is home, not "After the problem you
    # reported"
    assert page == "home_after_stop_done", (page, win._text.text())
    assert win._title.text() == tr("The arm is at its resting place")
    t = sim.sim
    assert t.violations == [], t.violations
    assert t.pos[1] <= 250, t.pos                   # at its resting place
    assert win.job.at_rest()
