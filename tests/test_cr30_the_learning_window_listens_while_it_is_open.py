"""The learning window must hear the presses made WHILE it is up.

It used to ask for the presses, wait to be dismissed, and only then start
listening — so every press made while reading it went nowhere. Basti pressed
once over Bluetooth on 2026-08-30, confirmed, and sat in front of a closed
window for 34 s before force-quitting the app.

These drive the real method with a reader shaped like the real one:
`learn_tile` blocks, reports each press through `on_press`, and honours
`cancelled`.
"""
import time

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPlainTextEdit, QWidget

from ui.tabs.tab_measure import TabMeasure


class _Reader:
    """Presses arrive on a schedule, exactly as a person supplies them."""

    guard_is_armed = False

    def __init__(self, kind="ble", presses=2, learns=True):
        self.open_transport, self._n, self._learns = kind, presses, learns
        self.saw_cancel = False

    def learn_tile(self, *, timeout=90.0, cancelled=None, on_press=None):
        for i in range(1, self._n + 1):
            end = time.monotonic() + 0.30
            while time.monotonic() < end:
                if cancelled and cancelled():
                    self.saw_cancel = True
                    return {"learned": False, "presses": i - 1, "provenance": ""}
                time.sleep(0.01)
            if callable(on_press):
                on_press(i)
        return {"learned": self._learns, "presses": self._n,
                "provenance": "two identical readings"}


def _host(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    host._log = QPlainTextEdit(host)
    host._flash_status = lambda *a, **k: None
    return host


def _live_dialog():
    for w in QApplication.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible():
            return w
    return None


def _live_line(dlg):
    for lab in dlg.findChildren(QLabel):
        if "press" in lab.text().lower() or "Reading" in lab.text():
            if "Waiting" in lab.text() or "Reading" in lab.text():
                return lab.text()
    return ""


def test_it_closes_itself_when_the_tile_is_proven(qtbot):
    """Nobody clicks anything: the presses alone finish it."""
    host, reader = _host(qtbot), _Reader(presses=2)
    TabMeasure._offer_cr30_tile_learning(host, reader)   # returns when closed
    assert _live_dialog() is None
    assert "has learned this instrument" in host._log.toPlainText()


def test_the_live_line_counts_the_presses_as_they_land(qtbot):
    seen = []
    host = _host(qtbot)

    def watch():
        dlg = _live_dialog()
        if dlg is not None:
            line = _live_line(dlg)
            if line and (not seen or seen[-1] != line):
                seen.append(line)

    timer = QTimer()
    timer.timeout.connect(watch)
    timer.start(20)
    TabMeasure._offer_cr30_tile_learning(host, _Reader(presses=2))
    timer.stop()

    assert seen, "the window never showed a live line"
    assert "Waiting" in seen[0], seen
    assert any("1" in s and "more press" in s for s in seen), (
        f"the first press was never reported on screen: {seen}")


def test_declining_stops_the_learner_and_says_what_it_costs(qtbot):
    host, reader = _host(qtbot), _Reader(presses=2)

    def decline():
        dlg = _live_dialog()
        if dlg is not None:
            dlg.reject()
        else:
            QTimer.singleShot(20, decline)

    QTimer.singleShot(20, decline)
    TabMeasure._offer_cr30_tile_learning(host, reader)
    # The learner runs on its own thread and is told to stop as the window
    # goes; it notices on its next poll, which is after this call returns.
    qtbot.waitUntil(lambda: reader.saw_cancel, timeout=3000)
    assert "built-in value" in host._log.toPlainText()


def test_a_press_after_the_window_closed_does_not_take_the_app_down(qtbot):
    """"Not now", then press the button anyway.

    The learner is usually still inside a read when the window goes, so the
    next press delivers `pressed` to a label Qt has already destroyed. Raised
    in a slot, PyQt6 turns that into an abort — so this fires the real signal
    on the real worker after the real window has closed.
    """
    host, kept = _host(qtbot), {}

    class _Late(_Reader):
        def learn_tile(self, *, timeout=90.0, cancelled=None, on_press=None):
            while not (cancelled and cancelled()):
                time.sleep(0.01)
            return {"learned": False, "presses": 0, "provenance": ""}

    def decline():
        dlg = _live_dialog()
        if dlg is None:
            QTimer.singleShot(20, decline)
            return
        # Hold the worker, which the tab drops as soon as its thread ends.
        kept["worker"] = host._learn_worker
        kept["label"] = [lab for lab in dlg.findChildren(QLabel)
                         if "Waiting" in lab.text()][0]
        dlg.reject()

    QTimer.singleShot(20, decline)
    TabMeasure._offer_cr30_tile_learning(host, _Late())
    qtbot.waitUntil(lambda: "worker" in kept, timeout=3000)
    QApplication.processEvents()

    from PyQt6 import sip
    assert sip.isdeleted(kept["label"]) or not kept["label"].isVisible(), (
        "the window is meant to be gone by now")
    kept["worker"].pressed.emit(1)      # the press that used to abort the app
    QApplication.processEvents()


@pytest.mark.parametrize("kind,expected", [("usb", "ONCE"), ("ble", "TWICE")])
def test_the_instruction_names_the_count_for_the_open_transport(qtbot, kind,
                                                                expected):
    host, said = _host(qtbot), []

    def look():
        dlg = _live_dialog()
        if dlg is None:
            QTimer.singleShot(20, look)
            return
        said.extend(lab.text() for lab in dlg.findChildren(QLabel))
        dlg.reject()

    QTimer.singleShot(20, look)
    TabMeasure._offer_cr30_tile_learning(host, _Reader(kind=kind, presses=9))
    body = "\n".join(said)
    assert expected in body, f"the window did not say {expected}: {body[:400]}"


def test_a_failure_is_not_reported_as_a_refusal(qtbot):
    """A learn that FAILS must say so, not "you declined".

    The stop flag is set unconditionally once the window has gone — a learner
    still reading after its window closed is the hang this was rebuilt to
    remove — and the note afterwards asked that same flag. So a link that went
    away, or readings that never agreed, both reported "you can carry on"
    and threw the instrument's own reason away.
    """
    host = _host(qtbot)

    class _Fails(_Reader):
        def learn_tile(self, *, timeout=90.0, cancelled=None, on_press=None):
            if callable(on_press):
                on_press(1)
            raise RuntimeError("BLE link went away")

    TabMeasure._offer_cr30_tile_learning(host, _Fails())
    said = host._log.toPlainText()
    assert "could not learn" in said, f"a failure said nothing about failing: {said}"
    assert "built-in value, which was measured on a different instrument" not in said, (
        "a failure was reported as though the user had declined")
    assert "BLE link went away" in said, (
        f"the instrument's own reason was thrown away: {said}")


def test_declining_still_says_what_it_costs(qtbot):
    """…and the refusal note must still appear when somebody really refuses."""
    host = _host(qtbot)

    def decline():
        dlg = _live_dialog()
        if dlg is None:
            QTimer.singleShot(20, decline)
        else:
            dlg.reject()

    QTimer.singleShot(20, decline)
    TabMeasure._offer_cr30_tile_learning(host, _Reader(presses=2))
    said = host._log.toPlainText()
    assert "built-in value" in said, f"declining said nothing: {said}"
    assert "could not learn" not in said, (
        "declining was also reported as a failure")


def test_a_reading_that_landed_is_counted_even_when_the_learn_raises(qtbot):
    """"Readings taken: 0" after a reading arrived reads as "it never
    answered", which sends the next person looking in the wrong place.

    `learn_tile` fills the press count in its RETURN value, so a raise carries
    none. The window counts what it actually saw instead.
    """
    host = _host(qtbot)

    class _OnePressThenGone(_Reader):
        def learn_tile(self, *, timeout=90.0, cancelled=None, on_press=None):
            if callable(on_press):
                on_press(1)                     # a reading really did land
            raise RuntimeError("BLE link went away")

    TabMeasure._offer_cr30_tile_learning(host, _OnePressThenGone())
    said = host._log.toPlainText()
    assert "Readings taken: 1" in said, (
        f"a reading that arrived was reported as none: {said}")
