"""The margin tolerance (Preferences > Beta, 2026-11-16) in the REAL
chromiq-chartread, through its replay instrument (an i1Pro 2 with the ruler):
a swipe ArgyllCMS's patch finder refused ({"cmd":"swipe","fault":"misread",
"reason":...,"margin":...}) hands its segments over, and the helper decides.

* without --margin-tolerance nothing changes: the refusal stays a refusal,
  the events carry no "margin" field, the session event no
  "margin_tolerance";
* with it, a margin at either end, or no white leader, is rescued: the
  strip_read event follows as for any accepted strip and the .ti3 holds the
  SAME values as an ordinary reading of that strip (byte for byte, CREATED
  aside);
* a swipe that began one patch in (the margin counted in its place) is
  refused, and so is a rescue candidate when the option is on but the ruler
  check is not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


def _chart(tmp: Path):
    from test_chartread_engine import _make_chart
    # no white or black patches, so no row can end in paper white
    base = _make_chart(tmp, randomised=False,
                       targen_args=["-d2", "-G", "-e0", "-B0", "-f42"])
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _ti3(base: Path) -> str:
    return "\n".join(ln for ln in base.with_suffix(".ti3").read_text(
        encoding="latin-1").splitlines() if not ln.startswith("CREATED"))


def _run(base, replay, args, swipes):
    """swipes: dicts sent as swipe commands, one per strip_ready; each must
    end in a reading (a rescued one included)."""
    with ReplaySession(base, replay, extra_args=args) as s:
        for sw in swipes:
            s.wait_event("strip_ready")
            i = s.event_index()
            s.send(cmd="swipe", **sw)
            s.wait_event("strip_ready", after=i)
        s.send(cmd="done")
        s.wait_event("done", timeout=8)
        s.finish()
    return s


MISREAD = {"ruler": "clean", "fault": "misread"}


@needs_helper
@pytest.mark.parametrize("margin,reason,rule", [
    ("start", "Too many patches", "M"),
    ("end", "Too many patches", "M"),
    ("both", "Too many patches", "M"),
    ("noleader", "Not enough patches", "L"),
])
def test_a_refused_margin_reading_is_rescued_with_the_ordinary_values(
        tmp_path, monkeypatch, margin, reason, rule):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, replay = _chart(tmp_path / "rescued")
    on = _run(base, replay, ["--ruler", "--margin-tolerance"],
              [dict(MISREAD, reason=reason, margin=margin), {"ruler": "clean"}])
    head = next(e for e in on.events if e.get("event") == "ruler")
    assert head["margin_tolerance"] == "on"
    rec = [e for e in on.events if e.get("event") == "ruler_strip"][0]
    assert rec["result"] == "read" and rec["reason"] == ""
    m = rec["margin"]
    assert m["accepted"] is True and m["rule"] == rule
    assert m["refused_because"] == reason
    assert m["left_start"] == (1 if margin in ("start", "both") else 0)
    assert m["left_end"] == (1 if margin in ("end", "both") else 0)
    assert len(rec["cut"]) == 2 * 21            # the kept patches' cut
    reads = [e for e in on.events if e.get("event") == "strip_read"]
    assert len(reads) == 2
    # the same chart read the ordinary way, with nothing refused
    base2, replay2 = _chart(tmp_path / "plain")
    _run(base2, replay2, ["--ruler", "--margin-tolerance"],
         [{"ruler": "clean"}, {"ruler": "clean"}])
    assert _ti3(base) == _ti3(base2)


@needs_helper
def test_a_swipe_begun_one_patch_in_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay,
                       extra_args=["--ruler", "--margin-tolerance"]) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", ruler="clean", fault="misread",
               reason="Too many patches", margin="shifted")
        rec = s.wait_event("ruler_strip", after=i)
        err = s.wait_event("error", after=i)
        s.send(cmd="quit")
        try:
            s.wait_event("strip_interrupted", timeout=3)
            s.send(cmd="quit")
        except TimeoutError:
            pass
        s.finish()
    assert rec["result"] == "misread" and rec["reason"] == "Too many patches"
    assert rec["margin"]["accepted"] is False and rec["margin"]["why"]
    assert err["kind"] == "misread"
    assert not any(e.get("event") == "strip_read" for e in s.events)


@needs_helper
def test_off_the_refusal_stays_and_no_field_is_added(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["--ruler"]) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", ruler="clean", fault="misread",
               reason="Too many patches", margin="start")
        rec = s.wait_event("ruler_strip", after=i)
        s.wait_event("error", after=i)
        s.send(cmd="quit")
        try:
            s.wait_event("strip_interrupted", timeout=3)
            s.send(cmd="quit")
        except TimeoutError:
            pass
        s.finish()
    head = next(e for e in s.events if e.get("event") == "ruler")
    assert "margin_tolerance" not in head
    assert rec["result"] == "misread" and "margin" not in rec


@needs_helper
def test_without_the_ruler_check_the_option_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["--margin-tolerance"]) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", ruler="clean", fault="misread",
               reason="Too many patches", margin="start")
        err = s.wait_event("error", after=i)
        s.send(cmd="quit")
        try:
            s.wait_event("strip_interrupted", timeout=3)
            s.send(cmd="quit")
        except TimeoutError:
            pass
        s.finish()
    assert err["kind"] == "misread"
    assert not any(str(e.get("event", "")).startswith("ruler") for e in s.events)
    assert not any(e.get("event") == "strip_read" for e in s.events)


@needs_helper
def test_an_i1pro3_never_gets_it(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, replay = _chart(tmp_path)
    s = _run(base, replay, ["--ruler", "--margin-tolerance"],
             [{"ruler": "clean"}, {"ruler": "clean"}])
    head = next(e for e in s.events if e.get("event") == "ruler")
    assert head["margin_tolerance"] == "not_i1pro2"
    assert not any("margin" in e for e in s.events
                   if e.get("event") == "ruler_strip")
