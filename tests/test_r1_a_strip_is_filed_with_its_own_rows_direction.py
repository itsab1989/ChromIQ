"""R1 (4.3.39): on a fixed-order chart, a strip filed under the row it was
read for takes THAT row's direction, not the direction of whichever row fitted
best (jctay, forum posts 150222 / 150236).

His i1Pro 3, a non-randomised 16 x 12 chart: strip 9 read forward fitted its
own row's design colours with 42.6 dE76 and row 13 turned round with 40.0.
ChromIQ starts the helper with -S, so no wrong-strip prompt; the helper filed
the reading under row 9 (right) with row 13's direction (wrong): back to
front, seven passes out of seven, in either direction, and the back-to-front
window's "Re-measure" could only go round again.

The fix (chromiq_chartread.c, after the wrong-strip prompt): when the reading
goes under the expected row without the prompt switching to that row's fit,
it takes the row's own best direction, as the prompt's "use it anyway" answer
always did, but only when that row can tell its own direction CLEARLY (turned
the other way it fits at least twice as badly: CQ_OWN_DIR_RATIO 0.5, the
Measure tab's REV_RATIO). On a print so far off its design that the row cannot
tell, upstream's choice stands.

The replay here is a SYNTHETIC chart shaped like his (tests/helpers/
strip_nine_fixture.py); none of his files is in the repository.

What did not change, and is proved here too: a strip really read backwards is
still filed the right way; -B (no recognition) files what was read as read;
the wrong-strip prompt still appears without -S; a randomised chart is
untouched; and with -S a swipe of ANOTHER strip is still filed under the
expected strip, as before (that is a separate question, reported, not changed).
The whole-population proof (every tracked chart and generated ones, four
noise levels, -S / none / -S -B, i1Pro 2 and 3: the v4.3.38 helper and this
one give identical events and .ti3 files) is a work-folder script, not a test,
because it takes minutes: see the build notes.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
import strip_nine_fixture as nine  # noqa: E402
from replay_tools import HELPER, ReplaySession  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "native" / "chartread_helper" / "chromiq_chartread.c"

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")

#: The instruments whose readings go through the same row loop: the original
#: i1Pro (the replay's default), the i1Pro 2 and the i1Pro 3.
INSTRUMENTS = ["", "i1pro2", "i1pro3"]


def test_the_fixture_has_the_testers_shape():
    sc = nine.scores(nine.SICK_ROW)
    own_fwd, own_rev = sc[(nine.SICK_ROW, 0)], sc[(nine.SICK_ROW, 1)]
    other_rev = sc[(nine.LOOKALIKE_ROW, 1)]
    best = min(sc, key=sc.get)
    assert best == (nine.LOOKALIKE_ROW, 1), "row 13 turned round fits best"
    assert other_rev < own_fwd < 1.15 * other_rev, "only slightly better"
    assert own_fwd <= 0.5 * own_rev, "the row itself knows its direction"
    # every other strip fits its own row forward best
    for s in range(1, nine.STRIPS + 1):
        if s != nine.SICK_ROW:
            sc = nine.scores(s)
            assert min(sc, key=sc.get) == (s, 0)


@pytest.fixture
def chart(tmp_path):
    base = tmp_path / "nine"
    nine.write_chart(base)
    return base, nine.write_replay(tmp_path / "replay.txt")


def _swipe(s, strip, **swipe):
    i = s.event_index()
    s.send(cmd="goto", strip=strip)
    s.wait_event("strip_ready", after=i, strip=strip)
    i = s.event_index()
    s.send(cmd="swipe", **swipe)
    return i


def _read(s, after):
    return s.wait_event("strip_read", after=after)


def _quit(s):
    i = s.event_index()
    s.send(cmd="quit")
    try:
        s.wait_event("strip_interrupted", timeout=3, after=i)
        s.send(cmd="quit")
    except TimeoutError:
        pass
    s.finish()


def _env(monkeypatch, inst):
    if inst:
        monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", inst)
    else:
        monkeypatch.delenv("CHROMIQ_REPLAY_INSTRUMENT", raising=False)


def _in_order(ev):
    """The filed patches equal the A -> L reading, patch for patch."""
    want = nine.reading_of(nine.SICK_ROW)
    got = [p["xyz"] for p in ev["patches"]]
    return all(abs(a - b) < 1e-3 for g, w in zip(got, want)
               for a, b in zip(g, w))


@needs_helper
@pytest.mark.parametrize("inst", INSTRUMENTS)
@pytest.mark.parametrize("backwards", [False, True])
def test_strip_nine_is_filed_the_right_way_round(chart, monkeypatch, inst,
                                                 backwards):
    _env(monkeypatch, inst)
    base, replay = chart
    with ReplaySession(base, replay, extra_args=["-S"]) as s:
        s.wait_event("strip_ready")
        ev = _read(s, _swipe(s, "9", reversed=backwards))
        assert ev["strip"] == "9"
        assert ev["reversed"] is backwards
        assert _in_order(ev), "strip 9 filed back to front"
        # the figures the event has always carried are unchanged in meaning:
        # corr is the best row overall (row 13 turned round), expected_corr
        # the strip's own row
        assert ev["corr"] < ev["expected_corr"]
        _quit(s)
    ti3 = base.with_suffix(".ti3").read_text(encoding="latin-1")
    first = next(l for l in ti3.splitlines() if '"9A"' in l)
    want = nine.reading_of(nine.SICK_ROW)[0]
    assert f"{want[0]:.4f}"[:5] in first


@needs_helper
def test_minus_b_still_files_what_was_read_as_read(chart):
    base, replay = chart
    with ReplaySession(base, replay, extra_args=["-S", "-B"]) as s:
        s.wait_event("strip_ready")
        ev = _read(s, _swipe(s, "9"))
        assert ev["reversed"] is False and _in_order(ev)
        ev = _read(s, _swipe(s, "9", reversed=True))
        assert ev["reversed"] is False      # no recognition: as read
        assert not _in_order(ev)
        _quit(s)


@needs_helper
def test_without_minus_s_the_wrong_strip_prompt_still_appears(chart):
    """Unchanged: row 9 is checkable, so without -S the helper asks; "use it
    anyway" files it under row 9 with row 9's own direction (upstream)."""
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = _swipe(s, "9")
        w = s.wait_event("strip_warning", after=i)
        assert (w["kind"], w["read"], w["expected"]) == ("wrong_strip", "13", "9")
        s.send(cmd="accept")
        ev = _read(s, i)
        assert ev["reversed"] is False and _in_order(ev)
        _quit(s)


@needs_helper
@pytest.mark.parametrize("backwards", [False, True])
def test_another_strip_swiped_on_nine_is_still_filed_under_nine(chart,
                                                                backwards):
    """Unchanged, reported: with -S a swipe of strip 5 while the reader is on
    strip 9 is filed under strip 9. ChromIQ's own checks (the patch error
    limit, the neighbour check, "I read strip B") are what catch it."""
    base, replay = chart
    with ReplaySession(base, replay, extra_args=["-S"]) as s:
        s.wait_event("strip_ready")
        ev = _read(s, _swipe(s, "9", **{"as": "5", "reversed": backwards}))
        assert ev["strip"] == "9"
        _quit(s)


@needs_helper
@pytest.mark.parametrize("backwards", [False, True])
def test_every_other_strip_is_filed_as_before(chart, backwards):
    base, replay = chart
    with ReplaySession(base, replay, extra_args=["-S"]) as s:
        s.wait_event("strip_ready")
        for strip in ("1", "8", "10", "13", "16"):
            ev = _read(s, _swipe(s, strip, reversed=backwards))
            assert ev["reversed"] is backwards, strip
        _quit(s)


def test_the_rule_is_where_the_brief_says_and_guarded():
    src = SRC.read_text(encoding="utf-8")
    assert "#define CQ_OWN_DIR_RATIO 0.5" in src
    m = re.search(r"if \(cq_json && !rand && boroi != oroi && dirrg == 2\s*"
                  r"&& xdcorr\[xbdir\] <= CQ_OWN_DIR_RATIO \* xdcorr\[1 - xbdir\]\) \{"
                  r"\s*bcorr = xbcorr;\s*boff = xboff;\s*bdir = xbdir;"
                  r"\s*werror = xwerror;\s*\}", src)
    assert m, "the R1 rule moved or changed"
    # it sits after the wrong-strip prompt and before the patch-error check
    assert src.index("kind\\\":\\\"wrong_strip") < m.start() \
        < src.index("kind\\\":\\\"unexpected_response")
    # the GUI's back-to-front check uses the same ratio
    from workflow import slipped_strip
    assert slipped_strip.REV_RATIO == 0.5
