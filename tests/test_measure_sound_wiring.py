"""#131 Phase 1: the Measure tab wires the measurement-manager signals to the
right sound events, and the master checkbox persists sound_enabled."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

import core.sound as snd                   # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Emitting a manager signal also fires the tab's real UI handlers (some of
    which open modal dialogs — e.g. instrument disconnected). Make every dialog
    non-blocking so the tests exercise only the sound wiring."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    for name in ("exec", "warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, name,
                            staticmethod(lambda *a, **k: 0), raising=False)


class _Settings:
    def __init__(self, d=None):
        self._d = dict(d or {})

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _make_tab():
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings({"sound_enabled": True, "patch_read_warn_de": 10.0})
    tab = TabMeasure(ArgyllRunner(s), s)
    played: list = []
    tab._sound.play = lambda e: played.append(e)      # record intent
    tab._sound._in_measurement = True                  # pretend a read is live
    return tab, played


def test_patch_sound_routes_by_delta_e():
    tab, played = _make_tab()
    tab._on_patch_sound({"de": 2.0})                   # under warn → OK
    tab._on_patch_sound({"de": 25.0})                  # over warn → looks off
    tab._on_patch_sound({"de": None})                  # unknown → OK
    assert played == [snd.PATCH_OK, snd.PATCH_OUT_OF_TOL, snd.PATCH_OK]


def test_strip_and_error_signals_make_sound():
    tab, played = _make_tab()
    tab._manager.strip_measured.emit({"strip": "A"})
    tab._manager.strip_error.emit("read failed")
    tab._manager.instrument_disconnected.emit()
    assert played == [snd.STRIP_OK, snd.STRIP_FAIL, snd.INSTRUMENT_ERROR]


def test_slow_down_text_maps_to_slow_down_sound():
    tab, played = _make_tab()
    tab._on_strip_error_sound("Not enough samples per patch - Slow Down!")
    assert played == [snd.SLOW_DOWN]


def test_measure_finished_plays_completion(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QDialog
    # measure_finished also drives report-save / scanner-target slots that may
    # open dialogs — make any dialog non-blocking so we test only sound wiring.
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab, played = _make_tab()
    ti3 = tmp_path / "x.ti3"
    ti3.write_text("CTI3\n")
    tab.measure_finished.emit(ti3)
    assert snd.MEASUREMENT_FINISHED in played


def test_checkbox_persists_enabled():
    tab, _ = _make_tab()
    tab._sound_cb.setChecked(False)
    assert tab._settings.get("sound_enabled") is False
    tab._sound_cb.setChecked(True)
    assert tab._settings.get("sound_enabled") is True
