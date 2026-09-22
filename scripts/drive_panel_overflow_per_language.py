#!/usr/bin/env python3
"""Does the Create Chart panel FIT its viewport, in every shipped language?

Found on the downloaded v4.3.0-beta.30 arm64 dmg: in Ukrainian the guided
panel is 565 px wide inside a 540 px viewport and the scroll area's horizontal
policy is ScrollBarAlwaysOff, so the last 25 px cannot be reached by any means
a user has. The rightmost column of that panel is the per-row info button, so
four of them are sliced in half by the viewport edge.

`drive_uk_language_on_screen.py` already recorded the two numbers (565 vs 540)
and its `icons` list came back EMPTY, because it collected only TooltipButtons
whose `parentWidget() is panel` and every one of them lives one level deeper,
inside a QGroupBox. A probe that cannot express the fault reported nothing and
the round read the nothing as "fine". This driver walks the whole subtree and
reports the overflow as a NUMBER per language.

    export CHROMIQ_SETTINGS_FILE=...   # sandboxed, refused otherwise
    export CHROMIQ_PRESETS_DIR=...
    python scripts/drive_panel_overflow_per_language.py <out-dir> <lang>

ON SCREEN. A real window, and the photograph goes through
`onscreen_capture.capture_window`, never `widget.grab()`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    raise SystemExit("CHROMIQ_SETTINGS_FILE is not set: refusing to write "
                     "into the owner's real preferences.")
if not os.environ.get("CHROMIQ_PRESETS_DIR"):
    raise SystemExit("CHROMIQ_PRESETS_DIR is not set.")
if os.environ.get("QT_QPA_PLATFORM"):
    raise SystemExit("QT_QPA_PLATFORM is set. This driver opens a WINDOW.")

from PyQt6.QtCore import QPoint                                  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QScrollArea,          # noqa: E402
                             QTabWidget, QWidget)

from onscreen_capture import capture_window                      # noqa: E402


def pump(app, ms=400):
    from PyQt6.QtCore import QElapsedTimer
    t = QElapsedTimer(); t.start()
    while t.elapsed() < ms:
        app.processEvents()


def scroll_area_of(w: QWidget):
    p = w.parentWidget()
    while p is not None and not isinstance(p, QScrollArea):
        p = p.parentWidget()
    return p


def measure(win, lang: str) -> dict:
    """The guided Create Chart panel, and every info button inside it."""
    from ui.tooltip_button import TooltipButton
    tabs = win.findChild(QTabWidget)
    chart = tabs.widget(0)

    # The scroll area that holds the guided panel: the one whose widget()
    # carries the most TooltipButtons, so nothing depends on a class name.
    best = None
    for sa in chart.findChildren(QScrollArea):
        inner = sa.widget()
        if inner is None:
            continue
        n = len([b for b in inner.findChildren(TooltipButton) if b.isVisible()])
        if best is None or n > best[1]:
            best = (sa, n)
    if best is None or best[1] == 0:
        return {"lang": lang, "error": "no scroll area with info buttons"}
    sa, _ = best
    panel = sa.widget()
    vp = sa.viewport()

    rows = []
    for b in panel.findChildren(TooltipButton):
        if not b.isVisible():
            continue
        # Right edge of the button in the VIEWPORT's coordinates: that is the
        # edge the window server actually clips against.
        tl = b.mapTo(vp, QPoint(0, 0))
        right = tl.x() + b.width()
        rows.append({"right_in_viewport": right,
                     "over_px": right - vp.width(),
                     "y": tl.y(),
                     "tip": (b.toolTip() or "")[:40]})
    rows.sort(key=lambda r: -r["over_px"])
    clipped = [r for r in rows if r["over_px"] > 0]

    return {
        "lang": lang,
        "panel_width": panel.width(),
        "panel_sizeHint": panel.sizeHint().width(),
        "panel_minimumSizeHint": panel.minimumSizeHint().width(),
        "viewport_width": vp.width(),
        "overflow_px": panel.width() - vp.width(),
        "hbar_policy": sa.horizontalScrollBarPolicy().name,
        "hbar_visible": sa.horizontalScrollBar().isVisible(),
        "hbar_maximum": sa.horizontalScrollBar().maximum(),
        "vbar_visible": sa.verticalScrollBar().isVisible(),
        "info_buttons": len(rows),
        "info_buttons_clipped": len(clipped),
        "worst_over_px": rows[0]["over_px"] if rows else None,
        "clipped": clipped[:10],
    }


def main() -> int:
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2]

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.setCursorFlashTime(0)

    from core.settings import AppSettings
    settings = AppSettings()
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

    res = measure(win, lang)
    res["settings_store"] = settings._qs.fileName()
    res["window_size"] = [win.width(), win.height()]

    shot = out / f"panel-{lang}.png"
    ok, why = capture_window(win, shot)
    res["photo"] = {"ok": bool(ok), "why": str(why), "file": shot.name}

    (out / f"overflow-{lang}.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "clipped"},
                     ensure_ascii=False))
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
