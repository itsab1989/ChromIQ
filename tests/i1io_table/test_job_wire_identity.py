"""WIRE IDENTITY: for every stage the tester has (open, start-up, park inside the way out, the
alignment, the creep, the check move, the homing, the close), the table job sends byte for byte
what tester 0.6.0's part C sends in the same situation.

The tester's lines were captured from tester 0.6.0 itself on its own simulator
(``data/tester_060_part_c_wire.json``; the capture tool is in the step 6 work folder), for 285
sittings: the warm and the cold table, two recorded i1Profiler alignments with the creep and
with "back", nine wrong alignments, four fault kinds at every line of the warm sitting, and a
cancel (the tester's Ctrl-C) at every line. The job runs the same sittings here, on the app's
copy of the simulator."""
from __future__ import annotations

import hashlib
import json

import pytest

from tests.i1io_table import job_wire_cases as W
from tests.i1io_table.job_harness import HERE

TESTER = json.loads((HERE / "data" / "tester_060_part_c_wire.json").read_text(encoding="utf-8"))
CASES = W.cases()


def test_every_captured_sitting_has_a_job_case():
    assert set(CASES) == set(TESTER["sittings"])
    assert len(CASES) == 285


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_job_sends_what_tester_060_sends(name):
    got, results, sim = W.job_lines(CASES[name])
    want = TESTER["sittings"][name]
    if isinstance(want, list):
        assert got == want
    else:
        assert len(got) == want["lines"]
        assert hashlib.sha256("\n".join(got).encode()).hexdigest() == want["sha256"]
    assert sim.violations == []
