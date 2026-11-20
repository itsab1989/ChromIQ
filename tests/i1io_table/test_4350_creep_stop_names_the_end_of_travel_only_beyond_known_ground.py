"""4.3.50 fix round (independent review of 20 Nov 2026, SHOULD-4): the page after a careful 5 mm
step towards the front ended badly says "Most likely the arm met the end of its travel there"
only when the step went beyond the ground the arm is known to have reached (the recordings'
front, Y 2773, this table's remembered reach, this measurement). The review's status-quiet run
had a status on the FIRST step, to Y 2773, ground driven before: the end of travel cannot be the
cause there, and the page now says so."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4350_front_stop_pages import _creep_with_fault, _page, DETAIL
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J


@pytest.mark.parametrize("nth,beyond", [(1, False), (3, True)])
def test_the_step_knows_whether_it_went_beyond_known_ground(tmp_path, monkeypatch, nth, beyond):
    import tests.i1io_table.test_4350_front_stop_pages as F
    real = F._arm_fault_in_creep_step
    monkeypatch.setattr(F, "_arm_fault_in_creep_step",
                        lambda sim, job_of, kind, nth_=2: real(sim, job_of, kind, nth=nth))
    out, job, sim, p, seen = _creep_with_fault(tmp_path, "status")
    step, k, reason, detail = out[-1]
    assert (step, k, reason) == ("creep", J.Kind.STOPPED, "table_answered_a_status"), out[-1]
    assert (detail["creep_to"][1] > geo.FRONTMOST_Y_REACHED) is beyond
    assert detail["beyond_known_front"] is beyond


@pytest.mark.parametrize("beyond", [True, False])
def test_the_page_names_the_end_of_travel_only_beyond_known_ground(beyond):
    for rid in ("table_answered_a_status", "table_refused_a_line", "table_did_not_answer"):
        _t, body = _page(dict(DETAIL, creep_stop=rid, beyond_known_front=beyond), rid)
        assert ("end of its range of movement there" in body
                or "at the end of its range of movement" in body) is (
            beyond), (rid, beyond)
        if not beyond and rid == "table_answered_a_status":
            assert "has reached this place before" in body
