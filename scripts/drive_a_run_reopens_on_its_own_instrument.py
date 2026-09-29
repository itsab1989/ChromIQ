#!/usr/bin/env python3
"""Drive the REAL window: does a CR30 project reopen as a CR30?

Basti, 2026-09-08: *"i have loaded the youtube project and the chart was made
for the cr30. but in guided mode it shows colormunki"*.

Three things are shown, in the order they bite:

1. a run whose stored Guided row says CR30 comes back on screen as CR30, with
   a disagreeing recipe stored beside it AND a global "Save as Defaults" left
   behind, which is the combination that used to lose;
2. the two modules still agree afterwards, so this was not bought by muting the
   Guided/Manual mirror;
3. a control the current instrument hides keeps its value: "No strip-length
   limit" and "Triple density" used to be force-unchecked and the loss stored,
   against the confirmed rule that an instrument change may not overwrite a
   value somebody chose (per_target_settings.md 4c D-2).

Run it against this checkout and against a master worktree to see the
difference. Settings and the ChromIQ root are sandboxed; nothing of the user's
is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-reopen.ini \
        python scripts/drive_a_run_reopens_on_its_own_instrument.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings, Qt                           # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtTest import QTest                                   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,              # noqa: E402
                             QMessageBox)

from core.resource_path import resource_path                     # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "run-reopens-on-its-own-instrument"

STORED_CR30 = {
    "mode": "guided",
    "engine_on": True,
    "guided": {"instrument": "CR30", "paper": "A4", "pages": 1,
               "double_density": True, "triple_density": False,
               "left_border": False, "no_strip_limit": False, "precond": ""},
}


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def run(app) -> int:
    from core.settings import AppSettings
    from workflow.layout_engine.presets import default_recipe

    sb = Path(tempfile.mkdtemp(prefix="chromiq-reopen-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sb / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    s = AppSettings()
    s._qs = dst
    work = sb / "ChromIQ"
    work.mkdir()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    s.set("use_chromiq_layout_engine", True)
    # what "Save as Defaults" in the layout panel leaves behind, globally
    s.set("manual_engine_recipe",
          json.dumps(default_recipe("CM", "A4").to_dict()))

    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("guided")
    pump(app, 1200)

    bad = 0
    SHOTS.mkdir(parents=True, exist_ok=True)

    print("\n  1. a run that says CR30, with a CM recipe beside it and a CM "
          "saved default")
    tab._apply_ui_state(dict(STORED_CR30,
                             engine_recipe=default_recipe("CM", "A4").to_dict()))
    pump(app, 1200)
    g = tab._shared_get("guided")
    m = str(tab._manual_get("printtarg", "-i", ""))
    print(f"        Guided instrument : {g['instrument']!r}")
    print(f"        density tick      : {g['double_density']!r}")
    print(f"        Manual  -i        : {m!r}")
    win.grab().save(str(SHOTS / "01-reopened.png"))
    if g["instrument"] != "CR30" or g["double_density"] is not True:
        print("        >>> the run did not come back on its own instrument")
        bad += 1
    if m != "CR30":
        print("        >>> the two modules disagree")
        bad += 1

    print("\n  2. a control the other instrument hides keeps its value")

    def pick(code):
        c = tab._instr_combo
        i = c.findData(code)
        c.showPopup()
        pump(app, 300)
        v = c.view()
        v.setCurrentIndex(c.model().index(i, 0))
        pump(app, 120)
        QTest.keyClick(v, Qt.Key.Key_Return)
        pump(app, 600)
        if c.currentData() != code:
            c.hidePopup()
            c.setCurrentIndex(i)
            c.activated.emit(i)
            pump(app, 400)

    for box, owner, visitor, name in (
            ("_nsl_check", "i1", "CR30", "No strip-length limit"),
            ("_td_check", "CM", "i1", "Triple density")):
        pick(owner)
        getattr(tab, box).setChecked(True)
        pick(visitor)
        hidden = getattr(tab, box).isHidden()
        pick(owner)
        kept = getattr(tab, box).isChecked()
        print(f"        {name:<22} ticked on {owner}, hidden on {visitor} "
              f"({hidden}), back on {owner}: {'KEPT' if kept else 'LOST'}")
        if not kept:
            bad += 1
    win.grab().save(str(SHOTS / "02-after-the-round-trips.png"))

    win.close()
    pump(app, 400)
    print(f"\n  problems: {bad}")
    print(f"  screenshots in {SHOTS}")
    return 1 if bad else 0


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    return run(app)


if __name__ == "__main__":
    raise SystemExit(main())
