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
from tests.i1io_table.job_harness import HERE


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


def _modes(name):
    return [True, False] if not name.startswith(("F ", "G ")) else [True]


@pytest.mark.parametrize("name,asking", [(n, a) for n in sorted(CASES) for a in _modes(n)],
                         ids=lambda v: v if isinstance(v, str) else ("asking" if v else "quiet"))
def test_the_job_reads_as_tester_060_reads(name, asking, tmp_path):
    got, readers, charts, results, sim = W.job_run(CASES[name], tmp_path, asking)
    want = TESTER["sittings"][name]
    if "sha256" in want:
        assert len(got) == want["n"]
        assert hashlib.sha256("\n".join(got).encode()).hexdigest() == want["sha256"]
    else:
        assert got == want["lines"]
        assert charts == want["charts"]
    assert _norm(readers) == _norm(want["readers"])
    assert sim.violations == []
