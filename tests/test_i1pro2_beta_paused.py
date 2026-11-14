"""The i1Pro 2's Beta parts since 4.3.36 and the technical line of a
communication failure, on the app's side.

4.3.36 paused both in the helper (native/chartread_helper/cq_beta_pause.h);
4.3.37 ended the lights' pause and 4.3.38 the ruler check's, and the header
is gone (the wire: tests/test_usb_failure_detail.py). The app:

* says the lights' quiet time once in the Measure log, never for an i1Pro 3;
* keeps the stored choices (and the command line it passes) as they were;
* opens an i1Pro 2 ruler session like an i1Pro 3 one, with its file;
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


def test_the_quiet_time_is_said_once_per_session(mgr):
    """4.3.37: the i1Pro 2's driver holds a trigger after a light change (the
    helper's held_ms event): the Measure log says so once, the app log every
    time; it is never taken for a session line."""
    lines = _lights_lines(mgr, dict(ACTIVE2))
    for _ in range(3):
        lines += _lights_lines(mgr, {"event": "lights", "held_ms": 1800})
    said = [ln for ln in lines if "wait a moment before it measured" in ln]
    assert len(said) == 1
    assert "about two seconds" in said[0] and "—" not in said[0]
    # 4.3.37 review (M1): what to do while it waits
    assert "keep the instrument still on the white paper" in said[0]
    assert "Start sliding at the beep." in said[0]
    assert not any("leaves them alone" in ln for ln in lines)


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


def test_an_i1pro2_ruler_session_is_active_and_writes_its_file(tmp_path):
    """4.3.38: the ruler check is back for the i1Pro 2 (4.3.36 and 4.3.37
    paused it): an active session opens as for the i1Pro 3, and the "paused"
    line is gone from the app."""
    import inspect
    from workflow import ruler_session
    from workflow.ruler_session import RulerSession
    assert '"paused"' not in inspect.getsource(ruler_session)
    ti1 = tmp_path / "runs" / "run1" / "chart.ti1"
    ti1.parent.mkdir(parents=True)
    ti1.write_text("CTI1\n", encoding="utf-8")
    rs = RulerSession(ti1_path=ti1, verification=False)
    lines = rs.on_session({"event": "ruler", "active": True,
                           "instrument": "i1pro2", "firmware": 634,
                           "sensor": True, "argyll": "3.5.0"})
    assert lines and not any("paused" in ln for ln in lines)
    assert rs.active and rs.diagnostics_path() is not None


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
def test_the_lights_confirmation_says_the_new_order_and_names_no_version():
    from ui.dialogs.settings_dialog import i1pro2_lights_confirmation
    text = i1pro2_lights_confirmation()
    assert "4.3." not in text
    assert "paused" not in text
    assert "Below you can choose a ready light only instead" in text
    assert "On an i1Pro 2, ChromIQ now follows the order X-Rite's i1Profiler" \
        in text
    assert "about two seconds" in text
    assert "has not yet been confirmed on a real i1Pro 2" in text
    assert "The instrument lost communication with the computer" in text
    assert "—" not in text


def test_the_lights_help_opens_with_the_new_order():
    from ui.dialogs.settings_dialog import i1pro2_lights_help
    help_ = i1pro2_lights_help()
    paras = help_.split("\n\n")
    assert paras[1].startswith("**New for the i1Pro 2: the lights follow "
                               "X-Rite's own order.**")
    assert "not yet been confirmed on a real i1Pro 2" in paras[1]
    assert "page read without a single" in paras[1]
    assert "keep the instrument still" in paras[1]
    assert "Start sliding at the beep." in paras[1]
    assert "paused for the i1Pro 2" not in help_.replace(
        "paused for it", "")
    # the i1Pro 3: one honest sentence
    assert ("The i1Pro 3's lights have not been confirmed on a real i1Pro 3: "
            "if “The instrument lost communication with the computer” appears "
            "with this option on, please switch it off and tell us.") in help_
    assert "On an i1Pro 2 both choices work the same" in help_
    assert "—" not in help_


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
    # review nit 6: the file is written only where the check runs
    assert ("Each measurement with an i1Pro 3 writes a small diagnostics "
            "file") in conf
    assert "With an i1Pro 2 no file is written while the check is paused." \
        in conf
    assert "Each measurement writes" not in conf
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


def test_the_help_claims_only_what_is_true_about_the_moments():
    """4.3.37 review (M2): the same recorded patterns at the same moments;
    two situations on an i1Pro 2 differ in what was showing before."""
    from ui.dialogs.settings_dialog import i1pro2_lights_help
    h = i1pro2_lights_help()
    assert "each at the moment i1Profiler sent it" not in h
    assert "light patterns seen in those recordings, at the moments" in h
    assert "two situations differ from the recordings" in h
    assert "a calibration that comes after the first one" in h
    assert "under the steady white of connecting" in h
