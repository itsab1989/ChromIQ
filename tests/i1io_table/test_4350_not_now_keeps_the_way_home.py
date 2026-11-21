"""4.3.50 fix round, MUST-1 (independent review of 20 Nov 2026): "LEAVE IT THERE" BROUGHT BACK THE
REFUSED START, and no page said so.

Shown on screen by the reviewer: Save, "Leave it there", a new START with "The arm is out": the
arm was still held out over the sheet with the table in its aiming mode (f1 sent, no f0: f0 is
recorded only after a homing), the START was refused after eight lines, the done page promised
an i1Profiler homing from a place no recording shows, and the refusal blamed "an earlier
measurement stopped while the arm was free" and offered to save readings that did not exist.

Now:
* the second answer at the homing of the ending is "Not now": nothing is sent, and the homing's
  hands-off question stays OPEN, so "Bring the arm home, my hands are away" is still offered on
  the next page while this window is open (only this measurement knows the way back); Close
  there (or End measurement, or the window's close) ends the connection;
* the homing page says, in two short sentences, what happens if the arm does not go home now;
* the last page after Close says what is true (the table stays in its aiming mode; no START
  until the arm is home; no recorded homing from that place; how a just switched-on table is
  started), never "it brings the arm home";
* the next START's refusal names its real cause and offers no readings that do not exist;
* f0 is never sent with the arm out: on every path here it follows a homing (i1), or it is not
  sent at all.
"""
from __future__ import annotations

from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow import measurement_messages as M

MOVES = ("m0", "m1", "m2", "i0", "i1")
BRING = "Bring the arm home, my hands are away"
#: where the reviewer's run left the arm (his sheet, his aims): held, in front of every recorded
#: homing start
HELD_OUT = (-1286.0, 3274.0)


def _cids(sim, since=0):
    return [ln[1:3] for ln in sim.sim.received[since:]]


def _f0_only_after_a_homing(cids):
    """Every f0 follows an i1 with nothing that moves between them."""
    for i, c in enumerate(cids):
        if c != "f0":
            continue
        before = [x for x in cids[:i] if x in MOVES]
        assert before and before[-1] == "i1", cids[max(0, i - 8):i + 1]


def _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert p.page() == "home_at_end"
    return win, sim, p, finished


def test_the_homing_page_says_what_not_now_means(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, p, _f = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    assert p.labels() == [tr("Not now"), tr(BRING)]
    text = win._text.text()
    assert tr("If the arm does not go home now, the table stays in its aiming mode.") in text \
        or "stays in its aiming mode" in text
    # 2026-11-21: no longer a lock-out: the next START brings the arm home first
    assert "which brings the arm home first" in text
    assert "Leave it there" not in text and "it should move the arm" not in text
    assert "—" not in M.M_I1IO_DRIVE_HOME_AT_END.body + M.M_I1IO_DRIVE_HOME_NOT_NOW.body


def test_not_now_sends_nothing_keeps_the_question_open_and_the_homing_is_still_offered(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, p, _f = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    n = len(sim.sim.received)
    p.press("Not now")
    assert p.page() == "home_not_now"
    assert sim.sim.received[n:] == []
    job = sim.jobs[0]
    # the job still holds the table and its hands-off question is still the one asked
    assert job.phase == "open" and job._pending is not None and job._pending.kind == "go"
    assert p.labels() == [tr("Close"), tr(BRING)]
    title, _b = M.M_I1IO_DRIVE_HOME_NOT_NOW.render()
    assert win._title.text() == tr(title)
    text = win._text.text()
    assert "From this window" in text and "Nothing has moved" in text
    qtbot.wait(150)
    assert sim.sim.received[n:] == []
    # the person comes back and takes it: the usual homing, at rest, f0 after the homing
    p.press(BRING)
    assert p.page() == "done", (p.page(), win._text.text()[:200])
    assert job.at_rest() and sim.sim.violations == []
    cids = _cids(sim, n)
    assert "i1" in cids and "f0" in cids
    _f0_only_after_a_homing(_cids(sim))


def test_not_now_then_close_ends_the_connection_and_the_last_page_is_true(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, p, finished = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    n = len(sim.sim.received)
    p.press("Not now")
    p.press("Close")
    assert p.page() == "done"
    assert sim.sim.received[n:] == []                 # nothing at all, f0 above all
    assert "f0" not in _cids(sim)
    job = sim.jobs[0]
    assert job.phase == "closed" and job.state().mode_on
    text = win._text.text()
    left = M.M_I1IO_DRIVE_LEFT_OUT.render()[1]
    assert tr(left) in text
    assert "it brings the arm home" not in text
    assert "you can still save them" not in text
    # 2026-11-21: the next START puts it right; no i1Profiler
    assert "next time you press START MEASUREMENT" in text and "i1Profiler" not in text


def test_end_measurement_on_the_not_now_page_also_lets_go_and_says_the_same(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, p, finished = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    n = len(sim.sim.received)
    p.press("Not now")
    win._on_end_pressed()
    p.idle()
    assert p.page() == "done" and sim.sim.received[n:] == []
    assert tr(M.M_I1IO_DRIVE_LEFT_OUT.render()[1]) in win._text.text()


def test_the_job_notes_that_the_table_is_left_in_its_aiming_mode(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, p, finished = _to_the_homing_of_the_ending(qtbot, monkeypatch, tmp_path, settings)
    p.press("Not now")
    p.press("Close")
    log = (sim.jobs[0].diag.folder / "session.log").read_text(encoding="utf-8")
    assert "home_at_end -> not now" in log
    assert "the table is left in its aiming mode" in log


class _LeftOutSim(WindowSim):
    """The table as the reviewer's run left it: warm, the arm held out, the aiming mode on."""

    def factory(self, *a, **k):
        job = super().factory(*a, **k)
        self.sim.pos, self.sim.mode, self.sim.free_arm = list(HELD_OUT), "01", False
        return job


def test_a_new_start_after_not_now_and_close_says_its_real_cause_and_moves_nothing(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """2026-11-21 (the owner: "driving the table should work without involving i1profiler"):
    the next START finds the aiming mode left on and puts it right itself, after its question:
    i1Profiler's end of a job, as i1Profiler does with such a table (the table owner's recording
    N1 of 21 Nov 2026). Before the question nothing moves and nothing is read."""
    sim = _LeftOutSim()
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, asking=False)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    win._tick_widgets[1].setChecked(True)            # only the bed: the arm is out
    p.press("The arm is out")
    page = p.drive_until(("repair_at_start", "stopped", "refused", "done"))
    assert page == "repair_at_start", page
    assert [c for c in _cids(sim)] == ["a1", "a1", "k2", "u8", "u8", "a0", "s0", "f4", "f4",
                                       "f4", "f4"]
    title, _body = M.M_I1IO_DRIVE_REPAIR_AT_START.render()
    assert win._title.text() == tr(title)
    assert p.labels() == [tr("Not now"), tr(BRING)]
    assert "i1Profiler" not in win._text.text()
    n = len(sim.sim.received)
    p.press(BRING)
    p.idle()
    assert _cids(sim, n) == ["s0", "p0", "i1", "s0", "f0", "f4", "f4", "p0"]
    job = sim.jobs[-1]
    assert job.at_rest() and not job.state().mode_on and sim.sim.violations == []
    _f0_only_after_a_homing(_cids(sim))


def test_the_same_with_the_answer_that_the_arm_is_at_rest(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    sim = _LeftOutSim()
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, asking=False)
    page = p.drive_until(("repair_at_start", "stopped", "refused", "done"))
    assert page == "repair_at_start" and not [c for c in _cids(sim) if c in MOVES]
    assert "still in its aiming mode" in win._text.text()


def test_a_stop_at_the_opening_never_offers_readings_that_do_not_exist(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """2026-11-21 fix round (B-1): four mode answers that differ among themselves (a0 and f4
    that disagree are put right at START). Nothing was read, nothing moves; the way on is inside
    ChromIQ, and the page says plainly that ChromIQ does not know this state."""
    sim = WindowSim(table_faults=[("free", "f4")])
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, asking=False)
    page = p.drive_until(("stopped", "refused", "done"))
    assert page == "stopped"
    text = win._text.text()
    assert "Nothing was read" in text and "you can still save them" not in text
    assert "does not know this state" in text and "i1Profiler" not in text
    assert not [c for c in _cids(sim) if c in MOVES]


def test_the_reason_sentences_are_true():
    still = W.reason_text("mode_flag_unexpected", {"mode_answer": "01", "mode_expected": "00",
                                                   "at_opening": True})
    assert "while the arm was free" not in still and "still in its aiming mode" in still
    state = W.table_state_text("120000")
    assert "moved by hand" not in state and "i1Profiler" not in state
