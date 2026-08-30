#!/usr/bin/env python3
"""Proof 34 — does the instrument choice follow the chart? ONE case per run.

Drives the REAL ChromIQ app on the REAL screen with the REAL settings store,
entering each project through the session-restore path (main_window.py:2397),
which is the documented .ti1 trap: the Measure tab is handed run.chart_ti1.

    python drive_proof34.py cr30_engine   # CR30 chart, ChromIQ reader
    python drive_proof34.py cr30_stock    # CR30 chart, stock ArgyllCMS reader
    python drive_proof34.py munki         # ColorMunki chart, both instruments on
    python drive_proof34.py i1pro         # i1 Pro chart, ColorMunki connected
    python drive_proof34.py noinstr       # chart with no TARGET_INSTRUMENT

Every modal window is screenshotted and then answered with its safest button
(Discard > RejectRole/Cancel > reject()). The CR30 is sent nothing: the one
CR30 window this can reach is "Calibrate the instrument", and Cancel there is
taken before any device command (DeviceReader opens on first use).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path("/Users/Basti/develop/ChromIQ")
sys.path.insert(0, str(ROOT))
SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)

CASES = {
    #  name         project            chartread_engine
    "cr30_engine": ("Proof34-CR30",    "chromiq"),
    "cr30_stock":  ("Proof34-CR30",    "argyll"),
    "munki":       ("Proof34-Munki",   "chromiq"),
    "i1pro":       ("Proof34-i1Pro",   "chromiq"),
    "noinstr":     ("Proof34-NoInstr", "chromiq"),
}
CASE = sys.argv[1]
PROJECT, ENGINE = CASES[CASE]

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication, #38)
except ImportError:
    pass

from PyQt6.QtCore import Qt, QTimer                     # noqa: E402
from PyQt6.QtGui import QFontDatabase                   # noqa: E402
from PyQt6.QtTest import QTest                          # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,     # noqa: E402
                             QMessageBox, QPushButton)

from core.resource_path import resource_path            # noqa: E402

DIALOGS: list[str] = []
_handled: set[int] = set()
_shot_n = 0


def say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def shot(widget, label: str) -> None:
    global _shot_n
    _shot_n += 1
    p = SHOTS / f"{CASE}-{_shot_n:02d}-{label}.png"
    try:
        widget.grab().save(str(p))
        say(f"shot: {p.name}")
    except Exception as exc:  # noqa: BLE001
        say(f"shot FAILED ({label}): {exc}")


def _dialog_text(w) -> str:
    bits = [w.windowTitle()]
    if isinstance(w, QMessageBox):
        bits += [w.text(), w.informativeText()]
    return " | ".join(b.replace("\n", " ") for b in bits if b)


def _answer(w) -> None:
    """Screenshot, log, then press the safest button."""
    shot(w, "dialog")
    txt = _dialog_text(w)
    DIALOGS.append(txt)
    say(f"MODAL: {txt[:220]}")
    btns = w.findChildren(QPushButton)
    # 1) an explicit Discard (the ending window's safe exit)
    for b in btns:
        if "discard" in b.text().lower():
            say(f"  clicking: {b.text()!r}")
            QTest.mouseClick(b, Qt.MouseButton.LeftButton)
            return
    # 2) the RejectRole button of a QMessageBox
    if isinstance(w, QMessageBox):
        for b in w.buttons():
            if w.buttonRole(b) == QMessageBox.ButtonRole.RejectRole:
                say(f"  clicking: {b.text()!r}")
                QTest.mouseClick(b, Qt.MouseButton.LeftButton)
                return
    # 3) a button literally named Cancel
    for b in btns:
        if b.text().replace("&", "").strip().lower() in ("cancel", "annuleren",
                                                         "abbrechen", "stop"):
            say(f"  clicking: {b.text()!r}")
            QTest.mouseClick(b, Qt.MouseButton.LeftButton)
            return
    say("  no safe button found -> reject()/close()")
    if isinstance(w, QDialog):
        w.reject()
    else:
        w.close()


def watch() -> None:
    w = QApplication.activeModalWidget()
    if w is None or id(w) in _handled:
        return
    _handled.add(id(w))
    # let it finish painting before the grab, then answer it
    QTimer.singleShot(700, lambda: _answer(w))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))

    from core.settings import AppSettings
    from ui.main_window import MainWindow

    settings = AppSettings()
    settings.set("restore_last_session", True)
    settings.set("session_target_name", PROJECT)
    settings.set("session_project_root", "")
    settings.set("chartread_engine", ENGINE)
    say(f"case={CASE} project={PROJECT} engine={ENGINE}")

    timer = QTimer()
    timer.timeout.connect(watch)
    timer.start(250)

    win = MainWindow(settings)
    win.show()
    pump(app, 1500)          # session restore fires on a 0ms timer

    tab = win._tab_measure
    t0 = time.time()
    while time.time() - t0 < 10:
        p = getattr(tab, "_ti1_path", None)
        if p is not None and PROJECT in str(p):
            break
        pump(app, 200)
    say(f"measure tab chart file: {getattr(tab, '_ti1_path', None)}")
    say(f"_chart_is_cr30() -> {tab._chart_is_cr30()}")

    win._tabs.setCurrentWidget(tab)
    pump(app, 800)
    shot(win, "measure-tab-before-start")
    say(f"Start enabled: {tab._start_btn.isEnabled()} "
        f"tooltip: {tab._start_btn.toolTip()[:120]!r}")
    say(f"pbp guided: checked={tab._pbp_cb.isChecked()} "
        f"enabled={tab._pbp_cb.isEnabled()} tip={tab._pbp_cb.toolTip()[:90]!r}")

    say("pressing Start")
    QTest.mouseClick(tab._start_btn, Qt.MouseButton.LeftButton)
    pump(app, 1000)

    # For the paths that launch a real reader process, wait for the instrument
    # to be named in the log, then stop.
    runner = tab._runner
    t0 = time.time()
    seen = ""
    while time.time() - t0 < 60:
        pump(app, 500)
        logtxt = tab._log.toPlainText()
        if "Instrument Type" in logtxt and "Instrument Type" not in seen:
            seen = "Instrument Type"
            say("log names the instrument -> screenshot")
            shot(win, "instrument-named")
            break
        if not runner.is_running and time.time() - t0 > 6:
            say("runner idle — start sequence ended without a reader process")
            break
    # Give a reactive dialog (the chart/instrument mismatch warning) time to
    # appear and be answered by the watcher before touching Stop.
    pump(app, 3500)
    if runner.is_running:
        say("pressing Stop")
        QTest.mouseClick(tab._stop_btn, Qt.MouseButton.LeftButton)
        t0 = time.time()
        while runner.is_running and time.time() - t0 < 30:
            pump(app, 400)
        say(f"runner stopped: {not runner.is_running}")

    pump(app, 1200)
    shot(win, "final")
    out = SHOTS / f"{CASE}-uilog.txt"
    out.write_text(tab._log.toPlainText())
    say(f"UI log saved: {out.name}")
    say("DIALOG SUMMARY: " + (" || ".join(DIALOGS) if DIALOGS else "none"))
    win.close()
    pump(app, 400)
    os._exit(0)


if __name__ == "__main__":
    main()
