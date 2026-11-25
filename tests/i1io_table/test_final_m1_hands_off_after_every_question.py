"""Final fix round, M-1 (review 13): a hand can be on the bed or the arm at EVERY question.

The rule: after ANY question the person answers, the next motor move is preceded by the
hands-off GO, unless that question's own answer IS the hands-off confirmation (then its page
says "take your hands away from the table and the arm" and names the move that follows).

Three kinds of proof:

* the job, every question it can ask, both modes: between an answer that is not a hands-off
  confirmation and the next answer, not one movement line is sent;
* the panel, the same rule over every page a person answers (the job's questions and the
  panel's own: the mark-3 check, Go on, Next step, the problem page, ...), both modes;
* the texts: every hands-off answer's page says so, and the two promises (CHANGELOG and the
  preparation page) say what the code does.

And the table module's guard refuses a movement while a confirmation is owed (planted)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.i1io_table import tester_d2 as D2
from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read, small_sheet
from workflow.i1io.table import job as J
from tests.i1io_table.test_window import settings  # noqa: F401 (the fixture)


@pytest.fixture(autouse=True)
def _first_time_on_new_ground(monkeypatch):
    """4.3.53 fix round (inventory A8): ground this table's reach record already holds no
    longer gets the guided first-visit question (TableJob._known_ground). The tests in this
    file are about what happens AT and AROUND a first-visit question (or compare the wire with
    tester 0.6.0, which asked it), so they keep the first time on new ground everywhere;
    tests/i1io_table/test_4353_first_visit_once.py proves the new rule."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J.TableJob, "_known_ground", lambda self, p: False)

ASKING = pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])
#: the panel walks in BOTH presentations (quiet round, 2026-11-18): the panel and the quiet
#: mode's pop-ups, each with and without the report after every step
MODES = pytest.mark.parametrize("asking,presentation",
                                [(True, "panel"), (False, "panel"),
                                 (True, "popups"), (False, "popups")],
                                ids=["panel-asking", "panel-quiet", "popups-asking",
                                     "popups-quiet"])
MOVES = ("m0", "m1", "m2", "i1", "i0")
HANDS = "take your hands away from the table and the arm"


def _motions(sim) -> int:
    return sum(1 for ln in sim.received if ln[1:3] in MOVES)


class _Timeline:
    """Every answer the job gets (its own questions, the report, the panel's own questions),
    with the number of movement lines sent before it."""

    def __init__(self, job, sim):
        self.job, self.sim, self.events = job, sim, []
        real_answer, real_report, real_window = job._answer, job._report, job.person_answered

        def answer(kind, value, by=""):
            self.events.append(((kind, value), _motions(sim)))
            return real_answer(kind, value, by)

        def report(value):
            if job.report_due is not None:
                self.events.append(((J.Confirm.REPORT_AFTER_STEP, value), _motions(sim)))
            return real_report(value)

        def window(question_id, answer=""):
            self.events.append(((question_id, answer), _motions(sim)))
            return real_window(question_id, answer)
        job._answer, job._report, job.person_answered = answer, report, window

    def breaches(self) -> list:
        """Answers after which the arm moved before the next answer, although they were not a
        hands-off confirmation."""
        ok = J.HANDS_OFF_ANSWERS | J.HANDS_OFF_WINDOW_ANSWERS
        out = []
        ev = self.events + [(("end", ""), _motions(self.sim))]
        for (ans, n), (_nxt, m) in zip(ev, ev[1:]):
            if m > n and ans not in ok:
                out.append((ans, m - n))
        return out

    def kinds(self) -> set:
        return {a[0] for a, _n in self.events}


# ---- the job: every question, both modes ---------------------------------------------------------

def _end_and_home(job, p):
    r = job.end()
    if r.kind == J.Kind.NEEDS:
        r = job.answer(J.Confirm.END, "save")
    r = p.drive(job.home())
    job.close()
    return r


def _sc_whole(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, asking=asking)
    tl = _Timeline(job, sim)
    ready_to_read(job, p)
    read_page(job, p)
    _end_and_home(job, p)
    return tl


def _sc_cold(tmp_path, asking):
    sheet = small_sheet()
    sim = csim.CSimTable(part_c=True, aims=list(H.demo_aims(sheet)), cold=True)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, sim=sim,
                                                ask_after_each_step=asking)
    p = H.Person(job, sim)
    tl = _Timeline(job, sim)
    for s in ("open", "start_up", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    read_page(job, p)
    _end_and_home(job, p)
    return tl


def _sc_own_tile(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, asking=asking,
                                       script={J.Confirm.CAL_PLACE: "own tile"})
    tl = _Timeline(job, sim)
    ready_to_read(job, p)
    read_page(job, p)
    _end_and_home(job, p)
    return tl


def _sc_consent_in_a_row(tmp_path, asking):
    """-N: no calibration, so the reader consent is asked in the first row, right before the
    arm would move to its first patch: GO follows it."""
    job, sim, helper, run, p = job_for(tmp_path, asking=asking)
    assert job.set_options(["-v", "-c", "1", "-p", "-N", "chart"]).ok
    tl = _Timeline(job, sim)
    for s in ("open", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    p.drive(job.read_row())
    asked = [c for _s, c, *_r in p.asked]
    i = asked.index(J.Confirm.READER_CONSENT)
    assert asked[i + 1] == J.Confirm.GO
    _end_and_home(job, p)
    return tl


def _sc_failed_rows(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, asking=asking, sheet=small_sheet([3, 3, 3]),
                                       faults={"read": {2: "dies_twice", 9: "dies_twice"}},
                                       script={J.Confirm.ROW_FAILED: "again"})
    tl = _Timeline(job, sim)
    ready_to_read(job, p)
    p.script[J.Confirm.ROW_FAILED] = "again"
    p.drive(job.read_row())
    p.script[J.Confirm.ROW_FAILED] = "skip"
    read_page(job, p)
    _end_and_home(job, p)
    return tl


def _sc_strip(tmp_path, asking):
    sheet = H.demo_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=asking,
                                                faults={"scan": {"not_ready": True},
                                                        "scan_at": 2})
    assert job.set_options(["-v", "-c", "1", "chart"]).ok
    p = H.Person(job, sim, {J.Confirm.ROW_FAILED_STRIP: "patch by patch"})
    tl = _Timeline(job, sim)
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    for _ in range(2):
        p.drive(job.read_row())
    _end_and_home(job, p)
    return tl


def _sc_front(tmp_path, asking):
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts, ask_after_each_step=asking)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    tl = _Timeline(job, sim)
    for s in ("open", "align", "creep", "home"):     # 4.3.50: no check move
        assert p.drive(getattr(job, s)()).ok, s
    job.close()
    return tl


def _sc_keep_measuring(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, asking=asking)
    tl = _Timeline(job, sim)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    r = job.end()
    assert r.confirm == J.Confirm.END
    assert job.answer(J.Confirm.END, "keep measuring").ok
    read_page(job, p)
    _end_and_home(job, p)
    return tl


def _sc_window_questions(tmp_path, asking):
    """The panel's own questions, as the panel tells the job about them: a "Go on" (never a
    hands-off answer; 4.3.50: the mark-3 check's "centred", the only window answer that was one,
    is gone)."""
    job, sim, helper, run, p = job_for(tmp_path, asking=asking)
    tl = _Timeline(job, sim)
    ready_to_read(job, p)
    job.person_answered("stored_white_refused", "_next")
    assert p.drive(job.read_row()).ok
    job.person_answered("next_page", "_next")          # any page of the panel's own
    r = p.drive(job.read_row())
    assert r.ok
    _end_and_home(job, p)
    return tl


def _sc_identity(tmp_path, asking):
    """The new chart layout (25 Nov 2026): the row identity check's question, on the bed that
    reads another sheet than the chart's: "right" (the next row's GO comes first), then, on a
    second table, "stop"."""
    from tests.i1io_table import bed_sim as B
    ch = B.build_chart(tmp_path, count=48)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(48, seed=99), seed=9)
    job, sim, helper, run = B.bed_job(tmp_path, ch, B.Bed(other.laid()),
                                      ask_after_each_step=asking)
    assert job.set_options(["-v", "-c", "1", "chart"]).ok
    p = H.Person(job, sim, {J.Confirm.ROW_IDENTITY: "right"})
    tl = _Timeline(job, sim)
    ready_to_read(job, p)
    for _ in range(2):
        assert p.drive(job.read_row()).ok
    _end_and_home(job, p)
    return tl


SCENARIOS = {"identity": _sc_identity, "whole": _sc_whole, "cold": _sc_cold, "own_tile": _sc_own_tile,
             "consent_in_a_row": _sc_consent_in_a_row, "failed_rows": _sc_failed_rows,
             "strip": _sc_strip, "front": _sc_front, "keep_measuring": _sc_keep_measuring,
             "window_questions": _sc_window_questions}


@ASKING
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_no_movement_between_an_answered_question_and_a_hands_off_confirmation(
        tmp_path, asking, scenario):
    tl = SCENARIOS[scenario](tmp_path, asking)
    assert tl.events, "nothing was asked"
    assert tl.breaches() == [], tl.events


def test_the_walk_reaches_every_question_the_job_can_ask(tmp_path):
    seen = set()
    for name, sc in SCENARIOS.items():
        for asking in (True, False):
            seen |= _Timeline.kinds(sc(tmp_path / f"{name}-{asking}", asking))
    every = set(J.CHOICES) - {J.Confirm.MARKER}
    # the marker question is asked before the USB is opened and is followed by READY_TO_OPEN
    # (test_the_marker_question_is_followed_by_ready_to_open_before_anything_moves)
    assert every <= seen | {J.Confirm.END}, sorted(every - seen)
    assert J.Confirm.REPORT_AFTER_STEP in seen and J.Confirm.FRONT_CHOICE in seen


def test_the_marker_question_is_followed_by_ready_to_open_before_anything_moves(tmp_path):
    from workflow.i1io.table import session_end as se
    folder = tmp_path / "markers"
    folder.mkdir()
    (folder / se.app_in_use_name("app-", "20261117-140000")).write_text("{}", encoding="utf-8")
    job, sim, helper, run = RS.make_reading_job(tmp_path, app_marker_place=(folder, "app-"))
    assert job._unacknowledged_markers()
    p = H.Person(job, sim)
    tl = _Timeline(job, sim)
    assert p.drive(job.open()).ok
    kinds = [a[0] for a, _n in tl.events]
    assert kinds[:2] == [J.Confirm.MARKER, J.Confirm.READY_TO_OPEN]
    assert _motions(sim) == 0 and job._hands_off_due
    job.close()


# ---- the guard ---------------------------------------------------------------------------------

def test_a_movement_after_a_question_without_the_confirmation_is_refused_by_the_table(
        tmp_path, monkeypatch):
    """Planted: a question is answered inside a row (simulated: the confirmation becomes owed
    right before the move to a patch) and the job forgets its GO. The table module's guard
    refuses the movement line: nothing moves and nothing more is sent."""
    def no_go(self, step, **detail):
        return
        yield  # pragma: no cover
    monkeypatch.setattr(J.TableJob, "_hands_off", no_go)
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)

    def owed(ev):
        if ev.get("event") == "patch_next":
            job._hands_off_due = True
    job.on_progress = owed
    n = _motions(sim)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.STOPPED and _motions(sim) == n, (r.kind, r.reason)
    assert r.state.sending_closed
    assert J.HANDS_OFF_BREACHES
    J.HANDS_OFF_BREACHES.clear()            # planted on purpose (see conftest.py)


def test_the_sheet_laid_answer_is_the_hands_off_go_and_no_go_comes_before_it(tmp_path):
    """Review 13's P1: GO, then "lay the sheet", then four moves. Now the sheet-laid answer is
    the confirmation, and nothing moves before it."""
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p, steps=("open", "calibrate"))
    seen = []
    p.on_ask = lambda person, res: seen.append((res.confirm, _motions(sim))) or None
    n = _motions(sim)
    assert p.drive(job.align()).ok
    assert seen[0] == (J.Confirm.SHEET_LAID, n) and seen[0][1] == n
    assert J.Confirm.GO not in [k for k, _m in seen[:2]]
    assert seen[0][0] == J.Confirm.SHEET_LAID and (J.Confirm.SHEET_LAID, "yes") in \
        J.HANDS_OFF_ANSWERS


# ---- the texts ---------------------------------------------------------------------------------

def test_every_hands_off_answer_page_says_take_your_hands_away_and_what_moves():
    from ui import i1io_table_window as W
    from workflow import measurement_messages as M
    pages = {
        (J.Confirm.SHEET_LAID, "yes"): M.M_I1IO_DRIVE_SHEET_LAID.render(
            page=1, corner=M._I1IO_CORNER_MARK)[1],
        (J.Confirm.FIRST_VISIT, "yes"): M.M_I1IO_DRIVE_FIRST_VISIT.render()[1],
        (J.Confirm.START_UP, "yes"): M.M_I1IO_DRIVE_START_UP.render()[1],
        (J.Confirm.GO, "yes"): M.M_I1IO_DRIVE_GO.render()[1],
        # 4.3.50: the one front question's "Go forward carefully, my hands are away"
        (J.Confirm.FRONT_CHOICE, "go on"): M.M_I1IO_DRIVE_FRONT.render(back_mm=7)[1],
    }
    for (kind, value), body in pages.items():
        assert HANDS in body, kind
        if kind != J.Confirm.GO:
            label = W.choice_label(kind, value)
            assert f"“{label}”" in body, (kind, label)
            assert "at once" in body, kind
    # the GO of the ending's homing has its own page (4.3.50), with its own button
    end = M.M_I1IO_DRIVE_HOME_AT_END.render(what="Saved.")[1]
    assert HANDS in end and "“Bring the arm home, my hands are away”" in end and "at once" in end
    assert set(pages) | {(J.Confirm.REPORT_AFTER_STEP, "as described")} == \
        J.HANDS_OFF_ANSWERS | J.HANDS_OFF_WINDOW_ANSWERS


def test_the_two_promises_say_what_the_code_does():
    from workflow import measurement_messages as M
    root = Path(__file__).resolve().parents[2]
    prep = M.M_I1IO_DRIVE_PREPARE.render(page=1, pages=2, corner=M._I1IO_CORNER_MARK)[1]
    promise = ("Before the arm moves after any question, ChromIQ asks you to take your hands "
               "away and waits until you confirm it")
    assert promise in " ".join(prep.split())
    log = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    section = log[log.index("## v4.3.45"):]
    section = section[:section.index("\n## v", 5)]
    assert promise in " ".join(section.split())
    assert "ChromIQ asks you before every move that follows a question" not in prep


# ---- the panel: every page a person answers, both modes ----------------------------------------

#: (page, the English label of the button) that ARE the hands-off confirmation
PANEL_HANDS_OFF = {("go", "Go"),
                   ("sheet_laid", "The page is laid, and my hands are away from the table"),
                   ("first_visit", "Make this move, my hands are away"),
                   ("start_up", "Start the table, my hands are away"),
                   ("report_after_step", "As described, my hands are away"),
                   # 4.3.50: the front question, and the homing that is part of the ending
                   ("front_choice", "Go forward carefully, my hands are away"),
                   ("home_at_end", "Bring the arm home, my hands are away")}


def _panel_walk(qtbot, monkeypatch, tmp_path, settings, asking, script=None, sim=None,
                sheet=None, before=None, presentation="panel"):
    from tests.i1io_table.test_window import open_window
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking, sim=sim, sheet=sheet,
                                                    presentation=presentation)
    assert win.presentation == presentation
    # the pop-ups' condition 3: not one movement line while a pop-up is open
    while_open = []
    if presentation == "popups" and getattr(sim, "transport", None) is not None:
        real_write = sim.transport.write

        def write(data, *a, **k):
            was_open = win.popup_open()
            n0 = len(sim.sim.received)
            out = real_write(data, *a, **k)
            if was_open and any(ln[1:3] in MOVES for ln in sim.sim.received[n0:]):
                while_open.append(win.pages_shown[-1:])
            return out
        sim.transport.write = write
    p.script.update({"end_of_session": "Save and stop", "stopped_by_you": "Next step",
                     "stored_white_refused": "Go on"})
    p.script.update(script or {})
    presses = []
    real = p.press

    def press(english):
        page = p.page()
        presses.append((page, english, _motions(sim.sim) if sim.sim is not None else 0))
        real(english)
    p.press = press
    if before is not None:
        before(win, sim, p)
    p.drive_until("done")
    assert while_open == [], while_open
    presses.append(("done", "", _motions(sim.sim)))
    out = []
    for (page, label, n), (_p2, _l2, m) in zip(presses, presses[1:]):
        if m > n and (page, label) not in PANEL_HANDS_OFF:
            out.append((page, label, m - n))
    return out, [pg for pg, _l, _n in presses]


@MODES
def test_the_panel_whole_measurement_cold_table(qtbot, monkeypatch, tmp_path, settings, asking, presentation):
    from tests.i1io_table.window_sim import WindowSim
    bad, pages = _panel_walk(qtbot, monkeypatch, tmp_path, settings, asking,
                             sim=WindowSim(cold=True),
                             presentation=presentation)
    assert bad == [], pages
    assert "start_up" in pages and "sheet_laid" in pages and "home_at_end" in pages
    assert pages.index("sheet_laid") < pages.index("aimed")
    # no GO before the sheet is laid: the sheet-laid answer is the confirmation
    i = pages.index("sheet_laid")
    assert "go" not in pages[max(0, i - 2):i]


@MODES
def test_the_panel_failed_row_skip_and_keep_measuring(qtbot, monkeypatch, tmp_path, settings,
                                                      asking, presentation):
    from tests.i1io_table.window_sim import WindowSim

    def before(win, sim, p):
        p.drive_until("end_of_session")
        p.press("Keep measuring")
    bad, pages = _panel_walk(qtbot, monkeypatch, tmp_path, settings, asking,
                             sheet=small_sheet([4, 4, 4]),
                             sim=WindowSim(faults={"read": {2: "dies_twice"}}),
                             script={"row_failed": "Skip it"}, before=before,
                             presentation=presentation)
    assert bad == [], pages
    assert "row_failed" in pages and pages.count("end_of_session") == 2


def _two_pages() -> dict:
    """Two pages whose patches have their own ids and names (small_sheet(pages=2) repeats
    page 1's, which a measurement file cannot hold)."""
    sheet = small_sheet(pages=2)
    n = sum(len(st["patches"]) for st in sheet["pages"][0]["strips"])
    for st in sheet["pages"][1]["strips"]:
        for q in st["patches"]:
            q["sample_id"] = str(int(q["sample_id"]) + n)
            q["loc"] = "2-" + q["loc"]
    return sheet


@MODES
def test_the_panel_two_pages(qtbot, monkeypatch, tmp_path, settings, asking, presentation):
    bad, pages = _panel_walk(qtbot, monkeypatch, tmp_path, settings, asking,
                             sheet=_two_pages(),
                             presentation=presentation)
    assert bad == [], pages
    assert "next_page" in pages and pages.count("sheet_laid") == 2


@MODES
def test_the_panel_stored_white_refused_and_own_tile(qtbot, monkeypatch, tmp_path, settings,
                                                     asking, presentation):
    from ui import i1io_table_window as W
    from tests.i1io_table.window_sim import WindowSim
    settings.set(W.STORED_WHITE_KEY, True)
    settings.set(W.CAL_KEY, "own tile")
    try:
        bad, pages = _panel_walk(qtbot, monkeypatch, tmp_path, settings, asking,
                                 sim=WindowSim(stored_tile=None),     # no usable values
                                 presentation=presentation)
    finally:
        settings.set(W.STORED_WHITE_KEY, True)
    assert bad == [], pages
    assert "stored_white_refused" in pages and "calibration_reseated" in pages


@MODES
def test_the_panel_stop_at_the_first_rows_go_and_carry_on(qtbot, monkeypatch, tmp_path, settings,
                                                          asking, presentation):
    # 4.3.50: the mark-3 check is gone; the page before the first row's move is its GO
    def before(win, sim, p):
        p.drive_until("rows")
        win._on_stop()                       # the footer's Stop, with the GO on screen
        n = _motions(sim.sim)
        p.press("Go")                        # the stop is honoured at the answer: no move
        assert p.page() == "stopped_by_you" and _motions(sim.sim) == n
    bad, pages = _panel_walk(qtbot, monkeypatch, tmp_path, settings, asking, before=before,
                             presentation=presentation)
    assert bad == [], pages
    i = pages.index("stopped_by_you")
    assert pages[i + 1] == "go"
