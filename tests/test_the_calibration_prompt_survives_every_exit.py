"""Every way out of the "Calibration Required" window, with the optional
button present — the case no test ever reached.

`optional=True` arrives only from a SwatchMate Cube, and the `and` in the old
`skip_btn is not None and btn_box.clickedButton() is skip_btn` short-circuits
for everything else, so the line was never executed by the suite. It called
`QMessageBox`'s API on a `QDialogButtonBox`: `AttributeError`, in a Qt slot,
where PyQt6 calls `qFatal()` — the process ended mid-measurement with
chartread's `.ti3` unwritten. On the same two lines, "Skip this step" was added
with `DestructiveRole`, which emits neither `accepted` nor `rejected`, so it
was wired to nothing and the window would not close at all.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from ui.tabs.tab_measure import TabMeasure


@pytest.fixture
def tab(qapp):
    s = AppSettings()
    t = TabMeasure(ArgyllRunner(s), s)
    t._detected_instrument = "SwatchMate Cube"
    return t


def _answer(qapp, label: str | None):
    """Press `label` in whatever modal is up, or Esc-equivalent when None."""
    state = {"done": False}

    def look():
        if state["done"]:
            return
        dlg = QApplication.activeModalWidget()
        if not isinstance(dlg, QDialog) or not dlg.isVisible():
            QTimer.singleShot(5, look)
            return
        state["done"] = True
        if label is None:
            dlg.reject()                      # the close box / Esc
            return
        for b in dlg.findChildren(QPushButton):
            if b.text().replace("&", "") == label:
                b.click()
                return
        raise AssertionError(
            f"{label!r} is not on this window: "
            f"{[b.text() for b in dlg.findChildren(QPushButton)]}")

    QTimer.singleShot(0, look)


@pytest.mark.parametrize("optional,label,key", [
    (True,  "Start Calibration",  "\r"),
    (True,  "Skip this step",     "s"),
    (True,  "Cancel Measurement", "\x1b"),
    (True,  None,                 "\x1b"),
    (False, "Start Calibration",  "\r"),
    (False, "Cancel Measurement", "\x1b"),
    (False, None,                 "\x1b"),
])
def test_every_exit_sends_its_key_and_the_app_survives(tab, qapp, monkeypatch,
                                                       optional, label, key):
    sent: list[str] = []
    monkeypatch.setattr(tab._manager, "send_key", lambda k: sent.append(k))
    monkeypatch.setattr(tab, "_arm_key_watchdog", lambda: None)

    _answer(qapp, label)
    tab._on_calibration_prompt(cond="", message="", optional=optional)

    assert sent == [key], (
        f"{label or 'the close box'} on an optional={optional} window sent "
        f"{sent!r}, not {[key]!r}")

# NOTE: "is Skip wired to anything?" needs no test of its own. The row above
# proves it end to end: if nothing were connected, the window would never
# close, the modal watchdog in `tests/conftest.py` would shut it after four
# seconds, and no key would have been sent at all.
