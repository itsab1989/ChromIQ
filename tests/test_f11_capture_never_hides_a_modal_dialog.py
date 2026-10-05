"""F-11: ``capture_window``'s rectangle fallback hides the window to prove the
picture. Hiding a QDialog that is inside ``exec()`` ends its modal loop as
Rejected and leaves a stray window on screen (agent 18's driver, 2026-10-05,
the "New patch set" window). The fallback must refuse a modal window, and any
window while a modal loop runs, whatever the caller passed."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QWidget        # noqa: E402

import scripts.onscreen_capture as oc                            # noqa: E402


@pytest.fixture
def no_screen(monkeypatch):
    """No real capture: the window id is unknown, the rectangle grab 'works',
    and hide() is recorded."""
    monkeypatch.setattr(oc, "session_is_locked", lambda: False)
    monkeypatch.setattr(oc, "keep_display_awake", lambda: None)
    monkeypatch.setattr(oc, "display_is_asleep", lambda: False)
    monkeypatch.setattr(oc, "window_id_for", lambda w: None)
    monkeypatch.setattr(oc, "_grab_region", lambda rect, path: True)
    monkeypatch.setattr(oc, "_difference", lambda a, b: 1.0)


def test_a_modal_dialog_in_exec_is_never_hidden(no_screen, tmp_path):
    app = QApplication.instance() or QApplication([])
    dlg = QDialog()
    seen = {}

    def inside():
        hidden = []
        dlg.hideEvent = lambda ev: hidden.append(True)
        ok, why = oc.capture_window(dlg, tmp_path / "x.png", settle=0.0)
        seen.update(ok=ok, why=why, hidden=bool(hidden), visible=dlg.isVisible())
        dlg.accept()

    QTimer.singleShot(50, inside)
    result = dlg.exec()
    assert seen["ok"] is False and "hide" in seen["why"]
    assert not seen["hidden"] and seen["visible"]
    # the dialog ended the way the DRIVER ended it, not as a side effect
    assert result == QDialog.DialogCode.Accepted


def test_a_plain_window_outside_any_modal_loop_may_still_use_the_fallback(no_screen, tmp_path):
    app = QApplication.instance() or QApplication([])
    w = QWidget()
    w.resize(300, 300)
    w.show()
    app.processEvents()
    ok, _why = oc.capture_window(w, tmp_path / "y.png", settle=0.0)
    assert ok
    w.close()
