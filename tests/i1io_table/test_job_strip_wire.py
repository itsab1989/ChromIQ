"""WIRE IDENTITY for strip rows (round B, build step 10): in every strip situation tester 0.6.0
has (its stages E2 and E3 after C1, D1, D2, with either white tile; six faults of the table-scan
reader: no lamp, not ready, lights-off failing, the trigger never handed over, the reader dying
at the fire, a dark that fails; four fault kinds of the table at every line of the E2 sitting;
a cancel at every line), the job reading the same rows as STRIPS sends the TABLE byte for byte
what the tester sends.

The tester's side was captured from tester 0.6.0 itself (its own part C, its own
``i1io_part_c_sim.FakeScanReader``, its own ``i1io_reader.SpotReader`` with the app's simulated
helper process) into ``data/tester_060_strip_wire.json``; the capture tool is round B's
``tools/wire_tester_b.py``. The job chooses its own speed (54 mm/s for this sheet, the speed
the tester's E2 suggests and its AutoConsole answers)."""
from __future__ import annotations

import hashlib
import json

import pytest

from tests.i1io_table import job_strip_wire_cases as W
from tests.i1io_table.job_harness import HERE
from workflow.i1io.table import job as J

TESTER = json.loads((HERE / "data" / "tester_060_strip_wire.json").read_text(encoding="utf-8"))
CASES = W.cases()


def test_every_captured_sitting_has_a_job_case():
    assert TESTER["tester"] == "chromiq-i1io-session 0.6.0 part C (strip)"
    assert set(CASES) == set(TESTER["sittings"])
    assert len(CASES) == 339


def test_the_whole_sitting_reads_every_strip_row():
    want = TESTER["sittings"]["S C1 D1 D2 E3 F"]
    assert [v for _s, v in want["verdicts"]] == ["worked"] * 5


def _modes(name):
    return [True, False] if not name.startswith(("U ", "V ")) else [True]


@pytest.mark.parametrize("name,asking", [(n, a) for n in sorted(CASES) for a in _modes(n)],
                         ids=lambda v: v if isinstance(v, str) else ("asking" if v else "quiet"))
def test_the_job_reads_strips_as_tester_060_reads(name, asking, tmp_path):
    got, results, sim, helper = W.job_run(CASES[name], tmp_path, asking)
    want = TESTER["sittings"][name]
    if "own tile" in name:
        # final fix round, S-1: the white's level check after an own-tile white
        from tests.i1io_table.test_job_reading_wire import without_the_s1_tile_reading
        got, _r, _c = without_the_s1_tile_reading(got)
    if "sha256" in want:
        assert len(got) == want["n"]
        assert hashlib.sha256("\n".join(got).encode()).hexdigest() == want["sha256"]
    else:
        assert got == want["lines"]
    assert sim.violations == []
    if name in ("S C1 D1 D2 E2 F", "S C1 D1 D2 E3 F"):
        rows = [r for r in results if r.step == "read_row"]
        assert rows and all(r.ok and r.detail.get("row_kind") == "strip"
                            and r.detail.get("status") == "read" for r in rows)
    if name in ("T E2 scan no_lamp", "T E2 scan fire_unsent", "T E2 scan dies_at_fire"):
        stopped = [r for r in results if r.kind == J.Kind.STOPPED]
        assert stopped and stopped[0].reason == "strip_move_may_be_pending"
        assert stopped[0].way_back == J.WayBack.SWITCH_OFF_PENDING
