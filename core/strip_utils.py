"""Shared strip-letter utilities used by measurement and profcheck modules."""
from __future__ import annotations

import re
from pathlib import Path
from core.text_io import read_text


def parse_passes_per_page(ti2_path: "Path | str") -> list[int]:
    """Return the strip (pass) count for each printed page of a chart.

    Reads the ``PASSES_IN_STRIPS2`` field that Argyll's printtarg writes into
    the .ti2, e.g. ``PASSES_IN_STRIPS2 "24,23"`` → ``[24, 23]`` (page 1 has 24
    strips, page 2 has 23). This is the authoritative per-page strip layout —
    far more reliable than counting strip labels in the rendered TIFF, which is
    fooled by two-character labels (AA, AB, …) and by the rotated title string
    printtarg prints down the right margin.

    Returns an empty list when the file can't be read or the field is absent.
    """
    try:
        text = read_text(Path(ti2_path), lenient=True)
    except OSError:
        return []
    m = re.search(r'PASSES_IN_STRIPS2\s+"([^"]*)"', text)
    if not m:
        return []
    counts: list[int] = []
    for part in m.group(1).split(","):
        part = part.strip()
        if part.isdigit():
            counts.append(int(part))
    return counts


def letter_to_idx(letter: str) -> int:
    """Convert a strip letter to a 0-based sort index.

    A=0, B=1, … Z=25, AA=26, AB=27, … AZ=51, BA=52, …
    """
    idx = 0
    for c in letter.upper():
        idx = idx * 26 + (ord(c) - ord("A") + 1)
    return idx - 1
