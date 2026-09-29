#!/usr/bin/env python3
"""The four Print Chart buttons, measured in a real window, in one language.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-uk/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-uk/presets
    python scripts/probe_print_chart_buttons.py <out.json> [uk|en|de]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if os.environ.get("QT_QPA_PLATFORM"):
    raise SystemExit("this driver opens a window")
for var in ("CHROMIQ_SETTINGS_FILE", "CHROMIQ_PRESETS_DIR"):
    if not os.environ.get(var):
        raise SystemExit(f"{var} is not set")

from PyQt6.QtGui import QFont, QFontMetrics                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QTabWidget              # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    lang = sys.argv[2] if len(sys.argv) > 2 else "uk"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.setCursorFlashTime(0)
    from core.settings import AppSettings
    settings = AppSettings()
    assert "/tmp/chromiq-uk" in settings._qs.fileName()
    settings.set("appearance", "light")
    settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    i18n.install_qt_translator(app)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    apply_appearance(app, win, "light")
    win.resize(1360, 900)
    win.show()
    pump(app, 2500)
    tabs = win.findChild(QTabWidget)
    tabs.setCurrentIndex(1)
    pump(app, 2500)
    page = tabs.widget(1)
    tp = None
    for w in (page, *page.findChildren(type(page))):
        if hasattr(w, "_print_page_btn"):
            tp = w
            break
    if tp is None:
        tp = page
    rows = []
    names = ("_print_page_btn", "_print_all_btn",
             "_clear_queue_btn", "_save_defaults_btn")
    for n in names:
        b = getattr(tp, n, None)
        if b is None:
            continue
        text = (b.text() or "")
        painted = (text.upper()
                   if b.font().capitalization() == QFont.Capitalization.AllUppercase
                   else text)
        fm = QFontMetrics(b.font())
        lines = painted.split("\n")
        rows.append({
            "attr": n, "text": text, "lines": len(lines),
            "line_px": [fm.horizontalAdvance(x) for x in lines],
            "widest_line_px": max(fm.horizontalAdvance(x) for x in lines),
            "button_w": b.width(), "button_h": b.height(),
            "minimumWidth": b.minimumWidth(),
            "minimumSizeHint": b.minimumSizeHint().width(),
            "sizeHint": b.sizeHint().width(),
            "line_height_px": fm.height(),
            "visible": b.isVisible(),
            "font": b.font().family(),
        })
    res = {"lang": lang, "row_width_available": tp.width(), "buttons": rows}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
