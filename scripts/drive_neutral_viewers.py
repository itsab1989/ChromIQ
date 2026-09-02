#!/usr/bin/env python3
"""Photograph every ChromIQ VIEWER — empty and with the user's own work in it.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_neutral_viewers.py <outdir> <mode>

ONE APPEARANCE PER PROCESS, and the appearance is written into the settings
*before* ``MainWindow`` is built. Switching a live window is what the app does
for a user, but it leaves two things behind that make a census lie: a dialog
that read ``resolve_mode(settings)`` at construction keeps the appearance it was
born with, and ``GroupBoxSurfaceFilter`` never takes back the light theme's
raised surface. A fresh process per appearance measures the appearance and
nothing else.

TWO PHASES, because a well can be the right colour and hold the wrong picture:

* **empty** — no project open. What is painted is the frame and nothing else,
  so a hue counted here is a hue in the chrome. This is the finish-line number.
* **full** — the Argyll-built ``Demo-Full-RGB`` demo project open, so the TIFF
  preview holds a real chart, the gamut well a real 3D gamut, the cube a real
  patch set and the marquee a real printed page. Every hue here has to be
  looked at and judged content or chrome; the pictures are the point.

Sandboxed: CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR and a custom_output_path
written into the .ini BEFORE anything builds an AppSettings.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/nview.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/nview-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/nview-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/nview-shots")
MODE = sys.argv[2] if len(sys.argv) > 2 else "neutral"

WORK.mkdir(parents=True, exist_ok=True)
if not SETTINGS_INI.exists() or "custom_output_path" not in SETTINGS_INI.read_text(encoding="utf-8"):
    SETTINGS_INI.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_INI.write_text(f"[General]\ncustom_output_path={WORK}\n", encoding="utf-8")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import Qt, QTimer                                # noqa: E402
from PyQt6.QtGui import QFontDatabase, QImage, QPixmap             # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,   # noqa: E402
                             QWidget)

SUBJECT = "Demo-Full-RGB"


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def pump_until(app, pred, ms: int = 60000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)
        if pred():
            return True
    return False


def sha(pixmap) -> str:
    img = pixmap.toImage()
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


def find_subject() -> "Path | None":
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob(f"*/{SUBJECT}")):
        if (cand / "project.json").is_file():
            return cand
    return None


class Shots:
    def __init__(self, outdir: Path, mode: str):
        self.dir = outdir / mode
        self.dir.mkdir(parents=True, exist_ok=True)
        self.record: dict[str, object] = {}

    def take(self, name: str, w) -> str:
        # DROP THE KEYBOARD FOCUS FIRST. A focused field wears the accent as a
        # 1 px ring, and which widget holds focus in an on-screen dialog is
        # decided by the window manager, not by the code under test — two
        # otherwise identical runs differ by 703 pixels of border because of
        # it. Nothing here is measuring a focus ring, so the grabs are taken
        # with none.
        if not isinstance(w, QPixmap):
            fw = w.focusWidget()
            if fw is not None:
                fw.clearFocus()
            QApplication.processEvents()
        pm = w if isinstance(w, QPixmap) else w.grab()
        if pm.isNull() or pm.width() <= 0:
            self.record[name] = "ungrabbable"
            print(f"    {name}: UNGRABBABLE", flush=True)
            return ""
        pm.save(str(self.dir / f"{name}.png"))
        h = sha(pm)
        self.record[f"{name}/sha"] = h
        self.record[f"{name}/size"] = [pm.width(), pm.height()]
        # The ground: the top-left pixel of the widget, which no content
        # reaches in any of these views.
        img = pm.toImage()
        self.record[f"{name}/corner"] = img.pixelColor(2, 2).name()
        print(f"    {name}: {pm.width()}x{pm.height()} {h} corner={img.pixelColor(2, 2).name()}",
              flush=True)
        return h


def census(scan_widget, where: str, root, out: list) -> None:
    if root is None:
        return
    for hit in scan_widget(root, skip=()):
        out.append({"where": where, "widget": hit.widget,
                    "objectName": hit.object_name, "pixels": hit.pixels,
                    "share": round(hit.share, 2),
                    "colours": hit.colours[:5], "path": hit.path})


def main() -> int:   # noqa: PLR0915, PLR0912
    OUT.mkdir(parents=True, exist_ok=True)
    real_root = Path.home() / "ChromIQ"
    before_real = tree_hash(real_root)
    print(f"~/ChromIQ before: {len(before_real)} entries")

    src = find_subject()
    if src is None:
        print("No cached Demo-Full-RGB; run the test suite once to build it.")
        return 2
    dest = WORK / SUBJECT
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    from core.settings import AppSettings
    settings = AppSettings()
    opened = Path(settings._qs.fileName())
    if opened != SETTINGS_INI:
        raise SystemExit(f"REFUSING TO RUN: settings escaped the sandbox: {opened}")
    if str(settings.get("custom_output_path", "")) != str(WORK):
        settings.set("custom_output_path", str(WORK))
    settings.set("appearance", MODE)
    print(f"settings: {opened}  out={settings.get('custom_output_path')}  "
          f"appearance={settings.get('appearance')}")

    QDialog.exec = lambda self: 1                        # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                    # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    from scripts.find_non_neutral_pixels import scan_widget

    win = MainWindow(settings)
    apply_appearance(app, win, MODE)
    win.resize(1700, 1050)
    win.show()
    if ONSCREEN:
        win.raise_()
        win.activateWindow()
    pump(app, 1500)

    dismissed: list[str] = []

    def _dismiss_modal() -> None:
        m = app.activeModalWidget()
        if m is not None and m.isVisible():
            dismissed.append(m.windowTitle())
            m.reject()

    wd = QTimer()
    wd.timeout.connect(_dismiss_modal)
    wd.start(150)

    s = Shots(OUT, MODE)
    scans: dict[str, list] = {"empty": [], "full": []}
    tabs = win._tabs
    from ui.scan_grid_marquee import ScanGridMarquee
    from ui.dialogs.patch_cube_dialog import PatchCubeDialog
    from ui.dialogs.softproof_dialog import SoftproofDialog
    from workflow.ti2_relayout import load_rgb_program

    PREVIEWS = ((0, "_tab_chart", "chart"), (1, "_tab_print", "print"),
                (2, "_tab_measure", "measure"))

    # ---------------------------------------------------------------- empty
    print("\n--- EMPTY (no project) ---")
    for idx, attr, label in PREVIEWS:
        tabs.setCurrentIndex(idx)
        pump(app, 700)
        pv = getattr(getattr(win, attr, None), "_preview", None)
        if pv is not None:
            s.take(f"E10-preview-{label}", pv)
            census(scan_widget, f"empty/preview-{label}", pv, scans["empty"])

    tabs.setCurrentIndex(4)
    pump(app, 900)
    gp = getattr(getattr(win, "_tab_check", None), "_gamut_panel", None)
    if gp is not None:
        s.take("E20-gamut-panel", gp)
        well = gp.findChild(QWidget, "gamutViewerFrame")
        if well is not None:
            s.take("E21-gamut-well", well)
        census(scan_widget, "empty/gamut-panel", gp, scans["empty"])

    marq = ScanGridMarquee(win)
    marq.setWindowFlags(Qt.WindowType.Tool)
    marq.setPalette(app.palette())
    marq.resize(900, 640)
    marq.show()
    if ONSCREEN:
        marq.raise_()
    pump(app, 600)
    s.take("E40-scan-marquee", marq)
    census(scan_widget, "empty/scan-marquee", marq, scans["empty"])

    cube_e = PatchCubeDialog([], mode=MODE, target_name="(empty)", parent=win)
    cube_e.setWindowModality(Qt.WindowModality.NonModal)
    cube_e.resize(900, 760)
    cube_e.show()
    if ONSCREEN:
        cube_e.raise_()
    pump(app, 2500)
    s.take("E30-patch-cube", cube_e)
    census(scan_widget, "empty/patch-cube", cube_e, scans["empty"])

    sp = SoftproofDialog(win._runner, settings, win)
    sp.setWindowModality(Qt.WindowModality.NonModal)
    sp.resize(1100, 800)
    sp.show()
    if ONSCREEN:
        sp.raise_()
    pump(app, 900)
    s.take("E50-softproof", sp)
    census(scan_widget, "empty/softproof", sp, scans["empty"])

    # ----------------------------------------------------------------- full
    print("\n--- FULL (Demo-Full-RGB open) ---")
    win._file_mgr.set_target_name(SUBJECT)
    win._target_bar.refresh()
    pump(app, 1500)
    proj = win._file_mgr.project()
    print("project:", getattr(proj, "root", None),
          "runs", [r.id for r in proj.all_runs()] if proj else [])

    tifs = sorted((dest / "runs" / "run1").glob("*_0*.tif"))
    print(f"    chart pages: {[t.name for t in tifs]}")
    for idx, attr, label in PREVIEWS:
        tabs.setCurrentIndex(idx)
        pump(app, 1200)
        pv = getattr(getattr(win, attr, None), "_preview", None)
        if pv is not None:
            if tifs:
                pv.load_tiff(tifs)
                pump(app, 1200)
            s.take(f"F10-preview-{label}", pv)
            s.record[f"F10-preview-{label}/pages"] = len(getattr(pv, "_paths", []) or [])
            census(scan_widget, f"full/preview-{label}", pv, scans["full"])
        s.take(f"F11-tab-{label}", win)

    # the 3D gamut, really built from the demo project's own profile
    tabs.setCurrentIndex(4)
    pump(app, 1200)
    if gp is not None:
        icc = next(iter(sorted((dest / "runs" / "run1").glob("*.icc"))), None)
        if icc is not None:
            gp.set_icc_path(icc)
            pump(app, 400)
            gp._on_run()
            ok = pump_until(app, lambda: bool(getattr(gp, "_primary_html", None)),
                            180000)
            print(f"    gamut analysis finished: {ok}")
            pump(app, 4000)
        s.take("F20-gamut-panel", gp)
        well = gp.findChild(QWidget, "gamutViewerFrame")
        if well is not None:
            s.take("F21-gamut-well", well)
        census(scan_widget, "full/gamut-panel", gp, scans["full"])
    s.take("F22-tab-check-refine", win)

    tif = next(iter(sorted((dest / "runs" / "run1").glob("*_01.tif"))), None)
    if tif is not None:
        img = QImage(str(tif))
        print(f"    marquee image: {img.width()}x{img.height()}")
        marq.set_image(img)
        pump(app, 900)
        s.take("F40-scan-marquee", marq)
        census(scan_widget, "full/scan-marquee", marq, scans["full"])

    ti1 = next(iter(sorted((dest / "runs" / "run1").glob("*.ti1"))), None)
    cube_f = None
    if ti1 is not None:
        program = load_rgb_program(ti1)
        print(f"    cube patches: {len(program)}")
        cube_f = PatchCubeDialog(program, mode=MODE, target_name=SUBJECT, parent=win)
        cube_f.setWindowModality(Qt.WindowModality.NonModal)
        cube_f.resize(900, 760)
        cube_f.show()
        if ONSCREEN:
            cube_f.raise_()
        pump(app, 3500)
        s.take("F30-patch-cube", cube_f)
        census(scan_widget, "full/patch-cube", cube_f, scans["full"])

    # ---------------------------------------------------------------- report
    for name, group in scans.items():
        tot = sum(h["pixels"] for h in group)
        print(f"\n  {name}: {len(group)} widgets painting a hue, {tot} px")
        for h in sorted(group, key=lambda x: -x["pixels"])[:18]:
            print(f"    {h['where']:>24} {h['widget']}#{h['objectName']}: "
                  f"{h['pixels']} px ({h['share']}%) {[c for c, _ in h['colours'][:3]]}")

    (OUT / f"viewers-{MODE}.json").write_text(
        json.dumps({"mode": MODE, "shots": s.record, "scan": scans,
                    "modals": dismissed}, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT / f'viewers-{MODE}.json'}")

    for w in (cube_e, cube_f, marq, sp):
        if w is not None:
            w.close()
            w.setParent(None)
            w.deleteLater()
    pump(app, 400)
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
