"""B1 (Basti, 2026-10-21, forum 149774): the instrument's button as Retry.

After a failed strip the engine waits at "Hit Esc to give up, any other key to
retry". The i1Pro, i1Pro 3 and ColorMunki drivers run a switch thread that
reports every press made outside a scan through the event callback
(i1pro_imp.c:11163, i1pro3_imp.c:4969, munki_imp.c:8491), and the engine used
to drop it. It now passes the press on as ``{"event":"switch"}``, but ONLY
while it waits at that one prompt: never at Wrong Strip Read, never during a
calibration, never at the strip menu (where a press is the scan trigger, as it
always was). The engine never acts on the press itself; the GUI decides.

These tests drive the REAL chromiq-chartread through its replay instrument,
whose ``{"cmd":"switch"}`` does what the i1Pro's switch thread does: a trigger
while a strip waits for one, otherwise an ``inst_event_switch``.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "native" / "chartread_helper"

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


def _chart(tmp: Path):
    from test_chartread_engine import _make_chart
    base = _make_chart(tmp, randomised=False)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _quit(s):
    from test_chartread_engine import _quit as quit_session
    quit_session(s)


def _switches(s, after: int) -> int:
    with s._lock:
        return sum(1 for e in s.events[after:] if e.get("event") == "switch")


# ---------------------------------------------------------------------------
# the positive path: misread -> press 1 reported -> ok -> press 2 scans
# ---------------------------------------------------------------------------
@needs_helper
def test_a_press_at_the_misread_prompt_is_reported_and_press_two_scans(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", fault="misread", reason="Too many patches")
        err = s.wait_event("error", after=i)
        assert err["kind"] == "misread"
        assert err["detail"] == "Too many patches"
        # the replay instrument is an i1Pro, whose switch thread reports presses
        assert err["button_retry"] is True

        i = s.event_index()
        s.send(cmd="switch")                       # press 1
        s.wait_event("switch", after=i)
        # the engine itself does nothing with it: still at the prompt
        time.sleep(0.4)
        with s._lock:
            assert not [e for e in s.events[i:]
                        if e.get("event") == "strip_ready"], \
                "the engine acted on the press by itself"

        s.send(cmd="ok")                           # what the GUI's Retry sends
        ready = s.wait_event("strip_ready", after=i)
        assert ready["strip"] == err.get("strip", ready["strip"])

        i = s.event_index()
        s.send(cmd="switch")                       # press 2: the scan press
        s.wait_event("scan_started", after=i)
        assert _switches(s, i) == 0, "the scan press was reported as a retry"
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        _quit(s)


@needs_helper
def test_the_event_line_is_one_clean_object(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", fault="misread")
        s.wait_event("error", after=i)
        s.send(cmd="switch")
        s.wait_event("switch", after=i)
        s.send(cmd="ok")
        s.wait_event("strip_ready", after=i)
        _quit(s)
    assert '{"event":"switch"}' in s.raw_lines
    errs = [ln for ln in s.raw_lines if '"kind":"misread"' in ln]
    assert errs and errs[0].endswith('"button_retry":true}'), errs


# ---------------------------------------------------------------------------
# the negative cases: nowhere else does a press become a retry
# ---------------------------------------------------------------------------
@needs_helper
def test_a_press_at_the_strip_menu_is_the_trigger_and_never_a_switch(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="switch")
        s.wait_event("scan_started", after=i)
        # a second press during the swipe (the driver reports it, the gate is shut)
        s.send(cmd="switch")
        time.sleep(0.4)
        assert _switches(s, i) == 0
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        _quit(s)


@needs_helper
def test_a_press_at_wrong_strip_read_is_not_reported(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        first = s.wait_event("strip_ready")
        other = "B" if first["strip"] != "B" else "C"
        i = s.event_index()
        s.send(cmd="swipe", **{"as": other})
        s.wait_event("strip_warning", after=i)
        j = s.event_index()
        s.send(cmd="switch")
        time.sleep(0.6)
        assert _switches(s, j) == 0, "a press at Wrong Strip Read was reported"
        s.send(cmd="retry")
        s.wait_event("strip_ready", after=j)
        _quit(s)


@needs_helper
def test_a_press_after_the_prompt_was_answered_is_not_reported(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", fault="misread")
        s.wait_event("error", after=i)
        s.send(cmd="ok")
        s.wait_event("strip_ready", after=i)
        # armed again: a press is the trigger, not a switch
        j = s.event_index()
        s.send(cmd="switch")
        s.wait_event("scan_started", after=j)
        assert _switches(s, j) == 0
        _quit(s)


@needs_helper
def test_a_press_during_a_requested_calibration_is_not_reported(tmp_path,
                                                                monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=i, timeout=8)
        j = s.event_index()
        s.send(cmd="switch")
        time.sleep(0.6)
        assert _switches(s, j) == 0, "a press during a calibration was reported"
        s.send(cmd="ok")
        s.wait_event("cal_result", after=j, timeout=8)
        _quit(s)


# ---------------------------------------------------------------------------
# the source: one gate, opened in two places and nowhere else
# ---------------------------------------------------------------------------
def test_the_gate_is_opened_only_at_the_misread_prompt_and_the_page_hold():
    """At the misread prompt (B1) and, since 4.3.10, in the pause between
    pages (``held``, tests/test_page_pause_engine.py). Both are waits outside
    any scan; nowhere else may a press be reported."""
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    opens = [m.start() for m in re.finditer(r"cq_switch_gate_set\(1\)", text)]
    assert len(opens) == 2, f"the switch gate is opened {len(opens)} times"
    before = text[max(0, opens[0] - 1500):opens[0]]
    assert "Strip read failed due to misread" in before
    assert '\\"kind\\":\\"misread\\"' in before
    before = text[max(0, opens[1] - 1500):opens[1]]
    assert "cq_hold_matches(hn)" in before
    assert '\\"event\\":\\"held\\"' in before


def test_the_callback_reports_a_press_only_through_the_gate():
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    m = re.search(r"void cq_event_callback\(void \*cntx, inst_event_type event\)"
                  r" \{(.*?)\n\}", text, re.S)
    assert m
    body = m.group(1)
    assert "inst_event_switch" in body
    assert "cq_switch_gate_open()" in body
    assert 'cq_emit_simple("switch")' in body


def test_only_the_instruments_with_a_switch_thread_offer_it():
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    m = re.search(r"static int cq_button_retry_ok\(.*?\n\}", text, re.S)
    assert m
    body = m.group(0)
    for t in ("instI1Pro", "instI1Pro2", "instI1Pro3", "instColorMunki"):
        assert re.search(rf"\b{t}\b", body), t
    for t in ("instDTP20", "instDTP22", "instDTP41", "instSpectroScan",
              "instI1iSis"):
        assert t not in body, t
