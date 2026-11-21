"""WIRE IDENTITY for reading (build step 7): in every reading situation tester 0.6.0 has (its
stages C1 with either white tile, C2, D3, D4, D2 before D3, D3 twice, a reader that cannot start,
a stop between two patches, four fault kinds at every line of the D3 sitting, a cancel at every
line), the job sends the TABLE byte for byte what the tester sends, and starts ChromIQ's reader
with the same arguments over the same row chart.

The tester's side was captured from tester 0.6.0 itself, its own part C and its own
``i1io_reader.SpotReader``, with the same simulated helper process behind it
(``data/tester_060_reading_wire.json``; the capture tool is the step 7 work folder's
``tools/wire_tester7.py``). The one difference in the reader's arguments is the NAME of the row
chart (``-p d3_row1`` in the tester, ``-p p1_row1`` in the job, which reads every page of a
chart): the chart files themselves are compared byte for byte.

C3 and C4 (the recorded i1Profiler row of 14 November) have no situation in the app: the job
reads the person's ChromIQ sheet only."""
from __future__ import annotations

import hashlib
import json

import pytest

from tests.i1io_table import job_reading_wire_cases as W
from tests.i1io_table import must1_wire as M1
from tests.i1io_table.job_harness import HERE



@pytest.fixture(autouse=True)
def _tester_060s_four_f4(monkeypatch):
    """4.3.53 fix round (inventory B15): the job sends two f4 after the aims, as i1Profiler
    does; tester 0.6.0 sent four. For the comparison with the tester's wire the job holds
    the tester's four here (test_4353_fix_round pins the two)."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J, "F4_AFTER_AIMS", 4)

@pytest.fixture(autouse=True)
def _the_testers_serpentine_spot_rows(monkeypatch):
    """Tester 0.6.0's spot stages ran every second row from the other end; the app's spot rows
    start at column 0 on every row since the owner-results round (S-8, as i1Profiler's spot rows
    on the volunteer's table). The frozen sittings are compared in the tester's order; nothing
    else of the job differs."""
    from workflow.i1io.table import spot as sp
    monkeypatch.setattr(sp, "SPOT_ROWS_SERPENTINE", True)

TESTER = json.loads((HERE / "data" / "tester_060_reading_wire.json").read_text(encoding="utf-8"))
CASES = W.cases()
ROW_CHARTS = ("c1_spot", "c2_tile")


def _norm(argvs):
    """The row chart's name is the job's own (page and row); everything else must be equal."""
    return [a[:-1] + ["<row chart>"] if len(a) > 1 and a[-2] == "-p" and a[-1] not in ROW_CHARTS
            else a for a in argvs]


def test_every_captured_sitting_has_a_job_case():
    assert TESTER["tester"] == "chromiq-i1io-session 0.6.0 part C"
    assert set(CASES) == set(TESTER["sittings"])
    assert len(CASES) == 524


def test_the_reader_arguments_are_the_testers_apart_from_the_row_charts_name():
    want = TESTER["sittings"]["D C1 D1 D3 F"]["readers"]
    assert want == [["--json", "-v", "-c", "1", "-p", "c1_spot"],
                    ["--json", "-v", "-c", "1", "-N", "-p", "d3_row1"]]


#: final fix round, S-1: after a white on the instrument's own tile the job reads the table's
#: tile once (at rest, nothing moves) to check the white's level; tester 0.6.0 did not. Those
#: three position readings and that reader are the only difference, and they are checked here.
S1_TILE_LINES = [";p025", ";p025", ";p025"]
S1_TILE_READER = ["--json", "-v", "-c", "1", "-N", "-p", "c2_tile"]


def without_the_s1_tile_reading(got, readers=None, charts=None):
    """The job's wire of an own-tile sitting with S-1's tile reading taken out (asserted to be
    exactly there: after the calibration's two position readings)."""
    k = [i for i, ln in enumerate(got) if ln == ";p025"][1] + 1
    assert got[k:k + 3] == S1_TILE_LINES, got[:k + 4]
    got = got[:k] + got[k + 3:]
    if readers is not None:
        assert readers[1] == S1_TILE_READER, readers
        readers = readers[:1] + readers[2:]
    if charts is not None:
        charts = charts[:1] + charts[2:]
    return got, readers, charts


def _modes(name):
    return [True, False] if not name.startswith(("F ", "G ")) else [True]


@pytest.fixture(autouse=True)
def _homing_as_the_tester_sent_it(monkeypatch):
    """2026-11-21: the vendor's way home (geometry.homing_detour: a detour to the home line from
    the far side and the back strip, i1Profiler's recordings N3 and R1) inserts lines that tester
    0.6.0 never sent, and these cases plant faults at absolute line numbers. Here the homing is
    the tester's, straight; the way home itself is pinned in test_4355_table_without_i1profiler
    and test_job_wire_identity (where the detour lines are taken out and checked)."""
    from workflow.i1io.table import geometry as geo
    monkeypatch.setattr(geo, "homing_detour", lambda p: () if p is not None else None)


@pytest.mark.parametrize("name,asking", [(n, a) for n in sorted(CASES) for a in _modes(n)],
                         ids=lambda v: v if isinstance(v, str) else ("asking" if v else "quiet"))
def test_the_job_reads_as_tester_060_reads(name, asking, tmp_path):
    got, readers, charts, results, sim = W.job_run(CASES[name], tmp_path, asking)
    # 4.3.47 MUST-1: the job's extra position queries after a question, each checked, out
    got = M1.without_must1(got, sim.job)
    want = TESTER["sittings"][name]
    if "own tile" in name:
        got, readers, charts = without_the_s1_tile_reading(got, readers, charts)
    if "sha256" in want:
        assert len(got) == want["n"]
        assert hashlib.sha256("\n".join(got).encode()).hexdigest() == want["sha256"]
    else:
        assert got == want["lines"]
        assert charts == want["charts"]
    assert _norm(readers) == _norm(want["readers"])
    assert sim.violations == []
