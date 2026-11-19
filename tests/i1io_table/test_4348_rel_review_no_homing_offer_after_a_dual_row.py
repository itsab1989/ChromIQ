"""4.3.48 release review (the merge of the dual scan and the table's homing after a stop).

Nobody had pinned what the homing offer does after a stop DURING a dual row: its UV pass may
leave a scan move waiting for a light that never came (the table then holds an m2 it has not
run). ChromIQ must then offer NO homing of its own (only the switch-off way), send nothing more,
and leave no dual phase set behind; and a person's Stop between the lamp and the UV pass ends
the row without the offer as well (things have moved in this sitting).
"""
from __future__ import annotations

from tests.i1io_table.test_dual_table import _job, _ready
from workflow.i1io.table import job as J


def _no_offer_and_nothing_sent(job, sim):
    n = len(sim.received)
    assert job.way_back() != J.WayBack.HOME_AFTER_STOP
    r = job.home_after_stop()
    assert r.kind == J.Kind.REFUSED, (r.kind, r.reason)
    assert job._after_end().get("next", []) == [] or "home_after_stop" not in job._after_end()["next"]
    assert len(sim.received) == n
    return r


def test_a_uv_pass_whose_light_never_came_offers_no_homing(tmp_path):
    """The UV LED does not light: the UV pass's scan move waits for it (pending). The way back
    is the switch-off one, ChromIQ's own homing is refused, nothing more is sent, and the dual
    phase is cleared."""
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"no_uv": True}})
    _ready(job, p)
    r = p.drive(job.read_row())
    assert not r.ok
    assert r.way_back in (J.WayBack.SWITCH_OFF_PENDING, J.WayBack.LINK_LOST_SWITCH_OFF_FIRST), \
        r.way_back
    assert job._table.dual_phase is None
    got = _no_offer_and_nothing_sent(job, sim)
    assert got.reason in ("movement_may_be_unfinished", "moved_in_this_sitting"), got.reason


def test_a_stop_between_the_lamp_and_the_uv_pass_offers_no_homing(tmp_path):
    """The person's Stop during the lamp pass is honoured before the UV pass; the arm has moved
    in this sitting, so ChromIQ does not offer its own homing after it."""
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    import workflow.i1io.table.scan as scm
    real = scm.run_row

    def stop_in_the_lamp_pass(table, *a, **k):
        if not k.get("uv_pass"):
            job.stop_at_next_pause()
        return real(table, *a, **k)
    scm.run_row = stop_in_the_lamp_pass
    try:
        r = p.drive(job.read_row())
    finally:
        scm.run_row = real
    assert r.reason == "stopped_before_the_uv_pass", (r.kind, r.reason)
    assert job._table.dual_phase is None
    _no_offer_and_nothing_sent(job, sim)
    assert job._home_after_stop_why() is not None
