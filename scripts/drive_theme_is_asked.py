#!/usr/bin/env python3
"""Drive the REAL ChromIQ window and ask the seven sites what they decide.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_theme_is_asked.py <outdir>

Seven places used to work the active appearance out by measuring how light a
background was. This opens the real main window, switches it between Light and
Dark through the app's own ``apply_appearance``, and for each of the seven
records the decision AND the pixels it produces — the actual icons where a site
picks an icon set. Run it once before the change and once after; the JSON files
must be identical.

Sandboxed: CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR and a custom_output_path
written into the .ini BEFORE anything builds an AppSettings, so a missing output
path can never fall back to the owner's real ~/ChromIQ. The run ends by checking
~/ChromIQ gained nothing.
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

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# SANDBOX ITSELF, BEFORE ANY ChromIQ IMPORT — do not rely on the shell.
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/themeask.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/themeask-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/themeask-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1
           else "/Users/Basti/Desktop/beta7/theme-ask-proof/onscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QSize                                     # noqa: E402
from PyQt6.QtGui import QFontDatabase, QIcon, QPalette             # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QGroupBox,     # noqa: E402
                             QLabel, QMessageBox, QWidget)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def save(pixmap, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))
    img = pixmap.toImage()
    b = img.bits()
    b.setsize(img.sizeInBytes())
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


def save_icon(icon: QIcon, size: int, path: Path,
              mode: QIcon.Mode = QIcon.Mode.Normal) -> str:
    return save(icon.pixmap(QSize(size, size), mode, QIcon.State.Off), path)


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

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance

    win = MainWindow(settings)
    win.show()
    if ONSCREEN:
        win.raise_()
        win.activateWindow()
    pump(app, 1200)

    report: dict[str, dict] = {}
    for mode in ("light", "dark"):
        print(f"\n=== {mode.upper()} ===")
        apply_appearance(app, win, mode)
        pump(app, 900)
        d = OUT / mode
        d.mkdir(parents=True, exist_ok=True)
        r: dict[str, object] = {}

        # The whole window, so the appearance itself is on the record.
        r["0_window_sha"] = save(win.grab(), d / "00-window.png")

        # -- 1. bar_icons: the disabled grey and the icon it draws -----------
        from ui.bar_icons import BarIconButton
        live = win.findChildren(BarIconButton)
        r["1_live_bar_icon_buttons"] = len(live)
        btn = live[0] if live else None
        if btn is not None:
            r["1_bar_icons_disabled_colour"] = btn._disabled_colour()
            r["1_bar_icons_disabled_icon_sha"] = save_icon(
                btn.icon(), btn.HEIGHT, d / "01-bar-icon-disabled.png",
                QIcon.Mode.Disabled)
            r["1_bar_icons_normal_icon_sha"] = save_icon(
                btn.icon(), btn.HEIGHT, d / "01-bar-icon-normal.png")

        # -- 2. cr30 pictograms: the Measure green, and a real drawing -------
        from ui.cr30_pictograms import WHITE_STEP, _accent, _ink, steps_pair
        from ui.dial_pictogram import dial
        r["2_cr30_accent"] = _accent(win).name()
        r["2_cr30_ink"] = _ink(win).name()
        r["2_cr30_steps_pair_sha"] = save(steps_pair(WHITE_STEP, win, height=220),
                                          d / "02-cr30-steps-pair.png")
        r["2_dial_pictogram_sha"] = save(dial("calibrate", win, size=220),
                                         d / "02-dial.png")

        # -- 3. scan-grid marquee: the well backdrop -------------------------
        from ui.scan_grid_marquee import ScanGridMarquee
        mq = ScanGridMarquee(win)
        mq.setGeometry(20, 20, 240, 180)
        mq.show()
        pump(app, 200)
        r["3_marquee_is_dark"] = bool(mq._is_dark())
        r["3_marquee_backdrop_sha"] = save(mq.grab(), d / "03-marquee.png")
        mq.hide()
        mq.setParent(None)
        mq.deleteLater()

        # -- 4. group-box surface, as the live filter painted it -------------
        from ui.widgets import _apply_groupbox_surface
        boxes = [gb for gb in win.findChildren(QGroupBox) if gb.isVisible()]
        r["4_live_groupboxes"] = len(boxes)
        if boxes:
            gb = boxes[0]
            r["4_live_groupbox_autofill"] = bool(gb.autoFillBackground())
            r["4_live_groupbox_window"] = gb.palette().color(
                QPalette.ColorRole.Window).name()
            r["4_live_groupbox_sha"] = save(gb.grab(), d / "04-groupbox.png")
        probe = QGroupBox("probe", win)
        _apply_groupbox_surface(probe)
        r["4_probe_autofill"] = bool(probe.autoFillBackground())
        r["4_probe_window"] = probe.palette().color(
            QPalette.ColorRole.Window).name()
        probe.setParent(None)
        probe.deleteLater()

        # -- 5. the icon SETS ------------------------------------------------
        from ui.widgets import (_is_light_palette, load_folder_icon,
                                load_preset_icon)
        r["5_is_light_palette"] = bool(_is_light_palette())
        r["5_folder_icon_sha"] = save_icon(load_folder_icon("folder"), 22,
                                           d / "05-folder.png")
        r["5_preset_plus_sha"] = save_icon(load_preset_icon("plus"), 16,
                                           d / "05-preset-plus.png")
        r["5_preset_minus_sha"] = save_icon(load_preset_icon("minus"), 16,
                                            d / "05-preset-minus.png")

        # -- 6. Check & Refine's scanner tip ---------------------------------
        from ui.tabs.tab_check_refine import _scanner_tip_on_dark
        r["6_check_refine_tip_on_dark"] = bool(_scanner_tip_on_dark())

        # -- 7. the scanner-target row, both accents -------------------------
        from ui.tabs.tab_measure import make_scanner_target_row
        host = QWidget(win)
        host.setGeometry(300, 20, 520, 200)
        green, _ = make_scanner_target_row(host, False)
        green.setGeometry(0, 0, 500, 90)
        violet, _ = make_scanner_target_row(
            host, False, accent="#9f82ff", hint_light="#5a3fc0",
            hint_dark="#cabfff")
        violet.setGeometry(0, 95, 500, 90)
        host.show()
        pump(app, 250)
        r["7_row_stylesheet"] = green.styleSheet()
        r["7_row_label_styles"] = [lb.styleSheet()
                                   for lb in green.findChildren(QLabel)
                                   if lb.styleSheet()]
        r["7_violet_label_styles"] = [lb.styleSheet()
                                      for lb in violet.findChildren(QLabel)
                                      if lb.styleSheet()]
        r["7_row_sha"] = save(host.grab(), d / "07-scanner-rows.png")
        host.hide()
        host.setParent(None)
        host.deleteLater()

        for k in sorted(r):
            print(f"  {k}: {r[k]!r}"[:160])
        report[mode] = r

    (OUT / "onscreen.json").write_text(json.dumps(report, indent=2,
                                                  sort_keys=True))
    print(f"\nwrote {OUT / 'onscreen.json'}")

    win.close()
    pump(app, 300)

    after_real = tree_hash(real_root)
    gained = sorted(set(after_real) - set(before_real))
    print(f"~/ChromIQ after: {len(after_real)} entries; gained {len(gained)}")
    if gained:
        print("  LEAK:", gained[:20])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
