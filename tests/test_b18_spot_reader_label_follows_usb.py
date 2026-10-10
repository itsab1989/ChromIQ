"""The "→ <reader>" label beside "Detect automatically" follows a cable.

Beta 18. `SpotReadDialog` defined `showEvent` and `hideEvent` twice (both pairs
added 2026-09-03, eae7bc5bf and f0d6d24cd). Python keeps the LAST definition
of a name in a class body, so the earlier pair, the one that started the
2-second refresh of this label, never ran: plug an instrument in or out with
the window open and the label went on naming the old reader (Start still
picked fresh). Basti approved the fix on 2026-10-10.

What a tick may cost was measured before it was switched back on: the full
question (`argyll_is_attached`) runs `/usr/sbin/ioreg`, 25 ms idle and 39 ms
with every core busy, on the GUI thread. So the tick now asks only whether the
USB list CHANGED, in process (`core.argyll_instruments.usb_fingerprint`, about
0.03 ms on macOS), and the full question follows only when it did.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings

import ui.dialogs.spot_read_dialog as mod

ROOT = Path(__file__).resolve().parent.parent


class _Usb:
    """A simulated USB bus: what is plugged in, and who asked how often."""

    def __init__(self):
        self.colormunki = False
        self.fingerprint_asks = 0
        self.full_asks = 0

    def fingerprint(self):
        self.fingerprint_asks += 1
        return ((0x0971, 0x2007, 0x01100000),) if self.colormunki else ()

    def argyll(self):
        self.full_asks += 1
        return self.colormunki


@pytest.fixture
def usb(monkeypatch):
    bus = _Usb()
    monkeypatch.setattr(mod, "usb_fingerprint_now", bus.fingerprint)
    monkeypatch.setattr(mod, "argyll_is_attached", bus.argyll)
    monkeypatch.setattr(mod, "cr30_is_probably_attached", lambda: False)
    # A CR30 this Mac reached over Bluetooth once: automatic points at it
    # until an ArgyllCMS instrument is actually plugged in.
    monkeypatch.setattr(mod, "cr30_is_remembered_over_bluetooth", lambda: True)
    return bus


@pytest.fixture
def dialog(qapp, tmp_path, usb):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = mod.SpotReadDialog(ArgyllRunner(s), s, None)
    dlg._instrument.setCurrentIndex(0)          # Detect automatically
    yield dlg
    dlg._auto_timer.stop()
    dlg.hide()
    dlg.deleteLater()


def test_the_class_defines_show_and_hide_once():
    """The fault itself: a second definition silently replaces the first."""
    tree = ast.parse((ROOT / "ui/dialogs/spot_read_dialog.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "SpotReadDialog")
    names = [n.name for n in cls.body if isinstance(n, ast.FunctionDef)]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    assert duplicated == [], f"defined twice, the first is dead: {duplicated}"


def test_the_timer_runs_while_the_window_is_shown_and_idle(dialog, qapp):
    assert not dialog._auto_timer.isActive()
    dialog.show()
    qapp.processEvents()
    assert dialog._auto_timer.isActive()
    assert dialog._auto_timer.interval() == 2000


def test_the_timer_stops_when_the_window_is_hidden(dialog, qapp):
    dialog.show()
    qapp.processEvents()
    dialog.hide()
    qapp.processEvents()
    assert not dialog._auto_timer.isActive()


def test_the_timer_stops_while_a_session_runs_and_resumes_after(dialog, qapp,
                                                                 usb):
    dialog.show()
    qapp.processEvents()
    dialog._set_session_running(True)
    assert not dialog._auto_timer.isActive()
    asked = usb.fingerprint_asks
    dialog._on_auto_tick()                      # a tick already queued
    assert usb.fingerprint_asks == asked, "USB was read under a running session"
    dialog._set_session_running(False)
    assert dialog._auto_timer.isActive()


def test_the_label_follows_a_simulated_plug_and_unplug(dialog, qapp, usb):
    dialog.show()
    qapp.processEvents()
    assert "CR30" in dialog._auto_choice.text()
    usb.colormunki = True
    dialog._on_auto_tick()
    assert "ArgyllCMS" in dialog._auto_choice.text()
    usb.colormunki = False
    dialog._on_auto_tick()
    assert "CR30" in dialog._auto_choice.text()


def test_the_timer_itself_drives_the_label(dialog, qapp, qtbot, usb):
    """End to end through the real QTimer, at a test-sized interval."""
    dialog._auto_timer.setInterval(20)
    dialog.show()
    qapp.processEvents()
    usb.colormunki = True
    qtbot.waitUntil(lambda: "ArgyllCMS" in dialog._auto_choice.text(),
                    timeout=3000)


def test_a_quiet_tick_asks_only_the_cheap_question(dialog, qapp, usb):
    """Nothing plugged or pulled: no `ioreg`, no Argyll tool, no device."""
    dialog.show()
    qapp.processEvents()
    full = usb.full_asks
    for _ in range(10):
        dialog._on_auto_tick()
    assert usb.full_asks == full
    assert usb.fingerprint_asks >= 10


def test_a_reader_chosen_by_hand_is_not_probed(dialog, qapp, usb):
    dialog.show()
    qapp.processEvents()
    dialog._instrument.setCurrentIndex(1)
    asked = usb.fingerprint_asks
    dialog._on_auto_tick()
    assert usb.fingerprint_asks == asked


def test_the_tick_is_a_bound_method_not_a_lambda():
    """CLAUDE.md, `ui/fade_scroll.py`: no self-capturing lambda as a slot."""
    src = inspect.getsource(mod.SpotReadDialog.__init__)
    assert "self._auto_timer.timeout.connect(self._on_auto_tick)" in src


def test_the_cheap_question_starts_no_program_and_opens_nothing():
    from core import argyll_instruments as ai
    src = inspect.getsource(ai._macos_usb_fingerprint) \
        + inspect.getsource(ai.usb_fingerprint) \
        + inspect.getsource(mod.usb_fingerprint_now)
    for forbidden in ("subprocess", "Popen", "ioreg\"", "serial.Serial",
                      "list_ports", "bleak", "spotread", "open("):
        assert forbidden not in src, forbidden


def test_the_real_fingerprint_answers_on_this_host():
    """Whatever is plugged in, the real call returns and is a tuple or None."""
    from core.argyll_instruments import usb_fingerprint
    fp = usb_fingerprint()
    assert fp is None or isinstance(fp, tuple)
