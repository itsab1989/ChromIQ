"""4.3.52 on 4.3.51: THE START RULE'S OFFERS STAY QUESTIONS WITH THE GUIDANCE OFF.

4.3.51 brought ONE rule for an arm found away from its resting place at a START
(test_4351_one_start_rule.py, test_4351_owner_try.py): on the home line, i1Profiler's recorded
homing; where i1Profiler's recorded homings start, 4.3.48's homing; over the rest of the measuring
area and the front, a TRY; anywhere else nothing is sent. Each of these moves the arm from a place
ChromIQ did not put it, so with "Guided, step by step measurement" off they are NOT on the list of
things the setting may answer: the offer is a page the person answers (Bring the arm home), and the
hands-off question (GO, step "home_after_stop", at_start) is asked, never replaced by a countdown.

Shown here with the guidance off (consent 4, the calibration place from Preferences), on both
paths that can find the arm out with the guidance off (the white's rest check, and -N's alignment;
"The arm is out" is not reachable, the ready question is answered by the setting): nothing moves
before the GO is asked, the GO is asked exactly once, no countdown and no automatic answer stand
for it, and the lines sent afterwards are 4.3.51's, unchanged.
"""
from __future__ import annotations

import pytest

from tests.i1io_table import reader_sim as RS
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4351_one_start_rule import F1_PLUS, F2, MOVES
from tests.i1io_table.test_job_reading import small_sheet
from ui import i1io_table_window as W
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)

#: one place of each START form (the forms and their lines: test_4351_one_start_rule.PLACES)
OFFERED = [("home line", (1098, 810), "start", F1_PLUS),
           ("where recorded homings start", (0, 1600), "end_of_job", F2),
           ("the try over the bed", (800, 800), "try", F2),
           ("the try at the front", (0, 3000), "try", F2)]
NOTHING = [("back strip off the line", (1058, 317)), ("the alignment start", (2507, 1429))]


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    J.HANDS_OFF_BREACHES.clear()


def _unguided_found(tmp_path, path, pos):
    sheet = small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet), real_table=False)
    job.guided = False
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    p = H.Person(job, sim, {})
    if path == "N":
        assert job.set_options(["-N"]).ok
    sim.pos = [float(pos[0]), float(pos[1])]
    r = p.drive(job.open())
    assert r.ok and r.detail["table"] == "warm", (r.reason, r.detail)
    assert job.guided is False and job.turned_guided is None
    r = p.drive(job.calibrate() if path == "cal" else job.align())
    return job, sim, p, r


CASES = [(path, *c) for c in OFFERED for path in ("cal", "N")
         if not (path == "N" and tbl.START_GUARD.contains(c[1]))]


@pytest.mark.parametrize("path,name,pos,form,wire", CASES,
                         ids=[f"{c[1]}-{c[0]}" for c in CASES])
def test_the_start_offer_is_asked_with_the_guidance_off(tmp_path, path, name, pos, form, wire):
    job, sim, p, r = _unguided_found(tmp_path, path, pos)
    assert not [ln for ln in sim.received if ln[1:3] in MOVES], "nothing moved before asking"
    assert r.way_back == J.WayBack.HOME_AFTER_STOP, (name, r.reason, r.way_back)
    assert J.start_homing_form(job._table.position_now) == form
    asked, n = len(p.asked), len(sim.received)
    cds, autos = len(job.countdowns), len(job.auto_answers)
    res = p.drive(job.home_after_stop())
    assert res.ok, (res.kind, res.reason, res.detail)
    gos = [a for a in p.asked[asked:] if a[1] == J.Confirm.GO]
    assert len(gos) == 1, p.asked[asked:]
    step, kind, detail, lines_at_ask, moving = gos[0]
    assert detail.get("step") == "home_after_stop" and detail.get("at_start") is True
    assert detail.get("form") == form
    assert lines_at_ask == n and not moving, "nothing sent before the hands-off answer"
    assert len(job.countdowns) == cds, "no countdown stood for the START offer"
    assert all(a["kind"] != J.Confirm.GO for a in job.auto_answers[autos:])
    assert sim.received[n:] == wire, "4.3.51's lines, unchanged"
    assert tbl.REST_GUARD.contains(job._table.position_now)
    assert sim.violations == [] and J.HANDS_OFF_BREACHES == []


@pytest.mark.parametrize("path,name,pos,form,wire", CASES[:1], ids=["home line-cal"])
def test_back_at_the_start_go_sends_nothing_with_the_guidance_off(tmp_path, path, name, pos,
                                                                  form, wire):
    job, sim, p, r = _unguided_found(tmp_path, path, pos)
    p.script[J.Confirm.GO] = "back"
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert res.kind == J.Kind.REFUSED and res.reason == "person_chose_back"
    assert sim.received[n:] == []


@pytest.mark.parametrize("path", ["cal", "N"])
@pytest.mark.parametrize("name,pos", NOTHING, ids=[c[0] for c in NOTHING])
def test_where_nothing_is_offered_nothing_is_sent_with_the_guidance_off(tmp_path, path, name,
                                                                       pos):
    job, sim, p, r = _unguided_found(tmp_path, path, pos)
    assert not r.ok
    assert not [ln for ln in sim.received if ln[1:3] in MOVES]
    n = len(sim.received)
    assert job.home_after_stop().kind == J.Kind.REFUSED and sim.received[n:] == []


def test_the_start_offer_is_never_answered_by_the_setting(tmp_path):
    """The policy itself, for every form the START rule can offer."""
    job, sim, p, r = _unguided_found(tmp_path, "cal", (1098, 810))
    job.turned_guided = None
    job._fault_seen = None           # as in a sitting without trouble
    for form in ("start", "end_of_job", "try"):
        ask = J.Ask(J.Confirm.GO, {"step": "home_after_stop", "at_start": True, "form": form})
        assert job._without_the_person(ask) is None, form


def test_a_start_with_the_arm_out_turns_the_rest_of_the_sitting_guided(tmp_path):
    """The fix round's MUST-1 rule (job._from_exception), as it now meets 4.3.51's START rule:
    the arm found out is a refusal, so the rest of that sitting is guided; the next START is
    unguided again (guidance is per sitting; a new job is built for it)."""
    job, sim, p, r = _unguided_found(tmp_path, "cal", (800, 800))
    assert job.guided_now is True and str(job.turned_guided).startswith("fault:")


# ---- 4.3.51's i1Profiler limit, on the branch's own new page ---------------------------------

@pytest.mark.parametrize("code", ["en", "de"])
def test_the_start_up_arm_page_says_the_i1profiler_limit_once(qtbot, monkeypatch, tmp_path,
                                                              settings, code):  # noqa: F811
    """M-I1IO-DRIVE-START-UP-ARM (4.3.52, the one arm question after power-on with the guidance
    off) sends the person to "i1Profiler 3.8.6 or older" as M-I1IO-DRIVE-START-UP does, so it
    carries 4.3.51's flag and the page shows the limit notice once (found at the rebase onto
    v4.3.51: the flag was missing)."""
    from core import i18n
    from tests.i1io_table.test_4352_guidance_off import _unguided
    from tests.i1io_table.window_sim import WindowSim
    from workflow import measurement_messages as M
    assert M.M_I1IO_DRIVE_START_UP_ARM.needs_old_i1profiler
    i18n.set_language(code)
    try:
        win, sim, run, p, saved, finished = _unguided(qtbot, monkeypatch, tmp_path, settings,
                                                      sim=WindowSim(cold=True))
        assert p.page() == "start_up_arm"
        notice = M.M_I1IO_DRIVE_I1PROFILER_LIMIT.render()[1]
        assert win._text.text().count(notice) == 1
    finally:
        i18n.set_language("en")
