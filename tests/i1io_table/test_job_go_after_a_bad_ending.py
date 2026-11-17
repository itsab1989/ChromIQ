"""The safety review of step 7 (REQUIRED): after a step that ended refused or stopped, the
person may have reached onto the bed, so the next moving step waits for a hands-off GO again;
and "again" on a failed row asks GO before the arm moves (the reviewer's recommended variant),
in both modes. A clean page gets no extra question."""
from __future__ import annotations

import collections

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read, small_sheet
from tests.i1io_table.test_job_safety import moves
from workflow.i1io.table import job as J

THREE = [4, 4, 4]


def _next_needs_go(job, sim, step="read_row"):
    n = len(moves(sim.received))
    r = getattr(job, step)()
    assert (r.kind, r.confirm) == (J.Kind.NEEDS, J.Confirm.GO), (r.kind, r.reason, r.confirm)
    assert len(moves(sim.received)) == n and not sim.moving
    back = job.answer(J.Confirm.GO, "back")
    assert back.reason == "person_chose_back" and len(moves(sim.received)) == n
    return n


@pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])
def test_the_reviewers_probe_a_stop_inside_row_1_then_the_next_row_asks_go(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, sheet=small_sheet(THREE), asking=asking)
    ready_to_read(job, p)
    helper.on_read = lambda n: job.stop_at_next_pause() if n == 2 else None
    r = p.drive(job.read_row())
    assert r.reason == "stopped_between_patches"
    helper.on_read = None
    _next_needs_go(job, sim)
    n = len(moves(sim.received))
    assert p.drive(job.read_row()).ok and len(moves(sim.received)) > n     # after a yes


def _stop_mid(job, helper, p):
    helper.on_read = lambda n: job.stop_at_next_pause() if n == 2 else None
    return p.drive(job.read_row())


def _stop_last(job, helper, p):
    helper.on_read = lambda n: job.stop_at_next_pause() if n == 4 else None
    return p.drive(job.read_row())


ENDINGS = {
    # (faults, script, how the row is ended)
    "stop between patches": ({}, {}, _stop_mid),
    "stop during the last patch": ({}, {}, _stop_last),
    "failed row, skip": ({"read": {2: "dies"}}, {J.Confirm.ROW_FAILED: "skip"}, None),
    "failed row, stop": ({"read": {2: "dies"}}, {J.Confirm.ROW_FAILED: "stop"}, None),
    "first visit declined": ({}, {J.Confirm.FIRST_VISIT: "no"}, None),
    "reader cannot open": ({"open": "busy", "open_at": 2}, {}, None),
    "again then back": ({"read": {2: "dies"}}, {J.Confirm.ROW_FAILED: "again"}, "again_back"),
}


@pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])
@pytest.mark.parametrize("name", sorted(ENDINGS))
def test_every_bad_ending_of_a_row_makes_the_next_moving_step_ask_go(tmp_path, name, asking):
    faults, script, how = ENDINGS[name]
    job, sim, helper, run, p = job_for(tmp_path, dict(script), sheet=small_sheet(THREE),
                                       faults=faults, asking=asking)
    ready_to_read(job, p)
    if how == "again_back":
        at = {}

        def on_ask(person, res):
            if res.confirm == J.Confirm.GO and res.detail.get("again"):
                at["moves"] = len(moves(sim.received))
                return person.job.answer(J.Confirm.GO, "back")
            return None
        p.on_ask = on_ask
        r = p.drive(job.read_row())
        p.on_ask = None
        # "again" asked GO before its first move; "back" ended it with nothing moved after
        assert r.reason == "person_chose_back"
        assert len(moves(sim.received)) == at["moves"]
    elif how is not None:
        r = how(job, helper, p)
    else:
        r = p.drive(job.read_row())
    helper.on_read = None
    if job.report_due is not None:
        p.drive(job.answer(J.Confirm.REPORT_AFTER_STEP, "as described"))
    assert job._go_page is None, name
    step = "read_row" if job.rows_left() and not job.only_home else "home"
    _next_needs_go(job, sim, step)


@pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])
def test_again_on_a_failed_row_asks_go_before_the_arm_moves(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, sheet=small_sheet(THREE),
                                       faults={"read": {2: "dies"}}, asking=asking)
    ready_to_read(job, p)
    seen = []

    def on_ask(person, res):
        seen.append((res.confirm, len(moves(sim.received)), sim.moving))
        return None
    p.on_ask = on_ask
    r = p.drive(job.read_row())
    assert r.ok and r.detail["attempts"] == 2
    kinds = [k for k, *_ in seen]
    i = kinds.index(J.Confirm.ROW_FAILED)
    assert kinds[i + 1] == J.Confirm.GO and seen[i + 1][1] == seen[i][1]   # nothing moved between


#: first_visit 3 -> 1 in the owner-results round (S-8): every spot row now starts at column 0,
#: so the move to each row's start runs back over the chart's own rows, already driven
CLEAN = {'aimed': 3, 'arm_felt': 1, 'calibration_place': 1, 'first_visit': 1, 'go': 2,
         'reader_consent': 1, 'ready_to_open': 1, 'sheet_laid': 1}


@pytest.mark.parametrize("asking,reports", [(True, 4), (False, 0)], ids=["asking", "quiet"])
def test_a_clean_page_gets_no_extra_question(tmp_path, asking, reports):
    """The counts measured on 4d4015866 (before this change) for a clean three-row page."""
    job, sim, helper, run, p = job_for(tmp_path, sheet=small_sheet(THREE), asking=asking)
    ready_to_read(job, p)
    read_page(job, p)
    assert p.drive(job.home()).ok
    assert dict(collections.Counter(k for _s, k, *_ in p.asked)) == CLEAN
    assert len(p.reports) == reports


def test_the_harness_default_go_is_yes():
    assert H.DEFAULT[J.Confirm.GO] == "yes"
