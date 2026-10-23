"""The pause between pages, in the engine (jctay, forum 149802; Basti
2026-10-23: "can this be added as an option in preferences measure tab").

The GUI sends ``{"cmd":"hold_after","strip":"F"}`` at the strip menu of the
strip it wants a pause after. Once that strip is read and accepted, the engine
does NOT arm the next strip: it reports ``{"event":"held"}`` and waits, with
the instrument's switch gate open, so a press of the button is reported as
``{"event":"switch"}`` and can never start the next strip by accident. These
tests drive the REAL chromiq-chartread through its replay instrument, whose
``{"cmd":"switch"}`` does what the i1Pro's switch thread does: a trigger while
a strip is armed, otherwise an ``inst_event_switch``.

Every test here fails on the engine before this change: it ignored
``hold_after``, never reported ``held`` and armed the next strip at once.
"""
from __future__ import annotations

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
    base = _make_chart(tmp, randomised=False,
                       targen_args=["-d2", "-G", "-e4", "-B4", "-f90"])
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _quit(s):
    from test_chartread_engine import _quit as quit_session
    quit_session(s)


def _events(s, after: int, name: str) -> list:
    with s._lock:
        return [e for e in s.events[after:] if e.get("event") == name]


def _read_held(s, strip: str) -> dict:
    """At strip *strip*'s menu: ask for the hold, read it, return `held`."""
    i = s.event_index()
    s.send(cmd="hold_after", strip=strip)
    s.send(cmd="swipe")
    s.wait_event("strip_read", after=i)
    return s.wait_event("held", after=i)


@needs_helper
def test_the_session_says_the_engine_can_hold(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        start = s.wait_event("session_start")
        assert start.get("hold_after") is True
        assert len(start["strips"]) >= 3, "the test needs three strips"
        s.wait_event("strip_ready")
        _quit(s)


@needs_helper
def test_after_the_strip_the_next_one_is_not_armed_until_resume(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        first = s.wait_event("strip_ready")["strip"]
        held = _read_held(s, first)
        assert held["strip"] == first
        # the replay instrument is an i1Pro: its button can continue
        assert held["button"] is True
        i = s.event_index()
        time.sleep(0.6)
        assert not _events(s, i, "strip_ready"), \
            "the engine armed the next strip while it was asked to hold"
        s.send(cmd="resume")
        ready = s.wait_event("strip_ready", after=i)
        assert ready["strip"] != first          # on to the next unread one
        _quit(s)


@needs_helper
def test_a_press_in_the_hold_is_reported_and_never_starts_a_scan(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        first = s.wait_event("strip_ready")["strip"]
        _read_held(s, first)
        i = s.event_index()
        s.send(cmd="switch")                        # the press that continues
        s.wait_event("switch", after=i)
        time.sleep(0.5)
        assert not _events(s, i, "scan_started"), "the press started a scan"
        assert not _events(s, i, "strip_ready"), "the engine acted on the press"
        # the GUI answers it with resume; only the NEXT press is the scan press
        s.send(cmd="resume")
        s.wait_event("strip_ready", after=i)
        j = s.event_index()
        s.send(cmd="switch")
        s.wait_event("scan_started", after=j)
        assert not _events(s, j, "switch"), "the scan press was reported"
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=j)
        _quit(s)


@needs_helper
def test_only_the_strip_it_was_asked_for_holds(tmp_path):
    """Every strip_ready forgets the request: one sent for strip A does not
    hold after strip B, and without a request nothing holds."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        first = s.wait_event("strip_ready")["strip"]
        i = s.event_index()
        s.send(cmd="hold_after", strip="ZZ")        # not this strip
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        s.wait_event("strip_ready", after=i)
        assert not _events(s, i, "held")
        # a request for the previous strip is gone now
        j = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=j)
        s.wait_event("strip_ready", after=j)
        assert not _events(s, j, "held")
        assert first
        _quit(s)


@needs_helper
def test_back_and_goto_move_from_the_strip_just_read(tmp_path):
    """Re-reading a strip of the page from the pause: back goes to the strip
    before the one just read, goto to the strip named, and no other strip is
    announced in between (the preview would flicker to the next page)."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        labels = [x["strip"] for x in s.wait_event("session_start")["strips"]]
        s.wait_event("strip_ready")
        # read A, then hold after B
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        s.wait_event("strip_ready", after=i)
        _read_held(s, labels[1])
        i = s.event_index()
        s.send(cmd="back")
        ready = s.wait_event("strip_ready", after=i)
        assert ready["strip"] == labels[0]
        time.sleep(0.3)
        assert [e["strip"] for e in _events(s, i, "strip_ready")] == [labels[0]]
        # read it again and hold, then go to strip B by name
        _read_held(s, labels[0])
        i = s.event_index()
        s.send(cmd="goto", strip=labels[1])
        ready = s.wait_event("strip_ready", after=i)
        assert ready["strip"] == labels[1]
        time.sleep(0.3)
        assert [e["strip"] for e in _events(s, i, "strip_ready")] == [labels[1]]
        _quit(s)


@needs_helper
def test_stop_and_save_from_the_hold_writes_the_readings(tmp_path):
    """Save and stop is the two-q chain: the first q is left for the strip
    menu (Strip Read Interrupted), the second writes the .ti3 and ends."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        first = s.wait_event("strip_ready")["strip"]
        _read_held(s, first)
        i = s.event_index()
        s.send(cmd="quit")
        s.wait_event("strip_interrupted", after=i)
        s.send(cmd="quit")
        s.wait_event("aborted", after=i)
        s.finish()
    ti3 = base.with_suffix(".ti3")
    assert ti3.exists(), "the readings were not saved"
    assert "BEGIN_DATA" in ti3.read_text(errors="replace")


@needs_helper
def test_done_from_the_hold_finishes_a_complete_chart(tmp_path):
    """The end of the chart: every strip read, the last one held. Done (the
    completion window's "Go to ... Tab") ends the read normally."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        labels = [x["strip"] for x in s.wait_event("session_start")["strips"]]
        s.wait_event("strip_ready")
        for lab in labels[:-1]:
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("strip_read", after=i)
            s.wait_event("strip_ready", after=i)
        _read_held(s, labels[-1])
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("done", after=i, timeout=8)
        s.finish()


@needs_helper
def test_a_stray_resume_at_the_strip_menu_triggers_nothing(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="resume")
        time.sleep(0.6)
        assert not _events(s, i, "scan_started")
        assert not _events(s, i, "strip_read")
        assert not _events(s, i, "strip_ready")
        _quit(s)


def test_the_hold_is_made_after_the_strip_is_saved_and_before_the_next():
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    hold = text.index("cq_hold_matches(hn)")
    saved = text.rfind("cq_write_ti3_atomic();", 0, hold)
    nxt = text.index("incflag = 2;		/* Skip to next unread */", hold)
    assert 0 < saved < hold < nxt
    # the gate around the hold's one wait
    seg = text[hold:nxt]
    assert re.search(r"cq_switch_gate_set\(1\);\s*hk = cq_hold_wait", seg)
    assert "cq_switch_gate_set(0);" in seg
