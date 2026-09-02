#!/usr/bin/env python3
"""The Preferences ⓘ icon, at real size, with its contrast measured.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/prove_tooltip_icon.py <outdir>

The owner: *"in preferences neutral mode the tooltip icons are too light. the
color they currently have would be good for a disabled state or something."*

Crops one Preferences row **1:1** — the label, its checkbox and its ⓘ — so the
icon can be judged by eye at the size it is actually drawn, and reports the
darkest ink the icon paints together with its contrast against the window it
sits on. A pixel count does not settle this one; the picture does.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir("/tmp")

if not os.environ.get("CHROMIQ_DRIVE_ONSCREEN"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/nctrl.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/nctrl-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/nctrl-tip")
MODE = os.environ.get("CHROMIQ_DRIVE_MODE", "neutral")
GROUND = {"neutral": "#e2e2e2", "light": "#eeece8", "dark": "#141414"}[MODE]

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, Qt                              # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox) # noqa: E402


def pump(app, ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _lum(h):
    h = h.lstrip("#")
    p = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in p]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return round((la + 0.05) / (lb + 0.05), 2)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))

    from core.settings import AppSettings
    settings = AppSettings()
    if Path(settings._qs.fileName()) != SETTINGS_INI:
        raise SystemExit("REFUSING TO RUN: settings escaped the sandbox")
    settings.set("appearance", MODE)
    settings.set("custom_output_path", "/tmp/nctrl-work")

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                 # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    win = MainWindow(settings)
    win.resize(1340, 940)
    win.show()
    pump(app, 1500)
    apply_appearance(app, win, MODE)
    pump(app, 900)

    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.tooltip_button import TooltipButton
    dlg = SettingsDialog(settings, win)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.resize(980, 760)
    dlg.show()
    pump(app, 1000)

    tips = [t for t in dlg.findChildren(TooltipButton) if t.isVisible()]
    rec = {"mode": MODE, "ground": GROUND, "tooltip_buttons_found": len(tips)}
    if not tips:
        raise SystemExit("no visible tooltip buttons")

    # CROP FROM THE DIALOG'S OWN RENDER, IN PHYSICAL PIXELS.
    #
    # Two ways of getting here are wrong and both look plausible:
    # `tip.grab()` on a TooltipButton comes back as a near-solid dark square —
    # the button paints no background of its own, so grabbing it alone is not
    # what the screen shows; and cropping the dialog with the button's LOGICAL
    # coordinates lands half a row away, because the dialog grab is 2x on this
    # display. The first version of this probe did the second and reported the
    # same three colours for both trees — a probe that finds its answer
    # somewhere else. Map the position, then multiply by the pixmap's own
    # device pixel ratio.
    big = dlg.grab()
    dpr = big.devicePixelRatio()
    tip = tips[1] if len(tips) > 1 else tips[0]
    at = tip.mapTo(dlg, QPoint(0, 0))

    def _crop(x, y, w, h):
        out = big.copy(int(x * dpr), int(y * dpr), int(w * dpr), int(h * dpr))
        out.setDevicePixelRatio(dpr)
        return out

    icon = _crop(at.x(), at.y(), tip.width(), tip.height())
    icon.save(str(OUT / "tooltip-icon.png"))

    # The whole ROW — label, control and ⓘ — as the owner sees it.
    x0, y0 = 40, max(0, at.y() - 7)
    row = _crop(x0, y0, at.x() + tip.width() + 14 - x0, tip.height() + 14)
    row.save(str(OUT / "tooltip-row.png"))
    rec_extra = {"tip_at": [at.x(), at.y()], "dpr": dpr}

    img = icon.toImage()
    from collections import Counter
    c: Counter = Counter()
    for y in range(img.height()):
        for x in range(img.width()):
            col = img.pixelColor(x, y)
            if col.alpha() >= 8:
                c[col.name()] += 1
    darkest = min(c, key=lambda h: QColor(h).lightness())
    rec["icon_colours"] = [[h, n] for h, n in c.most_common(6)]
    rec["darkest_ink"] = darkest
    rec["darkest_ink_contrast_vs_ground"] = contrast(darkest, GROUND)
    rec["disabled_token_contrast_vs_ground"] = contrast("#c4c4c4", GROUND)
    rec["row_size"] = [row.width(), row.height()]
    rec.update(rec_extra)
    rec["icon_size"] = [icon.width(), icon.height()]

    # What a DISABLED ⓘ looks like, from the same icon — Qt's own fade.
    tip.setEnabled(False)
    pump(app, 400)
    big = dlg.grab()
    dis = _crop(at.x(), at.y(), tip.width(), tip.height())
    dis.save(str(OUT / "tooltip-icon-disabled.png"))
    dimg = dis.toImage()
    dc: Counter = Counter()
    for y in range(dimg.height()):
        for x in range(dimg.width()):
            col = dimg.pixelColor(x, y)
            if col.alpha() >= 8:
                dc[col.name()] += 1
    ddark = min(dc, key=lambda h: QColor(h).lightness())
    rec["disabled_darkest_ink"] = ddark
    rec["disabled_darkest_contrast_vs_ground"] = contrast(ddark, GROUND)
    tip.setEnabled(True)

    (OUT / "tooltip.json").write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(rec, indent=2, sort_keys=True))
    dlg.close(); win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
