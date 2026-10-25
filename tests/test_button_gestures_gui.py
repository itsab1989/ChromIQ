"""Button gestures in the app (Basti, 2026-10-25; jctay, forum 149841).

The engine half is tests/test_button_gestures_engine.py. Here:

* the settings: off by default, an old file loads as off, an unknown value
  is "Nothing", the wait is clamped, and OFF starts the engine with exactly
  the command line it had (no ``--gestures``);
* the manager and the Measure tab map a recognised group to the chosen
  action through the keyboard's own commands, in strip and patch mode, at
  the Strip Read Failed window and in the holds, and the status line names
  where the reader went ("Double press: back to strip C" / "patch C5");
* nothing acts behind a window that finishes the measurement;
* Preferences ▸ Measurement: the section, greyed for a CR30, saved, and its
  "Try it" area with the replay instrument, which lets the instrument go.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.settings import DEFAULTS, AppSettings       # noqa: E402
from workflow import button_gestures as BG            # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER                       # noqa: E402

STRIPS = [{"strip": s, "sheet": 1, "read": False, "verifiable": True}
          for s in "ABCDEF"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path, **values):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in values.items():
        s.set(k, v)
    return s


def _feed(mgr, ev):
    mgr._handle_engine_line(json.dumps(ev), lambda _line: None)


def _settle(ms=60):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    s = _settings(tmp_path, button_gestures_enabled=True)
    t = TabMeasure(ArgyllRunner(s), s)
    mgr = t._manager
    written = []
    monkeypatch.setattr(mgr._runner, "write_stdin",
                        lambda text: written.append(json.loads(text)))
    mgr._engine_active = True
    mgr._spot_mode = False
    mgr._guided_state = "disabled"
    mgr._session_strips = [dict(x) for x in STRIPS]
    mgr._loc_strip = {f"{s}{i}": s for s in "ABCDEF" for i in (1, 2)}
    mgr._unread_locs = set(mgr._loc_strip)
    mgr._padding_locs = set()
    mgr._chart_was_complete = False
    mgr._is_resume = False
    t._session_live = True
    t._written = written
    yield t
    t._session_live = False


def _status(tab) -> str:
    return tab._status_bar_lbl.text()


# ---------------------------------------------------------------------------
# settings and the engine's command line
# ---------------------------------------------------------------------------
def test_off_by_default_and_an_old_file_loads_as_off(tmp_path):
    assert DEFAULTS["button_gestures_enabled"] is False
    cfg = BG.config_from(_settings(tmp_path))
    assert cfg.enabled is False and not cfg.active
    assert BG.engine_args(cfg) == []


def test_unknown_values_are_nothing_and_the_wait_is_clamped(tmp_path):
    s = _settings(tmp_path, button_gestures_enabled=True,
                  button_gesture_double="explode", button_gesture_triple="",
                  button_gesture_wait_ms=99999)
    cfg = BG.config_from(s)
    assert cfg.double == "none" and cfg.triple == "none"
    assert cfg.wait_ms == BG.WAIT_MAX_MS
    assert BG.engine_args(cfg) == []          # on, but nothing to do
    assert BG.clamp_wait("x") == BG.WAIT_DEFAULT_MS
    assert BG.clamp_wait(10) == BG.WAIT_MIN_MS


def test_on_passes_the_wait_and_the_counts_with_an_action(tmp_path):
    s = _settings(tmp_path, button_gestures_enabled=True)
    assert BG.engine_args(BG.config_from(s)) == ["--gestures", "600:23"]
    s.set("button_gesture_triple", "none")
    s.set("button_gesture_wait_ms", 850)
    assert BG.engine_args(BG.config_from(s)) == ["--gestures", "850:2"]


def test_the_tab_starts_the_engine_with_them_only_when_on(tab, tmp_path):
    from workflow.measure_manager import MeasureParams
    p = tab._apply_engine_params(MeasureParams(ti1_path=tmp_path / "c.ti1"))
    if p.engine_helper is None:
        pytest.skip("engine not available")
    assert p.gesture_args == ["--gestures", "600:23"]
    tab._settings.set("button_gestures_enabled", False)
    p = tab._apply_engine_params(MeasureParams(ti1_path=tmp_path / "c.ti1"))
    assert p.gesture_args == []


def test_the_manager_puts_them_on_the_command_line():
    import inspect
    from workflow import measure_manager
    src = inspect.getsource(measure_manager.MeasureManager)
    assert "eargs += list(params.gesture_args or [])" in src


def test_only_the_i1pro_line_and_the_colormunki_family():
    assert BG.supported(BG.family_of("X-Rite ColorMunki")) is True
    assert BG.supported(BG.family_of("GretagMacbeth i1 Pro")) is True
    assert BG.supported(BG.family_of("X-Rite i1 Pro 3")) is True
    assert BG.supported(BG.family_of("CM")) is True
    assert BG.supported(BG.family_of("i1")) is True
    assert BG.supported(BG.family_of("CR30")) is False
    assert BG.supported(BG.family_of("SS")) is False
    assert BG.supported(None) is None


# ---------------------------------------------------------------------------
# the Measure tab
# ---------------------------------------------------------------------------
def _at_strip(tab, strip="C"):
    mgr = tab._manager
    _feed(mgr, {"event": "gestures", "active": True, "unit": "strip",
                "wait_ms": 600})
    _feed(mgr, {"event": "strip_ready", "strip": strip, "read": False,
                "all_done": False})
    _feed(mgr, {"event": "scan_started"})
    tab._written.clear()


def test_a_double_press_goes_back_and_says_where(tab):
    mgr = tab._manager
    _at_strip(tab, "C")
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [310],
                "where": "strip", "strip": "C"})
    assert tab._written == [{"cmd": "back"}]
    assert mgr._scan_in_progress is False
    _feed(mgr, {"event": "strip_ready", "strip": "B", "read": True,
                "all_done": False})
    _settle()
    assert _status(tab) == "Double press: back to strip B"
    assert "Double press: back to strip B" in tab._log.toPlainText()


def test_a_triple_press_goes_to_the_next_unread(tab):
    mgr = tab._manager
    _at_strip(tab, "A")
    _feed(mgr, {"event": "gesture", "presses": 3, "gaps_ms": [300, 290],
                "where": "strip", "strip": "A"})
    assert tab._written == [{"cmd": "next_unread"}]
    _feed(mgr, {"event": "strip_ready", "strip": "D", "read": False,
                "all_done": False})
    assert _status(tab) == ("Triple press: on to strip D, the next one not "
                            "yet read")


def test_forward_and_the_chosen_actions(tab):
    mgr = tab._manager
    tab._settings.set("button_gesture_double", "forward")
    _at_strip(tab, "A")
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "strip", "strip": "A"})
    assert tab._written == [{"cmd": "forward"}]
    _feed(mgr, {"event": "strip_ready", "strip": "B", "read": False,
                "all_done": False})
    assert _status(tab) == "Double press: on to strip B"


def test_patch_by_patch_it_names_the_patch(tab):
    mgr = tab._manager
    mgr._spot_mode = True
    _feed(mgr, {"event": "gestures", "active": True, "unit": "patch",
                "wait_ms": 600})
    _feed(mgr, {"event": "spot_ready", "id": "9", "loc": "C5", "read": False,
                "all_done": False})
    tab._written.clear()
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "patch", "patch": "C5"})
    assert tab._written == [{"cmd": "back"}]
    _feed(mgr, {"event": "spot_ready", "id": "8", "loc": "C4", "read": True,
                "all_done": False})
    assert _status(tab) == "Double press: back to patch C4"


def test_pause_waits_and_one_press_goes_on(tab):
    mgr = tab._manager
    tab._settings.set("button_gesture_triple", "pause")
    _at_strip(tab, "C")
    _feed(mgr, {"event": "gesture", "presses": 3, "gaps_ms": [300, 300],
                "where": "strip", "strip": "C"})
    assert tab._written == []
    assert tab._gesture_paused == {"where": "strip", "label": "C"}
    assert _status(tab).startswith("Triple press: paused at strip C.")
    # the status line stays while paused
    tab._hide_status_flash()
    assert tab._status_bar_lbl.isVisibleTo(tab)
    _feed(mgr, {"event": "switch"})          # one press, from the hold
    assert tab._written == [{"cmd": "resume"}]
    assert tab._gesture_paused is None
    _feed(mgr, {"event": "strip_ready", "strip": "C", "read": False,
                "all_done": False})


def test_pause_then_a_second_pause_gesture_goes_on(tab):
    mgr = tab._manager
    tab._settings.set("button_gesture_double", "pause")
    _at_strip(tab, "C")
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "strip", "strip": "C"})
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "held"})
    assert tab._written == [{"cmd": "resume"}]


def test_a_click_on_the_preview_ends_the_pause(tab):
    mgr = tab._manager
    tab._settings.set("button_gesture_double", "pause")
    _at_strip(tab, "C")
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "strip", "strip": "C"})
    _feed(mgr, {"event": "strip_ready", "strip": "E", "read": False,
                "all_done": False})
    assert tab._gesture_paused is None


def test_nothing_happens_behind_a_finishing_window(tab):
    mgr = tab._manager
    got = []
    mgr.instrument_gesture.connect(got.append)
    mgr._engine_held = {"strip": "F", "button": True, "window": True}
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "held"})
    assert got == [] and tab._written == []


def test_in_the_page_pause_the_moves_act_from_the_pause(tab, monkeypatch):
    """Basti, 2026-10-25: back, forward and next unread act from the pause,
    like the arrow keys there; Pause / continue continues."""
    mgr = tab._manager
    calls = []
    monkeypatch.setattr(tab, "_page_pause_active", lambda: True)
    monkeypatch.setattr(tab, "_page_pause_continue", lambda: calls.append(1))
    mgr._engine_held = {"strip": "C", "button": True}
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "held"})                 # double = back
    assert tab._written == [{"cmd": "back"}] and calls == []
    _feed(mgr, {"event": "strip_ready", "strip": "B", "read": True,
                "all_done": False})
    assert _status(tab) == "Double press: back to strip B"
    tab._written.clear()
    mgr._engine_held = {"strip": "C", "button": True}
    _feed(mgr, {"event": "gesture", "presses": 3, "gaps_ms": [300, 300],
                "where": "held"})                 # triple = next unread
    assert tab._written == [{"cmd": "next_unread"}]
    tab._settings.set("button_gesture_double", "pause")
    tab._written.clear()
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "held"})
    assert calls == [1] and tab._written == []


def test_a_move_from_a_shortcut_pause(tab):
    mgr = tab._manager
    tab._settings.set("button_gesture_triple", "pause")
    _at_strip(tab, "C")
    _feed(mgr, {"event": "gesture", "presses": 3, "gaps_ms": [300, 300],
                "where": "strip", "strip": "C"})
    assert tab._gesture_paused
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "held"})
    assert tab._written == [{"cmd": "back"}]
    assert tab._gesture_paused is None
    _feed(mgr, {"event": "strip_ready", "strip": "B", "read": True,
                "all_done": False})
    assert _status(tab) == "Double press: back to strip B"


def test_at_the_strip_read_failed_window_a_double_press_moves(tab, monkeypatch):
    mgr = tab._manager
    _at_strip(tab, "C")

    def exec_window(dlg):
        # the window is up: the engine reports a double press at its prompt
        dlg.show()
        mgr._at_retry_prompt = True
        _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [280],
                    "where": "prompt"})
        assert not dlg.isVisible() and dlg.result() == 1

    monkeypatch.setattr(tab, "_exec_measurement_window", exec_window)
    monkeypatch.setattr(tab, "_is_last_unread_strip", lambda: False)
    tab._on_strip_error("Reading is too short", button=True)
    assert tab._written == [{"cmd": "ok"}]          # the prompt first
    _feed(mgr, {"event": "strip_ready", "strip": "C", "read": False,
                "all_done": False})
    assert tab._written[-1] == {"cmd": "back"}      # then the move
    assert "back to" not in _status(tab)            # not there yet
    _feed(mgr, {"event": "strip_ready", "strip": "B", "read": True,
                "all_done": False})
    assert _status(tab) == "Double press: back to strip B"


def test_not_in_a_session_nothing_happens(tab):
    mgr = tab._manager
    tab._session_live = False
    _feed(mgr, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                "where": "strip", "strip": "C"})
    assert tab._written == []


def test_no_sound_goes_with_a_shortcut(tab, monkeypatch):
    played = []
    snd = getattr(tab, "_sound", None)
    if snd is not None:
        monkeypatch.setattr(snd, "play", lambda *a, **k: played.append(a))
    _at_strip(tab, "C")
    _feed(tab._manager, {"event": "gesture", "presses": 2, "gaps_ms": [300],
                         "where": "strip", "strip": "C"})
    _feed(tab._manager, {"event": "strip_ready", "strip": "B", "read": True,
                         "all_done": False})
    assert played == []


# ---------------------------------------------------------------------------
# Preferences ▸ Measurement
# ---------------------------------------------------------------------------
@pytest.fixture
def section(qapp, tmp_path):
    from ui.button_shortcuts_section import ButtonShortcutsSection
    ctx = {"family": "colormunki", "name": "X-Rite ColorMunki", "port": 1,
           "busy": False}
    s = _settings(tmp_path)
    sec = ButtonShortcutsSection(s, lambda: ctx)
    sec._ctx = ctx
    yield sec
    sec.stop_try()
    sec.deleteLater()


def test_the_section_is_in_preferences_measurement(qapp, tmp_path):
    from ui.dialogs.settings_dialog import SettingsDialog
    d = SettingsDialog(_settings(tmp_path))
    try:
        sec = d._button_shortcuts
        assert sec.title() == "Instrument button shortcuts"
        assert not sec._enable_cb.isChecked()
        assert not sec._double_combo.isEnabled()
    finally:
        d.done(0)


def test_off_greys_the_options_and_on_enables_them(section):
    assert not section._double_combo.isEnabled()
    assert not section._try_btn.isEnabled() or not section._try_box.isEnabled()
    section._enable_cb.setChecked(True)
    for w in (section._double_combo, section._triple_combo,
              section._wait_spin, section._try_box):
        assert w.isEnabled()


def test_a_cr30_greys_the_whole_section_with_a_note(qapp, tmp_path):
    from ui.button_shortcuts_section import ButtonShortcutsSection
    s = _settings(tmp_path, button_gestures_enabled=True)
    sec = ButtonShortcutsSection(s, lambda: {"family": "cr30", "name": "CR30"})
    try:
        assert not sec._enable_cb.isEnabled()
        assert not sec._double_combo.isEnabled()
        assert sec._enable_cb.isChecked()           # the value is kept
        assert not sec._note.isHidden()
        assert "CR30" in sec._note.text()
    finally:
        sec.deleteLater()


def test_the_combos_offer_the_actions_in_order(section):
    items = [section._double_combo.itemData(i)
             for i in range(section._double_combo.count())]
    assert items == list(BG.ACTIONS)
    assert section._double_combo.currentData() == "back"
    assert section._triple_combo.currentData() == "next_unread"
    assert section._wait_spin.value() == pytest.approx(0.60)
    assert section._wait_spin.minimum() == pytest.approx(0.30)
    assert section._wait_spin.maximum() == pytest.approx(1.50)


def test_save_writes_the_four_keys(section, tmp_path):
    section._enable_cb.setChecked(True)
    section._triple_combo.setCurrentIndex(
        section._triple_combo.findData("pause"))
    section._wait_spin.setValue(0.85)
    s = _settings(tmp_path)
    section.save(s)
    assert s.get("button_gestures_enabled") is True
    assert s.get("button_gesture_double") == "back"
    assert s.get("button_gesture_triple") == "pause"
    assert int(s.get("button_gesture_wait_ms")) == 850


def _until(pred, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(0.01)
    return False


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
def test_try_it_with_the_replay_instrument(section, tmp_path, monkeypatch):
    from core import instrument_lease
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_REPLAY", str(replay))
    section._enable_cb.setChecked(True)
    section.start_try()
    assert section.is_trying()
    assert instrument_lease.holder() == instrument_lease.BUTTON_TRY
    assert _until(lambda: section._try_status.text().startswith("Ready."))
    for at in ("0,300", "0,250,500", "0"):
        n = section._try_list.count()
        section.send_to_try({"cmd": "presses", "at_ms": at})
        assert _until(lambda: section._try_list.count() == n + 1)
    lines = [section._try_list.item(i).text()
             for i in range(section._try_list.count())]
    assert lines[0] == "Single press: an ordinary press"
    assert lines[1].startswith("Triple press (")
    assert lines[1].endswith("apart): Next unread strip / patch")
    assert lines[2].startswith("Double press (")
    assert lines[2].endswith("apart): One strip / patch back")
    # a new wait applies at once
    section._wait_spin.setValue(0.40)
    n = section._try_list.count()
    section.send_to_try({"cmd": "presses", "at_ms": "0,550"})
    assert _until(lambda: section._try_list.count() == n + 2, timeout=6)
    section.stop_try()
    assert not section.is_trying()
    assert instrument_lease.holder() is None
    assert section._try_status.text() == "Stopped. The instrument is free again."


def test_try_it_refuses_while_a_measurement_runs(section):
    from core import instrument_lease
    section._enable_cb.setChecked(True)
    section._ctx["busy"] = True
    section.start_try()
    assert not section.is_trying()
    assert instrument_lease.holder() is None
    assert "measurement" in section._try_status.text()


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
def test_closing_preferences_lets_the_instrument_go(qapp, tmp_path,
                                                    monkeypatch):
    from core import instrument_lease
    from ui.dialogs.settings_dialog import SettingsDialog
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_REPLAY", str(replay))
    d = SettingsDialog(_settings(tmp_path, button_gestures_enabled=True))
    sec = d._button_shortcuts
    sec._context_fn = lambda: {"family": "colormunki", "name": "CM"}
    sec.refresh_instrument()
    sec.start_try()
    assert _until(lambda: sec._try_status.text().startswith("Ready."))
    proc = sec._proc
    d.reject()
    assert not sec.is_trying()
    assert proc is None or proc.state() == proc.ProcessState.NotRunning
    assert instrument_lease.holder() is None


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
@pytest.mark.parametrize("ending", ["stop", "close_preferences"])
def test_try_it_frees_a_stuck_instrument_in_two_seconds(qapp, tmp_path,
                                                        monkeypatch, ending):
    """Basti's ColorMunki (2026-10-25) stayed held after Try it ended. With
    an instrument whose close never returns (CHROMIQ_REPLAY_STUCK), Stop and
    closing Preferences still end the engine process within about two
    seconds, and the lease is free."""
    from core import instrument_lease
    from ui.dialogs.settings_dialog import SettingsDialog
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_REPLAY", str(replay))
    monkeypatch.setenv("CHROMIQ_REPLAY_STUCK", "close,signal")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    d = SettingsDialog(_settings(tmp_path, button_gestures_enabled=True))
    sec = d._button_shortcuts
    sec._context_fn = lambda: {"family": "colormunki", "name": "CM"}
    sec.refresh_instrument()
    sec.start_try()
    assert _until(lambda: sec._try_status.text().startswith("Ready."))
    proc = sec._proc
    pid = proc.processId()
    t0 = time.monotonic()
    if ending == "stop":
        sec.stop_try()
    else:
        d.reject()
    took = time.monotonic() - t0
    assert not sec.is_trying()
    assert instrument_lease.holder() is None
    assert took < 3.2, took
    import os as _os
    gone = False
    for _ in range(50):
        try:
            _os.kill(pid, 0)
        except ProcessLookupError:
            gone = True
            break
        time.sleep(0.05)
    assert gone, "the engine process is still alive"
    if ending == "stop":
        d.done(0)


# ---------------------------------------------------------------------------
# Measure my speed (Basti, 2026-10-25)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("gaps, want", [
    ([300, 130, 250], 500),     # Basti's ColorMunki: 0.30 s at most -> 0.50 s
    ([100], 300),               # quick: 1.5 x 0.10 = 0.15, +0.20 = 0.30
    ([50], 300),                # below the floor -> 0.30
    ([400], 600),               # 1.5 x 0.40 = 0.60 > 0.60? equal: 0.60
    ([410], 600),               # 0.615 -> 0.60 (nearest 0.05)
    ([417], 650),               # 0.6255 -> 0.65 (a half rounds up)
    ([1000], 1500),             # 1.5 x 1.00 = 1.50
    ([1200], 1500),             # above the ceiling -> 1.50
    ([], 600),                  # nothing measured -> the default
])
def test_the_speed_formula(gaps, want):
    assert BG.suggested_wait_ms(gaps) == want


def test_the_speed_formula_is_round_to_005_of_the_larger_rule():
    for g in range(20, 1600, 7):
        raw = max(1.5 * g, g + 200)
        expect = max(300, min(1500, int((raw + 25) // 50) * 50))
        assert BG.suggested_wait_ms([g]) == expect


def _speed_section(qapp, tmp_path, monkeypatch, stuck=""):
    from ui.button_shortcuts_section import ButtonShortcutsSection
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_REPLAY", str(replay))
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    if stuck:
        monkeypatch.setenv("CHROMIQ_REPLAY_STUCK", stuck)
    sec = ButtonShortcutsSection(
        _settings(tmp_path, button_gestures_enabled=True),
        lambda: {"family": "colormunki", "name": "CM"})
    return sec


def _press(sec, at):
    sec.send_to_try({"cmd": "presses", "at_ms": at})


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
def test_measure_my_speed_all_the_way_with_a_wrong_count(qapp, tmp_path,
                                                         monkeypatch):
    from core import instrument_lease
    sec = _speed_section(qapp, tmp_path, monkeypatch)
    try:
        sec._wait_spin.setValue(0.80)
        sec._on_speed_clicked()
        assert sec.is_measuring_speed() and sec.is_trying()
        assert instrument_lease.holder() == instrument_lease.BUTTON_TRY
        assert _until(lambda: "twice" in sec.speed_message())
        assert "(1 of 3)" in sec.speed_message()
        # a slow double press, 1.2 s apart, is still ONE group (wait 1.5 s)
        _press(sec, "0,1200")
        assert _until(lambda: "(2 of 3)" in sec.speed_message(), 8)
        assert sec.speed_progress().startswith("Double presses: ✓ ○ ○")
        # one compact area: the prompt on top, the ticks under it
        assert sec._try_list.count() == 2
        # a wrong count: a triple where a double is asked for
        _press(sec, "0,250,500")
        assert _until(lambda: "came through as 3 presses" in
                      sec.speed_message(), 8)
        assert "(2 of 3)" in sec.speed_message()
        for at in ("0,200", "0,200", "0,250,500", "0,250,500", "0,250,500"):
            n = sec.speed_progress().count("✓")
            _press(sec, at)
            assert _until(lambda: sec.speed_progress().count("✓") == n + 1,
                          8), sec.speed_message()
        text = sec.speed_message()
        assert text.startswith("Done, thank you.")
        assert "your slowest 1.20 s" in text and "1.50 s suits you" in text
        assert "on the slow side" in text            # the gentle note
        assert "Your current setting is 0.80 s." in text
        # measured: the instrument is let go before the choice
        assert not sec.is_trying()
        assert instrument_lease.holder() is None
        sec._on_speed_keep()
        assert sec._wait_spin.value() == pytest.approx(0.80)
        assert not sec.is_measuring_speed()
    finally:
        sec.cancel_speed()
        sec.stop_try()
        sec.deleteLater()


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
def test_measure_my_speed_use_takes_the_value(qapp, tmp_path, monkeypatch):
    sec = _speed_section(qapp, tmp_path, monkeypatch)
    try:
        sec._on_speed_clicked()
        assert _until(lambda: "twice" in sec.speed_message())
        for at in ("0,300", "0,200", "0,130", "0,250,500", "0,200,400",
                   "0,300,600"):
            n = sec.speed_progress().count("✓")
            _press(sec, at)
            assert _until(lambda: sec.speed_progress().count("✓") == n + 1,
                          8), sec.speed_message()
        assert "on the slow side" not in sec.speed_message()
        assert "0.50 s suits you" in sec.speed_message()
        sec._on_speed_use()
        assert sec._wait_spin.value() == pytest.approx(0.50)
        assert sec.config().wait_ms == 500
    finally:
        sec.cancel_speed()
        sec.stop_try()
        sec.deleteLater()


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
def test_measure_my_speed_gives_up_kindly_after_three_wrong_tries(
        qapp, tmp_path, monkeypatch):
    from core import instrument_lease
    sec = _speed_section(qapp, tmp_path, monkeypatch)
    try:
        sec._wait_spin.setValue(0.70)
        sec._on_speed_clicked()
        assert _until(lambda: "twice" in sec.speed_message())
        for k in range(3):
            _press(sec, "0")                        # a single, three times
            assert _until(lambda: sec._speed is None
                          or sec._speed["tries"] == k + 1, 8)
            if k < 2:
                assert ("came through as 1 press, but this step needs 2 "
                        "presses" in sec.speed_message())
        assert "did not work out after three tries" in sec.speed_message()
        assert not sec.is_measuring_speed() and not sec.is_trying()
        assert instrument_lease.holder() is None
        assert sec._wait_spin.value() == pytest.approx(0.70)
    finally:
        sec.cancel_speed()
        sec.stop_try()
        sec.deleteLater()


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
@pytest.mark.parametrize("how", ["cancel", "close_preferences"])
def test_cancelling_the_speed_changes_nothing_and_frees_it(qapp, tmp_path,
                                                           monkeypatch, how):
    """Even with an instrument whose close blocks."""
    from core import instrument_lease
    from ui.dialogs.settings_dialog import SettingsDialog
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_REPLAY", str(replay))
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    monkeypatch.setenv("CHROMIQ_REPLAY_STUCK", "close")
    d = SettingsDialog(_settings(tmp_path, button_gestures_enabled=True))
    sec = d._button_shortcuts
    sec._context_fn = lambda: {"family": "colormunki", "name": "CM"}
    sec.refresh_instrument()
    sec._wait_spin.setValue(0.65)
    sec._on_speed_clicked()
    assert _until(lambda: "twice" in sec.speed_message())
    _press(sec, "0,300")
    assert _until(lambda: "(2 of 3)" in sec.speed_message(), 8)
    t0 = time.monotonic()
    if how == "cancel":
        sec.cancel_speed()
    else:
        d.reject()
    assert time.monotonic() - t0 < 3.2
    assert not sec.is_measuring_speed() and not sec.is_trying()
    assert instrument_lease.holder() is None
    assert sec._wait_spin.value() == pytest.approx(0.65)
    if how == "cancel":
        d.done(0)


@pytest.mark.skipif(not HELPER.exists(), reason="engine not built")
def test_measuring_inside_a_running_try_it_keeps_it_running(qapp, tmp_path,
                                                            monkeypatch):
    sec = _speed_section(qapp, tmp_path, monkeypatch)
    try:
        sec.start_try()
        assert _until(lambda: sec._try_status.text().startswith("Ready."))
        sec._on_speed_clicked()
        assert "twice" in sec.speed_message()
        sec.cancel_speed()
        assert sec.is_trying()                 # Try it goes on
        n = sec._try_list.count()
        _press(sec, "0,300")                   # at its own wait again
        assert _until(lambda: sec._try_list.count() == n + 1, 8)
    finally:
        sec.stop_try()
        sec.deleteLater()


def test_the_spin_box_still_takes_a_value_by_hand(section):
    section._enable_cb.setChecked(True)
    section._wait_spin.setValue(1.10)
    assert section.config().wait_ms == 1100


# ---------------------------------------------------------------------------
# the page-pause note names the shortcuts (Basti, 2026-10-25)
# ---------------------------------------------------------------------------
_PLAN = {"kind": "page", "page": 1, "next_page": 2, "pages": 2,
         "strip": "C", "target": "D"}


def test_the_pause_note_names_the_users_shortcuts(tab):
    mgr = tab._manager
    mgr._session_strips = [dict(x, sheet=1 if x["strip"] in "ABC" else 2)
                           for x in STRIPS]
    mgr.gestures_active = True
    body = tab._page_pause_texts(_PLAN, True)["body"]
    assert ("A double press of the button goes back one strip. A triple press "
            "of the button goes to the next strip not yet read.") in body
    tab._settings.set("button_gesture_double", "pause")
    tab._settings.set("button_gesture_triple", "none")
    body = tab._page_pause_texts(_PLAN, True)["body"]
    assert "A double press of the button continues, just like one press." in body
    assert "triple press" not in body.lower()


def test_the_pause_note_is_as_before_when_the_shortcuts_are_off(tab):
    mgr = tab._manager
    mgr._session_strips = [dict(x, sheet=1 if x["strip"] in "ABC" else 2)
                           for x in STRIPS]
    mgr.gestures_active = True
    on = tab._page_pause_texts(_PLAN, True)["body"]
    tab._settings.set("button_gestures_enabled", False)
    off = tab._page_pause_texts(_PLAN, True)["body"]
    assert "double press" not in off.lower()
    assert on.startswith(off)
    # an instrument the engine did not switch them on for: as before too
    tab._settings.set("button_gestures_enabled", True)
    mgr.gestures_active = False
    assert tab._page_pause_texts(_PLAN, True)["body"] == off


def test_the_pause_note_sentences_are_in_german(tab):
    from core.i18n import set_language
    mgr = tab._manager
    mgr._session_strips = [dict(x, sheet=1 if x["strip"] in "ABC" else 2)
                           for x in STRIPS]
    mgr.gestures_active = True
    set_language("de")
    try:
        body = tab._page_pause_texts(_PLAN, True)["body"]
    finally:
        set_language("en")
    assert "Ein Doppeldruck der Taste geht einen Streifen zurück." in body


@pytest.mark.parametrize("lang, want", [("en", "0.45 s, 0.31 s"),
                                        ("de", "0,45 s, 0,31 s")])
def test_numbers_in_the_text_lines_use_the_languages_decimal_mark(lang, want):
    """Final review 4.3.14, Basti's 4.3.12 display rule: the Try it lines,
    the Measure my speed result and every message with a number in it write
    it with the LANGUAGE's decimal mark (decimal_text), not the system
    locale's. Only the spin box follows the system locale, like every spin
    box in the app."""
    from core import i18n
    from workflow import button_gestures as BG
    from ui.button_shortcuts_section import group_line
    before = i18n.current_language()
    try:
        i18n.set_language(lang)
        assert BG.gaps_text([450, 310]) == want
        line = group_line(2, [450], BG.GestureConfig(enabled=True))
        assert ("0.45 s" if lang == "en" else "0,45 s") in line, line
    finally:
        i18n.set_language(before)
