"""B1 and M1 (Basti, 2026-10-21): the Strip Read Failed window.

* Each error the drivers report gets its own cause and remedy
  (M-STRIP-FAILED-*), instead of one text for all that told "Too many patches"
  to scan more slowly.
* When the engine says the connected instrument's button can answer the window
  ("button_retry": true on its misread event), the window says so
  (M-STRIP-FAILED-BUTTON), and a press reported by the engine
  ({"event":"switch"}) clicks the window's own Retry. Never within 0.3 s of the
  window opening, never with no window open, never for a patch or a lost
  connection.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, QTimer            # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.measure_pace import misread_kind            # noqa: E402
from core.settings import AppSettings                 # noqa: E402
from workflow import measurement_messages as M        # noqa: E402

#: The drivers' own sentences (i1pro.c:455-475, i1pro3.c:419-439, munki.c:465-485).
DRIVER_SENTENCES = {
    "Too many patches": "too_many",
    "Not enough patches": "too_few",
    "Reading is inconsistent": "inconsistent",
    "Swipe didn't start and end on the media": "edges",
    "Not enough samples per patch - Slow Down!": "too_fast",
    "Reading is too short": "other",
    "Number of patches to match is wrong": "other",
    "Light level is too low": "other",
    "White calibration reading is inconsistent": "other",
    "misread": "other",
    "": "other",
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    monkeypatch.setattr(type(t._manager), "engine_active",
                        property(lambda self: True))
    t._engine_read = {"A": False, "B": False}
    t._current_strip_letter = "A"
    sent = []
    monkeypatch.setattr(t._manager, "send_key", lambda k: sent.append(k))
    monkeypatch.setattr(t._manager, "skip_current_strip", lambda: sent.append("skip"))
    monkeypatch.setattr(t, "_arm_key_watchdog", lambda: None)
    monkeypatch.setattr(t, "_on_strip_error_sound", lambda *_a: None)
    t._sent = sent
    return t


# ---------------------------------------------------------------------------
# which text
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sentence,kind", sorted(DRIVER_SENTENCES.items()))
def test_each_driver_sentence_gets_its_own_text(sentence, kind):
    assert misread_kind(sentence) == kind


def test_every_kind_has_a_proposed_message_of_its_own():
    kinds = set(DRIVER_SENTENCES.values())
    assert set(M.STRIP_FAILED_ADVICE) == kinds
    ids = [m.id for m in M.STRIP_FAILED_ADVICE.values()]
    assert len(set(ids)) == len(ids)
    for m in M.STRIP_FAILED_MESSAGES:
        assert m.id in M.PROPOSED, m.id


@pytest.mark.parametrize("kind", sorted(M.STRIP_FAILED_ADVICE))
def test_each_text_names_the_drivers_words_and_says_what_to_do(kind):
    title, body = M.STRIP_FAILED_ADVICE[kind].render(reason="XYZ sentence")
    assert "{" not in title + body
    assert "What to do:" in body
    assert body.rstrip().endswith("What the instrument reported: XYZ sentence")
    assert "—" not in title + body          # no em dash (CLAUDE.md)
    assert "white paper" in body


def test_too_many_patches_is_no_longer_told_to_scan_more_slowly():
    """The old text for every error: 'try scanning more slowly'. For "Too many
    patches" that is the wrong way (core.measure_pace: hesitant, not hurried)."""
    _t, body = M.M_STRIP_FAILED_TOO_MANY.render(reason="Too many patches")
    assert "more slowly" not in body
    assert "similar colours" in body and "small" in body
    assert "even speed" in body


def test_only_the_inconsistent_text_points_at_the_tolerance():
    for kind, msg in M.STRIP_FAILED_ADVICE.items():
        _t, body = msg.render(reason="r")
        assert ("Patch consistency tolerance (-T)" in body) == (kind == "inconsistent"), kind


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------
def _open(tab, monkeypatch, reason, button, during=None):
    """Open the real window; *during(dlg)* runs inside its event loop."""
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton
    seen = {}
    real_exec = QDialog.exec

    def run(dlg):
        seen["text"] = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        seen["labels"] = [b.text() for b in dlg.findChildren(QPushButton)]
        seen["window"] = getattr(tab, "_strip_error_window", None)
        if during is None:
            return 0
        QTimer.singleShot(0, lambda: during(dlg))
        QTimer.singleShot(4000, dlg.reject)          # never hang the suite
        return real_exec(dlg)
    monkeypatch.setattr(QDialog, "exec", run)
    tab._on_strip_error(reason, button)
    return seen


@pytest.mark.parametrize("sentence", ["Too many patches", "Not enough patches",
                                      "Reading is inconsistent",
                                      "Swipe didn't start and end on the media",
                                      "Something else entirely"])
def test_the_window_shows_the_text_for_its_error(tab, monkeypatch, sentence):
    seen = _open(tab, monkeypatch, sentence, False)
    title, _b = M.STRIP_FAILED_ADVICE[misread_kind(sentence)].render(reason=sentence)
    assert f"<b>{title}</b>" in seen["text"]
    for other in M.STRIP_FAILED_ADVICE.values():
        if other.title != title:
            assert f"<b>{other.title}</b>" not in seen["text"]


def test_the_button_is_mentioned_only_when_the_instrument_supports_it(tab, monkeypatch):
    button_title = M.M_STRIP_FAILED_BUTTON.title
    assert button_title in _open(tab, monkeypatch, "Too many patches", True)["text"]
    assert button_title not in _open(tab, monkeypatch, "Too many patches", False)["text"]


def test_the_button_is_never_mentioned_for_a_lost_connection(tab, monkeypatch):
    seen = _open(tab, monkeypatch, "communication problem", True)
    assert M.M_STRIP_FAILED_BUTTON.title not in seen["text"]
    assert seen["window"] is None


def test_the_button_is_never_offered_reading_patch_by_patch(tab, monkeypatch):
    tab._spot_session = True
    seen = _open(tab, monkeypatch, "Too many patches", True)
    assert M.M_STRIP_FAILED_BUTTON.title not in seen["text"]
    assert seen["window"] is None


def test_a_press_is_the_windows_own_retry(tab, monkeypatch):
    def press(dlg):
        tab._strip_error_window["shown"] -= 1.0      # past the debounce
        tab._manager.instrument_button.emit()
    _open(tab, monkeypatch, "Too many patches", True, during=press)
    assert tab._sent == ["\r"], tab._sent            # exactly what Retry sends
    assert tab._strip_error_window is None


def test_a_press_within_the_debounce_is_ignored(tab, monkeypatch):
    """The press (or release) that ended the failed scan arrives just after
    the failure: it must not count as press 1."""
    from PyQt6.QtWidgets import QPushButton
    state = {}

    def press_now(dlg):
        tab._manager.instrument_button.emit()       # at once: inside 0.3 s
        state["open_after"] = dlg.isVisible()
        for b in dlg.findChildren(QPushButton):     # then the user clicks Skip
            if "Skip" in b.text():
                b.click()
    _open(tab, monkeypatch, "Too many patches", True, during=press_now)
    assert state["open_after"] is True
    assert tab._sent == ["skip"], tab._sent


def test_a_press_with_no_window_open_does_nothing(tab):
    tab._strip_error_window = None
    tab._manager.instrument_button.emit()
    assert tab._sent == []


def test_a_press_is_ignored_when_the_window_did_not_offer_the_button(tab, monkeypatch):
    def press(dlg):
        tab._manager.instrument_button.emit()
        from PyQt6.QtWidgets import QPushButton
        for b in dlg.findChildren(QPushButton):
            if "Skip" in b.text():
                b.click()
    _open(tab, monkeypatch, "Too many patches", False, during=press)
    assert tab._sent == ["skip"]


# ---------------------------------------------------------------------------
# the manager: the two engine events
# ---------------------------------------------------------------------------
def _feed(mgr, ev):
    mgr._engine_active = True
    mgr._handle_engine_line(json.dumps(ev), lambda _line: None)


def test_the_manager_carries_button_retry_with_the_misread(tab):
    mgr = tab._manager
    got = []
    mgr.strip_error.disconnect()
    mgr.strip_error.connect(lambda r: got.append((r, mgr.misread_button_retry)))
    _feed(mgr, {"event": "error", "kind": "misread",
                "detail": "Too many patches", "button_retry": True})
    _feed(mgr, {"event": "error", "kind": "misread", "detail": "Too many patches"})
    assert got == [("Too many patches", True), ("Too many patches", False)]
    assert mgr.misread_button_retry is False


def test_the_manager_passes_a_press_on_only_at_the_retry_prompt(tab):
    mgr = tab._manager
    presses = []
    mgr.instrument_button.disconnect()
    mgr.instrument_button.connect(lambda: presses.append(1))
    mgr._at_retry_prompt = False
    _feed(mgr, {"event": "switch"})
    assert presses == []
    mgr._at_retry_prompt = True
    _feed(mgr, {"event": "switch"})
    assert presses == [1]


# ---------------------------------------------------------------------------
# the text is never cut off (review of B1/M1, agent 6, 2026-10-21)
# ---------------------------------------------------------------------------
def test_the_longest_text_is_never_cut_off(tab, monkeypatch):
    """On screen the Inconsistent text with the button paragraph lost its last
    lines: Qt opened the window at 2/3 of the screen height and squeezed the
    label. The text now sits in a scroll area and the window is sized to it,
    up to 90 % of the screen: all of it is on screen, or it scrolls."""
    from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea
    got = {}

    def during(dlg):
        QApplication.processEvents()
        area = [a for a in dlg.findChildren(QScrollArea)
                if isinstance(a.widget(), QLabel)]
        got["area"] = bool(area)
        if area:
            a = area[0]
            need = a.widget().heightForWidth(a.viewport().width())
            got["fits"] = a.viewport().height() >= need - 2
            got["scrolls"] = a.verticalScrollBar().maximum() > 0
            cap = dlg.screen().availableGeometry().height() * 0.9
            got["sized"] = dlg.height() > dlg.screen().availableGeometry().height() * 2 / 3 \
                or got["fits"]
            got["capped"] = dlg.height() <= cap + 1
        dlg.reject()

    _open(tab, monkeypatch, "Reading is inconsistent", True, during=during)
    assert got.get("area"), "the window's text is not in a scroll area"
    assert got["fits"] or got["scrolls"], "text cut off with no way to reach it"
    assert got["sized"] and got["capped"], got
