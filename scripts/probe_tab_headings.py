#!/usr/bin/env python3
"""Every tab heading, measured as INK rather than as advance, in a real window.

Sebastian: *"the last letter has a few px cut off"* on Print Chart, twice, in a
heading that looks almost right. That is the signature of a display face whose
final glyph paints past its own advance: `QLabel` sizes itself from
`horizontalAdvance`, so the ink of the last letter can fall outside the widget
even when "the text fits". The heading also carries `setLetterSpacing(85 %)`,
which pulls every advance in by 15 % and makes the gap wider.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-uk/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-uk/presets
    python scripts/probe_tab_headings.py <out.json> [uk|en|de]
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

from PyQt6.QtGui import QFontMetrics                              # noqa: E402
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
    from ui.tab_header import TabHeader
    win = MainWindow(settings)
    apply_appearance(app, win, "light")
    win.resize(1360, 900)
    win.show()
    pump(app, 2500)

    tabs = win.findChild(QTabWidget)
    rows = []
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        pump(app, 1500)
        for h in tabs.widget(i).findChildren(TabHeader):
            lbl = h._title_lbl
            if not lbl.isVisible():
                continue
            text = lbl.text()
            fm = QFontMetrics(lbl.font())
            adv = fm.horizontalAdvance(text)
            tight = fm.tightBoundingRect(text)
            ink_right = max(tight.right() + 1, fm.boundingRect(text).right() + 1)
            rows.append({
                "tab": i, "text": text,
                "font": lbl.font().family(),
                "px": lbl.font().pixelSize(), "pt": lbl.font().pointSizeF(),
                "letter_spacing": lbl.font().letterSpacing(),
                "advance_px": adv,
                "ink_right_px": ink_right,
                "ink_overhang_px": ink_right - adv,
                "label_w": lbl.width(),
                "sizeHint_w": lbl.sizeHint().width(),
                "ink_outside_label_px": ink_right - lbl.width(),
                "dpr": lbl.devicePixelRatioF(),
            })
    res = {"lang": lang, "headings": rows}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    for r in rows:
        flag = "CUT" if r["ink_outside_label_px"] > 0 else "ok "
        print(f"  {flag} tab{r['tab']} adv={r['advance_px']:4} "
              f"ink={r['ink_right_px']:4} label={r['label_w']:4} "
              f"outside={r['ink_outside_label_px']:3} "
              f"font={r['font']} {r['px']}px/{r['pt']}pt "
              f"spacing={r['letter_spacing']}  {r['text']!r}")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
