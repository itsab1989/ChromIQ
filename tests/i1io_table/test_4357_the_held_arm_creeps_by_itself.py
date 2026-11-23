"""4.3.57 (item 21): two 0.5 mm limits replaced by one with a measured reason.

The table owner's 4.3.56 runs of 22 Nov 2026 were stopped twice by a 5 unit (0.5 mm) limit:

* "arm moved before homing": the held arm, left out at (-1268, 2847), read (-1260, 2850) when he
  answered the START homing question 208 s later; the homing was not sent;
* row 2 at 168 mm/s ended at (-1460, 2505) for a planned (-1466, 2506): stopped "after doubt".

His held arm moves BY ITSELF up to 13 units with nothing sent (``tbl.HELD_ARM_CREEP_UNITS``,
measured), so both were false alarms. The limit is now ``tbl.HELD_ARM_MOVED_UNITS`` (30 units,
more than twice the largest creep, under half the smallest patch pitch). Beyond it, before a
START homing: read again and ASK AGAIN (nothing moves); at a row's end: read once more 0.3 s
later; only then the old doubt.
"""
from __future__ import annotations

from tests.i1io_table.test_job_reading import job_for, ready_to_read
from tests.i1io_table.test_roundB_strip import _job, _ready
from tests.i1io_table.test_window import settings  # noqa: F401 - fixture
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

C = J.Confirm


def test_the_limit_has_its_measured_reason():
    assert tbl.HELD_ARM_CREEP_UNITS == 13
    assert tbl.HELD_ARM_MOVED_UNITS >= 2 * tbl.HELD_ARM_CREEP_UNITS
    assert tbl.HELD_ARM_MOVED_UNITS < 40          # half of the 8 mm row pitch, in 0.1 mm


def _start_homing_with(tmp_path, moves, guided=True):
    """The arm found out at a START; *moves*: what the hand does at each GO (dx, dy) units."""
    asks = []
    left = list(moves)

    def on_ask(person, res):
        if res.confirm == C.GO and res.detail.get("step") == "home_at_start":
            asks.append(dict(res.detail))
            if left:
                dx, dy = left.pop(0)
                person.sim.pos = [person.sim.pos[0] + dx, person.sim.pos[1] + dy]
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    p.on_ask = on_ask
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.calibrate())
    return job, sim, r, asks, sim.received[n:]


def test_the_owners_208_second_creep_is_homed_without_a_second_question(tmp_path):
    # (-1268, 2847) -> (-1260, 2850): 8 and 3 units
    job, sim, r, asks, sent = _start_homing_with(tmp_path, [(8, 3)])
    assert r.ok, (r.kind, r.reason)
    assert len(asks) == 1
    assert ";i12b" in sent and sim.violations == []
    assert any("crept from" in ln and "its own creep" in ln for ln in job.diag.lines)


def test_a_creep_at_the_limit_is_homed_and_one_unit_beyond_asks_again(tmp_path):
    lim = tbl.HELD_ARM_MOVED_UNITS
    job, sim, r, asks, sent = _start_homing_with(tmp_path, [(lim, -lim)])
    assert r.ok and len(asks) == 1
    job, sim, r, asks, sent = _start_homing_with(tmp_path / "b", [(0, lim + 1), (0, 0)])
    assert r.ok and len(asks) == 2
    assert asks[1]["moved_while_asked"] and asks[1]["moved_mm"] == round((lim + 1) / 10, 1)
    # between the two questions only the status and one reading: nothing that moves
    # the reading that found the arm out, the first try (s0 p0: moved), the second (s0 p0),
    # then the homing: nothing that moves before it
    assert sent[:sent.index(";i12b")] == [";p025", ";s022", ";p025", ";s022", ";p025"]


def test_an_arm_that_keeps_moving_ends_as_before_after_the_last_question(tmp_path):
    job, sim, r, asks, sent = _start_homing_with(
        tmp_path, [(0, -100)] * (J.MOVED_ASK_AGAIN_MAX + 1))
    assert r.kind == J.Kind.STOPPED and r.reason == "arm_moved_before_homing"
    assert len(asks) == J.MOVED_ASK_AGAIN_MAX + 1
    assert ";i12b" not in sent and job.start_homing_failed


def test_with_the_guidance_off_the_question_after_a_move_is_asked_not_counted_down(tmp_path):
    asks = []
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    job.guided = False
    from ui import i1io_table_window as W
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    moved = []

    def progress(ev):
        # the hand pushes the arm 10 mm during the START homing's countdown
        if ev.get("event") == "countdown" and ev.get("for_step") == "home_at_start" \
                and not moved:
            moved.append(1)
            sim.pos = [sim.pos[0], sim.pos[1] - 100.0]
    job.on_progress = progress

    def on_ask(person, res):
        if res.confirm == C.GO and res.detail.get("step") == "home_at_start":
            asks.append(dict(res.detail))
    p.on_ask = on_ask
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate())
    assert r.ok, (r.kind, r.reason)
    assert moved, "the countdown before the START homing ran"
    # the move made the rest of the sitting guided, so the second question was ASKED
    assert job.turned_guided and "moved" in job.turned_guided
    assert len(asks) == 1 and asks[0]["moved_while_asked"]


# ---- the row end ----------------------------------------------------------------------------
def test_the_owners_row_ending_six_units_short_stands(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    sim.c_faults["scan_end_off"] = 6
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", (r.kind, r.reason, r.detail)
    assert job._table.closed_reason is None


def test_a_row_end_beyond_the_limit_is_read_again_and_stands_when_it_settled(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    sim.c_faults["scan_end_off"] = 40
    sim.c_faults["scan_end_settle"] = 4
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok, (r.kind, r.reason, r.detail)
    after_m2 = sim.received[n:]
    k = next(i for i, ln in enumerate(after_m2) if ln.startswith(";m2"))
    assert after_m2[k + 1:].count(";p025") >= 2


def test_a_row_end_still_beyond_the_limit_after_the_second_reading_is_a_doubt(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    sim.c_faults["scan_end_off"] = 40
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.STOPPED, (r.kind, r.reason)
    assert job._table.closed_reason and "not at the row end" in job._table.closed_reason


# ---- the page --------------------------------------------------------------------------------
def test_the_asked_again_page_says_how_far_the_arm_moved_above_the_question():
    from core.i18n import tr
    from ui.i1io_table_window import TableMeasureWindow
    from workflow import measurement_messages as M
    title, body = TableMeasureWindow._moved_ask_again({"moved_mm": 3.1}, "QUESTION")
    assert title == tr(M.M_I1IO_DRIVE_ARM_MOVED_ASK_AGAIN.title)
    assert "3.1 mm" in body and body.endswith("\n\nQUESTION")


def test_every_text_of_a_page_can_be_selected_and_copied(qtbot, monkeypatch, tmp_path, settings):
    from PyQt6.QtCore import Qt
    from tests.i1io_table.test_window import open_window
    win, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, asking=False)
    for lab in (win._title, win._text, win._state, win._status):
        assert lab.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse, \
            lab.objectName()


# ---- fix round (review F2): "Not now" to the question asked AGAIN ---------------------------
def _decline_the_second_question(tmp_path):
    """The arm found out at a START, the hand moves it 10 mm during the first question, and
    the person answers the question asked again with "Not now"."""
    asks = []

    def on_ask(person, res):
        if res.confirm == C.GO and res.detail.get("step") == "home_at_start":
            asks.append(dict(res.detail))
            if len(asks) == 1:
                person.sim.pos = [person.sim.pos[0], person.sim.pos[1] - 100.0]
                person.script[C.GO] = "yes"
            else:
                person.script[C.GO] = "back"    # "Not now"
    job, sim, helper, run, p = job_for(tmp_path, real_table=False)
    p.on_ask = on_ask
    sim.pos = [800.0, 800.0]
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.calibrate())
    return job, sim, r, asks, sim.received[n:]


def test_not_now_to_the_question_asked_again_is_no_failed_homing(tmp_path):
    """MUTATION: drop the `declined` guard in `_start_homing` and the flag is set."""
    job, sim, r, asks, sent = _decline_the_second_question(tmp_path)
    assert len(asks) == 2 and asks[1]["moved_while_asked"]
    assert r.reason == "person_chose_back", (r.kind, r.reason)   # a clean stop, as a first "no"
    assert ";i12b" not in sent and sim.violations == []
    assert job.start_homing_failed is False      # the same as a "no" to the first question


def test_a_later_stop_after_not_now_does_not_claim_the_homing_failed(
        qtbot, monkeypatch, tmp_path, settings):
    """The window shows "the homing did not bring the arm home" (M_I1IO_DRIVE_HOME_TRY_FAILED)
    for a stop whose reason is not the person's own while ``start_homing_failed`` is set. After
    "Not now" to the question asked again, a later stop for another reason (here a row end
    found off) must get its own page. The control: with the flag set, that page shows."""
    from tests.i1io_table.test_window import open_window
    from types import SimpleNamespace
    from core.i18n import tr
    from workflow import measurement_messages as M
    job, *_ = _decline_the_second_question(tmp_path / "job")
    win, *_ = open_window(qtbot, monkeypatch, tmp_path / "win", settings, asking=False)
    failed_title = tr(M.M_I1IO_DRIVE_HOME_TRY_FAILED.title)

    class _Shown(Exception):
        pass

    def first_page(job_now):
        shown = []

        def show(_kind, title, *_a, **_k):
            shown.append(title)
            raise _Shown
        monkeypatch.setattr(win, "_show", show)
        monkeypatch.setattr(win, "job", job_now)
        res = SimpleNamespace(way_back=None, step="read_row", reason="after_doubt",
                              detail={}, kind=J.Kind.STOPPED)
        try:
            win._on_stopped(res)
        except _Shown:
            pass
        return shown[0] if shown else None

    assert first_page(job) != failed_title
    job.start_homing_failed = True               # the control: the page that must not show
    assert first_page(job) == failed_title


def test_not_now_to_the_question_asked_again_after_a_stop_is_no_failed_homing(tmp_path):
    """The same at the second place: the homing offered after a stop (HOME_AFTER_STOP). The
    sending closes again (it was opened for the homing's lines only), with the person's
    reason, and the flag stays off. MUTATION: drop the `declined` guard in
    `_home_after_stop` and the flag is set."""
    from tests.i1io_table.test_4348_the_arm_home_without_i1profiler import (
        OUT_HELD, _stopped_at_the_homing)
    job, sim, p, r = _stopped_at_the_homing(tmp_path, OUT_HELD)
    asks = []

    def on_ask(person, res):
        if res.confirm == C.GO and res.detail.get("step") == "home_after_stop":
            asks.append(dict(res.detail))
            if len(asks) == 1:
                person.sim.pos = [person.sim.pos[0], person.sim.pos[1] - 100.0]
                person.script[C.GO] = "yes"
            else:
                person.script[C.GO] = "back"     # "Not now"
    p.on_ask = on_ask
    n = len(sim.received)
    res = p.drive(job.home_after_stop())
    assert len(asks) == 2 and asks[1]["moved_while_asked"]
    assert res.reason == "person_chose_back", (res.kind, res.reason)
    assert ";i12b" not in sim.received[n:] and sim.violations == []
    assert job.start_homing_failed is False
    assert job._table.closed_reason is not None
