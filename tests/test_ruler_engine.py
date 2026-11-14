"""The ruler check (Preferences > Beta, 2026-11-14) in the REAL
chromiq-chartread, through its replay instrument
(CHROMIQ_REPLAY_INSTRUMENT=i1pro2|i1pro3, {"cmd":"swipe","ruler":...}).

* without --ruler: not one ruler event, and the session is today's;
* with it: one ``ruler`` event per session, one ``ruler_strip`` per strip
  BEFORE that strip's ``strip_read``/error, and once the driver gives the
  ruler up (here: "late", a stream that did not end) no more records;
* the .ti3 written for the same readings is byte for byte the same with the
  option on and off (CREATED aside);
* an instrument without a ruler (the replay's default i1Pro) never gets it.
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
    base = _make_chart(tmp, randomised=False)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _session(base, replay, args, rulers):
    with ReplaySession(base, replay, extra_args=args) as s:
        for mode in rulers:
            s.wait_event("strip_ready")
            i = s.event_index()
            s.send(cmd="swipe", ruler=mode)
            s.wait_event("strip_ready", after=i)
        s.send(cmd="done")
        s.wait_event("done", timeout=8)
        s.finish()
    return s


def _ti3(base: Path) -> str:
    return "\n".join(ln for ln in base.with_suffix(".ti3").read_text(
        encoding="latin-1").splitlines() if not ln.startswith("CREATED"))


@needs_helper
@pytest.mark.parametrize("gen", ["i1pro2", "i1pro3"])
def test_on_reports_each_strip_before_its_reading(tmp_path, monkeypatch, gen):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", gen)
    base, replay = _chart(tmp_path)
    s = _session(base, replay, ["--ruler"], ["clean", "partial"])
    names = [e.get("event") for e in s.events]
    head = next(e for e in s.events if e.get("event") == "ruler")
    assert head["active"] is True and head["instrument"] == gen
    assert head["argyll"] == "3.5.0"        # ARGYLL_VERSION_STR (review item 9)
    strips = [e for e in s.events if e.get("event") == "ruler_strip"]
    assert len(strips) == 2
    for k in [i for i, n in enumerate(names) if n == "ruler_strip"]:
        assert "strip_read" in names[k + 1:k + 4]
    assert strips[0]["instrument"] == gen and strips[0]["changes"]
    assert strips[0]["cut"] and strips[0]["readings"] > 0


@needs_helper
def test_a_given_up_ruler_reports_nothing_more(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, replay = _chart(tmp_path)
    s = _session(base, replay, ["--ruler"], ["late", "clean"])
    strips = [e for e in s.events if e.get("event") == "ruler_strip"]
    assert len(strips) == 1
    assert strips[0]["stream_did_not_end"] is True
    assert strips[0]["giveup"] == "stream_did_not_end"


@needs_helper
def test_off_says_nothing_and_the_ti3_is_the_same(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, replay = _chart(tmp_path / "on")
    on = _session(base, replay, ["--ruler"], ["clean", "partial"])
    ti3_on = _ti3(base)
    base2, replay2 = _chart(tmp_path / "off")
    off = _session(base2, replay2, [], ["clean", "partial"])
    assert not any(str(e.get("event", "")).startswith("ruler")
                   for e in off.events)
    assert ti3_on == _ti3(base2)
    strip_on = [e for e in on.events if e.get("event") == "strip_read"]
    strip_off = [e for e in off.events if e.get("event") == "strip_read"]
    assert strip_on == strip_off


@needs_helper
def test_an_instrument_without_a_ruler_never_gets_it(tmp_path, monkeypatch):
    monkeypatch.delenv("CHROMIQ_REPLAY_INSTRUMENT", raising=False)
    base, replay = _chart(tmp_path)
    s = _session(base, replay, ["--ruler"], ["clean", "clean"])
    head = next(e for e in s.events if e.get("event") == "ruler")
    assert head["active"] is False and head["why"] == "instrument"
    assert not any(e.get("event") == "ruler_strip" for e in s.events)
