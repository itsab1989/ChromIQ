"""On-screen proof for B8-638, B8-756 and B8-1078, in REAL windows.

One process per language and appearance, because the UI language is chosen at
start-up and the help cards are translated when their module is imported:

    python scripts/drive_stable_fixes_a.py <lang> <light|dark> <what> <out_dir>

<what> is one of:
  welcome   the Welcome window on a help card: does "Save as PDF…" fit? (B8-638)
  prefs     Preferences: does the whole tab bar show when it opens?    (B8-756)
  checkbox  a disabled ticked box under the report window's own rules  (B8-1078)

Prints one JSON line of measurements and, unless NO_PHOTO is set, saves a
photograph of the window taken with scripts/onscreen_capture.py.

Run with CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR and CHROMIQ_LOG_DIR set to
sandbox paths. A watchdog closes any window this driver did not open, and
records it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

LANG, MODE, WHAT, OUT = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "sandbox the settings first"

import faulthandler  # noqa: E402
faulthandler.dump_traceback_later(100, exit=True)

from core import i18n  # noqa: E402

i18n.set_language(LANG)          # BEFORE any UI module is imported

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QLabel,  # noqa: E402
                             QVBoxLayout)

from capture_screens import build_app  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.theme import apply_appearance  # noqa: E402

app = build_app()
i18n.install_qt_translator(app)   # as main() does: Qt's own OK/Cancel
settings = AppSettings()
settings.set("appearance", MODE)
apply_appearance(app, None, MODE)
OUT.mkdir(parents=True, exist_ok=True)
result: dict = {"lang": LANG, "mode": MODE, "what": WHAT, "watchdog": []}
ours: list = []


def watchdog() -> None:
    for w in QApplication.topLevelWidgets():
        if w.isVisible() and isinstance(w, QDialog) and w not in ours:
            result["watchdog"].append(
                f"{type(w).__name__}: {w.windowTitle()!r}")
            w.close()


def settle(ms: int = 600) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def photograph(win, name: str) -> None:
    if os.environ.get("NO_PHOTO"):
        return
    from onscreen_capture import capture_window
    path = OUT / f"{LANG}-{MODE}-{name}.png"
    try:
        ok, why = capture_window(win, path)
        result["photo" if ok else "photo_error"] = str(path) if ok else why
    except Exception as exc:          # noqa: BLE001 - report, never hide
        result["photo_error"] = repr(exc)


dog = QTimer()
dog.timeout.connect(watchdog)
dog.start(300)

if WHAT == "welcome":
    from ui.dialogs.welcome_dialog import WorkflowCard, WelcomeDialog
    d = WelcomeDialog(settings, None, initial_mode=MODE)
    ours.append(d)
    d.show()
    settle()
    d._on_card_clicked(d.findChildren(WorkflowCard)[0]._key)
    settle(900)
    buttons = {}
    for b in (d._pdf_btn, d._print_btn, d._back_btn, d._close_btn):
        if b.isVisible():
            buttons[b.text()] = {"width": b.width(),
                                 "needs": b.sizeHint().width(),
                                 "fits": b.width() >= b.sizeHint().width()}
    result["buttons"] = buttons
    result["ok"] = all(v["fits"] for v in buttons.values()) and bool(buttons)
    photograph(d, "welcome")
elif WHAT == "prefs":
    from ui.dialogs.settings_dialog import SettingsDialog
    d = SettingsDialog(settings, None)
    ours.append(d)
    d.show()
    settle(900)
    bar = d._tabs.tabBar()
    last = bar.tabRect(bar.count() - 1)
    result.update({
        "dialog_width": d.width(),
        "bar_needs": bar.sizeHint().width(),
        "bar_width": bar.width(),
        "last_tab_right": last.right(),
        "last_tab": bar.tabText(bar.count() - 1),
        "ok": last.right() <= bar.width() and bar.sizeHint().width() <= bar.width(),
        "fits_1512": d.width() <= int(1512 * 0.9),
    })
    photograph(d, "preferences")
elif WHAT == "checkbox":
    from ui.dialogs.tools_dialogs import neutral_controls_qss
    from ui.styles import SPEC_GREEN
    d = QDialog()
    ours.append(d)
    d.setWindowTitle("B8-1078: disabled checkbox states")
    d.setStyleSheet(neutral_controls_qss(SPEC_GREEN, popup=SPEC_GREEN))
    lay = QVBoxLayout(d)
    for text, checked, enabled in (
            ("Enabled, ticked", True, True),
            ("Enabled, not ticked", False, True),
            ("Show detailed data for each run (disabled, ticked)", True, False),
            ("Disabled, not ticked", False, False)):
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setEnabled(enabled)
        lay.addWidget(cb)
    lay.addWidget(QLabel(f"appearance: {MODE}"))
    d.resize(460, 190)
    d.show()
    settle(900)
    result["ok"] = True
    photograph(d, "checkbox")

settle(300)
print(json.dumps(result, ensure_ascii=False))
