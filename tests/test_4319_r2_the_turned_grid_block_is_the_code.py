"""Review 4.3.19 r2, SF-B: the §M-PROPOSED block of M-IMPORT-TURNED-GRID is
what the app shows, fragment for fragment.

r1 changed two fragments in `workflow/measurement_messages.py` ("rows on its
first page: {got_rows}") and left §M quoting the old wording ("with
{got_rows} rows on its first page"), so the text up for approval was not the
text in the release. `test_message_catalogue.py` compares headlines, not
bodies, so nothing noticed.
"""
from __future__ import annotations

from pathlib import Path

from workflow import measurement_messages as M

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/design/unified_measurement_management.md"


def _quoted_block(mid: str) -> "list[str]":
    text = SPEC.read_text(encoding="utf-8")
    start = text.index(f"### {mid} ")
    end = text.index("\n### ", start + 1)
    lines = [l for l in text[start:end].splitlines() if l.startswith(">")]
    return [l[1:].strip() for l in lines]


def test_the_block_is_the_headline_and_every_fragment_of_the_code():
    quoted = _quoted_block("M-IMPORT-TURNED-GRID")
    msg = M.M_IMPORT_TURNED_GRID
    assert quoted[0] == f"**{msg.title}**"
    body = [l for l in quoted[1:] if l]
    assert body == [M._TURNED_GRID_DIFFERS, M._TURNED_GRID_DIFFERS_PAGED,
                    M._TURNED_GRID_PAGES, M._TURNED_GRID_CELLS_DIFFER,
                    M._TURNED_GRID_WHAT_TO_DO]
    assert body == msg.body.split("\n")


def test_the_way_out_leads_with_the_test_chart_file():
    """N-b: what puts the grid right comes first, the display device second."""
    w = M._TURNED_GRID_WHAT_TO_DO
    assert w.index("load the turned test-chart file (.txf)") \
        < w.index("check that i1Profiler now shows exactly the grid") \
        < w.index("Default display device")
