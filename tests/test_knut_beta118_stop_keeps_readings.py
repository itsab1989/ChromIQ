"""#130 (Knut, 2026-08-01): pressing Stop threw away everything read so far.

Twice in one session, on both reading modes:

    "the measurement session is ended without any measurement and the ti3 file
     is gone"
    "no ti3 file is saved, even though I did read one patch"

and the question that names it exactly:

    "Why do I not get this warning message when pressing Stop button or exiting
     during measurement failure?"

chartread keeps its readings in memory and writes the `.ti3` only when it exits
cleanly. Stop killed the process, so they went with it — silently. Pressing 'd'
has always asked "are you sure" and saved; Stop simply discarded.

Stop now offers to keep them, using the same two-'q' protocol as Save Partial,
and only asks when there is something to lose.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QMessageBox     # noqa: E402

from workflow.measure_manager import MeasureManager       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Runner:
    def __init__(self):
        self.out: list[str] = []
        self.aborted = False

    def write_stdin(self, data):
        self.out.append(data)

    def abort(self):
        self.aborted = True

    def __getattr__(self, _n):
        return lambda *a, **k: None


# ---- the manager knows whether anything is at stake ----------------------
def test_nothing_read_means_nothing_to_lose():
    m = MeasureManager(_Runner())
    assert m.has_unsaved_readings is False


def test_a_read_strip_counts():
    m = MeasureManager(_Runner())
    m._read_something = True
    assert m.has_unsaved_readings is True


# ---- Stop asks, and only when it should ---------------------------------
def _tab_with(manager, clicked_role, tmp_path):
    """A REAL TabMeasure with its manager swapped out.

    Not TabMeasure.__new__: the window needs a live QWidget parent, and a
    half-built one raises "super-class __init__() was never called" the moment
    QMessageBox(self) is constructed.
    """
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._manager = manager

    chosen = {}

    def fake_exec(self):
        for b in self.buttons():
            if self.buttonRole(b) == clicked_role:
                chosen["btn"] = b
                return 0
        return 0

    return tab, fake_exec, chosen


def test_stop_with_nothing_read_just_stops(qapp, monkeypatch, tmp_path):
    """No window when there is nothing to save — it would be pure noise."""
    m = MeasureManager(_Runner())
    tab, fake_exec, _ = _tab_with(m, QMessageBox.ButtonRole.AcceptRole, tmp_path)
    shown = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: shown.append(1) or 0)
    tab._on_stop()
    assert shown == []
    assert m._runner.aborted is True


def test_stop_after_reading_offers_to_save(qapp, monkeypatch, tmp_path):
    m = MeasureManager(_Runner())
    m._read_something = True
    tab, fake_exec, chosen = _tab_with(m, QMessageBox.ButtonRole.AcceptRole, tmp_path)
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: chosen.get("btn"))
    tab._on_stop()
    # Whatever the reader is, Save goes through the Save-Partial chain rather
    # than killing the process. This manager is stock chartread (no engine), so
    # the chain starts with 'd' at the strip menu — see
    # tests/test_knut_beta118_save_partial_stock.py for both readers.
    assert m._runner.out == ["d"]
    assert m.save_partial_in_progress is True
    assert m._runner.aborted is False, "saving must not kill the process"


def test_discard_still_stops_immediately(qapp, monkeypatch, tmp_path):
    m = MeasureManager(_Runner())
    m._read_something = True
    tab, fake_exec, chosen = _tab_with(m, QMessageBox.ButtonRole.DestructiveRole, tmp_path)
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: chosen.get("btn"))
    tab._on_stop()
    assert m._runner.aborted is True
    assert m._runner.out == []


def test_keep_measuring_changes_nothing(qapp, monkeypatch, tmp_path):
    """The session must survive an accidental Stop untouched."""
    m = MeasureManager(_Runner())
    m._read_something = True
    tab, fake_exec, chosen = _tab_with(m, QMessageBox.ButtonRole.RejectRole, tmp_path)
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: chosen.get("btn"))
    tab._on_stop()
    assert m._runner.aborted is False
    assert m._runner.out == []
    assert m.save_partial_in_progress is False


# ---- the words --------------------------------------------------------
def test_the_window_says_what_each_button_does():
    src = inspect.getsource(
        __import__("ui.tabs.tab_measure", fromlist=["x"]).TabMeasure._on_stop)
    assert "Save and stop" in src
    assert "Discard and stop" in src
    assert "Keep measuring" in src
    assert "What each button does" in src, \
        "Knut's standing rule for every window in the app"
    assert "Refine / resume" in src, \
        "the user needs to know how to carry on from a partial save"


def test_saving_is_the_default_button():
    """The safe choice is the one that keeps the work."""
    src = inspect.getsource(
        __import__("ui.tabs.tab_measure", fromlist=["x"]).TabMeasure._on_stop)
    assert "setDefaultButton(save)" in src
