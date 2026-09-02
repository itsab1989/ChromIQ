#!/usr/bin/env python3
"""Measure the chrome's non-neutral pixels, screen by screen, before and after.

    python scripts/drive_neutral_chrome.py <outdir> [--onscreen]

Two jobs, the same two the Neutral work has had from the start:

* **Neutral, counted.** `scripts/find_non_neutral_pixels.scan_widget` is run
  against the real main window on every tab plus the masthead, the tab bar and
  the Measurement Report dialog. A pixel count of zero in the chrome is the
  finish line, and this is what measures it. Nothing is estimated: the numbers
  are the instrument's, unchanged.
* **Light and Dark are untouched.** The same grabs in the two shipped
  appearances, hashed. Run once on the pre-change source and once after; every
  hash must be identical.

Sandboxed before any ChromIQ import — CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR
and a custom_output_path written into the .ini, so a missing output path can
never fall back to the owner's real ~/ChromIQ. Refuses to run if the store it
actually opened is not the sandbox, and ends by checking ~/ChromIQ gained
nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = "--onscreen" in sys.argv
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/nchrome.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/nchrome-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path("/tmp/nchrome-work")
OUT = Path([a for a in sys.argv[1:] if not a.startswith("--")][0])

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import Qt                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase, QPixmap               # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from scripts.find_non_neutral_pixels import scan_widget      # noqa: E402

#: The three things that legitimately show the user's own colours. Excluded by
#: the design, not by oversight — and named in the call, as the instrument asks.
SKIP = ("TiffPreview", "GamutPanel", "PatchCubePanel", "GamutViewWidget")


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def sha(pm) -> str:
    img = pm.toImage()
    b = img.bits()
    b.setsize(img.sizeInBytes())
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


def tree_hash(root: Path) -> "dict[str, str]":
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        out[rel + ("/" if p.is_dir() else "")] = (
            "dir" if p.is_dir() else hashlib.sha1(p.read_bytes()).hexdigest())
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    real_root = Path.home() / "ChromIQ"
    before_real = tree_hash(real_root)

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

    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.splash import make_splash_pixmap
    from ui.theme import apply_appearance

    win = MainWindow(settings)
    win.resize(1280, 900)
    win.show()
    if ONSCREEN:
        win.raise_(); win.activateWindow()
    pump(app, 1500)

    report: dict = {}

    # ---------------- Neutral: count the offenders ----------------------
    apply_appearance(app, win, "neutral")
    pump(app, 900)
    tabs = win._tabs
    neutral: dict = {}
    shots = OUT / "neutral"
    shots.mkdir(parents=True, exist_ok=True)

    def scan(name: str, widget) -> None:
        t0 = time.time()
        hits = scan_widget(widget, skip=SKIP)
        total = sum(h.pixels for h in hits)
        widget.grab().save(str(shots / f"{name}.png"))
        neutral[name] = {
            "offenders": len(hits),
            "non_neutral_pixels": total,
            "hits": [{"widget": h.widget, "object_name": h.object_name,
                      "pixels": h.pixels, "share_pct": round(h.share, 1),
                      "colours": [[c, n] for c, n in h.colours[:4]],
                      "path": h.path} for h in hits[:40]],
        }
        print(f"  {name}: {len(hits)} offenders, {total} px "
              f"({time.time() - t0:.0f}s)")

    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        pump(app, 700)
        label = tabs.tabText(i).strip().lower().replace(" ", "-").replace("&", "and")
        scan(f"10-tab{i + 1}-{label}", win)
    tabs.setCurrentIndex(0)
    pump(app, 500)
    scan("20-masthead", win._masthead)
    scan("21-tab-bar", tabs.tabBar())

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    rep = MeasurementReportDialog(settings, win)
    rep.setWindowModality(Qt.WindowModality.NonModal)
    rep.resize(980, 700)
    rep.show()
    pump(app, 900)
    scan("41-measurement-report", rep)
    rep.close(); rep.setParent(None); rep.deleteLater()
    pump(app, 300)

    from ui.dialogs.tools_dialogs import AverageMeasurementsDialog
    tdlg = AverageMeasurementsDialog(win._runner, settings, win)
    tdlg.setWindowModality(Qt.WindowModality.NonModal)
    tdlg.resize(900, 640)
    tdlg.show()
    pump(app, 700)
    scan("42-tool-dialog", tdlg)
    tdlg.close(); tdlg.setParent(None); tdlg.deleteLater()
    pump(app, 300)

    # The splash is a pixmap, not a widget tree — count it directly.
    from scripts.find_non_neutral_pixels import _worst
    pm = make_splash_pixmap("neutral", "v9.9.9")
    n, cols = _worst(pm.toImage(), 6)
    pm.save(str(shots / "50-splash.png"))
    neutral["50-splash"] = {"offenders": 1 if n else 0,
                            "non_neutral_pixels": n,
                            "hits": [{"widget": "splash pixmap",
                                      "object_name": "", "pixels": n,
                                      "share_pct": round(100 * n / (pm.width() * pm.height()), 1),
                                      "colours": [[c, k] for c, k in cols[:4]],
                                      "path": "make_splash_pixmap"}]}
    print(f"  50-splash: {n} px")

    report["neutral"] = neutral
    report["neutral_total_px"] = sum(v["non_neutral_pixels"]
                                     for v in neutral.values())

    # ---------------- Light and Dark: hashes only ------------------------
    for mode in ("light", "dark"):
        apply_appearance(app, win, mode)
        pump(app, 900)
        d = OUT / mode
        d.mkdir(parents=True, exist_ok=True)
        rec: dict = {}
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            pump(app, 700)
            label = tabs.tabText(i).strip().lower().replace(" ", "-").replace("&", "and")
            g = win.grab(); g.save(str(d / f"10-tab{i + 1}-{label}.png"))
            rec[f"10-tab{i + 1}-{label}"] = sha(g)
        tabs.setCurrentIndex(0)
        pump(app, 500)
        for name, w in (("20-masthead", win._masthead),
                        ("21-tab-bar", tabs.tabBar())):
            g = w.grab(); g.save(str(d / f"{name}.png"))
            rec[name] = sha(g)
        r2 = MeasurementReportDialog(settings, win)
        r2.setWindowModality(Qt.WindowModality.NonModal)
        r2.resize(980, 700)
        r2.show()
        pump(app, 900)
        g = r2.grab(); g.save(str(d / "41-measurement-report.png"))
        rec["41-measurement-report"] = sha(g)
        r2.close(); r2.setParent(None); r2.deleteLater()
        pump(app, 300)
        sp = make_splash_pixmap(mode, "v9.9.9")
        sp.save(str(d / "50-splash.png"))
        rec["50-splash"] = sha(sp)
        from ui.dialogs.tools_dialogs import AverageMeasurementsDialog
        try:
            td = AverageMeasurementsDialog(win._runner, settings, win)
            td.setWindowModality(Qt.WindowModality.NonModal)
            td.resize(900, 640)
            td.show()
            pump(app, 700)
            g = td.grab(); g.save(str(d / "42-tool-dialog.png"))
            rec["42-tool-dialog"] = sha(g)
            td.close(); td.setParent(None); td.deleteLater()
            pump(app, 300)
        except Exception as exc:            # noqa: BLE001
            rec["42-tool-dialog"] = f"unavailable: {exc}"
        report[mode] = rec
        print(f"{mode}: {len(rec)} grabs hashed")

    (OUT / "chrome.json").write_text(json.dumps(report, indent=2, sort_keys=True),
                                     encoding="utf-8")
    print(f"\nwrote {OUT / 'chrome.json'}")
    print(f"NEUTRAL NON-NEUTRAL PIXELS, TOTAL: {report['neutral_total_px']}")

    win.close()
    pump(app, 500)

    after_real = tree_hash(real_root)
    gained = sorted(set(after_real) - set(before_real))
    print(f"~/ChromIQ before {len(before_real)} → after {len(after_real)}, "
          f"gained {len(gained)}")
    if gained:
        print("LEAKED:", gained[:20])
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
