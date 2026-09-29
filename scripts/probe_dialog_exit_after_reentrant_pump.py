#!/usr/bin/env python3
"""Does a dialog's exec() return when it is accepted from a timer and the
same callback then keeps calling processEvents()? On screen (cocoa), no Qt
but plain widgets, no ChromIQ.

This is the pattern `scripts/userdrive.Drive.answer_file` used: `w.accept()`
and then `self.pump(600)`, a loop of `QApplication.processEvents()` inside the
timer callback that runs within the dialog's own exec(). The question is
whether the dialog's loop notices it was told to exit.

Three ways of answering, N rounds each, one outer "window" loop (as the
report window's own exec()) under every dialog, the way the app stacks them:

    pump-after-accept   accept(), then processEvents() for 600 ms (the driver)
    accept-and-return   accept(), return straight to the loop (a user's click)
    queued-click        QTimer.singleShot(0, accept), then pump (queued)

Prints, per round, how long exec() took to return after the accept.

    python scripts/probe_dialog_exit_after_reentrant_pump.py [rounds]
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QTimer                               # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout  # noqa: E402

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
HOLD_S = 8.0          # how long a stuck loop is given before it is released


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    outer = QDialog()
    outer.setWindowTitle("outer (the report window)")
    QVBoxLayout(outer).addWidget(QLabel("outer window"))
    outer.resize(420, 200)
    results = []

    def one_round(mode, idx):
        inner = QDialog(outer)
        inner.setWindowTitle(f"inner {mode} {idx}")
        QVBoxLayout(inner).addWidget(QLabel("the file chooser"))
        inner.resize(300, 120)
        stamp = {}

        def answer():
            stamp["t"] = time.monotonic()
            if mode == "pump-after-accept":
                inner.accept()
                pump(app, 600)
            elif mode == "accept-and-return":
                inner.accept()
            else:
                QTimer.singleShot(0, inner.accept)
                pump(app, 600)

        def release():                  # what closing the report window does
            if "back" not in stamp:
                stamp["released"] = True
                outer.hide()
                outer.show()
                QTimer.singleShot(0, lambda: None)
                app.postEvent(outer, __import__("PyQt6.QtCore", fromlist=[
                    "QEvent"]).QEvent(__import__("PyQt6.QtCore", fromlist=[
                        "QEvent"]).QEvent.Type.User))
                # the report window closing ends ITS loop, and the
                # dispatcher is interrupted on the way: do the same
                from PyQt6.QtCore import QEventLoop
                lp = QEventLoop()
                QTimer.singleShot(0, lp.quit)
                lp.exec()

        QTimer.singleShot(700, answer)
        watchdog = QTimer()
        watchdog.setInterval(int(HOLD_S * 1000))
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(release)
        watchdog.start()
        # a steady tick, as the drive's own timers are: a loop that is
        # stuck still runs these, which is how it looked in the drive
        ticks = QTimer()
        ticks.setInterval(250)
        ticks.timeout.connect(lambda: None)
        ticks.start()
        rc = inner.exec()
        stamp["back"] = time.monotonic()
        ticks.stop()
        watchdog.stop()
        results.append({"mode": mode, "round": idx, "rc": rc,
                        "returned_after_s": round(stamp["back"] - stamp["t"], 2),
                        "needed_release": bool(stamp.get("released"))})
        print(json.dumps(results[-1]), flush=True)
        inner.deleteLater()

    def run_all():
        for mode in ("pump-after-accept", "accept-and-return", "queued-click"):
            for i in range(ROUNDS):
                one_round(mode, i)
        outer.accept()

    QTimer.singleShot(300, run_all)
    outer.show()
    outer.exec()
    summary = {}
    for r in results:
        s = summary.setdefault(r["mode"], {"rounds": 0, "stuck": 0,
                                           "max_s": 0.0})
        s["rounds"] += 1
        s["stuck"] += int(r["needed_release"])
        s["max_s"] = max(s["max_s"], r["returned_after_s"])
    print("SUMMARY " + json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
