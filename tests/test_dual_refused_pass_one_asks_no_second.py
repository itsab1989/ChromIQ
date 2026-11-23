"""4.3.58 (item 17): a refused FIRST pass of an i1Pro 2 dual strip asks for no
second pass.

Approved as a direction by Basti, 23 Nov 2026: "when the first pass is
refused, refuse at once, do not ask for the second pass, and ask the person to
read the first pass again". A tester read 10 second passes in one morning that
ChromIQ then threw away (4.3.57: M-DUAL-PASS-TWO-UNREAD "Read pass 2 anyway",
then "Strip Read Failed").

What is built (docs/design/i1pro2_dual_scan.md section 18):

* the refusal is said at once (M-DUAL-PASS-ONE-REFUSED, with the "Strip read
  failed" sound), and asks for ONE press in place, not a second pass: the
  instrument's ruler stream is closed only by the recorded UV trigger, so the
  press is still needed; nothing new goes to the instrument;
* the misread that follows opens no window: the tab sends Retry itself, and the
  strip prompt asks for pass 1 of the same strip again (M-DUAL-PASS-ONE-AGAIN);
* a first pass ArgyllCMS accepted still gets its second pass, and a second pass
  that is refused still opens "Strip Read Failed" (unchanged);
* the helper sends no blue "second pass due" after a refused first pass.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent


class _Sound:
    def __init__(self):
        self.played = []

    def play(self, event):
        self.played.append(event)

    def play_window(self, event):
        self.played.append(event)


class _Keys:
    """Records what the tab sends to the engine instead of sending it."""

    def __init__(self, manager):
        self.sent = []
        self._manager = manager

    def __call__(self, key):
        self.sent.append(key)


def _live_tab(tmp_path, monkeypatch):
    from tests.test_b202_the_i1pro_generation_is_read_right import _tab
    tab = _tab(tmp_path)
    tab._dual_reset()
    tab._dual_live = True
    tab._sound = _Sound()
    keys = _Keys(tab._manager)
    monkeypatch.setattr(tab._manager, "send_key", keys)
    windows = []

    def _no_window(dlg):
        from PyQt6.QtWidgets import QLabel
        windows.append(dlg.windowTitle())
        texts.append(" ".join(lb.text() for lb in dlg.findChildren(QLabel)))
        dlg.reject()
    texts = []
    monkeypatch.setattr(tab, "_exec_measurement_window", _no_window)
    tab._test_window_texts = texts
    return tab, keys, windows


def test_a_refused_first_pass_is_refused_at_once_and_asks_no_second_pass(
        qapp, tmp_path, monkeypatch):
    import core.sound as snd
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    tab._dual_pass_one("A")
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    head = tab._status_bar_lbl.text()
    assert head == ("Strip A: pass 1 did not read. "
                    "Press the button once, then read pass 1 again")
    assert "pass 2" not in head and "Read pass 2" not in tab._log.toPlainText()
    assert "does not ask for its second pass" in tab._log.toPlainText()
    assert tab._sound.played == [snd.STRIP_FAIL]
    tab.close()


def test_the_misread_after_it_opens_no_window_and_pass_one_is_read_again(
        qapp, tmp_path, monkeypatch):
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    tab._dual_pass_one("A")
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    tab._on_dual_pass_result({"what": "strip", "strip": "A", "ok": False,
                              "why": "lamp"})
    played = list(tab._sound.played)
    tab._on_strip_error("Too many patches", button=True)
    assert windows == [], "no Strip Read Failed window after a refused pass 1"
    assert keys.sent == ["\r"], "Retry is sent by the tab itself"
    assert tab._sound.played == played, "the failure was heard once, at pass 1"
    # the strip prompt that follows: pass 1 of the same strip again, with why
    tab._dual_pass_one("A")
    assert tab._status_bar_lbl.text() == "Strip A, pass 1 of 2 again (lamp)"
    assert "The first pass did not read (Too many patches)" in (
        tab._status_bar_lbl.toolTip() + tab._log.toPlainText())
    # ...and then the strip goes on as always: pass 1, then pass 2
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": True})
    assert tab._status_bar_lbl.text() == "Strip A, pass 2 of 2 (UV light)"
    # a later misread (a refused SECOND pass) opens the window as before
    tab._on_dual_pass_result({"what": "strip", "strip": "A", "ok": False,
                              "why": "uv_pass_wrong_strip"})
    tab._on_strip_error("Misread", button=True)
    assert windows == ["Strip Read Failed"]
    tab._dual_pass_one("A")
    assert tab._status_bar_lbl.text() == "Strip A, pass 1 of 2 (lamp)"
    tab.close()


def test_an_accepted_first_pass_still_gets_its_second_pass(
        qapp, tmp_path, monkeypatch):
    """A first pass ArgyllCMS accepted, even a doubtful one ("Use Anyway",
    ChromIQ's slip check: both are asked only after both passes), gets its
    second pass, and a failure then is the ordinary window. Unchanged since
    4.3.57, so this passes against 4.3.57 too, by design."""
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    tab._dual_pass_one("B")
    tab._on_dual_pass({"strip": "B", "pass": "uv", "of": 2, "lamp_ok": True})
    assert tab._status_bar_lbl.text() == "Strip B, pass 2 of 2 (UV light)"
    assert tab._sound.played == []
    tab._on_strip_error("Misread", button=True)
    assert windows == ["Strip Read Failed"]
    assert keys.sent == ["\r"]       # the window's Retry (rejected = retry)
    tab.close()


def test_another_strip_after_the_refusal_is_not_called_again(
        qapp, tmp_path, monkeypatch):
    """"Again" belongs to the strip whose pass 1 was refused only."""
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    tab._dual_pass_one("A")
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    tab._on_strip_error("Too many patches", button=True)
    tab._dual_pass_one("C")
    assert tab._status_bar_lbl.text() == "Strip C, pass 1 of 2 (lamp)"
    tab.close()


def _refused_pass_one(tab, strip="A"):
    """Strip prompt, then a dual_pass with lamp_ok false, as the helper sends
    them after a first pass ArgyllCMS refused."""
    tab._dual_pass_one(strip)
    tab._on_dual_pass({"strip": strip, "pass": "uv", "of": 2, "lamp_ok": False})
    tab._on_dual_pass_result({"what": "strip", "strip": strip, "ok": False,
                              "why": "lamp"})


def test_a_connection_lost_during_the_press_shows_its_window_one_step_later(
        qapp, tmp_path, monkeypatch):
    """What really happens (chromiq_dualdev.c cq_dd_strip, review of
    4.3.58-a, finding 3): after a refused first pass the helper reports the
    FIRST pass's error whatever the press returned (lamp_ok false sets
    why = "lamp" and keeps *rv), so a connection lost during the press reaches
    the tab as the lamp's misread text, never as "communication". The tab
    sends Retry; the helper's next lamp pass then fails on the lost
    connection, and THAT misread opens the connection window, at the Retry,
    one step later. The helper is deliberately not changed for this (it would
    need another safety review)."""
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    _refused_pass_one(tab)
    # the press: the connection is lost, the helper still sends the lamp's text
    tab._on_strip_error("Too many patches", button=True)
    assert windows == [], "no window yet: the helper said the lamp's misread"
    assert keys.sent == ["\r"], "Retry is sent"
    # the next step: the strip prompt for pass 1 again, then its lamp pass
    # fails on the lost connection
    tab._dual_pass_one("A")
    assert tab._status_bar_lbl.text() == "Strip A, pass 1 of 2 again (lamp)"
    tab._on_strip_error("Strip read failed due to communication problem")
    assert windows == ["Strip Read Failed"]
    assert "lost communication with the computer" in tab._test_window_texts[-1]
    tab.close()


def test_a_stop_during_the_press_keeps_its_window(qapp, tmp_path, monkeypatch):
    """Without a Stop the misread after a refused pass 1 is answered with
    Retry and no window; with a Stop under way the window opens and answers
    it, as in 4.3.57."""
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    _refused_pass_one(tab)
    tab._on_strip_error("Too many patches", button=True)
    assert (windows, keys.sent) == ([], ["\r"])
    _refused_pass_one(tab)
    monkeypatch.setattr(tab._manager, "_user_quit", True, raising=False)
    tab._on_strip_error("Too many patches", button=True)
    assert windows == ["Strip Read Failed"]
    tab._dual_pass_one("A")
    assert "again" not in tab._status_bar_lbl.text()
    tab.close()


def test_patch_by_patch_is_unchanged(qapp, tmp_path, monkeypatch):
    """The same events that end a dual STRIP without a window open the
    "Patch Read Failed" window when reading patch by patch (the helper never
    sends dual_pass there, cq_dd_spot; the tab does not rely on that)."""
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    _refused_pass_one(tab)
    tab._on_strip_error("Misread", button=True)
    assert (windows, keys.sent) == ([], ["\r"])
    tab._spot_session = True
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    tab._on_strip_error("Misread", button=True)
    assert windows == ["Patch Read Failed"]
    tab.close()


def test_the_failed_strip_is_timed_by_its_lamp_pass_not_the_press(
        qapp, tmp_path, monkeypatch):
    """The pace panel lists the failed strip with its LAMP pass's seconds,
    not the short press that closes the instrument's ruler stream."""
    tab, keys, windows = _live_tab(tmp_path, monkeypatch)
    tab._last_strip_patches = 20
    tab._current_strip_letter = "A"
    tab._dual_pass_one("A")
    tab._on_scan_started()                 # the lamp pass: button ...
    tab._on_scan_ready()                   # ... and beep,
    tab._scan_started_at -= 3.5            # 3.5 s before its end
    tab._on_dual_pass({"strip": "A", "pass": "uv", "of": 2, "lamp_ok": False})
    tab._on_scan_started()                 # the one press: button and beep
    tab._on_scan_ready()
    tab._report_failed_strip_pace("Too many patches")
    assert tab._pace_times["A"][0] == pytest.approx(3.5, abs=0.3)
    tab.close()


def test_the_texts_are_proposed_translated_and_carry_no_em_dash():
    import json
    from workflow import measurement_messages as M
    for msg in (M.M_DUAL_PASS_ONE_REFUSED, M.M_DUAL_PASS_ONE_AGAIN):
        assert not msg.approved, "stays PROPOSED (§M)"
        title, body = msg.render(strip="A", reason="Too many patches")
        assert "—" not in title + body
        assert msg.id in M.CATALOGUE
    doc = (ROOT / "docs" / "design" / "unified_measurement_management.md"
           ).read_text(encoding="utf-8")
    assert "### M-DUAL-PASS-ONE-REFUSED · PROPOSED" in doc
    assert "### M-DUAL-PASS-ONE-AGAIN · PROPOSED" in doc
    keys = [M.M_DUAL_PASS_ONE_REFUSED.title, M.M_DUAL_PASS_ONE_REFUSED.body,
            M.M_DUAL_PASS_ONE_AGAIN.title, M.M_DUAL_PASS_ONE_AGAIN.body]
    for code in ("de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
                 "sv", "uk", "zh_CN"):
        d = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(
            encoding="utf-8"))
        for k in keys:
            assert d.get(k), (code, k)
            assert set(re.findall(r"\{\w+\}", d[k])) == set(re.findall(r"\{\w+\}", k))


def test_the_helper_sends_no_blue_after_a_refused_first_pass():
    """chromiq_dualdev.c passes lamp_ok on; cq_lights_second_pass_due returns
    before the blue is due when the first pass was refused, and says so."""
    dd = (ROOT / "native" / "chartread_helper" / "chromiq_dualdev.c").read_text(
        encoding="utf-8")
    cr = (ROOT / "native" / "chartread_helper" / "chromiq_chartread.c").read_text(
        encoding="utf-8")
    assert "cq_lights_second_pass_due(lamp_ok);" in dd
    fn = cr.split("static void cq_lights_second_pass_due(int lamp_ok) {")[1].split("\n}\n")[0]
    refused = fn.index("if (!lamp_ok)")
    assert refused < fn.index("cq_lights_blue_due = msec_time()")
    assert '\\"why\\":\\"lamp_refused\\"' in fn[refused:]
    # the wire is unchanged: the UV pass is still waited for after a refused pass 1
    assert "it->read_strip(it, \"STRIP\", npatch, (char *)strip" in dd
    ext = (ROOT / "native" / "chartread_helper" / "chromiq_ext.h").read_text(
        encoding="utf-8")
    assert '"chromiq-chartread 2026-11-23b ' in ext and "+lamp-refused-no-blue" in ext
    binary = ROOT / "native" / "chromiq-chartread"
    if binary.exists():
        data = binary.read_bytes()
        assert b"chromiq-chartread 2026-11-23b " in data and b"lamp_refused" in data


SIM = ROOT / "tests" / "helpers" / "dual_sim_helper.py"
needs_helper = pytest.mark.skipif(
    not (ROOT / "native" / "chromiq-chartread").exists(), reason="engine not built")


@needs_helper
def test_the_simulation_says_no_blue_after_a_refused_first_pass(tmp_path, monkeypatch):
    import tests.helpers.replay_tools as rt
    from tests.test_i1pro2_dual_scan_engine import _chart, _dual_args
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_TILE_S", "0.2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_PASS_S", "0.05")
    monkeypatch.setattr(rt, "HELPER", SIM)
    base, rp, truth, steps = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with rt.ReplaySession(base, rp, extra_args=_dual_args(cdir) + [
            "--dual-chosen", "M2", "--i1pro2-lights", "--lights-signals",
            "--lights-blue-after-ms", "50"]) as s:
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe", lamp_fault="misread", reason="Too many patches")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe")                       # the one press
        s.wait_event("error", after=i, kind="misread")
        refused = list(s.events[i:])
        i = s.event_index()
        s.send(cmd="retry")
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("dual_pass", after=i)
        import time
        time.sleep(0.3)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=i)
        good = list(s.events[i:])
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
        s.wait_event("done", timeout=10, after=i)
        s.finish()
    lights = [e for e in refused if e.get("event") == "lights"]
    assert {"event": "lights", "second_pass": "skipped", "why": "lamp_refused"} in lights
    assert not any(str(e.get("sent", "")).startswith("blue") for e in lights)
    assert [e["lamp_ok"] for e in refused if e.get("event") == "dual_pass"] == [False]
    assert any(str(e.get("sent", "")).startswith("blue") for e in good
               if e.get("event") == "lights")


@needs_helper
def test_the_simulation_reports_the_first_pass_error_whatever_the_press_returned(
        tmp_path, monkeypatch):
    """As the real helper (chromiq_dualdev.c cq_dd_strip: lamp_ok false sets
    why = "lamp" and keeps the lamp pass's code): a press that itself fails,
    here as a lost connection would, still ends in the FIRST pass's misread."""
    import json
    import tests.helpers.replay_tools as rt
    from tests.test_i1pro2_dual_scan_engine import _chart, _dual_args
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_TILE_S", "0.2")
    monkeypatch.setenv("CHROMIQ_DUAL_SIM_PASS_S", "0.05")
    monkeypatch.setattr(rt, "HELPER", SIM)
    base, rp, truth, steps = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with rt.ReplaySession(base, rp, extra_args=_dual_args(cdir) + [
            "--dual-chosen", "M2"]) as s:
        s.wait_event("strip_ready", timeout=10)
        i = s.event_index()
        s.send(cmd="swipe", lamp_fault="misread", reason="Too many patches")
        s.wait_event("dual_pass", after=i)
        s.send(cmd="swipe", uv_fault="uv_pass_missing")   # the press fails too
        err = s.wait_event("error", after=i, kind="misread")
        res = s.wait_event("dual_pass_result", after=i)
        i = s.event_index()
        s.send(cmd="retry")                  # the tab's own Retry
        s.wait_event("strip_ready", after=i)
        i = s.event_index()
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
        s.wait_event("done", timeout=10, after=i)
        s.finish()
    assert "Too many patches" in json.dumps(err)
    assert (res.get("ok"), res.get("why")) == (False, "lamp")
