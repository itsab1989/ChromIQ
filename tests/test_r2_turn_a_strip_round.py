"""R2 (4.3.39): "Turn this strip round" in the back-to-front question.

jctay (forum 150222 / 150236): on his fixed-order chart strip 9 came back
"filed back to front" on every pass, and M-STRIP-REVERSED offered only
Re-measure / Keep it / Stop, so he went round seven times. R1 removes that
loop on his chart; this button is for the cases left. Proved here:

* the engine: {"cmd":"turn","strip":S} reverses the readings filed under S
  (in the saved .ti3 too), answers strip_turned with S's patches in the new
  order, stays on the strip it was on, refuses a strip with nothing read, and
  says it can ("turn" in session_start and --caps);
* the manager sends it only when the engine can, holds it while the engine is
  mid-swipe or at a question, and learns the turned reading;
* the window offers the button only for a strip filed back to front IN STEP
  with an engine that can turn it, with M-STRIP-REVERSED-TURN's text; a strip
  that also slipped, or an older engine, keeps M-STRIP-REVERSED and its three
  buttons; nothing is turned without the click.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
sys.path.insert(0, str(Path(__file__).parent))
import strip_nine_fixture as nine  # noqa: E402
from replay_tools import HELPER, ReplaySession  # noqa: E402
from workflow import measurement_messages as M  # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


@pytest.fixture
def chart(tmp_path):
    base = tmp_path / "nine"
    nine.write_chart(base)
    return base, nine.write_replay(tmp_path / "replay.txt")


def _goto(s, strip):
    i = s.event_index()
    s.send(cmd="goto", strip=strip)
    s.wait_event("strip_ready", after=i, strip=strip)


@needs_helper
def test_the_engine_turns_a_strip_round_and_saves_it(chart):
    base, replay = chart
    want = nine.reading_of(nine.SICK_ROW)
    # -B: a strip read from the far end is filed as read, i.e. back to front
    with ReplaySession(base, replay, extra_args=["-S", "-B"]) as s:
        st = s.wait_event("session_start")
        assert st["turn"] is True
        s.wait_event("strip_ready")
        _goto(s, "9")
        i = s.event_index()
        s.send(cmd="swipe", reversed=True)
        ev = s.wait_event("strip_read", after=i)
        assert ev["patches"][0]["xyz"][1] == pytest.approx(want[-1][1], abs=1e-3)
        s.wait_event("strip_ready", after=i, strip="10")
        i = s.event_index()
        s.send(cmd="turn", strip="9")
        t = s.wait_event("strip_turned", after=i)
        assert t["strip"] == "9"
        assert [p["loc"] for p in t["patches"]] == [f"9{c}" for c in nine.LETTERS]
        for p, w in zip(t["patches"], want):
            assert p["xyz"] == pytest.approx(list(w), abs=1e-3)
        # the reader stays where it was
        assert s.wait_event("strip_ready", after=i)["strip"] == "10"
        # a strip with nothing read is refused, and nothing else moves
        i = s.event_index()
        s.send(cmd="turn", strip="12")
        assert s.wait_event("turn_refused", after=i)["strip"] == "12"
        i = s.event_index()
        s.send(cmd="quit")
        try:
            s.wait_event("strip_interrupted", timeout=3, after=i)
            s.send(cmd="quit")
        except TimeoutError:
            pass
        s.finish()
    ti3 = base.with_suffix(".ti3").read_text(encoding="latin-1")
    row = next(l for l in ti3.splitlines() if '"9A"' in l).split()
    assert float(row[-3]) == pytest.approx(want[0][0], abs=1e-3) or \
        f"{want[0][0]:.4f}"[:5] in " ".join(row)


@needs_helper
def test_the_caps_say_turn():
    import subprocess
    out = subprocess.run([str(HELPER), "--caps"], capture_output=True,
                         text=True, encoding="utf-8", timeout=30).stdout
    assert "turn" in json.loads(out.strip().splitlines()[-1])["caps"]


# ---- the manager -------------------------------------------------------------

def _manager():
    from workflow.measure_manager import MeasureManager
    from test_knut_5956210745_next_strip_after_a_read import _Runner
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._guided_state = "disabled"
    return m


def test_the_manager_sends_turn_only_when_the_engine_can(qapp):
    m = _manager()
    sent = []
    m.send_command = sent.append
    assert m.turn_strip("9") is False and sent == []     # an older engine
    m._engine_turns = True
    assert m.turn_strip("9") is True
    assert sent == [{"cmd": "turn", "strip": "9"}]
    m._spot_mode = True
    assert m.turn_strip("9") is False                    # patch by patch


def test_a_turn_waits_for_the_strip_menu(qapp):
    m = _manager()
    sent = []
    m.send_command = sent.append
    m._engine_turns = True
    m._scan_in_progress = True
    assert m.turn_strip("9") is True and sent == []
    m._scan_in_progress = False
    m._flush_held_turn()
    assert sent == [{"cmd": "turn", "strip": "9"}]


def test_strip_turned_is_learnt_and_passed_on(qapp):
    from test_knut_5956210745_next_strip_after_a_read import _feed
    m = _manager()
    got = []
    m.strip_turned.connect(got.append)
    pats = [{"loc": f"9{c}", "xyz": [10.0 + k, 11.0, 12.0], "exyz": [1, 1, 1],
             "de": 1.0} for k, c in enumerate("AB")]
    _feed(m, {"event": "session_start", "chart": "", "turn": True,
              "strips": [{"strip": "9", "read": True}]})
    assert m._engine_turns is True
    _feed(m, {"event": "strip_turned", "strip": "9", "patches": pats})
    assert got and got[0]["strip"] == "9" and got[0]["turned"] is True
    assert got[0]["patches"] == pats


# ---- the window --------------------------------------------------------------

def _tab(monkeypatch, can_turn):
    from PyQt6.QtWidgets import QLabel, QPushButton
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    seen = {}
    monkeypatch.setattr(tab._manager, "can_turn_strips", lambda: can_turn)
    turned, went = [], []
    monkeypatch.setattr(tab._manager, "turn_strip",
                        lambda st: turned.append(st) or True)
    monkeypatch.setattr(tab._manager, "goto_strip", went.append)
    seen["click"] = None

    def grab(dlg):
        seen["labels"] = [lb.text() for lb in dlg.findChildren(QLabel)]
        seen["buttons"] = [b.text() for b in dlg.findChildren(QPushButton)]
        from PyQt6.QtWidgets import QHBoxLayout
        row = dlg.findChildren(QHBoxLayout)[-1]
        seen["row"] = [row.itemAt(i).widget().text() for i in range(row.count())
                       if row.itemAt(i).widget() is not None]
        if seen["click"]:
            for b in dlg.findChildren(QPushButton):
                if b.text() == seen["click"]:
                    b.click()
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", grab)
    return tab, seen, turned, went


FINDING = {"strip": "9", "offset": 0, "reversed": True, "whole": True,
           "first": "9A", "last": "9L", "base": 48.2, "best": 2.1}


def test_the_window_offers_turn_for_a_strip_in_step(qapp, monkeypatch):
    tab, seen, turned, went = _tab(monkeypatch, True)
    tab._on_strip_partly_misaligned(dict(FINDING))
    text = " ".join(seen["labels"])
    assert seen["buttons"] == ["Re-measure this strip", "Keep it", "Stop",
                               "Turn this strip round"]
    # on screen it stands between Re-measure and Keep it
    assert seen["row"][:3] == ["Re-measure this strip",
                               "Turn this strip round", "Keep it"]
    assert "Turn this strip round: keep these readings, but turn them round" \
        in text
    assert "slips by one or two patches" not in text
    assert turned == [] and went == []        # nothing without the click
    tab.deleteLater()


def test_the_click_turns_it(qapp, monkeypatch):
    tab, seen, turned, went = _tab(monkeypatch, True)
    seen["click"] = "Turn this strip round"
    tab._on_strip_partly_misaligned(dict(FINDING))
    assert turned == ["9"] and went == []
    tab.deleteLater()


@pytest.mark.parametrize("can_turn,offset", [(False, 0), (True, 1), (True, -2)])
def test_no_turn_without_an_engine_or_for_a_slipped_strip(qapp, monkeypatch,
                                                          can_turn, offset):
    tab, seen, turned, _went = _tab(monkeypatch, can_turn)
    tab._on_strip_partly_misaligned(dict(FINDING, offset=offset))
    assert "Turn this strip round" not in seen["buttons"]
    assert seen["buttons"][:2] == ["Re-measure this strip", "Keep it"]
    assert "Turn this strip round" not in " ".join(seen["labels"])
    tab.deleteLater()


def test_the_turned_strip_is_logged_and_judged(qapp, monkeypatch):
    tab, _seen, _t, _w = _tab(monkeypatch, True)
    judged = []
    monkeypatch.setattr(tab, "_on_strip_measured", judged.append)
    tab._session_live = True
    ev = {"event": "strip_read", "strip": "9", "turned": True,
          "patches": [{"loc": "9A", "xyz": [1, 1, 1]}]}
    tab._on_strip_turned(ev)
    assert judged == [ev]
    assert "Strip 9: as you asked, its readings were turned round" in \
        tab._log.toPlainText()
    tab.deleteLater()


def test_the_texts_are_proposed():
    assert M.M_STRIP_REVERSED_TURN.id in M.PROPOSED
    assert M.M_STRIP_TURNED.id in M.PROPOSED
    _t, body = M.M_STRIP_REVERSED_TURN.render(
        strip="9", first="9A", last="9L", lead_line="", base="1", best="1",
        middle_line="", remeasure="R", turn="T", keep="K", stop="S")
    assert "\nT: keep these readings" in body and "\nK: keep this reading" in body
    assert "—" not in body


def test_the_text_agrees_with_closing_the_window():
    """Review of 4.3.39: Escape / the X keeps the reading (closing answers
    nothing), so the text no longer says the strip "should not stay"."""
    _t, body = M.M_STRIP_REVERSED_TURN.render(
        strip="9", first="9A", last="9L", lead_line="", base="1", best="1",
        middle_line="", remeasure="R", turn="T", keep="K", stop="S")
    assert "should not stay as it is" not in body
    assert "K: keep this reading as it is. Closing this window does the same." in body
