"""Beta 12, #182 B1: a corrected misread turns GREEN as soon as nothing
flags the patch any more, even when that happens after the re-read.

Knut's rule (5984277558): a patch that was red and whose live re-read fits is
drawn green. Until beta 11 the green was recorded only in the one live
judgement where the re-read was not flagged AT ALL. Basti's AA5 (2026-10-05):
the strip misread at ΔE 115 (past the limit, and a neighbour suspect), the
re-read gave ΔE 40 (under the limit) but the neighbour check still suspected
it, because the strips around it were not read yet; when strip AD cleared the
suspicion, the patch lost its outline and never turned green.

Now a live re-read that differs from a flagged reading by more than
SAME_READING_DE is remembered as a pending correction and turns green the
moment the patch is judged not flagged, live or not.

The J28 mirror case (the re-read matches the FIRST reading, not the misread
straight before it) is deliberately unchanged: it is a question to Knut.
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

from workflow import patch_flags as pf
from workflow.icc_info import xyz_to_lab
from workflow.neighbour_check import NeighbourCheck

DATA = Path(__file__).parent / "data" / "b1_basti_et8550_1005"

EXP = (60.0, 10.0, 10.0)
MISREAD = (20.0, 60.0, -40.0)
GOOD = (58.0, 12.0, 8.0)


def _j(judge, meas, flagged, *, live=True, suspect=False):
    return judge.judge("AA5", EXP, meas, pf._norm(pf._sub(meas, EXP)),
                       flagged, live=live, strip="AA", reread_only=suspect)


def test_a_reread_still_suspected_turns_green_when_the_suspicion_clears():
    judge = pf.FlagJudge()
    assert _j(judge, MISREAD, True, suspect=True).flag is pf.FLAG_RED
    # Re-read, under the limit, but the neighbour check still suspects it.
    assert _j(judge, GOOD, True, suspect=True).flag is pf.FLAG_RED
    # A later strip clears the suspicion: repainted, not a live reading.
    v = _j(judge, GOOD, False, live=False)
    assert v.flag == pf.FLAG_CORRECTED
    assert v.prev_de == pf._norm(pf._sub(MISREAD, EXP))
    assert "AA5" in judge.corrected
    assert judge.export()["AA5"]["kind"] == "corrected"


def test_the_misread_coming_back_cancels_the_pending_correction():
    judge = pf.FlagJudge()
    _j(judge, MISREAD, True, suspect=True)
    _j(judge, GOOD, True, suspect=True)
    _j(judge, MISREAD, True, suspect=True)          # the same misread again
    assert _j(judge, MISREAD, False, live=False).flag is pf.FLAG_NONE
    assert judge.corrected == {}


def test_a_repaint_alone_never_makes_green():
    judge = pf.FlagJudge()
    _j(judge, MISREAD, True, live=False)
    assert _j(judge, MISREAD, False, live=False).flag is pf.FLAG_NONE
    judge = pf.FlagJudge()
    _j(judge, MISREAD, True)
    _j(judge, MISREAD, True)                         # read twice, the same
    assert _j(judge, MISREAD, False, live=False).flag is pf.FLAG_NONE


def test_reset_forgets_a_pending_correction():
    judge = pf.FlagJudge()
    _j(judge, MISREAD, True, suspect=True)
    _j(judge, GOOD, True, suspect=True)
    judge.reset()
    _j(judge, GOOD, True, suspect=True)
    assert _j(judge, GOOD, False, live=False).flag is pf.FLAG_NONE


def _replay(limit: float, fence_on: bool) -> dict:
    """Basti's 43 strip events of 2026-10-05 through the Measure tab's own
    outline pipeline (the per-strip loop of ``tab_measure``), offline."""
    from ui.tabs.tab_measure import _strip_outlier_fence
    evs = json.loads((DATA / "strip_events.json").read_text(encoding="utf-8"))
    ti2 = DATA / "chart.ti2"
    judge = pf.FlagJudge(white=pf.chart_white(ti2),
                         device_ranges=pf.chart_device_ranges(ti2))
    nc = NeighbourCheck()
    inputs: dict = {}
    hist: dict = {}

    def strip_of(loc):
        return re.match(r"[A-Z]+", loc).group(0)

    for ev in evs:
        ps = ev["patches"]
        des = [float(p["de"]) for p in ps]
        fence = _strip_outlier_fence(des) if fence_on else 0.0
        med = statistics.median(des)
        for p in ps:
            nc.set_reading(p["loc"], p["exyz"], p["xyz"], strip_of(p["loc"]))
        changed = nc.evaluate()
        for loc, f in nc.updated().items():
            if f.suspect:
                changed.setdefault(loc, f)
        done = set()
        for p in ps:
            loc = p["loc"]
            de = float(p["de"])
            warn = de >= limit and de >= fence
            e = xyz_to_lab(tuple(v / 100 for v in p["exyz"]))
            m = xyz_to_lab(tuple(v / 100 for v in p["xyz"]))
            f = nc.finding(loc)
            sus = f is not None and f.suspect
            inputs[loc] = (e, m, de, warn, de - med)
            v = judge.judge(loc, e, m, de, warn or sus, standout=de - med,
                            live=True, strip=strip_of(loc), reread_only=sus)
            hist.setdefault(loc, []).append((True, warn, v.flag))
            done.add(loc)
        for loc, f in changed.items():
            if loc in done or loc not in inputs:
                continue
            e, m, de, warn, so = inputs[loc]
            v = judge.judge(loc, e, m, de, warn or f.suspect, standout=so,
                            live=False, strip=strip_of(loc),
                            reread_only=f.suspect)
            hist[loc].append((False, warn, v.flag))
        judge.rejudge()
    # Patches red by the LIMIT once and re-read under it: their last outline.
    out = {}
    for loc, h in hist.items():
        live = [x for x in h if x[0]]
        if len(live) >= 2 and any(x[1] for x in live[:-1]) and not live[-1][1]:
            out[loc] = h[-1][2]
    return out


def test_bastis_readings_aa5_and_aa16_turn_green():
    final = _replay(95.0, fence_on=False)
    assert pf.is_corrected(final["AA5"])
    assert pf.is_corrected(final["AA16"])
    # The J28 mirror case is unchanged (a question to Knut): still red.
    assert final["J28"] is pf.FLAG_RED
    assert [loc for loc, f in final.items() if not pf.is_corrected(f)] == ["J28"]
    assert len(final) == 32


def test_bastis_readings_with_the_strip_test_on_and_his_old_limit():
    final = _replay(95.0, fence_on=True)
    assert final and all(pf.is_corrected(f) for f in final.values())
    final = _replay(50.0, fence_on=False)
    assert pf.is_corrected(final["AA5"]) and pf.is_corrected(final["AA16"])
    assert all(pf.is_corrected(f) for f in final.values())
