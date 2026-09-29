"""`assets/charts/README.md` is the map of every bundled chart folder, and its
tables are what a reader (and GitHub) renders.

4.3.1 (B8-1700) rewrote the first table when the last prebuilt page images left
and left it broken: its one row began ``||``, which renders as an empty first
cell and pushes every column one to the right, and the paragraph under it ended
in a stray ``|``. Found by the 4.3.1 challenge round reading the file back.

MUTATION: put either stray pipe back and this goes red.
"""
from __future__ import annotations

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "assets" / "charts" / "README.md"


def _cells(line: str) -> list[str]:
    return line.strip().strip("|").split("|")


def test_every_table_row_has_the_header_s_columns_and_one_leading_pipe():
    lines = README.read_text(encoding="utf-8").splitlines()
    header = None
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        assert not s.startswith("||"), f"line {n} opens with an empty cell: {s[:60]}"
        if header is None:
            header = len(_cells(s))
            continue
        assert len(_cells(s)) == header, (
            f"line {n} has {len(_cells(s))} cells, its table {header}")


def test_no_prose_line_ends_in_a_table_pipe():
    for n, line in enumerate(README.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if s and not s.startswith("|"):
            assert not s.endswith("|"), f"line {n} ends in a stray pipe: {s[-60:]}"
