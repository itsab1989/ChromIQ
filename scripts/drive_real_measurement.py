#!/usr/bin/env python3
"""Set a real measurement up to the point a human has to swipe, then watch.

Everything else in this repo measures with Argyll's ``fakeread``. This is the
one path synthetic data cannot reach: a real instrument, a real printed chart,
and the windows that only appear while chartread is actually running — the
abort confirmation, Save Partial & Quit, the wrong-strip and slow-down notices.
Those matter because beta.160 shipped a fix to one of them that had **never
once run**: the event existed only in the stock reader's parser, so on the
ChromIQ engine no window ever appeared, and six more of the same shape turned
up afterwards.

    python scripts/drive_real_measurement.py <project> [run] [--replace]

It opens the project, selects the run, answers the "this chart already has a
measurement" dialog, presses Start Measurement — and then **stops
interfering**. From that point it only observes: every new log line, and every
window that appears, with its title and buttons. It must not dismiss anything,
because the person holding the instrument is the one who should answer.

Uses the REAL settings deliberately: a redirected store would not be testing
what the user actually runs.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QPlainTextEdit,  # noqa: E402
                             QPushButton)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    replace = "--replace" in sys.argv
    project = args[0] if args else "Knut-Scanner"
    run_id = args[1] if len(args) > 1 else "run1"

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")
    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    from core.settings import AppSettings
    settings = AppSettings()          # the REAL store, on purpose
    apply_appearance(app, None, settings.get("appearance", "light"))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    apply_appearance(app, win, settings.get("appearance", "light"))
    win.resize(1500, 1000)
    win.show()

    def settle(ms: int) -> None:
        end = time.time() + ms / 1000
        while time.time() < end:
            app.processEvents()
            time.sleep(0.01)

    settle(1500)
    # OPEN IT THE WAY THE APP DOES.
    #
    # set_target_name() alone points the FileManager at the folder but tells
    # nothing else, so the run bar still offered only "New run" and the Measure
    # tab had no chart. _restore_last_session() is the app's own path: it opens
    # the project, reads its current run and calls set_profile_run, which is
    # what actually populates the bar. It keys off session_target_name, not
    # target_name — a distinction that cost two restarts to notice.
    settings.set("session_target_name", project)
    settings.set("session_project_root", "")
    win._restore_last_session()
    settle(1500)
    print(f"[setup] project = {project}")

    # DRIVE THE COMBOS, NOT THE CONTROLLER.
    #
    # Calling ctl.set_profile_run() directly changes the selection but never
    # emits currentIndexChanged, so nothing downstream is told — the Measure
    # tab keeps whatever chart it had, which here was none, and Start
    # Measurement stays disabled. A person clicking the dropdown fires that
    # signal; the point of an on-screen driver is to do what they do.
    bar = win._target_bar
    for combo, want, label in ((bar._type_combo, "Profiling", "run type"),
                               (bar._run_combo, run_id, "run")):
        idx = -1
        for i in range(combo.count()):
            data = combo.itemData(i)
            if data == want or combo.itemText(i).strip() == want:
                idx = i
                break
        if idx < 0 and want == run_id:      # "Run 1" rather than "run1"
            for i in range(combo.count()):
                if want.replace("run", "").strip() in combo.itemText(i):
                    idx = i
                    break
        if idx >= 0:
            combo.setCurrentIndex(idx)
            settle(700)
            print(f"[setup] {label} -> {combo.itemText(idx)!r}")
        else:
            print(f"[setup] !! no {label} entry for {want!r} in "
                  f"{[combo.itemText(i) for i in range(combo.count())]}")

    measure_idx = next((i for i in range(win._tabs.count())
                        if "Measure" in win._tabs.tabText(i)), 2)
    win._tabs.setCurrentIndex(measure_idx)
    settle(1500)
    print(f"[setup] on tab {win._tabs.tabText(measure_idx)!r}")

    # The ONE dialog this script answers: "this chart already has a
    # measurement". Everything after Start Measurement belongs to the person
    # holding the instrument.
    answered = False
    for w in app.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible():
            title = w.windowTitle()
            if "already has a measurement" in title.lower():
                for b in w.findChildren(QPushButton):
                    if b.text().strip().upper().startswith("OK"):
                        print(f"[setup] answering {title!r} with OK "
                              f"({'replace' if replace else 'as configured'})")
                        b.click()
                        answered = True
                        break
    if not answered:
        print("[setup] no pre-measurement dialog was open")
    settle(800)

    tab = win._tabs.widget(measure_idx)
    logs = [w for w in tab.findChildren(QPlainTextEdit) if w.objectName() == "log"]
    log = logs[0] if logs else None
    seen_lines = 0
    seen_windows: set[str] = set()

    start = next((b for b in tab.findChildren(QPushButton)
                  if b.text().replace("&", "").strip().upper() == "START MEASUREMENT"), None)
    if start is None:
        print("[setup] !! could not find Start Measurement")
    elif not start.isEnabled():
        print("[setup] !! Start Measurement is disabled — nothing to measure")
    else:
        print("\n[GO] pressing Start Measurement — the instrument is yours now.\n"
              "     Calibrate on the base when asked, then swipe each strip the\n"
              "     app names. Everything below is what the app reports.\n")
        start.click()

    def poll():
        nonlocal seen_lines
        if log is not None:
            text = log.toPlainText().splitlines()
            for line in text[seen_lines:]:
                print(f"  | {line}")
            seen_lines = len(text)
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                title = w.windowTitle() or w.__class__.__name__
                if title not in seen_windows:
                    seen_windows.add(title)
                    btns = [b.text().replace("&", "") for b in w.findChildren(QPushButton)
                            if b.isVisible()]
                    print(f"\n  >> WINDOW: {title!r}  buttons={btns}\n")
        sys.stdout.flush()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(700)

    # Long, because a human is swiping 21 strips. Still bounded, so nothing of
    # mine is ever left sitting on someone's screen.
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(lambda: (print("\n[watchdog] 45 min — exiting"),
                                   app.quit()))
    guard.start(45 * 60 * 1000)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
