"""Calibrating during a measurement: the manager, the Measure tab, the cards.

Knut #182 5965478577 / 5965735823, Basti 5965500670. The helper's half is
`test_calibrate_during_measurement_helper.py`; this is everything ChromIQ does
around it, and the end of the file drives the real `MeasureManager` against
the real helper, which is where the challenge (2026-10-03, 1e) asked for
proof rather than reading: guided refinement mid-list, the unread question
already answered, and a chart that is already complete.

What is pinned, in the brief's words:
* the request goes out only on ChromIQ's engine reading strips or patches, as
  its own command; on stock chartread K is swallowed with a log line and
  NOTHING reaches the reader (asserted at the far end of a real pty);
* K pressed during a swipe or at a question is held until the next prompt;
* Cancel never marks a user quit, never sends aborted, never sets
  `_engine_fatal`, never falls back to stock;
* a failure locks reading; Try again and Save and stop work from the lock;
* K is on the help card, the printed card and every Calibration complete
  window; the Preferences switch is off by default and the button hidden.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, Qt                       # noqa: E402
from PyQt6.QtGui import QKeyEvent                         # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from workflow.measure_manager import MeasureManager       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Runner:
    is_running = True

    def __init__(self):
        self.sent: list[str] = []

    def write_stdin(self, data):
        self.sent.append(data)


def _cmds(runner) -> list:
    out = []
    for raw in runner.sent:
        try:
            out.append(json.loads(raw).get("cmd"))
        except (TypeError, ValueError, AttributeError):
            out.append(raw)
    return out


def _feed(m, *events):
    for ev in events:
        m._handle_engine_line(json.dumps(ev), lambda _s: None)


def _engine(*, spot=False):
    r = _Runner()
    m = MeasureManager(r)
    m._engine_active = True
    m._spot_mode = spot
    m._guided_state = "disabled"
    return m, r


def _ready(strip="B"):
    return {"event": "strip_ready", "strip": strip, "read": False,
            "all_done": False}


# ============================================================ the manager

def test_at_the_strip_prompt_the_request_goes_out_as_its_own_command():
    m, r = _engine()
    _feed(m, _ready())
    assert m.request_calibration() == "sent"
    assert _cmds(r) == ["calibrate"]
    assert m._user_quit is False and m._engine_fatal is None


def test_before_the_first_prompt_it_is_held_and_sent_at_it():
    m, r = _engine()
    held = []
    m.calibration_request_held.connect(lambda: held.append(1))
    assert m.request_calibration() == "held"
    assert r.sent == [] and held == [1]
    _feed(m, _ready("A"))
    assert _cmds(r) == ["calibrate"]


def test_during_a_swipe_it_is_held_until_the_next_strip_prompt():
    m, r = _engine()
    _feed(m, _ready("A"), {"event": "scan_started"})
    assert m.request_calibration() == "held"
    assert r.sent == []
    _feed(m, {"event": "strip_read", "strip": "A",
              "patches": [{"loc": "A1"}]})
    assert r.sent == [], "still nothing: the menu is not up yet"
    _feed(m, _ready("B"))
    assert _cmds(r) == ["calibrate"]


@pytest.mark.parametrize("question", [
    {"event": "error", "kind": "misread", "detail": "x"},
    {"event": "strip_warning", "kind": "wrong_strip", "read": "b",
     "expected": "a"},
    {"event": "unread_confirm", "id": "1", "loc": "A1"},
])
def test_at_a_question_it_is_held(question):
    m, r = _engine()
    _feed(m, _ready("A"), question)
    assert m.request_calibration() == "held"
    assert "calibrate" not in _cmds(r)
    _feed(m, _ready("A"))
    assert _cmds(r)[-1] == "calibrate"


def test_patch_by_patch_flushes_on_spot_ready():
    m, r = _engine(spot=True)
    assert m.request_calibration() == "held"
    _feed(m, {"event": "spot_ready", "id": "1", "loc": "A1", "read": False,
              "all_done": False, "exyz": [1, 1, 1]})
    assert _cmds(r) == ["calibrate"]


def test_an_ending_drops_the_request():
    m, r = _engine()
    _feed(m, _ready("A"))
    m.mark_stop_requested()
    assert m.request_calibration() == "ending"
    assert r.sent == []
    m2, r2 = _engine()
    _feed(m2, _ready("A"), {"event": "scan_started"})
    assert m2.request_calibration() == "held"
    m2.mark_ending_answered()
    _feed(m2, _ready("B"))
    assert "calibrate" not in _cmds(r2), "a held request outlived the ending"


@pytest.mark.parametrize("how", ["stock", "cr30", "whole_sheet", "fallback"])
def test_never_where_the_reader_cannot(how):
    m, r = _engine()
    if how == "stock":
        m._engine_active = False
    elif how == "cr30":
        m._external_values = True
    elif how == "whole_sheet":
        _feed(m, {"event": "chart_reading"})
    else:
        _feed(m, {"event": "mode_fallback"})
    _feed(m, _ready("A"))
    assert m.can_calibrate_on_request() is False
    assert m.request_calibration() == "unsupported"
    assert "calibrate" not in _cmds(r)


def test_a_second_press_while_one_is_out_is_busy():
    m, r = _engine()
    _feed(m, _ready())
    assert m.request_calibration() == "sent"
    assert m.request_calibration() == "busy"
    assert _cmds(r) == ["calibrate"]


def test_the_placement_prompt_goes_to_its_own_window():
    m, _r = _engine()
    own, needs = [], []
    m.calibration_requested_prompt.connect(lambda *a: own.append(a))
    m.calibration_prompt.connect(lambda *a: needs.append(a))
    _feed(m, {"event": "cal_required", "cond": "man_ref_white", "id": "",
              "optional": False, "requested": True})
    assert own == [("man_ref_white", "", False)] and needs == []
    _feed(m, {"event": "cal_required", "cond": "man_ref_white", "id": "",
              "optional": False})
    assert len(needs) == 1, "the needs-calibration path is unchanged"


def test_cancel_is_its_own_command_and_never_a_quit():
    m, r = _engine()
    _feed(m, _ready())
    m.request_calibration()
    m.cancel_requested_calibration()
    _feed(m, {"event": "cal_result", "result": "cancelled", "damaged": False})
    assert _cmds(r) == ["calibrate", "cal_cancel"]
    assert m._user_quit is False and m.ended_by_the_user is False
    assert m._engine_fatal is None
    assert m.calibration_locked is False


def test_a_failure_locks_and_a_success_unlocks_without_touching_the_flags():
    m, r = _engine()
    results = []
    m.calibration_request_result.connect(lambda *a: results.append(a))
    _feed(m, _ready())
    m.request_calibration()
    _feed(m, {"event": "cal_result", "result": "failed", "damaged": True,
              "detail": "White calibration failed (replay)"})
    assert m.calibration_locked is True
    assert m._engine_fatal is None and m._user_quit is False
    assert results[-1] == ("failed", True,
                           "White calibration failed (replay)", False)
    # Try again goes out at once: the lock IS the prompt.
    assert m.request_calibration() == "sent"
    _feed(m, {"event": "cal_result", "result": "done", "prompted": True})
    assert m.calibration_locked is False
    assert results[-1] == ("done", False, "", True)
    assert _cmds(r) == ["calibrate", "calibrate"]


def test_no_stock_fallback_after_a_requested_calibration():
    """Neither fallback may hand such a session to stock chartread."""
    m, _r = _engine()
    _feed(m, _ready())
    m.request_calibration()
    m._engine_fatal = "communication problem"      # a later, real failure
    m._engine_progress = True
    assert m._engine_should_resume_fallback(1) is False
    m._engine_progress = False
    assert m._engine_should_fall_back(1) is False


def test_the_same_strip_re_offered_after_a_calibration_is_not_a_guided_step():
    m, r = _engine()
    m._guided_strips = ["B", "C"]
    m._guided_state = "waiting"
    m._guided_idx = 0
    _feed(m, _ready("B"))
    m._guided_menu_pending = False
    m.request_calibration()
    _feed(m, {"event": "cal_result", "result": "done", "prompted": True},
          _ready("B"))
    assert m._guided_menu_pending is False
    assert m._guided_state == "waiting" and m._guided_idx == 0
    assert "goto" not in _cmds(r)


# ============================================================ the tab

class _Settings:
    def __init__(self, **kw):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq"}
        self._d.update(kw)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    sent: list[str] = []
    mgr = t._manager
    mgr._runner.write_stdin = sent.append
    mgr._engine_active = True
    mgr._guided_state = "disabled"
    t._sent = sent
    t._arm_key_watchdog = lambda: None
    t._session_live = True
    _feed(mgr, _ready("A"))
    yield t
    t._session_live = False
    t.deleteLater()


def _key(k, text="", *, nvk=0, scan=0):
    return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier,
                     scan, nvk, 0, text)


def _sent_cmds(tab):
    out = []
    for raw in tab._sent:
        try:
            out.append(json.loads(raw).get("cmd"))
        except (TypeError, ValueError, AttributeError):
            out.append(raw)
    return out


@pytest.mark.parametrize("text", ["k", "K"])
def test_k_and_shift_k_ask_for_a_calibration(tab, text):
    assert tab.eventFilter(tab, _key(Qt.Key.Key_K, text)) is True
    assert _sent_cmds(tab) == ["calibrate"]


def test_the_physical_k_key_under_a_cyrillic_layout(tab, monkeypatch):
    import ui.tabs.tab_measure as tm
    if sys.platform == "darwin":
        ev = _key(0, "л", nvk=tm.TabMeasure._MAC_KEYCODE_K)
    elif sys.platform.startswith("win"):
        ev = _key(0, "л", nvk=tm.TabMeasure._WIN_VK_K)
    else:
        ev = _key(0, "л", scan=tm.TabMeasure._LINUX_SCANCODE_K)
    assert tab.eventFilter(tab, ev) is True
    assert _sent_cmds(tab) == ["calibrate"]


def test_the_key_position_alone_never_calibrates_on_a_latin_layout(tab):
    """Dvorak types "t" on the K position: that is a "t", not a calibrate."""
    import ui.tabs.tab_measure as tm
    nvk = (tm.TabMeasure._MAC_KEYCODE_K if sys.platform == "darwin"
           else tm.TabMeasure._WIN_VK_K)
    tab.eventFilter(tab, _key(Qt.Key.Key_T, "t", nvk=nvk,
                              scan=tm.TabMeasure._LINUX_SCANCODE_K))
    assert "calibrate" not in _sent_cmds(tab)


def test_on_stock_k_is_swallowed_with_a_log_line(tab):
    tab._manager._engine_active = False
    tab._sent.clear()
    tab._manager._runner.write_stdin = tab._sent.append
    assert tab.eventFilter(tab, _key(Qt.Key.Key_K, "k")) is True
    assert tab._sent == [], "K reached stock chartread"
    assert "needs ChromIQ's chart-reading engine" in tab._log.toPlainText()


def test_a_modal_window_keeps_k(tab, qapp):
    from PyQt6.QtWidgets import QDialog
    dlg = QDialog(tab)
    dlg.setModal(True)
    dlg.show()
    try:
        if qapp.activeModalWidget() is None:
            pytest.skip("this platform plugin reports no active modal")
        assert tab.eventFilter(tab, _key(Qt.Key.Key_K, "k")) is False
        assert tab._sent == []
    finally:
        dlg.close()


def test_while_locked_esc_ends_through_the_one_window_and_keys_wait(
        tab, monkeypatch):
    stops = []
    monkeypatch.setattr(tab, "_on_stop", lambda: stops.append(1))
    tab._manager._cal_locked = True
    assert tab.eventFilter(tab, _key(Qt.Key.Key_F, "f")) is True
    assert tab._sent == [], "a key went to a reader that reads nothing"
    tab.eventFilter(tab, _key(Qt.Key.Key_Escape, "\x1b"))
    assert stops == [1]
    # …and K still asks for the next attempt.
    tab.eventFilter(tab, _key(Qt.Key.Key_K, "k"))
    assert _sent_cmds(tab) == ["calibrate"]


def test_the_button_is_hidden_by_default_and_follows_the_live_reader(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import DEFAULTS
    from ui.tabs.tab_measure import TabMeasure
    assert DEFAULTS["measure_calibrate_button"] is False
    off = TabMeasure(ArgyllRunner(_Settings()), _Settings())
    assert off._calibrate_btn.isHidden()
    off.deleteLater()

    s = _Settings(measure_calibrate_button=True)
    t = TabMeasure(ArgyllRunner(s), s)
    try:
        # Outside a session the row is exactly what it was: four buttons do
        # not fit the 580 px panel (measured on screen, "START MEASUREMEN").
        assert t._calibrate_btn.isHidden()
        assert not t._save_defaults_btn.isHidden()
        t._session_live = True
        t._sync_calibrate_btn_visible()
        assert not t._calibrate_btn.isHidden()
        assert t._save_defaults_btn.isHidden(), (
            "while measuring, Calibrate stands where the disabled Save as "
            "Defaults stands")
        assert not t._calibrate_btn.isEnabled(), "no strip offered yet"
        t._manager._engine_active = True
        t._manager._runner.write_stdin = lambda _d: None
        _feed(t._manager, _ready("A"))      # stripe_changed refreshes it
        assert t._calibrate_btn.isEnabled()
        t._manager._engine_active = False   # stock, or after a fallback
        t._refresh_calibrate_btn_state()
        assert not t._calibrate_btn.isEnabled()
        t._session_live = False
        t._sync_calibrate_btn_visible()
        assert t._calibrate_btn.isHidden()
        assert not t._save_defaults_btn.isHidden()
    finally:
        t._session_live = False
        t.deleteLater()


def test_the_placement_window_cancel_sends_cal_cancel(tab, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda self: True))
    seen = {}

    def _exec(dlg):
        seen["title"] = dlg.windowTitle()
        from PyQt6.QtWidgets import QPushButton
        seen["buttons"] = [b.text() for b in dlg.findChildren(QPushButton)]
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(tab, "_exec_measurement_window", _exec)
    tab._on_requested_calibration_prompt("man_ref_white", "", False)
    assert seen["title"] == "Calibrate the Instrument"
    assert "Cancel calibration" in seen["buttons"]
    assert "Cancel Measurement" not in seen["buttons"]
    assert _sent_cmds(tab) == ["cal_cancel"]
    assert tab._manager._user_quit is False


def test_the_placement_window_start_sends_ok(tab, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda self: True))
    monkeypatch.setattr(tab, "_exec_measurement_window",
                        lambda dlg: QDialog.DialogCode.Accepted)
    tab._on_requested_calibration_prompt("man_ref_white", "", False)
    assert _sent_cmds(tab) == ["ok"]


def test_the_failure_window_try_again_and_save_and_stop(tab, monkeypatch):
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda self: True))
    tab._manager._cal_locked = True

    def _press(label):
        def _exec(box):
            for b in box.buttons():
                if b.text() == label:
                    b.click()
                    return 0
            raise AssertionError(f"no {label!r} button")
        return _exec

    monkeypatch.setattr(tab, "_exec_measurement_window", _press("Try again"))
    tab._show_requested_calibration_failed("White calibration failed")
    assert _sent_cmds(tab) == ["calibrate"]
    tab._manager._cal_request_pending = False

    monkeypatch.setattr(tab, "_exec_measurement_window",
                        _press("Save and stop"))
    tab._show_requested_calibration_failed("White calibration failed")
    assert _sent_cmds(tab)[-1] == "quit", "the save chain's first quit"
    assert tab._manager._save_partial_state == "wait_give_up_prompt"
    # The locked helper answers with the give-up prompt; the chain finishes.
    _feed(tab._manager, {"event": "strip_interrupted"})
    assert _sent_cmds(tab)[-2:] == ["quit", "quit"]


def _labels_of(dlg) -> list:
    from PyQt6.QtWidgets import QLabel
    return [lb.text() for lb in dlg.findChildren(QLabel)]


@pytest.mark.parametrize("spot", [False, True])
def test_the_short_calibration_complete_lists_k(tab, monkeypatch, spot):
    got = {}
    monkeypatch.setattr(tab, "_exec_measurement_window",
                        lambda dlg: got.setdefault("labels", _labels_of(dlg)))
    tab._spot_session = spot
    tab._show_requested_calibration_done()
    assert "K" in got["labels"]
    assert any("same strip or patch" in t for t in got["labels"])


@pytest.mark.parametrize("variant", ["spot", "strip", "guided", "resume"])
def test_every_calibration_complete_window_lists_k(tab, monkeypatch, variant):
    got = {}
    monkeypatch.setattr(tab, "_exec_measurement_window",
                        lambda dlg: got.setdefault("labels", _labels_of(dlg)))
    tab._spot_session = variant == "spot"
    tab._guided_refinement_active = variant == "guided"
    tab._strip_list = ["B"] if variant == "guided" else []
    tab._resume_active = variant == "resume"
    tab._on_calibration_done()
    labels = got["labels"]
    assert "K" in labels or any(t.startswith("K: calibrate") for t in labels)


def test_the_calibration_complete_window_has_no_k_on_stock(tab, monkeypatch):
    got = {}
    monkeypatch.setattr(tab, "_exec_measurement_window",
                        lambda dlg: got.setdefault("labels", _labels_of(dlg)))
    tab._manager._engine_active = False
    tab._spot_session = False
    tab._guided_refinement_active = False
    tab._resume_active = False
    tab._on_calibration_done()
    assert "K" not in got["labels"]


def test_the_help_card_and_the_printed_card_list_k():
    from ui.keyboard_help import CHROMIQ, _measurement_keys, \
        keyboard_shortcuts_html
    rows = [r for r in _measurement_keys() if r[0] == "K"]
    assert rows and rows[0][2] == CHROMIQ
    assert "does nothing" in rows[0][1]
    html_ = keyboard_shortcuts_html()
    assert "<code>K</code>" in html_
    # The printed card renders the same HTML (help_card_print, "shortcuts").
    import inspect
    import ui.help_card_print as hp
    assert "keyboard_shortcuts_html()" in inspect.getsource(hp)


def test_the_preference_is_off_and_needs_the_engine(qapp):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s.set("chartread_engine", "argyll")
    dlg = SettingsDialog(s)
    try:
        assert dlg._calibrate_button_check.isChecked() is False
        assert dlg._calibrate_button_check.isEnabled() is False
        dlg._chartread_engine_check.setChecked(True)
        assert dlg._calibrate_button_check.isEnabled() is True
    finally:
        dlg.deleteLater()


# ============================================== stock, at the far end of a pty

@pytest.mark.parametrize("text,key", [("k", Qt.Key.Key_K),
                                      ("K", Qt.Key.Key_K)])
def test_on_stock_nothing_reaches_the_reader(qapp, tmp_path, text, key):
    from tests.helpers.live_reader import measuring
    with measuring(tmp_path) as (tab, reader):
        reader.forget()
        QApplication.sendEvent(tab, _key(key, text))
        assert reader.wait_for_a_byte() == b"", (
            "K reached stock chartread: in strip mode that starts a read, in "
            "patch mode a Cancel then ends the program without its .ti3")
        assert "needs ChromIQ's chart-reading engine" in tab._log.toPlainText()


# ======================================== the real manager on the real helper

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")


class _Bridge:
    """A runner whose stdin is the real helper's, and a pump that hands the
    helper's events to the real manager in order."""

    is_running = True

    def __init__(self, session: ReplaySession) -> None:
        self.s = session
        self.fed = 0
        self.sent: list[str] = []

    def write_stdin(self, data: str) -> None:
        self.sent.append(data)
        self.s.proc.stdin.write(data)
        self.s.proc.stdin.flush()

    def pump(self, m, until, timeout: float = 10.0, **fields) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.s._lock:
                pending = self.s.events[self.fed:]
            for ev in pending:
                self.fed += 1
                m._handle_engine_line(json.dumps(ev), lambda _s: None)
                if ev.get("event") == until and all(
                        ev.get(k) == v for k, v in fields.items()):
                    return ev
            time.sleep(0.02)
        raise TimeoutError(f"no {until} {fields}; tail: {self.s.raw_lines[-8:]}")


def _chart(tmp: Path, patches: int = 63) -> "tuple[Path, Path]":
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", f"-f{patches}",
                    str(base)], check=True, capture_output=True, cwd=tmp,
                   timeout=120)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.3)
    return base, replay


def _calibrate_through(m, b: _Bridge, strip: str) -> None:
    assert m.request_calibration() == "sent"
    b.pump(m, "cal_required")
    m.send_key("\r")
    b.pump(m, "cal_result", result="done")
    b.pump(m, "strip_ready", strip=strip)


real = pytest.mark.skipif(not HELPER.exists(),
                          reason="chromiq-chartread helper not built")


@real
def test_real_helper_guided_refinement_mid_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        b = _Bridge(s)
        m = MeasureManager(b)
        m._engine_active = True
        m._spot_mode = False
        m._guided_strips = ["B", "C"]
        m._guided_state = "idle"
        m._guided_idx = 0
        b.pump(m, "strip_ready", strip="B")          # guided moved A -> B
        assert m._guided_state == "waiting"
        before = list(b.sent)
        _calibrate_through(m, b, "B")
        moves = [json.loads(x)["cmd"] for x in b.sent[len(before):]]
        assert "goto" not in moves and "forward" not in moves, moves
        assert m._guided_state == "waiting" and m._guided_idx == 0
        s.send(cmd="swipe")
        b.pump(m, "strip_read", strip="B")
        b.pump(m, "strip_ready", strip="C")
        assert m._guided_idx == 1, "guided refinement moved on to C"
        m.send_key("q")
        b.pump(m, "strip_interrupted")
        s.send(cmd="quit")
        s.finish(timeout=15)


@real
def test_real_helper_unread_policy_already_answered(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        b = _Bridge(s)
        m = MeasureManager(b)
        m._engine_active = True
        m._spot_mode = False
        m._guided_state = "disabled"
        m._unread_policy = "unread"
        b.pump(m, "strip_ready", strip="A")
        s.send(cmd="swipe")
        b.pump(m, "strip_read", strip="A")
        b.pump(m, "strip_ready", strip="B")
        before = len(b.sent)
        _calibrate_through(m, b, "B")
        cmds = [json.loads(x)["cmd"] for x in b.sent[before:]]
        assert cmds == ["calibrate", "ok"], cmds
        assert m._unread_policy == "unread"
        assert m._held_after_read is None
        m.send_key("q")
        b.pump(m, "strip_interrupted")
        s.send(cmd="quit")
        s.finish(timeout=15)


@real
def test_real_helper_complete_chart_re_arm(tmp_path, monkeypatch):
    """Every strip read; the reader re-arms the last; a calibration there must
    neither move it nor announce the completion again."""
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = _chart(tmp_path, patches=42)
    with ReplaySession(base, replay) as s:
        b = _Bridge(s)
        m = MeasureManager(b)
        m._engine_active = True
        m._spot_mode = False
        m._guided_state = "disabled"
        m._is_resume = False
        done = []
        m.all_stripes_done.connect(lambda: done.append(1))
        b.pump(m, "strip_ready", strip="A")
        s.send(cmd="swipe")
        b.pump(m, "strip_read", strip="A")
        b.pump(m, "strip_ready", strip="B")
        s.send(cmd="swipe")
        b.pump(m, "strip_read", strip="B")
        ev = b.pump(m, "strip_ready", all_done=True)
        at = ev["strip"]
        time.sleep(0.3)
        before = len(b.sent)
        n_done = len(done)
        assert m.request_calibration() == "sent"
        b.pump(m, "cal_required")
        m.send_key("\r")
        b.pump(m, "cal_result", result="done")
        again = b.pump(m, "strip_ready")
        cmds = [json.loads(x)["cmd"] for x in b.sent[before:]]
        assert "goto" not in cmds, cmds
        assert again["all_done"] is True
        assert again["strip"] == at, "the reader moved"
        assert len(done) == n_done, "the completion was announced again"
        m.send_key("q")
        b.pump(m, "strip_interrupted")
        s.send(cmd="quit")
        s.finish(timeout=15)
