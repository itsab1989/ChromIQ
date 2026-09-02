#!/usr/bin/env python3
"""Drive the REAL ChromIQ window in Light, Dark and Neutral, and record it.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_neutral_appearance.py <outdir>

Two jobs in one pass:

* **Neutral, on screen.** All five tabs, the masthead, the tab bar,
  Preferences, a tool window and both splash styles — grabbed, and then
  MEASURED from the pixels: every distinct colour in each grab, its share, its
  contrast against this theme's panel, and whether it carries a hue. A value
  that is right in the token table and wrong on screen is exactly what this
  step exists to catch.
* **Light and Dark are untouched.** The same grabs in the two shipped
  appearances, hashed. Run once on the pre-change source and once after; every
  hash must be identical. Anything that moves in Light or Dark is a regression,
  not a side effect.

Sandboxed: CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR and a custom_output_path
written into the .ini BEFORE anything builds an AppSettings, so a missing output
path can never fall back to the owner's real ~/ChromIQ. The run refuses to start
if the store it actually opened is not the sandbox, and ends by checking
~/ChromIQ gained nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# SANDBOX ITSELF, BEFORE ANY ChromIQ IMPORT — do not rely on the shell.
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/neutral.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/neutral-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/neutral-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1
           else "/Users/Basti/Desktop/beta7/neutral-proof/onscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import Qt                                        # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase, QPainter, QPixmap   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox)   # noqa: E402

# BG_PANEL and BG_SURFACE were #ebebeb and #f5f5f5 until the owner collapsed
# the three grounds onto one on 2026-09-02; the names stay because a pixel here
# is still reported by the surface it belongs to.
TOKENS = {
    "BG_WINDOW": "#e2e2e2", "BG_PANEL": "#e2e2e2", "BG_SURFACE": "#e2e2e2",
    "BG_INPUT": "#ffffff", "BG_VIEWER": "#d4d4d4", "BORDER": "#b6b6b6",
    "BORDER_HI": "#2f2f2f", "TEXT_MAIN": "#101010", "TEXT_DIM": "#232323",
    "TEXT_FAINT": "#3f3f3f", "ACTION": "#101010", "ON_ACTION": "#e8e8e8",
    "DISABLED": "#c4c4c4",
}
BY_HEX = {}
for _k, _v in TOKENS.items():
    BY_HEX.setdefault(_v, []).append(_k)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _luminance(hexc: str) -> float:
    h = hexc.lstrip("#")
    parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    if la < lb:
        la, lb = lb, la
    return round((la + 0.05) / (lb + 0.05), 2)


def sha(pixmap) -> str:
    img = pixmap.toImage()
    b = img.bits()
    b.setsize(img.sizeInBytes())
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


def measure(pixmap) -> dict:
    """What is ACTUALLY painted: colour census, hues, and contrast."""
    img = pixmap.toImage()
    counts: Counter = Counter()
    step = max(1, min(img.width(), img.height()) // 900)   # cap the work
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            counts[QColor(img.pixel(x, y)).rgb() & 0xFFFFFF] += 1
    total = sum(counts.values())
    hued = Counter()
    for rgb, n in counts.items():
        r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
        if max(r, g, b) - min(r, g, b) > 8:
            hued[rgb] += n

    def name(rgb):
        return "#%06x" % rgb

    top = [{"hex": name(rgb), "share": round(100 * n / total, 2),
            "token": BY_HEX.get(name(rgb), []),
            "contrast_vs_panel": contrast(name(rgb), TOKENS["BG_PANEL"])}
           for rgb, n in counts.most_common(12)]
    return {
        "distinct_colours": len(counts),
        "sampled_pixels": total,
        "hued_share_pct": round(100 * sum(hued.values()) / total, 2),
        "hued_top": [{"hex": name(rgb), "share": round(100 * n / total, 3)}
                     for rgb, n in hued.most_common(8)],
        "top_colours": top,
    }


def tree_hash(root: Path) -> "dict[str, str]":
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        out[rel + ("/" if p.is_dir() else "")] = (
            "dir" if p.is_dir() else hashlib.sha1(p.read_bytes()).hexdigest())
    return out


class Shots:
    """One directory of PNGs per appearance, with a hash and a measurement."""

    def __init__(self, outdir: Path, mode: str, measure_it: bool):
        self.dir = outdir / mode
        self.dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.measure_it = measure_it
        self.record: dict[str, object] = {}
        self.files: list[tuple[str, Path]] = []

    def take(self, name: str, widget_or_pixmap) -> None:
        pm = (widget_or_pixmap if isinstance(widget_or_pixmap, QPixmap)
              else widget_or_pixmap.grab())
        if pm.isNull() or pm.width() <= 0:
            self.record[name] = "ungrabbable"
            return
        path = self.dir / f"{name}.png"
        pm.save(str(path))
        self.files.append((name, path))
        self.record[f"{name}/sha"] = sha(pm)
        self.record[f"{name}/size"] = [pm.width(), pm.height()]
        if self.measure_it:
            self.record[f"{name}/measured"] = measure(pm)


def contact_sheet(shot_dirs: "dict[str, list[tuple[str, Path]]]",
                  out: Path) -> None:
    """Every grab, every appearance, one column per appearance."""
    modes = list(shot_dirs)
    names = [n for n, _ in shot_dirs[modes[0]]]
    cell_w, cell_h, pad, head = 380, 250, 14, 34
    W = pad + len(modes) * (cell_w + pad) + 180
    H = head + len(names) * (cell_h + pad) + pad
    sheet = QPixmap(W, H)
    sheet.fill(QColor("#f2f2f2"))
    p = QPainter(sheet)
    f = p.font(); f.setPixelSize(15); f.setBold(True); p.setFont(f)
    p.setPen(QColor("#101010"))
    for i, m in enumerate(modes):
        p.drawText(180 + pad + i * (cell_w + pad), 22, m.upper())
    f.setBold(False); f.setPixelSize(12); p.setFont(f)
    for r, name in enumerate(names):
        y = head + r * (cell_h + pad)
        p.drawText(6, y + cell_h // 2, 170, 40,
                   int(Qt.AlignmentFlag.AlignLeft), name)
        for c, m in enumerate(modes):
            path = dict(shot_dirs[m]).get(name)
            x = 180 + pad + c * (cell_w + pad)
            p.fillRect(x, y, cell_w, cell_h, QColor("#dcdcdc"))
            if path and path.exists():
                pm = QPixmap(str(path)).scaled(
                    cell_w, cell_h, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(x + (cell_w - pm.width()) // 2,
                             y + (cell_h - pm.height()) // 2, pm)
            p.setPen(QColor("#b6b6b6"))
            p.drawRect(x, y, cell_w, cell_h)
            p.setPen(QColor("#101010"))
    p.end()
    sheet.save(str(out))
    print(f"contact sheet: {out}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    real_root = Path.home() / "ChromIQ"
    before_real = tree_hash(real_root)
    print(f"~/ChromIQ before: {len(before_real)} entries")

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
    opened = Path(settings._qs.fileName())
    if opened != SETTINGS_INI:
        raise SystemExit(f"REFUSING TO RUN: settings escaped the sandbox: {opened}")
    print(f"settings store: {opened}")
    WORK.mkdir(parents=True, exist_ok=True)
    if str(settings.get("custom_output_path", "")) != str(WORK):
        settings.set("custom_output_path", str(WORK))
    print(f"custom_output_path: {settings.get('custom_output_path')}")

    # Never leave a modal open.
    QDialog.exec = lambda self: 1                        # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                    # type: ignore[assignment]

    import ui.theme as theme
    from ui.main_window import MainWindow
    from ui.splash import make_splash_pixmap
    from ui.theme import apply_appearance

    modes = [m for m in ("light", "dark", "neutral")
             if m in theme.VALID_APPEARANCES]
    print(f"appearances this build offers: {modes}")

    win = MainWindow(settings)
    win.resize(1280, 900)
    win.show()
    if ONSCREEN:
        win.raise_()
        win.activateWindow()
    pump(app, 1500)

    report: dict[str, dict] = {}
    sheets: dict[str, list] = {}

    for mode in modes:
        print(f"\n=== {mode.upper()} ===")
        apply_appearance(app, win, mode)
        pump(app, 900)
        s = Shots(OUT, mode, measure_it=(mode == "neutral"))

        # ---- the five tabs ------------------------------------------------
        tabs = win._tabs
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            pump(app, 700)
            label = tabs.tabText(i).strip().lower().replace(" ", "-").replace("&", "and")
            s.take(f"10-tab{i + 1}-{label}", win)
        tabs.setCurrentIndex(0)
        pump(app, 500)

        # ---- the chrome, on its own so a fault is not lost in the window ---
        s.take("20-masthead", win._masthead)
        s.take("21-tab-bar", tabs.tabBar())

        # ---- Preferences --------------------------------------------------
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(settings, win)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.resize(940, 720)
        dlg.show()
        pump(app, 900)
        s.take("30-preferences", dlg)
        combo = getattr(dlg, "_appearance_combo", None)
        if combo is not None:
            s.record["30-preferences/appearance_items"] = [
                (combo.itemText(i), combo.itemData(i))
                for i in range(combo.count())]
            s.take("31-appearance-combo", combo)
        dlg.close()
        dlg.setParent(None)
        dlg.deleteLater()
        pump(app, 300)

        # ---- a tool window + the tools popup ------------------------------
        from ui.tools_popup import ToolsPopup
        tp = ToolsPopup(win)
        tp.set_appearance(mode)
        tp.resize(tp.sizeHint())
        tp.show()
        pump(app, 400)
        s.take("40-tools-popup", tp)
        tp.hide(); tp.setParent(None); tp.deleteLater()

        from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
        rep = MeasurementReportDialog(settings, win)
        rep.setWindowModality(Qt.WindowModality.NonModal)
        rep.resize(980, 700)
        rep.show()
        pump(app, 900)
        s.take("41-tool-measurement-report", rep)
        rep.close(); rep.setParent(None); rep.deleteLater()
        pump(app, 300)

        # ---- both splash styles -------------------------------------------
        s.take("50-splash-pixmap", make_splash_pixmap(mode, "v9.9.9"))
        from ui.splash import make_splash
        for plain in (True, False):
            sp = make_splash(mode, "v9.9.9", plain=plain)
            sp.show()
            if ONSCREEN:
                sp.raise_()
            pump(app, 500)
            s.take(f"51-splash-{'plain' if plain else 'classic'}", sp)
            sp.finish(win)
            sp.deleteLater()
            pump(app, 200)

        report[mode] = s.record
        sheets[mode] = s.files
        print(f"  {len(s.files)} grabs")

    (OUT / "onscreen.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT / 'onscreen.json'}")

    contact_sheet(sheets, OUT.parent / "CONTACT-SHEET.png")

    win.close()
    pump(app, 500)

    after_real = tree_hash(real_root)
    gained = sorted(set(after_real) - set(before_real))
    print(f"~/ChromIQ after: {len(after_real)} entries; gained {len(gained)}")
    if gained:
        print("LEAKED:", gained[:20])
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
