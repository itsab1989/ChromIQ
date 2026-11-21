"""The pace of a hand dual strip (after 4.3.54, 2026-11-21; docs/design/i1pro2_dual_scan.md
section 17; texts §M-PROPOSED M-DUAL-PASS-PACE, -PACE-CLOSE, -TOO-FAST).

Pinned here:
* the helper's dual_pass_result carries the pace block (C source) and the simulated helper sends
  the same fields;
* accepted strip: the Measure log and the reading-speed line say both passes' seconds and the
  emptiest patch's readings against the 3 needed (green; amber when exactly at 3);
* a "too fast" refusal: Strip Read Failed says how many readings, how many are needed, and about
  how long the pass should take; the reading-speed line says it in red;
* the app log: one line per pass verdict with the pace numbers, the per-patch lists in full at
  DEBUG, no serial and no path;
* without the pace block (an older helper, the table, a spot) every text is 4.3.54's;
* the Ruler (beta) line is true for a dual measurement.
INVENTED numbers only.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

import pytest

from workflow import measurement_messages as M
from workflow.dual_scan import pace as P
from workflow.dual_scan import session as D

ROOT = Path(__file__).resolve().parent.parent


def _ev(ok=True, fewest=5, uv_s=4.1, lamp_s=3.7, why="", strip="B", n=12, median=None):
    med = fewest + 3 if median is None else median
    counts = [med - 1 + (k % 3) for k in range(n)]
    counts[n // 2] = fewest
    return {"event": "dual_pass_result", "what": "strip", "strip": strip, "ok": ok,
            "why": why, "uv_readings": 840, "fewest_per_patch": fewest, "uv_triggers": 1,
            "volts": [1310, 1302], "pairing": "checked" if ok else "", "calibrate": False,
            "pace": True, "need": 3, "edge_steps": 0.5, "reading_ms": 4.896,
            "lamp_readings": 756, "lamp_s": lamp_s, "lamp_travel": 515, "lamp_dir": -1,
            "uv_s": uv_s, "uv_travel": 512, "uv_dir": 1, "lamp_off_ms": 2,
            "uv_dark_ms": 1150, "uv_trigger_ms": 1190, "uv_done_ms": 5290,
            "flatness": 0.00002, "window_flatness": 0.00003, "max_window_flatness": 0.001,
            "offset_steps": 0.85, "offset_rise": 1.7, "align": "lined_up",
            "lamp_cells": [c + 3 for c in counts], "uv_counts": counts}


def _old(ev):
    """the same event as a 4.3.54 helper sends it"""
    keep = ("event", "what", "strip", "ok", "why", "uv_readings", "fewest_per_patch",
            "uv_triggers", "volts", "pairing", "calibrate")
    return {k: v for k, v in ev.items() if k in keep}


# ---------------------------------------------------------------- the texts

def test_an_accepted_strip_with_room_is_green_and_says_both_passes():
    title, body, colour = P.accepted_text(_ev(fewest=5), "B")
    assert (title, body) == M.M_DUAL_PASS_PACE.render(
        strip="B", fewest=5, need=3, lamp_s="3.7", uv_s="4.1")
    assert colour == P.GOOD
    assert "3.7 seconds" in body and "4.1 seconds of reading" in body and "at least 5" in body


@pytest.mark.parametrize("f", [3, 4])
def test_an_accepted_strip_near_the_limit_is_amber(f):
    """review m4: at 4 against 3 a pass a quarter faster is refused, so not "leaves room" """
    title, body, colour = P.accepted_text(_ev(fewest=f), "B")
    assert title == M.M_DUAL_PASS_PACE_CLOSE.render(
        strip="B", fewest=f, need=3, lamp_s="3.7", uv_s="4.1")[0]
    assert colour == P.CLOSE and f"emptiest patch got {f} readings" in body
    assert "leaves room" not in body


def test_too_fast_names_a_time_with_room_above_the_limit():
    ev = _ev(ok=False, fewest=2, uv_s=3.8, why="uv_pass_too_fast")   # median 5
    assert P.too_fast_case(ev) == "time"
    title, body = P.too_fast_text(ev)
    assert title == "The second pass (UV light) was too fast"
    assert "only 2 readings" in body and "at least 3" in body
    # 3.8 x (3 + 0.5) / 2 = 6.65 -> 7.0: half a reading above the limit (review m1)
    assert "lasted 3.8 seconds of reading" in body and "a little longer than 7.0 seconds" in body
    assert "both passes" in body                                          # section 0 (a)


def test_too_fast_with_one_reading_is_said_in_the_singular():
    _t, body = P.too_fast_text(_ev(ok=False, fewest=1, uv_s=2.0, why="uv_pass_too_fast",
                                   median=4))
    assert "only 1 reading," in body and "1 readings" not in body
    assert "7.0 seconds" in body                                          # 2.0 x 3.5 = 7.0


def test_a_pass_slow_enough_as_a_whole_is_told_to_move_evenly():
    """review M3: half of the patches got twice what is needed: one fast stretch"""
    ev = _ev(ok=False, fewest=2, uv_s=5.0, why="uv_pass_too_fast", median=7)
    assert P.too_fast_case(ev) == "uneven"
    title, body = P.too_fast_text(ev)
    assert title == "One patch got too few readings in the second pass (UV light)"
    assert "Half of the patches got 7 readings or more" in body and "evenly" in body
    # the reviewer's m2: it cannot tell a quick hand from a narrower patch, and says so
    assert "a quicker moment there, or a narrower patch" in body and "sped up" not in body
    # the line under the chart carries the same headline, not "was too fast"
    assert P.too_fast_line(ev)[0] == title
    assert "seconds" not in body


@pytest.mark.parametrize("uv_s,fewest", [(6.6, 1), (13.0, 2), (19.0, 2)])
def test_the_advice_never_names_a_time_near_the_pass_limit(uv_s, fewest):
    """review M3: 4000 readings x 4.896 ms = 19.6 s is the longest pass taken"""
    ev = _ev(ok=False, fewest=fewest, uv_s=uv_s, why="uv_pass_too_fast", median=fewest + 2)
    assert P.cap_seconds(ev) == pytest.approx(19.584)
    assert P.too_fast_case(ev) == "even"
    _t, body = P.too_fast_text(ev)
    assert "up to about 19 seconds" in body and "longer than" not in body


def test_a_named_time_always_stays_under_the_limit():
    for uv_s in np.arange(0.5, 20.0, 0.25):
        for f in (1, 2):
            ev = _ev(ok=False, fewest=f, uv_s=float(uv_s), why="uv_pass_too_fast", median=f + 2)
            if P.too_fast_case(ev) == "time":
                assert P.target_seconds(float(uv_s), f, 3) < 0.8 * P.cap_seconds(ev)


def test_the_target_is_rounded_up_to_half_a_second():
    assert P.target_seconds(4.0, 2, 3) == 7.0
    assert P.target_seconds(3.8, 2, 3) == 7.0
    assert P.target_seconds(3.0, 3, 3) == 3.5


def test_the_line_under_the_chart_is_short():
    """review m2: the numbers only, not the whole window text"""
    t, b = P.too_fast_line(_ev(ok=False, fewest=2, uv_s=3.8, why="uv_pass_too_fast"))
    assert b == "One patch got only 2 readings (3 needed) in 3.8 seconds of reading."


def test_a_pass_that_did_not_line_up_has_its_own_text():
    t, b = P.refusal_text(_ev(ok=False, fewest=5, why="uv_pass_shifted"))
    assert (t, b) == M.M_DUAL_PASS_SHIFTED.render()
    assert "on the way back" in b and "both passes" in b
    assert D.reason_sentence("uv_pass_shifted") == b


def test_without_the_pace_block_nothing_new_is_said():
    assert P.accepted_text(_old(_ev()), "B") is None
    assert P.too_fast_text(_old(_ev(ok=False, fewest=2, why="uv_pass_too_fast"))) is None
    # a refusal of another kind keeps its own sentence even with the block
    assert P.too_fast_text(_ev(ok=False, fewest=4, why="uv_pass_misaligned")) is None
    assert P.refusal_text(_ev(ok=False, fewest=4, why="uv_pass_misaligned")) is None


def test_the_decimal_mark_is_the_languages(monkeypatch):
    import core.i18n as i18n
    monkeypatch.setattr(i18n, "uses_decimal_comma", lambda lang=None: True)
    _t, body, _c = P.accepted_text(_ev(fewest=5), "B")
    assert "3,7" in body and "4,1" in body


# ---------------------------------------------------------------- the app log

def test_the_app_log_has_the_pace_and_the_lists_in_full(caplog):
    caplog.set_level(logging.DEBUG, logger="chromiq.events")
    P.log_result(_ev(ok=False, fewest=2, uv_s=3.8, why="uv_pass_too_fast", n=23))
    lines = [r.getMessage() for r in caplog.records if r.name == "chromiq.events"]
    main = [x for x in lines if x.startswith("dual pass: ")]
    lists = [x for x in lines if x.startswith("dual pass patches: ")]
    assert len(main) == 1 and len(lists) == 1
    for key in ("strip=B", "ok=off", "why=uv_pass_too_fast", "lamp_dir=-1", "lamp_travel=515",
                "lamp_readings=756", "lamp_s=3.7", "uv_dir=1", "uv_travel=512", "uv_s=3.8",
                "uv_readings=840", "uv_count_min=2", "need=3", "edge_steps=0.5",
                "lamp_off_ms=2", "uv_dark_ms=1150", "uv_trigger_ms=1190", "slower_factor=1.75",
                "target_s=7", "advice=time", "cap_s=19.584", "flatness=0", "window_flatness=0",
                "max_window_flatness=0.001", "align=lined_up", "offset_steps=0.85",
                "offset_rise=1.7",
                "lamp_cell_min=", "lamp_cell_median=", "uv_count_median="):
        assert key in main[0], (key, main[0])
    assert lists[0].count(",") >= 2 * 22          # 23 patches, both lists, in full
    rec = [r for r in caplog.records if r.getMessage().startswith("dual pass patches: ")][0]
    assert rec.levelno == logging.DEBUG
    for bad in ("serial", "/Users", "\\"):
        assert bad not in main[0] + lists[0]


def test_the_manager_writes_the_line_for_every_verdict():
    src = (ROOT / "workflow" / "measure_manager.py").read_text(encoding="utf-8")
    i = src.index('elif kind == "dual_pass_result":')
    assert "_dual_pace_log(ev)" in src[i:i + 600]


# ---------------------------------------------------------------- the tab

def _tab(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    from tests.test_i1pro2_dual_scan_ui_fix import _fake
    fake, logged, notices, flashes = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M2"})
    TabMeasure._on_dual_calibration(fake, {"ok": True, "why": ""})
    return TabMeasure, fake, logged


def test_the_tab_logs_the_pace_of_an_accepted_strip(qapp, tmp_path):
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass_result(fake, _ev(fewest=3, strip="B"))
    title, body = M.M_DUAL_PASS_PACE_CLOSE.render(
        strip="B", fewest=3, need=3, lamp_s="3.7", uv_s="4.1")
    assert f"[{title}]\n{body}" in logged
    assert fake._dual_pace_line[0] == "B" and fake._dual_pace_line[2] == P.CLOSE


def _pace_fake(fake, too_fast=True):
    """the parts of the tab _report_strip_pace / _report_failed_strip_pace use; the #131
    tracker set to call this strip TOO FAST (the review's M2 case: a UV pass under about
    100 ms per patch, as at i1Profiler's own normal pace)"""
    import time
    from types import SimpleNamespace
    calls = {"panel": [], "prompt": [], "verdict": [], "show": []}
    pace = SimpleNamespace(patches=12, mean_seconds=0.06, elapsed=0.7, too_fast=too_fast,
                           marginal=False, est_samples=12)
    tracker = SimpleNamespace(strip_timed=lambda secs, n: pace,
                              config=SimpleNamespace(min_samples=20, sample_hz=200.0))
    fake._settings = {"pace_hint_enabled": True}
    fake._pace_tracker = lambda: tracker
    fake._scan_started_at = time.monotonic() - 0.7
    fake._scan_awaiting_ready = False
    fake._pace_times = {}
    fake._spot_session = False
    fake._last_strip_patches = 12
    fake._current_strip_letter = "B"
    fake._refresh_pace_panel = lambda text, colour="": calls["panel"].append((text, colour))
    fake._prompt_too_fast_strip = lambda *a: calls["prompt"].append(a)
    fake._strip_verdict = lambda ev, too_fast=False: calls["verdict"].append(too_fast) or True
    fake._show_strip_pace = lambda *a: calls["show"].append(a)
    return calls


def test_one_verdict_per_dual_strip_the_dual_one(qapp, tmp_path):
    """review M2: the #131 check (ArgyllCMS's lamp-pass rule, timed from the SECOND pass's
    beep) says "Too fast" while the readings per patch leave room: the dual verdict owns the
    strip; no #131 line, no #131 prompt, the time under the strip the pass's seconds of reading"""
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass_result(fake, _ev(fewest=6, strip="B", uv_s=2.4))
    calls = _pace_fake(fake, too_fast=True)
    T._report_strip_pace(fake, {"event": "strip_read", "strip": "B", "patches": [1] * 12})
    assert calls["panel"] and calls["panel"][-1][1] == P.GOOD
    assert "Strip B: both passes read" in calls["panel"][-1][0]
    assert not calls["prompt"] and not calls["show"] and calls["verdict"] == [False]
    assert fake._pace_times["B"] == (2.4, True)
    assert not [x for x in logged if "Too fast" in x]


def test_a_single_scan_strip_keeps_the_131_verdict(qapp, tmp_path):
    """options off / no pace from the engine: the #131 check as before"""
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass_result(fake, _old(_ev(fewest=6, strip="B")))
    calls = _pace_fake(fake, too_fast=True)
    T._report_strip_pace(fake, {"event": "strip_read", "strip": "B", "patches": [1] * 12})
    assert calls["show"], "the #131 path ran"


def test_a_refused_strip_gets_the_short_line_and_one_time(qapp, tmp_path):
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass(fake, {"strip": "B", "lamp_ok": True})
    T._on_dual_pass_result(fake, _ev(ok=False, fewest=2, uv_s=3.8, why="uv_pass_too_fast"))
    calls = _pace_fake(fake)
    T._report_failed_strip_pace(fake, "Misread")
    text, colour = calls["panel"][-1]
    assert colour == P.TOO_FAST
    assert text == ("The second pass (UV light) was too fast · One patch got only 2 readings "
                    "(3 needed) in 3.8 seconds of reading.")
    assert fake._pace_times["B"] == (3.8, False)


def test_a_pass_that_did_not_line_up_is_said_under_the_chart(qapp, tmp_path):
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass(fake, {"strip": "B", "lamp_ok": True})
    T._on_dual_pass_result(fake, _ev(ok=False, fewest=5, why="uv_pass_shifted"))
    calls = _pace_fake(fake)
    T._report_failed_strip_pace(fake, "Misread")
    assert calls["panel"][-1] == ("The second pass (UV light) did not line up with the first",
                                  P.TOO_FAST)
    html = T._dual_failure_html(fake)
    assert "on the way back" in html and "The second pass of strip B failed" in html


def test_the_failure_window_says_by_how_much(qapp, tmp_path):
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass(fake, {"strip": "B", "lamp_ok": True})
    ev = _ev(ok=False, fewest=2, uv_s=3.8, why="uv_pass_too_fast", strip="B")
    T._on_dual_pass_result(fake, ev)
    html = T._dual_failure_html(fake)
    _t, tf = P.too_fast_text(ev)
    title, _b = M.M_DUAL_PASS_FAILED.render(strip="B", reason=tf)
    assert "a little longer than 7.0 seconds" in html and "only 2 readings" in html
    assert "The second pass of strip B failed" in html


def test_the_failure_window_of_an_older_helper_is_4354s(qapp, tmp_path):
    T, fake, logged = _tab(tmp_path)
    T._on_dual_pass(fake, {"strip": "B", "lamp_ok": True})
    T._on_dual_pass_result(fake, _old(_ev(ok=False, fewest=2, why="uv_pass_too_fast")))
    html = T._dual_failure_html(fake)
    assert "move a little slower" in html and "seconds" not in html


# ---------------------------------------------------------------- the engine

def test_the_helper_emits_the_pace_block_after_the_cut():
    src = (ROOT / "native" / "chartread_helper" / "chromiq_dualdev.c").read_text(encoding="utf-8")
    i = src.index("static void cq_dd_strip(")
    body = src[i:src.index("\n}\n", i)]
    assert "i1pro2_cq_dual_times(it, &pc.t);" in body and "pc.cells = r.cut_no;" in body
    # every other verdict path sends no pace block (nothing is known there)
    assert src.count(", NULL);") >= 3
    h = (ROOT / "native" / "instlib" / "cq_dual.h").read_text(encoding="utf-8")
    assert "void i1pro2_cq_dual_times(void *pp, cq_dual_times *out);" in h


def test_the_simulation_sends_the_pace(tmp_path, monkeypatch):
    from tests.test_i1pro2_dual_scan_ui import _c_pace_fields, _sim_events

    def script(s):
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe", uv_fault="uv_pass_too_fast", uv_fewest=2, uv_s=3.8)
        s.wait_event("error", after=i, kind="misread")
        i = s.event_index()
        s.send(cmd="retry")
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe", uv_fewest=3)
        s.wait_event("strip_read", after=i)
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
        s.wait_event("done", timeout=10)
        s.finish()

    s, *_ = _sim_events(tmp_path, monkeypatch, script)
    res = [e for e in s.events if e.get("event") == "dual_pass_result"]
    assert [(r["ok"], r["why"], r["fewest_per_patch"]) for r in res] == [
        (False, "uv_pass_too_fast", 2), (True, "", 3)]
    for r in res:
        assert _c_pace_fields() <= set(r)
    assert P.too_fast_text(res[0]) is not None and P.accepted_text(res[1], "A")[2] == P.CLOSE


# ---------------------------------------------------------------- the ruler line

@pytest.mark.parametrize("dual", [False, True])
def test_the_ruler_line_is_true_for_a_dual_measurement(dual):
    from workflow.ruler_session import RulerSession
    rs = RulerSession(ti1_path=None, dual=dual)
    lines = rs.on_session({"active": True, "instrument": "i1pro2", "firmware": 634})
    if dual:
        assert "how long each pass took" in lines[0]
        assert "how far, which way and how fast" not in lines[0]
    else:
        assert "how far, which way and how fast" in lines[0]


def test_the_manager_tells_the_ruler_session_about_the_dual_scan():
    src = (ROOT / "workflow" / "measure_manager.py").read_text(encoding="utf-8")
    i = src.index("self._ruler = RulerSession(")
    assert "dual=bool(params.engine_dual_args)" in src[i:i + 900]
    assert D is not None
