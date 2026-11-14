"""4.3.36: the i1Pro 2's paused Beta parts and the technical line of a
communication failure, on the app's side.

The helper decides the pause (native/chartread_helper/cq_beta_pause.h; the
wire is proved in tests/test_usb_failure_detail.py) and says so in its events;
the app:

* says it once in the Measure log, with a line per paused choice, and never
  for an i1Pro 3;
* keeps the stored choices (and the command line it passes) as they were;
* says the ruler check is paused, and writes no diagnostics file;
* writes a communication failure's USB detail into the app log and shows
  one technical line at the bottom of the Strip Read Failed window, with
  the window's buttons unchanged.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.settings import AppSettings                 # noqa: E402
from workflow import measurement_messages as M        # noqa: E402
from workflow.measure_manager import (                # noqa: E402
    MeasureManager, coms_failure_detail)

COMS_EVENT = {
    "event": "error", "kind": "coms", "detail": "",
    "inst_code": "0x00010072", "driver": "Communications failure",
    "usb_step": "measure_trigger", "usb_failures": 2,
    "usb": [{"step": "measure_trigger", "kind": "control", "code": "0xD4",
             "icom": "0x000200", "bytes": -1, "asked": 14, "tout_ms": 2000,
             "took_ms": 3, "at_ms": 4120, "trigger": 1},
            {"step": "measurement_read", "kind": "read", "code": "0x82",
             "icom": "0x004000", "bytes": 0, "asked": 1072000,
             "tout_ms": 21785, "took_ms": 21790, "at_ms": 25910,
             "trigger": 1}],
    "light": "off_slow", "light_to_trigger_ms": 12,
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


@pytest.fixture
def mgr(qapp, settings, monkeypatch):
    from core import i1pro2_lights_marker as marker
    monkeypatch.setattr(marker, "note_white_on", lambda *_a, **_k: None)
    monkeypatch.setattr(marker, "note_lights_off", lambda *_a, **_k: None)
    m = MeasureManager(ArgyllRunner(settings))
    m._lights_option = True
    return m


def _lights_lines(mgr, ev):
    lines = []
    mgr._on_lights_event(ev, lines.append)
    return lines


ACTIVE2 = {"event": "lights", "active": True, "instrument": "i1pro2",
           "signals": False, "during_reading": "off", "firmware": 634}


@pytest.mark.parametrize("sig,left", [(True, False), (False, True),
                                      (True, True)])
def test_a_paused_choice_gets_one_line_of_its_own(mgr, sig, left):
    ev = dict(ACTIVE2, paused_signals=sig, paused_during_reading=left)
    lines = _lights_lines(mgr, ev)
    # the true description (the ready light), then the paused line
    assert lines[0] == MeasureManager._i1pro2_lights_line(False, False)
    paused = [ln for ln in lines if "paused for the i1Pro 2" in ln]
    assert len(paused) == 1
    p = paused[0]
    assert ("result signals" in p) == sig
    assert ("Left on during a reading" in p) == left
    assert "The instrument lost communication with the computer" in p
    assert "The i1Pro 3 is not affected." in p
    assert "—" not in p
    # no firmware line: the signals are not in use
    assert not any("firmware" in ln for ln in lines)


def test_nothing_paused_says_nothing_new(mgr):
    lines = _lights_lines(mgr, dict(ACTIVE2))
    assert lines == [MeasureManager._i1pro2_lights_line(False, False)]


@pytest.mark.parametrize("sig,left", [(False, False), (True, False),
                                      (False, True), (True, True)])
def test_an_i1pro3_is_told_what_4_3_35_told_it(mgr, sig, left):
    ev = {"event": "lights", "active": True, "instrument": "i1pro3",
          "signals": sig, "during_reading": "on" if left else "off",
          "firmware": 105}
    lines = _lights_lines(mgr, ev)
    assert lines[0] == MeasureManager._i1pro3_lights_line(sig, left)
    assert not any("paused" in ln for ln in lines)


def test_the_stored_choices_and_the_command_line_are_untouched(settings):
    """The helper decides for an i1Pro 2 (Python cannot know the generation
    before the instrument is open), so what the app stores and passes is
    exactly 4.3.35's."""
    from ui.tabs.tab_measure import TabMeasure
    settings.set("i1pro2_lights_beta", True)
    settings.set("i1pro2_lights_signals", True)
    settings.set("i1pro2_lights_during_reading", True)
    settings.set("ruler_check_beta", True)
    src = Path(__file__).resolve().parent.parent / "ui" / "tabs" / "tab_measure.py"
    text = src.read_text(encoding="utf-8")
    assert 'p.engine_lights_signals = bool(\n            self._settings.get("i1pro2_lights_signals", True))' in text
    mm = (Path(__file__).resolve().parent.parent / "workflow" /
          "measure_manager.py").read_text(encoding="utf-8")
    assert 'eargs += ["--lights-signals"]' in mm
    assert 'eargs += ["--lights-during-reading"]' in mm
    assert 'eargs += ["--ruler"]' in mm
    assert settings.get("i1pro2_lights_signals") is True
    assert settings.get("i1pro2_lights_during_reading") is True
    assert settings.get("ruler_check_beta") is True
    assert TabMeasure is not None


def test_the_ruler_says_it_is_paused_and_writes_no_file(tmp_path):
    from workflow.ruler_session import RulerSession
    ti1 = tmp_path / "runs" / "run1" / "chart.ti1"
    ti1.parent.mkdir(parents=True)
    ti1.write_text("CTI1\n", encoding="utf-8")
    rs = RulerSession(ti1_path=ti1, verification=False)
    lines = rs.on_session({"event": "ruler", "active": False,
                           "why": "paused", "instrument": "i1pro2"})
    assert len(lines) == 1
    assert "paused for the i1Pro 2" in lines[0]
    assert "exactly as it is without the option" in lines[0]
    assert "On an i1Pro 3 the ruler check works as before." in lines[0]
    assert rs.on_end() == []
    assert not list(tmp_path.rglob("ruler_diagnostics_*"))


# ---------------------------------------------------------------------------
# A communication failure
# ---------------------------------------------------------------------------
def test_the_technical_line_names_the_step():
    line = coms_failure_detail(COMS_EVENT)
    assert line.startswith("measure trigger failed: USB control 0xD4, "
                           "trigger 1 (dark reading at strip start), ICOM "
                           "0x000200 USB write error")
    assert "then measurement data read failed: USB read 0x82" in line
    assert "ICOM 0x004000 timed out, 0/1072000 bytes" in line
    assert "light off_slow 12 ms before trigger 1" in line
    assert line.endswith("driver 0x00010072 Communications failure")
    assert "—" not in line


@pytest.mark.parametrize("step,word", [
    ("measurement_read", "measurement data read failed"),
    ("button_read", "button read failed"),
    ("light", "light command failed"),
    ("ruler_read", "ruler read failed"),
])
def test_each_step_has_its_words(step, word):
    ev = {"usb": [{"step": step, "kind": "read", "code": "0x99",
                   "icom": "0x000100", "bytes": 0, "asked": 1,
                   "tout_ms": 100, "took_ms": 1, "at_ms": 1, "trigger": 0}],
          "usb_failures": 1}
    assert coms_failure_detail(ev).startswith(word)


def test_the_scan_trigger_and_more_failures():
    ev = json.loads(json.dumps(COMS_EVENT))
    ev["usb"] = [dict(ev["usb"][1], trigger=2)]
    ev["usb_failures"] = 3
    line = coms_failure_detail(ev)
    assert "trigger 2 (the scan)" in line and "+2 more" in line


def test_an_event_without_detail_gives_no_line():
    assert coms_failure_detail({"event": "error", "kind": "coms",
                                "detail": ""}) == ""


def test_no_failed_transfer_seen_is_said():
    line = coms_failure_detail({"usb_step": "none", "usb": [],
                                "usb_failures": 0, "inst_code": "0x00010072",
                                "driver": "Communications failure"})
    assert line.startswith("no failed USB transfer seen")


def test_the_manager_logs_it_and_keeps_it_for_the_window(mgr, caplog):
    errors = []
    mgr.strip_error.connect(errors.append)
    with caplog.at_level(logging.WARNING, logger="workflow.measure_manager"):
        mgr._handle_engine_line(json.dumps(COMS_EVENT), lambda _l: None)
    assert errors == ["communication problem"]
    assert mgr.last_coms_detail == coms_failure_detail(COMS_EVENT)
    rec = [r.getMessage() for r in caplog.records
           if "communication failure" in r.getMessage()]
    assert rec and '"usb_step": "measure_trigger"' in rec[0]
    assert mgr.last_coms_detail in rec[0]


@pytest.fixture
def tab(qapp, settings, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(settings), settings)
    monkeypatch.setattr(type(t._manager), "engine_active",
                        property(lambda self: True))
    t._engine_read = {"A": False, "B": False}
    t._current_strip_letter = "A"
    monkeypatch.setattr(t._manager, "send_key", lambda k: None)
    monkeypatch.setattr(t, "_arm_key_watchdog", lambda: None)
    monkeypatch.setattr(t, "_on_strip_error_sound", lambda *_a: None)
    return t


def _open(tab, monkeypatch, reason):
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    seen = {}

    def run(dlg):
        seen["text"] = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        seen["buttons"] = [b.text() for b in dlg.findChildren(QPushButton)]
        return 0
    monkeypatch.setattr(QDialog, "exec", run)
    tab._on_strip_error(reason, False)
    return seen


def test_the_window_shows_the_line_at_the_bottom(tab, monkeypatch):
    before = _open(tab, monkeypatch, "communication problem")
    tab._manager.last_coms_detail = coms_failure_detail(COMS_EVENT)
    after = _open(tab, monkeypatch, "communication problem")
    title, body = M.M_STRIP_FAILED_COMS_DETAIL.render(
        detail=tab._manager.last_coms_detail)
    assert title == "Technical detail for a report"
    import html
    want = f"<small>{html.escape(title)}: {html.escape(body)}</small>"
    assert want not in before["text"]
    assert after["text"].rstrip().endswith(want)
    assert "The instrument lost communication with the computer." in after["text"]
    # nothing else changes: the same buttons, in the same order
    assert after["buttons"] == before["buttons"]


def test_a_misread_window_never_shows_it(tab, monkeypatch):
    tab._manager.last_coms_detail = coms_failure_detail(COMS_EVENT)
    seen = _open(tab, monkeypatch, "Too many patches")
    assert M.M_STRIP_FAILED_COMS_DETAIL.title not in seen["text"]


def test_the_message_is_proposed_and_its_detail_untranslated():
    assert M.M_STRIP_FAILED_COMS_DETAIL.id in M.PROPOSED
    assert M.M_STRIP_FAILED_COMS_DETAIL.body == "{detail}"


# ---------------------------------------------------------------------------
# Preferences > Beta: the help and the confirmations say it
# ---------------------------------------------------------------------------
def test_the_lights_confirmation_says_what_is_paused_and_names_no_version():
    from ui.dialogs.settings_dialog import i1pro2_lights_confirmation
    text = i1pro2_lights_confirmation()
    assert "4.3." not in text                  # the 4.3.35 review's nit
    assert "Below you can choose a ready light only instead" in text
    assert ("For the i1Pro 2, the green / red result signals and “Left on "
            "during a reading” are paused in this version") in text
    assert "The instrument lost communication with the computer" in text
    assert "shows its ready light as before" in text
    assert "has not been tried on a real i1Pro 2 or i1Pro 3 with ChromIQ yet" \
        in text
    assert "—" not in text


def test_the_lights_help_opens_with_the_pause():
    from ui.dialogs.settings_dialog import i1pro2_lights_help
    paras = i1pro2_lights_help().split("\n\n")
    assert paras[1].startswith("**Paused for the i1Pro 2 in this version: "
                               "the green / red result signals and “Left on "
                               "during a reading”.**")
    assert "Nothing changes for the i1Pro 3." in paras[1]
    assert "—" not in paras[1]


def test_the_ruler_help_and_confirmation_say_it_is_paused():
    from ui.dialogs.settings_dialog import (ruler_check_confirmation,
                                            ruler_check_help)
    paras = ruler_check_help().split("\n\n")
    assert paras[1].startswith("**Paused for the i1Pro 2 in this version.**")
    assert "exactly as with it off" in paras[1]
    assert "until it has been tried step by step on a real i1Pro 2" in paras[1]
    assert "nothing new is sent to it" in paras[1]
    conf = ruler_check_confirmation()
    assert ("For the i1Pro 2 the ruler check is paused in this version, until "
            "it has been tried step by step on a real instrument") in conf
    assert "An i1Pro 3 gets nothing new" in conf
    assert "—" not in paras[1] + conf


@pytest.mark.parametrize("ms,said", [(12, "light off_slow 12 ms before trigger 1"),
                                     (-40, "light off_slow 40 ms after trigger 1"),
                                     (0, "light off_slow at trigger 1"),
                                     (None, "light off_slow;")])
def test_the_light_timing_reads_the_right_way_round(ms, said):
    """Review nit 5: a light sent after the first trigger is "after", never
    "-40 ms before"."""
    ev = json.loads(json.dumps(COMS_EVENT))
    ev["light"] = "off_slow"
    ev["light_to_trigger_ms"] = ms
    line = coms_failure_detail(ev)
    assert said in line
    assert "-" not in line.split("light off_slow", 1)[1].split(";", 1)[0]
