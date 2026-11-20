"""4.3.52 fix round, the independent safety review's S-3 and S-4
(~/Desktop/ChromIQ-work/2026-11-20_subopt452_review/review_subopt452.txt).

S-3: the exact list of questions answered by the setting is pinned, and every question kind has
its fate decided (BY_SETTING, COUNTDOWN_INSTEAD, SKIPPED, ALWAYS_ASKED): adding a question kind
without deciding its fate fails a test.
S-4: the three guards the review broke without any test noticing (plants P03, P06, P13)."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4352_guidance_off import _moves, _unguided_job
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from workflow.i1io.table import job as J

C = J.Confirm


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    J.HANDS_OFF_BREACHES.clear()


# ---- S-3: the exact lists ------------------------------------------------------------------

def _kinds():
    return {v for k, v in vars(J.Confirm).items() if k.isupper() and isinstance(v, str)}


def test_s3_the_questions_answered_by_the_setting_are_exactly_these():
    assert J.BY_SETTING == {C.READY_TO_OPEN: "yes", C.SHEET_LAID: "yes",
                            C.FRONT_CHOICE: "go on", C.FIRST_VISIT: "yes",
                            C.READER_CONSENT: "yes", C.END: "save"}
    # 4.3.52 (the owner's ruling of 2026-11-20): the start-up of a just-switched-on table is
    # sent wherever the arm is, so with the guidance off it comes after the countdown
    assert J.COUNTDOWN_INSTEAD == frozenset({C.GO, C.START_UP})
    assert J.SKIPPED == frozenset({C.ARM_FELT, C.REPORT_AFTER_STEP})
    assert J.COUNTDOWN_AFTER == frozenset({C.SHEET_LAID, C.FRONT_CHOICE})
    assert J.TableJob.AUTO_KINDS == frozenset(J.BY_SETTING)


def test_s3_every_question_kind_has_its_fate_decided():
    """A new question kind must be put into exactly one list before this passes: answered by
    the setting, a countdown instead, skipped, or always asked."""
    lists = [set(J.BY_SETTING), set(J.COUNTDOWN_INSTEAD), set(J.SKIPPED), set(J.ALWAYS_ASKED)]
    union = set().union(*lists)
    assert union == _kinds(), (sorted(_kinds() - union), sorted(union - _kinds()))
    assert sum(len(x) for x in lists) == len(union), "a kind is in two lists"


def test_s3_a_kind_always_asked_is_asked_with_the_guidance_off(tmp_path):
    job, sim, person = _unguided_job(tmp_path)
    for kind in J.ALWAYS_ASKED:
        assert job._without_the_person(J.Ask(kind, {})) is None, kind


# ---- S-4: the three guards the review broke without a test noticing ---------------------------

@pytest.mark.parametrize("detail", [{"step": "home_after_stop"}, {"step": "home", "at_start": True},
                                    {"step": "home_after_stop", "at_start": True}])
def test_s4_p03_the_homing_offers_stay_questions_with_the_guidance_off(tmp_path, detail):
    """P03: the homing offered after a Stop and the START rule's offer are never a countdown,
    even in a sitting that has had no trouble yet."""
    job, sim, person = _unguided_job(tmp_path)
    assert job.turned_guided is None
    assert job._without_the_person(J.Ask(C.GO, dict(detail))) is None


def test_s4_p03_the_homing_of_an_incomplete_ending_stays_a_question(tmp_path):
    job, sim, person = _unguided_job(tmp_path)
    job.ended = "saved"
    job._end_state_seen = {"state": "partial"}
    assert job._without_the_person(J.Ask(C.GO, {"step": "home"})) is None
    job._end_state_seen = {"state": "complete"}
    assert job._without_the_person(J.Ask(C.GO, {"step": "home"})) == "countdown"


def test_s4_p06_a_stale_stop_is_honoured_before_an_automatic_answer(tmp_path, monkeypatch):
    """P06: a stop waiting (``_pause_stop``) when the job is about to answer a question itself
    ends the step there, before the move the answer would allow. Since MUST-1 a Stop also turns
    the sitting guided, so this guard is the second line; it is pinned here on its own: the stop
    arrives exactly between the policy's "auto" and the answer (the rest of stop_at_next_pause
    left out)."""
    job, sim, person = _unguided_job(tmp_path)
    assert person.drive(job.open()).ok and person.drive(job.calibrate()).ok
    n = _moves(sim.received)
    real_policy, real_auto = J.TableJob._without_the_person, J.TableJob._auto_answer
    seen = []

    def policy(self, ask):
        how = real_policy(self, ask)
        if how == "auto" and ask.kind == C.SHEET_LAID and not seen:
            seen.append("stop")
            self._pause_stop = True
        return how

    def auto(self, step, ask):
        seen.append(ask.kind)
        return real_auto(self, step, ask)
    monkeypatch.setattr(J.TableJob, "_without_the_person", policy)
    monkeypatch.setattr(J.TableJob, "_auto_answer", auto)
    res = job.align()
    assert seen == ["stop"], seen
    assert res.kind in (J.Kind.REFUSED, J.Kind.STOPPED), res
    assert res.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE, res
    assert _moves(sim.received) == n


def test_s4_p13_the_rows_line_is_not_retired_after_a_stop_or_a_problem(qtbot, monkeypatch,
                                                                       tmp_path, settings):
    win, sim, run, p, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, guided=False,
                                       args=["-v", "-c", "1", "-S", "chart"])
    p.script.update({"aimed": "Aimed", "done": "Close"})
    for _ in range(100):
        if p.page() == "done":
            break
        p.answer_page(p.page())
    job = sim.jobs[0]
    assert job.rows_sitting_completed()
    for flag, value in (("stop_pressed", True), ("problems", [("wrong", None, 0)]),
                        ("stopped_by_person", True)):
        before = getattr(job, flag)
        setattr(job, flag, value)
        assert not job.rows_sitting_completed(), flag
        setattr(job, flag, before)
    assert job.rows_sitting_completed()
