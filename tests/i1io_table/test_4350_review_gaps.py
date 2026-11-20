"""4.3.50: the test gaps the 4.3.49 table reviews left open ("another guard behind it"), each
proved by planting the fault in a scratch copy (work folder 2026-11-19_table450, plants.txt).

Re-review 449, S-1: the way back before the homing (job._way_back) had no test that a plant of
P6 (the 4-move bound off), P7 (``arrived`` not cleared at a homing), P8 (a jump back without the
driven-ground test) or P9 (the way back inside the homing after a stop) turned red; nor the
geometry's own back-strip refusal (safety review 449, G2 / SHOULD-6). S-2 (the first leg back
along the way by construction) and S-3 (a way back never ends in front of Y 3109) are fixed
here, with their tests.

4.3.52 (the owner's ruling of 2026-11-20): the way back is GONE. i1Profiler homes a held arm
directly from where it stands; the move back along the way the arm came was our own invention,
and no recording or report shows harm from a direct homing. So P6-P9, S-2 and S-3 are moot (there
is no way back to bound); what they protected (no move into ground never driven before the
homing) is now: no move at all before the homing (test_4349_fix_way_back_before_the_homing.py,
"the homing goes straight home").
"""
from __future__ import annotations

import inspect

import pytest

from tests.i1io_table.test_4349_fix_way_back_before_the_homing import _stalled
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J


def test_after_a_homing_nothing_of_the_sitting_counts_as_arrived(tmp_path):
    """Plant P7 (``arrived`` not cleared at a homing) turned nothing red in 4.3.49; ``arrived``
    still feeds the reach, so it is still cleared."""
    job, sim, p, _d = _stalled(tmp_path)
    assert job.arrived
    assert p.drive(job.home()).kind == J.Kind.OK
    assert job.arrived == []


def test_no_homing_moves_anything_before_its_i1():
    """4.3.52: the usual homing sends s0 p0, then its i1, with no move between (the way back of
    4.3.49-4.3.51 is gone from the source)."""
    src = inspect.getsource(J.TableJob._end_of_job)
    assert "_way_back" not in src and "_go_back" not in src and "m0_line" not in src
    assert not hasattr(J.TableJob, "_way_back") and not hasattr(J.TableJob, "_go_back")


def test_the_geometry_refuses_a_computed_move_from_the_back_strip():
    """Safety review 449, G2: the geometry's own copy of the back-strip refusal (the table's
    gate holds one too; with only this one off, nothing turned red)."""
    with pytest.raises(geo.AreaRefused, match="back strip"):
        geo.check_move_from_reading((1102, 15), (1000, 1500), "a move")
    with pytest.raises(geo.AreaRefused, match="back strip"):
        geo.check_move_from_reading((1000, geo.AREA_RAW.ymin - 1), (1000, 1500), "a move")
    geo.check_move_from_reading((1000, geo.AREA_RAW.ymin), (1000, 1500), "a move")
