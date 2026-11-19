"""4.3.50: what the app makes of the helper's shift refusal.

The helper refuses a strip read one patch out at an end with the misread's own
event (``chromiq_shift.c``, ``test_strip_shift_in_the_helper.py``): kind
"misread", the sentence "Readings moved by one patch at the start|end of the
strip (shift score S, limit L)" and a "shift" record. So the existing Strip
Read Failed window answers it, with the existing buttons, keys and sound; only
its text is the shift test's own (M-STRIP-FAILED-SHIFTED-START / -END), and
the Measure log names the score (M-STRIP-SHIFT-REFUSED).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.measure_pace import failure_kind, misread_kind   # noqa: E402
from workflow import measurement_messages as M        # noqa: E402

START = "Readings moved by one patch at the start of the strip (shift score 49.0, limit 10.0)"
END = "Readings moved by one patch at the end of the strip (shift score 23.5, limit 20.0)"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_the_helpers_sentence_picks_the_shift_texts():
    assert misread_kind(START) == "shifted_start"
    assert misread_kind(END) == "shifted_end"
    assert M.STRIP_FAILED_ADVICE["shifted_start"] is M.M_STRIP_FAILED_SHIFTED_START
    assert M.STRIP_FAILED_ADVICE["shifted_end"] is M.M_STRIP_FAILED_SHIFTED_END


def test_speed_is_not_blamed():
    """The pace note and the sound treat it as 'not a speed problem' (the
    strip-failed sound, not the slow-down cue)."""
    assert failure_kind(START) == "other" and failure_kind(END) == "other"


def test_the_window_says_what_happened_and_what_to_do():
    from ui.tabs.tab_measure import _strip_failed_advice_html
    html = _strip_failed_advice_html(START)
    assert M.M_STRIP_FAILED_SHIFTED_START.title in html
    assert "clean white paper between the label and the first patch" in html
    assert "shift score 49.0" in html
    html = _strip_failed_advice_html(END)
    assert M.M_STRIP_FAILED_SHIFTED_END.title in html
    assert "well past the last patch" in html


def test_the_texts_are_proposed_and_have_no_em_dash():
    for m in (M.M_STRIP_FAILED_SHIFTED_START, M.M_STRIP_FAILED_SHIFTED_END,
              M.M_STRIP_SHIFT_REFUSED):
        assert m.id in M.PROPOSED
        assert "—" not in m.title + m.body


def _manager():
    from workflow.measure_manager import MeasureManager
    sys.path.insert(0, str(Path(__file__).parent))
    from test_knut_5956210745_next_strip_after_a_read import _Runner
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._guided_state = "disabled"
    return m


def test_the_manager_raises_the_misread_window_and_logs_the_score(qapp):
    from test_knut_5956210745_next_strip_after_a_read import _feed
    m = _manager()
    errors, infos = [], []
    m.strip_error.connect(errors.append)
    m.info_message.connect(lambda cat, text: infos.append((cat, text)))
    _feed(m, {"event": "strip_ready", "strip": "C", "read": False, "all_done": False},
          {"event": "error", "kind": "misread", "detail": START, "button_retry": True,
           "shift": {"at": "start", "k": 3, "score": 49.0, "limit": 10.0}})
    assert errors == [START]
    assert m._at_retry_prompt
    assert len(infos) == 1 and infos[0][0] == "strip_shift"
    text = infos[0][1]
    assert text.startswith("Strip C was not kept") and "49.0" in text and "10.0" in text


def test_an_ordinary_misread_logs_no_shift_line(qapp):
    from test_knut_5956210745_next_strip_after_a_read import _feed
    m = _manager()
    infos = []
    m.info_message.connect(lambda cat, text: infos.append(cat))
    _feed(m, {"event": "strip_ready", "strip": "C", "read": False, "all_done": False},
          {"event": "error", "kind": "misread", "detail": "Too many patches",
           "button_retry": True})
    assert "strip_shift" not in infos
