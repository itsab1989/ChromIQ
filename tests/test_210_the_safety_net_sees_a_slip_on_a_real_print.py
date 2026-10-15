"""#210: the strip-misalignment safety net must be able to fire on a REAL print.

A forum user's i1Pro 3 read two strips of a Canon SELPHY chart one patch out:
the blank paper before the first patch was filed as patch A, every reading
moved one place down, and the last patch was lost. Realigned, those strips fit
the design at 15.6 and 19.8 dE mean; as read, 78.4 and 63.2.

The opt-in net (`--safenet`, `cq_detect_misalign` in
`native/chartread_helper/chromiq_chartread.c`) asked for a realigned fit of
6 dE or better. The fit is against the .ti2's DESIGN colours, which no real
printer reproduces that closely (even the correctly read strips of that chart
missed them by 9.7 to 26.2 dE mean), so the net could never speak on paper.
Its own test fed it the design values plus 0.1, which is why nobody saw it.

The net now also probes the other direction: a slipped strip fits badly both
ways round, so chartread's choice of direction is a coin toss, and on this
chart's seed it files the slipped strip as reversed (`other_direction` in the
event). Probing only that direction found nothing. On the #210 data the same
change also finds strip 13, swiped from the far end AND a patch out.

These tests read a chart through the real engine with readings that look like
a print: the colours pulled towards grey and the white darkened, so that a
correctly read strip misses its design by well over the net's 12 dE trigger.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, parse_ti2_rows  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")
SLIPPED = 1          # index of the strip read one patch out
PAPER = (82.0, 85.0, 70.0)   # the blank paper the slipped swipe starts on

_D50 = (96.42, 100.0, 82.49)


def _lab(xyz):
    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = (f(a / b) for a, b in zip(xyz, _D50))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _printed(xyz):
    """A plausible print of a design colour: chroma pulled a quarter of the
    way to the neutral of the same lightness, white and black compressed."""
    x, y, z = xyz
    return (0.82 * (0.75 * x + 0.25 * y * 0.9642) + 1.0,
            0.82 * y + 1.5,
            0.82 * (0.75 * z + 0.25 * y * 0.8249) + 1.0)


def _mean_de(read, design):
    return sum(math.dist(_lab(r), _lab(d)) for r, d in zip(read, design)) / len(design)


def _chart(tmp: Path) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    if not Path(targen).exists() or not Path(HELPER).exists():
        pytest.skip("Argyll targen or the ChromIQ engine helper is unavailable")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "SL"
    subprocess.run([targen, "-v0", "-d2", "-G", "-f120", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="i1", paper="A4",
                randomize=True, seed=1001, layout_mode="patch_first")
    return base


def _replay(base: Path, slip: bool):
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    letters = sorted(rows)
    out = base.parent / "replay.txt"
    with out.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\n")
        for i, letter in enumerate(letters):
            read = [_printed(v) for v in rows[letter]]
            if slip and i == SLIPPED:
                read = [PAPER] + read[:-1]      # the lead-in filed as patch 1
            fp.write(f"STRIP {letter}\n")
            for x, y, z in read:
                fp.write(f"{x:.4f} {y:.4f} {z:.4f}\n")
    return letters, rows


def _read_all(base: Path, n: int, extra_args):
    """Swipe every strip once, answering 'use it anyway' to any question, so
    the reading reaches the point where the net looks at it."""
    s = ReplaySession(base, base.parent / "replay.txt", extra_args=extra_args)
    s.wait_event("session_start")
    s.wait_event("strip_ready")
    for _ in range(n):
        idx = s.event_index()
        s.send(cmd="swipe")
        deadline = time.time() + 15
        answered = 0
        while time.time() < deadline:
            evs = s.events[idx:]
            if any(e.get("event") == "strip_read" for e in evs):
                break
            asked = [e for e in evs if e.get("event") == "strip_warning"]
            if len(asked) > answered:
                answered = len(asked)
                s.send(cmd="ok")
            time.sleep(0.02)
        s.wait_event("saved", after=idx)
    s.send(cmd="done")
    s.wait_event("done", timeout=8)
    return s, s.finish()


def test_the_print_model_really_misses_the_design_like_a_print_does(tmp_path):
    """THE CONTROL. If the 'printed' readings fitted the design within the old
    6 dE bar, the tests below would prove nothing about real paper."""
    base = _chart(tmp_path)
    letters, rows = _replay(base, slip=False)
    for letter in letters:
        design = rows[letter]
        read = [_printed(v) for v in design]
        fit = _mean_de(read, design)
        assert fit >= 12.0, (
            f"strip {letter} fits its design at {fit:.1f} dE, too well to "
            f"stand for a print")
        assert fit <= 35.0, (
            f"strip {letter} misses its design by {fit:.1f} dE, more than the "
            f"real prints this was measured against")


def test_a_strip_read_one_patch_out_on_a_real_print_is_reported(tmp_path):
    """MUTATION: put CQ_MIS_GOOD_DE back to 6.0, rebuild the helper, and
    this goes red."""
    base = _chart(tmp_path)
    letters, _rows = _replay(base, slip=True)
    s, rc = _read_all(base, len(letters), ["--safenet"])
    assert rc == 0
    mis = [e for e in s.events if e.get("event") == "strip_misaligned"]
    assert [e["strip"] for e in mis] == [letters[SLIPPED]], (
        f"expected the slipped strip {letters[SLIPPED]} and nothing else, "
        f"got {mis}")
    assert abs(mis[0]["offset"]) == 1
    assert float(mis[0]["best_de"]) <= 0.5 * float(mis[0]["base_de"])


def test_a_good_read_of_a_real_print_stays_quiet(tmp_path):
    """The other half: vivid strips that miss the design but are read in the
    right place must not trip the wider bar."""
    base = _chart(tmp_path)
    letters, _rows = _replay(base, slip=False)
    s, rc = _read_all(base, len(letters), ["--safenet"])
    assert rc == 0
    assert not [e for e in s.events if e.get("event") == "strip_misaligned"]
