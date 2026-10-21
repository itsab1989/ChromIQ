"""N2 review (agent 12, 4.3.9): a Start that is called off must not leave the
audio keep-alive running.

``TabMeasure._on_start`` arms the sound (which, with "Wake the audio device"
on, starts core.audio_keepalive's stream) BEFORE four questions the user can
answer "no" to: the verification guard, replacing the stored chart, the
non-random bidirectional question and M-REPLACE. Each of them returned without
disarming, so the stream kept the sound hardware running, and coreaudiod
busy, until the NEXT measurement ended or the app quit. These tests fail on
the code before the fix.
"""
from __future__ import annotations

import pytest


class _Sound:
    def __init__(self):
        self.armed = False

    def arm(self, reading_engine=True):
        self.armed = True

    def disarm(self):
        self.armed = False

    def stop_keep_awake(self):
        self.armed = False


@pytest.fixture
def tab(tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    (tmp_path / "chart.ti1").write_text("CTI1\n", encoding="utf-8")
    t._ti1_path = tmp_path / "chart.ti1"
    for name in ("_blocked_by_new_run", "_blocked_by_missing_chart_file",
                 "_blocked_by_unreadable_locations",
                 "_blocked_by_stock_chartread_for_cr30",
                 "_blocked_by_the_instrument_being_in_use",
                 "_blocked_by_unusable_target_instrument",
                 "_blocked_by_a_misfitting_measurement"):
        monkeypatch.setattr(t, name, lambda *_a: False)
    monkeypatch.setattr(t, "_recover_engine_autosave", lambda: False)
    monkeypatch.setattr(t, "_verification_guard", lambda: None)
    monkeypatch.setattr(t, "_snapshot_verification_chart", lambda: True)
    monkeypatch.setattr(t, "_confirm_nonrandom_bidir", lambda _p: True)
    monkeypatch.setattr(t, "_starts_a_refinement", lambda _p: False)
    t._sound = _Sound()
    yield t
    t.deleteLater()


def _refuse(tab, monkeypatch, name, value):
    monkeypatch.setattr(tab, name, lambda *_a: value)


@pytest.mark.parametrize("name,value", [
    ("_snapshot_verification_chart", False),
    ("_confirm_nonrandom_bidir", False),
    ("_confirm_replacing_measurement", False),
])
def test_a_refused_start_leaves_nothing_armed(tab, monkeypatch, name, value):
    if name != "_confirm_replacing_measurement":
        monkeypatch.setattr(tab, "_confirm_replacing_measurement",
                            lambda: True)
    _refuse(tab, monkeypatch, name, value)
    tab._on_start()
    assert not getattr(tab, "_session_live", False)
    assert tab._sound.armed is False, (
        f"{name} said no and the keep-alive stream was left running")


def test_the_verification_guard_leaves_nothing_armed(tab, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    class _Block:
        def render(self):
            return ("t", "b")
    monkeypatch.setattr(tab, "_verification_guard", lambda: _Block())
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    tab._on_start()
    assert tab._sound.armed is False


def test_a_live_session_keeps_its_sound(tab):
    # The guard only disarms a start that did NOT start: a running session
    # (Continue, or a second press) keeps its sounds and its stream.
    tab._session_live = True
    tab._sound.armed = True
    from ui.tabs import tab_measure as TM
    TM._disarms_a_start_that_did_not_start(lambda self: None)(tab)
    assert tab._sound.armed is True
    tab._session_live = False


# ---- the option switched in Preferences during a measurement ---------------

class _FakeKeepAlive:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def _manager(monkeypatch, warm=True, sounds=True):
    import core.audio_keepalive as K
    import core.sound as S
    from core.settings import AppSettings
    monkeypatch.setattr(K, "AudioKeepAlive", _FakeKeepAlive)
    monkeypatch.setattr(S, "warm_up_audio", lambda *_a: None)
    monkeypatch.setattr(S, "preload_warm_up", lambda *_a: None)
    st = AppSettings()
    st.set("sound_warm_up_device", warm)
    st.set("sound_enabled", sounds)
    m = S.SoundManager(st)
    monkeypatch.setattr(m, "_preload", lambda *_a: None)
    return m


def test_switching_the_option_off_mid_measurement_stops_the_stream(monkeypatch):
    m = _manager(monkeypatch)
    m.arm()
    assert m.keeping_awake
    m._settings.set("sound_warm_up_device", False)
    m.refresh_keep_awake()
    assert not m.keeping_awake
    m._settings.set("sound_warm_up_device", True)
    m.refresh_keep_awake()
    assert m.keeping_awake, "switched back on during the measurement"
    m._settings.set("sound_enabled", False)
    m.refresh_keep_awake()
    assert not m.keeping_awake
    m.disarm()


def test_outside_a_measurement_the_refresh_starts_nothing(monkeypatch):
    m = _manager(monkeypatch)
    m.refresh_keep_awake()
    assert not m.keeping_awake


def test_preferences_ok_reaches_the_measure_tab():
    import inspect
    from ui import main_window
    src = inspect.getsource(main_window)
    assert "self._tab_measure.refresh_sound_keep_awake()" in src
