"""4.3.23 review round 1: the findings, each pinned.

S1  the CHANGELOG said -F is not passed when the option is switched ON.
S2  a 4.3.22-or-older import ("i1Pro 3", no spectra) was told to measure
    with an i1Pro, which it was; it is told to import the .mxf again.
S3  the Measure tab records the condition it measured under (-F), merges
    of an M1/M2 measurement with one of another or no condition are
    refused, and the FWA gate refuses -f for such chartread files too.
S4  an i1Profiler CGATS .txt import records the condition its
    MEASUREMENT_SOURCE names (Filter=no / D50 / UVcut / Polarized), and
    one that names none gets no -f.
M1  the Measurement Report keeps one .mxf under two conditions apart.
M3  "instrument differs" compares instrument families.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# S1
# ---------------------------------------------------------------------------

def _unreleased() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return text.split("## Unreleased", 1)[1].split("\n## v", 1)[0]


def test_s1_the_changelog_says_minus_f_is_left_out_while_the_option_is_off():
    text = _unreleased()
    assert "and then ChromIQ does not pass -F at all" not in text
    assert ("While it is off (the default), ChromIQ does not pass -F at all"
            in text)
