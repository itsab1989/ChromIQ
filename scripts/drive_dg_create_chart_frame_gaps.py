#!/usr/bin/env python3
"""AGENT DG — the two info frames under the Create Chart TIFF preview.

Basti, 4.2.0: "In the Create Chart tab under the TIFF preview, the left side of
the frame around the Measured from Preview section touches the panel separator,
and the right side of the frame around the Chart layout information section
touches the right side of the main window. There should be a gap."

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-dg.ini
    python scripts/drive_dg_create_chart_frame_gaps.py --tag before

WHAT IT MEASURES, and why it is measured this way. Both panels are plain
`QGroupBox`es and the app's stylesheet gives them `margin-top: 14px` and NO
left/right margin, so the 1 px border Basti can see is drawn AT the widget's own
left and right edge. That makes the gap he is complaining about a pure geometry
question: `panel.mapTo(win, (0,0)).x()` minus the splitter handle's right edge on
one side, and the window's right edge minus the panel's right edge on the other.
No pixel scan needed; the shots are for him, not for the number.

IT BUILDS THE APP THE WAY `main()` DOES. Fonts, `WinButtonLayoutStyle("Fusion")`,
`apply_appearance`, and — the one that matters here — `CompositeAppFilter`
installed on the application. That filter runs `ButtonFontFilter.relayout_around`,
which calls `layout.activate()` from inside an application event filter, so
widths measured without it are widths no user ever sees. One finding on this
project has already been withdrawn for exactly that.

The settings store is sandboxed by `CHROMIQ_SETTINGS_FILE` (CLAUDE.md) and this
script refuses to start without it.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    sys.exit("refusing to run offscreen — the whole point is the real screen")
if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    sys.exit("set CHROMIQ_SETTINGS_FILE first (CLAUDE.md): a driver that does "
             "not is writing into the preferences the owner works in")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, QRect                          # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase, QPainter, QPen   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,  # noqa: E402
                             QSplitter)

OUT_DEFAULT = Path("/Users/Basti/Desktop/beta 9/create-chart-frame-gaps")


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build_app(lang: str):
    """Everything main() does before it builds a window, in the same order."""
    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import CompositeAppFilter

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    # THE FILTER. Without it every width below is one no user ever sees.
    app._dg_filter = CompositeAppFilter(app)          # keep a reference
    app.installEventFilter(app._dg_filter)

    from core.settings import AppSettings
    settings = AppSettings()
    settings.migrate()
    from core.i18n import set_language
    set_language(lang)
    apply_appearance(app, None, settings.get("appearance", "auto"))
    return app, settings


def measure(win, tab) -> dict:
    """The four numbers Basti's sentence is about, in logical pixels."""
    splitter = tab.findChild(QSplitter)
    handle = splitter.handle(1)
    handle_right = handle.mapTo(win, QPoint(handle.width(), 0)).x()

    mp = tab._margin_panel
    li = tab._layout_info_panel
    prev = tab._preview

    def left_of(w):
        return w.mapTo(win, QPoint(0, 0)).x()

    def right_of(w):
        return w.mapTo(win, QPoint(w.width(), 0)).x()

    return {
        "window_w": win.width(),
        "handle_right": handle_right,
        "margin_panel_left": left_of(mp),
        "margin_panel_right": right_of(mp),
        "layout_info_left": left_of(li),
        "layout_info_right": right_of(li),
        "preview_left": left_of(prev),
        "preview_right": right_of(prev),
        "gap_left": left_of(mp) - handle_right,
        "gap_right": win.width() - right_of(li),
        "channel": left_of(li) - right_of(mp),
        "preview_gap_left": left_of(prev) - handle_right,
        "preview_gap_right": win.width() - right_of(prev),
        "mp_visible": mp.isVisible(),
        "li_visible": li.isVisible(),
    }


def report(m: dict, label: str) -> None:
    print(f"  [{label}]  window {m['window_w']} px, handle right edge at "
          f"x={m['handle_right']}")
    print(f"    LEFT   'Measured from Preview'  left edge x={m['margin_panel_left']}"
          f"   -> gap to separator = {m['gap_left']} px")
    print(f"    RIGHT  'Chart layout information' right edge x={m['layout_info_right']}"
          f"  -> gap to window edge = {m['gap_right']} px")
    print(f"    CHANNEL between the two frames = {m['channel']} px")
    print(f"    PREVIEW above them: left gap {m['preview_gap_left']} px, "
          f"right gap {m['preview_gap_right']} px")


def annotated_crop(win, tab, path: Path, m: dict) -> None:
    """A crop that shows both frame edges AND the separator, with the two gaps
    ringed, because a 0 px gap and a 6 px gap look the same in a thumbnail."""
    pm = win.grab()
    dpr = pm.devicePixelRatio() or 1.0
    mp = tab._margin_panel
    top = mp.mapTo(win, QPoint(0, 0)).y() - 26
    bottom = mp.mapTo(win, QPoint(0, mp.height())).y() + 22
    x0 = m["handle_right"] - 46
    rect = QRect(int(x0 * dpr), int(top * dpr),
                 int((m["window_w"] - x0) * dpr), int((bottom - top) * dpr))
    crop = pm.copy(rect)
    crop.setDevicePixelRatio(dpr)

    p = QPainter(crop)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#ff2d55"), 2.0))
    h = (bottom - top)
    # the separator
    p.drawLine(int(m["handle_right"] - x0), 0, int(m["handle_right"] - x0), h)
    # the two edges under complaint
    p.setPen(QPen(QColor("#00d1ff"), 2.0))
    p.drawLine(int(m["margin_panel_left"] - x0), 0,
               int(m["margin_panel_left"] - x0), h)
    p.drawLine(int(m["layout_info_right"] - x0), 0,
               int(m["layout_info_right"] - x0), h)
    p.end()
    crop.save(str(path))
    print(f"    saved {path.name}  ({crop.width()}x{crop.height()} px, dpr={dpr})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="before")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--lang", default="en")
    ap.add_argument("--width", type=int, default=1700)
    ap.add_argument("--height", type=int, default=1050)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    app, settings = build_app(args.lang)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for meth in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, meth, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    from ui.theme import apply_appearance
    apply_appearance(app, win, settings.get("appearance", "auto"))
    win.resize(args.width, args.height)
    win.show()
    pump(app, 2200)

    tab = win._tab_chart
    idx = win._tabs.indexOf(tab)
    win._tabs.setCurrentIndex(idx)
    pump(app, 1200)

    print(f"\n=== {args.tag}  lang={args.lang}  {args.width}x{args.height} ===")
    m = measure(win, tab)
    report(m, f"{args.tag}/{args.lang}/{args.width}")
    annotated_crop(win, tab, out / f"{args.tag}_{args.lang}_{args.width}_inforow.png", m)
    win.grab().save(str(out / f"{args.tag}_{args.lang}_{args.width}_window.png"))
    print(f"    saved {args.tag}_{args.lang}_{args.width}_window.png")

    # Can the separator move at all? The left pane is setFixedWidth(580), so the
    # answer is expected to be no — but "expected" is not "checked".
    splitter = tab.findChild(QSplitter)
    before_sizes = splitter.sizes()
    drag_results = []
    for name, sizes in (("dragged-left", [1, 10_000]),
                        ("dragged-right", [10_000, 1])):
        splitter.setSizes(sizes)
        pump(app, 500)
        d = measure(win, tab)
        drag_results.append((name, splitter.sizes(), d))
        print(f"  [{name}] splitter sizes {splitter.sizes()}  "
              f"gap_left={d['gap_left']}  gap_right={d['gap_right']}")
    splitter.setSizes(before_sizes)
    pump(app, 300)

    import json
    (out / f"{args.tag}_{args.lang}_{args.width}.json").write_text(
        json.dumps({"measured": m,
                    "drag": [{"name": n, "sizes": s, "m": d}
                             for n, s, d in drag_results]}, indent=2),
        encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
